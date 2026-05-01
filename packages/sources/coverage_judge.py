from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from packages.sources.retrieval_plan import CoverageGap, CoverageLanePlan, StopConditions


@dataclass(slots=True)
class CoverageBudgetState:
    max_search_credits: int
    used_search_credits: int = 0
    max_candidates: int = 0
    used_candidates: int = 0
    max_extractions: int = 0
    used_extractions: int = 0

    def exhausted(self) -> bool:
        return any(
            (
                self.max_search_credits > 0
                and self.used_search_credits >= self.max_search_credits,
                self.max_candidates > 0 and self.used_candidates >= self.max_candidates,
                self.max_extractions > 0 and self.used_extractions >= self.max_extractions,
            )
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "max_search_credits": self.max_search_credits,
            "used_search_credits": self.used_search_credits,
            "max_candidates": self.max_candidates,
            "used_candidates": self.used_candidates,
            "max_extractions": self.max_extractions,
            "used_extractions": self.used_extractions,
        }


@dataclass(slots=True)
class LaneRoundMetrics:
    accepted_candidate_count: int = 0
    accepted_document_count: int = 0
    rejected_reason_codes: list[str] = field(default_factory=list)
    local_claim_allowed: bool = True
    parent_evidence_only: bool = False


@dataclass(slots=True)
class LaneSufficiencyJudgment:
    sufficient: bool
    required: bool
    budget_exhausted: bool
    direct_keep_boundary_violation: bool
    coverage_gaps: list[CoverageGap]


@dataclass(slots=True)
class RoundTransition:
    decision: Literal["stop", "continue"]
    reason_code: str
    next_round: int | None = None
    domain_widening_blocked: bool = True


def judge_lane_sufficiency(
    *,
    lane_plan: CoverageLanePlan,
    metrics: LaneRoundMetrics,
    budget_state: CoverageBudgetState,
) -> LaneSufficiencyJudgment:
    min_docs = max(1, int(lane_plan.success_criteria.min_accepted_documents))
    documents_enough = metrics.accepted_document_count >= min_docs
    local_rule_ok = not (
        lane_plan.success_criteria.require_exact_local_match and not metrics.local_claim_allowed
    )
    direct_keep_boundary_violation = "direct_keep_boundary_violation" in set(
        metrics.rejected_reason_codes
    )
    budget_exhausted = budget_state.exhausted()
    sufficient = bool(documents_enough and local_rule_ok and not direct_keep_boundary_violation)

    gaps: list[CoverageGap] = []
    if not sufficient:
        reason_code = _gap_reason_code(
            budget_exhausted=budget_exhausted,
            direct_keep_boundary_violation=direct_keep_boundary_violation,
            lane_plan=lane_plan,
            metrics=metrics,
        )
        gaps.append(
            CoverageGap(
                lane_id=lane_plan.lane_id,
                reason_code=reason_code,
                required=lane_plan.required,
                fallback_level=(
                    "exact_local_required"
                    if lane_plan.success_criteria.require_exact_local_match
                    else None
                ),
                fallback_source=lane_plan.fallback_ladder[0] if lane_plan.fallback_ladder else None,
                parent_evidence_only=metrics.parent_evidence_only,
                local_claim_allowed=metrics.local_claim_allowed,
                notes=[],
            )
        )

    return LaneSufficiencyJudgment(
        sufficient=sufficient,
        required=lane_plan.required,
        budget_exhausted=budget_exhausted,
        direct_keep_boundary_violation=direct_keep_boundary_violation,
        coverage_gaps=gaps,
    )


def decide_round_transition(
    *,
    lane_plan: CoverageLanePlan,
    round_index: int,
    max_rounds: int,
    judgment: LaneSufficiencyJudgment,
    stop_conditions: StopConditions,
    supplemental_or_fallback_lane: bool,
) -> RoundTransition:
    if (
        judgment.direct_keep_boundary_violation
        and stop_conditions.stop_on_direct_keep_boundary_violation
    ):
        return RoundTransition(decision="stop", reason_code="direct_keep_boundary_violation")

    if (
        judgment.sufficient
        and stop_conditions.stop_when_all_required_lanes_sufficient
        and lane_plan.required
    ):
        return RoundTransition(decision="stop", reason_code="required_lane_sufficient")

    if judgment.budget_exhausted and stop_conditions.stop_when_credit_budget_reached:
        return RoundTransition(decision="stop", reason_code="budget_exhausted")

    if round_index >= max_rounds:
        return RoundTransition(decision="stop", reason_code="max_rounds_reached")

    if round_index == 1:
        if lane_plan.required and not judgment.sufficient:
            return RoundTransition(
                decision="continue",
                reason_code="required_lane_gap_needs_round2",
                next_round=2,
                domain_widening_blocked=True,
            )
        if supplemental_or_fallback_lane and not judgment.sufficient and max_rounds >= 3:
            return RoundTransition(
                decision="continue",
                reason_code="round3_supplemental_or_fallback",
                next_round=3,
                domain_widening_blocked=True,
            )
        return RoundTransition(decision="stop", reason_code="round2_required_lane_only")

    if round_index == 2:
        if lane_plan.required and not judgment.sufficient:
            if supplemental_or_fallback_lane and max_rounds >= 3:
                return RoundTransition(
                    decision="continue",
                    reason_code="round3_supplemental_or_fallback",
                    next_round=3,
                    domain_widening_blocked=True,
                )
            return RoundTransition(decision="stop", reason_code="round3_not_eligible_for_lane")
        return RoundTransition(decision="stop", reason_code="required_lane_sufficient")

    return RoundTransition(decision="stop", reason_code="max_rounds_reached")


def _gap_reason_code(
    *,
    budget_exhausted: bool,
    direct_keep_boundary_violation: bool,
    lane_plan: CoverageLanePlan,
    metrics: LaneRoundMetrics,
) -> str:
    if direct_keep_boundary_violation:
        return "direct_keep_boundary_violation"
    if budget_exhausted:
        return "budget_exhausted"
    if lane_plan.success_criteria.require_exact_local_match and not metrics.local_claim_allowed:
        return "local_source_pending_exact_match"
    if metrics.rejected_reason_codes:
        return "no_compatible_sources"
    return "insufficient_coverage"


__all__ = [
    "CoverageBudgetState",
    "LaneRoundMetrics",
    "LaneSufficiencyJudgment",
    "RoundTransition",
    "decide_round_transition",
    "judge_lane_sufficiency",
]
