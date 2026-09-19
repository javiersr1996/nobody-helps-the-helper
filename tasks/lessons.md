# Lessons

## A number with no code behind it is not a finding
**Why:** findings 4 and 5 opened the README with no source in the repo (commit 111a9ac: 50 lines
of prose, zero code). Rebuilt, finding 5 reversed and then its replacement was refuted too, and
finding 4 was answering a question Goldsberry never asked. P7.2 had fixed exactly this for
findings 1 and 3 and nobody swept the rest.
**How to apply:** before a number reaches a reader, name the script that prints it, RUN it, and
read the value back off the artefact rather than off your own intention: the video was reported
at 60 s because that is what the code asked ffmpeg for, and the file was 68. Then clone the repo
and follow your own README, whose test count was this machine's, not a clean install's.

## Check what the quantity is made of, not just that the test can fail
**Why, the test could not fail:** the estimated velocity correlated 0.99995 with the provider's
`speed`; the control field's AUC matched `closestDefDist`'s against a label derived from it.
**Why, it could fail, passed, and still measured the wrong thing:** the ball's entry angle
cleared a bar that a shuffled angle clears 0 times in 200. It is arctan(drop / run): `run`
carried it (+0.57), `drop` pointed the OTHER WAY (+0.17), and holding both left -0.04.
**How to apply:** ask what would have to be true for the two numbers to disagree, and correlate
every PART of a composite quantity before saying what it measures.

## Never report a pooled number where a per-unit split is possible
**Why:** F1's partial Spearman was 0.183 over 676 shots and 0.013 held out; P7.3's top-1 passed
pooled and held in three games of five, five rebounds of 285.
**How to apply:** split by the unit you generalise across (the game, never the shot), and put
the split INSIDE the bar, as P7.7 did.

## Set a threshold from measured evidence, then never move it
**Why:** a +0.02 bar set knowing nothing, amended to +0.005, missed by 0.0004. P1.5's 0.80 bar
sat above its own variable's ceiling. P7.2's area condition was already failing on calibration,
211 against 201 in plain sight, and no scaled zone could pass it at all.
**How to apply:** measure the available effect on the half you may look at, check the bar
against THAT, and ask what a passing version would score. Retiring an unpassable bar is not
moving it; the failure stays in the record (D13). Older: [[lessons-archive]].
