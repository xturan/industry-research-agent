from __future__ import annotations

import re
from collections import defaultdict
from statistics import mean

from packages.agents.schemas import ThesisItem
from packages.rag.schemas import EvidenceBundle, RetrievalChunkItem

POSITIVE_HINTS = {
    "growth",
    "increase",
    "expansion",
    "strong",
    "resilient",
    "elevated",
    "pricing",
    "improve",
}
NEGATIVE_HINTS = {
    "decline",
    "weak",
    "delay",
    "risk",
    "constraint",
    "pressure",
    "drop",
    "shortage",
}


class ThesisBuilderAgent:
    name = "thesis-builder-agent"

    def run(self, *, query: str, bundle: EvidenceBundle, max_theses: int = 3) -> list[ThesisItem]:
        grouped: dict[int, list[RetrievalChunkItem]] = defaultdict(list)
        for item in bundle.items:
            grouped[item.document_id].append(item)

        ordered_groups = sorted(
            grouped.values(),
            key=lambda items: max(chunk.score for chunk in items),
            reverse=True,
        )

        theses: list[ThesisItem] = []
        for index, doc_items in enumerate(ordered_groups[:max_theses], start=1):
            chosen_items = sorted(doc_items, key=lambda item: item.score, reverse=True)[:2]
            lead = chosen_items[0]
            combined_text = " ".join(item.chunk_text for item in chosen_items).lower()
            stance = self._infer_stance(combined_text)
            support_strength = round(min(1.0, mean(item.score for item in chosen_items) / 2.0), 4)
            confidence_score = round(min(0.95, 0.35 + support_strength * 0.6), 4)
            title = self._build_title(query, lead)
            summary = self._build_summary(chosen_items)

            evidence_chunk_ids = [item.chunk_id for item in chosen_items]
            evidence_refs = [
                self._evidence_ref(item.document_id, item.chunk_id, item.citation_locator)
                for item in chosen_items
            ]

            theses.append(
                ThesisItem(
                    thesis_id=f"thesis_{index}",
                    title=title,
                    stance=stance,
                    summary=summary,
                    confidence_score=confidence_score,
                    support_strength=support_strength,
                    evidence_chunk_ids=evidence_chunk_ids,
                    evidence_refs=evidence_refs,
                    rationale=(
                        "Generated from top-ranked chunk groups with deterministic lexical "
                        "signals and explicit evidence references."
                    ),
                )
            )
        return theses

    def _infer_stance(self, text: str) -> str:
        tokens = set(re.findall(r"[a-zA-Z]{3,}", text))
        positive_hits = len(tokens & POSITIVE_HINTS)
        negative_hits = len(tokens & NEGATIVE_HINTS)
        if positive_hits - negative_hits >= 2:
            return "constructive"
        if negative_hits - positive_hits >= 2:
            return "cautionary"
        return "neutral"

    def _build_title(self, query: str, lead: RetrievalChunkItem) -> str:
        focus = (lead.section_name or lead.document_title).strip()
        clipped_query = query.strip()[:80]
        return f"{focus}: evidence signal for '{clipped_query}'"

    def _build_summary(self, items: list[RetrievalChunkItem]) -> str:
        lead_text = items[0].chunk_text.strip().split(".")[0].strip()
        return (
            f"{lead_text}. "
            f"Based on {len(items)} chunk(s) from source '{items[0].document_title}'."
        )

    def _evidence_ref(self, document_id: int, chunk_id: int, locator: str | None) -> str:
        if locator:
            return f"doc:{document_id}/chunk:{chunk_id}@{locator}"
        return f"doc:{document_id}/chunk:{chunk_id}"
