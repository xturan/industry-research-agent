from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.sources.enums import CollectorType, ToolErrorCode, ToolStatus
from packages.sources.schemas import (
    DocumentSection,
    NormalizedDocument,
    RawDocument,
    SourceProfile,
    ToolError,
    ToolTrace,
)

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc  # noqa: UP017


def utc_now() -> datetime:
    return datetime.now(UTC)


class CollectorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DiscoveredItem(CollectorModel):
    item_id: str = Field(min_length=1, max_length=160)
    source_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=1, max_length=2048)
    summary: str | None = None
    published_at: datetime | None = None
    external_id: str | None = None
    list_position: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DetailPageContent(CollectorModel):
    item_id: str = Field(min_length=1, max_length=160)
    source_id: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=1, max_length=2048)
    title: str = Field(min_length=1, max_length=500)
    published_at: datetime | None = None
    html: str | None = None
    text_content: str | None = None
    summary: str | None = None
    sections: list[DocumentSection] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_content(self) -> DetailPageContent:
        if not self.sections and not (self.html or self.text_content):
            raise ValueError(
                "DetailPageContent requires html, text_content, or sections."
            )
        return self


class PdfArtifact(CollectorModel):
    artifact_id: str = Field(min_length=1, max_length=160)
    source_id: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=1, max_length=2048)
    item_id: str | None = None
    title: str | None = None
    filename: str | None = None
    media_type: str = Field(default="application/pdf", min_length=1, max_length=120)
    discovered_at: datetime = Field(default_factory=utc_now)
    attachment_ref: str | None = None
    checksum_sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PdfTextPage(CollectorModel):
    page_number: int = Field(ge=1)
    text: str = ""
    char_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def sync_char_count(self) -> PdfTextPage:
        actual = len(self.text)
        if self.char_count not in {0, actual}:
            raise ValueError("PdfTextPage.char_count must match len(text) when provided.")
        self.char_count = actual
        return self


class PdfTextDocument(CollectorModel):
    artifact_id: str = Field(min_length=1, max_length=160)
    source_id: str = Field(min_length=1, max_length=80)
    title: str | None = None
    url: str | None = None
    pages: list[PdfTextPage] = Field(default_factory=list)
    full_text: str = ""
    extracted_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def sync_text_fields(self) -> PdfTextDocument:
        if not self.full_text and self.pages:
            self.full_text = "\n\n".join(page.text for page in self.pages if page.text)
        self.metadata = {
            **self.metadata,
            "page_count": len(self.pages),
        }
        return self


class CollectorRequest(CollectorModel):
    source_id: str = Field(min_length=1, max_length=80)
    profile: SourceProfile
    entry_url: str | None = None
    detail_url: str | None = None
    item: DiscoveredItem | None = None
    detail_page: DetailPageContent | None = None
    raw_html: str | None = None
    raw_text: str | None = None
    pdf_artifacts: list[PdfArtifact] = Field(default_factory=list)
    pdf_text_document: PdfTextDocument | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: datetime = Field(default_factory=utc_now)
    trace_id: str | None = None

    @model_validator(mode="after")
    def validate_source_alignment(self) -> CollectorRequest:
        if self.profile.source_id != self.source_id:
            raise ValueError("CollectorRequest.source_id must match profile.source_id")
        return self


class CollectorResponse(CollectorModel):
    status: ToolStatus
    collector_name: str = Field(min_length=1, max_length=120)
    source_id: str = Field(min_length=1, max_length=80)
    items: list[DiscoveredItem] = Field(default_factory=list)
    detail_pages: list[DetailPageContent] = Field(default_factory=list)
    pdf_artifacts: list[PdfArtifact] = Field(default_factory=list)
    pdf_text_documents: list[PdfTextDocument] = Field(default_factory=list)
    raw_documents: list[RawDocument] = Field(default_factory=list)
    normalized_documents: list[NormalizedDocument] = Field(default_factory=list)
    errors: list[ToolError] = Field(default_factory=list)
    trace: ToolTrace | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseCollector(ABC):
    COLLECTOR_VERSION = "v1.0"

    @property
    @abstractmethod
    def collector_type(self) -> CollectorType:
        """Return the collector family type."""

    @property
    def collector_name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def discover_items(self, request: CollectorRequest) -> CollectorResponse:
        """Discover list/listing items from provided HTML or structured metadata."""

    @abstractmethod
    def fetch_detail(self, request: CollectorRequest) -> CollectorResponse:
        """Parse one detail page into structured detail content."""

    @abstractmethod
    def discover_attachments(self, request: CollectorRequest) -> CollectorResponse:
        """Discover file attachments such as PDF links from detail-page content."""

    @abstractmethod
    def normalize_to_documents(self, request: CollectorRequest) -> CollectorResponse:
        """Normalize collector outputs into auditable document contracts."""

    def not_implemented(
        self,
        request: CollectorRequest,
        *,
        operation: str,
        note: str,
    ) -> CollectorResponse:
        message = f"{self.collector_name}.{operation} is not implemented yet. {note}".strip()
        return CollectorResponse(
            status=ToolStatus.NOT_IMPLEMENTED,
            collector_name=self.collector_name,
            source_id=request.source_id,
            errors=[
                ToolError(
                    code=ToolErrorCode.NOT_IMPLEMENTED,
                    message=message,
                    retryable=False,
                )
            ],
            message=message,
            trace=self.build_trace(
                request=request,
                operation=operation,
                status=ToolStatus.NOT_IMPLEMENTED,
                warnings=[message],
            ),
        )

    def error_response(
        self,
        request: CollectorRequest,
        *,
        operation: str,
        message: str,
        code: ToolErrorCode = ToolErrorCode.INTERNAL_ERROR,
        retryable: bool = False,
        detail: dict[str, Any] | None = None,
    ) -> CollectorResponse:
        return CollectorResponse(
            status=ToolStatus.ERROR,
            collector_name=self.collector_name,
            source_id=request.source_id,
            errors=[
                ToolError(
                    code=code,
                    message=message,
                    retryable=retryable,
                    detail=detail or {},
                )
            ],
            message=message,
            trace=self.build_trace(
                request=request,
                operation=operation,
                status=ToolStatus.ERROR,
                retry_count=1 if retryable else 0,
                warnings=[message],
                metadata={"error_detail": detail or {}},
            ),
        )

    def build_trace(
        self,
        *,
        request: CollectorRequest,
        operation: str,
        status: ToolStatus,
        duration_ms: float | None = None,
        http_calls: int = 0,
        page_count: int = 0,
        item_count: int = 0,
        retry_count: int = 0,
        truncated: bool = False,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolTrace:
        return ToolTrace(
            tool_name=f"collector.{operation}",
            source_id=request.source_id,
            status=status,
            duration_ms=duration_ms,
            request_params={
                "collector_type": self.collector_type.value,
                "entry_url": request.entry_url,
                "detail_url": request.detail_url,
                **request.payload,
            },
            http_calls=max(http_calls, 0),
            page_count=max(page_count, 0),
            item_count=max(item_count, 0),
            evidence_count=0,
            retry_count=max(retry_count, 0),
            adapter_version=self.COLLECTOR_VERSION,
            truncated=truncated,
            warnings=warnings or [],
            notes=[
                "browser_fallback_todo",
                "ocr_todo",
                "site_specific_rules_todo",
            ],
            metadata=metadata or {},
        )

