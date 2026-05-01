from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.sources.enums import ToolStatus
from packages.sources.schemas import (
    EvidenceItem,
    SourceContributionItem,
    SourceGovernanceSnapshot,
    SourceSummaryItem,
    ToolTrace,
)

_FETCH_TOOL_NAMES = {"search_source_documents", "fetch_document_detail"}
_PARSE_TOOL_NAMES = {"extract_evidence_items"}
_DRIFT_WARNING_KEYWORDS = (
    "no list items discovered",
    "detail page parser returned no detail pages",
    "document_not_found",
    "selector",
    "drift",
)

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone(timedelta(0))


def build_source_governance_snapshot(
    *,
    traces: list[ToolTrace],
    source_summaries: list[SourceSummaryItem],
    evidence_items: list[EvidenceItem],
    dedupe_metadata: dict[str, int] | None = None,
) -> SourceGovernanceSnapshot:
    fetch_traces = [trace for trace in traces if trace.tool_name in _FETCH_TOOL_NAMES]
    parse_traces = [trace for trace in traces if trace.tool_name in _PARSE_TOOL_NAMES]

    fetch_success = sum(
        1 for trace in fetch_traces if trace.status in {ToolStatus.SUCCESS, ToolStatus.PARTIAL}
    )
    parse_success = sum(
        1 for trace in parse_traces if trace.status in {ToolStatus.SUCCESS, ToolStatus.PARTIAL}
    )

    attachment_discovered = 0
    attachment_processed = 0
    for trace in traces:
        meta = trace.metadata if isinstance(trace.metadata, dict) else {}
        attachment_discovered += _safe_int(meta.get("attachment_count"))
        pdf_processing = meta.get("pdf_processing")
        if isinstance(pdf_processing, dict):
            attachment_processed += _safe_int(pdf_processing.get("processed_attachments"))

    attachment_success_rate = 0.0
    if attachment_discovered > 0:
        attachment_success_rate = min(
            attachment_processed / float(max(attachment_discovered, 1)),
            1.0,
        )

    warning_count = 0
    total_warning_pool = 0
    for trace in traces:
        for warning in trace.warnings:
            total_warning_pool += 1
            warning_lower = warning.lower()
            if any(keyword in warning_lower for keyword in _DRIFT_WARNING_KEYWORDS):
                warning_count += 1
    drift_rate = 0.0
    if total_warning_pool > 0:
        drift_rate = warning_count / float(total_warning_pool)

    dedupe = dedupe_metadata or {}
    removed_docs = _safe_int(dedupe.get("removed_document_duplicates"))
    removed_evi = _safe_int(dedupe.get("removed_evidence_duplicates"))
    docs_after = _safe_int(dedupe.get("document_count_after_dedupe"))
    evi_after = _safe_int(dedupe.get("evidence_count_after_dedupe"))
    duplicate_before = removed_docs + removed_evi + docs_after + evi_after
    duplicate_ratio = 0.0
    if duplicate_before > 0:
        duplicate_ratio = (removed_docs + removed_evi) / float(duplicate_before)

    generated_at = datetime.now(UTC)
    freshness_lags: list[float] = []
    evidence_by_source: dict[str, list[EvidenceItem]] = {}
    for item in evidence_items:
        evidence_by_source.setdefault(item.source_id, []).append(item)
        if item.citation.published_at is not None:
            freshness_lags.append(
                _hours_between(item.citation.published_at, generated_at)
            )
    freshness_lag_avg = None
    if freshness_lags:
        freshness_lag_avg = sum(freshness_lags) / float(len(freshness_lags))

    total_docs = sum(summary.document_count for summary in source_summaries)
    pack_density = len(evidence_items) / float(max(total_docs, 1))

    contribution_items: list[SourceContributionItem] = []
    for summary in source_summaries:
        per_source_evidence = evidence_by_source.get(summary.source_id, [])
        lag_values = []
        for item in per_source_evidence:
            if item.citation.published_at is None:
                continue
            lag_values.append(_hours_between(item.citation.published_at, generated_at))
        lag_avg = None
        if lag_values:
            lag_avg = sum(lag_values) / float(len(lag_values))

        contribution_score = (
            summary.evidence_count * 2.0
            + summary.document_count * 0.5
            + min(1.0, len(per_source_evidence) / float(max(summary.document_count, 1))) * 2.0
        )
        contribution_items.append(
            SourceContributionItem(
                source_id=summary.source_id,
                evidence_count=summary.evidence_count,
                document_count=summary.document_count,
                contribution_score=round(contribution_score, 4),
                freshness_lag_hours=(round(lag_avg, 4) if lag_avg is not None else None),
            )
        )

    contribution_items = sorted(
        contribution_items,
        key=lambda item: (-item.contribution_score, item.source_id),
    )

    warnings = []
    if not traces:
        warnings.append("No traces available for governance snapshot.")
    if not source_summaries:
        warnings.append("No source summaries available for governance snapshot.")

    return SourceGovernanceSnapshot(
        generated_at=generated_at,
        fetch_success_rate=round(fetch_success / float(max(len(fetch_traces), 1)), 6),
        parse_success_rate=round(parse_success / float(max(len(parse_traces), 1)), 6),
        attachment_success_rate=round(attachment_success_rate, 6),
        drift_rate=round(drift_rate, 6),
        duplicate_ratio=round(duplicate_ratio, 6),
        freshness_lag_hours_avg=(
            round(freshness_lag_avg, 4) if freshness_lag_avg is not None else None
        ),
        pack_evidence_density=round(pack_density, 6),
        source_contribution=contribution_items,
        warnings=warnings,
        metadata={
            "fetch_trace_count": len(fetch_traces),
            "parse_trace_count": len(parse_traces),
            "attachment_discovered": attachment_discovered,
            "attachment_processed": attachment_processed,
            "trace_count": len(traces),
        },
    )


def _safe_int(value: object) -> int:
    try:
        if value is None:
            return 0
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _hours_between(start: datetime, end: datetime) -> float:
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    return max((end - start).total_seconds() / 3600.0, 0.0)
