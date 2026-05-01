from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from packages.sources.collectors import PdfArtifact, normalize_pdf_text_to_documents
from packages.sources.crawl4ai_extraction import (
    Crawl4AIExtractionProvider,
    Crawl4AIExtractionRequest,
    Crawl4AIExtractionService,
    SearchUrlCandidate,
)
from packages.sources.disclosure_api import CninfoDisclosureApiProvider
from packages.sources.disclosure_mapping import (
    DisclosureAnnouncementSearchSpec,
    build_disclosure_search_spec,
    disclosure_document_matches_spec,
)
from packages.sources.enums import ToolErrorCode, ToolStatus
from packages.sources.file_evidence import file_candidate_kind_from_url
from packages.sources.live_pdf import LivePdfDownloadError, LivePdfDownloadService
from packages.sources.local_source_patterns import (
    classify_local_region_match,
    generic_local_region_terms,
)
from packages.sources.pdf_text import PdfTextExtractionError, PdfTextExtractionService
from packages.sources.query_decomposition import QueryDecompositionTask
from packages.sources.registry import SourceRegistry, build_default_source_registry
from packages.sources.retrieval_plan import CoverageLane, lane_for_task_family
from packages.sources.schemas import (
    EvidenceItem,
    NormalizedDocument,
    QueryContext,
    RawDocument,
    ToolError,
    ToolRequest,
    ToolTrace,
)
from packages.sources.search_assisted_domestic import (
    convert_search_assisted_documents_to_evidence_items,
)
from packages.sources.search_discovery import (
    SearchDiscoveryProvider,
    TavilySearchAdapter,
    TavilySearchRequest,
    TavilySearchResult,
)
from packages.sources.source_family_backbone import (
    source_family_backbones_for_source_classes,
)

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 fallback

    class StrEnum(str, Enum):  # noqa: UP042
        pass


class DirectLaneExecutionState(StrEnum):
    EXECUTED_WITH_EVIDENCE = "executed_with_evidence"
    EXECUTED_WITHOUT_EVIDENCE = "executed_without_evidence"
    SKIPPED_BUDGET_EXHAUSTED = "skipped_budget_exhausted"
    SKIPPED_NO_ADAPTER = "skipped_no_adapter"
    SKIPPED_UNSUPPORTED_SOURCE_CLASS = "skipped_unsupported_source_class"
    REFUSED_DIRECT_KEEP_BOUNDARY = "refused_direct_keep_boundary"
    FAILED_RUNTIME_ERROR = "failed_runtime_error"


class DirectStructuredLaneExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ToolStatus
    task_id: str = Field(min_length=1, max_length=80)
    task_family: str = Field(min_length=1, max_length=40)
    execution_bucket: str = Field(min_length=1, max_length=40)
    lane_id: str | None = None
    execution_state: DirectLaneExecutionState
    source_ids_considered: list[str] = Field(default_factory=list)
    source_ids_selected: list[str] = Field(default_factory=list)
    source_ids_attempted: list[str] = Field(default_factory=list)
    documents: list[RawDocument] = Field(default_factory=list)
    normalized_documents: list[NormalizedDocument] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    errors: list[ToolError] = Field(default_factory=list)
    traces: list[ToolTrace] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def normalized_document_count(self) -> int:
        return len(self.normalized_documents)

    @property
    def evidence_count(self) -> int:
        return len(self.evidence_items)


_LOCAL_REGION_EVIDENCE_MATCH_TYPES = {"exact_local", "child_local", "parent_local"}
_PROVINCE_LEVEL_REGION_TERMS = {
    "安徽",
    "广东",
    "江苏",
    "浙江",
    "四川",
    "湖北",
    "山东",
    "内蒙古",
    "新疆",
    "陕西",
    "海南",
    "上海",
    "广西",
    "河南",
    "福建",
}


class DirectStructuredLaneExecutor:
    def __init__(
        self,
        *,
        source_registry: SourceRegistry | None = None,
        max_profiles_per_lane: int = 3,
        max_documents_per_profile: int = 1,
        max_evidence_per_profile: int = 1,
        project_search_provider: SearchDiscoveryProvider | None = None,
        project_extraction_provider: Crawl4AIExtractionProvider | None = None,
        data_metrics_search_provider: SearchDiscoveryProvider | None = None,
        data_metrics_extraction_provider: Crawl4AIExtractionProvider | None = None,
        official_record_search_provider: SearchDiscoveryProvider | None = None,
        official_record_extraction_provider: Crawl4AIExtractionProvider | None = None,
        official_record_pdf_download_service: LivePdfDownloadService | None = None,
        official_record_pdf_text_service: PdfTextExtractionService | None = None,
        disclosure_api_provider: Any | None = None,
        enable_project_search_fallback: bool = True,
        enable_data_metrics_search_fallback: bool = True,
        enable_official_record_search_fallback: bool = True,
        enable_official_record_pdf_fallback: bool = True,
        enable_disclosure_api_fallback: bool = True,
        max_project_fallback_candidates: int = 2,
        max_data_metrics_fallback_candidates: int = 2,
        max_project_fallback_search_credits: int = 2,
        max_data_metrics_fallback_search_credits: int = 2,
        max_official_record_fallback_candidates: int = 2,
        max_official_record_fallback_search_credits: int = 3,
        max_official_record_pdf_pages: int = 5,
    ) -> None:
        self.source_registry = source_registry or build_default_source_registry()
        self.max_profiles_per_lane = max(1, min(max_profiles_per_lane, 10))
        self.max_documents_per_profile = max(1, min(max_documents_per_profile, 20))
        self.max_evidence_per_profile = max(1, min(max_evidence_per_profile, 20))
        self.project_search_provider = project_search_provider
        self.project_extraction_provider = project_extraction_provider
        self.data_metrics_search_provider = data_metrics_search_provider
        self.data_metrics_extraction_provider = data_metrics_extraction_provider
        self.official_record_search_provider = official_record_search_provider
        self.official_record_extraction_provider = official_record_extraction_provider
        self.official_record_pdf_download_service = official_record_pdf_download_service
        self.official_record_pdf_text_service = official_record_pdf_text_service
        self.disclosure_api_provider = disclosure_api_provider
        self.enable_project_search_fallback = enable_project_search_fallback
        self.enable_data_metrics_search_fallback = enable_data_metrics_search_fallback
        self.enable_official_record_search_fallback = enable_official_record_search_fallback
        self.enable_official_record_pdf_fallback = enable_official_record_pdf_fallback
        self.enable_disclosure_api_fallback = enable_disclosure_api_fallback
        self.max_project_fallback_candidates = max(1, min(max_project_fallback_candidates, 5))
        self.max_data_metrics_fallback_candidates = max(
            1,
            min(max_data_metrics_fallback_candidates, 5),
        )
        self.max_project_fallback_search_credits = max(
            1,
            min(max_project_fallback_search_credits, 10),
        )
        self.max_data_metrics_fallback_search_credits = max(
            1,
            min(max_data_metrics_fallback_search_credits, 10),
        )
        self.max_official_record_fallback_candidates = max(
            1,
            min(max_official_record_fallback_candidates, 5),
        )
        self.max_official_record_fallback_search_credits = max(
            1,
            min(max_official_record_fallback_search_credits, 10),
        )
        self.max_official_record_pdf_pages = max(1, min(max_official_record_pdf_pages, 20))

    def execute_task(
        self,
        task: QueryDecompositionTask,
    ) -> DirectStructuredLaneExecutionResult:
        lane_id = lane_for_task_family(task.task_family)
        source_ids_considered = _candidate_source_ids_for_task(task)
        metadata: dict[str, Any] = {
            "lane_id": lane_id.value if lane_id is not None else None,
            "source_cluster": task.source_cluster,
            "source_strategy_hint": task.source_strategy_hint,
            "execution_bucket": task.execution_bucket,
            "reason_code": None,
        }
        disclosure_search_spec = None
        if task.task_family == "enterprise_disclosure":
            disclosure_search_spec = build_disclosure_search_spec(_task_text(task))
            metadata["disclosure_search_spec"] = disclosure_search_spec.to_dict()
            metadata["missing_company_hint"] = not disclosure_search_spec.entity_candidates
            source_ids_considered = [
                source_id
                for source_id in source_ids_considered
                if source_id in set(disclosure_search_spec.source_ids)
            ]
            if not disclosure_search_spec.entity_candidates:
                metadata["reason_code"] = "disclosure_no_entity_candidate"
                return self._empty_result(
                    task=task,
                    lane_id=lane_id,
                    state=DirectLaneExecutionState.EXECUTED_WITHOUT_EVIDENCE,
                    status=ToolStatus.PARTIAL,
                    source_ids_considered=source_ids_considered,
                    metadata=metadata,
                )
        if task.execution_bucket != "direct_structured_sources":
            metadata["reason_code"] = "not_direct_structured_lane"
            return self._empty_result(
                task=task,
                lane_id=lane_id,
                state=DirectLaneExecutionState.REFUSED_DIRECT_KEEP_BOUNDARY,
                status=ToolStatus.UNSUPPORTED,
                source_ids_considered=source_ids_considered,
                metadata=metadata,
                error=ToolError(
                    code=ToolErrorCode.UNSUPPORTED_OPERATION,
                    message="Task is not a direct structured lane.",
                    retryable=False,
                    detail={"reason_code": metadata["reason_code"]},
                ),
            )

        if task.task_family == "official_record":
            return self._execute_official_record_task(
                task=task,
                lane_id=lane_id,
                source_ids_considered=source_ids_considered,
                metadata=metadata,
            )

        if not source_ids_considered:
            metadata["reason_code"] = "unsupported_direct_source_class"
            return self._empty_result(
                task=task,
                lane_id=lane_id,
                state=DirectLaneExecutionState.SKIPPED_UNSUPPORTED_SOURCE_CLASS,
                status=ToolStatus.UNSUPPORTED,
                source_ids_considered=[],
                metadata=metadata,
            )

        available_source_ids = [
            source_id
            for source_id in source_ids_considered
            if self.source_registry.get_adapter(source_id) is not None
        ][: self.max_profiles_per_lane]
        if not available_source_ids:
            metadata["reason_code"] = "direct_adapter_not_available"
            return self._empty_result(
                task=task,
                lane_id=lane_id,
                state=DirectLaneExecutionState.SKIPPED_NO_ADAPTER,
                status=ToolStatus.UNSUPPORTED,
                source_ids_considered=source_ids_considered,
                metadata=metadata,
            )

        documents: list[RawDocument] = []
        normalized_documents: list[NormalizedDocument] = []
        evidence_items: list[EvidenceItem] = []
        errors: list[ToolError] = []
        traces: list[ToolTrace] = []
        weak_document_rejections: list[dict[str, Any]] = []
        attempted: list[str] = []
        query_context = _query_context_for_task(
            task,
            max_documents_per_source=self.max_documents_per_profile,
            max_evidence_per_source=self.max_evidence_per_profile,
        )
        if disclosure_search_spec is not None:
            query_context = query_context.model_copy(
                update={
                    "query": disclosure_search_spec.query,
                    "tickers": [
                        candidate.ticker
                        for candidate in disclosure_search_spec.entity_candidates
                        if candidate.ticker
                    ],
                    "metadata": {
                        **query_context.metadata,
                        "disclosure_search_spec": disclosure_search_spec.to_dict(),
                    },
                }
            )

        for source_id in available_source_ids:
            adapter = self.source_registry.get_adapter(source_id)
            if adapter is None:
                errors.append(
                    ToolError(
                        code=ToolErrorCode.SOURCE_NOT_FOUND,
                        message=f"Source '{source_id}' has no enabled adapter.",
                        retryable=False,
                        detail={"source_id": source_id},
                    )
                )
                continue
            attempted.append(source_id)
            try:
                response = adapter.search_documents(
                    ToolRequest(
                        tool_name="search_source_documents",
                        query_context=query_context,
                        source_id=source_id,
                        limit=self.max_documents_per_profile,
                        max_evidence_per_source=self.max_evidence_per_profile,
                        payload={
                            "direct_structured_lane": True,
                            "task_id": task.task_id,
                            "task_family": task.task_family,
                            "lane_id": lane_id.value if lane_id is not None else None,
                            "disclosure_search_spec": disclosure_search_spec.to_dict()
                            if disclosure_search_spec is not None
                            else None,
                        },
                    )
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=f"Direct lane source '{source_id}' failed: {exc}",
                        retryable=False,
                        detail={
                            "source_id": source_id,
                            "error_type": type(exc).__name__,
                        },
                    )
                )
                continue

            response_documents = list(response.documents)
            response_normalized_documents = list(response.normalized_documents)
            if disclosure_search_spec is not None:
                spec_payload = disclosure_search_spec.to_dict()
                response_documents = [
                    document.model_copy(
                        update={
                            "metadata": {
                                **document.metadata,
                                "disclosure_search_spec": spec_payload,
                            }
                        }
                    )
                    for document in response_documents
                ]
                response_normalized_documents = [
                    document.model_copy(
                        update={
                            "metadata": {
                                **document.metadata,
                                "disclosure_search_spec": spec_payload,
                            }
                        }
                    )
                    for document in response_normalized_documents
                ]
            filtered_documents, filtered_normalized_documents, rejections = (
                _filter_weak_direct_documents(
                    task=task,
                    source_id=source_id,
                    documents=response_documents,
                    normalized_documents=response_normalized_documents,
                )
            )
            documents.extend(filtered_documents)
            normalized_documents.extend(filtered_normalized_documents)
            weak_document_rejections.extend(rejections)
            rejected_ids = {str(item.get("document_id")) for item in rejections}
            evidence_items.extend(
                evidence_item
                for evidence_item in response.evidence_items
                if evidence_item.citation.document_id not in rejected_ids
            )
            errors.extend(response.errors)
            if response.trace is not None:
                traces.append(response.trace)
            traces.extend(response.traces)

        if (
            task.task_family == "project_transaction"
            and self.enable_project_search_fallback
            and not documents
            and not normalized_documents
            and not evidence_items
        ):
            (
                fallback_documents,
                fallback_normalized_documents,
                fallback_evidence_items,
                fallback_errors,
                fallback_metadata,
            ) = self._run_project_search_fallback(
                task=task,
                lane_id=lane_id,
                existing_urls={
                    str(rejection.get("url"))
                    for rejection in weak_document_rejections
                    if rejection.get("url")
                },
            )
            documents.extend(fallback_documents)
            normalized_documents.extend(fallback_normalized_documents)
            evidence_items.extend(fallback_evidence_items)
            errors.extend(fallback_errors)
            metadata["project_search_fallback"] = fallback_metadata

        if (
            task.task_family == "data_metrics"
            and self.enable_data_metrics_search_fallback
            and not documents
            and not normalized_documents
            and not evidence_items
        ):
            (
                fallback_documents,
                fallback_normalized_documents,
                fallback_evidence_items,
                fallback_errors,
                fallback_metadata,
            ) = self._run_data_metrics_search_fallback(
                task=task,
                lane_id=lane_id,
                existing_urls={
                    str(rejection.get("url"))
                    for rejection in weak_document_rejections
                    if rejection.get("url")
                },
            )
            documents.extend(fallback_documents)
            normalized_documents.extend(fallback_normalized_documents)
            evidence_items.extend(fallback_evidence_items)
            errors.extend(fallback_errors)
            metadata["data_metrics_search_fallback"] = fallback_metadata

        if (
            task.task_family == "enterprise_disclosure"
            and disclosure_search_spec is not None
            and not documents
            and not normalized_documents
            and not evidence_items
        ):
            if self.enable_disclosure_api_fallback:
                (
                    fallback_documents,
                    fallback_normalized_documents,
                    fallback_evidence_items,
                    fallback_errors,
                    fallback_metadata,
                ) = self._run_disclosure_api_fallback(
                    task=task,
                    spec=disclosure_search_spec,
                )
                documents.extend(fallback_documents)
                normalized_documents.extend(fallback_normalized_documents)
                evidence_items.extend(fallback_evidence_items)
                errors.extend(fallback_errors)
                metadata["disclosure_api_fallback"] = fallback_metadata
            else:
                metadata["disclosure_api_fallback"] = {
                    "attempted": False,
                    "provider": "cninfo_direct_api",
                    "status": "disabled",
                    "estimated_tavily_credits": 0,
                }

        if documents or normalized_documents or evidence_items:
            state = DirectLaneExecutionState.EXECUTED_WITH_EVIDENCE
            status = ToolStatus.PARTIAL if errors else ToolStatus.SUCCESS
        elif weak_document_rejections:
            state = DirectLaneExecutionState.EXECUTED_WITHOUT_EVIDENCE
            status = ToolStatus.PARTIAL
        elif attempted and errors:
            state = DirectLaneExecutionState.FAILED_RUNTIME_ERROR
            status = ToolStatus.ERROR
        else:
            state = DirectLaneExecutionState.EXECUTED_WITHOUT_EVIDENCE
            status = ToolStatus.PARTIAL

        metadata.update(
            {
                "reason_code": state.value,
                "profiles_considered": source_ids_considered,
                "profiles_selected": available_source_ids,
                "profile_attempt_count": len(attempted),
                "document_count": len(documents),
                "normalized_document_count": len(normalized_documents),
                "evidence_count": len(evidence_items),
                "rejected_document_count": len(weak_document_rejections),
                "weak_document_rejections": weak_document_rejections[:20],
                "evidence_quality_summary": _evidence_quality_summary(
                    documents=documents,
                    normalized_documents=normalized_documents,
                    rejections=weak_document_rejections,
                ),
                "direct_budget_state": {
                    "max_profiles_per_lane": self.max_profiles_per_lane,
                    "max_documents_per_profile": self.max_documents_per_profile,
                    "max_evidence_per_profile": self.max_evidence_per_profile,
                    "used_profiles": len(attempted),
                },
            }
        )
        return DirectStructuredLaneExecutionResult(
            status=status,
            task_id=task.task_id,
            task_family=task.task_family,
            execution_bucket=task.execution_bucket,
            lane_id=lane_id.value if lane_id is not None else None,
            execution_state=state,
            source_ids_considered=source_ids_considered,
            source_ids_selected=available_source_ids,
            source_ids_attempted=attempted,
            documents=documents,
            normalized_documents=normalized_documents,
            evidence_items=evidence_items,
            errors=errors,
            traces=traces,
            metadata=metadata,
        )

    def _run_disclosure_api_fallback(
        self,
        *,
        task: QueryDecompositionTask,
        spec: DisclosureAnnouncementSearchSpec,
    ) -> tuple[
        list[RawDocument],
        list[NormalizedDocument],
        list[EvidenceItem],
        list[ToolError],
        dict[str, Any],
    ]:
        provider = self.disclosure_api_provider or CninfoDisclosureApiProvider()
        documents, normalized_documents, errors, metadata = provider.search(
            task=task,
            spec=spec,
            max_results=self.max_documents_per_profile,
        )
        filtered_documents, filtered_normalized_documents, rejections = (
            _filter_weak_direct_documents(
                task=task,
                source_id="cn_exchange_cninfo_announcement_v1",
                documents=list(documents),
                normalized_documents=list(normalized_documents),
            )
        )
        evidence_items = convert_search_assisted_documents_to_evidence_items(
            task=task,
            documents=filtered_documents,
            normalized_documents=filtered_normalized_documents,
            max_items=self.max_evidence_per_profile,
        )
        metadata.update(
            {
                "status": (
                    "evidence_found"
                    if filtered_documents or filtered_normalized_documents or evidence_items
                    else metadata.get("status", "no_results")
                ),
                "document_count": len(filtered_documents),
                "normalized_document_count": len(filtered_normalized_documents),
                "evidence_count": len(evidence_items),
                "rejected_document_count": len(rejections),
                "weak_document_rejections": rejections[:20],
                "evidence_quality_summary": _evidence_quality_summary(
                    documents=filtered_documents,
                    normalized_documents=filtered_normalized_documents,
                    rejections=rejections,
                ),
                "estimated_tavily_credits": 0,
            }
        )
        if (
            metadata["status"] == "evidence_found"
            and not filtered_documents
            and not filtered_normalized_documents
            and not evidence_items
        ):
            metadata["status"] = "extracted_without_usable_evidence"
        return (
            filtered_documents,
            filtered_normalized_documents,
            evidence_items,
            errors,
            metadata,
        )

    def _execute_official_record_task(
        self,
        *,
        task: QueryDecompositionTask,
        lane_id: CoverageLane | None,
        source_ids_considered: list[str],
        metadata: dict[str, Any],
    ) -> DirectStructuredLaneExecutionResult:
        if not self.enable_official_record_search_fallback:
            metadata["reason_code"] = "official_record_search_fallback_disabled"
            return self._empty_result(
                task=task,
                lane_id=lane_id,
                state=DirectLaneExecutionState.SKIPPED_UNSUPPORTED_SOURCE_CLASS,
                status=ToolStatus.UNSUPPORTED,
                source_ids_considered=source_ids_considered,
                metadata=metadata,
            )

        (
            documents,
            normalized_documents,
            evidence_items,
            errors,
            fallback_metadata,
        ) = self._run_official_record_search_fallback(
            task=task,
            lane_id=lane_id,
            existing_urls=set(),
        )
        metadata["official_record_search_fallback"] = fallback_metadata
        if documents or normalized_documents or evidence_items:
            state = DirectLaneExecutionState.EXECUTED_WITH_EVIDENCE
            status = ToolStatus.PARTIAL if errors else ToolStatus.SUCCESS
        elif errors and fallback_metadata.get("selected_candidate_count"):
            if _official_record_errors_are_nonfatal_pdf_gaps(errors, fallback_metadata):
                state = DirectLaneExecutionState.EXECUTED_WITHOUT_EVIDENCE
                status = ToolStatus.PARTIAL
            else:
                state = DirectLaneExecutionState.FAILED_RUNTIME_ERROR
                status = ToolStatus.ERROR
        else:
            state = DirectLaneExecutionState.EXECUTED_WITHOUT_EVIDENCE
            status = ToolStatus.PARTIAL

        metadata.update(
            {
                "reason_code": state.value,
                "profiles_considered": source_ids_considered,
                "profiles_selected": [],
                "profile_attempt_count": 0,
                "document_count": len(documents),
                "normalized_document_count": len(normalized_documents),
                "evidence_count": len(evidence_items),
                "rejected_document_count": fallback_metadata.get("rejected_document_count", 0),
                "weak_document_rejections": fallback_metadata.get(
                    "weak_document_rejections",
                    [],
                ),
                "evidence_quality_summary": fallback_metadata.get(
                    "evidence_quality_summary",
                    _evidence_quality_summary(
                        documents=documents,
                        normalized_documents=normalized_documents,
                        rejections=fallback_metadata.get("weak_document_rejections", []),
                    ),
                ),
                "direct_budget_state": {
                    "max_profiles_per_lane": self.max_profiles_per_lane,
                    "max_documents_per_profile": self.max_documents_per_profile,
                    "max_evidence_per_profile": self.max_evidence_per_profile,
                    "used_profiles": 0,
                },
            }
        )
        return DirectStructuredLaneExecutionResult(
            status=status,
            task_id=task.task_id,
            task_family=task.task_family,
            execution_bucket=task.execution_bucket,
            lane_id=lane_id.value if lane_id is not None else None,
            execution_state=state,
            source_ids_considered=source_ids_considered,
            source_ids_selected=[],
            source_ids_attempted=[],
            documents=documents,
            normalized_documents=normalized_documents,
            evidence_items=evidence_items,
            errors=errors,
            metadata=metadata,
        )

    def _run_project_search_fallback(
        self,
        *,
        task: QueryDecompositionTask,
        lane_id: CoverageLane | None,
        existing_urls: set[str],
    ) -> tuple[
        list[RawDocument],
        list[NormalizedDocument],
        list[EvidenceItem],
        list[ToolError],
        dict[str, Any],
    ]:
        metadata: dict[str, Any] = {
            "attempted": True,
            "provider": "tavily_plus_crawl4ai",
            "reason": "direct_project_profiles_returned_no_usable_evidence",
            "max_candidates": self.max_project_fallback_candidates,
            "max_estimated_tavily_credits": self.max_project_fallback_search_credits,
            "budget_state": {
                "max_search_credits": self.max_project_fallback_search_credits,
                "used_search_credits": 0,
            },
            "search_response_count": 0,
            "candidate_decisions": [],
            "selected_candidate_count": 0,
            "estimated_tavily_credits": 0,
            "file_candidate_count": 0,
            "file_candidate_kinds": {},
            "stop_reason": None,
        }
        search_provider = self.project_search_provider or TavilySearchAdapter()
        extraction_provider = self.project_extraction_provider or Crawl4AIExtractionService()
        candidate_inputs: list[SearchUrlCandidate] = []
        pdf_candidate_inputs: list[SearchUrlCandidate] = []
        candidate_decisions: list[dict[str, Any]] = []
        errors: list[ToolError] = []
        seen_urls = set(existing_urls)

        for phrase_index, phrase in enumerate(task.search_phrases[:3], start=1):
            if (
                metadata["budget_state"]["used_search_credits"]
                >= self.max_project_fallback_search_credits
            ):
                metadata["stop_reason"] = "search_credit_budget_exhausted"
                break
            search_response = search_provider.search(
                TavilySearchRequest(
                    query=phrase,
                    include_domains=task.include_domains,
                    exclude_domains=task.exclude_domains,
                    max_results=max(self.max_project_fallback_candidates, 3),
                    search_depth="basic",
                    auto_parameters=False,
                    include_answer=False,
                    include_raw_content=False,
                )
            )
            metadata["search_response_count"] += 1
            search_credits = (
                search_response.usage.estimated_credits
                if search_response.usage is not None
                else 1
            )
            metadata["estimated_tavily_credits"] += search_credits
            metadata["budget_state"]["used_search_credits"] += search_credits
            errors.extend(search_response.errors)

            prioritized_results = _prioritize_project_search_results(
                search_response.results
            )
            for result_index, result in enumerate(prioritized_results, start=1):
                candidate_id = f"{task.task_id}_project_search_{phrase_index}_{result_index}"
                local_region_match = _local_region_match_for_search_candidate(
                    task=task,
                    result=result,
                )
                reason_code = _project_search_candidate_rejection_reason(
                    task=task,
                    result=result,
                    seen_urls=seen_urls,
                )
                if reason_code is not None:
                    candidate_decisions.append(
                        {
                            "candidate_id": candidate_id,
                            "url": result.url,
                            "title": result.title,
                            "decision": "reject",
                            "reason_code": reason_code,
                            "query": search_response.query,
                            **_local_region_match_metadata(local_region_match),
                        }
                    )
                    continue

                file_candidate_kind = _direct_lane_file_candidate_kind(result.url)
                if file_candidate_kind is not None:
                    seen_urls.add(result.url)
                    metadata["file_candidate_count"] += 1
                    _increment_failure_class(
                        metadata["file_candidate_kinds"],
                        file_candidate_kind,
                    )
                    if file_candidate_kind == "pdf":
                        candidate_decisions.append(
                            {
                                "candidate_id": candidate_id,
                                "url": result.url,
                                "title": result.title,
                                "decision": "accept",
                                "reason_code": "accepted_project_pdf_fallback",
                                "query": search_response.query,
                                "candidate_kind": "pdf",
                                "file_candidate_kind": file_candidate_kind,
                                **_local_region_match_metadata(local_region_match),
                            }
                        )
                        pdf_candidate_inputs.append(
                            SearchUrlCandidate(
                                candidate_id=candidate_id,
                                url=result.url,
                                source_id="search_assisted_project_fallback",
                                source_name_hint="Project Search Fallback",
                                title_hint=result.title,
                                snippet_hint=result.content,
                                published_at_hint=result.published_date,
                                discovery_provider="tavily",
                                discovery_query=search_response.query,
                                discovery_score=result.score,
                                task_family=task.task_family,
                                execution_bucket=task.execution_bucket,
                                source_cluster=task.source_cluster,
                                include_domains=task.include_domains,
                                metadata={
                                    "lane_id": (
                                        lane_id.value if lane_id is not None else None
                                    ),
                                    "project_search_fallback": True,
                                    "project_pdf_fallback": True,
                                    "file_candidate_kind": file_candidate_kind,
                                    **_local_region_match_metadata(local_region_match),
                                },
                            )
                        )
                        if (
                            len(candidate_inputs) + len(pdf_candidate_inputs)
                            >= self.max_project_fallback_candidates
                        ):
                            metadata["stop_reason"] = "candidate_limit_reached"
                            break
                        continue
                    candidate_decisions.append(
                        {
                            "candidate_id": candidate_id,
                            "url": result.url,
                            "title": result.title,
                            "decision": "reject",
                            "reason_code": "project_file_requires_adapter",
                            "query": search_response.query,
                            "file_candidate_kind": file_candidate_kind,
                            "extraction_failure_class": "file_or_download",
                            "extraction_failure_stage": "candidate_classification",
                            **_local_region_match_metadata(local_region_match),
                        }
                    )
                    errors.append(
                        ToolError(
                            code=ToolErrorCode.UNSUPPORTED_OPERATION,
                            message=(
                                "Project fallback file/download candidate requires "
                                "a file adapter before it can be counted as evidence."
                            ),
                            retryable=False,
                            detail={
                                "candidate_id": candidate_id,
                                "url": result.url,
                                "reason_code": "project_file_requires_adapter",
                                "file_candidate_kind": file_candidate_kind,
                                "extraction_failure_class": "file_or_download",
                                "extraction_failure_stage": "candidate_classification",
                                "task_family": task.task_family,
                            },
                        )
                    )
                    continue

                seen_urls.add(result.url)
                candidate_decisions.append(
                    {
                        "candidate_id": candidate_id,
                        "url": result.url,
                        "title": result.title,
                        "decision": "accept",
                        "reason_code": "accepted_project_search_fallback",
                        "query": search_response.query,
                        **_local_region_match_metadata(local_region_match),
                    }
                )
                candidate_inputs.append(
                    SearchUrlCandidate(
                        candidate_id=candidate_id,
                        url=result.url,
                        source_id="search_assisted_project_fallback",
                        source_name_hint="Project Search Fallback",
                        title_hint=result.title,
                        snippet_hint=result.content,
                        published_at_hint=result.published_date,
                        discovery_provider="tavily",
                        discovery_query=search_response.query,
                        discovery_score=result.score,
                        task_family=task.task_family,
                        execution_bucket=task.execution_bucket,
                        source_cluster=task.source_cluster,
                        include_domains=task.include_domains,
                        metadata={
                            "lane_id": lane_id.value if lane_id is not None else None,
                            "project_search_fallback": True,
                            **_local_region_match_metadata(local_region_match),
                        },
                    )
                )
                if (
                    len(candidate_inputs) + len(pdf_candidate_inputs)
                    >= self.max_project_fallback_candidates
                ):
                    metadata["stop_reason"] = "candidate_limit_reached"
                    break
            if (
                len(candidate_inputs) + len(pdf_candidate_inputs)
                >= self.max_project_fallback_candidates
            ):
                break

        metadata["candidate_decisions"] = candidate_decisions[:20]
        metadata["selected_candidate_count"] = len(candidate_inputs) + len(
            pdf_candidate_inputs
        )
        if not candidate_inputs and not pdf_candidate_inputs:
            if metadata["file_candidate_count"]:
                metadata["status"] = "file_candidates_require_adapter"
            else:
                metadata["status"] = (
                    "search_credit_budget_exhausted"
                    if metadata.get("stop_reason") == "search_credit_budget_exhausted"
                    else "no_accepted_candidates"
                )
            return [], [], [], errors, metadata

        extracted_documents: list[RawDocument] = []
        extracted_normalized_documents: list[NormalizedDocument] = []
        extraction_metadata: dict[str, Any] = {
            "provider": "crawl4ai_plus_static_pdf",
            "requested": len(candidate_inputs) + len(pdf_candidate_inputs),
            "succeeded": 0,
            "failed": 0,
        }
        if candidate_inputs:
            extraction_response = extraction_provider.extract(
                Crawl4AIExtractionRequest(
                    inputs=candidate_inputs,
                    allow_supplemental_direct_keep=True,
                )
            )
            errors.extend(extraction_response.errors)
            extracted_documents.extend(extraction_response.documents)
            extracted_normalized_documents.extend(extraction_response.normalized_documents)
            extraction_metadata["html"] = extraction_response.metadata
            extraction_metadata["succeeded"] += int(
                extraction_response.metadata.get("succeeded", 0) or 0
            )
            extraction_metadata["failed"] += len(extraction_response.errors)
        if pdf_candidate_inputs:
            pdf_documents, pdf_normalized_documents, pdf_errors, pdf_metadata = (
                self._extract_official_record_pdf_candidates(
                    pdf_candidate_inputs,
                    source_class="tender_or_procurement",
                    fallback_metadata_key="project_pdf_fallback",
                    failure_label="Project PDF",
                )
            )
            errors.extend(pdf_errors)
            extracted_documents.extend(pdf_documents)
            extracted_normalized_documents.extend(pdf_normalized_documents)
            extraction_metadata["pdf"] = pdf_metadata
            extraction_metadata["succeeded"] += pdf_metadata.get("succeeded", 0)
            extraction_metadata["failed"] += pdf_metadata.get("failed", 0)
            metadata["pdf_extraction"] = pdf_metadata
        filtered_documents, filtered_normalized_documents, rejections = (
            _filter_weak_direct_documents(
                task=task,
                source_id="search_assisted_project_fallback",
                documents=extracted_documents,
                normalized_documents=extracted_normalized_documents,
            )
        )
        evidence_items = convert_search_assisted_documents_to_evidence_items(
            task=task,
            documents=filtered_documents,
            normalized_documents=filtered_normalized_documents,
            max_items=self.max_evidence_per_profile,
        )
        metadata.update(
            {
                "status": (
                    "evidence_found"
                    if filtered_documents or filtered_normalized_documents or evidence_items
                    else "extracted_without_usable_evidence"
                ),
                "extraction": extraction_metadata,
                "document_count": len(filtered_documents),
                "normalized_document_count": len(filtered_normalized_documents),
                "evidence_count": len(evidence_items),
                "rejected_document_count": len(rejections),
                "weak_document_rejections": rejections[:20],
                "evidence_quality_summary": _evidence_quality_summary(
                    documents=filtered_documents,
                    normalized_documents=filtered_normalized_documents,
                    rejections=rejections,
                ),
            }
        )
        return (
            filtered_documents,
            filtered_normalized_documents,
            evidence_items,
            errors,
            metadata,
        )

    def _run_data_metrics_search_fallback(
        self,
        *,
        task: QueryDecompositionTask,
        lane_id: CoverageLane | None,
        existing_urls: set[str],
    ) -> tuple[
        list[RawDocument],
        list[NormalizedDocument],
        list[EvidenceItem],
        list[ToolError],
        dict[str, Any],
    ]:
        metadata: dict[str, Any] = {
            "attempted": True,
            "provider": "tavily_plus_crawl4ai",
            "reason": "direct_data_profiles_returned_no_usable_evidence",
            "max_candidates": self.max_data_metrics_fallback_candidates,
            "max_estimated_tavily_credits": self.max_data_metrics_fallback_search_credits,
            "budget_state": {
                "max_search_credits": self.max_data_metrics_fallback_search_credits,
                "used_search_credits": 0,
            },
            "search_response_count": 0,
            "candidate_decisions": [],
            "selected_candidate_count": 0,
            "estimated_tavily_credits": 0,
            "file_candidate_count": 0,
            "file_candidate_kinds": {},
            "stop_reason": None,
        }
        search_provider = self.data_metrics_search_provider or TavilySearchAdapter()
        extraction_provider = self.data_metrics_extraction_provider or Crawl4AIExtractionService()
        candidate_inputs: list[SearchUrlCandidate] = []
        pdf_candidate_inputs: list[SearchUrlCandidate] = []
        candidate_decisions: list[dict[str, Any]] = []
        errors: list[ToolError] = []
        seen_urls = set(existing_urls)

        for phrase_index, phrase in enumerate(task.search_phrases[:3], start=1):
            if (
                metadata["budget_state"]["used_search_credits"]
                >= self.max_data_metrics_fallback_search_credits
            ):
                metadata["stop_reason"] = "search_credit_budget_exhausted"
                break
            search_response = search_provider.search(
                TavilySearchRequest(
                    query=phrase,
                    include_domains=task.include_domains,
                    exclude_domains=task.exclude_domains,
                    max_results=max(self.max_data_metrics_fallback_candidates, 3),
                    search_depth="basic",
                    auto_parameters=False,
                    include_answer=False,
                    include_raw_content=False,
                )
            )
            metadata["search_response_count"] += 1
            search_credits = (
                search_response.usage.estimated_credits
                if search_response.usage is not None
                else 1
            )
            metadata["estimated_tavily_credits"] += search_credits
            metadata["budget_state"]["used_search_credits"] += search_credits
            errors.extend(search_response.errors)

            for result_index, result in enumerate(search_response.results, start=1):
                candidate_id = f"{task.task_id}_data_search_{phrase_index}_{result_index}"
                local_region_match = _local_region_match_for_search_candidate(
                    task=task,
                    result=result,
                )
                reason_code = _data_metrics_search_candidate_rejection_reason(
                    task=task,
                    result=result,
                    seen_urls=seen_urls,
                )
                if reason_code is not None:
                    candidate_decisions.append(
                        {
                            "candidate_id": candidate_id,
                            "url": result.url,
                            "title": result.title,
                            "decision": "reject",
                            "reason_code": reason_code,
                            "query": search_response.query,
                            **_local_region_match_metadata(local_region_match),
                        }
                    )
                    continue

                file_candidate_kind = _direct_lane_file_candidate_kind(result.url)
                if file_candidate_kind is not None:
                    seen_urls.add(result.url)
                    metadata["file_candidate_count"] += 1
                    _increment_failure_class(
                        metadata["file_candidate_kinds"],
                        file_candidate_kind,
                    )
                    if file_candidate_kind == "pdf":
                        candidate_decisions.append(
                            {
                                "candidate_id": candidate_id,
                                "url": result.url,
                                "title": result.title,
                                "decision": "accept",
                                "reason_code": "accepted_data_metrics_pdf_fallback",
                                "query": search_response.query,
                                "candidate_kind": "pdf",
                                "file_candidate_kind": file_candidate_kind,
                                **_local_region_match_metadata(local_region_match),
                            }
                        )
                        pdf_candidate_inputs.append(
                            SearchUrlCandidate(
                                candidate_id=candidate_id,
                                url=result.url,
                                source_id="search_assisted_data_metrics_fallback",
                                source_name_hint="Data Metrics Search Fallback",
                                title_hint=result.title,
                                snippet_hint=result.content,
                                published_at_hint=result.published_date,
                                discovery_provider="tavily",
                                discovery_query=search_response.query,
                                discovery_score=result.score,
                                task_family=task.task_family,
                                execution_bucket=task.execution_bucket,
                                source_cluster=task.source_cluster,
                                include_domains=task.include_domains,
                                metadata={
                                    "lane_id": (
                                        lane_id.value if lane_id is not None else None
                                    ),
                                    "data_metrics_search_fallback": True,
                                    "data_metrics_pdf_fallback": True,
                                    "file_candidate_kind": file_candidate_kind,
                                    **_local_region_match_metadata(local_region_match),
                                },
                            )
                        )
                        if (
                            len(candidate_inputs) + len(pdf_candidate_inputs)
                            >= self.max_data_metrics_fallback_candidates
                        ):
                            metadata["stop_reason"] = "candidate_limit_reached"
                            break
                        continue
                    candidate_decisions.append(
                        {
                            "candidate_id": candidate_id,
                            "url": result.url,
                            "title": result.title,
                            "decision": "reject",
                            "reason_code": "data_metrics_file_requires_adapter",
                            "query": search_response.query,
                            "file_candidate_kind": file_candidate_kind,
                            "extraction_failure_class": "file_or_download",
                            "extraction_failure_stage": "candidate_classification",
                            **_local_region_match_metadata(local_region_match),
                        }
                    )
                    errors.append(
                        ToolError(
                            code=ToolErrorCode.UNSUPPORTED_OPERATION,
                            message=(
                                "Data metrics file/download candidate requires "
                                f"a file adapter: {result.url}"
                            ),
                            retryable=False,
                            detail={
                                "candidate_id": candidate_id,
                                "url": result.url,
                                "reason_code": "data_metrics_file_requires_adapter",
                                "file_candidate_kind": file_candidate_kind,
                                "extraction_failure_class": "file_or_download",
                                "extraction_failure_stage": "candidate_classification",
                                "task_family": task.task_family,
                            },
                        )
                    )
                    continue

                seen_urls.add(result.url)
                candidate_decisions.append(
                    {
                        "candidate_id": candidate_id,
                        "url": result.url,
                        "title": result.title,
                        "decision": "accept",
                        "reason_code": "accepted_data_metrics_search_fallback",
                        "query": search_response.query,
                        **_local_region_match_metadata(local_region_match),
                    }
                )
                candidate_inputs.append(
                    SearchUrlCandidate(
                        candidate_id=candidate_id,
                        url=result.url,
                        source_id="search_assisted_data_metrics_fallback",
                        source_name_hint="Data Metrics Search Fallback",
                        title_hint=result.title,
                        snippet_hint=result.content,
                        published_at_hint=result.published_date,
                        discovery_provider="tavily",
                        discovery_query=search_response.query,
                        discovery_score=result.score,
                        task_family=task.task_family,
                        execution_bucket=task.execution_bucket,
                        source_cluster=task.source_cluster,
                        include_domains=task.include_domains,
                        metadata={
                            "lane_id": lane_id.value if lane_id is not None else None,
                            "data_metrics_search_fallback": True,
                            **_local_region_match_metadata(local_region_match),
                        },
                    )
                )
                if (
                    len(candidate_inputs) + len(pdf_candidate_inputs)
                    >= self.max_data_metrics_fallback_candidates
                ):
                    metadata["stop_reason"] = "candidate_limit_reached"
                    break
            if (
                len(candidate_inputs) + len(pdf_candidate_inputs)
                >= self.max_data_metrics_fallback_candidates
            ):
                break

        metadata["candidate_decisions"] = candidate_decisions[:20]
        metadata["selected_candidate_count"] = len(candidate_inputs) + len(
            pdf_candidate_inputs
        )
        if not candidate_inputs and not pdf_candidate_inputs:
            if metadata["file_candidate_count"]:
                metadata["status"] = "file_candidates_require_adapter"
            else:
                metadata["status"] = (
                    "search_credit_budget_exhausted"
                    if metadata.get("stop_reason") == "search_credit_budget_exhausted"
                    else "no_accepted_candidates"
                )
            return [], [], [], errors, metadata

        extracted_documents: list[RawDocument] = []
        extracted_normalized_documents: list[NormalizedDocument] = []
        extraction_metadata: dict[str, Any] = {
            "provider": "crawl4ai_plus_static_pdf",
            "requested": len(candidate_inputs) + len(pdf_candidate_inputs),
            "succeeded": 0,
            "failed": 0,
        }
        if candidate_inputs:
            extraction_response = extraction_provider.extract(
                Crawl4AIExtractionRequest(
                    inputs=candidate_inputs,
                    allow_supplemental_direct_keep=True,
                )
            )
            errors.extend(extraction_response.errors)
            extracted_documents.extend(extraction_response.documents)
            extracted_normalized_documents.extend(extraction_response.normalized_documents)
            extraction_metadata["html"] = extraction_response.metadata
            extraction_metadata["succeeded"] += int(
                extraction_response.metadata.get("succeeded", 0) or 0
            )
            extraction_metadata["failed"] += len(extraction_response.errors)
        if pdf_candidate_inputs:
            pdf_documents, pdf_normalized_documents, pdf_errors, pdf_metadata = (
                self._extract_official_record_pdf_candidates(
                    pdf_candidate_inputs,
                    source_class="statistics",
                    fallback_metadata_key="data_metrics_pdf_fallback",
                    failure_label="Data metrics PDF",
                )
            )
            errors.extend(pdf_errors)
            extracted_documents.extend(pdf_documents)
            extracted_normalized_documents.extend(pdf_normalized_documents)
            extraction_metadata["pdf"] = pdf_metadata
            extraction_metadata["succeeded"] += pdf_metadata.get("succeeded", 0)
            extraction_metadata["failed"] += pdf_metadata.get("failed", 0)
            metadata["pdf_extraction"] = pdf_metadata
        filtered_documents, filtered_normalized_documents, rejections = (
            _filter_weak_direct_documents(
                task=task,
                source_id="search_assisted_data_metrics_fallback",
                documents=extracted_documents,
                normalized_documents=extracted_normalized_documents,
            )
        )
        evidence_items = convert_search_assisted_documents_to_evidence_items(
            task=task,
            documents=filtered_documents,
            normalized_documents=filtered_normalized_documents,
            max_items=self.max_evidence_per_profile,
        )
        metadata.update(
            {
                "status": (
                    "evidence_found"
                    if filtered_documents or filtered_normalized_documents or evidence_items
                    else "extracted_without_usable_evidence"
                ),
                "extraction": extraction_metadata,
                "document_count": len(filtered_documents),
                "normalized_document_count": len(filtered_normalized_documents),
                "evidence_count": len(evidence_items),
                "rejected_document_count": len(rejections),
                "weak_document_rejections": rejections[:20],
                "evidence_quality_summary": _evidence_quality_summary(
                    documents=filtered_documents,
                    normalized_documents=filtered_normalized_documents,
                    rejections=rejections,
                ),
            }
        )
        return (
            filtered_documents,
            filtered_normalized_documents,
            evidence_items,
            errors,
            metadata,
        )

    def _run_official_record_search_fallback(
        self,
        *,
        task: QueryDecompositionTask,
        lane_id: CoverageLane | None,
        existing_urls: set[str],
    ) -> tuple[
        list[RawDocument],
        list[NormalizedDocument],
        list[EvidenceItem],
        list[ToolError],
        dict[str, Any],
    ]:
        metadata: dict[str, Any] = {
            "attempted": True,
            "provider": "tavily_plus_crawl4ai",
            "reason": "official_record_direct_adapter_not_available",
            "max_candidates": self.max_official_record_fallback_candidates,
            "max_estimated_tavily_credits": (
                self.max_official_record_fallback_search_credits
            ),
            "budget_state": {
                "max_search_credits": (
                    self.max_official_record_fallback_search_credits
                ),
                "used_search_credits": 0,
            },
            "search_response_count": 0,
            "candidate_decisions": [],
            "selected_candidate_count": 0,
            "estimated_tavily_credits": 0,
            "stop_reason": None,
        }
        search_provider = self.official_record_search_provider or TavilySearchAdapter()
        extraction_provider = (
            self.official_record_extraction_provider or Crawl4AIExtractionService()
        )
        candidate_inputs: list[SearchUrlCandidate] = []
        pdf_candidate_inputs: list[SearchUrlCandidate] = []
        candidate_decisions: list[dict[str, Any]] = []
        errors: list[ToolError] = []
        seen_urls = set(existing_urls)

        for phrase_index, phrase in enumerate(task.search_phrases[:3], start=1):
            if (
                metadata["budget_state"]["used_search_credits"]
                >= self.max_official_record_fallback_search_credits
            ):
                metadata["stop_reason"] = "search_credit_budget_exhausted"
                break
            search_response = search_provider.search(
                TavilySearchRequest(
                    query=phrase,
                    include_domains=task.include_domains,
                    exclude_domains=task.exclude_domains,
                    max_results=max(self.max_official_record_fallback_candidates, 3),
                    search_depth="basic",
                    auto_parameters=False,
                    include_answer=False,
                    include_raw_content=False,
                )
            )
            metadata["search_response_count"] += 1
            search_credits = (
                search_response.usage.estimated_credits
                if search_response.usage is not None
                else 1
            )
            metadata["estimated_tavily_credits"] += search_credits
            metadata["budget_state"]["used_search_credits"] += search_credits
            errors.extend(search_response.errors)

            for result_index, result in enumerate(search_response.results, start=1):
                candidate_id = (
                    f"{task.task_id}_official_record_search_{phrase_index}_{result_index}"
                )
                reason_code = _official_record_search_candidate_rejection_reason(
                    task=task,
                    result=result,
                    seen_urls=seen_urls,
                    enable_pdf_fallback=self.enable_official_record_pdf_fallback,
                )
                if reason_code is not None:
                    candidate_decisions.append(
                        {
                            "candidate_id": candidate_id,
                            "url": result.url,
                            "title": result.title,
                            "decision": "reject",
                            "reason_code": reason_code,
                            "query": search_response.query,
                        }
                    )
                    continue

                seen_urls.add(result.url)
                is_pdf_candidate = _is_pdf_url(result.url)
                search_candidate = SearchUrlCandidate(
                    candidate_id=candidate_id,
                    url=result.url,
                    source_id="search_assisted_official_record_fallback",
                    source_name_hint="Official Record Search Fallback",
                    title_hint=result.title,
                    snippet_hint=result.content,
                    published_at_hint=result.published_date,
                    discovery_provider="tavily",
                    discovery_query=search_response.query,
                    discovery_score=result.score,
                    task_family=task.task_family,
                    execution_bucket=task.execution_bucket,
                    source_cluster=task.source_cluster,
                    include_domains=task.include_domains,
                    metadata={
                        "lane_id": lane_id.value if lane_id is not None else None,
                        "official_record_search_fallback": True,
                        "source_class": "environmental_or_land_record",
                    },
                )
                candidate_decisions.append(
                    {
                        "candidate_id": candidate_id,
                        "url": result.url,
                        "title": result.title,
                        "decision": "accept",
                        "reason_code": (
                            "accepted_official_record_pdf_fallback"
                            if is_pdf_candidate
                            else "accepted_official_record_search_fallback"
                        ),
                        "query": search_response.query,
                        "candidate_kind": "pdf" if is_pdf_candidate else "html",
                    }
                )
                if is_pdf_candidate:
                    pdf_candidate_inputs.append(search_candidate)
                else:
                    candidate_inputs.append(search_candidate)
                selected_count = len(candidate_inputs) + len(pdf_candidate_inputs)
                if selected_count >= self.max_official_record_fallback_candidates:
                    metadata["stop_reason"] = "candidate_limit_reached"
                    break
            selected_count = len(candidate_inputs) + len(pdf_candidate_inputs)
            if selected_count >= self.max_official_record_fallback_candidates:
                break

        metadata["candidate_decisions"] = candidate_decisions[:20]
        metadata["selected_candidate_count"] = len(candidate_inputs) + len(pdf_candidate_inputs)
        metadata["selected_html_candidate_count"] = len(candidate_inputs)
        metadata["selected_pdf_candidate_count"] = len(pdf_candidate_inputs)
        if not candidate_inputs and not pdf_candidate_inputs:
            metadata["status"] = (
                "search_credit_budget_exhausted"
                if metadata.get("stop_reason") == "search_credit_budget_exhausted"
                else "no_accepted_candidates"
            )
            return [], [], [], errors, metadata

        extracted_documents: list[RawDocument] = []
        extracted_normalized_documents: list[NormalizedDocument] = []
        extraction_metadata: dict[str, Any] = {
            "provider": "crawl4ai_plus_static_pdf",
            "requested": len(candidate_inputs) + len(pdf_candidate_inputs),
            "succeeded": 0,
            "failed": 0,
        }
        if candidate_inputs:
            extraction_response = extraction_provider.extract(
                Crawl4AIExtractionRequest(
                    inputs=candidate_inputs,
                    allow_supplemental_direct_keep=True,
                )
            )
            errors.extend(extraction_response.errors)
            extracted_documents.extend(extraction_response.documents)
            extracted_normalized_documents.extend(extraction_response.normalized_documents)
            extraction_metadata["crawl4ai"] = extraction_response.metadata
            extraction_metadata["succeeded"] += len(extraction_response.documents)
            extraction_metadata["failed"] += len(extraction_response.errors)
        if pdf_candidate_inputs:
            pdf_documents, pdf_normalized_documents, pdf_errors, pdf_metadata = (
                self._extract_official_record_pdf_candidates(pdf_candidate_inputs)
            )
            errors.extend(pdf_errors)
            extracted_documents.extend(pdf_documents)
            extracted_normalized_documents.extend(pdf_normalized_documents)
            extraction_metadata["pdf"] = pdf_metadata
            extraction_metadata["succeeded"] += pdf_metadata.get("succeeded", 0)
            extraction_metadata["failed"] += pdf_metadata.get("failed", 0)
            metadata["pdf_extraction"] = pdf_metadata
        filtered_documents, filtered_normalized_documents, rejections = (
            _filter_weak_direct_documents(
                task=task,
                source_id="search_assisted_official_record_fallback",
                documents=extracted_documents,
                normalized_documents=extracted_normalized_documents,
            )
        )
        evidence_items = convert_search_assisted_documents_to_evidence_items(
            task=task,
            documents=filtered_documents,
            normalized_documents=filtered_normalized_documents,
            max_items=self.max_evidence_per_profile,
        )
        metadata.update(
            {
                "status": (
                    "evidence_found"
                    if filtered_documents or filtered_normalized_documents or evidence_items
                    else "extracted_without_usable_evidence"
                ),
                "extraction": extraction_metadata,
                "document_count": len(filtered_documents),
                "normalized_document_count": len(filtered_normalized_documents),
                "evidence_count": len(evidence_items),
                "rejected_document_count": len(rejections),
                "weak_document_rejections": rejections[:20],
                "evidence_quality_summary": _evidence_quality_summary(
                    documents=filtered_documents,
                    normalized_documents=filtered_normalized_documents,
                    rejections=rejections,
                ),
            }
        )
        return (
            filtered_documents,
            filtered_normalized_documents,
            evidence_items,
            errors,
            metadata,
        )

    def _extract_official_record_pdf_candidates(
        self,
        candidates: list[SearchUrlCandidate],
        *,
        source_class: str = "environmental_or_land_record",
        fallback_metadata_key: str = "official_record_pdf_fallback",
        failure_label: str = "Official-record PDF",
    ) -> tuple[
        list[RawDocument],
        list[NormalizedDocument],
        list[ToolError],
        dict[str, Any],
    ]:
        metadata: dict[str, Any] = {
            "provider": "static_pdf",
            "requested": len(candidates),
            "succeeded": 0,
            "failed": 0,
            "pages_extracted": 0,
            "retry_count": 0,
            "failure_classes": {},
        }
        if not candidates:
            return [], [], [], metadata

        download_service = self.official_record_pdf_download_service or LivePdfDownloadService()
        text_service = self.official_record_pdf_text_service or PdfTextExtractionService()
        documents: list[RawDocument] = []
        normalized_documents: list[NormalizedDocument] = []
        errors: list[ToolError] = []

        for candidate in candidates:
            filename = _filename_from_url(candidate.url) or f"{candidate.candidate_id}.pdf"
            artifact = PdfArtifact(
                artifact_id=f"{candidate.candidate_id}_pdf",
                source_id=candidate.source_id,
                url=candidate.url,
                title=candidate.title_hint,
                filename=filename,
                attachment_ref=filename,
                metadata={
                    "candidate_id": candidate.candidate_id,
                    "source_class": source_class,
                },
            )
            try:
                download = download_service.download_pdf(
                    candidate.url,
                    source_id=candidate.source_id,
                    attachment_ref=filename,
                )
                metadata["retry_count"] += int(getattr(download, "retry_count", 0) or 0)
                downloaded_artifact = artifact.model_copy(
                    update={
                        "url": str(getattr(download, "final_url", None) or candidate.url),
                        "checksum_sha256": getattr(download, "sha256", None),
                        "metadata": {
                            **artifact.metadata,
                            "download": _safe_pdf_download_dict(download),
                        },
                    }
                )
                pdf_document = text_service.extract_from_file(
                    file_path=str(download.file_path),
                    source_id=candidate.source_id,
                    artifact=downloaded_artifact,
                    title=candidate.title_hint,
                    max_pages=self.max_official_record_pdf_pages,
                    metadata={
                        "attachment_ref": filename,
                        "attachment_url": downloaded_artifact.url,
                        "requested_url": candidate.url,
                        "final_url": downloaded_artifact.url,
                        "source_name_hint": candidate.source_name_hint,
                        "title_hint": candidate.title_hint,
                        "snippet_hint": candidate.snippet_hint,
                        "published_at_hint": candidate.published_at_hint,
                        "discovery_provider": candidate.discovery_provider,
                        "discovery_query": candidate.discovery_query,
                        "discovery_score": candidate.discovery_score,
                        "task_family": candidate.task_family,
                        "execution_bucket": candidate.execution_bucket,
                        "source_cluster": candidate.source_cluster,
                        "include_domains": candidate.include_domains,
                        fallback_metadata_key: True,
                        "source_class": source_class,
                        **candidate.metadata,
                    },
                )
                raw_document, normalized_document = normalize_pdf_text_to_documents(
                    pdf_document,
                    title=candidate.title_hint,
                    published_at=_parse_direct_lane_datetime(candidate.published_at_hint),
                )
                shared_metadata = {
                    "provider": "static_pdf",
                    "requested_url": candidate.url,
                    "final_url": downloaded_artifact.url,
                    "from_pdf_attachment": True,
                    fallback_metadata_key: True,
                    "source_name_hint": candidate.source_name_hint,
                    "title_hint": candidate.title_hint,
                    "snippet_hint": candidate.snippet_hint,
                    "published_at_hint": candidate.published_at_hint,
                    "discovery_provider": candidate.discovery_provider,
                    "discovery_query": candidate.discovery_query,
                    "discovery_score": candidate.discovery_score,
                    "task_family": candidate.task_family,
                    "execution_bucket": candidate.execution_bucket,
                    "source_cluster": candidate.source_cluster,
                    "include_domains": candidate.include_domains,
                    "source_class": source_class,
                    **candidate.metadata,
                }
                raw_document.metadata = {**raw_document.metadata, **shared_metadata}
                normalized_document.metadata = {
                    **normalized_document.metadata,
                    **shared_metadata,
                }
                documents.append(raw_document)
                normalized_documents.append(normalized_document)
                metadata["succeeded"] += 1
                metadata["pages_extracted"] += len(pdf_document.pages)
                warnings = list(getattr(download, "warnings", []) or [])
                if warnings:
                    metadata.setdefault("warnings", []).extend(
                        [f"pdf_download:{warning}" for warning in warnings]
                    )
            except LivePdfDownloadError as exc:
                metadata["failed"] += 1
                _increment_failure_class(metadata["failure_classes"], "pdf_download_failed")
                errors.append(
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=(
                            f"{failure_label} download failed for "
                            f"'{candidate.url}': {exc}"
                        ),
                        retryable=exc.retryable,
                        detail={
                            **exc.to_dict(),
                            "url": candidate.url,
                            "candidate_id": candidate.candidate_id,
                            "extraction_failure_class": "pdf_or_download",
                            "extraction_failure_stage": "download",
                        },
                    )
                )
            except PdfTextExtractionError as exc:
                metadata["failed"] += 1
                _increment_failure_class(metadata["failure_classes"], exc.error_code)
                errors.append(
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=(
                            f"{failure_label} text extraction failed for "
                            f"'{candidate.url}': {exc}"
                        ),
                        retryable=False,
                        detail={
                            **exc.to_dict(),
                            "url": candidate.url,
                            "candidate_id": candidate.candidate_id,
                            "extraction_failure_class": "pdf_or_download",
                            "extraction_failure_stage": "text_extraction",
                        },
                    )
                )
            except Exception as exc:  # noqa: BLE001
                metadata["failed"] += 1
                _increment_failure_class(metadata["failure_classes"], "pdf_runtime_error")
                errors.append(
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=(
                            f"Unexpected {failure_label} extraction failure for "
                            f"'{candidate.url}': {exc}"
                        ),
                        retryable=False,
                        detail={
                            "url": candidate.url,
                            "candidate_id": candidate.candidate_id,
                            "extraction_failure_class": "pdf_or_download",
                            "extraction_failure_stage": "runtime",
                        },
                    )
                )

        return documents, normalized_documents, errors, metadata

    def _empty_result(
        self,
        *,
        task: QueryDecompositionTask,
        lane_id: CoverageLane | None,
        state: DirectLaneExecutionState,
        status: ToolStatus,
        source_ids_considered: list[str],
        metadata: dict[str, Any],
        error: ToolError | None = None,
    ) -> DirectStructuredLaneExecutionResult:
        return DirectStructuredLaneExecutionResult(
            status=status,
            task_id=task.task_id,
            task_family=task.task_family,
            execution_bucket=task.execution_bucket,
            lane_id=lane_id.value if lane_id is not None else None,
            execution_state=state,
            source_ids_considered=source_ids_considered,
            source_ids_selected=[],
            source_ids_attempted=[],
            errors=[error] if error is not None else [],
            metadata={
                **metadata,
                "profiles_considered": source_ids_considered,
                "profiles_selected": [],
                "profile_attempt_count": 0,
                "document_count": 0,
                "normalized_document_count": 0,
                "evidence_count": 0,
            },
        )


def _candidate_source_ids_for_task(task: QueryDecompositionTask) -> list[str]:
    if task.task_family == "project_transaction":
        return [
            "cn_project_ccgp_procurement_v1",
            "cn_project_ggzy_trade_v1",
            "cn_project_ndrc_approval_v1",
        ]
    if task.task_family == "enterprise_disclosure":
        return [
            "cn_exchange_cninfo_announcement_v1",
            "cn_exchange_sse_notice_v1",
            "cn_exchange_szse_notice_v1",
            "cn_exchange_bse_notice_v1",
        ]
    if task.task_family == "data_metrics":
        query = _task_text(task)
        source_ids = [*_regional_data_source_ids(query), "cn_data_stats_national_v1"]
        if _contains_any(
            query,
            ("export", "trade", "customs", "commerce", "出口", "贸易", "海关", "商务"),
        ):
            source_ids.extend(["cn_data_customs_trade_v1", "cn_trade_mofcom_policy_v1"])
        return _dedupe(source_ids)
    return []


def _query_context_for_task(
    task: QueryDecompositionTask,
    *,
    max_documents_per_source: int,
    max_evidence_per_source: int,
) -> QueryContext:
    query = " ".join(task.search_phrases).strip() or task.evidence_goal
    return QueryContext(
        query=query,
        source_strategy=task.source_strategy_hint,
        domestic_mode="direct_structured_lane_execution",
        regional_focus=_regional_focus_for_task(task),
        max_sources=max(1, max_documents_per_source),
        max_documents_per_source=max_documents_per_source,
        max_evidence_per_source=max_evidence_per_source,
        metadata={
            "task_id": task.task_id,
            "task_family": task.task_family,
            "execution_bucket": task.execution_bucket,
            "source_cluster": task.source_cluster,
        },
    )


def _filter_weak_direct_documents(
    *,
    task: QueryDecompositionTask,
    source_id: str,
    documents: list[RawDocument],
    normalized_documents: list[NormalizedDocument],
) -> tuple[list[RawDocument], list[NormalizedDocument], list[dict[str, Any]]]:
    if task.task_family not in {
        "project_transaction",
        "data_metrics",
        "enterprise_disclosure",
        "official_record",
    }:
        return documents, normalized_documents, []

    rejected_document_ids: set[str] = set()
    rejections: list[dict[str, Any]] = []
    kept_documents: list[RawDocument] = []
    normalized_by_id = {document.document_id: document for document in normalized_documents}
    for document in documents:
        evidence_quality = _direct_document_evidence_quality(
            task=task,
            source_id=source_id,
            document=document,
        )
        reason_code = _weak_direct_document_reason(task, document)
        if reason_code is None and evidence_quality["proof_strength"] == "weak":
            reason_code = "weak_evidence_quality"
        if reason_code is None:
            _attach_evidence_quality(
                raw_document=document,
                normalized_document=normalized_by_id.get(document.document_id),
                evidence_quality=evidence_quality,
            )
            kept_documents.append(document)
            continue
        rejected_document_ids.add(document.document_id)
        rejections.append(
            {
                "source_id": source_id,
                "document_id": document.document_id,
                "title": document.title,
                "url": str(document.source_uri) if document.source_uri is not None else None,
                "reason_code": reason_code,
                "evidence_quality": evidence_quality,
            }
        )

    kept_normalized_documents = [
        document
        for document in normalized_documents
        if document.document_id not in rejected_document_ids
    ]
    return kept_documents, kept_normalized_documents, rejections


def _attach_evidence_quality(
    *,
    raw_document: RawDocument,
    normalized_document: NormalizedDocument | None,
    evidence_quality: dict[str, Any],
) -> None:
    raw_document.metadata["evidence_quality"] = evidence_quality
    _promote_evidence_source_class(raw_document.metadata, evidence_quality)
    if normalized_document is not None:
        normalized_document.metadata["evidence_quality"] = evidence_quality
        _promote_evidence_source_class(normalized_document.metadata, evidence_quality)


def _promote_evidence_source_class(
    metadata: dict[str, Any],
    evidence_quality: dict[str, Any],
) -> None:
    source_class = evidence_quality.get("source_class")
    if not isinstance(source_class, str) or not source_class.strip():
        return
    source_class = source_class.strip()
    evidence_classes = evidence_quality.get("source_classes")
    existing_classes = metadata.get("source_classes")
    source_classes: list[str] = []
    if isinstance(existing_classes, str) and existing_classes.strip():
        source_classes.append(existing_classes.strip())
    elif isinstance(existing_classes, list):
        source_classes.extend(str(item).strip() for item in existing_classes if str(item).strip())
    if isinstance(evidence_classes, str) and evidence_classes.strip():
        source_classes.append(evidence_classes.strip())
    elif isinstance(evidence_classes, list):
        source_classes.extend(str(item).strip() for item in evidence_classes if str(item).strip())
    if source_class not in source_classes:
        source_classes.insert(0, source_class)
    source_classes = _unique_strings(source_classes)
    metadata.setdefault("source_class", source_class)
    metadata["source_classes"] = source_classes
    source_family_backbones = evidence_quality.get("source_family_backbones")
    if isinstance(source_family_backbones, list):
        metadata["source_family_backbones"] = [
            str(item).strip() for item in source_family_backbones if str(item).strip()
        ]


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _direct_document_evidence_quality(
    *,
    task: QueryDecompositionTask,
    source_id: str,
    document: RawDocument,
) -> dict[str, Any]:
    title = document.title or ""
    url = str(document.source_uri or "")
    raw_text = document.raw_text or ""
    metadata_text = _document_metadata_hint_text(
        document,
        include_discovery_query=False,
    )
    haystack = f"{title} {metadata_text} {raw_text} {url}".lower()
    early_haystack = f"{title} {metadata_text} {raw_text[:5000]} {url}".lower()
    region_metadata_text = _document_metadata_hint_text(
        document,
        include_discovery_query=False,
    )
    region_haystack = f"{title} {region_metadata_text} {raw_text} {url}".lower()
    relevance_terms = _relevance_terms_for_task(task)
    region_terms = _project_region_terms(task)
    source_class_match = _document_source_class_match(
        task=task,
        source_id=source_id,
        document=document,
        haystack=haystack,
    )
    topic_match = not relevance_terms or any(
        term.lower() in early_haystack for term in relevance_terms
    )
    local_region_match = classify_local_region_match(
        region_terms,
        region_haystack,
        candidate_domain=urlparse(url).netloc.lower(),
    )
    local_region_match_type = str(local_region_match.get("match_type") or "unknown")
    region_match = (
        not region_terms or local_region_match_type in _LOCAL_REGION_EVIDENCE_MATCH_TYPES
    )
    administrative_level_match = _document_administrative_level_match(
        task=task,
        document=document,
        region_match=region_match,
    )
    if local_region_match_type == "parent_local":
        administrative_level_match = False
    content_available = len(f"{raw_text} {metadata_text}".strip()) >= 40
    date_available = bool(
        document.published_at
        or document.metadata.get("published_at_hint")
        or document.metadata.get("published_date")
    )
    proof_score = _proof_score(
        source_class_match=source_class_match,
        topic_match=topic_match,
        region_match=region_match,
        administrative_level_match=administrative_level_match,
        content_available=content_available,
        date_available=date_available,
    )
    source_class = _expected_source_class_for_task(task)
    source_classes = _source_classes_for_task_evidence(
        task=task,
        source_class=source_class,
        haystack=haystack,
        source_id=source_id,
        url=url,
    )
    if document.metadata.get("from_pdf_attachment"):
        source_classes = _unique_strings([*source_classes, "pdf_backed_evidence"])
    source_family_backbones = [
        family.value
        for family in source_family_backbones_for_source_classes(
            source_classes,
            evidence_obligations=task.evidence_obligations,
            regional_level=_task_regional_level_value(task),
        )
    ]
    local_fallback = _local_fallback_metadata(
        local_region_match,
        region_terms=region_terms,
    )
    return {
        "proof_strength": _proof_strength(
            proof_score=proof_score,
            source_class_match=source_class_match,
            topic_match=topic_match,
            region_match=region_match,
            administrative_level_match=administrative_level_match,
        ),
        "proof_score": proof_score,
        "source_class_match": source_class_match,
        "topic_match": topic_match,
        "region_match": region_match,
        "administrative_level_match": administrative_level_match,
        "content_available": content_available,
        "date_available": date_available,
        "source_class": source_class,
        "source_classes": source_classes,
        "source_family_backbones": source_family_backbones,
        "region_terms": region_terms,
        "local_region_match_type": local_region_match_type,
        "local_region_expected_region": local_region_match.get("expected_region"),
        "local_region_matched_region": local_region_match.get("matched_region"),
        "local_region_candidate_domain_region": local_region_match.get(
            "candidate_domain_region"
        ),
        **local_fallback,
        "topic_terms": relevance_terms[:8],
    }


def _task_regional_level_value(task: QueryDecompositionTask) -> str:
    regional_level = task.regional_level
    value = getattr(regional_level, "value", regional_level)
    return str(value)


def _document_source_class_match(
    *,
    task: QueryDecompositionTask,
    source_id: str,
    document: RawDocument,
    haystack: str,
) -> bool:
    metadata_source_class = document.metadata.get("source_class")
    if (
        isinstance(metadata_source_class, str)
        and metadata_source_class == _expected_source_class_for_task(task)
    ):
        return True
    source_key = f"{source_id} {document.source_id}".lower()
    if task.task_family == "project_transaction":
        return (
            "project" in source_key
            or "procurement" in source_key
            or "ggzy" in source_key
            or "ccgp" in source_key
            or _has_project_signal_text(haystack)
        )
    if task.task_family == "data_metrics":
        return (
            "data" in source_key
            or "stats" in source_key
            or "statistics" in source_key
            or "customs" in source_key
            or "commerce" in source_key
            or _has_data_metrics_signal_text(haystack)
            or _is_local_government_report_text(haystack)
        )
    if task.task_family == "official_record":
        return (
            "official_record" in source_key
            or "environment" in source_key
            or "land" in source_key
            or "record" in source_key
            or _has_official_record_signal_text(haystack)
        )
    if task.task_family == "enterprise_disclosure":
        return (
            metadata_source_class == "company_disclosure"
            or "cninfo" in source_key
            or "exchange" in source_key
            or "sse" in source_key
            or "szse" in source_key
            or "bse" in source_key
        )
    return True


def _expected_source_class_for_task(task: QueryDecompositionTask) -> str:
    if task.task_family == "project_transaction":
        return "project_list"
    if task.task_family == "data_metrics":
        return "statistics"
    if task.task_family == "official_record":
        return "environmental_or_land_record"
    if task.task_family == "enterprise_disclosure":
        return "company_disclosure"
    return "unknown"


def _source_classes_for_task_evidence(
    *,
    task: QueryDecompositionTask,
    source_class: str,
    haystack: str,
    source_id: str = "",
    url: str = "",
) -> list[str]:
    source_classes = [source_class] if source_class and source_class != "unknown" else []
    if (
        task.task_family == "project_transaction"
        and _has_tender_or_procurement_signal_text(haystack)
        and _is_tender_or_procurement_evidence_source(source_id=source_id, url=url)
    ):
        source_classes.append("tender_or_procurement")
    if task.task_family == "official_record" and _has_regulatory_record_signal_text(
        haystack
    ):
        source_classes.append("regulatory_record")
    return _unique_strings(source_classes)


def _is_tender_or_procurement_evidence_source(*, source_id: str, url: str) -> bool:
    source_key = source_id.lower()
    if any(
        token in source_key
        for token in ("procurement", "tender", "ggzy", "ccgp", "zfcg", "cgzx")
    ):
        return True
    return _is_public_resource_or_procurement_domain(urlparse(url).netloc.lower())


def _relevance_terms_for_task(task: QueryDecompositionTask) -> list[str]:
    if task.task_family == "data_metrics":
        return _data_metrics_relevance_terms(task)
    if task.task_family == "official_record":
        return _official_record_relevance_terms(task)
    if task.task_family == "project_transaction":
        return _project_relevance_terms(task)
    if task.task_family == "enterprise_disclosure":
        return []
    return []


def _document_administrative_level_match(
    *,
    task: QueryDecompositionTask,
    document: RawDocument,
    region_match: bool,
) -> bool:
    if not task.include_domains:
        return region_match
    domain = urlparse(str(document.source_uri or "")).netloc.lower()
    if domain and any(
        domain == allowed.lower() or domain.endswith(f".{allowed.lower()}")
        for allowed in task.include_domains
    ):
        return True
    return region_match


def _proof_score(
    *,
    source_class_match: bool,
    topic_match: bool,
    region_match: bool,
    administrative_level_match: bool,
    content_available: bool,
    date_available: bool,
) -> int:
    score = 0
    if source_class_match:
        score += 25
    if topic_match:
        score += 25
    if region_match:
        score += 20
    if administrative_level_match:
        score += 15
    if content_available:
        score += 10
    if date_available:
        score += 5
    return min(score, 100)


def _proof_strength(
    *,
    proof_score: int,
    source_class_match: bool,
    topic_match: bool,
    region_match: bool,
    administrative_level_match: bool,
) -> str:
    if (
        proof_score >= 80
        and source_class_match
        and topic_match
        and region_match
        and administrative_level_match
    ):
        return "strong"
    if proof_score >= 55 and source_class_match and (topic_match or region_match):
        return "usable"
    return "weak"


def _evidence_quality_summary(
    *,
    documents: list[RawDocument],
    normalized_documents: list[NormalizedDocument],
    rejections: list[dict[str, Any]],
) -> dict[str, Any]:
    accepted_quality: list[dict[str, Any]] = []
    seen_document_ids: set[str] = set()
    for document in documents:
        quality = document.metadata.get("evidence_quality")
        if isinstance(quality, dict):
            accepted_quality.append(quality)
            seen_document_ids.add(document.document_id)
    for document in normalized_documents:
        if document.document_id in seen_document_ids:
            continue
        quality = document.metadata.get("evidence_quality")
        if isinstance(quality, dict):
            accepted_quality.append(quality)
    rejection_quality = [
        rejection.get("evidence_quality")
        for rejection in rejections
        if isinstance(rejection.get("evidence_quality"), dict)
    ]
    return {
        "accepted_document_count": len(accepted_quality),
        "rejected_document_count": len(rejections),
        "proof_strength_counts": _proof_strength_counts(accepted_quality),
        "weak_rejection_count": sum(
            1 for quality in rejection_quality if quality.get("proof_strength") == "weak"
        ),
        "min_accepted_proof_score": (
            min(int(quality.get("proof_score", 0)) for quality in accepted_quality)
            if accepted_quality
            else None
        ),
        "source_class_mismatch_rejection_count": sum(
            1 for quality in rejection_quality if quality.get("source_class_match") is False
        ),
        "topic_mismatch_rejection_count": sum(
            1 for quality in rejection_quality if quality.get("topic_match") is False
        ),
        "region_mismatch_rejection_count": sum(
            1 for quality in rejection_quality if quality.get("region_match") is False
        ),
    }


def _proof_strength_counts(qualities: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"strong": 0, "usable": 0, "weak": 0}
    for quality in qualities:
        strength = str(quality.get("proof_strength") or "weak")
        if strength not in counts:
            strength = "weak"
        counts[strength] += 1
    return counts


def _weak_direct_document_reason(
    task: QueryDecompositionTask,
    document: RawDocument,
) -> str | None:
    title = (document.title or "").strip().lower()
    url = str(document.source_uri or "").strip()
    path = urlparse(url).path.strip("/").lower()
    raw_text = (document.raw_text or "").strip()

    generic_titles = {"首页", "home", "index", "网站首页"}
    if task.task_family == "data_metrics":
        if title in {*generic_titles, "en", "english", "数据"}:
            return "generic_stats_homepage"
        if "stats.gov.cn/english" in url.lower():
            return "generic_stats_homepage"
        if path in {"", "english", "sj", "sj/zxfb"}:
            return "generic_stats_homepage"
        relevance_terms = _data_metrics_relevance_terms(task)
        metadata_text = _document_metadata_hint_text(document)
        haystack = f"{document.title} {metadata_text} {raw_text} {url}".lower()
        if (
            relevance_terms
            and not any(term.lower() in haystack for term in relevance_terms)
            and not _is_local_government_report_text(haystack)
        ):
            return "data_metrics_relevance_mismatch"
        return None

    if task.task_family == "enterprise_disclosure":
        if title in generic_titles:
            return "generic_disclosure_homepage"
        if path in {"new/index", "", "disclosure", "disclosure/announcement"}:
            return "generic_disclosure_homepage"
        if "cpc/" in path or title in {"党建动态", "党务动态"}:
            return "non_disclosure_page"
        spec_payload = document.metadata.get("disclosure_search_spec")
        if isinstance(spec_payload, dict) and not disclosure_document_matches_spec(
            title=document.title,
            raw_text=raw_text,
            source_uri=url,
            spec_payload=spec_payload,
        ):
            return "disclosure_entity_mismatch"
        return None

    if task.task_family == "project_transaction":
        metadata_text = _document_metadata_hint_text(document)
        signal_haystack = f"{metadata_text} {url}".lower()
        if title in generic_titles and not _has_project_signal_text(signal_haystack):
            return "generic_project_navigation"
        if path in {
            "",
            "cggg",
            "zcfg",
            "gpsr",
            "jdjc",
            "xxgg",
            "deal/deallist.html",
        }:
            return "generic_project_navigation"
        relevance_terms = _project_relevance_terms(task)
        haystack = f"{document.title} {metadata_text} {raw_text} {url}".lower()
        if relevance_terms and not any(term.lower() in haystack for term in relevance_terms):
            return "project_relevance_mismatch"
        return None

    if task.task_family == "official_record":
        metadata_text = _document_metadata_hint_text(
            document,
            include_discovery_query=False,
        )
        haystack = f"{document.title} {metadata_text} {raw_text} {url}".lower()
        domain = urlparse(url).netloc.lower()
        if domain and not _domain_allowed_for_official_record_search(
            domain,
            task.include_domains,
        ) and not _region_matched_official_record_document_domain(
            domain=domain,
            task=task,
            document=document,
            haystack=haystack,
        ) and not _national_scope_local_official_record_document_domain(
            domain=domain,
            task=task,
            document=document,
            haystack=haystack,
        ):
            return "official_record_domain_mismatch"
        if title in generic_titles and not _has_official_record_signal_text(haystack):
            return "generic_official_record_navigation"
        if path in {"", "xxgk", "zwgk", "gkml", "index"} and (
            not raw_text or len(raw_text) < 40
        ):
            return "generic_official_record_navigation"
        if not _has_official_record_signal_text(haystack):
            return "official_record_signal_missing"
        if _is_generic_official_record_case_page(
            title=title,
            path=path,
            metadata_text=metadata_text,
        ):
            return "generic_official_record_case_page"
        relevance_terms = _official_record_relevance_terms(task)
        if relevance_terms:
            # Avoid accepting unrelated full pages because theme terms appear
            # only in late footer/recommendation boilerplate.
            strong_haystack = f"{document.title} {raw_text[:5000]} {url}".lower()
            has_strong_match = any(term.lower() in strong_haystack for term in relevance_terms)
            has_sparse_hint_match = len(raw_text or "") < 200 and any(
                term.lower() in metadata_text.lower() for term in relevance_terms
            )
            if not has_strong_match and not has_sparse_hint_match:
                return "official_record_relevance_mismatch"
        return None

    if title in generic_titles:
        return "generic_homepage"
    if path in {"", "cggg", "jyxx"} and (not raw_text or len(raw_text) < 40):
        return "generic_list_or_homepage"
    return None


def _project_search_candidate_rejection_reason(
    *,
    task: QueryDecompositionTask,
    result: TavilySearchResult,
    seen_urls: set[str],
) -> str | None:
    if result.url in seen_urls:
        return "duplicate_project_candidate"
    domain = urlparse(result.url).netloc.lower()
    if not _domain_allowed_for_project_search(domain, task.include_domains):
        return "project_search_off_domain"
    title = result.title.strip().lower()
    path = urlparse(result.url).path.strip("/").lower()
    if _is_generic_project_planning_or_interpretation_page(title=title, path=path):
        return "generic_project_planning_or_interpretation"
    if _is_public_resource_or_procurement_domain(
        domain
    ) and _is_public_resource_or_procurement_list_or_search_path(path):
        return "generic_project_navigation"
    structured_public_resource_signal = _has_public_resource_project_search_signal(
        result=result,
        domain=domain,
        path=path,
    )
    structured_project_approval_signal = _has_project_approval_search_signal(
        result=result,
        domain=domain,
        path=path,
    )
    if structured_public_resource_signal or structured_project_approval_signal:
        title = ""
    if title in {"首页", "home", "index", "网站首页", "全国公共资源交易平台"}:
        return "generic_project_navigation"
    if path in {"", "cggg", "zcfg", "gpsr", "jdjc", "xxgg", "deal/deallist.html"}:
        return "generic_project_navigation"
    relevance_terms = _project_relevance_terms(task)
    haystack = f"{result.title} {result.content} {result.url}".lower()
    region_terms = _project_region_terms(task)
    local_region_match = _local_region_match_for_search_candidate(task=task, result=result)
    if (
        region_terms
        and local_region_match.get("match_type") not in _LOCAL_REGION_EVIDENCE_MATCH_TYPES
    ):
        return "project_region_mismatch"
    if not (
        _has_project_signal(result)
        or structured_public_resource_signal
        or structured_project_approval_signal
    ):
        return "project_signal_missing"
    if relevance_terms and not any(term.lower() in haystack for term in relevance_terms):
        return "project_relevance_mismatch"
    return None


def _data_metrics_search_candidate_rejection_reason(
    *,
    task: QueryDecompositionTask,
    result: TavilySearchResult,
    seen_urls: set[str],
) -> str | None:
    if result.url in seen_urls:
        return "duplicate_data_metrics_candidate"
    domain = urlparse(result.url).netloc.lower()
    if not _domain_allowed_for_data_metrics_search(domain, task.include_domains):
        return "data_metrics_search_off_domain"
    title = result.title.strip().lower()
    path = urlparse(result.url).path.strip("/").lower()
    if title in {"首页", "home", "index", "网站首页", "en", "english"}:
        return "generic_data_metrics_navigation"
    if path in {"", "english", "sj", "sj/zxfb"}:
        return "generic_data_metrics_navigation"
    if _is_generic_data_metrics_yearbook_file_candidate(
        title=title,
        path=path,
        task=task,
    ):
        return "generic_data_metrics_yearbook_file"
    region_terms = _project_region_terms(task)
    local_region_match = _local_region_match_for_search_candidate(task=task, result=result)
    if (
        region_terms
        and local_region_match.get("match_type") not in _LOCAL_REGION_EVIDENCE_MATCH_TYPES
    ):
        return "data_metrics_region_mismatch"
    local_government_report = _is_local_government_report_candidate(result)
    if (
        not local_government_report
        and not _has_data_metrics_source_role_candidate(result)
    ):
        return "data_metrics_source_role_mismatch"
    if not _has_data_metrics_signal(result) and not local_government_report:
        return "data_metrics_signal_missing"
    relevance_terms = _data_metrics_relevance_terms(task)
    haystack = f"{result.title} {result.content} {result.url}".lower()
    if (
        relevance_terms
        and not any(term.lower() in haystack for term in relevance_terms)
        and not local_government_report
    ):
        return "data_metrics_relevance_mismatch"
    return None


def _direct_lane_file_candidate_kind(url: str) -> str | None:
    kind = file_candidate_kind_from_url(url)
    return kind.value if kind is not None else None


def _data_metrics_file_candidate_kind(url: str) -> str | None:
    return _direct_lane_file_candidate_kind(url)


def _is_generic_data_metrics_yearbook_file_candidate(
    *,
    title: str,
    path: str,
    task: QueryDecompositionTask,
) -> bool:
    query_text = _task_text(task)
    if "统计年鉴" in query_text or "年鉴" in query_text:
        return False
    if "tjnj" not in path and "统计年鉴" not in path and "统计年鉴" not in title:
        return False
    generic_section_terms = (
        "第一部分",
        "第二部分",
        "第三部分",
        "特载",
        "综合",
        "目录",
        "说明",
    )
    return any(term in title or term in path for term in generic_section_terms)


def _local_region_match_for_search_candidate(
    *,
    task: QueryDecompositionTask,
    result: TavilySearchResult,
) -> dict[str, Any]:
    domain = urlparse(result.url).netloc.lower()
    return classify_local_region_match(
        _project_region_terms(task),
        f"{result.title} {result.content} {result.url}",
        candidate_domain=domain,
    )


def _local_region_match_metadata(local_region_match: dict[str, Any]) -> dict[str, Any]:
    return {
        "local_region_match_type": local_region_match.get("match_type"),
        "local_region_expected_region": local_region_match.get("expected_region"),
        "local_region_matched_region": local_region_match.get("matched_region"),
        "local_region_candidate_domain_region": local_region_match.get(
            "candidate_domain_region"
        ),
        **_local_fallback_metadata(local_region_match),
    }


def _local_fallback_metadata(
    local_region_match: dict[str, Any],
    *,
    region_terms: list[str] | None = None,
) -> dict[str, Any]:
    match_type = str(local_region_match.get("match_type") or "unknown")
    matched_region = local_region_match.get("matched_region")
    candidate_domain_region = local_region_match.get("candidate_domain_region")
    fallback_source = matched_region or candidate_domain_region
    has_region_requirement = bool(region_terms) if region_terms is not None else True

    if not has_region_requirement:
        return {
            "parent_evidence_only": False,
            "local_claim_allowed": True,
            "fallback_level": None,
            "fallback_source": None,
        }
    if match_type == "parent_local":
        return {
            "parent_evidence_only": True,
            "local_claim_allowed": False,
            "fallback_level": "parent_official",
            "fallback_source": fallback_source,
        }
    if match_type in {"exact_local", "child_local"}:
        return {
            "parent_evidence_only": False,
            "local_claim_allowed": True,
            "fallback_level": match_type,
            "fallback_source": fallback_source,
        }
    return {
        "parent_evidence_only": False,
        "local_claim_allowed": False,
        "fallback_level": "exact_local_required",
        "fallback_source": fallback_source,
    }


def _official_record_search_candidate_rejection_reason(
    *,
    task: QueryDecompositionTask,
    result: TavilySearchResult,
    seen_urls: set[str],
    enable_pdf_fallback: bool = True,
) -> str | None:
    if result.url in seen_urls:
        return "duplicate_official_record_candidate"
    domain = urlparse(result.url).netloc.lower()
    title = result.title.strip().lower()
    path = urlparse(result.url).path.strip("/").lower()
    if not _domain_allowed_for_official_record_search(
        domain,
        task.include_domains,
    ) and not _region_matched_subprovincial_official_record_domain(
        domain=domain,
        task=task,
        result=result,
    ) and not _national_scope_local_official_record_candidate(
        domain=domain,
        path=path,
        task=task,
        result=result,
    ):
        return "official_record_search_off_domain"
    if path.endswith(".pdf") and not enable_pdf_fallback:
        return "official_record_pdf_requires_adapter"
    if title in {"首页", "home", "index", "网站首页"}:
        return "generic_official_record_navigation"
    if path in {"", "xxgk", "zwgk", "gkml", "index"}:
        return "generic_official_record_navigation"
    if "site/search" in path or "search" in path:
        return "generic_official_record_navigation"
    if _is_generic_official_record_case_page(
        title=title,
        path=path,
        metadata_text=result.content,
    ):
        return "generic_official_record_case_page"
    region_terms = _project_region_terms(task)
    region_haystack = f"{result.title} {result.content} {result.url}".lower()
    local_region_match = classify_local_region_match(
        region_terms,
        region_haystack,
        candidate_domain=domain,
    )
    if (
        region_terms
        and local_region_match.get("match_type") not in _LOCAL_REGION_EVIDENCE_MATCH_TYPES
    ):
        return "official_record_region_mismatch"
    if not _has_official_record_search_signal(result, domain):
        return "official_record_signal_missing"
    relevance_terms = _official_record_relevance_terms(task)
    haystack = f"{result.title} {result.content} {result.url}".lower()
    if relevance_terms and not any(term.lower() in haystack for term in relevance_terms):
        return "official_record_relevance_mismatch"
    return None


def _domain_allowed_for_project_search(domain: str, include_domains: list[str]) -> bool:
    if not domain:
        return False
    allowed_domains = [item.strip().lower() for item in include_domains if item.strip()]
    if not allowed_domains:
        return domain.endswith(".gov.cn") or domain in {
            "gov.cn",
            "ccgp.gov.cn",
            "ggzy.gov.cn",
            "ndrc.gov.cn",
        }
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in allowed_domains)


def _domain_allowed_for_data_metrics_search(domain: str, include_domains: list[str]) -> bool:
    if not domain:
        return False
    allowed_domains = [item.strip().lower() for item in include_domains if item.strip()]
    if not allowed_domains:
        return domain.endswith(".gov.cn") or domain in {
            "gov.cn",
            "customs.gov.cn",
            "miit.gov.cn",
            "mofcom.gov.cn",
            "nda.gov.cn",
            "nea.gov.cn",
            "ndrc.gov.cn",
            "stats.gov.cn",
        }
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in allowed_domains)


def _has_data_metrics_source_role_candidate(result: TavilySearchResult) -> bool:
    domain = urlparse(result.url).netloc.lower()
    path = urlparse(result.url).path.strip("/").lower()
    title_url = f"{result.title} {result.url}".lower()
    return (
        _is_statistics_or_fiscal_data_domain(domain)
        or _is_official_quantitative_department_data_candidate(
            domain=domain,
            path=path,
            title_url=title_url,
        )
        or _is_statistics_or_fiscal_report_text(title_url)
        or _is_statistics_or_fiscal_report_path(path)
    )


def _is_statistics_or_fiscal_data_domain(domain: str) -> bool:
    if not domain:
        return False
    normalized = domain.removeprefix("www.")
    first_label = normalized.split(".", 1)[0]
    if normalized in {"stats.gov.cn", "customs.gov.cn"}:
        return True
    if normalized.endswith(".stats.gov.cn") or normalized.endswith(".customs.gov.cn"):
        return True
    return first_label in {"tj", "tjj", "stats", "stat", "czj", "czt", "finance"}


def _is_official_quantitative_department_data_candidate(
    *,
    domain: str,
    path: str,
    title_url: str,
) -> bool:
    if not domain.endswith(".gov.cn"):
        return False
    first_label = domain.removeprefix("www.").split(".", 1)[0]
    if first_label not in {
        "drc",
        "fgw",
        "gxt",
        "gyhxxh",
        "gxj",
        "jx",
        "jxt",
        "jtj",
        "nyj",
        "ny",
        "swt",
        "swb",
        "swj",
        "commerce",
        "dsj",
        "mofcom",
        "miit",
        "nda",
        "nea",
        "sj",
    }:
        return False
    if _is_data_metrics_media_or_news_context_path(path):
        return False
    return any(
        term in title_url
        for term in (
            "\u80fd\u6e90\u8fd0\u884c",
            "\u7535\u529b\u8fd0\u884c",
            "\u7535\u529b\u4f9b\u9700",
            "\u7535\u529b\u5de5\u4e1a\u7edf\u8ba1\u6570\u636e",
            "\u5de5\u4e1a\u8fd0\u884c",
            "\u7ecf\u6d4e\u8fd0\u884c",
            "\u5916\u8d38\u8fd0\u884c",
            "\u8fdb\u51fa\u53e3\u8fd0\u884c",
            "\u8fd0\u884c\u6708\u62a5",
            "\u8fd0\u884c\u6570\u636e",
            "\u6708\u5ea6\u6570\u636e",
            "\u76d1\u6d4b\u6570\u636e",
            "\u7edf\u8ba1\u6570\u636e",
            "\u53d1\u7535\u91cf",
            "\u7528\u7535\u91cf",
            "\u5168\u793e\u4f1a\u7528\u7535\u91cf",
            "\u7b97\u529b\u89c4\u6a21",
            "\u7b97\u529b\u6307\u6570",
            "\u6570\u636e\u4e2d\u5fc3\u80fd\u8017",
            "\u7eff\u8272\u6570\u636e\u4e2d\u5fc3",
            "\u80fd\u6548",
            "pue",
            "\u673a\u67b6",
            "\u4ea7\u91cf",
            "\u7164\u70ad\u4ea7\u91cf",
            "\u8fdb\u51fa\u53e3",
            "\u8fdb\u51fa\u53e3\u6570\u636e",
            "\u51fa\u53e3\u6570\u636e",
            "\u8fdb\u53e3\u6570\u636e",
            "\u53e3\u5cb8\u6570\u636e",
            "\u6e2f\u53e3\u541e\u5410\u91cf",
            "\u541e\u5410\u91cf",
            "\u4ef7\u683c\u6307\u6570",
            "\u6295\u8d44\u6570\u636e",
            "\u9884\u7b97\u6267\u884c",
            "\u8c03\u67e5\u62a5\u544a",
            "\u6570\u636e\u8d44\u6e90\u8c03\u67e5\u62a5\u544a",
        )
    )


def _is_statistics_or_fiscal_report_path(path: str) -> bool:
    return any(
        segment in path
        for segment in (
            "tjgb",
            "tjnj",
            "stats",
            "statistics",
            "stat",
            "data",
            "tjsj",
            "sjtj",
            "sjfb",
            "ywtj",
            "czj",
            "czt",
            "budget",
            "finance",
        )
    )


def _is_statistics_or_fiscal_report_text(text: str) -> bool:
    return any(
        term in text
        for term in (
            "\u7edf\u8ba1\u516c\u62a5",
            "\u7edf\u8ba1\u5206\u7c7b",
            "\u4ea7\u4e1a\u7edf\u8ba1\u5206\u7c7b",
            "\u7edf\u8ba1\u6570\u636e",
            "\u8c03\u67e5\u62a5\u544a",
            "\u6570\u636e\u8d44\u6e90\u8c03\u67e5\u62a5\u544a",
            "\u7edf\u8ba1\u5e74\u9274",
            "\u56fd\u6c11\u7ecf\u6d4e\u548c\u793e\u4f1a\u53d1\u5c55",
            "\u9884\u7b97",
            "\u51b3\u7b97",
            "\u8d22\u653f\u6536\u5165",
            "\u4e13\u9879\u8d44\u91d1",
        )
    )


def _domain_allowed_for_official_record_search(domain: str, include_domains: list[str]) -> bool:
    if not domain:
        return False
    allowed_domains = [item.strip().lower() for item in include_domains if item.strip()]
    if not allowed_domains:
        return domain.endswith(".gov.cn")
    for allowed in allowed_domains:
        if allowed == "gov.cn":
            if domain in {"gov.cn", "www.gov.cn"}:
                return True
            continue
        if domain == allowed or domain.endswith(f".{allowed}"):
            return True
    return False


def _is_pdf_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def _official_record_errors_are_nonfatal_pdf_gaps(
    errors: list[ToolError],
    metadata: dict[str, Any],
) -> bool:
    if metadata.get("status") != "extracted_without_usable_evidence":
        return False
    pdf_metadata = metadata.get("pdf_extraction")
    if not isinstance(pdf_metadata, dict) or not pdf_metadata.get("failed"):
        return False
    if not errors:
        return False
    return all(
        error.detail.get("extraction_failure_class") == "pdf_or_download"
        for error in errors
    )


def _filename_from_url(url: str) -> str | None:
    filename = urlparse(url).path.strip("/").split("/")[-1]
    return filename or None


def _parse_direct_lane_datetime(value: str | None) -> datetime | None:
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


def _safe_pdf_download_dict(download: Any) -> dict[str, Any]:
    to_dict = getattr(download, "to_dict", None)
    if callable(to_dict):
        try:
            result = to_dict()
            if isinstance(result, dict):
                return result
        except Exception:  # noqa: BLE001
            return {"to_dict_failed": True}
    return {
        "final_url": getattr(download, "final_url", None),
        "file_path": getattr(download, "file_path", None),
        "bytes_size": getattr(download, "bytes_size", None),
        "sha256": getattr(download, "sha256", None),
        "retry_count": getattr(download, "retry_count", None),
        "warnings": list(getattr(download, "warnings", []) or []),
    }


def _increment_failure_class(failure_classes: dict[str, int], failure_class: str) -> None:
    failure_classes[failure_class] = failure_classes.get(failure_class, 0) + 1


def _region_matched_subprovincial_official_record_domain(
    *,
    domain: str,
    task: QueryDecompositionTask,
    result: TavilySearchResult,
) -> bool:
    if not domain.endswith(".gov.cn") or domain in {"gov.cn", "www.gov.cn"}:
        return False
    region_terms = _project_region_terms(task)
    if not region_terms:
        return False
    haystack = f"{result.title} {result.content} {result.url}".lower()
    if _declares_unrelated_local_public_body(result.title, region_terms):
        return False
    local_region_match = classify_local_region_match(
        region_terms,
        haystack,
        candidate_domain=domain,
    )
    return local_region_match.get("match_type") in _LOCAL_REGION_EVIDENCE_MATCH_TYPES and (
        _has_official_record_search_signal(result, domain)
    )


def _region_matched_official_record_document_domain(
    *,
    domain: str,
    task: QueryDecompositionTask,
    document: RawDocument,
    haystack: str,
) -> bool:
    if not domain.endswith(".gov.cn") or domain in {"gov.cn", "www.gov.cn"}:
        return False
    region_terms = _project_region_terms(task)
    if not region_terms:
        return False
    government_title_context = f"{document.title} {_document_metadata_hint_text(document)}"
    if _declares_unrelated_local_public_body(government_title_context, region_terms):
        return False
    has_region_term = any(term.lower() in haystack for term in region_terms)
    return has_region_term and _has_official_record_signal_text(haystack)


def _national_scope_local_official_record_candidate(
    *,
    domain: str,
    path: str,
    task: QueryDecompositionTask,
    result: TavilySearchResult,
) -> bool:
    if not _is_unscoped_or_national_official_record_task(task):
        return False
    if not _is_local_official_record_domain(domain):
        return False
    if not _is_official_record_detail_path(path):
        return False
    if not _has_official_record_search_signal(result, domain):
        return False
    relevance_terms = _official_record_relevance_terms(task)
    haystack = f"{result.title} {result.content} {result.url}".lower()
    return not relevance_terms or any(term.lower() in haystack for term in relevance_terms)


def _national_scope_local_official_record_document_domain(
    *,
    domain: str,
    task: QueryDecompositionTask,
    document: RawDocument,
    haystack: str,
) -> bool:
    if not _is_unscoped_or_national_official_record_task(task):
        return False
    if not _is_local_official_record_domain(domain):
        return False
    path = urlparse(str(document.source_uri or "")).path.strip("/").lower()
    return _is_official_record_detail_path(path) and _has_official_record_signal_text(
        haystack
    )


def _is_unscoped_or_national_official_record_task(task: QueryDecompositionTask) -> bool:
    if _project_region_terms(task):
        return False
    text = " ".join(task.search_phrases)
    return "\u5168\u56fd" in text or "\u4e2d\u56fd" in text


def _is_local_official_record_domain(domain: str) -> bool:
    return domain.endswith(".gov.cn") and domain not in {"gov.cn", "www.gov.cn"}


def _declares_unrelated_local_public_body(title: str, region_terms: list[str]) -> bool:
    if not _has_exact_local_region_expectation(region_terms):
        return False
    declared_governments = re.findall(
        (
            r"([\u4e00-\u9fff]{2,12}(?:省|市|县|区|旗|盟|州))"
            r"(?:人民政府|生态环境局|生态环境厅|自然资源局|自然资源厅|"
            r"自然资源和规划局|发展和改革委员会|发改委|工业和信息化局|工信局|行政审批局)"
        ),
        title,
    )
    if not declared_governments:
        return False
    normalized_terms = [term.strip() for term in region_terms if term.strip()]
    for declared in declared_governments:
        if not any(term in declared or declared in term for term in normalized_terms):
            declared_region_match = classify_local_region_match(region_terms, declared)
            if declared_region_match.get("match_type") in _LOCAL_REGION_EVIDENCE_MATCH_TYPES:
                continue
            return True
    return False


def _has_exact_local_region_expectation(region_terms: list[str]) -> bool:
    return any(
        _canonical_local_region_term(term) not in _PROVINCE_LEVEL_REGION_TERMS
        for term in region_terms
        if term.strip()
    )


def _canonical_local_region_term(region: str) -> str:
    normalized = region.strip()
    if len(normalized) > 2 and normalized.endswith(("省", "市", "县", "区", "旗")):
        return normalized[:-1]
    return normalized


def _declares_unrelated_local_government(title: str, region_terms: list[str]) -> bool:
    return _declares_unrelated_local_public_body(title, region_terms)


def _has_project_signal(result: TavilySearchResult) -> bool:
    title_url = f"{result.title} {result.url}".lower()
    return _has_project_signal_text(title_url)


def _prioritize_project_search_results(
    results: list[TavilySearchResult],
) -> list[TavilySearchResult]:
    return sorted(
        results,
        key=lambda result: (
            _project_search_result_priority(result),
            result.score,
        ),
        reverse=True,
    )


def _project_search_result_priority(result: TavilySearchResult) -> int:
    domain = urlparse(result.url).netloc.lower()
    path = urlparse(result.url).path.strip("/").lower()
    haystack = f"{result.title} {result.content} {result.url}".lower()
    if _has_public_resource_project_search_signal(
        result=result,
        domain=domain,
        path=path,
    ):
        return 100
    if _has_project_approval_search_signal(result=result, domain=domain, path=path):
        return 90
    if (
        _is_public_resource_or_procurement_domain(domain)
        and _has_tender_or_procurement_signal_text(haystack)
    ):
        return 80
    if _has_tender_or_procurement_signal_text(haystack):
        return 70
    if _has_project_approval_signal_text(haystack):
        return 60
    if _has_project_signal_text(haystack):
        return 40
    return 0


def _has_public_resource_project_search_signal(
    *,
    result: TavilySearchResult,
    domain: str,
    path: str,
) -> bool:
    if not _is_public_resource_or_procurement_domain(domain):
        return False
    if not _is_public_resource_or_procurement_detail_path(path):
        return False
    haystack = f"{result.title} {result.content} {result.url}".lower()
    return _has_project_signal_text(haystack) or _has_tender_or_procurement_signal_text(
        haystack
    )


def _has_project_approval_search_signal(
    *,
    result: TavilySearchResult,
    domain: str,
    path: str,
) -> bool:
    if not _is_official_project_approval_domain(domain):
        return False
    if not _is_project_approval_detail_path(path):
        return False
    haystack = f"{result.title} {result.content} {result.url}".lower()
    return _has_project_signal_text(haystack) and _has_project_approval_signal_text(
        haystack
    )


def _is_public_resource_or_procurement_domain(domain: str) -> bool:
    return any(
        token in domain
        for token in (
            "ggzy",
            "ggzyjy",
            "ccgp",
            "zfcg",
            "cgw",
            "cgzx",
        )
    )


def _is_official_project_approval_domain(domain: str) -> bool:
    if domain.endswith(".gov.cn"):
        return True
    return any(token in domain for token in ("ndrc.gov.cn", "drc.", "fgw.", "fzggw."))


def _is_public_resource_or_procurement_detail_path(path: str) -> bool:
    normalized = path.strip("/").lower()
    if not normalized:
        return False
    if _is_public_resource_or_procurement_list_or_search_path(normalized):
        return False
    return any(
        token in normalized
        for token in (
            "deal",
            "jyxx",
            "jydt",
            "information",
            "html/b",
            "adminnmg/api/downloadfile",
            "cggg/",
            "zbgg",
            "zbcg",
            "cgxx",
        )
    )


def _is_public_resource_or_procurement_list_or_search_path(path: str) -> bool:
    normalized = path.strip("/").lower()
    if not normalized:
        return True
    if "site/search" in normalized or "search" in normalized:
        return True
    segments = [segment for segment in normalized.split("/") if segment]
    if not segments:
        return True
    if segments[-1] in {"index", "index.html", "index.htm", "index.shtml"}:
        return True
    if normalized in {"deal/deallist.html"}:
        return True
    return any(segment in {"list", "search"} for segment in segments)


def _is_project_approval_detail_path(path: str) -> bool:
    normalized = path.strip("/").lower()
    if not normalized:
        return False
    if normalized in {"index.html", "index.shtml"}:
        return False
    if "site/search" in normalized or "search" in normalized:
        return False
    return True


def _is_official_record_detail_path(path: str) -> bool:
    normalized = path.strip("/").lower()
    if not normalized:
        return False
    if normalized in {"index", "index.html", "index.shtml", "xxgk", "zwgk", "gkml"}:
        return False
    if "site/search" in normalized or "search" in normalized:
        return False
    return True


def _is_generic_project_planning_or_interpretation_page(*, title: str, path: str) -> bool:
    title_path = f"{title} {path}".lower()
    if any(
        term in title_path
        for term in (
            "招标",
            "中标",
            "采购",
            "成交",
            "候选人",
            "项目备案",
            "项目审批",
            "审批",
            "备案",
            "批复",
            "核准",
            "重点项目",
            "重大项目",
            "项目清单",
            "开工",
            "投产",
        )
    ):
        return False
    return any(
        term in title_path
        for term in (
            "规划研究",
            "发展规划",
            "征求意见",
            "专家观点",
            "政策建议",
            "制约因素",
            "对策研究",
            "问题与",
        )
    )


def _has_official_record_signal(result: TavilySearchResult) -> bool:
    # Search snippets can include broad policy text; require the record signal
    # to appear in the result title or URL before spending extraction budget.
    return _has_official_record_signal_text(f"{result.title} {result.url}".lower())


def _has_official_record_search_signal(
    result: TavilySearchResult,
    domain: str,
) -> bool:
    if _has_official_record_signal(result):
        return True
    if not _is_official_record_department_domain(domain):
        return False
    haystack = f"{result.title} {result.content} {result.url}".lower()
    return _has_official_record_signal_text(haystack)


def _is_official_record_department_domain(domain: str) -> bool:
    if not domain.endswith(".gov.cn"):
        return False
    return any(
        token in domain
        for token in (
            "drc",
            "fgw",
            "fzggw",
            "gtzy",
            "ndrc",
            "sthj",
            "sthjt",
            "zrzy",
        )
    )


def _has_official_record_signal_text(text: str) -> bool:
    return any(
        term in text
        for term in (
            "环评",
            "环境影响评价",
            "生态环境",
            "环保验收",
            "土地出让",
            "自然资源",
            "建设用地",
            "用地预审",
            "规划许可",
            "项目备案",
            "备案",
            "审批",
            "核准",
            "批复",
            "节能审查",
            "能评",
            "排污许可",
            "矿权",
            "采矿权",
            "公示",
        )
    )


def _is_generic_official_record_case_page(
    *,
    title: str,
    path: str,
    metadata_text: str,
) -> bool:
    hint_text = f"{title} {metadata_text}".lower()
    return "/dxal/" in f"/{path}/" or "典型案例" in hint_text or "案例" in title


def _has_project_signal_text(text: str) -> bool:
    return any(
        term in text
        for term in (
            "项目",
            "招标",
            "中标",
            "采购",
            "开工",
            "投产",
            "施工",
            "公示",
            "审批",
            "备案",
            "交易",
            "基地",
        )
    )


def _has_project_approval_signal_text(text: str) -> bool:
    return any(
        term in text
        for term in (
            "项目备案",
            "项目审批",
            "审批",
            "备案",
            "批复",
            "核准",
            "重点项目",
            "重大项目",
            "开工",
            "投产",
            "施工",
            "建设单位",
            "实施单位",
            "项目建设",
            "项目清单",
            "项目库",
            "产能",
            "生产线",
            "生产任务",
        )
    )


def _has_tender_or_procurement_signal_text(text: str) -> bool:
    return any(
        term in text
        for term in (
            "\u62db\u6807",
            "\u4e2d\u6807",
            "\u91c7\u8d2d",
            "\u653f\u5e9c\u91c7\u8d2d",
            "\u516c\u5171\u8d44\u6e90\u4ea4\u6613",
            "\u6210\u4ea4",
            "\u5019\u9009\u4eba",
        )
    )


def _has_regulatory_record_signal_text(text: str) -> bool:
    return any(
        term in text
        for term in (
            "\u5ba1\u6279",
            "\u6279\u590d",
            "\u5907\u6848",
            "\u6838\u51c6",
            "\u8bb8\u53ef",
            "\u53d7\u7406",
        )
    )


def _document_metadata_hint_text(
    document: RawDocument,
    *,
    include_discovery_query: bool = True,
) -> str:
    values: list[str] = []
    for key in ("title_hint", "snippet_hint", "discovery_query"):
        if key == "discovery_query" and not include_discovery_query:
            continue
        value = document.metadata.get(key)
        if isinstance(value, str):
            values.append(value)
    return " ".join(values)


def _has_data_metrics_signal(result: TavilySearchResult) -> bool:
    title_url = f"{result.title} {result.url}".lower()
    return _has_data_metrics_signal_text(title_url)


def _has_data_metrics_signal_text(text: str) -> bool:
    return any(
        term in text
        for term in (
            "统计",
            "统计数据",
            "数据",
            "公报",
            "年鉴",
            "运行",
            "产量",
            "销量",
            "用电",
            "能耗",
            "出口",
            "进口",
            "进出口",
            "外贸",
            "口岸",
            "吞吐量",
            "价格",
            "投资",
            "面积",
            "财政",
            "收入",
            "预算执行",
            "规上",
            "增加值",
            "生产",
            "能源",
            "电力运行",
            "能效",
            "算力规模",
            "算力指数",
            "机架",
            "pue",
            "煤炭",
            "发电",
            "产能",
            "指数",
            "月度",
            "年度",
            "报告",
            "调查报告",
            "数据资源调查报告",
            "电力工业统计数据",
            "政府工作报告",
        )
    )


def _is_local_government_report_candidate(result: TavilySearchResult) -> bool:
    path = urlparse(result.url).path.strip("/").lower()
    title_url = f"{result.title} {result.url}".lower()
    if not _is_local_government_report_text(title_url):
        return False
    if _is_data_metrics_media_or_news_context_path(
        path
    ) and not _is_local_government_report_path(path):
        return False
    return True


def _is_local_government_report_text(text: str) -> bool:
    return "政府工作报告" in text


def _is_local_government_report_path(path: str) -> bool:
    return any(
        segment in path
        for segment in (
            "gzbg",
            "zfgzbg",
            "zfxxgk",
            "xxgk",
            "govreport",
            "work-report",
        )
    )


def _is_data_metrics_media_or_news_context_path(path: str) -> bool:
    return any(
        segment in path
        for segment in (
            "mtjj",
            "media",
            "ns_news",
            "kjdt",
            "xwdt",
            "xwzx",
            "news",
        )
    )


def _data_metrics_relevance_terms(task: QueryDecompositionTask) -> list[str]:
    stop_terms = {
        "全国",
        "中国",
        "数据",
        "统计",
        "统计数据",
        "指标",
        "规模",
        "价格",
        "出口",
        "进口",
        "产业",
        "年度",
        "月度",
        "能源",
        "统计公报",
        "国家统计局",
        "国家能源局",
        "国家数据局",
        "工业和信息化部",
    }
    region_terms = set(_project_region_terms(task))
    terms: list[str] = []
    phrase_text = " ".join(task.search_phrases)
    for phrase in task.search_phrases:
        for term in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]+", phrase):
            normalized = term.strip()
            if (
                len(normalized) < 2
                or normalized in stop_terms
                or normalized in region_terms
                or normalized.endswith(("统计局", "能源局", "数据局"))
                or normalized in terms
            ):
                continue
            terms.append(normalized)
    if any(term in phrase_text for term in ("绿电", "绿氢", "煤化工", "能源")):
        for proxy_term in (
            "用电量",
            "发电量",
            "电力运行",
            "电力供需",
            "能耗",
            "煤炭",
            "煤化工",
            "绿电",
            "绿氢",
        ):
            if proxy_term not in terms:
                terms.append(proxy_term)
    return terms[:8]


def _official_record_relevance_terms(task: QueryDecompositionTask) -> list[str]:
    stop_terms = {
        "全国",
        "项目",
        "环评",
        "环保",
        "公示",
        "土地",
        "土地出让",
        "自然资源",
        "项目备案",
        "审批",
        "备案",
        "建设",
        "生态环境",
        "能评",
        "能耗",
    }
    terms: list[str] = []
    region_terms = set(_project_region_terms(task))
    for phrase in task.search_phrases:
        for term in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]+", phrase):
            normalized = term.strip()
            if (
                len(normalized) < 2
                or normalized in stop_terms
                or normalized in region_terms
                or normalized in terms
            ):
                continue
            terms.append(normalized)
    return terms[:8]


def _project_region_terms(task: QueryDecompositionTask) -> list[str]:
    stop_terms = {"全国", "中国", "项目", "招标", "中标", "采购"}
    region_terms: list[str] = []
    for phrase in task.search_phrases:
        first_token = phrase.strip().split(" ", 1)[0].strip()
        if (
            "exact_local_depth" in task.evidence_obligations
            and 2 <= len(first_token) <= 8
            and first_token not in stop_terms
            and first_token not in region_terms
        ):
            region_terms.append(first_token)
        for region in generic_local_region_terms(phrase):
            if region not in region_terms:
                region_terms.append(region)
        for token in re.findall(r"[\u4e00-\u9fff]{2,8}", phrase):
            if token in stop_terms:
                continue
            if token.endswith(("省", "市", "县", "区", "旗")) or token in {
                "安徽",
                "内蒙古",
                "海南",
                "合肥",
                "常州",
                "西安",
                "肥西",
                "神木",
                "若羌",
            }:
                if token not in region_terms:
                    region_terms.append(token)
    return region_terms[:3]


def _project_relevance_terms(task: QueryDecompositionTask) -> list[str]:
    stop_terms = {
        "全国",
        "项目",
        "招标",
        "中标",
        "采购",
        "基础设施",
        "政策",
        "建设",
        "地方",
        "产业",
    }
    terms: list[str] = []
    for phrase in task.search_phrases:
        for term in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]+", phrase):
            normalized = term.strip()
            if len(normalized) < 2 or normalized in stop_terms or normalized in terms:
                continue
            terms.append(normalized)
    return terms[:8]


def _regional_data_source_ids(text: str) -> list[str]:
    mapping = {
        "安徽": ["cn_data_ah_stats_bulletin_v1", "cn_trade_ah_commerce_policy_v1"],
        "广东": ["cn_data_gd_stats_bulletin_v1", "cn_trade_gd_commerce_policy_v1"],
        "江苏": ["cn_data_js_stats_bulletin_v1", "cn_trade_js_commerce_policy_v1"],
        "常州": ["cn_data_js_stats_bulletin_v1", "cn_trade_js_commerce_policy_v1"],
        "浙江": ["cn_data_zj_stats_bulletin_v1", "cn_trade_zj_commerce_policy_v1"],
        "四川": ["cn_data_sc_stats_bulletin_v1", "cn_trade_sc_commerce_policy_v1"],
        "上海": ["cn_data_sh_stats_bulletin_v1", "cn_trade_sh_commerce_policy_v1"],
        "内蒙古": ["cn_data_nmg_stats_bulletin_v1"],
    }
    source_ids: list[str] = []
    for region, region_source_ids in mapping.items():
        if region in text:
            source_ids.extend(region_source_ids)
    return source_ids


def _regional_focus_for_task(task: QueryDecompositionTask) -> list[str]:
    focus: list[str] = []
    for phrase in task.search_phrases:
        first_token = phrase.strip().split(" ", 1)[0].strip()
        if first_token and len(first_token) <= 12 and first_token not in focus:
            focus.append(first_token)
    return focus[:3]


def _has_company_hint(task: QueryDecompositionTask) -> bool:
    text = _task_text(task)
    if re.search(r"\b\d{6}(?:\.(?:SZ|SH|BJ))?\b", text, flags=re.IGNORECASE):
        return True
    if re.search(r"\b[A-Z]{2,8}\b", text):
        return True
    nongeneric_text = text.replace("上市公司", "")
    company_markers = ("股份", "集团", "公司", "中信海直", "比亚迪")
    return any(marker in nongeneric_text for marker in company_markers)


def _task_text(task: QueryDecompositionTask) -> str:
    return " ".join([*task.search_phrases, task.evidence_goal, task.source_cluster])


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in tokens)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


__all__ = [
    "DirectLaneExecutionState",
    "DirectStructuredLaneExecutionResult",
    "DirectStructuredLaneExecutor",
]
