"""Graph-runtime retrieval ranking.

Pipeline: dedup -> coarse rank (BM25 + vector, fused by RRF) -> pick docs ->
chunk -> LLM reranker rerank (deterministic fallback when the model is down).

Everything runs in-memory on the collected source dicts (no DB), so it slots into
the graph-runtime path of `retrieval_bridge.build_graph_retrieval_artifacts`
before `_inject_chunk_text_into_sources` injects the ranked chunks.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from packages.ingestion.chunker import chunk_parsed_content
from packages.ingestion.schemas import ParsedContent, ParsedSection
from packages.rag.chunk_quality import score_chunk_quality
from packages.rag.embeddings import (
    build_deterministic_embedding,
    cosine_similarity,
    embed_text,
    embed_text_batch,
)
from packages.rag.rerankers import rerank_with_llm
from packages.research_harness.source_cluster import canonicalize_url

_RRF_K = 60
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_ASCII_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


# HTML / markdown residual noise from fetched pages (logos, images, scripts).
_HTML_TAG_RE = re.compile(r"<[^>]{1,300}>")
# markdown image, closed or not: ![alt](url...) — stops at ) or whitespace.
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)\s]*\)?")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_IMG_URL_RE = re.compile(r"https?://[^\s]+\.(?:png|jpe?g|gif|webp|svg|ico)(?:\?[^\s]*)?", re.I)
_URL_RE = re.compile(r"https?://[^\s]+")
# Navigation / header / footer noise. Expanded term list (high-precision: these
# are unambiguous site-chrome tokens), each followed by up to 12 non-punct chars
# to also swallow adjacent breadcrumbs/params.
_NAV_NOISE_TERMS = (
    "首页|登录|注册|返回顶部|分享到|扫一扫|下载App|App下载|手机版|触屏版|移动端|"
    "网站地图|免责声明|版权声明|广告|推广|客服热线|设为首页|设为|加入收藏|收藏本站|"
    "无障碍|无障碍浏览|网站声明|关于我们|联系我们|帮助中心|使用帮助|常见问题|"
    "意见反馈|用户协议|隐私政策|友情链接|合作伙伴|站内搜索|全站搜索|高级搜索|"
    "登录注册|退出登录|个人中心|会员中心|在线咨询|服务热线|投诉举报|电子邮箱|"
    "官方微博|官方微信|微信公众号|二维码|手机客户端|主办单位|承办单位|技术支持|"
    "版权所有|网站备案|公安备案|备案号|ICP备案|进入词条|播报|编辑讨论"
)
_NAV_NOISE_RE = re.compile(rf"(?:{_NAV_NOISE_TERMS})[^\s。；;，,、|]{{0,12}}")

# Gov/news site chains separated by pipes, e.g. "中国政府网|工业和信息化部|湖南省政府门户网站".
_SITE_CHAIN_RE = re.compile(
    r"(?:[\u4e00-\u9fffA-Za-z0-9·（）()]{2,24}\s*\|\s*){2,}"
    r"[\u4e00-\u9fffA-Za-z0-9·（）()]{2,24}"
)

# Runs of 3+ known nav-menu items (CCTV / gov / gov-research / baidu style menus),
# allowing separators of spaces, pipes, or "*" bullet markers.
_NAV_MENU_ITEMS = (
    "讲习所|国际漫评|国际锐评|国际3分钟|国际微访谈|老外在中国|外媒看中国|国际甄选|"
    "走进我们|新闻中心|财经研究|决策参考|机关党建|学习园地|专家智库|"
    "网站|政府信息公开|办事服务|互动交流|政策文件|要闻动态|数据服务|在线服务|"
    "网页|贴吧|知道|网盘|图片|视频|地图|文库|资讯|采购|百科"
)
_NAV_MENU_RUN_RE = re.compile(
    rf"(?:(?:{_NAV_MENU_ITEMS})(?:\s*[*|]\s*|\s*)){{3,}}"
)
# Breadcrumb trails: "当前位置：湖南政研网>学习园地>参阅资料>湖南探索".
# Requires at least one '>' path segment so it never swallows body text.
_BREADCRUMB_RE = re.compile(
    r"当前位置[:：]\s*[^>。\n\s]{0,40}(?:\s*>\s*[^>。\n\s]{0,40}){1,6}"
)


def clean_html_noise(text: Any) -> str:
    """Strip HTML/markdown residual noise from fetched page text.

    Removes markdown images `![..](url)`, raw HTML tags, image URLs, bare URLs,
    and common navigation/footer noise — keeping the readable article body so
    chunking / evidence extraction operate on clean text."""
    value = str(text or "")
    value = _MD_IMAGE_RE.sub(" ", value)
    value = _HTML_TAG_RE.sub(" ", value)
    value = _IMG_URL_RE.sub(" ", value)
    value = _MD_LINK_RE.sub(lambda m: m.group(1) or " ", value)  # [text](url) -> text
    value = _URL_RE.sub(" ", value)
    # site chrome: gov/news site chains (pipe-separated), breadcrumbs, nav-menu
    # runs, nav phrases, then strip residual edge junk.
    value = _SITE_CHAIN_RE.sub(" ", value)
    value = _BREADCRUMB_RE.sub(" ", value)
    value = _NAV_MENU_RUN_RE.sub(" ", value)
    value = _NAV_NOISE_RE.sub(" ", value)
    # Strip residual site-chrome artifacts (pipes/stars/breadcrumb '>' at edges).
    value = value.strip(" *|;)>")
    return _normalize_text(value)


def _source_text(source: dict[str, Any]) -> str:
    """Best available document text for a source, cleaned of HTML/noise."""
    raw = str(
        source.get("full_text")
        or source.get("raw_text")
        or source.get("content_text")
        or source.get("snippet")
        or source.get("title")
        or ""
    )
    return clean_html_noise(raw)


def _tokenize_cjk(text: str) -> list[str]:
    """Tokenize for BM25: ASCII words + CJK character bigrams."""
    text = _normalize_text(text).lower()
    tokens: list[str] = []
    tokens.extend(_ASCII_TOKEN_RE.findall(text))
    for run in _CJK_RE.findall(text):
        if len(run) >= 2:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
        else:
            tokens.append(run)
    return tokens


# ── Step 1: dedup ──────────────────────────────────────────────────────────


def dedup_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedup by canonical URL and by content hash (title + body). Prefer the first
    occurrence on ties (collection order already favors higher-value routes)."""
    seen_url: set[str] = set()
    seen_hash: set[str] = set()
    out: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        url = canonicalize_url(str(source.get("url") or source.get("source_url") or ""))
        if url:
            if url in seen_url:
                continue
        content = _normalize_text(_source_text(source))
        if content:
            h = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if h in seen_hash:
                continue
            seen_hash.add(h)
        if url:
            seen_url.add(url)
        out.append(source)
    return out


# ── Step 2: coarse rank (BM25 + vector, RRF) ───────────────────────────────


def rrf_merge(
    bm25_scores: list[float], vector_scores: list[float], *, k: int = _RRF_K
) -> list[float]:
    """Reciprocal Rank Fusion of two score lists (same length, aligned by index).
    Returns fused scores aligned to the input order."""
    n = len(bm25_scores)
    fused = [0.0] * n
    bm25_rank = sorted(range(n), key=lambda i: -bm25_scores[i])
    vec_rank = sorted(range(n), key=lambda i: -vector_scores[i])
    for pos, idx in enumerate(bm25_rank):
        fused[idx] += 1.0 / (k + pos + 1)
    for pos, idx in enumerate(vec_rank):
        fused[idx] += 1.0 / (k + pos + 1)
    return fused


def coarse_rank_bm25_vector_rrf(
    sources: list[dict[str, Any]],
    query: str,
    search_phrases: list[str] | None = None,
    *,
    top_n: int = 30,
) -> list[dict[str, Any]]:
    """Coarse-rank sources: BM25 and hash-vector lanes in parallel, fused by RRF.

    BM25 uses `query + search_phrases` as the query (the search phrases from the
    planning stage are the strongest signal for what the user wants). Returns
    top_n sources each tagged with `_coarse_rrf_score`."""
    from rank_bm25 import BM25Okapi

    documents: list[dict[str, Any]] = []
    tokenized: list[list[str]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        text = _normalize_text(_source_text(source))
        if not text:
            continue
        toks = _tokenize_cjk(text)
        if not toks:
            continue
        documents.append(source)
        tokenized.append(toks)
    if not documents:
        return []

    # Coverage query = query + 全部 search phrase 的独特维度词（不再只取前 8 个）。
    # BM25 与向量路都用它，保证「检索的第一道门」就覆盖各维度。
    coverage_query = _build_rerank_query(query, search_phrases)

    bm25 = BM25Okapi(tokenized)
    bm25_query = _tokenize_cjk(coverage_query)
    bm25_scores = bm25.get_scores(bm25_query)

    # Vector lane: real embedding (vLLM /embeddings) when configured, otherwise
    # the deterministic hash embedding. Both lanes use the same dimension so
    # cosine_similarity never hits a mismatch.
    from packages.core.config import get_settings

    embed_dims = int(get_settings().embedding_dimensions)
    texts = [_normalize_text(_source_text(d)) for d in documents]
    query_vec = embed_text(coverage_query, dimensions=embed_dims) or build_deterministic_embedding(
        coverage_query, dimensions=embed_dims
    )
    vectors = embed_text_batch(texts, dimensions=embed_dims)
    vector_scores = [cosine_similarity(query_vec, vector) for vector in vectors]

    fused = rrf_merge(bm25_scores, vector_scores, k=_RRF_K)
    order = sorted(range(len(documents)), key=lambda i: -fused[i])[:top_n]
    ranked: list[dict[str, Any]] = []
    for idx in order:
        item = dict(documents[idx])
        item["_coarse_rrf_score"] = round(fused[idx], 6)
        ranked.append(item)
    return ranked


# ── Step 3: chunk selected documents ───────────────────────────────────────


def chunk_documents(
    docs: list[dict[str, Any]], *, max_chars: int = 1700
) -> list[dict[str, Any]]:
    """Chunk selected documents with the repository chunker. Each chunk carries
    `chunk_id/source_id/chunk_index/chunk_text/source_family` for downstream
    evidence mapping."""
    chunks: list[dict[str, Any]] = []
    for source in docs:
        if not isinstance(source, dict):
            continue
        text = _normalize_text(_source_text(source))
        if not text:
            continue
        sid = str(source.get("source_id") or "")
        parsed = ParsedContent(
            title=str(source.get("title") or sid or "source"),
            text=text,
            source_uri=str(source.get("url") or source.get("source_url") or ""),
            sections=[
                ParsedSection(
                    section_name=str(source.get("title") or "source"),
                    text=text,
                    locator=str(source.get("url") or source.get("source_url") or ""),
                )
            ],
        )
        for draft in chunk_parsed_content(parsed, max_chars=max_chars):
            chunks.append({
                "chunk_id": f"{sid}_chunk_{draft.chunk_index}",
                "source_id": sid,
                "document_title": str(source.get("title") or ""),
                "source_uri": str(source.get("url") or source.get("source_url") or ""),
                "source_family": str(source.get("source_family") or ""),
                "chunk_index": draft.chunk_index,
                "chunk_text": draft.text,
                "chunk_metadata": {
                    "graph_source_id": sid,
                    "source_family": str(source.get("source_family") or ""),
                },
            })
    return chunks


# ── Step 4: LLM reranker rerank (deterministic fallback) ────────────────────


# rerank query 长度上限（vLLM max_model_len=1536 token，900 字符约 ~450 token CJK，
# 加上 evidence text 后仍在预算内）。旧实现只取前 6 个 search phrase，会漏掉大量
# 维度独特词；新实现归一化去重全部 phrase + 提取 query 未覆盖的独特词。
_RERANK_QUERY_MAX_CHARS = 900
_CJK_TERM_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_ASCII_TERM_RE = re.compile(r"[a-zA-Z0-9]{2,}")
_RERANK_STOPWORDS = {
    "以及", "是否", "已经", "进入", "阶段", "目前", "处于", "什么", "哪些", "如何",
    "请分别", "分别", "验证", "请", "进行", "重点", "检查", "找出", "用", "区分",
    "然后", "之后", "其中", "对于",
}


def _phrase_terms(text: str) -> list[str]:
    """从短语中提取候选词：连续 CJK 段 + ASCII 词（过滤停用词）。"""
    terms: list[str] = []
    for run in _CJK_TERM_RE.findall(text):
        terms.append(run)
    terms.extend(_ASCII_TERM_RE.findall(text))
    return [t for t in terms if t not in _RERANK_STOPWORDS]


_PUNCT_EDGE_RE = re.compile(r"^[^\u4e00-\u9fffA-Za-z0-9]+|[^\u4e00-\u9fffA-Za-z0-9]+$")


def _clean_info(info: str) -> str:
    """去掉首尾标点（如 '、、、cninfo 披露' -> 'cninfo 披露'）。"""
    return _PUNCT_EDGE_RE.sub("", info).strip()


def _phrase_new_info(phrase: str, query: str, query_terms: set[str]) -> str:
    """返回一个 search phrase 相对 query 的「独特信息」：
    - 已被 query 完全包含（子串）→ 无新信息；
    - phrase 包含 query（整句 query 变体 + 尾巴）→ 只取 query 未覆盖的词段；
    - 短短语（<=40 字符，多为 dimension caliber_terms 或 LLM 维度搜索词）→
      剥离 query 首个主题词前缀（如'低空经济'）后整体加入（2026-08-11 优化：
      避免 LLM 维度词因带 query 主题前缀而重复）；
    - 其余长短语 → 只取 query 未覆盖的词段。"""
    if not phrase or phrase in query:
        return ""
    if query in phrase:
        new_terms = [t for t in _phrase_terms(phrase) if t not in query_terms]
        return " ".join(new_terms)
    if len(phrase) <= 40:
        stripped = phrase
        first = str(query).split()[0] if query.split() else ""
        if first and stripped.startswith(first):
            stripped = stripped[len(first):].strip()
            stripped = _clean_info(stripped)
        if not stripped:
            stripped = phrase
        info = _clean_info(stripped)
        return info if _CJK_TERM_RE.search(info) or _ASCII_TERM_RE.search(info) else ""
    new_terms = [t for t in _phrase_terms(phrase) if t not in query_terms]
    return " ".join(new_terms)


def _build_rerank_query(
    query: str,
    search_phrases: list[str] | None,
    *,
    dimension_terms: dict[str, list[str]] | None = None,
) -> str:
    """构建覆盖全部搜索词的紧凑 rerank query。

    设计（2026-08-11 优化）：
    1. 优先用 LLM 维度搜索词（dimension_terms，语义完整查询式如
       '低空经济 中标公告 竞争格局 企业名单'）——它们是 query特点+维度词+来源；
    2. 把 query + 所有来源（维度词、搜索短语）的词合并成**去重独特信息集合**
       （相对 query 的 delta），按长度升序排列，优先塞短独特词；
    3. 截断到 `_RERANK_QUERY_MAX_CHARS`。

    对比旧实现（51 短语拼接成松散词表），新 query 以语义完整的维度查询式为主，
    且去除重复的 query 前缀（'低空经济 中标公告'只保留一次在 base）。
    """
    base = str(query or "").strip()
    query_terms = set(_phrase_terms(base))
    # 收集所有候选源（维度词优先在前）
    all_phrases: list[str] = []
    seen_raw: set[str] = set()
    if dimension_terms:
        for terms in dimension_terms.values():
            for phrase in terms[:2]:
                t = _normalize_text(str(phrase or ""))
                if t and t not in seen_raw:
                    seen_raw.add(t)
                    all_phrases.append(t)
    for raw in search_phrases or []:
        t = _normalize_text(str(raw or ""))
        if t and t not in seen_raw:
            seen_raw.add(t)
            all_phrases.append(t)

    # 提取去重独特信息（相对 query 的 delta）
    candidates: list[str] = []
    seen_info: set[str] = set()
    for text in all_phrases:
        info = _phrase_new_info(text, base, query_terms)
        if info and info not in seen_info:
            seen_info.add(info)
            candidates.append(info)
    candidates.sort(key=len)
    parts = [base]
    for info in candidates:
        if len(" ".join(parts)) + len(info) + 1 > _RERANK_QUERY_MAX_CHARS:
            break
        parts.append(info)
    return " ".join(parts)[:_RERANK_QUERY_MAX_CHARS]


def rerank_chunks_llm(
    query: str,
    search_phrases: list[str] | None,
    chunks: list[dict[str, Any]],
    *,
    top_k: int = 24,
    dimension_terms: dict[str, list[str]] | None = None,
    max_workers: int = 4,
) -> tuple[list[dict[str, Any]], str]:
    """Rerank chunks with the LLM reranker (query = search phrases + query).
    Falls back to deterministic (chunk quality + coarse score) when the model is
    unavailable. Returns (sorted_chunks, rerank_mode).

    dimension_terms（LLM 生成的维度搜索词）优先作为精排 query——语义完整查询式
    比短语拼接更精准（2026-08-11）。"""
    if not chunks:
        return [], "no_chunks"
    rerank_query = _build_rerank_query(query, search_phrases, dimension_terms=dimension_terms)
    rerank_mode = "llm_reranker_v1"
    score_by_id: dict[str, float] = {}
    bucket_by_id: dict[str, int | None] = {}
    # ── 2026-08-11：前置健康检查——vLLM 不可达时立即回退 deterministic，
    # 不逐 chunk 超时（每个 chunk 30s 超时会拖死 parse_sources）。 ──
    try:
        from packages.rag.rerankers import reranker_health_check
        if not reranker_health_check():
            return _deterministic_rerank(chunks, top_k), "deterministic_fallback"
    except Exception:
        pass
    try:
        scores = rerank_with_llm(
            rerank_query, chunks, top_k=max(top_k * 3, 15), max_workers=max_workers
        )
        score_by_id = {
            str(item.get("chunk_id") or ""): float(item.get("rerank_score") or 0.0)
            for item in scores
        }
        bucket_by_id = {
            str(item.get("chunk_id") or ""): item.get("rerank_bucket")
            for item in scores
        }
        # Honest fallback: the LLM reranker returns 0.5 for every failed request;
        # if all scores are neutral the model is not actually serving.
        if not score_by_id or all(
            abs(value - 0.5) < 1e-6 for value in score_by_id.values()
        ):
            return _deterministic_rerank(chunks, top_k), "deterministic_fallback"
    except Exception:
        return _deterministic_rerank(chunks, top_k), "deterministic_fallback"

    scored: list[tuple[float, dict[str, Any]]] = []
    for chunk in chunks:
        cid = str(chunk.get("chunk_id") or "")
        score = score_by_id.get(cid, 0.0)
        scored.append((score, chunk))
    scored.sort(key=lambda x: -x[0])
    ranked: list[dict[str, Any]] = []
    for score, chunk in scored[:top_k]:
        cid = str(chunk.get("chunk_id") or "")
        ranked.append(dict(
            chunk,
            rerank_score=round(score, 6),
            rerank_bucket=bucket_by_id.get(cid),
        ))
    return ranked, rerank_mode


def _deterministic_rerank(
    chunks: list[dict[str, Any]], top_k: int
) -> list[dict[str, Any]]:
    """Deterministic fallback rerank: chunk quality composite score desc."""
    scored: list[tuple[float, dict[str, Any]]] = []
    for chunk in chunks:
        quality = score_chunk_quality(
            str(chunk.get("chunk_text") or ""),
            source_family=str(chunk.get("source_family") or "graph_source"),
            source_tier="C",
        )
        scored.append((float(quality.composite or 0.0), chunk))
    scored.sort(key=lambda x: -x[0])
    ranked: list[dict[str, Any]] = []
    for score, chunk in scored[:top_k]:
        cid = str(chunk.get("chunk_id") or "")
        ranked.append(dict(
            chunk,
            rerank_score=round(score, 6),
            rerank_bucket=None,
        ))
    return ranked


def rank_retrieved_sources(
    sources: list[dict[str, Any]],
    query: str,
    search_phrases: list[str] | None = None,
    *,
    coarse_top_n: int = 30,
    chunk_chars: int = 1700,
    rerank_top_k: int = 24,
    dimension_terms: dict[str, list[str]] | None = None,
    max_workers: int = 4,
) -> dict[str, Any]:
    """End-to-end: dedup -> coarse rank -> chunk -> rerank. Returns
    {source_chunks, coarse_meta, rerank_mode, ranked_sources}.

    **每个粗排选中的 source 都 chunk 处理**（chunk_documents 对全部 coarse 源生成
    chunk），rerank 只负责排序。返回的 source_chunks 覆盖所有粗排源的 chunk（不只是
    rerank_top_k 个），这样 _inject_chunk_text_into_sources 能让每个 source 都拿到
    自己的精排后 chunk，而非只有 top-24 落入少数源。rerank_top_k 仅用于标记 top-k 排序。

    dimension_terms（LLM 维度搜索词）优先作为精排 query（2026-08-11）。"""
    deduped = dedup_sources(sources)
    coarse = coarse_rank_bm25_vector_rrf(
        deduped, query, search_phrases, top_n=coarse_top_n
    )
    chunks = chunk_documents(coarse, max_chars=chunk_chars)
    reranked, rerank_mode = rerank_chunks_llm(
        query, search_phrases, chunks, top_k=max(rerank_top_k, len(chunks)),
        dimension_terms=dimension_terms, max_workers=max_workers,
    )
    return {
        "source_chunks": reranked,
        "coarse_meta": {
            "dedup_count": len(deduped),
            "coarse_count": len(coarse),
            "chunk_count": len(chunks),
        },
        "rerank_mode": rerank_mode,
        "ranked_sources": coarse,
    }


# Backward-compatible alias (legacy name "cross_encoder" is inaccurate — this is
# an LLM reranker, not a cross-encoder).
rerank_chunks_cross_encoder = rerank_chunks_llm
