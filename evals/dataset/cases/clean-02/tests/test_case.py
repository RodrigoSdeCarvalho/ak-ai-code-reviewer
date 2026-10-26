import subprocess

import pytest

import relnotes.git as git
from relnotes.cli import main

SEP = git.FIELD_SEP
LOG = f"a1b2c3d{SEP}Ana{SEP}feat(billing): add invoices export\ne4f5a6b{SEP}Bo{SEP}fix: round VAT per line\n"


class FakeRun:
    def __init__(self, stdout=LOG, returncode=0, stderr=""):
        self.calls = []
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if self.returncode:
            raise subprocess.CalledProcessError(self.returncode, argv, output="", stderr=self.stderr)
        return subprocess.CompletedProcess(argv, 0, stdout=self.stdout, stderr="")


@pytest.fixture
def fake(monkeypatch):
    run = FakeRun()
    monkeypatch.setattr(git.subprocess, "run", run)
    return run


def test_argv_is_a_list_with_paths_after_separator(fake, tmp_path):
    commits = git.commits_between(tmp_path, "v1.2.0", paths=["packages/billing", "-weird dir"])
    argv, kwargs = fake.calls[0]
    assert argv == ["git", "log", "--no-merges", "--reverse", git.LOG_FORMAT, "v1.2.0..HEAD", "--", "packages/billing", "-weird dir"]
    assert not kwargs.get("shell", False)
    assert kwargs["cwd"] == tmp_path
    assert [c.short_sha for c in commits] == ["a1b2c3d", "e4f5a6b"]


def test_without_paths_the_separator_is_last(fake, tmp_path):
    git.commits_between(tmp_path, "v1", "v2")
    assert fake.calls[0][0][-2:] == ["v1..v2", "--"]


@pytest.mark.parametrize("since", ["--output=/tmp/x", "", "v1 ; rm -rf /", "-p"])
def test_option_like_or_spaced_revisions_are_rejected(fake, tmp_path, since):
    with pytest.raises(ValueError):
        git.commits_between(tmp_path, since)
    assert fake.calls == []


def test_git_failure_becomes_git_error(monkeypatch, tmp_path):
    monkeypatch.setattr(git.subprocess, "run", FakeRun(returncode=128, stderr="fatal: bad revision 'v9'\n"))
    with pytest.raises(git.GitError, match="bad revision"):
        git.commits_between(tmp_path, "v9")


def test_cli_passes_paths_and_writes_notes(fake, tmp_path):
    out = tmp_path / "NOTES.md"
    code = main(["2.4.0", "--since", "v2.3.0", "--repo", str(tmp_path), "--path", "a", "--path", "b", "--output", str(out)])
    assert code == 0
    assert fake.calls[0][0][-3:] == ["--", "a", "b"]
    text = out.read_text(encoding="utf-8")
    assert "### Features\n- add invoices export (a1b2c3d)" in text
    assert "### Fixes\n- round VAT per line (e4f5a6b)" in text


def test_cli_reports_bad_revision(fake, tmp_path, capsys):
    assert main(["2.4.0", "--since=-all", "--repo", str(tmp_path)]) == 2
    assert "not a git revision" in capsys.readouterr().err
    assert fake.calls == []


def test_cli_empty_range_exits_1(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(git.subprocess, "run", FakeRun(stdout=""))
    assert main(["2.4.0", "--since", "v2.3.0", "--repo", str(tmp_path), "--path", "docs"]) == 1
    assert "no commits in v2.3.0..HEAD" in capsys.readouterr().err
