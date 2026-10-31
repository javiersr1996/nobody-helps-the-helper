# Nobody helps the helper

A defender leaves his man to stop a drive to the basket: does anyone move to cover the man left open? On average, none of the other three defenders moves toward him more than toward any other attacker. The data rule out even a tenth of one defender's rotation toward him.

Coaches teach the next defender to cover that man ("help the helper"); in these ten games, on average, that rotation does not show up as a default, so it is something to check, and the measure runs on any tracking data with matchups (`scbasket`).

Here "nobody" is that average, over ten SkillCorner basketball games with tracked positions, a PySport x SkillCorner Analytics Cup 2.0 entry. Everything is a displacement or a distance; nothing says why anyone moved. The page: [javiersr1996.github.io/nobody-helps-the-helper](https://javiersr1996.github.io/nobody-helps-the-helper/).

## How it is measured

A help: the off-ball defender nearest the ball moves at least 2 ft toward the ball handler within 1.0 s and, at 2.0 s, stands more than 1 ft farther from where his man started than at the start (he did not go back). Only his own movement decides. There are **246 of 618** drives like that. The man left is the attacker he guarded at the start, per the provider's matchups. For each of the other three defenders: how far he moves toward the man left, minus how far he moves toward the comparison attackers, the other off-ball attackers, not his own man. Negative means more toward the others.

The reference: the nearest defender moves less than 1 ft toward the handler (199 drives).

![Figure 1: one drive and how the measure works](reports/figures/wind_figure_1_one_drive.png)

*Figure 1. One drive chosen by a fixed rule: the helper, the man left, and the others' movement toward him.*

## The result

At 1.5 s the mean difference of the other three is **-0.22 ft** (CI **-0.58 to +0.13**): no more toward the man left than toward the others. The interval's top is the bound: the data rule out more than **+0.13 ft**. For scale, the helpers' median step toward the ball is 4.2 ft; had one of the three moved toward the man left that far, the mean would read **+1.35 ft**. The bound is 0.098 of that, about a tenth: a narrow interval, not a wide one. At 1.0 s -0.22 ft (CI -0.46 to +0.01), at 2.0 s -0.18 ft (CI -0.65 to +0.27). When the nearest stays home: -0.03 ft (CI -0.41 to +0.33).

Coaches teach it to one defender, on the pass (`docs/research/`). Two readings were fixed in git before running (`83e8d5d`): the defender nearest the hoop alone reads +0.21 ft (CI -0.33 to +0.73), and the one nearest the man left -1.11 ft (CI -1.78 to -0.47). Neither moves toward him more. A pass starts within 1.5 s in only **28 of 246** drives, too few to measure what follows: the window mostly sees the defence before any pass.

The absence is an average. In 43 % of these drives one of the three moves 4 ft or more toward the man left, and in 39 % toward the comparison attackers on average (34 % and 29 % in the reference).

Afterwards, as context: from the help step to +3 s, after any near step in (263 drives, whether or not he stayed in) the ball reaches the man left in **12.9 %**, against **8.5 %** in the reference (199): the gap holds resampling games, not drives. At the catch he is no more open and shoots no more often.

![Figure 2: who covers the man the helper leaves](reports/figures/wind_figure_2_who_covers.png)

*Figure 2. The three others' movement toward the man left, beside the reference and one rotation's size.*

## How solid it is

Not pre-registered: these numbers were seen before the claim was written. The scope was narrowed to near help after the first near/long results (`bd6033b`, `6bebf5d`, `4b57ff5`). An adversarial review then found that the earlier split between helpers who stay in and who go back read where the man left stood at 2.0 s, the very point the measure aims at; under it the claim was a contrast of **-0.63 ft** (CI -1.25 to -0.03), now withdrawn.

The interval holds 0 under every check: all **48** combinations of the three thresholds (CI tops +0.08 to +0.35), each game left out (means -0.34 to -0.12), games resampled (CI -0.51 to +0.11), no pass in the first 1.5 s (-0.21 ft), every player detected (-0.13 ft).

To our knowledge this has not been measured from tracking, and no public metric we opened (NBA.com, Second Spectrum, BBall Index) measures it; related work infers matchups (Franks et al. 2015; Keshri et al. 2019), detects drive-time defensive gaps (Supola et al. 2023) and links defensive role swaps to open shots (Lucey et al. 2014).

## Limits

- Long help, when the defender farthest from the ball jumps into the drive's path: **7** of 618 drives. Against drives where he stays home, the other three move toward his man +1.44 ft more (CI -0.33 to +2.98): the direction coaches teach, on too few drives.
- Who guards whom is the provider's table, with no ground truth. A hidden Markov model in the manner of Franks et al. (2015) agrees on the man left in **79 %** of these drives (91 % one second earlier); on those the absence holds. Two models agreeing, not validation.
- The rotation after the pass cannot be judged: n = 18 closeouts (a defender running at the receiver) land on a man left.
- The drive frame mirrors by the handler's lateral motion; the provider's direction agrees on 67 % (left) and 72 % (right).

## What ships

`scbasket`, scripts, figures, page, tests. `scripts/check_readme.py` recomputes every number here from its CSV.

## Run it

### From the committed CSVs (no dataset needed)

```bash
uv sync --extra dev
uv run pytest -q
uv run --extra figures python scripts/help_figures.py
uv run python scripts/wind_html.py
npm install -g docx
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
uv run python scripts/near_robustness.py
uv run python scripts/matchup_check.py
uv run python scripts/wind_scenes.py
```

## Licence

MIT, both ways: this repository (`LICENSE`) and SkillCorner's [opendata-basketball](https://github.com/SkillCorner/opendata-basketball), downloaded, not versioned here.
