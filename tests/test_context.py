"""User-message context: numbered post-change files, hunk fallback, the diff at the end, determinism."""

from __future__ import annotations

from pathlib import Path

from aireview.diffs import diff_dirs
from aireview.reviewer.context import build_user_message


def _make_case(tmp_path: Path, after_text: str, before_text: str = "a = 1\nb = 2\n") -> tuple[str, Path]:
    before, after = tmp_path / "before", tmp_path / "after"
    (before / "pkg").mkdir(parents=True)
    (after / "pkg").mkdir(parents=True)
    (before / "pkg" / "mod.py").write_text(before_text, encoding="utf-8")
    (after / "pkg" / "mod.py").write_text(after_text, encoding="utf-8")
    (before / "pkg" / "gone.py").write_text("x = 1\n", encoding="utf-8")
    return diff_dirs(before, after), after


def test_full_file_with_line_numbers_then_diff(tmp_path: Path) -> None:
    diff, after = _make_case(tmp_path, "a = 1\nb = 3\nc = 4\n")
    msg = build_user_message(diff, after)
    assert "### File 1/1: pkg/mod.py (modified)" in msg
    assert "   1 | a = 1\n   2 | b = 3\n   3 | c = 4" in msg
    assert "Deleted files: pkg/gone.py" in msg
    assert msg.index("## Changed files") < msg.index("## Unified diff")
    assert msg.rstrip().endswith("```")
    assert diff.rstrip("\n") in msg


def test_hunks_only_without_repo_or_when_too_long(tmp_path: Path) -> None:
    diff, after = _make_case(tmp_path, "a = 1\nb = 3\nc = 4\n")
    for msg in (build_user_message(diff, None), build_user_message(diff, after, max_full_lines=2)):
        assert "Changed hunks only" in msg
        assert "   2 + | b = 3" in msg
        assert "     - | b = 2" in msg
        assert "   1   | a = 1" in msg


def test_new_file_and_fence_longer_than_content_backticks(tmp_path: Path) -> None:
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (after / "doc.py").write_text('S = """\n```\n"""\n', encoding="utf-8")
    msg = build_user_message(diff_dirs(before, after), after)
    assert "(new file)" in msg
    assert "````\n   1 | S" in msg


def test_path_outside_repo_falls_back_to_hunks(tmp_path: Path) -> None:
    (tmp_path / "secret.py").write_text("token = 1\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    diff = "diff --git a/../secret.py b/../secret.py\n--- a/../secret.py\n+++ b/../secret.py\n@@ -1 +1 @@\n-x\n+y\n"
    msg = build_user_message(diff, repo)
    assert "token" not in msg
    assert "Changed hunks only" in msg


def test_deterministic(tmp_path: Path) -> None:
    diff, after = _make_case(tmp_path, "a = 1\nb = 3\n")
    assert build_user_message(diff, after) == build_user_message(diff.replace("\n", "\r\n"), after)
