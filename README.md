# Nobody helps the helper

Ten SkillCorner basketball games, tracked positions, one question about drives. Entry for the PySport x SkillCorner Analytics Cup 2.0.

On a drive, the defender nearest the ball sometimes steps toward the handler and does not go back. Call him the helper. The claim: nobody covers the man he leaves. It is a measured absence against a placebo and against drives where the nearest defender stays home, not a counter-rotation, and it says nothing about why anyone moved. It is about near help only; long help is a stated limit.

The page: [javiersr1996.github.io/nobody-helps-the-helper](https://javiersr1996.github.io/nobody-helps-the-helper/). It opens on one drive in 3D and rises to a top-down view where every measure is drawn. The tracking gives only floor positions; the player bodies and the camera are drawn.

## How it is measured

A near help that commits: the off-ball defender nearest the ball moves at least 2 ft toward the handler within 1.0 s and, at 2.0 s, is not back with his man. There are **159 of 618** resolved drives like that. The man left is the attacker that defender marked at the start (the provider's matchups). For each of the other three defenders, the measure is his own displacement projected toward the man left, minus the same displacement projected toward the placebo: the other off-ball attackers who are not his own man. A negative difference means he moved more toward the others.

The reference is the drives where the nearest defender moves less than 1 ft toward the handler (**199** drives): he stays home. In the drive of figure 1, chosen by a fixed rule, the man left is **8.7 ft** from the nearest defender at 1.5 s.

![Figure 1: one drive and how the measure works](reports/figures/wind_figure_1_one_drive.png)

*Figure 1. One drive chosen by a fixed rule, not by eye: the helper, the man he leaves, and the three others' movement toward him and toward the placebo.*

## The result

At 1.5 s after a near help that commits, the mean paired difference of the other three defenders is **-0.66 ft** (CI **-1.14 to -0.20**). When the nearest stays home it reads **-0.03 ft** (CI **-0.41 to +0.33**): the reference sits on the placebo. Committed minus reference is **-0.63 ft** (CI **-1.25 to -0.03**). The whole interval is below zero, only just at its top, and the reading fixed before the run was absence. At 1.0 s the contrast is **-0.40 ft** (CI **-0.80 to -0.01**) and at 2.0 s **-0.89 ft** (CI **-1.67 to -0.13**).

The defender nearest to the man left at 1.5 s is the helper in **51 %** of these drives (**70 %** when the nearest stays home, since he marked that man), the ball handler's defender in **31 %**, and one of the other three in **18 %** (**15 %** in the reference).

![Figure 2: who covers the man the helper leaves](reports/figures/wind_figure_2_who_covers.png)

*Figure 2. The result: where the man left stands at 1.5 s, which defender is nearest, and the three others' movement toward him against the placebo, for committed near help and for the reference.*

## The pooled helper

The earlier definition counted every helper: the off-ball defender who moves at least 4 ft toward where the ball is 1.0 s later. He appears in **45.3 %** of resolved drives (**280 of 618**). Against drives with no such helper, the same contrast at 1.5 s is **-0.16 ft** (CI **-0.65 to +0.32**): also no extra rotation, but an interval that holds zero, so the narrower claim above is the one that carries. Two qualifiers belong to the 45.3 %. The corner is occupancy: only **1.8 %** of off-ball defenders (**45 of 2,472**) start more than 18 ft from the centre line. And above the ball, sinking with the drive already counts as moving toward where it goes: **66 %** of helpers start there.

## Limits

- Long help: when the defender farthest from the ball jumps into the drive's path, the claim is neither extended nor narrowed. Of the 618 resolved drives, **7** qualify, too few to test. Coaches teach a rotation behind long help; none was looked for.
- Who guards whom is the provider's table, unvalidated: the open data has no video. Its handler defender is the nearest defender in **519 of 595** assigned drives. Consistency, not validation.
- The pooled helper's pass: a first pass follows in **110 of 258** helped drives; **31** of them (**28.2 %**) go to the man left. A random teammate would give 25 %, so at this n it cannot be told apart.
- The rotation after the pass (the X-out) cannot be judged: n = **18** closeouts land on the man left. Nothing is claimed.
- The drive frame mirrors drives by the ball handler's lateral motion. On near-straight drives that sign is close to arbitrary: the provider's own direction label agrees with it on **67 %** of left-labelled and **72 %** of right-labelled drives.
- Ten games. Positions the tracker extrapolates carry more error than detected ones.
- Everything is a displacement or a distance. Nothing here says a defender chose or decided.

## What ships

`scbasket.help_kinds` (near and long help), `scbasket.wind` (the first-second table, the kernel field, the base rate), `scbasket.rotation` (the placebo and the paired difference), the scripts that write every number to `reports/*.csv`, the figures, the page, and the tests. `scripts/check_readme.py` guards this file: at most 1000 words, two images, and every bold number recomputed from its CSV. The earlier rebound entry is archived in `docs/bounce/`.

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
uv run python scripts/help_kinds.py
uv run python scripts/matchup_check.py
uv run python scripts/wind_scenes.py
```

## Licence

MIT, both ways: this repository (`LICENSE`) and SkillCorner's [opendata-basketball](https://github.com/SkillCorner/opendata-basketball), downloaded, not versioned here.
