# The 1-minute video, "Nobody helps the helper" (D1)

Rules: one minute, own voice, English. It is the argument, not a summary of the README. The
picture is the silent cut built by D2 (`scripts/wind_video.py`): the drive captured from the page
frame by frame (`wind.seek(t)`, `wind.flight(p)`, `wind.view(name)`, `wind.next()`) and the two
figures whole. Every number spoken appears in `README.md` (checked at the end). Never say or
imply that a defender chose, decided or read anything, and never say where help comes from:
the work measures displacements and distances. Record in one pass over the cut; at 2.6 words
per second each line fills its scene.

---

**[0:00-0:08] Scene 1, the hook: one drive in 3D.** On screen: the page in `broadcast`, scene 0
(game 114243, the pull-up), `wind.view("broadcast")`, then `wind.seek(hookTime(k / 25))` for
t = 0 to 1.52, the slow-motion run; no numbers, no caption text on the slide.

> Ten basketball games, tracked. One drive. Watch the defender who steps toward the ball, and
> watch the man he leaves.

**[0:08-0:23] Scene 2, the helper and the man left.** On screen: the freeze at t = 1.52
(`wind.seek(1.52)`, broadcast), held, then the opening of the rise, `wind.flight(p)` for
p = 0 to 0.4. Still no numbers drawn.

> The helper moves at least four feet toward where the ball goes. A second and
> a half later the man he leaves is open in 58.3 percent of drives, up from 41.5; without a
> helper, 62.3 up to 75.9.

**[0:23-0:29] Scene 3, the camera rises to the measure.** On screen: `wind.flight(p)` for
p = 0.4 to 1, landing in `plan` (`wind.flight(1)`, the measure shown at once): the top-down
view, hoop at the bottom, ten trails, the three bars. Then cut to
`reports/figures/wind_figure_1_one_drive.png` whole.

> From above: how far does each of the other three defenders move toward the man left?

**[0:29-0:37] Scene 4, the measure against the placebo.** On screen: figure 1 stays
(`reports/figures/wind_figure_1_one_drive.png`), the bars and the placebo side visible; or the
page in `plan` at t = 1.52, scene 0.

> Against a placebo: the same movement toward the other attackers who are not his own man.
> The measure is the difference.

**[0:37-0:53] Scene 5, the result: a measured absence.** On screen:
`reports/figures/wind_figure_2_who_covers.png` whole, held to the end of the line.

> With a helper, the other three move 0.68 feet less toward the man left than toward the
> placebo. Without a helper, 0.52 feet less. Helped minus unhelped: minus 0.16 feet, interval
> minus 0.65 to plus 0.32. That cannot be told from zero.

**[0:53-1:01] Scene 6, one limit, close.** On screen: the page in `plan`, scene 0 at the
freeze (`wind.view("plan")`, `wind.seek(1.52)`), or the title slide again.

> Ten games only. Nothing here says why anyone moved. Nobody helps the helper, as far as
> these displacements can tell.

---

## Checks

Spoken word count, computed from the quoted lines (lines starting with `>`):

```bash
grep '^>' tasks/video_script_wind.md | sed 's/^> *//' | wc -w
```

Output: `158` (limit 160; at 2.6 words per second that is 60.8 s). Per scene: 20, 39, 16, 21, 42, 20 words.

Numbers spoken, with their source in `README.md`:

| Spoken | README line |
|---|---|
| ten games | line 3 ("Ten SkillCorner basketball games") |
| four feet | "How it is measured": "moves at least 4 ft toward where the ball is 1.0 s later" |
| 41.5, 62.3 | "The man he leaves": **41.5 %** open at the start, against **62.3 %** |
| 58.3 percent, 75.9 | "The man he leaves": **58.3 %** against **75.9 %** |
| 0.68 feet less | "The second help": **-0.68 ft** |
| 0.52 feet less | "The second help": **-0.52 ft** |
| minus 0.16, minus 0.65 to plus 0.32 | "The second help": **-0.16 ft** (CI **-0.65 to +0.32**) |
