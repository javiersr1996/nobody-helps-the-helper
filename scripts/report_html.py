"""The interactive page: the whole argument in one self-contained HTML file (P7.8).

Usage: uv run python scripts/report_html.py [--reports DIR] [--out FILE]

The competition deliverables do not change: a minute of video, a README of at most 1000
words and two figures. This is the extra a judge can click through, and it is the same
argument in the same order, with the numbers live instead of drawn.

Every number in a chart or a table on the page arrives in the payload below, and every value
in the payload is read off a `reports/*.csv` or off a frozen constant in `scbasket` (lesson 1:
a number with no code behind it is not a finding). The template types none of them. What it
does type is the handful of figures inside the negatives, which are quoted from the record
and have no CSV of their own; the page says so where it says it.

The banded tables and their crude cluster intervals come from `scbasket.report`, the same code
`scripts/figures.py` draws the two PNGs from, so the page and the figures cannot disagree.

The file has no network dependency: the data is inlined, the charts are drawn by hand in
SVG, and the only remote thing a judge could be missing is the font, which falls back.

Writes {out} (default `reports/nobody_reads_the_bounce.html`).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from _record import freeze_commits

from scbasket import report
from scbasket.conditional import FEATURES, FROZEN_BETA
from scbasket.court import FIBA, HOOP_X
from scbasket.tagging import (
    APPROACH_LEAD_FRAMES,
    FLAT_ZONE_FT,
    MAX_COVERAGE_GAP,
    ZONE_COVERAGE,
    ZONE_INTERCEPT_FT,
    ZONE_SLOPE,
)
from scbasket.validation import CALIBRATION_GAMES, VALIDATION_GAMES

TEMPLATE = Path(__file__).with_name("report_template.html")
PLACEHOLDER = "/*PAYLOAD*/"


def rows(table: pd.DataFrame) -> list[dict]:
    """A DataFrame as a list of plain records, rounded to what a page can honestly show."""
    return json.loads(table.round(6).to_json(orient="records"))


def banded(players: pd.DataFrame, slot: str, labels: tuple[str, ...],
           statistic: report.Statistic, rng: np.random.Generator) -> dict:
    """One chart: the bands, and one row per half and band with its interval and its n."""
    return {"labels": list(labels), "rows": rows(report.banded(players, slot, labels,
                                                               statistic, rng))}


def read(path: Path, **kwargs) -> pd.DataFrame:
    """A reports CSV, or a message naming the script that writes it."""
    if not path.exists():
        raise SystemExit(f"no {path}; run the script that writes it first")
    return pd.read_csv(path, **kwargs)


def zone_points(zone: pd.DataFrame) -> dict:
    """Every located rebound on the court, as parallel arrays to keep the file small.

    `x` and `y` are where the ball was won, in the attacking frame the page draws its court
    in; `shot_dist` is how far its shot was taken from, which is what the zone scales with.
    """
    located = zone.dropna(subset=["reb_x", "shot_dist"])
    return {
        "x": located["reb_x"].round(1).tolist(),
        "y": located["reb_y"].round(1).tolist(),
        "shot_dist": located["shot_dist"].round(1).tolist(),
        "half": located["half"].tolist(),
        "inside": located["in_zone"].astype(int).tolist(),
    }


def court(scenes: Path) -> dict:
    """The clips, with the court they are drawn on.

    The geometry is the package's own `CourtGeometry`, not seven numbers typed into the
    template: `ra_radius_ft` and the two angles beside it were fit by
    `scripts/fit_zone_geometry.py`, so a refit has to reach the page as well as the CSVs.
    """
    if not scenes.exists():
        raise SystemExit(f"no {scenes}; run scripts/court_scenes.py first")
    return {"geometry": asdict(FIBA),
            **json.loads(scenes.read_text(encoding="utf-8"))}


def payload(reports: Path) -> dict:
    """Everything the page shows, gathered from the CSVs and the frozen constants."""
    players = report.load_players(reports / "angle_players.csv")
    rng = np.random.default_rng(report.SEED)
    lift = banded(players, "dist_slot", report.DIST_LABELS, report.lift, rng)
    inside = players[players["rim_dist"] < report.FIXED_BAND_FT]
    curve = banded(inside, "angle_slot", report.ANGLE_LABELS, report.p_win, rng)

    cost = read(reports / "angle_tradeoff.csv")
    ball = read(reports / "rebound_flight_carry.csv", index_col=0)
    flight = read(reports / "rebound_flight_criterion.csv", index_col=0)
    contest = read(reports / "rebound_contest_criterion.csv", index_col=0)
    zone_criterion = read(reports / "rebound_zone_criterion.csv", index_col=0)

    return {
        "built": date.today().isoformat(),
        "halves": list(report.HALVES),
        "games": {"calibration": list(CALIBRATION_GAMES), "held out": list(VALIDATION_GAMES)},
        "lift": lift,
        "curve": curve,
        "pooled": rows(report.pooled(inside, "angle_slot", report.ANGLE_LABELS)),
        "committed_angle": report.COMMITTED_ANGLE_DEG,
        "fixed_band_ft": report.FIXED_BAND_FT,
        "ball": {"carry": ball.to_dict(), "spread": flight.to_dict()},
        # The cost side of the claim, which is a null: see `cost` in the page.
        "cost": rows(cost),
        "zone": {
            "intercept": ZONE_INTERCEPT_FT,
            "slope": ZONE_SLOPE,
            "coverage": ZONE_COVERAGE,
            "flat_ft": FLAT_ZONE_FT,
            "max_gap": MAX_COVERAGE_GAP,
            # Where the court opens: a shot from the top of the key, straight on.
            "example": [HOOP_X + 22.0, 0.0],
            "points": zone_points(read(reports / "rebound_zone.csv")),
            "criterion": zone_criterion.round(4).to_dict("index"),
        },
        "court": court(reports / "court_scenes.json"),
        "contest": {
            "criterion": contest.to_dict(),
            "features": list(FEATURES),
            "beta": list(FROZEN_BETA),
            "lead_frames": APPROACH_LEAD_FRAMES,
        },
        "record": [{"sha": sha, "subject": subject}
                   for sha, subject in freeze_commits()],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--out", type=Path,
                        default=Path("reports/nobody_reads_the_bounce.html"))
    args = parser.parse_args()

    data = payload(args.reports)
    template = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise SystemExit(f"{TEMPLATE} has lost its {PLACEHOLDER} marker")
    # `</` inside a <script> would close it early, whatever the JSON says it means.
    page = template.replace(PLACEHOLDER, json.dumps(data).replace("</", "<\\/"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")

    print(f"wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB, "
          f"{len(data['zone']['points']['x'])} located rebounds, "
          f"{len(data['court']['scenes'])} clips, "
          f"{len(data['record'])} commits of the record)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
