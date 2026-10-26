import pytest

from inventory.db import ConnectionPool, Store
from inventory.service import (
    DuplicateReservation,
    InsufficientStock,
    StockService,
    UnknownSku,
)


def _service(pool_size: int = 2) -> tuple[StockService, ConnectionPool]:
    pool = ConnectionPool(Store(), size=pool_size)
    service = StockService(pool)
    service.receive("MUG", 5)
    service.receive("TEE", 2)
    return service, pool


def test_rejected_reservation_returns_its_connection():
    service, pool = _service()
    with pytest.raises(InsufficientStock):
        service.reserve("o-1", [("MUG", 9)])
    assert pool.available == pool.size


def test_service_keeps_working_after_many_rejections():
    service, pool = _service()
    for i in range(5):
        with pytest.raises(InsufficientStock):
            service.reserve(f"o-{i}", [("TEE", 3)])
    with pytest.raises(UnknownSku):
        service.reserve("o-x", [("HAT", 1)])
    service.reserve("o-ok", [("MUG", 2), ("TEE", 2)])
    assert service.level("MUG").free == 3
    assert pool.available == pool.size


def test_reserve_is_all_or_nothing_and_cancel_restores_stock():
    service, _ = _service(pool_size=4)
    with pytest.raises(InsufficientStock):
        service.reserve("o-1", [("MUG", 2), ("TEE", 3)])
    assert service.level("MUG").free == 5
    service.reserve("o-2", [("MUG", 2), ("MUG", 1)])
    assert service.level("MUG").reserved == 3
    with pytest.raises(DuplicateReservation):
        service.reserve("o-2", [("TEE", 1)])
    assert service.cancel("o-2") is True
    assert service.cancel("o-2") is False
    assert service.level("MUG").free == 5
