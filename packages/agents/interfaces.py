from typing import Protocol

from packages.agents.schemas import (
    EvidenceJudgeOutput,
    FinalResearchMemo,
    ObjectionItem,
    ResearchAnalyzeRequest,
    RiskItem,
    SupervisorIntake,
    ThesisItem,
)
from packages.rag.schemas import EvidenceBundle


class SupervisorAgentContract(Protocol):
    name: str

    def intake(self, request: ResearchAnalyzeRequest, bundle: EvidenceBundle) -> SupervisorIntake:
        """Normalize request and create deterministic workflow focus points."""

    def synthesize_memo(
        self,
        *,
        query: str,
        theses: list[ThesisItem],
        objections: list[ObjectionItem],
        evidence_judge: EvidenceJudgeOutput,
        risks: list[RiskItem],
        insufficient_evidence: bool,
    ) -> FinalResearchMemo:
        """Assemble the final structured, auditable memo."""


class ThesisBuilderAgentContract(Protocol):
    name: str

    def run(self, *, query: str, bundle: EvidenceBundle, max_theses: int = 3) -> list[ThesisItem]:
        """Build candidate theses grounded in bundle evidence."""


class OpponentAgentContract(Protocol):
    name: str

    def run(self, *, theses: list[ThesisItem], bundle: EvidenceBundle) -> list[ObjectionItem]:
        """Challenge thesis items with grounded objections."""


class EvidenceJudgeAgentContract(Protocol):
    name: str

    def run(
        self,
        *,
        theses: list[ThesisItem],
        objections: list[ObjectionItem],
        bundle: EvidenceBundle,
    ) -> EvidenceJudgeOutput:
        """Judge evidence quality and identify gaps."""


class RiskAnalystAgentContract(Protocol):
    name: str

    def run(
        self,
        *,
        theses: list[ThesisItem],
        evidence_judge: EvidenceJudgeOutput,
        objections: list[ObjectionItem],
    ) -> list[RiskItem]:
        """Extract major risks and invalidation conditions."""


# TODO: Add MCP-compatible tool adapter contracts for agent tools and evaluators.
