# Lessons archive

Retired from `lessons.md` to keep it inside its 30-line cap. Kept because the reasoning
still holds, moved because the live risks of the project have shifted past them.

## A fixture must copy the real file's schema, never the code's assumption
**Why:** `canonical_ids` read the alias CSV by position; the real file has five columns
and column 1 is a NAME, so ids silently became strings. The suite could not catch it: the
fixture had two columns because it shared the code's wrong assumption, so it tested the bug.
**How to apply:** open the real file and copy its header before writing a fixture. When a
bug slips through, fix the fixture too and prove the test fails against the old code.
**Status:** internalised. P1.5 applied it unprompted, rebuilding the `_shot_row` fixture
around the real `location` field rather than a convenient stand-in.

## When a criterion is missed, check what it measured before lowering or failing it
**Why:** P0.3 asked for 99% of shots within 0.5 ft and got 96.6%, mixing which rotation is
correct with how precise the tracking is. P1.5 asked a space model to beat `closestDefDist`
at recovering a distance-derived label, above that variable's own 0.775 ceiling.
**How to apply:** re-specify to the quantity it meant and record the rewrite.
(Archived 2026-09-17, folded into the threshold lesson in lessons.md.)

## Superseded 2026-09-19 by "Check what the quantity is made of"
## Check the test can fail before you run it
**Why:** the estimated velocity correlated 0.99995 with the provider's `speed`, one derivative
computed twice; the control field's AUC matched `closestDefDist`'s against a label derived from
it; and 4.4 of 5 defenders sat between their man and the rim whether or not anyone helped.
**How to apply:** ask what would have to be true for the two numbers to disagree, and print
every quantity's spread first.
