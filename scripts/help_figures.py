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

  2. **Who covers the man he left.** Where the attacker the helper was guarding stands at the
     headline horizon (1.5 s), one dot per helped drive, coloured and shaped by which
     defender is nearest to him: the helper, the ball handler's defender, or a third. Under
     the court, the three other defenders' rotation toward him against the placebo, and the
     share nearest and the open share with its base rate.

Every number printed on either figure is computed here from the CSVs, never typed. Nothing
is drawn inside the court but the court, the data and the ball's median path: numbers,
keys and legends live in a strip under it, where no streamline can cross them.

Needs the `second_help_*.csv` drives, summary, contrast and contrast_sensitivity too, which
`scripts/second_help.py` writes.

Writes {out}/wind_figure_1_wind_map.png and {out}/wind_figure_2_who_covers.png.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from scbasket.court import CORNER_LINE_Y_FT, FIBA, HOOP_X, THREE_RADIUS_FT
from scbasket.rotation import HEADLINE_HORIZON
from scbasket.wind import HELP_FT, HORIZON_S

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

INK = "#2b2b2b"
COURT = "#555555"
ORANGE = "#f0a33c"
GREY = "#9a9a9a"
BLUE = "#0072b2"
PURPLE = "#cc79a7"

#: Figure 2's nearest defender: colour and marker (the shape repeats the colour for readers
#: who cannot tell them apart), then the name in the key.
WHO_STYLE = {
    "helper": (ORANGE, "o", "the helper"),
    "handler_def": (BLUE, "s", "the ball handler's defender"),
    "third": (PURPLE, "^", "a third defender"),
}
#: The horizons the rotation chart is drawn at, in frames (1.0, 1.5, 2.0 s).
CHART_HORIZONS = (25, 38, 50)

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

#: Figure layout, figure fractions: the court on top, a strip under it for everything else.
FIGSIZE = (7.2, 8.9)
COURT_BOX = (0.03, 0.175, 0.94, 0.745)
STRIP_TOP = 0.15
#: Figure 2 is laid out top-down in inches (the strip carries a chart and five paragraphs at
#: TEXT_PT, so its height follows from what it holds): width, the court's height, the side
#: margin, the line spacing and the characters per line that fit the width at TEXT_PT.
FIG2_WIDTH_IN, COURT_IN, MARGIN_IN = 7.2, 4.9, 0.3
TEXT_PT, LINE_SPACING, WRAP_CHARS = 11, 1.4, 82


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
    return {
        "n_drives": len(table),
        "n_resolved": len(ok),
        "n_helped": len(helped),
        "share_helped": len(helped) / len(ok),
        "from_middle": (helped["helper_origin_y"].abs() < MIDDLE_Y_FT).mean(),
        "from_corner_side": (helped["helper_origin_y"].abs() > CORNER_Y_FT).mean(),
        "helper_start_dist": helped["helper_start_dist"].median(),
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


def figure_2(drives: pd.DataFrame, summary: pd.DataFrame, contrasts: pd.DataFrame,
             sweep: pd.DataFrame, path: Path) -> None:
    def cell(horizon: int, helped: bool) -> pd.Series:
        return summary[(summary["horizon"] == horizon) & (summary["helped"] == helped)].iloc[0]

    contrast = {h: contrasts[contrasts["horizon"] == h].iloc[0] for h in CHART_HORIZONS}
    for h, c in contrast.items():  # the figure says "no more than with no helper": fail if not
        if c["contrast_ci_low"] > 0:
            raise ValueError(f"helped minus no-helper is above 0 at {h} frames "
                             f"(95% CI low {c['contrast_ci_low']:+.2f}): the claim does not hold")

    head, base = cell(HEADLINE_HORIZON, True), cell(HEADLINE_HORIZON, False)
    seconds = f"{head['horizon_s']:.1f} s"
    dots = drives[drives["helped"]].dropna(subset=[f"left_x_{HEADLINE_HORIZON}",
                                                   f"nearest_who_{HEADLINE_HORIZON}"])
    n_cut = int(drives["helped"].sum()) - len(dots)
    contain = int(((sweep["contrast_ci_low"] <= 0) & (sweep["contrast_ci_high"] >= 0)).sum())
    above = int((sweep["contrast_ci_low"] > 0).sum())
    thresholds = ", ".join(f"{t:.0f}" for t in sorted(sweep["help_ft"].unique()))
    pct = lambda v: f"{100 * v:.0f}%"  # noqa: E731

    def build(height: float, out: Path | None) -> float:
        """Draw top-down on a figure `height` inches tall; return the inches used."""
        fig = plt.figure(figsize=(FIG2_WIDTH_IN, height))
        inches = fig.dpi_scale_trans
        used = [0.2]

        def put(text: str, gap: float = 0.14, **style) -> None:
            wrapped = textwrap.fill(text, WRAP_CHARS)
            fig.text(MARGIN_IN, height - used[0], wrapped, transform=inches, va="top",
                     fontsize=TEXT_PT, color=INK, linespacing=LINE_SPACING, **style)
            used[0] += (wrapped.count("\n") + 1) * TEXT_PT * LINE_SPACING / 72 + gap

        def frac(left, top, width, tall):  # inches from the top-left -> figure fractions
            return [left / FIG2_WIDTH_IN, 1 - (top + tall) / height, width / FIG2_WIDTH_IN,
                    tall / height]

        put("Nobody else moves toward the man the helper left", gap=0.06, weight="bold")
        put(f"{seconds} into the drive, with a helper the three other defenders move toward him "
            f"no more than they do when there is no helper.", gap=0.1)
        ax = fig.add_axes(frac(0.1, used[0], FIG2_WIDTH_IN - 0.2, COURT_IN))
        draw_court(ax)
        for z, (who, (color, marker, _)) in enumerate(WHO_STYLE.items()):
            mine = dots[dots[f"nearest_who_{HEADLINE_HORIZON}"] == who]  # the rarer on top
            px, py = to_plot(mine[f"left_x_{HEADLINE_HORIZON}"],
                             mine[f"left_y_{HEADLINE_HORIZON}"])
            ax.scatter(px, py, s=34, marker=marker, color=color, edgecolor="white",
                       linewidth=0.5, zorder=4 + z)
        used[0] += COURT_IN + 0.1

        shares = {"helper": (f"{pct(head['nearest_helper'])} (with no helper, his own "
                             f"defender: {pct(base['nearest_helper'])})"),
                  "handler_def": f"{pct(head['nearest_handler_def'])} "
                                 f"({pct(base['nearest_handler_def'])})",
                  "third": f"{pct(head['nearest_third'])} ({pct(base['nearest_third'])})"}
        key = fig.legend(
            handles=[Line2D([], [], marker=m, linestyle="none", markersize=8, color=c,
                            label=f"{n} {shares[who]}") for who, (c, m, n) in WHO_STYLE.items()],
            title=f"Nearest defender at {seconds}, median {head['nearest_dist_median']:.1f} ft "
                  f"away (no helper: {base['nearest_dist_median']:.1f} ft)\n"
                  f"{len(dots)} of {len(dots) + n_cut} helped drives; {n_cut} end sooner",
            loc="upper left", bbox_to_anchor=(MARGIN_IN / FIG2_WIDTH_IN - 0.01,
                                              1 - used[0] / height),
            frameon=False, fontsize=TEXT_PT, title_fontsize=TEXT_PT, handletextpad=0.3,
            labelspacing=0.5, borderaxespad=0)
        key._legend_box.align = "left"
        used[0] += 5 * TEXT_PT * LINE_SPACING / 72 + 0.25
        put("Rotation toward him minus toward the placebo: mean over drives, 95% CI.",
            gap=0.04)
        fig.legend(handles=[Line2D([], [], marker="o", color=c, markersize=8, linewidth=1.6,
                                   label=n) for c, n in ((INK, "helped drives"),
                                                         (GREY, "drives with no helper"))],
                   loc="upper left", bbox_to_anchor=(MARGIN_IN / FIG2_WIDTH_IN - 0.01,
                                                     1 - used[0] / height),
                   ncol=2, frameon=False, fontsize=TEXT_PT, handletextpad=0.3,
                   columnspacing=1.4, borderaxespad=0)
        used[0] += 0.4
        chart_h = 1.4
        chart = fig.add_axes(frac(0.85, used[0] + 0.3, 3.5, chart_h))
        rows = np.arange(len(CHART_HORIZONS))
        for helped, color, shift in ((True, INK, -0.16), (False, GREY, 0.16)):
            cells = [cell(h, helped) for h in CHART_HORIZONS]
            mean = np.array([c["mean_diff"] for c in cells])
            low, high = (np.array([c["ci_low"] for c in cells]),
                         np.array([c["ci_high"] for c in cells]))
            chart.errorbar(mean, rows + shift, xerr=[mean - low, high - mean], fmt="o",
                           color=color, markersize=8, capsize=4, linewidth=1.8)
        chart.axvline(0, color=COURT, linewidth=1.0)
        chart.set_yticks(rows, [f"{cell(h, True)['horizon_s']:.1f} s" for h in CHART_HORIZONS])
        chart.set_ylim(len(CHART_HORIZONS) - 0.5, -0.5)
        chart.tick_params(labelsize=TEXT_PT, length=3)
        chart.set_xlabel("feet", fontsize=TEXT_PT, labelpad=2)
        for spine in ("top", "right"):
            chart.spines[spine].set_visible(False)
        columns = (0.15 / 3.5, 0.95 / 3.5, 1.8 / 3.5)  # inches from the chart, over its width
        for x, label in zip(columns, ("mean", "median", "pairs > 0"), strict=True):
            chart.text(1.0 + x, 1.05, label, transform=chart.transAxes, fontsize=TEXT_PT,
                       color=INK, ha="left", va="bottom")
        for row, h in zip(rows, CHART_HORIZONS, strict=True):
            c = cell(h, True)
            for x, value in zip(columns, (f"{c['mean_diff']:+.2f}", f"{c['median_diff']:+.2f}",
                                          pct(c["share_diff_positive"])), strict=True):
                chart.text(1.0 + x, row, value, transform=chart.get_yaxis_transform(),
                           fontsize=TEXT_PT, color=INK, ha="left", va="center")
        used[0] += 0.3 + chart_h + 0.5
        put("A pair = one drive and one of the three others. Median near 0: the typical pair "
            "moves as toward the placebo, and the mean is pulled by the tails. Grey is below 0 "
            "too, so the baseline is the grey series, not 0.", gap=0.1)
        put("Helped minus no helper, mean (95% CI): " + "; ".join(
            f"{cell(h, True)['horizon_s']:.1f} s {c['contrast_mean']:+.2f} "
            f"({c['contrast_ci_low']:+.2f} to {c['contrast_ci_high']:+.2f})"
            for h, c in contrast.items()) + ". Every interval contains 0: no more rotation "
            "than with no helper.", gap=0.1)
        put(f"Helper threshold {thresholds} ft x three horizons: {contain} of {len(sweep)} "
            f"of these intervals contain 0, and {above or 'none'} lie above it.", gap=0.1)
        if out is not None:
            fig.savefig(out, dpi=200)
        plt.close(fig)
        return used[0]

    build(build(40.0, None), path)  # the first pass only measures the height it needs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--out", type=Path, default=Path("reports/figures"))
    args = parser.parse_args()
    for name, script in (("help_table.csv", "help_wind"), ("help_vectors.csv", "help_wind"),
                         ("second_help_drives.csv", "second_help"),
                         ("second_help_summary.csv", "second_help"),
                         ("second_help_contrast.csv", "second_help"),
                         ("second_help_contrast_sensitivity.csv", "second_help")):
        if not (args.reports / name).exists():
            print(f"no {args.reports / name}; run scripts/{script}.py first", file=sys.stderr)
            return 1
    table = pd.read_csv(args.reports / "help_table.csv")
    vectors = pd.read_csv(args.reports / "help_vectors.csv")
    second = pd.read_csv(args.reports / "second_help_drives.csv")
    summary = pd.read_csv(args.reports / "second_help_summary.csv")
    contrasts = pd.read_csv(args.reports / "second_help_contrast.csv")
    sweep = pd.read_csv(args.reports / "second_help_contrast_sensitivity.csv")
    numbers = headline(table)
    print("numbers printed on the figures (from help_table.csv):")
    for key, value in numbers.items():
        print(f"  {key:18s} {value:.3f}" if isinstance(value, float) else f"  {key:18s} {value}")
    print(f"vectors in the field: {len(vectors)}; helper threshold {HELP_FT} ft in {HORIZON_S} s")

    args.out.mkdir(parents=True, exist_ok=True)
    figure_1(table, vectors, numbers, args.out / "wind_figure_1_wind_map.png")
    figure_2(second, summary, contrasts, sweep, args.out / "wind_figure_2_who_covers.png")
    print(f"wrote {args.out / 'wind_figure_1_wind_map.png'} and "
          f"{args.out / 'wind_figure_2_who_covers.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
