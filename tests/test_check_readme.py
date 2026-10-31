"""Tests for scripts/check_readme.py (C2): the real README passes, and a README with one bold
number changed fails, because a check that cannot fail has checked nothing (lesson 4)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_readme import run  # noqa: E402

README = ROOT / "README.md"


def test_real_readme_passes() -> None:
    rows = run(README)
    assert [name for ok, name, _ in rows if not ok] == []


def test_changed_bold_number_fails(tmp_path: Path) -> None:
    text = README.read_text(encoding="utf-8")
    assert "more than **+0.13 ft**" in text  # the claim's bound
    copy = tmp_path / "README.md"
    copy.write_text(text.replace("more than **+0.13 ft**", "more than **+0.12 ft**"),
                    encoding="utf-8")
    failed = [(name, detail) for ok, name, detail in run(copy) if not ok]
    assert len(failed) == 1
    assert "rule out more than" in failed[0][0]
    assert "+0.12 ft" in failed[0][1] and "+0.13 ft" in failed[0][1]


def test_code_tokens_count_toward_the_rendered_limit(tmp_path: Path) -> None:
    text = README.read_text(encoding="utf-8")
    copy = tmp_path / "README.md"
    copy.write_text(text + "\n```bash\n" + "word " * 20 + "\n```\n", encoding="utf-8")
    failed = [name for ok, name, _ in run(copy) if not ok]
    assert failed == ["rendered"]
