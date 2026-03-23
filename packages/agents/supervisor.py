from __future__ import annotations

import re

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

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]{3,}")


class SupervisorAgent:
    name = "supervisor-agent"

    def intake(self, request: ResearchAnalyzeRequest, bundle: EvidenceBundle) -> SupervisorIntake:
        normalized_query = " ".join(request.query.split())
        unique_terms: list[str] = []
        for token in TOKEN_PATTERN.findall(normalized_query.lower()):
            if token not in unique_terms:
                unique_terms.append(token)

        note = None
        if not bundle.items:
            note = "No evidence retrieved; workflow will return low-confidence structured memo."

        return SupervisorIntake(
            normalized_query=normalized_query,
            focus_terms=unique_terms[:8],
            planned_stages=[
                "retrieve_evidence",
                "thesis_builder",
                "opponent",
                "evidence_judge",
                "risk_analyst",
                "synthesize_memo",
            ],
            note=note,
        )

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
        if insufficient_evidence:
            executive = (
                "Retrieved evidence is insufficient for strong thesis formation. "
                "This memo records weak signals and prioritizes further data collection."
            )
        else:
            executive = (
                f"Retrieved evidence supports {len(theses)} candidate theses with "
                f"{evidence_judge.overall_label} evidence sufficiency."
            )

        next_questions = self._build_next_questions(evidence_judge.global_gaps, query)
        confidence_score = round(evidence_judge.overall_sufficiency_score, 4)
        confidence_assessment = (
            f"{evidence_judge.overall_label} confidence based on auditable chunk-level evidence."
        )

        return FinalResearchMemo(
            query=query,
            executive_summary=executive,
            key_theses=theses,
            counterarguments=objections,
            evidence_gaps=evidence_judge.global_gaps,
            major_risks=risks,
            confidence_assessment=confidence_assessment,
            confidence_score=confidence_score,
            suggested_next_questions=next_questions,
        )

    def _build_next_questions(self, global_gaps: list[str], query: str) -> list[str]:
        if not global_gaps:
            return [
                f"Which additional primary sources could strengthen confidence for '{query}'?",
                "What fresh filings or reports could invalidate current hypotheses?",
            ]

        questions = [f"What evidence can resolve this gap: {gap}" for gap in global_gaps[:3]]
        questions.append(
            "Are there high-quality counter-sources not represented in the current bundle?"
        )
        return questions
