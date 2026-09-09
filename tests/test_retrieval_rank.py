"""Tests for the graph-runtime retrieval ranking layer (retrieval_rank.py).

Covers: dedup (URL + content-hash), coarse rank (BM25 + hash-vector, RRF),
chunking, and LLM-reranker rerank with deterministic fallback.
"""

from __future__ import annotations

from packages.research_harness import retrieval_rank as rr


def _src(sid: str, url: str, title: str, text: str, family: str = "industry_research") -> dict:
    return {
        "source_id": sid, "url": url, "title": title,
        "source_family": family, "raw_text": text, "full_text": text,
    }


def test_clean_html_noise_removes_nav_menu_runs_and_site_chains():
    cases = [
        # gov site chain (pipe-separated) + nav menu run
        (
            "中国政府网| 工业和信息化部| 湖南省政府门户网站 "
            "* 网站 * 政府信息公开 * 办事服务 * 机关党建 浏阳烟花产业报告",
            "浏阳烟花产业报告",
        ),
        # star-separated CCTV nav menu run
        (
            "* 讲习所 * 国际漫评 * 国际锐评 * 国际3分钟 * 国际微访谈 浏阳花炮产业正文",
            "浏阳花炮产业正文",
        ),
        # breadcrumb + nav phrases before real content
        (
            "当前位置：湖南政研网>学习园地>参阅资料 设为 加入收藏 首页 返回顶部 "
            "2023年浏阳花炮产值500亿元。",
            "2023年浏阳花炮产值500亿元。",
        ),
        # baidu-style concatenated nav menu
        (
            "网页新闻贴吧知道网盘图片视频地图文库资讯采购百科 "
            "进入词条 播报 编辑讨论 浏阳烟花产业链报告",
            "浏阳烟花产业链报告",
        ),
    ]
    for noisy, expected in cases:
        cleaned = rr.clean_html_noise(noisy)
        assert expected in cleaned, f"expected content lost: {cleaned!r}"
        for noise_term in (
            "讲习所", "国际漫评", "政府信息公开", "加入收藏", "进入词条", "播报", "编辑讨论"
        ):
            assert noise_term not in cleaned, f"noise survived: {noise_term} in {cleaned!r}"


def test_clean_html_noise_removes_markdown_image_and_tags():
    noisy = (
        "![](/hnszf/xhtml/img/logo.png) 浏阳烟花产业链报告 "
        "<img src='/x.png'/> [来源链接](https://x.com/1) 首页 返回顶部 2023年产值500亿元。"
    )
    clean = rr.clean_html_noise(noisy)
    assert "logo" not in clean
    assert "img" not in clean.lower()
    assert "[](/" not in clean
    assert "首页" not in clean and "返回顶部" not in clean
    assert "浏阳烟花产业链报告" in clean
    assert "产值500亿元" in clean


def test_dedup_sources_removes_duplicate_url_and_content():
    sources = [
        _src("a", "https://X.com/1?utm_source=x", "A",
             "浏阳烟花产业链报告，上游原材料、中游制造。"),
        _src("b", "https://x.com/1", "A-copy", "浏阳烟花产业链报告，上游原材料、中游制造。"),
        _src("c", "https://x.com/2", "C", "某房地产公司年报，营收增长。"),
        _src("d", "https://x.com/3", "D", "浏阳烟花产值突破500亿元。"),
    ]
    deduped = rr.dedup_sources(sources)
    assert len(deduped) == 3  # b 的 URL 与 a 相同(canonicalize)被去重
    ids = {s["source_id"] for s in deduped}
    assert "b" not in ids


def test_dedup_sources_content_hash_removes_duplicate_body():
    sources = [
        _src("a", "https://x.com/1", "A", "完全相同的正文内容，重复发布。"),
        _src("b", "https://x.com/2", "B", "完全相同的正文内容，重复发布。"),
    ]
    deduped = rr.dedup_sources(sources)
    assert len(deduped) == 1


def test_rrf_merge_favors_high_rank_in_both_lanes():
    # bm25 排名：0,1,2,3,4；vec 排名：0,3,1,2,4
    bm25 = [3.0, 2.0, 1.0, 0.5, 0.1]
    vec = [3.0, 1.0, 0.5, 2.0, 0.2]
    fused = rr.rrf_merge(bm25, vec, k=60)
    # 文档 0 双第 1 最高；文档 1 排名(2,3) 高于文档 2(3,4) 高于文档 4(5,5)
    assert fused[0] > fused[1] > fused[2] > fused[4]


def test_coarse_rank_puts_relevant_source_on_top():
    sources = [
        _src("a", "https://x.com/1", "浏阳烟花产业链报告",
             "浏阳烟花产业链上游原材料、中游生产制造、下游销售，代表企业庆泰、东信。"),
        _src("b", "https://x.com/2", "某公司财报",
             "公司2023年营收增长，主要业务为房地产和金融。"),
        _src("c", "https://x.com/3", "浏阳烟花产值统计",
             "2023年浏阳烟花产值突破500亿元，出口120亿元，企业900余家。"),
    ]
    coarse = rr.coarse_rank_bm25_vector_rrf(
        sources, "湖南浏阳烟花产业发展", ["浏阳 烟花 产业链", "浏阳 烟花 产值"]
    )
    assert coarse
    assert all("_coarse_rrf_score" in s for s in coarse)
    # 与 query 强相关的 a 应排在前列（BM25 命中"产业链/烟花"最多）
    assert coarse[0]["source_id"] == "a"


def test_chunk_documents_produces_chunks_with_source_link():
    doc = _src("a", "https://x.com/1", "浏阳烟花产业链",
               "上游原材料（火药、纸张）。中游生产制造（自动化产线）。下游销售渠道与物流。")
    chunks = rr.chunk_documents([doc], max_chars=50)
    assert chunks
    assert chunks[0]["source_id"] == "a"
    assert chunks[0]["chunk_id"].startswith("a_chunk_")
    assert chunks[0]["chunk_text"]


def test_rerank_falls_back_to_deterministic_when_model_down(monkeypatch):
    chunks = [
        {"chunk_id": "a_chunk_0", "source_id": "a", "chunk_text": "浏阳烟花产值500亿元。",
         "source_family": "official_statistics"},
        {"chunk_id": "b_chunk_0", "source_id": "b", "chunk_text": "房地产公司年报。",
         "source_family": "company_disclosure"},
    ]

    def _boom(*args, **kwargs):
        raise ConnectionError("vllm down")

    monkeypatch.setattr(rr, "rerank_with_llm", _boom)
    ranked, mode = rr.rerank_chunks_llm(
        "湖南浏阳烟花产业发展", ["浏阳 烟花 产值"], chunks, top_k=5
    )
    assert mode == "deterministic_fallback"
    assert len(ranked) == 2
    assert all("rerank_score" in c for c in ranked)


def test_rank_retrieved_sources_end_to_end(monkeypatch):
    sources = [
        _src("a", "https://x.com/1", "浏阳烟花产业链",
             "上游原材料、中游制造、下游销售。代表企业庆泰、东信烟花。"),
        _src("b", "https://x.com/2", "公司财报", "营收增长，房地产金融。"),
    ]
    monkeypatch.setattr(rr, "rerank_with_llm", lambda *a, **k: [
        {"chunk_id": "a_chunk_0", "rerank_score": 0.9},
        {"chunk_id": "b_chunk_0", "rerank_score": 0.3},
    ])
    out = rr.rank_retrieved_sources(sources, "湖南浏阳烟花产业发展", ["浏阳 烟花 产业链"])
    assert out["source_chunks"]
    assert out["rerank_mode"] == "llm_reranker_v1"
    assert out["coarse_meta"]["dedup_count"] == 2
    assert out["ranked_sources"]


# ── rerank query coverage（G4 evidence-quality 修复） ─────────────────────────

def test_build_rerank_query_covers_all_distinctive_terms():
    """rerank query 必须覆盖全部 search phrase 的独特维度词，而不只是前 6 个。"""
    query = "低空经济中央政策是否进入规模化落地阶段"
    phrases = [
        query,  # 整句重复
        query + " 上市公司 年报",  # 长变体（query + 尾部新词）
        "通用航空",
        "eVTOL",
        "低空经济 定义 产业边界 通用航空 无人机 eVTOL",
        "无人机 技术 成熟度",
        "、、、cninfo 披露",  # 标点噪音应被清洗
        "中标公告 项目公告 招投标",
    ]
    rq = rr._build_rerank_query(query, phrases)
    terms = (
        "通用航空", "eVTOL", "无人机", "产业边界", "上市公司", "年报", "cninfo", "披露", "中标",
    )
    for term in terms:
        assert term in rq, f"rerank query missing distinctive term: {term}"
    # 噪音清洗：无孤立标点段
    assert "、" not in rq
    # 长度上限
    assert len(rq) <= rr._RERANK_QUERY_MAX_CHARS
    # 整句重复不堆积：query 只出现一次
    assert rq.count(query) == 1


def test_coarse_rank_covers_late_phrase_terms():
    """粗排（BM25+向量）必须覆盖超过前 8 个短语的维度词——匹配靠后短语的源要进 top。"""
    query = "低空经济政策"
    phrases = [f"低空经济 维度{i}" for i in range(15)]
    phrases.append("中标公告 上市公司 年报")  # 第 16 个，远超旧 [:8]
    sources = [
        _src("a", "https://x/1", "低空经济", "低空经济中央政策，空域改革，适航认证。"),
        _src("b", "https://x/2", "中标公告", "某公司中标低空经济项目，上市公司年报披露订单增长。"),
    ]
    coarse = rr.coarse_rank_bm25_vector_rrf(sources, query, phrases, top_n=2)
    ids = [c["source_id"] for c in coarse]
    assert "b" in ids, f"matching late-phrase (中标/上市公司) source should rank in top, got {ids}"


def test_build_rerank_query_dedups_query_variants_and_stays_compact():
    """query 的重复变体不产生重复信息；纯 query 变体不额外加词。"""
    query = "湖南浏阳烟花产业发展"
    variants = [
        "湖南浏阳烟花产业发展？请验证产值、出口、企业数量。",
        "湖南浏阳烟花产业发展（浏阳 烟花 产业链）",
        "湖南浏阳烟花产业 产值 出口",
    ]
    rq = rr._build_rerank_query(query, variants)
    assert "产值" in rq or "出口" in rq
    assert len(rq) <= rr._RERANK_QUERY_MAX_CHARS
    assert rq.count(query) == 1
