from __future__ import annotations

from packages.sources.registry import build_default_source_registry
from packages.sources.schemas import QueryContext, ToolRequest
from packages.sources.tools import build_source_tool_registry


def test_phase1_sample_profiles_registered_with_adapters() -> None:
    registry = build_default_source_registry()
    profiles = {
        profile.source_id: profile for profile in registry.list_profiles(enabled_only=False)
    }

    expected = {
        "cn_policy_state_council_zcwj_v1",
        "cn_policy_miit_tzgg_v1",
        "cn_exchange_sse_notice_v1",
        "cn_exchange_cninfo_announcement_v1",
        "cn_policy_gd_drc_tzgg_v1",
        "cn_policy_js_gxt_zcwj_v1",
        "cn_policy_shenzhen_gxt_tzgg_v1",
        "cn_policy_hangzhou_fgw_tzgg_v1",
    }
    assert expected.issubset(set(profiles))

    for source_id in expected:
        assert profiles[source_id].enabled is True
        assert registry.get_adapter(source_id, enabled_only=True) is not None


def test_policy_pack_v2_routes_policy_backbone_sources() -> None:
    tool_registry = build_source_tool_registry(source_registry=build_default_source_registry())
    response = tool_registry.dispatch(
        ToolRequest(
            tool_name="route_research_sources",
            query_context=QueryContext(
                query="部委 政策 通知 产业链 影响",
                source_pack="policy_pack_cn_v2",
                max_sources=6,
            ),
        )
    )
    assert response.route_recommendations
    source_ids = {item.source_id for item in response.route_recommendations}
    assert source_ids <= {
        "cn_policy_state_council_zcwj_v1",
        "cn_policy_ndrc_tzgg_v1",
        "cn_policy_miit_tzgg_v1",
        "cn_policy_generic",
    }


def test_disclosure_pack_v2_routes_disclosure_backbone_sources() -> None:
    tool_registry = build_source_tool_registry(source_registry=build_default_source_registry())
    response = tool_registry.dispatch(
        ToolRequest(
            tool_name="route_research_sources",
            query_context=QueryContext(
                query="交易所 披露 公告 年报",
                source_pack="disclosure_pack_cn_v2",
                max_sources=6,
            ),
        )
    )
    assert response.route_recommendations
    source_ids = {item.source_id for item in response.route_recommendations}
    assert source_ids <= {
        "cn_exchange_sse_notice_v1",
        "cn_exchange_szse_notice_v1",
        "cn_exchange_cninfo_announcement_v1",
        "cn_exchange_announcement_generic",
    }
