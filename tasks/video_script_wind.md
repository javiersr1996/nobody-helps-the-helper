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
- OPEN 2026-10-31 (item 13 c; the spoken lines below are NOT rewritten, Javier approves the
  words). After the review the committed class is the helper's own movement, the claim is the
  measured absence and scene 0 changed. Lines that became FALSE: the scope paragraph above
  ("nobody covers the man he leaves": now an average, no more toward him than toward any other
  attacker); scene 4 "his man is still 8.7 feet from the nearest defender" (scene 0 is now
  `drive-114243-1-4` -> `drive-114243-1-1`, a pull-up; his man is 2.6 ft from the nearest
  defender at 1.5 s, and that defender is the helper himself; "one of them heads his way" still
  holds: defender 1 moves +5.3 ft toward him, -0.2 toward the others); scene 5 "159 drives out
  of 618" (246) and "compared with drives where the nearest defender stays home, that falls by
  0.63 feet, the whole interval below zero" (withdrawn: the contrast is now -0.19 ft, CI -0.71
  to +0.32, reported and not claimed). Scene 2 "steps in to stop it" implies intent (review 7).
  Scene 6 still holds (seven long helps; "nobody" read as the README's average).
  Numbers the new script will need, all printed in `README.md` by `check_readme.py` (1.5 s):
  n **246 of 618**; the committed mean **-0.22 ft** (CI **-0.58 to +0.13**); the bound, the CI's
  top, **+0.13 ft**; its scale, the helpers' median step **4.2 ft**, or **+1.35 ft** had one of
  the three moved that far; the reference **-0.03 ft**; scene 0's man-left clearance **2.6 ft**
  (percentile 54 of 246, on figure 1, not in the README); the designated rotators (pre-registered,
  83e8d5d): low man **+0.21 ft** (CI -0.33 to +0.73), nearest to the man left **-1.11 ft**
  (CI -1.78 to -0.47); a pass within 1.5 s in **28 of 246**; long help **7**, **+1.44 ft**
  (CI -0.33 to +2.98).
  For the picture (D2): `wind_video.py`'s caption now reads the committed mean (-0.22, CI -0.58
  to 0.13) instead of the contrast; its scene-5 crops are pixel boxes of the OLD figure 2
  (1440 x 2678); the new one is 1440 x 3231, so `CROPS` must be re-cut before re-rendering.

---

**[0:00-0:06] Scene 1, the rule.** On screen: the page in `broadcast`, scene 0 at t = 0
(`wind.view("broadcast")`, `wind.seek(0)`), held: the drive about to start.

> Coaches teach one rule on defence: when a teammate helps, help the helper.

**[0:06-0:14] Scene 2, the help.** On screen: `wind.seek(hookTime(k / 25))`, the slow-motion run
from t = 0 to the help step t_h (the centre of the page's slow-down around the helper's move,
`clockOf(s).centre`).

> One drive, tracked. The defender nearest the ball steps in to stop it, and leaves his man.

**[0:14-0:20] Scene 3, the cliffhanger.** On screen: frozen at t_h, the man left marked (the
page's own highlight if it has one, else a ring added by D2), one second of silence after the
line.

> Three teammates are left. Does anyone cover his man?

**[0:20-0:29] Scene 4, one drive's answer.** On screen: play on from t_h to 1.52, then
`wind.flight(p)` for p = 0 to 1, landing in `plan` with the bars.

> One of them heads his way. A second and a half later, his man is still 8.7 feet from the
> nearest defender.

**[0:29-0:51] Scene 5, the result.** On screen: figure 2 whole, held to the end of the line.

> Is that the rule? In ten games, 159 drives out of 618 look like this. We measure each move
> toward the man left against moves toward the other attackers, a placebo. Compared with drives
> where the nearest defender stays home, that falls by 0.63 feet, the whole interval below zero.

**[0:51-1:00] Scene 6, the limit, close.** On screen: the page in `plan` at 1.52
(`wind.view("plan")`, `wind.seek(1.52)`), or the title slide.

> Long help is taught with a rotation; we found only seven, too few to test. On near help,
> nobody helps the helper.

---

## Checks

Spoken word count, computed from the quoted lines (lines starting with `>`):

```bash
grep '^>' tasks/video_script_wind.md | sed 's/^> *//' | wc -w
```

Output 2026-10-31 (scene 6 cut by the owner, windows tightened to 60 s): **133** words; per scene 13, 17, 9, 22, 50, 22
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
| seven (scene 6: "only seven") | `README.md` line 35 ("**7**"), `count,flag,long` 7 |
