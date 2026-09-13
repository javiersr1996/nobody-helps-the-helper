"""Download the SkillCorner basketball open data into data/raw.

It's about 730 MB: the tracking data travels through Git LFS, so git-lfs
must be installed (https://git-lfs.com). The dataset is not versioned in
this repository, it is downloaded.

Usage: python scripts/fetch_data.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/SkillCorner/opendata-basketball.git"
ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "raw" / "opendata-basketball"


def main() -> int:
    if shutil.which("git") is None:
        print("Can't find git on the PATH.", file=sys.stderr)
        return 1

    if (TARGET / "data" / "matches.json").exists():
        print(f"The dataset is already at {TARGET}. Nothing to do.")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    print(f"Cloning {REPO} into {TARGET} (about 730 MB, this takes a while)...")
    result = subprocess.run(["git", "clone", "--depth", "1", REPO, str(TARGET)], check=False)
    if result.returncode != 0:
        print("The clone failed.", file=sys.stderr)
        return result.returncode

    if not (TARGET / "data" / "matches.json").exists():
        print("The clone finished but data/matches.json is missing.", file=sys.stderr)
        return 1

    tracking = list(TARGET.glob("data/matches/*/*_tracking_data.jsonl.gz"))
    small = [p for p in tracking if p.stat().st_size < 1_000_000]
    if small:
        print(
            f"Warning: {len(small)} tracking files are under 1 MB. "
            "This usually means git-lfs was not installed and only the "
            "pointers were downloaded. Install git-lfs and run 'git lfs pull' "
            f"inside {TARGET}.",
            file=sys.stderr,
        )
        return 1

    print(f"Done: {len(tracking)} games with tracking in {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
