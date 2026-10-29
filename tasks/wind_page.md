# The page: storyboard (B3)

Written 2026-10-29 for B4 (builds it, Opus) and B5 (drives it from the console, Sonnet).
Title per D1: **"Nobody helps the helper"**. Every line here is a decision unless it says
"open"; the open points are gathered in section 9. Plan: `tasks/todo.md`, Phase B, D6, D8.

The one sentence the page exists for, and that the judge must have seen before reading
anything: on a drive, one defender steps toward the ball, and nobody moves toward the man
he leaves. The 3D opens the page only because it shows that (the helper stepping, the man
drifting free); the measure is taken from above, where feet on the floor are not distorted.

## 0. The decisions, on one screen

- **Slug:** `reports/nobody_helps_the_helper.html`, built by `scripts/wind_html.py` from
  `scripts/wind_template.html`, served as `index.html` by C1b. B4's task text still says
  `nobody_helps_from_the_corner.html`; this replaces it. Same pattern as
  `reports/nobody_reads_the_bounce.html` and `docs/memoria/memoria_nobody_helps_the_helper.docx`.
- **The clip is the measure's window:** frames 0 to 38 of each scene (0 to 1.52 s,
  `headline_frame` in `wind_scenes.json`), played in slow motion, half speed on average
  (B4b-2: slowest around the help step, faster elsewhere, the profile in 5.3), so the hook
  takes 3.04 s of wall time and freezes on the frame where figures 1 and 2 measure. Frames 39
  to 50 stay in the JSON (the 2.0 s sensitivity and `check_scene` use them); the page never
  draws them.
- **One flight, up.** The broadcast camera is the raised camera behind the basket, the one a
  broadcast cuts to for a replay of a drive, with the drive side on the right. At the freeze
  the camera pitches up into the top-down view in 1.5 s. The yaw never changes, so nothing
  turns on screen and the hoop stays in the bottom part of the frame throughout (B4b-2: the
  broadcast frame may be slid sideways by a lens shift, which the rise takes back to zero;
  2.3). Going back to the broadcast camera is always a cut, as on TV.
- **The plan view is figure 1's layout, exactly:** hoop at the bottom, the drive side on the
  right, the same palette, the same labels, the same crop rule. A judge who has the README
  open sees the same drive drawn the same way, now moving.
- **No measure outside `plan`.** Bars, numbers, the clearance, the strip, the trails and the
  "toward" lines exist only while `state().view === "plan"`. Everything numeric lives in the
  DOM (HTML and SVG) outside the WebGL canvas, in one container `#measure` that carries the
  `hidden` attribute otherwise. Inside the canvas, the only things ever drawn in `broadcast`
  and `rising` are the arena (court, hoops, stands and their crowd), the ten players (bodies,
  sinking into the tokens on the rise) and the ball; the six tags are DOM over the canvas.
- **The ball** is drawn at its measured height in the broadcast view, flat in the plan view,
  and nothing on the page is measured from its height. The limit is stated in words next to
  the hook, with no number (section 2.2 says why).
- **No orbit** (section 6 says why).
- **Reduced motion:** the page opens in `plan` on the frozen frame; every flight is a cut;
  nothing autoplays; the wind is static streamlines.
- **The state machine is B4's as written** (`play, pause, seek(t), next, view(name), state`),
  with additions and no change of meaning: `T`, `flight(p)`, `camera()`, `project(x, y, z)`,
  `unproject(px, py)`, `hookTime(w)`, `field` (section 5.1). `view("rising")` is refused:
  `rising` is only ever passed through.
- **One horizon on the page: 1.5 s** (the frame-38 rows of the CSVs, the figures' horizon).
  The 1.0 and 2.0 s rows go in a `<details>` under the result as the sensitivity.

## 1. What the page is built from

Nothing on the page is typed. `wind_html.py` reads these and injects one JSON payload at
`/*PAYLOAD*/`, as `report_html.py` does. The court geometry comes from `scbasket.court.FIBA`
in the payload, as the old page does (`D.court.geometry`).

| File | What the page takes from it |
|---|---|
| `reports/wind_scenes.json` | `hoop_x`, `fps`, `headline_frame`, `help_ft`, `selection[]` (`game`, `drives`, `all`, `chosen`), and per scene: `game`, `drive_id`, `end_type`, `roles` (`handler`, `handler_def`, `helper`, `left`, `others[3]`, `placebo_targets[3][]`), `xy[51][10][2]`, `ball[51][3]` (x, y, z in feet), `left_clearance[51]`, `to_left[3][51]`, `placebo[3][51]`, `helper_help_move`, `clearance_ft` (`0.0s`, `1.0s`, `1.5s`), `paired_mean_1_5s`, `paired_mean_1_5s_among_helped` (`n_helped`, `median`, `percentile`) |
| `reports/second_help_pairs.csv` | the 252 per-drive means at horizon 38 (helped, mean over `def_slot` of `to_left - placebo`, NaN placebo dropped), recomputed by importing `scripts/wind_scenes.paired_means`; the build refuses if their n, median or any scene's percentile differ from the JSON's `paired_mean_1_5s_among_helped` |
| `reports/second_help_drives.csv` | per scene drive_id: `nearest_who_38`, `nearest_dist_38`, `left_clear_38` (the console check reads these against what the page computes live) |
| `reports/second_help_summary.csv` | rows `horizon == 38`, `helped` True and False: `n_drives`, `n_pairs`, `mean_diff`, `ci_low`, `ci_high`, `median_diff`, `share_diff_positive`, `share_mover_left`, `share_mover_placebo`, `nearest_helper`, `nearest_handler_def`, `nearest_third`, `nearest_dist_median`, `left_open_share`, `left_open0_share`; the `horizon == 25` and `50` rows for the sensitivity details |
| `reports/second_help_contrast.csv` | all three rows: `horizon_s`, `contrast_mean`, `contrast_ci_low`, `contrast_ci_high`, `n_helped`, `n_no_helper` |
| `reports/second_help_contrast_sensitivity.csv` | the nine rows: how many intervals contain 0, how many lie above, which lie below |
| `reports/second_help_by_game.csv` | rows `horizon == 38`, `helped == True`: games with `median_diff < 0` and with `median_diff_pairs < 0`, out of the games present (counted by the build, as the memoria does) |
| `reports/second_help_pass.csv` | row `helped == True`: `n_drives`, `n_first_pass`, `n_to_left`, `share_to_left`, `left_clear_when_got_it`, `n_left_got_it`, `left_clear_when_not`, `n_left_missed` |
| `reports/second_help_closeouts.csv` | row `helped == True`, `receiver_is_left == True`: `n`, `closer_own_share`, `closer_other_share` |
| `reports/help_sensitivity.csv` | row `horizon_s == 1.0`, `help_ft == 4.0`: `n_drives`, `n_resolved`, `share_with_helper`, `helper_rate`, `helper_above_ball`, `helper_along_court_share`, `helper_start_dist`, `helper_hoop_dist0`, `defenders_from_corner_side`, `n_defenders_corner_side`, `helper_from_corner_side`, `helper_rate_corner_side`, `helper_rate_middle`, `left_open_share`, `left_open_share_no_helper`, `left_open0_share`, `left_open0_share_no_helper` |
| `reports/help_base_rate.csv` | `grouping == y_band`, `standardised_by == none`, groups `18-inf` and `0-8`: `n_defenders`, `n_helpers`, `rate`, `rate_low`, `rate_high`; `grouping == bearing_band`, groups `-1 to -0.7` and `0.7 to 1`: `rate`, `rate_low`, `rate_high` |
| `reports/help_vectors.csv` | the row count (2,472 off-ball defenders) |
| `reports/help_table.csv` | `status` counts (ok 618, no_frame 39, no_horizon 3); the provider-direction agreement, computed: share of `provider_direction == "left"` rows with `flip == 1` and of `"right"` rows with `flip == -1` (today 219 of 326 and 209 of 292) |
| `reports/help_field.csv` (B1) | `x`, `y`, `weight`, `mean_dx`, `mean_dy`, `helper_rate`; 957 cells on a 1.5 ft grid, `x` in the attacking frame (hoop at `hoop_x`), `y` across; means NaN under `MIN_WEIGHT` (756 cells carry one), rate NaN under `RATE_MIN_WEIGHT` (478 carry one) |
| `scripts/_record.freeze_commits` | the commit the page was built from, in the footer |

The build's acceptance stays B4's: `rg '[0-9]+\.[0-9]+ ?(%|ft)'` on the template finds nothing
outside the court geometry. The timing constants of section 2.6 carry no unit suffix and are
not data.

## 2. The stage

### 2.1 Coordinates and the court

- Everything is in the **drive frame in feet**, as the JSON: the attacked hoop at
  `(hoop_x, 0)` = (-40.76, 0), the baseline at x = -45.93, the handler's lateral motion
  toward +y. The page never re-derives orientation (the JSON is already mirrored by `flip`,
  per scene; lesson 3's "orientation flips with possession" cannot recur because the page
  has no possession to read).
- **The 3D world is laid out so that the top-down camera reproduces figure 1's layout**
  (hoop at the bottom, +y to the right). In three.js terms: world X = y_drive, world Y = z
  (up), world Z = -x_drive; the plan camera looks down -Y with `up = (0, 0, -1)`, so screen-up
  is +x_drive (up-court) and screen-right is +y_drive. That world is a mirror image of the
  real court; it carries no information here because the drive frame already mirrors half
  the drives by construction (`flip` is -1 in two of the four scenes) and the court is
  symmetric. The storyboard says so; the page need not.
- The court: the FIBA half court from `D.court.geometry` (lines: baseline, sidelines, paint,
  restricted area, free-throw circle, three-point line with its corner lines, the hoop and
  the backboard), drawn on a flat floor, no textures and no images (self-contained). A pale
  hardwood tone for the floor and dark grey lines, so figure 1's token palette (black, grey,
  orange, purple) holds in both views. The floor extends 3 ft past the lines on every side
  (the old page's `MARGIN`), so a player behind the baseline still shows.
- **Crop rule for the plan view**, per scene: across the full width (y from -24.61 - 3 to
  +24.61 + 3); along from the baseline - 3 to `max(hoop_x + 27, max x of any player over
  frames 0..38 + 2)`. That is figure 1's `FIG1_TOP_FT` rule. Over the four scenes the top
  lands at hoop + 27 ft = -13.8 (scene 1), -8.5 (scene 2), -12.8 (scene 3) and -4.4 (scene 4,
  whose handler starts 34 ft above the hoop), read off the JSON's frames 0..38.

### 2.2 Tokens, labels and the ball

- **Players are tokens on their tracked (x, y) in `plan`** (B4b-2 records what B4b changed:
  bodies in `broadcast`). A token is a flat puck, radius 1.15 ft (the old page's `DOT_R`),
  0.3 ft tall so it reads as an object in perspective and as a disc from above. In
  `broadcast` each player is a rigged body 6.5 ft tall (`BODY_H`) standing on the same
  tracked (x, y), with a ring of his colour on the floor; on the rise the bodies sink into the
  tokens. The bundle has no pose, height or facing: stride, facing, stance, the hands on the
  ball, skin tone, hair and kit are drawn, and nothing is measured from them. Skin tone, hair
  colour and hairline are dealt per player of each scene by a seeded generator; the kits carry
  no team's, league's or sponsor's mark.
- **The arena (B4b-2), drawn:** the hardwood lit by one key light over the attacked half,
  the keys and the apron past the lines stained darker so the court stands out of its
  surround, and stands on four sides with a crowd painted by a seeded generator (rows of
  seats, shirts, faces and hair, no signs, no text). The crowd never moves. Everything drawn
  is a pure function of t: two renders of the same t give the same pixels.
- **Palette, figure 1's:** ball handler black; the man he left black; the other three
  attackers grey; helper orange; the three other defenders purple; the ball handler's
  defender pale grey. Teams are therefore black/grey (attack) against orange/purple/pale
  (defence); nothing else distinguishes them.
- **Labels (tags)** are DOM elements over the canvas: "ball handler", "helper", "the man he
  left", and "1", "2", "3" on the three others (figure 1's numbering, by `roles.others`
  order). Labels are not measures and are shown in every view; they are what makes the 3D
  show the finding rather than ten players. Font 12 px CSS minimum at every width; labels
  never scale with the canvas.
- **The tag rule (B4b-2).** B4b placed each tag beside its player's head by a fixed offset
  and slid it aside when it hit another; in the cluster around the ball handler that put
  "ball handler" over a defender and "1" over the helper, which tells a viewer the wrong
  story. Now each tag points at its player:
  - its **anchor** is his head: the tracked (x, y) at the top of a standing body (6.5 ft) in
    `broadcast`, the token's top (1.5 ft) in `plan`, between the two on the rise, projected
    through the current camera;
  - a **leader** (an SVG `<line>` in `#tags`, its `data-tag` the tag's text) runs from the
    tag's box to the anchor; the line's second end (`x2`, `y2`) *is* the anchor;
  - every drawn frame places the six in a fixed order (ball handler, helper, the man he
    left, 1, 2, 3), each at the cheapest of eight directions by six gaps around its anchor
    (its own side first) whose box stays in the canvas, keeps 3 px from every tag already
    placed and from the ball, and covers no player's anchor; failing all, the spot that
    breaks the fewest. A function of the drawn frame alone, so `seek(t)` always gives the
    same tags.
  - **Acceptance**, on every frame 0..38 of the four scenes at 1440 and 390 px, in
    `broadcast` and in `plan`: each anchor is nearer to its own player's projected head
    than to any other player's; no two tag boxes overlap; no tag box covers the ball.
- **The ball** is a sphere of radius 0.39 ft at `ball[f]` = (x, y, z), z clamped at 0, with a
  flat shadow disc on the floor under it at (x, y) whose radius shrinks with z, as the old
  page did; the shadow is what makes the height legible. In the plan view the ball is a dot
  at (x, y) with no height and no shadow. Decision and reasons:
  - Measured height, not flat: a drive reads as a drive by its dribble, and the four scenes
    dribble (z between 1.3 and 4.3 ft over frames 0..38 in scenes 2 to 4); in scene 1 the
    pull-up is already in the air at the freeze (z = 10.06 ft at frame 38), which gives the
    hook a natural last image. A ball sliding on the floor reads as a puck and makes the
    handler look like he is kicking it.
  - Nothing is measured from z: the known defect of this bundle is in the ball's vertical
    second derivatives (a sibling audit of the same bundle fits the apparent gravity about
    15 % low; a smoothed curve whose bounces fall slow), while the heights themselves are
    usable (the rim reads at its height). Drawing a smoothed curve is honest; computing from
    it would not be. Every measure on the page is on (x, y).
  - The limit is stated in words under the stage (section 4.4 has the sentence) with no
    number: no `reports/*.csv` in this repo carries the gravity fit, and lesson 1 forbids
    typing it. If Javier wants the number on the page, it needs a CSV written by a script
    (open point 9.1).

### 2.3 The broadcast camera (`view === "broadcast"`)

A perspective camera raised behind the basket, the end-zone replay camera. B4 placed it at a
fixed point off the axis; B4b put it on the hoop's axis looking down 52° (58° on the square
canvas), fitted to all ten players, which left them about 40 px tall at 1440 px and 17 px at
390 px (Head bone to foot bone), with the top of the frame empty far court. B4b-2, as now:

- **On the hoop's axis, lower.** The camera stays in the vertical plane through the hoop's
  axis (y = 0), its up vector world up (no roll), looking down 32° with a vertical field of
  view of 22° on the desktop canvas (4:3) and 28° with 22° on the phone canvas (1:1). So the
  rise to plan stays a pure pitch.
- **Framed on the story, not on all ten.** Per frame, the page fits the tightest camera (its
  look-at point on the axis and its distance back along the pitch) that holds inside the
  canvas, less a 3 % margin, the **six story players** (ball handler, helper, the man he left,
  the three others: feet and the top of the body, 1 ft either side), **the ball** and **the
  hoop** (its base and its rim), aiming the hoop's base at the bottom 35 % of the canvas
  (smoothing lets it rise to 37 %; B5 asserts 40 %). The other four players may leave the
  frame.
- **A lens shift.** The six can stand 19 ft to one side of the axis and 14 to the other; a
  frame centred on the axis would be as wide as twice the larger. So the frame may slide
  sideways by up to an eighth of the canvas's width (a shifted frustum, `setViewOffset`): the
  camera itself never leaves the axis or turns, the hoop stays within 15 % of the horizontal
  centre, and the rise takes the shift back to zero.
- **The push-in.** Over the clip the distance only ever shrinks (smoothed over 6 frames) and
  starts 10 % further back than the fit, closing to it by the end.
- **Targets, measured from outside** (Head bone to the lower foot bone of each drawn body,
  projected): the median rendered height of the six over frames 0..38 is at least 80 px at
  1440 px and at least 40 px at 390 px, in each of the four scenes. A lower camera makes the
  bodies around the ball handler overlap more; the rings on the floor and the tags' leaders
  are what keep each one findable.
- **B5 asserts the framing rule, not the numbers:** on frames 0..38 of all four scenes, the
  six story players' tracked (x, y) at 0 and at 6.5 ft, the ball and the hoop's base and rim
  project inside the canvas; the hoop's base is in the bottom 40 % and within 15 % of the
  horizontal centre in every view.
- The near hoop's rim and backboard now stand in the upper middle of the frame (a 10 ft rim
  close to a camera this low projects high); the glass and frame are see-through in
  `broadcast`, so a player behind them still reads.
- The drive comes toward the camera and the lateral steps (the helper's step, the man's
  drift) read as left and right on screen, which perspective preserves far better than depth.
- In this view: the arena, the ten players, the six tags, the ball with its shadow. No
  trails, no measuring lines, no numbers, nothing in `#measure`. The caption under the canvas says which drive and which
  camera (section 5.3), the title above it is the h1; neither is a measure.

### 2.4 The flight (`view === "rising"`)

One deterministic function of progress `p` in [0, 1] (eased with smoothstep), used by the
page's own clock and exposed as `flight(p)` so the console check and the video can render it
frame by frame with no clock:

- Pitch only. The camera's position lerps from the broadcast position to a point above the
  crop centre; its look-at lerps to the crop centre on the floor; its up vector lerps from
  world up (0, 1, 0) to (0, 0, -1) and is renormalised, so forward and up stay perpendicular
  and screen-right stays +y_drive the whole way. Nothing rotates on screen; the hoop slides
  down to the bottom edge and the floor flattens. The broadcast frame's lens shift (2.3)
  eases to zero with the same progress, so the picture slides sideways at most an eighth of
  its width on the way up.
- The perspective collapses on the way: the vertical fov narrows from its broadcast value to
  about 2° while the distance grows so that the plan crop keeps the screen size it will have
  at p = 1 (the dolly-zoom to flat). At p = 1 the page swaps to the orthographic camera that
  frames the crop. The swap must be invisible: the hoop's screen position at p = 0.999 and at
  p = 1 differ by under 1 px (B5 asserts it).
- Players and ball are frozen at the current t for the whole flight (B5 asserts
  `state().positions` constant during `rising`). Trails do not exist yet.
- Duration `FLIGHT_S` = 1.5 s. Under reduced motion the flight is a cut (p jumps to 1).

### 2.5 The plan camera (`view === "plan"`)

- An `OrthographicCamera` straight down, framing the crop of 2.1 inside the fixed-aspect
  canvas ("contain": the court is letterboxed, never stretched). Because the camera is
  orthographic and tokens are placed at their (x, y) in feet with no offset, screen pixels are
  an affine image of feet; that is what makes B5's "true top-down" check possible.
- Drawn in the canvas in this view only: the trails from frame 0 to the current t for all ten
  players (polylines on the floor, 0.35 ft wide, the player's colour; a player who ends under
  1.5 ft from his start gets no arrowhead, figure 1's rule), an arrowhead at each trail's head,
  and the "toward" lines on hover (section 4.1).
- The ball: a dot, no height.
- `#measure` is visible, with the panels of sections 4.1 and 4.2 tracking t.

### 2.6 Timing constants (typed in the template; not data)

| Name | Value | What |
|---|---|---|
| `RATE` | 0.5 | clip seconds per wall second: in `plan` always; in `broadcast` the average, so a run takes `T / RATE` (B4b-2) |
| `SLOW` | 0.3 | the broadcast run's rate at the help step, clip seconds per wall second (B4b) |
| `SLOW_W` | 0.26 | half the slow window, clip seconds (B4b) |
| `HOLD_S` | 0.5 | the freeze between the broadcast run's end and the rise |
| `FLIGHT_S` | 1.5 | the rise |
| `FADE_S` | 0.4 | the measures' fade-in on landing (0 under reduced motion) |
| `T` | 1.52 | `headline_frame / fps`, read from the JSON, not typed |

The canvas: desktop 4:3, at most 760 px wide; phone (under 900 px) 1:1 at the full content
width. The aspect never changes within a view or during the flight, so the flight needs no
re-fit. Rendering is on demand (a `requestAnimationFrame` loop only while playing or flying),
and a hidden tab stops the clock, not the clip (the old page's rule).

**Start-up and frame time (B4b-2).** B4b's page drew its first frame 1.4 to 3.2 s after
navigation on this machine's GPU (cold browser), almost all of it the GPU compiling a dozen
shader programs one at a time, synchronously, at the first draw. Targets on this machine
(Intel Arc, ANGLE D3D11, headless Chromium with the GPU): the first stage frame painted
within 1.0 s of navigation start, `state().phase === "playing"` within 1.5 s; while playing at
1440 px, the median frame time at most 17 ms and the 95th percentile at most 20 ms. How: every
program the stage uses is started at once on the GPU's threads (`compileAsync`, with
`KHR_parallel_shader_compile`), the lit arena shares one program and the players another, the
canvases the textures are painted on are drawn in software, and the wind map below the fold is
drawn when it comes near the viewport. The page is under 8 MB.

## 3. The first five seconds (the hook, D8)

Scene 0 is `drive-114243-1-1` (game 114243, a pull-up; helper 5.46 ft; the man he left 1.79 ft
from the nearest defender at 0 s, 2.65 at 1.0 s, 9.29 at 1.5 s; all from `wind_scenes.json`),
the same drive as figure 1. With motion allowed, on load and with no click (wall time from the
hook's first frame, which is drawn within 1.0 s of navigation, see 2.6; before it the page
reads `broadcast`, `idle`, t = 0; B4b-2 times, from the profile of 5.3):

| Wall time | `view` | `phase` | t | What is on screen |
|---|---|---|---|---|
| 0.0 s | broadcast | playing | 0 | the court from behind the basket; the handler 24 ft up-court with the ball; the helper and the man he left side by side near the paint, tagged; the caption "Drive 1 of 4 · game 114243 · pull-up · the broadcast camera, slow motion (half speed on average)" |
| 0 to 2.12 s | broadcast | playing | 0 to 1.0 | the handler drives at the camera, dribbling; the helper steps left toward his path (5.46 ft by t = 1.0), slowest (0.3×) from t = 0.18 to 0.70 s; the man he left starts drifting left |
| 2.12 to 3.04 s | broadcast | playing | 1.0 to 1.52 | the man he left keeps drifting, nobody follows him; in scene 1 the pull-up leaves the hand and is at 10 ft at the freeze |
| 3.04 s | broadcast | ended | 1.52 | the freeze: the telestrator moment |
| 3.54 s | rising | ended | 1.52 | the camera pitches up; the floor flattens; the hoop slides to the bottom |
| 5.04 s | plan | ended | 1.52 | the top-down view, figure 1's layout; trails and `#measure` fade in over 0.4 s |
| 5.44 s | plan | ended | 1.52 | rest: the ten trails, the bars of 4.1 and the clearance of 4.2 at 1.5 s, the caption "Drive 1 of 4 · game 114243 · pull-up · from above: the measure" |

By three seconds a cold viewer has seen one defender step out and the man he was guarding
drift free. That is the hook's whole job; every number waits for the plan view. The page
then rests: the reader scrubs, replays, flips the camera or goes to the next drive (section 6).
The text above the stage changes with the view (DOM, asserted by B5): in `broadcast` the
subtitle reads "One defender steps toward the ball. Watch the man he leaves."; in `plan`,
"From above, the measure: how far each of the other three moves toward him."

## 4. The sections, all top-down

Each section states its claim, what it draws, the columns it reads, the limit that travels
next to the claim (lesson 2) and what the reader can touch. Wording obeys the entry's ruling:
"helper", "the man he left", "covers", "nearest" name measured vectors and distances, never
decisions, and no sentence says where help comes from (the corner claim was withdrawn: it
measured occupancy).

### 4.1 The drive, measured: the three others beside their placebo

The stage of section 2 and its `#measure` panel, side by side at or above 900 px, stacked
under 900 px. This section is figure 1 live.

- **Heading:** "Does anyone else move toward the man the helper left?" (figure 1's title;
  figure 2 and section 4.2 answer it).
- **Lead, injected:** "One drive, chosen by rule. The helper moves {helper_help_move} ft toward
  where the ball is at 1.0 s; at 1.5 s the man he was guarding is {clearance_ft["1.5s"]} ft
  from the nearest defender. For each of the three other defenders: how far he moves toward
  that man, against how far toward the other attackers off the ball."
- **On the court (canvas, plan only):** the ten trails to t, labels as figure 1. On hover or tap
  of other defender i (his token, his trail, or his row in the panel): his displacement from
  frame 0 to t as a purple arrow, a dashed black line from his start to where the man left is
  at t, and dashed grey lines from his start to each of his `placebo_targets[i]` at t. That is
  the line each "toward" is measured along, the lever `tasks/todo.md` left for figure 1 if it
  still did not read; on the page it costs one hover. Hover highlights, it does not change t.
- **The panel (SVG, `#measure`), tracking t:** three rows, one per other defender, numbered as on
  the court; in each a black bar `to_left[i][f]` and a grey bar `placebo[i][f]`, labelled with
  their values to one decimal, a zero line, and a right-hand column "black - grey" with each
  difference and their mean. Values at a fractional t are linearly interpolated between frames
  exactly as positions are. Caption under the bars, figure 1's definition: "Feet each moves
  toward a target: his own movement along the line from his start to where the target is then
  (negative: away). The whole defence sinks with a drive, so the test is the difference against
  the other attackers off the ball, his own man excepted (the placebo)."
- **The strip (SVG, static):** the 252 per-drive means at 1.5 s from `second_help_pairs.csv`
  (recomputed by the build, section 1), as a histogram with a "drives" axis, this drive's mean
  marked in purple with "this drive {paired_mean_1_5s}, percentile {percentile}" and the median
  dashed with "median {median}" (both from `paired_mean_1_5s_among_helped`). Labelled "at
  1.5 s", because the strip does not follow t while the bars do; the scrubber's 1.5 s tick is
  where they agree.
- **Columns read:** `to_left`, `placebo`, `roles`, `helper_help_move`, `clearance_ft`,
  `paired_mean_1_5s`, `paired_mean_1_5s_among_helped` from the JSON; the distribution from
  `second_help_pairs.csv` (`drive_id`, `helped`, `horizon`, `def_slot`, `to_left`, `placebo`).
- **Limit, next to it:** "Chosen by rule, not by look: the first drive with a helper, in each of
  four games, with all ten players detected for its whole window (in this game
  {selection.all} of {selection.drives} drives pass every condition). This drive sits at
  percentile {percentile} of {n_helped} drives with a helper: clearer than most, not typical.
  Section 4.2 has the result over all of them."
- **Touch:** play/pause, the scrubber (frames 0 to 38, shown in seconds, ticks at 1.0 s "the
  helper is named here" and 1.5 s "the measure"), next drive, the camera toggle, the hover.

### 4.2 The man he left: who covers him, and the result over all drives

Same stage, the second part of `#measure` (below the bars at every width). This section is
figure 2 live, with the live clearance of this drive on top.

- **Heading:** "Nobody else moves toward the man the helper left" (figure 2's title).
- **Live tile, tracking t:** "{left_clearance[f]} ft to the nearest defender, who is
  {nearest role}", the role computed in the page from `positions` at t as the nearest of the
  five defenders to `roles.left`, named "the helper", "the ball handler's defender" or "a third
  defender" by `roles`. At frame 38 it must equal `second_help_drives.csv` `nearest_who_38`
  for the scene's `drive_id` and the distance `nearest_dist_38` within 0.01 ft (B5 asserts;
  the JSON's `clearance_ft["1.5s"]` is the same number). Beside it, the drive's three quoted
  clearances "0 s {0.0s} · 1.0 s {1.0s} · 1.5 s {1.5s}" from `clearance_ft`.
- **Over all drives with a helper, at 1.5 s** (`second_help_summary.csv`, `horizon == 38`):
  - who is nearest to him: "the helper {nearest_helper} (with no helper, his own defender:
    {nearest_helper of helped == False}); the ball handler's defender {nearest_handler_def}
    ({no-helper value}); a third defender {nearest_third} ({no-helper value}); median distance
    {nearest_dist_median} ft ({no-helper value} ft)"; "{n_drives} of {n_drives at 25} helped
    drives; the rest end sooner".
  - open, with the base rate in the same sentence: "nobody within 6 ft: {left_open_share} of
    the men left at 1.5 s, against {left_open_share, helped False} of the comparable man in
    drives with no helper; at 0 s {left_open0_share} against {left_open0_share, helped False}.
    The help gives room to a man who started more closely guarded; it does not make an open
    man where there was none." The 6 comes from `scbasket.wind.OPEN_FT` in the payload.
  - the result, as figure 2's lower panel in SVG: for 1.0 / 1.5 / 2.0 s, the mean over drives
    of "toward him minus toward the placebo" with its 95 % CI, helped drives in black and
    drives with no helper in grey, and a column with `median_diff` and `share_diff_positive`.
    Under it the sentence that is the entry's claim: "Helped minus no helper, mean (95 % CI):
    1.0 s {contrast_mean} ({ci_low} to {ci_high}); 1.5 s ...; 2.0 s .... Every interval
    contains 0: with a helper the three others move toward him no more than when there is no
    helper." (`second_help_contrast.csv`). Then the robustness, counted by the build:
    "Helper threshold 3, 4, 5 ft by three horizons: {k} of {9} intervals contain 0, {m} lie
    above it" and, if any lies below, which (`second_help_contrast_sensitivity.csv`; today
    8 of 9, none above, 3 ft at 1.0 s below). Per game: "{games negative by drive} of {games}
    games negative by drive median, {by pairs} by pair median" (`second_help_by_game.csv`).
  - the pass, one sentence with its n (D7): "A first pass follows in {n_first_pass} of
    {n_drives} helped drives and goes to him in {n_to_left} ({share_to_left}; one of four is
    25 %). When it reached him he had {left_clear_when_got_it} ft of room (n = {n_left_got_it}),
    when it did not, {left_clear_when_not} (n = {n_left_missed})." (`second_help_pass.csv`,
    `helped == True`).
- **A `<details>` "the same at 1.0 and 2.0 s":** the `horizon == 25` and `50` rows of the summary
  and the contrast, as a table.
- **Limits, next to the claims:** "That the helper is nearest is near-persistence: he was
  guarding that man at the start. A nearest defender is a distance, not a decision." "The CI
  tops ({ci_high} at 1.0 / 1.5 / 2.0 s) are the most extra rotation the data cannot rule out:
  an absence with that bound, not a proven zero." "The grey series is negative too: the metric
  has its own geometric bias (the man left is on the perimeter), so the baseline is the grey
  series, not 0."
- **Touch:** the scrubber moves the live tile; hovering a horizon row in the SVG shows its
  numbers; nothing else.

### 4.3 Where the defence goes in the first second: the league wind, as context

A separate block below the stage: a 2D canvas (not WebGL) in the same plan layout (hoop at
the bottom, +y right, the same projection function), with the wind map's content moving.

- **Heading:** "Where the defence goes in the first second of a drive" (the wind map's title).
  Subtitle: "Context, over all {n_resolved} drives. The whole defence sinks with a drive; the
  help is a step on top of that."
- **Drawn:** particles advected by `help_field.csv`: about 500 particles seeded uniformly over
  the cells whose `mean_dx` is not NaN, each moving at the bilinear interpolation of
  (`mean_dx`, `mean_dy`) in feet per second (the field is feet in 1.0 s, so the wind blows at
  its measured speed; the maximum is 8.9 ft/s), with a short fading tail, a lifetime of 2 to
  3 s, and death on leaving the masked region. Under them, the helper rate per defender as the
  map's orange fill where `helper_rate` is not NaN, with the map's colour key (0 to 30 %) and
  "white: too few for a rate". The court lines over the fill, under the particles. The
  animation runs only while the block is in the viewport (IntersectionObserver) and, under
  reduced motion, is replaced by about 80 streamlines integrated once from grid seeds.
- **Strip, injected** (`help_sensitivity.csv` row 1.0 s / 4 ft unless said otherwise):
  "{n_resolved} of {n_drives} drives, ten ACB games, the first 1 s of each. Helper: the
  defender who moves most toward where the ball will be, 4 ft or more
  ({share_with_helper} of drives; of the {count of help_vectors rows} defenders off the ball,
  {helper_rate} are one). Of the helpers, {helper_above_ball} start farther from the hoop line
  than where the ball goes, where a plain sink counts as movement toward it; a defender is the
  helper {rate, bearing -1 to -0.7} of the time ({rate_low} to {rate_high}) when that spot
  lies mostly toward the hoop from him and {rate, bearing 0.7 to 1} ({low} to {high}) when it
  lies mostly away (`help_base_rate.csv`). The corner: {n_defenders, 18-inf} defenders
  ({defender_share}) start more than 18 ft from the middle and {n_helpers} helpers come from
  there; each is the helper {rate} of the time ({rate_low} to {rate_high}), against
  {rate, 0-8} in the middle: the corner is empty, and too few stand there to say whether it
  helps less."
- **Limit, next to it:** "This says where defenders stand and where they go; it does not say
  where help comes from. Part of the {share_with_helper} is the defence's common retreat seen
  from above the ball; the helper keeps its definition and the qualifier travels with the
  number."
- **Touch:** hovering a cell shows its `mean_dx`, `mean_dy`, `weight` and `helper_rate` in a
  tooltip; nothing else. The particles are decoration over a measured field, not a measure of
  any drive, which is why this block never needs the state machine.

### 4.4 The limits

A plain list, each item with its source, gathering the ones already placed and the ones that
belong to no section:

1. Ten games; {n_drives} drives, {n_resolved} resolved; {no_frame} start outside the frame
   cache and {no_horizon} have no 1 s horizon (`help_table.csv` `status`).
2. The drive frame mirrors each drive so the handler's lateral motion goes to +y; on
   near-straight drives that mirror is close to arbitrary. The provider's `direction` agrees
   with it on {left share} of left-labelled and {right share} of right-labelled drives,
   computed from `help_table.csv` (`provider_direction`, `flip`): two in three, no validation.
   Nothing on this page depends on which side is which.
3. Players stand on their tracked (x, y): bodies in the broadcast view, tokens from above.
   The bundle has no bodies, no pose, no facing; stride, facing and hands are drawn from (x, y)
   and the ball, skin, hair and kits (and the crowd) are decoration, and nothing is measured
   from any of them (B4b-2 records B4b's wording on the page, plus hair, skin and crowd).
   The four drives shown have all ten players detected on every frame of their window (the
   rule); the tables behind the numbers include extrapolated positions
   (`help_vectors.csv` `detected0`, `detected1`: the build reports the share detected at both
   ends).
4. The ball is drawn at the height the provider gives. That height is a smoothed curve: a
   sibling audit of this bundle found its bounces fall slower than gravity allows. Nothing on
   this page is measured from it; every measure is on the floor.
5. The absence is measured against a placebo and against drives with no helper, not as a
   rotation away from him: the typical pair sits on the placebo (`median_diff`), the mean is
   pulled by the tails, and the contrast's CI tops bound what the data cannot rule out.
6. {share_with_helper} of drives have a helper, and {helper_above_ball} of helpers start above
   the ball, where sinking counts as help (`help_sensitivity.csv`).
7. The corner is empty (1.8 % of defenders), not measurably stingy ({rate} with a 95 % interval
   of {rate_low} to {rate_high} on {n_defenders} defenders; `help_base_rate.csv`). The page
   claims nothing about where help comes from.
8. What follows the pass (the X-out) cannot be judged here: {n} provider closeouts land on the
   man left in helped drives; the closer is the helper {closer_own_share} of the time
   (`second_help_closeouts.csv`). One closeout moves the share by {100 / n} points.
9. Intent is never claimed: "helper", "the man he left", "covers" and "nearest" name measured
   vectors and distances.
10. A 3D viewer of this bundle already exists. The 3D here is the hook; the finding is in the
    top-down view, where "toward" can be judged by eye.

### 4.5 Footer

What ships (`scbasket.wind`, `scbasket.rotation`, `scripts/help_wind.py`,
`scripts/second_help.py`, `scripts/wind_scenes.py`, `scripts/wind_html.py`,
`scripts/drive_wind_page.py`, the `reports/*.csv` and the JSON), "run it" (the commands C3
actually runs), licence, the commit from `_record.freeze_commits`, and the data credit
(SkillCorner open ACB tracking).

## 5. The state machine

### 5.1 API (`window.wind`)

B4's five calls keep their names and meanings; the rest are additions.

| Member | Behaviour |
|---|---|
| `play()` | from `idle` or `ended` with t < T: `playing` from t. With t >= T: t = 0, then `playing`. While `playing` or `rising`: no-op, returns `false`. |
| `pause()` | `playing` -> `idle`, t kept. Cancels a pending rise (the hold timer). In `rising`: `false`. |
| `seek(t)` | t in clip seconds, clamped to [0, T]; draws the frame (positions, trails, panel values linearly interpolated between frames); `phase` -> `idle`; cancels a pending rise. In `rising`: `false`. |
| `next()` | scene = (scene + 1) mod 4. In `broadcast`: t = 0 and `playing` (the hook again; under reduced motion t = 0 drawn, `idle`). In `plan`: t = T, `idle`, trails and every number swap in a cut. In `rising`: `false`. |
| `view(name)` | `"plan"` from `broadcast`: pause if playing, then `rising` for `FLIGHT_S` (a cut under reduced motion), then `plan` with `#measure` fading in. `"broadcast"` from `plan`: a cut, `#measure` hidden before the frame is drawn, t kept, `idle` if it was playing. Same view: no-op, `true`. `"rising"` or anything else: `false`. |
| `state()` | `{scene, t, phase: "idle" \| "playing" \| "ended", view: "broadcast" \| "rising" \| "plan", positions: {players: [[x, y] x 10], ball: [x, y, z]}}`, drive-frame feet, interpolated at fractional t. |
| `T` | the clip length in seconds, `headline_frame / fps` (1.52). |
| `flight(p)` | addition. Sets the camera at progress p in [0, 1] of the flight with no clock, cancelling any running flight: p = 0 is the broadcast camera and `view` reads `"broadcast"`; 0 < p < 1 reads `"rising"`; p = 1 is the orthographic camera and reads `"plan"` (with `#measure` shown, no fade). For B5 and the video. |
| `camera()` | addition. `{type: "perspective" \| "orthographic", projection: number[16], view: number[16], width, height}` (column-major as three.js, CSS pixels), so a test can project the JSON's feet to pixels on its own. |
| `project(x, y, z)` | addition. Drive-frame feet to canvas CSS pixels through the current camera. |
| `unproject(px, py)` | addition. The drive-frame (x, y) on the floor plane under a canvas pixel through the current camera (exact in `plan`; a ray-plane intersection otherwise). |
| `hookTime(w)` | addition (B4b). The clip time a broadcast run of the current scene reaches w wall seconds after it starts, following the slow-motion profile of 5.3: 0 at 0, `T` at `T / RATE` and after. For the video, which follows the slow motion frame by frame with `seek`. |
| `field` | addition. `{running(), start(), stop(), sample(x, y) -> [dx, dy]}` for the wind block of 4.3. |

Playback is driven by `requestAnimationFrame` at `RATE` (in `broadcast`, by the profile of
5.3, `RATE` on average); a hidden tab pauses the clock and
resumes without a jump in t. The pending rise after a broadcast run is a timer of `HOLD_S`;
any of `pause`, `seek`, `next`, `view` cancels it (the old page's `waiting` timer class of
defect, closed by rule).

### 5.2 States and transitions

| Event | From | To |
|---|---|---|
| load, motion allowed | - | scene 0, `broadcast`, t = 0, `idle` while the stage's shaders compile (nothing drawn yet); then, at its first drawn frame, `playing` from t = 0 (B4b-2: `playing` means the clip is running, so it waits for the first frame). Any call before that cancels the start. |
| load, reduced motion | - | scene 0, `plan`, t = T, `idle`, `#measure` shown |
| playback reaches T in `broadcast` | `playing` | `ended`; after `HOLD_S`: `rising` for `FLIGHT_S` (cut if reduced); then `plan`, `#measure` fades in over `FADE_S` (0 if reduced). Every broadcast run that reaches T rises: the measure is always taken from above. |
| playback reaches T in `plan` | `playing` | `ended`, stays |
| `play()` | `idle`/`ended`, t < T | `playing` from t, same view |
| `play()` | `idle`/`ended`, t >= T | t = 0, `playing`, same view |
| `pause()` | `playing` | `idle`, t kept |
| `seek(t)` | not `rising` | t, `idle` |
| `next()` | `broadcast` | next scene, t = 0, `playing` (reduced: `idle`) |
| `next()` | `plan` | next scene, t = T, `idle`, cut |
| `view("plan")` | `broadcast` | (`idle` if playing) -> `rising` -> `plan` |
| `view("broadcast")` | `plan` | `broadcast`, cut, `#measure` hidden, t kept |
| any call | `rising` | ignored, returns `false`, nothing changes |
| `flight(p)` | any | the camera at p; `view` by p as in 5.1 |

The "replay the hook" button in `plan` is `view("broadcast")` then `play()`; no extra call.

### 5.3 Buttons and captions, by state (DOM text B5 asserts)

| `view` | `phase`, t | `#play` label | `#view-broadcast` / `#view-plan` | `#next` | `#stage-caption` |
|---|---|---|---|---|---|
| broadcast | playing | "Pause" | broadcast pressed | "Next drive" | "Drive {i} of 4 · game {game} · {end type} · the broadcast camera, slow motion (half speed on average)" |
| broadcast | idle, t < T | "Play" | broadcast pressed | enabled | same |
| broadcast | ended, or idle at t = T | "Replay" | broadcast pressed | enabled | same |
| rising | ended or idle | disabled | both disabled | disabled | "rising to the top-down view" |
| plan | playing | "Pause" | plan pressed | enabled | "Drive {i} of 4 · game {game} · {end type} · from above: the measure" |
| plan | idle, t < T | "Play" | plan pressed | enabled | same |
| plan | ended, or idle at t = T | "Replay" | plan pressed | enabled | same |

`aria-pressed` on the two view buttons, `disabled` on all three during `rising`, the scrubber
`<input type="range" id="scrub" min="0" max="38" step="1">` with `aria-valuetext` "t = {t} s"
and disabled during `rising`. `{end type}` maps `pullup`, `kickout`, `shotNearBasket`,
`interiorPass` to "pull-up", "kickout", "shot near the basket", "interior pass" (a word table,
not data).

**The slow-motion profile (B4b; written down by B4b-2).** B4b's caption said "half speed",
but the broadcast run is not played at one speed: it slows around the help step and runs
faster elsewhere, so "half speed" is only the average and the caption now says so. On the
wall clock only (`seek(t)` never sees it), for each scene:

- the **centre** c is the clip time of the first frame at which the helper has covered half
  the length of his path from frame 0 to frame 25 (`horizon_frames`, where he is named);
- the rate, in clip seconds per wall second, is r(t) = out - (out - 0.3) · cos²(π/2 · (t - c)
  / 0.26) for |t - c| < 0.26 s (`SLOW`, `SLOW_W`), and `out` elsewhere;
- `out` is the rate that makes the run take exactly T / `RATE` = 3.04 s.

Read from `wind_scenes.json` with this rule (and from the page, which agrees):

| Scene | c | slow window (clip s) | `out` | the run |
|---|---|---|---|---|
| 0 | 0.44 s | 0.18 to 0.70 | 0.563× | 3.04 s |
| 1 | 0.48 s | 0.22 to 0.74 | 0.563× | 3.04 s |
| 2 | 0.40 s | 0.14 to 0.66 | 0.563× | 3.04 s |
| 3 | 0.56 s | 0.30 to 0.82 | 0.563× | 3.04 s |

So the hook plays at 0.3× at the help step, 0.563× before and after it, and half speed on
average; in scene 0 it reaches t = 0.5 s at 1.14 s of wall time and t = 1.0 s at 2.12 s.
`#watch` says it in words: "in slow motion, slowest as the helper steps".

### 5.4 What B5 asserts (its own list, plus the invariants this storyboard adds)

B5's list stands: `seek(1.0)` puts the helper within 0.1 ft of `xy[25][roles.helper]`;
`play()` then wait reads `ended` with frame 38 drawn; pause then play resumes at the same t;
`next()` changes scene and numbers; the page opens in `broadcast` and reaches `plan` with no
click (wait `T / RATE + HOLD_S + FLIGHT_S + FADE_S` + margin, about 6 s); in `plan` the
top-down is true; no measure is visible while the view is not `plan`; reduced motion makes
the flight a cut; every injected number equals the CSV value it names; 390 and 1440 px. Added:

- **True top-down:** `camera().type === "orthographic"` in `plan`; and, independently of the
  page's bookkeeping, a screenshot's colour centroids of the two uniquely coloured tokens
  (orange helper, black man left; the handler is also black, so take the man left as the black
  blob nearest the page's own `project` of `roles.left`, or colour the man left's puck a
  distinct near-black in a `?test` mode if that is cleaner) map through `unproject` to within
  0.1 ft of `xy[25]` at `seek(1.0)`. Two true points plus an orthographic camera pin the affine
  map.
- **The flight:** `flight(0.5)` reads `rising`, `#measure` hidden, positions equal to those at
  `flight(0)`; the hoop's screen position at `flight(0.999)` and `flight(1)` differ by under
  1 px; at `flight(1)` `#measure` is visible and `camera().type` is orthographic.
- **No measure outside plan:** `#measure` carries `hidden` whenever `state().view !== "plan"`,
  and a pixel scan of the canvas in `broadcast` finds none of the trail colours.
- **Framing** (B4b-2's rule, 2.3): over the four scenes and frames 0..38, in `broadcast`, the
  six story players' tracked (x, y) at 0 and at 6.5 ft, the ball and the hoop's base and rim
  project inside the canvas (the other four players are not asserted); the hoop's base is in
  the bottom 40 % and within 15 % of the horizontal centre in every view.
- **Tags** (B4b-2, 2.2): on frames 0..38 of the four scenes at 1440 and 390 px, in
  `broadcast` and in `plan`, each tag's anchor (its leader's `x2`, `y2`) is nearer to its own
  player's head, projected by the check itself through `camera()` from the JSON's (x, y) at
  6.5 ft (1.5 ft in `plan`), than to any other player's; no two tag boxes overlap; no tag box
  covers the ball, projected the same way.
- **The broadcast clock** (B4b-2, 5.3): the natural run's clip time, sampled against the
  wall clock, follows the written profile: the observed rate is below `out` around the
  centre and near `out` well outside the window, and t reaches T at T / `RATE` after the first
  frame. The check computes c and `out` itself from the JSON and the rule; it never reads
  `hookTime`, which would test the page against itself. In `plan` the clip plays at `RATE`.
- **Start-up and frame time** (B4b-2, 2.6), on the GPU only: the first draw on the stage's
  WebGL canvas and the animation frame after it within 1.0 s of navigation start; `playing`
  within 1.5 s; 3 s of frames while playing at 1440 px, median at most 17 ms and 95th
  percentile at most 20 ms. Before the first frame the natural run reads `broadcast`, `idle`,
  t = 0. If the browser's WebGL renderer is a software one (SwiftShader), these rows and the
  clock's fail as "software renderer: timing not measurable", not pass.
- **The numbers at the headline frame:** at `seek(T)` the three black and grey bars equal
  `to_left[i][38]` and `placebo[i][38]` and the matching `second_help_pairs.csv` rows
  (`drive_id`, `horizon == 38`, `def_slot`) within 0.01 ft; the live tile equals
  `nearest_who_38` and `nearest_dist_38`; the strip's n, median and percentile equal the
  JSON's `paired_mean_1_5s_among_helped`.
- **Labels:** the table of 5.3 holds in every reachable state, including after `next()` and
  after a pause during the hold.
- **Rising ignores calls:** during `rising`, `play`, `pause`, `seek`, `next` return `false`
  and `state()` is unchanged.
- **Reduced motion** (Playwright `reducedMotion: "reduce"`): load reads `plan`, `idle`, t = T,
  `#measure` shown; `view("broadcast")` then `view("plan")` never reads `rising`; `next()` in
  `broadcast` does not autoplay; the wind block draws streamlines and `field.running()` is
  `false`. The streamlines are static: the flow canvas's bytes are identical 0.7 s apart.
  B4b-2: on a GPU-accelerated 2D canvas the *first* `getImageData` unpremultiplies on the GPU
  and every later one on the CPU, so the first read differs from all the others by one level
  in the colour of the anti-aliased edge pixels (530 of them, alpha identical) with nothing
  drawn in between; the check takes one read first and discards it, then compares two reads
  0.7 s apart byte for byte.
- **Mutations (lesson 4), B5's three:** a typed number in the template, a broken `seek`, a
  perspective camera left on in `plan`. The storyboard adds a fourth worth one run: a trail
  drawn in `broadcast` (the pixel scan must catch it).

## 6. What the reader can touch, and what not

- Play/pause, the scrubber, "Next drive", the camera toggle (Broadcast / Top-down), "Replay"
  (in plan: the hook again), hover or tap on the three other defenders (the "toward" lines),
  hover on the wind's cells. Keyboard: the buttons are buttons, the scrubber is a native range.
- **No orbit.** Three reasons, in order: orbiting lets the reader tilt into exactly the view
  where feet on the floor mislead, which D8 exists to avoid; a 3D viewer of this bundle
  already exists, so free exploration earns nothing on Originality and risks Communication;
  and `OrbitControls` is an addon with touch handlers that fight page scroll at 390 px and a
  camera state no console check can enumerate. Two cameras, both testable.
- **390 px:** the canvas 1:1 at the content width (358 px inside 16 px gutters; the court's
  49 ft across 358 px is 7.3 px per foot, a token 8 px across, labels 12 px CSS positioned in
  the DOM so they never shrink); controls under the canvas; the two `#measure` panels stacked
  under the controls, bars full width; the wind canvas full width with the field grid's
  aspect; no horizontal scroll, body text 16 px. **1440 px:** canvas 760 px wide at 4:3 with
  the `#measure` panels beside it; everything else in one column of at most 66 ch.
- **No WebGL:** the stage shows one sentence naming the finding and pointing to the README's
  figures; `#measure` and everything below (4.2's result, the wind on canvas 2D, the limits)
  still work, because none of it needs the GPU. B5 fails loudly if WebGL is not live in the
  browser it drives, as its task says.

## 7. The video (phase D) reuses the hook

`scripts/wind_video.py` drives the built page in Playwright at 1920 x 1080 with motion
allowed, captures frame by frame and never waits on the page's clock:

- the hook: `view("broadcast")`, then `seek(hookTime(k / 25))` for k = 0..76 (B4b-2: the
  slow motion of 5.3, frame by frame, 77 frames over the run's 3.04 s); the freeze, 12 frames
  of frame 38; the
  rise, `flight(p)` for p = k / 37, k = 0..37, 38 frames; the landing, 10 frames at
  `flight(1)` (the fade is skipped; `flight(1)` shows the measures at once); then plan frames
  as D1's script needs them (`seek(t)` for the bars, `next()` for another drive). About 5.5 s
  of the 60, the same pixels as the page from the same `wind_scenes.json`.
- the canvas is captured as an element at a device pixel ratio that makes it 1900 px wide
  (the page's layout does not change); the panels of 4.1 and 4.2 are captured the same way
  and composed on the slide. `wind_video.py` owns the composition; the page owns nothing
  video-specific beyond `flight(p)` and deterministic `seek`.

## 8. Build notes for B4 that follow from the above

- three.js vendored at one pinned release in `vendor/three/` with its MIT `LICENSE`, inlined
  by the build at `/*THREE*/`. The ESM build is the only one shipped since the UMD builds were
  dropped; inline either `three.module.min.js` with its trailing `export {...};` removed by the
  build (and the result parsed once in the build to prove it loads) or `three.cjs` behind a
  two-line `module.exports` shim in a classic script. No addons, no `OrbitControls`, no CDN,
  no fonts fetched (system stack).
- Two renderers only: WebGL for the stage, canvas 2D for the wind; the measures are SVG and
  HTML. No second renderer for the stage.
- Positions and panel values at fractional t are linear interpolations between adjacent
  frames; the scrubber steps by frame; B5 and the video use frame-aligned t.
- The payload carries the whole JSON (57 KB) and the per-drive means (252 floats), the
  field (957 rows), the summary rows and the scalars; the build asserts every scalar it injects
  is finite and refuses on the guards of section 1.

## 9. Open points (for Javier or the main session; the defaults apply until answered)

1. **The gravity number.** The ball limit (4.4 item 4) carries no number because no CSV in this
   repo holds the sibling audit's fit; the task text says 28.1 against 32.17 ft/s^2 and the
   memory note says 27.46 (shots) and 27.60 (bounces), which disagree. Default: words only.
   To put a number on the page, a script must write it to `reports/` first.
2. **The open share's horizon.** The page quotes the 1.5 s pair (58.3 % against 75.9 %,
   `second_help_summary.csv` horizon 38) because everything on the page is at 1.5 s; the
   README plan (C2) quotes the 1.0 s pair (58.5 % against 72.6 %, `help_sensitivity.csv`).
   Both are CSV values at their stated horizon. Default: the page keeps 1.5 s and shows the
   1.0 s pair in the `<details>`; C2 should say "at 1.0 s" explicitly or move to 1.5 s.
3. **The mirrored 3D world** (2.1): chosen so the plan view equals figure 1's layout. The
   alternative, a right-handed world, puts the drive side on the left in the plan view or the
   hoop at the top, either one a mirror of the README figure. Default: as written.
4. **`help_field.csv` columns** are read from B1's in-flight diff and the file on disk today
   (`x, y, weight, mean_dx, mean_dy, helper_rate`); if B1 renames them, section 1 follows.
5. **The hook's speed** (`RATE` 0.5) and `HOLD_S` 0.5 are the first guess that makes the hook
   land at about three seconds; B4 may tune them by eye within 0.4 to 0.6 and 0.3 to 0.8 and
   record the values; B5 reads them off `window.wind` constants rather than hard-coding waits.
6. **The release number of three.js** is B4's to pin (the newest at build time); the storyboard
   only fixes that it is pinned, MIT, vendored and inlined.
