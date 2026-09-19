# Lessons

## A number with no code behind it is not a finding
**Why:** findings 4 and 5 opened the README with no source anywhere in the repo (commit 580f6b7:
50 lines of prose, zero code). Rebuilt, finding 5 REVERSED, +0.018 becoming -0.353 held out in
five games of five, and finding 4 was answering a question Goldsberry never asked. P7.2 had
already fixed this for findings 1 and 3 and nobody swept the rest.
**How to apply:** before a number reaches a reader, name the script that prints it and RUN it;
then clone the repo and follow your own README, whose test count was this machine's, not a
clean install's.

## Never report a pooled number where a per-unit split is possible
**Why:** F1's partial Spearman was 0.183 over 676 shots, 0.013 held out, negative in three games
of five. P7.3 repeated it: top-1 passed pooled, held in three of five, five rebounds of 285.
**How to apply:** split by the unit you generalise across (the game, never the shot) and print
every value before quoting an average. Better, put the split INSIDE the bar, as P7.7 did.

## Check the test can fail before you run it
**Why:** the estimated velocity correlated 0.99995 with the provider's `speed`, one derivative
computed twice; the control field's AUC matched `closestDefDist`'s against a label derived from
it; and 4.4 of 5 defenders sat between their man and the rim whether or not anyone helped.
**How to apply:** ask what would have to be true for the two numbers to disagree, and print
every quantity's spread first.

## Set a threshold from measured evidence, then never move it
**Why:** three times. A +0.02 bar set knowing nothing, amended to +0.005, missed by 0.0004.
P1.5's 0.80 bar sat above its own variable's ceiling. P7.2's area condition was already failing
on calibration, 211 against 201 in plain sight, and no scaled zone could pass it at all.
**How to apply:** measure the available effect on the half you may look at, check the bar
against THAT, and ask what a passing version would score. Retiring an unpassable bar is not
moving it; the failure stays in the record (D13). Older: [[lessons-archive]].
