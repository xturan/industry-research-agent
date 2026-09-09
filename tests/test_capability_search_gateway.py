"""G2.2b Search Gateway Primary — Runtime Equivalence tests.

验证：SEARCH 真正走 Gateway 后，返回结果 / 异常语义 / fallback 行为与 Legacy
完全一致。三态（off/shadow/gateway）+ 三种运行时场景（primary success /
primary ERROR→fallback success / all ERROR）+ fingerprint/execution_id。

本轮不实现 concurrency/circuit/metrics/retry（G2.3/G2.4/G2.5）。
"""

from __future__ import annotations

from packages.capability_gateway import (
    CapabilityRouter,
    RoutingInvoker,
    SearchCapabilityService,
    build_gateway_aware_search_provider,
    build_search_adapter_registry,
    default_registry,
)
from packages.core.config import Settings
from packages.sources.enums import ToolStatus
from packages.sources.search_discovery import (
    SearchDiscoveryRequest,
    SourceAnySearchError,
    SourceTavilyError,
    build_search_discovery_provider,
)

# ── fake transport ───────────────────────────────────────────────────────────

def _any_success(endpoint, payload, headers, timeout):  # noqa: ARG001
    return {
        "result": {
            "content": [{
                "type": "text",
                "text": "### 1. 合肥低空经济政策\n"
                        "- **URL**: https://example.com/hefei\n正文内容",
            }]
        }
    }


def _any_error(endpoint, payload, headers, timeout):  # noqa: ARG001
    raise SourceAnySearchError("anysearch down", retryable=True,
                              detail={"status_code": 500})


def _tavily_success(endpoint, payload, headers, timeout):  # noqa: ARG001
    return {
        "results": [{
            "title": "合肥低空经济", "url": "https://tavily.com/hefei",
            "content": "政策全文",
        }]
    }


def _tavily_error(endpoint, payload, headers, timeout):  # noqa: ARG001
    raise SourceTavilyError("tavily down", retryable=True,
                           detail={"status_code": 500})


def _recorder(calls: list[str], label: str, transport):
    def _f(endpoint, payload, headers, timeout):  # noqa: ARG001
        calls.append(label)
        return transport(endpoint, payload, headers, timeout)
    return _f


# ── helpers ──────────────────────────────────────────────────────────────────

def _settings(enabled: bool = True, search_mode: str = "gateway") -> Settings:
    return Settings(
        _env_file=None,
        CAPABILITY_GATEWAY_ENABLED=enabled,
        CAPABILITY_GATEWAY_SEARCH_MODE=search_mode,
        CAPABILITY_GATEWAY_LLM_MODE="off",
        SEARCH_DISCOVERY_PROVIDER="anysearch",
        SEARCH_DISCOVERY_FALLBACK_PROVIDER="tavily",
        SEARCH_DISCOVERY_FALLBACK_ENABLED=True,
        SEARCH_PROVIDER_POLICY="fallback_allowed",
        TAVILY_API_KEY="test-key",
    )


def _request() -> SearchDiscoveryRequest:
    return SearchDiscoveryRequest(query="合肥低空经济 政策", max_results=5)


# ── 三态 mode 行为 ───────────────────────────────────────────────────────────

def test_gateway_disabled_uses_legacy():
    settings = _settings(enabled=False, search_mode="gateway")  # enabled=false > mode
    calls: list[str] = []
    provider = build_gateway_aware_search_provider(
        settings,
        anysearch_transport=_recorder(calls, "anysearch", _any_success),
        tavily_transport=_recorder(calls, "tavily", _tavily_success),
    )
    resp = provider.search(_request())
    assert resp.status == ToolStatus.SUCCESS
    assert calls == ["anysearch"]  # Legacy only
    assert "capability_routing" not in (resp.raw_response_metadata or {})


def test_search_mode_off_uses_legacy():
    settings = _settings(enabled=True, search_mode="off")
    calls: list[str] = []
    provider = build_gateway_aware_search_provider(
        settings,
        anysearch_transport=_recorder(calls, "anysearch", _any_success),
        tavily_transport=_recorder(calls, "tavily", _tavily_success),
    )
    resp = provider.search(_request())
    assert resp.status == ToolStatus.SUCCESS
    assert calls == ["anysearch"]
    assert "capability_routing" not in (resp.raw_response_metadata or {})


def test_search_mode_shadow_legacy_executes_gateway_not_invoked():
    """shadow：Legacy 正式执行一次；Gateway adapter transport 0 次。"""
    settings = _settings(enabled=True, search_mode="shadow")
    legacy_calls: list[str] = []
    gateway_calls: list[str] = []

    router = CapabilityRouter(default_registry())
    adapter_registry = build_search_adapter_registry(
        settings,
        anysearch_transport=_recorder(gateway_calls, "anysearch", _any_success),
        tavily_transport=_recorder(gateway_calls, "tavily", _tavily_success),
    )

    def _legacy_factory():
        return build_search_discovery_provider(
            settings,
            anysearch_transport=_recorder(legacy_calls, "anysearch", _any_success),
            tavily_transport=_recorder(legacy_calls, "tavily", _tavily_success),
        )

    svc = SearchCapabilityService(
        settings=settings, router=router,
        invoker=RoutingInvoker(adapter_registry), legacy_factory=_legacy_factory,
    )
    resp = svc.search(_request())
    assert resp.status == ToolStatus.SUCCESS
    assert legacy_calls == ["anysearch"]  # Legacy 调用一次
    assert gateway_calls == []  # Gateway transport 0 次
    assert resp.raw_response_metadata["capability_routing"]["mode"] == "shadow"
    assert resp.raw_response_metadata["capability_routing"]["equivalent"] is True


def test_search_mode_gateway_legacy_selector_not_executed():
    settings = _settings(enabled=True, search_mode="gateway")
    router = CapabilityRouter(default_registry())
    adapter_registry = build_search_adapter_registry(
        settings,
        anysearch_transport=_any_success,
        tavily_transport=_tavily_success,
    )

    def _legacy_factory():
        raise AssertionError("gateway mode 下 Legacy selector 不得执行")

    svc = SearchCapabilityService(
        settings=settings, router=router,
        invoker=RoutingInvoker(adapter_registry), legacy_factory=_legacy_factory,
    )
    resp = svc.search(_request())
    assert resp.status == ToolStatus.SUCCESS
    assert resp.raw_response_metadata["capability_routing"]["mode"] == "gateway"


# ── Gateway 行为：primary success / fallback / all error ─────────────────────

def test_gateway_anysearch_success_only_anysearch_called():
    settings = _settings(enabled=True, search_mode="gateway")
    calls: list[str] = []
    provider = build_gateway_aware_search_provider(
        settings,
        anysearch_transport=_recorder(calls, "anysearch", _any_success),
        tavily_transport=_recorder(calls, "tavily", _tavily_success),
    )
    resp = provider.search(_request())
    assert resp.status == ToolStatus.SUCCESS
    assert calls == ["anysearch"]  # Tavily 调用次数 0
    # provider identity 归一化（下游看到 anysearch，不是 instance_id）
    assert resp.usage.provider == "anysearch"
    routing = resp.raw_response_metadata["capability_routing"]
    assert routing["executed_provider"] == "anysearch.primary"
    assert routing["fallback_used"] is False


def test_gateway_anysearch_error_then_tavily():
    settings = _settings(enabled=True, search_mode="gateway")
    calls: list[str] = []
    provider = build_gateway_aware_search_provider(
        settings,
        anysearch_transport=_recorder(calls, "anysearch", _any_error),
        tavily_transport=_recorder(calls, "tavily", _tavily_success),
    )
    resp = provider.search(_request())
    assert resp.status == ToolStatus.SUCCESS
    assert calls == ["anysearch", "tavily"]
    assert resp.usage.provider == "tavily"
    routing = resp.raw_response_metadata["capability_routing"]
    assert routing["fallback_used"] is True
    assert routing["executed_provider"] == "tavily.fallback"


def test_gateway_all_error_returns_last_provider_failure():
    settings = _settings(enabled=True, search_mode="gateway")
    calls: list[str] = []
    provider = build_gateway_aware_search_provider(
        settings,
        anysearch_transport=_recorder(calls, "anysearch", _any_error),
        tavily_transport=_recorder(calls, "tavily", _tavily_error),
    )
    resp = provider.search(_request())
    assert resp.status == ToolStatus.ERROR
    assert calls == ["anysearch", "tavily"]
    assert resp.errors  # 保留失败 Contract（errors 非空）


# ── Legacy / Gateway Runtime Equivalence ────────────────────────────────────

def test_runtime_equivalence_case1_primary_success():
    settings = _settings(enabled=True, search_mode="gateway")
    legacy_calls: list[str] = []
    gw_calls: list[str] = []

    legacy = build_search_discovery_provider(
        settings,
        anysearch_transport=_recorder(legacy_calls, "anysearch", _any_success),
        tavily_transport=_recorder(legacy_calls, "tavily", _tavily_success),
    )
    gateway = build_gateway_aware_search_provider(
        settings,
        anysearch_transport=_recorder(gw_calls, "anysearch", _any_success),
        tavily_transport=_recorder(gw_calls, "tavily", _tavily_success),
    )
    lr = legacy.search(_request())
    gr = gateway.search(_request())
    assert legacy_calls == ["anysearch"]
    assert gw_calls == ["anysearch"]
    assert lr.status == gr.status == ToolStatus.SUCCESS
    assert [r.url for r in lr.results] == [r.url for r in gr.results]


def test_runtime_equivalence_case2_fallback_success():
    settings = _settings(enabled=True, search_mode="gateway")
    legacy_calls: list[str] = []
    gw_calls: list[str] = []

    legacy = build_search_discovery_provider(
        settings,
        anysearch_transport=_recorder(legacy_calls, "anysearch", _any_error),
        tavily_transport=_recorder(legacy_calls, "tavily", _tavily_success),
    )
    gateway = build_gateway_aware_search_provider(
        settings,
        anysearch_transport=_recorder(gw_calls, "anysearch", _any_error),
        tavily_transport=_recorder(gw_calls, "tavily", _tavily_success),
    )
    lr = legacy.search(_request())
    gr = gateway.search(_request())
    assert legacy_calls == ["anysearch", "tavily"]
    assert gw_calls == ["anysearch", "tavily"]
    assert lr.status == gr.status == ToolStatus.SUCCESS
    assert lr.usage.provider == gr.usage.provider == "tavily"
    assert [r.url for r in lr.results] == [r.url for r in gr.results]


def test_runtime_equivalence_case3_all_error():
    settings = _settings(enabled=True, search_mode="gateway")
    legacy_calls: list[str] = []
    gw_calls: list[str] = []

    legacy = build_search_discovery_provider(
        settings,
        anysearch_transport=_recorder(legacy_calls, "anysearch", _any_error),
        tavily_transport=_recorder(legacy_calls, "tavily", _tavily_error),
    )
    gateway = build_gateway_aware_search_provider(
        settings,
        anysearch_transport=_recorder(gw_calls, "anysearch", _any_error),
        tavily_transport=_recorder(gw_calls, "tavily", _tavily_error),
    )
    lr = legacy.search(_request())
    gr = gateway.search(_request())
    assert legacy_calls == ["anysearch", "tavily"]
    assert gw_calls == ["anysearch", "tavily"]
    # 失败 Contract：status + error 语义一致
    assert lr.status == gr.status == ToolStatus.ERROR
    assert bool(lr.errors) == bool(gr.errors)
    assert [e.retryable for e in lr.errors] == [e.retryable for e in gr.errors]


def test_gateway_output_schema_matches_legacy():
    settings = _settings(enabled=True, search_mode="gateway")
    legacy = build_search_discovery_provider(
        settings,
        anysearch_transport=_any_success, tavily_transport=_tavily_success,
    )
    gateway = build_gateway_aware_search_provider(
        settings,
        anysearch_transport=_any_success, tavily_transport=_tavily_success,
    )
    lr = legacy.search(_request())
    gr = gateway.search(_request())
    # 除 raw_response_metadata（诊断字段，按设计不同）外，Schema 一致
    assert lr.status == gr.status
    assert lr.query == gr.query
    assert [r.url for r in lr.results] == [r.url for r in gr.results]
    assert bool(lr.errors) == bool(gr.errors)


# ── fingerprint / execution_id ───────────────────────────────────────────────

def test_request_fingerprint_stable_route_execution_id_unique():
    settings = _settings(enabled=True, search_mode="gateway")
    provider = build_gateway_aware_search_provider(
        settings,
        anysearch_transport=_any_success, tavily_transport=_tavily_success,
    )
    r1 = provider.search(_request())
    r2 = provider.search(_request())
    fp1 = r1.raw_response_metadata["capability_routing"]["request_fingerprint"]
    fp2 = r2.raw_response_metadata["capability_routing"]["request_fingerprint"]
    eid1 = r1.raw_response_metadata["capability_routing"]["route_execution_id"]
    eid2 = r2.raw_response_metadata["capability_routing"]["route_execution_id"]
    assert fp1 == fp2  # 同请求 → 同指纹（确定性）
    assert eid1 != eid2  # 每次调用 → 唯一 route_execution_id


# ── G2.8 修复回归：full protection stack + fallback + telemetry ──────────────

def test_gateway_search_full_protection_fallback_records_telemetry():
    """G2.8：budget/circuit/recorder/run_id + FallbackPolicy 全套注入时，
    AnySearch ERROR → Tavily SUCCESS 真实回退，且 telemetry 记录两次 attempt
    （run_id 归因 + fallback 标志 + 顶层 provider_used 元数据）。"""
    from packages.capability_gateway import (
        CircuitBreaker,
        FallbackPolicy,
        InMemoryCircuitStateStore,
        InMemoryProviderAttemptRecorder,
        policy_from_instance,
    )
    from packages.capability_gateway.budget import InProcessConcurrencyBudget

    settings = _settings(enabled=True, search_mode="gateway")
    recorder = InMemoryProviderAttemptRecorder()
    policies = {
        inst.instance_id: policy_from_instance(inst) for inst in default_registry().all()
    }
    provider = build_gateway_aware_search_provider(
        settings,
        anysearch_transport=_any_error,
        tavily_transport=_tavily_success,
        budget=InProcessConcurrencyBudget(policies),
        circuit=CircuitBreaker(InMemoryCircuitStateStore()),
        fallback_policy=FallbackPolicy(),
        recorder=recorder,
        run_id_provider=lambda: "run-42",
    )
    resp = provider.search(_request())
    assert resp.status == ToolStatus.SUCCESS
    # 顶层回退元数据（与 legacy _provider_metadata 同构）
    assert resp.raw_response_metadata["provider_used"] == "tavily.fallback"
    assert resp.raw_response_metadata["fallback_used"] is True
    assert "tavily.fallback" in resp.raw_response_metadata["provider_attempted"]
    # telemetry：2 次 attempt，主失败 + fallback 成功，run_id 归因
    recs = recorder.all()
    assert len(recs) == 2
    assert recs[0].provider_instance_id == "anysearch.primary"
    assert recs[0].outcome == "failed"
    assert recs[1].provider_instance_id == "tavily.fallback"
    assert recs[1].outcome == "success"
    assert recs[0].run_id == recs[1].run_id == "run-42"
    assert recs[1].fallback_used is True


def test_gateway_fallback_on_network_error_without_status_code():
    """网络层错误（如 SSL UNEXPECTED_EOF，detail 只有 reason 无 status_code）
    必须归类为 NETWORK 触发 fallback，而不是 OUTPUT_INVALID 不兜底。"""
    from packages.capability_gateway import (
        CircuitBreaker,
        FallbackPolicy,
        InMemoryCircuitStateStore,
        InMemoryProviderAttemptRecorder,
        policy_from_instance,
    )
    from packages.capability_gateway.budget import InProcessConcurrencyBudget

    settings = _settings(enabled=True, search_mode="gateway")
    recorder = InMemoryProviderAttemptRecorder()
    policies = {
        inst.instance_id: policy_from_instance(inst) for inst in default_registry().all()
    }

    # AnySearch 返回 SSL 断连错误（detail 只有 reason，无 status_code）
    def _any_ssl_error(endpoint, payload, headers, timeout):
        from packages.sources.search_discovery import SourceAnySearchError

        raise SourceAnySearchError(
            "AnySearch network error: [SSL: UNEXPECTED_EOF_WHILE_READING]",
            retryable=True,
            detail={"reason": "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred"},
        )

    provider = build_gateway_aware_search_provider(
        settings,
        anysearch_transport=_any_ssl_error,
        tavily_transport=_tavily_success,
        budget=InProcessConcurrencyBudget(policies),
        circuit=CircuitBreaker(InMemoryCircuitStateStore()),
        fallback_policy=FallbackPolicy(),
        recorder=recorder,
    )
    resp = provider.search(_request())
    assert resp.status == ToolStatus.SUCCESS  # Tavily 兜底成功
    assert resp.raw_response_metadata["fallback_used"] is True
    assert resp.raw_response_metadata["provider_used"] == "tavily.fallback"
    recs = recorder.all()
    assert len(recs) == 2
    assert recs[0].provider_instance_id == "anysearch.primary"
    assert recs[0].outcome == "failed"
    assert recs[0].failure_class == "network"  # 归类为 NETWORK 才允许 fallback
    assert recs[1].provider_instance_id == "tavily.fallback"
    assert recs[1].outcome == "success"
