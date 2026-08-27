import pytest

from resilience import CircuitBreaker, CircuitOpenError


def test_opens_after_failure_threshold():
    breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=60)

    for _ in range(2):
        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("down")))

    with pytest.raises(CircuitOpenError):
        breaker.call(lambda: "unreachable")


def test_closes_after_recovery_window():
    breaker = CircuitBreaker(failure_threshold=1, recovery_seconds=0)

    with pytest.raises(ValueError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError("down")))

    assert breaker.call(lambda: "ok") == "ok"


def test_success_resets_failure_count():
    breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=60)

    with pytest.raises(ValueError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError("down")))
    assert breaker.call(lambda: "ok") == "ok"


def test_libre_client_accepts_breaker():
    from libre.client import LibreAuthError, get_recent_glucose

    breaker = CircuitBreaker(failure_threshold=2)
    with pytest.raises(LibreAuthError):
        get_recent_glucose(object(), breaker=breaker)  # type: ignore[arg-type]
