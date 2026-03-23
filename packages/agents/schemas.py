from __future__ import annotations

from datetime import datetime
from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 fallback

    class StrEnum(str, Enum):
        pass

from pydantic import BaseModel, Field, field_validator

from packages.db.models import DocumentStatus, SourceType
from packages.rag.schemas import RetrievalFilters


class ResearchMode(StrEnum):
    MOCK = "mock"
    LLM = "llm"


class ResearchProvider(StrEnum):
    MOCK = "mock"
    DEEPSEEK = "deepseek"


RESEARCH_MODEL_STEPS = (
    "supervisor_intake",
    "thesis_builder",
    "opponent",
    "evidence_judge",
    "risk_analyst",
    "synthesize_memo",
)


class ResearchAnalyzeRequest(BaseModel):
    query: str = Field(min_length=1, max_length=400)
    mode: ResearchMode = ResearchMode.MOCK
    provider: ResearchProvider | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)
    step_models: dict[str, str] | None = None
    enable_thinking: bool | None = None
    debug_reasoning: bool = False
    top_k: int = Field(default=8, ge=1, le=50)
    source_type: SourceType | None = None
    document_status: DocumentStatus | None = None
    industry: str | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    document_id: int | None = None
    theme_id: int | None = None

    @field_validator("step_models")
    @classmethod
    def validate_step_models(
        cls, value: dict[str, str] | None
    ) -> dict[str, str] | None:
        if value is None:
            return None
        normalized: dict[str, str] = {}
        allowed = set(RESEARCH_MODEL_STEPS)
        for step_name, model_name in value.items():
            step_key = step_name.strip()
            if step_key not in allowed:
                raise ValueError(
                    f"Unsupported step model key '{step_name}'. "
                    f"Allowed: {', '.join(RESEARCH_MODEL_STEPS)}"
                )
            model_value = model_name.strip()
            if not model_value:
                raise ValueError(f"Model override for step '{step_key}' cannot be empty.")
            if len(model_value) > 200:
                raise ValueError(
                    f"Model override for step '{step_key}' exceeds 200 characters."
                )
            normalized[step_key] = model_value
        return normalized

    def to_retrieval_filters(self) -> RetrievalFilters:
        return RetrievalFilters(
            source_type=self.source_type,
            document_status=self.document_status,
            industry=self.industry,
            published_from=self.published_from,
            published_to=self.published_to,
            document_id=self.document_id,
            theme_id=self.theme_id,
            limit=self.top_k,
        )


class SupervisorIntake(BaseModel):
    normalized_query: str
    focus_terms: list[str]
    planned_stages: list[str]
    note: str | None = None


class EvidenceReference(BaseModel):
    chunk_id: int
    document_id: int
    locator: str | None = None
    section_name: str | None = None
    score: float


class ThesisItem(BaseModel):
    thesis_id: str
    title: str
    stance: str
    summary: str
    confidence_score: float
    support_strength: float
    evidence_chunk_ids: list[int]
    evidence_refs: list[str]
    rationale: str


class ObjectionItem(BaseModel):
    thesis_id: str
    objection: str
    severity: int = Field(ge=1, le=5)
    evidence_chunk_ids: list[int]
    evidence_refs: list[str]
    rationale: str


class EvidenceCoverageItem(BaseModel):
    thesis_id: str
    support_score: float = Field(ge=0.0, le=1.0)
    support_label: str
    supporting_chunk_ids: list[int]
    gaps: list[str]
    notes: str


class EvidenceJudgeOutput(BaseModel):
    coverage: list[EvidenceCoverageItem]
    overall_sufficiency_score: float = Field(ge=0.0, le=1.0)
    overall_label: str
    global_gaps: list[str]


class RiskItem(BaseModel):
    thesis_id: str
    risk_title: str
    risk_description: str
    invalidation_condition: str
    severity: int = Field(ge=1, le=5)
    related_chunk_ids: list[int]


class FinalResearchMemo(BaseModel):
    query: str
    executive_summary: str
    key_theses: list[ThesisItem]
    counterarguments: list[ObjectionItem]
    evidence_gaps: list[str]
    major_risks: list[RiskItem]
    confidence_assessment: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    suggested_next_questions: list[str]


class EvidenceSummary(BaseModel):
    bundle_id: str
    retrieval_mode: str
    total_candidates: int
    selected_items: int
    sufficient: bool
    notes: list[str]
    top_documents: list[str]
    top_evidence: list[EvidenceReference]


class ResearchAnalysisResult(BaseModel):
    run_id: int
    query: str
    mode: ResearchMode
    provider: ResearchProvider
    model: str | None = None
    thinking_enabled: bool = False
    status: str
    evidence_summary: EvidenceSummary
    theses: list[ThesisItem]
    objections: list[ObjectionItem]
    evidence_judge: EvidenceJudgeOutput
    risks: list[RiskItem]
    final_memo: FinalResearchMemo
    confidence_score: float = Field(ge=0.0, le=1.0)
    insufficient_evidence: bool
    workflow_notes: list[str] = Field(default_factory=list)
    provider_metadata: dict[str, object] | None = None
    error_message: str | None = None


class ThesisBuilderOutput(BaseModel):
    theses: list[ThesisItem]


class OpponentOutput(BaseModel):
    objections: list[ObjectionItem]


class RiskAnalystOutput(BaseModel):
    risks: list[RiskItem]


class RunStepView(BaseModel):
    id: int
    step_name: str
    agent_name: str | None
    status: str
    input_json: dict[str, object] | None
    output_json: dict[str, object] | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None


class ResearchRunView(BaseModel):
    run_id: int
    run_type: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    input_json: dict[str, object] | None
    output_json: dict[str, object] | None
    steps: list[RunStepView]
