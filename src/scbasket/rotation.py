"""The second help: does anyone cover the man the helper left, measured against a placebo (P8).

Sibling of `scbasket.wind`, which keeps the first second. Same ruling: this module measures
displacements and distances, never decisions. "Rotation" names the projection of a defender's
own displacement, and "covers" the identity of the nearest defender; nothing here says anyone
chose to rotate, to stay, or to leave a man.

Definitions, fixed once in module constants and reported with a sensitivity table:

- **Population.** The resolved drives of `wind.help_table` with a man left (`left_slot >= 0`).
  `helped` is the table's `has_helper`; on the other drives the "helper" is the largest
  sub-threshold mover and the "man left" is HIS man, which makes them a comparable.
- **The three others.** The defenders who are neither the ball handler's matchup nor the
  helper. They are the only ones who could rotate onto the man left.
- **Rotation toward a target.** For one other defender and a horizon T (frames after the
  drive's `startFrame`), his OWN displacement over [0, T] projected on the unit vector from
  where he started to where the target IS at T. Feet; positive means he moved toward where
  the target ended up. `to_left` has the man left as target.
- **Placebo.** The mean of the same projection over the off-ball attackers who are neither
  the ball handler, nor the man left, nor the defender's own man by the RAW matchup at
  `startFrame` (the provider's table, before the nearest-defender fallback). Same defender,
  same drive, same displacement: only the target changes, so the paired difference
  `to_left - placebo` isolates "toward HIM" from "toward anyone off the ball".
- **Window.** Contiguous frames from `startFrame` inside the same chance. A window cut by a
  gap or a chance boundary drops the horizons it cannot reach and keeps the row, with NaN
  where the measurement does not exist.
- **Nearest.** At each horizon, which defender is nearest to the man left: `helper` (he
  recovered), `handler_def` (the ball handler's matchup) or `third` (one of the three others).
- **Clearance.** The man left's distance to his nearest defender at CLEARANCE_FRAMES after
  the start (0, 0.5, 1.0, 1.5, 2.0 s), for the base rate of "open".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scbasket.frames import N_SIDE, GameFrames
from scbasket.wind import _row_of

#: Horizons the rotation is read at, in frames: 1.0, 1.5 and 2.0 s.
ROTATION_HORIZONS = (25, 38, 50)
#: The horizon the headline quotes (1.5 s).
HEADLINE_HORIZON = 38
#: Frames after `startFrame` at which the man left's clearance is recorded: 0 to 2.0 s.
CLEARANCE_FRAMES = (0, 12, 25, 38, 50)

NEAREST_WHO = ("helper", "handler_def", "third")


def _window_end(frames: GameFrames, r0: int, n: int) -> int:
    """Last row reachable from `r0` within `n` frames, contiguous and inside the same chance."""
    fidx, chance = frames.frame_idx, frames.chance_idx
    end = r0
    while (end + 1 < len(fidx) and end + 1 - r0 <= n and fidx[end + 1] - fidx[end] == 1
           and chance[end + 1] == chance[r0]):
        end += 1
    return end


def _projection(p0: np.ndarray, p1: np.ndarray, target: np.ndarray) -> float:
    """Displacement `p0 -> p1` projected on the unit vector from `p0` to `target`, in feet."""
    to_target = target - p0
    norm = float(np.linalg.norm(to_target))
    return float((p1 - p0) @ (to_target / norm)) if norm > 0 else 0.0


def rotation_table(
    frames: GameFrames,
    drives: pd.DataFrame,
    help_table: pd.DataFrame,
    horizons: tuple[int, ...] = ROTATION_HORIZONS,
    fixed_targets: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The three others' rotation toward the man left and toward the placebo, per drive.

    `help_table` is `wind.help_table` of the same game; only the drives of `drives` that
    resolved with a man left are measured. `fixed_targets` (a sensitivity) reads every target,
    the man left and the placebo attackers, where it stands at `startFrame` instead of at the
    horizon, so no attacker's run after the start can move `to_left` or `placebo`; it changes
    nothing in `drives_out`. Returns `(pairs, drives_out)`:

    - `pairs`: one row per (drive, other defender, horizon) with `to_left` and `placebo` (NaN
      when the defender has no placebo target).
    - `drives_out`: one row per drive with `window_frames`, then per horizon T the best mover
      toward each target (`rot_left_T`, `rot_placebo_T`), `nearest_who_T`, `nearest_dist_T`,
      where the man left stands (`left_x_T`, `left_y_T`, the drive frame of `wind`: y
      mirrored by the table's `flip`), and the man left's clearance `left_clear_t` at each of
      CLEARANCE_FRAMES.

    A horizon the window cannot reach is absent from `pairs` and NaN / "" in `drives_out`.
    """
    ok = help_table[
        (help_table["status"] == "ok") & (help_table["left_slot"] >= 0)
        & help_table["drive_id"].isin(drives["id"])
    ]
    reach = max(*horizons, *CLEARANCE_FRAMES)
    xy = frames.xy.astype(np.float64)
    pairs, rows = [], []
    for d in ok.itertuples(index=False):
        r0 = _row_of(frames.frame_idx, int(d.start_frame))
        window = _window_end(frames, r0, reach) - r0
        slot, handler_def = int(d.handler_slot), int(d.handler_def_slot)
        helper, left = int(d.helper_def_slot), int(d.left_slot)
        raw_matchup = frames.matchup[r0]
        others = [x for x in range(N_SIDE) if x not in (handler_def, helper)]
        row = {
            "drive_id": d.drive_id, "game": int(d.game), "helped": bool(d.has_helper),
            "end_type": d.end_type, "helper_help_move": float(d.helper_help_move),
            "left_id": int(d.left_id), "window_frames": window,
        }
        for t in CLEARANCE_FRAMES:
            clear = np.nan
            if t <= window:
                clear = float(np.linalg.norm(xy[r0 + t, N_SIDE:] - xy[r0 + t, left], axis=1).min())
            row[f"left_clear_{t}"] = clear
        for horizon in horizons:
            row.update({f"rot_left_{horizon}": np.nan, f"rot_placebo_{horizon}": np.nan,
                        f"nearest_who_{horizon}": "", f"nearest_dist_{horizon}": np.nan,
                        f"left_x_{horizon}": np.nan, f"left_y_{horizon}": np.nan})
            if window < horizon:
                continue
            r1 = r0 + horizon
            row[f"left_x_{horizon}"] = float(xy[r1, left, 0])
            row[f"left_y_{horizon}"] = float(xy[r1, left, 1] * d.flip)  # the drive frame
            best_left, best_placebo = -np.inf, -np.inf
            rt = r0 if fixed_targets else r1  # where the targets are read
            for x in others:
                p0, p1 = xy[r0, N_SIDE + x], xy[r1, N_SIDE + x]
                to_left = _projection(p0, p1, xy[rt, left])
                own = set(np.flatnonzero(raw_matchup == x).tolist())
                targets = [a for a in range(N_SIDE) if a not in (slot, left) and a not in own]
                placebo = (float(np.mean([_projection(p0, p1, xy[rt, a]) for a in targets]))
                           if targets else np.nan)
                pairs.append({"drive_id": d.drive_id, "game": int(d.game),
                              "helped": bool(d.has_helper), "horizon": horizon,
                              "def_slot": x, "to_left": to_left, "placebo": placebo})
                best_left = max(best_left, to_left)
                if not np.isnan(placebo):
                    best_placebo = max(best_placebo, placebo)
            dist = np.linalg.norm(xy[r1, N_SIDE:] - xy[r1, left], axis=1)
            nearest = int(dist.argmin())
            who = "helper" if nearest == helper else (
                "handler_def" if nearest == handler_def else "third")
            row.update({
                f"rot_left_{horizon}": best_left,
                f"rot_placebo_{horizon}": best_placebo if np.isfinite(best_placebo) else np.nan,
                f"nearest_who_{horizon}": who,
                f"nearest_dist_{horizon}": float(dist.min()),
            })
        rows.append(row)
    return pd.DataFrame(pairs), pd.DataFrame(rows)
