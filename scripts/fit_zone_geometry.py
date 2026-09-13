"""Grid search for the undocumented court.py geometry parameters.

The data provider does not publish the restricted-area radius or the angle
boundaries that split corner_3 / wing_3 / top_3. This script sweeps them
against the shots of the 10 published games and picks the combination that
maximizes agreement between zone_of(location) and region_to_zone(region).

Run with: uv run python scripts/fit_zone_geometry.py
"""

from __future__ import annotations

import dataclasses
import time
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.court import FIBA, ZONES, region_to_zone, zone_of
from scbasket.io import Dataset

DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "raw" / "opendata-basketball"

# Grid search ranges. ra_radius_ft is the range fixed by the task (3-6 ft).
# The two angle boundaries get a generously wide range around the plausible
# court geometry (a straight-out shot is 0 deg, square to the baseline is
# 90 deg): corner_angle_deg somewhere past the free-throw-line extended,
# wing_top_angle_deg somewhere near the edge of the lane extended.
RA_RADIUS_GRID = np.arange(3.0, 6.01, 0.1)
CORNER_ANGLE_GRID = np.arange(60.0, 89.01, 0.5)
WING_TOP_ANGLE_GRID = np.arange(10.0, 40.01, 0.5)


def load_shots(root: Path) -> pd.DataFrame:
    """Concatenate the shots table of the 10 published games."""
    dataset = Dataset(root)
    frames = [dataset.events(gid)["shots"] for gid in dataset.game_ids]
    shots = pd.concat(frames, ignore_index=True)
    return shots.loc[shots["location"].notna() & shots["region"].notna()].copy()


def main() -> None:
    if not (DATA_ROOT / "data" / "matches.json").exists():
        raise SystemExit(f"No dataset at {DATA_ROOT}. Clone it with scripts/fetch_data.py first.")

    shots = load_shots(DATA_ROOT)
    xy = np.array(shots["location"].tolist())
    x, y = xy[:, 0], xy[:, 1]
    expected_zone = shots["region"].map(region_to_zone).to_numpy()
    is_three = shots["three"].to_numpy()

    print(f"Shots with a valid location and region: {len(shots)}")
    unmapped = sorted(set(shots.loc[expected_zone == "other", "region"].dropna().unique()))
    if unmapped:
        print(f"WARNING: regions falling back to 'other': {unmapped}")

    t0 = time.time()
    best = None
    for ra_radius in RA_RADIUS_GRID:
        for corner_angle in CORNER_ANGLE_GRID:
            for wing_top_angle in WING_TOP_ANGLE_GRID:
                geom = dataclasses.replace(
                    FIBA,
                    ra_radius_ft=ra_radius,
                    corner_angle_deg=corner_angle,
                    wing_top_angle_deg=wing_top_angle,
                )
                predicted = zone_of(x, y, geom)
                agreement = (predicted == expected_zone).mean()
                if best is None or agreement > best[0]:
                    best = (agreement, ra_radius, corner_angle, wing_top_angle)
    elapsed = time.time() - t0

    zone_agreement, ra_radius, corner_angle, wing_top_angle = best
    n_combos = RA_RADIUS_GRID.size * CORNER_ANGLE_GRID.size * WING_TOP_ANGLE_GRID.size
    print(f"Grid search over {n_combos} combinations took {elapsed:.1f}s")
    print(
        f"Best geometry: ra_radius_ft={ra_radius:.2f}, "
        f"corner_angle_deg={corner_angle:.2f}, wing_top_angle_deg={wing_top_angle:.2f}"
    )

    best_geom = dataclasses.replace(
        FIBA,
        ra_radius_ft=ra_radius,
        corner_angle_deg=corner_angle,
        wing_top_angle_deg=wing_top_angle,
    )
    predicted = zone_of(x, y, best_geom)
    three_zones = {"corner_3", "wing_3", "top_3", "far", "backcourt"}
    predicted_three = np.isin(predicted, list(three_zones))
    three_agreement = (predicted_three == is_three).mean()

    print(
        f"Zone agreement (zone_of vs region_to_zone):  {zone_agreement:.4f} ({zone_agreement:.1%})"
    )
    print(
        f"Three agreement (zone_of vs shots.three):   {three_agreement:.4f} ({three_agreement:.1%})"
    )

    print()
    print("Agreement with the geometry currently hardcoded in court.py (FIBA defaults):")
    predicted_default = zone_of(x, y, FIBA)
    default_zone_agreement = (predicted_default == expected_zone).mean()
    predicted_default_three = np.isin(predicted_default, list(three_zones))
    default_three_agreement = (predicted_default_three == is_three).mean()
    print(f"  zone agreement:  {default_zone_agreement:.4f} ({default_zone_agreement:.1%})")
    print(f"  three agreement: {default_three_agreement:.4f} ({default_three_agreement:.1%})")

    mismatches = shots.loc[predicted_default != expected_zone]
    if len(mismatches):
        print()
        print(f"Mismatches with FIBA defaults: {len(mismatches)}")
        print(
            mismatches.assign(predicted=predicted_default[predicted_default != expected_zone])
            .groupby(["region", "predicted"])
            .size()
            .to_string()
        )

    assert set(ZONES) >= set(expected_zone), "region_to_zone produced a label outside ZONES"


if __name__ == "__main__":
    main()
