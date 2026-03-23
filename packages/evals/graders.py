from __future__ import annotations

from typing import Any

from packages.evals.datasets import RESEARCH_MIN_CONFIDENCE_FOR_SUFFICIENT
from packages.evals.schemas import EvalCaseResult
from packages.policy.service import PolicyChecker


def grade_rag_chunks(chunks_payload: dict[str, Any]) -> list[EvalCaseResult]:
    items = chunks_payload.get("items") if isinstance(chunks_payload.get("items"), list) else []
    returned_count = int(chunks_payload.get("returned_count") or len(items))

    has_items = returned_count >= 1
    citation_ratio = 0.0
    if items:
        cited = 0
        for item in items:
            if item.get("citation_locator") or item.get("citation_quote"):
                cited += 1
        citation_ratio = cited / len(items)

    scores = [float(item.get("score") or 0.0) for item in items]
    score_desc = all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))

    has_doc_meta = True
    for item in items:
        if not item.get("document_title") or not item.get("source_type"):
            has_doc_meta = False
            break

    return [
        EvalCaseResult(
            case_name="rag_items_non_empty",
            passed=has_items,
            score=1.0 if has_items else 0.0,
            detail_json={"returned_count": returned_count},
        ),
        EvalCaseResult(
            case_name="rag_items_have_citations",
            passed=citation_ratio >= 0.5 if items else False,
            score=round(citation_ratio, 4),
            detail_json={"citation_ratio": citation_ratio, "item_count": len(items)},
        ),
        EvalCaseResult(
            case_name="rag_scores_descending",
            passed=score_desc,
            score=1.0 if score_desc else 0.0,
            detail_json={"scores": scores[:10]},
        ),
        EvalCaseResult(
            case_name="rag_items_have_doc_metadata",
            passed=has_doc_meta and bool(items),
            score=1.0 if (has_doc_meta and items) else 0.0,
            detail_json={"checked_items": len(items)},
        ),
    ]


def grade_evidence_bundle(bundle_payload: dict[str, Any]) -> list[EvalCaseResult]:
    items = bundle_payload.get("items") if isinstance(bundle_payload.get("items"), list) else []
    grouped_documents = (
        bundle_payload.get("grouped_documents")
        if isinstance(bundle_payload.get("grouped_documents"), list)
        else []
    )
    has_bundle_id = bool(bundle_payload.get("bundle_id"))
    has_items = len(items) > 0
    grouped_ok = len(grouped_documents) >= 1 if has_items else False

    locator_ratio = 0.0
    if items:
        has_locator = sum(1 for item in items if item.get("citation_locator"))
        locator_ratio = has_locator / len(items)

    return [
        EvalCaseResult(
            case_name="bundle_has_id",
            passed=has_bundle_id,
            score=1.0 if has_bundle_id else 0.0,
            detail_json={"bundle_id": bundle_payload.get("bundle_id")},
        ),
        EvalCaseResult(
            case_name="bundle_has_items",
            passed=has_items,
            score=1.0 if has_items else 0.0,
            detail_json={"item_count": len(items)},
        ),
        EvalCaseResult(
            case_name="bundle_grouped_documents_present",
            passed=grouped_ok,
            score=1.0 if grouped_ok else 0.0,
            detail_json={"grouped_documents_count": len(grouped_documents)},
        ),
        EvalCaseResult(
            case_name="bundle_locator_coverage",
            passed=locator_ratio >= 0.5 if items else False,
            score=round(locator_ratio, 4),
            detail_json={"locator_ratio": locator_ratio},
        ),
    ]


def grade_research_output(research_payload: dict[str, Any]) -> list[EvalCaseResult]:
    theses = (
        research_payload.get("theses")
        if isinstance(research_payload.get("theses"), list)
        else []
    )
    objections = (
        research_payload.get("objections")
        if isinstance(research_payload.get("objections"), list)
        else []
    )
    risks = research_payload.get("risks") if isinstance(research_payload.get("risks"), list) else []
    final_memo = (
        research_payload.get("final_memo")
        if isinstance(research_payload.get("final_memo"), dict)
        else {}
    )
    insufficient = bool(research_payload.get("insufficient_evidence"))
    confidence = float(research_payload.get("confidence_score") or 0.0)

    evidence_ref_ratio = 0.0
    if theses:
        with_ref = 0
        for thesis in theses:
            refs = (
                thesis.get("evidence_refs")
                if isinstance(thesis.get("evidence_refs"), list)
                else []
            )
            if refs:
                with_ref += 1
        evidence_ref_ratio = with_ref / len(theses)

    policy_report = PolicyChecker().check_research_result_payload(research_payload)

    return [
        EvalCaseResult(
            case_name="research_has_final_memo",
            passed=bool(final_memo.get("executive_summary")),
            score=1.0 if final_memo.get("executive_summary") else 0.0,
            detail_json={"has_executive_summary": bool(final_memo.get("executive_summary"))},
        ),
        EvalCaseResult(
            case_name="research_thesis_evidence_refs",
            passed=evidence_ref_ratio >= 0.8 if theses else insufficient,
            score=round(evidence_ref_ratio if theses else (1.0 if insufficient else 0.0), 4),
            detail_json={"thesis_count": len(theses), "evidence_ref_ratio": evidence_ref_ratio},
        ),
        EvalCaseResult(
            case_name="research_has_opposition_and_risks",
            passed=(len(objections) > 0 and len(risks) > 0) or insufficient,
            score=1.0 if ((len(objections) > 0 and len(risks) > 0) or insufficient) else 0.0,
            detail_json={"objections": len(objections), "risks": len(risks)},
        ),
        EvalCaseResult(
            case_name="research_confidence_consistency",
            passed=not insufficient or confidence <= RESEARCH_MIN_CONFIDENCE_FOR_SUFFICIENT,
            score=1.0
            if (not insufficient or confidence <= RESEARCH_MIN_CONFIDENCE_FOR_SUFFICIENT)
            else 0.0,
            detail_json={"insufficient_evidence": insufficient, "confidence_score": confidence},
        ),
        EvalCaseResult(
            case_name="research_policy_checks",
            passed=policy_report.passed,
            score=1.0 if policy_report.passed else 0.0,
            detail_json={
                "issues": [issue.model_dump(mode="json") for issue in policy_report.issues]
            },
        ),
    ]


def grade_content_outputs(assets_payload: list[dict[str, Any]]) -> list[EvalCaseResult]:
    checker = PolicyChecker()
    if not assets_payload:
        return [
            EvalCaseResult(
                case_name="content_assets_exist",
                passed=False,
                score=0.0,
                detail_json={"item_count": 0},
            )
        ]

    policy_passed = 0
    content_types = set()
    for asset in assets_payload:
        report = checker.check_content_asset(asset)
        if report.passed:
            policy_passed += 1
        if asset.get("content_type"):
            content_types.add(str(asset["content_type"]))

    policy_ratio = policy_passed / len(assets_payload)
    has_required_count = len(assets_payload) >= 3
    diverse_types = len(content_types) >= 2

    return [
        EvalCaseResult(
            case_name="content_assets_exist",
            passed=has_required_count,
            score=1.0 if has_required_count else 0.0,
            detail_json={"item_count": len(assets_payload)},
        ),
        EvalCaseResult(
            case_name="content_policy_pass_ratio",
            passed=policy_ratio >= 0.8,
            score=round(policy_ratio, 4),
            detail_json={"policy_pass_ratio": policy_ratio},
        ),
        EvalCaseResult(
            case_name="content_type_diversity",
            passed=diverse_types,
            score=1.0 if diverse_types else 0.0,
            detail_json={"content_types": sorted(content_types)},
        ),
    ]


def grade_task_delivery_flow(task_payload: dict[str, Any]) -> list[EvalCaseResult]:
    status = str(task_payload.get("status") or "")
    result_json = task_payload.get("result_json")
    result_json = result_json if isinstance(result_json, dict) else {}
    dispatch_status = str(result_json.get("status") or "")
    receipts = result_json.get("receipts") if isinstance(result_json.get("receipts"), list) else []

    return [
        EvalCaseResult(
            case_name="task_status_succeeded",
            passed=status == "succeeded",
            score=1.0 if status == "succeeded" else 0.0,
            detail_json={"task_status": status},
        ),
        EvalCaseResult(
            case_name="delivery_status_dispatched",
            passed=dispatch_status in {"dispatched", "partial_failed"},
            score=1.0 if dispatch_status in {"dispatched", "partial_failed"} else 0.0,
            detail_json={"delivery_status": dispatch_status},
        ),
        EvalCaseResult(
            case_name="delivery_receipts_present",
            passed=bool(receipts),
            score=1.0 if receipts else 0.0,
            detail_json={"receipt_count": len(receipts)},
        ),
    ]
