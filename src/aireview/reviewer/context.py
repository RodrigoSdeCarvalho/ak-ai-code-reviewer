"""Builds the reviewer's user message: each changed file with post-change line numbers, then the diff."""

from __future__ import annotations

import re
from pathlib import Path

from aireview.diffs import FileDiff, parse_unified_diff

MAX_FULL_LINES = 600

_BACKTICKS_RE = re.compile(r"`{3,}")


def _fence(text: str, lang: str = "") -> str:
    """Fence `text` with a backtick run longer than any run it contains."""
    longest = max((len(m.group(0)) for m in _BACKTICKS_RE.finditer(text)), default=2)
    ticks = "`" * (longest + 1)
    return f"{ticks}{lang}\n{text}\n{ticks}"


def _read_post_change(repo: Path, rel: str) -> list[str] | None:
    """Lines of `repo/rel`, or None if it is missing, outside the repo, binary or not UTF-8."""
    root = repo.resolve()
    path = (root / rel).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8").replace("\r\n", "\n").splitlines()
    except UnicodeDecodeError:
        return None


def _numbered(lines: list[str]) -> str:
    width = max(4, len(str(len(lines))))
    return "\n".join(f"{n:>{width}} | {line}" for n, line in enumerate(lines, start=1))


def _hunks_view(fd: FileDiff) -> str:
    """Hunks with new-side line numbers; removed lines have no number."""
    last = max((h.new_start + h.new_len for h in fd.hunks), default=1)
    width = max(4, len(str(last)))
    out: list[str] = []
    for hunk in fd.hunks:
        out.append(f"@@ -{hunk.old_start},{hunk.old_len} +{hunk.new_start},{hunk.new_len} @@")
        new_no = hunk.new_start
        for raw in hunk.lines:
            tag, text = raw[:1], raw[1:]
            if tag == "\\":
                continue
            if tag == "-":
                out.append(f"{'':>{width}} - | {text}")
                continue
            out.append(f"{new_no:>{width}} {'+' if tag == '+' else ' '} | {text}")
            new_no += 1
    return "\n".join(out)


def _file_section(index: int, total: int, fd: FileDiff, repo: Path | None, max_full_lines: int) -> str:
    status = "new file" if fd.is_new else (f"renamed from {fd.old_path}" if fd.old_path != fd.path else "modified")
    lines = _read_post_change(repo, fd.path) if repo is not None else None
    if lines is not None and len(lines) <= max_full_lines:
        body = f"Full post-change content ({len(lines)} lines):\n{_fence(_numbered(lines))}"
    elif fd.hunks:
        body = f"Changed hunks only (new-side line numbers):\n{_fence(_hunks_view(fd))}"
    else:
        body = "No text content to show (binary file or mode change)."
    return f"### File {index}/{total}: {fd.path} ({status})\n\n{body}"


def build_user_message(diff_text: str, repo: Path | None, max_full_lines: int = MAX_FULL_LINES) -> str:
    """The user message for one review: changed files with post-change line numbers, then the unified diff."""
    diff_text = diff_text.replace("\r\n", "\n")
    parsed = parse_unified_diff(diff_text)
    files = [fd for fd in parsed if not fd.is_deleted]
    deleted = sorted(fd.path for fd in parsed if fd.is_deleted)
    parts = ["Review the following change. Line numbers are post-change line numbers.", "## Changed files"]
    parts += [_file_section(i, len(files), fd, repo, max_full_lines) for i, fd in enumerate(files, start=1)]
    if deleted:
        parts.append("Deleted files: " + ", ".join(deleted))
    parts.append(f"## Unified diff\n\n{_fence(diff_text.rstrip('\n'), 'diff')}")
    return "\n\n".join(parts) + "\n"
