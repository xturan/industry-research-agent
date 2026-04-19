from __future__ import annotations

from packages.sources.live_fetch import LiveHtmlFetchService, build_inline_fetch_result
from packages.sources.profile_adapter import GenericProfileSourceAdapter
from packages.sources.profiles import build_cn_policy_ndrc_tzgg_v1_profile
from packages.sources.registry import SourceRegistry
from packages.sources.router import SourceRouter
from packages.sources.schemas import QueryContext
from packages.sources.service import SourceIntelligenceService

NDRC_TITLE = "\u53d1\u6539\u59d4\u7eff\u6280\u901a\u77e5"
NDRC_QUERY = "\u90e8\u59d4\u653f\u7b56\u901a\u77e5"


def _ndrc_list_html() -> str:
    return "\n".join(
        [
            '<ul class="list">',
            '  <li>',
            f'    <a href="/xwdt/tzgg/202604/t20260408_1404000.html">{NDRC_TITLE}</a>',
            '    <span>2026/04/08</span>',
            '  </li>',
            '</ul>',
        ]
    )


def _ndrc_detail_html() -> str:
    return "\n".join(
        [
            '<html>',
            '  <body>',
            f'    <div class="article_title">{NDRC_TITLE}</div>',
            '    <div class="shezhi">',
            '      <span class="time">\u53d1\u5e03\u65f6\u95f4\uff1a2026/04/08</span>',
            '    </div>',
            '    <div class="article_con">',
            (
                '      <div class="TRS_Editor">'
                '\u63d0\u51fa\u65b0\u7684\u4ea7\u4e1a\u652f\u6301\u653f\u7b56\u3002'
                '</div>'
            ),
            '    </div>',
            '  </body>',
            '</html>',
        ]
    )


def test_router_includes_domestic_policy_source_for_chinese_query() -> None:
    router = SourceRouter(include_domestic_profiles=True)
    recommendations = router.route(QueryContext(query=NDRC_QUERY))
    assert any(item.source_id == "cn_policy_ndrc_tzgg_v1" for item in recommendations)
    policy = next(item for item in recommendations if item.source_id == "cn_policy_ndrc_tzgg_v1")
    assert policy.final_score > 0
    assert policy.score_breakdown["rule_match_score"] > 0
    assert "\u653f\u7b56" in policy.reason or "notice" in policy.reason


def test_source_service_builds_bundle_with_enabled_domestic_profile(monkeypatch) -> None:
    profile = build_cn_policy_ndrc_tzgg_v1_profile(enabled=True)
    fetch_service = LiveHtmlFetchService(timeout_seconds=1.0, max_retries=1, backoff_seconds=0.0)
    list_html = _ndrc_list_html()
    detail_html = _ndrc_detail_html()

    def _fake_fetch_html(url: str, **kwargs):  # noqa: ANN003
        if url.endswith("/index.html"):
            return build_inline_fetch_result(
                url=url,
                text=list_html,
                warning="mocked_list_html",
            )
        return build_inline_fetch_result(
            url=url,
            text=detail_html,
            warning="mocked_detail_html",
        )

    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)

    registry = SourceRegistry()
    registry.register_profile(
        profile,
        adapter=GenericProfileSourceAdapter(profile, live_fetch_service=fetch_service),
    )
    service = SourceIntelligenceService(source_registry=registry)

    response = service.build_bundle_for_query(
        QueryContext(query=NDRC_QUERY, max_sources=3)
    )
    assert response.bundle is not None
    assert response.bundle.items
    assert any(
        item.source_id == "cn_policy_ndrc_tzgg_v1"
        for item in response.route_recommendations
    )
    assert response.bundle.metadata["source_quality_summary"]["sources_attempted"] >= 1
