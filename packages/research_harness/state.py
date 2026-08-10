from __future__ import annotations

from typing import Any, TypedDict


class ResearchGraphState(TypedDict, total=False):
    run_id: int
    task_job_id: int | None
    thread_id: str
    query: str
    strategy: str
    max_rounds: int
    max_loop_count: int
    loop_count: int
    current_node: str | None
    node_steps: list[dict[str, Any]]
    context_packs: list[dict[str, Any]]
    tool_traces: list[dict[str, Any]]
    plan: dict[str, Any]
    planner_metadata: dict[str, Any]
    spec_first_pass_min_search_rounds: int
    summary_memory: dict[str, Any]
    query_requirements: dict[str, Any]
    sources: list[dict[str, Any]]
    search_events: list[dict[str, Any]]
    source_chunks: list[dict[str, Any]]
    retrieval_pack: dict[str, Any]
    evidence: list[dict[str, Any]]
    evidence_gap_report: dict[str, Any]
    claims: list[dict[str, Any]]
    claim_support_matrix: list[dict[str, Any]]
    claim_verifications: list[dict[str, Any]]
    drafts: list[dict[str, Any]]
    review_issues: list[dict[str, Any]]
    editor2_route_recommendation: dict[str, Any]
    verifier_route_recommendation: dict[str, Any]
    quality_scores: dict[str, float]
    decision: str | None
    required_actions: list[dict[str, Any]]
    required_obligation_coverage: list[dict[str, Any]]
    planner_replan_request: dict[str, Any] | None
    gate_reason: str | None
    gate_route_to: str | None
    contract_meta: dict[str, Any]
    final_report: dict[str, Any]
    human_review: dict[str, Any] | None
    error: dict[str, Any] | None
    # Phase B.2 — evaluation persistence store + status (LangGraph-carried).
    evaluation_store: dict[str, Any]
    evaluation_persistence_status: str
    # Phase B.3.3b — advisory gap backfill (shadow only, never mutates main
    # sources/evidence/claims/coverage/report). Flag-gated; default off.
    advisory_backfill: dict[str, Any]
    advisory_backfill_status: str
    advisory_backfill_diagnostics: list[dict[str, Any]]
    # B.3.3b — why the evaluation run was finalized (REPORT_COMPLETED /
    # HUMAN_REVIEW / BUDGET_EXHAUSTED / PROVIDER_FAILED / GRAPH_ERROR /
    # USER_CANCELLED). Set by the runner's central finalize_evaluation_run.
    evaluation_termination_reason: str
    # C.2 — claim-constrained StructuredDraft shadow namespace (flag-gated,
    # fail-open, reads only the main evaluation store). Never touches
    # drafts/report_markdown/final_report/claims/evidence/coverage_report.
    structured_draft_shadow: dict[str, Any]


def build_initial_state(
    *,
    run_id: int,
    task_job_id: int | None,
    query: str,
    max_rounds: int,
    max_loop_count: int,
    strategy: str = "shadow_langgraph_v1",
) -> ResearchGraphState:
    return ResearchGraphState(
        run_id=run_id,
        task_job_id=task_job_id,
        thread_id=f"research_run:{run_id}",
        query=query,
        strategy=strategy,
        max_rounds=max_rounds,
        max_loop_count=max_loop_count,
        loop_count=0,
        current_node=None,
        node_steps=[],
        context_packs=[],
        tool_traces=[],
        plan={},
        planner_metadata={},
        summary_memory={},
        query_requirements={},
        sources=[],
        search_events=[],
        source_chunks=[],
        retrieval_pack={},
        evidence=[],
        claims=[],
        claim_support_matrix=[],
        claim_verifications=[],
        drafts=[],
        review_issues=[],
        editor2_route_recommendation={},
        verifier_route_recommendation={},
        quality_scores={},
        decision=None,
        required_actions=[],
        required_obligation_coverage=[],
        planner_replan_request=None,
        gate_reason=None,
        gate_route_to=None,
        contract_meta={},
        final_report={},
        human_review=None,
        error=None,
    )
