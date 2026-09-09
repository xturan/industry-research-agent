from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_DIR = Path("data/tmp/graph_provider_backed_smoke_matrix")
DEFAULT_CASES = [
    {
        "case_id": "P01",
        "label": "policy_procurement",
        "query": "2025年低空经济政策与公共资源采购中标证据 官方来源",
        "max_rounds": 2,
        "max_loop_count": 1,
    },
    {
        "case_id": "D01",
        "label": "disclosure",
        "query": "2025年低空经济上市公司年报披露与官方政策证据",
        "max_rounds": 2,
        "max_loop_count": 1,
    },
    {
        "case_id": "L01",
        "label": "local_hefei",
        "query": "2025年合肥低空经济地方政策项目公示官方来源",
        "max_rounds": 2,
        "max_loop_count": 1,
    },
    {
        "case_id": "L02",
        "label": "local_wuhan",
        "query": "2025年武汉低空经济地方政策项目公示官方来源",
        "max_rounds": 2,
        "max_loop_count": 1,
    },
    {
        "case_id": "E01",
        "label": "implementation_project",
        "query": "2025年低空经济示范项目落地与官方公示证据",
        "max_rounds": 2,
        "max_loop_count": 1,
    },
]


def main() -> None:
    args = _parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    per_case_dir = output_dir / "per_case"
    per_case_dir.mkdir(parents=True, exist_ok=True)
    cases = _load_cases(args.cases_file)

    case_summaries: list[dict[str, Any]] = []
    for case in cases:
        started = time.perf_counter()
        case_output_dir = per_case_dir / f"{case['case_id']}_{case['label']}"
        summary = _run_case(
            case=case,
            output_dir=case_output_dir,
            env_file=args.env_file,
            reset=args.reset_each_case,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        summary["case_id"] = case["case_id"]
        summary["label"] = case["label"]
        summary["latency_ms"] = elapsed_ms
        (case_output_dir / "matrix_case_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        case_summaries.append(summary)

    live_summary = _build_live_summary(case_summaries)
    markdown = _build_markdown_report(case_summaries, live_summary)

    payload = {"summary": live_summary, "cases": case_summaries}
    (output_dir / "live_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "live_summary.md").write_text(markdown, encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a broader provider-backed smoke matrix for graph_v1 promotion gating."
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--cases-file", default=None)
    parser.add_argument("--reset-each-case", action="store_true")
    return parser.parse_args()


def _load_cases(cases_file: str | None) -> list[dict[str, Any]]:
    if not cases_file:
        return list(DEFAULT_CASES)
    path = Path(cases_file)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("cases file must contain a JSON array of case objects.")
    cases: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"case at index {index} must be a JSON object.")
        case_id = str(item.get("case_id") or "").strip()
        label = str(item.get("label") or "").strip()
        query = str(item.get("query") or "").strip()
        if not case_id or not label or not query:
            raise ValueError(
                f"case at index {index} must include non-empty case_id, label, and query."
            )
        cases.append(
            {
                "case_id": case_id,
                "label": label,
                "query": query,
                "max_rounds": int(item.get("max_rounds", 2) or 2),
                "max_loop_count": int(item.get("max_loop_count", 1) or 1),
            }
        )
    return cases


def _run_case(
    *,
    case: dict[str, Any],
    output_dir: Path,
    env_file: str,
    reset: bool,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "scripts/graph_provider_backed_smoke.py",
        "--output-dir",
        str(output_dir),
        "--query",
        str(case["query"]),
        "--max-rounds",
        str(case.get("max_rounds", 2)),
        "--max-loop-count",
        str(case.get("max_loop_count", 1)),
        "--env-file",
        env_file,
    ]
    if reset:
        command.append("--reset")
    completed = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Smoke case {case['case_id']} failed with code {completed.returncode}: "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )
    summary_path = output_dir / "summary.json"
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _build_live_summary(case_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(str(item.get("status", "unknown")) for item in case_summaries)
    decision_counts = Counter(str(item.get("decision", "unknown")) for item in case_summaries)
    planner_mode_counts = Counter(
        str(item.get("planner_mode", "unknown")) for item in case_summaries
    )
    planner_reason_counts = Counter(
        str(item.get("planner_reason", "unknown")) for item in case_summaries
    )
    unstable_cases = [
        item["case_id"]
        for item in case_summaries
        if float(item.get("unstable_search_rate", 0.0) or 0.0) > 0.30
    ]
    uncovered_cases = [
        item["case_id"]
        for item in case_summaries
        if any(
            not bool(obligation.get("covered"))
            for obligation in list(item.get("required_obligation_coverage", []))
        )
    ]
    return {
        "total_cases": len(case_summaries),
        "status_counts": dict(status_counts),
        "decision_counts": dict(decision_counts),
        "planner_mode_counts": dict(planner_mode_counts),
        "planner_reason_counts": dict(planner_reason_counts),
        "semantic_repaired_count": sum(
            1 for item in case_summaries if item.get("planner_reason") == "semantic_plan_repaired"
        ),
        "deterministic_fallback_count": sum(
            1 for item in case_summaries if bool(item.get("planner_deterministic_fallback"))
        ),
        "estimated_tavily_credits": sum(
            int(item.get("estimated_credits", 0) or 0) for item in case_summaries
        ),
        "average_latency_ms": round(
            sum(float(item.get("latency_ms", 0.0) or 0.0) for item in case_summaries)
            / max(len(case_summaries), 1),
            3,
        ),
        "average_final_score": round(
            sum(
                float((item.get("quality_scores") or {}).get("final_score", 0.0) or 0.0)
                for item in case_summaries
            )
            / max(len(case_summaries), 1),
            3,
        ),
        "max_retry_rate": round(
            max(float(item.get("retry_rate", 0.0) or 0.0) for item in case_summaries),
            3,
        )
        if case_summaries
        else 0.0,
        "max_unstable_search_rate": round(
            max(float(item.get("unstable_search_rate", 0.0) or 0.0) for item in case_summaries),
            3,
        )
        if case_summaries
        else 0.0,
        "unstable_case_ids": unstable_cases,
        "uncovered_obligation_case_ids": uncovered_cases,
    }


def _build_markdown_report(
    case_summaries: list[dict[str, Any]],
    live_summary: dict[str, Any],
) -> str:
    lines = [
        "# Graph Provider-Backed Smoke Matrix",
        "",
        "## Summary",
        "",
        f"- total_cases: {live_summary['total_cases']}",
        f"- status_counts: {live_summary['status_counts']}",
        f"- decision_counts: {live_summary['decision_counts']}",
        f"- planner_mode_counts: {live_summary['planner_mode_counts']}",
        f"- planner_reason_counts: {live_summary['planner_reason_counts']}",
        f"- semantic_repaired_count: {live_summary['semantic_repaired_count']}",
        f"- deterministic_fallback_count: {live_summary['deterministic_fallback_count']}",
        f"- estimated_tavily_credits: {live_summary['estimated_tavily_credits']}",
        f"- average_latency_ms: {live_summary['average_latency_ms']}",
        f"- average_final_score: {live_summary['average_final_score']}",
        f"- max_retry_rate: {live_summary['max_retry_rate']}",
        f"- max_unstable_search_rate: {live_summary['max_unstable_search_rate']}",
        f"- unstable_case_ids: {live_summary['unstable_case_ids']}",
        f"- uncovered_obligation_case_ids: {live_summary['uncovered_obligation_case_ids']}",
        "",
        "## Cases",
        "",
    ]
    for item in case_summaries:
        lines.extend(
            [
                f"### {item['case_id']} {item['label']}",
                f"- query: {item['query']}",
                f"- status: {item['status']}",
                f"- decision: {item.get('decision')}",
                f"- planner_mode: {item.get('planner_mode')}",
                f"- planner_reason: {item.get('planner_reason')}",
                f"- final_score: {(item.get('quality_scores') or {}).get('final_score')}",
                f"- retry_rate: {item.get('retry_rate')}",
                f"- unstable_search_rate: {item.get('unstable_search_rate')}",
                f"- local_precision: {item.get('gate_local_precision')}",
                f"- required_obligation_coverage: {item.get('required_obligation_coverage', [])}",
                "",
            ]
        )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
