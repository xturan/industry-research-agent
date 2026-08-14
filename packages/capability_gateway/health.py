"""G2.5b Provider Health Snapshot — 从 Attempt 数据聚合健康画像（observe only）。

关键区分（不要一个 success_rate 把失败混在一起）：
- transport_success_rate      = success / transport_call_count
- availability_failure_rate   = (NETWORK/TIMEOUT/429/5xx) / transport_call_count
- business_quality_failure_rate = (OUTPUT_INVALID/BUSINESS_VALIDATION) / transport_call_count
- capacity_exhausted_count    独立（Provider 很健康也可能饱和 → 驱动 capacity tuning，不是 OPEN）

第一版不做单一综合 health score；用可解释维度（availability/latency/capacity/quality）。
Health Snapshot 暂时不改变正式 Router（G2.5c 只做 shadow compare）。
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.capability_gateway.circuit import AVAILABILITY_FAILURES, ProviderFailureClass
from packages.capability_gateway.telemetry import (
    OUTCOME_CAPACITY_EXHAUSTED,
    OUTCOME_SUCCESS,
    ProviderAttemptRecord,
)

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11
    UTC = timezone.utc

# 业务/质量失败类（不算 Provider outage）。
QUALITY_FAILURES = {
    ProviderFailureClass.OUTPUT_INVALID,
    ProviderFailureClass.BUSINESS_VALIDATION,
}

# 维度判定阈值（provisional，后续压测校准）。
_AVAILABILITY_UNHEALTHY_RATE = 0.10
_LATENCY_DEGRADED_P95_MS = 5000.0
_QUALITY_DEGRADED_RATE = 0.10


@dataclass
class ProviderHealthSnapshot:
    provider_instance_id: str
    window_started_at: datetime
    window_ended_at: datetime
    attempt_count: int
    transport_call_count: int
    success_count: int
    availability_failure_count: int
    timeout_count: int
    rate_limit_count: int
    provider_5xx_count: int
    network_failure_count: int
    capacity_exhausted_count: int
    quality_failure_count: int
    fallback_from_count: int
    fallback_to_count: int
    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    transport_success_rate: float = 0.0
    availability_failure_rate: float = 0.0
    business_quality_failure_rate: float = 0.0

    def dimensions(self) -> dict[str, str]:
        """可解释维度（不是综合分）：availability/latency/capacity/quality。"""
        if self.transport_call_count == 0:
            availability = "healthy"
        else:
            availability = (
                "healthy"
                if self.availability_failure_rate < _AVAILABILITY_UNHEALTHY_RATE
                else "unhealthy"
            )
        latency = (
            "normal"
            if self.latency_p95_ms is None or self.latency_p95_ms < _LATENCY_DEGRADED_P95_MS
            else "degraded"
        )
        capacity = "saturated" if self.capacity_exhausted_count > 0 else "normal"
        quality = (
            "normal"
            if self.business_quality_failure_rate < _QUALITY_DEGRADED_RATE
            else "degraded"
        )
        return {
            "availability": availability,
            "latency": latency,
            "capacity": capacity,
            "quality": quality,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_instance_id": self.provider_instance_id,
            "window_started_at": self.window_started_at.isoformat(),
            "window_ended_at": self.window_ended_at.isoformat(),
            "attempt_count": self.attempt_count,
            "transport_call_count": self.transport_call_count,
            "success_count": self.success_count,
            "availability_failure_count": self.availability_failure_count,
            "timeout_count": self.timeout_count,
            "rate_limit_count": self.rate_limit_count,
            "provider_5xx_count": self.provider_5xx_count,
            "network_failure_count": self.network_failure_count,
            "capacity_exhausted_count": self.capacity_exhausted_count,
            "quality_failure_count": self.quality_failure_count,
            "fallback_from_count": self.fallback_from_count,
            "fallback_to_count": self.fallback_to_count,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "transport_success_rate": round(self.transport_success_rate, 4),
            "availability_failure_rate": round(self.availability_failure_rate, 4),
            "business_quality_failure_rate": round(self.business_quality_failure_rate, 4),
            "dimensions": self.dimensions(),
        }


def build_health_snapshot(
    records: list[ProviderAttemptRecord],
    *,
    provider_instance_id: str,
    now: datetime | None = None,
) -> ProviderHealthSnapshot:
    """从一次 Provider 的 attempt 记录聚合 Health Snapshot（observe only）。"""
    now = now or datetime.now(UTC)
    transport = [r for r in records if r.transport_invoked]
    window_start = min((r.started_at for r in records), default=now)
    window_end = max((r.finished_at or r.started_at for r in records), default=now)

    success_count = sum(1 for r in transport if r.outcome == OUTCOME_SUCCESS)
    availability_failure = [
        r for r in transport if r.failure_class in AVAILABILITY_FAILURES
    ]
    timeout_count = sum(
        1 for r in availability_failure if r.failure_class == ProviderFailureClass.TIMEOUT
    )
    rate_limit_count = sum(
        1 for r in availability_failure if r.failure_class == ProviderFailureClass.RATE_LIMIT
    )
    provider_5xx_count = sum(
        1 for r in availability_failure if r.failure_class == ProviderFailureClass.PROVIDER_5XX
    )
    network_failure_count = sum(
        1 for r in availability_failure if r.failure_class == ProviderFailureClass.NETWORK
    )
    capacity_count = sum(
        1 for r in records if r.outcome == OUTCOME_CAPACITY_EXHAUSTED
        or r.failure_class == ProviderFailureClass.CAPACITY_EXHAUSTED
    )
    quality_failure = [
        r for r in transport if r.failure_class in QUALITY_FAILURES
    ]
    fallback_from = sum(1 for r in records if r.fallback_used)
    fallback_to = sum(1 for r in records if r.outcome == OUTCOME_SUCCESS and r.fallback_used)

    latencies = [r.latency_ms for r in transport if r.latency_ms is not None]
    p50 = statistics.median(latencies) if latencies else None
    p95 = (
        sorted(latencies)[int(len(latencies) * 0.95) - 1]
        if latencies else None
    )

    total = len(transport)
    availability_failure_count = len(availability_failure)
    quality_failure_count = len(quality_failure)

    return ProviderHealthSnapshot(
        provider_instance_id=provider_instance_id,
        window_started_at=window_start,
        window_ended_at=window_end,
        attempt_count=len(records),
        transport_call_count=total,
        success_count=success_count,
        availability_failure_count=availability_failure_count,
        timeout_count=timeout_count,
        rate_limit_count=rate_limit_count,
        provider_5xx_count=provider_5xx_count,
        network_failure_count=network_failure_count,
        capacity_exhausted_count=capacity_count,
        quality_failure_count=quality_failure_count,
        fallback_from_count=fallback_from,
        fallback_to_count=fallback_to,
        latency_p50_ms=round(p50, 3) if p50 is not None else None,
        latency_p95_ms=round(p95, 3) if p95 is not None else None,
        input_tokens=sum(r.input_tokens or 0 for r in transport),
        output_tokens=sum(r.output_tokens or 0 for r in transport),
        transport_success_rate=success_count / total if total else 0.0,
        availability_failure_rate=availability_failure_count / total if total else 0.0,
        business_quality_failure_rate=quality_failure_count / total if total else 0.0,
    )


__all__ = ["ProviderHealthSnapshot", "build_health_snapshot"]
