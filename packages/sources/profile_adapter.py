from __future__ import annotations

import re
from time import perf_counter

from packages.sources.adapters.base import BaseSourceAdapter
from packages.sources.citation import normalize_evidence_item
from packages.sources.collector_factory import CollectorExecutorFactory
from packages.sources.collectors import (
    BaseCollector,
    CollectorRequest,
    DiscoveredItem,
    PdfArtifact,
    normalize_pdf_text_to_documents,
)
from packages.sources.enums import CollectorType, ToolErrorCode, ToolStatus
from packages.sources.live_fetch import (
    LiveHtmlFetchError,
    LiveHtmlFetchResult,
    LiveHtmlFetchService,
    build_inline_fetch_result,
)
from packages.sources.live_pdf import LivePdfDownloadError, LivePdfDownloadService
from packages.sources.pdf_text import PdfTextExtractionError, PdfTextExtractionService
from packages.sources.schemas import (
    Citation,
    CitationLocator,
    DocumentSection,
    EvidenceItem,
    NormalizedDocument,
    RawDocument,
    SourceProfile,
    ToolError,
    ToolRequest,
    ToolResponse,
)

_QUERY_TERM_PATTERN = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]+")


def _rank_discovered_items_for_query(
    items: list[DiscoveredItem],
    *,
    request: ToolRequest,
) -> list[DiscoveredItem]:
    if not items or request.query_context is None:
        return items

    query = request.query_context.query
    task_family = str(request.query_context.metadata.get("task_family") or "")
    scored_items = [
        (
            _discovered_item_query_score(
                item,
                query=query,
                task_family=task_family,
            ),
            index,
            item,
        )
        for index, item in enumerate(items)
    ]
    if all(score == 0 for score, _, _ in scored_items):
        return items
    return [item for _, _, item in sorted(scored_items, key=lambda row: (-row[0], row[1]))]


def _discovered_item_query_score(
    item: DiscoveredItem,
    *,
    query: str,
    task_family: str,
) -> int:
    searchable_text = f"{item.title} {item.summary or ''} {item.url}".lower()
    query_terms = _query_terms(query)
    score = sum(5 for term in query_terms if term.lower() in searchable_text)

    if task_family == "data_metrics":
        score += _data_metrics_item_score(item.title, query=query)
    return score


def _query_terms(query: str) -> list[str]:
    return [
        term.strip()
        for term in _QUERY_TERM_PATTERN.findall(query)
        if term.strip() and len(term.strip()) >= 2
    ]


def _data_metrics_item_score(title: str, *, query: str) -> int:
    score = 0
    query_text = query.lower()

    # General annual statistical bulletins are the broadest reusable fallback
    # when a metrics query asks for energy, output, investment, trade, or fiscal
    # evidence and a list page only exposes mixed statistical bulletin types.
    if "国民经济和社会发展统计公报" in title:
        score += 30
    elif "统计公报" in title:
        score += 4

    if "人口" in title:
        score += 20 if "人口" in query_text else -10
    if "科技经费" in title:
        has_science_focus = any(term in query_text for term in ("科技", "研发", "研究", "经费"))
        score += 20 if has_science_focus else -10
    return score


def _should_hydrate_search_item_detail(request: ToolRequest) -> bool:
    task_family = str(
        request.payload.get("task_family")
        or request.query_context.metadata.get("task_family")
        or ""
    )
    return bool(request.payload.get("direct_structured_lane")) and task_family == "data_metrics"


class GenericProfileSourceAdapter(BaseSourceAdapter):
    ADAPTER_VERSION = "v1.0"

    def __init__(
        self,
        profile: SourceProfile,
        *,
        live_fetch_service: LiveHtmlFetchService | None = None,
        collector_factory: CollectorExecutorFactory | None = None,
        live_pdf_service: LivePdfDownloadService | None = None,
        pdf_text_service: PdfTextExtractionService | None = None,
    ) -> None:
        self.profile = profile
        self.live_fetch_service = live_fetch_service or LiveHtmlFetchService()
        self.collector_factory = collector_factory or CollectorExecutorFactory()
        self.live_pdf_service = live_pdf_service or LivePdfDownloadService()
        self.pdf_text_service = pdf_text_service or PdfTextExtractionService()

    def get_profile(self) -> SourceProfile:
        return self.profile

    def search_documents(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        preflight = self._validate_request(request, require_entry_url=True)
        if preflight is not None:
            return preflight

        discovered = self._discover_items(request)
        if isinstance(discovered, ToolResponse):
            return discovered

        collector, entry_url, list_fetch, discover_response = discovered
        limit, offset, page = self.resolve_limit_offset(
            request,
            default_limit=request.query_context.max_documents_per_source,
            max_limit=100,
        )
        items = _rank_discovered_items_for_query(
            discover_response.items,
            request=request,
        )
        selected_items = items[offset : offset + limit]
        raw_documents: list[RawDocument] = []
        normalized_documents: list[NormalizedDocument] = []
        errors = list(discover_response.errors)
        detail_warnings: list[str] = []

        for item in selected_items:
            normalized_response = collector.normalize_to_documents(
                CollectorRequest(
                    source_id=self.profile.source_id,
                    profile=self.profile,
                    item=item,
                    entry_url=entry_url,
                    payload=request.payload,
                    trace_id=request.trace_id,
                )
            )
            if _should_hydrate_search_item_detail(request) and normalized_response.raw_documents:
                detail_response = self.fetch_document_detail(
                    request.model_copy(
                        update={
                            "tool_name": "fetch_document_detail",
                            "document_id": normalized_response.raw_documents[0].document_id,
                        }
                    )
                )
                errors.extend(detail_response.errors)
                if detail_response.trace is not None:
                    detail_warnings.extend(detail_response.trace.warnings)
                if detail_response.documents or detail_response.normalized_documents:
                    raw_documents.extend(detail_response.documents)
                    normalized_documents.extend(detail_response.normalized_documents)
                    continue
            raw_documents.extend(normalized_response.raw_documents)
            normalized_documents.extend(normalized_response.normalized_documents)
            errors.extend(normalized_response.errors)

        warnings = [*list_fetch.warnings]
        warnings.extend(detail_warnings)
        if discover_response.trace is not None:
            warnings.extend(discover_response.trace.warnings)
        total_items = len(items)
        truncated = total_items > (offset + len(selected_items))
        if not items and not errors:
            warnings.append("No list items discovered from fetched list page.")
        status = ToolStatus.SUCCESS if raw_documents else ToolStatus.PARTIAL
        if errors and not raw_documents:
            status = ToolStatus.ERROR
        return ToolResponse(
            status=status,
            tool_name=request.tool_name,
            source_id=self.profile.source_id,
            documents=raw_documents,
            normalized_documents=normalized_documents,
            errors=errors,
            message=f"Discovered {len(raw_documents)} profile-driven document(s).",
            trace=self.build_trace(
                request=request,
                status=status,
                duration_ms=(perf_counter() - started) * 1000.0,
                http_calls=1,
                page_count=max(((total_items - 1) // max(limit, 1)) + 1, 1) if total_items else 0,
                item_count=len(raw_documents),
                retry_count=list_fetch.retry_count,
                truncated=truncated,
                warnings=warnings,
                metadata={
                    "entry_url": entry_url,
                    "collector_type": self.profile.collector_type.value
                    if self.profile.collector_type is not None
                    else None,
                    "list_fetch": list_fetch.to_dict(),
                    "total_items_discovered": total_items,
                    "page": page,
                    "offset": offset,
                },
            ),
        )

    def fetch_document_detail(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        preflight = self._validate_request(
            request,
            require_entry_url=True,
            require_document_id=True,
        )
        if preflight is not None:
            return preflight

        discovered = self._discover_items(request.model_copy(update={"document_id": None}))
        if isinstance(discovered, ToolResponse):
            return discovered
        collector, entry_url, list_fetch, discover_response = discovered

        target_item = self._resolve_item_by_document_id(
            collector,
            entry_url,
            discover_response.items,
        )
        if request.document_id is None or target_item.get(request.document_id) is None:
            return ToolResponse(
                status=ToolStatus.ERROR,
                tool_name=request.tool_name,
                source_id=self.profile.source_id,
                message="Document not found in profile-driven list page.",
                errors=[
                    ToolError(
                        code=ToolErrorCode.INVALID_REQUEST,
                        message="Document not found in profile-driven list page.",
                        retryable=False,
                    )
                ],
                trace=self.build_trace(
                    request=request,
                    status=ToolStatus.ERROR,
                    duration_ms=(perf_counter() - started) * 1000.0,
                    http_calls=1,
                    retry_count=list_fetch.retry_count,
                    warnings=["document_not_found_in_discovery"],
                    metadata={"entry_url": entry_url, "list_fetch": list_fetch.to_dict()},
                ),
            )
        item = target_item[request.document_id]

        detail_fetch = self._fetch_detail_html(request, detail_url=item.url)
        if isinstance(detail_fetch, ToolResponse):
            return detail_fetch

        detail_response = collector.fetch_detail(
            CollectorRequest(
                source_id=self.profile.source_id,
                profile=self.profile,
                item=item,
                entry_url=entry_url,
                detail_url=item.url,
                raw_html=detail_fetch.text,
                payload=request.payload,
                trace_id=request.trace_id,
            )
        )
        detail_page = detail_response.detail_pages[0] if detail_response.detail_pages else None
        if detail_page is None:
            warnings = [*list_fetch.warnings, *detail_fetch.warnings]
            if detail_response.trace is not None:
                warnings.extend(detail_response.trace.warnings)
            warnings.append("Detail page parser returned no detail pages.")
            return ToolResponse(
                status=ToolStatus.PARTIAL,
                tool_name=request.tool_name,
                source_id=self.profile.source_id,
                errors=detail_response.errors,
                message="Detail page unavailable.",
                trace=self.build_trace(
                    request=request,
                    status=ToolStatus.PARTIAL,
                    duration_ms=(perf_counter() - started) * 1000.0,
                    http_calls=2,
                    retry_count=list_fetch.retry_count + detail_fetch.retry_count,
                    warnings=warnings,
                    metadata={
                        "entry_url": entry_url,
                        "detail_url": item.url,
                        "list_fetch": list_fetch.to_dict(),
                        "detail_fetch": detail_fetch.to_dict(),
                    },
                ),
            )

        attachment_response = collector.discover_attachments(
            CollectorRequest(
                source_id=self.profile.source_id,
                profile=self.profile,
                item=item,
                entry_url=entry_url,
                detail_url=item.url,
                detail_page=detail_page,
                trace_id=request.trace_id,
            )
        )
        normalize_response = collector.normalize_to_documents(
            CollectorRequest(
                source_id=self.profile.source_id,
                profile=self.profile,
                detail_page=detail_page,
                entry_url=entry_url,
                detail_url=item.url,
                pdf_artifacts=attachment_response.pdf_artifacts,
                trace_id=request.trace_id,
            )
        )
        (
            pdf_raw_documents,
            pdf_normalized_documents,
            pdf_errors,
            pdf_warnings,
            pdf_metrics,
        ) = self._process_pdf_attachments(
            request=request,
            detail_page=detail_page,
            artifacts=attachment_response.pdf_artifacts,
        )
        all_raw_documents = [
            *normalize_response.raw_documents,
            *pdf_raw_documents,
        ]
        all_normalized_documents = [
            *normalize_response.normalized_documents,
            *pdf_normalized_documents,
        ]
        errors = [
            *detail_response.errors,
            *attachment_response.errors,
            *normalize_response.errors,
            *pdf_errors,
        ]
        warnings = [*list_fetch.warnings, *detail_fetch.warnings]
        if attachment_response.trace is not None:
            warnings.extend(attachment_response.trace.warnings)
        warnings.extend(pdf_warnings)
        status = (
            ToolStatus.SUCCESS
            if all_normalized_documents
            else ToolStatus.PARTIAL
        )
        if errors and not all_normalized_documents:
            status = ToolStatus.ERROR
        return ToolResponse(
            status=status,
            tool_name=request.tool_name,
            source_id=self.profile.source_id,
            documents=all_raw_documents,
            normalized_documents=all_normalized_documents,
            errors=errors,
            message=(
                "Fetched profile-driven detail document."
                if all_normalized_documents
                else "Detail page unavailable or could not be normalized."
            ),
            trace=self.build_trace(
                request=request,
                status=status,
                duration_ms=(perf_counter() - started) * 1000.0,
                http_calls=2,
                item_count=len(all_raw_documents),
                retry_count=(
                    list_fetch.retry_count
                    + detail_fetch.retry_count
                    + pdf_metrics["retry_count"]
                ),
                truncated=pdf_metrics["truncated"],
                warnings=warnings,
                metadata={
                    "entry_url": entry_url,
                    "detail_url": item.url,
                    "attachment_count": len(attachment_response.pdf_artifacts),
                    "pdf_processing": {
                        "enabled": pdf_metrics["enabled"],
                        "processed_attachments": pdf_metrics["processed_attachments"],
                        "pdf_documents": len(pdf_raw_documents),
                        "pages_extracted": pdf_metrics["pages_extracted"],
                        "truncated": pdf_metrics["truncated"],
                    },
                    "list_fetch": list_fetch.to_dict(),
                    "detail_fetch": detail_fetch.to_dict(),
                },
            ),
        )

    def extract_evidence_items(self, request: ToolRequest) -> ToolResponse:
        started = perf_counter()
        evidence_limit = self.resolve_evidence_limit(
            request,
            default_limit=request.query_context.max_evidence_per_source,
            max_limit=100,
        )
        detail_requests: list[ToolRequest] = []
        errors: list[ToolError] = []
        warnings: list[str] = []
        http_calls = 0
        retry_count = 0
        if request.document_id is not None:
            detail_requests.append(
                request.model_copy(update={"tool_name": "fetch_document_detail"})
            )
        else:
            search_response = self.search_documents(
                request.model_copy(update={"tool_name": "search_source_documents"})
            )
            errors.extend(search_response.errors)
            if search_response.trace is not None:
                warnings.extend(search_response.trace.warnings)
                http_calls += search_response.trace.http_calls
                retry_count += search_response.trace.retry_count
            detail_requests.extend(
                request.model_copy(
                    update={
                        "tool_name": "fetch_document_detail",
                        "document_id": raw_document.document_id,
                    }
                )
                for raw_document in search_response.documents[:evidence_limit]
            )

        documents: list[RawDocument] = []
        normalized_documents: list[NormalizedDocument] = []
        evidence_items: list[EvidenceItem] = []

        for detail_request in detail_requests:
            detail_response = self.fetch_document_detail(detail_request)
            documents.extend(detail_response.documents)
            normalized_documents.extend(detail_response.normalized_documents)
            errors.extend(detail_response.errors)
            if detail_response.trace is not None:
                warnings.extend(detail_response.trace.warnings)
                http_calls += detail_response.trace.http_calls
                retry_count += detail_response.trace.retry_count
            evidence_items.extend(self._build_evidence_items(detail_response.normalized_documents))

        total_evidence = len(evidence_items)
        evidence_items = evidence_items[:evidence_limit]
        truncated = total_evidence > len(evidence_items)
        status = ToolStatus.SUCCESS if evidence_items else ToolStatus.PARTIAL
        if errors and not evidence_items:
            status = ToolStatus.ERROR
        return ToolResponse(
            status=status,
            tool_name=request.tool_name,
            source_id=self.profile.source_id,
            documents=documents,
            normalized_documents=normalized_documents,
            evidence_items=evidence_items,
            errors=errors,
            message=(
                f"Extracted {len(evidence_items)} evidence item(s) from profile-driven source."
                if evidence_items
                else "No evidence items extracted from profile-driven source."
            ),
            trace=self.build_trace(
                request=request,
                status=status,
                duration_ms=(perf_counter() - started) * 1000.0,
                http_calls=http_calls,
                item_count=len(documents),
                evidence_count=len(evidence_items),
                retry_count=retry_count,
                truncated=truncated,
                warnings=warnings,
                metadata={"total_evidence_before_limit": total_evidence},
            ),
        )

    def _process_pdf_attachments(
        self,
        *,
        request: ToolRequest,
        detail_page,
        artifacts: list[PdfArtifact],
    ) -> tuple[
        list[RawDocument],
        list[NormalizedDocument],
        list[ToolError],
        list[str],
        dict[str, int | bool],
    ]:
        enabled = bool(request.payload.get("enable_pdf_processing", False))
        max_attachments = self._coerce_positive_int(
            request.payload.get("max_pdf_attachments_per_source")
            if request.payload.get("max_pdf_attachments_per_source") is not None
            else request.payload.get("max_pdf_attachments_per_document"),
            default=2,
            max_value=8,
        )
        max_pages = self._coerce_positive_int(
            request.payload.get("max_pdf_pages_per_attachment"),
            default=20,
            max_value=200,
        )
        if not enabled:
            return [], [], [], [], {
                "enabled": False,
                "processed_attachments": 0,
                "pages_extracted": 0,
                "retry_count": 0,
                "truncated": False,
            }

        raw_documents: list[RawDocument] = []
        normalized_documents: list[NormalizedDocument] = []
        errors: list[ToolError] = []
        warnings: list[str] = []
        total_pages_extracted = 0
        total_retry_count = 0
        truncated = len(artifacts) > max_attachments
        selected_artifacts = artifacts[:max_attachments]
        publisher = str(self.profile.collector_config.get("publisher") or "").strip() or None

        for artifact in selected_artifacts:
            attachment_ref = artifact.attachment_ref or artifact.filename or artifact.artifact_id
            try:
                download = self.live_pdf_service.download_pdf(
                    artifact.url,
                    source_id=self.profile.source_id,
                    attachment_ref=attachment_ref,
                )
                total_retry_count += download.retry_count
                downloaded_artifact = artifact.model_copy(
                    update={
                        "checksum_sha256": download.sha256,
                        "metadata": {
                            **artifact.metadata,
                            "download_result": download.to_dict(),
                            "local_file_path": download.file_path,
                        },
                    }
                )
                pdf_document = self.pdf_text_service.extract_from_file(
                    file_path=download.file_path,
                    source_id=self.profile.source_id,
                    artifact=downloaded_artifact,
                    title=downloaded_artifact.title,
                    max_pages=max_pages,
                    metadata={
                        "attachment_ref": attachment_ref,
                        "attachment_url": downloaded_artifact.url,
                        "detail_url": detail_page.url,
                    },
                )
                total_pages_extracted += len(pdf_document.pages)
                raw_document, normalized_document = normalize_pdf_text_to_documents(
                    pdf_document,
                    title=downloaded_artifact.title,
                    published_at=detail_page.published_at,
                    publisher=publisher,
                )
                normalized_document.metadata = {
                    **normalized_document.metadata,
                    "detail_url": detail_page.url,
                    "attachment_ref": attachment_ref,
                    "attachment_url": downloaded_artifact.url,
                    "from_pdf_attachment": True,
                }
                raw_document.metadata = {
                    **raw_document.metadata,
                    "detail_url": detail_page.url,
                    "from_pdf_attachment": True,
                }
                raw_documents.append(raw_document)
                normalized_documents.append(normalized_document)
                if download.warnings:
                    warnings.extend(
                        [f"pdf_download:{warning}" for warning in download.warnings]
                    )
            except LivePdfDownloadError as exc:
                errors.append(
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=f"PDF download failed for '{artifact.url}': {exc}",
                        retryable=exc.retryable,
                        detail=exc.to_dict(),
                    )
                )
            except PdfTextExtractionError as exc:
                errors.append(
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=f"PDF text extraction failed for '{artifact.url}': {exc}",
                        retryable=False,
                        detail=exc.to_dict(),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message=f"Unexpected PDF processing failure for '{artifact.url}': {exc}",
                        retryable=False,
                        detail={
                            "attachment_url": artifact.url,
                            "attachment_ref": attachment_ref,
                        },
                    )
                )

        if not selected_artifacts and artifacts:
            warnings.append("No PDF attachments selected after max attachment cap.")
        if enabled and not artifacts:
            warnings.append("PDF processing enabled but no attachments were discovered.")
        return raw_documents, normalized_documents, errors, warnings, {
            "enabled": enabled,
            "processed_attachments": len(selected_artifacts),
            "pages_extracted": total_pages_extracted,
            "retry_count": total_retry_count,
            "truncated": truncated,
        }

    def _coerce_positive_int(
        self,
        value: object,
        *,
        default: int,
        max_value: int,
    ) -> int:
        try:
            parsed = int(value) if value is not None else default
        except (TypeError, ValueError):
            parsed = default
        return max(1, min(parsed, max_value))

    def _build_evidence_items(
        self,
        normalized_documents: list[NormalizedDocument],
    ) -> list[EvidenceItem]:
        profile = self.get_profile()
        evidence_items: list[EvidenceItem] = []
        for document in normalized_documents:
            sections = list(document.sections)
            if not sections and document.summary:
                sections = [
                    DocumentSection(
                        section_id="section_0",
                        heading=document.title,
                        text=document.summary,
                    )
                ]
            document_meta = document.metadata if isinstance(document.metadata, dict) else {}
            for index, section in enumerate(sections):
                text = section.text.strip()
                if not text:
                    continue
                section_meta = section.metadata if isinstance(section.metadata, dict) else {}
                page_number = section_meta.get("page_number")
                if not isinstance(page_number, int):
                    page_number = None
                attachment_ref = document_meta.get("attachment_ref")
                attachment_url = document_meta.get("attachment_url") or document_meta.get("pdf_url")
                source_uri = attachment_url or document_meta.get("detail_url")
                locator_section_id = None if page_number is not None else section.section_id
                citation = Citation(
                    citation_id=f"cit_{document.document_id}_{index}",
                    source_id=profile.source_id,
                    document_id=document.document_id,
                    locator=CitationLocator(
                        document_id=document.document_id,
                        section_id=locator_section_id,
                        page_number=page_number,
                        external_ref=attachment_ref or source_uri,
                    ),
                    quote_text=text[:240],
                    source_uri=source_uri,
                    published_at=document.published_at,
                    metadata={
                        "locator_type": "page" if page_number is not None else "section",
                        "attachment_ref": attachment_ref,
                        "attachment_url": attachment_url,
                    },
                )
                evidence_items.append(
                    normalize_evidence_item(
                        EvidenceItem(
                            evidence_id=f"evi_{document.document_id}_{index}",
                            source_id=profile.source_id,
                            title=document.title,
                            summary=text[:180],
                            support_text=text[:400],
                            score=0.72 if index == 0 else 0.66,
                            citation=citation,
                            metadata={
                                "section_name": section.heading or section.section_id,
                                "profile_family": profile.profile_family,
                                "collector_type": profile.collector_type.value
                                if profile.collector_type is not None
                                else None,
                                "page_number": page_number,
                                "attachment_ref": attachment_ref,
                                "from_pdf_attachment": bool(
                                    document_meta.get("from_pdf_attachment")
                                ),
                            },
                        ),
                        source_name=profile.display_name,
                        external_id=document.document_id,
                    )
                )
        return evidence_items

    def _validate_request(
        self,
        request: ToolRequest,
        *,
        require_entry_url: bool = False,
        require_document_id: bool = False,
    ) -> ToolResponse | None:
        if not self.profile.enabled:
            return self.error_response(
                request,
                code=ToolErrorCode.SOURCE_DISABLED,
                message=f"Source '{self.profile.source_id}' is disabled.",
                retryable=False,
            )
        if self.profile.collector_type is None:
            return self._unsupported_response(
                request,
                message=f"Source '{self.profile.source_id}' has no collector_type configured.",
            )
        if self.profile.collector_type != CollectorType.HTML_LIST_DETAIL:
            return self._unsupported_response(
                request,
                message=(
                    f"Source '{self.profile.source_id}' collector_type="
                    f"{self.profile.collector_type.value} is not supported yet."
                ),
            )
        if require_entry_url and not self._resolve_entry_url(request):
            return self.error_response(
                request,
                code=ToolErrorCode.INVALID_REQUEST,
                message=f"Source '{self.profile.source_id}' has no entry_url configured.",
                retryable=False,
            )
        if require_document_id and not request.document_id:
            return self.error_response(
                request,
                code=ToolErrorCode.INVALID_REQUEST,
                message="document_id is required for profile-driven document detail.",
                retryable=False,
            )
        return None

    def _unsupported_response(self, request: ToolRequest, *, message: str) -> ToolResponse:
        return ToolResponse(
            status=ToolStatus.UNSUPPORTED,
            tool_name=request.tool_name,
            source_id=self.profile.source_id,
            message=message,
            errors=[
                ToolError(
                    code=ToolErrorCode.UNSUPPORTED_OPERATION,
                    message=message,
                    retryable=False,
                )
            ],
            trace=self.build_trace(
                request=request,
                status=ToolStatus.UNSUPPORTED,
                warnings=[message],
            ),
        )

    def _resolve_entry_url(self, request: ToolRequest) -> str | None:
        payload_entry_url = request.payload.get("entry_url")
        if isinstance(payload_entry_url, str) and payload_entry_url.strip():
            return payload_entry_url.strip()
        if self.profile.entry_urls:
            return self.profile.entry_urls[0]
        return None

    def _discover_items(
        self,
        request: ToolRequest,
    ) -> ToolResponse | tuple[BaseCollector, str, LiveHtmlFetchResult, object]:
        collector = self.collector_factory.get_collector(self.profile)
        if collector is None:
            return self._unsupported_response(
                request,
                message=(
                    f"{self.profile.source_id} collector_type="
                    f"{self.profile.collector_type} is not supported."
                ),
            )
        entry_url = self._resolve_entry_url(request)
        if not entry_url:
            return self.error_response(
                request,
                code=ToolErrorCode.INVALID_REQUEST,
                message=f"Source '{self.profile.source_id}' has no entry_url configured.",
                retryable=False,
            )
        list_fetch = self._fetch_list_html(request, entry_url=entry_url)
        if isinstance(list_fetch, ToolResponse):
            return list_fetch
        discover_response = collector.discover_items(
            CollectorRequest(
                source_id=self.profile.source_id,
                profile=self.profile,
                entry_url=entry_url,
                raw_html=list_fetch.text,
                payload=request.payload,
                trace_id=request.trace_id,
            )
        )
        return collector, entry_url, list_fetch, discover_response

    def _fetch_list_html(
        self,
        request: ToolRequest,
        *,
        entry_url: str,
    ) -> ToolResponse | LiveHtmlFetchResult:
        inline_html = request.payload.get("html") or request.payload.get("list_html")
        if isinstance(inline_html, str) and inline_html.strip():
            return build_inline_fetch_result(
                url=entry_url,
                text=inline_html,
                warning="used_inline_html",
            )
        try:
            return self.live_fetch_service.fetch_html(
                entry_url,
                encoding_hints=self.profile.encoding_hints,
            )
        except LiveHtmlFetchError as exc:
            return self.error_response(
                request,
                code=ToolErrorCode.INTERNAL_ERROR,
                message=f"Failed to fetch list page for '{self.profile.source_id}': {exc}",
                retryable=exc.retryable,
                detail={"fetch": exc.to_dict(), "entry_url": entry_url},
            )

    def _fetch_detail_html(
        self,
        request: ToolRequest,
        *,
        detail_url: str,
    ) -> ToolResponse | LiveHtmlFetchResult:
        detail_html_map = (
            request.payload.get("detail_html_by_url")
            or request.payload.get("detail_html_map")
        )
        if isinstance(detail_html_map, dict):
            mapped_html = detail_html_map.get(detail_url)
            if isinstance(mapped_html, str) and mapped_html.strip():
                return build_inline_fetch_result(
                    url=detail_url,
                    text=mapped_html,
                    warning="used_inline_detail_html_map",
                )
        detail_html = request.payload.get("detail_html")
        if isinstance(detail_html, str) and detail_html.strip():
            return build_inline_fetch_result(
                url=detail_url,
                text=detail_html,
                warning="used_inline_detail_html",
            )
        try:
            return self.live_fetch_service.fetch_html(
                detail_url,
                encoding_hints=self.profile.encoding_hints,
            )
        except LiveHtmlFetchError as exc:
            return self.error_response(
                request,
                code=ToolErrorCode.INTERNAL_ERROR,
                message=f"Failed to fetch detail page for '{self.profile.source_id}': {exc}",
                retryable=exc.retryable,
                detail={"fetch": exc.to_dict(), "detail_url": detail_url},
            )

    def _resolve_item_by_document_id(
        self,
        collector: BaseCollector,
        entry_url: str,
        items: list[DiscoveredItem],
    ) -> dict[str, DiscoveredItem]:
        mapping: dict[str, DiscoveredItem] = {}
        for item in items:
            normalized_response = collector.normalize_to_documents(
                CollectorRequest(
                    source_id=self.profile.source_id,
                    profile=self.profile,
                    item=item,
                    entry_url=entry_url,
                )
            )
            for raw_document in normalized_response.raw_documents:
                mapping[raw_document.document_id] = item
        return mapping
