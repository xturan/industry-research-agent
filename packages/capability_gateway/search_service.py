"""G2.2b SearchCapabilityService — 统一 SEARCH 入口（off/shadow/gateway 三态）。

业务层不判断 feature flag，只调用这个 Provider（实现现有 `SearchDiscoveryProvider`
协议，下游仍是统一 `SearchDiscoveryResponse`）。

mode 语义（enabled=false 优先于 mode）：
    off     → 完全 Legacy（build_search_discovery_provider 原逻辑）
    shadow  → Legacy 正式执行 + Gateway 只 route 对比（不 invoke）
    gateway → Gateway route + Adapter invoke（Legacy selector 不执行）

Gateway 正式路径：
    CapabilityRequest → Registry → Router → RoutingPlan
    → ProviderAdapterRegistry → RoutingInvoker → 现有 AnySearch/Tavily client

不复制现有 Provider HTTP client；Adapter 只桥接/规范化。
Routing diagnostic 挂 raw_response_metadata，不写 RunEvent（G2.5 再持久化）。
"""

from __future__ import annotations

import asyncio
from typing import Any

from packages.capability_gateway.adapters import (
    RoutingInvoker,
    build_search_adapter_registry,
)
from packages.capability_gateway.registry import default_registry
from packages.capability_gateway.router import CapabilityRouter, search_routing_mode
from packages.capability_gateway.schemas import (
    CapabilityRequest,
    CapabilityType,
    CostPolicy,
    RoutingPolicy,
)
from packages.capability_gateway.shadow import (
    LEGACY_PROVIDER_TO_INSTANCE,
    RoutingShadowReport,
    shadow_compare_search,
)


def search_capability_request(
    request: Any, settings: Any = None
) -> CapabilityRequest:
    """从现有 SearchDiscoveryRequest 构建 CapabilityRequest（SEARCH）。"""
    max_results = getattr(request, "max_results", None)
    if max_results is None and settings is not None:
        max_results = getattr(settings, "anysearch_max_results", None)
    requirements: dict[str, Any] = {"fresh_web": True}
    if max_results:
        requirements["max_results"] = int(max_results)
    return CapabilityRequest(
        capability=CapabilityType.SEARCH,
        task_type="research_discovery",
        requirements=requirements,
        routing_policy=RoutingPolicy.FALLBACK_ALLOWED,
        cost_policy=CostPolicy.PREFER_LOW_COST,
    )


class SearchCapabilityService:
    """统一 SEARCH 入口。实现 `SearchDiscoveryProvider` 协议（search/search_task）。"""

    def __init__(
        self,
        *,
        settings: Any,
        router: CapabilityRouter,
        invoker: RoutingInvoker,
        legacy_factory: Any,
    ) -> None:
        self._settings = settings
        self._router = router
        self._invoker = invoker
        self._legacy_factory = legacy_factory
        self._legacy_provider = None

    # ── 内部 ──────────────────────────────────────────────────────────────────

    def _legacy(self):
        if self._legacy_provider is None:
            self._legacy_provider = self._legacy_factory()
        return self._legacy_provider

    def _mode(self) -> str:
        return search_routing_mode(self._settings)

    def _attach(self, response: Any, diagnostic: dict[str, Any]) -> Any:
        response.raw_response_metadata = {
            **dict(response.raw_response_metadata or {}),
            "capability_routing": diagnostic,
        }
        return response

    # ── 三态实现 ──────────────────────────────────────────────────────────────

    def search(self, request) -> Any:
        mode = self._mode()
        if mode == "gateway":
            return self._gateway_search(request)
        response = self._legacy().search(request)
        if mode == "shadow":
            self._attach_shadow_diagnostic(response, request)
        return response

    def search_task(self, task) -> list[Any]:
        mode = self._mode()
        if mode == "gateway":
            return self._gateway_search_task(task)
        responses = self._legacy().search_task(task)
        if mode == "shadow":
            for response in responses:
                self._attach_shadow_diagnostic(response, getattr(response, "query", None))
        return responses

    # ── gateway ───────────────────────────────────────────────────────────────

    def _gateway_search(self, request) -> Any:
        from packages.sources.search_discovery import SearchDiscoveryResponse

        cap_req = search_capability_request(request, self._settings)
        plan = self._router.route(cap_req)
        result = asyncio.run(self._invoker.invoke(plan, {"request": request}))
        response = result.data if isinstance(result.data, SearchDiscoveryResponse) else None
        if response is None:
            response = self._synthesize_error(request, result)
        diagnostic = {
            "mode": "gateway",
            "request_fingerprint": plan.request_fingerprint,
            "route_execution_id": result.route_execution_id,
            "provider_call_id": result.provider_call_id,
            "planned_primary": plan.primary,
            "planned_fallback_chain": list(plan.fallback_chain),
            "executed_provider": result.provider_id,
            "fallback_used": plan.primary is not None and result.provider_id != plan.primary,
        }
        return self._attach(response, diagnostic)

    def _gateway_search_task(self, task) -> list[Any]:
        from packages.sources.search_discovery import (
            SearchDiscoveryRequest,
            _query_with_exact_phrases,
        )

        return [
            self.search(
                SearchDiscoveryRequest(
                    query=_query_with_exact_phrases(phrase, task.exact_phrases),
                    include_domains=task.include_domains,
                    exclude_domains=task.exclude_domains,
                    exact_match=bool(task.exact_phrases),
                )
            )
            for phrase in task.search_phrases
        ]

    def _synthesize_error(self, request, result) -> Any:
        from packages.sources.enums import ToolErrorCode, ToolStatus
        from packages.sources.schemas import ToolError
        from packages.sources.search_discovery import SearchDiscoveryResponse

        return SearchDiscoveryResponse(
            status=ToolStatus.ERROR,
            query=getattr(request, "query", None),
            results=[],
            errors=[
                ToolError(
                    code=ToolErrorCode.INTERNAL_ERROR,
                    message=str(result.error or "all search providers failed"),
                    retryable=True,
                )
            ],
            raw_response_metadata={
                "provider_attempted": [],
                "provider_used": None,
                "fallback_used": False,
            },
        )

    # ── shadow（只 route 对比，不 invoke） ─────────────────────────────────────

    def _attach_shadow_diagnostic(self, response, request) -> None:
        try:
            cap_req = search_capability_request(request, self._settings)
            plan = self._router.route(cap_req)
            report = self._shadow_report(cap_req)
            diagnostic = {
                "mode": "shadow",
                "request_fingerprint": plan.request_fingerprint,
                "planned_primary": plan.primary,
                "planned_fallback_chain": list(plan.fallback_chain),
                "equivalent": report.equivalent,
                "divergences": list(report.divergences),
            }
        except Exception:  # noqa: BLE001 - shadow 是诊断，绝不干扰主路径
            diagnostic = {"mode": "shadow", "error": "shadow_compute_failed"}
        self._attach(response, diagnostic)

    def _shadow_report(self, cap_req: CapabilityRequest) -> RoutingShadowReport:
        legacy_primary = str(
            getattr(self._settings, "search_discovery_provider", "anysearch") or "anysearch"
        )
        legacy_fallback = None
        if getattr(self._settings, "search_discovery_fallback_enabled", True):
            legacy_fallback = str(
                getattr(self._settings, "search_discovery_fallback_provider", "tavily")
                or "tavily"
            )
        legacy_policy = str(
            getattr(self._settings, "search_provider_policy", "fallback_allowed")
            or "fallback_allowed"
        )
        return shadow_compare_search(
            cap_req, self._router,
            legacy_primary=legacy_primary,
            legacy_fallback=legacy_fallback,
            legacy_policy=legacy_policy,
        )


def build_gateway_aware_search_provider(
    settings: Any = None,
    *,
    anysearch_transport: Any = None,
    tavily_transport: Any = None,
    budget: Any = None,
    recorder: Any = None,
) -> SearchCapabilityService:
    """生产统一入口：off/shadow/gateway 三态，返回 SearchDiscoveryProvider 兼容对象。

    - settings=None → get_settings()。
    - transport 可注入（测试用 fake）。
    - budget 可选（G2.3 Concurrency Budget）；None = 不启用预算。
    - recorder 可选（G2.5 ProviderAttemptRecorder）；None = 不记录 telemetry。
    - 返回对象是 SearchCapabilityService（实现 search/search_task 协议）。
    """
    from packages.core.config import get_settings
    from packages.sources.search_discovery import build_search_discovery_provider

    app = settings or get_settings()
    registry = default_registry()
    router = CapabilityRouter(registry)
    adapter_registry = build_search_adapter_registry(
        app,
        anysearch_transport=anysearch_transport,
        tavily_transport=tavily_transport,
    )
    invoker = RoutingInvoker(adapter_registry, budget=budget, recorder=recorder)

    def _legacy_factory():
        return build_search_discovery_provider(
            app,
            anysearch_transport=anysearch_transport,
            tavily_transport=tavily_transport,
        )

    return SearchCapabilityService(
        settings=app,
        router=router,
        invoker=invoker,
        legacy_factory=_legacy_factory,
    )


__all__ = [
    "LEGACY_PROVIDER_TO_INSTANCE",
    "SearchCapabilityService",
    "build_gateway_aware_search_provider",
    "search_capability_request",
]
