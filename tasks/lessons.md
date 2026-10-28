# Lessons

## A number with no code behind it is not a finding
**Why:** findings 4 and 5 opened the README with no source in the repo (111a9ac: 50 lines of
prose, zero code). Rebuilt, 5 reversed and its replacement was refuted, and 4 answered a
question Goldsberry never asked.
**How to apply:** name the script that prints it, RUN it, and read the value back off the
BUILT artefact: the video was reported at 60 s and the file was 68; the README's test count
was this machine's. Grep the built file for the words the ruling bans too, which reached a
page caption once. A patch that prints "ok" has not patched anything: assert, then re-read.

## Never report a pooled number where a per-unit split is possible
**Why:** F1's partial Spearman was 0.183 over 676 shots and 0.013 held out; P7.3's top-1 passed pooled and held in three games of five, five rebounds of 285.
**How to apply:** split by the unit you generalise across (the game, never the shot).

## A null that lives only in the record is an overclaim in the deliverable
**Why:** F6 has a replicated buy side and NO established cost side, written in `todo.md` and
in `angle_tradeoff.csv` and in neither the README nor the page. The entry said "occupy the
glass" and never that it could not price what that costs. The user found it in one question.
**How to apply:** for every claim shaped like a recommendation, ship the negative that
qualifies it NEXT TO it, not in the record. A question of the form "what happened to X?"
means X is missing from the deliverable, not that X needs explaining.

## Verify what moves by driving it, not by looking at it
**Why:** the page's clips were checked with screenshots and shipped nine animation defects,
all in transitions a still cannot show (the end of a clip, resume after pause, a button's
label). Two clips were geometrically false: orientation flips with the possession.
**How to apply:** assert the state machine from the console (draw, seek, end, reveal) and
give the data its own gate, like refusing a clip whose winner is over 3 ft from the published
landing point. Older: [[lessons-archive]].
