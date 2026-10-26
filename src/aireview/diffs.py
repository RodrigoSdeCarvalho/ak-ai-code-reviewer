"""Unified-diff parsing, changed-line sets, and diff generation (directory pairs and git repositories)."""

from __future__ import annotations

import difflib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

IGNORED_DIRS = {"__pycache__", ".pytest_cache", ".git", ".ruff_cache", ".mypy_cache"}
MAX_REPO_FILE_LINES = 2000
NO_NEWLINE = "\\ No newline at end of file"

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_GIT_HEADER_RE = re.compile(r"^diff --git (\S+) (\S+)$")


@dataclass
class Hunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    lines: list[str] = field(default_factory=list)  # raw lines with ' ', '+', '-' prefixes


@dataclass
class FileDiff:
    """One file of a diff. `path` is the post-change path (the old path for a deleted file)."""

    path: str
    old_path: str | None  # pre-change path; None for an added file
    is_new: bool = False
    is_deleted: bool = False
    hunks: list[Hunk] = field(default_factory=list)
    added_lines: set[int] = field(default_factory=set)  # new-side numbers of '+' lines
    changed_lines: set[int] = field(default_factory=set)  # added lines + nearest surviving line per deletion run


def normalize_path(p: str) -> str:
    """Repo-relative forward-slash path without `a/`, `b/` or `./` prefixes."""
    p = p.strip().replace("\\", "/")
    for prefix in ("a/", "b/"):
        if p.startswith(prefix):
            p = p[len(prefix) :]
            break
    while p.startswith("./"):
        p = p[2:]
    return p


def _header_path(raw: str) -> str | None:
    raw = raw.split("\t", 1)[0].strip()
    if raw == "/dev/null":
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        raw = raw[1:-1]
    return normalize_path(raw)


def _line_sets(hunks: list[Hunk]) -> tuple[set[int], set[int]]:
    added: set[int] = set()
    changed: set[int] = set()
    for hunk in hunks:
        new_no = hunk.new_start if hunk.new_len else hunk.new_start + 1
        in_deletion = False
        for line in hunk.lines:
            tag = line[:1]
            if tag == "-":
                in_deletion = True
                continue
            if tag == "\\":
                continue
            if in_deletion:
                changed.add(new_no)  # first surviving line after the deletion run
                in_deletion = False
            if tag == "+":
                added.add(new_no)
            new_no += 1
        if in_deletion and new_no > 1:
            changed.add(new_no - 1)  # deletion at the end of the hunk: the previous surviving line
    return added, changed | added


def parse_unified_diff(text: str) -> list[FileDiff]:
    """Parse a `git diff` (or plain unified) diff into per-file hunks and changed-line sets."""
    files: list[FileDiff] = []
    current: FileDiff | None = None
    lines = text.replace("\r\n", "\n").split("\n")
    i = 0

    def start(old: str | None, new: str | None) -> FileDiff:
        fd = FileDiff(path=new or old or "", old_path=old, is_new=old is None, is_deleted=new is None)
        files.append(fd)
        return fd

    while i < len(lines):
        line = lines[i]
        git = _GIT_HEADER_RE.match(line)
        if git:
            current = start(_header_path(git.group(1)), _header_path(git.group(2)))
            current.is_new = current.is_deleted = False
        elif current is not None and line.startswith("new file mode"):
            current.is_new, current.old_path = True, None
        elif current is not None and line.startswith("deleted file mode"):
            current.is_deleted = True
        elif current is not None and line.startswith("rename from "):
            current.old_path = normalize_path(line[len("rename from ") :])
        elif current is not None and line.startswith("rename to "):
            current.path = normalize_path(line[len("rename to ") :])
        elif line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            old, new = _header_path(line[4:]), _header_path(lines[i + 1][4:])
            if current is None or current.hunks:
                current = start(old, new)
            current.old_path = old
            current.path = new or old or current.path
            current.is_new, current.is_deleted = old is None, new is None
            i += 1
        elif (m := _HUNK_RE.match(line)) and current is not None:
            hunk = Hunk(
                old_start=int(m.group(1)),
                old_len=int(m.group(2)) if m.group(2) is not None else 1,
                new_start=int(m.group(3)),
                new_len=int(m.group(4)) if m.group(4) is not None else 1,
            )
            old_left, new_left = hunk.old_len, hunk.new_len
            while i + 1 < len(lines) and (old_left > 0 or new_left > 0 or lines[i + 1].startswith("\\")):
                body = lines[i + 1]
                tag = body[:1]
                if tag == "\\":
                    hunk.lines.append(body)
                elif tag == "+":
                    hunk.lines.append(body)
                    new_left -= 1
                elif tag == "-":
                    hunk.lines.append(body)
                    old_left -= 1
                elif tag in (" ", ""):
                    hunk.lines.append(" " + body[1:])
                    old_left -= 1
                    new_left -= 1
                else:
                    break
                i += 1
            current.hunks.append(hunk)
        i += 1

    for fd in files:
        fd.added_lines, fd.changed_lines = _line_sets(fd.hunks)
        if fd.is_deleted:
            fd.changed_lines = set()
    return files


def changed_files(text: str) -> set[str]:
    """Paths of every file in the diff (post-change path; old path for deletions)."""
    return {fd.path for fd in parse_unified_diff(text)}


def _read_text(path: Path) -> str | None:
    """File content with LF endings, or None for a binary file."""
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8").replace("\r\n", "\n")
    except UnicodeDecodeError:
        return None


def _list_files(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    out: dict[str, Path] = {}
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if path.is_file() and not any(part in IGNORED_DIRS for part in rel.parts) and path.suffix != ".pyc":
            out[rel.as_posix()] = path
    return out


def _file_diff(rel: str, old: str | None, new: str | None, context: int) -> list[str]:
    """Git-style diff lines (without trailing newlines) for one file; empty if unchanged."""
    header = [f"diff --git a/{rel} b/{rel}"]
    if old is None:
        header.append("new file mode 100644")
    elif new is None:
        header.append("deleted file mode 100644")
    old_lines = (old or "").splitlines(keepends=True)
    new_lines = (new or "").splitlines(keepends=True)
    body = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{rel}" if old is not None else "/dev/null",
            tofile=f"b/{rel}" if new is not None else "/dev/null",
            n=context,
        )
    )
    if not body:
        return [] if old is not None and new is not None else header
    out = [*header, body[0].rstrip("\n"), body[1].rstrip("\n")]
    for line in body[2:]:
        if line.endswith("\n"):
            out.append(line[:-1])
        else:
            out.extend([line, NO_NEWLINE])
    return out


def _binary_diff(rel: str, old: Path | None, new: Path | None) -> list[str]:
    a = f"a/{rel}" if old else "/dev/null"
    b = f"b/{rel}" if new else "/dev/null"
    return [f"diff --git a/{rel} b/{rel}", f"Binary files {a} and {b} differ"]


def diff_dirs(before: Path, after: Path, context: int = 3) -> str:
    """Deterministic git-style unified diff from directory `before` to `after` (files sorted, LF endings)."""
    old_files, new_files = _list_files(before), _list_files(after)
    out: list[str] = []
    for rel in sorted(old_files.keys() | new_files.keys()):
        old_path, new_path = old_files.get(rel), new_files.get(rel)
        old = _read_text(old_path) if old_path else None
        new = _read_text(new_path) if new_path else None
        if (old_path and old is None) or (new_path and new is None):
            if old_path and new_path and old_path.read_bytes() == new_path.read_bytes():
                continue
            out.extend(_binary_diff(rel, old_path, new_path))
            continue
        out.extend(_file_diff(rel, old, new, context))
    return "\n".join(out) + "\n" if out else ""


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def repo_diff(repo: Path, base: str | None) -> str:
    """`git diff <base>` in `repo`; with no base, every tracked text file (≤ 2000 lines) as an addition."""
    if base is not None:
        return _git(repo, "diff", "--no-color", "--no-ext-diff", base).replace("\r\n", "\n")
    tracked = sorted(p for p in _git(repo, "ls-files", "-z").split("\0") if p)
    out: list[str] = []
    for rel in tracked:
        path = repo / rel
        if not path.is_file() or any(part in IGNORED_DIRS for part in Path(rel).parts):
            continue
        text = _read_text(path)
        if text is None or text.count("\n") > MAX_REPO_FILE_LINES:
            continue
        out.extend(_file_diff(normalize_path(rel), None, text, 3))
    return "\n".join(out) + "\n" if out else ""
