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
  help_sensitivity.csv  share with a helper and what he leaves, over HELP_FT x horizon
  help_by_game.csv      the headline numbers per game, never pooled away
"""

from __future__ import annotations

import argparse
from pathlib import Path

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
    flow_field,
    help_table,
    help_vectors,
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


def summarise(table: pd.DataFrame, help_ft: float, open_ft: float) -> dict:
    """The headline numbers of one table at one threshold pair."""
    ok = table[table["status"] == "ok"]
    helped = ok[ok["helper_help_move"] >= help_ft]
    left = helped.dropna(subset=["left_nearest1"])
    return {
        "n_drives": int(len(table)),
        "n_resolved": int(len(ok)),
        "share_with_helper": float((ok["helper_help_move"] >= help_ft).mean()),
        "helper_start_dist": float(helped["helper_start_dist"].median()),
        "helper_hoop_dist0": float(helped["helper_hoop_dist0"].median()),
        "helper_from_middle": float((helped["helper_origin_y"].abs() < MIDDLE_Y_FT).mean()),
        "helper_from_corner_side": float((helped["helper_origin_y"].abs() > CORNER_Y_FT).mean()),
        "left_sep0": float(left["left_sep0"].median()),
        "left_sep1": float(left["left_sep1"].median()),
        "left_nearest1": float(left["left_nearest1"].median()),
        "left_open_share": float((left["left_nearest1"] >= open_ft).mean()),
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
    vectors = pd.concat(
        [help_vectors(frames_by_game[g], drives_by_game[g]) for g in dataset.game_ids],
        ignore_index=True,
    )
    flow = flow_field(vectors)
    table.to_csv(args.out / "help_table.csv", index=False)
    vectors.to_csv(args.out / "help_vectors.csv", index=False)
    flow.to_csv(args.out / "help_flow.csv", index=False)

    print(f"drives: {len(table)}; status: {table['status'].value_counts().to_dict()}")
    head = summarise(table, HELP_FT, OPEN_FT)
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

    by_game = pd.DataFrame(
        {g: summarise(t, HELP_FT, OPEN_FT) for g, t in zip(dataset.game_ids, tables, strict=True)}
    ).T.rename_axis("game").reset_index()
    by_game.to_csv(args.out / "help_by_game.csv", index=False)
    print("\nper game: share with a helper / left open / beyond the arc")
    print(by_game[["game", "n_resolved", "share_with_helper", "left_open_share",
                   "left_beyond_arc"]].to_string(index=False))

    rows = []
    for horizon_s in SENSITIVITY_HORIZON_S:
        frames_h = int(horizon_s * FPS)
        if frames_h == HORIZON_FRAMES:
            table_h = table
        else:
            table_h = pd.concat(
                [help_table(frames_by_game[g], drives_by_game[g], horizon_frames=frames_h)
                 for g in dataset.game_ids],
                ignore_index=True,
            )
        for help_ft in SENSITIVITY_HELP_FT:
            rows.append({"horizon_s": horizon_s, "help_ft": help_ft,
                         **summarise(table_h, help_ft, OPEN_FT)})
    sensitivity = pd.DataFrame(rows)
    sensitivity.to_csv(args.out / "help_sensitivity.csv", index=False)
    print("\nsensitivity (horizon x threshold): share with helper / from the middle / "
          "from the corner side / left open / beyond the arc")
    print(sensitivity[["horizon_s", "help_ft", "share_with_helper", "helper_from_middle",
                       "helper_from_corner_side", "left_open_share", "left_beyond_arc"]]
          .to_string(index=False))

    print(f"\nflow field: {len(flow)} cells with >= 15 vectors; consistency median "
          f"{flow['consistency'].median():.2f}, max {flow['consistency'].max():.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
