"""Near help and long help by the last, against their references (A8).

Usage: uv run python scripts/help_kinds.py [--root DIR] [--cache DIR] [--out DIR]

For every published game it loads the frame cache, classifies each resolved drive with
`scbasket.help_kinds.drive_kinds` and measures, for each kind and its reference, the same
paired difference as `scripts/second_help.py` (the other three defenders toward the helper's
man, minus the placebo; per-drive mean; bootstrap over drives with the same unit, draws and
seed), plus the contrast kind minus reference. It also splits the published helpers by class
and by recovered / committed against the published unhelped series. The pre-registered
readings (tasks/todo.md, A8: LONG and its sensitivities, NEAR-COMMITTED, the published
committed helpers) are applied by `reading` at the 1.5 s headline and written next to those
contrasts; the other contrasts carry no reading.

Writes to {out}:
  help_kinds.csv          one row per resolved drive, every flag and slot
  help_kinds_summary.csv  tidy: measure (count | paired_diff | contrast), kind, variant, horizon,
                          n, n_ref, mean, ci_low, ci_high, median, share_pos, nearest_* shares,
                          reading
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from second_help import contrast, summarise

from scbasket.frames import get_or_build
from scbasket.help_kinds import ANALYSES, drive_kinds, kind_help_table
from scbasket.io import Dataset
from scbasket.rotation import HEADLINE_HORIZON, ROTATION_HORIZONS, rotation_table
from scbasket.wind import FPS, HELP_FT, help_table

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "opendata-basketball"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

MIN_DRIVES = 40  # the pre-registered least n of a verdict
WIDE_FT = 1.0  # a CI beyond this on both sides of zero says nothing
COLUMNS = ["measure", "kind", "variant", "horizon", "n", "n_ref", "mean", "ci_low", "ci_high",
           "median", "share_pos", "nearest_helper", "nearest_handler_def", "nearest_third",
           "reading"]


def reading(n: int, low: float, high: float) -> str:
    """The pre-registered three-way reading of a contrast at the headline horizon."""
    if n < MIN_DRIVES or (low < -WIDE_FT and high > WIDE_FT):
        return "INCONCLUSIVE"
    return "ROTATION" if low > 0 else "ABSENCE"


def count_row(kind: str, variant: str, n: int) -> dict:
    return {"measure": "count", "kind": kind, "variant": variant, "n": int(n)}


def paired_row(kind: str, variant: str, pairs, drives, horizon: int, helped: bool) -> dict:
    s = summarise(pairs, drives, horizon, helped, HELP_FT)
    return {"measure": "paired_diff", "kind": kind, "variant": variant, "horizon": horizon / FPS,
            "n": s["n_drives"], "mean": s["mean_diff"], "ci_low": s["ci_low"],
            "ci_high": s["ci_high"], "median": s["median_diff"],
            "share_pos": s["share_diff_positive"],
            "nearest_helper": s["nearest_helper"], "nearest_handler_def": s["nearest_handler_def"],
            "nearest_third": s["nearest_third"]}


def contrast_row(kind: str, variant: str, pairs, horizon: int, read: bool = False) -> dict:
    row = {"measure": "contrast", "kind": kind, "variant": variant, "horizon": horizon / FPS}
    p = pairs[pairs["horizon"] == horizon].dropna(subset=["placebo"])
    if p.groupby("helped")["drive_id"].nunique().reindex([True, False]).fillna(0).min() == 0:
        return row | {"n": 0, "n_ref": 0}
    c = contrast(pairs, horizon)
    row |= {"n": c["n_helped"], "n_ref": c["n_no_helper"], "mean": c["contrast_mean"],
            "ci_low": c["contrast_ci_low"], "ci_high": c["contrast_ci_high"]}
    if read and horizon == HEADLINE_HORIZON:
        row["reading"] = reading(row["n"], row["ci_low"], row["ci_high"])
    return row


def kind_rows(kind: str, variant: str, pairs, drives) -> list[dict]:
    """Paired difference of the kind and of its reference, and the contrast, at every horizon."""
    rows = []
    for h in ROTATION_HORIZONS:
        rows.append(paired_row(kind, variant, pairs, drives, h, True))
        rows.append(paired_row(kind + "_ref", variant, pairs, drives, h, False))
        rows.append(contrast_row(kind, variant, pairs, h, kind != "near_stunt"))
    return rows


def published_rows(name: str, ids: set, pairs, drives) -> list[dict]:
    """A subset of the published helpers against the published unhelped series."""
    keep_p = pairs["drive_id"].isin(ids) | ~pairs["helped"]
    keep_d = drives["drive_id"].isin(ids) | ~drives["helped"]
    sub_p, sub_d = pairs[keep_p], drives[keep_d]
    rows = []
    for h in ROTATION_HORIZONS:
        rows.append(paired_row(name, "published", sub_p, sub_d, h, True))
        rows.append(contrast_row(name, "published", sub_p, h, name == "pub_committed"))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--root", type=Path, default=DATA)
    parser.add_argument("--cache", type=Path, default=INTERIM)
    parser.add_argument("--out", type=Path, default=REPORTS)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    dataset = Dataset(args.root)
    kinds_all = []
    run = {name: ([], []) for name in ANALYSES}
    pub = ([], [])
    for game in dataset.game_ids:
        frames = get_or_build(dataset, game, args.cache)
        drives = dataset.events(game)["drives"]
        table = help_table(frames, drives)
        kinds = drive_kinds(frames, drives, table)
        kinds_all.append(kinds)
        for name, (kind_col, ref_col, who) in ANALYSES.items():
            t = kind_help_table(frames, table, kinds, kind_col, ref_col, who)
            if len(t):
                pairs, out = rotation_table(frames, drives, t)
                run[name][0].append(pairs)
                run[name][1].append(out)
        pairs, out = rotation_table(frames, drives, table)
        pub[0].append(pairs)
        pub[1].append(out)
    kinds = pd.concat(kinds_all, ignore_index=True)
    kinds.to_csv(args.out / "help_kinds.csv", index=False)

    rows = [count_row("drives", "resolved", len(kinds)),
            count_row("drives", "published_helpers", kinds["has_helper"].sum())]
    for who in ("last", "near"):
        for status, n in kinds[f"{who}_status"].value_counts().items():
            rows.append(count_row(f"{who}_status", status, n))
    flags = ["beaten_geo", "blowby", "long", "long_path5", "long_path8", "long_blowby",
             "long_move4", "long_ref", "long_ref_blowby", "near_stunt", "near_committed",
             "near_ref"]
    for col in flags:
        rows.append(count_row("flag", col, kinds[col].sum()))
    helpers = kinds[kinds["has_helper"]]
    for cls, n in helpers["helper_class"].value_counts().items():
        rows.append(count_row("helper_class", cls, n))
    for stance, n in helpers["helper_stance"].replace("", "undefined").value_counts().items():
        rows.append(count_row("helper_stance", stance, n))
    for cls in ("last", "nearest", "other"):
        for stance, n in helpers[helpers["helper_class"] == cls]["helper_stance"].replace(
                "", "undefined").value_counts().items():
            rows.append(count_row("helper_class_stance", f"{cls}_{stance}", n))

    for name in ANALYSES:
        if not run[name][0]:
            continue
        pairs = pd.concat(run[name][0], ignore_index=True)
        out = pd.concat(run[name][1], ignore_index=True)
        primary = name in ("long", "near_stunt", "near_committed")
        rows += kind_rows(name, "primary" if primary else "sensitivity", pairs, out)

    pairs = pd.concat(pub[0], ignore_index=True)
    out = pd.concat(pub[1], ignore_index=True)
    rows.append(count_row("published_rotation", "with_man_left", len(out)))
    rows.append(count_row("published_rotation", "helped_with_man_left", out["helped"].sum()))
    cls = kinds.set_index("drive_id")
    out = out.assign(helper_class=out["drive_id"].map(cls["helper_class"]),
                     helper_stance=out["drive_id"].map(cls["helper_stance"]))
    helped = out[out["helped"]]
    subsets = {"pub_all": set(helped["drive_id"])}
    for c in ("last", "nearest", "other"):
        subsets[f"pub_{c}"] = set(helped.loc[helped["helper_class"] == c, "drive_id"])
    for stance in ("recovered", "committed"):
        subsets[f"pub_{stance}"] = set(helped.loc[helped["helper_stance"] == stance, "drive_id"])
    for name, ids in subsets.items():
        rows += published_rows(name, ids, pairs, out)
    rows += [paired_row("pub_unhelped", "published", pairs, out, h, False)
             for h in ROTATION_HORIZONS]

    summary = pd.DataFrame(rows).reindex(columns=COLUMNS)
    summary.to_csv(args.out / "help_kinds_summary.csv", index=False)

    print(summary[summary["measure"] == "count"][["kind", "variant", "n"]].to_string(index=False))
    head = summary[(summary["horizon"] == HEADLINE_HORIZON / FPS) & (summary["measure"] != "count")]
    print("\n1.5 s")
    with pd.option_context("display.width", 220, "display.max_columns", 30,
                           "display.float_format", "{:+.2f}".format):
        print(head.drop(columns=["measure", "horizon"]).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
