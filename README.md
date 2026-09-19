# Nobody reads the bounce

**The eight feet where the rebound is decided**, on SkillCorner's open broadcast tracking of
the Liga ACB 2025-26.

**Thesis: the rebound is not read, it is occupied.** The two halves hold each other up.

**The ball is barely legible.** Knowing where the shot came from cuts the spread of where it
lands by 4% (sd 4.97 to 4.76 ft). The angle the ball descends at, recovered here from
broadcast tracking on 407 clean approaches (median 34.9 deg), adds 2.5% more and is nearly
independent of shot distance (-0.062 / -0.050), so it is genuinely new information. It still
fails to predict the landing radius out of sample.

**So the only thing a player controls is their own heading, inside a small zone.** Within 4 ft
of the rim, arriving rimward (under 60 deg) lifts the chance of winning the board by **+0.172**
on the five calibration games and **+0.322** on the five held out. Past 12 ft it is worth nothing.

If the bounce were legible, rebounding would be a reading contest. It is not, so it is an
occupation contest, and it replicates on five games never touched.

## The two figures

![Lift of a rimward heading by distance to the rim](reports/figures/figure_1_lift_by_distance.png)

Both halves on the same axes, because the replication is the argument. Intervals are a cluster
bootstrap over the five games of each half, not over rebounds, which are not independent inside
a game. Five clusters is few, so the bands are crude. Every point carries its count.

![P(win) by approach angle inside a fixed 0-8 ft band](reports/figures/figure_2_pwin_by_angle.png)

The control. Players arriving rimward are also nearer, so figure 1 alone cannot separate the
heading from proximity. Holding distance fixed and varying only the angle, P(win) falls 4.5x,
from 0.251 to 0.056 pooled. Split, the held-out half is monotone and calibration ticks up in
the last band; the figure says so on its face.

## How it was tested

Ten games, split once and never pooled: **calibration** 114243, 114234, 114169, 114099, 114086;
**held out** 178442, 179612, 184439, 188630, 191313. Every parameter and every pass/fail
criterion was frozen and committed before a held-out game was opened (`1e670ea`, `194f5c6`).
A criterion that failed is reported as it fell.

**The shot-scaled zone.** r(d) = 5.40 + 0.180·d feet, d the shot's distance to the rim, fitted
by pinball loss at q = 0.75 on 325 located calibration rebounds. Held out it holds coverage
0.760 and cuts the drift across shot-distance bands to 0.039, against the constant 8 ft band's
0.168: it does not cover more ground, it covers it more evenly. Rebounds land a median 4.81 ft
(calibration) and 4.93 ft (held out) from the rim, and the radius scales with the shot,
Spearman +0.336 / +0.367.

**Who wins among the ten present.** Exactly one of ten players wins each rebound, so ten
independent probabilities is the wrong structure. A conditional logit over the ten on court,
scored half a second before the ball is won, on distance in units of the zone its shot earned,
how rimward the heading is, speed, and team. Coefficients frozen
on calibration and not refitted. On 285 graded held-out rebounds it puts **-1.829** of log
probability per rebound on the player who actually won, against the distance-only model's
-1.912, and the gain holds in **five games of five**.

## The negatives, which are part of the claim

- **The descent angle fails.** +0.018 on calibration against +0.190 held out: the halves
  disagree, so it is not a result.
- **The model's top-1 accuracy is a pooled artefact.** 0.263 against the nearest-to-the-rim
  rule's 0.246 passed as pre-registered, but it holds in three games of five and amounts to
  five rebounds of 285. The claim rests on the log probability, which holds in all five.
- **One pre-registered condition was retired, not moved.** It asked the scaled zone to carry no
  more mean area than the constant one at matched coverage. Area is quadratic in the radius, so
  no scaled zone could pass it, and it was already failing on the half it was written from. The
  failure stays in the record, and the verdict reads "passes the two conditions that can
  discriminate", never "passed".
- **Defensive help does not leave you badly placed to rebound.** Four probes, all negative: a
  help compresses both teams toward the rim almost equally (-0.371 against -0.342 in zone
  units), and 4.4 of 5 defenders are already between their man and the rim whether anyone
  helped or not.
- **Side bias reproduces Goldsberry (2014) and extends him.** Share landing opposite the
  shooter's side: threes 0.494 / **0.568**, reproducing his 56% out of sample. Inside 16 ft it
  inverts into a pronounced **strong**-side bias, 0.302 / 0.351, which is the new part.

## What ships

`scbasket` is the derived layer the open bundle does not carry: rebound approach kinematics
from tracking. `approach_angles` (heading and speed half a second before the ball is won),
`zone_radius` and `rebound_zone_table` (the shot-scaled zone), and `scbasket.conditional` (the
contest among the ten). It is published as a **definition, never a detector**. It measures
vectors, not intentions: tracking shows players converging but not whether they crashed or
drifted, which is SkillCorner's own position. Nothing here says a player
crashed, tagged up or boxed out.

## Run it

```bash
uv sync --extra dev
python scripts/fetch_data.py                            # ~730 MB, needs git-lfs
uv run python scripts/build_frame_cache.py
uv run python scripts/rebound_zone.py                   # --fit re-derives the frozen zone
uv run python scripts/rebound_contest.py                # --fit re-derives the frozen betas
uv run python scripts/angle_tradeoff.py
uv run --extra figures python scripts/figures.py
uv run pytest                                           # 232 tests, 15 more with the data
```

Every number above lands in a `reports/*.csv`. The package runs on pandas and numpy alone;
matplotlib and scikit-learn are optional extras.

## Data and licence

MIT, both ways: this repository and SkillCorner's
[opendata-basketball](https://github.com/SkillCorner/opendata-basketball), which is downloaded
rather than versioned here. Dependencies are BSD or MIT.
Entry for the PySport x SkillCorner Analytics Cup 2.0.
