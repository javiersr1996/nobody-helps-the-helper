"""Tests for scripts/wind_video.py (D2): the cut's scene windows come from the script and add up
to a minute, and a number typed on a slide must be a cell of its CSV. Each guard is shown failing
on a spoiled input, because a check that cannot fail has checked nothing (lesson 4)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from wind_video import (  # noqa: E402
    SCRIPT,
    caption_cells,
    caption_text,
    check_slide_numbers,
    crop_index,
    parse_script,
    plan_crops,
)

TEXT = SCRIPT.read_text(encoding="utf-8")


def test_real_script_windows_are_contiguous_and_a_minute() -> None:
    scenes = parse_script(TEXT)
    assert [s.n for s in scenes] == [1, 2, 3, 4, 5, 6]
    assert scenes[0].start == 0
    assert all(a.end == b.start for a, b in zip(scenes, scenes[1:], strict=False))
    assert 59 <= scenes[-1].end <= 60
    assert all(s.line for s in scenes)


def test_a_gap_between_windows_is_refused() -> None:
    spoiled = TEXT.replace("[0:06-0:13]", "[0:07-0:13]")
    assert spoiled != TEXT
    with pytest.raises(ValueError, match="starts at 7"):
        parse_script(spoiled)


def test_a_cut_of_the_wrong_length_is_refused() -> None:
    spoiled = TEXT.replace("[0:51-1:00]", "[0:51-1:20]")
    assert spoiled != TEXT
    with pytest.raises(ValueError, match="add up to 80"):
        parse_script(spoiled)


def test_caption_numbers_are_cells_of_the_csv() -> None:
    text = caption_text()
    assert check_slide_numbers(text, caption_cells()) == ["246", "618", "-0.22", "-0.58", "0.13"]


@pytest.mark.parametrize(
    "bad", ["247 of 618 drives", "246 of 618 drives, -0.23 ft", "CI -0.58 to +0.30"]
)
def test_a_number_not_in_the_csv_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="no cell"):
        check_slide_numbers(bad, caption_cells())


def test_the_old_61_second_headers_are_refused() -> None:
    spoiled = TEXT.replace("[0:51-1:00]", "[0:51-1:01]")
    assert spoiled != TEXT
    with pytest.raises(ValueError, match="add up to 61"):
        parse_script(spoiled)


def test_scene_5_cuts_from_the_court_panel_to_the_intervals() -> None:
    assert crop_index(0.0) == 0
    assert crop_index(6.5) == 0
    assert crop_index(6.6) == 1


def test_crops_contain_what_they_must_and_never_zoom_past_2x() -> None:
    boxes = [(800.0, 300.0, 1100.0, 600.0)] * 40 + [(100.0, 200.0, 1700.0, 1000.0)] * 40
    crops = plan_crops(boxes)
    assert (1920 / crops[:, 2]).max() <= 2.0 + 1e-9
    for (x0, y0, w), b in zip(crops, boxes, strict=True):
        h = w * 9 / 16
        assert x0 <= b[0] and y0 <= b[1] and x0 + w >= b[2] and y0 + h >= b[3]
        assert x0 >= -1e-6 and y0 >= -1e-6 and x0 + w <= 1920 + 1e-6 and y0 + h <= 1080 + 1e-6
    assert (crops[1:, 2] - crops[:-1, 2]).max() < 60  # no jump when the need changes


def test_the_caption_follows_the_csv_and_a_stale_one_is_refused(tmp_path, monkeypatch) -> None:
    import pandas as pd
    import wind_video

    real = caption_text()
    df = pd.read_csv(wind_video.SUMMARY)
    row = (df.measure == "paired_diff") & (df.kind == "near_committed") & (df.variant == "primary")
    df.loc[row & (df.horizon.round(2) == 1.52), "mean"] += 0.5
    spoiled = tmp_path / "help_kinds_summary.csv"
    df.to_csv(spoiled, index=False)
    monkeypatch.setattr(wind_video, "SUMMARY", spoiled)
    assert caption_text() != real  # the bar reads the file
    with pytest.raises(ValueError, match="no cell"):
        check_slide_numbers(real, caption_cells())  # and the old text no longer matches it
