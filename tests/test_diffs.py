import shutil
import subprocess
from pathlib import Path

import pytest

from aireview.diffs import changed_files, diff_dirs, normalize_path, parse_unified_diff, repo_diff


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def _lines(n: int, prefix: str = "line") -> str:
    return "".join(f"{prefix} {i}\n" for i in range(1, n + 1))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("a/src/x.py", "src/x.py"), ("b/src/x.py", "src/x.py"), ("./src/x.py", "src/x.py"), ("src\\x.py", "src/x.py")],
)
def test_normalize_path(raw, expected):
    assert normalize_path(raw) == expected


def test_diff_dirs_added_deleted_modified(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    _write(before, {"pkg/keep.py": _lines(10), "pkg/gone.py": "x = 1\n", "pkg/same.py": "y = 2\n"})
    _write(after, {"pkg/keep.py": _lines(10).replace("line 5\n", "line five\n"), "pkg/new.py": "a\nb\n"})
    _write(after, {"pkg/same.py": "y = 2\n", "pkg/__pycache__/junk.pyc": "zz"})

    text = diff_dirs(before, after)
    assert text.index("a/pkg/gone.py") < text.index("a/pkg/keep.py") < text.index("a/pkg/new.py")
    assert "same.py" not in text and "__pycache__" not in text
    assert "--- /dev/null\n+++ b/pkg/new.py\n@@ -0,0 +1,2 @@" in text
    assert "--- a/pkg/gone.py\n+++ /dev/null\n@@ -1 +0,0 @@" in text
    assert diff_dirs(before, after) == text  # deterministic

    files = {fd.path: fd for fd in parse_unified_diff(text)}
    assert files["pkg/new.py"].is_new and files["pkg/new.py"].old_path is None
    assert files["pkg/new.py"].added_lines == {1, 2}
    assert files["pkg/gone.py"].is_deleted and files["pkg/gone.py"].changed_lines == set()
    assert files["pkg/keep.py"].added_lines == {5}
    assert files["pkg/keep.py"].changed_lines == {5}
    assert changed_files(text) == {"pkg/new.py", "pkg/gone.py", "pkg/keep.py"}


def test_multiple_hunks_and_pure_deletion(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    old = _lines(40)
    new_lines = old.splitlines(keepends=True)
    new_lines.insert(3, "inserted\n")  # new line 4
    del new_lines[30:32]  # drop old lines 30-31; old line 32 becomes new line 31
    _write(before, {"m.py": old})
    _write(after, {"m.py": "".join(new_lines)})

    [fd] = parse_unified_diff(diff_dirs(before, after))
    assert len(fd.hunks) == 2
    assert fd.added_lines == {4}
    assert fd.changed_lines == {4, 31}
    assert fd.hunks[1].lines.count("-line 30") == 1


def test_deletion_at_end_of_file_maps_to_previous_line(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    _write(before, {"m.py": _lines(10)})
    _write(after, {"m.py": _lines(8)})
    [fd] = parse_unified_diff(diff_dirs(before, after))
    assert fd.added_lines == set()
    assert fd.changed_lines == {8}


def test_missing_newline_at_end_of_file(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    _write(before, {"m.py": "a\nb"})
    _write(after, {"m.py": "a\nc"})
    text = diff_dirs(before, after)
    assert "\\ No newline at end of file" in text
    [fd] = parse_unified_diff(text)
    assert fd.added_lines == {2}


def test_parse_git_rename_and_mode_headers():
    text = (
        "diff --git a/old/name.py b/new/name.py\n"
        "similarity index 90%\n"
        "rename from old/name.py\n"
        "rename to new/name.py\n"
        "index 111..222 100644\n"
        "--- a/old/name.py\n"
        "+++ b/new/name.py\n"
        "@@ -1,3 +1,3 @@ def f():\n"
        " a\n"
        "-b\n"
        "+B\n"
        " c\n"
        "diff --git a/pure.py b/pure2.py\n"
        "similarity index 100%\n"
        "rename from pure.py\n"
        "rename to pure2.py\n"
    )
    first, second = parse_unified_diff(text)
    assert (first.path, first.old_path, first.is_new, first.is_deleted) == ("new/name.py", "old/name.py", False, False)
    assert first.added_lines == {2}
    assert (second.path, second.old_path, second.hunks) == ("pure2.py", "pure.py", [])


def test_parse_plain_unified_diff_with_crlf():
    text = "--- a/x.py\r\n+++ b/x.py\r\n@@ -1,2 +1,3 @@\r\n a\r\n+--- not a header\r\n b\r\n"
    [fd] = parse_unified_diff(text)
    assert fd.path == "x.py"
    assert fd.added_lines == {2}


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_diff_dirs_output_applies_with_git(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    _write(before, {"a.py": _lines(30), "b.py": "x\n"})
    _write(after, {"a.py": _lines(30).replace("line 3\n", "LINE 3\n").replace("line 25\n", ""), "c.py": "new\n"})
    patch = tmp_path / "change.diff"
    patch.write_text(diff_dirs(before, after), encoding="utf-8", newline="\n")
    subprocess.run(["git", "init", "-q"], cwd=before, check=True)
    subprocess.run(["git", "apply", str(patch)], cwd=before, check=True)
    assert diff_dirs(before, after) == ""


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_repo_diff_whole_repo_and_base(tmp_path):
    repo = tmp_path / "repo"
    _write(repo, {"src/app.py": "print('hi')\n", "big.txt": _lines(2001), "README.md": "# r\n"})
    (repo / "blob.bin").write_bytes(b"\x00\x01\x02")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([*git, "init", "-q"], cwd=repo, check=True)
    subprocess.run([*git, "add", "-A"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-qm", "init"], cwd=repo, check=True)

    whole = repo_diff(repo, None)
    assert changed_files(whole) == {"src/app.py", "README.md"}
    assert all(fd.is_new for fd in parse_unified_diff(whole))

    _write(repo, {"src/app.py": "print('hi')\nprint('bye')\n"})
    [fd] = parse_unified_diff(repo_diff(repo, "HEAD"))
    assert (fd.path, fd.added_lines) == ("src/app.py", {2})
