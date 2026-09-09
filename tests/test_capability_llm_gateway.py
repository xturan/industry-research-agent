"""G2-M1 LLM Gateway Production Wiring tests。

验证 LLMCapabilityService 从 plan-only 升级为正式执行 facade：
off/shadow/gateway 三态；strict → DeepSeek only；best-effort → DeepSeek→OpenRouter
fallback；telemetry 记录；circuit OPEN 跳过 provider。
"""

from __future__ import annotations

import pytest

from packages.capability_gateway import (
    CapabilityRouter,
    CircuitBreaker,
    FallbackPolicy,
    InMemoryCircuitStateStore,
    InMemoryProviderAttemptRecorder,
    LLMCapabilityService,
    LLMTaskType,
    ProviderFailureClass,
    RoutingInvoker,
    build_llm_adapter_registry,
    default_registry,
)
from packages.core.config import Settings


class _FakeResp:
    def __init__(self, json_data=None, provider="fake", model="m"):
        self.json_data = json_data if json_data is not None else {}
        self.provider = provider
        self.model = model
        self.metadata = type(
            "M", (), {"usage": {"input_tokens": 10, "output_tokens": 5}, "extra": {}}
        )()


class _FakeLLMClient:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = 0

    def generate_json(self, **kwargs):
        self.calls += 1
        if self.fail:
            from packages.providers.base import ProviderRetryableError

            raise ProviderRetryableError("provider timeout")
        return _FakeResp(json_data={"ok": True}, provider="deepseek", model="deepseek-chat")

    def generate_text(self, **kwargs):
        return self.generate_json(**kwargs)


def _settings(mode: str) -> Settings:
    return Settings(
        _env_file=None,
        CAPABILITY_GATEWAY_ENABLED=True,
        CAPABILITY_GATEWAY_SEARCH_MODE="shadow",
        CAPABILITY_GATEWAY_LLM_MODE=mode,
    )


def _svc(mode: str, *, deepseek_fail: bool = False, recorder=None, circuit=None):
    settings = _settings(mode)
    router = CapabilityRouter(default_registry())
    ds = _FakeLLMClient(fail=deepseek_fail)
    or_client = _FakeLLMClient()
    adapter_reg = build_llm_adapter_registry(
        settings, deepseek_client=ds, openrouter_client=or_client
    )
    invoker = RoutingInvoker(
        adapter_reg, circuit=circuit, recorder=recorder, fallback_policy=FallbackPolicy()
    )
    svc = LLMCapabilityService(
        settings=settings, router=router, invoker=invoker,
        adapter_registry=adapter_reg, legacy_factory=lambda: ds,
    )
    return svc, ds, or_client


# ── off / shadow ─────────────────────────────────────────────────────────────

def test_off_mode_calls_legacy_no_gateway():
    svc, ds, or_client = _svc("off")
    resp = svc.generate_json(
        LLMTaskType.EVIDENCE_EXTRACTION, system_prompt="s", user_prompt="u"
    )
    assert resp.json_data == {"ok": True}
    assert ds.calls == 1 and or_client.calls == 0
    assert "capability_routing" not in resp.metadata.extra  # off 无诊断


def test_shadow_mode_calls_legacy_and_attaches_diagnostic():
    svc, ds, or_client = _svc("shadow")
    resp = svc.generate_json(
        LLMTaskType.EVIDENCE_EXTRACTION, system_prompt="s", user_prompt="u"
    )
    assert ds.calls == 1 and or_client.calls == 0
    assert "capability_routing" in resp.metadata.extra  # shadow 挂 route 诊断


# ── gateway：strict → DeepSeek only ──────────────────────────────────────────

def test_gateway_strict_routes_to_deepseek_only():
    recorder = InMemoryProviderAttemptRecorder()
    svc, ds, or_client = _svc("gateway", recorder=recorder)
    resp = svc.generate_json(
        LLMTaskType.EVIDENCE_EXTRACTION, system_prompt="s", user_prompt="u"
    )
    assert resp.json_data == {"ok": True}
    assert ds.calls == 1 and or_client.calls == 0  # STRICT 不 fallback
    recs = recorder.all()
    assert len(recs) == 1
    assert recs[0].outcome == "success"
    assert recs[0].provider_instance_id == "deepseek.chat.primary"
    assert recs[0].task_type == "evidence_extraction"


def test_gateway_strict_deepseek_fail_no_fallback():
    svc, ds, or_client = _svc("gateway", deepseek_fail=True)
    from packages.providers.base import ProviderRetryableError

    with pytest.raises(ProviderRetryableError):
        svc.generate_json(
            LLMTaskType.EVIDENCE_EXTRACTION, system_prompt="s", user_prompt="u"
        )
    assert ds.calls == 1 and or_client.calls == 0  # 绝不 fallback


# ── gateway：best-effort → DeepSeek → OpenRouter ─────────────────────────────

def test_gateway_best_effort_falls_back_to_openrouter():
    recorder = InMemoryProviderAttemptRecorder()
    svc, ds, or_client = _svc("gateway", deepseek_fail=True, recorder=recorder)
    resp = svc.generate_json(
        LLMTaskType.QUERY_EXPANSION, system_prompt="s", user_prompt="u"
    )
    assert resp.json_data == {"ok": True}  # OpenRouter 兜底成功
    assert ds.calls == 1 and or_client.calls == 1
    recs = recorder.all()
    assert len(recs) == 2
    assert recs[0].outcome == "failed"
    assert recs[0].provider_instance_id == "deepseek.chat.primary"
    assert recs[1].outcome == "success"
    assert recs[1].provider_instance_id == "openrouter.free.best_effort"
    assert recs[0].route_execution_id == recs[1].route_execution_id  # 同 fallback chain


def test_gateway_best_effort_max_tokens_rebuilds_openrouter_client():
    """best-effort 任务带 max_tokens 时，OpenRouter adapter 按 payload 重建 client。

    DeepSeek/OpenRouter 的 max_tokens 是构造时固定（generate_json 无 per-call 参数），
    所以 max_tokens 传给 client_factory(max_tokens) 重建 client，而不是传给
    generate_json。验证 factory 收到正确的 max_tokens。
    """
    import asyncio

    from packages.capability_gateway.adapters import (
        CapabilityInvocation,
        _LlmClientAdapter,
    )
    from packages.capability_gateway.schemas import CapabilityType

    factory_calls: list[int] = []

    class _FakeORProbe:
        def generate_json(self, **kwargs):
            return _FakeResp(json_data={"ok": True}, provider="openrouter")

        def generate_text(self, **kwargs):
            return self.generate_json(**kwargs)

    def _fake_or_factory(max_tokens):
        factory_calls.append(max_tokens)
        return _FakeORProbe()

    adapter = _LlmClientAdapter(
        "openrouter.free.best_effort", _FakeORProbe(), client_factory=_fake_or_factory
    )
    invocation = CapabilityInvocation(
        capability=CapabilityType.LLM,
        task_type="query_expansion",
        provider_id="openrouter.free.best_effort",
        payload={
            "system_prompt": "s", "user_prompt": "u", "model": "m",
            "enable_thinking": False, "output": "json", "max_tokens": 800,
        },
    )
    result = asyncio.run(adapter.invoke(invocation))
    assert result.success
    assert factory_calls == [800]  # max_tokens 传给重建 factory


# ── gateway：circuit OPEN 跳过 provider ──────────────────────────────────────

def test_gateway_circuit_open_skips_to_fallback():
    store = InMemoryCircuitStateStore()
    breaker = CircuitBreaker(store, failure_threshold=3)
    for _ in range(3):
        breaker.record_failure("deepseek.chat.primary", ProviderFailureClass.TIMEOUT)
    svc, ds, or_client = _svc("gateway", circuit=breaker)
    resp = svc.generate_json(
        LLMTaskType.QUERY_EXPANSION, system_prompt="s", user_prompt="u"
    )
    assert resp.json_data == {"ok": True}
    assert ds.calls == 0  # circuit OPEN → 无 transport call
    assert or_client.calls == 1


# ── gateway：token usage 透传 ────────────────────────────────────────────────

def test_gateway_records_token_usage():
    recorder = InMemoryProviderAttemptRecorder()
    svc, ds, or_client = _svc("gateway", recorder=recorder)
    svc.generate_json(LLMTaskType.QUERY_EXPANSION, system_prompt="s", user_prompt="u")
    recs = recorder.all()
    assert recs[0].input_tokens == 10
    assert recs[0].output_tokens == 5
