"""Tests for scbasket.conditional: the conditional rebound model (P7.3).

The structure is the claim here. Ten independent probabilities would not sum to one, and this
model does by construction, so the tests hold the construction: the probabilities over the
choice set, the fitter that finds the single maximum of a concave likelihood, and the
bookkeeping that keeps every rebound accounted for even when it cannot be graded.

A rebound that cannot be used is never quietly removed: it keeps its row with the reason. A
model that silently drops the awkward third of its data would look better than it is.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import GAME_ID, REAL_DATASET_ROOT, requires_real_dataset

from scbasket.conditional import (
    FALLBACK_ZONE_FT,
    FEATURES,
    FROZEN_BETA,
    choice_probabilities,
    fit_conditional_logit,
    log_likelihood,
    rebound_choice_set,
    top1_accuracy,
)
from scbasket.frames import GameFrames, get_or_build
from scbasket.io import Dataset
from scbasket.tagging import APPROACH_LEAD_FRAMES, ATTACKED_HOOP, zone_radius
from scbasket.validation import CALIBRATION_GAMES

CACHE_DIR = REAL_DATASET_ROOT.parents[1] / "interim"


def _frames(xy, v=None, frame_idx=None, off_ids=None, def_ids=None) -> GameFrames:
    """Frames carrying only what the choice set reads: positions, velocities and ids."""
    xy = np.asarray(xy, dtype=np.float32)
    n = len(xy)
    frame_idx = np.arange(n, dtype=np.int32) if frame_idx is None else np.asarray(frame_idx,
                                                                                 np.int32)
    ids = lambda first, given: np.broadcast_to(  # noqa: E731
        np.asarray(np.arange(first, first + 5) if given is None else given, np.int32), (n, 5)
    ).astype(np.int32)
    return GameFrames(
        game_id=GAME_ID,
        frame_idx=frame_idx,
        wall_clock=frame_idx.astype(np.int64) * 40,
        shot_clock=np.full(n, 12.0, np.float32),
        period=np.ones(n, np.int8),
        possession_idx=np.zeros(n, np.int32),
        chance_idx=np.zeros(n, np.int32),
        off_ids=ids(5001, off_ids),
        def_ids=ids(6001, def_ids),
        xy=xy,
        v=np.zeros((n, 10, 2), np.float32) if v is None
        else np.asarray(v, np.float32).reshape(n, 10, 2),
        pred_error=np.ones((n, 10), np.float32),
        detected=np.ones((n, 10), bool),
        ball=np.zeros((n, 3), np.float32),
        ball_holder=np.zeros(n, np.int8),
        matchup=np.full((n, 5), -1, np.int8),
    )


def _at_rim_distance(feet: float) -> list[float]:
    return [float(ATTACKED_HOOP[0] + feet), 0.0]


def _rebounds(rows) -> pd.DataFrame:
    """rows: (id, shotId, frame, rebounderId, defensive)."""
    return pd.DataFrame(rows, columns=["id", "shotId", "frame", "rebounderId", "defensive"])


def _shots(rows) -> pd.DataFrame:
    """rows: (id, distance from the rim in feet or None)."""
    return pd.DataFrame({
        "id": [r[0] for r in rows],
        "location": [None if r[1] is None else _at_rim_distance(r[1]) for r in rows],
    })


# ------------------------------------------------------------------- the structure itself


def test_the_ten_probabilities_sum_to_one_for_every_rebound():
    """Not a property to check afterwards: it is the reason the model has this shape."""
    rng = np.random.default_rng(0)
    X = rng.normal(size=(50, 10, len(FEATURES)))
    p = choice_probabilities(X, FROZEN_BETA)
    assert p.shape == (50, 10)
    assert p.sum(axis=1) == pytest.approx(np.ones(50))
    assert (p > 0).all()


def test_a_model_that_knows_nothing_spreads_the_board_evenly_over_the_ten():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(20, 10, len(FEATURES)))
    y = rng.integers(0, 10, size=20)
    zero = np.zeros(len(FEATURES))
    assert choice_probabilities(X, zero) == pytest.approx(np.full((20, 10), 0.1))
    assert log_likelihood(X, y, zero) == pytest.approx(np.log(0.1))


def test_a_huge_score_does_not_overflow_into_nan():
    """The scores are shifted before exponentiating, which is the only reason this holds."""
    X = np.zeros((1, 10, len(FEATURES)))
    X[0, 3, 0] = 5000.0
    p = choice_probabilities(X, [1.0, 0, 0, 0, 0])
    assert np.isfinite(p).all()
    assert p[0, 3] == pytest.approx(1.0)


def test_being_nearer_the_rim_raises_a_players_share_and_lowers_everyone_elses():
    near = np.zeros((1, 10, len(FEATURES)))
    near[0, :, 0] = 1.0
    far = near.copy()
    far[0, 2, 0] = 2.0  # player 2 is now a zone-width further out
    p_near = choice_probabilities(near, FROZEN_BETA)[0]
    p_far = choice_probabilities(far, FROZEN_BETA)[0]
    assert p_far[2] < p_near[2]
    assert (np.delete(p_far, 2) > np.delete(p_near, 2)).all()


# ----------------------------------------------------------------------------- the fitter


def test_the_fitter_recovers_the_coefficients_it_was_given():
    """A conditional logit generated from a known beta must come back as that beta."""
    rng = np.random.default_rng(7)
    truth = np.array([-0.9, 0.7, 0.1, 0.3, -0.5])
    X = rng.normal(size=(6000, 10, len(FEATURES)))
    p = choice_probabilities(X, truth)
    y = np.array([rng.choice(10, p=row) for row in p])
    assert fit_conditional_logit(X, y) == pytest.approx(truth, abs=0.08)


def test_the_fit_beats_knowing_nothing_on_its_own_data():
    rng = np.random.default_rng(8)
    X = rng.normal(size=(500, 10, len(FEATURES)))
    y = np.array([rng.choice(10, p=row) for row in choice_probabilities(X, FROZEN_BETA)])
    beta = fit_conditional_logit(X, y)
    assert log_likelihood(X, y, beta) > log_likelihood(X, y, np.zeros(len(FEATURES)))


def test_a_feature_that_is_constant_within_every_choice_set_is_refused_by_name():
    """The softmax subtracts it away, so it cannot be identified and the Hessian is singular."""
    rng = np.random.default_rng(9)
    X = rng.normal(size=(100, 10, len(FEATURES)))
    X[:, :, 2] = 4.0  # the same speed for all ten, every time
    y = rng.integers(0, 10, size=100)
    with pytest.raises(ValueError, match="speed"):
        fit_conditional_logit(X, y)


def test_top1_counts_the_rebounds_whose_winner_the_model_ranks_first():
    X = np.zeros((2, 10, len(FEATURES)))
    X[0, 4, 0] = -1.0  # player 4 is by far the nearest on the first rebound
    X[1, 7, 0] = -1.0
    assert top1_accuracy(X, np.array([4, 7]), FROZEN_BETA) == pytest.approx(1.0)
    assert top1_accuracy(X, np.array([4, 0]), FROZEN_BETA) == pytest.approx(0.5)


# -------------------------------------------------------------------------- the choice set


def test_the_features_are_read_half_a_second_before_the_ball_is_won():
    """The rebound frame itself is the ball being secured; the approach is what is modelled."""
    xy = np.zeros((2, 10, 2), np.float32)
    xy[0, 3] = _at_rim_distance(4.0)    # at the lead frame, player 3 is 4 ft out
    xy[1, 3] = _at_rim_distance(40.0)   # by the rebound frame they are 40 ft away
    frames = _frames(xy, frame_idx=[100, 100 + APPROACH_LEAD_FRAMES])
    X, y, rows = rebound_choice_set(
        frames,
        _rebounds([("r1", "s1", 100 + APPROACH_LEAD_FRAMES, 5004, True)]),
        _shots([("s1", 20.0)]),
    )
    assert len(y) == 1 and y[0] == 3
    assert X[0, 3, 0] == pytest.approx(4.0 / zone_radius(20.0), abs=1e-4)


def test_the_distance_is_scaled_by_the_zone_that_shot_earned():
    """P7.2 consumed: six feet out is a different thing on a layup and on a three."""
    xy = np.zeros((2, 10, 2), np.float32)
    xy[:, 0] = _at_rim_distance(6.0)
    frames = _frames(xy, frame_idx=[100, 200])
    X, _, _ = rebound_choice_set(
        frames,
        _rebounds([("r1", "s1", 100 + APPROACH_LEAD_FRAMES, 5001, True),
                   ("r2", "s2", 200 + APPROACH_LEAD_FRAMES, 5001, True)]),
        _shots([("s1", 2.0), ("s2", 25.0)]),
    )
    assert X[0, 0, 0] == pytest.approx(6.0 / zone_radius(2.0), abs=1e-4)
    assert X[1, 0, 0] == pytest.approx(6.0 / zone_radius(25.0), abs=1e-4)
    assert X[0, 0, 0] > X[1, 0, 0], "the same spot is deeper inside the zone of a three"


def test_a_shot_with_no_location_falls_back_to_the_constant_zone():
    """Dropping the rebound instead would let a missing shot location decide who was placed."""
    xy = np.zeros((1, 10, 2), np.float32)
    xy[0, 0] = _at_rim_distance(4.0)
    frames = _frames(xy, frame_idx=[100])
    X, _, rows = rebound_choice_set(
        frames,
        _rebounds([("r1", "s1", 100 + APPROACH_LEAD_FRAMES, 5001, True)]),
        _shots([("s1", None)]),
    )
    assert X[0, 0, 0] == pytest.approx(4.0 / FALLBACK_ZONE_FT, abs=1e-4)
    assert np.isnan(rows.loc[0, "shot_dist"])


def test_a_player_below_the_speed_floor_keeps_their_place_with_no_heading_flagged():
    """Dropping them would break the one thing the structure guarantees."""
    xy = np.zeros((1, 10, 2), np.float32)
    v = np.zeros((1, 10, 2), np.float32)
    v[0, 0] = (-6.0, 0.0)  # driving at the rim
    v[0, 1] = (-0.5, 0.0)  # barely moving, so no usable heading
    frames = _frames(xy, v=v, frame_idx=[100])
    X, _, _ = rebound_choice_set(
        frames,
        _rebounds([("r1", "s1", 100 + APPROACH_LEAD_FRAMES, 5001, True)]),
        _shots([("s1", 10.0)]),
    )
    rimward, no_heading = FEATURES.index("rimward"), FEATURES.index("no_heading")
    assert X[0, 0, rimward] == pytest.approx(1.0, abs=1e-3)
    assert X[0, 0, no_heading] == 0.0
    assert X[0, 1, rimward] == 0.0
    assert X[0, 1, no_heading] == 1.0


def test_the_first_five_slots_are_the_attacking_team():
    frames = _frames(np.zeros((1, 10, 2), np.float32), frame_idx=[100])
    X, _, _ = rebound_choice_set(
        frames,
        _rebounds([("r1", "s1", 100 + APPROACH_LEAD_FRAMES, 5001, True)]),
        _shots([("s1", 10.0)]),
    )
    offense = FEATURES.index("offense")
    assert X[0, :, offense].tolist() == [1.0] * 5 + [0.0] * 5


def test_every_rebound_keeps_a_row_and_the_ones_that_cannot_be_graded_say_why():
    frames = _frames(np.zeros((1, 10, 2), np.float32), frame_idx=[100])
    lead = 100 + APPROACH_LEAD_FRAMES
    X, y, rows = rebound_choice_set(
        frames,
        _rebounds([
            ("r1", "s1", lead, 5001, True),      # graded
            ("r2", "s1", 9999, 5001, True),      # no frame at the lead
            ("r3", "s1", lead, np.nan, True),    # the provider attributes it to nobody
            ("r4", "s1", lead, 7777, True),      # the rebounder is not one of the ten
        ]),
        _shots([("s1", 10.0)]),
    )
    assert len(rows) == 4 and len(y) == 1
    assert rows["drop_reason"].tolist() == [
        None, "no frame at the lead", "no rebounder", "winner not on court"]
    assert rows.loc[0, "winner_slot"] == 0
    assert rows["winner_slot"].isna().sum() == 3


def test_an_empty_rebound_table_produces_an_empty_choice_set():
    frames = _frames(np.zeros((1, 10, 2), np.float32), frame_idx=[100])
    X, y, rows = rebound_choice_set(frames, _rebounds([]), _shots([("s1", 10.0)]))
    assert X.shape == (0, 10, len(FEATURES))
    assert len(y) == 0 and len(rows) == 0


def test_the_feature_order_is_the_one_the_frozen_coefficients_were_fitted_in():
    """The coefficients are read by position, so a silent reordering would invert the model."""
    assert FEATURES == ("zone_ratio", "rimward", "speed", "no_heading", "offense")
    assert len(FROZEN_BETA) == len(FEATURES)


# ------------------------------------------------------------------------------ the real data


@pytest.mark.data
@requires_real_dataset
def test_the_model_grades_a_real_calibration_game_and_the_frozen_fit_reproduces():
    """Calibration only. The held-out half is the script's business, read once after the freeze."""
    dataset = Dataset(REAL_DATASET_ROOT)
    parts = []
    for game_id in CALIBRATION_GAMES:
        frames = get_or_build(dataset, game_id, CACHE_DIR)
        events = dataset.events(game_id)
        parts.append(rebound_choice_set(frames, events["rebounds"], events["shots"]))
    X = np.concatenate([p[0] for p in parts])
    y = np.concatenate([p[1] for p in parts])
    rows = pd.concat([p[2] for p in parts], ignore_index=True)

    assert len(rows) == 409 and len(y) == 324
    assert rows["drop_reason"].value_counts()["no frame at the lead"] == 44
    assert rows["drop_reason"].value_counts()["no rebounder"] == 41

    assert fit_conditional_logit(X, y) == pytest.approx(np.array(FROZEN_BETA), abs=0.001)
    assert log_likelihood(X, y, FROZEN_BETA) == pytest.approx(-1.8583, abs=0.0005)
    assert top1_accuracy(X, y, FROZEN_BETA) == pytest.approx(0.306, abs=0.005)
