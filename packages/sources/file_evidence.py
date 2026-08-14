from __future__ import annotations

from enum import Enum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 fallback

    class StrEnum(str, Enum):  # noqa: UP042
        pass


class FileEvidenceKind(StrEnum):
    PDF = "pdf"
    XLS = "xls"
    XLSX = "xlsx"
    DOC = "doc"
    DOCX = "docx"
    CSV = "csv"
    ZIP = "zip"
    DOWNLOAD_ENDPOINT = "download_endpoint"


class FileEvidenceCandidate(BaseModel):
    """Internal contract for file-backed source evidence candidates."""

    model_config = ConfigDict(extra="forbid")

    requested_url: str = Field(min_length=1, max_length=2048)
    final_url: str = Field(min_length=1, max_length=2048)
    source_id: str = Field(min_length=1, max_length=120)
    task_family: str = Field(min_length=1, max_length=80)
    source_class: str = Field(min_length=1, max_length=120)
    file_candidate_kind: FileEvidenceKind
    title: str | None = Field(default=None, max_length=500)
    content_type: str | None = Field(default=None, max_length=200)
    content_length: int | None = Field(default=None, ge=0)
    download_status: str = Field(min_length=1, max_length=80)
    extractor: str | None = Field(default=None, max_length=120)
    text_chars: int = Field(default=0, ge=0)
    extraction_failure_class: str | None = Field(default=None, max_length=120)
    extraction_failure_stage: str | None = Field(default=None, max_length=120)
    claim_eligible: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("requested_url", "final_url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        normalized = value.strip()
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("file evidence URL must be absolute http(s)")
        return normalized

    def to_metadata(self) -> dict[str, Any]:
        return {
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "citation_url": self.requested_url,
            "source_id": self.source_id,
            "task_family": self.task_family,
            "source_class": self.source_class,
            "file_candidate_kind": self.file_candidate_kind.value,
            "title": self.title,
            "content_type": self.content_type,
            "content_length": self.content_length,
            "download_status": self.download_status,
            "extractor": self.extractor,
            "text_chars": self.text_chars,
            "extraction_failure_class": self.extraction_failure_class,
            "extraction_failure_stage": self.extraction_failure_stage,
            "claim_eligible": self.claim_eligible,
            **self.metadata,
        }


class UnsupportedFileEvidenceError(Exception):
    def __init__(self, candidate: FileEvidenceCandidate) -> None:
        super().__init__(
            f"Unsupported file evidence kind: {candidate.file_candidate_kind.value}"
        )
        self.candidate = candidate

    def to_detail(self) -> dict[str, Any]:
        return self.candidate.to_metadata()


def file_candidate_kind_from_url(url: str) -> FileEvidenceKind | None:
    parsed = urlparse(url)
    path = parsed.path.lower()
    query = parsed.query.lower()
    file_extensions = {
        ".pdf": FileEvidenceKind.PDF,
        ".xls": FileEvidenceKind.XLS,
        ".xlsx": FileEvidenceKind.XLSX,
        ".doc": FileEvidenceKind.DOC,
        ".docx": FileEvidenceKind.DOCX,
        ".csv": FileEvidenceKind.CSV,
        ".zip": FileEvidenceKind.ZIP,
    }
    for extension, kind in file_extensions.items():
        if path.endswith(extension):
            return kind

    download_markers = (
        "download",
        "downloadfile",
        "filedownload",
        "attach",
        "attachment",
        "fileid=",
        "filename=",
    )
    path_query = f"{path}?{query}"
    if any(marker in path_query for marker in download_markers):
        return FileEvidenceKind.DOWNLOAD_ENDPOINT
    return None


def build_file_evidence_candidate(
    *,
    url: str,
    source_id: str,
    task_family: str,
    source_class: str,
    title: str | None = None,
    content_type: str | None = None,
    content_length: int | None = None,
    final_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> FileEvidenceCandidate:
    kind = file_candidate_kind_from_url(url)
    if kind is None:
        raise ValueError("url is not a recognized file evidence candidate")

    if kind == FileEvidenceKind.PDF:
        return FileEvidenceCandidate(
            requested_url=url,
            final_url=final_url or url,
            source_id=source_id,
            task_family=task_family,
            source_class=source_class,
            file_candidate_kind=kind,
            title=title,
            content_type=content_type,
            content_length=content_length,
            download_status="candidate_classified",
            extractor="static_pdf",
            claim_eligible=False,
            metadata=metadata or {},
        )

    candidate = FileEvidenceCandidate(
        requested_url=url,
        final_url=final_url or url,
        source_id=source_id,
        task_family=task_family,
        source_class=source_class,
        file_candidate_kind=kind,
        title=title,
        content_type=content_type,
        content_length=content_length,
        download_status="unsupported_file_type",
        extraction_failure_class="file_or_download",
        extraction_failure_stage="candidate_classification",
        claim_eligible=False,
        metadata=metadata or {},
    )
    raise UnsupportedFileEvidenceError(candidate)
