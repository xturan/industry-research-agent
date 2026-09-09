"""G2.1 Capability Contract & Registry tests.

覆盖：query_expansion 的 primary/fallback 排序、structured_extraction 硬过滤、
search 双链、disabled/circuit/concurrency/quota 过滤、确定性排序稳定性。
G2.1 阶段不调用真实 API——只验证"Agent 能描述能力需求，Registry 能正确告诉
我们哪些 Provider 有资格执行"。
"""

from __future__ import annotations

from packages.capability_gateway import (
    CapabilityInstance,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityType,
    CircuitState,
    CostPolicy,
    RoutingPolicy,
    default_registry,
)

# ── 请求构造 helper ──────────────────────────────────────────────────────────

def _query_expansion() -> CapabilityRequest:
    return CapabilityRequest(
        capability=CapabilityType.LLM,
        task_type="query_expansion",
        requirements={"structured_output": False, "tool_calling": False,
                      "min_context_tokens": 8000},
        routing_policy=RoutingPolicy.BEST_EFFORT,
        cost_policy=CostPolicy.PREFER_LOW_COST,
    )


def _structured_extraction() -> CapabilityRequest:
    return CapabilityRequest(
        capability=CapabilityType.LLM,
        task_type="evidence_extraction",
        requirements={"structured_output": True, "json_schema": True,
                      "min_context_tokens": 32000},
        routing_policy=RoutingPolicy.STRICT,
        cost_policy=CostPolicy.QUALITY_FIRST,
    )


def _search() -> CapabilityRequest:
    return CapabilityRequest(
        capability=CapabilityType.SEARCH,
        task_type="research_discovery",
        requirements={"fresh_web": True, "max_results": 10},
        routing_policy=RoutingPolicy.FALLBACK_ALLOWED,
        cost_policy=CostPolicy.PREFER_LOW_COST,
    )


# ── 默认链路由 ───────────────────────────────────────────────────────────────

def test_default_registry_has_five_instances():
    reg = default_registry()
    ids = {i.instance_id for i in reg.all()}
    assert ids == {
        "deepseek.chat.primary",
        "openrouter.free.best_effort",
        "anysearch.primary",
        "tavily.fallback",
        "ollama.source_tier.local",
    }


def test_query_expansion_ranks_primary_before_fallback():
    reg = default_registry()
    dec = reg.select(_query_expansion())
    assert dec.selected is not None
    assert dec.selected.instance_id == "deepseek.chat.primary"
    assert [f.instance_id for f in dec.fallbacks] == ["openrouter.free.best_effort"]
    # query_expansion 不要求 structured_output → OpenRouter Free 也有资格
    assert "openrouter.free.best_effort" not in {i.instance_id for i, _ in dec.filtered_out}


def test_structured_extraction_filters_out_weak_fallback():
    reg = default_registry()
    dec = reg.select(_structured_extraction())
    assert dec.selected is not None
    assert dec.selected.instance_id == "deepseek.chat.primary"
    assert dec.selected.model == "deepseek-chat"
    # OpenRouter Free 被硬过滤：structured_output 缺失 + context 32000 不够
    filtered_ids = {i.instance_id for i, _ in dec.filtered_out}
    assert "openrouter.free.best_effort" in filtered_ids
    reasons = dec.rejected_by_id()
    reasons_txt = " | ".join(reasons.values())
    assert (
        "missing_feature:structured_output" in reasons_txt
        or "insufficient_capacity" in reasons_txt
    )
    # fallback 只有 DeepSeek 一个候选 → fallbacks 为空（严格策略下没有不合格的替补）
    assert dec.fallbacks == []


def test_search_anysearch_primary_tavily_fallback():
    reg = default_registry()
    dec = reg.select(_search())
    assert dec.selected is not None
    assert dec.selected.instance_id == "anysearch.primary"
    assert [f.instance_id for f in dec.fallbacks] == ["tavily.fallback"]


def test_search_falls_back_when_primary_circuit_open():
    reg = default_registry()
    reg.get("anysearch.primary").circuit = CircuitState.OPEN
    dec = reg.select(_search())
    assert dec.selected is not None
    assert dec.selected.instance_id == "tavily.fallback"
    # anysearch 被过滤原因
    assert "circuit_open" in dec.rejected_by_id().values()


def test_disabled_instance_filtered_out():
    reg = default_registry()
    reg.get("deepseek.chat.primary").enabled = False
    dec = reg.select(_query_expansion())
    # primary disabled → 只剩 OpenRouter Free
    assert dec.selected.instance_id == "openrouter.free.best_effort"
    assert dec.rejected_by_id()["deepseek.chat.primary"] == "disabled"


def test_concurrency_capacity_filters_primary():
    reg = default_registry()
    anysearch = reg.get("anysearch.primary")
    anysearch.limits["max_concurrency"] = 2
    anysearch.current_concurrency = 2  # 打满
    dec = reg.select(_search())
    assert dec.selected.instance_id == "tavily.fallback"
    assert dec.rejected_by_id()["anysearch.primary"] == "concurrency_capacity"


def test_quota_exhausted_filters_out():
    reg = default_registry()
    deepseek = reg.get("deepseek.chat.primary")
    deepseek.limits["quota_remaining"] = 0
    dec = reg.select(_query_expansion())
    assert dec.selected.instance_id == "openrouter.free.best_effort"
    assert dec.rejected_by_id()["deepseek.chat.primary"] == "quota_exhausted"


def test_capability_mismatch_filters_wrong_capability():
    reg = default_registry()
    # LLM 请求 → SEARCH 实例全部被过滤
    dec = reg.select(_query_expansion())
    for inst in reg.all():
        if inst.capability == CapabilityType.SEARCH:
            assert dec.rejected_by_id()[inst.instance_id].startswith("capability_mismatch")
    # SEARCH 请求 → LLM 实例全部被过滤
    dec2 = reg.select(_search())
    for inst in reg.all():
        if inst.capability == CapabilityType.LLM:
            assert dec2.rejected_by_id()[inst.instance_id].startswith("capability_mismatch")


def test_no_candidate_when_all_filtered():
    reg = default_registry()
    # 全 disable + 全 open → 无候选
    for inst in reg.all():
        inst.enabled = False
    dec = reg.select(_search())
    assert dec.selected is None
    assert dec.fallbacks == []
    assert len(dec.filtered_out) == 5


# ── 确定性排序 ───────────────────────────────────────────────────────────────

def test_deterministic_sort_primary_over_fallback_on_tie():
    reg = CapabilityRegistry()
    fallback = CapabilityInstance(
        instance_id="b.fallback", capability=CapabilityType.LLM,
        provider="x", roles=["fallback"], routing={"priority": 50},
        features={"max_context_tokens": 100000},
    )
    primary = CapabilityInstance(
        instance_id="a.primary", capability=CapabilityType.LLM,
        provider="x", roles=["primary"], routing={"priority": 50},
        features={"max_context_tokens": 100000},
    )
    reg.register_all([fallback, primary])
    dec = reg.select(_query_expansion())
    # 同 priority 时 primary 排在 fallback 前，且结果稳定
    assert dec.selected.instance_id == "a.primary"
    assert dec.ordered_candidates == [primary, fallback]


def test_cost_tier_breaks_tie_for_same_role_priority():
    reg = CapabilityRegistry()
    paid = CapabilityInstance(
        instance_id="paid", capability=CapabilityType.LLM, provider="x",
        roles=["primary"], routing={"priority": 50, "cost_tier": "paid"},
        features={"max_context_tokens": 100000},
    )
    free = CapabilityInstance(
        instance_id="free", capability=CapabilityType.LLM, provider="y",
        roles=["primary"], routing={"priority": 50, "cost_tier": "free"},
        features={"max_context_tokens": 100000},
    )
    reg.register_all([paid, free])
    dec = reg.select(_query_expansion())
    # 同 priority + 同 role → cost_tier free 优先（确定性）
    assert dec.selected.instance_id == "free"


def test_candidates_returns_same_order_as_selection():
    reg = default_registry()
    request = _search()
    assert reg.candidates(request)[0].instance_id == "anysearch.primary"
    assert reg.select(request).selected.instance_id == "anysearch.primary"
