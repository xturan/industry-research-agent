from __future__ import annotations

from typing import Any

import pytest

from packages.core.config import Settings
from packages.sources.enums import ToolErrorCode, ToolStatus
from packages.sources.query_decomposition import decompose_query
from packages.sources.search_discovery import (
    AnySearchSearchAdapter,
    AnySearchSettings,
    FallbackSearchDiscoveryAdapter,
    TavilySearchAdapter,
    TavilySearchRequest,
    TavilySearchSettings,
    build_search_discovery_provider,
    tavily_settings_from_app_settings,
)


def _anysearch_payload(text: str) -> dict[str, Any]:
    return {"result": {"content": [{"type": "text", "text": text}]}}


def test_anysearch_parses_original_content_and_post_filters_domains() -> None:
    captured: dict[str, Any] = {}

    def transport(endpoint, payload, headers, timeout):
        captured.update(payload=payload, headers=headers)
        return _anysearch_payload(
            "### 1. 官方公告\n- **URL**: https://www.szse.cn/a.html\n正文原文\n"
            "### 2. 媒体转载\n- **URL**: https://example.com/b.html\n转载正文"
        )

    adapter = AnySearchSearchAdapter(
        settings=AnySearchSettings(api_key=None),
        transport=transport,
    )
    response = adapter.search(
        TavilySearchRequest(
            query="上市公司公告",
            include_domains=["szse.cn"],
            max_results=5,
        )
    )

    assert response.status == ToolStatus.SUCCESS
    assert len(response.results) == 1
    assert response.results[0].raw_content == "正文原文"
    assert response.results[0].content_origin == "search_discovery"
    assert response.results[0].route == "general"
    assert response.raw_response_metadata["provider_used"] == "anysearch"
    assert response.raw_response_metadata["filtered_result_count"] == 1
    assert "site:szse.cn" in captured["payload"]["params"]["arguments"]["query"]
    assert "Authorization" not in captured["headers"]


def test_fallback_uses_tavily_on_anysearch_parser_error_but_not_empty_result() -> None:
    fallback_calls = 0

    def fallback_transport(endpoint, payload, headers, timeout):
        nonlocal fallback_calls
        fallback_calls += 1
        return {"query": payload["query"], "results": []}

    fallback = TavilySearchAdapter(
        settings=TavilySearchSettings(api_key="test-secret"),
        transport=fallback_transport,
    )
    broken = AnySearchSearchAdapter(
        settings=AnySearchSettings(),
        transport=lambda *args: _anysearch_payload("unexpected response"),
    )
    adapter = FallbackSearchDiscoveryAdapter(broken, fallback)
    response = adapter.search(TavilySearchRequest(query="test"))
    assert response.raw_response_metadata["fallback_used"] is True
    assert fallback_calls == 1

    empty = AnySearchSearchAdapter(
        settings=AnySearchSettings(),
        transport=lambda *args: _anysearch_payload("No results found"),
    )
    response = FallbackSearchDiscoveryAdapter(empty, fallback).search(
        TavilySearchRequest(query="empty")
    )
    assert response.status == ToolStatus.SUCCESS
    assert response.results == []
    assert fallback_calls == 1


def test_provider_factory_defaults_to_anysearch_with_explicit_tavily_fallback() -> None:
    provider = build_search_discovery_provider(
        Settings(TAVILY_API_KEY="test-secret"),
        anysearch_transport=lambda *args: _anysearch_payload("No results found"),
    )

    assert isinstance(provider, FallbackSearchDiscoveryAdapter)
    assert isinstance(provider.primary, AnySearchSearchAdapter)
    assert isinstance(provider.fallback, TavilySearchAdapter)

def test_tavily_missing_api_key_returns_structured_failure() -> None:
    adapter = TavilySearchAdapter(settings=TavilySearchSettings(api_key=None))

    response = adapter.search(TavilySearchRequest(query="安徽 低空经济 政策"))

    assert response.status == ToolStatus.ERROR
    assert response.errors
    assert response.errors[0].code == ToolErrorCode.INVALID_REQUEST
    assert response.errors[0].retryable is False
    assert response.usage is not None
    assert response.usage.estimated_credits == 1


def test_tavily_search_uses_low_credit_defaults_and_authorization_header() -> None:
    captured: dict[str, Any] = {}

    def fake_transport(
        endpoint: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        captured["headers"] = headers
        captured["timeout_seconds"] = timeout_seconds
        return {
            "query": payload["query"],
            "results": [
                {
                    "title": "安徽省低空经济政策",
                    "url": "https://www.ah.gov.cn/example.html",
                    "content": "政策摘要",
                    "score": 0.91,
                }
            ],
            "response_time": 0.12,
        }

    adapter = TavilySearchAdapter(
        settings=TavilySearchSettings(api_key="test-secret"),
        transport=fake_transport,
    )

    response = adapter.search(
        TavilySearchRequest(
            query="安徽 低空经济 政策",
            include_domains=["ah.gov.cn"],
            exclude_domains=["example.com"],
            exact_match=True,
        )
    )

    assert response.status == ToolStatus.SUCCESS
    assert response.results[0].url == "https://www.ah.gov.cn/example.html"
    assert captured["headers"]["Authorization"] == "Bearer test-secret"
    assert captured["payload"] == {
        "query": "安徽 低空经济 政策",
        "search_depth": "basic",
        "topic": "general",
        "max_results": 5,
        "auto_parameters": False,
        "include_answer": False,
        "include_raw_content": False,
        "country": "china",
        "include_domains": ["ah.gov.cn"],
        "exclude_domains": ["example.com"],
        "exact_match": True,
    }
    assert response.usage is not None
    assert response.usage.estimated_credits == 1
    assert "api_key" not in response.usage.request_params


def test_tavily_search_rotates_api_keys_and_falls_back_after_quota_error() -> None:
    seen_authorizations: list[str] = []

    def fake_transport(
        endpoint: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        seen_authorizations.append(headers["Authorization"])
        if headers["Authorization"] == "Bearer exhausted-key":
            from packages.sources.search_discovery import SourceTavilyError

            raise SourceTavilyError(
                "Tavily HTTP error 432",
                retryable=False,
                detail={"status_code": 432},
            )
        return {
            "query": payload["query"],
            "results": [
                {
                    "title": "usable result",
                    "url": "https://example.gov.cn/result.html",
                    "content": "official content",
                }
            ],
        }

    adapter = TavilySearchAdapter(
        settings=TavilySearchSettings(
            api_key="exhausted-key",
            api_keys=["exhausted-key", "fresh-key"],
        ),
        transport=fake_transport,
    )

    first_response = adapter.search(TavilySearchRequest(query="first query"))
    second_response = adapter.search(TavilySearchRequest(query="second query"))

    assert first_response.status == ToolStatus.SUCCESS
    assert second_response.status == ToolStatus.SUCCESS
    assert seen_authorizations == [
        "Bearer exhausted-key",
        "Bearer fresh-key",
        "Bearer fresh-key",
    ]
    assert first_response.raw_response_metadata["api_key_attempt_count"] == 2
    assert second_response.raw_response_metadata["api_key_attempt_count"] == 1


def test_tavily_search_overrides_depth_and_records_advanced_credit_estimate() -> None:
    def fake_transport(
        endpoint: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        return {"query": payload["query"], "results": []}

    adapter = TavilySearchAdapter(
        settings=TavilySearchSettings(api_key="test-secret"),
        transport=fake_transport,
    )

    response = adapter.search(
        TavilySearchRequest(
            query="国家层面 算力基础设施 政策",
            search_depth="advanced",
            max_results=3,
        )
    )

    assert response.status == ToolStatus.SUCCESS
    assert response.usage is not None
    assert response.usage.search_depth == "advanced"
    assert response.usage.max_results == 3
    assert response.usage.estimated_credits == 2


def test_tavily_search_accepts_fast_low_credit_depth() -> None:
    def fake_transport(
        endpoint: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        return {"query": payload["query"], "results": []}

    adapter = TavilySearchAdapter(
        settings=TavilySearchSettings(api_key="test-secret"),
        transport=fake_transport,
    )

    response = adapter.search(
        TavilySearchRequest(
            query="安徽 低空经济 政策",
            search_depth="fast",
            max_results=1,
        )
    )

    assert response.status == ToolStatus.SUCCESS
    assert response.usage is not None
    assert response.usage.search_depth == "fast"
    assert response.usage.estimated_credits == 1


@pytest.mark.parametrize(
    "field",
    [
        "search_depth",
        "topic",
    ],
)
def test_tavily_search_request_rejects_invalid_overrides(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        TavilySearchRequest(query="安徽 低空经济 政策", **{field: "bogus"})


def test_tavily_search_task_consumes_decomposition_task_phrases() -> None:
    seen_queries: list[str] = []

    def fake_transport(
        endpoint: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        seen_queries.append(str(payload["query"]))
        assert payload["include_domains"]
        return {
            "query": payload["query"],
            "results": [
                {
                    "title": "候选页面",
                    "url": f"https://www.ah.gov.cn/{len(seen_queries)}.html",
                    "content": "候选摘要",
                }
            ],
        }

    decomposition = decompose_query("安徽的低空经济未来前景如何")
    local_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "local_rollout"
    )
    adapter = TavilySearchAdapter(
        settings=TavilySearchSettings(api_key="test-secret"),
        transport=fake_transport,
    )

    responses = adapter.search_task(local_task)

    assert len(responses) == len(local_task.search_phrases)
    assert seen_queries == local_task.search_phrases
    assert all(response.status == ToolStatus.SUCCESS for response in responses)


def test_tavily_search_task_maps_exact_phrases_to_exact_match() -> None:
    captured_payloads: list[dict[str, Any]] = []

    def fake_transport(
        endpoint: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        captured_payloads.append(payload)
        return {"query": payload["query"], "results": []}

    decomposition = decompose_query("中信海直（000099.SZ）在低空经济方向有哪些公告和项目")
    enterprise_task = next(
        task
        for task in decomposition.decomposition_tasks
        if task.task_family == "enterprise_disclosure"
    ).model_copy(update={"exact_phrases": ["中信海直"]})
    adapter = TavilySearchAdapter(
        settings=TavilySearchSettings(api_key="test-secret"),
        transport=fake_transport,
    )

    adapter.search_task(enterprise_task)

    assert captured_payloads
    for payload in captured_payloads:
        assert payload["exact_match"] is True
        assert '"中信海直"' in payload["query"]


def test_tavily_settings_are_loaded_from_app_settings_aliases() -> None:
    settings = Settings(
        TAVILY_API_KEY="test-secret",
        TAVILY_API_KEYS="test-secret,backup-secret",
        TAVILY_SEARCH_DEPTH="ultra-fast",
        TAVILY_TOPIC="general",
        TAVILY_COUNTRY="china",
        TAVILY_MAX_RESULTS=4,
        TAVILY_AUTO_PARAMETERS=False,
        TAVILY_INCLUDE_ANSWER=False,
        TAVILY_INCLUDE_RAW_CONTENT=False,
        TAVILY_TIMEOUT_SECONDS=9,
    )

    tavily_settings = tavily_settings_from_app_settings(settings)

    assert tavily_settings.api_key == "test-secret"
    assert tavily_settings.api_keys == ["test-secret", "backup-secret"]
    assert tavily_settings.search_depth == "ultra-fast"
    assert tavily_settings.max_results == 4
    assert tavily_settings.timeout_seconds == 9
