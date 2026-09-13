"""League-wide shot value surface from the 293-game season aggregates.

Usage: uv run python scripts/build_value_surface.py
Writes reports/value_surface_zones.csv (zone, attempts, points, PPS) and
reports/value_surface_grid.csv (one row per grid cell: x, y, zone, value).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from scbasket.court import make_grid
from scbasket.io import Dataset
from scbasket.value import league_zone_values, surface_from_zones, zone_totals

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "opendata-basketball"
REPORTS = ROOT / "reports"

# Acceptance criteria from tasks/todo.md P0.4.
VALUED_ZONES = ("restricted_area", "paint_non_ra", "mid_range", "corner_3", "wing_3", "top_3")
PPS_RANGE = (0.5, 1.6)
MAX_ATTEMPTS_DEVIATION = 0.01


def main() -> int:
    dataset = Dataset(DATA)
    shots_agg = dataset.aggregates("shots")

    totals = zone_totals(shots_agg)
    zone_values = league_zone_values(shots_agg)
    totals["pps"] = totals["zone"].map(zone_values)

    REPORTS.mkdir(exist_ok=True)
    totals.to_csv(REPORTS / "value_surface_zones.csv", index=False)

    print("=== League zone values (293 games, 2025-2026 ACB season) ===")
    print(totals.to_string(index=False))

    ok = True

    # Criterion 1 + 3: 6 zones carry value, all within [0.5, 1.6] PPS.
    valued = totals.set_index("zone").loc[list(VALUED_ZONES), "pps"]
    print(f"\n6 valued zones: {list(VALUED_ZONES)}")
    out_of_range = valued[(valued < PPS_RANGE[0]) | (valued > PPS_RANGE[1])]
    if out_of_range.empty:
        print(f"All 6 values fall inside {PPS_RANGE} points per shot: OK")
    else:
        ok = False
        print(f"FAILS: values outside {PPS_RANGE}:\n{out_of_range.to_string()}")

    # Criterion 2: restricted_area highest, mid_range lowest.
    highest, lowest = valued.idxmax(), valued.idxmin()
    if highest == "restricted_area" and lowest == "mid_range":
        print("restricted_area is the highest and mid_range the lowest: OK")
    else:
        ok = False
        print(
            f"FAILS: highest is {highest} ({valued[highest]:.3f}), "
            f"lowest is {lowest} ({valued[lowest]:.3f})"
        )

    # Criterion 4: zone attempts reconcile against the `attempts` column.
    rows = shots_agg.loc[shots_agg["team_name"] != "total"]
    attempts_col_sum = rows["attempts"].sum()
    zone_attempts_sum = totals["attempts"].sum()
    deviation = abs(zone_attempts_sum - attempts_col_sum) / attempts_col_sum
    print(
        f"\nSum of zone attempts: {zone_attempts_sum} vs attempts column: "
        f"{attempts_col_sum} -> deviation {deviation:.4%}"
    )
    if deviation < MAX_ATTEMPTS_DEVIATION:
        print("Deviation is below 1%: OK")
    else:
        ok = False
        print("FAILS: deviation is at or above 1%")

    grid = make_grid()
    surface = surface_from_zones(grid, zone_values)
    grid_df = pd.DataFrame({
        "x": grid.centers[:, 0],
        "y": grid.centers[:, 1],
        "zone": grid.zone,
        "value": surface.values,
    })
    grid_df.to_csv(REPORTS / "value_surface_grid.csv", index=False)
    print(f"\nWrote {len(totals)} zones and {len(grid_df)} grid cells to reports/.")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
