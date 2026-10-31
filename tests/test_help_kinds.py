"""Tests for scbasket.help_kinds: near help (stunt / committed) and long help by the last.

Every convention is pinned on a scene built by hand on the W1 scene of `test_wind`, with the
frames written out as keyframes so a defender can step and come back. Attackers are slots 0-4,
defenders slots 0-4 (xy rows 5-9), the raw matchup is the identity, the handler (attacker 0, at
(-16, 0), his defender slot 0) is the ball. Off the ball, the NEAREST defender is slot 3 at
(-12, -13) guarding attacker 3, and the LAST is slot 2 at (-30, 12) guarding attacker 2.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from test_wind import START, _drives, _frames

from scbasket.help_kinds import drive_kinds, kind_help_table
from scbasket.rotation import rotation_table
from scbasket.wind import help_table

FIRST_FRAME = 100
N = 60  # 2.4 s: the 2.0 s window exists
NEAR, LAST = 3, 2  # defender slots; their xy rows are 5 + slot


def _track(keys: dict[int, list[tuple[int, tuple[float, float]]]], matchup=None):
    """Frames where the xy rows in `keys` follow their (frame, point) keyframes, the rest stand."""
    xy = np.repeat(START[None], N, axis=0)
    t = np.arange(N)
    for row, points in keys.items():
        f, p = zip(*points, strict=True)
        xy[:, row] = np.stack([np.interp(t, f, [q[0] for q in p]),
                               np.interp(t, f, [q[1] for q in p])], axis=1)
    return _frames(xy, np.arange(FIRST_FRAME, FIRST_FRAME + N), matchup=matchup)


def _kinds(frames) -> pd.DataFrame:
    drives = _drives().assign(blowby=False)
    return drive_kinds(frames, drives, help_table(frames, drives)).iloc[0]


def _step_toward_handler(feet: float) -> tuple[float, float]:
    """The point `feet` from the nearest defender's start on the line to the (static) handler."""
    p0, h = START[5 + NEAR], START[0]
    q = p0 + feet * (h - p0) / np.linalg.norm(h - p0)
    return float(q[0]), float(q[1])


# ----------------------------------------------------------------------------- near help


def test_a_nearest_who_steps_three_feet_and_returns_is_a_stunt():
    p0 = tuple(START[5 + NEAR])
    row = _kinds(_track({5 + NEAR: [(0, p0), (12, _step_toward_handler(3.0)), (40, p0), (N, p0)]}))
    assert row["near_slot"] == NEAR and row["near_man"] == NEAR and row["near_status"] == "ok"
    assert row["near_move"] == pytest.approx(3.0, abs=1e-6)
    assert row["near_stunt"] and not row["near_committed"] and not row["near_ref"]


def test_a_nearest_who_steps_three_feet_and_stays_is_committed():
    p0 = tuple(START[5 + NEAR])
    step = _step_toward_handler(3.0)
    row = _kinds(_track({5 + NEAR: [(0, p0), (12, step), (N, step)]}))
    assert row["near_move"] == pytest.approx(3.0, abs=1e-6)
    assert row["near_committed"] and not row["near_stunt"] and not row["near_ref"]


def test_a_man_who_cuts_to_his_helper_leaves_the_help_committed_and_flips_only_the_old_rule():
    # The helper steps 5 ft toward the handler and stays; his man (attacker 3) cuts to within
    # 1 ft of him by 2.0 s. Only the helper's own movement decides: he is far from where his man
    # started, so committed. The rule before the review read the man at 2.0 s and called it a
    # stunt, which let the man's run, the measure's own target, pick the class.
    p0 = tuple(START[5 + NEAR])
    step = _step_toward_handler(5.0)
    near_man = np.asarray(step) + np.array([1.0, 0.0])
    frames = _track({5 + NEAR: [(0, p0), (12, step), (N, step)],
                     NEAR: [(0, tuple(START[NEAR])), (25, tuple(START[NEAR])),
                            (50, tuple(near_man)), (N, tuple(near_man))]})
    row = _kinds(frames)
    assert row["near_move"] == pytest.approx(5.0, abs=1e-6)
    assert row["near_dist2_man"] == pytest.approx(1.0, abs=1e-6)
    assert row["near_dist2_start"] > row["near_dist0"] + 1.0
    assert row["near_committed"] and not row["near_stunt"]
    assert not row["near_committed_endpos"]


def test_a_nearest_who_stays_put_is_the_near_reference_and_neither_kind():
    row = _kinds(_track({}))
    assert row["near_move"] == pytest.approx(0.0, abs=1e-9)
    assert row["near_ref"] and not row["near_stunt"] and not row["near_committed"]


def test_a_near_drive_without_the_two_second_window_is_dropped_not_classified():
    frames = _track({5 + NEAR: [(0, tuple(START[5 + NEAR])), (12, _step_toward_handler(3.0)),
                                (N, _step_toward_handler(3.0))]})
    cut = np.r_[np.zeros(40, int), np.ones(N - 40, int)]  # a chance boundary at 1.6 s
    frames = replace(frames, chance_idx=cut.astype(np.int32))
    row = _kinds(frames)
    assert row["near_status"] == "no_window"
    assert not (row["near_stunt"] or row["near_committed"] or row["near_ref"])


# ---------------------------------------------------------------------------- long help

# The handler drives to (-30, 4). The last (slot 2, from (-30, 12)) walks to (-34, 4): 4 ft from
# the handler and nearer the hoop (-40.76, 0). His defender (slot 0) trails to (-25, 4).
HANDLER_END = (-30.0, 4.0)
LAST_END = (-34.0, 4.0)


def _drive(handler_def_end, last_end):
    return _track({
        0: [(0, tuple(START[0])), (38, HANDLER_END), (N, HANDLER_END)],
        5: [(0, tuple(START[5])), (38, handler_def_end), (N, handler_def_end)],
        5 + LAST: [(0, tuple(START[5 + LAST])), (38, last_end), (N, last_end)],
    })


def test_on_a_beaten_drive_a_last_who_ends_four_feet_from_the_handler_ahead_of_him_is_long():
    row = _kinds(_drive((-25.0, 4.0), LAST_END))
    assert row["last_slot"] == LAST and row["last_man"] == LAST and row["last_status"] == "ok"
    assert row["beaten_geo"] and row["path6"] and row["path5"] and row["path8"]
    assert row["long"] and not row["long_ref"]


def test_a_last_who_stays_home_on_an_unbeaten_drive_is_the_reference():
    row = _kinds(_drive((-34.0, 4.0), tuple(START[5 + LAST])))  # his defender stays ahead
    assert not row["beaten_geo"]
    assert row["last_move"] < 2.0
    assert row["long_ref"] and not row["long"]


def test_the_path_radius_decides_a_last_who_ends_seven_feet_ahead_of_the_handler():
    row = _kinds(_drive((-25.0, 4.0), (-37.0, 4.0)))  # 7 ft from the handler, nearer the hoop
    assert row["beaten_geo"] and not row["path6"] and not row["path5"] and row["path8"]
    assert not row["long"] and not row["long_path5"]


def test_a_last_without_a_raw_man_is_dropped_and_never_long():
    matchup = np.broadcast_to(np.array([0, 1, -1, 3, 4], np.int8), (N, 5))
    frames = _drive((-25.0, 4.0), LAST_END)
    frames = replace(frames, matchup=np.array(matchup))
    row = _kinds(frames)
    assert row["last_status"] == "no_man"
    assert not (row["long"] or row["long_ref"])


# ------------------------------------------------------------------------- who rotates


def test_a_defender_who_rotates_onto_the_lasts_man_scores_a_positive_paired_difference():
    # slot 4 (row 9, at (-16, 16)) walks 5 ft toward attacker 2 (-30, 15), the last's man
    p0, man = START[9], START[LAST]
    end = p0 + 5.0 * (man - p0) / np.linalg.norm(man - p0)
    frames = _drive((-25.0, 4.0), LAST_END)
    xy = frames.xy.copy()
    xy[:, 9] = np.stack([np.interp(np.arange(N), [0, 38, N], [p0[0], end[0], end[0]]),
                         np.interp(np.arange(N), [0, 38, N], [p0[1], end[1], end[1]])], axis=1)
    frames = replace(frames, xy=xy)
    drives = _drives().assign(blowby=False)
    table = help_table(frames, drives)
    kinds = drive_kinds(frames, drives, table)
    assert bool(kinds.iloc[0]["long"])
    pairs, _ = rotation_table(frames, drives, kind_help_table(frames, table, kinds, "long",
                                                              "long_ref", "last"))
    at = pairs[pairs["horizon"] == 38]
    assert sorted(at["def_slot"]) == [1, 3, 4]  # not the handler's defender, not the last
    diff = (at["to_left"] - at["placebo"]).set_axis(at["def_slot"])
    assert diff[4] > 4.0
    assert diff[1] == pytest.approx(0.0, abs=1e-9) and diff[3] == pytest.approx(0.0, abs=1e-9)
    assert at["helped"].all()
