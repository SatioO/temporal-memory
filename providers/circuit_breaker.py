import time
from typing import Optional
from math import floor, isfinite
from dataclasses import dataclass

from schema import CircuitBreakerSnapshot, CircuitBreakerState


@dataclass
class CircuitBreakerOptions:
    failure_threashold: Optional[int] = 3
    failure_window_ms: Optional[int] = 60000
    recovery_timeout_ms: Optional[int] = 30000


def positive_finite(val, fallback: int) -> int:
    try:
        val = int(val)
        return val if isfinite(val) and val > 0 else fallback
    except (TypeError, ValueError):
        return fallback


class CircuitBreaker:
    def __init__(self, opts: Optional[CircuitBreakerOptions] = None):
        opts = opts or CircuitBreakerOptions()

        self._state: CircuitBreakerState = CircuitBreakerState.CLOSED
        self._failures: int = 0
        self._last_failure_at: Optional[float] = None
        self._opened_at: Optional[float] = None

        self._failure_threshold = max(1, opts.failure_threashold)
        self._failure_window_ms = opts.failure_window_ms
        self._recovery_timeout_ms = opts.recovery_timeout_ms

    @property
    def failure_threshold(self) -> int:
        return self.failure_threshold

    @property
    def failure_window_ms(self) -> int:
        return self._failure_window_ms

    @property
    def recovery_timeout_ms(self) -> int:
        return self._recovery_timeout_ms

    @property
    def is_allowed(self) -> bool:
        if self._state == CircuitBreakerState.CLOSED:
            return True

        if self._state == CircuitBreakerState.OPEN:
            if (
                self.opened_at is not None and
                (time.time() * 1000 - self.opened_at) >= self.recovery_timeout_ms
            ):
                self._state = CircuitBreakerState.HALF_OPEN
                return True

            return False

        return True

    def record_success(self) -> None:
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._state = CircuitBreakerState.CLOSED
            self._failures = 0
            self._last_failure_at = None
            self._failure_window_ms = None

    def record_failures(self) -> None:
        now = time.time() * 1000

        if self._state == CircuitBreakerState.HALF_OPEN:
            self._state = CircuitBreakerState.OPEN
            self._opened_at = time.time()
            return

        if (
            self.last_failure_at is not None and
            (now - self.last_failure_at) > self.failure_window_ms
        ):
            self.failures = 0

        self.failures += 1
        self.last_failure_at = now

        if self.failures >= self.failure_threshold:
            self._state = CircuitBreakerState.OPEN
            self.opened_at = now

    def get_state(self) -> CircuitBreakerSnapshot:
        return CircuitBreakerSnapshot(
            state=self._state,
            failures=self._failures,
            last_failure_at=self._last_failure_at,
            opened_at=self._opened_at
        )
