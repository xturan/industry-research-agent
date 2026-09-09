"""G4 Provider-Plane Load Acceptance（deterministic fake provider + 真实 PG）。

在 G2 各单项验收之上，把 RoutingInvoker 的完整编排（circuit → budget → adapter
→ classifier → circuit feedback → fallback → telemetry）放上并发负载：

  P1 budget_under_load        primary max_concurrency=5，50 并发 invoke
                              → max_observed<=5、overshoot=0、全 success、permit 无泄漏
  P2 circuit_open_recover     primary 连续 NETWORK 失败 → 3 次后 OPEN → 拒绝期
                              circuit_rejected（不 transport）→ cooldown 后
                              HALF_OPEN probe 成功 → CLOSED
  P3 fallback_under_concurrency  primary 失败、fallback success，30 并发
                              → 全 success 走 fallback，telemetry 记录正确
  P4 non_availability_no_circuit  primary 返回 BUSINESS_VALIDATION ×5
                              → 不 fallback、不污染 circuit（保持 CLOSED）
  P5 leak                     permit 无活动、pool.checkedout==0

用法：
  GATEWAY_TEST_DATABASE_URL=postgresql+psycopg://... \
    python scripts/gateway_provider_load_acceptance.py
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from packages.capability_gateway.adapters import (
    CapabilityResult,
    ProviderAdapterRegistry,
    RoutingInvoker,
)
from packages.capability_gateway.budget import (
    PostgresLeaseConcurrencyBudget,
    ProviderConcurrencyPolicy,
    create_concurrency_tables,
)
from packages.capability_gateway.circuit import (
    CircuitBreaker,
    CircuitState,
    FailureClassifier,
    PostgresCircuitStateStore,
    create_circuit_tables,
)
from packages.capability_gateway.fallback import FallbackPolicy
from packages.capability_gateway.plan import RoutingPlan, RoutingTrace
from packages.capability_gateway.schemas import (
    CapabilityRequest,
    CapabilityType,
    CostPolicy,
    RoutingPolicy,
)
from packages.capability_gateway.telemetry import (
    PostgresProviderAttemptRecorder,
    create_attempt_tables,
)
from packages.providers.base import ProviderRetryableError

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone.utc

OUT_DIR = _REPO / "data" / "tmp" / "gateway_provider_load_acceptance"
PRIMARY = "load.primary"
FALLBACK = "load.fallback"
BUDGET_CAP = int(os.environ.get("G4P_BUDGET_CAP", "5"))
P1_CONCURRENCY = int(os.environ.get("G4P_P1_CONCURRENCY", "50"))
P3_CONCURRENCY = int(os.environ.get("G4P_P3_CONCURRENCY", "30"))


def _pct(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    return round(float(statistics.quantiles(values, n=100, method="inclusive")[p - 1]), 3)


def _latency(times: list[float]) -> dict[str, float]:
    return {
        "count": len(times),
        "p50_ms": round(statistics.median(times) * 1000, 2),
        "p95_ms": round(_pct(times, 95) * 1000, 2),
        "p99_ms": round(_pct(times, 99) * 1000, 2),
        "max_ms": round(max(times) * 1000, 2),
    }


class _FakeAdapter:
    """Deterministic fake provider。state 是共享 dict，mode 控制行为。"""

    def __init__(self, instance_id: str, state: dict[str, Any]) -> None:
        self._instance_id = instance_id
        self._state = state

    async def invoke(self, invocation: Any) -> CapabilityResult:
        mode = self._state["mode"]
        delay = float(self._state.get("delay", 0.0))
        if delay:
            await asyncio.sleep(delay)
        if mode == "success":
            return CapabilityResult(provider_id=self._instance_id, success=True, data={"ok": True})
        if mode == "fail_network":
            raise ProviderRetryableError("fake provider down")
        if mode == "fail_business":
            from packages.capability_gateway.circuit import ProviderFailureClass

            return CapabilityResult(
                provider_id=self._instance_id, success=False, error="bad output",
                failure_class=ProviderFailureClass.BUSINESS_VALIDATION,
            )
        raise AssertionError(f"unknown fake mode {mode}")


def _make_plan() -> RoutingPlan:
    req = CapabilityRequest(
        capability=CapabilityType.LLM,
        task_type="query_expansion",
        routing_policy=RoutingPolicy.FALLBACK_ALLOWED,
        cost_policy=CostPolicy.PREFER_LOW_COST,
    )
    return RoutingPlan(
        capability=req.capability, task_type=req.task_type, policy=req.routing_policy,
        primary=PRIMARY, fallback_chain=[FALLBACK],
        eligible=[PRIMARY, FALLBACK], filtered={},
        route_reason=["g4_provider_load"], trace=RoutingTrace(request=req),
    )


def _reset(sf) -> None:
    with sf() as s:
        s.execute(text("DELETE FROM provider_attempt_records"))
        s.execute(text("DELETE FROM provider_circuit_state"))
        s.execute(text("DELETE FROM provider_concurrency_leases"))
        s.commit()


def _active_permits(sf) -> int:
    with sf() as s:
        return int(s.execute(text(
            "SELECT COUNT(*) FROM provider_concurrency_leases "
            "WHERE released_at IS NULL AND expires_at >= now()"
        )).scalar() or 0)


def _attempt_rows(sf, *, primary: str = PRIMARY, fallback: str = FALLBACK) -> list[dict]:
    with sf() as s:
        rows = s.execute(text(
            "SELECT provider_instance_id, outcome, failure_class, fallback_used "
            "FROM provider_attempt_records"
        )).mappings().all()
    return [dict(r) for r in rows]


async def _invoke_n(invoker, plan, n: int, *, concurrency: int) -> tuple[list[dict], list[float]]:
    async def _one(i: int) -> dict:
        t0 = time.perf_counter()
        res = await invoker.invoke(plan, {"i": i})
        return {"i": i, "t": time.perf_counter() - t0, "success": res.success, "err": res.error}

    results: list[dict] = []
    times: list[float] = []
    for start in range(0, n, concurrency):
        batch = await asyncio.gather(*[_one(i) for i in range(start, min(start + concurrency, n))])
        results.extend(batch)
        times.extend(b["t"] for b in batch)
    return results, times


# ── P1 budget under load ─────────────────────────────────────────────────────

async def p1_budget(sf, invoker, budget, plan, *, concurrency: int) -> dict:
    _reset(sf)
    primary_state = invoker._registry.get(PRIMARY)._state  # noqa: SLF001
    primary_state["mode"] = "success"
    primary_state["delay"] = 0.05

    stop = {"stop": False}
    max_observed = {"v": 0}

    def _observer() -> None:
        while not stop["stop"]:
            v = budget.active_leases(PRIMARY)
            if v > max_observed["v"]:
                max_observed["v"] = v
            time.sleep(0.002)

    obs = threading.Thread(target=_observer, daemon=True)
    obs.start()
    t_wall0 = time.perf_counter()
    results, times = await _invoke_n(invoker, plan, concurrency, concurrency=concurrency)
    t_wall = time.perf_counter() - t_wall0
    stop["stop"] = True
    obs.join(timeout=5)

    active_after = _active_permits(sf)
    ok = (
        all(r["success"] for r in results)
        and max_observed["v"] <= BUDGET_CAP
        and active_after == 0
    )
    return {
        "PASS": ok,
        "concurrency": concurrency, "cap": BUDGET_CAP,
        "success": sum(1 for r in results if r["success"]),
        "max_observed_active_permits": max_observed["v"],
        "overshoot": max_observed["v"] - BUDGET_CAP,
        "active_permits_after": active_after,
        "wall_seconds": round(t_wall, 3),
        "throughput_invokes_s": round(concurrency / max(t_wall, 1e-9), 2),
        "invoke_latency": _latency(times),
    }


# ── P2 circuit open / recover ────────────────────────────────────────────────

async def p2_circuit(sf, invoker, circuit, plan) -> dict:
    _reset(sf)
    primary_state = invoker._registry.get(PRIMARY)._state  # noqa: SLF001
    primary_state["mode"] = "fail_network"
    primary_state["delay"] = 0.0

    # 5 次失败：前 3 次 transport（累计到 OPEN），后 2 次 circuit_rejected
    results, _ = await _invoke_n(invoker, plan, 5, concurrency=1)
    rec = circuit._store.get(PRIMARY)  # noqa: SLF001
    opened = rec.state == CircuitState.OPEN and not circuit.allow(PRIMARY)

    # 拒绝期：3 次调用，primary 全部 circuit_rejected（不 transport），fallback 成功
    results2, _ = await _invoke_n(invoker, plan, 3, concurrency=1)
    attempts = _attempt_rows(sf)
    rejected_count = sum(
        1 for a in attempts
        if a["provider_instance_id"] == PRIMARY and a["outcome"] == "circuit_rejected"
    )

    # cooldown 后 probe 成功 → CLOSED
    primary_state["mode"] = "success"
    await asyncio.sleep(2.1)  # cooldown_seconds=2.0
    res_probe = await invoker.invoke(plan, {"probe": 1})
    rec_after = circuit._store.get(PRIMARY)  # noqa: SLF001
    closed = (
        rec_after.state == CircuitState.CLOSED
        and circuit.allow(PRIMARY)
        and res_probe.success
        and res_probe.provider_id == PRIMARY  # probe 走 primary（非 fallback）
    )
    ok = opened and rejected_count >= 3 and closed
    return {
        "PASS": ok,
        "opened_after_3_failures": bool(opened),
        "circuit_rejected_during_open": rejected_count,
        "probe_succeeded_via_primary": bool(res_probe.success and res_probe.provider_id == PRIMARY),
        "recovered_to_closed": bool(closed),
    }


# ── P3 fallback chain under concurrency ──────────────────────────────────────

async def p3_fallback(sf, invoker, plan, *, concurrency: int) -> dict:
    _reset(sf)
    primary_state = invoker._registry.get(PRIMARY)._state  # noqa: SLF001
    primary_state["mode"] = "fail_network"
    primary_state["delay"] = 0.01

    results, times = await _invoke_n(invoker, plan, concurrency, concurrency=concurrency)
    attempts = _attempt_rows(sf)
    fallback_success = sum(
        1 for a in attempts
        if a["provider_instance_id"] == FALLBACK and a["outcome"] == "success"
    )
    fallback_used = sum(
        1 for a in attempts if a["fallback_used"] and a["outcome"] == "success"
    )
    primary_attempted = sum(
        1 for a in attempts
        if a["provider_instance_id"] == PRIMARY and a["outcome"] in ("failed", "circuit_rejected")
    )
    ok = (
        all(r["success"] for r in results)
        and fallback_success == concurrency
        and fallback_used == concurrency
        and primary_attempted == concurrency
    )
    return {
        "PASS": ok,
        "concurrency": concurrency,
        "all_success": all(r["success"] for r in results),
        "fallback_success_records": fallback_success,
        "fallback_used_records": fallback_used,
        "primary_failed_or_rejected_records": primary_attempted,
        "wall_seconds": round(sum(r["t"] for r in results) / max(concurrency, 1), 3),
        "invoke_latency": _latency(times),
    }


# ── P4 non-availability doesn't trip circuit ────────────────────────────────

async def p4_non_availability(sf, invoker, circuit, plan) -> dict:
    _reset(sf)
    primary_state = invoker._registry.get(PRIMARY)._state  # noqa: SLF001
    primary_state["mode"] = "fail_business"
    primary_state["delay"] = 0.0

    results, _ = await _invoke_n(invoker, plan, 5, concurrency=1)
    rec = circuit._store.get(PRIMARY)  # noqa: SLF001
    ok = (
        all(not r["success"] for r in results)
        and rec.state == CircuitState.CLOSED
        and circuit.allow(PRIMARY)
    )
    return {
        "PASS": ok,
        "failed_as_business_validation": sum(1 for r in results if not r["success"]),
        "circuit_state": rec.state.value,
        "circuit_allow": circuit.allow(PRIMARY),
    }


def p5_leak(sf, engine) -> dict:
    active = _active_permits(sf)
    checkedout = engine.pool.checkedout()
    return {
        "PASS": active == 0 and checkedout == 0,
        "active_permits": active,
        "pool_checkedout": checkedout,
    }


async def main() -> int:
    url = os.environ.get("GATEWAY_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url or "postgres" not in url:
        print("GATEWAY_TEST_DATABASE_URL (or DATABASE_URL) must point to PostgreSQL.")
        return 2
    engine = create_engine(url, pool_pre_ping=True, pool_size=60, max_overflow=0, pool_timeout=60)
    create_concurrency_tables(engine)
    create_circuit_tables(engine)
    create_attempt_tables(engine)
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    # ── wiring：deterministic fake provider + real PG budget/circuit/telemetry ──
    primary_state = {"mode": "success", "delay": 0.0}
    fallback_state = {"mode": "success", "delay": 0.0}
    registry = ProviderAdapterRegistry()
    registry.register(PRIMARY, _FakeAdapter(PRIMARY, primary_state))
    registry.register(FALLBACK, _FakeAdapter(FALLBACK, fallback_state))

    policies = {
        PRIMARY: ProviderConcurrencyPolicy(
            provider_instance_id=PRIMARY, max_concurrency=BUDGET_CAP,
            acquire_timeout_seconds=15.0, lease_ttl_seconds=60.0,
        ),
        FALLBACK: ProviderConcurrencyPolicy(
            provider_instance_id=FALLBACK, max_concurrency=200,
            acquire_timeout_seconds=5.0, lease_ttl_seconds=60.0,
        ),
    }
    budget = PostgresLeaseConcurrencyBudget(sf, policies, poll_interval_seconds=0.02)
    circuit = CircuitBreaker(
        PostgresCircuitStateStore(sf), failure_threshold=3, cooldown_seconds=2.0
    )
    recorder = PostgresProviderAttemptRecorder(sf)
    invoker = RoutingInvoker(
        registry, budget=budget, circuit=circuit, classifier=FailureClassifier(),
        fallback_policy=FallbackPolicy(), recorder=recorder,
    )
    plan = _make_plan()

    _reset(sf)
    blocks: dict[str, Any] = {}
    blocks["budget_under_load"] = await p1_budget(
        sf, invoker, budget, plan, concurrency=P1_CONCURRENCY
    )
    print("P1 budget_under_load:", blocks["budget_under_load"]["PASS"],
          f"overshoot={blocks['budget_under_load']['overshoot']} "
          f"tps={blocks['budget_under_load']['throughput_invokes_s']}")

    blocks["circuit_open_recover"] = await p2_circuit(sf, invoker, circuit, plan)
    print("P2 circuit_open_recover:", blocks["circuit_open_recover"]["PASS"],
          f"rejected={blocks['circuit_open_recover']['circuit_rejected_during_open']} "
          f"closed={blocks['circuit_open_recover']['recovered_to_closed']}")

    blocks["fallback_under_concurrency"] = await p3_fallback(
        sf, invoker, plan, concurrency=P3_CONCURRENCY
    )
    print("P3 fallback_under_concurrency:", blocks["fallback_under_concurrency"]["PASS"],
          f"fallback_used={blocks['fallback_under_concurrency']['fallback_used_records']}")

    blocks["non_availability_no_circuit"] = await p4_non_availability(sf, invoker, circuit, plan)
    print("P4 non_availability_no_circuit:", blocks["non_availability_no_circuit"]["PASS"],
          f"circuit={blocks['non_availability_no_circuit']['circuit_state']}")

    blocks["leak_check"] = p5_leak(sf, engine)
    print("P5 leak:", blocks["leak_check"]["PASS"])

    all_pass = all(b["PASS"] for b in blocks.values())
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "g4_provider_plane_load": blocks,
        "status": "PASS" if all_pass else "FAIL",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "provider_load_acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nG4 Provider-plane Load {'PASS' if all_pass else 'FAIL'} -> {OUT_DIR}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
