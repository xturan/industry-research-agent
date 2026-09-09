from __future__ import annotations

import hashlib
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse

from packages.db.models import SourceType
from packages.ingestion.fetchers import fetch_local_file, fetch_url
from packages.ingestion.parser import parse_source
from packages.sources.adapters.base import BaseSourceAdapter
from packages.sources.citation import normalize_evidence_item
from packages.sources.enums import (
    AccessMethod,
    SourceCategory,
    ToolErrorCode,
    ToolStatus,
    TrustTier,
)
from packages.sources.schemas import (
    Citation,
    CitationLocator,
    DocumentSection,
    EvidenceItem,
    NormalizedDocument,
    QueryContext,
    RawDocument,
    SourceAccess,
    SourceCapabilities,
    SourceProfile,
    ToolError,
    ToolRequest,
    ToolResponse,
    UserProvidedSource,
)


class UserInputAdapter(BaseSourceAdapter):
    ADAPTER_VERSION = "v1.2"

    def get_profile(self) -> SourceProfile:
        return SourceProfile(
            source_id="user_input",
            display_name="User Provided Sources",
            category=SourceCategory.USER_PROVIDED,
            trust_tier=TrustTier.USER_PROVIDED,
            enabled=True,
            description="Adapts user-uploaded links/text into source-intelligence contracts.",
            access=SourceAccess(access_method=AccessMethod.FILE_UPLOAD, auth_required=False),
            capabilities=SourceCapabilities(
                supports_search=True,
                supports_document_detail=True,
                supports_evidence_extraction=True,
                supports_time_filter=False,
                supports_keyword_filter=True,
                supports_bulk=False,
            ),
            priority_hint=100,
            tags=["manual", "inline", "high-context"],
        )

    def search_documents(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        context = request.query_context
        limit, offset, page = self.resolve_limit_offset(
            request,
            default_limit=context.max_documents_per_source,
            max_limit=500,
        )
        documents: list[RawDocument] = []
        normalized_documents: list[NormalizedDocument] = []
        errors: list[ToolError] = []
        for index, source in enumerate(context.user_provided_sources):
            try:
                raw_document, normalized = self._build_documents(context, index, source)
                documents.append(raw_document)
                normalized_documents.append(normalized)
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=f"user_input source index={index} parse failed: {exc}",
                        retryable=False,
                    )
                )
        total_available = len(documents)
        documents = documents[offset : offset + limit]
        normalized_documents = normalized_documents[offset : offset + limit]
        truncated = total_available > (offset + len(documents))
        warnings: list[str] = []
        if total_available == 0:
            warnings.append("No user_provided_sources available.")
        if offset >= total_available and total_available > 0:
            warnings.append("Offset exceeds available user-provided documents.")
        status = ToolStatus.SUCCESS if documents and not errors else ToolStatus.PARTIAL
        if not documents and errors:
            status = ToolStatus.ERROR
        if not documents and not errors:
            status = ToolStatus.PARTIAL
        return ToolResponse(
            status=status,
            tool_name=request.tool_name,
            source_id="user_input",
            documents=documents,
            normalized_documents=normalized_documents,
            errors=errors,
            message=f"Loaded {len(documents)} user-provided source document(s).",
            trace=self.build_trace(
                request=request,
                status=status,
                duration_ms=(perf_counter() - started) * 1000.0,
                page_count=max(((total_available - 1) // max(limit, 1)) + 1, 1)
                if total_available
                else 0,
                item_count=len(documents),
                retry_count=0,
                truncated=truncated,
                warnings=warnings,
                metadata={"total_available": total_available, "offset": offset, "page": page},
            ),
        )

    def fetch_document_detail(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        if request.document_id is None:
            return ToolResponse(
                status=ToolStatus.ERROR,
                tool_name=request.tool_name,
                source_id="user_input",
                message="document_id is required for user_input document detail.",
                trace=self.build_trace(
                    request=request,
                    status=ToolStatus.ERROR,
                    duration_ms=(perf_counter() - started) * 1000.0,
                    warnings=["document_id is required."],
                ),
            )
        response = self.search_documents(request.with_source("user_input"))
        documents = response.documents
        normalized = response.normalized_documents
        matched = [doc for doc in documents if doc.document_id == request.document_id]
        normalized_matched = [doc for doc in normalized if doc.document_id == request.document_id]
        status = ToolStatus.SUCCESS if matched else ToolStatus.ERROR
        return ToolResponse(
            status=status,
            tool_name=request.tool_name,
            source_id="user_input",
            documents=matched,
            normalized_documents=normalized_matched,
            errors=response.errors,
            message=(
                "Document found."
                if matched
                else "Document not found in user_provided_sources."
            ),
            trace=self.build_trace(
                request=request,
                status=status,
                duration_ms=(perf_counter() - started) * 1000.0,
                item_count=len(matched),
                metadata={"searched_documents": len(documents)},
            ),
        )

    def extract_evidence_items(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        response = self.search_documents(request.with_source("user_input"))
        evidence_items: list[EvidenceItem] = []
        evidence_limit = self.resolve_evidence_limit(
            request,
            default_limit=request.query_context.max_evidence_per_source,
            max_limit=500,
        )
        for idx, normalized_document in enumerate(response.normalized_documents):
            text = (normalized_document.summary or "").strip()
            if not text and normalized_document.sections:
                text = normalized_document.sections[0].text.strip()
            if not text:
                continue
            document_id = normalized_document.document_id
            locator = CitationLocator(document_id=document_id, section_id="section_0")
            citation = Citation(
                citation_id=f"cit_user_{idx}",
                source_id="user_input",
                document_id=document_id,
                locator=locator,
                quote_text=text[:240],
                source_uri=normalized_document.metadata.get("source_uri"),
                published_at=normalized_document.published_at,
                )
            evidence_items.append(
                normalize_evidence_item(
                    EvidenceItem(
                    evidence_id=f"evi_user_{idx}",
                    source_id="user_input",
                    title=normalized_document.title,
                    summary=text[:180],
                    support_text=text[:400],
                    score=0.65,
                    citation=citation,
                    metadata={
                        "origin": "user_provided_source",
                        "section_name": "section_0",
                        "source_kind": "user_input",
                    },
                ),
                    source_name=self.get_profile().display_name,
                    external_id=document_id,
                )
            )
        total_evidence = len(evidence_items)
        evidence_items = evidence_items[:evidence_limit]
        truncated = total_evidence > len(evidence_items)
        status = ToolStatus.SUCCESS if evidence_items else ToolStatus.PARTIAL
        return ToolResponse(
            status=status,
            tool_name=request.tool_name,
            source_id="user_input",
            documents=response.documents,
            normalized_documents=response.normalized_documents,
            evidence_items=evidence_items,
            errors=response.errors,
            message=(
                f"Extracted {len(evidence_items)} evidence item(s) from user-provided input."
                if evidence_items
                else "No inline user-provided text found for evidence extraction."
            ),
            trace=self.build_trace(
                request=request,
                status=status,
                duration_ms=(perf_counter() - started) * 1000.0,
                item_count=len(response.documents),
                evidence_count=len(evidence_items),
                truncated=truncated,
                metadata={
                    "total_evidence_before_limit": total_evidence,
                    "evidence_limit": evidence_limit,
                },
            ),
        )

    def _build_documents(
        self,
        context: QueryContext,
        index: int,
        source: UserProvidedSource,
    ) -> tuple[RawDocument, NormalizedDocument]:
        document_id = self._build_document_id(source=source, index=index)
        title = source.title or f"User Source {index + 1}"
        published_at = source.published_at
        language = source.language
        source_uri = source.source_uri
        raw_text = source.inline_text
        sections: list[DocumentSection] = []

        if source.inline_text:
            text = source.inline_text.strip()
            if text:
                sections = [DocumentSection(section_id="section_0", heading=None, text=text)]
        elif source.file_ref:
            raw = fetch_local_file(source.file_ref, source_type=SourceType.OTHER)
            parsed = parse_source(raw)
            title = source.title or parsed.title
            source_uri = source_uri or raw.source_uri
            published_at = source.published_at or parsed.published_at
            language = source.language or "en"
            raw_text = parsed.text
            sections = self._sections_from_parsed(parsed)
        elif source.source_uri:
            parsed_uri = urlparse(source.source_uri)
            if parsed_uri.scheme in {"http", "https"}:
                raw = fetch_url(source.source_uri, source_type=SourceType.ARTICLE)
                parsed = parse_source(raw)
                title = source.title or parsed.title
                source_uri = raw.source_uri
                published_at = source.published_at or parsed.published_at
                language = source.language or "en"
                raw_text = parsed.text
                sections = self._sections_from_parsed(parsed)
            else:
                raw = fetch_local_file(Path(source.source_uri), source_type=SourceType.OTHER)
                parsed = parse_source(raw)
                title = source.title or parsed.title
                source_uri = raw.source_uri
                published_at = source.published_at or parsed.published_at
                language = source.language or "en"
                raw_text = parsed.text
                sections = self._sections_from_parsed(parsed)

        raw_document = RawDocument(
            document_id=document_id,
            source_id="user_input",
            title=title,
            source_uri=source_uri,
            published_at=published_at,
            language=language,
            raw_text=raw_text,
            snippet=(raw_text or "").strip()[:240] or None,
            metadata=source.metadata,
        )
        normalized = NormalizedDocument(
            document_id=document_id,
            source_id="user_input",
            title=title,
            language=language,
            published_at=published_at,
            summary=(raw_text or "").strip()[:400] or None,
            sections=sections,
            metadata={"origin": "user_input", "source_uri": source_uri, **source.metadata},
        )
        return raw_document, normalized

    def _build_document_id(self, *, source: UserProvidedSource, index: int) -> str:
        key = source.source_uri or source.file_ref or source.inline_text or str(index)
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
        return f"user_input_{index}_{digest}"

    def _sections_from_parsed(self, parsed) -> list[DocumentSection]:  # noqa: ANN001
        sections: list[DocumentSection] = []
        for idx, section in enumerate(parsed.sections):
            sections.append(
                DocumentSection(
                    section_id=f"section_{idx}",
                    heading=section.section_name,
                    text=section.text,
                    order_index=idx,
                    metadata={"locator": section.locator, **section.metadata},
                )
            )
        if not sections and parsed.text.strip():
            sections = [
                DocumentSection(
                    section_id="section_0",
                    heading=None,
                    text=parsed.text.strip(),
                )
            ]
        return sections
