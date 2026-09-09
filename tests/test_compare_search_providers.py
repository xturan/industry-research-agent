from __future__ import annotations

from pathlib import Path
from runpy import run_path

SCRIPT = run_path(str(Path(__file__).parents[1] / "scripts" / "compare_search_providers.py"))
NormalizedResult = SCRIPT["NormalizedResult"]
aggregate = SCRIPT["aggregate"]
evaluate_results = SCRIPT["evaluate_results"]
parse_anysearch_response = SCRIPT["parse_anysearch_response"]


def test_parse_anysearch_response_reads_envelope_and_content() -> None:
    results, metadata = parse_anysearch_response(
        {
            "code": 0,
            "request_id": "req-1",
            "data": {
                "results": [
                    {
                        "title": "安徽低空经济实施方案",
                        "url": "https://www.ah.gov.cn/policy/1.html",
                        "snippet": "政策摘要",
                        "content": "政策正文",
                    }
                ],
                "metadata": {"total_results": 1, "search_time_ms": 120},
            },
        }
    )

    assert results[0].title == "安徽低空经济实施方案"
    assert results[0].content == "政策正文"
    assert metadata["request_id"] == "req-1"
    assert metadata["total_results"] == 1


def test_evaluate_results_measures_source_and_returned_depth() -> None:
    case = {
        "keywords": ["安徽", "低空经济", "项目"],
        "required_geo_terms": ["安徽"],
        "expected_source_classes": ["official_policy"],
    }
    results = [
        NormalizedResult(
            title="安徽低空经济项目实施方案",
            url="https://www.ah.gov.cn/policy/1.html",
            snippet="安徽低空经济项目",
            content="安徽低空经济项目" * 200,
        )
    ]

    metrics = evaluate_results(case, results)

    assert metrics["keyword_coverage"] == 1.0
    assert metrics["official_result_rate"] == 1.0
    assert metrics["geo_match_rate"] == 1.0
    assert metrics["expected_source_class_coverage"] == 1.0
    assert metrics["deep_content_rate"] == 1.0
    assert metrics["scores"]["overall"] > 90


def test_aggregate_preserves_errors_and_selects_dimension_winner() -> None:
    metric_template = {
        "result_count": 1,
        "official_result_rate": 1.0,
        "unique_domain_rate": 1.0,
        "keyword_coverage": 1.0,
        "avg_content_chars": 2000.0,
        "deep_content_rate": 1.0,
        "source_classes": ["official_policy"],
        "scores": {
            "relevance": 90.0,
            "source_quality": 90.0,
            "returned_depth": 90.0,
            "overall": 90.0,
        },
    }
    case_runs = [
        {
            "providers": {
                "anysearch": {
                    "status": "success",
                    "latency_ms": 100,
                    "metrics": metric_template,
                },
                "tavily_basic": {
                    "status": "error",
                    "latency_ms": 50,
                    "error": "quota",
                },
            }
        }
    ]

    summary = aggregate(case_runs, ["anysearch", "tavily_basic"])

    assert summary["providers"]["anysearch"]["success_count"] == 1
    assert summary["providers"]["tavily_basic"]["error_count"] == 1
    assert summary["dimension_winners"]["overall"] == "anysearch"
