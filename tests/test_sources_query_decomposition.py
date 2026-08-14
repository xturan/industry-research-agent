from __future__ import annotations

import pytest

from packages.sources.enums import GovernanceAxis, InfoType, LineFamily, RegionalLevel
from packages.sources.query_decomposition import (
    ALLOWED_EXECUTION_BUCKETS,
    SUPPLEMENTAL_ALLOWED_DOMAINS,
    build_query_decomposition_prompt,
    decompose_query,
    local_domains_for_task_backbones,
    local_evidence_backbones_for_task,
    repair_query_decomposition,
)


def test_decompose_anhui_low_altitude_has_required_task_families() -> None:
    decomposition = decompose_query("安徽的低空经济未来前景如何")

    task_families = {task.task_family for task in decomposition.decomposition_tasks}
    assert {
        "policy_direction",
        "local_rollout",
        "project_transaction",
        "enterprise_disclosure",
        "industry_topic",
    } <= task_families
    assert "安徽" in decomposition.regional_focus

    for task in decomposition.decomposition_tasks:
        assert 1 <= len(task.search_phrases) <= 3
        assert task.execution_bucket in ALLOWED_EXECUTION_BUCKETS

    local_rollout = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "local_rollout"
    )
    assert local_rollout.tiaokuai_axis == GovernanceAxis.BLOCK
    assert any("安徽" in phrase for phrase in local_rollout.search_phrases)


def test_macro_low_altitude_scaleout_keeps_regulator_and_project_facets() -> None:
    decomposition = decompose_query(
        "低空经济在中央层面的政策支持是否已经进入规模化落地阶段？"
        "请分别验证空域改革、适航认证、基础设施建设、地方试点和企业订单。"
    )

    task_families = {task.task_family for task in decomposition.decomposition_tasks}
    assert {
        "policy_direction",
        "local_rollout",
        "project_transaction",
        "enterprise_disclosure",
        "industry_topic",
    } <= task_families

    policy_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "policy_direction"
    )
    assert "caac.gov.cn" in policy_task.include_domains
    assert any("空域改革" in phrase for phrase in policy_task.search_phrases)
    assert any("适航" in phrase for phrase in policy_task.search_phrases)

    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )
    assert any(
        "基础设施" in phrase or "地方试点" in phrase
        for phrase in project_task.search_phrases
    )

    industry_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "industry_topic"
    )
    assert "aopa.org.cn" in industry_task.include_domains


def test_decompose_listed_company_query_preserves_direct_sources() -> None:
    decomposition = decompose_query("中信海直（000099.SZ）在低空经济方向有哪些公告和项目")

    assert {
        task.task_family for task in decomposition.decomposition_tasks
    } == {"enterprise_disclosure", "project_transaction"}
    assert {
        task.execution_bucket for task in decomposition.decomposition_tasks
    } == {"direct_structured_sources"}
    enterprise_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "enterprise_disclosure"
    )
    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )

    assert enterprise_task.execution_bucket == "direct_structured_sources"
    assert project_task.execution_bucket == "direct_structured_sources"
    assert "cninfo.com.cn" in enterprise_task.include_domains
    assert "ccgp.gov.cn" in project_task.include_domains


def test_project_query_direct_keep_does_not_emit_search_assisted_tasks() -> None:
    decomposition = decompose_query("深圳低空经济有哪些招标和中标项目？")

    assert [task.task_family for task in decomposition.decomposition_tasks] == [
        "project_transaction"
    ]
    assert decomposition.decomposition_tasks[0].execution_bucket == "direct_structured_sources"


def test_structured_data_query_direct_keep_does_not_emit_search_assisted_tasks() -> None:
    decomposition = decompose_query("国家统计局和国家能源局有哪些新能源装机与发电量数据？")

    assert [task.task_family for task in decomposition.decomposition_tasks] == [
        "data_metrics"
    ]
    assert decomposition.decomposition_tasks[0].execution_bucket == "direct_structured_sources"


def test_park_city_query_decomposes_to_holdout_marker() -> None:
    decomposition = decompose_query("成都人工智能产业园区有哪些政策和项目机会？")

    assert [task.task_family for task in decomposition.decomposition_tasks] == [
        "local_rollout"
    ]
    task = decomposition.decomposition_tasks[0]
    assert task.execution_bucket == "search_assisted_sources"
    assert task.regional_level == RegionalLevel.MUNICIPAL
    assert task.source_cluster == "park_city_rollout_backbone"


def test_supplemental_only_query_avoids_official_policy_fanout() -> None:
    decomposition = decompose_query("低空经济行业协会、白皮书和论坛最近释放了哪些产业信号？")

    assert [task.task_family for task in decomposition.decomposition_tasks] == [
        "industry_topic"
    ]
    task = decomposition.decomposition_tasks[0]
    assert task.execution_bucket == "search_assisted_sources"
    assert "aopa.org.cn" in task.include_domains
    assert task.search_phrases[0] == "低空经济 协会 白皮书 报告"


def test_compute_supplemental_query_uses_topic_platform_domains() -> None:
    decomposition = decompose_query("中国算力基础设施白皮书和产业论坛最近释放了哪些信号？")

    assert [task.task_family for task in decomposition.decomposition_tasks] == [
        "industry_topic"
    ]
    task = decomposition.decomposition_tasks[0]
    assert task.include_domains == ["cndkw.com"]
    assert task.search_phrases[0] == "算力 基础设施 白皮书 产业 报告"


def test_compute_data_metrics_prioritizes_official_energy_and_data_sources() -> None:
    decomposition = decompose_query(
        "\u201c\u4e1c\u6570\u897f\u7b97\u201d\u548c\u5168\u56fd"
        "\u4e00\u4f53\u5316\u7b97\u529b\u7f51\u7edc\u662f\u5426\u5df2"
        "\u7ecf\u8f6c\u5316\u4e3a\u771f\u5b9e\u6570\u636e\u4e2d\u5fc3"
        "\u5efa\u8bbe\u9700\u6c42\uff1f\u8bf7\u7528\u56fd\u5bb6\u653f"
        "\u7b56\u3001\u5730\u65b9\u9879\u76ee\u6e05\u5355\u3001\u7528"
        "\u7535/\u80fd\u8017\u7ea6\u675f\u3001\u670d\u52a1\u5668/IDC "
        "\u4f01\u4e1a\u516c\u544a\u4ea4\u53c9\u9a8c\u8bc1\u3002"
    )

    task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "data_metrics"
    )

    assert task.search_phrases[:3] == [
        (
            "\u56fd\u5bb6\u6570\u636e\u5c40 "
            "\u5168\u56fd\u6570\u636e\u8d44\u6e90\u8c03\u67e5\u62a5\u544a "
            "\u7b97\u529b"
        ),
        (
            "\u56fd\u5bb6\u80fd\u6e90\u5c40 "
            "\u5168\u56fd\u7535\u529b\u5de5\u4e1a\u7edf\u8ba1\u6570\u636e "
            "\u7528\u7535\u91cf"
        ),
        (
            "\u5de5\u4e1a\u548c\u4fe1\u606f\u5316\u90e8 "
            "\u7eff\u8272\u6570\u636e\u4e2d\u5fc3 \u80fd\u6548"
        ),
    ]
    assert "nda.gov.cn" in task.include_domains
    assert "nea.gov.cn" in task.include_domains
    assert "miit.gov.cn" in task.include_domains


def test_low_altitude_data_metrics_prioritizes_statistical_classification() -> None:
    decomposition = decompose_query(
        "\u4f4e\u7a7a\u7ecf\u6d4e\u5728\u4e2d\u592e\u5c42\u9762"
        "\u7684\u653f\u7b56\u652f\u6301\u662f\u5426\u5df2\u7ecf"
        "\u8fdb\u5165\u89c4\u6a21\u5316\u843d\u5730\u9636\u6bb5\uff1f"
        "\u8bf7\u5206\u522b\u9a8c\u8bc1\u7a7a\u57df\u6539\u9769\u3001"
        "\u9002\u822a\u8ba4\u8bc1\u3001\u57fa\u7840\u8bbe\u65bd\u5efa"
        "\u8bbe\u3001\u5730\u65b9\u8bd5\u70b9\u548c\u4f01\u4e1a\u8ba2\u5355\u3002"
    )

    task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "data_metrics"
    )

    assert task.search_phrases[0] == (
        "\u4f4e\u7a7a\u7ecf\u6d4e \u4ea7\u4e1a\u7edf\u8ba1\u5206\u7c7b "
        "\u56fd\u5bb6\u7edf\u8ba1\u5c40"
    )
    assert "stats.gov.cn" in task.include_domains
    assert "caac.gov.cn" in task.include_domains


def test_inner_mongolia_energy_data_metrics_use_energy_operation_sources() -> None:
    decomposition = decompose_query(
        "\u5185\u8499\u53e4\u7eff\u7535\u3001\u7eff\u6c22\u548c"
        "\u73b0\u4ee3\u7164\u5316\u5de5\u9879\u76ee\u662f\u5426"
        "\u5177\u5907\u6210\u672c\u4e0e\u6d88\u7eb3\u4f18\u52bf\uff1f"
        "\u8bf7\u6838\u67e5\u98ce\u5149\u8d44\u6e90\u3001\u7528"
        "\u7535\u4ef7\u683c\u3001\u9879\u76ee\u5ba1\u6279\u3001\u4e0b\u6e38\u9700\u6c42\u3002"
    )

    task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "data_metrics"
    )

    assert task.search_phrases[:3] == [
        (
            "\u5185\u8499\u53e4\u81ea\u6cbb\u533a\u80fd\u6e90\u5c40 "
            "\u7535\u529b\u8fd0\u884c \u53d1\u7535\u91cf \u7528\u7535\u91cf"
        ),
        (
            "\u5185\u8499\u53e4 \u7eff\u7535 \u7eff\u6c22 "
            "\u7164\u5316\u5de5 \u80fd\u8017 \u6d88\u7eb3 \u6570\u636e"
        ),
        (
            "\u5185\u8499\u53e4\u81ea\u6cbb\u533a\u7edf\u8ba1\u5c40 "
            "\u80fd\u6e90 \u7edf\u8ba1\u516c\u62a5"
        ),
    ]
    assert "tj.nmg.gov.cn" in task.include_domains
    assert "nyj.nmg.gov.cn" in task.include_domains


def test_task_family_uses_local_evidence_backbone_domain_selection() -> None:
    assert local_evidence_backbones_for_task("local_rollout") == ["local_government"]
    assert local_evidence_backbones_for_task("project_transaction") == [
        "project_public_resource"
    ]
    assert local_evidence_backbones_for_task("data_metrics") == ["statistics_fiscal"]
    assert local_evidence_backbones_for_task("official_record") == [
        "environmental_land_record"
    ]

    project_domains = local_domains_for_task_backbones(
        "project_transaction",
        ["\u80a5\u897f"],
        query="\u80a5\u897f \u65b0\u80fd\u6e90\u6c7d\u8f66 \u9879\u76ee",
    )
    rollout_domains = local_domains_for_task_backbones(
        "local_rollout",
        ["\u5408\u80a5"],
        query="\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 \u653f\u7b56",
    )
    fiscal_domains = local_domains_for_task_backbones(
        "local_rollout",
        ["\u5408\u80a5"],
        query="\u5408\u80a5 \u65b0\u80fd\u6e90\u6c7d\u8f66 \u8d22\u653f \u8865\u8d34",
    )

    assert "ggzy.hefei.gov.cn" in project_domains
    assert "fgw.hefei.gov.cn" in rollout_domains
    assert "czj.hefei.gov.cn" not in rollout_domains
    assert "czj.hefei.gov.cn" in fiscal_domains


def test_repair_missing_region_and_trim_search_phrases() -> None:
    candidate = {
        "original_query": "低空经济地方项目有哪些",
        "normalized_theme": "低空经济",
        "regional_focus": [],
        "time_horizon": "",
        "user_intent": "",
        "decomposition_tasks": [
            {
                "task_id": "local_1",
                "task_family": "local_rollout",
                "tiaokuai_axis": "invalid_axis",
                "line_family": "invalid_line",
                "regional_level": "invalid_level",
                "info_type": "invalid_type",
                "execution_bucket": "search_assisted_sources",
                "source_cluster": "local_policy_backbone",
                "include_domains": ["evil.com", "ah.gov.cn"],
                "exclude_domains": [],
                "search_phrases": [
                    "低空经济",
                    "低空经济 项目",
                    "低空经济 政策",
                    "低空经济 试点",
                ],
                "evidence_goal": "goal",
                "fallback_path": "fallback",
                "priority": 120,
                "confidence": 2,
            }
        ],
        "unsupported_or_missing_sources": [],
        "notes": [],
    }

    repaired = repair_query_decomposition(candidate)

    assert repaired.regional_focus == ["全国"]
    task = repaired.decomposition_tasks[0]
    assert task.tiaokuai_axis == GovernanceAxis.BLOCK
    assert len(task.search_phrases) == 3
    assert "evil.com" not in task.include_domains


def test_repair_direct_source_preservation_for_disclosure() -> None:
    candidate = {
        "original_query": "上市公司低空经济公告",
        "normalized_theme": "低空经济",
        "regional_focus": ["浙江"],
        "time_horizon": "latest_focus",
        "user_intent": "find disclosure",
        "decomposition_tasks": [
            {
                "task_id": "disclosure_1",
                "task_family": "enterprise_disclosure",
                "tiaokuai_axis": "mixed",
                "line_family": "exchange",
                "regional_level": "provincial",
                "info_type": "regulatory_announcement",
                "execution_bucket": "search_assisted_sources",
                "source_cluster": "official_disclosure_backbone",
                "include_domains": [],
                "exclude_domains": [],
                "search_phrases": ["低空经济 上市公司 公告"],
                "evidence_goal": "goal",
                "fallback_path": "fallback",
            }
        ],
        "unsupported_or_missing_sources": [],
        "notes": [],
    }

    repaired = repair_query_decomposition(candidate)
    task = repaired.decomposition_tasks[0]

    assert task.execution_bucket == "direct_structured_sources"
    assert "cninfo.com.cn" in task.include_domains


def test_prompt_template_can_render() -> None:
    prompt = build_query_decomposition_prompt(
        "安徽低空经济政策",
        source_taxonomy_summary="taxonomy",
        domain_allowlist="gov.cn, ndrc.gov.cn",
    )
    assert "Do not answer the query" in prompt
    assert "安徽低空经济政策" in prompt
    assert "TAVILY_API_KEY" not in prompt
    assert "Crawl4AI" not in prompt


def test_decomposition_does_not_require_tavily_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    decomposition = decompose_query("安徽的低空经济未来前景如何")

    assert decomposition.decomposition_tasks


@pytest.mark.parametrize(
    ("query",),
    [
        ("安徽的低空经济未来前景如何",),
        ("广东人形机器人产业政策和项目落地情况",),
        ("深圳低空经济有哪些政策和招标信号",),
        ("中信海直（000099.SZ）在低空经济方向有哪些公告和项目",),
        ("新能源汽车换电政策未来趋势",),
        ("江苏光伏产业链出海面临哪些政策和贸易风险",),
        ("成都人工智能产业园区有哪些政策和项目机会",),
        ("浙江低空经济相关上市公司有哪些公告",),
        ("国家层面对算力基础设施有什么最新政策方向",),
        ("某行业协会的白皮书和论坛信息如何作为补充证据",),
    ],
)
def test_phase1_queries_can_be_decomposed_offline(query: str) -> None:
    decomposition = decompose_query(query)
    assert decomposition.decomposition_tasks
    for task in decomposition.decomposition_tasks:
        assert task.execution_bucket in ALLOWED_EXECUTION_BUCKETS
        assert isinstance(task.tiaokuai_axis, GovernanceAxis)
        assert isinstance(task.line_family, LineFamily)
        assert isinstance(task.regional_level, RegionalLevel)
        assert isinstance(task.info_type, InfoType)
        assert 1 <= len(task.search_phrases) <= 3


def test_q03_local_rollout_does_not_leak_supplemental_domains() -> None:
    decomposition = decompose_query("广东人形机器人产业政策和项目落地情况")

    local_rollout = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "local_rollout"
    )
    assert "gd.gov.cn" in local_rollout.include_domains
    assert not (set(local_rollout.include_domains) & SUPPLEMENTAL_ALLOWED_DOMAINS)
    assert {"低空经济", "通航", "无人机"} <= set(local_rollout.negative_terms)


def test_unknown_theme_industry_topic_does_not_fanout_all_supplemental_domains() -> None:
    decomposition = decompose_query("某未知新材料协会白皮书和论坛释放了什么信号")

    assert [task.task_family for task in decomposition.decomposition_tasks] == [
        "industry_topic"
    ]
    task = decomposition.decomposition_tasks[0]
    assert task.include_domains == ["ccpit.org"]
    assert set(task.include_domains) != SUPPLEMENTAL_ALLOWED_DOMAINS


def test_city_park_query_includes_parent_province_domains_for_fallback() -> None:
    decomposition = decompose_query("成都人工智能产业园区有哪些政策和项目机会")

    assert [task.task_family for task in decomposition.decomposition_tasks] == [
        "local_rollout"
    ]
    task = decomposition.decomposition_tasks[0]
    assert "chengdu.gov.cn" in task.include_domains
    assert "sc.gov.cn" in task.include_domains


def test_county_district_fixture_prefers_local_then_parent_domains() -> None:
    decomposition = decompose_query("苏州工业园区光伏项目政策有哪些")

    task = decomposition.decomposition_tasks[0]
    assert task.task_family == "local_rollout"
    assert task.source_cluster == "park_city_rollout_backbone"
    assert "sipac.gov.cn" in task.include_domains
    assert "suzhou.gov.cn" in task.include_domains
    assert "jiangsu.gov.cn" in task.include_domains
    assert any("苏州工业园区" in phrase for phrase in task.search_phrases)
    assert len(task.search_phrases) <= 3
    assert not (set(task.include_domains) & SUPPLEMENTAL_ALLOWED_DOMAINS)


def test_county_park_cluster_query_keeps_direct_lanes_when_records_requested() -> None:
    decomposition = decompose_query(
        "肥西县新能源汽车产业链是否只是承接合肥外溢，还是形成独立项目集群？"
        "请验证项目、园区、企业、土地和用工数据。"
    )

    task_families = {task.task_family for task in decomposition.decomposition_tasks}
    assert {
        "local_rollout",
        "project_transaction",
        "enterprise_disclosure",
        "official_record",
    } <= task_families
    local_rollout = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "local_rollout"
    )
    assert "ahfeixi.gov.cn" in local_rollout.include_domains
    assert "gxj.hefei.gov.cn" in local_rollout.include_domains
    assert "xf.ahfeixi.gov.cn" in local_rollout.exclude_domains
    assert local_rollout.search_phrases[:3] == [
        "肥西 新能源汽车 产业集群 合肥市工业和信息化局",
        "肥西 新能源汽车 项目 园区",
        "肥西 新能源汽车 土地 用工",
    ]
    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )
    assert "ahfeixi.gov.cn" in project_task.include_domains
    assert "gxj.hefei.gov.cn" in project_task.include_domains
    assert "ggzy.hefei.gov.cn" in project_task.include_domains

    data_task = next(
        task for task in decomposition.decomposition_tasks if task.task_family == "data_metrics"
    )
    assert "ahfeixi.gov.cn" in data_task.include_domains
    assert "gxj.hefei.gov.cn" in data_task.include_domains
    assert "tjj.hefei.gov.cn" in data_task.include_domains
    assert "czj.hefei.gov.cn" in data_task.include_domains
    assert data_task.include_domains.index("ahfeixi.gov.cn") < data_task.include_domains.index(
        "ah.gov.cn"
    )
    assert data_task.include_domains.index("tjj.hefei.gov.cn") < data_task.include_domains.index(
        "stats.gov.cn"
    )
    assert data_task.search_phrases[0] == "肥西县统计局 新能源汽车 统计 数据"

    official_record_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "official_record"
    )
    assert official_record_task.execution_bucket == "direct_structured_sources"
    assert official_record_task.source_cluster == "official_record_backbone"
    assert "ahfeixi.gov.cn" in official_record_task.include_domains
    assert "sthjj.hefei.gov.cn" in official_record_task.include_domains
    assert "zrzy.hefei.gov.cn" in official_record_task.include_domains
    assert official_record_task.search_phrases[:3] == [
        "肥西县 新能源汽车 环评 公示",
        "肥西县 新能源汽车 土地出让 自然资源",
        "肥西县 新能源汽车 项目备案 审批",
    ]
    assert any(
        "土地出让" in phrase or "环评" in phrase
        for phrase in official_record_task.search_phrases
    )


def test_data_metrics_financial_queries_keep_exact_local_then_broad_fallback() -> None:
    decomposition = decompose_query(
        "神木市煤炭和煤化工产业在双碳约束下是否仍具备扩张空间？"
        "请验证煤炭产量、煤化工项目、环评、能耗和财政依赖。"
    )

    data_task = next(
        task for task in decomposition.decomposition_tasks if task.task_family == "data_metrics"
    )

    assert data_task.search_phrases[:3] == [
        "神木市统计局 煤化工 统计公报",
        "神木 煤化工 财政资金 补贴",
        "神木市财政局 煤化工 财政资金 补贴",
    ]


def test_hefei_city_industrial_cluster_preserves_local_rollout_with_direct_keep() -> None:
    decomposition = decompose_query(
        "合肥市新能源汽车产业集群是否已经从龙头企业招商进入供应链自循环阶段？"
        "请验证整车、电池、零部件、土地项目、财政支持和企业公告。"
    )

    assert decomposition.regional_focus == ["合肥"]
    task_families = {task.task_family for task in decomposition.decomposition_tasks}
    assert {
        "local_rollout",
        "project_transaction",
        "enterprise_disclosure",
        "official_record",
    } <= task_families

    official_record_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "official_record"
    )
    assert official_record_task.search_phrases[:3] == [
        "合肥市 新能源汽车 环评 公示",
        "合肥市 新能源汽车 土地出让 自然资源",
        "合肥市 新能源汽车 项目备案 审批",
    ]

    local_rollout = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "local_rollout"
    )
    assert local_rollout.execution_bucket == "search_assisted_sources"
    assert local_rollout.regional_level == RegionalLevel.MUNICIPAL
    assert "hefei.gov.cn" in local_rollout.include_domains
    assert any("合肥" in phrase for phrase in local_rollout.search_phrases)


def test_phase2_project_and_fiscal_backbones_emit_targeted_phrases() -> None:
    decomposition = decompose_query(
        "合肥市新能源汽车产业集群是否已经从龙头企业招商进入供应链自循环阶段？"
        "请验证整车、电池、零部件、土地项目、财政支持和企业公告。"
    )

    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )
    data_task = next(
        task for task in decomposition.decomposition_tasks if task.task_family == "data_metrics"
    )

    assert any(
        "项目清单" in phrase or "重点项目" in phrase for phrase in project_task.search_phrases
    )
    assert any("开工" in phrase or "投产" in phrase for phrase in project_task.search_phrases)
    assert any(
        "财政" in phrase or "补贴" in phrase or "专项资金" in phrase
        for phrase in data_task.search_phrases
    )
    assert any("统计公报" in phrase or "统计" in phrase for phrase in data_task.search_phrases)


def test_city_multisector_project_queries_keep_public_resource_in_early_budget() -> None:
    decomposition = decompose_query(
        "合肥市新能源汽车产业集群是否已经从龙头企业招商进入供应链自循环阶段？"
        "请验证整车、电池、零部件、土地项目、财政支持和企业公告。"
    )

    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )

    assert any("公共资源交易" in phrase for phrase in project_task.search_phrases[:2])
    assert any("ggzy" in domain for domain in project_task.include_domains)


def test_project_cluster_queries_prioritize_key_project_without_losing_public_resource() -> None:
    decomposition = decompose_query(
        "肥西县新能源汽车产业链是否只是承接合肥外溢，还是形成独立项目集群？"
        "请验证项目、园区、企业、土地和用工数据。"
    )

    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )

    assert project_task.search_phrases[:2] == [
        "肥西 新能源汽车 重点项目 开工 投产",
        "肥西 新能源汽车 公共资源交易 招标 中标",
    ]


def test_national_computing_query_with_local_project_list_keeps_project_lane() -> None:
    decomposition = decompose_query(
        "“东数西算”和全国一体化算力网络是否已经转化为真实数据中心建设需求？"
        "请用国家政策、地方项目清单、用电/能耗约束、服务器/IDC 企业公告交叉验证。"
    )

    task_families = {task.task_family for task in decomposition.decomposition_tasks}
    assert "project_transaction" in task_families

    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )
    assert project_task.execution_bucket == "direct_structured_sources"
    assert any("算力" in phrase for phrase in project_task.search_phrases)
    assert any(
        "招标" in phrase or "采购" in phrase
        for phrase in project_task.search_phrases[:2]
    )


def test_changzhou_capacity_risk_preserves_local_rollout_when_disclosure_needed() -> None:
    decomposition = decompose_query(
        "常州市动力电池和光伏产业链是否存在产能集中风险？"
        "请验证新增产能、开工投产、企业公告、地方扶持和市场价格。"
    )

    assert decomposition.regional_focus == ["常州"]
    task_families = {task.task_family for task in decomposition.decomposition_tasks}
    assert {"local_rollout", "enterprise_disclosure"} <= task_families

    local_rollout = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "local_rollout"
    )
    assert local_rollout.execution_bucket == "search_assisted_sources"
    assert local_rollout.regional_level == RegionalLevel.MUNICIPAL
    assert "changzhou.gov.cn" in local_rollout.include_domains
    assert any("常州" in phrase for phrase in local_rollout.search_phrases)


def test_changzhou_capacity_risk_preserves_data_metrics_for_price_signal() -> None:
    decomposition = decompose_query(
        "常州市动力电池和光伏产业链是否存在产能集中风险？"
        "请验证新增产能、开工投产、企业公告、地方扶持和市场价格。"
    )

    task_families = {task.task_family for task in decomposition.decomposition_tasks}
    assert "data_metrics" in task_families

    data_task = next(
        task for task in decomposition.decomposition_tasks if task.task_family == "data_metrics"
    )
    assert data_task.execution_bucket == "direct_structured_sources"
    assert any("常州" in phrase for phrase in data_task.search_phrases)
    assert any("价格" in phrase for phrase in data_task.search_phrases)


def test_regional_multisector_data_metrics_prioritizes_official_energy_and_stats() -> None:
    decomposition = decompose_query(
        "内蒙古绿电、绿氢和现代煤化工项目是否具备成本与消纳优势？"
        "请核查风光资源、用电价格、项目审批、下游需求。"
    )

    data_task = next(
        task for task in decomposition.decomposition_tasks if task.task_family == "data_metrics"
    )

    assert "tj.nmg.gov.cn" in data_task.include_domains
    assert "nyj.nmg.gov.cn" in data_task.include_domains
    assert "能源局" in data_task.search_phrases[0]
    assert "电力运行" in data_task.search_phrases[0]
    assert any(
        "绿电" in phrase and "绿氢" in phrase and "煤化工" in phrase
        for phrase in data_task.search_phrases[1:]
    )
    assert any(
        "统计局" in phrase and "统计公报" in phrase
        for phrase in data_task.search_phrases
    )


def test_changzhou_capacity_risk_emits_industry_capacity_market_phrases() -> None:
    decomposition = decompose_query(
        "常州市动力电池和光伏产业链是否存在产能集中风险？"
        "请验证新增产能、开工投产、企业公告、地方扶持和市场价格。"
    )

    industry_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "industry_topic"
    )
    assert any("产能" in phrase and "价格" in phrase for phrase in industry_task.search_phrases)
    assert any("行业协会" in phrase for phrase in industry_task.search_phrases)
    assert "动力电池 产能 价格 最新 行业协会" in industry_task.search_phrases
    assert "光伏 产能 价格 最新 行业协会" in industry_task.search_phrases
    assert "battery100.org" in industry_task.include_domains
    assert "chinapv.org.cn" in industry_task.include_domains


def test_industry_topic_uses_theme_specific_public_domains() -> None:
    cases = {
        (
            "安徽省新能源汽车产业链是否仍依赖合肥龙头带动，还是已经形成全省多地协同？"
            "请从整车、电池、零部件、财政补贴和项目分布验证。"
        ): {"caam.org.cn", "battery100.org"},
        (
            "海南自由贸易港政策对实际产业投资的拉动是否集中在旅游消费，"
            "还是已经扩展到医药、航运、数字贸易？请用项目和企业证据验证。"
        ): {"hiipb.com", "hiac.org.cn"},
    }
    for query, expected_domains in cases.items():
        decomposition = decompose_query(query)
        industry_task = next(
            task
            for task in decomposition.decomposition_tasks
            if task.task_family == "industry_topic"
        )
        assert expected_domains <= set(industry_task.include_domains)


def test_industry_topic_phrases_keep_region_and_sector_context() -> None:
    cases = {
        (
            "安徽省新能源汽车产业链是否仍依赖合肥龙头带动，还是已经形成全省多地协同？"
            "请从整车、电池、零部件、财政补贴和项目分布验证。"
        ): ["安徽 新能源汽车 产业链 报告"],
        (
            "海南自由贸易港政策对实际产业投资的拉动是否集中在旅游消费，"
            "还是已经扩展到医药、航运、数字贸易？请用项目和企业证据验证。"
        ): ["海南 自由贸易港 医药 航运 数字贸易 投资 报告"],
    }
    for query, expected_phrases in cases.items():
        decomposition = decompose_query(query)
        industry_task = next(
            task
            for task in decomposition.decomposition_tasks
            if task.task_family == "industry_topic"
        )
        for phrase in expected_phrases:
            assert phrase in industry_task.search_phrases


def test_changzhou_capacity_risk_preserves_project_lane_for_startup_and_ramp() -> None:
    decomposition = decompose_query(
        "常州市动力电池和光伏产业链是否存在产能集中风险？"
        "请验证新增产能、开工投产、企业公告、地方扶持和市场价格。"
    )

    task_families = {task.task_family for task in decomposition.decomposition_tasks}
    assert "project_transaction" in task_families

    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )
    assert any(
        "重点项目" in phrase or "项目清单" in phrase
        for phrase in project_task.search_phrases
    )
    assert any(
        "招标" in phrase or "采购" in phrase
        for phrase in project_task.search_phrases[:2]
    )


def test_changzhou_capacity_risk_disclosure_keeps_region_and_multisector_terms() -> None:
    decomposition = decompose_query(
        "常州市动力电池和光伏产业链是否存在产能集中风险？"
        "请验证新增产能、开工投产、企业公告、地方扶持和市场价格。"
    )

    disclosure_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "enterprise_disclosure"
    )
    assert "常州 动力电池 光伏 上市公司 公告" in disclosure_task.search_phrases


def test_real_estate_three_projects_query_preserves_project_lane_for_starts() -> None:
    decomposition = decompose_query(
        "房地产去库存、城中村改造、“三大工程”和地方收储政策是否能实质改善钢铁、"
        "水泥、家电、工程机械需求？请区分政策目标、资金来源、开工数据和企业收入。"
    )

    task_families = {task.task_family for task in decomposition.decomposition_tasks}
    assert "project_transaction" in task_families

    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )
    assert any(
        "招标" in phrase or "采购" in phrase
        for phrase in project_task.search_phrases[:2]
    )


def test_macro_real_estate_query_uses_central_housing_facets() -> None:
    decomposition = decompose_query(
        "房地产去库存、城中村改造、“三大工程”和地方收储政策是否能实质改善钢铁、"
        "水泥、家电、工程机械需求？请区分政策目标、资金来源、开工数据和企业收入。"
    )

    task_families = {task.task_family for task in decomposition.decomposition_tasks}
    assert {
        "policy_direction",
        "project_transaction",
        "enterprise_disclosure",
        "data_metrics",
    } <= task_families
    assert "local_rollout" not in task_families

    policy_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "policy_direction"
    )
    assert "mohurd.gov.cn" in policy_task.include_domains
    assert "ndrc.gov.cn" in policy_task.include_domains
    assert "stats.gov.cn" in policy_task.include_domains
    assert "www.gov.cn" in policy_task.include_domains
    assert "gov.cn" not in policy_task.include_domains
    assert any("site:mohurd.gov.cn" in phrase for phrase in policy_task.search_phrases)
    assert any("site:www.gov.cn" in phrase for phrase in policy_task.search_phrases)
    assert any("site:ndrc.gov.cn" in phrase for phrase in policy_task.search_phrases)
    assert any("城中村改造" in phrase for phrase in policy_task.search_phrases)
    assert any("三大工程" in phrase for phrase in policy_task.search_phrases)
    assert policy_task.exact_phrases == []

    data_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "data_metrics"
    )
    assert any("新开工" in phrase or "待售面积" in phrase for phrase in data_task.search_phrases)


def test_environmental_land_record_need_is_visible_in_missing_sources() -> None:
    decomposition = decompose_query(
        "神木市煤炭和煤化工产业在双碳约束下是否仍具备扩张空间？"
        "请验证煤炭产量、煤化工项目、环评、能耗和财政依赖。"
    )

    task_families = {task.task_family for task in decomposition.decomposition_tasks}
    assert "official_record" in task_families
    official_record_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "official_record"
    )
    assert official_record_task.execution_bucket == "direct_structured_sources"
    assert official_record_task.source_cluster == "official_record_backbone"
    assert "sxsm.gov.cn" in official_record_task.include_domains
    assert "tjj.shaanxi.gov.cn" in next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "data_metrics"
    ).include_domains
    assert "czt.shaanxi.gov.cn" in next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "data_metrics"
    ).include_domains
    assert any("环评" in phrase for phrase in official_record_task.search_phrases)
    assert any(
        "节能审查" in phrase or "批复" in phrase
        for phrase in official_record_task.search_phrases
    )
    assert any(
        "Environmental/land/regulatory records" in note
        for note in decomposition.unsupported_or_missing_sources
    )


def test_ruoqiang_salt_lake_official_record_uses_exact_local_record_phrases() -> None:
    decomposition = decompose_query(
        "若羌县盐湖锂钾资源和新能源项目是否具备实际产业化条件？"
        "请核查资源、交通、电力、项目备案、环评和企业投资。"
    )

    assert decomposition.regional_focus[0] == "若羌"
    official_record_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "official_record"
    )
    assert "xjrq.gov.cn" in official_record_task.include_domains
    assert "xjbz.gov.cn" in official_record_task.include_domains
    assert official_record_task.search_phrases == [
        "若羌 罗布泊 盐湖 环评 公示",
        "若羌 盐湖锂钾 项目备案 环评",
        "若羌 锂钾 矿产资源 总体规划",
    ]


def test_project_transaction_prioritizes_filing_when_query_requests_approval_evidence() -> None:
    decomposition = decompose_query(
        "若羌县盐湖锂钾资源和新能源项目是否具备实际产业化条件？"
        "请核查资源、交通、电力、项目备案、环评和企业投资。"
    )

    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )

    assert project_task.search_phrases[:2] == [
        "若羌 盐湖 项目备案 审批",
        "若羌 盐湖 重点项目 开工 投产",
    ]


def test_project_transaction_prioritizes_key_project_for_project_validation_queries() -> None:
    decomposition = decompose_query(
        "神木市煤炭和煤化工产业在双碳约束下是否仍具备扩张空间？"
        "请验证煤炭产量、煤化工项目、环评、能耗和财政依赖。"
    )

    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )

    assert project_task.search_phrases[:2] == [
        "神木 煤化工 重点项目 开工 投产",
        "神木 煤化工 项目备案 审批",
    ]


def test_shenmu_coal_chemical_official_record_uses_eia_and_energy_review_phrases() -> None:
    decomposition = decompose_query(
        "神木市煤炭和煤化工产业在双碳约束下是否仍具备扩张空间？"
        "请验证煤炭产量、煤化工项目、环评、能耗和财政依赖。"
    )

    assert decomposition.regional_focus[0] == "神木"
    official_record_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "official_record"
    )
    assert "sthjt.shaanxi.gov.cn" in official_record_task.include_domains
    assert "sndrc.shaanxi.gov.cn" in official_record_task.include_domains
    assert official_record_task.search_phrases == [
        "神木 煤化工 环境影响评价 报告书",
        "神木 兰炭 煤化工 环评 公示",
        "神木 煤化工 节能审查 批复",
    ]


def test_known_exact_local_entities_use_city_county_regional_bucket_across_lanes() -> None:
    for query in [
        (
            "神木市煤炭和煤化工产业在双碳约束下是否仍具备扩张空间？"
            "请验证煤炭产量、煤化工项目、环评、能耗和财政依赖。"
        ),
        (
            "若羌县盐湖锂钾资源和新能源项目是否具备实际产业化条件？"
            "请核查资源、交通、电力、项目备案、环评和企业投资。"
        ),
    ]:
        decomposition = decompose_query(query)
        tasks_by_family = {
            task.task_family: task for task in decomposition.decomposition_tasks
        }

        for task_family in (
            "local_rollout",
            "project_transaction",
            "data_metrics",
            "official_record",
        ):
            task = tasks_by_family[task_family]
            assert task.regional_level == RegionalLevel.MUNICIPAL
            assert "administrative_granularity:county" in task.evidence_obligations
            assert "exact_local_depth" in task.evidence_obligations


def test_inner_mongolia_green_hydrogen_official_record_uses_coal_olefin_phrases() -> None:
    decomposition = decompose_query(
        "内蒙古绿电、绿氢和现代煤化工项目是否具备成本与消纳优势？"
        "请核查风光资源、用电价格、项目审批、下游需求。"
    )

    official_record_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "official_record"
    )
    assert official_record_task.search_phrases == [
        "内蒙古 绿氢 煤制烯烃 环评 公示",
        "内蒙古 煤基新材料 环境影响评价",
        "内蒙古 现代煤化工 节能审查 批复",
    ]


def test_xian_commercial_space_project_lane_uses_city_region_not_national_prefix() -> None:
    decomposition = decompose_query(
        "西安市商业航天和硬科技产业是否形成从研发到订单的闭环？"
        "请验证高校/院所、企业、发射/卫星项目和地方基金。"
    )

    assert decomposition.regional_focus == ["西安"]
    task_families = {task.task_family for task in decomposition.decomposition_tasks}
    assert "project_transaction" in task_families

    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )
    assert project_task.regional_level == RegionalLevel.MUNICIPAL
    assert "xa.gov.cn" in project_task.include_domains
    assert any(phrase.startswith("西安 ") for phrase in project_task.search_phrases)
    assert "西安 商业航天 公共资源交易 招标 中标" in project_task.search_phrases
    assert not any(phrase.startswith("全国 ") for phrase in project_task.search_phrases)

    local_rollout = next(
        task for task in decomposition.decomposition_tasks if task.task_family == "local_rollout"
    )
    assert "xa.gov.cn" in local_rollout.include_domains
    assert "xcaib.xa.gov.cn" in local_rollout.include_domains
    assert "shaanxi.gov.cn" not in local_rollout.include_domains
    assert "kjt.shaanxi.gov.cn" not in local_rollout.include_domains


def test_xian_commercial_space_local_rollout_covers_fund_and_research_signals() -> None:
    decomposition = decompose_query(
        "西安市商业航天和硬科技产业是否形成从研发到订单的闭环？"
        "请验证高校/院所、企业、发射/卫星项目和地方基金。"
    )

    local_rollout = next(
        task for task in decomposition.decomposition_tasks if task.task_family == "local_rollout"
    )
    assert any("国家民用航天产业基地" in phrase for phrase in local_rollout.search_phrases)
    assert any("地方基金" in phrase for phrase in local_rollout.search_phrases)
    assert any("高校" in phrase or "院所" in phrase for phrase in local_rollout.search_phrases)


def test_low_altitude_scaleout_data_metrics_uses_scale_and_order_terms() -> None:
    decomposition = decompose_query(
        "低空经济在中央层面的政策支持是否已经进入规模化落地阶段？"
        "请分别验证空域改革、适航认证、基础设施建设、地方试点和企业订单。"
    )

    data_task = next(
        task for task in decomposition.decomposition_tasks if task.task_family == "data_metrics"
    )
    assert any("市场规模" in phrase for phrase in data_task.search_phrases)
    assert any("企业订单" in phrase or "订单" in phrase for phrase in data_task.search_phrases)


def test_disclosure_control_lane_is_present_for_smoke_blocker_cases() -> None:
    queries = [
        (
            "房地产去库存、城中村改造、“三大工程”和地方收储政策是否能实质改善钢铁、"
            "水泥、家电、工程机械需求？请区分政策目标、资金来源、开工数据和企业收入。"
        ),
        (
            "内蒙古绿电、绿氢和现代煤化工项目是否具备成本与消纳优势？"
            "请核查风光资源、用电价格、项目审批、下游需求。"
        ),
        (
            "安徽省新能源汽车产业链是否仍依赖合肥龙头带动，还是已经形成全省多地协同？"
            "请从整车、电池、零部件、财政补贴和项目分布验证。"
        ),
        (
            "神木市煤炭和煤化工产业在双碳约束下是否仍具备扩张空间？"
            "请验证煤炭产量、煤化工项目、环评、能耗和财政依赖。"
        ),
        (
            "西安市商业航天和硬科技产业是否形成从研发到订单的闭环？"
            "请验证高校/院所、企业、发射/卫星项目和地方基金。"
        ),
    ]

    for query in queries:
        decomposition = decompose_query(query)
        task_families = {task.task_family for task in decomposition.decomposition_tasks}
        assert "enterprise_disclosure" in task_families


def test_quantity_validation_terms_emit_data_metrics_lane() -> None:
    queries = [
        (
            "安徽省新能源汽车产业链是否仍依赖合肥龙头带动，还是已经形成全省多地协同？"
            "请从整车、电池、零部件、财政补贴和项目分布验证。"
        ),
        (
            "神木市煤炭和煤化工产业在双碳约束下是否仍具备扩张空间？"
            "请验证煤炭产量、煤化工项目、环评、能耗和财政依赖。"
        ),
        (
            "海南自由贸易港政策对实际产业投资的拉动是否集中在旅游消费，"
            "还是已经扩展到医药、航运、数字贸易？请用项目和企业证据验证。"
        ),
    ]

    for query in queries:
        decomposition = decompose_query(query)
        task_families = {task.task_family for task in decomposition.decomposition_tasks}
        assert "data_metrics" in task_families


def test_phase1_province_distribution_query_exposes_multicity_obligation() -> None:
    decomposition = decompose_query(
        "安徽省新能源汽车产业链是否仍依赖合肥龙头带动，还是已经形成全省多地协同？"
        "请从整车、电池、零部件、财政补贴和项目分布验证。"
    )

    obligations_by_family = {
        task.task_family: set(task.evidence_obligations)
        for task in decomposition.decomposition_tasks
    }

    assert "administrative_granularity:province" in obligations_by_family["local_rollout"]
    assert "multi_city_distribution" in obligations_by_family["local_rollout"]
    assert "multi_city_distribution" in obligations_by_family["project_transaction"]
    assert "quantitative_metric_evidence" in obligations_by_family["data_metrics"]


def test_phase1_multisector_query_exposes_sector_obligation() -> None:
    decomposition = decompose_query(
        "海南自由贸易港政策对实际产业投资的拉动是否集中在旅游消费，"
        "还是已经扩展到医药、航运、数字贸易？请用项目和企业证据验证。"
    )

    obligations_by_family = {
        task.task_family: set(task.evidence_obligations)
        for task in decomposition.decomposition_tasks
    }

    assert "multi_sector_decomposition" in obligations_by_family["local_rollout"]
    assert "multi_sector_decomposition" in obligations_by_family["project_transaction"]
    assert "multi_sector_decomposition" in obligations_by_family["enterprise_disclosure"]


def test_phase1_county_query_exposes_exact_local_and_metric_obligations() -> None:
    decomposition = decompose_query(
        "肥西县新能源汽车产业链是否只是承接合肥外溢，还是形成独立项目集群？"
        "请验证项目、园区、企业、土地和用工数据。"
    )

    obligations_by_family = {
        task.task_family: set(task.evidence_obligations)
        for task in decomposition.decomposition_tasks
    }

    assert "administrative_granularity:county" in obligations_by_family["local_rollout"]
    assert "exact_local_depth" in obligations_by_family["local_rollout"]
    assert "exact_local_depth" in obligations_by_family["official_record"]
    assert "quantitative_metric_evidence" in obligations_by_family["data_metrics"]


def test_phase2_province_distribution_expands_non_anchor_city_sources() -> None:
    decomposition = decompose_query(
        "安徽省新能源汽车产业链是否仍依赖合肥龙头带动，还是已经形成全省多地协同？"
        "请从整车、电池、零部件、财政补贴和项目分布验证。"
    )

    local_rollout = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "local_rollout"
    )
    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )
    data_task = next(
        task for task in decomposition.decomposition_tasks if task.task_family == "data_metrics"
    )

    assert "wuhu.gov.cn" in local_rollout.include_domains
    assert "mas.gov.cn" in local_rollout.include_domains
    assert any("芜湖" in phrase or "马鞍山" in phrase for phrase in local_rollout.search_phrases)
    assert any("芜湖" in phrase or "马鞍山" in phrase for phrase in project_task.search_phrases)
    assert data_task.search_phrases[0] == "安徽省统计局 新能源汽车 统计公报"
    assert any("芜湖" in phrase or "马鞍山" in phrase for phrase in data_task.search_phrases)


def test_phase2_multisector_query_expands_sector_specific_phrases() -> None:
    decomposition = decompose_query(
        "海南自由贸易港政策对实际产业投资的拉动是否集中在旅游消费，"
        "还是已经扩展到医药、航运、数字贸易？请用项目和企业证据验证。"
    )

    project_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "project_transaction"
    )
    data_task = next(
        task for task in decomposition.decomposition_tasks if task.task_family == "data_metrics"
    )

    joined_project_phrases = " ".join(project_task.search_phrases)
    assert "海南 医药 项目" in joined_project_phrases
    assert "海南 航运 项目" in joined_project_phrases
    assert "海南 数字贸易 项目" in joined_project_phrases
    assert any(
        "医药" in phrase and "航运" in phrase and "数字贸易" in phrase
        for phrase in data_task.search_phrases
    )


def test_phase3_generic_county_level_city_gets_exact_local_gov_seed() -> None:
    decomposition = decompose_query(
        "昆山市电子信息和台资制造业是否面临产业链外迁压力？"
        "请同时验证出口数据、重点企业投资、园区项目和地方稳外资政策。"
    )

    assert decomposition.regional_focus == ["昆山"]
    local_rollout = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "local_rollout"
    )
    data_task = next(
        task for task in decomposition.decomposition_tasks if task.task_family == "data_metrics"
    )

    assert local_rollout.regional_level == RegionalLevel.MUNICIPAL
    assert "administrative_granularity:city" in local_rollout.evidence_obligations
    assert "exact_local_depth" in local_rollout.evidence_obligations
    assert "gov.cn" in local_rollout.include_domains
    assert "gov.cn" in data_task.include_domains
    assert any(phrase.startswith("昆山 ") for phrase in local_rollout.search_phrases)


def test_phase3_generic_county_query_gets_exact_local_gov_seed_across_lanes() -> None:
    decomposition = decompose_query(
        "曹县电商产业是否已经从网红流量转向稳定制造和供应链能力？"
        "请验证企业数量、产业带、物流、税收和平台数据。"
    )

    assert decomposition.regional_focus == ["曹县"]
    local_rollout = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "local_rollout"
    )
    data_task = next(
        task for task in decomposition.decomposition_tasks if task.task_family == "data_metrics"
    )

    assert local_rollout.regional_level == RegionalLevel.MUNICIPAL
    assert "administrative_granularity:county" in local_rollout.evidence_obligations
    assert "exact_local_depth" in local_rollout.evidence_obligations
    assert "quantitative_metric_evidence" in data_task.evidence_obligations
    assert "gov.cn" in local_rollout.include_domains
    assert "gov.cn" in data_task.include_domains
    assert any(phrase.startswith("曹县 ") for phrase in local_rollout.search_phrases)
    assert any(phrase.startswith("曹县 ") for phrase in data_task.search_phrases)


def test_phase4_known_exact_local_rollout_keeps_local_domains_before_parent() -> None:
    cases = [
        (
            "神木市煤炭和煤化工产业在双碳约束下是否仍具备扩张空间？"
            "请验证煤炭产量、煤化工项目、环评、能耗和财政依赖。",
            "sxsm.gov.cn",
            "shaanxi.gov.cn",
        ),
        (
            "若羌县盐湖锂钾资源和新能源项目是否具备实际产业化条件？"
            "请核查资源、交通、电力、项目备案、环评和企业投资。",
            "xjrq.gov.cn",
            "xinjiang.gov.cn",
        ),
    ]

    for query, exact_domain, parent_domain in cases:
        decomposition = decompose_query(query)
        local_rollout = next(
            task
            for task in decomposition.decomposition_tasks
            if task.task_family == "local_rollout"
        )

        assert local_rollout.include_domains[0] == exact_domain
        assert parent_domain not in local_rollout.include_domains[:1]


def test_phase5_macro_policy_to_demand_query_requires_local_fanout() -> None:
    decomposition = decompose_query(
        "“东数西算”和全国一体化算力网络是否已经转化为真实数据中心建设需求？"
        "请用国家政策、地方项目清单、用电/能耗约束、服务器/IDC 企业公告交叉验证。"
    )

    task_by_family = {
        task.task_family: task for task in decomposition.decomposition_tasks
    }

    assert {
        "policy_direction",
        "local_rollout",
        "project_transaction",
        "data_metrics",
        "enterprise_disclosure",
    } <= set(task_by_family)

    for task_family in ("local_rollout", "project_transaction", "data_metrics"):
        assert (
            "macro_to_local_obligation"
            in task_by_family[task_family].evidence_obligations
        )

    local_rollout = task_by_family["local_rollout"]
    assert local_rollout.regional_level == RegionalLevel.PROVINCIAL
    assert "gov.cn" in local_rollout.include_domains
    assert any(
        "地方" in phrase or "省市" in phrase
        for phrase in local_rollout.search_phrases
    )
    assert not all(
        phrase.startswith("全国 ") for phrase in local_rollout.search_phrases
    )

    project_task = task_by_family["project_transaction"]
    assert not all(
        phrase.startswith("全国 ") for phrase in project_task.search_phrases
    )
