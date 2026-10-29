"""The wind on every drive: who comes, from where, and who is left (P8).

Usage: uv run python scripts/help_wind.py [--root DIR] [--cache DIR] [--out DIR]

For every published game it loads the frame cache (building it if missing), takes the
provider's `drives`, and measures the defence's own movement over the first second with
`scbasket.wind`. Nothing is gated: every definition is fixed in the module and the
sensitivity sweep prints its neighbours next to it.

Writes to {out}:
  help_table.csv        one row per drive (the largest mover and the man he left)
  help_vectors.csv      one row per (drive, non-matchup defender), drive frame
  help_flow.csv         the flow field, one row per cell of the drive frame
  help_field.csv        the kernel field (mean move, helper rate, kernel mass), one row per
                        grid point of the drive frame: the wind map and the page read it
  help_sensitivity.csv  share with a helper and what he leaves, over HELP_FT x horizon
  help_by_game.csv      the headline numbers per game, never pooled away
  help_base_rate.csv    per off-ball defender: where they start and how often each is the
                        helper, raw and standardised by where the ball goes from him
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.court import HOOP_X
from scbasket.frames import get_or_build
from scbasket.io import Dataset
from scbasket.wind import (
    FPS,
    HELP_FT,
    HORIZON_FRAMES,
    OPEN_FT,
    SENSITIVITY_HELP_FT,
    SENSITIVITY_HORIZON_S,
    field_grid,
    flow_field,
    help_table,
    help_vectors,
    kernel_field,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "opendata-basketball"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

#: Origin bands along the court, feet from the hoop line, for the "where from" summary.
ORIGIN_BANDS = [0.0, 8.0, 16.0, 24.0, 100.0]
MIDDLE_Y_FT = 8.0  # |y| under this is "through the middle"
CORNER_Y_FT = 18.0  # |y| over this is "the corner side"
#: The man left is "beyond the arc" when `zone_of` puts him there; by zone and not by a radial
#: distance, because the FIBA line is straight in the corners and 21.65 ft out there.
THREE_ZONES = ("corner_3", "wing_3", "top_3", "far")

#: |y| bands of a defender's start for the base rate: the middle and the corner side above, with
#: the gap between them split in two.
Y_BANDS = [0.0, MIDDLE_Y_FT, 13.0, CORNER_Y_FT, np.inf]
#: Strata the helper rate is standardised over, both set in the session probe of 2026-10-29:
#: feet from a defender's start to where the handler is at the horizon (`target_dist`), and the
#: along-court share of the way there (`target_bearing_x`, negative toward the hoop line).
TARGET_DIST_BANDS = [0.0, 8.0, 12.0, 16.0, 20.0, 25.0, 30.0, np.inf]
BEARING_BANDS = [-1.0, -0.7, -0.3, 0.3, 0.7, 1.0]
STANDARDISED_BY = {
    "none": [],
    "target_dist": ["dist_band"],
    "bearing": ["bearing_band"],
    "target_dist+bearing": ["dist_band", "bearing_band"],
}
BOOTSTRAP_DRAWS = 4000
BOOTSTRAP_SEED = 0


def helper_flags(vectors: pd.DataFrame, help_ft: float) -> pd.Series:
    """True on each drive's largest mover when he moves at least `help_ft`: `help_table`'s
    helper read off the vectors (the first one on a tie, as `max` takes it there)."""
    flags = pd.Series(False, index=vectors.index)
    flags.loc[vectors.groupby("drive_id", sort=False)["help_move"].idxmax().to_numpy()] = True
    return flags & (vectors["help_move"] >= help_ft)


def helper_rate(
    vectors: pd.DataFrame,
    group: str,
    help_ft: float,
    strata: list[str] | tuple[str, ...] = (),
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = BOOTSTRAP_SEED,
) -> pd.DataFrame:
    """Per value of `group`: how many off-ball defenders start there, how many of them are the
    helper, the rate per defender, and that rate against the one their mix of `strata` predicts.

    `expected` adds up, over the group's defenders, the pooled helper rate of the stratum each
    falls in (the overall rate when `strata` is empty), and `ratio` is helpers over expected:
    1 when the group is the helper as often as its strata alone say. Intervals are 95 % by
    bootstrap over drives (a drawn drive brings its four defenders, and the stratum rates are
    recomputed on every draw), with a fixed seed.
    """
    helper = helper_flags(vectors, help_ft).to_numpy(float)
    g_codes, g_labels = pd.factorize(vectors[group], sort=True)
    s_codes = (vectors.groupby(list(strata), observed=True, sort=False).ngroup().to_numpy()
               if strata else np.zeros(len(vectors), int))
    d_codes, d_labels = pd.factorize(vectors["drive_id"])
    n_g, n_s = len(g_labels), int(s_codes.max()) + 1

    def estimate(w: np.ndarray) -> tuple[np.ndarray, ...]:
        s_def = np.bincount(s_codes, w, n_s)
        s_rate = np.divide(np.bincount(s_codes, w * helper, n_s), s_def,
                           out=np.zeros(n_s), where=s_def > 0)
        n_def = np.bincount(g_codes, w, n_g)
        n_help = np.bincount(g_codes, w * helper, n_g)
        expected = np.bincount(g_codes, w * s_rate[s_codes], n_g)
        with np.errstate(invalid="ignore", divide="ignore"):
            return n_def, n_help, expected, n_help / n_def, n_help / expected

    n_def, n_help, expected, rate, ratio = estimate(np.ones(len(vectors)))
    rng = np.random.default_rng(seed)
    boot_rate, boot_ratio = np.empty((draws, n_g)), np.empty((draws, n_g))
    for i in range(draws):
        counts = np.bincount(rng.integers(0, len(d_labels), len(d_labels)), minlength=len(d_labels))
        *_, boot_rate[i], boot_ratio[i] = estimate(counts[d_codes].astype(float))
    rate_low, rate_high = np.nanpercentile(boot_rate, [2.5, 97.5], axis=0)
    ratio_low, ratio_high = np.nanpercentile(boot_ratio, [2.5, 97.5], axis=0)
    return pd.DataFrame({
        "group": g_labels,
        "n_defenders": n_def.astype(int),
        "defender_share": n_def / n_def.sum(),
        "n_helpers": n_help.astype(int),
        "helper_share": n_help / n_help.sum(),
        "rate": rate, "rate_low": rate_low, "rate_high": rate_high,
        "expected": expected,
        "ratio": ratio, "ratio_low": ratio_low, "ratio_high": ratio_high,
    })


def base_rate(vectors: pd.DataFrame, help_ft: float) -> pd.DataFrame:
    """`helper_rate` by |y| band and by zone, raw and under each standardisation, then raw by
    bearing band (standardising it by itself would read 1 by construction)."""
    bands = vectors.assign(
        y_band=pd.cut(vectors["origin_y"].abs(), Y_BANDS, right=False,
                      labels=[f"{a:g}-{b:g}" for a, b in zip(Y_BANDS[:-1], Y_BANDS[1:],
                                                             strict=True)]),
        dist_band=pd.cut(vectors["target_dist"], TARGET_DIST_BANDS, right=False),
        bearing_band=pd.cut(vectors["target_bearing_x"], BEARING_BANDS, include_lowest=True,
                            labels=[f"{a:g} to {b:g}" for a, b in zip(BEARING_BANDS[:-1],
                                                                       BEARING_BANDS[1:],
                                                                       strict=True)]),
    )
    parts = [
        helper_rate(bands, grouping, help_ft, strata)
        .assign(grouping=grouping, standardised_by=name)
        for grouping in ("y_band", "zone0") for name, strata in STANDARDISED_BY.items()
    ]
    parts.append(helper_rate(bands, "bearing_band", help_ft)
                 .assign(grouping="bearing_band", standardised_by="none"))
    out = pd.concat(parts, ignore_index=True)
    return out[["grouping", "standardised_by", *out.columns[:-2]]]


def summarise(table: pd.DataFrame, vectors: pd.DataFrame, help_ft: float, open_ft: float) -> dict:
    """The headline numbers of one table and its vectors at one threshold pair."""
    ok = table[table["status"] == "ok"]
    helped = ok[ok["helper_help_move"] >= help_ft]
    left = helped.dropna(subset=["left_nearest1"])
    # The base rate: the same columns for the man of the largest mover UNDER the threshold.
    comparable = ok[ok["helper_help_move"] < help_ft].dropna(subset=["left_nearest1"])
    # And the helper's: where the off-ball defenders start, and how often each one is the helper.
    is_helper = helper_flags(vectors, help_ft)
    middle = vectors["origin_y"].abs() < MIDDLE_Y_FT
    corner_side = vectors["origin_y"].abs() > CORNER_Y_FT
    # Above the ball (the spot nearer the hoop line than he is) a plain sink is help movement:
    # how many helpers stand there, and how much of their help movement runs along the court.
    helpers = vectors[is_helper]
    along = helpers["dx"] * helpers["target_bearing_x"] / helpers["help_move"]
    return {
        "n_drives": int(len(table)),
        "n_resolved": int(len(ok)),
        "share_with_helper": float((ok["helper_help_move"] >= help_ft).mean()),
        "helper_start_dist": float(helped["helper_start_dist"].median()),
        "helper_hoop_dist0": float(helped["helper_hoop_dist0"].median()),
        "helper_from_middle": float((helped["helper_origin_y"].abs() < MIDDLE_Y_FT).mean()),
        "helper_from_corner_side": float((helped["helper_origin_y"].abs() > CORNER_Y_FT).mean()),
        "defenders_from_middle": float(middle.mean()),
        "defenders_from_corner_side": float(corner_side.mean()),
        "helper_rate": float(is_helper.mean()),
        "helper_rate_middle": float(is_helper[middle].mean()),
        "helper_rate_corner_side": float(is_helper[corner_side].mean()),
        "n_defenders_corner_side": int(corner_side.sum()),
        "helper_above_ball": float((helpers["target_bearing_x"] < 0).mean()),
        "helper_along_court_share": float(along.median()),
        "left_sep0": float(left["left_sep0"].median()),
        "left_sep1": float(left["left_sep1"].median()),
        "left_nearest1": float(left["left_nearest1"].median()),
        "left_open_share": float((left["left_nearest1"] >= open_ft).mean()),
        "left_open_share_no_helper": float((comparable["left_nearest1"] >= open_ft).mean()),
        "left_open0_share": float((left["left_nearest0"] >= open_ft).mean()),
        "left_open0_share_no_helper": float((comparable["left_nearest0"] >= open_ft).mean()),
        "left_hoop1": float(left["left_hoop1"].median()),
        "left_beyond_arc": float(left["left_zone1"].isin(THREE_ZONES).mean()),
    }


def origin_bands(table: pd.DataFrame, help_ft: float) -> pd.DataFrame:
    """Where the helper starts: share per band from the hoop line, and the middle/corner split."""
    helped = table[(table["status"] == "ok") & (table["helper_help_move"] >= help_ft)]
    x = helped["helper_origin_x"] - HOOP_X
    band = pd.cut(x, ORIGIN_BANDS, right=False)
    y = helped["helper_origin_y"].abs()
    return pd.DataFrame({
        "share": band.value_counts(normalize=True, sort=False),
        "n": band.value_counts(sort=False),
        "middle_share": (y < MIDDLE_Y_FT).groupby(band, observed=False).mean(),
        "corner_side_share": (y > CORNER_Y_FT).groupby(band, observed=False).mean(),
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--root", type=Path, default=DATA)
    parser.add_argument("--cache", type=Path, default=INTERIM)
    parser.add_argument("--out", type=Path, default=REPORTS)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    dataset = Dataset(args.root)
    frames_by_game = {gid: get_or_build(dataset, gid, args.cache) for gid in dataset.game_ids}
    drives_by_game = {gid: dataset.events(gid)["drives"] for gid in dataset.game_ids}

    tables = [help_table(frames_by_game[g], drives_by_game[g]) for g in dataset.game_ids]
    table = pd.concat(tables, ignore_index=True)
    vectors_by_game = [help_vectors(frames_by_game[g], drives_by_game[g]) for g in dataset.game_ids]
    vectors = pd.concat(vectors_by_game, ignore_index=True)
    # `summarise` and `base_rate` read the helper off the vectors; it must be the table's.
    flagged = vectors[helper_flags(vectors, HELP_FT)].set_index("drive_id")["def_slot"]
    helped = table[table["has_helper"]].set_index("drive_id")["helper_def_slot"]
    if not flagged.sort_index().equals(helped.sort_index().astype(flagged.dtype)):
        raise ValueError("the helper read off the vectors is not help_table's helper")
    flow = flow_field(vectors)
    rates = base_rate(vectors, HELP_FT)
    field = kernel_field(vectors, helper_flags(vectors, HELP_FT).to_numpy(float), *field_grid())
    table.to_csv(args.out / "help_table.csv", index=False)
    vectors.to_csv(args.out / "help_vectors.csv", index=False)
    flow.to_csv(args.out / "help_flow.csv", index=False)
    field.to_csv(args.out / "help_field.csv", index=False)
    rates.to_csv(args.out / "help_base_rate.csv", index=False)

    print(f"drives: {len(table)}; status: {table['status'].value_counts().to_dict()}")
    head = summarise(table, vectors, HELP_FT, OPEN_FT)
    print(f"\nHEADLINE at {HELP_FT:.0f} ft in {HORIZON_FRAMES / FPS:.1f} s, "
          f"open at {OPEN_FT:.0f} ft")
    for key, value in head.items():
        print(f"  {key:24s} {value:.3f}" if isinstance(value, float) else f"  {key:24s} {value}")
    print("\nwhere the helper starts (feet from the hoop line):")
    print(origin_bands(table, HELP_FT).to_string())
    ok = table[table["status"] == "ok"]
    # `flip` is +1 when the handler's lateral motion in the ATTACKING frame was to +y (the
    # attacking team's left) and -1 otherwise. The drive-frame columns are mirrored by it and
    # cannot be used here: a first version of this check did, and printed 1.000 by construction.
    to_left = ok["flip"] == 1.0
    is_left, is_right = ok["provider_direction"] == "left", ok["provider_direction"] == "right"
    print(f"\nprovider `direction` vs the handler's lateral motion in the attacking frame: "
          f"left-labelled drives that moved to +y: {to_left[is_left].mean():.3f} "
          f"(n={is_left.sum()}); right-labelled drives that moved to -y: "
          f"{(~to_left)[is_right].mean():.3f} (n={is_right.sum()})")
    print("\nshare with a helper by endType:")
    print(ok.groupby("end_type")["has_helper"].agg(["mean", "size"]).to_string())
    print("\nper off-ball defender: share starting there, share of helpers, helper rate, and the "
          "rate over the one its strata predict (95 % by drive bootstrap)")
    for (grouping, by), part in rates.groupby(["grouping", "standardised_by"], sort=False):
        print(f"\n  {grouping}, standardised by {by}:")
        print(part[["group", "n_defenders", "defender_share", "n_helpers", "helper_share", "rate",
                    "rate_low", "rate_high", "ratio", "ratio_low", "ratio_high"]]
              .to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    by_game = pd.DataFrame(
        {g: summarise(t, v, HELP_FT, OPEN_FT)
         for g, t, v in zip(dataset.game_ids, tables, vectors_by_game, strict=True)}
    ).T.rename_axis("game").reset_index()
    by_game.to_csv(args.out / "help_by_game.csv", index=False)
    print("\nper game: share with a helper / left open (and with no helper) / beyond the arc")
    print(by_game[["game", "n_resolved", "share_with_helper", "left_open_share",
                   "left_open_share_no_helper", "left_beyond_arc"]].to_string(index=False))

    rows = []
    for horizon_s in SENSITIVITY_HORIZON_S:
        frames_h = int(horizon_s * FPS)
        if frames_h == HORIZON_FRAMES:
            table_h, vectors_h = table, vectors
        else:
            table_h = pd.concat(
                [help_table(frames_by_game[g], drives_by_game[g], horizon_frames=frames_h)
                 for g in dataset.game_ids],
                ignore_index=True,
            )
            vectors_h = pd.concat(
                [help_vectors(frames_by_game[g], drives_by_game[g], horizon_frames=frames_h)
                 for g in dataset.game_ids],
                ignore_index=True,
            )
        for help_ft in SENSITIVITY_HELP_FT:
            rows.append({"horizon_s": horizon_s, "help_ft": help_ft,
                         **summarise(table_h, vectors_h, help_ft, OPEN_FT)})
    sensitivity = pd.DataFrame(rows)
    sensitivity.to_csv(args.out / "help_sensitivity.csv", index=False)
    print("\nsensitivity (horizon x threshold): share with helper / from the middle / "
          "from the corner side / left open (and with no helper) / beyond the arc")
    print(sensitivity[["horizon_s", "help_ft", "share_with_helper", "helper_from_middle",
                       "helper_from_corner_side", "left_open_share",
                       "left_open_share_no_helper", "left_beyond_arc"]]
          .to_string(index=False))
    print("\nsensitivity, per off-ball defender: share starting on the corner side / helper rate "
          "overall, from the middle, from the corner side (n defenders there)")
    print(sensitivity[["horizon_s", "help_ft", "defenders_from_corner_side", "helper_rate",
                       "helper_rate_middle", "helper_rate_corner_side",
                       "n_defenders_corner_side"]].to_string(index=False))

    print(f"\nflow field: {len(flow)} cells with >= 15 vectors; consistency median "
          f"{flow['consistency'].median():.2f}, max {flow['consistency'].max():.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
