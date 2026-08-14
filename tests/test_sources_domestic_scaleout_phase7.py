from __future__ import annotations

from packages.sources.enums import GovernanceAxis, InfoType, LineFamily, RegionalLevel
from packages.sources.packs import get_source_pack
from packages.sources.query_decomposition import (
    SUPPLEMENTAL_ALLOWED_DOMAINS,
    decompose_query,
)
from packages.sources.registry import build_default_source_registry
from packages.sources.retrieval_plan import (
    CoverageLane,
    SourceIntent,
    build_deterministic_retrieval_plan,
)
from packages.sources.router import SourceRouter
from packages.sources.schemas import QueryContext
from packages.sources.source_resolver import evaluate_candidate_compatibility


def test_phase4_backbone_profiles_registered_with_adapters() -> None:
    registry = build_default_source_registry()
    profiles = {
        profile.source_id: profile for profile in registry.list_profiles(enabled_only=False)
    }
    expected = {
        "cn_policy_ndrc_tzgg_v1",
        "cn_policy_most_tzgg_v1",
        "cn_data_stats_national_v1",
        "cn_data_customs_trade_v1",
        "cn_trade_mofcom_policy_v1",
        "cn_policy_gd_portal_policy_v1",
        "cn_data_js_stats_bulletin_v1",
        "cn_policy_ah_kjt_tzgg_v1",
        "cn_trade_zj_commerce_policy_v1",
        "cn_data_sc_stats_bulletin_v1",
        "cn_policy_sh_stcsm_tzgg_v1",
    }
    assert expected.issubset(set(profiles))
    for source_id in expected:
        assert profiles[source_id].enabled is True
        assert registry.get_adapter(source_id, enabled_only=True) is not None


def test_default_router_q03_does_not_fanout_to_unrelated_regions_or_city_park() -> None:
    router = SourceRouter(include_domestic_profiles=True)
    recommendations = router.route(
        QueryContext(
            query="广东人形机器人产业政策和项目落地情况",
            max_sources=30,
        )
    )
    source_ids = {item.source_id for item in recommendations}

    assert {
        "cn_policy_gd_portal_policy_v1",
        "cn_policy_gd_drc_tzgg_v1",
        "cn_policy_gd_industry_gdii_v1",
    } & source_ids
    assert not (
        source_ids
        & {
            "cn_policy_js_portal_policy_v1",
            "cn_policy_js_gxt_zcwj_v1",
            "cn_policy_anhui_drc_tzgg_v1",
            "cn_policy_shandong_gxt_tzgg_v1",
            "cn_policy_shenzhen_gxt_tzgg_v1",
            "cn_park_sh_lingang_tzgg_v1",
        }
    )


def test_default_router_generic_local_rollout_does_not_include_city_park_sources() -> None:
    router = SourceRouter(include_domestic_profiles=True)
    recommendations = router.route(
        QueryContext(
            query="地方 项目 落地 情况",
            max_sources=30,
        )
    )
    source_ids = {item.source_id for item in recommendations}

    assert not any("park" in source_id for source_id in source_ids)
    assert not any(
        source_id.startswith(
            (
                "cn_policy_shenzhen_",
                "cn_policy_suzhou_",
                "cn_policy_hangzhou_",
                "cn_policy_wuhan_",
                "cn_policy_guangzhou_",
                "cn_policy_nanjing_",
                "cn_policy_chengdu_",
            )
        )
        for source_id in source_ids
    )


def test_phase4_policy_data_backbone_pack_excludes_city_county_park_sources() -> None:
    pack = get_source_pack("policy_data_backbone_pack_cn_v1")
    assert pack is not None

    assert pack.source_ids
    assert not any("park" in source_id for source_id in pack.source_ids)
    assert not any(
        source_id.startswith((
            "cn_policy_shenzhen_",
            "cn_policy_suzhou_",
            "cn_policy_hangzhou_",
            "cn_policy_wuhan_",
            "cn_policy_guangzhou_",
            "cn_policy_nanjing_",
            "cn_policy_chengdu_",
        ))
        for source_id in pack.source_ids
    )


def test_q03_local_rollout_primary_domains_keep_official_guangdong_only() -> None:
    decomposition = decompose_query("广东人形机器人产业政策和项目落地情况")
    local_rollout = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "local_rollout"
    )

    assert "gd.gov.cn" in local_rollout.include_domains
    assert "drc.gd.gov.cn" in local_rollout.include_domains
    assert not (set(local_rollout.include_domains) & {"aopa.org.cn", "china-uav.cn"})
    assert not (set(local_rollout.include_domains) & SUPPLEMENTAL_ALLOWED_DOMAINS)


def test_unknown_supplemental_theme_still_has_no_fanout() -> None:
    decomposition = decompose_query("某未知新材料协会白皮书和论坛释放了什么信号")

    assert [task.task_family for task in decomposition.decomposition_tasks] == ["industry_topic"]
    task = decomposition.decomposition_tasks[0]
    assert task.include_domains == []


def test_src_cov_04_router_and_plan_cover_customs_and_commerce() -> None:
    query = "江苏光伏产业链出海面临哪些政策和贸易风险"
    plan = build_deterministic_retrieval_plan(query)
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}
    data_lane = lane_by_id[CoverageLane.STATISTICS_OR_INDUSTRY_DATA]

    assert {
        SourceIntent.NATIONAL_CUSTOMS,
        SourceIntent.NATIONAL_COMMERCE,
        SourceIntent.PROVINCE_COMMERCE,
    } <= set(data_lane.source_intents)

    router = SourceRouter(include_domestic_profiles=True)
    recommendations = router.route(
        QueryContext(
            query=query,
            source_strategy="cn_policy_data_backbone_v1",
            max_sources=20,
        )
    )
    source_ids = {item.source_id for item in recommendations}
    assert "cn_data_customs_trade_v1" in source_ids
    assert "cn_trade_mofcom_policy_v1" in source_ids
    assert "cn_trade_js_commerce_policy_v1" in source_ids


def test_source_resolver_accepts_new_provincial_official_domain_region_match() -> None:
    from packages.sources.query_decomposition import QueryDecompositionTask

    task = QueryDecompositionTask(
        task_id="local_rollout_1",
        task_family="local_rollout",
        tiaokuai_axis=GovernanceAxis.BLOCK,
        line_family=LineFamily.POLICY,
        regional_level=RegionalLevel.PROVINCIAL,
        info_type=InfoType.POLICY_NOTICE,
        execution_bucket="search_assisted_sources",
        source_cluster="province_or_city_backbone",
        include_domains=["tjj.jiangsu.gov.cn"],
        search_phrases=["江苏 人形机器人 政策"],
        evidence_goal="collect",
        fallback_path="fallback",
    )

    accepted = evaluate_candidate_compatibility(
        task=task,
        query="江苏人形机器人产业政策和项目落地情况",
        url="https://www.tjj.jiangsu.gov.cn/art/2026/4/8/art_1.html",
        domain="www.tjj.jiangsu.gov.cn",
        title="江苏 人形机器人 统计 公报",
        snippet="江苏 产业 统计 数据",
        allowed_domains={"tjj.jiangsu.gov.cn", "gov.cn"},
    )
    assert accepted.decision == "accept"
