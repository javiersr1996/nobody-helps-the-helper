"""The approach-angle trade-off: what a rimward heading buys and what it costs (F6).

Usage: uv run python scripts/angle_tradeoff.py [--root DIR] [--cache DIR] [--out DIR]

One quantity, measured half a second before the ball comes off the rim, moves two outcomes
in opposite directions:
  - the BUY: a player heading at the rim wins more offensive rebounds
  - the COST: a player heading at the rim has more turning to do, and F5's `break_area`
    says how much valuable court the other team then owns over the first 4 s of its break

An approach angle is the direction of a velocity vector. It asserts nothing about what a
player meant to do, which is the objection SkillCorner raised against reading crashes off
tracking, and it is the reason this framing survives that objection.

**On the split.** Nothing here is fitted, tuned or graded, so opening the held-out games
costs nothing that D11 protects. They are still reported SEPARATELY from the calibration
games throughout, because a curve that replicates on five unseen games is worth more than
the same curve drawn over ten, and because anything that fails to replicate needs to be
visible rather than averaged away.

Writes {out}/angle_players.csv (one row per player per rebound),
{out}/angle_rebounds.csv (one row per rebound) and {out}/angle_tradeoff.csv (the curve).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.control import ControlParams
from scbasket.court import make_grid
from scbasket.frames import N_SIDE, at_frames, get_or_build
from scbasket.io import Dataset
from scbasket.tagging import (
    APPROACH_LEAD_FRAMES,
    COMMITTED_ANGLE_DEG,
    MIN_APPROACH_SPEED,
    approach_angles,
    transition_outcome,
)
from scbasket.validation import CALIBRATION_GAMES, VALIDATION_GAMES
from scbasket.value import league_zone_values, surface_from_zones

ANGLE_BANDS = [0, 30, 60, 90, 120, 180]
DIST_BANDS = [0, 8, 15, 25, 200]
FROZEN = ControlParams(r_near=2.0, r_far=10.0, t_h=0.3)


def per_player(dataset: Dataset, game_id: int, cache_dir: Path) -> pd.DataFrame:
    """One row per player per rebound, measured APPROACH_LEAD_FRAMES before the ball is won."""
    frames = get_or_build(dataset, game_id, cache_dir)
    events = dataset.events(game_id)
    rebounds = events["rebounds"][events["rebounds"]["frame"].notna()]
    if rebounds.empty:
        return pd.DataFrame()

    target = rebounds["frame"].to_numpy(dtype=np.int64) - APPROACH_LEAD_FRAMES
    at = at_frames(frames, target)
    rebounds = rebounds[np.isin(target, frames.frame_idx)].reset_index(drop=True)
    if len(at) == 0:
        return pd.DataFrame()

    kin = approach_angles(at)
    ids = np.concatenate([at.off_ids, at.def_ids], axis=1)
    winner = rebounds["rebounderId"].to_numpy()[:, None] == ids
    n, slots = winner.shape

    return pd.DataFrame({
        "game": game_id,
        "rebound_id": np.repeat(rebounds["id"].to_numpy(), slots),
        "shot_id": np.repeat(rebounds["shotId"].to_numpy(), slots),
        "defensive": np.repeat(rebounds["defensive"].to_numpy().astype(bool), slots),
        "offense": np.tile(np.arange(slots) < N_SIDE, n),
        "is_winner": winner.ravel(),
        "angle": kin["angle"].ravel(),
        "speed": kin["speed"].ravel(),
        "rim_dist": kin["rim_dist"].ravel(),
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/raw/opendata-basketball"))
    parser.add_argument("--cache", type=Path, default=Path("data/interim"))
    parser.add_argument("--out", type=Path, default=Path("reports"))
    args = parser.parse_args()

    dataset = Dataset(args.root)
    grid = make_grid(1.0)
    surface = surface_from_zones(grid, league_zone_values(dataset.aggregates("shots")))
    games = list(CALIBRATION_GAMES) + list(VALIDATION_GAMES)

    players = pd.concat([per_player(dataset, g, args.cache) for g in games], ignore_index=True)
    players["half"] = np.where(players["game"].isin(CALIBRATION_GAMES), "calibration", "held out")
    moving = players[players["angle"].notna()].copy()

    print(f"rebounds with a frame {APPROACH_LEAD_FRAMES} frames earlier in the cache: "
          f"{players['rebound_id'].nunique()}")
    print(f"player rows {len(players)}, moving at >= {MIN_APPROACH_SPEED} ft/s: "
          f"{len(moving)} ({len(moving) / len(players):.1%}); the rest have no usable heading")

    # ------------------------------------------------------------------ the buy, by angle
    off = moving[moving["offense"]].copy()
    off["angle_band"] = pd.cut(off["angle"], ANGLE_BANDS, right=False)
    off["dist_band"] = pd.cut(off["rim_dist"], DIST_BANDS, right=False)

    print("\n" + "=" * 78)
    print("P(this offensive player wins the rebound) by approach angle, the two halves apart")
    print("=" * 78)
    buy = off.pivot_table(index="angle_band", columns="half", values="is_winner",
                          aggfunc=["count", "mean"], observed=True)
    print(buy.round(4).to_string())

    print("\nThe same, split by distance to the rim, so the angle is not just proximity:")
    grid_table = off.pivot_table(index="angle_band", columns="dist_band", values="is_winner",
                                 aggfunc=["count", "mean"], observed=True)
    print(grid_table.round(3).to_string())

    print("\nDefensive players, for contrast (they start closer and face the other way):")
    dfn = moving[~moving["offense"]].copy()
    dfn["angle_band"] = pd.cut(dfn["angle"], ANGLE_BANDS, right=False)
    print(dfn.pivot_table(index="angle_band", columns="half", values="is_winner",
                          aggfunc=["count", "mean"], observed=True).round(4).to_string())

    # ------------------------------------------------- the cost, via break_area per rebound
    per_rebound = off.groupby(["game", "rebound_id", "half"], observed=True).agg(
        off_angle_mean=("angle", "mean"),
        off_angle_min=("angle", "min"),
        n_committed=("angle", lambda a: int((a < COMMITTED_ANGLE_DEG).sum())),
        n_moving=("angle", "size"),
        rim_dist_mean=("rim_dist", "mean"),
    ).reset_index()
    won = off.groupby("rebound_id", observed=True)["is_winner"].any()
    per_rebound["off_reb_won"] = per_rebound["rebound_id"].map(won)

    breaks = []
    for game_id in games:
        events = dataset.events(game_id)
        frames = get_or_build(dataset, game_id, args.cache)
        table = transition_outcome(frames, events["rebounds"], events["chances"],
                                   grid, FROZEN, surface)
        breaks.append(table.assign(game=game_id))
    breaks = pd.concat(breaks, ignore_index=True)
    per_rebound = per_rebound.merge(
        breaks[["rebound_id", "break_area", "next_pts", "next_transition"]],
        on="rebound_id", how="left",
    )
    per_rebound.to_csv(args.out / "angle_rebounds.csv", index=False)

    print("\n" + "=" * 78)
    print("THE TRADE-OFF: one number, two outcomes, opposite directions")
    print("=" * 78)
    print(f"Bucketed by how many offensive players were heading within "
          f"{COMMITTED_ANGLE_DEG:.0f} deg of the rim.")
    print("`break_area` is only defined on rebounds the other team won, which is the "
          "situation where a break exists to measure.\n")

    curve = per_rebound.groupby(["n_committed", "half"], observed=True).agg(
        rebounds=("rebound_id", "size"),
        off_reb_rate=("off_reb_won", "mean"),
        break_area=("break_area", "mean"),
        break_area_n=("break_area", "count"),
        next_pts=("next_pts", "mean"),
    ).reset_index()
    print(curve.round(3).to_string(index=False))
    curve.to_csv(args.out / "angle_tradeoff.csv", index=False)

    players.to_csv(args.out / "angle_players.csv", index=False)
    print(f"\nWrote {args.out / 'angle_players.csv'}, {args.out / 'angle_rebounds.csv'} "
          f"and {args.out / 'angle_tradeoff.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
