"""The committed near help's own paired difference under every check the module promises (13a).

Usage: uv run python scripts/near_robustness.py [--root DIR] [--cache DIR] [--out DIR]

The claim since the review of 2026-10-31 (`scripts/help_kinds.py`): after a near help that
commits, the three other defenders move toward the man he left no more than toward any other
attacker (the placebo), with the 95 % CI's top as the bound. These numbers were seen before the
claim was written, so this file is a robustness record, not a pre-registration. For every
published game it measures the paired difference ONCE for every drive whose nearest defender
has a man and a 2.0 s window (`help_kinds.near_status == "ok"`, the helper being the nearest),
then regroups the drives by each check's rule, so every cell is the same per-drive values
counted over a different set. Bootstraps use `second_help`'s unit, draws and seed; the primary
rows and the old split's rows are asserted equal to `help_kinds_summary.csv` before anything is
written, so the two scripts cannot drift.

The checks, each reported for the committed group's own mean, the reference's (the nearest
moves less than NEAR_STAY_FT) and their contrast:

  primary         the rule of `scbasket.help_kinds` (the helper's distance at 2.0 s to where
                  his man STARTED)
  endpos          the split before the review (his distance to where the man IS at 2.0 s)
  fixed_targets   every target read where it stands at the drive's start, not at the horizon
                  (`rotation_table(fixed_targets=True)`): no attacker's run can move it
  no_pass         drives whose chance has no pass from the drive's start to 1.52 s
  detected        the three others and the man left detected on every frame 0 to 1.52 s
  coherent        the nearest is the defender closest to his own raw man at the start
  leave_one_out   one game dropped at a time (`detail` names it)
  game_cluster    the interval from resampling GAMES with replacement (the mean is the
                  full sample's)

Writes to {out}:
  near_sensitivity.csv        the grid NEAR_STEP_FT x RECOVER_FT x NEAR_STAY_FT at 1.5 s, one
                              row per cell: the committed group, the reference, the contrast,
                              and the reading of the committed group's own interval
  near_robustness.csv         tidy: check, detail, horizon, group (committed | reference |
                              contrast), n, n_ref, mean, ci_low, ci_high
  near_matchup_coherence.csv  per group: how often the nearest is the defender closest to his
                              own raw man at the start (the provider's matchup, a consistency
                              check, not a validation)
  near_rotator.csv            13 a2 (i), pre-registered in tasks/todo.md (commit 83e8d5d)
                              before it ran: R1, the other defender closest to the man left at
                              the start, and R2, the low man (closest to the hoop), each on his
                              own: rotator, horizon, group, n, mean, CI, and at 1.5 s the
                              reading (ROTATION if the committed interval lies above 0)
  near_pass.csv               13 a2 (ii), same commit: drives with a pass starting inside the
                              first 1.52 s (any, to the man left, with 1.0 s of tracking after
                              it), and from the first such pass's release over 1.0 s the three
                              others' mean and R1's own value, same placebo; the reading is
                              LIMIT under PASS_MIN_N committed drives
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from help_kinds import CLAIM, reading
from second_help import BOOTSTRAP_DRAWS, BOOTSTRAP_SEED, bootstrap_ci, first_pass

from scbasket.frames import N_SIDE, get_or_build
from scbasket.help_kinds import NEAR_STAY_FT, NEAR_STEP_FT, RECOVER_FT, drive_kinds, kind_help_table
from scbasket.io import Dataset
from scbasket.rotation import (
    HEADLINE_HORIZON,
    ROTATION_HORIZONS,
    _projection,
    _window_end,
    rotation_table,
)
from scbasket.wind import FPS, HOOP, _row_of, help_table

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "opendata-basketball"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

GRID_STEP_FT = (1.5, 2.0, 2.5, 3.0)
GRID_RECOVER_FT = (0.0, 0.5, 1.0, 2.0)
GRID_STAY_FT = (0.5, 1.0, 1.5)
#: The headline window, seconds: a pass inside it, or a frame undetected, drops the drive.
WINDOW_S = HEADLINE_HORIZON / FPS
#: 13 a2 (ii): the measure after the pass runs 1.0 s from its release, and reads only with at
#: least PASS_MIN_N committed drives that have that window.
PASS_FRAMES = 25
PASS_MIN_N = 30


def a2_reading(low: float) -> str:
    """13 a2's reading, fixed before the run: an interval above 0 is a rotation."""
    return "ROTATION" if low > 0 else "ABSENCE"


def after_pass(xy: np.ndarray, rp: int, others: list[int], left: int, handler: int,
               raw: np.ndarray) -> dict[int, float]:
    """Each other defender's `to_left - placebo` from the pass release `rp` over PASS_FRAMES: his
    displacement projected toward the man left and toward the placebo targets (the set fixed at
    the drive's start, `raw` its raw matchup) where they are PASS_FRAMES after the release."""
    r1 = rp + PASS_FRAMES
    out = {}
    for x in others:
        p0, p1 = xy[rp, N_SIDE + x], xy[r1, N_SIDE + x]
        own = set(np.flatnonzero(raw == x).tolist())
        targets = [a for a in range(N_SIDE) if a not in (handler, left) and a not in own]
        if targets:
            out[x] = (_projection(p0, p1, xy[r1, left])
                      - float(np.mean([_projection(p0, p1, xy[r1, a]) for a in targets])))
    return out


def game_drives(dataset: Dataset, game: int, cache: Path) -> pd.DataFrame:
    """One row per near-ok drive of one game: the flags' inputs, the checks' subsets and the
    per-drive paired difference at each horizon, with targets at the horizon (`diff_T`) and at
    the start (`fixed_T`); the designated rotators' own values (`r1_T`, `r2_T`); and the pass
    of 13 a2 (`pass_in`, `pass_to_left`, `pass3`, `pass_r1`)."""
    frames = get_or_build(dataset, game, cache)
    events = dataset.events(game)
    drives, passes = events["drives"], events["passes"]
    table = help_table(frames, drives)
    kinds = drive_kinds(frames, drives, table)
    kinds["near_ok"] = kinds["near_status"] == "ok"
    t = kind_help_table(frames, table, kinds, CLAIM, "near_ok", "near")
    chance_of = dict(zip(drives["id"], drives["chanceId"], strict=True))
    xy = frames.xy.astype(np.float64)
    pairs, _ = rotation_table(frames, drives, t)
    own_value = (pairs.dropna(subset=["placebo"])
                 .assign(v=lambda p: p["to_left"] - p["placebo"])
                 .set_index(["drive_id", "def_slot", "horizon"])["v"])
    rows = []
    for d in t.itertuples(index=False):
        r0 = _row_of(frames.frame_idx, int(d.start_frame))
        helper, left = int(d.helper_def_slot), int(d.left_slot)
        others = [x for x in range(N_SIDE) if x not in (int(d.handler_def_slot), helper)]
        cols = [N_SIDE + x for x in others] + [left]
        got = first_pass(frames, passes, chance_of[d.drive_id], d)
        closest = int(np.linalg.norm(xy[r0, N_SIDE:] - xy[r0, left], axis=1).argmin())
        r1 = min(others, key=lambda x: float(np.linalg.norm(xy[r0, N_SIDE + x] - xy[r0, left])))
        r2 = min(others, key=lambda x: float(np.linalg.norm(xy[r0, N_SIDE + x] - HOOP)))
        row = {
            "drive_id": d.drive_id, "game": int(game),
            "pass_delay": got["delay_s"] if got["has_pass"] else np.nan,
            "detected": bool(frames.detected[r0:r0 + HEADLINE_HORIZON + 1][:, cols].all()),
            "coherent": closest == helper, "r1_slot": r1, "r2_slot": r2,
        }
        for h in ROTATION_HORIZONS:
            for name, slot in (("r1", r1), ("r2", r2)):
                row[f"{name}_{h}"] = own_value.get((d.drive_id, slot, h), np.nan)
        # 13 a2 (ii): the first pass of the chance starting inside the headline window
        p = passes[(passes["chanceId"] == chance_of[d.drive_id])
                   & (passes["startFrame"] >= d.start_frame)
                   & (passes["startFrame"] <= d.start_frame + HEADLINE_HORIZON)]
        row.update({"pass_in": len(p) > 0,
                    "pass_to_left": bool((p["receiverId"] == d.left_id).any()),
                    "pass_window": False, "pass3": np.nan, "pass_r1": np.nan})
        if len(p):
            rp = _row_of(frames.frame_idx, int(p["startFrame"].min()))
            if (rp >= 0 and frames.chance_idx[rp] == frames.chance_idx[r0]
                    and _window_end(frames, rp, PASS_FRAMES) - rp >= PASS_FRAMES):
                v = after_pass(xy, rp, others, left, int(d.handler_slot),
                               frames.matchup[r0])
                row.update({"pass_window": True,
                            "pass3": float(np.mean(list(v.values()))) if v else np.nan,
                            "pass_r1": v.get(r1, np.nan)})
        rows.append(row)
    out = pd.DataFrame(rows).merge(
        kinds[["drive_id", "near_move", "near_dist0", "near_dist2_start", "near_dist2_man"]],
        on="drive_id")
    for name, fixed in (("diff", False), ("fixed", True)):
        if fixed:
            pairs, _ = rotation_table(frames, drives, t, fixed_targets=True)
        p = pairs.dropna(subset=["placebo"])
        per = (p["to_left"] - p["placebo"]).groupby([p["drive_id"], p["horizon"]]).mean()
        wide = per.unstack("horizon").reindex(columns=list(ROTATION_HORIZONS))
        wide.columns = [f"{name}_{h}" for h in wide.columns]
        out = out.merge(wide, left_on="drive_id", right_index=True, how="left")
    return out


def committed(df: pd.DataFrame, step: float = NEAR_STEP_FT, recover: float = RECOVER_FT,
              endpos: bool = False) -> pd.Series:
    back = df["near_dist2_man"] if endpos else df["near_dist2_start"]
    return (df["near_move"] >= step) & (back > df["near_dist0"] + recover)


def reference(df: pd.DataFrame, stay: float = NEAR_STAY_FT) -> pd.Series:
    return df["near_move"] < stay


def two_sample(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """`second_help.contrast`'s interval: each group resampled on its own, same seed and draws."""
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = (a[rng.integers(0, len(a), size=(BOOTSTRAP_DRAWS, len(a)))].mean(axis=1)
             - b[rng.integers(0, len(b), size=(BOOTSTRAP_DRAWS, len(b)))].mean(axis=1))
    low, high = np.percentile(draws, [2.5, 97.5])
    return float(low), float(high)


def values(df: pd.DataFrame, mask: pd.Series, column: str) -> np.ndarray:
    """The per-drive values of one group, in drive_id order (the order `summarise` resamples)."""
    return df[mask].dropna(subset=[column]).sort_values("drive_id")[column].to_numpy()


def three(df: pd.DataFrame, com: pd.Series, ref: pd.Series, column: str) -> dict[str, dict]:
    """The committed group, the reference and their contrast, by drive bootstrap."""
    a, b = values(df, com, column), values(df, ref, column)
    (al, ah), (bl, bh), (cl, ch) = bootstrap_ci(a), bootstrap_ci(b), two_sample(a, b)
    return {
        "committed": {"n": len(a), "mean": float(a.mean()), "ci_low": al, "ci_high": ah},
        "reference": {"n": len(b), "mean": float(b.mean()), "ci_low": bl, "ci_high": bh},
        "contrast": {"n": len(a), "n_ref": len(b), "mean": float(a.mean() - b.mean()),
                     "ci_low": cl, "ci_high": ch},
    }


def by_games(df: pd.DataFrame, com: pd.Series, ref: pd.Series, column: str) -> dict[str, dict]:
    """The same three, with intervals from resampling games (seed and draws as the drives')."""
    point = three(df, com, ref, column)
    games = np.sort(df["game"].unique())
    a = {g: values(df, com & (df["game"] == g), column) for g in games}
    b = {g: values(df, ref & (df["game"] == g), column) for g in games}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    own, base, diff = [], [], []
    for _ in range(BOOTSTRAP_DRAWS):
        pick = rng.choice(games, size=len(games), replace=True)
        x, y = np.concatenate([a[g] for g in pick]), np.concatenate([b[g] for g in pick])
        own.append(x.mean())
        base.append(y.mean())
        diff.append(x.mean() - y.mean())
    for group, draws in (("committed", own), ("reference", base), ("contrast", diff)):
        low, high = np.percentile(draws, [2.5, 97.5])
        point[group] |= {"ci_low": float(low), "ci_high": float(high)}
    return point


def tidy(check: str, detail: str, horizon: int, cells: dict[str, dict]) -> list[dict]:
    return [{"check": check, "detail": detail, "horizon": horizon / FPS, "group": group, **cell}
            for group, cell in cells.items()]


def assert_equals_summary(rows: list[dict], summary: pd.DataFrame, kind: str) -> None:
    """The primary (or old-split) rows must equal `help_kinds_summary.csv`'s, to 1e-9."""
    for r in rows:
        name = {"committed": kind, "reference": f"{kind}_ref", "contrast": kind}[r["group"]]
        measure = "contrast" if r["group"] == "contrast" else "paired_diff"
        want = summary[(summary["measure"] == measure) & (summary["kind"] == name)
                       & np.isclose(summary["horizon"], r["horizon"])]
        assert len(want) == 1, (measure, name, r["horizon"])
        w = want.iloc[0]
        for col in ("n", "mean", "ci_low", "ci_high"):
            assert abs(r[col] - w[col]) < 1e-9, (kind, r["group"], r["horizon"], col)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--root", type=Path, default=DATA)
    parser.add_argument("--cache", type=Path, default=INTERIM)
    parser.add_argument("--out", type=Path, default=REPORTS)
    args = parser.parse_args()
    summary = pd.read_csv(args.out / "help_kinds_summary.csv")

    dataset = Dataset(args.root)
    df = pd.concat([game_drives(dataset, g, args.cache) for g in dataset.game_ids],
                   ignore_index=True)
    com, ref = committed(df), reference(df)
    no_pass = ~(df["pass_delay"] <= WINDOW_S)

    rows, primary, endpos = [], [], []
    for h in ROTATION_HORIZONS:
        col = f"diff_{h}"
        primary += tidy("primary", "", h, three(df, com, ref, col))
        endpos += tidy("endpos", "", h, three(df, committed(df, endpos=True), ref, col))
        rows += tidy("fixed_targets", "", h, three(df, com, ref, f"fixed_{h}"))
        rows += tidy("no_pass", "", h, three(df, com & no_pass, ref & no_pass, col))
        rows += tidy("detected", "", h, three(df, com & df["detected"], ref & df["detected"], col))
        rows += tidy("coherent", "", h, three(df, com & df["coherent"], ref & df["coherent"], col))
        for g in np.sort(df["game"].unique()):
            keep = df["game"] != g
            rows += tidy("leave_one_out", str(g), h, three(df, com & keep, ref & keep, col))
        rows += tidy("game_cluster", "", h, by_games(df, com, ref, col))
    assert_equals_summary(primary, summary, CLAIM)
    assert_equals_summary(endpos, summary, "near_committed_endpos")
    robust = pd.DataFrame(primary + endpos + rows)
    robust = robust.reindex(columns=["check", "detail", "horizon", "group", "n", "n_ref", "mean",
                                     "ci_low", "ci_high"])
    robust.to_csv(args.out / "near_robustness.csv", index=False)

    grid = []
    col = f"diff_{HEADLINE_HORIZON}"
    for step in GRID_STEP_FT:
        for recover in GRID_RECOVER_FT:
            for stay in GRID_STAY_FT:
                c = three(df, committed(df, step, recover), reference(df, stay), col)
                own = c["committed"]
                grid.append({
                    "step_ft": step, "recover_ft": recover, "stay_ft": stay,
                    "horizon": HEADLINE_HORIZON / FPS,
                    "n": own["n"], "mean": own["mean"], "ci_low": own["ci_low"],
                    "ci_high": own["ci_high"],
                    "reading": reading(own["n"], own["ci_low"], own["ci_high"]),
                    "n_ref": c["reference"]["n"], "ref_mean": c["reference"]["mean"],
                    "ref_ci_low": c["reference"]["ci_low"],
                    "ref_ci_high": c["reference"]["ci_high"],
                    "contrast_mean": c["contrast"]["mean"],
                    "contrast_ci_low": c["contrast"]["ci_low"],
                    "contrast_ci_high": c["contrast"]["ci_high"],
                    "primary": (step, recover, stay) == (NEAR_STEP_FT, RECOVER_FT, NEAR_STAY_FT),
                })
    grid = pd.DataFrame(grid)
    grid.to_csv(args.out / "near_sensitivity.csv", index=False)

    rot = []
    for name in ("r1", "r2"):
        for h in ROTATION_HORIZONS:
            cells = three(df, com, ref, f"{name}_{h}")
            if h == HEADLINE_HORIZON:
                cells["committed"]["reading"] = a2_reading(cells["committed"]["ci_low"])
            rot += [{"rotator": name.upper(), **r} for r in tidy("rotator", "", h, cells)]
    rot = pd.DataFrame(rot).drop(columns=["check", "detail"]).reindex(
        columns=["rotator", "horizon", "group", "n", "n_ref", "mean", "ci_low", "ci_high",
                 "reading"])
    rot.to_csv(args.out / "near_rotator.csv", index=False)

    window = df["pass_window"]
    passed = [{"measure": "count", "who": what, "group": group, "n": int((mask & sel).sum())}
              for group, mask in (("committed", com), ("reference", ref))
              for what, sel in (("drives", pd.Series(True, index=df.index)),
                                ("pass_in_window", df["pass_in"]),
                                ("pass_to_man_left", df["pass_to_left"]),
                                ("post_pass_window", window))]
    for who, column in (("three", "pass3"), ("R1", "pass_r1")):
        cells = three(df, com & window, ref & window, column)
        n = cells["committed"]["n"]
        cells["committed"]["reading"] = ("LIMIT" if n < PASS_MIN_N
                                         else a2_reading(cells["committed"]["ci_low"]))
        passed += [{"measure": "after_pass", "who": who, "group": group,
                    "horizon": PASS_FRAMES / FPS, **cell} for group, cell in cells.items()]
    passed = pd.DataFrame(passed).reindex(
        columns=["measure", "who", "group", "horizon", "n", "n_ref", "mean", "ci_low", "ci_high",
                 "reading"])
    passed.to_csv(args.out / "near_pass.csv", index=False)

    groups = {"committed": com, "reference": ref, "committed_endpos": committed(df, endpos=True),
              "all_near_ok": pd.Series(True, index=df.index)}
    coherence = pd.DataFrame([{"group": name, "n": int(mask.sum()),
                               "n_coherent": int((mask & df["coherent"]).sum()),
                               "share": float(df.loc[mask, "coherent"].mean())}
                              for name, mask in groups.items()])
    coherence.to_csv(args.out / "near_matchup_coherence.csv", index=False)

    head = robust[np.isclose(robust["horizon"], WINDOW_S)]
    with pd.option_context("display.width", 200, "display.float_format", "{:+.2f}".format):
        print(head.to_string(index=False))
        print("\ngrid at 1.5 s, the committed group's own interval:")
        print(f"  {len(grid)} cells; reading {grid['reading'].value_counts().to_dict()}; "
              f"CI holds 0 in {int(((grid.ci_low <= 0) & (grid.ci_high >= 0)).sum())}, below 0 in "
              f"{int((grid.ci_high < 0).sum())}, above 0 in {int((grid.ci_low > 0).sum())}; "
              f"CI top {grid.ci_high.min():+.2f} to {grid.ci_high.max():+.2f}")
        print(coherence.to_string(index=False))
        print("\n13 a2 (i), the designated rotators:")
        print(rot.to_string(index=False))
        print("\n13 a2 (ii), the pass:")
        print(passed.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
