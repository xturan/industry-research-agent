"""G2.2c LLM workload taxonomy — task_type → requirements + routing_policy。

把散落在 Agent 里的 LLM 调用统一成明确的 task_type。业务代码只说
`task_type=LLMTaskType.EVIDENCE_EXTRACTION`，Gateway 自动编译 requirements
（与 ResearchContract「业务声明语义，不重复声明底层实现约束」一致）。

设计原则：
- requirements 集中定义在 TaskProfile，Agent 不得手写 provider requirements；
- OpenRouter Free 只作为 best-effort task（query_expansion /
  search_phrase_generation）的 fallback candidate；
- strict task 的 RoutingPlan 禁止出现 OpenRouter Free fallback；
- G2.5 Metrics 将按这个 taxonomy 统计 workload。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from packages.capability_gateway.schemas import (
    CapabilityRequest,
    CapabilityType,
    CostPolicy,
    RoutingPolicy,
)


class LLMTaskType(StrEnum):
    """LLM workload taxonomy（第一版 9 类）。"""

    # 规划类（保守 strict：决定整个研究计划）
    INTENT_PLANNING = "intent_planning"
    RESEARCH_PLANNING = "research_planning"

    # best-effort（允许 fallback 到 OpenRouter Free）
    QUERY_EXPANSION = "query_expansion"
    SEARCH_PHRASE_GENERATION = "search_phrase_generation"

    # 结构化抽取/生成类（strict）
    EVIDENCE_EXTRACTION = "evidence_extraction"
    CLAIM_GENERATION = "claim_generation"
    STRUCTURED_DRAFT = "structured_draft"
    CONSTRAINED_SYNTHESIS = "constrained_synthesis"
    STRUCTURED_REPAIR = "structured_repair"

    # workflow 真实调用点（2026-08-12 审计修复：gateway 分类缺口 → KeyError 静默降级）
    DIMENSION_SEARCH_TERMS = "dimension_search_terms"
    EDITOR1_DIMENSION_SECTION = "editor1_dimension_section"

    # 本地 source-tier 分类（Ollama，strict）——验证 Gateway 是 provider-agnostic，
    # 不只是 DeepSeek+OpenRouter。
    SOURCE_TIER_CLASSIFICATION = "source_tier_classification"


@dataclass(frozen=True)
class LLMTaskProfile:
    """一个 LLM 任务的能力需求 + 路由策略（集中定义，Agent 不手写）。"""

    task_type: LLMTaskType
    routing_policy: RoutingPolicy
    requirements: dict[str, Any]
    cost_policy: CostPolicy = CostPolicy.QUALITY_FIRST
    description: str = ""


# best-effort：不需要强结构化，允许低成本 fallback
_BEST_EFFORT_REQ = {"structured_output": False, "min_context_tokens": 8000}
# strict：要求严格 JSON schema 输出（过滤掉 OpenRouter Free）
_STRICT_REQ = {"structured_output": True, "json_schema": True}
# source-tier 本地推理：要求 local_inference（只有 Ollama 满足，DeepSeek 被过滤）
_SOURCE_TIER_REQ = {"structured_output": True, "json_schema": True, "local_inference": True}


def _best_effort(task_type: LLMTaskType, desc: str) -> LLMTaskProfile:
    return LLMTaskProfile(
        task_type=task_type,
        routing_policy=RoutingPolicy.FALLBACK_ALLOWED,
        requirements=_BEST_EFFORT_REQ,
        cost_policy=CostPolicy.PREFER_LOW_COST,
        description=desc,
    )


def _strict(task_type: LLMTaskType, desc: str) -> LLMTaskProfile:
    return LLMTaskProfile(
        task_type=task_type,
        routing_policy=RoutingPolicy.STRICT,
        requirements=_STRICT_REQ,
        cost_policy=CostPolicy.QUALITY_FIRST,
        description=desc,
    )


LLM_TASK_PROFILES: dict[LLMTaskType, LLMTaskProfile] = {
    LLMTaskType.INTENT_PLANNING: _strict(
        LLMTaskType.INTENT_PLANNING, "意图识别/研究需求 intake（决定研究维度）"),
    LLMTaskType.RESEARCH_PLANNING: _strict(
        LLMTaskType.RESEARCH_PLANNING,
        "研究计划：dimensions/obligations/search_rounds/claim slots",
    ),
    LLMTaskType.QUERY_EXPANSION: _best_effort(
        LLMTaskType.QUERY_EXPANSION, "查询扩写（可降级）"),
    LLMTaskType.SEARCH_PHRASE_GENERATION: _best_effort(
        LLMTaskType.SEARCH_PHRASE_GENERATION, "检索短语生成（可降级）"),
    LLMTaskType.EVIDENCE_EXTRACTION: _strict(
        LLMTaskType.EVIDENCE_EXTRACTION, "证据抽取（严格 JSON）"),
    LLMTaskType.CLAIM_GENERATION: _strict(
        LLMTaskType.CLAIM_GENERATION, "Claim 生成（严格 JSON）"),
    LLMTaskType.STRUCTURED_DRAFT: _strict(
        LLMTaskType.STRUCTURED_DRAFT, "Editor1 结构化草稿（严格 JSON）"),
    LLMTaskType.CONSTRAINED_SYNTHESIS: _strict(
        LLMTaskType.CONSTRAINED_SYNTHESIS, "受约束综合（严格 JSON）"),
    LLMTaskType.STRUCTURED_REPAIR: _strict(
        LLMTaskType.STRUCTURED_REPAIR, "结构化校验修复/retry（严格 JSON）"),
    LLMTaskType.DIMENSION_SEARCH_TERMS: _strict(
        LLMTaskType.DIMENSION_SEARCH_TERMS,
        "一次 LLM 调用生成全部维度的搜索词（严格 JSON，stride 是检索质量）",
    ),
    LLMTaskType.EDITOR1_DIMENSION_SECTION: _strict(
        LLMTaskType.EDITOR1_DIMENSION_SECTION,
        "Editor1 按维度分章节生成（严格 JSON，stride 是报告质量）",
    ),
    LLMTaskType.SOURCE_TIER_CLASSIFICATION: LLMTaskProfile(
        task_type=LLMTaskType.SOURCE_TIER_CLASSIFICATION,
        routing_policy=RoutingPolicy.STRICT,
        requirements=_SOURCE_TIER_REQ,
        cost_policy=CostPolicy.QUALITY_FIRST,
        description="本地 source-tier 分类（Ollama，严格 JSON）",
    ),
}

# 第一版允许 fallback 的 task（OpenRouter Free 只进这两个）
FALLBACK_ALLOWED_TASK_TYPES = {
    LLMTaskType.QUERY_EXPANSION,
    LLMTaskType.SEARCH_PHRASE_GENERATION,
}

# strict task 集合（RoutingPlan 必须 0 fallback）
STRICT_TASK_TYPES = {t for t in LLMTaskType if t not in FALLBACK_ALLOWED_TASK_TYPES}


def get_llm_profile(task_type: LLMTaskType | str) -> LLMTaskProfile:
    """按 task_type（枚举或字符串）取 profile；未知抛 KeyError（尽早暴露分类缺口）。"""
    if isinstance(task_type, LLMTaskType):
        key = task_type
    else:
        try:
            key = LLMTaskType(task_type)
        except ValueError as exc:
            raise KeyError(f"未分类的 LLM task_type: {task_type}") from exc
    try:
        return LLM_TASK_PROFILES[key]
    except KeyError as exc:
        raise KeyError(f"未分类的 LLM task_type: {task_type}") from exc


def llm_capability_request(task_type: LLMTaskType | str) -> CapabilityRequest:
    """由 profile 自动编译 CapabilityRequest（Agent 不手写 requirements）。"""
    profile = get_llm_profile(task_type)
    return CapabilityRequest(
        capability=CapabilityType.LLM,
        task_type=profile.task_type.value,
        requirements=dict(profile.requirements),
        routing_policy=profile.routing_policy,
        cost_policy=profile.cost_policy,
    )


def legacy_llm_provider() -> str:
    """默认正式 LLM provider（大多数 workload 是 DeepSeek）。"""
    return "deepseek"


def legacy_provider_for_task(task_type: LLMTaskType | str) -> str:
    """某个 workload 的 Legacy 语义 Provider（primary equivalence 的对照）。"""
    key = get_llm_profile(task_type).task_type
    if key == LLMTaskType.SOURCE_TIER_CLASSIFICATION:
        return "ollama"
    return "deepseek"


def legacy_primary_instance(task_type: LLMTaskType | str) -> str:
    """Legacy 语义 Provider 对应的 Gateway instance_id。"""
    provider = legacy_provider_for_task(task_type)
    if provider == "ollama":
        return "ollama.source_tier.local"
    return "deepseek.chat.primary"


__all__ = [
    "FALLBACK_ALLOWED_TASK_TYPES",
    "LLMTaskProfile",
    "LLMTaskType",
    "LLM_TASK_PROFILES",
    "STRICT_TASK_TYPES",
    "get_llm_profile",
    "legacy_llm_provider",
    "legacy_primary_instance",
    "legacy_provider_for_task",
    "llm_capability_request",
]
