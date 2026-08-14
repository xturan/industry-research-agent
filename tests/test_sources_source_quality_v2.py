from __future__ import annotations

from datetime import date

from packages.sources.source_quality import (
    assess_source_quality_v2,
    classify_source_role,
    score_freshness,
)


def test_classify_source_role_distinguishes_policy_transaction_and_media() -> None:
    assert (
        classify_source_role(
            "www.gov.cn",
            "https://www.gov.cn/zhengce/2025-01/01/content_123.htm",
            "低空经济发展政策通知",
        )
        == "official_policy_original"
    )
    assert (
        classify_source_role(
            "ggzy.hefei.gov.cn",
            "https://ggzy.hefei.gov.cn/jyxx/002001/202506/tender.html",
            "低空经济项目中标公告",
        )
        == "public_resource_transaction"
    )
    assert (
        classify_source_role(
            "finance.sina.com.cn",
            "https://finance.sina.com.cn/news.html",
            "产业新闻解读",
        )
        == "commercial_media_context"
    )


def test_freshness_keeps_old_policy_as_validity_check_not_stale() -> None:
    policy = score_freshness(
        title="低空经济政策通知 2020年1月1日",
        url="https://www.gov.cn/zhengce/2020-01/01/content_1.htm",
        published_date=None,
        extracted_text="",
        source_role="official_policy_original",
        query="低空经济政策",
        as_of_date=date(2026, 6, 9),
    )
    procurement = score_freshness(
        title="低空经济项目中标公告 2020年1月1日",
        url="https://ggzy.example.cn/20200101/bid.html",
        published_date=None,
        extracted_text="",
        source_role="public_resource_transaction",
        query="低空经济最新招标",
        as_of_date=date(2026, 6, 9),
    )

    assert policy.label == "needs_validity_check"
    assert policy.validity_status == "needs_validity_check"
    assert procurement.label == "historical"
    assert procurement.score < policy.score


def test_assess_source_quality_v2_records_query_relevance_signals() -> None:
    quality = assess_source_quality_v2(
        query="合肥低空经济招标项目",
        domain="ggzy.hefei.gov.cn",
        url="https://ggzy.hefei.gov.cn/jyxx/002001/202512/bid.html",
        title="合肥低空经济项目中标公告",
        snippet="合肥公共资源交易中心发布低空经济项目中标结果。",
        extracted_text="本项目为低空经济基础设施采购，中标单位已经公示。",
        published_date="2025-12-01",
        discovered_by_phrase="合肥 低空经济 招标 中标",
        expanded_terms=["低空经济", "招标", "中标"],
        as_of_date=date(2026, 6, 9),
    )
    data = quality.to_dict()

    assert data["source_role"] == "public_resource_transaction"
    assert data["freshness"]["label"] == "fresh"
    assert data["query_relevance"]["signals"]["query_phrase_match"] is True
    assert data["query_relevance"]["signals"]["source_family_match"] is True
    assert data["usage_role"] in {
        "primary_evidence_candidate",
        "supporting_evidence_candidate",
    }


def test_family_mismatch_with_procurement_intent_is_not_primary() -> None:
    quality = assess_source_quality_v2(
        query="低空经济公共资源采购中标证据",
        domain="www.gov.cn",
        url="https://www.gov.cn/zhengce/2025-01/01/content_123.htm",
        title="低空经济发展政策通知",
        snippet="低空经济政策支持方向。",
        extracted_text="该政策提出支持低空经济发展，但没有中标或采购结果。",
        published_date="2025-01-01",
        discovered_by_phrase="低空经济 采购 中标 官方",
        expanded_terms=["低空经济", "采购", "中标"],
        as_of_date=date(2026, 6, 9),
    )
    data = quality.to_dict()

    assert data["source_role"] == "official_policy_original"
    assert data["query_relevance"]["signals"]["source_family_match"] is False
    assert data["query_relevance"]["score"] <= 0.68
    assert data["usage_role"] == "supporting_evidence_candidate"
    assert "winning bid evidence" in data["not_sufficient_for"]
