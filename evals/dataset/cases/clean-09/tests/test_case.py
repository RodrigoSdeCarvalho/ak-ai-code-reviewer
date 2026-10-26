import pytest

from logscan.cli import build_parser, filter_from_args, main

APP_LOG = (
    "2026-05-01T10:00:00 INFO service started\n"
    "2026-05-01T10:00:05 DEBUG cache warm\n"
    "2026-05-01T10:01:00 WARNING slow query 1.2s\n"
    "not a log line\n"
    "2026-05-01T10:02:00 ERROR payment timeout\n"
)
WORKER_LOG = "2026-05-01T10:03:00 ERROR worker crashed\n2026-05-01T10:04:00 INFO worker restarted"


@pytest.fixture
def logs(tmp_path):
    app = tmp_path / "app.log"
    worker = tmp_path / "worker.log"
    app.write_text(APP_LOG, encoding="utf-8")
    worker.write_text(WORKER_LOG, encoding="utf-8")
    return str(app), str(worker)


def _run(capsys, argv):
    code = main(argv)
    return code, capsys.readouterr().out.splitlines()


def test_repeated_level_keeps_each_given_level(logs, capsys):
    code, out = _run(capsys, [*logs, "--level", "ERROR", "--level", "WARNING"])
    assert code == 0
    assert [line.split(" ", 2)[2] for line in out] == ["slow query 1.2s", "payment timeout", "worker crashed"]


def test_no_level_means_every_level(logs, capsys):
    _, out = _run(capsys, list(logs))
    assert len(out) == 6


def test_level_default_is_not_shared_between_parses():
    parser = build_parser()
    first = parser.parse_args(["a.log", "--level", "ERROR"])
    second = parser.parse_args(["a.log"])
    assert first.levels == ["ERROR"]
    assert second.levels is None
    assert filter_from_args(second).levels is None


def test_limit_counts_across_files(logs, capsys):
    _, out = _run(capsys, [*logs, "--level", "ERROR", "--limit", "2"])
    assert [line.split(" ", 2)[2] for line in out] == ["payment timeout", "worker crashed"]


def test_limit_zero_prints_nothing(logs, capsys):
    code, out = _run(capsys, [*logs, "--limit", "0"])
    assert code == 0
    assert out == []


def test_limit_larger_than_matches_prints_all(logs, capsys):
    _, out = _run(capsys, [*logs, "--limit", "100"])
    assert len(out) == 6
    assert out[-1].endswith("worker restarted")


@pytest.mark.parametrize("argv", [["x.log", "--limit", "-1"], ["x.log", "--limit", "two"], ["x.log", "--level", "info"]])
def test_bad_options_exit_with_usage_error(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(argv)
    assert exc.value.code == 2


def test_missing_file_reports_error(tmp_path, capsys):
    code = main([str(tmp_path / "missing.log")])
    assert code == 2
    assert "logscan:" in capsys.readouterr().err


def test_limit_reached_stops_before_opening_later_files(logs, tmp_path, capsys):
    app, _ = logs
    code, out = _run(capsys, [app, str(tmp_path / "missing.log"), "--level", "ERROR", "--limit", "1"])
    assert code == 0
    assert [line.split(" ", 2)[2] for line in out] == ["payment timeout"]
