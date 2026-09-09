from __future__ import annotations

from packages.sources.registry import build_default_source_registry
from packages.sources.schemas import QueryContext, ToolRequest
from packages.sources.tools import build_source_tool_registry


def test_phase4_city_park_profiles_registered_with_adapters() -> None:
    registry = build_default_source_registry()
    profiles = {
        profile.source_id: profile for profile in registry.list_profiles(enabled_only=False)
    }
    expected = {
        "cn_policy_guangzhou_gxt_tzgg_v1",
        "cn_policy_nanjing_gxt_tzgg_v1",
        "cn_policy_chengdu_jxj_tzgg_v1",
        "cn_park_sh_lingang_tzgg_v1",
    }
    assert expected.issubset(set(profiles))
    for source_id in expected:
        assert profiles[source_id].enabled is True
        assert registry.get_adapter(source_id, enabled_only=True) is not None


def test_city_park_pack_routes_expected_sources() -> None:
    tool_registry = build_source_tool_registry(source_registry=build_default_source_registry())
    response = tool_registry.dispatch(
        ToolRequest(
            tool_name="route_research_sources",
            query_context=QueryContext(
                query="地方 试点 项目 园区 产业 落地",
                source_pack="city_park_pack_cn_v1",
                max_sources=10,
            ),
        )
    )
    assert response.route_recommendations
    source_ids = {item.source_id for item in response.route_recommendations}
    assert source_ids <= {
        "cn_policy_shenzhen_gxt_tzgg_v1",
        "cn_policy_suzhou_drc_tzgg_v1",
        "cn_policy_hangzhou_fgw_tzgg_v1",
        "cn_policy_wuhan_gxt_tzgg_v1",
        "cn_policy_guangzhou_gxt_tzgg_v1",
        "cn_policy_nanjing_gxt_tzgg_v1",
        "cn_policy_chengdu_jxj_tzgg_v1",
        "cn_park_sh_lingang_tzgg_v1",
    }
    assert "cn_park_sh_lingang_tzgg_v1" in source_ids


def test_city_park_strategy_resolves_to_pack() -> None:
    tool_registry = build_source_tool_registry(source_registry=build_default_source_registry())
    response = tool_registry.dispatch(
        ToolRequest(
            tool_name="route_research_sources",
            query_context=QueryContext(
                query="城市 园区 项目 落地",
                source_strategy="cn_city_park_rollout",
                max_sources=10,
            ),
        )
    )
    assert response.route_recommendations
    assert all(item.selected_via == "source_strategy" for item in response.route_recommendations)
