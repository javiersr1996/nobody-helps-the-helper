"""Tests for scbasket.control: influence ellipses, control field, Voronoi baseline, counterfactuals.

Geometric properties are checked on GameFrames built here with hand-placed or
random positions (``_make_frames`` / ``_random_frames``): the stock synthetic
game of conftest places every home player on top of an away player, so it only
serves to prove the module runs end to end on real GameFrames.
"""

from __future__ import annotations

import time
from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest
from conftest import GAME_ID, REAL_DATASET_ROOT, requires_real_dataset

from scbasket.control import (
    REMOVED_XY_FT,
    ControlParams,
    control_at_points,
    control_field,
    influence,
    remove_players,
    voronoi_field,
)
from scbasket.court import FIBA, make_grid
from scbasket.frames import GameFrames, build_game_frames, get_or_build, subsample
from scbasket.io import Dataset

CACHE_DIR = REAL_DATASET_ROOT.parents[1] / "interim"
GRID = make_grid(2.0)  # 2 ft keeps the unit tests fast; the data test uses the 1 ft grid
BALL_Z_FT = 4.0
SWAP = np.r_[5:10, 0:5]


def _make_frames(xy, v=None, ball=None, shot_clock=24.0) -> GameFrames:
    """A GameFrames with the given geometry, placeholder metadata and the cached dtypes.

    The ball defaults to attacker 0's position; shot_clock is a scalar or (N,).
    """
    xy = np.asarray(xy, dtype=np.float32)
    n = len(xy)
    v = np.zeros_like(xy) if v is None else np.asarray(v, dtype=np.float32)
    if ball is None:
        ball = np.concatenate([xy[:, 0], np.full((n, 1), BALL_Z_FT, np.float32)], axis=1)
    return GameFrames(
        game_id=GAME_ID,
        frame_idx=np.arange(n, dtype=np.int32),
        wall_clock=np.arange(n, dtype=np.int64) * 40,
        shot_clock=np.broadcast_to(np.asarray(shot_clock, np.float32), (n,)).copy(),
        period=np.ones(n, np.int8),
        possession_idx=np.zeros(n, np.int32),
        chance_idx=np.zeros(n, np.int32),
        off_ids=np.tile(np.arange(5001, 5006, dtype=np.int32), (n, 1)),
        def_ids=np.tile(np.arange(6001, 6006, dtype=np.int32), (n, 1)),
        xy=xy,
        v=v,
        pred_error=np.ones((n, 10), np.float32),
        detected=np.ones((n, 10), bool),
        ball=np.asarray(ball, dtype=np.float32),
        ball_holder=np.zeros(n, np.int8),
        matchup=np.full((n, 5), -1, np.int8),
    )


def _random_frames(rng, n: int, speed: float = 0.0, shot_clock=24.0) -> GameFrames:
    """n frames with 10 players uniform over the offensive half court and the ball on attacker 0."""
    xy = np.empty((n, 10, 2))
    xy[..., 0] = rng.uniform(-FIBA.half_length_ft, 0.0, (n, 10))
    xy[..., 1] = rng.uniform(-FIBA.half_width_ft, FIBA.half_width_ft, (n, 10))
    v = rng.normal(0.0, speed, (n, 10, 2)) if speed else np.zeros((n, 10, 2))
    return _make_frames(xy, v, shot_clock=shot_clock)


def _swap_teams(frames: GameFrames) -> GameFrames:
    """The same frames with the defense in the attacker slots and vice versa."""
    return replace(
        frames,
        xy=frames.xy[:, SWAP],
        v=frames.v[:, SWAP],
        pred_error=frames.pred_error[:, SWAP],
        detected=frames.detected[:, SWAP],
        off_ids=frames.def_ids,
        def_ids=frames.off_ids,
    )


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


# --------------------------------------------------------------------------- params


def test_params_defaults_are_the_plan_initial_values_and_frozen():
    params = ControlParams()

    assert (params.r_near, params.r_far, params.d_far) == (4.0, 10.0, 30.0)
    assert (params.v_max, params.t_h, params.slope) == (25.0, 0.3, 1.0)
    with pytest.raises(FrozenInstanceError):
        params.slope = 2.0  # type: ignore[misc]


@pytest.mark.parametrize(
    "bad", [{"r_near": 0.0}, {"r_far": -1.0}, {"d_far": 0.0}, {"v_max": 0.0}, {"t_h": -0.1}]
)
def test_params_reject_non_positive_lengths_and_negative_horizons(bad):
    with pytest.raises(ValueError):
        ControlParams(**bad)


# --------------------------------------------------------------------------- influence


def test_influence_is_one_at_the_projected_centre_and_decays_away_from_it():
    params = ControlParams()
    xy = np.zeros((1, 10, 2))
    v = np.zeros((1, 10, 2))
    xy[0, 0] = (-30.0, 5.0)  # at rest
    xy[0, 1] = (-20.0, -5.0)
    v[0, 1] = (10.0, 0.0)  # projected 10 * 0.3 = 3 ft along +x
    ball = np.array([[0.0, 0.0, BALL_Z_FT]])
    clock = np.array([24.0])
    points = np.array([[-30.0, 5.0], [-17.0, -5.0], [-30.0, 7.0], [-30.0, 9.0]])

    infl = influence(xy, v, ball, clock, points, params)

    assert infl.shape == (1, 10, 4)
    assert np.all(infl > 0) and np.all(infl <= 1)
    assert infl[0, 0, 0] == pytest.approx(1.0)
    assert infl[0, 1, 1] == pytest.approx(1.0)
    assert infl[0, 0, 0] > infl[0, 0, 2] > infl[0, 0, 3]
    # Per-frame points (B, G, 2) give the same numbers as the shared (G, 2) form.
    per_frame = influence(xy, v, ball, clock, points[None], params)
    np.testing.assert_array_equal(per_frame, infl)


def test_influence_radius_grows_linearly_with_distance_to_the_ball_up_to_d_far():
    """At rest the standard deviation is r / 2 (F&B convention), r linear in the ball distance."""
    params = ControlParams(r_near=4.0, r_far=10.0, d_far=30.0)
    xy = np.zeros((1, 10, 2))
    xy[0, :4, 0] = (0.0, 15.0, 30.0, 60.0)  # ball at the origin: 0, 15, 30 and 60 ft away
    ball = np.array([[0.0, 0.0]])
    offset = 3.0
    points = xy[0] + (0.0, offset)  # each player evaluated 3 ft beside itself

    infl = influence(xy, np.zeros_like(xy), ball, np.array([24.0]), points, params)

    radius = np.array([4.0, 7.0, 10.0, 10.0])
    expected = np.exp(-0.5 * offset**2 / (radius / 2) ** 2)
    np.testing.assert_allclose(np.diagonal(infl[0])[:4], expected, rtol=1e-12)


def test_influence_is_elongated_along_the_velocity_and_gated_by_the_shot_clock():
    """Half of v_max gives an elongation of 0.25; the clock scales projection and elongation."""
    params = ControlParams(r_near=10.0, r_far=10.0, v_max=25.0, t_h=0.3)
    xy = np.zeros((1, 10, 2))
    v = np.zeros((1, 10, 2))
    xy[0, 0] = (-20.0, 0.0)
    v[0, 0] = (0.0, 12.5)  # +y at half of v_max
    ball = np.array([[0.0, 0.0]])

    def at(clock: float, points):
        return influence(xy, v, ball, np.array([clock]), np.asarray(points), params)[0, 0]

    # Full horizon: centre (-20, 3.75), sigma 6.25 along y and 3.75 across.
    ahead, side = at(24.0, [[-20.0, 3.75 + 4.0], [-16.0, 3.75]])
    assert ahead == pytest.approx(np.exp(-0.5 * 16 / 6.25**2), rel=1e-12)
    assert side == pytest.approx(np.exp(-0.5 * 16 / 3.75**2), rel=1e-12)
    assert ahead > side
    # Half the horizon: centre (-20, 1.875), elongation 0.125.
    ahead, side = at(0.15, [[-20.0, 1.875 + 4.0], [-16.0, 1.875]])
    assert ahead == pytest.approx(np.exp(-0.5 * 16 / 5.625**2), rel=1e-12)
    assert side == pytest.approx(np.exp(-0.5 * 16 / 4.375**2), rel=1e-12)
    # Expired clock: the centre stays put and the ellipse is a circle of sigma 5.
    ahead, side = at(0.0, [[-20.0, 4.0], [-16.0, 0.0]])
    assert ahead == side == pytest.approx(np.exp(-0.5 * 16 / 25.0), rel=1e-12)


# --------------------------------------------------------------------------- control_field


def test_control_field_runs_on_the_synthetic_game_where_the_teams_coincide(synthetic_root):
    frames = build_game_frames(Dataset(synthetic_root), GAME_ID)
    field = control_field(frames, GRID, ControlParams())

    assert field.shape == (len(frames), len(GRID.centers))
    assert field.dtype == np.float64
    # In this fixture every home player shares position and velocity with one away player.
    np.testing.assert_array_equal(frames.xy[:, :5], frames.xy[:, 5:])
    np.testing.assert_array_equal(field, 0.5)


def test_control_field_stays_in_the_unit_interval_and_is_symmetric_under_a_team_swap():
    rng = np.random.default_rng(1)
    frames = _random_frames(rng, 40, speed=6.0, shot_clock=rng.uniform(0.0, 24.0, 40))
    params = ControlParams(slope=2.0)

    field = control_field(frames, GRID, params)
    swapped = control_field(_swap_teams(frames), GRID, params)

    assert np.all(field >= 0.0) and np.all(field <= 1.0)
    assert field.min() < 0.3 and field.max() > 0.7  # the field is not flat
    assert np.abs(field + swapped - 1.0).max() < 1e-9


def test_control_field_is_bit_identical_for_any_batch_size():
    rng = np.random.default_rng(2)
    frames = _random_frames(rng, 70, speed=6.0)  # not a multiple of the batch size
    params = ControlParams()

    one = control_field(frames, GRID, params, batch=1)
    sixty_four = control_field(frames, GRID, params, batch=64)
    everything = control_field(frames, GRID, params, batch=1000)

    assert np.array_equal(one, sixty_four)
    assert np.array_equal(everything, sixty_four)
    with pytest.raises(ValueError):
        control_field(frames, GRID, params, batch=0)


def test_lone_attacker_owns_their_own_position():
    """A lone attacker's position is the maximum of the field, at sigmoid(slope * 1).

    The plan's criterion reads "P > 0.99 at their position". Under D1 the influence
    of one player is at most 1, so sigmoid(slope) is the ceiling of any single
    player: 0.731 at the default slope of 1, above 0.99 only from slope ln(99) = 4.6
    on. The quantity the criterion meant, that nobody contests the location and
    the model gives it entirely to the attacker, is asserted through that ceiling
    with the default params, and the literal 0.99 with slope 5.
    """
    position = np.array([[-30.0, 5.0]])
    xy = np.zeros((1, 10, 2))
    xy[0, 0] = position[0]
    alone = remove_players(_make_frames(xy), np.arange(10)[None] != 0)

    for slope in (1.0, 5.0):
        params = ControlParams(slope=slope)
        at_position = control_at_points(alone, position, params)[0]
        field = control_field(alone, GRID, params)[0]
        assert at_position == pytest.approx(_sigmoid(slope), abs=1e-12)
        assert field.max() <= at_position
        assert field.min() >= 0.5  # with nobody defending, no cell leans to the defense
    assert control_at_points(alone, position, ControlParams(slope=5.0))[0] > 0.99


def test_small_radii_reduce_the_field_to_voronoi():
    """Shrinking the radii turns the field into the nearest-player partition.

    The plan's criterion reads "with radii -> 0 it matches Voronoi in >= 99% of
    cells". The quantity it tests is the sign of the influence surplus, and that
    sign is only visible in P where the surplus exceeds the float64 resolution of
    the sigmoid at 0.5 (2.2e-16): with a radius r the Gaussians are below it
    wherever every player is farther than 8.5 * r / 2, and P is exactly 0.5 there
    (42% of the cells at r = 2 ft on random frames). So the agreement is measured
    on the cells where P != 0.5, the undecided share is reported, and the
    mismatch rate must not rise as the radii shrink. Measured on the seed below:
    99.86%, 100.0% and 100.0% agreement at 4, 2 and 1 ft.

    With a uniform radius the dominant player of every cell (largest influence)
    is exactly the nearest player: that identity holds on every cell.
    """
    rng = np.random.default_rng(3)
    frames = _random_frames(rng, 30)
    voronoi = voronoi_field(frames, GRID)
    assert set(np.unique(voronoi)) == {0.0, 1.0}  # continuous positions: no ties

    mismatch_rates = []
    for r in (4.0, 2.0, 1.0):
        params = ControlParams(r_near=r, r_far=r, t_h=0.0)
        field = control_field(frames, GRID, params)
        decided = field != 0.5
        agree = ((field > 0.5) == (voronoi == 1.0)) & decided
        rate = 1.0 - agree[decided].mean()
        mismatch_rates.append(rate)
        print(f"r={r} ft: agreement {1 - rate:.2%} on {decided.mean():.1%} decided cells")
        assert rate <= 0.01, f"r={r}: {rate:.2%} of decided cells disagree with Voronoi"
    assert mismatch_rates == sorted(mismatch_rates, reverse=True)

    params = ControlParams(r_near=4.0, r_far=4.0, t_h=0.0)
    infl = influence(frames.xy, frames.v, frames.ball, frames.shot_clock, GRID.centers, params)
    dist = np.linalg.norm(GRID.centers[None, None] - frames.xy[:, :, None].astype(float), axis=-1)
    np.testing.assert_array_equal(infl.argmax(axis=1), dist.argmin(axis=1))


def test_expired_shot_clock_makes_the_field_purely_positional():
    rng = np.random.default_rng(4)
    frames = _random_frames(rng, 20, speed=8.0, shot_clock=0.0)
    still = replace(frames, v=np.zeros_like(frames.v))
    params = ControlParams()

    np.testing.assert_array_equal(
        control_field(frames, GRID, params), control_field(still, GRID, params)
    )
    running = replace(frames, shot_clock=np.full(len(frames), 24.0, np.float32))
    running_still = replace(still, shot_clock=running.shot_clock)
    assert np.abs(
        control_field(running, GRID, params) - control_field(running_still, GRID, params)
    ).max() > 0.05


# --------------------------------------------------------------------------- control_at_points


def test_control_at_points_matches_the_field_at_cell_centres():
    rng = np.random.default_rng(5)
    n = 25
    frames = _random_frames(rng, n, speed=5.0, shot_clock=rng.uniform(0.0, 24.0, n))
    cells = rng.integers(0, len(GRID.centers), n)
    params = ControlParams()

    at_points = control_at_points(frames, GRID.centers[cells], params)
    field = control_field(frames, GRID, params)

    assert at_points.shape == (n,)
    np.testing.assert_array_equal(at_points, field[np.arange(n), cells])


def test_control_at_points_is_half_beyond_everyone_and_accepts_empty_input():
    rng = np.random.default_rng(6)
    frames = _random_frames(rng, 5)
    params = ControlParams()

    far = np.full((5, 2), 1e4)
    np.testing.assert_array_equal(control_at_points(frames, far, params), 0.5)
    empty = frames.take(np.empty(0, np.int64))
    assert control_at_points(empty, np.empty((0, 2)), params).shape == (0,)
    assert control_field(empty, GRID, params).shape == (0, len(GRID.centers))


# --------------------------------------------------------------------------- voronoi_field


def test_voronoi_matches_brute_force_nearest_player_for_any_batch_size():
    rng = np.random.default_rng(7)
    frames = _random_frames(rng, 10, speed=5.0)  # velocity must play no role

    voronoi = voronoi_field(frames, GRID)

    brute = np.empty_like(voronoi)
    for row in range(len(frames)):
        for cell, center in enumerate(GRID.centers):
            nearest = np.linalg.norm(frames.xy[row].astype(float) - center, axis=1).argmin()
            brute[row, cell] = 1.0 if nearest < 5 else 0.0
    np.testing.assert_array_equal(voronoi, brute)
    np.testing.assert_array_equal(voronoi_field(frames, GRID, batch=3), voronoi)
    with pytest.raises(ValueError):
        voronoi_field(frames, GRID, batch=0)


def test_voronoi_is_symmetric_under_a_team_swap_and_splits_exact_ties():
    rng = np.random.default_rng(8)
    frames = _random_frames(rng, 10)

    swapped = voronoi_field(_swap_teams(frames), GRID)
    np.testing.assert_array_equal(voronoi_field(frames, GRID) + swapped, 1.0)
    everyone_at_the_origin = _make_frames(np.zeros((2, 10, 2)))
    np.testing.assert_array_equal(voronoi_field(everyone_at_the_origin, GRID), 0.5)


# --------------------------------------------------------------------------- remove_players


def test_remove_players_parks_the_masked_players_and_touches_nothing_else():
    rng = np.random.default_rng(9)
    frames = _random_frames(rng, 6, speed=5.0)
    before = replace(frames, xy=frames.xy.copy(), v=frames.v.copy())
    mask = rng.random((6, 10)) < 0.3
    mask[0] = False

    out = remove_players(frames, mask)

    assert isinstance(out, GameFrames) and out is not frames and len(out) == 6
    assert out.xy.dtype == np.float32 and out.v.dtype == np.float32
    assert np.all(out.xy[mask] == REMOVED_XY_FT) and np.all(out.v[mask] == 0.0)
    np.testing.assert_array_equal(out.xy[~mask], frames.xy[~mask])
    np.testing.assert_array_equal(out.v[~mask], frames.v[~mask])
    for name in ("ball", "ball_holder", "matchup", "off_ids", "def_ids", "shot_clock", "detected"):
        np.testing.assert_array_equal(getattr(out, name), getattr(frames, name), err_msg=name)
    np.testing.assert_array_equal(frames.xy, before.xy)  # the input is not mutated
    np.testing.assert_array_equal(frames.v, before.v)
    with pytest.raises(ValueError):
        remove_players(frames, mask[:, :5])


def test_removing_a_defender_never_lowers_control_and_removing_an_attacker_never_raises_it():
    """The monotonicity denied_k >= 0 (P2.2) relies on: exact zero influence of a parked player."""
    rng = np.random.default_rng(10)
    n = 15
    frames = _random_frames(rng, n, speed=5.0, shot_clock=rng.uniform(0.0, 24.0, n))
    params = ControlParams()
    field = control_field(frames, GRID, params)
    voronoi = voronoi_field(frames, GRID)

    for slot in range(10):
        mask = np.zeros((n, 10), bool)
        mask[:, slot] = True
        without = remove_players(frames, mask)
        parked = influence(
            without.xy, without.v, without.ball, without.shot_clock, GRID.centers, params
        )[:, slot]
        assert np.all(parked == 0.0)
        counterfactual = control_field(without, GRID, params)
        if slot < 5:
            assert np.all(counterfactual <= field)
            assert np.all(voronoi_field(without, GRID) <= voronoi)
        else:
            assert np.all(counterfactual >= field)
            assert np.all(voronoi_field(without, GRID) >= voronoi)
        assert np.any(counterfactual != field)
    untouched = remove_players(frames, np.zeros((n, 10), bool))
    np.testing.assert_array_equal(control_field(untouched, GRID, params), field)


# --------------------------------------------------------------------------- real data


@pytest.mark.data
@requires_real_dataset
def test_one_game_at_five_hz_on_a_one_foot_grid_runs_under_two_minutes():
    """P1.1 performance criterion on game 114086; the measured numbers are printed with -s."""
    frames = subsample(get_or_build(Dataset(REAL_DATASET_ROOT), 114086, CACHE_DIR), 5)
    grid = make_grid(1.0)
    params = ControlParams()

    t0 = time.perf_counter()
    field = control_field(frames, grid, params)
    seconds = time.perf_counter() - t0
    voronoi = voronoi_field(frames, grid)
    agreement = ((field > 0.5) == (voronoi == 1.0)).mean()
    print(
        f"\n{len(frames)} frames at 5 Hz x {len(grid.centers)} cells in {seconds:.1f} s; "
        f"mean P_off {field.mean():.3f}, range [{field.min():.3f}, {field.max():.3f}]; "
        f"Voronoi mean {voronoi.mean():.3f}, side agreement {agreement:.1%}"
    )

    assert field.shape == (len(frames), len(grid.centers))
    assert np.all(field >= 0.0) and np.all(field <= 1.0)
    assert seconds <= 120.0, seconds
