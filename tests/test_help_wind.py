"""Tests for scripts/help_wind.py: the helper rate per off-ball defender, and its standardisation.

The scene is built so the answer can be read off the counts: two groups of defenders start in
different places, and whether a defender is the helper depends ONLY on his stratum (near or
far from where the ball goes), at the same rate in both groups. The raw rates differ by group;
standardised by the stratum, both ratios must be exactly 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from help_wind import helper_flags, helper_rate  # noqa: E402

# Two kinds of drive, 40 each, four off-ball defenders per drive as (group, stratum). The
# perimeter group stands mostly near, the inside group mostly far. Per stratum the helper rate
# is the same in both groups: near 20/80 and 10/40 = 0.25, far 4/40 and 16/160 = 0.1.
KIND_1 = [("perimeter", "near"), ("perimeter", "near"), ("perimeter", "far"), ("inside", "far")]
KIND_2 = [("inside", "near"), ("inside", "far"), ("inside", "far"), ("inside", "far")]
HELPERS_1 = [0] * 20 + [2] * 4 + [3] * 4 + [None] * 12  # which slot is the helper, per drive
HELPERS_2 = [0] * 10 + [1] * 12 + [None] * 18


def _vectors() -> pd.DataFrame:
    rows = []
    for kind, members, helpers in (("a", KIND_1, HELPERS_1), ("b", KIND_2, HELPERS_2)):
        for i, helper in enumerate(helpers):
            for slot, (group, stratum) in enumerate(members):
                rows.append({"drive_id": f"{kind}{i}", "def_slot": slot, "group": group,
                             "stratum": stratum, "help_move": 5.0 if slot == helper else 1.0})
    return pd.DataFrame(rows)


def test_the_helper_is_each_drives_largest_mover_and_only_past_the_threshold():
    vectors = pd.DataFrame({
        "drive_id": ["x"] * 4 + ["y"] * 4,
        "help_move": [1.0, 5.0, 2.0, -1.0, 3.5, 0.0, 3.5, 1.0],
    })
    assert helper_flags(vectors, 4.0).tolist() == [False, True] + [False] * 6
    # at 3 ft drive y has one too, and only the first of its tied movers
    assert helper_flags(vectors, 3.0).tolist() == [False, True, False, False,
                                                   True, False, False, False]


def test_rates_count_defenders_and_helpers_per_group():
    out = helper_rate(_vectors(), "group", 4.0, draws=200).set_index("group")
    assert out.loc["perimeter", "n_defenders"] == 120 and out.loc["inside", "n_defenders"] == 200
    assert out.loc["perimeter", "n_helpers"] == 24 and out.loc["inside", "n_helpers"] == 26
    assert out.loc["perimeter", "rate"] == pytest.approx(0.2)
    assert out.loc["inside", "rate"] == pytest.approx(0.13)
    assert out["defender_share"].sum() == pytest.approx(1.0)
    assert out["helper_share"].sum() == pytest.approx(1.0)
    assert (out["rate_low"] <= out["rate"]).all() and (out["rate"] <= out["rate_high"]).all()


def test_a_group_that_helps_only_as_its_stratum_says_reads_a_ratio_of_one():
    vectors = _vectors()
    standardised = helper_rate(vectors, "group", 4.0, ["stratum"], draws=200).set_index("group")
    assert standardised.loc["perimeter", "expected"] == pytest.approx(80 * 0.25 + 40 * 0.1)
    assert standardised.loc["inside", "expected"] == pytest.approx(40 * 0.25 + 160 * 0.1)
    assert standardised["ratio"].tolist() == pytest.approx([1.0, 1.0])
    assert (standardised["ratio_low"] <= 1.0).all() and (standardised["ratio_high"] >= 1.0).all()
    # Unstandardised, the same scene reads a perimeter excess: the stratum is what removes it.
    raw = helper_rate(vectors, "group", 4.0, draws=200).set_index("group")
    assert raw.loc["perimeter", "ratio"] == pytest.approx(0.2 / (50 / 320))
    assert raw.loc["inside", "ratio"] == pytest.approx(0.13 / (50 / 320))
