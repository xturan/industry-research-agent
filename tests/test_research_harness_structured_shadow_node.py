"""C.2 — Structured Shadow Graph Node tests.

8 cases:
  1. flag OFF -> no-op, no namespace, formal output unchanged
  2. happy path -> status=completed, draft has sections/paragraphs, validation passes
  3. input filtering -> only approved claims + referenced evidence; no backfill leak
  4. non-interference OFF/ON -> main namespaces hash-identical
  5. node failure -> degraded, fail-open (editor1 not blocked)
  6. checkpoint recovery -> stable draft_id, no duplicate shadow draft
  7. unknown/blocked section -> only gap_descriptive
  8. advisory backfill isolation -> reads only the MAIN store
"""

from __future__ import annotations

import hashlib
import json

from packages.research_harness import real_nodes
from packages.research_harness.eval_persistence import (
    RunEvaluationStore,
)
from packages.research_harness.structured_draft import stable_draft_id


def _main_store() -> RunEvaluationStore:
    store = RunEvaluationStore("run")
    store.record_claim_slots([{
        "slot_id": "s1", "section_id": "sec", "criticality": "required",
        "min_evidence_items": 1, "min_raw_supporting_sources": 1,
        "field_requirements": {"mandatory": [], "any_of": ["operation_status"]},
        "source_obligations": {"required_families": ["government"],
                               "primary_source_required": True},
    }])
    store.record_search_event({
        "search_event_id": "se1", "run_id": "run", "slot_ids": ["s1"],
        "query": "q", "source_family": "government", "provider": "anysearch",
        "status": "completed", "result_count": 1, "accepted_source_ids": ["a"],
        "schema_version": "search_event_v1",
    })
    store.record_evidence_unit({
        "evidence_id": "ev1", "run_id": "run", "source_id": "a",
        "source_family": "government", "supports_slot_ids": ["s1"],
        "key_fields": {"operation_status": {"status": "present", "value": "投运"}},
        "key_field_extraction_status": "completed", "schema_version": "evidence_unit_v2",
    })
    store.record_evidence_unit({
        "evidence_id": "ev_unref", "run_id": "run", "source_id": "b",
        "source_family": "government", "supports_slot_ids": ["s1"],
        "key_fields": {"operation_status": {"status": "present", "value": "投运"}},
        "key_field_extraction_status": "completed", "schema_version": "evidence_unit_v2",
    })
    store.record_claim_card({
        "claim_id": "c1", "primary_slot_id": "s1", "slot_ids": ["s1"],
        "evidence_ids": ["ev1"], "claim_type": "factual",
        "epistemic_status": "supported", "assertion_level": "supported",
        "max_allowed_assertion_level": "confirmed",
        "approval_status": "approved", "limitations": ["未披露日均运营架次"],
        "text": "合肥低空物流项目已投入运营。",
        "idempotency_key": "claim:c1", "schema_version": "claim_card_v1",
    })
    store.record_claim_card({
        "claim_id": "c_pending", "primary_slot_id": "s1", "slot_ids": ["s1"],
        "evidence_ids": ["ev_unref"], "claim_type": "factual",
        "epistemic_status": "unsupported", "assertion_level": "mentioned",
        "max_allowed_assertion_level": "observed",
        "approval_status": "pending", "limitations": [],
        "text": "该项目投资额约1.2亿元。",
        "idempotency_key": "claim:c_pending", "schema_version": "claim_card_v1",
    })
    return store


def _state(store=None, *, with_backfill_shadow=False) -> dict:
    store = store or _main_store()
    state = {
        "run_id": "1", "query": "合肥低空物流",
        "evaluation_store": store.to_dict(),
        "research_gaps": [],
        "sources": [{"source_id": "a", "source_family": "government"}],
        "evidence": [{"evidence_id": "ev1", "source_id": "a"}],
        "claims": [{"claim_id": "c1"}],
        "final_report": {"report_markdown": "original"},
        "report_markdown": "original",
    }
    if with_backfill_shadow:
        # A fake advisory shadow store that MUST NOT leak into the writing input.
        shadow_store = RunEvaluationStore("run")
        shadow_store.record_claim_card({
            "claim_id": "c_backfill", "primary_slot_id": "s1", "slot_ids": ["s1"],
            "evidence_ids": ["ev_backfill"], "claim_type": "factual",
            "epistemic_status": "supported", "assertion_level": "confirmed",
            "max_allowed_assertion_level": "confirmed",
            "approval_status": "approved", "limitations": [],
            "text": "补搜产生的额外结论。",
            "idempotency_key": "claim:c_backfill", "schema_version": "claim_card_v1",
        })
        state["advisory_backfill"] = {"evaluation_store": shadow_store.to_dict()}
    return state


def _hash_state(state: dict) -> dict:
    out = {}
    for key in ("sources", "evidence", "claims", "final_report", "report_markdown"):
        out[key] = hashlib.sha256(
            json.dumps(state.get(key), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
    return out


def _enable():
    real_nodes.set_structured_shadow_override(enabled=True, mode="shadow")


def _disable():
    real_nodes.set_structured_shadow_override(enabled=None, mode=None)


# ── 1. flag OFF ─────────────────────────────────────────────────────────────

def test_flag_off_is_noop_and_does_not_add_namespace():
    _disable()
    state = _state()
    before = _hash_state(state)
    out = real_nodes.structured_shadow_editor1_provider_backed(state)
    assert out == {}
    assert "structured_draft_shadow" not in state
    assert _hash_state(state) == before


# ── 2. happy path ───────────────────────────────────────────────────────────

def test_happy_path_produces_shadow_draft():
    _enable()
    state = _state()
    out = real_nodes.structured_shadow_editor1_provider_backed(state)
    shadow = out["structured_draft_shadow"]
    assert shadow["status"] == "completed"
    assert shadow["draft"]["sections"]
    assert any(p["paragraph_role"] == "factual"
               for s in shadow["draft"]["sections"] for p in s["paragraphs"])
    assert shadow["validation_report"]["passed"] is True
    assert shadow["schema_version"] == "structured_draft_shadow_v1"
    _disable()


# ── 3. input filtering ──────────────────────────────────────────────────────

def test_input_filtering_only_approved_and_referenced():
    _enable()
    state = _state()
    out = real_nodes.structured_shadow_editor1_provider_backed(state)
    ei = out["structured_draft_shadow"]["editor1_input"]
    assert ei["approved_claim_ids"] == ["c1"]  # c_pending filtered
    assert ei["referenced_evidence_ids"] == ["ev1"]  # ev_unref filtered
    _disable()


# ── 4. non-interference OFF/ON ──────────────────────────────────────────────

def test_non_interference_off_on_main_namespaces_identical():
    off_state = _state()
    _disable()
    real_nodes.structured_shadow_editor1_provider_backed(off_state)
    off_hashes = _hash_state(off_state)

    on_state = _state()
    _enable()
    real_nodes.structured_shadow_editor1_provider_backed(on_state)
    on_hashes = _hash_state(on_state)

    assert on_hashes == off_hashes
    _disable()


# ── 5. node failure -> degraded, fail-open ──────────────────────────────────

def test_node_failure_degrades_fail_open():
    _enable()
    store = _main_store()
    # Inject a claim card without claim_id -> build_structured_shadow_draft raises
    store.claim_cards["bad"] = {"approval_status": "approved", "text": "x"}
    state = _state(store)
    out = real_nodes.structured_shadow_editor1_provider_backed(state)
    shadow = out["structured_draft_shadow"]
    assert shadow["status"] == "degraded"
    assert shadow["diagnostics"][0]["code"] == "STRUCTURED_DRAFT_SHADOW_FAILED"
    # fail-open: no error/decision key, main namespaces untouched
    assert "error" not in out and "decision" not in out
    assert _hash_state(state)["report_markdown"] == hashlib.sha256(
        json.dumps("original", sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    _disable()


# ── 6. checkpoint recovery (stable ID, no duplicate) ────────────────────────

def test_checkpoint_recovery_stable_id_and_no_duplicate():
    _enable()
    state = _state()
    out1 = real_nodes.structured_shadow_editor1_provider_backed(state)
    out2 = real_nodes.structured_shadow_editor1_provider_backed(state)
    assert out1 == out2  # single namespace, no accumulation
    d1 = out1["structured_draft_shadow"]["draft"]
    # stable, content-derived draft_id (no uuid randomness)
    expected = stable_draft_id(
        run_id="run", draft_version=1, claim_ids=["c1"],
        coverage_snapshot_id="cr",
    )
    assert d1["draft_id"] == expected
    # paragraph ids are stable too
    assert d1["sections"][0]["paragraphs"][0]["paragraph_id"]  # non-empty, stable
    _disable()


# ── 7. unknown/blocked section -> only gap_descriptive ─────────────────────

def test_unknown_section_produces_only_gap_descriptive():
    store = RunEvaluationStore("run")
    store.record_claim_slots([{
        "slot_id": "s1", "section_id": "sec", "criticality": "required",
        "min_evidence_items": 1, "min_raw_supporting_sources": 1,
        "field_requirements": {"mandatory": [], "any_of": []},
        "source_obligations": {"required_families": ["government"],
                               "primary_source_required": True},
    }])
    # NO search event -> not_evaluable -> section unknown
    store.record_claim_card({
        "claim_id": "c1", "primary_slot_id": "s1", "slot_ids": ["s1"],
        "evidence_ids": [], "claim_type": "factual",
        "epistemic_status": "unsupported", "assertion_level": "mentioned",
        "max_allowed_assertion_level": "observed",
        "approval_status": "approved", "limitations": [],
        "text": "该项目存在潜在影响。",
        "idempotency_key": "claim:c1", "schema_version": "claim_card_v1",
    })
    _enable()
    out = real_nodes.structured_shadow_editor1_provider_backed(_state(store))
    draft = out["structured_draft_shadow"]["draft"]
    assert draft["sections"][0]["readiness_at_write"] == "unknown"
    roles = {p["paragraph_role"] for p in draft["sections"][0]["paragraphs"]}
    assert roles == {"gap_descriptive"}
    # the approved claim is unused (cannot write a strong conclusion)
    assert "c1" in draft["unused_claim_ids"]
    _disable()


# ── 8. advisory backfill isolation ──────────────────────────────────────────

def test_advisory_backfill_shadow_evidence_never_leaks():
    _enable()
    state = _state(with_backfill_shadow=True)
    out = real_nodes.structured_shadow_editor1_provider_backed(state)
    ei = out["structured_draft_shadow"]["editor1_input"]
    # Only the MAIN store's approved claim enters; the backfill shadow claim does not.
    assert ei["approved_claim_ids"] == ["c1"]
    assert "c_backfill" not in ei["approved_claim_ids"]
    assert ei["referenced_evidence_ids"] == ["ev1"]
    # and the main store itself was never mutated by the node
    main_store = RunEvaluationStore.from_dict(state["evaluation_store"])
    assert "c_backfill" not in main_store.claim_cards
    _disable()
