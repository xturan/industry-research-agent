from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolKind(str, Enum):
    READ_ONLY = "read_only"
    REVIEW_ACTION = "review_action"
    REPORT_COMPOSE = "report_compose"
    FORBIDDEN = "forbidden"


class GetEvidenceBundleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_ids: list[str] = Field(default_factory=list, max_length=20)


class GetClaimSupportMatrixInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_ids: list[str] = Field(default_factory=list, max_length=20)


class GetSourceBundleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ids: list[str] = Field(default_factory=list, max_length=30)
    source_families: list[str] = Field(default_factory=list, max_length=10)


class RequestReplanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus_claim_ids: list[str] = Field(default_factory=list, max_length=20)
    note: str = Field(default="", max_length=500)


class RequestRevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_claim_ids: list[str] = Field(default_factory=list, max_length=20)
    note: str = Field(default="", max_length=500)


class ComposeSectionOutlineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_ids: list[str] = Field(default_factory=list, max_length=20)


class ComposeFinalReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_ids: list[str] = Field(default_factory=list, max_length=20)


class GenericToolOutput(BaseModel):
    model_config = ConfigDict(extra="allow")


class ToolTraceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    node_name: str
    agent_name: str
    tool_name: str
    tool_kind: str
    call_index: int
    status: str
    reason_code: str
    message: str = ""
    args_summary: dict[str, Any] = Field(default_factory=dict)
    result_summary: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    tool_name: str
    kind: ToolKind
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    side_effect_level: str
    required_scopes: tuple[str, ...]


TOOL_SPECS: dict[str, ToolSpec] = {
    "get_evidence_bundle": ToolSpec(
        tool_name="get_evidence_bundle",
        kind=ToolKind.READ_ONLY,
        description="Return structured evidence items linked to selected claims.",
        input_model=GetEvidenceBundleInput,
        output_model=GenericToolOutput,
        side_effect_level="none",
        required_scopes=("claims", "evidence", "sources"),
    ),
    "get_claim_support_matrix": ToolSpec(
        tool_name="get_claim_support_matrix",
        kind=ToolKind.READ_ONLY,
        description="Return structured claim support matrix rows for review and gate analysis.",
        input_model=GetClaimSupportMatrixInput,
        output_model=GenericToolOutput,
        side_effect_level="none",
        required_scopes=("claims", "claim_support_matrix", "claim_verifications"),
    ),
    "get_source_bundle": ToolSpec(
        tool_name="get_source_bundle",
        kind=ToolKind.READ_ONLY,
        description="Return structured source metadata and source-quality summaries.",
        input_model=GetSourceBundleInput,
        output_model=GenericToolOutput,
        side_effect_level="none",
        required_scopes=("sources",),
    ),
    "request_replan": ToolSpec(
        tool_name="request_replan",
        kind=ToolKind.REVIEW_ACTION,
        description="Return a structured replanning proposal without mutating graph state.",
        input_model=RequestReplanInput,
        output_model=GenericToolOutput,
        side_effect_level="graph_state_only",
        required_scopes=("claims", "review_issues", "claim_verifications", "query_requirements"),
    ),
    "request_revision": ToolSpec(
        tool_name="request_revision",
        kind=ToolKind.REVIEW_ACTION,
        description="Return a structured revision request for draft rewriting.",
        input_model=RequestRevisionInput,
        output_model=GenericToolOutput,
        side_effect_level="graph_state_only",
        required_scopes=("claims", "drafts", "review_issues"),
    ),
    "compose_section_outline": ToolSpec(
        tool_name="compose_section_outline",
        kind=ToolKind.REPORT_COMPOSE,
        description="Return a deterministic report section scaffold from current claims and evidence.",
        input_model=ComposeSectionOutlineInput,
        output_model=GenericToolOutput,
        side_effect_level="none",
        required_scopes=("claims", "evidence", "sources"),
    ),
    "compose_final_report": ToolSpec(
        tool_name="compose_final_report",
        kind=ToolKind.REPORT_COMPOSE,
        description="Return a deterministic final-report composition pack from graph state.",
        input_model=ComposeFinalReportInput,
        output_model=GenericToolOutput,
        side_effect_level="none",
        required_scopes=("claims", "evidence", "sources", "quality_scores", "review_issues"),
    ),
}


FORBIDDEN_TOOL_NAMES = {
    "write_database_record",
    "update_run_status",
    "arbitrary_network_fetch",
}
