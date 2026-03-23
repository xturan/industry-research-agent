from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from packages.db.models import SourceType


@dataclass(slots=True)
class RawSourceData:
    source_uri: str
    source_name: str
    source_type: SourceType
    content_bytes: bytes
    media_type: str | None = None
    file_extension: str | None = None


@dataclass(slots=True)
class StoredRawSource:
    storage_path: str
    content_hash: str
    byte_size: int


@dataclass(slots=True)
class ParsedSection:
    section_name: str | None
    text: str
    locator: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedContent:
    title: str
    text: str
    source_uri: str
    sections: list[ParsedSection]
    publisher: str | None = None
    published_at: datetime | None = None
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChunkDraft:
    chunk_index: int
    section_name: str | None
    text: str
    metadata_json: dict[str, Any]
    token_count: int


@dataclass(slots=True)
class CitationDraft:
    locator: str
    quote_text: str
