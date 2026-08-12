"""G2.1 CapabilityRegistry — 硬过滤 + 确定性排序（不调用真实 API）。

G2.2 第一版 Router 不要"智能"。只做：

    Hard Filter:
      enabled
      circuit != OPEN
      supports capability
      supports required features
      concurrency available
      quota available

    然后确定性排序:
      priority  →  role(primary first)  →  health  →  latency  →  cost

先做到可解释，不搞 0.4*success_rate + 0.3*latency 这种加权。
后面有真实 Call Metrics（G2.5）再校准。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.capability_gateway.schemas import (
    CapabilityDecision,
    CapabilityInstance,
    CapabilityRequest,
    CapabilityRole,
    CapabilityType,
    CircuitState,
)

# 布尔型能力特性：request.requirements 里为 True 时，instance.features 必须为 True
# 才视为满足（False 表示"不要求"，任何 Provider 都可通过）。
_FEATURE_BOOL_KEYS = {"structured_output", "tool_calling", "json_schema"}

# 最小量能力特性：request 需要 N，instance.features 对应键必须 >= N。
_FEATURE_MIN_KEYS = {
    "min_context_tokens": "max_context_tokens",
    "max_results": "max_results",
}

# 成本分层排序值（越低越优先）。
_COST_RANK = {"free": 0, "low": 1, "paid": 2, "unknown": 3}


def _meets_features(
    instance: CapabilityInstance, requirements: dict[str, Any]
) -> tuple[bool, str | None]:
    """判断 instance 是否满足 request 的能力特性要求。

    规则：
    - 布尔特性（structured_output 等）：required=True 必须支持；False 不强制。
    - 最小量特性（min_context_tokens 等）：instance 的能力值必须 >= 需求值。
    - 其他键按布尔特性兜底。
    """
    features = instance.features or {}
    for key, value in requirements.items():
        if key in _FEATURE_BOOL_KEYS:
            if bool(value) is True and not bool(features.get(key, False)):
                return False, f"missing_feature:{key}"
        elif key in _FEATURE_MIN_KEYS:
            have = int(features.get(_FEATURE_MIN_KEYS[key], 0) or 0)
            need = int(value)
            if have < need:
                return False, (
                    f"insufficient_capacity:{key}=need_{need}_have_{have}"
                )
        else:
            if bool(value) is True and not bool(features.get(key, False)):
                return False, f"missing_feature:{key}"
    return True, None


def _sort_key(inst: CapabilityInstance) -> tuple:
    """确定性排序键：priority(desc) → role(primary first) → health(desc) →
    cost_tier(free first) → latency(asc) → instance_id(稳定)。"""
    role_rank = 0 if inst.is_primary() else 1
    return (
        -inst.priority,
        role_rank,
        -float(inst.health),
        _COST_RANK.get(inst.cost_tier, 3),
        inst.latency_ms if inst.latency_ms is not None else float("inf"),
        inst.instance_id,
    )


@dataclass
class CapabilityRegistry:
    """Provider 能力注册表。持有 CapabilityInstance 集合，按请求做硬过滤+排序。"""

    _instances: dict[str, CapabilityInstance] = field(default_factory=dict)

    def register(self, instance: CapabilityInstance) -> CapabilityInstance:
        if instance.instance_id in self._instances:
            raise ValueError(f"duplicate capability instance: {instance.instance_id}")
        self._instances[instance.instance_id] = instance
        return instance

    def register_all(self, instances: list[CapabilityInstance]) -> None:
        for inst in instances:
            self.register(inst)

    def unregister(self, instance_id: str) -> None:
        self._instances.pop(instance_id, None)

    def get(self, instance_id: str) -> CapabilityInstance | None:
        return self._instances.get(instance_id)

    def all(self) -> list[CapabilityInstance]:
        return sorted(self._instances.values(), key=lambda i: i.instance_id)

    # ── 硬过滤 ───────────────────────────────────────────────────────────────

    def evaluate(
        self, request: CapabilityRequest, instance: CapabilityInstance
    ) -> tuple[bool, str | None]:
        """Hard Filter。返回 (是否通过, 拒绝原因|None)。"""
        if not instance.enabled:
            return False, "disabled"
        if instance.capability != request.capability:
            return False, (
                f"capability_mismatch:want={request.capability.value}"
                f"_have={instance.capability.value}"
            )
        if instance.task_types is not None and request.task_type not in instance.task_types:
            return False, f"task_type_not_served:{request.task_type}"
        if instance.circuit == CircuitState.OPEN:
            return False, "circuit_open"
        ok, reason = _meets_features(instance, request.requirements)
        if not ok:
            return False, reason
        if not instance.has_concurrency():
            return False, "concurrency_capacity"
        if not instance.has_quota():
            return False, "quota_exhausted"
        return True, None

    def candidates(self, request: CapabilityRequest) -> list[CapabilityInstance]:
        """过滤 + 排序后的合格候选（selected 在其首位）。"""
        passed = [
            inst for inst in self.all() if self.evaluate(request, inst)[0]
        ]
        passed.sort(key=_sort_key)
        return passed

    def select(self, request: CapabilityRequest) -> CapabilityDecision:
        """裁决一次请求：返回 selected + fallbacks + 被过滤项及原因。"""
        passed: list[CapabilityInstance] = []
        filtered: list[tuple[CapabilityInstance, str]] = []
        for inst in self.all():
            ok, reason = self.evaluate(request, inst)
            if ok:
                passed.append(inst)
            else:
                filtered.append((inst, reason or "rejected"))
        passed.sort(key=_sort_key)
        return CapabilityDecision(
            request=request,
            ordered_candidates=passed,
            selected=passed[0] if passed else None,
            fallbacks=passed[1:],
            filtered_out=filtered,
        )


# ── 默认四 Provider 真实链（DeepSeek → OpenRouter Free / AnySearch → Tavily） ──

def default_registry() -> CapabilityRegistry:
    """构建 G2 第一版真实 Provider 注册表（静态能力描述，不读 key、不调 API）。"""
    registry = CapabilityRegistry()
    registry.register_all(
        [
            CapabilityInstance(
                instance_id="deepseek.chat.primary",
                capability=CapabilityType.LLM,
                provider="deepseek",
                model="deepseek-chat",
                enabled=True,
                roles=[CapabilityRole.PRIMARY.value],
                features={
                    "structured_output": True,
                    "json_schema": True,
                    "tool_calling": True,
                    "max_context_tokens": 64000,
                },
                limits={"max_concurrency": 10},
                routing={"priority": 100, "cost_tier": "paid"},
                reliability="high",
            ),
            CapabilityInstance(
                # 不要把 openrouter/free 当成稳定"模型"——它是 Provider 内部的
                # 动态免费模型路由入口，只是一种 best-effort fallback capability。
                # 实际 model 由 settings.openrouter_free_model 决定（当前固定
                # openai/gpt-oss-20b:free，见 config.py）。
                instance_id="openrouter.free.best_effort",
                capability=CapabilityType.LLM,
                provider="openrouter",
                model="openrouter/free",
                enabled=True,
                roles=[CapabilityRole.FALLBACK.value],
                features={
                    "structured_output": False,
                    "tool_calling": False,
                    "max_context_tokens": 8000,
                },
                limits={"max_concurrency": 5},
                routing={"priority": 20, "cost_tier": "free"},
                reliability="best_effort",
            ),
            CapabilityInstance(
                instance_id="anysearch.primary",
                capability=CapabilityType.SEARCH,
                provider="anysearch",
                model=None,
                enabled=True,
                roles=[CapabilityRole.PRIMARY.value],
                features={"max_results": 20, "fresh_web": True},
                limits={"max_concurrency": 20},
                routing={"priority": 100, "cost_tier": "paid"},
                reliability="high",
            ),
            CapabilityInstance(
                instance_id="tavily.fallback",
                capability=CapabilityType.SEARCH,
                provider="tavily",
                model=None,
                enabled=True,
                roles=[CapabilityRole.FALLBACK.value],
                features={"max_results": 10, "fresh_web": True},
                limits={"max_concurrency": 10},
                routing={"priority": 20, "cost_tier": "paid"},
                reliability="best_effort",
            ),
            CapabilityInstance(
                # 本地 Ollama source-tier 分类（strict）。验证 Gateway 是
                # provider-agnostic：source_tier_classification 的 requirements
                # 要求 local_inference=True，只有它满足 → 路由到 ollama 而非 DeepSeek。
                instance_id="ollama.source_tier.local",
                capability=CapabilityType.LLM,
                provider="ollama",
                model="local",
                enabled=True,
                roles=[CapabilityRole.PRIMARY.value],
                # 只服务 source_tier_classification（provider-agnostic 验证点）
                task_types=["source_tier_classification"],
                features={
                    "structured_output": True,
                    "json_schema": True,
                    "local_inference": True,
                },
                limits={"max_concurrency": 1},
                routing={"priority": 10, "cost_tier": "free"},
                reliability="local",
            ),
        ]
    )
    return registry
