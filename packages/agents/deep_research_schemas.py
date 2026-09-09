from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResearchDimension(BaseModel):
    """A single research dimension decomposed from the user query."""
    model_config = ConfigDict(extra="forbid")

    dimension_id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    caliber_terms: list[str] = Field(default_factory=list, max_length=12)
    source_priority: Literal["government", "enterprise", "media", "mixed"] = "mixed"


class QueryUnderstanding(BaseModel):
    """Phase 1 output: decomposed query with caliber-expanded dimensions."""
    model_config = ConfigDict(extra="forbid")

    normalized_query: str = Field(min_length=1, max_length=500)
    research_dimensions: list[ResearchDimension] = Field(min_length=1, max_length=8)
    caliber_notes: str = Field(default="", max_length=600)


class SearchRoundPlan(BaseModel):
    """A single search round in the multi-round plan."""
    model_config = ConfigDict(extra="forbid")

    round_number: int = Field(ge=1, le=10)
    objective: str = Field(min_length=1, max_length=300)
    search_phrases: list[str] = Field(min_length=1, max_length=8)
    include_domains: list[str] = Field(default_factory=list)
    target_dimensions: list[str] = Field(default_factory=list)
    expected_source_tier: Literal["A", "B", "C"] = "B"


class MultiRoundSearchPlan(BaseModel):
    """Phase 1+2: full multi-round search plan."""
    model_config = ConfigDict(extra="forbid")

    rounds: list[SearchRoundPlan] = Field(min_length=1, max_length=10)
    stop_conditions: list[str] = Field(default_factory=list)


class SourceAssessment(BaseModel):
    """Phase 3: single source evaluation."""
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2000)
    title: str = Field(default="", max_length=500)
    tier: Literal["A", "B", "C", "D"] = "C"
    authority_score: float = Field(default=0.0, ge=0.0, le=1.0)
    proximity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    timeliness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    verifiability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_usable: bool = True
    usage_note: str = Field(default="", max_length=500)


class EvidenceItem(BaseModel):
    """Phase 4: a single piece of evidence in the chain."""
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=60)
    claim: str = Field(min_length=1, max_length=500)
    source_urls: list[str] = Field(default_factory=list)
    stage: Literal[
        "policy_statement",
        "implementation_rule",
        "project_announcement",
        "demonstration",
        "order_or_contract",
        "production_line",
        "mass_production",
        "revenue_confirmed",
    ] = "policy_statement"
    confidence: Literal["high", "medium", "low"] = "medium"
    counter_evidence: str = Field(default="", max_length=500)
    verification_status: Literal["verified", "partially_verified", "unverified"] = "unverified"


class DeepResearchReport(BaseModel):
    """Phase 5: final assembled research report."""
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    executive_summary: str = Field(min_length=1, max_length=3000)
    overall_confidence: Literal["high", "medium", "low"] = "medium"
    key_findings: list[str] = Field(default_factory=list, max_length=12)
    key_inferences: list[str] = Field(default_factory=list, max_length=12)
    evidence_chain: list[EvidenceItem] = Field(default_factory=list)
    source_assessments: list[SourceAssessment] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list, max_length=20)
    suggested_followups: list[str] = Field(default_factory=list, max_length=8)
    search_rounds_executed: int = Field(default=0, ge=0, le=20)
    estimated_tavily_credits: int = Field(default=0, ge=0)
