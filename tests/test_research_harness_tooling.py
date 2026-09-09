from packages.research_harness.tooling import ToolExecutor, ToolHarness, ToolSession
from packages.research_harness.tooling.llm_agents import (
    build_editor1_draft_prompts,
    build_editor2_review_prompts,
    build_verifier_prompts,
)


def _sample_state() -> dict[str, object]:
    return {
        "query": "low altitude economy award notice",
        "claims": [
            {
                "claim_id": "claim_policy_primary",
                "text": "The query has official policy grounding.",
                "supported": True,
                "evidence_ids": ["ev_1"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "ev_1",
                "source_id": "src_1",
                "summary": "Official policy text confirms the program remains active.",
                "support_type": "background_support",
                "support_strength": 0.66,
                "specificity": "policy_statement",
                "limitations": [],
            }
        ],
        "sources": [
            {
                "source_id": "src_1",
                "title": "Official policy notice",
                "url": "https://www.gov.cn/policy.html",
                "source_family": "official_policy",
                "source_tier": "A",
            }
        ],
        "review_issues": [],
        "claim_support_matrix": [],
        "claim_verifications": [],
        "drafts": [],
        "query_requirements": {},
    }


def _editor1_session() -> ToolSession:
    return ToolSession(
        node_name="editor1_draft",
        agent_name="Editor1",
        state=_sample_state(),
        harness=ToolHarness(),
        executor=ToolExecutor(),
    )


def test_editor1_tooling_allows_get_evidence_bundle() -> None:
    session = _editor1_session()

    result = session.call_tool(
        "get_evidence_bundle",
        {"claim_ids": ["claim_policy_primary"]},
    )

    assert result["ok"] is True
    assert result["result"]["claim_count"] == 1
    assert result["result"]["evidence_count"] == 1


def test_editor1_tooling_denies_request_replan() -> None:
    session = _editor1_session()

    result = session.call_tool(
        "request_replan",
        {"focus_claim_ids": ["claim_policy_primary"], "note": "Need more procurement evidence."},
    )

    assert result["ok"] is False
    assert result["error_code"] == "tool_not_allowed_for_node"


def test_tooling_denies_forbidden_tool_and_records_trace() -> None:
    session = _editor1_session()

    result = session.call_tool("write_database_record", {})
    traces = session.export_traces()

    assert result["ok"] is False
    assert result["error_code"] == "forbidden_tool"
    assert traces[-1]["tool_name"] == "write_database_record"
    assert traces[-1]["status"] == "denied"
    assert traces[-1]["reason_code"] == "forbidden_tool"


def test_tooling_records_allowed_and_denied_trace_details() -> None:
    session = _editor1_session()

    allowed = session.call_tool(
        "get_evidence_bundle",
        {"claim_ids": ["claim_policy_primary"]},
    )
    denied = session.call_tool(
        "request_replan",
        {"focus_claim_ids": ["claim_policy_primary"], "note": "Need more procurement evidence."},
    )
    traces = session.export_traces()

    assert allowed["ok"] is True
    assert denied["ok"] is False
    assert len(traces) == 2
    assert traces[0]["tool_name"] == "get_evidence_bundle"
    assert traces[0]["status"] == "allowed"
    assert traces[0]["result_summary"]["item_count"] == 1
    assert traces[1]["tool_name"] == "request_replan"
    assert traces[1]["status"] == "denied"
    assert traces[1]["reason_code"] == "tool_not_allowed_for_node"


def test_editor1_prompt_targets_readable_report_product() -> None:
    system_prompt, user_prompt = build_editor1_draft_prompts(
        query="低空经济 地方政策 项目公示",
        draft_version=1,
        claims=[
            {
                "claim_id": "claim_policy_primary",
                "text": "存在政策依据。",
                "supported": True,
                "claim_family": "policy_basis",
                "required_source_family": "official_policy",
                "support_requirement": "policy_statement",
                "evidence_ids": ["ev_1"],
            },
            {
                "claim_id": "claim_local_rollout",
                "text": "存在地方执行线索。",
                "supported": True,
                "claim_family": "local_rollout",
                "required_source_family": "official_policy",
                "support_requirement": "policy_statement",
                "evidence_ids": ["ev_2"],
            },
        ],
        evidence_bundle={"items": [{"claim_id": "claim_policy_primary"}]},
        outline={"sections": ["Executive Summary", "Policy Basis", "Local Rollout"]},
        prior_drafts=[],
    )

    assert "publishable Chinese Markdown research memo" in system_prompt
    assert "Executive Summary" in user_prompt
    assert "Method And Scope" in user_prompt
    assert "Uncertainty And Next Steps" in user_prompt
    assert "do not merge everything into one coarse conclusion" in user_prompt


def test_editor2_and_verifier_prompts_target_report_quality_not_schema_only() -> None:
    editor2_system, editor2_user = build_editor2_review_prompts(
        query="低空经济 地方政策 项目公示",
        plan={"dimension_plan": [{"dimension_type": "policy"}]},
        claims=[
            {
                "claim_id": "claim_policy_primary",
                "text": "存在政策依据。",
                "supported": True,
                "claim_family": "policy_basis",
                "required_source_family": "official_policy",
                "support_requirement": "policy_statement",
                "evidence_ids": ["ev_1"],
            }
        ],
        evidence=[
            {
                "evidence_id": "ev_1",
                "summary": "政策原文",
                "support_strength": 0.81,
                "specificity": "policy_statement",
                "limitations": [],
                "source_ids": ["src_1"],
            }
        ],
        sources=[
            {
                "source_id": "src_1",
                "title": "政策原文",
                "source_family": "official_policy",
                "source_quality_v2": {
                    "source_role": "official_policy_original",
                    "usage_role": "primary_evidence_candidate",
                    "credibility_score": 0.9,
                },
            }
        ],
        support_matrix=[],
        latest_draft={
            "draft_id": "draft_1",
            "draft_version": 1,
            "report_markdown": "## Executive Summary\n\n初稿。",
            "sections": [],
        },
        review_focus=["dimension coverage", "section framing"],
    )
    verifier_system, verifier_user = build_verifier_prompts(
        query="低空经济 地方政策 项目公示",
        plan={"dimension_plan": [{"dimension_type": "policy"}]},
        claims=[
            {
                "claim_id": "claim_policy_primary",
                "text": "存在政策依据。",
                "claim_family": "policy_basis",
                "required_source_family": "official_policy",
                "support_requirement": "policy_statement",
                "evidence_ids": ["ev_1"],
            }
        ],
        evidence=[
            {
                "evidence_id": "ev_1",
                "summary": "政策原文",
                "support_strength": 0.81,
                "specificity": "policy_statement",
                "limitations": [],
                "source_ids": ["src_1"],
            }
        ],
        sources=[
            {
                "source_id": "src_1",
                "source_family": "official_policy",
                "source_quality_v2": {
                    "source_role": "official_policy_original",
                    "usage_role": "primary_evidence_candidate",
                    "credibility_score": 0.9,
                },
            }
        ],
        support_matrix=[],
        latest_draft={
            "draft_id": "draft_1",
            "draft_version": 1,
            "report_markdown": "## Executive Summary\n\n初稿。",
            "sections": [],
        },
        review_issues=[],
    )

    assert "real research opponent before publication" in editor2_system
    assert "readable report" in editor2_user
    assert "senior analyst would give to a junior research writer" in editor2_user
    assert "protect report quality and auditability" in verifier_system
    assert "meaningful score spread" in verifier_user
    assert "conditional or scope-limited" in verifier_user
