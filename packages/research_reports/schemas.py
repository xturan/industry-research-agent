from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResearchReportCreate(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    report_json: dict[str, Any]
    dossier_path: str | None = None
    source_count: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    overall_confidence: str = Field(default="medium")
    search_rounds: int = Field(default=0, ge=0)
    tavily_credits: int = Field(default=0, ge=0)


class ResearchReportSummary(BaseModel):
    id: int
    query: str
    dossier_path: str | None = None
    source_count: int
    evidence_count: int
    overall_confidence: str
    search_rounds: int
    tavily_credits: int
    created_at: datetime


class ResearchReportView(BaseModel):
    id: int
    query: str
    report_json: dict[str, Any]
    dossier_path: str | None = None
    source_count: int
    evidence_count: int
    overall_confidence: str
    search_rounds: int
    tavily_credits: int
    created_at: datetime
