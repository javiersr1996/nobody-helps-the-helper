"""Tracking quality profile and uncertainty propagation.

Broadcast tracking does not observe every position: part of it is
extrapolated. The provider delivers that information frame by frame and
position by position (isDetected and predError, in feet), but never
summarizes it or propagates it into anything built on top. This module does
both.

Reading predError: in 90% of cases, the true position is within predError
feet of the published one.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.io import Dataset, iter_frames

# FIBA court: 28 x 15 meters, origin at the center.
COURT_LENGTH_FT = 91.86
COURT_WIDTH_FT = 49.21


@dataclass
class GameQuality:
    """Quality profile of a single game."""

    game_id: int
    summary: dict
    by_player: pd.DataFrame
    by_zone: pd.DataFrame

    def __repr__(self) -> str:
        s = self.summary
        return (
            f"GameQuality(game_id={self.game_id}, "
            f"detected={s['detected_rate']:.1%}, "
            f"mean predError={s['pred_error_mean']:.2f} ft)"
        )


def profile_game(
    path: str | Path,
    *,
    game_id: int | None = None,
    zone_bins: tuple[int, int] = (6, 4),
) -> GameQuality:
    """Walk an entire game and summarize its tracking quality.

    A single streaming pass: it never materializes the tracking data.
    """
    n_frames = n_dead = 0
    errors: list[float] = []
    errors_detected: list[float] = []
    errors_extrapolated: list[float] = []
    per_player: dict[int, list[int]] = defaultdict(lambda: [0, 0, 0.0])  # n, detected, error sum
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
    """Summary profile of the published games, one row per game."""
    rows = []
    for game_id in dataset.game_ids:
        profile = profile_game(dataset.tracking_path(game_id), game_id=game_id)
        rows.append(profile.summary)
    return pd.DataFrame(rows)


def distance_error(error_a: float, error_b: float) -> float:
    """Error of the distance between two positions, in feet.

    Conservative bound from the quadrature sum of the errors at each
    endpoint. This matters because almost everything tactical is a distance:
    who is guarding whom, whether a closeout arrived in time, whether a
    screen was effective. With a mean predError of 1.5 ft per position, the
    distance between two players carries about 2.1 ft of error, and that is
    what decides whether a shot is marked as contested.
    """
    return math.hypot(error_a, error_b)


def distance_with_error(
    frame_positions: pd.DataFrame,
    player_a: int,
    player_b: int,
) -> tuple[float, float]:
    """Distance between two players in a frame, with its associated error.

    frame_positions is a slice of load_tracking for a single frameIdx.
    Returns (distance, error) in feet.
    """
    a = frame_positions.loc[frame_positions["playerId"] == player_a]
    b = frame_positions.loc[frame_positions["playerId"] == player_b]
    if a.empty or b.empty:
        return (float("nan"), float("nan"))
    a, b = a.iloc[0], b.iloc[0]
    dist = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
    return dist, distance_error(a["predError"], b["predError"])


# 90% quantile of a Rayleigh(sigma) distribution, in units of sigma: sqrt(-2 ln(0.1)).
RAYLEIGH_90_FACTOR = 2.146


def sigma_from_pred_error(pred_error: np.ndarray) -> np.ndarray:
    """Isotropic Gaussian sigma (ft) implied by predError, for the Monte Carlo of P1.2 (D8).

    predError is the provider's 90% quantile of the position error radius (see the module
    docstring). Modelling the error on each axis as an independent, zero-mean Gaussian of
    standard deviation sigma makes the radius sqrt(dx^2 + dy^2) Rayleigh-distributed with
    that same sigma, and a Rayleigh's 90% quantile is sigma * sqrt(-2 ln(0.1)) = 2.146 sigma,
    hence sigma = predError / 2.146.

    Used by scbasket.control.control_with_uncertainty and
    control_at_points_with_uncertainty to perturb tracked positions by their own
    measurement error; nothing else in this module propagates predError, it only
    summarizes it (profile_game, profile_dataset).
    """
    return np.asarray(pred_error, dtype=np.float64) / RAYLEIGH_90_FACTOR
