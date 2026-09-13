"""Perfil de calidad del tracking y propagacion de la incertidumbre.

El tracking de broadcast no observa todas las posiciones: una parte se
extrapola. El proveedor entrega esa informacion frame a frame y posicion a
posicion (isDetected y predError, en pies), pero no la resume ni la propaga a
nada de lo que se construya encima. Este modulo hace las dos cosas.

Lectura de predError: en el 90% de los casos la posicion real esta a menos de
predError pies de la publicada.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.io import Dataset, iter_frames

# Pista FIBA: 28 x 15 metros, origen en el centro.
COURT_LENGTH_FT = 91.86
COURT_WIDTH_FT = 49.21


@dataclass
class GameQuality:
    """Perfil de calidad de un partido."""

    game_id: int
    summary: dict
    by_player: pd.DataFrame
    by_zone: pd.DataFrame

    def __repr__(self) -> str:
        s = self.summary
        return (
            f"GameQuality(game_id={self.game_id}, "
            f"detectadas={s['detected_rate']:.1%}, "
            f"predError medio={s['pred_error_mean']:.2f} ft)"
        )


def profile_game(
    path: str | Path,
    *,
    game_id: int | None = None,
    zone_bins: tuple[int, int] = (6, 4),
) -> GameQuality:
    """Recorre un partido entero y resume su calidad de tracking.

    Una sola pasada en streaming: no materializa el tracking.
    """
    n_frames = n_dead = 0
    errors: list[float] = []
    errors_detected: list[float] = []
    errors_extrapolated: list[float] = []
    per_player: dict[int, list[int]] = defaultdict(lambda: [0, 0, 0.0])  # n, detectadas, suma error
    nx, ny = zone_bins
    zone_n = np.zeros((nx, ny))
    zone_det = np.zeros((nx, ny))
    zone_err = np.zeros((nx, ny))

    half_len, half_wid = COURT_LENGTH_FT / 2, COURT_WIDTH_FT / 2

    for frame in iter_frames(path):
        n_frames += 1
        home = frame.get("homePlayers") or []
        away = frame.get("awayPlayers") or []
        if not home and not away:
            n_dead += 1
            continue
        for player in home + away:
            detected = bool(player.get("isDetected"))
            err = player.get("predError")
            if err is not None:
                errors.append(err)
                (errors_detected if detected else errors_extrapolated).append(err)

            pid = player.get("playerId")
            if pid is not None:
                acc = per_player[pid]
                acc[0] += 1
                acc[1] += detected
                acc[2] += err or 0.0

            xyz = player.get("xyz")
            if xyz and err is not None:
                ix = min(nx - 1, max(0, int((xyz[0] + half_len) / COURT_LENGTH_FT * nx)))
                iy = min(ny - 1, max(0, int((xyz[1] + half_wid) / COURT_WIDTH_FT * ny)))
                zone_n[ix, iy] += 1
                zone_det[ix, iy] += detected
                zone_err[ix, iy] += err

    arr = np.array(errors)
    arr_det = np.array(errors_detected)
    arr_ext = np.array(errors_extrapolated)

    summary = {
        "game_id": game_id,
        "frames": n_frames,
        "dead_frames": n_dead,
        "dead_frame_rate": n_dead / n_frames if n_frames else float("nan"),
        "positions": len(arr),
        "detected_rate": len(arr_det) / len(arr) if len(arr) else float("nan"),
        "pred_error_mean": float(arr.mean()) if len(arr) else float("nan"),
        "pred_error_median": float(np.median(arr)) if len(arr) else float("nan"),
        "pred_error_p95": float(np.percentile(arr, 95)) if len(arr) else float("nan"),
        "pred_error_detected_mean": float(arr_det.mean()) if len(arr_det) else float("nan"),
        "pred_error_extrapolated_mean": float(arr_ext.mean()) if len(arr_ext) else float("nan"),
    }

    by_player = pd.DataFrame(
        [
            {
                "playerId": pid,
                "positions": n,
                "detected_rate": det / n if n else float("nan"),
                "pred_error_mean": err_sum / n if n else float("nan"),
            }
            for pid, (n, det, err_sum) in per_player.items()
        ]
    ).sort_values("positions", ascending=False).reset_index(drop=True)

    zone_rows = []
    for ix in range(nx):
        for iy in range(ny):
            n = zone_n[ix, iy]
            if not n:
                continue
            zone_rows.append({
                "x_bin": ix,
                "y_bin": iy,
                "x_center": (ix + 0.5) / nx * COURT_LENGTH_FT - half_len,
                "y_center": (iy + 0.5) / ny * COURT_WIDTH_FT - half_wid,
                "positions": int(n),
                "detected_rate": zone_det[ix, iy] / n,
                "pred_error_mean": zone_err[ix, iy] / n,
            })

    return GameQuality(
        game_id=game_id,
        summary=summary,
        by_player=by_player,
        by_zone=pd.DataFrame(zone_rows),
    )


def profile_dataset(dataset: Dataset) -> pd.DataFrame:
    """Perfil resumido de los partidos publicados, uno por fila."""
    rows = []
    for game_id in dataset.game_ids:
        profile = profile_game(dataset.tracking_path(game_id), game_id=game_id)
        rows.append(profile.summary)
    return pd.DataFrame(rows)


def distance_error(error_a: float, error_b: float) -> float:
    """Error de la distancia entre dos posiciones, en pies.

    Cota conservadora por suma en cuadratura de los errores de cada extremo.
    Importa porque casi todo lo tactico es una distancia: quien defiende a
    quien, si un closeout llego, si el bloqueo fue efectivo. Con un predError
    medio de 1,5 ft por posicion, la distancia entre dos jugadores arrastra
    unos 2,1 ft de error, y eso decide si un tiro se marca como contestado.
    """
    return math.hypot(error_a, error_b)


def distance_with_error(
    frame_positions: pd.DataFrame,
    player_a: int,
    player_b: int,
) -> tuple[float, float]:
    """Distancia entre dos jugadores en un frame, con su error asociado.

    frame_positions es un corte de load_tracking para un unico frameIdx.
    Devuelve (distancia, error) en pies.
    """
    a = frame_positions.loc[frame_positions["playerId"] == player_a]
    b = frame_positions.loc[frame_positions["playerId"] == player_b]
    if a.empty or b.empty:
        return (float("nan"), float("nan"))
    a, b = a.iloc[0], b.iloc[0]
    dist = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
    return dist, distance_error(a["predError"], b["predError"])
