from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from packages.sources.resilience import RetryExecutionError, run_with_retry


@dataclass(slots=True)
class HttpCallTrace:
    url: str
    status_code: int | None
    attempts: int
    retry_count: int
    retryable_failures: int
    non_retryable_failures: int
    latency_ms: float
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status_code": self.status_code,
            "attempts": self.attempts,
            "retry_count": self.retry_count,
            "retryable_failures": self.retryable_failures,
            "non_retryable_failures": self.non_retryable_failures,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


class SourceHttpError(Exception):
    def __init__(self, message: str, *, retryable: bool, trace: HttpCallTrace) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.trace = trace


def fetch_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
    data, _trace = fetch_json_with_trace(
        url,
        headers=headers,
        timeout=timeout,
        max_retries=0,
        backoff_seconds=0.0,
    )
    return data


def fetch_json_with_trace(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
    max_retries: int = 2,
    backoff_seconds: float = 0.3,
) -> tuple[Any, HttpCallTrace]:
    request_headers = headers or {}

    def _request_once() -> tuple[bytes, int]:
        request = Request(url, headers=request_headers)
        with urlopen(request, timeout=timeout) as response:  # nosec: B310
            payload = response.read()
            status_code = int(response.getcode() or 200)
        return payload, status_code

    try:
        (payload, status_code), retry_meta = run_with_retry(
            _request_once,
            max_retries=max(max_retries, 0),
            backoff_seconds=max(backoff_seconds, 0.0),
        )
        return (
            json.loads(payload.decode("utf-8")),
            HttpCallTrace(
                url=url,
                status_code=status_code,
                attempts=retry_meta.attempts,
                retry_count=retry_meta.retry_count,
                retryable_failures=retry_meta.retryable_failures,
                non_retryable_failures=retry_meta.non_retryable_failures,
                latency_ms=retry_meta.duration_ms,
                error=retry_meta.last_error,
            ),
        )
    except RetryExecutionError as exc:
        status_code = None
        if isinstance(exc.cause, HTTPError):
            status_code = int(exc.cause.code)
        trace = HttpCallTrace(
            url=url,
            status_code=status_code,
            attempts=exc.metadata.attempts,
            retry_count=exc.metadata.retry_count,
            retryable_failures=exc.metadata.retryable_failures,
            non_retryable_failures=exc.metadata.non_retryable_failures,
            latency_ms=exc.metadata.duration_ms,
            error=exc.metadata.last_error,
        )
        raise SourceHttpError(
            f"HTTP fetch failed: {exc.cause}",
            retryable=exc.retryable,
            trace=trace,
        ) from exc.cause
