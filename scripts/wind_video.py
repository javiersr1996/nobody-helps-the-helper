"""D2: the one-minute silent video of "Nobody helps the helper", captured from the built page.

Usage (needs the `page` and `figures` extras and the Playwright Chromium)::

    uv run --extra page --extra figures python scripts/wind_video.py [--out DIR] [--scenes 3,4]
                                                                   [--frame-stats]

The six scenes and their windows are read from the `[m:ss-m:ss]` headers of
`tasks/video_script_wind.md`, so the script and the cut cannot drift apart; together they must
last 60 s or less. Scenes 1-4 and 6 are the page itself (viewport 1920x1080, device scale 2, the
machine's GPU), driven from the console frame by frame (`wind.seek`, `wind.flight`,
`wind.view`, never wall-clock playback), one screenshot per frame at 25 fps. For the phone, the
video is framed and not only filmed: in scenes 1-4 each frame is cropped to the tightest 16:9
window that holds the seven story players (handler, his defender, helper, man left, the three
others; feet to head; `--all-ten` adds the off-ball attackers, which pins the zoom at 1.00x because
they stand at the frame edge), their tags, the ring and, while it shows, the
title card, plus a margin, smoothed in time and never zoomed past 2x; the tags are set larger
by CSS injected before the page loads (so the page's own placement sees the larger boxes).
Scene 5 is figure 2, from the PNG the README carries and not redrawn, as two held crops cut on
the line (court panel, then the interval panel), under a caption whose numbers are checked
against their CSV. Everything the video adds is CSS and DOM at capture time; neither the page
nor the template is touched. The MP4 is silent, H.264, and its length is read back with
ffprobe.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
PAGE = REPORTS / "nobody_helps_the_helper.html"
SCRIPT = ROOT / "tasks" / "video_script_wind.md"
FIGURE_2 = REPORTS / "figures" / "wind_figure_2_who_covers.png"
SUMMARY = REPORTS / "help_kinds_summary.csv"
FPS = 25
W, H = 1920, 1080
DPR = 2
TOTAL_MIN, TOTAL_MAX = 59.0, 60.0  # a minute: not a second over
ZOOM_MAX, MARGIN, SIGMA = 2.0, 40.0, 12  # the crop: 2x at most, px of margin, frames of smoothing

# Larger tags, set before the page's own script measures them.
TAG_JS = """
(() => {
  const s = document.createElement('style');
  s.textContent = '.tag{font-size:24px !important;padding:2px 6px !important}'
    + '.tag.other{font-size:26px !important}';
  const add = () => (document.head || document.documentElement).appendChild(s);
  if (document.documentElement) add();
  else new MutationObserver((m, o) => { if (document.documentElement) { o.disconnect(); add(); } })
    .observe(document, {childList: true});
})();
"""

# What the capture adds to the page, only while it films: no controls, no live caption line,
# the live tile or the result tile stacked under the bars, the title card faded by script.
VIDEO_CSS = """
html, body { overflow: hidden !important; }
#controls { display: none !important; }
#stage-caption { visibility: hidden !important; }
#tile, #result-tile { position: fixed !important; left: 1536px; top: 458px; width: 384px;
  box-sizing: border-box; margin: 0 !important; z-index: 5; }
#vring { position: fixed; left: 0; top: 0; width: 1920px; height: 1080px;
  pointer-events: none; z-index: 40; }
"""

INSTALL_JS = """
([css]) => {
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.id = 'vring'; svg.setAttribute('viewBox', '0 0 1920 1080');
  for (const [k, w, c, o] of [['back', 13, '#000', 0.55], ['front', 6, '#fff', 1]]) {
    const p = document.createElementNS(ns, 'path');
    p.id = 'vring-' + k; p.setAttribute('fill', 'none'); p.setAttribute('stroke', c);
    p.setAttribute('stroke-width', w); p.setAttribute('stroke-opacity', o);
    p.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(p);
  }
  document.body.appendChild(svg);
  return true;
}
"""

# One evaluate per frame: act on the page, lay the overlays out, wait two animation frames,
# then read everything the checks and the framing need, so nothing can move between the action
# and the reading. The ten players are projected at the feet and at head height (6.5 ft).
FRAME_JS = """
async ([S, left, radius]) => {
  const w = window.wind, g = (i) => document.getElementById(i);
  if (S.act === 'seek') { if (w.state().view !== 'broadcast') w.view('broadcast'); w.seek(S.t); }
  else if (S.act === 'flight') { w.flight(S.p); }
  else if (S.act === 'plan') { if (w.state().view !== 'plan') w.flight(1); w.seek(S.t); }
  g('top').style.opacity = String(S.top);
  g('tile').style.display = S.tile === 'tile' ? '' : 'none';
  g('result-tile').style.display = S.tile === 'result' ? '' : 'none';
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  const st = w.state(), cam = w.camera();
  const [x, y] = st.positions.players[left];
  const pr = w.project(x, y, 0);
  const R = radius * (1 + 0.1 * Math.sin(2 * Math.PI * S.clock));
  let d = '', rb = [1e9, 1e9, -1e9, -1e9];
  for (let i = 0; i < 72; i++) {
    const a = 2 * Math.PI * i / 72, q = w.project(x + R * Math.cos(a), y + R * Math.sin(a), 0);
    d += (i ? 'L' : 'M') + q[0].toFixed(1) + ' ' + q[1].toFixed(1);
    rb = [Math.min(rb[0], q[0]), Math.min(rb[1], q[1]), Math.max(rb[2], q[0]), Math.max(rb[3], q[1])];
  }
  for (const k of ['back', 'front']) {
    g('vring-' + k).setAttribute('d', d + 'Z');
    g('vring-' + k).style.opacity = String(S.ring);
  }
  const m = (a, v) => [0,1,2,3].map(r => a[r]*v[0] + a[4+r]*v[1] + a[8+r]*v[2] + a[12+r]*v[3]);
  const q = m(cam.projection, m(cam.view, m(cam.world, [x, y, 0, 1])));
  const indep = [(q[0]/q[3]*0.5 + 0.5) * cam.width, (1 - (q[1]/q[3]*0.5 + 0.5)) * cam.height];
  const box = (e) => { const b = e.getBoundingClientRect(); return [b.x, b.y, b.x + b.width, b.y + b.height]; };
  const tg = document.querySelector('#tags .left'), tr = tg ? tg.getBoundingClientRect() : null;
  const tags = Array.from(document.querySelectorAll('#tags .tag')).map(box).filter(b => b[2] > b[0]);
  const pts = st.positions.players.flatMap(p => [w.project(p[0], p[1], 0), w.project(p[0], p[1], 6.5)]);
  const V = cam.view, eye = [0,1,2].map(i => -(V[4*i]*V[12] + V[4*i+1]*V[13] + V[4*i+2]*V[14]));
  return {scene: st.scene, t: st.t, view: st.view, phase: st.phase, cam: cam.type, eye: eye,
          man: [x, y], proj: pr, indep: indep, tag: tr ? [tr.x + tr.width / 2, tr.y, tr.width] : null,
          pts: pts, tags: tags, ringbox: rb, card: box(g('top')), ring: [d.length, S.ring]};
}
"""


# ---------------------------------------------------------------- the script's windows


@dataclass(frozen=True)
class Scene:
    n: int
    start: int
    end: int
    name: str
    line: str

    @property
    def frames(self) -> int:
        return (self.end - self.start) * FPS


HEADER = re.compile(r"^\*\*\[(\d+):(\d{2})-(\d+):(\d{2})\] Scene (\d+), ([^.]*)\.\*\*")


def parse_script(text: str) -> list[Scene]:
    """The scenes, in order, from the `**[m:ss-m:ss] Scene N, name.**` headers and the quoted
    lines (`>`) under each. Refuses windows that are not contiguous from 0, or a total that is
    not a minute: 59 to 60 s, never over."""
    scenes: list[Scene] = []
    for ln in text.splitlines():
        m = HEADER.match(ln)
        if m:
            a, b, c, d = (int(m.group(i)) for i in range(1, 5))
            scenes.append(Scene(int(m.group(5)), a * 60 + b, c * 60 + d, m.group(6), ""))
        elif ln.startswith(">") and scenes:
            last = scenes[-1]
            joined = (last.line + " " + ln.lstrip("> ").strip()).strip()
            scenes[-1] = Scene(last.n, last.start, last.end, last.name, joined)
    if not scenes:
        raise ValueError("no scene headers found")
    if scenes[0].start != 0:
        raise ValueError(f"the first scene starts at {scenes[0].start} s, not 0")
    for prev, nxt in zip(scenes, scenes[1:], strict=False):
        if nxt.start != prev.end:
            raise ValueError(f"scene {prev.n} ends at {prev.end} s, scene {nxt.n} starts at {nxt.start}")
    for s in scenes:
        if s.end <= s.start:
            raise ValueError(f"scene {s.n} has no length")
    total = scenes[-1].end
    if not TOTAL_MIN <= total <= TOTAL_MAX:
        raise ValueError(f"the scenes add up to {total} s, not {TOTAL_MIN} to {TOTAL_MAX}")
    return scenes


# ---------------------------------------------------------------- numbers typed on a slide


def caption_cells() -> dict[str, float]:
    """The values a caption may quote, each read from help_kinds_summary.csv."""
    df = pd.read_csv(SUMMARY)
    c = df[(df.measure == "contrast") & (df.kind == "near_committed") & (df.variant == "primary")
           & np.isclose(df.horizon, 1.52)]
    if len(c) != 1:
        raise ValueError("help_kinds_summary.csv: no single near_committed primary row at 1.52 s")
    r = c.iloc[0]
    n_all = df[(df.measure == "count") & (df.kind == "drives") & (df.variant == "resolved")]
    return {"flagged drives": float(r.n), "resolved drives": float(n_all.n.iloc[0]),
            "contrast mean": float(r["mean"]), "ci low": float(r.ci_low), "ci high": float(r.ci_high)}


NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def check_slide_numbers(text: str, cells: dict[str, float]) -> list[str]:
    """Every number typed on a slide must equal one of the CSV cells at the precision it is
    printed with. Returns the numbers found; raises ValueError naming the first that is not."""
    found = NUMBER.findall(text)
    for tok in found:
        dec = len(tok.split(".")[1]) if "." in tok else 0
        if not any(round(v, dec) == float(tok) for v in cells.values()):
            raise ValueError(f"the slide types {tok}, which no cell of {SUMMARY.name} gives")
    return found


def caption_text() -> str:
    c = caption_cells()
    text = (f"{c['flagged drives']:.0f} of {c['resolved drives']:.0f} drives look like this"
            f"      {c['contrast mean']:.2f} ft (CI {c['ci low']:.2f} to {c['ci high']:.2f})")
    check_slide_numbers(text, c)
    return text


# ---------------------------------------------------------------- scene 5: figure 2, held crops

BAND = 90
#: Crops of the README's PNG (1440 x 2678), x0, y0, x1, y1, and the second at which each is shown.
#: Cut times come from the guide voice's word boundaries (edge-tts, en-GB-RyanNeural): the line
#: "Compared with drives where the nearest defender stays home" starts 13.70 s in; the cut is
#: 0.2 s earlier, since another voice will be slower or faster and an early cut is the safer.
CROPS = [(0.0, (0, 0, 1440, 1240)), (13.5, (0, 1495, 1440, 2678))]
DISSOLVE = 6


def crop_index(sec: float) -> int:
    return max(i for i, (t0, _) in enumerate(CROPS) if sec >= t0)


def slide_frame(sec: float, fig, caption: str):
    """One frame of scene 5: a held crop of the figure at its largest size that fits above the
    caption bar, centred on white, a short dissolve at each cut."""
    from PIL import Image, ImageDraw, ImageFont

    view_h = H - BAND

    def crop(i: int):
        im = fig.crop(CROPS[i][1])
        s = view_h / im.height
        im = im.resize((round(im.width * s), view_h), Image.LANCZOS)
        c = Image.new("RGB", (W, H), "white")
        c.paste(im, ((W - im.width) // 2, 0))
        return c

    i = crop_index(sec)
    canvas = crop(i)
    since = sec - CROPS[i][0]
    if i > 0 and since < DISSOLVE / FPS:
        canvas = Image.blend(crop(i - 1), canvas, min(1.0, (since * FPS + 1) / (DISSOLVE + 1)))
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, view_h, W, H), fill="white")
    d.rectangle((0, view_h, W, view_h + 5), fill="#f0a33c")
    import matplotlib

    font = ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans-Bold.ttf"), 38)
    box = d.textbbox((0, 0), caption, font=font)
    d.text(((W - (box[2] - box[0])) / 2, view_h + (BAND - 5 - (box[3] - box[1])) / 2 + 3), caption,
           fill="#1a1a1a", font=font)
    return canvas


# ---------------------------------------------------------------- the frame plan


def page_specs(scene: Scene, th: float, hook, w_h: float, w_end: float, t_end: float) -> list[dict]:
    """One spec per frame of a page scene. `hook` is the page's own clip time at wall second w."""
    n = scene.frames
    out: list[dict] = []
    for k in range(n):
        s = {"act": "seek", "t": 0.0, "top": 0.0, "ring": 0.0, "tile": None, "view": "broadcast",
             "p": None, "clock": (scene.start * FPS + k) / FPS}
        if scene.n == 1:
            s.update(t=0.0, top=1.0)
        elif scene.n == 2:
            s.update(t=hook(w_h * k / n), top=max(0.0, 1 - k / 15))
        elif scene.n == 3:
            s.update(t=th, ring=min(1.0, k / 12))
        elif scene.n == 4:
            clip, hold, fl = 100, 10, 65
            if k < clip:
                s.update(t=hook(w_h + (w_end - w_h) * (k + 1) / clip), ring=1.0)
            elif k < clip + hold:
                s.update(t=t_end, ring=1.0)
            elif k < clip + hold + fl:
                j = k - clip - hold
                s.update(act="flight", t=t_end, p=(j + 1) / fl, view="rising" if j + 1 < fl else "plan",
                         ring=max(0.0, 1 - j / 10), tile="tile" if j + 1 == fl else None)
            else:
                s.update(act="plan", t=t_end, view="plan", p=1.0, tile="tile")
        elif scene.n == 6:
            s.update(act="plan", t=t_end, view="plan", p=1.0, tile="result", top=min(1.0, k / 15))
        out.append(s)
    return out


# ---------------------------------------------------------------- framing


def need_box(r: dict, s: dict, slots=None):
    """The box a broadcast frame must keep in view: ten players feet to head, their tags, the
    ring while it shows, the title card while it is up. None for the views framed whole."""
    if s["view"] != "broadcast":
        return None
    keep = range(10) if slots is None else slots
    pts = [tuple(p) for i in keep for p in r["pts"][2 * i: 2 * i + 2]]
    for t in r["tags"]:
        pts += [(t[0], t[1]), (t[2], t[3])]
    if s["ring"] > 0.05:
        b = r["ringbox"]
        pts += [(b[0], b[1]), (b[2], b[3])]
    if s["top"] > 0.5:
        c = r["card"]
        pts += [(c[0], c[1]), (c[2], c[3])]
    xs = [min(max(x, 0), W) for x, _ in pts]
    ys = [min(max(y, 0), H) for _, y in pts]
    return min(xs), min(ys), max(xs), max(ys)


def gauss(a: np.ndarray, sigma: float = SIGMA) -> np.ndarray:
    k = np.exp(-0.5 * (np.arange(-3 * sigma, 3 * sigma + 1) / sigma) ** 2)
    k /= k.sum()
    return np.convolve(np.pad(a, 3 * sigma, mode="edge"), k, mode="valid")


def plan_crops(boxes: list) -> np.ndarray:
    """One (x0, y0, width) crop per frame from the boxes to keep in view: the box plus a margin
    as a 16:9 window, widths dilated by a running maximum (so the zoom-out leads the need) and
    smoothed, centres smoothed, then widened wherever smoothing left something out."""
    n = len(boxes)
    tw, cx, cy = np.empty(n), np.empty(n), np.empty(n)
    for i, b in enumerate(boxes):
        if b is None:
            tw[i], cx[i], cy[i] = W, W / 2, H / 2
            continue
        bw, bh = b[2] - b[0] + 2 * MARGIN, b[3] - b[1] + 2 * MARGIN
        tw[i] = min(W, max(bw, bh * 16 / 9, W / ZOOM_MAX))
        cx[i], cy[i] = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    for _ in range(12):
        dil = np.array([tw[max(0, i - int(1.5 * SIGMA)): i + int(1.5 * SIGMA) + 1].max() for i in range(n)])
        ws = np.clip(gauss(dil), W / ZOOM_MAX, W)
        xs = np.clip(gauss(cx), ws / 2, W - ws / 2)
        ys = np.clip(gauss(cy), ws * 9 / 32, H - ws * 9 / 32)
        grew = False
        for i, b in enumerate(boxes):
            if b is None:
                continue
            dx = max(xs[i] - b[0], b[2] - xs[i]) + 16
            dy = max(ys[i] - b[1], b[3] - ys[i]) + 16
            need = max(2 * dx, dy * 32 / 9)
            if need > ws[i] + 0.5 and ws[i] < W:
                tw[i] = max(tw[i], min(W, need + 10))
                grew = True
        if not grew:
            break
    return np.stack([xs - ws / 2, ys - ws * 9 / 32, ws], axis=1)


# ---------------------------------------------------------------- capture


def interp_xy(js: dict, t: float, slot: int) -> np.ndarray:
    xy = js["scenes"][0]["xy"]
    f = min(max(t * js["fps"], 0), len(xy) - 1)
    i = int(math.floor(f))
    j = min(i + 1, len(xy) - 1)
    a, b = np.array(xy[i][slot], float), np.array(xy[j][slot], float)
    return a + (b - a) * (f - i)


def help_step(js: dict) -> float:
    """t_h, the centre of the slow-down: the first frame at which the helper has covered half
    of his path to frame 25 (the page's clockOf rule, recomputed here from the JSON)."""
    h = js["scenes"][0]["roles"]["helper"]
    series = np.array([f[h] for f in js["scenes"][0]["xy"]], float)[:26]
    cum = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(series, axis=0).T))])
    return int(np.argmax(cum >= cum[-1] / 2)) / js["fps"]


def capture(scenes: list[Scene], frames_dir: Path, only: set[int] | None, stats_only: bool,
            story: bool = False) -> dict[int, int]:
    from drive_wind_page import CHROMIUM_ARGS
    from PIL import Image
    from playwright.sync_api import sync_playwright

    js = json.loads((REPORTS / "wind_scenes.json").read_text(encoding="utf-8"))
    roles = js["scenes"][0]["roles"]
    left = roles["left"]
    slots = [roles[k] for k in ("handler", "handler_def", "helper", "left")] + roles["others"] if story else None
    th = help_step(js)
    fig = Image.open(FIGURE_2).convert("RGB")
    caption = caption_text()
    counts: dict[int, int] = {}
    keyframes: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=CHROMIUM_ARGS)
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=DPR)
        ctx.add_init_script(TAG_JS)
        pg = ctx.new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(PAGE.as_uri(), wait_until="load")
        pg.wait_for_function("window.wind && wind.state && document.getElementById('play')", timeout=30000)
        pg.evaluate("wind.pause()")
        pg.evaluate("wind.seek(0)")
        renderer = pg.evaluate(
            "(() => { const c = document.createElement('canvas').getContext('webgl');"
            " const e = c.getExtension('WEBGL_debug_renderer_info');"
            " return e ? c.getParameter(e.UNMASKED_RENDERER_WEBGL) : 'unknown'; })()")
        if re.search(r"swiftshader|software|llvmpipe", renderer, re.I):
            raise SystemExit(f"software renderer ({renderer}): the video must be filmed on the GPU")
        print(f"renderer: {renderer}; device scale {pg.evaluate('devicePixelRatio')}")
        pg.evaluate(INSTALL_JS, [VIDEO_CSS])
        T, RATE = pg.evaluate("[wind.T, wind.RATE]")

        # the page's own slow-down centre, from its hookTime: the clip rate is lowest at the help
        # step, so the wall second where d(hookTime)/dw is smallest sits at the centre
        ws = np.linspace(0, T / RATE, 3041)
        ts = np.array(pg.evaluate("(ws) => ws.map(w => wind.hookTime(w))", ws.tolist()))
        page_centre = float(ts[int(np.argmin(np.gradient(ts, ws)))])
        if abs(page_centre - th) > 0.05:
            raise SystemExit(f"help step {th:.2f} s from the JSON, {page_centre:.2f} s from hookTime")
        # the wall second at which the page's clock reaches t_h (hookTime is monotone)
        lo, hi = 0.0, T / RATE
        for _ in range(50):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if pg.evaluate("(w) => wind.hookTime(w)", mid) < th else (lo, mid)
        w_h, w_end = (lo + hi) / 2, T / RATE
        print(f"t_h = {th:.2f} s (JSON), {page_centre:.3f} s (hookTime); wall {w_h:.3f} of {w_end:.2f} s")
        hook = lambda w: float(pg.evaluate("(w) => wind.hookTime(w)", w))  # noqa: E731

        wanted = [sc for sc in scenes if sc.n != 5 and (not only or sc.n in only)]
        specs = {sc.n: page_specs(sc, th, hook, w_h, w_end, T) for sc in wanted}

        # pass 1: what each broadcast frame of scenes 1-4 must keep in view, then the crops
        series = [(sc.n, k) for sc in wanted if sc.n < 5 for k in range(sc.frames)]
        boxes = []
        for n, k in series:
            s = specs[n][k]
            r = pg.evaluate(FRAME_JS, [s, left, 2.4]) if s["view"] == "broadcast" else None
            boxes.append(need_box(r, s, slots) if r else None)
        crops = plan_crops(boxes) if boxes else np.zeros((0, 3))
        crop_of = dict(zip(series, crops, strict=True))
        zoom = W / crops[:, 2] if len(crops) else np.array([1.0])
        print(f"zoom over scenes 1-4: min {zoom.min():.2f}, median {np.median(zoom):.2f}, max {zoom.max():.2f}")
        for n in sorted({n for n, _ in series}):
            z = np.array([W / crop_of[(n, k)][2] for k in range(len(specs[n]))])
            print(f"  scene {n}: zoom {z.min():.2f} to {z.max():.2f}")
        if stats_only:
            browser.close()
            return counts

        last_page = None
        last_slide = slide_frame(sum(sc.frames for sc in scenes if sc.n == 5) / FPS - 1e-3, fig, caption)
        prev_eye = None
        for sc in scenes:
            if only and sc.n not in only:
                continue
            g0 = sc.start * FPS
            if sc.n == 5:
                for k in range(sc.frames):
                    img = slide_frame(k / FPS, fig, caption)
                    if k < 10 and last_page is not None:
                        img = Image.blend(last_page, img, (k + 1) / 10)
                    img.save(frames_dir / f"{g0 + k:05d}.png", compress_level=1)
                counts[5] = sc.frames
                continue
            held = None
            for k, s in enumerate(specs[sc.n]):
                cx0, cy0, cw = crop_of.get((sc.n, k), (0.0, 0.0, float(W)))
                ch = cw * 9 / 16
                key = json.dumps({a: s[a] for a in ("act", "t", "top", "ring", "tile", "p")})
                key += f"|{cx0:.2f},{cy0:.2f},{cw:.2f}"
                if s["ring"] > 0:
                    key += f"|{s['clock']}"
                if held and held[0] == key and not (sc.n == 6 and k < 10):
                    img = held[1]
                else:
                    r = pg.evaluate(FRAME_JS, [s, left, 2.4])
                    verify_frame(sc, k, s, r, js, left, prev_eye, (cx0, cy0, cw, ch), slots)
                    prev_eye = r["eye"][1] if s["view"] == "rising" else None
                    if k in (0, sc.frames // 2, sc.frames - 1):
                        keyframes.append(
                            f"scene {sc.n} frame {k}: scene={r['scene']} t={r['t']:.3f} view={r['view']}"
                            f" cam={r['cam']} eye_h={r['eye'][1]:.1f} p={s['p']} zoom={W / cw:.2f}")
                    shot = pg.screenshot(type="jpeg", quality=95,
                                         clip={"x": cx0, "y": cy0, "width": cw, "height": ch})
                    img = Image.open(io.BytesIO(shot)).convert("RGB").resize((W, H), Image.LANCZOS)
                    held = (key, img)
                if sc.n == 6 and k < 10:
                    img = Image.blend(last_slide.convert("RGB"), img, (k + 1) / 10)
                img.save(frames_dir / f"{g0 + k:05d}.png", compress_level=1)
                last_page = held[1] if held else img
            counts[sc.n] = sc.frames
        if errors:
            raise SystemExit("page errors while filming: " + "; ".join(errors[:2]))
        browser.close()
    print("\n".join(keyframes))
    return counts


def verify_frame(sc: Scene, k: int, s: dict, r: dict, js: dict, left: int, prev_eye, crop, slots=None) -> None:
    """The state machine and the framing, asserted per frame from what the page itself reported."""
    where = f"scene {sc.n} frame {k}"
    if r["scene"] != 0:
        raise SystemExit(f"{where}: page scene {r['scene']}, want 0")
    if r["view"] != s["view"]:
        raise SystemExit(f"{where}: view {r['view']}, want {s['view']}")
    if abs(r["t"] - s["t"]) > 1e-6:
        raise SystemExit(f"{where}: t {r['t']}, want {s['t']}")
    if (r["cam"] == "orthographic") != (s["view"] == "plan"):
        raise SystemExit(f"{where}: camera {r['cam']} in view {s['view']}")
    dx = math.hypot(r["proj"][0] - r["indep"][0], r["proj"][1] - r["indep"][1])
    if dx > 0.5:
        raise SystemExit(f"{where}: the page's projection of the man left differs {dx:.2f} px from the camera matrices")
    want = interp_xy(js, r["t"], left)
    if math.hypot(*(np.array(r["man"]) - want)) > 0.01:
        raise SystemExit(f"{where}: man left at {r['man']}, the JSON has {want.tolist()}")
    if s["ring"] > 0 and s["view"] == "broadcast":
        tag = r["tag"]
        if tag is None or abs(tag[0] - r["proj"][0]) > 160 or tag[1] > r["proj"][1]:
            raise SystemExit(f"{where}: the page's own 'the man he left' tag {tag} is not over the ring at {r['proj']}")
    # (the landing frame swaps to the orthographic camera, whose eye height is its own number)
    if s["view"] == "rising" and prev_eye is not None and r["eye"][1] < prev_eye - 1e-6:
        raise SystemExit(f"{where}: the camera went down during the rise")
    # in crop coordinates: nobody clipped, and the ring on the man left inside the frame
    x0, y0, cw, ch = crop
    to = lambda p: ((p[0] - x0) * W / cw, (p[1] - y0) * H / ch)  # noqa: E731
    if s["view"] == "broadcast" and cw < W - 0.5:
        inside = lambda px, py: -2 <= px <= W + 2 and -2 <= py <= H + 2  # noqa: E731
        for name, pts in (("player", [(max(0, min(W, x)), max(0, min(H, y))) for i in (range(10) if slots is None else slots) for x, y in r["pts"][2 * i: 2 * i + 2]]),
                          ("tag", [(t[0], t[1]) for t in r["tags"]] + [(t[2], t[3]) for t in r["tags"]])):
            for p in pts:
                if not inside(*to(p)):
                    raise SystemExit(f"{where}: a {name} at {p} falls outside the crop {crop}")
    if s["ring"] > 0.05 and s["view"] == "broadcast":
        b = r["ringbox"]
        for p in ((b[0], b[1]), (b[2], b[3]), tuple(r["proj"])):
            px, py = to(p)
            if not (0 <= px <= W and 0 <= py <= H):
                raise SystemExit(f"{where}: the ring ({px:.0f}, {py:.0f}) is outside the frame")


# ---------------------------------------------------------------- ffmpeg


def probe(mp4: Path, entry: str, *extra: str) -> str:
    out = subprocess.run(["ffprobe", "-v", "error", *extra, "-show_entries", entry,
                          "-of", "default=nw=1:nk=1", str(mp4)], capture_output=True, text=True)
    return out.stdout.strip()


def assemble(frames_dir: Path, mp4: Path, total_frames: int) -> None:
    cmd = ["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(frames_dir / "%05d.png"),
           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-an",
           "-movflags", "+faststart", str(mp4)]
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(done.stderr[-800:])
    dur = float(probe(mp4, "format=duration"))
    nb = int(probe(mp4, "stream=nb_read_frames", "-count_frames", "-select_streams", "v:0"))
    size = probe(mp4, "stream=width,height", "-select_streams", "v:0").replace("\n", "x")
    print(f"wrote {mp4} ({mp4.stat().st_size / 1e6:.1f} MB): ffprobe {dur:.3f} s, {nb} frames, {size}")
    if not TOTAL_MIN <= dur <= TOTAL_MAX or nb != total_frames:
        raise SystemExit(f"length {dur:.3f} s / {nb} frames, want {TOTAL_MIN} to {TOTAL_MAX} s / {total_frames}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "video")
    ap.add_argument("--scenes", default="", help="comma list: film only these scenes, no MP4")
    ap.add_argument("--frame-stats", action="store_true", help="plan the crops, print the zoom, film nothing")
    ap.add_argument("--all-ten", action="store_true",
                    help="frame all ten players (the crop then stays at 1.00x: the off-ball attackers stand at the edge)")
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()
    scenes = parse_script(SCRIPT.read_text(encoding="utf-8"))
    only = {int(x) for x in args.scenes.split(",") if x} or None
    frames_dir = args.out / "wind_frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True)
    for sc in scenes:
        print(f"scene {sc.n}: {sc.start}-{sc.end} s, {sc.frames} frames, {sc.name}")
    counts = capture(scenes, frames_dir, only, args.frame_stats, not args.all_ten)
    print("frames per scene:", counts)
    if only or args.frame_stats:
        return 0
    total = sum(s.frames for s in scenes)
    written = len(list(frames_dir.glob("*.png")))
    if written != total or counts != {s.n: s.frames for s in scenes}:
        raise SystemExit(f"{written} frames written, {total} planned")
    assemble(frames_dir, args.out / "nobody_helps_the_helper.mp4", total)
    if not args.keep_frames:
        shutil.rmtree(frames_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
