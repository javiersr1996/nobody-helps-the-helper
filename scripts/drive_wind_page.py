"""B5: drive the built wind page from the browser console and check it against the storyboard.

Run (needs the `page` extra and one browser download)::

    uv run --extra page playwright install chromium        # once
    uv run --extra page python scripts/drive_wind_page.py [path-or-http(s)-url]

The default target is `reports/nobody_helps_the_helper.html`; C1b points the same driver at
the published GitHub Pages URL. The expected values come from `tasks/wind_page.md` and the
files it names (`reports/wind_scenes.json`, `reports/second_help_*.csv`, `reports/help_*.csv`),
read here, never typed; the page's own source is not read. One line per check, exit 0 if every
check passes and 1 otherwise.

Out of scope, said once: headless Chromium cannot hide a tab, so the hidden-tab clock rule of
the storyboard (section 2.6, "a hidden tab stops the clock, not the clip") is not exercised.
WebGL needs `--use-angle=swiftshader --enable-unsafe-swiftshader` headless; if it is not live
the driver fails loudly before anything else.
"""

from __future__ import annotations

import importlib
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DEFAULT_PAGE = REPORTS / "nobody_helps_the_helper.html"
CHROMIUM_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
END_WORD = {
    "pullup": "pull-up",
    "kickout": "kickout",
    "shotNearBasket": "shot near the basket",
    "interiorPass": "interior pass",
}
SUB_BROADCAST = "One defender steps toward the ball. Watch the man he leaves."
SUB_PLAN = "From above, the measure: how far each of the other three moves toward him."
BODY_MIN_PX = 16
SCENES_N = 4

# In-page helpers, installed before the page's own script runs. `__ui()` reads the buttons and
# captions, `__vis(el)` is "really visible" (not hidden, not display none, has a box), and a
# 10 ms sampler logs every change of (view, phase, scene, ui, measure hidden) plus the frozen
# positions seen while rising, so the transitions are observed, not inferred from polling.
INIT_JS = """
(() => {
  const txt = (e) => (e ? e.textContent.replace(/\\s+/g, ' ').trim() : null);
  window.__vis = (e) => {
    if (!e) return false;
    for (let n = e; n && n.nodeType === 1; n = n.parentElement) {
      if (n.hidden) return false;
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    }
    return e.getClientRects().length > 0;
  };
  window.__ui = () => {
    const g = (i) => document.getElementById(i);
    const b = (i) => ({text: txt(g(i)), disabled: g(i).disabled, pressed: g(i).getAttribute('aria-pressed')});
    return {play: b('play'), bcast: b('view-broadcast'), plan: b('view-plan'), next: b('next'),
      caption: txt(g('stage-caption')), sub: txt(g('stage-sub')),
      scrub: {value: g('scrub').value, disabled: g('scrub').disabled,
              valuetext: g('scrub').getAttribute('aria-valuetext')}};
  };
  window.__log = [];
  window.__rise = [];
  let last = '';
  setInterval(() => {
    const w = window.wind, m = document.getElementById('measure');
    if (!w || !w.state || !m || !document.getElementById('play')) return;
    const s = w.state(), u = window.__ui();
    const sig = [s.view, s.phase, s.scene, JSON.stringify(u), m.hidden].join('|');
    if (sig !== last) {
      last = sig;
      window.__log.push({ts: performance.now(), s: s, u: u, mh: m.hidden, mv: window.__vis(m)});
    }
    if (s.view === 'rising') window.__rise.push(JSON.stringify(s.positions));
  }, 10);
})();
"""

# Connected components of pixels near a colour, read from the WebGL canvas through
# drawImage + getImageData (labels are DOM, so none of them can leak into this read).
SCAN_JS = """
([hexes, tol]) => {
  const c = document.getElementById('court');
  const t = document.createElement('canvas');
  t.width = c.width; t.height = c.height;
  const cx = t.getContext('2d');
  cx.drawImage(c, 0, 0);
  const W = c.width, H = c.height, d = cx.getImageData(0, 0, W, H).data;
  const out = {};
  for (const hex of hexes) {
    const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    const mask = new Uint8Array(W * H);
    let count = 0;
    for (let i = 0; i < W * H; i++) {
      if (Math.abs(d[4*i] - r) <= tol && Math.abs(d[4*i+1] - g) <= tol && Math.abs(d[4*i+2] - b) <= tol) {
        mask[i] = 1; count++;
      }
    }
    const comps = [];
    for (let i = 0; i < W * H; i++) {
      if (mask[i] !== 1) continue;
      const stack = [i]; mask[i] = 2;
      let n = 0, sx = 0, sy = 0;
      while (stack.length) {
        const k = stack.pop(), x = k % W, y = (k - x) / W;
        n++; sx += x + 0.5; sy += y + 0.5;
        for (const [dx, dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
          const xx = x + dx, yy = y + dy;
          if (xx < 0 || yy < 0 || xx >= W || yy >= H) continue;
          const kk = yy * W + xx;
          if (mask[kk] === 1) { mask[kk] = 2; stack.push(kk); }
        }
      }
      comps.push({n: n, x: sx / n, y: sy / n});
    }
    out[hex] = {count: count, comps: comps};
  }
  return {w: W, h: H, colours: out};
}
"""

# Pixel of a drive-frame point through camera(): independent of the page's own `project`.
PROJ_JS = """
([x, y, z]) => {
  const cam = wind.camera(), W = cam.world, P = cam.projection, V = cam.view;
  const mul = (m, v) => [0,1,2,3].map(r => m[r]*v[0] + m[4+r]*v[1] + m[8+r]*v[2] + m[12+r]*v[3]);
  const q = mul(P, mul(V, mul(W, [x, y, z, 1])));
  return [(q[0]/q[3]*0.5 + 0.5) * cam.width, (1 - (q[1]/q[3]*0.5 + 0.5)) * cam.height];
}
"""


class Report:
    """Collects one line per check; `ok` is the exit-code decision."""

    def __init__(self) -> None:
        self.rows: list[tuple[bool, str, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        ok = bool(ok)
        self.rows.append((ok, name, detail))
        print(
            f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""), flush=True
        )
        return ok

    @property
    def ok(self) -> bool:
        return all(r[0] for r in self.rows)


R = Report()


def guarded(fn):
    """A crash inside one group of checks is a FAIL line, not a silent skip of the rest."""

    def run(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as e:  # noqa: BLE001 - the report must name the failing group
            R.check(f"{fn.__name__} ran to the end", False, f"{type(e).__name__}: {str(e)[:300]}")

    return run


# ---------------------------------------------------------------- expected values, from files


class Data:
    def __init__(self) -> None:
        self.js = json.loads((REPORTS / "wind_scenes.json").read_text(encoding="utf-8"))
        self.scenes = self.js["scenes"]
        self.fps = self.js["fps"]
        self.headline = self.js["headline_frame"]
        self.hoop_x = self.js["hoop_x"]
        self.drives = pd.read_csv(REPORTS / "second_help_drives.csv").set_index("drive_id")
        self.pairs = pd.read_csv(REPORTS / "second_help_pairs.csv")
        self._csv: dict[str, pd.DataFrame] = {}

    def csv(self, name: str) -> pd.DataFrame:
        if name not in self._csv:
            self._csv[name] = pd.read_csv(REPORTS / name)
        return self._csv[name]

    def xy(self, scene: int, frame: int) -> np.ndarray:
        return np.array(self.scenes[scene]["xy"][frame], dtype=float)

    def ball(self, scene: int, frame: int) -> np.ndarray:
        return np.array(self.scenes[scene]["ball"][frame], dtype=float)

    def nearest_defender(self, scene: int, frame: int) -> tuple[str, float]:
        """The nearest of the five defenders to the man left, named by role (storyboard 4.2)."""
        roles = self.scenes[scene]["roles"]
        pts = self.xy(scene, frame)
        left = pts[roles["left"]]
        cand = {"handler_def": roles["handler_def"], "helper": roles["helper"]}
        cand.update({f"third{i}": s for i, s in enumerate(roles["others"])})
        best = min(cand.items(), key=lambda kv: float(np.hypot(*(pts[kv[1]] - left))))
        who = "third" if best[0].startswith("third") else best[0]
        return who, float(np.hypot(*(pts[best[1]] - left)))

    def drive_means(self, horizon: int = 38) -> pd.Series:
        """Per-drive mean of (to_left - placebo), helped drives, NaN placebo dropped (4.1)."""
        p = self.pairs[(self.pairs.horizon == horizon) & self.pairs.helped].dropna(
            subset=["placebo"]
        )
        return (p.to_left - p.placebo).groupby(p.drive_id).mean()


def pair_match(col: pd.Series, want: str) -> pd.Series:
    if col.dtype == bool:
        return col == (want.lower() == "true")
    try:
        return np.isclose(pd.to_numeric(col, errors="coerce"), float(want), rtol=0, atol=1e-9)
    except ValueError:
        return col.astype(str) == want


def filter_rows(df: pd.DataFrame, expr: str | None, sep: str) -> pd.DataFrame:
    for part in expr.split(sep) if expr else []:
        k, v = part.split("=", 1)
        df = df[pair_match(df[k], v)]
    return df


def source_value(D: Data, src: str, row: str | None, col: str) -> float:
    """What the data attributes of an injected number name, read from the file itself."""
    if src.endswith(".json"):
        if col.startswith("selection."):
            sel = [s for s in D.js["selection"] if f"game={s['game']}" == row]
            return float(sel[0][col.split(".", 1)[1]])
        node, parts = D.js, col.split(".")
        while parts:
            if isinstance(node, list):
                node = node[int(parts.pop(0))]
                continue
            # keys such as "1.5s" contain the separator: take the shortest prefix that is a key
            k = next(
                ".".join(parts[:n]) for n in range(1, len(parts) + 1) if ".".join(parts[:n]) in node
            )
            node = node[k]
            parts = parts[len(k.split(".")) :]
        return float(node)
    if not src.endswith(".csv"):  # a constant of the shipped package, e.g. scbasket.wind / OPEN_FT
        return float(getattr(importlib.import_module(src), col))
    df = D.csv(src)
    df = filter_rows(df, row, ";")
    if col in df.columns:
        if len(df) != 1:
            raise ValueError(f"{src} {row}: {len(df)} rows for {col}")
        return float(df[col].iloc[0])
    if col == "rows":
        return float(len(df))
    if col == "games":
        return float(len(df)) if "median_diff" in df.columns else float(df["game"].nunique())
    if col.startswith("games with "):
        return float((df[col.removeprefix("games with ").split(" < ")[0]] < 0).sum())
    if col == "intervals containing 0":
        return float(((df.contrast_ci_low <= 0) & (df.contrast_ci_high >= 0)).sum())
    if col == "detected0 and detected1":
        return float((df.detected0 & df.detected1).mean())
    if "=" in col:
        return float(len(filter_rows(df, col, " and ")))
    raise KeyError(f"no rule for {src} / {col}")


def shown_matches(text: str, value: float) -> tuple[bool, str]:
    """The visible number equals data-value to the precision it is printed with."""
    m = re.search(r"[-−+]?\d[\d,]*(?:\.(\d+))?", text.replace(" ", " "))
    if not m:
        return False, f"no number in {text!r}"
    shown = float(m.group(0).replace("−", "-").replace(",", ""))
    dec = len(m.group(1) or "")
    target = value * 100 if "%" in text else value
    return abs(shown - target) <= 0.5 * 10 ** (-dec) + 1e-9, f"{text!r} vs {target:.6g}"


# ---------------------------------------------------------------- expected UI, storyboard 5.3


def expect_ui(D: Data, st: dict, u: dict) -> list[str]:
    """Differences between the DOM and the 5.3 table for this state (empty: it holds)."""
    bad: list[str] = []
    sc = D.scenes[st["scene"]]
    T = D.headline / D.fps
    i, game, end = st["scene"] + 1, sc["game"], END_WORD[sc["end_type"]]

    def eq(what: str, got, want) -> None:
        if got != want:
            bad.append(f"{what}: {got!r} != {want!r}")

    if st["view"] == "rising":
        eq("caption", u["caption"], "rising to the top-down view")
        for k in ("play", "bcast", "plan", "next"):
            eq(f"{k} disabled", u[k]["disabled"], True)
        eq("scrub disabled", u["scrub"]["disabled"], True)
        return bad
    at_end = st["phase"] == "ended" or st["t"] >= T - 1e-6
    label = "Pause" if st["phase"] == "playing" else ("Replay" if at_end else "Play")
    eq("play label", u["play"]["text"], label)
    eq("bcast pressed", u["bcast"]["pressed"], "true" if st["view"] == "broadcast" else "false")
    eq("plan pressed", u["plan"]["pressed"], "true" if st["view"] == "plan" else "false")
    eq("next label", u["next"]["text"], "Next drive")
    for k in ("play", "bcast", "plan", "next"):
        eq(f"{k} enabled", u[k]["disabled"], False)
    eq("scrub enabled", u["scrub"]["disabled"], False)
    tail = (
        "the broadcast camera, half speed"
        if st["view"] == "broadcast"
        else "from above: the measure"
    )
    eq("caption", u["caption"], f"Drive {i} of {SCENES_N} · game {game} · {end} · {tail}")
    eq("subtitle", u["sub"], SUB_BROADCAST if st["view"] == "broadcast" else SUB_PLAN)
    frame = float(u["scrub"]["value"])
    if abs(frame - st["t"] * D.fps) > 1.01:
        bad.append(f"scrub {frame} vs t*fps {st['t'] * D.fps:.2f}")
    vt = re.search(r"t = ([\d.]+) s", u["scrub"]["valuetext"] or "")
    if not vt or abs(float(vt.group(1)) - st["t"]) > 1.0 / D.fps + 0.011:
        bad.append(f"valuetext {u['scrub']['valuetext']!r} vs t {st['t']:.3f}")
    return bad


# ---------------------------------------------------------------- browser helpers


def state(pg) -> dict:
    return pg.evaluate("wind.state()")


def ui(pg) -> dict:
    return pg.evaluate("__ui()")


def vis(pg, sel: str) -> bool:
    return pg.evaluate("(s) => __vis(document.querySelector(s))", sel)


def settle(pg) -> None:
    pg.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def wait_view(pg, view: str, timeout_s: float = 12.0) -> None:
    pg.wait_for_function(f"wind.state().view === '{view}'", timeout=timeout_s * 1000)


def go_plan(pg) -> None:
    """Cut to the top-down view through the exposed flight (no clock)."""
    pg.evaluate("wind.flight(1)")
    settle(pg)


def go_broadcast(pg) -> None:
    pg.evaluate("wind.view('broadcast') || wind.flight(0)")
    settle(pg)


def close(a, b, tol: float) -> bool:
    return bool(np.all(np.abs(np.asarray(a, float) - np.asarray(b, float)) <= tol))


def open_page(browser, target: str, *, width=1440, height=900, reduced=False, init=True):
    ctx = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
        reduced_motion="reduce" if reduced else "no-preference",
    )
    if init:
        ctx.add_init_script(INIT_JS)
    pg = ctx.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(target, wait_until="load")
    pg.wait_for_function(
        "window.wind && wind.state && document.getElementById('play')", timeout=30000
    )
    return ctx, pg, errors


# ---------------------------------------------------------------- the check groups


def webgl_alive(pg) -> bool:
    ok = pg.evaluate(
        """() => { const c = document.createElement('canvas');
                   return !!(c.getContext('webgl2') || c.getContext('webgl')); }"""
    )
    page_gl = pg.evaluate("document.getElementById('court').width > 0 && wind.camera().width > 0")
    return bool(ok and page_gl)


@guarded
def check_hook(D: Data, browser, target: str) -> None:
    """Natural run from load: opens in broadcast, ends, holds, rises, lands in plan, no click."""
    ctx, pg, errors = open_page(browser, target)
    c = pg.evaluate(
        "({RATE: wind.RATE, HOLD: wind.HOLD_S, FLIGHT: wind.FLIGHT_S, FADE: wind.FADE_S, T: wind.T})"
    )
    T = D.headline / D.fps
    R.check(
        "constants: T equals headline_frame / fps", abs(c["T"] - T) < 1e-9, f"T={c['T']} file={T}"
    )
    R.check(
        "constants: RATE, HOLD_S, FLIGHT_S, FADE_S inside the storyboard's ranges",
        0.4 <= c["RATE"] <= 0.6
        and 0.3 <= c["HOLD"] <= 0.8
        and c["FLIGHT"] == 1.5
        and 0 < c["FADE"] <= 0.5,
        json.dumps(c),
    )
    first = pg.evaluate("window.__log[0]")
    R.check(
        "opens in scene 0, broadcast, playing",
        first
        and first["s"]["scene"] == 0
        and first["s"]["view"] == "broadcast"
        and first["s"]["phase"] == "playing",
        f"{first['s']['view']}/{first['s']['phase']} t={first['s']['t']:.3f}"
        if first
        else "no log",
    )
    R.check("measure hidden at load", bool(first and first["mh"] and not first["mv"]))
    total = c["T"] / c["RATE"] + c["HOLD"] + c["FLIGHT"] + c["FADE"]
    wait_view(pg, "plan", total + 4)
    pg.wait_for_timeout(int((c["FADE"] + 0.4) * 1000))
    log = pg.evaluate("window.__log")
    t0 = first["ts"] - first["s"]["t"] / c["RATE"]

    def when(pred):
        return next((e["ts"] for e in log if pred(e["s"])), None)

    t_end = when(lambda s: s["view"] == "broadcast" and s["phase"] == "ended")
    t_rise = when(lambda s: s["view"] == "rising")
    t_plan = when(lambda s: s["view"] == "plan")
    seq = []
    for e in log:
        k = (e["s"]["view"], e["s"]["phase"] if e["s"]["view"] != "rising" else "-")
        if not seq or seq[-1] != k:
            seq.append(k)
    R.check(
        "reaches plan with no click: broadcast/playing, broadcast/ended, rising, plan",
        [s[0] for s in seq][:4] == ["broadcast", "broadcast", "rising", "plan"]
        and seq[0][1] == "playing"
        and seq[1][1] == "ended",
        " > ".join(f"{a}/{b}" for a, b in seq),
    )
    if t_end and t_rise and t_plan:
        R.check(
            "timeline: end at T/RATE, rise after HOLD_S, plan after FLIGHT_S (observed from the page)",
            abs((t_end - t0) / 1000 - c["T"] / c["RATE"]) < 0.5
            and abs((t_rise - t_end) / 1000 - c["HOLD"]) < 0.25
            and abs((t_plan - t_rise) / 1000 - c["FLIGHT"]) < 0.25,
            f"end {(t_end - t0) / 1000:.2f}s, hold {(t_rise - t_end) / 1000:.2f}s, "
            f"flight {(t_plan - t_rise) / 1000:.2f}s",
        )
    ended = next(
        (e for e in log if e["s"]["view"] == "broadcast" and e["s"]["phase"] == "ended"), None
    )
    last_xy = D.xy(0, D.headline)
    R.check(
        "ended: t = T and the last frame is drawn (positions = frame 38, scrub at 38)",
        bool(ended)
        and abs(ended["s"]["t"] - T) < 1e-6
        and close(ended["s"]["positions"]["players"], last_xy, 0.01)
        and float(ended["u"]["scrub"]["value"]) == D.headline,
    )
    bad = []
    for e in log:
        for b in expect_ui(D, e["s"], e["u"]):
            bad.append(f"{e['s']['view']}/{e['s']['phase']}: {b}")
    R.check(
        "5.3 label table holds in every state of the natural run (incl. hold and rising)",
        not bad,
        f"{len(log)} states; " + "; ".join(sorted(set(bad))[:3]),
    )
    rising_rows = [e for e in log if e["s"]["view"] == "rising"]
    R.check(
        "rising: measure hidden in every logged state",
        bool(rising_rows) and all(e["mh"] and not e["mv"] for e in rising_rows),
    )
    rise = pg.evaluate("window.__rise")
    R.check(
        "rising: positions frozen for the whole flight",
        len(rise) > 20 and len(set(rise)) == 1,
        f"{len(rise)} samples, {len(set(rise))} distinct",
    )
    landed = [e for e in log if e["s"]["view"] == "plan"]
    R.check(
        "plan: measure shown after landing",
        bool(landed) and landed[-1]["mv"] and not landed[-1]["mh"],
    )
    R.check(
        "plan reached: orthographic camera",
        pg.evaluate("wind.camera().type") == "orthographic",
    )
    R.check(
        "no page errors or console errors during the natural run", not errors, "; ".join(errors[:2])
    )
    ctx.close()

    # Calls during the real (clocked) flight are refused and change nothing.
    ctx, pg, _ = open_page(browser, target)
    pg.evaluate("wind.seek(wind.T - 0.2)")
    pg.evaluate("wind.play()")
    wait_view(pg, "rising", 8)
    out = pg.evaluate(
        """() => { const a = JSON.stringify(wind.state());
          const r = [wind.play(), wind.pause(), wind.seek(0.3), wind.next(), wind.view('plan'),
                     wind.view('broadcast')];
          return {r: r, same: JSON.stringify(wind.state()) === a || wind.state().view}; }"""
    )
    R.check(
        "clocked rising ignores play/pause/seek/next/view and returns false",
        out["r"] == [False] * 6,
        json.dumps(out["r"]),
    )
    wait_view(pg, "plan", 5)
    R.check(
        "the flight still lands in plan after the refused calls",
        state(pg)["scene"] == 0 and pg.evaluate("wind.camera().type") == "orthographic",
    )
    ctx.close()


@guarded
def check_transport(D: Data, browser, target: str) -> None:
    ctx, pg, _ = open_page(browser, target)
    c = pg.evaluate(
        "({RATE: wind.RATE, HOLD: wind.HOLD_S, FLIGHT: wind.FLIGHT_S, FADE: wind.FADE_S})"
    )
    T = D.headline / D.fps
    sc = D.scenes[0]
    go_broadcast(pg)
    pg.evaluate("wind.pause()")

    # seek(1.0): the JSON, all ten players and the ball, then clamping and interpolation.
    pg.evaluate("wind.seek(1.0)")
    s = state(pg)
    helper = sc["roles"]["helper"]
    err = float(np.hypot(*(np.array(s["positions"]["players"][helper]) - D.xy(0, 25)[helper])))
    R.check("seek(1.0): helper within 0.1 ft of xy[25][helper]", err <= 0.1, f"{err:.4f} ft")
    R.check(
        "seek(1.0): all ten players and the ball equal frame 25",
        close(s["positions"]["players"], D.xy(0, 25), 0.01)
        and close(s["positions"]["ball"], D.ball(0, 25), 0.01)
        and s["phase"] == "idle"
        and abs(s["t"] - 1.0) < 1e-9,
    )
    pg.evaluate("wind.seek(0.5)")
    mid = (D.xy(0, 12) + D.xy(0, 13)) / 2
    R.check(
        "seek(0.5): positions are the linear interpolation of frames 12 and 13",
        close(state(pg)["positions"]["players"], mid, 0.01),
    )
    pg.evaluate("wind.seek(-3)")
    lo = state(pg)["t"]
    pg.evaluate("wind.seek(99)")
    hi = state(pg)["t"]
    R.check("seek clamps to [0, T]", lo == 0 and abs(hi - T) < 1e-9, f"{lo}, {hi}")

    # pause then play resumes at the same t, at RATE.
    pg.evaluate("wind.seek(0.2)")
    R.check("play() from idle returns true", pg.evaluate("wind.play()") is True)
    pg.wait_for_timeout(500)
    pg.evaluate("wind.pause()")
    t1 = state(pg)
    pg.wait_for_timeout(400)
    t2 = state(pg)
    R.check(
        "pause: phase idle and t kept while paused",
        t1["phase"] == "idle" and t1["t"] == t2["t"] and t1["t"] > 0.3,
        f"t={t1['t']:.4f} then {t2['t']:.4f}",
    )
    R.check("pause: label reads Play", ui(pg)["play"]["text"] == "Play")
    pg.evaluate("wind.play()")
    t3 = state(pg)
    R.check(
        "play after pause resumes at the same t (no jump)",
        abs(t3["t"] - t1["t"]) < 0.05 and t3["phase"] == "playing",
        f"{t1['t']:.4f} -> {t3['t']:.4f}",
    )
    pg.evaluate("window.__a = [performance.now(), wind.state().t]")
    pg.wait_for_timeout(600)
    rate = pg.evaluate(
        "(performance.now() - __a[0]) > 0 ? (wind.state().t - __a[1]) / ((performance.now() - __a[0]) / 1000) : 0"
    )
    R.check(
        "playback advances at RATE clip-seconds per second",
        abs(rate - c["RATE"]) < 0.08,
        f"{rate:.3f} vs RATE {c['RATE']}",
    )
    R.check("play() while playing is a no-op returning false", pg.evaluate("wind.play()") is False)
    pg.evaluate("wind.pause()")

    # Pause during the hold cancels the rise; seek during the hold does too.
    for how, call in (("pause", "wind.pause()"), ("seek", "wind.seek(0.5)")):
        go_broadcast(pg)
        pg.evaluate("wind.seek(wind.T - 0.15)")
        pg.evaluate("wind.play()")
        pg.wait_for_function("wind.state().phase === 'ended'", timeout=5000)
        in_hold = state(pg)
        bad = expect_ui(D, in_hold, ui(pg))
        R.check(
            f"hold ({how} test): ended in broadcast, label table holds",
            in_hold["view"] == "broadcast" and not bad,
            "; ".join(bad[:2]),
        )
        pg.wait_for_timeout(int(c["HOLD"] * 1000 * 0.4))
        pg.evaluate(call)
        after = state(pg)
        bad = expect_ui(D, after, ui(pg))
        R.check(
            f"{how} during the hold: stays in broadcast, label table holds",
            after["view"] == "broadcast" and not bad,
            f"{after['view']}/{after['phase']} t={after['t']:.2f}; " + "; ".join(bad[:2]),
        )
        pg.wait_for_timeout(int((c["HOLD"] + c["FLIGHT"]) * 1000 + 500))
        R.check(
            f"{how} during the hold cancels the rise (still broadcast, measure hidden after HOLD_S + FLIGHT_S)",
            state(pg)["view"] == "broadcast" and not vis(pg, "#measure"),
        )
    # After the cancelled hold (seek variant) play resumes, and at t = T play() restarts at 0.
    pg.evaluate("wind.seek(wind.T)")
    pg.evaluate("wind.play()")
    st = state(pg)
    R.check(
        "play() at t = T restarts the clip at 0, playing",
        st["phase"] == "playing" and st["t"] < 0.3,
        f"t={st['t']:.3f}",
    )
    pg.evaluate("wind.pause()")

    # View switching.
    pg.evaluate("wind.seek(1.0)")
    R.check(
        "view('plan') from broadcast starts the flight",
        pg.evaluate("wind.view('plan')") is True and state(pg)["view"] == "rising",
    )
    wait_view(pg, "plan", 4)
    R.check(
        "view('plan') in plan is a no-op returning true", pg.evaluate("wind.view('plan')") is True
    )
    pg.wait_for_timeout(int(c["FADE"] * 1000) + 200)
    t_before = state(pg)["t"]
    ok_b = pg.evaluate("wind.view('broadcast')")
    sb = state(pg)
    R.check(
        "view('broadcast') from plan is a cut: broadcast at once, measure hidden, t kept, idle",
        ok_b is True
        and sb["view"] == "broadcast"
        and sb["phase"] == "idle"
        and sb["t"] == t_before
        and not vis(pg, "#measure")
        and pg.evaluate("wind.camera().type") == "perspective",
    )
    R.check(
        "view('rising') and unknown names are refused",
        pg.evaluate("[wind.view('rising'), wind.view('nope')]") == [False, False],
    )
    ctx.close()


@guarded
def check_scenes(D: Data, browser, target: str) -> None:
    """next() in plan and in broadcast; the numbers of every scene; the headline frame."""
    ctx, pg, _ = open_page(browser, target)
    T = D.headline / D.fps
    go_plan(pg)
    pg.wait_for_timeout(500)
    pg.evaluate("wind.seek(wind.T)")
    seen = []
    for k in range(SCENES_N + 1):
        i = k % SCENES_N
        s, u = state(pg), ui(pg)
        sc = D.scenes[i]
        roles = sc["roles"]
        row = D.drives.loc[sc["drive_id"]]
        tag = f"scene {i}"
        R.check(
            f"{tag}: scene index, t = T, idle, plan",
            s["scene"] == i
            and abs(s["t"] - T) < 1e-9
            and s["phase"] == "idle"
            and s["view"] == "plan",
        )
        R.check(
            f"{tag}: positions equal xy[38]",
            close(s["positions"]["players"], D.xy(i, D.headline), 0.01)
            and close(s["positions"]["ball"], D.ball(i, D.headline), 0.01),
        )
        bad = expect_ui(D, s, u)
        R.check(f"{tag}: label table holds after next()", not bad, "; ".join(bad[:2]))
        vals = pg.evaluate(
            """() => { const v = (i) => { const e = document.getElementById(i);
                   return e ? parseFloat(e.dataset.value) : null; };
              const out = {};
              for (let i = 1; i <= 3; i++) { out['t' + i] = v('bar-toward-' + i); out['p' + i] = v('bar-placebo-' + i);
                                              out['d' + i] = v('bar-diff-' + i); }
              out.mean = v('bar-mean'); out.dist = v('tile-dist');
              out.who = document.getElementById('tile-who').dataset.who;
              out.n = v('strip-n'); out.med = v('strip-median'); out.pct = v('strip-percentile');
              return out; }"""
        )
        diffs = []
        for j in range(3):
            tl, pl = sc["to_left"][j][D.headline], sc["placebo"][j][D.headline]
            slot = roles["others"][j] - 5  # defenders are players 5..9; def_slot counts from 0
            pr = D.pairs[
                (D.pairs.drive_id == sc["drive_id"])
                & (D.pairs.horizon == 38)
                & (D.pairs.def_slot == slot)
            ]
            diffs.append(tl - pl)
            R.check(
                f"{tag}: bar {j + 1} black/grey/difference equal to_left, placebo at 38 within 0.01 ft",
                abs(vals[f"t{j + 1}"] - tl) <= 0.01
                and abs(vals[f"p{j + 1}"] - pl) <= 0.01
                and abs(vals[f"d{j + 1}"] - (tl - pl)) <= 0.011,
                f"{vals[f't{j + 1}']:.3f}/{vals[f'p{j + 1}']:.3f} vs {tl:.3f}/{pl:.3f}",
            )
            R.check(f"{tag}: second_help_pairs.csv has the row for bar {j + 1}", len(pr) == 1)
            if len(pr) == 1:
                R.check(
                    f"{tag}: bar {j + 1} equals second_help_pairs.csv (horizon 38, def_slot {slot})",
                    abs(vals[f"t{j + 1}"] - pr.to_left.iloc[0]) <= 0.01
                    and abs(vals[f"p{j + 1}"] - pr.placebo.iloc[0]) <= 0.01,
                )
        R.check(
            f"{tag}: bar mean equals the mean of the three differences",
            abs(vals["mean"] - np.mean(diffs)) <= 0.01,
            f"{vals['mean']:.3f} vs {np.mean(diffs):.3f}",
        )
        who, dist = D.nearest_defender(i, D.headline)
        R.check(
            f"{tag}: tile equals second_help_drives.csv nearest_who_38 / nearest_dist_38 (and the page's rule)",
            vals["who"] == row["nearest_who_38"] == who
            and abs(vals["dist"] - row["nearest_dist_38"]) <= 0.01
            and abs(dist - row["nearest_dist_38"]) <= 0.01
            and abs(vals["dist"] - sc["clearance_ft"]["1.5s"]) <= 0.01,
            f"{vals['who']} {vals['dist']:.3f} vs {row['nearest_who_38']} {row['nearest_dist_38']:.3f}",
        )
        means = D.drive_means()
        mine = means.loc[sc["drive_id"]]
        am = sc["paired_mean_1_5s_among_helped"]
        pct_le = (
            100.0 * float((means <= mine).sum()) / len(means)
        )  # the JSON counts the drive itself
        R.check(
            f"{tag}: strip n, median, percentile equal the JSON and the 252 means recomputed from the CSV",
            vals["n"] == am["n_helped"] == len(means)
            and abs(vals["med"] - am["median"]) <= 1e-6
            and abs(float(means.median()) - am["median"]) <= 1e-6
            and abs(vals["pct"] - am["percentile"]) <= 1e-6
            and abs(pct_le - am["percentile"]) <= 1e-6
            and abs(mine - sc["paired_mean_1_5s"]) <= 1e-6,
            f"n {vals['n']}/{len(means)}, median {vals['med']:.4f}/{means.median():.4f}, "
            f"pct {vals['pct']:.3f}/{pct_le:.3f}",
        )
        seen.append((s["scene"], json.dumps(vals, sort_keys=True), u["caption"]))
        if k < SCENES_N:
            R.check(f"{tag}: next() returns true", pg.evaluate("wind.next()") is True)
    R.check(
        "next() cycles 0,1,2,3,0 and the captions and numbers differ between scenes",
        [x[0] for x in seen] == [0, 1, 2, 3, 0]
        and len({x[1] for x in seen[:4]}) == 4
        and len({x[2] for x in seen[:4]}) == 4
        and seen[0][1:] == seen[4][1:],
    )

    # The live tile and bars follow t (frame-aligned t, scene 0).
    pg.evaluate("wind.next()") if state(pg)["scene"] != 0 else None
    sc = D.scenes[0]
    live = []
    for f in (0, 12, 25, 38):
        pg.evaluate(f"wind.seek({f} / {D.fps})")
        v = pg.evaluate(
            "[parseFloat(document.getElementById('tile-dist').dataset.value), document.getElementById('tile-who').dataset.who, parseFloat(document.getElementById('bar-toward-1').dataset.value)]"
        )
        who, dist = D.nearest_defender(0, f)
        live.append(
            abs(v[0] - sc["left_clearance"][f]) <= 0.01
            and abs(v[0] - dist) <= 0.01
            and v[1] == who
            and abs(v[2] - sc["to_left"][0][f]) <= 0.01
        )
    R.check(
        "the live tile and bar 1 track t (frames 0, 12, 25, 38: left_clearance, nearest role, to_left)",
        all(live),
        str(live),
    )

    # next() in broadcast: the hook again.
    go_broadcast(pg)
    pg.evaluate("wind.pause()")
    before = state(pg)["scene"]
    pg.evaluate("wind.next()")
    s = state(pg)
    bad = expect_ui(D, s, ui(pg))
    R.check(
        "next() in broadcast: next scene, t restarts, playing, label table holds",
        s["scene"] == (before + 1) % SCENES_N
        and s["phase"] == "playing"
        and s["t"] < 0.3
        and s["view"] == "broadcast"
        and not bad,
        f"{s['view']}/{s['phase']} t={s['t']:.2f}; " + "; ".join(bad[:2]),
    )
    ctx.close()


@guarded
def check_camera(D: Data, browser, target: str) -> None:
    ctx, pg, _ = open_page(browser, target)
    hoop = [D.hoop_x, 0.0, 0.0]
    proj = lambda p: pg.evaluate(PROJ_JS, p)  # noqa: E731

    # True top-down: type, then two coloured tokens through unproject.
    go_plan(pg)
    pg.wait_for_timeout(600)
    R.check(
        "plan: camera().type is orthographic", pg.evaluate("wind.camera().type") == "orthographic"
    )
    R.check("plan: measure visible", vis(pg, "#measure") and vis(pg, "#bar-toward-1"))
    pg.evaluate("wind.seek(1.0)")
    settle(pg)
    sc = D.scenes[0]
    helper_xy, left_xy = D.xy(0, 25)[sc["roles"]["helper"]], D.xy(0, 25)[sc["roles"]["left"]]
    colours = pg.evaluate("wind.colours")
    hexes = [colours["tokens"]["helper"], colours["tokens"]["left"]]
    scan = pg.evaluate(SCAN_JS, [hexes, 10])

    def pick(hexv: str, near_px) -> dict | None:
        comps = [c for c in scan["colours"][hexv]["comps"] if c["n"] >= 40]
        return min(
            comps, key=lambda c: math.hypot(c["x"] - near_px[0], c["y"] - near_px[1]), default=None
        )

    for name, hexv, true_xy, z in (
        ("helper (orange)", hexes[0], helper_xy, 0.15),
        ("man left (near-black)", hexes[1], left_xy, 0.15),
    ):
        near = proj([float(true_xy[0]), float(true_xy[1]), z])
        comp = pick(hexv, near)
        if comp is None:
            R.check(f"top-down true: {name} blob found in the canvas pixels", False, "no blob")
            continue
        got = pg.evaluate("([x, y]) => wind.unproject(x, y)", [comp["x"], comp["y"]])
        err = float(np.hypot(got[0] - true_xy[0], got[1] - true_xy[1]))
        R.check(
            f"top-down true: {name} pixel centroid through unproject within 0.1 ft of xy[25]",
            err <= 0.1,
            f"{err:.3f} ft, blob {comp['n']} px at ({comp['x']:.1f}, {comp['y']:.1f})",
        )

    # Trails: present in plan, absent in broadcast (pixel scan, counts not zero).
    pg.evaluate("wind.seek(wind.T)")
    settle(pg)
    tr = colours["trails"]
    keys = ["helper", "others", "attackers", "handler_def"]
    hx = [tr[k] for k in keys]
    plan_scan = pg.evaluate(SCAN_JS, [hx, 4])["colours"]
    go_broadcast(pg)
    pg.evaluate("wind.seek(wind.T)")
    settle(pg)
    R.check(
        "broadcast: perspective camera, #measure hidden and none of its panels visible",
        pg.evaluate("wind.camera().type") == "perspective"
        and pg.evaluate("document.getElementById('measure').hidden")
        and not any(
            vis(pg, f"#{i}")
            for i in ("measure", "bar-toward-1", "bar-mean", "tile-dist", "strip-n", "strip-median")
        ),
    )
    bc_scan = pg.evaluate(SCAN_JS, [hx, 4])["colours"]
    for k, h in zip(keys, hx, strict=True):
        p, b = plan_scan[h]["count"], bc_scan[h]["count"]
        R.check(
            f"trail colour {k} {h}: many pixels in plan, almost none in broadcast",
            p >= 150 and b <= max(30, 0.05 * p),
            f"plan {p}, broadcast {b}",
        )

    # The flight.
    pg.evaluate("wind.flight(0)")
    settle(pg)
    s0 = state(pg)
    R.check(
        "flight(0): broadcast, perspective camera",
        s0["view"] == "broadcast" and pg.evaluate("wind.camera().type") == "perspective",
    )
    res = []
    for p in (0.25, 0.5, 0.75, 0.999):
        pg.evaluate(f"wind.flight({p})")
        settle(pg)
        s = state(pg)
        res.append((p, s["view"], s["positions"] == s0["positions"], not vis(pg, "#measure")))
    R.check(
        "flight(p) for p in (0.25, 0.5, 0.75, 0.999): reads rising, positions frozen, #measure hidden",
        all(r[1] == "rising" and r[2] and r[3] for r in res),
        str(res),
    )
    pg.evaluate("wind.flight(0.999)")
    settle(pg)
    a = proj(hoop)
    pg.evaluate("wind.flight(1)")
    settle(pg)
    b = proj(hoop)
    sw = float(math.hypot(a[0] - b[0], a[1] - b[1]))
    R.check(
        "swap at flight(0.999) vs flight(1): hoop screen position differs by under 1 px",
        sw < 1.0,
        f"{sw:.3f} px",
    )
    R.check(
        "flight(1): plan, orthographic, #measure visible at once",
        state(pg)["view"] == "plan"
        and pg.evaluate("wind.camera().type") == "orthographic"
        and vis(pg, "#measure"),
    )
    pg.evaluate("wind.flight(0.5)")
    out = pg.evaluate(
        """() => { const a = JSON.stringify(wind.state()), u = JSON.stringify(__ui());
          const r = [wind.play(), wind.pause(), wind.seek(0.2), wind.next(), wind.view('plan'), wind.view('broadcast')];
          return {r: r, same: JSON.stringify(wind.state()) === a, ui: JSON.stringify(__ui()) === u}; }"""
    )
    R.check(
        "rising (flight(0.5)) ignores play, pause, seek, next, view: all false, state and UI unchanged",
        out["r"] == [False] * 6 and out["same"] and out["ui"],
        json.dumps(out),
    )
    bad = expect_ui(D, state(pg), ui(pg))
    R.check(
        "rising: label table (all three buttons and scrubber disabled, caption)",
        not bad,
        "; ".join(bad[:3]),
    )
    pg.evaluate("wind.flight(0)")
    settle(pg)
    R.check(
        "flight(0) after flight(0.5): back to broadcast with the label table",
        not expect_ui(D, state(pg), ui(pg)),
    )
    ctx.close()


@guarded
def check_framing(D: Data, browser, target: str, width: int) -> None:
    ctx, pg, _ = open_page(browser, target, width=width, height=900 if width > 600 else 844)
    out = []
    for i in range(SCENES_N):
        go_broadcast(pg)
        while state(pg)["scene"] != i:
            pg.evaluate("wind.next()")
        pg.evaluate("wind.pause()")
        cam = pg.evaluate("wind.camera()")
        W, H = cam["width"], cam["height"]
        worst = (1e9, 0, 0)
        outside = 0
        for f in range(D.headline + 1):
            pts = [[float(x), float(y), 0.0] for x, y in D.xy(i, f)] + [
                list(map(float, D.ball(i, f)))
            ]
            for p in pts:
                px, py = pg.evaluate(PROJ_JS, p)
                if not (0 <= px <= W and 0 <= py <= H):
                    outside += 1
                worst = (min(worst[0], px, W - px, py, H - py), worst[1], worst[2])
        hx, hy = pg.evaluate(PROJ_JS, [D.hoop_x, 0.0, 0.0])
        hoop_ok = hy >= 0.6 * H and abs(hx - W / 2) <= 0.15 * W
        out.append((i, outside, round(worst[0], 1), hoop_ok))
        go_plan(pg)
        px, py = pg.evaluate(PROJ_JS, [D.hoop_x, 0.0, 0.0])
        out.append(
            (
                i,
                "plan hoop",
                hy >= 0.6 * H and hoop_ok and py >= 0.6 * H and abs(px - W / 2) <= 0.15 * W,
            )
        )
    R.check(
        f"framing at {width}px: every token and the ball inside the canvas on frames 0..38 of all scenes in broadcast; "
        "hoop in the bottom 40 % and within 15 % of centre in broadcast and plan",
        all(o[1] == 0 and o[3] for o in out if len(o) == 4)
        and all(o[2] for o in out if len(o) == 3),
        str(out),
    )
    ctx.close()


@guarded
def check_reduced_motion(D: Data, browser, target: str) -> None:
    ctx, pg, errors = open_page(browser, target, reduced=True)
    T = D.headline / D.fps
    s = state(pg)
    R.check(
        "reduced motion: opens in scene 0, plan, idle, t = T",
        s["scene"] == 0 and s["view"] == "plan" and s["phase"] == "idle" and abs(s["t"] - T) < 1e-9,
        f"{s['view']}/{s['phase']} t={s['t']}",
    )
    R.check(
        "reduced motion: #measure shown (not hidden, bars visible)",
        vis(pg, "#measure") and vis(pg, "#bar-toward-1"),
    )
    R.check(
        "reduced motion: orthographic camera, label table holds",
        pg.evaluate("wind.camera().type") == "orthographic" and not expect_ui(D, s, ui(pg)),
    )
    pg.wait_for_timeout(1200)
    s2 = state(pg)
    R.check(
        "reduced motion: nothing autoplays (t, phase, view unchanged after 1.2 s)",
        s2["t"] == s["t"] and s2["phase"] == "idle" and s2["view"] == "plan",
    )
    pg.evaluate("window.__log.length = 0")
    pg.evaluate("window.__rise.length = 0")
    r1 = pg.evaluate("wind.view('broadcast')")
    s3 = state(pg)
    R.check(
        "reduced motion: view('broadcast') is a cut, idle, t kept, measure hidden",
        r1 is True
        and s3["view"] == "broadcast"
        and s3["phase"] == "idle"
        and s3["t"] == s["t"]
        and not vis(pg, "#measure"),
    )
    r2 = pg.evaluate("wind.view('plan')")
    seen = [state(pg)["view"]]
    for _ in range(25):
        pg.wait_for_timeout(20)
        seen.append(state(pg)["view"])
    log_views = pg.evaluate("window.__log.map(e => e.s.view)")
    R.check(
        "reduced motion: view('plan') lands in plan with no rising in any sample (state, 10 ms log, frozen log)",
        r2 is True
        and seen[-1] == "plan"
        and "rising" not in seen
        and "rising" not in log_views
        and len(pg.evaluate("window.__rise")) == 0,
        f"samples {sorted(set(seen))}, log {log_views}",
    )
    R.check("reduced motion: measure shown right after landing (FADE_S is 0)", vis(pg, "#measure"))
    pg.evaluate("wind.view('broadcast')")
    n0 = state(pg)["scene"]
    pg.evaluate("wind.next()")
    s4 = state(pg)
    pg.wait_for_timeout(700)
    s5 = state(pg)
    R.check(
        "reduced motion: next() in broadcast draws t = 0 and does not autoplay",
        s4["scene"] == (n0 + 1) % SCENES_N
        and s4["t"] == 0
        and s4["phase"] == "idle"
        and s5["t"] == 0
        and s5["phase"] == "idle",
        f"{s4['phase']} t={s4['t']} then t={s5['t']}",
    )
    R.check(
        "reduced motion: wind block not running (field.running() false)",
        pg.evaluate("wind.field.running()") is False,
    )
    pg.evaluate("document.getElementById('league').scrollIntoView()")
    pg.wait_for_timeout(500)
    R.check(
        "reduced motion: field.running() stays false with the wind block on screen",
        pg.evaluate("wind.field.running()") is False,
    )
    ink = lambda: pg.evaluate(  # noqa: E731
        """() => { const c = document.getElementById('wind-flow'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
                   let n = 0, h = 0; for (let i = 3; i < d.length; i += 4) { if (d[i] > 0) { n++; h = (h * 31 + d[i-3] + d[i-2] * 7 + i) | 0; } } return [n, h]; }"""
    )
    a = ink()
    pg.wait_for_timeout(700)
    b = ink()
    R.check(
        "reduced motion: the wind block draws static streamlines (ink present, identical 0.7 s later)",
        a[0] > 200 and a == b,
        f"{a[0]} px of ink; {'identical' if a == b else 'changed'}",
    )
    R.check("reduced motion: no page errors", not errors, "; ".join(errors[:2]))
    ctx.close()

    # Motion allowed: the wind block does animate while on screen (the check above can fail).
    ctx, pg, _ = open_page(browser, target)
    pg.evaluate("document.getElementById('league').scrollIntoView()")
    pg.wait_for_timeout(1200)
    R.check(
        "motion allowed: field.running() is true while the wind block is on screen (so the reduced-motion false means something)",
        pg.evaluate("wind.field.running()") is True,
    )
    ctx.close()


@guarded
def check_numbers(D: Data, browser, target: str) -> None:
    """Every element carrying data-src: its attributes name a file value, and the DOM shows it."""
    ctx, pg, _ = open_page(browser, target)
    go_plan(pg)
    pg.wait_for_timeout(500)
    total = bad_src = bad_show = unverified = 0
    problems: list[str] = []
    done: set[tuple] = set()
    for k in range(SCENES_N):
        pg.evaluate("wind.seek(wind.T)")
        els = pg.evaluate(
            """() => [...document.querySelectorAll('[data-src]')].map(e => ({id: e.id, src: e.dataset.src, row: e.dataset.row || null,
                 col: e.dataset.col || null, value: e.dataset.value, text: e.textContent.trim()}))"""
        )
        for e in els:
            key = (e["src"], e["row"], e["col"], e["value"], e["text"], e["id"])
            if key in done:
                continue
            done.add(key)
            total += 1
            if (
                e["col"] is None
            ):  # the strip's median/percentile: named by id, file wind_scenes.json
                col = {
                    "strip-median": f"scenes.{k}.paired_mean_1_5s_among_helped.median",
                    "strip-percentile": f"scenes.{k}.paired_mean_1_5s_among_helped.percentile",
                }.get(e["id"])
            else:
                col = e["col"]
            try:
                want = source_value(D, e["src"], e["row"], col)
            except (KeyError, ValueError, IndexError) as exc:
                unverified += 1
                problems.append(f"unverified {e['src']} {e['row']} {col}: {exc}")
                continue
            val = float(e["value"])
            if abs(val - want) > 1e-6 * max(1.0, abs(want)):
                bad_src += 1
                problems.append(f"{e['src']} {e['row']} {col}: data-value {val} != file {want}")
            ok, why = shown_matches(e["text"], want)
            if not ok:
                bad_show += 1
                problems.append(f"shown {e['src']} {col}: {why}")
        pg.evaluate("wind.next()")
    R.check(
        "every injected number: data-value equals the file value its data-src/row/col name",
        bad_src == 0,
        f"{total} distinct elements over 4 scenes, {bad_src} differ; "
        + "; ".join(p for p in problems if "data-value" in p)[:300],
    )
    R.check(
        "every injected number: the digits on screen equal that value at the printed precision",
        bad_show == 0,
        f"{bad_show} differ; " + "; ".join(p for p in problems if p.startswith("shown"))[:300],
    )
    R.check(
        "every injected number: a verification rule exists for every data-src element",
        unverified == 0,
        "; ".join(p for p in problems if p.startswith("unverified"))[:300],
    )
    R.check(
        "coverage: the page carries at least the 40 file-sourced numbers the storyboard lists",
        total >= 40,
        f"{total}",
    )
    ctx.close()


@guarded
def check_layout(D: Data, browser, target: str, width: int) -> None:
    height = 844 if width < 600 else 900
    ctx, pg, _ = open_page(browser, target, width=width, height=height)
    for view in ("broadcast", "plan"):
        (go_broadcast if view == "broadcast" else go_plan)(pg)
        pg.wait_for_timeout(500)
        m = pg.evaluate(
            """() => { const de = document.documentElement, b = document.body;
              const r = (id) => document.getElementById(id).getBoundingClientRect().toJSON();
              const small = [...document.querySelectorAll('main p, main li, p, li, summary')]
                .filter(e => e.textContent.trim().length > 0 && !e.closest('svg') && !e.closest('canvas') && __vis(e))
                .map(e => [parseFloat(getComputedStyle(e).fontSize), e.id || e.tagName, e.textContent.trim().slice(0, 30), e.textContent.trim().length])
                .filter(x => x[0] < (x[3] >= 60 ? 16 : 12));
              return {iw: innerWidth, sw: Math.max(de.scrollWidth, b.scrollWidth), body: parseFloat(getComputedStyle(b).fontSize),
                      court: r('court'), measure: r('measure'), small: small,
                      controls: ['play', 'view-broadcast', 'view-plan', 'next', 'scrub'].map(r)}; }"""
        )
        tag = f"{width}px {view}"
        R.check(
            f"{tag}: no horizontal scroll",
            m["sw"] <= m["iw"],
            f"scrollWidth {m['sw']} vs {m['iw']}",
        )
        R.check(f"{tag}: body font >= {BODY_MIN_PX}px", m["body"] >= BODY_MIN_PX, f"{m['body']}px")
        R.check(
            f"{tag}: every visible prose paragraph, list item and summary (60+ chars) >= {BODY_MIN_PX}px, short labels >= 12px",
            not m["small"],
            json.dumps(m["small"][:4]),
        )
        c = m["court"]
        R.check(
            f"{tag}: canvas inside the viewport horizontally",
            c["left"] >= 0 and c["right"] <= m["iw"] + 0.01,
            f"{c['left']:.0f}..{c['right']:.0f} of {m['iw']}",
        )
        ctrl_ok = all(r["left"] >= 0 and r["right"] <= m["iw"] + 0.01 for r in m["controls"])
        R.check(f"{tag}: controls inside the viewport", ctrl_ok)
        if view == "broadcast":
            aspect = c["width"] / c["height"]
            if width < 900:
                R.check(
                    f"{tag}: phone canvas is 1:1 at the content width",
                    abs(aspect - 1) < 0.02 and c["width"] <= width - 20,
                    f"{c['width']:.0f}x{c['height']:.0f}",
                )
            else:
                R.check(
                    f"{tag}: desktop canvas is 4:3, at most 760 px wide",
                    abs(aspect - 4 / 3) < 0.02 and c["width"] <= 760.5,
                    f"{c['width']:.0f}x{c['height']:.0f}",
                )
        else:
            me = m["measure"]
            if width < 900:
                R.check(
                    f"{tag}: #measure stacked under the canvas",
                    me["top"] >= c["bottom"] - 1
                    and me["left"] >= 0
                    and me["right"] <= m["iw"] + 0.01,
                    f"canvas bottom {c['bottom']:.0f}, measure top {me['top']:.0f}",
                )
            else:
                R.check(
                    f"{tag}: #measure beside the canvas",
                    me["left"] >= c["right"] - 1 and me["right"] <= m["iw"] + 0.01,
                    f"canvas right {c['right']:.0f}, measure left {me['left']:.0f}",
                )
    ctx.close()


# ---------------------------------------------------------------- main


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else str(DEFAULT_PAGE)
    target = arg if re.match(r"^https?://", arg) else Path(arg).resolve().as_uri()
    D = Data()
    print(f"target: {target}", flush=True)
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(args=CHROMIUM_ARGS)
        ctx, pg, _ = open_page(browser, target)
        if not webgl_alive(pg):
            R.check(
                "WebGL is live in the browser being driven",
                False,
                "no webgl context; nothing else can be trusted",
            )
            browser.close()
            return 1
        R.check(
            "WebGL is live in the browser being driven",
            True,
            pg.evaluate("navigator.userAgent")[-60:],
        )
        ctx.close()
        check_hook(D, browser, target)
        check_transport(D, browser, target)
        check_scenes(D, browser, target)
        check_camera(D, browser, target)
        check_numbers(D, browser, target)
        check_reduced_motion(D, browser, target)
        for w in (1440, 390):
            check_framing(D, browser, target, w)
            check_layout(D, browser, target, w)
        browser.close()
    n_fail = sum(1 for r in R.rows if not r[0])
    print(f"\n{len(R.rows) - n_fail} passed, {n_fail} failed, {time.time() - t0:.0f} s")
    print("not covered: the hidden-tab clock (headless Chromium cannot hide a tab)")
    return 0 if R.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
