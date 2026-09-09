from __future__ import annotations

from packages.sources.live_fetch import (
    LiveHtmlFetchError,
    LiveHtmlFetchService,
    build_inline_fetch_result,
)
from packages.sources.profile_adapter import GenericProfileSourceAdapter
from packages.sources.profiles import (
    build_cn_exchange_szse_notice_v1_profile,
    build_cn_policy_ndrc_tzgg_v1_profile,
)
from packages.sources.registry import SourceRegistry
from packages.sources.schemas import QueryContext, ToolRequest
from packages.sources.service import SourceIntelligenceService

NDRC_TITLE = "\u53d1\u6539\u59d4\u7eff\u6280\u901a\u77e5"
SZSE_TITLE = "\u6df1\u4ea4\u6240\u516c\u544a"
NDRC_PUBLISHER = "\u56fd\u5bb6\u53d1\u5c55\u548c\u6539\u9769\u59d4\u5458\u4f1a"
SZSE_PUBLISHER = "\u6df1\u5733\u8bc1\u5238\u4ea4\u6613\u6240"


def _build_ndrc_list_html() -> str:
    return "\n".join(
        [
            '<ul class="list">',
            '  <li>',
            f'    <a href="/xwdt/tzgg/202604/t20260409_1404477.html">{NDRC_TITLE}</a>',
            '    <span>2026/04/09</span>',
            '  </li>',
            '</ul>',
        ]
    )


def _build_ndrc_detail_html(*, with_attachment: bool = True) -> str:
    rows = [
        '<html>',
        '  <body>',
        f'    <div class="article_title">{NDRC_TITLE}</div>',
        '    <div class="shezhi">',
        '      <span class="time">\u53d1\u5e03\u65f6\u95f4\uff1a2026/04/09</span>',
        '    </div>',
        '    <div class="article_con">',
        (
            '      <div class="TRS_Editor">'
            '\u63a8\u8fdb\u7eff\u8272\u4f4e\u78b3\u5148\u8fdb\u6280\u672f'
            '\u5e94\u7528\u793a\u8303\u3002'
            '</div>'
        ),
        '    </div>',
    ]
    if with_attachment:
        rows.extend(
            [
                '    <div class="attachment_r">',
                (
                    '      <a href="/xxgk/zcfb/tz/202604/'
                    'P020260409000000000000.pdf">'
                    '\u9644\u4ef6\uff1a\u7533\u62a5\u6307\u5357.pdf'
                    '</a>'
                ),
                '    </div>',
            ]
        )
    rows.extend(['  </body>', '</html>'])
    return "\n".join(rows)


def _build_szse_list_html() -> str:
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


def _build_szse_detail_html() -> str:
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


def test_ndrc_real_profile_end_to_end_with_attachment(monkeypatch) -> None:
    profile = build_cn_policy_ndrc_tzgg_v1_profile(enabled=True)
    fetch_service = LiveHtmlFetchService(timeout_seconds=1.0, max_retries=1, backoff_seconds=0.0)
    list_html = _build_ndrc_list_html()
    detail_html = _build_ndrc_detail_html(with_attachment=True)

    def _fake_fetch_html(url: str, **kwargs):  # noqa: ANN003
        if url.endswith("/index.html"):
            return build_inline_fetch_result(
                url=url,
                text=list_html,
                warning="mocked_ndrc_list_html",
            )
        return build_inline_fetch_result(
            url=url,
            text=detail_html,
            warning="mocked_ndrc_detail_html",
        )

    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    adapter = GenericProfileSourceAdapter(profile, live_fetch_service=fetch_service)
    request = ToolRequest(
        tool_name="search_source_documents",
        query_context=QueryContext(
            query="\u53d1\u6539\u59d4 \u653f\u7b56 \u901a\u77e5",
            max_documents_per_source=3,
        ),
    )

    search = adapter.search_documents(request)
    assert search.status.value == "success"
    assert len(search.documents) == 1
    assert search.normalized_documents[0].metadata["publisher"] == NDRC_PUBLISHER

    detail = adapter.fetch_document_detail(
        ToolRequest(
            tool_name="fetch_document_detail",
            query_context=request.query_context,
            document_id=search.documents[0].document_id,
        )
    )
    assert detail.status.value == "success"
    assert detail.normalized_documents
    assert detail.normalized_documents[0].metadata["attachment_refs"]
    assert detail.normalized_documents[0].metadata["detail_url"].endswith(".html")

    extract = adapter.extract_evidence_items(
        ToolRequest(
            tool_name="extract_evidence_items",
            query_context=QueryContext(
                query="\u53d1\u6539\u59d4 \u7eff\u6280",
                max_evidence_per_source=2,
            ),
            document_id=search.documents[0].document_id,
        )
    )
    assert extract.status.value == "success"
    assert extract.evidence_items
    assert extract.evidence_items[0].citation.metadata["source_name"] == "NDRC Notices"
    assert extract.evidence_items[0].citation.metadata["published_at"] == "2026-04-09T00:00:00"


def test_szse_real_profile_script_defined_list_parsing(monkeypatch) -> None:
    profile = build_cn_exchange_szse_notice_v1_profile(enabled=True)
    fetch_service = LiveHtmlFetchService(timeout_seconds=1.0, max_retries=1, backoff_seconds=0.0)
    list_html = _build_szse_list_html()
    detail_html = _build_szse_detail_html()

    def _fake_fetch_html(url: str, **kwargs):  # noqa: ANN003
        if url.endswith("/index.html"):
            return build_inline_fetch_result(
                url=url,
                text=list_html,
                warning="mocked_szse_list_html",
            )
        return build_inline_fetch_result(
            url=url,
            text=detail_html,
            warning="mocked_szse_detail_html",
        )

    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    adapter = GenericProfileSourceAdapter(profile, live_fetch_service=fetch_service)

    search = adapter.search_documents(
        ToolRequest(
            tool_name="search_source_documents",
            query_context=QueryContext(
                query="\u6df1\u4ea4\u6240 \u516c\u544a \u62ab\u9732",
                max_documents_per_source=3,
            ),
        )
    )
    assert search.status.value == "success"
    assert len(search.documents) == 1
    assert search.documents[0].source_uri.endswith("t20260410_619897.html")
    assert search.documents[0].title == SZSE_TITLE

    detail = adapter.fetch_document_detail(
        ToolRequest(
            tool_name="fetch_document_detail",
            query_context=QueryContext(query="\u6df1\u4ea4\u6240 \u516c\u544a"),
            document_id=search.documents[0].document_id,
        )
    )
    assert detail.status.value == "success"
    assert detail.normalized_documents
    assert detail.normalized_documents[0].metadata["publisher"] == SZSE_PUBLISHER

    extract = adapter.extract_evidence_items(
        ToolRequest(
            tool_name="extract_evidence_items",
            query_context=QueryContext(
                query="\u6e2f\u80a1\u901a\u540d\u5355\u8c03\u6574",
                max_evidence_per_source=2,
            ),
            document_id=search.documents[0].document_id,
        )
    )
    assert extract.status.value == "success"
    assert extract.evidence_items
    assert extract.evidence_items[0].citation.metadata["source_name"] == "SZSE Notice Announcements"


def test_real_domestic_profile_partial_failure_when_detail_fetch_fails(monkeypatch) -> None:
    profile = build_cn_policy_ndrc_tzgg_v1_profile(enabled=True)
    fetch_service = LiveHtmlFetchService(timeout_seconds=1.0, max_retries=1, backoff_seconds=0.0)
    list_html = _build_ndrc_list_html()

    def _fake_fetch_html(url: str, **kwargs):  # noqa: ANN003
        if url.endswith("/index.html"):
            return build_inline_fetch_result(
                url=url,
                text=list_html,
                warning="mocked_ndrc_list_html",
            )
        raise LiveHtmlFetchError(
            "detail fetch timeout",
            url=url,
            retryable=True,
            status_code=None,
            attempts=2,
            retry_count=1,
            latency_ms=1200.0,
            detail={"stage": "detail"},
        )

    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    adapter = GenericProfileSourceAdapter(profile, live_fetch_service=fetch_service)

    search = adapter.search_documents(
        ToolRequest(
            tool_name="search_source_documents",
            query_context=QueryContext(
                query="\u53d1\u6539\u59d4 \u653f\u7b56 \u901a\u77e5",
                max_documents_per_source=3,
            ),
        )
    )
    assert search.status.value == "success"

    detail = adapter.fetch_document_detail(
        ToolRequest(
            tool_name="fetch_document_detail",
            query_context=QueryContext(query="\u53d1\u6539\u59d4 \u653f\u7b56 \u901a\u77e5"),
            document_id=search.documents[0].document_id,
        )
    )
    assert detail.status.value == "error"
    assert detail.errors
    assert "Failed to fetch detail page" in detail.errors[0].message


def test_source_service_builds_bundle_with_real_ndrc_profile(monkeypatch) -> None:
    profile = build_cn_policy_ndrc_tzgg_v1_profile(enabled=True)
    fetch_service = LiveHtmlFetchService(timeout_seconds=1.0, max_retries=1, backoff_seconds=0.0)
    list_html = _build_ndrc_list_html()
    detail_html = _build_ndrc_detail_html(with_attachment=False)

    def _fake_fetch_html(url: str, **kwargs):  # noqa: ANN003
        if url.endswith("/index.html"):
            return build_inline_fetch_result(
                url=url,
                text=list_html,
                warning="mocked_ndrc_list_html",
            )
        return build_inline_fetch_result(
            url=url,
            text=detail_html,
            warning="mocked_ndrc_detail_html",
        )

    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    registry = SourceRegistry()
    registry.register_profile(
        profile,
        adapter=GenericProfileSourceAdapter(profile, live_fetch_service=fetch_service),
    )
    service = SourceIntelligenceService(source_registry=registry)

    response = service.build_bundle_for_query(
        QueryContext(query="\u56fd\u5bb6\u53d1\u6539\u59d4 \u653f\u7b56", max_sources=3)
    )
    assert response.bundle is not None
    assert response.bundle.items
    assert any(
        item.source_id == "cn_policy_ndrc_tzgg_v1"
        for item in response.route_recommendations
    )
    assert response.bundle.metadata["source_quality_summary"]["sources_attempted"] >= 1
