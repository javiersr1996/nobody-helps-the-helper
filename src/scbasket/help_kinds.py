"""Near help and long help by the last: the published helper, split by the coach's two kinds (A8).

Sibling of `scbasket.wind` and `scbasket.rotation`, under the same ruling: this module measures
displacements and distances, never decisions. "Stunt", "committed" and "long help" name
geometric conditions fixed below, not intentions.

The coach separates two things the published "helper" pools:

- **Near help.** The off-ball defender NEAREST the ball steps toward the handler. A stunt if he
  is back with his man 2.0 s later, committed if he is not.
- **Long help.** The handler beats his defender and the LAST defender (the off-ball defender
  farthest from the ball) is in the drive's path. The question is who rotates to the last's man.

Definitions, fixed once in module constants and reported with a sensitivity. All at the
drive's start frame r0 unless said; the horizons are those of `rotation`, headline 1.5 s.

- **Off-ball defenders.** The four who are not the handler's matchup (with fallback).
- **NEAREST / LAST.** The off-ball defender nearest / farthest from the ball at r0. Each one's
  man is his RAW provider matchup at r0 (no fallback); a drive without one, or where that man
  is the handler, is dropped and counted (`*_status`).
- **BEATEN** (primary, geometric). At some frame in [r0, r0 + 1.5 s] the handler is closer to
  the hoop than the handler's defender. Sensitivity: the provider's `drives.blowby`.
- **LONG** (primary). BEATEN and, at some frame in the same 1.5 s, the last is within
  PATH_FT of the handler AND closer to the hoop than the handler. Sensitivities: PATH_FT 5 and
  8, BEATEN by `blowby`, and the first probe's rule (the last moves LAST_MOVE_FT toward the
  handler in 1.0 s, with no path condition).
- **LONG reference.** Not BEATEN and the last moves less than STAY_FT toward the handler in
  1.0 s (stays home).
- **NEAR help.** The nearest moves at least NEAR_STEP_FT toward the handler within 1.0 s (the
  `wind` help-movement projection, best frame). STUNT if at 2.0 s his distance to his man is at
  most his distance at r0 plus RECOVER_FT; COMMITTED otherwise. Undefined (counted, excluded)
  without the 2.0 s window or without his man. **NEAR reference.** The nearest moves less than
  NEAR_STAY_FT toward the handler, on the same population.
- **Published helper class.** LAST / NEAREST / OTHER by who `wind.help_table` named, and
  recovered / committed by the same 2.0 s rule applied to his own raw man.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scbasket.frames import N_SIDE, GameFrames, matchup_with_fallback
from scbasket.rotation import HEADLINE_HORIZON, _projection, _window_end
from scbasket.wind import HOOP, _row_of

#: BEATEN and LONG look at [r0, r0 + 1.5 s]; the movements at 1.0 s; the stunt rule at 2.0 s.
BEAT_FRAMES = HEADLINE_HORIZON
MOVE_FRAMES = 25
OUTCOME_FRAMES = 50

#: The last is "in the drive's path" within this many feet of the handler (and nearer the hoop).
PATH_FT = 6.0
SENSITIVITY_PATH_FT = (5.0, 8.0)
#: The first probe's rule for long help, kept as a sensitivity.
LAST_MOVE_FT = 4.0
#: The last "stays home" under this projection toward the handler at 1.0 s.
STAY_FT = 2.0
#: The nearest "helps" from this projection on, and is the reference under NEAR_STAY_FT.
NEAR_STEP_FT = 2.0
NEAR_STAY_FT = 1.0
#: Recovered: back within this much of the start distance to his man.
RECOVER_FT = 1.0

#: (kind column, reference column, who is the helper) of every analysis of the script.
ANALYSES = {
    "long": ("long", "long_ref", "last"),
    "long_path5": ("long_path5", "long_ref", "last"),
    "long_path8": ("long_path8", "long_ref", "last"),
    "long_blowby": ("long_blowby", "long_ref_blowby", "last"),
    "long_move4": ("long_move4", "long_ref", "last"),
    "near_stunt": ("near_stunt", "near_ref", "near"),
    "near_committed": ("near_committed", "near_ref", "near"),
}

STATUSES = ("ok", "no_man", "man_is_handler", "no_window")


def _man(raw: np.ndarray, defender: int) -> int:
    """The attacker the provider assigns to `defender` at r0, or -1."""
    hit = np.flatnonzero(raw == defender)
    return int(hit[0]) if len(hit) else -1


def _status(man: int, handler: int, window: int, need: int) -> str:
    if man < 0:
        return "no_man"
    if man == handler:
        return "man_is_handler"
    return "ok" if window >= need else "no_window"


def _recovered(xy: np.ndarray, r0: int, defender: int, man: int) -> bool:
    """At 2.0 s the defender is no farther from his man than at r0 plus RECOVER_FT."""
    start = float(np.linalg.norm(xy[r0, N_SIDE + defender] - xy[r0, man]))
    end = float(np.linalg.norm(xy[r0 + OUTCOME_FRAMES, N_SIDE + defender]
                               - xy[r0 + OUTCOME_FRAMES, man]))
    return end <= start + RECOVER_FT


def drive_kinds(frames: GameFrames, drives: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    """One row per resolved drive of `table` with every flag, slot and drop reason.

    `table` is `wind.help_table` of the same game. Flags are False wherever the drive's
    `last_status` / `near_status` is not "ok", so the drops never enter a kind or a reference.
    """
    xy = frames.xy.astype(np.float64)
    ball = frames.ball[:, :2].astype(np.float64)
    matchup0 = matchup_with_fallback(frames)
    blowby = dict(zip(drives["id"], drives["blowby"].astype(bool), strict=True))
    rows = []
    for d in table[table["status"] == "ok"].itertuples(index=False):
        r0 = _row_of(frames.frame_idx, int(d.start_frame))
        s, hd = int(d.handler_slot), int(d.handler_def_slot)
        assert matchup0[r0][s] == hd
        raw = frames.matchup[r0]
        window = _window_end(frames, r0, OUTCOME_FRAMES) - r0
        off = [x for x in range(N_SIDE) if x != hd]
        dist = {x: float(np.linalg.norm(xy[r0, N_SIDE + x] - ball[r0])) for x in off}
        last, near = max(dist, key=dist.get), min(dist, key=dist.get)
        last_man, near_man = _man(raw, last), _man(raw, near)
        last_status = _status(last_man, s, window, BEAT_FRAMES)
        near_status = _status(near_man, s, window, OUTCOME_FRAMES)
        helper = int(d.helper_def_slot)
        helper_man = int(d.left_slot)
        row = {
            "drive_id": d.drive_id, "game": int(d.game), "start_frame": int(d.start_frame),
            "handler_slot": s, "handler_def_slot": hd, "window_frames": window,
            "has_helper": bool(d.has_helper), "blowby": blowby[d.drive_id],
            "helper_slot": helper, "helper_man": helper_man,
            "helper_class": ("last" if helper == last
                             else "nearest" if helper == near else "other"),
            "helper_stance": "",
            "last_slot": last, "last_man": last_man, "last_status": last_status,
            "near_slot": near, "near_man": near_man, "near_status": near_status,
            "beaten_geo": False, "path5": False, "path6": False, "path8": False,
            "last_move": np.nan, "near_move": np.nan,
        }
        if helper_man >= 0 and helper_man != s and window >= OUTCOME_FRAMES:
            row["helper_stance"] = ("recovered" if _recovered(xy, r0, helper, helper_man)
                                    else "committed")
        if last_status == "ok":
            ts = range(BEAT_FRAMES + 1)
            handler_hoop = [float(np.linalg.norm(xy[r0 + t, s] - HOOP)) for t in ts]
            row["beaten_geo"] = any(
                handler_hoop[t] < float(np.linalg.norm(xy[r0 + t, N_SIDE + hd] - HOOP)) for t in ts)
            last_xy = [xy[r0 + t, N_SIDE + last] for t in ts]
            for ft, key in ((5.0, "path5"), (PATH_FT, "path6"), (8.0, "path8")):
                row[key] = any(
                    float(np.linalg.norm(last_xy[t] - xy[r0 + t, s])) <= ft
                    and float(np.linalg.norm(last_xy[t] - HOOP)) < handler_hoop[t] for t in ts)
            r1 = r0 + MOVE_FRAMES
            row["last_move"] = _projection(xy[r0, N_SIDE + last], xy[r1, N_SIDE + last], xy[r1, s])
        if near_status == "ok":
            row["near_move"] = max(
                _projection(xy[r0, N_SIDE + near], xy[r0 + t, N_SIDE + near], xy[r0 + t, s])
                for t in range(1, MOVE_FRAMES + 1))
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    ok_last, ok_near = out["last_status"] == "ok", out["near_status"] == "ok"
    stays = ok_last & (out["last_move"] < STAY_FT)
    beaten = out["beaten_geo"]
    out["long"] = ok_last & beaten & out["path6"]
    out["long_path5"] = ok_last & beaten & out["path5"]
    out["long_path8"] = ok_last & beaten & out["path8"]
    out["long_blowby"] = ok_last & out["blowby"] & out["path6"]
    out["long_move4"] = ok_last & beaten & (out["last_move"] >= LAST_MOVE_FT)
    out["long_ref"] = stays & ~beaten
    out["long_ref_blowby"] = stays & ~out["blowby"]
    moves = ok_near & (out["near_move"] >= NEAR_STEP_FT)
    recovered = np.array([_recovered(xy, _row_of(frames.frame_idx, int(r.start_frame)),
                                     int(r.near_slot), int(r.near_man)) if ok else False
                          for r, ok in zip(out.itertuples(), ok_near, strict=True)], bool)
    out["near_stunt"] = moves & recovered
    out["near_committed"] = moves & ~recovered
    out["near_ref"] = ok_near & (out["near_move"] < NEAR_STAY_FT)
    return out


def kind_help_table(frames: GameFrames, table: pd.DataFrame, kinds: pd.DataFrame,
                    kind_col: str, ref_col: str, who: str) -> pd.DataFrame:
    """`help_table` rows of the drives in the kind or its reference, with `who` as the helper.

    The result feeds `rotation.rotation_table` unchanged: `has_helper` is the kind flag, the
    helper is the last or the nearest (`who` in {"last", "near"}) and the man left is his raw
    man, so the three others, the placebo and `nearest_who` all read as in the second help.
    """
    k = kinds.set_index("drive_id")
    use = k[k[kind_col] | k[ref_col]]
    t = table[table["drive_id"].isin(use.index)].copy()
    u = use.loc[t["drive_id"]]
    t["helper_def_slot"] = u[f"{who}_slot"].to_numpy()
    t["left_slot"] = u[f"{who}_man"].to_numpy()
    t["helper_help_move"] = u[f"{who}_move"].to_numpy()
    t["has_helper"] = u[kind_col].to_numpy()
    rows = [_row_of(frames.frame_idx, int(sf)) for sf in t["start_frame"]]
    t["left_id"] = [int(frames.off_ids[r, int(m)])
                    for r, m in zip(rows, t["left_slot"], strict=True)]
    return t
