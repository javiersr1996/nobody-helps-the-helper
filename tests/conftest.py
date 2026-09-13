"""Shared fixtures for the scbasket test suite.

``synthetic_root`` builds, under ``tmp_path``, a synthetic dataset that mirrors
the real structure of the SkillCorner/opendata-basketball repo: it lets the
suite run on any machine without cloning the ~730 MB real dataset.

Tests that DO need the real dataset should be marked with ``@pytest.mark.data``
and ``@requires_real_dataset`` (defined below), which skips them when the
dataset has not been downloaded to ``data/raw/opendata-basketball``. Example
for future tasks:

    @pytest.mark.data
    @requires_real_dataset
    def test_something_on_the_real_dataset():
        ...
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from scbasket.io import Dataset

REAL_DATASET_ROOT = Path(__file__).resolve().parents[1] / "data" / "raw" / "opendata-basketball"
REAL_MATCHES_JSON = REAL_DATASET_ROOT / "data" / "matches.json"

requires_real_dataset = pytest.mark.skipif(
    not REAL_MATCHES_JSON.exists(),
    reason=f"real dataset not found at {REAL_MATCHES_JSON}; run scripts/fetch_data.py",
)

GAME_ID = 900001
OTHER_GAME_ID = 900002
HOME_TEAM_ID = 1001
AWAY_TEAM_ID = 1002
HOME_PLAYER_IDS = [5001, 5002, 5003, 5004, 5005]
AWAY_PLAYER_IDS = [6001, 6002, 6003, 6004, 6005]
N_FRAMES = 40
DEAD_FRAME_IDXS = frozenset({5, 15, 25, 35, 38})


def _match(game_id: int, date_time: str) -> dict:
    """A matches.json record with the real keys."""
    return {
        "id": game_id,
        "date_time": date_time,
        "home_team": {"id": HOME_TEAM_ID, "name": "Home Team Test"},
        "away_team": {"id": AWAY_TEAM_ID, "name": "Away Team Test"},
        "home_score": 83,
        "away_score": 68,
        "competition_id": 8,
        "competition_name": "Liga ACB",
        "season_id": 51,
        "competition_edition_id": 211,
        "season": "2025-2026",
        "status": "closed",
    }


def _players(ids: list[int]) -> list[dict]:
    return [
        {
            "playerId": pid,
            "firstName": f"First{pid}",
            "lastName": f"Last{pid}",
            "jersey": str(i + 1),
        }
        for i, pid in enumerate(ids)
    ]


def _game_data(game_id: int) -> dict:
    """Minimal game_data.json: gameId, homeTeam and awayTeam with teamId/teamName/players."""
    return {
        "gameId": game_id,
        "homeTeam": {
            "teamId": HOME_TEAM_ID,
            "teamName": "Home Team Test",
            "players": _players(HOME_PLAYER_IDS),
        },
        "awayTeam": {
            "teamId": AWAY_TEAM_ID,
            "teamName": "Away Team Test",
            "players": _players(AWAY_PLAYER_IDS),
        },
    }


def _dynamic_events(game_id: int) -> dict:
    """Minimal dynamic_events.json covering the event families load_events fixes touch."""
    chance_a, chance_b = f"chance-{game_id}-1-0", f"chance-{game_id}-1-1"
    return {
        "possessions": [
            {
                "id": f"possession-{game_id}-1-0",
                "gameId": game_id,
                "period": 1,
                "startFrame": 0,
                "endFrame": 100,
                "offTeamId": HOME_TEAM_ID,
                "defTeamId": AWAY_TEAM_ID,
                "outcome": "FGM",
                "ptsScored": 2,
                "leftHoop": True,
            },
            {
                "id": f"possession-{game_id}-1-1",
                "gameId": game_id,
                "period": 1,
                "startFrame": 101,
                "endFrame": 200,
                "offTeamId": AWAY_TEAM_ID,
                "defTeamId": HOME_TEAM_ID,
                "outcome": "FGM",
                "ptsScored": 3,
                "leftHoop": False,
            },
        ],
        "chances": [
            {
                "id": chance_a,
                "gameId": game_id,
                "period": 1,
                "startFrame": 0,
                "endFrame": 100,
                "offTeamId": HOME_TEAM_ID,
                "defTeamId": AWAY_TEAM_ID,
                "usable": True,
            },
            {
                "id": chance_b,
                "gameId": game_id,
                "period": 1,
                "startFrame": 101,
                "endFrame": 200,
                "offTeamId": AWAY_TEAM_ID,
                "defTeamId": HOME_TEAM_ID,
                "usable": False,
            },
        ],
        "shots": [
            {
                "id": f"shot-{game_id}-1-0",
                "gameId": game_id,
                "chanceId": chance_a,
                "startFrame": 50,
                "shooterId": HOME_PLAYER_IDS[0],
                "offTeamId": HOME_TEAM_ID,
                "defTeamId": AWAY_TEAM_ID,
                "location": [-40.0, -2.0],
                "region": "ra",
                "three": False,
                "outcome": True,
                "fouled": False,
                "contestLevel": "plus",
                "shotQuality": 48.5,
                "closestDefDist": 0.7,
                "closestDefId": AWAY_PLAYER_IDS[0],
            },
            {
                "id": f"shot-{game_id}-1-1",
                "gameId": game_id,
                "chanceId": chance_b,
                "startFrame": 150,
                "shooterId": AWAY_PLAYER_IDS[1],
                "offTeamId": AWAY_TEAM_ID,
                "defTeamId": HOME_TEAM_ID,
                "location": [10.0, 5.0],
                "region": "top_3",
                "three": True,
                "outcome": False,
                "fouled": True,
                "contestLevel": "average",
                "shotQuality": 35.2,
                "closestDefDist": 3.5,
                "closestDefId": HOME_PLAYER_IDS[1],
            },
        ],
        "picks": [
            {
                "id": f"pick-{game_id}-1-0",
                "gameId": game_id,
                "chanceId": chance_a,
                "frame": 60,
                "ballhandlerId": HOME_PLAYER_IDS[0],
                "screenerId": HOME_PLAYER_IDS[1],
                "ballhandlerDefId": AWAY_PLAYER_IDS[0],
                "screenerDefId": AWAY_PLAYER_IDS[1],
                "bhrDefType": "over",
                "scrDefType": "show",
                "direct": False,
            },
        ],
        "off_ball_screens": [
            {
                "id": f"off_ball_screen-{game_id}-1-0",
                "gameId": game_id,
                "chanceId": chance_a,
                "frame": 65,
                "cutterId": HOME_PLAYER_IDS[2],
                "screenerId": HOME_PLAYER_IDS[3],
                "cutterDefId": AWAY_PLAYER_IDS[2],
                "screenerDefId": AWAY_PLAYER_IDS[3],
                "direct": False,
            },
        ],
        "matchups": [
            {
                "id": f"matchup-{game_id}-1-0",
                "chanceId": chance_a,
                "startFrame": 0,
                "endFrame": 50,
                "defPlayerId": AWAY_PLAYER_IDS[0],
                "offPlayerId": HOME_PLAYER_IDS[0],
            },
            {
                "id": f"matchup-{game_id}-1-1",
                "chanceId": chance_a,
                "startFrame": 51,
                "endFrame": 100,
                "defPlayerId": AWAY_PLAYER_IDS[1],
                "offPlayerId": HOME_PLAYER_IDS[1],
            },
            {
                "id": f"matchup-{game_id}-1-2",
                "chanceId": chance_b,
                "startFrame": 101,
                "endFrame": 200,
                "defPlayerId": HOME_PLAYER_IDS[2],
                "offPlayerId": AWAY_PLAYER_IDS[2],
            },
        ],
        "touches": [
            {
                "id": f"touch-{game_id}-1-0",
                "chanceId": chance_a,
                "playerId": HOME_PLAYER_IDS[0],
                "startFrame": 0,
                "endFrame": 20,
            },
            {
                "id": f"touch-{game_id}-1-1",
                "chanceId": chance_a,
                "playerId": HOME_PLAYER_IDS[1],
                "startFrame": 21,
                "endFrame": 50,
            },
            {
                "id": f"touch-{game_id}-1-2",
                "chanceId": chance_b,
                "playerId": AWAY_PLAYER_IDS[0],
                "startFrame": 101,
                "endFrame": 130,
            },
        ],
        "passes": [
            {
                "id": f"pass-{game_id}-1-0",
                "chanceId": chance_a,
                "passerId": HOME_PLAYER_IDS[0],
                "toReceiverId": AWAY_PLAYER_IDS[0],
                "startFrame": 10,
                "endFrame": 15,
            },
            {
                "id": f"pass-{game_id}-1-1",
                "chanceId": chance_a,
                "passerId": HOME_PLAYER_IDS[1],
                "toReceiverId": AWAY_PLAYER_IDS[1],
                "startFrame": 30,
                "endFrame": 35,
            },
        ],
    }


def _player_state(player_id: int, jersey: int, frame_idx: int) -> dict:
    """A live player position. isDetected is an INT (0/1), like the real feed."""
    detected = (frame_idx + player_id) % 3 == 0
    return {
        "xyz": [float(frame_idx + player_id % 10), float(player_id % 5), 0.0],
        "speed": 3.0 + (frame_idx % 5),
        "jersey": str(jersey),
        "playerId": player_id,
        "isDetected": int(detected),
        "predError": 1.5 if detected else 4.5,
    }


def _ball_state(frame_idx: int) -> dict:
    """A live ball position. isDetected is a FLOAT (0.0/1.0), like the real feed."""
    detected = frame_idx % 2 == 0
    return {
        "xyz": [0.0, 0.0, 5.0 + (frame_idx % 3)],
        "speed": 10.0,
        "isDetected": float(detected),
        "predError": 0.8,
    }


def _write_tracking(path: Path) -> None:
    """Write ~N_FRAMES frames as gzipped JSON Lines, with dead frames interspersed.

    Live frames always carry exactly 5 home players, 5 away players and a ball,
    matching the real dataset. Dead frames carry empty homePlayers/awayPlayers
    and an empty ball, but keep their clock fields populated.
    """
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for frame_idx in range(N_FRAMES):
            base = {
                "frameIdx": frame_idx,
                "wallClock": frame_idx * 40,
                "gameClock": 600.0 - frame_idx * 0.04,
                "gameClockStopped": False,
                "period": 1,
                "shotClock": 24.0 - (frame_idx % 24),
            }
            if frame_idx in DEAD_FRAME_IDXS:
                frame = {**base, "homePlayers": [], "awayPlayers": [], "ball": {}}
            else:
                frame = {
                    **base,
                    "homePlayers": [
                        _player_state(pid, i + 1, frame_idx)
                        for i, pid in enumerate(HOME_PLAYER_IDS)
                    ],
                    "awayPlayers": [
                        _player_state(pid, i + 1, frame_idx)
                        for i, pid in enumerate(AWAY_PLAYER_IDS)
                    ],
                    "ball": _ball_state(frame_idx),
                }
            f.write(json.dumps(frame) + "\n")


@pytest.fixture
def synthetic_root(tmp_path: Path) -> Path:
    """Build a synthetic dataset with the real layout expected by Dataset (io.py).

    One full game (GAME_ID) with events, rosters and 40 tracking frames (5 of
    them dead), plus a second game (OTHER_GAME_ID) that only appears in
    matches.json, to exercise sorting by date.
    """
    root = tmp_path / "opendata-basketball"
    data = root / "data"
    data.mkdir(parents=True)

    matches = [
        _match(GAME_ID, "2025-11-15T19:00:00Z"),
        _match(OTHER_GAME_ID, "2025-10-01T18:00:00Z"),
    ]
    (data / "matches.json").write_text(json.dumps(matches), encoding="utf-8")

    # Mirror the real five-column schema. A two-column stand-in would let code that
    # reads the first two columns by position pass, and that code maps ids to names.
    aliases = data / "player_id_aliases.csv"
    aliases.write_text(
        "player_id,player_name,canonical_player_id,canonical_player_name,acb_player_id\n"
        "5999,Alias Spelling,5001,Canonical Spelling,90001\n"
        "5001,Canonical Spelling,5001,Canonical Spelling,90001\n",
        encoding="utf-8",
    )

    game_dir = data / "matches" / str(GAME_ID)
    game_dir.mkdir(parents=True)
    (game_dir / f"{GAME_ID}_game_data.json").write_text(
        json.dumps(_game_data(GAME_ID)), encoding="utf-8"
    )
    (game_dir / f"{GAME_ID}_dynamic_events.json").write_text(
        json.dumps(_dynamic_events(GAME_ID)), encoding="utf-8"
    )
    _write_tracking(game_dir / f"{GAME_ID}_tracking_data.jsonl.gz")

    return root


@pytest.fixture
def synthetic_dataset(synthetic_root: Path) -> Dataset:
    """A Dataset instance ready to use, backed by synthetic_root."""
    return Dataset(synthetic_root)
