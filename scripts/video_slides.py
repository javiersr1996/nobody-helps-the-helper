"""The one-minute video, rendered as slides and assembled into a silent, timed MP4 (P7.5).

Usage: uv run --extra figures python scripts/video_slides.py [--reports DIR] [--out DIR]
                                                             [--no-video]

The competition asks for a minute of video in the entrant's own voice. The voice is the one
part a script cannot produce, so this produces everything else: five 1920x1080 slides and an
MP4 that holds each of them for exactly as long as its line takes to say, so the recording is
a single pass of narration over a finished picture.

The timings come from `tasks/video_script.md` and are repeated in `SLIDES` below. They are the
measured ones: 141 spoken words, 56 s at 150 words per minute and 62 s at 135, which is the
realistic pace for a script with numbers in it. The slides run to 60 s exactly.

House style is the figures': white ground, black for the held-out half, grey for calibration,
and the same orange the zone is shaded with. Slides 3 and 4 are the two figures the README
already carries, dropped in whole rather than redrawn, because the thing the audience is asked
to trust is the thing the repository publishes.

Slide 2 is the only new picture in the entry and it carries the refutation: two balls arriving
at the same rim, one steep and one still carrying sideways, landing at different distances.
That is the whole of what the ball turned out to say, and it is geometry.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

W, H, DPI = 19.2, 10.8, 100          # 1920x1080
INK, GREY, ACCENT, FAINT = "#1a1a1a", "#8c8c8c", "#f0a33c", "#d8d8d8"

#: (name, seconds) in order. The seconds are the script's shot list, and they sum to 60.
SLIDES = [
    ("slide_1_title", 8),
    ("slide_2_the_ball", 16),
    ("slide_3_lift", 18),
    ("slide_4_control", 10),
    ("slide_5_record", 8),
]


def blank():
    """A 1920x1080 figure with nothing on it but white."""
    fig = plt.figure(figsize=(W, H), dpi=DPI, facecolor="white")
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    return fig, ax


def title_slide(ax) -> None:
    ax.text(0.08, 0.60, "Nobody reads\nthe bounce", fontsize=96, color=INK, va="center",
            linespacing=1.05, fontweight="bold")
    ax.text(0.08, 0.34, "the eight feet where the rebound is decided",
            fontsize=34, color=GREY, va="center")
    ax.plot([0.08, 0.36], [0.27, 0.27], color=ACCENT, linewidth=6)
    ax.text(0.08, 0.17, "ten ACB games of SkillCorner's open tracking   ·   scbasket",
            fontsize=24, color=GREY, va="center")


def ball_slide(ax) -> None:
    """Two balls through the SAME point at rim height, landing at different distances.

    The only thing that differs between them is how much they are still carrying sideways
    when they get there, which is the whole of what the ball turned out to say.
    """
    floor, rim_x, rim_y = 0.20, 0.22, 0.58
    ax.plot([0.04, 0.66], [floor, floor], color=INK, linewidth=3)
    ax.plot([rim_x - 0.035, rim_x + 0.035], [rim_y, rim_y], color=INK, linewidth=8)
    ax.plot([rim_x, rim_x], [floor, rim_y], color=FAINT, linewidth=3)
    ax.text(rim_x - 0.055, rim_y, "rim height", fontsize=22, color=GREY, ha="right",
            va="center")

    for label, back, rise, land, colour, style in (
        ("steep", 0.045, 0.17, 0.30, GREY, "--"),
        ("still carrying", 0.165, 0.10, 0.55, INK, "-"),
    ):
        # incoming: a straight fall into the rim point, steeper for the first ball
        ax.plot([rim_x - back, rim_x], [rim_y + rise, rim_y], color=colour, linewidth=4,
                linestyle=style)
        # where it ends up, drawn dotted because the bounce itself is not modelled here
        t = np.linspace(0, 1, 60)
        x = rim_x + (land - rim_x) * t
        y = rim_y - (rim_y - floor) * t**1.8
        ax.plot(x, y, color=colour, linewidth=3, linestyle=":")
        ax.scatter([land], [floor], s=300, color=colour, zorder=3)
        ax.annotate(label, (land, floor), xytext=(0, 34), textcoords="offset points",
                    fontsize=25, color=colour, ha="center")
        ax.add_patch(FancyArrowPatch((rim_x, floor - 0.06), (land, floor - 0.06),
                                     arrowstyle="<->", mutation_scale=22, color=colour,
                                     linewidth=2))
    ax.text(0.38, floor - 0.12, "how far the rebound lands", fontsize=23, color=GREY,
            ha="center")

    ax.text(0.06, 0.92, "The ball says one thing, and it is geometry",
            fontsize=46, color=INK, fontweight="bold")
    ax.text(0.06, 0.855, "a ball still travelling outward when it reaches rim height lands "
                         "further out", fontsize=27, color=GREY)

    ax.plot([0.68, 0.68], [0.16, 0.80], color=FAINT, linewidth=2)
    ax.text(0.71, 0.75, "rank correlation with\nhow far the rebound lands", fontsize=22,
            color=GREY, linespacing=1.3, va="top")
    ax.text(0.71, 0.63, "calibration", fontsize=19, color=GREY)
    ax.text(0.865, 0.63, "held out", fontsize=19, color=GREY)
    for i, (what, cal, held, colour) in enumerate((
        ("how far it is still carrying", "+0.57", "+0.57", INK),
        ("how steeply it falls", "+0.17", "+0.22", GREY),
        ("the arrival angle, holding both", "-0.04", "-0.01", GREY),
    )):
        y = 0.55 - i * 0.15
        ax.text(0.71, y, what, fontsize=23, color=colour)
        ax.text(0.71, y - 0.06, cal, fontsize=34, color=colour,
                fontweight="bold" if colour == INK else "normal")
        ax.text(0.865, y - 0.06, held, fontsize=34, color=colour,
                fontweight="bold" if colour == INK else "normal")


def figure_slide(ax, path: Path) -> bool:
    """One of the README's two figures, whole and unaltered, filling the frame.

    No caption is added over it: the figures carry their own titles, and what the audience is
    asked to trust should be exactly what the repository publishes, down to the wording.
    """
    if not path.exists():
        return False
    inner = ax.figure.add_axes((0.03, 0.03, 0.94, 0.94))
    inner.set_axis_off()
    inner.imshow(plt.imread(path))
    return True


def record_slide(ax, lines: list[str]) -> None:
    ax.text(0.06, 0.90, "Frozen before the held-out games were opened",
            fontsize=44, color=INK, fontweight="bold")
    ax.text(0.06, 0.83, "and the ones that failed are in there too", fontsize=28, color=GREY)
    for i, line in enumerate(lines[:6]):
        y = 0.68 - i * 0.10
        sha, _, subject = line.partition(" ")
        if len(subject) > 66:                       # cut at a word, never mid-word
            subject = subject[:66].rsplit(" ", 1)[0] + " ..."
        ax.text(0.06, y, sha, fontsize=21, color=ACCENT, family="monospace")
        ax.text(0.14, y, subject, fontsize=21, color=INK, family="monospace")


def git_lines() -> list[str]:
    """The freeze commits, read from the repository rather than typed out."""
    wanted = ("Freeze", "Refute", "Retire", "Grade", "Record the P7.2")
    out = subprocess.run(["git", "log", "--oneline", "-40"], capture_output=True, text=True)
    lines = [ln for ln in out.stdout.splitlines() if any(w in ln for w in wanted)]
    return lines or out.stdout.splitlines()[:6]


def assemble(out: Path, paths: list[tuple[Path, int]]) -> bool:
    """One silent MP4 holding each slide for its own number of seconds."""
    if shutil.which("ffmpeg") is None:
        print("no ffmpeg on the PATH; the slides are written, the video is not", file=sys.stderr)
        return False
    listing = out / "slides.txt"
    body = "".join(f"file '{p.name}'\nduration {s}\n" for p, s in paths)
    listing.write_text(body + f"file '{paths[-1][0].name}'\n", encoding="utf-8")
    mp4 = out / "nobody_reads_the_bounce.mp4"
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
           "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium",
           "-crf", "20", str(mp4)]
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        print(done.stderr[-800:], file=sys.stderr)
        return False
    print(f"wrote {mp4} ({mp4.stat().st_size / 1e6:.1f} MB, {sum(s for _, s in paths)} s)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, default=Path("reports/figures"))
    parser.add_argument("--out", type=Path, default=Path("reports/video"))
    parser.add_argument("--no-video", action="store_true", help="slides only, skip ffmpeg")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    written: list[tuple[Path, int]] = []
    for name, seconds in SLIDES:
        fig, ax = blank()
        if name == "slide_1_title":
            title_slide(ax)
        elif name == "slide_2_the_ball":
            ball_slide(ax)
        elif name == "slide_3_lift":
            ok = figure_slide(ax, args.reports / "figure_1_lift_by_distance.png")
            if not ok:
                print("run scripts/figures.py first", file=sys.stderr)
                return 1
        elif name == "slide_4_control":
            figure_slide(ax, args.reports / "figure_2_pwin_by_angle.png")
        else:
            record_slide(ax, git_lines())

        path = args.out / f"{name}.png"
        fig.savefig(path, dpi=DPI, facecolor="white")
        plt.close(fig)
        written.append((path, seconds))
        print(f"wrote {path}  ({seconds} s)")

    print(f"\n{len(written)} slides, {sum(s for _, s in written)} s in total, "
          f"against 141 spoken words (56 s at 150 wpm, 62 s at 135)")
    if args.no_video:
        return 0
    return 0 if assemble(args.out, written) else 1


if __name__ == "__main__":
    raise SystemExit(main())
