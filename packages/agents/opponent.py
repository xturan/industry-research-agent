from __future__ import annotations

from packages.agents.schemas import ObjectionItem, ThesisItem
from packages.rag.schemas import EvidenceBundle


class OpponentAgent:
    name = "opponent-agent"

    def run(self, *, theses: list[ThesisItem], bundle: EvidenceBundle) -> list[ObjectionItem]:
        objections: list[ObjectionItem] = []
        for thesis in theses:
            evidence_count = len(thesis.evidence_chunk_ids)
            if evidence_count <= 1:
                objection = (
                    "Thesis depends on a single chunk and may not represent cross-source consensus."
                )
                severity = 4
                rationale = "Single-source concentration increases the chance of overfitting."
            elif thesis.stance == "constructive":
                objection = (
                    "Downside scenarios are underrepresented; adverse policy or demand shifts "
                    "could invalidate this constructive stance."
                )
                severity = 3
                rationale = "Constructive claims require explicit downside evidence checks."
            elif thesis.stance == "cautionary":
                objection = (
                    "Potential upside offsets are not fully covered, so the cautionary read may be "
                    "too one-sided."
                )
                severity = 3
                rationale = "Balanced analysis should include disconfirming upside evidence."
            else:
                objection = (
                    "Directional signal remains ambiguous; stronger evidence is required "
                    "to improve "
                    "decision usefulness."
                )
                severity = 2
                rationale = "Neutral theses are vulnerable to weak differentiation."

            objections.append(
                ObjectionItem(
                    thesis_id=thesis.thesis_id,
                    objection=objection,
                    severity=severity,
                    evidence_chunk_ids=thesis.evidence_chunk_ids,
                    evidence_refs=thesis.evidence_refs,
                    rationale=rationale,
                )
            )
        return objections
