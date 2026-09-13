"""Loading for the three open data formats published by SkillCorner basketball.

The goal is that nobody has to reread KNOWN_ISSUES.md to avoid the traps: the
pitfalls documented by the provider are encoded here.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# Columns that hold a PLAYER id (not a team, chance, possession, or touch id).
# Inventoried across the 10 published games, family by family.
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

# Columns holding LISTS of player ids.
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
    """Game metadata and rosters."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def iter_frames(path: str | Path, *, skip_dead: bool = False) -> Iterator[dict]:
    """Walk the tracking data frame by frame without loading it all into memory.

    A game is about 125,000 frames and 40 MB compressed: iterate whenever you
    can instead of materializing.

    skip_dead drops dead-ball frames, which arrive with empty homePlayers/
    awayPlayers and ball equal to {}. Note: in the published games these are
    NOT "roughly half" as the provider's documentation claims, but quite a bit
    less. The quality module measures this game by game.
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
    """Tracking data in long format: one row per player and frame.

    isDetected is normalized to a boolean in both cases: the provider
    delivers it as an integer for players and as a float for the ball.

    sample_rate subsamples frames (2 = one out of every two, 25 = one per
    second).
    """
    if sample_rate < 1:
        raise ValueError("sample_rate must be >= 1")

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
    """One DataFrame per event family, with the known pitfalls already fixed.

    With apply_known_fixes (the default):

    - passes.toReceiverId is renamed to interceptedByDefenderId. Despite the
      original name, the field holds the defender who intercepted the pass,
      not the intended receiver. This is documented in the provider's
      KNOWN_ISSUES.md.
    - shots gains countsAsFga: shots with a foul (fouled) do not count as a
      field goal attempt under the FIBA convention used in official box
      scores, but they still appear in the shots table.

    If canonical_ids is passed, players who appear under two different
    player_id values depending on the game are unified.
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
    """Access to the SkillCorner/opendata-basketball repo already cloned on disk."""

    root: Path

    def __post_init__(self) -> None:
        if not (self.root / "data" / "matches.json").exists():
            raise FileNotFoundError(
                f"Can't find data/matches.json under {self.root}. "
                "Clone the dataset with scripts/fetch_data.py."
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
        """player_id -> canonical id, for duplicated players."""
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
        """name: shots, drives, or picks. Offense only, 293 games."""
        path = self.root / "data" / "aggregates" / f"acb_{name}aggregates_20252026.csv"
        return pd.read_csv(path)
