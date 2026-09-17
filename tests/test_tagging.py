"""Tests for scbasket.tagging: the derived high-side layer and the transition outcome (F5).

This layer is published as a DEFINITION rather than a detector, because the open bundle
carries no crash or box-out label to check it against. A definition earns trust by being
exact, so the sign convention and the shooter exclusion are pinned against hand-built
geometry where the answer can be read off the coordinates.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import GAME_ID, REAL_DATASET_ROOT, requires_real_dataset

from scbasket.control import ControlParams
from scbasket.court import make_grid
from scbasket.frames import GameFrames, get_or_build
from scbasket.io import Dataset
from scbasket.tagging import (
    DEPTH_CONTROLS,
    OWN_HOOP,
    TAG_FEATURES,
    high_side_distance,
    release_frames_for,
    tag_features,
    transition_outcome,
)
from scbasket.value import surface_from_zones

CACHE_DIR = REAL_DATASET_ROOT.parents[1] / "interim"
GRID = make_grid(2.0)
SHOOTER_ID = 5001


def _frames(xy, chance_idx=None, frame_idx=None, matchup=None) -> GameFrames:
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
        off_ids=np.tile(np.arange(5001, 5006, dtype=np.int32), (n, 1)),
        def_ids=np.tile(np.arange(6001, 6006, dtype=np.int32), (n, 1)),
        xy=xy,
        v=np.zeros((n, 10, 2), np.float32),
        pred_error=np.ones((n, 10), np.float32),
        detected=np.ones((n, 10), bool),
        ball=ball,
        ball_holder=np.zeros(n, np.int8),
        matchup=np.full((n, 5), -1, np.int8) if matchup is None else np.asarray(matchup, np.int8),
    )


def _shots(n: int, shooter: int = SHOOTER_ID) -> pd.DataFrame:
    return pd.DataFrame({"shooterId": [shooter] * n})


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
