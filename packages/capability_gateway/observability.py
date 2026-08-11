"""网关负载/运行观测（2026-08-11）——从 provider_attempt_records 表聚合健康快照。

真实 run 通过 PostgresProviderAttemptRecorder 写入 attempt 记录（G2.5a）。本模块
提供查询 + build_health_snapshot 聚合，供 API 暴露网关负载/运行状态。
"""

from __future__ import annotations

from typing import Any

from packages.capability_gateway.health import ProviderHealthSnapshot, build_health_snapshot
from packages.capability_gateway.telemetry import ProviderAttemptRecord

_QUERY_COLS = (
    "provider_call_id, route_execution_id, request_fingerprint, run_id, "
    "provider_instance_id, capability, task_type, attempt_index, transport_invoked, "
    "started_at, finished_at, latency_ms, outcome, failure_class, fallback_used, "
    "fallback_index, input_tokens, output_tokens, request_count, result_count, "
    "cost_estimate, created_at"
)


def load_recent_attempts(
    session: Any,
    *,
    provider_instance_id: str | None = None,
    limit: int = 200,
) -> list[ProviderAttemptRecord]:
    """从 provider_attempt_records 表加载最近 attempt 记录。"""
    from sqlalchemy import text

    sql = f"SELECT {_QUERY_COLS} FROM provider_attempt_records"
    params: dict[str, Any] = {}
    if provider_instance_id:
        sql += " WHERE provider_instance_id = :pid"
        params["pid"] = provider_instance_id
    sql += " ORDER BY started_at DESC LIMIT :lim"
    params["lim"] = min(max(limit, 1), 1000)
    rows = session.execute(text(sql), params).mappings().all()
    return [_record_from_row(dict(row)) for row in rows]


def _record_from_row(row: dict[str, Any]) -> ProviderAttemptRecord:
    return ProviderAttemptRecord(
        provider_call_id=str(row.get("provider_call_id") or ""),
        route_execution_id=str(row.get("route_execution_id") or ""),
        provider_instance_id=str(row.get("provider_instance_id") or ""),
        outcome=str(row.get("outcome") or ""),
        transport_invoked=bool(row.get("transport_invoked")),
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        latency_ms=row.get("latency_ms"),
        attempt_index=int(row.get("attempt_index") or 0),
        fallback_used=bool(row.get("fallback_used")),
        fallback_index=row.get("fallback_index"),
        failure_class=row.get("failure_class"),
        request_fingerprint=row.get("request_fingerprint"),
        run_id=row.get("run_id"),
        capability=row.get("capability"),
        task_type=row.get("task_type"),
        input_tokens=row.get("input_tokens"),
        output_tokens=row.get("output_tokens"),
        request_count=row.get("request_count"),
        result_count=row.get("result_count"),
        cost_estimate=row.get("cost_estimate"),
        created_at=row.get("created_at"),
    )


def build_provider_health(
    session: Any,
    *,
    window_hours: float = 24.0,
    limit: int = 500,
) -> dict[str, dict[str, Any]]:
    """聚合各 provider 的健康快照（按 provider_instance_id 分组）。"""
    from datetime import datetime, timedelta, timezone

    records = load_recent_attempts(session, limit=limit)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    by_provider: dict[str, list[ProviderAttemptRecord]] = {}
    for r in records:
        # sqlite 可能返回 ISO 字符串；解析为 datetime（naive 视为 UTC）
        started = r.started_at
        if isinstance(started, str):
            try:
                started = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
            except Exception:
                started = None
        if started:
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if started < cutoff:
                continue
        by_provider.setdefault(r.provider_instance_id, []).append(r)

    out: dict[str, dict[str, Any]] = {}
    for pid, recs in by_provider.items():
        snap: ProviderHealthSnapshot = build_health_snapshot(recs, provider_instance_id=pid)
        out[pid] = {
            "attempt_count": snap.attempt_count,
            "success_count": snap.success_count,
            "transport_call_count": snap.transport_call_count,
            "timeout_count": snap.timeout_count,
            "rate_limit_count": snap.rate_limit_count,
            "provider_5xx_count": snap.provider_5xx_count,
            "network_failure_count": snap.network_failure_count,
            "capacity_exhausted_count": snap.capacity_exhausted_count,
            "fallback_from_count": snap.fallback_from_count,
            "fallback_to_count": snap.fallback_to_count,
            "latency_p50_ms": snap.latency_p50_ms,
            "latency_p95_ms": snap.latency_p95_ms,
            "input_tokens": snap.input_tokens,
            "output_tokens": snap.output_tokens,
            "transport_success_rate": round(snap.transport_success_rate, 4),
            "availability_failure_rate": round(snap.availability_failure_rate, 4),
            "dimensions": snap.dimensions(),
        }
    return out


def build_gateway_summary(session: Any, *, window_hours: float = 24.0) -> dict[str, Any]:
    """网关综合健康概览：各 provider 状态 + 电路 + 预算。"""
    providers = build_provider_health(session, window_hours=window_hours)
    # circuit 状态（进程内 store 或默认 CLOSED）
    circuit_states: dict[str, str] = {}
    try:
        from packages.capability_gateway.circuit import InMemoryCircuitStateStore

        store = InMemoryCircuitStateStore()
        for pid in providers:
            try:
                circuit_states[pid] = str(store.get(pid).state)
            except Exception:
                circuit_states[pid] = "CLOSED"
    except Exception:
        circuit_states = {pid: "CLOSED" for pid in providers}
    return {
        "provider_count": len(providers),
        "providers": providers,
        "circuit_states": circuit_states,
        "window_hours": window_hours,
    }
