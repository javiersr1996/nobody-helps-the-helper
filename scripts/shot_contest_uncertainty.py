"""Cuanto de la contestacion de un tiro es senal y cuanto es error de tracking.

SkillCorner publica contestLevel, contested y shotQuality apoyandose en
closestDefDist: la distancia entre tirador y defensor mas cercano en el momento
del release. Esa distancia se calcula sobre dos posiciones que el propio
proveedor acompana de su error esperado (predError, en pies).

Este script mide tres cosas por tiro:

1. Validacion: la distancia recalculada desde el tracking contra la publicada.
2. Si la distancia cae por debajo de su propio error combinado.
3. Si la identidad del defensor mas cercano es ambigua, es decir, si el segundo
   defensor mas cercano esta dentro del margen de error del primero.

Uso: python scripts/shot_contest_uncertainty.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

from scbasket import Dataset
from scbasket.io import iter_frames

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "opendata-basketball"
REPORTS = ROOT / "reports"


def shot_rows_for_game(dataset: Dataset, game_id: int) -> list[dict]:
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
            # Margen para decidir si el 2o defensor podria ser en realidad el 1o.
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


def main() -> int:
    dataset = Dataset(DATA)
    REPORTS.mkdir(exist_ok=True)

    all_rows: list[dict] = []
    for i, game_id in enumerate(dataset.game_ids, start=1):
        rows = shot_rows_for_game(dataset, game_id)
        all_rows.extend(rows)
        print(f"[{i}/10] {game_id}: {len(rows)} tiros emparejados con tracking", flush=True)

    df = pd.DataFrame(all_rows)
    df.to_csv(REPORTS / "shot_contest_uncertainty.csv", index=False)

    print("\n=== VALIDACION CONTRA EL CAMPO PUBLICADO ===")
    ok = df["reported_dist"].notna() & df["recomputed_dist"].notna()
    diff = (df.loc[ok, "recomputed_dist"] - df.loc[ok, "reported_dist"]).abs()
    print(f"tiros emparejados: {len(df)}")
    print(f"diferencia media con closestDefDist: {diff.mean():.3f} ft  mediana: {diff.median():.3f} ft")
    print(f"dentro de 0,5 ft: {(diff < 0.5).mean():.1%}   dentro de 1 ft: {(diff < 1.0).mean():.1%}")
    same_id = (df["reported_defId"] == df["recomputed_defId"]).mean()
    print(f"mismo defensor mas cercano identificado: {same_id:.1%}")

    print("\n=== LA DISTANCIA CONTRA SU PROPIO ERROR ===")
    print(f"closestDefDist mediana: {df['recomputed_dist'].median():.2f} ft")
    print(f"error combinado medio:  {df['combined_error'].mean():.2f} ft")
    print(f"tiros donde la distancia es MENOR que su error: {df['dist_inside_noise'].mean():.1%}")

    print("\n=== AMBIGUEDAD DEL DEFENSOR MAS CERCANO ===")
    print(f"tiros donde el 2o defensor esta dentro del margen de error del 1o: "
          f"{df['identity_ambiguous'].mean():.1%}")

    print("\n=== POR NIVEL DE CONTESTACION ===")
    by_level = df.groupby("contestLevel").agg(
        tiros=("shotId", "size"),
        dist_mediana=("recomputed_dist", "median"),
        error_medio=("combined_error", "mean"),
        dentro_del_ruido=("dist_inside_noise", "mean"),
        identidad_ambigua=("identity_ambiguous", "mean"),
    ).sort_values("dist_mediana")
    print(by_level.to_string())

    return 0


if __name__ == "__main__":
    sys.exit(main())
