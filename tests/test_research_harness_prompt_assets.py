from packages.research_harness.prompt_assets import (
    NODE_SEQUENCE,
    PROVIDER_BACKED_STRATEGY,
    SHADOW_STRATEGY,
    get_prompt_asset,
)


def test_prompt_asset_registry_covers_all_runtime_nodes() -> None:
    for strategy in (SHADOW_STRATEGY, PROVIDER_BACKED_STRATEGY):
        for node_name in NODE_SEQUENCE:
            asset = get_prompt_asset(node_name=node_name, strategy=strategy)
            assert asset.node_name == node_name
            assert asset.prompt_version
            assert asset.context_fields
            assert asset.context_budget_tokens > 0
            assert asset.output_contract
            assert asset.fallback_rule
            assert asset.fallback_usage_review
            assert asset.live_validation_focus
            assert asset.failure_class_focus


def test_provider_backed_prompt_assets_are_explicit_for_human_review_and_finalize() -> None:
    human_review = get_prompt_asset(
        node_name="human_review",
        strategy=PROVIDER_BACKED_STRATEGY,
    )
    finalize_report = get_prompt_asset(
        node_name="finalize_report",
        strategy=PROVIDER_BACKED_STRATEGY,
    )

    assert human_review.prompt_version == "provider_backed_v1.human_review"
    assert "review_issues" in human_review.context_fields
    assert human_review.context_budget_tokens >= 400
    assert "human_decision_visibility" in human_review.live_validation_focus
    assert finalize_report.prompt_version == "provider_backed_v1.finalize_report"
    assert "claims" in finalize_report.context_fields
    assert "evidence" in finalize_report.context_fields
    assert "compose_final_report" in finalize_report.tool_permissions
    assert "get_evidence_bundle" in finalize_report.tool_permissions
    assert "readable_report" in finalize_report.output_contract
    assert "report_readability" in finalize_report.live_validation_focus
    assert "context_contract" in finalize_report.failure_class_focus


def test_provider_backed_prompt_assets_are_explicit_for_editor2_and_verifier() -> None:
    editor2 = get_prompt_asset(
        node_name="editor2_review",
        strategy=PROVIDER_BACKED_STRATEGY,
    )
    verifier = get_prompt_asset(
        node_name="verify_claims",
        strategy=PROVIDER_BACKED_STRATEGY,
    )

    assert editor2.prompt_version == "provider_backed_v1.editor2_review"
    assert "plan" in editor2.context_fields
    assert "claim_support_matrix" in editor2.context_fields
    assert "drafts" in editor2.context_fields
    assert "request_revision" in editor2.tool_permissions

    assert verifier.prompt_version == "provider_backed_v1.verify_claims"
    assert "plan" in verifier.context_fields
    assert "claim_support_matrix" in verifier.context_fields
    assert "drafts" in verifier.context_fields
    assert "verification_specificity" in verifier.live_validation_focus
