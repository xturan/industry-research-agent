from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from packages.core.config import get_settings
from packages.sources.resilience import RetryExecutionError, run_with_retry

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc  # noqa: UP017


@dataclass(slots=True)
class LivePdfDownloadResult:
    url: str
    final_url: str
    status_code: int | None
    content_type: str | None
    file_path: str
    bytes_size: int
    sha256: str
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
            "file_path": self.file_path,
            "bytes_size": self.bytes_size,
            "sha256": self.sha256,
            "attempts": self.attempts,
            "retry_count": self.retry_count,
            "latency_ms": self.latency_ms,
            "warnings": self.warnings,
            "retrieved_at": self.retrieved_at.isoformat(),
        }


class LivePdfDownloadError(Exception):
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


class LivePdfDownloadService:
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; InvestAgent/0.1; "
            "+https://example.local/invest-agent)"
        ),
        "Accept": "application/pdf,*/*;q=0.8",
    }

    def __init__(
        self,
        *,
        storage_dir: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        backoff_seconds: float | None = None,
        max_bytes: int = 25 * 1024 * 1024,
    ) -> None:
        settings = get_settings()
        self.storage_dir = Path(storage_dir or Path(settings.raw_storage_dir) / "source_pdfs")
        self.timeout_seconds = float(
            timeout_seconds if timeout_seconds is not None else settings.source_http_timeout_seconds
        )
        self.max_retries = int(
            max_retries if max_retries is not None else settings.source_http_retry_count
        )
        self.backoff_seconds = float(
            backoff_seconds if backoff_seconds is not None else settings.source_http_backoff_seconds
        )
        self.max_bytes = max(max_bytes, 1024 * 1024)

    def download_pdf(
        self,
        url: str,
        *,
        source_id: str,
        attachment_ref: str | None = None,
        headers: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        backoff_seconds: float | None = None,
        max_bytes: int | None = None,
    ) -> LivePdfDownloadResult:
        request_headers = {**self.DEFAULT_HEADERS, **(headers or {})}
        timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        retries = max_retries if max_retries is not None else self.max_retries
        backoff = backoff_seconds if backoff_seconds is not None else self.backoff_seconds
        max_allowed = max_bytes if max_bytes is not None else self.max_bytes

        def _download_once() -> tuple[bytes, int, str | None, str]:
            return self._request_once(url, headers=request_headers, timeout_seconds=timeout)

        try:
            (
                payload,
                status_code,
                content_type,
                final_url,
            ), retry_meta = run_with_retry(
                _download_once,
                max_retries=retries,
                backoff_seconds=backoff,
            )
        except RetryExecutionError as exc:
            status_code = None
            if isinstance(exc.cause, HTTPError):
                status_code = int(exc.cause.code)
            raise LivePdfDownloadError(
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

        if len(payload) > max_allowed:
            raise LivePdfDownloadError(
                "Downloaded PDF exceeds configured max_bytes limit.",
                url=url,
                retryable=False,
                status_code=status_code,
                attempts=retry_meta.attempts,
                retry_count=retry_meta.retry_count,
                latency_ms=retry_meta.duration_ms,
                detail={
                    "bytes_size": len(payload),
                    "max_bytes": max_allowed,
                },
            )

        digest = hashlib.sha256(payload).hexdigest()
        file_path = self._persist_payload(
            payload=payload,
            source_id=source_id,
            sha256=digest,
            final_url=final_url,
            attachment_ref=attachment_ref,
        )

        warnings: list[str] = []
        content_type_lower = (content_type or "").lower()
        if content_type and "pdf" not in content_type_lower:
            warnings.append(f"unexpected_content_type:{content_type}")
        if not payload.startswith(b"%PDF"):
            warnings.append("missing_pdf_magic_header")

        return LivePdfDownloadResult(
            url=url,
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            file_path=str(file_path),
            bytes_size=len(payload),
            sha256=digest,
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

    def _persist_payload(
        self,
        *,
        payload: bytes,
        source_id: str,
        sha256: str,
        final_url: str,
        attachment_ref: str | None,
    ) -> Path:
        source_dir = self.storage_dir / source_id
        source_dir.mkdir(parents=True, exist_ok=True)
        filename = self._build_filename(
            sha256=sha256,
            final_url=final_url,
            attachment_ref=attachment_ref,
        )
        path = source_dir / filename
        path.write_bytes(payload)
        return path

    def _build_filename(
        self,
        *,
        sha256: str,
        final_url: str,
        attachment_ref: str | None,
    ) -> str:
        preferred = attachment_ref or urlparse(final_url).path.split("/")[-1]
        if not preferred:
            preferred = "attachment.pdf"
        preferred = re.sub(r"[^A-Za-z0-9._-]+", "_", preferred)
        if not preferred.lower().endswith(".pdf"):
            preferred = f"{preferred}.pdf"
        return f"{sha256[:12]}_{preferred}"
