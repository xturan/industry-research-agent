from __future__ import annotations

from packages.ingestion.schemas import ChunkDraft, CitationDraft


def build_citations_for_chunks(chunks: list[ChunkDraft]) -> list[CitationDraft]:
    citations: list[CitationDraft] = []
    for chunk in chunks:
        locator_prefix = chunk.section_name or "body"
        paragraph_start = chunk.metadata_json.get("paragraph_start", 0)
        paragraph_end = chunk.metadata_json.get("paragraph_end", paragraph_start)
        locator = (
            f"{locator_prefix} | chunk:{chunk.chunk_index} | "
            f"paragraphs:{paragraph_start}-{paragraph_end}"
        )
        quote_text = chunk.text[:280]
        citations.append(CitationDraft(locator=locator, quote_text=quote_text))
    return citations
