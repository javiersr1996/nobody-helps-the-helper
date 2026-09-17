"""Tests for scbasket.tagging: the high-side layer (F5) and the approach kinematics (F6).

This layer is published as a DEFINITION rather than a detector, because the open bundle
carries no crash or box-out label to check it against. A definition earns trust by being
exact, so the sign convention and the shooter exclusion are pinned against hand-built
geometry where the answer can be read off the coordinates.

The same applies to the approach angle at the bottom of the file, which carries the
headline: every convention is checked against coordinates, and the inputs it is allowed to
read are checked too, because a heading that never touches the ball or the matchup is what
keeps F6 on the right side of the ruling that tracking cannot show intent.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import GAME_ID, REAL_DATASET_ROOT, requires_real_dataset

from scbasket.control import ControlParams
from scbasket.court import make_grid
from scbasket.frames import N_SIDE, GameFrames, at_frames, get_or_build
from scbasket.io import Dataset
from scbasket.tagging import (
    APPROACH_LEAD_FRAMES,
    ATTACKED_HOOP,
    COMMITTED_ANGLE_DEG,
    DEPTH_CONTROLS,
    FLIGHT_FEATURES,
    MIN_APPROACH_SPEED,
    OWN_HOOP,
    TAG_FEATURES,
    approach_angles,
    high_side_distance,
    high_side_for_pairs,
    rebound_zone_table,
    release_frames_for,
    retreat_match_distance,
    retreat_pairs,
    tag_features,
    tag_flight_features,
    transition_outcome,
    zone_radius,
)
from scbasket.validation import CALIBRATION_GAMES, spearman
from scbasket.value import surface_from_zones

CACHE_DIR = REAL_DATASET_ROOT.parents[1] / "interim"
GRID = make_grid(2.0)
SHOOTER_ID = 5001


def _ids(value, first: int, n: int) -> np.ndarray:
    """(n, 5) player ids: the default block, or one explicit row broadcast over every frame."""
    if value is None:
        value = np.arange(first, first + N_SIDE)
    return np.broadcast_to(np.asarray(value, np.int32), (n, N_SIDE)).astype(np.int32)


def _frames(xy, chance_idx=None, frame_idx=None, matchup=None, v=None,
            off_ids=None, def_ids=None) -> GameFrames:
    xy = np.asarray(xy, dtype=np.float32)
    n = len(xy)
    if frame_idx is None:
        frame_idx = np.arange(n, dtype=np.int32)
    frame_idx = np.asarray(frame_idx, np.int32)
    ball = np.concatenate([xy[:, 0], np.full((n, 1), 4.0, np.float32)], axis=1)
    return GameFrames(
        game_id=GAME_ID,
        frame_idx=frame_idx,
        wall_clock=frame_idx.astype(np.int64) * 40,
        shot_clock=np.full(n, 12.0, np.float32),
        period=np.ones(n, np.int8),
        possession_idx=np.zeros(n, np.int32),
        chance_idx=np.zeros(n, np.int32) if chance_idx is None
        else np.asarray(chance_idx, np.int32),
        off_ids=_ids(off_ids, 5001, n),
        def_ids=_ids(def_ids, 6001, n),
        xy=xy,
        v=np.zeros((n, 10, 2), np.float32) if v is None
        else np.asarray(v, np.float32).reshape(n, 10, 2),
        pred_error=np.ones((n, 10), np.float32),
        detected=np.ones((n, 10), bool),
        ball=ball,
        ball_holder=np.zeros(n, np.int8),
        matchup=np.full((n, 5), -1, np.int8) if matchup is None else np.asarray(matchup, np.int8),
    )


def _shots(n: int, shooter: int = SHOOTER_ID) -> pd.DataFrame:
    return pd.DataFrame({"shooterId": [shooter] * n})


def _shots_with_ids(ids, shooters=None) -> pd.DataFrame:
    """Shots carrying the two columns the retreat and flight functions read: id and shooterId."""
    return pd.DataFrame({
        "id": list(ids),
        "shooterId": [SHOOTER_ID] * len(ids) if shooters is None else list(shooters),
    })


def _line_of_players(offsets_from_defender: list[float]) -> np.ndarray:
    """Five attackers and five defenders on the x axis; each attacker offset toward OWN_HOOP.

    OWN_HOOP sits at positive x, so a positive offset must read as a positive high side.
    """
    xy = np.zeros((1, 10, 2), np.float32)
    xy[0, 5:, 0] = np.arange(5) * 0.0  # every defender at the origin, on the axis to OWN_HOOP
    xy[0, :5, 0] = offsets_from_defender
    return xy


# -------------------------------------------------------------------------- the sign convention


def test_high_side_is_positive_toward_the_basket_the_attacker_must_defend():
    assert OWN_HOOP[0] > 0, "the test geometry below assumes the own hoop sits at positive x"
    xy = _line_of_players([5.0, -5.0, 0.0, 12.0, -1.0])
    got = high_side_distance(_frames(xy))[0]
    assert got == pytest.approx([5.0, -5.0, 0.0, 12.0, -1.0], abs=1e-4)


def test_high_side_measures_along_the_retreat_direction_not_raw_separation():
    """An attacker displaced sideways from their defender is level, not ahead."""
    xy = np.zeros((1, 10, 2), np.float32)
    xy[0, :5, 1] = 8.0  # every attacker 8 ft to the side, same x as their defender
    assert high_side_distance(_frames(xy))[0] == pytest.approx(np.zeros(5), abs=1e-3)


def test_a_defender_standing_on_the_own_hoop_does_not_blow_up():
    """The unit vector is undefined there; it must fall back to zero rather than NaN."""
    xy = np.zeros((1, 10, 2), np.float32)
    xy[0, 5:] = OWN_HOOP
    assert np.isfinite(high_side_distance(_frames(xy))).all()


# ------------------------------------------------------------------------------ tag_features


def test_the_shooter_is_excluded_from_every_aggregate():
    """The shooter is not tagging anyone, and they sit near the offensive rim by construction."""
    xy = _line_of_players([100.0, 1.0, 1.0, 1.0, 1.0])  # slot 0 is the shooter, wildly high side
    row = tag_features(_frames(xy), _shots(1)).iloc[0]
    assert row["tag_index"] == pytest.approx(1.0)
    assert row["high_side_mean"] == pytest.approx(1.0)
    assert row["high_side_max"] == pytest.approx(1.0), "the shooter's 100 ft leaked in"


def test_tag_index_counts_only_the_strictly_positive_side():
    xy = _line_of_players([0.0, -3.0, 2.0, 4.0, 0.0])  # slot 0 is the shooter
    row = tag_features(_frames(xy), _shots(1)).iloc[0]
    assert row["tag_index"] == pytest.approx(0.5)  # two of the four others are above zero


def test_tag_features_returns_both_blocks_and_keeps_them_named():
    row = tag_features(_frames(_line_of_players([0.0] * 5)), _shots(1))
    assert set(TAG_FEATURES) <= set(row.columns)
    assert set(DEPTH_CONTROLS) <= set(row.columns)
    assert not set(TAG_FEATURES) & set(DEPTH_CONTROLS)


def test_depth_controls_see_a_deep_offense_as_deep():
    """The control that stops the tag geometry from merely restating 'they stood further back'."""
    near = np.zeros((1, 10, 2), np.float32)
    near[0, :5] = np.array([-40.0, 0.0], np.float32)  # attackers on top of the attacked rim
    far = np.zeros((1, 10, 2), np.float32)
    far[0, :5] = np.array([10.0, 0.0], np.float32)  # attackers already retreating

    near_row = tag_features(_frames(near), _shots(1)).iloc[0]
    far_row = tag_features(_frames(far), _shots(1)).iloc[0]
    assert near_row["off_rim_dist_mean"] < far_row["off_rim_dist_mean"]
    assert near_row["n_inside_15ft"] > far_row["n_inside_15ft"]


def test_a_length_mismatch_is_refused_rather_than_broadcast():
    with pytest.raises(ValueError, match="release has"):
        tag_features(_frames(_line_of_players([0.0] * 5)), _shots(3))


def test_an_empty_input_returns_an_empty_frame_with_the_columns():
    out = tag_features(_frames(np.zeros((0, 10, 2), np.float32)), _shots(0))
    assert len(out) == 0
    assert set(TAG_FEATURES) <= set(out.columns)


# ------------------------------------------------------------------------ transition_outcome


def _rebounds(rows) -> pd.DataFrame:
    """rows: (id, shotId, defensive, nextChanceId)."""
    return pd.DataFrame(rows, columns=["id", "shotId", "defensive", "nextChanceId"])


def _chances(ids, transition=None, pts=None) -> pd.DataFrame:
    return pd.DataFrame({
        "id": list(ids),
        "transition": [False] * len(ids) if transition is None else transition,
        "ptsScored": [0] * len(ids) if pts is None else pts,
    })


def _surface(value: float) -> object:
    return surface_from_zones(GRID, {z: value for z in set(GRID.zone)})


def test_only_defensive_rebounds_become_rows():
    """An offensive rebound keeps the ball; there is no opponent break to measure."""
    frames = _frames(np.zeros((4, 10, 2), np.float32), chance_idx=[0, 0, 1, 1])
    reb = _rebounds([
        ("r1", "s1", True, "c1"),
        ("r2", "s2", False, "c1"),
        ("r3", "s3", True, None),
    ])
    args = (_chances(["c0", "c1"]), GRID, ControlParams(), _surface(1.0))
    out = transition_outcome(frames, reb, *args)
    assert out["rebound_id"].tolist() == ["r1"]


def test_break_area_is_nan_when_the_next_chance_has_no_cached_frame():
    """Counted, not silently dropped: D12 removes whole chances and the caller must see it."""
    frames = _frames(np.zeros((2, 10, 2), np.float32), chance_idx=[0, 0])
    reb = _rebounds([("r1", "s1", True, "c1")])
    args = (_chances(["c0", "c1"]), GRID, ControlParams(), _surface(1.0))
    out = transition_outcome(frames, reb, *args)
    assert len(out) == 1 and np.isnan(out.loc[0, "break_area"])


def test_break_area_only_reads_the_window_after_the_rebound():
    """Frames past the window must not move the mean, or the outcome is not about the break."""
    n = 200
    xy = np.zeros((n, 10, 2), np.float32)
    xy[:, :5, 0] = -30.0
    xy[100:, :5, 0] = 40.0  # a big change well past a 1-frame window
    frames = _frames(xy, chance_idx=np.ones(n, np.int32), frame_idx=np.arange(n))
    reb = _rebounds([("r1", "s1", True, "c1")])
    args = (_chances(["c0", "c1"]), GRID, ControlParams(), _surface(1.0))

    short = transition_outcome(frames, reb, *args, window_frames=1).loc[0, "break_area"]
    long = transition_outcome(frames, reb, *args, window_frames=n).loc[0, "break_area"]
    assert short != pytest.approx(long)


def test_the_events_columns_travel_through_unchanged():
    frames = _frames(np.zeros((4, 10, 2), np.float32), chance_idx=[1, 1, 1, 1])
    reb = _rebounds([("r1", "s1", True, "c1")])
    chances = _chances(["c0", "c1"], transition=[False, True], pts=[0, 3])
    out = transition_outcome(frames, reb, chances, GRID, ControlParams(), _surface(1.0))
    assert bool(out.loc[0, "next_transition"]) is True
    assert out.loc[0, "next_pts"] == 3.0


# --------------------------------------------------------------------------- release_frames_for


def test_only_missed_shots_come_back():
    frames = _frames(np.zeros((10, 10, 2), np.float32), frame_idx=np.arange(10))
    shots = pd.DataFrame({"outcome": [True, False, False], "startFrame": [1, 2, 3],
                          "shooterId": [SHOOTER_ID] * 3})
    release, matched = release_frames_for(frames, shots)
    assert matched["startFrame"].tolist() == [2, 3]
    assert release.frame_idx.tolist() == [2, 3]
    assert len(release) == len(matched)


def test_a_shot_whose_release_frame_is_not_cached_is_dropped_from_both_sides():
    frames = _frames(np.zeros((3, 10, 2), np.float32), frame_idx=[0, 1, 2])
    shots = pd.DataFrame({"outcome": [False, False], "startFrame": [1, 999],
                          "shooterId": [SHOOTER_ID] * 2})
    release, matched = release_frames_for(frames, shots)
    assert len(release) == len(matched) == 1


# --------------------------------------------------------------------------------- retreat_pairs


def test_the_pairs_are_the_four_non_shooting_attackers_and_their_matched_defenders():
    matchup = np.array([[0, 4, 3, 2, 1]], np.int8)
    pairs = retreat_pairs(_frames(np.zeros((1, 10, 2), np.float32), matchup=matchup), _shots(1))
    assert len(pairs) == 1 and pairs[0].shape == (4, 2)
    assert pairs[0][:, 0].tolist() == [5002, 5003, 5004, 5005]  # the shooter 5001 is gone
    assert pairs[0][:, 1].tolist() == [6005, 6004, 6003, 6002]  # defender slots 4, 3, 2, 1


def test_a_missing_provider_matchup_falls_back_to_the_nearest_defender():
    """The D7 fallback: a frame the provider left unassigned is described, not dropped."""
    xy = np.zeros((1, 10, 2), np.float32)
    xy[0, :5, 1] = [0.0, 10.0, 20.0, 30.0, 40.0]  # attackers up the y axis
    xy[0, 5:, 1] = [41.0, 31.0, 21.0, 11.0, 1.0]  # defenders down it, so the pairing reverses
    pairs = retreat_pairs(_frames(xy), _shots(1))  # matchup defaults to -1 everywhere
    assert pairs[0][:, 1].tolist() == [6004, 6003, 6002, 6001]


def test_the_provider_matchup_wins_where_it_exists_and_only_the_gaps_fall_back():
    xy = np.zeros((1, 10, 2), np.float32)
    xy[0, :5, 1] = [0.0, 10.0, 20.0, 30.0, 40.0]
    xy[0, 5:, 1] = [41.0, 31.0, 21.0, 11.0, 1.0]
    matchup = np.array([[-1, 0, -1, -1, -1]], np.int8)  # only the first non-shooter is assigned
    pairs = retreat_pairs(_frames(xy, matchup=matchup), _shots(1))
    assert pairs[0][:, 1].tolist() == [6001, 6003, 6002, 6001]


def test_each_shot_drops_its_own_shooter_and_not_slot_zero():
    """Keyed on the shooter id, so a shot from another slot excludes that player instead."""
    pairs = retreat_pairs(_frames(np.zeros((2, 10, 2), np.float32)),
                          _shots_with_ids(["s1", "s2"], [5001, 5003]))
    assert pairs[0][:, 0].tolist() == [5002, 5003, 5004, 5005]
    assert pairs[1][:, 0].tolist() == [5001, 5002, 5004, 5005]


# ------------------------------------------------------------------------ retreat_match_distance


def _retreat_rebounds(rows) -> pd.DataFrame:
    """rows: (shotId, defensive, nextChanceId, frame)."""
    return pd.DataFrame(rows, columns=["shotId", "defensive", "nextChanceId", "frame"])


def _fc_chances(ids, frontcourt) -> pd.DataFrame:
    return pd.DataFrame({"id": list(ids), "frontcourtFrame": list(frontcourt)})


IDENTITY_MATCHUP = np.array([[0, 1, 2, 3, 4]], np.int8)


def _frontcourt_frame(separations: list[float], off_ids=None) -> GameFrames:
    """The frame at the opponent frontcourt crossing, with the possession already flipped.

    The 6001-6005 block is attacking by then and the 5001-5005 block defending, so every
    player has changed side and slot since the release. Each former attacker 500(k+1) is
    placed `separations[k]` feet from the defender 600(k+1) they were matched with.
    """
    xy = np.zeros((1, 10, 2), np.float32)
    xy[0, :5, 1] = np.arange(5) * 10.0  # 6001..6005, ten feet apart
    xy[0, 5:, 1] = np.arange(5) * 10.0
    xy[0, 5:, 0] = separations  # 5001..5005, each pushed off their old mark
    return _frames(
        xy,
        frame_idx=[400],
        off_ids=[6001, 6002, 6003, 6004, 6005] if off_ids is None else off_ids,
        def_ids=[5001, 5002, 5003, 5004, 5005],
    )


def _release_at(frame: int, n: int = 1) -> GameFrames:
    """n release frames with everyone on the origin and the provider matchup one to one."""
    return _frames(np.zeros((n, 10, 2), np.float32),
                   frame_idx=[frame + 20 * i for i in range(n)],
                   matchup=np.tile(IDENTITY_MATCHUP, (n, 1)))


def test_the_release_pairs_are_re_measured_after_the_possession_has_flipped():
    """P5.1b discriminating check: plain retreat puts you back, not back ATTACHED."""
    frames = _frontcourt_frame([0.0, 2.0, 4.0, 6.0, 8.0])  # the shooter separation is not counted
    out = retreat_match_distance(frames, _release_at(100), _shots_with_ids(["s1"]),
                                 _retreat_rebounds([("s1", True, "c1", 250)]),
                                 _fc_chances(["c0", "c1"], [np.nan, 400]))
    assert out.loc[0, "n_pairs_found"] == 4
    assert out.loc[0, "match_dist"] == pytest.approx(5.0, abs=1e-3)  # (2 + 4 + 6 + 8) / 4
    assert out.loc[0, "secs_to_frontcourt"] == pytest.approx(6.0)  # 150 frames at 25 fps


def test_a_player_missing_at_the_frontcourt_frame_is_left_out_of_the_mean():
    """Substitutions happen between the shot and the crossing; that pair is not measurable."""
    frames = _frontcourt_frame([0.0, 2.0, 4.0, 6.0, 8.0],
                               off_ids=[6001, 6002, 6003, 6004, 7777])  # 6005 came off
    out = retreat_match_distance(frames, _release_at(100), _shots_with_ids(["s1"]),
                                 _retreat_rebounds([("s1", True, "c1", 250)]),
                                 _fc_chances(["c0", "c1"], [np.nan, 400]))
    assert out.loc[0, "n_pairs_found"] == 3
    assert out.loc[0, "match_dist"] == pytest.approx(4.0, abs=1e-3)  # (2 + 4 + 6) / 3


def test_an_offensive_rebound_leaves_no_retreat_to_measure():
    frames = _frontcourt_frame([0.0, 2.0, 4.0, 6.0, 8.0])
    out = retreat_match_distance(frames, _release_at(100), _shots_with_ids(["s1"]),
                                 _retreat_rebounds([("s1", False, "c1", 250)]),
                                 _fc_chances(["c0", "c1"], [np.nan, 400]))
    assert out.loc[0, "n_pairs_found"] == 0
    assert np.isnan(out.loc[0, "match_dist"])


def test_a_chance_with_no_frontcourt_frame_is_not_guessed_at():
    frames = _frontcourt_frame([0.0, 2.0, 4.0, 6.0, 8.0])
    out = retreat_match_distance(frames, _release_at(100), _shots_with_ids(["s1"]),
                                 _retreat_rebounds([("s1", True, "c1", 250)]),
                                 _fc_chances(["c0", "c1"], [np.nan, np.nan]))
    assert np.isnan(out.loc[0, "match_dist"]) and out.loc[0, "n_pairs_found"] == 0


def test_a_next_chance_that_is_not_in_the_table_is_not_guessed_at():
    frames = _frontcourt_frame([0.0, 2.0, 4.0, 6.0, 8.0])
    out = retreat_match_distance(frames, _release_at(100), _shots_with_ids(["s1"]),
                                 _retreat_rebounds([("s1", True, "unknown-chance", 250)]),
                                 _fc_chances(["c0", "c1"], [np.nan, 400]))
    assert np.isnan(out.loc[0, "match_dist"])


def test_a_frontcourt_frame_absent_from_the_cache_reports_nothing_including_the_seconds():
    """D12 removes whole chances; the crossing then has no geometry and no timing to report."""
    frames = _frontcourt_frame([0.0, 2.0, 4.0, 6.0, 8.0])  # this frame is 400, the chance says 401
    out = retreat_match_distance(frames, _release_at(100), _shots_with_ids(["s1"]),
                                 _retreat_rebounds([("s1", True, "c1", 250)]),
                                 _fc_chances(["c0", "c1"], [np.nan, 401]))
    assert out.loc[0, "n_pairs_found"] == 0
    assert np.isnan(out.loc[0, "match_dist"]) and np.isnan(out.loc[0, "secs_to_frontcourt"])


def test_every_shot_gets_a_retreat_row_in_order_even_when_it_was_never_rebounded():
    frames = _frontcourt_frame([0.0, 2.0, 4.0, 6.0, 8.0])
    out = retreat_match_distance(frames, _release_at(100, n=2), _shots_with_ids(["s1", "s2"]),
                                 _retreat_rebounds([("s2", True, "c1", 250)]),
                                 _fc_chances(["c0", "c1"], [np.nan, 400]))
    assert len(out) == 2
    assert np.isnan(out.loc[0, "match_dist"]) and out.loc[0, "n_pairs_found"] == 0
    assert out.loc[1, "match_dist"] == pytest.approx(5.0, abs=1e-3)


def test_a_shot_with_two_defensive_rebounds_uses_the_first_row():
    """The real table has one per shot; a duplicate must not raise on the lookup either."""
    frames = _frontcourt_frame([0.0, 2.0, 4.0, 6.0, 8.0])
    out = retreat_match_distance(frames, _release_at(100), _shots_with_ids(["s1"]),
                                 _retreat_rebounds([("s1", True, "c1", 250),
                                                    ("s1", True, "c1", 300)]),
                                 _fc_chances(["c0", "c1"], [np.nan, 400]))
    assert out.loc[0, "secs_to_frontcourt"] == pytest.approx(6.0)  # from frame 250, not from 300


# ---------------------------------------------------------------------------- high_side_for_pairs


def test_the_id_keyed_high_side_agrees_with_the_slot_keyed_one_on_the_same_geometry():
    frame = _frames(_line_of_players([5.0, -5.0, 0.0, 12.0, -1.0]))
    pairs = np.column_stack([np.arange(5001, 5006), np.arange(6001, 6006)])
    assert high_side_for_pairs(frame, pairs) == pytest.approx(high_side_distance(frame)[0],
                                                              abs=1e-4)


def test_a_pair_reads_the_same_once_the_slots_and_the_sides_have_moved():
    """The same two ids are read at the release and again later, after the possession flips."""
    at_release = np.zeros((1, 10, 2), np.float32)
    at_release[0, 1] = (6.0, 0.0)  # attacker 5002, six feet toward OWN_HOOP of ...
    at_release[0, 7] = (0.0, 0.0)  # ... defender 6003, who is not their provider matchup
    pair = np.array([[5002, 6003]])
    before = high_side_for_pairs(_frames(at_release), pair)
    assert before == pytest.approx([6.0], abs=1e-4)

    later_xy = np.zeros((1, 10, 2), np.float32)
    later_xy[0, 2] = (0.0, 0.0)  # 6003 is attacking now, from slot 2
    later_xy[0, 6] = (6.0, 0.0)  # 5002 is defending now, from slot 6
    later = _frames(later_xy, off_ids=[6001, 6002, 6003, 6004, 6005],
                    def_ids=[5001, 5002, 5003, 5004, 5005])
    assert high_side_for_pairs(later, pair) == pytest.approx(before, abs=1e-4)


def test_a_player_absent_from_the_frame_gives_nan_rather_than_a_wrong_pair():
    frame = _frames(np.zeros((1, 10, 2), np.float32))
    got = high_side_for_pairs(frame, np.array([[5002, 6003], [7777, 6003], [5002, 8888]]))
    assert np.isfinite(got[0])
    assert np.isnan(got[1:]).all()


def test_the_id_keyed_high_side_survives_a_defender_on_the_own_hoop_too():
    xy = np.zeros((1, 10, 2), np.float32)
    xy[0, 5:] = OWN_HOOP
    assert np.isfinite(high_side_for_pairs(_frames(xy), np.array([[5001, 6001]]))).all()


# -------------------------------------------------------------------------- tag_flight_features


def _flight_rebounds(rows) -> pd.DataFrame:
    """rows: (shotId, frame)."""
    return pd.DataFrame(rows, columns=["shotId", "frame"])


def test_the_gain_is_the_high_side_taken_during_the_flight_not_the_pose_at_the_release():
    release = _frames(np.zeros((1, 10, 2), np.float32), frame_idx=[100])
    end = np.zeros((1, 10, 2), np.float32)
    end[0, 1:5, 0] = 6.0  # the four non-shooters each take six feet while the ball is up
    out = tag_flight_features(_frames(end, frame_idx=[125]), release, _shots_with_ids(["s1"]),
                              _flight_rebounds([("s1", 125)]))
    assert out.loc[0, "n_flight_pairs"] == 4
    assert out.loc[0, "high_side_gain_mean"] == pytest.approx(6.0, abs=1e-3)
    assert out.loc[0, "high_side_gain_min"] == pytest.approx(6.0, abs=1e-3)
    assert out.loc[0, "flight_secs"] == pytest.approx(1.0)  # 25 frames at 25 fps


def test_a_player_who_was_already_deep_and_stayed_there_gains_nothing():
    """The whole reason P5.1c exists: a gain cannot restate the depth that swallowed P5.1b."""
    deep = np.zeros((1, 10, 2), np.float32)
    deep[0, :5, 0] = 20.0  # the attackers were twenty feet high side before the shot left
    out = tag_flight_features(_frames(deep, frame_idx=[125]), _frames(deep, frame_idx=[100]),
                              _shots_with_ids(["s1"]), _flight_rebounds([("s1", 125)]))
    assert out.loc[0, "high_side_gain_mean"] == pytest.approx(0.0, abs=1e-3)
    assert out.loc[0, "high_side_end_mean"] == pytest.approx(20.0, abs=1e-3)
    assert out.loc[0, "tag_index_end"] == pytest.approx(1.0)


def test_the_flight_window_stops_at_two_seconds_however_late_the_rebound_is():
    """One window, taken from the mechanism. Trying windows until one passes is the F5 failure."""
    release = _frames(np.zeros((1, 10, 2), np.float32), frame_idx=[100])
    xy = np.zeros((300, 10, 2), np.float32)
    xy[:, 1:5, 0] = np.arange(300)[:, None]  # a foot of high side per frame, without end
    out = tag_flight_features(_frames(xy, frame_idx=np.arange(300)), release,
                              _shots_with_ids(["s1"]), _flight_rebounds([("s1", 250)]))
    assert out.loc[0, "flight_secs"] == pytest.approx(2.0)
    assert out.loc[0, "high_side_gain_mean"] == pytest.approx(150.0, abs=1e-3)


def test_every_shot_gets_a_flight_row_in_order_even_when_it_was_never_rebounded():
    release = _frames(np.zeros((2, 10, 2), np.float32), frame_idx=[100, 200])
    end = np.zeros((2, 10, 2), np.float32)
    end[1, 1:5, 0] = 5.0
    out = tag_flight_features(_frames(end, frame_idx=[125, 225]), release,
                              _shots_with_ids(["s1", "s2"]), _flight_rebounds([("s2", 225)]))
    assert len(out) == 2
    assert out.loc[0, "n_flight_pairs"] == 0
    assert out.loc[0, list(FLIGHT_FEATURES)].isna().all()
    assert out.loc[1, "high_side_gain_mean"] == pytest.approx(5.0, abs=1e-3)


def test_a_rebound_frame_missing_from_the_cache_is_not_guessed_at():
    release = _frames(np.zeros((1, 10, 2), np.float32), frame_idx=[100])
    frames = _frames(np.zeros((1, 10, 2), np.float32), frame_idx=[101])  # 125 is not cached
    out = tag_flight_features(frames, release, _shots_with_ids(["s1"]),
                              _flight_rebounds([("s1", 125)]))
    assert out.loc[0, "n_flight_pairs"] == 0 and np.isnan(out.loc[0, "high_side_gain_mean"])


def test_a_rebound_on_the_release_frame_leaves_no_flight_to_measure():
    release = _frames(np.zeros((1, 10, 2), np.float32), frame_idx=[100])
    out = tag_flight_features(release, release, _shots_with_ids(["s1"]),
                              _flight_rebounds([("s1", 100)]))
    assert out.loc[0, "n_flight_pairs"] == 0 and np.isnan(out.loc[0, "flight_secs"])


def test_a_player_who_left_the_floor_during_the_flight_is_dropped_from_the_averages():
    release = _frames(np.zeros((1, 10, 2), np.float32), frame_idx=[100])
    end = np.zeros((1, 10, 2), np.float32)
    end[0, 1:5, 0] = [4.0, 8.0, 12.0, 0.0]
    frames = _frames(end, frame_idx=[125], off_ids=[5001, 5002, 5003, 5004, 7777])
    out = tag_flight_features(frames, release, _shots_with_ids(["s1"]),
                              _flight_rebounds([("s1", 125)]))
    assert out.loc[0, "n_flight_pairs"] == 3
    assert out.loc[0, "high_side_gain_mean"] == pytest.approx(8.0, abs=1e-3)


def test_a_shot_that_appears_twice_in_the_rebounds_uses_the_first_frame():
    release = _frames(np.zeros((1, 10, 2), np.float32), frame_idx=[100])
    xy = np.zeros((2, 10, 2), np.float32)
    xy[0, 1:5, 0] = 2.0
    xy[1, 1:5, 0] = 9.0
    out = tag_flight_features(_frames(xy, frame_idx=[110, 140]), release, _shots_with_ids(["s1"]),
                              _flight_rebounds([("s1", 110), ("s1", 140)]))
    assert out.loc[0, "high_side_gain_mean"] == pytest.approx(2.0, abs=1e-3)


def test_tag_index_end_counts_the_strictly_positive_pairs():
    release = _frames(np.zeros((1, 10, 2), np.float32), frame_idx=[100])
    end = np.zeros((1, 10, 2), np.float32)
    end[0, 1:5, 0] = [3.0, -3.0, 0.0, 7.0]
    out = tag_flight_features(_frames(end, frame_idx=[125]), release, _shots_with_ids(["s1"]),
                              _flight_rebounds([("s1", 125)]))
    assert out.loc[0, "tag_index_end"] == pytest.approx(0.5)
    assert out.loc[0, "high_side_end_mean"] == pytest.approx(1.75, abs=1e-3)
    assert out.loc[0, "high_side_gain_min"] == pytest.approx(-3.0, abs=1e-3)


# ------------------------------------------------------------- approach_angles: the headline (F6)
#
# The heading is what the finding rests on, so the convention is pinned against geometry a
# reader can check by hand. It is also the reason F6 survives SkillCorner ruling that tracking
# cannot separate a crash from a drift: an angle is a property of a velocity vector, and the
# tests below hold it to exactly that and to nothing more.


def test_zero_is_driving_at_the_rim_ninety_is_across_it_and_one_eighty_is_away():
    assert ATTACKED_HOOP[0] < 0, "the geometry below assumes the attacked rim sits at negative x"
    v = np.zeros((1, 10, 2), np.float32)
    v[0, 0] = (-5.0, 0.0)  # straight at the attacked rim
    v[0, 1] = (0.0, 5.0)   # across it
    v[0, 2] = (5.0, 0.0)   # away from it
    v[0, 3] = (-5.0, 5.0)  # half way between driving at it and running across
    got = approach_angles(_frames(np.zeros((1, 10, 2), np.float32), v=v))["angle"][0]
    assert got[:4] == pytest.approx([0.0, 90.0, 180.0, 45.0], abs=1e-3)


def test_the_heading_is_measured_against_the_direction_to_the_rim_not_a_court_axis():
    """Two players with the SAME velocity vector, on opposite sides of the rim, read opposite."""
    xy = np.zeros((1, 10, 2), np.float32)
    xy[0, 0] = (ATTACKED_HOOP[0], 20.0)
    xy[0, 1] = (ATTACKED_HOOP[0], -20.0)
    v = np.zeros((1, 10, 2), np.float32)
    v[0, :2] = (0.0, -5.0)
    got = approach_angles(_frames(xy, v=v))["angle"][0]
    assert got[0] == pytest.approx(0.0, abs=1e-3)
    assert got[1] == pytest.approx(180.0, abs=1e-3)


def test_the_angle_recovers_the_turn_and_reads_the_same_on_either_side_of_the_rim_line():
    """It is unsigned: a cut 30 deg left of the rim and one 30 deg right are one commitment."""
    turns = np.array([0.0, 30.0, 60.0, 90.0, 120.0, 180.0])
    theta = np.radians(180.0 + np.concatenate([turns, -turns]))  # the rim lies at 180 deg
    v = np.zeros((2 * len(turns), 10, 2), np.float32)
    v[:, 0, 0] = 6.0 * np.cos(theta)
    v[:, 0, 1] = 6.0 * np.sin(theta)
    got = approach_angles(_frames(np.zeros((2 * len(turns), 10, 2), np.float32), v=v))["angle"]
    turned = np.concatenate([turns, turns])
    assert got[:, 0] == pytest.approx(turned, abs=1e-3)

    # The committed band reads the same on both sides too. A heading built exactly ON the bar
    # comes back a ten-thousandth either side of it, so 60 itself is left out of this check.
    committed = (got[:, 0] < COMMITTED_ANGLE_DEG)[turned != COMMITTED_ANGLE_DEG]
    assert committed.tolist() == (turned[turned != COMMITTED_ANGLE_DEG] < 60.0).tolist()


def test_the_angle_is_a_heading_and_does_not_move_with_the_speed():
    v = np.zeros((2, 10, 2), np.float32)
    v[0, 0] = (-2.0, 2.0)
    v[1, 0] = (-20.0, 20.0)  # the same heading, ten times the speed
    kin = approach_angles(_frames(np.zeros((2, 10, 2), np.float32), v=v))
    assert kin["angle"][0, 0] == pytest.approx(kin["angle"][1, 0], abs=1e-3)
    assert kin["speed"][1, 0] == pytest.approx(10.0 * kin["speed"][0, 0], rel=1e-5)


def test_below_the_speed_floor_there_is_no_heading_but_the_speed_and_distance_still_report():
    """The caller counts these rows; reading a near-stationary direction would invent a heading."""
    v = np.zeros((1, 10, 2), np.float32)
    v[0, 0] = (-(MIN_APPROACH_SPEED - 0.5), 0.0)
    v[0, 1] = (-MIN_APPROACH_SPEED, 0.0)  # exactly at the floor, which is kept
    v[0, 2] = (-(MIN_APPROACH_SPEED + 0.5), 0.0)
    kin = approach_angles(_frames(np.zeros((1, 10, 2), np.float32), v=v))
    assert np.isnan(kin["angle"][0, 0])
    assert kin["angle"][0, 1:3] == pytest.approx([0.0, 0.0], abs=1e-3)
    assert np.isnan(kin["angle"][0, 3:]).all()  # the rest are standing still
    assert kin["speed"][0, 0] == pytest.approx(MIN_APPROACH_SPEED - 0.5)
    assert kin["rim_dist"][0, 0] == pytest.approx(abs(ATTACKED_HOOP[0]))


def test_both_teams_are_measured_toward_the_same_rim():
    """All ten slots land in one table, so a defender cannot be read toward their own basket."""
    v = np.zeros((1, 10, 2), np.float32)
    v[0, 0] = v[0, 5] = (-5.0, 0.0)
    got = approach_angles(_frames(np.zeros((1, 10, 2), np.float32), v=v))["angle"][0]
    assert got[5] == pytest.approx(got[0], abs=1e-6)
    assert got[5] == pytest.approx(0.0, abs=1e-3)


def test_the_three_quantities_come_back_together_for_every_slot():
    kin = approach_angles(_frames(np.zeros((7, 10, 2), np.float32)))
    assert set(kin) == {"angle", "speed", "rim_dist"}
    assert all(value.shape == (7, 10) for value in kin.values())


def test_nothing_but_position_and_velocity_reaches_the_answer():
    """The no-intent rule, as a test: the ball, the holder and the matchup cannot enter."""
    xy = np.zeros((1, 10, 2), np.float32)
    xy[0, :, 1] = np.arange(10)  # spread them out, so a matchup would have something to say
    v = np.full((1, 10, 2), 4.0, np.float32)
    plain = _frames(xy, v=v)
    loaded = _frames(xy, v=v, matchup=np.array([[4, 3, 2, 1, 0]], np.int8))
    loaded.ball[:] = 99.0
    loaded.ball_holder[:] = 3
    before, after = approach_angles(plain), approach_angles(loaded)
    for key in before:
        assert before[key] == pytest.approx(after[key], nan_ok=True)


def test_an_empty_frame_set_returns_empty_arrays_rather_than_failing():
    kin = approach_angles(_frames(np.zeros((0, 10, 2), np.float32)))
    assert all(value.shape == (0, 10) for value in kin.values())


def test_a_player_standing_on_the_rim_stays_finite_and_is_marked_by_their_distance():
    """The direction to the rim is meaningless at zero range; rim_dist is what flags the row."""
    xy = np.zeros((1, 10, 2), np.float32)
    xy[0, 0] = ATTACKED_HOOP
    v = np.zeros((1, 10, 2), np.float32)
    v[0, 0] = (-5.0, 0.0)
    kin = approach_angles(_frames(xy, v=v))
    assert kin["rim_dist"][0, 0] == pytest.approx(0.0, abs=1e-4)
    assert np.isfinite(kin["angle"][0, 0])


# ------------------------------------------------------------- the shot-scaled zone (P7.2)
#
# The zone replaces a constant 8 ft band, and its coefficients are frozen. Tests here hold
# the line itself, and hold the table to carrying an unmeasurable rebound through as unknown
# rather than as one that landed outside, which is the difference between 662 rebounds and a
# convenient subset of them.


def _at_rim_distance(feet: float) -> list[float]:
    """An event location exactly `feet` from the attacked rim, straight out from it."""
    return [float(ATTACKED_HOOP[0] + feet), 0.0]


def _zone_shots(rows) -> pd.DataFrame:
    """rows: (id, distance from the rim in feet or None, three)."""
    return pd.DataFrame({
        "id": [r[0] for r in rows],
        "location": [None if r[1] is None else _at_rim_distance(r[1]) for r in rows],
        "three": [r[2] for r in rows],
    })


def _zone_rebounds(rows) -> pd.DataFrame:
    """rows: (id, shotId, distance from the rim in feet or None, defensive)."""
    return pd.DataFrame({
        "id": [r[0] for r in rows],
        "shotId": [r[1] for r in rows],
        "location": [None if r[2] is None else _at_rim_distance(r[2]) for r in rows],
        "defensive": [r[3] for r in rows],
    })


def test_the_zone_is_the_frozen_line_and_a_longer_shot_never_earns_a_smaller_one():
    """D11: these three numbers were committed before a held-out game was read."""
    assert zone_radius(0.0) == pytest.approx(5.40)
    assert zone_radius(8.0) == pytest.approx(6.84)
    assert zone_radius(22.15) == pytest.approx(9.387)
    assert np.all(np.diff(zone_radius(np.linspace(0.0, 30.0, 61))) > 0)


def test_an_unknown_shot_distance_earns_no_zone_rather_than_the_intercept():
    assert np.isnan(zone_radius(np.nan))


def test_the_table_measures_both_distances_from_the_rim_and_scales_the_landing_by_the_zone():
    out = rebound_zone_table(_zone_shots([("s1", 22.0, True)]),
                             _zone_rebounds([("r1", "s1", 6.0, True)]))
    row = out.iloc[0]
    assert row["shot_dist"] == pytest.approx(22.0, abs=1e-6)
    assert row["reb_dist"] == pytest.approx(6.0, abs=1e-6)
    assert row["zone_ft"] == pytest.approx(zone_radius(22.0))
    assert row["zone_ratio"] == pytest.approx(6.0 / zone_radius(22.0), abs=1e-6)
    assert row["in_zone"]


def test_the_same_landing_spot_is_inside_the_zone_of_a_three_and_outside_that_of_a_layup():
    """The whole point of P7.2: seven feet out means different things for different shots."""
    out = rebound_zone_table(
        _zone_shots([("s1", 2.0, False), ("s2", 25.0, True)]),
        _zone_rebounds([("r1", "s1", 7.0, True), ("r2", "s2", 7.0, True)]),
    )
    assert not out.loc[0, "in_zone"]  # the zone of a layup is 5.76 ft
    assert out.loc[1, "in_zone"]      # the zone of a 25 ft shot is 9.90 ft


def test_the_edge_of_the_zone_is_where_the_ratio_crosses_one():
    edge = zone_radius(10.0)
    out = rebound_zone_table(
        _zone_shots([("s1", 10.0, False), ("s2", 10.0, False)]),
        _zone_rebounds([("r1", "s1", edge * 0.999, True), ("r2", "s2", edge * 1.001, True)]),
    )
    assert out.loc[0, "in_zone"] and not out.loc[1, "in_zone"]


def test_a_rebound_with_no_location_is_carried_through_as_unknown_not_as_outside():
    """Counting an unlocated rebound as outside the zone would inflate every share reported."""
    out = rebound_zone_table(_zone_shots([("s1", 10.0, False)]),
                             _zone_rebounds([("r1", "s1", None, True)]))
    assert len(out) == 1
    assert np.isnan(out.loc[0, "reb_dist"])
    assert pd.isna(out.loc[0, "in_zone"])


def test_a_shot_with_no_location_leaves_the_zone_unknown_too():
    out = rebound_zone_table(_zone_shots([("s1", None, False)]),
                             _zone_rebounds([("r1", "s1", 4.0, True)]))
    assert out.loc[0, "reb_dist"] == pytest.approx(4.0, abs=1e-6)
    assert np.isnan(out.loc[0, "zone_ft"])
    assert pd.isna(out.loc[0, "in_zone"])


def test_every_rebound_keeps_its_row_and_its_shot_columns():
    out = rebound_zone_table(
        _zone_shots([("s1", 4.0, False), ("s2", 25.0, True)]),
        _zone_rebounds([("r1", "s1", 3.0, True), ("r2", "s2", 12.0, False),
                        ("r3", "s1", None, True)]),
    )
    assert out["rebound_id"].tolist() == ["r1", "r2", "r3"]
    assert out["shot_id"].tolist() == ["s1", "s2", "s1"]
    assert out["three"].tolist() == [False, True, False]
    assert out["defensive"].tolist() == [True, False, True]


def test_an_empty_rebound_table_returns_an_empty_one_with_the_columns():
    out = rebound_zone_table(_zone_shots([("s1", 4.0, False)]), _zone_rebounds([]))
    assert len(out) == 0
    assert {"reb_dist", "shot_dist", "zone_ft", "zone_ratio", "in_zone"} <= set(out.columns)


# ------------------------------------------------------------------------------ the real data


@pytest.mark.data
@requires_real_dataset
def test_the_layer_builds_on_a_real_game_and_the_tag_index_varies():
    """Lesson 3, as a test: a constant index would make every F5 criterion meaningless."""
    dataset = Dataset(REAL_DATASET_ROOT)
    frames = get_or_build(dataset, 114086, CACHE_DIR)
    events = dataset.events(114086)

    release, missed = release_frames_for(frames, events["shots"])
    table = tag_features(release, missed)
    assert len(table) == 71
    assert table["tag_index"].nunique() >= 4
    assert 0.5 < table["tag_index"].mean() < 0.8


@pytest.mark.data
@requires_real_dataset
def test_the_approach_kinematics_hold_on_a_real_game_and_the_heading_varies():
    """Half a second before each rebound of 114086, a CALIBRATION game and never a held-out one."""
    dataset = Dataset(REAL_DATASET_ROOT)
    frames = get_or_build(dataset, 114086, CACHE_DIR)
    rebounds = dataset.events(114086)["rebounds"]
    rebounds = rebounds[rebounds["frame"].notna()]
    at = at_frames(frames, rebounds["frame"].to_numpy(dtype=np.int64) - APPROACH_LEAD_FRAMES)
    assert len(rebounds) == 63
    assert len(at) == 58, "five rebounds have no cached frame half a second earlier"

    kin = approach_angles(at)
    angle, speed = kin["angle"], kin["speed"]
    assert np.array_equal(np.isnan(angle), speed < MIN_APPROACH_SPEED)
    assert np.isnan(angle).sum() == 113, "113 of the 580 player rows have no usable heading"
    finite = angle[np.isfinite(angle)]
    assert finite.min() >= 0.0 and finite.max() <= 180.0
    # Lesson 3: a quantity that cannot vary cannot carry a finding. This one spreads over the
    # whole range on a real game, and a third of the rows sit inside the committed band.
    assert 0.25 < (finite < COMMITTED_ANGLE_DEG).mean() < 0.45
    assert kin["rim_dist"].max() < 95.0, "the far corner is about 90 ft from this rim"


@pytest.mark.data
@requires_real_dataset
def test_the_shot_scaled_zone_reproduces_finding_three_on_the_calibration_games():
    """Finding 3 had no code behind it until P7.2. This is it, on the calibration half only:
    the held-out half is the script's business and is read once, after the freeze."""
    dataset = Dataset(REAL_DATASET_ROOT)
    table = pd.concat(
        [rebound_zone_table(dataset.events(g)["shots"], dataset.events(g)["rebounds"])
         for g in CALIBRATION_GAMES],
        ignore_index=True,
    )
    assert len(table) == 409, "every rebound of the five games keeps its row"
    assert table["in_zone"].isna().sum() == 84, "67 have no location, 17 more no shot location"
    usable = table.dropna(subset=["reb_dist", "shot_dist"])
    assert len(usable) == 325

    assert usable["reb_dist"].median() == pytest.approx(4.81, abs=0.01)
    rho = spearman(usable["shot_dist"].to_numpy(), usable["reb_dist"].to_numpy())
    assert rho == pytest.approx(0.336, abs=0.001), "the record's +0.336, now reproducible"
    assert usable["in_zone"].mean() == pytest.approx(0.75, abs=0.03)
