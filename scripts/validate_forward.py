"""Grade the frozen forward-label model on the five held-out games (P1.8, D11, D13).

Usage: uv run python scripts/validate_forward.py [--root DIR] [--cache DIR] [--out DIR]
                                                 [--params FILE] [--cell-ft FT] [--every N]

Reads the ControlParams that scripts/calibrate_forward.py froze in
{out}/control_params_forward.json (committed BEFORE this script first ran: D11) and
evaluates them, unchanged, on the five VALIDATION games. Nothing here fits, sweeps or
tunes: the three pre-registered criteria of F1b are graded exactly as tasks/todo.md
writes them, and each is reported pass or fail. A failed criterion is a FINDING, not an
error, so the exit code is 0 either way. The script refuses to run (exit 1) only when the
parameters are not actually frozen.

The three criteria (F1b, D13, amended by the user on 2026-09-17 BEFORE any held-out
game was read; tasks/todo.md carries the full record of why):
  1. Mean leave-one-game-out delta AUC >= +0.005 AND delta > 0 in 5 of 5 folds.
  2. AUC of `area_valuable` ALONE >= 0.60 in every one of the 5 folds.
  3. The delta is not the clock: FAIL if dropping `shot_clock` and `secs_into_chance`
     from the baseline is what makes the delta reach the bar.

Every criterion prints all five folds. No pooled figure is quoted (lesson 1).

Writes {out}/validation_forward.csv (one row per game and model) and
{out}/validation_forward_criteria.csv (one row per criterion, with its verdict).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.control import ControlParams
from scbasket.court import make_grid
from scbasket.forward import (
    CLOCK_FEATURES,
    SEED,
    delta_auc,
    field_features,
    fold_auc,
    game_inputs,
    logo_scores,
)
from scbasket.io import Dataset
from scbasket.validation import VALIDATION_GAMES
from scbasket.value import league_zone_values, surface_from_zones

MEAN_DELTA_BAR = 0.005
MIN_POSITIVE_FOLDS = 5
SOLO_AUC_BAR = 0.60
SOLO_FEATURE = "area_valuable"


def _frozen_params(path: Path) -> tuple[ControlParams, dict]:
    """The frozen cell, refusing to proceed unless the json is committed and unmodified (D11)."""
    if not path.exists():
        raise SystemExit(f"{path} does not exist: run scripts/calibrate_forward.py first (P1.7).")
    payload = json.loads(path.read_text(encoding="utf-8"))

    committed = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(path)], capture_output=True, text=True
    )
    if committed.returncode != 0:
        raise SystemExit(f"{path} is not committed. D11: freeze it before opening held-out data.")
    dirty = subprocess.run(
        ["git", "diff", "--quiet", "--", str(path)], capture_output=True, text=True
    )
    if dirty.returncode != 0:
        raise SystemExit(f"{path} differs from its committed version. D11 forbids grading on it.")
    return ControlParams(**payload["params"]), payload


def _criterion(name: str, detail: str, value: float, bar: str, passed: bool) -> dict:
    return {"criterion": name, "detail": detail, "value": value, "bar": bar,
            "verdict": "PASS" if passed else "FAIL"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/raw/opendata-basketball"))
    parser.add_argument("--cache", type=Path, default=Path("data/interim"))
    parser.add_argument("--out", type=Path, default=Path("reports"))
    parser.add_argument("--params", type=Path, default=None)
    parser.add_argument("--cell-ft", type=float, default=1.0)
    parser.add_argument("--every", type=int, default=5)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    params, frozen = _frozen_params(args.params or args.out / "control_params_forward.json")
    print(f"Frozen params (P1.7, commit {frozen['code_commit'][:8]}): {params}")
    print(f"Calibration objective was {frozen['objective_value']:+.4f} "
          f"on {frozen['positive_folds']}/5 calibration folds.")
    print(f"Held-out games (D11, opened once): {list(VALIDATION_GAMES)}\n")

    dataset = Dataset(args.root)
    grid = make_grid(cell_ft=args.cell_ft)
    surface = surface_from_zones(grid, league_zone_values(dataset.aggregates("shots")))

    inputs = [game_inputs(dataset, g, args.cache, args.every) for g in VALIDATION_GAMES]
    for item in inputs:
        print(
            f"  game {item['game_id']}: {item['n_sampled']:6d} sampled, "
            f"{item['n_backcourt_dropped']:5d} dropped as backcourt, "
            f"{len(item['frames']):6d} kept, base rate {item['label'].mean():.4f} "
            f"(open {item['label_open'].mean():.4f})"
        )

    game = np.concatenate([np.full(len(i["frames"]), i["game_id"]) for i in inputs])
    label = np.concatenate([i["label"] for i in inputs])
    label_open = np.concatenate([i["label_open"] for i in inputs])
    baseline = pd.concat([i["baseline"] for i in inputs], ignore_index=True)
    field = pd.concat(
        [field_features(i["frames"], grid, params, surface) for i in inputs], ignore_index=True
    )

    # -------------------------------------------------------------------- criterion 1
    table = delta_auc(baseline, field, label, game, seed=args.seed)
    mean_delta, positive = table["delta"].mean(), int((table["delta"] > 0).sum())
    print("\nCriterion 1, delta AUC per held-out game (the graded baseline HAS the clock):")
    print(table.round(4).to_string())
    print(f"  mean {mean_delta:+.4f}, positive in {positive}/5 folds")
    passed_1 = mean_delta >= MEAN_DELTA_BAR and positive >= MIN_POSITIVE_FOLDS

    # -------------------------------------------------------------------- criterion 2
    solo = fold_auc(logo_scores(field[[SOLO_FEATURE]], label, game, seed=args.seed), label, game)
    worst = solo.min()
    print(f"\nCriterion 2, AUC of {SOLO_FEATURE} alone, per fold:")
    print(solo.round(4).to_string())
    passed_2 = bool((solo >= SOLO_AUC_BAR).all())

    # -------------------------------------------------------------------- criterion 3
    no_clock = baseline.drop(columns=list(CLOCK_FEATURES))
    table_no_clock = delta_auc(no_clock, field, label, game, seed=args.seed)
    mean_no_clock = table_no_clock["delta"].mean()
    print("\nCriterion 3, the same delta against a baseline with NO clock features:")
    print(table_no_clock.round(4).to_string())
    print(f"  mean {mean_no_clock:+.4f} without the clock, {mean_delta:+.4f} with it")
    clock_explains_it = mean_no_clock >= MEAN_DELTA_BAR and mean_delta < MEAN_DELTA_BAR
    passed_3 = not clock_explains_it

    # ------------------------------------------------------------- secondary, reported
    open_table = delta_auc(baseline, field, label_open, game, seed=args.seed)
    print("\nSecondary label `open_shot_next_3s`, REPORTED not graded "
          "(partially circular: `open` derives from closestDefDist, which the baseline carries):")
    print(open_table.round(4).to_string())
    print(f"  mean {open_table['delta'].mean():+.4f}, "
          f"positive in {int((open_table['delta'] > 0).sum())}/5 folds")

    criteria = pd.DataFrame([
        _criterion("1. mean delta AUC", f"positive in {positive}/5 folds", mean_delta,
                   f">= {MEAN_DELTA_BAR:+.3f} and >= {MIN_POSITIVE_FOLDS}/5 folds", passed_1),
        _criterion("2. field alone", f"worst fold of {SOLO_FEATURE}", worst,
                   f">= {SOLO_AUC_BAR:.2f} in every fold", passed_2),
        _criterion("3. not the clock", f"mean delta without the clock {mean_no_clock:+.4f}",
                   mean_delta, "the delta must not appear only once the clock is removed",
                   passed_3),
    ])
    print("\n" + "=" * 78)
    print(criteria.round(4).to_string(index=False))
    print("=" * 78)
    n_failed = int((criteria["verdict"] == "FAIL").sum())
    print(f"\n{3 - n_failed}/3 pre-registered criteria PASS.")
    if n_failed:
        print("D13: a failed threshold is reported as it fell and work STOPS to replan. "
              "Nothing here was adjusted to the result.")

    rows = table.assign(model="baseline+field", label="shot_next_3s")
    rows = pd.concat([
        rows,
        table_no_clock.assign(model="baseline_no_clock+field", label="shot_next_3s"),
        open_table.assign(model="baseline+field", label="open_shot_next_3s"),
        solo.to_frame("auc_with_field").assign(
            auc_baseline=np.nan, delta=np.nan, model=f"{SOLO_FEATURE}_alone",
            label="shot_next_3s"),
    ])
    rows.index.name = "game_id"
    rows.to_csv(args.out / "validation_forward.csv")
    criteria.to_csv(args.out / "validation_forward_criteria.csv", index=False)
    print(f"\nWrote {args.out / 'validation_forward.csv'} and "
          f"{args.out / 'validation_forward_criteria.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
