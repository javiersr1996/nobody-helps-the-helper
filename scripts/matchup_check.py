"""Do the provider's matchups hold up, and does the absence of a second help survive them?

Usage: uv run python scripts/matchup_check.py [--root DIR] [--cache DIR] [--out DIR]

The measure of the entry rests on the provider's `matchups` table: who guards the ball handler
and which attacker the helper marked (the man left). There is no video in the open data, so
the table was never checked against ground truth. If it were wrong, the man left would often
be the wrong attacker, and the paired difference would be pushed toward the claimed absence.

Two things are done, both on the resolved drives, both in process (like second_help.py):

  1. Coherence at the start frame: how often the handler's defender is assigned, equals the
     nearest defender, equals the provider's own `drives.ballhandlerDefId`; whether a defender
     is ever assigned twice; and how often the helper is the defender nearest to the man he
     leaves. This is consistency, not validation.
  2. The second-help contrast re-run on nested subsets where the matchup is corroborated:
       S0  every resolved drive with a man left (must equal second_help_summary.csv)
       S1  S0 and the handler's matchup defender is both the nearest defender and the
           provider's `ballhandlerDefId`
       S2  S1 and the helper is the defender nearest to the man left at the start
       S3  S2 and the helper starts within 10 ft of the man left

Reading, fixed before the run: HOLDS if every corroborated subset's helped-minus-unhelped CI
contains zero and the helped mean stays at or below zero; FAILS if a contrast CI lies above
zero or the helped mean rises monotonically as the corroboration tightens.

Writes to {out}:
  matchup_coherence.csv            metric, n, of: the counts of step 1
  second_help_matchup_check.csv    subset x horizon x series (helped, unhelped, contrast)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from second_help import BOOTSTRAP_DRAWS, DATA, INTERIM, REPORTS, contrast, summarise

from scbasket.frames import N_SIDE, get_or_build, nearest_defenders
from scbasket.io import Dataset
from scbasket.rotation import ROTATION_HORIZONS, rotation_table
from scbasket.wind import FPS, HELP_FT, _row_of, help_table

SUBSETS = ("S0", "S1", "S2", "S3")
NEAR_LEFT_FT = 10.0


def subset_flags(handler_ok: bool, helper_nearest: bool, helper_dist: float) -> dict[str, bool]:
    """Membership of one drive in the nested subsets S0 to S3."""
    s1 = handler_ok
    s2 = s1 and helper_nearest
    return {"S0": True, "S1": s1, "S2": s2, "S3": s2 and helper_dist <= NEAR_LEFT_FT}


def drive_checks(frames, drives: pd.DataFrame, table: pd.DataFrame) -> list[dict]:
    """One row per resolved drive: the coherence facts and, with a man left, the subset flags."""
    bh_def = drives.set_index("id")["ballhandlerDefId"]
    near = nearest_defenders(frames)
    rows = []
    for d in table[(table["status"] == "ok") & table["drive_id"].isin(drives["id"])].itertuples(
            index=False):
        r0 = _row_of(frames.frame_idx, int(d.start_frame))
        raw = frames.matchup[r0]
        prov = int(raw[int(d.handler_slot)])
        hb = bh_def.get(d.drive_id, np.nan)
        assigned = prov >= 0
        row = {
            "drive_id": d.drive_id,
            "handler_assigned": assigned,
            "handler_is_nearest": assigned and prov == int(near[r0, int(d.handler_slot)]),
            "handler_is_drive_def": assigned and bool(pd.notna(hb))
            and int(frames.def_ids[r0, prov]) == int(hb),
            "defender_twice": len(set(raw[raw >= 0].tolist())) < int((raw >= 0).sum()),
            "helped_with_man_left": bool(d.has_helper) and d.left_slot >= 0,
        }
        if d.left_slot >= 0:
            dist = np.linalg.norm(frames.xy[r0, N_SIDE:].astype(np.float64)
                                  - frames.xy[r0, int(d.left_slot)].astype(np.float64), axis=1)
            h = int(d.helper_def_slot)  # without a helper: the comparable defender, as in rotation
            row["helper_nearest"] = int(np.argmin(dist)) == h
            row["helper_dist"] = float(dist[h])
            row["handler_corroborated"] = row["handler_is_nearest"] and row["handler_is_drive_def"]
        rows.append(row)
    return rows


def coherence_table(checks: pd.DataFrame) -> pd.DataFrame:
    """The counts of step 1, as metric, n, of."""
    assigned = checks[checks["handler_assigned"]]
    helped = checks[checks["helped_with_man_left"]]
    rows = [
        ("resolved drives", len(checks), len(checks)),
        ("handler's defender assigned", int(checks["handler_assigned"].sum()), len(checks)),
        ("assigned defender is the nearest", int(assigned["handler_is_nearest"].sum()),
         len(assigned)),
        ("assigned defender is drives.ballhandlerDefId",
         int(assigned["handler_is_drive_def"].sum()), len(assigned)),
        ("drives with a defender assigned twice", int(checks["defender_twice"].sum()), len(checks)),
        ("helper is nearest to the man left at the start", int(helped["helper_nearest"].sum()),
         len(helped)),
        ("helper within 10 ft of the man left at the start",
         int((helped["helper_dist"] <= NEAR_LEFT_FT).sum()), len(helped)),
    ]
    return pd.DataFrame(rows, columns=["metric", "n", "of"])


def check_table(pairs: pd.DataFrame, drives_out: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    """Subset x horizon x series, with the contrast as the third series."""
    rows = []
    for sub in SUBSETS:
        keep = set(flags.index[flags[sub]])
        p = pairs[pairs["drive_id"].isin(keep)]
        d = drives_out[drives_out["drive_id"].isin(keep)]
        for h in ROTATION_HORIZONS:
            for helped in (True, False):
                s = summarise(p, d, h, helped, HELP_FT)
                rows.append({"subset": sub, "horizon_s": h / FPS,
                             "series": "helped" if helped else "unhelped",
                             "n_drives": s["n_drives"], "mean": s["mean_diff"],
                             "ci_low": s["ci_low"], "ci_high": s["ci_high"],
                             "median_pairs": s["median_diff"],
                             "share_pos": s["share_diff_positive"]})
            c = contrast(p, h)
            rows.append({"subset": sub, "horizon_s": h / FPS, "series": "contrast",
                         "n_drives": f"{c['n_helped']}/{c['n_no_helper']}",
                         "mean": c["contrast_mean"], "ci_low": c["contrast_ci_low"],
                         "ci_high": c["contrast_ci_high"], "median_pairs": np.nan,
                         "share_pos": np.nan})
    return pd.DataFrame(rows)


def assert_s0_is_published(out: pd.DataFrame, reports: Path) -> None:
    """S0 is the published analysis: its rows must equal second_help_summary / _contrast."""
    s0 = out[out["subset"] == "S0"]
    summ = pd.read_csv(reports / "second_help_summary.csv")
    for r in summ.itertuples(index=False):
        got = s0[(s0["horizon_s"] == r.horizon_s)
                 & (s0["series"] == ("helped" if r.helped else "unhelped"))].iloc[0]
        assert int(got["n_drives"]) == r.n_drives
        assert np.allclose([got["mean"], got["ci_low"], got["ci_high"]],
                           [r.mean_diff, r.ci_low, r.ci_high], atol=1e-9), (r.horizon_s, r.helped)
    con = pd.read_csv(reports / "second_help_contrast.csv")
    for r in con.itertuples(index=False):
        got = s0[(s0["horizon_s"] == r.horizon_s) & (s0["series"] == "contrast")].iloc[0]
        assert got["n_drives"] == f"{r.n_helped}/{r.n_no_helper}"
        assert np.allclose([got["mean"], got["ci_low"], got["ci_high"]],
                           [r.contrast_mean, r.contrast_ci_low, r.contrast_ci_high], atol=1e-9)


def reading(out: pd.DataFrame) -> list[tuple[float, str]]:
    """The pre-registered reading, per horizon: HOLDS or FAILS, and why."""
    verdicts = []
    for h in sorted(out["horizon_s"].unique()):
        sub = out[out["horizon_s"] == h]
        corr = sub[sub["subset"] != "S0"]
        con = corr[corr["series"] == "contrast"]
        helped = [float(sub[(sub["subset"] == s) & (sub["series"] == "helped")]["mean"].iloc[0])
                  for s in SUBSETS]
        above = bool((con["ci_low"] > 0).any())
        rising = all(b > a for a, b in zip(helped, helped[1:], strict=False))
        holds = (not above and not rising and all(m <= 0 for m in helped)
                 and bool(((con["ci_low"] <= 0) & (con["ci_high"] >= 0)).all()))
        verdicts.append((float(h), "HOLDS" if holds else "FAILS"))
    return verdicts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--root", type=Path, default=DATA)
    parser.add_argument("--cache", type=Path, default=INTERIM)
    parser.add_argument("--out", type=Path, default=REPORTS)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    dataset = Dataset(args.root)
    all_pairs, all_drives, checks = [], [], []
    for game in dataset.game_ids:
        frames = get_or_build(dataset, game, args.cache)
        drives = dataset.events(game)["drives"]
        table = help_table(frames, drives)
        pairs, drives_out = rotation_table(frames, drives, table)
        all_pairs.append(pairs)
        all_drives.append(drives_out)
        checks += drive_checks(frames, drives, table)
    pairs = pd.concat(all_pairs, ignore_index=True)
    drives_out = pd.concat(all_drives, ignore_index=True)
    checks = pd.DataFrame(checks)

    coherence = coherence_table(checks)
    coherence.to_csv(args.out / "matchup_coherence.csv", index=False)

    with_left = checks[checks["helper_nearest"].notna()]
    flags = pd.DataFrame(
        [subset_flags(bool(r.handler_corroborated), bool(r.helper_nearest), float(r.helper_dist))
         for r in with_left.itertuples(index=False)],
        index=with_left["drive_id"].to_numpy())
    out = check_table(pairs, drives_out, flags)
    assert_s0_is_published(out, args.out)
    out.to_csv(args.out / "second_help_matchup_check.csv", index=False)

    print(coherence.to_string(index=False))
    print(f"\nS0 rows equal second_help_summary.csv and second_help_contrast.csv "
          f"({BOOTSTRAP_DRAWS} draws)")
    pd.set_option("display.width", 200)
    print(out.round(3).to_string(index=False))
    for h, verdict in reading(out):
        print(f"pre-registered reading at {h:.1f} s: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
