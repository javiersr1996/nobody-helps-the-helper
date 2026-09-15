# Lessons

## Never report a pooled number where a per-unit split is possible
**Why:** F1's one surviving criterion was a partial Spearman of 0.183 at p = 0.0005 over
676 shots. Split by game it was five separate effects, and on the held-out five it was
0.013 at p = 0.37, negative in three. The pooling did not weaken the result, it made it.
**How to apply:** split by the unit you will generalise across (the game, never the shot)
and print every value before quoting an average. If the per-unit values straddle the
baseline, the pooled figure is an artefact and must be reported as one.

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

## When a criterion is missed, check what it measured before lowering or failing it
**Why:** P0.3 asked for 99% of shots within 0.5 ft and got 96.6%, mixing which rotation is
correct with how precise the tracking is. P1.5 asked a space model to beat `closestDefDist`
at recovering a distance-derived label, above that variable's own 0.775 ceiling.
**How to apply:** re-specify to the quantity it meant and record the rewrite. Never rewrite
a pre-registered criterion (D13): report the miss and replan. Older: [[lessons-archive]].
