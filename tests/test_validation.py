"""Tests for scbasket.validation: rank_auc, spearman, partial_spearman, permutation_pvalue,
release_features, calibrate, release_metrics.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from conftest import REAL_DATASET_ROOT, requires_real_dataset

from scbasket.control import (
    ControlParams,
    control_at_points,
    control_at_points_with_uncertainty,
    control_field,
)
from scbasket.court import ZONES, make_grid
from scbasket.epc import epc_share
from scbasket.frames import GameFrames, get_or_build
from scbasket.io import Dataset
from scbasket.validation import (
    CALIBRATION_GAMES,
    CONTEST_LEVELS,
    RELEASE_COLUMNS,
    RELEASE_MODELS,
    RELEASE_PARTIAL_CONTROLS,
    RELEASE_PARTIAL_PREDICTORS,
    RELEASE_THRESHOLDS,
    VALIDATION_GAMES,
    best_cell,
    calibrate,
    edge_dimensions,
    hoop_distance,
    level_medians,
    monotone_pairs,
    partial_spearman,
    partial_spearman_table,
    permutation_pvalue,
    rank_auc,
    release_features,
    release_metrics,
    spearman,
)
from scbasket.value import ValueSurface, league_zone_values, surface_from_zones

CACHE_DIR = REAL_DATASET_ROOT.parents[1] / "interim"
CONTROL_PARAMS_JSON = REAL_DATASET_ROOT.parents[2] / "reports" / "control_params.json"
VALIDATION_RELEASE_CSV = REAL_DATASET_ROOT.parents[2] / "reports" / "validation_release.csv"
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


def test_partial_spearman_with_one_column_z_matches_the_one_dimensional_path():
    rng = np.random.default_rng(6)
    y, x, z = rng.standard_normal((3, 200))
    assert partial_spearman(y, x, z[:, None]) == pytest.approx(partial_spearman(y, x, z), abs=1e-12)


def test_partial_spearman_with_two_controls_removes_what_both_explain():
    rng = np.random.default_rng(8)
    z1 = rng.standard_normal(3000)
    z2 = rng.standard_normal(3000)
    x = rng.standard_normal(3000)
    y_from_controls = 2 * z1 - 3 * z2 + 0.1 * rng.standard_normal(3000)
    y_with_x = y_from_controls + 3 * x
    controls = np.column_stack([z1, z2])

    assert abs(partial_spearman(y_from_controls, x, controls)) <= 0.05
    assert partial_spearman(y_with_x, x, controls) > 0.3
    # Controlling for z1 alone leaves z2's share in the residual: the joint fit is not
    # the one-control fit, which is the whole point of accepting several controls.
    joint = partial_spearman(y_with_x, x, controls)
    assert joint != partial_spearman(y_with_x, x, z1)


def test_partial_spearman_ignores_a_constant_or_duplicated_control_column():
    rng = np.random.default_rng(9)
    z = rng.standard_normal(300)
    x = rng.standard_normal(300)
    y = 2 * z + x + 0.1 * rng.standard_normal(300)
    single = partial_spearman(y, x, z)

    assert partial_spearman(y, x, np.column_stack([z, np.full(300, 4.0)])) == pytest.approx(
        single, abs=1e-9
    )
    assert partial_spearman(y, x, np.column_stack([z, z])) == pytest.approx(single, abs=1e-9)


def test_partial_spearman_drops_rows_with_a_nan_in_any_control_column():
    rng = np.random.default_rng(10)
    y, x, z1, z2 = rng.standard_normal((4, 50))
    z = np.column_stack([z1, z2])
    z_holed = z.copy()
    z_holed[3, 1] = np.nan
    z_holed[7, 0] = np.nan
    keep = np.ones(50, dtype=bool)
    keep[[3, 7]] = False

    assert partial_spearman(y, x, z_holed) == partial_spearman(y[keep], x[keep], z[keep])


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


def _release_frames(xy, ball=None, shot_clock=24.0, pred_error=None) -> GameFrames:
    """A minimal n-row GameFrames for release_features tests: fixed 5+5 ids, no velocity.

    frame_idx is 10, 20, 30, ... so tests can target a specific row by startFrame.
    pred_error defaults to 1.0 ft everywhere; pass an override for the p_off_std tests.
    """
    xy = np.asarray(xy, dtype=np.float32)
    n = len(xy)
    ball = np.zeros((n, 3), np.float32) if ball is None else np.asarray(ball, dtype=np.float32)
    if pred_error is None:
        pred_error = np.ones((n, 10), np.float32)
    else:
        pred_error = np.broadcast_to(np.asarray(pred_error, np.float32), (n, 10)).copy()
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
        pred_error=pred_error,
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
        "location": [-35.0, 0.0],  # the real field: a [x, y] list, null for a few shots
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
        "voronoi_disk", "p_off_std",
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


def _p_off_std_fixture(pred_error) -> tuple[GameFrames, pd.DataFrame]:
    """Two shots with distinct, hand-placed geometry, for the p_off_std (D8/P1.2) tests."""
    xy = np.zeros((2, 10, 2), dtype=np.float32)
    xy[:, :5] = [(-30.0, 5.0), (-25.0, -3.0), (-10.0, 10.0), (-10.0, -10.0), (0.0, 0.0)]
    xy[:, 5:] = [(-33.0, 5.0), (-40.0, 20.0), (-40.0, -20.0), (10.0, 10.0), (10.0, -10.0)]
    xy[1, :5, 0] -= 5.0  # second shot: same shape, shifted, so it is a distinct release frame
    frames = _release_frames(xy, pred_error=pred_error)
    shots = pd.DataFrame([_shot_row(10, OFF_IDS[0]), _shot_row(20, OFF_IDS[0])])
    return frames, shots


def test_release_features_p_off_std_is_zero_when_pred_error_is_zero():
    """D8/P1.2 acceptance: predError = 0 gives p_off_std 0, to float64 machine precision.
    See test_control.py's control_with_uncertainty zero-predError test for why the
    tolerance is float64 epsilon rather than a literal ``== 0.0``: numpy's std of several
    bit-identical draws is not guaranteed to round to exactly 0.0.
    """
    frames, shots = _p_off_std_fixture(pred_error=0.0)
    grid = make_grid(4.0)

    out = release_features(frames, shots, grid, ControlParams(), _flat_surface(grid))

    np.testing.assert_allclose(out["p_off_std"].to_numpy(), 0.0, atol=1e-9)


def test_release_features_p_off_std_is_bounded_and_matches_a_direct_monte_carlo_call():
    """p_off_std must be a real per-shot number, not a placeholder, and must agree with
    calling control_at_points_with_uncertainty directly on the same matched release frame
    and shooter position (the same computation release_features does internally)."""
    frames, shots = _p_off_std_fixture(pred_error=1.5)
    grid = make_grid(4.0)
    params = ControlParams()

    out = release_features(frames, shots, grid, params, _flat_surface(grid))

    assert (out["p_off_std"] > 0.0).all()
    assert (out["p_off_std"] <= 0.5).all()  # std of a variable bounded in [0, 1]
    shooter_xy = frames.xy[:, 0].astype(np.float64)
    _, expected_std = control_at_points_with_uncertainty(
        frames, shooter_xy, params, samples=20, rng=np.random.default_rng(0)
    )
    np.testing.assert_array_equal(out["p_off_std"].to_numpy(), expected_std)


def test_release_features_p_off_std_is_reproducible_across_calls():
    """release_features takes no rng parameter, so it must be a pure function of its
    arguments: calling it twice on identical inputs gives identical p_off_std."""
    frames, shots = _p_off_std_fixture(pred_error=2.0)
    grid = make_grid(4.0)
    params = ControlParams()

    first = release_features(frames, shots, grid, params, _flat_surface(grid))
    second = release_features(frames, shots, grid, params, _flat_surface(grid))

    np.testing.assert_array_equal(first["p_off_std"].to_numpy(), second["p_off_std"].to_numpy())


def test_hoop_distance_from_location_and_nan_where_it_is_null():
    location = pd.Series([[-40.76, 0.0], [-37.76, 4.0], None, np.nan, [0.0, 0.0]])

    out = hoop_distance(location)

    np.testing.assert_allclose(out[[0, 1, 4]], [0.0, 5.0, 40.76])
    assert np.isnan(out[2]) and np.isnan(out[3])
    assert np.isnan(hoop_distance(pd.Series([None, None]))).all()
    assert hoop_distance(pd.Series([], dtype=object)).shape == (0,)


def test_release_features_hoop_dist_comes_from_the_shot_location():
    xy = np.zeros((2, 10, 2), dtype=np.float32)
    xy[:, 0] = (-30.0, 5.0)
    xy[:, 5] = (-35.0, 5.0)
    frames = _release_frames(xy)
    shots = pd.DataFrame([
        _shot_row(10, OFF_IDS[0], location=[-30.76, 5.0]),
        _shot_row(20, OFF_IDS[0], location=None),
    ])
    grid = make_grid(4.0)

    out = release_features(frames, shots, grid, ControlParams(), _flat_surface(grid))

    assert out["hoop_dist"].iloc[0] == pytest.approx(np.hypot(10.0, 5.0))
    assert np.isnan(out["hoop_dist"].iloc[1])  # a null location keeps the shot, not the control
    assert len(out) == 2


@pytest.mark.data
@requires_real_dataset
def test_release_features_matched_yield_on_the_10_published_games():
    """Matched-shot yield against the D12-filtered cache; see release_features' docstring
    for why this differs from the 1,445 the raw-stream script
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


# --------------------------------------------------------------------------- calibrate

SMALL_GRID = {"r_near": [3.0, 4.0], "r_far": [8.0, 10.0], "t_h": [0.0, 0.3]}


def _calibration_games(seed: int = 11) -> tuple[dict[int, GameFrames], dict[int, pd.DataFrame]]:
    """Two synthetic games (12 and 10 shots) with random geometry, moving players and every
    contest level, keyed by game id the way calibrate expects them."""
    rng = np.random.default_rng(seed)
    frames_by_game: dict[int, GameFrames] = {}
    shots_by_game: dict[int, pd.DataFrame] = {}
    for game_id, n in ((900001, 12), (900002, 10)):
        xy = np.empty((n, 10, 2), dtype=np.float32)
        xy[..., 0] = rng.uniform(-40.0, 0.0, size=(n, 10))
        xy[..., 1] = rng.uniform(-20.0, 20.0, size=(n, 10))
        frames = _release_frames(xy, ball=np.column_stack([xy[:, 0], np.full(n, 4.0)]))
        v = rng.normal(0.0, 5.0, size=(n, 10, 2)).astype(np.float32)
        frames_by_game[game_id] = replace(frames, game_id=game_id, v=v)
        shots_by_game[game_id] = pd.DataFrame([
            _shot_row(
                10 * (i + 1), OFF_IDS[i % 5], contestLevel=CONTEST_LEVELS[i % 5],
                shotQuality=float(rng.uniform(0.0, 100.0)),
            )
            for i in range(n)
        ])
    return frames_by_game, shots_by_game


def test_calibrate_one_row_per_cell_in_product_order_with_slope_fixed():
    frames_by_game, shots_by_game = _calibration_games()

    table = calibrate(frames_by_game, shots_by_game, SMALL_GRID)

    assert len(table) == 8
    cells = list(zip(table["r_near"], table["r_far"], table["t_h"], strict=True))
    assert cells == list(itertools.product(*SMALL_GRID.values()))
    assert (table["slope"] == 1.0).all()
    assert (table["n_shots"] == 22).all()
    assert (table["n_open"] == 5).all() and (table["n_other"] == 17).all()
    assert (table["n_quality"] == 22).all()
    np.testing.assert_array_equal(
        table["objective"], table["auc_open"] + table["spearman_quality"]
    )
    for reference in ("voronoi_disk_auc", "closest_def_dist_auc", "closest_def_dist_spearman"):
        assert table[reference].nunique() == 1, reference  # parameter-free references
    assert table["auc_open"].nunique() > 1  # the geometry actually moves the objective


def test_calibrate_cell_agrees_with_release_features_bit_for_bit():
    """The objective is graded on the same functions release_features uses, so a cell and
    release_features at the same ControlParams must agree exactly, not approximately."""
    frames_by_game, shots_by_game = _calibration_games()
    cell = {"r_near": 4.0, "r_far": 10.0, "t_h": 0.3}
    grid = make_grid(4.0)
    features = pd.concat(
        [
            release_features(frames_by_game[g], shots_by_game[g], grid, ControlParams(**cell),
                             _flat_surface(grid))
            for g in frames_by_game
        ],
        ignore_index=True,
    )
    label = (features["contestLevel"] == "open").to_numpy(dtype=float)

    row = calibrate(frames_by_game, shots_by_game, {k: [v] for k, v in cell.items()}).iloc[0]

    assert row["auc_open"] == rank_auc(features["p_off_shooter"], label)
    assert row["spearman_quality"] == spearman(features["p_off_shooter"], features["shotQuality"])
    assert row["p_off_disk_auc"] == rank_auc(features["p_off_disk"], label)
    assert row["voronoi_disk_auc"] == rank_auc(features["voronoi_disk"], label)
    assert row["closest_def_dist_auc"] == rank_auc(features["closest_def_dist"], label)
    assert row["closest_def_dist_spearman"] == spearman(
        features["closest_def_dist"], features["shotQuality"]
    )


def test_calibrate_t_h_zero_is_a_velocity_ablation():
    """At t_h = 0 the model ignores velocity entirely: the row must equal the one computed
    on the same frames with every velocity zeroed, and differ from the t_h = 0.3 row."""
    frames_by_game, shots_by_game = _calibration_games()
    still = {g: replace(f, v=np.zeros_like(f.v)) for g, f in frames_by_game.items()}
    grid = {"r_near": [4.0], "r_far": [10.0], "t_h": [0.0, 0.3]}

    moving = calibrate(frames_by_game, shots_by_game, grid)
    frozen = calibrate(still, shots_by_game, grid)

    metrics = ["auc_open", "spearman_quality", "p_off_disk_auc"]
    np.testing.assert_array_equal(moving.loc[0, metrics], frozen.loc[0, metrics])
    assert moving.loc[1, "objective"] != frozen.loc[1, "objective"]


def test_calibrate_drops_unlabelled_shots_from_the_metrics_but_not_from_n_shots():
    frames_by_game, shots_by_game = _calibration_games()
    shots = shots_by_game[900001]
    shots.loc[0, "contestLevel"] = None
    shots.loc[1, "shotQuality"] = np.nan
    shots.loc[2, "contestLevel"] = None
    shots.loc[2, "shotQuality"] = np.nan

    row = calibrate(frames_by_game, shots_by_game, {"r_near": [4.0]}).iloc[0]

    assert row["n_shots"] == 22
    assert row["n_open"] + row["n_other"] == 20
    assert row["n_quality"] == 20
    assert np.isfinite(row["objective"])
    assert row["r_near"] == 4.0 and row["slope"] == 1.0


def test_calibrate_refuses_slope_as_a_dimension():
    frames_by_game, shots_by_game = _calibration_games()
    with pytest.raises(ValueError, match="monotone"):
        calibrate(frames_by_game, shots_by_game, {"r_near": [4.0], "slope": [0.5, 1.0, 2.0]})


def test_best_cell_ignores_nan_and_edge_dimensions_skips_single_value_dimensions():
    grid = {"r_near": [3.0, 4.0, 5.0], "r_far": [10.0], "t_h": [0.0, 0.3, 0.6]}
    table = pd.DataFrame({
        "r_near": [3.0, 4.0, 4.0, 5.0],
        "r_far": [10.0, 10.0, 10.0, 10.0],
        "t_h": [0.3, 0.3, 0.6, 0.0],
        "objective": [1.2, np.nan, 1.1, 0.9],
    })

    best = best_cell(table)

    assert best["r_near"] == 3.0 and best["objective"] == 1.2
    assert edge_dimensions(best, grid) == ["r_near"]
    assert edge_dimensions(table.iloc[2], grid) == ["t_h"]
    assert edge_dimensions({"r_near": 4.0, "r_far": 10.0, "t_h": 0.3}, grid) == []
    assert edge_dimensions(table.iloc[3], grid) == ["r_near", "t_h"]
    with pytest.raises(ValueError, match="NaN"):
        best_cell(table.assign(objective=np.nan))


def test_partial_spearman_table_one_row_per_predictor_and_control_set():
    frames_by_game, shots_by_game = _calibration_games()
    grid = make_grid(4.0)
    features = pd.concat(
        [release_features(frames_by_game[g], shots_by_game[g], grid, ControlParams(),
                          _flat_surface(grid)) for g in frames_by_game],
        ignore_index=True,
    )
    features.loc[0, "closestDefDist"] = np.nan  # one row must drop from every control set

    table = partial_spearman_table(features, n=200, seed=3)
    again = partial_spearman_table(features, n=200, seed=3)

    assert list(table.columns) == ["predictor", "controls", "n_shots", "rho", "p_value"]
    assert list(zip(table["predictor"], table["controls"], strict=True)) == [
        ("p_off_shooter", "closestDefDist"), ("p_off_shooter", "closestDefDist+three"),
        ("p_off_disk", "closestDefDist"), ("p_off_disk", "closestDefDist+three"),
        ("epc_share", "closestDefDist"), ("epc_share", "closestDefDist+three"),
    ]
    assert (table["n_shots"] == 21).all()
    assert ((table["p_value"] > 0.0) & (table["p_value"] <= 1.0)).all()
    pd.testing.assert_frame_equal(table, again)  # seeded per row: reproducible
    expected = partial_spearman(
        features["shotQuality"], features["p_off_disk"],
        features[["closestDefDist", "three"]].to_numpy(dtype=float),
    )
    assert table.loc[3, "rho"] == expected


@pytest.mark.data
@requires_real_dataset
@pytest.mark.skipif(not CONTROL_PARAMS_JSON.exists(), reason="run scripts/calibrate_control.py")
def test_frozen_params_reproduce_the_recorded_objective_on_the_calibration_games():
    """reports/control_params.json is the pre-registration (D11): the frozen parameters must
    give back the recorded objective on the five calibration games, and those five must be
    the oldest by date. Only matches.json (dates) and the calibration games are read."""
    dataset = Dataset(REAL_DATASET_ROOT)
    assert dataset.game_ids[:5] == list(CALIBRATION_GAMES)
    frozen = json.loads(CONTROL_PARAMS_JSON.read_text(encoding="utf-8"))
    assert frozen["params"]["slope"] == 1.0 and frozen["slope_calibrated"] is False
    assert frozen["calibration_games"] == list(CALIBRATION_GAMES)

    frames_by_game = {g: get_or_build(dataset, g, CACHE_DIR) for g in CALIBRATION_GAMES}
    shots_by_game = {g: dataset.events(g)["shots"] for g in CALIBRATION_GAMES}
    params = frozen["params"]
    row = calibrate(
        frames_by_game, shots_by_game, {k: [params[k]] for k in ("r_near", "r_far", "t_h")}
    ).iloc[0]

    print(f"\nfrozen {params}: objective {row['objective']:.4f} on {row['n_shots']} shots")
    assert row["objective"] == pytest.approx(frozen["objective"], abs=1e-9)
    assert row["auc_open"] == pytest.approx(frozen["auc_open"], abs=1e-9)
    assert row["spearman_quality"] == pytest.approx(frozen["spearman_quality"], abs=1e-9)
    assert {k: int(row[k]) for k in frozen["denominators"]} == frozen["denominators"]

    # The recorded partial Spearman rows (P1.5's fourth criterion, calibration games only)
    # come back from release_features at the frozen cell plus the seeded permutation test.
    recorded = frozen["partial_spearman_shot_quality"]
    grid = make_grid(recorded["grid_ft"])
    surface = surface_from_zones(grid, league_zone_values(dataset.aggregates("shots")))
    control = ControlParams(**params)
    features = pd.concat(
        [release_features(frames_by_game[g], shots_by_game[g], grid, control, surface)
         for g in CALIBRATION_GAMES],
        ignore_index=True,
    )
    table = partial_spearman_table(features)
    for r, rec in zip(table.itertuples(), recorded["rows"], strict=True):
        assert (r.predictor, r.controls, r.n_shots) == (
            rec["predictor"], rec["controls"], rec["n_shots"]
        )
        assert r.rho == pytest.approx(rec["rho"], abs=1e-9)
        assert r.p_value == pytest.approx(rec["p_value"], abs=1e-9)


# --------------------------------------------------------------------------- release_metrics


def _metrics_features(quality: list[float] | None = None) -> pd.DataFrame:
    """Ten hand-placed shots, two per contest level, shaped like a release_features table.

    p_off_shooter separates open from the rest perfectly and its medians fall strictly from
    open to blocked, so criteria 1 and 3 hold by construction; shotQuality defaults to the
    reverse order of p_off_shooter, so criterion 4a fails by construction.
    """
    shooter = [0.9, 0.85, 0.7, 0.75, 0.6, 0.55, 0.4, 0.45, 0.2, 0.25]
    return pd.DataFrame({
        "contestLevel": [level for level in CONTEST_LEVELS for _ in range(2)],
        "p_off_shooter": shooter,
        "p_off_disk": [v - 0.05 for v in shooter],
        "epc_share": [0.5, 0.45, 0.4, 0.42, 0.38, 0.36, 0.3, 0.33, 0.25, 0.28],
        "voronoi_disk": [0.6, 0.7, 0.5, 0.6, 0.5, 0.4, 0.5, 0.4, 0.3, 0.5],
        "closestDefDist": [8.0, 7.0, 4.0, 4.5, 3.0, 3.5, 2.0, 2.5, 1.0, 1.5],
        "closest_def_dist": [8.01, 7.01, 4.01, 4.51, 3.01, 3.51, 2.01, 2.51, 1.01, 1.51],
        "shotQuality": [10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0]
        if quality is None else quality,
        "three": [False, True] * 5,
        "hoop_dist": [25.0, 10.0, 22.0, 8.0, 15.0, 5.0, 12.0, 4.0, 3.0, 6.0],
    })


def test_validation_games_are_the_other_five():
    assert len(VALIDATION_GAMES) == 5 and len(set(VALIDATION_GAMES)) == 5
    assert set(VALIDATION_GAMES).isdisjoint(CALIBRATION_GAMES)
    assert len(set(VALIDATION_GAMES) | set(CALIBRATION_GAMES)) == 10


def test_monotone_pairs_counts_strict_decreases_and_never_a_nan():
    assert monotone_pairs([5.0, 4.0, 3.0, 2.0, 1.0]) == 4
    assert monotone_pairs([5.0, 5.0, 3.0, 2.0, 1.0]) == 3
    assert monotone_pairs([1.0, 2.0, 3.0, 4.0, 5.0]) == 0
    assert monotone_pairs([5.0, 4.0, np.nan, 2.0, 1.0]) == 2
    assert monotone_pairs([np.nan] * 5) == 0


def test_level_medians_follows_contest_level_order_and_counts_missing_levels():
    features = pd.DataFrame({
        "contestLevel": ["plus", "open", "open", None, "light"],
        "p_off_shooter": [0.2, 0.9, 0.7, 0.5, 0.6],
        "closestDefDist": [1.0, 5.0, np.nan, 2.0, 3.0],
    })

    table = level_medians(features, columns=("p_off_shooter", "closestDefDist"))

    assert list(table.index) == list(CONTEST_LEVELS)
    assert list(table.columns) == ["n_shots", "p_off_shooter", "closestDefDist"]
    assert table["n_shots"].tolist() == [2, 1, 0, 1, 0]  # the unlabelled shot counts nowhere
    assert table.loc["open", "p_off_shooter"] == pytest.approx(0.8)
    assert table.loc["open", "closestDefDist"] == 5.0  # the NaN value is skipped, not counted
    assert np.isnan(table.loc["average", "p_off_shooter"])


def test_release_metrics_rows_reproduce_the_underlying_statistics():
    features = _metrics_features()

    table = release_metrics(features, n=200, seed=3)

    assert list(table.columns) == list(RELEASE_COLUMNS)
    assert (table["surface"] == "league").all()
    per_feature = 2 + len(CONTEST_LEVELS) + 1  # auc, spearman, five medians, monotone
    n_partial = len(RELEASE_PARTIAL_PREDICTORS) * len(RELEASE_PARTIAL_CONTROLS)
    assert len(table) == per_feature * len(RELEASE_MODELS) + 2 + n_partial
    assert dict(zip(table["feature"], table["model"], strict=True)) == RELEASE_MODELS

    label = (features["contestLevel"] == "open").to_numpy(dtype=float)
    medians = level_medians(features)

    def row(metric, feature, controls=""):
        at = (
            (table["metric"] == metric) & (table["feature"] == feature)
            & (table["controls"] == controls)
        )
        assert at.sum() == 1, (metric, feature, controls)
        return table[at].iloc[0]

    for feature in RELEASE_MODELS:
        score = features[feature].to_numpy(dtype=float)
        assert row("auc_open", feature)["value"] == rank_auc(score, label)
        assert row("auc_open", feature)["n_shots"] == 10
        assert row("spearman_quality", feature)["value"] == spearman(
            score, features["shotQuality"]
        )
        for level in CONTEST_LEVELS:
            assert row(f"median_{level}", feature)["value"] == medians.loc[level, feature]
            assert row(f"median_{level}", feature)["n_shots"] == 2
        assert row("monotone_pairs", feature)["value"] == monotone_pairs(
            medians[feature].to_numpy()
        )
    for feature in ("p_off_shooter", "p_off_disk"):
        assert row("auc_margin_vs_voronoi_disk", feature)["value"] == pytest.approx(
            row("auc_open", feature)["value"] - row("auc_open", "voronoi_disk")["value"]
        )
    for predictor in RELEASE_PARTIAL_PREDICTORS:
        for controls in RELEASE_PARTIAL_CONTROLS:
            partial = row("partial_spearman_quality", predictor, "+".join(controls))
            assert partial["value"] == partial_spearman(
                features["shotQuality"], features[predictor],
                features[list(controls)].to_numpy(dtype=float),
            )
            assert 0.0 < partial["p_value"] <= 1.0
            assert partial["n_shots"] == 10
    assert table.loc[table["controls"] == "", "p_value"].isna().all()


def test_release_metrics_grades_exactly_the_five_pre_registered_criteria():
    table = release_metrics(_metrics_features(), n=200, seed=3)
    graded = table[table["criterion"] != ""]

    assert len(graded) == 5
    assert graded["passed"].map(type).eq(bool).all()
    assert table.loc[table["criterion"] == "", "passed"].isna().all()
    by_metric = graded.set_index("metric")
    assert list(by_metric.index) == [
        "auc_open", "spearman_quality", "monotone_pairs", "auc_margin_vs_voronoi_disk",
        "partial_spearman_quality",
    ]
    assert (by_metric["feature"] == ["p_off_shooter", "p_off_shooter", "p_off_shooter",
                                     "p_off_disk", "p_off_shooter"]).all()
    assert by_metric.loc["partial_spearman_quality", "controls"] == "closestDefDist"
    # By construction: open separates perfectly and the medians fall strictly ...
    assert by_metric.loc["auc_open", "value"] == 1.0
    assert by_metric.loc["auc_open", "passed"] is True
    assert by_metric.loc["monotone_pairs", "value"] == RELEASE_THRESHOLDS["monotone_pairs"]
    assert by_metric.loc["monotone_pairs", "passed"] is True
    # ... while shotQuality runs the other way, so 4a and 4b fail.
    assert by_metric.loc["spearman_quality", "value"] < 0
    assert by_metric.loc["spearman_quality", "passed"] is False
    assert by_metric.loc["partial_spearman_quality", "passed"] is False
    margin = by_metric.loc["auc_margin_vs_voronoi_disk"]
    assert margin["passed"] is (bool(margin["value"] >= RELEASE_THRESHOLDS["auc_margin"]))
    partial = by_metric.loc["partial_spearman_quality"]
    assert partial["passed"] is bool(
        partial["value"] > 0 and partial["p_value"] < RELEASE_THRESHOLDS["partial_p_value"]
    )


def test_release_metrics_passes_4a_when_quality_follows_the_field():
    features = _metrics_features(quality=[100.0 * v for v in _metrics_features()["p_off_shooter"]])

    table = release_metrics(features, n=200, seed=3)
    table = table[table["controls"] == ""].set_index(["metric", "feature"])

    assert table.loc[("spearman_quality", "p_off_shooter"), "value"] == pytest.approx(1.0)
    assert table.loc[("spearman_quality", "p_off_shooter"), "passed"] is True


def test_release_metrics_fails_the_order_criterion_when_a_level_is_absent():
    features = _metrics_features()
    features = features[features["contestLevel"] != "blocked"].reset_index(drop=True)

    table = release_metrics(features, n=200, seed=3)
    table = table[table["controls"] == ""].set_index(["metric", "feature"]).sort_index()

    assert table.loc[("median_blocked", "p_off_shooter"), "n_shots"] == 0
    assert np.isnan(table.loc[("median_blocked", "p_off_shooter"), "value"])
    assert table.loc[("monotone_pairs", "p_off_shooter"), "value"] == 3
    assert table.loc[("monotone_pairs", "p_off_shooter"), "passed"] is False


def test_release_metrics_survives_a_csv_round_trip(tmp_path):
    table = release_metrics(_metrics_features(), n=200, seed=3)
    path = tmp_path / "validation_release.csv"
    table.to_csv(path, index=False)

    back = pd.read_csv(path)

    assert list(back.columns) == list(RELEASE_COLUMNS)
    assert back["controls"].fillna("").tolist() == table["controls"].tolist()
    assert back["criterion"].fillna("").tolist() == table["criterion"].tolist()
    assert back["passed"].map(lambda v: None if pd.isna(v) else bool(v)).tolist() == \
        table["passed"].tolist()
    np.testing.assert_allclose(back["value"], table["value"], equal_nan=True)
    np.testing.assert_allclose(back["p_value"], table["p_value"], equal_nan=True)


@pytest.mark.data
@requires_real_dataset
@pytest.mark.skipif(not CONTROL_PARAMS_JSON.exists(), reason="run scripts/calibrate_control.py")
@pytest.mark.skipif(not VALIDATION_RELEASE_CSV.exists(), reason="run scripts/validate_release.py")
def test_validation_release_csv_reproduces_from_the_frozen_params_on_the_held_out_games():
    """reports/validation_release.csv is P1.5's deliverable: it must come back, row for row,
    from the frozen parameters applied to the five held-out games (the newest by date, D11).
    The denominators follow from the established ones: 1,459 shot events across the 10
    games with 740 on the calibration five, and 1,360 matched to the D12 cache with 689
    there. The verdicts are printed, never asserted: pass or fail, they are the finding."""
    dataset = Dataset(REAL_DATASET_ROOT)
    assert dataset.game_ids[5:] == list(VALIDATION_GAMES)
    assert set(VALIDATION_GAMES).isdisjoint(CALIBRATION_GAMES)
    frozen = json.loads(CONTROL_PARAMS_JSON.read_text(encoding="utf-8"))
    assert frozen["calibration_games"] == list(CALIBRATION_GAMES)
    params = ControlParams(**frozen["params"])
    grid = make_grid(1.0)
    surface = surface_from_zones(grid, league_zone_values(dataset.aggregates("shots")))

    n_events = 0
    features = []
    for game_id in VALIDATION_GAMES:
        shots = dataset.events(game_id)["shots"]
        n_events += len(shots)
        features.append(release_features(
            get_or_build(dataset, game_id, CACHE_DIR), shots, grid, params, surface
        ))
    features = pd.concat(features, ignore_index=True)
    assert n_events == 1459 - 740
    assert len(features) == 1360 - 689

    table = release_metrics(features)
    written = pd.read_csv(VALIDATION_RELEASE_CSV)
    assert len(written) == len(table)
    for column in ("surface", "metric", "model", "feature"):
        assert written[column].tolist() == table[column].tolist(), column
    assert written["controls"].fillna("").tolist() == table["controls"].tolist()
    assert written["criterion"].fillna("").tolist() == table["criterion"].tolist()
    assert written["n_shots"].tolist() == table["n_shots"].tolist()
    np.testing.assert_allclose(written["value"], table["value"], atol=1e-9, equal_nan=True)
    np.testing.assert_allclose(written["p_value"], table["p_value"], atol=1e-9, equal_nan=True)
    assert written["passed"].map(lambda v: None if pd.isna(v) else bool(v)).tolist() == \
        table["passed"].tolist()
    graded = table[table["criterion"] != ""]
    print("\n" + "\n".join(
        f"{r.criterion}: {r.value:.4f} -> {'PASS' if r.passed else 'FAIL'}"
        for r in graded.itertuples()
    ))
