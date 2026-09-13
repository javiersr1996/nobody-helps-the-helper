"""Per-game frame arrays: the tracking stream converted once into oriented numpy arrays.

Every later phase (control field, EPC, validation, series) reads these arrays
instead of the JSON stream, so this module is the performance backbone of the
package. One build streams a game once (about 40 MB gzipped, 6 s of JSON
parsing), applies the D12 filters, orients every frame into the attacking frame
of its possession, estimates velocities (D10), resolves the ball handler and the
defensive matchups, and caches the result as ``data/interim/{gid}_frames.npz``.

Row layout (one row per kept frame, in stream order, ``frame_idx`` ascending):

- ``xy[:, 0:5]`` are the five attackers and ``xy[:, 5:10]`` the five defenders,
  each block sorted by player id, so a player keeps its slot for as long as the
  lineup does not change. ``off_ids`` / ``def_ids`` give the id in each slot.
- Coordinates are feet in the attacking frame of the row's possession
  (``scbasket.court.orient``): attacked hoop at negative x. The ball's z is left
  untouched.
- ``ball_holder`` is a slot 0-4 into the attacker block; ``matchup[:, j]`` is a
  slot 0-4 into the defender block (the defender of attacker j sits at
  ``xy[:, 5 + matchup[:, j]]``). Both are -1 when unknown.
- Player ids are canonicalized (``data/player_id_aliases.csv``) so they join
  the event tables loaded with canonical ids.

Which frames enter (D12): live (players on the floor), inside a chance with
``usable == True``, with a non-null shotClock and with exactly 5 + 5 players.
A dropped frame is attributed to the first failing test in that order (plus a
final technical bucket for chances whose possession, ``leftHoop`` or offensive
side cannot be resolved), and the counts come back in ``BuildStats``.

Shared boundary frames: consecutive chances (and possessions) share their
boundary frame in the provider's tables, ``prev.endFrame == next.startFrame``
for 127 of 194 chance boundaries in game 114086. That frame is given to the
EARLIER chance: across the 10 games it is the release frame of 62 shots (of
1,459) against the first frame of only 8, and 5,346 of 14,416 matchup intervals
end exactly there.

Velocity (D10): centered difference over +-2 frames of positions smoothed with
a 5-frame moving average, computed on the cached (oriented, filtered) arrays,
within runs that break at every frameIdx jump, possession change or lineup
change; capped at 30 ft/s. Windows shrink symmetrically at run edges (down to a
one-sided difference at the first and last frame), which keeps a straight-line
trajectory exact everywhere. The provider's ``speed`` is a check, not an input.

Sampling (D9): ``subsample(frames, 5)`` gives the 5 Hz view used by series and
aggregates; ``at_frames`` picks the 25 Hz rows of event frames.
"""

from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.court import orient
from scbasket.io import Dataset, iter_frames

FPS = 25.0  # tracking frame rate
V_MAX_FT_S = 30.0  # cap on the estimated speed (D10)
SMOOTH_RADIUS = 2  # 5-frame moving average (D10)
DIFF_RADIUS = 2  # centered difference over +-2 frames (D10)
HOLDER_MAX_DIST_FT = 3.0  # ball-handler fallback: nearest attacker within this distance
N_SIDE = 5
FORMAT_VERSION = 1  # bump when the npz layout changes; stale caches are rebuilt

# Attribution of dropped frames, in the order the D12 tests are applied.
DROP_REASONS = (
    "no_chance",
    "unusable_chance",
    "null_shot_clock",
    "not_five_v_five",
    "unresolved_possession",
)

_NAN3 = (np.nan, np.nan, np.nan)
_SWAP_BLOCKS = np.r_[N_SIDE : 2 * N_SIDE, 0:N_SIDE]


@dataclass
class GameFrames:
    """One row per live frame inside a usable chance (see the module docstring).

    Dtypes: frame_idx int32, wall_clock int64 (ms), shot_clock float32 (s),
    period int8, possession_idx / chance_idx int32 (positional row into
    ``Dataset.events(game_id)["possessions"]`` / ``["chances"]``), off_ids /
    def_ids int32 (N, 5), xy / v float32 (N, 10, 2), pred_error float32 (N, 10),
    detected bool (N, 10), ball float32 (N, 3), ball_holder int8 (N,), matchup
    int8 (N, 5).
    """

    game_id: int
    frame_idx: np.ndarray
    wall_clock: np.ndarray
    shot_clock: np.ndarray
    period: np.ndarray
    possession_idx: np.ndarray
    chance_idx: np.ndarray
    off_ids: np.ndarray
    def_ids: np.ndarray
    xy: np.ndarray
    v: np.ndarray
    pred_error: np.ndarray
    detected: np.ndarray
    ball: np.ndarray
    ball_holder: np.ndarray
    matchup: np.ndarray

    def __len__(self) -> int:
        return len(self.frame_idx)

    def take(self, rows: np.ndarray) -> GameFrames:
        """Rows selected by an index array, boolean mask or slice, in that order."""
        return replace(self, **{name: getattr(self, name)[rows] for name in _ROW_FIELDS})


_ROW_FIELDS = tuple(f.name for f in fields(GameFrames) if f.name != "game_id")


@dataclass
class BuildStats:
    """Diagnostics of one build: D12 attribution, coverage and the velocity check."""

    game_id: int
    n_frames: int  # every frame in the stream, dead ones included
    n_live: int  # frames with players on the floor
    n_no_chance: int  # live but outside every chance
    n_no_chance_clock_stopped: int  # subset of the above with gameClockStopped
    n_unusable_chance: int
    n_null_shot_clock: int
    n_not_five_v_five: int
    n_unresolved_possession: int
    n_kept: int
    n_runs: int  # velocity runs among the kept rows
    holder_touch_share: float  # kept rows whose ball handler comes from touches
    holder_fallback_share: float  # ... from the nearest attacker within 3 ft
    holder_none_share: float
    matchup_cell_coverage: float  # (row, attacker) cells with an assigned defender
    matchup_frame_coverage: float  # rows with all five attackers assigned
    n_detected_positions: int
    speed_pearson_detected: float  # |v| vs provider speed on detected positions
    speed_pearson_all: float
    build_seconds: float

    def as_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- streaming


class _LiveBuffer:
    """Preallocated per-live-frame arrays that double when full.

    vals is (n, 2, 5, 5): side (home, away) x player x (x, y, speed, predError,
    isDetected). ids is (n, 2, 5). Frames whose sides do not carry exactly five
    players are flagged in five_v_five and left with unspecified values.
    """

    def __init__(self, capacity: int = 1 << 16) -> None:
        self.n = 0
        self.capacity = capacity
        self.frame_idx = np.empty(capacity, np.int32)
        self.wall_clock = np.empty(capacity, np.int64)
        self.shot_clock = np.empty(capacity, np.float64)
        self.period = np.empty(capacity, np.int8)
        self.clock_stopped = np.empty(capacity, bool)
        self.five_v_five = np.empty(capacity, bool)
        self.vals = np.zeros((capacity, 2, N_SIDE, 5), np.float64)
        self.ids = np.zeros((capacity, 2, N_SIDE), np.int32)
        self.ball = np.empty((capacity, 3), np.float64)

    _ARRAYS = (
        "frame_idx", "wall_clock", "shot_clock", "period", "clock_stopped",
        "five_v_five", "vals", "ids", "ball",
    )

    def grow(self) -> None:
        self.capacity *= 2
        for name in self._ARRAYS:
            old = getattr(self, name)
            new = np.zeros((self.capacity, *old.shape[1:]), old.dtype)
            new[: self.n] = old
            setattr(self, name, new)

    def trim(self) -> None:
        for name in self._ARRAYS:
            setattr(self, name, getattr(self, name)[: self.n])


def _player_row(player: dict) -> tuple[float, float, float, float, float]:
    xyz = player.get("xyz") or _NAN3
    speed = player.get("speed")
    err = player.get("predError")
    return (
        xyz[0],
        xyz[1],
        np.nan if speed is None else speed,
        np.nan if err is None else err,
        1.0 if player.get("isDetected") else 0.0,
    )


def _stream_live(path: Path) -> tuple[_LiveBuffer, int]:
    """One pass over the tracking: live frames into arrays, plus the total frame count."""
    buf = _LiveBuffer()
    n_frames = 0
    for frame in iter_frames(path):
        n_frames += 1
        home = frame.get("homePlayers") or ()
        away = frame.get("awayPlayers") or ()
        if not home and not away:
            continue
        if buf.n == buf.capacity:
            buf.grow()
        i = buf.n
        buf.frame_idx[i] = frame["frameIdx"]
        buf.wall_clock[i] = frame["wallClock"]
        buf.period[i] = frame["period"]
        shot_clock = frame.get("shotClock")
        buf.shot_clock[i] = np.nan if shot_clock is None else shot_clock
        buf.clock_stopped[i] = bool(frame.get("gameClockStopped"))
        five = True
        for side, players in ((0, home), (1, away)):
            if len(players) != N_SIDE:
                five = False
                continue
            buf.vals[i, side] = [_player_row(p) for p in players]
            buf.ids[i, side] = [p["playerId"] for p in players]
        buf.five_v_five[i] = five
        ball = frame.get("ball") or {}
        buf.ball[i] = ball.get("xyz") or _NAN3
        buf.n += 1
    buf.trim()
    return buf, n_frames


# --------------------------------------------------------------------------- events


def _interval_labels(table: pd.DataFrame, query: np.ndarray) -> np.ndarray:
    """Row index of the interval [startFrame, endFrame] containing each query frame, or -1.

    Overlaps go to the EARLIER interval (see the module docstring on shared
    boundary frames). Rows with a missing bound cover nothing.
    """
    starts = pd.to_numeric(table["startFrame"], errors="coerce").to_numpy(dtype=float)
    ends = pd.to_numeric(table["endFrame"], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(starts) & np.isfinite(ends) & (ends >= starts) & (starts >= 0)
    query = np.asarray(query, dtype=np.int64)
    out = np.full(query.shape, -1, np.int32)
    if not valid.any() or query.size == 0:
        return out
    size = int(max(ends[valid].max(), query.max())) + 1
    labels = np.full(size, -1, np.int32)
    rows = np.flatnonzero(valid)
    for row in rows[np.argsort(starts[valid], kind="stable")[::-1]]:
        labels[int(starts[row]) : int(ends[row]) + 1] = row
    ok = (query >= 0) & (query < size)
    out[ok] = labels[query[ok]]
    return out


def _possession_of_chances(chances: pd.DataFrame, possessions: pd.DataFrame) -> np.ndarray:
    """Possession row of each chance: by possessionId when present, else by interval."""
    if "possessionId" in chances.columns and "id" in possessions.columns:
        row_of = {pid: i for i, pid in enumerate(possessions["id"])}
        mapped = chances["possessionId"].map(row_of)
        return mapped.fillna(-1).to_numpy(dtype=np.int32)
    starts = pd.to_numeric(chances["startFrame"], errors="coerce").fillna(-1)
    return _interval_labels(possessions, starts.to_numpy(dtype=np.int64))


def _bool_column(column: pd.Series) -> np.ndarray:
    """A possibly-object boolean column as a bool array, with missing values as False."""
    values = column.to_numpy(dtype=object)
    return np.where(pd.isna(values), False, values).astype(bool)


def canonical_player_ids(dataset: Dataset) -> dict[int, int]:
    """player_id -> canonical_player_id for the aliased players only.

    Thin wrapper over ``Dataset.canonical_ids``: it normalises the types and drops
    the rows that map a player to themselves, which is all ``_canonicalize`` needs.
    """
    return {
        int(a): int(b) for a, b in dataset.canonical_ids.items() if int(a) != int(b)
    }


def _canonicalize(ids: np.ndarray, mapping: dict[int, int]) -> np.ndarray:
    if not mapping:
        return ids
    uniq, inverse = np.unique(ids, return_inverse=True)
    canon = np.array([mapping.get(int(u), int(u)) for u in uniq], dtype=ids.dtype)
    return canon[inverse].reshape(ids.shape)


def _canonical_columns(
    table: pd.DataFrame, mapping: dict[int, int], columns: tuple[str, ...]
) -> pd.DataFrame:
    """A copy of table with the given player-id columns mapped through mapping."""
    table = table.copy()
    for column in columns:
        if column in table.columns:
            table[column] = [mapping.get(value, value) for value in table[column]]
    return table


def _frame_slice(frame_idx: np.ndarray, start: int, end: int) -> tuple[int, int]:
    """Half-open row range of the rows whose frame_idx lies in [start, end]."""
    lo = int(np.searchsorted(frame_idx, start, side="left"))
    hi = int(np.searchsorted(frame_idx, end, side="right"))
    return lo, hi


def _intervals(table: pd.DataFrame, columns: tuple[str, ...]) -> np.ndarray:
    """Rows of table[columns] with every value present, as int64, sorted by startFrame."""
    if table.empty or any(c not in table.columns for c in columns):
        return np.empty((0, len(columns)), np.int64)
    sub = table[list(columns)].apply(pd.to_numeric, errors="coerce").dropna()
    sub = sub.sort_values("startFrame", kind="stable")
    return sub.to_numpy(dtype=np.int64)


def _holder_from_touches(
    frame_idx: np.ndarray, off_ids: np.ndarray, touches: pd.DataFrame
) -> np.ndarray:
    """Slot of the attacker holding the ball per row, from touches; -1 where none resolves.

    A touch whose player is not among the row's five attackers (touches often
    start before their chance, inside the previous one) resolves to -1 there.
    Later touches override earlier ones on overlap.
    """
    holder = np.full(len(frame_idx), -1, np.int8)
    for start, end, player in _intervals(touches, ("startFrame", "endFrame", "playerId")):
        lo, hi = _frame_slice(frame_idx, start, end)
        if hi <= lo:
            continue
        is_player = off_ids[lo:hi] == player
        has = is_player.any(axis=1)
        holder[lo:hi][has] = is_player[has].argmax(axis=1)
    return holder


def _matchups_from_intervals(
    frame_idx: np.ndarray, off_ids: np.ndarray, def_ids: np.ndarray, matchups: pd.DataFrame
) -> np.ndarray:
    """(N, 5) defender slot assigned to each attacker slot from the matchup intervals, or -1."""
    out = np.full((len(frame_idx), N_SIDE), -1, np.int8)
    columns = ("startFrame", "endFrame", "offPlayerId", "defPlayerId")
    for start, end, off_player, def_player in _intervals(matchups, columns):
        lo, hi = _frame_slice(frame_idx, start, end)
        if hi <= lo:
            continue
        is_off = off_ids[lo:hi] == off_player
        is_def = def_ids[lo:hi] == def_player
        both = is_off.any(axis=1) & is_def.any(axis=1)
        rows = lo + np.flatnonzero(both)
        out[rows, is_off[both].argmax(axis=1)] = is_def[both].argmax(axis=1)
    return out


# --------------------------------------------------------------------------- velocity


def velocity_runs(
    frame_idx: np.ndarray, possession_idx: np.ndarray, off_ids: np.ndarray, def_ids: np.ndarray
) -> np.ndarray:
    """Run id per row: a new run starts at every frameIdx jump, possession or lineup change."""
    n = len(frame_idx)
    breaks = np.ones(n, dtype=bool)
    if n > 1:
        breaks[1:] = (
            (np.diff(frame_idx.astype(np.int64)) != 1)
            | (possession_idx[1:] != possession_idx[:-1])
            | np.any(off_ids[1:] != off_ids[:-1], axis=1)
            | np.any(def_ids[1:] != def_ids[:-1], axis=1)
        )
    return np.cumsum(breaks) - 1


def estimate_velocity(
    xy: np.ndarray, run_id: np.ndarray, *, fps: float = FPS, v_max: float = V_MAX_FT_S
) -> np.ndarray:
    """D10 velocity, ft/s, for positions xy of shape (N, P, 2) grouped in runs.

    Within each run (rows with the same run_id, contiguous), positions are
    smoothed with a 5-frame moving average and differentiated with a centered
    difference over +-2 frames. Both windows shrink symmetrically at run edges;
    the first and last frame of a run use a one-sided difference; a run of one
    frame gets zero velocity. Vectors longer than v_max are scaled down to v_max.
    """
    xy = np.asarray(xy, dtype=np.float64)
    n = len(xy)
    if n == 0:
        return np.zeros_like(xy, dtype=np.float32)
    run_id = np.asarray(run_id)
    is_start = np.ones(n, dtype=bool)
    is_start[1:] = run_id[1:] != run_id[:-1]
    start_pos = np.flatnonzero(is_start)
    run_len = np.diff(np.append(start_pos, n))
    run_of = np.cumsum(is_start) - 1
    idx = np.arange(n)
    before = idx - start_pos[run_of]  # frames available before i within its run
    after = run_len[run_of] - 1 - before  # frames available after i within its run

    radius = np.minimum(SMOOTH_RADIUS, np.minimum(before, after))
    csum = np.zeros((n + 1, *xy.shape[1:]), dtype=np.float64)
    np.cumsum(xy, axis=0, out=csum[1:])
    width = (2 * radius + 1).reshape(-1, *([1] * (xy.ndim - 1)))
    smooth = (csum[idx + radius + 1] - csum[idx - radius]) / width

    half = np.minimum(DIFF_RADIUS, np.minimum(before, after))
    hi = idx + half
    lo = idx - half
    edge = half == 0
    hi = np.where(edge & (before == 0) & (after > 0), idx + 1, hi)
    lo = np.where(edge & (after == 0) & (before > 0), idx - 1, lo)
    span = (hi - lo).reshape(-1, *([1] * (xy.ndim - 1)))
    v = np.zeros_like(xy)
    np.divide(smooth[hi] - smooth[lo], span / fps, out=v, where=span > 0)

    magnitude = np.linalg.norm(v, axis=-1, keepdims=True)
    scale = np.where(magnitude > v_max, v_max / np.maximum(magnitude, 1e-12), 1.0)
    return (v * scale).astype(np.float32)


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


# --------------------------------------------------------------------------- build


def build_game_frames_with_stats(dataset: Dataset, game_id: int) -> tuple[GameFrames, BuildStats]:
    """Stream one game and build its GameFrames, returning the build diagnostics too."""
    t0 = time.perf_counter()
    meta = dataset.game_data(game_id)
    home_id = meta["homeTeam"]["teamId"]
    away_id = meta["awayTeam"]["teamId"]
    # Raw ids on both sides (consistent within a game), canonicalized with one mapping.
    mapping = canonical_player_ids(dataset)
    events = dataset.events(game_id, canonical=False)
    possessions, chances = events["possessions"], events["chances"]
    touches = _canonical_columns(events.get("touches", pd.DataFrame()), mapping, ("playerId",))
    matchups = _canonical_columns(
        events.get("matchups", pd.DataFrame()), mapping, ("offPlayerId", "defPlayerId")
    )

    raw, n_frames = _stream_live(dataset.tracking_path(game_id))
    n_live = raw.n

    # Canonical ids, each side sorted by id so slots are stable across frames.
    ids = _canonicalize(raw.ids, mapping)
    order = np.argsort(ids, axis=2, kind="stable")
    ids = np.take_along_axis(ids, order, axis=2)
    vals = np.take_along_axis(raw.vals, order[..., None], axis=2)

    # Frame -> chance -> possession, and what each possession says about orientation.
    chance_idx = _interval_labels(chances, raw.frame_idx)
    poss_of_chance = _possession_of_chances(chances, possessions)
    usable = _bool_column(chances["usable"])
    left = possessions["leftHoop"].to_numpy(dtype=object)
    left_known = ~pd.isna(left)
    left_hoop = _bool_column(possessions["leftHoop"])
    off_team = pd.to_numeric(possessions["offTeamId"], errors="coerce").to_numpy()
    off_is_home = off_team == home_id
    poss_ok = left_known & (off_is_home | (off_team == away_id))

    has_chance = chance_idx >= 0
    safe_chance = np.maximum(chance_idx, 0)
    possession_idx = np.where(has_chance, poss_of_chance[safe_chance], -1).astype(np.int32)
    safe_poss = np.maximum(possession_idx, 0)
    resolved = has_chance & (possession_idx >= 0) & poss_ok[safe_poss]

    # D12, attributed sequentially.
    reason = np.zeros(n_live, np.int8)
    reason[~has_chance] = 1
    reason[(reason == 0) & ~(has_chance & usable[safe_chance])] = 2
    reason[(reason == 0) & ~np.isfinite(raw.shot_clock)] = 3
    reason[(reason == 0) & ~raw.five_v_five] = 4
    reason[(reason == 0) & ~resolved] = 5
    keep = np.flatnonzero(reason == 0)

    # Attackers first, then orientation.
    vals10 = vals[keep].reshape(len(keep), 2 * N_SIDE, 5)
    ids10 = ids[keep].reshape(len(keep), 2 * N_SIDE)
    swap = ~off_is_home[safe_poss[keep]]
    vals10[swap] = vals10[swap][:, _SWAP_BLOCKS]
    ids10[swap] = ids10[swap][:, _SWAP_BLOCKS]
    xy = vals10[:, :, :2].copy()
    ball = raw.ball[keep].copy()
    flip = ~left_hoop[safe_poss[keep]]
    xy[flip] = orient(xy[flip], False)
    ball[flip, :2] = orient(ball[flip, :2], False)

    frame_idx = raw.frame_idx[keep]
    possession_idx = possession_idx[keep]
    off_ids, def_ids = ids10[:, :N_SIDE], ids10[:, N_SIDE:]
    run_id = velocity_runs(frame_idx, possession_idx, off_ids, def_ids)
    v = estimate_velocity(xy, run_id)

    holder = _holder_from_touches(frame_idx, off_ids, touches)
    from_touch = holder >= 0
    dist = np.linalg.norm(xy[:, :N_SIDE] - ball[:, None, :2], axis=-1)
    nearest = dist.argmin(axis=1)
    within = dist[np.arange(len(keep)), nearest] < HOLDER_MAX_DIST_FT
    fallback = ~from_touch & within
    holder[fallback] = nearest[fallback]

    matchup = _matchups_from_intervals(frame_idx, off_ids, def_ids, matchups)

    speed = vals10[:, :, 2]
    detected = vals10[:, :, 4] > 0
    magnitude = np.linalg.norm(v.astype(np.float64), axis=-1)
    finite = np.isfinite(speed)
    mask_det = detected & finite

    frames = GameFrames(
        game_id=int(game_id),
        frame_idx=frame_idx,
        wall_clock=raw.wall_clock[keep],
        shot_clock=raw.shot_clock[keep].astype(np.float32),
        period=raw.period[keep],
        possession_idx=possession_idx,
        chance_idx=chance_idx[keep],
        off_ids=np.ascontiguousarray(off_ids),
        def_ids=np.ascontiguousarray(def_ids),
        xy=xy.astype(np.float32),
        v=v,
        pred_error=vals10[:, :, 3].astype(np.float32),
        detected=detected,
        ball=ball.astype(np.float32),
        ball_holder=holder,
        matchup=matchup,
    )
    n_kept = len(keep)
    share = 1.0 / n_kept if n_kept else float("nan")
    no_chance = reason == 1
    stats = BuildStats(
        game_id=int(game_id),
        n_frames=n_frames,
        n_live=n_live,
        n_no_chance=int(no_chance.sum()),
        n_no_chance_clock_stopped=int((no_chance & raw.clock_stopped).sum()),
        n_unusable_chance=int((reason == 2).sum()),
        n_null_shot_clock=int((reason == 3).sum()),
        n_not_five_v_five=int((reason == 4).sum()),
        n_unresolved_possession=int((reason == 5).sum()),
        n_kept=n_kept,
        n_runs=int(run_id[-1] + 1) if n_kept else 0,
        holder_touch_share=float(from_touch.sum() * share),
        holder_fallback_share=float(fallback.sum() * share),
        holder_none_share=float((holder < 0).sum() * share),
        matchup_cell_coverage=float((matchup >= 0).mean()) if n_kept else float("nan"),
        matchup_frame_coverage=float((matchup >= 0).all(axis=1).mean()) if n_kept else float("nan"),
        n_detected_positions=int(mask_det.sum()),
        speed_pearson_detected=_pearson(magnitude[mask_det], speed[mask_det]),
        speed_pearson_all=_pearson(magnitude[finite], speed[finite]),
        build_seconds=time.perf_counter() - t0,
    )
    return frames, stats


def build_game_frames(dataset: Dataset, game_id: int) -> GameFrames:
    """Stream one game and build its GameFrames (see build_game_frames_with_stats)."""
    return build_game_frames_with_stats(dataset, game_id)[0]


# --------------------------------------------------------------------------- cache


def save_npz(frames: GameFrames, path: str | Path) -> None:
    """Write frames to an uncompressed .npz (atomically: a temp file renamed at the end)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    arrays = {name: getattr(frames, name) for name in _ROW_FIELDS}
    with open(tmp, "wb") as f:
        np.savez(
            f,
            format_version=np.int32(FORMAT_VERSION),
            game_id=np.int64(frames.game_id),
            **arrays,
        )
    os.replace(tmp, path)


def load_npz(path: str | Path) -> GameFrames:
    """Read frames written by save_npz. Raises ValueError on a stale format version."""
    with np.load(path, allow_pickle=False) as z:
        version = int(z["format_version"])
        if version != FORMAT_VERSION:
            raise ValueError(
                f"{path}: cache format {version}, expected {FORMAT_VERSION}; rebuild it"
            )
        return GameFrames(game_id=int(z["game_id"]), **{name: z[name] for name in _ROW_FIELDS})


def cache_path(cache_dir: str | Path, game_id: int) -> Path:
    return Path(cache_dir) / f"{game_id}_frames.npz"


def get_or_build(dataset: Dataset, game_id: int, cache_dir: str | Path) -> GameFrames:
    """Load ``{cache_dir}/{game_id}_frames.npz`` if it exists (and is current), else build it."""
    path = cache_path(cache_dir, game_id)
    if path.exists():
        try:
            return load_npz(path)
        except ValueError:
            pass  # stale format: rebuild below
    frames = build_game_frames(dataset, game_id)
    save_npz(frames, path)
    return frames


# --------------------------------------------------------------------------- views


def subsample(frames: GameFrames, every: int) -> GameFrames:
    """Rows whose frame_idx is a multiple of ``every`` (5 gives the 5 Hz view, D9).

    Anchored to the absolute frame index rather than to row position, so the
    same frames are selected no matter which filters ran before.
    """
    if every < 1:
        raise ValueError("every must be >= 1")
    return frames.take(np.flatnonzero(frames.frame_idx % every == 0))


def at_frames(frames: GameFrames, frame_idx: np.ndarray) -> GameFrames:
    """Rows of the requested frame indices, in the requested order.

    Requested frames absent from ``frames`` (dead, filtered by D12, or simply
    not there) are skipped, so align on the returned ``frame_idx``.
    """
    wanted = np.asarray(frame_idx, dtype=np.int64).ravel()
    n = len(frames)
    if n == 0 or wanted.size == 0:
        return frames.take(np.empty(0, np.int64))
    have = frames.frame_idx.astype(np.int64)
    order = None
    if np.any(np.diff(have) < 0):
        order = np.argsort(have, kind="stable")
        have = have[order]
    pos = np.minimum(np.searchsorted(have, wanted), n - 1)
    found = have[pos] == wanted
    rows = pos[found]
    if order is not None:
        rows = order[rows]
    return frames.take(rows)


def nearest_defenders(frames: GameFrames) -> np.ndarray:
    """(N, 5) slot of the closest defender to each attacker, by 2D distance."""
    diff = frames.xy[:, :N_SIDE, None, :] - frames.xy[:, None, N_SIDE:, :]
    return np.linalg.norm(diff, axis=-1).argmin(axis=2).astype(np.int8)


def matchup_with_fallback(frames: GameFrames) -> np.ndarray:
    """``matchup`` with every -1 replaced by the nearest defender (the D7 fallback)."""
    return np.where(frames.matchup >= 0, frames.matchup, nearest_defenders(frames)).astype(np.int8)
