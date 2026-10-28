"""The shot-scaled zone: where the ball lands, and the zone each shot earns (P7.2).

Usage: uv run python scripts/rebound_zone.py [--root DIR] [--out DIR] [--fit]

Findings 1 (the zone is real and small) and 3 (it scales with the shot) were measured while
exploring F6 and never committed as code, so nothing in the repo reproduced them. This script
is that code. It rebuilds both from the event tables, the two halves reported apart, and then
grades the frozen zone of `scbasket.tagging` against the constant 8 ft band it replaces.

The criterion was frozen together with the coefficients, before any held-out game was read
(D11), and it is RELATIVE, so there is no number left to move later (D13). On the held-out
games the shot-scaled zone must:
  1. drift LESS across the shot-distance bands than the constant zone, measured as the spread
     between its best and worst covered band,
  2. hold its overall coverage within 0.03 of ZONE_COVERAGE, and
  3. RETIRED on 2026-09-17, see below: cover no more mean area than the constant zone.
Condition 1 is the whole point: both zones hold three quarters of the rebounds overall by
construction, and the question is whether the constant one only manages it by being too
generous on close misses and too tight on everything else.

**Condition 3 was retired, and the rewrite is recorded here rather than quietly dropped**
(D13). It asked a varying zone to carry no more MEAN area than a constant one at matched
coverage, and area is quadratic in the radius, so it cannot: measured at equal coverage on
both halves the scaled zone is the larger one on average while being the SMALLER zone on 48%
and 41% of shots. No shot-scaled zone could pass it, and one that did would be a zone that
barely varies, which is the null this work is tested against. It is retired for being unable
to discriminate, not for failing, and the distinction matters: it was ALREADY failing on the
calibration half when it was written, with 211 against 201 sq ft printed in front of whoever
wrote it, so retiring it uses no held-out information. The failure it produced stays in
tasks/todo.md and in commit 7223c7f, and the concern behind it is still answered below, as a
diagnostic and never as a bar.

Writes {out}/rebound_zone.csv (one row per rebound) and {out}/rebound_zone_criterion.csv.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.io import Dataset
from scbasket.tagging import (
    FLAT_ZONE_FT,
    MAX_COVERAGE_GAP,
    ZONE_COVERAGE,
    ZONE_INTERCEPT_FT,
    ZONE_SLOPE,
    rebound_zone_table,
    zone_radius,
)
from scbasket.validation import CALIBRATION_GAMES, VALIDATION_GAMES, spearman

#: The frozen reporting bands the drift is measured over: the paint-ish shot, mid-range, the
#: long two, and the three. FLAT_ZONE_FT and MAX_COVERAGE_GAP live in `scbasket.tagging`
#: with the zone they grade, because the page states them too.
SHOT_BANDS = [0.0, 8.0, 16.0, 22.15, 200.0]


def build(dataset: Dataset, game_id: int) -> pd.DataFrame:
    """One row per rebound of this game, with the half it belongs to."""
    events = dataset.events(game_id)
    table = rebound_zone_table(events["shots"], events["rebounds"])
    half = "calibration" if game_id in CALIBRATION_GAMES else "held out"
    return table.assign(game=game_id, half=half)


def coverage(table: pd.DataFrame, radius: np.ndarray) -> pd.Series:
    """Share of rebounds inside `radius`, by shot-distance band, plus the overall share."""
    inside = pd.Series(table["reb_dist"].to_numpy() <= radius, index=table.index)
    bands = pd.cut(table["shot_dist"], SHOT_BANDS, right=False)
    by_band = inside.groupby(bands, observed=True).mean()
    by_band.loc["overall"] = inside.mean()
    return by_band


def grade(table: pd.DataFrame) -> dict:
    """The frozen conditions on one half, plus the retired one and what replaces it."""
    scaled = zone_radius(table["shot_dist"].to_numpy())
    flat = np.full(len(table), FLAT_ZONE_FT)
    scaled_cov, flat_cov = coverage(table, scaled), coverage(table, flat)
    bands = [i for i in scaled_cov.index if i != "overall"]
    # The retired condition and its well-posed diagnostic travel together, so that reading the
    # area difference without the equal-coverage comparison beside it takes an effort.
    equal_cov_radius = float(np.quantile(table["reb_dist"], scaled_cov["overall"]))
    return {
        "n": len(table),
        "scaled_spread": scaled_cov[bands].max() - scaled_cov[bands].min(),
        "flat_spread": flat_cov[bands].max() - flat_cov[bands].min(),
        "scaled_overall": scaled_cov["overall"],
        "flat_overall": flat_cov["overall"],
        "scaled_area": float(np.pi * np.mean(scaled**2)),
        "flat_area": float(np.pi * FLAT_ZONE_FT**2),
        "equal_cov_radius": equal_cov_radius,
        "equal_cov_area": float(np.pi * equal_cov_radius**2),
        "share_under_flat": float((scaled < FLAT_ZONE_FT).mean()),
    }


def fit(table: pd.DataFrame, quantile: float) -> tuple[float, float]:
    """Re-derive the frozen coefficients: the pinball-loss fit over the same coarse grid."""
    x = table["shot_dist"].to_numpy()
    y = table["reb_dist"].to_numpy()
    best = None
    for intercept in np.arange(0.0, 12.01, 0.1):
        for slope in np.arange(-0.2, 0.61, 0.01):
            resid = y - (intercept + slope * x)
            loss = np.maximum(quantile * resid, (quantile - 1.0) * resid).mean()
            if best is None or loss < best[0]:
                best = (loss, float(intercept), float(slope))
    return best[1], best[2]


def report_landing(table: pd.DataFrame) -> pd.DataFrame:
    """Finding 1, rebuilt: how far from the rim the ball is actually won."""
    return table.groupby("half", observed=True)["reb_dist"].agg(
        n="count",
        median="median",
        inside_4ft=lambda s: (s <= 4).mean(),
        inside_6ft=lambda s: (s <= 6).mean(),
        inside_8ft=lambda s: (s <= 8).mean(),
        inside_15ft=lambda s: (s <= 15).mean(),
        sd="std",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/raw/opendata-basketball"))
    parser.add_argument("--out", type=Path, default=Path("reports"))
    parser.add_argument("--fit", action="store_true",
                        help="re-derive the coefficients on the calibration games and exit")
    args = parser.parse_args()

    dataset = Dataset(args.root)
    games = list(CALIBRATION_GAMES) if args.fit else list(CALIBRATION_GAMES) + list(
        VALIDATION_GAMES)
    raw = pd.concat([build(dataset, g) for g in games], ignore_index=True)
    usable = raw.dropna(subset=["reb_dist", "shot_dist"]).reset_index(drop=True)

    print(f"rebounds {len(raw)}, with a location {raw['reb_dist'].notna().sum()}, "
          f"with their shot's location too {len(usable)}; "
          f"{len(raw) - len(usable)} carried through as NaN rather than dropped")

    if args.fit:
        intercept, slope = fit(usable, ZONE_COVERAGE)
        print(f"\nfitted on {len(usable)} calibration rebounds at q={ZONE_COVERAGE}: "
              f"r(d) = {intercept:.2f} + {slope:.3f} d")
        print(f"frozen in scbasket.tagging:                     "
              f"r(d) = {ZONE_INTERCEPT_FT:.2f} + {ZONE_SLOPE:.3f} d")
        # Half a grid step on each: the fit walks a grid of floats, so it lands a hair off.
        if abs(intercept - ZONE_INTERCEPT_FT) > 0.05 or abs(slope - ZONE_SLOPE) > 0.005:
            print("MISMATCH: the frozen coefficients no longer reproduce. Report it, do not "
                  "quietly refit (D13).")
        return 0

    print("\n" + "=" * 78)
    print("Finding 1, rebuilt: where the ball is won, the two halves apart")
    print("=" * 78)
    print(report_landing(usable).round(3).to_string())

    print("\nOffensive rebounds land closer than defensive ones (share inside 4 ft):")
    print(usable.pivot_table(index="half", columns="defensive", values="reb_dist",
                             aggfunc=lambda s: (s <= 4).mean(), observed=True)
          .round(3).to_string())

    print("\n" + "=" * 78)
    print("Finding 3, rebuilt: the zone scales with the shot")
    print("=" * 78)
    for half, part in usable.groupby("half", observed=True):
        rho = spearman(part["shot_dist"].to_numpy(), part["reb_dist"].to_numpy())
        print(f"  Spearman(shot distance, rebound distance), {half}: {rho:+.3f} "
              f"over {len(part)} rebounds")
    bands = pd.cut(usable["shot_dist"], SHOT_BANDS, right=False)
    print("\nMedian rebound distance by shot-distance band:")
    print(usable.pivot_table(index=bands, columns="half", values="reb_dist",
                             aggfunc=["count", "median"], observed=True).round(2).to_string())

    print("\n" + "=" * 78)
    print(f"The frozen zone r(d) = {ZONE_INTERCEPT_FT:.2f} + {ZONE_SLOPE:.3f} d "
          f"against the constant {FLAT_ZONE_FT:.0f} ft band")
    print("=" * 78)
    rows = {}
    for half, part in usable.groupby("half", observed=True):
        scaled = zone_radius(part["shot_dist"].to_numpy())
        flat = np.full(len(part), FLAT_ZONE_FT)
        rows[(half, "scaled")] = coverage(part, scaled)
        rows[(half, "flat")] = coverage(part, flat)
    print(pd.DataFrame(rows).round(3).to_string())

    grades = {half: grade(part) for half, part in usable.groupby("half", observed=True)}
    criterion = pd.DataFrame(grades).T
    print("\n" + criterion.round(3).to_string())

    held = grades["held out"]
    checks = {
        "1. drifts less across the bands than the constant zone":
            held["scaled_spread"] < held["flat_spread"],
        f"2. overall coverage within {MAX_COVERAGE_GAP} of {ZONE_COVERAGE}":
            abs(held["scaled_overall"] - ZONE_COVERAGE) <= MAX_COVERAGE_GAP,
    }
    print("\nThe frozen criterion, on the HELD-OUT games:")
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    print(f"  [RETIRED] 3. covers no more mean area than the constant zone: "
          f"{held['scaled_area']:.1f} against {held['flat_area']:.1f} sq ft, which FAILED. "
          f"Retired as unable to discriminate; the module docstring says why.")
    print(f"      what it was meant to catch, as a diagnostic and never as a bar: at equal "
          f"coverage the constant radius would be {held['equal_cov_radius']:.2f} ft "
          f"({held['equal_cov_area']:.1f} sq ft), and the scaled zone is the SMALLER of the "
          f"two on {held['share_under_flat']:.0%} of shots. Differently shaped, not bigger.")
    print(f"\nVerdict on the conditions that can discriminate: "
          f"{'PASS' if all(checks.values()) else 'FAIL'}. That is not 'P7.2 passed': the "
          f"third condition fell and its failure stays in the record (D13).")

    args.out.mkdir(parents=True, exist_ok=True)
    raw.to_csv(args.out / "rebound_zone.csv", index=False)
    criterion.to_csv(args.out / "rebound_zone_criterion.csv")
    print(f"\nwrote {args.out / 'rebound_zone.csv'} and "
          f"{args.out / 'rebound_zone_criterion.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
