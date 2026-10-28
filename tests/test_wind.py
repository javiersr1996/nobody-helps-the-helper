"""Tests for scbasket.wind: the defence's own movement on a drive, and who is left.

Published as a DEFINITION, so every convention is pinned against a scene built by hand
where the answer can be read off the coordinates: the helper moves exactly 5 ft toward
where the ball handler ends up, a second defender only sinks with the drive and must score
negative, the ball handler's own matchup can never be the helper however far he moves, and
the drive frame mirrors left- and right-hand drives onto each other.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import GAME_ID, REAL_DATASET_ROOT, requires_real_dataset

from scbasket.court import HOOP_X
from scbasket.frames import N_SIDE, GameFrames, get_or_build
from scbasket.io import Dataset
from scbasket.wind import (
    HELP_FT,
    HORIZON_FRAMES,
    STATUSES,
    drive_endpoints,
    flow_field,
    help_table,
    help_vectors,
)

CACHE_DIR = REAL_DATASET_ROOT.parents[1] / "interim"
FIRST_FRAME = 100
HANDLER_ID = 5001

# The scene, attacking frame (hoop at HOOP_X, 0). Attackers in slots 0-4, defenders 5-9.
# Slot 0 drives toward the hoop and to +y. Defender 5 is his matchup and follows. Defender 6
# starts at (-26, -10) and moves exactly 5 ft toward where the handler ENDS, (-24, 6); he
# guards attacker 1, parked beyond the arc at (-18, -20). Defender 7 only sinks 4 ft toward
# the hoop along x. Defenders 8 and 9 stand still.
_DIR_TO_END = np.array([2.0, 16.0]) / np.hypot(2.0, 16.0)
START = np.array([
    [-16.0, 0.0], [-18.0, -20.0], [-30.0, 15.0], [-10.0, -12.0], [-14.0, 18.0],
    [-19.0, 1.0], [-26.0, -10.0], [-30.0, 12.0], [-12.0, -13.0], [-16.0, 16.0],
])
END = START.copy()
END[0] = [-24.0, 6.0]
END[5] = [-26.0, 6.0]
END[6] = START[6] + 5.0 * _DIR_TO_END
END[7] = [-34.0, 12.0]


def _frames(xy, frame_idx, chance_idx=None, matchup=None) -> GameFrames:
    xy = np.asarray(xy, np.float32)
    n = len(xy)
    frame_idx = np.asarray(frame_idx, np.int32)
    identity = np.broadcast_to(np.arange(N_SIDE, dtype=np.int8), (n, N_SIDE))
    return GameFrames(
        game_id=GAME_ID,
        frame_idx=frame_idx,
        wall_clock=frame_idx.astype(np.int64) * 40,
        shot_clock=np.full(n, 12.0, np.float32),
        period=np.ones(n, np.int8),
        possession_idx=np.zeros(n, np.int32),
        chance_idx=np.zeros(n, np.int32) if chance_idx is None
        else np.asarray(chance_idx, np.int32),
        off_ids=np.broadcast_to(np.arange(5001, 5006, dtype=np.int32), (n, N_SIDE)).copy(),
        def_ids=np.broadcast_to(np.arange(6001, 6006, dtype=np.int32), (n, N_SIDE)).copy(),
        xy=xy,
        v=np.zeros((n, 2 * N_SIDE, 2), np.float32),
        pred_error=np.ones((n, 2 * N_SIDE), np.float32),
        detected=np.ones((n, 2 * N_SIDE), bool),
        ball=np.concatenate([xy[:, 0], np.full((n, 1), 4.0, np.float32)], axis=1),
        ball_holder=np.zeros(n, np.int8),
        matchup=identity.copy() if matchup is None else np.asarray(matchup, np.int8),
    )


def _scene(start=START, end=END, n=HORIZON_FRAMES + 1, mirror_y=False, **kwargs) -> GameFrames:
    """Linear motion from `start` to `end` over `n` frames, first frame FIRST_FRAME."""
    t = np.linspace(0.0, 1.0, n)[:, None, None]
    xy = start[None] + (end - start)[None] * t
    if mirror_y:
        xy = xy * np.array([1.0, -1.0])
    return _frames(xy, np.arange(FIRST_FRAME, FIRST_FRAME + n), **kwargs)


def _drives(start_frame=FIRST_FRAME, handler=HANDLER_ID, drive_id="drive-1") -> pd.DataFrame:
    return pd.DataFrame({
        "id": [drive_id], "gameId": [GAME_ID], "startFrame": [start_frame],
        "ballhandlerId": [handler], "endType": ["kickout"], "category": ["iso"],
        "direction": ["left"],
    })


# ------------------------------------------------------------------ the hand-built scene


def test_helper_is_the_defender_who_moved_toward_the_ball():
    row = help_table(_scene(), _drives()).iloc[0]
    assert row["status"] == "ok"
    assert row["handler_slot"] == 0 and row["handler_def_slot"] == 0
    assert row["flip"] == 1.0
    assert row["helper_def_slot"] == 1 and row["helper_def_id"] == 6002
    assert row["helper_help_move"] == pytest.approx(5.0, abs=1e-3)
    assert row["help_move_max"] == pytest.approx(5.0, abs=1e-3)
    assert row["has_helper"]
    assert row["n_movers_3ft"] == 1
    assert row["helper_origin_x"] == pytest.approx(-26.0) and row["helper_origin_y"] == -10.0
    assert row["helper_start_dist"] == pytest.approx(np.hypot(10.0, 10.0), abs=1e-3)


def test_a_defender_who_only_sinks_with_the_drive_scores_negative():
    vectors = help_vectors(_scene(), _drives())
    assert len(vectors) == 4  # five defenders minus the handler's matchup
    assert set(vectors["def_slot"]) == {1, 2, 3, 4}
    sinking = vectors.set_index("def_slot").loc[2]
    assert sinking["dx"] == pytest.approx(-4.0, abs=1e-3) and sinking["dy"] == pytest.approx(0.0)
    assert sinking["help_move"] < 0
    still = vectors.set_index("def_slot").loc[[3, 4], "help_move"]
    assert (still.abs() < 1e-6).all()


def test_the_handlers_matchup_is_never_the_helper():
    end = END.copy()
    end[5] = END[0] + np.array([0.5, 0.5])  # the matchup lands on top of the handler
    row = help_table(_scene(end=end), _drives()).iloc[0]
    assert row["helper_def_slot"] == 1
    assert row["helper_help_move"] == pytest.approx(5.0, abs=1e-3)


def test_the_man_he_leaves_is_measured_at_both_ends():
    row = help_table(_scene(), _drives()).iloc[0]
    assert row["left_slot"] == 1 and row["left_id"] == 5002
    assert row["left_sep0"] == pytest.approx(np.hypot(8.0, 10.0), abs=1e-3)
    assert row["left_sep1"] == pytest.approx(np.linalg.norm(START[1] - END[6]), abs=1e-3)
    # nearest ANY defender at the horizon is defender 8 at (-12, -13): hypot(6, 7)
    assert row["left_nearest1"] == pytest.approx(np.hypot(6.0, 7.0), abs=1e-3)
    assert row["left_open"]
    assert row["left_hoop1"] == pytest.approx(np.hypot(-18.0 - HOOP_X, 20.0), abs=1e-3)
    assert row["left_zone1"] == "wing_3"
    assert row["handler_hoop0"] == pytest.approx(-16.0 - HOOP_X, abs=1e-3)


def test_open_flag_follows_the_nearest_defender_not_the_helper():
    start, end = START.copy(), END.copy()
    start[8] = end[8] = [-20.0, -17.0]  # a defender parked 3.6 ft from the man left
    row = help_table(_scene(start=start, end=end), _drives()).iloc[0]
    assert row["left_sep1"] > 6.0  # the helper himself is far away
    assert row["left_nearest1"] == pytest.approx(np.hypot(2.0, 3.0), abs=1e-3)
    assert not row["left_open"]


def test_threshold_only_changes_the_flag_not_the_measurement():
    row = help_table(_scene(), _drives(), help_ft=6.0).iloc[0]
    assert not row["has_helper"]
    assert row["helper_def_slot"] == 1 and row["helper_help_move"] == pytest.approx(5.0, abs=1e-3)


def test_drive_frame_mirrors_a_right_hand_drive_onto_a_left_hand_one():
    left = help_table(_scene(), _drives()).iloc[0]
    right = help_table(_scene(mirror_y=True), _drives()).iloc[0]
    assert right["flip"] == -1.0
    for column in ("helper_def_slot", "helper_help_move", "helper_origin_x", "helper_origin_y",
                   "helper_dx", "helper_dy", "handler_y1", "left_y1", "left_sep1",
                   "left_nearest1", "left_hoop1", "left_zone1"):
        assert right[column] == pytest.approx(left[column]) if isinstance(left[column], float) \
            else right[column] == left[column], column
    vectors_l = help_vectors(_scene(), _drives()).set_index("def_slot")
    vectors_r = help_vectors(_scene(mirror_y=True), _drives()).set_index("def_slot")
    assert np.allclose(vectors_l[["origin_y", "dy"]], vectors_r[["origin_y", "dy"]], atol=1e-5)


def test_a_helper_with_no_assigned_attacker_leaves_nan_not_a_guess():
    matchup = np.broadcast_to(np.array([0, 3, 2, 4, -1], np.int8), (HORIZON_FRAMES + 1, 5))
    row = help_table(_scene(matchup=matchup), _drives()).iloc[0]
    assert row["helper_def_slot"] == 1  # the geometry is unchanged
    assert row["left_slot"] == -1 and np.isnan(row["left_sep1"]) and not row["left_open"]


# ---------------------------------------------------------------- unresolved drives


def test_unresolved_drives_keep_their_row_with_a_status():
    frames = _scene(n=HORIZON_FRAMES + 11)
    boundary = _scene(chance_idx=np.r_[np.zeros(20, int), np.ones(HORIZON_FRAMES - 19, int)])
    drives = pd.concat([
        _drives(start_frame=FIRST_FRAME, drive_id="ok"),
        _drives(start_frame=FIRST_FRAME + 500, drive_id="no_frame"),
        _drives(start_frame=FIRST_FRAME + 10 + 1, drive_id="no_horizon"),
        _drives(handler=9999, drive_id="no_handler"),
    ], ignore_index=True)
    endpoints = drive_endpoints(frames, drives).set_index("drive_id")
    assert endpoints["status"].to_dict() == {
        "ok": "ok", "no_frame": "no_frame", "no_horizon": "no_horizon", "no_handler": "no_handler",
    }
    assert drive_endpoints(boundary, _drives()).iloc[0]["status"] == "no_horizon"
    table = help_table(frames, drives)
    assert len(table) == 4 and set(table["status"]) <= set(STATUSES)
    unresolved = table[table["status"] != "ok"]
    assert unresolved["helper_help_move"].isna().all() and not unresolved["has_helper"].any()
    assert len(help_vectors(frames, drives)) == 4


# --------------------------------------------------------------------- the flow field


def test_flow_field_aggregates_cells_and_reports_consistency():
    same = pd.DataFrame({
        "origin_x": HOOP_X + 12.0, "origin_y": -3.0, "dx": -2.0, "dy": 1.0, "help_move": 1.5,
    }, index=range(20))
    cancel = pd.DataFrame({
        "origin_x": HOOP_X + 20.0, "origin_y": 12.0, "dx": [1.0, -1.0] * 10, "dy": 0.0,
        "help_move": 0.0,
    })
    sparse = pd.DataFrame({
        "origin_x": HOOP_X + 30.0, "origin_y": 0.0, "dx": 1.0, "dy": 1.0, "help_move": 0.0,
    }, index=range(5))
    flow = flow_field(pd.concat([same, cancel, sparse], ignore_index=True))
    assert len(flow) == 2  # the five-vector cell is dropped
    cell = flow.set_index(["cell_x", "cell_y"])
    a = cell.loc[(1, 2)]
    assert a["n"] == 20
    assert a["mean_dx"] == pytest.approx(-2.0) and a["mean_dy"] == pytest.approx(1.0)
    assert a["consistency"] == pytest.approx(1.0)
    assert a["x_center"] == pytest.approx(HOOP_X + 12.0) and a["y_center"] == pytest.approx(0.0)
    b = cell.loc[(2, 3)]
    assert b["n"] == 20 and b["consistency"] == pytest.approx(0.0)


# ------------------------------------------------------------------- the real dataset


@pytest.mark.data
@requires_real_dataset
def test_one_published_game_resolves_and_never_names_the_matchup_as_helper():
    dataset = Dataset(REAL_DATASET_ROOT)
    game_id = 114086
    frames = get_or_build(dataset, game_id, CACHE_DIR)
    drives = dataset.events(game_id)["drives"]
    table = help_table(frames, drives)
    assert len(table) == len(drives)
    ok = table[table["status"] == "ok"]
    assert len(ok) >= 0.85 * len(table)
    assert (ok["helper_def_slot"] != ok["handler_def_slot"]).all()
    assert np.isfinite(ok["helper_help_move"]).all()
    assert ok["has_helper"].eq(ok["helper_help_move"] >= HELP_FT).all()
    vectors = help_vectors(frames, drives)
    assert len(vectors) == 4 * len(ok)
    assert set(vectors["def_slot"]) <= {0, 1, 2, 3, 4}
