from __future__ import annotations

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
from packages.sources.registry import SourceRegistry, build_default_source_registry
from packages.sources.router import SourceRouter
from packages.sources.schemas import (
    Citation,
    CitationLocator,
    EvidenceItem,
    QueryContext,
    SourceAccess,
    SourceCapabilities,
    SourceProfile,
    ToolRequest,
    ToolResponse,
)
from packages.sources.tools import build_source_tool_registry


class _PackReadyAdapter(BaseSourceAdapter):
    def __init__(self, profile: SourceProfile) -> None:
        self._profile = profile

    def get_profile(self) -> SourceProfile:
        return self._profile

    def search_documents(self, request: ToolRequest):
        return ToolResponse(
            status=ToolStatus.SUCCESS,
            tool_name=request.tool_name,
            source_id=self._profile.source_id,
            documents=[],
            normalized_documents=[],
            message="pack-ready-search",
            trace=self.build_trace(
                request=request,
                status=ToolStatus.SUCCESS,
            ),
        )

    def fetch_document_detail(self, request: ToolRequest):
        return ToolResponse(
            status=ToolStatus.SUCCESS,
            tool_name=request.tool_name,
            source_id=self._profile.source_id,
            documents=[],
            normalized_documents=[],
            message="pack-ready-detail",
            trace=self.build_trace(
                request=request,
                status=ToolStatus.SUCCESS,
            ),
        )

    def extract_evidence_items(self, request: ToolRequest):
        evidence = EvidenceItem(
            evidence_id=f"evi_{self._profile.source_id}",
            source_id=self._profile.source_id,
            title=f"{self._profile.display_name} evidence",
            summary="summary",
            support_text="support text",
            score=0.7,
            citation=Citation(
                citation_id=f"cit_{self._profile.source_id}",
                source_id=self._profile.source_id,
                document_id=f"doc_{self._profile.source_id}",
                locator=CitationLocator(document_id=f"doc_{self._profile.source_id}"),
                quote_text="quote",
                source_uri="https://example.cn/doc",
            ),
        )
        duplicate = evidence.model_copy(
            update={
                "evidence_id": f"{evidence.evidence_id}_dup",
                "score": 0.5,
            }
        )
        return ToolResponse(
            status=ToolStatus.SUCCESS,
            tool_name=request.tool_name,
            source_id=self._profile.source_id,
            evidence_items=[evidence, duplicate],
            message="pack-ready-evidence",
            trace=self.build_trace(
                request=request,
                status=ToolStatus.SUCCESS,
                evidence_count=2,
            ),
        )


def _build_pack_registry() -> SourceRegistry:
    registry = SourceRegistry()
    for profile in (
        SourceProfile(
            source_id="cn_policy_ndrc_tzgg_v1",
            display_name="NDRC Notices",
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
        ),
        SourceProfile(
            source_id="cn_policy_generic",
            display_name="Policy Generic",
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
        ),
    ):
        registry.register_profile(profile, adapter=_PackReadyAdapter(profile))
    return registry


def test_tiaokuai_router_adds_breakdown_for_domestic_policy() -> None:
    registry = build_default_source_registry()
    profiles = {item.source_id: item for item in registry.list_profiles(enabled_only=False)}
    router = SourceRouter(include_domestic_profiles=True)
    recs = router.route(
        QueryContext(query="\u90e8\u59d4 \u653f\u7b56 \u901a\u77e5 \u7ec6\u5219"),
        profiles_by_source=profiles,
    )
    assert recs
    ndrc = next(item for item in recs if item.source_id == "cn_policy_ndrc_tzgg_v1")
    assert ndrc.score_breakdown["tiaokuai_line_family_bonus"] > 0
    assert ndrc.score_breakdown["tiaokuai_axis_bonus"] > 0


def test_tiaokuai_router_prefers_block_source_for_local_rollout_query() -> None:
    registry = build_default_source_registry()
    profiles = {item.source_id: item for item in registry.list_profiles(enabled_only=False)}
    router = SourceRouter(include_domestic_profiles=True)
    recs = router.route(
        QueryContext(query="\u5730\u65b9 \u8bd5\u70b9 \u9879\u76ee \u843d\u5730 \u8fdb\u5ea6"),
        profiles_by_source=profiles,
    )
    assert recs
    industry = next(
        item for item in recs if item.source_id == "cn_industry_association_generic"
    )
    assert industry.score_breakdown["tiaokuai_axis_bonus"] > 0
    assert industry.score_breakdown["tiaokuai_regional_bonus"] > 0


def test_source_pack_routing_restricts_to_pack_sources() -> None:
    registry = _build_pack_registry()
    tools = build_source_tool_registry(
        source_registry=registry,
        source_router=SourceRouter(include_domestic_profiles=True),
    )
    route = tools.dispatch(
        ToolRequest(
            tool_name="route_research_sources",
            query_context=QueryContext(
                query="\u4ea7\u4e1a\u653f\u7b56",
                source_pack="policy_pack_cn",
            ),
        )
    )
    assert route.status == ToolStatus.SUCCESS
    source_ids = {item.source_id for item in route.route_recommendations}
    assert source_ids <= {"cn_policy_ndrc_tzgg_v1", "cn_policy_generic"}
    assert route.trace is not None
    assert route.trace.metadata["source_pack"] == "policy_pack_cn"


def test_source_pack_bundle_builds_evidence_and_keeps_metadata() -> None:
    registry = _build_pack_registry()
    tools = build_source_tool_registry(
        source_registry=registry,
        source_router=SourceRouter(include_domestic_profiles=True),
    )
    bundle = tools.dispatch(
        ToolRequest(
            tool_name="build_evidence_bundle",
            query_context=QueryContext(
                query="\u90e8\u59d4 \u653f\u7b56",
                source_pack="policy_pack_cn",
                max_sources=2,
                max_documents_per_source=1,
                max_evidence_per_source=1,
            ),
        )
    )
    assert bundle.status in {ToolStatus.SUCCESS, ToolStatus.PARTIAL}
    assert bundle.bundle is not None
    assert bundle.bundle.metadata["source_pack"] == "policy_pack_cn"
    assert bundle.evidence_items


def test_source_pack_bundle_applies_defaults_and_dedupes() -> None:
    registry = _build_pack_registry()
    tools = build_source_tool_registry(
        source_registry=registry,
        source_router=SourceRouter(include_domestic_profiles=True),
    )
    bundle = tools.dispatch(
        ToolRequest(
            tool_name="build_evidence_bundle",
            query_context=QueryContext(
                query="\u90e8\u59d4 \u653f\u7b56",
                source_pack="policy_pack_cn",
                max_sources=2,
                max_documents_per_source=10,
                max_evidence_per_source=10,
            ),
        )
    )
    assert bundle.bundle is not None
    defaults = bundle.bundle.metadata["source_pack_defaults_applied"]
    assert defaults["pack_id"] == "policy_pack_cn"
    assert bundle.bundle.metadata["max_docs_per_source"] == 4
    assert bundle.bundle.metadata["max_evidence_per_source"] == 2
    dedupe = bundle.bundle.metadata["dedupe"]
    assert dedupe["removed_evidence_duplicates"] > 0
    assert dedupe["evidence_count_after_dedupe"] == len(bundle.evidence_items)


def test_source_strategy_can_select_pack_without_explicit_source_pack() -> None:
    registry = _build_pack_registry()
    tools = build_source_tool_registry(
        source_registry=registry,
        source_router=SourceRouter(include_domestic_profiles=True),
    )
    route = tools.dispatch(
        ToolRequest(
            tool_name="route_research_sources",
            query_context=QueryContext(
                query="\u653f\u7b56 \u89c4\u5212",
                source_strategy="cn_policy_first",
            ),
        )
    )
    assert route.route_recommendations
    assert all(item.selected_via == "source_strategy" for item in route.route_recommendations)
    source_ids = {item.source_id for item in route.route_recommendations}
    assert source_ids <= {"cn_policy_ndrc_tzgg_v1", "cn_policy_generic"}


def test_domestic_mode_and_regional_focus_are_reflected_in_breakdown() -> None:
    registry = build_default_source_registry()
    profiles = {item.source_id: item for item in registry.list_profiles(enabled_only=False)}
    router = SourceRouter(include_domestic_profiles=True)
    recs = router.route(
        QueryContext(
            query="\u5730\u65b9 \u8bd5\u70b9 \u9879\u76ee",
            domestic_mode="tiao_priority",
            regional_focus=["anhui", "guangdong"],
        ),
        profiles_by_source=profiles,
    )
    assert recs
    top = recs[0]
    assert top.score_breakdown["tiaokuai_mode_bonus"] > 0
    assert "tiaokuai_regional_bonus" in top.score_breakdown
