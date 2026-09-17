"""Who wins the board among the ten present: the conditional model, graded (P7.3).

Usage: uv run python scripts/rebound_contest.py [--root DIR] [--cache DIR] [--out DIR] [--fit]

The earlier F6 work gave each player a probability of winning the rebound independently of the
other nine, and those numbers do not sum to one. Exactly one of ten wins, so the model is a
conditional logit over the choice set of the ten on court, scored half a second before the
ball is won. `scbasket.conditional` holds it; this script fits it, freezes it and grades it.

The criterion was frozen with the coefficients, before any held-out game was read (D11), and
it is RELATIVE, so there is no number to move afterwards (D13). With the coefficients fitted
on calibration and not refitted, on the held-out games the full model must:
  1. put more log probability on the player who actually won than the distance-only model
     does, both frozen, and
  2. rank the actual winner first more often than the rule "whoever is nearest the rim wins".
Distance is the baseline because every rebound is won near the rim: a model that only knows
that already gets a long way, and the question is whether heading and speed add anything on
top of it. This is the same shape as F5's depth controls, for the same reason.

Effect available on calibration, measured before the bar was written (lesson 4): log
likelihood per rebound -1.9788 for distance only against -1.8583 for the full model, and
top-1 0.228 against 0.306, with the nearest-to-the-rim rule at 0.235.

Writes {out}/rebound_contest.csv (one row per graded rebound) and
{out}/rebound_contest_criterion.csv.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.conditional import (
    FEATURES,
    FROZEN_BETA,
    FROZEN_BETA_DISTANCE_ONLY,
    FROZEN_BETA_RIM_DIST,
    choice_probabilities,
    fit_conditional_logit,
    log_likelihood,
    rebound_choice_set,
    top1_accuracy,
)
from scbasket.frames import get_or_build
from scbasket.io import Dataset
from scbasket.validation import CALIBRATION_GAMES, VALIDATION_GAMES

UNIFORM_LL = float(np.log(0.1))


def build(dataset: Dataset, game_id: int, cache_dir: Path, *, rim_distance: bool = False):
    """The choice sets of one game, plus the per-rebound rows including the dropped ones."""
    frames = get_or_build(dataset, game_id, cache_dir)
    events = dataset.events(game_id)
    X, y, rows = rebound_choice_set(frames, events["rebounds"], events["shots"],
                                    rim_distance_feature=rim_distance)
    half = "calibration" if game_id in CALIBRATION_GAMES else "held out"
    return X, y, rows.assign(game=game_id, half=half)


def gather(dataset: Dataset, games, cache_dir: Path, *, rim_distance: bool = False):
    parts = [build(dataset, g, cache_dir, rim_distance=rim_distance) for g in games]
    X = np.concatenate([p[0] for p in parts]) if parts else np.zeros((0, 10, len(FEATURES)))
    y = np.concatenate([p[1] for p in parts]) if parts else np.zeros(0, dtype=np.int64)
    return X, y, pd.concat([p[2] for p in parts], ignore_index=True)


def nearest_rim_top1(X: np.ndarray, y: np.ndarray) -> float:
    """The rule the model has to beat: whoever is closest to the rim wins the board.

    Column 0 is the distance scaled by the zone, and the zone is one number per rebound, so
    ranking on it is ranking on the raw distance. The rule is the same either way.
    """
    return float((X[:, :, 0].argmin(axis=1) == y).mean())


def show(label: str, beta) -> str:
    """One line of coefficients, named, for the --fit comparison against the frozen pair."""
    return f"  {label} " + ", ".join(f"{n}={b:+.3f}"
                                     for n, b in zip(FEATURES, beta, strict=True))


def score(X: np.ndarray, y: np.ndarray) -> pd.Series:
    """Every model on one half, in log probability per rebound and in top-1."""
    return pd.Series({
        "n": len(y),
        "ll_uniform": UNIFORM_LL,
        "ll_distance_only": log_likelihood(X, y, FROZEN_BETA_DISTANCE_ONLY),
        "ll_full": log_likelihood(X, y, FROZEN_BETA),
        "top1_nearest_rim": nearest_rim_top1(X, y),
        "top1_distance_only": top1_accuracy(X, y, FROZEN_BETA_DISTANCE_ONLY),
        "top1_full": top1_accuracy(X, y, FROZEN_BETA),
    })


def per_rebound(X: np.ndarray, y: np.ndarray, rows: pd.DataFrame) -> pd.DataFrame:
    """One row per graded rebound: what the frozen model said about the player who won."""
    kept = rows[rows["drop_reason"].isna()].reset_index(drop=True)
    p = choice_probabilities(X, FROZEN_BETA)
    p_winner = p[np.arange(len(y)), y]
    rank = (p > p_winner[:, None]).sum(axis=1) + 1
    return kept.assign(
        p_winner=p_winner,
        rank_winner=rank,
        p_best=p.max(axis=1),
        winner_offense=y < 5,
        zone_ratio_winner=X[np.arange(len(y)), y, 0],
        rimward_winner=X[np.arange(len(y)), y, 1],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/raw/opendata-basketball"))
    parser.add_argument("--cache", type=Path, default=Path("data/interim"))
    parser.add_argument("--out", type=Path, default=Path("reports"))
    parser.add_argument("--fit", action="store_true",
                        help="re-derive the coefficients on the calibration games and exit")
    args = parser.parse_args()

    dataset = Dataset(args.root)
    games = list(CALIBRATION_GAMES) if args.fit else list(CALIBRATION_GAMES) + list(
        VALIDATION_GAMES)
    X, y, rows = gather(dataset, games, args.cache)

    print(f"rebounds {len(rows)}, graded {len(y)}. Dropped, attributed:")
    print(rows["drop_reason"].value_counts(dropna=False).to_string())

    if args.fit:
        refit = fit_conditional_logit(X, y)
        print(f"\nfitted on {len(y)} calibration rebounds, in {FEATURES} order:")
        print(show("refit ", refit))
        print(show("frozen", FROZEN_BETA))
        if np.abs(refit - np.array(FROZEN_BETA)).max() > 0.001:
            print("  MISMATCH: the frozen coefficients no longer reproduce. Report it, do "
                  "not quietly refit (D13).")

        X_rim, y_rim, _ = gather(dataset, games, args.cache, rim_distance=True)
        refit_rim = fit_conditional_logit(X_rim, y_rim)
        print("\nthe same with the raw rim distance in place of the shot-scaled ratio:")
        print(show("refit ", refit_rim))
        print(show("frozen", FROZEN_BETA_RIM_DIST))
        print(f"  log likelihood per rebound: shot-scaled "
              f"{log_likelihood(X, y, refit):.4f}, raw distance "
              f"{log_likelihood(X_rim, y_rim, refit_rim):.4f}")

        baseline = fit_conditional_logit(X[:, :, [0, 4]], y)
        print(f"\ndistance only (zone_ratio, offense): {baseline[0]:+.3f}, {baseline[1]:+.3f}; "
              f"frozen {FROZEN_BETA_DISTANCE_ONLY[0]:+.3f}, "
              f"{FROZEN_BETA_DISTANCE_ONLY[4]:+.3f}")
        return 0

    # `graded` is the kept rows in the order X and y were built, so a boolean mask over it
    # indexes straight into them.
    graded = per_rebound(X, y, rows)
    halves = {half: score(X[(graded["half"] == half).to_numpy()],
                          y[(graded["half"] == half).to_numpy()])
              for half in ("calibration", "held out")}
    table = pd.DataFrame(halves)
    print("\n" + "=" * 78)
    print("The conditional model, the two halves apart. Log probability per rebound, and the")
    print("share of rebounds whose actual winner the model ranks first among the ten.")
    print("=" * 78)
    print(table.round(4).to_string())

    held = halves["held out"]
    checks = {
        "1. beats distance alone in log probability":
            held["ll_full"] > held["ll_distance_only"],
        "2. ranks the winner first more often than the nearest-to-the-rim rule":
            held["top1_full"] > held["top1_nearest_rim"],
    }
    print("\nThe frozen criterion, on the HELD-OUT games:")
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    print(f"\nVerdict: {'PASS' if all(checks.values()) else 'FAIL'}. Reported as it fell (D13).")

    print("\nWhere the model puts the winner, held out (rank among the ten):")
    held_rows = graded[graded["half"] == "held out"]
    print(held_rows["rank_winner"].value_counts().sort_index().head(10).to_string())

    args.out.mkdir(parents=True, exist_ok=True)
    graded.to_csv(args.out / "rebound_contest.csv", index=False)
    table.to_csv(args.out / "rebound_contest_criterion.csv")
    print(f"\nwrote {args.out / 'rebound_contest.csv'} and "
          f"{args.out / 'rebound_contest_criterion.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
