from __future__ import annotations

import sys
from typing import Any

from packages.sources import crawl4ai_extraction
from packages.sources.crawl4ai_extraction import (
    Crawl4AIExtractionInput,
    Crawl4AIExtractionRequest,
    Crawl4AIExtractionService,
    Crawl4AIExtractionSettings,
    Crawl4AIUnavailableError,
    SearchUrlCandidate,
)
from packages.sources.enums import ToolErrorCode, ToolStatus


def test_crawl4ai_unavailable_returns_structured_response() -> None:
    def unavailable_runner(urls: list[str], timeout_seconds: int, user_agent: str) -> list[Any]:
        del urls
        del timeout_seconds
        del user_agent
        raise Crawl4AIUnavailableError(
            "Crawl4AI dependency missing.",
            detail={"reason": "dependency_missing"},
        )

    service = Crawl4AIExtractionService(
        settings=Crawl4AIExtractionSettings(enabled=True),
        runner=unavailable_runner,
    )
    response = service.extract(
        Crawl4AIExtractionRequest(
            inputs=[Crawl4AIExtractionInput(url="https://www.gov.cn/example-policy.html")]
        )
    )

    assert response.status == ToolStatus.UNSUPPORTED
    assert response.errors
    assert response.errors[0].code == ToolErrorCode.UNSUPPORTED_OPERATION
    assert response.errors[0].detail["reason"] == "dependency_missing"
    assert response.documents == []
    assert response.normalized_documents == []
    assert response.metadata["requested"] == 1
    assert response.metadata["failed"] == 1


def test_crawl4ai_success_maps_to_typed_documents() -> None:
    def success_runner(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
    ) -> list[dict[str, Any]]:
        del timeout_seconds
        del user_agent
        assert urls == ["https://www.gov.cn/example-policy.html"]
        return [
            {
                "url": urls[0],
                "success": True,
                "final_url": "https://www.gov.cn/final-policy.html",
                "title": "Sample policy page",
                "markdown": "# Policy highlights\nSupport low-altitude economy.\n"
                "# Execution\nStrengthen coordination.",
                "published_at": "2026-04-01T08:00:00+08:00",
                "links": {"external": [{"href": "https://www.ndrc.gov.cn/notice"}]},
                "attachments": [{"url": "https://www.gov.cn/files/policy.pdf"}],
                "metadata": {"lang": "zh-CN"},
            }
        ]

    service = Crawl4AIExtractionService(
        settings=Crawl4AIExtractionSettings(enabled=True),
        runner=success_runner,
    )
    response = service.extract(
        Crawl4AIExtractionRequest(
            inputs=[
                Crawl4AIExtractionInput(
                    url="https://www.gov.cn/example-policy.html",
                    source_id="central_policy",
                    metadata={"category": "policy"},
                )
            ]
        )
    )

    assert response.status == ToolStatus.SUCCESS
    assert len(response.documents) == 1
    assert len(response.normalized_documents) == 1
    raw_doc = response.documents[0]
    normalized_doc = response.normalized_documents[0]
    assert raw_doc.source_id == "central_policy"
    assert raw_doc.source_uri == "https://www.gov.cn/final-policy.html"
    assert raw_doc.metadata["provider"] == "crawl4ai"
    assert raw_doc.metadata["category"] == "policy"
    assert raw_doc.metadata["attachments"] == ["https://www.gov.cn/files/policy.pdf"]
    assert normalized_doc.sections
    assert normalized_doc.metadata["outlink_count"] == 1
    assert normalized_doc.metadata["attachment_count"] == 1
    assert response.errors == []


def test_crawl4ai_runner_receives_timeout_and_user_agent() -> None:
    captured: dict[str, Any] = {}

    def success_runner(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
    ) -> list[dict[str, Any]]:
        captured["urls"] = urls
        captured["timeout_seconds"] = timeout_seconds
        captured["user_agent"] = user_agent
        return [
            {
                "url": urls[0],
                "success": True,
                "title": "Sample page",
                "raw_text": "Extracted content.",
            }
        ]

    service = Crawl4AIExtractionService(
        settings=Crawl4AIExtractionSettings(
            enabled=True,
            timeout_seconds=12,
            user_agent="custom-agent/1.0",
        ),
        runner=success_runner,
    )
    response = service.extract(
        Crawl4AIExtractionRequest(
            inputs=[Crawl4AIExtractionInput(url="https://www.gov.cn/example-policy.html")]
        )
    )

    assert response.status == ToolStatus.SUCCESS
    assert captured["timeout_seconds"] == 12
    assert captured["user_agent"] == "custom-agent/1.0"


def test_crawl4ai_partial_failure_keeps_successful_documents() -> None:
    def mixed_runner(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
    ) -> list[dict[str, Any]]:
        del timeout_seconds
        del user_agent
        return [
            {
                "url": urls[0],
                "success": True,
                "title": "Success page",
                "raw_text": "Successfully extracted body text.",
            },
            {
                "url": urls[1],
                "success": False,
                "error_message": "blocked by target",
            },
        ]

    service = Crawl4AIExtractionService(
        settings=Crawl4AIExtractionSettings(enabled=True),
        runner=mixed_runner,
    )
    response = service.extract(
        Crawl4AIExtractionRequest(
            inputs=[
                Crawl4AIExtractionInput(
                    url="https://example.com/success",
                    source_id="city_department",
                ),
                Crawl4AIExtractionInput(
                    url="https://example.com/blocked",
                    source_id="city_department",
                ),
            ]
        )
    )

    assert response.status == ToolStatus.PARTIAL
    assert len(response.documents) == 1
    assert len(response.normalized_documents) == 1
    assert len(response.errors) == 1
    assert response.errors[0].code == ToolErrorCode.INTERNAL_ERROR
    assert response.errors[0].detail["url"] == "https://example.com/blocked"
    assert response.metadata["requested"] == 2
    assert response.metadata["succeeded"] == 1
    assert response.metadata["failed"] == 1
    assert response.metadata["failure_classes"] == {"anti_bot_or_forbidden": 1}
    assert response.errors[0].detail["extraction_failure_class"] == "anti_bot_or_forbidden"


def test_crawl4ai_failure_classification_covers_pdf_ssl_and_empty_content() -> None:
    def runner(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
    ) -> list[dict[str, Any]]:
        del timeout_seconds
        del user_agent
        return [
            {
                "url": urls[0],
                "success": True,
                "final_url": "https://example.com/report.pdf",
                "title": "Report PDF",
                "raw_text": "",
            },
            {
                "url": urls[1],
                "success": False,
                "error_message": "SSL certificate verify failed",
            },
            {
                "url": urls[2],
                "success": True,
                "title": "Empty page",
                "raw_text": "",
            },
        ]

    service = Crawl4AIExtractionService(
        settings=Crawl4AIExtractionSettings(enabled=True),
        runner=runner,
    )
    response = service.extract(
        Crawl4AIExtractionRequest(
            inputs=[
                Crawl4AIExtractionInput(url="https://example.com/report.pdf"),
                Crawl4AIExtractionInput(url="https://example.com/ssl"),
                Crawl4AIExtractionInput(url="https://example.com/empty"),
            ]
        )
    )

    assert response.status == ToolStatus.ERROR
    assert response.metadata["failure_classes"] == {
        "pdf_or_download": 1,
        "ssl_certificate_error": 1,
        "minimal_text_or_empty": 1,
    }
    assert [
        error.detail["extraction_failure_class"]
        for error in response.errors
    ] == [
        "pdf_or_download",
        "ssl_certificate_error",
        "minimal_text_or_empty",
    ]


def test_crawl4ai_long_runtime_error_is_truncated_to_tool_error_limit() -> None:
    long_message = "runtime failure " * 200

    def runner(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
    ) -> list[dict[str, Any]]:
        del timeout_seconds
        del user_agent
        return [
            {
                "url": urls[0],
                "success": False,
                "error_message": long_message,
            }
        ]

    service = Crawl4AIExtractionService(
        settings=Crawl4AIExtractionSettings(enabled=True),
        runner=runner,
    )
    response = service.extract(
        Crawl4AIExtractionRequest(
            inputs=[
                Crawl4AIExtractionInput(
                    url="https://example.com/blocked",
                    source_id="city_department",
                )
            ]
        )
    )

    assert response.status == ToolStatus.ERROR
    assert len(response.errors[0].message) <= 900
    assert response.errors[0].detail["error_message_truncated"] is True


def test_crawl4ai_stdio_guard_reconfigures_gbk_streams(monkeypatch: Any) -> None:
    class FakeTextStream:
        def __init__(self) -> None:
            self.encoding = "gbk"
            self.calls: list[dict[str, str]] = []

        def reconfigure(self, **kwargs: str) -> None:
            self.calls.append(kwargs)
            self.encoding = kwargs.get("encoding", self.encoding)

    stdout = FakeTextStream()
    stderr = FakeTextStream()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    crawl4ai_extraction._ensure_utf8_stdio_for_crawl4ai()

    assert stdout.calls == [{"encoding": "utf-8", "errors": "replace"}]
    assert stderr.calls == [{"encoding": "utf-8", "errors": "replace"}]


def test_crawl4ai_rejects_direct_structured_primary_path() -> None:
    called = False

    def runner(urls: list[str], timeout_seconds: int, user_agent: str) -> list[Any]:
        nonlocal called
        called = True
        del urls
        del timeout_seconds
        del user_agent
        return []

    service = Crawl4AIExtractionService(
        settings=Crawl4AIExtractionSettings(enabled=True),
        runner=runner,
    )
    response = service.extract(
        Crawl4AIExtractionRequest(
            inputs=[
                SearchUrlCandidate(
                    candidate_id="disclosure_1",
                    url="https://static.cninfo.com.cn/finalpage/example.pdf",
                    source_id="official_disclosure_backbone",
                    execution_bucket="direct_structured_sources",
                    source_cluster="official_disclosure_backbone",
                )
            ]
        )
    )

    assert called is False
    assert response.status == ToolStatus.ERROR
    assert response.errors[0].code == ToolErrorCode.INVALID_REQUEST
    assert response.errors[0].detail["reason"] == "direct_structured_source_protected"


def test_crawl4ai_allows_direct_structured_when_marked_supplemental() -> None:
    def runner(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
    ) -> list[dict[str, Any]]:
        del timeout_seconds
        del user_agent
        return [
            {
                "url": urls[0],
                "success": True,
                "title": "IR supplement",
                "raw_text": "Company website supplemental project description.",
            }
        ]

    service = Crawl4AIExtractionService(
        settings=Crawl4AIExtractionSettings(enabled=True),
        runner=runner,
    )
    response = service.extract(
        Crawl4AIExtractionRequest(
            allow_supplemental_direct_keep=True,
            inputs=[
                SearchUrlCandidate(
                    candidate_id="ir_1",
                    url="https://example.com/ir-news",
                    source_id="official_disclosure_backbone",
                    execution_bucket="direct_structured_sources",
                    source_cluster="official_disclosure_backbone",
                    discovery_provider="tavily",
                    discovery_query="中信海直 低空经济 公告",
                    task_family="enterprise_disclosure",
                    include_domains=["cninfo.com.cn"],
                )
            ],
        )
    )

    assert response.status == ToolStatus.SUCCESS
    assert response.documents[0].metadata["execution_bucket"] == "direct_structured_sources"
    assert response.documents[0].metadata["discovery_provider"] == "tavily"
