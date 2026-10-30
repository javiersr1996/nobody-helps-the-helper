# Analytics Cup 2.0, second entry: nobody helps from the corner

## PLAN, set 2026-10-28. Read this section first; the rebound entry's plan follows it.

### The project
**Title: "Nobody helps from the corner"**, subtitle *the wind map of ACB defences, on
SkillCorner's open tracking*.

**Thesis, one line: on every drive the defence moves like weather; the help blows from the
middle and the top, never from the corner, and it leaves a shooter open beyond the arc.**

### Why this one (decided 2026-10-28 with Javier; a colleague, Miguel, had pointed at defensive help)
- Nobody has drawn help on this bundle: the sportsanalystf Streamlit platform (12 pages,
  collapse curve on drives), the Spacing Connectome (offensive, kernel regression),
  acb-tracking-101, spatial-rebounding, the LinkedIn 3D viewer, the broken-rotations EP
  model, the action-detection benchmark. The Connectome names it as future work.
- The open bundle's `drives` carry no help field; the commercial Dynamic Events do ("help
  involvement"). This is the missing derived layer, as `approach_angles` was for the rebound.
- The outcome is the geometry of the first second itself, not a decision taken seconds
  later. Two neighbours probed the same day died on exactly that and are CLOSED:
  dribble-cadence breaks do not open separation 0.48 s later (quick -0.04 ft against
  steady -0.28, signs mixed by game, 5,457 dribbles), and the length of the pickup- or
  catch-to-release window does not change what the defender closes (Spearman -0.04 and
  +0.00 on 552 and 486 shots). The dribble cadence itself is real (10,608 intervals,
  median 0.72 s, the provider's dribble frames sit on a ball-z minimum 96.8% of the time)
  and may serve as a scene, never as the argument.

### Rules for THIS entry (they differ from the rebound's, on purpose)
- No pre-registration, no held-out half, no gates. Definitions are fixed once and
  reported with a sensitivity table next to every headline. Per-game splits are reported,
  never gated. What comes out marginal is reported as it comes out.
- **Definitions.** Drive frame: the attacking frame mirrored so the ball handler's lateral
  motion over the horizon points to +y. Horizon: 1.0 s (25 frames) from `startFrame`.
  Help movement: a non-matchup defender's OWN displacement projected on the direction from
  his start to the ball handler's position at the horizon. Helper: the non-matchup
  defender with the largest help movement, if it is >= 4 ft. The man he leaves: the
  attacker the `matchups` table assigns him at `startFrame`. Open: no defender within
  6 ft at the horizon. Sensitivity: 3 / 5 / 6 ft and 0.5 / 1.5 s.
- Intent is still not claimable: "help", "helper" and "open man" name measured vectors and
  distances, never decisions. Nothing says a defender chose to help or left a man on
  purpose. Same ruling as the rebound, same banned framing.
- Every number in the README and on the page comes from a `reports/*.csv` written by a
  script (rebound lesson 1 holds). Verify what moves by driving it (rebound lesson 4).
- **The memoria.** Javier wants the whole project documented in a living .docx, extended
  at every milestone (asked 2026-10-28): `docs/memoria/`, built by a script from the same
  CSVs the figures read, in Spanish, with a version log at the end. Each W closes by
  adding its section there.

### What the probe already measured (scratchpad `help_probe2.py`, 608 of 660 drives: 39 without a cached frame, 10 without the handler slot, 3 without a 1 s horizon)
- Largest own movement toward the ball by a non-matchup defender in 1 s: median 3.74 ft;
  drives with one >= 3 / 4 / 5 / 6 ft: 64 / 46 / 33 / 21 %.
- The helper (>= 4 ft, n=278) starts 15.0 ft from the handler. Origin by distance from
  the hoop line: 0-8 ft 14 %, 8-16 24 %, 16-24 36 %, 24+ 26 %; through the middle
  (|y| < 8 ft) 32 / 55 / 65 / 58 % of each band; from the corner side (|y| > 18 ft)
  8 / 3 / 0 / 1 %.
- The attacker he leaves: separation 6.7 -> 8.7 ft; nearest ANY defender at 1 s 6.8 ft,
  none within 6 ft in 59 %; 23.8 ft from the hoop, beyond 22 ft in 65 %.
- Share of drives with a helper by `endType`: kickout 51 %, interiorPass 49 %,
  shotNearBasket 47 %, pullup 33 %. Per game 33 % to 67 %.
- Flow field in the drive frame (8 x 10 ft cells): perimeter cells 16-32 ft from the hoop
  line move 3.0-5.4 ft toward the hoop with consistency 0.63-0.85; the 0-8 ft cells move
  laterally toward the drive side (+1.6 ft, consistency 0.70 on the far weak side).

### What ships
1. `scbasket.wind` (`help` would shadow the builtin): `help_table(frames, drives)`, one row per drive (helper slot and id,
   origin, displacement, help movement, the attacker he guarded, that attacker's
   separation at 0 and at the horizon, nearest defender at the horizon, his distance to
   the hoop, detected flags), `flow_field(frames, drives, horizon, cell)`, and the
   sensitivity sweep.
2. `scripts/help_wind.py` -> `reports/help_table.csv`, `help_flow.csv`,
   `help_sensitivity.csv`, `help_by_game.csv`.
3. Two figures (`scripts/help_figures.py`): figure 1 the wind map (streamplot plus the
   helper-origin density); figure 2 the open man (where he stands at 1 s, coloured by the
   nearest defender's distance).
4. The page: a wind animation (particles over the court, HTML canvas, no CDN), one real
   drive with its four streaks, the field, the open man. Built like `report_html.py`:
   numbers injected from the CSVs, nothing typed.
5. README <= 1000 words, 2 figures; 60 s video, silent cut plus Javier's voice.

### Schedule (deadline 18 Dec 2026)
- [x] W1 (to 4 Nov): DONE 2026-10-28. `scbasket.wind`, `scripts/help_wind.py`, 11
      synthetic tests plus one on game 114086 (a helper built by hand is found at exactly
      5 ft; a defender who only sinks with the drive scores negative; the matchup defender
      is never the helper; the drive frame mirrors right onto left; the three unresolved
      statuses keep their rows). Ran on the ten games: 660 drives, 618 resolved (39 start
      outside the cache, 3 have no 1 s horizon; the probe's 10 "no handler" were raw ids
      against canonical ones, gone now). Headline at 4 ft in 1.0 s: **45.3 % of drives
      have a helper**; he starts 15.6 ft from the handler and 19.6 ft from the hoop; from
      the middle 56 %, **from the corner side 2.5 %** (0-4 % in every cell of the
      sensitivity sweep, 3-6 ft x 0.5-1.5 s); the man he leaves goes 6.8 -> 8.8 ft of
      separation, nearest any defender 6.9 ft, **open (>= 6 ft) 58.5 %**, 23.3 ft from the
      hoop, **beyond 22 ft 61 %**. Origin by band from the hoop line: 0-8 ft 18 %, 8-16
      24 %, 16-24 38 %, 24+ 20 %. **CORRECTED 2026-10-28**: this record first said the
      provider's `direction` agreed with the drive frame on 100 % of drives; that check
      compared the sign of a lateral motion ALREADY mirrored to be positive, and could not
      fail (see lessons). On the un-mirrored flag the agreement is 67 % of left-labelled
      and 72 % of right-labelled drives (326 and 292): two in three, no validation. It
      also means the mirror is close to arbitrary on near-straight drives, which blurs
      "drive side" against "far side" (and is part of why the man left splits 55/45) but
      not the corner measure, which is symmetric. By endType: kickout 51 %, interiorPass 47 %,
      shotNearBasket 46 %, pullup 33 %. Per game 33-67 %. At 0.5 s only 14 % of drives
      have a 3 ft mover: the help takes more than half a second to show. Flow field: 17
      cells with >= 15 vectors, consistency median 0.64, max 0.83. Everything in
      `reports/help_table.csv`, `help_vectors.csv`, `help_flow.csv`,
      `help_sensitivity.csv`, `help_by_game.csv`.
- [x] W2 (to 11 Nov): DONE 2026-10-28. `scripts/help_figures.py` draws both in the drive
      frame, shot-chart orientation (hoop at the bottom, the drive to the right): figure 1
      the wind map (kernel field, bandwidth 4 ft on a 1.5 ft grid, masked under 10 vectors
      of kernel mass, streamlines with width by displacement, helper-origin density in
      orange, the ball's median path), figure 2 the man left (dots coloured by whether
      anyone is within 6 ft, histogram in a strip under the court). Looked at before
      accepting, three passes: v1 had text under the streamlines, a spurious curl at the
      baseline, an inset and a legend over the dots, and grey lines that added nothing;
      v2 moved everything that is not data into a strip under the court, dropped the
      lines and the "away from the ball" claim (55 % is not "most"); v3 fixed the strip
      text running into the width key. `left_beyond_arc` is now by zone (`zone_of`,
      which knows the corner line): 60.5 % against 61.2 % radial. Figures whitelisted in
      `.gitignore` as `reports/figures/wind_figure_*.png`.
#### Reframed entry (set 2026-10-28, after the council and the probe in the next section)
**Thesis, one line: the help blows from the middle and never from the corner, and nobody helps
the helper: the man he leaves is covered by the helper himself or by nobody, measured against
a placebo.**
What ships: `scbasket.wind` (the first second, W1) plus `scbasket.rotation` (the second help as
a measured absence, with its placebo); `reports/help_*.csv` and `reports/second_help_*.csv`;
figure 1 the wind map, figure 2 who covers the man left, with base rates; one self-contained
page with the wind on canvas and a real drive replayed, driven from the console; README <= 1000
words; 60 s video in Javier's voice; the memoria in Spanish, one section per phase. The
post-pass rotation (X-out) ships as a stated limit (18 provider closeouts on the man left). The
title stays "Nobody helps from the corner" until decision D1 below says otherwise.
Rules of the plan: definitions fixed once in module constants and reported with a sensitivity
table; per-game splits reported, never gated; no pre-registration, no held-out half; every
phase closes with `uv run ruff check .` + `uv run pytest` + a check with Javier; ONE adversarial
review, at V. Tags: `[haiku]` mechanical, `[sonnet]` standard, `[opus]` hard but bounded,
`[fable]` where the retry is expensive. No Python through bash heredocs: files go through the
editor. "Help", "helper", "covers" name measured vectors and distances, never decisions.

#### Phase A, 29 Oct to 8 Nov: the absence, measured (the probe becomes code)
- [x] A1 `src/scbasket/rotation.py` [sonnet]: sibling of `wind`, which keeps the first second.
      `rotation_table(frames, drives, help_table, horizons=ROTATION_HORIZONS)` returns `pairs`
      (one row per resolved drive with a man left, other defender, horizon: his own displacement
      projected toward the man left at the horizon, and toward the placebo, the mean over the
      off-ball attackers who are neither the handler, the man left, nor his own man by the raw
      matchup) and `drives` (per drive and horizon: best mover toward each target, who is
      nearest to the man left among helper / handler_def / third and at what distance, and the
      man left's clearance at 0, 0.5, 1.0, 1.5, 2.0 s). The window is contiguous and inside the
      chance; a cut window drops the horizons it cannot reach and keeps the row. Constants:
      `ROTATION_HORIZONS = (25, 38, 50)` frames, headline horizon per decision D4 (default 38).
      Accept: on the ten games the module reproduces today's probe to two decimals (-0.68 ft at
      1.5 s; helper nearest 60 %; the CI with a fixed seed), read back off A3's CSVs.
- [x] A2 `tests/test_rotation.py` [sonnet], on the W1 scene with a third defender added: (a) a
      rotation of exactly 5 ft built toward the man left is the best mover, `to_left == 5.0`
      and placebo < 5.0; (b) three others who only sink along x, with the man left and the
      placebo attackers mirrored across each sinker's line (the placebo attackers may share a
      point), get a paired difference of exactly 0.0 (move one target 1 ft and the test fails:
      demonstrated once, reverted); (c) the defender's own man by the raw matchup is never
      among his placebo targets; (d) the helper and the handler's matchup are never among the
      three others; (e) a chance boundary inside the window drops the horizons past it and
      keeps the row; (f) `nearest_who` reads `helper` when he recovers to within 1 ft. Accept:
      `uv run pytest tests/test_rotation.py` green; only (b), the one that could pass by
      construction, is shown to fail on its mutation (Javier asked for fewer gates, 2026-10-28).
- [x] A3 `scripts/second_help.py` [sonnet] -> `reports/second_help_pairs.csv`,
      `second_help_drives.csv`, `second_help_summary.csv` (per horizon x helped: median
      to_left, placebo, paired difference with a 95 % CI by bootstrap over drives, share
      diff > 0, share with a >= HELP_FT mover toward each target, nearest_who shares, the man
      left's open share and the no-helper comparable's), `second_help_by_game.csv` (the paired
      median per game at each horizon, reported, never gated), `second_help_sensitivity.csv`
      (HELP_FT 3 / 4 / 5 x the three horizons), `second_help_pass.csv` (first pass after the
      drive: n, to the man left, most-open shares, his clearance when he got it and when not)
      and `second_help_closeouts.csv` (the X-out, n = 18, published as a limit). Accept: the
      seven CSVs exist and the numbers quoted in the council section below (-0.52 / -0.68 /
      -0.74; 62 / 60 / 60 %; 8 of 10 games; 31 of 110; n = 18) are read back from them, none
      transcribed by hand.
- [x] A4 Base rate into W1 [sonnet]: `wind._scene` gains `left_nearest0` (nearest any defender
      at `startFrame`) and `help_table` `left_open0`; `help_wind.summarise` gains
      `left_open_share_no_helper`, `left_open0_share`, `left_open0_share_no_helper` (the
      comparable man is the largest sub-threshold mover's man: the same `left_*` columns over
      `~has_helper`); `help_by_game.csv` and `help_sensitivity.csv` carry the new columns. One
      synthetic test: a man left guarded at 0 s and open at 1 s reads `left_open0 == False`,
      `left_open == True`. Accept: `help_sensitivity.csv` carries the base rate in all twelve
      cells; the 4 ft / 1.0 s row reads 0.585 next to 0.726.
      **A1-A4 DONE 2026-10-28** (two Sonnet agents in parallel; ruff clean, 292 tests pass).
      Read back off the CSVs, not typed: 587 / 258 drives; paired diff -0.52 / -0.68 / -0.74
      helped and -0.39 / -0.52 / -0.63 unhelped; nearest helper 0.624 / 0.599 / 0.598, third
      0.167 / 0.187 / 0.203; open 0.415 -> 0.585 against 0.623 -> 0.726; pass 110 / 31;
      closeouts n = 18. Two differences from the probe, both kept as they fell: the bootstrap
      CI at 1.5 s and 2.0 s is -1.08..-0.27 and -1.27..-0.21 (the probe shared one generator
      across the six cells; A3 seeds each one), and the per-game sign count (see the correction
      in the council section). Shared columns of `help_*.csv` unchanged against HEAD. Test (b)
      fails on its mutation (0.064 against 0.0), as does A4's (`left_nearest0` at the horizon).
      `rotation.py` and `second_help.py` import `wind._row_of`, a private name.
- [x] A5 Figure 2 redrawn per decision D3 [sonnet] (default if no answer by 1 Nov: "who covers
      the man he left": dots at the headline horizon coloured by the nearest defender's
      identity, helper / handler's defender / third; in the strip under the court the rotation
      toward him against the placebo at 1.0 / 1.5 / 2.0 s with its CI, and the open share with
      its base rate in the same sentence). Numbers from `second_help_summary.csv` and
      `help_sensitivity.csv`, none typed; looked at before accepting, as in W2. Accept:
      `reports/figures/wind_figure_2_*.png` rebuilt, every number on it greps back to a CSV
      column, Javier has looked at it.
      **DONE 2026-10-29** (814dab0) except Javier's look, which moves to A7.
      `reports/figures/wind_figure_2_who_covers.png` replaces `wind_figure_2_open_man.png`.
      `rotation_table` gained `left_x_T`, `left_y_T` in the drive frame; at T = 25 they equal
      `help_table` `left_x1, left_y1` on 587 of 587 drives (max diff 0.0, and dropping the
      flip breaks 44 % of them; the new test fails on that mutation). Every older column of the
      seven `second_help_*.csv` is unchanged against HEAD. Every number on the figure is read
      from `second_help_summary.csv` / `second_help_drives.csv`. **New qualifier:** the -0.68 ft
      is the MEAN over drives; the median over pairs is -0.05 (-0.15 / -0.10 at 1.0 / 2.0 s) and
      49 % of pairs are > 0. The typical pair sits on the placebo, so the honest claim is an
      absence of rotation toward the man left, not a rotation away from him. The figure carries
      it next to the mean, and the README and page must too. Open share at 1.5 s: 58 % against
      76 % without a helper (41 % and 62 % at 0 s). Two look-and-fix passes.
      **Revised 2026-10-29 after a council screening (47/100, "not ready").** Taken: the 60 %
      is near-persistence (the helper guarded that man at the start; with no helper his own
      defender is nearest 78 %), so the title now states the measured absence ("Nobody else
      moves toward the man the helper left"); the grey series overlaps the black at every
      horizon, written on the figure and guarded by a ValueError (seen to fire once); the
      placebo panel promoted, 11 pt, 252 of 258 explained, one robustness line (15 of 18
      cells, 7 of 10 games, both computed). Rejected: the screening's title "58 % unguarded vs
      76 % when nobody helped", which reads the base rate as a cost (41 -> 58 % against
      62 -> 76 % are similar rises). Final 1440 x 2262 px. Memoria 9.2 and the 11 sentence on
      the nearest defender follow it.
      **Second council screening, same day (45/100).** Taken: overlapping CIs are not a test,
      and the grey series being negative too shows the metric's own geometric bias, so the
      null is the no-helper baseline, not zero. `second_help.py` now writes
      `second_help_contrast.csv` (helped minus no helper, two-sample bootstrap):
      -0.12 (-0.45..+0.20), -0.16 (-0.65..+0.32), -0.11 (-0.74..+0.52) ft at 1.0 / 1.5 / 2.0 s,
      every CI contains 0, and `second_help_contrast_sensitivity.csv` (3 / 4 / 5 ft x three
      horizons): 8 of 9 contain 0, none above (3 ft at 1.0 s is below, -0.61..-0.01). The
      claim is now "no more rotation than with no helper", guarded in figure and memoria
      (fail if any contrast CI low > 0; seen to fire once). The robustness line counts the
      contrast, not cells against zero. Nearest-defender median distance on the legend
      (7.5 ft, 9.4 ft with no helper). Open line moved off the figure: it goes in the README
      next to 58.5 %. **Consequence for the README:** "-0.68 ft below the placebo" and
      "15 of 18 cells exclude 0" test against zero, the wrong null; the README headline for the
      second help is the contrast. The CI tops (+0.20 / +0.32 / +0.52 ft) are the most extra
      rotation the data cannot rule out: an absence with that bound, not a proven zero.
      Rejected: colouring the map by distance (against D3), merging 7/10 and 8/10 (only one
      is on the figure). Final 1440 x 2437 px; 295 tests pass.
- [ ] A6 Memoria v0.3 [sonnet]: amend 8.2 (the base rate next to 58.5 %, lesson 2) and 9.2
      (the new figure 2); new section 13 "La segunda ayuda: una ausencia medida" (the council's
      37/100 and why points per chance has no power; the placebo design; the three results; the
      pass; the X-out as a limit) reading `second_help_*.csv`; section 10 replaced by this
      phased plan; section 11 pruned by the single-entry decision (items 1, 3 and 4 closed, the
      closing reason kept); `SECTIONS` index and version row 0.2; rebuild with
      `NODE_PATH="$(npm root -g)" node docs/memoria/build_memoria.js`, export to PDF, look at
      it. Accept: the PDF is read; section 13 is in the index; its numbers match the CSVs.
      **DONE 2026-10-29, v0.3, 21 pages.** The new section is 11 "La segunda ayuda: una
      ausencia medida" (8 subsections, every number from `second_help_*.csv`, two asserts in
      the build: no 11.2 CI contains zero, helped and unhelped CIs overlap); plan is now 12,
      pending 13, version log 14. 10.3 keeps only the design and points to 11. Typed numbers
      in 8, 8.3, 8.4, 9.1 and 10.3 now read from CSVs. Per-game signs computed in the build:
      7 of 10 by pair median, 8 of 10 by drive median at 1.5 s (as recorded). The 21 helped
      numbers of 11.2-11.6 read back from the PDF text by script against the CSV: 21 of 21.
      **New qualifier for the README:** in the sensitivity grid 15 of 18 CI cells exclude zero;
      helped at 5 ft and 2.0 s (-1.20 to +0.14) and two unhelped 3 ft cells do not. Left typed,
      no CSV carries them: 7.1's 283 tests (true at W1), 9.3's 55 % (history), section 5 and
      10.2's council numbers. The PDF is ignored by `.gitignore:32`; E2 decides whether it ships.
- [x] A7 Phase close [haiku]: `uv run ruff check .` and `uv run pytest` exit 0; then Javier's
      check (figure 2, decisions D1, D3, D4).
      **DONE 2026-10-29**: ruff clean, 295 passed; Javier approved figure 2 v4 (7ff6827).
      Phase A is closed; the corner base rate (section "OPEN 2026-10-29" below) is new work
      that comes before B1.

#### Phase B, 9 Nov to 29 Nov: the page (the finding on the court, in motion)
- [x] B1 (DONE 2026-10-29; see the record) Kernel field into the package [sonnet]: move the field `help_figures.py` computes into
      `scbasket.wind.kernel_field(vectors, grid_ft, bandwidth_ft, min_weight)`; `help_wind.py`
      writes `reports/help_field.csv` (grid, mean dx, dy, kernel weight); `help_figures.py`
      reads it. Test: one vector gives a field that points its way, decays with distance and is
      masked under `min_weight`. Accept: figure 1 rebuilt is unchanged or the diff is named; the
      page and figure 1 read the same file.
- [x] B2 (DONE 2026-10-29, pulled forward for figure 1; see the record) `scripts/wind_scenes.py` [sonnet] -> `reports/wind_scenes.json`: drives chosen by a
      rule, not a search (per decision D6, default: the first helped drive of each of four games
      in which the ten players are detected on every frame of the 2 s window and the man left
      has a provider matchup); per drive, 2 s of ten players and ball in the drive frame, slot
      roles (handler, handler_def, helper, left, other x3), the man left's clearance per frame,
      and each other defender's projection toward the man left and toward the placebo per
      frame; no ids, no names, as in `court_scenes.py`. Accept: a test asserts each scene's
      helper movement at 1.0 s equals `help_table.csv` within 0.01 ft and refuses a scene that
      disagrees.
- [x] B3 (DONE 2026-10-29, accepted by Javier: "dale") Storyboard before the engine [fable], in `tasks/wind_page.md`: the three-second hook
      per D8 (the rule's drive in 3D from a broadcast-like camera, moving with no click: the
      helper stepping toward the ball, the man he leaves drifting free; then the camera rises to
      the top-down view, where every measure is shown); the camera path and when it rises; the
      sequence after it, all top-down (the three others' trails beside their placebo, with the
      bars of figure 1; the man left and who covers him, with the live clearance and the base
      rate; the league wind as context; the limits); the claim of each section and the CSV
      column that sits next to it; what the reader can touch (scrub, next drive, orbit the 3D
      view or not, 390 px). Also decides the ball: drawn at its measured height, with the
      vertical-axis limit stated (the sibling audit fits gravity at 28.1 against 32.17 ft/s²,
      so bounces fall slow), or flat on the floor. Fable because the retry is the whole phase:
      an earlier page was rejected for technique over a closed analysis, and this one has to
      show the finding; a 3D viewer of this bundle already exists (the LinkedIn one), so the 3D
      earns Communication only if it shows the helper and the man left, never Originality.
      Accept: Javier accepts it before B4 starts; every claim in it names its CSV column; no
      measure is shown in the perspective view.
- [x] B4 (DONE 2026-10-29; see the record) `scripts/wind_template.html` + `scripts/wind_html.py` [opus] ->
      `reports/nobody_helps_the_helper.html` (slug per D1 and B3; the storyboard
      `tasks/wind_page.md` is the spec and wins where this text is shorter): self-contained, no CDN,
      no network; payload injected at `/*PAYLOAD*/` from `help_*.csv`, `second_help_*.csv`,
      `help_field.csv` and `wind_scenes.json` (lesson 1, nothing typed); per D8 a WebGL court
      with three.js vendored in the repo at a pinned release with its MIT licence and inlined
      by the build (no CDN, no network); players as tokens on their tracked (x, y), never
      bodies (the bundle has no pose); the drive replay with the helper's streak, the man
      left's and the three others'; the camera from the broadcast view to an orthographic
      top-down view, in which the court is in shot-chart orientation and the trails, bars and
      particles advected by the field are drawn; `prefers-reduced-motion` honoured (a cut
      instead of the camera flight, no autoplay); the state machine exposed as `window.wind =
      {play, pause, seek(t), next, view(name), state}` with `state()` returning `{scene, t,
      phase: idle|playing|ended, view: broadcast|rising|plan, positions}`.
      Accept: builds from the CSVs; `rg '[0-9]+\.[0-9]+ ?(%|ft)'` on the template finds nothing
      outside the court geometry; renders with DevTools offline.
- [x] B4b (DONE 2026-10-30; see the record) The hook, rebuilt to hook (Javier, 2026-10-29, on opening B4's page: "no engancha
      nada; las fichas deben ser jugadores de baloncesto; vamos a currárnoslo todo lo que
      podamos"). Amends D8's "players as tokens": in `broadcast` and `rising` the players are
      rigged 3D basketball players (a CC0 or MIT/CC-BY asset found by a research spike, licence
      quoted and vendored with it; procedural figures only if no asset qualifies), animated
      from the tracking: position tracked, stride and blend (idle, jog, run) from speed, facing
      drawn (attackers along their motion, defenders toward the ball handler), the handler's
      dribble synced to the ball's measured height. Two teams by jersey (no real team or league
      branding); roles by a coloured ring on the floor under each player (figure 1's colours)
      and the two name tags; the ring is what the rise turns into figure 1's token, so `plan`
      stays exactly B4's (B5's checks hold). An arena: lit court, procedural hardwood, dark
      surroundings, soft shadows. Cinematography inside the 1.52 s clip: the broadcast camera
      may move (push-in), slow motion around the help step; the rise unchanged. No measure in
      perspective still holds; no ring, glow or spotlight encodes a number. Next to the hook,
      the limit: only where each player stands is tracked; bodies, facing and stride are drawn.
      Order: research spike (assets) -> storyboard amendment (section 2.2, 2.3, 3) -> a hook
      prototype Javier judges as a capture (GIF/MP4) BEFORE the rest is polished -> integrate.
      Accept: Javier says it hooks; B5 passes; page under 8 MB; 60 fps desktop.
- [x] B5 (DONE 2026-10-29 on B4's page; rerun on B4b's; see the record) `scripts/drive_wind_page.py` [sonnet] (Playwright headless, under a new `page` extra,
      never core): drives the built page from the console: `seek(1.0)` puts the helper within
      0.1 ft of the JSON; `play()` and wait reads `ended` with the last frame drawn; pause then
      play resumes at the same `t`; `next()` changes scene and numbers; the page opens in
      `broadcast` and reaches `plan` with no click; in `plan`, every player's screen position
      mapped back through the camera is within 0.1 ft of the JSON at `seek(1.0)` (the top-down
      is true, not a perspective that looks flat); no measure (bar, number, strip) is visible
      while the view is not `plan`; with reduced motion the flight is a cut; every injected
      number in the DOM equals the CSV value it names; at 390 and 1440 px no horizontal
      scroll, body >= 16 px, canvas inside the viewport. WebGL must be live in the browser it
      drives (checked first, failing loudly if not). Lesson 4: run once against a template
      with one typed number, one broken `seek` and a perspective camera left on in `plan`; it
      must fail all three (recorded here), then reverted.
      Accept: exit 0 on the built page, exit 1 on each mutation.
- [x] B6 (DONE 2026-10-30) Memoria v0.4 [sonnet]: section 14 "La página" (what the storyboard decided, what the
      console check asserts, the mutations it fails on), index and version row; rebuild, PDF,
      look. Accept: as A6.
- [ ] B7 Phase close [haiku]: ruff + pytest exit 0; Javier opens the page on his own machine.

#### Phase C, 30 Nov to 6 Dec: the public repo and the README
- [x] C1 (DONE 2026-10-30: tag bounce-final on 635ea4d, commit 7fbf8f8; readme field of pyproject repointed until C2) Execute decision D2 [haiku] (default: this repo is the entry): tag HEAD `bounce-final`
      first; move `README.md` to `docs/bounce/README.md` with its figure, page and video links
      corrected; update the `pyproject.toml` description; every rebound script, test and CSV
      stays (open-source value, tests stay green); `range.bin` per D5. Accept: `uv run pytest`
      green after the move; every link in `docs/bounce/README.md` resolves (`ls` each path).
- [ ] C1b (PUBLISHED 2026-10-30; acceptance open, the start-up over the network: see NEXT SESSION 6) The page on GitHub Pages [haiku, with Javier] (added 2026-10-29 on Javier's word):
      GitHub shows an HTML file in a repo as source, so a link to `reports/*.html` would show
      code, not the 3D page; the README links to a served page instead. Needs the public repo
      on GitHub: today no remote is configured (`git remote -v` empty, 2026-10-29); creating it
      and pushing is outward-facing, so Javier confirms at that moment. Served by a GitHub
      Actions workflow (`.github/workflows/pages.yml`, the official `upload-pages-artifact` and
      `deploy-pages` actions) that publishes the committed page (B4's `reports/*.html`, slug
      per D1) as `index.html`, not rebuilt in CI (C3's clean clone proves the build); free on
      a public repo. Accept: `curl -I` on the Pages URL returns 200; the served file hashes
      equal to the committed page; B5's driver, pointed at the URL instead of the local file,
      exits 0 (so `drive_wind_page.py` takes a path or a URL); C2's README links to that URL.
- [x] C2 (DONE 2026-10-30: README 876 words by the checker, 2 images, 31 bold numbers each
      mapped to a CSV and recomputed; mutation run: "45.3 %" changed to "46.3 %" in a copy
      gives FAIL, README '46.3 %' against CSV '45.3 %', exit 1. `readme` of pyproject back to
      README.md. Thesis is only the second help since 2026-10-29: the corner is occupancy
      (1.8 %) and 66 % of helpers start above the ball, next to the 45.3 %. Left out for lack
      of a CSV: the 4 to 5 ft error of extrapolated positions (typed in the memoria only).
      Page link is the local file with a `C1b` comment until GitHub Pages) `README.md` of the entry [sonnet], <= 1000 words, 2 figures: the thesis; the first
      help (corner side 2.5 %, 0-4 % in all twelve cells); the man left with its base rate in
      the same sentence (58.5 % against 72.6 % is the 1.0 s pair; per B3, C2 quotes the 1.5 s
      pair from `second_help_summary.csv`, 58.3 % against 75.9 % today, like both figures and
      the page, and names the horizon); the second help as a measured absence with its
      placebo (-0.68 ft, CI, per-game signs: 8 of 10 by drive, 7 of 10 by pair) and who covers him (the helper, 60 %); the pass in
      one sentence with its n (D7); the limits (X-out n = 18, the mirror on near-straight
      drives, ten games, extrapolated positions); what ships; run it; licence. Nothing says a
      defender chose. Accept: `scripts/check_readme.py` counts <= 1000 words and exactly two
      images, and maps every bold number to the CSV column it comes from, failing on a number
      it cannot find (tried once with a typed number).
- [x] C3 (DONE 2026-10-30: clone at a35e489 in scratchpad; exit codes uv sync 0, pytest 0 with "288 passed, 21 skipped", help_figures 0, wind_html 0, build_memoria 0; git status: reports/nobody_helps_the_helper.html changed only in the record sha/subject (now a35e489), docs/memoria docx rebuilt with the commit-log table shifted one row and new timestamps; check_readme 0 failed, 890 words) Clean clone [haiku]: `git clone` into the scratchpad, `uv sync --extra dev`,
      `uv run pytest` (data tests skipped), `uv run --extra figures python
      scripts/help_figures.py`, the page build, the memoria build, all from the committed CSVs
      and no dataset. Accept: the five commands exit 0 in the clone and the README's "Run it"
      block is the list actually run.
- [x] C4 (DONE 2026-10-30: memoria v0.6, new section 14 "El repositorio público y el README" (one page, p. 32 of 36), Plan/Pendientes/Registro renumbered 15/16/17 with 14.1 -> 15.1, phase C row and version row updated; read back with pdftotext: titles in index and body, 890 words, 29 bold numbers, 288 passed/21 skipped, 45,3 to 46,3 mutation; page looked at) Memoria [sonnet]: section "El repositorio público y el README" (decision D2,
      what moved, the clean-clone result), index and version row; rebuild, PDF, look.
- [ ] C5 Phase close [haiku]: ruff + pytest exit 0; Javier reads the README.

#### Phase D, 7 Dec to 13 Dec: the video
- [ ] D1 (WRITTEN 2026-10-30: 158 spoken words, about 61 s at 2.6 words a second, the start base rates spoken in scene 2; waits for Javier to read it aloud) `tasks/video_script_wind.md` [sonnet]: <= 160 spoken words, six scenes, each naming
      the figure or the page state (`seek(t)`) it shows; the base rate and the placebo are
      spoken, not only shown. Accept: word count by `wc -w`; Javier reads it aloud once and it
      lands between 55 and 62 s.
- [ ] D2 `scripts/wind_video.py` [sonnet], sibling of `video_slides.py`: 1920x1080 slides
      (title; figure 1; figure 2; the record) and, per D8, the drive captured from the page
      itself, driven by `seek(t)` frame by frame at 1920x1080 (the 3D hook and the camera
      rising to the top-down view), so video and page show the same pixels from the same
      `wind_scenes.json`; the silent MP4 timed to D1 with ffmpeg. Accept: `ffprobe` reads
      60 +- 1 s off the built file; every number on a slide greps to a CSV.
- [ ] D3 Voice [haiku]: Javier records one pass over the silent cut; mux with ffmpeg; `ffprobe`
      duration read back and written here. Accept: 58-62 s, voice audible on a phone speaker.
- [ ] D4 Memoria v0.6 [sonnet]: section 16 "El vídeo", index and version row; rebuild, PDF,
      look.
- [ ] D5 Phase close [haiku]: ruff + pytest exit 0; Javier watches the video once through.

#### Phase E, 14 Dec to 18 Dec: margin and close (submit by 17 Dec)
- [ ] E1 Real devices [haiku]: the page on Javier's phone and a real window, the video on the
      phone; defects fixed if under an hour, else written as limits in README and memoria.
- [ ] E2 Memoria v1.0 [sonnet]: final version row; section 11 holds nothing open, or each
      item with its decision; rebuild, PDF, look; docx and PDF committed.
- [ ] E3 Submission [haiku]: public repo URL, tag `cup2-v1.0`, the form sent by 17 Dec, the
      confirmation saved under `tasks/`.
- [ ] V. Verificación
      - Gates, all exit 0 on the clean clone of C3: `uv run ruff check .`; `uv run pytest`;
        `NODE_PATH="$(npm root -g)" node docs/memoria/build_memoria.js`;
        `uv run python scripts/wind_html.py` then `uv run python scripts/drive_wind_page.py`;
        `uv run python scripts/check_readme.py`; and on the published page (C1b), `curl -I`
        on the Pages URL returns 200 and `drive_wind_page.py` exits 0 against it.
      - Aggregate acceptance of the plan: every number in README, page, video slides and
        memoria reads back from a `reports/*.csv` written by a script in the repo (lesson 1);
        each headline ships with its qualifier next to it: the corner share with its twelve
        sensitivity cells, the open share with its base rate, the rotation with its placebo,
        CI and per-game signs, the X-out as a limit (lesson 2); the page's motion is asserted
        from the console, not from stills (lesson 3); no check in the repo passes by
        construction, each has been seen to fail once (lesson 4); no sentence claims intent.
      - The ONE adversarial review of the plan [opus]: the `revisor-adversarial` subagent reads
        the full diff `git diff b6263f8..HEAD` plus the built README, page and memoria PDF and
        answers "what would break this" per criterion (relevance, methodology, originality,
        communication, open-source potential); each finding fixed or written as a limit in
        README and memoria before E3 sends the form.

#### Decisions for Javier (listed, not settled; the default applies if no answer by the date)
**ANSWERED 2026-10-28.** Executors: mixed, by the tags above. D1: **"Nobody helps the helper"**
(against the recommendation; the page slug, the memoria and the README follow it). D2: this repo
is the entry. D3: figure 2 is "who covers the man he left". D4, D6, D7: the defaults, accepted as
technical. D5 (`range.bin`): deleted 2026-10-29 on Javier's word (100 bytes, the head of a
JSON tracking frame, untracked, no reference). The memoria went to v0.2 the same day
with the single-entry decision, the council, the probe (numbers from this record) and this plan,
so the memoria tasks below are each one version later than written (A6 v0.3, B6 v0.4, C4 v0.5,
D4 v0.6) and each new section goes in before "Plan y calendario", not at a fixed number.
- D1 Title (by 1 Nov). Keep "Nobody helps from the corner" with the subtitle "and nobody helps
  the helper", or move to "Nobody helps the helper". Recommendation: keep. The corner claim is
  the robust, positive, visual half (0-4 % in all twelve cells) and the files, memoria and
  figures already carry it; a null with a placebo is the second half, not a headline.
- D2 Public repo (by 29 Nov). This repo becomes the entry (tag `bounce-final`, rebound README
  under `docs/bounce/`, optional GitHub rename with redirects) versus a new repo depending on
  `scbasket`. Recommendation: this repo. The split costs a week of seven, `court`, `frames`
  and `io` are shared, "works on clone" is already proven here, and the rebound record is
  open-source value the rules score.
- D3 Figure 2 (by 1 Nov). "Who covers the man he left" (A5 default) versus the W2 open-man dots
  with the base rate added. Recommendation: who covers. The dots were the W1 story and now ship
  with a base rate that takes half their punch; the nearest defender's identity is the new
  finding and its strip carries the placebo.
- D4 Headline horizon of the rotation (by 1 Nov): 1.5 s (default; 8 of 10 games negative by
  drive, 7 of 10 by pair) with 1.0 and 2.0 in the sensitivity table, or 1.0 s to match W1.
- D5 `range.bin` (by 29 Nov): delete. Recommendation: delete; nothing references it.
- D6 Drive replay scope (by 9 Nov): four drives chosen by rule, one autoplaying, a next button
  (default) versus one drive versus a browser of all 258. Recommendation: four; the hook needs
  one, the rule guards against cherry-picking, more is cost without a claim.
- D7 The pass in the README (by 30 Nov): one sentence with its n in the limits (default) versus
  only in memoria and page. Recommendation: one sentence; it answers "did the ball find him".
- D8 **ANSWERED 2026-10-29 (Javier: "sí").** The page opens with the rule's drive in 3D, from a
  broadcast-like camera, and the camera rises to the top-down view for the measure; the video
  captures it from the page. Not in the README: GitHub shows images and runs no 3D, the rules
  allow two figures, and perspective distorts the very thing measured (feet on the floor
  toward a point: a foot near the camera does not look like a foot far from it), so only the
  top-down view lets a reader judge "toward" by eye. Limits stated with it: players are
  tokens on (x, y), the bundle has no bodies; the ball's height carries the vertical-axis
  anomaly; a 3D viewer of this bundle exists, so this scores on Communication or not at all.
  No hours were measured for WebGL over canvas 2D; it lands in B4 (Opus), whose three weeks
  had no slack already.

### Council and the second-help probe (2026-10-28, after W2)
Javier decided this is the ONLY basketball entry (the rebound and the vertical-axis audit are not
submitted) and proposed turning it toward first and, above all, second help. Full council: 37/100
if the question is the effect on points (Contrarian 43, First Principles 37, Expansionist 55,
Outsider 30, Executor 45, mean 42; peer review -5 blind spot, -5 unrebutted red, +5 unanimous
strength; the screening of the unreframed entry had given 51). That null has no power: points per chance 0.911 with a
helper against 0.905 without (280 / 338), 95% CI of the difference -0.17 to +0.18.
Probe (scratchpad `second_help_probe.py`, `second_help_closeouts.py`; 587 resolved drives with a
man left, 258 helped). **The second help, as a rotation by a third defender, is CLOSED**:
- The three defenders who are neither the handler's matchup nor the helper move toward the man
  left LESS than toward the other off-ball attackers who are not their own man (own displacement
  projected on each target, mean per drive): -0.52 ft at 1.0 s (95% CI -0.79 to -0.25), -0.68 at
  1.5 s (-1.09 to -0.28), -0.74 at 2.0 s (-1.25 to -0.24); in drives with no helper -0.39, -0.52,
  -0.63. Per game at 1.5 s, 7 of 10 pair medians negative (**CORRECTED 2026-10-28**: first
  written here as 8 of 10, a miscount of the probe's own print, which read 7; the per-drive
  median that A3 publishes beside it gives 8 of 10, one of them -0.06; both ship). A >= 4 ft mover toward him in 44 % of
  drives against 42 % toward the placebo.
- What covers him is the helper himself: nearest defender to the man left at 1.0 / 1.5 / 2.0 s is
  the helper 62 / 60 / 60 %, the handler's defender 21 / 21 / 20 %, a third defender 17 / 19 /
  20 % (with no helper: his own man 77 / 78 / 76 %, a third 10 / 13 / 15 %).
- **The W1 headline needs its base rate.** Open (nobody within 6 ft): the man left 41.5 % at 0 s,
  58.5 % at 1.0 s, 58.1 % at 2.0 s; the comparable man in drives with no helper (the largest
  sub-threshold mover's) 62.3 %, 72.6 %, 74.7 %. The help adds room to a man who starts more
  closely guarded; it does not make an open man where there was none. Figure 2 and the memoria
  carry 58.5 % with no base rate next to it (lesson 2).
- The pass: a first pass in 110 of 258 helped drives, to the man left 31 (28 %, one of four
  receivers is 25 %). At the pass frame (median 1.92 s) he is the most open teammate in 20.9 %;
  the receiver was the most open in 31.8 %. His clearance at the pass: 9.29 ft when he got it
  (n=31), 6.74 when he did not (n=79).
- After the pass: 116 drives have a provider closeout. On the man left (n=18) the closer is the
  helper 56 %, someone else 44 %; with no helper, someone other than the receiver's own defender
  closes 43 % (n=56). Too few to say anything.

### OPEN 2026-10-29: the corner headline has no base rate (session probe, not yet code)
On `help_vectors.csv` x `help_table.csv` (2,472 off-ball defenders, 618 drives): only 1.8 % of
off-ball defenders START at |y| > 18 ft and none in the corner-3 zone (`zone0`), against
46.6 % at |y| < 8 ft. Helpers come from there 2.5 % / 56.4 % (n = 280). Per defender, the
chance of being the helper: |y| > 18 ft 7 of 45 (15.6 %), |y| > 14 ft 9.2 %, |y| < 8 ft 13.7 %;
by zone top_3 23 %, wing_3 25 %, mid_range 8.7 %, paint 8.3 %, restricted area 1.8 %. So
"nobody helps from the corner" (2.5 %, 0-4 % in all twelve cells, a sweep that could not
have come out otherwise) is mostly "no defender stands in the corner"; the per-defender
gradient is perimeter-high against inside, not middle against corner. Lessons 2 and 4 both
apply. Needs: the base rate in `help_wind.summarise` and the sensitivity table, written as
code, then Javier decides what the first half of the thesis and figure 1's title say.
Council screening of figure 1, same day: 46/100, not ready, on exactly this (the orange is a
raw origin density, not a rate per defender; strip text 8-9 pt). Its proposed title "Help
comes from the three-point line, not the paint. The corner is empty, not stingy" is NOT
taken as is: 7 of 45 cannot say "not stingy" (a 95 % interval runs roughly 8 to 29 %), and
the perimeter-against-inside gradient may be mechanical (the helper is the largest mover
TOWARD the ball's future spot, and an inside defender already stands near it). Order for the
next session: (1) the base rate and the per-defender rate by zone and by |y| band, with
intervals, into `help_wind` and a CSV, with a test; (2) whether the gradient survives
measuring help against each defender's distance to the ball's future spot; (3) Javier
decides the thesis's first half and figure 1's title; (4) figure 1 redrawn (rate per
defender or ratio, n shown, text >= 11 pt); (5) memoria 8 and 9.1 follow.
**(1) and (2) DONE 2026-10-29**, as code: `wind` vectors gain `target_dist` and
`target_bearing_x` (the projection's target: how far, and the along-court share of the way,
negative toward the hoop line); `help_wind.py` gains `helper_flags`, `helper_rate` (rate per
defender by group, and helpers over what the group's strata predict, 95 % by bootstrap over
drives, seed 0) and writes `reports/help_base_rate.csv` (|y| band and zone, each raw and
standardised by distance, bearing and both); `summarise` gains `defenders_from_middle`,
`defenders_from_corner_side`, `helper_rate`, `helper_rate_middle`, `helper_rate_corner_side`,
`n_defenders_corner_side`, `helper_above_ball` (share of helpers with `target_bearing_x` < 0)
and `helper_along_court_share` (median share of a helper's help movement that is his
along-court component), so all twelve sensitivity cells and every game carry them; the CSV
also carries the raw rate by bearing band. The
script refuses to run if the helper read off the vectors is not `help_table`'s. Every older
column of the five `help_*.csv` is unchanged against HEAD. Tests: `test_help_wind.py` (a
group that helps only as its stratum says reads ratio 1.0; standardising inside each group
makes the raw ratio 1.0 too, and the test fails on that mutation, 1.0 against 1.28: seen
once, reverted) and a `test_wind` case pinning a defender above the ball whose pure 4 ft
sink scores 4 ft of help. 299 tests pass, ruff clean. Read back off the CSVs:
- **The corner is empty, not measurably stingy.** 45 of 2,472 off-ball defenders (1.8 %)
  start at |y| > 18 ft, none in `corner_3`; 7 of 280 helpers. Per defender 15.6 %
  (5.7-27.3 %) against 13.7 % (11.9-15.5 %) from the middle and 11.3 % overall. In the eight
  sensitivity cells at 1.0 and 1.5 s, corner minus middle runs -0.036 to +0.058; at 0.5 s the
  corner has 0 or 1 helpers. "Nobody helps from the corner" is "nobody stands there".
- **Distance does not explain the perimeter gradient** (the hypothesis written above is
  refuted: inside defenders are NOT nearer the ball's future spot). Ratio to expected, raw
  then by distance: top_3 2.06 -> 1.90, wing_3 2.19 -> 2.16, mid_range 0.77 -> 0.79, paint
  0.73 -> 0.70, restricted area 0.16 -> 0.16.
- **The bearing does.** Helper rate 31.7 % (26.3-37.0) when the spot lies mostly toward the
  hoop line from the defender (bearing <= -0.7), 5.4 % (3.9-7.0) when it lies mostly away
  (> 0.7); 65.7 % of helpers stand farther out than the spot, and the along-court part is a
  median 49 % of a helper's help movement. Across the twelve cells: above the ball 57-100 %,
  along-court 44-96 %, both rising with the threshold (the bigger the mover, the more of it
  is the sink). Ratio to expected by bearing: top_3
  1.07 (0.88-1.27), paint 0.98 (0.73-1.23), mid_range 0.87 (0.77-0.97), wing_3 1.43
  (1.05-1.80), restricted area 0.25 (0-0.84, 1 helper of 55); |y| bands 1.04 / 0.93 / 0.91
  and the corner side 1.86 (0.71-3.22). Distance and bearing together change none of these
  materially. Same verdict with 3, 8 or decile bearing bins (scratchpad `bearing_binning.py`,
  a robustness probe for this record, not shipped).
- Left after the bearing: wing_3 at about 1.4x, the restricted area low, and `far` (beyond
  32 ft) at 2.5x: 15 helpers there with a median dx of -11.1 ft, defenders running back.
- **Qualifier on the helper definition (lesson 2):** `wind`'s docstring said a defender who
  only sinks "scores low"; that holds below the ball only, and is now corrected there. Above
  the ball the sink is help movement, so part of the 45.3 % with a helper is the defence's
  common retreat seen from above the ball. README and memoria need it next to the helper.
**(3) ANSWERED 2026-10-29: Javier accepts the three recommendations.** The thesis's first
half is retired as a claim; the thesis is the second half alone ("nobody helps the helper",
D1). Figure 1 becomes descriptive context, titled on where the defence goes in the first
second, with the corner as occupancy (share of off-ball defenders) and the share of helpers
above the ball in its strip, each with its n. The helper keeps its definition; the
above-the-ball qualifier travels next to the 45.3 %. Memoria: this goes in as v0.4, so B6,
C4, D4 and E2 each shift one version later again (v0.5, v0.6, v0.7, v1.0).
**(4) and (5) DONE 2026-10-29.** Figure 1 redrawn (1440 x 2360 px): title "Where the defence
goes in the first second of a drive"; the orange is now the helper rate per defender (kernel
mean of a 0/1 flag, same bandwidth), drawn where >= 80 defenders' kernel mass start; strip at
11 pt with the corner as occupancy and the above-the-ball share, every number from
`help_table` / `help_vectors` / `help_base_rate.csv`, and the script refuses to draw if the
three disagree on the helpers. Looked at three times: at a mask of 30 the smoothing painted
a rate on 6 of the 24 grid points inside `corner_3` (scratchpad `corner_mass.py`), none at
80, which also keeps the rate's binomial SE near 3.5 points; the white is "too few for a
rate" because the streamlines keep their own mask of 10; the typed "two in three" became the
computed share. Figure 2 byte-identical. Bearing bands now labelled without commas ("-1 to
-0.7"), because the memoria's CSV reader splits on commas. Memoria v0.4, 27 pages: new
section 12 "La esquina, con su tasa base" (12.1 rate per defender by |y| band; 12.2 distance
or bearing, with the inside defenders' median distance to the spot read from
`help_vectors.csv`; 12.3 the helper qualifier; 12.4 the decision); corrected section 6 (the
sink claim), 8.4 (the title sentence), 10.4 (note), 13.1 (a risk); 9.1 new figure and text,
9.3 the three looks; the corner base rate in the section 8 table; plan, pending and version
log. Four claims guarded in the build (it throws if the corner CI stops containing the middle
rate, if distance explains top_3, if top_3 or paint by bearing stop containing 1, if the
inside defenders become nearer the spot). Figure size now read from the PNG header. Read back
from the PDF text by an independent script against the CSVs: 17 of 17 section-12 numbers.
Open: Javier looks at figure 1; README and page carry the helper qualifier (C2, B3).
**Council screening of the redrawn figure 1, same day: 37/100, not ready** (Contrarian 30,
First Principles 40, Expansionist 55, Outsider 30, Executor 45, mean 40; the screener took
-3 for an unresolved blind spot, outside the skill's -5 to -10 range, so 35 by the rule;
either way under 50, no full council). Judged on a written description, not the image.
Core: with two figures allowed and the thesis now only the second help, a context figure
spends half the visual budget on an occupancy fact and a null; the 32 % against 5 % by
bearing is largely the helper definition itself, so it is a qualifier, not a finding; the
first image is where Originality and Communication are judged. Proposed: figure 1 becomes
the mechanism (one real drive: the helper stepping out, the man he leaves, the others
flat), the context moves to two README sentences. **ANSWERED 2026-10-29: Javier says do
it.** Plan: (a) B2 pulled forward as written below (`scripts/wind_scenes.py` ->
`reports/wind_scenes.json`, the D6 rule, its test), executed by a Sonnet agent; (b) figure 1
redrawn from that JSON: the rule's first drive in the drive frame, trails to 1.5 s of the
handler, the helper, the man he leaves and the three others, with that drive's own numbers
and where it sits in the distribution, so one drive is not sold as typical; the wind map
moves to the memoria and the page; (c) memoria 9.1, 12.4 and the version row follow (v0.4
is not yet shared, so the same version). Accept: the scene test passes and fails on its
mutation; every number on the figure greps to a CSV or the JSON; looked at before accepting.
**(a) B2 DONE 2026-10-29** (Sonnet agent; `scripts/wind_scenes.py`, `tests/test_wind_scenes.py`,
`reports/wind_scenes.json`): the strict D6 rule found a drive in each of the first four games
tried (114243, 114234, 114169, 114099; 10-16 drives pass every condition per game), nothing
relaxed; helper movement and per-frame projections at 25/38/50 equal `help_table.csv` and
`second_help_pairs.csv` within 0.01 ft; `check_scene` refuses a helper moved 0.5 ft (5.949
against 5.461); 309 tests pass. **(b) STOPPED before drawing:** the rule's first drive
(drive-114243-1-1, pull-up; helper 5.46 ft; man left 1.79 / 2.65 / 9.29 ft clear at 0 / 1.0 /
1.5 s; per-drive paired mean -2.61 ft, 23rd percentile of 252, median -0.25) does NOT show
"the others flat": at 1.5 s the three others move toward the man left -5.26 / +7.35 / +7.15
ft and toward the placebo +5.06 / +4.85 / +7.16. The council's figure assumed flat others;
the thesis is an absence against a placebo (a >= 4 ft mover toward him in 44 % of helped
drives, 42 % toward the placebo), which one drive cannot show as "nobody moves". Picking
another drive that looks flat would be the cherry-picking the rule exists to prevent.
Back to Javier. **He chose (2026-10-29) the drive as the measurement, not the conclusion.**
**(b) DONE:** `reports/figures/wind_figure_1_one_drive.png` (1440 x 2405 px), "How the absence
is measured, on one drive": the rule's first scene to 1.5 s (helper orange, man left a
diamond, the three others purple and numbered, handler's defender blue, other attackers
grey; hollow at the start, filled at 1.5 s); under it each other's projection toward him
against the placebo; the strip states the rule, the drive's numbers and its percentile (23
of 252, median -0.25 ft), and sends the claim to figure 2. Every number from
`wind_scenes.json`; the figure refuses to draw if its projections do not give the scene's
recorded mean. Looked at twice (man left hollow at both ends against the key; "23th"; a
number split from its unit; one decimal against figure 2's two). The wind map is now
`wind_map_league.png` (byte-identical to the v0.4 figure 1), out of the README, kept in
memoria 12.5 and for the page; `.gitignore` whitelist updated, the old file removed.
Figure 2 byte-identical. **(c) DONE:** memoria v0.4 (30 pages): 9 intro, 9.1 the new figure
with its numbers read from the JSON (the build throws if the first scene is not the first
game's choice), 9.3 the council's 37 and the stop, 12.4 revised, 12.5 the wind map, plan and
version row; section-12 readback still 17 of 17. 309 tests pass, ruff clean.
Open: Javier looks at the new figure 1; README C2 carries the corner and helper context in
two sentences.
**Council screening of the one-drive figure 1, same day: 48/100, not ready** (Contrarian 40,
First Principles 59, Expansionist 70, Outsider 40, Executor 55, mean 52.8; +5 unanimous
strength, -5 blind spot, -5 unrebutted red; under 50, no full council). Judged on a written
description. Strengths: the rule and the percentile make it honest; it teaches the
instrument figure 2 cannot; clean split, figure 1 the measure, figure 2 the result. Blind
spot, checked: the drive's -2.61 ft is one defender moving away (-10.3 of the -7.8 summed
difference; the second is +2.5, the third 0.0), so without the text a reader sees "two of
three rotate", and "the whole defence closes in" feeds that reading; the 252 drives appear
only as a percentile in a sentence; nobody checked legibility at README width. Proposed:
subtitle reframed as the measure, not the result; text cut to the bars plus one line; a
strip of the 252 per-drive means with this drive and the median marked; check at 800 px.
**Applied 2026-10-29 on Javier's word** (all but one point: the percentile stays on the
figure, not moved to the README, since it is this drive's qualifier, lesson 2). Subtitle:
"One drive, chosen by rule, to show the measure, not the result ... the measure is the
difference" ("closes in" gone); text cut to the bars, the strip and one line; the strip is
the 252 per-drive means from `second_help_pairs.csv` with this drive (purple, percentile
23) and the median (dashed) marked, and the figure refuses to draw unless the CSV gives the
scene's n, drive mean and median; the court is cropped above the drive (FIG1_TOP_FT 27, never
under 2 ft above any trail), so the drive fills the width. Checked downscaled to 800 px: body
text about 17 px, nothing overlaps. 1440 x 2593 px. Figure 2 byte-identical. Memoria 9.1
(the strip) and 9.3 (the 48, the one-defender split computed from the JSON, what was applied)
read back from the PDF: 7 of 7, plus the section-12 17 of 17.
**Javier, looking at it, asked "qué estamos representando en esta nueva figura 1?"**: it does
not explain itself, the Outsider's point in the 48. Written as pending in memoria 14.
**Figure 1 made to read on its own, 2026-10-29 (next session).** Decided: simplify, and NO
fourth council screening (its screenings judge a written description, which cannot test
whether an image reads by itself; Javier asked for fewer reviews). The test instead: a cold
read of the PNG by a fresh agent (Sonnet, image only, no project context: what question,
what happens on the court, what the bars and the strip mean, what it could not decode), on
the old figure and on the new. Old: guessed the bars' sign, unsure whether the placebo is one
player or a mean, "absence" and the corner labels undefined, misread where the man left
starts, purple bars read as the purple defenders. Applied: title is the question ("Does
anyone else move toward the man the helper left?", figure 2 answers it); players named on the
court, the six-entry legend gone; only the measure's cast in colour (handler black, his
defender pale, the other attackers the placebo's grey); arrows instead of hollow/filled
(a player who ends under 1.5 ft from his start gets no arrow); numbers 1-3 placed behind
each defender's own motion, off the trails; bars coloured by their target (black toward the
man left, grey toward the others); a "black − grey" column with each difference and the
mean, which is the number the strip places; the strip gets a "drives" axis; no corner labels
(`draw_court(sides=False)`, which also drops the margin they needed); court height computed
from its aspect. Second cold read: sign, placebo-as-mean and the difference read right, and
a correct, cautious conclusion ("whether -0.25 differs from 0 is figure 2's"). Its remaining
doubts fixed after it: "toward" defined (his own movement along the line from his start to
where the target is then), why the placebo (the whole defence sinks with a drive), the man
left's trail ends in an arrow (read as a link before), "drives with a helper". Both reads
said "60-90 s"; a model's timing is not evidence and is not used. A model decodes keys better
than a hurried reader: necessary, not sufficient. 1440 x 2685 px; figure 2 and the wind map
byte-identical; every number still from `wind_scenes.json` / `second_help_pairs.csv` behind
the same guards. Memoria v0.4 (31 pages): section 9 intro (the "nothing inside the court"
rule now scoped to figure 2 and the wind map), 9.1 caption and text (arrows, colours, the
difference column with its three values computed in the build), 9.3 a paragraph on this
pass, 14 pending updated, version row; read back from the PDF by script against the JSON,
13 of 13 (the first run missed three lists on a "+" the memoria does not print: format, not
values). 309 tests pass, ruff clean.
**Javier approved the new figure 1, 2026-10-29** ("apruebo la figura 1"). Memoria 9.3, 14 and
the version row say so. B1 (Sonnet) and B3 (Fable) were launched in parallel the same day.
**B1 DONE 2026-10-29** (Sonnet agent, checked here). `scbasket.wind.kernel_field(vectors,
helper, along, across, ...)` and `field_grid()`, with the constants (GRID_FT, BANDWIDTH_FT,
MIN_WEIGHT, RATE_MIN_WEIGHT, the grid's extent) moved out of `help_figures.py`;
`help_wind.py` writes `reports/help_field.csv` (957 cells: drive-frame x, y, kernel weight,
mean_dx, mean_dy, helper_rate; NaN under each threshold, weight kept, so no consumer
re-applies one); the wind map reads it. Three tests written first (one off-centre vector,
two vectors pulling a cell, the rate's own mask); the agent's mutations (dx/dy swapped,
weights reversed) failed 2 and 3 of them. Every other CSV help_wind.py rewrites is
byte-identical; figures 1 and 2 byte-identical; the wind map differs in 3 of 3.4 M pixels
(rows 879-882, cols 552-555, max channel diff 30, re-measured here), because the field now
comes from the vectors in memory and not from their CSV re-read (last-digit float parse);
rebuilt from the re-read vectors in a scratch dir it was byte-identical (agent's check).
Kept the new PNG: it is what the committed code produces from a clean clone. Memoria 12.5
and version row. 312 tests pass (agent's full run), ruff clean, `test_wind.py` 16 of 16 here.
**B3 written 2026-10-29 and accepted by Javier the same day ("dale")** (Fable agent): `tasks/wind_page.md`.
Slug `reports/nobody_helps_the_helper.html`; the clip is frames 0-38 at half speed (3.04 s),
frozen on the measured frame, then a pitch-only rise (1.5 s, dolly-zoom to an orthographic
camera) into figure 1's layout; every measure in a `#measure` DOM container hidden outside
`plan`; ball at its height in broadcast, flat in plan, its limit in words with no number (no
CSV here carries the gravity fit); no orbit; additions to `window.wind`: `T`, `flight(p)`,
`camera()`, `unproject`, `field`. Its quoted numbers checked here by script against the files
they name (`check_storyboard.py` in the session scratchpad): open shares 58.3/75.9 % at 1.5 s
and 58.5/72.6 % at 1.0 s, 8 of 9 sensitivity CIs contain 0 (3 ft at 1.0 s below), 957/756/478
field cells and 8.9 ft/s top speed, statuses 618/39/3, provider agreement 219 of 326 and 209
of 292 on resolved drives, scene 1's helper and man left moving to screen-left (dy -5.15 and
-9.20 ft at 1.0 s), ball z 10.06 ft at frame 38; one error fixed (scene 3's crop top is -12.8,
not -13.8). Open points settled here, technical: gravity in words only; the mirrored world
kept (the plan view equals figure 1); C2 moves to the 1.5 s open pair (written into C2).
**B4 DONE 2026-10-29** (Opus agent; screenshots looked at here). `scripts/wind_html.py` +
`scripts/wind_template.html` -> `reports/nobody_helps_the_helper.html` (2.38 MB: three.js
2.04 MB unminified, payload 119 KB); `vendor/three/` holds three@0.185.1 `three.cjs` (MIT,
sha256 checked by the build after LF normalisation; 0.186 dropped the single-file build).
The build refuses on the storyboard's guards (252 means, n, median, percentiles vs the JSON;
bars at frame 38 vs `second_help_pairs.csv`; nearest vs `second_help_drives.csv`; a contrast
CI excluding 0; the corner CI not containing the middle's rate; field masks vs thresholds;
non-finite numbers; three.js hash, exports, and loading under node). `tests/test_wind_html.py`
16 tests, one break per guard. Typed-number `rg` empty (a planted "5.5 ft" was caught, then
reverted). Agent's console drive: 148 checks, 0 failed, at 1440, 390, reduced motion and no
WebGL (hook ends at T 3.06 s, plan 1.57 s after the rise starts; true top-down within 0.03 ft;
bars, tile and strip within 0.01 ft of the CSVs). Deviations it reported, accepted: broadcast
camera refitted onto the hoop's axis (the storyboard's y = -8 and fov put tokens outside the
canvas and would roll the image on the rise); the rise narrows to 1°, not 2° (sub-pixel swap);
full-court floor with the far half's lines only; plan crop on the canvas's bottom edge; trails
40 % lighter than tokens (B5's pixel checks); `#league` not `#wind` (a `wind` id shadows
`window.wind`). The stage column is sticky, so the measure column scrolls beside it.
Not verified: the hidden-tab clock (headless cannot hide a tab). 328 tests pass, ruff clean.
**B5 DONE 2026-10-29** (Sonnet agent, written from the storyboard without reading the
template; rerun here: `uv run --extra page python scripts/drive_wind_page.py`, exit 0, 178
passed, 0 failed, 48 s). Path or URL argument (C1b reuses it). Expected values read from the
JSON/CSVs at run time; 136 injected elements checked by `data-src`/`data-value` and by their
printed digits; true top-down by pixel centroids through `unproject` (0.004 ft). Mutations,
each built to a scratch file: a typed `helper_help_move` (caught by data-value and digits), a
`seek` at t * 0.5 (18 failures), a perspective camera in plan (orthographic checks and the
unproject check, 0.31 ft), trails in broadcast (the pixel scan: 315-1203 px vs plan's
513-2207): exit 1 each. Its first run's 15 failures were all the driver's own (def_slot is
`others[j] - 5`; the percentile counts the drive itself; a "1.5s" key; a package-constant
data-src; a 16 px rule it narrowed to prose of 60+ characters, 12 px for short labels: its own
threshold). Not covered: a number typed with no `data-src`; the hidden-tab clock. New extra
`page = ["playwright>=1.45"]`, E501 ignored for the driver (embedded JS).
Javier then opened the page: the hook does not hook (B4b); the CC0 Quaternius UAL mannequin
(598 KB trimmed, 10 clips, no kit, no strafe, no dribble) was chosen by a research spike, and
a hook prototype with players was built in an isolated worktree (c59e335, merged 905ed37).
Javier watched its video and approved the direction (players, camera behind the hoop) and the
four fixes I found reviewing it as a stranger: players too small (about 50 px on the desktop
canvas, 25 px on the phone; the top 40 % of the frame is empty far court), tags landing on
the wrong player at the help step, 2.7 s before the hook moves (pucks: 0.46 s), bald heads
and no crowd. On this laptop's GPU (Intel Arc, ANGLE D3D11, headless) it runs at 16.7 ms a
frame, and B5 gives 176 of 178: the constant-rate check (the slow motion now plays about 0.3x
at the help and about 0.6x elsewhere) and the reduced-motion ink check, which fails the same
way on B4's page, so it predates B4b. Under SwiftShader the timing rows fail on frame time
alone, so B5 moves to the GPU. The four fixes, made in a second worktree pass (ef61367 to
c9e1cfe, fast-forwarded): camera at 32° (28° square) on the hoop's axis, framing the six story
players, ball and hoop with a sideways lens shift of at most an eighth; median story-player
height 85.6-109.9 px at 1440 and 41.9-55.2 px at 390 (from 39.4-44.1 and 16.7-19.2); tags
with a leader to their own head, 0 wrong, 0 overlapping, 0 on the ball on every frame; the
start-up cause was 12 shader programs compiled serially at the first draw (about 915 ms
blocked), now shared and compiled in parallel: first frame 0.56-0.70 s in my B5 run; hair,
skin tones and a seeded crowd, procedural. The ink flake was GPU readback (the first
`getImageData` rounds differently), not a redraw. Storyboard amended (slow-motion profile in
5.3). B5 on the GPU, my run: 184 passed, 0 failed; full suite 329 passed. Left, as a stranger
sees it: the bottom fifth of the desktop frame is dark apron, and the crowd shows only as a
thin strip, so the arena still reads empty; the helper hides the handler at the help step
(the story's own geometry from behind the hoop). Javier watched the video and said it hooks
("sí"); one short pass follows for the apron (a vertical lens shift) and a crowd that shows,
leaving the backboard and the hidden handler as they are.
**B4b CLOSED 2026-10-30.** The follow-up pass (branch `worktree-agent-ada1dd0fe1ae15475`:
21b09a4 bottom-room rule in the storyboard, 0c1ab86 vertical lens shift, faca83d crowd as
figures courtside, 8534983 the rule in B5 plus the software guard on every timed row) was
reviewed and merged. Stills at 1440 and 390, t = 0 and 0.75 s of the four scenes, read as a
stranger: the paint, not apron, fills the bottom; the tags land on their players; the crowd
reads as people (a row of figures across the top at 390, the two side stands' corners at
1440). Caught on the way: the first B5 rerun used main's driver on the branch's page (old
4-tuple rows), so the new rule had not run. With the branch's driver, alone on the GPU
(Intel Arc, ANGLE D3D11): branch page 184 passed, 0 failed, bottom room 6.0 % in all four
scenes at both widths, frame median 16.7 ms, playing in 0.47-0.67 s; main's c9e1cfe page
fails exactly the two framing rows, bottom room 18.7-36.9 % (so the rule can fail). Memoria
v0.4 amended before sharing (section 13 paragraph on B4b, phase B row, version row "29 y 30
de octubre"; 32 pages, the new sentences read back from the PDF). ruff and pytest green.
**B6 DONE 2026-10-30.** Memoria v0.5: new section 13 "La página" (13.1 what the storyboard
decided, 13.2 construction and the players, 13.3 what the console check asserts, 13.4 the
mutations it fails on, with its non-coverage), the four page paragraphs moved out of the Plan
section (kept there: D8 and GitHub Pages, with a pointer); Plan, Pendientes and Registro
renumbered 14, 15, 16, index and cross-references fixed, version row 0.5, phase B row updated.
35 pages (section 13 is pages 29-31). Read back from the built PDF: title in the index and
the body, titles 14 to 16, and each of the 21 numbers checked (184, 65 s, 16,7 ms, 0,47 a
0,67 s, 6,0 %, 18, 315 a 1203, 513 a 2207, 0,31 ft, 18,7 % and 36,9 %, 136, 101, 0,1 ft,
0,01 ft, 10 %, 1440, 390, ANGLE Intel Arc D3D11, c9e1cfe) found in the text.

### NEXT SESSION (left 2026-10-30)
1. Two merged worktrees remain under `.claude/worktrees/` (agent-a22b51f6d4661edd3, merged
   905ed37; agent-ada1dd0fe1ae15475, merged 2026-10-30, locked): remove them and their
   branches once Javier says so.
2. B4 reads `help_field.csv`; the wind map, now
   `wind_map_league.png`, is a top-down section of the page, not a README figure; since D8 the
   hook is the drive in 3D.
3. DONE 2026-10-30: README C2 (the corner as occupancy and the above-the-ball qualifier
   sit next to the 45.3 %; nothing says where help comes from).
4. Memoria v0.4 is built and committed (32 pages) and not yet shared; each step updates it.
5. B6 and C4 are done (memoria v0.6, section 13 "La página" and section 14 "El repositorio
   público y el README"). Phases B and C are ahead of their windows.
6. C1b PUBLISHED 2026-10-30 on Javier's "ok": public repo
   https://github.com/javiersr1996/nobody-helps-the-helper (main and tag bounce-final pushed;
   history scanned first: no secret patterns, no `data/`, largest blob 3.0 MB), Pages by
   `.github/workflows/pages.yml` (copies the committed page to `index.html`, no rebuild),
   https://javiersr1996.github.io/nobody-helps-the-helper/ answers 200, served sha256 equals
   the committed file; README links there. B5 against the URL: its `next()` row failed twice
   with identical values; the cause was the DRIVER (state and scrubber read in two round trips
   while the page plays), fixed in 8fe2146 (one evaluate; proven to fail on a page forced to
   desync). OPEN, the acceptance is not met: the start-up rows over the network, first frame
   0.97-1.18 s, then 0.57 s, then 1.15-1.52 s against the storyboard's 1.0 s (local
   0.47-0.67 s); 182 of 184 on the last run. Same bytes (877 KB gzipped), so it is the network;
   NOT yet measured how much is download vs parse vs compile. Next: measure that split (a
   Playwright trace or the Performance API on the URL), then decide with Javier: cut bytes, or
   paint the first frame before the heavy work, or state the target as local-only. Do not move
   the 1.0 s.
7. Waiting for Javier: B7 (he opened the local page today; checklist given in chat: start-up,
   the drive and its tags, the rise, the controls, the tracked/drawn note), C5 (read the README
   on GitHub), D1 (read `tasks/video_script_wind.md` aloud once: it must land at 55-62 s).
   Then D2 (`scripts/wind_video.py`).
8. DONE 2026-10-30: probe of the provider's `matchups` (never checked against video; an error
   would push the paired difference toward the claimed absence). Reading fixed before the
   run: HOLDS if every corroborated subset's helped-minus-unhelped CI contains zero and the
   helped mean stays <= 0; FAILS if a contrast CI lies above zero or the helped mean rises
   monotonically with corroboration. Result: HOLDS at 1.0, 1.5 and 2.0 s. At 1.5 s contrasts
   S0 -0.16 [-0.65, +0.32], S1 -0.09, S2 -0.40 [-1.04, +0.20] (144/232), S3 0.00
   [-0.68, +0.65] (122/167); helped means -0.68, -0.63, -0.84, -0.55. Coherence: handler's
   defender assigned in 595 of 618, nearest in 519 of 595, equal to `ballhandlerDefId` in 533
   of 595, none assigned twice; helper nearest to the man left in 190 of 258 (the session
   probe said 70 % of 280: it counted drives with no man left). Limit: consistency, not
   validation; S3 rules out only a contrast above +0.65 ft. Files: `scripts/matchup_check.py`
   (asserts its S0 rows equal `second_help_summary/contrast.csv`), `reports/matchup_coherence.csv`,
   `reports/second_help_matchup_check.csv`, `tests/test_matchup_check.py`, README Limits
   bullet, memoria 11.9 (v0.6).

### Settled while building, not before
- The whole defence sinks with the drive, so the x-component of the wind is partly retreat.
  The field shows it as it is; the helper is the max mover toward the ball's FUTURE
  position, which separates the two in the table but not in the picture. The caption says so.
- Team panels are illustration (one or two games per defence); the league field is the
  deliverable.

---

# Analytics Cup 2.0, first entry: nobody reads the bounce (scbasket)

## DEFINITIVE PLAN, set 2026-09-17. Read this section first.
Everything below this section is the RECORD: the earlier plan, four premises that failed,
and the measurements that killed them. None of it is deleted, because the record is part of
the deliverable. But the plan is here.

### The project
**Title: "Nobody reads the bounce"**, subtitle *the eight feet where the rebound is decided,
on SkillCorner's open ACB tracking*.

**Thesis, one line: the rebound is not read, it is occupied.** The two halves hold each
other up:
- **The ball is barely legible.** Knowing where the shot came from cuts the uncertainty on
  where the ball will land by 4%. The angle it comes down at, measured here for the first
  time from broadcast tracking, adds 2.5% more.
- **So the only thing a player controls is their own heading, inside a small zone.** Within
  4 ft of the rim, coming in rimward multiplies the chance of winning the board by 3.5 on
  the calibration games and by 5.6 on the held-out ones. Past 12 ft it is worth nothing.

If the bounce were legible, rebounding would be a reading contest. It is not, so it is an
occupation contest. That is falsifiable and it replicates on five games never touched.

### What is established (every figure below is measured in this repo)
Split throughout: CALIBRATION (114243, 114234, 114169, 114099, 114086) and HELD OUT
(178442, 179612, 184439, 188630, 191313), reported apart, never pooled.

**1. The zone is real and small.** 662 located rebounds: median 4.9 ft from the rim, 58.5%
inside 6 ft, 72.8% inside 8 ft, 92.3% inside 15 ft. Offensive rebounds land slightly closer
(43.8% inside 4 ft against 37.0%).

**2. The heading decides inside it and nothing outside it.** Lift of a rimward heading
(under 60 deg) over the rest, calibration then held out: 0-4 ft **+0.172 / +0.322**, 4-8 ft
+0.145 / +0.053, 8-12 ft +0.042 / -0.008, 12-16 ft +0.026 / +0.020, 16-22 ft +0.007 /
+0.031, 22+ ft +0.007 / -0.003. Within a FIXED 0-8 ft band, P(win) by angle band runs
0.251, 0.213, 0.136, 0.071, 0.056: monotone, 4.5x, so it is not proximity relabelled.
**Qualified 2026-09-17 while drawing P7.4**: that five-number curve is POOLED over both
halves, which this plan otherwise never does. Split, the held-out half is monotone (0.270,
0.207, 0.140, 0.115, 0.048) and the calibration half ticks UP in the last band (0.237,
0.217, 0.133, 0.051, 0.062), on 59 and 113 players. The 4.5x fall and the direction hold in
both halves; strict monotonicity is a property of the pooled curve only, and the figure says
so on its face.

**3. The zone scales with the shot.** Median rebound radius 3.4 ft for shots inside 8 ft
rising to 6.5 ft on threes; Spearman(shot distance, rebound distance) +0.336 / +0.367.

**4. Side bias: we reproduce Goldsberry, then extend him.** Primary source read: Kirk
Goldsberry, Grantland, 14 Oct 2014, about 95,000 rebounds, NBA 2013-14, SportVU. He reports
56% weak side on missed CORNER THREES, calls that a slim majority himself, and already notes
long rebounds invert. Ours, share landing opposite the shooter's side: threes 0.494 /
**0.568** (his 56%, reproduced out of sample), 16-23 ft 0.475 / 0.477, and **inside 16 ft
0.302 / 0.351, a pronounced STRONG-side bias**. The short-shot category is the new part.

**5. The ball does not help further.** Descent angle recovered on 407 clean approaches
(median 34.9 deg, q10 16.6, q90 52.6, apex 14.8 ft), nearly independent of shot distance
(-0.062 / -0.050), so it is genuinely new information. It still fails to predict the landing
radius: +0.018 on calibration against +0.190 held out, the halves disagreeing, which is the
F1 failure mode. sd of the landing radius 4.97 to 4.76 (shot distance) to 4.64 (plus
descent).

**6. The control field survives as an instrument, not as the deliverable.** P1.8 criterion 2
held out of sample: `area_valuable` alone separates "a shot follows within 3 s" at AUC
0.6205 to 0.6547 in all five held-out games.

### What ships
1. **The derived layer, open source.** Rebound approach kinematics from tracking: heading,
   speed, distance, the shot-scaled zone, and the ball's descent angle. The open bundle does
   not carry it and SkillCorner confirmed their video-annotated crash events are not coming
   for the competition. Published as a **DEFINITION, never a detector**: it measures
   vectors, not intentions. This framing is non-negotiable, see the ruling below.
2. **The finding**, with its two replicated negatives.
3. **The record of what failed.** Four premises down in one day, three stopped BEFORE any
   held-out game was read; thresholds frozen with commit hashes; one bar amended with the
   reason written before anything ran. Most entries do not ship this. It is 20% of the mark.

### Remaining work, in order
- [x] **P7.1 Test the untested.** DONE 2026-09-17. 36 tests added to
      `tests/test_tagging.py` (35 synthetic, 1 on a calibration game) for `approach_angles`
      (first, it carries the headline), `retreat_pairs`, `retreat_match_distance`,
      `high_side_for_pairs` and `tag_flight_features`. Every convention is pinned against
      hand-built geometry, and the heading is pinned to read NOTHING but position and
      velocity: the ball, the holder and the matchup cannot enter it, which is the intent
      ruling written as a test. Proof the tests bite: 14 deliberate mutations of the five
      functions (sign flips, the speed floor removed, the 2 s cap dropped, pairs read by slot
      instead of by id) were all caught. State: ruff clean, 207 tests without the `data`
      marker, 220 with it. No held-out game is touched.
      Noted, not fixed, for P7.3 to decide on: `retreat_pairs` documents a (4, 2) result but
      returns one row per non-shooting attacker, so a shot whose shooter is not in `off_ids`
      yields five pairs and no error, and unlike `tag_features` it does not check that
      `release` and `shots` have the same length. Separately, a heading built exactly on the
      60 deg bar lands either side of it by float dust; the band test says so rather than
      picking a side.
- [x] **P7.2 The shot-scaled zone**, formalised from finding 3 rather than a constant 8 ft.
      PRE-REGISTERED 2026-09-17 and frozen before any held-out game was read (D11).
      **The zone**: r(d) = 5.40 + 0.180 d feet, d the shot's distance to the rim. Fitted on
      the 325 located CALIBRATION rebounds by pinball loss at q = 0.75 over a deliberately
      coarse grid (0.1 ft on the intercept, 0.01 on the slope). q = 0.75 is the coverage the
      constant 8 ft band already reaches on calibration (0.745), so the two zones are
      compared at equal coverage and can only differ in WHERE they hold it. Lives in
      `scbasket.tagging` (`ZONE_COVERAGE`, `ZONE_INTERCEPT_FT`, `ZONE_SLOPE`, `zone_radius`,
      `rebound_zone_table`), graded by `scripts/rebound_zone.py`, whose `--fit` re-derives
      the two numbers from the data and prints them next to the frozen pair.
      **Effect available, measured on calibration BEFORE the bar was written** (lesson 4):
      coverage spread across the four shot bands is 0.230 for the constant zone against
      0.125 for the scaled one, at equal overall coverage (0.745 / 0.748) and equal mean area
      (201 / 211 sq ft). The scaled zone halves the drift; it does not cover more ground.
      **CRITERION**, relative on purpose so there is no number left to move (D13). On the
      HELD-OUT games: (1) the scaled zone drifts less across the bands than the constant one,
      (2) its overall coverage sits within 0.03 of 0.75, (3) its mean area is no larger.
      **Rebuilt on the way**: findings 1 and 3 had NO code behind them. Commit 111a9ac added
      50 lines of record and not one line of source, so nothing in the repo reproduced the
      headline zone numbers. Now `rebound_zone_table` does: on calibration, 409 rebounds, 342
      with a location, 325 with their shot's location too, median 4.81 ft, Spearman +0.336,
      which is the recorded figure exactly. The 84 unusable rebounds keep their rows as
      unknown instead of being counted as landing outside the zone.
      **RESULT, 2026-09-17.** The criterion was applied once, after the freeze (commit
      1e670ea), on 288 usable held-out rebounds. (1) PASS: coverage spread 0.039 scaled
      against 0.168 constant, a wider margin than calibration showed. (2) PASS: overall
      coverage 0.760, gap 0.010. (3) **FAIL**: mean area 222.9 sq ft against the constant
      zone's 201.1. Findings 1 and 3 replicate: median 4.93 ft held out against 4.81
      calibration (the held-out figure is 4.9248 and rounds to 4.92: see the audit below), Spearman +0.367 against +0.336, both the recorded figures.
      **Verdict FAIL, and the fault is in the bar, not in the data.** Condition 3 was already
      failing on the calibration half when it was written: the probe that produced the effect
      size printed 211 against 201, and the bar was written anyway. That is lesson 4's
      failure again, this time with the number in plain sight. It is also close to
      unsatisfiable in principle, because area is quadratic in the radius: a zone that varies
      but holds the same coverage carries a larger MEAN area than the constant one even when
      it is the smaller zone for most shots. Post-hoc diagnostic, recorded and NOT used to
      re-grade: at equal coverage the constant radius would be 8.16 ft on calibration and
      8.22 held out (areas 209.3 and 212.4) against the scaled zone's 211.2 and 222.9, and
      the scaled radius is under 8 ft on 48% and 41% of shots. So it is not a uniformly
      bigger zone, it is a differently shaped one.
      Work stops here to replan (D13). The bar is not moved to fit the result; any rewrite is
      recorded as a rewrite, with this entry left standing.
      **REWRITE, 2026-09-17, recorded as D13 requires.** Condition 3 is RETIRED. Not moved,
      not re-thresholded, not replaced by a friendlier number. The reason is that it cannot
      discriminate: it asks a varying zone to carry no more MEAN area than a constant one at
      matched coverage, and area is quadratic in the radius, so no shot-scaled zone can pass
      it, while one that did would be a zone that barely varies, which is the null this work
      is tested against. The retirement uses no held-out information, because the condition
      was already failing on the calibration half, 211 against 201 sq ft, when it was
      written. The failure entry above stays exactly as it fell, and the verdict is written
      as "passes the two conditions that can discriminate", never as "P7.2 passed".
      The concern behind condition 3 survives as a DIAGNOSTIC, reported and never graded: at
      equal coverage the constant radius would be 8.16 ft on calibration and 8.22 held out
      (209.3 and 212.4 sq ft) against the scaled zone's 211.2 and 222.9, and the scaled zone
      is the SMALLER of the two on 48% and 41% of shots. Differently shaped, not bigger.
      **Ships**: `ZONE_*`, `zone_radius` and `rebound_zone_table` in `scbasket.tagging`,
      `scripts/rebound_zone.py` (`--fit` re-derives the frozen pair), `reports/rebound_zone.csv`
      and `reports/rebound_zone_criterion.csv`, 10 tests of which one runs on a calibration
      game. P7.3 consumes `zone_ratio`, the landing distance in units of the zone its shot
      earned, which is the shot-scaled replacement for "within 8 ft".
- [x] **P7.3 The conditional model: who wins among the ten present.** Exactly one of ten
      wins each rebound, so ten independent probabilities is the wrong structure and today's
      numbers do not sum to one. Condition on the players actually there and rank them on
      heading, distance and speed inside the zone. This is what "who is best positioned"
      means and it is what a SkillCorner contact pointed at.
      PRE-REGISTERED 2026-09-17, frozen before any held-out game was read (D11).
      **The model**: a conditional logit over the ten on court, scored `APPROACH_LEAD_FRAMES`
      before the ball is won. P(player i wins) is their score's share of the ten exponentiated
      scores, so the ten probabilities sum to one by construction rather than by correction.
      Features, in frozen order: `zone_ratio` (distance to the rim in units of P7.2's
      shot-scaled zone), `rimward` (cosine of the approach angle), `speed`, `no_heading` (the
      player is under the 2 ft/s floor, kept in the choice set with `rimward` zeroed because
      removing a player would break the one guarantee the structure gives), `offense`.
      Fitted by Newton on the concave likelihood, numpy only, no new dependency. Lives in
      `scbasket/conditional.py`; `scripts/rebound_contest.py --fit` re-derives the frozen
      coefficients. Frozen beta: -0.871, +0.739, +0.124, +0.317, -0.456.
      **Sample**: 409 calibration rebounds, 324 graded. 44 have no cached frame at the lead
      and 41 are attributed to nobody by the provider; both keep their row with the reason.
      Zero rebounds are lost to a winner who is not among the ten, so the choice set closes.
      **Effect available on calibration, measured BEFORE the bar was written** (lesson 4):
      log probability per rebound -2.303 knowing nothing, -1.979 for distance and side alone,
      -1.858 for the full model. Top-1 0.100, 0.228, and 0.306, with the plain rule "whoever
      is nearest the rim wins" at 0.235.
      **CRITERION**, relative so there is no number to move (D13). Coefficients frozen from
      calibration and NOT refitted, on the held-out games the full model must (1) put more log
      probability on the player who actually won than the distance-only model does, and (2)
      rank the actual winner first more often than the nearest-to-the-rim rule.
      **Recorded now, not after the fact**: the shot-scaled `zone_ratio` and the raw distance
      in feet are indistinguishable inside this model on calibration, -1.8583 against -1.8607
      per rebound. The shot-scaled version is frozen because it is the object P7.2 argues for,
      not because it earned the place here, and both are carried so the difference stays
      visible.
      **RESULT, 2026-09-17.** The criterion was applied once, after the freeze (commit
      194f5c6), on 285 graded held-out rebounds of 359 (46 with no cached frame at the lead,
      28 attributed to nobody, again zero lost to a winner outside the ten).
      (1) PASS: log probability per rebound -1.8287 against the distance-only model's -1.9119,
      a gain of +0.083. (2) PASS: top-1 0.2632 against the nearest-to-the-rim rule's 0.2456.
      **Then lesson 1 splits the two apart, and they do not survive equally.** Per held-out
      game, condition 1 holds in FIVE of five: +0.168, +0.119, +0.027, +0.027, +0.074. The
      log-probability gain is a replicated effect. Condition 2 holds in THREE of five, losing
      184439 (0.258 against 0.323) and 188630 (0.250 against 0.269); pooled it is 75 correct
      against 70 out of 285, a difference of five rebounds. It passed as written because the
      bar was written pooled, and the pass stands in the record as it fell, but by lesson 1
      the top-1 margin is reported as a POOLED ARTEFACT and not as a result. The claim rests
      on condition 1. The script prints the per-game split every run so the qualification
      cannot be lost.
      Margins also shrink out of sample, which is worth stating plainly: the gain over
      distance is +0.121 on calibration against +0.083 held out, and top-1 0.306 against
      0.263. The model ranks the true winner in its top three on 197 of 285 held-out rebounds.
      **Ships**: `scbasket/conditional.py`, `scripts/rebound_contest.py`,
      `reports/rebound_contest.csv`, `reports/rebound_contest_criterion.csv`, 17 tests of
      which one runs on the calibration games. P7.4 draws from `rebound_contest.csv`.
- [x] **P7.4 The figure.** DONE 2026-09-17, `scripts/figures.py`, two figures, which is the
      maximum allowed. Both draw the halves ON TOP of each other rather than side by side,
      because the replication is the argument.
      1. `figure_1_lift_by_distance.png`: the lift of a rimward heading by distance to the
         rim. It reproduces finding 2 to the digit (0.172/0.322, 0.145/0.053, 0.042/-0.008,
         0.026/0.020, 0.007/0.031, 0.007/-0.003), which is also an independent check on it:
         the record's numbers came out of `angle_tradeoff.py` and these out of a second
         implementation reading the same rows.
      2. `figure_2_pwin_by_angle.png`: P(win) by angle inside a FIXED 0-8 ft band, the
         control that stops the heading from being proximity relabelled.
      Intervals are a CLUSTER bootstrap over the five games of each half, not over rebounds,
      because rebounds inside a game are not independent (lesson 1). Five clusters is few and
      the bands are correspondingly wide; they are there so a band of 26 players cannot look
      as solid as one of 608, and every point carries its count on the figure itself.
      matplotlib is declared as the OPTIONAL `figures` extra, the same rule scikit-learn
      lives under: the package still installs and runs on numpy and pandas alone, and every
      number behind both figures is in a `reports/*.csv` that needs no plotting library.
      The PNGs are regenerable output and `reports/figures/` is gitignored, so the script is
      what ships, not the images.
      **Found while drawing it**: finding 2's monotone claim is pooled over the halves. See
      the qualification added above; the figure states it rather than hiding it.
- [x] **P7.5 README, video script, package name, licence check.** DONE 2026-09-19.
      **README rewritten** from the superseded space-control project to this one: 995 words
      counting the code block, the alt text and the URLs, against a bar of 1000, and the two
      figures the rules allow. Its numbers were REGENERATED for it rather than copied out of
      this record: `scripts/figures.py` reprints the six lift values (0.172/0.322, 0.145/0.053,
      0.042/-0.008, 0.026/0.020, 0.007/0.031, 0.007/-0.003) and the five pooled angle values
      (0.251, 0.213, 0.136, 0.071, 0.056) to the digit, and the zone and contest figures come
      from `reports/rebound_zone_criterion.csv` and `reports/rebound_contest_criterion.csv`.
      The three qualifications travel INTO the README instead of staying in the record: the
      descent angle failing out of sample, top-1 as a pooled artefact holding in three games of
      five, and the retired condition named as retired. The four negative defensive-help probes
      ship there too, which is where that direction ends up.
      **The two figures are now versioned.** `reports/figures/` was gitignored on the rule that
      the script ships and the images do not. That rule is right for reproducibility and wrong
      for a README a judge reads on GitHub, where an unversioned PNG is a broken image. The
      gitignore now un-ignores exactly those two files by name, so any other figure stays
      ignored and the script is still what regenerates them.
      **Package name: `scbasket` kept.** Free on PyPI (404 on the JSON endpoint, checked
      2026-09-19), accurate for what the package now is, and renaming would touch every import
      and every test for nothing. What WAS stale is the description: `pyproject.toml` and the
      package docstring still advertised "shot-value-weighted space control", the project that
      F2 superseded. Both now say rebound approach kinematics, with the definition-not-detector
      ruling written into the docstring.
      **Licence check, all four layers.** This repo MIT (LICENSE, `pyproject.toml`). The data
      is SkillCorner's `opendata-basketball`, also MIT, and it is downloaded rather than
      versioned, so nothing of theirs is redistributed here. Dependencies: pandas BSD-3, numpy
      BSD-3 (with 0BSD, MIT, Zlib and CC0 components), scikit-learn BSD-3, pytest MIT, ruff MIT,
      matplotlib under its own PSF-style licence, which is BSD-compatible. Every one is an open
      licence and the competition's open-source-only rule is met. Versions in the environment
      that produced the figures: Python 3.14.3, pandas 3.0.5, numpy 2.5.3, matplotlib 3.11.2.
      **The video is a SCRIPT, not a recording**: `tasks/video_script.md`, 144 spoken words with
      the shot list and the timings, which is 58 s at 150 words per minute and 64 s at 135, the
      realistic pace for a script with numbers in it. It carries the cut order for a take that
      runs long and the ruling that "crash", "box out" and "tag up" are not said aloud either.
      Recording it is Javier's, and it is the one deliverable a session cannot produce.
- [x] **RESUELTO 2026-09-19: dos negativos medidos el 2026-09-17.** Quedaron en el registro
      en el commit 531f90f, y el (b) además SALE en el README, en la lista de negativos: una
      dirección cerrada con cuatro sondas es entregable, no un descarte que se esconde.
      El (a) se queda en el registro y en la memoria, porque es un coeficiente dentro de un
      modelo que sí ship, no una dirección. El detalle de los dos:
      (a) La etiqueta de punteo del proveedor se probó como variable del modelo condicional:
      coeficiente -0.178 y la log-verosimilitud sube de -1.8583 a -1.8571,
      +0.001 por rebote. Puntear cuesta rebote a través de la posición, que el modelo ya ve, y
      la variable no se gana el sitio. (b) La dirección de ayudas defensivas se exploró con
      cuatro sondas y se cerró, todas negativas. Ambas son calibración, nada congelado, ningún
      held-out abierto, nada commiteado fuera de esta nota. Detalle en la memoria del proyecto,
      `ayudas-defensivas-descartada`.
      **Las cuatro sondas, con sus cifras, porque el README apunta aquí y esto tiene que poder
      leerse en un clon del repositorio** (añadido 2026-09-19: hasta hoy esta entrada remitía a
      la memoria del proyecto, que no viaja con `git clone`, y un jurado que siguiera el puntero
      no encontraba nada). Todo es calibración, nada congelado, ningún held-out abierto, y no
      hay una línea de código en el repo porque la dirección se cerró antes de escribirlo.
      1. **Orden de ayuda medido geométricamente** (el defensor se aleja de su hombre mientras
         cierra hacia el balón): el primero en romper coincide con el defensor al que el
         proveedor le apunta el closeout el 26,5% de las veces, contra un 25,0% de azar. La
         versión escala-libre (coseno de la velocidad, reutilizando `approach_angles`) arregla
         el sesgo de distancia pero marca dos o más rompedores en el 72% de las penetraciones,
         porque durante un drive todo el mundo deriva hacia el balón.
      2. **Orden tomado de la etiqueta del proveedor** (varios closeouts en la misma jugada):
         31 jugadas con dos o más en calibración, 8 con tres. No hay muestra para un ordinal.
      3. **Ayuda -> mala colocación para rebotear**: una ayuda comprime a los dos equipos hacia
         el aro casi igual (defensa -0,371, ataque -0,342 en unidades de zona dentro de 8 ft),
         así que la ventaja relativa no se mueve. Y el box-out está en su techo: 4,4 de 5
         defensores ya están entre su hombre y el aro, haya habido ayuda o no.
      4. **Puntear el tiro -> perder el rebote**: el signo es el correcto y el efecto es nulo
         una vez descontada la posición. Metida como variable en el modelo condicional de P7.3
         da coeficiente -0,178 y sube la log-verosimilitud de -1,8583 a -1,8571, +0,001 por
         rebote. Puntear cuesta rebote a través de DÓNDE acabas colocado, que el modelo ya veía.
      Lo que quedó vivo por si se reabre: los closeouts como evento etiquetado (unos 600 en los
      diez partidos, distancias 13,7 -> 10,9 -> 4,9 ft), el recuento de colapso por drive, que
      se mueve con la etiqueta `blowby` del proveedor (1,64 contra 1,40), y una observación sin
      explotar: el que cierra es MENOS probable que el azar de haber sido el defensor más
      cercano (14% contra 25%), o sea ayuda el lado débil y no el contiguo. Caveat: celdas de 36
      a 84 casos, así que un efecto pequeño no se habría visto; lo que sostiene el cierre son
      cuatro encuadres independientes dando lo mismo, no cada uno por separado.
- [x] **P7.7 The ball, rebuilt as code.** OPENED 2026-09-19 by the P7.6 verification pass,
      which found that three groups of README numbers had no code anywhere in the repository,
      ever: the descent angle, the sd chain 4.97 -> 4.76 -> 4.64 (the "4%" and "2.5%" the
      README and the video OPEN with), and the Goldsberry side bias. Commit 111a9ac added
      fifty lines of this file and not one line of source, and the word "descent" never
      appeared in `src/`, `scripts/` or `tests/` in the whole history. (Corrected 2026-09-19:
      this entry, the script's docstring, `lessons.md` and the messages of commits cdb3cd5 and
      32c30ec first cited 580f6b7, which is a different commit and did ship 179 lines of
      `angle_tradeoff.py`. The zero-code commit is 111a9ac, exactly as the P7.2 entry above
      already said. The commit messages stay as they fell; this correction is the record.) It is exactly the hole
      P7.2 had to fill for findings 1 and 3, left open in the two places that carry the
      headline. Javier's call, with the three options measured: rebuild, freeze, and spend a
      held-out read on it.
      **The quantity**: the ENTRY ANGLE, how steeply the ball falls through rim height on the
      INCOMING flight, before it touches anything. `ball_entry_table` in `scbasket.tagging`,
      graded by `scripts/rebound_flight.py`. The record's own definition is gone with the
      scratchpad, so this is a new measurement of the same idea and not a reproduction: it
      reports a median of 43.4 deg against the record's 34.9. A LEVEL like that is a property
      of the definition (the median moves 47.3 -> 38.7 with the fitting window alone), so
      every claim is built on the ORDERING, which barely moves (Spearman 0.96 between a
      3-frame and an 8-frame window).
      **Effect available on calibration, measured BEFORE the bar was written** (lesson 3), on
      409 rebounds of which 300 have an angle and 256 also have both locations:
      Spearman(shot distance, entry angle) = +0.000, so it is genuinely new information;
      Spearman(entry angle, landing radius) = **-0.330**, negative in FIVE of five calibration
      games (-0.187, -0.592, -0.331, -0.216, -0.279); residual sd of the landing radius under
      the frozen coefficients 4.725 knowing nothing, 4.604 knowing the shot's distance, 4.276
      knowing the entry angle too. **This contradicts finding 5**, which reported +0.018 here
      and retired the ball as useless.
      **CRITERION**, frozen with the coefficients before any held-out game is read (D11),
      relative so there is nothing left to move (D13). Coefficients fitted on calibration and
      NOT refitted. On the held-out games: (1) the frozen model that reads the entry angle
      leaves a smaller residual sd of the landing radius than the frozen model that reads only
      the shot's distance; (2) Spearman(entry angle, landing radius) is negative in at least
      FOUR of the five games taken separately. Lesson 1 is built INTO the bar this time rather
      than applied to it afterwards, which is what P7.3's top-1 condition bought.
      **Tests**: 14 synthetic plus 1 on the calibration games. The one that matters is the
      circularity guard, `test_the_angle_is_the_incoming_flight_and_never_the_bounce_that_
      follows`: reading the angle after the bounce would predict where the ball lands from the
      ball already travelling there. Five deliberate mutations (crossing taken after the
      bounce, the angle's legs swapped, the whole descent fitted, the apex clearance dropped,
      a middle shot given a side) were all caught.
      **Side bias (finding 4) rides along as a DESCRIPTIVE table**, `side_bias_table`, no
      criterion: it is a share and was always reported as one. It keeps middle-of-the-floor
      shots, which contribute a near coin flip and pull every share toward 0.5, so it
      UNDERSTATES a bias rather than manufacturing one. On calibration that gives inside 16 ft
      0.424, 16-22 ft 0.448, threes 0.504, against the record's 0.302 / 0.475 / 0.494 under a
      definition that is gone. Same direction inside 16 ft, weaker.
      STATE AT THE FREEZE: 246 tests without the `data` marker, 16 with it, ruff clean, no
      held-out game read for this question yet.
      **RESULT, 2026-09-19.** The criterion was applied once, after the freeze (commit
      cdb3cd5), on 236 usable held-out rebounds of 359. (1) PASS: the frozen model that reads
      the entry angle leaves a residual sd of 4.511 ft against 4.700 for the frozen model that
      reads only the shot. (2) PASS: Spearman(entry angle, landing radius) is negative in FIVE
      of five held-out games (-0.322, -0.381, -0.264, -0.281, -0.482), pooled **-0.353**
      against calibration's -0.330. It is the first quantity in this project that comes back
      from the held-out half no weaker than it went in.
      **So finding 5 is overturned, not qualified.** The record said the ball does not help:
      it does, it is the only thing besides the shot itself that does, and it holds per game
      in both halves, which is the standard lesson 1 sets and which P7.3's top-1 failed.
      **What shrinks out of sample, stated plainly**: the angle's share of the work. It takes
      the sd from 4.604 to 4.276 on calibration (-7.1%) and from 4.700 to 4.511 held out
      (-4.0%). And the independence from the shot's distance is clean on calibration (+0.000)
      but -0.117 held out, small but no longer nothing, so "genuinely new information" is
      reported with that number next to it.
      **The thesis survives and gets sharper, because the absolute numbers did not move.**
      With the shot AND the ball's own trajectory, the landing radius still has an sd of
      4.5 ft, which is most of the zone. The bounce is barely legible to a camera measuring
      the ball after the fact; nothing here says a player can use it in the half second they
      have, and this work does not claim they can.
      **Side bias, rebuilt, does NOT reproduce the record, and the Goldsberry claim was
      answering a question he did not ask.** His 56% weak side is about missed CORNER threes.
      The record compared it to OUR band of all threes and called that a reproduction; cut to
      corner threes, which the `region` column gives directly, the two halves disagree: 0.414
      on calibration and 0.519 held out, on 29 and 27 rebounds. So this data neither
      reproduces nor contradicts him, and the README says exactly that. Outside his
      population: other threes 0.528 / 0.557 (weak side), inside 16 ft 0.424 / 0.477 (strong
      side), 16-22 ft 0.435 / 0.333. This is the THIRD time the Goldsberry claim has gone into
      the record wrong, after being written backwards on 2026-09-17, and the rule it keeps
      breaking is the one already in this file: nothing from the research report reaches the
      README until its primary source has been read. Now it has code and the right population,
      and the claim it supports is a refusal to claim.
      **REFUTED THE SAME DAY, by the P7.6 adversarial review, lens 2 of 3.** The criterion
      passed and the pass stands as it fell (D13); what fell is the CLAIM the pass was read
      as. Every number below was recomputed here independently before being accepted, and the
      reviewer's and this session's agree to three decimals. The angle is arctan(drop / run)
      and it predicts through its DENOMINATOR:
        - rho(run, landing radius) +0.570 / +0.568, rho(cross_dist, landing radius) +0.640 /
          +0.637, both larger than the angle's own -0.330 / -0.353.
        - rho(drop, landing radius) **+0.171 / +0.222**: steepness alone, which is what "a
          flatter ball carries further" was about, points the OTHER WAY in both halves.
        - partial(angle, landing radius | run) **+0.119 / +0.142**, the sign REVERSING once
          the run is held; given the crossing point instead, -0.267 / -0.220; given both,
          **-0.041 / -0.014**, which is nothing.
        - restricted to crossings that happen at the rim (within two contact radii), rho is
          -0.235 / -0.180 on 74 and 73 rebounds, and the association grows monotonically with
          how FAR from the rim the measurement was taken. That gradient is the signature of a
          third variable, not of an entry angle.
      So a ball still travelling outward when it reaches rim height lands further out. That is
      geometry, not a reading of the bounce, and the original thesis is the one that survives:
      **nobody reads the bounce.** Finding 5's conclusion was right; its number (+0.018) came
      from a definition that no longer exists, and its replacement was right about the
      correlation and wrong about what the correlation was.
      **A false claim in the code, found by the same review and corrected**: `_entry_angle_of`
      said the ball "has not touched the rim yet... the one mistake this function exists to
      avoid". Measured: on 15.3% of calibration rows and 12.6% of held-out rows the ball is
      already within a ball plus a rim radius of the rim axis at the crossing, or the fitted
      window falls less than half a foot, which is a ball rolling on the ring. The function's
      BEHAVIOUR is unchanged, because changing it after the held-out read would be fitting the
      definition to the result; the docstring now states the contamination rate, the table
      publishes `entry_drop_ft`, `entry_run_ft` and `cross_dist_ft` so a caller can exclude
      those rows, and two tests pin it.
      **Ships now**: the diagnostic lives in `carry_diagnostic` and `partial_spearman` in
      `scripts/rebound_flight.py` and in `reports/rebound_flight_carry.csv`, so the refutation
      is as reproducible as the claim it refutes. 17 tests on this path, of which one runs on
      the calibration games.
      **Ships**: `ball_entry_table`, `side_bias_table` and the `ENTRY_*` constants in
      `scbasket.tagging`, `scripts/rebound_flight.py` (`--fit` re-derives the frozen
      coefficients from calibration alone), `reports/rebound_flight.csv` and
      `reports/rebound_flight_criterion.csv`, 15 tests of which one runs on the calibration
      games.
- [x] **P7.6 Verification pass.** DONE 2026-09-19. Mechanical half: 264 tests with the data,
      ruff clean, the wheel builds and imports in a clean Python 3.11 venv on pandas and numpy
      alone, no data or secrets tracked, and a fresh clone followed as a judge would (227 pass,
      241 collected). Judgement half: three adversarial lenses, each told to refute and to
      default to refuted, on the pre-registration, the measurement and the README against the
      code. Two of the three refuted, and both were right: the entry angle's interpretation
      (see P7.7) and four README defects, all fixed. Every number either reviewer produced was
      recomputed here before it was accepted. The pass that the first lens could not break is
      the D11 discipline itself.
- [ ] **P7.8 The interactive page.** OPENED 2026-09-19 on the user's call: the analysis gets
      an output a judge can click through, a single self-contained HTML page in SkillCorner's
      own house style (black ground, the lime `#c8ff6a` and green `#00a82f` of their CSS
      variables, their wordmark for attribution only), with no CDN and no network at open
      time. It REPLACES nothing. The competition asks for one video, a README of at most
      1000 words and at most two figures, and those stay exactly as they are; the page is an
      extra the README links in one line.
      **Design, decided before writing**: `src/scbasket/report.py` becomes the one place the
      banded tables are computed (the lift of a rimward heading by distance, P(win) by angle
      inside the fixed band, and the cluster bootstrap over the five games of each half).
      `scripts/figures.py` loses its private copies and imports them; `scripts/report_html.py`
      reads the same tables plus the criterion CSVs and injects them as JSON into
      `scripts/report_template.html`. Not one number is typed into the page: every value on
      screen is read off a `reports/*.csv` (lesson 1). Slide 2 of the video still types three
      pairs of correlations by hand and is noted here, not fixed in this task.
      **The simplification, which is the second half of the ask**: the cluster bootstrap is
      2000 pandas `groupby`s per half per figure, 1m34 for two PNGs, and the page would have
      paid the same bill a second time. Resampling five GAMES only ever sums five rows of
      per-game counts, so the whole bootstrap is an integer index into a small array. Same
      seed, same draws (verified first: `rng.choice(size=(2000, 5))` consumes the stream
      exactly as 2000 calls of `size=5`), so the intervals do not move and the two committed
      PNGs stay as they are.
      **RESULT 2026-09-19, after the user rejected the first build as not worth reading.**
      The verdict was "either it grabs attention immediately or nothing", with two demands:
      draw the results ON a court, and make them move. Both were answerable with data already
      in the repository, which is the only reason they were done:
      - `rebound_zone_table` now also returns `reb_x`, `reb_y`, `shot_x`, `shot_y`, the
        published event locations it was already reducing to two distances. Nothing is
        reconstructed and no number moved: `reports/rebound_zone_criterion.csv` is identical
        after the rebuild. The page draws its court out of these.
      - `scripts/court_scenes.py` writes `reports/court_scenes.json`: eight whole rebounds as
        tracking, the ten players and the ball from the shot to half a second after the ball
        is won, with the frozen model's ten probabilities attached. The clips are chosen by a
        rule, half of them ones the model ranks first and half ones it gets wrong, so the page
        cannot show only the flattering ones. No player id, name or number is written.
      - **The check that earned its place**: two of the first eight clips had the winner 71 ft
        from the ball. Orientation is a property of the possession, and the frames after a
        defensive rebound already belong to the other team attacking the other hoop, so a clip
        that ran past the rebound mirrored itself halfway through. Fixed by cutting the clip
        to the rebound's own chance, and the check stayed in as a gate: a clip ships only if
        the winner is within 3 ft of the published landing point. On the eight that ship the
        worst gap is 0.60 ft, which is also an independent check of the orientation, the frame
        alignment and the slot order all at once.
      - The page leads with that clip running, and its first interaction is the reader picking
        who wins from the frame the model sees, before the model's ten probabilities are
        revealed on the court. The two figures, the zone, the ball and the record follow.
      **The three-point line was wrong in the first draft** and was found by measuring rather
      than by looking: the arc was drawn with SVG's small-arc flag, so its apex sat 10 ft
      short. The rendered path's bounding box is now checked against the geometry computed
      from `court.py`'s constants, and matches to the hundredth of a foot.
      **What the README paid**: it was at 999 words of 1000. The page and its two run lines
      cost 16, so the Goldsberry bullet's supporting numbers (other threes 0.528 / 0.557,
      inside 16 ft 0.424 / 0.477) came out of the README and went ONTO the page, where there
      is no word limit. Nothing left the deliverable.
      **One claim on the page was false and was corrected, not deleted**: the byline said every
      number on the page is read from a CSV. The charts and tables are; the negatives quote
      figures from this record that have no CSV of their own. The byline now says which is
      which, rather than the page quietly failing its own standard (lesson 1).
      **Still not done, and deliberately**: slide 2 of the video still types the three pairs of
      carry correlations by hand instead of reading `reports/rebound_flight_carry.csv`. It is
      the same defect the page just fixed for itself, in the other output, and it is left here
      as the next thing to do rather than folded into this task.
      **`/simplify` over the whole output layer, 2026-09-19.** Four reviewers, one per angle,
      on the diff. Applied:
      - the cluster bootstrap is vectorised over the five per-game counter rows instead of
        2000 `pd.concat`s per half per figure: **1m34 to 3.9 s**, and the two committed PNGs
        are BYTE-IDENTICAL to the ones in `HEAD` afterwards, which is the proof that the
        intervals did not move.
      - `scbasket.report` now also owns the pooled angle curve, which `figures.py` and
        `report_html.py` had a copy of each.
      - one `scripts/_record.py` reads the freeze commits for both the video's last slide and
        the page's last section; there were two keyword lists, free to drift.
      - the court geometry is no longer typed into the template: `scripts/report_html.py`
        ships `dataclasses.asdict(court.FIBA)` in the payload and the page reads all eight
        measurements from it. `ra_radius_ft` is FITTED by `scripts/fit_zone_geometry.py`, so
        a refit would have left the page drawing the old restricted area for ever.
      - `FLAT_ZONE_FT` and `MAX_COVERAGE_GAP` moved from `scripts/rebound_zone.py` into
        `scbasket.tagging` beside `ZONE_COVERAGE`, because the page states them too. The
        grader re-run after the move writes `reports/rebound_zone_criterion.csv` identical to
        the committed one, so nothing about the pre-registration moved with them.
      - smaller: the per-frame `getElementById` and the per-frame DOM read of a radius are
        both hoisted; one `IntersectionObserver` per bar block instead of a new one per
        filter click; `_coordinates` is now the single location parser in `tagging.py`
        (`side_bias_table` had its own copy).
      Skipped, with the reason: factoring the "grade one game with the frozen model" sequence
      out of `rebound_contest.py` (the grader is frozen and the shared part is already
      `rebound_choice_set`), and replacing the `half = "calibration" if ... else "held out"`
      line in three other scripts (a pre-existing pattern in files this work does not touch).
      **THE HOLE THE USER FOUND, 2026-09-19, and it was the right one.** Asked what happened
      to the defensive transition, and said the answer as it stood gave them nothing. They
      were right twice over. The F6 verdict above says it plainly: **a strong replicated buy
      side and NO established cost side** (`break_area` moves 2% and the halves disagree at
      n_committed 0, 515.6 against 490.6; `next_pts` moves the OTHER way, 0.919 to 0.562;
      n_committed 4 and 5 have 2 to 4 usable rebounds). That verdict was in this file and in
      `reports/angle_tradeoff.csv` and in NEITHER deliverable. An entry that says "occupy the
      glass" without saying it could not price what that costs is quietly overclaiming, which
      is the one thing this repository is built not to do.
      Now: the page carries the whole bucketed table (`D.cost`, straight from
      `reports/angle_tradeoff.csv`, both halves, n_committed 0 to 3) under the heading a coach
      would use, and the README carries it as a negative. It was paid for at 1000 words by
      dropping three run-block comments each script's `--help` already prints and one gloss
      the ball paragraph had already made; the defensive-help bullet gave up its README line
      and gained its two real numbers ON the page (26.5% against 25.0% by chance; the
      compression -0.371 against -0.342), where it had been asking to be trusted.
      **And a defect I wrote myself, caught in the same pass**: the new caption said "what
      does crashing cost you". `crash` is a banned word in every deliverable under the intent
      ruling, and the first place it appeared was the sentence about a coach's decision, which
      is exactly where it is easiest to write. Reworded, and the page now says so out loud
      where it would have been easiest to slip.
- [ ] **What is left before submitting** (deadline 18 Dec 2026, about 13 weeks):
      1. **Record the minute of video.** The picture is built and timed
         (`scripts/video_slides.py`, `tasks/video_script.md`, 141 spoken words, a 60.000 s
         silent cut measured with ffprobe). Only the voice is missing, and only Javier can
         add it.
      2. **Optional, offered and not yet answered**: animating slide 2's two arrivals, or a
         sixth slide drawing the shot-scaled zone on a court. Neither is needed for a complete
         entry.
      3. **Decide whether anything else ships.** The entry is complete as it stands: README,
         two figures, the derived layer, the record, the interactive page, and a video
         waiting for a voice.
      4. **Two checks on the page that this machine could not run** (P7.8, 2026-09-19):
         the phone layout, because the browser driven here does not change its render
         viewport, so the 900 px breakpoint is written and never seen; and the replay at 60
         fps, because a background tab throttles the frame callback, so the state machine was
         asserted from the console instead of watched. Both want two minutes on a real phone
         and a real window before submitting.
      IN PROGRESS 2026-09-19. Mechanical half done and passing: 247 tests (before P7.7),
      ruff clean, the wheel builds and imports in a clean Python 3.11 venv on pandas and numpy
      alone, no data or secrets tracked, licences checked in all four layers, and every zone /
      contest / lift / angle-curve number in the README reproduced by RUNNING the scripts. It
      is this pass that opened P7.7. README now 999 words of 1000 and two figures.
      **Found by cloning the repo and following the README as a judge would**: the test count
      the README quoted was the one from THIS machine's environment, not the one a clean
      install produces. `uv sync --extra dev` collects 241 tests, of which 227 pass, 1 skips
      (it needs the `forward` extra) and 14 need the dataset. The larger counts quoted before
      only collect where matplotlib and scikit-learn are already present.
      The README now states the clean-install numbers.
      **Known environment limitation, recorded and not fixed**: `uv sync --extra forward` on
      Python 3.14 builds scikit-learn from source and the build lands incomplete
      (`sklearn.metrics._pairwise_distances_reduction._middle_term_computer` missing), so the
      four F1b grading tests fail there while they pass against a wheel install. It is
      upstream, it touches only the superseded F1b path, and nothing in the deliverable
      imports scikit-learn, so the fix is not worth carrying: the README does not ask anyone
      to install that extra.
      **Adversarial review, lens 3 of 3 (the README against the code), came back REFUTED, and
      it was right on every count.** Checked here before accepting, all confirmed:
      (1) the README opened with "sd 4.73"; the value is 4.724858, which rounds to **4.72**.
      (2) it said the held-out median landing radius is 4.93 ft; it is 4.924779, which rounds
      to **4.92**. That digit came from THIS FILE, where the P7.2 entry rounded the 3-decimal
      display 4.925 upward, so the record carried the error into the deliverable. Both are
      corrected in the README; the P7.2 entry keeps its number with this note beside it.
      (3) the README pointed at `tasks/todo.md` for the defensive-help detail and this file
      pointed at a memory that does not travel with `git clone`. The four probes now live in
      this file, above, with their numbers.
      (4) the README glossed the conditional model's fifth feature as "team" when the code
      calls it `offense`, attacker or defender rather than which team: reworded.
      Its "clean" list is the useful half: the zone formula, both criteria CSVs, the lift and
      P(win) values, the game ids, the three freeze hashes, the figures being versioned and the
      word count all reproduce at the digit.
      **Test counts corrected again** (they had aged two tests in a day): a clean clone with
      `uv sync --extra dev` and no dataset collects 241, of which 227 pass, 14 are the
      dataset's and 1 needs the `forward` extra.
      **Lens 1's remaining half, delivered after the verdict, adds the sharpest point of the
      three**: the frozen criterion could not have discriminated. `run` alone, the denominator,
      passes condition 2 with the opposite sign in 5 of 5 calibration games (+0.548, +0.722,
      +0.494, +0.547, +0.519) and 5 of 5 held out (+0.611, +0.709, +0.388, +0.663, +0.504),
      and beats condition 1's bar more comfortably than the angle does (residual sd 4.079
      against the angle's 4.511, and the crossing position 3.854). A bar that the angle and its
      own denominator clear equally cannot tell them apart, which is the question in dispute.
      That is lesson 2's failure in a new shape: the test COULD fail, and still could not
      answer. Also from lens 1, and recorded because it is the only thing that came back clean:
      **selection is not related to the outcome**. Landing radius for rebounds with an angle
      against without: calibration median 5.42 against 4.45, held out 5.21 against 4.36,
      Mann-Whitney p = 0.31 and 0.40. And trimming the 10% most extreme angles at each end
      leaves -0.213 and -0.271, so the association is not a tail artefact either. It dies only
      where it should: controlling for the crossing position, or restricting to entries that
      really happen at the rim (-0.070 at p = 0.63, -0.042 at p = 0.78).
      **Adversarial review, lens 1 of 3 (the pre-registration), came back NOT REFUTED.** Run
      by a fresh reviewer with the instruction to refute and to default to refuted if
      uncertain, because the author of a claim is the worst judge of it. What it found:
      `git diff cdb3cd5 32c30ec -- src/scbasket/tagging.py scripts/rebound_flight.py` is
      EMPTY, so no threshold or coefficient moved between the freeze and the held-out read;
      the CSV committed at the freeze carries only the five calibration games; and
      `git log -S"entry_angle" --all` returns `cdb3cd5` alone, so the quantity did not exist
      before it. Then the test this entry did not think to run: shuffling `entry_angle` among
      the held-out rows 200 times, condition 1 passes 0 of 200, condition 2 passes 47 of 200
      (about the binomial rate), and **both together 0 of 200**. So the bar cannot be cleared
      by chance, which is the opposite failure to P7.2's, where the bar could not be cleared
      at all. Its one open point, raised as suspicious rather than as a refutation: the
      held-out -0.117 dependence on shot distance is in this record but not in the README.
      Checked and left as it is, because the README makes no independence claim: its "another
      7.1% and 4.0%" is the gain of the frozen model that ALREADY holds shot distance, so the
      omission cannot overstate anything. Two more lenses (measurement artefact and
      circularity; README against code) were still running when this was written.

### TWO NOTES FROM THE SIBLING PROJECT, 2026-09-19, both measured elsewhere
Measured in `skillcorner_screens`, a separate repository that shares only the public
bundle. Neither changes a number here; both change what can be said.

**1. The rules were re-read at source and one of them is stricter than this record says.**
The README limit is "a maximum of two figures OR TABLES in total, in any combination",
not two figures. Checked: this README carries two figures and no tables, so it complies,
but there is no room for a table. Also confirmed and not previously written down: one
basketball entry per region and no entering both regions; remote talks are not accepted,
so the Paris final needs someone there in person and travel is not reimbursed; and
finalists may receive additional ACB 2025/2026 data under a EULA between 8 January and
the final.

**2. The tracking's effective time resolution is 200 ms, not 40 ms.** Player and ball
tracks change slope every five frames: 46.6% of second differences are exactly zero for
fully detected players, and the autocorrelation of the acceleration peaks at lag 5 and
again at lag 10, in detected tracks, extrapolated tracks and the ball alike. P7.7 fits
the ball's entry angle over windows of 3 to 8 frames, that is 120 to 320 ms, at or below
the solution interval, so that quantity is partly fitted to interpolation. It is already
refuted on other grounds and ships qualified; this is a second, independent reason, and
it explains the window dependence P7.7 recorded and could not account for (the median
moving 47.3 to 38.7 degrees with the fitting window alone). The headline is safe: the
approach heading is measured over 0.48 s, which is two and a half solution intervals.

Deadline 18 Dec 2026, about 13 weeks from this plan. Finalists 8 Jan 2027, European final
17 Feb 2027 in Paris.

### Rules that carry into every session
- **D11**: parameters and thresholds are frozen and COMMITTED before any held-out game is
  read. **D13**: a pre-registered threshold that fails is reported as it fell and work stops
  to replan; it is never moved to fit a result.
- **Intent is not claimable from tracking.** SkillCorner's own position, given directly:
  tracking shows the points converging but not whether they converged from crashing or from
  drifting. No deliverable says a player crashed, tagged or boxed out. This closed the whole
  tagging direction and it does not reopen.
- **Nothing from the research report reaches the README until its primary source has been
  read.** It leaked twice on 2026-09-17: the Goldsberry claim was written up backwards, and
  a `break_area` agreement was called independent when the inputs were never checked. Still
  unverified: Maheswaran et al. SSAC 2012, Nylon Calculus 2020, the Fearne and Henare
  attribution for tagging up (out of scope now anyway).
- `tasks/lessons.md` holds the four lessons, each bought with a failure. Read them first.

### Superseded, kept below as the record
F1 (control field validated at release), F1b (the forward label), F2 (expected points
controlled), F3 (the possession as a time series), F5 (tagging up). The code for all of them
stays in the repo; `tag_features` and `tag_flight_features` ship as neither metric nor
deliverable.

### Where the evidence lives
`reports/angle_players.csv`, `angle_rebounds.csv`, `angle_tradeoff.csv`,
`validation_forward.csv`, `validation_forward_criteria.csv`, `construct_validity.csv`,
`control_params_forward.json`, `validation_release.csv`, `pilot_pick_signatures.csv`.
Scripts: `angle_tradeoff.py`, `construct_validity.py`, `validate_forward.py`,
`calibrate_forward.py`. Modules: `tagging.py`, `forward.py`, `control.py`, `value.py`,
`frames.py`, `court.py`, `epc.py`, `validation.py`, `quality.py`, `io.py`.

---

## THE RECORD BELOW THIS LINE (earlier plan, superseded 2026-09-17)


## Decision
Extend `scbasket` with its analytical side: a SPACE CONTROL model WEIGHTED BY SHOT
VALUE ("expected points controlled", EPC) that adapts football pitch control
(Spearman / Fernández-Bornn lineage) to basketball on SkillCorner's open data
for the Liga ACB 2025-2026.

It replaces the council's earlier decision (54/100: an ingestion and quality package
with no tactical metric). What already exists (loader, quality profile, noise
measurement) is not redone: it is the base. Uncertainty drops to a supporting section
(error bars on the control field where positions are extrapolated).

The intellectual contribution lies in the adaptation, which is not mechanical: in
football, control asks who would reach the ball first; in basketball the ball is
almost always controlled and what matters is who owns the locations that ARE WORTH
POINTS. Controlling the corner three is not the same as controlling half court.

Three basketball differences the model handles explicitly:
- A 28x15 m court with all 10 players always within help distance: small influence
  radii (feet, not meters) and a focus on the offensive half court.
- Shot clock: the time budget of control. It enters as a cap on the projection
  horizon of the velocities and as an analysis dimension.
- The hoop as focus instead of a goal line: the value surface is radial and
  discontinuous (three-point line), not a gradient toward the goal.

### Design constraint that governs the whole plan
10 games are about 2,000 possessions but almost a MILLION live frames. The project
rests on FRAMES, not possessions. Any deliverable that is a player ranking is
forbidden: there is no sample. Conclusions are about MECHANISMS (zone, role,
coverage, clock, contest level). Player ids live only in intermediate tables,
never in the README or the figures.

## Official rules (verified in the pysport.org bundle)
- Submission: 18 Dec 2026. Finalists: 8 Jan 2027. European final: 17 Feb 2027, Paris.
- There are NO tracks in 2.0. Suggested basketball topic, not mandatory: **Shot Quality**.
- Criteria, 20% each: Relevance, Methodology, Originality, Communication,
  Open-source potential.
- Individual or pair (maximum 2). Open license mandatory, public repo.
- Deliverable: 1-minute video with own voice + repo that works out of the box +
  README of at most 1000 words and at most 2 figures.
- Prizes: 500 euros per finalist, 1,500 to the regional winner as a grant for a
  Python package or PR.
- Open-source tools only. 14 weeks left, solo and part-time
  (about 110 hours in total).

## Verified data

### The three layers and the role of each
1. AGGREGATES, 293 games, `data/aggregates/acb_shotsaggregates_20252026.csv`, 326
   player-team-season rows (316 players; traded players have one row per
   team plus a `total` row). Role: estimate the VALUE SURFACE (points per
   shot by zone) over a whole season instead of over 10 games. Zones with
   `_attempts`, `_mades`, `_misses`, `_total_points`: `restricted_area`,
   `paint_non_ra`, `mid_range`, `corner_3` (and `corner_3_left/right`),
   `wing_3_left/right`, `top_3`, `above_break_3`, `backcourt`, `far`, `other`.
   Beware: `attempts` excludes misses with a foul drawn (FIBA convention) and
   `total_points` includes the extra free throw on and-ones.
2. TRACKING, 10 games at 25 fps. Role: the frame-by-frame control field. Live
   frames ALWAYS contain the 10 players and the ball, at 100% (92,188 live
   frames out of 124,796 in game 114086; the rest are dead ball, between 26% and
   55% depending on the game). Coordinates in feet, origin at the center of the court,
   x along the length (half court = 45.93 ft), y across the width (half width = 24.61 ft).
   Each position carries `speed` (ft/s, no direction), `isDetected` (0/1) and `predError`
   (ft, 90% quantile of the error). The ball carries a real z (median 3.5 ft, max 17 ft).
   Detection 76.2%-82.8% per game; mean predError 0.9 ft on detected positions and
   4.4-5.1 ft on extrapolated ones (17-24% of positions).
3. EVENTS, those 10 games, 20 families. Role: EXTERNAL VALIDATION, the ground
   truth. `shots` carries `contestLevel` (open/light/average/plus/blocked), `shotQuality`
   (0-100, SkillCorner's model), `closestDefDist`, `closestDefId`, `location`,
   `region`, `startFrame` (release), `outcome`, `three`, `shotClock`. `picks` carries
   `frame`, `bhrDefType` (none/ice/switch/over/blitz/under) and `scrDefType`
   (none/ice/soft/switch/blitz/show), the ids of both defenders and `locationType`.
   `matchups` carries defender-attacker assignments by interval
   (`startFrame`/`endFrame`) within each chance. `possessions` (with `leftHoop`,
   `offTeamId`, `defTeamId`) and `chances` (with `usable`, `transition`,
   `frontcourtFrame`) delimit the units of play. `touches` gives who has the
   ball in each interval.

### Coordinate orientation (to be verified in P0.3, not assumed)
The documentation says that in the events the attacked hoop is at negative x, and that
the tracking follows the camera axis. `possessions.leftHoop` indicates whether the attack goes
toward the broadcast's left hoop. Hypothesis: the attacking frame is obtained with
`(x, y)` if `leftHoop` and `(-x, -y)` otherwise. Checked against `shots.location`.

### Corrections to the council, verified against the real data
1. The "pick and roll coverage classifier" option is DEAD: the `picks` events
   already carry `bhrDefType` and `scrDefType` with the labels. Here those labels
   are used the other way around: as ground truth to validate that the control field has
   a distinct signature per coverage.
2. Uncertainty does NOT need to be modeled: each position carries `isDetected` and
   `predError` in feet. The work is propagating it, which is engineering.
3. Defensive data is NOT missing from the events: `matchups`, `closeouts` and the ids
   of both defenders in `picks`. What is missing are the season AGGREGATES for defense
   (the 293-game CSVs are offense only). The "space denial" output covers
   that declared gap in the dataset.

### Shot counts: three different denominators, do not mix them
Measured in P0.2. The 10 games carry **1,459** shot events in total. Of those, **1,433**
have both a valid `location` and a valid `region` (26 have both fields null): that is the
denominator for any geometry or zone agreement. And **1,414** are the ones the release
frame could be matched to in the tracking with both lineups on the floor: that is the
denominator for the contest analysis below. Every reported figure must say which one it
uses.

**Amended on 2026-09-15: the 1,414 figure is NOT REPRODUCIBLE and must never be cited
again.** Re-measured from the current code, the raw-stream match yields **1,445**: all
1,459 shots carry a `startFrame` and exactly 14 have the shooter absent from the
offensive lineup at that frame. Three candidate explanations for the old 1,414 were
tested and all fail: the P0.5 id canonicalization changes only 13 shooterIds across the
10 games, far too few for a 31-shot gap; requiring a full 5+5 lineup instead of shooter
plus two defenders gives 1,445 as well, identically, because live frames always carry 10
players; and intersecting with valid `location` and `region` gives 1,420, still 6 off.
The search was stopped there rather than dug deeper, because the raw-stream count is only
the legacy comparison section and nothing downstream rests on it.

**The denominators that stand, each verified twice:** 1,459 shot events; 1,433 with valid
`location` and `region`; 1,445 matched against the raw tracking stream; **1,360 matched
against the D12 cache, which is the denominator for F1 and everything after it.** The
prior-work percentages below were computed on the old 1,414 match; the two that P1.2
re-measured on 1,445 barely moved (`plus` 26.3% to 26.2%, `blocked` 43.1% unchanged), so
they are sound as orders of magnitude, but any figure that reaches the README must be
recomputed on a denominator from this list.

### Prior work on shot contest (verified with data, 1,414 shots)
"Shot Quality" relies on `closestDefDist`, the shooter-defender distance at release,
computed from two positions that carry their own error. Measured:
- Median `closestDefDist`: 3.59 ft. Mean combined error: 1.85 ft.
- 17.3% of shots have a distance smaller than their own measurement error.
- 21.6% have an ambiguous closest defender (the second one falls within the margin).
- The noise concentrates where it weighs most: `plus` 26.3%, `blocked` 43.1%, `open` 4.1%.
Validation of the computation: the distance recomputed from the tracking differs from the
published field with median 0.000 ft, 96.5% fall within 0.5 ft and the same
defender is identified in 95.1% of shots. This becomes the supporting section:
error bars on the control field (P1.2).

## SPEC

### Architecture
Package `src/scbasket/`, all numpy + pandas, no scipy or scikit-learn. Each new
module has a single responsibility and consumes the previous ones.

| Module | Status | Responsibility | Depends on |
|---|---|---|---|
| `io.py` | exists | Tracking streaming, events with pitfalls corrected, `Dataset` | - |
| `quality.py` | exists (+1 function) | Detection and predError profile; gains `sigma_from_pred_error` | `io` |
| `court.py` | new | FIBA geometry in feet, frame orientation, zones, grid | `quality` (constants) |
| `value.py` | new | Value surface (points per shot per cell) from the aggregates | `court` |
| `frames.py` | new | From the JSON stream to oriented per-game arrays, with velocities, ball handler and matchups; `.npz` cache | `io`, `court` |
| `control.py` | new | Control field (adapted Fernández-Bornn), Voronoi baseline, counterfactuals, Monte Carlo of the error | `frames`, `court`, `quality` |
| `epc.py` | new | Expected points controlled: total share, by zone, per-player contribution, per-chance series | `control`, `value` |
| `validation.py` | new | Release features, pick windows, rank metrics (AUC, Spearman, partial, permutation), calibration | `epc`, `frames` |
| `plotting.py` | new (`viz` extra) | Court, field as a heatmap, series | `court` |

Scripts in `scripts/` (one per output, all with `--root` and `--out`, all write
to `reports/`): `build_value_surface.py`, `build_frame_cache.py`,
`calibrate_control.py`, `validate_release.py`, `space_creation.py`,
`chance_series.py`, `pick_signatures.py`, `make_figures.py`, `run_all.py [--quick]`.

Tests in `tests/`: `conftest.py` with a SYNTHETIC dataset (2 possessions, 10 players,
about 300 live frames and 100 dead ones, and events from the families in use) so
the suite runs without the 730 MB. Tests that need real data carry the `data`
marker and are skipped if `data/raw/opendata-basketball/data/matches.json` does not exist.

### Public interfaces
```python
# court.py
HOOP_X = -40.76          # attacked hoop, ft (FIBA: 1.575 m from the baseline; attack toward -x)
THREE_RADIUS_FT = 22.15  # 6.75 m
CORNER_LINE_Y_FT = 21.65 # sideline at 0.90 m
ZONES = ("restricted_area", "paint_non_ra", "mid_range", "corner_3", "wing_3", "top_3",
         "backcourt", "far", "other")
def orient(xy: np.ndarray, left_hoop: bool) -> np.ndarray       # broadcast -> attacking frame
def zone_of(x: np.ndarray, y: np.ndarray, geom: CourtGeometry = FIBA) -> np.ndarray
def region_to_zone(region: str) -> str                          # 14 event regions -> 9 zones
@dataclass(frozen=True)
class Grid: cell_ft: float; centers: np.ndarray  # (G, 2), offensive half court only
             zone: np.ndarray                     # (G,) zone label per cell
def make_grid(cell_ft: float = 1.0) -> Grid

# value.py
def league_zone_values(shots_agg: pd.DataFrame) -> dict[str, float]   # PPS per zone, 293 games
def player_zone_values(shots_agg, canonical_ids, k: float = 50.0) -> pd.DataFrame  # optional, P2.4
@dataclass(frozen=True)
class ValueSurface: grid: Grid; values: np.ndarray; zone_values: dict[str, float]
def surface_from_zones(grid: Grid, zone_values: dict, smooth_ft: float = 1.5) -> ValueSurface

# frames.py
@dataclass
class GameFrames:            # one element per live frame inside a usable chance
    game_id: int
    frame_idx, wall_clock, shot_clock, period: np.ndarray        # (N,)
    possession_idx, chance_idx: np.ndarray                       # (N,) index into the tables
    off_ids, def_ids: np.ndarray                                 # (N, 5)
    xy: np.ndarray             # (N, 10, 2) attack-oriented; rows 0-4 offense, 5-9 defense
    v: np.ndarray              # (N, 10, 2) estimated velocity, ft/s
    pred_error: np.ndarray     # (N, 10)
    detected: np.ndarray       # (N, 10) bool
    ball: np.ndarray           # (N, 3)
    ball_holder: np.ndarray    # (N,) index 0-4 of the ball handler (touches) or -1
    matchup: np.ndarray        # (N, 5) index 0-4 of the defender assigned to each attacker or -1
def build_game_frames(dataset: Dataset, game_id: int) -> GameFrames
def save_npz(frames, path) -> None;  def load_npz(path) -> GameFrames
def get_or_build(dataset, game_id, cache_dir) -> GameFrames
def subsample(frames, every: int) -> GameFrames
def at_frames(frames, frame_idx: np.ndarray) -> GameFrames

# control.py
@dataclass(frozen=True)
class ControlParams:
    r_near: float = 4.0; r_far: float = 10.0; d_far: float = 30.0  # radius by distance to the ball
    v_max: float = 25.0                                            # ft/s, elongation by velocity
    t_h: float = 0.3                                               # projection horizon, s
    slope: float = 1.0                                             # sigmoid slope
def influence(xy, v, ball, shot_clock, points, params) -> np.ndarray  # (B, 10, G)
def control_field(frames, grid, params, batch: int = 64) -> np.ndarray  # (N, G) P_off in [0, 1]
def control_at_points(frames, points, params) -> np.ndarray             # (N,)
def voronoi_field(frames, grid) -> np.ndarray                           # (N, G) baseline
def remove_players(frames, mask) -> GameFrames                          # (N, 10) bool, counterfactuals
def control_with_uncertainty(frames, grid, params, samples=20, rng=None) -> tuple[np.ndarray, np.ndarray]

# quality.py (added)
def sigma_from_pred_error(pred_error) -> np.ndarray   # predError / 2.146 (90% quantile of a 2D Rayleigh)

# epc.py
def epc_share(p_off, surface) -> np.ndarray                 # (N,) share of the court value under control
def epc_by_zone(p_off, surface) -> pd.DataFrame             # (N x zones)
def player_contributions(frames, grid, params, surface) -> pd.DataFrame  # frame x player: own, created, denied
def chance_series(frames, grid, params, surface, every=5) -> pd.DataFrame

# validation.py
def release_features(frames, shots, grid, params, surface) -> pd.DataFrame
def rank_auc(score, label) -> float
def spearman(a, b) -> float;  def partial_spearman(y, x, z) -> float
def permutation_pvalue(stat, groups, n=2000, rng=None) -> float
def calibrate(frames_by_game, shots_by_game, grid, surface, param_grid) -> pd.DataFrame
def pick_windows(frames, picks, grid, params, surface, before_s=1.0, after_s=2.0) -> pd.DataFrame
def break_points(series, shots, actions) -> pd.DataFrame
```

### Modeling decisions
- D1. Form of the control: Fernández-Bornn (2018). Each player i exerts a bivariate
  Gaussian influence centered on their projected position, elongated in the direction
  of their velocity, with a radius by distance to the ball; offensive control in a
  cell is `sigmoid(slope * (sum_off I_i - sum_def I_i))`. Chosen because it asks
  who owns the space, not who reaches the ball (which in basketball is held), and
  because its ingredients come with the tracking. Discarded: Voronoi (kept as the
  baseline to beat), full Spearman with time to intercept (requires
  accelerations, and differentiating positions twice with 4.5 ft of error is noise), learned
  models (no ground truth for "control", and with 10 games there is no sample).
  **Amended after P1.1 (user decision of 2026-09-15): `slope` is a READOUT SCALE
  parameter, not a geometric one.** Because `P_off = sigmoid(slope * score)` is monotone
  in the score, every rank metric in F1 (the AUC and both Spearman figures of P1.4 and
  P1.5) is exactly invariant to it: slopes 0.5, 1 and 2 give identical rankings. F1
  therefore cannot identify it and must not pretend to. It is fixed at 1, only the three
  geometric parameters are calibrated, and its effect on the reported `epc_share` values
  is shown in F2 as a sensitivity band over {0.5, 1, 2} rather than as a fitted number.
- D2. Radii in feet, not meters: `r_near` = 4 ft next to the ball, `r_far` = 10 ft at
  30 ft or more from the ball, linear interpolation. Rationale: football uses 4-10 m; the
  court is 3.6 times shorter and everyone is within help distance. The values
  are initial: they are calibrated in P1.4 against `contestLevel`, never by eye.
- D3. Time and shot clock: the position is projected `t_h` seconds (0.3 s as a
  starting point, calibrated) along the velocity; the horizon is clipped to
  `min(t_h, shotClock)`, so that with the clock expired the control is purely
  positional. The clock is also an analysis dimension (bands 24-16, 16-8, 8-0 s).
  Discarded: per-cell horizon equal to the pass flight time (adds `v_pass`,
  which cannot be calibrated separately from `t_h` with 10 games).
- D4. Grid: 1 ft, offensive half court only (46 x 49, about 2,250 cells). A
  1 ft cell is at the level of the error of detected positions (0.9 ft); anything
  finer is faking precision. 2 ft is too coarse for the corner-three strip
  (3 ft between the line and the sideline). `--quick` uses 2 ft.
- D5. Value surface: constant per zone from the 293-game aggregates,
  `PPS_zone = sum(zone_total_points) / sum(zone_attempts)` over rows with
  `team_name != 'total'`; left and right are merged (the league is symmetric);
  `backcourt`, `far` and `other` are worth 0; Gaussian smoothing of 1.5 ft at the borders
  so as not to create artificial steps in the field. Discarded: fitting a
  continuous surface with the 1,414 shots of the 10 games (small sample), weighting
  by shot frequency (confuses usage with value), an in-house xP model (not needed,
  the zone value already comes from the whole season).
- D6. Headline metric: `epc_share = sum_c P_off(c) V(c) / sum_c V(c)`, share of the court's
  value under offensive control, in [0, 1], and its decomposition by zone.
  Communicable ("the offense controls 38% of the value; after the screen it rises to 52%,
  almost all on the weak side") and without odd units (points per square foot).
- D7. Per-player counterfactuals (each one a frame without that player):
  - `own_j`: value of the cells where j is the attacker with the greatest influence.
  - `created_j` (off-ball creation): change in the value controlled by the TEAMMATES
    (cells where j does not dominate) when removing j and their assigned defender (`matchups`;
    if there is no assignment, the closest defender). It can be negative: a non-shooter
    whose defender helps inside costs their teammates space. Computed only in
    frames where j is not the ball handler.
  - `denied_k` (denial): rise in the value controlled by the offense when removing
    defender k. It is monotone non-negative by construction.
  Limitation declared in the README: the counterfactual is static (it does not know where
  the defender would be if j were not a threat); that is why the analysis also looks at the
  DYNAMICS (how `created_j` changes during cuts and off-ball screens).
- D8. Uncertainty: Monte Carlo perturbation of the positions with
  `sigma = predError / 2.146` (for an isotropic 2D error, the 90% quantile of the radius
  is 2.146 sigma), K = 20 samples, only on event frames (release, picks),
  not on the million frames. It replaces the heuristic ambiguity bound of the prior
  work. It reuses `quality.py`, it does not duplicate it.
- D9. Temporal sampling: 5 Hz (one in every five frames) for series and aggregates; consecutive
  frames at 25 Hz are autocorrelated and add no information. 25 Hz
  only on event frames.
- D10. Velocity: centered difference over ±2 frames of positions smoothed with a
  5-frame moving average, computed on the cached arrays (respecting possession
  cuts and jumps in `frameIdx`), capped at 30 ft/s. The provider's `speed`
  serves as a check (expected correlation ≥ 0.9), not as input: it carries no
  direction. Discarded: Kalman (over-engineering).
- D11. Calibration and validation split by GAME. The 5 oldest by date calibrate
  (114243, 114234, 114169, 114099, 114086); the remaining 5 validate
  (178442, 179612, 184439, 188630, 191313). Parameters are frozen in
  `reports/control_params.json` with the commit hash BEFORE touching the validation
  games. Every number in the README comes from the held-out games.
- D12. Frames that enter: live, inside a `chance` with `usable == True`, with
  non-null `shotClock` and with 5 + 5 players. How many are discarded and why is printed.
- D13. PRE-REGISTERED validation thresholds (P1.5). If they are not met, it is reported
  as a finding and work STOPS to replan; thresholds are not adjusted to the result.

### Conventions
- Units: feet and seconds throughout the package. Attacking frame: the attacked hoop at
  `(HOOP_X, 0)`, attack toward negative x, left side of the attack at positive y.
- All computation over frames is vectorized in batches (`batch` frames at a time) over
  `(N, 10, 2)` arrays; never a Python loop per frame inside the model.
- Nothing in the package reads the tracking twice: `frames.py` converts it once to
  `.npz` per game in `data/interim/` (ignored by git).
- **LANGUAGE: the whole repository is in ENGLISH.** User decision of 2026-09-13.
  Docstrings, comments, variable and test names, assert and error messages,
  script console output, README, figures and commit messages. This plan file too.
  It is a submission to an international competition with a European and US jury, the
  README and the video are in English, and the package aims to be used by the community.
  The only thing that stays in Spanish is the conversation with the user.
- Style: `from __future__ import annotations`, lines ≤ 100, numpy and pandas only.
  Ruff with `E, F, I, B, UP`.
- Tests: per module, happy path plus two edge cases. There is no UI, so Playwright
  does not apply.

## Phases and tasks

Execution mode chosen by the user on 2026-09-13: **mixed per plan**. Each
task runs with the model of its tag, `sonnet` or `PLANNER` (Fable 5.1).

Schedule compressed to 12 weeks by user decision, leaving weeks 13 and
14 as reserve for the scenario where a pre-registered threshold fails in F1 and forces
a replan. Cost of the compression: the weekly load rises from about 7.5 h to about
8.4 h. Hour split (about 101): F0 12 h, F1 30 h, F2 18 h, F3 18 h, F4 15 h, V 8 h.
`[optional]` tasks are left out unless a phase closes ahead of schedule.

### F0. Verifiable foundations (weeks 1-2)
Closed objective: test suite and lint green, geometry validated against the
provider's labels, and the league value surface written to `reports/`.

- [x] P0.1 Test and lint infrastructure `[sonnet]`
  - Does: `ruff` in the `dev` extra with the config above; `tests/conftest.py` with the
    synthetic dataset (fixture `synthetic_root` that creates `matches.json`,
    `player_id_aliases.csv` and one game with the three files; includes 2 possessions
    with different `leftHoop`, 2 `shots`, 1 `pick`, 1 `off_ball_screen`, `matchups`,
    `touches`, `chances` with `usable`); `data` marker with `skipif` if the real
    dataset is absent; three smoke tests on `io.py`.
  - Accepts: `uv run pytest -q` green with ≥ 3 tests without real data;
    `uv run ruff check .` with 0 errors (fix whatever trivial issues come up in the existing
    code, without refactoring).
- [x] P0.2 Court geometry and zone classifier `[sonnet]`
  - Does: `court.py` with the FIBA geometry in feet, `zone_of`, `region_to_zone`,
    `make_grid`. The `restricted_area` radius and the angular corner/wing/top
    boundaries are not documented: they are fitted by grid search
    (radius 3-6 ft, angles) maximizing agreement with `shots.region` of the 10
    games, and the fitted values remain as constants with the agreement noted.
  - Accepts: agreement of `zone_of(location)` against `region_to_zone(region)` ≥ 95% over
    the 1,433 shots with a valid `location` and `region` (test with `data` marker that
    prints the number); agreement with
    `three` ≥ 99%; 6 known points in a unit test (hoop, corner three,
    top of the three, elbow, backcourt, out of bounds).
- [x] P0.3 Tracking orientation `[sonnet]`
  - Does: `orient` in `court.py`; short script that, for each shot, compares the shooter's
    position in the tracking at `startFrame` (oriented with the `leftHoop` of its
    possession) against `shots.location` under the two rotation hypotheses.
  - Accepted, but the criterion had to be re-specified. It originally read "exactly one
    hypothesis has >= 99% of shots with difference < 0.5 ft". The real numbers: hypothesis A
    (`(x, y)` if `leftHoop`, `(-x, -y)` otherwise) reaches **96.6%** within 0.5 ft, median
    0.000 ft, p95 0.24 ft; hypothesis B reaches **0.0%**, median 76.2 ft.
    This is NOT a threshold lowered to fit the result. The criterion was measuring the wrong
    quantity: it conflated "which rotation is right" with "how precise the tracking is". On
    the question it meant to settle, the separation is total: A is closer on **1,389 of 1,389**
    matched shots, zero exceptions, and the worst error under A (2.88 ft) sits far below the
    best error under B (6.53 ft). There is no overlap, so no amount of extra data could flip it.
    The residual 3.4% is tracking noise, not rotation error: it is uniform across periods
    (94.7% to 97.6%), no possession has a null `leftHoop` (0 of 1,433), the failing shots keep
    the correct sign, and their 1 to 3 ft error matches the documented `predError` of 1.4 to
    1.9 ft plus the frame lag on the release of a jump shot.
    Re-specified criterion, met: the winning hypothesis is closest on 100% of matched shots,
    with no overlap between its worst error and the other hypothesis's best. The `data` test
    asserts 95% within 0.5 ft, and the real 96.6% is recorded in the `orient` docstring.
    Note for P1.5: this is the reason the validation thresholds there are pre-registered
    BEFORE seeing the numbers. This one was not, and it had to be rewritten after the fact,
    which is exactly the situation D13 exists to prevent.
- [x] P0.4 League value surface `[sonnet]`
  - Does: `value.py` (`league_zone_values`, `surface_from_zones`) and
    `scripts/build_value_surface.py`, which writes `reports/value_surface_zones.csv`
    (zone, attempts, points, PPS) and `reports/value_surface_grid.csv`.
  - Accepts: 6 zones with value; `restricted_area` is the highest and `mid_range` the lowest;
    all in [0.5, 1.6] points per shot; the sum of attempts per zone matches
    `attempts` of the same rows with deviation < 1%; unit test with synthetic
    aggregates (including a `total` row that must NOT be counted) and test that the
    smoothed surface integrates the same as the stepped one (< 1e-6 relative).
- [x] P0.5 Per-game arrays with cache `[PLANNER]`
  - Does: full `frames.py` (`build_game_frames`, D10 velocities, ball handler from
    `touches` with fallback to the attacker closest to the ball at < 3 ft, `matchup` from
    `matchups` by interval, D12 filters) and `scripts/build_frame_cache.py` which leaves
    `data/interim/{gid}_frames.npz` for the 10 games.
  - Accepts: for 114086, 92,188 live frames are read and how many remain after
    D12 is printed along with why the rest is discarded; each row has 5 + 5 players; the
    magnitude of the estimated velocity against the provider's `speed` has Pearson ≥ 0.9
    on detected positions; `matchup` coverage printed (if < 80%, it is documented
    and the fallback is used); build ≤ 3 min per game; `.npz` ≤ 50 MB per
    game and load ≤ 2 s; unit tests on the synthetic: orientation per
    possession, velocity of a player in a straight line (error < 1%), ball handler,
    `subsample` and `at_frames`.

  - **Result, with three findings that change what comes next.**
    1. D12 is far more aggressive than expected: of 92,188 live frames in 114086 only
       **51,496 survive (55.9%)**, and across the 10 games 537k of 830k. The bulk of the
       loss is frames outside any chance (33,498, of which 32,758 have the clock stopped:
       players standing on the floor during free throws and timeouts), then non-usable
       chances (3,656) and null `shotClock` (3,538, the first 1.6 to 5.5 s of a chance
       before the clock is set). Zero frames fail the 5+5 test. The filter is right, but
       every later sample size must be quoted against 537k, not against a million.
    2. **Matchup coverage is 69.8% (64% to 71% across the games), under the 80% bar, and
       the reason is structural, not a bug**: the provider only assigns matchups from
       `frontcourtFrame` onward (94.6% after it, 4.0% before). The documented fallback
       (nearest defender) covers the rest. Any conclusion that leans on assignment must
       either restrict itself to frontcourt frames or declare it uses the fallback.
    3. **The provider's `speed` is NOT an independent check on our velocity estimate.**
       Pearson is 0.99995 (n=476,734, MAE 0.025 ft/s): it is the same smoothed derivative.
       D10 treated it as a cross-check; it is a reproduction. The velocity estimate is
       therefore unvalidated against anything external, and P1.4 should not count this
       agreement as evidence.
  - Performance is comfortable: build 4 to 13 s per game (budget 3 min), `.npz` 14.7 to
    17.6 MB (budget 50 MB), load 0.03 to 0.06 s (budget 2 s), peak memory 208 MB.

### F1. Control field and validation at release (weeks 3-6)
Closed objective: the model calibrated on 5 games and VALIDATED on the other 5 against
`contestLevel` and `shotQuality`, with error bars. First demo of the project.

- [x] P1.1 Control model `[PLANNER]`
  - Does: `control.py` with `influence` (analytic 2x2 quadratic form, no
    `np.linalg`), batched `control_field`, `control_at_points`, `voronoi_field`,
    `remove_players`.
  - Accepts: tests: `P_off` in [0, 1]; symmetry when swapping teams
    (`|P + P' - 1| < 1e-9`); a lone attacker against nobody gives `P > 0.99` at their
    position; with radii → 0 it matches Voronoi in ≥ 99% of cells; batch of 1 and of
    64 give identical arrays; with `shotClock = 0` the result does not depend on `v`.
    Performance: one game at 5 Hz with a 1 ft grid ≤ 2 min on the `.npz`
    (time printed by a `data` test).

  - **Result. Gate green (ruff clean, 99 tests, 6 with the `data` marker). Performance
    comfortable: 10,305 frames at 5 Hz x 2,254 cells in 19.1 s against a 120 s budget;
    Voronoi 7.9 s. On 114086 the field has mean `P_off` 0.494 and range [0.047, 0.898],
    and agrees with the Voronoi side on 87.8% of cells. Two acceptance criteria could
    not be met literally and were re-specified to the quantity they meant; one finding
    changes P1.4.**
    1. "Radii → 0 matches Voronoi in ≥ 99% of cells" fails at every radius for a
       float64 reason, not a modelling one: `sigmoid(score)` rounds to exactly 0.5 once
       every player is farther than 8.5 sigma from the cell, so the smaller the radius
       the more cells are undecided (at r = 1 ft only 20.6% are decided). The quantity
       meant is the SIGN of the influence surplus, so agreement is now measured on
       decided cells and the mismatch rate is required not to rise as r shrinks:
       99.86% at r = 4 ft, 100.0% at 2 ft and at 1 ft. An exact companion property was
       added: with a uniform radius the dominant player of every cell equals the
       nearest player on 100% of cells, no tolerance. The 99% threshold was not touched.
    2. "A lone attacker gives `P > 0.99` at their position" is unreachable under D1 at
       the default slope, and not because of the implementation: the influence is
       normalised to 1 at its centre, so a single player's ceiling is
       `sigmoid(slope)` = 0.731 at slope 1, and `P > 0.99` would need slope > 4.6.
       Verified independently. The test now asserts `P == sigmoid(slope)` to 1e-12,
       that it is the field maximum, that no cell falls below 0.5 with nobody
       defending, and the literal `> 0.99` at slope 5.
    3. **`slope` is unidentifiable by every metric in F1, which rewrites P1.4.** See the
       amendment to D1 and to P1.4 below. Measured on real frames: slopes 0.5, 1 and 2
       give bit-identical rankings of `P_off` at a per-frame point, changing only the
       spread (range [0.33, 0.74] against [0.06, 0.99]).
    - Design choices where the plan left latitude, all recorded in the module:
      D3's horizon `h = clip(shot_clock, 0, t_h)` scales the projection AND the
      elongation, so with the clock expired the field is purely positional as D3
      requires (3.5% of kept rows); at `|v| >= v_max` the perpendicular axis is floored
      at 1e-3 ft (149 of 5.37M positions, a numerical guard, not a parameter);
      `remove_players` parks the player at 1e6 ft rather than dropping the row, which
      keeps the 5+5 layout and makes the counterfactual exactly monotone cell by cell,
      which is what `denied_k >= 0` needs in P2.2; undetected positions enter as they
      are, since their error is P1.2's job.
- [x] P1.2 Monte Carlo uncertainty `[sonnet]`
  - Does: `sigma_from_pred_error` in `quality.py`; `control_with_uncertainty`;
    `p_off_std` column in the release features. Replaces the heuristic bound of
    `scripts/shot_contest_uncertainty.py` with the perturbation (the script now also
    writes `p_off_mean`, `p_off_std` and whether the difference between consecutive
    contest levels falls within the standard deviation).
  - Accepts: tests: with `predError = 0` the standard deviation is 0; with 200 samples the mean
    is < 0.02 away from the deterministic field on the synthetic; same seed, same
    result. The report prints what fraction of `plus` and `blocked` shots has
    `p_off_std` greater than the distance to the median of the neighboring level.

  - **Result. Gate green: ruff clean, 122 tests, 7 with the `data` marker.** The
    Rayleigh factor was verified independently: `sqrt(2 ln 10)` = 2.146 exactly.
    `control_at_points_with_uncertainty` was added next to `control_at_points`, since
    the release features need a scalar per shot and not a field.
    - **The deliverable, in `reports/shot_contest_neighbour_ambiguity.csv`.** "Neighbouring
      level" was read as every ADJACENT pair, not just one: `plus` has two neighbours and
      `average` carries the sample. Fraction whose `p_off_std` exceeds the gap to the
      neighbour's median: `plus` vs `average` **24.0%** of 549 shots (neighbour median from
      374), `plus` vs `blocked` **22.4%**, `blocked` vs `plus` **23.4%** of 47. Against the
      old heuristic's 26.2% and 43.1%: below it at both levels and about half at `blocked`.
      The figure is stable across both of `plus`'s neighbours, so it is not an artefact of
      the rare tail, and the propagated geometry resolves ambiguity that a raw
      distance-against-error comparison could not see. This is the table the README cites.
    - Two criteria hold to precision rather than to the letter, both recorded in the test
      docstrings. With `predError = 0` the std is 5e-17, not literal 0: the perturbation
      IS bit-exact zero on every draw, and the residual is `np.std` over identical float64
      values, ordinary IEEE754. The "< 0.02 from the deterministic field" holds on the mean
      (0.0017, p99 0.0103) with a 0.0223 maximum. **That tail is the finding, not a
      stretched tolerance**: the std is widest at cells near a sign change of the influence
      surplus, which are the same cells `contestLevel` itself is least sure about.
- [x] P1.3 Release features and rank metrics `[sonnet]`
  - Does: `release_features` (P_off at the shooter's position, mean over a 3 ft
    disk, `epc_share`, Voronoi at the shooter, recomputed `closestDefDist`, plus the
    required `shots` columns), `rank_auc`, `spearman`, `partial_spearman`
    (rank residuals), `permutation_pvalue`.
  - Split in two for scheduling: the four rank metrics were built first because they
    depend on nothing (`validation.py`, 27 tests); `release_features` followed.
  - `epc_share` was pulled forward from P2.1 into `epc.py` because `release_features`
    needs it and duplicating it inline would be worse. `epc_by_zone` stays in P2.1.

  - **Result, with two findings. Gate green: ruff clean, 107 tests, 7 with the `data`
    marker.**
    1. **The matched-shot count is 1,360, not the 1,414 this task asked for, and the
       criterion was measuring the wrong thing.** It meant "no shots lost to a matching
       bug", and zero are: once a release frame is found the shooter is in `off_ids`
       100% of the time across the 10 games. The divergence is structural.
       `scripts/shot_contest_uncertainty.py` matched against the raw tracking stream and
       bypassed D12; `release_features` consumes `GameFrames`, so it can only reach
       shots whose release frame survived D12. Of the 99 shots that do not,
       **93 sit in a chance with `usable == False` and 6 have a null `shotClock`**.
       Verified independently by set membership against the cached `frame_idx`:
       1,459 - 99 = 1,360. Excluding shots the provider itself marks unusable improves
       the sample rather than shrinking it, and D12 is what makes the control field
       well-defined at a frame, so D12 was not weakened to chase the old number.
       **A FOURTH denominator now exists: 1,459 events, 1,433 with valid `location` and
       `region`, 1,414 matched against the raw stream, 1,360 matched against the D12
       cache. F1 and everything after it use 1,360.**
    2. **The Voronoi baseline of P1.5 was degenerate by construction and has been
       replaced (user decision of 2026-09-15).** Voronoi evaluated at the shooter's own
       position is exactly 1.0 for every shot, always, because a player is their own
       nearest player: AUC 0.5 by construction, measured and confirmed. The baseline is
       now `voronoi_disk`, the mean Voronoi occupancy over the same 3 ft disk as
       `p_off_disk`, so the comparison isolates the model instead of the support it is
       measured on. `voronoi_shooter` stays in the table, documented as constant and
       never to be reported, as the visible evidence for the amendment.
       **This raises the bar sharply and honestly.** On three CALIBRATION games (never
       the held-out five), with uncalibrated defaults on a 2 ft grid: `voronoi_disk`
       reaches AUC 0.7535 while `p_off_shooter` is at 0.7213 and `p_off_disk` at 0.7318.
       The baseline currently BEATS the model. Under the old criterion P1.5 would have
       passed trivially against 0.5. P1.4 may close the gap, since nothing is tuned yet,
       but the risk that the pre-registered thresholds fail is now real. D13 governs:
       if they fail it is reported as a finding and F1 replans. The threshold is not
       touched, and this paragraph was written BEFORE running P1.4.
  - Accepts: 1,414 matched shots (same number as the prior script); tests:
    `rank_auc` gives 1.0 with perfect separation and 0.5 ± 0.05 with random labels
    (n = 2,000, fixed seed); `spearman` matches pandas (< 1e-12);
    `partial_spearman(y, x, z)` is 0 (± 0.05) when `y` depends only on `z`.
- [x] P1.4 Calibration on the 5 oldest games `[PLANNER]`
  - Does: `calibrate` and `scripts/calibrate_control.py`: grid `r_near` ∈ {3,4,5,6},
    `r_far` ∈ {8,10,12,14}, `t_h` ∈ {0, 0.3, 0.6} (**48** combinations, `slope` fixed
    at 1 per the D1 amendment) over the release frames of the calibration games;
    objective = AUC(open vs contested) + Spearman(shotQuality) of `P_off` at the
    shooter. The chosen parameters are frozen in `reports/control_params.json`
    with the commit hash.
  - Accepts: `reports/calibration_grid.csv` with 48 rows; the optimum is not on the
    edge of the grid in any dimension (if it is, the grid is extended and rerun);
    commit of the json BEFORE running anything on the validation games. The report
    states that `slope` was not calibrated and why, so the README can say it plainly.
    Note `t_h = 0` is a clean ablation: the model then ignores velocity entirely.

  - **Result. Gate green: ruff clean, 134 tests, 8 with the `data` marker. Frozen in
    `reports/control_params.json` at commit `77253a9`, whose json records `code_commit
    a7891b7` with `working_tree_dirty: false`, so the D11 provenance chain is clean and
    the V row can verify it with `git log`. Calibration games only: 740 shot events, 689
    matched to the D12 cache, 676 with a `shotQuality`.**
    - **The frozen cell: `r_near` 2 ft, `r_far` 8 ft, `t_h` 0 s, `slope` 1.** The planned
      48-cell grid put the optimum on the edge of all three dimensions, so it was extended
      to 108 cells as the plan prescribes; the optimum is then interior in both radii and
      sits on `t_h = 0`, a hard bound rather than an extendable edge.
    - **Three of the four pre-registered thresholds cannot be met, for a structural reason
      that is a finding in its own right.** Objective 0.9611 = AUC 0.7727 + Spearman
      0.1884. Against the thresholds: AUC 0.77 vs 0.80, margin -0.0105 vs +0.03, Spearman
      0.19 vs 0.30. **The provider's own `closestDefDist` reaches AUC 0.7753 on these
      games, verified independently, so the 0.80 bar was set ABOVE the ceiling of the
      variable the label derives from.** The medians say why: `light` 4.07 ft and
      `average` 4.24 ft are indistinguishable by distance and `open` spans 1.25 to 35 ft.
      And `shotQuality` is location-driven (Spearman -0.2877 with `three`, only 0.1215
      with distance) while `P_off` at a point carries no location. Nothing was adjusted:
      no threshold, no objective, no feature. This is what D13 exists to produce.
    - **The fourth criterion holds, and it is the one that tests what the model claims.**
      Partial Spearman of `shotQuality` on `p_off_shooter`: rho 0.1830 (p 0.0005)
      controlling for `closestDefDist`, and **rho 0.1269 (p 0.0010) controlling for
      `closestDefDist`, `three` AND a continuous distance to the hoop**, a harder location
      control than the plan asked for, added and verified independently. Since the frozen
      cell has `t_h = 0` the velocity is switched off, so this information is the
      MULTI-PLAYER GEOMETRY (second defender, teammate spacing), not velocity. By
      contrast the `epc_share` information beyond distance is entirely location (0.1862
      against distance alone, -0.0374 once location is controlled): it says where the shot
      is, not how contested, and must not be sold as contest information.
    - **Velocity as modelled HURTS at release.** `t_h` dominates the whole surface (mean
      objective 0.917 at 0, 0.630 at 0.3, 0.536 at 0.6). Diagnosed cause, consistent with
      the data but not proven: the shooter's own Gaussian is projected forward by `v*t_h`
      while the field is evaluated at their TRACKED point, which is inconsistent for the
      shooter themself; at the 9.3 ft/s median of blocked shots that is about 2 sigma.
      A model defect worth fixing, not a parameter to tune. Recorded in "Open decisions".
    - **Inside the `t_h = 0` slab the surface is flat**: 7 of 108 cells within 0.01 of the
      best, top three within 0.003, well under what 676 shots resolve (AUC s.e. ~0.02).
      The radii are barely identified. Same lesson as `slope` and the Voronoi baseline,
      for the third time in this phase.
    - D11 note for reviewers, disclosed rather than hidden: the P1.3 data test
      `test_release_features_matched_yield_on_the_10_published_games` computes
      `release_features` at DEFAULT parameters on all 10 games to assert the 1,360 count.
      It touches held-out data but computes no metric and no label, so nothing from those
      games could have influenced the frozen parameters. The spirit of D11 holds and the
      test was deliberately left in place.
- [x] P1.5 Validation on the 5 held-out games `[PLANNER]`
  - Does: `scripts/validate_release.py` with the frozen parameters. Writes
    `reports/validation_release.csv` (one row per metric and model: control,
    Voronoi, `closestDefDist`) and prints the table of medians by `contestLevel`.
  - **Run as pre-registered, per the F1 replan above. Report every criterion as it
    falls, pass or fail, and adjust nothing. Three are expected to fail on the
    calibration evidence; reporting them honestly with the ceiling diagnosis IS the
    deliverable, together with the fourth holding out of sample.**
  - Accepts (pre-registered thresholds, D13): AUC(open vs contested) of `P_off` at
    the shooter ≥ 0.80 and ≥ `voronoi_disk` AUC + 0.03, the margin measured with
    `p_off_disk` against `voronoi_disk` so both models sit on identical geometry
    (amended in P1.3 because the original `voronoi_shooter` is constant by
    construction; the 0.80 and the +0.03 are untouched); monotone medians across the 5 levels
    open > light > average > plus > blocked; Spearman with `shotQuality` ≥ 0.30;
    partial Spearman with `shotQuality` controlling for `closestDefDist` > 0 with p < 0.01
    by permutation (2,000 shuffles). The latter is the Methodology argument:
    the field contributes information that the distance to the closest defender does not have
    (velocities and second defender). If a threshold fails: it is written as is in the
    report and work STOPS to replan before F2.

  - **Result. ALL FOUR pre-registered criteria FAIL out of sample, including the partial
    Spearman that held on calibration. Nothing was adjusted: no threshold, no feature, no
    objective. Gate green: ruff clean, 145 tests, 9 with the `data` marker. Held-out
    games only: 719 shot events, 671 matched to the D12 cache, 663 with every field.
    Every figure below was reproduced independently by the team lead.**

    | Criterion | Calibration | Held out | Bar | Verdict |
    |---|---|---|---|---|
    | AUC(open vs contested) of `p_off_shooter` | 0.7727 | 0.7828 | >= 0.80 | FAIL |
    | Margin `p_off_disk` - `voronoi_disk` | -0.0105 | -0.0121 | >= +0.03 | FAIL |
    | Monotone medians across the 5 levels | - | 3 of 4 pairs | 4 of 4 | FAIL |
    | Spearman with `shotQuality` | 0.1884 | 0.1313 | >= 0.30 | FAIL |
    | Partial Spearman given `closestDefDist` | +0.1830 (p 0.0005) | **+0.0129 (p 0.3748)** | rho > 0, p < 0.01 | FAIL |

    - **The ceiling is CONFIRMED out of sample, and it is the project's most solid
      finding.** The provider's own `closestDefDist` alone reaches AUC 0.7970 on the
      held-out games (0.8010 recomputed from the cache; 0.7727 to 0.7753 on calibration).
      The 0.80 bar sits at or above the ceiling of the very variable the label derives
      from, on both halves of the split. Per game, `p_off_shooter`'s AUC is within 0.03 of
      `closestDefDist`'s on all 10 games. On the calibration games the two AUCs agree to
      four decimals (0.7727 and 0.7727): **the model is reproducing the distance, not
      adding to it.**
    - **The partial Spearman did not replicate, and the failure mode matters more than the
      failure.** Per game, `p_off_shooter` given `closestDefDist`: calibration +0.167,
      +0.164, +0.162, +0.124, +0.271, positive in all five; held out +0.179, -0.099,
      -0.052, -0.012, +0.155, at zero or NEGATIVE in three of five. It is not one outlier
      game and it is not small-sample noise: it is a game-dependent effect that pooling
      676 shots dressed up as p = 0.0005. **The F1 claim that `P_off` at a point carries
      multi-player-geometry information about `shotQuality` beyond distance is DEAD and
      must not appear in the README.** The replan's "3 failures plus 1 pass" is now
      4 failures and 0 passes.
    - Criterion 3's inverted pair is `light`/`average`, and the provider's own
      `closestDefDist` has the SAME inversion on these games (light 4.43 ft, average
      4.66 ft): the label is not monotone in its own source variable there, so no model
      built on spatial geometry could have satisfied it.
    - `epc_share` behaves on held-out exactly as on calibration: 0.2961 (p 0.0005) given
      distance, collapsing to 0.0032 (p 0.47) once location is controlled. Its information
      is location. It says WHERE the shot is, never how contested, and selling it as
      contest information would be wrong on both halves of the split.
    - Composition differs between the halves and it is real, not a bug (`hoop_dist` agrees
      with the provider's own `distance` column to 0.01 ft on all 708 located shots):
      held-out shots are farther (median 12.83 ft vs 9.78) and more often threes (39.5% vs
      35.0%). Worth stating whenever the two halves are compared.

### F1 replan, decided by the user on 2026-09-15 after P1.4
D13 fired: three pre-registered thresholds failed, so F1 replans before F2 opens.
**Decision: run P1.5 exactly as pre-registered, change nothing, and report 3 failures
with their diagnosis plus 1 pass out of sample. The primary external validation of the
project moves to the pick coverages of P3.4.** Rationale, in order:
- Nothing needs re-pre-registering, because the criterion that survives was already one
  of the four. Rewriting the thresholds now would pay a credibility cost for nothing.
- The three failures are not a weak model, they are the wrong question: P1.5 asked a
  value-weighted SPACE control model, evaluated at a single point, to recover a
  DISTANCE-derived contest label. That cannot beat the label's own source variable.
- `bhrDefType` and `scrDefType` are labels about how a space is defended, not about how
  many feet away a defender stands, so P3.4 is where this model can actually be tested
  against ground truth. The cost is accepted: the headline validation arrives in week 10
  instead of week 6, and the README leads with three failed thresholds and their cause.
- The alternative of fixing the shooter-projection defect first was considered and
  deferred: it cannot lift the AUC, because the 0.775 ceiling does not depend on the
  model. It stays as a candidate for the reserve weeks.

### P3.4 feasibility pilot, run 2026-09-15 on the calibration games only
**Verdict: the control field does NOT validate against the coverage labels either.** It
adds nothing over a trivial baseline of pick location plus raw inter-player distances, so
P3.4 as designed cannot be the project's external validation. 651 labelled picks with a
cached frame across the 5 calibration games (about 1,300 projected over the 10, above the
plan's 1,000 bar), so sample size is not the constraint. Only three classes actually
occur per label: over/switch/under and show/soft/switch, not the five or six P3.4 assumed.

Leave-one-game-out accuracy, every fold inspected, never a pooled figure:

| Features | `bhrDefType` (majority 0.674) | `scrDefType` (majority 0.373) |
|---|---|---|
| control field only | 0.568, worse than majority, 0 of 5 folds | 0.481, beats majority 5 of 5 |
| location + distances | **0.789**, beats majority 5 of 5 | **0.675**, beats majority 5 of 5 |
| field + location + distances | 0.759, WORSE than without the field | 0.673, identical without it |

The field is not empty: its centroid gaps are significant for `over` and `under`
(p around 0.001) and on `scrDefType` it beats the majority in all five folds. But it is
entirely subsumed by the trivial baseline, which was the question. Same failure mode as
F1: the field reproduces geometry the label already encodes.

Consequence: F2 and F3 are ON HOLD. The project has no validated tactical metric, and
both candidate external validations have now failed for the same reason. The direction
decision is the user's and is pending. `scripts/pilot_pick_signatures.py` and
`reports/pilot_pick_signatures.csv` hold the evidence; nothing was added to the package,
deliberately, so no design is committed to before the direction is settled.

### F1b. Re-validation against a forward-looking label (replan of 2026-09-17)
**Decided by the user on 2026-09-17: change the LABEL, not the model.** The trigger is
Luke Blomm's public thread of 2026-09-15 (x.com/LukeBlomm/status/2099753077096284611),
which builds the same object (P(offense arrives first) x open-shot value, summed over
cells worth >= half a point, every 0.2 s) and validates it differently: leave-one-game-out,
**+0.04 AUC over a spacing and defender-distance baseline, predicting a shot or an open
shot in the next 3 s**. He also states the negative result plainly: it does not predict
points on the possession, and nothing does from one frame.

Why this is a replan and not a threshold rewrite (D13 holds): P1.5 and P3.4 both asked the
field to recover a label DERIVED from the variable it was competing against
(`contestLevel` from `closestDefDist`; coverage type from inter-player distances). Lesson
2 in `tasks/lessons.md` names that failure mode. A future event is not derived from the
present field, so the two CAN disagree: an offense can own valuable space and not shoot.
That is the whole point of the change.

**Everything below is PRE-REGISTERED and must be committed before the script first runs
on the held-out games (D11).**

#### Unit and filter
One row per sampled live frame: every 5th cached frame (0.2 s at 25 fps), D12 filter
already applied by the cache, plus the offense in the frontcourt (at or after the chance's
`frontcourtFrame`). Measured yield at 0.2 s without the frontcourt filter: 10,305 rows on
game 114086 and 12,011 on 178442, so about 105k rows over the 10 games. The frontcourt
filter's cost is reported, not assumed.

#### Labels
- **Primary, `shot_next_3s`**: 1 if a `shots` event with the same `chance_idx` has its
  `startFrame` in (t, t + 75 frames]. Measured base rate 0.176 (114086) and 0.173
  (178442), and identical at 1 s sampling, so it does not depend on the sampling grid.
- **Secondary, `open_shot_next_3s`**: the same with `contestLevel == "open"`. Base rate
  0.036 and 0.030. **Declared secondary and disclosed as partially circular**: `open`
  derives from `closestDefDist`, which sits in the baseline. It is reported because it is
  Luke's headline, never as the project's own evidence.

#### Model features (the field)
- `A_t`: area in ft^2 of grid cells with `P_off(c) * V(c) >= 0.5` points. Luke's headline
  quantity, recomputed here on our own frozen field and our own value surface.
- `epc_share`: already implemented and tested (`epc.py`).
- `p_off_ball`: P_off at the ball holder's position.

#### Baseline (what must be beaten), field-free
Spacing and distances only, plus the two clock variables. The clock is NOT optional:
`A_t` grows as an offense sets up and shots come late, so without it the criterion would
reward the field for proxying the clock.
- convex hull area of the five offensive players
- mean and minimum offense-defense pairwise distance
- distance from the ball to the attacked hoop
- distance from the ball holder to their nearest defender
- `shot_clock` and seconds elapsed inside the chance

#### Estimator and protocol
`HistGradientBoostingClassifier` (scikit-learn, added as an OPTIONAL extra, never a
package dependency: the core stays numpy and pandas). Chosen to match Luke's gradient
boosting so the comparison is like for like, and because a linear model would flatter
whichever block of features happens to be more linear.

Split, preserving D11: control parameters are re-calibrated against the NEW label on the
five CALIBRATION games only and re-frozen in `reports/control_params_forward.json` with a
commit hash, then graded by **leave-one-game-out across the five HELD-OUT games**. The
re-calibration is necessary and is disclosed: the frozen cell has `t_h = 0.0`, so velocity
does not enter the model at all, because P1.4's objective was a static contest AUC. A
forward-looking label is exactly where a projection horizon should matter, and `t_h` sat
on the grid edge. Full 10-game leave-one-game-out is reported as a supplementary row.

**Per-fold values are printed for every criterion. No pooled figure is quoted anywhere
(lesson 1).**

#### Accepts (pre-registered thresholds, D13)
1. **Delta AUC.** AUC(baseline + field) - AUC(baseline) on `shot_next_3s`, leave-one-game-out
   on the five held-out games: mean delta **>= +0.005** AND positive in **5 of the 5 folds**.
   The bar is ours, not Luke's: +0.04 is his number on his implementation, against a
   baseline of spacing and defender distance with no clock in it, and is quoted as external
   context only. Ours is a harder baseline (AUC 0.78 to 0.81 on its own), so it leaves less
   room above it.

   **AMENDED on 2026-09-17, before any held-out game was opened, and this is the whole
   record of it.** The bar first written here was >= +0.02 with 4 of 5 folds. Timing one
   sweep cell produced the calibration figure as a by-product: +0.0068 mean, positive in
   5 of 5, at default parameters. +0.02 was therefore unreachable, and it had been picked
   with no evidence about the magnitude a baseline this strong leaves available. The
   amendment LOWERS the magnitude to +0.005 and RAISES the consistency from 4 of 5 to 5 of
   5, so it is stricter on exactly the failure mode that killed F1 (an effect that changes
   sign between games and that pooling disguised) and realistic on the part that was not.
   D11 is intact: no validation game had been read, and the five calibration cells that
   informed this are named above. After P1.8 opens the held-out games, this bar is frozen
   for good.
2. **The field carries signal alone.** AUC of `A_t` by itself on `shot_next_3s` **>= 0.60
   in every one of the 5 folds**.
3. **It is not the clock.** Criterion 1 is graded against a baseline that ALREADY contains
   `shot_clock` and seconds-into-chance. If dropping the two clock features from the
   baseline is what makes the delta appear, the criterion is failed and reported as such.

If a threshold fails: it is written as is and work STOPS to replan, exactly as in P1.5.
Two failed external validations are already on the record; a third is reported, not hidden.

#### Cost
Measured, not estimated: `control_field` on a 1 ft grid (2,254 cells) runs at 1.3 ms per
frame, so all 10 games at 0.2 s take **2.2 minutes**. A 36-cell calibration sweep on the
five calibration games is about 40 minutes and runs in the background.

- [x] P1.6 Build the forward label and the baseline block `[sonnet]`
- [x] P1.7 Re-calibrate on the calibration games, freeze, commit `[PLANNER]`
- [x] P1.8 Grade on the five held-out games, report every fold `[PLANNER]`

#### P1.8 RESULT: 2 of 3 criteria pass, and the headline one FAILS
Frozen cell `r_near=2.0, r_far=10.0, t_h=0.3`, calibration objective +0.0117 on 5/5 folds.
Held-out rows: 7,562 to 8,245 per game, base rate 0.215 to 0.246. Nothing was adjusted.

| Criterion | Held out | Bar | Verdict |
|---|---|---|---|
| 1. mean delta AUC | **+0.0046**, positive in **4/5** | >= +0.005 and 5/5 | **FAIL** |
| 2. `area_valuable` alone, worst fold | **0.6205** (range 0.6205 to 0.6547) | >= 0.60 in every fold | PASS |
| 3. not the clock | +0.0046 with the clock, +0.0048 without | delta must not need the clock removed | PASS |

Per-fold delta: +0.0081, +0.0095, +0.0016, **-0.0002**, +0.0040. It misses both legs of
criterion 1 narrowly: 0.0004 short on the mean, and game 188630 sits at -0.0002, which is
zero rather than a reversal.

- **Criterion 2 is the real finding and it is clean.** `area_valuable` ALONE separates
  "a shot follows within 3 s" at AUC 0.62 to 0.65, in all five held-out games, with no
  baseline underneath it. The field carries genuine forward information. That is the first
  external result in this project that neither reproduces its own label nor changes sign
  between games.
- **Criterion 3 matters more than it looks.** The delta is +0.0046 with the clock in the
  baseline and +0.0048 without it: identical. The field's contribution is orthogonal to
  the shot clock, which is the trap this criterion existed to catch. It did not fire.
- **Why criterion 1 still fails: the baseline already knows it.** Spacing, matchup
  distances and ball-to-hoop reach AUC 0.77 to 0.81 alone. The field knows something real
  (criterion 2) but almost nothing the baseline does not already know.
- **Shrinkage from calibration to held out is 60%** (+0.0117 to +0.0046). The top five
  sweep cells were within 0.0004 of each other, so taking the argmax over 36 cells on five
  folds fitted the calibration noise. Flagged before the run, confirmed after it.
- Secondary `open_shot_next_3s`: mean **-0.0040**, positive in 2/5. Negative, as the
  disclosed circularity predicted. It is reported and must never be sold as support.
- Cosmetic defect found in the output, disclosed: the criteria table printed the bar as
  "+0.01" because of a `.2f` format on 0.005. The comparison used 0.005 and no verdict
  changes; the format is now `.3f`.

**D13: work STOPS to replan.** The evidence is in `reports/validation_forward.csv` and
`reports/validation_forward_criteria.csv`.

### F5. Tagging up and the defensive transition trade-off (replan of 2026-09-17)
**Decided by the user on 2026-09-17 after P1.8.** The control field stops being the
deliverable and becomes the INSTRUMENT. P1.8's criterion 2 is what licenses that: held
out, `area_valuable` alone separates a shot in the next 3 s at AUC 0.62 to 0.65 in all
five games. It measures something real; it just does not beat a spacing baseline at
predicting shots. So it is pointed at a question where nothing else can be pointed.

**The question.** Tagging up (run at your own defender at the moment of the shot, take the
high side, then retreat already matched) claims to let a team attack the offensive glass
WITHOUT paying for it in transition defense. Coaches are unanimous about it and nobody has
measured it. Does the claim hold on ACB tracking?

**Why this question and not another.** SkillCorner published a crash-rate case study with
the UF Sports Analytics Lab in August 2026 on exactly this kind of data, and wrote that
crossing it with defensive transition would be the interesting next step. They did not do
it. That is the provider's own declared gap, four months before the deadline. Attribution
note for the README: tagging up is generally credited to Tuomas Iisalo, who is a diffuser;
The Athletic traces it to Aaron Fearne and Paul Henare in New Zealand, with Mike Brown
bringing it into the NBA in 2021. Single-source, and it will be cited as such.

Also worth stating up front: the declared PRIMARY goal of tagging up is stopping the
opponent's break, with offensive rebounding as the secondary benefit. Measuring it by
offensive rebounds alone would be measuring the thing it is not for.

#### Measured feasibility, before any design (never estimated)
| Quantity | Measured | Note |
|---|---|---|
| Missed shots with a cached release frame | **796** | the unit for the tag geometry |
| Defensive rebounds | **528** | all 528 carry a `nextChanceId` |
| ... whose next chance is `transition` | **205** | 38.8% |
| Offensive rebounds | 240 | the thin side; not the primary unit |
| Rebounds resolving `shotId` into `shots` | 713 of 768 | |
| Defensive rebounds per game | 44 to 63 | no game is an outlier |
| Next-chance duration after a defensive rebound | median 10.7 s (q10 4.5, q90 20.0) | |

**Lesson 3 check, done before writing a single criterion.** The tag index varies: over the
796 missed shots it takes 0.00 (5), 0.25 (96), 0.50 (286), 0.75 (299), 1.00 (110), mean
0.630, sd 0.224. Its continuous form (mean signed high-side distance) runs -12.23 to
+22.04 ft, mean +2.97, sd 3.36. Per game the mean sits between 0.610 and 0.664.

#### Definitions
- **Tag index**, at the release frame of a missed shot: the share of the four non-shooting
  attackers who sit on the HIGH SIDE of their matched defender, that is, whose projection
  onto the unit vector from that defender toward the basket they must now defend is
  positive. `matchup_with_fallback` supplies the assignment. The continuous form is the
  mean signed distance in feet and is the primary, because the four-step index throws
  away magnitude.
- **Transition cost**, over the opponent's chance that follows the defensive rebound:
  points scored, and the retreating team's `area_valuable` over the first 4 s, which is
  this project's control field pointed at the defending team instead of the attacking one.
- **Crash benefit**: offensive rebound won on that shot.

#### The guard this design exists around
"High side" correlates mechanically with standing deeper, and standing deeper means fewer
offensive rebounds. The probe already shows it: offensive rebound rate falls from 0.333 at
tag index 0.25 to 0.255 at 1.00. **So every criterion is graded against a baseline that
ALREADY contains each attacker's distance to the offensive rim and to their own rim.** If
the tag index only adds "how far back they were standing", it must fail, and the run that
shows that is the deliverable. This is P1.8's criterion 3 applied to a new trap.

The outcome is not circular in the sense of lesson 1: the tag geometry is at the shooting
team's release, the outcome is what the OTHER team does seconds later. The two can
disagree, and the whole point is to find out when.

#### What the open data does NOT carry (confirmed with SkillCorner, 2026-09-17)
A SkillCorner contact told the user directly: **the crash rebounding data is not open.**
Verified against the bundle: none of the 20 event families labels a crash, a box-out or a
retreat. The August 2026 UF case study used a layer we do not have, which is why it could
report 97% agreement with video for its crash detector.

What IS open, and measured here, is everything F5 actually needs:
- `rebounds` is complete, not a sample: 768 events against 853 missed shots (90%; the rest
  are out of bounds, fouled or end of period), 76.8 per game, which is a normal full game.
  It carries `rebounderId`, `defensive`, `frame`, `shotId`, `location` and `nextChanceId`.
- Tracking at 25 fps with `matchups`, which is what the tag geometry is computed from.
- `chances.transition` and `ptsScored`, which is what the outcome is measured on.

**The consequence, stated plainly and it belongs in the README.** There is no provider
ground truth for "was this a tag", so F5 can never claim a validated tag DETECTOR the way
the UF study could. F5 measures a geometric quantity and tests what it relates to. It does
not claim to read intent. P5.1b exists because of this.

This also cuts the other way: the gap cannot be closed by anyone who merely downloads the
open data, because the geometry has to be derived from tracking. That derivation is the
contribution.

#### Tasks
- [x] P5.1 Build the tag features and the transition outcome `[sonnet]`
  - `tagging.py`: `high_side_distance`, `tag_features` (the geometry block plus the depth
    controls), `transition_outcome` (`break_area`, the rebounding team's `area_valuable`
    over the first 4 s of the chance they win, plus the events' own `transition` and
    `ptsScored`), `release_frames_for`. 16 tests, sign convention and shooter exclusion
    pinned against hand-built geometry.
  - Signal on game 114086: `break_area` is 509.3 on chances the events label `transition`
    and 481.3 on the ones they do not.
    **CORRECTION, 2026-09-17: this was overclaimed when first recorded.** It was written up
    as agreement between "two measures that share no input". That is not established. The
    bundle's own `KNOWN_ISSUES.md` says assists and rebounds are tracking-derived judgment
    calls, and nothing documents how `chances.transition` is built. If that flag comes from
    ball speed or court progression, it shares its input with a tracking-derived space
    measure and the agreement is partly circular, which is lesson 2 committed while
    presenting a validity check. Downgraded to a consistency observation until SkillCorner
    says how the flag is built. It is on the list of questions for them.
  - Denominator to carry forward: 36 of 44 defensive rebounds resolve a `break_area` on
    that game; the other 8 have no cached frame for the next chance (D12). Reported, never
    dropped in silence.
- [x] P5.1b Construct validity for the tag index `[PLANNER]`

#### P5.1b RESULT: THE GATE FAILS. The index at the release is not tagging up.
Calibration games only, 217 usable shots (missed, rebounded by the other team, and the
break reached a cached `frontcourtFrame`). Check B expected a NEGATIVE partial correlation
with `match_dist`: more high side at the shot, fewer feet adrift when the break arrives.

| Feature | Pooled raw | Pooled given depth | Negative in |
|---|---|---|---|
| `tag_index` | +0.076 | **-0.000** | 2 of 5 games |
| `high_side_mean` | +0.175 | **+0.115** | 1 of 5 |
| `high_side_min` | +0.043 | +0.002 | 3 of 5 |
| `high_side_max` | +0.231 | **+0.163** | 1 of 5 |

Three of the four run the WRONG WAY and the fourth is zero. Per game the sign flips freely
(`high_side_min` runs -0.412 to +0.347). Check C is worse for the premise: between-team
variance of `tag_index` gives permutation p = 0.337 over 2,000 shuffles, team means from
0.576 to 0.689. **A coached system would separate teams. This does not.**

**The most likely cause is a specification error in P5.1, not a dead concept.** Tagging up
is executed DURING THE SHOT FLIGHT: the attackers run at their defenders after the ball
leaves. Measuring at the release instant captures the offensive shape the possession
finished in, which is the state BEFORE the tag. Two secondary suspects: the provider
matchup has 54 to 62% frame coverage so "your man" leans on the nearest-defender fallback,
and ACB teams may simply not tag much (Iisalo's Paris is EuroLeague).

**This is the first gate this project has failed BEFORE writing a criterion and before
touching a held-out game.** It cost one script instead of a phase. That is the process
working, and it is worth saying so in the README.

- [ ] P5.1c ONE re-specification, declared in advance as the last attempt `[PLANNER]`
  - Does: measure the high side over the SHOT FLIGHT window instead of at the release
    instant, and re-run P5.1b unchanged. Fixing a mis-specified instant is legitimate;
    hunting through windows until one passes is not. **One window, chosen from the
    mechanism (release to the rebound frame, capped), one re-run, and if check B is still
    not negative and consistent, F5's premise is dead and the project replans again.**
  - Denominator to carry: 217 usable shots on five games, so about 430 over ten. Thinner
    than the 796 missed shots the tag geometry alone can be computed on.

#### P5.1c RESULT: check B fails AGAIN. Check C passes hard. The gate is failed.
The re-specification measures the tag as a MOVEMENT: pairs fixed at the release, high side
re-measured at the rebound frame (capped at 2 s), and the difference is what the attacker
actually took during the flight. Median flight window used, 216 usable shots.

**Check B, the pre-declared gate, fails.** Partial correlation with `match_dist` given depth:

| Feature | Pooled | Negative in |
|---|---|---|
| `high_side_gain_mean` | **+0.119** | 2 of 5 (+0.545, +0.191, -0.110, -0.142, +0.307) |
| `high_side_gain_min` | +0.061 | 2 of 5 |
| `tag_index_end` | -0.071 | 3 of 5 |
| `high_side_end_mean` | **+0.188** | 0 of 5 |

Taking high side during the flight does NOT leave you closer to your man when the break
arrives. **F5's premise as written is dead and is not being rescued.** P5.1c was declared
in advance as the only retry and it was spent.

**But check C passes decisively, and this is a real finding.** Between-team variance of
`high_side_gain_mean`: observed 1.087 against a null median of 0.225, **permutation
p = 0.0000** (2,000 shuffles, seed 0). Team means run **1.82 to 4.75 ft**, a 2.6x spread.
The release-instant version gave p = 0.337. So: the POSE at the shot is not coached, the
MOVEMENT during the flight strongly is.

**Competing explanation that must not be buried.** `high_side_end_mean` correlates
POSITIVELY with `match_dist` in 5 of 5 games. Ending further high side means ending further
from your man. That is consistent with the flight gain measuring *who bails out early and
sprints back*, a coached transition-defense policy, rather than *who tags*. Both would show
a team signal. Nothing here separates them yet, and the README cannot claim the tag reading
over the bail-out reading without a test that does.

**Consequence.** Whether the flight gain relates to the TRANSITION OUTCOME (`break_area`,
`next_pts`) is a different question from check B and has not been asked. It would need its
own pre-registration, not an extension of this one.

#### RULED OUT by SkillCorner, 2026-09-17: intent cannot come from tracking
The user's SkillCorner contact, asked directly about the crash events, answered in
substance: crash is not in the open bundle as a dynamic event; with tracking you can see
the points converge, **but you cannot tell whether they converged because the player is
crashing or because they simply drifted there**; their crash events are annotated FROM
VIDEO, sit in an event family not yet released, and will not be released for the
competition. Their advice was explicit: do not go down that road, because it will be asked.

**This is the same finding P5.1c reached from the data, stated from inside.** The competing
reading recorded above (tag versus bail-out, with nothing separating them) is exactly the
ambiguity they describe. It was never an implementation defect and no better definition
fixes it: geometry does not carry intent, and the only thing that resolves it is the video
annotation we do not have and will not get.

**Therefore, and this is a closure and not a pause:**
- Any deliverable that CLAIMS to identify a crash, a tag or a box-out is abandoned. Not
  re-specified, abandoned. A published tag index would invite one question the project
  cannot answer, from a jury, in public.
- `tag_features`, `tag_flight_features` and the construct-validity run STAY IN THE REPO as
  the record of a negative result. They are not deleted and they are not shipped as a
  metric.
- What survives is the half that never claimed intent: `break_area` measures the space the
  breaking team owns, which is observable, and the control field behind it passed P1.8's
  criterion 2 out of sample. Positions at the shot are observable too. **Observable shape
  in, observable space out, and no sentence in between about what anybody meant to do.**
  - Does: check the tag index means what it is claimed to mean, using behaviour rather
    than a label. A high tag index at release must show up later as the attacking team
    arriving at the defensive end sooner and already matched. If it does not, the index is
    measuring something else and F5 stops before its criteria are even written.
  - `tagging.py`: `tag_features` (index, continuous high-side, plus the depth controls),
    `transition_outcome` (next chance, its points, its `transition` flag, retreat
    `area_valuable` over the first 4 s). Tests for both, including the degenerate cases.
- [ ] P5.2 Measure the available magnitudes on the CALIBRATION games only `[PLANNER]`
  - Does: report what effect size is actually on the table, per fold, before any bar is
    written. **This task exists because of this session's mistake:** on 2026-09-17 a
    criterion 1 bar of +0.02 was pre-registered with no evidence about the magnitude a
    strong baseline leaves available, and had to be amended the same day at +0.005, which
    it then missed by 0.0004. A bar chosen blind is not rigour, it is a coin toss with a
    credibility cost. No held-out game is read here.
- [ ] P5.3 Pre-register the bars with the user and COMMIT them `[PLANNER]`
  - D13 and D11 as always: written, committed, then never touched again.
- [ ] P5.4 Grade on the five held-out games, report every fold `[PLANNER]`

#### Status of the phases this replaces
F2 (expected points controlled) and F3 (the possession as a time series) are **DROPPED**,
not paused. They were designed around the control field being the deliverable, and it is
not. `epc_share` and the control field survive inside F5 as instruments. F4
(communication) and V (verification) stand, with their content repointed at F5.

### F6. The approach angle (opened 2026-09-17, on the user's call)
An approach angle is the direction of a velocity vector, so it asserts nothing about what a
player meant to do. That is the whole point: SkillCorner's objection is that tracking cannot
separate a deliberate crash from a drift, and a heading never has to. It is a measurement,
like `closestDefDist`.

Measured `APPROACH_LEAD_FRAMES` = 12 (about 0.5 s) before the ball is won, so the outcome is
not already encoded. 678 of 768 rebounds have that frame cached; 6,780 player rows, of which
5,638 (83.2%) clear `MIN_APPROACH_SPEED` = 2 ft/s and have a usable heading.

Nothing here is fitted, so opening the held-out games costs nothing D11 protects, and both
halves are reported apart throughout.

#### The buy: it REPLICATES, and it is the first thing in this project that does
P(an offensive player wins the rebound), by approach angle to the rim:

| Angle | Calibration | Held out |
|---|---|---|
| 0-30 deg | 0.1090 | 0.1157 |
| 30-60 | 0.1101 | 0.0979 |
| 60-90 | 0.0466 | 0.0478 |
| 90-120 | 0.0267 | 0.0357 |
| 120-180 | 0.0310 | 0.0233 |

Five bands, two halves, same shape and the same magnitudes. A 3.5x drop from rimward to
across. Defenders show the same shape from a higher base (0.199 to 0.037) and also replicate.

**And it is not proximity wearing a new name.** Within the SAME distance band, 0 to 8 ft of
the rim, P(win) runs 0.251, 0.213, 0.136, 0.071, 0.056 across the five angle bands: monotone,
4.5x, at a fixed distance. The depth confound that swallowed P5.1b and P5.1c does not
swallow this.

#### The cost: NOT established, and it must be said so
Bucketing by how many offensive players head within 60 deg of the rim, the offensive rebound
rate rises as expected (0.16, 0.20, 0.35, 0.22, 0.60 on calibration) but the break side does
not carry:
- `break_area` moves 515.6 to 524.0 to 525.3 across n_committed 0 to 3, about 2%, and the
  two halves disagree at n_committed = 0 (515.6 against 490.6).
- `next_pts` moves the OTHER way, 0.919 down to 0.562, contradicting `break_area`.
- n_committed 4 and 5 have 2 to 4 rebounds with a defined `break_area`. Unusable.

**So F6 has a strong, replicated buy side and no established cost side.** The trade-off
figure cannot be drawn honestly yet. Either the cost needs a better measure than a 4 s space
average, or 10 games cannot resolve it and the paper reports the buy plus a null cost.

Evidence: `reports/angle_players.csv`, `angle_rebounds.csv`, `angle_tradeoff.csv`.

#### F6 exploration, 2026-09-17: the rebound zone, the ball, and the descent angle
Three questions asked in order, each one because the previous answer demanded it.

**1. Where does the ball land?** 662 located rebounds: median 4.9 ft from the rim, 58.5%
inside 6 ft, 72.8% inside 8 ft, 92.3% inside 15 ft. Offensive rebounds land slightly closer
(43.8% inside 4 ft against 37.0%). The "semicircle" a SkillCorner contact pointed at is real
and it is small.

**2. Does the heading matter outside it? No.** Lift of a rimward heading (<60 deg) over the
rest, by distance band, calibration then held out: 0-4 ft **+0.172 / +0.322**, 4-8 ft
**+0.145 / +0.053**, 8-12 ft +0.042 / -0.008, 12-16 ft +0.026 / +0.020, 16-22 ft +0.007 /
+0.031, 22+ ft +0.007 / -0.003. **The whole value of the angle lives inside 8 ft.**

  *Correction this forces on the headline curve.* The five-band angle table reported earlier
  mixes distances, and at 22+ ft 511 of 598 players are not rimward because they are already
  retreating, so part of that gradient was composition. The effect survives WITHIN 0-8 ft
  (0.251 to 0.056, monotone, at fixed distance), but the honest headline is not "the angle
  matters", it is **"inside 8 ft the heading decides, outside 8 ft it decides nothing"**.

**3. Is the landing spot predictable, so a heading could aim at it?** Using the ACTUAL spot
is future information and would be circular, so only a prediction from the shot counts.
- Long shots give long rebounds, and it replicates: Spearman +0.336 / +0.367, median radius
  3.4 ft for shots inside 8 ft rising to 6.5 ft on threes.
- **Side bias: we EXTEND Goldsberry, we do not contradict him.** Source checked at the
  primary (Kirk Goldsberry, Grantland, 14 Oct 2014, ~95,000 rebounds, NBA 2013-14, SportVU).
  He claims 56% weak side on missed CORNER THREES, calls that "a slim majority" himself, and
  already reports that long rebounds (20% of all) invert to a strong-side bias. Ours, share
  landing opposite the shooter's side: threes 0.494 / **0.568**, which reproduces his 56%
  out of sample; 16-23 ft 0.475 / 0.477, neutral; **shots inside 16 ft 0.302 / 0.351, a
  pronounced STRONG-side bias.** The new part is the short-shot category, which is not the
  one he attributes the inversion to (he attributes it to long rebounds off violent rim
  collisions). Replicates in both halves.
  **This entry corrected on 2026-09-17**, having first been written up as "the weak-side law
  does not hold here", which the primary source does not support. It came from the research
  report and reached the plan unverified. RULE, second time this happened today: nothing
  from that report enters the README without the primary source being read. Still unchecked
  and flagged: Maheswaran et al. SSAC 2012, Nylon Calculus 2020, and the Fearne/Henare
  attribution for tagging up (single journalistic source, and now out of scope anyway).
- **But the spot itself is not predictable.** sd of the landing radius is 4.88 ft overall and
  4.68 ft within shot-distance quartiles: conditioning buys 4%.

**4. Does the ball's DESCENT ANGLE rescue it? No, and this was the last candidate.**
Recovered on 407 clean descending approaches over the ten games, fitted over the 6 frames
before the closest horizontal approach to the rim, because the tracker smooths straight
through the rim contact itself (the ball visibly hovers near 11 ft for about 0.5 s) and the
impact is not sharply resolved. Median 34.9 deg, q10 16.6, q90 52.6; apex 14.8 ft.
- It is genuinely NEW information: Spearman with shot distance is -0.062 / -0.050.
- It still does not predict the landing radius: given shot distance, **+0.018 on calibration
  and +0.190 held out**. The halves disagree, which is F1's failure mode exactly, so by
  lesson 1 it is not a result.
- Uncertainty test: sd 4.97 -> 4.76 (shot distance) -> **4.64** (shot distance and descent).
  Adding the descent angle buys 0.12 ft, about 2.5%.
- One consistent crumb, recorded but not built on: among shots of 16 ft or more, median
  rebound radius runs flat 5.44/5.92, mid 6.40/6.77, steep 6.98/7.21, monotone in BOTH
  halves. Steeper comes down FARTHER, which is the opposite of the usual coaching line. The
  tracker's smoothing is a live alternative explanation and cannot be ruled out here.

**Design consequence.** The zone is not a fixed 8 ft: it SCALES with the shot, from about
3.5 ft on a close miss to about 6.5 ft on a three. Positioning quality gets judged against
the zone that shot earns, not a constant radius. The ball's own geometry buys nothing
beyond that, and ball z goes back out of scope.

### F2. Expected points controlled and counterfactuals (weeks 7-8)
Closed objective: outputs 1 (creation) and 2 (denial) as tables by mechanism.

- [ ] P2.1 EPC and decomposition by zone `[sonnet]`
  - Does: `epc.py` with `epc_share` and `epc_by_zone`. `epc_share` is already done and
    tested, pulled forward in P1.3; only `epc_by_zone` remains.
  - Accepts: tests: `P_off = 1` gives share 1 and `P_off = 0` gives 0; the zones sum to the
    total (< 1e-9); on a real game the mean share over live frames falls in
    [0.3, 0.7] (printed, sanity).
- [ ] P2.2 Per-player counterfactuals `[PLANNER]`
  - Does: `player_contributions` per D7 (own, created, denied) using
    `remove_players`, `matchup` and `ball_holder`.
  - Accepts: tests: `sum_j own_j == epc_share` (< 1e-9, dominance partitions the
    cells); `denied_k ≥ 0` in every frame of the synthetic (exact monotonicity);
    `created_j` is NaN when j has the ball; total cost ≤ 6 times that of the
    base field (11 fields per frame, measured and printed).
- [ ] P2.3 Creation and denial mechanisms `[sonnet]`
  - Does: `scripts/space_creation.py`. Aggregates `created` and `denied` (5 Hz, 10
    games) by the player's role in the frame (ball handler, screener or cutter per
    the `picks` and `off_ball_screens` windows, otherwise spacer), by the player's
    zone, by shot clock band and by distance to their defender (3 ft
    bins). Outputs: `reports/space_creation_by_role.csv`,
    `reports/space_denial_by_zone.csv`. No player id columns.
  - Accepts: sanity check with ground truth: around off-ball
    screens (`off_ball_screens`), the screener's `created` rises between the
    [-2 s, 0] window and the [0, +2 s] window with p < 0.05 by permutation; the
    ball handler's defender denies more value than the weak-side defenders (mean
    printed). If a sanity check fails, it is reported as a finding with its number.
- [ ] P2.4 `[optional]` Per-player value surface `[PLANNER]`
  - Does: `player_zone_values` with shrinkage toward the league (`k = 50` attempts,
    ids canonicalized with `Dataset.canonical_ids`, summing rows per team); the value
    of a cell becomes the mix of the attackers' values weighted by
    their influence. Repeats the P1.5 metrics with this surface.
  - Accepts: `surface = player` row in `reports/validation_release.csv`; it stays
    in the package only if the Spearman with `shotQuality` improves ≥ 0.02 on the
    held-out games; otherwise it remains a documented function and not the default.

### F3. The possession as a time series (weeks 9-10)
Closed objective: output 3 (where and when a defense breaks) and the second
external validation (pick and roll signatures by coverage).

- [ ] P3.1 Per-chance series `[sonnet]`
  - Does: `chance_series` at 5 Hz and `scripts/chance_series.py`, which caches
    `data/interim/{gid}_series.csv` (chance, frame, seconds to the end,
    `shot_clock`, `epc_share`, share in the paint, in mid-range, in threes, and
    `P_off` at the ball).
  - Accepts: one row per (chance, sampled frame), count equal to that of
    `subsample(frames, 5)`; the 10 games in ≤ 15 min; test on the synthetic that
    the series respects chance boundaries.
- [ ] P3.2 Release-aligned trajectories `[sonnet]`
  - Does: mean `epc_share` over [-4 s, 0] by `contestLevel` with 95% bootstrap
    bands resampling by chance. Writes `reports/release_trajectories.csv`.
  - Accepts: at t = 0 the open minus blocked difference is positive with an interval that
    excludes 0 (expected; if not, it is reported). Table printed with the 5 levels.
- [ ] P3.3 Break point and attribution to actions `[PLANNER]`
  - Does: `break_points`: in each chance ending in a shot, the largest 1 s increase in
    `epc_share` within the last 4 s; it is attributed to the action whose
    window contains it (`picks`, `drives`, `handoffs`, `off_ball_screens`,
    `isolations`, `posts`, with a documented priority order) or to "none".
    Writes `reports/break_points.csv` and the table action x seconds before the shot
    x zone where control rises.
  - Accepts: ≥ 60% of chances with a shot have a break attributed to an action (if
    not, the number is reported as is); test on the synthetic with a hand-built
    rise that is attributed to the pick.
- [ ] P3.4 Pick and roll control signatures `[PLANNER]`
  - Does: `pick_windows` over [-1 s, +2 s] at 5 Hz around `picks.frame`, in
    local coordinates (mirrored in y so that the screen side is positive);
    features per instant: `epc_share`, share in the paint, share in threes on the ball
    side and on the weak side, `P_off` at the ball handler, at the screener and in the
    roll lane (screener-hoop segment). Signature = mean trajectory by
    `bhrDefType` (over, under, switch, ice, blitz) and by `scrDefType` (soft, show,
    switch, blitz, ice) with bootstrap bands. Test: nearest-centroid
    classifier with leave-one-game-out validation against the majority class, and
    permutation of the distance between centroids. Writes `reports/pick_signatures.csv`.
  - Accepts: accuracy ≥ majority + 10 points; p < 0.01 in at least 3 of the 5
    ball handler coverages against the rest; ≥ 1,000 picks with labeled coverage
    and cached frame (printed).

### F4. Communication and package (weeks 11-12)
Closed objective: reproducible public repo, README within limits, video script.

- [ ] P4.1 Figures `[sonnet]`
  - Does: `plotting.py` (`viz` extra with matplotlib) and `scripts/make_figures.py`.
    Figure 1: value-weighted field on a pick and roll frame with the `epc_share`
    series of that chance below it and the uncertainty band. Figure 2: signatures
    by coverage (P3.4) or trajectories by contest level (P3.2), whichever has the
    clearer result. Both generated from files in `reports/`.
  - Accepts: exactly 2 PNGs in `reports/figures/`, ≤ 300 KB each, with the
    data source in the caption; `uv run python scripts/make_figures.py` regenerates them.
- [ ] P4.2 `run_all` and reproducibility `[sonnet]`
  - Does: `scripts/run_all.py` chains cache, value, calibration (only if the frozen
    json does not exist), validation, creation, series, picks and figures; `--quick`
    uses 2 games and a 2 ft grid; writes `reports/summary.json` with every
    number the README cites.
  - Accepts: on a clean clone, `uv sync --all-extras`, `uv run python
    scripts/fetch_data.py`, `uv run python scripts/run_all.py --quick` finishes in
    ≤ 10 min; the full run reproduces `reports/summary.json` with
    differences < 1e-6 relative to the committed one.
- [ ] P4.3 README of at most 1000 words `[PLANNER]`
  - Does: structure by the 5 criteria (what question, why frames and not
    possessions, the model in 5 lines, the external validation with its numbers, the
    three outputs by mechanism, uncertainty as support, limitations: static counterfactual,
    league value and not player value, 10 games; how to reproduce; how to
    contribute). `/humanizer` pass.
  - Accepts: `wc -w README.md` ≤ 1000; ≤ 2 images referenced; every number in the
    README exists in `reports/summary.json`; no player name or id.
- [ ] P4.4 1-minute video script `[sonnet]`
  - Does: `docs/video_script.md` with 6 scenes of 10 s (question, data, model,
    validation, finding, repo) and the voice-over text.
  - Accepts: ≤ 160 spoken words; each scene states which figure or screen is shown.
- [ ] P4.5 Publication `[sonnet]`
  - Does: public package name decided, `pyproject.toml` metadata,
    `CITATION.cff`, MIT LICENSE already exists, `v0.2.0` tag, public repo.
  - Accepts: `uv build` produces wheel and sdist; the clean clone of P4.2 is repeated from
    the public URL.

### V. Verification (week 12; weeks 13-14 in reserve)
- [ ] V. Verification
  - Exact gate commands, in this order and all green:
    ```
    uv sync --all-extras
    uv run ruff check .
    uv run pytest -q                      # without data: `data` tests are skipped
    uv run pytest -q -m data              # with the dataset in data/raw
    uv run python scripts/run_all.py --quick
    uv run python scripts/run_all.py      # full; compares reports/summary.json with the committed one
    wc -w README.md                       # ≤ 1000
    grep -c '!\[' README.md               # ≤ 2
    grep -ci 'player' reports/summary.json   # 0: nothing cited in the README is per player
    git clone <url pública> /tmp/scb && cd /tmp/scb && uv sync --all-extras && uv run pytest -q
    ```
  - Aggregate acceptance criterion: every "Accepts" from P0.1 to P4.5 met or,
    in the threshold cases (P1.5, P2.3, P3.2, P3.3, P3.4), reported as a finding
    with its number and without having touched the threshold; the model parameters are those
    frozen in `reports/control_params.json` and their hash predates any
    run on the validation games (`git log` of the file); no
    deliverable is a player ranking; the prior uncertainty work is
    integrated (P1.2) and not duplicated.
  - Adversarial review: launch the `revisor-adversarial` subagent with the full
    `git diff bf47b73..HEAD` and the list of "Accepts" from this file. It must
    return an empty "Rompe" (breaks) section; every point it returns is fixed and it is
    relaunched until it is empty. Then, `/simplify` on the diff and
    `/verification-before-completion`.

## Out of scope (does not fit in 14 part-time weeks, stated here rather than shoehorned in)
- Full Spearman model with time to intercept and accelerations.
- Learned control models (networks, gradient boosting) or a full-possession
  EPV: no ground truth and no sample.
- Any player ranking or player card, including individual "gravity" as a
  season number: the data is 10 games.
- Season defensive aggregates: there is no tracking for the other 283 games.
- Continuous or shot-type-dependent value surface; constant per zone only
  (and per player with shrinkage if P2.4 makes it in).
- Use of the ball's z, pass flight, rebound modeling.
- Transition-specific analysis: transition frames enter with their `transition`
  label but have no phase of their own.
- Integration into kloppy, DataballPy or similar: mentioned in the README as a
  next step and possible destination of the grant, not done.
- Dashboard, web app or animated video of the field: the author records the video with the
  static figures.

## Open decisions
- Public package name. Working name `scbasket`. Decided in P4.5.
- Solo or pair: the plan assumes solo; if a partner joins, F2 and F3 are parallelized.
- Figure 2 (P4.1): chosen with the numbers in hand, not before.
- The shooter-projection defect found in P1.4: the shooter's own Gaussian is projected
  forward by `v*t_h` while the field is read at their tracked point. Candidate for the
  reserve weeks; it cannot change the AUC ceiling, but it would decide whether velocity
  is usable at all in F2 and F3, where it is not evaluated at the moving player's point.

## Warnings
- The parent repo `data_engineer` has 119 uncommitted deletions: the previous project
  was moved to `feb_platform/`. Do not touch or commit that without asking.
- The project lives at `C:\Users\javie\Desktop\proyectos\skillcorner_basket_data`, not
  under `data_engineer/` (only an empty folder with the same name remains there).
- `data/interim/` and `reports/figures/` are already in `.gitignore`; `reports/*.csv` and
  `reports/summary.json` are versioned because the README cites them.
- `tasks/lessons.md` does not exist; it is created with the user's first correction.
