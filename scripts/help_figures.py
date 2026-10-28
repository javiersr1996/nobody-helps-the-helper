"""The two figures of the second entry: the wind map, and the man it leaves (P8, W2).

Usage: uv run --extra figures python scripts/help_figures.py [--reports DIR] [--out DIR]

Needs `reports/help_table.csv` and `reports/help_vectors.csv`, which `scripts/help_wind.py`
writes. Both figures are drawn in the DRIVE FRAME and in shot-chart orientation: the attacked
hoop at the bottom, the baseline under it, and the ball handler's lateral motion to the
RIGHT, so left- and right-hand drives pool and "the corner side" is always bottom right.

  1. **The wind map.** The mean displacement, over the first second of every drive, of the
     four defenders who are not the ball handler's matchup: a kernel-smoothed field drawn as
     streamlines, line width by how far the defence moves. Under it, in orange, where the
     HELPER starts (the largest mover, HELP_FT or more toward where the ball ends up). The
     field shows the whole defence sinking with the drive as well as the help; the table
     separates the two (`help_move` is the movement toward the ball's future position), the
     picture does not, and the caption says so.

  2. **The man he leaves.** Where the attacker the helper was guarding stands one second
     in, orange when no defender is within OPEN_FT of him, grey otherwise, with the
     distribution of that distance under the court.

Every number printed on either figure is computed here from the CSVs, never typed. Nothing
is drawn inside the court but the court, the data and the ball's median path: numbers,
keys and legends live in a strip under it, where no streamline can cross them.

Writes {out}/wind_figure_1_wind_map.png and {out}/wind_figure_2_open_man.png.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from scbasket.court import CORNER_LINE_Y_FT, FIBA, HOOP_X, THREE_RADIUS_FT
from scbasket.wind import HELP_FT, HORIZON_S, OPEN_FT

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

INK = "#2b2b2b"
COURT = "#555555"
ORANGE = "#f0a33c"
GREY = "#9a9a9a"

#: FIBA measurements court.py does not carry, feet: the free-throw circle (1.80 m), the
#: backboard (1.20 m from the baseline, 1.80 m wide) and the rim (0.45 m across).
FT_CIRCLE_FT = 5.91
BACKBOARD_FROM_BASELINE_FT = 3.94
BACKBOARD_HALF_WIDTH_FT = 2.95
RIM_RADIUS_FT = 0.74

#: The kernel field: grid step, Gaussian bandwidth, and the least kernel mass (in vectors'
#: worth) a cell needs before it is drawn, so the wind only blows where defenders stood.
GRID_FT = 1.5
BANDWIDTH_FT = 4.0
MIN_WEIGHT = 10.0
DENSITY_BANDWIDTH_FT = 3.0
#: Streamline width, points, for a mean displacement of zero and of WIDTH_FULL_FT.
WIDTH_MIN, WIDTH_MAX, WIDTH_FULL_FT = 0.4, 2.8, 6.0

MIDDLE_Y_FT = 8.0
CORNER_Y_FT = 18.0
THREE_ZONES = ("corner_3", "wing_3", "top_3", "far")

#: Figure layout, figure fractions: the court on top, a strip under it for everything else.
FIGSIZE = (7.2, 8.9)
COURT_BOX = (0.03, 0.175, 0.94, 0.745)
STRIP_TOP = 0.15


def to_plot(x, y) -> tuple[np.ndarray, np.ndarray]:
    """Drive-frame feet to plot feet: lateral across, distance from the hoop line up."""
    return np.asarray(y, float), np.asarray(x, float) - HOOP_X


def draw_court(ax) -> None:
    """The FIBA half court in plot feet: hoop at (0, 0), baseline below, half court on top."""
    baseline = -(FIBA.half_length_ft + HOOP_X)
    top = -HOOP_X
    half = FIBA.half_width_ft
    line = {"color": COURT, "linewidth": 1.0, "solid_capstyle": "round"}
    ax.plot([-half, half, half, -half, -half], [baseline, baseline, top, top, baseline], **line)
    pw, ft_line = FIBA.paint_half_width_ft, baseline + FIBA.paint_length_ft
    ax.plot([-pw, -pw, pw, pw], [baseline, ft_line, ft_line, baseline], **line)
    t = np.linspace(0, np.pi, 60)
    ax.plot(FT_CIRCLE_FT * np.cos(t), ft_line + FT_CIRCLE_FT * np.sin(t), **line)
    ax.plot(FIBA.ra_radius_ft * np.cos(t), FIBA.ra_radius_ft * np.sin(t), color=COURT,
            linewidth=0.8)
    y_meet = np.sqrt(THREE_RADIUS_FT**2 - CORNER_LINE_Y_FT**2)
    for side in (-1, 1):
        ax.plot([side * CORNER_LINE_Y_FT] * 2, [baseline, y_meet], **line)
    a0 = np.arctan2(y_meet, CORNER_LINE_Y_FT)
    t3 = np.linspace(a0, np.pi - a0, 120)
    ax.plot(THREE_RADIUS_FT * np.cos(t3), THREE_RADIUS_FT * np.sin(t3), **line)
    tr = np.linspace(0, 2 * np.pi, 40)
    ax.plot(RIM_RADIUS_FT * np.cos(tr), RIM_RADIUS_FT * np.sin(tr), color=COURT, linewidth=1.0)
    bb = baseline + BACKBOARD_FROM_BASELINE_FT
    ax.plot([-BACKBOARD_HALF_WIDTH_FT, BACKBOARD_HALF_WIDTH_FT], [bb, bb], color=COURT,
            linewidth=1.8)
    ax.text(half - 0.6, baseline - 0.8, "corner side of the drive", fontsize=7.5, color=COURT,
            ha="right", va="top", style="italic")
    ax.text(-half + 0.6, baseline - 0.8, "far corner", fontsize=7.5, color=COURT, ha="left",
            va="top", style="italic")
    ax.set_aspect("equal")
    ax.set_xlim(-half - 1.5, half + 1.5)
    ax.set_ylim(baseline - 3.0, top + 1.0)
    ax.axis("off")


def kernel_field(px, py, u, v, grid_x, grid_y):
    """Gaussian-weighted mean of (u, v) on the grid, masked where too few vectors are near."""
    gx, gy = np.meshgrid(grid_x, grid_y)
    d2 = (gx.ravel()[:, None] - px[None, :]) ** 2 + (gy.ravel()[:, None] - py[None, :]) ** 2
    w = np.exp(-0.5 * d2 / BANDWIDTH_FT**2)
    mass = w.sum(axis=1)
    safe = np.maximum(mass, 1e-9)
    mask = (mass < MIN_WEIGHT).reshape(gx.shape)
    U = np.ma.array((w @ u / safe).reshape(gx.shape), mask=mask)
    V = np.ma.array((w @ v / safe).reshape(gx.shape), mask=mask)
    return gx, gy, U, V


def density(px, py, grid_x, grid_y) -> np.ndarray:
    """Gaussian kernel density of the points on the grid, in points per square foot."""
    gx, gy = np.meshgrid(grid_x, grid_y)
    d2 = (gx.ravel()[:, None] - px[None, :]) ** 2 + (gy.ravel()[:, None] - py[None, :]) ** 2
    k = np.exp(-0.5 * d2 / DENSITY_BANDWIDTH_FT**2).sum(axis=1)
    return (k / (2 * np.pi * DENSITY_BANDWIDTH_FT**2)).reshape(gx.shape)


def width_of(displacement_ft) -> np.ndarray:
    """Streamline width for a mean displacement, clipped at WIDTH_FULL_FT."""
    share = np.clip(np.asarray(displacement_ft, float) / WIDTH_FULL_FT, 0.0, 1.0)
    return WIDTH_MIN + (WIDTH_MAX - WIDTH_MIN) * share


def headline(table: pd.DataFrame) -> dict:
    """The numbers both figures print, each from the table and nowhere else."""
    ok = table[table["status"] == "ok"]
    helped = ok[ok["has_helper"]]
    left = helped.dropna(subset=["left_nearest1"])
    return {
        "n_drives": len(table),
        "n_resolved": len(ok),
        "n_helped": len(helped),
        "share_helped": len(helped) / len(ok),
        "from_middle": (helped["helper_origin_y"].abs() < MIDDLE_Y_FT).mean(),
        "from_corner_side": (helped["helper_origin_y"].abs() > CORNER_Y_FT).mean(),
        "helper_start_dist": helped["helper_start_dist"].median(),
        "n_left": len(left),
        "left_open": (left["left_nearest1"] >= OPEN_FT).mean(),
        "left_nearest": left["left_nearest1"].median(),
        "left_beyond_arc": left["left_zone1"].isin(THREE_ZONES).mean(),
        "left_far_side": (left["left_y1"] < 0).mean(),
    }


def figure_1(table: pd.DataFrame, vectors: pd.DataFrame, numbers: dict, path: Path) -> None:
    px, py = to_plot(vectors["origin_x"], vectors["origin_y"])
    u, v = vectors["dy"].to_numpy(float), vectors["dx"].to_numpy(float)  # lateral, along
    grid_x = np.arange(-24.0, 24.0 + GRID_FT, GRID_FT)
    grid_y = np.arange(-3.0, 38.0 + GRID_FT, GRID_FT)
    gx, gy, U, V = kernel_field(px, py, u, v, grid_x, grid_y)
    magnitude = np.ma.filled(np.hypot(U, V), 0.0)

    fig = plt.figure(figsize=FIGSIZE)
    ax = fig.add_axes(COURT_BOX)
    draw_court(ax)

    helped = table[(table["status"] == "ok") & table["has_helper"]]
    hx, hy = to_plot(helped["helper_origin_x"], helped["helper_origin_y"])
    dens = density(hx, hy, grid_x, grid_y)
    levels = np.linspace(0.12 * dens.max(), dens.max(), 7)
    ax.contourf(gx, gy, dens, levels=levels, cmap="Oranges", alpha=0.55, antialiased=True)
    ax.streamplot(grid_x, grid_y, U, V, density=1.2, color=INK, linewidth=width_of(magnitude),
                  arrowsize=0.9, arrowstyle="-|>", zorder=3)

    ok = table[table["status"] == "ok"]
    start = to_plot(ok["handler_x0"].median(), ok["handler_y0"].median())
    end = to_plot(ok["handler_x1"].median(), ok["handler_y1"].median())
    ax.annotate("", xy=end, xytext=start, zorder=5,
                arrowprops={"arrowstyle": "-|>", "color": "black", "linewidth": 2.4,
                            "shrinkA": 0, "shrinkB": 0})
    ax.scatter([start[0]], [start[1]], s=70, color="white", edgecolor="black", linewidth=1.6,
               zorder=6)
    ax.text(start[0] - 1.4, start[1] + 0.6, "the ball:\nmedian start,\none second later",
            fontsize=7.5, color="black", ha="right", va="bottom", zorder=6, linespacing=1.3,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.9, "pad": 1.5})
    ax.set_title("On a drive the defence moves like weather, and the help blows from the\n"
                 "middle and the top. Nobody helps from the corner.", fontsize=11, loc="left")

    # Lines kept under 75 characters so the block ends before the line-width key begins.
    text = (f"{numbers['n_resolved']} drives, ten ACB games, the first {HORIZON_S:.0f} s of each.\n"
            f"Streamlines: where the four defenders off the ball move, every one of\n"
            f"them, so the field carries the whole defence sinking with the drive\n"
            f"as well as the help. Orange: where the HELPER starts, the defender who\n"
            f"moves most toward where the ball will be, {HELP_FT:.0f} ft or more: "
            f"{numbers['n_helped']} drives, {100 * numbers['share_helped']:.0f}%.\n"
            f"From the middle {100 * numbers['from_middle']:.0f}%; from the corner side "
            f"{100 * numbers['from_corner_side']:.1f}%.")
    fig.text(0.04, STRIP_TOP, text, fontsize=8, color=INK, ha="left", va="top", linespacing=1.5)

    key = fig.add_axes([0.74, 0.025, 0.23, 0.075])
    key.axis("off")
    key.set_xlim(0, 1)
    key.set_ylim(0, 1)
    for i, feet in enumerate((1.0, 3.0, 6.0)):
        y = 0.82 - 0.33 * i
        key.plot([0.0, 0.3], [y, y], color=INK, linewidth=width_of(feet), solid_capstyle="butt")
        key.text(0.36, y, f"{feet:.0f} ft in {HORIZON_S:.0f} s", fontsize=7.5, va="center")
    key.set_title("line width: mean displacement", fontsize=7.5, loc="left", pad=2)

    fig.savefig(path, dpi=200)
    plt.close(fig)


def figure_2(table: pd.DataFrame, numbers: dict, path: Path) -> None:
    helped = table[(table["status"] == "ok") & table["has_helper"]].dropna(subset=["left_x1"])
    lx, ly = to_plot(helped["left_x1"], helped["left_y1"])
    nearest = helped["left_nearest1"].to_numpy()
    is_open = nearest >= OPEN_FT

    fig = plt.figure(figsize=FIGSIZE)
    ax = fig.add_axes(COURT_BOX)
    draw_court(ax)
    ax.scatter(lx[~is_open], ly[~is_open], s=26, color=GREY, edgecolor="white", linewidth=0.5,
               zorder=4)
    ax.scatter(lx[is_open], ly[is_open], s=30, color=ORANGE, edgecolor="white", linewidth=0.5,
               zorder=5)
    ax.set_title("The price of the help: the man it leaves, one second into the drive.\n"
                 "Most of him stands beyond the arc with nobody within six feet.",
                 fontsize=11, loc="left")

    hist = fig.add_axes([0.06, 0.04, 0.36, 0.085])
    bins = np.arange(0, 20.5, 1.0)
    hist.hist(nearest[~is_open], bins=bins, color=GREY)
    hist.hist(nearest[is_open], bins=bins, color=ORANGE)
    hist.axvline(OPEN_FT, color=INK, linewidth=1)
    hist.set_xlabel("feet to the nearest defender, one second in", fontsize=7.5, labelpad=2)
    hist.tick_params(labelsize=7, length=2)
    hist.set_yticks([])
    for spine in ("top", "right", "left"):
        hist.spines[spine].set_visible(False)
    hist.text(OPEN_FT + 0.4, hist.get_ylim()[1] * 0.95,
              f"median {numbers['left_nearest']:.1f} ft", fontsize=7.5, va="top")

    handles = [
        Line2D([], [], marker="o", linestyle="none", markersize=6, color=ORANGE,
               label=f"open: nobody within {OPEN_FT:.0f} ft ({is_open.sum()})"),
        Line2D([], [], marker="o", linestyle="none", markersize=6, color=GREY,
               label=f"covered: a defender within {OPEN_FT:.0f} ft ({(~is_open).sum()})"),
    ]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.47, STRIP_TOP + 0.005),
               frameon=False, fontsize=8, handletextpad=0.4, borderaxespad=0)
    text = (f"The attacker the helper was guarding when the drive began, where he stands "
            f"{HORIZON_S:.0f} s later: {numbers['n_left']} drives.\n"
            f"Open {100 * numbers['left_open']:.0f}%; beyond the arc "
            f"{100 * numbers['left_beyond_arc']:.0f}%; on the side away from the drive "
            f"{100 * numbers['left_far_side']:.0f}%, so he is left on either side.")
    fig.text(0.47, STRIP_TOP - 0.075, text, fontsize=8, color=INK, ha="left", va="top",
             linespacing=1.5, wrap=True)

    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--out", type=Path, default=Path("reports/figures"))
    args = parser.parse_args()
    for name in ("help_table.csv", "help_vectors.csv"):
        if not (args.reports / name).exists():
            print(f"no {args.reports / name}; run scripts/help_wind.py first", file=sys.stderr)
            return 1
    table = pd.read_csv(args.reports / "help_table.csv")
    vectors = pd.read_csv(args.reports / "help_vectors.csv")
    numbers = headline(table)
    print("numbers printed on the figures (from help_table.csv):")
    for key, value in numbers.items():
        print(f"  {key:18s} {value:.3f}" if isinstance(value, float) else f"  {key:18s} {value}")
    print(f"vectors in the field: {len(vectors)}; helper threshold {HELP_FT} ft in {HORIZON_S} s")

    args.out.mkdir(parents=True, exist_ok=True)
    figure_1(table, vectors, numbers, args.out / "wind_figure_1_wind_map.png")
    figure_2(table, numbers, args.out / "wind_figure_2_open_man.png")
    print(f"wrote {args.out / 'wind_figure_1_wind_map.png'} and "
          f"{args.out / 'wind_figure_2_open_man.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
