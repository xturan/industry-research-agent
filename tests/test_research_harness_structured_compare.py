# ruff: noqa: E501
"""C.3.1 — Structured Compare tests.

12 cases:
  generate/parse 1-3, reference 4-6, writing boundary 7-10,
  compare non-interference 11-12, plus backfill-isolation regression.
"""

from __future__ import annotations

from packages.research_harness.eval_persistence import (
    RunEvaluationStore,
    build_evaluable_coverage_report,
)
from packages.research_harness.gap_retrieval import derive_gaps
from packages.research_harness.structured_compare import (
    SectionGenerationInput,
    build_section_inputs,
    generate_structured_section,
    parse_llm_section,
    run_structured_compare,
    select_section_examples,
    validate_llm_section,
)


def _store() -> RunEvaluationStore:
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
        "quoted_span": "2025年6月项目正式投运",
        "key_fields": {"operation_status": {"status": "present", "value": "投运"}},
        "key_field_extraction_status": "completed", "schema_version": "evidence_unit_v2",
    })
    store.record_claim_card({
        "claim_id": "c1", "primary_slot_id": "s1", "slot_ids": ["s1"],
        "evidence_ids": ["ev1"], "claim_type": "factual",
        "epistemic_status": "supported", "assertion_level": "supported",
        "max_allowed_assertion_level": "supported",
        "approval_status": "approved", "limitations": ["未披露日均运营架次"],
        "text": "合肥低空物流项目已投入运营。",
        "idempotency_key": "claim:c1", "schema_version": "claim_card_v1",
    })
    store.record_claim_card({
        "claim_id": "c_pending", "primary_slot_id": "s1", "slot_ids": ["s1"],
        "evidence_ids": [], "claim_type": "factual",
        "epistemic_status": "unsupported", "assertion_level": "mentioned",
        "max_allowed_assertion_level": "observed",
        "approval_status": "pending", "limitations": [],
        "text": "该项目投资额约1.2亿元。",
        "idempotency_key": "claim:c_pending", "schema_version": "claim_card_v1",
    })
    return store


def _section_input() -> SectionGenerationInput:
    return SectionGenerationInput(
        section_id="sec", title="项目进展", readiness="ready",
        allowed_claim_ids=("c1",),
        claim_cards=({
            "claim_id": "c1", "primary_slot_id": "s1", "slot_ids": ["s1"],
            "evidence_ids": ["ev1"], "max_allowed_assertion_level": "supported",
            "approval_status": "approved", "limitations": ["未披露日均运营架次"],
            "text": "合肥低空物流项目已投入运营。",
        },),
        referenced_evidence_units=({
            "evidence_id": "ev1", "quoted_span": "2025年6月项目正式投运",
            "key_fields": {"operation_status": {"status": "present", "value": "投运"}},
            "supports_slot_ids": ["s1"],
        },),
        unresolved_gap_ids=(),
    )


def _valid_section() -> dict:
    return {
        "section_id": "sec", "title": "项目进展",
        "paragraphs": [{
            "paragraph_role": "factual",
            "text": "公开资料显示合肥低空物流项目已投入运营。",
            "claim_ids": ["c1"], "evidence_ids": ["ev1"],
            "assertion_level": "supported", "limitations": ["未披露日均运营架次"],
            "numeric_mentions": [{"text": "2025年6月", "evidence_id": "ev1"}],
        }],
    }


class _SeqLLM:
    """Returns payloads in sequence; last one repeats."""

    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = 0

    def __call__(self, system_prompt, user_prompt):
        self.calls += 1
        if self.payloads:
            return self.payloads.pop(0)
        return self.payloads[-1] if self.payloads else None


# ── 1-3. generate / parse / retry ───────────────────────────────────────────

def test_valid_section_json_parses():
    draft = parse_llm_section(_valid_section(), section_id="sec")
    assert draft.section_id == "sec"
    assert draft.paragraphs[0].claim_ids == ["c1"]


def test_invalid_json_triggers_one_retry_then_succeeds():
    llm = _SeqLLM({"section_id": "WRONG", "title": "x", "paragraphs": []},
                  _valid_section())
    result = generate_structured_section(_section_input(), llm, max_retries=1)
    assert result.status == "ok"
    assert result.retry_count == 1
    assert llm.calls == 2


def test_second_failure_marks_validation_failed():
    # first: unparseable (wrong section_id); retry: parseable but invalid claim
    bad_but_parseable = _valid_section()
    bad_but_parseable["paragraphs"][0]["claim_ids"] = ["nope"]
    llm = _SeqLLM({"section_id": "WRONG", "title": "x", "paragraphs": []},
                  bad_but_parseable)
    result = generate_structured_section(_section_input(), llm, max_retries=1)
    assert result.status == "validation_failed"
    assert result.retry_count == 1
    assert llm.calls == 2  # initial + 1 retry


# ── 4-6. reference constraints ──────────────────────────────────────────────

def test_unknown_claim_id_rejected():
    bad = _valid_section()
    bad["paragraphs"][0]["claim_ids"] = ["nope"]
    issues = validate_llm_section(parse_llm_section(bad, section_id="sec"),
                                  _section_input())
    assert any(i.code == "claim_not_in_allowed_set" for i in issues)


def test_evidence_not_referenced_by_claim_rejected():
    # add a second evidence that IS allowed in the input, but c1 doesn't reference
    section_input = SectionGenerationInput(
        section_id="sec", title="x", readiness="ready",
        allowed_claim_ids=("c1",),
        claim_cards=_section_input().claim_cards,
        referenced_evidence_units=_section_input().referenced_evidence_units + ({
            "evidence_id": "ev2", "quoted_span": "官方公示 2025", "key_fields": {},
            "supports_slot_ids": ["s1"],
        },),
        unresolved_gap_ids=(),
    )
    bad = _valid_section()
    bad["paragraphs"][0]["evidence_ids"] = ["ev2"]  # exists but not referenced by c1
    issues = validate_llm_section(parse_llm_section(bad, section_id="sec"),
                                  section_input)
    assert any(i.code == "evidence_not_referenced_by_claim" for i in issues)


def test_factual_paragraph_without_evidence_rejected():
    bad = _valid_section()
    bad["paragraphs"][0]["evidence_ids"] = []
    issues = validate_llm_section(parse_llm_section(bad, section_id="sec"),
                                  _section_input())
    assert any(i.code == "factual_missing_evidence" for i in issues)


# ── 7-10. writing boundary ──────────────────────────────────────────────────

def test_assertion_escalation_rejected():
    bad = _valid_section()
    bad["paragraphs"][0]["assertion_level"] = "confirmed"  # c1 max = supported
    issues = validate_llm_section(parse_llm_section(bad, section_id="sec"),
                                  _section_input())
    assert any(i.code == "assertion_level_exceeded" for i in issues)


def test_limitation_dropped_rejected():
    bad = _valid_section()
    bad["paragraphs"][0]["limitations"] = []
    issues = validate_llm_section(parse_llm_section(bad, section_id="sec"),
                                  _section_input())
    assert any(i.code == "limitation_not_preserved" for i in issues)


def test_unknown_section_strong_conclusion_rejected():
    section_input = SectionGenerationInput(
        section_id="sec", title="x", readiness="unknown",
        allowed_claim_ids=("c1",),
        claim_cards=_section_input().claim_cards,
        referenced_evidence_units=_section_input().referenced_evidence_units,
        unresolved_gap_ids=(),
    )
    bad = _valid_section()  # factual supported paragraph
    issues = validate_llm_section(parse_llm_section(bad, section_id="sec"),
                                  section_input)
    assert any(i.code == "blocked_unknown_strong_conclusion" for i in issues)


def test_gap_written_as_negative_rejected():
    gap_section = {
        "section_id": "sec", "title": "x",
        "paragraphs": [{
            "paragraph_role": "gap_descriptive",
            "text": "相关项目尚未形成收入。",  # negative assertion forbidden
            "claim_ids": [], "evidence_ids": [],
            "assertion_level": "observed", "limitations": [],
        }],
    }
    issues = validate_llm_section(parse_llm_section(gap_section, section_id="sec"),
                                  _section_input())
    assert any(i.code == "gap_unapproved_negative_assertion" for i in issues)


# ── 11-12. compare non-interference ─────────────────────────────────────────

def test_structured_compare_keeps_legacy_as_formal_output():
    store = _store()
    report, gaps = build_evaluable_coverage_report(store), derive_gaps(
        build_evaluable_coverage_report(store), store
    )[0]
    legacy = "合肥低空物流项目已投入运营。"
    result = run_structured_compare(
        store=store, coverage_report=report, research_gaps=gaps,
        legacy_markdown=legacy, llm_call=_SeqLLM(_valid_section()), run_id="r1",
    )
    assert result["mode"] == "structured_compare"
    assert result["legacy_markdown"] == legacy  # formal output untouched
    assert result["structured_markdown"]  # side-by-side shadow produced
    # store not mutated by the compare run
    assert store.to_dict()["claim_cards"]["c1"]["approval_status"] == "approved"


def test_structured_failure_does_not_block_legacy():
    store = _store()
    report, gaps = build_evaluable_coverage_report(store), derive_gaps(
        build_evaluable_coverage_report(store), store
    )[0]
    legacy = "合肥低空物流项目已投入运营。"

    def boom(system, user):
        raise RuntimeError("llm down")

    result = run_structured_compare(
        store=store, coverage_report=report, research_gaps=gaps,
        legacy_markdown=legacy, llm_call=boom, run_id="r2",
    )
    # LLM failure -> section llm_failed -> fallback gap paragraph; legacy intact
    assert result["legacy_markdown"] == legacy
    assert result["comparison_report"]["structured_failed_section_count"] >= 1


# ── backfill isolation regression ───────────────────────────────────────────

def test_advisory_backfill_shadow_evidence_never_enters_editor1_input():
    store = _store()
    # an advisory shadow store that must never be read by the compare pipeline
    shadow = RunEvaluationStore("run")
    shadow.record_claim_card({
        "claim_id": "c_backfill", "primary_slot_id": "s1", "slot_ids": ["s1"],
        "evidence_ids": [], "claim_type": "factual",
        "epistemic_status": "supported", "assertion_level": "confirmed",
        "max_allowed_assertion_level": "confirmed",
        "approval_status": "approved", "limitations": [],
        "text": "补搜产生的额外结论。",
        "idempotency_key": "claim:c_backfill", "schema_version": "claim_card_v1",
    })
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    result = run_structured_compare(
        store=store, coverage_report=report, research_gaps=gaps,
        legacy_markdown="x", llm_call=_SeqLLM(_valid_section()), run_id="r3",
    )
    assert "c_backfill" not in result["editor1_input"]["approved_claim_ids"]
    assert result["editor1_input"]["approved_claim_ids"] == ["c1"]


# ── C.3.1 calibration: metric semantics + coverage contract ─────────────────

def _calibration_store() -> RunEvaluationStore:
    store = RunEvaluationStore("run")
    store.record_claim_slots([
        {"slot_id": "s1", "section_id": "sec", "criticality": "required",
         "min_evidence_items": 1, "min_raw_supporting_sources": 1,
         "field_requirements": {"mandatory": [], "any_of": ["operation_status"]},
         "source_obligations": {"required_families": ["government"],
                                "primary_source_required": True}},
        {"slot_id": "s2", "section_id": "sec", "criticality": "required",
         "min_evidence_items": 1, "min_raw_supporting_sources": 1,
         "field_requirements": {"mandatory": [], "any_of": ["amount"]},
         "source_obligations": {"required_families": ["government"],
                                "primary_source_required": True}},
    ])
    for sid in ("s1", "s2"):
        store.record_search_event({
            "search_event_id": f"se_{sid}", "run_id": "run", "slot_ids": [sid],
            "query": sid, "source_family": "government", "provider": "anysearch",
            "status": "completed", "result_count": 1,
            "accepted_source_ids": [f"a_{sid}"], "schema_version": "search_event_v1",
        })
    store.record_evidence_unit({
        "evidence_id": "ev1", "run_id": "run", "source_id": "a_s1",
        "source_family": "government", "supports_slot_ids": ["s1"],
        "quoted_span": "2025年6月正式投运", "quote_verification_status": "verified",
        "key_fields": {"operation_status": {"status": "present", "value": "投运"}},
        "key_field_extraction_status": "completed", "schema_version": "evidence_unit_v2",
    })
    store.record_evidence_unit({
        "evidence_id": "ev2", "run_id": "run", "source_id": "a_s2",
        "source_family": "government", "supports_slot_ids": ["s2"],
        "quoted_span": "投资金额1.2亿元", "quote_verification_status": "verified",
        "key_fields": {"amount": {"status": "present", "value": "1.2亿元"}},
        "key_field_extraction_status": "completed", "schema_version": "evidence_unit_v2",
    })
    store.record_claim_card({
        "claim_id": "c1", "primary_slot_id": "s1", "slot_ids": ["s1"],
        "evidence_ids": ["ev1"], "claim_type": "factual",
        "epistemic_status": "supported", "assertion_level": "supported",
        "max_allowed_assertion_level": "3",  # -> supported
        "approval_status": "approved", "limitations": ["未披露日均架次"],
        "text": "合肥低空物流项目已正式投运。",
        "idempotency_key": "claim:c1", "schema_version": "claim_card_v1",
    })
    store.record_claim_card({
        "claim_id": "c2", "primary_slot_id": "s2", "slot_ids": ["s2"],
        "evidence_ids": ["ev2"], "claim_type": "factual",
        "epistemic_status": "supported", "assertion_level": "supported",
        "max_allowed_assertion_level": "3",
        "approval_status": "approved", "limitations": [],
        "text": "项目投资金额约1.2亿元。",
        "idempotency_key": "claim:c2", "schema_version": "claim_card_v1",
    })
    store.record_claim_card({
        "claim_id": "c3", "primary_slot_id": "s2", "slot_ids": ["s2"],
        "evidence_ids": ["ev2"], "claim_type": "factual",
        "epistemic_status": "supported", "assertion_level": "observed",
        "max_allowed_assertion_level": "2",
        "approval_status": "approved", "limitations": [],
        "text": "项目资金来源为财政拨款。",
        "idempotency_key": "claim:c3", "schema_version": "claim_card_v1",
    })
    return store


def test_metrics_required_and_eligible_claim_usage():
    store = _calibration_store()
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)

    def llm(system, user):
        return {
            "section_id": "sec", "title": "项目",
            "paragraphs": [{
                "paragraph_role": "factual",
                "text": "项目已投运，投资约1.2亿元。",
                "claim_ids": ["c1", "c2"], "evidence_ids": ["ev1", "ev2"],
                "assertion_level": "supported",
                "limitations": ["未披露日均架次"], "numeric_mentions": [],
            }],
        }

    result = run_structured_compare(
        store=store, coverage_report=report, research_gaps=gaps,
        legacy_markdown="项目已投运", llm_call=llm, run_id="cal1",
    )
    cr = result["comparison_report"]
    # both required claims (c1, c2) used -> 1.0
    assert cr["required_claim_usage_rate"] == 1.0
    # eligible = c1,c2,c3 (ready section); c3 not used -> 2/3
    assert cr["eligible_approved_claim_usage_rate"] == round(2 / 3, 4)
    assert cr["paragraph_claim_mapping_rate"] == 1.0
    assert cr["paragraph_evidence_mapping_rate"] == 1.0


def test_required_claim_missing_is_rejected_by_validator():
    section_input = SectionGenerationInput(
        section_id="sec", title="x", readiness="ready",
        allowed_claim_ids=("c1", "c2"),
        required_claim_ids=("c2",),
        required_limitation_ids=("未披露日均架次",),
        claim_cards=(
            {"claim_id": "c1", "evidence_ids": ["ev1"],
             "max_allowed_assertion_level": "supported", "approval_status": "approved",
             "limitations": ["未披露日均架次"], "text": "x"},
            {"claim_id": "c2", "evidence_ids": ["ev2"],
             "max_allowed_assertion_level": "supported", "approval_status": "approved",
             "limitations": [], "text": "y"},
        ),
        referenced_evidence_units=(
            {"evidence_id": "ev1", "quoted_span": "投运", "key_fields": {}},
            {"evidence_id": "ev2", "quoted_span": "1.2亿", "key_fields": {}},
        ),
        unresolved_gap_ids=(),
    )
    bad = _valid_section()
    bad["paragraphs"][0]["claim_ids"] = ["c1"]  # misses required c2
    bad["paragraphs"][0]["limitations"] = []  # drops required limitation
    issues = validate_llm_section(parse_llm_section(bad, section_id="sec"), section_input)
    codes = {i.code for i in issues}
    assert "required_claim_missing" in codes
    assert "required_limitation_missing" in codes


def test_blocked_unknown_section_skips_llm():
    calls = []
    section_input = SectionGenerationInput(
        section_id="sec", title="x", readiness="unknown",
        allowed_claim_ids=(), unresolved_gap_ids=("gap_1",),
    )

    def llm(system, user):
        calls.append(system)
        raise AssertionError("llm must not be called for blocked/unknown")

    result = generate_structured_section(section_input, llm, max_retries=1)
    assert calls == []
    assert result.status == "ok"
    assert result.section_draft.paragraphs[0].paragraph_role == "gap_descriptive"
    assert "gap_1" in result.section_draft.paragraphs[0].text


def test_fewshot_selection_by_readiness():
    assert any("示例 A" in e for e in select_section_examples("ready"))
    partial = select_section_examples("partial")
    assert any("示例 B" in e for e in partial)
    assert any("示例 C" in e for e in partial)
    assert select_section_examples("blocked") == []
    assert select_section_examples("unknown") == []


def test_evidence_compressed_to_strongest_two_per_claim():
    from packages.research_harness.structured_draft import compile_editor1_input

    store = _calibration_store()
    # add a weak third evidence to c1 (unverified, no span)
    store.record_evidence_unit({
        "evidence_id": "ev_weak", "run_id": "run", "source_id": "a_s1",
        "source_family": "commercial_media", "supports_slot_ids": ["s1"],
        "quoted_span": "", "quote_verification_status": "not_verified",
        "key_fields": {}, "key_field_extraction_status": "not_extracted",
        "schema_version": "evidence_unit_v2",
    })
    store.claim_cards["c1"]["evidence_ids"] = ["ev1", "ev_weak"]
    report = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(report, store)
    ei = compile_editor1_input(store=store, coverage_report=report, research_gaps=gaps)
    inputs = build_section_inputs(ei, max_evidence_per_claim=1)
    # each claim should contribute at most 1 evidence brief -> ev_weak excluded
    ev_ids = {e["evidence_id"] for si in inputs for e in si.referenced_evidence_units}
    assert "ev_weak" not in ev_ids
    assert "ev1" in ev_ids
    assert "ev2" in ev_ids
