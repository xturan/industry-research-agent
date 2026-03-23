from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from packages.db.models import Citation, Document, DocumentChunk, Thesis, ThesisEvidenceLink
from packages.db.models.enums import SourceType
from packages.rag.schemas import RetrievalChunkItem, RetrievalFilters, RetrievalResponse

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]{2,}")
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}")


@dataclass(slots=True)
class _Candidate:
    chunk: DocumentChunk
    document: Document
    lexical_score: float


class ChunkRetrievalService:
    """Chunk-level lexical retrieval with auditable scoring."""

    def __init__(self, session: Session):
        self.session = session

    def search_chunks(
        self, query: str, filters: RetrievalFilters | None = None
    ) -> RetrievalResponse:
        normalized_query = query.strip()
        filters = filters or RetrievalFilters()
        limit = min(max(filters.limit, 1), 50)
        tokens = self._tokenize(normalized_query)

        dialect_name = self._dialect_name()
        notes: list[str] = []
        if dialect_name == "postgresql" and normalized_query:
            candidates = self._search_postgres(normalized_query, tokens, filters, limit)
            retrieval_mode = "postgres_fts_v1"
            notes.append("Used PostgreSQL full-text retrieval for initial candidate generation.")
            if not candidates:
                candidates = self._search_fallback(normalized_query, tokens, filters, limit)
                retrieval_mode = "postgres_fts_fallback_v1"
                notes.append(
                    "PostgreSQL FTS returned no hits; fell back to lexical substring retrieval."
                )
        else:
            candidates = self._search_fallback(normalized_query, tokens, filters, limit)
            retrieval_mode = "lexical_fallback_v1"
            notes.append("Used lexical fallback retrieval (LIKE + deterministic rerank).")

        items = self._rerank_candidates(candidates, tokens, limit=limit)
        return RetrievalResponse(
            query=normalized_query,
            retrieval_mode=retrieval_mode,
            filters=filters,
            total_candidates=len(candidates),
            items=items,
            notes=notes,
        )

    def _apply_common_filters(
        self, stmt: Select[tuple[Any, ...]], filters: RetrievalFilters
    ) -> Select[tuple[Any, ...]]:
        if filters.source_type:
            stmt = stmt.where(Document.source_type == filters.source_type)
        if filters.document_status:
            stmt = stmt.where(Document.status == filters.document_status)
        if filters.industry:
            stmt = stmt.where(func.lower(Document.industry) == filters.industry.strip().lower())
        if filters.published_from:
            stmt = stmt.where(Document.published_at >= filters.published_from)
        if filters.published_to:
            stmt = stmt.where(Document.published_at <= filters.published_to)
        if filters.document_id:
            stmt = stmt.where(Document.id == filters.document_id)
        if filters.theme_id:
            theme_chunk_ids = (
                select(ThesisEvidenceLink.chunk_id)
                .join(Thesis, Thesis.id == ThesisEvidenceLink.thesis_id)
                .where(Thesis.theme_id == filters.theme_id)
            )
            stmt = stmt.where(DocumentChunk.id.in_(theme_chunk_ids))
        return stmt

    def _search_postgres(
        self, query: str, tokens: list[str], filters: RetrievalFilters, limit: int
    ) -> list[_Candidate]:
        vector = func.to_tsvector("english", func.coalesce(DocumentChunk.text, ""))
        ts_query = func.plainto_tsquery("english", query)
        rank = func.ts_rank_cd(vector, ts_query).label("lexical_score")
        stmt = (
            select(DocumentChunk, Document, rank)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(rank > 0)
        )
        stmt = self._apply_common_filters(stmt, filters)
        candidate_pool = max(limit * 8, 40)
        rows = self.session.execute(
            stmt.order_by(rank.desc(), Document.published_at.desc().nullslast()).limit(
                candidate_pool
            )
        ).all()
        return [
            _Candidate(chunk=chunk, document=document, lexical_score=float(lexical_score or 0.0))
            for chunk, document, lexical_score in rows
        ]

    def _search_fallback(
        self, query: str, tokens: list[str], filters: RetrievalFilters, limit: int
    ) -> list[_Candidate]:
        stmt = select(DocumentChunk, Document).join(
            Document, Document.id == DocumentChunk.document_id
        )
        stmt = self._apply_common_filters(stmt, filters)
        if tokens:
            token_filters = []
            for token in tokens:
                pattern = f"%{token}%"
                token_filters.append(
                    or_(
                        func.lower(DocumentChunk.text).like(pattern),
                        func.lower(Document.title).like(pattern),
                        func.lower(func.coalesce(Document.summary, "")).like(pattern),
                    )
                )
            stmt = stmt.where(or_(*token_filters))
        candidate_pool = max(limit * 8, 40)
        rows = self.session.execute(
            stmt.order_by(
                Document.published_at.desc().nullslast(), DocumentChunk.chunk_index.asc()
            ).limit(candidate_pool)
        ).all()
        return [
            _Candidate(
                chunk=chunk,
                document=document,
                lexical_score=self._fallback_lexical_score(tokens, chunk.text or "", document),
            )
            for chunk, document in rows
        ]

    def _fallback_lexical_score(
        self, tokens: list[str], chunk_text: str, document: Document
    ) -> float:
        if not tokens:
            return 0.0
        chunk_text_l = chunk_text.lower()
        title_l = (document.title or "").lower()
        summary_l = (document.summary or "").lower()
        total = 0.0
        for token in tokens:
            if token in chunk_text_l:
                total += 1.0
            if token in title_l:
                total += 0.5
            if token in summary_l:
                total += 0.25
        return total / float(len(tokens))

    def _rerank_candidates(
        self, candidates: list[_Candidate], tokens: list[str], *, limit: int
    ) -> list[RetrievalChunkItem]:
        if not candidates:
            return []

        sorted_candidates = sorted(
            candidates,
            key=lambda item: (
                item.lexical_score,
                self._published_timestamp(item.document.published_at),
            ),
            reverse=True,
        )
        citations_by_chunk = self._load_primary_citations(
            [item.chunk.id for item in sorted_candidates]
        )
        seen_documents: set[int] = set()
        reranked: list[RetrievalChunkItem] = []

        for candidate in sorted_candidates:
            doc = candidate.document
            chunk = candidate.chunk
            title_l = (doc.title or "").lower()
            summary_l = (doc.summary or "").lower()
            section_l = (chunk.section_name or "").lower()

            title_bonus = 0.0
            summary_bonus = 0.0
            section_bonus = 0.0
            for token in tokens:
                if token in title_l:
                    title_bonus = max(title_bonus, 0.15)
                if token in summary_l:
                    summary_bonus = max(summary_bonus, 0.08)
                if token in section_l:
                    section_bonus = max(section_bonus, 0.05)

            recency_bonus = 0.0
            if doc.published_at:
                age_days = max((datetime.now(doc.published_at.tzinfo) - doc.published_at).days, 0)
                if age_days <= 30:
                    recency_bonus = 0.05
                elif age_days <= 180:
                    recency_bonus = 0.03
                elif age_days <= 365:
                    recency_bonus = 0.015

            source_quality_bonus = 0.0
            if doc.source_type in {SourceType.REPORT, SourceType.FILING}:
                source_quality_bonus = 0.06
            elif doc.source_type == SourceType.ARTICLE:
                source_quality_bonus = 0.03

            diversity_bonus = 0.02 if doc.id not in seen_documents else 0.0
            seen_documents.add(doc.id)

            final_score = (
                candidate.lexical_score
                + title_bonus
                + summary_bonus
                + section_bonus
                + recency_bonus
                + source_quality_bonus
                + diversity_bonus
            )
            citation = citations_by_chunk.get(chunk.id)
            reranked.append(
                RetrievalChunkItem(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    chunk_index=chunk.chunk_index,
                    section_name=chunk.section_name,
                    chunk_text=chunk.text,
                    chunk_metadata=chunk.metadata_json,
                    citation_locator=citation.locator if citation else None,
                    citation_quote=citation.quote_text if citation else None,
                    document_title=doc.title,
                    source_uri=doc.source_uri,
                    publisher=doc.publisher,
                    published_at=doc.published_at,
                    source_type=doc.source_type.value,
                    document_status=doc.status.value,
                    industry=doc.industry,
                    score=round(final_score, 6),
                    score_breakdown={
                        "lexical": round(candidate.lexical_score, 6),
                        "title_bonus": round(title_bonus, 6),
                        "summary_bonus": round(summary_bonus, 6),
                        "section_bonus": round(section_bonus, 6),
                        "recency_bonus": round(recency_bonus, 6),
                        "source_quality_bonus": round(source_quality_bonus, 6),
                        "diversity_bonus": round(diversity_bonus, 6),
                    },
                )
            )

        reranked.sort(
            key=lambda item: (
                -item.score,
                -self._published_timestamp(item.published_at),
                item.chunk_index,
            )
        )
        return reranked[:limit]

    def _load_primary_citations(self, chunk_ids: list[int]) -> dict[int, Citation]:
        if not chunk_ids:
            return {}
        citations = self.session.scalars(
            select(Citation)
            .where(Citation.chunk_id.in_(chunk_ids))
            .order_by(Citation.chunk_id.asc(), Citation.id.asc())
        ).all()
        by_chunk: dict[int, Citation] = {}
        for citation in citations:
            if citation.chunk_id is None:
                continue
            by_chunk.setdefault(citation.chunk_id, citation)
        return by_chunk

    def _tokenize(self, query: str) -> list[str]:
        alnum_tokens = [token.lower() for token in TOKEN_PATTERN.findall(query)]
        cjk_tokens = CJK_PATTERN.findall(query)
        seen: set[str] = set()
        tokens: list[str] = []
        for token in [*alnum_tokens, *cjk_tokens]:
            normalized = token.strip()
            if not normalized or normalized in seen:
                continue
            tokens.append(normalized)
            seen.add(normalized)
        return tokens

    def _dialect_name(self) -> str:
        if self.session.bind and self.session.bind.dialect:
            return self.session.bind.dialect.name
        return "unknown"

    def _published_timestamp(self, value: datetime | None) -> float:
        if value is None:
            return -1.0
        try:
            return value.timestamp()
        except (ValueError, OSError):
            return -1.0
