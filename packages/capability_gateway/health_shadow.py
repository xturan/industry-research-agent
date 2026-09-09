"""G2.5c Health-aware Routing Shadow — 只算不改（observe only）。

Router 正式仍用 priority → role → static eligibility；这里额外计算一个
「如果按 health 调整会怎样」的 hypothetical plan，用于 Shadow Compare。

规则（第一版，可解释）：
- availability == "unhealthy" 的 Provider → 从 hypothetical plan 排除（不调用）。
- capacity == "saturated" 的 Provider → 降到最后（保留，但延后）。
- 其余保持原 static 顺序。

**绝不修改正式 Router / 不 Promote**，验证后再决定。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.capability_gateway.plan import RoutingPlan


@dataclass
class HealthRoutingShadow:
    """static plan vs health-aware hypothetical plan 的对比。"""

    route_execution_fingerprint: str | None
    static_providers: list[str]
    health_aware_providers: list[str]
    excluded_unhealthy: list[str] = field(default_factory=list)
    demoted_saturated: list[str] = field(default_factory=list)

    @property
    def diverges(self) -> bool:
        return self.static_providers != self.health_aware_providers

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_fingerprint": self.route_execution_fingerprint,
            "static_providers": list(self.static_providers),
            "health_aware_providers": list(self.health_aware_providers),
            "excluded_unhealthy": list(self.excluded_unhealthy),
            "demoted_saturated": list(self.demoted_saturated),
            "diverges": self.diverges,
        }


def build_health_aware_providers(
    plan: RoutingPlan,
    health_snapshots: dict[str, Any],
) -> list[str]:
    """按 health 调整 provider 顺序（hypothetical，不执行）。"""
    healthy: list[str] = []
    saturated: list[str] = []
    for provider_id in plan.providers:
        snap = health_snapshots.get(provider_id)
        if snap is None:
            healthy.append(provider_id)
            continue
        dims = snap.dimensions() if hasattr(snap, "dimensions") else {}
        if dims.get("availability") == "unhealthy":
            continue  # 排除（不调用）
        if dims.get("capacity") == "saturated":
            saturated.append(provider_id)
        else:
            healthy.append(provider_id)
    return healthy + saturated


def compare_health_routing(
    plan: RoutingPlan,
    health_snapshots: dict[str, Any],
) -> HealthRoutingShadow:
    """static plan vs health-aware hypothetical plan。"""
    static = list(plan.providers)
    aware = build_health_aware_providers(plan, health_snapshots)
    excluded = [p for p in static if p not in aware]
    demoted = [p for p in aware if p in static and aware.index(p) != static.index(p)]
    return HealthRoutingShadow(
        route_execution_fingerprint=plan.request_fingerprint,
        static_providers=static,
        health_aware_providers=aware,
        excluded_unhealthy=excluded,
        demoted_saturated=demoted,
    )


__all__ = ["HealthRoutingShadow", "build_health_aware_providers", "compare_health_routing"]
