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
        / "_source_quality_budget_diagnostics.py"
    )
    spec = importlib.util.spec_from_file_location(
        "source_quality_budget_diagnostics", path
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_budget_diagnostics_flags_credit_expansion_and_broad_local_fanout(
    tmp_path: Path,
) -> None:
    module = _load_module()
    run_dir = tmp_path / "run"

    _write_json(
        run_dir / "live_summary.json",
        {
            "summary": {
                "total_cases": 2,
                "estimated_tavily_credits": 80,
                "status_counts": {"success": 2},
            }
        },
    )
    _write_json(
        run_dir / "per_query" / "C01.json",
        {
            "case_id": "C01",
            "level": "city",
            "status": "success",
            "diagnostics": {"estimated_tavily_credits": 2},
            "executed_tasks": [
                {
                    "task": {
                        "task_family": "policy_direction",
                        "regional_level": "national",
                        "execution_bucket": "search_assisted_sources",
                        "include_domains": ["gov.cn", "ndrc.gov.cn"],
                    },
                    "status": "success",
                    "metadata": {
                        "budget_state": {"used_search_credits": 1},
                    },
                    "documents": [{"document_id": "policy_doc"}],
                },
                {
                    "task": {
                        "task_family": "project_transaction",
                        "regional_level": "city",
                        "execution_bucket": "direct_structured_sources",
                        "include_domains": ["ccgp.gov.cn", "ggzy.gov.cn"],
                    },
                    "status": "partial",
                    "metadata": {
                        "project_search_fallback": {
                            "estimated_tavily_credits": 2,
                            "search_statuses": ["success", "success"],
                        }
                    },
                    "documents": [],
                }
            ],
        },
    )
    _write_json(
        run_dir / "per_query" / "K09.json",
        {
            "case_id": "K09",
            "level": "county",
            "status": "success",
            "diagnostics": {"estimated_tavily_credits": 1},
            "executed_tasks": [
                {
                    "task": {
                        "task_family": "data_metrics",
                        "regional_level": "county",
                        "execution_bucket": "direct_structured_sources",
                        "include_domains": ["shenmu.gov.cn", "tjj.shenmu.gov.cn"],
                    },
                    "status": "success",
                    "metadata": {
                        "data_metrics_search_fallback": {
                            "estimated_tavily_credits": 1,
                            "search_statuses": ["success"],
                        }
                    },
                    "documents": [{"document_id": "doc_1"}],
                }
            ],
        },
    )

    diagnostics = module.build_budget_diagnostics(run_dir, baseline_credits=78)

    assert diagnostics["budget_policy"]["baseline_comparison"] == "exceeds_baseline"
    assert diagnostics["budget_policy"]["credit_delta"] == 2
    assert diagnostics["budget_flags"] == [
        {
            "reason_code": "credit_expansion_above_baseline",
            "severity": "warning",
            "message": "Estimated Tavily credits exceed the baseline by 2.",
            "baseline_credits": 78,
            "estimated_tavily_credits": 80,
            "credit_delta": 2,
        }
    ]
    assert diagnostics["by_task_family"]["project_transaction"] == {
        "estimated_tavily_credits": 2,
        "task_count": 1,
        "document_count": 0,
    }
    assert diagnostics["by_task_family"]["policy_direction"] == {
        "estimated_tavily_credits": 1,
        "task_count": 1,
        "document_count": 1,
    }
    assert diagnostics["by_task_family"]["data_metrics"] == {
        "estimated_tavily_credits": 1,
        "task_count": 1,
        "document_count": 1,
    }
    assert diagnostics["domain_targeting_flags"] == [
        {
            "case_id": "C01",
            "task_family": "project_transaction",
            "regional_level": "city",
            "reason_code": "broad_domains_before_targeted_local_domains",
            "include_domains": ["ccgp.gov.cn", "ggzy.gov.cn"],
            "estimated_tavily_credits": 2,
            "message": "Local lane used broad/national domains without a targeted local domain.",
        }
    ]
    assert diagnostics["recommendations"] == [
        {
            "priority": "P0",
            "component": "source_router",
            "recommended_change": (
                "Prefer targeted local-government, local public-resource, "
                "statistics, or official-record domains before increasing fanout."
            ),
            "affected_cases": ["C01"],
            "expected_effect": "reduce_cost_and_improve_precision",
        }
    ]
