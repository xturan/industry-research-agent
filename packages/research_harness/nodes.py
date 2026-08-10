from __future__ import annotations

from typing import Any

from packages.research_harness.context import sanitize_text
from packages.research_harness.real_nodes import (
    advisory_gap_backfill_provider_backed,
    build_evidence_provider_backed,
    chief_gate_provider_backed,
    collect_sources_provider_backed,
    editor1_draft_provider_backed,
    editor2_review_provider_backed,
    finalize_report_provider_backed,
    parse_sources_provider_backed,
    plan_task_provider_backed,
    score_sources_single_point,
    structured_shadow_editor1_provider_backed,
)
from packages.research_harness.retrieval_bridge import build_graph_retrieval_artifacts

PROCUREMENT_HINTS = (
    "\u4e2d\u6807",
    "\u91c7\u8d2d",
    "\u62db\u6807",
    "\u6295\u6807",
    "\u4ea4\u6613\u4e2d\u5fc3",
    "\u516c\u5171\u8d44\u6e90",
)

DEBUG_INVALID_EDITOR1 = "__force_invalid_editor1__"
DEBUG_INVALID_EDITOR2 = "__force_invalid_editor2__"
DEBUG_INVALID_VERIFIER = "__force_invalid_verifier__"
DEBUG_INVALID_GATE = "__force_invalid_gate__"
DEBUG_FAIL_PARSE = "__force_fail_parse__"


def advisory_gap_backfill(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    """B.3.3b shadow advisory backfill node (flag-gated, fail-open).

    Runs between build_claims and editor1_draft. Only writes the
    advisory_backfill namespace; never changes main sources/evidence/claims.
    """
    return advisory_gap_backfill_provider_backed(state, tool_session=tool_session)


def structured_shadow_editor1(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    """C.2 claim-constrained StructuredDraft shadow node (flag-gated, fail-open).

    Runs between advisory_gap_backfill and editor1_draft. Reads only the main
    evaluation store; writes only the structured_draft_shadow namespace.
    """
    return structured_shadow_editor1_provider_backed(state, tool_session=tool_session)


def plan_task(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    if _is_provider_backed(state):
        return plan_task_provider_backed(state, tool_session=tool_session)
    query = state["query"].strip()
    caliber_terms = [query, f"{query} policy", f"{query} project", f"{query} notice"]
    source_obligations = [
        {
            "obligation_id": "obl_policy_primary",
            "source_family": "policy_document",
            "required_for": "policy grounding",
            "min_required_evidence": 1,
        }
    ]
    if _needs_procurement_evidence(query):
        source_obligations.append(
            {
                "obligation_id": "obl_procurement_award",
                "source_family": "tender_procurement",
                "required_for": "procurement or award evidence",
                "min_required_evidence": 1,
            }
        )
    return {
        "plan": {
            "normalized_query": query,
            "research_dimensions": [
                {
                    "dimension_id": "d_policy",
                    "label": "policy framing",
                    "description": "official policy and implementation framing",
                    "caliber_terms": caliber_terms[:3],
                    "source_priority": "government",
                },
                {
                    "dimension_id": "d_execution",
                    "label": "execution evidence",
                    "description": "project, procurement, notice, and execution evidence",
                    "caliber_terms": caliber_terms[1:4],
                    "source_priority": "mixed",
                },
            ],
            "dimension_plan": [
                {
                    "dimension_id": "d_policy",
                    "dimension_type": "policy_regulation",
                    "research_question": f"What official policy supports {query}?",
                    "why_it_matters": "Policy grounding keeps the shadow plan auditable.",
                    "coverage_required": "Collect at least one official policy source.",
                    "expected_section_heading": "政策与监管",
                    "source_priority": "government",
                    "source_families": ["policy_document"],
                    "caliber_terms": caliber_terms[:3],
                },
                {
                    "dimension_id": "d_execution",
                    "dimension_type": "project_execution",
                    "research_question": (
                        "What project, procurement, or notice evidence shows "
                        f"execution for {query}?"
                    ),
                    "why_it_matters": "Execution evidence separates framing from actual rollout.",
                    "coverage_required": (
                        "Collect auditable project, procurement, or notice evidence."
                    ),
                    "expected_section_heading": "项目落地与执行状态",
                    "source_priority": "mixed",
                    "source_families": ["tender_procurement", "policy_document"],
                    "caliber_terms": caliber_terms[1:4],
                },
            ],
            "source_obligations": source_obligations,
            "search_rounds": [
                {
                    "round_number": 1,
                    "objective": "establish official policy baseline",
                    "search_phrases": caliber_terms[:2],
                    "expected_source_tier": "A",
                },
                {
                    "round_number": 2,
                    "objective": "augment execution evidence",
                    "search_phrases": caliber_terms[2:4],
                    "expected_source_tier": "B",
                },
            ][: state["max_rounds"]],
        }
    }


def collect_sources(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    if _is_provider_backed(state):
        return collect_sources_provider_backed(state, tool_session=tool_session)
    query = state["query"]
    loop_count = int(state.get("loop_count", 0))
    plan = state.get("plan", {})
    rounds = plan.get("search_rounds", [])
    phrases = rounds[0].get("search_phrases", [query]) if rounds else [query]
    sources = [
        {
            "source_id": "src_policy",
            "url": "https://www.gov.cn/policy/mock-policy.html",
            "title": "Official policy notice",
            "source_family": "policy_document",
            "search_phrase": phrases[0],
            "raw_text": (
                "[\u9996\u9875] \u6253\u5370 \u6536\u85cf javascript:void(0) "
                "Policy text: official support measures remain active."
            ),
        }
    ]
    if not _needs_procurement_evidence(query):
        sources.append(
            {
                "source_id": "src_local_notice",
                "url": "https://example.gov.cn/notice/mock-notice.html",
                "title": "Local implementation notice",
                "source_family": "local_official",
                "search_phrase": phrases[-1],
                "raw_text": "Local notice: project application and rollout continue.",
            }
        )
    elif loop_count >= 1:
        sources.append(
            {
                "source_id": "src_procurement",
                "url": "https://www.ggzy.gov.cn/award/mock-award.html",
                "title": "Public resource award notice",
                "source_family": "tender_procurement",
                "search_phrase": f"{query} award notice",
                "raw_text": "Award notice: the project completed evaluation and published result.",
            }
        )
    return {"sources": sources}


def parse_sources(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    if _is_provider_backed(state):
        result = parse_sources_provider_backed(state, tool_session=tool_session)
        # ── Chunk retrieval: provider-backed path must also run the bridge ──
        sources = list(result.get("sources", []) or state.get("sources", []))
        cleaned_sources = _prepare_sources_for_retrieval(sources)
        retrieval_artifacts = build_graph_retrieval_artifacts(
            query=str(state.get("query", "")),
            sources=cleaned_sources,
            plan=dict(state.get("plan", {})),
            query_requirements=dict(state.get("query_requirements", {})),
            run_id=int(state.get("run_id", 0) or 0) or None,
            session=getattr(tool_session, "db_session", None),
        )
        result["sources"] = cleaned_sources
        result.update(retrieval_artifacts)
        return result
    if _has_debug_flag(state["query"], DEBUG_FAIL_PARSE):
        raise RuntimeError("forced-parse-failure")
    sources = list(state.get("sources", []))
    cleaned_sources = _prepare_sources_for_retrieval(sources)
    retrieval_artifacts = build_graph_retrieval_artifacts(
        query=str(state.get("query", "")),
        sources=cleaned_sources,
        plan=dict(state.get("plan", {})),
        query_requirements=dict(state.get("query_requirements", {})),
        run_id=int(state.get("run_id", 0) or 0) or None,
        session=getattr(tool_session, "db_session", None),
    )
    return {"sources": cleaned_sources, **retrieval_artifacts}


def _prepare_sources_for_retrieval(
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Use full_text (not truncated raw_text) for chunk retrieval when available."""
    cleaned: list[dict[str, Any]] = []
    for source in sources:
        source_copy = dict(source)
        # Prefer full_text for chunking; fall back to raw_text
        retrieval_text = str(
            source_copy.get("full_text")
            or source_copy.get("raw_text")
            or ""
        )
        source_copy["raw_text"] = retrieval_text
        source_copy["clean_text"] = sanitize_text(retrieval_text)
        cleaned.append(source_copy)
    return cleaned


def score_sources(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    if _is_provider_backed(state):
        # G4 精简：单点评分（活代码），绕过字节码冻结评分器，修 R1 双算。
        return score_sources_single_point(state)
    scored_sources = []
    for source in state.get("sources", []):
        family = source.get("source_family")
        tier = "A" if family == "policy_document" else "B"
        freshness = 0.82 if family == "policy_document" else 0.78
        query_relevance = 0.72 if family == "policy_document" else 0.88
        credibility = 0.90 if tier == "A" else 0.78
        scored_sources.append(
            {
                **source,
                "source_quality_v2": {
                    "tier": tier,
                    "freshness_score": freshness,
                    "query_relevance": query_relevance,
                    "credibility_score": credibility,
                    "source_family_match": family
                    in {"policy_document", "tender_procurement"},
                    "evaluation_mode": "rule_only_shadow_v1",
                    "usage_role": "primary_support" if tier == "A" else "secondary_support",
                },
            }
        )
    return {"sources": scored_sources}


def build_evidence(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    if _is_provider_backed(state):
        return build_evidence_provider_backed(state, tool_session=tool_session)
    evidence = []
    for index, source in enumerate(state.get("sources", []), start=1):
        family = source.get("source_family", "")
        support_type = (
            "direct_support"
            if family == "tender_procurement"
            else "background_support"
        )
        evidence.append(
            {
                "evidence_id": f"ev_{index}",
                "source_id": source["source_id"],
                "source_url": source["url"],
                "summary": source.get("clean_text", "")[:120],
                "support_type": support_type,
                "support_strength": 0.86 if support_type == "direct_support" else 0.56,
                "specificity": (
                    "procurement_award_notice"
                    if support_type == "direct_support"
                    else "policy_statement"
                ),
                "limitations": (
                    []
                    if support_type == "direct_support"
                    else ["Supports policy framing only, not execution outcome."]
                ),
                "evaluator_mode": "rule_then_llm_if_needed",
            }
        )
    return {"evidence": evidence}


def editor1_draft(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    if _is_provider_backed(state):
        return editor1_draft_provider_backed(state, tool_session=tool_session)
    return _build_editor_draft_placeholder(state)


def editor2_review(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    if _is_provider_backed(state):
        return editor2_review_provider_backed(state, tool_session=tool_session)
    return {"review_issues": [], "decision": "PASS"}


def _build_editor_draft_placeholder(state: dict[str, Any]) -> dict[str, Any]:
    """shadow 路径：无 claim 时基于 evidence 生成简单草稿占位。"""
    evidence = list(state.get("evidence", []))
    sections = []
    if evidence:
        sections.append({
            "section_id": "s_overview",
            "title": "概览",
            "markdown_body": "\n\n".join(
                f"- {str(e.get('summary') or '')[:100]}" for e in evidence[:8]
            ),
            "paragraphs": [],
        })
    return {
        "draft_id": "draft_placeholder",
        "draft_version": 1,
        "report_markdown": "\n".join(f"## {s['title']}\n\n{s['markdown_body']}" for s in sections),
        "sections": sections,
    }


def chief_gate(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    if _is_provider_backed(state):
        return chief_gate_provider_backed(state, tool_session=tool_session)
    # shadow：同样按维度 evidence 覆盖度判定（chief_gate_provider_backed 是纯
    # 计算，不调 LLM），保证 shadow/provider 的 gate 语义一致。无 claim 时也
    # 不能无条件放行——覆盖不足 + 无补证预算必须 HUMAN_REVIEW。
    return chief_gate_provider_backed(state, tool_session=tool_session)


def human_review(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    """Human review terminal node: mark pending + persist gate context.

    Gate routed HUMAN_REVIEW here; the run stops and waits for a resume
    (human_review_action on the next request). No LLM call.
    """
    return {
        "pending_human_review": True,
        "human_review": {
            "pending": True,
            "status": "pending",
            "gate_reason": str(state.get("gate_reason") or ""),
            "required_actions": list(state.get("required_actions") or []),
            "supported_actions": ["approve", "add_evidence", "rewrite", "reject"],
            "blocking_issues": list(state.get("review_issues") or []),
            "draft_snapshot": (
                list(state.get("drafts") or [])[-1] if state.get("drafts") else {}
            ),
        },
        "decision": "HUMAN_REVIEW",
    }


def finalize_report(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    if _is_provider_backed(state):
        return finalize_report_provider_backed(state, tool_session=tool_session)
    claims = state.get("claims", [])
    executive_summary = "Shadow-mode graph run completed with structured contracts."
    report_preview = {
        "query": state["query"],
        "claim_count": len(claims),
        "source_count": len(state.get("sources", [])),
        "evidence_count": len(state.get("evidence", [])),
        "decision": state.get("decision"),
        "gate_reason": state.get("gate_reason"),
        "executive_summary": executive_summary,
    }
    return {"final_report": report_preview}


def _needs_procurement_evidence(query: str) -> bool:
    return any(token in query for token in PROCUREMENT_HINTS)


def _has_debug_flag(query: str, flag: str) -> bool:
    return flag in query


def _is_provider_backed(state: dict[str, Any]) -> bool:
    return state.get("strategy") == "provider_backed_v1"
