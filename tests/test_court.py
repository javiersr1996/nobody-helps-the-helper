"""Tests for scbasket.court: geometry, zone classification and the grid."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scbasket.court import (
    FIBA,
    ZONES,
    make_grid,
    region_to_zone,
    zone_of,
)
from scbasket.io import Dataset

DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "raw" / "opendata-basketball"
HAS_REAL_DATA = (DATA_ROOT / "data" / "matches.json").exists()

# Six known points, none of which need the real dataset.
KNOWN_POINTS = {
    "under_hoop": ((-40.76, 0.0), "restricted_area"),
    "three_point_corner": ((-44.0, -23.0), "corner_3"),
    "three_point_top": ((-15.76, 0.0), "top_3"),
    "elbow_mid_range": ((-26.9, 9.0), "mid_range"),
    "backcourt": ((10.0, 0.0), "backcourt"),
    "outside_the_court": ((-30.0, 30.0), "other"),
}


def test_zone_of_known_points():
    x = np.array([pt[0][0] for pt in KNOWN_POINTS.values()])
    y = np.array([pt[0][1] for pt in KNOWN_POINTS.values()])
    expected = [pt[1] for pt in KNOWN_POINTS.values()]
    result = zone_of(x, y)
    assert list(result) == expected


@pytest.mark.parametrize(("name", "point"), [(k, v) for k, v in KNOWN_POINTS.items()])
def test_zone_of_known_points_individually(name, point):
    (x, y), expected = point
    result = zone_of(np.array([x]), np.array([y]))
    assert result[0] == expected, f"{name}: expected {expected}, got {result[0]}"


def test_zone_of_is_vectorized_over_arrays():
    x = np.linspace(-45.0, 40.0, 50)
    y = np.linspace(-24.0, 24.0, 50)
    result = zone_of(x, y)
    assert result.shape == x.shape
    assert set(result).issubset(set(ZONES))


def test_zone_of_scalar_shape_matches_input():
    result = zone_of(np.array(-40.76), np.array(0.0))
    assert result.shape == ()
    assert str(result) == "restricted_area"


def test_region_to_zone_covers_documented_regions():
    expected = {
        "ra": "restricted_area",
        "key": "paint_non_ra",
        "left wing three": "wing_3",
        "right wing three": "wing_3",
        "middle three": "top_3",
        "left corner three": "corner_3",
        "right corner three": "corner_3",
        "left wing two": "mid_range",
        "right wing two": "mid_range",
        "middle two": "mid_range",
        "left corner two": "mid_range",
        "right corner two": "mid_range",
        "backcourt": "backcourt",
        "far": "far",
    }
    for region, zone in expected.items():
        assert region_to_zone(region) == zone
    assert set(expected.values()).issubset(set(ZONES))


def test_region_to_zone_unknown_falls_back_to_other():
    assert region_to_zone("not-a-real-region") == "other"
    assert region_to_zone(None) == "other"


def test_make_grid_default_cell_size_is_about_2250_cells():
    grid = make_grid(1.0)
    assert 2000 <= len(grid.centers) <= 2500
    assert grid.centers.shape == (len(grid.centers), 2)
    assert grid.zone.shape == (len(grid.centers),)
    assert grid.cell_ft == 1.0


def test_make_grid_only_covers_the_offensive_half():
    grid = make_grid(1.0)
    assert np.all(grid.centers[:, 0] <= 0)
    assert np.all(np.abs(grid.centers[:, 1]) <= FIBA.half_width_ft)


def test_make_grid_zones_are_valid_labels():
    grid = make_grid(1.0)
    assert set(grid.zone).issubset(set(ZONES))
    # The offensive half-court grid never crosses half court or leaves the court.
    assert "backcourt" not in set(grid.zone)
    assert "other" not in set(grid.zone)


def test_make_grid_works_with_a_coarser_cell_size():
    grid = make_grid(2.0)
    assert grid.cell_ft == 2.0
    assert len(grid.centers) > 0
    assert len(grid.centers) < len(make_grid(1.0).centers)


@pytest.mark.data
@pytest.mark.skipif(not HAS_REAL_DATA, reason="requires the opendata-basketball dataset")
def test_zone_agreement_on_real_shots():
    """zone_of(location) must agree with region_to_zone(region) on >= 95% of shots."""
    dataset = Dataset(DATA_ROOT)
    frames = [dataset.events(gid)["shots"] for gid in dataset.game_ids]
    shots = pd.concat(frames, ignore_index=True)
    shots = shots.loc[shots["location"].notna() & shots["region"].notna()]

    xy = np.array(shots["location"].tolist())
    predicted = zone_of(xy[:, 0], xy[:, 1])
    expected = shots["region"].map(region_to_zone).to_numpy()

    agreement = (predicted == expected).mean()
    assert agreement >= 0.95, f"zone agreement {agreement:.1%} is below the 95% threshold"


@pytest.mark.data
@pytest.mark.skipif(not HAS_REAL_DATA, reason="requires the opendata-basketball dataset")
def test_three_point_agreement_on_real_shots():
    """The three-point split of zone_of must agree with shots.three on >= 99% of shots."""
    dataset = Dataset(DATA_ROOT)
    frames = [dataset.events(gid)["shots"] for gid in dataset.game_ids]
    shots = pd.concat(frames, ignore_index=True)
    shots = shots.loc[shots["location"].notna() & shots["region"].notna()]

    xy = np.array(shots["location"].tolist())
    predicted = zone_of(xy[:, 0], xy[:, 1])
    predicted_three = np.isin(predicted, ["corner_3", "wing_3", "top_3", "far", "backcourt"])

    agreement = (predicted_three == shots["three"].to_numpy()).mean()
    assert agreement >= 0.99, f"three-point agreement {agreement:.1%} is below the 99% threshold"
