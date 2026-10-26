from datetime import date, datetime, timedelta

import pytest
from scheduling.calendar import CalendarSet, Region
from scheduling.holidays import JsonHolidaySource, StaticHolidaySource, UnknownRegion, write_holiday_file
from scheduling.sla import Priority, SlaPolicy, Ticket

HOLIDAYS = {
    "PT": [date(2026, 4, 3), date(2026, 4, 25), date(2026, 12, 25), date(2027, 1, 1)],
    "IL": [date(2026, 4, 8), date(2026, 9, 21), date(2027, 1, 3)],
}
REGIONS = [Region("PT"), Region("IL", weekend=frozenset({4, 5}), cutoff_hour=16)]


class CountingSource(StaticHolidaySource):
    def __init__(self) -> None:
        super().__init__(HOLIDAYS)
        self.calls = 0

    def holidays(self, region: str, year: int) -> list[date]:
        self.calls += 1
        return super().holidays(region, year)


def _ticket(ticket_id: str, region: str, opened: datetime, priority: Priority) -> Ticket:
    return Ticket(ticket_id, opened, priority, region)


def test_holiday_data_is_loaded_once_per_region_and_year():
    source = CountingSource()
    policy = SlaPolicy(CalendarSet(source, REGIONS))
    tickets = [
        _ticket(f"T{i}", "PT" if i % 2 else "IL", datetime(2026, 12, 1, 9) + timedelta(days=i // 2), Priority.LOW)
        for i in range(60)
    ]
    policy.overdue(tickets, date(2027, 2, 1))
    assert source.calls <= 4


def test_due_dates_respect_regional_weekends_holidays_and_cutoffs():
    policy = SlaPolicy(CalendarSet(CountingSource(), REGIONS))
    assert policy.due_date(_ticket("A", "PT", datetime(2026, 4, 2, 10), Priority.HIGH)) == date(2026, 4, 7)
    assert policy.due_date(_ticket("B", "PT", datetime(2026, 4, 2, 18), Priority.URGENT)) == date(2026, 4, 7)
    assert policy.due_date(_ticket("C", "IL", datetime(2026, 4, 2, 15), Priority.NORMAL)) == date(2026, 4, 12)
    assert policy.due_date(_ticket("D", "IL", datetime(2026, 4, 2, 16, 30), Priority.URGENT)) == date(2026, 4, 6)
    assert policy.due_date(_ticket("E", "PT", datetime(2026, 12, 24, 9), Priority.HIGH)) == date(2026, 12, 29)


def test_overdue_grouped_by_region():
    policy = SlaPolicy(CalendarSet(CountingSource(), REGIONS))
    tickets = [
        _ticket("A", "PT", datetime(2026, 4, 2, 10), Priority.HIGH),
        _ticket("B", "PT", datetime(2026, 4, 2, 18), Priority.URGENT),
        _ticket("C", "IL", datetime(2026, 4, 2, 15), Priority.NORMAL),
        _ticket("D", "IL", datetime(2026, 4, 2, 16, 30), Priority.URGENT),
    ]
    late = policy.overdue(tickets, date(2026, 4, 9))
    assert [(item.ticket.id, item.days_late) for item in late] == [("D", 3), ("A", 2), ("B", 2)]
    grouped = policy.overdue_by_region(tickets, date(2026, 4, 9))
    assert {code: [item.ticket.id for item in items] for code, items in grouped.items()} == {
        "IL": ["D"],
        "PT": ["A", "B"],
    }
    assert not policy.is_breached(tickets[2], date(2026, 4, 12))


def test_json_source_round_trip_and_unknown_region(tmp_path):
    path = tmp_path / "holidays.json"
    write_holiday_file(path, HOLIDAYS)
    source = JsonHolidaySource(path)
    assert source.holidays("PT", 2026) == HOLIDAYS["PT"][:3]
    with pytest.raises(UnknownRegion):
        source.holidays("BR", 2026)
    with pytest.raises(KeyError):
        CalendarSet(source, REGIONS).for_region("BR")
