from __future__ import annotations

from dataclasses import dataclass, replace

SHADOW_STRATEGY = "shadow_langgraph_v1"
PROVIDER_BACKED_STRATEGY = "provider_backed_v1"

NODE_SEQUENCE = (
    "plan_task",
    "collect_sources",
    "parse_sources",
    "score_sources",
    "build_evidence",
    "build_claims",
    "editor1_draft",
    "editor2_review",
    "verify_claims",
    "chief_gate",
    "human_review",
    "finalize_report",
)


@dataclass(frozen=True, slots=True)
class PromptAsset:
    node_name: str
    strategy: str
    prompt_version: str
    context_fields: tuple[str, ...]
    output_contract: str
    fallback_rule: str
    context_budget_tokens: int = 512
    tool_permissions: tuple[str, ...] = ()
    fallback_usage_review: str = "review_fallback_usage_in_live_cases"
    live_validation_focus: tuple[str, ...] = ("general_behavior",)
    failure_class_focus: tuple[str, ...] = ("provider_runtime",)


def get_prompt_asset(*, node_name: str, strategy: str) -> PromptAsset:
    assets = _PROMPT_ASSETS.get(strategy, {})
    asset = assets.get(node_name)
    if asset is not None:
        return asset
    fallback_strategy = SHADOW_STRATEGY if strategy == PROVIDER_BACKED_STRATEGY else strategy
    fallback_assets = _PROMPT_ASSETS.get(fallback_strategy, {})
    fallback_asset = fallback_assets.get(node_name)
    if fallback_asset is not None:
        return fallback_asset
    return PromptAsset(
        node_name=node_name,
        strategy=strategy,
        prompt_version=f"{strategy}.unknown",
        context_fields=("query",),
        output_contract="unknown",
        fallback_rule="unknown_asset_fallback",
        live_validation_focus=("unknown_asset",),
        failure_class_focus=("registry_gap",),
    )


def get_prompt_version(*, node_name: str, strategy: str) -> str:
    return get_prompt_asset(node_name=node_name, strategy=strategy).prompt_version


_COMMON_ASSETS = {
    "plan_task": PromptAsset(
        node_name="plan_task",
        strategy=SHADOW_STRATEGY,
        prompt_version="shadow_v1.plan_task",
        context_fields=("query", "planner_replan_request"),
        output_contract="research_plan",
        fallback_rule="deterministic_plan_fallback",
        context_budget_tokens=600,
        fallback_usage_review="planner_fallback_should_be_audited_against_live_cases",
        live_validation_focus=("plan_shape", "obligation_coverage"),
        failure_class_focus=("prompt_contract", "provider_runtime"),
    ),
    "collect_sources": PromptAsset(
        node_name="collect_sources",
        strategy=SHADOW_STRATEGY,
        prompt_version="shadow_v1.collect_sources",
        context_fields=("query", "plan", "sources"),
        output_contract="source_list",
        fallback_rule="shadow_rule_collection",
        context_budget_tokens=700,
        live_validation_focus=("source_discovery", "retry_stability"),
        failure_class_focus=("provider_runtime", "source_quality"),
    ),
    "parse_sources": PromptAsset(
        node_name="parse_sources",
        strategy=SHADOW_STRATEGY,
        prompt_version="shadow_v1.parse_sources",
        context_fields=("query", "sources"),
        output_contract="clean_source_list",
        fallback_rule="sanitize_raw_source_text",
        context_budget_tokens=900,
        live_validation_focus=("text_sanitization", "noise_removal"),
        failure_class_focus=("context_contract", "extraction_quality"),
    ),
    "score_sources": PromptAsset(
        node_name="score_sources",
        strategy=SHADOW_STRATEGY,
        prompt_version="shadow_v1.score_sources",
        context_fields=("query", "sources"),
        output_contract="source_quality_records",
        fallback_rule="deterministic_source_quality_scoring",
        context_budget_tokens=1000,
        live_validation_focus=("source_role_classification", "usage_role_classification"),
        failure_class_focus=("context_contract", "scoring_logic"),
    ),
    "build_evidence": PromptAsset(
        node_name="build_evidence",
        strategy=SHADOW_STRATEGY,
        prompt_version="shadow_v1.build_evidence",
        context_fields=("query", "sources"),
        output_contract="evidence_items",
        fallback_rule="source_to_evidence_projection",
        context_budget_tokens=1100,
        live_validation_focus=("evidence_granularity", "support_strength_spread"),
        failure_class_focus=("context_contract", "scoring_logic"),
    ),
    "build_claims": PromptAsset(
        node_name="build_claims",
        strategy=SHADOW_STRATEGY,
        prompt_version="shadow_v1.build_claims",
        context_fields=("query", "plan", "evidence", "query_requirements"),
        output_contract="claims",
        fallback_rule="query_intent_claim_family_fallback",
        context_budget_tokens=1200,
        live_validation_focus=("claim_family_count", "claim_auditability"),
        failure_class_focus=("prompt_contract", "context_contract"),
    ),
    "editor1_draft": PromptAsset(
        node_name="editor1_draft",
        strategy=SHADOW_STRATEGY,
        prompt_version="shadow_v1.editor1_draft",
        context_fields=("query", "claims", "evidence", "drafts"),
        output_contract="draft_sections",
        fallback_rule="structured_editor_fallback",
        context_budget_tokens=1600,
        tool_permissions=("get_evidence_bundle", "compose_section_outline"),
        fallback_usage_review="editor_draft_fallback_should_be_checked_for_provider_contract_mismatch",
        live_validation_focus=("draft_readability", "claim_to_section_mapping"),
        failure_class_focus=("prompt_contract", "provider_runtime"),
    ),
    "editor2_review": PromptAsset(
        node_name="editor2_review",
        strategy=SHADOW_STRATEGY,
        prompt_version="shadow_v1.editor2_review",
        context_fields=(
            "query",
            "plan",
            "claims",
            "evidence",
            "sources",
            "claim_support_matrix",
            "drafts",
        ),
        output_contract="review_issues",
        fallback_rule="claim_review_issue_fallback",
        context_budget_tokens=1500,
        tool_permissions=("get_claim_support_matrix", "get_source_bundle", "request_revision"),
        live_validation_focus=("review_specificity", "revision_guidance_quality"),
        failure_class_focus=("prompt_contract", "context_contract"),
    ),
    "verify_claims": PromptAsset(
        node_name="verify_claims",
        strategy=SHADOW_STRATEGY,
        prompt_version="shadow_v1.verify_claims",
        context_fields=(
            "query",
            "plan",
            "claims",
            "evidence",
            "sources",
            "claim_support_matrix",
            "review_issues",
            "drafts",
        ),
        output_contract="claim_verifications",
        fallback_rule="claim_support_matrix_fallback",
        context_budget_tokens=1500,
        live_validation_focus=("verification_specificity", "claim_support_alignment"),
        failure_class_focus=("context_contract", "provider_runtime"),
    ),
    "chief_gate": PromptAsset(
        node_name="chief_gate",
        strategy=SHADOW_STRATEGY,
        prompt_version="shadow_v1.chief_gate",
        context_fields=("query", "claims", "claim_verifications", "review_issues"),
        output_contract="gate_decision",
        fallback_rule="structured_gate_fallback",
        context_budget_tokens=1200,
        tool_permissions=("get_claim_support_matrix", "get_source_bundle", "request_replan"),
        fallback_usage_review="gate_fallback_should_trigger_manual_review_bias",
        live_validation_focus=("actionability_of_gate_output", "human_review_threshold"),
        failure_class_focus=("prompt_contract", "context_contract", "provider_runtime"),
    ),
    "human_review": PromptAsset(
        node_name="human_review",
        strategy=SHADOW_STRATEGY,
        prompt_version="shadow_v1.human_review",
        context_fields=("query", "claims", "review_issues", "required_actions", "drafts"),
        output_contract="human_review_payload",
        fallback_rule="pending_human_review_payload_fallback",
        context_budget_tokens=800,
        live_validation_focus=("human_decision_visibility", "resume_action_clarity"),
        failure_class_focus=("context_contract", "workflow_contract"),
    ),
    "finalize_report": PromptAsset(
        node_name="finalize_report",
        strategy=SHADOW_STRATEGY,
        prompt_version="shadow_v1.finalize_report",
        context_fields=("query", "claims", "evidence", "claim_verifications", "review_issues"),
        output_contract="readable_report",
        fallback_rule="deterministic_report_composition",
        context_budget_tokens=1800,
        tool_permissions=("compose_final_report", "get_evidence_bundle"),
        fallback_usage_review="report_fallback_should_be_checked_for_readability_and_noise",
        live_validation_focus=("report_readability", "evidence_line_cleanliness"),
        failure_class_focus=("context_contract", "provider_runtime", "report_rendering"),
    ),
}

_PROVIDER_BACKED_OVERRIDES = {
    "plan_task": replace(
        _COMMON_ASSETS["plan_task"],
        strategy=PROVIDER_BACKED_STRATEGY,
        prompt_version="provider_backed_v1.plan_task",
    ),
    "collect_sources": replace(
        _COMMON_ASSETS["collect_sources"],
        strategy=PROVIDER_BACKED_STRATEGY,
        prompt_version="provider_backed_v1.collect_sources",
    ),
    "parse_sources": replace(
        _COMMON_ASSETS["parse_sources"],
        strategy=PROVIDER_BACKED_STRATEGY,
        prompt_version="provider_backed_v1.parse_sources",
    ),
    "score_sources": replace(
        _COMMON_ASSETS["score_sources"],
        strategy=PROVIDER_BACKED_STRATEGY,
        prompt_version="provider_backed_v1.score_sources",
    ),
    "build_evidence": replace(
        _COMMON_ASSETS["build_evidence"],
        strategy=PROVIDER_BACKED_STRATEGY,
        prompt_version="provider_backed_v1.build_evidence",
    ),
    "build_claims": replace(
        _COMMON_ASSETS["build_claims"],
        strategy=PROVIDER_BACKED_STRATEGY,
        prompt_version="provider_backed_v1.build_claims",
    ),
    "editor1_draft": replace(
        _COMMON_ASSETS["editor1_draft"],
        strategy=PROVIDER_BACKED_STRATEGY,
        prompt_version="provider_backed_v1.editor1_draft",
    ),
    "editor2_review": replace(
        _COMMON_ASSETS["editor2_review"],
        strategy=PROVIDER_BACKED_STRATEGY,
        prompt_version="provider_backed_v1.editor2_review",
    ),
    "verify_claims": replace(
        _COMMON_ASSETS["verify_claims"],
        strategy=PROVIDER_BACKED_STRATEGY,
        prompt_version="provider_backed_v1.verify_claims",
    ),
    "chief_gate": replace(
        _COMMON_ASSETS["chief_gate"],
        strategy=PROVIDER_BACKED_STRATEGY,
        prompt_version="provider_backed_v1.chief_gate",
    ),
    "human_review": replace(
        _COMMON_ASSETS["human_review"],
        strategy=PROVIDER_BACKED_STRATEGY,
        prompt_version="provider_backed_v1.human_review",
    ),
    "finalize_report": replace(
        _COMMON_ASSETS["finalize_report"],
        strategy=PROVIDER_BACKED_STRATEGY,
        prompt_version="provider_backed_v1.finalize_report",
    ),
}

_PROMPT_ASSETS = {
    SHADOW_STRATEGY: _COMMON_ASSETS,
    PROVIDER_BACKED_STRATEGY: _PROVIDER_BACKED_OVERRIDES,
}
