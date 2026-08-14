from __future__ import annotations

import re

from packages.ingestion.schemas import ChunkDraft, ParsedContent, ParsedSection


def _paragraphs(text: str) -> list[str]:
    return [segment.strip() for segment in re.split(r"\n\s*\n", text) if segment.strip()]


def _split_long_paragraph(
    paragraph: str, *, max_chars: int
) -> list[str]:
    """Split a single over-long paragraph into pieces ≤ max_chars at sentence
    boundaries (。！？.!?\n). Piece concatenation == original text (no content
    loss). If no sentence boundary fits, fall back to hard character cuts."""
    pieces: list[str] = []
    remaining = paragraph
    # sentence-boundary regex: split after sentence-ending punctuation
    # (keep the punctuation with the preceding piece)
    while len(remaining) > max_chars:
        window = remaining[:max_chars]
        # find last sentence boundary within window (but not right at the edge)
        boundary = max(
            window.rfind(p) for p in ("。", "！", "？", ".", "!", "?", "\n")
        )
        if boundary <= 0 or boundary >= max_chars - 1:
            # no usable boundary -> hard cut (prefer near max_chars)
            boundary = max_chars
        else:
            boundary += 1  # include the punctuation
        pieces.append(remaining[:boundary].strip())
        remaining = remaining[boundary:].lstrip()
    if remaining.strip():
        pieces.append(remaining.strip())
    return [p for p in pieces if p]


def _emit_chunk(
    *,
    chunks: list[ChunkDraft],
    chunk_index: int,
    section_position: int,
    section_name: str | None,
    start_paragraph_idx: int,
    end_paragraph_idx: int,
    locator: str,
    text: str,
) -> int:
    """Append a ChunkDraft; returns next chunk_index."""
    chunk_text = text.strip()
    if chunk_text:
        chunks.append(
            ChunkDraft(
                chunk_index=chunk_index,
                section_name=section_name,
                text=chunk_text,
                metadata_json={
                    "section_position": section_position,
                    "paragraph_start": start_paragraph_idx,
                    "paragraph_end": end_paragraph_idx,
                    "source_locator": locator,
                },
                token_count=len(chunk_text.split()),
            )
        )
        chunk_index += 1
    return chunk_index


def chunk_parsed_content(
    parsed: ParsedContent,
    *,
    max_chars: int = 1200,
    force_split_long_paragraphs: bool = True,
) -> list[ChunkDraft]:
    if not parsed.sections:
        parsed_sections = [ParsedSection(section_name=None, text=parsed.text, locator="body:0")]
    else:
        parsed_sections = parsed.sections

    chunks: list[ChunkDraft] = []
    chunk_index = 0

    for section_position, section in enumerate(parsed_sections):
        paragraphs = _paragraphs(section.text)
        if not paragraphs:
            continue

        start_paragraph_idx = 0
        end_paragraph_idx = -1
        buffer_parts: list[str] = []

        for paragraph_idx, paragraph in enumerate(paragraphs):
            # ── Force split single over-long paragraphs ──
            # Without this, a 40k-char paragraph becomes ONE chunk and gets
            # truncated downstream (reranker / atomic extractor) — losing content.
            # Split at sentence boundaries into ≤max_chars pieces; concatenation
            # of pieces == original paragraph (content-conserving).
            if force_split_long_paragraphs and len(paragraph) > max_chars:
                # flush any buffered paragraphs first (keep chunk ordering)
                if buffer_parts:
                    chunk_text = "\n\n".join(buffer_parts).strip()
                    chunk_index = _emit_chunk(
                        chunks=chunks, chunk_index=chunk_index,
                        section_position=section_position,
                        section_name=section.section_name,
                        start_paragraph_idx=start_paragraph_idx,
                        end_paragraph_idx=end_paragraph_idx,
                        locator=section.locator, text=chunk_text,
                    )
                    buffer_parts = []
                piece_meta_start = paragraph_idx
                for piece in _split_long_paragraph(paragraph, max_chars=max_chars):
                    chunk_index = _emit_chunk(
                        chunks=chunks, chunk_index=chunk_index,
                        section_position=section_position,
                        section_name=section.section_name,
                        start_paragraph_idx=piece_meta_start,
                        end_paragraph_idx=paragraph_idx,
                        locator=section.locator, text=piece,
                    )
                continue

            joined_buffer = "\n\n".join(buffer_parts)
            candidate = paragraph if not buffer_parts else f"{joined_buffer}\n\n{paragraph}"
            if len(candidate) > max_chars and buffer_parts:
                chunk_text = "\n\n".join(buffer_parts).strip()
                chunk_index = _emit_chunk(
                    chunks=chunks, chunk_index=chunk_index,
                    section_position=section_position,
                    section_name=section.section_name,
                    start_paragraph_idx=start_paragraph_idx,
                    end_paragraph_idx=end_paragraph_idx,
                    locator=section.locator, text=chunk_text,
                )
                buffer_parts = []
                start_paragraph_idx = paragraph_idx
            if not buffer_parts:
                start_paragraph_idx = paragraph_idx
            buffer_parts.append(paragraph)
            end_paragraph_idx = paragraph_idx

        chunk_text = "\n\n".join(buffer_parts).strip()
        chunk_index = _emit_chunk(
            chunks=chunks, chunk_index=chunk_index,
            section_position=section_position,
            section_name=section.section_name,
            start_paragraph_idx=start_paragraph_idx,
            end_paragraph_idx=end_paragraph_idx,
            locator=section.locator, text=chunk_text,
        )

    return chunks
