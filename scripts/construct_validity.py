"""Does the tag index measure what F5 says it measures? (P5.1b)

Usage: uv run python scripts/construct_validity.py [--root DIR] [--cache DIR] [--out DIR]

SkillCorner's open bundle carries no crash or box-out label, so there is no ground truth to
score a tag detector against and F5 never claims one. What can still be tested is whether
the DEFINITION behaves the way the thing it is named after must behave. Three checks, on
the FIVE CALIBRATION GAMES only (D11: no held-out game is read here, and P5.1b writes no
criterion, it decides whether criteria are worth writing at all).

  A. The confound, shown rather than hidden. Raw Spearman of the tag geometry against
     `match_dist`. Sitting high side means sitting deep, so this one is expected to look
     good for the wrong reason, and it is printed so the reader can see the correction.
  B. THE GATE. Partial Spearman of the tag geometry against `match_dist`, controlling for
     the whole depth block. Tagging up is not retreating: retreating puts you back in
     time, tagging puts you back ATTACHED to your man. If the relationship dies once depth
     is controlled, the index is a depth proxy wearing a tactical name and F5 STOPS here.
     Expected sign is NEGATIVE: more high side at the release, fewer feet adrift later.
  C. The system check. Tagging up is coached, so some teams should do it and others not.
     Between-team variance of the tag index against a permutation null that shuffles the
     team labels. A pure-noise index has no team signal.

Per-game values are printed for every check before any pooled figure (lesson 1).
Writes {out}/construct_validity.csv.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.frames import get_or_build
from scbasket.io import Dataset
from scbasket.tagging import (
    DEPTH_CONTROLS,
    TAG_FEATURES,
    release_frames_for,
    retreat_match_distance,
    tag_features,
)
from scbasket.validation import CALIBRATION_GAMES, partial_spearman, spearman

N_SHUFFLES = 2000
SEED = 0


def build(dataset: Dataset, game_id: int, cache_dir: Path) -> pd.DataFrame:
    """One row per missed shot of this game: tag geometry, depth controls and the retreat."""
    frames = get_or_build(dataset, game_id, cache_dir)
    events = dataset.events(game_id)
    release, missed = release_frames_for(frames, events["shots"])
    if len(missed) == 0:
        return pd.DataFrame()

    table = pd.concat(
        [
            tag_features(release, missed),
            retreat_match_distance(frames, release, missed, events["rebounds"], events["chances"]),
        ],
        axis=1,
    )
    possessions = events["possessions"].set_index("id")
    return table.assign(
        game=game_id,
        shot_id=missed["id"].to_numpy(),
        off_team=missed["possessionId"].map(possessions["offTeamId"]).to_numpy(),
        three=missed["three"].to_numpy(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/raw/opendata-basketball"))
    parser.add_argument("--cache", type=Path, default=Path("data/interim"))
    parser.add_argument("--out", type=Path, default=Path("reports"))
    args = parser.parse_args()

    dataset = Dataset(args.root)
    print(f"Calibration games only (D11): {list(CALIBRATION_GAMES)}\n")
    table = pd.concat(
        [build(dataset, g, args.cache) for g in CALIBRATION_GAMES], ignore_index=True
    )

    usable = table[table["match_dist"].notna()].copy()
    print(f"missed shots: {len(table)}")
    print(f"  of which the other team rebounded AND the break reached a cached frontcourt "
          f"frame: {len(usable)} ({len(usable) / len(table):.1%})")
    print(f"  pairs found per usable shot: mean {usable['n_pairs_found'].mean():.2f} of 4")
    print(f"\nmatch_dist (ft between the release pairs when the break arrives): "
          f"median {usable['match_dist'].median():.1f}, "
          f"q10 {usable['match_dist'].quantile(.1):.1f}, "
          f"q90 {usable['match_dist'].quantile(.9):.1f}")
    print(f"secs_to_frontcourt: median {usable['secs_to_frontcourt'].median():.1f}")

    rows = []
    print("\n" + "=" * 78)
    print("CHECK A (confounded on purpose) and CHECK B (the gate), per game then pooled")
    print("=" * 78)
    for feature in TAG_FEATURES:
        print(f"\n{feature} vs match_dist:")
        for game_id, part in usable.groupby("game"):
            raw = spearman(part[feature].to_numpy(), part["match_dist"].to_numpy())
            partial = partial_spearman(
                part["match_dist"].to_numpy(),
                part[feature].to_numpy(),
                part[list(DEPTH_CONTROLS)].to_numpy(),
            )
            print(f"  game {game_id}  n {len(part):4d}  raw {raw:+.3f}   "
                  f"given depth {partial:+.3f}")
            rows.append({"check": "B", "feature": feature, "game": game_id, "n": len(part),
                         "raw_spearman": raw, "partial_spearman": partial})

        raw_all = spearman(usable[feature].to_numpy(), usable["match_dist"].to_numpy())
        partial_all = partial_spearman(
            usable["match_dist"].to_numpy(),
            usable[feature].to_numpy(),
            usable[list(DEPTH_CONTROLS)].to_numpy(),
        )
        per_game = [r["partial_spearman"] for r in rows if r["feature"] == feature]
        negative = sum(1 for v in per_game if v < 0)
        print(f"  POOLED    n {len(usable):4d}  raw {raw_all:+.3f}   given depth {partial_all:+.3f}"
              f"   negative in {negative}/5 games")
        rows.append({"check": "B", "feature": feature, "game": "pooled", "n": len(usable),
                     "raw_spearman": raw_all, "partial_spearman": partial_all,
                     "negative_games": negative})

    print("\n" + "=" * 78)
    print("CHECK C: is the tag index a team trait, or noise?")
    print("=" * 78)
    by_team = table.groupby("off_team")["tag_index"].agg(["count", "mean"]).sort_values("mean")
    print(by_team.round(3).to_string())

    teams = table["off_team"].to_numpy()
    values = table["tag_index"].to_numpy()

    def between_team_variance(labels: np.ndarray) -> float:
        frame = pd.DataFrame({"t": labels, "v": values})
        means = frame.groupby("t")["v"].mean()
        return float(means.var(ddof=0))

    observed = between_team_variance(teams)
    rng = np.random.default_rng(SEED)
    null = np.array([between_team_variance(rng.permutation(teams)) for _ in range(N_SHUFFLES)])
    p_value = float((null >= observed).mean())
    print(f"\nbetween-team variance of tag_index: observed {observed:.5f}, "
          f"null median {np.median(null):.5f}, permutation p = {p_value:.4f} "
          f"({N_SHUFFLES} shuffles, seed {SEED})")
    rows.append({"check": "C", "feature": "tag_index", "game": "all", "n": len(table),
                 "observed": observed, "p_value": p_value})

    pd.DataFrame(rows).to_csv(args.out / "construct_validity.csv", index=False)
    print(f"\nWrote {args.out / 'construct_validity.csv'}")
    print("\nP5.1b is a GATE, not a criterion. If check B's partial correlation is not "
          "negative and consistent across games, F5 stops before any bar is written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
