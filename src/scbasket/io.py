"""Carga de los tres formatos del open data de baloncesto de SkillCorner.

El objetivo del modulo es que nadie tenga que releer KNOWN_ISSUES.md para no
tropezar: las trampas documentadas por el proveedor van codificadas aqui.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# Columnas que contienen un id de JUGADOR (no de equipo, chance, posesion ni
# touch). Inventariadas sobre los 10 partidos publicados, familia a familia.
PLAYER_ID_COLUMNS = frozenset({
    "playerId", "defPlayerId", "offPlayerId",
    "ballhandlerId", "ballhandlerDefId",
    "screenerId", "screenerDefId",
    "cutterId", "cutterDefId",
    "setterId", "setterDefId",
    "receiverId", "receiverDefId",
    "passerId", "shooterId", "blockerId", "closestDefId",
    "rebounderId", "foulerId", "fouledId",
    "turnedOverId", "stealerId", "defenderId",
    "interceptedByDefenderId",
})

# Columnas con LISTAS de ids de jugador.
PLAYER_ID_LIST_COLUMNS = frozenset({"offPlayerIds", "defPlayerIds"})

EVENT_FAMILIES = (
    "chances", "possessions", "chance_players", "matchups",
    "shots", "free_throws", "picks", "drives", "passes", "touches",
    "dribbles", "rebounds", "turnovers", "fouls", "isolations",
    "handoffs", "posts", "off_ball_screens", "closeouts", "timeouts",
)

TRACKING_COLUMNS = [
    "frameIdx", "wallClock", "gameClock", "shotClock", "gameClockStopped",
    "period", "side", "playerId", "jersey", "x", "y", "z", "speed",
    "isDetected", "predError",
]


def load_game_data(path: str | Path) -> dict:
    """Metadatos del partido y plantillas."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def iter_frames(path: str | Path, *, skip_dead: bool = False) -> Iterator[dict]:
    """Recorre el tracking frame a frame sin cargarlo entero en memoria.

    Un partido son unos 125.000 frames y 40 MB comprimidos: itera siempre que
    puedas en lugar de materializar.

    skip_dead descarta los frames de balon muerto, que llegan con
    homePlayers/awayPlayers vacios y ball igual a {}. Ojo: en los partidos
    publicados no son "aproximadamente la mitad" como dice la documentacion
    del proveedor, sino bastante menos. El modulo quality lo mide partido a
    partido.
    """
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            frame = json.loads(line)
            if skip_dead and not frame.get("homePlayers") and not frame.get("awayPlayers"):
                continue
            yield frame


def load_tracking(
    path: str | Path,
    *,
    skip_dead: bool = True,
    sample_rate: int = 1,
    include_ball: bool = False,
) -> pd.DataFrame:
    """Tracking en formato largo: una fila por jugador y frame.

    isDetected se normaliza a booleano en ambos casos: el proveedor lo entrega
    como entero para jugadores y como float para el balon.

    sample_rate submuestrea frames (2 = uno de cada dos, 25 = uno por segundo).
    """
    if sample_rate < 1:
        raise ValueError("sample_rate debe ser >= 1")

    rows: list[tuple] = []
    for i, frame in enumerate(iter_frames(path, skip_dead=skip_dead)):
        if i % sample_rate:
            continue
        clock = (
            frame["frameIdx"], frame["wallClock"], frame.get("gameClock"),
            frame.get("shotClock"), frame.get("gameClockStopped"), frame.get("period"),
        )
        for side in ("homePlayers", "awayPlayers"):
            for player in frame.get(side) or ():
                xyz = player.get("xyz") or (None, None, None)
                rows.append((
                    *clock, side[:4], player.get("playerId"), player.get("jersey"),
                    xyz[0], xyz[1], xyz[2], player.get("speed"),
                    bool(player.get("isDetected")), player.get("predError"),
                ))
        if include_ball:
            ball = frame.get("ball") or {}
            if ball:
                xyz = ball.get("xyz") or (None, None, None)
                rows.append((
                    *clock, "ball", None, None,
                    xyz[0], xyz[1], xyz[2], ball.get("speed"),
                    bool(ball.get("isDetected")), ball.get("predError"),
                ))

    return pd.DataFrame(rows, columns=TRACKING_COLUMNS)


def load_events(
    path: str | Path,
    *,
    canonical_ids: dict[int, int] | None = None,
    apply_known_fixes: bool = True,
) -> dict[str, pd.DataFrame]:
    """Un DataFrame por familia de eventos, con las trampas ya corregidas.

    Con apply_known_fixes (por defecto):

    - passes.toReceiverId se renombra a interceptedByDefenderId. Pese al
      nombre original, el campo guarda el defensor que intercepto el pase, no
      el receptor previsto. Lo dice KNOWN_ISSUES.md del proveedor.
    - shots gana countsAsFga: los tiros con falta (fouled) no cuentan como
      intento de campo en la convencion FIBA de las actas oficiales, pero si
      aparecen en la tabla shots.

    Si se pasa canonical_ids, se unifican los jugadores que aparecen con dos
    player_id distintos segun el partido.
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    tables: dict[str, pd.DataFrame] = {}
    for family, records in raw.items():
        if not isinstance(records, list):
            continue
        frame = pd.DataFrame(records)
        if apply_known_fixes and family == "passes" and "toReceiverId" in frame.columns:
            frame = frame.rename(columns={"toReceiverId": "interceptedByDefenderId"})
        if apply_known_fixes and family == "shots" and "fouled" in frame.columns:
            frame["countsAsFga"] = ~frame["fouled"].fillna(False).astype(bool)
        if canonical_ids:
            frame = _canonicalize_player_ids(frame, canonical_ids)
        tables[family] = frame
    return tables


def _canonicalize_player_ids(frame: pd.DataFrame, mapping: dict[int, int]) -> pd.DataFrame:
    for col in frame.columns:
        if col in PLAYER_ID_COLUMNS:
            frame[col] = frame[col].map(lambda v: mapping.get(v, v))
        elif col in PLAYER_ID_LIST_COLUMNS:
            frame[col] = frame[col].map(
                lambda vs: [mapping.get(v, v) for v in vs] if isinstance(vs, list) else vs
            )
    return frame


@dataclass(frozen=True)
class Dataset:
    """Acceso al repo SkillCorner/opendata-basketball ya clonado en disco."""

    root: Path

    def __post_init__(self) -> None:
        if not (self.root / "data" / "matches.json").exists():
            raise FileNotFoundError(
                f"No encuentro data/matches.json bajo {self.root}. "
                "Clona el dataset con scripts/fetch_data.py."
            )

    @property
    def matches(self) -> pd.DataFrame:
        with open(self.root / "data" / "matches.json", encoding="utf-8") as f:
            rows = json.load(f)
        frame = pd.json_normalize(rows, sep="_")
        return frame.sort_values("date_time").reset_index(drop=True)

    @property
    def game_ids(self) -> list[int]:
        return self.matches["id"].tolist()

    @property
    def canonical_ids(self) -> dict[int, int]:
        """player_id -> id canonico, para los jugadores duplicados."""
        aliases = pd.read_csv(self.root / "data" / "player_id_aliases.csv")
        return dict(zip(aliases.iloc[:, 0], aliases.iloc[:, 1], strict=True))

    def _game_dir(self, game_id: int) -> Path:
        return self.root / "data" / "matches" / str(game_id)

    def tracking_path(self, game_id: int) -> Path:
        return self._game_dir(game_id) / f"{game_id}_tracking_data.jsonl.gz"

    def events(self, game_id: int, *, canonical: bool = True) -> dict[str, pd.DataFrame]:
        return load_events(
            self._game_dir(game_id) / f"{game_id}_dynamic_events.json",
            canonical_ids=self.canonical_ids if canonical else None,
        )

    def game_data(self, game_id: int) -> dict:
        return load_game_data(self._game_dir(game_id) / f"{game_id}_game_data.json")

    def tracking(self, game_id: int, **kwargs) -> pd.DataFrame:
        return load_tracking(self.tracking_path(game_id), **kwargs)

    def aggregates(self, name: str) -> pd.DataFrame:
        """name: shots, drives o picks. Solo ataque, 293 partidos."""
        path = self.root / "data" / "aggregates" / f"acb_{name}aggregates_20252026.csv"
        return pd.read_csv(path)
