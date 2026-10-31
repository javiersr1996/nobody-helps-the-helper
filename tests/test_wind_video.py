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
    pan_offset,
    parse_script,
)

TEXT = SCRIPT.read_text(encoding="utf-8")


def test_real_script_windows_are_contiguous_and_a_minute() -> None:
    scenes = parse_script(TEXT)
    assert [s.n for s in scenes] == [1, 2, 3, 4, 5, 6]
    assert scenes[0].start == 0
    assert all(a.end == b.start for a, b in zip(scenes, scenes[1:], strict=False))
    assert abs(scenes[-1].end - 60) <= 1
    assert all(s.line for s in scenes)


def test_a_gap_between_windows_is_refused() -> None:
    spoiled = TEXT.replace("[0:06-0:15]", "[0:07-0:15]")
    assert spoiled != TEXT
    with pytest.raises(ValueError, match="starts at 7"):
        parse_script(spoiled)


def test_a_cut_of_the_wrong_length_is_refused() -> None:
    spoiled = TEXT.replace("[0:52-1:01]", "[0:52-1:20]")
    assert spoiled != TEXT
    with pytest.raises(ValueError, match="add up to 80"):
        parse_script(spoiled)


def test_caption_numbers_are_cells_of_the_csv() -> None:
    text = caption_text()
    assert check_slide_numbers(text, caption_cells()) == ["159", "618", "-0.63", "-1.25", "-0.03"]


@pytest.mark.parametrize(
    "bad", ["160 of 618 drives", "159 of 618 drives, -0.64 ft", "CI -1.25 to -0.30"]
)
def test_a_number_not_in_the_csv_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="no cell"):
        check_slide_numbers(bad, caption_cells())


def test_pan_ends_where_the_figure_does() -> None:
    assert pan_offset(0) == 0
    assert pan_offset(21) == 2678 - 990
