from __future__ import annotations

import hashlib
from collections.abc import Iterable

from packages.sources.collectors.base import (
    DetailPageContent,
    DiscoveredItem,
    PdfArtifact,
    PdfTextDocument,
)
from packages.sources.schemas import DocumentSection, NormalizedDocument, RawDocument


def build_domestic_document_id(
    source_id: str,
    *,
    url: str | None = None,
    external_id: str | None = None,
    prefix: str = "cn_doc",
) -> str:
    stable_key = external_id or url or source_id
    digest = hashlib.sha1(stable_key.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{source_id}_{digest}"


def normalize_discovered_item_to_raw_document(
    item: DiscoveredItem,
    *,
    publisher: str | None = None,
) -> RawDocument:
    return RawDocument(
        document_id=build_domestic_document_id(
            item.source_id,
            url=item.url,
            external_id=item.external_id or item.item_id,
        ),
        source_id=item.source_id,
        title=item.title,
        source_uri=item.url,
        publisher=publisher,
        published_at=item.published_at,
        language="zh-CN",
        snippet=item.summary,
        metadata={
            **item.metadata,
            "item_id": item.item_id,
            "external_id": item.external_id,
            "list_position": item.list_position,
        },
    )


def normalize_detail_page_to_documents(
    detail: DetailPageContent,
    *,
    attachments: Iterable[PdfArtifact] | None = None,
) -> tuple[RawDocument, NormalizedDocument]:
    attachment_refs = [artifact.attachment_ref or artifact.url for artifact in attachments or []]
    text_sections = detail.sections or [
        DocumentSection(
            section_id="main_content",
            heading=detail.title,
            text=detail.text_content or detail.summary or detail.title,
        )
    ]
    raw = RawDocument(
        document_id=build_domestic_document_id(
            detail.source_id,
            url=detail.url,
            external_id=detail.item_id,
        ),
        source_id=detail.source_id,
        title=detail.title,
        source_uri=detail.url,
        published_at=detail.published_at,
        language="zh-CN",
        raw_text=detail.text_content,
        snippet=detail.summary,
        metadata={
            **detail.metadata,
            "item_id": detail.item_id,
            "attachment_refs": attachment_refs,
            "collector_contract": "html_list_detail_v1",
        },
    )
    normalized = NormalizedDocument(
        document_id=raw.document_id,
        source_id=detail.source_id,
        title=detail.title,
        language="zh-CN",
        published_at=detail.published_at,
        summary=detail.summary,
        sections=text_sections,
        metadata={
            **detail.metadata,
            "attachment_refs": attachment_refs,
            "detail_url": detail.url,
        },
    )
    return raw, normalized


def normalize_pdf_text_document(
    pdf_text: PdfTextDocument,
    *,
    title: str | None = None,
    document_id: str | None = None,
    published_at=None,
) -> NormalizedDocument:
    resolved_document_id = document_id or build_domestic_document_id(
        pdf_text.source_id,
        url=pdf_text.url,
        external_id=pdf_text.artifact_id,
        prefix="cn_pdf",
    )
    sections = [
        DocumentSection(
            section_id=f"page_{page.page_number}",
            heading=f"Page {page.page_number}",
            text=page.text or "",
            order_index=page.page_number - 1,
            metadata={
                **page.metadata,
                "page_number": page.page_number,
                "char_count": page.char_count,
            },
        )
        for page in pdf_text.pages
        if page.text
    ]
    return NormalizedDocument(
        document_id=resolved_document_id,
        source_id=pdf_text.source_id,
        title=title or pdf_text.title or pdf_text.artifact_id,
        language="zh-CN",
        published_at=published_at,
        summary=(pdf_text.full_text[:280] if pdf_text.full_text else None),
        sections=sections,
        metadata={
            **pdf_text.metadata,
            "artifact_id": pdf_text.artifact_id,
            "pdf_url": pdf_text.url,
            "pdf_page_count": len(pdf_text.pages),
            "collector_contract": "pdf_text_extract_v1",
        },
    )


def normalize_pdf_text_to_documents(
    pdf_text: PdfTextDocument,
    *,
    title: str | None = None,
    published_at=None,
    publisher: str | None = None,
) -> tuple[RawDocument, NormalizedDocument]:
    document_id = build_domestic_document_id(
        pdf_text.source_id,
        url=pdf_text.url,
        external_id=pdf_text.artifact_id,
        prefix="cn_pdf",
    )
    normalized = normalize_pdf_text_document(
        pdf_text,
        title=title,
        document_id=document_id,
        published_at=published_at,
    )
    raw = RawDocument(
        document_id=document_id,
        source_id=pdf_text.source_id,
        title=normalized.title,
        source_uri=pdf_text.url,
        publisher=publisher,
        published_at=published_at,
        language=normalized.language,
        raw_text=pdf_text.full_text,
        snippet=(pdf_text.full_text[:240] if pdf_text.full_text else None),
        metadata={
            **normalized.metadata,
            "pdf_page_count": len(pdf_text.pages),
            "attachment_ref": pdf_text.metadata.get("attachment_ref"),
            "attachment_url": pdf_text.metadata.get("attachment_url") or pdf_text.url,
            "collector_contract": "pdf_attachment_pipeline_v1",
            **({"publisher": publisher} if publisher else {}),
        },
    )
    normalized.metadata = {
        **normalized.metadata,
        **({"publisher": publisher} if publisher else {}),
    }
    return raw, normalized
