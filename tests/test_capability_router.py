"""G2.2 Deterministic Capability Routing tests.

覆盖：RoutingPlan 生成、strict/fallback policy、feature 过滤、deterministic trace、
Legacy vs Gateway 等价性、shadow 非干预、简单 Invoker 按 Plan 顺序尝试。
本轮不实现 concurrency/circuit/metrics/retry。
"""

from __future__ import annotations

import asyncio

from packages.capability_gateway import (
    CapabilityInvocation,
    CapabilityRequest,
    CapabilityResult,
    CapabilityRouter,
    CapabilityType,
    CircuitState,
    CostPolicy,
    ProviderAdapterRegistry,
    RoutingInvoker,
    RoutingPolicy,
    default_registry,
    llm_policy_for_task,
    llm_routing_mode,
    search_routing_mode,
    shadow_compare_from_settings,
    shadow_compare_search,
)
from packages.core.config import Settings

# ── 请求构造 helper ──────────────────────────────────────────────────────────

def _search_req() -> CapabilityRequest:
    return CapabilityRequest(
        capability=CapabilityType.SEARCH,
        task_type="research_discovery",
        requirements={"fresh_web": True, "max_results": 10},
        routing_policy=RoutingPolicy.FALLBACK_ALLOWED,
        cost_policy=CostPolicy.PREFER_LOW_COST,
    )


def _query_expansion() -> CapabilityRequest:
    return CapabilityRequest(
        capability=CapabilityType.LLM,
        task_type="query_expansion",
        requirements={"structured_output": False, "min_context_tokens": 8000},
        routing_policy=RoutingPolicy.FALLBACK_ALLOWED,
        cost_policy=CostPolicy.PREFER_LOW_COST,
    )


def _structured_extraction() -> CapabilityRequest:
    return CapabilityRequest(
        capability=CapabilityType.LLM,
        task_type="structured_extraction",
        requirements={"structured_output": True, "json_schema": True,
                      "min_context_tokens": 32000},
        routing_policy=RoutingPolicy.STRICT,
        cost_policy=CostPolicy.QUALITY_FIRST,
    )


# ── RoutingPlan 基础 ─────────────────────────────────────────────────────────

def test_search_plan_primary_and_fallback_chain():
    plan = CapabilityRouter(default_registry()).route(_search_req())
    assert plan.primary == "anysearch.primary"
    assert plan.fallback_chain == ["tavily.fallback"]
    assert plan.providers == ["anysearch.primary", "tavily.fallback"]
    assert plan.eligible == ["anysearch.primary", "tavily.fallback"]
    # SEARCH 请求会过滤掉 LLM 实例（capability_mismatch），但 SEARCH 实例全部合格
    assert set(plan.filtered) == {
        "deepseek.chat.primary",
        "openrouter.free.best_effort",
        "ollama.source_tier.local",
    }
    assert all(r.startswith("capability_mismatch") for r in plan.filtered.values())


def test_anysearch_disabled_promotes_tavily_to_primary():
    reg = default_registry()
    reg.get("anysearch.primary").enabled = False
    plan = CapabilityRouter(reg).route(_search_req())
    assert plan.primary == "tavily.fallback"
    assert plan.fallback_chain == []
    assert plan.filtered["anysearch.primary"] == "disabled"


def test_anysearch_circuit_open_promotes_tavily_to_primary():
    reg = default_registry()
    reg.get("anysearch.primary").circuit = CircuitState.OPEN
    plan = CapabilityRouter(reg).route(_search_req())
    assert plan.primary == "tavily.fallback"
    assert plan.filtered["anysearch.primary"] == "circuit_open"


# ── Strict / best-effort LLM ─────────────────────────────────────────────────

def test_structured_extraction_strict_deepseek_selected_openrouter_filtered():
    plan = CapabilityRouter(default_registry()).route(_structured_extraction())
    assert plan.primary == "deepseek.chat.primary"
    assert plan.fallback_chain == []
    assert plan.filtered["openrouter.free.best_effort"].startswith(
        ("missing_feature:", "insufficient_capacity")
    )


def test_structured_extraction_deepseek_unavailable_no_free_fallback():
    reg = default_registry()
    reg.get("deepseek.chat.primary").enabled = False
    plan = CapabilityRouter(reg).route(_structured_extraction())
    # strict：DeepSeek 不可用 → 无合格 Provider，绝不偷偷 free fallback
    assert plan.primary is None
    assert plan.fallback_chain == []
    assert plan.has_selection is False


def test_query_expansion_best_effort_deepseek_then_openrouter():
    plan = CapabilityRouter(default_registry()).route(_query_expansion())
    assert plan.primary == "deepseek.chat.primary"
    assert plan.fallback_chain == ["openrouter.free.best_effort"]
    assert plan.providers == ["deepseek.chat.primary", "openrouter.free.best_effort"]


def test_llm_policy_for_task():
    assert llm_policy_for_task("query_expansion") == RoutingPolicy.FALLBACK_ALLOWED
    assert llm_policy_for_task("search_phrase_generation") == RoutingPolicy.FALLBACK_ALLOWED
    assert llm_policy_for_task("structured_extraction") == RoutingPolicy.STRICT
    assert llm_policy_for_task("claim_generation") == RoutingPolicy.STRICT
    assert llm_policy_for_task("synthesis") == RoutingPolicy.STRICT


# ── Trace ────────────────────────────────────────────────────────────────────

def test_trace_has_reason_for_every_provider():
    plan = CapabilityRouter(default_registry()).route(_structured_extraction())
    # 每个被过滤 Provider 有 reason
    filtered_steps = [s for s in plan.trace.steps if s.result == "filtered"]
    # openrouter(missing_feature) + ollama(task_type_not_served) + 2 个 SEARCH(capability_mismatch)
    assert len(filtered_steps) == 4
    for step in filtered_steps:
        assert step.reason
    # selected 有确定 reason
    selected_steps = [s for s in plan.trace.steps if s.result == "selected"]
    assert len(selected_steps) == 1
    assert selected_steps[0].instance_id == "deepseek.chat.primary"
    assert selected_steps[0].reason == "highest_priority"


def test_route_is_deterministic():
    router = CapabilityRouter(default_registry())
    a = router.route(_search_req()).to_dict()
    b = router.route(_search_req()).to_dict()
    assert a == b


def test_plan_serializable():
    plan = CapabilityRouter(default_registry()).route(_search_req())
    d = plan.to_dict()
    assert d["capability"] == "search"
    assert d["primary"] == "anysearch.primary"
    assert "trace" in d and "steps" in d["trace"]


# ── Legacy vs Gateway shadow ─────────────────────────────────────────────────

def test_shadow_search_legacy_equals_gateway():
    router = CapabilityRouter(default_registry())
    report = shadow_compare_search(
        _search_req(), router,
        legacy_primary="anysearch", legacy_fallback="tavily",
        legacy_policy="fallback_allowed",
    )
    assert report.legacy_primary == "anysearch"
    assert report.gateway_primary == "anysearch.primary"
    assert report.legacy_fallback == "tavily"
    assert report.gateway_fallback == "tavily.fallback"
    assert report.equivalent is True
    assert report.divergences == []


def test_shadow_divergence_when_legacy_and_gateway_differ():
    reg = default_registry()
    reg.get("anysearch.primary").enabled = False  # gateway 现在选 tavily
    router = CapabilityRouter(reg)
    report = shadow_compare_search(
        _search_req(), router,
        legacy_primary="anysearch", legacy_fallback="tavily",
        legacy_policy="fallback_allowed",
    )
    assert report.equivalent is False
    assert any("primary" in d for d in report.divergences)


def test_shadow_from_settings_equivalent_on_default_baseline():
    settings = Settings(
        _env_file=None,
        SEARCH_DISCOVERY_PROVIDER="anysearch",
        SEARCH_DISCOVERY_FALLBACK_PROVIDER="tavily",
        SEARCH_DISCOVERY_FALLBACK_ENABLED=True,
        SEARCH_PROVIDER_POLICY="fallback_allowed",
    )
    reg = default_registry()
    report = shadow_compare_from_settings(reg, CapabilityRouter(reg), settings=settings)
    assert report.equivalent is True


def test_shadow_does_not_invoke_provider():
    """Shadow 只算不改：正式 Provider 的 transport 不能被触发。"""
    from packages.sources.search_discovery import build_search_discovery_provider

    settings = Settings(
        _env_file=None,
        SEARCH_DISCOVERY_PROVIDER="anysearch",
        SEARCH_DISCOVERY_FALLBACK_PROVIDER="tavily",
        SEARCH_DISCOVERY_FALLBACK_ENABLED=True,
        SEARCH_PROVIDER_POLICY="fallback_allowed",
        ANYSEARCH_API_KEY=None,
    )
    calls: list[str] = []

    def _fake_transport(endpoint, payload, headers, timeout):  # noqa: ARG001
        calls.append(endpoint)
        return {"results": []}

    build_search_discovery_provider(
        settings, anysearch_transport=_fake_transport, tavily_transport=_fake_transport
    )
    # 构建 Provider 本身不调用 transport
    assert calls == []

    reg = default_registry()
    report = shadow_compare_from_settings(reg, CapabilityRouter(reg), settings=settings)
    assert report.equivalent is True
    assert calls == []  # shadow 之后仍未触发任何 Provider 调用


# ── Feature flag / Gateway disabled ──────────────────────────────────────────

def test_routing_modes_off_by_default():
    settings = Settings(_env_file=None, CAPABILITY_GATEWAY_ENABLED=False)
    assert search_routing_mode(settings) == "off"
    assert llm_routing_mode(settings) == "off"


def test_routing_modes_shadow_when_enabled():
    settings = Settings(
        _env_file=None,
        CAPABILITY_GATEWAY_ENABLED=True,
        CAPABILITY_GATEWAY_SEARCH_MODE="shadow",
        CAPABILITY_GATEWAY_LLM_MODE="off",
    )
    assert search_routing_mode(settings) == "shadow"
    assert llm_routing_mode(settings) == "off"


def test_gateway_disabled_keeps_legacy_provider():
    """Gateway disabled 时，正式路径仍是 FallbackSearchDiscoveryAdapter(anysearch→tavily)。"""
    from packages.sources.search_discovery import (
        FallbackSearchDiscoveryAdapter,
        build_search_discovery_provider,
    )

    settings = Settings(
        _env_file=None,
        CAPABILITY_GATEWAY_ENABLED=False,
        CAPABILITY_GATEWAY_SEARCH_MODE="gateway",  # 即便配成 gateway，总开关关=Legacy
        SEARCH_DISCOVERY_PROVIDER="anysearch",
        SEARCH_DISCOVERY_FALLBACK_PROVIDER="tavily",
        SEARCH_DISCOVERY_FALLBACK_ENABLED=True,
    )
    provider = build_search_discovery_provider(settings)
    assert isinstance(provider, FallbackSearchDiscoveryAdapter)
    assert search_routing_mode(settings) == "off"


# ── Invoker（复用现有 fallback 判定：非 success 继续尝试） ─────────────────────

class _FakeAdapter:
    """实现 CapabilityAdapter Protocol 的桩：按构造参数返回 success 与否。"""

    def __init__(self, instance_id: str, succeed: bool):
        self._instance_id = instance_id
        self._succeed = succeed

    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult:
        return CapabilityResult(
            provider_id=invocation.provider_id,
            success=self._succeed,
            data={"called": invocation.provider_id},
        )


def test_invoker_tries_primary_then_fallback():
    registry = ProviderAdapterRegistry()
    registry.register("anysearch.primary", _FakeAdapter("anysearch.primary", succeed=False))
    registry.register("tavily.fallback", _FakeAdapter("tavily.fallback", succeed=True))

    plan = CapabilityRouter(default_registry()).route(_search_req())
    result = asyncio.run(RoutingInvoker(registry).invoke(plan, {"request": None}))
    assert result.provider_id == "tavily.fallback"
    assert result.success is True


def test_invoker_stops_when_primary_succeeds():
    calls: list[str] = []

    class _Recorder(_FakeAdapter):
        async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult:
            calls.append(invocation.provider_id)
            return await super().invoke(invocation)

    registry = ProviderAdapterRegistry()
    registry.register("anysearch.primary", _Recorder("anysearch.primary", succeed=True))
    registry.register("tavily.fallback", _Recorder("tavily.fallback", succeed=True))

    plan = CapabilityRouter(default_registry()).route(_search_req())
    result = asyncio.run(RoutingInvoker(registry).invoke(plan, {"request": None}))
    assert result.provider_id == "anysearch.primary"
    assert calls == ["anysearch.primary"]  # fallback 未被调用


def test_invoker_all_fail_returns_error():
    registry = ProviderAdapterRegistry()
    registry.register("anysearch.primary", _FakeAdapter("anysearch.primary", succeed=False))
    registry.register("tavily.fallback", _FakeAdapter("tavily.fallback", succeed=False))

    plan = CapabilityRouter(default_registry()).route(_search_req())
    result = asyncio.run(RoutingInvoker(registry).invoke(plan, {"request": None}))
    assert result.success is False
    assert result.error == "all_providers_failed"
