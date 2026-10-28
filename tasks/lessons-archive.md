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

## Check what the quantity is made of, not just that the test can fail
**Why, it could not fail:** the estimated velocity correlated 0.99995 with the provider's
`speed`. **Why, it could, passed, and still measured the wrong thing:** the entry angle
cleared a bar a shuffled angle clears 0 times in 200, and it is arctan(drop / run): `run`
carried it (+0.57), `drop` pointed the OTHER WAY (+0.17), holding both left -0.04.
**How to apply:** ask what would have to be true for the two numbers to disagree, and
correlate every PART of a composite quantity before saying what it measures.

## Set a threshold from measured evidence, then never move it
**Why:** a +0.02 bar set knowing nothing, amended to +0.005, missed by 0.0004. P7.2's area
condition was already failing on calibration, 211 against 201 in plain sight.
**How to apply:** measure the available effect on the half you may look at and check the bar
against THAT. Retiring an unpassable bar is not moving it; the failure stays (D13).

(Both archived 2026-09-19 when the file hit its 30-line cap: the pre-registration
phase is closed and what is left is shipping. They stand, they are just not the
rules that bite this week.)
