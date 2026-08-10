# ruff: noqa: E501
"""Phase C.3.1 — Structured Compare acceptance (real LLM for structured side).

For each case:
- Legacy Editor1 output (formal) is taken from the existing B.2 real-run
  (Case1/Case2) or a fresh deterministic graph run (Case3, a longer
  multi-section task).
- Structured side runs per-section Strict-JSON generation through the REAL
  DeepSeek adapter (real_section_llm_call), validated + retried (max 1).
- Writes artifacts to data/tmp/c3_structured_compare/<case>/ and prints the
  comparison report.

Run:
  python scripts/c3_structured_compare_acceptance.py --cases case_01 case_02
  python scripts/c3_structured_compare_acceptance.py --cases case_01 case_02 --include-case3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.research_harness.eval_persistence import (
    RunEvaluationStore,
    build_evaluable_coverage_report,
)
from packages.research_harness.gap_retrieval import derive_gaps
from packages.research_harness.structured_compare import (
    real_section_llm_call,
    run_structured_compare,
)

REPO = Path(__file__).resolve().parents[1]
B2_ROOT = REPO / "data" / "tmp" / "b2_real_run_acceptance"
OUT_ROOT = REPO / "data" / "tmp" / "c3_structured_compare"

CASES = {
    "case_01": "2025 年合肥低空物流项目的落地进展、运营状态及官方证据",
    "case_02": "2025 年合肥低空经济相关上市公司的项目收入及订单贡献",
}

def _legacy_markdown_from_response(case_id: str) -> str:
    path = B2_ROOT / case_id / "response.json"
    if not path.exists():
        return ""
    response = json.loads(path.read_text(encoding="utf-8"))
    report = response.get("report_preview") or {}
    return str(
        report.get("report_markdown")
        or report.get("editor1_report_markdown")
        or ""
    )


def _load_b2_case(case_id: str):
    store_path = B2_ROOT / case_id / "evaluation_store.json"
    store = RunEvaluationStore.from_dict(
        json.loads(store_path.read_text(encoding="utf-8"))
    )
    coverage = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(coverage, store)
    legacy = _legacy_markdown_from_response(case_id)
    return store, coverage, gaps, legacy


def _synthetic_case3() -> tuple[RunEvaluationStore, dict, list, str]:
    """A longer multi-section store with approved claims + evidence.

    Legacy is a deterministic stand-in (section headings + claim texts) so the
    comparison has a real baseline; the structured side uses the real DeepSeek.
    """
    store = RunEvaluationStore("case3")
    sections = [
        ("sec_policy", "低空经济政策", "official_policy", ["政策要点"]),
        ("sec_procurement", "公共资源采购", "public_resource_transaction", ["中标项目"]),
        ("sec_disclosure", "上市公司披露", "company_disclosure", ["订单贡献"]),
        ("sec_industry", "产业统计", "statistics", ["产业规模"]),
    ]
    for section_id, title, family, fields in sections:
        slot_id = f"{section_id}.{family}.basis"
        store.record_claim_slots([{
            "slot_id": slot_id, "section_id": section_id, "criticality": "required",
            "min_evidence_items": 1, "min_raw_supporting_sources": 1,
            "field_requirements": {"mandatory": [], "any_of": fields},
            "source_obligations": {"required_families": [family],
                                   "primary_source_required": True},
        }])
        store.record_search_event({
            "search_event_id": f"se_{section_id}", "run_id": "case3",
            "slot_ids": [slot_id], "query": title, "source_family": family,
            "provider": "anysearch", "status": "completed", "result_count": 1,
            "accepted_source_ids": [f"src_{section_id}"],
            "schema_version": "search_event_v1",
        })
        for j in range(2):
            ev_id = f"ev_{section_id}_{j}"
            store.record_evidence_unit({
                "evidence_id": ev_id, "run_id": "case3",
                "source_id": f"src_{section_id}", "source_family": family,
                "supports_slot_ids": [slot_id],
                "quoted_span": f"2025年{section_id}相关数据{j}",
                "key_fields": {f: {"status": "present", "value": f"数据{j}"}
                               for f in fields},
                "key_field_extraction_status": "completed",
                "schema_version": "evidence_unit_v2",
            })
            store.record_claim_card({
                "claim_id": f"claim_{section_id}_{j}", "primary_slot_id": slot_id,
                "slot_ids": [slot_id], "evidence_ids": [ev_id],
                "claim_type": "factual", "epistemic_status": "supported",
                "assertion_level": "supported",
                "max_allowed_assertion_level": "3",  # Phase A level -> supported
                "approval_status": "approved",
                "limitations": [f"未披露{section_id}细分数据{j}"],
                "text": f"{title}显示{section_id}相关指标为{j}。",
                "idempotency_key": f"claim:{section_id}_{j}",
                "schema_version": "claim_card_v1",
            })
    coverage = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(coverage, store)
    legacy_parts = ["# 2025 年低空经济产业综合研究"]
    for _section_id, title, _family, _fields in sections:
        legacy_parts.append(f"## {title}")
        legacy_parts.append(f"{title}显示相关指标存在。")
    legacy = "\n\n".join(legacy_parts)
    return store, coverage, gaps, legacy


def _synthetic_case4() -> tuple[RunEvaluationStore, dict, list, str]:
    """Holdout multi-section store (different theme: 新能源汽车). Run ONCE."""
    store = RunEvaluationStore("case4")
    sections = [
        ("sec_policy", "新能源汽车政策", "official_policy", ["政策要点"]),
        ("sec_build", "产能建设", "public_resource_transaction", ["产能"]),
        ("sec_disclosure", "上市公司披露", "company_disclosure", ["销量"]),
    ]
    for section_id, title, family, fields in sections:
        slot_id = f"{section_id}.{family}.basis"
        store.record_claim_slots([{
            "slot_id": slot_id, "section_id": section_id, "criticality": "required",
            "min_evidence_items": 1, "min_raw_supporting_sources": 1,
            "field_requirements": {"mandatory": [], "any_of": fields},
            "source_obligations": {"required_families": [family],
                                   "primary_source_required": True},
        }])
        store.record_search_event({
            "search_event_id": f"se_{section_id}", "run_id": "case4",
            "slot_ids": [slot_id], "query": title, "source_family": family,
            "provider": "anysearch", "status": "completed", "result_count": 1,
            "accepted_source_ids": [f"src_{section_id}"],
            "schema_version": "search_event_v1",
        })
        for j in range(2):
            ev_id = f"ev_{section_id}_{j}"
            store.record_evidence_unit({
                "evidence_id": ev_id, "run_id": "case4",
                "source_id": f"src_{section_id}", "source_family": family,
                "supports_slot_ids": [slot_id],
                "quoted_span": f"2025年{section_id}披露数据{j}",
                "key_fields": {f: {"status": "present", "value": f"数据{j}"}
                               for f in fields},
                "key_field_extraction_status": "completed",
                "schema_version": "evidence_unit_v2",
            })
            store.record_claim_card({
                "claim_id": f"claim_{section_id}_{j}", "primary_slot_id": slot_id,
                "slot_ids": [slot_id], "evidence_ids": [ev_id],
                "claim_type": "factual", "epistemic_status": "supported",
                "assertion_level": "supported",
                "max_allowed_assertion_level": "3",
                "approval_status": "approved",
                "limitations": [f"未披露{section_id}细分数据{j}"],
                "text": f"{title}显示{section_id}指标为{j}。",
                "idempotency_key": f"claim:{section_id}_{j}",
                "schema_version": "claim_card_v1",
            })
    coverage = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(coverage, store)
    legacy_parts = ["# 2025 年新能源汽车产业综合研究"]
    for _section_id, title, _family, _fields in sections:
        legacy_parts.append(f"## {title}")
        legacy_parts.append(f"{title}显示相关指标存在。")
    legacy = "\n\n".join(legacy_parts)
    return store, coverage, gaps, legacy


def _synthetic_case5() -> tuple[RunEvaluationStore, dict, list, str]:
    """C.3.2 Assignment Holdout: includes duplicate/subsumed claims so the
    Section–Claim Assignment must suppress them and keep eligible coverage high."""
    store = RunEvaluationStore("case5")
    sections = [
        ("sec_policy", "低空经济政策", "official_policy", ["政策要点"]),
        ("sec_build", "项目建设", "public_resource_transaction", ["中标项目"]),
        ("sec_disclosure", "上市公司披露", "company_disclosure", ["订单"]),
    ]
    for section_id, title, family, fields in sections:
        slot_id = f"{section_id}.{family}.basis"
        store.record_claim_slots([{
            "slot_id": slot_id, "section_id": section_id, "criticality": "required",
            "min_evidence_items": 1, "min_raw_supporting_sources": 1,
            "field_requirements": {"mandatory": [], "any_of": fields},
            "source_obligations": {"required_families": [family],
                                   "primary_source_required": True},
        }])
        store.record_search_event({
            "search_event_id": f"se_{section_id}", "run_id": "case5",
            "slot_ids": [slot_id], "query": title, "source_family": family,
            "provider": "anysearch", "status": "completed", "result_count": 1,
            "accepted_source_ids": [f"src_{section_id}"],
            "schema_version": "search_event_v1",
        })
        # evidence + 2 distinct claims + 1 duplicate
        for j in range(2):
            ev_id = f"ev_{section_id}_{j}"
            store.record_evidence_unit({
                "evidence_id": ev_id, "run_id": "case5",
                "source_id": f"src_{section_id}", "source_family": family,
                "supports_slot_ids": [slot_id],
                "quoted_span": f"2025年{section_id}披露{j}",
                "quote_verification_status": "verified",
                "key_fields": {f: {"status": "present", "value": f"数据{j}"}
                               for f in fields},
                "key_field_extraction_status": "completed",
                "schema_version": "evidence_unit_v2",
            })
        texts = [
            f"{title}显示{section_id}核心指标为A。",
            f"{title}显示{section_id}已形成配套场景。",
            f"{title}显示{section_id}核心指标为A（重复表述）。",
        ]
        for j, text in enumerate(texts):
            store.record_claim_card({
                "claim_id": f"claim_{section_id}_{j}", "primary_slot_id": slot_id,
                "slot_ids": [slot_id], "evidence_ids": [f"ev_{section_id}_{j % 2}"],
                "claim_type": "factual", "epistemic_status": "supported",
                "assertion_level": "supported", "max_allowed_assertion_level": "3",
                "approval_status": "approved",
                "limitations": [f"未披露{section_id}细分{j}"] if j == 1 else [],
                "text": text,
                "idempotency_key": f"claim:{section_id}_{j}",
                "schema_version": "claim_card_v1",
            })
    coverage = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(coverage, store)
    legacy_parts = ["# 2025 年低空经济产业综合研究（Assignment Holdout）"]
    for _section_id, title, _family, _fields in sections:
        legacy_parts.append(f"## {title}")
        legacy_parts.append(f"{title}显示相关指标存在。")
    legacy = "\n\n".join(legacy_parts)
    return store, coverage, gaps, legacy


def _synthetic_case6() -> tuple[RunEvaluationStore, dict, list, str]:
    """C.3.3 Synthesis Holdout: policy + project + disclosure + industry + gap."""
    store = RunEvaluationStore("case6")
    sections = [
        ("sec_policy", "低空经济政策", "official_policy", ["政策要点"]),
        ("sec_build", "项目建设", "public_resource_transaction", ["中标项目"]),
        ("sec_disclosure", "上市公司披露", "company_disclosure", ["订单"]),
        ("sec_industry", "产业统计", "statistics", ["产业规模"]),
    ]
    for si, (section_id, title, family, fields) in enumerate(sections):
        slot_id = f"{section_id}.{family}.basis"
        store.record_claim_slots([{
            "slot_id": slot_id, "section_id": section_id, "criticality": "required",
            "min_evidence_items": 1, "min_raw_supporting_sources": 1,
            "field_requirements": {"mandatory": [], "any_of": fields},
            "source_obligations": {"required_families": [family],
                                   "primary_source_required": True},
        }])
        store.record_search_event({
            "search_event_id": f"se_{section_id}", "run_id": "case6",
            "slot_ids": [slot_id], "query": title, "source_family": family,
            "provider": "anysearch", "status": "completed", "result_count": 1,
            "accepted_source_ids": [f"src_{section_id}"],
            "schema_version": "search_event_v1",
        })
        for j in range(2):
            ev_id = f"ev_{section_id}_{j}"
            store.record_evidence_unit({
                "evidence_id": ev_id, "run_id": "case6",
                "source_id": f"src_{section_id}", "source_family": family,
                "supports_slot_ids": [slot_id],
                "content_cluster_id": f"cl_{section_id}_{j}",
                "quoted_span": f"2025年{section_id}披露{j}",
                "quote_verification_status": "verified",
                "key_fields": {f: {"status": "present", "value": f"数据{j}"}
                               for f in fields},
                "key_field_extraction_status": "completed",
                "schema_version": "evidence_unit_v2",
            })
        store.record_claim_card({
            "claim_id": f"claim_{section_id}_policy", "primary_slot_id": slot_id,
            "slot_ids": [slot_id], "evidence_ids": [f"ev_{section_id}_0"],
            "claim_type": "factual", "epistemic_status": "supported",
            "assertion_level": "supported", "max_allowed_assertion_level": "3",
            "approval_status": "approved", "limitations": [],
            "text": f"{title}提出{section_id}相关支持方向。" if si == 0 else
                   f"{title}显示{section_id}已有具体落地动作。",
            "idempotency_key": f"claim:{section_id}_policy",
            "schema_version": "claim_card_v1",
        })
        store.record_claim_card({
            "claim_id": f"claim_{section_id}_scenario", "primary_slot_id": slot_id,
            "slot_ids": [slot_id], "evidence_ids": [f"ev_{section_id}_1"],
            "claim_type": "factual", "epistemic_status": "supported",
            "assertion_level": "supported", "max_allowed_assertion_level": "3",
            "approval_status": "approved",
            "limitations": [f"未披露{section_id}细分指标"],
            "text": f"{title}相关应用场景已落地，但未披露细分指标。",
            "idempotency_key": f"claim:{section_id}_scenario",
            "schema_version": "claim_card_v1",
        })
    # an evidence gap: statistics slot left unsatisfied on purpose
    coverage = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(coverage, store)
    legacy_parts = ["# 2025 年低空经济产业综合研究（Synthesis Holdout）"]
    for _section_id, title, _family, _fields in sections:
        legacy_parts.append(f"## {title}")
        legacy_parts.append(f"{title}显示相关指标存在。")
    legacy = "\n\n".join(legacy_parts)
    return store, coverage, gaps, legacy


def _case_inputs(case_id: str, *, include_case3: bool, include_case4: bool,
                 include_case5: bool, include_case6: bool):
    if case_id == "case_03" and include_case3:
        return _synthetic_case3()
    if case_id == "case_04" and include_case4:
        return _synthetic_case4()
    if case_id == "case_05" and include_case5:
        return _synthetic_case5()
    if case_id == "case_06" and include_case6:
        return _synthetic_case6()
    return _load_b2_case(case_id)


def run_case(case_id: str, *, use_fewshot: bool, include_case3: bool,
             include_case4: bool, include_case5: bool, include_case6: bool) -> dict:
    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    mode = "few_shot" if use_fewshot else "zero_shot"
    print(f"[{case_id}/{mode}] preparing inputs ...")
    store, coverage, gaps, legacy = _case_inputs(
        case_id, include_case3=include_case3, include_case4=include_case4,
        include_case5=include_case5, include_case6=include_case6)
    print(f"[{case_id}/{mode}] structured compare (real DeepSeek, "
          f"{len(coverage.get('slot_reports', []))} slots) ...")
    result = run_structured_compare(
        store=store,
        coverage_report=coverage,
        research_gaps=gaps,
        legacy_markdown=legacy,
        llm_call=real_section_llm_call,
        run_id=f"{case_id}__{mode}",
        output_dir=str(OUT_ROOT),
        max_retries=1,
        use_fewshot=use_fewshot,
    )
    cr = result["comparison_report"]
    print(json.dumps(cr, ensure_ascii=False, indent=2))
    return {"case": case_id, "mode": mode, "comparison_report": cr}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", default=list(CASES))
    ap.add_argument("--mode", choices=["both", "zero_shot", "few_shot"],
                    default="both", help="zero-shot v2 vs few-shot v2 ablation")
    ap.add_argument("--include-case3", action="store_true",
                    help="also run Case3 (synthetic multi-section calibration)")
    ap.add_argument("--include-case4", action="store_true",
                    help="also run Case4 (synthetic multi-section holdout, once)")
    ap.add_argument("--include-case5", action="store_true",
                    help="also run Case5 (C.3.2 assignment holdout, once)")
    ap.add_argument("--include-case6", action="store_true",
                    help="also run Case6 (C.3.3 synthesis holdout, once)")
    args = ap.parse_args()

    valid = set(CASES)
    if args.include_case3:
        valid.add("case_03")
    if args.include_case4:
        valid.add("case_04")
    if args.include_case5:
        valid.add("case_05")
    if args.include_case6:
        valid.add("case_06")

    results = []
    ran: set[str] = set()
    for case_id in args.cases:
        if case_id not in valid:
            raise SystemExit(f"unknown case {case_id}")
        if case_id in ran:
            continue
        for use_fewshot in (False, True) if args.mode == "both" else (
            (args.mode == "few_shot",)
        ):
            results.append(run_case(
                case_id, use_fewshot=use_fewshot,
                include_case3=args.include_case3, include_case4=args.include_case4,
                include_case5=args.include_case5, include_case6=args.include_case6))
        ran.add(case_id)
    for cid, enabled in (("case_03", args.include_case3),
                         ("case_04", args.include_case4),
                         ("case_05", args.include_case5),
                         ("case_06", args.include_case6)):
        if enabled and cid not in ran:
            for use_fewshot in (False, True) if args.mode == "both" else (
                (args.mode == "few_shot",)
            ):
                results.append(run_case(
                    cid, use_fewshot=use_fewshot,
                    include_case3=args.include_case3, include_case4=args.include_case4,
                    include_case5=args.include_case5, include_case6=args.include_case6))
            ran.add(cid)

    (OUT_ROOT / "C3_STRUCTURED_COMPARE_ACCEPTANCE.md").write_text(
        "# Phase C.3.1 Structured Compare Calibration (Prompt v2)\n\n"
        + json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[DONE] -> {OUT_ROOT}")


if __name__ == "__main__":
    main()
