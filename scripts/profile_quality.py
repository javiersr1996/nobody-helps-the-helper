"""Perfil de calidad del tracking sobre los 10 partidos publicados.

Uso: python scripts/profile_quality.py
Escribe reports/quality_by_game.csv y reports/quality_by_zone.csv
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

from scbasket import Dataset
from scbasket.quality import profile_game

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "opendata-basketball"
REPORTS = ROOT / "reports"


def main() -> int:
    dataset = Dataset(DATA)
    REPORTS.mkdir(exist_ok=True)

    summaries, zones, players = [], [], []
    for i, game_id in enumerate(dataset.game_ids, start=1):
        start = time.time()
        profile = profile_game(dataset.tracking_path(game_id), game_id=game_id)
        summaries.append(profile.summary)

        zone = profile.by_zone.assign(game_id=game_id)
        zones.append(zone)
        players.append(profile.by_player.assign(game_id=game_id))

        s = profile.summary
        print(
            f"[{i}/10] {game_id}  detectadas {s['detected_rate']:.1%}  "
            f"predError {s['pred_error_mean']:.2f} ft  "
            f"muertos {s['dead_frame_rate']:.1%}  ({time.time() - start:.0f}s)",
            flush=True,
        )

    by_game = pd.DataFrame(summaries)
    by_game.to_csv(REPORTS / "quality_by_game.csv", index=False)
    pd.concat(zones).to_csv(REPORTS / "quality_by_zone.csv", index=False)
    pd.concat(players).to_csv(REPORTS / "quality_by_player.csv", index=False)

    print("\n=== RESUMEN DE LOS 10 PARTIDOS ===")
    print(
        by_game[[
            "game_id", "frames", "dead_frame_rate", "detected_rate",
            "pred_error_mean", "pred_error_p95",
            "pred_error_detected_mean", "pred_error_extrapolated_mean",
        ]].to_string(index=False)
    )
    print("\ndeteccion: min {:.1%} max {:.1%}".format(
        by_game["detected_rate"].min(), by_game["detected_rate"].max()
    ))
    print("frames muertos: min {:.1%} max {:.1%}".format(
        by_game["dead_frame_rate"].min(), by_game["dead_frame_rate"].max()
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
