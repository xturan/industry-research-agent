"""G2.2a SEARCH Shadow Compare — Legacy 与 Gateway 路由等价性（不替换生产路径）。

原则（Shadow → Compare → Promote）：
- 现有 `build_search_discovery_provider` 仍是正式执行路径。
- Gateway 只计算「如果由我路由，我会选谁」并对比 Legacy 选择。
- 要求 shadow divergence = 0 后，才进入 G2.2b 正式切到 Gateway。
- shadow 阶段不 invoke 任何 Provider（非干预）。

Legacy 基线来自 Settings：
    SEARCH_DISCOVERY_PROVIDER = "anysearch"          → legacy primary
    SEARCH_DISCOVERY_FALLBACK_PROVIDER = "tavily"    → legacy fallback（fallback_enabled 时）
    SEARCH_PROVIDER_POLICY = "fallback_allowed"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.capability_gateway.plan import RoutingPlan
from packages.capability_gateway.registry import CapabilityRegistry
from packages.capability_gateway.router import CapabilityRouter
from packages.capability_gateway.schemas import (
    CapabilityRequest,
    CapabilityType,
    CostPolicy,
    RoutingPolicy,
)

# Legacy provider 名 → Gateway instance_id 映射（G2.2a 只覆盖 SEARCH 两条链）。
LEGACY_PROVIDER_TO_INSTANCE = {
    "anysearch": "anysearch.primary",
    "tavily": "tavily.fallback",
}


@dataclass
class RoutingShadowReport:
    """一次 shadow 对比的结果。equivalent=True 表示 Gateway 与 Legacy 选择一致。"""

    capability: CapabilityType
    task_type: str
    legacy_policy: str
    legacy_primary: str | None
    legacy_fallback: str | None
    gateway_primary: str | None
    gateway_fallback: str | None
    equivalent: bool
    divergences: list[str] = field(default_factory=list)
    plan: RoutingPlan | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability.value,
            "task_type": self.task_type,
            "legacy_policy": self.legacy_policy,
            "legacy_primary": self.legacy_primary,
            "legacy_fallback": self.legacy_fallback,
            "gateway_primary": self.gateway_primary,
            "gateway_fallback": self.gateway_fallback,
            "equivalent": self.equivalent,
            "divergences": list(self.divergences),
            "plan": self.plan.to_dict() if self.plan else None,
        }


def _expected_instance(legacy_name: str | None) -> str | None:
    if not legacy_name:
        return None
    return LEGACY_PROVIDER_TO_INSTANCE.get(str(legacy_name).strip().lower())


def shadow_compare_search(
    request: CapabilityRequest,
    router: CapabilityRouter,
    *,
    legacy_primary: str = "anysearch",
    legacy_fallback: str | None = "tavily",
    legacy_policy: str = "fallback_allowed",
) -> RoutingShadowReport:
    """对比一次 SEARCH 请求的 Legacy vs Gateway 选择。纯函数，不 invoke。"""
    plan = router.route(request)
    gw_primary = plan.primary
    gw_fallback = plan.fallback_chain[0] if plan.fallback_chain else None

    exp_primary = _expected_instance(legacy_primary)
    exp_fallback = _expected_instance(legacy_fallback)

    divergences: list[str] = []
    if exp_primary != gw_primary:
        divergences.append(
            f"primary:legacy={legacy_primary!r}->{exp_primary!r} gateway={gw_primary!r}"
        )
    if exp_fallback != gw_fallback:
        divergences.append(
            f"fallback:legacy={legacy_fallback!r}->{exp_fallback!r} gateway={gw_fallback!r}"
        )

    return RoutingShadowReport(
        capability=request.capability,
        task_type=request.task_type,
        legacy_policy=legacy_policy,
        legacy_primary=legacy_primary,
        legacy_fallback=legacy_fallback,
        gateway_primary=gw_primary,
        gateway_fallback=gw_fallback,
        equivalent=not divergences,
        divergences=divergences,
        plan=plan,
    )


def shadow_compare_from_settings(
    registry: CapabilityRegistry,
    router: CapabilityRouter,
    settings: Any = None,
) -> RoutingShadowReport:
    """从真实 Settings 读取 Legacy 基线并对比（不 invoke）。"""
    from packages.core.config import get_settings

    app = settings or get_settings()
    legacy_primary = str(app.search_discovery_provider or "").strip().lower()
    legacy_fallback = (
        str(app.search_discovery_fallback_provider or "").strip().lower()
        if app.search_discovery_fallback_enabled
        else None
    )
    legacy_policy = str(app.search_provider_policy or "fallback_allowed").strip().lower()

    request = CapabilityRequest(
        capability=CapabilityType.SEARCH,
        task_type="research_discovery",
        requirements={"fresh_web": True},
        routing_policy=RoutingPolicy.FALLBACK_ALLOWED,
        cost_policy=CostPolicy.PREFER_LOW_COST,
    )
    return shadow_compare_search(
        request,
        router,
        legacy_primary=legacy_primary,
        legacy_fallback=legacy_fallback,
        legacy_policy=legacy_policy,
    )


__all__ = [
    "LEGACY_PROVIDER_TO_INSTANCE",
    "RoutingShadowReport",
    "shadow_compare_from_settings",
    "shadow_compare_search",
]
