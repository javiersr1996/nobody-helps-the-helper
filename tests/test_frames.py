"""Tests for scbasket.frames: per-game arrays, velocities, ball handler, matchups, cache.

The unit tests run on a variant of the synthetic dataset (``frames_root``) whose
40 tracking frames are split across two possessions with opposite ``leftHoop``,
an unusable chance, a gap between chances, two frames with a null shotClock and
one frame with only four home players, so every D12 filter and both
orientations are exercised. The stock ``synthetic_root`` (one usable chance
covering everything) is the happy path.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pytest
from conftest import (
    AWAY_PLAYER_IDS,
    AWAY_TEAM_ID,
    DEAD_FRAME_IDXS,
    GAME_ID,
    HOME_PLAYER_IDS,
    HOME_TEAM_ID,
    N_FRAMES,
    REAL_DATASET_ROOT,
    requires_real_dataset,
)

from scbasket.frames import (
    FORMAT_VERSION,
    GameFrames,
    at_frames,
    build_game_frames,
    build_game_frames_with_stats,
    estimate_velocity,
    get_or_build,
    load_npz,
    matchup_with_fallback,
    nearest_defenders,
    save_npz,
    subsample,
)
from scbasket.io import Dataset, iter_frames

# Layout of the frames_root variant (frames 5, 15, 25, 35 and 38 are dead).
NULL_SHOT_CLOCK_FRAMES = (0, 1)  # first frames of chance A, like the real feed
FOUR_HOME_PLAYERS_FRAME = 12
BALL_ON_5003_FRAMES = (16, 17, 18, 19)  # ball 0.5 ft from home player 5003
POSSESSION_0 = (0, 19)  # home attacks, leftHoop True
POSSESSION_1 = (19, 39)  # away attacks, leftHoop False (shares frame 19)
CHANCE_A = (0, 19)  # usable
CHANCE_B = (19, 29)  # not usable
CHANCE_C = (31, 37)  # usable; frames 30, 38, 39 belong to no chance
EXPECTED_KEPT_A = [2, 3, 4, 6, 7, 8, 9, 10, 11, 13, 14, 16, 17, 18, 19]
EXPECTED_KEPT_C = [31, 32, 33, 34, 36, 37]
SYNTHETIC_SPEED_FT_S = 25.0  # every synthetic player moves +1 ft per frame along x


def _game_dir(root: Path) -> Path:
    return root / "data" / "matches" / str(GAME_ID)


def _possession(idx: int, span: tuple[int, int], off: int, de: int, left_hoop: bool) -> dict:
    return {
        "id": f"possession-{GAME_ID}-1-{idx}",
        "gameId": GAME_ID,
        "period": 1,
        "startFrame": span[0],
        "endFrame": span[1],
        "offTeamId": off,
        "defTeamId": de,
        "leftHoop": left_hoop,
    }


def _chance(idx: int, span: tuple[int, int], off: int, de: int, poss: int, usable: bool) -> dict:
    return {
        "id": f"chance-{GAME_ID}-1-{idx}",
        "possessionId": f"possession-{GAME_ID}-1-{poss}",
        "gameId": GAME_ID,
        "period": 1,
        "startFrame": span[0],
        "endFrame": span[1],
        "offTeamId": off,
        "defTeamId": de,
        "usable": usable,
    }


def _touch(idx: int, chance: int, player: int, span: tuple[int, int]) -> dict:
    return {
        "id": f"touch-{GAME_ID}-1-{idx}",
        "chanceId": f"chance-{GAME_ID}-1-{chance}",
        "playerId": player,
        "startFrame": span[0],
        "endFrame": span[1],
    }


def _matchup(idx: int, chance: int, off: int, de: int, span: tuple[int, int]) -> dict:
    return {
        "id": f"matchup-{GAME_ID}-1-{idx}",
        "chanceId": f"chance-{GAME_ID}-1-{chance}",
        "startFrame": span[0],
        "endFrame": span[1],
        "offPlayerId": off,
        "defPlayerId": de,
    }


@pytest.fixture
def frames_root(synthetic_root: Path) -> Path:
    """synthetic_root with events split into two possessions and a patched tracking file."""
    events_path = _game_dir(synthetic_root) / f"{GAME_ID}_dynamic_events.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    home, away = HOME_TEAM_ID, AWAY_TEAM_ID
    events["possessions"] = [
        _possession(0, POSSESSION_0, home, away, True),
        _possession(1, POSSESSION_1, away, home, False),
    ]
    events["chances"] = [
        _chance(0, CHANCE_A, home, away, 0, True),
        _chance(1, CHANCE_B, away, home, 1, False),
        _chance(2, CHANCE_C, away, home, 1, True),
    ]
    events["touches"] = [
        _touch(0, 0, HOME_PLAYER_IDS[0], (0, 10)),
        _touch(1, 0, HOME_PLAYER_IDS[1], (11, 16)),
        _touch(2, 2, AWAY_PLAYER_IDS[0], (29, 33)),  # starts inside chance B, like real touches
        _touch(3, 2, HOME_PLAYER_IDS[0], (34, 37)),  # a defender in chance C: must not resolve
    ]
    events["matchups"] = [
        _matchup(0, 0, HOME_PLAYER_IDS[0], AWAY_PLAYER_IDS[0], (0, 9)),
        _matchup(1, 0, HOME_PLAYER_IDS[1], AWAY_PLAYER_IDS[1], (0, 19)),
        _matchup(2, 2, AWAY_PLAYER_IDS[3], HOME_PLAYER_IDS[3], (31, 37)),
    ]
    events_path.write_text(json.dumps(events), encoding="utf-8")

    tracking_path = _game_dir(synthetic_root) / f"{GAME_ID}_tracking_data.jsonl.gz"
    with gzip.open(tracking_path, "rt", encoding="utf-8") as f:
        frames = [json.loads(line) for line in f]
    for frame in frames:
        idx = frame["frameIdx"]
        if idx in NULL_SHOT_CLOCK_FRAMES:
            frame["shotClock"] = None
        if idx == FOUR_HOME_PLAYERS_FRAME:
            frame["homePlayers"] = frame["homePlayers"][:4]
        if idx in BALL_ON_5003_FRAMES:
            player = next(p for p in frame["homePlayers"] if p["playerId"] == HOME_PLAYER_IDS[2])
            frame["ball"]["xyz"] = [player["xyz"][0] + 0.5, player["xyz"][1], 4.0]
    with gzip.open(tracking_path, "wt", encoding="utf-8") as f:
        for frame in frames:
            f.write(json.dumps(frame) + "\n")
    return synthetic_root


def _raw_positions(root: Path) -> dict[int, dict[int, np.ndarray]]:
    """frameIdx -> playerId -> raw broadcast xy, straight from the tracking file."""
    out: dict[int, dict[int, np.ndarray]] = {}
    for frame in iter_frames(_game_dir(root) / f"{GAME_ID}_tracking_data.jsonl.gz"):
        out[frame["frameIdx"]] = {
            p["playerId"]: np.array(p["xyz"][:2])
            for p in (frame.get("homePlayers") or []) + (frame.get("awayPlayers") or [])
        }
    return out


def _replace_player_id(root: Path, old: int, new: int) -> None:
    """Rewrite one player's id in both the tracking and the events of the synthetic game."""
    game_dir = _game_dir(root)
    tracking_path = game_dir / f"{GAME_ID}_tracking_data.jsonl.gz"
    with gzip.open(tracking_path, "rt", encoding="utf-8") as f:
        frames = [json.loads(line) for line in f]
    for frame in frames:
        for player in (frame.get("homePlayers") or []) + (frame.get("awayPlayers") or []):
            if player["playerId"] == old:
                player["playerId"] = new
    with gzip.open(tracking_path, "wt", encoding="utf-8") as f:
        for frame in frames:
            f.write(json.dumps(frame) + "\n")
    events_path = game_dir / f"{GAME_ID}_dynamic_events.json"
    text = events_path.read_text(encoding="utf-8").replace(f": {old}", f": {new}")
    events_path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------- happy path


def test_stock_synthetic_keeps_every_live_frame_in_the_home_attacking_frame(synthetic_root):
    frames, stats = build_game_frames_with_stats(Dataset(synthetic_root), GAME_ID)

    assert stats.n_frames == N_FRAMES
    assert stats.n_live == N_FRAMES - len(DEAD_FRAME_IDXS)
    assert stats.n_kept == stats.n_live
    assert stats.n_no_chance + stats.n_unusable_chance + stats.n_null_shot_clock == 0
    assert set(frames.frame_idx.tolist()).isdisjoint(DEAD_FRAME_IDXS)
    # The stock chances carry no possessionId: the possession comes from the interval.
    assert np.all(frames.possession_idx == 0)
    assert np.all(frames.chance_idx == 0)
    assert frames.off_ids.tolist() == [sorted(HOME_PLAYER_IDS)] * len(frames)
    assert frames.def_ids.tolist() == [sorted(AWAY_PLAYER_IDS)] * len(frames)
    raw = _raw_positions(synthetic_root)
    for row, idx in enumerate(frames.frame_idx.tolist()):
        for slot, pid in enumerate(frames.off_ids[row].tolist()):
            np.testing.assert_allclose(frames.xy[row, slot], raw[idx][pid], rtol=1e-6)


def test_dtypes_and_shapes(synthetic_root):
    frames = build_game_frames(Dataset(synthetic_root), GAME_ID)
    n = len(frames)

    assert frames.frame_idx.dtype == np.int32 and frames.frame_idx.shape == (n,)
    assert frames.wall_clock.dtype == np.int64
    assert frames.shot_clock.dtype == np.float32
    assert frames.period.dtype == np.int8
    assert frames.possession_idx.dtype == np.int32 and frames.chance_idx.dtype == np.int32
    assert frames.off_ids.dtype == np.int32 and frames.off_ids.shape == (n, 5)
    assert frames.def_ids.shape == (n, 5)
    assert frames.xy.dtype == np.float32 and frames.xy.shape == (n, 10, 2)
    assert frames.v.dtype == np.float32 and frames.v.shape == (n, 10, 2)
    assert frames.pred_error.dtype == np.float32 and frames.pred_error.shape == (n, 10)
    assert frames.detected.dtype == bool and frames.detected.shape == (n, 10)
    assert frames.ball.dtype == np.float32 and frames.ball.shape == (n, 3)
    assert frames.ball_holder.dtype == np.int8 and frames.ball_holder.shape == (n,)
    assert frames.matchup.dtype == np.int8 and frames.matchup.shape == (n, 5)
    assert np.all(np.diff(frames.frame_idx) > 0)
    assert np.isfinite(frames.shot_clock).all()


# --------------------------------------------------------------------------- D12 filters


def test_d12_filters_are_attributed_in_order(frames_root):
    frames, stats = build_game_frames_with_stats(Dataset(frames_root), GAME_ID)

    assert stats.n_live == 35
    assert stats.n_no_chance == 2  # frames 30 and 39 (38 is dead)
    assert stats.n_unusable_chance == 9  # chance B: 20-24, 26-29 (19 belongs to A)
    assert stats.n_null_shot_clock == 2
    assert stats.n_not_five_v_five == 1
    assert stats.n_unresolved_possession == 0
    assert stats.n_kept == 21
    assert frames.frame_idx.tolist() == EXPECTED_KEPT_A + EXPECTED_KEPT_C
    total = (
        stats.n_no_chance + stats.n_unusable_chance + stats.n_null_shot_clock
        + stats.n_not_five_v_five + stats.n_unresolved_possession + stats.n_kept
    )
    assert total == stats.n_live


def test_shared_boundary_frame_goes_to_the_earlier_chance(frames_root):
    frames = build_game_frames(Dataset(frames_root), GAME_ID)
    row = int(np.flatnonzero(frames.frame_idx == 19)[0])

    assert frames.chance_idx[row] == 0
    assert frames.possession_idx[row] == 0
    assert frames.off_ids[row].tolist() == sorted(HOME_PLAYER_IDS)


# --------------------------------------------------------------------------- orientation


def test_orientation_follows_each_possession_left_hoop(frames_root):
    frames = build_game_frames(Dataset(frames_root), GAME_ID)
    raw = _raw_positions(frames_root)
    in_a = frames.possession_idx == 0
    in_c = frames.possession_idx == 1
    assert in_a.sum() == len(EXPECTED_KEPT_A) and in_c.sum() == len(EXPECTED_KEPT_C)

    # Possession 0: home attacks the left hoop, the broadcast frame is the attacking frame.
    assert frames.off_ids[in_a].tolist() == [sorted(HOME_PLAYER_IDS)] * int(in_a.sum())
    # Possession 1: away attacks the right hoop, everything is rotated 180 degrees.
    assert frames.off_ids[in_c].tolist() == [sorted(AWAY_PLAYER_IDS)] * int(in_c.sum())
    assert frames.def_ids[in_c].tolist() == [sorted(HOME_PLAYER_IDS)] * int(in_c.sum())
    for row in range(len(frames)):
        idx = int(frames.frame_idx[row])
        sign = 1.0 if in_a[row] else -1.0
        ids = np.concatenate([frames.off_ids[row], frames.def_ids[row]])
        for slot, pid in enumerate(ids.tolist()):
            np.testing.assert_allclose(frames.xy[row, slot], sign * raw[idx][pid], rtol=1e-6)


def test_ball_is_oriented_with_the_players_and_keeps_its_height(frames_root):
    frames = build_game_frames(Dataset(frames_root), GAME_ID)
    row = int(np.flatnonzero(frames.frame_idx == 16)[0])  # ball placed next to player 5003
    slot = frames.off_ids[row].tolist().index(HOME_PLAYER_IDS[2])
    np.testing.assert_allclose(frames.ball[row, :2], frames.xy[row, slot] + [0.5, 0.0], atol=1e-5)
    assert frames.ball[row, 2] == pytest.approx(4.0)
    # In possession 1 the (0, 0, z) ball stays at the origin but z is untouched.
    row_c = int(np.flatnonzero(frames.frame_idx == 31)[0])
    assert frames.ball[row_c, 2] > 0


# --------------------------------------------------------------------------- velocity


def test_velocity_of_straight_line_motion_is_within_one_percent(frames_root):
    frames = build_game_frames(Dataset(frames_root), GAME_ID)
    speed = np.linalg.norm(frames.v.astype(np.float64), axis=-1)

    assert np.all(np.abs(speed - SYNTHETIC_SPEED_FT_S) / SYNTHETIC_SPEED_FT_S < 0.01)
    # Direction follows the orientation: +x for possession 0, -x for possession 1.
    sign = np.where(frames.possession_idx == 0, 1.0, -1.0)
    expected_vx = np.repeat(sign[:, None] * SYNTHETIC_SPEED_FT_S, 10, axis=1)
    np.testing.assert_allclose(frames.v[:, :, 0], expected_vx, rtol=1e-4)
    np.testing.assert_allclose(frames.v[:, :, 1], np.zeros((len(frames), 10)), atol=1e-4)


def test_estimate_velocity_respects_runs_singletons_and_the_cap():
    t = np.arange(12, dtype=float)
    xy = np.zeros((12, 1, 2))
    xy[:6, 0, 0] = 2.0 * t[:6]  # run 0: +50 ft/s along x (2 ft per frame)
    xy[6:11, 0, 1] = -0.5 * t[:5]  # run 1: -12.5 ft/s along y
    xy[11, 0] = (100.0, 100.0)  # run 2: a single frame
    run_id = np.array([0] * 6 + [1] * 5 + [2])

    v = estimate_velocity(xy, run_id, v_max=30.0)

    np.testing.assert_allclose(v[:6, 0], [[30.0, 0.0]] * 6, atol=1e-5)  # capped, direction kept
    np.testing.assert_allclose(v[6:11, 0], [[0.0, -12.5]] * 5, atol=1e-5)
    np.testing.assert_allclose(v[11, 0], [0.0, 0.0])
    uncapped = estimate_velocity(xy, run_id, v_max=1e9)
    np.testing.assert_allclose(uncapped[:6, 0, 0], 50.0, atol=1e-5)


# --------------------------------------------------------------------------- ball handler


def test_ball_holder_from_touches_then_nearest_attacker_within_three_feet(frames_root):
    frames = build_game_frames(Dataset(frames_root), GAME_ID)
    by_frame = dict(zip(frames.frame_idx.tolist(), frames.ball_holder.tolist(), strict=True))
    home_slot = {pid: i for i, pid in enumerate(sorted(HOME_PLAYER_IDS))}
    away_slot = {pid: i for i, pid in enumerate(sorted(AWAY_PLAYER_IDS))}

    for idx in (2, 3, 4, 6, 7, 8, 9, 10):
        assert by_frame[idx] == home_slot[HOME_PLAYER_IDS[0]], idx  # touch 0
    for idx in (11, 13, 14, 16):
        assert by_frame[idx] == home_slot[HOME_PLAYER_IDS[1]], idx  # touch 1 beats the ball
    for idx in (17, 18, 19):
        assert by_frame[idx] == home_slot[HOME_PLAYER_IDS[2]], idx  # fallback: ball 0.5 ft away
    for idx in (31, 32, 33):
        assert by_frame[idx] == away_slot[AWAY_PLAYER_IDS[0]], idx  # touch 2
    for idx in (34, 36, 37):
        assert by_frame[idx] == -1, idx  # touch 3 is by a defender and the ball is far


def test_aliased_player_id_is_canonical_in_ids_holder_and_matchups(frames_root):
    """The synthetic alias file maps 5999 -> 5001: a game tracked under 5999 must cache 5001."""
    alias, canonical = 5999, HOME_PLAYER_IDS[0]
    _replace_player_id(frames_root, canonical, alias)
    frames = build_game_frames(Dataset(frames_root), GAME_ID)

    ids = np.concatenate([frames.off_ids, frames.def_ids], axis=1)
    assert alias not in ids
    assert (ids == canonical).any(axis=1).all()
    by_frame = dict(zip(frames.frame_idx.tolist(), frames.ball_holder.tolist(), strict=True))
    slot = sorted(HOME_PLAYER_IDS).index(canonical)
    for idx in (2, 3, 4, 6, 7, 8, 9, 10):
        assert by_frame[idx] == slot, idx  # touch 0 by the aliased player still resolves
    row = int(np.flatnonzero(frames.frame_idx == 4)[0])
    assert frames.matchup[row, slot] == sorted(AWAY_PLAYER_IDS).index(AWAY_PLAYER_IDS[0])


# --------------------------------------------------------------------------- matchups


def test_matchups_by_interval_and_the_nearest_defender_fallback(frames_root):
    frames = build_game_frames(Dataset(frames_root), GAME_ID)
    home_slot = {pid: i for i, pid in enumerate(sorted(HOME_PLAYER_IDS))}
    away_slot = {pid: i for i, pid in enumerate(sorted(AWAY_PLAYER_IDS))}

    for row, idx in enumerate(frames.frame_idx.tolist()):
        expected = [-1] * 5
        if idx <= 19:
            if idx <= 9:
                expected[home_slot[HOME_PLAYER_IDS[0]]] = away_slot[AWAY_PLAYER_IDS[0]]
            expected[home_slot[HOME_PLAYER_IDS[1]]] = away_slot[AWAY_PLAYER_IDS[1]]
        else:
            expected[away_slot[AWAY_PLAYER_IDS[3]]] = home_slot[HOME_PLAYER_IDS[3]]
        assert frames.matchup[row].tolist() == expected, idx

    nearest = nearest_defenders(frames)
    brute = np.empty_like(nearest)
    for row in range(len(frames)):
        for j in range(5):
            dists = np.linalg.norm(frames.xy[row, 5:] - frames.xy[row, j], axis=1)
            brute[row, j] = int(dists.argmin())
    assert np.array_equal(nearest, brute)
    filled = matchup_with_fallback(frames)
    assert np.all(filled >= 0)
    assigned = frames.matchup >= 0
    assert np.array_equal(filled[assigned], frames.matchup[assigned])
    assert np.array_equal(filled[~assigned], nearest[~assigned])


# --------------------------------------------------------------------------- views


def test_subsample_keeps_multiples_of_every(frames_root):
    frames = build_game_frames(Dataset(frames_root), GAME_ID)

    every_two = subsample(frames, 2)
    assert every_two.frame_idx.tolist() == [f for f in frames.frame_idx.tolist() if f % 2 == 0]
    assert subsample(frames, 5).frame_idx.tolist() == [10]
    assert len(subsample(frames, 1)) == len(frames)
    with pytest.raises(ValueError):
        subsample(frames, 0)
    # Every array is sliced consistently.
    row = int(np.flatnonzero(frames.frame_idx == 10)[0])
    five = subsample(frames, 5)
    np.testing.assert_array_equal(five.xy[0], frames.xy[row])
    np.testing.assert_array_equal(five.matchup[0], frames.matchup[row])


def test_at_frames_returns_requested_order_and_skips_missing(frames_root):
    frames = build_game_frames(Dataset(frames_root), GAME_ID)

    picked = at_frames(frames, np.array([14, 999, 2, 14, 30]))  # 999 absent, 30 filtered out
    assert picked.frame_idx.tolist() == [14, 2, 14]
    row14 = int(np.flatnonzero(frames.frame_idx == 14)[0])
    np.testing.assert_array_equal(picked.xy[0], frames.xy[row14])
    np.testing.assert_array_equal(picked.xy[2], frames.xy[row14])
    assert len(at_frames(frames, np.array([], dtype=int))) == 0
    # Works on a result that is no longer sorted.
    again = at_frames(picked, np.array([2]))
    assert again.frame_idx.tolist() == [2]


# --------------------------------------------------------------------------- cache


def test_npz_roundtrip_preserves_every_array_and_dtype(frames_root, tmp_path):
    frames = build_game_frames(Dataset(frames_root), GAME_ID)
    path = tmp_path / "cache" / f"{GAME_ID}_frames.npz"

    save_npz(frames, path)
    loaded = load_npz(path)

    assert isinstance(loaded, GameFrames)
    assert loaded.game_id == GAME_ID
    for name in vars(frames):
        if name == "game_id":
            continue
        a, b = getattr(frames, name), getattr(loaded, name)
        assert a.dtype == b.dtype, name
        np.testing.assert_array_equal(a, b, err_msg=name)
    assert not list(path.parent.glob("*.tmp"))


def test_get_or_build_writes_once_and_rejects_stale_formats(frames_root, tmp_path, monkeypatch):
    dataset = Dataset(frames_root)
    cache_dir = tmp_path / "interim"

    first = get_or_build(dataset, GAME_ID, cache_dir)
    path = cache_dir / f"{GAME_ID}_frames.npz"
    assert path.exists()

    import scbasket.frames as frames_module

    def fail(*args, **kwargs):
        raise AssertionError("the cache should have been used")

    monkeypatch.setattr(frames_module, "build_game_frames", fail)
    second = get_or_build(dataset, GAME_ID, cache_dir)
    np.testing.assert_array_equal(first.xy, second.xy)

    with np.load(path) as z:
        stale = {k: z[k] for k in z.files}
    stale["format_version"] = np.int32(FORMAT_VERSION + 1)
    np.savez(path, **stale)
    with pytest.raises(ValueError, match="cache format"):
        load_npz(path)
    monkeypatch.undo()
    rebuilt = get_or_build(dataset, GAME_ID, cache_dir)
    assert len(rebuilt) == len(first)
    with np.load(path) as z:
        assert int(z["format_version"]) == FORMAT_VERSION


# --------------------------------------------------------------------------- real data


@pytest.mark.data
@requires_real_dataset
def test_game_114086_meets_the_p05_acceptance_criteria(tmp_path):
    """P0.5 acceptance on game 114086; the real numbers are printed with -s."""
    import time

    dataset = Dataset(REAL_DATASET_ROOT)
    frames, stats = build_game_frames_with_stats(dataset, 114086)
    print(f"\n{stats}")

    assert stats.n_live == 92_188
    assert stats.n_kept == len(frames)
    total = (
        stats.n_no_chance + stats.n_unusable_chance + stats.n_null_shot_clock
        + stats.n_not_five_v_five + stats.n_unresolved_possession + stats.n_kept
    )
    assert total == stats.n_live
    ids = np.concatenate([frames.off_ids, frames.def_ids], axis=1)
    assert ids.shape[1] == 10 and (ids > 0).all()
    assert (np.sort(ids, axis=1)[:, 1:] != np.sort(ids, axis=1)[:, :-1]).all()
    assert stats.speed_pearson_detected >= 0.9, stats.speed_pearson_detected
    assert stats.build_seconds <= 180.0, stats.build_seconds

    path = tmp_path / "114086_frames.npz"
    save_npz(frames, path)
    size_mb = path.stat().st_size / 1e6
    t0 = time.perf_counter()
    loaded = load_npz(path)
    load_s = time.perf_counter() - t0
    print(f"npz {size_mb:.1f} MB, load {load_s:.2f} s, matchup coverage "
          f"{stats.matchup_cell_coverage:.1%}")
    assert size_mb <= 50.0, size_mb
    assert load_s <= 2.0, load_s
    assert len(loaded) == len(frames)
