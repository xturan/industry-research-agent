from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.models import MemoryRecord
from packages.memory.schemas import (
    MemoryCandidate,
    MemoryRecordView,
    MemorySearchRequest,
    to_db_memory_type,
    to_memory_kind,
)
from packages.memory.selectors import keyword_score, rank_memory_records

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc


class MemoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_candidate(self, candidate: MemoryCandidate) -> MemoryRecord:
        db_memory_type = to_db_memory_type(candidate.memory_type)
        existing = self._find_existing(
            memory_type=db_memory_type,
            scope_key=candidate.scope_key,
            content=candidate.content,
            metadata_json=candidate.metadata_json,
        )

        if existing is None:
            existing = MemoryRecord(
                memory_type=db_memory_type,
                scope_key=candidate.scope_key,
                content=candidate.content,
            )
            self.session.add(existing)

        existing.content = candidate.content
        existing.score = candidate.score
        existing.metadata_json = candidate.metadata_json
        existing.last_accessed_at = datetime.now(UTC)
        self.session.flush()
        return existing

    def bulk_upsert(self, candidates: list[MemoryCandidate]) -> list[MemoryRecord]:
        rows = [self.upsert_candidate(candidate) for candidate in candidates]
        self.session.commit()
        for row in rows:
            self.session.refresh(row)
        return rows

    def search(self, request: MemorySearchRequest) -> list[MemoryRecord]:
        stmt = select(MemoryRecord)

        if request.memory_types:
            db_types = [to_db_memory_type(item) for item in request.memory_types]
            stmt = stmt.where(MemoryRecord.memory_type.in_(db_types))

        if request.scope_key:
            stmt = stmt.where(MemoryRecord.scope_key.like(f"{request.scope_key}%"))

        if request.min_score is not None:
            stmt = stmt.where(MemoryRecord.score >= request.min_score)

        records = self.session.scalars(stmt).all()
        ranked = rank_memory_records(
            records,
            query=request.query,
            recent_first=request.recent_first,
        )

        if request.query and request.query.strip():
            filtered: list[MemoryRecord] = []
            for row in ranked:
                metadata_text = ""
                if isinstance(row.metadata_json, dict):
                    metadata_text = " ".join(str(value) for value in row.metadata_json.values())
                score = keyword_score(text=f"{row.content} {metadata_text}", query=request.query)
                if score > 0.0:
                    filtered.append(row)
            ranked = filtered

        selected = ranked[: request.limit]
        now = datetime.now(UTC)
        for row in selected:
            row.last_accessed_at = now
            self.session.add(row)
        if selected:
            self.session.commit()

        return selected

    def list_by_scope(self, scope_key: str, *, limit: int = 50) -> list[MemoryRecord]:
        rows = self.session.scalars(
            select(MemoryRecord)
            .where(MemoryRecord.scope_key.like(f"{scope_key}%"))
            .order_by(MemoryRecord.updated_at.desc(), MemoryRecord.id.desc())
            .limit(limit)
        ).all()
        now = datetime.now(UTC)
        for row in rows:
            row.last_accessed_at = now
            self.session.add(row)
        if rows:
            self.session.commit()
        return rows

    def _find_existing(
        self,
        *,
        memory_type: Any,
        scope_key: str,
        content: str,
        metadata_json: dict[str, object],
    ) -> MemoryRecord | None:
        rows = self.session.scalars(
            select(MemoryRecord)
            .where(
                MemoryRecord.memory_type == memory_type,
                MemoryRecord.scope_key == scope_key,
            )
            .order_by(MemoryRecord.id.asc())
        ).all()

        memory_key = metadata_json.get("memory_key")
        if isinstance(memory_key, str) and memory_key:
            for row in rows:
                if not isinstance(row.metadata_json, dict):
                    continue
                if row.metadata_json.get("memory_key") == memory_key:
                    return row

        for row in rows:
            if row.content == content:
                return row

        return None


def memory_to_view(row: MemoryRecord) -> MemoryRecordView:
    return MemoryRecordView(
        id=row.id,
        memory_type=to_memory_kind(row.memory_type),
        scope_key=row.scope_key,
        content=row.content,
        score=row.score,
        metadata_json=row.metadata_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_accessed_at=row.last_accessed_at,
    )
