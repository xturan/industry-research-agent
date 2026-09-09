from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.providers.base import JsonProviderResponse, ProviderCallMetadata
from packages.research_harness.plan_semantic import build_semantic_plan

# The planning pipeline is now exactly TWO LLM calls (intent planner + search
# builder). The old single "semantic plan assembly" call (_build_with_client) is
# DISABLED. These tests drive build_semantic_plan with a queue-based fake client
# that returns IntentPlan-shaped JSON on call #1 and SearchPlan-shaped JSON on
# call #2, and assert the assembled payload carries the research structure.


@dataclass(slots=True)
class _FakeJsonClient:
    responses: list[dict[str, Any]]
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    calls: list[dict[str, Any]] = field(default_factory=list)

    def generate_json(self, **kwargs: Any) -> JsonProviderResponse:  # noqa: ANN401
        self.calls.append(kwargs)
        payload = self.responses.pop(0)
        return JsonProviderResponse(
            provider=self.provider,
            model=self.model,
            content_text="{}",
            json_data=payload,
            metadata=ProviderCallMetadata(
                provider=self.provider,
                model=self.model,
                request_id="fake-plan-req",
                usage={"prompt_tokens": 1, "completion_tokens": 1},
                finish_reason="stop",
                response_ms=1.0,
                extra={},
            ),
            reasoning_content="should_not_persist",
        )


def _fallback_payload(query: str) -> dict[str, Any]:
    return {
        "plan": {
            "normalized_query": query,
            "research_dimensions": [
                {
                    "dimension_id": "d_policy",
                    "label": "official policy grounding",
                    "description": "policy documents",
                    "caliber_terms": [query, f"{query} 政策"],
                    "source_priority": "government",
                }
            ],
            "dimension_plan": [
                {
                    "dimension_id": "d_policy",
                    "dimension_type": "policy",
                    "research_question": f"What official policy supports {query}?",
                    "why_it_matters": "Policy grounding keeps the report auditable.",
                    "coverage_required": "Collect at least one official policy source.",
                    "expected_section_heading": "政策依据与口径",
                    "source_priority": "government",
                    "source_families": ["official_policy"],
                    "caliber_terms": [query, f"{query} 政策"],
                }
            ],
            "source_obligations": [
                {
                    "obligation_id": "obl_policy_primary",
                    "source_family": "official_policy",
                    "required_for": "official policy grounding",
                    "min_required_evidence": 1,
                }
            ],
            "search_rounds": [
                {
                    "round_number": 1,
                    "objective": "collect official policy",
                    "search_phrases": [query],
                    "include_domains": ["gov.cn"],
                    "expected_source_tier": "A",
                }
            ],
            "execution_mode": "provider_backed",
        },
        "query_requirements": {
            "needs_company_disclosure": False,
            "target_location": None,
            "is_location_sensitive": False,
        },
    }


_POLICY_DIM = {
    "dimension_id": "d_policy",
    "dimension_type": "policy",
    "research_question": "What official policy supports the query?",
    "why_it_matters": "Policy grounding keeps the report auditable.",
    "coverage_required": "Collect at least one official policy source.",
    "expected_section_heading": "政策依据与口径",
    "source_priority": "government",
    "source_families": ["official_policy"],
    "caliber_terms": ["低空经济 政策"],
}

_DISCLOSURE_DIM = {
    "dimension_id": "d_disclosure",
    "dimension_type": "disclosure",
    "research_question": "What disclosure evidence supports the query?",
    "why_it_matters": "Disclosure evidence reflects company-side statements.",
    "coverage_required": "Collect listed-company annual reports or exchange filings.",
    "expected_section_heading": "公司披露与年报口径",
    "source_priority": "enterprise",
    "source_families": ["company_disclosure"],
    "caliber_terms": ["低空经济 年报", "低空经济 披露"],
}


def _intent_payload(query: str, *, disclosure: bool = False) -> dict[str, Any]:
    """Build an IntentPlan-shaped dict for the (new) intent-planner call."""
    dims = [dict(_POLICY_DIM)]
    obls = [
        {
            "obligation_id": "obl_policy_primary",
            "source_family": "official_policy",
            "required_for": "official policy grounding",
            "min_required_evidence": 1,
        }
    ]
    if disclosure:
        dims.append(dict(_DISCLOSURE_DIM))
        obls.append(
            {
                "obligation_id": "obl_company_disclosure",
                "source_family": "company_disclosure",
                "required_for": "annual report or disclosure evidence",
                "min_required_evidence": 1,
            }
        )
    research_dimensions = [
        {
            "dimension_id": d["dimension_id"],
            "label": d["expected_section_heading"][:120],
            "description": d.get("why_it_matters", ""),
            "caliber_terms": list(d.get("caliber_terms", [])),
            "source_priority": d.get("source_priority", "mixed"),
        }
        for d in dims
    ]
    return {
        "normalized_query": query,
        "user_goal": {
            "goal_type": "evidence_verification",
            "goal_description": f"核查{query[:40]}的相关证据",
            "is_evidence_verification": True,
            "is_location_sensitive": False,
            "is_time_sensitive": False,
        },
        "explicit_constraints": {
            "time": [],
            "locations": [],
            "companies": [],
            "industries_or_topics": ["低空经济"],
            "required_source_style": [],
        },
        "query_levels": [],
        "evidence_needs": [
            {
                "name": "地方政策",
                "status": "required",
                "priority": "high",
                "why_needed": "query包含地方政策相关关键词",
                "what_to_verify": "验证地方政策相关证据",
                "suggested_caliber_terms": [],
                "source_type_preference": [],
                "noise_risk": "medium",
            }
        ],
        "expansion_policy": {
            "should_expand_topic_terms": True,
            "should_expand_location_levels": False,
            "should_expand_company_terms": False,
            "should_expand_project_terms": True,
            "expansion_limits": "",
        },
        "search_budget_advice": {
            "recommended_rounds": 3,
            "recommended_phrases_per_round": 4,
            "must_cover_original_query": True,
            "original_query_anchor_ratio": "20%-30%",
        },
        "caliber_notes": ["test_intent"],
        "research_dimensions": research_dimensions,
        "dimension_plan": dims,
        "source_obligations": obls,
        "query_requirements": {
            "needs_company_disclosure": disclosure,
            "target_location": None,
            "is_location_sensitive": False,
        },
    }


def _search_payload(query: str) -> dict[str, Any]:
    """Build a SearchPlan-shaped dict for the search-builder call."""
    return {
        "search_strategy_summary": {
            "original_query": query,
            "normalized_query": query,
            "total_rounds": 2,
            "total_phrases": 5,
            "anchor_phrase_count": 1,
            "non_anchor_phrase_count": 4,
        },
        "anchor_phrases": [
            {"phrase": query, "anchor_type": "original_query", "reason": "保留原始查询"}
        ],
        "search_groups": [
            {
                "group_id": "G1",
                "group_name": "政策搜索组",
                "dominant_intent": "检索政策",
                "target_evidence_need": "地方政策",
                "priority": "high",
                "target_level": "",
                "source_type_preference": [],
                "required_source_family": "official_policy",
                "include_domains": ["gov.cn"],
                "search_phrases": [
                    {
                        "phrase": f"{query} 政策",
                        "phrase_type": "evidence_specific",
                        "intent": "检索官方政策",
                        "reason": "test",
                    }
                ],
            }
        ],
        "deferred_search_ideas": [],
        "quality_checks": {
            "has_original_query_anchor": True,
            "has_normalized_query_anchor": False,
            "avoids_suffix_only_variants": True,
            "each_group_has_single_dominant_intent": True,
            "does_not_expand_all_possible_directions": True,
        },
    }


def test_semantic_plan_makes_exactly_two_llm_calls() -> None:
    query = "2025年低空经济上市公司年报披露与官方政策证据"
    client = _FakeJsonClient(
        [_intent_payload(query, disclosure=True), _search_payload(query)]
    )
    result = build_semantic_plan(
        query=query,
        fallback_payload=_fallback_payload(query),
        client=client,
    )

    # The old "semantic plan assembly" call must never fire: exactly 2 LLM calls.
    assert len(client.calls) == 2
    assert result.metadata["planner_stage"] == "caliber_only"
    assert result.metadata["planner_mode"] == "semantic_provider"
    assert result.metadata["deterministic_fallback"] is False
    assert "研究查询意图识别专家" in client.calls[0]["system_prompt"]
    assert "搜索词构建专家" in client.calls[1]["system_prompt"]


def test_semantic_plan_accepts_valid_intent_structure() -> None:
    query = "2025年低空经济上市公司年报披露与官方政策证据"
    client = _FakeJsonClient(
        [_intent_payload(query, disclosure=True), _search_payload(query)]
    )
    result = build_semantic_plan(
        query=query,
        fallback_payload=_fallback_payload(query),
        client=client,
    )

    assert result.metadata["planner_mode"] == "semantic_provider"
    assert result.metadata["deterministic_fallback"] is False
    obligations = result.payload["plan"]["source_obligations"]
    assert result.payload["plan"]["dimension_plan"]
    assert any(item["source_family"] == "company_disclosure" for item in obligations)
    assert result.payload["query_requirements"]["needs_company_disclosure"] is True
    # search_rounds are derived from the search builder's search_groups.
    assert result.payload["plan"]["search_rounds"]


def test_semantic_plan_repairs_invalid_schema_shapes() -> None:
    query = "2025年合肥低空经济地方政策项目公示官方来源"
    invalid_intent = {
        "normalized_query": query,
        "research_dimensions": "not-a-list",
        "source_obligations": "not-a-list",
        "query_requirements": "not-a-dict",
    }
    client = _FakeJsonClient([invalid_intent, _search_payload(query)])

    result = build_semantic_plan(
        query=query,
        fallback_payload=_fallback_payload(query),
        client=client,
    )

    # The always-on floor fills the malformed structure from the deterministic
    # fallback, so the payload still validates and carries structure.
    assert result.metadata["reason"] in {
        "semantic_plan_repaired",
        "semantic_plan_accepted",
    }
    assert result.payload["plan"]["normalized_query"] == query
    assert result.payload["plan"]["dimension_plan"]
    assert result.payload["plan"]["source_obligations"]


def test_semantic_plan_repairs_partial_payload() -> None:
    query = "2025年低空经济上市公司年报披露与官方政策证据"
    intent = _intent_payload(query)
    # Keep only the disclosure structure; no query_requirements.
    intent["dimension_plan"] = [dict(_DISCLOSURE_DIM)]
    intent["research_dimensions"] = [
        {
            "dimension_id": "d_disclosure",
            "label": "上市公司披露维度",
            "description": "official annual report or disclosure evidence",
            "caliber_terms": ["低空经济 年报"],
            "source_priority": "enterprise",
        }
    ]
    intent["source_obligations"] = [
        {
            "obligation_id": "obl_company_disclosure",
            "source_family": "company_disclosure",
            "required_for": "annual report or disclosure evidence",
            "min_required_evidence": 1,
        }
    ]
    intent["query_requirements"] = {"needs_company_disclosure": True}
    client = _FakeJsonClient([intent, _search_payload(query)])

    result = build_semantic_plan(
        query=query,
        fallback_payload=_fallback_payload(query),
        client=client,
    )

    assert result.metadata["reason"] in {
        "semantic_plan_accepted",
        "semantic_plan_repaired",
    }
    assert result.payload["plan"]["research_dimensions"]
    assert result.payload["plan"]["dimension_plan"]
    assert any(
        item["source_family"] == "company_disclosure"
        for item in result.payload["plan"]["source_obligations"]
    )


def test_semantic_plan_replan_context_reaches_intent_planner() -> None:
    query = "2025年低空经济上市公司年报披露与官方政策证据"
    intent = _intent_payload(query, disclosure=True)
    replan_request = {
        "reason": "chief_gate_add_evidence",
        "execution_term_hints": [f"{query} cninfo", f"{query} 交易所公告"],
    }
    client = _FakeJsonClient([intent, _search_payload(query)])

    result = build_semantic_plan(
        query=query,
        fallback_payload=_fallback_payload(query),
        client=client,
        replan_request=replan_request,
    )

    assert result.metadata["planner_mode"] == "semantic_provider"
    assert '"reason": "chief_gate_add_evidence"' in client.calls[0]["user_prompt"]
    assert result.payload["query_requirements"]["needs_company_disclosure"] is True
    assert result.payload["plan"]["source_obligations"]


def test_semantic_plan_disabled_caliber_returns_fallback_without_llm() -> None:
    query = "2025年合肥低空经济地方政策项目公示官方来源"
    client = _FakeJsonClient([_intent_payload(query), _search_payload(query)])

    result = build_semantic_plan(
        query=query,
        fallback_payload=_fallback_payload(query),
        client=client,
        enable_caliber_expansion=False,
    )

    assert client.calls == []
    assert result.payload == _fallback_payload(query)
    assert result.metadata["planner_mode"] == "deterministic_fallback"
    assert result.metadata["reason"] == "caliber_expansion_disabled"


def test_semantic_plan_keeps_fallback_disclosure_requirement_when_semantic_omits_it() -> None:
    query = "2025年低空经济上市公司年报披露与官方政策证据"
    # Intent omits disclosure; the bytecode fallback carries it.
    intent = _intent_payload(query, disclosure=False)
    fallback = _fallback_payload(query)
    fallback["plan"]["dimension_plan"] = [
        dict(_POLICY_DIM),
        dict(_DISCLOSURE_DIM),
    ]
    fallback["plan"]["research_dimensions"] = [
        {
            "dimension_id": "d_policy",
            "label": "政策依据维度",
            "description": "policy documents",
            "caliber_terms": [query],
            "source_priority": "government",
        },
        {
            "dimension_id": "d_disclosure",
            "label": "上市公司披露维度",
            "description": "annual report or disclosure evidence",
            "caliber_terms": [f"{query} 年报"],
            "source_priority": "enterprise",
        },
    ]
    fallback["plan"]["source_obligations"] = [
        {
            "obligation_id": "obl_policy_primary",
            "source_family": "official_policy",
            "required_for": "official policy grounding",
            "min_required_evidence": 1,
        },
        {
            "obligation_id": "obl_company_disclosure",
            "source_family": "company_disclosure",
            "required_for": "annual report or disclosure evidence",
            "min_required_evidence": 1,
        },
    ]
    fallback["query_requirements"] = {
        "needs_company_disclosure": True,
        "target_location": None,
        "is_location_sensitive": False,
    }
    client = _FakeJsonClient([intent, _search_payload(query)])

    result = build_semantic_plan(
        query=query,
        fallback_payload=fallback,
        client=client,
    )

    assert result.payload["query_requirements"]["needs_company_disclosure"] is True
    assert any(
        item["dimension_type"] == "disclosure"
        for item in result.payload["plan"]["dimension_plan"]
    )
    assert any(
        item["source_family"] == "company_disclosure"
        for item in result.payload["plan"]["source_obligations"]
    )


def test_enrich_round_phrases_replaces_query_variants_with_dimension_terms():
    """query 变体 search_phrases 应被 target_dimensions 的定向词替换（采集层修复）。"""
    from packages.research_harness.plan_semantic import _enrich_round_phrases

    query = (
        "低空经济中央政策是否进入规模化落地阶段？"
        "请验证空域改革、适航认证、基础设施、地方试点和企业订单。"
    )
    rounds = [
        {
            "round_number": 1,
            "search_phrases": [f"{query} 重复变体1", f"{query} 重复变体2"],
            "target_dimensions": ["project_execution"],
        },
    ]
    dimension_plan = [{
        "dimension_id": "project_execution",
        "dimension_type": "project_execution",
        "caliber_terms": ["低空经济项目", "试点", "基础设施"],
        "search_key_fields": [],
    }]
    enriched = _enrich_round_phrases(rounds, dimension_plan, query)
    phrases = enriched[0]["search_phrases"]
    joined = " ".join(phrases)
    # 维度定向词进来了
    assert "低空经济项目" in joined
    # query 变体被替换掉（不再含整句 query）
    assert not any(query in p for p in phrases)
    assert len(phrases) <= 6


def test_dim_search_terms_prefers_evidence_type_fields():
    """search_key_fields 里优先取有 _SEARCH_FIELD_TERMS 映射的证据类型字段（招标→中标）。"""
    from packages.research_harness.plan_semantic import _dim_search_terms

    dim = {
        "caliber_terms": [],  # 空的 caliber → 走 key_fields
        "search_key_fields": ["项目名称", "项目主体", "招标状态", "中标单位", "投资金额"],
    }
    terms = _dim_search_terms(dim, "低空经济")
    joined = " ".join(terms)
    assert "招标 中标" in joined  # 有映射的证据类型字段优先
    assert "项目名称" in joined  # 再补原始字段


def test_ensure_base_dimension_rounds_covers_all_10_base_dims():
    """收口 ensure_base_dimension_rounds 必须为未被覆盖的基础维度补搜索轮。"""
    from packages.research_harness import research_taxonomy as rt
    from packages.research_harness.plan_semantic import (
        _enrich_round_phrases,
        ensure_base_dimension_rounds,
    )

    query = "半导体设备国产替代是否已转化为订单收入？请检查招投标、中标、客户验证、收入。"
    # 只有一个轮：project_execution（模拟 LLM 只覆盖一个基础维度）
    rounds = [{
        "round_number": 1,
        "search_phrases": [query],
        "target_dimensions": ["project_execution"],
    }]
    dimension_plan = [
        {"dimension_id": dtype, "dimension_type": dtype, "caliber_terms": []}
        for dtype in rt.BASE_DIMENSIONS
    ]
    out = ensure_base_dimension_rounds(rounds, dimension_plan, query)
    covered = set()
    for r in out:
        for t in (r.get("target_dimensions") or []):
            covered.add(str(t))
    for dtype in rt.BASE_DIMENSIONS:
        assert (f"d_{dtype}" in covered) or (dtype in covered), f"missing base dim: {dtype}"
    # 新轮短语经 enrichment 后是维度定向、紧凑的（不含整句 query）
    enriched = _enrich_round_phrases(out, dimension_plan, query)
    for r in enriched:
        for p in (r.get("search_phrases") or []):
            assert len(str(p)) < 60, f"phrase not compact: {p}"
