"""Calibrate the control field on the five oldest games and freeze the result (P1.4, D11).

Usage: uv run python scripts/calibrate_control.py [--root DIR] [--cache DIR] [--out DIR]

Grid search over r_near x r_far x t_h of AUC(open vs the other contest levels) +
Spearman(shotQuality) of P_off at the shooter, over the release frames of the CALIBRATION
games only (scbasket.validation.CALIBRATION_GAMES, the five oldest by date: D11). The five
held-out games are never read here; the split is checked against matches.json's dates
before anything runs.

After the freeze, the P1.5 outlook is printed at the frozen cell, on the calibration games
only: the three threshold quantities of the objective's family (AUC, the disk margin over
Voronoi, the plain Spearman) and the fourth pre-registered criterion, the partial Spearman
of shotQuality with each model feature controlling for closestDefDist (and for
closestDefDist + three), with its 2,000-shuffle permutation p-value
(scbasket.validation.partial_spearman_table, on release_features at D4's 1 ft grid). None
of this is the P1.5 result; it says whether P1.5 is worth running at all.

Two grids, both written, following the plan's rule "if the optimum sits on an edge, extend
that dimension and rerun":

1. PLANNED_GRID, the plan's 4 x 4 x 3 = 48 cells -> {out}/calibration_grid.csv.
2. EXTENDED_GRID, run only if the planned optimum sits on an edge that can be extended ->
   {out}/calibration_grid_extended.csv. On the published games the planned optimum sat on
   the LOW edge of both radii (r_near 3 ft, r_far 8 ft), so the extension adds two values
   below each. t_h = 0 is a hard lower bound (the model ignores velocity entirely) and is
   reported as a finding, never extended.

`slope` is not swept and is frozen at 1: P_off = sigmoid(slope * score) is monotone in the
score, so both terms of the objective are exactly invariant to it (D1 amendment, measured
in P1.1). d_far and v_max keep their ControlParams defaults.

{out}/control_params.json freezes the chosen ControlParams with the commit hash of the code
that produced them, the objective and its components on the calibration games, the grid
that chose them, and whether the optimum sits on an edge of it. Committing this file is the
project's pre-registration: it must land BEFORE anything runs on the validation games.

Exit code 1 if the final optimum still sits on an extendable edge.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from scbasket.control import ControlParams
from scbasket.court import make_grid
from scbasket.frames import GameFrames, get_or_build
from scbasket.io import Dataset
from scbasket.validation import (
    CALIBRATION_GAMES,
    PARTIAL_SHUFFLES,
    best_cell,
    calibrate,
    edge_dimensions,
    open_label,
    partial_spearman_table,
    rank_auc,
    release_features,
)
from scbasket.value import league_zone_values, surface_from_zones

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "opendata-basketball"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

# The plan's grid (P1.4 as amended: 48 cells, slope fixed at 1).
PLANNED_GRID = {
    "r_near": [3.0, 4.0, 5.0, 6.0],
    "r_far": [8.0, 10.0, 12.0, 14.0],
    "t_h": [0.0, 0.3, 0.6],
}
# The planned grid extended on the side where its optimum sat: two more values below the
# low edge of each radius. t_h keeps its values (its edge, 0, is a hard bound). Note the
# product now holds cells with r_far < r_near (a radius that shrinks away from the ball,
# against D2's intent); they are swept like any other and are visible in the table.
EXTENDED_GRID = {
    "r_near": [1.0, 2.0, *PLANNED_GRID["r_near"]],
    "r_far": [4.0, 6.0, *PLANNED_GRID["r_far"]],
    "t_h": PLANNED_GRID["t_h"],
}
DIMENSIONS = tuple(PLANNED_GRID)

# P1.5's pre-registered thresholds (D13), printed here only as an outlook on the calibration
# games. They are decided on the held-out games, never here.
P15_AUC = 0.80
P15_MARGIN = 0.03
P15_SPEARMAN = 0.30
P15_PARTIAL_P = 0.01


def git_state() -> tuple[str | None, bool | None]:
    """HEAD's hash and whether anything outside reports/ is uncommitted; (None, None) if no git."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", ".", ":!reports"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return head, bool(status.strip())


def check_split(dataset: Dataset) -> None:
    """D11: the calibration games must be exactly the five oldest by date (matches.json only)."""
    oldest = dataset.game_ids[: len(CALIBRATION_GAMES)]  # game_ids is sorted by date_time
    if set(oldest) != set(CALIBRATION_GAMES):
        raise SystemExit(
            f"D11 violated: the five oldest games are {oldest}, CALIBRATION_GAMES is "
            f"{list(CALIBRATION_GAMES)}"
        )


def extendable_edges(best: pd.Series, param_grid: Mapping[str, Sequence[float]]) -> list[str]:
    """Edge dimensions of `best` that the plan's rule can extend: every one except t_h at 0."""
    return [e for e in edge_dimensions(best, param_grid) if not (e == "t_h" and best["t_h"] == 0)]


def sweep(
    name: str,
    param_grid: Mapping[str, Sequence[float]],
    frames_by_game: Mapping[int, GameFrames],
    shots_by_game: Mapping[int, pd.DataFrame],
    out: Path,
) -> tuple[pd.DataFrame, pd.Series, float]:
    """Run one grid, write {out}/{name}.csv, print its summary; return table, best cell, seconds."""
    n_cells = 1
    for values in param_grid.values():
        n_cells *= len(values)
    t0 = time.perf_counter()
    table = calibrate(frames_by_game, shots_by_game, param_grid)
    seconds = time.perf_counter() - t0
    table.to_csv(out / f"{name}.csv", index=False)
    best = best_cell(table)
    edges = edge_dimensions(best, param_grid)

    print(f"\n=== {name}: {n_cells} cells in {seconds:.1f} s ===")
    print("grid: " + "; ".join(f"{d} {[float(v) for v in param_grid[d]]}" for d in DIMENSIONS))
    print("top 10 cells by objective = AUC(open vs other levels) + Spearman(shotQuality), P_off "
          "at the shooter:")
    columns = [*DIMENSIONS, "auc_open", "spearman_quality", "objective", "p_off_disk_auc"]
    top = table.sort_values("objective", ascending=False).head(10)
    print(top[columns].to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print(f"best cell: r_near {best['r_near']:g} ft, r_far {best['r_far']:g} ft, "
          f"t_h {best['t_h']:g} s (slope fixed at {best['slope']:g}, not calibrated)")
    print(f"  objective {best['objective']:.4f} = AUC {best['auc_open']:.4f} + Spearman "
          f"{best['spearman_quality']:.4f}")
    margin = best["p_off_disk_auc"] - best["voronoi_disk_auc"]
    print(f"  p_off_disk AUC {best['p_off_disk_auc']:.4f} vs voronoi_disk AUC "
          f"{best['voronoi_disk_auc']:.4f} (margin {margin:+.4f})")
    print(f"  reference, nearest-defender distance alone: AUC {best['closest_def_dist_auc']:.4f}, "
          f"Spearman {best['closest_def_dist_spearman']:.4f}")
    if edges:
        note = "" if extendable_edges(best, param_grid) else \
            "; t_h = 0 is a hard bound (velocity ignored), not extendable"
        print(f"  ON THE EDGE of the grid in: {edges}{note}")
    else:
        print("  interior in every dimension")

    objective = table["objective"]
    print(f"surface: objective min {objective.min():.4f}, max {objective.max():.4f}, std "
          f"{objective.std():.4f}; {int((objective >= objective.max() - 0.01).sum())} of "
          f"{n_cells} cells within 0.01 of the best")
    print("mean objective by value of each dimension:")
    for name_ in DIMENSIONS:
        by_value = table.groupby(name_)["objective"].mean()
        cells = "  ".join(f"{value:g}: {mean:.4f}" for value, mean in by_value.items())
        print(f"  {name_:<7} {cells}   (spread {by_value.max() - by_value.min():.4f})")
    ablation = table.loc[table["t_h"] == 0.0, "objective"]
    if not ablation.empty:
        print(f"velocity ablation (t_h = 0): best objective {ablation.max():.4f} against "
              f"{table.loc[table['t_h'] > 0.0, 'objective'].max():.4f} with velocity")
    return table, best, seconds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DATA, help="opendata-basketball clone")
    parser.add_argument("--cache", type=Path, default=INTERIM, help="D12 frame cache directory")
    parser.add_argument("--out", type=Path, default=REPORTS, help="reports directory")
    args = parser.parse_args(argv)

    dataset = Dataset(args.root)
    check_split(dataset)
    args.out.mkdir(parents=True, exist_ok=True)

    frames_by_game = {g: get_or_build(dataset, g, args.cache) for g in CALIBRATION_GAMES}
    shots_by_game = {g: dataset.events(g)["shots"] for g in CALIBRATION_GAMES}
    n_events = sum(len(s) for s in shots_by_game.values())
    print(f"calibration games (D11, the five oldest): {list(CALIBRATION_GAMES)}, "
          f"{n_events} shot events")

    grid_name, grid = "calibration_grid", PLANNED_GRID
    table, best, seconds = sweep(grid_name, grid, frames_by_game, shots_by_game, args.out)
    n = {k: int(table.loc[0, k]) for k in ("n_shots", "n_open", "n_other", "n_quality")}
    print(f"denominators: {n['n_shots']} shots matched to a D12 release frame (of {n_events} "
          f"events), AUC on {n['n_open']} open vs {n['n_other']} other, Spearman on "
          f"{n['n_quality']} with a shotQuality")
    planned_edges = edge_dimensions(best, grid)
    if extendable_edges(best, grid):
        print(f"\nthe planned optimum sits on an extendable edge in "
              f"{extendable_edges(best, grid)}: rerunning on the extended grid (plan rule)")
        grid_name, grid = "calibration_grid_extended", EXTENDED_GRID
        table, best, more = sweep(grid_name, grid, frames_by_game, shots_by_game, args.out)
        seconds += more

    params = ControlParams(**{name: float(best[name]) for name in DIMENSIONS})
    edges = edge_dimensions(best, grid)
    print("\nslope: fixed at 1 and NOT calibrated. P_off = sigmoid(slope * score) is monotone in "
          "the score, so the AUC and the Spearman above are bit-identical at every slope; a "
          "grid over it would be all ties (D1 amendment).")
    print("\nP1.5 outlook at the frozen cell on the CALIBRATION games only (the thresholds are "
          "decided on the held-out games, not here):")
    margin = best["p_off_disk_auc"] - best["voronoi_disk_auc"]
    for label, value, bar in (
        ("AUC(open) of p_off_shooter", best["auc_open"], P15_AUC),
        ("p_off_disk - voronoi_disk AUC margin", margin, P15_MARGIN),
        ("Spearman(shotQuality) of p_off_shooter", best["spearman_quality"], P15_SPEARMAN),
    ):
        print(f"  {label}: {value:.4f} [>= {bar}: {'reached' if value >= bar else 'NOT reached'}]")

    # Fourth criterion: information beyond the nearest-defender distance. Needs epc_share,
    # so release_features at the frozen cell on D4's grid; the point features it returns are
    # the same numbers the sweep graded (checked below, not assumed).
    court = make_grid(1.0)
    surface = surface_from_zones(court, league_zone_values(dataset.aggregates("shots")))
    features = pd.concat(
        [release_features(frames_by_game[g], shots_by_game[g], court, params, surface)
         for g in CALIBRATION_GAMES],
        ignore_index=True,
    )
    t0 = time.perf_counter()
    partial = partial_spearman_table(features)
    partial_s = time.perf_counter() - t0
    print(f"\nP1.5 fourth criterion at the frozen cell, CALIBRATION games only: partial Spearman "
          f"of shotQuality with each feature, controlling for the provider's closestDefDist "
          f"(and for closestDefDist + three), one-sided permutation p-value with "
          f"{PARTIAL_SHUFFLES} shuffles, seed 0 ({partial_s:.1f} s). Bar: rho > 0 with "
          f"p < {P15_PARTIAL_P}. NaN rho = predictor collinear with the controls, undefined.")
    verdicts = [
        "reached" if (r.rho > 0 and r.p_value < P15_PARTIAL_P) else "NOT reached"
        for r in partial.itertuples()
    ]
    print(partial.assign(verdict=verdicts).to_string(
        index=False, float_format=lambda x: f"{x:.4f}", na_rep="NaN"))
    reproduced = features["p_off_shooter"].to_numpy()
    print(f"release_features at the frozen cell has {len(features)} rows; its p_off_shooter "
          f"reproduces the sweep's AUC: "
          f"{rank_auc(reproduced, open_label(features['contestLevel'])) == best['auc_open']}")

    head, dirty = git_state()
    frozen = {
        "params": asdict(params),
        "slope_calibrated": False,
        "slope_note": "fixed at 1: P_off = sigmoid(slope * score) is monotone in the score, so "
                      "every rank metric in F1 is invariant to it (D1 amendment)",
        "objective": float(best["objective"]),
        "auc_open": float(best["auc_open"]),
        "spearman_quality": float(best["spearman_quality"]),
        "p_off_disk_auc": float(best["p_off_disk_auc"]),
        "voronoi_disk_auc": float(best["voronoi_disk_auc"]),
        "closest_def_dist_auc": float(best["closest_def_dist_auc"]),
        "closest_def_dist_spearman": float(best["closest_def_dist_spearman"]),
        "denominators": n,
        "calibration_games": list(CALIBRATION_GAMES),
        "grid_name": grid_name,
        "grid": {name: [float(v) for v in values] for name, values in grid.items()},
        "on_grid_edge": edges,
        "planned_grid": {name: [float(v) for v in vals] for name, vals in PLANNED_GRID.items()},
        "planned_grid_optimum_on_edge": planned_edges,
        "partial_spearman_shot_quality": {
            "scope": "calibration games only, at the frozen cell; P1.5's fourth criterion is "
                     "decided on the held-out games, never here",
            "criterion": f"rho > 0 with one-sided permutation p < {P15_PARTIAL_P}, "
                         f"{PARTIAL_SHUFFLES} shuffles, seed 0",
            "grid_ft": court.cell_ft,
            "rows": [
                {
                    "predictor": r.predictor,
                    "controls": r.controls,
                    "n_shots": int(r.n_shots),
                    "rho": None if pd.isna(r.rho) else float(r.rho),
                    "p_value": None if pd.isna(r.p_value) else float(r.p_value),
                }
                for r in partial.itertuples()
            ],
        },
        "sweep_seconds": round(seconds, 1),
        "code_commit": head,
        "working_tree_dirty": dirty,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (args.out / "control_params.json").write_text(
        json.dumps(frozen, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nfrozen {asdict(params)} from {grid_name} into {args.out / 'control_params.json'} "
          f"(code {head}, dirty={dirty}); sweeps {seconds:.1f} s in total")

    if extendable_edges(best, grid):
        print(f"\nFAIL: the optimum still sits on an extendable edge in "
              f"{extendable_edges(best, grid)}; extend EXTENDED_GRID on that side and rerun.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
