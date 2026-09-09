"""A2.6 — Entity-bound Critical Fact Conflict v2 (FactFrame) tests.

Covers: exact-hash skip, same-entity+scope amount conflict, attribute/scope
separation (总投资 vs 一期投资), multi-entity documents, status revision, and
unbound-fact non-conflict.
"""

from __future__ import annotations

from packages.research_harness.fact_frame import (
    bound_fact_conflict,
    critical_fact_conflict_v2,
    extract_entities,
    extract_fact_frames,
)


def test_exact_hash_skips_conflict():
    text = "合肥低空物流项目正式投运，总投资12亿元，一期投资10亿元。"
    assert critical_fact_conflict_v2(text, text) is False


def test_same_entity_same_scope_amount_conflict():
    a = "合肥低空物流项目总投资10亿元，一期投资5亿元。"
    b = "合肥低空物流项目总投资12亿元，一期投资5亿元。"
    conflicts = bound_fact_conflict(a, b)
    # total_investment conflict, but phase1 amount matches -> only one conflict
    assert len(conflicts) == 1
    assert conflicts[0]["attribute"] == "amount:total_investment"
    assert critical_fact_conflict_v2(a, b) is True


def test_total_vs_phase1_is_not_conflict():
    a = "合肥低空物流项目总投资12亿元。"
    b = "合肥低空物流项目一期投资10亿元。"
    # different amount attributes -> NOT a hard conflict
    assert bound_fact_conflict(a, b) == []
    assert critical_fact_conflict_v2(a, b) is False


def test_multi_entity_document_is_not_conflict():
    a = "项目A已投运，项目B正在建设，项目C计划开工，总投资50亿元。"
    b = "项目A已投运，项目B正在建设，项目D计划签约，总投资50亿元。"
    # C vs D are different entities; A/B status identical -> no bound conflict
    assert critical_fact_conflict_v2(a, b) is False


def test_same_entity_status_revision_is_conflict():
    # same entity, different lifecycle state -> revision conflict
    a = "合肥低空物流项目处于开工阶段。"
    b = "合肥低空物流项目已正式投运。"
    assert critical_fact_conflict_v2(a, b) is True


def test_unbound_fact_difference_is_not_hard_conflict():
    a = "某项目总投资10亿元，该项目已投运。"
    b = "某项目总投资12亿元，该项目已投运。"
    # entity names not extractable from these bare phrases -> UNBOUND -> not hard
    assert critical_fact_conflict_v2(a, b) is False


def test_entity_extraction():
    text = "《合肥市低空经济高质量发展方案》印发，合肥低空物流项目开工。"
    entities = extract_entities(text)
    # normalized forms (admin prefix + 项目/工程 suffix stripped for cross-page matching)
    assert "低空经济高质量发展方案" in entities
    assert "低空物流" in entities


def test_fact_frames_bound_to_entity():
    text = "合肥低空物流项目总投资10亿元，一期投资5亿元。"
    frames = extract_fact_frames(text)
    bound = [f for f in frames if f["entity"] != "UNBOUND"]
    assert any(f["attribute"] == "amount:total_investment" and f["value"] == 10.0 for f in bound)
    assert any(f["attribute"] == "amount:phase1_investment" and f["value"] == 5.0 for f in bound)
