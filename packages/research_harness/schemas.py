from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GraphAnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500, description="Research query")
    max_rounds: int = Field(default=12, ge=1, le=12)
    # 2026-08-11：一次到位——基础搜索 + 未覆盖维度深度补搜后直接写报告，
    # 不经过 ADD_EVIDENCE 多轮循环。默认 max_loop_count=0（gate 只 PASS/标注）。
    max_loop_count: int = Field(default=0, ge=0, le=6)
    resume_run_id: int | None = Field(default=None, ge=1)
    human_review_action: Literal["approve", "add_evidence", "rewrite", "reject", "override_p0"] | None = None  # noqa: E501
    human_review_notes: str | None = Field(default=None, max_length=2_000)
    execution_mode: Literal["shadow", "provider_backed"] = Field(
        default="shadow",
        description=(
            "Graph harness execution mode. shadow keeps deterministic mock nodes; "
            "provider_backed opts into real search/source-quality backed early nodes."
        ),
    )


class GraphHumanReviewState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending: bool = False
    status: Literal[
        "pending",
        "approved",
        "add_evidence_requested",
        "rewrite_requested",
        "rejected",
        "overridden",
    ]
    gate_reason: str | None = None
    blocking_issues: list[dict[str, Any]] = Field(default_factory=list)
    required_actions: list[dict[str, Any]] = Field(default_factory=list)
    supported_actions: list[str] = Field(default_factory=list)
    draft_snapshot: dict[str, Any] = Field(default_factory=dict)
    report_snapshot: dict[str, Any] = Field(default_factory=dict)
    selected_action: Literal["approve", "add_evidence", "rewrite", "reject", "override_p0"] | None = None  # noqa: E501
    notes: str | None = None
    p0_review_context: dict[str, Any] | None = None


class GraphNodeStepSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_name: str
    agent_name: str
    status: Literal["succeeded", "failed", "skipped"]
    output_summary: dict[str, Any] = Field(default_factory=dict)


class GraphContextPackSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_pack_id: str
    node_name: str
    agent_name: str
    prompt_version: str
    input_hash: str
    included_source_ids: list[str] = Field(default_factory=list)
    included_evidence_ids: list[str] = Field(default_factory=list)
    included_claim_ids: list[str] = Field(default_factory=list)
    included_issue_ids: list[str] = Field(default_factory=list)
    included_fields: list[str] = Field(default_factory=list)
    context_budget_tokens: int | None = None
    tool_permissions: list[str] = Field(default_factory=list)
    fallback_usage_review: str | None = None
    live_validation_focus: list[str] = Field(default_factory=list)
    failure_class_focus: list[str] = Field(default_factory=list)
    token_estimate: int
    budget_status: Literal["within_budget", "over_budget", "unbudgeted"] = "unbudgeted"
    io_snapshot: dict[str, Any] | None = None
    budget_overage_tokens: int = Field(default=0, ge=0)
    sanitization_summary: dict[str, Any] = Field(default_factory=dict)


class GraphCheckpointView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: int
    checkpoint_version: int | None = None
    thread_id: str
    current_node: str | None = None
    saved_at: str | None = None


class GraphCheckpointCompactionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: int
    keep_latest: int
    deleted_count: int
    retained_count: int
    latest_checkpoint_version: int | None = None


class GraphRuntimeCleanupSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cleanup_scope: str
    retention_policy: str
    document_count: int = 0
    chunk_count: int = 0
    citation_count: int = 0
    status: Literal["cleaned", "skipped_pending_human_review", "cleanup_failed"] | None = None


class GraphRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: int
    thread_id: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    decision: Literal[
        "PASS",
        "ADD_EVIDENCE",
        "REVISE_TEXT",
        "REVIEW_RISK",
        "HUMAN_REVIEW",
        "FAILED",
    ] | None = None
    resumed_from_checkpoint: bool = False
    checkpoint_version: int | None = None
    checkpoint_saved_at: str | None = None
    dossier_path: str | None = None
    report_id: int | None = None
    gate_reason: str | None = None
    last_failed_node: str | None = None
    report_preview_summary: str | None = None
    created_at: str | None = None
    finished_at: str | None = None
    pending_human_review: bool = False
    task_refs: list[dict[str, Any]] = Field(default_factory=list)


class GraphAnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: int
    task_job_id: int | None = None
    thread_id: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    decision: Literal[
        "PASS",
        "ADD_EVIDENCE",
        "REVISE_TEXT",
        "REVIEW_RISK",
        "HUMAN_REVIEW",
        "FAILED",
    ] | None = None
    quality_scores: dict[str, float] = Field(default_factory=dict)
    node_steps: list[GraphNodeStepSummary] = Field(default_factory=list)
    context_packs: list[GraphContextPackSummary] = Field(default_factory=list)
    report_preview: dict[str, Any] = Field(default_factory=dict)
    human_review: GraphHumanReviewState | None = None
    dossier_path: str | None = None
    checkpoint_path: str | None = None
    resumed_from_checkpoint: bool = False
    checkpoint_history: list[GraphCheckpointView] = Field(default_factory=list)
    graph_runtime_cleanup: GraphRuntimeCleanupSummary | None = None
