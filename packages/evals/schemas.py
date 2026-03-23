from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.db.models import EvalStatus, EvalType


class EvalCaseResult(BaseModel):
    case_name: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    detail_json: dict[str, Any] = Field(default_factory=dict)


class EvalSummary(BaseModel):
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    issue_count: int = Field(ge=0)
    issues: list[str] = Field(default_factory=list)
    case_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)


class EvalRunView(BaseModel):
    id: int
    eval_type: EvalType
    target_type: str
    target_ref: str | None
    status: EvalStatus
    score: float | None
    summary_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    items: list[EvalCaseResult]


class SmokeEvalRequest(BaseModel):
    query: str = Field(default="lithium pricing outlook", min_length=1, max_length=400)
    top_k: int = Field(default=6, ge=1, le=20)
    bootstrap_sample: bool = True
    research_mode: str = "mock"
    content_mode: str = "mock"


class SmokeEvalResponse(BaseModel):
    eval_run_id: int
    status: EvalStatus
    summary: EvalSummary
