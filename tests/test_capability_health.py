"""G2.5b Health Snapshot + G2.5c Health-aware Routing Shadow tests。

验证：availability / quality / capacity 三个失败维度分离（不做综合分）；
p50/p95 聚合；可解释 dimensions；health-aware hypothetical plan（只算不改）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from packages.capability_gateway import (
    CapabilityRegistry,
    CapabilityRouter,
    CapabilityType,
    ProviderFailureClass,
    build_health_aware_providers,
    build_health_snapshot,
    compare_health_routing,
    llm_capability_request,
)
from packages.capability_gateway.schemas import CapabilityInstance
from packages.capability_gateway.telemetry import (
    OUTCOME_CAPACITY_EXHAUSTED,
    OUTCOME_FAILED,
    OUTCOME_SUCCESS,
    ProviderAttemptRecord,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _record(
    pid: str, *, outcome: str = OUTCOME_SUCCESS, failure_class: str | None = None,
    transport: bool = True, latency: float = 100.0, fallback_used: bool = False,
    attempt_index: int = 0, tokens_in: int | None = None, tokens_out: int | None = None,
) -> ProviderAttemptRecord:
    return ProviderAttemptRecord(
        provider_call_id=f"{pid}-{attempt_index}",
        route_execution_id="r1",
        provider_instance_id=pid,
        outcome=outcome,
        transport_invoked=transport,
        started_at=_T0,
        finished_at=_T0 + timedelta(milliseconds=latency),
        latency_ms=latency,
        attempt_index=attempt_index,
        fallback_used=fallback_used,
        fallback_index=attempt_index,
        failure_class=failure_class,
        capability="llm",
        task_type="query_expansion",
        input_tokens=tokens_in,
        output_tokens=tokens_out,
    )


# ── G2.5b 聚合 ───────────────────────────────────────────────────────────────

def test_snapshot_separates_availability_quality_capacity():
    records = [
        _record("dp", outcome=OUTCOME_SUCCESS, tokens_in=100, tokens_out=20) for _ in range(9)
    ]
    records.append(_record("dp", outcome=OUTCOME_FAILED,
                           failure_class=ProviderFailureClass.TIMEOUT.value, latency=5000))
    records.append(_record("dp", outcome=OUTCOME_FAILED,
                           failure_class=ProviderFailureClass.OUTPUT_INVALID.value, latency=200))
    records.append(_record("dp", outcome=OUTCOME_CAPACITY_EXHAUSTED,
                           failure_class=ProviderFailureClass.CAPACITY_EXHAUSTED.value,
                           transport=False, latency=30000))

    snap = build_health_snapshot(records, provider_instance_id="dp")
    assert snap.transport_call_count == 11  # 只有 transport 的
    assert snap.success_count == 9
    assert snap.availability_failure_count == 1  # 只有 timeout 计入 availability
    assert snap.quality_failure_count == 1  # output_invalid 属于 quality
    assert snap.capacity_exhausted_count == 1  # 独立统计
    assert snap.transport_success_rate == 9 / 11
    assert snap.availability_failure_rate == 1 / 11
    assert snap.business_quality_failure_rate == 1 / 11
    assert snap.input_tokens == 900
    assert snap.output_tokens == 180


def test_snapshot_p50_p95():
    records = [_record("dp", latency=float(i * 100)) for i in range(1, 21)]  # 100..2000ms
    snap = build_health_snapshot(records, provider_instance_id="dp")
    assert snap.latency_p50_ms is not None and snap.latency_p50_ms <= snap.latency_p95_ms


def test_no_composite_health_score():
    records = [_record("dp") for _ in range(5)]
    snap = build_health_snapshot(records, provider_instance_id="dp")
    d = snap.to_dict()
    assert "health_score" not in d and "score" not in d  # 不做综合分


def test_dimensions_capacity_saturated_and_unhealthy():
    # capacity saturated
    cap_snap = build_health_snapshot(
        [_record("dp", outcome=OUTCOME_CAPACITY_EXHAUSTED,
                 failure_class=ProviderFailureClass.CAPACITY_EXHAUSTED.value, transport=False)],
        provider_instance_id="dp",
    )
    assert cap_snap.dimensions()["capacity"] == "saturated"
    # availability unhealthy
    bad = [_record("dp", outcome=OUTCOME_FAILED, failure_class=ProviderFailureClass.TIMEOUT.value)
           for _ in range(5)]
    un_snap = build_health_snapshot(bad, provider_instance_id="dp")
    assert un_snap.dimensions()["availability"] == "unhealthy"


# ── G2.5c health-aware shadow（只算不改） ────────────────────────────────────

def _three_provider_plan():
    reg = CapabilityRegistry()
    for pid, prio, role in (("a", 100, "primary"), ("b", 50, "fallback"), ("c", 20, "fallback")):
        reg.register(CapabilityInstance(
            instance_id=pid, capability=CapabilityType.LLM, provider="x", roles=[role],
            features={"structured_output": False, "max_context_tokens": 10000},
            routing={"priority": prio},
        ))
    request = llm_capability_request("query_expansion")
    return CapabilityRouter(reg).route(request)


def test_health_aware_excludes_unhealthy_demotes_saturated():
    plan = _three_provider_plan()
    assert plan.providers == ["a", "b", "c"]

    healthy_a = build_health_snapshot([_record("a")], provider_instance_id="a")
    saturated_b = build_health_snapshot(
        [_record("b", outcome=OUTCOME_CAPACITY_EXHAUSTED,
                 failure_class=ProviderFailureClass.CAPACITY_EXHAUSTED.value, transport=False)],
        provider_instance_id="b",
    )
    unhealthy_c = build_health_snapshot(
        [_record("c", outcome=OUTCOME_FAILED, failure_class=ProviderFailureClass.TIMEOUT.value)
         for _ in range(5)],
        provider_instance_id="c",
    )
    snapshots = {"a": healthy_a, "b": saturated_b, "c": unhealthy_c}

    aware = build_health_aware_providers(plan, snapshots)
    assert aware == ["a", "b"]  # c（unhealthy）被排除，b（saturated）被保留但降序
    shadow = compare_health_routing(plan, snapshots)
    assert shadow.diverges is True
    assert shadow.excluded_unhealthy == ["c"]
    assert "c" not in shadow.health_aware_providers


def test_health_aware_no_change_when_all_healthy():
    plan = _three_provider_plan()
    healthy = {pid: build_health_snapshot([_record(pid)], provider_instance_id=pid)
               for pid in ("a", "b", "c")}
    aware = build_health_aware_providers(plan, healthy)
    assert aware == ["a", "b", "c"]  # 全部健康 → 与 static 一致
    assert compare_health_routing(plan, healthy).diverges is False
