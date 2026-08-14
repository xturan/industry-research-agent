from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from packages.sources.registry import build_default_source_registry
from packages.sources.schemas import QueryContext, ToolRequest
from packages.sources.service import SourceIntelligenceService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate source acquisition from a single source, pack, or strategy. "
            "Returns non-zero exit code when required checks fail."
        )
    )
    parser.add_argument("--query", required=True, help="Research query used for routing/search.")
    parser.add_argument("--source-id", help="Validate one specific source adapter directly.")
    parser.add_argument("--source-pack", help="Validate a configured source pack.")
    parser.add_argument("--source-strategy", help="Validate a configured source strategy.")
    parser.add_argument(
        "--max-sources",
        type=int,
        default=5,
        help="Max routed sources when validating packs/strategies.",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=3,
        help="Max documents per source.",
    )
    parser.add_argument(
        "--max-evidence",
        type=int,
        default=3,
        help="Max evidence items per source.",
    )
    parser.add_argument(
        "--must-contain",
        action="append",
        default=[],
        help=(
            "Keyword that must appear in titles, summaries, evidence text, or citations. "
            "Can be repeated."
        ),
    )
    parser.add_argument(
        "--regional-focus",
        action="append",
        default=[],
        help="Optional regional focus for domestic routing. Can be repeated.",
    )
    parser.add_argument(
        "--domestic-mode",
        default=None,
        help="Optional domestic mode such as `tiao_priority`.",
    )
    parser.add_argument(
        "--show-docs",
        action="store_true",
        help="Print document-level summary.",
    )
    parser.add_argument(
        "--show-evidence",
        action="store_true",
        help="Print evidence-level summary.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry = build_default_source_registry()
    service = SourceIntelligenceService(source_registry=registry)

    query_context = QueryContext(
        query=args.query,
        source_pack=args.source_pack,
        source_strategy=args.source_strategy,
        domestic_mode=args.domestic_mode,
        regional_focus=args.regional_focus,
        max_sources=args.max_sources,
        max_documents_per_source=args.max_docs,
        max_evidence_per_source=args.max_evidence,
    )

    if args.source_id:
        summary = validate_single_source(
            source_id=args.source_id,
            query_context=query_context,
            limit=args.max_docs,
            max_evidence=args.max_evidence,
            show_docs=args.show_docs,
            show_evidence=args.show_evidence,
        )
    else:
        summary = validate_bundle(
            service=service,
            query_context=query_context,
            limit=args.max_docs,
            max_evidence=args.max_evidence,
            show_docs=args.show_docs,
            show_evidence=args.show_evidence,
        )

    keyword_failures = check_keywords(summary, args.must_contain)
    summary["keyword_failures"] = keyword_failures
    summary["ok"] = not keyword_failures and summary.get("ok", False)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    else:
        print_human_summary(summary)

    return 0 if summary["ok"] else 1


def validate_single_source(
    *,
    source_id: str,
    query_context: QueryContext,
    limit: int,
    max_evidence: int,
    show_docs: bool,
    show_evidence: bool,
) -> dict[str, Any]:
    registry = build_default_source_registry()
    profile = registry.get_profile(source_id, enabled_only=False)
    adapter = registry.get_adapter(source_id, enabled_only=True)
    if profile is None:
        return {
            "mode": "single_source",
            "source_id": source_id,
            "ok": False,
            "error": f"source_id `{source_id}` not found in registry.",
        }
    if adapter is None:
        return {
            "mode": "single_source",
            "source_id": source_id,
            "ok": False,
            "error": f"source_id `{source_id}` is disabled or has no adapter.",
            "profile": profile.model_dump(mode="json"),
        }

    search_request = ToolRequest(
        tool_name="search_source_documents",
        query_context=query_context,
        source_id=source_id,
        limit=limit,
        max_evidence_per_source=max_evidence,
    )
    search = adapter.search_documents(search_request)

    documents = [
        {
            "document_id": item.document_id,
            "title": item.title,
            "source_uri": item.source_uri,
            "published_at": item.published_at,
        }
        for item in search.documents
    ]

    details: list[dict[str, Any]] = []
    evidence_items: list[dict[str, Any]] = []
    if search.documents:
        for item in search.documents[:limit]:
            detail = adapter.fetch_document_detail(
                ToolRequest(
                    tool_name="fetch_document_detail",
                    query_context=query_context,
                    source_id=source_id,
                    document_id=item.document_id,
                    limit=1,
                    max_evidence_per_source=max_evidence,
                )
            )
            details.append(
                {
                    "document_id": item.document_id,
                    "status": detail.status.value,
                    "normalized_count": len(detail.normalized_documents),
                    "errors": [err.message for err in detail.errors],
                    "attachment_refs": collect_attachment_refs(detail.normalized_documents),
                }
            )

        extract = adapter.extract_evidence_items(
            ToolRequest(
                tool_name="extract_evidence_items",
                query_context=query_context,
                source_id=source_id,
                document_id=search.documents[0].document_id,
                max_evidence_per_source=max_evidence,
            )
        )
        evidence_items = [
            {
                "evidence_id": item.evidence_id,
                "title": item.title,
                "summary": item.summary,
                "score": item.score,
                "source_uri": item.citation.source_uri,
                "quote_text": item.citation.quote_text,
                "locator": item.citation.metadata.get("locator"),
            }
            for item in extract.evidence_items
        ]
        extract_status = extract.status.value
        extract_errors = [err.message for err in extract.errors]
    else:
        extract_status = "skipped"
        extract_errors = []

    return {
        "mode": "single_source",
        "source_id": source_id,
        "display_name": profile.display_name,
        "ok": bool(search.documents),
        "search_status": search.status.value,
        "search_errors": [err.message for err in search.errors],
        "document_count": len(search.documents),
        "documents": documents if show_docs else [],
        "detail_results": details,
        "extract_status": extract_status,
        "extract_errors": extract_errors,
        "evidence_count": len(evidence_items),
        "evidence_items": evidence_items if show_evidence else [],
        "raw_text_for_validation": build_validation_text(
            documents=documents,
            detail_results=details,
            evidence_items=evidence_items,
        ),
    }


def validate_bundle(
    *,
    service: SourceIntelligenceService,
    query_context: QueryContext,
    limit: int,
    max_evidence: int,
    show_docs: bool,
    show_evidence: bool,
) -> dict[str, Any]:
    response = service.build_bundle_for_query(
        query_context,
        limit=limit,
        max_evidence_per_source=max_evidence,
    )
    routed_sources = [item.source_id for item in response.route_recommendations]
    documents = [
        {
            "document_id": item.document_id,
            "source_id": item.source_id,
            "title": item.title,
            "source_uri": item.source_uri,
            "published_at": item.published_at,
        }
        for item in response.documents
    ]
    evidence_items = [
        {
            "evidence_id": item.evidence_id,
            "source_id": item.source_id,
            "title": item.title,
            "summary": item.summary,
            "score": item.score,
            "source_uri": item.citation.source_uri,
            "quote_text": item.citation.quote_text,
            "locator": item.citation.metadata.get("locator"),
        }
        for item in response.evidence_items
    ]
    bundle_id = response.bundle.bundle_id if response.bundle is not None else None
    return {
        "mode": "bundle",
        "source_pack": query_context.source_pack,
        "source_strategy": query_context.source_strategy,
        "ok": bool(response.documents or response.evidence_items),
        "status": response.status.value,
        "errors": [err.message for err in response.errors],
        "routed_sources": routed_sources,
        "document_count": len(response.documents),
        "evidence_count": len(response.evidence_items),
        "bundle_id": bundle_id,
        "source_quality_summary": (
            response.source_quality_summary.model_dump(mode="json")
            if response.source_quality_summary is not None
            else None
        ),
        "governance_snapshot": (
            response.governance_snapshot.model_dump(mode="json")
            if response.governance_snapshot is not None
            else None
        ),
        "documents": documents if show_docs else [],
        "evidence_items": evidence_items if show_evidence else [],
        "raw_text_for_validation": build_validation_text(
            documents=documents,
            detail_results=[],
            evidence_items=evidence_items,
        ),
    }


def collect_attachment_refs(normalized_documents: list[Any]) -> list[str]:
    refs: list[str] = []
    for item in normalized_documents:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        attachment_refs = metadata.get("attachment_refs") or []
        if isinstance(attachment_refs, list):
            for ref in attachment_refs:
                if isinstance(ref, str) and ref.strip():
                    refs.append(ref.strip())
        attachment_ref = metadata.get("attachment_ref")
        if isinstance(attachment_ref, str) and attachment_ref.strip():
            refs.append(attachment_ref.strip())
    return sorted(set(refs))


def build_validation_text(
    *,
    documents: list[dict[str, Any]],
    detail_results: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
) -> str:
    chunks: list[str] = []
    for item in documents:
        chunks.extend(
            [
                str(item.get("title") or ""),
                str(item.get("source_uri") or ""),
            ]
        )
    for item in detail_results:
        chunks.extend(item.get("attachment_refs") or [])
        chunks.extend(item.get("errors") or [])
    for item in evidence_items:
        chunks.extend(
            [
                str(item.get("title") or ""),
                str(item.get("summary") or ""),
                str(item.get("quote_text") or ""),
                str(item.get("source_uri") or ""),
                str(item.get("locator") or ""),
            ]
        )
    return "\n".join(chunks)


def check_keywords(summary: dict[str, Any], keywords: list[str]) -> list[str]:
    haystack = str(summary.get("raw_text_for_validation") or "").lower()
    failures: list[str] = []
    for keyword in keywords:
        needle = keyword.strip().lower()
        if needle and needle not in haystack:
            failures.append(keyword)
    return failures


def print_human_summary(summary: dict[str, Any]) -> None:
    mode = summary.get("mode")
    print(f"mode: {mode}")
    print(f"ok: {summary.get('ok')}")

    if mode == "single_source":
        print(f"source_id: {summary.get('source_id')}")
        print(f"display_name: {summary.get('display_name')}")
        print(f"search_status: {summary.get('search_status')}")
        print(f"document_count: {summary.get('document_count')}")
        print(f"extract_status: {summary.get('extract_status')}")
        print(f"evidence_count: {summary.get('evidence_count')}")
        if summary.get("search_errors"):
            print("search_errors:")
            for item in summary["search_errors"]:
                print(f"  - {item}")
        if summary.get("extract_errors"):
            print("extract_errors:")
            for item in summary["extract_errors"]:
                print(f"  - {item}")
        for item in summary.get("detail_results", []):
            print(
                "detail_result: "
                f"document_id={item['document_id']} "
                f"status={item['status']} "
                f"normalized_count={item['normalized_count']} "
                f"attachment_refs={item['attachment_refs']}"
            )
        if summary.get("documents"):
            print("documents:")
            for item in summary["documents"]:
                print(f"  - {item['title']} | {item['source_uri']}")
        if summary.get("evidence_items"):
            print("evidence_items:")
            for item in summary["evidence_items"]:
                print(f"  - {item['title']} | score={item['score']} | {item['source_uri']}")
    else:
        print(f"source_pack: {summary.get('source_pack')}")
        print(f"source_strategy: {summary.get('source_strategy')}")
        print(f"status: {summary.get('status')}")
        print(f"bundle_id: {summary.get('bundle_id')}")
        print(f"routed_sources: {summary.get('routed_sources')}")
        print(f"document_count: {summary.get('document_count')}")
        print(f"evidence_count: {summary.get('evidence_count')}")
        if summary.get("errors"):
            print("errors:")
            for item in summary["errors"]:
                print(f"  - {item}")
        if summary.get("source_quality_summary") is not None:
            print(
                "source_quality_summary: "
                f"{json.dumps(summary['source_quality_summary'], ensure_ascii=False)}"
            )
        if summary.get("documents"):
            print("documents:")
            for item in summary["documents"]:
                print(f"  - [{item['source_id']}] {item['title']} | {item['source_uri']}")
        if summary.get("evidence_items"):
            print("evidence_items:")
            for item in summary["evidence_items"]:
                print(
                    f"  - [{item['source_id']}] {item['title']} "
                    f"| score={item['score']} | {item['source_uri']}"
                )

    if summary.get("keyword_failures"):
        print(f"keyword_failures: {summary['keyword_failures']}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
