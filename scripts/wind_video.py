"""D2: the one-minute silent video of "Nobody helps the helper", captured from the built page.

Usage (needs the `page` and `figures` extras and the Playwright Chromium)::

    uv run --extra page --extra figures python scripts/wind_video.py [--out DIR] [--scenes 3,4]

The six scenes and their windows are read from the `[m:ss-m:ss]` headers of
`tasks/video_script_wind.md`, so the script and the cut cannot drift apart. Scenes 1-4 and 6 are
the page itself at 1920x1080 (dpr 1, the machine's GPU), driven from the console frame by frame
(`wind.seek`, `wind.flight`, `wind.view`, never wall-clock playback), one screenshot per frame
at 25 fps. Scene 5 is figure 2, whole, panned down at its own pixel size (it is 1440 x 2678, so
a 1080-high frame cannot hold it readable), under a caption whose numbers are checked against
their CSV. Video-only changes (no controls, no caption line, the tiles moved beside the bars,
a ring on the man left, the title card faded) are CSS and DOM added at capture time; neither the
page nor the template is touched. The MP4 is silent, H.264, and its length is read back with
ffprobe.
"""

from __future__ import annotations

import argparse
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
TOTAL_S, TOTAL_TOL = 60.0, 1.0

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
# then read everything the checks need, so nothing can move between the action and the reading.
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
  let d = '';
  for (let i = 0; i < 72; i++) {
    const a = 2 * Math.PI * i / 72, q = w.project(x + R * Math.cos(a), y + R * Math.sin(a), 0);
    d += (i ? 'L' : 'M') + q[0].toFixed(1) + ' ' + q[1].toFixed(1);
  }
  for (const k of ['back', 'front']) {
    g('vring-' + k).setAttribute('d', d + 'Z');
    g('vring-' + k).style.opacity = String(S.ring);
  }
  const m = (a, v) => [0,1,2,3].map(r => a[r]*v[0] + a[4+r]*v[1] + a[8+r]*v[2] + a[12+r]*v[3]);
  const q = m(cam.projection, m(cam.view, m(cam.world, [x, y, 0, 1])));
  const indep = [(q[0]/q[3]*0.5 + 0.5) * cam.width, (1 - (q[1]/q[3]*0.5 + 0.5)) * cam.height];
  const tg = document.querySelector('#tags .left'), tr = tg ? tg.getBoundingClientRect() : null;
  const V = cam.view, eye = [0,1,2].map(i => -(V[4*i]*V[12] + V[4*i+1]*V[13] + V[4*i+2]*V[14]));
  return {scene: st.scene, t: st.t, view: st.view, phase: st.phase, cam: cam.type, eye: eye,
          man: [x, y], proj: pr, indep: indep, tag: tr ? [tr.x + tr.width / 2, tr.y, tr.width] : null,
          ring: [d.length, S.ring]};
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
    not 60 +- 1 s: the cut must be the length the script was written for."""
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
    if abs(total - TOTAL_S) > TOTAL_TOL:
        raise ValueError(f"the scenes add up to {total} s, not {TOTAL_S} +- {TOTAL_TOL}")
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


# ---------------------------------------------------------------- scene 5: figure 2, whole


PAN = [(0.0, 0), (3.0, 0), (8.0, 900), (13.0, 900), (18.0, 1688), (21.0, 1688)]
BAND = 90


def pan_offset(sec: float) -> float:
    """Pixels of the figure scrolled off the top at `sec` into scene 5: hold, glide, hold."""
    for (t0, y0), (t1, y1) in zip(PAN, PAN[1:], strict=False):
        if sec <= t1:
            if t1 == t0 or y1 == y0:
                return y1
            u = (sec - t0) / (t1 - t0)
            return y0 + (y1 - y0) * u * u * (3 - 2 * u)
    return PAN[-1][1]


def slide_frame(sec: float, fig, caption: str):
    """One frame of scene 5: the figure at its own size, centred on white, scrolled, with the
    caption band along the bottom."""
    from PIL import Image, ImageDraw, ImageFont

    canvas = Image.new("RGB", (W, H), "white")
    view_h = H - BAND
    oy = round(pan_offset(sec))
    canvas.paste(fig.crop((0, oy, fig.width, min(fig.height, oy + view_h))), ((W - fig.width) // 2, 0))
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


def smooth(u: float) -> float:
    return u * u * (3 - 2 * u)


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
            clip, hold, fl = 120, 10, 70
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


def capture(scenes: list[Scene], frames_dir: Path, only: set[int] | None) -> dict[int, int]:
    from drive_wind_page import CHROMIUM_ARGS
    from PIL import Image
    from playwright.sync_api import sync_playwright

    js = json.loads((REPORTS / "wind_scenes.json").read_text(encoding="utf-8"))
    left = js["scenes"][0]["roles"]["left"]
    th = help_step(js)
    fig = Image.open(FIGURE_2).convert("RGB")
    caption = caption_text()
    counts: dict[int, int] = {}
    keyframes: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=CHROMIUM_ARGS)
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1)
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
        print(f"renderer: {renderer}")
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

        last_page: bytes | None = None
        last_slide = slide_frame(21.0, fig, caption)
        prev_eye = None
        for sc in scenes:
            if only and sc.n not in only:
                continue
            g0 = sc.start * FPS
            if sc.n == 5:
                for k in range(sc.frames):
                    img = slide_frame(k / FPS, fig, caption)
                    if k < 10 and last_page is not None:
                        import io

                        prev = Image.open(io.BytesIO(last_page)).convert("RGB")
                        img = Image.blend(prev, img, (k + 1) / 10)
                    img.save(frames_dir / f"{g0 + k:05d}.png")
                counts[5] = sc.frames
                continue
            specs = page_specs(sc, th, hook, w_h, w_end, T)
            held: tuple[str, bytes] | None = None
            for k, s in enumerate(specs):
                key = json.dumps({a: s[a] for a in ("act", "t", "top", "ring", "tile", "p")})
                if s["ring"] > 0:
                    key += f"|{s['clock']}"
                if held and held[0] == key and not (sc.n == 6 and k < 10):
                    png = held[1]
                else:
                    r = pg.evaluate(FRAME_JS, [s, left, 2.4])
                    verify_frame(sc, k, s, r, js, left, prev_eye)
                    prev_eye = r["eye"][1] if s["view"] == "rising" else None
                    if k in (0, sc.frames // 2, sc.frames - 1):
                        keyframes.append(
                            f"scene {sc.n} frame {k}: scene={r['scene']} t={r['t']:.3f} view={r['view']}"
                            f" cam={r['cam']} eye_h={r['eye'][1]:.1f} p={s['p']}")
                    png = pg.screenshot(type="png")
                    held = (key, png)
                if sc.n == 6 and k < 10:
                    import io

                    a = last_slide.convert("RGB")
                    b = Image.open(io.BytesIO(png)).convert("RGB")
                    Image.blend(a, b, (k + 1) / 10).save(frames_dir / f"{g0 + k:05d}.png")
                else:
                    (frames_dir / f"{g0 + k:05d}.png").write_bytes(png)
                last_page = png
            counts[sc.n] = sc.frames
        if errors:
            raise SystemExit("page errors while filming: " + "; ".join(errors[:2]))
        browser.close()
    print("\n".join(keyframes))
    return counts


def verify_frame(sc: Scene, k: int, s: dict, r: dict, js: dict, left: int, prev_eye) -> None:
    """The state machine, asserted per frame from what the page itself reported."""
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
        if tag is None or abs(tag[0] - r["proj"][0]) > 120 or tag[1] > r["proj"][1]:
            raise SystemExit(f"{where}: the page's own 'the man he left' tag {tag} is not over the ring at {r['proj']}")
    # (the landing frame swaps to the orthographic camera, whose eye height is its own number)
    if s["view"] == "rising" and prev_eye is not None and r["eye"][1] < prev_eye - 1e-6:
        raise SystemExit(f"{where}: the camera went down during the rise")


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
    if abs(dur - TOTAL_S) > TOTAL_TOL or nb != total_frames:
        raise SystemExit(f"length {dur:.3f} s / {nb} frames, want {TOTAL_S} +- {TOTAL_TOL} s / {total_frames}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "video")
    ap.add_argument("--scenes", default="", help="comma list: film only these scenes, no MP4")
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()
    scenes = parse_script(SCRIPT.read_text(encoding="utf-8"))
    only = {int(x) for x in args.scenes.split(",") if x} or None
    frames_dir = args.out / "wind_frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True)
    for sc in scenes:
        print(f"scene {sc.n}: {sc.start}-{sc.end} s, {sc.frames} frames, {sc.name}")
    counts = capture(scenes, frames_dir, only)
    print("frames per scene:", counts)
    if only:
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
