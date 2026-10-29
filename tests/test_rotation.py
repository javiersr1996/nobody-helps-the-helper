"""Tests for scbasket.rotation: the second help, a displacement toward the man left vs a placebo.

Published as a DEFINITION, so every convention is pinned against a scene built by hand on the
W1 scene of `test_wind`: a third defender rotating exactly 5 ft toward the man left reads
5.0, three defenders who only sink along x read a paired difference of exactly 0.0 when their
targets are mirrored across their lines, the defender's own man (by the RAW matchup) is never
in his placebo, the helper and the handler's matchup are never among the three others, a window
cut by a chance boundary drops the horizons it cannot reach and keeps the row, and `nearest_who`
names the helper when he recovers to within a foot of the man left.
"""

from __future__ import annotations

import numpy as np
import pytest
from conftest import REAL_DATASET_ROOT, requires_real_dataset
from test_wind import CACHE_DIR, END, START, _drives, _scene

from scbasket.frames import get_or_build
from scbasket.io import Dataset
from scbasket.rotation import CLEARANCE_FRAMES, ROTATION_HORIZONS, rotation_table
from scbasket.wind import HORIZON_FRAMES, help_table


def _run(frames, horizons=(HORIZON_FRAMES,)):
    drives = _drives()
    return rotation_table(frames, drives, help_table(frames, drives), horizons)


def _toward(start, target, feet):
    """The point `feet` away from `start` on the straight line to `target`."""
    direction = np.asarray(target, float) - start
    return start + feet * direction / np.linalg.norm(direction)


def _proj(p0, p1, target):
    """Reference projection, written out from the definition, not imported."""
    u = np.asarray(target, float) - p0
    return float((p1 - p0) @ u / np.linalg.norm(u))


# (a) -------------------------------------------------------------- a rotation of exactly 5 ft


def test_a_rotation_of_five_feet_toward_the_man_left_is_the_best_mover():
    end = END.copy()
    end[7] = _toward(START[7], START[1], 5.0)  # defender slot 2 walks 5 ft at attacker 1
    pairs, drives_out = _run(_scene(end=end))
    row = drives_out.iloc[0]
    assert row["left_id"] == 5002 and row["rot_left_25"] == pytest.approx(5.0, abs=1e-4)
    mover = pairs[pairs["def_slot"] == 2].iloc[0]
    assert mover["to_left"] == pytest.approx(5.0, abs=1e-4)
    assert mover["placebo"] < 5.0
    assert (pairs[pairs["def_slot"] != 2]["to_left"] < 5.0).all()
    # the placebo is the mean over attackers 3 and 4 (not the handler, the man left or his own)
    expected = np.mean([_proj(START[7], end[7], START[a]) for a in (3, 4)])
    assert mover["placebo"] == pytest.approx(expected, abs=1e-4)


# (b) ------------------------------------------------- sinking only: the paired difference is 0

LEFT_Y, PLACEBO_Y = -8.0, 8.0  # the man left and the placebo attackers, mirrored across y = 0


def _sinkers() -> tuple[np.ndarray, np.ndarray]:
    """Defenders 7, 8, 9 stand on y = 0 and sink 2 ft along x; every target is mirrored."""
    start = np.array([
        [-16.0, 0.0], [-18.0, LEFT_Y], [-18.0, PLACEBO_Y], [-18.0, PLACEBO_Y],
        [-18.0, PLACEBO_Y],
        [-19.0, 1.0], [-20.0, LEFT_Y], [-30.0, 0.0], [-33.0, 0.0], [-36.0, 0.0],
    ])
    end = start.copy()
    end[0] = [-24.0, 6.0]
    end[5] = [-26.0, 6.0]
    end[7:, 0] -= 2.0
    return start, end


def test_three_others_who_only_sink_read_zero_against_mirrored_targets():
    start, end = _sinkers()
    pairs, _ = _run(_scene(start=start, end=end))
    assert sorted(pairs["def_slot"]) == [2, 3, 4]
    assert (pairs["to_left"] < -1.0).all()  # they do move: the zero is a difference, not stillness
    assert (pairs["to_left"] - pairs["placebo"]).abs().max() == pytest.approx(0.0, abs=1e-9)


# (c) ------------------------------------------ the defender's own man is never in his placebo


def test_the_own_man_by_the_raw_matchup_is_never_a_placebo_target():
    end = END.copy()
    end[7] = _toward(START[7], START[1], 5.0)
    # attacker 2 is guarded by defender slot 3 and attacker 3 by slot 2 (the mover), raw
    matchup = np.broadcast_to(np.array([0, 1, 3, 2, 4], np.int8), (HORIZON_FRAMES + 1, 5))
    pairs, _ = _run(_scene(end=end, matchup=matchup))
    mover = pairs[pairs["def_slot"] == 2].iloc[0]
    honest = np.mean([_proj(START[7], end[7], START[a]) for a in (2, 4)])
    by_slot_number = np.mean([_proj(START[7], end[7], START[a]) for a in (3, 4)])
    assert abs(honest - by_slot_number) > 0.1  # the scene can tell the two apart
    assert mover["placebo"] == pytest.approx(honest, abs=1e-4)


# (d) ------------------------------------------- the helper and the handler's matchup are out


def test_the_helper_and_the_handlers_matchup_are_never_among_the_three_others():
    pairs, _ = _run(_scene())  # helper is defender slot 1, the handler's matchup slot 0
    assert sorted(pairs["def_slot"]) == [2, 3, 4]
    end = END.copy()
    end[6] = START[6]  # slot 1 stands still ...
    end[8] = _toward(START[8], END[0], 6.0)  # ... and slot 3 becomes the largest mover
    pairs, drives_out = _run(_scene(end=end))
    assert sorted(pairs["def_slot"]) == [1, 2, 4]
    assert drives_out.iloc[0]["left_id"] == 5004  # the man slot 3 guards at the start


# (e) ---------------------------------------------------------- a chance boundary inside the window


def test_a_cut_window_drops_the_horizons_it_cannot_reach_and_keeps_the_row():
    n = 51
    chance = np.r_[np.zeros(31, int), np.ones(n - 31, int)]  # rows 0-30 are the chance
    pairs, drives_out = _run(_scene(n=n, chance_idx=chance), ROTATION_HORIZONS)
    assert len(drives_out) == 1
    row = drives_out.iloc[0]
    assert row["window_frames"] == 30
    assert set(pairs["horizon"]) == {25} and len(pairs) == 3
    assert np.isfinite(row["rot_left_25"]) and row["nearest_who_25"] != ""
    for horizon in (38, 50):
        assert np.isnan(row[f"rot_left_{horizon}"]) and row[f"nearest_who_{horizon}"] == ""
        assert np.isnan(row[f"nearest_dist_{horizon}"])
    assert np.isfinite(row["left_clear_25"]) and np.isnan(row["left_clear_38"])
    whole = _run(_scene(n=n), ROTATION_HORIZONS)[1].iloc[0]
    assert whole["window_frames"] == 50 and np.isfinite(whole["rot_left_50"])
    assert all(np.isfinite(whole[f"left_clear_{t}"]) for t in CLEARANCE_FRAMES)


# (g) ------------------------------------------- the man left's position is in the drive frame


def test_the_man_left_position_is_in_the_drive_frame_on_either_side():
    plain = _run(_scene())[1].iloc[0]
    mirrored = _run(_scene(mirror_y=True))[1].iloc[0]  # the same drive seen from the other side
    assert plain["left_x_25"] == pytest.approx(START[1][0]) and plain["left_y_25"] == -20.0
    # raw y is +20 here; only the flip puts him back on y = -20, where the other side has him
    assert mirrored["left_y_25"] == pytest.approx(plain["left_y_25"])
    assert mirrored["left_x_25"] == pytest.approx(plain["left_x_25"])


# (f) ----------------------------------------------------------------------- nearest_who


def test_nearest_who_reads_helper_when_he_recovers_to_within_a_foot():
    end = END.copy()
    end[1] = END[6] + np.array([0.5, 0.0])  # the man left ends 0.5 ft from the helper
    _, drives_out = _run(_scene(end=end))
    row = drives_out.iloc[0]
    assert row["nearest_who_25"] == "helper"
    assert row["nearest_dist_25"] == pytest.approx(0.5, abs=1e-4)


def test_nearest_who_tells_the_handlers_matchup_and_a_third_defender_apart():
    _, base = _run(_scene())
    assert base.iloc[0]["nearest_who_25"] == "third"  # defender slot 3 at (-12, -13)
    assert base.iloc[0]["nearest_dist_25"] == pytest.approx(np.hypot(6.0, 7.0), abs=1e-4)
    end = END.copy()
    end[5] = START[1] + np.array([0.0, 0.3])  # the handler's matchup lands on the man left
    _, near = _run(_scene(end=end))
    assert near.iloc[0]["nearest_who_25"] == "handler_def"


# ------------------------------------------------------------------- the real dataset


@pytest.mark.data
@requires_real_dataset
def test_one_published_game_keeps_the_helper_and_the_handlers_matchup_out_of_the_others():
    dataset = Dataset(REAL_DATASET_ROOT)
    game_id = 114086
    frames = get_or_build(dataset, game_id, CACHE_DIR)
    drives = dataset.events(game_id)["drives"]
    table = help_table(frames, drives)
    pairs, drives_out = rotation_table(frames, drives, table)
    ok = table[(table["status"] == "ok") & (table["left_slot"] >= 0)]
    assert len(drives_out) == len(ok) > 0
    merged = pairs.merge(ok[["drive_id", "helper_def_slot", "handler_def_slot"]], on="drive_id")
    assert (merged["def_slot"] != merged["helper_def_slot"]).all()
    assert (merged["def_slot"] != merged["handler_def_slot"]).all()
    assert pairs.groupby(["drive_id", "horizon"]).size().eq(3).all()
