"""Minimal L2 Pipeline Replay (research-contract-refactor Phase A, review 2026-08-03).

L2 fixes every external-unstable input: it starts from RECORDED parsed sources
(no query -> live search -> crawl) and runs only the deterministic pipeline
stages with recorded claims/evidence. No network, no live provider.

Cases:
- M03: policy + project (local_rollout / execution)
- C01: company disclosure
- K07: weak evidence / research gaps / deliberately-broken explicit mapping

The report's natural-language text is NOT asserted for equality; only structural
invariants are (schema completeness, citation integrity, quote authenticity,
claim constraints, draft mapping, determinism).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from packages.research_harness.real_nodes import (
    _annotate_draft_paragraph_mapping,
    _build_research_gaps,
    _enrich_claim_semantics,
    _locate_quote_in_source,
    _quote_in_source,
)
from packages.research_harness.research_contract import compile_research_contract

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "research_replay"

GAP_TYPES = {"no_reliable_evidence", "contradiction", "missing_fields", "not_found"}
ASSERTION_LABELS = {
    1: "mention_only",
    2: "fact_confirmed",
    3: "pattern_supported",
    4: "strong_conclusion",
}


def _load_fixture(qid: str) -> dict:
    path = FIXTURE_ROOT / qid / "fixture.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def no_network(monkeypatch):
    """L2 must never reach a live provider — any call_tooling_json raises."""
    import packages.research_harness.tooling.llm_agents as llm_agents

    def _forbidden_call(**kwargs):
        raise AssertionError("L2 replay must not call a live provider")

    monkeypatch.setattr(llm_agents, "call_tooling_json", _forbidden_call)


def _build_src_family_map(sources) -> dict:
    return {str(s["source_id"]): str(s.get("source_family") or "") for s in sources}


# ── per-case parametrized structural invariants ─────────────────────────────

@pytest.mark.parametrize("qid", ["M03", "C01", "K07"])
def test_l2_replay_schema_and_citation_invariants(qid, no_network):
    fx = _load_fixture(qid)
    plan, sources = fx["plan"], fx["sources"]
    evidence, claims = fx["evidence"], fx["claims"]
    draft = fx["draft"]

    # ── Contract Compiler ──
    contract = compile_research_contract(plan)
    assert contract["contract_version"] == "research_contract_v1"
    assert isinstance(contract["sections"], list) and contract["sections"]
    assert isinstance(contract["writing_policy"], dict)
    assert isinstance(contract["contract_warnings"], list)

    evidence_map = {str(e["evidence_id"]): e for e in evidence}
    src_family_by_id = _build_src_family_map(sources)

    # ── ClaimCard annotation ──
    enriched = _enrich_claim_semantics(
        claims=copy.deepcopy(claims), evidence=evidence
    )
    for card in enriched:
        assert card["claim_type"] in {
            "fact", "comparison", "trend", "causal", "synthesis", "risk", "outlook",
        }
        assert card["epistemic_status"] in {
            "supported", "supported_with_limitation", "partially_supported",
            "conflicted", "unsupported",
        }
        rank = int(card["max_assertion_level"])
        assert 1 <= rank <= 4
        assert card["assertion_level_label"] == ASSERTION_LABELS[rank]
        # forbidden levels must be exactly levels above the rank
        assert card["forbidden_assertion_levels"] == [
            f"level_{i}" for i in range(rank + 1, 5)
        ]
        # citation integrity: every claim evidence_id exists
        for eid in card.get("evidence_ids", []):
            assert str(eid) in evidence_map, (
                f"{qid}: claim {card['claim_id']} -> missing evidence {eid}"
            )
        # unsupported claims must cap at rank 1 (mention_only)
        if card["epistemic_status"] == "unsupported":
            assert rank == 1

    # ── ResearchGap ──
    gaps = _build_research_gaps(
        contract=contract, evidence=evidence, src_family_by_id=src_family_by_id
    )
    for gap in gaps:
        assert gap["gap_type"] in GAP_TYPES
        assert gap["reportability"] == "pending_coverage_review"
        assert gap["approved_report_expression"] is None
        assert gap["candidate_report_expression"]
        assert "公开渠道暂未发现" not in gap["candidate_report_expression"]

    # ── Paragraph mapping ──
    mapping = _annotate_draft_paragraph_mapping(
        sections=copy.deepcopy(draft["sections"]), claims=enriched, evidence=evidence
    )
    for section in mapping["sections"]:
        for para in section.get("paragraphs", []):
            assert "mapping_source" in para
            assert "mapping_validated" in para
            if para.get("mapping_validated"):
                # citation integrity holds for VALIDATED paragraphs
                for cid in para.get("claim_ids", []):
                    assert any(str(c["claim_id"]) == cid for c in enriched), (
                        f"{qid}: paragraph -> missing claim {cid}"
                    )
                for eid in para.get("evidence_ids", []):
                    assert str(eid) in evidence_map, f"{qid}: paragraph -> missing evidence {eid}"
            else:
                # non-validated mapping must carry explicit issues (K07 negative case)
                assert para.get("mapping_issues"), (
                    f"{qid}: non-validated paragraph must carry mapping_issues"
                )


# ── per-case semantic expectations ──────────────────────────────────────────

def test_l2_replay_m03_policy_and_execution_grounding(no_network):
    fx = _load_fixture("M03")
    contract = compile_research_contract(fx["plan"])
    policy_slot = next(
        s for sec in contract["sections"]
        for s in sec["claim_slots"]
        if s["slot_id"] == "dim_policy.official_policy.policy_basis"
    )
    assert policy_slot["required"] == "required"
    enriched = _enrich_claim_semantics(
        claims=copy.deepcopy(fx["claims"]), evidence=fx["evidence"]
    )
    for card in enriched:
        assert card["epistemic_status"] == "supported"
        assert card["max_assertion_level"] >= 3


def test_l2_replay_k07_weak_evidence_and_broken_mapping(no_network):
    fx = _load_fixture("K07")
    # unsupported claim -> mention_only
    enriched = _enrich_claim_semantics(
        claims=copy.deepcopy(fx["claims"]), evidence=fx["evidence"]
    )
    gap_card = next(c for c in enriched if c["claim_id"] == "claim_project_not_in_service")
    assert gap_card["epistemic_status"] == "unsupported"
    assert gap_card["max_assertion_level"] == 1
    assert gap_card["assertion_level_label"] == "mention_only"
    # no execution-required-family evidence -> a research gap exists
    src_family_by_id = _build_src_family_map(fx["sources"])
    contract = compile_research_contract(fx["plan"])
    gaps = _build_research_gaps(
        contract=contract, evidence=fx["evidence"], src_family_by_id=src_family_by_id
    )
    assert any(g["gap_type"] == "no_reliable_evidence" for g in gaps)
    # deliberately broken explicit mapping -> validation must flag ghost ids
    mapping = _annotate_draft_paragraph_mapping(
        sections=copy.deepcopy(fx["draft"]["sections"]), claims=enriched, evidence=fx["evidence"]
    )
    para = mapping["sections"][0]["paragraphs"][0]
    assert para["mapping_source"] == "editor_explicit"
    assert para["mapping_validated"] is False
    assert any("ghost_claim" in issue for issue in para["mapping_issues"])
    assert any("ghost_ev" in issue for issue in para["mapping_issues"])


# ── quote authenticity ──────────────────────────────────────────────────────

def test_l2_replay_quote_authenticity(no_network):
    for qid in ("M03", "C01", "K07"):
        fx = _load_fixture(qid)
        source_map = {str(s["source_id"]): s for s in fx["sources"]}
        for ev in fx["evidence"]:
            if not ev.get("quoted_span"):
                continue
            source = source_map.get(str(ev["source_id"]), {})
            assert _quote_in_source(ev["quoted_span"], source) is True, (
                f"{qid}: quoted_span not in source {ev['source_id']}"
            )
            loc = _locate_quote_in_source(ev["quoted_span"], source)
            assert loc["offset_mode"] != "none"
            if loc["offset_mode"] == "raw":
                text = " ".join(
                    [
                        str(source.get("full_text") or ""),
                        str(source.get("raw_text") or ""),
                        str(source.get("content_text") or ""),
                    ]
                )
                assert text[loc["quote_start"]:loc["quote_end"]] == ev["quoted_span"]


# ── determinism ─────────────────────────────────────────────────────────────

def test_l2_replay_determinism(no_network):
    for qid in ("M03", "C01", "K07"):
        fx = _load_fixture(qid)
        plan = fx["plan"]
        # contract determinism
        assert compile_research_contract(plan) == compile_research_contract(plan)
        # ClaimCard annotation determinism (deep-copy each run)
        run_a = _enrich_claim_semantics(claims=copy.deepcopy(fx["claims"]), evidence=fx["evidence"])
        run_b = _enrich_claim_semantics(claims=copy.deepcopy(fx["claims"]), evidence=fx["evidence"])
        assert run_a == run_b
        # paragraph parser determinism
        map_a = _annotate_draft_paragraph_mapping(
            sections=copy.deepcopy(fx["draft"]["sections"]), claims=run_a, evidence=fx["evidence"]
        )
        map_b = _annotate_draft_paragraph_mapping(
            sections=copy.deepcopy(fx["draft"]["sections"]), claims=run_b, evidence=fx["evidence"]
        )
        assert map_a == map_b
