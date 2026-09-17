# Lessons

## Never report a pooled number where a per-unit split is possible
**Why:** F1's surviving criterion was a partial Spearman of 0.183 at p = 0.0005 over 676
shots. Split by game it was five effects, and held out it was 0.013 at p = 0.37, negative
in three. The pooling did not weaken the result, it made it.
**How to apply:** split by the unit you generalise across (the game, never the shot) and
print every value before quoting an average. If the per-unit values straddle the baseline,
the pooled figure is an artefact and must be reported as one.

## A correlation with a variable the label derives from is a reproduction, not a validation
**Why:** twice. The estimated velocity correlated 0.99995 with the provider's `speed`: one
smoothed derivative computed twice. And the control field's AUC matched `closestDefDist`'s
to four decimals against a label derived from that distance, so it recovered it.
**How to apply:** ask what the label is built from, and what would have to be true for the
two numbers to disagree. If the answer is nothing, it is one computation run twice.

## Check a quantity can actually vary before building a criterion on it
**Why:** three times in F1. `slope` was to be fitted over 144 cells against rank metrics,
but `sigmoid(slope * score)` is monotone, so all values ranked identically. Voronoi read at
the shooter's own position is 1.0 always. The calibration surface was flat in both radii.
**How to apply:** ask what makes the number differ across cases. Ranks cannot see a
monotone reparameterisation, and a reference point that is the subject itself is constant.

## Set a threshold from measured evidence, then never move it
**Why:** twice in one day. A +0.02 bar was pre-registered knowing nothing about the
magnitude a strong baseline leaves available; a sweep cell revealed +0.0068 and it was
amended to +0.005 hours later, which then missed by 0.0004. P1.5's 0.80 bar sat above the
ceiling of the variable its own label derived from. Both were guesses dressed as rigour.
**How to apply:** before writing a bar, measure the available effect size on the half of
the split you may look at, and say so. Then it is frozen: a missed criterion is
re-specified only by recording the rewrite (D13), never by moving the number to fit the
result. Older: [[lessons-archive]].
