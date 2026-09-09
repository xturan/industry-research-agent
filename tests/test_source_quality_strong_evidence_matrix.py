from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _load_matrix_module() -> Any:
    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "tmp"
        / "_source_quality_strong_evidence_matrix.py"
    )
    spec = importlib.util.spec_from_file_location("source_quality_strong_evidence_matrix", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_strong_evidence_matrix_classifies_core_gap_types(tmp_path: Path) -> None:
    module = _load_matrix_module()
    run_dir = tmp_path / "run"

    _write_json(
        run_dir / "batch_eval.json",
        {
            "batch_summary": {"live_status_counts": {"success": 1}},
            "source_coverage_gaps": [
                {
                    "source_class": "company_disclosure",
                    "affected_queries": ["C01"],
                },
                {
                    "source_class": "project_list",
                    "affected_queries": ["C01"],
                },
                {
                    "source_class": "statistics",
                    "affected_queries": ["C01"],
                },
                {
                    "source_class": "environmental_or_land_record",
                    "affected_queries": ["C01"],
                },
            ],
        },
    )
    _write_json(
        run_dir / "source_roadmap.json",
        {
            "adapter_candidates": [{"adapter_candidate": "C01_adapter_candidate"}],
            "source_profile_updates": [{"profile_name_or_candidate": "C01_profile"}],
            "requires_reopening_plan_items": [{"case_id": "C01"}],
        },
    )
    _write_json(run_dir / "live_summary.json", {"summary": {"success": 1}})
    _write_json(run_dir / "llm_audit_summary.json", {"summary": {"success": 1}})
    _write_json(
        run_dir / "per_query" / "C01.json",
        {
            "case_id": "C01",
            "level": "city",
            "query": "city query",
            "status": "success",
            "executed_tasks": [
                {
                    "task": {
                        "task_id": "enterprise_disclosure_1",
                        "task_family": "enterprise_disclosure",
                        "source_cluster": "official_disclosure_backbone",
                        "execution_bucket": "direct_structured_sources",
                    },
                    "status": "partial",
                    "metadata": {
                        "execution_state": "executed_without_evidence",
                        "evidence_count": 0,
                        "profiles_selected": ["cninfo"],
                    },
                },
                {
                    "task": {
                        "task_id": "project_transaction_1",
                        "task_family": "project_transaction",
                        "source_cluster": "project_transaction_backbone",
                        "execution_bucket": "direct_structured_sources",
                    },
                    "status": "partial",
                    "metadata": {
                        "execution_state": "executed_without_evidence",
                        "evidence_count": 0,
                    },
                },
                {
                    "task": {
                        "task_id": "data_metrics_1",
                        "task_family": "data_metrics",
                        "source_cluster": "structured_data_backbone",
                        "execution_bucket": "direct_structured_sources",
                    },
                    "status": "partial",
                    "metadata": {
                        "execution_state": "executed_without_evidence",
                        "evidence_count": 0,
                    },
                },
            ],
        },
    )
    _write_json(
        run_dir / "llm_audit" / "C01.json",
        {
            "status": "success",
            "audit": {
                "query_id": "C01",
                "verdict": "fail",
                "overall_score": 3,
                "covered_source_classes": ["local_government"],
                "missing_source_classes": [
                    "company_disclosure",
                    "project_list",
                    "statistics",
                    "environmental_or_land_record",
                ],
                "source_gap_analysis": {
                    "missing_critical_sources": [
                        "company disclosure filings",
                        "project transaction records",
                        "official statistics",
                        "environmental or land approvals",
                    ]
                },
            },
        },
    )

    matrix = module.build_matrix(run_dir)

    assert len(matrix["case_summaries"]) == 1
    assert len(matrix["gap_matrix"]) == 4
    assert matrix["baseline_summary"]["target_missing_counts"] == {
        "company_disclosure": 1,
        "environmental_or_land_record": 1,
        "project_list": 1,
        "statistics": 1,
    }
    assert (
        matrix["architecture_gate"]["phase0_decision"]
        == "phase1_can_proceed_without_public_contract_change"
    )
    rows_by_class = {row["source_class"]: row for row in matrix["gap_matrix"]}
    assert (
        rows_by_class["company_disclosure"]["recommended_remediation_type"]
        == "adapter_repair_and_entity_mapping"
    )
    assert (
        rows_by_class["project_list"]["recommended_remediation_type"]
        == "adapter_repair_and_local_profile_update"
    )
    assert (
        rows_by_class["statistics"]["recommended_remediation_type"]
        == "adapter_repair_and_structured_profile_update"
    )
    assert (
        rows_by_class["environmental_or_land_record"]["recommended_remediation_type"]
        == "new_source_family_or_profile"
    )


def test_strong_evidence_matrix_writes_json_csv_and_markdown(tmp_path: Path) -> None:
    module = _load_matrix_module()
    output_dir = tmp_path / "out"
    matrix = {
        "generated_at": "2026-04-29T00:00:00+00:00",
        "baseline_summary": {
            "batch_summary": {
                "live_status_counts": {"success": 1},
                "audit_verdict_counts": {"fail": 1},
                "audit_status_counts": {"success": 1},
            },
            "target_missing_counts": {"company_disclosure": 1},
            "matrix_status_counts": {"missing": 1},
        },
        "architecture_gate": {
            "phase0_decision": "phase1_can_proceed_without_public_contract_change"
        },
        "phase1_queue": [
            {
                "priority": "P0",
                "owner_lane": "eval_harness_worker",
                "work_item": "Normalize roadmap",
            }
        ],
        "gap_matrix": [
            {
                "case_id": "C01",
                "level": "city",
                "source_class": "company_disclosure",
                "matrix_status": "missing",
                "task": {"task_id": "enterprise_disclosure_1", "evidence_count": 0},
                "recommended_remediation_type": "adapter_repair_and_entity_mapping",
                "phase_hint": "Phase 2",
            }
        ],
    }

    paths = module.write_artifacts(matrix, output_dir)

    assert Path(paths["json"]).exists()
    assert Path(paths["csv"]).exists()
    assert Path(paths["markdown"]).exists()
    assert "company_disclosure" in Path(paths["markdown"]).read_text(encoding="utf-8")
