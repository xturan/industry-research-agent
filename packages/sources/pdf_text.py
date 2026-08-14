from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.sources.collectors.base import PdfArtifact, PdfTextDocument, PdfTextPage

try:
    from pypdf import PdfReader
    from pypdf import __version__ as pypdf_version
    from pypdf.errors import PdfReadError
except ImportError:  # pragma: no cover - dependency is optional at runtime
    PdfReader = None
    PdfReadError = Exception
    pypdf_version = "unavailable"


@dataclass(slots=True)
class PdfTextExtractionStats:
    total_pages: int
    pages_with_text: int
    extracted_chars: int
    truncated: bool


class PdfTextExtractionError(Exception):
    def __init__(
        self,
        message: str,
        *,
        file_path: str,
        error_code: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.file_path = file_path
        self.error_code = error_code
        self.detail = detail or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "error_code": self.error_code,
            "detail": self.detail,
        }


class PdfTextExtractionService:
    EXTRACTOR_VERSION = "pypdf_v1"

    def extract_from_file(
        self,
        *,
        file_path: str,
        source_id: str,
        artifact: PdfArtifact | None = None,
        title: str | None = None,
        max_pages: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PdfTextDocument:
        path = Path(file_path)
        if not path.exists():
            raise PdfTextExtractionError(
                "PDF file does not exist.",
                file_path=str(path),
                error_code="pdf_not_found",
            )
        if PdfReader is None:
            raise PdfTextExtractionError(
                "pypdf is required for PDF text extraction.",
                file_path=str(path),
                error_code="dependency_missing",
                detail={"dependency": "pypdf"},
            )

        try:
            reader = PdfReader(str(path))
        except PdfReadError as exc:  # pragma: no cover - depends on binary parsing internals
            raise PdfTextExtractionError(
                f"Invalid or unreadable PDF: {exc}",
                file_path=str(path),
                error_code="invalid_pdf",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise PdfTextExtractionError(
                f"Unexpected PDF parse failure: {exc}",
                file_path=str(path),
                error_code="pdf_parse_error",
            ) from exc

        total_pages = len(reader.pages)
        if total_pages == 0:
            raise PdfTextExtractionError(
                "PDF has no pages.",
                file_path=str(path),
                error_code="pdf_empty",
            )

        capped_pages = total_pages
        if max_pages is not None:
            capped_pages = max(min(int(max_pages), total_pages), 1)

        pages: list[PdfTextPage] = []
        for index in range(capped_pages):
            page_number = index + 1
            page_obj = reader.pages[index]
            text = ""
            try:
                extracted = page_obj.extract_text() or ""
                text = extracted.strip()
            except Exception:  # noqa: BLE001
                text = ""
            page_metadata: dict[str, Any] = {"page_number": page_number}
            if not text:
                page_metadata["empty_text"] = True
            pages.append(
                PdfTextPage(
                    page_number=page_number,
                    text=text,
                    metadata=page_metadata,
                )
            )

        pages_with_text = sum(1 for page in pages if page.text)
        extracted_chars = sum(page.char_count for page in pages)
        stats = PdfTextExtractionStats(
            total_pages=total_pages,
            pages_with_text=pages_with_text,
            extracted_chars=extracted_chars,
            truncated=total_pages > capped_pages,
        )
        if stats.pages_with_text == 0:
            raise PdfTextExtractionError(
                "PDF extraction produced zero text across all pages.",
                file_path=str(path),
                error_code="zero_text",
                detail={
                    "total_pages": stats.total_pages,
                    "processed_pages": capped_pages,
                },
            )

        effective_artifact_id = (
            artifact.artifact_id
            if artifact is not None
            else f"pdf_{source_id}_{path.stem}"
        )
        base_metadata = dict(metadata or {})
        if artifact is not None:
            base_metadata.setdefault("attachment_ref", artifact.attachment_ref)
            base_metadata.setdefault("attachment_url", artifact.url)
            base_metadata.setdefault("checksum_sha256", artifact.checksum_sha256)
        base_metadata.update(
            {
                "extractor": "pypdf",
                "extractor_version": self.EXTRACTOR_VERSION,
                "extractor_lib_version": pypdf_version,
                "file_path": str(path),
                "page_count_total": stats.total_pages,
                "page_count_extracted": len(pages),
                "pages_with_text": stats.pages_with_text,
                "extracted_chars": stats.extracted_chars,
                "truncated_pages": stats.truncated,
            }
        )

        return PdfTextDocument(
            artifact_id=effective_artifact_id,
            source_id=source_id,
            title=title or (artifact.title if artifact is not None else path.name),
            url=artifact.url if artifact is not None else None,
            pages=pages,
            metadata=base_metadata,
        )
