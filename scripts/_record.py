"""The freeze commits, read out of the repository, for the outputs that show them.

Two deliverables put the record on screen: the last slide of the video and the last section
of the page. They were reading `git log` with their own copy of the filter, which is two
lists of what counts as the record, free to drift apart. This is the one list.

It lives in `scripts/` rather than in `scbasket` because it shells out to git: the published
package measures rebounds and has no business knowing it is in a repository at all.
"""

from __future__ import annotations

import subprocess

#: What the record is made of: the freezes, and the entries that went against us.
WANTED = ("Freeze", "Refute", "Retire", "Grade", "Read the held-out")


def freeze_commits(limit: int = 40) -> list[tuple[str, str]]:
    """(sha, subject) of the commits that make up the record, newest first.

    Falls back to the most recent commits if none of them match, so a clone with a rewritten
    history shows something true rather than an empty list.
    """
    log = subprocess.run(["git", "log", "--oneline", f"-{limit}"],
                         capture_output=True, text=True)
    lines = [ln for ln in log.stdout.splitlines() if any(w in ln for w in WANTED)]
    return [(sha, subject) for sha, _, subject in
            (ln.partition(" ") for ln in (lines or log.stdout.splitlines()[:6]))]
