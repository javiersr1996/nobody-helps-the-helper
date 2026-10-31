"""Tests for scripts/near_robustness.py: the classes it regroups by, its bootstrap against
`second_help`'s, the post-pass measure of 13 a2, and the shipped CSVs against their readings."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from near_robustness import (  # noqa: E402
    PASS_FRAMES,
    PASS_MIN_N,
    a2_reading,
    after_pass,
    committed,
    reference,
    two_sample,
)
from second_help import contrast  # noqa: E402

REPORTS = ROOT / "reports"


def test_committed_reads_the_start_spot_and_the_old_split_reads_where_the_man_is():
    df = pd.DataFrame({"near_move": [3.0, 3.0, 0.5], "near_dist0": [2.0, 2.0, 2.0],
                       "near_dist2_start": [6.0, 2.5, 2.0], "near_dist2_man": [2.5, 6.0, 2.0]})
    assert committed(df).tolist() == [True, False, False]
    assert committed(df, endpos=True).tolist() == [False, True, False]
    assert reference(df).tolist() == [False, False, True]
    assert committed(df, step=3.5).tolist() == [False, False, False]


def test_the_two_sample_interval_is_second_helps_contrast():
    rng = np.random.default_rng(1)
    rows = [{"drive_id": f"d{i:03d}", "helped": i < 30, "horizon": 38, "def_slot": s,
             "to_left": float(rng.normal()), "placebo": float(rng.normal())}
            for i in range(70) for s in range(3)]
    pairs = pd.DataFrame(rows)
    want = contrast(pairs, 38)
    per = (pairs["to_left"] - pairs["placebo"]).groupby([pairs["helped"], pairs["drive_id"]]).mean()
    low, high = two_sample(per.loc[True].to_numpy(), per.loc[False].to_numpy())
    assert (low, high) == pytest.approx((want["contrast_ci_low"], want["contrast_ci_high"]))


def test_after_the_pass_a_defender_running_at_the_man_left_reads_his_run_minus_the_placebo():
    # attackers 0-4 (0 the handler, 1 the man left), defenders 5-9; defender slot 2 runs 5 ft
    # straight at where attacker 1 is 1.0 s after the release; his own man (2) is not a target
    n = 40
    xy = np.zeros((n, 10, 2))
    xy[:, :5] = [[0, 0], [10, 0], [0, 10], [0, -10], [-10, 0]]
    xy[:, 5:] = [[1, 1], [8, 2], [0, 12], [1, -9], [-9, 1]]
    rp = 5
    start = xy[rp, 7].copy()
    goal = xy[rp + PASS_FRAMES, 1]
    xy[rp + PASS_FRAMES:, 7] = start + 5.0 * (goal - start) / np.linalg.norm(goal - start)
    raw = np.arange(5)
    v = after_pass(xy, rp, [2, 3], 1, 0, raw)
    p1 = xy[rp + PASS_FRAMES, 7]
    placebo = np.mean([(p1 - start) @ (xy[rp, a] - start) / np.linalg.norm(xy[rp, a] - start)
                       for a in (3, 4)])
    assert v[2] == pytest.approx(5.0 - placebo, abs=1e-9)
    assert v[3] == pytest.approx(0.0, abs=1e-12)


def test_the_readings_of_13_a2_follow_the_rule_fixed_before_the_run():
    assert a2_reading(0.01) == "ROTATION" and a2_reading(0.0) == "ABSENCE"
    rot = pd.read_csv(REPORTS / "near_rotator.csv")
    head = rot[(rot["group"] == "committed") & np.isclose(rot["horizon"], 1.52)]
    assert sorted(head["rotator"]) == ["R1", "R2"]
    for r in head.itertuples():
        assert r.reading == a2_reading(r.ci_low)
    passed = pd.read_csv(REPORTS / "near_pass.csv")
    after = passed[(passed["measure"] == "after_pass") & (passed["group"] == "committed")]
    for r in after.itertuples():
        assert r.reading == ("LIMIT" if r.n < PASS_MIN_N else a2_reading(r.ci_low))


def test_the_primary_rows_equal_help_kinds_summary():
    robust = pd.read_csv(REPORTS / "near_robustness.csv")
    summary = pd.read_csv(REPORTS / "help_kinds_summary.csv")
    for r in robust[robust["check"] == "primary"].itertuples():
        kind = "near_committed_ref" if r.group == "reference" else "near_committed"
        measure = "contrast" if r.group == "contrast" else "paired_diff"
        want = summary[(summary["measure"] == measure) & (summary["kind"] == kind)
                       & np.isclose(summary["horizon"], r.horizon)].iloc[0]
        assert (r.n, r.mean, r.ci_high) == pytest.approx((want["n"], want["mean"], want["ci_high"]))
