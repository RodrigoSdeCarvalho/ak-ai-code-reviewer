import io
from datetime import date

import pytest

from salesreport.cli import main
from salesreport.daily import daily_totals
from salesreport.records import Sale

EXPORT = """timestamp,store,amount
2026-05-01T09:12:00,north,12.50
2026-05-01T17:40:00,south,7.50
2026-05-03T11:05:00,north,20.00
2026-05-04T08:30:00,north,4.25
2026-05-04T19:55:00,south,30.00
"""


def _sales() -> list[Sale]:
    return [
        Sale(date(2026, 5, 1), "north", 1250),
        Sale(date(2026, 5, 3), "north", 2000),
        Sale(date(2026, 5, 4), "south", 3000),
    ]


def test_range_includes_the_until_day():
    rows = daily_totals(_sales(), date(2026, 5, 1), date(2026, 5, 4))
    assert [(row.day.day, row.amount_cents, row.transactions) for row in rows] == [
        (1, 1250, 1),
        (2, 0, 0),
        (3, 2000, 1),
        (4, 3000, 1),
    ]


def test_single_day_report():
    rows = daily_totals(_sales(), date(2026, 5, 3), date(2026, 5, 3))
    assert [(row.day, row.amount_cents) for row in rows] == [(date(2026, 5, 3), 2000)]


def test_cli_default_range_covers_the_whole_export(tmp_path):
    export = tmp_path / "pos.csv"
    export.write_text(EXPORT, encoding="utf-8")
    out = io.StringIO()
    assert main(["daily", str(export)], out) == 0
    lines = out.getvalue().splitlines()
    assert [line.split()[0] for line in lines[1:-1]] == ["2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04"]
    assert lines[-1].split() == ["total", "74.25", "5"]


def test_store_filter_and_out_of_range_sales_are_ignored():
    rows = daily_totals(_sales(), date(2026, 5, 2), date(2026, 5, 3), store="north")
    assert [(row.day.day, row.amount_cents) for row in rows] == [(2, 0), (3, 2000)]


def test_reversed_range_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        daily_totals(_sales(), date(2026, 5, 4), date(2026, 5, 1))
    export = tmp_path / "pos.csv"
    export.write_text(EXPORT, encoding="utf-8")
    assert main(["daily", str(export), "--since", "2026-05-04", "--until", "2026-05-01"], io.StringIO()) == 2
