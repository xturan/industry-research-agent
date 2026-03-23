from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from packages.ingestion.schemas import ParsedContent, ParsedSection, RawSourceData

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
PUBLISHED_TIME_META_KEYS = (
    "article:published_time",
    "og:published_time",
    "pubdate",
    "date",
    "dc.date",
)


def _decode_content(raw_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")


def _parse_possible_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _build_markdown_sections(text: str) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    heading_index = -1

    def flush() -> None:
        nonlocal heading_index
        body = "\n".join(current_lines).strip()
        if not body:
            return
        heading_index += 1
        sections.append(
            ParsedSection(
                section_name=current_heading,
                text=body,
                locator=f"heading:{heading_index}",
                metadata={"parser": "markdown"},
            )
        )

    for line in text.splitlines():
        match = HEADING_PATTERN.match(line.strip())
        if match:
            flush()
            current_lines = []
            current_heading = match.group(2).strip()
            continue
        current_lines.append(line)
    flush()

    if not sections and text.strip():
        sections.append(
            ParsedSection(
                section_name=None,
                text=text.strip(),
                locator="body:0",
                metadata={"parser": "markdown"},
            )
        )
    return sections


def _parse_text(raw: RawSourceData, text: str) -> ParsedContent:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Source content is empty after decoding.")
    title = lines[0][:200]
    section = ParsedSection(
        section_name=None,
        text=text.strip(),
        locator="body:0",
        metadata={"parser": "plain_text"},
    )
    return ParsedContent(
        title=title,
        text=text.strip(),
        source_uri=raw.source_uri,
        sections=[section],
        metadata={"parser": "plain_text"},
    )


def _parse_markdown(raw: RawSourceData, text: str) -> ParsedContent:
    sections = _build_markdown_sections(text)
    if not sections:
        raise ValueError("Markdown parsing produced no content.")
    top_heading = None
    for line in text.splitlines():
        match = HEADING_PATTERN.match(line.strip())
        if match and len(match.group(1)) == 1:
            top_heading = match.group(2).strip()
            break
    heading_title = next(
        (section.section_name for section in sections if section.section_name), None
    )
    title = top_heading or heading_title or sections[0].text.splitlines()[0][:200]
    merged_text = "\n\n".join(section.text for section in sections)
    return ParsedContent(
        title=title,
        text=merged_text,
        source_uri=raw.source_uri,
        sections=sections,
        metadata={"parser": "markdown"},
    )


def _parse_html(raw: RawSourceData, text: str) -> ParsedContent:
    soup = BeautifulSoup(text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else Path(raw.source_name).stem

    for tag_name in ("script", "style", "noscript"):
        for node in soup.find_all(tag_name):
            node.decompose()

    publisher = None
    published_at = None
    for meta in soup.find_all("meta"):
        key = (meta.get("property") or meta.get("name") or "").strip().lower()
        content = meta.get("content")
        if key == "og:site_name" and content:
            publisher = content.strip()
        if key in PUBLISHED_TIME_META_KEYS:
            parsed_time = _parse_possible_datetime(content)
            if parsed_time:
                published_at = parsed_time

    main = soup.find("article") or soup.body or soup
    sections: list[ParsedSection] = []
    section_buckets: list[dict[str, Any]] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    section_index = -1

    def flush_section() -> None:
        nonlocal section_index
        body = "\n\n".join(line for line in current_lines if line).strip()
        if not body:
            return
        section_index += 1
        sections.append(
            ParsedSection(
                section_name=current_heading,
                text=body,
                locator=f"section:{section_index}",
                metadata={"parser": "html"},
            )
        )
        section_buckets.append({"section_name": current_heading, "char_count": len(body)})

    for node in main.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        node_text = node.get_text(" ", strip=True)
        if not node_text:
            continue
        if node.name and node.name.startswith("h"):
            flush_section()
            current_lines = []
            current_heading = node_text
            continue
        current_lines.append(node_text)
    flush_section()

    if not sections:
        fallback_text = main.get_text(" ", strip=True)
        if not fallback_text:
            raise ValueError("HTML parsing produced no readable text.")
        sections = [
            ParsedSection(
                section_name=None,
                text=fallback_text,
                locator="body:0",
                metadata={"parser": "html"},
            )
        ]

    merged_text = "\n\n".join(section.text for section in sections)
    return ParsedContent(
        title=title[:200],
        text=merged_text,
        source_uri=raw.source_uri,
        sections=sections,
        publisher=publisher,
        published_at=published_at,
        metadata={"parser": "html", "section_count": len(sections), "sections": section_buckets},
    )


def parse_source(raw: RawSourceData) -> ParsedContent:
    text = _decode_content(raw.content_bytes)
    extension = (raw.file_extension or "").lower()
    media_type = (raw.media_type or "").lower()

    if extension in {".md", ".markdown"} or media_type == "text/markdown":
        return _parse_markdown(raw, text)
    if extension in {".html", ".htm"} or media_type == "text/html":
        return _parse_html(raw, text)
    return _parse_text(raw, text)
