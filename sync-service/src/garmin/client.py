from collections.abc import Callable
import asyncio
from typing import TypeVar

from pulsebase_garmin.client import GarminClient as SharedGarminClient
from resilience import CircuitBreaker
from tenacity import Retrying, stop_after_attempt, wait_exponential

_T = TypeVar("_T")


class GarminClient(SharedGarminClient):
    def __init__(self, email: str, password: str, token_dir: str) -> None:
        super().__init__(email=email, password=password, token_dir=token_dir)
        self._breaker = CircuitBreaker()

    @property
    def breaker(self) -> CircuitBreaker:
        return self._breaker


def garmin_call(fn: Callable[[], _T], breaker: CircuitBreaker | None = None) -> _T:
    """Call a synchronous Garmin API function with up to 3 retries and exponential backoff."""
    for attempt in Retrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    ):
        with attempt:
            return breaker.call(fn) if breaker else fn()
    raise RuntimeError(
        "unreachable: tenacity reraises on exhaustion"
    )  # pragma: no cover


async def garmin_call_async(
    fn: Callable[[], _T], breaker: CircuitBreaker | None = None
) -> _T:
    return await asyncio.to_thread(garmin_call, fn, breaker)
