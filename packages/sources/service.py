from __future__ import annotations

from typing import Any

from packages.sources.governance import build_source_governance_snapshot
from packages.sources.registry import SourceRegistry, build_default_source_registry
from packages.sources.router import SourceRouter
from packages.sources.schemas import (
    QueryContext,
    SourceGovernanceSnapshot,
    SourcePerformanceItem,
    ToolRequest,
    ToolResponse,
)
from packages.sources.tools import SourceToolRegistry, build_source_tool_registry


class SourceIntelligenceService:
    # TODO: Add DB-backed source profile overrides and per-account routing policies.
    # TODO: Add full source acquisition orchestration with task queue integration.
    def __init__(
        self,
        *,
        source_registry: SourceRegistry | None = None,
        source_router: SourceRouter | None = None,
        tool_registry: SourceToolRegistry | None = None,
        source_performance_by_source: dict[str, SourcePerformanceItem] | None = None,
    ) -> None:
        self.source_registry = source_registry or build_default_source_registry()
        self.source_router = source_router or SourceRouter(
            include_domestic_profiles=self.source_registry.has_enabled_collector_profiles()
        )
        self.tool_registry = tool_registry or build_source_tool_registry(
            source_registry=self.source_registry,
            source_router=self.source_router,
        )
        self.source_performance_by_source = source_performance_by_source or {}

    def route_sources(
        self,
        query_context: QueryContext,
        *,
        source_performance_by_source: dict[str, SourcePerformanceItem] | None = None,
    ):
        return self.source_router.route(
            query_context,
            performance_by_source=(
                source_performance_by_source or self.source_performance_by_source
            ),
            profiles_by_source={
                profile.source_id: profile
                for profile in self.source_registry.list_profiles(enabled_only=False)
            },
        )

    def build_bundle_for_query(
        self,
        query_context: QueryContext,
        *,
        source_pack: str | None = None,
        limit: int | None = None,
        page: int | None = None,
        offset: int | None = None,
        max_evidence_per_source: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ToolResponse:
        effective_context = query_context
        if source_pack:
            effective_context = query_context.model_copy(update={"source_pack": source_pack})
        request = ToolRequest(
            tool_name="build_evidence_bundle",
            query_context=effective_context,
            limit=limit,
            page=page,
            offset=offset,
            max_evidence_per_source=max_evidence_per_source,
            payload=payload or {},
        )
        return self.tool_registry.dispatch(request)

    def build_governance_snapshot(
        self,
        query_context: QueryContext,
        *,
        source_pack: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> SourceGovernanceSnapshot:
        response = self.build_bundle_for_query(
            query_context,
            source_pack=source_pack,
            payload=payload,
        )
        if response.governance_snapshot is not None:
            return response.governance_snapshot
        bundle = response.bundle
        return build_source_governance_snapshot(
            traces=response.traces,
            source_summaries=(bundle.source_summary if bundle is not None else []),
            evidence_items=response.evidence_items,
            dedupe_metadata=(
                bundle.metadata.get("dedupe")
                if bundle is not None and isinstance(bundle.metadata, dict)
                else None
            ),
        )
