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


def pct0(x: float) -> str:
    return f"{100 * x:.0f} %"


def ft(x: float) -> str:
    return f"{x:.2f} ft"


def pct1(x: float) -> str:
    return f"{100 * x:.1f} %"


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


def hmm_agreement(df: pd.DataFrame, series: str) -> float:
    """hmm_matchups_summary.csv: the HMM's agreement with the provider, committed drives."""
    return float(one(df, section="agreement", config="frozen", group="committed",
                     series=series)["value"])


def outcome_reached(df: pd.DataFrame) -> pd.Series:
    """man_left_outcome_summary.csv: the ball reaches the man left, near help vs stays home."""
    return one(df, comparison="help_vs_reference", window="step", quantity="reached")


@dataclass(frozen=True)
class Source:
    """One number: the text before it, where it comes from and how it is printed."""

    anchor: str
    csv: str
    select: Callable[[pd.DataFrame], object]
    fmt: Callable[[object], str]
    bold: bool = True  # False: plain text, still matched and checked


def sft(x: float) -> str:
    return f"{x:+.2f} ft"


def ft1(x: float) -> str:
    return f"{x:.1f} ft"


def near(df: pd.DataFrame, measure: str, kind: str, horizon: float,
         variant: str = "primary") -> pd.Series:
    """One row of help_kinds_summary.csv: a variant (primary unless named) at a horizon, s."""
    rows = df[(df["measure"] == measure) & (df["kind"] == kind) & (df["variant"] == variant)
              & ((df["horizon"] - horizon).abs() < 1e-9)]
    assert len(rows) == 1, (measure, kind, variant, horizon)
    return rows.iloc[0]


def robust(df: pd.DataFrame, check: str, group: str = "committed") -> pd.DataFrame:
    """The rows of near_robustness.csv of one check and group at the headline horizon."""
    return df[(df["check"] == check) & (df["group"] == group)
              & ((df["horizon"] - 1.52).abs() < 1e-9)]


def rotator(df: pd.DataFrame, name: str) -> pd.Series:
    """near_rotator.csv: one designated rotator, committed group, at the headline horizon."""
    rows = df[(df["rotator"] == name) & (df["group"] == "committed")
              & ((df["horizon"] - 1.52).abs() < 1e-9)]
    assert len(rows) == 1, name
    return rows.iloc[0]


def pass_count(df: pd.DataFrame, who: str) -> int:
    return int(one(df, measure="count", who=who, group="committed")["n"])


def count(df: pd.DataFrame, kind: str, variant: str) -> int:
    rows = df[(df["measure"] == "count") & (df["kind"] == kind) & (df["variant"] == variant)]
    assert len(rows) == 1, (kind, variant)
    return int(rows["n"].iloc[0])


def ci_of(row: pd.Series) -> tuple[float, float]:
    return row["ci_low"], row["ci_high"]


def _nearest(who: str, kind: str) -> Callable[[pd.DataFrame], float]:
    return lambda d: near(d, "paired_diff", kind, 1.52)[who]


KINDS = "help_kinds_summary.csv"
COMMIT, REF = "near_committed", "near_committed_ref"

SOURCES: tuple[Source, ...] = (
    # The scope: committed near help and its reference (help_kinds_summary.csv).
    Source("There are ", KINDS,
           lambda d: (count(d, "flag", "near_committed"), count(d, "drives", "resolved")),
           lambda v: f"{v[0]} of {v[1]}"),
    Source("toward the handler (", KINDS, lambda d: count(d, "flag", "near_ref"), plain, False),
    # The claim: the committed near help's own paired difference, its bound and its scale.
    Source("of the other three is ", KINDS,
           lambda d: near(d, "paired_diff", COMMIT, 1.52)["mean"], ft),
    Source("of the other three is **-0.22 ft** (CI ", KINDS,
           lambda d: ci_of(near(d, "paired_diff", COMMIT, 1.52)), span),
    Source("the data rule out more than ", KINDS,
           lambda d: near(d, "paired_diff", COMMIT, 1.52)["ci_high"], sft),
    Source("median step toward the ball is ", KINDS,
           lambda d: near(d, "scale", COMMIT, 1.52, "helper_step")["median"], ft1, False),
    Source("At 1.0 s ", KINDS, lambda d: near(d, "paired_diff", COMMIT, 1.0)["mean"], ft, False),
    Source("At 1.0 s -0.22 ft (CI ", KINDS,
           lambda d: ci_of(near(d, "paired_diff", COMMIT, 1.0)), span, False),
    Source("at 2.0 s ", KINDS, lambda d: near(d, "paired_diff", COMMIT, 2.0)["mean"], ft, False),
    Source("at 2.0 s -0.18 ft (CI ", KINDS,
           lambda d: ci_of(near(d, "paired_diff", COMMIT, 2.0)), span, False),
    Source("the mean would read ", KINDS,
           lambda d: near(d, "scale", COMMIT, 1.52, "one_rotates")["mean"], sft),
    Source("When the nearest stays home: ", KINDS,
           lambda d: near(d, "paired_diff", REF, 1.52)["mean"], ft, False),
    Source("When the nearest stays home: -0.03 ft (CI ", KINDS,
           lambda d: ci_of(near(d, "paired_diff", REF, 1.52)), span, False),
    # 13 a2, pre-registered: the designated rotators and the pass (near_rotator.csv, _pass.csv).
    Source("the defender nearest the hoop alone reads ", "near_rotator.csv",
           lambda d: rotator(d, "R2")["mean"], sft, False),
    Source("the defender nearest the hoop alone reads +0.21 ft (CI ", "near_rotator.csv",
           lambda d: ci_of(rotator(d, "R2")), span, False),
    Source("and the one nearest the man left ", "near_rotator.csv",
           lambda d: rotator(d, "R1")["mean"], sft, False),
    Source("and the one nearest the man left -1.11 ft (CI ", "near_rotator.csv",
           lambda d: ci_of(rotator(d, "R1")), span, False),
    Source("within 1.5 s in only ", "near_pass.csv",
           lambda d: (pass_count(d, "pass_in_window"), pass_count(d, "drives")),
           lambda v: f"{v[0]} of {v[1]}"),
    # The per-drive picture: the best mover.
    Source("The absence is an average. In ", KINDS,
           _nearest("share_mover_left", COMMIT), pct0, False),
    Source("the man left, and in ", KINDS, _nearest("share_mover_placebo", COMMIT), pct0, False),
    Source("toward the comparison attackers on average (", KINDS,
           _nearest("share_mover_left", REF), pct0, False),
    Source("toward the comparison attackers on average (34 % and ", KINDS,
           _nearest("share_mover_placebo", REF), pct0, False),
    # The record and the robustness (help_kinds_summary.csv, near_sensitivity.csv,
    # near_robustness.csv).
    Source("a contrast of ", KINDS,
           lambda d: near(d, "contrast", "near_committed_endpos", 1.52, "sensitivity")["mean"],
           ft),
    Source("a contrast of **-0.63 ft** (CI ", KINDS,
           lambda d: ci_of(near(d, "contrast", "near_committed_endpos", 1.52, "sensitivity")),
           span, False),
    Source("under every check: all ", "near_sensitivity.csv",
           lambda d: len(d) if (d["reading"] == "ABSENCE").all() else -1, plain),
    Source("(CI tops ", "near_sensitivity.csv",
           lambda d: (d["ci_high"].min(), d["ci_high"].max()), span, False),
    Source("(means ", "near_robustness.csv",
           lambda d: (robust(d, "leave_one_out")["mean"].min(),
                      robust(d, "leave_one_out")["mean"].max()), span, False),
    Source("games resampled (CI ", "near_robustness.csv",
           lambda d: ci_of(robust(d, "game_cluster").iloc[0]), span, False),
    Source("in the first 1.5 s (", "near_robustness.csv",
           lambda d: robust(d, "no_pass").iloc[0]["mean"], ft, False),
    Source("every player detected (", "near_robustness.csv",
           lambda d: robust(d, "detected").iloc[0]["mean"], ft, False),
    # Long help, the stated limit.
    Source("the drive's path: ", KINDS, lambda d: count(d, "flag", "long"), plain),
    Source("toward his man ", KINDS, lambda d: near(d, "contrast", "long", 1.52)["mean"], sft,
           False),
    Source("more (CI ", KINDS, lambda d: ci_of(near(d, "contrast", "long", 1.52)), span, False),
    # The rotation after the pass (second_help_closeouts.csv).
    Source("n = ", "second_help_closeouts.csv",
           lambda d: int(one(d, helped=True, receiver_is_left=True)["n"]), plain, False),
    # The HMM cross-check of the provider's matchups (hmm_matchups_summary.csv).
    Source("agrees on the man left in ", "hmm_matchups_summary.csv",
           lambda d: hmm_agreement(d, "hmm"), pct0),
    Source("of these drives (", "hmm_matchups_summary.csv",
           lambda d: hmm_agreement(d, "hmm_1s_before"), pct0, False),
    # The outcome of the man left (man_left_outcome_summary.csv): near help vs stays home.
    Source("the ball reaches the man left in ", "man_left_outcome_summary.csv",
           lambda d: outcome_reached(d)["mean_a"], pct1),
    Source("the ball reaches the man left in **12.9 %**, against ", "man_left_outcome_summary.csv",
           lambda d: outcome_reached(d)["mean_b"], pct1),
    # The mirror (help_table.csv: provider_direction against the un-mirrored lateral sign).
    Source("direction agrees on ", "help_table.csv",
           lambda d: direction_agreement(d, "left"), pct0, False),
    Source("% (left) and ", "help_table.csv",
           lambda d: direction_agreement(d, "right"), pct0, False),
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
        want = src.fmt(src.select(csv(src.csv, reports)))
        if not src.bold:
            n = text.count(src.anchor + want)
            rows.append((n == 1, f"plain after {src.anchor!r} <- {src.csv}",
                         f"{n} places print {want!r} here, need 1"))
            continue
        hits = list(re.finditer(re.escape(src.anchor) + r"\*\*(.+?)\*\*", text))
        label = f"bold after {src.anchor!r} <- {src.csv}"
        if len(hits) != 1:
            rows.append((False, label, f"{len(hits)} bold spans follow this anchor, need 1"))
            continue
        printed = hits[0].group(1)
        claimed.add(hits[0].start(1))
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
