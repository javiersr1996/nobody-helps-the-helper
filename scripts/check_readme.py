"""C2: guard the root README.md of the entry.

Usage: uv run python scripts/check_readme.py [README.md]

Three checks, one line each, exit 0 if all pass and 1 otherwise:

  words    at most 1000. A word is a whitespace-separated token of the prose left after
           removing fenced code blocks, HTML comments and the URL of every link and image
           (`[text](url)` keeps `[text]`).
  images   exactly two images, the two figures in order, and both files exist.
  bold     every bold span (`**...**`) is a number the table SOURCES below maps to a CSV.
           Each entry names the text that must stand right before the bold span (its
           anchor), the CSV, a selector that picks the value from it and a formatter. The
           check recomputes the printed string from the CSV and fails when the README prints
           something else, when an entry finds no bold span, and when a bold span matches
           no entry. A bold number with no source is a failure, not a skip.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
MAX_WORDS = 1000
FIGURES = (
    "reports/figures/wind_figure_1_one_drive.png",
    "reports/figures/wind_figure_2_who_covers.png",
)
HEADLINE = 38  # frames: 1.52 s, the headline horizon (decision D4)


def pct1(x: float) -> str:
    return f"{100 * x:.1f} %"


def pct0(x: float) -> str:
    return f"{100 * x:.0f} %"


def ft(x: float) -> str:
    return f"{x:.2f} ft"


def span(pair: tuple[float, float]) -> str:
    return f"{pair[0]:+.2f} to {pair[1]:+.2f}"


def plain(x: object) -> str:
    return str(x)


def csv(name: str, reports: Path = REPORTS) -> pd.DataFrame:
    return pd.read_csv(reports / name)


def resolved(t: pd.DataFrame) -> pd.DataFrame:
    return t[t["status"] == "ok"]


def is_true(col: pd.Series) -> pd.Series:
    return col.astype(str) == "True"


def summary(df: pd.DataFrame, helped: bool) -> pd.Series:
    rows = df[(df["horizon"] == HEADLINE) & (is_true(df["helped"]) == helped)]
    assert len(rows) == 1
    return rows.iloc[0]


def one(df: pd.DataFrame, **where: object) -> pd.Series:
    rows = df
    for col, val in where.items():
        rows = rows[rows[col] == val]
    assert len(rows) == 1, where
    return rows.iloc[0]


def direction_agreement(t: pd.DataFrame, label: str) -> float:
    """Share of drives the provider labels `label` whose un-mirrored lateral sign agrees."""
    ok = resolved(t)
    rows = ok[ok["provider_direction"] == label]
    return float(((rows["provider_direction"] == "left") == (rows["flip"] == 1)).mean())


@dataclass(frozen=True)
class Source:
    """One bold number: the text before it, where it comes from and how it is printed."""

    anchor: str
    csv: str
    select: Callable[[pd.DataFrame], object]
    fmt: Callable[[object], str]


def _helped_games(df: pd.DataFrame, col: str) -> str:
    rows = df[(df["horizon"] == HEADLINE) & is_true(df["helped"])]
    return f"{int((rows[col] < 0).sum())} of {len(rows)}"


def _excludes_zero(df: pd.DataFrame) -> str:
    out = (df["ci_low"] > 0) | (df["ci_high"] < 0)
    return f"{int(out.sum())} of {len(df)}"


def _y_band(df: pd.DataFrame, col: str) -> object:
    return one(df, grouping="y_band", standardised_by="none", group="18-inf")[col]


def _s2_contrast(df: pd.DataFrame) -> pd.Series:
    """The contrast row of the corroborated subset S2 at the headline horizon."""
    rows = df[(df["subset"] == "S2") & (df["series"] == "contrast")
              & (df["horizon_s"].round(2) == 1.52)]
    assert len(rows) == 1
    return rows.iloc[0]


def near(df: pd.DataFrame, measure: str, kind: str, horizon: float) -> pd.Series:
    """One row of help_kinds_summary.csv: the primary variant at a horizon in seconds."""
    rows = df[(df["measure"] == measure) & (df["kind"] == kind) & (df["variant"] == "primary")
              & ((df["horizon"] - horizon).abs() < 1e-9)]
    assert len(rows) == 1, (measure, kind, horizon)
    return rows.iloc[0]


def count(df: pd.DataFrame, kind: str, variant: str) -> int:
    rows = df[(df["measure"] == "count") & (df["kind"] == kind) & (df["variant"] == variant)]
    assert len(rows) == 1, (kind, variant)
    return int(rows["n"].iloc[0])


def ci_of(row: pd.Series) -> tuple[float, float]:
    return row["ci_low"], row["ci_high"]


def _scene0_clearance(df: pd.DataFrame) -> float:
    """The headline clearance of the drive figure 1 draws (the first scene of the JSON)."""
    first = json.loads((REPORTS / "wind_scenes.json").read_text(encoding="utf-8"))
    return one(df, drive_id=first["scenes"][0]["drive_id"])[f"left_clear_{HEADLINE}"]


def _nearest(who: str, kind: str) -> Callable[[pd.DataFrame], float]:
    return lambda d: near(d, "paired_diff", kind, 1.52)[who]


KINDS = "help_kinds_summary.csv"
COMMIT, REF = "near_committed", "near_committed_ref"

SOURCES: tuple[Source, ...] = (
    # The scope: committed near help and its reference (help_kinds_summary.csv).
    Source("There are ", KINDS,
           lambda d: (count(d, "flag", "near_committed"), count(d, "drives", "resolved")),
           lambda v: f"{v[0]} of {v[1]}"),
    Source("toward the handler (", KINDS, lambda d: count(d, "flag", "near_ref"), plain),
    Source("the man left is ", "near_committed_drives.csv", _scene0_clearance,
           lambda v: f"{v:.1f} ft"),
    Source("defenders is ", KINDS, lambda d: near(d, "paired_diff", COMMIT, 1.52)["mean"], ft),
    Source("defenders is **-0.66 ft** (CI ", KINDS,
           lambda d: ci_of(near(d, "paired_diff", COMMIT, 1.52)), span),
    Source("stays home it reads ", KINDS, lambda d: near(d, "paired_diff", REF, 1.52)["mean"], ft),
    Source("stays home it reads **-0.03 ft** (CI ", KINDS,
           lambda d: ci_of(near(d, "paired_diff", REF, 1.52)), span),
    Source("Committed minus reference is ", KINDS,
           lambda d: near(d, "contrast", COMMIT, 1.52)["mean"], ft),
    Source("Committed minus reference is **-0.63 ft** (CI ", KINDS,
           lambda d: ci_of(near(d, "contrast", COMMIT, 1.52)), span),
    Source("At 1.0 s the contrast is ", KINDS,
           lambda d: near(d, "contrast", COMMIT, 1.0)["mean"], ft),
    Source("At 1.0 s the contrast is **-0.40 ft** (CI ", KINDS,
           lambda d: ci_of(near(d, "contrast", COMMIT, 1.0)), span),
    Source("and at 2.0 s ", KINDS, lambda d: near(d, "contrast", COMMIT, 2.0)["mean"], ft),
    Source("and at 2.0 s **-0.89 ft** (CI ", KINDS,
           lambda d: ci_of(near(d, "contrast", COMMIT, 2.0)), span),
    # Who is nearest to the man left at 1.5 s (committed, then the reference).
    Source("the helper in ", KINDS, _nearest("nearest_helper", COMMIT), pct0),
    Source("of these drives (", KINDS, _nearest("nearest_helper", REF), pct0),
    Source("the ball handler's defender in ", KINDS, _nearest("nearest_handler_def", COMMIT), pct0),
    Source("one of the other three in ", KINDS, _nearest("nearest_third", COMMIT), pct0),
    Source("one of the other three in **18 %** (", KINDS, _nearest("nearest_third", REF), pct0),
    # Long help, the stated limit.
    Source("resolved drives, ", KINDS, lambda d: count(d, "flag", "long"), plain),
    # The pooled helper (help_table.csv, second_help_contrast.csv, help_base_rate.csv).
    Source("appears in ", "help_table.csv",
           lambda d: is_true(resolved(d)["has_helper"]).mean(), pct1),
    Source("resolved drives (", "help_table.csv",
           lambda d: (int(is_true(resolved(d)["has_helper"]).sum()), len(resolved(d))),
           lambda v: f"{v[0]} of {v[1]}"),
    Source("with no such helper, the same contrast at 1.5 s is ", "second_help_contrast.csv",
           lambda d: one(d, horizon=HEADLINE)["contrast_mean"], ft),
    Source("with no such helper, the same contrast at 1.5 s is **-0.16 ft** (CI ",
           "second_help_contrast.csv",
           lambda d: (one(d, horizon=HEADLINE)["contrast_ci_low"],
                      one(d, horizon=HEADLINE)["contrast_ci_high"]), span),
    Source("only ", "help_base_rate.csv", lambda d: _y_band(d, "defender_share"), pct1),
    Source("off-ball defenders (", "help_base_rate.csv",
           lambda d: (
               int(_y_band(d, "n_defenders")),
               int(d[(d["grouping"] == "y_band") & (d["standardised_by"] == "none")]
                   ["n_defenders"].sum()),
           ),
           lambda v: f"{v[0]} of {v[1]:,}"),
    Source("where it goes: ", "help_sensitivity.csv",
           lambda d: one(d, horizon_s=1.0, help_ft=4.0)["helper_above_ball"], pct0),
    # The pass and the X-out of the pooled helper (second_help_pass.csv, _closeouts.csv).
    Source("follows in ", "second_help_pass.csv",
           lambda d: (int(one(d, helped=True)["n_first_pass"]),
                      int(one(d, helped=True)["n_drives"])),
           lambda v: f"{v[0]} of {v[1]}"),
    Source("helped drives; ", "second_help_pass.csv",
           lambda d: int(one(d, helped=True)["n_to_left"]), plain),
    Source("of them (", "second_help_pass.csv",
           lambda d: one(d, helped=True)["share_to_left"], pct1),
    Source("n = ", "second_help_closeouts.csv",
           lambda d: int(one(d, helped=True, receiver_is_left=True)["n"]), plain),
    # The provider's matchups (matchup_coherence.csv).
    Source("is the nearest defender in ", "matchup_coherence.csv",
           lambda d: one(d, metric="assigned defender is the nearest"),
           lambda r: f"{r['n']} of {r['of']}"),
    # The mirror (help_table.csv: provider_direction against the un-mirrored lateral sign).
    Source("agrees with it on ", "help_table.csv",
           lambda d: direction_agreement(d, "left"), pct0),
    Source("left-labelled and ", "help_table.csv",
           lambda d: direction_agreement(d, "right"), pct0),
)

BOLD = re.compile(r"\*\*(.+?)\*\*")


def prose(text: str) -> str:
    """The text the word count sees: no code blocks, HTML comments or link/image URLs."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    return re.sub(r"\]\([^)]*\)", "]", text)


def body(text: str) -> str:
    """The README without fenced code blocks, where bold spans are looked for."""
    return re.sub(r"```.*?```", " ", text, flags=re.S)


def check_words(text: str) -> tuple[bool, str]:
    n = len(prose(text).split())
    return n <= MAX_WORDS, f"{n} words, limit {MAX_WORDS}"


def check_images(text: str, root: Path) -> tuple[bool, str]:
    paths = re.findall(r"!\[[^\]]*\]\(([^)]*)\)", body(text))
    ok = tuple(paths) == FIGURES and all((root / p).is_file() for p in paths)
    return ok, f"{len(paths)} images: {', '.join(paths) or 'none'}"


def check_bold(text: str, reports: Path) -> list[tuple[bool, str, str]]:
    """One row per source, then one per bold span no source claimed."""
    text = body(text)
    rows: list[tuple[bool, str, str]] = []
    claimed: set[int] = set()
    for src in SOURCES:
        hits = list(re.finditer(re.escape(src.anchor) + r"\*\*(.+?)\*\*", text))
        label = f"bold after {src.anchor!r} <- {src.csv}"
        if len(hits) != 1:
            rows.append((False, label, f"{len(hits)} bold spans follow this anchor, need 1"))
            continue
        printed = hits[0].group(1)
        claimed.add(hits[0].start(1))
        want = src.fmt(src.select(csv(src.csv, reports)))
        rows.append((printed == want, label, f"README {printed!r}, CSV {want!r}"))
    for m in BOLD.finditer(text):
        if m.start(1) not in claimed:
            rows.append((False, f"bold {m.group(1)!r}", "no source maps it"))
    return rows


def run(readme: Path, root: Path = ROOT) -> list[tuple[bool, str, str]]:
    text = readme.read_text(encoding="utf-8")
    words_ok, words_detail = check_words(text)
    images_ok, images_detail = check_images(text, root)
    rows = [(words_ok, "words", words_detail), (images_ok, "images", images_detail)]
    rows.extend(check_bold(text, root / "reports"))
    return rows


def main(argv: list[str]) -> int:
    readme = Path(argv[1]) if len(argv) > 1 else ROOT / "README.md"
    rows = run(readme)
    for ok, name, detail in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  [{detail}]")
    n_fail = sum(not r[0] for r in rows)
    print(f"{len(rows) - n_fail} passed, {n_fail} failed")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
