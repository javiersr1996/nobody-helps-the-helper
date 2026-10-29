"""The wind on a drive: where the defence moves in its first second, and who comes (P8).

SkillCorner's open bundle carries no help field on `drives` (the commercial Dynamic Events
do, as "help involvement"), so this module DERIVES one from tracking and publishes it as a
DEFINITION, never as a detector, under the same ruling as `scbasket.tagging`: it measures
displacement vectors and distances, not decisions. Nothing here says a defender chose to
help or left a man on purpose; "help movement" is the projection of a measured displacement.

Definitions, fixed once and reported with a sensitivity table next to every headline:

- **Horizon.** HORIZON_FRAMES (1.0 s) after the drive's `startFrame`, inside the same chance.
- **Drive frame.** The attacking frame (attacked hoop at negative x) mirrored in y so the
  ball handler's lateral motion over the horizon points to +y. Every origin and displacement
  the table and the flow field report is in that frame, so left- and right-hand drives
  pool. Shot zones are classified in the attacking frame, before the mirror.
- **Help movement.** For a defender who is NOT the ball handler's matchup, his OWN
  displacement over the horizon projected on the unit vector from where he started to
  where the ball handler IS at the horizon. Feet; positive means he moved toward where the
  ball was going. A defender who merely sinks with the drive scores low on it when he stands
  nearer the hoop line than where the handler ends up, and positive when he stands farther
  out (`target_bearing_x` < 0): above the ball, a plain sink counts as help movement.
  `scripts/help_wind.py` reports the helper rate standardised by that bearing.
- **Helper.** The non-matchup defender with the largest help movement, when that movement
  is at least HELP_FT. The table always describes the largest mover, so the threshold can
  be swept afterwards without recomputing anything.
- **The man he leaves.** The attacker the provider's `matchups` table assigns to the helper
  at `startFrame`: his separation from the helper at both ends, his distance to ANY
  defender at the horizon (and at the start, `left_nearest0`, the base to read it against),
  and whether that distance is at least OPEN_FT ("open").

Every drive keeps its row; the ones the cache cannot resolve carry a `status` other than
"ok" and NaN measurements, so the denominator is always visible.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scbasket.court import HOOP_X, zone_of
from scbasket.frames import N_SIDE, GameFrames, matchup_with_fallback

FPS = 25

#: The window after `startFrame` the defence is watched over, in seconds and in frames.
HORIZON_S = 1.0
HORIZON_FRAMES = int(HORIZON_S * FPS)

#: Feet of help movement that make the largest mover "the helper", and feet of clearance to
#: the nearest defender that make the man he leaves "open". Both are definitions, chosen
#: before the tables were read in full, and the sensitivity sweep reports the neighbours.
HELP_FT = 4.0
OPEN_FT = 6.0
SENSITIVITY_HELP_FT = (3.0, 4.0, 5.0, 6.0)
SENSITIVITY_HORIZON_S = (0.5, 1.0, 1.5)

#: The attacked hoop in the attacking frame; the drive frame keeps it in place (x is never
#: mirrored), so distances to the hoop read the same in both.
HOOP = np.array([HOOP_X, 0.0])

#: Flow-field cells, in feet: along the court from the hoop line, and across it.
CELL_X_FT = 8.0
CELL_Y_FT = 10.0
HALF_WIDTH_BIN_FT = 25.0  # the across bins run from -25 to +25 ft, 5 cells of CELL_Y_FT

#: The kernel field: grid step, Gaussian bandwidth, and the least kernel mass (in vectors'
#: worth) a cell needs before its mean displacement is kept, so the wind only blows where
#: defenders stood. The grid runs from FIELD_ALONG_FT past the hoop line (negative: behind
#: it) and across FIELD_ACROSS_FT, the drive frame's y.
GRID_FT = 1.5
BANDWIDTH_FT = 4.0
MIN_WEIGHT = 10.0
FIELD_ALONG_FT = (-3.0, 38.0)
FIELD_ACROSS_FT = (-24.0, 24.0)
#: The helper rate per defender is smoothed with the same kernel but kept only where
#: RATE_MIN_WEIGHT defenders' worth of mass started. At 80 the rate's binomial standard error
#: stays near 3.5 points, and the smoothing no longer bleeds into the corner-3 zone, where no
#: defender starts (at 30 it did).
RATE_MIN_WEIGHT = 80.0

STATUSES = ("ok", "no_frame", "no_horizon", "no_handler")


def _row_of(frame_idx: np.ndarray, frame: int) -> int:
    """Row holding `frame`, or -1 when the cache does not carry it."""
    r = int(np.searchsorted(frame_idx, frame))
    return r if r < len(frame_idx) and frame_idx[r] == frame else -1


def _zone(xy: np.ndarray) -> str:
    """Shot zone of one attacking-frame point."""
    return str(zone_of(np.array([xy[0]]), np.array([xy[1]]))[0])


def drive_endpoints(
    frames: GameFrames, drives: pd.DataFrame, horizon_frames: int = HORIZON_FRAMES
) -> pd.DataFrame:
    """One row per drive: the cache rows at `startFrame` and at the horizon, and a status.

    `status` is "ok" or the first test that failed, in order: "no_frame" (the start frame is
    not in the cache: dead, outside a usable chance, or not five on five), "no_horizon" (the
    horizon row is missing, not contiguous, or in another chance), "no_handler" (the
    provider's `ballhandlerId` is not among the five attackers of the start row).
    """
    fidx = frames.frame_idx
    rows = []
    for d in drives.itertuples(index=False):
        r0 = _row_of(fidx, int(d.startFrame))
        status, r1, slot = "ok", -1, -1
        if r0 < 0:
            status = "no_frame"
        else:
            r1 = r0 + horizon_frames
            contiguous = r1 < len(fidx) and fidx[r1] - fidx[r0] == horizon_frames
            if not contiguous or frames.chance_idx[r1] != frames.chance_idx[r0]:
                status, r1 = "no_horizon", -1
            else:
                hit = np.flatnonzero(frames.off_ids[r0] == d.ballhandlerId)
                if len(hit) == 0:
                    status = "no_handler"
                else:
                    slot = int(hit[0])
        rows.append((d.id, status, r0, r1, slot))
    return pd.DataFrame(rows, columns=["drive_id", "status", "row0", "row1", "handler_slot"])


def _scene(frames: GameFrames, matchup0: np.ndarray, r0: int, r1: int, s: int) -> dict:
    """Everything measured on one resolved drive, in the drive frame where it says so."""
    xy0 = frames.xy[r0].astype(np.float64)
    xy1 = frames.xy[r1].astype(np.float64)
    bh0, bh1 = xy0[s], xy1[s]
    flip = -1.0 if bh1[1] < bh0[1] else 1.0
    handler_def = int(matchup0[s])
    raw_matchup = frames.matchup[r0]

    vectors = []
    for j in range(N_SIDE):
        if j == handler_def:
            continue
        p0, p1 = xy0[N_SIDE + j], xy1[N_SIDE + j]
        disp = p1 - p0
        to_ball = bh1 - p0
        norm = float(np.linalg.norm(to_ball))
        move = float(disp @ (to_ball / norm)) if norm > 0 else 0.0
        vectors.append({
            "def_slot": j,
            "def_id": int(frames.def_ids[r0, j]),
            "origin_x": float(p0[0]),
            "origin_y": float(p0[1] * flip),
            "dx": float(disp[0]),
            "dy": float(disp[1] * flip),
            "help_move": move,
            "start_dist": float(np.linalg.norm(p0 - bh0)),
            "hoop_dist0": float(np.linalg.norm(p0 - HOOP)),
            "zone0": _zone(p0),
            "detected0": bool(frames.detected[r0, N_SIDE + j]),
            "detected1": bool(frames.detected[r1, N_SIDE + j]),
            # The target of the projection: how far it is, and how much of the way to it runs
            # along the court (x is never mirrored; negative is toward the hoop line).
            "target_dist": norm,
            "target_bearing_x": float(to_ball[0] / norm) if norm > 0 else 0.0,
        })
    top = max(vectors, key=lambda v: v["help_move"])
    j = top["def_slot"]

    left = {
        "left_slot": -1, "left_id": -1, "left_sep0": np.nan, "left_sep1": np.nan,
        "left_nearest0": np.nan, "left_nearest1": np.nan, "left_hoop1": np.nan, "left_zone1": "",
        "left_x1": np.nan, "left_y1": np.nan,
    }
    guarded = np.flatnonzero(raw_matchup == j)
    if len(guarded):
        k = int(guarded[0])
        a1 = xy1[k]
        left.update({
            "left_slot": k,
            "left_id": int(frames.off_ids[r0, k]),
            "left_sep0": float(np.linalg.norm(xy0[k] - xy0[N_SIDE + j])),
            "left_sep1": float(np.linalg.norm(a1 - xy1[N_SIDE + j])),
            "left_nearest0": float(np.linalg.norm(xy0[N_SIDE:] - xy0[k], axis=1).min()),
            "left_nearest1": float(np.linalg.norm(xy1[N_SIDE:] - a1, axis=1).min()),
            "left_hoop1": float(np.linalg.norm(a1 - HOOP)),
            "left_zone1": _zone(a1),
            "left_x1": float(a1[0]),
            "left_y1": float(a1[1] * flip),
        })

    drive = {
        "handler_slot": s,
        "handler_def_slot": handler_def,
        "flip": flip,
        "handler_x0": float(bh0[0]), "handler_y0": float(bh0[1] * flip),
        "handler_x1": float(bh1[0]), "handler_y1": float(bh1[1] * flip),
        "handler_hoop0": float(np.linalg.norm(bh0 - HOOP)),
        "handler_hoop1": float(np.linalg.norm(bh1 - HOOP)),
        "help_move_max": top["help_move"],
        "n_movers_3ft": int(sum(v["help_move"] >= 3.0 for v in vectors)),
        **{f"helper_{key}": value for key, value in top.items()},
        **left,
    }
    return {"drive": drive, "vectors": vectors}


def _measure(
    frames: GameFrames, drives: pd.DataFrame, horizon_frames: int
) -> tuple[list[dict], list[dict]]:
    endpoints = drive_endpoints(frames, drives, horizon_frames)
    matchup0 = matchup_with_fallback(frames)
    table, vectors = [], []
    for d, e in zip(drives.itertuples(index=False), endpoints.itertuples(index=False),
                    strict=True):
        base = {
            "drive_id": d.id,
            "game": int(d.gameId),
            "start_frame": int(d.startFrame),
            "handler_id": int(d.ballhandlerId),
            "end_type": d.endType,
            "category": d.category,
            "provider_direction": d.direction,
            "status": e.status,
        }
        if e.status != "ok":
            table.append(base)
            continue
        scene = _scene(frames, matchup0[e.row0], e.row0, e.row1, e.handler_slot)
        table.append({**base, **scene["drive"]})
        for v in scene["vectors"]:
            vectors.append({"drive_id": d.id, "game": int(d.gameId), **v})
    return table, vectors


def help_table(
    frames: GameFrames,
    drives: pd.DataFrame,
    horizon_frames: int = HORIZON_FRAMES,
    help_ft: float = HELP_FT,
    open_ft: float = OPEN_FT,
) -> pd.DataFrame:
    """One row per drive: the largest mover among the non-matchup defenders, and the man he left.

    `has_helper` applies `help_ft` to `helper_help_move`; `left_open` and `left_open0` apply
    `open_ft` to `left_nearest1` and `left_nearest0`. All are recomputable from the row, which
    is how the sensitivity sweep works. Unresolved drives keep their row with `status` set and
    NaN measurements.
    """
    rows, _ = _measure(frames, drives, horizon_frames)
    table = pd.DataFrame(rows)
    for column in ("helper_help_move", "left_nearest0", "left_nearest1"):  # absent if none resolved
        if column not in table:
            table[column] = np.nan
    table["has_helper"] = table["helper_help_move"] >= help_ft
    table["left_open0"] = table["left_nearest0"] >= open_ft
    table["left_open"] = table["left_nearest1"] >= open_ft
    return table


def help_vectors(
    frames: GameFrames, drives: pd.DataFrame, horizon_frames: int = HORIZON_FRAMES
) -> pd.DataFrame:
    """One row per (resolved drive, non-matchup defender): origin and displacement, drive frame."""
    _, vectors = _measure(frames, drives, horizon_frames)
    return pd.DataFrame(vectors)


def flow_field(
    vectors: pd.DataFrame,
    cell_x_ft: float = CELL_X_FT,
    cell_y_ft: float = CELL_Y_FT,
    min_n: int = 15,
) -> pd.DataFrame:
    """Mean displacement per cell of the drive frame: the wind map.

    Cells tile x from the hoop line (`origin_x - HOOP_X`, so 0 is the baseline side of the
    hoop and positive runs toward half court) in `cell_x_ft` steps, and y from
    -HALF_WIDTH_BIN_FT to +HALF_WIDTH_BIN_FT in `cell_y_ft` steps. `consistency` is the
    length of the mean vector over the mean length, 1 when every defender in the cell moved
    the same way and 0 when their moves cancel. Cells under `min_n` vectors are dropped.
    """
    x = vectors["origin_x"].to_numpy() - HOOP_X
    y = vectors["origin_y"].to_numpy()
    cx = np.floor(x / cell_x_ft).astype(int)
    cy = np.floor((y + HALF_WIDTH_BIN_FT) / cell_y_ft).astype(int)
    frame = vectors.assign(cell_x=cx, cell_y=cy)
    length = np.hypot(frame["dx"], frame["dy"])
    frame = frame.assign(length=length)
    grouped = frame.groupby(["cell_x", "cell_y"])
    out = grouped.agg(
        n=("dx", "size"),
        mean_dx=("dx", "mean"),
        mean_dy=("dy", "mean"),
        mean_length=("length", "mean"),
        mean_help_move=("help_move", "mean"),
    ).reset_index()
    out = out[out["n"] >= min_n].copy()
    out["x_center"] = HOOP_X + (out["cell_x"] + 0.5) * cell_x_ft
    out["y_center"] = -HALF_WIDTH_BIN_FT + (out["cell_y"] + 0.5) * cell_y_ft
    out["consistency"] = np.hypot(out["mean_dx"], out["mean_dy"]) / out["mean_length"]
    return out.reset_index(drop=True)


def field_grid(grid_ft: float = GRID_FT) -> tuple[np.ndarray, np.ndarray]:
    """The kernel field's axes: feet from the hoop line along the court, and y across it."""
    along = np.arange(FIELD_ALONG_FT[0], FIELD_ALONG_FT[1] + grid_ft, grid_ft)
    across = np.arange(FIELD_ACROSS_FT[0], FIELD_ACROSS_FT[1] + grid_ft, grid_ft)
    return along, across


def kernel_field(
    vectors: pd.DataFrame,
    helper: np.ndarray,
    along: np.ndarray,
    across: np.ndarray,
    bandwidth_ft: float = BANDWIDTH_FT,
    min_weight: float = MIN_WEIGHT,
    rate_min_weight: float = RATE_MIN_WEIGHT,
) -> pd.DataFrame:
    """Gaussian-weighted mean displacement and helper rate on a grid of the drive frame.

    The grid is `along` (feet from the hoop line, as `flow_field` bins x) by `across` (drive
    frame y). One row per cell, along outer and across inner: its centre `x` (drive frame,
    `HOOP_X` + along, like every origin in `vectors`) and `y`, the kernel mass `weight` (in
    vectors' worth), `mean_dx`, `mean_dy`, and `helper_rate`, the kernel mean of the 0/1
    `helper` flag, i.e. the share of the defenders starting nearby who are the helper. The
    mass depends on positions only, so both share it. The means are NaN where `weight` is
    under `min_weight` (the rate: `rate_min_weight`); `weight` is kept so nobody re-applies a
    threshold.
    """
    gx, gy = np.meshgrid(along, across, indexing="ij")
    px = vectors["origin_x"].to_numpy(float) - HOOP_X
    py = vectors["origin_y"].to_numpy(float)
    d2 = (gx.ravel()[:, None] - px[None, :]) ** 2 + (gy.ravel()[:, None] - py[None, :]) ** 2
    w = np.exp(-0.5 * d2 / bandwidth_ft**2)
    mass = w.sum(axis=1)
    safe = np.maximum(mass, 1e-9)

    def mean(values: np.ndarray, least: float) -> np.ndarray:
        return np.where(mass < least, np.nan, w @ np.asarray(values, float) / safe)

    return pd.DataFrame({
        "x": HOOP_X + gx.ravel(), "y": gy.ravel(), "weight": mass,
        "mean_dx": mean(vectors["dx"], min_weight),
        "mean_dy": mean(vectors["dy"], min_weight),
        "helper_rate": mean(helper, rate_min_weight),
    })
