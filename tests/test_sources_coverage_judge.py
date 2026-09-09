from __future__ import annotations

from packages.sources.coverage_judge import (
    CoverageBudgetState,
    LaneRoundMetrics,
    decide_round_transition,
    judge_lane_sufficiency,
)
from packages.sources.retrieval_plan import (
    CoverageLane,
    CoverageLanePlan,
    DomainStrategy,
    ExecutionBucket,
    LaneSuccessCriteria,
    SourceIntent,
    StopConditions,
)


def _build_lane(*, lane_id: CoverageLane, required: bool = True) -> CoverageLanePlan:
    return CoverageLanePlan(
        lane_id=lane_id,
        required=required,
        priority=90,
        source_intents=[SourceIntent.PROVINCE_GOVERNMENT],
        execution_bucket=ExecutionBucket.SEARCH_ASSISTED_SOURCES,
        domain_strategy=DomainStrategy.REGION_OFFICIAL_DOMAINS_ONLY,
        search_phrases=["广东 人形机器人 政策"],
        exact_phrases=[],
        negative_terms=[],
        allowed_domains=["gd.gov.cn"],
        success_criteria=LaneSuccessCriteria(
            min_accepted_documents=1,
            must_match_region=True,
            must_match_theme=True,
            must_match_source_role=True,
        ),
        fallback_ladder=["province_government_portal"],
    )


def test_round1_stops_when_required_lane_is_sufficient() -> None:
    lane = _build_lane(lane_id=CoverageLane.PROVINCIAL_POLICY_ROLLOUT, required=True)
    metrics = LaneRoundMetrics(
        accepted_candidate_count=1,
        accepted_document_count=1,
        rejected_reason_codes=[],
        local_claim_allowed=True,
        parent_evidence_only=False,
    )
    budget = CoverageBudgetState(
        max_search_credits=3,
        used_search_credits=1,
        max_candidates=3,
        used_candidates=1,
        max_extractions=2,
        used_extractions=1,
    )
    judgment = judge_lane_sufficiency(
        lane_plan=lane,
        metrics=metrics,
        budget_state=budget,
    )

    transition = decide_round_transition(
        lane_plan=lane,
        round_index=1,
        max_rounds=3,
        judgment=judgment,
        stop_conditions=StopConditions(),
        supplemental_or_fallback_lane=False,
    )

    assert judgment.sufficient is True
    assert transition.decision == "stop"
    assert transition.reason_code == "required_lane_sufficient"
    assert transition.next_round is None


def test_round2_is_required_lane_only() -> None:
    required_lane = _build_lane(
        lane_id=CoverageLane.PROVINCIAL_POLICY_ROLLOUT,
        required=True,
    )
    optional_lane = _build_lane(
        lane_id=CoverageLane.NATIONAL_POLICY_DIRECTION,
        required=False,
    )
    insufficient_metrics = LaneRoundMetrics(
        accepted_candidate_count=0,
        accepted_document_count=0,
        rejected_reason_codes=["off_domain_candidate"],
        local_claim_allowed=False,
        parent_evidence_only=False,
    )
    budget = CoverageBudgetState(
        max_search_credits=6,
        used_search_credits=1,
        max_candidates=3,
        used_candidates=0,
        max_extractions=2,
        used_extractions=0,
    )

    required_transition = decide_round_transition(
        lane_plan=required_lane,
        round_index=1,
        max_rounds=3,
        judgment=judge_lane_sufficiency(
            lane_plan=required_lane,
            metrics=insufficient_metrics,
            budget_state=budget,
        ),
        stop_conditions=StopConditions(),
        supplemental_or_fallback_lane=False,
    )
    optional_transition = decide_round_transition(
        lane_plan=optional_lane,
        round_index=1,
        max_rounds=3,
        judgment=judge_lane_sufficiency(
            lane_plan=optional_lane,
            metrics=insufficient_metrics,
            budget_state=budget,
        ),
        stop_conditions=StopConditions(),
        supplemental_or_fallback_lane=False,
    )

    assert required_transition.decision == "continue"
    assert required_transition.next_round == 2
    assert required_transition.reason_code == "required_lane_gap_needs_round2"
    assert required_transition.domain_widening_blocked is True

    assert optional_transition.decision == "stop"
    assert optional_transition.reason_code == "round2_required_lane_only"


def test_round3_is_bounded_and_only_for_supplemental_or_fallback_lanes() -> None:
    lane = _build_lane(
        lane_id=CoverageLane.INDUSTRY_ASSOCIATION_SIGNAL,
        required=True,
    )
    insufficient_metrics = LaneRoundMetrics(
        accepted_candidate_count=0,
        accepted_document_count=0,
        rejected_reason_codes=["domain_topic_mismatch"],
        local_claim_allowed=True,
        parent_evidence_only=False,
    )
    budget = CoverageBudgetState(
        max_search_credits=9,
        used_search_credits=2,
        max_candidates=3,
        used_candidates=0,
        max_extractions=2,
        used_extractions=0,
    )
    judgment = judge_lane_sufficiency(
        lane_plan=lane,
        metrics=insufficient_metrics,
        budget_state=budget,
    )

    supplemental_transition = decide_round_transition(
        lane_plan=lane,
        round_index=2,
        max_rounds=3,
        judgment=judgment,
        stop_conditions=StopConditions(),
        supplemental_or_fallback_lane=True,
    )
    primary_transition = decide_round_transition(
        lane_plan=lane,
        round_index=2,
        max_rounds=3,
        judgment=judgment,
        stop_conditions=StopConditions(),
        supplemental_or_fallback_lane=False,
    )

    assert supplemental_transition.decision == "continue"
    assert supplemental_transition.next_round == 3
    assert supplemental_transition.reason_code == "round3_supplemental_or_fallback"

    assert primary_transition.decision == "stop"
    assert primary_transition.reason_code == "round3_not_eligible_for_lane"


def test_budget_exhaustion_creates_structured_gap_without_fake_sufficiency() -> None:
    lane = _build_lane(lane_id=CoverageLane.CITY_COUNTY_FALLBACK, required=True)
    metrics = LaneRoundMetrics(
        accepted_candidate_count=0,
        accepted_document_count=0,
        rejected_reason_codes=[],
        local_claim_allowed=False,
        parent_evidence_only=True,
    )
    budget = CoverageBudgetState(
        max_search_credits=1,
        used_search_credits=1,
        max_candidates=1,
        used_candidates=1,
        max_extractions=1,
        used_extractions=1,
    )
    judgment = judge_lane_sufficiency(
        lane_plan=lane,
        metrics=metrics,
        budget_state=budget,
    )

    assert judgment.sufficient is False
    assert judgment.budget_exhausted is True
    assert any(gap.reason_code == "budget_exhausted" for gap in judgment.coverage_gaps)


def test_budget_exhaustion_does_not_override_sufficient_evidence() -> None:
    lane = _build_lane(lane_id=CoverageLane.NATIONAL_POLICY_DIRECTION, required=True)
    metrics = LaneRoundMetrics(
        accepted_candidate_count=3,
        accepted_document_count=3,
        rejected_reason_codes=["off_domain_candidate"],
        local_claim_allowed=True,
        parent_evidence_only=False,
    )
    budget = CoverageBudgetState(
        max_search_credits=2,
        used_search_credits=1,
        max_candidates=3,
        used_candidates=3,
        max_extractions=3,
        used_extractions=3,
    )
    judgment = judge_lane_sufficiency(
        lane_plan=lane,
        metrics=metrics,
        budget_state=budget,
    )

    transition = decide_round_transition(
        lane_plan=lane,
        round_index=1,
        max_rounds=2,
        judgment=judgment,
        stop_conditions=StopConditions(),
        supplemental_or_fallback_lane=False,
    )

    assert judgment.budget_exhausted is True
    assert judgment.sufficient is True
    assert judgment.coverage_gaps == []
    assert transition.decision == "stop"
    assert transition.reason_code == "required_lane_sufficient"
