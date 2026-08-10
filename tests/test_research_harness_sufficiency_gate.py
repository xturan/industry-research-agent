"""Phase B.1 Shadow CoverageReport Integration (research-contract-refactor).

Covers the B.1 spec: dual-track (raw vs duplicate-adjusted) Slot/Section/Report
readiness, distinct-content-as-proxy (never independent-source), search
execution recording, shadow ResearchGap eligibility (approved stays null),
no-critical-slot behavior, contradiction handling, and State non-interference.
"""

from __future__ import annotations

import copy

from packages.research_harness.research_contract import compile_research_contract
from packages.research_harness.sufficiency_gate import build_shadow_coverage_report


def _plan(**overrides) -> dict:
    plan = {
        "normalized_query": "合肥低空经济项目投运情况",
        "dimension_plan": [
            {
                "dimension_id": "dim_project",
                "dimension_type": "project_execution",
                "research_question": "合肥低空经济项目是否已投运？",
                "why_it_matters": "判断项目落地",
                "coverage_required": "覆盖项目状态与主体",
                "expected_section_heading": "项目投运",
                "source_priority": "B",
                "source_families": ["tender_procurement", "local_official"],
                "caliber_terms": ["低空经济"],
            }
        ],
        "source_obligations": [
            {"obligation_id": "obl", "source_family": "tender_procurement",
             "required_for": "项目", "min_required_evidence": 2}
        ],
        "query_requirements": {"needs_company_disclosure": False},
    }
    plan.update(overrides)
    return plan


def _src(sid: str, *, family: str = "tender_procurement", full_text: str = "") -> dict:
    return {"source_id": sid, "url": f"https://x.com/{sid}", "title": sid,
            "source_family": family, "full_text": full_text}


def _ev(eid: str, sid: str, *, family: str = "tender_procurement", **fields) -> dict:
    return {
        "evidence_id": eid, "source_id": sid, "source_ids": [sid],
        "source_family": family, "support_strength": 0.8, "limitations": [],
        **fields,
    }


BODY = "合肥低空经济项目2025年开工建设，投资约10亿元，预计2026年投运。"


def _report(contract, *, evidence=(), claims=(), sources=(), search_events=(), plan=None):
    return build_shadow_coverage_report({
        "contract": contract,
        "evidence": list(evidence),
        "claims": list(claims),
        "sources": list(sources),
        "search_events": list(search_events),
        "research_gaps": [],
        "plan": None,
    })


def _slot(report, slot_id: str) -> dict:
    return next(r for r in report["slots"] if r["slot_id"] == slot_id)


# ── B.1.2 slot deterministic evaluator ──────────────────────────────────────

def test_slot_reports_four_count_metrics():
    contract = compile_research_contract(_plan())
    # 3 sources, 2 identical content (reprint), 8 evidence from the 3 sources
    sources = [
        _src("a", full_text=BODY),
        _src("b", full_text=BODY),
        _src("c", full_text=BODY + "另有增量信息。"),
    ]
    evidence = [
        _ev("e1", "a"), _ev("e2", "a"), _ev("e3", "a"),
        _ev("e4", "b"), _ev("e5", "b"),
        _ev("e6", "c"), _ev("e7", "c"), _ev("e8", "c"),
    ]
    report = _report(contract, evidence=evidence, sources=sources)
    slot = _slot(report, "dim_project.tender_procurement.tender_evidence")
    assert slot["supporting_evidence_count"] == 8
    assert slot["raw_supporting_source_count"] == 3
    assert slot["distinct_supporting_content_count"] == 2


def test_slot_satisfied_to_insufficient_flip():
    plan = _plan()
    plan["source_obligations"] = [
        {"obligation_id": "obl", "source_family": "tender_procurement",
         "required_for": "项目", "min_required_evidence": 3}
    ]
    contract = compile_research_contract(plan)
    # raw 3 sources, but 2 identical -> distinct 2 < min 3
    sources = [
        _src("a", full_text=BODY),
        _src("b", full_text=BODY),
        _src("c", full_text=BODY + "另有增量信息。"),
    ]
    evidence = [
        _ev("e1", "a", stage="招标"), _ev("e2", "b", stage="招标"),
        _ev("e3", "c", stage="招标"),
    ]
    report = _report(
        contract, evidence=evidence, sources=sources,
        search_events=[{"target_source_family": "tender_procurement", "round": 1}],
    )
    slot = _slot(report, "dim_project.tender_procurement.tender_evidence")
    assert slot["raw_status"] == "satisfied"
    assert slot["duplicate_adjusted_status"] == "unsatisfied"
    assert slot["transition"] == "satisfied_to_unsatisfied"
    assert slot["content_distinctness_proxy_satisfied"] == "unsatisfied"
    assert slot["independence_requirement_status"] == "not_evaluable"


def test_slot_never_counts_evidence_references_as_sources():
    contract = compile_research_contract(_plan())
    # 8 evidence all from ONE source -> raw source count 1, never 8
    evidence = [_ev(f"e{i}", "a") for i in range(8)]
    report = _report(contract, evidence=evidence, sources=[_src("a", full_text=BODY)])
    slot = _slot(report, "dim_project.tender_procurement.tender_evidence")
    assert slot["supporting_evidence_count"] == 8
    assert slot["raw_supporting_source_count"] == 1
    assert slot["distinct_supporting_content_count"] == 1


# ── B.1.3 / B.1.4 section + report dual-track ──────────────────────────────

def test_no_multi_member_cluster_raw_equals_dup():
    contract = compile_research_contract(_plan())
    sources = [
        _src("a", full_text="合肥项目A内容一，政策支持持续加码，规模达500亿元。"),
        _src("b", full_text="合肥项目B内容二，市场关注度提升，规模达600亿元。"),
    ]
    report = _report(contract, sources=sources)
    slot = _slot(report, "dim_project.tender_procurement.tender_evidence")
    assert slot["raw_status"] == slot["duplicate_adjusted_status"]
    assert report["summary"]["would_change_decision"] is False


# ── B.1 critical gate ───────────────────────────────────────────────────────

def test_critical_gate_disabled_without_explicit_critical():
    report = _report(compile_research_contract(_plan()))
    assert report["critical_gate_enabled"] is False
    assert report["critical_gate"]["enabled"] is False
    assert report["critical_gate"]["reason"] == "NO_CRITICAL_SLOT_DECLARED"
    assert any(w["code"] == "NO_CRITICAL_SLOT_DECLARED" for w in report["contract_warnings"])


def test_critical_gate_enabled_computes_would_block_only():
    plan = _plan()
    plan["critical_slots"] = ["dim_project.tender_procurement.tender_evidence"]
    contract = compile_research_contract(plan)
    # family searched but no evidence -> critical slot unsatisfied -> would_block
    report = _report(
        contract, sources=[_src("a", full_text=BODY)],
        search_events=[{"target_source_family": "tender_procurement", "round": 1}],
    )
    assert report["critical_gate_enabled"] is True
    section = next(s for s in report["sections"] if s["section_id"] == "dim_project")
    assert section["duplicate_adjusted_status"] in {"partial", "blocked"}
    assert report["summary"]["would_block_if_duplicate_adjusted_enabled"] is True
    # critical gate only COMPUTES would_block; nothing actually blocks
    assert report["shadow_only"] is True


# ── B.1.6 contradiction ─────────────────────────────────────────────────────

def test_contradiction_makes_slot_insufficient_even_if_count_ok():
    contract = compile_research_contract(_plan())
    evidence = [
        _ev("e1", "a", limitations=["不同口径数据存在矛盾，状态不一致"]),
        _ev("e2", "b"),
    ]
    sources = [_src("a", full_text=BODY), _src("b", full_text=BODY + "增量")]
    report = _report(contract, evidence=evidence, sources=sources)
    slot = _slot(report, "dim_project.tender_procurement.tender_evidence")
    assert slot["contradiction_status"] == "unresolved"
    assert slot["raw_status"] == "unsatisfied"  # contradiction blocks regardless of count


# ── B.1.5 ResearchGap shadow eligibility ───────────────────────────────────

def test_research_gap_shadow_eligibility_never_approves():
    report = build_shadow_coverage_report({
        "plan": _plan(),
        "evidence": [],
        "claims": [],
        "sources": [],
        "search_events": [
            {"target_source_family": "tender_procurement", "round": 1, "error": None}
        ],
        "research_gaps": [
            {"gap_id": "gap_1",
             "slot_id": "dim_project.tender_procurement.tender_evidence",
             "source_family": "tender_procurement",
             "gap_type": "no_reliable_evidence",
             "candidate_report_expression": "当前已收集证据中未包含…",
             "reportability": "pending_coverage_review"}
        ],
    })
    gap = report["research_gaps"][0]
    assert gap["approved_report_expression"] is None
    assert gap["shadow_reportability"] in {"eligible_if_enabled", "not_evaluable"}
    if gap["shadow_reportability"] == "eligible_if_enabled":
        assert gap["shadow_approval_reasons"]
        assert gap["shadow_report_expression"]
    # the whole report never carries a decision
    assert "decision" not in report
    assert report["shadow_only"] is True


# ── B.1.8 state non-interference ────────────────────────────────────────────

def test_state_non_interference():
    plan = _plan()
    state = {
        "plan": plan,
        "evidence": [_ev("e1", "a"), _ev("e2", "b")],
        "claims": [{"claim_id": "c1", "evidence_ids": ["e1"],
                    "required_source_family": "tender_procurement"}],
        "sources": [_src("a", full_text=BODY), _src("b", full_text=BODY + "增量")],
        "search_events": [{"target_source_family": "tender_procurement", "round": 1}],
        "research_gaps": [],
    }
    snapshot = copy.deepcopy(state)
    report = build_shadow_coverage_report(state)
    assert state == snapshot  # claims/evidence/sources untouched
    assert report["shadow_only"] is True


# ── determinism ─────────────────────────────────────────────────────────────

def test_tiered_exact_vs_likely_reprint_count():
    contract = compile_research_contract(_plan())
    # 3 sources: 2 EXACT duplicates (same content) + 1 distinct
    srcs = [
        _src("a", full_text="合肥低空物流项目总投资12亿元，位于合肥高新区。"),
        _src("b", full_text="合肥低空物流项目总投资12亿元，位于合肥高新区。"),
        _src("c", full_text="合肥另一项目总投资5亿元，位于合肥经开区。"),
    ]
    report = _report(
        contract, sources=srcs,
        search_events=[{"target_source_family": "tender_procurement", "round": 1}],
    )
    slot = _slot(report, "dim_project.tender_procurement.tender_evidence")
    assert slot["raw_supporting_source_count"] == 3
    assert slot["exact_duplicate_adjusted_count"] == 2   # deterministic: exact dup collapsed
    assert slot["likely_reprint_adjusted_count"] == slot["distinct_supporting_content_count"]
    # advisory warning when likely reprint < raw
    codes = [w["code"] for w in report["warnings"]]
    assert "SOURCE_SUPPORT_MAY_SHARE_SAME_CONTENT_ORIGIN" in codes


def test_coverage_report_determinism():
    plan = _plan()
    state = {
        "plan": plan,
        "evidence": [_ev("e1", "a"), _ev("e2", "b")],
        "claims": [],
        "sources": [_src("a", full_text=BODY), _src("b", full_text=BODY + "增量")],
        "search_events": [],
        "research_gaps": [],
    }
    a = build_shadow_coverage_report(copy.deepcopy(state))
    b = build_shadow_coverage_report(copy.deepcopy(state))
    assert a == b


# ── B.1.8 recorded L2 replay (M03 fixture) ─────────────────────────────────

def test_l2_replay_coverage_report_on_m03_fixture():
    """Run the CoverageReport over the recorded M03 replay fixture (no network)."""
    import json
    from pathlib import Path
    fixture = (
        Path(__file__).parent / "fixtures" / "research_replay" / "M03" / "fixture.json"
    )
    fx = json.loads(fixture.read_text(encoding="utf-8"))
    state = {
        "plan": fx["plan"],
        "evidence": fx["evidence"],
        "claims": fx["claims"],
        "sources": fx["sources"],
        "search_events": [],
        "research_gaps": [],
    }
    report = build_shadow_coverage_report(copy.deepcopy(state))
    assert report["shadow_only"] is True
    assert report["report_version"] == "coverage_report_v1"
    assert report["critical_gate"]["enabled"] is False  # fixture has no critical_slots
    assert report["summary"]["raw_required_slot_coverage"] >= 0
    # every slot carries the dual-track fields + search execution
    for slot in report["slots"]:
        assert "raw_status" in slot and "duplicate_adjusted_status" in slot
        assert "supporting_evidence_count" in slot
        assert "raw_supporting_source_count" in slot
        assert "distinct_supporting_content_count" in slot
        assert "search_execution" in slot
        assert slot["independence_requirement_status"] == "not_evaluable"
    # determinism over the fixture
    b = build_shadow_coverage_report(copy.deepcopy(state))
    assert report == b
