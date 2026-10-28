"""The banded tables behind the two figures and the interactive page (P7.4, P7.8).

Three artefacts read the same two tables off `reports/angle_players.csv`: the lift of a
rimward heading by distance to the rim, and P(win) by heading inside a fixed distance band.
They used to be computed inside `scripts/figures.py`, which meant the page could only have
them by copying the code or by re-deriving the numbers, and a number that exists twice is a
number that will disagree with itself.

The bands are the frozen reporting bands of the record, not chosen here, and a player is
"arriving rimward" under `COMMITTED_ANGLE_DEG`, which was frozen with the finding.

Everything is a ratio of four counters per game and band, which is what makes the cluster
bootstrap cheap: resampling five GAMES only ever sums five rows of counters, so the 2000
draws are one integer index into a small array rather than 2000 rebuilds of a DataFrame.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

#: The reporting bands, in feet and in degrees, left-closed. Frozen with the finding.
DIST_EDGES = (0, 4, 8, 12, 16, 22, 200)
ANGLE_EDGES = (0, 30, 60, 90, 120, 180)
DIST_LABELS = ("0-4", "4-8", "8-12", "12-16", "16-22", "22+")
ANGLE_LABELS = ("0-30", "30-60", "60-90", "90-120", "120-180")

#: Under this heading, in degrees, the player is arriving at the rim rather than across it.
COMMITTED_ANGLE_DEG = 60.0
#: Figure 2 holds the distance inside this band and varies only the heading.
FIXED_BAND_FT = 8.0

#: Drawn in this order, calibration first, so the replication reads left to right.
HALVES = ("calibration", "held out")
N_BOOTSTRAP = 2000
SEED = 0

#: The counters every statistic below is a ratio of, per game and band.
COUNTERS = ("n", "won", "n_rimward", "won_rimward")

#: A table of counters per half: (games, bands, 4), the games in the order they are played.
Blocks = dict[str, np.ndarray]
Statistic = Callable[[np.ndarray], np.ndarray]


def load_players(path: Path) -> pd.DataFrame:
    """The offensive rows with a usable heading, banded by distance and by heading."""
    players = pd.read_csv(path)
    players = players[players["offense"] & players["angle"].notna()].copy()
    players["dist_slot"] = _slots(players["rim_dist"], DIST_EDGES)
    players["angle_slot"] = _slots(players["angle"], ANGLE_EDGES)
    return players[(players["dist_slot"] >= 0) & (players["angle_slot"] >= 0)]


def _slots(values: pd.Series, edges: tuple[int, ...]) -> pd.Series:
    """Band index per row, left-closed like the record's bands, -1 for anything outside."""
    return pd.cut(values, list(edges), right=False).cat.codes


def count(players: pd.DataFrame, slot: str, n_bands: int) -> Blocks:
    """Per half, the four counters summed per game and band.

    The game order is the order the games appear in, which is what the bootstrap resamples
    from; sorting it here would change the draws without changing anything they mean.
    """
    blocks: Blocks = {}
    for half in HALVES:
        part = players[players["half"] == half]
        games = part["game"].unique()
        block = np.zeros((len(games), n_bands, len(COUNTERS)))
        won = part["is_winner"].to_numpy(dtype=float)
        rimward = (part["angle"].to_numpy() < COMMITTED_ANGLE_DEG).astype(float)
        np.add.at(
            block,
            (pd.Categorical(part["game"], categories=games).codes, part[slot].to_numpy()),
            np.column_stack([np.ones_like(won), won, rimward, won * rimward]),
        )
        blocks[half] = block
    return blocks


def lift(counters: np.ndarray) -> np.ndarray:
    """Share won arriving rimward minus share won otherwise; nan where one side is empty."""
    n, won, n_rimward = counters[..., 0], counters[..., 1], counters[..., 2]
    won_rimward, n_other = counters[..., 3], n - n_rimward
    with np.errstate(invalid="ignore", divide="ignore"):
        both = (n_rimward > 0) & (n_other > 0)
        return np.where(both, won_rimward / n_rimward - (won - won_rimward) / n_other, np.nan)


def p_win(counters: np.ndarray) -> np.ndarray:
    """Share of these offensive players who won the rebound; nan where the band is empty."""
    n = counters[..., 0]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, counters[..., 1] / n, np.nan)


def table(blocks: Blocks, statistic: Statistic, labels: tuple[str, ...]) -> pd.DataFrame:
    """The point estimate per half and band, with the number of players behind it."""
    rows = []
    for half, block in blocks.items():
        totals = block.sum(axis=0)
        for slot, (value, n) in enumerate(zip(statistic(totals), totals[:, 0], strict=True)):
            if not np.isnan(value):
                rows.append({"half": half, "slot": slot, "band": labels[slot],
                             "value": float(value), "n": int(n)})
    return pd.DataFrame(rows)


def cluster_bootstrap(blocks: Blocks, statistic: Statistic,
                      rng: np.random.Generator) -> pd.DataFrame:
    """2.5 and 97.5 percentiles of the statistic, resampling whole GAMES within each half.

    The cluster is the game, not the rebound: rebounds inside a game are not independent and
    the claim generalises across games. Five clusters is a small number and the intervals are
    correspondingly crude. They are here to stop a band of 29 players from reading as solidly
    as one of 598, and not as a test of anything.
    """
    rows = []
    for half, block in blocks.items():
        picked = rng.choice(len(block), size=(N_BOOTSTRAP, len(block)), replace=True)
        draws = statistic(block[picked].sum(axis=1))
        # A band nobody is in is nan in every draw, and has no interval rather than a
        # warning: `table` will not have a row for it either.
        lo, hi = (np.full(block.shape[1], np.nan) for _ in range(2))
        seen = np.isfinite(draws).any(axis=0)
        if seen.any():
            lo[seen], hi[seen] = np.nanpercentile(draws[:, seen], [2.5, 97.5], axis=0)
        rows += [{"half": half, "slot": slot, "lo": lo[slot], "hi": hi[slot]}
                 for slot in range(block.shape[1])]
    return pd.DataFrame(rows).set_index(["half", "slot"])


def banded(players: pd.DataFrame, slot: str, labels: tuple[str, ...], statistic: Statistic,
           rng: np.random.Generator) -> pd.DataFrame:
    """One figure's table: the point estimate, the players behind it and its crude interval."""
    blocks = count(players, slot, len(labels))
    return table(blocks, statistic, labels).join(
        cluster_bootstrap(blocks, statistic, rng), on=["half", "slot"])


def pooled(players: pd.DataFrame, slot: str, labels: tuple[str, ...]) -> pd.DataFrame:
    """The same curve with the two halves pooled, which is the form the record quotes.

    It is monotone pooled and only the held-out half is monotone split, so the two are
    reported together everywhere and neither is ever quoted as the other.
    """
    counts = players.groupby(slot, observed=True)["is_winner"].agg(["count", "mean"])
    return pd.DataFrame({"band": [labels[s] for s in counts.index],
                         "n": counts["count"].to_numpy(),
                         "value": counts["mean"].to_numpy()})
