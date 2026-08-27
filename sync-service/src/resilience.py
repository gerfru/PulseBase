import time
from collections.abc import Callable
from typing import TypeVar

_T = TypeVar("_T")


class CircuitOpenError(RuntimeError):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._failures = 0
        self._opened_at: float | None = None

    def call(self, fn: Callable[[], _T]) -> _T:
        if self._opened_at is not None:
            if time.monotonic() - self._opened_at < self.recovery_seconds:
                raise CircuitOpenError("external provider circuit is open")
            self._opened_at = None
            self._failures = 0
        try:
            result = fn()
        except Exception:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()
            raise
        self._failures = 0
        return result
