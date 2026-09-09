from __future__ import annotations

from time import perf_counter

from packages.sources.collectors.base import (
    BaseCollector,
    CollectorRequest,
    CollectorResponse,
    PdfTextDocument,
    PdfTextPage,
)
from packages.sources.collectors.normalize import normalize_pdf_text_document
from packages.sources.enums import CollectorType, ToolStatus


class PdfTextExtractCollector(BaseCollector):
    # TODO: Add OCR-backed fallback for scanned PDFs in a later step.
    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.PDF_TEXT_EXTRACT

    def discover_items(self, request: CollectorRequest) -> CollectorResponse:
        return self.not_implemented(
            request,
            operation="discover_items",
            note="PDF text extraction starts from existing PDF artifact references.",
        )

    def fetch_detail(self, request: CollectorRequest) -> CollectorResponse:
        return self.not_implemented(
            request,
            operation="fetch_detail",
            note="PDF text extraction does not fetch HTML detail pages.",
        )

    def discover_attachments(self, request: CollectorRequest) -> CollectorResponse:
        return self.not_implemented(
            request,
            operation="discover_attachments",
            note="Provide PDF artifacts from an upstream collector stage.",
        )

    def extract_text(self, request: CollectorRequest) -> CollectorResponse:
        started = perf_counter()
        if request.pdf_text_document is not None:
            document = request.pdf_text_document
        else:
            page_payloads = request.payload.get("page_texts")
            pages = []
            if isinstance(page_payloads, list) and page_payloads:
                for index, payload in enumerate(page_payloads, start=1):
                    if isinstance(payload, dict):
                        pages.append(
                            PdfTextPage(
                                page_number=int(payload.get("page_number", index)),
                                text=str(payload.get("text") or ""),
                                metadata=payload.get("metadata") or {},
                            )
                        )
                    else:
                        pages.append(PdfTextPage(page_number=index, text=str(payload)))
            elif request.raw_text:
                pages = [PdfTextPage(page_number=1, text=request.raw_text)]
            else:
                return self.not_implemented(
                    request,
                    operation="extract_text",
                    note=(
                        "Provide page_texts or raw_text; real PDF binary extraction "
                        "is deferred to Step 4.2."
                    ),
                )

            artifact = request.pdf_artifacts[0] if request.pdf_artifacts else None
            document = PdfTextDocument(
                artifact_id=artifact.artifact_id if artifact is not None else "pdf_text_0",
                source_id=request.source_id,
                title=artifact.title if artifact is not None else None,
                url=artifact.url if artifact is not None else None,
                pages=pages,
            )

        return CollectorResponse(
            status=ToolStatus.SUCCESS,
            collector_name=self.collector_name,
            source_id=request.source_id,
            pdf_artifacts=request.pdf_artifacts,
            pdf_text_documents=[document],
            message="Constructed PDF text extraction contract output.",
            trace=self.build_trace(
                request=request,
                operation="extract_text",
                status=ToolStatus.SUCCESS,
                duration_ms=(perf_counter() - started) * 1000.0,
                page_count=len(document.pages),
                item_count=1,
            ),
        )

    def normalize_to_documents(self, request: CollectorRequest) -> CollectorResponse:
        started = perf_counter()
        extracted = self.extract_text(request)
        if extracted.status != ToolStatus.SUCCESS or not extracted.pdf_text_documents:
            return extracted
        normalized = normalize_pdf_text_document(extracted.pdf_text_documents[0])
        return CollectorResponse(
            status=ToolStatus.SUCCESS,
            collector_name=self.collector_name,
            source_id=request.source_id,
            pdf_artifacts=extracted.pdf_artifacts,
            pdf_text_documents=extracted.pdf_text_documents,
            normalized_documents=[normalized],
            message="Normalized PDF text extraction output.",
            trace=self.build_trace(
                request=request,
                operation="normalize_to_documents",
                status=ToolStatus.SUCCESS,
                duration_ms=(perf_counter() - started) * 1000.0,
                item_count=1,
            ),
        )
