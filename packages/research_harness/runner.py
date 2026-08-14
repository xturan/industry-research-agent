from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from packages.db.models import Run, RunStatus, RunStep, RunType, StepStatus
from packages.research_harness.checkpoints import GraphCheckpointRepository
from packages.research_harness.context import build_context_pack_summary
from packages.research_harness.eval_persistence import RunEvaluationStore
from packages.research_harness.evaluation_recorder import (
    finalize_evaluation_run,
    resume_suspended_tasks,
)
from packages.research_harness.graph import build_research_graph
from packages.research_harness.nodes import (
    advisory_gap_backfill,
    build_evidence,
    chief_gate,
    collect_sources,
    editor1_draft,
    editor2_review,
    finalize_report,
    human_review,
    parse_sources,
    plan_task,
    score_sources,
    structured_shadow_editor1,
)
from packages.research_harness.persistence import GraphBusinessRecordRepository
from packages.research_harness.retrieval_bridge import cleanup_graph_runtime_documents
from packages.research_harness.schemas import (
    GraphAnalyzeRequest,
    GraphAnalyzeResponse,
    GraphCheckpointView,
    GraphContextPackSummary,
    GraphHumanReviewState,
    GraphNodeStepSummary,
)
from packages.research_harness.state import ResearchGraphState, build_initial_state
from packages.research_harness.tooling import ToolExecutor, ToolHarness, ToolSession
from packages.research_reports.dossier import write_graph_research_dossier
from packages.research_reports.schemas import ResearchReportCreate
from packages.research_reports.service import ResearchReportService


class ResearchGraphRunner:
    def __init__(
        self,
        session: Session,
        *,
        checkpoint_repository: GraphCheckpointRepository | None = None,
    ) -> None:
        self.session = session
        self.checkpoint_repository = checkpoint_repository or GraphCheckpointRepository(
            session=session
        )
        self.business_repository = GraphBusinessRecordRepository(session)
        self.tool_harness = ToolHarness()
        self.tool_executor = ToolExecutor()

    def run(
        self,
        request: GraphAnalyzeRequest,
        *,
        task_job_id: int | None = None,
    ) -> GraphAnalyzeResponse:
        resumed_from_checkpoint = False
        if request.resume_run_id is not None:
            run = self._get_existing_run(request.resume_run_id)
            if run is None:
                raise ValueError(f"Run {request.resume_run_id} not found for resume.")
            initial_state = self._load_resume_state(run=run, request=request)
            resumed_from_checkpoint = True
        else:
            run = self._create_run(request=request, task_job_id=task_job_id)
            initial_state = build_initial_state(
                run_id=run.id,
                task_job_id=task_job_id,
                query=request.query,
                max_rounds=request.max_rounds,
                max_loop_count=request.max_loop_count,
                strategy=_strategy_from_execution_mode(request.execution_mode),
            )
        if resumed_from_checkpoint:
            final_state = self._resume_from_checkpoint(initial_state)
        else:
            graph = build_research_graph(self)
            final_state = graph.invoke(initial_state)
        # B.3.3b: central run-termination (independent of finalize_report). Closes
        # or suspends remaining planned/running SearchTasks on EVERY termination
        # path (REPORT_COMPLETED / HUMAN_REVIEW / BUDGET_EXHAUSTED / PROVIDER_FAILED
        # / GRAPH_ERROR / USER_CANCELLED), so no task is left semantically
        # ambiguous even when finalize_report never ran.
        final_state = self._finalize_evaluation(final_state)
        checkpoint_path = self._save_checkpoint(final_state)
        status = RunStatus.FAILED if final_state.get("error") else RunStatus.SUCCEEDED
        checkpoint_history = self._checkpoint_history_views(run.id)
        response = GraphAnalyzeResponse(
            run_id=run.id,
            task_job_id=task_job_id,
            thread_id=str(final_state["thread_id"]),
            status=status.value,
            decision=final_state.get("decision"),
            quality_scores={
                key: float(value) for key, value in final_state.get("quality_scores", {}).items()
            },
            node_steps=[
                GraphNodeStepSummary(**step) for step in final_state.get("node_steps", [])
            ],
            context_packs=[
                GraphContextPackSummary(
                    **{
                        key: value
                        for key, value in pack.items()
                        if key in GraphContextPackSummary.model_fields
                    }
                )
                for pack in final_state.get("context_packs", [])
            ],
            report_preview=final_state.get("final_report", {}),
            human_review=_human_review_response(final_state),
            checkpoint_path=checkpoint_path,
            resumed_from_checkpoint=resumed_from_checkpoint,
            checkpoint_history=checkpoint_history,
        )
        dossier_path = self._write_dossier(
            query=request.query,
            response_json=response.model_dump(mode="json"),
            final_state=final_state,
        )
        if dossier_path is not None:
            response = response.model_copy(update={"dossier_path": str(dossier_path)})
        report_id = self._save_report_artifact(
            run=run,
            query=request.query,
            final_state=final_state,
            dossier_path=response.dossier_path,
            status=status,
        )
        if report_id is not None:
            report_preview = dict(response.report_preview)
            report_preview["report_id"] = report_id
            report_preview["report_artifact"] = {
                "report_id": report_id,
                "workflow_version": "graph_v1",
                "graph_run_id": run.id,
                "dossier_path": response.dossier_path,
            }
            response = response.model_copy(update={"report_preview": report_preview})
        self._finish_run(run, status=status, output_json=response.model_dump(mode="json"))
        return response

    def make_node_handler(
        self,
        node_name: str,
        agent_name: str,
        node_fn: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> Callable[[ResearchGraphState], ResearchGraphState]:
        def _handler(state: ResearchGraphState) -> ResearchGraphState:
            if state.get("error"):
                return state

            step = RunStep(
                run_id=state["run_id"],
                step_name=node_name,
                agent_name=agent_name,
                status=StepStatus.RUNNING,
                started_at=_utc_now(),
                input_json=self._build_step_input(state),
            )
            self.session.add(step)
            self.session.commit()
            self.session.refresh(step)

            try:
                node_state = self._state_with_business_records(
                    state,
                    node_name=node_name,
                )
                tool_session = ToolSession(
                    node_name=node_name,
                    agent_name=agent_name,
                    state=dict(node_state),
                    harness=self.tool_harness,
                    executor=self.tool_executor,
                    db_session=self.session,
                )
                # ── Phase C: Capture state before node execution for IO snapshot ──
                state_before = dict(node_state)
                partial = node_fn(dict(node_state), tool_session=tool_session)
                tool_traces_delta = tool_session.export_traces()
                updated = dict(node_state)
                updated.update(partial)
                if tool_traces_delta:
                    updated["tool_traces"] = [
                        *node_state.get("tool_traces", []),
                        *tool_traces_delta,
                    ]
                self._persist_business_state(updated)
                updated["claim_support_matrix"] = (
                    self.business_repository.build_claim_support_matrix(
                        int(updated["run_id"])
                    )
                )
                if node_name == "chief_gate":
                    partial["claim_support_matrix"] = updated["claim_support_matrix"]
            except Exception as exc:
                self.session.rollback()
                step.status = StepStatus.FAILED
                step.error_message = str(exc)
                step.finished_at = _utc_now()
                self.session.add(step)
                self.session.commit()
                failure_step = {
                    "node_name": node_name,
                    "agent_name": agent_name,
                    "status": StepStatus.FAILED.value,
                    "output_summary": {
                        "error": str(exc),
                        "tool_traces": (
                            tool_session.export_traces()
                            if "tool_session" in locals()
                            else []
                        ),
                    },
                }
                failed_payload = dict(state)
                failed_payload["current_node"] = node_name
                failed_payload["node_steps"] = [*state.get("node_steps", []), failure_step]
                if "tool_session" in locals() and tool_session.export_traces():
                    failed_payload["tool_traces"] = [
                        *state.get("tool_traces", []),
                        *tool_session.export_traces(),
                    ]
                failed_payload["error"] = {"node_name": node_name, "message": str(exc)}
                failed_payload["decision"] = "FAILED"
                failed_state = ResearchGraphState(**failed_payload)
                self._save_checkpoint(failed_state)
                return failed_state

            step.status = StepStatus.SUCCEEDED
            step.finished_at = _utc_now()
            context_pack = build_context_pack_summary(
                node_name=node_name,
                agent_name=agent_name,
                state=updated,
                state_before=state_before,
                state_after=updated,
            )
            updated["context_packs"] = [*state.get("context_packs", []), context_pack]
            step.output_json = self._build_step_output(
                partial,
                context_pack,
                tool_traces=tool_traces_delta,
            )
            self.session.add(step)
            self.session.commit()

            node_step = {
                "node_name": node_name,
                "agent_name": agent_name,
                "status": StepStatus.SUCCEEDED.value,
                "output_summary": step.output_json or {},
            }
            updated["current_node"] = node_name
            updated["node_steps"] = [*state.get("node_steps", []), node_step]
            self._save_checkpoint(updated)
            return ResearchGraphState(**updated)

        return _handler

    def route_after_chief_gate(self, state: ResearchGraphState) -> str:
        return str(state.get("decision") or "FAILED")

    def _create_run(self, *, request: GraphAnalyzeRequest, task_job_id: int | None) -> Run:
        run = Run(
            run_type=RunType.RESEARCH,
            status=RunStatus.RUNNING,
            started_at=_utc_now(),
            input_json={
                "pipeline": "langgraph_research_harness_v1",
                "query": request.query,
                "max_rounds": request.max_rounds,
                "max_loop_count": request.max_loop_count,
                "execution_mode": request.execution_mode,
                "strategy": _strategy_from_execution_mode(request.execution_mode),
                "task_job_id": task_job_id,
            },
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        input_json = dict(run.input_json or {})
        input_json["thread_id"] = f"research_run:{run.id}"
        run.input_json = input_json
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def _get_existing_run(self, run_id: int) -> Run | None:
        return self.session.get(Run, run_id)

    def _finish_run(self, run: Run, *, status: RunStatus, output_json: dict[str, Any]) -> None:
        cleanup_summary = self._cleanup_graph_runtime_documents_if_terminal(
            run=run,
            output_json=output_json,
        )
        if cleanup_summary is not None:
            output_json = dict(output_json)
            output_json["graph_runtime_cleanup"] = cleanup_summary
        run.status = status
        run.finished_at = _utc_now()
        run.output_json = output_json
        self.session.add(run)
        self.session.commit()

    def _build_step_input(self, state: ResearchGraphState) -> dict[str, Any]:
        return {
            "thread_id": state["thread_id"],
            "strategy": state.get("strategy"),
            "loop_count": state.get("loop_count", 0),
            "decision": state.get("decision"),
            "source_count": len(state.get("sources", [])),
            "evidence_count": len(state.get("evidence", [])),
            "claim_count": len(state.get("claims", [])),
            "claim_support_matrix_count": len(state.get("claim_support_matrix", [])),
            "claim_verification_count": len(state.get("claim_verifications", [])),
            "issue_count": len(state.get("review_issues", [])),
            "tool_trace_count": len(state.get("tool_traces", [])),
        }

    def _build_step_output(
        self,
        partial: dict[str, Any],
        context_pack: dict[str, Any] | None = None,
        tool_traces: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        output: dict[str, Any] = {}
        if "plan" in partial:
            output["plan_summary"] = {
                "research_dimension_count": len(
                    partial["plan"].get("research_dimensions", [])
                ),
                "dimension_plan_count": len(partial["plan"].get("dimension_plan", [])),
                "dimension_types": [
                    item.get("dimension_type")
                    for item in partial["plan"].get("dimension_plan", [])
                    if item.get("dimension_type")
                ],
                "search_round_count": len(partial["plan"].get("search_rounds", [])),
                "source_obligation_count": len(partial["plan"].get("source_obligations", [])),
            }
        if "planner_metadata" in partial:
            output["planner_metadata"] = partial["planner_metadata"]
        if "sources" in partial:
            output["source_count"] = len(partial["sources"])
            output["source_ids"] = [item.get("source_id") for item in partial["sources"]]
        if "source_chunks" in partial:
            output["source_chunk_count"] = len(partial["source_chunks"])
        if "retrieval_pack" in partial:
            output["retrieval_pack_summary"] = {
                "retrieval_mode": partial["retrieval_pack"].get("retrieval_mode"),
                "total_candidates": partial["retrieval_pack"].get("total_candidates"),
                "returned_count": partial["retrieval_pack"].get("returned_count"),
                "adapter_status": partial["retrieval_pack"].get("adapter_status"),
                "backend_retrieval_mode": partial["retrieval_pack"].get(
                    "backend_retrieval_mode"
                ),
            }
        if "search_events" in partial:
            output["search_events"] = partial["search_events"]
        if "evidence" in partial:
            output["evidence_count"] = len(partial["evidence"])
            output["support_types"] = [item.get("support_type") for item in partial["evidence"]]
        if "claims" in partial:
            output["claim_count"] = len(partial["claims"])
            output["supported_claim_count"] = sum(
                1 for item in partial["claims"] if item.get("supported")
            )
        if "claim_support_matrix" in partial:
            output["claim_support_matrix_count"] = len(partial["claim_support_matrix"])
        if "claim_verifications" in partial:
            output["claim_verification_count"] = len(partial["claim_verifications"])
            output["unsupported_claims"] = [
                item.get("claim_id")
                for item in partial["claim_verifications"]
                if item.get("support_status") == "unsupported"
            ]
        if "drafts" in partial:
            output["draft_version"] = partial["drafts"][-1]["draft_version"]
        if "review_issues" in partial:
            output["issue_count"] = len(partial["review_issues"])
            output["issue_types"] = [item.get("issue_type") for item in partial["review_issues"]]
        if "quality_scores" in partial:
            output["quality_scores"] = partial["quality_scores"]
        if "dimension_coverage" in partial:
            output["dimension_coverage"] = partial["dimension_coverage"]
        if "decision" in partial:
            output["decision"] = partial["decision"]
            output["loop_count"] = partial.get("loop_count")
        if "required_actions" in partial:
            output["required_actions"] = partial["required_actions"]
        if "required_obligation_coverage" in partial:
            output["required_obligation_coverage"] = partial[
                "required_obligation_coverage"
            ]
        if "planner_replan_request" in partial:
            output["planner_replan_request"] = partial["planner_replan_request"]
        if "gate_reason" in partial:
            output["gate_reason"] = partial["gate_reason"]
        if "gate_route_to" in partial:
            output["gate_route_to"] = partial["gate_route_to"]
        if "contract_meta" in partial:
            output["contract_meta"] = partial["contract_meta"]
        if "human_review" in partial:
            output["human_review"] = partial["human_review"]
        if tool_traces:
            output["tool_traces"] = tool_traces
        if "final_report" in partial:
            output["report_preview"] = partial["final_report"]
        if context_pack is not None:
            output["context_pack_summary"] = context_pack
        if not output:
            output["updated_keys"] = sorted(partial.keys())
        return output

    def _write_dossier(
        self,
        *,
        query: str,
        response_json: dict[str, Any],
        final_state: ResearchGraphState,
    ) -> str | None:
        try:
            path = write_graph_research_dossier(
                run_id=int(final_state["run_id"]),
                query=query,
                response_json=response_json,
                context={
                    "node_steps": final_state.get("node_steps", []),
                    "context_packs": final_state.get("context_packs", []),
                    "plan": final_state.get("plan", {}),
                    "planner_metadata": final_state.get("planner_metadata", {}),
                    "summary_memory": final_state.get("summary_memory", {}),
                    "search_events": final_state.get("search_events", []),
                    "source_chunks": final_state.get("source_chunks", []),
                    "retrieval_pack": final_state.get("retrieval_pack", {}),
                    "sources": final_state.get("sources", []),
                    "evidence": final_state.get("evidence", []),
                    "claims": final_state.get("claims", []),
                    "tool_traces": final_state.get("tool_traces", []),
                    "claim_support_matrix": final_state.get("claim_support_matrix", []),
                    "claim_verifications": final_state.get("claim_verifications", []),
                    "review_issues": final_state.get("review_issues", []),
                    "human_review": final_state.get("human_review"),
                    "quality_scores": final_state.get("quality_scores", {}),
                    "decision": final_state.get("decision"),
                    "final_report": final_state.get("final_report", {}),
                },
            )
        except Exception:
            return None
        return str(path)

    def _save_report_artifact(
        self,
        *,
        run: Run,
        query: str,
        final_state: ResearchGraphState,
        dossier_path: str | None,
        status: RunStatus,
    ) -> int | None:
        if status != RunStatus.SUCCEEDED:
            return None
        final_report = dict(final_state.get("final_report") or {})
        if not final_report:
            return None
        existing_report_id = _existing_report_id(run.output_json)
        if existing_report_id is not None:
            if dossier_path:
                ResearchReportService(self.session).update_dossier_path(
                    existing_report_id,
                    dossier_path,
                )
            return existing_report_id
        report_json = self._build_report_artifact_json(
            final_state=final_state,
            final_report=final_report,
            dossier_path=dossier_path,
        )
        saved = ResearchReportService(self.session).save(
            ResearchReportCreate(
                query=query,
                report_json=report_json,
                source_count=len(final_state.get("sources", [])),
                evidence_count=len(final_state.get("evidence", [])),
                overall_confidence=_confidence_from_quality_scores(
                    final_state.get("quality_scores", {})
                ),
                search_rounds=len(final_state.get("search_events", [])),
                tavily_credits=_estimated_tavily_credits(final_state),
                dossier_path=dossier_path,
            )
        )
        return saved.id

    def _build_report_artifact_json(
        self,
        *,
        final_state: ResearchGraphState,
        final_report: dict[str, Any],
        dossier_path: str | None,
    ) -> dict[str, Any]:
        quality_scores = dict(final_state.get("quality_scores", {}))
        claims = list(final_state.get("claims", []))
        evidence = list(final_state.get("evidence", []))
        sources = list(final_state.get("sources", []))
        support_matrix = list(final_state.get("claim_support_matrix", []))
        return {
            **final_report,
            "workflow_version": "graph_v1",
            "graph_run_id": int(final_state["run_id"]),
            "thread_id": str(final_state["thread_id"]),
            "task_job_id": final_state.get("task_job_id"),
            "dossier_path": dossier_path,
            "executive_summary": final_report.get("executive_summary", ""),
            "key_claims": [
                {
                    "claim_id": claim.get("claim_id"),
                    "text": claim.get("text"),
                    "supported": claim.get("supported"),
                    "evidence_ids": claim.get("evidence_ids", []),
                    "required_source_family": claim.get("required_source_family"),
                    "support_requirement": claim.get("support_requirement"),
                }
                for claim in claims
            ],
            "evidence_table": [
                {
                    "evidence_id": item.get("evidence_id"),
                    "source_id": item.get("source_id"),
                    "support_type": item.get("support_type"),
                    "support_strength": item.get("support_strength"),
                    "specificity": item.get("specificity"),
                    "summary": item.get("summary"),
                    "limitations": item.get("limitations", []),
                }
                for item in evidence
            ],
            "limitations": _dedupe_report_limitations(final_state),
            "source_quality_summary": {
                "source_count": len(sources),
                "source_tiers": _count_values(
                    source.get("source_tier")
                    or source.get("source_quality_v2", {}).get("tier")
                    for source in sources
                ),
                "source_families": _count_values(
                    source.get("source_family") for source in sources
                ),
                "usage_roles": _count_values(
                    source.get("source_quality_v2", {}).get("usage_role")
                    for source in sources
                ),
            },
            "claim_support_matrix": support_matrix,
            "quality_scores": quality_scores,
            "cost_latency_diagnostics": {
                "search_event_count": len(final_state.get("search_events", [])),
                "estimated_tavily_credits": _estimated_tavily_credits(final_state),
                "node_step_count": len(final_state.get("node_steps", [])),
                "context_pack_count": len(final_state.get("context_packs", [])),
            },
            "compliance_statement": (
                "This graph_v1 report is industry intelligence and research "
                "assistance. It is not direct securities investment advice."
            ),
        }

    def _finalize_evaluation(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run-close the evaluation store for whatever way the run ended.

        Fail-open: a finalize error must not change the run's outcome.
        """
        store_data = state.get("evaluation_store")
        if not isinstance(store_data, dict):
            return state
        try:
            store = RunEvaluationStore.from_dict(store_data)
            reason = self._termination_reason(state)
            finalize_evaluation_run(store, termination_reason=reason)
            state["evaluation_store"] = store.to_dict()
            state["evaluation_termination_reason"] = reason
        except Exception as exc:  # noqa: BLE001 - fail-open, never blocks the run
            state.setdefault("evaluation_persistence_status", "degraded")
            state["evaluation_persistence_diagnostic"] = (
                f"finalize_eval_error:{type(exc).__name__}"
            )
        return state

    def _termination_reason(self, state: dict[str, Any]) -> str:
        if state.get("error"):
            return "GRAPH_ERROR"
        human = state.get("human_review")
        if isinstance(human, dict) and bool(human.get("pending", False)):
            return "HUMAN_REVIEW"
        decision = state.get("decision")
        if decision == "PASS":
            return "REPORT_COMPLETED"
        if decision == "FAILED":
            return "GRAPH_ERROR"
        if bool(state.get("budget_exhausted")):
            return "BUDGET_EXHAUSTED"
        if state.get("final_report"):
            return "REPORT_COMPLETED"
        return "GRAPH_ERROR"

    def _resume_from_checkpoint(self, state: ResearchGraphState) -> ResearchGraphState:
        # Re-open `suspended` SearchTasks (left by a HUMAN_REVIEW pause) so the
        # resumed run can continue executing them instead of keeping them frozen.
        store_data = state.get("evaluation_store")
        if isinstance(store_data, dict):
            try:
                resume_store = RunEvaluationStore.from_dict(store_data)
                resume_suspended_tasks(resume_store)
                state["evaluation_store"] = resume_store.to_dict()
            except Exception:  # noqa: BLE001 - fail-open
                pass
        runtime_nodes = self._runtime_nodes()
        current_state = state
        next_node = self._next_node_after(
            current_node=current_state.get("current_node"),
            state=current_state,
        )
        while next_node is not None:
            if current_state.get("error") and current_state.get("current_node") == next_node:
                retry_state = dict(current_state)
                retry_state["error"] = None
                retry_state["decision"] = None
                current_state = ResearchGraphState(**retry_state)
            current_state = runtime_nodes[next_node](current_state)
            if current_state.get("error"):
                break
            next_node = self._next_node_after(
                current_node=current_state.get("current_node"),
                state=current_state,
            )
        return current_state

    def _save_checkpoint(self, state: ResearchGraphState) -> str | None:
        try:
            return self.checkpoint_repository.save(
                run_id=int(state["run_id"]),
                thread_id=str(state["thread_id"]),
                current_node=state.get("current_node"),
                state=dict(state),
            )
        except Exception:
            return None

    def _persist_business_state(self, state: dict[str, Any]) -> None:
        self.business_repository.persist_state(state)

    def _state_with_business_records(
        self,
        state: ResearchGraphState,
        *,
        node_name: str,
    ) -> ResearchGraphState:
        if node_name not in {
            "chief_gate",
            "finalize_report",
        }:
            return state
        enriched = dict(state)
        enriched["claim_support_matrix"] = (
            self.business_repository.build_claim_support_matrix(int(state["run_id"]))
        )
        return ResearchGraphState(**enriched)

    def _load_resume_state(
        self,
        *,
        run: Run,
        request: GraphAnalyzeRequest,
    ) -> ResearchGraphState:
        checkpoint = self.checkpoint_repository.load(run_id=run.id)
        if checkpoint is None:
            raise ValueError(f"No checkpoint found for run {run.id}.")
        payload_state = checkpoint.get("state") or {}
        payload_state["query"] = request.query
        payload_state["max_rounds"] = request.max_rounds
        payload_state["max_loop_count"] = request.max_loop_count
        if "execution_mode" in request.model_fields_set:
            payload_state["strategy"] = _strategy_from_execution_mode(request.execution_mode)
        if request.human_review_action is not None:
            payload_state = _apply_human_review_action(
                payload_state,
                action=request.human_review_action,
                notes=request.human_review_notes,
            )
        return ResearchGraphState(**payload_state)

    def _checkpoint_history_views(self, run_id: int) -> list[GraphCheckpointView]:
        return [
            GraphCheckpointView(
                run_id=item["run_id"],
                checkpoint_version=item.get("checkpoint_version"),
                thread_id=item["thread_id"],
                current_node=item.get("current_node"),
                saved_at=item.get("saved_at"),
            )
            for item in self.checkpoint_repository.history(run_id=run_id)
        ]

    def _cleanup_graph_runtime_documents_if_terminal(
        self,
        *,
        run: Run,
        output_json: dict[str, Any],
    ) -> dict[str, Any] | None:
        human_review = output_json.get("human_review")
        if isinstance(human_review, dict) and human_review.get("pending", False):
            return None
        try:
            cleanup_summary = cleanup_graph_runtime_documents(
                session=self.session,
                run_id=int(run.id),
            )
        except Exception:
            self.session.rollback()
            return {
                "cleanup_scope": "graph_run_scoped_documents",
                "retention_policy": "delete_on_terminal_run",
                "status": "cleanup_failed",
            }
        cleanup_summary["status"] = "cleaned"
        return cleanup_summary

    def _runtime_nodes(self) -> dict[str, Callable[[ResearchGraphState], ResearchGraphState]]:
        return {
            "plan_task": self.make_node_handler("plan_task", "Planner", plan_task),
            "collect_sources": self.make_node_handler(
                "collect_sources", "Source Hunter", collect_sources
            ),
            "parse_sources": self.make_node_handler(
                "parse_sources", "Parser/Structurer", parse_sources
            ),
            "score_sources": self.make_node_handler(
                "score_sources", "Source Quality v2", score_sources
            ),
            "build_evidence": self.make_node_handler(
                "build_evidence", "Evidence Builder", build_evidence
            ),
            "advisory_gap_backfill": self.make_node_handler(
                "advisory_gap_backfill", "Advisory Gap Backfill", advisory_gap_backfill
            ),
            "structured_shadow_editor1": self.make_node_handler(
                "structured_shadow_editor1", "Structured Shadow Editor1",
                structured_shadow_editor1,
            ),
            "editor1_draft": self.make_node_handler(
                "editor1_draft", "Editor1", editor1_draft
            ),
            "editor2_review": self.make_node_handler(
                "editor2_review", "Editor2", editor2_review
            ),
            "chief_gate": self.make_node_handler(
                "chief_gate", "Chief Gate", chief_gate
            ),
            "human_review": self.make_node_handler(
                "human_review", "Human Review", human_review
            ),
            "finalize_report": self.make_node_handler(
                "finalize_report", "Supervisor", finalize_report
            ),
        }

    def _next_node_after(
        self,
        *,
        current_node: str | None,
        state: ResearchGraphState,
    ) -> str | None:
        if current_node is None:
            return "plan_task"
        if state.get("error"):
            return current_node

        sequential = {
            "plan_task": "collect_sources",
            "collect_sources": "parse_sources",
            "parse_sources": "score_sources",
            "score_sources": "build_evidence",
            "build_evidence": "advisory_gap_backfill",
            "advisory_gap_backfill": "structured_shadow_editor1",
            "structured_shadow_editor1": "editor1_draft",
            "editor1_draft": "editor2_review",
            "editor2_review": "chief_gate",
            "finalize_report": None,
        }
        if current_node == "chief_gate":
            decision = state.get("decision")
            if decision == "PASS":
                return "finalize_report"
            if decision == "ADD_EVIDENCE":
                return "plan_task"
            if decision == "REVISE_TEXT":
                return "editor1_draft"
            if decision == "REVIEW_RISK":
                return "editor2_review"
            if decision == "HUMAN_REVIEW":
                return "human_review"
            return "finalize_report"
        if current_node == "human_review":
            human_review = dict(state.get("human_review") or {})
            if human_review.get("pending", False):
                return None
            selected_action = human_review.get("selected_action")
            if selected_action == "approve":
                return "finalize_report"
            if selected_action == "add_evidence":
                return "plan_task"
            if selected_action == "rewrite":
                return "editor1_draft"
            return None
        return sequential.get(current_node)


def _utc_now() -> datetime:
    try:
        return datetime.now(datetime.UTC)
    except AttributeError:  # pragma: no cover - Python < 3.11 fallback
        return datetime.now(timezone.utc)  # noqa: UP017 - Python < 3.11 fallback


def _strategy_from_execution_mode(execution_mode: str) -> str:
    if execution_mode == "provider_backed":
        return "provider_backed_v1"
    return "shadow_langgraph_v1"


def _existing_report_id(output_json: Any) -> int | None:
    if not isinstance(output_json, dict):
        return None
    report_preview = output_json.get("report_preview")
    if not isinstance(report_preview, dict):
        return None
    report_id = report_preview.get("report_id")
    try:
        value = int(report_id)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _confidence_from_quality_scores(quality_scores: dict[str, Any]) -> str:
    try:
        final_score = float(quality_scores.get("final_score", 0.0))
    except (TypeError, ValueError):
        final_score = 0.0
    if final_score >= 0.82:
        return "high"
    if final_score >= 0.55:
        return "medium"
    return "low"


def _estimated_tavily_credits(state: ResearchGraphState) -> int:
    total = 0
    for event in state.get("search_events", []):
        try:
            total += int(event.get("estimated_credits", 0) or 0)
        except (TypeError, ValueError):
            continue
    return total


def _count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "").strip()
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def _dedupe_report_limitations(state: ResearchGraphState) -> list[str]:
    limitations: list[str] = []
    for item in state.get("evidence", []):
        limitations.extend(str(value) for value in item.get("limitations", []) if value)
    for verification in state.get("claim_verifications", []):
        limitations.extend(str(value) for value in verification.get("notes", []) if value)
    for issue in state.get("review_issues", []):
        description = issue.get("description")
        if description:
            limitations.append(str(description))
    seen: set[str] = set()
    output: list[str] = []
    for limitation in limitations:
        normalized = limitation.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output[:20]


def _human_review_response(state: ResearchGraphState) -> GraphHumanReviewState | None:
    payload = state.get("human_review")
    if not isinstance(payload, dict):
        return None
    return GraphHumanReviewState.model_validate(payload)


def _apply_human_review_action(
    state: dict[str, Any],
    *,
    action: str,
    notes: str | None,
) -> dict[str, Any]:
    payload = dict(state)
    existing = dict(payload.get("human_review") or {})
    if not existing or not bool(existing.get("pending", False)):
        return payload

    status_map = {
        "approve": "approved",
        "add_evidence": "add_evidence_requested",
        "rewrite": "rewrite_requested",
        "reject": "rejected",
        "override_p0": "overridden",
    }
    decision_map = {
        "approve": "PASS",
        "add_evidence": "ADD_EVIDENCE",
        "rewrite": "REVISE_TEXT",
        "reject": "FAILED",
        "override_p0": "PASS",
    }
    existing.update(
        {
            "pending": False,
            "status": status_map[action],
            "selected_action": action,
            "notes": notes,
        }
    )
    if action == "override_p0":
        blocking_issues = existing.get("blocking_issues", [])
        for issue in blocking_issues:
            if isinstance(issue, dict):
                issue["overridden_by_human"] = True
        existing["blocking_issues"] = blocking_issues
    payload["human_review"] = existing
    payload["decision"] = decision_map[action]
    payload["gate_route_to"] = None
    if action == "reject":
        payload["required_actions"] = []
        payload["planner_replan_request"] = None
    return payload
