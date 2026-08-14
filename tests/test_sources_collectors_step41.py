from __future__ import annotations

from datetime import datetime

import pytest

from packages.sources.collectors import (
    BaseCollector,
    ChinaCitation,
    CollectorRequest,
    CollectorResponse,
    DetailPageContent,
    DiscoveredItem,
    HtmlListDetailCollector,
    PdfArtifact,
    PdfFetchCollector,
    PdfTextDocument,
    PdfTextExtractCollector,
    PdfTextPage,
    normalize_china_citation,
)
from packages.sources.enums import ChinaLocatorType, CollectorType, ToolStatus
from packages.sources.profiles import (
    build_cn_exchange_announcement_generic_profile,
    build_cn_industry_association_generic_profile,
    build_cn_policy_generic_profile,
)
from packages.sources.registry import SourceRegistry, build_default_source_registry


class EchoCollector(BaseCollector):
    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.HTML_LIST_DETAIL

    def discover_items(self, request: CollectorRequest) -> CollectorResponse:
        return CollectorResponse(
            status=ToolStatus.SUCCESS,
            collector_name=self.collector_name,
            source_id=request.source_id,
            items=[
                DiscoveredItem(
                    item_id="echo_item_1",
                    source_id=request.source_id,
                    title="Echo Item",
                    url="https://example.cn/echo/1",
                )
            ],
        )

    def fetch_detail(self, request: CollectorRequest) -> CollectorResponse:
        detail = DetailPageContent(
            item_id="echo_item_1",
            source_id=request.source_id,
            url="https://example.cn/echo/1",
            title="Echo Item",
            text_content="Echo detail text.",
        )
        return CollectorResponse(
            status=ToolStatus.SUCCESS,
            collector_name=self.collector_name,
            source_id=request.source_id,
            detail_pages=[detail],
        )

    def discover_attachments(self, request: CollectorRequest) -> CollectorResponse:
        return CollectorResponse(
            status=ToolStatus.SUCCESS,
            collector_name=self.collector_name,
            source_id=request.source_id,
            pdf_artifacts=[
                PdfArtifact(
                    artifact_id="echo_pdf_1",
                    source_id=request.source_id,
                    url="https://example.cn/echo/echo.pdf",
                    filename="echo.pdf",
                )
            ],
        )

    def normalize_to_documents(self, request: CollectorRequest) -> CollectorResponse:
        return CollectorResponse(
            status=ToolStatus.SUCCESS,
            collector_name=self.collector_name,
            source_id=request.source_id,
        )


def test_collector_schema_validation() -> None:
    profile = build_cn_policy_generic_profile()
    request = CollectorRequest(
        source_id=profile.source_id,
        profile=profile,
        entry_url=profile.entry_urls[0],
        raw_html="<ul><li><a href='/notice/1'>通知</a></li></ul>",
    )
    assert request.profile.collector_type == CollectorType.HTML_LIST_DETAIL

    with pytest.raises(ValueError):
        CollectorRequest(
            source_id="mismatch_source",
            profile=profile,
        )


def test_base_collector_subclass_contract() -> None:
    profile = build_cn_policy_generic_profile()
    collector = EchoCollector()
    request = CollectorRequest(source_id=profile.source_id, profile=profile)

    discovered = collector.discover_items(request)
    detail = collector.fetch_detail(request)
    attachments = collector.discover_attachments(request)

    assert discovered.status == ToolStatus.SUCCESS
    assert detail.detail_pages[0].text_content == "Echo detail text."
    assert attachments.pdf_artifacts[0].filename == "echo.pdf"


def test_domestic_source_profiles_are_valid_and_disabled_by_default() -> None:
    profiles = [
        build_cn_policy_generic_profile(),
        build_cn_exchange_announcement_generic_profile(),
        build_cn_industry_association_generic_profile(),
    ]
    assert all(profile.collector_type == CollectorType.HTML_LIST_DETAIL for profile in profiles)
    assert all(profile.entry_urls for profile in profiles)
    assert all(profile.language == "zh-CN" for profile in profiles)
    assert all(profile.enabled is False for profile in profiles)


def test_html_list_detail_collector_placeholder_behavior() -> None:
    collector = HtmlListDetailCollector()
    profile = build_cn_policy_generic_profile(enabled=True)
    list_html = """
    <ul class="list">
      <li data-id="notice-1">
        <a href="/policy/notice-1.html">关于行业升级的通知</a>
        <span class="date">2026-03-01</span>
      </li>
    </ul>
    """
    list_request = CollectorRequest(
        source_id=profile.source_id,
        profile=profile,
        entry_url="https://example.cn/policy/list",
        raw_html=list_html,
    )
    discovered = collector.discover_items(list_request)
    assert discovered.status == ToolStatus.SUCCESS
    assert len(discovered.items) == 1
    assert discovered.items[0].url == "https://example.cn/policy/notice-1.html"

    detail_html = """
    <html>
      <body>
        <h1>关于行业升级的通知</h1>
        <div class="article-content">推进重点产业升级，鼓励设备更新。</div>
        <span class="publish-date">2026-03-01</span>
        <a href="/files/notice-1.pdf">附件下载</a>
      </body>
    </html>
    """
    detail_request = CollectorRequest(
        source_id=profile.source_id,
        profile=profile,
        item=discovered.items[0],
        detail_url=discovered.items[0].url,
        raw_html=detail_html,
    )
    detail = collector.fetch_detail(detail_request)
    assert detail.status == ToolStatus.SUCCESS
    assert detail.detail_pages[0].title == "关于行业升级的通知"

    attachment_request = CollectorRequest(
        source_id=profile.source_id,
        profile=profile,
        item=discovered.items[0],
        detail_page=detail.detail_pages[0],
    )
    attachments = collector.discover_attachments(attachment_request)
    assert attachments.status == ToolStatus.SUCCESS
    assert attachments.pdf_artifacts[0].url.endswith("notice-1.pdf")

    normalized = collector.normalize_to_documents(
        CollectorRequest(
            source_id=profile.source_id,
            profile=profile,
            detail_page=detail.detail_pages[0],
            pdf_artifacts=attachments.pdf_artifacts,
        )
    )
    assert normalized.status == ToolStatus.SUCCESS
    assert normalized.normalized_documents[0].metadata["attachment_refs"]


def test_pdf_contract_objects_validate_and_normalize() -> None:
    artifact = PdfArtifact(
        artifact_id="pdf_1",
        source_id="cn_policy_generic",
        url="https://example.cn/files/policy.pdf",
        filename="policy.pdf",
    )
    page = PdfTextPage(page_number=1, text="第一页内容")
    document = PdfTextDocument(
        artifact_id=artifact.artifact_id,
        source_id=artifact.source_id,
        title="政策附件",
        url=artifact.url,
        pages=[page],
    )
    assert document.full_text == "第一页内容"
    assert document.metadata["page_count"] == 1

    with pytest.raises(ValueError):
        PdfTextPage(page_number=0, text="bad")


def test_pdf_collectors_placeholder_behavior() -> None:
    profile = build_cn_policy_generic_profile(enabled=True)
    artifact = PdfArtifact(
        artifact_id="policy_pdf_1",
        source_id=profile.source_id,
        url="https://example.cn/files/policy.pdf",
        filename="policy.pdf",
    )
    fetch_collector = PdfFetchCollector()
    extract_collector = PdfTextExtractCollector()

    fetch_response = fetch_collector.discover_attachments(
        CollectorRequest(
            source_id=profile.source_id,
            profile=profile,
            pdf_artifacts=[artifact],
        )
    )
    assert fetch_response.status == ToolStatus.SUCCESS
    assert fetch_response.pdf_artifacts[0].attachment_ref == "policy.pdf"

    extract_response = extract_collector.extract_text(
        CollectorRequest(
            source_id=profile.source_id,
            profile=profile,
            pdf_artifacts=[artifact],
            payload={"page_texts": ["第一页", {"page_number": 2, "text": "第二页"}]},
        )
    )
    assert extract_response.status == ToolStatus.SUCCESS
    assert len(extract_response.pdf_text_documents[0].pages) == 2

    normalized = extract_collector.normalize_to_documents(
        CollectorRequest(
            source_id=profile.source_id,
            profile=profile,
            pdf_artifacts=[artifact],
            payload={"page_texts": ["第一页"]},
        )
    )
    assert normalized.status == ToolStatus.SUCCESS
    assert normalized.normalized_documents[0].metadata["pdf_page_count"] == 1


def test_china_citation_normalization_contract() -> None:
    citation = normalize_china_citation(
        source_id="cn_policy_generic",
        source_name="China Policy Portal Generic",
        title="关于行业升级的通知",
        url="https://example.cn/policy/notice-1.html",
        published_at=datetime(2026, 3, 1),
        locator_type=ChinaLocatorType.ATTACHMENT,
        attachment_ref="notice-1.pdf",
        external_id="notice-1",
        quote_text="推进重点产业升级。",
    )
    assert isinstance(citation, ChinaCitation)
    assert citation.locator_value == "notice-1"
    assert citation.metadata["citation_normalized"] is True


def test_registry_lists_domestic_profiles_and_disabled_behavior() -> None:
    registry = build_default_source_registry()
    enabled_profiles = {profile.source_id for profile in registry.list_profiles(enabled_only=True)}
    all_profiles = {profile.source_id for profile in registry.list_profiles(enabled_only=False)}

    assert "cn_policy_generic" not in enabled_profiles
    assert {
        "cn_policy_generic",
        "cn_exchange_announcement_generic",
        "cn_industry_association_generic",
    } <= all_profiles
    assert registry.get_profile("cn_policy_generic", enabled_only=True) is None

    profile = build_cn_policy_generic_profile(enabled=True)
    custom_registry = SourceRegistry()
    custom_registry.register_profile(profile)
    assert custom_registry.get_profile("cn_policy_generic", enabled_only=True) is not None
    assert custom_registry.get_adapter("cn_policy_generic", enabled_only=False) is None
