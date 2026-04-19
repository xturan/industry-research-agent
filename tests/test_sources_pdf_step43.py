from __future__ import annotations

from pathlib import Path

import pytest

from packages.sources.collectors import PdfArtifact
from packages.sources.enums import ToolStatus
from packages.sources.live_fetch import LiveHtmlFetchService, build_inline_fetch_result
from packages.sources.live_pdf import (
    LivePdfDownloadError,
    LivePdfDownloadResult,
    LivePdfDownloadService,
)
from packages.sources.pdf_text import PdfTextExtractionError, PdfTextExtractionService
from packages.sources.profile_adapter import GenericProfileSourceAdapter
from packages.sources.profiles import build_cn_policy_ndrc_tzgg_v1_profile
from packages.sources.registry import SourceRegistry
from packages.sources.schemas import QueryContext, ToolRequest
from packages.sources.service import SourceIntelligenceService

FIXTURE_DIR = Path("tests/fixtures/sources")
SAMPLE_PDF = FIXTURE_DIR / "sample_attachment.pdf"
CORRUPT_PDF = FIXTURE_DIR / "corrupt_attachment.pdf"


def _build_ndrc_list_html() -> str:
    return "\n".join(
        [
            '<ul class="list">',
            "  <li>",
            (
                '    <a href="/xwdt/tzgg/202604/t20260409_1404477.html">'
                "政策通知示例"
                "</a>"
            ),
            "    <span>2026/04/09</span>",
            "  </li>",
            "</ul>",
        ]
    )


def _build_ndrc_detail_html() -> str:
    return "\n".join(
        [
            "<html>",
            "  <body>",
            '    <div class="article_title">政策通知示例</div>',
            '    <div class="shezhi"><span class="time">发布时间：2026/04/09</span></div>',
            '    <div class="article_con"><div class="TRS_Editor">正文内容示例。</div></div>',
            (
                '    <div class="attachment_r">'
                '<a href="/files/sample_attachment.pdf">附件下载</a>'
                "</div>"
            ),
            "  </body>",
            "</html>",
        ]
    )


def test_live_pdf_download_creates_local_artifact(monkeypatch, tmp_path) -> None:
    payload = SAMPLE_PDF.read_bytes()

    class _FakeHeaders(dict):
        def get(self, key, default=None):  # noqa: ANN001, ANN201
            return super().get(key, default)

    class _FakeResponse:
        def __init__(self, body: bytes) -> None:
            self._body = body
            self.headers = _FakeHeaders({"Content-Type": "application/pdf"})

        def read(self) -> bytes:
            return self._body

        def getcode(self) -> int:
            return 200

        def geturl(self) -> str:
            return "https://example.cn/files/sample_attachment.pdf"

        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

    def _fake_urlopen(request, timeout=0):  # noqa: ANN001, ARG001
        return _FakeResponse(payload)

    monkeypatch.setattr("packages.sources.live_pdf.urlopen", _fake_urlopen)
    service = LivePdfDownloadService(
        storage_dir=str(tmp_path / "pdfs"),
        timeout_seconds=1.0,
        max_retries=1,
        backoff_seconds=0.0,
    )

    result = service.download_pdf(
        "https://example.cn/files/sample_attachment.pdf",
        source_id="cn_policy_ndrc_tzgg_v1",
        attachment_ref="sample_attachment.pdf",
    )

    assert Path(result.file_path).exists()
    assert result.bytes_size == len(payload)
    assert result.content_type == "application/pdf"
    assert result.retry_count == 0


def test_pdf_text_extraction_from_local_fixture() -> None:
    artifact = PdfArtifact(
        artifact_id="pdf_fixture_1",
        source_id="cn_policy_ndrc_tzgg_v1",
        url="https://example.cn/files/sample_attachment.pdf",
        filename="sample_attachment.pdf",
        attachment_ref="sample_attachment.pdf",
    )
    service = PdfTextExtractionService()
    document = service.extract_from_file(
        file_path=str(SAMPLE_PDF),
        source_id="cn_policy_ndrc_tzgg_v1",
        artifact=artifact,
        max_pages=5,
    )

    assert len(document.pages) == 2
    assert document.pages[0].page_number == 1
    assert document.metadata["extractor_version"] == "pypdf_v1"
    assert document.metadata["page_count_total"] == 2
    assert "pilot project" in document.full_text.lower()


def test_pdf_text_extraction_corrupt_fixture_returns_structured_error() -> None:
    service = PdfTextExtractionService()
    with pytest.raises(PdfTextExtractionError) as exc_info:
        service.extract_from_file(
            file_path=str(CORRUPT_PDF),
            source_id="cn_policy_ndrc_tzgg_v1",
        )
    assert exc_info.value.error_code in {"invalid_pdf", "pdf_parse_error"}


def test_domestic_profile_can_produce_pdf_derived_evidence(monkeypatch, tmp_path) -> None:
    profile = build_cn_policy_ndrc_tzgg_v1_profile(enabled=True)
    fetch_service = LiveHtmlFetchService(timeout_seconds=1.0, max_retries=1, backoff_seconds=0.0)
    live_pdf_service = LivePdfDownloadService(storage_dir=str(tmp_path / "pdf_downloads"))
    text_service = PdfTextExtractionService()
    list_html = _build_ndrc_list_html()
    detail_html = _build_ndrc_detail_html()

    def _fake_fetch_html(url: str, **kwargs):  # noqa: ANN003, ARG001
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

    def _fake_download_pdf(url: str, **kwargs):  # noqa: ANN003, ARG001
        return LivePdfDownloadResult(
            url=url,
            final_url=url,
            status_code=200,
            content_type="application/pdf",
            file_path=str(SAMPLE_PDF),
            bytes_size=SAMPLE_PDF.stat().st_size,
            sha256="mocked_sha256",
            attempts=1,
            retry_count=0,
            latency_ms=4.0,
        )

    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    monkeypatch.setattr(live_pdf_service, "download_pdf", _fake_download_pdf)
    adapter = GenericProfileSourceAdapter(
        profile,
        live_fetch_service=fetch_service,
        live_pdf_service=live_pdf_service,
        pdf_text_service=text_service,
    )
    context = QueryContext(
        query="发改委 通知 附件",
        max_documents_per_source=2,
        max_evidence_per_source=4,
    )

    search = adapter.search_documents(
        ToolRequest(tool_name="search_source_documents", query_context=context)
    )
    document_id = search.documents[0].document_id

    detail = adapter.fetch_document_detail(
        ToolRequest(
            tool_name="fetch_document_detail",
            query_context=context,
            document_id=document_id,
            payload={
                "enable_pdf_processing": True,
                "max_pdf_attachments_per_source": 1,
                "max_pdf_pages_per_attachment": 2,
            },
        )
    )
    assert detail.status == ToolStatus.SUCCESS
    assert any(
        doc.metadata.get("from_pdf_attachment")
        for doc in detail.normalized_documents
    )

    extract = adapter.extract_evidence_items(
        ToolRequest(
            tool_name="extract_evidence_items",
            query_context=context,
            document_id=document_id,
            payload={
                "enable_pdf_processing": True,
                "max_pdf_attachments_per_source": 1,
                "max_pdf_pages_per_attachment": 2,
            },
        )
    )
    assert extract.status == ToolStatus.SUCCESS
    assert any(
        item.metadata.get("from_pdf_attachment")
        for item in extract.evidence_items
    )
    assert any(
        item.citation.locator.page_number is not None
        for item in extract.evidence_items
    )


def test_domestic_profile_pdf_failure_is_structured(monkeypatch, tmp_path) -> None:
    profile = build_cn_policy_ndrc_tzgg_v1_profile(enabled=True)
    fetch_service = LiveHtmlFetchService(timeout_seconds=1.0, max_retries=1, backoff_seconds=0.0)
    live_pdf_service = LivePdfDownloadService(storage_dir=str(tmp_path / "pdf_downloads"))
    list_html = _build_ndrc_list_html()
    detail_html = _build_ndrc_detail_html()

    def _fake_fetch_html(url: str, **kwargs):  # noqa: ANN003, ARG001
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

    def _always_fail_download(url: str, **kwargs):  # noqa: ANN003, ARG001
        raise LivePdfDownloadError(
            "timeout while downloading pdf",
            url=url,
            retryable=True,
            status_code=None,
            attempts=2,
            retry_count=1,
            latency_ms=1200.0,
            detail={"stage": "download"},
        )

    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    monkeypatch.setattr(live_pdf_service, "download_pdf", _always_fail_download)
    adapter = GenericProfileSourceAdapter(
        profile,
        live_fetch_service=fetch_service,
        live_pdf_service=live_pdf_service,
    )
    context = QueryContext(
        query="发改委 通知 附件",
        max_documents_per_source=2,
        max_evidence_per_source=4,
    )
    search = adapter.search_documents(
        ToolRequest(tool_name="search_source_documents", query_context=context)
    )
    detail = adapter.fetch_document_detail(
        ToolRequest(
            tool_name="fetch_document_detail",
            query_context=context,
            document_id=search.documents[0].document_id,
            payload={"enable_pdf_processing": True},
        )
    )

    assert detail.status in {ToolStatus.SUCCESS, ToolStatus.PARTIAL}
    assert any("PDF download failed" in error.message for error in detail.errors)


def test_source_service_bundle_can_include_pdf_evidence(monkeypatch, tmp_path) -> None:
    profile = build_cn_policy_ndrc_tzgg_v1_profile(enabled=True)
    fetch_service = LiveHtmlFetchService(timeout_seconds=1.0, max_retries=1, backoff_seconds=0.0)
    live_pdf_service = LivePdfDownloadService(storage_dir=str(tmp_path / "pdf_downloads"))
    list_html = _build_ndrc_list_html()
    detail_html = _build_ndrc_detail_html()

    def _fake_fetch_html(url: str, **kwargs):  # noqa: ANN003, ARG001
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

    def _fake_download_pdf(url: str, **kwargs):  # noqa: ANN003, ARG001
        return LivePdfDownloadResult(
            url=url,
            final_url=url,
            status_code=200,
            content_type="application/pdf",
            file_path=str(SAMPLE_PDF),
            bytes_size=SAMPLE_PDF.stat().st_size,
            sha256="mocked_sha256",
            attempts=1,
            retry_count=0,
            latency_ms=4.0,
        )

    monkeypatch.setattr(fetch_service, "fetch_html", _fake_fetch_html)
    monkeypatch.setattr(live_pdf_service, "download_pdf", _fake_download_pdf)
    adapter = GenericProfileSourceAdapter(
        profile,
        live_fetch_service=fetch_service,
        live_pdf_service=live_pdf_service,
        pdf_text_service=PdfTextExtractionService(),
    )
    registry = SourceRegistry()
    registry.register_profile(profile, adapter=adapter)
    service = SourceIntelligenceService(source_registry=registry)

    response = service.build_bundle_for_query(
        QueryContext(
            query="发改委 政策 通知 附件",
            max_sources=2,
            max_documents_per_source=2,
            max_evidence_per_source=6,
            metadata={"include_domestic_profiles": True},
        ),
        payload={
            "enable_pdf_processing": True,
            "max_pdf_attachments_per_source": 1,
            "max_pdf_pages_per_attachment": 2,
        },
    )

    assert response.status == ToolStatus.SUCCESS
    assert response.bundle is not None
    assert any(
        item.metadata.get("from_pdf_attachment")
        for item in response.bundle.items
    )
