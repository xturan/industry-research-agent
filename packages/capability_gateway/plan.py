"""G2.2 RoutingPlan / RoutingTrace — 可审计的路由决策产物。

`CapabilityDecision`（G2.1）回答「哪些 Provider 合格、哪些被过滤、为什么」；
`RoutingPlan` 回答「这一次业务调用应该按什么顺序尝试 Provider」。

职责分离：
    CapabilityRequest → Registry(eligibility) → Router(decision→plan) → RoutingPlan
    RoutingPlan → Invoker/Adapter → Provider
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.capability_gateway.schemas import CapabilityRequest, CapabilityType, RoutingPolicy


@dataclass
class RoutingStep:
    """Trace 中的一行：某个 instance 在这次 route 中的结果与原因。"""

    instance_id: str
    result: str  # eligible | filtered | selected
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "instance_id": self.instance_id,
            "result": self.result,
            "reason": self.reason,
        }


@dataclass
class RoutingTrace:
    """一次 route 的完整决策轨迹（debug 用，不塞进 RunEvent）。

    三层分层：
      RunEvent（G1）       → 业务阶段（SEARCH_STARTED / SEARCH_COMPLETED）
      CapabilityRoutingTrace（G2） → 路由决策（选谁、为什么）
      ProviderCallMetric（G2.5） → Provider 调用（延迟/成败）
    """

    request: CapabilityRequest
    steps: list[RoutingStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.request.capability.value,
            "task_type": self.request.task_type,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class RoutingPlan:
    """一次业务调用的可执行路由计划（确定性、可序列化、可复现）。

    注意 request_fingerprint 是「路由决策指纹」（同请求稳定），不是「一次实际调用」
    的 trace id；一次实际调用由 invoker 生成 route_execution_id（Gateway invocation）
    + provider_call_id（每次 Provider attempt）。
    """

    capability: CapabilityType
    task_type: str
    policy: RoutingPolicy
    primary: str | None  # instance_id；None = 无合格 Provider
    fallback_chain: list[str]  # 按尝试顺序
    eligible: list[str]  # 全部合格候选（有序）
    filtered: dict[str, str]  # {instance_id: 被过滤原因}
    route_reason: list[str]  # 人类可读的决策理由（deterministic）
    trace: RoutingTrace
    request_fingerprint: str | None = None

    @property
    def providers(self) -> list[str]:
        """按调用顺序展开：primary + fallback_chain（去掉 None/空）。"""
        ordered = []
        if self.primary:
            ordered.append(self.primary)
        for pid in self.fallback_chain:
            if pid and pid not in ordered:
                ordered.append(pid)
        return ordered

    @property
    def has_selection(self) -> bool:
        return self.primary is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_fingerprint": self.request_fingerprint,
            "capability": self.capability.value,
            "task_type": self.task_type,
            "policy": self.policy.value,
            "primary": self.primary,
            "fallback_chain": list(self.fallback_chain),
            "eligible": list(self.eligible),
            "filtered": dict(self.filtered),
            "route_reason": list(self.route_reason),
            "trace": self.trace.to_dict(),
        }
