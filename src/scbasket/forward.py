"""Forward-looking event label and its field-free baseline (F1b).

P1.5 and P3.4 both graded the control field against a label DERIVED from the variable
the field was competing against, and both failed the same way. This module builds the
replacement asked for in F1b: a label that is a FUTURE EVENT, so the field and the label
can disagree, and the field-free baseline the field has to beat.

``forward_label`` marks a sampled frame 1 when a shot of the SAME chance follows within
the horizon. ``baseline_features`` is spacing, matchup distances and the two clock
variables, computed without ever touching the control field. ``field_features`` is the
model's side: ``area_valuable`` (Luke Blomm's A_t, the ft^2 of court the offense both
reaches first and would score from), ``epc_share`` and P_off at the ball.

Everything is vectorized over the (N, 10, 2) arrays and returns one row per frame of the
GameFrames handed in, in that order, so the three pieces concatenate positionally.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scbasket.control import ControlParams, control_field
from scbasket.court import HOOP_X, Grid
from scbasket.epc import epc_share
from scbasket.frames import N_SIDE, GameFrames, get_or_build, matchup_with_fallback, subsample
from scbasket.io import Dataset
from scbasket.validation import rank_auc
from scbasket.value import ValueSurface

FPS = 25
HORIZON_S = 3.0
HORIZON_FRAMES = int(HORIZON_S * FPS)
MIN_POINTS = 0.5
OPEN_LEVEL = "open"


def frontcourt_mask(frames: GameFrames, chances: pd.DataFrame) -> np.ndarray:
    """(N,) True where the frame is at or after its chance's ``frontcourtFrame``.

    The control field is built over the offensive half only, so a frame with the ball
    still in the backcourt reads a field nobody is playing on yet. Chances whose
    ``frontcourtFrame`` is null are KEPT (True): the frame cannot be shown to be in the
    backcourt, and silently dropping them would bias the denominator. Callers report how
    many rows each of the two reasons accounts for.
    """
    frontcourt = chances["frontcourtFrame"].to_numpy(dtype=float)[frames.chance_idx]
    return np.isnan(frontcourt) | (frames.frame_idx >= frontcourt)


def forward_label(
    frames: GameFrames,
    shots: pd.DataFrame,
    chances: pd.DataFrame,
    *,
    horizon_frames: int = HORIZON_FRAMES,
    level: str | None = None,
) -> np.ndarray:
    """(N,) bool: does a shot of this frame's own chance follow within the horizon?

    A shot counts for frame t when its ``startFrame`` falls in (t, t + horizon_frames]
    AND it belongs to the same chance, so a shot taken by the other team after a turnover
    never labels the frames before it. Shots with a null ``startFrame`` or a null
    ``chanceId`` are ignored.

    ``level`` restricts to one ``contestLevel`` (``OPEN_LEVEL`` for the secondary label).
    That variant is partially circular by construction, because ``contestLevel`` derives
    from ``closestDefDist`` and the baseline carries matchup distances; F1b declares it
    secondary and reports it as context, never as the project's own evidence.

    The shot's chance is resolved through ``chances`` (``shots.chanceId`` -> the positional
    row that ``frames.chance_idx`` stores), NEVER by looking the shot's own frame up in
    ``frames``: the caller hands in a 0.2 s subsample, so four shots in five do not land on
    a sampled frame and a frame lookup silently drops them. Measured when that bug was
    live: base rate 0.076 instead of 0.176 on game 114086.
    """
    if horizon_frames < 1:
        raise ValueError("horizon_frames must be >= 1")

    keep = shots["startFrame"].notna() & shots["chanceId"].notna()
    if level is not None:
        keep &= shots["contestLevel"] == level
    shots = shots[keep]
    if shots.empty:
        return np.zeros(len(frames), dtype=bool)

    row_of_chance = pd.Series(np.arange(len(chances)), index=chances["id"])
    shot_chance = shots["chanceId"].map(row_of_chance).to_numpy(dtype=float)
    shot_frame = shots["startFrame"].to_numpy(dtype=np.int64)
    known = ~np.isnan(shot_chance)
    shot_chance, shot_frame = shot_chance[known].astype(np.int64), shot_frame[known]

    same = frames.chance_idx[:, None] == shot_chance[None, :]
    frame_idx = frames.frame_idx[:, None]
    within = (frame_idx > shot_frame[None, :] - horizon_frames) & (frame_idx <= shot_frame[None, :])
    return (same & within).any(axis=1)


def _pairwise_offense(xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mean and minimum pairwise distance among the five attackers, per frame."""
    diff = xy[:, :N_SIDE, None, :] - xy[:, None, :N_SIDE, :]
    dist = np.linalg.norm(diff, axis=-1)
    iu = np.triu_indices(N_SIDE, k=1)
    pairs = dist[:, iu[0], iu[1]]
    return pairs.mean(axis=1), pairs.min(axis=1)


def _ball_features(frames: GameFrames) -> tuple[np.ndarray, np.ndarray]:
    """Distance from the ball to the hoop, and from the ball holder to their nearest defender.

    The holder distance is NaN on frames with no resolved holder (``ball_holder < 0``,
    about 12-15% of frames per the cache summary): the estimator handles NaN natively and
    imputing a distance there would invent a defender.
    """
    ball_xy = frames.ball[:, :2].astype(np.float64)
    hoop = np.array([HOOP_X, 0.0])
    ball_hoop = np.linalg.norm(ball_xy - hoop, axis=1)

    holder = frames.ball_holder.astype(np.int64)
    has = holder >= 0
    slot = np.clip(holder, 0, N_SIDE - 1)[:, None, None]
    holder_xy = np.take_along_axis(frames.xy[:, :N_SIDE].astype(np.float64), slot, axis=1)[:, 0]
    to_def = np.linalg.norm(
        holder_xy[:, None, :] - frames.xy[:, N_SIDE:].astype(np.float64), axis=-1
    ).min(axis=1)
    return ball_hoop, np.where(has, to_def, np.nan)


def _secs_into_chance(frames: GameFrames) -> np.ndarray:
    """Seconds elapsed since the first CACHED frame of each chance.

    Measured against the cache, not against the chance's true start, because a chance
    whose opening frames were dropped by D12 has no usable origin here. Stated plainly
    rather than silently: this is a lower bound on the real elapsed time.
    """
    frame_idx = frames.frame_idx.astype(np.int64)
    _, inverse = np.unique(frames.chance_idx, return_inverse=True)
    first = np.full(inverse.max(initial=-1) + 1, np.iinfo(np.int64).max, dtype=np.int64)
    np.minimum.at(first, inverse, frame_idx)
    return (frame_idx - first[inverse]) / FPS


def nearest_cell(grid: Grid, points: np.ndarray) -> np.ndarray:
    """(N,) index of the grid cell nearest to each (N, 2) point, by lattice arithmetic.

    The brute-force alternative (argmin over an (N, G) distance matrix) allocates about
    700 MB for the five calibration games at the 1 ft grid. Measured, the wall clock barely
    moves (97.3 s per sweep cell against 104.3 s): the win here is memory, not time. The
    grid is a regular lattice in ``make_grid``'s ``indexing="ij"`` order, so the row is
    ``i * n_y + j`` and both indices follow from one rounding. Points outside the half
    court clamp to the edge cell, which is what the argmin returned too.
    """
    centers, cell = grid.centers, grid.cell_ft
    n_y = int(np.count_nonzero(centers[:, 0] == centers[0, 0]))
    n_x = len(centers) // n_y
    i = np.clip(np.round((points[:, 0] - centers[0, 0]) / cell), 0, n_x - 1)
    j = np.clip(np.round((points[:, 1] - centers[0, 1]) / cell), 0, n_y - 1)
    return (i * n_y + j).astype(np.int64)


def baseline_features(frames: GameFrames) -> pd.DataFrame:
    """The field-free baseline the control field has to beat (F1b).

    Spacing, matchup distances and the two clock variables. The clock is NOT optional:
    ``area_valuable`` grows while an offense sets up and shots come late, so a baseline
    without it would let the field win by proxying the shot clock. F1b's third criterion
    grades exactly that.
    """
    xy = frames.xy.astype(np.float64)
    off_mean, off_min = _pairwise_offense(xy)

    matchup = matchup_with_fallback(frames).astype(np.int64)
    defender_xy = np.take_along_axis(
        xy[:, N_SIDE:], matchup[:, :, None].repeat(2, axis=2), axis=1
    )
    matchup_dist = np.linalg.norm(xy[:, :N_SIDE] - defender_xy, axis=-1)

    ball_hoop, ball_def = _ball_features(frames)
    return pd.DataFrame(
        {
            "off_pairwise_mean": off_mean,
            "off_pairwise_min": off_min,
            "matchup_dist_mean": matchup_dist.mean(axis=1),
            "matchup_dist_min": matchup_dist.min(axis=1),
            "ball_hoop_dist": ball_hoop,
            "ball_def_dist": ball_def,
            "shot_clock": frames.shot_clock.astype(np.float64),
            "secs_into_chance": _secs_into_chance(frames),
        }
    )


CLOCK_FEATURES = ("shot_clock", "secs_into_chance")


def field_features(
    frames: GameFrames,
    grid: Grid,
    params: ControlParams,
    surface: ValueSurface,
    *,
    min_points: float = MIN_POINTS,
    batch: int = 64,
) -> pd.DataFrame:
    """The model's side: area_valuable (A_t), epc_share and P_off at the ball.

    ``area_valuable`` is the ft^2 of court whose expected points under offensive control
    reach ``min_points``: cells with ``P_off(c) * V(c) >= min_points``, times the grid's
    cell area. It is the quantity Luke Blomm's thread sums, recomputed on this project's
    own field and its own league value surface.
    """
    p_off = control_field(frames, grid, params, batch=batch)
    weighted = p_off * np.asarray(surface.values, dtype=np.float64)[None, :]
    cell_area = grid.cell_ft**2

    cell_of_ball = nearest_cell(grid, frames.ball[:, :2].astype(np.float64))
    return pd.DataFrame(
        {
            "area_valuable": (weighted >= min_points).sum(axis=1) * cell_area,
            "epc_share": epc_share(p_off, surface),
            "p_off_ball": p_off[np.arange(len(frames)), cell_of_ball],
        }
    )


# ------------------------------------------------------------------ leave-one-game-out grading

SEED = 0


def _classifier(seed: int):
    """HistGradientBoostingClassifier, imported lazily so scbasket installs without sklearn.

    scikit-learn is the `forward` optional extra, never a package dependency (pyproject).
    Everything else in scbasket runs on numpy and pandas alone, and this is the one place
    that needs a learner: F1b grades whether the field ADDS to a baseline, and a linear
    model would flatter whichever block of features happens to be the more linear one.
    """
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "F1b's grading needs scikit-learn: uv pip install 'scbasket[forward]'"
        ) from exc
    return HistGradientBoostingClassifier(random_state=seed)


def logo_scores(
    features: pd.DataFrame, label: np.ndarray, game: np.ndarray, *, seed: int = SEED
) -> np.ndarray:
    """Out-of-fold P(label) from leave-one-game-out gradient boosting.

    One model per held-out game, trained on every OTHER game's frames and scored on that
    game's. The fold is the GAME, never the frame or the shot: frames 0.2 s apart are all
    but identical, so a random split would train and test on the same possession and
    report an AUC that means nothing (lesson 1 in tasks/lessons.md, the other way round).
    NaN goes in untouched: HistGradientBoosting splits on missingness natively.
    """
    scores = np.full(len(features), np.nan)
    for held_out in np.unique(game):
        test = game == held_out
        model = _classifier(seed).fit(features[~test], label[~test])
        scores[test] = model.predict_proba(features[test])[:, 1]
    return scores


def fold_auc(scores: np.ndarray, label: np.ndarray, game: np.ndarray) -> pd.Series:
    """AUC per game, indexed by game id. NaN for a game whose label has only one class."""
    return pd.Series(
        {
            int(g): rank_auc(scores[game == g], label[game == g].astype(float))
            for g in np.unique(game)
        },
        dtype=float,
        name="auc",
    )


def delta_auc(
    baseline: pd.DataFrame,
    field: pd.DataFrame,
    label: np.ndarray,
    game: np.ndarray,
    *,
    seed: int = SEED,
) -> pd.DataFrame:
    """Per-game AUC of the baseline, of baseline + field, and their difference (F1b's criterion 1).

    Returns one row per game. NOTHING here pools: F1b grades the mean and the per-fold
    signs, and the caller prints every row before quoting either.
    """
    both = pd.concat([baseline.reset_index(drop=True), field.reset_index(drop=True)], axis=1)
    base_auc = fold_auc(logo_scores(baseline, label, game, seed=seed), label, game)
    full_auc = fold_auc(logo_scores(both, label, game, seed=seed), label, game)
    return pd.DataFrame({"auc_baseline": base_auc, "auc_with_field": full_auc}).assign(
        delta=lambda d: d["auc_with_field"] - d["auc_baseline"]
    )


def game_inputs(dataset: Dataset, game_id: int, cache_dir, every: int = 5) -> dict:
    """Everything about one game that does NOT depend on the control parameters.

    Sampled frames after the frontcourt filter, both labels and the field-free baseline.
    Split out from the field so a parameter sweep recomputes only ``field_features`` per
    cell instead of re-reading the tracking cache once per cell, and so P1.7 and P1.8
    build their rows through exactly the same code path.
    """
    frames = subsample(get_or_build(dataset, game_id, cache_dir), every)
    events = dataset.events(game_id)
    before = len(frames)
    frames = frames.take(frontcourt_mask(frames, events["chances"]))
    return {
        "game_id": game_id,
        "frames": frames,
        "n_sampled": before,
        "n_backcourt_dropped": before - len(frames),
        "label": forward_label(frames, events["shots"], events["chances"]),
        "label_open": forward_label(frames, events["shots"], events["chances"], level=OPEN_LEVEL),
        "baseline": baseline_features(frames),
    }
