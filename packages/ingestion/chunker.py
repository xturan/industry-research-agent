from __future__ import annotations

import re

from packages.ingestion.schemas import ChunkDraft, ParsedContent, ParsedSection


def _paragraphs(text: str) -> list[str]:
    return [segment.strip() for segment in re.split(r"\n\s*\n", text) if segment.strip()]


def chunk_parsed_content(
    parsed: ParsedContent,
    *,
    max_chars: int = 1200,
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
            joined_buffer = "\n\n".join(buffer_parts)
            candidate = paragraph if not buffer_parts else f"{joined_buffer}\n\n{paragraph}"
            if len(candidate) > max_chars and buffer_parts:
                chunk_text = "\n\n".join(buffer_parts).strip()
                if chunk_text:
                    metadata_json = {
                        "section_position": section_position,
                        "paragraph_start": start_paragraph_idx,
                        "paragraph_end": end_paragraph_idx,
                        "source_locator": section.locator,
                    }
                    chunks.append(
                        ChunkDraft(
                            chunk_index=chunk_index,
                            section_name=section.section_name,
                            text=chunk_text,
                            metadata_json=metadata_json,
                            token_count=len(chunk_text.split()),
                        )
                    )
                    chunk_index += 1
                buffer_parts = []
                start_paragraph_idx = paragraph_idx
            if not buffer_parts:
                start_paragraph_idx = paragraph_idx
            buffer_parts.append(paragraph)
            end_paragraph_idx = paragraph_idx

        chunk_text = "\n\n".join(buffer_parts).strip()
        if chunk_text:
            metadata_json = {
                "section_position": section_position,
                "paragraph_start": start_paragraph_idx,
                "paragraph_end": end_paragraph_idx,
                "source_locator": section.locator,
            }
            chunks.append(
                ChunkDraft(
                    chunk_index=chunk_index,
                    section_name=section.section_name,
                    text=chunk_text,
                    metadata_json=metadata_json,
                    token_count=len(chunk_text.split()),
                )
            )
            chunk_index += 1

    return chunks
