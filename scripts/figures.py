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

The tables and their crude cluster intervals come from `scbasket.report`, which is also what
`scripts/report_html.py` reads, so the page and the figures cannot drift apart.

Writes {out}/figure_1_lift_by_distance.png and {out}/figure_2_pwin_by_angle.png.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from scbasket import report

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLOURS = {"calibration": "#8c8c8c", "held out": "#1a1a1a"}
MARKERS = {"calibration": "o", "held out": "s"}


def show(title: str, table: pd.DataFrame, labels: tuple[str, ...]) -> None:
    """The table as it is drawn, printed so a reader never has to trust the picture."""
    wide = table.pivot(index="slot", columns="half", values="value").round(3)
    wide.index = [labels[slot] for slot in wide.index]
    print(f"\n{title}:")
    print(wide.to_string())


def draw(ax, table: pd.DataFrame, labels: tuple[str, ...]) -> None:
    """One panel: both halves on the same axes, with their crude cluster intervals."""
    for half in report.HALVES:
        part = table[table["half"] == half]
        colour, pos, values = COLOURS[half], part["slot"], part["value"]
        ax.fill_between(pos, part["lo"], part["hi"], color=colour, alpha=0.12, linewidth=0)
        ax.plot(pos, values, marker=MARKERS[half], color=colour, linewidth=2,
                markersize=6, label=half)
        # One half above its markers and the other below, or the counts collide wherever the
        # two lines meet, which is most of the right hand side.
        offset = 9 if half == "held out" else -15
        for xi, yi, n in zip(pos, values, part["n"], strict=True):
            ax.annotate(f"{n}", (xi, yi), textcoords="offset points", xytext=(0, offset),
                        ha="center", fontsize=7, color=colour)
    ax.set_xticks(np.arange(len(labels)), labels)
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

    players = report.load_players(source)
    print(f"offensive player rows with a usable heading: {len(players)}")
    print(players.groupby("half", observed=True)["is_winner"].agg(["count", "mean"]).to_string())

    rng = np.random.default_rng(report.SEED)
    args.out.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- figure 1: the lift
    lift = report.banded(players, "dist_slot", report.DIST_LABELS, report.lift, rng)
    show("Figure 1, the lift of a rimward heading by distance band", lift, report.DIST_LABELS)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    draw(ax, lift, report.DIST_LABELS)
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
    inside = players[players["rim_dist"] < report.FIXED_BAND_FT]
    curve = report.banded(inside, "angle_slot", report.ANGLE_LABELS, report.p_win, rng)
    show("Figure 2, P(win) by angle band inside a fixed 0-8 ft", curve, report.ANGLE_LABELS)
    # The record quotes this curve POOLED, where it is monotone. Split, only the held-out
    # half is: calibration ticks up in the last band. Printed so the two are never confused.
    print("the same pooled over both halves, which is what the record quotes:")
    print(report.pooled(inside, "angle_slot", report.ANGLE_LABELS)
          .set_index("band").round(3).to_string())

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    draw(ax, curve, report.ANGLE_LABELS)
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
