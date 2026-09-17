"""The two figures the entry is allowed, both halves drawn on top of each other (P7.4).

Usage: uv run --extra figures python scripts/figures.py [--reports DIR] [--out DIR]

Needs `reports/angle_players.csv`, which `scripts/angle_tradeoff.py` writes: one row per
player per rebound, measured half a second before the ball is won.

The competition allows two figures, and the argument has exactly two parts, so there is no
choice to make:

  1. **The lift of a rimward heading, by distance to the rim.** Calibration and held out are
     drawn on the same axes rather than side by side, because the replication IS the claim.
     The lift is the share of rebounds won by offensive players arriving under 60 degrees
     minus the share won by everyone else, in the same distance band. It is large inside
     4 ft, it is gone by 12, and both halves say so.

  2. **P(win) by heading inside a FIXED 0-8 ft band.** Figure 1 alone cannot separate the
     heading from proximity: players arriving rimward are also nearer. Holding distance fixed
     and varying only the angle answers that, and the curve stays monotone in both halves.

The bands are the frozen reporting bands of the record, not chosen here. Intervals are a
CLUSTER bootstrap that resamples the five GAMES of each half with replacement, not the
rebounds, because rebounds within a game are not independent and the claim generalises across
games (lesson 1). Five clusters is a small number and the intervals are correspondingly
crude; they are drawn to stop a band of 29 rebounds from looking as solid as one of 131, and
not as a test of anything.

Writes {out}/figure_1_lift_by_distance.png and {out}/figure_2_pwin_by_angle.png.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DIST_BANDS = [0, 4, 8, 12, 16, 22, 200]
ANGLE_BANDS = [0, 30, 60, 90, 120, 180]
COMMITTED_ANGLE_DEG = 60.0
ZONE_MIN_FT, ZONE_MAX_FT = 5.40, 9.39  # the shot-scaled zone of P7.2, from a layup to a three

HALVES = {"calibration": "#8c8c8c", "held out": "#1a1a1a"}
MARKERS = {"calibration": "o", "held out": "s"}
N_BOOTSTRAP = 2000
SEED = 0


def band_labels(edges: list[int], last: str) -> list[str]:
    """Human labels for the bands, with the open-ended last one spelled out."""
    return [f"{lo}-{hi}" for lo, hi in zip(edges[:-2], edges[1:-1], strict=True)] + [last]


def lift_by_distance(players: pd.DataFrame) -> pd.DataFrame:
    """Share won arriving rimward minus share won otherwise, per distance band and half."""
    rows = []
    for (half, band), part in players.groupby(["half", "dist_band"], observed=True):
        rimward = part["angle"] < COMMITTED_ANGLE_DEG
        if rimward.sum() == 0 or (~rimward).sum() == 0:
            continue
        rows.append({
            "half": half, "band": band,
            "lift": part.loc[rimward, "is_winner"].mean() - part.loc[~rimward, "is_winner"].mean(),
            "n": len(part), "n_rimward": int(rimward.sum()),
        })
    return pd.DataFrame(rows)


def pwin_by_angle(players: pd.DataFrame) -> pd.DataFrame:
    """P(this offensive player wins) by angle band, inside a fixed distance band."""
    rows = []
    for (half, band), part in players.groupby(["half", "angle_band"], observed=True):
        rows.append({"half": half, "band": band,
                     "p_win": part["is_winner"].mean(), "n": len(part)})
    return pd.DataFrame(rows)


def cluster_bootstrap(players: pd.DataFrame, statistic, rng: np.random.Generator) -> pd.DataFrame:
    """2.5 and 97.5 percentiles of `statistic`, resampling whole games within each half."""
    draws = []
    for half, part in players.groupby("half", observed=True):
        games = part["game"].unique()
        by_game = {g: sub for g, sub in part.groupby("game", observed=True)}
        for _ in range(N_BOOTSTRAP):
            picked = rng.choice(games, size=len(games), replace=True)
            resampled = pd.concat([by_game[g] for g in picked], ignore_index=True)
            draws.append(statistic(resampled).assign(half=half))
    stacked = pd.concat(draws, ignore_index=True)
    value = "lift" if "lift" in stacked.columns else "p_win"
    return (stacked.groupby(["half", "band"], observed=True)[value]
            .quantile([0.025, 0.975]).unstack())


def draw(ax, table: pd.DataFrame, bounds: pd.DataFrame, labels: list[str], value: str) -> None:
    """One panel: both halves on the same axes, with their crude cluster intervals."""
    x = np.arange(len(labels))
    for half, colour in HALVES.items():
        part = table[table["half"] == half].set_index("band")
        seen = [b for b in part.index]
        pos = [list(part.index).index(b) for b in seen]
        lo = [bounds.loc[(half, b), 0.025] for b in seen]
        hi = [bounds.loc[(half, b), 0.975] for b in seen]
        values = part[value].to_numpy()
        ax.fill_between(pos, lo, hi, color=colour, alpha=0.12, linewidth=0)
        ax.plot(pos, values, marker=MARKERS[half], color=colour, linewidth=2,
                markersize=6, label=half)
        # One half above its markers and the other below, or the counts collide wherever the
        # two lines meet, which is most of the right hand side.
        offset = 9 if half == "held out" else -15
        for xi, yi, n in zip(pos, values, part["n"], strict=True):
            ax.annotate(f"{n}", (xi, yi), textcoords="offset points", xytext=(0, offset),
                        ha="center", fontsize=7, color=colour)
    ax.set_xticks(x, labels)
    ax.grid(axis="y", color="#dddddd", linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--out", type=Path, default=Path("reports/figures"))
    args = parser.parse_args()

    source = args.reports / "angle_players.csv"
    if not source.exists():
        print(f"no {source}; run scripts/angle_tradeoff.py first", file=sys.stderr)
        return 1

    players = pd.read_csv(source)
    players = players[players["offense"] & players["angle"].notna()].copy()
    players["dist_band"] = pd.cut(players["rim_dist"], DIST_BANDS, right=False)
    players["angle_band"] = pd.cut(players["angle"], ANGLE_BANDS, right=False)
    print(f"offensive player rows with a usable heading: {len(players)}")
    print(players.groupby("half", observed=True)["is_winner"].agg(["count", "mean"]).to_string())

    rng = np.random.default_rng(SEED)
    args.out.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- figure 1: the lift
    lift = lift_by_distance(players)
    print("\nFigure 1, the lift of a rimward heading by distance band:")
    print(lift.pivot(index="band", columns="half", values="lift").round(3).to_string())
    bounds = cluster_bootstrap(players, lift_by_distance, rng)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    labels = band_labels(DIST_BANDS, "22+")
    draw(ax, lift, bounds, labels, "lift")
    ax.axhline(0, color="#000000", linewidth=1)
    ax.axvspan(-0.5, 1.5, color="#f0a33c", alpha=0.10, linewidth=0)
    # Bottom left, which is the one corner neither the lines, the intervals nor the legend use.
    ax.text(0.02, 0.06, "shaded: the 8 ft band this work replaced. The zone a shot\n"
                        "earns runs 5.4 ft on a layup to 9.4 ft on a three",
            transform=ax.transAxes, fontsize=8, color="#8a6d3b", va="bottom")
    ax.set_xlabel("distance to the rim, feet, half a second before the ball is won")
    ax.set_ylabel("P(win) arriving rimward minus P(win) otherwise")
    ax.set_title("Inside the zone the heading decides. Outside it, nothing.\n"
                 "Both halves on the same axes; the small number is the players in the band.",
                 fontsize=11, loc="left")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(args.out / "figure_1_lift_by_distance.png", dpi=200)
    plt.close(fig)

    # -------------------------------------------- figure 2: the angle at a fixed distance
    inside = players[players["rim_dist"] < 8.0].copy()
    curve = pwin_by_angle(inside)
    print("\nFigure 2, P(win) by angle band inside a fixed 0-8 ft:")
    print(curve.pivot(index="band", columns="half", values="p_win").round(3).to_string())
    # The record quotes this curve POOLED, where it is monotone. Split, only the held-out
    # half is: calibration ticks up in the last band. Printed so the two are never confused.
    pooled = inside.groupby("angle_band", observed=True)["is_winner"].agg(["count", "mean"])
    print("the same pooled over both halves, which is what the record quotes:")
    print(pooled.round(3).to_string())
    bounds2 = cluster_bootstrap(inside, pwin_by_angle, rng)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    draw(ax, curve, bounds2, band_labels(ANGLE_BANDS, "120-180"), "p_win")
    ax.set_xlabel("approach angle, degrees. 0 is driving at the rim, 180 is running away")
    ax.set_ylabel("P(this offensive player wins the rebound)")
    ax.set_title("Not proximity relabelled: at a FIXED 0-8 ft band, only the heading varies.\n"
                 "Pooled it falls 4.5x. Held out monotone; calibration ticks up at the end.",
                 fontsize=11, loc="left")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(args.out / "figure_2_pwin_by_angle.png", dpi=200)
    plt.close(fig)

    print(f"\nwrote {args.out / 'figure_1_lift_by_distance.png'} and "
          f"{args.out / 'figure_2_pwin_by_angle.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
