from __future__ import annotations

import pytest

from packages.sources.retrieval_plan import (
    CoverageLane,
    DomainStrategy,
    ExecutionBucket,
    SourceIntent,
    build_deterministic_retrieval_plan,
    build_retrieval_plan,
    is_supplemental_or_fallback_lane,
    lane_for_task_family,
)

SRC_COV_CASES: list[tuple[str, str, set[CoverageLane]]] = [
    (
        "SRC-COV-01",
        "广东人形机器人产业政策和项目落地情况",
        {
            CoverageLane.NATIONAL_POLICY_DIRECTION,
            CoverageLane.PROVINCIAL_POLICY_ROLLOUT,
            CoverageLane.PROJECT_TRANSACTION,
            CoverageLane.STATISTICS_OR_INDUSTRY_DATA,
        },
    ),
    (
        "SRC-COV-02",
        "安徽的低空经济未来前景如何",
        {
            CoverageLane.NATIONAL_POLICY_DIRECTION,
            CoverageLane.PROVINCIAL_POLICY_ROLLOUT,
        },
    ),
    (
        "SRC-COV-03",
        "国家层面对算力基础设施有什么最新政策方向",
        {CoverageLane.NATIONAL_POLICY_DIRECTION},
    ),
    (
        "SRC-COV-04",
        "江苏光伏产业链出海面临哪些政策和贸易风险",
        {
            CoverageLane.NATIONAL_POLICY_DIRECTION,
            CoverageLane.PROVINCIAL_POLICY_ROLLOUT,
        },
    ),
    (
        "SRC-COV-05",
        "深圳低空经济有哪些政策和招标信号",
        {
            CoverageLane.CITY_COUNTY_FALLBACK,
            CoverageLane.PROJECT_TRANSACTION,
        },
    ),
    (
        "SRC-COV-06",
        "中信海直（000099.SZ）在低空经济方向有哪些公告和项目",
        {
            CoverageLane.ENTERPRISE_DISCLOSURE,
            CoverageLane.PROJECT_TRANSACTION,
        },
    ),
    (
        "SRC-COV-07",
        "成都人工智能产业园区有哪些政策和项目机会",
        {
            CoverageLane.CITY_COUNTY_FALLBACK,
            CoverageLane.PARK_ZONE_SIGNAL,
            CoverageLane.PROJECT_TRANSACTION,
        },
    ),
    (
        "SRC-COV-08",
        "浙江低空经济相关上市公司有哪些公告",
        {CoverageLane.ENTERPRISE_DISCLOSURE},
    ),
    (
        "SRC-COV-09",
        "广东人形机器人产业规模和企业数量有什么数据支撑",
        {CoverageLane.STATISTICS_OR_INDUSTRY_DATA},
    ),
    (
        "SRC-COV-10",
        "某行业协会的白皮书和论坛信息如何作为补充证据",
        {CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL},
    ),
]


def _required_lanes(query: str) -> set[CoverageLane]:
    plan = build_deterministic_retrieval_plan(query)
    return {lane.lane_id for lane in plan.coverage_lanes if lane.required}


@pytest.mark.parametrize(("case_id", "query", "expected"), SRC_COV_CASES)
def test_src_cov_cases_include_expected_required_lanes(
    case_id: str,
    query: str,
    expected: set[CoverageLane],
) -> None:
    lanes = _required_lanes(query)
    assert expected <= lanes, case_id


def test_src_cov_10_is_supplemental_only_without_official_fanout() -> None:
    query = "某行业协会的白皮书和论坛信息如何作为补充证据"
    lanes = _required_lanes(query)
    assert lanes == {CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL}


def test_src_cov_04_trade_risk_has_customs_and_commerce_angle() -> None:
    query = (
        "\u6c5f\u82cf\u5149\u4f0f\u4ea7\u4e1a\u94fe\u51fa\u6d77"
        "\u9762\u4e34\u54ea\u4e9b\u653f\u7b56\u548c\u8d38\u6613\u98ce\u9669"
    )
    plan = build_deterministic_retrieval_plan(query)
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}

    data_lane = lane_by_id[CoverageLane.STATISTICS_OR_INDUSTRY_DATA]
    assert data_lane.required is True
    assert data_lane.execution_bucket == ExecutionBucket.DIRECT_STRUCTURED_SOURCES
    assert data_lane.domain_strategy == DomainStrategy.DIRECT_STRUCTURED_ONLY
    assert {
        SourceIntent.NATIONAL_CUSTOMS,
        SourceIntent.NATIONAL_COMMERCE,
        SourceIntent.PROVINCE_COMMERCE,
    } <= set(data_lane.source_intents)
    assert any("customs" in step or "commerce" in step for step in data_lane.fallback_ladder)
    assert any(
        "\u51fa\u53e3" in phrase or "\u8d38\u6613" in phrase
        for phrase in data_lane.search_phrases
    )


def test_policy_only_computing_infrastructure_does_not_force_project_lane() -> None:
    query = (
        "\u56fd\u5bb6\u5c42\u9762\u5bf9\u7b97\u529b\u57fa\u7840\u8bbe\u65bd"
        "\u6709\u4ec0\u4e48\u6700\u65b0\u653f\u7b56\u65b9\u5411"
    )
    plan = build_deterministic_retrieval_plan(query)

    required_lanes = {lane.lane_id for lane in plan.coverage_lanes if lane.required}
    assert CoverageLane.NATIONAL_POLICY_DIRECTION in required_lanes
    assert CoverageLane.PROJECT_TRANSACTION not in required_lanes


def test_m03_low_altitude_retrieval_plan_keeps_local_and_industry_lanes() -> None:
    query = (
        "\u4f4e\u7a7a\u7ecf\u6d4e\u5728\u4e2d\u592e\u5c42\u9762"
        "\u7684\u653f\u7b56\u652f\u6301\u662f\u5426\u5df2\u7ecf"
        "\u8fdb\u5165\u89c4\u6a21\u5316\u843d\u5730\u9636\u6bb5\uff1f"
        "\u8bf7\u5206\u522b\u9a8c\u8bc1\u7a7a\u57df\u6539\u9769"
        "\u3001\u9002\u822a\u8ba4\u8bc1\u3001\u57fa\u7840\u8bbe\u65bd"
        "\u5efa\u8bbe\u3001\u5730\u65b9\u8bd5\u70b9\u548c\u4f01\u4e1a"
        "\u8ba2\u5355\u3002"
    )
    plan = build_deterministic_retrieval_plan(query)
    required_lanes = {lane.lane_id for lane in plan.coverage_lanes if lane.required}

    assert CoverageLane.PROVINCIAL_POLICY_ROLLOUT in required_lanes
    assert CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL in required_lanes


def test_m06_real_estate_retrieval_plan_prefers_macro_policy_and_data_lanes() -> None:
    query = (
        "\u623f\u5730\u4ea7\u53bb\u5e93\u5b58\u3001\u57ce\u4e2d\u6751"
        "\u6539\u9020\u3001\u201c\u4e09\u5927\u5de5\u7a0b\u201d\u548c"
        "\u5730\u65b9\u6536\u50a8\u653f\u7b56\u662f\u5426\u80fd\u5b9e"
        "\u8d28\u6539\u5584\u94a2\u94c1\u3001\u6c34\u6ce5\u3001\u5bb6"
        "\u7535\u3001\u5de5\u7a0b\u673a\u68b0\u9700\u6c42\uff1f\u8bf7"
        "\u533a\u5206\u653f\u7b56\u76ee\u6807\u3001\u8d44\u91d1\u6765"
        "\u6e90\u3001\u5f00\u5de5\u6570\u636e\u548c\u4f01\u4e1a\u6536"
        "\u5165\u3002"
    )
    plan = build_deterministic_retrieval_plan(query)
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}
    required_lanes = {lane.lane_id for lane in plan.coverage_lanes if lane.required}

    assert CoverageLane.NATIONAL_POLICY_DIRECTION in required_lanes
    assert CoverageLane.STATISTICS_OR_INDUSTRY_DATA in required_lanes
    assert CoverageLane.PROJECT_TRANSACTION in required_lanes
    assert CoverageLane.ENTERPRISE_DISCLOSURE in required_lanes
    assert CoverageLane.CITY_COUNTY_FALLBACK not in required_lanes

    policy_phrases = " ".join(lane_by_id[CoverageLane.NATIONAL_POLICY_DIRECTION].search_phrases)
    assert "\u57ce\u4e2d\u6751\u6539\u9020" in policy_phrases
    assert "\u4e09\u5927\u5de5\u7a0b" in policy_phrases

    data_phrases = " ".join(lane_by_id[CoverageLane.STATISTICS_OR_INDUSTRY_DATA].search_phrases)
    assert "\u65b0\u5f00\u5de5" in data_phrases
    assert "\u5f85\u552e\u9762\u79ef" in data_phrases


def test_phase5_macro_policy_to_demand_plan_requires_policy_and_local_fanout() -> None:
    query = (
        "“东数西算”和全国一体化算力网络是否已经转化为真实数据中心建设需求？"
        "请用国家政策、地方项目清单、用电/能耗约束、服务器/IDC 企业公告交叉验证。"
    )
    plan = build_deterministic_retrieval_plan(query)
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}
    required_lanes = {lane.lane_id for lane in plan.coverage_lanes if lane.required}

    assert CoverageLane.NATIONAL_POLICY_DIRECTION in required_lanes
    assert CoverageLane.PROVINCIAL_POLICY_ROLLOUT in required_lanes
    assert CoverageLane.PROJECT_TRANSACTION in required_lanes
    assert CoverageLane.STATISTICS_OR_INDUSTRY_DATA in required_lanes
    assert CoverageLane.ENTERPRISE_DISCLOSURE in required_lanes

    for lane_id in (
        CoverageLane.PROVINCIAL_POLICY_ROLLOUT,
        CoverageLane.PROJECT_TRANSACTION,
        CoverageLane.STATISTICS_OR_INDUSTRY_DATA,
    ):
        assert "macro_to_local_obligation" in lane_by_id[lane_id].evidence_obligations

    rollout_phrases = " ".join(
        lane_by_id[CoverageLane.PROVINCIAL_POLICY_ROLLOUT].search_phrases
    )
    assert "地方" in rollout_phrases or "省市" in rollout_phrases


def test_hefei_city_industrial_cluster_has_city_county_and_direct_keep_lanes() -> None:
    query = (
        "\u5408\u80a5\u5e02\u65b0\u80fd\u6e90\u6c7d\u8f66\u4ea7\u4e1a\u96c6\u7fa4"
        "\u662f\u5426\u5df2\u7ecf\u4ece\u9f99\u5934\u4f01\u4e1a\u62db\u5546"
        "\u8fdb\u5165\u4f9b\u5e94\u94fe\u81ea\u5faa\u73af\u9636\u6bb5\uff1f"
        "\u8bf7\u9a8c\u8bc1\u6574\u8f66\u3001\u7535\u6c60\u3001\u96f6\u90e8\u4ef6"
        "\u3001\u571f\u5730\u9879\u76ee\u3001\u8d22\u653f\u652f\u6301\u548c\u4f01\u4e1a\u516c\u544a\u3002"
    )
    plan = build_deterministic_retrieval_plan(query)
    required_lanes = {lane.lane_id for lane in plan.coverage_lanes if lane.required}

    assert any(region.name == "\u5408\u80a5" for region in plan.regions)
    assert CoverageLane.CITY_COUNTY_FALLBACK in required_lanes
    assert CoverageLane.PROJECT_TRANSACTION in required_lanes
    assert CoverageLane.ENTERPRISE_DISCLOSURE in required_lanes


def test_changzhou_capacity_risk_has_city_county_and_disclosure_lanes() -> None:
    query = (
        "\u5e38\u5dde\u5e02\u52a8\u529b\u7535\u6c60\u548c\u5149\u4f0f\u4ea7\u4e1a\u94fe"
        "\u662f\u5426\u5b58\u5728\u4ea7\u80fd\u96c6\u4e2d\u98ce\u9669\uff1f"
        "\u8bf7\u9a8c\u8bc1\u65b0\u589e\u4ea7\u80fd\u3001\u5f00\u5de5\u6295\u4ea7"
        "\u3001\u4f01\u4e1a\u516c\u544a\u3001\u5730\u65b9\u6276\u6301\u548c\u5e02\u573a\u4ef7\u683c\u3002"
    )
    plan = build_deterministic_retrieval_plan(query)
    required_lanes = {lane.lane_id for lane in plan.coverage_lanes if lane.required}

    assert any(region.name == "\u5e38\u5dde" for region in plan.regions)
    assert CoverageLane.CITY_COUNTY_FALLBACK in required_lanes
    assert CoverageLane.ENTERPRISE_DISCLOSURE in required_lanes
    assert CoverageLane.STATISTICS_OR_INDUSTRY_DATA in required_lanes


def test_shenmu_resource_county_query_has_statistics_and_disclosure_controls() -> None:
    query = (
        "\u795e\u6728\u5e02\u7164\u70ad\u548c\u7164\u5316\u5de5\u4ea7\u4e1a"
        "\u5728\u53cc\u78b3\u7ea6\u675f\u4e0b\u662f\u5426\u4ecd\u5177\u5907\u6269\u5f20\u7a7a\u95f4\uff1f"
        "\u8bf7\u9a8c\u8bc1\u7164\u70ad\u4ea7\u91cf\u3001\u7164\u5316\u5de5\u9879\u76ee"
        "\u3001\u73af\u8bc4\u3001\u80fd\u8017\u548c\u8d22\u653f\u4f9d\u8d56\u3002"
    )
    plan = build_deterministic_retrieval_plan(query)
    required_lanes = {lane.lane_id for lane in plan.coverage_lanes if lane.required}

    assert any(region.name == "\u795e\u6728" for region in plan.regions)
    assert CoverageLane.CITY_COUNTY_FALLBACK in required_lanes
    assert CoverageLane.PROJECT_TRANSACTION in required_lanes
    assert CoverageLane.STATISTICS_OR_INDUSTRY_DATA in required_lanes
    assert CoverageLane.ENTERPRISE_DISCLOSURE in required_lanes


def test_ruoqiang_industrialization_query_has_statistics_and_disclosure_controls() -> None:
    query = (
        "\u82e5\u7f8c\u53bf\u76d0\u6e56\u9502\u94be\u8d44\u6e90\u548c\u65b0\u80fd\u6e90\u9879\u76ee"
        "\u662f\u5426\u5177\u5907\u5b9e\u9645\u4ea7\u4e1a\u5316\u6761\u4ef6\uff1f"
        "\u8bf7\u6838\u67e5\u8d44\u6e90\u3001\u4ea4\u901a\u3001\u7535\u529b"
        "\u3001\u9879\u76ee\u5907\u6848\u3001\u73af\u8bc4\u548c\u4f01\u4e1a\u6295\u8d44\u3002"
    )
    plan = build_deterministic_retrieval_plan(query)
    required_lanes = {lane.lane_id for lane in plan.coverage_lanes if lane.required}

    assert any(region.name == "\u82e5\u7f8c" for region in plan.regions)
    assert CoverageLane.CITY_COUNTY_FALLBACK in required_lanes
    assert CoverageLane.PROJECT_TRANSACTION in required_lanes
    assert CoverageLane.STATISTICS_OR_INDUSTRY_DATA in required_lanes
    assert CoverageLane.ENTERPRISE_DISCLOSURE in required_lanes


def test_direct_keep_lanes_are_direct_primary_paths() -> None:
    plan = build_retrieval_plan("中信海直（000099.SZ）在低空经济方向有哪些公告和项目")
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}

    for lane_id in (
        CoverageLane.ENTERPRISE_DISCLOSURE,
        CoverageLane.PROJECT_TRANSACTION,
    ):
        lane = lane_by_id[lane_id]
        assert lane.execution_bucket == ExecutionBucket.DIRECT_STRUCTURED_SOURCES
        assert lane.domain_strategy == DomainStrategy.DIRECT_STRUCTURED_ONLY


def test_direct_keep_lanes_are_visible_as_control_gaps() -> None:
    query = (
        "\u795e\u6728\u5e02\u7164\u70ad\u548c\u7164\u5316\u5de5\u4ea7\u4e1a"
        "\u5728\u53cc\u78b3\u7ea6\u675f\u4e0b\u662f\u5426\u4ecd\u5177\u5907\u6269\u5f20\u7a7a\u95f4\uff1f"
        "\u8bf7\u9a8c\u8bc1\u7164\u70ad\u4ea7\u91cf\u3001\u7164\u5316\u5de5\u9879\u76ee"
        "\u3001\u73af\u8bc4\u3001\u80fd\u8017\u548c\u8d22\u653f\u4f9d\u8d56\u3002"
    )
    plan = build_retrieval_plan(query)
    gaps_by_lane = {gap.lane_id: gap for gap in plan.coverage_gaps}

    for lane_id in (
        CoverageLane.STATISTICS_OR_INDUSTRY_DATA,
        CoverageLane.PROJECT_TRANSACTION,
        CoverageLane.ENTERPRISE_DISCLOSURE,
    ):
        assert gaps_by_lane[lane_id].reason_code == "direct_structured_primary_path_required"
        assert gaps_by_lane[lane_id].fallback_level == "direct_structured_required"
        assert gaps_by_lane[lane_id].local_claim_allowed is False
        assert any("not satisfied by Tavily" in note for note in gaps_by_lane[lane_id].notes)


def test_q03_humanoid_has_no_low_altitude_supplemental_leakage() -> None:
    plan = build_deterministic_retrieval_plan("广东人形机器人产业政策和项目落地情况")
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}

    required = {
        CoverageLane.NATIONAL_POLICY_DIRECTION,
        CoverageLane.PROVINCIAL_POLICY_ROLLOUT,
        CoverageLane.PROJECT_TRANSACTION,
        CoverageLane.STATISTICS_OR_INDUSTRY_DATA,
    }
    assert required <= {lane for lane, item in lane_by_id.items() if item.required}

    supplemental = lane_by_id.get(CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL)
    if supplemental:
        assert "aopa.org.cn" not in supplemental.allowed_domains
        assert "china-uav.cn" not in supplemental.allowed_domains

    for lane in lane_by_id.values():
        joined = " ".join([*lane.search_phrases, *lane.negative_terms])
        assert "无人机" in joined or "低空经济" in joined


def test_city_and_park_queries_carry_fallback_and_gap_guard() -> None:
    plan = build_deterministic_retrieval_plan("成都人工智能产业园区有哪些政策和项目机会")
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}

    city_lane = lane_by_id[CoverageLane.CITY_COUNTY_FALLBACK]
    park_lane = lane_by_id[CoverageLane.PARK_ZONE_SIGNAL]
    assert city_lane.success_criteria.require_exact_local_match is True
    assert city_lane.success_criteria.parent_fallback_requires_gap is True
    assert "city_government_portal" in city_lane.fallback_ladder
    assert "province_government_portal" in city_lane.fallback_ladder
    assert park_lane.success_criteria.require_exact_local_match is True

    guarded_lanes = {
        gap.lane_id
        for gap in plan.coverage_gaps
        if gap.parent_evidence_only and not gap.local_claim_allowed
    }
    assert CoverageLane.CITY_COUNTY_FALLBACK in guarded_lanes
    assert CoverageLane.PARK_ZONE_SIGNAL in guarded_lanes


def test_src_cov_05_city_fallback_order_and_project_direct_keep_boundary() -> None:
    plan = build_deterministic_retrieval_plan("深圳低空经济有哪些政策和招标信号")
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}

    city_lane = lane_by_id[CoverageLane.CITY_COUNTY_FALLBACK]
    assert city_lane.fallback_ladder[:5] == [
        "exact_city_county_or_park_official_domain",
        "city_government_portal",
        "city_drc_industry_science_statistics",
        "province_government_portal",
        "province_drc_industry_science_statistics",
    ]

    project_lane = lane_by_id[CoverageLane.PROJECT_TRANSACTION]
    assert project_lane.execution_bucket == ExecutionBucket.DIRECT_STRUCTURED_SOURCES
    assert project_lane.domain_strategy == DomainStrategy.DIRECT_STRUCTURED_ONLY

    city_gap = next(
        gap for gap in plan.coverage_gaps if gap.lane_id == CoverageLane.CITY_COUNTY_FALLBACK
    )
    assert city_gap.fallback_level == "exact_local_required"
    assert city_gap.parent_evidence_only is True
    assert city_gap.local_claim_allowed is False


def test_src_cov_07_park_query_fallback_labels_require_exact_park_match() -> None:
    plan = build_deterministic_retrieval_plan("成都人工智能产业园区有哪些政策和项目机会")
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}

    park_lane = lane_by_id[CoverageLane.PARK_ZONE_SIGNAL]
    assert park_lane.fallback_ladder == [
        "park_zone_official_site",
        "city_government_portal",
        "province_government_portal",
        "national_policy_direction",
    ]
    assert park_lane.success_criteria.require_exact_local_match is True
    assert park_lane.success_criteria.parent_fallback_requires_gap is True

    park_gap = next(
        gap for gap in plan.coverage_gaps if gap.lane_id == CoverageLane.PARK_ZONE_SIGNAL
    )
    assert park_gap.fallback_level == "exact_local_required"
    assert park_gap.parent_evidence_only is True
    assert park_gap.local_claim_allowed is False


def test_unknown_theme_supplemental_does_not_default_to_all_domains() -> None:
    plan = build_deterministic_retrieval_plan("某未知新材料协会白皮书和论坛释放了什么信号")

    assert plan.planner_metadata.supplemental_domains == []
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}
    association_lane = lane_by_id[CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL]
    assert association_lane.allowed_domains == []


def test_fallback_builder_is_deterministic_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("DEEPSEEK_API_KEY", "TAVILY_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    plan = build_deterministic_retrieval_plan("广东人形机器人产业政策和项目落地情况")

    assert plan.coverage_lanes
    assert plan.planner_metadata.deterministic_fallback is True
    assert plan.planner_metadata.planner_provider == "deterministic"


def test_environmental_land_record_needs_are_visible_as_project_record_gap() -> None:
    query = (
        "内蒙古绿电、绿氢和现代煤化工项目是否具备成本与消纳优势？"
        "请核查风光资源、用电价格、项目审批、下游需求。"
    )
    plan = build_deterministic_retrieval_plan(query)

    matching_gaps = [
        gap
        for gap in plan.coverage_gaps
        if gap.reason_code == "official_record_adapter_not_available"
    ]

    assert matching_gaps
    gap = matching_gaps[0]
    assert gap.lane_id == CoverageLane.PROJECT_TRANSACTION
    assert gap.fallback_source == "environmental_or_land_record"
    assert gap.local_claim_allowed is False
    assert "source_class:environmental_or_land_record" in gap.notes


def test_employment_or_labor_needs_are_visible_as_statistics_gap() -> None:
    query = (
        "\u80a5\u897f\u53bf\u65b0\u80fd\u6e90\u6c7d\u8f66\u4ea7\u4e1a\u94fe"
        "\u662f\u5426\u53ea\u662f\u627f\u63a5\u5408\u80a5\u5916\u6ea2\uff0c"
        "\u8fd8\u662f\u5f62\u6210\u72ec\u7acb\u9879\u76ee\u96c6\u7fa4\uff1f"
        "\u8bf7\u9a8c\u8bc1\u9879\u76ee\u3001\u56ed\u533a\u3001\u4f01\u4e1a"
        "\u3001\u571f\u5730\u548c\u7528\u5de5\u6570\u636e\u3002"
    )
    plan = build_deterministic_retrieval_plan(query)

    matching_gaps = [
        gap
        for gap in plan.coverage_gaps
        if gap.reason_code == "employment_or_labor_data_adapter_not_available"
    ]

    assert matching_gaps
    gap = matching_gaps[0]
    assert gap.lane_id == CoverageLane.STATISTICS_OR_INDUSTRY_DATA
    assert gap.fallback_source == "employment_or_labor_data"
    assert gap.local_claim_allowed is False
    assert "source_class:employment_or_labor_data" in gap.notes


def test_coverage_lane_v1_is_fixed_to_nine_values() -> None:
    values = set(CoverageLane)
    assert len(values) == 9
    assert CoverageLane.MEDIA_NEWS_CONTEXT in values


def test_task_family_to_lane_mapping_is_stable() -> None:
    assert lane_for_task_family("policy_direction") == CoverageLane.NATIONAL_POLICY_DIRECTION
    assert lane_for_task_family("local_rollout") == CoverageLane.CITY_COUNTY_FALLBACK
    assert lane_for_task_family("industry_topic") == CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL
    assert lane_for_task_family("enterprise_disclosure") == CoverageLane.ENTERPRISE_DISCLOSURE
    assert lane_for_task_family("project_transaction") == CoverageLane.PROJECT_TRANSACTION
    assert lane_for_task_family("unknown_family") is None


def test_round3_eligibility_is_limited_to_supplemental_or_fallback_lanes() -> None:
    assert is_supplemental_or_fallback_lane(CoverageLane.CITY_COUNTY_FALLBACK) is True
    assert is_supplemental_or_fallback_lane(CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL) is True
    assert is_supplemental_or_fallback_lane(CoverageLane.PARK_ZONE_SIGNAL) is True
    assert is_supplemental_or_fallback_lane(CoverageLane.NATIONAL_POLICY_DIRECTION) is False


def test_phase1_retrieval_plan_marks_province_distribution_obligations() -> None:
    query = (
        "\u5b89\u5fbd\u7701\u65b0\u80fd\u6e90\u6c7d\u8f66\u4ea7\u4e1a\u94fe"
        "\u662f\u5426\u4ecd\u4f9d\u8d56\u5408\u80a5\u9f99\u5934\u5e26\u52a8\uff0c"
        "\u8fd8\u662f\u5df2\u7ecf\u5f62\u6210\u5168\u7701\u591a\u5730\u534f\u540c\uff1f"
        "\u8bf7\u4ece\u6574\u8f66\u3001\u7535\u6c60\u3001\u96f6\u90e8\u4ef6"
        "\u3001\u8d22\u653f\u8865\u8d34\u548c\u9879\u76ee\u5206\u5e03\u9a8c\u8bc1\u3002"
    )
    plan = build_deterministic_retrieval_plan(query)
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}

    rollout_obligations = set(
        lane_by_id[CoverageLane.PROVINCIAL_POLICY_ROLLOUT].evidence_obligations
    )
    project_obligations = set(lane_by_id[CoverageLane.PROJECT_TRANSACTION].evidence_obligations)

    assert "administrative_granularity:province" in rollout_obligations
    assert "multi_city_distribution" in rollout_obligations
    assert "multi_city_distribution" in project_obligations


def test_phase1_retrieval_plan_marks_multisector_and_metric_obligations() -> None:
    query = (
        "\u5e38\u5dde\u5e02\u52a8\u529b\u7535\u6c60\u548c\u5149\u4f0f\u4ea7\u4e1a\u94fe"
        "\u662f\u5426\u5b58\u5728\u4ea7\u80fd\u96c6\u4e2d\u98ce\u9669\uff1f"
        "\u8bf7\u9a8c\u8bc1\u65b0\u589e\u4ea7\u80fd\u3001\u5f00\u5de5\u6295\u4ea7"
        "\u3001\u4f01\u4e1a\u516c\u544a\u3001\u5730\u65b9\u6276\u6301\u548c\u5e02\u573a\u4ef7\u683c\u3002"
    )
    plan = build_deterministic_retrieval_plan(query)
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}

    data_obligations = set(
        lane_by_id[CoverageLane.STATISTICS_OR_INDUSTRY_DATA].evidence_obligations
    )
    disclosure_obligations = set(
        lane_by_id[CoverageLane.ENTERPRISE_DISCLOSURE].evidence_obligations
    )

    assert "administrative_granularity:city" in data_obligations
    assert "multi_sector_decomposition" in data_obligations
    assert "quantitative_metric_evidence" in data_obligations
    assert "multi_sector_decomposition" in disclosure_obligations


def test_phase1_retrieval_plan_marks_exact_local_obligations() -> None:
    query = (
        "\u80a5\u897f\u53bf\u65b0\u80fd\u6e90\u6c7d\u8f66\u4ea7\u4e1a\u94fe"
        "\u662f\u5426\u53ea\u662f\u627f\u63a5\u5408\u80a5\u5916\u6ea2\uff0c"
        "\u8fd8\u662f\u5f62\u6210\u72ec\u7acb\u9879\u76ee\u96c6\u7fa4\uff1f"
        "\u8bf7\u9a8c\u8bc1\u9879\u76ee\u3001\u56ed\u533a\u3001\u4f01\u4e1a"
        "\u3001\u571f\u5730\u548c\u7528\u5de5\u6570\u636e\u3002"
    )
    plan = build_deterministic_retrieval_plan(query)
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}

    local_obligations = set(lane_by_id[CoverageLane.CITY_COUNTY_FALLBACK].evidence_obligations)
    data_obligations = set(
        lane_by_id[CoverageLane.STATISTICS_OR_INDUSTRY_DATA].evidence_obligations
    )

    assert "administrative_granularity:county" in local_obligations
    assert "exact_local_depth" in local_obligations
    assert "exact_local_depth" in data_obligations
    assert "quantitative_metric_evidence" in data_obligations


def test_phase2_retrieval_plan_expands_province_distribution_city_hints() -> None:
    query = (
        "\u5b89\u5fbd\u7701\u65b0\u80fd\u6e90\u6c7d\u8f66\u4ea7\u4e1a\u94fe"
        "\u662f\u5426\u4ecd\u4f9d\u8d56\u5408\u80a5\u9f99\u5934\u5e26\u52a8\uff0c"
        "\u8fd8\u662f\u5df2\u7ecf\u5f62\u6210\u5168\u7701\u591a\u5730\u534f\u540c\uff1f"
        "\u8bf7\u4ece\u6574\u8f66\u3001\u7535\u6c60\u3001\u96f6\u90e8\u4ef6"
        "\u3001\u8d22\u653f\u8865\u8d34\u548c\u9879\u76ee\u5206\u5e03\u9a8c\u8bc1\u3002"
    )
    plan = build_deterministic_retrieval_plan(query)
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}

    rollout_phrases = " ".join(
        lane_by_id[CoverageLane.PROVINCIAL_POLICY_ROLLOUT].search_phrases
    )
    project_phrases = " ".join(lane_by_id[CoverageLane.PROJECT_TRANSACTION].search_phrases)

    assert "\u829c\u6e56" in rollout_phrases
    assert "\u9a6c\u978d\u5c71" in rollout_phrases
    assert "\u829c\u6e56" in project_phrases or "\u9a6c\u978d\u5c71" in project_phrases


def test_phase2_retrieval_plan_expands_multisector_project_phrases() -> None:
    query = (
        "\u6d77\u5357\u81ea\u7531\u8d38\u6613\u6e2f\u653f\u7b56\u5bf9\u5b9e\u9645"
        "\u4ea7\u4e1a\u6295\u8d44\u7684\u62c9\u52a8\u662f\u5426\u96c6\u4e2d\u5728"
        "\u65c5\u6e38\u6d88\u8d39\uff0c\u8fd8\u662f\u5df2\u7ecf\u6269\u5c55\u5230"
        "\u533b\u836f\u3001\u822a\u8fd0\u3001\u6570\u5b57\u8d38\u6613\uff1f"
        "\u8bf7\u7528\u9879\u76ee\u548c\u4f01\u4e1a\u8bc1\u636e\u9a8c\u8bc1\u3002"
    )
    plan = build_deterministic_retrieval_plan(query)
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}

    project_phrases = " ".join(lane_by_id[CoverageLane.PROJECT_TRANSACTION].search_phrases)
    data_phrases = " ".join(lane_by_id[CoverageLane.STATISTICS_OR_INDUSTRY_DATA].search_phrases)

    assert "\u6d77\u5357 \u533b\u836f \u9879\u76ee" in project_phrases
    assert "\u6d77\u5357 \u822a\u8fd0 \u9879\u76ee" in project_phrases
    assert "\u6d77\u5357 \u6570\u5b57\u8d38\u6613 \u9879\u76ee" in project_phrases
    assert "\u533b\u836f" in data_phrases
    assert "\u822a\u8fd0" in data_phrases
    assert "\u6570\u5b57\u8d38\u6613" in data_phrases
