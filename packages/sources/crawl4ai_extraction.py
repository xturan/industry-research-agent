from __future__ import annotations

import asyncio
import hashlib
import re
import sys
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.sources.enums import ToolErrorCode, ToolStatus
from packages.sources.schemas import (
    DocumentSection,
    NormalizedDocument,
    RawDocument,
    ToolError,
)

_HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+")
_DOWNLOAD_SUFFIXES = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar")


class Crawl4AIExtractionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Crawl4AIExtractionSettings(Crawl4AIExtractionModel):
    enabled: bool = True
    timeout_seconds: int = Field(default=45, ge=1, le=300)
    user_agent: str = Field(
        default="invest-agent/0.1 (source-intelligence)",
        min_length=1,
        max_length=200,
    )


class Crawl4AIExtractionInput(Crawl4AIExtractionModel):
    url: str = Field(min_length=1, max_length=2000)
    source_id: str = Field(default="crawl4ai_web", min_length=1, max_length=80)
    source_name_hint: str | None = Field(default=None, max_length=200)
    title_hint: str | None = Field(default=None, max_length=500)
    snippet_hint: str | None = None
    published_at_hint: str | None = None
    discovery_provider: str | None = Field(default=None, max_length=80)
    discovery_query: str | None = Field(default=None, max_length=800)
    discovery_score: float | None = Field(default=None, ge=0.0)
    task_family: str | None = Field(default=None, max_length=80)
    execution_bucket: str | None = Field(default=None, max_length=80)
    source_cluster: str | None = Field(default=None, max_length=120)
    include_domains: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        normalized = value.strip()
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute http(s) URL")
        return normalized

    @field_validator("source_id")
    @classmethod
    def normalize_source_id(cls, value: str) -> str:
        return value.strip()


class Crawl4AIExtractionRequest(Crawl4AIExtractionModel):
    inputs: list[Crawl4AIExtractionInput] = Field(min_length=1, max_length=50)
    allow_supplemental_direct_keep: bool = False


class SearchUrlCandidate(Crawl4AIExtractionInput):
    candidate_id: str | None = Field(default=None, max_length=120)


class Crawl4AIPageResult(Crawl4AIExtractionModel):
    url: str = Field(min_length=1, max_length=2000)
    success: bool = True
    final_url: str | None = None
    title: str | None = None
    markdown: str | None = None
    raw_text: str | None = None
    published_at: str | None = None
    outlinks: list[str] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class Crawl4AIExtractionResponse(Crawl4AIExtractionModel):
    status: ToolStatus
    documents: list[RawDocument] = Field(default_factory=list)
    normalized_documents: list[NormalizedDocument] = Field(default_factory=list)
    errors: list[ToolError] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceCrawl4AIError(Exception):
    def __init__(self, message: str, *, retryable: bool, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.detail = detail or {}


class Crawl4AIUnavailableError(SourceCrawl4AIError):
    def __init__(self, message: str, *, detail: dict[str, Any] | None = None):
        super().__init__(message, retryable=False, detail=detail)


RunnerResult = Crawl4AIPageResult | dict[str, Any] | Any
Runner = Callable[[list[str], int, str], list[RunnerResult]]


class Crawl4AIExtractionProvider(Protocol):
    def extract(self, request: Crawl4AIExtractionRequest) -> Crawl4AIExtractionResponse:
        """Extract URL pages into typed source documents."""


class Crawl4AIExtractionService:
    def __init__(
        self,
        *,
        settings: Crawl4AIExtractionSettings | None = None,
        runner: Runner | None = None,
    ) -> None:
        self.settings = settings or Crawl4AIExtractionSettings()
        self._runner = runner or _default_runner

    def extract(self, request: Crawl4AIExtractionRequest) -> Crawl4AIExtractionResponse:
        if not self.settings.enabled:
            return _unavailable_response(
                "Crawl4AI extraction is disabled in settings.",
                detail={"reason": "disabled", "provider": "crawl4ai"},
            )

        direct_keep_inputs = [
            item
            for item in request.inputs
            if item.execution_bucket == "direct_structured_sources"
        ]
        if direct_keep_inputs and not request.allow_supplemental_direct_keep:
            return Crawl4AIExtractionResponse(
                status=ToolStatus.ERROR,
                errors=[
                    ToolError(
                        code=ToolErrorCode.INVALID_REQUEST,
                        message=(
                            "Direct structured candidates cannot use Crawl4AI as "
                            "their primary extraction path."
                        ),
                        retryable=False,
                        detail={
                            "reason": "direct_structured_source_protected",
                            "urls": [item.url for item in direct_keep_inputs],
                            "source_clusters": [
                                item.source_cluster for item in direct_keep_inputs
                            ],
                        },
                    )
                ],
                metadata={
                    "provider": "crawl4ai",
                    "requested": len(request.inputs),
                    "succeeded": 0,
                    "failed": len(request.inputs),
                    "protected_direct_keep_count": len(direct_keep_inputs),
                },
            )

        urls = [item.url for item in request.inputs]
        try:
            runner_results = self._runner(
                urls,
                self.settings.timeout_seconds,
                self.settings.user_agent,
            )
        except Crawl4AIUnavailableError as exc:
            return _unavailable_response(
                str(exc),
                detail=exc.detail,
                requested_count=len(request.inputs),
            )
        except SourceCrawl4AIError as exc:
            return Crawl4AIExtractionResponse(
                status=ToolStatus.ERROR,
                errors=[
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=str(exc),
                        retryable=exc.retryable,
                        detail=exc.detail,
                    )
                ],
                metadata={
                    "provider": "crawl4ai",
                    "requested": len(request.inputs),
                    "succeeded": 0,
                    "failed": len(request.inputs),
                },
            )
        except Exception as exc:  # pragma: no cover - defensive boundary
            return Crawl4AIExtractionResponse(
                status=ToolStatus.ERROR,
                errors=[
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=f"Crawl4AI extraction failed: {exc}",
                        retryable=True,
                        detail={"provider": "crawl4ai"},
                    )
                ],
                metadata={
                    "provider": "crawl4ai",
                    "requested": len(request.inputs),
                    "succeeded": 0,
                    "failed": len(request.inputs),
                },
            )

        documents: list[RawDocument] = []
        normalized_documents: list[NormalizedDocument] = []
        errors: list[ToolError] = []
        failure_classes: dict[str, int] = {}
        for index, item in enumerate(request.inputs):
            if index >= len(runner_results):
                failure_class = "runtime_missing_result"
                _increment_failure_class(failure_classes, failure_class)
                errors.append(
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message="Crawl4AI did not return a result for URL.",
                        retryable=True,
                        detail={
                            "url": item.url,
                            "source_id": item.source_id,
                            "extraction_failure_class": failure_class,
                            "extraction_failure_stage": "runner",
                        },
                    )
                )
                continue

            page = _coerce_page_result(runner_results[index], requested_url=item.url)
            if not page.success:
                failure_class = _classify_extraction_failure(
                    item=item,
                    page=page,
                    stage="fetch",
                )
                _increment_failure_class(failure_classes, failure_class)
                errors.append(
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=_safe_error_message(
                            page.error_message,
                            default="Crawl4AI extraction failed.",
                        ),
                        retryable=True,
                        detail={
                            "url": item.url,
                            "final_url": page.final_url,
                            "source_id": item.source_id,
                            "error_message_truncated": bool(
                                page.error_message and len(page.error_message) > 900
                            ),
                            "extraction_failure_class": failure_class,
                            "extraction_failure_stage": "fetch",
                        },
                    )
                )
                continue

            raw_doc, normalized_doc = _to_documents(item, page)
            if raw_doc is None or normalized_doc is None:
                failure_class = _classify_extraction_failure(
                    item=item,
                    page=page,
                    stage="content",
                )
                _increment_failure_class(failure_classes, failure_class)
                errors.append(
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message="Crawl4AI returned no extractable content.",
                        retryable=False,
                        detail={
                            "url": item.url,
                            "final_url": page.final_url,
                            "source_id": item.source_id,
                            "extraction_failure_class": failure_class,
                            "extraction_failure_stage": "content",
                        },
                    )
                )
                continue

            documents.append(raw_doc)
            normalized_documents.append(normalized_doc)

        status = _status_from_counts(success_count=len(documents), error_count=len(errors))
        return Crawl4AIExtractionResponse(
            status=status,
            documents=documents,
            normalized_documents=normalized_documents,
            errors=errors,
            metadata={
                "provider": "crawl4ai",
                "requested": len(request.inputs),
                "succeeded": len(documents),
                "failed": len(errors),
                "failure_classes": failure_classes,
            },
        )


def _default_runner(urls: list[str], timeout_seconds: int, user_agent: str) -> list[RunnerResult]:
    _ensure_utf8_stdio_for_crawl4ai()

    try:
        from crawl4ai import AsyncWebCrawler  # type: ignore[import-untyped]
    except Exception as exc:  # pragma: no cover - dependency boundary
        raise Crawl4AIUnavailableError(
            "Crawl4AI dependency is unavailable. Install `crawl4ai` to enable extraction.",
            detail={"reason": "dependency_missing"},
        ) from exc

    async def _crawl() -> list[RunnerResult]:
        results: list[RunnerResult] = []
        async with AsyncWebCrawler() as crawler:
            for url in urls:
                try:
                    crawl_result = await crawler.arun(
                        url=url,
                        headers={"User-Agent": user_agent},
                        page_timeout=timeout_seconds * 1000,
                    )
                    results.append(crawl_result)
                except Exception as exc:  # pragma: no cover - network/runtime boundary
                    results.append(
                        {
                            "url": url,
                            "success": False,
                            "error_message": f"Crawl4AI runtime error: {exc}",
                        }
                    )
        return results

    try:
        return asyncio.run(_crawl())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_crawl())
        finally:
            loop.close()


def _ensure_utf8_stdio_for_crawl4ai() -> None:
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", "") or "").lower()
        if encoding in {"utf-8", "utf8"}:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, RuntimeError, ValueError):
            continue


def _coerce_page_result(result: RunnerResult, *, requested_url: str) -> Crawl4AIPageResult:
    if isinstance(result, Crawl4AIPageResult):
        return result
    if isinstance(result, dict):
        return Crawl4AIPageResult(
            url=str(result.get("url") or requested_url),
            success=bool(result.get("success", True)),
            final_url=_as_text(result.get("final_url")),
            title=_as_text(result.get("title")),
            markdown=_as_text(result.get("markdown") or result.get("content_markdown")),
            raw_text=_as_text(
                result.get("raw_text")
                or result.get("text")
                or result.get("content")
                or result.get("cleaned_text")
            ),
            published_at=_as_text(result.get("published_at") or result.get("published_date")),
            outlinks=_collect_urls(result.get("outlinks") or result.get("links")),
            attachments=_collect_urls(result.get("attachments") or result.get("media")),
            metadata=(
                result.get("metadata")
                if isinstance(result.get("metadata"), dict)
                else {}
            ),
            error_message=_as_text(result.get("error_message") or result.get("error")),
        )

    payload = _object_to_dict(result)
    return _coerce_page_result(payload, requested_url=requested_url)


def _object_to_dict(result: Any) -> dict[str, Any]:
    return {
        "url": _read_attr(result, "url"),
        "success": _read_attr(result, "success", True),
        "final_url": _read_attr(result, "final_url"),
        "title": _read_attr(result, "title"),
        "markdown": _read_attr(result, "markdown"),
        "raw_text": _read_attr(result, "raw_text")
        or _read_attr(result, "text")
        or _read_attr(result, "content"),
        "published_at": _read_attr(result, "published_at"),
        "outlinks": _read_attr(result, "outlinks") or _read_attr(result, "links"),
        "attachments": _read_attr(result, "attachments") or _read_attr(result, "media"),
        "metadata": _read_attr(result, "metadata", {}),
        "error_message": _read_attr(result, "error_message") or _read_attr(result, "error"),
    }


def _read_attr(obj: Any, name: str, default: Any = None) -> Any:
    if hasattr(obj, name):
        return getattr(obj, name)
    return default


def _to_documents(
    extraction_input: Crawl4AIExtractionInput,
    page: Crawl4AIPageResult,
) -> tuple[RawDocument | None, NormalizedDocument | None]:
    text = _best_text(page)
    if not text:
        return None, None

    document_id = _document_id(extraction_input.source_id, extraction_input.url)
    final_url = page.final_url or page.url or extraction_input.url
    title = page.title or _title_from_url(final_url)
    published_at = _parse_datetime(page.published_at or extraction_input.published_at_hint)
    snippet = _snippet(text)
    section_seed = page.markdown or text
    sections = _split_sections(section_seed, document_id=document_id)

    metadata = {
        "provider": "crawl4ai",
        "requested_url": extraction_input.url,
        "final_url": final_url,
        "attachments": page.attachments,
        "outlinks": page.outlinks,
        "crawl_metadata": page.metadata,
        "source_name_hint": extraction_input.source_name_hint,
        "title_hint": extraction_input.title_hint,
        "snippet_hint": extraction_input.snippet_hint,
        "published_at_hint": extraction_input.published_at_hint,
        "discovery_provider": extraction_input.discovery_provider,
        "discovery_query": extraction_input.discovery_query,
        "discovery_score": extraction_input.discovery_score,
        "task_family": extraction_input.task_family,
        "execution_bucket": extraction_input.execution_bucket,
        "source_cluster": extraction_input.source_cluster,
        "include_domains": extraction_input.include_domains,
        **extraction_input.metadata,
    }
    raw_doc = RawDocument(
        document_id=document_id,
        source_id=extraction_input.source_id,
        title=title,
        source_uri=final_url,
        published_at=published_at,
        raw_text=text,
        snippet=snippet,
        metadata=metadata,
    )
    normalized_doc = NormalizedDocument(
        document_id=document_id,
        source_id=extraction_input.source_id,
        title=title,
        published_at=published_at,
        summary=snippet,
        sections=sections,
        metadata={
            "provider": "crawl4ai",
            "requested_url": extraction_input.url,
            "final_url": final_url,
            "attachment_count": len(page.attachments),
            "outlink_count": len(page.outlinks),
            "crawl_metadata": page.metadata,
            "source_name_hint": extraction_input.source_name_hint,
            "discovery_provider": extraction_input.discovery_provider,
            "task_family": extraction_input.task_family,
            "execution_bucket": extraction_input.execution_bucket,
            "source_cluster": extraction_input.source_cluster,
        },
    )
    return raw_doc, normalized_doc


def _best_text(page: Crawl4AIPageResult) -> str:
    markdown = (page.markdown or "").strip()
    if markdown:
        return markdown
    return (page.raw_text or "").strip()


def _document_id(source_id: str, url: str) -> str:
    digest = hashlib.sha1(f"{source_id}|{url}".encode()).hexdigest()[:16]
    return f"crawl4ai_{digest}"


def _title_from_url(url: str) -> str:
    parsed = urlparse(url)
    tail = parsed.path.strip("/").split("/")[-1] if parsed.path else ""
    if tail:
        return tail[:500]
    return parsed.netloc[:500] or "untitled"


def _snippet(text: str, *, max_len: int = 280) -> str:
    compact = " ".join(text.split())
    return compact[:max_len]


def _split_sections(text: str, *, document_id: str) -> list[DocumentSection]:
    lines = text.splitlines()
    sections: list[DocumentSection] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if not body:
            return
        section_id = f"{document_id}_sec_{len(sections) + 1}"
        sections.append(
            DocumentSection(
                section_id=section_id,
                heading=current_heading,
                text=body,
                order_index=len(sections),
            )
        )

    for line in lines:
        if _HEADING_PATTERN.match(line):
            flush()
            current_lines = []
            current_heading = line.lstrip("#").strip() or None
            continue
        current_lines.append(line)
    flush()

    if sections:
        return sections

    fallback_text = text.strip()
    if not fallback_text:
        return []
    return [
        DocumentSection(
            section_id=f"{document_id}_sec_1",
            heading=None,
            text=fallback_text,
            order_index=0,
        )
    ]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    candidates = [normalized]
    if normalized.endswith("Z"):
        candidates.append(normalized[:-1] + "+00:00")
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _collect_urls(payload: Any) -> list[str]:
    collected: list[str] = []
    _collect_urls_recursive(payload, collected)
    deduped: list[str] = []
    seen: set[str] = set()
    for url in collected:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def _collect_urls_recursive(payload: Any, collected: list[str]) -> None:
    if payload is None:
        return
    if isinstance(payload, str):
        candidate = payload.strip()
        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            collected.append(candidate)
        return
    if isinstance(payload, dict):
        preferred_keys = ("url", "href", "src", "link")
        for key in preferred_keys:
            if key in payload:
                _collect_urls_recursive(payload.get(key), collected)
        for value in payload.values():
            _collect_urls_recursive(value, collected)
        return
    if isinstance(payload, list):
        for item in payload:
            _collect_urls_recursive(item, collected)


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_error_message(value: str | None, *, default: str) -> str:
    text = (value or default).strip()
    if len(text) <= 900:
        return text
    return f"{text[:897]}..."


def _classify_extraction_failure(
    *,
    item: Crawl4AIExtractionInput,
    page: Crawl4AIPageResult,
    stage: str,
) -> str:
    if _page_points_to_download(item=item, page=page):
        return "pdf_or_download"

    text = " ".join(
        value
        for value in (
            item.url,
            page.url,
            page.final_url or "",
            page.error_message or "",
            page.title or "",
        )
        if value
    ).lower()
    if any(token in text for token in ("ssl", "certificate", "cert verify")):
        return "ssl_certificate_error"
    if any(
        token in text
        for token in (
            "403",
            "forbidden",
            "access denied",
            "blocked",
            "captcha",
            "anti-bot",
            "antibot",
            "cloudflare",
        )
    ):
        return "anti_bot_or_forbidden"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if stage == "content":
        return "minimal_text_or_empty"
    return "runtime_error"


def _page_points_to_download(
    *,
    item: Crawl4AIExtractionInput,
    page: Crawl4AIPageResult,
) -> bool:
    urls = [item.url, page.url, page.final_url or "", *page.attachments]
    return any(_is_download_url(url) for url in urls if url)


def _is_download_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(_DOWNLOAD_SUFFIXES)


def _increment_failure_class(failure_classes: dict[str, int], failure_class: str) -> None:
    failure_classes[failure_class] = failure_classes.get(failure_class, 0) + 1


def _status_from_counts(*, success_count: int, error_count: int) -> ToolStatus:
    if success_count > 0 and error_count == 0:
        return ToolStatus.SUCCESS
    if success_count > 0 and error_count > 0:
        return ToolStatus.PARTIAL
    return ToolStatus.ERROR


def _unavailable_response(
    message: str,
    *,
    detail: dict[str, Any],
    requested_count: int = 0,
) -> Crawl4AIExtractionResponse:
    return Crawl4AIExtractionResponse(
        status=ToolStatus.UNSUPPORTED,
        errors=[
            ToolError(
                code=ToolErrorCode.UNSUPPORTED_OPERATION,
                message=message,
                retryable=False,
                detail=detail,
            )
        ],
        metadata={
            "provider": "crawl4ai",
            "requested": requested_count,
            "succeeded": 0,
            "failed": requested_count,
            "unavailable": True,
        },
    )


__all__ = [
    "Crawl4AIExtractionInput",
    "Crawl4AIExtractionProvider",
    "Crawl4AIExtractionRequest",
    "Crawl4AIExtractionResponse",
    "Crawl4AIExtractionService",
    "Crawl4AIExtractionSettings",
    "Crawl4AIPageResult",
    "Crawl4AIUnavailableError",
    "SearchUrlCandidate",
    "SourceCrawl4AIError",
]
