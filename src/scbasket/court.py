"""FIBA half-court geometry and shot zone classification.

Origin at the court center, feet throughout. x runs along the length of the
court (half length = 45.93 ft), y runs along the width (half width = 24.61
ft). Attack direction is toward negative x: HOOP_X is the hoop the offense
shoots at.

zone_of(location) works directly on shots.location because that field is
already given in this attacking frame (verified against shots.distance,
which matches hypot(x - HOOP_X, y) to within 0.01 ft across all 10 games).
Tracking data is NOT pre-oriented this way -- converting a tracking frame to
the attacking frame (using possessions.leftHoop) is orient(), P0.3, not
implemented here yet.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from scbasket.quality import COURT_LENGTH_FT, COURT_WIDTH_FT

# Public geometry constants (FIBA rulebook, feet).
HOOP_X = -40.76  # attacked hoop, 1.575 m from the baseline
THREE_RADIUS_FT = 22.15  # 6.75 m
CORNER_LINE_Y_FT = 21.65  # corner line, 0.90 m from the sideline

ZONES = (
    "restricted_area",
    "paint_non_ra",
    "mid_range",
    "corner_3",
    "wing_3",
    "top_3",
    "backcourt",
    "far",
    "other",
)

# NOTE(P0.3): orient(xy, left_hoop) belongs here -- broadcast tracking frame
# to the attacking frame used by zone_of. Not implemented in this task.


@dataclass(frozen=True)
class CourtGeometry:
    """FIBA half-court measurements plus the boundaries used by zone_of.

    hoop_x, three_radius_ft and corner_line_y_ft mirror the module-level
    constants above. half_length_ft/half_width_ft, paint_half_width_ft and
    paint_length_ft come straight from the FIBA rulebook (28x15 m court,
    4.9x5.8 m lane) and are not fitted.

    ra_radius_ft, corner_angle_deg and wing_top_angle_deg are NOT published
    by the data provider and were fit by grid search in
    scripts/fit_zone_geometry.py against the 1433 shots (of 1459 total
    across the 10 published games) that carry both a location and a
    provider region label. See zone_of below for the resulting agreement.

    far_dist_ft and bounds_margin_ft are read off the data directly (the
    gap between the farthest ordinary three and the "far" shots, and the
    tracking noise beyond the physical sideline/baseline) rather than fit.
    """

    hoop_x: float = HOOP_X
    three_radius_ft: float = THREE_RADIUS_FT
    corner_line_y_ft: float = CORNER_LINE_Y_FT
    half_length_ft: float = COURT_LENGTH_FT / 2
    half_width_ft: float = COURT_WIDTH_FT / 2
    paint_half_width_ft: float = 8.04  # FIBA lane, 4.9 m wide
    paint_length_ft: float = 19.03  # FIBA lane, baseline to free-throw line, 5.80 m
    bounds_margin_ft: float = 1.0  # tolerance for tracking noise past the court edge
    far_dist_ft: float = 32.0  # frontcourt heaves beyond this distance become "far"

    # Fit by scripts/fit_zone_geometry.py (grid search over the ranges documented there):
    ra_radius_ft: float = 4.1
    corner_angle_deg: float = 78.0
    wing_top_angle_deg: float = 22.5


FIBA = CourtGeometry()


def zone_of(x: np.ndarray, y: np.ndarray, geom: CourtGeometry = FIBA) -> np.ndarray:
    """Classify shot locations (feet, attacking frame) into one of ZONES.

    Vectorized over numpy arrays of any matching shape. Classification
    order:

    1. Points outside the court rectangle (with geom.bounds_margin_ft of
       slack for tracking noise) are "other".
    2. Points with x > 0 (past half court, away from the attacked hoop) are
       "backcourt".
    3. Within geom.ra_radius_ft of the hoop: "restricted_area".
    4. Inside the free-throw lane rectangle, outside the restricted area:
       "paint_non_ra".
    5. Otherwise, a shot counts as a three if it clears the arc
       (dist_from_hoop >= three_radius_ft) OR sits in the straight corner
       segment of the line (|y| > corner_line_y_ft) -- the actual FIBA line
       is straight near the corners and only becomes an arc farther out.
       Three-point attempts split by angle from the hoop (0 deg straight
       out front, 90 deg square to the baseline): beyond far_dist_ft is
       "far", then "corner_3" (angle >= corner_angle_deg), "top_3"
       (angle < wing_top_angle_deg) or "wing_3" (in between).
    6. Anything else inside the arc is "mid_range".

    Fit against the 1433 shots with both a location and a region label
    across the 10 published games (see scripts/fit_zone_geometry.py):
    98.6% agreement with region_to_zone(region), 99.4% agreement between
    being classified as a three (corner_3/wing_3/top_3/far/backcourt) and
    the provider's own `three` field. Both are grid-search maxima over
    ra_radius_ft in [3, 6] ft and the two angle boundaries.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    out = np.full(x.shape, "other", dtype="<U16")

    in_bounds = (
        (x >= -geom.half_length_ft - geom.bounds_margin_ft)
        & (x <= geom.half_length_ft + geom.bounds_margin_ft)
        & (np.abs(y) <= geom.half_width_ft + geom.bounds_margin_ft)
    )
    backcourt = in_bounds & (x > 0)
    out[backcourt] = "backcourt"

    front = in_bounds & ~backcourt
    dx = x - geom.hoop_x
    dist = np.hypot(dx, y)
    angle_deg = np.degrees(np.arctan2(np.abs(y), dx))

    ra = front & (dist <= geom.ra_radius_ft)
    out[ra] = "restricted_area"

    free_throw_line_x = -geom.half_length_ft + geom.paint_length_ft
    paint = front & ~ra & (x <= free_throw_line_x) & (np.abs(y) <= geom.paint_half_width_ft)
    out[paint] = "paint_non_ra"

    remaining = front & ~ra & ~paint
    is_three = remaining & ((dist >= geom.three_radius_ft) | (np.abs(y) > geom.corner_line_y_ft))

    far = is_three & (dist > geom.far_dist_ft)
    out[far] = "far"

    corner = is_three & ~far & (angle_deg >= geom.corner_angle_deg)
    out[corner] = "corner_3"

    top = is_three & ~far & ~corner & (angle_deg < geom.wing_top_angle_deg)
    out[top] = "top_3"

    wing = is_three & ~far & ~corner & ~top
    out[wing] = "wing_3"

    mid = remaining & ~is_three
    out[mid] = "mid_range"

    return out


# shots.region -> ZONES, from the 14 values documented in
# data/raw/opendata-basketball/docs/data_dictionary/shots.md.
_REGION_TO_ZONE = {
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


def region_to_zone(region: str) -> str:
    """Map the provider's shots.region label to one of ZONES.

    Unknown labels (including None/NaN, which the provider leaves for a
    small number of shots) fall back to "other".
    """
    return _REGION_TO_ZONE.get(region, "other")


@dataclass(frozen=True)
class Grid:
    """A regular lattice of cell centers over the offensive half-court, zoned.

    centers is (G, 2) feet, attacking frame, offensive half only (x <= 0).
    zone is (G,) with one ZONES label per row of centers, from zone_of.
    """

    cell_ft: float
    centers: np.ndarray
    zone: np.ndarray


def make_grid(cell_ft: float = 1.0, geom: CourtGeometry = FIBA) -> Grid:
    """Build a regular grid of cell centers over the offensive half-court.

    Cells tile x in [-half_length_ft, 0] and y in [-half_width_ft,
    half_width_ft], centered within each cell_ft x cell_ft square. With
    cell_ft=1.0 this yields about 2250 cells (45.93 x 49.21 ft of half
    court). Any cell_ft works the same way, just with a coarser or finer
    lattice.
    """
    n_x = int(round(geom.half_length_ft / cell_ft))
    n_y = int(round(2 * geom.half_width_ft / cell_ft))
    xs = -geom.half_length_ft + (np.arange(n_x) + 0.5) * cell_ft
    ys = -geom.half_width_ft + (np.arange(n_y) + 0.5) * cell_ft
    xx, yy = np.meshgrid(xs, ys, indexing="ij")
    centers = np.column_stack([xx.ravel(), yy.ravel()])
    zone = zone_of(centers[:, 0], centers[:, 1], geom)
    return Grid(cell_ft=cell_ft, centers=centers, zone=zone)
