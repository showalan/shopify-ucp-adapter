"""Simple circuit breaker implementation."""

import time


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open."""


class CircuitBreaker:
    """Simple circuit breaker with failure threshold and reset timeout."""

    def __init__(self, failure_threshold: int = 3, reset_timeout_seconds: int = 30):
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.failure_count = 0
        self.opened_at: float | None = None

    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.time() - self.opened_at >= self.reset_timeout_seconds:
            self.opened_at = None
            self.failure_count = 0
            return False
        return True

    def record_success(self) -> None:
        self.failure_count = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.opened_at = time.time()

    def guard(self) -> None:
        if self.is_open():
            raise CircuitBreakerOpen()
