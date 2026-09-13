"""Tests for scbasket.value: the league-wide shot value surface."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import REAL_DATASET_ROOT, requires_real_dataset

from scbasket.court import ZONES, make_grid
from scbasket.io import Dataset
from scbasket.value import ValueSurface, league_zone_values, surface_from_zones, zone_totals

VALUED_ZONES = ("restricted_area", "paint_non_ra", "mid_range", "corner_3", "wing_3", "top_3")
ZERO_VALUE_ZONES = ("backcourt", "far", "other")

# Every zone prefix a shots-aggregates row carries columns for (corner_3 and
# wing_3 only exist split into left/right in the real CSV, see
# data/raw/opendata-basketball/docs/aggregates_columns.md).
_PREFIXES = (
    "restricted_area", "paint_non_ra", "mid_range",
    "corner_3_left", "corner_3_right", "wing_3_left", "wing_3_right",
    "top_3", "backcourt", "far", "other",
)

# (attempts, points) per prefix for two team rows of one traded player.
_TEAM_A = {
    "restricted_area": (10, 20), "paint_non_ra": (5, 6), "mid_range": (8, 8),
    "corner_3_left": (2, 3), "corner_3_right": (2, 3),
    "wing_3_left": (3, 3), "wing_3_right": (3, 3), "top_3": (4, 6),
    "backcourt": (1, 0), "far": (1, 3), "other": (0, 0),
}
_TEAM_B = {
    "restricted_area": (6, 10), "paint_non_ra": (3, 4), "mid_range": (4, 4),
    "corner_3_left": (1, 3), "corner_3_right": (1, 0),
    "wing_3_left": (2, 3), "wing_3_right": (2, 0), "top_3": (2, 3),
    "backcourt": (0, 0), "far": (0, 0), "other": (1, 0),
}
# Deliberately implausible: if the "total" row leaked into a sum, it would be
# unmistakable (10x either team row on every zone).
_TOTAL_ROW = {prefix: (1000, 2000) for prefix in _PREFIXES}


def _row(team_name: str, stats: dict[str, tuple[int, int]]) -> dict:
    row: dict[str, object] = {"team_name": team_name}
    row["attempts"] = sum(attempts for attempts, _ in stats.values())
    for prefix, (attempts, points) in stats.items():
        row[f"zone_{prefix}_attempts"] = attempts
        row[f"zone_{prefix}_total_points"] = points
    return row


@pytest.fixture
def synthetic_shots_agg() -> pd.DataFrame:
    """Two per-team rows for one traded player plus their season-total row.

    The total row (team_name == "total") must be excluded from every sum:
    league_zone_values and zone_totals should behave as if only TeamA and
    TeamB existed.
    """
    return pd.DataFrame([
        _row("TeamA", _TEAM_A),
        _row("TeamB", _TEAM_B),
        _row("total", _TOTAL_ROW),
    ])


def test_zone_totals_excludes_the_total_row(synthetic_shots_agg):
    totals = zone_totals(synthetic_shots_agg).set_index("zone")
    # restricted_area: 10+6 attempts, 20+10 points (not the 1000/2000 total row).
    assert totals.loc["restricted_area", "attempts"] == 16
    assert totals.loc["restricted_area", "points"] == 30
    assert totals.loc["other", "attempts"] == 1
    assert set(totals.index) == set(ZONES)


def _expected_pps(*prefixes: str) -> float:
    """PPS for the given prefixes, summed over TeamA and TeamB only (no total row)."""
    attempts = sum(_TEAM_A[p][0] + _TEAM_B[p][0] for p in prefixes)
    points = sum(_TEAM_A[p][1] + _TEAM_B[p][1] for p in prefixes)
    return points / attempts


def test_league_zone_values_merges_left_right_and_excludes_total(synthetic_shots_agg):
    values = league_zone_values(synthetic_shots_agg)

    assert set(values) == set(ZONES)
    # corner_3 = corner_3_left + corner_3_right, summed over TeamA and TeamB only.
    assert values["corner_3"] == pytest.approx(_expected_pps("corner_3_left", "corner_3_right"))
    assert values["wing_3"] == pytest.approx(_expected_pps("wing_3_left", "wing_3_right"))
    assert values["restricted_area"] == pytest.approx(_expected_pps("restricted_area"))
    for zone in ZERO_VALUE_ZONES:
        assert values[zone] == 0.0


def test_league_zone_values_all_valued_zones_positive(synthetic_shots_agg):
    values = league_zone_values(synthetic_shots_agg)
    for zone in VALUED_ZONES:
        assert values[zone] > 0.0


def test_surface_from_zones_shape_and_zero_smoothing_matches_stepped():
    grid = make_grid(cell_ft=2.0)
    zone_values = {zone: 1.0 for zone in ZONES}
    surface = surface_from_zones(grid, zone_values, smooth_ft=0.0)

    assert isinstance(surface, ValueSurface)
    assert surface.values.shape == (len(grid.centers),)
    assert np.all(surface.values == 1.0)


def test_smoothed_surface_integrates_to_the_same_total_as_stepped():
    grid = make_grid(cell_ft=1.0)
    zone_values = {
        "restricted_area": 1.2, "paint_non_ra": 1.0, "mid_range": 0.75,
        "corner_3": 1.3, "wing_3": 1.05, "top_3": 1.05,
        "backcourt": 0.0, "far": 0.0, "other": 0.0,
    }
    stepped = surface_from_zones(grid, zone_values, smooth_ft=0.0)
    smoothed = surface_from_zones(grid, zone_values, smooth_ft=1.5)

    total_stepped = stepped.values.sum()
    total_smoothed = smoothed.values.sum()
    relative_diff = abs(total_smoothed - total_stepped) / abs(total_stepped)
    assert relative_diff < 1e-6, relative_diff
    # Smoothing should actually move values near zone boundaries, not be a no-op.
    assert not np.allclose(smoothed.values, stepped.values)


@pytest.mark.data
@requires_real_dataset
def test_league_zone_values_on_real_season_aggregates():
    """Acceptance criteria for P0.4, against the real 293-game season aggregates."""
    dataset = Dataset(REAL_DATASET_ROOT)
    shots_agg = dataset.aggregates("shots")

    zone_values = league_zone_values(shots_agg)
    valued = {zone: zone_values[zone] for zone in VALUED_ZONES}
    print("\nLeague zone values (293 games, PPS):")
    for zone, pps in valued.items():
        print(f"  {zone}: {pps:.3f}")

    assert all(0.5 <= pps <= 1.6 for pps in valued.values()), valued
    assert max(valued, key=valued.get) == "restricted_area", valued
    assert min(valued, key=valued.get) == "mid_range", valued

    totals = zone_totals(shots_agg)
    rows = shots_agg.loc[shots_agg["team_name"] != "total"]
    deviation = abs(totals["attempts"].sum() - rows["attempts"].sum()) / rows["attempts"].sum()
    print(f"attempts reconciliation deviation: {deviation:.4%}")
    assert deviation < 0.01, deviation
