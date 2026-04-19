from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.sources.enums import (
    AccessMethod,
    CollectorType,
    EvidenceMode,
    PaginationMode,
    QueryType,
    SourceCategory,
    ToolErrorCode,
    ToolStatus,
    TrustTier,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TimeRange(StrictModel):
    start_at: datetime | None = None
    end_at: datetime | None = None

    @model_validator(mode="after")
    def validate_order(self) -> TimeRange:
        if self.start_at and self.end_at and self.start_at > self.end_at:
            raise ValueError("TimeRange.start_at must be <= TimeRange.end_at")
        return self


class UserProvidedSource(StrictModel):
    source_uri: str | None = None
    file_ref: str | None = None
    inline_text: str | None = None
    title: str | None = None
    published_at: datetime | None = None
    language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload(self) -> UserProvidedSource:
        if not (self.source_uri or self.file_ref or self.inline_text):
            raise ValueError("UserProvidedSource requires source_uri, file_ref, or inline_text")
        return self


class QueryContext(StrictModel):
    query: str = Field(min_length=1, max_length=800)
    time_range: TimeRange | None = None
    industry: str | None = None
    tickers: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    user_provided_sources: list[UserProvidedSource] = Field(default_factory=list)
    max_sources: int = Field(default=5, ge=1, le=50)
    max_documents_per_source: int = Field(default=5, ge=1, le=100)
    max_evidence_per_source: int = Field(default=3, ge=1, le=100)
    evidence_mode: EvidenceMode = EvidenceMode.EXTRACTED_EVIDENCE
    metadata: dict[str, Any] = Field(default_factory=dict)


class RateLimitHint(StrictModel):
    requests_per_minute: int | None = Field(default=None, ge=1)
    burst_limit: int | None = Field(default=None, ge=1)
    cooldown_seconds: int | None = Field(default=None, ge=0)
    notes: str | None = None


class SourceAccess(StrictModel):
    access_method: AccessMethod
    auth_required: bool = False
    auth_type: str | None = None
    base_url: str | None = None
    terms_url: str | None = None


class SourceCapabilities(StrictModel):
    supports_search: bool = True
    supports_document_detail: bool = False
    supports_evidence_extraction: bool = False
    supports_time_filter: bool = False
    supports_keyword_filter: bool = True
    supports_bulk: bool = False


class SourceProfile(StrictModel):
    source_id: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    category: SourceCategory
    trust_tier: TrustTier
    enabled: bool = True
    description: str | None = None
    access: SourceAccess
    capabilities: SourceCapabilities
    rate_limit_hint: RateLimitHint | None = None
    priority_hint: int = Field(default=50, ge=1, le=100)
    tags: list[str] = Field(default_factory=list)
    profile_family: str | None = None
    collector_type: CollectorType | None = None
    entry_urls: list[str] = Field(default_factory=list)
    selectors: dict[str, str] = Field(default_factory=dict)
    detail_required: bool = False
    pdf_expected: bool = False
    pagination_mode: PaginationMode | None = None
    language: str | None = None
    encoding_hints: list[str] = Field(default_factory=list)
    collector_config: dict[str, Any] = Field(default_factory=dict)
    collector_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_collector_profile(self) -> SourceProfile:
        if self.collector_type is None:
            return self
        if not self.entry_urls:
            raise ValueError("Collector-backed SourceProfile requires at least one entry_url")
        if self.pagination_mode is None:
            self.pagination_mode = PaginationMode.NONE
        if not self.language:
            self.language = "zh-CN"
        return self


class RawDocument(StrictModel):
    document_id: str = Field(min_length=1, max_length=120)
    source_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=500)
    source_uri: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    language: str | None = None
    raw_text: str | None = None
    snippet: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentSection(StrictModel):
    section_id: str = Field(min_length=1, max_length=120)
    heading: str | None = None
    text: str = Field(min_length=1)
    order_index: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractedEntity(StrictModel):
    entity_type: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=500)
    normalized_value: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedDocument(StrictModel):
    document_id: str = Field(min_length=1, max_length=120)
    source_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=500)
    language: str | None = None
    published_at: datetime | None = None
    summary: str | None = None
    sections: list[DocumentSection] = Field(default_factory=list)
    entities: list[ExtractedEntity] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CitationLocator(StrictModel):
    document_id: str = Field(min_length=1, max_length=120)
    section_id: str | None = None
    chunk_index: int | None = Field(default=None, ge=0)
    page_number: int | None = Field(default=None, ge=1)
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)
    external_ref: str | None = None

    @model_validator(mode="after")
    def validate_char_range(self) -> CitationLocator:
        if (
            self.start_char is not None
            and self.end_char is not None
            and self.end_char < self.start_char
        ):
            raise ValueError("CitationLocator.end_char must be >= CitationLocator.start_char")
        return self


class Citation(StrictModel):
    citation_id: str = Field(min_length=1, max_length=120)
    source_id: str = Field(min_length=1, max_length=80)
    document_id: str = Field(min_length=1, max_length=120)
    locator: CitationLocator
    quote_text: str | None = None
    source_uri: str | None = None
    published_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceItem(StrictModel):
    evidence_id: str = Field(min_length=1, max_length=120)
    source_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=500)
    summary: str | None = None
    support_text: str | None = None
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    citation: Citation
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceSummaryItem(StrictModel):
    source_id: str = Field(min_length=1, max_length=80)
    source_name: str = Field(min_length=1, max_length=120)
    document_count: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    notes: list[str] = Field(default_factory=list)


class EvidenceBundle(StrictModel):
    bundle_id: str = Field(default_factory=lambda: f"src_bundle_{uuid4().hex[:12]}")
    query: str = Field(min_length=1, max_length=800)
    items: list[EvidenceItem] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    source_summary: list[SourceSummaryItem] = Field(default_factory=list)
    sources: list[SourceSummaryItem] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def sync_compat_fields(self) -> EvidenceBundle:
        if self.items and not self.evidence_items:
            self.evidence_items = self.items
        if self.evidence_items and not self.items:
            self.items = self.evidence_items
        if self.source_summary and not self.sources:
            self.sources = self.source_summary
        if self.sources and not self.source_summary:
            self.source_summary = self.sources
        return self


class SourceQualitySummary(StrictModel):
    sources_attempted: int = Field(default=0, ge=0)
    sources_succeeded: int = Field(default=0, ge=0)
    sources_failed: int = Field(default=0, ge=0)
    source_error_breakdown: dict[str, int] = Field(default_factory=dict)
    citation_completeness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_density: float = Field(default=0.0, ge=0.0)
    truncated_sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RoutingRecommendation(StrictModel):
    source_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=400)
    priority: int = Field(default=50, ge=1, le=100)
    query_type: QueryType | None = None
    final_score: float = Field(default=0.0)
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    selected_via: str = Field(default="routing_logic")
    matched_terms: list[str] = Field(default_factory=list)


class SourcePerformanceItem(StrictModel):
    source_id: str = Field(min_length=1, max_length=80)
    attempt_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    partial_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    no_result_count: int = Field(default=0, ge=0)
    avg_latency_ms: float = Field(default=0.0, ge=0.0)
    avg_evidence_density: float = Field(default=0.0, ge=0.0)
    avg_citation_completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    last_seen_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourcePerformanceSummary(StrictModel):
    lookback_days: int = Field(default=30, ge=1, le=3650)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    items: list[SourcePerformanceItem] = Field(default_factory=list)


class ToolTrace(StrictModel):
    tool_name: str = Field(min_length=1, max_length=120)
    source_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    status: ToolStatus
    duration_ms: float | None = Field(default=None, ge=0.0)
    request_params: dict[str, Any] = Field(default_factory=dict)
    http_calls: int = Field(default=0, ge=0)
    page_count: int = Field(default=0, ge=0)
    item_count: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    adapter_version: str | None = None
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolError(StrictModel):
    code: ToolErrorCode
    message: str = Field(min_length=1, max_length=1000)
    retryable: bool = False
    detail: dict[str, Any] = Field(default_factory=dict)


class ToolRequest(StrictModel):
    tool_name: str = Field(min_length=1, max_length=120)
    query_context: QueryContext
    source_id: str | None = None
    document_id: str | None = None
    limit: int | None = Field(default=None, ge=1, le=500)
    page: int | None = Field(default=None, ge=1, le=10000)
    offset: int | None = Field(default=None, ge=0, le=1000000)
    max_evidence_per_source: int | None = Field(default=None, ge=1, le=500)
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence_mode: EvidenceMode | None = None
    trace_id: str | None = None

    @field_validator("source_id")
    @classmethod
    def normalize_source_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def with_source(self, source_id: str) -> ToolRequest:
        return self.model_copy(update={"source_id": source_id})


class ToolResponse(StrictModel):
    status: ToolStatus
    tool_name: str = Field(min_length=1, max_length=120)
    source_id: str | None = None
    route_recommendations: list[RoutingRecommendation] = Field(default_factory=list)
    documents: list[RawDocument] = Field(default_factory=list)
    normalized_documents: list[NormalizedDocument] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    bundle: EvidenceBundle | None = None
    errors: list[ToolError] = Field(default_factory=list)
    trace: ToolTrace | None = None
    traces: list[ToolTrace] = Field(default_factory=list)
    source_quality_summary: SourceQualitySummary | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
