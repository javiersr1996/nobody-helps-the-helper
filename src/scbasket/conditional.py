"""The conditional rebound model: exactly one of the ten on court wins the board (P7.3).

Ten independent probabilities is the wrong structure for a rebound. One player wins it and
nine do not, so the quantities that matter are conditional on the other nine being there: a
player 4 ft from the rim driving at it is well placed against four retreating opponents and
badly placed against two crashing bigs. A model of independent probabilities cannot say that,
and its numbers do not sum to one.

So the model here is a conditional logit over the ten players present. Each player gets a
score from their own kinematics, and the probability that player i wins is their score's share
of the ten exponentiated scores. The probabilities sum to one per rebound BY CONSTRUCTION,
which is not a property to be checked afterwards but the reason for this shape.

What goes into the score, half a second before the ball is won:
  - `zone_ratio`: distance to the rim in units of the zone that shot earned (P7.2), so being
    6 ft out means one thing on a layup and another on a three,
  - `rimward`: the cosine of the approach angle, +1 driving straight at the rim, -1 running
    away, 0 moving across it,
  - `speed`,
  - `no_heading`: 1 where the player is below `MIN_APPROACH_SPEED` and a heading would be
    numerically meaningless. These players are kept in the choice set with `rimward` set to
    0, because dropping a player would break the one thing this structure guarantees,
  - `offense`: 1 for the five attackers, which carries the base rate (they win about 30%).

Every feature is a position or a velocity. None of them claims to know what a player meant to
do, which is the ruling this whole layer is built under.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scbasket.frames import GameFrames, at_frames
from scbasket.tagging import (
    APPROACH_LEAD_FRAMES,
    approach_angles,
    zone_radius,
)
from scbasket.validation import hoop_distance

N_PLAYERS = 10

#: Column order of the (N, 10, K) design. Frozen: the coefficients below are read by position.
FEATURES = ("zone_ratio", "rimward", "speed", "no_heading", "offense")

#: The zone used when a rebound's shot has no published location (5% of them): the constant
#: 8 ft band P7.2 replaced. The alternative is dropping the rebound, and a missing shot
#: location says nothing about who was best placed to win the ball.
FALLBACK_ZONE_FT = 8.0

#: FROZEN on the CALIBRATION games on 2026-09-17, committed before any held-out game was read
#: (D11), in the order of `FEATURES`. `scripts/rebound_contest.py --fit` re-derives them.
FROZEN_BETA = (-0.871, 0.739, 0.124, 0.317, -0.456)

#: The same fit with `zone_ratio` replaced by the raw distance to the rim in feet. Kept
#: because the two are indistinguishable on calibration (-1.8583 against -1.8607 per rebound)
#: and saying so is more useful than implying the shot-scaled version earned its place here.
FROZEN_BETA_RIM_DIST = (-0.113, 0.716, 0.125, 0.302, -0.441)

#: Distance alone, the baseline the full model has to beat: every rebound is won near the rim,
#: so a model that only knows that is the honest thing to compare against.
FROZEN_BETA_DISTANCE_ONLY = (-0.850, 0.0, 0.0, 0.0, -0.400)


def rebound_choice_set(
    frames: GameFrames,
    rebounds: pd.DataFrame,
    shots: pd.DataFrame,
    *,
    lead_frames: int = APPROACH_LEAD_FRAMES,
    rim_distance_feature: bool = False,
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """(K-feature design, winning slot, one row per rebound) for one game.

    Returns `X` of shape (kept, 10, len(FEATURES)), `y` of shape (kept,) holding the slot of
    the player who actually won, and `rows`, which has one row for EVERY rebound passed in,
    kept or not, with `drop_reason` set on the ones that could not be used. The three reasons
    are a rebound with no frame `lead_frames` earlier in the cache, a rebound the provider
    attributes to nobody, and one whose rebounder is not among the ten on court. The caller
    reports those counts; they are never dropped quietly.

    Slots 0-4 are the attacking team and 5-9 the defending team, the same order
    `approach_angles` reads, so `y` indexes straight into the model's output.

    With `rim_distance_feature`, the first column carries the raw distance to the rim in feet
    instead of its ratio to the shot-scaled zone. The two are otherwise identical, and the
    frozen coefficients for each are `FROZEN_BETA` and `FROZEN_BETA_RIM_DIST`.
    """
    rows = pd.DataFrame({
        "rebound_id": rebounds["id"].to_numpy(),
        "shot_id": rebounds["shotId"].to_numpy(),
        "defensive": rebounds["defensive"].astype("boolean").to_numpy(),
        "frame": rebounds["frame"].to_numpy(dtype=float),
        "shot_dist": hoop_distance(rebounds["shotId"].map(shots.set_index("id")["location"])),
        "winner_slot": np.nan,
        "drop_reason": pd.Series([None] * len(rebounds), dtype=object),
    })
    if len(rebounds) == 0:
        return np.zeros((0, N_PLAYERS, len(FEATURES))), np.zeros(0, dtype=np.int64), rows

    target = rows["frame"].to_numpy() - lead_frames
    found = np.isin(target, frames.frame_idx) & np.isfinite(target)
    rows.loc[~found, "drop_reason"] = "no frame at the lead"

    at = at_frames(frames, target[found].astype(np.int64))
    kin = approach_angles(at)
    ids = np.concatenate([at.off_ids, at.def_ids], axis=1)
    rebounder = rebounds["rebounderId"].to_numpy()[found]

    zone = zone_radius(rows["shot_dist"].to_numpy()[found])
    zone = np.where(np.isfinite(zone), zone, FALLBACK_ZONE_FT)
    distance = kin["rim_dist"] if rim_distance_feature else kin["rim_dist"] / zone[:, None]
    slow = ~np.isfinite(kin["angle"])
    design = np.stack([
        distance,
        np.where(slow, 0.0, np.cos(np.radians(np.nan_to_num(kin["angle"])))),
        kin["speed"],
        slow.astype(np.float64),
        np.tile(np.arange(N_PLAYERS) < N_PLAYERS // 2, (len(at), 1)).astype(np.float64),
    ], axis=-1)

    winner = np.asarray(rebounder, dtype=float)[:, None] == ids
    n_winners = winner.sum(axis=1)
    usable = n_winners == 1
    at_rows = np.flatnonzero(found)
    reason = np.where(pd.isna(rebounder), "no rebounder", "winner not on court")
    rows.loc[at_rows[~usable], "drop_reason"] = reason[~usable]
    rows.loc[at_rows[usable], "winner_slot"] = winner[usable].argmax(axis=1)
    return design[usable], winner[usable].argmax(axis=1), rows


def choice_probabilities(X: np.ndarray, beta) -> np.ndarray:
    """(N, 10) probability that each player wins, summing to one per rebound by construction."""
    scores = np.asarray(X, dtype=np.float64) @ np.asarray(beta, dtype=np.float64)
    scores = scores - scores.max(axis=1, keepdims=True)
    weights = np.exp(scores)
    return weights / weights.sum(axis=1, keepdims=True)


def log_likelihood(X: np.ndarray, y: np.ndarray, beta) -> float:
    """Mean log probability the model puts on the player who actually won the ball.

    Per rebound rather than summed, so the two halves are comparable at different sizes. A
    model that knows nothing scores log(1/10) = -2.303.
    """
    if len(y) == 0:
        return np.nan
    return float(np.log(choice_probabilities(X, beta)[np.arange(len(y)), y]).mean())


def top1_accuracy(X: np.ndarray, y: np.ndarray, beta) -> float:
    """Share of rebounds whose actual winner the model ranks first among the ten present."""
    if len(y) == 0:
        return np.nan
    return float((choice_probabilities(X, beta).argmax(axis=1) == y).mean())


def fit_conditional_logit(
    X: np.ndarray, y: np.ndarray, *, max_iter: int = 50, tol: float = 1e-10
) -> np.ndarray:
    """Newton fit of the conditional logit; returns the coefficients in `FEATURES` order.

    The log-likelihood of a conditional logit is concave, so Newton converges to the single
    maximum from a zero start in a handful of steps and there is nothing to tune. Written in
    numpy on purpose: this model is a core deliverable and the package installs without
    scikit-learn.

    A column that is constant across the ten players of every rebound cannot be identified,
    because the softmax subtracts it away, and the Hessian is singular in that direction.
    That is raised rather than silently returning whatever the solver lands on.
    """
    X = np.asarray(X, dtype=np.float64)
    n, _, k = X.shape
    varies = np.abs(X - X.mean(axis=1, keepdims=True)).max(axis=(0, 1)) > 1e-12
    if not varies.all():
        dead = [FEATURES[i] for i in np.flatnonzero(~varies)] if k == len(FEATURES) else \
            list(np.flatnonzero(~varies))
        raise ValueError(f"constant within every choice set, so not identified: {dead}")

    beta = np.zeros(k)
    chosen = X[np.arange(n), y]
    for _ in range(max_iter):
        p = choice_probabilities(X, beta)
        mean_x = np.einsum("ij,ijk->ik", p, X)
        gradient = (chosen - mean_x).sum(axis=0)
        second = np.einsum("ij,ijk,ijl->kl", p, X, X)
        hessian = -(second - np.einsum("ik,il->kl", mean_x, mean_x))
        step = np.linalg.solve(hessian, gradient)
        beta = beta - step
        if np.abs(step).max() < tol:
            break
    return beta
