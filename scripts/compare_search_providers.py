from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from packages.sources.enums import ToolStatus
from packages.sources.search_discovery import (
    TavilySearchAdapter,
    TavilySearchRequest,
    TavilySearchSettings,
)

ANYSEARCH_ENDPOINT = "https://api.anysearch.com/v1/search"
DEFAULT_CASE_FILE = Path("data/evals/search_provider_comparison_v1.json")
DEFAULT_OUTPUT_ROOT = Path("data/tmp/search_provider_comparison")


@dataclass
class NormalizedResult:
    title: str
    url: str
    snippet: str
    content: str
    score: float | None = None
    published_date: str | None = None


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and value:
            os.environ.setdefault(name, value)


def parse_anysearch_response(
    payload: dict[str, Any],
) -> tuple[list[NormalizedResult], dict[str, Any]]:
    if payload.get("code") not in {None, 0}:
        raise ValueError(
            f"AnySearch business error {payload.get('code')}: {payload.get('message')}"
        )
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise ValueError("AnySearch response data is not an object")
    raw_results = data.get("results") or []
    if not isinstance(raw_results, list):
        raise ValueError("AnySearch results is not a list")
    results = []
    for item in raw_results:
        if not isinstance(item, dict) or not str(item.get("url") or "").strip():
            continue
        snippet = str(item.get("snippet") or "")
        results.append(
            NormalizedResult(
                title=str(item.get("title") or ""),
                url=str(item["url"]).strip(),
                snippet=snippet,
                content=str(item.get("content") or snippet),
                score=_safe_float(item.get("score")),
                published_date=_optional_string(item.get("published_date")),
            )
        )
    metadata = dict(data.get("metadata") or {})
    if payload.get("request_id"):
        metadata["request_id"] = payload["request_id"]
    return results, metadata


def anysearch_search(
    query: str,
    *,
    max_results: int,
    api_key: str | None,
    timeout_seconds: int,
) -> tuple[list[NormalizedResult], dict[str, Any]]:
    body = json.dumps(
        {
            "query": query,
            "max_results": max_results,
            "zone": "cn",
            "language": "zh-CN",
            "format": "json",
        },
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(ANYSEARCH_ENDPOINT, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # nosec: B310
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AnySearch HTTP {exc.code}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"AnySearch network error: {exc.reason}") from exc
    return parse_anysearch_response(payload)


def tavily_search(
    adapter: TavilySearchAdapter,
    query: str,
    *,
    max_results: int,
    depth: str,
) -> tuple[list[NormalizedResult], dict[str, Any]]:
    response = adapter.search(
        TavilySearchRequest(
            query=query,
            country="china",
            topic="general",
            max_results=max_results,
            search_depth=depth,
            auto_parameters=False,
            include_answer=False,
            include_raw_content=False,
        )
    )
    if response.status != ToolStatus.SUCCESS:
        messages = "; ".join(error.message for error in response.errors)
        raise RuntimeError(messages or "Tavily search failed")
    results = [
        NormalizedResult(
            title=item.title,
            url=item.url,
            snippet=item.content,
            content=item.raw_content or item.content,
            score=item.score,
            published_date=item.published_date,
        )
        for item in response.results
    ]
    metadata = response.usage.model_dump(mode="json") if response.usage else {}
    metadata.update(response.raw_response_metadata)
    return results, metadata


def evaluate_results(case: dict[str, Any], results: list[NormalizedResult]) -> dict[str, Any]:
    keywords = [str(value).lower() for value in case.get("keywords") or [] if str(value).strip()]
    geo_terms = [
        str(value).lower() for value in case.get("required_geo_terms") or [] if str(value).strip()
    ]
    expected_classes = set(case.get("expected_source_classes") or [])
    texts = [f"{item.title}\n{item.snippet}\n{item.content}".lower() for item in results]
    all_text = "\n".join(texts)
    keyword_hits = {keyword: keyword in all_text for keyword in keywords}
    top3_text = "\n".join(texts[:3])
    relevant_count = sum(_is_relevant(text, keywords, geo_terms) for text in texts)
    domains = [_domain(item.url) for item in results]
    source_classes = sorted({_source_class(item) for item in results})
    official_count = sum(_is_official_domain(domain) for domain in domains)
    valid_url_count = sum(_valid_http_url(item.url) for item in results)
    content_lengths = [len(item.content.strip()) for item in results]
    snippet_lengths = [len(item.snippet.strip()) for item in results]
    result_count = len(results)
    keyword_coverage = _ratio(sum(keyword_hits.values()), len(keywords))
    top3_keyword_coverage = _ratio(sum(keyword in top3_text for keyword in keywords), len(keywords))
    relevant_result_rate = _ratio(relevant_count, result_count)
    geo_match_rate = (
        _ratio(sum(any(term in text for term in geo_terms) for text in texts), result_count)
        if geo_terms
        else 1.0
    )
    official_result_rate = _ratio(official_count, result_count)
    unique_domain_rate = _ratio(len(set(domains)), result_count)
    expected_source_class_coverage = _ratio(
        len(expected_classes.intersection(source_classes)), len(expected_classes)
    )
    deep_content_rate = _ratio(sum(length >= 1000 for length in content_lengths), result_count)
    avg_content_chars = _average(content_lengths)
    if geo_terms:
        relevance_score = 100 * (
            0.35 * keyword_coverage
            + 0.25 * relevant_result_rate
            + 0.15 * top3_keyword_coverage
            + 0.25 * geo_match_rate
        )
    else:
        relevance_score = 100 * (
            0.45 * keyword_coverage + 0.35 * relevant_result_rate + 0.20 * top3_keyword_coverage
        )
    source_score = 100 * (
        0.45 * official_result_rate
        + 0.25 * unique_domain_rate
        + 0.30 * expected_source_class_coverage
    )
    depth_score = 100 * (
        0.50 * deep_content_rate
        + 0.25 * min(avg_content_chars / 3000, 1.0)
        + 0.25 * keyword_coverage
    )
    overall_score = 0.45 * relevance_score + 0.30 * source_score + 0.25 * depth_score
    return {
        "result_count": result_count,
        "keyword_hits": keyword_hits,
        "keyword_coverage": _round(keyword_coverage),
        "top3_keyword_coverage": _round(top3_keyword_coverage),
        "relevant_result_rate": _round(relevant_result_rate),
        "geo_match_rate": _round(geo_match_rate),
        "official_result_rate": _round(official_result_rate),
        "unique_domain_count": len(set(domains)),
        "unique_domain_rate": _round(unique_domain_rate),
        "domains": domains,
        "source_classes": source_classes,
        "expected_source_class_coverage": _round(expected_source_class_coverage),
        "valid_url_rate": _round(_ratio(valid_url_count, result_count)),
        "avg_snippet_chars": round(_average(snippet_lengths), 2),
        "avg_content_chars": round(avg_content_chars, 2),
        "deep_content_rate": _round(deep_content_rate),
        "scores": {
            "relevance": round(relevance_score, 2),
            "source_quality": round(source_score, 2),
            "returned_depth": round(depth_score, 2),
            "overall": round(overall_score, 2),
        },
    }


def aggregate(case_runs: list[dict[str, Any]], providers: list[str]) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for provider in providers:
        successful = [
            run["providers"][provider]
            for run in case_runs
            if run["providers"].get(provider, {}).get("status") == "success"
        ]
        summaries[provider] = {
            "case_count": len(case_runs),
            "success_count": len(successful),
            "error_count": len(case_runs) - len(successful),
            "avg_latency_ms": round(_average([item["latency_ms"] for item in successful]), 2),
            "avg_result_count": round(
                _average([item["metrics"]["result_count"] for item in successful]), 2
            ),
            "avg_official_result_rate": _metric_average(successful, "official_result_rate"),
            "avg_unique_domain_rate": _metric_average(successful, "unique_domain_rate"),
            "avg_keyword_coverage": _metric_average(successful, "keyword_coverage"),
            "avg_content_chars": round(
                _average([item["metrics"]["avg_content_chars"] for item in successful]), 2
            ),
            "avg_deep_content_rate": _metric_average(successful, "deep_content_rate"),
            "avg_scores": {
                dimension: round(
                    _average([item["metrics"]["scores"][dimension] for item in successful]), 2
                )
                for dimension in ("relevance", "source_quality", "returned_depth", "overall")
            },
            "source_class_frequency": dict(
                Counter(
                    source_class
                    for item in successful
                    for source_class in item["metrics"]["source_classes"]
                )
            ),
        }
    return {
        "providers": summaries,
        "dimension_winners": {
            dimension: _winner(summaries, dimension)
            for dimension in ("relevance", "source_quality", "returned_depth", "overall")
        },
    }


def run_comparison(args: argparse.Namespace) -> dict[str, Any]:
    load_env_file(args.env_file)
    case_payload = json.loads(args.case_file.read_text(encoding="utf-8-sig"))
    cases = case_payload["cases"]
    if args.case_id:
        requested = set(args.case_id)
        cases = [case for case in cases if case["id"] in requested]
    providers = [value.strip() for value in args.providers.split(",") if value.strip()]
    unknown = set(providers) - {"anysearch", "tavily_basic", "tavily_advanced"}
    if unknown:
        raise ValueError(f"Unknown providers: {sorted(unknown)}")

    tavily_settings = _tavily_settings(args.timeout_seconds, args.max_results)
    tavily_adapters = {
        "tavily_basic": TavilySearchAdapter(settings=tavily_settings),
        "tavily_advanced": TavilySearchAdapter(settings=tavily_settings),
    }
    anysearch_key = _clean_secret(os.getenv("ANYSEARCH_API_KEY"))
    case_runs = []
    for case in cases:
        provider_runs: dict[str, Any] = {}
        for provider in providers:
            started = perf_counter()
            try:
                if provider == "anysearch":
                    results, metadata = anysearch_search(
                        case["query"],
                        max_results=args.max_results,
                        api_key=anysearch_key,
                        timeout_seconds=args.timeout_seconds,
                    )
                else:
                    depth = provider.removeprefix("tavily_")
                    results, metadata = tavily_search(
                        tavily_adapters[provider],
                        case["query"],
                        max_results=args.max_results,
                        depth=depth,
                    )
                provider_runs[provider] = {
                    "status": "success",
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                    "metadata": metadata,
                    "metrics": evaluate_results(case, results),
                    "results": [asdict(item) for item in results],
                }
            except Exception as exc:  # noqa: BLE001 - batch must retain provider failures
                provider_runs[provider] = {
                    "status": "error",
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "results": [],
                }
        case_runs.append({"case": case, "providers": provider_runs})

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "case_file": str(args.case_file),
        "max_results": args.max_results,
        "providers_requested": providers,
        "anysearch_auth_mode": "api_key" if anysearch_key else "anonymous",
        "methodology": {
            "fairness": "same query and max_results for all providers",
            "tavily_lanes": [value for value in providers if value.startswith("tavily_")],
            "anysearch_depth_note": (
                "AnySearch has no public depth parameter; depth is measured from returned content."
            ),
            "score_warning": (
                "Deterministic scores are diagnostics, not a semantic ground-truth judgment."
            ),
        },
        "cases": case_runs,
        "aggregate": aggregate(case_runs, providers),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "comparison.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AnySearch vs Tavily Comparison",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "| Provider | Success | Avg latency ms | Official rate | Keyword coverage | "
        "Avg content chars | Overall score |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for provider, summary in report["aggregate"]["providers"].items():
        lines.append(
            f"| {provider} | {summary['success_count']}/{summary['case_count']} | "
            f"{summary['avg_latency_ms']} | {summary['avg_official_result_rate']} | "
            f"{summary['avg_keyword_coverage']} | {summary['avg_content_chars']} | "
            f"{summary['avg_scores']['overall']} |"
        )
    lines.extend(["", "## Dimension Winners", ""])
    for dimension, winner in report["aggregate"]["dimension_winners"].items():
        lines.append(f"- `{dimension}`: `{winner}`")
    lines.extend(["", "## Case Results", ""])
    for case_run in report["cases"]:
        case = case_run["case"]
        lines.append(f"### {case['id']} ({case['level']})")
        lines.append("")
        lines.append(case["query"])
        lines.append("")
        lines.append("| Provider | Status | Results | Official | Keyword | Depth | Overall |")
        lines.append("|---|---|---:|---:|---:|---:|---:|")
        for provider, item in case_run["providers"].items():
            if item["status"] != "success":
                lines.append(f"| {provider} | error | 0 | - | - | - | - |")
                continue
            metrics = item["metrics"]
            lines.append(
                f"| {provider} | success | {metrics['result_count']} | "
                f"{metrics['official_result_rate']} | {metrics['keyword_coverage']} | "
                f"{metrics['scores']['returned_depth']} | {metrics['scores']['overall']} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Interpretation Guardrails",
            "",
            "- AnySearch content and Tavily snippets are different product surfaces.",
            "- Inspect raw `comparison.json` results before provider decisions.",
            "- Rerun the live comparison before production integration.",
        ]
    )
    return "\n".join(lines) + "\n"


def _tavily_settings(timeout_seconds: int, max_results: int) -> TavilySearchSettings:
    api_key = _clean_secret(os.getenv("TAVILY_API_KEY"))
    api_keys = _split_secrets(os.getenv("TAVILY_API_KEYS"))
    return TavilySearchSettings(
        api_key=api_key,
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


def _source_class(result: NormalizedResult) -> str:
    domain = _domain(result.url)
    text = f"{result.title} {result.url}".lower()
    if _is_official_domain(domain):
        if any(term in text for term in ("统计", "tjj", "stats", "公报")):
            return "statistics"
        if any(term in text for term in ("环评", "生态环境", "土地", "自然资源")):
            return "environment_or_land"
        if any(term in text for term in ("采购", "招标", "中标", "ggzy", "ccgp")):
            return "project_or_procurement"
        return "official_policy"
    if domain.endswith(("cninfo.com.cn", "sse.com.cn", "szse.cn", "bse.cn")):
        return "company_disclosure"
    if any(term in text for term in ("采购", "招标", "中标", "ggzy", "ccgp")):
        return "project_or_procurement"
    if any(term in text for term in ("新闻", "news", "日报", "在线")):
        return "media"
    return "third_party"


def _is_official_domain(domain: str) -> bool:
    return bool(
        domain == "gov.cn"
        or domain.endswith(".gov.cn")
        or domain.endswith(
            (
                "ndrc.gov.cn",
                "miit.gov.cn",
                "stats.gov.cn",
                "caac.gov.cn",
                "mof.gov.cn",
                "mofcom.gov.cn",
            )
        )
    )


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _valid_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_relevant(text: str, keywords: list[str], geo_terms: list[str]) -> bool:
    if not keywords:
        return False
    if geo_terms and not any(term in text for term in geo_terms):
        return False
    threshold = 1 if len(keywords) <= 2 else 2
    return sum(keyword in text for keyword in keywords) >= threshold


def _winner(summaries: dict[str, Any], dimension: str) -> str:
    eligible = {
        provider: summary["avg_scores"][dimension]
        for provider, summary in summaries.items()
        if summary["success_count"] > 0
    }
    if not eligible:
        return "none"
    ordered = sorted(eligible.items(), key=lambda item: item[1], reverse=True)
    if len(ordered) > 1 and ordered[0][1] - ordered[1][1] < 3:
        return "tie"
    return ordered[0][0]


def _metric_average(items: list[dict[str, Any]], key: str) -> float:
    return _round(_average([item["metrics"][key] for item in items]))


def _average(values: list[float | int]) -> float:
    return sum(values) / len(values) if values else 0.0


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _round(value: float) -> float:
    return round(value, 4)


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None else None


def _clean_secret(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().strip('"').strip("'")
    return cleaned or None


def _split_secrets(value: str | None) -> list[str]:
    if not value:
        return []
    return [secret for item in re.split(r"[,;\s]+", value) if (secret := _clean_secret(item))]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare AnySearch and Tavily search quality.")
    parser.add_argument("--case-file", type=Path, default=DEFAULT_CASE_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT / "latest")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--case-id", action="append", help="Run only the selected case ID.")
    parser.add_argument("--max-results", type=int, default=5, choices=range(1, 21))
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument(
        "--providers",
        default="anysearch,tavily_basic,tavily_advanced",
        help="Comma-separated provider lanes.",
    )
    parser.add_argument("--print-json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = run_comparison(args)
    summary = {
        "generated_at": report["generated_at"],
        "output_dir": str(args.output_dir.resolve()),
        "anysearch_auth_mode": report["anysearch_auth_mode"],
        "aggregate": report["aggregate"],
    }
    if args.print_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Comparison written to {args.output_dir.resolve()}")
        for provider, item in report["aggregate"]["providers"].items():
            print(
                f"{provider}: success={item['success_count']}/{item['case_count']} "
                f"overall={item['avg_scores']['overall']} latency_ms={item['avg_latency_ms']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
