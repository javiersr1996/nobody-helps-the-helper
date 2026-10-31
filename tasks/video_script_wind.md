# The 1-minute video, "Nobody helps the helper" (D1)

Rules: one minute, own voice, English. It is the argument, not a summary of the README. The
picture is the silent cut built by D2 (`scripts/wind_video.py`): the drive captured from the page
frame by frame (`wind.seek(t)`, `wind.flight(p)`, `wind.view(name)`, `wind.next()`) and the two
figures whole. Every number spoken appears in `README.md` (checked at the end). Never say or
imply that a defender chose, decided or read anything, and never say where help comes from:
the work measures displacements and distances. Record in one pass over the cut; at 2.6 words
per second each line fills its scene.

**Scope (rewritten 2026-10-30, on the thesis of 2026-10-30):** the claim is the near help that
commits (A8): the off-ball defender nearest the ball steps toward the handler and does not get
back to his man; nobody covers the man he leaves. Long help by the last defender is a limit
(7 drives). The earlier version spoke the pooled helper (-0.68, -0.52, -0.16 ft and the open
shares); it is in git history.

**Pending before D2 (the picture, not the words):**
- Done 2026-10-30: the page's four drives were re-picked among the 159 committed near helps
  (scene 0 is `drive-114243-1-4`) and figure 1 redrawn; figure 2 now shows committed near help
  against the near reference; the README carries every number below.

---

**[0:00-0:06] Scene 1, the rule.** On screen: the page in `broadcast`, scene 0 at t = 0
(`wind.view("broadcast")`, `wind.seek(0)`), held: the drive about to start.

> Coaches teach one rule on defence: when a teammate helps, help the helper.

**[0:06-0:15] Scene 2, the help.** On screen: `wind.seek(hookTime(k / 25))`, the slow-motion run
from t = 0 to the help step t_h (the centre of the page's slow-down around the helper's move,
`clockOf(s).centre`).

> One drive, tracked. The defender nearest the ball steps in to stop it, and leaves his man.

**[0:15-0:21] Scene 3, the cliffhanger.** On screen: frozen at t_h, the man left marked (the
page's own highlight if it has one, else a ring added by D2), one second of silence after the
line.

> Three teammates are left. Does anyone cover his man?

**[0:21-0:31] Scene 4, one drive's answer.** On screen: play on from t_h to 1.52, then
`wind.flight(p)` for p = 0 to 1, landing in `plan` with the bars.

> One of them heads his way. A second and a half later, his man is still 8.7 feet from the
> nearest defender.

**[0:31-0:52] Scene 5, the result.** On screen: figure 2 whole, held to the end of the line.

> Is that the rule? In ten games, 159 drives out of 618 look like this. We measure each move
> toward the man left against moves toward the other attackers, a placebo. Compared with drives
> where the nearest defender stays home, that falls by 0.63 feet, the whole interval below zero.

**[0:52-1:01] Scene 6, the limit, close.** On screen: the page in `plan` at 1.52
(`wind.view("plan")`, `wind.seek(1.52)`), or the title slide.

> Long help, by the defender farthest from the ball, is taught with a rotation; we found seven,
> too few to test. On near help, nobody helps the helper.

---

## Checks

Spoken word count, computed from the quoted lines (lines starting with `>`):

```bash
grep '^>' tasks/video_script_wind.md | sed 's/^> *//' | wc -w
```

Output 2026-10-30 (narrative of the owner's approval): **139** words; per scene 13, 17, 9, 22, 50, 28
(limit 160). Record in `tasks/todo.md` (item 11, D1). Numbers count as one word there but take three
to five spoken (159, 618, 0.63), so the spoken length is read off Javier's pass, not the count.

Numbers spoken, with their source (all at the 1.5 s headline, horizon 1.52 s = 38 frames; the
README line is the one `grep -n` finds, checked by `scripts/check_readme.py`):

| Spoken | Source |
|---|---|
| ten games | `README.md` line 3 ("Ten SkillCorner basketball games") |
| three teammates | the three other defenders (`README.md` "the other three defenders") |
| 8.7 feet | `README.md` line 13 ("**8.7 ft**"), `near_committed_drives.csv`: `left_clear_38` of `drive-114243-1-4` (scene 0) |
| a second and a half | the headline horizon, 1.52 s (`README.md` "At 1.5 s") |
| 159 out of 618 | `README.md` line 11 ("**159 of 618**"), `help_kinds_summary.csv`: `count,flag,near_committed` 159; `count,drives,resolved` 618 |
| stays home | `README.md` line 13: the nearest moves less than 1 ft toward the handler (n = 199) |
| 0.63 feet, whole interval below zero | `README.md` line 21 ("**-0.63 ft** (CI **-1.25 to -0.03**)"), `contrast,near_committed,primary,1.52` |
| seven | `README.md` line 35 ("**7**"), `count,flag,long` 7 |
