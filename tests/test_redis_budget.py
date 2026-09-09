"""G2.3 RedisLeaseConcurrencyBudget — Redis Sorted Set 并发预算测试。

镜像 test_capability_budget.py（InProcess 版）的断言集，验证 Redis 版语义等价：
硬上限（max inflight）、success/error/cancel release、waiting-cancel 不 invoke、
acquire timeout、per-provider 独立、stale lease recovery（TTL 过期）、
RoutingInvoker 集成、Redis 错误降级。

用 fakeredis（Lua/EVAL 支持需要 lupa，已装）零外部依赖。
"""

from __future__ import annotations

import asyncio
import threading

import fakeredis
import pytest

from packages.capability_gateway import (
    BudgetWaitCancelled,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityRouter,
    CapabilityType,
    ProviderAdapterRegistry,
    ProviderCapacityExhaustedError,
    ProviderConcurrencyPolicy,
    RedisLeaseConcurrencyBudget,
    RoutingInvoker,
    RoutingPolicy,
)
from packages.capability_gateway.schemas import CapabilityInstance, CostPolicy


def _client() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


def _budget(cap: int, *, ttl: float = 60.0, timeout: float = 1.0, client=None):
    client = client or _client()
    return RedisLeaseConcurrencyBudget(client, {
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
        cancelled = asyncio.Event()

        def _should_cancel():
            return cancelled.is_set()

        # 第二个等待中的 acquire：取消后不 invoke
        task_b = asyncio.create_task(invoker.invoke(_plan(), {}, should_cancel=_should_cancel))
        await asyncio.sleep(0.05)
        cancelled.set()
        with pytest.raises(BudgetWaitCancelled):
            await task_b
        assert invoked == ["p"]  # 只 invoke 了第一个
        task_a.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task_a

    asyncio.run(_run())


def test_acquire_timeout_raises_capacity_exhausted():
    async def _run():
        budget = _budget(cap=1, timeout=0.1)
        adapter_reg = ProviderAdapterRegistry()
        started = asyncio.Event()

        class _Block:
            async def invoke(self, invocation):
                started.set()
                await asyncio.Event().wait()

        adapter_reg.register("p", _Block())
        invoker = RoutingInvoker(adapter_reg, budget=budget)
        task_a = asyncio.create_task(invoker.invoke(_plan(), {}))
        await started.wait()
        with pytest.raises(ProviderCapacityExhaustedError):
            await invoker.invoke(_plan(), {})
        task_a.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task_a

    asyncio.run(_run())


# ── per-provider 独立 / stale lease recovery ─────────────────────────────────

def test_per_provider_independent():
    async def _run():
        budget = _budget(cap=1)
        # p 拿满，other 不受影响
        p1 = await budget.acquire(
            provider_instance_id="p", route_execution_id="r", provider_call_id="c1"
        )
        o1 = await budget.acquire(
            provider_instance_id="other", route_execution_id="r", provider_call_id="c2"
        )
        assert budget.active_leases("p") == 1
        assert budget.active_leases("other") == 1
        await budget.release(p1)
        await budget.release(o1)
        assert budget.active_leases("p") == 0
        assert budget.active_leases("other") == 0

    asyncio.run(_run())


def test_stale_lease_recovery():
    """TTL 过期后不 release，capacity 自动恢复（Lua ZREMRANGEBYSCORE 清理）。"""
    async def _run():
        budget = _budget(cap=1, ttl=0.1, timeout=1.0)
        await budget.acquire(
            provider_instance_id="p", route_execution_id="r", provider_call_id="c1"
        )
        assert budget.active_leases("p") == 1
        await asyncio.sleep(0.15)  # 超过 TTL
        # 不 release p1，重 acquire 应成功（过期 lease 被清理）
        p2 = await budget.acquire(
            provider_instance_id="p", route_execution_id="r", provider_call_id="c2"
        )
        assert p2 is not None
        assert budget.active_leases("p") == 1
        await budget.release(p2)

    asyncio.run(_run())


# ── Redis 错误降级 ──────────────────────────────────────────────────────────

class _FailingRedis:
    """Redis 不可用时：acquire fail-closed（capacity_exhausted），release fail-open。"""

    def register_script(self, script):
        class _Script:
            def __call__(self, keys, args):
                raise OSError("connection refused")

        return _Script()

    def zrem(self, *a, **k):
        raise OSError("connection refused")

    def zcount(self, *a, **k):
        raise OSError("connection refused")

    def time(self):
        raise OSError("connection refused")


def test_acquire_fail_closed_on_redis_error():
    async def _run():
        budget = RedisLeaseConcurrencyBudget(_FailingRedis(), {
            "p": ProviderConcurrencyPolicy(provider_instance_id="p", max_concurrency=1),
        })
        with pytest.raises(ProviderCapacityExhaustedError):
            await budget.acquire(
                provider_instance_id="p", route_execution_id="r", provider_call_id="c1"
            )

    asyncio.run(_run())


def test_release_fail_open_on_redis_error():
    async def _run():
        from datetime import UTC, datetime

        from packages.capability_gateway.budget import ProviderPermit

        budget = RedisLeaseConcurrencyBudget(_FailingRedis(), {
            "p": ProviderConcurrencyPolicy(provider_instance_id="p", max_concurrency=1),
        })
        permit = ProviderPermit(
            lease_id="lid", provider_instance_id="p",
            route_execution_id="r", provider_call_id="c",
            acquired_at=datetime.now(UTC), expires_at=datetime.now(UTC),
        )
        await budget.release(permit)  # 不抛（fail-open）
        assert permit.released_at is not None

    asyncio.run(_run())


def test_active_leases_fail_open_on_redis_error():
    budget = RedisLeaseConcurrencyBudget(_FailingRedis(), {
        "p": ProviderConcurrencyPolicy(provider_instance_id="p", max_concurrency=1),
    })
    assert budget.active_leases("p") == 0  # fail-open 返回 0
