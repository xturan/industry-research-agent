from __future__ import annotations

from typing import Any

from packages.research_harness.contracts import (
    ChiefGateOutput,
    EditorDraftOutput,
    RequiredAction,
    ReviewIssueList,
    VerifierOutput,
    coerce_model_output,
)


def build_editor_draft(
    *,
    query: str,
    claims: list[dict[str, Any]],
    prior_drafts: list[dict[str, Any]],
    inject_invalid_json: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    draft_version = len(prior_drafts) + 1
    raw_output: dict[str, Any] | str = {
        "draft_id": f"draft_{draft_version}",
        "draft_version": draft_version,
        "sections": [
            {
                "section_id": "sec_overview",
                "title": "Research Summary",
                "paragraphs": [
                    {
                        "paragraph_id": f"p_{claim['claim_id']}",
                        "text": claim["text"],
                        "claim_ids": [claim["claim_id"]],
                        "evidence_ids": claim.get("evidence_ids", []),
                        "confidence": "high" if claim.get("supported") else "medium",
                        "limitations": (
                            [] if claim.get("supported") else ["Needs stronger support."]
                        ),
                    }
                    for claim in claims
                ],
            }
        ],
    }
    if inject_invalid_json:
        raw_output = '{"draft_id": "broken", "draft_version": "bad"'

    model, meta = coerce_model_output(
        raw_output,
        model_cls=EditorDraftOutput,
        fallback_factory=lambda: {
            "draft_id": f"draft_{draft_version}",
            "draft_version": draft_version,
            "sections": [
                {
                    "section_id": "sec_fallback",
                    "title": "Fallback Summary",
                    "paragraphs": [
                        {
                            "paragraph_id": "p_fallback",
                            "text": f"Fallback draft for query: {query}",
                            "claim_ids": [],
                            "evidence_ids": [],
                            "confidence": "low",
                            "limitations": ["Structured fallback was used."],
                        }
                    ],
                }
            ],
        },
    )
    return model.model_dump(mode="json"), meta


def build_review_issues(
    *,
    query: str,
    claims: list[dict[str, Any]],
    inject_invalid_json: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_output: dict[str, Any] | str = {
        "issues": [
            {
                "issue_id": f"issue_{claim['claim_id']}",
                "severity": "blocker",
                "issue_type": "unsupported_claim",
                "target_claim_id": claim["claim_id"],
                "description": "Claim lacks direct supporting evidence.",
                "required_fix": "Add stronger evidence before approval.",
                "suggested_search_queries": [f"{query} award notice"],
            }
            for claim in claims
            if not claim.get("supported", False)
        ]
    }
    if inject_invalid_json:
        raw_output = '{"issues": [{"issue_id": 1, "severity": "blocker"}]'

    model, meta = coerce_model_output(
        raw_output,
        model_cls=ReviewIssueList,
        fallback_factory=lambda: {"issues": []},
    )
    return model.model_dump(mode="json"), meta


def build_verifier_output(
    *,
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    review_issues: list[dict[str, Any]],
    inject_invalid_json: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence_map = {item.get("evidence_id"): item for item in evidence}
    claim_results = []
    for claim in claims:
        claim_evidence_ids = claim.get("evidence_ids", [])
        claim_source_ids = [
            evidence_map[evidence_id]["source_id"]
            for evidence_id in claim_evidence_ids
            if evidence_id in evidence_map
        ]
        support_status = "supported" if claim.get("supported") else "unsupported"
        notes = []
        if not claim.get("supported"):
            notes.append("Missing direct support evidence.")
        claim_results.append(
            {
                "claim_id": claim["claim_id"],
                "support_status": support_status,
                "support_score": 1.0 if claim.get("supported") else 0.45,
                "evidence_ids": claim_evidence_ids,
                "source_ids": claim_source_ids,
                "notes": notes,
            }
        )

    supported_count = sum(1 for item in claim_results if item["support_status"] == "supported")
    total_claims = max(len(claim_results), 1)
    evidence_coverage = round(supported_count / total_claims, 2)
    # G4 真实化：citation_integrity 改为「可溯源证据占比」——所有被 claim 引用的 evidence 中，
    # 有可解析 source_url 且非占位符的比例（原 0.96/0.82 硬编码与 evidence 层完全脱钩）。
    evidence_by_id = {str(item.get("evidence_id")): item for item in evidence}
    cited_evidence = [
        evidence_by_id[str(eid)]
        for claim in claims
        for eid in (claim.get("evidence_ids", []) or [])
        if str(eid) in evidence_by_id
    ]
    if cited_evidence:
        resolvable = 0
        for ev in cited_evidence:
            url = str(ev.get("source_url") or ev.get("url") or "")
            if url and url not in {"", "unknown", "n/a"} and url.startswith(("http", "www")):
                resolvable += 1
        citation_integrity = round(resolvable / len(cited_evidence), 2)
    else:
        citation_integrity = 0.0
    source_quality = round(
        sum(
            float(source.get("source_quality_v2", {}).get("credibility_score", 0.0))
            for source in sources
        )
        / max(len(sources), 1),
        2,
    )
    contradiction_resolution = 0.8 if not review_issues else 0.6
    # G4 真实化：final_score 加权 0.4/0.3/0.2/0.1（原四者等权）
    final_score = round(
        evidence_coverage * 0.4
        + citation_integrity * 0.3
        + source_quality * 0.2
        + contradiction_resolution * 0.1,
        2,
    )

    raw_output: dict[str, Any] | str = {
        "claim_verifications": claim_results,
        "quality_scores": {
            "evidence_coverage": evidence_coverage,
            "citation_integrity": citation_integrity,
            "source_quality": source_quality,
            "contradiction_resolution": contradiction_resolution,
            "final_score": final_score,
        },
    }
    if inject_invalid_json:
        raw_output = '{"claim_verifications": "broken"}'

    model, meta = coerce_model_output(
        raw_output,
        model_cls=VerifierOutput,
        fallback_factory=lambda: {
            "claim_verifications": [],
            "quality_scores": {
                "evidence_coverage": 0.0,
                "citation_integrity": 0.0,
                "source_quality": 0.0,
                "contradiction_resolution": 0.0,
                "final_score": 0.0,
            },
        },
    )
    return model.model_dump(mode="json"), meta


def build_chief_gate_output(
    *,
    query: str,
    claim_verifications: list[dict[str, Any]],
    quality_scores: dict[str, float],
    review_issues: list[dict[str, Any]],
    loop_count: int,
    max_loop_count: int,
    inject_invalid_json: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    unsupported_claims = [
        item for item in claim_verifications if item.get("support_status") == "unsupported"
    ]
    decision = "PASS"
    reason = "All key claims are sufficiently supported."
    route_to = "finalize_report"
    required_actions: list[RequiredAction] = []

    if unsupported_claims and loop_count >= max_loop_count:
        decision = "HUMAN_REVIEW"
        reason = "Unsupported key claims remain after reaching loop budget."
        route_to = "human_review"
        required_actions.append(
            RequiredAction(
                action_type="HUMAN_REVIEW",
                note="Manual review required after repeated unsupported claims.",
            )
        )
    elif unsupported_claims or any(issue.get("severity") == "blocker" for issue in review_issues):
        decision = "ADD_EVIDENCE"
        reason = "Unsupported key claims require stronger evidence."
        route_to = "collect_sources"
        for claim in unsupported_claims:
            required_actions.append(
                RequiredAction(
                    action_type="ADD_EVIDENCE",
                    target_claim_id=claim.get("claim_id"),
                    required_source_family="tender_procurement",
                    note=f"Augment support for {claim.get('claim_id')}.",
                )
            )
    elif float(quality_scores.get("citation_integrity", 0.0)) < 0.95:
        decision = "REVISE_TEXT"
        reason = "Citation integrity is below threshold."
        route_to = "editor1_draft"
        required_actions.append(
            RequiredAction(
                action_type="REVISE_TEXT",
                note="Revise text to align citations and claims.",
            )
        )
    elif float(quality_scores.get("final_score", 0.0)) < 0.7:
        decision = "REVIEW_RISK"
        reason = "Quality score remains below release threshold."
        route_to = "editor2_review"
        required_actions.append(
            RequiredAction(
                action_type="REVIEW_RISK",
                note="Re-open critique loop for risk review.",
            )
        )

    raw_output: dict[str, Any] | str = {
        "decision": decision,
        "reason": reason,
        "route_to": route_to,
        "required_actions": [item.model_dump(mode="json") for item in required_actions],
        "quality_scores": quality_scores,
        "loop_count": (
            loop_count + 1
            if decision in {"ADD_EVIDENCE", "REVISE_TEXT", "REVIEW_RISK"}
            else loop_count
        ),
        "contract_mode": "validated",
    }
    if inject_invalid_json:
        raw_output = '{"decision": "ADD_EVIDENCE", "reason": 1}'

    model, meta = coerce_model_output(
        raw_output,
        model_cls=ChiefGateOutput,
        fallback_factory=lambda: {
            "decision": "HUMAN_REVIEW",
            "reason": f"Fallback gate for query: {query}",
            "route_to": "human_review",
            "required_actions": [
                {
                    "action_type": "HUMAN_REVIEW",
                    "note": "Structured fallback triggered.",
                }
            ],
            "quality_scores": quality_scores,
            "loop_count": loop_count,
            "contract_mode": "fallback",
        },
    )
    return model.model_dump(mode="json"), meta
