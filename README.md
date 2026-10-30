# Nobody helps the helper

Ten SkillCorner basketball games, tracked positions, one question about drives. Entry for the PySport x SkillCorner Analytics Cup 2.0.

On a drive, one defender sometimes steps toward where the ball is going. Call him the helper. The claim: with a helper, the other three defenders do not move toward the man he leaves any more than they do without one. It is a measured absence against a placebo, not a counter-rotation, and it says nothing about why anyone moved.

The page: [reports/nobody_helps_the_helper.html](reports/nobody_helps_the_helper.html) <!-- C1b: replace with the GitHub Pages URL -->. It opens on one drive in 3D and rises to a top-down view where every measure is drawn. The tracking gives only floor positions; the player bodies and the camera are drawn.

## How it is measured

The helper is the off-ball defender, other than the ball handler's own matchup, who moves at least 4 ft toward where the ball is 1.0 s later. The man left is the attacker that defender marked at the start (the provider's matchups). For each of the other three defenders, the measure is his own displacement projected toward the man left, minus the same displacement projected toward the placebo: the other off-ball attackers who are not his own man. A negative difference means he moved more toward the others.

![Figure 1: one drive and how the measure works](reports/figures/wind_figure_1_one_drive.png)

*Figure 1. One drive chosen by a fixed rule, not by eye: the helper, the man he leaves, and the three others' movement toward him and toward the placebo.*

## How often there is a helper

A helper appears in **45.3 %** of resolved drives (**280 of 618**). Two qualifiers belong to that number. The corner is occupancy: only **1.8 %** of off-ball defenders (**45 of 2,472**) start more than 18 ft from the centre line, so there is little to say about help from there. And above the ball, sinking with the drive already counts as moving toward where it goes: **66 %** of helpers start there, so part of the 45.3 % is the whole defence retreating.

## The man he leaves

At 1.5 s after the drive starts, the man left is open (no defender within 6 ft) in **58.3 %** of helped drives, against **75.9 %** for the comparable man in drives with no helper (**252 and 324** drives). He also started more closely guarded: **41.5 %** open at the start, against **62.3 %**.

## The second help

At 1.5 s the mean paired difference of the other three defenders is **-0.68 ft** (95 % bootstrap CI **-1.08 to -0.27**): they move less toward the man left than toward the placebo. The measure has a bias of its own, since the man left stands on the perimeter. Without a helper it reads **-0.52 ft** (CI **-0.80 to -0.25**), so that series is the reference, not zero. Helped minus unhelped is **-0.16 ft** (CI **-0.65 to +0.32**), which cannot be told from no difference. The typical pair sits near the placebo (median **-0.05 ft**), so the tails carry the mean. The median is negative in **8 of 10** games by drive and **7 of 10** by pair; the per-game cut is published, not used to decide.

In the sensitivity grid (help threshold 3, 4 or 5 ft; horizon 1.0, 1.5 or 2.0 s; with and without a helper) the CI excludes zero in **15 of 18** cells. The three that do not: helped drives at 5 ft and 2.0 s (CI **-1.20 to +0.14**) and the unhelped 3 ft cells at 1.5 s and 2.0 s.

The defender nearest to the man left is the helper himself in **59.9 %** of helped drives. That is almost given, since he marked that man; with no helper, the man's own defender is nearest in **77.8 %**.

![Figure 2: who covers the man the helper leaves](reports/figures/wind_figure_2_who_covers.png)

*Figure 2. The result: where the man left stands at 1.5 s, which defender is nearest, and the three others' movement toward him against the placebo.*

## Limits

- The pass: a first pass follows in **110 of 258** helped drives; **31** of them (**28.2 %**) go to the man left. A random teammate would give 25 %, so at this n it cannot be told apart.
- The rotation after the pass (the X-out) cannot be judged: n = **18** closeouts land on the man left. Nothing is claimed.
- The drive frame mirrors drives by the ball handler's lateral motion. On near-straight drives that sign is close to arbitrary: the provider's own direction label agrees with it on **67 %** of left-labelled and **72 %** of right-labelled drives.
- Ten games. Positions the tracker extrapolates carry more error than detected ones.
- Everything is a displacement or a distance. Nothing here says a defender chose or decided.

## What ships

`scbasket.wind` (the first-second table, the kernel field, the base rate), `scbasket.rotation` (the placebo and the paired difference), the scripts that write every number to `reports/*.csv`, the figures, the page, and the tests. `scripts/check_readme.py` guards this file: at most 1000 words, two images, and every bold number recomputed from its CSV. The earlier rebound entry is archived in `docs/bounce/`.

## Run it

### From the committed CSVs (no dataset needed)

```bash
uv sync --extra dev
uv run pytest -q
uv run --extra figures python scripts/help_figures.py
uv run python scripts/wind_html.py
NODE_PATH="$(npm root -g)" node docs/memoria/build_memoria.js
uv run python scripts/check_readme.py
```

### Full pipeline (needs the dataset)

```bash
uv run python scripts/fetch_data.py          # ~730 MB, needs git-lfs
uv run python scripts/build_frame_cache.py
uv run python scripts/help_wind.py
uv run python scripts/second_help.py
uv run python scripts/wind_scenes.py
```

## Licence

MIT, both ways: this repository (`LICENSE`) and SkillCorner's [opendata-basketball](https://github.com/SkillCorner/opendata-basketball), downloaded, not versioned here.
