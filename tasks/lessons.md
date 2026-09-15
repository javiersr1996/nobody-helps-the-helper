# Lessons

## A fixture must copy the real file's schema, never the code's assumption
**Why:** `canonical_ids` read the alias CSV by position; the real file has five columns
and column 1 is a NAME, so ids silently became strings. The suite could not catch it: the
fixture had two columns because it shared the code's wrong assumption, so it tested the bug.
**How to apply:** open the real file and copy its header before writing a fixture. When a
bug slips through, fix the fixture too and prove the test fails against the old code.

## A correlation near 1 with a provider's own field is a reproduction, not a validation
**Why:** the estimated velocity correlated 0.99995 with the provider's `speed`. That reads
as external validation but both compute the same smoothed derivative, so nothing was checked.
**How to apply:** ask what would have to be true for the two numbers to disagree. If the
answer is nothing, it is one computation run twice. Say so instead of banking it.

## When a criterion is missed, check what it measured before lowering or failing it
**Why:** P0.3 asked for 99% of shots within 0.5 ft and got 96.6%, because the criterion
mixed which rotation is correct with how precise the tracking is. On the question it meant
to settle the separation was absolute: 1,389 of 1,389 shots. P1.1 hit this twice more.
**How to apply:** re-specify to the quantity it meant to test and record the rewrite with
its reasoning. Never rewrite a criterion pre-registered for validation (D13): report and replan.

## A rank metric cannot calibrate a parameter that only rescales the score
**Why:** P1.4 was going to fit `slope` over a 144-cell grid against AUC and Spearman. But
`P_off = sigmoid(slope * score)` is monotone, so all three slopes give bit-identical
rankings: the grid had 48 real cells and 96 ties, and the "optimum not on the edge" check
was inverifiable in that dimension. Nothing in F1 can see `slope` at all.
**How to apply:** before putting a parameter in a grid, ask whether the objective can
distinguish its values. If the objective only sees ranks, any monotone reparameterisation
is invisible; fix the parameter, say why, and report its effect as a sensitivity band.
