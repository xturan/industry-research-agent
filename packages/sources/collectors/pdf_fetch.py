from __future__ import annotations

from time import perf_counter
from urllib.parse import urlparse

from packages.sources.collectors.base import (
    BaseCollector,
    CollectorRequest,
    CollectorResponse,
    PdfArtifact,
)
from packages.sources.collectors.normalize import normalize_pdf_text_document
from packages.sources.enums import CollectorType, ToolStatus


class PdfFetchCollector(BaseCollector):
    # TODO: Add authenticated PDF download flow in a later step.
    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.PDF_FETCH

    def discover_items(self, request: CollectorRequest) -> CollectorResponse:
        return self.not_implemented(
            request,
            operation="discover_items",
            note="PDF fetch collector expects attachment URLs, not list-page discovery.",
        )

    def fetch_detail(self, request: CollectorRequest) -> CollectorResponse:
        return self.not_implemented(
            request,
            operation="fetch_detail",
            note="PDF fetch collector does not parse HTML detail pages.",
        )

    def discover_attachments(self, request: CollectorRequest) -> CollectorResponse:
        started = perf_counter()
        if request.pdf_artifacts:
            artifacts = []
            for artifact in request.pdf_artifacts:
                attachment_ref = artifact.attachment_ref or artifact.filename
                if not attachment_ref:
                    parsed = urlparse(artifact.url)
                    attachment_ref = parsed.path.split("/")[-1] or artifact.artifact_id
                artifacts.append(
                    artifact.model_copy(
                        update={
                            "attachment_ref": attachment_ref,
                        }
                    )
                )
        else:
            candidate_urls: list[str] = []
            payload_urls = request.payload.get("attachment_urls")
            if isinstance(payload_urls, list):
                candidate_urls.extend(str(url) for url in payload_urls if str(url).strip())
            if request.item is not None and request.item.url.lower().endswith(".pdf"):
                candidate_urls.append(request.item.url)

            artifacts = []
            for index, url in enumerate(candidate_urls):
                parsed = urlparse(url)
                filename = parsed.path.split("/")[-1] or f"attachment_{index}.pdf"
                artifacts.append(
                    PdfArtifact(
                        artifact_id=f"pdf_{index}",
                        source_id=request.source_id,
                        item_id=request.item.item_id if request.item is not None else None,
                        url=url,
                        title=filename,
                        filename=filename,
                        attachment_ref=filename,
                    )
                )

        status = ToolStatus.SUCCESS if artifacts else ToolStatus.PARTIAL
        warnings = [] if artifacts else ["No PDF artifact references were provided."]
        return CollectorResponse(
            status=status,
            collector_name=self.collector_name,
            source_id=request.source_id,
            pdf_artifacts=artifacts,
            message=f"Prepared {len(artifacts)} PDF artifact contract(s).",
            trace=self.build_trace(
                request=request,
                operation="discover_attachments",
                status=status,
                duration_ms=(perf_counter() - started) * 1000.0,
                item_count=len(artifacts),
                warnings=warnings,
            ),
        )

    def normalize_to_documents(self, request: CollectorRequest) -> CollectorResponse:
        started = perf_counter()
        if request.pdf_text_document is None:
            return self.not_implemented(
                request,
                operation="normalize_to_documents",
                note="Provide pdf_text_document; binary PDF fetching/parsing is deferred.",
            )

        normalized = normalize_pdf_text_document(request.pdf_text_document)
        return CollectorResponse(
            status=ToolStatus.SUCCESS,
            collector_name=self.collector_name,
            source_id=request.source_id,
            pdf_text_documents=[request.pdf_text_document],
            normalized_documents=[normalized],
            message="Normalized PDF text contract into document shape.",
            trace=self.build_trace(
                request=request,
                operation="normalize_to_documents",
                status=ToolStatus.SUCCESS,
                duration_ms=(perf_counter() - started) * 1000.0,
                item_count=1,
            ),
        )
