# Lessons

## A number with no code behind it is not a finding
**Why:** findings 4 and 5 opened the README with no code in the repo (111a9ac); rebuilt, 5
reversed and its replacement was refuted, and 4 answered a question Goldsberry never asked.
**How to apply:** name the script that prints it, RUN it, read the value back off the BUILT
artefact (video said 60 s, file 68); counts too ("8 of 10" was 7). Assert and re-read.

## A null that lives only in the record is an overclaim in the deliverable
**Why:** F6's missing cost side lived in `todo.md` and a CSV, not the README or the page.
**How to apply:** ship the negative that qualifies a claim NEXT TO it, not in the record.
"What happened to X?" means X is missing from the deliverable, not that X needs explaining.

## Verify what moves by driving it, not by looking at it
**Why:** clips checked with screenshots shipped nine defects, all in transitions a still cannot
show (end of a clip, resume after pause, a button's label); two flipped with the possession.
**How to apply:** assert the state machine from the console (draw, seek, end, reveal) and give
the data its own gate (refuse a clip whose winner is over 3 ft off). Older: [[lessons-archive]].

## A check that cannot fail has checked nothing
**Why:** the drive-frame check compared `direction` with the sign of a lateral motion ALREADY
mirrored to be positive, printed 1.000 and was reported as a validation; really 0.67 and 0.72.
**How to apply:** before trusting a 100 %, name what would have made it 0 %; if nothing could,
the quantity is being compared with itself.

## A data limit decides the label, not the picture
**Why:** "the bundle has no pose" became "players as pucks"; the user: "no engancha nada, las
fichas deben ser jugadores de baloncesto". Honest and unwatchable is still a failed hook.
**How to apply:** draw the domain (players, arena); state next to it what is tracked and what
is drawn. Keep the limit where it bites: no measure taken from what is drawn.
