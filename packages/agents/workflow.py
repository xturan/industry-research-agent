from __future__ import annotations

from collections.abc import Callable
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
)
from packages.db.models import Run, RunStatus, RunStep, RunType, StepStatus
from packages.rag.bundle import EvidenceBundleBuilder
from packages.rag.retrieval import ChunkRetrievalService
from packages.rag.schemas import EvidenceBundle, RetrievalResponse

T = TypeVar("T")

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc


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

        resolution: ProviderResolution | None = None

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
            )
            self._finish_run(
                run,
                status=RunStatus.FAILED,
                output_json=failed_result.model_dump(mode="json"),
            )
            return failed_result
        finally:
            self._active_provider = None

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
