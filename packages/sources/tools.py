from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

from packages.sources.citation import normalize_evidence_item
from packages.sources.enums import ToolErrorCode, ToolStatus
from packages.sources.quality import summarize_source_quality
from packages.sources.registry import SourceRegistry, build_default_source_registry
from packages.sources.router import SourceRouter
from packages.sources.schemas import (
    EvidenceBundle,
    SourceSummaryItem,
    ToolError,
    ToolRequest,
    ToolResponse,
    ToolTrace,
)

ToolHandler = Callable[[ToolRequest], ToolResponse]


class SourceToolRegistry:
    def __init__(
        self,
        *,
        source_registry: SourceRegistry | None = None,
        source_router: SourceRouter | None = None,
    ) -> None:
        self.source_registry = source_registry or build_default_source_registry()
        self.source_router = source_router or SourceRouter()
        self._handlers: dict[str, ToolHandler] = {}
        self._register_defaults()

    def register(self, tool_name: str, handler: ToolHandler) -> None:
        self._handlers[tool_name] = handler

    def list_tools(self) -> list[str]:
        return sorted(self._handlers.keys())

    def dispatch(self, request: ToolRequest) -> ToolResponse:
        handler = self._handlers.get(request.tool_name)
        if handler is None:
            return ToolResponse(
                status=ToolStatus.ERROR,
                tool_name=request.tool_name,
                message=f"Unknown tool '{request.tool_name}'.",
                errors=[
                    ToolError(
                        code=ToolErrorCode.INVALID_REQUEST,
                        message=f"Unknown tool '{request.tool_name}'.",
                    )
                ],
            )
        return handler(request)

    def _register_defaults(self) -> None:
        self.register("route_research_sources", self.route_research_sources)
        self.register("fetch_user_provided_source", self.fetch_user_provided_source)
        self.register("search_source_documents", self.search_source_documents)
        self.register("fetch_document_detail", self.fetch_document_detail)
        self.register("extract_evidence_items", self.extract_evidence_items)
        self.register("build_evidence_bundle", self.build_evidence_bundle)

    def route_research_sources(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        performance_by_source = self._performance_from_payload(request)
        try:
            recommendations = self.source_router.route(
                request.query_context,
                performance_by_source=performance_by_source,
            )
        except TypeError:
            recommendations = self.source_router.route(request.query_context)
        return ToolResponse(
            status=ToolStatus.SUCCESS,
            tool_name=request.tool_name,
            route_recommendations=recommendations,
            message=f"Recommended {len(recommendations)} source(s).",
            trace=ToolTrace(
                tool_name=request.tool_name,
                status=ToolStatus.SUCCESS,
                source_ids=[item.source_id for item in recommendations],
                duration_ms=(perf_counter() - started) * 1000.0,
                item_count=len(recommendations),
                page_count=1,
                metadata={
                    "query_type": (
                        recommendations[0].query_type.value
                        if recommendations and recommendations[0].query_type is not None
                        else None
                    ),
                    "recommendations": [
                        item.model_dump(mode="json") for item in recommendations
                    ],
                },
            ),
        )

    def fetch_user_provided_source(self, request: ToolRequest) -> ToolResponse:
        adapter = self.source_registry.get_adapter("user_input")
        if adapter is None:
            return self._source_not_found_response(request, "user_input")
        return adapter.search_documents(request.with_source("user_input"))

    def search_source_documents(self, request: ToolRequest) -> ToolResponse:
        adapter = self._resolve_adapter(request)
        if isinstance(adapter, ToolResponse):
            return adapter
        return adapter.search_documents(request)

    def fetch_document_detail(self, request: ToolRequest) -> ToolResponse:
        adapter = self._resolve_adapter(request)
        if isinstance(adapter, ToolResponse):
            return adapter
        return adapter.fetch_document_detail(request)

    def extract_evidence_items(self, request: ToolRequest) -> ToolResponse:
        adapter = self._resolve_adapter(request)
        if isinstance(adapter, ToolResponse):
            return adapter
        return adapter.extract_evidence_items(request)

    def build_evidence_bundle(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        max_docs_per_source = request.query_context.max_documents_per_source
        max_evidence_per_source = request.query_context.max_evidence_per_source
        if request.limit is not None:
            max_docs_per_source = min(request.limit, max_docs_per_source)
        if request.max_evidence_per_source is not None:
            max_evidence_per_source = min(
                request.max_evidence_per_source,
                max_evidence_per_source,
            )

        route_response = self.route_research_sources(
            ToolRequest(
                tool_name="route_research_sources",
                query_context=request.query_context,
                limit=max_docs_per_source,
                page=request.page,
                offset=request.offset,
                max_evidence_per_source=max_evidence_per_source,
                payload=request.payload,
                trace_id=request.trace_id,
            )
        )
        evidence_items = []
        documents = []
        normalized_documents = []
        errors = list(route_response.errors)
        gaps: list[str] = []
        source_summaries: dict[str, SourceSummaryItem] = {}
        traces: list[ToolTrace] = []
        if route_response.trace is not None:
            traces.append(route_response.trace)
        truncated_sources: set[str] = set()

        for recommendation in route_response.route_recommendations:
            adapter = self.source_registry.get_adapter(recommendation.source_id)
            if adapter is None:
                errors.append(
                    ToolError(
                        code=ToolErrorCode.SOURCE_NOT_FOUND,
                        message=f"Source '{recommendation.source_id}' not found or disabled.",
                    )
                )
                gaps.append(f"source:{recommendation.source_id}:adapter_not_found")
                continue
            search_response = adapter.search_documents(
                ToolRequest(
                    tool_name="search_source_documents",
                    query_context=request.query_context,
                    source_id=recommendation.source_id,
                    limit=max_docs_per_source,
                    page=request.page,
                    offset=request.offset,
                    max_evidence_per_source=max_evidence_per_source,
                    payload=request.payload,
                    trace_id=request.trace_id,
                )
            )
            documents.extend(search_response.documents)
            normalized_documents.extend(search_response.normalized_documents)
            errors.extend(search_response.errors)
            if search_response.trace is not None:
                traces.append(search_response.trace)
                if search_response.trace.truncated:
                    truncated_sources.add(recommendation.source_id)
            if search_response.status in {ToolStatus.ERROR, ToolStatus.NOT_IMPLEMENTED}:
                gaps.append(f"source:{recommendation.source_id}:search_unavailable")

            detail_count = 0
            if search_response.documents:
                for raw_document in search_response.documents[:max_docs_per_source]:
                    detail_response = adapter.fetch_document_detail(
                        ToolRequest(
                            tool_name="fetch_document_detail",
                            query_context=request.query_context,
                            source_id=recommendation.source_id,
                            document_id=raw_document.document_id,
                            limit=max_docs_per_source,
                            page=request.page,
                            offset=request.offset,
                            max_evidence_per_source=max_evidence_per_source,
                            payload=request.payload,
                            trace_id=request.trace_id,
                        )
                    )
                    detail_count += len(detail_response.documents)
                    documents.extend(detail_response.documents)
                    normalized_documents.extend(detail_response.normalized_documents)
                    errors.extend(detail_response.errors)
                    if detail_response.trace is not None:
                        traces.append(detail_response.trace)
                        if detail_response.trace.truncated:
                            truncated_sources.add(recommendation.source_id)

            seed_document_id = None
            if search_response.documents:
                seed_document_id = search_response.documents[0].document_id
            extract_response = adapter.extract_evidence_items(
                ToolRequest(
                    tool_name="extract_evidence_items",
                    query_context=request.query_context,
                    source_id=recommendation.source_id,
                    document_id=seed_document_id,
                    limit=max_docs_per_source,
                    page=request.page,
                    offset=request.offset,
                    max_evidence_per_source=max_evidence_per_source,
                    payload=request.payload,
                    trace_id=request.trace_id,
                )
            )
            normalized_evidence = [
                normalize_evidence_item(
                    item,
                    source_name=adapter.get_profile().display_name,
                    external_id=item.citation.document_id,
                )
                for item in extract_response.evidence_items[:max_evidence_per_source]
            ]
            truncated = len(extract_response.evidence_items) > len(normalized_evidence)
            if truncated:
                truncated_sources.add(recommendation.source_id)

            documents.extend(extract_response.documents)
            normalized_documents.extend(extract_response.normalized_documents)
            evidence_items.extend(normalized_evidence)
            errors.extend(extract_response.errors)
            if extract_response.trace is not None:
                trace = extract_response.trace.model_copy(
                    update={
                        "evidence_count": len(normalized_evidence),
                        "truncated": extract_response.trace.truncated or truncated,
                    }
                )
                traces.append(trace)
                if trace.truncated:
                    truncated_sources.add(recommendation.source_id)

            if extract_response.evidence_items:
                profile = adapter.get_profile()
                source_summaries[recommendation.source_id] = SourceSummaryItem(
                    source_id=recommendation.source_id,
                    source_name=profile.display_name,
                    document_count=max(len(search_response.documents), detail_count),
                    evidence_count=len(normalized_evidence),
                    notes=[
                        recommendation.reason,
                        f"max_docs_per_source={max_docs_per_source}",
                        f"max_evidence_per_source={max_evidence_per_source}",
                    ],
                )
            else:
                gaps.append(f"source:{recommendation.source_id}:no_evidence")

        source_quality = summarize_source_quality(
            source_ids=[item.source_id for item in route_response.route_recommendations],
            traces=traces,
            errors=errors,
            evidence_items=evidence_items,
            source_summaries=list(source_summaries.values()),
        )
        bundle = EvidenceBundle(
            query=request.query_context.query,
            items=evidence_items,
            evidence_items=evidence_items,
            source_summary=list(source_summaries.values()),
            sources=list(source_summaries.values()),
            gaps=gaps,
            metadata={
                "route_recommendation_count": len(route_response.route_recommendations),
                "max_docs_per_source": max_docs_per_source,
                "max_evidence_per_source": max_evidence_per_source,
                "truncated_sources": sorted(truncated_sources),
                "source_quality_summary": source_quality.model_dump(mode="json"),
                "trace_count": len(traces),
                "requested_evidence_mode": (
                    request.evidence_mode.value
                    if request.evidence_mode is not None
                    else request.query_context.evidence_mode.value
                ),
            },
        )

        status = ToolStatus.SUCCESS if evidence_items else ToolStatus.PARTIAL
        message = (
            f"Built evidence bundle with {len(evidence_items)} evidence item(s)."
            if evidence_items
            else "No evidence items extracted in this skeleton step."
        )
        return ToolResponse(
            status=status,
            tool_name=request.tool_name,
            bundle=bundle,
            documents=documents,
            normalized_documents=normalized_documents,
            evidence_items=evidence_items,
            route_recommendations=route_response.route_recommendations,
            errors=errors,
            traces=traces,
            source_quality_summary=source_quality,
            trace=ToolTrace(
                tool_name=request.tool_name,
                status=status,
                source_ids=[item.source_id for item in route_response.route_recommendations],
                duration_ms=(perf_counter() - started) * 1000.0,
                page_count=1,
                item_count=len(documents),
                evidence_count=len(evidence_items),
                retry_count=sum(trace.retry_count for trace in traces),
                truncated=bool(truncated_sources),
                warnings=source_quality.warnings,
                metadata={
                    "error_count": len(errors),
                    "trace_count": len(traces),
                    "source_quality_summary": source_quality.model_dump(mode="json"),
                },
            ),
            message=message,
        )

    def _resolve_adapter(self, request: ToolRequest):
        if not request.source_id:
            return ToolResponse(
                status=ToolStatus.ERROR,
                tool_name=request.tool_name,
                message="source_id is required.",
                errors=[
                    ToolError(
                        code=ToolErrorCode.INVALID_REQUEST,
                        message="source_id is required.",
                    )
                ],
            )
        adapter = self.source_registry.get_adapter(request.source_id)
        if adapter is None:
            return self._source_not_found_response(request, request.source_id)
        return adapter

    def _source_not_found_response(self, request: ToolRequest, source_id: str) -> ToolResponse:
        return ToolResponse(
            status=ToolStatus.ERROR,
            tool_name=request.tool_name,
            source_id=source_id,
            message=f"Source '{source_id}' not found or disabled.",
            errors=[
                ToolError(
                    code=ToolErrorCode.SOURCE_NOT_FOUND,
                    message=f"Source '{source_id}' not found or disabled.",
                )
            ],
        )

    def _performance_from_payload(self, request: ToolRequest):
        rows = request.payload.get("source_performance")
        if not isinstance(rows, list):
            return {}
        parsed = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                from packages.sources.schemas import SourcePerformanceItem

                item = SourcePerformanceItem.model_validate(row)
            except Exception:  # noqa: BLE001
                continue
            parsed[item.source_id] = item
        return parsed


def build_source_tool_registry(
    *,
    source_registry: SourceRegistry | None = None,
    source_router: SourceRouter | None = None,
) -> SourceToolRegistry:
    return SourceToolRegistry(
        source_registry=source_registry,
        source_router=source_router,
    )
