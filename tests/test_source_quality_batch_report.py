from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _load_batch_report_module() -> Any:
    path = (
        Path(__file__).resolve().parents[1] / "data" / "tmp" / "_source_quality_batch_report.py"
    )
    spec = importlib.util.spec_from_file_location("source_quality_batch_report", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_batch_report_separates_schema_diagnostics_from_blockers(tmp_path: Path) -> None:
    module = _load_batch_report_module()
    run_dir = tmp_path / "run"

    _write_json(
        run_dir / "per_query" / "C01.json",
        {"case_id": "C01", "level": "city", "status": "success", "diagnostics": {}},
    )
    _write_json(
        run_dir / "per_query" / "K09.json",
        {"case_id": "K09", "level": "county", "status": "success", "diagnostics": {}},
    )
    _write_json(
        run_dir / "llm_audit" / "C01.json",
        {
            "status": "invalid_schema",
            "case_id": "C01",
            "query_id": "C01",
            "reason_code": "missing_required_fields",
            "missing_fields": ["query_id", "verdict"],
            "finish_reason": "length",
            "raw_content_excerpt": "{}",
            "retry_attempted": True,
            "retry_recovered": False,
            "audit": {
                "query_id": "C01",
                "verdict": "fail",
                "missing_source_classes": ["company_disclosure"],
                "implementation_recommendation": {"blocker_reason": "schema failure"},
            },
        },
    )
    _write_json(
        run_dir / "llm_audit" / "K09.json",
        {
            "status": "success",
            "audit": {
                "query_id": "K09",
                "verdict": "blocker",
                "missing_source_classes": ["statistics"],
                "implementation_recommendation": {
                    "blocker_reason": "real source blocker",
                    "needs_production_code_change": True,
                },
            },
        },
    )

    audits = module._audit_by_case(run_dir)
    diagnostics = module._audit_shape_diagnostics(audits)
    missing_source_classes = module._collect_missing_source_classes(audits)
    blockers = module._build_blockers(audits)
    by_level = module._by_level(
        [
            {"case_id": "C01", "level": "city", "status": "success"},
            {"case_id": "K09", "level": "county", "status": "success"},
        ],
        audits,
    )

    assert diagnostics == [
        {
            "query_id": "C01",
            "status": "invalid_schema",
            "reason_code": "missing_required_fields",
            "missing_fields": ["query_id", "verdict"],
            "finish_reason": "length",
            "retry_attempted": True,
            "retry_recovered": False,
            "raw_content_excerpt": "{}",
        }
    ]
    assert missing_source_classes == [
        {
            "source_class": "statistics",
            "missing_count": 1,
            "affected_queries": ["K09"],
        }
    ]
    assert blockers == [
        {
            "query_id": "K09",
            "reason": "real source blocker",
            "requires_production_code_change": True,
        }
    ]
    assert by_level["city"]["audit_verdict_counts"] == {}
    assert by_level["county"]["audit_verdict_counts"] == {"blocker": 1}


def test_phase3_batch_report_separates_coverage_from_sufficiency_gaps(
    tmp_path: Path,
) -> None:
    module = _load_batch_report_module()
    run_dir = tmp_path / "run"

    _write_json(
        run_dir / "per_query" / "P04.json",
        {"case_id": "P04", "level": "province", "status": "success", "diagnostics": {}},
    )
    _write_json(
        run_dir / "llm_audit" / "P04.json",
        {
            "status": "success",
            "audit": {
                "query_id": "P04",
                "verdict": "fail",
                "missing_source_classes": [],
                "covered_source_classes": [
                    "official_policy",
                    "statistics",
                    "project_list",
                    "company_disclosure",
                ],
                "dimension_scores": {
                    "source_coverage": 18,
                    "evidence_sufficiency": 6,
                    "regional_granularity": 4,
                },
                "source_gap_analysis": {
                    "missing_critical_sources": [
                        {
                            "source_class": "local_government",
                            "why_needed": (
                                "province distribution claim needs non-anchor-city "
                                "official evidence"
                            ),
                            "impact_if_missing": "high",
                            "affected_claims": ["安徽是否形成全省多地协同"],
                        }
                    ],
                    "source_level_mismatch": {
                        "expected_level": "province",
                        "actual_sources_used": ["province", "hefei_anchor_city"],
                        "problem": (
                            "Only anchor-city evidence is present for a province "
                            "distribution claim."
                        ),
                        "severity": "high",
                    },
                },
            },
        },
    )

    audits = module._audit_by_case(run_dir)

    assert module._collect_missing_source_classes(audits) == []
    assert module._collect_evidence_sufficiency_gaps(audits) == [
        {
            "query_id": "P04",
            "gap_type": "missing_critical_source",
            "severity": "high",
            "detail": "province distribution claim needs non-anchor-city official evidence",
            "source_class": "local_government",
            "affected_claims": ["安徽是否形成全省多地协同"],
        },
        {
            "query_id": "P04",
            "gap_type": "source_level_mismatch",
            "severity": "high",
            "detail": "Only anchor-city evidence is present for a province distribution claim.",
            "source_class": None,
            "affected_claims": [],
        },
        {
            "query_id": "P04",
            "gap_type": "claim_support_weak",
            "severity": "medium",
            "detail": "evidence_sufficiency score 6 is below 12 while source classes are present.",
            "source_class": None,
            "affected_claims": [],
        },
        {
            "query_id": "P04",
            "gap_type": "regional_granularity_weak",
            "severity": "medium",
            "detail": "regional_granularity score 4 is below 7.",
            "source_class": None,
            "affected_claims": [],
        },
    ]
