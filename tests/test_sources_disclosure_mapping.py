from __future__ import annotations

from packages.sources.disclosure_mapping import (
    build_disclosure_search_spec,
    disclosure_document_matches_spec,
)
from packages.sources.enums import GovernanceAxis, InfoType, LineFamily, RegionalLevel, ToolStatus
from packages.sources.lane_execution import DirectStructuredLaneExecutor
from packages.sources.query_decomposition import QueryDecompositionTask
from packages.sources.schemas import RawDocument


def _enterprise_task(*, search_phrases: list[str]) -> QueryDecompositionTask:
    return QueryDecompositionTask(
        task_id="enterprise_disclosure_1",
        task_family="enterprise_disclosure",
        tiaokuai_axis=GovernanceAxis.MIXED,
        line_family=LineFamily.EXCHANGE,
        regional_level=RegionalLevel.NATIONAL,
        info_type=InfoType.REGULATORY_ANNOUNCEMENT,
        execution_bucket="direct_structured_sources",
        source_cluster="official_disclosure_backbone",
        source_strategy_hint="cn_disclosure_first_v2",
        include_domains=["cninfo.com.cn", "sse.com.cn", "szse.cn", "bse.cn"],
        search_phrases=search_phrases,
        evidence_goal="Find listed-company disclosure evidence.",
        fallback_path="Use direct disclosure adapters first.",
        priority=85,
        confidence=0.75,
    )


def test_disclosure_mapping_builds_topic_entity_search_spec() -> None:
    spec = build_disclosure_search_spec("安徽 新能源汽车 上市公司 公告 项目进展")

    assert spec.no_match_reason is None
    assert {candidate.name for candidate in spec.entity_candidates} >= {
        "江淮汽车",
        "国轩高科",
    }
    assert "新能源汽车" in spec.topic_keywords
    assert "cn_exchange_cninfo_announcement_v1" in spec.source_ids
    assert "江淮汽车" in spec.query
    assert "公告" in spec.query


def test_disclosure_mapping_prioritizes_region_tagged_candidates() -> None:
    spec = build_disclosure_search_spec("常州 动力电池 光伏 上市公司 公告")

    assert [candidate.name for candidate in spec.entity_candidates[:2]] == [
        "天合光能",
        "亿纬锂能",
    ]
    assert "天合光能" in spec.query


def test_disclosure_mapping_returns_precise_no_entity_candidate() -> None:
    spec = build_disclosure_search_spec("上市公司 公告 披露")

    assert spec.entity_candidates == ()
    assert spec.no_match_reason == "disclosure_no_entity_candidate"


def test_disclosure_document_match_requires_mapped_entity() -> None:
    spec = build_disclosure_search_spec("低空经济 上市公司 公告")
    payload = spec.to_dict()

    assert disclosure_document_matches_spec(
        title="中信海直：2025年年度报告",
        raw_text="公司持续推进低空经济相关业务。",
        source_uri="https://www.cninfo.com.cn/new/disclosure/detail?stockCode=000099",
        spec_payload=payload,
    )
    assert not disclosure_document_matches_spec(
        title="交易所通知公告",
        raw_text="这是一个通用公告页面。",
        source_uri="https://www.szse.cn/disclosure/notice/general/index.html",
        spec_payload=payload,
    )


def test_enterprise_disclosure_without_entity_returns_precise_no_match() -> None:
    task = _enterprise_task(search_phrases=["上市公司 公告 披露"])
    result = DirectStructuredLaneExecutor().execute_task(task)

    assert result.status == ToolStatus.PARTIAL
    assert result.evidence_count == 0
    assert result.metadata["reason_code"] == "disclosure_no_entity_candidate"
    assert result.metadata["missing_company_hint"] is True
    assert result.metadata["profile_attempt_count"] == 0


def test_weak_disclosure_filter_rejects_entity_mismatch() -> None:
    from packages.sources.lane_execution import _weak_direct_document_reason

    spec = build_disclosure_search_spec("低空经济 上市公司 公告")
    document = RawDocument(
        document_id="doc_1",
        source_id="cn_exchange_szse_notice_v1",
        title="交易所通知公告",
        source_uri="https://www.szse.cn/disclosure/notice/general/t20260410.html",
        raw_text="这是一个通用公告页面。",
        metadata={"disclosure_search_spec": spec.to_dict()},
    )
    task = _enterprise_task(search_phrases=["低空经济 上市公司 公告"])

    assert _weak_direct_document_reason(task, document) == "disclosure_entity_mismatch"
