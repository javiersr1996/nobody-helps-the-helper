"""How legible the ball is: its entry angle at the rim, frozen and graded (P7.7).

Usage: uv run python scripts/rebound_flight.py [--root DIR] [--cache DIR] [--out DIR] [--fit]

Findings 4 and 5 of the record ("the ball does not help further" and the side bias) had NO
code behind them: commit 580f6b7 added fifty lines of `tasks/todo.md` and not one line of
source, and the word "descent" never appeared in `src/`. So nothing in this repository
reproduced the two numbers the README opens with, which is the same hole P7.2 had to fill for
findings 1 and 3. This script is that code, and it does not agree with the record.

The quantity is the ENTRY ANGLE: how steeply the ball is falling when it first comes back
down through rim height, measured on the incoming flight before it touches anything
(`scbasket.tagging.ball_entry_table`). The record measured something else, under a definition
that lived only in a scratchpad and is gone, and reported a median of 34.9 degrees against
this one's 43.4. A level like that is a property of the definition: over the same rebounds
the median moves from 47.3 to 38.7 degrees with the fitting window alone. The ORDERING
barely moves (Spearman 0.96 between a 3-frame and an 8-frame window), so every claim here is
built on the ordering.

**Measured on CALIBRATION before the criterion below was written** (lesson 3). Of 409
rebounds, 300 have an entry angle and 256 of those have their own location and their shot's,
which is the sample every number below is on:
  - Spearman(shot distance, entry angle) = +0.000. The angle is not the shot relabelled: it
    is genuinely new information, which is what the record claimed too.
  - Spearman(entry angle, landing radius) = -0.330, and negative in FIVE of five calibration
    games individually (-0.187, -0.592, -0.331, -0.216, -0.279). A flatter ball carries
    further. The record reported +0.018 here and called the quantity useless.
  - Residual sd of the landing radius under the frozen coefficients: 4.725 ft knowing
    nothing, 4.604 knowing the shot's distance, 4.276 knowing the entry angle too.

So the ball is MORE legible than the record says, and the honest version of "nobody reads the
bounce" is quantitative: with the shot AND the ball's own trajectory, measured to a precision
no player has in the half second they get, the landing point still moves over four feet.

**CRITERION**, frozen with the coefficients before any held-out game was read (D11), relative
so there is no number left to move afterwards (D13). Coefficients fitted on calibration and
NOT refitted. On the five held-out games:
  1. the frozen model that reads the entry angle leaves a smaller residual sd of the landing
     radius than the frozen model that reads only the shot's distance;
  2. Spearman(entry angle, landing radius) is negative in at least four of the five games
     taken separately. Lesson 1 is built INTO the bar rather than applied to it afterwards,
     because that is the lesson P7.3's top-1 condition bought.

The side bias (finding 4) rides along as a DESCRIPTIVE table with no criterion attached: it
is a share, it was always reported as a share, and `side_bias_table` is what makes it
reproducible.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.frames import get_or_build
from scbasket.io import Dataset
from scbasket.tagging import ball_entry_table, rebound_zone_table, side_bias_table
from scbasket.validation import CALIBRATION_GAMES, VALIDATION_GAMES, spearman

#: Least squares on the 256 usable CALIBRATION rebounds, frozen 2026-09-19 before any
#: held-out game was read. `--fit` re-derives both and prints them next to these.
#: landing radius ~ 1 + shot distance
FROZEN_BETA_SHOT = (4.3970, 0.1254)
#: landing radius ~ 1 + shot distance + entry angle
FROZEN_BETA_SHOT_ENTRY = (8.5619, 0.1275, -0.0941)

#: What the criterion is graded on.
CRITERION_COLUMNS = ("n", "sd_none", "sd_shot", "sd_shot_entry", "rho_angle_radius",
                     "games_negative")


def build(dataset: Dataset, game_id: int, cache_dir: Path) -> pd.DataFrame:
    """One row per rebound of this game: the ball's entry, where it landed, and which side."""
    events = dataset.events(game_id)
    shots, rebounds = events["shots"], events["rebounds"]
    frames = get_or_build(dataset, game_id, cache_dir)

    entry = ball_entry_table(frames, shots, rebounds)
    zone = rebound_zone_table(shots, rebounds)
    side = side_bias_table(shots, rebounds)
    table = entry.merge(zone.drop(columns=["shot_id"]), on="rebound_id").merge(
        side.drop(columns=["shot_id", "shot_dist", "three"]), on="rebound_id")
    table["region"] = table["shot_id"].map(shots.set_index("id")["region"])
    half = "calibration" if game_id in CALIBRATION_GAMES else "held out"
    return table.assign(game=game_id, half=half)


def design(table: pd.DataFrame, with_entry: bool) -> np.ndarray:
    """The regression design: an intercept, the shot's distance, optionally the entry angle."""
    cols = [np.ones(len(table)), table["shot_dist"].to_numpy()]
    if with_entry:
        cols.append(table["entry_angle"].to_numpy())
    return np.column_stack(cols)


def fit(table: pd.DataFrame, with_entry: bool) -> np.ndarray:
    """Least squares of the landing radius on that design."""
    beta, *_ = np.linalg.lstsq(design(table, with_entry), table["reb_dist"].to_numpy(),
                               rcond=None)
    return beta


def residual_sd(table: pd.DataFrame, beta, with_entry: bool) -> float:
    """sd of the landing radius left by a FROZEN beta, with no refitting on this half."""
    resid = table["reb_dist"].to_numpy() - design(table, with_entry) @ np.asarray(beta)
    return float(np.std(resid, ddof=1))


def measure(table: pd.DataFrame) -> dict:
    """The five numbers the criterion reads, on one half."""
    by_game = {g: spearman(p["entry_angle"].to_numpy(), p["reb_dist"].to_numpy())
               for g, p in table.groupby("game", observed=True)}
    return {
        "n": len(table),
        "sd_none": float(np.std(table["reb_dist"].to_numpy(), ddof=1)),
        "sd_shot": residual_sd(table, FROZEN_BETA_SHOT, False),
        "sd_shot_entry": residual_sd(table, FROZEN_BETA_SHOT_ENTRY, True),
        "rho_angle_radius": spearman(table["entry_angle"].to_numpy(),
                                     table["reb_dist"].to_numpy()),
        "games_negative": sum(1 for v in by_game.values() if v < 0),
        "_by_game": by_game,
    }


def side_shares(table: pd.DataFrame) -> pd.DataFrame:
    """Share landing opposite the shooter's side, by shot-distance band and half.

    The last row is the CORNER THREE, which is the only row that speaks to Goldsberry: his
    56% weak side is about missed corner threes, not about threes in general, and comparing
    our wider band to his number would be answering a question he did not ask.
    """
    bands = pd.cut(table["shot_dist"], [0, 16, 22.15, 200], right=False,
                   labels=["inside 16 ft", "16-22 ft", "threes"]).astype(object)
    corner = table["region"].astype(str).str.contains("corner three", case=False, na=False)
    bands[corner.to_numpy()] = "... of which corner threes"
    return (table.assign(band=bands).dropna(subset=["opposite"])
            .pivot_table(index="band", columns="half", values="opposite",
                         aggfunc=["mean", "count"], observed=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/raw/opendata-basketball"))
    parser.add_argument("--cache", type=Path, default=Path("data/interim"))
    parser.add_argument("--out", type=Path, default=Path("reports"))
    parser.add_argument("--fit", action="store_true",
                        help="re-derive the frozen coefficients from CALIBRATION only")
    args = parser.parse_args()

    if not args.root.exists():
        print(f"no dataset at {args.root}; run scripts/fetch_data.py", file=sys.stderr)
        return 1

    dataset = Dataset(args.root)
    games = list(CALIBRATION_GAMES) if args.fit else list(CALIBRATION_GAMES) + list(
        VALIDATION_GAMES)
    table = pd.concat([build(dataset, g, args.cache) for g in games], ignore_index=True)

    print(f"rebounds {len(table)}; with an entry angle {table['entry_angle'].notna().sum()}")
    print("why the rest have none:")
    print(table.loc[table["entry_angle"].isna(), "reason"].value_counts().to_string())

    usable = table.dropna(subset=["entry_angle", "reb_dist", "shot_dist"]).copy()
    print(f"\nwith the ball, their own location and their shot's: {len(usable)}")
    print(usable.groupby("half", observed=True)["entry_angle"].describe()[
        ["count", "25%", "50%", "75%"]].round(1).to_string())

    calibration = usable[usable["half"] == "calibration"]
    if args.fit:
        print("\nRe-derived on calibration, against the frozen pair:")
        print(f"  shot only  {np.round(fit(calibration, False), 4)}  frozen {FROZEN_BETA_SHOT}")
        print(f"  plus entry {np.round(fit(calibration, True), 4)}  "
              f"frozen {FROZEN_BETA_SHOT_ENTRY}")

    print("\n" + "=" * 78)
    print("Is the entry angle the shot relabelled? (it is not: that is what makes it news)")
    print("=" * 78)
    for half, part in usable.groupby("half", observed=True):
        print(f"  Spearman(shot distance, entry angle), {half}: "
              f"{spearman(part['shot_dist'].to_numpy(), part['entry_angle'].to_numpy()):+.3f}")

    print("\n" + "=" * 78)
    print("How much of the landing radius anything explains, frozen betas, never refitted")
    print("=" * 78)
    stats = {half: measure(part) for half, part in usable.groupby("half", observed=True)}
    frame = pd.DataFrame({h: {k: v for k, v in s.items() if not k.startswith("_")}
                          for h, s in stats.items()}).loc[list(CRITERION_COLUMNS)]
    print(frame.round(4).to_string())
    for half, s in stats.items():
        print(f"  {half}, Spearman(entry angle, landing radius) per game: " +
              ", ".join(f"{g}: {v:+.3f}" for g, v in s["_by_game"].items()))

    print("\n" + "=" * 78)
    print("Which side it lands on, the shooter's or the other (finding 4, rebuilt)")
    print("=" * 78)
    print(side_shares(table).round(3).to_string())

    args.out.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.out / "rebound_flight.csv", index=False)
    frame.to_csv(args.out / "rebound_flight_criterion.csv")

    if not args.fit:
        held = stats.get("held out")
        print("\nThe frozen criterion, on the HELD-OUT games:")
        one = held["sd_shot_entry"] < held["sd_shot"]
        two = held["games_negative"] >= 4
        print(f"  [{'PASS' if one else 'FAIL'}] 1. the entry angle leaves a smaller residual "
              f"sd: {held['sd_shot_entry']:.3f} against {held['sd_shot']:.3f}")
        print(f"  [{'PASS' if two else 'FAIL'}] 2. negative in at least four of five games: "
              f"{held['games_negative']} of 5")
        print(f"\nVerdict: {'PASS' if one and two else 'FAIL'}. Reported as it fell (D13).")

    print(f"\nwrote {args.out / 'rebound_flight.csv'} and "
          f"{args.out / 'rebound_flight_criterion.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
