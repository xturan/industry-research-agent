from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _load_live_inspection_module() -> Any:
    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "tmp"
        / "_source_quality_live_inspection.py"
    )
    spec = importlib.util.spec_from_file_location("source_quality_live_inspection", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_task_estimated_tavily_credits_counts_direct_fallback_metadata() -> None:
    module = _load_live_inspection_module()

    assert (
        module._task_estimated_tavily_credits(
            {
                "metadata": {
                    "budget_state": {"used_search_credits": 1},
                    "project_search_fallback": {"estimated_tavily_credits": 2},
                    "data_metrics_search_fallback": {"estimated_tavily_credits": 3},
                    "official_record_search_fallback": {"estimated_tavily_credits": 4},
                }
            }
        )
        == 10
    )


def test_source_class_coverage_reports_expected_covered_and_missing_classes() -> None:
    module = _load_live_inspection_module()

    coverage = module._source_class_coverage(
        {
            "task_family": "project_transaction",
            "source_cluster": "project_transaction_backbone",
        },
        [
            {
                "metadata": {"source_class": "project_list"},
            }
        ],
    )

    assert coverage == {
        "expected_source_classes": ["project_list", "tender_or_procurement"],
        "covered_source_classes": ["project_list"],
        "missing_source_classes": ["tender_or_procurement"],
        "coverage_complete": False,
    }
