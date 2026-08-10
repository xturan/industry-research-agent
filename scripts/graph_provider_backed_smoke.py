from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.session import reset_db_session_state
from packages.research_harness.runner import ResearchGraphRunner
from packages.research_harness.schemas import GraphAnalyzeRequest

DEFAULT_QUERY = "2025年低空经济政策与公共资源采购中标证据 官方来源"
DEFAULT_OUTPUT_DIR = Path("data/tmp/langgraph_provider_backed_live_manual")


def main() -> None:
    args = _parse_args()
    _load_env_file(args.env_file)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir.with_suffix(".db")
    if args.reset and db_path.exists():
        db_path.unlink()

    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"
    os.environ.setdefault("TAVILY_SEARCH_DEPTH", "basic")
    os.environ.setdefault("TAVILY_TIMEOUT_SECONDS", "30")
    get_settings.cache_clear()
    reset_db_session_state()

    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        runner = ResearchGraphRunner(session)
        initial_result = runner.run(
            GraphAnalyzeRequest(
                query=args.query,
                max_rounds=args.max_rounds,
                max_loop_count=args.max_loop_count,
                execution_mode="provider_backed",
            )
        )

        initial_response = initial_result.model_dump(mode="json")
        final_response = initial_response
        resumed_response: dict[str, Any] | None = None
        if args.resume_action:
            resumed_result = runner.run(
                GraphAnalyzeRequest(
                    query=args.query,
                    max_rounds=args.max_rounds,
                    max_loop_count=args.max_loop_count,
                    execution_mode="provider_backed",
                    resume_run_id=initial_result.run_id,
                    human_review_action=args.resume_action,
                    human_review_notes=args.resume_notes,
                )
            )
            resumed_response = resumed_result.model_dump(mode="json")
            final_response = resumed_response

    response = final_response
    search_events = _search_events_from_response(response)
    plan_task_summaries = _all_step_outputs(response, "plan_task")
    first_plan_task_summary = plan_task_summaries[0] if plan_task_summaries else {}
    latest_plan_task_summary = plan_task_summaries[-1] if plan_task_summaries else {}
    chief_gate_summary = _latest_step_output(response, "chief_gate")
    contract_diagnostics = _contract_diagnostics_from_response(response)
    contract_status_by_node = {
        item["node_name"]: {
            "status": item.get("status"),
            "used_fallback": item.get("used_fallback"),
            "attempt_count": item.get("attempt_count"),
            "normalizations": item.get("normalizations", []),
            "llm_mode": item.get("llm_mode"),
            "input_mode": item.get("input_mode"),
        }
        for item in contract_diagnostics
    }
    over_budget_context_packs = [
        {
            "node_name": pack.get("node_name"),
            "context_pack_id": pack.get("context_pack_id"),
            "token_estimate": pack.get("token_estimate"),
            "context_budget_tokens": pack.get("context_budget_tokens"),
            "budget_overage_tokens": pack.get("budget_overage_tokens"),
        }
        for pack in response.get("context_packs", [])
        if pack.get("budget_status") == "over_budget"
    ]
    dossier_text = _read_text(response.get("dossier_path"))
    dossier_artifact_path = out_dir / "dossier.md"
    if dossier_text:
        dossier_artifact_path.write_text(dossier_text, encoding="utf-8")
    final_report_artifact_path = _write_final_report_artifact(
        response.get("report_preview"),
        out_dir,
    )
    final_report_markdown = _report_markdown_from_preview(
        response.get("report_preview")
    )
    (out_dir / "response.initial.json").write_text(
        json.dumps(initial_response, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if resumed_response is not None:
        (out_dir / "response.resume.json").write_text(
            json.dumps(resumed_response, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    summary = {
        "query": args.query,
        "run_id": response["run_id"],
        "status": response["status"],
        "decision": response.get("decision"),
        "initial_decision": initial_response.get("decision"),
        "initial_status": initial_response.get("status"),
        "initial_human_review_pending": (
            initial_response.get("human_review", {}) or {}
        ).get("pending"),
        "resume_action": args.resume_action,
        "resume_notes": args.resume_notes,
        "resumed": resumed_response is not None,
        "resumed_from_checkpoint": response.get("resumed_from_checkpoint", False),
        "resume_selected_action": (
            response.get("human_review", {}) or {}
        ).get("selected_action"),
        "resume_human_review_status": (
            response.get("human_review", {}) or {}
        ).get("status"),
        "quality_scores": response.get("quality_scores", {}),
        "node_count": len(response.get("node_steps", [])),
        "context_pack_count": len(response.get("context_packs", [])),
        "dossier_path": response.get("dossier_path"),
        "report_id": response.get("report_preview", {}).get("report_id"),
        "report_artifact": response.get("report_preview", {}).get("report_artifact", {}),
        "dossier_artifact_path": (
            str(dossier_artifact_path) if dossier_text else None
        ),
        "final_report_artifact_path": (
            str(final_report_artifact_path)
            if final_report_artifact_path is not None
            else None
        ),
        "final_report_artifact_status": (
            "exported"
            if final_report_artifact_path is not None
            else "absent_empty_report_preview"
        ),
        "final_report_markdown_chars": len(final_report_markdown),
        "checkpoint_history_count": len(response.get("checkpoint_history", [])),
        "search_event_count": len(search_events),
        "search_success_count": sum(
            1 for event in search_events if event.get("status") == "success"
        ),
        "search_error_count": sum(
            1 for event in search_events if event.get("status") == "error"
        ),
        "search_error_rate": round(
            sum(1 for event in search_events if event.get("status") == "error")
            / max(len(search_events), 1),
            3,
        ),
        "unstable_search_event_count": sum(
            1
            for event in search_events
            if event.get("status") == "error"
            or "error" in list(event.get("attempt_statuses") or [])
        ),
        "unstable_search_rate": round(
            sum(
                1
                for event in search_events
                if event.get("status") == "error"
                or "error" in list(event.get("attempt_statuses") or [])
            )
            / max(len(search_events), 1),
            3,
        ),
        "estimated_credits": sum(
            int(event.get("estimated_credits") or 0) for event in search_events
        ),
        "retry_event_count": sum(
            1 for event in search_events if int(event.get("retry_count") or 0) > 0
        ),
        "retry_rate": round(
            sum(1 for event in search_events if int(event.get("retry_count") or 0) > 0)
            / max(len(search_events), 1),
            3,
        ),
        "max_attempt_count": max(
            [int(event.get("attempt_count") or 0) for event in search_events] or [0]
        ),
        "gate_obligation_gap_count": (
            chief_gate_summary.get("contract_meta", {})
            .get("chief_gate", {})
            .get("obligation_gap_count", 0)
        ),
        "gate_local_precision": (
            chief_gate_summary.get("contract_meta", {})
            .get("chief_gate", {})
            .get("local_precision")
        ),
        "gate_unstable_search_rate": (
            chief_gate_summary.get("contract_meta", {})
            .get("chief_gate", {})
            .get("unstable_search_rate")
        ),
        "planner_invocation_count": len(plan_task_summaries),
        "planner_mode": (
            latest_plan_task_summary.get("planner_metadata", {}).get("planner_mode")
        ),
        "planner_provider": (
            latest_plan_task_summary.get("planner_metadata", {}).get("planner_provider")
        ),
        "planner_model": (
            latest_plan_task_summary.get("planner_metadata", {}).get("planner_model")
        ),
        "planner_deterministic_fallback": (
            latest_plan_task_summary.get("planner_metadata", {}).get("deterministic_fallback")
        ),
        "planner_reason": (
            latest_plan_task_summary.get("planner_metadata", {}).get("reason")
        ),
        "planner_first_mode": (
            first_plan_task_summary.get("planner_metadata", {}).get("planner_mode")
        ),
        "planner_first_reason": (
            first_plan_task_summary.get("planner_metadata", {}).get("reason")
        ),
        "planner_replan_request": chief_gate_summary.get("planner_replan_request"),
        "required_obligation_coverage": (
            chief_gate_summary.get("contract_meta", {})
            .get("chief_gate", {})
            .get("required_obligation_coverage", [])
        ),
        "contract_diagnostics": contract_diagnostics,
        "contract_status_by_node": contract_status_by_node,
        "contract_fallback_nodes": [
            item["node_name"] for item in contract_diagnostics if item.get("used_fallback")
        ],
        "contract_normalized_nodes": [
            item["node_name"]
            for item in contract_diagnostics
            if str(item.get("status", "")).endswith("normalized")
            or bool(item.get("normalizations"))
        ],
        "over_budget_context_packs": over_budget_context_packs,
        "over_budget_node_names": [
            str(item.get("node_name"))
            for item in over_budget_context_packs
            if item.get("node_name")
        ],
        "provider_backed_editor_pack": _has_prompt_version(
            response, "provider_backed_v1.editor1_draft"
        ),
        "provider_backed_review_pack": _has_prompt_version(
            response, "provider_backed_v1.editor2_review"
        ),
        "provider_backed_gate_pack": _has_prompt_version(
            response, "provider_backed_v1.chief_gate"
        ),
        "dossier_has_search_events": "### Search Events" in dossier_text,
        "dossier_has_claim_verifications": "### Claim Verifications" in dossier_text,
    }

    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "response.json").write_text(
        json.dumps(response, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a cost-capped provider-backed LangGraph smoke test."
    )
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--max-loop-count", type=int, default=1)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument(
        "--resume-action",
        choices=["approve", "add_evidence", "rewrite", "reject"],
    )
    parser.add_argument(
        "--resume-notes",
        default="Approved after manual review.",
    )
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


def _search_events_from_response(response: dict[str, Any]) -> list[dict[str, Any]]:
    for step in response.get("node_steps", []):
        summary = step.get("output_summary") or {}
        if "search_events" in summary:
            return list(summary["search_events"])
    return []


def _latest_step_output(response: dict[str, Any], node_name: str) -> dict[str, Any]:
    for step in reversed(response.get("node_steps", [])):
        if step.get("node_name") == node_name:
            return dict(step.get("output_summary") or {})
    return {}


def _all_step_outputs(response: dict[str, Any], node_name: str) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for step in response.get("node_steps", []):
        if step.get("node_name") == node_name:
            outputs.append(dict(step.get("output_summary") or {}))
    return outputs


def _read_text(path: str | None) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def _report_markdown_from_preview(report_preview: object) -> str:
    if not isinstance(report_preview, dict):
        return ""
    return str(report_preview.get("report_markdown") or "").strip()


def _write_final_report_artifact(
    report_preview: object,
    out_dir: Path,
) -> Path | None:
    report_markdown = _report_markdown_from_preview(report_preview)
    if not report_markdown:
        return None
    artifact_path = out_dir / "FINAL_REPORT.md"
    artifact_path.write_text(report_markdown, encoding="utf-8")
    return artifact_path


def _has_prompt_version(response: dict[str, Any], prompt_version: str) -> bool:
    return any(
        pack.get("prompt_version") == prompt_version
        for pack in response.get("context_packs", [])
    )


def _contract_diagnostics_from_response(response: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for step in response.get("node_steps", []):
        output_summary = step.get("output_summary") or {}
        contract_meta = output_summary.get("contract_meta") or {}
        if not isinstance(contract_meta, dict):
            continue
        for node_name, meta in contract_meta.items():
            if not isinstance(meta, dict):
                continue
            normalizations: list[str] = []
            for attempt in list(meta.get("attempts", [])):
                if isinstance(attempt, dict):
                    normalizations.extend(
                        str(value)
                        for value in list(attempt.get("normalizations", []))
                        if value
                    )
            diagnostics.append(
                {
                    "node_name": node_name,
                    "status": meta.get("status"),
                    "used_fallback": meta.get("used_fallback"),
                    "attempt_count": meta.get("attempt_count"),
                    "normalizations": _dedupe_preserve_order(normalizations),
                    "llm_mode": meta.get("llm_mode"),
                    "input_mode": meta.get("input_mode"),
                }
            )
    return diagnostics


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


if __name__ == "__main__":
    main()
