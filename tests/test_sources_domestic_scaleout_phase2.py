from __future__ import annotations

from packages.sources.registry import build_default_source_registry
from packages.sources.schemas import QueryContext, ToolRequest
from packages.sources.tools import build_source_tool_registry


def test_phase2_project_profiles_registered_with_adapters() -> None:
    registry = build_default_source_registry()
    profiles = {
        profile.source_id: profile for profile in registry.list_profiles(enabled_only=False)
    }
    expected = {
        "cn_project_ccgp_procurement_v1",
        "cn_project_ggzy_trade_v1",
        "cn_project_ndrc_approval_v1",
    }
    assert expected.issubset(set(profiles))
    for source_id in expected:
        assert profiles[source_id].enabled is True
        assert registry.get_adapter(source_id, enabled_only=True) is not None
    assert profiles["cn_project_ccgp_procurement_v1"].selectors["list_item"] == ".ulst li"
    assert profiles["cn_project_ggzy_trade_v1"].entry_urls == [
        "https://www.ggzy.gov.cn/deal/dealList.html"
    ]
    assert profiles["cn_project_ndrc_approval_v1"].entry_urls == [
        "https://www.ndrc.gov.cn/fgsj/tzcx/"
    ]


def test_inner_mongolia_statistics_profile_uses_bulletin_entry_url() -> None:
    registry = build_default_source_registry()
    profiles = {
        profile.source_id: profile for profile in registry.list_profiles(enabled_only=False)
    }

    assert profiles["cn_data_nmg_stats_bulletin_v1"].entry_urls == [
        "https://tj.nmg.gov.cn/tjyw/tjgb/"
    ]
    assert profiles["cn_data_nmg_stats_bulletin_v1"].selectors["list_item"] == (
        ".dlp_glrtbody li"
    )


def test_project_signal_pack_routes_expected_sources() -> None:
    tool_registry = build_source_tool_registry(source_registry=build_default_source_registry())
    response = tool_registry.dispatch(
        ToolRequest(
            tool_name="route_research_sources",
            query_context=QueryContext(
                query="政府采购 公共资源交易 投资项目审批",
                source_pack="project_signal_pack_cn_v1",
                max_sources=6,
            ),
        )
    )
    assert response.route_recommendations
    source_ids = {item.source_id for item in response.route_recommendations}
    assert source_ids <= {
        "cn_project_ccgp_procurement_v1",
        "cn_project_ggzy_trade_v1",
        "cn_project_ndrc_approval_v1",
    }


def test_project_strategy_resolves_to_project_pack() -> None:
    tool_registry = build_source_tool_registry(source_registry=build_default_source_registry())
    response = tool_registry.dispatch(
        ToolRequest(
            tool_name="route_research_sources",
            query_context=QueryContext(
                query="项目 招标 中标",
                source_strategy="cn_project_signal",
                max_sources=6,
            ),
        )
    )
    assert response.route_recommendations
    assert all(item.selected_via == "source_strategy" for item in response.route_recommendations)
