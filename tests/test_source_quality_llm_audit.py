from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _load_audit_module() -> Any:
    path = Path(__file__).resolve().parents[1] / "data" / "tmp" / "_source_quality_llm_audit.py"
    spec = importlib.util.spec_from_file_location("source_quality_llm_audit", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_audit_json_recovers_fenced_object() -> None:
    module = _load_audit_module()

    parsed, error = module._parse_audit_json(
        '```json\n{"query_id":"M03","verdict":"fail"}\n```'
    )

    assert error is None
    assert parsed == {"query_id": "M03", "verdict": "fail"}


def test_call_deepseek_retries_truncated_invalid_json(monkeypatch) -> None:
    module = _load_audit_module()
    calls: list[dict[str, Any]] = []

    def fake_post(payload: dict[str, Any], *, api_key: str, timeout: int) -> dict[str, Any]:
        calls.append(payload)
        if len(calls) == 1:
            return {
                "ok": True,
                "status": 200,
                "body": {
                    "model": "deepseek-v4-pro",
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {"content": '{"query_id":"M03","verdict":"fail"'},
                        }
                    ],
                    "usage": {"completion_tokens": 4096, "total_tokens": 5000},
                },
            }
        return {
            "ok": True,
            "status": 200,
            "body": {
                "model": "deepseek-v4-pro",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": '{"query_id":"M03","verdict":"fail","overall_score":20}'
                        },
                    }
                ],
                "usage": {"completion_tokens": 120, "total_tokens": 1000},
            },
        }

    monkeypatch.setattr(module, "_post_deepseek", fake_post)

    result = module._call_deepseek(
        {"case_id": "M03", "level": "macro", "case_expectations": {}},
        prompt="Return JSON.",
        api_key="test-key",
        model="deepseek-v4-pro",
        reasoning_effort="max",
        timeout=1,
        max_input_chars=24000,
    )

    assert result["status"] == "success"
    assert result["recovered_from_invalid_json"] is True
    assert result["initial_invalid_json"]["finish_reason"] == "length"
    assert result["audit"]["query_id"] == "M03"
    assert "reasoning_effort" in calls[0]
    assert "reasoning_effort" not in calls[1]
    assert calls[1]["max_tokens"] >= 8192
    assert "Use short strings" in calls[1]["messages"][1]["content"]


def test_call_deepseek_retries_invalid_schema_and_recovers(monkeypatch) -> None:
    module = _load_audit_module()
    calls: list[dict[str, Any]] = []

    def fake_post(payload: dict[str, Any], *, api_key: str, timeout: int) -> dict[str, Any]:
        calls.append(payload)
        if len(calls) == 1:
            return {
                "ok": True,
                "status": 200,
                "body": {
                    "model": "deepseek-v4-pro",
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {"content": "{}"},
                        }
                    ],
                    "usage": {"completion_tokens": 4096, "total_tokens": 6000},
                },
            }
        return {
            "ok": True,
            "status": 200,
            "body": {
                "model": "deepseek-v4-pro",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": '{"query_id":"C01","verdict":"fail","overall_score":10}'
                        },
                    }
                ],
                "usage": {"completion_tokens": 90, "total_tokens": 1200},
            },
        }

    monkeypatch.setattr(module, "_post_deepseek", fake_post)

    result = module._call_deepseek(
        {"case_id": "C01", "level": "city", "case_expectations": {}},
        prompt="Return JSON.",
        api_key="test-key",
        model="deepseek-v4-pro",
        reasoning_effort="max",
        timeout=1,
        max_input_chars=24000,
    )

    assert result["status"] == "success"
    assert result["recovered_from_invalid_schema"] is True
    assert result["initial_invalid_schema"]["finish_reason"] == "length"
    assert result["initial_invalid_schema"]["missing_fields"] == ["query_id", "verdict"]
    assert result["audit"]["query_id"] == "C01"
    assert "reasoning_effort" in calls[0]
    assert "reasoning_effort" not in calls[1]


def test_call_deepseek_returns_schema_diagnostics_after_failed_retry(monkeypatch) -> None:
    module = _load_audit_module()
    calls: list[dict[str, Any]] = []

    def fake_post(payload: dict[str, Any], *, api_key: str, timeout: int) -> dict[str, Any]:
        calls.append(payload)
        return {
            "ok": True,
            "status": 200,
            "body": {
                "model": "deepseek-v4-pro",
                "choices": [
                    {
                        "finish_reason": "length" if len(calls) == 1 else "stop",
                        "message": {"content": "{}"},
                    }
                ],
                "usage": {"completion_tokens": 4096, "total_tokens": 6000},
            },
        }

    monkeypatch.setattr(module, "_post_deepseek", fake_post)

    result = module._call_deepseek(
        {"case_id": "C01", "level": "city", "case_expectations": {}},
        prompt="Return JSON.",
        api_key="test-key",
        model="deepseek-v4-pro",
        reasoning_effort="max",
        timeout=1,
        max_input_chars=24000,
    )

    assert result["status"] == "invalid_schema"
    assert result["reason_code"] == "missing_required_fields"
    assert result["case_id"] == "C01"
    assert result["query_id"] == "C01"
    assert result["missing_fields"] == ["query_id", "verdict"]
    assert result["retry_attempted"] is True
    assert result["retry_recovered"] is False
    assert result["finish_reason"] == "length"
    assert result["raw_content_excerpt"] == "{}"


def test_compact_artifact_preserves_audit_visibility_for_quality_and_failures() -> None:
    module = _load_audit_module()
    artifact = {
        "case_id": "P08",
        "level": "province",
        "query": "test query",
        "status": "success",
        "case_expectations": {"expected_source_classes": ["environmental_or_land_record"]},
        "padding": "x" * 5000,
        "executed_tasks": [
            {
                "task": {"task_id": "official_record_1", "task_family": "official_record"},
                "status": "partial",
                "metadata": {
                    "official_record_search_fallback": {
                        "status": "evidence_found",
                        "selected_candidate_count": 2,
                        "selected_pdf_candidate_count": 1,
                        "extraction": {
                            "provider": "crawl4ai_plus_static_pdf",
                            "succeeded": 1,
                            "failed": 1,
                        },
                        "pdf_extraction": {
                            "provider": "static_pdf",
                            "failure_classes": {"pdf_download_failed": 1},
                        },
                        "rejected_documents": [
                            {
                                "document_id": "doc_bad",
                                "reason_code": "official_record_relevance_mismatch",
                            }
                        ],
                    },
                    "source_class_coverage": {
                        "covered_source_classes": ["environmental_or_land_record"],
                        "missing_source_classes": [],
                    },
                },
                "errors": [
                    {
                        "code": "internal_error",
                        "message": "Official-record PDF download failed",
                        "retryable": True,
                        "detail": {
                            "extraction_failure_class": "pdf_or_download",
                            "extraction_failure_stage": "download",
                            "url": "https://example.gov.cn/a.pdf",
                        },
                    }
                ],
                "documents": [
                    {
                        "title": "record",
                        "url": "https://example.gov.cn/record.html",
                        "raw_text_chars": 14029,
                        "raw_text_excerpt": "official record text" * 100,
                        "metadata": {
                            "source_classes": [
                                "environmental_or_land_record",
                                "regulatory_record",
                            ],
                            "evidence_quality": {
                                "proof_strength": "strong",
                                "proof_score": 95,
                                "topic_match": True,
                                "region_match": True,
                                "administrative_level_match": True,
                                "topic_terms": ["现代煤化工"],
                            },
                        },
                    }
                ],
            }
        ],
    }

    compact = module._compact_artifact(artifact, max_chars=1000)

    assert compact["truncated_for_llm"] is True
    summary = compact["audit_summary"]["tasks"][0]
    fallback = summary["direct_fallbacks"]["official_record_search_fallback"]
    assert fallback["pdf_extraction"]["failure_classes"]["pdf_download_failed"] == 1
    assert fallback["rejected_documents"][0]["reason_code"] == (
        "official_record_relevance_mismatch"
    )
    assert summary["errors"][0]["extraction_failure_class"] == "pdf_or_download"
    assert summary["documents"][0]["source_classes"] == [
        "environmental_or_land_record",
        "regulatory_record",
    ]
    assert summary["documents"][0]["evidence_quality"]["proof_strength"] == "strong"
