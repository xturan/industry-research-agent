from __future__ import annotations

import json
import re
from collections.abc import Callable
from time import perf_counter
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.core.config import Settings, get_settings
from packages.sources.enums import ToolErrorCode, ToolStatus
from packages.sources.query_decomposition import QueryDecompositionTask
from packages.sources.schemas import ToolError

TAVILY_SEARCH_ENDPOINT = "https://api.tavily.com/search"


class SearchDiscoveryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TavilySearchSettings(SearchDiscoveryModel):
    api_key: str | None = None
    api_keys: list[str] = Field(default_factory=list)
    endpoint: str = TAVILY_SEARCH_ENDPOINT
    search_depth: str = "basic"
    topic: str = "general"
    country: str = "china"
    max_results: int = Field(default=5, ge=1, le=20)
    auto_parameters: bool = False
    include_answer: bool = False
    include_raw_content: bool = False
    timeout_seconds: int = Field(default=30, ge=1, le=120)

    @field_validator("search_depth")
    @classmethod
    def validate_search_depth(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"basic", "fast", "advanced", "ultra-fast"}:
            raise ValueError("search_depth must be basic, fast, advanced, or ultra-fast")
        return normalized

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"general", "news", "finance"}:
            raise ValueError("topic must be general, news, or finance")
        return normalized


class TavilySearchRequest(SearchDiscoveryModel):
    query: str = Field(min_length=1, max_length=800)
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)
    country: str | None = None
    topic: str | None = None
    exact_match: bool | None = None
    max_results: int | None = Field(default=None, ge=1, le=20)
    search_depth: str | None = None
    auto_parameters: bool | None = None
    include_answer: bool | None = None
    include_raw_content: bool | None = None

    @field_validator("search_depth")
    @classmethod
    def validate_search_depth(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in {"basic", "fast", "advanced", "ultra-fast"}:
            raise ValueError("search_depth must be basic, fast, advanced, or ultra-fast")
        return normalized

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in {"general", "news", "finance"}:
            raise ValueError("topic must be general, news, or finance")
        return normalized


class TavilySearchResult(SearchDiscoveryModel):
    title: str = ""
    url: str = Field(min_length=1)
    content: str = ""
    score: float | None = None
    published_date: str | None = None
    raw_content: str | None = None


class TavilyUsageMetadata(SearchDiscoveryModel):
    provider: str = "tavily"
    endpoint: str = TAVILY_SEARCH_ENDPOINT
    search_depth: str
    max_results: int
    estimated_credits: int
    response_time_seconds: float | None = None
    request_params: dict[str, Any] = Field(default_factory=dict)
    result_count: int = 0


class TavilySearchResponse(SearchDiscoveryModel):
    status: ToolStatus
    query: str
    results: list[TavilySearchResult] = Field(default_factory=list)
    usage: TavilyUsageMetadata | None = None
    errors: list[ToolError] = Field(default_factory=list)
    raw_response_metadata: dict[str, Any] = Field(default_factory=dict)


Transport = Callable[[str, dict[str, Any], dict[str, str], int], dict[str, Any]]


class SearchDiscoveryProvider(Protocol):
    def search(self, request: TavilySearchRequest) -> TavilySearchResponse:
        """Discover candidate URLs for a query."""

    def search_task(self, task: QueryDecompositionTask) -> list[TavilySearchResponse]:
        """Discover candidate URLs for each search phrase in a decomposition task."""


class TavilySearchAdapter:
    def __init__(
        self,
        *,
        settings: TavilySearchSettings | None = None,
        transport: Transport | None = None,
    ) -> None:
        self.settings = settings or tavily_settings_from_app_settings()
        self._transport = transport or _default_transport
        self._next_api_key_index = 0
        self._disabled_api_key_indices: set[int] = set()

    def search(self, request: TavilySearchRequest) -> TavilySearchResponse:
        api_keys = self._resolved_api_keys()
        if not api_keys:
            return TavilySearchResponse(
                status=ToolStatus.ERROR,
                query=request.query,
                errors=[
                    ToolError(
                        code=ToolErrorCode.INVALID_REQUEST,
                        message=(
                            "TAVILY_API_KEY or TAVILY_API_KEYS is required for "
                            "Tavily search discovery."
                        ),
                        retryable=False,
                    )
                ],
                usage=self._usage_for_request(request, result_count=0),
            )

        payload = self._payload_for_request(request)
        started = perf_counter()
        last_error: SourceTavilyError | None = None
        attempt_count = 0
        for api_key_index, api_key in self._api_key_attempt_order(api_keys):
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            attempt_count += 1
            try:
                raw_response = self._transport(
                    self.settings.endpoint,
                    payload,
                    headers,
                    self.settings.timeout_seconds,
                )
                self._next_api_key_index = (api_key_index + 1) % len(api_keys)
                break
            except SourceTavilyError as exc:
                last_error = exc
                if _should_rotate_api_key(exc):
                    self._disabled_api_key_indices.add(api_key_index)
                if not _should_rotate_api_key(exc) or attempt_count >= len(api_keys):
                    return TavilySearchResponse(
                        status=ToolStatus.ERROR,
                        query=request.query,
                        errors=[
                            ToolError(
                                code=ToolErrorCode.INTERNAL_ERROR,
                                message=str(exc),
                                retryable=exc.retryable,
                                detail={
                                    **exc.detail,
                                    "api_key_attempt_count": attempt_count,
                                },
                            )
                        ],
                        usage=self._usage_for_request(request, result_count=0),
                    )
                continue
        else:
            error = last_error or SourceTavilyError(
                "Tavily search failed before a response was returned.",
                retryable=True,
            )
            return TavilySearchResponse(
                status=ToolStatus.ERROR,
                query=request.query,
                errors=[
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=str(error),
                        retryable=error.retryable,
                        detail={
                            **error.detail,
                            "api_key_attempt_count": attempt_count,
                        },
                    )
                ],
                usage=self._usage_for_request(request, result_count=0),
            )

        response_time = perf_counter() - started
        results = _parse_results(raw_response)
        usage = self._usage_for_request(
            request,
            result_count=len(results),
            response_time_seconds=response_time,
        )
        return TavilySearchResponse(
            status=ToolStatus.SUCCESS,
            query=str(raw_response.get("query") or request.query),
            results=results,
            usage=usage,
            raw_response_metadata={
                "answer_present": bool(raw_response.get("answer")),
                "response_time": raw_response.get("response_time"),
                "images_count": len(raw_response.get("images") or []),
                "api_key_attempt_count": attempt_count,
            },
        )

    def search_task(self, task: QueryDecompositionTask) -> list[TavilySearchResponse]:
        responses: list[TavilySearchResponse] = []
        for phrase in task.search_phrases:
            responses.append(
                self.search(
                    TavilySearchRequest(
                        query=_query_with_exact_phrases(phrase, task.exact_phrases),
                        include_domains=task.include_domains,
                        exclude_domains=task.exclude_domains,
                        exact_match=bool(task.exact_phrases),
                    )
                )
            )
        return responses

    def _payload_for_request(self, request: TavilySearchRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "query": request.query,
            "search_depth": request.search_depth or self.settings.search_depth,
            "topic": request.topic or self.settings.topic,
            "max_results": request.max_results or self.settings.max_results,
            "auto_parameters": (
                self.settings.auto_parameters
                if request.auto_parameters is None
                else request.auto_parameters
            ),
            "include_answer": (
                self.settings.include_answer
                if request.include_answer is None
                else request.include_answer
            ),
            "include_raw_content": (
                self.settings.include_raw_content
                if request.include_raw_content is None
                else request.include_raw_content
            ),
        }
        country = request.country or self.settings.country
        if country:
            payload["country"] = country
        if request.include_domains:
            payload["include_domains"] = request.include_domains
        if request.exclude_domains:
            payload["exclude_domains"] = request.exclude_domains
        if request.exact_match is not None:
            payload["exact_match"] = request.exact_match
        return payload

    def _usage_for_request(
        self,
        request: TavilySearchRequest,
        *,
        result_count: int,
        response_time_seconds: float | None = None,
    ) -> TavilyUsageMetadata:
        search_depth = request.search_depth or self.settings.search_depth
        max_results = request.max_results or self.settings.max_results
        return TavilyUsageMetadata(
            endpoint=self.settings.endpoint,
            search_depth=search_depth,
            max_results=max_results,
            estimated_credits=_estimate_search_credits(search_depth),
            response_time_seconds=(
                round(response_time_seconds, 4)
                if response_time_seconds is not None
                else None
            ),
            request_params=_redacted_params(self._payload_for_request(request)),
            result_count=result_count,
        )

    def _resolved_api_keys(self) -> list[str]:
        keys: list[str] = []
        if self.settings.api_key:
            keys.append(self.settings.api_key)
        keys.extend(self.settings.api_keys)
        return _dedupe_api_keys(keys)

    def _api_key_attempt_order(self, api_keys: list[str]) -> list[tuple[int, str]]:
        active_indices = [
            index for index in range(len(api_keys)) if index not in self._disabled_api_key_indices
        ]
        if not active_indices:
            self._disabled_api_key_indices.clear()
            active_indices = list(range(len(api_keys)))
        start_index = self._next_api_key_index % len(api_keys)
        ordered_indices = list(range(start_index, len(api_keys))) + list(range(0, start_index))
        ordered_indices = [index for index in ordered_indices if index in active_indices]
        return [(index, api_keys[index]) for index in ordered_indices]


class SourceTavilyError(Exception):
    def __init__(self, message: str, *, retryable: bool, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.detail = detail or {}


def tavily_settings_from_app_settings(settings: Settings | None = None) -> TavilySearchSettings:
    app_settings = settings or get_settings()
    return TavilySearchSettings(
        api_key=(app_settings.tavily_api_key or None),
        api_keys=_parse_api_keys(app_settings.tavily_api_keys),
        search_depth=app_settings.tavily_search_depth,
        topic=app_settings.tavily_topic,
        country=app_settings.tavily_country,
        max_results=app_settings.tavily_max_results,
        auto_parameters=app_settings.tavily_auto_parameters,
        include_answer=app_settings.tavily_include_answer,
        include_raw_content=app_settings.tavily_include_raw_content,
        timeout_seconds=app_settings.tavily_timeout_seconds,
    )


def _default_transport(
    endpoint: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # nosec: B310
            body = response.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as exc:
        retryable = 500 <= int(exc.code) < 600
        raise SourceTavilyError(
            f"Tavily HTTP error {exc.code}",
            retryable=retryable,
            detail={"status_code": int(exc.code)},
        ) from exc
    except URLError as exc:
        raise SourceTavilyError(
            f"Tavily network error: {exc.reason}",
            retryable=True,
            detail={"reason": str(exc.reason)},
        ) from exc
    except json.JSONDecodeError as exc:
        raise SourceTavilyError(
            "Tavily response was not valid JSON.",
            retryable=False,
            detail={"error": str(exc)},
        ) from exc


def _parse_results(raw_response: dict[str, Any]) -> list[TavilySearchResult]:
    raw_results = raw_response.get("results")
    if not isinstance(raw_results, list):
        return []

    parsed: list[TavilySearchResult] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        parsed.append(
            TavilySearchResult(
                title=str(item.get("title") or ""),
                url=url,
                content=str(item.get("content") or ""),
                score=_safe_float(item.get("score")),
                published_date=(
                    str(item.get("published_date"))
                    if item.get("published_date") is not None
                    else None
                ),
                raw_content=(
                    str(item.get("raw_content"))
                    if item.get("raw_content") is not None
                    else None
                ),
            )
        )
    return parsed


def _estimate_search_credits(search_depth: str) -> int:
    return 2 if search_depth == "advanced" else 1


def _redacted_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if key.lower() != "api_key"}


def _parse_api_keys(value: str | None) -> list[str]:
    if not value:
        return []
    return _dedupe_api_keys(re.split(r"[,;\s]+", value))


def _dedupe_api_keys(values: list[str]) -> list[str]:
    keys: list[str] = []
    for value in values:
        normalized = value.strip().strip('"').strip("'")
        if normalized and normalized not in keys:
            keys.append(normalized)
    return keys


def _should_rotate_api_key(error: SourceTavilyError) -> bool:
    status_code = error.detail.get("status_code")
    return status_code in {401, 403, 429, 432}


def _query_with_exact_phrases(query: str, exact_phrases: list[str]) -> str:
    quoted_phrases = []
    for phrase in exact_phrases:
        normalized = str(phrase).strip().strip('"')
        if normalized and f'"{normalized}"' not in query:
            quoted_phrases.append(f'"{normalized}"')
    if not quoted_phrases:
        return query
    return f"{' '.join(quoted_phrases)} {query}"


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "SearchDiscoveryProvider",
    "SourceTavilyError",
    "TAVILY_SEARCH_ENDPOINT",
    "TavilySearchAdapter",
    "TavilySearchRequest",
    "TavilySearchResponse",
    "TavilySearchResult",
    "TavilySearchSettings",
    "TavilyUsageMetadata",
    "tavily_settings_from_app_settings",
]
