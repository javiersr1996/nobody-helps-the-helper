# Lessons

## A fixture must copy the real file's schema, never the code's assumption
**Why:** `Dataset.canonical_ids` read the alias CSV by position, columns 0 and 1. The
real file has five columns and column 1 is a player NAME, so the mapping silently turned
integer player ids into strings. The suite could not catch it: the synthetic fixture had
two columns because it was built from the same wrong assumption the code made, so the
test was validating the bug.
**How to apply:** before writing a fixture for an external data format, open the real
file and copy its header. If you cannot open it, do not write the fixture yet. And when
a bug does slip through, fix the fixture too, then prove the regression test fails
against the old code.

## A correlation near 1 with a provider's own field is a reproduction, not a validation
**Why:** the estimated velocity correlated 0.99995 with the provider's `speed` (MAE
0.025 ft/s). That reads as external validation but it means both compute the same
smoothed derivative, so nothing was validated and the estimate is still unchecked.
**How to apply:** before counting agreement as evidence, ask what would have to be true
for the two numbers to disagree. If the answer is nothing, it is the same computation
run twice. Say so in the report instead of banking the correlation.

## When a criterion is missed, check what it measured before lowering or failing it
**Why:** P0.3 asked for 99% of shots within 0.5 ft and got 96.6%. The criterion mixed two
questions: which rotation is correct, and how precise the tracking is. On the question it
meant to settle the separation was absolute, 1,389 of 1,389 shots, worst error under the
winner far below the best error under the loser.
**How to apply:** re-specify the criterion to the quantity it meant to test and record
the rewrite with its reasoning, so the trail is visible. Exception: a criterion that was
pre-registered for validation is never rewritten after seeing the numbers (D13). Report
the miss and replan.
