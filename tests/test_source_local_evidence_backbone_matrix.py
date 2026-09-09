from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _load_module() -> Any:
    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "tmp"
        / "_source_local_evidence_backbone_matrix.py"
    )
    spec = importlib.util.spec_from_file_location(
        "source_local_evidence_backbone_matrix", path
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_backbone_matrix_groups_local_evidence_failures(tmp_path: Path) -> None:
    module = _load_module()
    run_dir = tmp_path / "run"
    audit_dir = run_dir / "llm_audit"
    audit_dir.mkdir(parents=True)
    (run_dir / "batch_eval.json").write_text(
        json.dumps(
            {
                "batch_summary": {
                    "total_queries": 3,
                    "live_status_counts": {"success": 3},
                    "audit_verdict_counts": {"blocker": 1, "fail": 2},
                    "total_estimated_tavily_credits": 78,
                },
                "source_coverage_gaps": [
                    {
                        "source_class": "local_government",
                        "missing_count": 2,
                        "affected_queries": ["C01", "K07"],
                    },
                    {
                        "source_class": "project_list",
                        "missing_count": 2,
                        "affected_queries": ["C01", "K07"],
                    },
                    {
                        "source_class": "statistics",
                        "missing_count": 1,
                        "affected_queries": ["K09"],
                    },
                    {
                        "source_class": "environmental_or_land_record",
                        "missing_count": 1,
                        "affected_queries": ["C01"],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "live_summary.json").write_text(
        json.dumps(
            {
                "summary": {
                    "total_cases": 3,
                    "status_counts": {"success": 3},
                    "estimated_tavily_credits": 78,
                    "average_latency_ms": 34000,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "source_roadmap.json").write_text(
        json.dumps(
            {
                "source_profile_updates": [
                    {
                        "affected_queries": ["C01"],
                        "profile_name_or_candidate": "hefei local profile",
                        "reason": "PDF extraction failed for public resource pages.",
                    }
                ],
                "requires_reopening_plan_items": [
                    {
                        "case_id": "C01",
                        "recommended_next_step": "Add city-level project and land profiles.",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (audit_dir / "C01.json").write_text(
        json.dumps(
            {
                "status": "success",
                "audit": {
                    "query_id": "C01",
                    "verdict": "blocker",
                    "overall_score": 41,
                    "missing_source_classes": [
                        "local_government",
                        "project_list",
                        "environmental_or_land_record",
                    ],
                    "evidence_pipeline_improvement": [
                        {"component": "extraction", "problem": "PDF download failed"}
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (audit_dir / "K09.json").write_text(
        json.dumps(
            {
                "status": "success",
                "audit": {
                    "query_id": "K09",
                    "verdict": "fail",
                    "overall_score": 58,
                    "missing_source_classes": ["statistics"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    matrix = module.build_backbone_matrix(run_dir, credit_baseline=69)

    by_id = {item["backbone_id"]: item for item in matrix["backbones"]}
    assert set(by_id) >= {
        "local_government",
        "project_public_resource",
        "statistics_fiscal",
        "environmental_land_record",
        "extraction_reliability",
        "budget_lane_scheduling",
    }
    assert by_id["local_government"]["affected_cases"] == ["C01", "K07"]
    assert by_id["project_public_resource"]["affected_cases"] == ["C01", "K07"]
    assert by_id["statistics_fiscal"]["affected_cases"] == ["K09"]
    assert by_id["environmental_land_record"]["affected_cases"] == ["C01"]
    assert by_id["extraction_reliability"]["affected_cases"] == ["C01"]
    assert by_id["budget_lane_scheduling"]["active"] is True
    assert by_id["budget_lane_scheduling"]["credit_delta"] == 9
    assert matrix["case_backbone_map"]["C01"] == [
        "local_government",
        "project_public_resource",
        "environmental_land_record",
        "extraction_reliability",
        "budget_lane_scheduling",
    ]
    assert matrix["next_gate"]["audit_blockers"] == 0
    assert matrix["next_gate"]["statistics_missing_maximum"] == 3
