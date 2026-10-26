import pytest

from ratelimit.limiter import FixedWindowLimiter, TokenBucketLimiter
from ratelimit.middleware import Request, Response, build_limiter, rate_limited


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_burst_then_steady_refill_rate():
    clock = FakeClock()
    limiter = TokenBucketLimiter(capacity=10, refill_rate=1.0, clock=clock)
    assert all(limiter.check("a").allowed for _ in range(10))
    assert not limiter.check("a").allowed
    clock.now += 3.0
    assert [limiter.check("a").allowed for _ in range(4)] == [True, True, True, False]


def test_denied_polling_does_not_speed_up_refill():
    clock = FakeClock()
    limiter = TokenBucketLimiter(capacity=10, refill_rate=1.0, clock=clock)
    for _ in range(10):
        limiter.check("a")
    allowed = 0
    for _ in range(80):
        clock.now += 0.125
        allowed += limiter.check("a").allowed
    assert allowed == 10


def test_denied_decision_reports_time_until_enough_tokens():
    clock = FakeClock()
    limiter = TokenBucketLimiter(capacity=5, refill_rate=0.5, clock=clock)
    assert limiter.check("a", cost=5).allowed
    clock.now += 1.0
    denied = limiter.check("a", cost=5)
    assert not denied.allowed
    assert denied.retry_after == pytest.approx(9.0)
    clock.now += 1.0
    assert limiter.check("a", cost=5).retry_after == pytest.approx(8.0)


def test_clients_have_separate_buckets():
    clock = FakeClock()
    limiter = TokenBucketLimiter(capacity=2, refill_rate=1.0, clock=clock)
    assert limiter.check("a").allowed and limiter.check("a").allowed
    assert not limiter.check("a").allowed
    assert limiter.check("b").allowed


def test_build_limiter_strategies():
    clock = FakeClock()
    assert isinstance(build_limiter({"limit": 5, "window_seconds": 60}, clock), FixedWindowLimiter)
    bucket = build_limiter({"strategy": "token_bucket", "limit": 60, "window_seconds": 60, "burst": 3}, clock)
    assert isinstance(bucket, TokenBucketLimiter)
    assert [bucket.check("a").allowed for _ in range(4)] == [True, True, True, False]
    with pytest.raises(ValueError):
        build_limiter({"strategy": "sliding", "limit": 1, "window_seconds": 1}, clock)


def test_middleware_with_token_bucket():
    clock = FakeClock()
    limiter = build_limiter({"strategy": "token_bucket", "limit": 1, "window_seconds": 2, "burst": 1}, clock)
    handler = rate_limited(lambda request: Response(200, {"ok": True}), limiter)
    request = Request("/v1/items", {"x-api-key": "k1"})
    assert handler(request).status == 200
    throttled = handler(request)
    assert throttled.status == 429
    assert throttled.headers["Retry-After"] == "2"
    clock.now += 1.5
    assert handler(request).status == 429
    clock.now += 0.6
    assert handler(request).status == 200
