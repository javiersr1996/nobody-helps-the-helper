# The 1-minute video, "Nobody helps the helper" (D1)

Rules: one minute, own voice, English. It is the argument, not a summary of the README. The
picture is the silent cut built by D2 (`scripts/wind_video.py`): the drive captured from the page
frame by frame (`wind.seek(t)`, `wind.flight(p)`, `wind.view(name)`, `wind.next()`) and the two
figures whole. Every number spoken appears in `README.md` (checked at the end). Never say or
imply that a defender chose, decided or read anything, and never say where help comes from:
the work measures displacements and distances. Record in one pass over the cut; at 2.6 words
per second each line fills its scene.

**DRAFT 2026-10-31, awaiting Javier** (the words are his to approve; the lines of scenes 2, 4
and 5 are new, scenes 1, 3 and 6 are as he approved them).

**Scope (rewritten 2026-10-31, after the review of item 13):** the claim is a measured absence:
after the defender nearest the ball steps toward the handler and does not go back to where his
man started, the other three defenders move toward the man he left no more than toward any other
attacker, on average over 246 of 618 drives, with the CI's top (+0.13 ft) as the bound against
one rotation (+1.35 ft). Not pre-registered (README). Long help by the last defender is a limit
(7 drives). Scene 0 of the page is `drive-114243-1-1`: a pull-up, the man left 4.5 ft from the
nearest defender at t = 0 and 2.6 ft at 1.5 s, that defender being the helper himself
(`near_committed_drives.csv`: `left_clear_0`, `left_clear_38`, `nearest_who_38`); at 1.5 s the
three others have moved +5.3, +7.2 and -5.0 ft toward the man left and -0.2, +7.2 and +0.3 toward
the placebo (`near_committed_pairs.csv`, horizon 38, def_slots 0, 2, 4): "one of them heads his
way" holds for the first (+5.3 against -0.2); the second moves as far toward the others. The
timings were read off the guide voice (en-GB-RyanNeural) and the windows set so every line fits:
scenes 2 and 3 have under 0.3 s to spare, so the silence the cliffhanger wanted is gone; Javier's
own pass decides whether a line must lose a word.

---

**[0:00-0:06] Scene 1, the rule.** On screen: the page in `broadcast`, scene 0 at t = 0
(`wind.view("broadcast")`, `wind.seek(0)`), held: the drive about to start.

> Coaches teach one rule on defence: when a teammate helps, help the helper.

**[0:06-0:13] Scene 2, the help.** On screen: `wind.seek(hookTime(k / 25))`, the slow-motion run
from t = 0 to the help step t_h (the centre of the page's slow-down around the helper's move,
`clockOf(s).centre`).

> One drive, tracked. The defender nearest the ball steps toward it, away from his man.

**[0:13-0:18] Scene 3, the cliffhanger.** On screen: frozen at t_h, the man left marked (the
page's own tag, plus a ring added by D2), held; the line fills the scene (no silence after it,
see the draft note).

> Three teammates are left. Does anyone cover his man?

**[0:18-0:27] Scene 4, one drive's answer.** On screen: play on from t_h to 1.52, then
`wind.flight(p)` for p = 0 to 1, landing in `plan` with the bars.

> One of them heads his way. A second and a half on, his nearest defender is the helper,
> 2.6 feet away.

**[0:27-0:51] Scene 5, the result.** On screen: figure 2 as two held crops (the dots panel with its key, then the interval panel with the "one rotation" line and the bound), under a caption bar with the numbers.

> Is that the rule? Of 618 drives, 246 look like this. Against the other
> attackers, a placebo, the three move no more toward the man left: minus 0.22 feet. The data rule
> out more than 0.13. Had one moved as far as the helper does, it would read 1.35.

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

Output 2026-10-31 (draft, item 13c): **129** words; per scene 13, 15, 9, 21, 49, 22 (limit 140).
Numbers count as one word there but take three to five spoken (246, 618, 0.22), so the spoken
length is read off Javier's pass, not the count. Guide voice (en-GB-RyanNeural, not the entry's
voice), line against window: 5.23/6, 6.82/7, 4.80/5, 7.97/9, 23.40/24, 8.71/9 s.

Numbers spoken, with their source (all at the 1.5 s headline, horizon 1.52 s = 38 frames; the
README line is the one `grep -n` finds, checked by `scripts/check_readme.py`):

| Spoken | Source |
|---|---|
| three teammates | the three other defenders (`README.md` lines 3, 9 "the other three") |
| a second and a half | the headline horizon, 1.52 s (`README.md` line 19 "At 1.5 s") |
| 2.6 feet | `README.md` line 11 ("**2.6 ft**"), `near_committed_drives.csv`: `left_clear_38` of `drive-114243-1-1` (scene 0), `nearest_who_38` = helper |
| 246 of 618 | `README.md` line 9 ("**246 of 618**"), `help_kinds_summary.csv`: the committed count, `count,drives,resolved` 618 |
| minus 0.22 feet | `README.md` line 19 ("**-0.22 ft** (CI **-0.58 to +0.13**)") |
| 0.13 (the bound) | `README.md` line 19 ("the data rule out more than **+0.13 ft**") |
| 1.35 | `README.md` line 19 ("the mean would read **+1.35 ft**"; the helpers' median step 4.2 ft) |
| seven (scene 6: "only seven") | `README.md` line 39 ("**7**"), `count,flag,long` 7 |
