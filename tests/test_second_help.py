"""Tests for scripts/second_help.py: the helped minus no-helper contrast of the paired mean."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from second_help import contrast  # noqa: E402


def _pairs(helped_diff: float, base_diff: float, n: int = 40) -> pd.DataFrame:
    """`n` drives per group, three defenders each, every pair's difference fixed per group."""
    rows = []
    for helped, diff in ((True, helped_diff), (False, base_diff)):
        for i in range(n):
            for slot in range(3):
                rows.append({"drive_id": f"{helped}-{i}", "helped": helped, "horizon": 38,
                             "def_slot": slot, "to_left": diff, "placebo": 0.0})
    return pd.DataFrame(rows)


def test_two_groups_built_with_a_known_difference_give_that_difference():
    out = contrast(_pairs(-0.7, -0.5), 38)
    assert out["contrast_mean"] == pytest.approx(-0.2)
    assert out["contrast_ci_low"] == pytest.approx(-0.2) == out["contrast_ci_high"]  # no spread
    assert out["n_helped"] == out["n_no_helper"] == 40


def test_the_interval_has_width_when_the_drives_differ_and_holds_the_contrast():
    rng = np.random.default_rng(1)
    pairs = _pairs(0.0, 0.0)
    pairs["to_left"] = rng.normal(0.0, 1.0, len(pairs))
    pairs.loc[pairs["helped"], "to_left"] -= 1.0  # helped drives sit 1 ft lower
    out = contrast(pairs, 38)
    assert out["contrast_ci_low"] < out["contrast_mean"] < out["contrast_ci_high"]
    assert out["contrast_mean"] == pytest.approx(-1.0, abs=0.35)
    assert out["contrast_ci_high"] < 0  # the shift is large against the noise: zero is out
