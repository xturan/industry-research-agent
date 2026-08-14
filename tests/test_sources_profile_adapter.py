from __future__ import annotations

from packages.sources.collector_factory import CollectorExecutorFactory
from packages.sources.collectors import HtmlListDetailCollector
from packages.sources.enums import (
    AccessMethod,
    CollectorType,
    SourceCategory,
    ToolErrorCode,
    ToolStatus,
    TrustTier,
)
from packages.sources.live_fetch import LiveHtmlFetchService, build_inline_fetch_result
from packages.sources.profile_adapter import GenericProfileSourceAdapter
from packages.sources.profiles import (
    build_cn_exchange_szse_notice_v1_profile,
    build_cn_policy_ndrc_tzgg_v1_profile,
)
from packages.sources.schemas import (
    QueryContext,
    SourceAccess,
    SourceCapabilities,
    SourceProfile,
    ToolRequest,
)

NDRC_TITLE = "\u653f\u7b56\u901a\u77e5\u6807\u9898"
SZSE_TITLE = "\u6df1\u4ea4\u6240\u516c\u544a"


def _ndrc_list_html() -> str:
    return "\n".join(
        [
            '<ul class="list">',
            '  <li>',
            f'    <a href="/xwdt/tzgg/202604/t20260401_1403000.html">{NDRC_TITLE}</a>',
            '    <span>2026/04/01</span>',
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
            '      <span class="time">\u53d1\u5e03\u65f6\u95f4\uff1a2026/04/01</span>',
            '    </div>',
            '    <div class="article_con">',
            (
                '      <div class="TRS_Editor">'
                '\u652f\u6301\u91cd\u70b9\u6280\u672f\u6539\u9020\u3002'
                '</div>'
            ),
            '    </div>',
            '    <div class="attachment_r">',
            '      <a href="/files/notice-1.pdf">\u9644\u4ef6\u4e0b\u8f7d</a>',
            '    </div>',
            '  </body>',
            '</html>',
        ]
    )


def _szse_list_html() -> str:
    return "\n".join(
        [
            '<ul class="article-list">',
            '  <li>',
            '    <div class="time"><span>2026-04-10</span></div>',
            '    <script>',
            "      var curHref = './t20260410_619897.html';",
            f"      var curTitle ='{SZSE_TITLE}';",
            '    </script>',
            '  </li>',
            '</ul>',
        ]
    )


def _szse_detail_html() -> str:
    return "\n".join(
        [
            '<html>',
            '  <body>',
            '    <div class="des-header">',
            f'      <div class="title">{SZSE_TITLE}</div>',
            '      <div class="time"><span>2026-04-10</span></div>',
            '    </div>',
            (
                '    <div class="des-content">'
                '\u5bf9\u6e2f\u80a1\u901a\u6807\u7684\u8bc1\u5238\u540d\u5355'
                '\u8fdb\u884c\u8c03\u6574\u3002'
                '</div>'
            ),
            '  </body>',
            '</html>',
        ]
    )


def _nmg_stats_list_html() -> str:
    return "\n".join(
        [
            '<div class="dlp_glrtbody"><ul>',
            (
                '  <li><a href="./kjjftrtjgb/202510/t20251011_2801294.html">'
                "\u79d1\u6280\u7ecf\u8d39\u6295\u5165\u7edf\u8ba1\u516c\u62a5"
                "</a></li>"
            ),
            (
                '  <li><a href="./rkgb/202504/t20250403_2692853.html">'
                "\u5e38\u4f4f\u4eba\u53e3\u4e3b\u8981\u6570\u636e\u516c\u62a5"
                "</a></li>"
            ),
            (
                '  <li><a href="./ndtjgb/202504/t20250402_2692478.html">'
                "\u5185\u8499\u53e4\u81ea\u6cbb\u533a2024\u5e74"
                "\u56fd\u6c11\u7ecf\u6d4e\u548c\u793e\u4f1a\u53d1\u5c55\u7edf\u8ba1\u516c\u62a5"
                "</a></li>"
            ),
            "</ul></div>",
        ]
    )


def _nmg_stats_detail_html() -> str:
    return "\n".join(
        [
            "<html><body>",
            "<h1>\u5185\u8499\u53e4\u81ea\u6cbb\u533a2025\u5e74"
            "\u56fd\u6c11\u7ecf\u6d4e\u548c\u793e\u4f1a\u53d1\u5c55\u7edf\u8ba1\u516c\u62a5</h1>",
            (
                "<div class='trs_editor_view'>"
                "\u5168\u533a\u539f\u7164\u4ea7\u91cf\u3001\u53d1\u7535\u91cf"
                "\u548c\u7528\u7535\u91cf\u4fdd\u6301\u589e\u957f\uff0c"
                "\u65b0\u80fd\u6e90\u53d1\u7535\u5360\u6bd4\u63d0\u5347\u3002"
                "</div>"
            ),
            "</body></html>",
        ]
    )


def test_collector_executor_factory_returns_html_list_detail() -> None:
    profile = build_cn_policy_ndrc_tzgg_v1_profile(enabled=True)
    collector = CollectorExecutorFactory().get_collector(profile)
    assert isinstance(collector, HtmlListDetailCollector)


def test_generic_profile_source_adapter_executes_html_list_detail_path(monkeypatch) -> None:
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
    adapter = GenericProfileSourceAdapter(profile, live_fetch_service=fetch_service)
    context = QueryContext(
        query="\u90e8\u59d4\u653f\u7b56\u901a\u77e5",
        max_documents_per_source=3,
        max_evidence_per_source=3,
    )

    search = adapter.search_documents(
        ToolRequest(tool_name="search_source_documents", query_context=context)
    )
    assert search.status == ToolStatus.SUCCESS
    assert len(search.documents) == 1

    document_id = search.documents[0].document_id
    detail = adapter.fetch_document_detail(
        ToolRequest(
            tool_name="fetch_document_detail",
            query_context=context,
            document_id=document_id,
        )
    )
    assert detail.status == ToolStatus.SUCCESS
    assert detail.normalized_documents
    assert detail.normalized_documents[0].metadata["attachment_refs"]

    extract = adapter.extract_evidence_items(
        ToolRequest(
            tool_name="extract_evidence_items",
            query_context=context,
            document_id=document_id,
            max_evidence_per_source=2,
        )
    )
    assert extract.status == ToolStatus.SUCCESS
    assert extract.evidence_items
    assert extract.evidence_items[0].citation.metadata["source_name"] == profile.display_name


def test_generic_profile_source_adapter_handles_script_defined_szse_items(monkeypatch) -> None:
    profile = build_cn_exchange_szse_notice_v1_profile(enabled=True)
    fetch_service = LiveHtmlFetchService(timeout_seconds=1.0, max_retries=1, backoff_seconds=0.0)
    list_html = _szse_list_html()
    detail_html = _szse_detail_html()

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
    adapter = GenericProfileSourceAdapter(profile, live_fetch_service=fetch_service)

    search = adapter.search_documents(
        ToolRequest(
            tool_name="search_source_documents",
            query_context=QueryContext(query="\u6df1\u4ea4\u6240 \u516c\u544a \u62ab\u9732"),
        )
    )
    assert search.status == ToolStatus.SUCCESS
    assert len(search.documents) == 1
    assert search.documents[0].source_uri.endswith("t20260410_619897.html")


def test_generic_profile_source_adapter_prioritizes_relevant_statistical_bulletin(
    monkeypatch,
) -> None:
    profile = SourceProfile(
        source_id="cn_data_nmg_stats_bulletin_v1",
        display_name="Inner Mongolia Statistics Bureau Data Bulletins",
        category=SourceCategory.MACRO_DATA,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        access=SourceAccess(
            access_method=AccessMethod.WEB,
            base_url="https://tj.nmg.gov.cn",
        ),
        capabilities=SourceCapabilities(supports_search=True),
        collector_type=CollectorType.HTML_LIST_DETAIL,
        entry_urls=["https://tj.nmg.gov.cn/tjyw/tjgb/"],
        selectors={"list_item": ".dlp_glrtbody li"},
    )
    fetch_service = LiveHtmlFetchService(timeout_seconds=1.0, max_retries=1, backoff_seconds=0.0)

    def _fake_fetch_html(url: str, **kwargs):  # noqa: ANN003
        return build_inline_fetch_result(
            url=url,
            text=_nmg_stats_list_html(),
            warning="mocked_nmg_stats_list_html",
        )

    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    adapter = GenericProfileSourceAdapter(profile, live_fetch_service=fetch_service)

    search = adapter.search_documents(
        ToolRequest(
            tool_name="search_source_documents",
            query_context=QueryContext(
                query="\u5185\u8499\u53e4 \u80fd\u6e90 \u53d1\u7535\u91cf \u7528\u7535\u91cf",
                max_documents_per_source=1,
                metadata={"task_family": "data_metrics"},
            ),
        )
    )

    assert search.status == ToolStatus.SUCCESS
    assert search.documents[0].title == (
        "\u5185\u8499\u53e4\u81ea\u6cbb\u533a2024\u5e74"
        "\u56fd\u6c11\u7ecf\u6d4e\u548c\u793e\u4f1a\u53d1\u5c55\u7edf\u8ba1\u516c\u62a5"
    )


def test_generic_profile_source_adapter_hydrates_data_metrics_direct_lane_detail(
    monkeypatch,
) -> None:
    profile = SourceProfile(
        source_id="cn_data_nmg_stats_bulletin_v1",
        display_name="Inner Mongolia Statistics Bureau Data Bulletins",
        category=SourceCategory.MACRO_DATA,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        access=SourceAccess(
            access_method=AccessMethod.WEB,
            base_url="https://tj.nmg.gov.cn",
        ),
        capabilities=SourceCapabilities(supports_search=True),
        collector_type=CollectorType.HTML_LIST_DETAIL,
        entry_urls=["https://tj.nmg.gov.cn/tjyw/tjgb/"],
        selectors={
            "list_item": ".dlp_glrtbody li",
            "detail_content": ".trs_editor_view, body",
        },
    )
    fetch_service = LiveHtmlFetchService(timeout_seconds=1.0, max_retries=1, backoff_seconds=0.0)

    def _fake_fetch_html(url: str, **kwargs):  # noqa: ANN003
        return build_inline_fetch_result(
            url=url,
            text=_nmg_stats_detail_html() if "/ndtjgb/" in url else _nmg_stats_list_html(),
            warning="mocked_nmg_stats_html",
        )

    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    adapter = GenericProfileSourceAdapter(profile, live_fetch_service=fetch_service)

    search = adapter.search_documents(
        ToolRequest(
            tool_name="search_source_documents",
            query_context=QueryContext(
                query="\u5185\u8499\u53e4 \u80fd\u6e90 \u53d1\u7535\u91cf \u7528\u7535\u91cf",
                max_documents_per_source=1,
                metadata={"task_family": "data_metrics"},
            ),
            payload={
                "direct_structured_lane": True,
                "task_family": "data_metrics",
            },
        )
    )

    assert search.status == ToolStatus.SUCCESS
    assert "\u53d1\u7535\u91cf" in (search.documents[0].raw_text or "")
    assert search.normalized_documents[0].sections[0].text


def test_generic_profile_source_adapter_fails_gracefully_for_unsupported_profile() -> None:
    profile = SourceProfile(
        source_id="cn_incomplete_profile",
        display_name="Incomplete Domestic Profile",
        category=SourceCategory.POLICY_PORTAL,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        enabled=True,
        access=SourceAccess(access_method=AccessMethod.WEB, auth_required=False),
        capabilities=SourceCapabilities(
            supports_search=True,
            supports_document_detail=False,
            supports_evidence_extraction=False,
            supports_time_filter=False,
            supports_keyword_filter=True,
            supports_bulk=False,
        ),
    )
    adapter = GenericProfileSourceAdapter(profile)
    response = adapter.search_documents(
        ToolRequest(
            tool_name="search_source_documents",
            query_context=QueryContext(query="\u653f\u7b56\u901a\u77e5"),
        )
    )
    assert response.status == ToolStatus.UNSUPPORTED
    assert response.errors
    assert response.errors[0].code == ToolErrorCode.UNSUPPORTED_OPERATION
