"""Four committed near helps, as tracking, for the page to replay on a court (B2, 11a).

Usage: uv run python scripts/wind_scenes.py [--root DIR] [--cache DIR] [--pairs FILE]
                                            [--out FILE] [--games N]

Sibling of `scripts/court_scenes.py`, for the wind. Every other artefact of the entry reduces
a drive to numbers; the page needs one drive itself: the ten players and the ball for two
seconds, in the DRIVE FRAME (the attacking frame mirrored in y by `help_table`'s `flip`, so the
handler's lateral motion goes to +y; x is never mirrored), with the helper, the man he left and
the three other defenders named by slot. Since 2026-10-30 (the thesis scoped to the near help
that commits, `scbasket.help_kinds`) the roles are those of that analysis: the helper is the
off-ball defender NEAREST the ball, the man left his raw provider matchup at the start, the
three others the remaining off-ball defenders (`help_kinds.kind_help_table`). Nothing is
modelled here. The per-frame projections use exactly the conventions of `scbasket.rotation`
(`_projection`, the three others, the placebo targets), so at frames 25, 38 and 50 they equal
`reports/near_committed_pairs.csv` (`scripts/help_kinds.py`).

The choice is a rule, not a search: games in `dataset.game_ids` order, and in each the first
helped drive (in the game's `drives` order) whose man left has a provider matchup and whose
2 s window (frames 0 to 50 from `startFrame`) is contiguous inside one chance with the ten
players DETECTED on every frame. "Helped" is `help_kinds`' `near_committed` (the nearest
moves >= 2 ft toward the handler within 1.0 s and is not back with his man at 2.0 s); until
2026-10-30 it was `help_table`'s `has_helper`, the pooled largest mover. The other conditions
are unchanged. The first `--games` games that have one are taken. Nothing looks at how good a
drive is to watch, and the per-game counts of each condition (over the game's committed near
helps) are printed so a rule that finds fewer than asked is visible, not relaxed.

One drive is never presented as typical: each scene carries its 1.5 s paired mean (the three
others' `to_left` minus `placebo`, frame 38) and where that value sits among the same value
of every committed near help in `near_committed_pairs.csv` (the key keeps its old name,
`paired_mean_1_5s_among_helped`).

What it deliberately does NOT write: any player id, name or number. Slots 0-4 are the
attacking team and 5-9 the defending one, and a slot is not a person. The ruling the entry is
built under holds: "helper", "man left" and "covers" name measured vectors and distances,
never decisions.

Every scene is checked against its table row before it is written (`check_scene`): the
helper's movement within 1.0 s (`help_kinds`' `near_move`) and the man left's clearance at 0
and 1.0 s are recomputed from the scene's own arrays and must equal the row within
TOLERANCE_FT, and the helper must not be back with his man at 2.0 s, or the script raises
ValueError.

Writes {out} (default `reports/wind_scenes.json`), which the page inlines.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.court import HOOP_X
from scbasket.frames import N_SIDE, GameFrames, get_or_build
from scbasket.help_kinds import (
    MOVE_FRAMES,
    OUTCOME_FRAMES,
    RECOVER_FT,
    drive_kinds,
    kind_help_table,
)
from scbasket.io import Dataset
from scbasket.rotation import HEADLINE_HORIZON, _projection, _window_end
from scbasket.wind import FPS, HELP_FT, HORIZON_FRAMES, _row_of, help_table

#: Frames of a scene: 0 to 2.0 s after `startFrame`, 51 frames at 25 fps.
SCENE_LAST = 50
SCENE_FRAMES = SCENE_LAST + 1
#: Clearance is quoted at these frames: 0, 1.0 and 1.5 s.
CLEARANCE_QUOTED = (0, HORIZON_FRAMES, HEADLINE_HORIZON)
#: How far a scene may be from `help_table` before it is refused, in feet. Coordinates ship
#: rounded to ROUND_DECIMALS, which moves a projection by far less than this.
TOLERANCE_FT = 0.01
ROUND_DECIMALS = 3
#: The conditions of the rule, in the order they are counted.
CONDITIONS = ("helped", "left", "window", "detected")


def _round(values: np.ndarray) -> list:
    """Nested lists rounded for the file, with NaN written as null (JSON has no NaN)."""
    a = np.asarray(values, dtype=float)
    out = np.round(a, ROUND_DECIMALS).astype(object)
    out[np.isnan(a)] = None
    return out.tolist()


def drive_conditions(frames: GameFrames, row: pd.Series, r0: int) -> dict[str, bool]:
    """Which conditions of the rule one drive of `help_table` meets, each on its own.

    `helped`: a resolved drive whose `has_helper` is set (in `near_committed_table`, a
    committed near help). `left`: the man he left has a provider matchup. `window`: frames 0
    to SCENE_LAST from `startFrame` are contiguous and in one chance. `detected`: all ten
    players are detected on every one of them.
    """
    ok = row["status"] == "ok" and r0 >= 0
    window = bool(ok and _window_end(frames, r0, SCENE_LAST) - r0 >= SCENE_LAST)
    return {
        "helped": bool(ok and row["has_helper"]),
        "left": bool(ok and row["left_slot"] >= 0),
        "window": window,
        "detected": bool(window and frames.detected[r0:r0 + SCENE_FRAMES].all()),
    }


def first_qualifying(frames: GameFrames, table: pd.DataFrame) -> tuple[pd.Series | None, dict]:
    """The first drive of the table (its order) that meets every condition, and the counts.

    The counts are drives meeting each condition on its own, and `all` the ones meeting all of
    them, so a game with no scene says which condition took it away.
    """
    counts = dict.fromkeys((*CONDITIONS, "all"), 0)
    chosen = None
    for _, row in table.iterrows():
        r0 = _row_of(frames.frame_idx, int(row["start_frame"])) if row["status"] == "ok" else -1
        met = drive_conditions(frames, row, r0)
        for name in CONDITIONS:
            counts[name] += met[name]
        if all(met.values()):
            counts["all"] += 1
            if chosen is None:
                chosen = row
    return chosen, counts


def near_committed_table(frames: GameFrames, drives: pd.DataFrame,
                         table: pd.DataFrame) -> pd.DataFrame:
    """`help_table` rows of one game's committed near helps, in that analysis' roles.

    `help_kinds.kind_help_table` makes the nearest the helper, his raw man the man left and his
    `near_move` the `helper_help_move`. It leaves `left_nearest0` / `left_nearest1` as the
    pooled helper's man's; `check_scene` reads them, so they are recomputed here for this man,
    as `wind` computes them (his nearest defender at 0 and 1.0 s).
    """
    kinds = drive_kinds(frames, drives, table)
    near = kind_help_table(frames, table, kinds, "near_committed", "near_committed", "near")
    xy = frames.xy.astype(np.float64)
    rows = [_row_of(frames.frame_idx, int(sf)) for sf in near["start_frame"]]
    for column, dt in (("left_nearest0", 0), ("left_nearest1", HORIZON_FRAMES)):
        near[column] = [float(np.linalg.norm(xy[r + dt, N_SIDE:] - xy[r + dt, int(m)],
                                             axis=1).min())
                        for r, m in zip(rows, near["left_slot"], strict=True)]
    return near


def helper_move(xy: np.ndarray, helper: int, handler: int) -> float:
    """`help_kinds`' near-help movement from a scene's own arrays: the helper's displacement
    from frame 0 projected on the unit vector to where the handler is at the same frame, at
    its best frame of 1 to MOVE_FRAMES (`near_move`). Feet."""
    return max(_projection(xy[0, helper], xy[t, helper], xy[t, handler])
               for t in range(1, MOVE_FRAMES + 1))


def clearance(xy: np.ndarray, left: int) -> np.ndarray:
    """The man left's distance to his nearest defender, per frame."""
    return np.linalg.norm(xy[:, N_SIDE:] - xy[:, None, left], axis=2).min(axis=1)


def build_scene(frames: GameFrames, row: pd.Series) -> dict:
    """One drive as a replayable clip in the drive frame, from the cache rows of its window."""
    r0 = _row_of(frames.frame_idx, int(row["start_frame"]))
    rows = slice(r0, r0 + SCENE_FRAMES)
    mirror = np.array([1.0, float(row["flip"])])
    xy = frames.xy[rows].astype(np.float64) * mirror
    ball = frames.ball[rows].astype(np.float64) * np.array([*mirror, 1.0])

    handler, left = int(row["handler_slot"]), int(row["left_slot"])
    handler_def, helper = int(row["handler_def_slot"]), int(row["helper_def_slot"])
    others = [x for x in range(N_SIDE) if x not in (handler_def, helper)]  # as `rotation`
    raw_matchup = frames.matchup[r0]

    to_left = np.zeros((len(others), SCENE_FRAMES))
    placebo = np.full((len(others), SCENE_FRAMES), np.nan)
    placebo_targets = []
    for i, x in enumerate(others):
        own = set(np.flatnonzero(raw_matchup == x).tolist())
        targets = [a for a in range(N_SIDE) if a not in (handler, left) and a not in own]
        placebo_targets.append(targets)
        p0 = xy[0, N_SIDE + x]
        for t in range(SCENE_FRAMES):
            p1 = xy[t, N_SIDE + x]
            to_left[i, t] = _projection(p0, p1, xy[t, left])
            if targets:
                placebo[i, t] = np.mean([_projection(p0, p1, xy[t, a]) for a in targets])

    clear = clearance(xy, left)
    paired = float(np.mean(to_left[:, HEADLINE_HORIZON] - placebo[:, HEADLINE_HORIZON]))
    return {
        "game": int(row["game"]),
        "drive_id": row["drive_id"],
        "end_type": row["end_type"],
        "flip": float(row["flip"]),
        "roles": {
            "handler": handler,
            "handler_def": N_SIDE + handler_def,
            "helper": N_SIDE + int(row["helper_def_slot"]),
            "left": left,
            "others": [N_SIDE + x for x in others],
            "off_ball": [a for a in range(N_SIDE) if a != handler],
            "placebo_targets": placebo_targets,
        },
        "helper_help_move": float(row["helper_help_move"]),
        "clearance_ft": {f"{t / FPS:.1f}s": float(clear[t]) for t in CLEARANCE_QUOTED},
        "paired_mean_1_5s": paired,
        "xy": _round(xy),
        "ball": _round(ball),
        "left_clearance": _round(clear),
        "to_left": _round(to_left),
        "placebo": _round(placebo),
    }


def check_scene(scene: dict, row: pd.Series) -> None:
    """Refuse a scene that disagrees with its table row; ValueError names what differs.

    The helper's movement within 1.0 s and the man left's clearance at 0 and 1.0 s are
    recomputed from the scene's own `xy` (what the page would draw) and compared with the
    row's `helper_help_move`, `left_nearest0` and `left_nearest1` (`near_committed_table`);
    the stored scalars and the handler's position at 1.0 s are held to the same row. The
    helper must also be committed in the scene: back within his 0 s distance to his man plus
    RECOVER_FT at 2.0 s is a stunt (`help_kinds`' rule), and is refused.
    """
    xy = np.asarray(scene["xy"], dtype=float)
    roles = scene["roles"]
    clear = clearance(xy, roles["left"])
    handler_1s = np.array([row["handler_x1"], row["handler_y1"]])
    claims = {
        "helper_help_move (recomputed)": (helper_move(xy, roles["helper"], roles["handler"]),
                                          row["helper_help_move"]),
        "helper_help_move (stored)": (scene["helper_help_move"], row["helper_help_move"]),
        "clearance at 0 s": (clear[0], row["left_nearest0"]),
        "clearance at 1.0 s": (clear[HORIZON_FRAMES], row["left_nearest1"]),
        "handler x at 1.0 s": (xy[HORIZON_FRAMES, roles["handler"], 0], handler_1s[0]),
        "handler y at 1.0 s": (xy[HORIZON_FRAMES, roles["handler"], 1], handler_1s[1]),
    }
    bad = [f"{name}: scene {got:.3f} vs table {want:.3f}"
           for name, (got, want) in claims.items() if abs(got - want) > TOLERANCE_FT]
    start, end = (float(np.linalg.norm(xy[t, roles["helper"]] - xy[t, roles["left"]]))
                  for t in (0, OUTCOME_FRAMES))
    if end <= start + RECOVER_FT:
        bad.append(f"helper back with his man at 2.0 s: {end:.3f} ft, {start:.3f} at 0 s")
    if bad:
        raise ValueError(f"scene {scene['drive_id']} disagrees with help_table: " + "; ".join(bad))


def paired_means(pairs: pd.DataFrame, horizon: int = HEADLINE_HORIZON) -> pd.Series:
    """Per helped drive, the mean over the three others of `to_left - placebo` at `horizon`
    (the unit of the headline), from a pairs file (`near_committed_pairs.csv`, or
    `second_help_pairs.csv`, which has the same columns)."""
    p = pairs[pairs["helped"] & (pairs["horizon"] == horizon)].dropna(subset=["placebo"])
    return (p["to_left"] - p["placebo"]).groupby(p["drive_id"]).mean()


def place_in(value: float, distribution: pd.Series) -> dict:
    """Where one drive's paired mean sits among the helped drives of `distribution`: the share
    at or below it."""
    return {"n_helped": int(len(distribution)),
            "median": float(distribution.median()),
            "percentile": float(100 * (distribution <= value).mean())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--root", type=Path, default=Path("data/raw/opendata-basketball"))
    parser.add_argument("--cache", type=Path, default=Path("data/interim"))
    parser.add_argument("--pairs", type=Path, default=Path("reports/near_committed_pairs.csv"))
    parser.add_argument("--out", type=Path, default=Path("reports/wind_scenes.json"))
    parser.add_argument("--games", type=int, default=4, help="games, one drive each")
    args = parser.parse_args()

    dataset = Dataset(args.root)
    distribution = paired_means(pd.read_csv(args.pairs))
    scenes, selection = [], []
    for game in dataset.game_ids:
        if len(scenes) == args.games:
            break
        frames = get_or_build(dataset, game, args.cache)
        drives = dataset.events(game)["drives"]
        table = help_table(frames, drives)  # in process, not the CSV
        row, counts = first_qualifying(frames, near_committed_table(frames, drives, table))
        selection.append({"game": int(game), "drives": int(len(table)), **counts,
                          "chosen": None if row is None else row["drive_id"]})
        print(f"  {game}: " + ", ".join(f"{k} {v}" for k, v in counts.items())
              + f" -> {'no scene' if row is None else row['drive_id']}")
        if row is None:
            continue
        scene = build_scene(frames, row)
        check_scene(scene, row)
        scene["paired_mean_1_5s_among_helped"] = place_in(scene["paired_mean_1_5s"], distribution)
        scenes.append(scene)

    if not scenes:
        print("no game has a qualifying drive; see the counts above", file=sys.stderr)
        return 1
    if len(scenes) < args.games:
        print(f"only {len(scenes)} of {args.games} games have a qualifying drive; shipping those",
              file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "hoop_x": HOOP_X,
        "fps": FPS,
        "n_frames": SCENE_FRAMES,
        "help_ft": HELP_FT,
        "horizon_frames": HORIZON_FRAMES,
        "headline_frame": HEADLINE_HORIZON,
        "selection": selection,
        "scenes": scenes,
    }), encoding="utf-8")
    print(f"wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB, {len(scenes)} scenes, "
          f"{sum(len(s['xy']) for s in scenes)} frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
