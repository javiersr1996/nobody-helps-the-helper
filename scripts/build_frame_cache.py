"""Build the per-game frame cache, data/interim/{gid}_frames.npz, for the published games.

Usage: uv run python scripts/build_frame_cache.py [--root DIR] [--out DIR] [--games ID ...]
                                                   [--force]

For every game it streams the tracking once (scbasket.frames.build_game_frames),
writes the .npz, reloads it, and prints the P0.5 acceptance numbers: how many
live frames were read and how many survive each D12 filter, the Pearson
correlation between the estimated speed and the provider's, the ball-handler
and matchup coverage, build time, file size and load time. A one-row-per-game
summary goes to reports/frame_cache_summary.csv.

Hard criteria (exit code 1 if any fails): every row 5 + 5 players, Pearson on
detected positions >= 0.9, build <= 180 s, .npz <= 50 MB, load <= 2 s.
Matchup coverage below 80% is documented, not failed: the fallback is
scbasket.frames.matchup_with_fallback (nearest defender).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.frames import (
    BuildStats,
    GameFrames,
    build_game_frames_with_stats,
    cache_path,
    load_npz,
    save_npz,
)
from scbasket.io import Dataset

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "opendata-basketball"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

MIN_SPEED_PEARSON = 0.9
MAX_BUILD_SECONDS = 180.0
MAX_NPZ_MB = 50.0
MAX_LOAD_SECONDS = 2.0
MIN_MATCHUP_COVERAGE = 0.8


def check_five_v_five(frames: GameFrames) -> bool:
    """Every row carries five distinct attackers and five distinct defenders."""
    ids = np.concatenate([frames.off_ids, frames.def_ids], axis=1)
    if ids.shape[1] != 10 or (ids <= 0).any():
        return False
    return bool((np.sort(ids, axis=1)[:, 1:] != np.sort(ids, axis=1)[:, :-1]).all())


def report_game(stats: BuildStats, five_ok: bool, size_mb: float, load_s: float) -> bool:
    """Print one game's block and return whether the hard criteria pass."""
    s = stats
    live_pct = 100 * s.n_live / s.n_frames if s.n_frames else float("nan")
    kept_pct = 100 * s.n_kept / s.n_live if s.n_live else float("nan")
    print(f"frames in stream: {s.n_frames:,}; live (players on the floor): {s.n_live:,} "
          f"({live_pct:.1f}%)")
    print("D12 filters, applied in order:")
    print(f"  outside every chance:      {s.n_no_chance:>8,}   "
          f"({s.n_no_chance_clock_stopped:,} of them with the game clock stopped)")
    print(f"  chance not usable:         {s.n_unusable_chance:>8,}")
    print(f"  shotClock null:            {s.n_null_shot_clock:>8,}")
    print(f"  not 5 + 5 players:         {s.n_not_five_v_five:>8,}")
    print(f"  possession unresolved:     {s.n_unresolved_possession:>8,}")
    print(f"  kept:                      {s.n_kept:>8,}   ({kept_pct:.1f}% of live, "
          f"{s.n_runs:,} velocity runs)")

    ok = True

    def verdict(passed: bool) -> str:
        nonlocal ok
        ok = ok and passed
        return "OK" if passed else "FAILS"

    print(f"every row has 5 + 5 distinct players: {verdict(five_ok)}")
    pearson = s.speed_pearson_detected
    pearson_ok = bool(np.isfinite(pearson) and pearson >= MIN_SPEED_PEARSON)
    print(f"|v| vs provider speed, Pearson on detected positions: {s.speed_pearson_detected:.4f} "
          f"(n={s.n_detected_positions:,}; all positions {s.speed_pearson_all:.4f}) "
          f"[>= {MIN_SPEED_PEARSON}: {verdict(pearson_ok)}]")
    print(f"ball handler: touches {100 * s.holder_touch_share:.1f}%, nearest attacker "
          f"< 3 ft {100 * s.holder_fallback_share:.1f}%, none {100 * s.holder_none_share:.1f}%")
    coverage_note = (
        "OK"
        if s.matchup_cell_coverage >= MIN_MATCHUP_COVERAGE
        else "below 80%: documented, fallback = nearest defender (matchup_with_fallback)"
    )
    print(f"matchup coverage: cells {100 * s.matchup_cell_coverage:.1f}%, rows with all five "
          f"assigned {100 * s.matchup_frame_coverage:.1f}% [{coverage_note}]")
    print(f"build {s.build_seconds:.1f} s [<= {MAX_BUILD_SECONDS:.0f}: "
          f"{verdict(s.build_seconds <= MAX_BUILD_SECONDS)}]; "
          f"npz {size_mb:.1f} MB [<= {MAX_NPZ_MB:.0f}: {verdict(size_mb <= MAX_NPZ_MB)}]; "
          f"load {load_s:.2f} s [<= {MAX_LOAD_SECONDS:.0f}: {verdict(load_s <= MAX_LOAD_SECONDS)}]")
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DATA, help="opendata-basketball clone")
    parser.add_argument("--out", type=Path, default=INTERIM, help="cache directory")
    parser.add_argument("--games", type=int, nargs="*", help="game ids (default: all)")
    parser.add_argument("--force", action="store_true", help="rebuild existing caches")
    args = parser.parse_args(argv)

    dataset = Dataset(args.root)
    game_ids = args.games or dataset.game_ids
    args.out.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    all_ok = True
    for i, game_id in enumerate(game_ids, start=1):
        path = cache_path(args.out, game_id)
        print(f"\n=== game {game_id} ({i}/{len(game_ids)}) ===")
        if path.exists() and not args.force:
            print(f"{path.name} exists, skipping (use --force to rebuild)")
            continue
        frames, stats = build_game_frames_with_stats(dataset, game_id)
        save_npz(frames, path)
        size_mb = path.stat().st_size / 1e6
        t0 = time.perf_counter()
        reloaded = load_npz(path)
        load_s = time.perf_counter() - t0
        five_ok = check_five_v_five(reloaded) and len(reloaded) == len(frames)
        ok = report_game(stats, five_ok, size_mb, load_s)
        all_ok = all_ok and ok
        rows.append({**stats.as_dict(), "npz_mb": size_mb, "load_seconds": load_s, "ok": ok})

    if rows:
        REPORTS.mkdir(exist_ok=True)
        summary = pd.DataFrame(rows)
        summary.to_csv(REPORTS / "frame_cache_summary.csv", index=False)
        columns = [
            "game_id", "n_live", "n_kept", "speed_pearson_detected",
            "matchup_cell_coverage", "build_seconds", "npz_mb", "load_seconds", "ok",
        ]
        print("\n=== summary ===")
        print(summary[columns].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
        print(f"\nWrote {len(rows)} rows to reports/frame_cache_summary.csv")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
