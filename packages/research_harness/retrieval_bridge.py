from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.models import Citation, Document, DocumentChunk, DocumentStatus, SourceType
from packages.ingestion.chunker import chunk_parsed_content
from packages.ingestion.citations import build_citations_for_chunks
from packages.ingestion.schemas import ParsedContent, ParsedSection
from packages.rag.chunk_quality import score_chunk_quality
from packages.rag.embeddings import build_deterministic_embedding
from packages.rag.retrieval import ChunkRetrievalService
from packages.rag.schemas import RetrievalChunkItem, RetrievalFilters, RetrievalResponse
from packages.sources.local_source_patterns import canonical_source_family

_SOURCE_FAMILY_TO_TYPE = {
    "policy_document": SourceType.REPORT,
    "tender_procurement": SourceType.ARTICLE,
    "company_disclosure": SourceType.FILING,
    "exchange_disclosure": SourceType.FILING,
    "official_statistics": SourceType.DATASET,
}

_SOURCE_FAMILY_BONUS = {
    "policy_document": 0.08,
    "tender_procurement": 0.07,
    "company_disclosure": 0.07,
    "exchange_disclosure": 0.07,
    "official_statistics": 0.06,
}

_GRAPH_RUNTIME_RETENTION_POLICY = "delete_on_terminal_run"
_GRAPH_RUNTIME_CLEANUP_SCOPE = "graph_run_scoped_documents"

# Graph-runtime ranking: coarse top-N docs, rerank top-K chunks.
_RETRIEVAL_COARSE_TOP_N = 30
_RETRIEVAL_RERANK_TOP_K = 24


def _collect_search_phrases(plan: dict[str, Any]) -> list[str]:
    """Collect all search phrases from the plan's search_rounds, plus each
    dimension's caliber_terms so the coarse-rank query keeps dimension focus."""
    phrases: list[str] = []
    for round_plan in plan.get("search_rounds") or []:
        if not isinstance(round_plan, dict):
            continue
        for phrase in round_plan.get("search_phrases") or []:
            text = str(phrase or "").strip()
            if text and text not in phrases:
                phrases.append(text)
    for dim in plan.get("dimension_plan") or []:
        if not isinstance(dim, dict):
            continue
        for term in dim.get("caliber_terms") or []:
            text = str(term or "").strip()
            if text and text not in phrases:
                phrases.append(text)
    return phrases


def _items_from_ranked_chunks(
    chunks: list[dict[str, Any]],
) -> list[RetrievalChunkItem]:
    """Build RetrievalChunkItem list from ranked chunk dicts (score = rerank)."""
    items: list[RetrievalChunkItem] = []
    for idx, chunk in enumerate(chunks):
        score = float(
            chunk.get("rerank_score")
            or chunk.get("_coarse_rrf_score")
            or 0.0
        )
        items.append(RetrievalChunkItem(
            chunk_id=10_000_000 + idx + 1,
            document_id=20_000_000 + idx + 1,
            chunk_index=int(chunk.get("chunk_index") or 0),
            section_name="source",
            chunk_text=str(chunk.get("chunk_text") or ""),
            chunk_metadata=dict(chunk.get("chunk_metadata") or {}),
            citation_locator=str(chunk.get("chunk_id") or "") or None,
            citation_quote=str(chunk.get("chunk_text") or "")[:280] or None,
            document_title=str(chunk.get("document_title") or ""),
            source_uri=str(chunk.get("source_uri") or "") or None,
            publisher=None,
            published_at=None,
            source_type=str(chunk.get("source_type") or "other"),
            document_status="graph_runtime_source",
            industry=None,
            score=score,
            score_breakdown={
                "rerank_score": chunk.get("rerank_score"),
                "coarse_rrf": chunk.get("_coarse_rrf_score"),
            },
        ))
    return items


def build_graph_retrieval_artifacts(
    *,
    query: str,
    sources: list[dict[str, Any]],
    plan: dict[str, Any] | None = None,
    query_requirements: dict[str, Any] | None = None,
    run_id: int | None = None,
    session: Session | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    # ── Graph-runtime 主路径（恒走）：dedup -> coarse rank -> chunk -> LLM reranker ──
    # source_chunks 恒 = 精排 chunk（覆盖所有粗排选中 source 的 chunk，非仅 top-k）。
    # 旧逻辑用 _build_source_chunks(所有 sources) 无脑 chunk 是浪费；persistent 分支
    # 也只附加 retrieval_pack，不再提前 return 覆盖 source_chunks。
    from packages.research_harness.retrieval_rank import rank_retrieved_sources

    search_phrases = _collect_search_phrases(plan or {})
    # 2026-08-11：LLM 维度搜索词优先作为精排 query（语义完整查询式，比短语拼接精准）
    dimension_terms = (plan or {}).get("dimension_search_terms") or None
    ranked = rank_retrieved_sources(
        sources,
        query,
        search_phrases,
        coarse_top_n=_RETRIEVAL_COARSE_TOP_N,
        rerank_top_k=_RETRIEVAL_RERANK_TOP_K,
        dimension_terms=dimension_terms,
    )
    reranked_chunks = ranked.get("source_chunks", [])
    items = _items_from_ranked_chunks(reranked_chunks)
    adapter_status = "graph_runtime_only"
    adapter_notes: list[str] = []
    persisted_document_ids: list[int] = []
    backend_retrieval_mode = ""

    if session is not None and run_id is not None:
        try:
            persisted_document_ids = _persist_graph_runtime_documents(
                session=session,
                run_id=run_id,
                sources=sources,
            )
            if persisted_document_ids:
                retrieval_response = _build_persistent_retrieval_response(
                    query=query,
                    session=session,
                    document_ids=persisted_document_ids,
                    plan=plan or {},
                    query_requirements=query_requirements or {},
                    limit=limit,
                )
                adapter_status = "persistent_graph_documents"
                backend_retrieval_mode = retrieval_response.retrieval_mode
        except Exception as exc:
            session.rollback()
            adapter_status = "persistent_adapter_failed_fallback"
            adapter_notes.append(f"Persistent graph retrieval adapter failed: {exc}")

    retrieval_response = RetrievalResponse(
        query=query.strip(),
        retrieval_mode="graph_runtime_rank_v1",
        filters=RetrievalFilters(limit=len(items) or limit),
        total_candidates=len(items),
        items=items,
        notes=[
            "Graph-runtime ranking: dedup -> BM25 + hash-vector (RRF) -> chunk -> "
            "LLM reranker rerank.",
            f"rerank_mode={ranked.get('rerank_mode')}",
            f"adapter_status={adapter_status}",
            *list(adapter_notes or []),
        ],
        audit={
            "rerank_mode": ranked.get("rerank_mode"),
            "coarse_meta": ranked.get("coarse_meta"),
            "ranked_source_count": len(ranked.get("ranked_sources", [])),
            "adapter_status": adapter_status,
            "persisted_document_ids": persisted_document_ids,
        },
    )
    return {
        "source_chunks": reranked_chunks,
        "retrieval_pack": _retrieval_pack_payload(
            retrieval_response=retrieval_response,
            plan=plan or {},
            adapter_status=adapter_status,
            persisted_document_ids=persisted_document_ids,
            backend_retrieval_mode=backend_retrieval_mode,
            adapter_notes=adapter_notes,
        ),
    }


def _build_retrieval_response(
    *,
    query: str,
    chunks: list[dict[str, Any]],
    plan: dict[str, Any],
    query_requirements: dict[str, Any],
    limit: int,
    adapter_notes: list[str] | None = None,
) -> RetrievalResponse:
    dimension_entries = list(plan.get("dimension_plan", []))
    obligation_entries = list(plan.get("source_obligations", []))
    target_location = str(query_requirements.get("target_location") or "").strip()
    dimension_terms = _collect_dimension_terms(dimension_entries)
    dimension_families = _collect_dimension_families(dimension_entries)
    obligation_families = _collect_obligation_families(obligation_entries)
    ranked = _rank_source_chunks(
        query=query,
        chunks=chunks,
        dimension_terms=dimension_terms,
        dimension_families=dimension_families,
        obligation_families=obligation_families,
        target_location=target_location,
        limit=limit,
    )
    notes = [
        "Built graph-local chunks from current source text using repository chunking semantics.",
        "Applied dimension-aware lexical retrieval over graph-local runtime chunks.",
        (
            "Ranking now considers query match, dimension terms, "
            "source-family obligations, and location alignment."
        ),
        (
            "This is a graph-runtime retrieval adapter; PostgreSQL + "
            "pgvector + BM25 + reranker is still pending."
        ),
        *list(adapter_notes or []),
    ]
    retrieval_mode = "graph_runtime_hybrid_contract_v1"
    return RetrievalResponse(
        query=query.strip(),
        retrieval_mode=retrieval_mode,
        filters=RetrievalFilters(limit=limit),
        total_candidates=len(chunks),
        items=ranked,
        notes=notes,
    )


def _build_persistent_retrieval_response(
    *,
    query: str,
    session: Session,
    document_ids: list[int],
    plan: dict[str, Any],
    query_requirements: dict[str, Any],
    limit: int,
) -> RetrievalResponse:
    service = ChunkRetrievalService(session)
    candidate_limit = max(limit * 3, 12)
    response = service.search_chunks(
        query,
        RetrievalFilters(
            document_ids=document_ids,
            chunk_levels=["child"],
            limit=candidate_limit,
            rerank_mode="lane_balance_v1",
        ),
    )
    expanded_response = _expand_persistent_context_items(
        session=session,
        items=response.items,
        limit=limit,
    )

    focused_items = _apply_focus_to_persistent_items(
        items=expanded_response["items"],
        query=query,
        plan=plan,
        query_requirements=query_requirements,
        limit=limit,
    )
    backend_mode = response.retrieval_mode or "chunk_retrieval_service"
    backend_audit = dict(response.audit or {})
    return RetrievalResponse(
        query=query.strip(),
        retrieval_mode=f"graph_persistent_retrieval_adapter_v1::{backend_mode}",
        filters=RetrievalFilters(document_ids=document_ids, limit=limit),
        total_candidates=response.total_candidates,
        items=focused_items,
        notes=[
            "Persisted graph runtime sources into Document/DocumentChunk-compatible rows.",
            "Scoped retrieval to the current graph run's persisted document ids.",
            "Reused ChunkRetrievalService scoped document-set retrieval before graph focus rerank.",
            "Expanded child hits with parent and adjacent context before graph focus rerank.",
            "Applied dimension/source-obligation/location focus after backend retrieval.",
        ],
        audit={
            "backend_candidate_collection": backend_audit.get("candidate_collection", []),
            "backend_rerank_strategy": backend_audit.get("rerank_strategy"),
            "backend_lane_weights": backend_audit.get("lane_weights", {}),
            "backend_rerank_mode": backend_audit.get("rerank_mode"),
            "context_expansion": expanded_response["audit"],
            "scoped_document_count": len(document_ids),
        },
    )


def _persist_graph_runtime_documents(
    *,
    session: Session,
    run_id: int,
    sources: list[dict[str, Any]],
) -> list[int]:
    document_ids: list[int] = []
    for source in sources:
        source_id = str(source.get("source_id") or "").strip()
        text = str(
            source.get("clean_text")
            or source.get("raw_text")
            or source.get("snippet")
            or ""
        ).strip()
        if not source_id or not text:
            continue
        source_family = canonical_source_family(source.get("source_family"))
        parsed = _source_to_parsed_content(source, text=text, source_family=source_family)
        content_hash = _graph_content_hash(run_id=run_id, source_id=source_id, text=text)
        document = session.scalar(select(Document).where(Document.content_hash == content_hash))
        if document is None:
            document = Document(
                title=parsed.title[:512] or source_id,
                source_type=_source_type_for_family(source_family),
                source_uri=parsed.source_uri,
                publisher=parsed.publisher,
                published_at=parsed.published_at,
                language=parsed.language,
                summary=parsed.text[:500],
                raw_storage_path=None,
                content_hash=content_hash,
                status=DocumentStatus.PARSED,
            )
            session.add(document)
            session.flush()
        else:
            document.title = parsed.title[:512] or source_id
            document.source_type = _source_type_for_family(source_family)
            document.source_uri = parsed.source_uri
            document.publisher = parsed.publisher
            document.published_at = parsed.published_at
            document.language = parsed.language
            document.summary = parsed.text[:500]
            document.status = DocumentStatus.PARSED
            session.add(document)
            session.flush()
            _delete_existing_document_chunks(session=session, document_id=document.id)

        chunk_drafts = chunk_parsed_content(parsed, max_chars=700)
        source_tier = str(source.get("source_tier") or "C")
        for chunk in chunk_drafts:
            quality = score_chunk_quality(
                chunk.text,
                source_family=source_family,
                source_tier=source_tier,
            )
            chunk.metadata_json["chunk_quality"] = {
                "info_density": quality.info_density,
                "citability": quality.citability,
                "authority": quality.authority,
                "composite": quality.composite,
            }
        citation_drafts = build_citations_for_chunks(chunk_drafts)
        chunk_rows: list[DocumentChunk] = []
        for chunk in chunk_drafts:
            # ChunkDraft 重构后无 index_text/chunk_level/section_path/parent_chunk_index，
            # 索引文本直接用 chunk.text（DocumentChunk 也无这些列）。
            embedding = build_deterministic_embedding(chunk.text)
            row = DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                section_name=chunk.section_name,
                text=chunk.text,
                metadata_json={
                    **dict(chunk.metadata_json),
                    "graph_run_id": run_id,
                    "graph_source_id": source_id,
                    "source_family": source_family,
                    "source_tier": source_tier,
                    "graph_runtime_document": True,
                    "retention_policy": _GRAPH_RUNTIME_RETENTION_POLICY,
                },
                token_count=chunk.token_count,
                embedding_json=embedding,
                embedding_model="deterministic_hash_embed_v1",
                embedding_dimension=16,
            )
            session.add(row)
            chunk_rows.append(row)
        session.flush()
        for index, chunk_row in enumerate(chunk_rows):
            citation = citation_drafts[index]
            session.add(
                Citation(
                    document_id=document.id,
                    chunk_id=chunk_row.id,
                    locator=citation.locator,
                    quote_text=citation.quote_text,
                )
            )
        document.status = DocumentStatus.INDEXED
        session.add(document)
        session.flush()
        document_ids.append(document.id)
    session.commit()
    return document_ids


def _delete_existing_document_chunks(*, session: Session, document_id: int) -> None:
    session.query(Citation).filter(Citation.document_id == document_id).delete(
        synchronize_session=False
    )
    session.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete(
        synchronize_session=False
    )
    session.flush()


def _source_type_for_family(source_family: str) -> SourceType:
    return _SOURCE_FAMILY_TO_TYPE.get(source_family, SourceType.OTHER)


def _graph_content_hash(*, run_id: int, source_id: str, text: str) -> str:
    digest = hashlib.sha1(f"{run_id}|{source_id}|{text}".encode()).hexdigest()
    return f"graph:{run_id}:{source_id}:{digest}"[:128]


def cleanup_graph_runtime_documents(*, session: Session, run_id: int) -> dict[str, int | str]:
    prefix = f"graph:{run_id}:"
    document_ids = list(
        session.scalars(select(Document.id).where(Document.content_hash.like(f"{prefix}%"))).all()
    )
    if not document_ids:
        return {
            "cleanup_scope": _GRAPH_RUNTIME_CLEANUP_SCOPE,
            "retention_policy": _GRAPH_RUNTIME_RETENTION_POLICY,
            "document_count": 0,
            "chunk_count": 0,
            "citation_count": 0,
        }
    citation_count = (
        session.query(Citation)
        .filter(Citation.document_id.in_(document_ids))
        .delete(synchronize_session=False)
    )
    chunk_count = (
        session.query(DocumentChunk)
        .filter(DocumentChunk.document_id.in_(document_ids))
        .delete(synchronize_session=False)
    )
    document_count = (
        session.query(Document)
        .filter(Document.id.in_(document_ids))
        .delete(synchronize_session=False)
    )
    session.flush()
    return {
        "cleanup_scope": _GRAPH_RUNTIME_CLEANUP_SCOPE,
        "retention_policy": _GRAPH_RUNTIME_RETENTION_POLICY,
        "document_count": int(document_count or 0),
        "chunk_count": int(chunk_count or 0),
        "citation_count": int(citation_count or 0),
    }


def _source_to_parsed_content(
    source: dict[str, Any],
    *,
    text: str,
    source_family: str,
) -> ParsedContent:
    source_id = str(source.get("source_id") or "").strip()
    title = str(source.get("title") or source_id)
    return ParsedContent(
        title=title,
        text=text,
        source_uri=str(source.get("url") or source_id),
        sections=[
            ParsedSection(
                section_name=title or "source",
                text=text,
                locator=str(source.get("url") or source_id),
            )
        ],
        publisher=str(source.get("domain") or "") or None,
        published_at=_parse_published_at(source.get("published_date")),
        language="zh",
        metadata={"source_id": source_id, "source_family": source_family},
    )


def _apply_focus_to_persistent_items(
    *,
    items: list[RetrievalChunkItem],
    query: str,
    plan: dict[str, Any],
    query_requirements: dict[str, Any],
    limit: int,
) -> list[RetrievalChunkItem]:
    dimension_entries = list(plan.get("dimension_plan", []))
    dimension_terms = _collect_dimension_terms(dimension_entries)
    dimension_families = _collect_dimension_families(dimension_entries)
    obligation_families = _collect_obligation_families(
        list(plan.get("source_obligations", []))
    )
    target_location = str(query_requirements.get("target_location") or "").strip()
    query_tokens = _tokenize(query)
    focused: list[RetrievalChunkItem] = []
    for item in items:
        metadata = dict(item.chunk_metadata or {})
        quality = metadata.get("chunk_quality", {})
        if isinstance(quality, dict) and quality.get("composite", 1.0) < 0.15:
            continue  # Skip low-quality chunks
        source_family = str(metadata.get("source_family") or "")
        text = item.chunk_text or ""
        title = item.document_title or ""
        section = item.section_name or ""
        breakdown = dict(item.score_breakdown or {})
        matched_dimensions: list[str] = []
        dimension_bonus = 0.0
        for dimension_id, terms in dimension_terms.items():
            term_score = _match_score(terms, f"{title} {section} {text}")
            family_bonus = (
                0.05
                if source_family and source_family in dimension_families.get(dimension_id, set())
                else 0.0
            )
            combined = min(0.18, term_score * 0.12 + family_bonus)
            if combined > 0:
                dimension_bonus += combined
                matched_dimensions.append(dimension_id)
        obligation_bonus = (
            0.07 if source_family and source_family in obligation_families else 0.0
        )
        location_bonus = 0.08 if target_location and target_location in f"{title} {text}" else 0.0
        query_focus_bonus = min(0.08, _match_score(query_tokens, f"{title} {text}") * 0.08)
        source_family_bonus = _SOURCE_FAMILY_BONUS.get(source_family, 0.0)
        breakdown.update(
            {
                "graph_query_focus_bonus": round(query_focus_bonus, 6),
                "dimension_bonus": round(dimension_bonus, 6),
                "obligation_bonus": round(obligation_bonus, 6),
                "location_bonus": round(location_bonus, 6),
                "source_family_bonus": round(source_family_bonus, 6),
            }
        )
        if matched_dimensions:
            metadata["matched_dimension_ids"] = matched_dimensions
        metadata["graph_retrieval_adapter"] = "persistent_document_chunk_v1"
        item.chunk_metadata = metadata
        item.score_breakdown = breakdown
        item.score = round(
            item.score
            + query_focus_bonus
            + dimension_bonus
            + obligation_bonus
            + location_bonus
            + source_family_bonus,
            6,
        )
        focused.append(item)
    focused.sort(
        key=lambda candidate: (
            -candidate.score,
            candidate.document_id,
            candidate.chunk_index,
        )
    )
    return focused[: max(1, limit)]


def _expand_persistent_context_items(
    *,
    session: Session,
    items: list[RetrievalChunkItem],
    limit: int,
) -> dict[str, Any]:
    if not items:
        return {
            "items": [],
            "audit": {
                "strategy": "parent_neighbor_v1",
                "hit_chunk_ids": [],
                "expanded_parent_chunk_ids": [],
                "expanded_neighbor_chunk_ids": [],
            },
        }

    seed_items = items[: max(1, limit)]
    seed_chunk_ids = [item.chunk_id for item in seed_items]
    seed_rows = session.scalars(
        select(DocumentChunk).where(DocumentChunk.id.in_(seed_chunk_ids))
    ).all()
    row_by_id = {row.id: row for row in seed_rows}

    expanded_parent_ids: list[int] = []
    expanded_neighbor_ids: list[int] = []
    expanded_chunk_ids: list[int] = []
    for item in seed_items:
        row = row_by_id.get(item.chunk_id)
        if row is None:
            continue
        expanded_chunk_ids.append(item.chunk_id)
        # ChunkDraft 重构后无 parent-child 层级：只展开同文档相邻 chunk 作为上下文。
        neighbor_rows = session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == row.document_id)
            .where(DocumentChunk.chunk_index.in_([row.chunk_index - 1, row.chunk_index + 1]))
        ).all()
        expanded_neighbor_ids.extend(neighbor.id for neighbor in neighbor_rows)

    unique_ids = []
    seen_ids: set[int] = set()
    for chunk_id in [*expanded_chunk_ids, *expanded_parent_ids, *expanded_neighbor_ids]:
        if chunk_id in seen_ids:
            continue
        unique_ids.append(chunk_id)
        seen_ids.add(chunk_id)

    all_rows = session.scalars(
        select(DocumentChunk).where(DocumentChunk.id.in_(unique_ids))
    ).all()
    ordered_items: list[RetrievalChunkItem] = []
    for seed_item in seed_items:
        row = row_by_id.get(seed_item.chunk_id)
        if row is None:
            continue
        ordered_items.append(seed_item)
        for neighbor_index in (row.chunk_index - 1, row.chunk_index + 1):
            neighbor_row = next(
                (
                    candidate
                    for candidate in all_rows
                    if candidate.document_id == row.document_id
                    and candidate.chunk_index == neighbor_index
                ),
                None,
            )
            if neighbor_row is None:
                continue
            ordered_items.append(
                _build_context_item_from_row(
                    session=session,
                    row=neighbor_row,
                    document_id=seed_item.document_id,
                    document_title=seed_item.document_title,
                    source_uri=seed_item.source_uri,
                    publisher=seed_item.publisher,
                    published_at=seed_item.published_at,
                    source_type=seed_item.source_type,
                    document_status=seed_item.document_status,
                    industry=seed_item.industry,
                    context_role="neighbor_context",
                )
            )

    deduped_items: list[RetrievalChunkItem] = []
    emitted_chunk_ids: set[int] = set()
    for item in ordered_items:
        if item.chunk_id in emitted_chunk_ids:
            continue
        emitted_chunk_ids.add(item.chunk_id)
        deduped_items.append(item)

    return {
        "items": deduped_items,
        "audit": {
            "strategy": "parent_neighbor_v1",
            "hit_chunk_ids": seed_chunk_ids,
            "expanded_parent_chunk_ids": sorted(set(expanded_parent_ids)),
            "expanded_neighbor_chunk_ids": sorted(set(expanded_neighbor_ids)),
        },
    }


def _build_context_item_from_row(
    *,
    session: Session,
    row: DocumentChunk,
    document_id: int,
    document_title: str,
    source_uri: str | None,
    publisher: str | None,
    published_at: datetime | None,
    source_type: str,
    document_status: str,
    industry: str | None,
    context_role: str,
) -> RetrievalChunkItem:
    citation = session.scalar(
        select(Citation)
        .where(Citation.chunk_id == row.id)
        .order_by(Citation.id.asc())
    )
    metadata = dict(row.metadata_json or {})
    metadata["context_role"] = context_role
    return RetrievalChunkItem(
        chunk_id=row.id,
        document_id=document_id,
        chunk_index=row.chunk_index,
        section_name=row.section_name,
        chunk_text=row.text,
        chunk_metadata=metadata,
        citation_locator=citation.locator if citation else None,
        citation_quote=citation.quote_text if citation else None,
        document_title=document_title,
        source_uri=source_uri,
        publisher=publisher,
        published_at=published_at,
        source_type=source_type,
        document_status=document_status,
        industry=industry,
        score=0.0,
        score_breakdown={"context_expansion_bonus": 0.0},
    )


def _retrieval_pack_payload(
    *,
    retrieval_response: RetrievalResponse,
    plan: dict[str, Any],
    adapter_status: str,
    persisted_document_ids: list[int],
    backend_retrieval_mode: str,
    adapter_notes: list[str],
) -> dict[str, Any]:
    return {
        "query": retrieval_response.query,
        "retrieval_mode": retrieval_response.retrieval_mode,
        "filters": retrieval_response.filters.to_dict(),
        "total_candidates": retrieval_response.total_candidates,
        "returned_count": len(retrieval_response.items),
        "notes": [*retrieval_response.notes, *adapter_notes],
        "audit": dict(retrieval_response.audit or {}),
        "items": [item.to_dict() for item in retrieval_response.items],
        "dimension_focus": _dimension_focus_summary(plan),
        "obligation_focus": _obligation_focus_summary(plan),
        "adapter_status": adapter_status,
        "persisted_document_ids": persisted_document_ids,
        "backend_retrieval_mode": backend_retrieval_mode,
        "retention_policy": _GRAPH_RUNTIME_RETENTION_POLICY,
        "cleanup_scope": _GRAPH_RUNTIME_CLEANUP_SCOPE,
    }



def _rank_source_chunks(
    *,
    query: str,
    chunks: list[dict[str, Any]],
    dimension_terms: dict[str, list[str]],
    dimension_families: dict[str, set[str]],
    obligation_families: set[str],
    target_location: str,
    limit: int,
) -> list[RetrievalChunkItem]:
    query_tokens = _tokenize(query)
    ranked: list[tuple[float, dict[str, Any], dict[str, float], list[str]]] = []
    for chunk in chunks:
        text = str(chunk.get("chunk_text") or "")
        title = str(chunk.get("document_title") or "")
        section = str(chunk.get("section_name") or "")
        source_family = str(chunk.get("source_family") or "")
        lexical = _match_score(query_tokens, text)
        title_bonus = min(0.18, _match_score(query_tokens, title) * 0.18)
        section_bonus = min(0.08, _match_score(query_tokens, section) * 0.12)

        dimension_bonus = 0.0
        matched_dimensions: list[str] = []
        for dimension_id, terms in dimension_terms.items():
            term_score = _match_score(terms, f"{title} {section} {text}")
            family_bonus = (
                0.05
                if source_family and source_family in dimension_families.get(dimension_id, set())
                else 0.0
            )
            combined = min(0.18, term_score * 0.12 + family_bonus)
            if combined > 0:
                dimension_bonus += combined
                matched_dimensions.append(dimension_id)

        obligation_bonus = (
            0.07 if source_family and source_family in obligation_families else 0.0
        )
        location_bonus = 0.0
        if target_location:
            location_bonus = 0.08 if target_location in f"{title} {text}" else 0.0

        source_quality_bonus = _SOURCE_FAMILY_BONUS.get(source_family, 0.0)
        total = round(
            lexical
            + title_bonus
            + section_bonus
            + dimension_bonus
            + obligation_bonus
            + location_bonus
            + source_quality_bonus,
            6,
        )
        if total <= 0:
            continue
        ranked.append(
            (
                total,
                chunk,
                {
                    "lexical": round(lexical, 6),
                    "title_bonus": round(title_bonus, 6),
                    "section_bonus": round(section_bonus, 6),
                    "dimension_bonus": round(dimension_bonus, 6),
                    "obligation_bonus": round(obligation_bonus, 6),
                    "location_bonus": round(location_bonus, 6),
                    "source_family_bonus": round(source_quality_bonus, 6),
                },
                matched_dimensions,
            )
        )
    ranked.sort(
        key=lambda item: (
            -item[0],
            item[1].get("source_id", ""),
            item[1].get("chunk_index", 0),
        )
    )
    items: list[RetrievalChunkItem] = []
    for total, chunk, breakdown, matched_dimensions in ranked[: max(1, limit)]:
        item = RetrievalChunkItem(
            chunk_id=10_000_000 + len(items) + 1,
            document_id=20_000_000 + len(items) + 1,
            chunk_index=int(chunk.get("chunk_index") or 0),
            section_name=str(chunk.get("section_name") or "") or None,
            chunk_text=str(chunk.get("chunk_text") or ""),
            chunk_metadata=dict(chunk.get("chunk_metadata") or {}),
            citation_locator=str(chunk.get("citation_locator") or "") or None,
            citation_quote=str(chunk.get("chunk_text") or "")[:280] or None,
            document_title=str(chunk.get("document_title") or ""),
            source_uri=str(chunk.get("source_uri") or "") or None,
            publisher=str(chunk.get("publisher") or "") or None,
            published_at=_parse_published_at(chunk.get("published_at")),
            source_type=str(chunk.get("source_type") or "other"),
            document_status=str(chunk.get("document_status") or "graph_runtime_source"),
            industry=None,
            score=total,
            score_breakdown=breakdown,
        )
        if matched_dimensions:
            metadata = dict(item.chunk_metadata or {})
            metadata["matched_dimension_ids"] = matched_dimensions
            item.chunk_metadata = metadata
        items.append(item)
    return items


def _collect_dimension_terms(
    dimension_entries: list[dict[str, Any]],
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for entry in dimension_entries:
        dimension_id = str(entry.get("dimension_id") or "").strip()
        if not dimension_id:
            continue
        terms = [
            str(term).strip()
            for term in list(entry.get("caliber_terms", []))
            if str(term).strip()
        ]
        question = str(entry.get("research_question") or "").strip()
        if question:
            terms.extend(_tokenize(question))
        result[dimension_id] = _dedupe_terms(terms)
    return result


def _collect_dimension_families(
    dimension_entries: list[dict[str, Any]],
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for entry in dimension_entries:
        dimension_id = str(entry.get("dimension_id") or "").strip()
        if not dimension_id:
            continue
        result[dimension_id] = {
            str(family).strip()
            for family in list(entry.get("source_families", []))
            if str(family).strip()
        }
    return result


def _collect_obligation_families(obligation_entries: list[dict[str, Any]]) -> set[str]:
    return {
        str(entry.get("source_family") or "").strip()
        for entry in obligation_entries
        if str(entry.get("source_family") or "").strip()
    }


def _dimension_focus_summary(plan: dict[str, Any]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for entry in list(plan.get("dimension_plan", []))[:12]:
        summary.append(
            {
                "dimension_id": entry.get("dimension_id"),
                "dimension_type": entry.get("dimension_type"),
                "expected_section_heading": entry.get("expected_section_heading"),
                "source_families": list(entry.get("source_families", [])),
                "caliber_terms": list(entry.get("caliber_terms", []))[:6],
            }
        )
    return summary


def _obligation_focus_summary(plan: dict[str, Any]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for entry in list(plan.get("source_obligations", []))[:12]:
        summary.append(
            {
                "obligation_id": entry.get("obligation_id"),
                "source_family": entry.get("source_family"),
                "required_for": entry.get("required_for"),
                "min_required_evidence": entry.get("min_required_evidence"),
            }
        )
    return summary


def _match_score(tokens: list[str], text: str) -> float:
    haystack = text.lower()
    if not tokens:
        return 0.0
    total = 0.0
    for token in tokens:
        if token.lower() in haystack:
            total += 1.0
    return total / float(len(tokens))


def _tokenize(query: str) -> list[str]:
    normalized = str(query or "").strip().lower()
    if not normalized:
        return []
    tokens: list[str] = []
    for piece in (
        normalized.replace("/", " ")
        .replace(",", " ")
        .replace("，", " ")
        .replace("。", " ")
        .replace("：", " ")
        .split()
    ):
        item = piece.strip()
        if item and item not in tokens:
            tokens.append(item)
    return tokens


def _dedupe_terms(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def _citation_locator(source: dict[str, Any], chunk_index: int) -> str:
    url = str(source.get("url") or source.get("source_id") or "source")
    return f"{url} | chunk:{chunk_index}"


def _parse_published_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
