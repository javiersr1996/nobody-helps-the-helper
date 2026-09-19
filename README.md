# Nobody reads the bounce

**The eight feet where the rebound is decided**, on SkillCorner's open ACB tracking.

**Thesis: the rebound is not read, it is occupied.**

**The ball is barely legible.** Knowing where the shot came from cuts the spread of where it lands
by 2.6% (sd 4.72 to 4.60 ft fitted, 4.84 to 4.70 held out). The ball's own flight cuts more, and a
pre-registered test of it passed held out. Then this repository refuted what it meant. The
quantity was the angle the ball arrives at, arctan(drop / run), and only the denominator predicts:
how far the ball is still carrying sideways when it reaches rim height (rho +0.57) and how far
from the rim it gets there (+0.64). Steepness alone points the other way, +0.17 and +0.22. Hold
those two and the angle keeps **-0.04 and -0.01** of the landing radius, which is nothing. A ball
still heading outward lands outward: geometry, not a read.

**What a player controls is their heading, inside a small zone.** Within 4 ft of the rim, arriving
rimward (under 60 deg) lifts the chance of winning the board by **+0.172** on the five calibration
games and **+0.322** on the five held out. Past 12 ft it is worth nothing.

So rebounding is not a reading contest but an occupation contest, and it replicates on five games
never touched.

## The two figures

![Lift of a rimward heading by distance to the rim](reports/figures/figure_1_lift_by_distance.png)

Both halves on the same axes: the replication is the argument. Intervals are a cluster bootstrap
over the five games of each half, not over rebounds, which are not independent inside a game. Five
clusters is few, so the bands are crude.

![P(win) by approach angle inside a fixed 0-8 ft band](reports/figures/figure_2_pwin_by_angle.png)

The control. Players arriving rimward are also nearer, so figure 1 alone cannot separate heading
from proximity. At a fixed distance, varying only the angle, P(win) falls 4.5x, 0.251 to 0.056
pooled. Split, the held-out half is monotone and calibration ticks up at the end.

## How it was tested

Ten games, split once, never pooled: **calibration** 114243, 114234, 114169, 114099, 114086;
**held out** 178442, 179612, 184439, 188630, 191313. Every parameter and criterion was frozen and
committed before a held-out game was opened (`1e670ea`, `194f5c6`, `cdb3cd5`).

**The shot-scaled zone.** r(d) = 5.40 + 0.180·d feet, d the shot's distance to the rim, fitted by
pinball loss at q = 0.75 on 325 located calibration rebounds. Held out it holds coverage 0.760 and
cuts the drift across shot-distance bands to 0.039, against the constant 8 ft band's 0.168.
Rebounds land a median 4.81 / 4.92 ft from the rim, and the radius scales with the shot: Spearman
+0.336 / +0.367.

**Who wins among the ten present.** Exactly one of ten wins each rebound, so ten independent
probabilities is the wrong structure. A conditional logit over the ten on court, scored half a
second before the ball is won, on distance in zone units, heading, speed, and whether they are
attacking or defending. Coefficients frozen on calibration, not refitted. On 285 graded held-out
rebounds it puts **-1.829** of log probability per rebound on the player who won, against the
distance-only model's -1.912, and the gain holds in **five games of five**.

## The negatives, which are part of the claim

- **This repository overturned a finding of its own, then refuted the overturn.** Earlier work
  called the ball useless (+0.018) from an exploration that left no code. Rebuilt as code the
  sign reversed, -0.353 held out, clearing a bar a shuffled angle clears 0 times in 200.
  An adversarial review then showed the angle is a proxy for carry. The pass stands as it
  fell; the reading of it does not.
- **The model's top-1 accuracy is a pooled artefact.** 0.263 against the nearest-to-the-rim
  rule's 0.246 passed as pre-registered, but holds in three games of five: five rebounds of
  285. The claim rests on the log probability, which holds in all five.
- **One pre-registered condition was retired, not moved.** It asked the scaled zone to carry no
  more mean area than the constant one at equal coverage. Area is quadratic in the radius, so
  no scaled zone could pass it, and it was already failing on the half it was written from.
- **The side bias cannot answer Goldsberry (2014).** His 56% weak side is about missed CORNER
  threes; on those our two halves disagree, 0.414 and 0.519 on 29 and 27 rebounds, so this
  neither reproduces nor contradicts him. Other threes lean weak side, 0.528 / 0.557;
  shots inside 16 ft lean strong, 0.424 / 0.477.
- **Defensive help does not leave you badly placed to rebound.** Four probes, all negative,
  closed in an afternoon. No code ships from it, so no number is quoted here; the detail is
  in `tasks/todo.md`.

## What ships

`scbasket` is the derived layer the open bundle does not carry: `approach_angles` (heading and
speed half a second before the ball is won), `zone_radius` and `rebound_zone_table` (the
shot-scaled zone), `ball_entry_table` (the ball's arrival, with the two legs it is built from) and
`scbasket.conditional` (the contest among the ten). Published as a **definition, never a
detector**: it measures vectors, not intentions, as SkillCorner itself says. Nothing here says a
player crashed, tagged up or boxed out.

## Run it

```bash
uv sync --extra dev
python scripts/fetch_data.py                            # ~730 MB, needs git-lfs
uv run python scripts/build_frame_cache.py
uv run python scripts/rebound_zone.py                   # --fit re-derives the zone
uv run python scripts/rebound_contest.py                # --fit re-derives the betas
uv run python scripts/rebound_flight.py                 # --fit reads calibration only
uv run python scripts/angle_tradeoff.py
uv run --extra figures python scripts/figures.py
uv run pytest                    # 227 pass; 14 more need the dataset, 1 the forward extra
```

Every number above lands in a `reports/*.csv`; the package runs on pandas and numpy alone.

## Data and licence

MIT, both ways: this repository and SkillCorner's
[opendata-basketball](https://github.com/SkillCorner/opendata-basketball), downloaded, not
versioned here. Dependencies are BSD or MIT. Entry for the PySport x SkillCorner Analytics Cup
2.0.