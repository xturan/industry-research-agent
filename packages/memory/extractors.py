from __future__ import annotations

import re
from collections import Counter
from typing import Any

from packages.db.models import Run, RunStep, RunType, StepStatus
from packages.memory.schemas import MemoryCandidate, MemoryKind


def extract_memories_from_run(*, run: Run, steps: list[RunStep]) -> list[MemoryCandidate]:
    candidates: list[MemoryCandidate] = []

    if run.run_type == RunType.RESEARCH:
        candidates.extend(_extract_research_memories(run=run))
    elif run.run_type == RunType.CONTENT_GENERATE:
        candidates.extend(_extract_content_generation_memories(run=run))

    candidates.append(_extract_run_trace_memory(run=run, steps=steps))
    return candidates


def _extract_research_memories(*, run: Run) -> list[MemoryCandidate]:
    output_json = run.output_json if isinstance(run.output_json, dict) else {}
    input_json = run.input_json if isinstance(run.input_json, dict) else {}

    final_memo = output_json.get("final_memo")
    if not isinstance(final_memo, dict):
        final_memo = {}

    theses = output_json.get("theses")
    if not isinstance(theses, list):
        theses = []

    risks = output_json.get("risks")
    if not isinstance(risks, list):
        risks = []

    thesis_titles = [item.get("title") for item in theses if isinstance(item, dict)]
    risk_titles = [item.get("risk_title") for item in risks if isinstance(item, dict)]

    executive_summary = str(final_memo.get("executive_summary") or "")
    next_questions = final_memo.get("suggested_next_questions")
    if not isinstance(next_questions, list):
        next_questions = []

    theme_scope_key = _build_theme_scope_key(run=run)
    query = str(input_json.get("query") or output_json.get("query") or "")

    content_parts = [
        f"Query focus: {query}" if query else "Query focus: unspecified",
        f"Executive summary: {executive_summary or 'No summary available.'}",
        (
            "Top theses: " + "; ".join(str(value) for value in thesis_titles[:3] if value)
            if thesis_titles
            else "Top theses: none"
        ),
        (
            "Major risks: " + "; ".join(str(value) for value in risk_titles[:3] if value)
            if risk_titles
            else "Major risks: none"
        ),
        (
            "Next questions: " + "; ".join(str(value) for value in next_questions[:3])
            if next_questions
            else "Next questions: none"
        ),
    ]

    score_raw = output_json.get("confidence_score")
    score = float(score_raw) if isinstance(score_raw, (int, float)) else 0.5
    score = max(0.0, min(score, 1.0))

    return [
        MemoryCandidate(
            memory_type=MemoryKind.THEME_MEMORY,
            scope_key=theme_scope_key,
            content="\n".join(content_parts),
            score=score,
            metadata_json={
                "memory_key": f"theme_from_run:{run.id}",
                "source_run_id": run.id,
                "source_run_type": run.run_type.value,
                "thesis_count": len(theses),
                "risk_count": len(risks),
                "insufficient_evidence": bool(output_json.get("insufficient_evidence", False)),
            },
        )
    ]


def _extract_content_generation_memories(*, run: Run) -> list[MemoryCandidate]:
    output_json = run.output_json if isinstance(run.output_json, dict) else {}

    assets_raw = output_json.get("assets")
    assets = assets_raw if isinstance(assets_raw, list) else []

    formats: list[str] = []
    statuses: list[str] = []
    for item in assets:
        if not isinstance(item, dict):
            continue
        content_format = item.get("content_format")
        if isinstance(content_format, str):
            formats.append(content_format)
        status = item.get("status")
        if isinstance(status, str):
            statuses.append(status)

    scope_key = f"theme:{run.theme_id}" if run.theme_id is not None else "account:default"
    format_summary = ", ".join(sorted(set(formats))) if formats else "none"
    status_summary = ", ".join(sorted(set(statuses))) if statuses else "unknown"

    return [
        MemoryCandidate(
            memory_type=MemoryKind.CONTENT_STRATEGY_MEMORY,
            scope_key=scope_key,
            content=(
                "Content generation baseline from run "
                f"{run.id}: formats={format_summary}; statuses={status_summary}; "
                f"asset_count={len(assets)}."
            ),
            score=0.6,
            metadata_json={
                "memory_key": f"content_strategy_from_run:{run.id}",
                "source_run_id": run.id,
                "source_run_type": run.run_type.value,
                "source_research_run_id": output_json.get("source_research_run_id"),
                "formats": sorted(set(formats)),
                "asset_count": len(assets),
            },
        )
    ]


def _extract_run_trace_memory(*, run: Run, steps: list[RunStep]) -> MemoryCandidate:
    step_counter = Counter(step.status.value for step in steps)
    failed_steps = [step.step_name for step in steps if step.status == StepStatus.FAILED]

    content = (
        f"Run {run.id} ({run.run_type.value}) finished with status={run.status.value}. "
        f"Step stats: succeeded={step_counter.get('succeeded', 0)}, "
        f"failed={step_counter.get('failed', 0)}, skipped={step_counter.get('skipped', 0)}."
    )
    score = 0.9 if run.status.value == "succeeded" else 0.2

    return MemoryCandidate(
        memory_type=MemoryKind.RUN_MEMORY,
        scope_key=f"run:{run.id}",
        content=content,
        score=score,
        metadata_json={
            "memory_key": f"run_trace:{run.id}",
            "source_run_id": run.id,
            "source_run_type": run.run_type.value,
            "run_status": run.status.value,
            "step_count": len(steps),
            "step_status_counts": dict(step_counter),
            "failed_steps": failed_steps,
        },
    )


def _build_theme_scope_key(*, run: Run) -> str:
    if run.theme_id is not None:
        return f"theme:{run.theme_id}"

    input_json: dict[str, Any] = run.input_json if isinstance(run.input_json, dict) else {}
    filters = input_json.get("filters")
    if isinstance(filters, dict):
        industry = filters.get("industry")
        if isinstance(industry, str) and industry.strip():
            return f"theme:{_slugify(industry)}"

    query = input_json.get("query")
    if isinstance(query, str) and query.strip():
        return f"theme:{_slugify(query)}"
    return "theme:general"


def _slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "general"
