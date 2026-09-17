"""Tests for scbasket.forward: the forward-looking label and its field-free baseline (F1b).

The label is the piece F1b rests on, so it is tested against hand-built frames where the
right answer can be counted by hand: which frames a shot labels, that a shot of another
chance labels nothing, and both ends of the horizon window. The regression at the bottom
pins the bug found while building the module (resolving the shot's chance by looking its
own frame up in a 0.2 s subsample drops four shots in five).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import GAME_ID, REAL_DATASET_ROOT, requires_real_dataset

from scbasket.control import ControlParams
from scbasket.court import FIBA, make_grid
from scbasket.forward import (
    CLOCK_FEATURES,
    FPS,
    HORIZON_FRAMES,
    OPEN_LEVEL,
    baseline_features,
    delta_auc,
    field_features,
    fold_auc,
    forward_label,
    frontcourt_mask,
    game_inputs,
    logo_scores,
    nearest_cell,
)
from scbasket.frames import GameFrames, get_or_build, subsample
from scbasket.io import Dataset
from scbasket.value import surface_from_zones

CACHE_DIR = REAL_DATASET_ROOT.parents[1] / "interim"
GRID = make_grid(2.0)  # 2 ft keeps the unit tests fast, as in test_control


def _frames(frame_idx, chance_idx, xy=None, ball_holder=0, shot_clock=24.0) -> GameFrames:
    """GameFrames at the given frame indices and chances, geometry irrelevant unless given."""
    frame_idx = np.asarray(frame_idx, dtype=np.int32)
    n = len(frame_idx)
    if xy is None:
        xy = np.zeros((n, 10, 2), np.float32)
        xy[:, :, 0] = np.arange(10, dtype=np.float32) * 3.0 - 30.0
    xy = np.asarray(xy, dtype=np.float32)
    ball = np.concatenate([xy[:, 0], np.full((n, 1), 4.0, np.float32)], axis=1)
    return GameFrames(
        game_id=GAME_ID,
        frame_idx=frame_idx,
        wall_clock=frame_idx.astype(np.int64) * 40,
        shot_clock=np.broadcast_to(np.asarray(shot_clock, np.float32), (n,)).copy(),
        period=np.ones(n, np.int8),
        possession_idx=np.zeros(n, np.int32),
        chance_idx=np.asarray(chance_idx, dtype=np.int32),
        off_ids=np.tile(np.arange(5001, 5006, dtype=np.int32), (n, 1)),
        def_ids=np.tile(np.arange(6001, 6006, dtype=np.int32), (n, 1)),
        xy=xy,
        v=np.zeros((n, 10, 2), np.float32),
        pred_error=np.ones((n, 10), np.float32),
        detected=np.ones((n, 10), bool),
        ball=ball,
        ball_holder=np.broadcast_to(np.asarray(ball_holder, np.int8), (n,)).copy(),
        matchup=np.full((n, 5), -1, np.int8),
    )


def _chances(ids, frontcourt=None) -> pd.DataFrame:
    frontcourt = [np.nan] * len(ids) if frontcourt is None else frontcourt
    return pd.DataFrame({"id": list(ids), "frontcourtFrame": frontcourt})


def _shots(rows) -> pd.DataFrame:
    """rows: (chanceId, startFrame, contestLevel) tuples."""
    return pd.DataFrame(rows, columns=["chanceId", "startFrame", "contestLevel"])


# ------------------------------------------------------------------------------ the label


def test_label_marks_the_horizon_before_the_shot_and_nothing_after():
    frames = _frames(frame_idx=np.arange(0, 200, 5), chance_idx=np.zeros(40, np.int32))
    label = forward_label(frames, _shots([("c0", 100, "plus")]), _chances(["c0"]))

    marked = frames.frame_idx[label]
    assert marked.min() > 100 - HORIZON_FRAMES
    assert marked.max() == 100
    assert not label[frames.frame_idx > 100].any()


def test_label_window_is_open_at_the_far_end_and_closed_at_the_shot():
    """Exactly (t_shot - horizon, t_shot]: the far edge is out, the shot's own frame is in."""
    shot = 100
    frames = _frames(
        frame_idx=[shot - HORIZON_FRAMES, shot - HORIZON_FRAMES + 1, shot, shot + 1],
        chance_idx=np.zeros(4, np.int32),
    )
    label = forward_label(frames, _shots([("c0", shot, "plus")]), _chances(["c0"]))
    assert label.tolist() == [False, True, True, False]


def test_a_shot_of_another_chance_labels_nothing():
    """A turnover hands the ball over: the next team's shot must not label these frames."""
    frames = _frames(frame_idx=np.arange(0, 100, 5), chance_idx=np.zeros(20, np.int32))
    label = forward_label(frames, _shots([("c1", 60, "plus")]), _chances(["c0", "c1"]))
    assert not label.any()


def test_the_open_level_selects_a_strict_subset():
    frames = _frames(frame_idx=np.arange(0, 200, 5), chance_idx=np.zeros(40, np.int32))
    shots = _shots([("c0", 60, "plus"), ("c0", 160, OPEN_LEVEL)])
    chances = _chances(["c0"])

    every = forward_label(frames, shots, chances)
    only_open = forward_label(frames, shots, chances, level=OPEN_LEVEL)
    assert only_open.sum() < every.sum()
    assert (every | only_open == every).all()


def test_shots_with_a_null_frame_or_an_unknown_chance_are_ignored():
    frames = _frames(frame_idx=np.arange(0, 200, 5), chance_idx=np.zeros(40, np.int32))
    shots = _shots([("c0", np.nan, "plus"), ("ghost", 100, "plus")])
    assert not forward_label(frames, shots, _chances(["c0"])).any()


def test_the_label_does_not_depend_on_the_sampling_grid():
    """The regression: resolving the chance by frame lookup halved the base rate on a subsample."""
    dense = _frames(frame_idx=np.arange(0, 500), chance_idx=np.zeros(500, np.int32))
    shots = _shots([("c0", 120, "plus"), ("c0", 300, "plus"), ("c0", 460, "plus")])
    chances = _chances(["c0"])

    rate_dense = forward_label(dense, shots, chances).mean()
    rate_sparse = forward_label(subsample(dense, 5), shots, chances).mean()
    assert rate_sparse == pytest.approx(rate_dense, abs=0.02)
    assert rate_sparse > 0.3


def test_a_horizon_below_one_frame_is_refused():
    frames = _frames(frame_idx=[0], chance_idx=[0])
    with pytest.raises(ValueError, match="horizon_frames"):
        forward_label(frames, _shots([("c0", 0, "plus")]), _chances(["c0"]), horizon_frames=0)


# ------------------------------------------------------------------------- frontcourt mask


def test_frontcourt_mask_keeps_frames_at_or_after_the_crossing():
    frames = _frames(frame_idx=[10, 19, 20, 21], chance_idx=np.zeros(4, np.int32))
    mask = frontcourt_mask(frames, _chances(["c0"], frontcourt=[20.0]))
    assert mask.tolist() == [False, False, True, True]


def test_a_null_frontcourt_frame_keeps_every_frame_of_that_chance():
    """Dropping them would bias the denominator: the frame cannot be SHOWN to be backcourt."""
    frames = _frames(frame_idx=[0, 5, 10], chance_idx=np.zeros(3, np.int32))
    assert frontcourt_mask(frames, _chances(["c0"], frontcourt=[np.nan])).all()


# ----------------------------------------------------------------------- baseline features


def test_baseline_distances_are_the_hand_computed_ones():
    xy = np.zeros((1, 10, 2), np.float32)
    xy[0, :5, 0] = [0.0, 3.0, 6.0, 9.0, 12.0]  # attackers on a line, 3 ft apart
    xy[0, 5:, 0] = [0.0, 3.0, 6.0, 9.0, 12.0]
    xy[0, 5:, 1] = 4.0  # every defender 4 ft off their man
    frames = _frames(frame_idx=[0], chance_idx=[0], xy=xy)

    row = baseline_features(frames).iloc[0]
    assert row["off_pairwise_min"] == pytest.approx(3.0)
    assert row["off_pairwise_mean"] == pytest.approx(6.0)
    assert row["matchup_dist_mean"] == pytest.approx(4.0)
    assert row["matchup_dist_min"] == pytest.approx(4.0)


def test_the_holder_distance_is_nan_when_no_holder_is_resolved():
    """13% of cached frames have ball_holder < 0; imputing a distance there invents a defender."""
    frames = _frames(frame_idx=[0, 1], chance_idx=[0, 0], ball_holder=-1)
    assert baseline_features(frames)["ball_def_dist"].isna().all()


def test_seconds_into_chance_restart_at_each_chance():
    frames = _frames(frame_idx=[0, 25, 50, 300, 325], chance_idx=[0, 0, 0, 1, 1])
    secs = baseline_features(frames)["secs_into_chance"].to_numpy()
    assert secs.tolist() == [0.0, 1.0, 2.0, 0.0, 1.0]


def test_the_baseline_carries_both_clock_features():
    """F1b criterion 3 is graded against a baseline that already contains the clock."""
    frames = _frames(frame_idx=[0, 5], chance_idx=[0, 0])
    assert set(CLOCK_FEATURES) <= set(baseline_features(frames).columns)


def test_the_baseline_never_touches_the_control_field(monkeypatch):
    """A baseline that called the field would make the delta-AUC criterion meaningless."""
    import scbasket.forward as forward_mod

    def explode(*args, **kwargs):
        raise AssertionError("baseline_features must not compute the control field")

    monkeypatch.setattr(forward_mod, "control_field", explode)
    baseline_features(_frames(frame_idx=[0, 5], chance_idx=[0, 0]))


# -------------------------------------------------------------------------- field features


def test_area_valuable_stays_inside_the_court_it_is_measured_on():
    rng = np.random.default_rng(0)
    xy = np.empty((8, 10, 2))
    xy[..., 0] = rng.uniform(-FIBA.half_length_ft, 0.0, (8, 10))
    xy[..., 1] = rng.uniform(-FIBA.half_width_ft, FIBA.half_width_ft, (8, 10))
    frames = _frames(frame_idx=np.arange(8) * 5, chance_idx=np.zeros(8, np.int32), xy=xy)

    surface = surface_from_zones(GRID, {z: 1.0 for z in set(GRID.zone)})
    area = field_features(frames, GRID, ControlParams(), surface)["area_valuable"].to_numpy()
    court_area = len(GRID.centers) * GRID.cell_ft**2
    assert ((area >= 0) & (area <= court_area)).all()


def test_a_worthless_surface_leaves_no_valuable_area():
    """Lesson 3: check the quantity can vary. With V == 0 everywhere, A_t must be 0, not noise."""
    frames = _frames(frame_idx=[0, 5], chance_idx=[0, 0])
    surface = surface_from_zones(GRID, {z: 0.0 for z in set(GRID.zone)})
    assert (field_features(frames, GRID, ControlParams(), surface)["area_valuable"] == 0).all()


# --------------------------------------------------------------------------- the real data


@pytest.mark.data
@requires_real_dataset
def test_the_label_base_rate_on_a_real_game_is_what_f1b_pre_registered():
    """F1b quotes 0.176 at 0.2 s before the frontcourt filter; pinned against a refactor."""
    dataset = Dataset(REAL_DATASET_ROOT)
    game_id = 114086
    frames = subsample(get_or_build(dataset, game_id, CACHE_DIR), 5)
    events = dataset.events(game_id)

    label = forward_label(frames, events["shots"], events["chances"])
    assert label.mean() == pytest.approx(0.176, abs=0.005)
    assert HORIZON_FRAMES == 3 * FPS


# --------------------------------------------------------------- leave-one-game-out grading

pytest.importorskip("sklearn", reason="F1b grading needs the `forward` extra")


def _two_game_frame(n: int = 400, seed: int = 0):
    """Two games, a signal feature that carries the label and a noise feature that does not."""
    rng = np.random.default_rng(seed)
    game = np.repeat([1, 2], n)
    label = rng.random(2 * n) < 0.3
    signal = label + rng.normal(0.0, 0.5, 2 * n)
    noise = rng.normal(0.0, 1.0, 2 * n)
    return pd.DataFrame({"signal": signal, "noise": noise}), label, game


def test_logo_scores_leave_one_game_out_never_trains_on_the_fold_it_scores():
    """A feature that is the label in game 1 and inverted in game 2 must score BELOW chance."""
    n = 300
    game = np.repeat([1, 2], n)
    label = np.r_[np.arange(n) % 2 == 0, np.arange(n) % 2 == 0]
    flipped = np.r_[label[:n], ~label[n:]].astype(float)
    features = pd.DataFrame({"flipped": flipped})

    auc = fold_auc(logo_scores(features, label, game), label, game)
    assert (auc < 0.5).all(), "a within-fold fit would have scored these near 1.0"


def test_fold_auc_returns_one_row_per_game():
    features, label, game = _two_game_frame()
    auc = fold_auc(logo_scores(features, label, game), label, game)
    assert list(auc.index) == [1, 2]
    assert auc.notna().all()


def test_a_feature_that_carries_the_label_lifts_the_delta():
    features, label, game = _two_game_frame()
    table = delta_auc(features[["noise"]], features[["signal"]], label, game)
    assert (table["delta"] > 0.1).all()
    assert set(table.columns) == {"auc_baseline", "auc_with_field", "delta"}


def test_pure_noise_does_not_lift_the_delta():
    """The falsification: if delta_auc rewarded any extra column, the criterion is worthless."""
    features, label, game = _two_game_frame()
    rng = np.random.default_rng(1)
    junk = pd.DataFrame({"junk": rng.normal(0.0, 1.0, len(label))})
    assert delta_auc(features[["signal"]], junk, label, game)["delta"].mean() < 0.02


@pytest.mark.data
@requires_real_dataset
def test_game_inputs_builds_the_same_rows_for_every_piece():
    dataset = Dataset(REAL_DATASET_ROOT)
    item = game_inputs(dataset, 114086, CACHE_DIR, every=25)
    n = len(item["frames"])
    assert len(item["baseline"]) == n == len(item["label"]) == len(item["label_open"])
    assert item["n_backcourt_dropped"] == item["n_sampled"] - n
    assert item["label_open"].sum() < item["label"].sum()


def test_nearest_cell_agrees_with_the_brute_force_argmin_it_replaced():
    """Including points off the half court, which clamp to the edge cell in both versions."""
    rng = np.random.default_rng(0)
    points = np.column_stack([rng.uniform(-60, 20, 2000), rng.uniform(-35, 35, 2000)])
    for cell_ft in (1.0, 2.0, 3.0):
        grid = make_grid(cell_ft)
        brute = np.linalg.norm(
            points[:, None, :] - grid.centers[None, :, :], axis=-1
        ).argmin(axis=1)
        assert (nearest_cell(grid, points) == brute).all(), f"cell_ft={cell_ft}"
