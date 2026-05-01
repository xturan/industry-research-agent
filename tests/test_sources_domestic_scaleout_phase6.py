from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.sources.adapters.base import BaseSourceAdapter
from packages.sources.enums import (
    AccessMethod,
    GovernanceAxis,
    InfoType,
    LineFamily,
    RegionalLevel,
    SourceCategory,
    SourceRole,
    ToolStatus,
    TrustTier,
)
from packages.sources.registry import SourceRegistry
from packages.sources.router import SourceRouter
from packages.sources.schemas import (
    Citation,
    CitationLocator,
    EvidenceItem,
    QueryContext,
    RawDocument,
    SourceAccess,
    SourceCapabilities,
    SourceProfile,
    ToolRequest,
    ToolResponse,
)
from packages.sources.service import SourceIntelligenceService
from packages.sources.tools import build_source_tool_registry

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone(timedelta(0))


class _GovernanceAdapter(BaseSourceAdapter):
    def __init__(self, profile: SourceProfile) -> None:
        self._profile = profile

    def get_profile(self) -> SourceProfile:
        return self._profile

    def search_documents(self, request: ToolRequest) -> ToolResponse:
        doc = RawDocument(
            document_id=f"doc_{self._profile.source_id}",
            source_id=self._profile.source_id,
            title=f"{self._profile.display_name} Doc",
            source_uri="https://example.cn/doc",
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            raw_text="policy sample",
        )
        return ToolResponse(
            status=ToolStatus.SUCCESS,
            tool_name=request.tool_name,
            source_id=self._profile.source_id,
            documents=[doc],
            message="gov-search",
            trace=self.build_trace(
                request=request,
                status=ToolStatus.SUCCESS,
                item_count=1,
                http_calls=1,
                metadata={"attachment_count": 2},
            ),
        )

    def fetch_document_detail(self, request: ToolRequest) -> ToolResponse:
        doc = RawDocument(
            document_id=request.document_id or f"doc_{self._profile.source_id}",
            source_id=self._profile.source_id,
            title=f"{self._profile.display_name} Detail",
            source_uri="https://example.cn/detail",
            published_at=datetime(2026, 1, 2, tzinfo=UTC),
            raw_text="detail sample",
        )
        return ToolResponse(
            status=ToolStatus.SUCCESS,
            tool_name=request.tool_name,
            source_id=self._profile.source_id,
            documents=[doc],
            message="gov-detail",
            trace=self.build_trace(
                request=request,
                status=ToolStatus.SUCCESS,
                item_count=1,
                http_calls=1,
                metadata={
                    "attachment_count": 2,
                    "pdf_processing": {
                        "enabled": True,
                        "processed_attachments": 1,
                        "pdf_documents": 1,
                        "pages_extracted": 2,
                        "truncated": False,
                    },
                },
            ),
        )

    def extract_evidence_items(self, request: ToolRequest) -> ToolResponse:
        citation = Citation(
            citation_id=f"cit_{self._profile.source_id}",
            source_id=self._profile.source_id,
            document_id=f"doc_{self._profile.source_id}",
            locator=CitationLocator(document_id=f"doc_{self._profile.source_id}", section_id="s1"),
            quote_text="quote",
            source_uri="https://example.cn/detail",
            published_at=datetime(2026, 1, 2, tzinfo=UTC),
            metadata={
                "source_name": self._profile.display_name,
                "source_id": self._profile.source_id,
                "title": "sample title",
                "url": "https://example.cn/detail",
                "published_at": "2026-01-02T00:00:00+00:00",
                "retrieved_at": "2026-04-21T00:00:00+00:00",
                "locator": "section:s1",
                "external_id": f"doc_{self._profile.source_id}",
            },
        )
        primary = EvidenceItem(
            evidence_id=f"evi_{self._profile.source_id}",
            source_id=self._profile.source_id,
            title="sample",
            summary="summary",
            support_text="support",
            score=0.7,
            citation=citation,
        )
        duplicate = primary.model_copy(
            update={"evidence_id": f"{primary.evidence_id}_dup", "score": 0.5}
        )
        return ToolResponse(
            status=ToolStatus.SUCCESS,
            tool_name=request.tool_name,
            source_id=self._profile.source_id,
            evidence_items=[primary, duplicate],
            message="gov-evidence",
            trace=self.build_trace(
                request=request,
                status=ToolStatus.SUCCESS,
                evidence_count=2,
                item_count=1,
            ),
        )


def _build_profile(source_id: str, display_name: str) -> SourceProfile:
    return SourceProfile(
        source_id=source_id,
        display_name=display_name,
        category=SourceCategory.POLICY_PORTAL,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        enabled=True,
        access=SourceAccess(access_method=AccessMethod.WEB, auth_required=False),
        capabilities=SourceCapabilities(
            supports_search=True,
            supports_document_detail=True,
            supports_evidence_extraction=True,
            supports_time_filter=True,
            supports_keyword_filter=True,
            supports_bulk=False,
        ),
        governance_axis=GovernanceAxis.LINE,
        line_family=LineFamily.POLICY,
        regional_level=RegionalLevel.NATIONAL,
        info_type=InfoType.POLICY_NOTICE,
        source_role=SourceRole.PRIMARY,
    )


def _build_registry() -> SourceRegistry:
    registry = SourceRegistry()
    for source_id, display_name in (
        ("cn_policy_ndrc_tzgg_v1", "NDRC"),
        ("cn_policy_generic", "Policy Generic"),
    ):
        profile = _build_profile(source_id, display_name)
        registry.register_profile(profile, adapter=_GovernanceAdapter(profile))
    return registry


def test_phase6_bundle_contains_governance_snapshot() -> None:
    registry = _build_registry()
    tools = build_source_tool_registry(
        source_registry=registry,
        source_router=SourceRouter(include_domestic_profiles=True),
    )
    response = tools.dispatch(
        ToolRequest(
            tool_name="build_evidence_bundle",
            query_context=QueryContext(
                query="政策 通知",
                source_pack="policy_pack_cn",
                max_sources=2,
                max_documents_per_source=2,
                max_evidence_per_source=2,
            ),
        )
    )
    assert response.status in {ToolStatus.SUCCESS, ToolStatus.PARTIAL}
    assert response.governance_snapshot is not None
    snapshot = response.governance_snapshot
    assert snapshot.fetch_success_rate > 0.0
    assert snapshot.parse_success_rate > 0.0
    assert snapshot.duplicate_ratio > 0.0
    assert snapshot.pack_evidence_density >= 0.0
    assert response.bundle is not None
    assert "governance_snapshot" in response.bundle.metadata


def test_phase6_service_governance_snapshot_method() -> None:
    registry = _build_registry()
    tools = build_source_tool_registry(
        source_registry=registry,
        source_router=SourceRouter(include_domestic_profiles=True),
    )
    service = SourceIntelligenceService(
        source_registry=registry,
        source_router=SourceRouter(include_domestic_profiles=True),
        tool_registry=tools,
    )
    snapshot = service.build_governance_snapshot(
        QueryContext(
            query="政策 通知",
            source_pack="policy_pack_cn",
            max_sources=2,
            max_documents_per_source=2,
            max_evidence_per_source=2,
        )
    )
    assert snapshot.fetch_success_rate > 0.0
    assert snapshot.parse_success_rate > 0.0
