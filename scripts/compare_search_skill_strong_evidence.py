from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

import requests

from packages.sources.enums import ToolStatus
from packages.sources.search_discovery import (
    TavilySearchAdapter,
    TavilySearchRequest,
    TavilySearchSettings,
)

ANYSEARCH_MCP_ENDPOINT = "https://api.anysearch.com/mcp"
DEFAULT_CASE_FILE = Path("data/evals/search_skill_strong_evidence_v1.json")
DEFAULT_OUTPUT_DIR = Path("data/tmp/search_skill_strong_evidence/latest")
PROVIDERS = ("anysearch_skill", "tavily_basic")
WEAK_DOMAINS = (
    "baidu.com",
    "eastmoney.com",
    "10jqka.com.cn",
    "sohu.com",
    "163.com",
    "qq.com",
    "toutiao.com",
)


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    content: str
    route: str


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name := name.strip():
            os.environ.setdefault(name, value.strip().strip('"').strip("'"))


def tavily_settings(timeout_seconds: int, max_results: int) -> TavilySearchSettings:
    api_keys = [
        item.strip()
        for item in re.split(r"[,;\s]+", os.getenv("TAVILY_API_KEYS", ""))
        if item.strip()
    ]
    return TavilySearchSettings(
        api_key=(os.getenv("TAVILY_API_KEY") or "").strip() or None,
        api_keys=api_keys,
        search_depth="basic",
        topic="general",
        country="china",
        max_results=max_results,
        auto_parameters=False,
        include_answer=False,
        include_raw_content=False,
        timeout_seconds=timeout_seconds,
    )

def parse_anysearch_markdown(text: str, *, route: str) -> list[SearchResult]:
    pattern = re.compile(
        r"^###\s+\d+\.\s+(?P<title>.+?)\r?\n"
        r"-\s+\*\*URL\*\*:\s+(?P<url>\S+)\r?\n"
        r"(?P<body>.*?)(?=^###\s+\d+\.|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    return [
        SearchResult(
            title=match.group("title").strip(),
            url=match.group("url").strip(),
            content=match.group("body").strip(),
            route=route,
        )
        for match in pattern.finditer(text)
    ]


def call_anysearch_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    api_key: str | None,
    timeout_seconds: int,
) -> str:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "X-Anysearch-Client": "skill-eval/2.1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.post(
        ANYSEARCH_MCP_ENDPOINT,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
        headers=headers,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    for item in payload.get("result", {}).get("content", []):
        if item.get("type") == "text":
            return str(item.get("text") or "")
    raise ValueError("AnySearch Skill returned no text content")


def anysearch_skill_search(
    case: dict[str, Any],
    *,
    max_results: int,
    api_key: str | None,
    timeout_seconds: int,
) -> tuple[list[SearchResult], dict[str, Any]]:
    calls = [
        (
            "general",
            {"query": case["query"], "max_results": max_results},
        )
    ]
    vertical = case.get("vertical")
    if vertical:
        calls.append(
            (
                "vertical",
                {
                    "query": case["query"],
                    "domain": vertical["domain"],
                    "sub_domain": vertical["sub_domain"],
                    "sub_domain_params": vertical["params"],
                    "max_results": max_results,
                },
            )
        )

    results: list[SearchResult] = []
    raw_responses: dict[str, str] = {}
    for route, arguments in calls:
        raw = call_anysearch_tool(
            "search",
            arguments,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        raw_responses[route] = raw
        results.extend(parse_anysearch_markdown(raw, route=route))
    deduplicated = {result.url: result for result in results}
    return list(deduplicated.values()), {
        "routes": [route for route, _ in calls],
        "raw_responses": raw_responses,
        "auth_mode": "api_key" if api_key else "anonymous",
    }


def tavily_basic_search(
    case: dict[str, Any],
    *,
    adapter: TavilySearchAdapter,
    max_results: int,
) -> tuple[list[SearchResult], dict[str, Any]]:
    response = adapter.search(
        TavilySearchRequest(
            query=case["query"],
            country="china",
            topic="general",
            max_results=max_results,
            search_depth="basic",
            auto_parameters=False,
            include_answer=False,
            include_raw_content=False,
        )
    )
    if response.status != ToolStatus.SUCCESS:
        raise RuntimeError("; ".join(error.message for error in response.errors))
    results = [
        SearchResult(
            title=result.title,
            url=result.url,
            content=result.raw_content or result.content,
            route="general",
        )
        for result in response.results
    ]
    metadata = response.usage.model_dump(mode="json") if response.usage else {}
    metadata.update(response.raw_response_metadata)
    return results, metadata


def evaluate_strong_evidence(
    case: dict[str, Any], results: list[SearchResult]
) -> dict[str, Any]:
    entity_terms = _terms(case, "entity_terms")
    geo_terms = _terms(case, "geo_terms")
    document_signals = _terms(case, "document_signals")
    implementation_signals = _terms(case, "implementation_signals")
    domain_hints = _terms(case, "strong_domain_hints")
    rows = []
    for result in results:
        text = f"{result.title}\n{result.content}".lower()
        domain = _domain(result.url)
        entity_match = _all_groups_match(text, entity_terms)
        geo_match = not geo_terms or any(term in text for term in geo_terms)
        document_match = any(term in text for term in document_signals)
        implementation_hits = sum(term in text for term in implementation_signals)
        primary_source = _is_primary(domain, domain_hints)
        weak_source = any(domain.endswith(item) for item in WEAK_DOMAINS)
        strong = entity_match and geo_match and document_match and primary_source
        rows.append(
            {
                "url": result.url,
                "domain": domain,
                "route": result.route,
                "entity_match": entity_match,
                "geo_match": geo_match,
                "document_match": document_match,
                "implementation_hits": implementation_hits,
                "primary_source": primary_source,
                "weak_source": weak_source,
                "strong_evidence": strong,
                "content_chars": len(result.content),
            }
        )
    count = len(rows)
    metrics = {
        "result_count": count,
        "primary_source_rate": _rate(rows, "primary_source"),
        "entity_match_rate": _rate(rows, "entity_match"),
        "geo_match_rate": _rate(rows, "geo_match"),
        "evidence_family_match_rate": _rate(rows, "document_match"),
        "implementation_detail_rate": _ratio(
            sum(row["implementation_hits"] >= 2 for row in rows), count
        ),
        "strong_evidence_rate": _rate(rows, "strong_evidence"),
        "strong_evidence_count": sum(row["strong_evidence"] for row in rows),
        "weak_source_rate": _rate(rows, "weak_source"),
        "deep_content_rate": _ratio(
            sum(row["content_chars"] >= 1000 for row in rows), count
        ),
        "avg_content_chars": round(
            sum(row["content_chars"] for row in rows) / count, 2
        )
        if count
        else 0.0,
        "result_diagnostics": rows,
    }
    metrics["score"] = round(
        100
        * (
            0.30 * metrics["strong_evidence_rate"]
            + 0.20 * metrics["primary_source_rate"]
            + 0.15 * metrics["entity_match_rate"]
            + 0.15 * metrics["evidence_family_match_rate"]
            + 0.10 * metrics["implementation_detail_rate"]
            + 0.10 * metrics["deep_content_rate"]
            - 0.10 * metrics["weak_source_rate"]
        ),
        2,
    )
    return metrics


def aggregate_by_family(cases: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case_run in cases:
        grouped[case_run["case"]["family"]].append(case_run)
    summary: dict[str, Any] = {}
    for family, family_cases in grouped.items():
        providers: dict[str, Any] = {}
        for provider in PROVIDERS:
            successful = [
                item["providers"][provider]
                for item in family_cases
                if item["providers"][provider]["status"] == "success"
            ]
            providers[provider] = {
                "success_count": len(successful),
                "avg_score": _avg(item["metrics"]["score"] for item in successful),
                "avg_strong_evidence_rate": _avg(
                    item["metrics"]["strong_evidence_rate"] for item in successful
                ),
                "avg_primary_source_rate": _avg(
                    item["metrics"]["primary_source_rate"] for item in successful
                ),
                "avg_latency_ms": _avg(item["latency_ms"] for item in successful),
            }
        ranked = sorted(
            providers,
            key=lambda provider: (
                providers[provider]["avg_strong_evidence_rate"],
                providers[provider]["avg_primary_source_rate"],
                providers[provider]["avg_score"],
            ),
            reverse=True,
        )
        summary[family] = {
            "providers": providers,
            "provisional_winner": ranked[0] if ranked else None,
            "decision_basis": "strong evidence, then primary source, then score",
        }
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    load_env_file(args.env_file)
    payload = json.loads(args.case_file.read_text(encoding="utf-8-sig"))
    cases = payload["cases"]
    if args.case_id:
        selected = set(args.case_id)
        cases = [case for case in cases if case["id"] in selected]
    tavily = TavilySearchAdapter(
        settings=tavily_settings(args.timeout_seconds, args.max_results)
    )
    anysearch_key = (os.getenv("ANYSEARCH_API_KEY") or "").strip() or None
    case_runs = []
    for case in cases:
        provider_runs = {}
        for provider in PROVIDERS:
            started = perf_counter()
            try:
                if provider == "anysearch_skill":
                    results, metadata = anysearch_skill_search(
                        case,
                        max_results=args.max_results,
                        api_key=anysearch_key,
                        timeout_seconds=args.timeout_seconds,
                    )
                else:
                    results, metadata = tavily_basic_search(
                        case, adapter=tavily, max_results=args.max_results
                    )
                provider_runs[provider] = {
                    "status": "success",
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                    "metadata": metadata,
                    "metrics": evaluate_strong_evidence(case, results),
                    "results": [asdict(result) for result in results],
                }
            except Exception as exc:  # noqa: BLE001 - provider failures are eval data
                provider_runs[provider] = {
                    "status": "error",
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                    "error": f"{type(exc).__name__}: {exc}",
                }
        case_runs.append({"case": case, "providers": provider_runs})
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "case_file": str(args.case_file),
        "cases": case_runs,
        "by_family": aggregate_by_family(case_runs),
        "guardrails": [
            "No global winner: use per-family results.",
            "Long content does not compensate for missing primary evidence.",
            "Vertical announcement results supplement but do not replace project records.",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "summary.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Strong Evidence Search Comparison", "", "## Family Summary", ""]
    lines.append(
        "| Family | Provider | Success | Strong evidence | Primary source | Score | Latency ms |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for family, family_summary in report["by_family"].items():
        for provider, metrics in family_summary["providers"].items():
            lines.append(
                f"| {family} | {provider} | {metrics['success_count']} | "
                f"{metrics['avg_strong_evidence_rate']} | {metrics['avg_primary_source_rate']} | "
                f"{metrics['avg_score']} | {metrics['avg_latency_ms']} |"
            )
    lines.extend(["", "## Case Detail", ""])
    for case_run in report["cases"]:
        lines.append(f"### {case_run['case']['id']} - {case_run['case']['family']}")
        lines.append("")
        lines.append(case_run["case"]["query"])
        for provider, run_data in case_run["providers"].items():
            if run_data["status"] == "success":
                metrics = run_data["metrics"]
                lines.append(
                    f"- `{provider}`: strong={metrics['strong_evidence_count']}/"
                    f"{metrics['result_count']}, primary={metrics['primary_source_rate']}, "
                    f"score={metrics['score']}"
                )
            else:
                lines.append(f"- `{provider}`: ERROR {run_data['error']}")
        lines.append("")
    return "\n".join(lines)


def _terms(case: dict[str, Any], name: str) -> list[str]:
    return [str(term).strip().lower() for term in case.get(name, []) if str(term).strip()]


def _all_groups_match(text: str, terms: list[str]) -> bool:
    return bool(terms) and sum(term in text for term in terms) >= min(2, len(terms))


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _is_primary(domain: str, hints: list[str]) -> bool:
    return domain.endswith(("gov.cn", "cninfo.com.cn", "sse.com.cn", "szse.cn", "bse.cn")) or any(
        domain.endswith(hint) for hint in hints
    )


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _rate(rows: list[dict[str, Any]], field: str) -> float:
    return _ratio(sum(bool(row[field]) for row in rows), len(rows))


def _avg(values: Any) -> float:
    items = list(values)
    return round(sum(items) / len(items), 4) if items else 0.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare AnySearch Skill and Tavily on strong industrial evidence."
    )
    parser.add_argument("--case-file", type=Path, default=DEFAULT_CASE_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--max-results", type=int, default=5, choices=range(1, 11))
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--print-json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = run(args)
    if args.print_json:
        print(json.dumps(report["by_family"], ensure_ascii=False, indent=2))
    else:
        print(f"Comparison written to {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
