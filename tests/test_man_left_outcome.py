"""Tests for scripts/man_left_outcome.py: the release window, the shot after the catch, the
clearance at a frame, the cluster bootstrap, the per-attacker rows, and the shipped CSVs."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from man_left_outcome import (  # noqa: E402
    QUANTITIES,
    SHOT_FRAMES,
    STEP_WINDOW_FRAMES,
    WINDOWS,
    at_frame,
    cluster_ci,
    first_catch,
    outcome_rows,
    shot_after,
    step_frame,
)
from second_help import bootstrap_ci  # noqa: E402

from scbasket.help_kinds import OUTCOME_FRAMES  # noqa: E402

REPORTS = ROOT / "reports"
START = 1000


def _passes(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["chanceId", "receiverId", "complete", "startFrame",
                                       "endFrame"])


def test_the_primary_window_opens_after_the_splits_last_frame():
    assert WINDOWS["primary"][0] == OUTCOME_FRAMES  # the split reads the helper until 2.0 s


def test_first_catch_takes_the_first_complete_pass_to_him_released_inside_the_window():
    window = WINDOWS["primary"]
    lo, hi = START + window[0], START + window[1]
    p = _passes([
        ("c1", 7, True, lo, lo + 8),            # released on the split's last frame: out
        ("c1", 7, False, lo + 2, lo + 9),       # incomplete: out
        ("c1", 8, True, lo + 3, lo + 9),        # to someone else: out
        ("c2", 7, True, lo + 4, lo + 9),        # another chance: out
        ("c1", 7, True, lo + 20, lo + 30),      # the second one in: not first
        ("c1", 7, True, lo + 1, lo + 10),       # the first one in
        ("c1", 7, True, hi + 1, hi + 9),        # after the window: out
    ])
    assert first_catch(p, "c1", 7, START, window) == (lo + 1, lo + 10)
    assert first_catch(p.iloc[[0, 1, 2, 3, 6]], "c1", 7, START, window) is None
    last = _passes([("c1", 7, True, hi, hi + 5)])
    assert first_catch(last, "c1", 7, START, window) == (hi, hi + 5)
    # the naive window sees the pass on the split's last frame
    assert first_catch(p.iloc[[0]], "c1", 7, START, WINDOWS["from_start"]) == (lo, lo + 8)


def test_a_shot_counts_from_the_catch_to_two_seconds_after_by_him_in_the_chance():
    catch = 1100
    shots = pd.DataFrame({"chanceId": ["c1", "c1", "c2", "c1"],
                          "shooterId": [7, 8, 7, 7],
                          "startFrame": [catch - 1, catch + 3, catch + 3, catch + SHOT_FRAMES + 1]})
    assert not shot_after(shots, "c1", 7, catch)
    on_time = pd.concat([shots, pd.DataFrame({"chanceId": ["c1"], "shooterId": [7],
                                              "startFrame": [catch + SHOT_FRAMES]})])
    assert shot_after(on_time, "c1", 7, catch)


def _frames(n: int = 200) -> SimpleNamespace:
    """Five attackers on a line, their defenders 2, 4, 6, 8, 10 ft away; the ball at slot 2."""
    xy = np.zeros((n, 10, 2), np.float32)
    xy[:, :5, 0] = [0, 20, 40, 60, 80]
    xy[:, 5:, 0] = xy[:, :5, 0]
    xy[:, 5:, 1] = [2, 4, 6, 8, 10]
    ball = np.zeros((n, 3), np.float32)
    ball[:, 0], ball[:, 1] = 40.0, 3.0
    return SimpleNamespace(frame_idx=np.arange(START, START + n),
                           off_ids=np.tile(np.array([11, 12, 13, 14, 15]), (n, 1)),
                           xy=xy, ball=ball)


def test_at_frame_reads_his_nearest_defender_and_the_ball_and_nan_off_the_cache():
    frames = _frames()
    assert at_frame(frames, START + 10, 13) == pytest.approx((6.0, 3.0))
    assert at_frame(frames, START + 10, 15) == pytest.approx((10.0, np.hypot(40.0, 3.0)))
    assert np.isnan(at_frame(frames, START - 1, 13)).all()
    assert np.isnan(at_frame(frames, START + 10, 99)).all()


def test_outcome_rows_name_the_man_drop_the_handler_and_read_each_window():
    frames = _frames()
    frames.xy[1:, 7, 0] = 37.0  # the nearest (defender slot 2) steps 3 ft toward the handler
    kinds = pd.DataFrame({"drive_id": ["d1"], "game": [1], "start_frame": [START],
                          "handler_slot": [0], "near_slot": [2], "near_man": [2],
                          "near_committed": [True], "near_stunt": [False], "near_ref": [False]})
    events = {
        "drives": pd.DataFrame({"id": ["d1"], "chanceId": ["c1"]}),
        "passes": _passes([("c1", 12, True, START + 40, START + 45),    # before 2.0 s
                           ("c1", 13, True, START + 60, START + 70)]),  # the man, at 2.4 s
        "shots": pd.DataFrame({"chanceId": ["c1"], "shooterId": [13],
                               "startFrame": [START + 90]}),
    }
    rows = pd.DataFrame(outcome_rows(frames, events, kinds)).set_index("attacker_id")
    assert sorted(rows.index) == [12, 13, 14, 15]
    assert rows.loc[13, "role"] == "man" and (rows.drop(13)["role"] == "placebo").all()
    assert (rows["group"] == "committed").all()
    man = rows.loc[13]
    assert (man["reached_primary"], man["shot_primary"], man["shot_any_primary"]) == (1, 1, 1)
    assert man["release_s_primary"] == pytest.approx(60 / 25)
    assert man["catch_s_primary"] == pytest.approx(70 / 25)
    assert (man["clear_primary"], man["open_primary"]) == pytest.approx((np.hypot(3, 6), 1.0))
    assert man["ball_catch_primary"] == pytest.approx(3.0)
    early = rows.loc[12]
    assert (early["reached_primary"], early["reached_from_start"]) == (0, 1)
    assert np.isnan(early["clear_primary"]) and early["shot_any_primary"] == 0
    assert early["clear_from_start"] == pytest.approx(4.0)
    assert early["shot_from_start"] == 0
    # the step window opens at the step (frame 1): it sees the pass at 1.6 s; so does `early`
    assert man["step_s"] == pytest.approx(1 / 25) and not man["step_matched"]
    assert (early["reached_step"], early["reached_early"], man["reached_early"]) == (1, 1, 0)


def test_step_frame_is_the_first_frame_the_projection_reaches_the_step():
    xy = np.zeros((40, 10, 2))
    xy[:, 0] = [10.0, 0.0]                      # the handler stands still
    xy[:, 5 + 2] = [0.0, 0.0]                   # defender slot 2 starts 10 ft away
    xy[7:, 5 + 2] = [1.0, 0.0]                  # 1 ft at frame 7: not yet
    xy[12:, 5 + 2] = [2.0, 0.0]                 # 2 ft at frame 12: the step
    xy[20:, 5 + 2] = [5.0, 0.0]
    assert step_frame(xy, 0, 2, 0) == 12
    xy[12:, 5 + 2] = [1.5, 0.0]
    xy[20:, 5 + 2] = [1.5, 0.0]
    assert step_frame(xy, 0, 2, 0) == -1        # never 2 ft within 1.0 s


def test_a_stays_home_drive_opens_its_step_window_at_its_games_median_step():
    frames = _frames()
    frames.xy[3:, 7, 0] = 37.0     # drive a: the nearest steps at frame 3
    frames.xy[110:, 7, 0] = 37.0   # (drive b starts at frame 100: steps at frame 10)
    frames.xy[100:110, 7, 0] = 40.0
    kinds = pd.DataFrame({
        "drive_id": ["a", "b", "r"], "game": [1, 1, 1], "start_frame": [START, START + 100,
                                                                         START + 150],
        "handler_slot": [0, 0, 0], "near_slot": [2, 2, 2], "near_man": [2, 2, 2],
        "near_committed": [True, False, False], "near_stunt": [False, True, False],
        "near_ref": [False, False, True]})
    frames.xy[150:, 7, 0] = 40.0   # r: the nearest stays home
    events = {"drives": pd.DataFrame({"id": ["a", "b", "r"], "chanceId": ["c1", "c2", "c3"]}),
              "passes": _passes([("c3", 13, True, START + 150 + 5, START + 150 + 9)]),
              "shots": pd.DataFrame({"chanceId": [], "shooterId": [], "startFrame": []})}
    rows = pd.DataFrame(outcome_rows(frames, events, kinds))
    man = rows[rows["role"] == "man"].set_index("drive_id")
    assert man["group"].to_dict() == {"a": "committed", "b": "recovered", "r": "reference"}
    assert man["step_s"].to_dict() == pytest.approx({"a": 3 / 25, "b": 10 / 25, "r": 6 / 25})
    assert man["step_matched"].to_dict() == {"a": False, "b": False, "r": True}
    # r's window opens at frame 6 (the median of 3 and 10, rounded down): a pass at 5 is out
    assert man.loc["r", "reached_step"] == 0 and man.loc["r", "reached_early"] == 1
    assert STEP_WINDOW_FRAMES == 75


def test_cluster_ci_with_one_value_per_cluster_is_second_helps_drive_bootstrap():
    rng = np.random.default_rng(3)
    v = rng.normal(size=60)
    out = cluster_ci(v, np.arange(60), np.ones(60, bool), np.zeros(60, bool))
    assert (out["ci_low_a"], out["ci_high_a"]) == pytest.approx(bootstrap_ci(v))
    assert out["n_a"] == 60 and out["n_b"] == 0 and np.isnan(out["mean_b"])


def test_cluster_ci_leaves_nan_out_and_separates_groups_exactly():
    clusters = np.repeat(np.arange(10), 4)
    a = np.tile([True, True, False, False], 10)
    v = np.where(a, 1.0, 0.0)
    v[0] = np.nan
    out = cluster_ci(v, clusters, a, ~a)
    assert (out["n_a"], out["n_b"]) == (19, 20)
    assert (out["mean_a"], out["mean_b"], out["diff"]) == (1.0, 0.0, 1.0)
    assert (out["ci_low_diff"], out["ci_high_diff"]) == (1.0, 1.0)


def _shipped() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows_path = REPORTS / "man_left_outcome.csv"
    summary_path = REPORTS / "man_left_outcome_summary.csv"
    if not (rows_path.exists() and summary_path.exists()):
        pytest.skip("man_left_outcome CSVs not written yet")
    return pd.read_csv(rows_path), pd.read_csv(summary_path)


def test_the_shipped_groups_are_the_headlines_split():
    rows, summary = _shipped()
    counts = pd.read_csv(REPORTS / "help_kinds_summary.csv")
    flags = counts[(counts["measure"] == "count") & (counts["kind"] == "flag")]
    want = dict(zip(flags["variant"], flags["n"], strict=True))
    reached = summary[(summary["comparison"] == "committed_vs_reference")
                      & (summary["quantity"] == "reached")]
    assert (reached["n_a"] == want["near_committed"]).all()
    assert (reached["n_b"] == want["near_ref"]).all()
    assert (rows.groupby("drive_id")["role"].apply(lambda r: (r == "man").sum()) == 1).all()


def test_the_shipped_summary_means_are_the_rows_means():
    rows, summary = _shipped()
    for s in summary.itertuples(index=False):
        col = f"{QUANTITIES[s.quantity]}_{s.window}"
        for side, mean in ((s.a, s.mean_a), (s.b, s.mean_b)):
            groups, role = side.rsplit("_", 1)
            v = rows[rows["group"].isin(groups.split("+")) & (rows["role"] == role)][col].dropna()
            assert v.mean() == pytest.approx(mean, nan_ok=True), (s.comparison, col, side)
