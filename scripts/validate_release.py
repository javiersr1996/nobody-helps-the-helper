"""Validate the frozen control field on the five held-out games (P1.5, D11, D13).

Usage: uv run python scripts/validate_release.py [--root DIR] [--cache DIR] [--out DIR]
                                                  [--params FILE]

Loads the ControlParams that scripts/calibrate_control.py froze in {out}/control_params.json
(committed BEFORE this script first ran: D11) and evaluates them, unchanged, on the release
frames of the five VALIDATION games (scbasket.validation.VALIDATION_GAMES, the five newest by
date; the calibration games are never graded here). Nothing in this script fits, sweeps or
tunes anything: the four pre-registered criteria (D13, scbasket.validation.RELEASE_THRESHOLDS)
are graded exactly as written in tasks/todo.md and each is reported pass or fail. A failed
criterion is a finding, not an error, so the exit code is 0 either way. The script refuses to
run (exit 1) only when the parameters are not actually frozen (the json is missing, was never
committed or differs from its committed version) or the game split does not match the dates.

Writes {out}/validation_release.csv (scbasket.validation.release_metrics: one row per metric
and model feature, with the criterion and its verdict on the five rows that carry one) and
prints the medians by contestLevel, the denominators, and the calibration figures read back
from the frozen json next to the held-out ones. Grid: D4's 1 ft. Only epc_share depends on
the grid; P_off at the shooter, the 3 ft disk and every distance are grid-free.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.control import ControlParams
from scbasket.court import make_grid
from scbasket.frames import get_or_build
from scbasket.io import Dataset
from scbasket.validation import (
    CALIBRATION_GAMES,
    CONTEST_LEVELS,
    PARTIAL_SHUFFLES,
    VALIDATION_GAMES,
    level_medians,
    release_features,
    release_metrics,
)
from scbasket.value import league_zone_values, surface_from_zones

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "opendata-basketball"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"
GRID_FT = 1.0  # D4's default; only epc_share depends on it


def frozen_provenance(path: Path) -> tuple[str | None, str | None, bool | None]:
    """(HEAD, the commit that last touched `path`, whether `path` has uncommitted changes).

    All three are None when git is unavailable (a clean download without history); the
    second is None when the file was never committed.
    """
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        head = run("rev-parse", "HEAD")
        committed = run("log", "-1", "--format=%H", "--", str(path)) or None
        modified = bool(run("status", "--porcelain", "--", str(path)))
    except (OSError, subprocess.CalledProcessError):
        return None, None, None
    return head, committed, modified


def load_frozen(path: Path) -> tuple[dict, ControlParams]:
    """The frozen json and its ControlParams; SystemExit if they are not frozen (D11)."""
    if not path.exists():
        raise SystemExit(f"{path} not found: run scripts/calibrate_control.py and commit it first")
    head, committed, modified = frozen_provenance(path)
    if head is None:
        print(f"WARNING: no git history, cannot check that {path.name} is committed (D11)")
    elif committed is None or modified:
        raise SystemExit(
            f"D11 violated: {path.name} is "
            f"{'not committed' if committed is None else 'modified since its commit'}; "
            "the parameters must be frozen before the validation games are opened"
        )
    frozen = json.loads(path.read_text(encoding="utf-8"))
    if frozen["calibration_games"] != list(CALIBRATION_GAMES):
        raise SystemExit(
            f"{path.name} was calibrated on {frozen['calibration_games']}, not on "
            f"CALIBRATION_GAMES {list(CALIBRATION_GAMES)}"
        )
    print(f"frozen parameters: {frozen['params']} from {path.name} (committed in "
          f"{committed}, code {frozen['code_commit']}, dirty={frozen['working_tree_dirty']}); "
          f"HEAD {head}")
    return frozen, ControlParams(**frozen["params"])


def check_split(dataset: Dataset) -> None:
    """D11: the validation games are the five newest by date and share nothing with calibration."""
    n = len(CALIBRATION_GAMES)
    if dataset.game_ids[:n] != list(CALIBRATION_GAMES):
        raise SystemExit(f"D11 violated: the {n} oldest games are {dataset.game_ids[:n]}")
    if dataset.game_ids[n:] != list(VALIDATION_GAMES):
        raise SystemExit(
            f"D11 violated: the games after the {n} oldest are {dataset.game_ids[n:]}, "
            f"VALIDATION_GAMES is {list(VALIDATION_GAMES)}"
        )


def calibration_reference(frozen: dict) -> dict[tuple[str, str, str], float]:
    """(metric, feature, controls) -> the calibration-game value recorded in the frozen json."""
    reference = {
        ("auc_open", "p_off_shooter", ""): frozen["auc_open"],
        ("auc_open", "p_off_disk", ""): frozen["p_off_disk_auc"],
        ("auc_open", "voronoi_disk", ""): frozen["voronoi_disk_auc"],
        ("auc_open", "closest_def_dist", ""): frozen["closest_def_dist_auc"],
        ("auc_margin_vs_voronoi_disk", "p_off_disk", ""):
            frozen["p_off_disk_auc"] - frozen["voronoi_disk_auc"],
        ("spearman_quality", "p_off_shooter", ""): frozen["spearman_quality"],
        ("spearman_quality", "closest_def_dist", ""): frozen["closest_def_dist_spearman"],
    }
    for row in frozen["partial_spearman_shot_quality"]["rows"]:
        if row["rho"] is not None:
            reference[("partial_spearman_quality", row["predictor"], row["controls"])] = row["rho"]
    return reference


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DATA, help="opendata-basketball clone")
    parser.add_argument("--cache", type=Path, default=INTERIM, help="D12 frame cache directory")
    parser.add_argument("--out", type=Path, default=REPORTS, help="reports directory")
    parser.add_argument("--params", type=Path, default=None,
                        help="frozen parameters (default: {out}/control_params.json)")
    args = parser.parse_args(argv)
    params_path = args.params or args.out / "control_params.json"

    frozen, params = load_frozen(params_path)
    dataset = Dataset(args.root)
    check_split(dataset)
    args.out.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    grid = make_grid(GRID_FT)
    surface = surface_from_zones(grid, league_zone_values(dataset.aggregates("shots")))
    n_events = 0
    features = []
    for game_id in VALIDATION_GAMES:
        shots = dataset.events(game_id)["shots"]
        n_events += len(shots)
        features.append(release_features(
            get_or_build(dataset, game_id, args.cache), shots, grid, params, surface
        ))
    features = pd.concat(features, ignore_index=True)
    features_s = time.perf_counter() - t0
    print(f"\nvalidation games (D11, the five newest): {list(VALIDATION_GAMES)}, {n_events} "
          f"shot events, {len(features)} matched to a D12 release frame; release_features at "
          f"the frozen cell on the {GRID_FT:g} ft grid in {features_s:.1f} s")
    label = features["contestLevel"]
    print(f"denominators: AUC on {int((label == 'open').sum())} open vs "
          f"{int((label.notna() & (label != 'open')).sum())} other levels "
          f"({int(label.isna().sum())} without a contestLevel dropped); Spearman on "
          f"{int(features['shotQuality'].notna().sum())} with a shotQuality; the partial rows "
          f"state their own count (rows with every control present)")
    hoop = features["hoop_dist"]
    print(f"hoop_dist from shots.location: median {hoop.median():.2f} ft, {int(hoop.isna().sum())}"
          f" null (calibration games: median 9.78 ft)")

    t0 = time.perf_counter()
    table = release_metrics(features)
    metrics_s = time.perf_counter() - t0
    out_path = args.out / "validation_release.csv"
    table.to_csv(out_path, index=False)
    print(f"\nwrote {len(table)} rows to {out_path} ({metrics_s:.1f} s, permutation p-values "
          f"with {PARTIAL_SHUFFLES} shuffles, seed 0)")

    print("\nmedians by contestLevel on the held-out games (n_shots = shots at that level):")
    print(level_medians(features).to_string(float_format=lambda x: f"{x:.4f}"))

    reference = calibration_reference(frozen)
    print("\nheld-out against calibration (calibration values read back from the frozen json):")
    compare = table[table["metric"].isin(
        ["auc_open", "auc_margin_vs_voronoi_disk", "spearman_quality", "partial_spearman_quality"]
    )].copy()
    compare["calibration"] = [
        reference.get((m, f, c), np.nan)
        for m, f, c in zip(compare["metric"], compare["feature"], compare["controls"], strict=True)
    ]
    columns = ["metric", "model", "feature", "controls", "n_shots", "value", "p_value",
               "calibration"]
    print(compare[columns].to_string(index=False, float_format=lambda x: f"{x:.4f}",
                                     na_rep=""))

    print("\npre-registered criteria (D13), graded as written and not adjusted:")
    for row in table[table["criterion"] != ""].sort_values("criterion").itertuples():
        p = "" if np.isnan(row.p_value) else f", p {row.p_value:.4f}"
        print(f"  {row.criterion}: {row.value:.4f}{p} on {row.n_shots} shots -> "
              f"{'PASS' if row.passed else 'FAIL'}")
    ceiling = table[(table["metric"] == "auc_open") & (table["feature"] == "closestDefDist")]
    print(f"reference: the provider's closestDefDist alone reaches AUC "
          f"{float(ceiling['value'].iloc[0]):.4f} on the held-out games (calibration: "
          f"{frozen['closest_def_dist_auc']:.4f} recomputed from the cache); the label is "
          f"derived from that distance, so this is the ceiling the 0.80 bar sits against")
    order = " > ".join(CONTEST_LEVELS)
    print(f"criterion 3 reads the medians of p_off_shooter in the order {order}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
