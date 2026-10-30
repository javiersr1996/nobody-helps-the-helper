"""Tests for scripts/matchup_check.py: the corroborated subsets are nested and S3 cuts at 10 ft."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from matchup_check import subset_flags  # noqa: E402


def test_subsets_are_nested_and_the_last_cuts_at_ten_feet():
    assert subset_flags(False, True, 2.0) == {"S0": True, "S1": False, "S2": False, "S3": False}
    assert subset_flags(True, False, 2.0) == {"S0": True, "S1": True, "S2": False, "S3": False}
    assert subset_flags(True, True, 10.0) == {"S0": True, "S1": True, "S2": True, "S3": True}
    assert subset_flags(True, True, 10.01) == {"S0": True, "S1": True, "S2": True, "S3": False}
