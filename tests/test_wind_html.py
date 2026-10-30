"""Tests for scripts/wind_html.py: the page's payload equals the reports it names, and the build
refuses, rather than writes, a page whose numbers disagree with their sources (B4).

Each refusal test spoils one source file in a copy of `reports/` and expects the guard that
watches it to fire: a guard no mutation can trip has checked nothing (lesson 4).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from wind_html import (  # noqa: E402
    SOURCES,
    TEMPLATE,
    Refused,
    assemble,
    inlined_block,
    payload,
    players,
    prove_loads,
    vendored,
)
from wind_scenes import paired_means  # noqa: E402

REPORTS = ROOT / "reports"
VENDOR = ROOT / "vendor" / "three"
PLAYERS = ROOT / "vendor" / "players"
#: B4's acceptance: no number with a decimal point and a unit typed in the template.
TYPED = re.compile(r"[0-9]+\.[0-9]+ ?(%|ft)")


@pytest.fixture(scope="module")
def built() -> dict:
    return payload(REPORTS)


@pytest.fixture
def reports(tmp_path: Path) -> Path:
    """A private copy of every file the page is built from, free to spoil."""
    out = tmp_path / "reports"
    out.mkdir()
    for name in SOURCES:
        shutil.copy(REPORTS / name, out / name)
    return out


def _scene0() -> dict:
    return json.loads((REPORTS / "wind_scenes.json").read_text(encoding="utf-8"))["scenes"][0]


def test_the_payload_rows_are_the_csv_rows(built):
    summary = pd.read_csv(REPORTS / "second_help_summary.csv")
    for row in built["summary"]:
        want = summary[(summary["horizon"] == row["horizon"])
                       & (summary["helped"] == row["helped"])]
        assert len(want) == 1
        for column in ("nearest_helper", "left_open_share", "mean_diff", "ci_high", "n_drives"):
            assert row[column] == pytest.approx(want.iloc[0][column], abs=1e-12)
    contrast = pd.read_csv(REPORTS / "second_help_contrast.csv")
    assert [r["contrast_ci_high"] for r in built["contrast"]] == pytest.approx(
        contrast["contrast_ci_high"].tolist(), abs=1e-12)
    passes = pd.read_csv(REPORTS / "second_help_pass.csv")
    assert built["pass"]["n_to_left"] == passes[passes["helped"]].iloc[0]["n_to_left"]
    closeouts = pd.read_csv(REPORTS / "second_help_closeouts.csv")
    landed = closeouts[closeouts["helped"] & closeouts["receiver_is_left"]].iloc[0]
    assert built["closeouts"]["n"] == landed["n"]
    league = pd.read_csv(REPORTS / "help_sensitivity.csv")
    row = league[(league["horizon_s"] == 1.0) & (league["help_ft"] == 4.0)].iloc[0]
    assert built["league"]["share_with_helper"] == pytest.approx(row["share_with_helper"],
                                                                 abs=1e-12)
    assert built["vectors"]["n"] == len(pd.read_csv(REPORTS / "help_vectors.csv"))
    table = pd.read_csv(REPORTS / "help_table.csv")
    assert built["table"]["status"] == table["status"].value_counts().to_dict()


def test_the_counted_sentences_are_counted_from_their_csv(built):
    """The robustness, per-game and provider sentences are counts the build makes: recounted
    here by a second route so a wrong filter in the build cannot agree with itself."""
    sweep = pd.read_csv(REPORTS / "second_help_contrast_sensitivity.csv")
    bounds = zip(sweep["contrast_ci_low"], sweep["contrast_ci_high"], strict=True)
    contain = sum(lo <= 0 <= hi for lo, hi in bounds)
    assert (built["sweep"]["contain"], built["sweep"]["n"]) == (contain, len(sweep))
    games = pd.read_csv(REPORTS / "second_help_by_game.csv")
    rows = [r for r in games.itertuples() if r.horizon == 38 and r.helped]
    assert built["by_game"] == {"n": len(rows),
                                "negative_by_drive": sum(r.median_diff < 0 for r in rows),
                                "negative_by_pairs": sum(r.median_diff_pairs < 0 for r in rows)}
    table = pd.read_csv(REPORTS / "help_table.csv")
    left = table[(table["status"] == "ok") & (table["provider_direction"] == "left")]
    assert built["table"]["direction"]["left"] == {"n": len(left),
                                                   "agree": int((left["flip"] == 1).sum())}


def test_the_strip_is_every_helped_drive_and_places_each_scene_as_the_json_does(built):
    means = paired_means(pd.read_csv(REPORTS / "near_committed_pairs.csv"))
    assert built["strip"]["means"] == pytest.approx(means.tolist())
    for scene in built["scenes"]["scenes"]:
        among = scene["paired_mean_1_5s_among_helped"]
        assert len(built["strip"]["means"]) == among["n_helped"]
        assert float(np.median(built["strip"]["means"])) == pytest.approx(among["median"])


def _bar(reports: Path) -> None:
    pairs = pd.read_csv(reports / "near_committed_pairs.csv")
    scene = _scene0()
    hit = ((pairs["drive_id"] == scene["drive_id"]) & (pairs["horizon"] == 38)
           & (pairs["def_slot"] == scene["roles"]["others"][0] - 5))
    pairs.loc[hit, ["to_left", "placebo"]] += 0.5  # both: the drive's mean, so the strip, holds
    pairs.to_csv(reports / "near_committed_pairs.csv", index=False)


def _strip(reports: Path) -> None:
    pairs = pd.read_csv(reports / "near_committed_pairs.csv")
    other = pairs[pairs["helped"] & (pairs["horizon"] == 38)
                  & (pairs["drive_id"] != _scene0()["drive_id"])]["drive_id"].iloc[0]
    pairs[pairs["drive_id"] != other].to_csv(reports / "near_committed_pairs.csv", index=False)


def _nearest(reports: Path) -> None:
    drives = pd.read_csv(reports / "near_committed_drives.csv")
    drives.loc[drives["drive_id"] == _scene0()["drive_id"], "nearest_who_38"] = "third"
    drives.to_csv(reports / "near_committed_drives.csv", index=False)


def _clearance(reports: Path) -> None:
    drives = pd.read_csv(reports / "near_committed_drives.csv")
    drives.loc[drives["drive_id"] == _scene0()["drive_id"], "left_clear_38"] += 0.1
    drives.to_csv(reports / "near_committed_drives.csv", index=False)


def _contrast(reports: Path) -> None:
    contrast = pd.read_csv(reports / "second_help_contrast.csv")
    contrast.loc[contrast["horizon"] == 38, "contrast_ci_low"] = 0.01
    contrast.to_csv(reports / "second_help_contrast.csv", index=False)


def _corner(reports: Path) -> None:
    rates = pd.read_csv(reports / "help_base_rate.csv")
    rates.loc[(rates["grouping"] == "y_band") & (rates["group"] == "18-inf"), "rate_high"] = 0.05
    rates.to_csv(reports / "help_base_rate.csv", index=False)


def _field(reports: Path) -> None:
    field = pd.read_csv(reports / "help_field.csv")
    field.loc[field["mean_dx"].isna().idxmax(), "mean_dx"] = 1.0
    field.to_csv(reports / "help_field.csv", index=False)


def _not_finite(reports: Path) -> None:
    passes = pd.read_csv(reports / "second_help_pass.csv")
    passes.loc[passes["helped"], "left_clear_when_got_it"] = np.nan
    passes.to_csv(reports / "second_help_pass.csv", index=False)


@pytest.mark.parametrize(("spoil", "says"), [
    (_bar, "to_left at frame 38"),
    (_strip, "helped drives"),
    (_nearest, "would name"),
    (_clearance, "left_clear_38"),
    (_contrast, "every interval contains 0"),
    (_corner, "too few to say"),
    (_field, "MIN_WEIGHT"),
    (_not_finite, "left_clear_when_got_it"),
])
def test_the_build_refuses_a_source_that_disagrees(reports, spoil, says):
    payload(reports)  # the untouched copy builds
    spoil(reports)
    with pytest.raises(Refused, match=re.escape(says)):
        payload(reports)


def test_the_template_types_no_number_with_a_unit():
    assert TYPED.search("the helper moves 5.5 ft")  # the pattern itself can fire
    assert TYPED.search("58.3 %")
    assert TYPED.findall(TEMPLATE.read_text(encoding="utf-8")) == []


def test_the_vendored_three_is_the_pinned_file_and_exports_what_the_page_uses(tmp_path):
    template = TEMPLATE.read_text(encoding="utf-8")
    code, release = vendored(VENDOR, template)
    assert release in (VENDOR / "README").read_text(encoding="utf-8")
    assert "exports.WebGLRenderer = WebGLRenderer;" in code
    with pytest.raises(Refused, match="does not export"):
        vendored(VENDOR, template + " THREE.NoSuchThing ")
    spoilt = tmp_path / "three"
    shutil.copytree(VENDOR, spoilt)
    with open(spoilt / "three.cjs", "a", encoding="utf-8") as f:
        f.write("\n")
    with pytest.raises(Refused, match="does not hash"):
        vendored(spoilt, template)


def test_the_vendored_players_are_the_pinned_glb_with_every_clip_and_bone_the_page_names(tmp_path):
    template = TEMPLATE.read_text(encoding="utf-8")
    body, size = players(PLAYERS, template)
    assert size == (PLAYERS / "ual_mannequin_trimmed.glb").stat().st_size
    assert re.fullmatch(r"[A-Za-z0-9+/=]+", body)
    assert "CC0" in (PLAYERS / "LICENSE.txt").read_text(encoding="utf-8")
    assert (PLAYERS / "trim.mjs").exists()
    with pytest.raises(Refused, match="lacks the clips"):
        players(PLAYERS, template + " rig.clips.Moonwalk_Loop ")
    with pytest.raises(Refused, match="lacks the bones"):
        players(PLAYERS, template + " B.byName.tail_01 ")
    spoilt = tmp_path / "players"
    shutil.copytree(PLAYERS, spoilt)
    with open(spoilt / "ual_mannequin_trimmed.glb", "ab") as f:
        f.write(b"\0")
    with pytest.raises(Refused, match="does not hash"):
        players(spoilt, template)


def test_assembly_fills_each_marker_once_and_keeps_the_payload_inside_its_script():
    template = ("<script id=\"three-js\">/*THREE*/</script><script>/*PAYLOAD*/</script>"
                "<script>/*PLAYERS*/</script>")
    page = assemble(template, {"a": "</script><b>"}, "var x = 1;", "Z2xURg==")
    assert page.count("</script>") == 3
    assert '"<\\/script><b>"' in page and "Z2xURg==" in page
    with pytest.raises(SystemExit, match="exactly once"):
        assemble(template.replace("/*THREE*/", ""), {}, "", "")
    with pytest.raises(SystemExit, match="exactly once"):
        assemble(template.replace("/*PLAYERS*/", ""), {}, "", "")
    with pytest.raises(Refused, match="base64"):
        assemble(template, {}, "", "</script>")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on the PATH")
def test_the_inlined_three_loads_and_a_broken_one_is_refused(built):
    template = TEMPLATE.read_text(encoding="utf-8")
    code, release = vendored(VENDOR, template)
    page = assemble(template, built, code, players(PLAYERS, template)[0])
    assert "three r185" in prove_loads(page, release)
    block = inlined_block(page)
    broken = page.replace(block, block.replace("'use strict';", "'use strict'; )", 1))
    with pytest.raises(Refused, match="does not load"):
        prove_loads(broken, release)


def test_the_page_loads_nothing_from_the_network(built):
    template = TEMPLATE.read_text(encoding="utf-8")
    code, _ = vendored(VENDOR, template)
    page = assemble(template, built, code, players(PLAYERS, template)[0])
    loads =r"<script[^>]*\bsrc=|<link\b|<img\b|<iframe\b|@import|url\(\s*['\"]?https?:"
    assert not re.search(loads, page)
    linked = set(re.findall(r"""\b(?:src|href|action)\s*=\s*["'](https?:[^"']*)""", page))
    # a link to click, not a load
    assert linked == {"https://github.com/SkillCorner/opendata-basketball"}
