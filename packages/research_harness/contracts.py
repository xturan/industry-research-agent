from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class DraftParagraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paragraph_id: str
    text: str = Field(min_length=1)
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    limitations: list[str] = Field(default_factory=list)
    argument_posture: Literal["conclusive", "conditional", "exploratory"] = (
        "conditional"
    )


class DraftSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    title: str = Field(min_length=1)
    section_role: str = "analysis"
    argument_posture: Literal["conclusive", "conditional", "exploratory", "mixed"] = "mixed"
    markdown_body: str = ""
    paragraphs: list[DraftParagraph] = Field(default_factory=list)


class EditorDraftOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    draft_version: int = Field(ge=1)
    report_markdown: str = ""
    sections: list[DraftSection] = Field(default_factory=list)


class ReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    severity: Literal["info", "warning", "blocker"]
    issue_type: str = Field(min_length=1)
    target_claim_id: str | None = None
    description: str = Field(min_length=1)
    required_fix: str = Field(min_length=1)
    suggested_search_queries: list[str] = Field(default_factory=list)


class ReviewIssueList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[ReviewIssue] = Field(default_factory=list)


class ClaimVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    support_status: Literal[
        "supported",
        "partially_supported",
        "unsupported",
        "contradicted",
    ]
    support_score: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VerifierOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_verifications: list[ClaimVerificationResult] = Field(default_factory=list)
    quality_scores: dict[str, float] = Field(default_factory=dict)


class RequiredAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: Literal["ADD_EVIDENCE", "REVISE_TEXT", "REVIEW_RISK", "HUMAN_REVIEW"]
    target_claim_id: str | None = None
    required_source_family: str | None = None
    suggested_search_queries: list[str] = Field(default_factory=list)
    note: str = ""


class ChiefGateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal[
        "PASS",
        "ADD_EVIDENCE",
        "REVISE_TEXT",
        "REVIEW_RISK",
        "HUMAN_REVIEW",
        "FAILED",
    ]
    reason: str = Field(min_length=1)
    route_to: str = Field(min_length=1)
    required_actions: list[RequiredAction] = Field(default_factory=list)
    quality_scores: dict[str, float] = Field(default_factory=dict)
    loop_count: int = Field(ge=0)
    contract_mode: str = "validated"


def coerce_model_output(
    raw_output: Any,
    *,
    model_cls: type[BaseModel],
    fallback_factory,
) -> tuple[BaseModel, dict[str, Any]]:
    attempts: list[dict[str, Any]] = []

    try:
        normalized_output, normalization_notes = _normalize_model_output(
            raw_output,
            model_cls=model_cls,
        )
        model = model_cls.model_validate(normalized_output)
        attempt: dict[str, Any] = {"mode": "validate_dict", "status": "success"}
        status = "validated"
        if normalization_notes:
            attempt["normalizations"] = normalization_notes
            status = "normalized"
        return model, {
            "status": status,
            "attempt_count": 1,
            "used_fallback": False,
            "attempts": [attempt],
        }
    except ValidationError as exc:
        attempts.append(
            {
                "mode": "validate_dict",
                "status": "failed",
                "error": _truncate(str(exc)),
            }
        )

    if isinstance(raw_output, str):
        repaired = _try_parse_json_like(raw_output)
        if repaired is not None:
            try:
                normalized_repaired, normalization_notes = _normalize_model_output(
                    repaired,
                    model_cls=model_cls,
                )
                model = model_cls.model_validate(normalized_repaired)
                attempt = {"mode": "repair_json", "status": "success"}
                status = "repaired"
                if normalization_notes:
                    attempt["normalizations"] = normalization_notes
                    status = "repaired_normalized"
                attempts.append(attempt)
                return model, {
                    "status": status,
                    "attempt_count": len(attempts),
                    "used_fallback": False,
                    "attempts": attempts,
                }
            except ValidationError as exc:
                attempts.append(
                    {
                        "mode": "repair_json",
                        "status": "failed",
                        "error": _truncate(str(exc)),
                    }
                )

    fallback_model = model_cls.model_validate(fallback_factory())
    attempts.append({"mode": "structured_fallback", "status": "success"})
    return fallback_model, {
        "status": "fallback",
        "attempt_count": len(attempts),
        "used_fallback": True,
        "attempts": attempts,
    }


def _normalize_model_output(
    raw_output: Any,
    *,
    model_cls: type[BaseModel],
) -> tuple[Any, list[str]]:
    if model_cls is EditorDraftOutput and isinstance(raw_output, dict):
        return _normalize_editor_draft_output(raw_output)
    return raw_output, []


def _normalize_editor_draft_output(raw_output: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    is_section_like_input = _looks_like_draft_section(raw_output)
    normalized = dict(raw_output)
    notes: list[str] = []
    if "draft_id" not in normalized:
        normalized["draft_id"] = "editor_draft_normalized"
        notes.append("editor_draft_missing_draft_id")
    if "draft_version" not in normalized:
        normalized["draft_version"] = 1
        notes.append("editor_draft_missing_draft_version")

    sections = normalized.get("sections")
    if not isinstance(sections, list):
        if is_section_like_input:
            section_payload = {
                key: value
                for key, value in normalized.items()
                if key
                not in {
                    "draft_id",
                    "draft_version",
                    "report_markdown",
                    "sections",
                }
            }
            sections = [section_payload]
            normalized = {
                "draft_id": normalized.get("draft_id"),
                "draft_version": normalized.get("draft_version"),
                "report_markdown": "",
                "sections": sections,
            }
            notes.append("editor_draft_section_wrapped_as_output")
        else:
            return normalized, sorted(set(notes))

    normalized_sections: list[Any] = []
    for section in sections:
        if not isinstance(section, dict):
            normalized_sections.append(section)
            continue
        normalized_section = dict(section)
        markdown_body = normalized_section.get("markdown_body")
        if not markdown_body and normalized_section.get("body"):
            normalized_section["markdown_body"] = str(normalized_section.get("body") or "")
            notes.append("editor_draft_section_body_promoted_to_markdown_body")
        if "body" in normalized_section:
            normalized_section.pop("body", None)
        normalized_section["argument_posture"] = _normalize_section_argument_posture(
            normalized_section.get("argument_posture")
        )
        paragraphs = normalized_section.get("paragraphs")
        if isinstance(paragraphs, list):
            normalized_paragraphs: list[Any] = []
            for paragraph in paragraphs:
                if not isinstance(paragraph, dict):
                    normalized_paragraphs.append(paragraph)
                    continue
                normalized_paragraph = dict(paragraph)
                confidence = normalized_paragraph.get("confidence")
                qualitative = _normalize_confidence_label(confidence)
                if qualitative is not None and qualitative != confidence:
                    normalized_paragraph["confidence"] = qualitative
                    notes.append("editor_draft_numeric_confidence_to_label")
                normalized_paragraph["argument_posture"] = _normalize_paragraph_argument_posture(
                    normalized_paragraph.get("argument_posture")
                )
                normalized_paragraphs.append(normalized_paragraph)
            normalized_section["paragraphs"] = normalized_paragraphs
        normalized_sections.append(normalized_section)

    normalized["sections"] = normalized_sections
    if not normalized.get("report_markdown"):
        normalized["report_markdown"] = _compose_editor_report_markdown(
            sections=normalized_sections,
        )
        notes.append("editor_draft_report_markdown_composed_from_sections")
    return normalized, sorted(set(notes))


def _looks_like_draft_section(raw_output: dict[str, Any]) -> bool:
    return bool(raw_output.get("section_id")) and bool(raw_output.get("title"))


def _normalize_section_argument_posture(value: Any) -> Literal[
    "conclusive",
    "conditional",
    "exploratory",
    "mixed",
]:
    normalized = str(value or "").strip().lower()
    if normalized in {"conclusive", "conditional", "exploratory", "mixed"}:
        return normalized  # type: ignore[return-value]
    if normalized in {"neutral", "balanced", "analytic", "analytical"}:
        return "mixed"
    if normalized in {"cautious", "tentative"}:
        return "conditional"
    return "mixed"


def _normalize_paragraph_argument_posture(
    value: Any,
) -> Literal["conclusive", "conditional", "exploratory"]:
    normalized = str(value or "").strip().lower()
    if normalized in {"conclusive", "conditional", "exploratory"}:
        return normalized  # type: ignore[return-value]
    if normalized in {"neutral", "balanced", "analytic", "analytical", "cautious"}:
        return "conditional"
    return "conditional"


def _compose_editor_report_markdown(*, sections: list[Any]) -> str:
    rendered_sections: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "").strip()
        markdown_body = str(section.get("markdown_body") or "").strip()
        if markdown_body:
            if title and f"## {title}" not in markdown_body:
                rendered_sections.append(f"## {title}\n\n{markdown_body}")
            else:
                rendered_sections.append(markdown_body)
        elif title:
            rendered_sections.append(f"## {title}")
    return "\n\n".join(part for part in rendered_sections if part)


def _normalize_confidence_label(value: Any) -> Literal["high", "medium", "low"] | None:
    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped in {"high", "medium", "low"}:
            return stripped  # type: ignore[return-value]
        try:
            value = float(stripped)
        except ValueError:
            return None
    if isinstance(value, int | float):
        score = float(value)
        if score >= 0.75:
            return "high"
        if score >= 0.45:
            return "medium"
        if 0.0 <= score < 0.45:
            return "low"
    return None


def _try_parse_json_like(raw_output: str) -> dict[str, Any] | None:
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        start = raw_output.find("{")
        end = raw_output.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw_output[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def _truncate(text: str, limit: int = 300) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
