from __future__ import annotations

from pathlib import Path
from runpy import run_path

SCRIPT = run_path(
    str(Path(__file__).parents[1] / "scripts" / "compare_search_skill_strong_evidence.py")
)
SearchResult = SCRIPT["SearchResult"]
aggregate_by_family = SCRIPT["aggregate_by_family"]
evaluate_strong_evidence = SCRIPT["evaluate_strong_evidence"]
parse_anysearch_markdown = SCRIPT["parse_anysearch_markdown"]


def test_parse_anysearch_markdown_preserves_full_body() -> None:
    raw = """## Search Results (2 results, 10ms)

### 1. 项目环境影响评价受理公示
- **URL**: https://sthjt.xinjiang.gov.cn/eia/1.html
- 建设单位：示例公司。建设地点：若羌县。

### 2. 项目新闻
- **URL**: https://example.com/news
- 新闻正文。
"""

    results = parse_anysearch_markdown(raw, route="general")

    assert len(results) == 2
    assert results[0].title == "项目环境影响评价受理公示"
    assert "建设单位" in results[0].content
    assert results[0].route == "general"


def test_evaluate_strong_evidence_requires_primary_family_match() -> None:
    case = {
        "entity_terms": ["若羌", "锂"],
        "geo_terms": ["新疆"],
        "document_signals": ["环评", "受理公示"],
        "implementation_signals": ["建设单位", "建设地点", "总投资"],
        "strong_domain_hints": ["xinjiang.gov.cn"],
    }
    results = [
        SearchResult(
            title="若羌锂项目环评受理公示",
            url="https://sthjt.xinjiang.gov.cn/eia/1.html",
            content="新疆若羌锂项目，建设单位甲，建设地点乙，总投资10亿元。",
            route="general",
        ),
        SearchResult(
            title="若羌锂项目新闻",
            url="https://finance.eastmoney.com/news/1.html",
            content="新疆若羌锂项目环评新闻。",
            route="general",
        ),
    ]

    metrics = evaluate_strong_evidence(case, results)

    assert metrics["strong_evidence_count"] == 1
    assert metrics["primary_source_rate"] == 0.5
    assert metrics["weak_source_rate"] == 0.5
    assert metrics["implementation_detail_rate"] == 0.5


def test_aggregate_by_family_does_not_create_global_winner() -> None:
    metric = {
        "score": 80.0,
        "strong_evidence_rate": 0.8,
        "primary_source_rate": 0.9,
    }
    cases = [
        {
            "case": {"family": "enterprise_disclosure"},
            "providers": {
                "anysearch_skill": {"status": "success", "latency_ms": 10, "metrics": metric},
                "tavily_basic": {"status": "success", "latency_ms": 20, "metrics": metric},
            },
        }
    ]

    summary = aggregate_by_family(cases)

    assert set(summary) == {"enterprise_disclosure"}
    assert "global_winner" not in summary
    assert summary["enterprise_disclosure"]["provisional_winner"] in {
        "anysearch_skill",
        "tavily_basic",
    }
