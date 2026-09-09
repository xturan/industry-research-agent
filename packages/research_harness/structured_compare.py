# ruff: noqa: E501
"""Phase C.3.1 — Structured Compare.

Side-by-side comparison of two Editor1 outputs for the SAME inputs:
- Legacy Editor1 -> legacy_markdown (the ONLY formal output; unchanged).
- Claim-Constrained Structured Editor1 -> Strict-JSON per-section LLM generation
  -> StructuredDraft -> deterministic Markdown renderer -> structured_markdown.

Structured Editor1 reads ONLY the C.1 Editor1Input (approved ClaimCards +
referenced EvidenceUnits + Section readiness + unresolved gaps + writing policy).
It NEVER reads raw sources, full evidence, pending/rejected/blocked claims, the
advisory backfill shadow store, or the Legacy draft (independence).

Per section: LLM is called once; the section is validated; on failure it is
retried at most `max_retries` (default 1) with the validation errors injected.
Second failure -> section_status = validation_failed. Never affects Legacy.

Compare output is saved per run under the caller-provided output_dir:
  editor1_input.json / structured_draft.json / validation_report.json /
  structured_markdown.md / legacy_markdown.md / comparison_report.json
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.research_harness.constrained_synthesis import (
    build_evidence_gap_paragraph,
    build_semantic_basis_map,
    compile_report_synthesis_triggers,
    generate_synthesis_paragraph,
    run_semantic_critic,
)
from packages.research_harness.eval_persistence import RunEvaluationStore
from packages.research_harness.structured_draft import (
    ASSERTION_RANK,
    DEFAULT_WRITING_POLICY,
    READINESS_MAX_ASSERTION,
    DraftParagraph,
    DraftSection,
    StructuredDraft,
    compile_editor1_input,
    draft_to_dict,
    editor_input_to_dict,
    input_fingerprint,
    stable_draft_id,
    stable_paragraph_id,
    validate_structured_draft,
)

AssertionLevel = Literal["mentioned", "observed", "supported", "confirmed"]
ParagraphRole = Literal["factual", "gap_descriptive", "transition", "synthesis"]

_GAP_NEGATIVE_PHRASES = (
    "尚未形成", "没有发生", "没有形成", "不存在", "并未", "未发生",
    "没有项目", "没有收入", "没有政策",
)


# ── strict LLM section JSON (extra="forbid", enum constraints) ──────────────

class LLMNumericMention(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    evidence_id: str


class LLMParagraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paragraph_role: ParagraphRole = "factual"
    text: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    assertion_level: AssertionLevel = "mentioned"
    limitations: list[str] = Field(default_factory=list)
    numeric_mentions: list[LLMNumericMention] = Field(default_factory=list)
    synthesis_id: str = ""  # C.3.3: only for paragraph_role == "synthesis"


class LLMSectionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section_id: str
    title: str
    paragraphs: list[LLMParagraph] = Field(default_factory=list)


@dataclass(frozen=True)
class SectionIssue:
    code: str
    severity: Literal["error", "warning"] = "error"
    message: str = ""
    paragraph_id: str = ""
    target_id: str = ""


# ── per-section generation input ────────────────────────────────────────────

@dataclass(frozen=True)
class SectionGenerationInput:
    section_id: str
    title: str
    readiness: str
    # allowed = eligible claims in ready/partial sections (what the LLM may use)
    allowed_claim_ids: tuple[str, ...]
    # Coverage Contract (C.3.1 calibration):
    required_claim_ids: tuple[str, ...] = ()
    optional_claim_ids: tuple[str, ...] = ()
    required_limitation_ids: tuple[str, ...] = ()
    forbidden_conclusions: tuple[str, ...] = ()
    paragraph_budget: dict[str, int] = field(
        default_factory=lambda: {"min": 1, "max": 3}
    )
    claim_cards: tuple[dict[str, Any], ...] = ()
    referenced_evidence_units: tuple[dict[str, Any], ...] = ()
    unresolved_gap_ids: tuple[str, ...] = ()
    writing_policy: dict[str, Any] = field(default_factory=lambda: DEFAULT_WRITING_POLICY)


# ── deterministic claim selection (C.3.2 assignment) + evidence compression ──

def _rank_evidence(evidence_map: dict[str, dict], evidence_ids: list[str]) -> list[str]:
    """Score evidence briefs: verified > primary > family match > span non-empty."""

    def score(eid: str) -> tuple[int, int, int, int]:
        e = evidence_map.get(eid, {})
        verified = 1 if e.get("quote_verification_status") == "verified" else 0
        primary = 1 if e.get("is_primary_source") else 0
        family = 1 if e.get("source_family") else 0
        span = 1 if (e.get("quoted_span") or "").strip() else 0
        return (verified, primary, family, span)

    ordered = sorted(
        (eid for eid in evidence_ids if eid in evidence_map),
        key=lambda eid: score(eid),
        reverse=True,
    )
    return ordered


def build_section_inputs(
    editor1_input,
    *,
    max_evidence_per_claim: int = 2,
    slot_status: dict[str, str] | None = None,
) -> list[SectionGenerationInput]:
    """Build per-section Coverage Contracts (C.3.1 + C.3.2 assignment).

    - allowed = required + optional (post Section–Claim Assignment); suppressed
      claims never enter the prompt.
    - required = representative claim of each critical / required-and-satisfied
      slot (C.3.2 assignment).
    - Evidence compressed to the top `max_evidence_per_claim` briefs per claim.
    """
    from packages.research_harness.section_claim_assignment import assign_section_claims

    slot_status = slot_status or {
        r["slot_id"]: r["status"]
        for r in editor1_input.coverage_report.get("slot_reports", [])
    }
    assignments = {
        a.section_id: a for a in assign_section_claims(editor1_input)
    }
    evidence_map = {e["evidence_id"]: e for e in editor1_input.referenced_evidence_units}

    section_inputs: list[SectionGenerationInput] = []
    for constraint in editor1_input.section_constraints:
        slot_ids = list(constraint.slot_ids)
        readiness = constraint.readiness
        assignment = assignments.get(constraint.section_id)

        if readiness in {"blocked", "unknown"}:
            # no LLM; deterministic gap only -> no allowed claims
            section_inputs.append(SectionGenerationInput(
                section_id=constraint.section_id,
                title=constraint.section_id,
                readiness=readiness,
                allowed_claim_ids=(),
                required_claim_ids=(),
                optional_claim_ids=(),
                referenced_evidence_units=(),
                unresolved_gap_ids=tuple(
                    g.get("gap_id") or g.get("gap_key") or ""
                    for g in editor1_input.unresolved_research_gaps
                    if g.get("slot_id") in slot_ids
                ),
            ))
            continue

        required = list(assignment.required_claim_ids) if assignment else []
        optional = list(assignment.optional_claim_ids) if assignment else []
        allowed_ids = required + optional
        claim_map = {c["claim_id"]: c for c in editor1_input.approved_claim_cards}
        claims_in_section = [
            claim_map[cid] for cid in allowed_ids if cid in claim_map
        ]

        # required limitations = limitation texts of required claims
        required_limitations: list[str] = []
        for cid in required:
            card = claim_map.get(cid)
            if card:
                for lim in card.get("limitations") or []:
                    if lim and lim not in required_limitations:
                        required_limitations.append(lim)

        # compressed evidence per claim (only allowed claims' evidence)
        referenced: list[dict] = []
        seen: set[str] = set()
        for c in claims_in_section:
            ranked = _rank_evidence(
                evidence_map, list(c.get("evidence_ids") or [])
            )[:max_evidence_per_claim]
            for eid in ranked:
                if eid not in seen:
                    seen.add(eid)
                    referenced.append(dict(evidence_map[eid]))

        section_inputs.append(SectionGenerationInput(
            section_id=constraint.section_id,
            title=constraint.section_id,
            readiness=readiness,
            allowed_claim_ids=tuple(allowed_ids),
            required_claim_ids=tuple(required),
            optional_claim_ids=tuple(optional),
            required_limitation_ids=tuple(required_limitations),
            forbidden_conclusions=tuple(_forbidden_conclusions(readiness, slot_ids)),
            claim_cards=tuple(claims_in_section),
            referenced_evidence_units=tuple(referenced),
            unresolved_gap_ids=tuple(
                g.get("gap_id") or g.get("gap_key") or ""
                for g in editor1_input.unresolved_research_gaps
                if g.get("slot_id") in slot_ids
            ),
        ))
    return section_inputs


def _forbidden_conclusions(readiness: str, slot_ids: list[str]) -> list[str]:
    defaults = ["不得根据证据缺失推导'尚未发生/不存在'"]
    if readiness == "partial":
        defaults.append("不得表述为已全面验证或规模化商业运营")
    return defaults


class LlmCall(Protocol):
    def __call__(self, system_prompt: str, user_prompt: str) -> dict[str, Any] | None: ...


# ── parser ──────────────────────────────────────────────────────────────────

def parse_llm_section(raw: Any, *, section_id: str) -> LLMSectionDraft:
    """Strict parse of the LLM section JSON (raises on any schema violation)."""
    if not isinstance(raw, dict):
        raise ValueError(f"section JSON root must be an object, got {type(raw).__name__}")
    draft = LLMSectionDraft.model_validate(raw)
    if draft.section_id != section_id:
        raise ValueError(
            f"section_id mismatch: expected {section_id!r}, got {draft.section_id!r}"
        )
    return draft


def _claim_map(section_input: SectionGenerationInput) -> dict[str, dict[str, Any]]:
    return {c["claim_id"]: c for c in section_input.claim_cards}


def _evidence_map(section_input: SectionGenerationInput) -> dict[str, dict[str, Any]]:
    return {e["evidence_id"]: e for e in section_input.referenced_evidence_units}


def _is_gap_negative(text: str) -> bool:
    lowered = (text or "").lower()
    return any(phrase in lowered for phrase in _GAP_NEGATIVE_PHRASES)


def _numeric_mention_supported(mention: LLMNumericMention, evidence: dict) -> bool:
    text = mention.text
    if text and text in str(evidence.get("quoted_span") or ""):
        return True
    for kv in (evidence.get("key_fields") or {}).values():
        if text and text in str(kv.get("value") or ""):
            return True
    return False


# ── section validator (schema / references / assertion / limitation / gap) ──

def validate_llm_section(
    section_draft: LLMSectionDraft,
    section_input: SectionGenerationInput,
) -> list[SectionIssue]:
    issues: list[SectionIssue] = []
    claim_map = _claim_map(section_input)
    evidence_map = _evidence_map(section_input)
    readiness_max = READINESS_MAX_ASSERTION.get(section_input.readiness, "observed")

    # Coverage Contract: every required claim and required limitation must be used.
    used_claims = {cid for p in section_draft.paragraphs for cid in p.claim_ids}
    for cid in section_input.required_claim_ids:
        if cid not in used_claims:
            issues.append(SectionIssue("required_claim_missing", "error",
                                       f"required claim {cid} not used", "", cid))
    used_limitations = {lim for p in section_draft.paragraphs for lim in p.limitations}
    for lim in section_input.required_limitation_ids:
        if lim not in used_limitations:
            issues.append(SectionIssue("required_limitation_missing", "error",
                                       f"required limitation not preserved: {lim}", "", lim))

    for p in section_draft.paragraphs:
        pid = f"{section_draft.section_id}:{p.text[:20]}"
        if p.paragraph_role == "factual":
            if not p.claim_ids:
                issues.append(SectionIssue("factual_missing_claim", "error",
                                           "factual paragraph has no claim_ids", pid))
            if not p.evidence_ids:
                issues.append(SectionIssue("factual_missing_evidence", "error",
                                           "factual paragraph has no evidence_ids", pid))

        # Paragraph claims: validate membership/approval, then check evidence
        # against the UNION of the paragraph's claims' evidence (a paragraph may
        # synthesize multiple claims, each contributing its own evidence).
        paragraph_cards = []
        for cid in p.claim_ids:
            if cid not in section_input.allowed_claim_ids:
                issues.append(SectionIssue("claim_not_in_allowed_set", "error",
                                           f"claim {cid} not in allowed set", pid, cid))
                continue
            card = claim_map.get(cid)
            if card is None:
                issues.append(SectionIssue("unknown_claim_id", "error",
                                           f"claim {cid} does not exist", pid, cid))
                continue
            if card.get("approval_status") != "approved":
                issues.append(SectionIssue("claim_not_approved", "error",
                                           f"claim {cid} not approved", pid, cid))
            paragraph_cards.append(card)

        union_evidence = {
            eid for card in paragraph_cards for eid in (card.get("evidence_ids") or [])
        }
        for eid in p.evidence_ids:
            if eid not in evidence_map:
                issues.append(SectionIssue("unknown_evidence_id", "error",
                                           f"evidence {eid} does not exist", pid, eid))
            elif eid not in union_evidence:
                issues.append(SectionIssue("evidence_not_referenced_by_claim", "error",
                                           f"evidence {eid} not referenced by any paragraph claim",
                                           pid, eid))

        for card in paragraph_cards:
            cid = card["claim_id"]
            max_allowed = str(card.get("max_allowed_assertion_level") or "mentioned")
            if ASSERTION_RANK.get(p.assertion_level, 0) > ASSERTION_RANK.get(max_allowed, 0):
                issues.append(SectionIssue("assertion_level_exceeded", "error",
                                           f"{p.assertion_level} > claim max {max_allowed}",
                                           pid, cid))
            claim_lim = set(card.get("limitations") or [])
            if claim_lim and not claim_lim.issubset(set(p.limitations)):
                issues.append(SectionIssue("limitation_not_preserved", "error",
                                           f"claim {cid} limitations dropped", pid, cid))

        if ASSERTION_RANK.get(p.assertion_level, 0) > ASSERTION_RANK.get(readiness_max, 0):
            issues.append(SectionIssue("readiness_assertion_exceeded", "error",
                                       f"{p.assertion_level} > readiness max {readiness_max}",
                                       pid))
        if section_input.readiness in {"blocked", "unknown"} and (
            p.paragraph_role == "factual"
            or ASSERTION_RANK.get(p.assertion_level, 0) >= ASSERTION_RANK.get("supported", 0)
        ):
            issues.append(SectionIssue("blocked_unknown_strong_conclusion", "error",
                                       "blocked/unknown section strong conclusion", pid))
        if p.paragraph_role == "gap_descriptive" and _is_gap_negative(p.text):
            issues.append(SectionIssue("gap_unapproved_negative_assertion", "error",
                                       "gap paragraph auto-asserts a negative conclusion", pid))

        for mention in p.numeric_mentions:
            if mention.evidence_id not in evidence_map:
                issues.append(SectionIssue("unsupported_numeric_mention", "error",
                                           "numeric mention references missing evidence",
                                           pid, mention.evidence_id))
            elif not _numeric_mention_supported(mention, evidence_map[mention.evidence_id]):
                issues.append(SectionIssue("unsupported_numeric_mention", "error",
                                           "numeric mention not found in evidence span/fact",
                                           pid, mention.evidence_id))

    return issues


# ── prompt builder ──────────────────────────────────────────────────────────

_SECTION_JSON_SCHEMA = """{
  "section_id": "<section_id>",
  "title": "<title>",
  "paragraphs": [
    {
      "paragraph_role": "factual|gap_descriptive|transition",
      "text": "...",
      "claim_ids": ["allowed_claim_id"],
      "evidence_ids": ["allowed_evidence_id"],
      "assertion_level": "mentioned|observed|supported|confirmed",
      "limitations": ["..."],
      "numeric_mentions": [{"text": "2025年6月", "evidence_id": "allowed_evidence_id"}]
    }
  ]
}"""


# ── few-shot examples (virtual IDs only; never real run IDs) ────────────────

_READY_MULTI_CLAIM_EXAMPLE_IN = """\
readiness=ready
required_claim_ids=[c1, c2]
optional_claim_ids=[c3]
claims:
- c1: 项目已正式投入运营 (max_assertion_level=confirmed, evidence=[e1])
- c2: 项目已开通跨城物流场景 (max_assertion_level=supported, evidence=[e2])"""

_READY_MULTI_CLAIM_EXAMPLE_OUT = """\
{
  "section_id": "project_progress",
  "title": "项目落地与运营进展",
  "paragraphs": [{
    "paragraph_role": "factual",
    "text": "官方披露显示，该项目已正式投入运营，并已形成跨城物流应用场景，说明其已从规划建设阶段进入实际运行阶段。",
    "claim_ids": ["c1", "c2"],
    "evidence_ids": ["e1", "e2"],
    "assertion_level": "supported",
    "limitations": [],
    "numeric_mentions": []
  }]
}"""

_PARTIAL_WITH_LIMITATION_EXAMPLE_IN = """\
readiness=partial
required_claim_ids=[c4, c5]
required_limitation_ids=[l1]
forbidden_conclusions=[不得判断项目已经实现规模化商业运营]
claims:
- c4: 项目已经投入试运行 (max_assertion_level=observed, evidence=[e4])
- c5: 项目已完成首批运输任务 (max_assertion_level=observed, evidence=[e5],
     limitations=[l1: 尚未披露稳定运营频次和订单规模])"""

_PARTIAL_WITH_LIMITATION_EXAMPLE_OUT = """\
{
  "section_id": "operation_progress",
  "title": "运营进展",
  "paragraphs": [{
    "paragraph_role": "factual",
    "text": "公开信息显示，该项目已进入试运行阶段并完成首批运输任务，表明具体应用场景已经开始落地；但由于尚未披露稳定运营频次和订单规模，目前不足以判断其是否已形成规模化商业运营。",
    "claim_ids": ["c4", "c5"],
    "evidence_ids": ["e4", "e5"],
    "assertion_level": "observed",
    "limitations": ["l1"],
    "numeric_mentions": []
  }]
}"""

_GAP_NEGATIVE_CORRECTION = """\
错误：未找到上市公司收入披露，因此相关项目尚未形成收入。
正确：在本轮检索范围内，尚未找到能够确认相关项目收入贡献的公开披露。
原因：证据缺失只能说明当前未能确认，不能证明事实不存在。"""


def select_section_examples(readiness: str) -> list[str]:
    if readiness == "ready":
        return [
            "【示例 A｜ready，多 Claim 综合】\n输入：\n"
            + _READY_MULTI_CLAIM_EXAMPLE_IN
            + "\n输出：\n" + _READY_MULTI_CLAIM_EXAMPLE_OUT,
        ]
    if readiness == "partial":
        return [
            "【示例 B｜partial，有限结论并保留 limitation】\n输入：\n"
            + _PARTIAL_WITH_LIMITATION_EXAMPLE_IN
            + "\n输出：\n" + _PARTIAL_WITH_LIMITATION_EXAMPLE_OUT,
            "【示例 C｜证据缺失 ≠ 事实不存在】\n" + _GAP_NEGATIVE_CORRECTION,
        ]
    return []


def build_section_prompt(
    section_input: SectionGenerationInput, *, errors_hint: str = "",
    use_fewshot: bool = True,
) -> tuple[str, str]:
    required_claims = "\n".join(
        f"- {c['claim_id']} [max_allowed={c.get('max_allowed_assertion_level')}] "
        f"limitations={c.get('limitations')} | {c.get('text')}"
        for c in section_input.claim_cards if c["claim_id"] in section_input.required_claim_ids
    ) or "(无)"
    optional_claims = "\n".join(
        f"- {c['claim_id']} [max_allowed={c.get('max_allowed_assertion_level')}] | {c.get('text')}"
        for c in section_input.claim_cards if c["claim_id"] in section_input.optional_claim_ids
    ) or "(无)"
    allowed_evidence = "\n".join(
        f"- {e['evidence_id']} (family={e.get('source_family')}, primary={e.get('is_primary_source')}) "
        f"span={e.get('quoted_span') or ''}"
        for e in section_input.referenced_evidence_units
    )
    gaps = ", ".join(section_input.unresolved_gap_ids) or "none"
    forbidden = "; ".join(section_input.forbidden_conclusions) or "(无)"
    budget = section_input.paragraph_budget

    examples = "\n\n".join(
        select_section_examples(section_input.readiness) if use_fewshot else []
    )

    system_prompt = (
        "你是严谨的中文产业研报写作助手。只根据给定的已批准 Claim 与 Evidence 撰写单一章节。\n"
        "不得读取或引用未提供的材料。\n\n"
        "[非协商规则]\n"
        "1. 只能引用 allowed claim_ids / evidence_ids，禁止自创 ID。\n"
        "2. 必须使用 required_claim_ids 中的每个 Claim（每个 required Claim 至少出现在一个 "
        "paragraph.claim_ids 中）。optional_claim_ids 可省略，但不得使用列表之外的 Claim。\n"
        "3. 可将多个相关 Claim 合并为一个自然段，不要逐条机械复述。\n"
        "4. 所有 required_limitation_ids 必须原样出现在对应 Paragraph 的 limitations 中，"
        "并在正文体现。\n"
        "5. 不得通过更强措辞扩大 max_assertion_level；readiness=partial 时段落必须包含限制性表达。\n"
        "6. 未批准 Gap 只能写'现有证据不足以确认…'，禁止写'没有/尚未/不存在/未形成'。\n"
        "7. 输出必须是严格 JSON，无额外字段，字段名与 schema 完全一致。\n\n"
        f"[输出 JSON Schema]\n{_SECTION_JSON_SCHEMA}"
    )
    user_prompt = (
        f"[当前章节 Contract]\n"
        f"section_id={section_input.section_id}\n"
        f"title={section_input.title}\n"
        f"readiness={section_input.readiness} "
        f"(允许最大 assertion={READINESS_MAX_ASSERTION.get(section_input.readiness, 'observed')})\n"
        f"paragraph_budget min={budget.get('min')} max={budget.get('max')}\n"
        f"required_claim_ids={list(section_input.required_claim_ids)}\n"
        f"optional_claim_ids={list(section_input.optional_claim_ids)}\n"
        f"required_limitation_ids={list(section_input.required_limitation_ids)}\n"
        f"forbidden_conclusions={forbidden}\n"
        f"未解决 gap_ids={gaps}\n\n"
        f"[示例]\n{examples or '(该 readiness 无示例)'}\n\n"
        f"[当前 allowed claims]\nrequired:\n{required_claims}\noptional:\n{optional_claims}\n\n"
        f"[当前 allowed evidence（已压缩为每 Claim 最强 1-2 条）]\n{allowed_evidence or '(无)'}\n\n"
        + (f"[上一轮校验失败，请仅修复以下问题，保留已通过段落]\n{errors_hint}\n\n" if errors_hint else "")
        + "[输出前自检]\n"
        "- 每个 required Claim 是否都已覆盖？\n"
        "- 每个 required limitation 是否都保留？\n"
        "- 是否使用了 allowed 集合之外的 Claim/Evidence ID？\n"
        "- assertion 是否不超过允许上限？\n"
        "请只输出该章节的 JSON。"
    )
    return system_prompt, user_prompt


# ── per-section generation with validator-guided retry ──────────────────────

@dataclass(frozen=True)
class SectionGenerationResult:
    section_id: str
    status: Literal["ok", "validation_failed", "parse_failed", "llm_failed"]
    retry_count: int
    section_draft: LLMSectionDraft | None
    issues: tuple[SectionIssue, ...] = ()


def _deterministic_gap_section(section_input: SectionGenerationInput) -> LLMSectionDraft:
    """Blocked/unknown sections skip the LLM entirely (deterministic gap)."""
    text = DEFAULT_WRITING_POLICY["gap_unapproved_fallback_text"]
    if section_input.unresolved_gap_ids:
        text += f"（相关 gap: {', '.join(section_input.unresolved_gap_ids)}）"
    return LLMSectionDraft(
        section_id=section_input.section_id,
        title=section_input.title,
        paragraphs=[LLMParagraph(
            paragraph_role="gap_descriptive",
            text=text,
            claim_ids=[], evidence_ids=[],
            assertion_level="observed",
            limitations=[],
            numeric_mentions=[],
        )],
    )


def _retry_feedback(
    section_draft: LLMSectionDraft,
    section_input: SectionGenerationInput,
    issues: list[SectionIssue],
) -> str:
    """Precise, actionable retry feedback (not a generic rewrite instruction)."""
    used_claim_ids = {cid for p in section_draft.paragraphs for cid in p.claim_ids}
    used_limitations = {lim for p in section_draft.paragraphs for lim in p.limitations}

    missing_claims = [
        cid for cid in section_input.required_claim_ids if cid not in used_claim_ids
    ]
    missing_limits = [
        lim for lim in section_input.required_limitation_ids if lim not in used_limitations
    ]
    invalid_claims = sorted({
        i.target_id for i in issues if i.code in {"claim_not_in_allowed_set", "unknown_claim_id"}
    })
    invalid_evidence = sorted({
        i.target_id for i in issues if i.code in {"unknown_evidence_id"}
    })
    assertion = [i.code for i in issues if "assertion" in i.code]
    forbidden_gap = [i.code for i in issues if i.code == "gap_unapproved_negative_assertion"]

    feedback = {
        "missing_required_claim_ids": missing_claims,
        "missing_limitation_ids": missing_limits,
        "invalid_claim_ids": invalid_claims,
        "invalid_evidence_ids": invalid_evidence,
        "assertion_level_violations": assertion,
        "forbidden_gap_assertions": forbidden_gap,
    }
    instruction = (
        "只修复上述问题；不得删除当前已验证通过的 Paragraph；"
        "不得新增允许集合之外的 Claim 或 Evidence。"
    )
    return f"{json.dumps(feedback, ensure_ascii=False)}。{instruction}"


def generate_structured_section(
    section_input: SectionGenerationInput,
    llm_call: LlmCall,
    *,
    max_retries: int = 1,
    use_fewshot: bool = True,
) -> SectionGenerationResult:
    # Blocked/unknown: deterministic gap_descriptive, never call the LLM.
    if section_input.readiness in {"blocked", "unknown"}:
        return SectionGenerationResult(
            section_input.section_id, "ok", 0,
            _deterministic_gap_section(section_input),
        )

    errors_hint = ""
    last_draft: LLMSectionDraft | None = None
    last_issues: list[SectionIssue] = []
    for attempt in range(max_retries + 1):
        system_prompt, user_prompt = build_section_prompt(
            section_input, errors_hint=errors_hint, use_fewshot=use_fewshot,
        )
        try:
            raw = llm_call(system_prompt, user_prompt)
        except Exception as exc:  # noqa: BLE001 - fail-open
            return SectionGenerationResult(
                section_input.section_id, "llm_failed", attempt, None,
                (SectionIssue("llm_call_failed", "error", str(exc)[:200]),),
            )
        if raw is None:
            return SectionGenerationResult(
                section_input.section_id, "llm_failed", attempt, None,
                (SectionIssue("llm_call_failed", "error", "llm returned None"),),
            )
        try:
            draft = parse_llm_section(raw, section_id=section_input.section_id)
        except (ValidationError, ValueError) as exc:
            errors_hint = (
                f"输出无法解析为合法 JSON（{type(exc).__name__}）。请严格按 schema 输出。"
            )
            continue
        issues = validate_llm_section(draft, section_input)
        errors = [i for i in issues if i.severity == "error"]
        if not errors:
            return SectionGenerationResult(
                section_input.section_id, "ok", attempt, draft,
            )
        last_draft = draft
        last_issues = issues
        errors_hint = _retry_feedback(draft, section_input, errors)
    return SectionGenerationResult(
        section_input.section_id, "validation_failed", max_retries, last_draft,
        tuple(last_issues),
    )


# ── assemble StructuredDraft from section results ───────────────────────────

def assemble_structured_draft(
    *,
    section_results: list[SectionGenerationResult],
    run_id: str,
    draft_version: int = 1,
    approved_claim_ids: list[str],
    coverage_snapshot_id: str,
    unresolved_gap_ids: list[str],
    report_title: str,
) -> StructuredDraft:
    draft_id = stable_draft_id(
        run_id=run_id, draft_version=draft_version,
        claim_ids=approved_claim_ids, coverage_snapshot_id=coverage_snapshot_id,
    )
    sections: list[DraftSection] = []
    used_claim_ids: set[str] = set()
    for _i, result in enumerate(section_results):
        if result.section_draft is None:
            paragraphs = (DraftParagraph(
                paragraph_id=stable_paragraph_id(
                    draft_id=draft_id, section_id=result.section_id, index=0),
                text=DEFAULT_WRITING_POLICY["gap_unapproved_fallback_text"],
                paragraph_role="gap_descriptive",
                assertion_level="observed",
            ),)
        else:
            paragraphs = []
            for idx, p in enumerate(result.section_draft.paragraphs):
                paragraphs.append(DraftParagraph(
                    paragraph_id=stable_paragraph_id(
                        draft_id=draft_id, section_id=result.section_id, index=idx),
                    text=p.text,
                    claim_ids=tuple(p.claim_ids),
                    evidence_ids=tuple(p.evidence_ids),
                    assertion_level=p.assertion_level,
                    limitations=tuple(p.limitations),
                    paragraph_role=p.paragraph_role,
                    numeric_mentions=tuple(m.text for m in p.numeric_mentions),
                    synthesis_id=p.synthesis_id or "",
                ))
                used_claim_ids.update(p.claim_ids)
        sections.append(DraftSection(
            section_id=result.section_id,
            title=result.section_draft.title if result.section_draft else result.section_id,
            readiness_at_write=_readiness_of(result.section_id),
            paragraphs=tuple(paragraphs),
        ))
    unused = tuple(cid for cid in approved_claim_ids if cid not in used_claim_ids)
    return StructuredDraft(
        draft_id=draft_id, run_id=run_id, draft_version=draft_version,
        report_title=report_title, sections=tuple(sections),
        unused_claim_ids=unused, unresolved_gap_ids=tuple(unresolved_gap_ids),
    )


def _readiness_of(section_id: str) -> str:
    # Callers pass readiness through the generation input; this is patched via
    # the orchestrator below (we keep the string for the assembled DraftSection).
    return "ready"


# ── deterministic markdown renderer ─────────────────────────────────────────

def render_structured_draft_markdown(draft: StructuredDraft) -> str:
    parts: list[str] = []
    if draft.report_title:
        parts.append(f"# {draft.report_title}")
    for section in draft.sections:
        parts.append(f"## {section.title}")
        for p in section.paragraphs:
            text = str(p.text or "").strip()
            if not text:
                continue
            if p.paragraph_role == "gap_descriptive":
                text = f"> {text}"
            if p.limitations:
                text += "\n\n> 局限：" + "；".join(p.limitations)
            parts.append(text)
    return "\n\n".join(part for part in parts if part)


# ── comparison report ───────────────────────────────────────────────────────

def _text_coverage(markdown: str, texts: list[str]) -> float:
    if not texts:
        return 1.0
    norm_md = re.sub(r"\s+", "", markdown or "")
    hit = 0
    for text in texts:
        norm = re.sub(r"\s+", "", str(text or ""))
        if norm and norm in norm_md:
            hit += 1
    return round(hit / len(texts), 4)


def build_comparison_report(
    *,
    legacy_markdown: str,
    draft: StructuredDraft,
    approved_claims: list[dict[str, Any]],
    referenced_evidence: list[dict[str, Any]],
    section_inputs: list[SectionGenerationInput],
    validation_report: dict[str, Any],
    retry_count: int,
    section_failure_count: int = 0,
) -> dict[str, Any]:
    approved_texts = [c.get("text") or "" for c in approved_claims]
    legacy_claim_coverage = _text_coverage(legacy_markdown, approved_texts)

    draft_used_claims = {
        cid for s in draft.sections for p in s.paragraphs for cid in p.claim_ids
    }

    # C.3.1 metric semantics: eligible = approved claims in ready/partial
    # sections (may be used); required = coverage contract subset (must be used).
    eligible_ids = {
        cid for si in section_inputs for cid in si.allowed_claim_ids
    }
    required_ids = {
        cid for si in section_inputs for cid in si.required_claim_ids
    }
    # Empty claim sets -> rate null + status "not_applicable" (NEVER 0.0, which
    # would be misread as "model used nothing").
    eligible_approved_claim_usage_rate = (
        round(len(draft_used_claims & eligible_ids) / len(eligible_ids), 4)
        if eligible_ids else None
    )
    eligible_usage_status = "ok" if eligible_ids else "not_applicable"
    required_claim_usage_rate = (
        round(len(draft_used_claims & required_ids) / len(required_ids), 4)
        if required_ids else None
    )
    required_usage_status = "ok" if required_ids else "not_applicable"
    approved_ids = [c["claim_id"] for c in approved_claims]
    approved_claim_usage_rate = round(
        len(draft_used_claims & set(approved_ids)) / max(1, len(approved_ids)), 4
    )

    # Paragraph mapping rates (among factual paragraphs).
    factual_paragraphs = [
        p for s in draft.sections for p in s.paragraphs if p.paragraph_role == "factual"
    ]
    paragraph_claim_mapping_rate = round(
        sum(1 for p in factual_paragraphs if p.claim_ids) / max(1, len(factual_paragraphs)), 4
    )
    paragraph_evidence_mapping_rate = round(
        sum(1 for p in factual_paragraphs if p.evidence_ids) / max(1, len(factual_paragraphs)), 4
    )

    referenced_ids = {e["evidence_id"] for e in referenced_evidence}
    draft_used_evidence = {
        eid for s in draft.sections for p in s.paragraphs for eid in p.evidence_ids
    }
    structured_evidence_trace_rate = round(
        len(draft_used_evidence & referenced_ids) / max(1, len(referenced_ids)), 4
    )

    legacy_evidence_spans = [e.get("quoted_span") or "" for e in referenced_evidence]
    legacy_evidence_trace_rate = _text_coverage(legacy_markdown, legacy_evidence_spans)

    legacy_limitation_texts = [
        lim for c in approved_claims for lim in (c.get("limitations") or [])
    ]
    legacy_limitation_retention = _text_coverage(legacy_markdown, legacy_limitation_texts)

    # Limitation retention: retained / required limitations of used-or-must-use
    # claims in ready/partial sections. not_applicable when nothing is required
    # (blocked/unknown only, or no factual paragraphs).
    required_limitations = {
        lim for si in section_inputs for lim in si.required_limitation_ids
    }
    retained_limitations = {
        lim for s in draft.sections for p in s.paragraphs for lim in p.limitations
    }
    if required_limitations:
        structured_limitation_retention = round(
            len(retained_limitations & required_limitations) / len(required_limitations), 4
        )
        limitation_retention_status = "ok"
    else:
        structured_limitation_retention = None
        limitation_retention_status = "not_applicable"

    structured_word_count = len(
        re.sub(r"\s+", "", " ".join(p.text for s in draft.sections for p in s.paragraphs))
    )
    legacy_word_count = len(re.sub(r"\s+", "", legacy_markdown or ""))

    structured_validation_passed = bool(validation_report.get("passed"))
    errors = [i for i in validation_report.get("issues", []) if i.get("severity") == "error"]
    issue_codes = [i.get("code") for i in errors]

    content_loss_warning = bool(
        (isinstance(eligible_approved_claim_usage_rate, (int, float))
         and eligible_approved_claim_usage_rate < 0.8)
        or (legacy_word_count and structured_word_count / legacy_word_count < 0.6)
        or any(
            s.readiness_at_write == "ready" and not any(
                p.paragraph_role == "factual" for p in s.paragraphs
            )
            for s in draft.sections
        )
    )

    return {
        "legacy_claim_coverage": legacy_claim_coverage,
        "structured_claim_coverage": approved_claim_usage_rate,
        "required_claim_usage_rate": required_claim_usage_rate,
        "required_claim_usage_status": required_usage_status,
        "eligible_approved_claim_usage_rate": eligible_approved_claim_usage_rate,
        "eligible_approved_claim_usage_status": eligible_usage_status,
        "paragraph_claim_mapping_rate": paragraph_claim_mapping_rate,
        "paragraph_evidence_mapping_rate": paragraph_evidence_mapping_rate,
        "legacy_evidence_trace_rate": legacy_evidence_trace_rate,
        "structured_evidence_trace_rate": structured_evidence_trace_rate,
        "legacy_limitation_retention": legacy_limitation_retention,
        "structured_limitation_retention": structured_limitation_retention,
        "limitation_retention_status": limitation_retention_status,
        "approved_claim_usage_rate": approved_claim_usage_rate,
        "structured_validation_passed": structured_validation_passed,
        "structured_retry_count": retry_count,
        "unsupported_numeric_mentions": issue_codes.count("unsupported_numeric_mention"),
        "assertion_level_violations": (
            issue_codes.count("assertion_level_exceeded")
            + issue_codes.count("readiness_assertion_exceeded")
        ),
        "blocked_section_strong_claims": issue_codes.count(
            "blocked_unknown_strong_conclusion"
        ),
        "structured_word_count": structured_word_count,
        "legacy_word_count": legacy_word_count,
        "structured_failed_section_count": section_failure_count,
        "content_loss_warning": content_loss_warning,
    }


# ── orchestrator ────────────────────────────────────────────────────────────

def _apply_constrained_synthesis(
    section_inputs: list[SectionGenerationInput],
    section_results: list[SectionGenerationResult],
    *,
    store: RunEvaluationStore,
    editor_input,
    llm_call: LlmCall,
    critic: LlmCall | None = None,
) -> tuple[list[SectionGenerationResult], list[dict[str, Any]]]:
    """C.3.3: append constrained synthesis paragraphs + upgrade gap paragraphs.

    Only touches the shadow SectionGenerationResult; never the main store.
    """
    slot_by_id: dict[str, dict] = {}
    for sec in editor_input.research_contract.get("sections", []):
        sec_id = str(sec.get("section_id") or "_default")
        for s in sec.get("claim_slots", []):
            slot_by_id[s["slot_id"]] = {**s, "section_id": sec_id}
    evidence_map = dict(store.evidence_units)
    claim_cards = dict(store.claim_cards)
    semantic_basis_map = build_semantic_basis_map(
        list(editor_input.approved_claim_cards), evidence_map)
    coverage_slot_status = {
        r["slot_id"]: r for r in editor_input.coverage_report.get("slot_reports", [])
    }
    synthesis_meta: list[dict[str, Any]] = []

    # C.3.3.1: report-level trigger scan; synthesis paragraphs are inserted into
    # each contract's target_section_id (may differ from the claims' source sections).
    report_contracts = compile_report_synthesis_triggers(
        section_inputs, slot_by_id=slot_by_id, evidence_map=evidence_map,
    )
    contracts_by_target: dict[str, list[Any]] = {}
    for contract in report_contracts:
        contracts_by_target.setdefault(contract.target_section_id, []).append(contract)

    updated: list[SectionGenerationResult] = []
    for section_input, result in zip(section_inputs, section_results, strict=False):
        if result.section_draft is None:
            updated.append(result)
            continue

        existing_paragraphs = list(result.section_draft.paragraphs)

        if section_input.readiness in {"blocked", "unknown"}:
            # Replace the bare gap paragraph with a rich, informative one.
            slot_ids = {
                s["slot_id"] for s in slot_by_id.values()
                if s.get("section_id") == section_input.section_id
            }
            missing_fields = []
            for sid in slot_ids:
                sr = coverage_slot_status.get(sid)
                if sr:
                    for f, st in (sr.get("field_status") or {}).items():
                        if st == "unsatisfied" and f not in missing_fields:
                            missing_fields.append(f)
            searched_families = sorted({
                str(ev.get("source_family") or "") for ev in store.search_events.values()
                if set(ev.get("slot_ids", [])) & slot_ids and ev.get("source_family")
            })
            gap = build_evidence_gap_paragraph(
                section_id=section_input.section_id,
                gap_ids=list(section_input.unresolved_gap_ids),
                searched_source_families=searched_families,
                missing_fields=missing_fields,
                missing_source_families=[],
                available_partial_claim_ids=list(section_input.optional_claim_ids),
            )
            gap_llm = LLMParagraph(
                paragraph_role="gap_descriptive", text=gap.text,
                claim_ids=[], evidence_ids=[], assertion_level="observed",
                limitations=[], numeric_mentions=[],
            )
            new_draft = result.section_draft.model_copy(update={"paragraphs": [gap_llm]})
            updated.append(SectionGenerationResult(
                section_id=result.section_id, status=result.status,
                retry_count=result.retry_count, section_draft=new_draft,
                issues=result.issues,
            ))
            continue

        # ready/partial: synthesis contracts targeting this section
        # (report-level scan, may combine claims from other sections)
        contracts = contracts_by_target.get(section_input.section_id, [])

        appended: list[Any] = []
        for contract in contracts:
            draft, status, issues, forensics = generate_synthesis_paragraph(
                contract, llm_call,
                claim_cards=claim_cards, evidence_units=evidence_map,
                max_retries=1,
            )
            risks: list[str] = []
            if draft is not None and status == "ok" and critic is not None:
                risks = run_semantic_critic(draft, contract, critic)
            if draft is not None and status == "ok":
                appended.append(LLMParagraph(
                    paragraph_role="synthesis",
                    synthesis_id=draft.synthesis_id,
                    text=draft.text,
                    claim_ids=draft.claim_ids,
                    evidence_ids=draft.evidence_ids,
                    assertion_level=draft.assertion_level,
                    limitations=draft.limitations,
                    numeric_mentions=[{"text": m.get("text", ""), "evidence_id": m.get("evidence_id", "")}
                                      for m in draft.numeric_mentions],
                ))
            # C.3.3.3: record per-claim semantic basis + trigger trace so a
            # fallback-based trigger is auditable (was it a real policy/landing
            # match, or an accidental keyword overlap?).
            basis_info: dict[str, dict] = {}
            for cid in contract.required_claim_ids:
                basis = semantic_basis_map.get(cid)
                if basis is not None:
                    basis_info[cid] = {
                        "source": basis.source,
                        "fallback_used": basis.fallback_used,
                        "evidence_ids": list(basis.evidence_ids),
                    }
            trigger_trace = None
            if contract.section_id == "_report" and len(contract.required_claim_ids) == 2:
                trigger_trace = {
                    "synthesis_id": contract.synthesis_id,
                    "policy_claim_id": contract.required_claim_ids[0],
                    "implementation_claim_id": contract.required_claim_ids[1],
                    "policy_semantic_source": basis_info.get(
                        contract.required_claim_ids[0], {}).get("source"),
                    "implementation_semantic_source": basis_info.get(
                        contract.required_claim_ids[1], {}).get("source"),
                    "trigger_result": "matched",
                }
            synthesis_meta.append({
                "section_id": section_input.section_id,
                "synthesis_id": contract.synthesis_id,
                "synthesis_type": contract.synthesis_type,
                "status": status,
                "inference_code": contract.allowed_inference_code,
                "semantic_risks": risks,
                "semantic_basis": basis_info,
                "trigger_trace": trigger_trace,
                "forensics": forensics,
            })

        new_draft = result.section_draft.model_copy(
            update={"paragraphs": [*existing_paragraphs, *appended]}
        )
        updated.append(SectionGenerationResult(
            section_id=result.section_id, status=result.status,
            retry_count=result.retry_count, section_draft=new_draft,
            issues=result.issues,
        ))

    return updated, synthesis_meta


def run_structured_compare(
    *,
    store: RunEvaluationStore,
    coverage_report: dict[str, Any],
    research_gaps: Sequence[Any],
    legacy_markdown: str,
    llm_call: LlmCall,
    run_id: str = "",
    output_dir=None,
    max_retries: int = 1,
    use_fewshot: bool = True,
    use_synthesis: bool = True,
    critic: LlmCall | None = None,
) -> dict[str, Any]:
    """Compile Editor1Input -> per-section LLM -> synthesis -> assemble -> compare.

    Writes artifacts under output_dir/<run_id>/ (when output_dir is given).
    Returns a JSON-serializable summary.
    """
    editor_input = compile_editor1_input(
        store=store, coverage_report=coverage_report, research_gaps=research_gaps,
    )
    section_inputs = build_section_inputs(editor_input)

    section_results: list[SectionGenerationResult] = []
    total_retries = 0
    for section_input in section_inputs:
        result = generate_structured_section(
            section_input, llm_call, max_retries=max_retries, use_fewshot=use_fewshot,
        )
        total_retries += result.retry_count
        section_results.append(result)

    # C.3.3 constrained synthesis + rich evidence-gap paragraphs (shadow only).
    if use_synthesis:
        section_results, synthesis_meta = _apply_constrained_synthesis(
            section_inputs, section_results,
            store=store, editor_input=editor_input,
            llm_call=llm_call, critic=critic,
        )
    else:
        synthesis_meta = []

    approved_claim_ids = [c["claim_id"] for c in editor_input.approved_claim_cards]
    coverage_snapshot_id = str(
        coverage_report.get("coverage_report_id") or coverage_report.get(
            "coverage_snapshot_id") or "cr"
    )
    unresolved_gap_ids = [
        g.get("gap_id") or g.get("gap_key") or ""
        for g in editor_input.unresolved_research_gaps
    ]
    draft = assemble_structured_draft(
        section_results=section_results,
        run_id=run_id,
        approved_claim_ids=approved_claim_ids,
        coverage_snapshot_id=coverage_snapshot_id,
        unresolved_gap_ids=unresolved_gap_ids,
        report_title=str(editor_input.research_contract.get("report_title") or ""),
    )
    # Patch readiness onto assembled sections from the generation inputs.
    readiness_map = {s.section_id: s.readiness for s in section_inputs}
    draft = _with_readiness(draft, readiness_map)

    validation = validate_structured_draft(
        draft,
        claim_cards=store.claim_cards,
        evidence_units=store.evidence_units,
        coverage_report=coverage_report,
    )
    structured_markdown = render_structured_draft_markdown(draft)
    comparison = build_comparison_report(
        legacy_markdown=legacy_markdown,
        draft=draft,
        approved_claims=list(editor_input.approved_claim_cards),
        referenced_evidence=list(editor_input.referenced_evidence_units),
        section_inputs=section_inputs,
        validation_report=validation.to_dict(),
        retry_count=total_retries,
        section_failure_count=sum(
            1 for r in section_results if r.status != "ok"
        ),
    )

    result = {
        "run_id": run_id,
        "mode": "structured_compare",
        "editor1_input": editor_input_to_dict(editor_input),
        "input_fingerprint": input_fingerprint(editor_input),
        "draft": draft_to_dict(draft),
        "validation_report": validation.to_dict(),
        "structured_markdown": structured_markdown,
        "legacy_markdown": legacy_markdown,
        "comparison_report": comparison,
        "synthesis_meta": synthesis_meta,
    }

    if output_dir is not None:
        from pathlib import Path

        out_dir = Path(output_dir) / (run_id or "run")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "editor1_input.json").write_text(
            json_dumps(result["editor1_input"]), encoding="utf-8")
        (out_dir / "structured_draft.json").write_text(
            json_dumps(result["draft"]), encoding="utf-8")
        (out_dir / "validation_report.json").write_text(
            json_dumps(result["validation_report"]), encoding="utf-8")
        (out_dir / "structured_markdown.md").write_text(
            result["structured_markdown"], encoding="utf-8")
        (out_dir / "legacy_markdown.md").write_text(
            result["legacy_markdown"], encoding="utf-8")
        (out_dir / "comparison_report.json").write_text(
            json_dumps(result["comparison_report"]), encoding="utf-8")
        result["artifact_dir"] = str(out_dir)

    return result


def _with_readiness(draft: StructuredDraft, readiness_map: dict[str, str]) -> StructuredDraft:
    return StructuredDraft(
        draft_id=draft.draft_id, run_id=draft.run_id, draft_version=draft.draft_version,
        report_title=draft.report_title,
        sections=tuple(
            DraftSection(
                section_id=s.section_id, title=s.title,
                readiness_at_write=readiness_map.get(s.section_id, "ready"),
                paragraphs=s.paragraphs,
            )
            for s in draft.sections
        ),
        unused_claim_ids=draft.unused_claim_ids,
        unresolved_gap_ids=draft.unresolved_gap_ids,
    )


def json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2)


# ── real LLM adapter (DeepSeek JSON via call_tooling_json) ──────────────────

def real_section_llm_call(system_prompt: str, user_prompt: str) -> dict[str, Any] | None:
    """Real adapter: DeepSeek strict JSON. Returns dict or None on failure."""
    from packages.research_harness.tooling.llm_agents import call_tooling_json

    result = call_tooling_json(system_prompt=system_prompt, user_prompt=user_prompt)
    return result.payload if isinstance(result.payload, dict) else None
