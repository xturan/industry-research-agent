from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from packages.sources.resilience import RetryExecutionError, run_with_retry

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc  # noqa: UP017


@dataclass(slots=True)
class LiveHtmlFetchResult:
    url: str
    final_url: str
    status_code: int | None
    content_type: str | None
    encoding: str
    text: str
    attempts: int
    retry_count: int
    latency_ms: float
    warnings: list[str] = field(default_factory=list)
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "encoding": self.encoding,
            "attempts": self.attempts,
            "retry_count": self.retry_count,
            "latency_ms": self.latency_ms,
            "warnings": self.warnings,
            "retrieved_at": self.retrieved_at.isoformat(),
        }


class LiveHtmlFetchError(Exception):
    def __init__(
        self,
        message: str,
        *,
        url: str,
        retryable: bool,
        status_code: int | None,
        attempts: int,
        retry_count: int,
        latency_ms: float,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.retryable = retryable
        self.status_code = status_code
        self.attempts = attempts
        self.retry_count = retry_count
        self.latency_ms = latency_ms
        self.detail = detail or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "retryable": self.retryable,
            "status_code": self.status_code,
            "attempts": self.attempts,
            "retry_count": self.retry_count,
            "latency_ms": self.latency_ms,
            "detail": self.detail,
        }


class LiveHtmlFetchService:
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; InvestAgent/0.1; "
            "+https://example.local/invest-agent)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def __init__(
        self,
        *,
        timeout_seconds: float = 12.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.3,
    ) -> None:
        self.timeout_seconds = max(timeout_seconds, 0.1)
        self.max_retries = max(max_retries, 0)
        self.backoff_seconds = max(backoff_seconds, 0.0)

    def fetch_html(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        encoding_hints: list[str] | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        backoff_seconds: float | None = None,
    ) -> LiveHtmlFetchResult:
        request_headers = {**self.DEFAULT_HEADERS, **(headers or {})}
        timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        retries = max_retries if max_retries is not None else self.max_retries
        backoff = backoff_seconds if backoff_seconds is not None else self.backoff_seconds

        def _fetch_once() -> tuple[bytes, int, str | None, str]:
            return self._request_once(
                url,
                headers=request_headers,
                timeout_seconds=timeout,
            )

        try:
            (
                payload,
                status_code,
                content_type,
                final_url,
            ), retry_meta = run_with_retry(
                _fetch_once,
                max_retries=retries,
                backoff_seconds=backoff,
            )
        except RetryExecutionError as exc:
            status_code = None
            if isinstance(exc.cause, HTTPError):
                status_code = int(exc.cause.code)
            raise LiveHtmlFetchError(
                str(exc.cause),
                url=url,
                retryable=exc.retryable,
                status_code=status_code,
                attempts=exc.metadata.attempts,
                retry_count=exc.metadata.retry_count,
                latency_ms=exc.metadata.duration_ms,
                detail={
                    "last_error": exc.metadata.last_error,
                    "retryable_failures": exc.metadata.retryable_failures,
                    "non_retryable_failures": exc.metadata.non_retryable_failures,
                },
            ) from exc.cause

        parsed_encoding = self._resolve_encoding(
            payload,
            content_type=content_type,
            encoding_hints=encoding_hints or [],
        )
        text = payload.decode(parsed_encoding, errors="replace")
        warnings: list[str] = []
        if content_type and "html" not in content_type.lower():
            warnings.append(f"unexpected_content_type:{content_type}")
        parsed_url = urlparse(final_url)
        if parsed_url.scheme not in {"http", "https"}:
            warnings.append(f"unexpected_scheme:{parsed_url.scheme or 'unknown'}")
        return LiveHtmlFetchResult(
            url=url,
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            encoding=parsed_encoding,
            text=text,
            attempts=retry_meta.attempts,
            retry_count=retry_meta.retry_count,
            latency_ms=retry_meta.duration_ms,
            warnings=warnings,
        )

    def _request_once(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> tuple[bytes, int, str | None, str]:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=timeout_seconds) as response:  # nosec: B310
            payload = response.read()
            status_code = int(response.getcode() or 200)
            content_type = response.headers.get("Content-Type")
            final_url = response.geturl()
        return payload, status_code, content_type, final_url

    def _resolve_encoding(
        self,
        payload: bytes,
        *,
        content_type: str | None,
        encoding_hints: list[str],
    ) -> str:
        candidates: list[str] = []
        if content_type:
            lower = content_type.lower()
            marker = "charset="
            if marker in lower:
                charset = lower.split(marker, 1)[1].split(";", 1)[0].strip()
                if charset:
                    candidates.append(charset)
        candidates.extend(encoding_hints)
        candidates.extend(["utf-8", "gb18030", "gbk", "latin-1"])
        tried: set[str] = set()
        for candidate in candidates:
            normalized = candidate.strip().lower()
            if not normalized or normalized in tried:
                continue
            tried.add(normalized)
            try:
                payload.decode(normalized)
                return normalized
            except UnicodeDecodeError:
                continue
        return "utf-8"


def build_inline_fetch_result(
    *,
    url: str,
    text: str,
    warning: str,
) -> LiveHtmlFetchResult:
    return LiveHtmlFetchResult(
        url=url,
        final_url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        encoding="utf-8",
        text=text,
        attempts=1,
        retry_count=0,
        latency_ms=0.0,
        warnings=[warning],
    )


def is_retryable_fetch_exception(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, URLError):
        return True
    if isinstance(exc, HTTPError):
        code = int(exc.code or 0)
        return code >= 500 or code in {408, 429}
    return False

