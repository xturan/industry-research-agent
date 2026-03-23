from __future__ import annotations

import re
from collections.abc import Iterable

from packages.db.models import MemoryRecord

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_\-\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_PATTERN.findall(text)]


def keyword_score(*, text: str, query: str) -> float:
    if not query.strip():
        return 0.0
    terms = tokenize(query)
    if not terms:
        return 0.0

    haystack = text.lower()
    hit_count = 0
    for term in terms:
        if term in haystack:
            hit_count += 1
    return hit_count / len(terms)


def rank_memory_records(
    records: Iterable[MemoryRecord],
    *,
    query: str | None,
    recent_first: bool,
) -> list[MemoryRecord]:
    query_text = (query or "").strip()

    def sort_key(record: MemoryRecord) -> tuple[float, float, int]:
        base = record.score or 0.0
        query_bonus = 0.0
        if query_text:
            metadata_text = ""
            if isinstance(record.metadata_json, dict):
                metadata_text = " ".join(str(value) for value in record.metadata_json.values())
            query_bonus = keyword_score(text=f"{record.content} {metadata_text}", query=query_text)

        recency = record.last_accessed_at or record.updated_at or record.created_at
        recency_value = recency.timestamp() if recency is not None else 0.0

        total = base + (query_bonus * 0.5)
        if recent_first:
            return (total, recency_value, record.id)
        return (total, 0.0, record.id)

    return sorted(records, key=sort_key, reverse=True)
