"""The second help on every drive: does anyone cover the man the helper left? (P8).

Usage: uv run python scripts/second_help.py [--root DIR] [--cache DIR] [--out DIR]

For every published game it loads the frame cache (building it if missing), computes the
first-second table with `scbasket.wind.help_table` IN PROCESS (it does not read
`reports/help_table.csv`, so it can run while that file is being rewritten) and measures the
three other defenders' rotation toward the man left, against a placebo, with
`scbasket.rotation`. It then reads the first pass and the first closeout after each drive.
Nothing is gated: the definitions are fixed in the modules and the sensitivity sweep prints
its neighbours. Rotation, "covers" and "helps" name measured displacements and distances,
never decisions.

Writes to {out}:
  second_help_pairs.csv        one row per (drive, other defender, horizon)
  second_help_drives.csv       one row per drive: best movers, nearest_who, the clearance curve
  second_help_summary.csv      per horizon x helped: the paired difference with its CI and shares
  second_help_contrast.csv     helped minus no helper, per horizon, with a two-sample bootstrap CI
  second_help_by_game.csv      the paired median per game x horizon x helped, reported not gated
  second_help_sensitivity.csv  the summary over HELP_FT x horizon
  second_help_contrast_sensitivity.csv  the contrast over HELP_FT x horizon
  second_help_pass.csv         the first pass after the drive, per helped
  second_help_closeouts.csv    the first closeout after the drive, per helped x receiver (a limit)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.frames import N_SIDE, get_or_build
from scbasket.io import Dataset
from scbasket.rotation import (
    HEADLINE_HORIZON,
    NEAREST_WHO,
    ROTATION_HORIZONS,
    rotation_table,
)
from scbasket.wind import FPS, HELP_FT, OPEN_FT, _row_of, help_table

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "opendata-basketball"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

SENSITIVITY_HELP_FT = (3.0, 4.0, 5.0)
BOOTSTRAP_DRAWS = 4000
BOOTSTRAP_SEED = 0


def bootstrap_ci(values: np.ndarray) -> tuple[float, float]:
    """95 % interval of the mean, resampling drives (one value each) with a fixed seed."""
    if len(values) == 0:
        return np.nan, np.nan
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    means = values[rng.integers(0, len(values), size=(BOOTSTRAP_DRAWS, len(values)))].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(low), float(high)


def summarise(pairs: pd.DataFrame, drives: pd.DataFrame, horizon: int, helped: bool,
              help_ft: float) -> dict:
    """The headline numbers of one (horizon, helped) cell.

    The paired difference is `to_left - placebo` for the same defender in the same drive; its
    mean is taken per drive first (three defenders per drive are not independent draws) and the
    interval resamples drives. The open shares use the clearance at `horizon` and at 0 s.
    """
    p = pairs[(pairs["helped"] == helped) & (pairs["horizon"] == horizon)].dropna(
        subset=["placebo"])
    diff = p["to_left"] - p["placebo"]
    per_drive = diff.groupby(p["drive_id"]).mean().to_numpy()
    low, high = bootstrap_ci(per_drive)
    d = drives[(drives["helped"] == helped) & drives[f"nearest_who_{horizon}"].ne("")]
    who = d[f"nearest_who_{horizon}"].value_counts(normalize=True)
    clear = d[f"left_clear_{horizon}"].dropna()  # the horizons are all clearance frames
    clear0 = drives.loc[drives["helped"] == helped, "left_clear_0"].dropna()
    return {
        "horizon": horizon, "horizon_s": horizon / FPS, "helped": helped, "help_ft": help_ft,
        "n_drives": int(len(d)), "n_pairs": int(len(p)),
        "median_to_left": float(p["to_left"].median()),
        "median_placebo": float(p["placebo"].median()),
        "median_diff": float(diff.median()),
        "mean_diff": float(per_drive.mean()) if len(per_drive) else np.nan,
        "ci_low": low, "ci_high": high,
        "share_diff_positive": float((diff > 0).mean()),
        "share_mover_left": float((d[f"rot_left_{horizon}"] >= help_ft).mean()),
        "share_mover_placebo": float((d[f"rot_placebo_{horizon}"] >= help_ft).mean()),
        **{f"nearest_{name}": float(who.get(name, 0.0)) for name in NEAREST_WHO},
        "nearest_dist_median": float(d[f"nearest_dist_{horizon}"].median()),
        "n_clear": int(len(clear)), "left_open_share": float((clear >= OPEN_FT).mean()),
        "n_clear0": int(len(clear0)), "left_open0_share": float((clear0 >= OPEN_FT).mean()),
    }


def contrast(pairs: pd.DataFrame, horizon: int, help_ft: float = HELP_FT) -> dict:
    """Helped minus no-helper, on the per-drive mean paired difference of `summarise`.

    The no-helper group is the baseline: the man left stands out on the perimeter, so even
    with no helper the paired difference is not zero. Two-sample bootstrap: each group is
    resampled on its own, with the same seed and number of draws as `bootstrap_ci`.
    """
    p = pairs[pairs["horizon"] == horizon].dropna(subset=["placebo"])
    diff = p["to_left"] - p["placebo"]
    per_drive = diff.groupby([p["helped"], p["drive_id"]]).mean()
    helped, base = per_drive.loc[True].to_numpy(), per_drive.loc[False].to_numpy()
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = (helped[rng.integers(0, len(helped), size=(BOOTSTRAP_DRAWS, len(helped)))].mean(axis=1)
             - base[rng.integers(0, len(base), size=(BOOTSTRAP_DRAWS, len(base)))].mean(axis=1))
    low, high = np.percentile(draws, [2.5, 97.5])
    return {"horizon": horizon, "horizon_s": horizon / FPS, "help_ft": help_ft,
            "n_helped": len(helped), "n_no_helper": len(base),
            "contrast_mean": float(helped.mean() - base.mean()),
            "contrast_ci_low": float(low), "contrast_ci_high": float(high)}


def by_game(pairs: pd.DataFrame) -> pd.DataFrame:
    """The paired difference per game x horizon x helped: reported, never gated.

    `median_diff` is the median over drives of the per-drive mean (the unit of the headline's
    mean and CI); `median_diff_pairs` is the median over the individual (drive, defender) pairs.
    """
    rows = []
    for (game, horizon, helped), g in pairs.dropna(subset=["placebo"]).groupby(
            ["game", "horizon", "helped"]):
        diff = g["to_left"] - g["placebo"]
        rows.append({"game": game, "horizon": horizon, "helped": helped, "n_pairs": len(g),
                     "n_drives": g["drive_id"].nunique(),
                     "median_diff": float(diff.groupby(g["drive_id"]).mean().median()),
                     "median_diff_pairs": float(diff.median())})
    return pd.DataFrame(rows)


def first_pass(frames, passes: pd.DataFrame, chance_id, d) -> dict:
    """The first pass of the drive's chance from `startFrame`, and the man left at that frame."""
    p = passes[(passes["chanceId"] == chance_id) & (passes["startFrame"] >= d.start_frame)]
    if not len(p):
        return {"has_pass": False}
    fp = p.sort_values("startFrame").iloc[0]
    out = {"has_pass": True, "delay_s": (fp["startFrame"] - d.start_frame) / FPS,
           "to_left": bool(pd.notna(fp["receiverId"]) and int(fp["receiverId"]) == int(d.left_id))}
    r0 = _row_of(frames.frame_idx, int(d.start_frame))
    rp = _row_of(frames.frame_idx, int(fp["startFrame"]))
    if rp < 0 or frames.chance_idx[rp] != frames.chance_idx[r0]:
        return out
    xy = frames.xy.astype(np.float64)
    passer = np.flatnonzero(frames.off_ids[rp] == fp["passerId"])
    passer = int(passer[0]) if len(passer) else int(d.handler_slot)
    open_ft = {a: float(np.linalg.norm(xy[rp, N_SIDE:] - xy[rp, a], axis=1).min())
               for a in range(N_SIDE) if a != passer}
    most_open = max(open_ft, key=open_ft.get)
    receiver = np.flatnonzero(frames.off_ids[rp] == fp["receiverId"])
    left = int(d.left_slot)
    out.update({
        "resolved": True, "left_open": open_ft.get(left, np.nan),
        "left_most_open": most_open == left,
        "receiver_most_open": len(receiver) > 0 and int(receiver[0]) == most_open,
        "receiver_open": open_ft.get(int(receiver[0]), np.nan) if len(receiver) else np.nan,
        "most_open": open_ft[most_open],
    })
    return out


def pass_summary(rows: pd.DataFrame) -> pd.DataFrame:
    """Per helped: how many first passes, how many to the man left, and how open he was."""
    out = []
    for helped, g in rows.groupby("helped"):
        passed = g[g["has_pass"]]
        r = passed[passed["resolved"].fillna(False).astype(bool)]
        got, missed = r[r["to_left"].astype(bool)], r[~r["to_left"].astype(bool)]
        out.append({
            "helped": helped, "n_drives": len(g), "n_first_pass": len(passed),
            "n_to_left": int(passed["to_left"].astype(bool).sum()),
            "share_to_left": float(passed["to_left"].astype(bool).mean()),
            "median_delay_s": float(passed["delay_s"].median()),
            "n_resolved": len(r),
            "left_most_open_share": float(r["left_most_open"].astype(bool).mean()),
            "receiver_most_open_share": float(r["receiver_most_open"].astype(bool).mean()),
            "median_left_clear": float(r["left_open"].median()),
            "median_receiver_clear": float(r["receiver_open"].median()),
            "median_most_open_clear": float(r["most_open"].median()),
            "n_left_got_it": len(got), "left_clear_when_got_it": float(got["left_open"].median()),
            "n_left_missed": len(missed),
            "left_clear_when_not": float(missed["left_open"].median()),
        })
    return pd.DataFrame(out)


def first_closeout(frames, closeouts: pd.DataFrame, chance_id, d) -> dict | None:
    """The first provider closeout of the chance from `startFrame`: who closed on whom."""
    c = closeouts[(closeouts["chanceId"] == chance_id) & (closeouts["startFrame"] >= d.start_frame)]
    if not len(c):
        return None
    c = c.sort_values("startFrame").iloc[0]
    r0 = _row_of(frames.frame_idx, int(d.start_frame))
    receiver = np.flatnonzero(frames.off_ids[r0] == c["ballhandlerId"])
    if not len(receiver):
        return None
    own_slot = int(frames.matchup[r0][int(receiver[0])])
    own_id = int(frames.def_ids[r0, own_slot]) if own_slot >= 0 else -1
    closer = int(c["ballhandlerDefId"]) if pd.notna(c["ballhandlerDefId"]) else -2
    return {"helped": bool(d.has_helper),
            "receiver_is_left": bool(d.has_helper) and int(d.left_id) == int(c["ballhandlerId"]),
            "closer_is_own": closer == own_id,
            "delay_s": (c["startFrame"] - d.start_frame) / FPS,
            "start_dist": c["startDistance"], "end_dist": c["endDistance"]}


def closeout_summary(rows: pd.DataFrame) -> pd.DataFrame:
    """Per helped x receiver-is-the-man-left: who closes out, published as a limit (small n)."""
    out = []
    for (helped, is_left), g in rows.groupby(["helped", "receiver_is_left"]):
        out.append({
            "helped": helped, "receiver_is_left": is_left, "n": len(g),
            "closer_own_share": float(g["closer_is_own"].mean()),
            "closer_other_share": float(1.0 - g["closer_is_own"].mean()),
            "median_delay_s": float(g["delay_s"].median()),
            "median_start_dist": float(g["start_dist"].median()),
            "median_end_dist": float(g["end_dist"].median()),
        })
    return pd.DataFrame(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--root", type=Path, default=DATA)
    parser.add_argument("--cache", type=Path, default=INTERIM)
    parser.add_argument("--out", type=Path, default=REPORTS)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    dataset = Dataset(args.root)
    all_pairs, all_drives, pass_rows, closeout_rows = [], [], [], []
    for game in dataset.game_ids:
        frames = get_or_build(dataset, game, args.cache)
        events = dataset.events(game)
        drives = events["drives"]
        table = help_table(frames, drives)
        pairs, drives_out = rotation_table(frames, drives, table)
        all_pairs.append(pairs)
        all_drives.append(drives_out)
        chance_of = dict(zip(drives["id"], drives["chanceId"], strict=True))
        for d in table[table["status"] == "ok"].itertuples(index=False):
            closeout = first_closeout(frames, events["closeouts"], chance_of[d.drive_id], d)
            if closeout is not None:
                closeout_rows.append(closeout)
            if d.left_slot >= 0:
                got = first_pass(frames, events["passes"], chance_of[d.drive_id], d)
                pass_rows.append({"drive_id": d.drive_id, "helped": bool(d.has_helper), **got})
    pairs = pd.concat(all_pairs, ignore_index=True)
    drives_out = pd.concat(all_drives, ignore_index=True)
    pairs.to_csv(args.out / "second_help_pairs.csv", index=False)
    drives_out.to_csv(args.out / "second_help_drives.csv", index=False)

    summary = pd.DataFrame([summarise(pairs, drives_out, h, helped, HELP_FT)
                            for h in ROTATION_HORIZONS for helped in (True, False)])
    summary.to_csv(args.out / "second_help_summary.csv", index=False)
    contrasts = pd.DataFrame([contrast(pairs, h) for h in ROTATION_HORIZONS])
    contrasts.to_csv(args.out / "second_help_contrast.csv", index=False)
    game_table = by_game(pairs)
    game_table.to_csv(args.out / "second_help_by_game.csv", index=False)

    rows, contrast_rows = [], []
    for help_ft in SENSITIVITY_HELP_FT:
        relabel = drives_out.assign(helped=drives_out["helper_help_move"] >= help_ft)
        pairs_h = pairs.drop(columns="helped").merge(relabel[["drive_id", "helped"]],
                                                     on="drive_id")
        rows += [summarise(pairs_h, relabel, h, helped, help_ft)
                 for h in ROTATION_HORIZONS for helped in (True, False)]
        contrast_rows += [contrast(pairs_h, h, help_ft) for h in ROTATION_HORIZONS]
    pd.DataFrame(rows).to_csv(args.out / "second_help_sensitivity.csv", index=False)
    pd.DataFrame(contrast_rows).to_csv(args.out / "second_help_contrast_sensitivity.csv",
                                       index=False)

    pass_table = pass_summary(pd.DataFrame(pass_rows))
    pass_table.to_csv(args.out / "second_help_pass.csv", index=False)
    closeouts = closeout_summary(pd.DataFrame(closeout_rows))
    closeouts.to_csv(args.out / "second_help_closeouts.csv", index=False)

    print(f"resolved drives with a man left: {len(drives_out)}; "
          f"helped (>= {HELP_FT:.0f} ft): {int(drives_out['helped'].sum())}")
    print("\nrotation toward the man left minus the placebo, mean per drive (95% CI, "
          f"{BOOTSTRAP_DRAWS} resamples), median over pairs, share > 0")
    for row in summary.itertuples(index=False):
        print(f"  helped={row.helped!s:5} {row.horizon_s:.1f} s  n={row.n_drives:3d}  "
              f"{row.mean_diff:+.2f} ft ({row.ci_low:+.2f} to {row.ci_high:+.2f})  "
              f"median {row.median_diff:+.2f}  share>0 {row.share_diff_positive:.3f}  "
              f"mover >= {HELP_FT:.0f} ft: left {row.share_mover_left:.3f} vs placebo "
              f"{row.share_mover_placebo:.3f}")
    head = game_table[(game_table["horizon"] == HEADLINE_HORIZON) & game_table["helped"]]
    print(f"\nper game, helped, {HEADLINE_HORIZON / FPS:.1f} s: median per-drive "
          f"paired difference negative in {int((head['median_diff'] < 0).sum())} "
          f"of {len(head)} games")
    print("\nnearest defender to the man left (helper / handler_def / third), median distance:")
    for row in summary.itertuples(index=False):
        print(f"  helped={row.helped!s:5} {row.horizon_s:.1f} s  {row.nearest_helper:.3f} / "
              f"{row.nearest_handler_def:.3f} / {row.nearest_third:.3f}  "
              f"{row.nearest_dist_median:.2f} ft")
    print(f"\nthe man left open (nobody within {OPEN_FT:.0f} ft), helped against no helper:")
    for row in summary.itertuples(index=False):
        print(f"  helped={row.helped!s:5} {row.horizon_s:.1f} s  at the horizon "
              f"{row.left_open_share:.3f}, at 0 s {row.left_open0_share:.3f}")
    print("\nthe first pass after the drive:")
    print(pass_table.to_string(index=False))
    print("\nthe first closeout after the drive (a limit, not a finding):")
    print(closeouts.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
