from __future__ import annotations

from packages.sources.registry import build_default_source_registry
from packages.sources.schemas import QueryContext, ToolRequest
from packages.sources.tools import build_source_tool_registry


def test_phase3_provincial_profiles_registered_with_adapters() -> None:
    registry = build_default_source_registry()
    profiles = {
        profile.source_id: profile for profile in registry.list_profiles(enabled_only=False)
    }
    expected = {
        "cn_policy_anhui_drc_tzgg_v1",
        "cn_policy_shandong_gxt_tzgg_v1",
    }
    assert expected.issubset(set(profiles))
    for source_id in expected:
        assert profiles[source_id].enabled is True
        assert registry.get_adapter(source_id, enabled_only=True) is not None


def test_local_rollout_pack_v2_routes_expected_sources() -> None:
    tool_registry = build_source_tool_registry(source_registry=build_default_source_registry())
    response = tool_registry.dispatch(
        ToolRequest(
            tool_name="route_research_sources",
            query_context=QueryContext(
                query="地方 项目 落地 试点 产业政策",
                source_pack="local_rollout_pack_cn_v2",
                max_sources=8,
            ),
        )
    )
    assert response.route_recommendations
    source_ids = {item.source_id for item in response.route_recommendations}
    assert source_ids <= {
        "cn_policy_anhui_drc_tzgg_v1",
        "cn_policy_shandong_gxt_tzgg_v1",
        "cn_policy_fujian_drc_tzgg_v1",
        "cn_policy_henan_gxt_tzgg_v1",
        "cn_policy_gd_drc_tzgg_v1",
        "cn_policy_js_gxt_zcwj_v1",
        "cn_policy_zhejiang_drc_tzgg_v1",
        "cn_policy_hubei_gxt_tzgg_v1",
        "cn_policy_sichuan_drc_tzgg_v1",
        "cn_policy_shanghai_portal_policy_v1",
        "cn_policy_shenzhen_gxt_tzgg_v1",
        "cn_policy_hangzhou_fgw_tzgg_v1",
        "cn_industry_association_generic",
    }
    assert {
        "cn_policy_anhui_drc_tzgg_v1",
        "cn_policy_shandong_gxt_tzgg_v1",
    } & source_ids


def test_local_rollout_strategy_v2_resolves_to_pack() -> None:
    tool_registry = build_source_tool_registry(source_registry=build_default_source_registry())
    response = tool_registry.dispatch(
        ToolRequest(
            tool_name="route_research_sources",
            query_context=QueryContext(
                query="地方 省级 产业 项目 进展",
                source_strategy="cn_local_rollout_v2",
                max_sources=8,
            ),
        )
    )
    assert response.route_recommendations
    assert all(item.selected_via == "source_strategy" for item in response.route_recommendations)
