"""League-wide shot value surface, built from the 293-game season aggregates.

The value comes from a whole ACB season (293 games), not the 10 tracked games
(1,433 shots): a season gives a stable points-per-shot estimate per zone,
while 10 games would not. This is why the aggregate layer exists in this
project at all -- see D5 in tasks/todo.md.

Two known traps in the aggregates, both handled here:
- Traded players get one row per team PLUS a season-total row (team_name ==
  "total"). Summing that row too double counts them.
- attempts follows the FIBA box-score convention and excludes field goal
  attempts missed while the shooter was fouled (those are free throw trips);
  total_points includes the extra free throw scored on an and-one. Neither
  quirk needs correcting here: both sides of PPS_zone = points / attempts
  are read straight off the aggregates, consistently.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from scbasket.court import ZONES, Grid

# Aggregate column prefixes (under "zone_<prefix>_attempts" / "_total_points")
# summed to build each zone's value. corner_3 and wing_3 merge their left/right
# splits: the league is symmetric, so a corner (or wing) three carries the same
# value on either side of the floor.
_ZONE_PREFIXES: dict[str, tuple[str, ...]] = {
    "restricted_area": ("restricted_area",),
    "paint_non_ra": ("paint_non_ra",),
    "mid_range": ("mid_range",),
    "corner_3": ("corner_3_left", "corner_3_right"),
    "wing_3": ("wing_3_left", "wing_3_right"),
    "top_3": ("top_3",),
    "backcourt": ("backcourt",),
    "far": ("far",),
    "other": ("other",),
}
assert set(_ZONE_PREFIXES) == set(ZONES)

# Zones with no shot value by modeling decision (backcourt heaves, desperation
# "far" attempts, unclassified "other" shots): fixed at 0.0 rather than priced
# off their (thin, noisy) share of season attempts.
_ZERO_VALUE_ZONES = ("backcourt", "far", "other")


def zone_totals(shots_agg: pd.DataFrame) -> pd.DataFrame:
    """Attempts and points by zone, summed over the 293-game season aggregates.

    Drops the season-total rows (team_name == "total") so traded players are
    not double counted. One row per scbasket.court.ZONES label, columns zone,
    attempts, points. Feeds both league_zone_values (PPS = points / attempts)
    and the season-attempts reconciliation check in
    scripts/build_value_surface.py.
    """
    rows = shots_agg.loc[shots_agg["team_name"] != "total"]
    records = []
    for zone in ZONES:
        prefixes = _ZONE_PREFIXES[zone]
        attempts = sum(rows[f"zone_{p}_attempts"].sum() for p in prefixes)
        points = sum(rows[f"zone_{p}_total_points"].sum() for p in prefixes)
        records.append({"zone": zone, "attempts": attempts, "points": points})
    return pd.DataFrame.from_records(records)


def league_zone_values(shots_agg: pd.DataFrame) -> dict[str, float]:
    """Points per shot (PPS) by zone, from the 293-game season aggregates.

    PPS_zone = sum(zone_total_points) / sum(zone_attempts) over player-team
    rows only (see zone_totals). backcourt, far and other are fixed at 0.0
    regardless of their real season PPS (see _ZERO_VALUE_ZONES).

    Returns one entry per ZONES label.
    """
    totals = zone_totals(shots_agg)
    return {
        row.zone: 0.0 if row.zone in _ZERO_VALUE_ZONES else row.points / row.attempts
        for row in totals.itertuples()
    }


@dataclass(frozen=True)
class ValueSurface:
    """Expected points per shot at each cell of a court grid.

    grid is the lattice values was built over (scbasket.court.Grid). values
    is (G,), points per shot per cell, after Gaussian smoothing across zone
    boundaries (see surface_from_zones). zone_values keeps the unsmoothed
    per-zone PPS the surface was built from.
    """

    grid: Grid
    values: np.ndarray
    zone_values: dict[str, float]


def _gaussian_kernel1d(sigma: float) -> np.ndarray:
    """A normalized 1D Gaussian kernel, radius ceil(3 sigma) samples (>= 1)."""
    radius = max(1, int(np.ceil(3 * sigma)))
    offsets = np.arange(-radius, radius + 1, dtype=float)
    kernel = np.exp(-0.5 * (offsets / sigma) ** 2)
    return kernel / kernel.sum()


def _convolve_axis(field: np.ndarray, kernel: np.ndarray, axis: int) -> np.ndarray:
    """1D same-shape convolution along one axis of a 2D array.

    Symmetric padding (mirroring the field about each edge, including the
    edge cell itself) is what makes the smoothed field integrate to exactly
    the same total as the stepped one, verified numerically to float
    precision (~1e-14) for arbitrary fields and kernel widths. Edge
    (replicate) padding does NOT have this property in general -- it only
    conserves the sum when the field is locally constant near the boundary,
    which a stepped zone field is not. Wrap (circular) padding also
    conserves the sum exactly, but blends each edge with the far side of the
    court (baseline with half-court line); mirroring instead blends each
    edge only with its own nearby cells, which is the physically sensible
    choice here (a court boundary behaves like a wall, not a wraparound).
    """
    pad = len(kernel) // 2
    pad_width = [(0, 0)] * field.ndim
    pad_width[axis] = (pad, pad)
    padded = np.pad(field, pad_width, mode="symmetric")
    return np.apply_along_axis(lambda line: np.convolve(line, kernel, mode="valid"), axis, padded)


def _smooth_on_grid(grid: Grid, field: np.ndarray, smooth_ft: float) -> np.ndarray:
    """Separable Gaussian blur of a per-cell field over grid's regular x/y lattice.

    grid.centers is ordered x-major (all y values for x[0], then all y values
    for x[1], ...): the order make_grid builds via
    meshgrid(xs, ys, indexing="ij").ravel(). Recovered here from the unique x/y
    coordinates rather than assumed, so a change in make_grid's layout would
    surface as a shape mismatch, not silent corruption.
    """
    xs = np.unique(grid.centers[:, 0])
    ys = np.unique(grid.centers[:, 1])
    n_x, n_y = len(xs), len(ys)
    if n_x * n_y != field.size:
        raise ValueError("grid.centers is not a regular x-major lattice")

    field_2d = field.reshape(n_x, n_y)
    kernel = _gaussian_kernel1d(smooth_ft / grid.cell_ft)
    field_2d = _convolve_axis(field_2d, kernel, axis=0)
    field_2d = _convolve_axis(field_2d, kernel, axis=1)
    return field_2d.reshape(-1)


def surface_from_zones(
    grid: Grid, zone_values: dict[str, float], smooth_ft: float = 1.5
) -> ValueSurface:
    """Build a smoothed value surface from per-zone PPS.

    Zones are broadcast to a stepped per-cell field, then blurred with a
    separable Gaussian of standard deviation smooth_ft (feet), implemented
    with numpy only (no scipy), so that zone boundaries (the three-point arc,
    the restricted area) don't leave an artificial step in the field.
    """
    stepped = np.array([zone_values[z] for z in grid.zone], dtype=float)
    if smooth_ft <= 0:
        return ValueSurface(grid=grid, values=stepped, zone_values=dict(zone_values))

    smoothed = _smooth_on_grid(grid, stepped, smooth_ft)
    return ValueSurface(grid=grid, values=smoothed, zone_values=dict(zone_values))
