"""Rank-based validation metrics for scbasket.

Pure numpy, no sklearn/scipy: the model is graded against ground truth
(`contestLevel`, `shotQuality`) with rank statistics computed from first
principles, because the acceptance criteria in the project plan (P1.5, P2.3)
need exact control over tie handling and the permutation scheme.

This module holds the four statistics helpers below (`rank_auc`, `spearman`,
`partial_spearman`, `permutation_pvalue`), which depend on nothing, plus
`release_features`, appended after them, which does depend on `control.py`
and `epc.py`, and `calibrate` (P1.4), the grid search over the control
parameters on the release frames of the calibration games. `pick_windows`
and `break_points` are appended below by a later change (P1.5).
"""

from __future__ import annotations

import functools
import itertools
from collections.abc import Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from scbasket.control import (
    ControlParams,
    control_at_points,
    control_at_points_with_uncertainty,
    control_field,
)
from scbasket.court import Grid
from scbasket.epc import epc_share
from scbasket.frames import N_SIDE, GameFrames, at_frames
from scbasket.value import ValueSurface


def _midranks(x: np.ndarray) -> np.ndarray:
    """1-based ranks of `x`, averaging ranks within ties (midrank convention).

    Matches `pandas.Series.rank()`'s default (`method="average"`), which is
    what the Mann-Whitney U <-> AUC identity and pandas' own Spearman
    implementation both rely on. Fully vectorized: no Python loop over ties.
    """
    order = np.argsort(x, kind="mergesort")
    plain_ranks = np.empty(x.shape[0], dtype=float)
    plain_ranks[order] = np.arange(1, x.shape[0] + 1, dtype=float)
    _, inverse, counts = np.unique(x, return_inverse=True, return_counts=True)
    sums = np.zeros(counts.shape[0], dtype=float)
    np.add.at(sums, inverse, plain_ranks)
    return (sums / counts)[inverse]


def _pearson_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation of two already-cleaned 1-D arrays; NaN if either is constant."""
    a = a - a.mean()
    b = b - b.mean()
    denom = np.sqrt((a**2).sum() * (b**2).sum())
    if denom == 0:
        return float("nan")
    return float((a * b).sum() / denom)


def _ols_residuals(z: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Residuals of the OLS regression of `target` on `z` (with intercept).

    `z` is (n,) for one control or (n, k) for several. If `z` is constant there
    is nothing to regress on: the residual is just `target`'s deviation from
    its own mean, i.e. no control is applied. With several controls the fit is
    a least-squares solve on the centred columns (numpy.linalg.lstsq, minimum
    norm), which stays defined when columns are constant or collinear: a
    redundant control changes nothing. The one-control path is the closed form
    and is untouched by the (n, k) case.
    """
    target_centered = target - target.mean()
    if z.ndim == 2:
        z_centered = z - z.mean(axis=0)
        beta = np.linalg.lstsq(z_centered, target_centered, rcond=None)[0]
        return target_centered - z_centered @ beta
    z_centered = z - z.mean()
    var_z = (z_centered**2).sum()
    if var_z == 0:
        return target_centered
    slope = (z_centered * target_centered).sum() / var_z
    return target_centered - slope * z_centered


def rank_auc(score: np.ndarray, label: np.ndarray) -> float:
    """Area under the ROC curve, computed from ranks (Mann-Whitney U statistic).

    `label` must be binary (0/1 or bool). AUC is the probability that a
    randomly drawn positive (`label == 1`) outranks a randomly drawn
    negative, with tied scores counted as one half -- no sklearn, no scipy.
    Ties use the midrank convention (`_midranks`).

    NaN policy: rows where `score` or `label` is NaN are dropped pairwise
    before ranking. Returns NaN if fewer than 3 valid pairs remain, or if
    `label` has only one class (AUC is undefined with no negatives, or no
    positives, to compare against). A constant `score` is NOT a degenerate
    case: every pair ties and the midrank formula correctly returns 0.5.
    """
    score = np.asarray(score, dtype=float)
    label = np.asarray(label, dtype=float)
    valid = ~(np.isnan(score) | np.isnan(label))
    score, label = score[valid], label[valid]

    if score.shape[0] < 3:
        return float("nan")

    positive = label == 1
    n1, n0 = int(positive.sum()), int((~positive).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")

    ranks = _midranks(score)
    r1 = ranks[positive].sum()
    u1 = r1 - n1 * (n1 + 1) / 2
    return float(u1 / (n1 * n0))


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rank correlation, matching `pandas.Series.corr(method="spearman")`.

    Ties use the midrank convention (`_midranks`), the same one pandas'
    `.rank()` uses by default, then it is the Pearson correlation of the two
    rank arrays.

    NaN policy: rows where `a` or `b` is NaN are dropped pairwise. Returns
    NaN if fewer than 3 valid pairs remain, or if `a` or `b` is constant
    (no variance to correlate).
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    valid = ~(np.isnan(a) | np.isnan(b))
    a, b = a[valid], b[valid]

    if a.shape[0] < 3:
        return float("nan")
    if np.all(a == a[0]) or np.all(b == b[0]):
        return float("nan")

    return _pearson_corr(_midranks(a), _midranks(b))


def partial_spearman(y: np.ndarray, x: np.ndarray, z: np.ndarray) -> float:
    """Partial Spearman correlation of `y` and `x` controlling for `z`, via rank residuals.

    Answers "does `x` carry information about `y` beyond `z`". Method (as
    specified in the project plan, not the textbook first-order-partial
    formula): rank-transform `y`, `x` and `z` (midranks), regress ranked `y`
    and ranked `x` on ranked `z` by ordinary least squares, and correlate
    the two residuals (Pearson).

    `z` is one control, shape (n,), or several at once, shape (n, k): each
    column is ranked on its own and the two regressions use all of them
    jointly (one least-squares fit with an intercept, not one control after
    another, which would only agree if the controls were orthogonal). P1.5's
    "controlling for closestDefDist" is the (n,) case; "controlling for
    closestDefDist and three" the (n, 2) case. A (n, 1) `z` gives the (n,)
    answer.

    NaN policy: rows where any of `y`, `x`, `z` (any column) is NaN are
    dropped rowwise. Returns NaN if fewer than 3 valid rows remain, or if
    `y` or `x` is constant (nothing to correlate). A constant `z` is NOT a
    degenerate case: `_ols_residuals` then applies no control and this
    reduces to plain `spearman(y, x)`, which is the mathematically correct
    answer for "controlling for a variable that never varies". If the
    residuals of `y` or `x` end up constant (e.g. `y` is an exact monotonic
    function of `z`, so ranking removes all of its variance), the
    correlation is undefined and NaN is returned.
    """
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    z_nan = np.isnan(z) if z.ndim == 1 else np.isnan(z).any(axis=1)
    valid = ~(np.isnan(y) | np.isnan(x) | z_nan)
    y, x, z = y[valid], x[valid], z[valid]

    if y.shape[0] < 3:
        return float("nan")
    if np.all(y == y[0]) or np.all(x == x[0]):
        return float("nan")

    ry, rx = _midranks(y), _midranks(x)
    rz = _midranks(z) if z.ndim == 1 else np.column_stack([_midranks(col) for col in z.T])
    resid_y = _ols_residuals(rz, ry)
    resid_x = _ols_residuals(rz, rx)
    return _pearson_corr(resid_y, resid_x)


def permutation_pvalue(
    stat: Callable[..., float] | float,
    groups: Sequence[np.ndarray] | np.ndarray,
    n: int = 2000,
    rng: np.random.Generator | None = None,
) -> float:
    """One-sided permutation p-value: the share of the null draws >= the observed statistic.

    Two calling conventions, chosen to cover both places this project needs a
    permutation test (P1.5, P2.3), which shuffle fundamentally different
    things:

    1. `stat` callable, `groups` a sequence of 1-D arrays of equal length
       that are the thing being permuted (everything else `stat` needs is
       captured by closure). Each of the `n` draws applies one shared random
       permutation index to every array in `groups` (so their relative order
       to each other survives, only their pairing to whatever is captured by
       closure is broken), then calls `stat(*permuted_groups)`. The observed
       statistic is `stat(*groups)` (unpermuted). This is P1.5's case:
       `permutation_pvalue(lambda x: partial_spearman(y, x, z), groups=(x,))`
       shuffles `x` while `y` and `z` (closed over) stay fixed. It is also
       the classic two-sample label-shuffle test: pool the values into one
       array `v`, build a 0/1 window-label array `w`, and call
       `permutation_pvalue(lambda w: v[w == 1].mean() - v[w == 0].mean(),
       groups=(w,))` -- P2.3's "does the screener's `created` rise between
       the two windows" case.
    2. `stat` a plain number (the already-computed observed statistic) and
       `groups` the already-simulated null distribution (an array of one
       statistic value per permutation draw). `n` and `rng` are ignored.
       This exists for callers whose shuffle needs domain logic this module
       has no business knowing (P2.3's actual `created` aggregation lives in
       `scripts/space_creation.py` and reshuffles window labels over
       frame-level data, not a plain array this module could permute
       generically); they run their own permutation loop and hand the
       resulting numbers here just for the p-value arithmetic.

    Both of this project's uses ask for a one-sided test ("> 0", "rises"),
    so the p-value is always `P(null >= observed)`, never two-sided.

    Reproducibility: pass an explicit `rng` (a `numpy.random.Generator`,
    e.g. `np.random.default_rng(seed)`); the same seed gives the same
    p-value. Without one, a fresh, unseeded generator is used.

    NaN policy: returns NaN if fewer than 3 data points are available to
    permute (mode 1: `len(groups[0]) < 3`; mode 2: `len(groups) < 3`), if the
    observed statistic is NaN, or if fewer than 3 non-NaN null draws remain
    (NaN null draws, e.g. from a degenerate shuffle, are dropped). Uses the
    standard add-one correction so the p-value is never exactly 0.
    """
    if callable(stat):
        arrays = [np.asarray(g) for g in groups]
        if not arrays or arrays[0].shape[0] < 3:
            return float("nan")
        length = arrays[0].shape[0]
        if any(a.shape[0] != length for a in arrays):
            raise ValueError("all arrays in `groups` must have the same length")

        rng = np.random.default_rng() if rng is None else rng
        observed = float(stat(*arrays))
        null = np.empty(n, dtype=float)
        for i in range(n):
            perm = rng.permutation(length)
            null[i] = stat(*(a[perm] for a in arrays))
    else:
        observed = float(stat)
        null = np.asarray(groups, dtype=float).ravel()
        if null.shape[0] < 3:
            return float("nan")

    if np.isnan(observed):
        return float("nan")

    null = null[~np.isnan(null)]
    if null.shape[0] < 3:
        return float("nan")

    exceed = int(np.sum(null >= observed))
    return float((exceed + 1) / (null.shape[0] + 1))


# --------------------------------------------------------------------------- release_features

DISK_RADIUS_FT = 3.0  # p_off_disk radius around the shooter (plan spec)
_DISK_CELL_FT = 1.0  # disk sampling lattice, matching D4's 1 ft grid resolution
_MC_SAMPLES = 20  # D8: K = 20 Monte Carlo draws per event frame
_MC_SEED = 0  # release_features takes no rng parameter (SPEC), so p_off_std is derived from
# a fresh, fixed-seed Generator on every call: reproducible, and it never touches global
# numpy random state, without changing the function's public signature.

# shots columns copied through verbatim (provider's names): the ground truth the later
# calibration/validation tasks (P1.4, P1.5) grade the model against, plus enough context
# (region, shotClock, startFrame) to slice the results without rejoining shots.
_SHOT_COLUMNS = (
    "contestLevel", "shotQuality", "closestDefDist", "outcome", "three", "shotClock", "region",
    "startFrame",
)


def _disk_offsets(radius_ft: float = DISK_RADIUS_FT, cell_ft: float = _DISK_CELL_FT) -> np.ndarray:
    """(K, 2) offsets tiling a disk of the given radius on a regular cell_ft lattice."""
    n = int(np.ceil(radius_ft / cell_ft))
    xs = np.arange(-n, n + 1, dtype=np.float64) * cell_ft
    xx, yy = np.meshgrid(xs, xs, indexing="ij")
    offsets = np.column_stack([xx.ravel(), yy.ravel()])
    return offsets[np.hypot(offsets[:, 0], offsets[:, 1]) <= radius_ft]


_DISK_OFFSETS = _disk_offsets()


def _disk_mean(frames: GameFrames, centers: np.ndarray, params: ControlParams) -> np.ndarray:
    """Mean P_off over a small disk of points (DISK_RADIUS_FT) around one centre per frame.

    control_at_points takes one point per frame, so the disk is swept with one call per
    offset (a fixed, small count, not one per frame) and averaged; every call is fully
    vectorized over frames, so this stays inside the "no Python loop per frame" rule.
    """
    samples = np.stack(
        [control_at_points(frames, centers + offset, params) for offset in _DISK_OFFSETS], axis=1
    )
    return samples.mean(axis=1)


def _voronoi_at_points(frames: GameFrames, points: np.ndarray) -> np.ndarray:
    """Nearest-player Voronoi baseline (scbasket.control.voronoi_field) at one point per frame.

    control.py only evaluates Voronoi over a shared grid (voronoi_field); this is the same
    definition (1.0 where the nearest of the 10 players is an attacker, 0.0 a defender, 0.5
    on an exact tie) at an arbitrary per-frame point instead, which release_features needs
    for voronoi_shooter and control.py has no reason to carry for a single point.
    """
    diff = frames.xy.astype(np.float64) - points[:, None, :]
    d2 = (diff * diff).sum(axis=-1)  # (N, 10)
    d_off = d2[:, :N_SIDE].min(axis=1)
    d_def = d2[:, N_SIDE:].min(axis=1)
    return np.where(d_off < d_def, 1.0, np.where(d_off > d_def, 0.0, 0.5))


def _voronoi_disk_mean(frames: GameFrames, centers: np.ndarray) -> np.ndarray:
    """Mean Voronoi occupancy over the same disk _disk_mean uses for P_off.

    This is the baseline P1.5 compares the control field against. It samples the disk
    rather than the centre because Voronoi AT a player's own position is constant by
    construction (see voronoi_shooter), which makes it worthless as a comparator. Sharing
    _DISK_OFFSETS with p_off_disk keeps the two models on identical geometry, so the
    comparison isolates the model and not the support it is measured on.
    """
    samples = np.stack(
        [_voronoi_at_points(frames, centers + offset) for offset in _DISK_OFFSETS], axis=1
    )
    return samples.mean(axis=1)


def match_shots_to_release(
    frames: GameFrames, shots: pd.DataFrame
) -> tuple[pd.DataFrame, GameFrames, np.ndarray]:
    """Shots matched to a release frame in `frames`, that frame, and the shooter's (N, 2) xy.

    A shot is DROPPED, never padded with NaN, when: its startFrame is null; the exact frame
    is absent from `frames` (by far the most common cause -- D12 already dropped it before
    caching, typically because the shot's chance has usable == False, occasionally a null
    shotClock; see the release_features docstring for the measured breakdown); or the
    shooterId is not among that frame's five offensive slots (0 cases measured on the 10
    published games, kept here only as a safety net, e.g. against a data revision).

    Public (not `_`-prefixed) because release_features and
    scripts/shot_contest_uncertainty.py (P1.2) both need it: the script computes
    p_off_mean/p_off_std at the shooter's position over the same matched release frames,
    and duplicating this matching would risk the two silently diverging.
    """
    shots = shots[shots["startFrame"].notna()]
    start_frame = shots["startFrame"].to_numpy(dtype=np.int64)
    found = np.isin(start_frame, frames.frame_idx)
    shots, start_frame = shots[found], start_frame[found]

    release = at_frames(frames, start_frame)
    is_shooter = release.off_ids == shots["shooterId"].to_numpy()[:, None]
    has_shooter = is_shooter.any(axis=1)
    shooter_slot = is_shooter[has_shooter].argmax(axis=1)
    shots, release = shots[has_shooter], release.take(has_shooter)

    shooter_xy = release.xy[np.arange(len(release)), shooter_slot].astype(np.float64)
    return shots.reset_index(drop=True), release, shooter_xy


def release_features(
    frames: GameFrames,
    shots: pd.DataFrame,
    grid: Grid,
    params: ControlParams,
    surface: ValueSurface,
) -> pd.DataFrame:
    """One row per shot of `shots` (one game) matched to its release frame in `frames`.

    `frames` and `shots` are one game's worth (e.g. `get_or_build(dataset, game_id, cache_dir)`
    and `dataset.events(game_id)["shots"]`); callers loop over games and concatenate. Columns:

    - `p_off_shooter`: P_off (control.control_at_points) at the shooter's tracked position
      at release.
    - `p_off_disk`: mean P_off over a DISK_RADIUS_FT = 3 ft disk around that position.
    - `epc_share`: the whole-frame share of court value under offensive control (epc.py),
      evaluated on `grid`/`surface` at the release frame.
    - `voronoi_shooter`: Voronoi at the shooter's own position. It is exactly 1.0 for
      every shot, always: a player is their own nearest player, so this carries no
      information and its AUC is 0.5 by construction. Kept only as the visible evidence
      for why the P1.5 baseline is `voronoi_disk`; never report it as a baseline.
    - `voronoi_disk`: mean Voronoi occupancy over the same 3 ft disk as `p_off_disk`.
      This is the P1.5 baseline, on geometry identical to the control feature it is
      compared against (user decision of 2026-09-15).
    - `closest_def_dist`: shooter-to-nearest-defender distance, recomputed from `frames.xy`
      at the release frame -- independently of the provider's own `closestDefDist` column,
      which is carried through unchanged alongside it for comparison. Two distances agreeing
      is a reproduction of the provider's arithmetic (same tracking, same formula), not
      evidence the *model* works; only p_off_shooter / p_off_disk / epc_share are validated
      against ground truth (contestLevel, shotQuality) in P1.4/P1.5.
    - `p_off_std`: standard deviation of P_off at the shooter's position over D8's Monte
      Carlo perturbation (control.control_at_points_with_uncertainty, K = `_MC_SAMPLES`
      = 20 draws, each player displaced by its own quality.sigma_from_pred_error(predError)).
      This is P1.2's principled replacement for the heuristic ambiguity bound of
      `scripts/shot_contest_uncertainty.py` ("is closestDefDist smaller than its own
      measurement error"): it propagates the same predError through the model itself
      instead of through a hand-built margin. release_features has no `rng` parameter
      (fixed by the SPEC), so the draws use a fresh, fixed-seed Generator private to this
      call (`_MC_SEED`) -- deterministic and reproducible without touching global numpy
      random state or widening this function's signature.
    - the columns named in _SHOT_COLUMNS, copied through from `shots` unchanged, plus
      `game_id` (from `frames.game_id`).

    Matching and its yield: of the 1,459 shot events across the 10 published games, 1,433
    carry both a `location` and a `region` (a different, unrelated denominator: P0.2/P0.3's
    zone-agreement checks). This function's own denominator is how many get a release frame
    with both lineups on the floor. `scripts/shot_contest_uncertainty.py` (P1.2's starting
    point) matches shots directly against the raw tracking stream -- any frame carrying the
    shooter and at least two defenders at the exact startFrame, independent of D12 -- and
    reaches 1,445 (an earlier count of 1,414 for this same raw-stream match does not
    reproduce and must not be cited: confirmed under three independent matching criteria,
    see tasks/todo.md). This function instead matches against `frames`, the D12-filtered
    GameFrames cache that control_at_points/control_field require (oriented positions,
    velocity, shot clock: none of that exists for a frame D12 already dropped), so it can
    only ever match a subset of the full 1,459. Measured on the 10 published games: 1,360.
    The 99-shot gap from 1,459 is not a matching bug -- 0 shots fail on a missing shooter
    once their frame is found -- it is exactly D12's model-readiness filters removing frames
    that the raw stream still has: 93 shots sit in a chance with usable == False and 6 have
    a null shotClock; both are frames the control model cannot evaluate (no resolved chance,
    or no shot-clock horizon to project velocity over), not shots the matching logic failed
    to find.
    """
    shots_matched, release, shooter_xy = match_shots_to_release(frames, shots)

    field = control_field(release, grid, params)
    out = pd.DataFrame({"game_id": np.full(len(shots_matched), frames.game_id, dtype=np.int64)})
    out["p_off_shooter"] = control_at_points(release, shooter_xy, params)
    out["p_off_disk"] = _disk_mean(release, shooter_xy, params)
    out["epc_share"] = epc_share(field, surface)
    out["voronoi_shooter"] = _voronoi_at_points(release, shooter_xy)
    out["voronoi_disk"] = _voronoi_disk_mean(release, shooter_xy)
    def_xy = release.xy[:, N_SIDE:].astype(np.float64)
    out["closest_def_dist"] = np.linalg.norm(def_xy - shooter_xy[:, None, :], axis=-1).min(axis=1)
    _, out["p_off_std"] = control_at_points_with_uncertainty(
        release, shooter_xy, params, samples=_MC_SAMPLES, rng=np.random.default_rng(_MC_SEED)
    )
    for column in _SHOT_COLUMNS:
        out[column] = shots_matched[column].to_numpy()
    return out


# --------------------------------------------------------------------------- calibrate

# D11: the five oldest games by date calibrate the control parameters; the other five are
# held out for P1.5 and nothing on the calibration path may read them. The ids are written
# out here rather than derived from Dataset.game_ids at run time so the split is visible in
# the code and cannot drift with the dataset; scripts/calibrate_control.py checks them
# against matches.json's dates before running anything.
CALIBRATION_GAMES = (114243, 114234, 114169, 114099, 114086)

# The AUC's positive class: the objective grades `open` against the four other contest
# levels (light, average, plus, blocked). This is the reading P1.3's figures used and the
# one the pre-registered P1.5 threshold refers to. It is NOT the provider's `contested`
# boolean, which groups `light` with `open` (contested == contestLevel in {average, plus,
# blocked}, exact on the five calibration games): that is a different question, and it was
# fixed as "not the objective" before the sweep ran. A shot with a null contestLevel has no
# ground truth and is dropped by rank_auc's NaN policy, not counted as contested (P1.3's
# quoted 0.7213 counted 7 such shots as contested; dropping them gives 0.7221).
OPEN_LEVEL = "open"


def open_label(contest_level: pd.Series) -> np.ndarray:
    """1.0 where contestLevel is OPEN_LEVEL, 0.0 for any other level, NaN where it is missing."""
    label = (contest_level == OPEN_LEVEL).to_numpy(dtype=float)
    label[contest_level.isna().to_numpy()] = np.nan
    return label


def _param_cells(param_grid: Mapping[str, Sequence[float]]) -> list[dict[str, float]]:
    """Every cell of the Cartesian product of `param_grid`, in itertools.product order."""
    if "slope" in param_grid:
        raise ValueError(
            "slope is not a calibration dimension: P_off = sigmoid(slope * score) is monotone "
            "in the score, so every rank metric is invariant to it (D1 amendment)"
        )
    names = list(param_grid)
    return [
        dict(zip(names, values, strict=True))
        for values in itertools.product(*(param_grid[name] for name in names))
    ]


def calibrate(
    frames_by_game: Mapping[int, GameFrames],
    shots_by_game: Mapping[int, pd.DataFrame],
    param_grid: Mapping[str, Sequence[float]],
) -> pd.DataFrame:
    """Grid search of the control parameters on the release frames of the given games (P1.4).

    One row per cell of the Cartesian product of `param_grid` (keys are ControlParams
    field names, e.g. {"r_near": [3, 4], "r_far": [8, 10], "t_h": [0, 0.3]}; fields not
    in the grid keep their ControlParams defaults), in itertools.product order. Per cell:

    - `auc_open`: rank_auc of P_off at the shooter's tracked position (control_at_points,
      the same call release_features makes for p_off_shooter), `open` against every other
      contest level (OPEN_LEVEL).
    - `spearman_quality`: spearman of that same P_off with the provider's shotQuality.
    - `objective`: their sum, the quantity the plan maximises; NaN if either term is.
    - `p_off_disk_auc`, `voronoi_disk_auc`: the same AUC for p_off_disk and for the P1.5
      baseline (release_features' voronoi_disk), so the margin P1.5 pre-registers (p_off_disk
      against voronoi_disk, identical geometry) can be read off the table. voronoi_disk does
      not depend on the parameters, so its column is constant across cells.
    - `closest_def_dist_auc`, `closest_def_dist_spearman`: the two objective terms for the
      shooter-to-nearest-defender distance alone (release_features' closest_def_dist), the
      third model of P1.5's table. Also parameter-free and constant across cells. It is the
      reference that says whether a cell adds anything to plain distance, and it bounds what
      contestLevel can reward: the provider derives that label from this same distance.
    - `n_shots`, `n_open`, `n_other`, `n_quality`: the denominators. Matched shots (see
      match_shots_to_release), shots labelled open, shots labelled any other level, shots
      with a shotQuality. The AUC uses n_open + n_other, the Spearman n_quality.

    Hoisted out of the cell loop: the release-frame matching and the shooter positions
    (once per game), the labels, and voronoi_disk. Recomputed per cell is only what the
    parameters change: P_off at the shooter and over the 3 ft disk. release_features is not
    called, because its other columns (epc_share over the whole grid, the K = 20 Monte Carlo
    p_off_std) are not part of the objective and dominate its cost; the two columns that ARE
    used come from the same functions with the same arguments, so a cell here and
    release_features at the same ControlParams agree bit for bit. This is also why calibrate
    takes no grid or value surface: nothing in the objective depends on either (P_off is
    evaluated at the shooter's exact tracked point, and the disk is a fixed 1 ft lattice),
    so the sweep is exactly invariant to the grid resolution, verified at 1 ft and 2 ft.

    `slope` is refused as a grid dimension (ValueError): both terms of the objective are
    rank statistics and P_off = sigmoid(slope * score) is monotone in the score, so every
    cell of a slope sweep would tie exactly (D1 amendment, measured in P1.1).
    """
    if not frames_by_game:
        raise ValueError("frames_by_game is empty")
    matched = [
        match_shots_to_release(frames_by_game[game_id], shots_by_game[game_id])
        for game_id in frames_by_game
    ]
    shots = pd.concat([m[0] for m in matched], ignore_index=True)
    label = open_label(shots["contestLevel"])
    quality = shots["shotQuality"].to_numpy(dtype=float)
    voronoi_disk = np.concatenate([_voronoi_disk_mean(r, xy) for _, r, xy in matched])
    closest = np.concatenate([
        np.linalg.norm(r.xy[:, N_SIDE:].astype(np.float64) - xy[:, None, :], axis=-1).min(axis=1)
        for _, r, xy in matched
    ])
    references = {
        "voronoi_disk_auc": rank_auc(voronoi_disk, label),
        "closest_def_dist_auc": rank_auc(closest, label),
        "closest_def_dist_spearman": spearman(closest, quality),
    }
    denominators = {
        "n_shots": len(shots),
        "n_open": int(np.sum(label == 1.0)),
        "n_other": int(np.sum(label == 0.0)),
        "n_quality": int(np.sum(~np.isnan(quality))),
    }

    rows = []
    for cell in _param_cells(param_grid):
        params = ControlParams(**cell)
        shooter = np.concatenate([control_at_points(r, xy, params) for _, r, xy in matched])
        disk = np.concatenate([_disk_mean(r, xy, params) for _, r, xy in matched])
        auc = rank_auc(shooter, label)
        rho = spearman(shooter, quality)
        rows.append({
            **cell,
            "slope": params.slope,
            "auc_open": auc,
            "spearman_quality": rho,
            "objective": auc + rho,
            "p_off_disk_auc": rank_auc(disk, label),
            **references,
            **denominators,
        })
    return pd.DataFrame(rows)


def best_cell(table: pd.DataFrame) -> pd.Series:
    """The row of a calibrate table with the highest objective; NaN objectives are ignored."""
    if table["objective"].isna().all():
        raise ValueError("every cell has a NaN objective: nothing to choose")
    return table.loc[table["objective"].idxmax()]


def edge_dimensions(
    cell: Mapping[str, float], param_grid: Mapping[str, Sequence[float]]
) -> list[str]:
    """Grid dimensions on which `cell` sits at the smallest or largest value swept.

    The plan (P1.4) requires the optimum to be interior in every dimension: on an edge, the
    grid did not bracket it and must be extended on that side and rerun. A dimension with a
    single value is not being calibrated and is never reported as an edge.
    """
    return [
        name
        for name, values in param_grid.items()
        if len(values) > 1 and cell[name] in (min(values), max(values))
    ]


# ------------------------------------------------------------ partial_spearman_table

# P1.5's fourth pre-registered criterion, "the field contributes information that the
# distance to the closest defender does not have": partial Spearman of shotQuality with a
# model feature, controlling for the provider's own closestDefDist (the column
# release_features copies through, as pre-registered; not the recomputed closest_def_dist).
# The three predictors are the model's shooter-level features; epc_share is the only one that
# carries location. The second control set adds `three`, because shotQuality is mostly
# location, so surviving it is the stronger claim.
PARTIAL_PREDICTORS = ("p_off_shooter", "p_off_disk", "epc_share")
PARTIAL_CONTROLS = (("closestDefDist",), ("closestDefDist", "three"))
PARTIAL_SHUFFLES = 2000  # P1.5: p < 0.01 by permutation with 2,000 shuffles


def partial_spearman_table(
    features: pd.DataFrame,
    predictors: Sequence[str] = PARTIAL_PREDICTORS,
    controls: Sequence[Sequence[str]] = PARTIAL_CONTROLS,
    n: int = PARTIAL_SHUFFLES,
    seed: int = 0,
) -> pd.DataFrame:
    """Does a model feature add information about shotQuality beyond the controls?

    One row per (predictor, control set) over `features`, a release_features table (any
    number of games concatenated): `rho` = partial_spearman(shotQuality, predictor,
    controls), `p_value` = its one-sided permutation p-value (permutation_pvalue, `n`
    shuffles of the predictor while shotQuality and the controls stay paired, with a fresh
    numpy.random.default_rng(seed) per row so every row is reproducible on its own), and
    `n_shots`, the rows where none of the three is NaN. `controls` is joined with "+".

    `rho` is NaN, not 0, when the predictor is an exact function of the controls (its rank
    residual is constant): report it as undefined, never as "no information".
    """
    y = features["shotQuality"].to_numpy(dtype=float)
    rows = []
    for predictor in predictors:
        x = features[predictor].to_numpy(dtype=float)
        for control in controls:
            z = features[list(control)].to_numpy(dtype=float)
            valid = ~(np.isnan(y) | np.isnan(x) | np.isnan(z).any(axis=1))
            rows.append({
                "predictor": predictor,
                "controls": "+".join(control),
                "n_shots": int(valid.sum()),
                "rho": partial_spearman(y, x, z),
                "p_value": permutation_pvalue(
                    functools.partial(partial_spearman, y, z=z), groups=(x,), n=n,
                    rng=np.random.default_rng(seed),
                ),
            })
    return pd.DataFrame(rows)
