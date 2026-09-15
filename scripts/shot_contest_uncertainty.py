"""How much of a shot's contest level is signal and how much is tracking error.

SkillCorner publishes contestLevel, contested, and shotQuality relying on
closestDefDist: the distance between the shooter and the closest defender at
the moment of release. That distance is computed from two positions that the
provider itself annotates with its expected error (predError, in feet).

This script measures four things per shot:

1. Validation: the distance recomputed from tracking against the published one
   (matched directly against the raw tracking stream, independently of the
   scbasket.frames D12 cache -- 1,445 of 1,459 shot events; an earlier count of
   1,414 for this same raw-stream match does not reproduce and must not be
   cited -- confirmed under three independent matching criteria, see
   tasks/todo.md).
2. The OLD heuristic ambiguity bound (kept only for comparison, no longer the
   deliverable -- see point 3): whether that distance falls below its own
   combined measurement error, and whether the identity of the closest
   defender is ambiguous (the second-closest defender's distance falls within
   the margin of error of the first).
3. THE DELIVERABLE OF P1.2 (D8): Monte Carlo uncertainty of the control
   field's P_off at the shooter's own tracked position --
   scbasket.control.control_at_points_with_uncertainty, K = 20 samples, each
   player perturbed by its own scbasket.quality.sigma_from_pred_error(predError).
   This replaces the heuristic of point 2 with the model's own propagated
   uncertainty: p_off_mean and p_off_std per shot, and -- for 'plus' and
   'blocked', the two levels the old heuristic found noisiest -- the fraction
   of shots whose p_off_std exceeds the distance to EVERY adjacent
   contestLevel's median (plus vs average, plus vs blocked, blocked vs plus;
   'average' is by far the more populous boundary for 'plus', so it is not
   skipped in favour of the boundary the old heuristic happened to frame).
   Matched against the D12-filtered frame cache (control_at_points needs
   oriented positions, velocity and shot clock, none of which D12-dropped
   frames carry), which is a DIFFERENT, smaller denominator than points 1/2's
   raw-stream match: 1,360 of 1,459 shot events (see
   validation.release_features's docstring for the 99-shot breakdown).
4. By-contestLevel summary of both the old heuristic and the new Monte Carlo
   numbers, printed side by side so the change is visible.

Usage: uv run python scripts/shot_contest_uncertainty.py [--root DIR] [--cache DIR]
                                                          [--out DIR] [--samples N] [--seed N]
Writes reports/shot_contest_uncertainty.csv (raw-stream validation + old heuristic, one row
per shot matched to the raw stream), reports/shot_contest_mc.csv (p_off_shooter, p_off_mean,
p_off_std, one row per shot matched to the D12 frame cache) and
reports/shot_contest_neighbour_ambiguity.csv (the P1.2 deliverable: one row per
level/neighbour pair, with sample sizes and the old heuristic alongside for comparison).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.control import ControlParams, control_at_points, control_at_points_with_uncertainty
from scbasket.frames import get_or_build
from scbasket.io import Dataset, iter_frames
from scbasket.validation import match_shots_to_release

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "opendata-basketball"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

MC_SAMPLES = 20  # D8: K = 20
# Ordered least to most contested (SPEC, EVENTS layer); P1.5 later checks this ordering is
# monotone in P_off. Used here only to walk consecutive pairs and look up neighbours.
CONTEST_LEVELS = ("open", "light", "average", "plus", "blocked")
# The P1.2 deliverable's subjects are 'plus' and 'blocked' (the two levels the prior
# heuristic found noisiest: 26.3% and 43.1%, see tasks/todo.md), each checked against
# EVERY adjacent contestLevel, not just the boundary the old heuristic happened to be
# about. 'plus' sits between 'average' and 'blocked' in CONTEST_LEVELS, so it has two
# neighbours; 'blocked' is the top of the order, so it has only one ('plus'). 'average' is
# by far the more populous boundary for 'plus' (374 shots against blocked's 47), so
# dropping it would have hidden the comparison with the most sample behind it.
NEIGHBOURS = {"plus": ("average", "blocked"), "blocked": ("plus",)}


def shot_rows_for_game(dataset: Dataset, game_id: int) -> list[dict]:
    """Raw-stream validation + old heuristic, one row per shot matched directly to tracking.

    Independent of scbasket.frames/D12: any frame carrying the shooter and at least two
    defenders at the exact startFrame counts, which is why this reaches 1,445 shots against
    release_features' 1,360 (see the module docstring).
    """
    events = dataset.events(game_id)
    shots = events["shots"]
    shots = shots[shots["startFrame"].notna()].copy()

    meta = dataset.game_data(game_id)
    side_of_team = {
        meta["homeTeam"]["teamId"]: "home",
        meta["awayTeam"]["teamId"]: "away",
    }

    wanted = {int(f): [] for f in shots["startFrame"]}
    for row in shots.itertuples():
        wanted[int(row.startFrame)].append(row)

    rows: list[dict] = []
    for frame in iter_frames(dataset.tracking_path(game_id)):
        idx = frame.get("frameIdx")
        if idx not in wanted:
            continue
        positions = {"home": frame.get("homePlayers") or [], "away": frame.get("awayPlayers") or []}

        for shot in wanted[idx]:
            def_side = side_of_team.get(shot.defTeamId)
            off_side = side_of_team.get(shot.offTeamId)
            if def_side is None or off_side is None:
                continue

            shooter = next(
                (p for p in positions[off_side] if p.get("playerId") == shot.shooterId), None
            )
            defenders = positions[def_side]
            if shooter is None or len(defenders) < 2:
                continue

            sx, sy = shooter["xyz"][0], shooter["xyz"][1]
            s_err = shooter.get("predError") or 0.0

            ranked = sorted(
                (
                    (
                        math.hypot(d["xyz"][0] - sx, d["xyz"][1] - sy),
                        d.get("predError") or 0.0,
                        d.get("playerId"),
                    )
                    for d in defenders
                ),
                key=lambda t: t[0],
            )
            (d1, e1, id1), (d2, e2, _id2) = ranked[0], ranked[1]

            err1 = math.hypot(s_err, e1)
            # Margin to decide whether the 2nd defender could actually be the 1st.
            gap_err = math.hypot(e1, e2)

            rows.append({
                "gameId": game_id,
                "shotId": shot.id,
                "shooterId": shot.shooterId,
                "reported_dist": shot.closestDefDist,
                "recomputed_dist": d1,
                "reported_defId": shot.closestDefId,
                "recomputed_defId": id1,
                "shooter_predError": s_err,
                "def_predError": e1,
                "combined_error": err1,
                "second_dist": d2,
                "gap_1_2": d2 - d1,
                "gap_error": gap_err,
                "dist_inside_noise": d1 < err1,
                "identity_ambiguous": (d2 - d1) < gap_err,
                "contestLevel": shot.contestLevel,
                "contested": shot.contested,
                "shotQuality": shot.shotQuality,
                "three": shot.three,
                "outcome": shot.outcome,
                "shotType": shot.shotType,
            })
    return rows


def mc_rows_for_game(
    dataset: Dataset,
    game_id: int,
    cache_dir: Path,
    params: ControlParams,
    samples: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """p_off_shooter (deterministic) and p_off_mean/p_off_std (D8 Monte Carlo), one row per
    shot matched to the D12-filtered frame cache -- the P1.2 deliverable.
    """
    frames = get_or_build(dataset, game_id, cache_dir)
    shots = dataset.events(game_id)["shots"]
    shots_matched, release, shooter_xy = match_shots_to_release(frames, shots)
    if len(shots_matched) == 0:
        return pd.DataFrame()

    p_off_mean, p_off_std = control_at_points_with_uncertainty(
        release, shooter_xy, params, samples=samples, rng=rng
    )
    return pd.DataFrame({
        "gameId": game_id,
        "shotId": shots_matched["id"].to_numpy(),
        "shooterId": shots_matched["shooterId"].to_numpy(),
        "p_off_shooter": control_at_points(release, shooter_xy, params),
        "p_off_mean": p_off_mean,
        "p_off_std": p_off_std,
        "contestLevel": shots_matched["contestLevel"].to_numpy(),
        "shotQuality": shots_matched["shotQuality"].to_numpy(),
        "closestDefDist": shots_matched["closestDefDist"].to_numpy(),
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DATA, help="opendata-basketball clone")
    parser.add_argument("--cache", type=Path, default=INTERIM, help="D12 frame cache directory")
    parser.add_argument("--out", type=Path, default=REPORTS, help="reports directory")
    parser.add_argument("--samples", type=int, default=MC_SAMPLES, help="Monte Carlo draws (D8)")
    parser.add_argument("--seed", type=int, default=0, help="seed for the Monte Carlo generator")
    args = parser.parse_args(argv)

    dataset = Dataset(args.root)
    args.out.mkdir(parents=True, exist_ok=True)

    # --- 1/2: raw-stream validation and the old heuristic (unchanged; kept for comparison) ---
    all_rows: list[dict] = []
    for i, game_id in enumerate(dataset.game_ids, start=1):
        rows = shot_rows_for_game(dataset, game_id)
        all_rows.extend(rows)
        print(f"[{i}/10] {game_id}: {len(rows)} shots matched with the raw tracking stream",
              flush=True)

    df = pd.DataFrame(all_rows)
    df.to_csv(args.out / "shot_contest_uncertainty.csv", index=False)

    print(f"\n=== VALIDATION AGAINST THE PUBLISHED FIELD (raw-stream match, {len(df)} shots) ===")
    ok = df["reported_dist"].notna() & df["recomputed_dist"].notna()
    diff = (df.loc[ok, "recomputed_dist"] - df.loc[ok, "reported_dist"]).abs()
    print(
        f"mean difference vs closestDefDist: {diff.mean():.3f} ft  "
        f"median: {diff.median():.3f} ft"
    )
    print(
        f"within 0.5 ft: {(diff < 0.5).mean():.1%}   "
        f"within 1 ft: {(diff < 1.0).mean():.1%}"
    )
    same_id = (df["reported_defId"] == df["recomputed_defId"]).mean()
    print(f"same closest defender identified: {same_id:.1%}")

    print("\n=== OLD HEURISTIC AMBIGUITY (kept for comparison; superseded by section 3 below) ===")
    print(f"closestDefDist median: {df['recomputed_dist'].median():.2f} ft")
    print(f"mean combined error:   {df['combined_error'].mean():.2f} ft")
    print(f"shots where the distance is SMALLER than its error: "
          f"{df['dist_inside_noise'].mean():.1%}")
    print(f"shots where the 2nd defender is within the margin of error of the 1st: "
          f"{df['identity_ambiguous'].mean():.1%}")

    by_level_old = df.groupby("contestLevel").agg(
        shots=("shotId", "size"),
        median_dist=("recomputed_dist", "median"),
        mean_error=("combined_error", "mean"),
        inside_noise=("dist_inside_noise", "mean"),
        ambiguous_identity=("identity_ambiguous", "mean"),
    ).reindex(CONTEST_LEVELS)
    print("\nby contestLevel (old heuristic):")
    print(by_level_old.to_string())

    # --- 3: Monte Carlo uncertainty of P_off, the P1.2 deliverable ---
    params = ControlParams()
    rng = np.random.default_rng(args.seed)
    mc_frames = []
    for i, game_id in enumerate(dataset.game_ids, start=1):
        rows = mc_rows_for_game(dataset, game_id, args.cache, params, args.samples, rng)
        mc_frames.append(rows)
        print(f"[{i}/10] {game_id}: {len(rows)} shots matched to the D12 frame cache",
              flush=True)

    mc = pd.concat(mc_frames, ignore_index=True)
    mc.to_csv(args.out / "shot_contest_mc.csv", index=False)

    print(f"\n=== MONTE CARLO UNCERTAINTY OF P_off (D8, K={args.samples}) ===")
    print(f"{len(mc)} of 1,459 shots matched to the D12 frame cache -- a DIFFERENT, smaller "
          f"denominator than section 1/2's raw-stream match ({len(df)}); see "
          f"validation.release_features's docstring for why.")
    print(f"mean |p_off_mean - p_off_shooter| (Monte Carlo mean vs the deterministic field): "
          f"{(mc['p_off_mean'] - mc['p_off_shooter']).abs().mean():.4f}")

    medians = mc.groupby("contestLevel")["p_off_mean"].median().reindex(CONTEST_LEVELS)
    print("\nmedian p_off_mean by contestLevel (open -> blocked, uncalibrated default params):")
    print(medians.to_string())

    print("\nconsecutive-level median gap vs the model's own uncertainty (mean p_off_std of "
          "the two levels):")
    # strict=False: CONTEST_LEVELS and its [1:] slice are deliberately offset by one, to
    # walk consecutive pairs -- they are never meant to be the same length.
    for level_a, level_b in zip(CONTEST_LEVELS, CONTEST_LEVELS[1:], strict=False):
        if pd.isna(medians[level_a]) or pd.isna(medians[level_b]):
            print(f"  {level_a} -> {level_b}: not enough shots")
            continue
        gap = medians[level_a] - medians[level_b]
        pooled_std = mc.loc[mc["contestLevel"].isin([level_a, level_b]), "p_off_std"].mean()
        verdict = "WITHIN one std: not resolvable" if abs(gap) < pooled_std else "beyond one std"
        print(f"  {level_a} -> {level_b}: median drop {gap:+.4f}, mean p_off_std "
              f"{pooled_std:.4f}  [{verdict}]")

    print("\n=== P1.2 DELIVERABLE: fraction of plus/blocked shots whose own p_off_std exceeds "
          "the distance to a neighbouring contest level's median p_off_mean ===")
    print("(replaces the old heuristic's 'distance smaller than its own error' above -- every "
          "adjacent level is checked, not just the one boundary the old heuristic was about)")
    neighbour_rows: list[dict] = []
    for level, neighbours in NEIGHBOURS.items():
        sub = mc[mc["contestLevel"] == level]
        old_share = by_level_old.loc[level, "inside_noise"]  # reindexed above: always present
        for neighbour in neighbours:
            neighbour_n = int((mc["contestLevel"] == neighbour).sum())
            if sub.empty or pd.isna(medians.get(neighbour, float("nan"))):
                print(f"  {level} vs {neighbour}: no shots")
                continue
            distance_to_neighbour = (sub["p_off_mean"] - medians[neighbour]).abs()
            ambiguous_share = (sub["p_off_std"] > distance_to_neighbour).mean()
            print(f"  {level} vs {neighbour}: {ambiguous_share:.1%} of {len(sub)} shots  "
                  f"({neighbour} median from {neighbour_n} shots; old heuristic '{level} "
                  f"inside its own noise': {old_share:.1%})")
            neighbour_rows.append({
                "level": level,
                "neighbour": neighbour,
                "n_level": len(sub),
                "n_neighbour": neighbour_n,
                "fraction_ambiguous": ambiguous_share,
                "old_heuristic_inside_noise": old_share,
            })

    pd.DataFrame(neighbour_rows).to_csv(
        args.out / "shot_contest_neighbour_ambiguity.csv", index=False
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
