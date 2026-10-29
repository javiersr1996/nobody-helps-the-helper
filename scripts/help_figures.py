"""The two figures of the second entry, and the wind map behind them (P8, W2).

Usage: uv run --extra figures python scripts/help_figures.py [--reports DIR] [--out DIR]

Needs `reports/help_table.csv` and `reports/help_vectors.csv`, which `scripts/help_wind.py`
writes. Everything is drawn in the DRIVE FRAME and in shot-chart orientation: the attacked
hoop at the bottom, the baseline under it, and the ball handler's lateral motion to the
RIGHT, so left- and right-hand drives pool and "the corner side" is always bottom right.

  1. **Does anyone else move toward the man the helper left?** The first scene of
     `reports/wind_scenes.json` (`scripts/wind_scenes.py`, chosen by rule, not by look):
     the ten players from the start to the headline horizon, named on the court rather than
     in a key, only the measure's cast in colour (the helper, the man he left, the three
     other defenders, the ball handler). Under the court, each of the three's movement
     toward the man left and toward the placebo, their difference and its mean, and where
     that mean sits among all helped drives, so one drive is never sold as typical. The
     claim itself is figure 2's.

  0. **The wind map** (not one of the README's two since 2026-10-29; the memoria and the
     page keep it). The mean displacement, over the first second of every drive, of the
     four defenders who are not the ball handler's matchup: a kernel-smoothed field drawn as
     streamlines, line width by how far the defence moves. Under it, in orange, the share of
     the defenders starting at each spot who are the HELPER (the largest mover, HELP_FT or
     more toward where the ball ends up), drawn only where enough defenders start, so white
     means nobody stands there. Context, not a claim about who helps: the strip states the
     corner as occupancy, with its per-defender rate, and that most helpers start above the
     ball, where a plain sink is movement toward it (`help_base_rate.csv`). The field shows
     the whole defence sinking with the drive as well as the help, and the strip says so.

  2. **Who covers the man he left.** Where the attacker the helper was guarding stands at the
     headline horizon (1.5 s), one dot per helped drive, coloured and shaped by which
     defender is nearest to him: the helper, the ball handler's defender, or a third. Under
     the court, the three other defenders' rotation toward him against the placebo, and the
     share nearest and the open share with its base rate.

Every number printed on either figure is computed here from the CSVs, never typed. On the
wind map and figure 2 nothing is drawn inside the court but the court, the data and the
ball's median path: numbers, keys and legends live in a strip under it, where no streamline
can cross them. Figure 1 draws one drive, sparse enough to name its players where they stand.

Needs `reports/help_base_rate.csv` from the same script, the `second_help_*.csv` drives,
summary, contrast and contrast_sensitivity, which `scripts/second_help.py` writes, and
`reports/wind_scenes.json`.

Writes {out}/wind_figure_1_one_drive.png, {out}/wind_figure_2_who_covers.png and
{out}/wind_map_league.png.
"""

from __future__ import annotations

import argparse
import json
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
PALE = "#cfcfcf"
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
#: Figure 1's orange: the helper rate per defender, kernel-smoothed like the field, drawn only
#: where RATE_MIN_WEIGHT defenders' worth of kernel mass started, in these bands. At 80 the
#: rate's binomial standard error stays near 3.5 points, under a band's width, and the
#: smoothing no longer bleeds into the corner-3 zone, where no defender starts (at 30 it did).
RATE_MIN_WEIGHT = 80.0
RATE_LEVELS = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 1.0)
RATE_ALPHA = 0.75
#: Streamline width, points, for a mean displacement of zero and of WIDTH_FULL_FT.
WIDTH_MIN, WIDTH_MAX, WIDTH_FULL_FT = 0.4, 2.8, 6.0

CORNER_Y_FT = 18.0
#: Figure 1's court is cropped this far above the hoop line (the arc's apex is 22.15 ft).
FIG1_TOP_FT = 27.0

#: Both figures are laid out top-down in inches (the strip carries paragraphs at TEXT_PT, so
#: the height follows from what it holds): width, each court's height, the side margin, the
#: line spacing and the characters per line that fit the width at TEXT_PT.
FIG2_WIDTH_IN, COURT_IN, COURT1_IN, MARGIN_IN = 7.2, 4.9, 6.2, 0.3
TEXT_PT, LINE_SPACING, WRAP_CHARS = 11, 1.4, 82


def to_plot(x, y) -> tuple[np.ndarray, np.ndarray]:
    """Drive-frame feet to plot feet: lateral across, distance from the hoop line up."""
    return np.asarray(y, float), np.asarray(x, float) - HOOP_X


def draw_court(ax, sides: bool = True) -> None:
    """The FIBA half court in plot feet: hoop at (0, 0), baseline below, half court on top.

    `sides` names the two corners under the baseline, which matters when drives are pooled
    and not when one drive is drawn.
    """
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
    if sides:
        ax.text(half - 0.6, baseline - 0.8, "corner side of the drive", fontsize=7.5,
                color=COURT, ha="right", va="top", style="italic")
        ax.text(-half + 0.6, baseline - 0.8, "far corner", fontsize=7.5, color=COURT,
                ha="left", va="top", style="italic")
    ax.set_aspect("equal")
    ax.set_xlim(-half - 1.5, half + 1.5)
    ax.set_ylim(baseline - (3.0 if sides else 0.5), top + 1.0)
    ax.axis("off")


def kernel_field(px, py, u, v, grid_x, grid_y, min_weight=MIN_WEIGHT):
    """Gaussian-weighted mean of (u, v) on the grid, masked where too few vectors are near."""
    gx, gy = np.meshgrid(grid_x, grid_y)
    d2 = (gx.ravel()[:, None] - px[None, :]) ** 2 + (gy.ravel()[:, None] - py[None, :]) ** 2
    w = np.exp(-0.5 * d2 / BANDWIDTH_FT**2)
    mass = w.sum(axis=1)
    safe = np.maximum(mass, 1e-9)
    mask = (mass < min_weight).reshape(gx.shape)
    U = np.ma.array((w @ u / safe).reshape(gx.shape), mask=mask)
    V = np.ma.array((w @ v / safe).reshape(gx.shape), mask=mask)
    return gx, gy, U, V


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
        "helper_start_dist": helped["helper_start_dist"].median(),
    }


def figure_1(scenes: dict, pairs: pd.DataFrame, path: Path) -> None:
    scene, t = scenes["scenes"][0], scenes["headline_frame"]
    # Every helped drive's mean over the three others of toward him minus placebo, at t: the
    # distribution this one drive is placed in, checked against what the scene recorded.
    at_t = pairs[pairs["helped"] & (pairs["horizon"] == t)]
    per_drive = (at_t["to_left"] - at_t["placebo"]).groupby(at_t["drive_id"]).mean()
    xy = np.array(scene["xy"], dtype=float)[: t + 1]  # frames, slots 0-4 attack 5-9 defence
    roles = scene["roles"]
    others = roles["others"]
    to_left = np.array([row[t] for row in scene["to_left"]])
    placebo = np.array([row[t] for row in scene["placebo"]])
    mean_diff = float((to_left - placebo).mean())
    if abs(mean_diff - scene["paired_mean_1_5s"]) > 0.01:
        raise ValueError(f"the scene's projections give {mean_diff:+.2f} ft, its record "
                         f"{scene['paired_mean_1_5s']:+.2f}: rerun scripts/wind_scenes.py")
    among = scene["paired_mean_1_5s_among_helped"]
    if (len(per_drive) != among["n_helped"]
            or abs(per_drive[scene["drive_id"]] - mean_diff) > 0.01
            or abs(per_drive.median() - among["median"]) > 0.01):
        raise ValueError("second_help_pairs.csv and wind_scenes.json disagree on the helped "
                         "drives at the headline horizon: rerun second_help.py, wind_scenes.py")
    seconds = t / scenes["fps"]
    window = (scenes["n_frames"] - 1) / scenes["fps"]
    clear = scene["clearance_ft"][f"{seconds:.1f}s"]
    placebo_men = [a for a in roles["off_ball"] if a != roles["left"]]
    #: Who is drawn how: slot -> colour, line width. Only the measure's cast is coloured; the
    #: other attackers are the placebo's grey, the ball handler's defender paler still.
    style = {roles["handler_def"]: (PALE, 1.2),
             **{s: (GREY, 1.2) for s in placebo_men},
             roles["handler"]: (INK, 2.2),
             roles["left"]: (INK, 1.6),
             **{s: (PURPLE, 1.8) for s in others},
             roles["helper"]: (ORANGE, 3.0)}
    on_court = {"fontsize": TEXT_PT, "zorder": 7,
                "bbox": {"boxstyle": "round,pad=0.15", "facecolor": "white", "edgecolor": "none",
                         "alpha": 0.85}}

    def fmt(v: float, d: int = 1) -> str:
        return f"{0:.{d}f}" if round(v, d) == 0 else f"{v:+.{d}f}".replace("-", "−")

    nb = " "  # a number and its unit never split across lines

    def build(height: float, out: Path | None) -> float:
        """Draw top-down on a figure `height` inches tall; return the inches used."""
        fig = plt.figure(figsize=(FIG2_WIDTH_IN, height))
        inches = fig.dpi_scale_trans
        used = [0.2]

        def put(text: str, gap: float = 0.14, **style_) -> None:
            wrapped = textwrap.fill(text, WRAP_CHARS)
            fig.text(MARGIN_IN, height - used[0], wrapped, transform=inches, va="top",
                     fontsize=TEXT_PT, color=INK, linespacing=LINE_SPACING, **style_)
            used[0] += (wrapped.count("\n") + 1) * TEXT_PT * LINE_SPACING / 72 + gap

        def frac(left, top, width, tall):  # inches from the top-left -> figure fractions
            return [left / FIG2_WIDTH_IN, 1 - (top + tall) / height, width / FIG2_WIDTH_IN,
                    tall / height]

        put("Does anyone else move toward the man the helper left?", gap=0.06, weight="bold")
        put(f"One drive, chosen by rule, to show the measure. The helper steps toward the ball "
            f"handler; {seconds:.1f}{nb}s later the man he was guarding is {clear:.1f}{nb}ft "
            f"from the nearest defender. For each of the three other defenders: how far he "
            f"moves toward that man, against how far toward the other attackers off the "
            f"ball.", gap=0.1)
        ax = fig.add_axes(frac(0.1, used[0], FIG2_WIDTH_IN - 0.2, COURT_IN))
        draw_court(ax, sides=False)
        # One drive fills the court near the hoop only: crop above it so the drive is drawn
        # larger, never closer than 2 ft above the highest point of any trail.
        reach = float(to_plot(xy[..., 0], xy[..., 1])[1].max()) + 2.0
        ax.set_ylim(ax.get_ylim()[0], max(FIG1_TOP_FT, reach))
        # Equal aspect: the court's own height at this width, so no blank band is left.
        (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
        court_h = (FIG2_WIDTH_IN - 0.2) * (y1 - y0) / (x1 - x0)
        ax.set_position(frac(0.1, used[0], FIG2_WIDTH_IN - 0.2, court_h))
        for slot, (colour, width) in style.items():
            px, py = to_plot(xy[:, slot, 0], xy[:, slot, 1])
            ax.plot(px, py, color=colour, linewidth=width, solid_capstyle="round", zorder=3)
            ax.scatter(px[:1], py[:1], s=28, facecolor="white", edgecolor=colour, linewidth=1.4,
                       zorder=4)
            if np.hypot(px[-1] - px[0], py[-1] - py[0]) < 1.5:  # stayed: the hollow says it
                continue
            # The arrow's direction from the last foot of the trail, not the last frame's jitter.
            back = np.hypot(px - px[-1], py - py[-1])
            tail = int(np.nonzero(back >= 1.0)[0][-1]) if (back >= 1.0).any() else 0
            ax.annotate("", xy=(px[-1], py[-1]), xytext=(px[tail], py[tail]), zorder=5,
                        arrowprops={"arrowstyle": "-|>", "color": colour, "linewidth": width,
                                    "mutation_scale": 14, "shrinkA": 0, "shrinkB": 0})
        # Named where they stand, not in a key: labels sit by each start, away from the
        # collapse into the paint where the trails end.
        start = {slot: to_plot(*xy[0, slot]) for slot in style}
        end = {slot: to_plot(*xy[-1, slot]) for slot in style}
        hx, hy = start[roles["handler"]]
        ax.text(hx, hy + 1.2, "ball handler", color=INK, ha="center", va="bottom", **on_court)
        hx, hy = start[roles["helper"]]
        ax.text(hx - 1.0, hy - 2.0, "helper", color=ORANGE, weight="bold", ha="center",
                va="top", **on_court)
        lx, ly = end[roles["left"]]
        ax.text(lx, ly + 1.2, "the man\nhe left", color=INK, weight="bold", ha="center",
                va="bottom", linespacing=1.1, **on_court)
        for n, slot in enumerate(others, start=1):  # behind where he moves, off his trail
            (ox, oy), (ex, ey) = start[slot], end[slot]
            back = np.hypot(ox - ex, oy - ey)
            ax.text(ox + 1.6 * (ox - ex) / back, oy + 1.6 * (oy - ey) / back, str(n),
                    color=PURPLE, weight="bold", ha="center", va="center", **on_court)
        used[0] += court_h + 0.15

        put(f"Hollow: where each player starts; arrows: where he is {seconds:.1f}{nb}s later. "
            f"Purple, 1 to 3: the three other defenders. Grey: the other attackers off the "
            f"ball; pale: the ball handler's defender.", gap=0.2)

        put(f"Feet each of the three moves in {seconds:.1f}{nb}s toward a target: his own "
            f"movement along the line from his start to where the target is then (negative: "
            f"away). The whole defence sinks with a drive, so the test is the difference "
            f"against the other attackers off the ball, his own man excepted (the placebo).",
            gap=0.05)
        chart_h = 1.25
        chart = fig.add_axes(frac(0.75, used[0] + 0.6, 4.2, chart_h))
        rows = np.arange(len(others))
        chart.barh(rows - 0.18, to_left, height=0.34, color=INK,
                   label="toward the man he left")
        chart.barh(rows + 0.18, placebo, height=0.34, color=GREY,
                   label="toward the other attackers, on average")
        chart.axvline(0, color=COURT, linewidth=1.0)
        span = max(abs(to_left).max(), abs(placebo).max())
        chart.set_xlim(-span - 2.5, span + 2.5)
        for row, a, b in zip(rows, to_left, placebo, strict=True):
            for value, shift in ((a, -0.18), (b, 0.18)):
                chart.text(value + (0.3 if value >= 0 else -0.3), row + shift, fmt(value),
                           fontsize=TEXT_PT - 1, va="center",
                           ha="left" if value >= 0 else "right")
            # The difference per defender, then their mean: the number the strip places.
            chart.text(1.22, row, fmt(a - b), transform=chart.get_yaxis_transform(),
                       fontsize=TEXT_PT, va="center", ha="right")
        chart.text(1.22, -0.6, "black − grey", transform=chart.get_yaxis_transform(),
                   fontsize=TEXT_PT - 1, va="bottom", ha="right", color=COURT)
        chart.text(1.22, len(others) - 0.15, f"mean {fmt(mean_diff, 2)}",
                   transform=chart.get_yaxis_transform(), fontsize=TEXT_PT, va="top",
                   ha="right", color=PURPLE, weight="bold")
        chart.set_yticks(rows, [str(n) for n in range(1, len(others) + 1)])
        chart.set_ylim(len(others) - 0.5, -0.5)
        chart.tick_params(labelsize=TEXT_PT, length=3)
        chart.tick_params(axis="y", colors=PURPLE)
        chart.set_xlabel("feet", fontsize=TEXT_PT, labelpad=2)
        for spine in ("top", "right"):
            chart.spines[spine].set_visible(False)
        chart.legend(loc="lower left", bbox_to_anchor=(0.0, 1.04), frameon=False,
                     fontsize=TEXT_PT - 1, handlelength=1.2, borderaxespad=0)
        used[0] += 0.6 + chart_h + 0.55

        put(f"That mean, for each of the {len(per_drive)} drives with a helper. Left of 0, "
            f"the three moved less toward the man he left than toward the other attackers.",
            gap=0.05)
        strip_h = 1.1
        strip = fig.add_axes(frac(0.75, used[0] + 0.45, FIG2_WIDTH_IN - 1.2, strip_h))
        edges = np.arange(np.floor(per_drive.min()), np.ceil(per_drive.max()) + 0.5, 0.5)
        strip.hist(per_drive, bins=edges, color=GREY, edgecolor="white", linewidth=0.5)
        strip.axvline(0, color=COURT, linewidth=1.0)
        strip.axvline(per_drive.median(), color=INK, linewidth=1.4, linestyle="--")
        strip.axvline(mean_diff, color=PURPLE, linewidth=2.4)
        top = strip.get_ylim()[1]
        strip.text(mean_diff - 0.25, top * 1.04, f"this drive {fmt(mean_diff, 2)}, percentile "
                   f"{among['percentile']:.0f}", color=PURPLE, fontsize=TEXT_PT - 1,
                   ha="right", va="bottom", weight="bold")
        strip.text(per_drive.median() + 0.25, top * 1.04,
                   f"median {fmt(per_drive.median(), 2)}", color=INK, fontsize=TEXT_PT - 1,
                   ha="left", va="bottom")
        strip.tick_params(labelsize=TEXT_PT, length=3)
        strip.set_xlabel("feet", fontsize=TEXT_PT, labelpad=2)
        strip.set_ylabel("drives", fontsize=TEXT_PT, labelpad=4)
        for spine in ("top", "right"):
            strip.spines[spine].set_visible(False)
        used[0] += 0.45 + strip_h + 0.55

        put(f"Chosen by rule, not by look: the first drive with a helper, in the first game, "
            f"with all ten players detected for its whole {window:.0f}{nb}s window. Figure 2 "
            f"has the result, over all drives and against drives with no helper.", gap=0.1)
        if out is not None:
            fig.savefig(out, dpi=200)
        plt.close(fig)
        return used[0]

    build(build(40.0, None), path)  # the first pass only measures the height it needs


def wind_map(table: pd.DataFrame, vectors: pd.DataFrame, rates: pd.DataFrame, numbers: dict,
             path: Path) -> None:
    px, py = to_plot(vectors["origin_x"], vectors["origin_y"])
    u, v = vectors["dy"].to_numpy(float), vectors["dx"].to_numpy(float)  # lateral, along
    grid_x = np.arange(-24.0, 24.0 + GRID_FT, GRID_FT)
    grid_y = np.arange(-3.0, 38.0 + GRID_FT, GRID_FT)
    gx, gy, U, V = kernel_field(px, py, u, v, grid_x, grid_y)
    magnitude = np.ma.filled(np.hypot(U, V), 0.0)

    # Which vector is the helper: help_table's (help_wind.py refuses to run if the vectors
    # disagree), checked here against the per-defender counts the strip prints.
    helper_slot = vectors["drive_id"].map(
        table[table["has_helper"]].set_index("drive_id")["helper_def_slot"])
    flag = (vectors["def_slot"] == helper_slot).to_numpy(float)
    by_y = rates[(rates["grouping"] == "y_band")
                 & (rates["standardised_by"] == "none")].set_index("group")
    bearing = rates[rates["grouping"] == "bearing_band"]
    if int(flag.sum()) != int(by_y["n_helpers"].sum()) or len(flag) != by_y["n_defenders"].sum():
        raise ValueError("help_table, help_vectors and help_base_rate disagree: rerun help_wind.py")
    # The kernel mean of a 0/1 flag is the share of the defenders starting nearby who are it.
    _, _, rate, _ = kernel_field(px, py, flag, flag, grid_x, grid_y, RATE_MIN_WEIGHT)
    colours = plt.get_cmap("Oranges")(np.linspace(0.12, 0.85, len(RATE_LEVELS) - 1))
    corner, middle = by_y.iloc[-1], by_y.iloc[0]  # the |y| bands run from the middle out
    if not str(corner.name).startswith(f"{CORNER_Y_FT:g}-"):
        raise ValueError(f"the last |y| band is {corner.name}, not the corner side")
    above = (vectors.loc[flag == 1, "target_bearing_x"] < 0).mean()
    ok = table[table["status"] == "ok"]
    start = to_plot(ok["handler_x0"].median(), ok["handler_y0"].median())
    end = to_plot(ok["handler_x1"].median(), ok["handler_y1"].median())
    pct = lambda v, d=0: f"{100 * v:.{d}f}%"  # noqa: E731

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

        put("Where the defence goes in the first second of a drive", gap=0.06, weight="bold")
        put(f"Almost no defender starts in the corner, so almost no help comes from there. Of "
            f"the helpers, {pct(above)} start above the ball, where sinking is moving toward it.",
            gap=0.1)
        ax = fig.add_axes(frac(0.1, used[0], FIG2_WIDTH_IN - 0.2, COURT1_IN))
        draw_court(ax)
        ax.contourf(gx, gy, rate, levels=RATE_LEVELS, colors=colours, alpha=RATE_ALPHA)
        ax.streamplot(grid_x, grid_y, U, V, density=1.2, color=INK,
                      linewidth=width_of(magnitude), arrowsize=0.9, arrowstyle="-|>", zorder=3)
        ax.annotate("", xy=end, xytext=start, zorder=5,
                    arrowprops={"arrowstyle": "-|>", "color": "black", "linewidth": 2.4,
                                "shrinkA": 0, "shrinkB": 0})
        ax.scatter([start[0]], [start[1]], s=70, color="white", edgecolor="black",
                   linewidth=1.6, zorder=6)
        ax.text(start[0] - 1.4, start[1] + 0.6, "the ball:\nmedian start,\none second later",
                fontsize=TEXT_PT - 1, color="black", ha="right", va="bottom", zorder=6,
                linespacing=1.3,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.9, "pad": 1.5})
        used[0] += COURT1_IN + 0.15

        # Two keys side by side: line width, and the orange bands (white: too few defenders).
        widths = fig.add_axes(frac(MARGIN_IN, used[0], 2.6, 0.9))
        widths.axis("off")
        widths.set_xlim(0, 1)
        widths.set_ylim(0, 1)
        widths.text(0.0, 1.0, "line width: mean displacement", fontsize=TEXT_PT, va="top")
        for i, feet in enumerate((1.0, 3.0, 6.0)):
            y = 0.62 - 0.27 * i
            widths.plot([0.0, 0.25], [y, y], color=INK, linewidth=width_of(feet),
                        solid_capstyle="butt")
            widths.text(0.3, y, f"{feet:.0f} ft in {HORIZON_S:.0f} s", fontsize=TEXT_PT,
                        va="center")
        bands = fig.add_axes(frac(3.3, used[0], FIG2_WIDTH_IN - 3.3 - MARGIN_IN, 0.9))
        bands.axis("off")
        bands.set_xlim(0, len(colours) + 0.4)
        bands.set_ylim(0, 1)
        bands.text(0.0, 1.0, "orange: % of the defenders starting there\nwho are the helper "
                   "(white: too few for a rate)", fontsize=TEXT_PT, va="top", linespacing=1.2)
        for i, colour in enumerate(colours):
            bands.add_patch(plt.Rectangle((i, 0.12), 1, 0.2, color=colour, alpha=RATE_ALPHA))
            bands.text(i, 0.07, f"{100 * RATE_LEVELS[i]:.0f}", fontsize=TEXT_PT - 2,
                       ha="center", va="top")
        used[0] += 0.9 + 0.25

        put(f"{numbers['n_resolved']} drives, ten ACB games, the first {HORIZON_S:.0f} s of each. "
            f"Streamlines: where the four defenders off the ball move, all of them, so the field "
            f"carries the whole defence sinking with the drive as well as the help.")
        put(f"Helper: the defender who moves most toward where the ball will be, "
            f"{HELP_FT:.0f} ft or more, in {numbers['n_helped']} drives "
            f"({pct(numbers['share_helped'])}). Of the {len(flag):,} defenders off the ball, "
            f"{pct(flag.mean(), 1)} are one.")
        put(f"The corner: {corner['n_defenders']} defenders ({pct(corner['defender_share'], 1)}) "
            f"start more than {CORNER_Y_FT:.0f} ft from the middle, and {corner['n_helpers']} "
            f"helpers ({pct(corner['helper_share'], 1)}) come from there. Each is the helper "
            f"{pct(corner['rate'])} of the time (95% CI {pct(corner['rate_low'])} to "
            f"{pct(corner['rate_high'])}), against {pct(middle['rate'])} in the middle: the "
            f"corner is empty, and too few stand there to say whether it helps less.")
        put(f"Above the ball: {pct(above)} of helpers start farther from the hoop line than "
            f"where the ball goes, where a plain sink counts as movement toward it. A defender "
            f"is the helper {pct(bearing['rate'].iloc[0])} of the time when that spot lies "
            f"mostly toward the hoop from him, {pct(bearing['rate'].iloc[-1])} when it lies "
            f"mostly away.", gap=0.1)
        if out is not None:
            fig.savefig(out, dpi=200)
        plt.close(fig)
        return used[0]

    build(build(40.0, None), path)  # the first pass only measures the height it needs


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
                         ("help_base_rate.csv", "help_wind"),
                         ("second_help_drives.csv", "second_help"),
                         ("second_help_summary.csv", "second_help"),
                         ("second_help_contrast.csv", "second_help"),
                         ("second_help_contrast_sensitivity.csv", "second_help"),
                         ("second_help_pairs.csv", "second_help"),
                         ("wind_scenes.json", "wind_scenes")):
        if not (args.reports / name).exists():
            print(f"no {args.reports / name}; run scripts/{script}.py first", file=sys.stderr)
            return 1
    table = pd.read_csv(args.reports / "help_table.csv")
    vectors = pd.read_csv(args.reports / "help_vectors.csv")
    rates = pd.read_csv(args.reports / "help_base_rate.csv")
    second = pd.read_csv(args.reports / "second_help_drives.csv")
    summary = pd.read_csv(args.reports / "second_help_summary.csv")
    contrasts = pd.read_csv(args.reports / "second_help_contrast.csv")
    sweep = pd.read_csv(args.reports / "second_help_contrast_sensitivity.csv")
    scenes = json.loads((args.reports / "wind_scenes.json").read_text(encoding="utf-8"))
    pairs = pd.read_csv(args.reports / "second_help_pairs.csv")
    numbers = headline(table)
    print("numbers printed on the figures (from help_table.csv):")
    for key, value in numbers.items():
        print(f"  {key:18s} {value:.3f}" if isinstance(value, float) else f"  {key:18s} {value}")
    print(f"vectors in the field: {len(vectors)}; helper threshold {HELP_FT} ft in {HORIZON_S} s")

    args.out.mkdir(parents=True, exist_ok=True)
    figure_1(scenes, pairs, args.out / "wind_figure_1_one_drive.png")
    figure_2(second, summary, contrasts, sweep, args.out / "wind_figure_2_who_covers.png")
    wind_map(table, vectors, rates, numbers, args.out / "wind_map_league.png")
    print(f"wrote {args.out / 'wind_figure_1_one_drive.png'}, "
          f"{args.out / 'wind_figure_2_who_covers.png'} and {args.out / 'wind_map_league.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
