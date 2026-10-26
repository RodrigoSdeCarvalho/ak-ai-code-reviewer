from datetime import date

from metering.cli import main
from metering.events import load_events
from metering.report import build_report, render_csv
from metering.rollup import daily_totals, previous_month, rollup

EXPORT = """\
# account,metric,quantity,timestamp
acme,api_calls,100,2026-02-10T09:00:00Z
acme,api_calls,50,2026-02-10T15:00:00Z
acme,api_calls,200,2026-02-20T10:00:00Z
acme,api_calls,300,2026-03-02T08:00:00Z
acme,api_calls,120,2026-03-05T23:30:00-03:00
acme,api_calls,80,2026-03-06T12:00:00Z
acme,storage_gb,10,2026-03-01T00:00:00Z
acme,storage_gb,12,2026-03-15T00:00:00Z
globex,api_calls,40,2026-02-28T23:59:00Z
globex,api_calls,30,2026-03-01T00:01:00Z
globex,api_calls,10,2026-03-01T05:00:00Z
"""

MARCH_CSV = """\
account_id,metric,total,active_days,avg_per_day,peak_day,peak_quantity,previous_total,change
acme,api_calls,500,2,250.0,2026-03-02,300,350,+42.9%
acme,storage_gb,22,2,11.0,2026-03-15,12,,n/a
globex,api_calls,40,1,40.0,2026-03-01,40,40,+0.0%
"""


def _events():
    return list(load_events(EXPORT.splitlines()))


def test_daily_totals_are_per_utc_day():
    totals = [(t.account_id, t.metric, t.day, t.quantity) for t in daily_totals(reversed(_events()))]
    assert totals == [
        ("acme", "api_calls", date(2026, 2, 10), 150),
        ("acme", "api_calls", date(2026, 2, 20), 200),
        ("acme", "api_calls", date(2026, 3, 2), 300),
        ("acme", "api_calls", date(2026, 3, 6), 200),
        ("acme", "storage_gb", date(2026, 3, 1), 10),
        ("acme", "storage_gb", date(2026, 3, 15), 12),
        ("globex", "api_calls", date(2026, 2, 28), 40),
        ("globex", "api_calls", date(2026, 3, 1), 40),
    ]


def test_monthly_rollup_totals_and_peaks():
    usage = rollup(_events())
    march = usage[("acme", "api_calls", "2026-03")]
    assert (march.total, march.active_days, march.peak_day, march.peak_quantity) == (500, 2, date(2026, 3, 2), 300)
    assert usage[("acme", "api_calls", "2026-02")].total == 350
    assert usage[("globex", "api_calls", "2026-02")].total == 40


def test_report_compares_with_previous_month():
    rows = {(row.account_id, row.metric): row for row in build_report(rollup(_events()), "2026-03")}
    assert rows[("acme", "api_calls")].previous_total == 350
    assert rows[("acme", "api_calls")].change_pct == 42.9
    assert rows[("acme", "storage_gb")].previous_total is None
    assert rows[("globex", "api_calls")].change_pct == 0.0


def test_render_csv():
    assert render_csv(build_report(rollup(_events()), "2026-03")) == MARCH_CSV


def test_previous_month_wraps_the_year():
    assert previous_month("2026-01") == "2025-12"
    assert previous_month("2026-11") == "2026-10"


def test_cli_report(tmp_path, capsys):
    export = tmp_path / "usage.csv"
    export.write_text(EXPORT, encoding="utf-8")
    assert main(["report", str(export), "--month", "2026-03", "--format", "csv"]) == 0
    assert capsys.readouterr().out == MARCH_CSV
    assert main(["report", str(export), "--month", "2026-01"]) == 0
    assert "(no usage)" in capsys.readouterr().out
