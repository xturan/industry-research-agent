from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _load_module() -> Any:
    path = Path(__file__).resolve().parents[1] / "scripts" / "graph_provider_backed_smoke_matrix.py"
    spec = importlib.util.spec_from_file_location("graph_provider_backed_smoke_matrix", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_live_summary_counts_modes_and_obligation_gaps() -> None:
    module = _load_module()
    summaries = [
        {
            "case_id": "P01",
            "status": "succeeded",
            "decision": "PASS",
            "planner_mode": "semantic_provider",
            "planner_reason": "semantic_plan_accepted",
            "planner_deterministic_fallback": False,
            "estimated_credits": 6,
            "latency_ms": 1000.0,
            "retry_rate": 0.0,
            "unstable_search_rate": 0.0,
            "quality_scores": {"final_score": 0.9},
            "required_obligation_coverage": [
                {"obligation_id": "obl_policy_primary", "covered": True}
            ],
        },
        {
            "case_id": "L01",
            "status": "succeeded",
            "decision": "PASS",
            "planner_mode": "semantic_provider",
            "planner_reason": "semantic_plan_repaired",
            "planner_deterministic_fallback": False,
            "estimated_credits": 7,
            "latency_ms": 2000.0,
            "retry_rate": 0.25,
            "unstable_search_rate": 0.4,
            "quality_scores": {"final_score": 0.8},
            "required_obligation_coverage": [
                {"obligation_id": "obl_policy_primary", "covered": True},
                {"obligation_id": "obl_location_precision", "covered": False},
            ],
        },
        {
            "case_id": "D01",
            "status": "succeeded",
            "decision": "HUMAN_REVIEW",
            "planner_mode": "deterministic_fallback",
            "planner_reason": "provider_error:ProviderParseError",
            "planner_deterministic_fallback": True,
            "estimated_credits": 5,
            "latency_ms": 1500.0,
            "retry_rate": 0.1,
            "unstable_search_rate": 0.1,
            "quality_scores": {"final_score": 0.6},
            "required_obligation_coverage": [
                {"obligation_id": "obl_company_disclosure", "covered": True}
            ],
        },
    ]

    summary = module._build_live_summary(summaries)

    assert summary["total_cases"] == 3
    assert summary["status_counts"] == {"succeeded": 3}
    assert summary["decision_counts"] == {"PASS": 2, "HUMAN_REVIEW": 1}
    assert summary["planner_mode_counts"] == {
        "semantic_provider": 2,
        "deterministic_fallback": 1,
    }
    assert summary["semantic_repaired_count"] == 1
    assert summary["deterministic_fallback_count"] == 1
    assert summary["estimated_tavily_credits"] == 18
    assert summary["average_latency_ms"] == 1500.0
    assert summary["average_final_score"] == 0.767
    assert summary["max_retry_rate"] == 0.25
    assert summary["max_unstable_search_rate"] == 0.4
    assert summary["unstable_case_ids"] == ["L01"]
    assert summary["uncovered_obligation_case_ids"] == ["L01"]


def test_load_cases_from_json_file(tmp_path: Path) -> None:
    module = _load_module()
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            [
                {
                    "case_id": "X01",
                    "label": "edge_combo",
                    "query": "2025年合肥低空经济上市公司年报披露与地方政策项目公示官方来源",
                    "max_rounds": 3,
                    "max_loop_count": 2,
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    cases = module._load_cases(str(path))

    assert cases == [
        {
            "case_id": "X01",
            "label": "edge_combo",
            "query": "2025年合肥低空经济上市公司年报披露与地方政策项目公示官方来源",
            "max_rounds": 3,
            "max_loop_count": 2,
        }
    ]
