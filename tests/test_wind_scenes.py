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
PAIRS = ROOT / "reports" / "second_help_pairs.csv"


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


@pytest.mark.data
@requires_real_dataset
def test_each_scene_reproduces_the_published_help_table(shipped):
    table = pd.read_csv(HELP_TABLE).set_index("drive_id")
    assert shipped["scenes"]
    for scene in shipped["scenes"]:
        row = table.loc[scene["drive_id"]]
        xy = np.asarray(scene["xy"])
        roles = scene["roles"]
        assert xy.shape == (SCENE_FRAMES, 10, 2)
        assert scene["helper_help_move"] == pytest.approx(row["helper_help_move"], abs=0.01)
        assert bool(row["has_helper"])
        check_scene(scene, row)  # recomputed from the arrays the page would draw
        clear = np.asarray(scene["left_clearance"])
        assert clear[0] == pytest.approx(row["left_nearest0"], abs=0.01)
        assert clear[25] == pytest.approx(row["left_nearest1"], abs=0.01)
        assert row["left_slot"] == roles["left"]


@pytest.mark.data
@requires_real_dataset
def test_per_frame_projections_equal_second_help_pairs_at_25_38_50(shipped):
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
def test_the_percentile_places_the_scene_among_all_helped_drives(shipped):
    distribution = paired_means(pd.read_csv(PAIRS))
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
    row = pd.read_csv(HELP_TABLE).set_index("drive_id").loc[shipped["scenes"][0]["drive_id"]]
    scene = copy.deepcopy(shipped["scenes"][0])
    check_scene(scene, row)  # the untouched scene passes: the refusal below is not a default
    helper = scene["roles"]["helper"]
    handler = np.asarray(scene["xy"])[25, scene["roles"]["handler"]]
    xy = np.asarray(scene["xy"])
    away = handler - xy[25, helper]
    xy[25, helper] += 0.5 * away / np.linalg.norm(away)  # 0.5 ft toward the handler at 1.0 s
    scene["xy"] = xy.tolist()
    assert 0.5 > TOLERANCE_FT
    with pytest.raises(ValueError, match="helper_help_move"):
        check_scene(scene, row)
