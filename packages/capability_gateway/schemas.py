"""G2.1 Capability Contract — 描述「Agent 需要什么能力」，而不是「调用谁」。

核心原则：
> Agent 描述"我需要什么能力"，Gateway 决定"谁来完成"。

Agent 不写 `deepseek_client.chat(...)`，而写
`gateway.execute(CapabilityRequest(capability=..., task_type=..., ...))`。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CapabilityType(StrEnum):
    """能力类别。G2.1 只启用 LLM / SEARCH。

    EMBED / RERANK 属于独立 Resource Model（本地 GPU、batch、VRAM、model
    loading、queue），等 G2.6 再作为 CapabilityInstance 接入，避免牵着
    网关架构走。
    """

    LLM = "llm"
    SEARCH = "search"
    EMBED = "embed"
    RERANK = "rerank"


class RoutingPolicy(StrEnum):
    """请求级路由策略。

    - best_effort:      尽力而为，能上就上（query 扩写等可降级任务）
    - strict:           严格，候选能力不满足 Contract 就绝不使用
    - fallback_allowed: 主 provider 失败时允许走 fallback（搜索等）
    """

    BEST_EFFORT = "best_effort"
    STRICT = "strict"
    FALLBACK_ALLOWED = "fallback_allowed"


class CostPolicy(StrEnum):
    """成本策略，作为排序的次级信号（G2.2 确定性排序时才参与）。"""

    PREFER_LOW_COST = "prefer_low_cost"
    QUALITY_FIRST = "quality_first"


class CircuitState(StrEnum):
    """Provider 熔断状态（G2.4 完整实现；G2.1 过滤阶段直接消费）。

    只把 NETWORK / TIMEOUT / PROVIDER_429 / PROVIDER_5XX 计入熔断；
    MODEL_OUTPUT_INVALID 等业务质量失败不算 Provider 挂。
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CapabilityRole(StrEnum):
    PRIMARY = "primary"
    FALLBACK = "fallback"


@dataclass
class CapabilityInstance:
    """Registry 中的一行：描述「某个 Provider 能做什么」。

    字段对应设计稿：
    - identity: instance_id / capability / provider / model
    - enabled
    - roles: ["primary"] 或 ["fallback"]
    - features: structured_output / tool_calling / max_context_tokens / max_results ...
    - limits: max_concurrency / quota_remaining
    - routing: priority / cost_tier
    - reliability: best_effort / high
    - 运行期状态: circuit / health / latency_ms / current_concurrency
    """

    instance_id: str
    capability: CapabilityType
    provider: str
    model: str | None = None
    enabled: bool = True
    roles: list[str] = field(default_factory=list)
    # None = 服务任意 task_type；否则只服务列出的 task_type（按 workload 白名单）
    task_types: list[str] | None = None
    features: dict[str, Any] = field(default_factory=dict)
    limits: dict[str, Any] = field(default_factory=dict)
    routing: dict[str, Any] = field(default_factory=dict)
    reliability: str = "best_effort"
    circuit: CircuitState = CircuitState.CLOSED
    health: float = 1.0
    latency_ms: float | None = None
    current_concurrency: int = 0

    # ── 派生访问器（避免各处散落 int()/dict.get） ──────────────────────────

    @property
    def priority(self) -> int:
        return int(self.routing.get("priority", 0) or 0)

    @property
    def cost_tier(self) -> str:
        return str(self.routing.get("cost_tier", "unknown"))

    @property
    def max_concurrency(self) -> int:
        return int(self.limits.get("max_concurrency", 0) or 0)

    def is_primary(self) -> bool:
        return CapabilityRole.PRIMARY.value in self.roles

    def has_concurrency(self) -> bool:
        """未配置并发上限（<=0）视为不限制；否则 current < max。"""
        if self.max_concurrency <= 0:
            return True
        return self.current_concurrency < self.max_concurrency

    def has_quota(self) -> bool:
        quota = self.limits.get("quota_remaining")
        if quota is None:
            return True
        return int(quota) > 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "capability": self.capability.value,
            "provider": self.provider,
            "model": self.model,
            "enabled": self.enabled,
            "roles": list(self.roles),
            "task_types": list(self.task_types) if self.task_types else None,
            "features": dict(self.features),
            "limits": dict(self.limits),
            "routing": dict(self.routing),
            "reliability": self.reliability,
            "circuit": self.circuit.value,
            "health": self.health,
            "latency_ms": self.latency_ms,
            "current_concurrency": self.current_concurrency,
        }


@dataclass
class CapabilityRequest:
    """Agent 描述"我需要什么能力"。由 Gateway 决定谁来完成。

    例（query 扩写，可降级）:
        capability=llm, task_type=query_expansion,
        requirements={"structured_output": False, "tool_calling": False,
                      "min_context_tokens": 8000},
        routing_policy=best_effort, cost_policy=prefer_low_cost

    例（claim extraction，严格）:
        capability=llm, task_type=evidence_extraction,
        requirements={"structured_output": True, "json_schema": True,
                      "min_context_tokens": 32000},
        routing_policy=strict, cost_policy=quality_first
    """

    capability: CapabilityType
    task_type: str
    requirements: dict[str, Any] = field(default_factory=dict)
    routing_policy: RoutingPolicy = RoutingPolicy.BEST_EFFORT
    cost_policy: CostPolicy = CostPolicy.PREFER_LOW_COST


@dataclass
class CapabilityDecision:
    """Registry 对一次 CapabilityRequest 的裁决结果（纯确定性，不调用 API）。"""

    request: CapabilityRequest
    ordered_candidates: list[CapabilityInstance] = field(default_factory=list)
    selected: CapabilityInstance | None = None
    fallbacks: list[CapabilityInstance] = field(default_factory=list)
    filtered_out: list[tuple[CapabilityInstance, str]] = field(default_factory=list)

    @property
    def has_selection(self) -> bool:
        return self.selected is not None

    def rejected_reasons(self) -> list[str]:
        return [reason for _inst, reason in self.filtered_out]

    def rejected_by_id(self) -> dict[str, str]:
        """{instance_id: 被过滤原因}——便于断言/审计。"""
        return {inst.instance_id: reason for inst, reason in self.filtered_out}
