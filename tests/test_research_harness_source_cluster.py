"""Shadow Source Content Clustering (research-contract-refactor Phase A2).

Covers the 10 positive/negative scenarios from the A2 spec, plus
representative-based anti-chaining, shadow output shape, and the guarantee that
cluster_sources never mutates source records.

Key negative principle: 同一事件 ≠ 同一稿件, 语义相关 ≠ 内容重复.
"""

from __future__ import annotations

import copy
import json

from packages.research_harness.source_cluster import (
    canonicalize_url,
    cluster_sources,
    content_fingerprint,
    normalize_title,
    slot_source_counts,
)

BODY = "合肥低空经济产业2025年规模达500亿元，同比增长8%，预计2026年突破600亿元，政策支持持续加码。"


def _src(sid: str, *, url: str, title: str = "", full_text: str = "") -> dict:
    return {
        "source_id": sid,
        "url": url,
        "title": title or full_text[:20],
        "full_text": full_text,
    }


# ── normalization ───────────────────────────────────────────────────────────

def test_canonicalize_url_drops_tracking_sorts_params_unifies_slash():
    a = canonicalize_url("https://www.Hefei.gov.cn/a/b/?utm_source=x&b=2&a=1&utm_medium=y#frag")
    b = canonicalize_url("https://hefei.gov.cn/a/b?a=1&b=2")
    assert a == b == "https://hefei.gov.cn/a/b?a=1&b=2"


def test_canonicalize_url_strips_print_mobile():
    assert canonicalize_url("https://example.com/news/print?id=5") == "https://example.com/news?id=5"
    assert canonicalize_url("https://example.com/news/amp?id=5") == "https://example.com/news?id=5"


def test_normalize_title_strips_site_name():
    t1 = normalize_title("合肥市支持低空经济若干政策 - 合肥市人民政府")
    assert t1 == "合肥市支持低空经济若干政策"
    assert normalize_title("【安徽日报】合肥低空经济加速起飞") == "合肥低空经济加速起飞"
    assert normalize_title("合肥低空经济加速起飞 | 澎湃") == "合肥低空经济加速起飞"


def test_content_fingerprint_is_deterministic_and_whitespace_collapsed():
    # whitespace RUNS are collapsed to a single space (deterministic)
    assert content_fingerprint("合肥   政策  支持 ") == content_fingerprint("合肥 政策 支持")
    assert content_fingerprint("合肥政策支持").startswith("sha256:")


# ── positive scenarios: same cluster ────────────────────────────────────────

def test_same_url_diff_utm_same_cluster():
    srcs = [
        _src("a", url="https://hefei.gov.cn/p1?utm_source=wechat", full_text=BODY),
        _src("b", url="https://hefei.gov.cn/p1?utm_source=weibo", full_text=BODY),
    ]
    out = cluster_sources(srcs)
    assert out["shadow_distinct_content_count"] == 1
    assert out["raw_source_count"] == 2


def test_diff_domain_same_body_same_cluster():
    srcs = [
        _src("a", url="https://hefei.gov.cn/p1", full_text=BODY),
        _src("b", url="https://news.cn/reprint/123", full_text=BODY),
    ]
    out = cluster_sources(srcs)
    assert out["shadow_distinct_content_count"] == 1
    cluster = out["clusters"][0]
    assert set(cluster["source_ids"]) == {"a", "b"}
    assert "exact_content_hash" in cluster["duplicate_reason"]
    assert cluster["duplicate_confidence"] == 1.0


def test_header_footer_template_difference_same_cluster():
    long_body = BODY * 6  # dominate the template noise
    srcs = [
        _src("a", url="https://a.com/p", full_text="【站点A导航】" + long_body + "【站点A版权】"),
        _src("b", url="https://b.com/p", full_text="【站点B导航】" + long_body + "【站点B备案】"),
    ]
    out = cluster_sources(srcs)
    assert out["shadow_distinct_content_count"] == 1


def test_title_minor_change_body_high_sim_same_cluster():
    variant = BODY[:-1] + "！"  # near-identical body, different title
    srcs = [
        _src("a", url="https://a.com/p1", title="合肥低空经济规模报告", full_text=BODY),
        _src("b", url="https://b.com/p2", title="合肥低空经济规模报告(修订版)", full_text=variant),
    ]
    out = cluster_sources(srcs)
    assert out["shadow_distinct_content_count"] == 1
    assert any("body_high_similarity" in c["duplicate_reason"] for c in out["clusters"])


def test_official_original_and_media_reprint_same_cluster():
    srcs = [
        _src("a", url="https://gov.cn/xxx", full_text=BODY),
        _src("b", url="https://media.cn/reprint", full_text=BODY),
    ]
    out = cluster_sources(srcs)
    assert out["shadow_distinct_content_count"] == 1


# ── negative scenarios: must NOT merge ─────────────────────────────────────

def test_summary_report_is_candidate_not_merged():
    summary = "合肥低空经济产业2025年规模达500亿元，同比增长8%。"
    srcs = [
        _src("a", url="https://gov.cn/full", full_text=BODY),
        _src("b", url="https://media.cn/summary", full_text=summary),
    ]
    out = cluster_sources(srcs)
    assert out["shadow_distinct_content_count"] == 2  # not merged
    assert any(c["candidate_only"] for c in out["candidates"])


def test_independent_interview_not_merged():
    interview_a = "专家甲表示，合肥低空经济项目将于2025年投运，产业前景广阔。"
    interview_b = "记者采访获悉，合肥低空经济项目预计2026年完成建设并投入运营。"
    srcs = [
        _src("a", url="https://a.com/i1", full_text=interview_a),
        _src("b", url="https://b.com/i2", full_text=interview_b),
    ]
    out = cluster_sources(srcs)
    assert out["shadow_distinct_content_count"] == 2
    assert out["candidates"] == []


def test_page_update_revision_candidate_not_merged():
    # same canonical URL, different content (project status changed)
    srcs = [
        _src("a", url="https://gov.cn/project/1", full_text="项目处于招标阶段，计划2025年9月开工。"),  # noqa: E501
        _src("b", url="https://gov.cn/project/1", full_text="项目已正式投运，2026年1月实现首飞。"),  # noqa: E501
    ]
    out = cluster_sources(srcs)
    assert out["shadow_distinct_content_count"] == 2  # not merged
    assert any(r["reason"] == "same_url_different_content" for r in out["revision_candidates"])


def test_policy_original_vs_interpretation_not_merged():
    original = "为促进低空经济高质量发展，合肥市出台若干支持政策，重点支持eVTOL研发制造与场景应用。"
    interpretation = "分析人士认为，合肥市低空经济新政释放积极信号，将带动上游零部件与基础设施投资增长。"  # noqa: E501
    srcs = [
        _src("a", url="https://gov.cn/policy", full_text=original),
        _src("b", url="https://analysis.cn/comment", full_text=interpretation),
    ]
    out = cluster_sources(srcs)
    assert out["shadow_distinct_content_count"] == 2
    assert out["candidates"] == []


def test_same_number_different_analysis_not_merged():
    a = "A公司2024年低空经济营收2.3亿元，增长35%，业务拓展顺利。"
    b = "A公司2024年低空经济营收2.3亿元，增长35%，但面临成本压力与竞争加剧。"
    srcs = [
        _src("a", url="https://a.com/n1", full_text=a),
        _src("b", url="https://b.com/n2", full_text=b),
    ]
    out = cluster_sources(srcs)
    # shared numbers but different analysis -> NOT merged
    assert out["shadow_distinct_content_count"] == 2


# ── critical-fact conflict (status update vs reprint) ─────────────────────

def test_critical_fact_conflict_blocks_status_update_merge():
    from packages.research_harness.source_cluster import blocking_reasons
    # same entity, different lifecycle state -> bound conflict -> blocking reason
    a = "合肥低空物流项目2025年正式开工，总投资12亿元，预计2026年投运，政策支持持续加码。"
    b = "合肥低空物流项目2025年正式投运，总投资12亿元，预计2026年投运，政策支持持续加码。"
    assert "critical_fact_conflict" in blocking_reasons(a, b)
    srcs = [
        _src("a", url="https://a.com/s1", full_text=a),
        _src("b", url="https://b.com/s2", full_text=b),
    ]
    out = cluster_sources(srcs)
    assert out["shadow_distinct_content_count"] == 2  # NOT merged
    assert any("critical_fact_conflict" in c["duplicate_reason"] for c in out["candidates"])


def test_critical_fact_conflict_blocks_amount_change_merge():
    a = "合肥低空物流项目总投资约10亿元。"
    b = "合肥低空物流项目总投资约12亿元。"
    srcs = [
        _src("a", url="https://a.com/m1", full_text=a),
        _src("b", url="https://b.com/m2", full_text=b),
    ]
    out = cluster_sources(srcs)
    assert out["shadow_distinct_content_count"] == 2  # NOT merged (amount changed)


def test_same_status_near_dup_still_merges():
    a = BODY.replace("持续加码", "进入开工阶段")
    b = a[:-1] + "！"  # near-identical, same status word 开工
    srcs = [
        _src("a", url="https://a.com/g1", full_text=a),
        _src("b", url="https://b.com/g2", full_text=b),
    ]
    out = cluster_sources(srcs)
    assert out["shadow_distinct_content_count"] == 1  # merged (no status conflict)


# ── representative-based anti-chaining ─────────────────────────────────────

def test_representative_based_no_chain():
    """A source similar only to a non-representative member must NOT join.

    R (rep) + M (near-dup, one-char variant) form a cluster. C (longer tail
    variant) is only compared to the representative R -> candidate, not merged.
    If clustering compared against every member (simple Union-Find), C could
    slip in via M. Representative-based prevents cumulative drift.
    """
    r = _src("R", url="https://a.com/r", full_text=BODY)
    m = _src("M", url="https://a.com/m", full_text=BODY[:-1] + "！")
    c = _src("C", url="https://a.com/c", full_text=BODY + "产业生态不断完善。")
    out = cluster_sources([r, m, c])
    # R and M form one cluster; C stays out
    cluster_sizes = sorted(len(cl["source_ids"]) for cl in out["clusters"])
    assert cluster_sizes == [1, 2]
    cluster_ids = [set(cl["source_ids"]) for cl in out["clusters"]]
    assert {"R", "M"} in cluster_ids
    assert any(cand["source_id"] == "C" and cand["candidate_only"] for cand in out["candidates"])


# ── shadow output shape + no-mutation ──────────────────────────────────────

def test_shadow_report_and_slot_counts():
    srcs = [
        _src("a", url="https://gov.cn/p1", full_text=BODY),
        _src("b", url="https://media.cn/reprint", full_text=BODY),
        _src("c", url="https://gov.cn/p2", full_text="合肥市出台低空经济专项基金管理办法。"),
    ]
    out = cluster_sources(srcs)
    assert out["raw_source_count"] == 3
    assert out["shadow_distinct_content_count"] == 2
    assert out["shadow_duplicate_adjusted_source_count"] == 2
    assert out["clustering_mode"] == "shadow"
    assert out["clustering_version"] == "source_cluster_v1"

    # slot-level: project slot backed by a+b (duplicate) + c
    rows = slot_source_counts(
        {"project.operation_status": ["a", "b", "c"]}, out
    )
    row = next(r for r in rows if r["slot_id"] == "project.operation_status")
    assert row["raw_supporting_source_count"] == 3
    assert row["shadow_distinct_content_count"] == 2
    assert row["shadow_count_difference"] == -1


def test_cluster_sources_never_mutates_sources():
    srcs = [
        _src("a", url="https://gov.cn/p1", full_text=BODY),
        _src("b", url="https://media.cn/reprint", full_text=BODY),
    ]
    snapshot = copy.deepcopy(srcs)
    cluster_sources(srcs)
    assert srcs == snapshot  # no mutation, no origin_source_id written


def test_shadow_integration_hook_attaches_metadata_only():
    from packages.research_harness.real_nodes import _shadow_source_clustering_meta

    srcs = [
        _src("a", url="https://gov.cn/p1", full_text=BODY),
        _src("b", url="https://media.cn/reprint", full_text=BODY),
        _src("c", url="https://gov.cn/p2", full_text="合肥市出台低空经济专项基金管理办法。"),
    ]
    snapshot = copy.deepcopy(srcs)
    shadow = _shadow_source_clustering_meta(state={"evidence": []}, sources=srcs)
    assert srcs == snapshot  # sources untouched
    assert shadow is not None
    assert shadow["report"]["raw_source_count"] == 3
    assert shadow["report"]["shadow_distinct_content_count"] == 2
    assert shadow["report"]["clustering_mode"] == "shadow"
    assert shadow["duplicate_removed_count"] == 1


def test_shadow_integration_no_origin_source_id():
    from packages.research_harness.real_nodes import _shadow_source_clustering_meta

    srcs = [_src("a", url="https://gov.cn/p1", full_text=BODY)]
    shadow = _shadow_source_clustering_meta(state={"evidence": []}, sources=srcs)
    # shadow output must never fabricate origin_source_id
    assert "origin_source_id" not in json.dumps(shadow, ensure_ascii=False)
