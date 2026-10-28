"""Whole rebounds, as tracking, for the page to replay on a court (P7.8).

Usage: uv run python scripts/court_scenes.py [--root DIR] [--cache DIR] [--out FILE]
                                             [--per-game N]

Every other artefact in this repository reduces a rebound to numbers. The page needs the
rebound itself: the ball coming down, the ten players moving, and the moment one of them wins
it. That is what the frame cache already holds, so this script models nothing of its own. It
cuts the window around each chosen rebound and attaches the frozen model's probabilities to
it, exactly as `scripts/rebound_contest.py` grades them.

What it deliberately does NOT write: any player id, name or number. Slots 0-4 are the
attacking team and 5-9 the defending one, the same order the model reads, and a slot is not a
person. The ruling the repository is built under holds here too: this measures vectors, never
intentions, and nothing about a clip says a player crashed, tagged up or boxed out.

The choice is a rule, not a search: the first rebounds of each game, half of them ones the
frozen model ranks first and half ones it gets wrong, so the page cannot quietly show only
the clips that flatter the model. Nothing looks at how good a clip is to watch.

Writes {out} (default `reports/court_scenes.json`), which the page inlines.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.conditional import FROZEN_BETA, choice_probabilities, rebound_choice_set
from scbasket.court import HOOP_X
from scbasket.frames import GameFrames, at_frames, get_or_build
from scbasket.io import Dataset
from scbasket.tagging import APPROACH_LEAD_FRAMES, zone_radius
from scbasket.validation import CALIBRATION_GAMES, VALIDATION_GAMES

#: 25 fps in, every other frame out: the page redraws at 12.5 fps, which is enough to read a
#: player's approach and cheap enough to inline several clips in one file.
STRIDE = 2
#: How much of the play to keep around the moment the ball is won, in frames at 25 fps.
BEFORE_FRAMES, AFTER_FRAMES = 100, 12
#: Below this a clip is not worth replaying.
MIN_CLIP_FRAMES = 12
#: How far the winner may be from the published landing point, in feet, before the clip is
#: refused. Tracking noise is about 1.5 ft; anything past this is a different disagreement.
MAX_LANDING_GAP_FT = 3.0


def location_of(event: pd.Series) -> np.ndarray | None:
    """The published `[x, y]` of an event, or None where it has none.

    One place decides what "this event has no location" means, because the two callers below
    used to each have their own opinion about it.
    """
    place = event["location"]
    return np.asarray(place, dtype=float) if isinstance(place, list) else None


def clip_of(frames: GameFrames, first: int, last: int, chance: int) -> GameFrames:
    """Rows of ONE chance between two frame indices, every STRIDEth one.

    The chance filter is not cosmetic. Orientation is a property of the possession, so the
    frames after a defensive rebound already belong to the other team attacking the other
    hoop: without this, a clip mirrors itself halfway through and the winner appears 70 ft
    from the ball. That is what the landing check below caught.
    """
    clip = at_frames(frames, np.arange(first, last + 1, STRIDE))
    return clip.take(np.flatnonzero(clip.chance_idx == chance))


def scene(frames: GameFrames, rebound: pd.Series, shot: pd.Series, frame: int, chance: int,
          probability: np.ndarray, winner: int, half: str) -> dict | None:
    """One rebound as a replayable clip, or None where the cache cannot support one."""
    shot_xy, landing = location_of(shot), location_of(rebound)
    if shot_xy is None or landing is None:
        return None
    start = frame - BEFORE_FRAMES
    if pd.notna(shot.get("endFrame")):
        start = max(start, int(shot["endFrame"]) - 25)
    clip = clip_of(frames, start, frame + AFTER_FRAMES, chance)
    if len(clip) < MIN_CLIP_FRAMES:
        return None
    won_at = int(min(np.searchsorted(clip.frame_idx, frame), len(clip) - 1))
    # The clip and the published landing point come from different places: the tracking
    # cache and the event table. If the winner is not standing where the ball was won, this
    # clip does not show what the caption says it shows, so it does not ship.
    if np.linalg.norm(clip.xy[won_at, winner] - landing) > MAX_LANDING_GAP_FT:
        return None
    return {
        "half": half,
        "defensive": bool(rebound["defensive"]),
        "three": bool(shot["three"]),
        "shot": np.round(shot_xy, 2).tolist(),
        "landing": np.round(landing, 2).tolist(),
        "zone": round(float(zone_radius(np.hypot(shot_xy[0] - HOOP_X, shot_xy[1]))), 2),
        "won_at": won_at,
        "winner": int(winner),
        "p": np.round(probability, 4).tolist(),
        "xy": np.round(clip.xy, 1).tolist(),
        "ball": np.round(clip.ball, 1).tolist(),
    }


def candidates(probability: np.ndarray, winner: np.ndarray, wanted: int) -> list[int]:
    """Rows to try, in rebound order: the earliest the model ranks first, and the earliest
    it does not, in equal numbers. Three times as many as are wanted, because a clip the
    cache cannot support is refused below and the next candidate takes its place."""
    first = probability.argmax(axis=1) == winner
    keep = 3 * wanted // 2
    return sorted(int(i) for i in
                  list(np.flatnonzero(first)[:keep]) + list(np.flatnonzero(~first)[:keep]))


def from_game(dataset: Dataset, game_id: int, cache: Path, wanted: int) -> list[dict]:
    """The clips taken from one game, in the order the rebounds happened."""
    frames = get_or_build(dataset, game_id, cache)
    events = dataset.events(game_id)
    rebounds, shots = events["rebounds"], events["shots"].set_index("id")
    design, winner, rows = rebound_choice_set(frames, rebounds, shots.reset_index())
    if not len(winner):
        return []
    probability = choice_probabilities(design, FROZEN_BETA)
    graded = rows[rows["winner_slot"].notna()].reset_index(drop=True)
    by_id = rebounds.set_index("id")
    chance_at = {name: i for i, name in enumerate(events["chances"]["id"])}
    half = "calibration" if game_id in CALIBRATION_GAMES else "held out"

    built, refused = [], 0
    for at in candidates(probability, winner, wanted):
        if len(built) == wanted:
            break
        row = graded.iloc[at]
        rebound, shot = by_id.loc[row["rebound_id"]], shots.loc[row["shot_id"]]
        clip = scene(frames, rebound, shot, int(row["frame"]), chance_at[rebound["chanceId"]],
                     probability[at], int(winner[at]), half)
        if clip is None:
            refused += 1
        else:
            built.append(clip)
    print(f"  {game_id}: {len(built)} clips, {refused} refused (too short, or the winner not "
          f"within {MAX_LANDING_GAP_FT:.0f} ft of the published landing point)")
    return built


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/raw/opendata-basketball"))
    parser.add_argument("--cache", type=Path, default=Path("data/interim"))
    parser.add_argument("--out", type=Path, default=Path("reports/court_scenes.json"))
    parser.add_argument("--per-game", type=int, default=4, help="clips per game, half of them"
                                                               " ones the model gets wrong")
    args = parser.parse_args()

    dataset = Dataset(args.root)
    scenes = []
    for game_id in (CALIBRATION_GAMES[0], VALIDATION_GAMES[0]):
        scenes += from_game(dataset, game_id, args.cache, args.per_game)

    if not scenes:
        print("no scene could be built; is the frame cache in data/interim?", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "hoop_x": HOOP_X,
        "lead_frames": APPROACH_LEAD_FRAMES,
        "stride": STRIDE,
        "fps": 25 / STRIDE,
        "scenes": scenes,
    }), encoding="utf-8")

    ranked_first = sum(int(np.argmax(s["p"]) == s["winner"]) for s in scenes)
    print(f"wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB, {len(scenes)} clips, "
          f"{sum(len(s['xy']) for s in scenes)} frames, "
          f"{ranked_first} clips the frozen model ranks first and "
          f"{len(scenes) - ranked_first} it does not)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
