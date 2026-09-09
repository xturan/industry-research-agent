from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from packages.core.config import get_settings
from packages.db.session import reset_db_session_state
from packages.research_harness import real_nodes

DEFAULT_QUERY = "2025年合肥低空经济地方政策、上市公司披露与项目落地情况"
DEFAULT_OUTPUT_DIR = Path("data/tmp/spec_first_pass_live_inspect")


def main() -> None:
    args = _parse_args()
    _load_env_file(args.env_file)
    os.environ.setdefault("TAVILY_SEARCH_DEPTH", "basic")
    os.environ.setdefault("TAVILY_TIMEOUT_SECONDS", "30")
    get_settings.cache_clear()
    reset_db_session_state()

    out_dir = Path(args.output_dir)
    if args.reset and out_dir.exists():
        for path in out_dir.glob("*.json"):
            path.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    plan_state = {
        "query": args.query,
        "max_rounds": args.max_rounds,
        "max_loop_count": 1,
        "loop_count": 0,
    }
    plan_result = real_nodes.plan_task_provider_backed(plan_state)
    collect_state = {
        "query": args.query,
        "max_rounds": args.max_rounds,
        "query_requirements": dict(plan_result.get("query_requirements") or {}),
        "plan": dict(plan_result.get("plan") or {}),
        "planner_metadata": dict(plan_result.get("planner_metadata") or {}),
        "spec_first_pass_min_search_rounds": int(
            plan_result.get("spec_first_pass_min_search_rounds", 0) or 0
        ),
        "sources": [],
        "search_events": [],
    }
    collect_result = real_nodes.collect_sources_provider_backed(collect_state)

    search_events = list(collect_result.get("search_events", []))
    spec_events = [
        event
        for event in search_events
        if event.get("round_origin") == "spec_driven_first_pass"
    ]
    sources = list(collect_result.get("sources", []))
    spec_sources = [
        source
        for source in sources
        if source.get("round_origin") == "spec_driven_first_pass"
    ]
    spec_target_family_mismatch_count = sum(
        1
        for source in spec_sources
        if source.get("target_source_family")
        and source.get("target_source_family_match") is False
    )
    summary = {
        "query": args.query,
        "env": {
            "tavily_api_key_present": bool(os.environ.get("TAVILY_API_KEY")),
            "tavily_api_keys_present": bool(os.environ.get("TAVILY_API_KEYS")),
            "deepseek_api_key_present": bool(os.environ.get("DEEPSEEK_API_KEY")),
        },
        "plan": {
            "search_round_count": len(
                list((plan_result.get("plan") or {}).get("search_rounds", []))
            ),
            "spec_first_pass_min_search_rounds": plan_result.get(
                "spec_first_pass_min_search_rounds"
            ),
            "spec_driven_first_pass": (
                (plan_result.get("planner_metadata") or {}).get(
                    "spec_driven_first_pass"
                )
            ),
        },
        "collect": {
            "search_event_count": len(search_events),
            "spec_search_event_count": len(spec_events),
            "source_count": len(sources),
            "spec_source_count": len(spec_sources),
            "spec_target_family_mismatch_count": spec_target_family_mismatch_count,
            "estimated_credits": sum(
                float(event.get("estimated_credits") or 0)
                for event in search_events
            ),
            "spec_target_families": sorted(
                {
                    str(event.get("target_source_family") or "")
                    for event in spec_events
                    if str(event.get("target_source_family") or "")
                }
            ),
        },
        "spec_events": spec_events,
        "spec_sources_preview": [
            {
                "title": source.get("title"),
                "url": source.get("url"),
                "source_family": source.get("source_family"),
                "target_source_family": source.get("target_source_family"),
                "target_source_family_match": source.get("target_source_family_match"),
                "target_source_family_mismatch_reason": source.get(
                    "target_source_family_mismatch_reason"
                ),
                "search_phrase": source.get("search_phrase"),
            }
            for source in spec_sources[: args.preview_sources]
        ],
    }

    _write_json(out_dir / "plan_result.json", plan_result)
    _write_json(out_dir / "collect_result.json", collect_result)
    _write_json(out_dir / "summary.json", summary)
    if args.print_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect live spec-driven first-pass retrieval without running the full graph."
    )
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--max-rounds", type=int, default=1)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--preview-sources", type=int, default=5)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    return parser.parse_args()


def _load_env_file(path: str) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    allowed = {
        "TAVILY_API_KEY",
        "TAVILY_API_KEYS",
        "TAVILY_SEARCH_DEPTH",
        "TAVILY_TOPIC",
        "TAVILY_COUNTRY",
        "TAVILY_TIMEOUT_SECONDS",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_RESEARCH_MODEL",
        "DEEPSEEK_TIMEOUT_SECONDS",
        "DEEPSEEK_MAX_RETRIES",
        "DEEPSEEK_MAX_TOKENS",
    }
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key not in allowed:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
