"""G2.5a Provider Attempt Telemetry tests。

验证：每次 Provider attempt 独立记录（append-only）、fallback chain 同
route_execution_id 不同 provider_call_id、circuit/capacity 记 attempt 但
transport_invoked=false、cancel 记 cancelled、recorder fail-open、不记 raw prompt/
API key/source。
"""

from __future__ import annotations

import asyncio
from datetime import UTC

from packages.capability_gateway import (
    BudgetWaitCancelled,
    CapabilityResult,
    CapabilityRouter,
    CircuitBreaker,
    FailureClassifier,
    FallbackPolicy,
    InMemoryCircuitStateStore,
    InMemoryProviderAttemptRecorder,
    InProcessConcurrencyBudget,
    LLMTaskType,
    ProviderAdapterRegistry,
    ProviderConcurrencyPolicy,
    ProviderFailureClass,
    RoutingInvoker,
    default_registry,
    llm_capability_request,
)


class _FakeAdapter:
    def __init__(self, success: bool = True, failure_class: ProviderFailureClass | None = None,
                 input_tokens: int | None = None, output_tokens: int | None = None):
        self._success = success
        self._failure_class = failure_class
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self.calls = 0

    async def invoke(self, invocation):
        self.calls += 1
        return CapabilityResult(
            provider_id=invocation.provider_id,
            success=self._success,
            failure_class=self._failure_class,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
        )


def _plan(task_type: LLMTaskType):
    return CapabilityRouter(default_registry()).route(llm_capability_request(task_type))


def _invoker(adapter_reg, *, budget=None, circuit=None, recorder=None, fallback=True):
    return RoutingInvoker(
        adapter_reg,
        budget=budget,
        circuit=circuit,
        classifier=FailureClassifier(),
        fallback_policy=FallbackPolicy() if fallback else None,
        recorder=recorder,
    )


# ── 1. primary success → 1 record ───────────────────────────────────────────

def test_primary_success_records_one_attempt():
    deepseek = _FakeAdapter(success=True, input_tokens=100, output_tokens=20)
    adapter_reg = ProviderAdapterRegistry()
    adapter_reg.register("deepseek.chat.primary", deepseek)
    recorder = InMemoryProviderAttemptRecorder()
    invoker = _invoker(adapter_reg, recorder=recorder)

    result = asyncio.run(invoker.invoke(_plan(LLMTaskType.QUERY_EXPANSION), {}))
    assert result.success is True
    recs = recorder.all()
    assert len(recs) == 1
    assert recs[0].outcome == "success"
    assert recs[0].transport_invoked is True
    assert recs[0].input_tokens == 100
    assert recs[0].output_tokens == 20
    assert recs[0].latency_ms is not None and recs[0].latency_ms >= 0
    assert recs[0].fallback_used is False


# ── 2. fallback chain → 2 records，同 route，不同 provider_call_id ──────────

def test_fallback_chain_records_two_attempts_shared_route():
    deepseek = _FakeAdapter(success=False, failure_class=ProviderFailureClass.TIMEOUT)
    openrouter = _FakeAdapter(success=True)
    adapter_reg = ProviderAdapterRegistry()
    adapter_reg.register("deepseek.chat.primary", deepseek)
    adapter_reg.register("openrouter.free.best_effort", openrouter)
    recorder = InMemoryProviderAttemptRecorder()
    invoker = _invoker(adapter_reg, recorder=recorder)

    result = asyncio.run(invoker.invoke(_plan(LLMTaskType.QUERY_EXPANSION), {}))
    assert result.provider_id == "openrouter.free.best_effort"
    recs = recorder.all()
    assert len(recs) == 2
    assert recs[0].outcome == "failed"
    assert recs[0].failure_class == "timeout"
    assert recs[0].transport_invoked is True
    assert recs[1].outcome == "success"
    assert recs[1].fallback_used is True
    # fallback chain：同 route_execution_id，不同 provider_call_id
    assert recs[0].route_execution_id == recs[1].route_execution_id
    assert recs[0].provider_call_id != recs[1].provider_call_id
    assert recs[0].attempt_index == 0 and recs[1].attempt_index == 1


# ── 3. circuit open → transport_invoked=false ────────────────────────────────

def test_circuit_rejected_records_transport_false():
    deepseek = _FakeAdapter(success=True)
    openrouter = _FakeAdapter(success=True)
    adapter_reg = ProviderAdapterRegistry()
    adapter_reg.register("deepseek.chat.primary", deepseek)
    adapter_reg.register("openrouter.free.best_effort", openrouter)
    store = InMemoryCircuitStateStore()
    breaker = CircuitBreaker(store, failure_threshold=3)
    for _ in range(3):
        breaker.record_failure("deepseek.chat.primary", ProviderFailureClass.TIMEOUT)
    recorder = InMemoryProviderAttemptRecorder()
    invoker = _invoker(adapter_reg, circuit=breaker, recorder=recorder)

    result = asyncio.run(invoker.invoke(_plan(LLMTaskType.QUERY_EXPANSION), {}))
    assert result.provider_id == "openrouter.free.best_effort"
    assert deepseek.calls == 0
    recs = recorder.all()
    assert any(r.outcome == "circuit_rejected" and r.transport_invoked is False for r in recs)


# ── 4. capacity exhausted → transport_invoked=false ──────────────────────────

def test_capacity_exhausted_records_transport_false():
    deepseek = _FakeAdapter(success=True)
    openrouter = _FakeAdapter(success=True)
    adapter_reg = ProviderAdapterRegistry()
    adapter_reg.register("deepseek.chat.primary", deepseek)
    adapter_reg.register("openrouter.free.best_effort", openrouter)
    budget = InProcessConcurrencyBudget({
        "deepseek.chat.primary": ProviderConcurrencyPolicy(
            "deepseek.chat.primary", max_concurrency=1, acquire_timeout_seconds=0.1,
        ),
    })
    recorder = InMemoryProviderAttemptRecorder()
    invoker = _invoker(adapter_reg, budget=budget, recorder=recorder)

    async def _run():
        permit = await budget.acquire(
            provider_instance_id="deepseek.chat.primary",
            route_execution_id="occupy", provider_call_id="occupy-c",
        )
        result = await invoker.invoke(_plan(LLMTaskType.QUERY_EXPANSION), {})
        await budget.release(permit)
        return result

    result = asyncio.run(_run())
    assert result.provider_id == "openrouter.free.best_effort"
    assert deepseek.calls == 0
    recs = recorder.all()
    assert any(
        r.outcome == "capacity_exhausted" and r.transport_invoked is False
        for r in recs
    )


# ── 5. strict failure → 1 record，无 fallback ────────────────────────────────

def test_strict_failure_single_record_no_fallback():
    deepseek = _FakeAdapter(success=False, failure_class=ProviderFailureClass.TIMEOUT)
    openrouter = _FakeAdapter(success=True)
    adapter_reg = ProviderAdapterRegistry()
    adapter_reg.register("deepseek.chat.primary", deepseek)
    adapter_reg.register("openrouter.free.best_effort", openrouter)
    recorder = InMemoryProviderAttemptRecorder()
    invoker = _invoker(adapter_reg, recorder=recorder)

    result = asyncio.run(invoker.invoke(_plan(LLMTaskType.EVIDENCE_EXTRACTION), {}))
    assert result.success is False
    assert openrouter.calls == 0
    assert len(recorder.all()) == 1


# ── 6. cancel → outcome cancelled，无 fallback ───────────────────────────────

def test_cancel_records_cancelled_no_fallback():
    deepseek = _FakeAdapter(success=True)
    openrouter = _FakeAdapter(success=True)
    adapter_reg = ProviderAdapterRegistry()
    adapter_reg.register("deepseek.chat.primary", deepseek)
    adapter_reg.register("openrouter.free.best_effort", openrouter)
    budget = InProcessConcurrencyBudget({
        "deepseek.chat.primary": ProviderConcurrencyPolicy(
            "deepseek.chat.primary", max_concurrency=1, acquire_timeout_seconds=5.0,
        ),
    })
    recorder = InMemoryProviderAttemptRecorder()
    invoker = _invoker(adapter_reg, budget=budget, recorder=recorder)

    async def _run():
        permit = await budget.acquire(
            provider_instance_id="deepseek.chat.primary",
            route_execution_id="o", provider_call_id="oc",
        )
        flag = {"c": False}
        task = asyncio.create_task(
            invoker.invoke(_plan(LLMTaskType.QUERY_EXPANSION), {},
                           should_cancel=lambda: flag["c"])
        )
        await asyncio.sleep(0.05)
        flag["c"] = True
        try:
            await task
        except BudgetWaitCancelled:
            pass
        finally:
            await budget.release(permit)
            if not task.done():
                task.cancel()

    asyncio.run(_run())
    assert openrouter.calls == 0
    assert any(r.outcome == "cancelled" and r.transport_invoked is False for r in recorder.all())


# ── 7. recorder failure → Provider 结果不受影响（fail-open） ────────────────

def test_recorder_failure_does_not_break_business():
    deepseek = _FakeAdapter(success=True)
    adapter_reg = ProviderAdapterRegistry()
    adapter_reg.register("deepseek.chat.primary", deepseek)

    class _RaisesRecorder:
        def record(self, attempt):
            raise RuntimeError("recorder boom")

    invoker = _invoker(adapter_reg, recorder=_RaisesRecorder())
    result = asyncio.run(invoker.invoke(_plan(LLMTaskType.QUERY_EXPANSION), {}))
    assert result.success is True  # telemetry 失败不影响业务


# ── 8. 安全：不记 raw prompt / api key / source ──────────────────────────────

def test_record_never_contains_raw_secrets():
    from datetime import datetime

    from packages.capability_gateway.telemetry import ProviderAttemptRecord

    rec = ProviderAttemptRecord(
        provider_call_id="c1", route_execution_id="r1",
        provider_instance_id="deepseek.chat.primary",
        outcome="success", transport_invoked=True,
        started_at=datetime.now(UTC),
    )
    d = rec.to_dict()
    forbidden = {"prompt", "response", "api_key", "source", "messages", "raw"}
    assert forbidden.isdisjoint(set(d.keys()))
    # dataclass 也没有这些字段
    for name in forbidden:
        assert not hasattr(rec, name)
