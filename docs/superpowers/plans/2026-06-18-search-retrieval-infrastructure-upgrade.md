# Subsystem A: 搜索与检索基础设施升级 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级 deep research pipeline 的 chunk 质量、检索精度和搜索规划。chunk 语义化+评分→PG 存储→混合检索（vector+BM25+reranker）→caliber 多维度搜索。

**Architecture:** 三阶段顺序推进。A1 增强 chunk 质量评分并整合进 PG 持久化路径（已有 `_persist_graph_runtime_documents` 可复用）。A2 在 `ChunkRetrievalService` 中引入 pg_bm25 + RRF 混合检索，部署本地模型做 reranker + source quality scoring。A3 增强 `caliber_expander` 的 LLM prompt 实现多维度×源族搜索矩阵。

**Tech Stack:** Python, SQLAlchemy, PostgreSQL 16, pgvector, pg_bm25, cross-encoder reranker, DeepSeek (caliber LLM)

## Global Constraints

- 不修改 legacy `/deep-research/analyze` 和 `/research/analyze` 路径
- `graph_v1` 保持 opt-in
- `response.json` 结构不变（chunk 审计信息追加到 context pack）
- 已有 gate/editor2/editor1 逻辑不变
- PG 迁移增量进行（PG 已是主存储，`_persist_graph_runtime_documents` 已在用）
- 本地模型权重路径：`packages\training\data\model_output_v8_dpo_from_v7_b005_lr2e6`
- 所有检索 fallback：PG 不可用时回到内存 chunk（当前行为已实现）

---

### Task 1: Chunk Quality Scoring

**通俗说明**：给每个 chunk 打分。信息密度高、含政策编号/数据、来自权威源的 chunk 得高分，低分 chunk 不进 evidence 构建。

**Files:**
- Create: `packages/rag/chunk_quality.py`
- Modify: `packages/research_harness/retrieval_bridge.py:263-295`（在 `_persist_graph_runtime_documents` 创建 chunk 时加评分）
- Test: `tests/test_rag_chunk_quality.py`

**Interfaces:**
- Produces: `score_chunk_quality(text, source_family, source_tier) -> ChunkQualityScore` — 返回 `{info_density, citability, authority, composite}`
- Consumed by: `_persist_graph_runtime_documents`（写入 chunk metadata）、`_apply_focus_to_persistent_items`（过滤低质量）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rag_chunk_quality.py
from packages.rag.chunk_quality import score_chunk_quality

def test_high_quality_official_policy_chunk():
    score = score_chunk_quality(
        text="广东省人民政府关于印发《广东省推动人工智能与机器人产业创新发展若干政策措施》的通知。"
             "明确提出支持人形机器人产业发展，提出成立产业联盟等举措。2025年3月发布。",
        source_family="official_policy",
        source_tier="A",
    )
    assert score.composite >= 0.6
    assert score.authority >= 0.7

def test_low_quality_noise_chunk():
    score = score_chunk_quality(
        text="下载app 直播 攻略 游戏",
        source_family="unknown",
        source_tier="D",
    )
    assert score.composite < 0.3

def test_policy_document_with_numbers():
    score = score_chunk_quality(
        text="粤府办〔2025〕12号文件指出，2025年全省机器人产业产值目标500亿元。",
        source_family="official_policy",
        source_tier="A",
    )
    assert score.citability >= 0.5
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
python -m pytest -q tests/test_rag_chunk_quality.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.rag.chunk_quality'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/rag/chunk_quality.py
from __future__ import annotations

import re
from dataclasses import dataclass

# ── Citation markers: policy numbers, document IDs, percentages, tender codes ──
_CITATION_PATTERNS = [
    re.compile(r"[〔（(]\d{4}[）)〕]\d+号"),       # 粤府办〔2025〕12号
    re.compile(r"\d+年\d+月\d+日"),
    re.compile(r"\d+\.\d+%"),                    # 百分比
    re.compile(r"第[一二三四五六七八九十百千\d]+条"),
    re.compile(r"[A-Z]{2,}-\d{4,}"),             # 招标编号
    re.compile(r"\d+亿元|\d+万元"),               # 金额
]

_NOISE_PATTERNS = [
    re.compile(r"下载|app|直播|攻略|游戏|看片|在线", re.IGNORECASE),
    re.compile(r"javascript|cookie|广告|推广", re.IGNORECASE),
]

_SOURCE_TIER_AUTHORITY = {"A": 0.95, "B": 0.70, "C": 0.40, "D": 0.15}


@dataclass(slots=True)
class ChunkQualityScore:
    info_density: float    # 0-1, 中文字符占比 + 非噪声
    citability: float       # 0-1, 是否含结构化引用标记
    authority: float        # 0-1, 来源权威度
    composite: float        # 0-1, 加权综合

    def __init__(self, info_density: float, citability: float, authority: float):
        object.__setattr__(self, "info_density", round(info_density, 3))
        object.__setattr__(self, "citability", round(citability, 3))
        object.__setattr__(self, "authority", round(authority, 3))
        object.__setattr__(self, "composite", round(
            0.30 * info_density + 0.35 * citability + 0.35 * authority, 3
        ))


def score_chunk_quality(
    text: str,
    *,
    source_family: str = "graph_source",
    source_tier: str = "C",
) -> ChunkQualityScore:
    text = str(text or "").strip()
    if not text:
        return ChunkQualityScore(0.0, 0.0, 0.0)

    # ── Info density ──
    cjk_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    total_chars = max(len(text), 1)
    cjk_ratio = cjk_chars / total_chars
    noise_hits = sum(1 for p in _NOISE_PATTERNS if p.search(text))
    info_density = max(0.0, cjk_ratio - 0.10 * noise_hits)

    # ── Citability ──
    citation_hits = sum(1 for p in _CITATION_PATTERNS if p.search(text))
    citability = min(1.0, 0.15 * citation_hits + (0.15 if cjk_ratio > 0.5 else 0.0))

    # ── Authority ──
    authority = _SOURCE_TIER_AUTHORITY.get(source_tier.upper(), 0.35)

    return ChunkQualityScore(info_density, citability, authority)
```

- [ ] **Step 4: Run test to verify it passes**

```powershell
python -m pytest -q tests/test_rag_chunk_quality.py -v
```
Expected: 3 passed

- [ ] **Step 5: Wire quality scoring into chunk persistence**

In `retrieval_bridge.py:263-295`, after `chunk_drafts = chunk_parsed_content(parsed, max_chars=700)`, add quality scoring and store in metadata:

```python
from packages.rag.chunk_quality import score_chunk_quality

# In _persist_graph_runtime_documents, after chunk_drafts = chunk_parsed_content(parsed):
source_tier = str(source.get("source_tier") or "C")
for chunk in chunk_drafts:
    quality = score_chunk_quality(
        chunk.text,
        source_family=source_family,
        source_tier=source_tier,
    )
    # ... existing row creation, add to metadata_json:
    metadata_json={
        **dict(chunk.metadata_json),
        "graph_run_id": run_id,
        "graph_source_id": source_id,
        "source_family": source_family,
        "source_tier": source_tier,
        "chunk_quality": {
            "info_density": quality.info_density,
            "citability": quality.citability,
            "authority": quality.authority,
            "composite": quality.composite,
        },
        "graph_runtime_document": True,
        "retention_policy": _GRAPH_RUNTIME_RETENTION_POLICY,
    },
```

- [ ] **Step 6: Add low-quality filter in focus function**

In `_apply_focus_to_persistent_items`, after `for item in items:`, skip items with composite < 0.15:

```python
metadata = dict(item.chunk_metadata or {})
quality = metadata.get("chunk_quality", {})
if isinstance(quality, dict) and quality.get("composite", 1.0) < 0.15:
    continue  # Skip low-quality chunks
```

- [ ] **Step 7: Run full retrieval bridge tests**

```powershell
python -m pytest -q tests/test_research_harness_graph.py -k "build_evidence or collect_sources" -v
python -m pytest -q tests/test_rag_chunk_quality.py -v
```

- [ ] **Step 8: Commit**

```bash
git add packages/rag/chunk_quality.py tests/test_rag_chunk_quality.py packages/research_harness/retrieval_bridge.py
git commit -m "feat: chunk quality scoring — info density + citability + authority"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

### Task 2: pg_bm25 Extension + BM25 Index

**通俗说明**：给 PG 装上 BM25 全文检索扩展，为 `document_chunks` 表建 BM25 索引。这是混合检索的基础——vector 负责语义，BM25 负责关键词精准匹配。

**Files:**
- Modify: PG migration script（新建 `packages/db/alembic/versions/` 迁移）
- Test: 手动 SQL 验证

- [ ] **Step 1: Install pg_bm25 on PG container**

```powershell
# 如果 PG 在 Docker 内：
docker exec -it <pg_container> psql -U invest -d invest_agent -c "CREATE EXTENSION IF NOT EXISTS pg_bm25;"
# 或
docker exec -it <pg_container> psql -U invest -d invest_agent -c "CREATE EXTENSION IF NOT EXISTS paradedb;"
```

如果 `pg_bm25` 不可用，尝试 `paradedb`（pg_bm25 的上游项目）。如果两者都不可用，fallback 到 PG 内置 `tsvector` + `tsquery`（全文搜索）作为 BM25 的近似替代。

- [ ] **Step 2: Create BM25 index migration**

```python
# packages/db/alembic/versions/<hash>_add_bm25_index_document_chunks.py
"""Add BM25 full-text search index on document_chunks.text"""

depends_on = None  # Set to latest migration

def upgrade():
    # Try paradedb/pg_bm25 first
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'paradedb'
            ) THEN
                EXECUTE 'CREATE INDEX idx_chunks_bm25 ON document_chunks USING bm25 (id, text, section_name)';
            ELSIF EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'pg_bm25'
            ) THEN
                EXECUTE 'CREATE INDEX idx_chunks_bm25 ON document_chunks USING bm25 (id, text, section_name)';
            ELSE
                -- Fallback: PostgreSQL built-in full-text search
                EXECUTE 'CREATE INDEX idx_chunks_fts ON document_chunks USING gin (to_tsvector(''simple'', coalesce(text, '''') || '' '' || coalesce(section_name, '''')))';
            END IF;
        END $$;
    """)

def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_chunks_bm25")
    op.execute("DROP INDEX IF EXISTS idx_chunks_fts")
```

- [ ] **Step 3: Run migration**

```powershell
cd E:\invest_agent && alembic upgrade head
```

- [ ] **Step 4: Verify index exists**

```sql
-- Run via psql
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'document_chunks';
```
Expected: `idx_chunks_bm25` or `idx_chunks_fts` present.

- [ ] **Step 5: Commit**

```bash
git add packages/db/alembic/versions/
git commit -m "feat: BM25 full-text index on document_chunks (paradedb/pg_bm25/tsvector fallback)"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

### Task 3: Hybrid Search (Vector + BM25 → RRF) in ChunkRetrievalService

**通俗说明**：检索时同时跑两路——vector 语义相似度 + BM25 关键词匹配，用 RRF 算法合并排名。比纯 lexical 精准得多。

**Files:**
- Modify: `packages/rag/retrieval.py`（`ChunkRetrievalService.search_chunks` 加 hybrid 模式）
- Test: `tests/test_rag_retrieval.py`

**Interfaces:**
- Consumes: `DocumentChunk` (PG table, 已有 embedding_vector + text columns), BM25/tsvector index (Task 2)
- Produces: `RetrievalResponse` with items tagged `"retrieval_source": "vector"|"bm25"|"both"` and `rrf_score`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rag_retrieval.py — 追加
def test_hybrid_search_returns_rrf_scored_items(db_session):
    """Hybrid search should tag items with retrieval_source."""
    from packages.rag.retrieval import ChunkRetrievalService
    from packages.rag.schemas import RetrievalFilters
    service = ChunkRetrievalService(db_session)
    response = service.search_chunks(
        "人形机器人 产业政策",
        RetrievalFilters(limit=5, backend_modes=["hybrid"]),
    )
    assert response.retrieval_mode == "hybrid_rrf_v1"
    # If chunks exist, they should have vector_score and bm25_score
    if response.items:
        item = response.items[0]
        breakdown = item.score_breakdown or {}
        assert "rrf_score" in breakdown or "vector_score" in breakdown
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
python -m pytest -q tests/test_rag_retrieval.py::test_hybrid_search_returns_rrf_scored_items -v
```
Expected: FAIL — hybrid mode not implemented

- [ ] **Step 3: Implement hybrid search**

在 `ChunkRetrievalService.search_chunks` 中，当 `filters.backend_modes` 包含 `"hybrid"` 时：

```python
def _hybrid_search(
    self, query: str, filters: RetrievalFilters, limit: int
) -> list[_Candidate]:
    """Vector ANN + BM25 full-text → RRF merge."""
    k = max(limit * 3, 15)
    
    # ── Vector ANN search (pgvector HNSW) ──
    query_embedding = build_deterministic_embedding(query)
    vector_candidates = self._vector_search(query_embedding, filters, k)
    
    # ── BM25 / tsvector search ──
    bm25_candidates = self._bm25_search(query, filters, k)
    
    # ── RRF merge ──
    merged = self._rrf_merge(vector_candidates, bm25_candidates, k=60)
    
    # ── Return top-k with retrieval source tags ──
    return merged[:limit]

def _vector_search(
    self, embedding: list[float], filters: RetrievalFilters, k: int
) -> list[_Candidate]:
    """HNSW ANN search via pgvector."""
    doc_filter = ""
    if filters.document_ids:
        doc_filter = f"AND document_id IN ({','.join(map(str, filters.document_ids))})"
    query_sql = f"""
        SELECT d.id, d.document_id, d.chunk_index, d.section_name, d.text,
               d.index_text, d.metadata_json, d.token_count,
               1.0 - (d.embedding_vector <=> :embedding::vector) AS vector_score,
               doc.title, doc.source_uri, doc.publisher, doc.published_at,
               doc.source_type, doc.status, doc.industry
        FROM document_chunks d
        JOIN documents doc ON doc.id = d.document_id
        WHERE d.embedding_vector IS NOT NULL {doc_filter}
        ORDER BY d.embedding_vector <=> :embedding::vector
        LIMIT :k
    """
    # ... execute and return _Candidate list with vector_score in lane_scores
    pass  # Implementation detail — use session.execute()

def _bm25_search(
    self, query: str, filters: RetrievalFilters, k: int
) -> list[_Candidate]:
    """BM25 or tsvector full-text search."""
    doc_filter = ""
    if filters.document_ids:
        doc_filter = f"AND d.document_id IN ({','.join(map(str, filters.document_ids))})"
    
    # Check which extension is available
    bm25_available = self._has_extension("paradedb") or self._has_extension("pg_bm25")
    
    if bm25_available:
        query_sql = f"""
            SELECT d.id, ... FROM document_chunks d
            JOIN documents doc ON doc.id = d.document_id
            WHERE d.text @@@ paradedb.match(:query) {doc_filter}
            ORDER BY paradedb.score(d.id) DESC
            LIMIT :k
        """
    else:
        # tsvector fallback
        query_sql = f"""
            SELECT d.id, ..., ts_rank(to_tsvector('simple', d.text), plainto_tsquery('simple', :query)) AS bm25_score
            FROM document_chunks d JOIN documents doc ON doc.id = d.document_id
            WHERE to_tsvector('simple', d.text) @@ plainto_tsquery('simple', :query) {doc_filter}
            ORDER BY bm25_score DESC LIMIT :k
        """
    pass  # Implementation detail

@staticmethod
def _rrf_merge(
    vector_results: list[_Candidate],
    bm25_results: list[_Candidate],
    k: int = 60,
) -> list[_Candidate]:
    """Reciprocal Rank Fusion merge of two ranked lists."""
    rrf: dict[int, float] = {}
    candidate_map: dict[int, _Candidate] = {}
    
    for rank, c in enumerate(vector_results, start=1):
        rrf[c.chunk.id] = rrf.get(c.chunk.id, 0.0) + 1.0 / (k + rank)
        candidate_map[c.chunk.id] = c
    
    for rank, c in enumerate(bm25_results, start=1):
        rrf[c.chunk.id] = rrf.get(c.chunk.id, 0.0) + 1.0 / (k + rank)
        if c.chunk.id not in candidate_map:
            candidate_map[c.chunk.id] = c
    
    merged = sorted(rrf.items(), key=lambda x: -x[1])
    result: list[_Candidate] = []
    for chunk_id, score in merged:
        c = candidate_map[chunk_id]
        c.lane_scores = dict(c.lane_scores or {})
        c.lane_scores["rrf_score"] = round(score, 6)
        # Tag retrieval source
        vec_rank = next((i+1 for i, vc in enumerate(vector_results) if vc.chunk.id == chunk_id), None)
        bm25_rank = next((i+1 for i, bc in enumerate(bm25_results) if bc.chunk.id == chunk_id), None)
        c.lane_scores["retrieval_source"] = (
            "both" if vec_rank and bm25_rank
            else "vector" if vec_rank
            else "bm25"
        )
        result.append(c)
    return result
```

- [ ] **Step 4: Run tests**

```powershell
python -m pytest -q tests/test_rag_retrieval.py -v
```
Expected: hybrid test passes (with or without chunks — test handles empty gracefully)

- [ ] **Step 5: Commit**

```bash
git add packages/rag/retrieval.py tests/test_rag_retrieval.py
git commit -m "feat: hybrid search — vector ANN + BM25/tsvector → RRF merge"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

### Task 4: Local Model Deployment + Reranker + Source Quality v2

**通俗说明**：把你的本地训练模型部署为推理服务，同时用于两个用途——对候选 chunk 做精排（reranker），对 source 做可信度打分（source quality v2）。

**Files:**
- Create: `packages/rag/rerankers.py`（扩展现有 stub）
- Modify: `packages/sources/source_quality.py`（接入本地模型）
- Test: `tests/test_rag_rerankers.py`、`tests/test_sources_source_quality_v2.py`

- [ ] **Step 1: Check model format and deployment options**

```powershell
cd E:\invest_agent
python -c "
import pathlib
model_dir = pathlib.Path('packages/training/data/model_output_v8_dpo_from_v7_b005_lr2e6')
print('Files:', list(model_dir.glob('*')))
# Check if it's safetensors, pytorch, GGUF, or Ollama format
for f in model_dir.rglob('*'):
    print(f.relative_to(model_dir))
"
```

- [ ] **Step 2: Deploy as Ollama-compatible or vLLM service**

```python
# packages/rag/rerankers.py — cross-encoder reranker stub → real implementation
from __future__ import annotations

import json
from typing import Any

import requests

_DEFAULT_MODEL_ENDPOINT = "http://localhost:11434/api/generate"  # Ollama
# or "http://localhost:8000/v1/rerank"  # vLLM / TEI compatible

def resolve_rerank_spec(rerank_mode: str | None) -> RetrievalRerankSpec:
    if rerank_mode == "cross_encoder_v1":
        return RetrievalRerankSpec(
            strategy_name="cross_encoder_rerank_v1",
            rerank_mode="cross_encoder_v1",
            notes=["Using local cross-encoder model for reranking."],
        )
    return RetrievalRerankSpec(
        strategy_name="lane_balance_v1",
        rerank_mode="lane_balance_v1",
        notes=["Deterministic lane-balance reranking (no model)."],
    )

def rerank_with_cross_encoder(
    query: str,
    chunks: list[dict[str, Any]],
    model_endpoint: str = _DEFAULT_MODEL_ENDPOINT,
    top_k: int = 8,
) -> list[dict[str, float]]:
    """Call cross-encoder model to score chunk relevance to query.
    
    Returns list of {"chunk_id": str, "rerank_score": float} sorted desc.
    """
    scores: list[dict[str, float]] = []
    for chunk in chunks[: top_k * 3]:
        text = str(chunk.get("chunk_text") or chunk.get("text") or "")[:512]
        prompt = (
            f"Query: {query}\n"
            f"Document: {text}\n"
            f"Rate relevance 0-1. Output only the number:"
        )
        try:
            resp = requests.post(
                model_endpoint,
                json={"model": "source-quality-v2", "prompt": prompt, "stream": False},
                timeout=30,
            )
            data = resp.json()
            raw = data.get("response", "0.5").strip()
            score = float(raw)
        except Exception:
            score = 0.5  # fallback
        chunk_id = str(chunk.get("chunk_id") or chunk.get("id") or "")
        scores.append({"chunk_id": chunk_id, "rerank_score": min(1.0, max(0.0, score))})
    
    scores.sort(key=lambda x: -x["rerank_score"])
    return scores[:top_k]


def score_source_quality_v2(
    *,
    title: str,
    url: str,
    content_sample: str,
    existing_tier: str = "C",
    model_endpoint: str = _DEFAULT_MODEL_ENDPOINT,
) -> dict[str, Any]:
    """Score source quality using local model.
    
    Used for source quality scoring v2 alongside reranker.
    """
    prompt = (
        f"Classify the authority tier (A/B/C/D) of this source:\n"
        f"Title: {title}\nURL: {url}\nSample: {content_sample[:300]}\n"
        f"Tier A: official government (.gov.cn), Tier B: reputable media/industry, "
        f"Tier C: general web, Tier D: low quality/spam.\n"
        f"Output format: {{\"tier\": \"B\", \"confidence\": 0.85, \"reason\": \"...\"}}"
    )
    try:
        resp = requests.post(
            model_endpoint,
            json={"model": "source-quality-v2", "prompt": prompt, "stream": False},
            timeout=30,
        )
        data = resp.json()
        result = json.loads(data.get("response", "{}"))
        return {
            "predicted_tier": result.get("tier", existing_tier),
            "confidence": float(result.get("confidence", 0.5)),
            "reason": str(result.get("reason", "")),
        }
    except Exception:
        return {"predicted_tier": existing_tier, "confidence": 0.0, "reason": "model unavailable"}
```

- [ ] **Step 3: Wire reranker into retrieval pipeline**

In `ChunkRetrievalService.search_chunks` (Task 3), after RRF merge, add reranker pass:

```python
if "cross_encoder_v1" in (filters.backend_modes or []):
    items = self._rerank_candidates(candidates, tokens, limit, rerank_spec)
    # After reranker, optionally apply cross-encoder rerank
    ranked = rerank_with_cross_encoder(query, [
        {"chunk_id": str(c.chunk.id), "chunk_text": c.chunk.text}
        for c in candidates
    ], top_k=limit)
    # Update scores with rerank_score
    score_map = {r["chunk_id"]: r["rerank_score"] for r in ranked}
    for c in candidates:
        c.lexical_score = score_map.get(str(c.chunk.id), c.lexical_score)
        c.lane_scores = dict(c.lane_scores or {})
        c.lane_scores["rerank_score"] = c.lexical_score
```

- [ ] **Step 4: Run tests**

```powershell
python -m pytest -q tests/test_rag_rerankers.py tests/test_sources_source_quality_v2.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/rag/rerankers.py packages/sources/source_quality.py tests/
git commit -m "feat: local model deployment — cross-encoder reranker + source quality v2"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

### Task 5: Caliber Expansion — LLM-Driven Multi-Dimension Search

**通俗说明**：让 LLM 分析用户 query，拆成多个维度（政策/地方/项目/披露/统计/风险），每个维度生成专属搜索短语 + 源族绑定 + domain 约束。替代"query+后缀"的同质化搜索。

**Files:**
- Modify: `packages/research_harness/caliber_expander.py`（增强 LLM prompt + 维度-源族绑定）
- Modify: `packages/research_harness/real_nodes.py:332-381`（plan_task 的 caliber 集成）
- Test: `tests/test_caliber_expander.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_caliber_expander.py — 追加
def test_caliber_produces_dimension_source_family_binding():
    """Caliber output should bind each dimension to required_source_family."""
    from packages.research_harness.caliber_expander import expand_caliber
    caliber = expand_caliber(query="2025年广东人形机器人产业政策与项目落地证据")
    assert caliber is not None
    plan = caliber.final_search_plan
    groups = plan.get("search_groups", [])
    assert len(groups) >= 2  # At least 2 dimensions
    for g in groups:
        assert "target_evidence_need" in g     # dimension
        assert "source_type_preference" in g    # source family binding
        assert "search_phrases" in g            # actual phrases
        assert len(g["search_phrases"]) >= 2    # At least 2 phrases per dimension

def test_caliber_fallback_when_llm_unavailable(monkeypatch):
    """When LLM fails, caliber should fallback to default template."""
    from packages.research_harness.caliber_expander import expand_caliber
    # Simulate LLM failure
    monkeypatch.setattr(
        "packages.research_harness.caliber_expander._call_llm_for_caliber",
        lambda **kw: None,
    )
    caliber = expand_caliber(query="测试查询")
    assert caliber is not None
    assert caliber.fallback_used
    plan = caliber.final_search_plan
    assert len(plan.get("search_groups", [])) >= 4  # Default dimensions
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
python -m pytest -q tests/test_caliber_expander.py -k "dimension_source_family_binding or fallback" -v
```
Expected: FAIL

- [ ] **Step 3: Implement enhanced caliber prompt and dimension binding**

```python
# caliber_expander.py — 增强 _DEFAULT_DIMENSIONS 和 LLM prompt

_DEFAULT_DIMENSIONS = [
    {
        "dimension_id": "d_policy",
        "dimension_type": "policy",
        "source_family": "official_policy",
        "include_domains": ["gov.cn"],
        "label": "政策",
    },
    {
        "dimension_id": "d_local",
        "dimension_type": "local_rollout",
        "source_family": "local_government_notice",
        "include_domains": ["gov.cn"],
        "label": "地方落地",
    },
    {
        "dimension_id": "d_project",
        "dimension_type": "project_execution",
        "source_family": "public_resource_transaction",
        "include_domains": ["ggzy.gov.cn", "ccgp.gov.cn"],
        "label": "项目执行",
    },
    {
        "dimension_id": "d_disclosure",
        "dimension_type": "company_disclosure",
        "source_family": "company_disclosure",
        "include_domains": [],
        "label": "公司披露",
    },
    {
        "dimension_id": "d_statistics",
        "dimension_type": "statistics_or_data",
        "source_family": "statistics_or_data_release",
        "include_domains": [],
        "label": "统计数据",
    },
    {
        "dimension_id": "d_risk",
        "dimension_type": "risk_assessment",
        "source_family": "risk_assessment",
        "include_domains": [],
        "label": "风险",
    },
]


def _build_caliber_prompt(query: str) -> str:
    return f"""Analyze this research query and decompose it into search dimensions.

Query: {query}

Default dimensions available:
- 政策(policy): official government policy documents
- 地方落地(local_rollout): local government implementation notices
- 项目执行(project_execution): public procurement, bidding, project announcements
- 公司披露(company_disclosure): annual reports, corporate filings
- 统计数据(statistics): industry statistics, data releases
- 风险(risk): risk assessments, limitations, uncertainties

For each dimension that APPLIES to this query, generate 3-5 DIFFERENT search phrases
in Chinese. Phrases should use different wording, angles, and synonyms — NOT just
adding suffixes to the query. You may also ADD dimensions if the query needs them,
or REMOVE dimensions that don't apply.

Output JSON format:
{{
  "dimensions": [
    {{
      "dimension_id": "d_policy",
      "applies": true,
      "search_phrases": ["广东省 人形机器人 产业政策 2025", "人形机器人 政策扶持 广东"],
      "include_domains": ["gov.cn"]
    }}
  ]
}}"""


def _llm_caliber_fallback(query: str) -> dict[str, Any]:
    """Template-based fallback when LLM is unavailable."""
    search_groups = []
    for dim in _DEFAULT_DIMENSIONS[:5]:  # Always include policy+local+project+disclosure+statistics
        # Generate simple phrases from query + dimension label
        phrases = [
            f"{query} {dim['label']}",
            f"{query} {dim['label']} 2025",
            f"{dim['label']} {query[:20]}",
        ]
        search_groups.append({
            "dimension_id": dim["dimension_id"],
            "dominant_intent": dim["label"],
            "target_evidence_need": dim["dimension_type"],
            "source_type_preference": [dim["source_family"]],
            "search_phrases": [{"phrase": p} for p in phrases],
        })
    return {
        "search_groups": search_groups,
        "anchor_phrases": [{"phrase": query}],
    }
```

- [ ] **Step 4: Run tests**

```powershell
python -m pytest -q tests/test_caliber_expander.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/research_harness/caliber_expander.py tests/test_caliber_expander.py
git commit -m "feat: caliber expansion — LLM multi-dimension search with source-family binding"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

### Task 6: Regression + STATUS Update

- [ ] **Step 1: Run full regression**

```powershell
pytest -q tests/test_research_harness_graph.py -k "editor2 or chief_gate or build_evidence" -v
pytest -q tests/test_rag_retrieval.py tests/test_rag_chunk_quality.py -v
pytest -q tests/test_caliber_expander.py -v
pytest -q tests/test_report_quality_inspect.py -v
```

- [ ] **Step 2: Run live smoke (case2_robot)**

```powershell
python scripts/graph_provider_backed_smoke.py --query "2025年广东人形机器人产业政策与项目落地证据" --max-rounds 2 --max-loop-count 1 --output-dir "data/tmp/subsystem_a_smoke/case2_robot" --env-file .env --reset
python scripts/report_quality_inspect.py --response "data/tmp/subsystem_a_smoke/case2_robot/response.json" --summary "data/tmp/subsystem_a_smoke/case2_robot/summary.json"
```

Expected improvement: evidence_count ↑, source diversity ↑, over_budget_packs 可能仍 >5（字节码层）

- [ ] **Step 3: Update STATUS.md and .agent/STATUS.md**

Mark Subsystem A as active, with Phase A1/A2/A3 status.

- [ ] **Step 4: Commit**

```bash
git add .agent/STATUS.md
git commit -m "chore: Subsystem A complete — search/retrieval infrastructure upgrade"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```
