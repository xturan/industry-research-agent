from __future__ import annotations

from packages.agents.schemas import EvidenceJudgeOutput, ObjectionItem, RiskItem, ThesisItem


class RiskAnalystAgent:
    name = "risk-analyst-agent"

    def run(
        self,
        *,
        theses: list[ThesisItem],
        evidence_judge: EvidenceJudgeOutput,
        objections: list[ObjectionItem],
    ) -> list[RiskItem]:
        coverage_map = {item.thesis_id: item for item in evidence_judge.coverage}
        objection_map = {item.thesis_id: item for item in objections}
        risks: list[RiskItem] = []

        for thesis in theses:
            coverage = coverage_map.get(thesis.thesis_id)
            objection = objection_map.get(thesis.thesis_id)
            support_label = coverage.support_label if coverage else "insufficient"
            severity = 2
            if support_label == "moderate":
                severity = 3
            elif support_label in {"weak", "insufficient"}:
                severity = 4
            if objection and objection.severity >= 4:
                severity = min(5, severity + 1)

            risk_title = "Evidence concentration risk"
            if support_label == "strong":
                risk_title = "Scenario shift risk"
            elif support_label == "moderate":
                risk_title = "Partial evidence risk"

            objection_text = (
                objection.objection if objection else "No explicit objection recorded."
            )
            gaps_text = (
                "; ".join(coverage.gaps)
                if coverage and coverage.gaps
                else "No major gaps logged."
            )
            risks.append(
                RiskItem(
                    thesis_id=thesis.thesis_id,
                    risk_title=risk_title,
                    risk_description=f"{objection_text} Gaps: {gaps_text}",
                    invalidation_condition=(
                        "A credible source contradicts the cited chunks or fills the current gaps "
                        "with opposite evidence."
                    ),
                    severity=severity,
                    related_chunk_ids=thesis.evidence_chunk_ids,
                )
            )

        return risks
