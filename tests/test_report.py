"""The banded tables the two figures and the page are both drawn from (P7.8).

These are not tests of matplotlib or of HTML. They are tests of the one place the lift and
the P(win) curve are computed, because the figures and the page now agree only as long as
this module does what it says. Every expected value below is arithmetic done by hand.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scbasket import report


def _players(rows) -> pd.DataFrame:
    """rows: (game, half, offense, angle, rim_dist, is_winner)."""
    return pd.DataFrame({
        "game": [r[0] for r in rows],
        "half": [r[1] for r in rows],
        "offense": [r[2] for r in rows],
        "angle": [r[3] for r in rows],
        "rim_dist": [r[4] for r in rows],
        "is_winner": [r[5] for r in rows],
    })


def _written(tmp_path, rows):
    path = tmp_path / "angle_players.csv"
    _players(rows).to_csv(path, index=False)
    return report.load_players(path)


def test_only_offensive_rows_with_a_heading_are_kept_and_they_land_in_the_right_bands(tmp_path):
    kept = _written(tmp_path, [
        (1, "calibration", True, 10.0, 3.9, True),     # band 0-4, angle 0-30
        (1, "calibration", True, np.nan, 3.0, False),  # no heading: slower than the floor
        (1, "calibration", False, 10.0, 3.0, False),   # a defender
        (1, "calibration", True, 179.9, 199.0, False),  # the open-ended last bands
    ])
    assert len(kept) == 2
    assert kept["dist_slot"].tolist() == [0, len(report.DIST_LABELS) - 1]
    assert kept["angle_slot"].tolist() == [0, len(report.ANGLE_LABELS) - 1]


def test_the_lift_is_the_difference_between_two_shares_measured_in_the_same_band(tmp_path):
    # Inside 4 ft: two arriving rimward, one wins (0.5); two not, neither wins (0.0).
    players = _written(tmp_path, [
        (1, "calibration", True, 10.0, 2.0, True),
        (1, "calibration", True, 20.0, 2.0, False),
        (1, "calibration", True, 100.0, 2.0, False),
        (1, "calibration", True, 170.0, 2.0, False),
    ])
    table = report.table(report.count(players, "dist_slot", len(report.DIST_LABELS)),
                         report.lift, report.DIST_LABELS)
    assert table["band"].tolist() == ["0-4"]
    assert table.loc[0, "value"] == pytest.approx(0.5)
    assert table.loc[0, "n"] == 4


def test_a_band_with_nobody_on_one_side_of_the_heading_is_left_out_rather_than_guessed(tmp_path):
    players = _written(tmp_path, [
        (1, "calibration", True, 10.0, 2.0, True),     # 0-4: rimward only
        (1, "calibration", True, 20.0, 2.0, False),
        (1, "calibration", True, 10.0, 6.0, True),     # 4-8: both sides present
        (1, "calibration", True, 170.0, 6.0, False),
    ])
    blocks = report.count(players, "dist_slot", len(report.DIST_LABELS))
    assert np.isnan(report.lift(blocks["calibration"].sum(axis=0))[0])
    assert report.table(blocks, report.lift, report.DIST_LABELS)["band"].tolist() == ["4-8"]


def test_p_win_is_the_share_of_these_players_who_won_the_ball(tmp_path):
    players = _written(tmp_path, [
        (1, "calibration", True, 10.0, 2.0, True),
        (1, "calibration", True, 20.0, 2.0, False),
        (1, "calibration", True, 25.0, 2.0, False),
        (1, "calibration", True, 100.0, 2.0, True),
    ])
    table = report.table(report.count(players, "angle_slot", len(report.ANGLE_LABELS)),
                         report.p_win, report.ANGLE_LABELS)
    got = table.set_index("band")["value"].to_dict()
    assert got == pytest.approx({"0-30": 1 / 3, "90-120": 1.0})


def test_one_game_per_half_makes_every_resample_the_same_game_and_the_interval_collapses(tmp_path):
    """The cluster is the GAME. With one of them there is nothing to resample, and an
    interval that did not collapse would mean the bootstrap is resampling rebounds."""
    players = _written(tmp_path, [
        (1, "calibration", True, 10.0, 2.0, True),
        (1, "calibration", True, 170.0, 2.0, False),
        (2, "held out", True, 10.0, 2.0, False),
        (2, "held out", True, 170.0, 2.0, True),
    ])
    table = report.banded(players, "dist_slot", report.DIST_LABELS, report.lift,
                          np.random.default_rng(report.SEED))
    assert table["lo"].tolist() == table["value"].tolist() == table["hi"].tolist()
    assert table.set_index("half")["value"].to_dict() == {"calibration": 1.0, "held out": -1.0}


def test_the_interval_widens_when_the_games_disagree_and_holds_the_point_estimate(tmp_path):
    """Five games, one of which says something else: the interval has to contain the
    estimate and cannot be a point, or the bands on the figures mean nothing."""
    rows = []
    for game in range(1, 6):
        winner = game != 5              # four games where the rimward player wins, one not
        rows += [(game, "calibration", True, 10.0, 2.0, winner),
                 (game, "calibration", True, 170.0, 2.0, not winner)]
    table = report.banded(_written(tmp_path, rows), "dist_slot", report.DIST_LABELS,
                          report.lift, np.random.default_rng(report.SEED))
    row = table.iloc[0]
    assert row["value"] == pytest.approx(0.6)          # 0.8 rimward minus 0.2 otherwise
    assert row["lo"] < row["value"] < row["hi"]
    assert row["lo"] >= -1.0 and row["hi"] <= 1.0


def test_the_bootstrap_draws_the_same_games_for_a_given_seed(tmp_path):
    """The two committed PNGs are byte-identical run to run, which is only true while this
    is: the bands are a property of the seed, not of the machine."""
    players = _written(tmp_path, [(g, "calibration", True, a, 2.0, g % 2 == 0)
                                  for g in range(1, 6) for a in (10.0, 170.0)])
    first = report.banded(players, "dist_slot", report.DIST_LABELS, report.lift,
                          np.random.default_rng(report.SEED))
    again = report.banded(players, "dist_slot", report.DIST_LABELS, report.lift,
                          np.random.default_rng(report.SEED))
    pd.testing.assert_frame_equal(first, again)
