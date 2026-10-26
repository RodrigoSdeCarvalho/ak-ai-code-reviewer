import threading
from datetime import datetime

import pytest

from metering.usage import UsageMeter

NOW = datetime(2026, 9, 30, 23, 59, 59)
THREADS = 8
CALLS_PER_THREAD = 20_000


def test_concurrent_records_and_drains_lose_nothing():
    meter = UsageMeter()
    start = threading.Barrier(THREADS + 1)
    drained: list[int] = []
    done = threading.Event()

    def worker(index: int) -> None:
        start.wait()
        tenant = f"t{index % 3}"
        for _ in range(CALLS_PER_THREAD):
            meter.record(tenant)

    def drainer() -> None:
        start.wait()
        while not done.is_set():
            drained.append(meter.drain(NOW).total)

    workers = [threading.Thread(target=worker, args=(i,)) for i in range(THREADS)]
    collector = threading.Thread(target=drainer)
    for thread in [*workers, collector]:
        thread.start()
    for thread in workers:
        thread.join()
    done.set()
    collector.join()
    assert sum(drained) + meter.drain(NOW).total == THREADS * CALLS_PER_THREAD


def test_drain_resets_and_snapshot_does_not():
    meter = UsageMeter({"acme": 5})
    meter.record("acme", 2)
    meter.record("globex")
    assert meter.snapshot(NOW).calls == {"acme": 7, "globex": 1}
    assert meter.count("acme") == 7
    drained = meter.drain(NOW)
    assert drained.calls == {"acme": 7, "globex": 1}
    assert meter.count("acme") == 0
    assert meter.snapshot(NOW).total == 0


def test_returned_snapshots_are_independent_of_later_calls():
    meter = UsageMeter()
    meter.record("acme")
    snapshot = meter.snapshot(NOW)
    drained = meter.drain(NOW)
    meter.record("acme", 10)
    assert snapshot.calls == {"acme": 1}
    assert drained.calls == {"acme": 1}


def test_default_initial_counts_are_not_shared():
    first = UsageMeter()
    first.record("acme", 3)
    second = UsageMeter()
    assert second.count("acme") == 0
    assert UsageMeter.__init__.__defaults__ == ({},)


def test_initial_mapping_is_copied():
    persisted = {"acme": 4}
    meter = UsageMeter(persisted)
    meter.record("acme")
    assert persisted == {"acme": 4}
    assert meter.count("acme") == 5


def test_csv_rows_order():
    meter = UsageMeter({"b": 2, "a": 2, "c": 9})
    assert meter.snapshot(NOW).to_csv_rows() == ["c,9", "a,2", "b,2"]


@pytest.mark.parametrize("calls", [0, -1])
def test_non_positive_record_is_rejected(calls):
    with pytest.raises(ValueError):
        UsageMeter().record("acme", calls)
