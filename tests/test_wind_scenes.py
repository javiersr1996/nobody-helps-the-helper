"""Tests for scripts/wind_scenes.py: the rule that picks a drive, and a scene that must agree
with the published tables or not ship."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from conftest import requires_real_dataset

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from wind_scenes import (  # noqa: E402
    CLEARANCE_QUOTED,
    SCENE_FRAMES,
    TOLERANCE_FT,
    check_scene,
    first_qualifying,
    paired_means,
)

SCENES = ROOT / "reports" / "wind_scenes.json"
HELP_TABLE = ROOT / "reports" / "help_table.csv"
KINDS = ROOT / "reports" / "help_kinds.csv"
SUMMARY = ROOT / "reports" / "help_kinds_summary.csv"
PAIRS = ROOT / "reports" / "near_committed_pairs.csv"
DRIVES = ROOT / "reports" / "near_committed_drives.csv"


def _frames(n: int = 200, undetected: int | None = None, gap_at: int | None = None,
            chance_change_at: int | None = None) -> SimpleNamespace:
    """Just the fields the rule reads: a contiguous run of `n` frames, optionally spoiled."""
    frame_idx = np.arange(n)
    if gap_at is not None:
        frame_idx[gap_at:] += 1
    chance = np.zeros(n, dtype=int)
    if chance_change_at is not None:
        chance[chance_change_at:] = 1
    detected = np.ones((n, 10), dtype=bool)
    if undetected is not None:
        detected[undetected, 3] = False
    return SimpleNamespace(frame_idx=frame_idx, chance_idx=chance, detected=detected)


def _table(*starts: int) -> pd.DataFrame:
    return pd.DataFrame({"drive_id": [f"d{s}" for s in starts], "start_frame": list(starts),
                         "status": "ok", "has_helper": True, "left_slot": 1.0})


def test_the_first_drive_meeting_every_condition_is_chosen():
    row, counts = first_qualifying(_frames(), _table(10, 20))
    assert row["drive_id"] == "d10"
    assert counts["all"] == 2


@pytest.mark.parametrize("spoil", [
    {"undetected": 40},  # one defender undetected on one frame of the window
    {"gap_at": 40},  # a hole in the frame index
    {"chance_change_at": 40},  # the window leaves its chance
])
def test_a_spoiled_window_is_skipped_for_the_next_drive(spoil):
    row, counts = first_qualifying(_frames(**spoil), _table(10, 70))
    assert row["drive_id"] == "d70"
    assert counts["all"] == 1


def test_unhelped_and_no_matchup_drives_are_never_chosen():
    table = _table(10, 20)
    table.loc[0, "has_helper"] = False
    table.loc[1, "left_slot"] = -1.0
    row, counts = first_qualifying(_frames(), table)
    assert row is None
    assert counts["helped"] == 1 and counts["left"] == 1 and counts["all"] == 0


def test_a_window_cut_short_by_the_end_of_the_game_is_skipped():
    row, _ = first_qualifying(_frames(n=100), _table(60))
    assert row is None


@pytest.fixture(scope="module")
def shipped() -> dict:
    return json.loads(SCENES.read_text(encoding="utf-8"))


def _near_row(drive_id: str) -> pd.Series:
    """The row `check_scene` is held to, by a second route: the published `help_table.csv` row
    with `help_kinds.csv`'s nearest, his raw man and `near_move`, and the man's clearance at
    0 and 1.0 s from `near_committed_drives.csv` (rotation's, not `near_committed_table`'s)."""
    row = pd.read_csv(HELP_TABLE).set_index("drive_id").loc[drive_id].copy()
    kind = pd.read_csv(KINDS).set_index("drive_id").loc[drive_id]
    drive = pd.read_csv(DRIVES).set_index("drive_id").loc[drive_id]
    row["helper_def_slot"], row["left_slot"] = kind["near_slot"], kind["near_man"]
    row["helper_help_move"], row["has_helper"] = kind["near_move"], kind["near_committed"]
    row["left_nearest0"], row["left_nearest1"] = drive["left_clear_0"], drive["left_clear_25"]
    return row


@pytest.mark.data
@requires_real_dataset
def test_each_scene_is_a_published_committed_near_help_in_its_roles(shipped):
    kinds = pd.read_csv(KINDS).set_index("drive_id")
    drives = pd.read_csv(DRIVES).set_index("drive_id")
    assert shipped["scenes"]
    for scene in shipped["scenes"]:
        kind, drive = kinds.loc[scene["drive_id"]], drives.loc[scene["drive_id"]]
        xy = np.asarray(scene["xy"])
        roles = scene["roles"]
        assert xy.shape == (SCENE_FRAMES, 10, 2)
        assert bool(kind["near_committed"]) and bool(drive["helped"])
        assert roles["helper"] == 5 + kind["near_slot"] and roles["left"] == kind["near_man"]
        off = (roles["handler_def"] - 5, kind["near_slot"])
        assert sorted(roles["others"]) == [5 + x for x in range(5) if x not in off]
        assert scene["helper_help_move"] == pytest.approx(kind["near_move"], abs=0.01)
        check_scene(scene, _near_row(scene["drive_id"]))  # from the arrays the page would draw
        clear = np.asarray(scene["left_clearance"])
        for t in (0, 25, 38):
            assert clear[t] == pytest.approx(drive[f"left_clear_{t}"], abs=0.01)


@pytest.mark.data
@requires_real_dataset
def test_per_frame_projections_equal_near_committed_pairs_at_25_38_50(shipped):
    pairs = pd.read_csv(PAIRS)
    for scene in shipped["scenes"]:
        mine = pairs[pairs["drive_id"] == scene["drive_id"]]
        assert len(mine) == 9  # three others x three horizons
        for i, slot in enumerate(scene["roles"]["others"]):
            for horizon in (25, 38, 50):
                want = mine[(mine["def_slot"] == slot - 5) & (mine["horizon"] == horizon)].iloc[0]
                assert scene["to_left"][i][horizon] == pytest.approx(want["to_left"], abs=0.01)
                assert scene["placebo"][i][horizon] == pytest.approx(want["placebo"], abs=0.01)


@pytest.mark.data
@requires_real_dataset
def test_the_percentile_places_the_scene_among_all_committed_near_helps(shipped):
    distribution = paired_means(pd.read_csv(PAIRS))
    summary = pd.read_csv(SUMMARY)
    n = summary[(summary["measure"] == "paired_diff") & (summary["kind"] == "near_committed")
                & (summary["horizon"] == 1.52)]["n"]
    assert len(distribution) == int(n.iloc[0])  # the n of the thesis, 159 when written
    for scene in shipped["scenes"]:
        mine = distribution.loc[scene["drive_id"]]
        assert scene["paired_mean_1_5s"] == pytest.approx(mine, abs=0.01)
        placed = scene["paired_mean_1_5s_among_helped"]
        assert placed["n_helped"] == len(distribution)
        assert placed["percentile"] == pytest.approx(100 * (distribution <= mine).mean(), abs=0.5)
        assert [f"{t / 25:.1f}s" for t in CLEARANCE_QUOTED] == list(scene["clearance_ft"])


@pytest.mark.data
@requires_real_dataset
def test_a_scene_that_disagrees_with_the_table_is_refused(shipped):
    row = _near_row(shipped["scenes"][0]["drive_id"])
    scene = copy.deepcopy(shipped["scenes"][0])
    check_scene(scene, row)  # the untouched scene passes: the refusal below is not a default
    helper, handler = scene["roles"]["helper"], scene["roles"]["handler"]
    xy = np.asarray(scene["xy"])
    for t in range(1, 26):  # 0.5 ft toward the handler on every frame of the first second
        away = xy[t, handler] - xy[t, helper]
        xy[t, helper] += 0.5 * away / np.linalg.norm(away)
    scene["xy"] = xy.tolist()
    assert 0.5 > TOLERANCE_FT
    with pytest.raises(ValueError, match="helper_help_move"):
        check_scene(scene, row)


@pytest.mark.data
@requires_real_dataset
def test_a_scene_whose_helper_is_back_with_his_man_is_refused(shipped):
    row = _near_row(shipped["scenes"][0]["drive_id"])
    scene = copy.deepcopy(shipped["scenes"][0])
    xy = np.asarray(scene["xy"])
    xy[50, scene["roles"]["helper"]] = xy[50, scene["roles"]["left"]]  # on his man at 2.0 s
    scene["xy"] = xy.tolist()
    with pytest.raises(ValueError, match="back with his man"):
        check_scene(scene, row)
