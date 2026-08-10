"""G2.2c LLM Routing Shadow tests.

验证：LLM workload taxonomy（task_type → requirements + policy 集中定义）、
LLMCapabilityService shadow plan（纯路由不 invoke）、primary divergence=0、
strict fallback leakage=0、best-effort 才有 OpenRouter candidate。

本轮不做真实 OpenRouter 调用 / concurrency / circuit / metrics / retry。
"""

from __future__ import annotations

import pytest

from packages.capability_gateway import (
    FALLBACK_ALLOWED_TASK_TYPES,
    STRICT_TASK_TYPES,
    CapabilityRouter,
    LLMCapabilityService,
    LLMTaskType,
    RoutingPolicy,
    build_llm_capability_service,
    default_registry,
    get_llm_profile,
    legacy_primary_instance,
    llm_capability_request,
    llm_routing_mode,
)
from packages.core.config import Settings


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        CAPABILITY_GATEWAY_ENABLED=True,
        CAPABILITY_GATEWAY_SEARCH_MODE="shadow",
        CAPABILITY_GATEWAY_LLM_MODE="shadow",
    )


# ── taxonomy：policy 分类 ────────────────────────────────────────────────────

def test_best_effort_task_types_have_fallback_policy():
    assert set(FALLBACK_ALLOWED_TASK_TYPES) == {
        LLMTaskType.QUERY_EXPANSION,
        LLMTaskType.SEARCH_PHRASE_GENERATION,
    }
    for task_type in FALLBACK_ALLOWED_TASK_TYPES:
        assert get_llm_profile(task_type).routing_policy == RoutingPolicy.FALLBACK_ALLOWED


def test_strict_task_types_are_strict():
    assert LLMTaskType.INTENT_PLANNING in STRICT_TASK_TYPES
    assert LLMTaskType.RESEARCH_PLANNING in STRICT_TASK_TYPES
    assert LLMTaskType.EVIDENCE_EXTRACTION in STRICT_TASK_TYPES
    assert LLMTaskType.CLAIM_GENERATION in STRICT_TASK_TYPES
    assert LLMTaskType.STRUCTURED_DRAFT in STRICT_TASK_TYPES
    assert LLMTaskType.CONSTRAINED_SYNTHESIS in STRICT_TASK_TYPES
    assert LLMTaskType.STRUCTURED_REPAIR in STRICT_TASK_TYPES
    for task_type in STRICT_TASK_TYPES:
        assert get_llm_profile(task_type).routing_policy == RoutingPolicy.STRICT


def test_all_taxonomy_types_covered():
    from packages.capability_gateway import LLM_TASK_PROFILES

    assert set(LLM_TASK_PROFILES) == set(LLMTaskType)
    assert len(LLM_TASK_PROFILES) == 10  # 9 + source_tier_classification


def test_requirements_centralized():
    # strict：强结构化 + json_schema（过滤 OpenRouter Free）
    strict_req = llm_capability_request(LLMTaskType.EVIDENCE_EXTRACTION).requirements
    assert strict_req["structured_output"] is True
    assert strict_req["json_schema"] is True
    # best-effort：不强结构化，但要求最小上下文
    best_req = llm_capability_request(LLMTaskType.QUERY_EXPANSION).requirements
    assert best_req["structured_output"] is False
    assert best_req["min_context_tokens"] == 8000


def test_unknown_task_type_raises():
    with pytest.raises(KeyError):
        get_llm_profile("no_such_task")
    with pytest.raises(KeyError):
        llm_capability_request("no_such_task")


# ── shadow plan：strict / best-effort ────────────────────────────────────────

def test_strict_plan_has_no_openrouter_fallback():
    svc = build_llm_capability_service(_settings())
    for task_type in STRICT_TASK_TYPES:
        result = svc.plan(task_type)
        # strict 的 primary = 该 workload 的 legacy 语义 provider
        assert result.gateway_primary == legacy_primary_instance(task_type)
        assert result.fallback_chain == []
        assert "openrouter" not in result.providers
        assert result.strict_leakage == 0


def test_best_effort_plan_has_openrouter_fallback():
    svc = build_llm_capability_service(_settings())
    for task_type in FALLBACK_ALLOWED_TASK_TYPES:
        result = svc.plan(task_type)
        assert result.gateway_primary == "deepseek.chat.primary"
        assert result.fallback_chain == ["openrouter.free.best_effort"]
        assert result.providers == ["deepseek.chat.primary", "openrouter.free.best_effort"]


# ── shadow 不 invoke / 纯路由 ────────────────────────────────────────────────

def test_shadow_plan_does_not_invoke():
    """plan() 是纯路由计算；即使 adapter 不存在也能出结果（不触发任何 transport）。"""
    svc = build_llm_capability_service(_settings())
    result = svc.plan(LLMTaskType.QUERY_EXPANSION)
    assert result.task_type == "query_expansion"
    assert result.equivalent_primary is True


# ── acceptance 指标 ──────────────────────────────────────────────────────────

def test_primary_divergence_zero():
    """primary divergence=0：gateway primary == legacy 语义 provider（不假设全是 DeepSeek）。"""
    svc = build_llm_capability_service(_settings())
    for task_type in LLMTaskType:
        result = svc.plan(task_type)
        expected = legacy_primary_instance(task_type)
        assert result.legacy_primary_instance == expected
        assert result.gateway_primary == expected
        assert result.equivalent_primary is True  # primary divergence = 0


def test_strict_fallback_leakage_zero():
    svc = build_llm_capability_service(_settings())
    for task_type in STRICT_TASK_TYPES:
        result = svc.plan(task_type)
        assert result.strict_leakage == 0
        assert all("openrouter" not in pid for pid in result.providers)


def test_filtered_reasons_recorded_for_strict():
    svc = build_llm_capability_service(_settings())
    result = svc.plan(LLMTaskType.EVIDENCE_EXTRACTION)
    assert "openrouter.free.best_effort" in result.filtered
    assert result.filtered["openrouter.free.best_effort"].startswith("missing_feature")


def test_counterfactual_strict_isolated_from_features():
    """反事实：即使 OpenRouter 具备全部 feature，strict task 也不得 fallback。

    证明 strict isolation 是 Router 架构规则，不是 Registry metadata 的偶然结果。
    """
    reg = default_registry()
    openrouter = reg.get("openrouter.free.best_effort")
    openrouter.features.update({
        "structured_output": True, "json_schema": True, "tool_calling": True,
    })
    svc = LLMCapabilityService(settings=_settings(), router=CapabilityRouter(reg))
    for task_type in (
        LLMTaskType.EVIDENCE_EXTRACTION,
        LLMTaskType.CLAIM_GENERATION,
        LLMTaskType.STRUCTURED_DRAFT,
    ):
        result = svc.plan(task_type)
        assert result.gateway_primary == "deepseek.chat.primary"
        assert result.fallback_chain == []
        assert "openrouter" not in result.providers
        # 被过滤原因是策略（strict_primary_only），而非 feature 缺失
        assert result.filtered.get("openrouter.free.best_effort") == "strict_primary_only"

    # DeepSeek 不可用 → strict 直接失败，绝不提升 OpenRouter
    reg.get("deepseek.chat.primary").enabled = False
    result = svc.plan(LLMTaskType.EVIDENCE_EXTRACTION)
    assert result.gateway_primary is None
    assert result.fallback_chain == []
    assert result.providers == []


def test_best_effort_promotes_fallback_when_primary_unavailable():
    """best-effort：primary 不可用时，fallback-role Provider 可提升为 selected。"""
    reg = default_registry()
    reg.get("deepseek.chat.primary").enabled = False
    svc = LLMCapabilityService(settings=_settings(), router=CapabilityRouter(reg))
    result = svc.plan(LLMTaskType.QUERY_EXPANSION)
    assert result.gateway_primary == "openrouter.free.best_effort"
    assert result.fallback_chain == []
    assert result.providers == ["openrouter.free.best_effort"]
    assert "promoted_fallback" in result.route_reason


def test_source_tier_routes_to_ollama():
    """source_tier_classification → legacy 语义 provider = Ollama（provider-agnostic）。"""
    svc = build_llm_capability_service(_settings())
    result = svc.plan(LLMTaskType.SOURCE_TIER_CLASSIFICATION)
    assert result.gateway_primary == "ollama.source_tier.local"
    assert result.legacy_provider == "ollama"
    assert result.equivalent_primary is True
    assert result.fallback_chain == []  # strict
    assert "deepseek.chat.primary" in result.filtered  # 被 local_inference 过滤


def test_request_fingerprint_stable():
    svc = build_llm_capability_service(_settings())
    a = svc.plan(LLMTaskType.QUERY_EXPANSION).request_fingerprint
    b = svc.plan(LLMTaskType.QUERY_EXPANSION).request_fingerprint
    assert a == b
    c = svc.plan(LLMTaskType.SEARCH_PHRASE_GENERATION).request_fingerprint
    assert c != a  # 不同 task → 不同指纹


def test_plan_all_covers_all_tasks():
    svc = build_llm_capability_service(_settings())
    plans = svc.plan_all()
    assert set(plans) == {t.value for t in LLMTaskType}


def test_shadow_result_serializable():
    svc = build_llm_capability_service(_settings())
    d = svc.plan(LLMTaskType.STRUCTURED_DRAFT).to_dict()
    assert d["task_type"] == "structured_draft"
    assert d["policy"] == "strict"
    assert d["gateway_primary"] == "deepseek.chat.primary"
    assert "filtered" in d and "request_fingerprint" in d


def test_llm_routing_mode_shadow_when_enabled():
    assert llm_routing_mode(_settings()) == "shadow"


def test_llm_routing_mode_off_when_disabled():
    settings = Settings(_env_file=None, CAPABILITY_GATEWAY_ENABLED=False)
    assert llm_routing_mode(settings) == "off"
