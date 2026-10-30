"""Where the page's start-up goes, cold load by cold load (C1b's open start-up, 2026-10-30).

Run (the `page` extra, like B5)::

    uv run --extra page python scripts/startup_split.py [--rounds N] [--trace DIR] [TARGET ...]

The default targets are the committed page and its GitHub Pages URL, loaded in turn (so a slow
minute of the machine does not land on one target only), each load in a fresh browser on the
machine's GPU with B5's browser arguments and init script: `first paint` is the number B5's
start-up row reads. Per load: Navigation Timing (first byte, download over), the parser's end
(domInteractive, after every inline script has run) and B5's first draw and first paint.

With --trace, every load is also traced (Chromium's timeline and V8's CPU sampler, aligned to
performance.now() by a mark put at the first draw) and the main thread up to the first draw is
split: three.js compiled and run, the page script run, and that run by the start-up call each
CPU sample falls in. Tracing slows the page, so a traced load is read as shares, never as a time.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import defaultdict
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("drive_wind_page", HERE / "drive_wind_page.py")
drv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drv)

URL = "https://javiersr1996.github.io/nobody-helps-the-helper/"
HOOK = "window.__firstDraw = performance.now();"
if drv.INIT_JS.count(HOOK) != 1:
    raise SystemExit("B5's first-draw hook moved; the trace could not be aligned to it")
INIT = drv.INIT_JS.replace(HOOK, HOOK + " performance.mark('firstDraw');")
CATS = ["devtools.timeline", "disabled-by-default-devtools.timeline", "v8", "v8.execute",
        "blink.user_timing", "loading", "toplevel", "disabled-by-default-v8.cpu_profiler"]
# 0-based lines of the two executed <script> elements (the served page has the same lines)
LINES = drv.DEFAULT_PAGE.read_text(encoding="utf-8").splitlines()
THREE = next(i for i, s in enumerate(LINES) if s.startswith('<script id="three-js">'))
PAGE = max(i for i, s in enumerate(LINES) if s.startswith("<script>"))
PERF_JS = """() => ({nav: performance.getEntriesByType('navigation')[0].toJSON(),
  draw: window.__firstDraw, paint: window.__firstPaint})"""


def block(line: int) -> str:
    return "page script" if line >= PAGE else "three.js" if line >= THREE else "-"


def split(ev: list, draw_ms: float) -> dict:
    """The main thread from the time origin to the first draw, from one load's trace."""
    mark = next(e for e in ev if e.get("name") == "firstDraw" and "user_timing" in e.get("cat", ""))
    off = mark["ts"] / 1000 - draw_ms  # trace ms minus performance.now() ms
    lo, hi, thread = off * 1000, mark["ts"], (mark["pid"], mark["tid"])
    scripts = {}
    for e in ev:
        d = e.get("args", {}).get("data", {})
        if (e.get("name") in ("EvaluateScript", "v8.compile") and (e["pid"], e["tid"]) == thread
                and lo <= e["ts"] < hi and d.get("lineNumber") is not None):
            scripts[(e["name"], block(d["lineNumber"] - 1))] = e["dur"] / 1000
    # CPU samples of that thread, each given to its outermost page frame: under the script's top
    # level that is the start-up call it is in (buildStage, warmUp, ...), so the shares add up
    clock = {e["id"]: e["args"]["data"]["startTime"] for e in ev
             if e.get("name") == "Profile" and (e["pid"], e["tid"]) == thread}
    nodes, parent, samples = {}, {}, []
    for e in ev:
        if e.get("name") != "ProfileChunk" or e.get("id") not in clock or e["pid"] != thread[0]:
            continue
        cp = e["args"]["data"].get("cpuProfile", {})
        for n in cp.get("nodes", []):
            nodes[n["id"]] = n["callFrame"]
            if "parent" in n:
                parent[n["id"]] = n["parent"]
        deltas = e["args"]["data"].get("timeDeltas", [])
        for s, dt in zip(cp.get("samples", []), deltas, strict=True):
            clock[e["id"]] += dt
            samples.append((clock[e["id"]], s))
    win = sorted((t, s) for t, s in samples if lo <= t <= hi)
    calls = defaultdict(float)
    for (t, s), (t2, _) in zip(win[:-1], win[1:], strict=True):
        chain, n = [], s
        while n is not None:
            if nodes[n].get("lineNumber", -1) >= PAGE:
                chain.append(nodes[n])
            n = parent.get(n)
        if not chain:
            continue
        top = chain[-1]
        if top["lineNumber"] == PAGE and not top.get("functionName"):
            top = chain[-2] if len(chain) > 1 else {"functionName": "(top level)"}
        name = top.get("functionName") or f"(anonymous, line {top['lineNumber'] + 1})"
        calls[name] += (t2 - t) / 1000
    return {"scripts": scripts, "samples": len(win), "calls": dict(calls)}


def load(p, target: str, trace_dir: Path | None, k: int) -> dict:
    browser = p.chromium.launch(args=drv.CHROMIUM_ARGS)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    ctx.add_init_script(INIT)
    pg = ctx.new_page()
    if trace_dir:
        browser.start_tracing(page=pg, categories=CATS)
    pg.goto(target, wait_until="load")
    pg.wait_for_function("window.__firstPaint !== undefined", timeout=30000)
    r = pg.evaluate(PERF_JS)
    if trace_dir:
        raw = browser.stop_tracing()
        (trace_dir / f"trace_{k}.json").write_bytes(raw)
        r["split"] = split(json.loads(raw)["traceEvents"], r["draw"])
    ctx.close()
    browser.close()
    r["target"] = target
    return r


def show(r: dict) -> None:
    n = r["nav"]
    print(f"{r['target'][:60]:60s} first byte {n['responseStart']:5.0f}  download over"
          f" {n['responseEnd']:5.0f}  parser done {n['domInteractive']:5.0f}  first draw"
          f" {r['draw']:5.0f}  first paint {r['paint']:5.0f} ms"
          f"  ({n['transferSize'] / 1e3:.0f} KB over the wire,"
          f" {n['decodedBodySize'] / 1e3:.0f} KB)")
    if "split" in r:
        S = r["split"]
        s = S["scripts"]
        print(f"    three.js compile {s.get(('v8.compile', 'three.js'), 0):.0f} ms, run"
              f" {s.get(('EvaluateScript', 'three.js'), 0):.0f} ms in all; page script run"
              f" {s.get(('EvaluateScript', 'page script'), 0):.0f} ms; {S['samples']} CPU samples")
        top = sorted(S["calls"].items(), key=lambda kv: -kv[1])[:8]
        print("    page script by start-up call, ms: " + ", ".join(f"{k} {v:.0f}" for k, v in top))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="*", default=[str(drv.DEFAULT_PAGE), URL])
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--trace", type=Path, help="folder for the traces; splits the main thread")
    a = ap.parse_args()
    targets = [t if re.match(r"^https?://", t) else Path(t).resolve().as_uri() for t in a.targets]
    if a.trace:
        a.trace.mkdir(parents=True, exist_ok=True)
    runs = []
    with sync_playwright() as p:
        for _ in range(a.rounds):
            for t in targets:
                runs.append(load(p, t, a.trace, len(runs)))
                show(runs[-1])
    print()
    for t in targets:
        rs = [r for r in runs if r["target"] == t]
        print(f"{t[:60]:60s} first paint " + ", ".join(f"{r['paint'] / 1000:.2f}" for r in rs)
              + " s; download over " + ", ".join(f"{r['nav']['responseEnd']:.0f}" for r in rs)
              + " ms")


if __name__ == "__main__":
    main()
