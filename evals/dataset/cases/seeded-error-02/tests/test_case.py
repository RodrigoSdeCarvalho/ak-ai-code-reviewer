from decimal import Decimal

import pytest

from pipeline.load import Loader, Rejection, TooManyRejected
from pipeline.sink import MemorySink, SinkError


def _row(i: int, amount: str = "10.00") -> dict[str, str]:
    return {"date": "2026-02-03", "account": f"ACC-{i:03d}", "amount": amount, "currency": "EUR"}


class FlakySink(MemorySink):
    """Fails the n-th write (1-based) and accepts every other one."""

    def __init__(self, fail_on: int) -> None:
        super().__init__()
        self._fail_on = fail_on
        self._calls = 0

    def write(self, batch):
        self._calls += 1
        if self._calls == self._fail_on:
            raise SinkError("connection reset by peer")
        super().write(batch)


def test_malformed_rows_are_skipped_and_reported():
    sink = MemorySink()
    bad_date = {"date": "2026-02-30", "account": "X", "amount": "1", "currency": "EUR"}
    rows = [_row(1), _row(2, amount="ten"), _row(3), bad_date]
    report = Loader(sink, batch_size=2).load(rows)
    assert report.loaded == 2
    assert [r.row for r in report.rejected] == [2, 4]
    assert not report.clean
    assert sink.accounts() == {"ACC-001", "ACC-003"}
    assert sink.total("EUR") == Decimal("20.00")


def test_too_many_rejected_rows_abort():
    rows = [_row(1, amount="?"), _row(2, amount="?"), _row(3)]
    with pytest.raises(TooManyRejected):
        Loader(MemorySink(), max_rejected=1).load(rows)


def test_sink_failure_is_not_reported_as_a_rejected_row():
    sink = FlakySink(fail_on=1)
    rows = [_row(i) for i in range(10)]
    with pytest.raises(SinkError):
        Loader(sink, batch_size=4).load(rows)


def test_failed_batch_aborts_the_load_instead_of_being_dropped():
    sink = FlakySink(fail_on=2)
    rows = [_row(i) for i in range(10)]
    with pytest.raises(SinkError):
        Loader(sink, batch_size=4).load(rows)
    assert len(sink) == 4


def test_rejections_carry_row_and_reason():
    report = Loader(MemorySink()).load([_row(1, amount="1e999999999")])
    assert report.rejected == [Rejection(1, "bad amount '1e999999999'")]
    assert report.loaded == 0
