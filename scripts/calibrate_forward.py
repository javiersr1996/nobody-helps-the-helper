"""Re-calibrate the control parameters against the forward label and freeze them (P1.7, D11).

Usage: uv run python scripts/calibrate_forward.py [--root DIR] [--cache DIR] [--out DIR]
                                                  [--cell-ft FT] [--every N] [--seed N]

Touches the FIVE CALIBRATION GAMES ONLY (scbasket.validation.CALIBRATION_GAMES). The five
held-out games are not read here, not even to count rows: P1.8 opens them once, after this
script's output has been committed.

Why a re-calibration at all, when control_params.json already exists: that cell was chosen
by P1.4 against a STATIC contest AUC, and it came out at t_h = 0.0, on the lower edge of
the sweep. t_h is the projection horizon, so at 0.0 the players' velocities do not enter
the model at all. A label about what happens in the next 3 s is exactly where a horizon
should matter, so the sweep is redone against the new objective and t_h is given room
upward. Everything else about D11 holds: the cell is frozen to a json with the commit hash
before any held-out game is read.

The objective is the same quantity F1b's criterion 1 grades, measured here on the
calibration games: the MEAN leave-one-game-out delta AUC of baseline + field over baseline
alone. Per-fold values for every cell are written out, never only the mean.

Writes {out}/control_params_forward.json (the frozen cell plus the full sweep summary) and
{out}/calibration_forward_grid.csv (one row per cell and fold).
"""

from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.control import ControlParams
from scbasket.court import make_grid
from scbasket.forward import (
    HORIZON_FRAMES,
    HORIZON_S,
    SEED,
    delta_auc,
    field_features,
    game_inputs,
)
from scbasket.io import Dataset
from scbasket.validation import CALIBRATION_GAMES
from scbasket.value import league_zone_values, surface_from_zones

# The sweep. r_near and r_far bracket P1.4's frozen (2.0, 8.0); t_h is given room ABOVE
# 0.0, which is where P1.4 pinned it and which is the lower edge of any horizon sweep.
PARAM_GRID = {
    "r_near": (2.0, 3.0, 4.0),
    "r_far": (8.0, 10.0, 12.0),
    "t_h": (0.0, 0.3, 0.6, 1.0),
}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/raw/opendata-basketball"))
    parser.add_argument("--cache", type=Path, default=Path("data/interim"))
    parser.add_argument("--out", type=Path, default=Path("reports"))
    parser.add_argument("--cell-ft", type=float, default=1.0)
    parser.add_argument("--every", type=int, default=5)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    dataset = Dataset(args.root)
    grid = make_grid(cell_ft=args.cell_ft)
    surface = surface_from_zones(grid, league_zone_values(dataset.aggregates("shots")))

    print(f"Calibration games (D11): {list(CALIBRATION_GAMES)}")
    print("The five held-out games are NOT read by this script.\n")

    started = time.perf_counter()
    inputs = [game_inputs(dataset, g, args.cache, args.every) for g in CALIBRATION_GAMES]
    for item in inputs:
        print(
            f"  game {item['game_id']}: {item['n_sampled']:6d} sampled, "
            f"{item['n_backcourt_dropped']:5d} dropped as backcourt, "
            f"{len(item['frames']):6d} kept, base rate {item['label'].mean():.4f} "
            f"(open {item['label_open'].mean():.4f})"
        )

    game = np.concatenate([np.full(len(i["frames"]), i["game_id"]) for i in inputs])
    label = np.concatenate([i["label"] for i in inputs])
    baseline = pd.concat([i["baseline"] for i in inputs], ignore_index=True)
    print(f"\nPooled rows: {len(game)}, base rate {label.mean():.4f}")
    print(f"Sweep: {PARAM_GRID}\n")

    rows, cells = [], list(itertools.product(*PARAM_GRID.values()))
    for n, values in enumerate(cells, start=1):
        cell = dict(zip(PARAM_GRID.keys(), values, strict=True))
        params = ControlParams(**cell)
        field = pd.concat(
            [field_features(i["frames"], grid, params, surface) for i in inputs],
            ignore_index=True,
        )
        table = delta_auc(baseline, field, label, game, seed=args.seed)
        mean_delta = table["delta"].mean()
        positive = int((table["delta"] > 0).sum())
        print(
            f"[{n:2d}/{len(cells)}] {cell}  mean delta {mean_delta:+.4f}  "
            f"positive {positive}/5  folds {[f'{d:+.3f}' for d in table['delta']]}"
        )
        for game_id, row in table.iterrows():
            rows.append({**cell, "game_id": game_id, **row.to_dict()})

    grid_table = pd.DataFrame(rows)
    grid_table.to_csv(args.out / "calibration_forward_grid.csv", index=False)

    by_cell = (
        grid_table.groupby(list(PARAM_GRID))
        .agg(mean_delta=("delta", "mean"), positive_folds=("delta", lambda d: int((d > 0).sum())))
        .reset_index()
        .sort_values("mean_delta", ascending=False)
    )
    best = by_cell.iloc[0]
    frozen = {k: float(best[k]) for k in PARAM_GRID}
    on_edge = [k for k, v in frozen.items() if v in (min(PARAM_GRID[k]), max(PARAM_GRID[k]))]

    print("\nTop 5 cells by mean delta AUC:")
    print(by_cell.head(5).to_string(index=False))
    print(f"\nFROZEN: {frozen}  mean delta {best['mean_delta']:+.4f}, "
          f"positive in {int(best['positive_folds'])}/5 calibration folds")
    if on_edge:
        print(f"WARNING: the optimum sits on the grid edge for {on_edge}")

    payload = {
        "params": {**ControlParams(**frozen).__dict__},
        "objective": "mean leave-one-game-out delta AUC (baseline + field vs baseline)",
        "objective_value": float(best["mean_delta"]),
        "positive_folds": int(best["positive_folds"]),
        "scope": "calibration games only; P1.8 decides on the five held-out games",
        "label": {
            "name": "shot_next_3s",
            "horizon_s": HORIZON_S,
            "horizon_frames": HORIZON_FRAMES,
            "base_rate": float(label.mean()),
            "n_rows": int(len(game)),
        },
        "sample": {
            "every": args.every,
            "cell_ft": args.cell_ft,
            "seed": args.seed,
            "per_game": {
                str(i["game_id"]): {
                    "n_sampled": i["n_sampled"],
                    "n_backcourt_dropped": i["n_backcourt_dropped"],
                    "n_kept": len(i["frames"]),
                    "base_rate": float(i["label"].mean()),
                    "base_rate_open": float(i["label_open"].mean()),
                }
                for i in inputs
            },
        },
        "grid": {k: list(v) for k, v in PARAM_GRID.items()},
        "on_grid_edge": on_edge,
        "calibration_games": list(CALIBRATION_GAMES),
        "previous_params_note": (
            "P1.4's control_params.json froze t_h = 0.0 against a static contest AUC, so "
            "velocity did not enter the model. This cell is chosen against the forward label."
        ),
        "sweep_seconds": round(time.perf_counter() - started, 1),
        "code_commit": _git("rev-parse", "HEAD"),
        "working_tree_dirty": bool(_git("status", "--porcelain")),
    }
    path = args.out / "control_params_forward.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {path} and {args.out / 'calibration_forward_grid.csv'}")
    print("COMMIT control_params_forward.json BEFORE running scripts/validate_forward.py (D11).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
