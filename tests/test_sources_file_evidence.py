from __future__ import annotations

from packages.sources.file_evidence import (
    FileEvidenceCandidate,
    FileEvidenceKind,
    UnsupportedFileEvidenceError,
    build_file_evidence_candidate,
    file_candidate_kind_from_url,
)


def test_file_candidate_kind_from_url_classifies_extensions_and_downloads() -> None:
    assert (
        file_candidate_kind_from_url("https://ggzy.example.gov.cn/files/project.pdf")
        == FileEvidenceKind.PDF
    )
    assert (
        file_candidate_kind_from_url("https://stats.example.gov.cn/report.xlsx")
        == FileEvidenceKind.XLSX
    )
    assert (
        file_candidate_kind_from_url("https://ggzy.gov.cn/admin/api/downloadFile.do?id=abc")
        == FileEvidenceKind.DOWNLOAD_ENDPOINT
    )
    assert file_candidate_kind_from_url("https://example.gov.cn/article/123.html") is None


def test_pdf_file_evidence_candidate_contract_preserves_citation_url() -> None:
    candidate = build_file_evidence_candidate(
        url="https://www.ggzy.gov.cn/files/hefei-project.pdf",
        source_id="search_assisted_project_fallback",
        task_family="project_transaction",
        source_class="tender_or_procurement",
        title="合肥新能源汽车零部件项目中标公告",
        content_type="application/pdf",
        content_length=1024,
    )

    assert isinstance(candidate, FileEvidenceCandidate)
    assert candidate.file_candidate_kind == FileEvidenceKind.PDF
    assert candidate.requested_url == "https://www.ggzy.gov.cn/files/hefei-project.pdf"
    assert candidate.final_url == "https://www.ggzy.gov.cn/files/hefei-project.pdf"
    assert candidate.extractor == "static_pdf"
    assert candidate.download_status == "candidate_classified"
    assert candidate.extraction_failure_class is None
    assert candidate.to_metadata()["citation_url"] == candidate.requested_url


def test_unsupported_file_evidence_is_structured_and_not_claim_eligible() -> None:
    try:
        build_file_evidence_candidate(
            url="https://www.ggzy.gov.cn/files/project-attachments.zip",
            source_id="search_assisted_project_fallback",
            task_family="project_transaction",
            source_class="tender_or_procurement",
        )
    except UnsupportedFileEvidenceError as exc:
        detail = exc.to_detail()
    else:  # pragma: no cover - test must fail if no structured refusal happens
        raise AssertionError("ZIP candidates must produce a structured unsupported failure")

    assert detail["file_candidate_kind"] == "zip"
    assert detail["download_status"] == "unsupported_file_type"
    assert detail["extraction_failure_class"] == "file_or_download"
    assert detail["extraction_failure_stage"] == "candidate_classification"
    assert detail["claim_eligible"] is False
