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
- None of the page's four drives is a committed near help (checked 2026-10-30 against
  `reports/help_kinds.csv`): the hook, scene 0 (`drive-114243-1-1`), has a helper of class
  `other` and its nearest defender stunts; scene 3 (`drive-114099-1-7`) is a nearest helper
  who recovers. Scenes 1, 2, 3 and the plan view need a drive picked by the same rule among the
  159 committed near helps, which changes the page and figure 1.
- Figure 2 shows the pooled helper's numbers, not these.
- The README still carries the pooled numbers; its rewrite must carry every number below, or
  the check against it fails.

---

**[0:00-0:08] Scene 1, the hook: one drive in 3D.** On screen: the page in `broadcast`, the rule's
drive (a committed near help, see Pending), `wind.view("broadcast")`, then
`wind.seek(hookTime(k / 25))` for t = 0 to 1.52, the slow-motion run; no numbers, no caption
text on the slide.

> Ten basketball games, tracked. One drive. Watch the defender nearest the ball step toward the
> driver, and the man he leaves.

**[0:08-0:20] Scene 2, the near help that stays.** On screen: the freeze at t = 1.52
(`wind.seek(1.52)`, broadcast), held, then the opening of the rise, `wind.flight(p)` for
p = 0 to 0.4. Still no numbers drawn.

> He moves at least two feet toward the driver within a second and, two seconds in, is not back
> with his man: 159 of 618 drives.

**[0:20-0:27] Scene 3, the camera rises to the measure.** On screen: `wind.flight(p)` for
p = 0.4 to 1, landing in `plan` (`wind.flight(1)`, the measure shown at once): the top-down
view, hoop at the bottom, ten trails, the three bars. Then cut to figure 1 whole.

> From above: how far does each of the other three defenders move toward the man he leaves?

**[0:27-0:35] Scene 4, the measure against the placebo.** On screen: figure 1 stays, the bars
and the placebo side visible; or the page in `plan` at t = 1.52.

> Against a placebo: the same movement toward the other attackers who are not his own man.
> The measure is the difference.

**[0:35-0:51] Scene 5, the result: a measured absence.** On screen: figure 2 whole (see
Pending), held to the end of the line.

> Against drives where the nearest defender stays home, that difference falls by 0.63 feet, and
> its whole interval sits below zero. One of the three ends up nearest the man left in 18
> percent of drives, against 15.

**[0:51-1:01] Scene 6, the limit, close.** On screen: the page in `plan` at the freeze
(`wind.view("plan")`, `wind.seek(1.52)`), or the title slide again.

> Long help, by the defender farthest from the ball, is taught with a rotation; ten games hold
> seven of them, too few to test. Nobody helps the helper.

---

## Checks

Spoken word count, computed from the quoted lines (lines starting with `>`):

```bash
grep '^>' tasks/video_script_wind.md | sed 's/^> *//' | wc -w
```

Output: see the record in `tasks/todo.md` (D1). Numbers count as one word there but take three
to five spoken (159, 618, 0.63), so the spoken length is read off Javier's pass, not the count.

Numbers spoken, with their source (all at the 1.5 s headline, horizon 1.52 s = 38 frames):

| Spoken | Source |
|---|---|
| ten games | `README.md` line 3 ("Ten SkillCorner basketball games") |
| two feet, within a second | `src/scbasket/help_kinds.py`: `NEAR_STEP_FT = 2.0` over `MOVE_FRAMES = 25` |
| two seconds in, not back with his man | `OUTCOME_FRAMES = 50`; committed if his distance to his man then exceeds the start's by more than `RECOVER_FT = 1.0` |
| 159 of 618 | `reports/help_kinds_summary.csv`: `count,flag,near_committed` 159; `count,drives,resolved` 618 |
| stays home | near reference: the nearest moves less than `NEAR_STAY_FT = 1.0` toward the handler (n = 199) |
| 0.63 feet, whole interval below zero | `contrast,near_committed,primary,1.52`: -0.6345 [-1.2476, -0.0346] |
| 18 percent, against 15 | `nearest_third` of `paired_diff,near_committed,primary,1.52` 0.1824 and of `near_committed_ref` 0.1508 |
| seven | `count,flag,long` 7 |
