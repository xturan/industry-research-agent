"""Focused unit tests for ClaimCard (research-contract-refactor Phase A).

Covers the deterministic, additive ClaimCard fields added on top of existing
claim dicts in `real_nodes._annotate_claim_card`:

- slot_id (additive, empty when unknown)
- claim_type (fact/comparison/trend/causal/synthesis/risk/outlook/evidence_gap)
- epistemic_status (supported/supported_with_limitation/partially_supported/
  conflicted/unsupported/not_found)
- max_assertion_level (1..4)
- forbidden_assertion_levels (machine-readable)
- forbidden_expansions (NL guardrails for Editor1)

All classification is deterministic: the same input always yields the same
ClaimCard, with no LLM involved.
"""

from packages.research_harness.real_nodes import (
    _annotate_claim_card,
    _classify_claim_type,
    _compute_forbidden_assertion_levels,
    _compute_max_assertion_level,
    _enrich_claim_semantics,
    _locate_quote_in_source,
)


def _evidence(evidence_id: str, *, strength: float, source_id: str = "src_1") -> dict:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "source_ids": [source_id],
        "summary": f"evidence summary {evidence_id}",
        "support_type": "direct_support",
        "support_strength": strength,
        "limitations": [],
    }


def _claim(claim_id: str, text: str, *, evidence_ids, supported=True, limitations=None) -> dict:
    return {
        "claim_id": claim_id,
        "text": text,
        "supported": supported,
        "evidence_ids": list(evidence_ids),
        "claim_family": "policy_basis",
        "required_source_family": "official_policy",
        "limitations": list(limitations or []),
    }


# ── claim_type lexical classification ───────────────────────────────────────

def test_claim_type_each_canonical_value():
    cases = {
        "合肥GDP增速高于全国平均水平": "comparison",
        "合肥市2023年GDP同比增长8%": "trend",
        "由于政策推动，项目落地明显加速": "causal",
        "该项目仍存在较大的不确定性风险": "risk",
        "预计2025年二期工程将投产": "outlook",
        "总体来看，低空经济呈现加速发展态势": "synthesis",
        "公告显示公司披露了2023年年报数据": "fact",
        "未能找到该项目任何落地证据": "risk",  # evidence_gap overridden structurally in annotate
    }
    for text, expected in cases.items():
        assert _classify_claim_type(text) == expected, f"{text!r} -> {expected}"


def test_claim_type_fallback_is_fact():
    assert _classify_claim_type("这是一个无法归类的普通句子") == "fact"


# ── quoted_span raw-offset location ─────────────────────────────────────────

def test_locate_quote_raw_offset():
    source = {"full_text": "合肥市2023年低空经济规模达500亿元，同比增长8%。"}
    loc = _locate_quote_in_source("低空经济规模达500亿元", source)
    assert loc["offset_mode"] == "raw"
    assert source["full_text"][loc["quote_start"]:loc["quote_end"]] == "低空经济规模达500亿元"
    assert loc["quote_occurrence"] >= 1


def test_locate_quote_occurrence_for_repeated_span():
    source = {"full_text": "政策支持低空经济。政策支持低空经济再次强调。"}
    loc = _locate_quote_in_source("政策支持低空经济", source)
    assert loc["quote_occurrence"] == 1  # first occurrence
    assert loc["offset_mode"] == "raw"


def test_locate_quote_normalized_fallback():
    source = {"full_text": "合肥市 2023 年低空经济规模达 500 亿元。"}
    # raw text has spaces that the quote lacks -> normalized fallback
    loc = _locate_quote_in_source("合肥市2023年低空经济规模达500亿元", source)
    assert loc["offset_mode"] == "normalized"


def test_locate_quote_absent():
    loc = _locate_quote_in_source("编造的不存在引用", {"full_text": "完全不同的正文内容。"})
    assert loc["offset_mode"] == "none"
    assert loc["quote_start"] == -1


# ── max_assertion_level + forbidden levels ──────────────────────────────────

def test_max_assertion_level_strong_multi_source():
    eq = {
        "linked_evidence_count": 3,
        "linked_source_count": 3,
        "avg_support_strength": 0.8,
        "single_source_risk": False,
    }
    assert _compute_max_assertion_level(supported=True, evidence_quality=eq) == 4
    assert _compute_forbidden_assertion_levels(4) == []


def test_max_assertion_level_single_source_medium():
    eq = {
        "linked_evidence_count": 1,
        "linked_source_count": 1,
        "avg_support_strength": 0.55,
        "single_source_risk": True,
    }
    assert _compute_max_assertion_level(supported=True, evidence_quality=eq) == 2
    assert _compute_forbidden_assertion_levels(2) == ["level_3", "level_4"]


def test_max_assertion_level_unsupported_is_one():
    eq = {"linked_evidence_count": 0, "linked_source_count": 0, "avg_support_strength": 0.0}
    assert _compute_max_assertion_level(supported=False, evidence_quality=eq) == 1
    assert _compute_forbidden_assertion_levels(1) == ["level_2", "level_3", "level_4"]


# ── _annotate_claim_card end-to-end ─────────────────────────────────────────

def _annotated(claim: dict, evidence: list[dict]) -> dict:
    evidence_map = {str(e.get("evidence_id")): e for e in evidence}
    _annotate_claim_card(claim=claim, evidence_map=evidence_map)
    return claim


def test_strong_claim_card():
    claim = _claim("c1", "公告显示公司披露了2023年年报数据", evidence_ids=["ev_1", "ev_2"])
    evidence = [_evidence("ev_1", strength=0.8, source_id="a"),
                _evidence("ev_2", strength=0.7, source_id="b")]
    card = _annotated(claim, evidence)
    assert card["claim_type"] == "fact"
    assert card["epistemic_status"] == "supported"
    assert card["max_assertion_level"] == 4
    assert card["assertion_level_label"] == "strong_conclusion"
    assert card["forbidden_assertion_levels"] == []
    assert "slot_id" in card
    # Global editorial rules live in the contract writing_policy, not per-claim.
    assert card["forbidden_expansions"] == []
    assert card["primary_slot_id"] == ""
    assert card["slot_ids"] == []


def test_single_source_low_strength_card():
    claim = _claim("c2", "该企业在该领域具备一定优势", evidence_ids=["ev_1"])
    card = _annotated(claim, [_evidence("ev_1", strength=0.35, source_id="a")])
    assert card["epistemic_status"] == "supported_with_limitation"
    assert card["max_assertion_level"] <= 2
    assert "level_4" in card["forbidden_assertion_levels"]
    assert any("单一来源" in h for h in card["forbidden_expansions"])


def test_no_evidence_claim_is_unsupported_not_gap():
    # Review 2026-08-03: a claim with no evidence stays a claim (lexical
    # claim_type) with epistemic_status=unsupported; the research gap is a
    # separate object, not a claim_type.
    claim = _claim("c3", "合肥低空经济产业规模处于全国前列", evidence_ids=[])
    card = _annotated(claim, [])
    assert card["claim_type"] != "evidence_gap"
    assert card["epistemic_status"] == "unsupported"
    assert card["max_assertion_level"] == 1
    assert card["forbidden_assertion_levels"] == ["level_2", "level_3", "level_4"]


def test_conflicted_status_from_limitation():
    claim = _claim(
        "c4",
        "该项目已经正式签约落地",
        evidence_ids=["ev_1"],
        limitations=["不同口径数据存在矛盾，签约状态不一致"],
    )
    card = _annotated(claim, [_evidence("ev_1", strength=0.8, source_id="a")])
    assert card["epistemic_status"] == "conflicted"


def test_absence_claim_is_unsupported_without_coverage():
    # "未找到" is not self-evidently a fact: without a CoverageReport the claim
    # is unsupported (not not_found). The ResearchGap carries the honest wording.
    claim = _claim("c5", "检索范围内暂未发现该县区相关专项政策文件", evidence_ids=[])
    card = _annotated(claim, [])
    assert card["epistemic_status"] == "unsupported"


def test_unsupported_claim_with_partial_evidence():
    claim = _claim("c6", "该项目已经全面投产", evidence_ids=["ev_1"], supported=False)
    card = _annotated(claim, [_evidence("ev_1", strength=0.4, source_id="a")])
    assert card["epistemic_status"] == "partially_supported"
    assert any("不得断言项目已投运" in h for h in card["forbidden_expansions"])


def test_enrich_claim_semantics_injects_claim_card():
    claims = [_claim("c7", "由于政策推动，项目落地加速", evidence_ids=["ev_1"])]
    evidence = [_evidence("ev_1", strength=0.75, source_id="a")]
    enriched = _enrich_claim_semantics(claims=claims, evidence=evidence)
    card = enriched[0]
    assert card["claim_type"] == "causal"
    assert card["epistemic_status"] == "supported"
    assert card["max_assertion_level"] >= 3
    assert isinstance(card["forbidden_expansions"], list)
