from __future__ import annotations

from collections import Counter

from packages.sources.enums import ToolStatus
from packages.sources.schemas import (
    EvidenceItem,
    SourceQualitySummary,
    SourceSummaryItem,
    ToolError,
    ToolTrace,
)

_CITATION_KEYS = (
    "source_name",
    "source_id",
    "title",
    "url",
    "published_at",
    "retrieved_at",
    "locator",
    "external_id",
)


def summarize_source_quality(
    *,
    source_ids: list[str],
    traces: list[ToolTrace],
    errors: list[ToolError],
    evidence_items: list[EvidenceItem],
    source_summaries: list[SourceSummaryItem],
) -> SourceQualitySummary:
    attempted = len(source_ids)
    traces_by_source: dict[str, list[ToolTrace]] = {}
    for trace in traces:
        if trace.source_id is None:
            continue
        traces_by_source.setdefault(trace.source_id, []).append(trace)
    succeeded = 0
    failed = 0
    truncated_sources: list[str] = []
    warnings: list[str] = []

    for source_id in source_ids:
        source_traces = traces_by_source.get(source_id, [])
        if not source_traces:
            failed += 1
            warnings.append(f"Missing trace for source={source_id}.")
            continue

        has_error_status = False
        has_success_status = False
        has_not_implemented_only = True
        for trace in source_traces:
            if trace.truncated:
                truncated_sources.append(source_id)
            warnings.extend(trace.warnings)
            if trace.status == ToolStatus.ERROR:
                has_error_status = True
            if trace.status in {ToolStatus.SUCCESS, ToolStatus.PARTIAL}:
                has_success_status = True
            if trace.status not in {ToolStatus.NOT_IMPLEMENTED, ToolStatus.UNSUPPORTED}:
                has_not_implemented_only = False

        if has_error_status:
            failed += 1
            continue
        if has_success_status:
            succeeded += 1
            continue
        if has_not_implemented_only:
            failed += 1
            continue
        succeeded += 1

    error_breakdown = Counter(error.code.value for error in errors)
    citation_score = _citation_completeness_score(evidence_items)
    total_docs = sum(item.document_count for item in source_summaries)
    evidence_density = round(
        len(evidence_items) / float(max(total_docs, 1)),
        6,
    )
    return SourceQualitySummary(
        sources_attempted=attempted,
        sources_succeeded=succeeded,
        sources_failed=failed,
        source_error_breakdown=dict(error_breakdown),
        citation_completeness_score=citation_score,
        evidence_density=evidence_density,
        truncated_sources=sorted(set(truncated_sources)),
        warnings=warnings,
    )


def _citation_completeness_score(evidence_items: list[EvidenceItem]) -> float:
    if not evidence_items:
        return 0.0
    total_ratio = 0.0
    for item in evidence_items:
        metadata = item.citation.metadata or {}
        present = 0
        for key in _CITATION_KEYS:
            value = metadata.get(key)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            present += 1
        total_ratio += present / float(len(_CITATION_KEYS))
    return round(total_ratio / float(len(evidence_items)), 6)
