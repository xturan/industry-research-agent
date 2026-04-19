from __future__ import annotations

from typing import Any

from packages.evals.datasets import RESEARCH_MIN_CONFIDENCE_FOR_SUFFICIENT
from packages.evals.schemas import EvalCaseResult
from packages.policy.service import PolicyChecker
from packages.sources.enums import QueryType
from packages.sources.router import SourceRouter
from packages.sources.schemas import QueryContext, ToolResponse


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


def grade_source_acquisition_result(
    *,
    scenario_name: str,
    query_context: QueryContext,
    response: ToolResponse,
) -> tuple[list[EvalCaseResult], dict[str, dict[str, Any]]]:
    router = SourceRouter()
    query_type, _ = router.classify_query_type(query_context)
    traces_by_source = _pick_source_traces(response)
    source_ids = [item.source_id for item in response.route_recommendations]
    for source_id in traces_by_source:
        if source_id not in source_ids:
            source_ids.append(source_id)

    if not source_ids:
        return (
            [
                EvalCaseResult(
                    case_name=f"{scenario_name}:no_sources",
                    passed=False,
                    score=0.0,
                    detail_json={"query": query_context.query},
                )
            ],
            {},
        )

    case_results: list[EvalCaseResult] = []
    per_source_metrics: dict[str, dict[str, Any]] = {}
    for source_id in source_ids:
        trace = traces_by_source.get(source_id, {})
        status = str(trace.get("status") or "error")
        warnings = trace.get("warnings") if isinstance(trace.get("warnings"), list) else []
        retry_count = _safe_int(trace.get("retry_count"))
        evidence_count = _safe_int(trace.get("evidence_count"))
        item_count = max(_safe_int(trace.get("item_count")), 1)
        evidence_density = round(evidence_count / float(item_count), 6)

        source_evidence = [
            item
            for item in response.evidence_items
            if item.source_id == source_id
        ]
        citation_completeness = _citation_completeness(source_evidence)
        availability = 1.0 if status in {"success", "partial"} else 0.0
        evidence_yield = min(1.0, evidence_count / 2.0)
        trace_completeness = _trace_completeness(trace)
        query_fit = _query_fit_score(
            source_id=source_id,
            query_type=query_type,
            query_context=query_context,
        )
        operational = _operational_stability_score(
            status=status,
            retry_count=retry_count,
            warnings=warnings,
        )
        overall = round(
            (
                availability
                + evidence_yield
                + citation_completeness
                + trace_completeness
                + query_fit
                + operational
            )
            / 6.0,
            4,
        )
        per_source_metrics[source_id] = {
            "availability": availability,
            "evidence_yield": evidence_yield,
            "citation_completeness": citation_completeness,
            "trace_completeness": trace_completeness,
            "query_fit": query_fit,
            "operational_stability": operational,
            "overall_score": overall,
            "status": status,
            "retry_count": retry_count,
            "warnings": warnings,
            "evidence_density": evidence_density,
        }
        case_results.extend(
            [
                EvalCaseResult(
                    case_name=f"{scenario_name}:{source_id}:availability",
                    passed=availability >= 1.0,
                    score=availability,
                    detail_json={"status": status},
                ),
                EvalCaseResult(
                    case_name=f"{scenario_name}:{source_id}:evidence_yield",
                    passed=evidence_yield >= 0.5,
                    score=round(evidence_yield, 4),
                    detail_json={
                        "evidence_count": evidence_count,
                        "evidence_density": evidence_density,
                    },
                ),
                EvalCaseResult(
                    case_name=f"{scenario_name}:{source_id}:citation_completeness",
                    passed=citation_completeness >= 0.5 if source_evidence else True,
                    score=round(citation_completeness, 4),
                    detail_json={"evidence_items": len(source_evidence)},
                ),
                EvalCaseResult(
                    case_name=f"{scenario_name}:{source_id}:trace_completeness",
                    passed=trace_completeness >= 0.8,
                    score=round(trace_completeness, 4),
                    detail_json={"trace_keys": sorted(list(trace.keys()))},
                ),
                EvalCaseResult(
                    case_name=f"{scenario_name}:{source_id}:query_fit",
                    passed=query_fit >= 0.5,
                    score=round(query_fit, 4),
                    detail_json={"query_type": query_type.value},
                ),
                EvalCaseResult(
                    case_name=f"{scenario_name}:{source_id}:operational_stability",
                    passed=operational >= 0.5,
                    score=round(operational, 4),
                    detail_json={
                        "retry_count": retry_count,
                        "warning_count": len(warnings),
                    },
                ),
                EvalCaseResult(
                    case_name=f"{scenario_name}:{source_id}:overall",
                    passed=overall >= 0.55,
                    score=overall,
                    detail_json=per_source_metrics[source_id],
                ),
            ]
        )
    return case_results, per_source_metrics


def _pick_source_traces(response: ToolResponse) -> dict[str, dict[str, Any]]:
    stage_order = {
        "search_source_documents": 1,
        "fetch_document_detail": 2,
        "extract_evidence_items": 3,
    }
    selected: dict[str, tuple[int, dict[str, Any]]] = {}
    for trace in response.traces:
        if not trace.source_id:
            continue
        rank = stage_order.get(trace.tool_name, 0)
        row = trace.model_dump(mode="json")
        current = selected.get(trace.source_id)
        if current is None or rank >= current[0]:
            selected[trace.source_id] = (rank, row)
    return {source_id: row for source_id, (_rank, row) in selected.items()}


def _citation_completeness(source_evidence: list[Any]) -> float:
    if not source_evidence:
        return 0.0
    required_keys = (
        "source_name",
        "source_id",
        "title",
        "url",
        "retrieved_at",
        "locator",
    )
    total = 0.0
    for item in source_evidence:
        metadata = item.citation.metadata if item.citation.metadata is not None else {}
        present = 0
        for key in required_keys:
            value = metadata.get(key)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            present += 1
        total += present / float(len(required_keys))
    return round(total / len(source_evidence), 6)


def _trace_completeness(trace: dict[str, Any]) -> float:
    required = (
        "tool_name",
        "status",
        "duration_ms",
        "http_calls",
        "page_count",
        "item_count",
        "evidence_count",
        "retry_count",
        "adapter_version",
    )
    present = 0
    for key in required:
        if key not in trace:
            continue
        value = trace.get(key)
        if value is None:
            continue
        present += 1
    return round(present / float(len(required)), 6)


def _query_fit_score(
    *,
    source_id: str,
    query_type: QueryType,
    query_context: QueryContext,
) -> float:
    if source_id == "user_input" and query_context.user_provided_sources:
        return 1.0
    compatibility = {
        QueryType.MACRO: {"world_bank"},
        QueryType.ENERGY: {"eia"},
        QueryType.FILING: {"sec_edgar"},
        QueryType.HEALTH: {"who_gho"},
        QueryType.GENERAL: {"user_input"},
    }
    if source_id in compatibility.get(query_type, set()):
        return 1.0
    return 0.5 if query_type == QueryType.GENERAL else 0.0


def _operational_stability_score(
    *,
    status: str,
    retry_count: int,
    warnings: list[Any],
) -> float:
    score = 1.0
    if status not in {"success", "partial"}:
        score -= 0.5
    score -= min(max(retry_count, 0) * 0.1, 0.3)
    score -= min(len(warnings) * 0.05, 0.2)
    return round(max(score, 0.0), 6)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
