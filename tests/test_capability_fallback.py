"""G2.4b Runtime Fallback tests。

验证：FallbackPolicy 决定某类 failure 是否进入下一个 Provider；STRICT 一律不
fallback；capacity 先 bounded wait 再 fallback 判断且不污染 circuit；cancel 不
fallback；fallback 只在 plan.fallback_chain 内；OPEN Provider 不产生 transport。
"""

from __future__ import annotations

import asyncio

from packages.capability_gateway import (
    BudgetWaitCancelled,
    CapabilityResult,
    CapabilityRouter,
    CircuitBreaker,
    FailureClassifier,
    FallbackPolicy,
    InMemoryCircuitStateStore,
    InProcessConcurrencyBudget,
    LLMTaskType,
    ProviderAdapterRegistry,
    ProviderConcurrencyPolicy,
    ProviderFailureClass,
    RoutingInvoker,
    RoutingPolicy,
    default_registry,
    llm_capability_request,
)


class _FakeAdapter:
    def __init__(self, success: bool = True, failure_class: ProviderFailureClass | None = None):
        self._success = success
        self._failure_class = failure_class
        self.calls = 0

    async def invoke(self, invocation):
        self.calls += 1
        return CapabilityResult(
            provider_id=invocation.provider_id,
            success=self._success,
            failure_class=self._failure_class,
        )


def _plan(task_type: LLMTaskType):
    return CapabilityRouter(default_registry()).route(llm_capability_request(task_type))


def _invoker(adapter_reg, *, budget=None, circuit=None, fallback=True):
    return RoutingInvoker(
        adapter_reg,
        budget=budget,
        circuit=circuit,
        classifier=FailureClassifier(),
        fallback_policy=FallbackPolicy() if fallback else None,
    )


# ── best-effort：TIMEOUT → fallback ──────────────────────────────────────────

def test_best_effort_timeout_falls_back():
    deepseek = _FakeAdapter(success=False, failure_class=ProviderFailureClass.TIMEOUT)
    openrouter = _FakeAdapter(success=True)
    adapter_reg = ProviderAdapterRegistry()
    adapter_reg.register("deepseek.chat.primary", deepseek)
    adapter_reg.register("openrouter.free.best_effort", openrouter)
    store = InMemoryCircuitStateStore()
    breaker = CircuitBreaker(store, failure_threshold=3)
    invoker = _invoker(adapter_reg, circuit=breaker)

    result = asyncio.run(invoker.invoke(_plan(LLMTaskType.QUERY_EXPANSION), {}))
    assert result.success is True
    assert result.provider_id == "openrouter.free.best_effort"
    assert deepseek.calls == 1 and openrouter.calls == 1
    # circuit 记录 availability failure
    assert store.get("deepseek.chat.primary").consecutive_failures == 1


# ── strict：TIMEOUT → fail，不 fallback ──────────────────────────────────────

def test_strict_timeout_fails_no_fallback():
    deepseek = _FakeAdapter(success=False, failure_class=ProviderFailureClass.TIMEOUT)
    openrouter = _FakeAdapter(success=True)
    adapter_reg = ProviderAdapterRegistry()
    adapter_reg.register("deepseek.chat.primary", deepseek)
    adapter_reg.register("openrouter.free.best_effort", openrouter)
    invoker = _invoker(adapter_reg)

    # strict plan 的 fallback_chain 为空 → 只试 deepseek
    result = asyncio.run(invoker.invoke(_plan(LLMTaskType.EVIDENCE_EXTRACTION), {}))
    assert result.success is False
    assert result.provider_id == "deepseek.chat.primary"
    assert openrouter.calls == 0  # STRICT 不 fallback（也不在 plan.fallback_chain）


# ── capacity：bounded wait 后 fallback，且不污染 circuit ────────────────────

def test_best_effort_capacity_exhausted_falls_back_without_circuit_penalty():
    deepseek = _FakeAdapter(success=True)  # 不应被调用（budget 满）
    openrouter = _FakeAdapter(success=True)
    adapter_reg = ProviderAdapterRegistry()
    adapter_reg.register("deepseek.chat.primary", deepseek)
    adapter_reg.register("openrouter.free.best_effort", openrouter)

    budget = InProcessConcurrencyBudget({
        "deepseek.chat.primary": ProviderConcurrencyPolicy(
            "deepseek.chat.primary", max_concurrency=1, acquire_timeout_seconds=0.1,
        ),
    })
    store = InMemoryCircuitStateStore()
    breaker = CircuitBreaker(store, failure_threshold=3)

    async def _run():
        # 占住 deepseek permit → query_expansion 的 deepseek acquire 会超时
        permit = await budget.acquire(
            provider_instance_id="deepseek.chat.primary",
            route_execution_id="occupy", provider_call_id="occupy-c",
        )
        invoker = _invoker(adapter_reg, budget=budget, circuit=breaker)
        result = await invoker.invoke(_plan(LLMTaskType.QUERY_EXPANSION), {})
        await budget.release(permit)
        return result

    result = asyncio.run(_run())
    assert result.success is True
    assert result.provider_id == "openrouter.free.best_effort"
    assert deepseek.calls == 0  # 没真正调用 deepseek
    # capacity 不污染 circuit
    assert store.get("deepseek.chat.primary").consecutive_failures == 0
    assert store.get("deepseek.chat.primary").state.value == "closed"


def test_strict_capacity_exhausted_fails():
    deepseek = _FakeAdapter(success=True)
    adapter_reg = ProviderAdapterRegistry()
    adapter_reg.register("deepseek.chat.primary", deepseek)
    budget = InProcessConcurrencyBudget({
        "deepseek.chat.primary": ProviderConcurrencyPolicy(
            "deepseek.chat.primary", max_concurrency=1, acquire_timeout_seconds=0.1,
        ),
    })
    invoker = _invoker(adapter_reg, budget=budget)

    async def _run():
        permit = await budget.acquire(
            provider_instance_id="deepseek.chat.primary",
            route_execution_id="o", provider_call_id="oc",
        )
        result = await invoker.invoke(_plan(LLMTaskType.EVIDENCE_EXTRACTION), {})
        await budget.release(permit)
        return result

    result = asyncio.run(_run())
    assert result.success is False
    assert result.failure_class == ProviderFailureClass.CAPACITY_EXHAUSTED


# ── cancellation：不 fallback ────────────────────────────────────────────────

def test_waiting_cancellation_no_fallback():
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
    invoker = _invoker(adapter_reg, budget=budget)

    async def _run():
        permit = await budget.acquire(
            provider_instance_id="deepseek.chat.primary",
            route_execution_id="occupy", provider_call_id="occupy-c",
        )
        flag = {"c": False}
        task = asyncio.create_task(
            invoker.invoke(
                _plan(LLMTaskType.QUERY_EXPANSION), {},
                should_cancel=lambda: flag["c"],
            )
        )
        await asyncio.sleep(0.05)  # 让 invoker 进入 budget wait
        flag["c"] = True  # 等待中被取消
        try:
            await task
        except BudgetWaitCancelled:
            return "cancelled"
        finally:
            await budget.release(permit)
            if not task.done():
                task.cancel()

    outcome = asyncio.run(_run())
    assert outcome == "cancelled"  # 取消 → 不 fallback
    assert openrouter.calls == 0


# ── circuit OPEN：跳过该 Provider（不产生 transport），继续 fallback ─────────

def test_circuit_open_skips_provider_and_falls_back():
    deepseek = _FakeAdapter(success=True)
    openrouter = _FakeAdapter(success=True)
    adapter_reg = ProviderAdapterRegistry()
    adapter_reg.register("deepseek.chat.primary", deepseek)
    adapter_reg.register("openrouter.free.best_effort", openrouter)
    store = InMemoryCircuitStateStore()
    breaker = CircuitBreaker(store, failure_threshold=3)
    # 先把 deepseek 打到 OPEN
    for _ in range(3):
        breaker.record_failure("deepseek.chat.primary", ProviderFailureClass.TIMEOUT)
    invoker = _invoker(adapter_reg, circuit=breaker)

    result = asyncio.run(invoker.invoke(_plan(LLMTaskType.QUERY_EXPANSION), {}))
    assert result.success is True
    assert result.provider_id == "openrouter.free.best_effort"
    assert deepseek.calls == 0  # OPEN → 无 transport call
    assert openrouter.calls == 1


# ── FallbackPolicy 表 ────────────────────────────────────────────────────────

def test_fallback_policy_table():
    policy = FallbackPolicy()
    eligible = {
        ProviderFailureClass.NETWORK,
        ProviderFailureClass.TIMEOUT,
        ProviderFailureClass.RATE_LIMIT,
        ProviderFailureClass.PROVIDER_5XX,
        ProviderFailureClass.CAPACITY_EXHAUSTED,
    }
    not_eligible = {
        ProviderFailureClass.AUTH,
        ProviderFailureClass.QUOTA,
        ProviderFailureClass.OUTPUT_INVALID,
        ProviderFailureClass.BUSINESS_VALIDATION,
        ProviderFailureClass.CANCELLED,
    }
    for fc in eligible:
        assert policy.should_fallback(
            routing_policy=RoutingPolicy.FALLBACK_ALLOWED, failure_class=fc
        ) is True
        assert policy.should_fallback(
            routing_policy=RoutingPolicy.STRICT, failure_class=fc
        ) is False
    for fc in not_eligible:
        assert policy.should_fallback(
            routing_policy=RoutingPolicy.FALLBACK_ALLOWED, failure_class=fc
        ) is False
        assert policy.should_fallback(
            routing_policy=RoutingPolicy.STRICT, failure_class=fc
        ) is False
    assert policy.should_fallback(
        routing_policy=RoutingPolicy.FALLBACK_ALLOWED, failure_class=None
    ) is False
