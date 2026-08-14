"""G2.3a InProcessConcurrencyBudget — 单进程预算语义测试。

覆盖：硬上限（max inflight）、success/error/cancel release、waiting-cancel
不 invoke、acquire timeout、per-provider 独立、stale lease recovery、
permit 绑定 provider_call_id、RoutingInvoker 集成 acquire/release。

G2.3a 是单进程语义验证（InProcess），不是多进程生产保证（Postgres 版见 G2.3b）。
"""

from __future__ import annotations

import asyncio
import threading

import pytest

from packages.capability_gateway import (
    BudgetWaitCancelled,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityRouter,
    CapabilityType,
    InProcessConcurrencyBudget,
    ProviderAdapterRegistry,
    ProviderCapacityExhaustedError,
    ProviderConcurrencyPolicy,
    RoutingInvoker,
    RoutingPolicy,
)
from packages.capability_gateway.schemas import CapabilityInstance, CostPolicy

# ── helpers ──────────────────────────────────────────────────────────────────

def _budget(cap: int, *, ttl: float = 60.0, timeout: float = 1.0) -> InProcessConcurrencyBudget:
    return InProcessConcurrencyBudget({
        "p": ProviderConcurrencyPolicy(
            provider_instance_id="p", max_concurrency=cap,
            acquire_timeout_seconds=timeout, lease_ttl_seconds=ttl,
        ),
        "other": ProviderConcurrencyPolicy(
            provider_instance_id="other", max_concurrency=1,
            acquire_timeout_seconds=timeout, lease_ttl_seconds=ttl,
        ),
    })


def _plan():
    reg = CapabilityRegistry()
    reg.register(CapabilityInstance(
        instance_id="p", capability=CapabilityType.SEARCH, provider="fake",
        roles=["primary"], features={"max_results": 5},
    ))
    request = CapabilityRequest(
        capability=CapabilityType.SEARCH, task_type="research_discovery",
        requirements={"max_results": 5}, routing_policy=RoutingPolicy.FALLBACK_ALLOWED,
        cost_policy=CostPolicy.PREFER_LOW_COST,
    )
    return CapabilityRouter(reg).route(request)


def _inflight_adapter(counter: dict, delay: float = 0.05):
    lock = threading.Lock()

    class _A:
        async def invoke(self, invocation):
            from packages.capability_gateway import CapabilityResult

            with lock:
                counter["inflight"] += 1
                counter["max"] = max(counter["max"], counter["inflight"])
            await asyncio.sleep(delay)
            with lock:
                counter["inflight"] -= 1
            return CapabilityResult(provider_id=invocation.provider_id, success=True)

    return _A()


# ── 硬上限 / release ────────────────────────────────────────────────────────

def test_max_inflight_hard_cap():
    async def _run():
        budget = _budget(cap=2)
        counter = {"inflight": 0, "max": 0}
        adapter_reg = ProviderAdapterRegistry()
        adapter_reg.register("p", _inflight_adapter(counter, delay=0.05))
        invoker = RoutingInvoker(adapter_reg, budget=budget)
        plan = _plan()
        await asyncio.gather(*[invoker.invoke(plan, {}) for _ in range(10)])
        return counter["max"], budget.active_leases("p")

    max_obs, active = asyncio.run(_run())
    assert max_obs == 2  # inflight 永不超限
    assert active == 0  # 全部 release


def test_success_release():
    async def _run():
        budget = _budget(cap=1)
        adapter_reg = ProviderAdapterRegistry()
        adapter_reg.register("p", _inflight_adapter({"inflight": 0, "max": 0}))
        invoker = RoutingInvoker(adapter_reg, budget=budget)
        await invoker.invoke(_plan(), {})
        return budget.active_leases("p")

    assert asyncio.run(_run()) == 0  # success → release


def test_exception_release():
    async def _run():
        budget = _budget(cap=1)
        adapter_reg = ProviderAdapterRegistry()

        class _Raise:
            async def invoke(self, invocation):
                raise RuntimeError("boom")

        adapter_reg.register("p", _Raise())
        invoker = RoutingInvoker(adapter_reg, budget=budget)
        with pytest.raises(RuntimeError):
            await invoker.invoke(_plan(), {})
        return budget.active_leases("p")

    assert asyncio.run(_run()) == 0  # 异常 → finally release


def test_cancellation_release():
    async def _run():
        budget = _budget(cap=1)
        adapter_reg = ProviderAdapterRegistry()
        started = asyncio.Event()

        class _Block:
            async def invoke(self, invocation):
                started.set()
                await asyncio.Event().wait()

        adapter_reg.register("p", _Block())
        invoker = RoutingInvoker(adapter_reg, budget=budget)
        task = asyncio.create_task(invoker.invoke(_plan(), {}))
        await started.wait()
        assert budget.active_leases("p") == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return budget.active_leases("p")

    assert asyncio.run(_run()) == 0  # 取消 → finally release


# ── waiting cancellation / timeout ───────────────────────────────────────────

def test_waiting_cancellation_does_not_invoke():
    async def _run():
        budget = _budget(cap=1)
        adapter_reg = ProviderAdapterRegistry()
        invoked: list[str] = []

        class _A:
            async def invoke(self, invocation):
                invoked.append(invocation.provider_id)
                await asyncio.Event().wait()

        adapter_reg.register("p", _A())
        invoker = RoutingInvoker(adapter_reg, budget=budget)
        task_a = asyncio.create_task(invoker.invoke(_plan(), {}))
        await asyncio.sleep(0.05)
        assert budget.active_leases("p") == 1

        cancel_flag = {"cancelled": False}
        task_b = asyncio.create_task(
            invoker.invoke(_plan(), {}, should_cancel=lambda: cancel_flag["cancelled"])
        )
        await asyncio.sleep(0.05)
        cancel_flag["cancelled"] = True  # B 等待中被取消
        with pytest.raises(BudgetWaitCancelled):
            await task_b
        b_invoked = list(invoked)
        active_while_b = budget.active_leases("p")

        task_a.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task_a
        return b_invoked, active_while_b, budget.active_leases("p")

    invoked, active_while_b, active_after = asyncio.run(_run())
    assert invoked == ["p"]  # B 没有 invoke provider
    assert active_while_b == 1  # 只有 A 的 lease，无泄漏
    assert active_after == 0


def test_acquire_timeout_raises_capacity_exhausted():
    async def _run():
        budget = _budget(cap=1, timeout=0.2)
        permit = await budget.acquire(
            provider_instance_id="p", route_execution_id="r1", provider_call_id="c1"
        )
        with pytest.raises(ProviderCapacityExhaustedError):
            await budget.acquire(
                provider_instance_id="p", route_execution_id="r2", provider_call_id="c2"
            )
        await budget.release(permit)
        return budget.active_leases("p")

    assert asyncio.run(_run()) == 0


# ── per-provider 独立 / stale lease ──────────────────────────────────────────

def test_per_provider_independence():
    async def _run():
        budget = _budget(cap=1)
        await budget.acquire(
            provider_instance_id="p", route_execution_id="r1", provider_call_id="c1"
        )
        permit2 = await budget.acquire(
            provider_instance_id="other", route_execution_id="r2", provider_call_id="c2"
        )
        return (permit2.provider_instance_id, budget.active_leases("p"),
                budget.active_leases("other"))

    pid, active_p, active_other = asyncio.run(_run())
    assert pid == "other"
    assert active_p == 1
    assert active_other == 1  # 互不阻塞


def test_stale_lease_recovery():
    async def _run():
        budget = InProcessConcurrencyBudget({
            "p": ProviderConcurrencyPolicy(
                provider_instance_id="p", max_concurrency=1,
                acquire_timeout_seconds=1.0, lease_ttl_seconds=0.1,
            ),
        })
        permit = await budget.acquire(
            provider_instance_id="p", route_execution_id="r1", provider_call_id="c1"
        )
        await asyncio.sleep(0.15)  # 不 release，TTL 过期
        permit2 = await budget.acquire(
            provider_instance_id="p", route_execution_id="r2", provider_call_id="c2"
        )
        return permit.lease_id, permit2.lease_id, budget.active_leases("p")

    lease1, lease2, active = asyncio.run(_run())
    assert lease1 != lease2  # 新 lease
    assert active == 1  # 过期 lease 被清理，容量恢复


# ── permit 身份 / invoker 集成 ───────────────────────────────────────────────

def test_permit_binds_provider_call_id():
    async def _run():
        budget = _budget(cap=1)
        permit = await budget.acquire(
            provider_instance_id="p", route_execution_id="route-1", provider_call_id="call-1"
        )
        active = permit.is_active
        await budget.release(permit)
        return (permit.provider_call_id, permit.route_execution_id, active,
                permit.released_at is not None, permit.is_active)

    call_id, route_id, active_before, released, active_after = asyncio.run(_run())
    assert call_id == "call-1"
    assert route_id == "route-1"
    assert active_before is True
    assert released is True
    assert active_after is False


def test_invoker_sets_provider_call_id():
    async def _run():
        budget = _budget(cap=1)
        adapter_reg = ProviderAdapterRegistry()
        captured: dict[str, str] = {}

        class _A:
            async def invoke(self, invocation):
                captured["provider_call_id"] = invocation.provider_call_id
                from packages.capability_gateway import CapabilityResult
                return CapabilityResult(provider_id=invocation.provider_id, success=True)

        adapter_reg.register("p", _A())
        invoker = RoutingInvoker(adapter_reg, budget=budget)
        result = await invoker.invoke(_plan(), {})
        return result.route_execution_id, result.provider_call_id, captured["provider_call_id"]

    route_id, call_id, captured = asyncio.run(_run())
    assert route_id is not None
    assert call_id is not None
    assert captured == call_id  # permit 绑定同一 provider_call_id
