"""Smoke tests for scbasket.io, running entirely on the synthetic dataset.

None of these tests need the real SkillCorner dataset: see conftest.py for the
synthetic fixtures and for the mechanism future tests should use to guard any
test that does need it (@pytest.mark.data + requires_real_dataset).
"""

from __future__ import annotations

from conftest import AWAY_PLAYER_IDS, DEAD_FRAME_IDXS, GAME_ID, HOME_PLAYER_IDS, N_FRAMES

from scbasket.io import Dataset, iter_frames, load_events, load_tracking


def test_matches_and_game_ids_sorted_by_date(synthetic_dataset: Dataset) -> None:
    matches = synthetic_dataset.matches

    assert matches["date_time"].is_monotonic_increasing
    assert synthetic_dataset.game_ids == matches["id"].tolist()
    assert GAME_ID in synthetic_dataset.game_ids


def test_load_events_applies_known_fixes(synthetic_root) -> None:
    events_path = (
        synthetic_root / "data" / "matches" / str(GAME_ID) / f"{GAME_ID}_dynamic_events.json"
    )

    tables = load_events(events_path)

    passes = tables["passes"]
    assert "interceptedByDefenderId" in passes.columns
    assert "toReceiverId" not in passes.columns
    assert passes["interceptedByDefenderId"].tolist() == [
        AWAY_PLAYER_IDS[0],
        AWAY_PLAYER_IDS[1],
    ]

    shots = tables["shots"]
    assert "countsAsFga" in shots.columns
    assert bool(shots.loc[shots["fouled"], "countsAsFga"].eq(False).all())
    assert bool(shots.loc[~shots["fouled"], "countsAsFga"].eq(True).all())


def test_iter_frames_skip_dead_drops_exactly_the_dead_frames(synthetic_dataset: Dataset) -> None:
    tracking_path = synthetic_dataset.tracking_path(GAME_ID)

    all_frames = list(iter_frames(tracking_path, skip_dead=False))
    assert len(all_frames) == N_FRAMES

    live_frames = list(iter_frames(tracking_path, skip_dead=True))
    assert len(live_frames) == N_FRAMES - len(DEAD_FRAME_IDXS)

    live_idxs = {frame["frameIdx"] for frame in live_frames}
    assert live_idxs.isdisjoint(DEAD_FRAME_IDXS)


def test_load_tracking_row_count_and_isdetected_normalization(
    synthetic_dataset: Dataset,
) -> None:
    tracking_path = synthetic_dataset.tracking_path(GAME_ID)
    n_live_frames = N_FRAMES - len(DEAD_FRAME_IDXS)

    df = load_tracking(tracking_path, skip_dead=True, include_ball=True)

    expected_rows = n_live_frames * (len(HOME_PLAYER_IDS) + len(AWAY_PLAYER_IDS) + 1)
    assert len(df) == expected_rows
    assert df["isDetected"].dtype == bool

    ball_rows = df[df["side"] == "ball"]
    assert len(ball_rows) == n_live_frames
    assert set(ball_rows["isDetected"].unique()) == {True, False}

    player_rows = df[df["side"] != "ball"]
    assert len(player_rows) == n_live_frames * (len(HOME_PLAYER_IDS) + len(AWAY_PLAYER_IDS))
    assert set(player_rows["isDetected"].unique()) == {True, False}
