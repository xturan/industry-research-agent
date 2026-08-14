from __future__ import annotations

from packages.sources.adapters import UserInputAdapter, WorldBankAdapter
from packages.sources.adapters.base import BaseSourceAdapter
from packages.sources.citation import normalize_evidence_item
from packages.sources.enums import (
    AccessMethod,
    SourceCategory,
    ToolErrorCode,
    ToolStatus,
    TrustTier,
)
from packages.sources.registry import SourceRegistry
from packages.sources.resilience import run_with_retry
from packages.sources.schemas import (
    Citation,
    CitationLocator,
    EvidenceItem,
    QueryContext,
    RoutingRecommendation,
    SourceAccess,
    SourceCapabilities,
    SourceProfile,
    ToolRequest,
    UserProvidedSource,
)
from packages.sources.tools import build_source_tool_registry


class _StaticRouter:
    def route(self, _query_context: QueryContext) -> list[RoutingRecommendation]:
        return [
            RoutingRecommendation(
                source_id="broken_api",
                reason="inject-failure",
                priority=100,
            ),
            RoutingRecommendation(
                source_id="user_input",
                reason="inject-success",
                priority=90,
            ),
        ]


class _BrokenAdapter(BaseSourceAdapter):
    def get_profile(self) -> SourceProfile:
        return SourceProfile(
            source_id="broken_api",
            display_name="Broken API",
            category=SourceCategory.MACRO_DATA,
            trust_tier=TrustTier.SECONDARY_INSTITUTIONAL,
            enabled=True,
            description="Synthetic failure adapter for tests.",
            access=SourceAccess(access_method=AccessMethod.API, auth_required=False),
            capabilities=SourceCapabilities(
                supports_search=True,
                supports_document_detail=False,
                supports_evidence_extraction=False,
                supports_time_filter=False,
                supports_keyword_filter=True,
                supports_bulk=False,
            ),
        )

    def search_documents(self, request: ToolRequest):
        return self.error_response(
            request,
            code=ToolErrorCode.INTERNAL_ERROR,
            message="broken_api simulated upstream failure",
            retryable=True,
        )

    def fetch_document_detail(self, request: ToolRequest):
        return self.not_implemented(request, "fetch_document_detail")

    def extract_evidence_items(self, request: ToolRequest):
        return self.not_implemented(request, "extract_evidence_items")


def test_world_bank_search_limit_and_truncation(monkeypatch) -> None:
    adapter = WorldBankAdapter()

    def _fake_fetch_json(url: str):  # noqa: ANN001
        if "/v2/indicator/" in url and "/country/" not in url:
            return [{}, [{"id": "NY.GDP.MKTP.CD", "name": "GDP (current US$)"}]]
        raise AssertionError(url)

    monkeypatch.setattr(adapter, "_fetch_json", _fake_fetch_json)
    request = ToolRequest(
        tool_name="search_source_documents",
        query_context=QueryContext(
            query="gdp trend",
            countries=["USA", "CHN", "JPN"],
            max_documents_per_source=10,
        ),
        limit=1,
        page=2,
    )
    response = adapter.search_documents(request)
    assert response.status == ToolStatus.SUCCESS
    assert len(response.documents) == 1
    assert response.trace is not None
    assert response.trace.page_count == 3
    assert response.trace.item_count == 1
    assert response.trace.truncated is True


def test_retry_metadata_records_retryable_failure_path() -> None:
    state = {"count": 0}

    def _flaky_call() -> str:
        state["count"] += 1
        if state["count"] == 1:
            raise TimeoutError("transient timeout")
        return "ok"

    result, metadata = run_with_retry(_flaky_call, max_retries=2, backoff_seconds=0.0)
    assert result == "ok"
    assert metadata.attempts == 2
    assert metadata.retry_count == 1
    assert metadata.retryable_failures == 1
    assert metadata.non_retryable_failures == 0
    assert metadata.last_error is not None


def test_citation_normalization_enriches_required_fields() -> None:
    evidence = EvidenceItem(
        evidence_id="evi_1",
        source_id="user_input",
        title="Internal note",
        summary="summary",
        support_text="support",
        score=0.5,
        citation=Citation(
            citation_id="cit_1",
            source_id="user_input",
            document_id="doc_1",
            locator=CitationLocator(
                document_id="doc_1",
                section_id="section_0",
                external_ref="doc_1#section_0",
            ),
            quote_text="quote",
            source_uri="https://example.com/internal-note",
        ),
    )
    normalized = normalize_evidence_item(
        evidence,
        source_name="User Provided Sources",
        external_id="doc_1",
    )
    metadata = normalized.citation.metadata
    assert metadata["source_name"] == "User Provided Sources"
    assert metadata["source_id"] == "user_input"
    assert metadata["title"] == "Internal note"
    assert metadata["url"] == "https://example.com/internal-note"
    assert metadata["locator"] == "doc_1#section_0"
    assert metadata["external_id"] == "doc_1"
    assert metadata["retrieved_at"]


def test_build_bundle_reports_source_quality_and_partial_failure() -> None:
    registry = SourceRegistry()
    registry.register(UserInputAdapter())
    registry.register(_BrokenAdapter())

    tools = build_source_tool_registry(
        source_registry=registry,
        source_router=_StaticRouter(),
    )
    response = tools.dispatch(
        ToolRequest(
            tool_name="build_evidence_bundle",
            query_context=QueryContext(
                query="mixed route",
                max_documents_per_source=3,
                max_evidence_per_source=2,
                user_provided_sources=[
                    UserProvidedSource(
                        title="Desk note",
                        inline_text="Supply remains constrained across refiners.",
                    )
                ],
            ),
        )
    )
    assert response.bundle is not None
    assert response.status in {ToolStatus.SUCCESS, ToolStatus.PARTIAL}
    assert response.source_quality_summary is not None
    quality = response.source_quality_summary
    assert quality.sources_attempted == 2
    assert quality.sources_succeeded >= 1
    assert quality.sources_failed >= 1
    assert quality.source_error_breakdown
    assert response.traces
    trace = response.traces[0]
    assert trace.page_count >= 0
    assert trace.item_count >= 0
    assert trace.evidence_count >= 0
    assert isinstance(response.bundle.metadata.get("truncated_sources"), list)
    assert isinstance(response.bundle.metadata.get("source_quality_summary"), dict)
