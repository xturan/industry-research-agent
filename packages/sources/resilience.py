from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar
from urllib.error import HTTPError, URLError

T = TypeVar("T")


@dataclass(slots=True)
class RetryMetadata:
    attempts: int
    retry_count: int
    retryable_failures: int
    non_retryable_failures: int
    total_sleep_ms: float
    duration_ms: float
    last_error: str | None


class RetryExecutionError(Exception):
    def __init__(
        self,
        message: str,
        *,
        cause: Exception,
        retryable: bool,
        metadata: RetryMetadata,
    ) -> None:
        super().__init__(message)
        self.cause = cause
        self.retryable = retryable
        self.metadata = metadata


def is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, URLError):
        return True
    if isinstance(exc, HTTPError):
        status_code = getattr(exc, "code", None)
        if status_code in {408, 409, 425, 429}:
            return True
        if isinstance(status_code, int) and 500 <= status_code <= 599:
            return True
    return False


def run_with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 2,
    backoff_seconds: float = 0.3,
    is_retryable: Callable[[Exception], bool] | None = None,
) -> tuple[T, RetryMetadata]:
    retryable_classifier = is_retryable or is_retryable_exception
    started = time.perf_counter()
    attempts = 0
    retry_count = 0
    retryable_failures = 0
    non_retryable_failures = 0
    total_sleep_ms = 0.0
    last_error: str | None = None
    last_exc: Exception | None = None

    while attempts <= max_retries:
        attempts += 1
        try:
            result = fn()
            duration_ms = (time.perf_counter() - started) * 1000.0
            return result, RetryMetadata(
                attempts=attempts,
                retry_count=retry_count,
                retryable_failures=retryable_failures,
                non_retryable_failures=non_retryable_failures,
                total_sleep_ms=round(total_sleep_ms, 3),
                duration_ms=round(duration_ms, 3),
                last_error=last_error,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            last_error = f"{type(exc).__name__}: {exc}"
            retryable = retryable_classifier(exc)
            if retryable:
                retryable_failures += 1
            else:
                non_retryable_failures += 1

            if not retryable or attempts > max_retries:
                break

            retry_count += 1
            delay = min(backoff_seconds * float(retry_count), 2.0)
            total_sleep_ms += delay * 1000.0
            time.sleep(delay)

    duration_ms = (time.perf_counter() - started) * 1000.0
    metadata = RetryMetadata(
        attempts=attempts,
        retry_count=retry_count,
        retryable_failures=retryable_failures,
        non_retryable_failures=non_retryable_failures,
        total_sleep_ms=round(total_sleep_ms, 3),
        duration_ms=round(duration_ms, 3),
        last_error=last_error,
    )
    if last_exc is None:
        raise RuntimeError("run_with_retry ended without result or error")
    raise RetryExecutionError(
        "Retry execution failed.",
        cause=last_exc,
        retryable=retryable_classifier(last_exc),
        metadata=metadata,
    )

