import pytest

from webhooks.delivery import DeliveryError, Event, RetryPolicy, broadcast, deliver

EVENT = Event("evt_1", "invoice.paid", {"invoice": "inv_9", "amount": 1200})


class ScriptedTransport:
    """Answers each post with the next scripted outcome: an int status or an exception instance."""

    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def post(self, url, body, headers):
        self.calls.append((url, headers))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _deliver(outcomes, policy=RetryPolicy()):
    transport = ScriptedTransport(outcomes)
    sleeps: list[float] = []
    return transport, sleeps, lambda: deliver(transport, "https://hooks.example/a", EVENT, policy, sleeps.append)


def test_success_on_first_attempt_does_not_sleep():
    transport, sleeps, run = _deliver([204])
    assert run() == 1
    assert sleeps == []
    assert transport.calls[0][1]["Idempotency-Key"] == "evt_1"


def test_transient_failures_are_retried_with_exponential_backoff():
    _, sleeps, run = _deliver([503, ConnectionError("reset"), 429, 200])
    assert run() == 4
    assert sleeps == [0.5, 1.0, 2.0]


def test_backoff_is_capped():
    policy = RetryPolicy(attempts=7, base_delay=1.0, max_delay=5.0)
    _, sleeps, run = _deliver([500] * 6 + [200], policy)
    assert run() == 7
    assert sleeps == [1.0, 2.0, 4.0, 5.0, 5.0, 5.0]


def test_last_failure_is_reraised_after_all_attempts():
    transport, sleeps, run = _deliver([502, 502, 502, 504])
    with pytest.raises(DeliveryError) as exc:
        run()
    assert exc.value.status == 504
    assert len(transport.calls) == 4
    assert sleeps == [0.5, 1.0, 2.0]


def test_unreachable_endpoint_is_reraised_with_cause():
    _, _, run = _deliver([TimeoutError()], RetryPolicy(attempts=1))
    with pytest.raises(DeliveryError) as exc:
        run()
    assert exc.value.status is None
    assert isinstance(exc.value.__cause__, TimeoutError)


@pytest.mark.parametrize("status", [400, 401, 404, 410])
def test_permanent_failure_is_not_retried(status):
    transport, sleeps, run = _deliver([status, 200])
    with pytest.raises(DeliveryError) as exc:
        run()
    assert exc.value.status == status
    assert len(transport.calls) == 1
    assert sleeps == []


def test_default_policy_is_not_changed_by_use():
    _deliver([503, 200])[2]()
    assert RetryPolicy() == deliver.__defaults__[0]
    assert deliver.__defaults__[0].attempts == 4


def test_broadcast_collects_failures_and_continues():
    transport = ScriptedTransport([404, 200])
    failures = broadcast(transport, ["https://hooks.example/gone", "https://hooks.example/ok"], EVENT)
    assert list(failures) == ["https://hooks.example/gone"]
    assert [url for url, _ in transport.calls] == ["https://hooks.example/gone", "https://hooks.example/ok"]
