from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import Session

from packages.agents.provider import ProviderResolution, resolve_provider
from packages.agents.schemas import (
    EvidenceJudgeOutput,
    EvidenceSummary,
    FinalResearchMemo,
    ResearchAnalysisResult,
    ResearchAnalyzeRequest,
    ResearchMode,
    ResearchProvider,
    SourceAcquisitionSummary,
)
from packages.core.run_log import CompactRunLogger
from packages.db.models import Run, RunStatus, RunStep, RunType, StepStatus
from packages.rag.bundle import EvidenceBundleBuilder
from packages.rag.retrieval import ChunkRetrievalService
from packages.rag.schemas import EvidenceBundle, RetrievalChunkItem, RetrievalResponse
from packages.sources.citation import normalize_evidence_item
from packages.sources.enums import ToolErrorCode, ToolStatus
from packages.sources.performance import SourcePerformanceService
from packages.sources.quality import summarize_source_quality
from packages.sources.query_decomposition import QueryDecompositionTask, decompose_query
from packages.sources.schemas import (
    EvidenceBundle as SourceEvidenceBundle,
)
from packages.sources.schemas import (
    EvidenceItem as SourceEvidenceItem,
)
from packages.sources.schemas import (
    QueryContext,
    RoutingRecommendation,
    SourceSummaryItem,
    TimeRange,
    ToolError,
    ToolRequest,
    ToolTrace,
)
from packages.sources.search_assisted_domestic import (
    SEARCH_ASSISTED_SOURCE_ID,
    SEARCH_ASSISTED_SOURCE_NAME,
    SearchAssistedDomesticOrchestrator,
    convert_search_response_to_evidence_items,
)
from packages.sources.service import SourceIntelligenceService

T = TypeVar("T")

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc

SOURCE_STAGE_STEPS = (
    "source_route",
    "source_search",
    "source_fetch_detail",
    "source_extract_evidence",
    "source_build_bundle",
)

SOURCE_PDF_STAGE_STEPS = (
    "pdf_discover_attachments",
    "pdf_download",
    "pdf_extract",
    "pdf_extract_evidence",
)


@dataclass(slots=True)
class SourceAcquisitionArtifacts:
    retrieval: RetrievalResponse
    bundle: EvidenceBundle
    summary: SourceAcquisitionSummary


class ResearchWorkflowRunner:
    """Runs a deterministic, auditable multi-agent research workflow."""

    # TODO: Add optional self-reflection loop for thesis-objection refinement.
    # TODO: Emit scoring/eval artifacts for offline quality benchmarking.

    def __init__(
        self,
        session: Session,
        *,
        provider_resolution: ProviderResolution | None = None,
    ) -> None:
        self.session = session
        self.provider_resolution = provider_resolution
        self._active_provider = None
        self._provider_step_metadata: dict[str, dict[str, Any]] = {}
        self._run_logger: CompactRunLogger | None = None

    def run(self, request: ResearchAnalyzeRequest) -> ResearchAnalysisResult:
        fallback_provider = request.provider or (
            ResearchProvider.DEEPSEEK if request.mode == ResearchMode.LLM else ResearchProvider.MOCK
        )
        run = self._create_run(
            request=request,
            resolved_mode=request.mode,
            resolved_provider=fallback_provider,
            resolved_model=request.model,
            thinking_enabled=bool(request.enable_thinking),
        )
        self._run_logger = CompactRunLogger(task_name="research_analyze", run_id=run.id)
        self._run_logger.start(
            input_summary=run.input_json,
            decision_summary=[
                "resolve provider/model settings",
                (
                    "use source acquisition pipeline"
                    if request.enable_source_acquisition
                    else "use existing retrieval/evidence bundle pipeline"
                ),
                "run supervisor, thesis, opponent, evidence judge, risk, memo stages",
            ],
        )

        resolution: ProviderResolution | None = None
        source_summary = SourceAcquisitionSummary(
            enabled=request.enable_source_acquisition,
            pdf_summary=self._build_pdf_summary(
                enabled=(request.enable_source_acquisition and request.enable_pdf_processing)
            ),
        )

        try:
            resolution = self.provider_resolution or resolve_provider(
                mode=request.mode,
                provider=request.provider,
                model=request.model,
                step_models=request.step_models,
                enable_thinking=request.enable_thinking,
                debug_reasoning=request.debug_reasoning,
            )
            provider = resolution.provider
            self._active_provider = provider
            self._provider_step_metadata = {}
            self._update_run_resolution(run, resolution=resolution)

            if request.enable_source_acquisition:
                source_artifacts = self._run_source_acquisition(run=run, request=request)
                retrieval = source_artifacts.retrieval
                bundle = source_artifacts.bundle
                source_summary = source_artifacts.summary
            else:
                self._record_source_stages_skipped(
                    run=run,
                    reason="Source acquisition disabled for this request.",
                )
                retrieval_filters = request.to_retrieval_filters()
                retrieval = self._run_step(
                    run=run,
                    step_name="retrieve_evidence",
                    agent_name="rag-retrieval",
                    input_json={"query": request.query, **retrieval_filters.to_dict()},
                    fn=lambda: ChunkRetrievalService(self.session).search_chunks(
                        request.query, retrieval_filters
                    ),
                    output_serializer=lambda result: result.to_dict(),
                )
                bundle = self._run_step(
                    run=run,
                    step_name="build_evidence_bundle",
                    agent_name="rag-bundle-builder",
                    input_json={"group_by_document": True, "max_items": request.top_k},
                    fn=lambda: EvidenceBundleBuilder().build_bundle(
                        retrieval,
                        group_by_document=True,
                        max_items=request.top_k,
                    ),
                    output_serializer=lambda result: result.to_dict(),
                )
                source_summary = SourceAcquisitionSummary(
                    enabled=False,
                    notes=["disabled"],
                    pdf_summary=self._build_pdf_summary(enabled=False),
                )
            intake = self._run_step(
                run=run,
                step_name="supervisor_intake",
                agent_name=provider.supervisor.name,
                input_json={"query": request.query},
                fn=lambda: provider.supervisor.intake(request, bundle),
                output_serializer=lambda result: result.model_dump(mode="json"),
            )

            evidence_summary = self._build_evidence_summary(retrieval=retrieval, bundle=bundle)
            workflow_notes = [*resolution.notes]
            workflow_notes.extend(source_summary.notes)
            if intake.note:
                workflow_notes.append(intake.note)

            if not bundle.items:
                self._record_skipped_step(
                    run=run,
                    step_name="thesis_builder",
                    agent_name=provider.thesis_builder.name,
                    reason="No evidence items in bundle.",
                )
                self._record_skipped_step(
                    run=run,
                    step_name="opponent",
                    agent_name=provider.opponent.name,
                    reason="No theses generated due to empty evidence bundle.",
                )
                evidence_judge = self._run_step(
                    run=run,
                    step_name="evidence_judge",
                    agent_name=provider.evidence_judge.name,
                    input_json={"theses": 0, "objections": 0},
                    fn=lambda: provider.evidence_judge.run(
                        theses=[],
                        objections=[],
                        bundle=bundle,
                    ),
                    output_serializer=lambda result: result.model_dump(mode="json"),
                )
                self._record_skipped_step(
                    run=run,
                    step_name="risk_analyst",
                    agent_name=provider.risk_analyst.name,
                    reason="No theses available for risk extraction.",
                )
                memo = self._run_step(
                    run=run,
                    step_name="synthesize_memo",
                    agent_name=provider.supervisor.name,
                    input_json={"query": request.query, "insufficient_evidence": True},
                    fn=lambda: provider.supervisor.synthesize_memo(
                        query=request.query,
                        theses=[],
                        objections=[],
                        evidence_judge=evidence_judge,
                        risks=[],
                        insufficient_evidence=True,
                    ),
                    output_serializer=lambda result: result.model_dump(mode="json"),
                )
                result = ResearchAnalysisResult(
                    run_id=run.id,
                    query=request.query,
                    mode=resolution.resolved_mode,
                    provider=resolution.resolved_provider,
                    model=resolution.resolved_model,
                    thinking_enabled=resolution.thinking_enabled,
                    status=RunStatus.SUCCEEDED.value,
                    evidence_summary=evidence_summary,
                    theses=[],
                    objections=[],
                    evidence_judge=evidence_judge,
                    risks=[],
                    final_memo=memo,
                    confidence_score=memo.confidence_score,
                    insufficient_evidence=True,
                    source_acquisition=source_summary,
                    workflow_notes=workflow_notes,
                    provider_metadata=self._build_provider_metadata(),
                )
                self._finish_run(
                    run,
                    status=RunStatus.SUCCEEDED,
                    output_json=result.model_dump(mode="json"),
                )
                return result

            theses = self._run_step(
                run=run,
                step_name="thesis_builder",
                agent_name=provider.thesis_builder.name,
                input_json={"query": request.query, "bundle_id": bundle.bundle_id},
                fn=lambda: provider.thesis_builder.run(query=request.query, bundle=bundle),
            )
            objections = self._run_step(
                run=run,
                step_name="opponent",
                agent_name=provider.opponent.name,
                input_json={"thesis_count": len(theses)},
                fn=lambda: provider.opponent.run(theses=theses, bundle=bundle),
            )
            evidence_judge = self._run_step(
                run=run,
                step_name="evidence_judge",
                agent_name=provider.evidence_judge.name,
                input_json={"thesis_count": len(theses), "objection_count": len(objections)},
                fn=lambda: provider.evidence_judge.run(
                    theses=theses,
                    objections=objections,
                    bundle=bundle,
                ),
            )
            risks = self._run_step(
                run=run,
                step_name="risk_analyst",
                agent_name=provider.risk_analyst.name,
                input_json={"thesis_count": len(theses)},
                fn=lambda: provider.risk_analyst.run(
                    theses=theses,
                    evidence_judge=evidence_judge,
                    objections=objections,
                ),
            )
            insufficient_evidence = evidence_judge.overall_label in {"weak", "insufficient"}
            memo = self._run_step(
                run=run,
                step_name="synthesize_memo",
                agent_name=provider.supervisor.name,
                input_json={"query": request.query, "insufficient_evidence": insufficient_evidence},
                fn=lambda: provider.supervisor.synthesize_memo(
                    query=request.query,
                    theses=theses,
                    objections=objections,
                    evidence_judge=evidence_judge,
                    risks=risks,
                    insufficient_evidence=insufficient_evidence,
                ),
            )

            result = ResearchAnalysisResult(
                run_id=run.id,
                query=request.query,
                mode=resolution.resolved_mode,
                provider=resolution.resolved_provider,
                model=resolution.resolved_model,
                thinking_enabled=resolution.thinking_enabled,
                status=RunStatus.SUCCEEDED.value,
                evidence_summary=evidence_summary,
                theses=theses,
                objections=objections,
                evidence_judge=evidence_judge,
                risks=risks,
                final_memo=memo,
                confidence_score=memo.confidence_score,
                insufficient_evidence=insufficient_evidence,
                source_acquisition=source_summary,
                workflow_notes=workflow_notes,
                provider_metadata=self._build_provider_metadata(),
            )
            self._finish_run(
                run,
                status=RunStatus.SUCCEEDED,
                output_json=result.model_dump(mode="json"),
            )
            return result

        except Exception as exc:
            failed_result = self._build_failed_result(
                run_id=run.id,
                query=request.query,
                mode=(
                    resolution.resolved_mode
                    if resolution is not None
                    else request.mode
                ),
                provider=(
                    resolution.resolved_provider
                    if resolution is not None
                    else fallback_provider
                ),
                model=resolution.resolved_model if resolution is not None else request.model,
                thinking_enabled=(
                    resolution.thinking_enabled
                    if resolution is not None
                    else bool(request.enable_thinking)
                ),
                message=str(exc),
                notes=[*(resolution.notes if resolution is not None else [])],
                source_acquisition=source_summary,
            )
            self._finish_run(
                run,
                status=RunStatus.FAILED,
                output_json=failed_result.model_dump(mode="json"),
            )
            return failed_result
        finally:
            self._active_provider = None
            self._run_logger = None

    def _run_source_acquisition(
        self,
        *,
        run: Run,
        request: ResearchAnalyzeRequest,
    ) -> SourceAcquisitionArtifacts:
        source_performance_by_source = SourcePerformanceService(self.session).by_source()
        source_service = SourceIntelligenceService(
            source_performance_by_source=source_performance_by_source
        )
        query_context = self._build_source_query_context(request)
        source_request_payload = self._build_source_tool_payload(request)
        routed_sources = self._run_step(
            run=run,
            step_name="source_route",
            agent_name="source-router",
            input_json={
                "query": request.query,
                "source_ids_override": request.source_ids or [],
                "max_sources": query_context.max_sources,
                "include_user_sources": request.include_user_sources,
                "enable_pdf_processing": request.enable_pdf_processing,
                "max_pdf_attachments_per_source": request.max_pdf_attachments_per_source,
                "max_pdf_pages_per_attachment": request.max_pdf_pages_per_attachment,
                "source_performance_count": len(source_performance_by_source),
            },
            fn=lambda: self._resolve_source_recommendations(
                request=request,
                query_context=query_context,
                source_service=source_service,
            ),
            output_serializer=lambda items: {
                "routed_sources": [item.model_dump(mode="json") for item in items],
            },
        )

        search_responses: dict[str, Any] = {}
        search_doc_counts: dict[str, int] = {}
        detail_doc_counts: dict[str, int] = {}
        evidence_counts: dict[str, int] = {}
        search_documents: list[Any] = []
        detail_documents: list[Any] = []
        detail_normalized_documents: list[Any] = []
        source_evidence_items: list[SourceEvidenceItem] = []
        source_errors: list[ToolError] = []
        source_traces: list[ToolTrace] = []
        truncated_sources: set[str] = set()
        pdf_errors: list[str] = []
        pdf_metrics_by_source: dict[str, dict[str, int]] = {}
        pdf_summary = self._build_pdf_summary(enabled=request.enable_pdf_processing)
        decomposition_tasks: list[QueryDecompositionTask] = []
        search_assisted_task_outputs: list[tuple[QueryDecompositionTask, Any]] = []
        search_assisted_allowed_task_count = 0
        search_assisted_direct_keep_task_count = 0
        search_assisted_hold_or_refused_task_count = 0
        search_assisted_notes: list[str] = []
        search_assisted_coverage_gap_markers: list[str] = []
        search_assisted_coverage_gap_count = 0

        if request.source_ids:
            search_assisted_notes.append(
                "search_assisted_domestic_skipped_due_to_source_ids_override"
            )
        else:
            try:
                decomposition = decompose_query(request.query)
                decomposition_tasks = decomposition.decomposition_tasks
                if decomposition.unsupported_or_missing_sources:
                    search_assisted_notes.extend(decomposition.unsupported_or_missing_sources)
            except Exception as exc:
                source_errors.append(
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=f"query decomposition failed: {exc}",
                        retryable=False,
                        detail={"path": "search_assisted_domestic"},
                    )
                )

        def _search_stage() -> dict[str, Any]:
            nonlocal search_assisted_allowed_task_count
            nonlocal search_assisted_direct_keep_task_count
            nonlocal search_assisted_hold_or_refused_task_count
            nonlocal search_assisted_coverage_gap_count
            per_source: list[dict[str, Any]] = []
            for item in routed_sources:
                source_id = item.source_id
                adapter = source_service.source_registry.get_adapter(source_id)
                if adapter is None:
                    source_errors.append(
                        ToolError(
                            code=ToolErrorCode.SOURCE_NOT_FOUND,
                            message=f"Source '{source_id}' not found or disabled.",
                        )
                    )
                    search_doc_counts[source_id] = 0
                    per_source.append(
                        {
                            "source_id": source_id,
                            "status": "error",
                            "documents_found": 0,
                            "errors": 1,
                        }
                    )
                    continue

                response = adapter.search_documents(
                    ToolRequest(
                        tool_name="search_source_documents",
                        query_context=query_context,
                        source_id=source_id,
                        limit=query_context.max_documents_per_source,
                        max_evidence_per_source=query_context.max_evidence_per_source,
                        payload=source_request_payload,
                    )
                )
                search_responses[source_id] = response
                search_doc_counts[source_id] = len(response.documents)
                search_documents.extend(response.documents)
                source_errors.extend(response.errors)
                if response.trace is not None:
                    source_traces.append(response.trace)
                    if response.trace.truncated:
                        truncated_sources.add(source_id)
                per_source.append(
                    {
                        "source_id": source_id,
                        "status": response.status.value,
                        "documents_found": len(response.documents),
                        "errors": len(response.errors),
                    }
                )
            if not request.source_ids and decomposition_tasks:
                search_assisted_allowed_tasks = [
                    task
                    for task in decomposition_tasks
                    if task.execution_bucket == "search_assisted_sources"
                ]
                direct_keep_tasks = [
                    task
                    for task in decomposition_tasks
                    if task.execution_bucket == "direct_structured_sources"
                ]
                search_assisted_allowed_task_count = len(search_assisted_allowed_tasks)
                search_assisted_direct_keep_task_count = len(direct_keep_tasks)
                if search_assisted_direct_keep_task_count:
                    search_assisted_notes.append(
                        "search_assisted_direct_keep_controls_preserved"
                    )
                    search_assisted_notes.append(
                        f"direct_keep_task_count={search_assisted_direct_keep_task_count}"
                    )
                if search_assisted_allowed_tasks:
                    orchestrator = SearchAssistedDomesticOrchestrator(
                        max_candidates=query_context.max_documents_per_source
                    )
                    search_assisted_documents = 0
                    search_assisted_errors = 0
                    for task in search_assisted_allowed_tasks:
                        response = orchestrator.orchestrate_task(task)
                        search_assisted_task_outputs.append((task, response))
                        search_assisted_documents += len(response.documents)
                        search_assisted_errors += len(response.errors)
                        search_documents.extend(response.documents)
                        detail_documents.extend(response.documents)
                        detail_normalized_documents.extend(response.normalized_documents)
                        source_errors.extend(response.errors)
                        gate_decision = (
                            response.metadata.get("gate_decision")
                            if isinstance(response.metadata, dict)
                            else None
                        )
                        if gate_decision in {"hold", "refuse"}:
                            search_assisted_hold_or_refused_task_count += 1
                        if isinstance(response.metadata, dict):
                            coverage_gaps = response.metadata.get("coverage_gaps")
                            if isinstance(coverage_gaps, list):
                                for gap in coverage_gaps:
                                    if not isinstance(gap, dict):
                                        continue
                                    lane_id = gap.get("lane_id")
                                    reason_code = gap.get("reason_code")
                                    if not isinstance(lane_id, str) or not isinstance(
                                        reason_code,
                                        str,
                                    ):
                                        continue
                                    search_assisted_coverage_gap_count += 1
                                    search_assisted_coverage_gap_markers.append(
                                        f"coverage_gap:{lane_id}:{reason_code}"
                                    )
                        source_traces.append(
                            ToolTrace(
                                tool_name="search_assisted_domestic",
                                source_id=SEARCH_ASSISTED_SOURCE_ID,
                                status=response.status,
                                item_count=len(response.documents),
                                page_count=len(response.normalized_documents),
                                metadata={
                                    "task_id": task.task_id,
                                    "task_family": task.task_family,
                                    "execution_bucket": task.execution_bucket,
                                    "source_cluster": task.source_cluster,
                                    "candidate_decisions": [
                                        decision.model_dump(mode="json")
                                        for decision in response.candidate_decisions
                                    ],
                                    "response_metadata": response.metadata,
                                    "error_count": len(response.errors),
                                },
                            )
                        )
                    search_doc_counts[SEARCH_ASSISTED_SOURCE_ID] = search_assisted_documents
                    per_source.append(
                        {
                            "source_id": SEARCH_ASSISTED_SOURCE_ID,
                            "status": (
                                "success"
                                if search_assisted_documents > 0
                                else "partial"
                            ),
                            "documents_found": search_assisted_documents,
                            "errors": search_assisted_errors,
                        }
                    )
                else:
                    search_assisted_notes.append("search_assisted_no_allowed_tasks")
            return {
                "sources": per_source,
                "documents_found": len(search_documents),
                "errors": len(source_errors),
            }

        self._run_step(
            run=run,
            step_name="source_search",
            agent_name="source-search",
            input_json={
                "source_count": len(routed_sources),
                "enable_pdf_processing": request.enable_pdf_processing,
            },
            fn=_search_stage,
        )

        def _fetch_stage() -> dict[str, Any]:
            per_source: list[dict[str, Any]] = []
            doc_limit = query_context.max_documents_per_source
            for item in routed_sources:
                source_id = item.source_id
                adapter = source_service.source_registry.get_adapter(source_id)
                if adapter is None:
                    detail_doc_counts[source_id] = 0
                    per_source.append(
                        {
                            "source_id": source_id,
                            "status": "error",
                            "details_fetched": 0,
                            "errors": 1,
                        }
                    )
                    continue
                response = search_responses.get(source_id)
                source_docs = list(response.documents[:doc_limit]) if response is not None else []
                fetched_count = 0
                for document in source_docs:
                    detail_response = adapter.fetch_document_detail(
                        ToolRequest(
                            tool_name="fetch_document_detail",
                            query_context=query_context,
                            source_id=source_id,
                            document_id=document.document_id,
                            limit=query_context.max_documents_per_source,
                            max_evidence_per_source=query_context.max_evidence_per_source,
                            payload=source_request_payload,
                        )
                    )
                    detail_documents.extend(detail_response.documents)
                    detail_normalized_documents.extend(detail_response.normalized_documents)
                    source_errors.extend(detail_response.errors)
                    if detail_response.trace is not None:
                        source_traces.append(detail_response.trace)
                        if detail_response.trace.truncated:
                            truncated_sources.add(source_id)
                        trace_meta = (
                            detail_response.trace.metadata
                            if isinstance(detail_response.trace.metadata, dict)
                            else {}
                        )
                        attachment_count = trace_meta.get("attachment_count")
                        if isinstance(attachment_count, int) and attachment_count > 0:
                            pdf_summary["attachments_discovered"] = int(
                                pdf_summary["attachments_discovered"]
                            ) + attachment_count
                            pdf_metrics_by_source.setdefault(
                                source_id,
                                {
                                    "attachments_discovered": 0,
                                    "attachments_processed": 0,
                                    "pages_extracted": 0,
                                    "pdf_evidence_items_found": 0,
                                },
                            )
                            pdf_metrics_by_source[source_id]["attachments_discovered"] += (
                                attachment_count
                            )

                        pdf_processing = trace_meta.get("pdf_processing")
                        if isinstance(pdf_processing, dict):
                            processed_count = pdf_processing.get("processed_attachments")
                            pages_extracted = pdf_processing.get("pages_extracted")
                            if isinstance(processed_count, int) and processed_count > 0:
                                pdf_summary["attachments_processed"] = int(
                                    pdf_summary["attachments_processed"]
                                ) + processed_count
                                pdf_metrics_by_source.setdefault(
                                    source_id,
                                    {
                                        "attachments_discovered": 0,
                                        "attachments_processed": 0,
                                        "pages_extracted": 0,
                                        "pdf_evidence_items_found": 0,
                                    },
                                )
                                pdf_metrics_by_source[source_id]["attachments_processed"] += (
                                    processed_count
                                )
                            if isinstance(pages_extracted, int) and pages_extracted > 0:
                                pdf_summary["pages_extracted"] = int(
                                    pdf_summary["pages_extracted"]
                                ) + pages_extracted
                                pdf_metrics_by_source.setdefault(
                                    source_id,
                                    {
                                        "attachments_discovered": 0,
                                        "attachments_processed": 0,
                                        "pages_extracted": 0,
                                        "pdf_evidence_items_found": 0,
                                    },
                                )
                                pdf_metrics_by_source[source_id]["pages_extracted"] += (
                                    pages_extracted
                                )
                    for error in detail_response.errors:
                        message_lower = error.message.lower()
                        if "pdf" in message_lower:
                            pdf_errors.append(f"{source_id}:{error.message}")
                    fetched_count += len(detail_response.documents)
                detail_doc_counts[source_id] = fetched_count
                per_source.append(
                    {
                        "source_id": source_id,
                        "status": "success" if fetched_count > 0 else "partial",
                        "details_fetched": fetched_count,
                        "errors": 0,
                    }
                )
            if search_assisted_task_outputs:
                search_assisted_detail_count = sum(
                    len(response.documents)
                    for _, response in search_assisted_task_outputs
                )
                detail_doc_counts[SEARCH_ASSISTED_SOURCE_ID] = search_assisted_detail_count
                per_source.append(
                    {
                        "source_id": SEARCH_ASSISTED_SOURCE_ID,
                        "status": (
                            "success"
                            if search_assisted_detail_count > 0
                            else "partial"
                        ),
                        "details_fetched": search_assisted_detail_count,
                        "errors": 0,
                    }
                )
            return {
                "sources": per_source,
                "detail_documents": len(detail_documents),
                "normalized_documents": len(detail_normalized_documents),
                "errors": len(source_errors),
            }

        self._run_step(
            run=run,
            step_name="source_fetch_detail",
            agent_name="source-detail-fetcher",
            input_json={
                "source_count": len(routed_sources),
                "enable_pdf_processing": request.enable_pdf_processing,
            },
            fn=_fetch_stage,
        )

        def _extract_stage() -> dict[str, Any]:
            per_source: list[dict[str, Any]] = []
            for item in routed_sources:
                source_id = item.source_id
                adapter = source_service.source_registry.get_adapter(source_id)
                if adapter is None:
                    evidence_counts[source_id] = 0
                    per_source.append(
                        {
                            "source_id": source_id,
                            "status": "error",
                            "evidence_items": 0,
                            "errors": 1,
                        }
                    )
                    continue
                search_response = search_responses.get(source_id)
                seed_document_id = None
                if search_response is not None and search_response.documents:
                    seed_document_id = search_response.documents[0].document_id
                extract_response = adapter.extract_evidence_items(
                    ToolRequest(
                        tool_name="extract_evidence_items",
                        query_context=query_context,
                        source_id=source_id,
                        document_id=seed_document_id,
                        limit=query_context.max_documents_per_source,
                        max_evidence_per_source=query_context.max_evidence_per_source,
                        payload=source_request_payload,
                    )
                )
                profile = source_service.source_registry.get_profile(
                    source_id,
                    enabled_only=False,
                )
                normalized_items = [
                    normalize_evidence_item(
                        evidence_item,
                        source_name=(
                            profile.display_name if profile is not None else source_id
                        ),
                        external_id=evidence_item.citation.document_id,
                    )
                    for evidence_item in extract_response.evidence_items[
                        : query_context.max_evidence_per_source
                    ]
                ]
                pdf_item_count = sum(
                    1
                    for evidence_item in normalized_items
                    if isinstance(evidence_item.metadata, dict)
                    and bool(evidence_item.metadata.get("from_pdf_attachment"))
                )
                source_evidence_items.extend(normalized_items)
                source_errors.extend(extract_response.errors)
                for error in extract_response.errors:
                    if "pdf" in error.message.lower():
                        pdf_errors.append(f"{source_id}:{error.message}")
                evidence_counts[source_id] = len(normalized_items)
                if pdf_item_count > 0:
                    pdf_summary["pdf_evidence_items_found"] = int(
                        pdf_summary["pdf_evidence_items_found"]
                    ) + pdf_item_count
                    pdf_metrics_by_source.setdefault(
                        source_id,
                        {
                            "attachments_discovered": 0,
                            "attachments_processed": 0,
                            "pages_extracted": 0,
                            "pdf_evidence_items_found": 0,
                        },
                    )
                    pdf_metrics_by_source[source_id]["pdf_evidence_items_found"] += pdf_item_count
                if len(extract_response.evidence_items) > len(normalized_items):
                    truncated_sources.add(source_id)
                if extract_response.trace is not None:
                    trace = extract_response.trace.model_copy(
                        update={
                            "evidence_count": len(normalized_items),
                            "truncated": (
                                extract_response.trace.truncated
                                or len(extract_response.evidence_items) > len(normalized_items)
                            ),
                        }
                    )
                    source_traces.append(trace)
                    if trace.truncated:
                        truncated_sources.add(source_id)
                per_source.append(
                    {
                        "source_id": source_id,
                        "status": extract_response.status.value,
                        "evidence_items": len(normalized_items),
                        "pdf_evidence_items": pdf_item_count,
                        "errors": len(extract_response.errors),
                    }
                )
            if search_assisted_task_outputs:
                search_assisted_evidence_count = 0
                for task, response in search_assisted_task_outputs:
                    remaining_capacity = max(request.top_k - search_assisted_evidence_count, 0)
                    if remaining_capacity == 0:
                        break
                    converted_items = convert_search_response_to_evidence_items(
                        task=task,
                        response=response,
                        max_items=min(
                            query_context.max_evidence_per_source,
                            remaining_capacity,
                        ),
                    )
                    source_evidence_items.extend(converted_items)
                    search_assisted_evidence_count += len(converted_items)
                    source_traces.append(
                        ToolTrace(
                            tool_name="search_assisted_evidence_conversion",
                            source_id=SEARCH_ASSISTED_SOURCE_ID,
                            status=(
                                ToolStatus.SUCCESS
                                if converted_items
                                else (
                                    ToolStatus.UNSUPPORTED
                                    if response.status == ToolStatus.UNSUPPORTED
                                    else ToolStatus.PARTIAL
                                )
                            ),
                            item_count=len(response.normalized_documents),
                            evidence_count=len(converted_items),
                            metadata={
                                "task_id": task.task_id,
                                "task_family": task.task_family,
                                "source_cluster": task.source_cluster,
                                "response_status": response.status.value,
                            },
                        )
                    )
                evidence_counts[SEARCH_ASSISTED_SOURCE_ID] = search_assisted_evidence_count
                per_source.append(
                    {
                        "source_id": SEARCH_ASSISTED_SOURCE_ID,
                        "status": (
                            "success"
                            if search_assisted_evidence_count > 0
                            else "partial"
                        ),
                        "evidence_items": search_assisted_evidence_count,
                        "pdf_evidence_items": 0,
                        "errors": sum(
                            len(response.errors)
                            for _, response in search_assisted_task_outputs
                        ),
                    }
                )
            return {
                "sources": per_source,
                "evidence_items": len(source_evidence_items),
                "errors": len(source_errors),
            }

        self._run_step(
            run=run,
            step_name="source_extract_evidence",
            agent_name="source-evidence-extractor",
            input_json={
                "source_count": len(routed_sources),
                "enable_pdf_processing": request.enable_pdf_processing,
            },
            fn=_extract_stage,
        )

        if request.enable_pdf_processing:
            if pdf_errors:
                deduplicated_errors = list(dict.fromkeys(pdf_errors))
                pdf_summary["errors"] = deduplicated_errors[:50]
            self._run_step(
                run=run,
                step_name="pdf_discover_attachments",
                agent_name="source-pdf",
                input_json={"enabled": True},
                fn=lambda: {
                    "enabled": True,
                    "attachments_discovered": pdf_summary["attachments_discovered"],
                    "by_source": {
                        source_id: values["attachments_discovered"]
                        for source_id, values in pdf_metrics_by_source.items()
                    },
                },
            )
            self._run_step(
                run=run,
                step_name="pdf_download",
                agent_name="source-pdf",
                input_json={"enabled": True},
                fn=lambda: {
                    "enabled": True,
                    "attachments_processed": pdf_summary["attachments_processed"],
                    "errors": pdf_summary["errors"],
                    "by_source": {
                        source_id: values["attachments_processed"]
                        for source_id, values in pdf_metrics_by_source.items()
                    },
                },
            )
            self._run_step(
                run=run,
                step_name="pdf_extract",
                agent_name="source-pdf",
                input_json={"enabled": True},
                fn=lambda: {
                    "enabled": True,
                    "pages_extracted": pdf_summary["pages_extracted"],
                    "errors": pdf_summary["errors"],
                    "by_source": {
                        source_id: values["pages_extracted"]
                        for source_id, values in pdf_metrics_by_source.items()
                    },
                },
            )
            self._run_step(
                run=run,
                step_name="pdf_extract_evidence",
                agent_name="source-pdf",
                input_json={"enabled": True},
                fn=lambda: {
                    "enabled": True,
                    "pdf_evidence_items_found": pdf_summary["pdf_evidence_items_found"],
                    "errors": pdf_summary["errors"],
                    "by_source": {
                        source_id: values["pdf_evidence_items_found"]
                        for source_id, values in pdf_metrics_by_source.items()
                    },
                },
            )
        else:
            for step_name in SOURCE_PDF_STAGE_STEPS:
                self._record_skipped_step(
                    run=run,
                    step_name=step_name,
                    agent_name="source-pdf",
                    reason="PDF processing disabled for this request.",
                )

        artifact_holder: dict[str, SourceAcquisitionArtifacts] = {}

        def _build_bundle_stage() -> dict[str, Any]:
            source_summary_items: list[SourceSummaryItem] = []
            routed_source_ids = [item.source_id for item in routed_sources]
            routing_recommendation_payload = [
                item.model_dump(mode="json") for item in routed_sources
            ]
            include_search_assisted_source = bool(
                search_assisted_task_outputs or search_assisted_allowed_task_count > 0
            )
            if (
                include_search_assisted_source
                and SEARCH_ASSISTED_SOURCE_ID not in routed_source_ids
            ):
                routed_source_ids.append(SEARCH_ASSISTED_SOURCE_ID)
                routing_recommendation_payload.append(
                    {
                        "source_id": SEARCH_ASSISTED_SOURCE_ID,
                        "reason": (
                            "query decomposition routed allowed tasks to "
                            "search-assisted domestic execution"
                        ),
                        "priority": 50,
                        "final_score": 50.0,
                        "score_breakdown": {"search_assisted_domestic": 50.0},
                        "selected_via": "query_decomposition",
                        "matched_terms": [],
                    }
                )
            for recommendation in routed_sources:
                source_id = recommendation.source_id
                profile = source_service.source_registry.get_profile(source_id, enabled_only=False)
                source_summary_items.append(
                    SourceSummaryItem(
                        source_id=source_id,
                        source_name=(
                            profile.display_name
                            if profile is not None
                            else source_id
                        ),
                        document_count=max(
                            search_doc_counts.get(source_id, 0),
                            detail_doc_counts.get(source_id, 0),
                        ),
                        evidence_count=evidence_counts.get(source_id, 0),
                        notes=[recommendation.reason],
                    )
                )
            if include_search_assisted_source:
                search_assisted_note_items: list[str] = [
                    (
                        "search-assisted domestic evidence from allowed "
                        "query-decomposition tasks"
                    ),
                    f"allowed_tasks={search_assisted_allowed_task_count}",
                    (
                        "direct_keep_controls="
                        f"{search_assisted_direct_keep_task_count}"
                    ),
                    (
                        "hold_or_refused_tasks="
                        f"{search_assisted_hold_or_refused_task_count}"
                    ),
                ]
                source_summary_items.append(
                    SourceSummaryItem(
                        source_id=SEARCH_ASSISTED_SOURCE_ID,
                        source_name=SEARCH_ASSISTED_SOURCE_NAME,
                        document_count=max(
                            search_doc_counts.get(SEARCH_ASSISTED_SOURCE_ID, 0),
                            detail_doc_counts.get(SEARCH_ASSISTED_SOURCE_ID, 0),
                        ),
                        evidence_count=evidence_counts.get(SEARCH_ASSISTED_SOURCE_ID, 0),
                        notes=[*search_assisted_note_items, *search_assisted_notes],
                    )
                )

            gaps: list[str] = []
            if not routed_source_ids:
                gaps.append("no_routed_sources")
            if not source_evidence_items:
                gaps.append("no_evidence_items_extracted")
            if source_errors:
                gaps.extend(self._source_error_messages(source_errors))
            if search_assisted_coverage_gap_markers:
                gaps.extend(
                    list(dict.fromkeys(search_assisted_coverage_gap_markers))
                )

            source_quality_summary = summarize_source_quality(
                source_ids=routed_source_ids,
                traces=source_traces,
                errors=source_errors,
                evidence_items=source_evidence_items,
                source_summaries=source_summary_items,
            )
            source_bundle = SourceEvidenceBundle(
                query=request.query,
                items=source_evidence_items,
                evidence_items=source_evidence_items,
                source_summary=source_summary_items,
                sources=source_summary_items,
                gaps=gaps,
                metadata={
                    "mode": "source_acquisition_v1",
                    "routed_source_count": len(routed_sources),
                    "error_count": len(source_errors),
                    "truncated_sources": sorted(truncated_sources),
                    "pdf_summary": pdf_summary,
                    "source_quality_summary": source_quality_summary.model_dump(mode="json"),
                    "source_traces": [
                        trace.model_dump(mode="json") for trace in source_traces
                    ],
                },
            )
            retrieval, bundle = self._convert_source_bundle_to_rag(
                request=request,
                source_bundle=source_bundle,
            )
            notes: list[str] = []
            if not routed_sources:
                notes.append("No sources were routed for this query.")
            if source_errors:
                notes.append(f"{len(source_errors)} source adapter error(s) observed.")
            if not source_evidence_items:
                notes.append("Source acquisition produced no evidence items.")
            if source_quality_summary.sources_failed > 0:
                notes.append(
                    f"{source_quality_summary.sources_failed} source(s) "
                    "failed or returned unusable output."
                )
            if include_search_assisted_source:
                notes.append(
                    "Search-assisted domestic path executed via query decomposition "
                    f"(allowed_tasks={search_assisted_allowed_task_count}, "
                    f"direct_keep_controls={search_assisted_direct_keep_task_count}, "
                    f"hold_or_refused={search_assisted_hold_or_refused_task_count})."
                )
            if search_assisted_coverage_gap_count > 0:
                notes.append(
                    f"coverage_gap_count={search_assisted_coverage_gap_count}"
                )
                notes.extend(
                    list(dict.fromkeys(search_assisted_coverage_gap_markers))
                )
            notes.extend(search_assisted_notes)
            if request.enable_pdf_processing:
                notes.append(
                    "PDF processing enabled for source acquisition "
                    f"(processed={pdf_summary['attachments_processed']}, "
                    f"pdf_evidence={pdf_summary['pdf_evidence_items_found']})."
                )
                if pdf_summary["errors"]:
                    notes.append(
                        f"PDF processing observed {len(pdf_summary['errors'])} error(s)."
                    )

            artifact_holder["value"] = SourceAcquisitionArtifacts(
                retrieval=retrieval,
                bundle=bundle,
                summary=SourceAcquisitionSummary(
                    enabled=True,
                    routed_sources=routed_source_ids,
                    routing_recommendations=routing_recommendation_payload,
                    documents_found=len(search_documents),
                    evidence_items_found=len(source_evidence_items),
                    bundle_id=bundle.bundle_id,
                    source_quality_summary=source_quality_summary.model_dump(mode="json"),
                    source_traces=[
                        trace.model_dump(mode="json") for trace in source_traces
                    ],
                    truncated_sources=sorted(truncated_sources),
                    notes=notes,
                    pdf_summary=pdf_summary,
                ),
            )
            return {
                "bundle_id": bundle.bundle_id,
                "routed_sources": routed_source_ids,
                "documents_found": len(search_documents),
                "evidence_items_found": len(source_evidence_items),
                "pdf_summary": pdf_summary,
                "source_quality_summary": source_quality_summary.model_dump(mode="json"),
                "trace_count": len(source_traces),
                "gaps": gaps,
            }

        self._run_step(
            run=run,
            step_name="source_build_bundle",
            agent_name="source-bundle-builder",
            input_json={"top_k": request.top_k},
            fn=_build_bundle_stage,
        )
        return artifact_holder["value"]

    def _record_source_stages_skipped(self, *, run: Run, reason: str) -> None:
        for step_name in [*SOURCE_STAGE_STEPS, *SOURCE_PDF_STAGE_STEPS]:
            self._record_skipped_step(
                run=run,
                step_name=step_name,
                agent_name="source-intelligence",
                reason=reason,
            )

    def _build_source_query_context(self, request: ResearchAnalyzeRequest) -> QueryContext:
        time_range = None
        if request.published_from is not None or request.published_to is not None:
            time_range = TimeRange(start_at=request.published_from, end_at=request.published_to)
        max_sources = (
            request.max_sources
            if request.max_sources is not None
            else min(request.top_k, 10)
        )
        max_documents_per_source = (
            request.max_docs_per_source
            if request.max_docs_per_source is not None
            else min(request.top_k, 10)
        )
        max_evidence_per_source = (
            request.max_evidence_per_source
            if request.max_evidence_per_source is not None
            else min(request.top_k, 10)
        )
        return QueryContext(
            query=request.query,
            time_range=time_range,
            industry=request.industry,
            user_provided_sources=(
                request.user_provided_sources if request.include_user_sources else []
            ),
            max_sources=max_sources,
            max_documents_per_source=max_documents_per_source,
            max_evidence_per_source=max_evidence_per_source,
            metadata={
                "from_research": True,
                "research_top_k": request.top_k,
                "theme_id": request.theme_id,
                "document_id": request.document_id,
                "enable_pdf_processing": request.enable_pdf_processing,
                "max_pdf_attachments_per_source": request.max_pdf_attachments_per_source,
                "max_pdf_pages_per_attachment": request.max_pdf_pages_per_attachment,
            },
        )

    def _build_source_tool_payload(self, request: ResearchAnalyzeRequest) -> dict[str, Any]:
        return {
            "enable_pdf_processing": request.enable_pdf_processing,
            "max_pdf_attachments_per_source": request.max_pdf_attachments_per_source,
            # Backward-compat key for existing adapters/tests.
            "max_pdf_attachments_per_document": request.max_pdf_attachments_per_source,
            "max_pdf_pages_per_attachment": request.max_pdf_pages_per_attachment,
        }

    def _build_pdf_summary(self, *, enabled: bool) -> dict[str, Any]:
        return {
            "enabled": enabled,
            "attachments_discovered": 0,
            "attachments_processed": 0,
            "pages_extracted": 0,
            "pdf_evidence_items_found": 0,
            "errors": [],
        }

    def _resolve_source_recommendations(
        self,
        *,
        request: ResearchAnalyzeRequest,
        query_context: QueryContext,
        source_service: SourceIntelligenceService,
    ) -> list[RoutingRecommendation]:
        if request.source_ids:
            routed: list[RoutingRecommendation] = []
            for index, source_id in enumerate(request.source_ids):
                routed.append(
                    RoutingRecommendation(
                        source_id=source_id,
                        reason="Explicit source_ids override.",
                        priority=max(1, 100 - index),
                        final_score=float(max(1, 100 - index)),
                        score_breakdown={"explicit_source_ids": 100.0 - index},
                        selected_via="explicit_source_ids",
                    )
                )
            return routed

        routed = source_service.route_sources(query_context)
        if (
            request.include_user_sources
            and query_context.user_provided_sources
            and not any(item.source_id == "user_input" for item in routed)
        ):
            routed = [
                RoutingRecommendation(
                    source_id="user_input",
                    reason="user_provided_sources present; force-include user_input.",
                    priority=100,
                    final_score=100.0,
                    score_breakdown={"forced_user_input": 100.0},
                    selected_via="user_provided_sources",
                    matched_terms=["user_provided_sources"],
                ),
                *routed,
            ]
        return routed[: query_context.max_sources]

    def _convert_source_bundle_to_rag(
        self,
        *,
        request: ResearchAnalyzeRequest,
        source_bundle: SourceEvidenceBundle,
    ) -> tuple[RetrievalResponse, EvidenceBundle]:
        doc_id_map: dict[str, int] = {}
        rag_items: list[RetrievalChunkItem] = []
        for idx, item in enumerate(source_bundle.items):
            citation = item.citation
            doc_key = citation.document_id or item.evidence_id
            if doc_key not in doc_id_map:
                doc_id_map[doc_key] = 1_000_000 + len(doc_id_map)
            rag_items.append(
                RetrievalChunkItem(
                    chunk_id=2_000_000 + idx,
                    document_id=doc_id_map[doc_key],
                    chunk_index=idx,
                    section_name=citation.locator.section_id,
                    chunk_text=(
                        item.support_text
                        or item.summary
                        or citation.quote_text
                        or ""
                    ),
                    chunk_metadata=item.metadata or {},
                    citation_locator=(
                        citation.locator.external_ref
                        or citation.locator.section_id
                    ),
                    citation_quote=citation.quote_text,
                    document_title=item.title,
                    source_uri=citation.source_uri,
                    publisher=item.metadata.get("publisher")
                    if isinstance(item.metadata, dict)
                    else None,
                    published_at=citation.published_at,
                    source_type=item.source_id,
                    document_status="parsed",
                    industry=request.industry,
                    score=item.score,
                    score_breakdown={"source_adapter_score": round(item.score, 6)},
                )
            )
        retrieval = RetrievalResponse(
            query=request.query,
            retrieval_mode="source_acquisition_v1",
            filters=request.to_retrieval_filters(),
            total_candidates=len(rag_items),
            items=rag_items,
            notes=[*source_bundle.gaps],
        )
        bundle = EvidenceBundleBuilder().build_bundle(
            retrieval,
            group_by_document=True,
            max_items=request.top_k,
        )
        return retrieval, bundle

    def _source_error_messages(self, errors: list[ToolError]) -> list[str]:
        messages: list[str] = []
        for error in errors[:10]:
            messages.append(f"{error.code.value}: {error.message}")
        return messages

    def _create_run(
        self,
        *,
        request: ResearchAnalyzeRequest,
        resolved_mode: ResearchMode,
        resolved_provider: ResearchProvider,
        resolved_model: str | None,
        thinking_enabled: bool,
    ) -> Run:
        run = Run(
            run_type=RunType.RESEARCH,
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
            input_json={
                "pipeline": "multi_agent_research_v1",
                "query": request.query,
                "mode_requested": request.mode.value,
                "mode_resolved": resolved_mode.value,
                "provider_requested": (
                    request.provider.value if request.provider is not None else None
                ),
                "provider_resolved": resolved_provider.value,
                "model_requested": request.model,
                "model_resolved": resolved_model,
                "step_models_requested": request.step_models or {},
                "thinking_requested": request.enable_thinking,
                "thinking_resolved": thinking_enabled,
                "debug_reasoning": request.debug_reasoning,
                "filters": request.to_retrieval_filters().to_dict(),
                "source_acquisition": {
                    "enabled": request.enable_source_acquisition,
                    "max_sources": request.max_sources,
                    "max_docs_per_source": request.max_docs_per_source,
                    "max_evidence_per_source": request.max_evidence_per_source,
                    "enable_pdf_processing": request.enable_pdf_processing,
                    "max_pdf_attachments_per_source": request.max_pdf_attachments_per_source,
                    "max_pdf_pages_per_attachment": request.max_pdf_pages_per_attachment,
                    "source_ids": request.source_ids or [],
                    "include_user_sources": request.include_user_sources,
                    "user_sources_count": (
                        len(request.user_provided_sources)
                        if request.include_user_sources
                        else 0
                    ),
                },
            },
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def _update_run_resolution(self, run: Run, *, resolution: ProviderResolution) -> None:
        input_json = dict(run.input_json or {})
        input_json["mode_resolved"] = resolution.resolved_mode.value
        input_json["provider_resolved"] = resolution.resolved_provider.value
        input_json["model_resolved"] = resolution.resolved_model
        input_json["step_models_resolved"] = resolution.resolved_step_models
        input_json["thinking_resolved"] = resolution.thinking_enabled
        input_json["debug_reasoning"] = resolution.debug_reasoning
        run.input_json = input_json
        self.session.add(run)
        self.session.commit()

    def _run_step(
        self,
        *,
        run: Run,
        step_name: str,
        agent_name: str,
        input_json: dict[str, Any] | None,
        fn: Callable[[], T],
        output_serializer: (
            Callable[[T], dict[str, Any] | list[dict[str, Any]] | None] | None
        ) = None,
    ) -> T:
        step = RunStep(
            run_id=run.id,
            step_name=step_name,
            agent_name=agent_name,
            status=StepStatus.RUNNING,
            started_at=datetime.now(UTC),
            input_json=input_json,
        )
        self.session.add(step)
        self.session.commit()
        self.session.refresh(step)

        try:
            result = fn()
        except Exception as exc:
            step.status = StepStatus.FAILED
            step.error_message = str(exc)
            step.finished_at = datetime.now(UTC)
            self.session.add(step)
            self.session.commit()
            if self._run_logger is not None:
                self._run_logger.step(
                    step_name=step_name,
                    agent_name=agent_name,
                    input_summary=input_json,
                    status=StepStatus.FAILED.value,
                    error=str(exc),
                )
            raise

        step.status = StepStatus.SUCCEEDED
        step.finished_at = datetime.now(UTC)
        output_value: dict[str, Any] | None
        if output_serializer is not None:
            output_value = self._ensure_output_json(output_serializer(result))
        else:
            output_value = self._ensure_output_json(result)
        provider_step_meta = self._consume_provider_step_metadata(step_name)
        if provider_step_meta is not None:
            output_value = dict(output_value or {})
            output_value["_provider"] = provider_step_meta
        step.output_json = output_value
        self.session.add(step)
        self.session.commit()
        if self._run_logger is not None:
            self._run_logger.step(
                step_name=step_name,
                agent_name=agent_name,
                input_summary=input_json,
                output_summary=output_value,
                status=StepStatus.SUCCEEDED.value,
            )
        return result

    def _record_skipped_step(
        self,
        *,
        run: Run,
        step_name: str,
        agent_name: str,
        reason: str,
    ) -> None:
        step = RunStep(
            run_id=run.id,
            step_name=step_name,
            agent_name=agent_name,
            status=StepStatus.SKIPPED,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            output_json={"reason": reason},
        )
        self.session.add(step)
        self.session.commit()
        if self._run_logger is not None:
            self._run_logger.step(
                step_name=step_name,
                agent_name=agent_name,
                input_summary={"reason": reason},
                output_summary={"reason": reason},
                status=StepStatus.SKIPPED.value,
            )

    def _build_evidence_summary(
        self, *, retrieval: RetrievalResponse, bundle: EvidenceBundle
    ) -> EvidenceSummary:
        top_documents: list[str] = []
        for item in bundle.items:
            if item.document_title not in top_documents:
                top_documents.append(item.document_title)

        top_evidence = []
        for item in bundle.items[:5]:
            top_evidence.append(
                {
                    "chunk_id": item.chunk_id,
                    "document_id": item.document_id,
                    "locator": item.citation_locator,
                    "section_name": item.section_name,
                    "score": item.score,
                }
            )

        return EvidenceSummary(
            bundle_id=bundle.bundle_id,
            retrieval_mode=retrieval.retrieval_mode,
            total_candidates=retrieval.total_candidates,
            selected_items=len(bundle.items),
            sufficient=len(bundle.items) > 0,
            notes=retrieval.notes,
            top_documents=top_documents[:5],
            top_evidence=top_evidence,
        )

    def _finish_run(self, run: Run, *, status: RunStatus, output_json: dict[str, Any]) -> None:
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.output_json = output_json
        self.session.add(run)
        self.session.commit()
        if self._run_logger is not None:
            self._run_logger.finish(status=status.value, output_summary=output_json)

    def _consume_provider_step_metadata(self, step_name: str) -> dict[str, Any] | None:
        if self._active_provider is None:
            return None
        metadata = self._active_provider.pop_step_metadata(step_name)
        if metadata is None:
            return None
        self._provider_step_metadata[step_name] = metadata
        return metadata

    def _build_provider_metadata(self) -> dict[str, Any] | None:
        if not self._provider_step_metadata:
            return None
        return {"steps": self._provider_step_metadata}

    def _build_failed_result(
        self,
        *,
        run_id: int,
        query: str,
        mode: ResearchMode,
        provider: ResearchProvider,
        model: str | None,
        thinking_enabled: bool,
        message: str,
        notes: list[str],
        source_acquisition: SourceAcquisitionSummary | None = None,
    ) -> ResearchAnalysisResult:
        evidence_judge = EvidenceJudgeOutput(
            coverage=[],
            overall_sufficiency_score=0.0,
            overall_label="insufficient",
            global_gaps=["Workflow failed before reliable judgement could be completed."],
        )
        memo = FinalResearchMemo(
            query=query,
            executive_summary=(
                "Research workflow failed before completion; inspect run steps for details."
            ),
            key_theses=[],
            counterarguments=[],
            evidence_gaps=evidence_judge.global_gaps,
            major_risks=[],
            confidence_assessment="insufficient confidence due to workflow failure",
            confidence_score=0.0,
            suggested_next_questions=["Which stage failed and what input caused the failure?"],
        )
        return ResearchAnalysisResult(
            run_id=run_id,
            query=query,
            mode=mode,
            provider=provider,
            model=model,
            thinking_enabled=thinking_enabled,
            status=RunStatus.FAILED.value,
            evidence_summary=EvidenceSummary(
                bundle_id="bundle_unavailable",
                retrieval_mode="unavailable",
                total_candidates=0,
                selected_items=0,
                sufficient=False,
                notes=["Research workflow failed before producing evidence summary."],
                top_documents=[],
                top_evidence=[],
            ),
            theses=[],
            objections=[],
            evidence_judge=evidence_judge,
            risks=[],
            final_memo=memo,
            confidence_score=0.0,
            insufficient_evidence=True,
            source_acquisition=source_acquisition,
            workflow_notes=notes,
            provider_metadata=self._build_provider_metadata(),
            error_message=message,
        )

    def _ensure_output_json(self, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if hasattr(value, "to_dict"):
            return value.to_dict()  # type: ignore[no-any-return]
        if isinstance(value, list):
            serialized_list = []
            for item in value:
                if isinstance(item, BaseModel):
                    serialized_list.append(item.model_dump(mode="json"))
                elif hasattr(item, "to_dict"):
                    serialized_list.append(item.to_dict())  # type: ignore[no-any-return]
                else:
                    serialized_list.append(item)
            return {"items": serialized_list}
        return {"value": str(value)}
