"""G2.2 CapabilityRouter — 把 G2.1 的「谁有资格」编译成可执行的 RoutingPlan。

Registry 只负责 eligibility（Provider metadata / eligibility）。
Router 负责产生 RoutingPlan（routing decision）。
Provider Adapter 负责实际调用（G2.2b）。

G2.2 只回答「应该选谁」，不实现 concurrency budget / circuit transition /
metrics / retry / dynamic weighting（分别属于 G2.3/G2.4/G2.5）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from packages.capability_gateway.plan import RoutingPlan, RoutingStep, RoutingTrace
from packages.capability_gateway.registry import CapabilityRegistry
from packages.capability_gateway.schemas import (
    CapabilityRequest,
    RoutingPolicy,
)

# 允许 LLM fallback 到 best-effort（如 OpenRouter Free）的 task_type 白名单。
# 结构化抽取/claim/draft/synthesis 一律 strict（只 DeepSeek）。
LLM_FALLBACK_ALLOWED_TASK_TYPES = {
    "query_expansion",
    "search_phrase_generation",
    "simple_summary",
}


def _request_signature(request: CapabilityRequest) -> str:
    """稳定 request id：capability + task_type + 排序后的 requirements + 策略。"""
    blob = json.dumps(
        {
            "capability": request.capability.value,
            "task_type": request.task_type,
            "requirements": dict(sorted(request.requirements.items(), key=lambda kv: kv[0])),
            "routing_policy": request.routing_policy.value,
            "cost_policy": request.cost_policy.value,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _route_reasons(
    request: CapabilityRequest,
    plan_primary: str | None,
    has_fallback: bool,
    promoted: bool,
) -> list[str]:
    reasons: list[str] = []
    if plan_primary is None:
        reasons.append("no_eligible_provider")
        return reasons
    reasons.append("capability_match")
    reasons.append("requirements_satisfied")
    if promoted:
        reasons.append("promoted_fallback")
    else:
        reasons.append("highest_priority")
    if request.routing_policy == RoutingPolicy.STRICT:
        reasons.append("strict_primary_only")
    if has_fallback:
        reasons.append("fallback_allowed_by_policy")
    return reasons


@dataclass
class CapabilityRouter:
    """注册表之上的确定性路由层。给定请求，产出 RoutingPlan（含 trace）。

    G2.2d 硬化：Routing Policy 是与 Feature Requirement 独立的维度。
    - STRICT：只允许 primary-role 合格 Provider；fallback_chain 恒为空；
      primary 不可用 → primary=None（不把 fallback-role Provider 提升为 primary）。
      即使 fallback Provider 具备全部 feature，也不得作为 strict task 的 fallback。
    - FALLBACK_ALLOWED：primary-role 优先；fallback-role 作为 fallback_chain；
      primary 不可用时，fallback-role Provider 可被提升为 selected（promoted_fallback）。
    """

    registry: CapabilityRegistry

    def route(self, request: CapabilityRequest) -> RoutingPlan:
        decision = self.registry.select(request)
        eligible = decision.ordered_candidates  # 全部 capability/feature 合格（有序）

        # ── policy 硬化（G2.2d） ──────────────────────────────────────────────
        if request.routing_policy == RoutingPolicy.STRICT:
            usable = [inst for inst in eligible if inst.is_primary()]
            policy_filtered = [inst for inst in eligible if not inst.is_primary()]
            selected = usable[0] if usable else None
            fallback_chain: list[str] = []
        else:
            usable = list(eligible)
            policy_filtered = []
            selected = decision.selected
            fallback_chain = (
                [inst.instance_id for inst in decision.fallbacks]
                if selected is not None else []
            )

        # ── trace ─────────────────────────────────────────────────────────────
        trace_steps: list[RoutingStep] = []
        for inst in eligible:
            trace_steps.append(
                RoutingStep(instance_id=inst.instance_id, result="eligible",
                            reason="requirements_satisfied")
            )
        for inst in policy_filtered:
            trace_steps.append(
                RoutingStep(instance_id=inst.instance_id, result="filtered",
                            reason="strict_primary_only")
            )
        for instance_id in sorted(decision.rejected_by_id()):
            trace_steps.append(
                RoutingStep(instance_id=instance_id, result="filtered",
                            reason=decision.rejected_by_id()[instance_id])
            )

        promoted = selected is not None and not selected.is_primary()
        if selected is not None:
            trace_steps.append(
                RoutingStep(
                    instance_id=selected.instance_id, result="selected",
                    reason="promoted_fallback" if promoted else "highest_priority",
                )
            )

        primary = selected.instance_id if selected else None
        eligible_ids = [inst.instance_id for inst in usable]
        filtered = {
            **decision.rejected_by_id(),
            **{inst.instance_id: "strict_primary_only" for inst in policy_filtered},
        }

        return RoutingPlan(
            request_fingerprint=_request_signature(request),
            capability=request.capability,
            task_type=request.task_type,
            policy=request.routing_policy,
            primary=primary,
            fallback_chain=fallback_chain,
            eligible=eligible_ids,
            filtered=filtered,
            route_reason=_route_reasons(
                request, primary, bool(fallback_chain), promoted
            ),
            trace=RoutingTrace(request=request, steps=trace_steps),
        )


# ── 策略 helper：按 task_type 决定 LLM 是否允许 fallback ───────────────────────

def llm_policy_for_task(
    task_type: str, *, default: RoutingPolicy = RoutingPolicy.STRICT
) -> RoutingPolicy:
    """best-effort 类任务允许 fallback；结构化类严格 DeepSeek only。"""
    if task_type in LLM_FALLBACK_ALLOWED_TASK_TYPES:
        return RoutingPolicy.FALLBACK_ALLOWED
    return default


# ── feature flag helper（G2.2a 默认 shadow / off，不替换生产路径） ──────────────

def search_routing_mode(settings: Any = None) -> str:
    """返回 SEARCH 路由模式：off | shadow | gateway。

    - off     → 完全走 Legacy（build_search_discovery_provider 原逻辑）。
    - shadow  → Legacy 正式执行；Gateway 只计算「如果由我路由会选谁」并对比。
    - gateway → 正式由 Gateway 接管（G2.2b 才落地）。
    """
    from packages.core.config import get_settings

    app = settings or get_settings()
    if not app.capability_gateway_enabled:
        return "off"
    return str(app.capability_gateway_search_mode).strip().lower()


def llm_routing_mode(settings: Any = None) -> str:
    """返回 LLM 路由模式：off | shadow | gateway（G2.2b 之后才接入）。"""
    from packages.core.config import get_settings

    app = settings or get_settings()
    if not app.capability_gateway_enabled:
        return "off"
    return str(app.capability_gateway_llm_mode).strip().lower()
