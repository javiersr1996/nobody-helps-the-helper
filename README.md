# Nobody helps the helper

A defender leaves his man to stop a drive to the basket: does anyone move to cover the man left open? On average, none of the other three defenders moves toward him more than toward any other attacker. The data rule out even a tenth of one defender's rotation toward him.

Coaches teach the next defender to cover that man ("help the helper"); that rotation does not show up as a default, so it is something to check, and the measure runs on any tracking data with matchups (`scbasket`).

Here "nobody" is that average, over ten SkillCorner basketball games, a PySport x SkillCorner Analytics Cup 2.0 entry. Everything is a displacement or a distance; nothing says why anyone moved. The page: [javiersr1996.github.io/nobody-helps-the-helper](https://javiersr1996.github.io/nobody-helps-the-helper/).

## How it is measured

A help: the off-ball defender nearest the ball moves at least 2 ft toward the handler within 1.0 s and, at 2.0 s, stands more than 1 ft farther from where his man started than at the start (he did not go back). There are **246 of 618** drives like that. The man left is the attacker he guarded at the start, per the provider's matchups. For each of the other three defenders: how far he moves toward the man left, minus how far he moves toward the comparison attackers (the placebo: the other off-ball attackers, not his own man). Negative means more toward the others.

The reference: the nearest defender moves less than 1 ft toward the handler (199 drives).

![Figure 1: one drive and how the measure works](reports/figures/wind_figure_1_one_drive.png)

*Figure 1. One drive chosen by a fixed rule: the helper, the man left, and the others' movement toward him.*

## The result

At 1.5 s the mean difference of the other three is **-0.22 ft** (CI **-0.58 to +0.13**): no more toward the man left than toward the others. The interval's top is the bound: the data rule out more than **+0.13 ft**. The helpers' mean step toward the ball is 4.7 ft; had one of the three moved toward the man left as far as his own helper stepped, the mean would read **+1.35 ft**. The bound is 0.098 of that, about a tenth. At 1.0 s -0.22 ft (CI -0.46 to +0.01), at 2.0 s -0.18 ft (CI -0.65 to +0.27).

Coaches teach it to one defender, on the pass. Two readings were fixed in git before running (`83e8d5d`): the defender nearest the hoop alone reads +0.21 ft (CI -0.33 to +0.73), and the one nearest the man left -1.11 ft (CI -1.78 to -0.47). A pass starts within 1.5 s in only **28 of 246** drives, too few to measure what follows.

Big moves cut both ways: in 43 % of drives one of them moves 4 ft or more toward the man left, in 39 % toward the comparison attackers; with the nearest at home, 34 % and 29 %, a similar gap: no excess toward him.

As context, from the help step to +3 s, after any near step in (263 drives, stayed in or not) the ball reaches the man left in **12.9 %**, against **8.5 %** in the reference (199). The gap, 4.4 points, is within noise once drives are resampled (CI -1.5 to +9.8 points). At the catch he is no more open and shoots no more often.

![Figure 2: who covers the man the helper leaves](reports/figures/wind_figure_2_who_covers.png)

*Figure 2. The three others' movement toward the man left, beside the reference and one rotation's size.*

## How solid it is

Not pre-registered: these numbers were seen before the claim was written. The scope was narrowed to near help after the first near/long results (`bd6033b`, `6bebf5d`, `4b57ff5`). An adversarial review then found that the earlier split between helpers who stay in and who go back read where the man left stood at 2.0 s, the point the measure aims at; that claim, a contrast of **-0.63 ft** (CI -1.25 to -0.03), is withdrawn.

The interval holds 0 in all **48** combinations of the three thresholds (CI tops +0.08 to +0.35), each game left out (means -0.34 to -0.12), games resampled (CI -0.51 to +0.11), no pass in the first 1.5 s (-0.21 ft) and every player detected (-0.13 ft). With targets fixed at the start, both groups lie below 0 (committed -0.81 ft, CI -1.15 to -0.48; reference -0.43 ft).

To our knowledge this has not been measured from tracking, and no public metric we opened (NBA.com, Second Spectrum, BBall Index) measures it; related work infers matchups (Franks et al. 2015; Keshri et al. 2019), detects drive-time defensive gaps (Supola et al. 2023) and links defensive role swaps to open shots (Lucey et al. 2014).

## Limits

- Long help, when the defender farthest from the ball jumps into the drive's path: **7** of 618 drives. Against drives where he stays home, the other three move toward his man +1.44 ft more (CI -0.33 to +2.98): the direction coaches teach, on too few drives.
- Who guards whom is the provider's table, with no ground truth. A hidden Markov model in the manner of Franks et al. (2015) agrees on the man left in **79 %** of these drives (91 % one second earlier), the nearest-attacker rule in 84 %: not the best available. On those the absence holds.
- The rotation after the pass cannot be judged: only n = 18 closeouts land on a man left.
- The frame mirrors by the handler's lateral motion; the provider's direction agrees on 67 % (left) and 72 % (right).

## What ships

The entry's modules are `help_kinds`, `wind` and `rotation`; the rest is an earlier rebound study (`docs/bounce/`). `scripts/check_readme.py` recomputes every number here from its CSV.

## Run it

```bash
uv sync --extra dev
uv run pytest -q
```

All commands: [docs/RUN.md](docs/RUN.md).

## Licence

MIT, both ways: this repository (`LICENSE`) and SkillCorner's [opendata-basketball](https://github.com/SkillCorner/opendata-basketball), downloaded, not versioned here. Vendored: three.js (MIT) and the Quaternius mannequin (CC0), see `vendor/`.
