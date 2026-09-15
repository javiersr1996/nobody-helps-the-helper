"""Tests for scbasket.epc: epc_share."""

from __future__ import annotations

import numpy as np
import pytest

from scbasket.court import ZONES, make_grid
from scbasket.epc import epc_share
from scbasket.value import ValueSurface, surface_from_zones

GRID = make_grid(6.0)  # a coarse grid keeps these tests fast; the geometry itself is unused


def _surface(zone_values: dict[str, float], smooth_ft: float = 0.0) -> ValueSurface:
    return surface_from_zones(GRID, zone_values, smooth_ft=smooth_ft)


def test_epc_share_is_the_value_weighted_mean_of_p_off():
    rng = np.random.default_rng(0)
    values = rng.uniform(0.5, 1.5, len(GRID.centers))
    surface = ValueSurface(grid=GRID, values=values, zone_values={})
    p_off = rng.uniform(0.0, 1.0, (5, len(GRID.centers)))

    result = epc_share(p_off, surface)

    expected = (p_off * values[None, :]).sum(axis=1) / values.sum()
    np.testing.assert_allclose(result, expected, rtol=1e-12)
    assert np.all(result >= 0.0) and np.all(result <= 1.0)


def test_epc_share_is_exactly_one_or_zero_at_full_or_no_offensive_control():
    surface = _surface(dict.fromkeys(ZONES, 1.0))
    n = len(GRID.centers)

    all_controlled = np.ones((3, n))
    none_controlled = np.zeros((3, n))

    np.testing.assert_array_equal(epc_share(all_controlled, surface), 1.0)
    np.testing.assert_array_equal(epc_share(none_controlled, surface), 0.0)


def test_epc_share_ignores_control_of_zero_value_cells():
    """Zones priced at 0 (backcourt, far, other) must not move the share either way."""
    zone_values = {z: (0.0 if z in ("backcourt", "far", "other") else 1.0) for z in ZONES}
    surface = _surface(zone_values)
    zero_value_cells = np.isin(GRID.zone, ["backcourt", "far", "other"])
    assert zero_value_cells.any() and (~zero_value_cells).any()

    # Full control, but ONLY of the zero-value cells: the rest of the court is uncontrolled.
    p_off = zero_value_cells.astype(float)[None, :]

    assert epc_share(p_off, surface)[0] == 0.0


def test_epc_share_raises_on_a_cell_count_mismatch_and_returns_nan_for_a_worthless_surface():
    surface = _surface(dict.fromkeys(ZONES, 1.0))
    with pytest.raises(ValueError):
        epc_share(np.zeros((2, len(GRID.centers) - 1)), surface)

    worthless = _surface(dict.fromkeys(ZONES, 0.0))
    result = epc_share(np.ones((2, len(GRID.centers))), worthless)
    assert np.all(np.isnan(result))
