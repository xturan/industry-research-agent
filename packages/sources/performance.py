from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.models import Run
from packages.db.models.enums import RunType
from packages.sources.schemas import SourcePerformanceItem, SourcePerformanceSummary

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc


_TRACE_STAGE_ORDER = {
    "search_source_documents": 1,
    "fetch_document_detail": 2,
    "extract_evidence_items": 3,
}


@dataclass(slots=True)
class _SourceAccumulator:
    attempt_count: int = 0
    success_count: int = 0
    partial_count: int = 0
    failure_count: int = 0
    no_result_count: int = 0
    latency_total: float = 0.0
    evidence_density_total: float = 0.0
    citation_completeness_total: float = 0.0
    last_seen_at: datetime | None = None


class SourcePerformanceService:
    # TODO: Extend aggregation with per-source eval_run_items once source benchmarks grow.
    # TODO: Add cached materialization for high-QPS ops dashboards.

    def __init__(self, session: Session) -> None:
        self.session = session

    def summarize(
        self,
        *,
        lookback_days: int = 30,
        max_runs: int = 500,
    ) -> SourcePerformanceSummary:
        lookback_days = max(1, min(lookback_days, 3650))
        max_runs = max(1, min(max_runs, 5000))
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

        rows = self.session.scalars(
            select(Run)
            .where(Run.run_type == RunType.RESEARCH, Run.created_at >= cutoff)
            .order_by(Run.created_at.desc(), Run.id.desc())
            .limit(max_runs)
        ).all()

        accumulators: dict[str, _SourceAccumulator] = {}
        for run in rows:
            output_json = run.output_json if isinstance(run.output_json, dict) else {}
            source_acquisition = output_json.get("source_acquisition")
            if not isinstance(source_acquisition, dict):
                continue
            if not bool(source_acquisition.get("enabled")):
                continue

            routed_sources = source_acquisition.get("routed_sources")
            routed_sources = (
                [str(item) for item in routed_sources if str(item).strip()]
                if isinstance(routed_sources, list)
                else []
            )
            if not routed_sources:
                continue

            source_quality_summary = source_acquisition.get("source_quality_summary")
            quality_json = (
                source_quality_summary
                if isinstance(source_quality_summary, dict)
                else {}
            )
            citation_score = _safe_float(
                quality_json.get("citation_completeness_score"),
                default=0.0,
            )

            trace_rows = source_acquisition.get("source_traces")
            trace_rows = trace_rows if isinstance(trace_rows, list) else []
            final_traces = _pick_final_source_traces(trace_rows)

            for source_id in routed_sources:
                acc = accumulators.setdefault(source_id, _SourceAccumulator())
                acc.attempt_count += 1
                acc.citation_completeness_total += citation_score
                if run.created_at is not None and (
                    acc.last_seen_at is None or run.created_at > acc.last_seen_at
                ):
                    acc.last_seen_at = run.created_at

                trace = final_traces.get(source_id)
                if not isinstance(trace, dict):
                    acc.failure_count += 1
                    acc.no_result_count += 1
                    continue

                status = str(trace.get("status") or "").lower()
                if status == "success":
                    acc.success_count += 1
                elif status == "partial":
                    acc.partial_count += 1
                else:
                    acc.failure_count += 1

                duration_ms = _safe_float(trace.get("duration_ms"), default=0.0)
                if duration_ms > 0:
                    acc.latency_total += duration_ms

                evidence_count = _safe_int(trace.get("evidence_count"), default=0)
                item_count = max(_safe_int(trace.get("item_count"), default=0), 1)
                evidence_density = evidence_count / float(item_count)
                if evidence_density > 0:
                    acc.evidence_density_total += evidence_density
                if evidence_count <= 0:
                    acc.no_result_count += 1

        items: list[SourcePerformanceItem] = []
        for source_id, acc in accumulators.items():
            attempts = max(acc.attempt_count, 1)
            items.append(
                SourcePerformanceItem(
                    source_id=source_id,
                    attempt_count=acc.attempt_count,
                    success_count=acc.success_count,
                    partial_count=acc.partial_count,
                    failure_count=acc.failure_count,
                    no_result_count=acc.no_result_count,
                    avg_latency_ms=round(acc.latency_total / attempts, 6),
                    avg_evidence_density=round(acc.evidence_density_total / attempts, 6),
                    avg_citation_completeness=round(
                        acc.citation_completeness_total / attempts,
                        6,
                    ),
                    last_seen_at=acc.last_seen_at,
                )
            )

        items.sort(
            key=lambda item: (
                -item.attempt_count,
                -item.success_count,
                item.source_id,
            )
        )
        return SourcePerformanceSummary(lookback_days=lookback_days, items=items)

    def by_source(
        self,
        *,
        lookback_days: int = 30,
        max_runs: int = 500,
    ) -> dict[str, SourcePerformanceItem]:
        summary = self.summarize(lookback_days=lookback_days, max_runs=max_runs)
        return {item.source_id: item for item in summary.items}


def _pick_final_source_traces(trace_rows: list[Any]) -> dict[str, dict[str, Any]]:
    by_source: dict[str, tuple[int, dict[str, Any]]] = {}
    for row in trace_rows:
        if not isinstance(row, dict):
            continue
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            continue
        stage_rank = _TRACE_STAGE_ORDER.get(str(row.get("tool_name") or ""), 0)
        existing = by_source.get(source_id)
        if existing is None or stage_rank >= existing[0]:
            by_source[source_id] = (stage_rank, row)
    return {source_id: row for source_id, (_rank, row) in by_source.items()}


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
