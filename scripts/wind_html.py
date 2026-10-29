"""The second entry's page: one drive in 3D, the measure from above (B4).

Usage: uv run python scripts/wind_html.py [--reports DIR] [--vendor DIR] [--out FILE]

The spec is `tasks/wind_page.md`, the storyboard Javier accepted. The page opens on the drive of
figure 1 from a broadcast camera behind the basket, plays it at half speed with no click, then
rises to the top-down view, where every measure is shown: the three other defenders beside
their placebo, who covers the man the helper left, and the result over all drives. The league
wind and the limits follow. Nothing numeric exists while the camera is not straight down.

Every number on the page arrives in the payload below, and every value in the payload is read
off a `reports/*.csv`, off `reports/wind_scenes.json` or off a frozen constant in `scbasket`
(lesson 1). The template types none of them. Before writing, the build refuses on the guards of
the storyboard's section 1, so the page cannot quote a table that disagrees with the scenes it
draws: the 252 per-drive means are recomputed from `second_help_pairs.csv` with the same
function `wind_scenes.py` used, each scene's bars and nearest defender at 1.5 s are held to the
CSV rows of its drive, and each sentence that states a result is held to the rows behind it.

three.js is vendored at one pinned release in `vendor/three/` with its MIT licence and inlined
here, behind a two-line `module.exports` shim (section 8). Its hash is checked against
`vendor/three/README`, every `THREE.<name>` the template uses must be exported by it, and, when
`node` is on the PATH, the exact inlined block is run once in a bare context to prove it loads.
No CDN, no font, no request leaves the page.

Writes {out} (default `reports/nobody_helps_the_helper.html`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from _record import freeze_commits
from wind_scenes import paired_means, place_in

from scbasket.court import FIBA
from scbasket.frames import N_SIDE
from scbasket.rotation import HEADLINE_HORIZON, NEAREST_WHO, ROTATION_HORIZONS
from scbasket.wind import MIN_WEIGHT, OPEN_FT, RATE_MIN_WEIGHT

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(__file__).with_name("wind_template.html")
PAYLOAD = "/*PAYLOAD*/"
THREE = "/*THREE*/"
THREE_FILE = "three.cjs"
#: What the inlined three.js must never contain: an HTML parser would end or re-enter the
#: script element on the first two, and the markers would be substituted twice.
FORBIDDEN_IN_SCRIPT = ("</script", "<script", "<!--", PAYLOAD, THREE)

#: How far a scene may be from the CSV row it is held to, in feet (the JSON's coordinates
#: ship rounded to 3 decimals, which moves a distance by far less than this).
TOLERANCE_FT = 0.01

#: Every file the page is built from, with the script that writes it.
SOURCES = {
    "wind_scenes.json": "wind_scenes",
    "second_help_pairs.csv": "second_help",
    "second_help_drives.csv": "second_help",
    "second_help_summary.csv": "second_help",
    "second_help_contrast.csv": "second_help",
    "second_help_contrast_sensitivity.csv": "second_help",
    "second_help_by_game.csv": "second_help",
    "second_help_pass.csv": "second_help",
    "second_help_closeouts.csv": "second_help",
    "help_sensitivity.csv": "help_wind",
    "help_base_rate.csv": "help_wind",
    "help_vectors.csv": "help_wind",
    "help_table.csv": "help_wind",
    "help_field.csv": "help_wind",
}

#: The wind map's orange bands, the helper rate per defender. A copy of `RATE_LEVELS` in
#: `scripts/help_figures.py`, which cannot be imported without matplotlib: the page's key has
#: to read like the map's.
RATE_LEVELS = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 1.0)

#: The league row of `help_sensitivity.csv` the page quotes: the entry's helper definition.
LEAGUE_HORIZON_S, LEAGUE_HELP_FT = 1.0, 4.0


class Refused(SystemExit):
    """The build will not write a page whose numbers disagree with their sources."""

    def __init__(self, why: str) -> None:
        super().__init__(f"refused: {why}")


def read(reports: Path, name: str) -> pd.DataFrame:
    """A reports CSV, or a message naming the script that writes it."""
    path = reports / name
    if not path.exists():
        raise SystemExit(f"no {path}; run scripts/{SOURCES[name]}.py first")
    return pd.read_csv(path)


def records(table: pd.DataFrame) -> list[dict]:
    """A DataFrame as plain records at full precision (the page shows rounded values and
    carries the exact ones in `data-value`, so a console check can compare them with the CSV)."""
    return json.loads(table.to_json(orient="records", double_precision=15))


def one(table: pd.DataFrame, what: str) -> dict:
    """The only row of a selection, as a record; refuse if there is not exactly one."""
    if len(table) != 1:
        raise Refused(f"{what}: expected one row, found {len(table)}")
    return records(table)[0]


def nearest(xy: np.ndarray, roles: dict) -> tuple[str, float]:
    """Who of the five defenders is nearest to the man left at one frame, and how far, named
    as `scbasket.rotation` names it ("helper", "handler_def" or "third")."""
    gaps = np.linalg.norm(xy[N_SIDE:] - xy[roles["left"]], axis=1)
    slot = N_SIDE + int(np.argmin(gaps))
    who = {roles["helper"]: "helper", roles["handler_def"]: "handler_def"}.get(slot, "third")
    if who not in NEAREST_WHO:
        raise Refused(f"unknown nearest role {who}")
    return who, float(gaps.min())


def check_scenes(scenes: dict, pairs: pd.DataFrame, drives: pd.DataFrame) -> pd.Series:
    """Section 1's guards on the four scenes; returns the per-drive means of the strip.

    The strip is recomputed from `second_help_pairs.csv` with `wind_scenes.paired_means`, the
    function that placed each scene, so its n, median and every percentile must equal the
    JSON's. Each scene's three bars at the headline frame must equal the CSV's rows for its
    drive, and its nearest defender at 1.5 s must be the one `second_help_drives.csv` names.
    """
    t = scenes["headline_frame"]
    if t != HEADLINE_HORIZON:
        raise Refused(f"wind_scenes.json headline_frame {t}, scbasket {HEADLINE_HORIZON}")
    means = paired_means(pairs, t)
    by_id = drives.set_index("drive_id")
    at_t = pairs[(pairs["horizon"] == t) & pairs["helped"]].set_index(["drive_id", "def_slot"])
    for scene in scenes["scenes"]:
        name, roles = scene["drive_id"], scene["roles"]
        placed = place_in(scene["paired_mean_1_5s"], means)
        stored = scene["paired_mean_1_5s_among_helped"]
        if placed["n_helped"] != stored["n_helped"]:
            raise Refused(f"{name}: the strip has {placed['n_helped']} helped drives, the JSON "
                          f"{stored['n_helped']}: rerun scripts/wind_scenes.py")
        for key in ("median", "percentile"):
            if not math.isclose(placed[key], stored[key], abs_tol=1e-9):
                raise Refused(f"{name}: the strip's {key} is {placed[key]:.4f}, the JSON's "
                              f"{stored[key]:.4f}: rerun scripts/wind_scenes.py")
        if name not in means.index or abs(means[name] - scene["paired_mean_1_5s"]) > TOLERANCE_FT:
            raise Refused(f"{name}: its paired mean in second_help_pairs.csv does not equal "
                          f"the scene's {scene['paired_mean_1_5s']:+.3f}")
        for i, slot in enumerate(roles["others"]):
            key = (name, slot - N_SIDE)
            if key not in at_t.index:
                raise Refused(f"{name}: no second_help_pairs.csv row for def_slot {key[1]}")
            row = at_t.loc[key]
            for column in ("to_left", "placebo"):
                if abs(scene[column][i][t] - row[column]) > TOLERANCE_FT:
                    raise Refused(f"{name}: defender {i + 1}'s {column} at frame {t} is "
                                  f"{scene[column][i][t]:+.3f} in the scene and "
                                  f"{row[column]:+.3f} in second_help_pairs.csv")
        if name not in by_id.index:
            raise Refused(f"{name}: not in second_help_drives.csv")
        drive = by_id.loc[name]
        who, dist = nearest(np.asarray(scene["xy"][t], float), roles)
        if who != drive[f"nearest_who_{t}"]:
            raise Refused(f"{name}: the page would name {who} nearest at frame {t}, "
                          f"second_help_drives.csv names {drive[f'nearest_who_{t}']}")
        for value, column in ((dist, f"nearest_dist_{t}"),
                              (scene["left_clearance"][t], f"left_clear_{t}")):
            if abs(value - drive[column]) > TOLERANCE_FT:
                raise Refused(f"{name}: clearance {value:.3f} ft at frame {t}, "
                              f"second_help_drives.csv {column} {drive[column]:.3f}")
    return means


def check_field(field: pd.DataFrame) -> None:
    """help_field.csv as B1 wrote it: its columns, and its masks where `scbasket.wind` says."""
    missing = {"x", "y", "weight", "mean_dx", "mean_dy", "helper_rate"} - set(field.columns)
    if missing:
        raise Refused(f"help_field.csv has lost {sorted(missing)}")
    if not (field["mean_dx"].notna() == (field["weight"] >= MIN_WEIGHT)).all():
        raise Refused("help_field.csv: the means are not masked at scbasket.wind.MIN_WEIGHT")
    if not (field["helper_rate"].notna() == (field["weight"] >= RATE_MIN_WEIGHT)).all():
        raise Refused("help_field.csv: the rate is not masked at scbasket.wind.RATE_MIN_WEIGHT")


def check_finite(value, where: str = "payload") -> None:
    """Every scalar the page injects must be a finite number (or a string or a bool)."""
    if isinstance(value, dict):
        for key, item in value.items():
            check_finite(item, f"{where}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            check_finite(item, f"{where}[{i}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise Refused(f"{where} is {value}")
    elif value is None:
        raise Refused(f"{where} is missing")


def payload(reports: Path) -> dict:
    """Everything the page shows, gathered from the reports and the frozen constants."""
    for name in SOURCES:
        if not (reports / name).exists():
            raise SystemExit(f"no {reports / name}; run scripts/{SOURCES[name]}.py first")
    scenes = json.loads((reports / "wind_scenes.json").read_text(encoding="utf-8"))
    pairs = read(reports, "second_help_pairs.csv")
    drives = read(reports, "second_help_drives.csv")
    summary = read(reports, "second_help_summary.csv")
    contrast = read(reports, "second_help_contrast.csv")
    sweep = read(reports, "second_help_contrast_sensitivity.csv")
    games = read(reports, "second_help_by_game.csv")
    passes = read(reports, "second_help_pass.csv")
    closeouts = read(reports, "second_help_closeouts.csv")
    league = read(reports, "help_sensitivity.csv")
    rates = read(reports, "help_base_rate.csv")
    vectors = read(reports, "help_vectors.csv")
    table = read(reports, "help_table.csv")
    field = read(reports, "help_field.csv")

    means = check_scenes(scenes, pairs, drives)
    check_field(field)

    # The claim under figure 2's chart: every interval of helped minus no helper contains 0.
    for row in records(contrast):
        if not row["contrast_ci_low"] <= 0 <= row["contrast_ci_high"]:
            raise Refused(f"the contrast at {row['horizon_s']} s is ({row['contrast_ci_low']:+.2f}"
                          f" to {row['contrast_ci_high']:+.2f}): 'every interval contains 0' "
                          "would be false")
    if sorted(contrast["horizon"]) != sorted(ROTATION_HORIZONS):
        raise Refused(f"second_help_contrast.csv horizons {sorted(contrast['horizon'])}")
    contain = (sweep["contrast_ci_low"] <= 0) & (sweep["contrast_ci_high"] >= 0)
    below = sweep[sweep["contrast_ci_high"] < 0]

    at_t = games[(games["horizon"] == HEADLINE_HORIZON) & games["helped"]]

    by_y = rates[(rates["grouping"] == "y_band") & (rates["standardised_by"] == "none")]
    corner, middle = by_y.iloc[-1], by_y.iloc[0]  # the |y| bands run from the middle out
    corner_ft = re.match(r"([0-9.]+)-inf$", str(corner["group"]))
    if corner_ft is None or not str(middle["group"]).startswith("0-"):
        raise Refused(f"help_base_rate.csv y bands are {list(by_y['group'])}")
    # "Too few stand there to say whether it helps less": the corner's interval holds the
    # middle's rate, or the sentence would be false.
    if not corner["rate_low"] <= middle["rate"] <= corner["rate_high"]:
        raise Refused("the corner's rate interval excludes the middle's rate: the page's "
                      "'too few to say' would be false")
    if len(vectors) != by_y["n_defenders"].sum():
        raise Refused(f"help_vectors.csv has {len(vectors)} rows, help_base_rate.csv "
                      f"{by_y['n_defenders'].sum()} defenders: rerun scripts/help_wind.py")
    bearing = rates[rates["grouping"] == "bearing_band"]

    ok = table[table["status"] == "ok"]
    direction = {side: {"n": int((ok["provider_direction"] == side).sum()),
                        "agree": int(((ok["provider_direction"] == side)
                                      & (ok["flip"] == sign)).sum())}
                 for side, sign in (("left", 1), ("right", -1))}

    data = {
        "built": date.today().isoformat(),
        "record": [{"sha": sha, "subject": subject} for sha, subject in freeze_commits()[:1]],
        "court": {"geometry": asdict(FIBA)},
        "open_ft": OPEN_FT,
        "strip": {"means": [float(v) for v in means.to_numpy()]},
        "drives": records(drives[drives["drive_id"].isin(
            [s["drive_id"] for s in scenes["scenes"]])][
            ["drive_id", f"nearest_who_{HEADLINE_HORIZON}", f"nearest_dist_{HEADLINE_HORIZON}",
             f"left_clear_{HEADLINE_HORIZON}"]]),
        "summary": records(summary),
        "contrast": records(contrast),
        "sweep": {"n": len(sweep), "contain": int(contain.sum()),
                  "above": int((sweep["contrast_ci_low"] > 0).sum()),
                  "below": records(below[["help_ft", "horizon_s"]]),
                  "help_ft": sorted(float(v) for v in sweep["help_ft"].unique())},
        "by_game": {"n": int(at_t["game"].nunique()),
                    "negative_by_drive": int((at_t["median_diff"] < 0).sum()),
                    "negative_by_pairs": int((at_t["median_diff_pairs"] < 0).sum())},
        "pass": one(passes[passes["helped"]], "second_help_pass.csv helped"),
        "closeouts": one(closeouts[closeouts["helped"] & closeouts["receiver_is_left"]],
                         "second_help_closeouts.csv helped, receiver_is_left"),
        "league": one(league[(league["horizon_s"] == LEAGUE_HORIZON_S)
                             & (league["help_ft"] == LEAGUE_HELP_FT)],
                      f"help_sensitivity.csv {LEAGUE_HORIZON_S} s, {LEAGUE_HELP_FT} ft"),
        "base_rate": {"corner": records(corner.to_frame().T)[0],
                      "middle": records(middle.to_frame().T)[0],
                      "corner_ft": float(corner_ft.group(1)),
                      "toward": records(bearing.iloc[[0]])[0],
                      "away": records(bearing.iloc[[-1]])[0]},
        "vectors": {"n": len(vectors),
                    "detected_both": float((vectors["detected0"] & vectors["detected1"]).mean())},
        "table": {"n_drives": len(table), "n_games": int(table["game"].nunique()),
                  "status": {k: int(v) for k, v in table["status"].value_counts().items()},
                  "direction": direction},
        "rate_levels": list(RATE_LEVELS),
    }
    check_finite(data)
    # Checked above or by their writers, and allowed their nulls (NaN placebo, masked cells).
    data["scenes"] = scenes
    data["field"] = {column: [None if pd.isna(v) else round(float(v), 6) for v in field[column]]
                     for column in ("x", "y", "weight", "mean_dx", "mean_dy", "helper_rate")}
    return data


def vendored(vendor: Path, template: str) -> tuple[str, str]:
    """The vendored three.js as inlined text and its release, after the checks of section 8.

    The hash in `vendor/three/README` is of the file with LF line endings, so a checkout that
    rewrote them (git's autocrlf) still passes, and the page always inlines the LF text.
    """
    readme = (vendor / "README").read_text(encoding="utf-8")
    pinned = re.search(r"three@([0-9.]+)", readme)
    digest = re.search(r"sha256 ([0-9a-f]{64})", readme)
    if pinned is None or digest is None:
        raise Refused(f"{vendor / 'README'} must name the release (three@X) and its sha256")
    code = (vendor / THREE_FILE).read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(code).hexdigest() != digest.group(1):
        raise Refused(f"{vendor / THREE_FILE} does not hash to the sha256 in its README")
    text = code.decode("utf-8")
    for bad in FORBIDDEN_IN_SCRIPT:
        if bad.lower() in text.lower():
            raise Refused(f"the vendored three.js contains {bad!r}; it cannot be inlined")
    if re.search(r"^\s*(import|export)\s", text, flags=re.MULTILINE):
        raise Refused("the vendored three.js has ES module syntax; the shim needs the CJS build")
    exported = set(re.findall(r"^exports\.([A-Za-z0-9_$]+) = ", text, flags=re.MULTILINE))
    used = set(re.findall(r"THREE\.([A-Za-z0-9_$]+)", template))
    if used - exported:
        raise Refused(f"the template uses THREE.{sorted(used - exported)}, which "
                      f"three {pinned.group(1)} does not export")
    return text, pinned.group(1)


def assemble(template: str, data: dict, three: str) -> str:
    """The template with three.js and the payload in place of their markers, once each."""
    for marker in (PAYLOAD, THREE):
        if template.count(marker) != 1:
            raise SystemExit(f"{TEMPLATE} must hold {marker} exactly once")
    # `</` inside a <script> would close it early, whatever the JSON says it means.
    blob = json.dumps(data, allow_nan=False).replace("</", "<\\/")
    head, tail = template.split(PAYLOAD)
    return head.replace(THREE, three) + blob + tail.replace(THREE, three)


#: Runs one classic script in a bare context (no require, no module, no DOM) and prints what
#: it left on `window.THREE`: the same conditions as a browser's <script>.
NODE_PROBE = (
    "const vm = require('vm'), fs = require('fs');"
    "const box = {}; box.window = box; vm.createContext(box);"
    "vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), box);"
    "const T = box.THREE || {};"
    "console.log(JSON.stringify({revision: T.REVISION, renderer: typeof T.WebGLRenderer,"
    " names: Object.keys(T).length}));"
)


def inlined_block(page: str) -> str:
    """The <script id="three-js"> element's text, as the browser will run it."""
    found = re.search(r'<script id="three-js">(.*?)</script>', page, flags=re.DOTALL)
    if found is None:
        raise SystemExit('the page has no <script id="three-js"> element')
    return found.group(1)


def prove_loads(page: str, release: str) -> str:
    """Run the inlined three.js block once under node; refuse if it does not load.

    Returns what was checked, or why it could not be (no node on the PATH: the structural
    checks of `vendored` still hold, and the console driver B5 loads it in a real browser).
    """
    node = shutil.which("node")
    if node is None:
        return "node not found: the inlined three.js was checked by hash and exports only"
    with tempfile.TemporaryDirectory() as scratch:
        script = Path(scratch) / "three_block.js"
        script.write_text(inlined_block(page), encoding="utf-8")
        run = subprocess.run([node, "-e", NODE_PROBE, str(script)], capture_output=True,
                             text=True, timeout=120)
    if run.returncode != 0:
        raise Refused(f"the inlined three.js does not load: {run.stderr.strip()[-400:]}")
    seen = json.loads(run.stdout.strip().splitlines()[-1])
    if seen["renderer"] != "function" or f"0.{seen['revision']}." not in f"{release}.":
        raise Refused(f"the inlined three.js loaded as {seen}, expected r{release}")
    return f"loaded under node: three r{seen['revision']}, {seen['names']} exports"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--reports", type=Path, default=ROOT / "reports")
    parser.add_argument("--vendor", type=Path, default=ROOT / "vendor" / "three")
    parser.add_argument("--out", type=Path, default=ROOT / "reports/nobody_helps_the_helper.html")
    args = parser.parse_args()

    template = TEMPLATE.read_text(encoding="utf-8")
    three, release = vendored(args.vendor, template)
    data = payload(args.reports)
    page = assemble(template, data, three)
    proof = prove_loads(page, release)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")

    print(f"wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB: three.js {release} "
          f"{len(three) / 1024:.0f} KB, payload {len(json.dumps(data)) / 1024:.0f} KB)")
    print(f"  {len(data['scenes']['scenes'])} scenes, strip of {len(data['strip']['means'])} "
          f"drives, field of {len(data['field']['x'])} cells; three.js {proof}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
