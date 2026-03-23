from __future__ import annotations

from statistics import mean

from packages.agents.schemas import (
    EvidenceCoverageItem,
    EvidenceJudgeOutput,
    ObjectionItem,
    ThesisItem,
)
from packages.rag.schemas import EvidenceBundle


class EvidenceJudgeAgent:
    name = "evidence-judge-agent"

    def run(
        self,
        *,
        theses: list[ThesisItem],
        objections: list[ObjectionItem],
        bundle: EvidenceBundle,
    ) -> EvidenceJudgeOutput:
        if not theses:
            return EvidenceJudgeOutput(
                coverage=[],
                overall_sufficiency_score=0.0,
                overall_label="insufficient",
                global_gaps=["No thesis-level evidence available."],
            )

        bundle_by_chunk = {item.chunk_id: item for item in bundle.items}
        objection_by_thesis = {item.thesis_id: item for item in objections}
        coverage: list[EvidenceCoverageItem] = []

        for thesis in theses:
            matched = [
                bundle_by_chunk[chunk_id]
                for chunk_id in thesis.evidence_chunk_ids
                if chunk_id in bundle_by_chunk
            ]
            scores = [item.score for item in matched]
            avg_score = mean(scores) if scores else 0.0
            source_diversity = len({item.document_id for item in matched})
            evidence_count = len(matched)

            support_score = min(
                1.0,
                (avg_score / 2.0)
                + (0.15 if evidence_count >= 2 else 0.0)
                + (0.1 if source_diversity >= 2 else 0.0),
            )
            support_score = round(support_score, 4)
            support_label = self._support_label(support_score)

            gaps: list[str] = []
            if evidence_count < 2:
                gaps.append("Needs at least two independent chunk references.")
            if source_diversity < 2:
                gaps.append("Needs broader source diversity across documents.")
            objection = objection_by_thesis.get(thesis.thesis_id)
            if objection and objection.severity >= 4:
                gaps.append("High-severity opponent objection remains unresolved.")

            coverage.append(
                EvidenceCoverageItem(
                    thesis_id=thesis.thesis_id,
                    support_score=support_score,
                    support_label=support_label,
                    supporting_chunk_ids=[item.chunk_id for item in matched],
                    gaps=gaps,
                    notes=(
                        f"avg_score={avg_score:.4f}; evidence_count={evidence_count}; "
                        f"source_diversity={source_diversity}"
                    ),
                )
            )

        overall_score = round(mean(item.support_score for item in coverage), 4)
        global_gaps = self._dedupe([gap for item in coverage for gap in item.gaps])
        return EvidenceJudgeOutput(
            coverage=coverage,
            overall_sufficiency_score=overall_score,
            overall_label=self._support_label(overall_score),
            global_gaps=global_gaps,
        )

    def _support_label(self, score: float) -> str:
        if score >= 0.75:
            return "strong"
        if score >= 0.5:
            return "moderate"
        if score >= 0.3:
            return "weak"
        return "insufficient"

    def _dedupe(self, values: list[str]) -> list[str]:
        ordered: list[str] = []
        for value in values:
            if value not in ordered:
                ordered.append(value)
        return ordered
