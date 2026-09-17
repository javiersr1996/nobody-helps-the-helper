# Analytics Cup 2.0: shot-value-weighted space control (scbasket)

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
