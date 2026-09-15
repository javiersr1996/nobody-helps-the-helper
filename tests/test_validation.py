"""Tests for scbasket.validation: rank_auc, spearman, partial_spearman, permutation_pvalue,
release_features.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import REAL_DATASET_ROOT, requires_real_dataset

from scbasket.control import ControlParams, control_at_points, control_field
from scbasket.court import ZONES, make_grid
from scbasket.epc import epc_share
from scbasket.frames import GameFrames, get_or_build
from scbasket.io import Dataset
from scbasket.validation import (
    partial_spearman,
    permutation_pvalue,
    rank_auc,
    release_features,
    spearman,
)
from scbasket.value import ValueSurface, league_zone_values, surface_from_zones

CACHE_DIR = REAL_DATASET_ROOT.parents[1] / "interim"
OFF_IDS = np.array([5001, 5002, 5003, 5004, 5005], dtype=np.int32)
DEF_IDS = np.array([6001, 6002, 6003, 6004, 6005], dtype=np.int32)


def _brute_force_auc(score: np.ndarray, label: np.ndarray) -> float:
    """Independent O(n^2) reference: count pairs, crediting ties as one half."""
    positive = score[label == 1]
    negative = score[label == 0]
    total = 0.0
    for p in positive:
        for ng in negative:
            if p > ng:
                total += 1.0
            elif p == ng:
                total += 0.5
    return total / (positive.shape[0] * negative.shape[0])


# --------------------------------------------------------------------------- rank_auc


def test_rank_auc_perfect_separation_is_one():
    score = np.array([1.0, 2.0, 3.0, 10.0, 11.0, 12.0])
    label = np.array([0, 0, 0, 1, 1, 1])
    assert rank_auc(score, label) == 1.0


def test_rank_auc_random_labels_is_about_half():
    rng = np.random.default_rng(42)
    score = rng.standard_normal(2000)
    label = rng.integers(0, 2, size=2000)
    result = rank_auc(score, label)
    assert abs(result - 0.5) <= 0.05


def test_rank_auc_with_ties_matches_brute_force_pair_counting():
    score = np.array([1.0, 2.0, 2.0, 2.0, 3.0, 3.0, 4.0, 5.0, 5.0, 6.0])
    label = np.array([0, 0, 1, 0, 1, 0, 1, 1, 0, 1])
    assert rank_auc(score, label) == pytest.approx(_brute_force_auc(score, label))


def test_rank_auc_drops_nan_pairs_before_ranking():
    score = np.array([1.0, 2.0, np.nan, 4.0, 5.0, 6.0])
    label = np.array([0, 0, 1, 1, 1, 1])
    cleaned_score = np.array([1.0, 2.0, 4.0, 5.0, 6.0])
    cleaned_label = np.array([0, 0, 1, 1, 1])
    assert rank_auc(score, label) == rank_auc(cleaned_score, cleaned_label)


def test_rank_auc_returns_nan_with_fewer_than_three_valid_pairs():
    assert np.isnan(rank_auc(np.array([1.0, 2.0]), np.array([0, 1])))


def test_rank_auc_returns_nan_when_label_has_a_single_class():
    score = np.array([1.0, 2.0, 3.0, 4.0])
    label = np.array([0, 0, 0, 0])
    assert np.isnan(rank_auc(score, label))


def test_rank_auc_constant_score_is_one_half():
    score = np.full(10, 3.0)
    label = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
    assert rank_auc(score, label) == pytest.approx(0.5)


# --------------------------------------------------------------------------- spearman


def _pandas_spearman(a: np.ndarray, b: np.ndarray) -> float:
    """pandas' own Spearman correlation, without going through scipy.

    `Series.corr(method="spearman")` dispatches to `scipy.stats.spearmanr`,
    and scipy is not a dependency of this repo (nor installed in this venv).
    Spearman correlation is, by definition, the Pearson correlation of the
    ranks, so `Series.rank()` (pandas' own midrank implementation) followed
    by the default Pearson `.corr()` is the exact same computation scipy
    would do, and is still a genuine cross-check: both the ranking and the
    correlation are pandas' independent implementation, not ours.
    """
    return pd.Series(a).rank().corr(pd.Series(b).rank())


def test_spearman_matches_pandas_without_ties():
    rng = np.random.default_rng(1)
    a = rng.standard_normal(200)
    b = rng.standard_normal(200)
    expected = _pandas_spearman(a, b)
    assert spearman(a, b) == pytest.approx(expected, abs=1e-12)


def test_spearman_matches_pandas_with_ties():
    rng = np.random.default_rng(2)
    a = rng.integers(0, 5, size=300).astype(float)  # heavy ties
    b = rng.integers(0, 8, size=300).astype(float)
    expected = _pandas_spearman(a, b)
    assert spearman(a, b) == pytest.approx(expected, abs=1e-12)


def test_spearman_perfect_monotonic_relationship_is_one():
    a = np.linspace(-5.0, 5.0, 50)
    b = a**3  # strictly increasing, non-linear -- Spearman is rank-only
    assert spearman(a, b) == pytest.approx(1.0)


def test_spearman_drops_nan_pairs():
    a = np.array([1.0, np.nan, 3.0, 4.0, 5.0])
    b = np.array([2.0, 3.0, np.nan, 8.0, 10.0])
    cleaned_a = np.array([1.0, 4.0, 5.0])
    cleaned_b = np.array([2.0, 8.0, 10.0])
    assert spearman(a, b) == spearman(cleaned_a, cleaned_b)


def test_spearman_returns_nan_with_fewer_than_three_valid_pairs():
    assert np.isnan(spearman(np.array([1.0, 2.0]), np.array([3.0, 4.0])))


def test_spearman_returns_nan_for_constant_input():
    a = np.full(10, 1.0)
    b = np.arange(10.0)
    assert np.isnan(spearman(a, b))


# --------------------------------------------------------------------- partial_spearman


def test_partial_spearman_near_zero_when_y_depends_only_on_z():
    rng = np.random.default_rng(3)
    z = rng.standard_normal(3000)
    y = 2 * z + 0.1 * rng.standard_normal(3000)  # y ~ z, plus a little noise
    x = rng.standard_normal(3000)  # independent of both y and z
    result = partial_spearman(y, x, z)
    assert abs(result) <= 0.05


def test_partial_spearman_positive_when_x_adds_information_beyond_z():
    rng = np.random.default_rng(4)
    z = rng.standard_normal(3000)
    x = rng.standard_normal(3000)
    y = 2 * z + 3 * x + 0.1 * rng.standard_normal(3000)
    result = partial_spearman(y, x, z)
    assert result > 0.3


def test_partial_spearman_with_a_constant_z_reduces_to_plain_spearman():
    rng = np.random.default_rng(5)
    y = rng.standard_normal(100)
    x = rng.standard_normal(100)
    z = np.full(100, 7.0)
    assert partial_spearman(y, x, z) == pytest.approx(spearman(y, x), abs=1e-9)


def test_partial_spearman_drops_nan_rows():
    y = np.array([1.0, 2.0, np.nan, 4.0, 5.0])
    x = np.array([2.0, 3.0, 4.0, np.nan, 6.0])
    z = np.array([1.0, 1.0, 1.0, 1.0, 2.0])
    cleaned_y = np.array([1.0, 2.0, 5.0])
    cleaned_x = np.array([2.0, 3.0, 6.0])
    cleaned_z = np.array([1.0, 1.0, 2.0])
    assert partial_spearman(y, x, z) == partial_spearman(cleaned_y, cleaned_x, cleaned_z)


def test_partial_spearman_returns_nan_with_fewer_than_three_valid_rows():
    y = np.array([1.0, 2.0])
    x = np.array([3.0, 4.0])
    z = np.array([5.0, 6.0])
    assert np.isnan(partial_spearman(y, x, z))


def test_partial_spearman_returns_nan_for_constant_y():
    y = np.full(20, 1.0)
    x = np.arange(20.0)
    z = np.arange(20.0)[::-1]
    assert np.isnan(partial_spearman(y, x, z))


# ------------------------------------------------------------------- permutation_pvalue


def test_permutation_pvalue_reproducible_with_a_fixed_seed():
    values = np.array([0.1, 0.4, 0.2, 0.9, 1.1, 0.3, 0.6, 1.4, 0.8, 1.0, 0.15, 0.95])
    labels = np.array([0, 0, 0, 1, 1, 0, 0, 1, 1, 1, 0, 1])

    def stat(w):
        return values[w == 1].mean() - values[w == 0].mean()

    p1 = permutation_pvalue(stat, groups=(labels,), n=500, rng=np.random.default_rng(7))
    p2 = permutation_pvalue(stat, groups=(labels,), n=500, rng=np.random.default_rng(7))
    assert p1 == p2


def test_permutation_pvalue_small_for_an_obvious_effect():
    rng = np.random.default_rng(0)
    values = np.concatenate([rng.normal(0.0, 1.0, 300), rng.normal(3.0, 1.0, 300)])
    labels = np.concatenate([np.zeros(300), np.ones(300)])

    def stat(w):
        return values[w == 1].mean() - values[w == 0].mean()

    p = permutation_pvalue(stat, groups=(labels,), n=2000, rng=np.random.default_rng(1))
    assert p < 0.01


def test_permutation_pvalue_large_for_pure_noise():
    rng = np.random.default_rng(2)
    values = rng.normal(0.0, 1.0, 600)  # same distribution regardless of the label
    labels = np.concatenate([np.zeros(300), np.ones(300)])

    def stat(w):
        return values[w == 1].mean() - values[w == 0].mean()

    p = permutation_pvalue(stat, groups=(labels,), n=2000, rng=np.random.default_rng(3))
    assert p > 0.1


def test_permutation_pvalue_precomputed_mode_matches_manual_calculation():
    null = np.array([1.0, 2.0, 3.0, 4.0, 10.0, 6.0, 7.0])
    observed = 5.0
    result = permutation_pvalue(observed, null)
    expected = (np.sum(null >= observed) + 1) / (null.shape[0] + 1)
    assert result == pytest.approx(expected)


def test_permutation_pvalue_raises_on_mismatched_group_lengths():
    with pytest.raises(ValueError):
        permutation_pvalue(lambda a, b: 0.0, groups=(np.zeros(5), np.zeros(6)))


def test_permutation_pvalue_returns_nan_with_fewer_than_three_points():
    p = permutation_pvalue(lambda a: a.mean(), groups=(np.array([1.0, 2.0]),))
    assert np.isnan(p)


def test_permutation_pvalue_precomputed_mode_returns_nan_with_a_short_null():
    assert np.isnan(permutation_pvalue(5.0, np.array([1.0, 2.0])))


def test_permutation_pvalue_returns_nan_when_observed_statistic_is_nan():
    assert np.isnan(permutation_pvalue(float("nan"), np.array([1.0, 2.0, 3.0])))


# --------------------------------------------------------------------------- release_features


def _release_frames(xy, ball=None, shot_clock=24.0) -> GameFrames:
    """A minimal n-row GameFrames for release_features tests: fixed 5+5 ids, no velocity.

    frame_idx is 10, 20, 30, ... so tests can target a specific row by startFrame.
    """
    xy = np.asarray(xy, dtype=np.float32)
    n = len(xy)
    ball = np.zeros((n, 3), np.float32) if ball is None else np.asarray(ball, dtype=np.float32)
    return GameFrames(
        game_id=900001,
        frame_idx=np.arange(10, 10 * (n + 1), 10, dtype=np.int32),
        wall_clock=np.arange(n, dtype=np.int64) * 40,
        shot_clock=np.broadcast_to(np.asarray(shot_clock, np.float32), (n,)).copy(),
        period=np.ones(n, np.int8),
        possession_idx=np.zeros(n, np.int32),
        chance_idx=np.zeros(n, np.int32),
        off_ids=np.tile(OFF_IDS, (n, 1)),
        def_ids=np.tile(DEF_IDS, (n, 1)),
        xy=xy,
        v=np.zeros_like(xy),
        pred_error=np.ones((n, 10), np.float32),
        detected=np.ones((n, 10), bool),
        ball=ball,
        ball_holder=np.zeros(n, np.int8),
        matchup=np.full((n, 5), -1, np.int8),
    )


def _shot_row(start_frame, shooter_id, **overrides) -> dict:
    """A shots.itertuples()-shaped row with sane defaults, one field overridable at a time."""
    row = {
        "startFrame": start_frame,
        "shooterId": shooter_id,
        "contestLevel": "open",
        "shotQuality": 50.0,
        "closestDefDist": 5.0,
        "outcome": True,
        "three": False,
        "shotClock": 15.0,
        "region": "ra",
    }
    row.update(overrides)
    return row


def _flat_surface(grid, value: float = 1.0) -> ValueSurface:
    """A ValueSurface worth `value` everywhere (no zero-value zones, no smoothing)."""
    return surface_from_zones(grid, dict.fromkeys(ZONES, value), smooth_ft=0.0)


def test_release_features_happy_path_matches_and_computes_every_column():
    xy = np.zeros((1, 10, 2), dtype=np.float32)
    xy[0, :5] = [(-30.0, 5.0), (-25.0, -3.0), (-10.0, 10.0), (-10.0, -10.0), (0.0, 0.0)]
    xy[0, 5:] = [(-33.0, 5.0), (-40.0, 20.0), (-40.0, -20.0), (10.0, 10.0), (10.0, -10.0)]
    frames = _release_frames(xy, ball=np.array([[-30.0, 5.0, 4.0]], dtype=np.float32))
    shots = pd.DataFrame([_shot_row(10, OFF_IDS[0])])
    grid = make_grid(4.0)
    params = ControlParams()
    surface = _flat_surface(grid)

    out = release_features(frames, shots, grid, params, surface)

    required = {
        "game_id", "p_off_shooter", "p_off_disk", "epc_share", "voronoi_shooter",
        "voronoi_disk",
        "closest_def_dist", "contestLevel", "shotQuality", "closestDefDist", "outcome",
        "three", "shotClock", "region", "startFrame",
    }
    assert required <= set(out.columns)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["game_id"] == frames.game_id
    assert row["startFrame"] == 10

    shooter_xy = xy[0, 0].astype(np.float64)
    assert row["p_off_shooter"] == control_at_points(frames, shooter_xy[None], params)[0]
    assert row["epc_share"] == epc_share(control_field(frames, grid, params), surface)[0]
    # The shooter is at distance 0 from themself, so they are always their own nearest
    # player: the Voronoi baseline at the shooter's own position is not a coincidence.
    assert row["voronoi_shooter"] == 1.0
    # ... which is why the P1.5 baseline samples the disk instead: with a defender 3 ft
    # away the disk is genuinely contested, so voronoi_disk can discriminate and
    # voronoi_shooter cannot.
    assert 0.0 < row["voronoi_disk"] < 1.0
    expected_dist = np.linalg.norm(xy[0, 5:].astype(np.float64) - shooter_xy, axis=1).min()
    assert row["closest_def_dist"] == pytest.approx(expected_dist)
    assert row["closest_def_dist"] == pytest.approx(3.0)  # hand-placed nearest defender
    assert 0.0 < row["p_off_disk"] < 1.0


def test_release_features_drops_a_shot_whose_release_frame_is_missing_from_the_cache():
    xy = np.zeros((2, 10, 2), dtype=np.float32)
    xy[:, 0] = (-30.0, 5.0)
    xy[:, 5] = (-35.0, 5.0)
    frames = _release_frames(xy)  # frame_idx 10, 20 -- 999 is never in the cache
    shots = pd.DataFrame([
        _shot_row(10, OFF_IDS[0], shotQuality=10.0),
        _shot_row(999, OFF_IDS[0], shotQuality=90.0),
    ])
    grid = make_grid(4.0)

    out = release_features(frames, shots, grid, ControlParams(), _flat_surface(grid))

    assert len(out) == 1  # dropped, not padded to 2 rows with a NaN
    assert out["startFrame"].iloc[0] == 10
    assert out["shotQuality"].iloc[0] == 10.0
    assert not out.isna().any().any()


def test_release_features_disk_mean_equals_point_value_on_a_uniform_field():
    """Every defender mirrors its attacker's position exactly, so the influence surplus
    cancels term by term and P_off(p) == 0.5 for ANY p (the same construction
    test_control.py's stock-synthetic-game test uses for a field that is uniform
    everywhere, not just locally). p_off_disk, the mean over several such points, must
    then equal p_off_shooter exactly, not just approximately.
    """
    xy = np.zeros((1, 10, 2), dtype=np.float32)
    xy[0, :5] = [(-30.0, 5.0), (-20.0, -5.0), (-15.0, 8.0), (-8.0, -8.0), (-2.0, 2.0)]
    xy[0, 5:] = xy[0, :5]
    frames = _release_frames(xy, ball=np.array([[-15.0, 0.0, 4.0]], dtype=np.float32))
    shots = pd.DataFrame([_shot_row(10, OFF_IDS[0])])
    grid = make_grid(4.0)

    out = release_features(frames, shots, grid, ControlParams(), _flat_surface(grid))

    assert out["p_off_shooter"].iloc[0] == pytest.approx(0.5, abs=1e-12)
    assert out["p_off_disk"].iloc[0] == pytest.approx(0.5, abs=1e-12)
    assert out["p_off_disk"].iloc[0] == out["p_off_shooter"].iloc[0]


@pytest.mark.data
@requires_real_dataset
def test_release_features_matched_yield_on_the_10_published_games():
    """Matched-shot yield against the D12-filtered cache; see release_features' docstring
    for why this differs from the 1,414 the raw-stream script
    (scripts/shot_contest_uncertainty.py) reaches: 93 of the 99 unmatched shots sit in a
    chance with usable == False and 6 have a null shotClock, frames the control model
    cannot evaluate at all, not a failure of the matching itself (0 shooter-not-found
    cases across all 10 games).
    """
    dataset = Dataset(REAL_DATASET_ROOT)
    grid = make_grid(2.0)
    params = ControlParams()
    surface = surface_from_zones(grid, league_zone_values(dataset.aggregates("shots")))

    total_shots = 0
    total_matched = 0
    for game_id in dataset.game_ids:
        frames = get_or_build(dataset, game_id, CACHE_DIR)
        shots = dataset.events(game_id)["shots"]
        total_shots += len(shots)
        total_matched += len(release_features(frames, shots, grid, params, surface))

    print(f"\n{total_matched} of {total_shots} shots matched to a release frame")
    assert total_shots == 1459
    assert total_matched == 1360
