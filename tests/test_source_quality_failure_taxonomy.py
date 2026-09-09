from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _load_taxonomy_module() -> Any:
    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "tmp"
        / "_source_quality_failure_taxonomy.py"
    )
    spec = importlib.util.spec_from_file_location("source_quality_failure_taxonomy", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_failure_taxonomy_groups_general_failure_families(tmp_path: Path) -> None:
    module = _load_taxonomy_module()
    run_dir = tmp_path / "run"
    audit_dir = run_dir / "llm_audit"
    audit_dir.mkdir(parents=True)
    (run_dir / "batch_eval.json").write_text(
        json.dumps(
            {
                "batch_summary": {
                    "total_queries": 2,
                    "audit_verdict_counts": {"fail": 1, "blocker": 1},
                },
                "source_coverage_gaps": [
                    {
                        "source_class": "project_list",
                        "missing_count": 2,
                        "affected_queries": ["C01", "M03"],
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
    (run_dir / "source_roadmap.json").write_text(
        json.dumps(
            {
                "adapter_candidates": [
                    {
                        "affected_queries": ["M03"],
                        "adapter_candidate": "CAAC low-altitude regulator profile",
                    }
                ]
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
                    "verdict": "fail",
                    "overall_score": 53,
                    "missing_source_classes": [
                        "project_list",
                        "environmental_or_land_record",
                    ],
                    "source_gap_analysis": {
                        "source_level_mismatch": {"severity": "high"},
                        "overused_weak_sources": ["generic local page"],
                    },
                    "implementation_recommendation": {
                        "blocker_reason": "Missing local project and land records."
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (audit_dir / "M03.json").write_text(
        json.dumps(
            {
                "status": "success",
                "audit": {
                    "query_id": "M03",
                    "verdict": "blocker",
                    "overall_score": 2,
                    "missing_source_classes": [
                        "association_enhancement",
                        "project_transaction_backbone",
                    ],
                    "evidence_pipeline_improvement": [
                        {"component": "extraction", "problem": "PDF extraction failed"}
                    ],
                    "implementation_recommendation": {
                        "blocker_reason": "Missing CAAC and project evidence."
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    taxonomy = module.build_failure_taxonomy(run_dir)

    family_ids = {family["family_id"] for family in taxonomy["failure_families"]}
    assert "local_project_public_resource" in family_ids
    assert "local_official_record" in family_ids
    assert "coverage_lane_planner" in family_ids
    assert "extraction_reliability" in family_ids
    assert "evidence_sufficiency_scoring" in family_ids
    assert taxonomy["per_case"]["C01"]["family_ids"] == [
        "local_project_public_resource",
        "local_official_record",
        "evidence_sufficiency_scoring",
    ]
    assert taxonomy["next_gate"]["audit_blockers"] == 0
    assert taxonomy["next_gate"]["weak_or_pass_minimum"] == 6
