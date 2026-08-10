from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.core.config import get_settings
from packages.providers import DeepSeekProviderClient, ProviderConfigError
from packages.providers.base import JsonProviderClient


@dataclass(slots=True)
class StructuredLlmCallResult:
    payload: dict[str, Any] | None
    metadata: dict[str, Any]


def _truncate_text(value: Any, *, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _compact_evidence_bundle(evidence_bundle: dict[str, Any]) -> dict[str, Any]:
    """Compact evidence bundle for editor1 prompt context.

    Handles TWO shapes from the tool layer:
    1. Claim-centric (legacy): items have claim_id/claim_text/evidence_count/evidence[]
    2. Evidence-centric (current): items have evidence_id/summary/source_ids/...
       This is the shape returned by _tool_get_evidence_bundle.
    """
    items = []
    raw_items = list(evidence_bundle.get("items", []))[:8]
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        # ── Shape detection: evidence-centric vs claim-centric ──
        if "evidence_id" in item and "claim_id" not in item:
            # Evidence-centric: group by claim_ids
            claim_ids_for_ev = list(item.get("claim_ids", []))
            summary = item.get("summary", "")
            source_ids = list(item.get("source_ids", []))[:3]
            source_family = ""
            if isinstance(item.get("source"), dict):
                source_family = item.get("source", {}).get("source_family", "")
            # Build a single evidence entry
            ev_entry = {
                "evidence_id": item.get("evidence_id"),
                "summary": _truncate_text(summary, limit=180),
                "support_type": item.get("support_type"),
                "support_strength": item.get("support_strength"),
                "source_family": source_family,
                "source_ids": source_ids,
            }
            # Attach to each referenced claim
            for cid in claim_ids_for_ev[:4]:
                # Check if this claim already has an entry
                existing = next(
                    (ci for ci in items if ci.get("claim_id") == cid), None
                )
                if existing:
                    existing.setdefault("evidence_count", 0)
                    existing["evidence_count"] += 1
                    existing.setdefault("evidence", [])
                    existing["evidence"].append(ev_entry)
                else:
                    items.append({
                        "claim_id": cid,
                        "claim_text": "",  # evidence-centric items don't carry claim text
                        "evidence_count": 1,
                        "evidence": [ev_entry],
                    })
        elif "claim_id" in item:
            # Claim-centric: original format
            items.append({
                "claim_id": item.get("claim_id"),
                "claim_text": _truncate_text(item.get("claim_text"), limit=160),
                "evidence_count": item.get("evidence_count"),
                "evidence": [
                    {
                        "evidence_id": evidence.get("evidence_id"),
                        "summary": _truncate_text(evidence.get("summary"), limit=180),
                        "support_type": evidence.get("support_type"),
                        "support_strength": evidence.get("support_strength"),
                        "source_ids": list(evidence.get("source_ids") or [])[:3],
                    }
                    for evidence in list(item.get("evidence", []))[:3]
                    if isinstance(evidence, dict)
                ],
            })
    return {
        "claim_count": evidence_bundle.get("claim_count"),
        "evidence_count": evidence_bundle.get("evidence_count"),
        "items": items,
    }


def _compact_outline(outline: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(outline, dict):
        return {}
    sections = []
    for section in list(outline.get("sections", []))[:8]:
        if not isinstance(section, dict):
            continue
        sections.append(
            {
                "section_id": section.get("section_id"),
                "title": section.get("title"),
                "section_role": section.get("section_role"),
                "claim_ids": list(section.get("claim_ids", []))[:6],
            }
        )
    if sections:
        return {"section_count": len(sections), "sections": sections}
    return {
        key: value
        for key, value in list(outline.items())[:6]
        if key in {"section_count", "sections", "titles"}
    }


def _compact_support_matrix_rows(
    rows: list[dict[str, Any]],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    compact_rows = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        compact_rows.append(
            {
                "claim_id": row.get("claim_id"),
                "support_status": row.get("support_status"),
                "avg_support_strength": row.get("avg_support_strength"),
                "evidence_count": row.get("evidence_count"),
                "source_count": row.get("source_count"),
                "family_matched": row.get("family_matched"),
                "required_source_family": row.get("required_source_family"),
            }
        )
    return compact_rows


def build_tooling_llm_client(
    *,
    max_tokens: int | None = None,
    timeout_seconds: int | None = None,
) -> JsonProviderClient | None:
    settings = get_settings()
    if not settings.deepseek_api_key:
        return None
    try:
        return DeepSeekProviderClient(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_research_model,
            timeout_seconds=min(timeout_seconds or settings.deepseek_timeout_seconds, 120),
            max_retries=settings.deepseek_max_retries,
            max_tokens=max_tokens or settings.deepseek_max_tokens,
            store_reasoning_content=False,
        )
    except ProviderConfigError:
        return None


def call_tooling_json(
    *,
    system_prompt: str,
    user_prompt: str,
    client: JsonProviderClient | None = None,
    model: str | None = None,
    enable_thinking: bool | None = None,
    max_tokens: int | None = None,
    trace_ctx: dict[str, Any] | None = None,
    task_type: str | None = None,
) -> StructuredLlmCallResult:
    settings = get_settings()
    if client is None:
        from packages.capability_gateway.llm_service import build_gateway_aware_llm_client
        from packages.capability_gateway.router import llm_routing_mode

        if llm_routing_mode(settings) == "gateway":
            # G2-M1：gateway 模式 → LLM 正式走 Capability Gateway（STRICT → DeepSeek）。
            resolved_client = build_gateway_aware_llm_client(
                settings, task_type=task_type or "structured_draft"
            )
        else:
            resolved_client = build_tooling_llm_client(max_tokens=max_tokens)
    else:
        resolved_client = client
    if resolved_client is None:
        return StructuredLlmCallResult(
            payload=None,
            metadata={
                "llm_mode": "deterministic_fallback",
                "llm_reason": "missing_or_invalid_provider_config",
            },
        )

    try:
        response = resolved_client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model or settings.deepseek_research_model,
            enable_thinking=(
                settings.deepseek_enable_thinking
                if enable_thinking is None
                else enable_thinking
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return StructuredLlmCallResult(
            payload=None,
            metadata={
                "llm_mode": "deterministic_fallback",
                "llm_reason": f"provider_error:{type(exc).__name__}",
                "llm_error": str(exc)[:300],
            },
        )

    payload = response.json_data if isinstance(response.json_data, dict) else None
    metadata = {
        "llm_mode": "live_provider",
        "llm_reason": "provider_response_accepted" if payload is not None else "invalid_json_root",
        "llm_provider": response.provider,
        "llm_model": response.model,
        "llm_request_id": response.metadata.request_id,
        "llm_finish_reason": response.metadata.finish_reason,
        "llm_usage": response.metadata.usage,
        "llm_response_ms": response.metadata.response_ms,
    }
    if payload is None:
        metadata["llm_mode"] = "deterministic_fallback"

    # ── Real LLM-input audit (resume-eval observability) ──
    # Persist the ACTUAL system/user prompt sent to the provider, plus response
    # and metadata, into data/run_contexts/<run_id>/<node>/attempt_N.json so a
    # reviewer can see exactly what the model received. trace_ctx is provided by
    # node call sites (run_id + node_name); when absent, nothing is written.
    if trace_ctx:
        _persist_llm_trace(
            run_id=trace_ctx.get("run_id"),
            node_name=trace_ctx.get("node_name"),
            prompt_version=trace_ctx.get("prompt_version"),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_payload=payload,
            metadata=metadata,
            temperature=getattr(settings, "deepseek_temperature", 0.1),
        )

    return StructuredLlmCallResult(payload=payload, metadata=metadata)


def _persist_llm_trace(
    *,
    run_id: Any,
    node_name: str | None,
    prompt_version: str | None,
    system_prompt: str,
    user_prompt: str,
    response_payload: Any,
    metadata: dict[str, Any],
    temperature: float | None = None,
) -> str | None:
    """Write the real LLM input/output artifact for one call. Returns the path."""
    if not run_id:
        return None
    node = node_name or "unknown"
    run_dir = Path("data/run_contexts") / f"run_{run_id}" / node
    run_dir.mkdir(parents=True, exist_ok=True)
    attempt = 1
    while (run_dir / f"attempt_{attempt}.json").exists():
        attempt += 1
    import hashlib as _hashlib
    import subprocess as _sp
    try:
        git_commit = _sp.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
    except Exception:
        git_commit = ""
    artifact = {
        "run_id": run_id,
        "node_name": node,
        "attempt": attempt,
        "provider": metadata.get("llm_provider"),
        "model": metadata.get("llm_model"),
        "prompt_version": prompt_version,
        "system_prompt": system_prompt,
        "system_prompt_hash": _hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:16],
        "user_prompt": user_prompt,
        "user_prompt_hash": _hashlib.sha256(user_prompt.encode("utf-8")).hexdigest()[:16],
        "temperature": temperature,
        "git_commit": git_commit,
        "schema_version": "trace_v1",
        "response": response_payload,
        "metadata": metadata,
        "redaction": {"secrets_removed": True},
    }
    path = run_dir / f"attempt_{attempt}.json"
    try:
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)
    except Exception:
        return None


def build_editor1_draft_prompts(
    *,
    query: str,
    draft_version: int,
    claims: list[dict[str, Any]],
    evidence_bundle: dict[str, Any],
    outline: dict[str, Any] | None,
    prior_drafts: list[dict[str, Any]],
) -> tuple[str, str]:
    # ── Filter out fallback drafts that would pollute editor1 context ──
    _FALLBACK_SECTION_MARKERS = frozenset({
        "sec_provider_backed_fallback", "sec_fallback", "sec_structured_fallback",
    })
    _FALLBACK_CONTENT_MARKERS = ("fallback", "结构化降级草稿", "Fallback provider-backed draft")

    usable_drafts: list[dict[str, Any]] = []
    for draft in prior_drafts:
        if not isinstance(draft, dict):
            continue
        sections = list(draft.get("sections", []))
        section_ids = {
            str(s.get("section_id", ""))
            for s in sections if isinstance(s, dict)
        }
        # Skip if all sections are fallback markers
        if section_ids and section_ids.issubset(_FALLBACK_SECTION_MARKERS):
            continue
        # Skip if draft body explicitly says it's a fallback
        report_md = str(draft.get("report_markdown", ""))
        if any(marker in report_md for marker in _FALLBACK_CONTENT_MARKERS):
            continue
        usable_drafts.append(draft)

    prior_summary = [
        {
            "draft_id": draft.get("draft_id"),
            "draft_version": draft.get("draft_version"),
            "section_ids": [
                section.get("section_id")
                for section in list(draft.get("sections", []))[:8]
                if isinstance(section, dict)
            ],
        }
        for draft in usable_drafts[-2:]
    ]
    claim_summary = [
        {
            "claim_id": claim.get("claim_id"),
            "text": _truncate_text(claim.get("text"), limit=180),
            "supported": claim.get("supported"),
            "claim_family": claim.get("claim_family"),
            "required_source_family": claim.get("required_source_family"),
            "support_requirement": claim.get("support_requirement"),
            "evidence_ids": list(claim.get("evidence_ids", []))[:8],
        }
        for claim in claims[:12]
    ]
    system_prompt = (
        "You are Editor1, a lead research analyst writing the first readable "
        "draft for a production deep-research report. The product goal is a "
        "publishable Chinese Markdown research memo, not a schema dump or an "
        "audit preview. "
        "Return one strict JSON object only. "
        "Do not add commentary outside JSON. "
        "Use Markdown inside `report_markdown` and each section `markdown_body`. "
        "Use only the provided claims and evidence bundle. "
        "Do not invent unsupported evidence IDs, claim IDs, or source facts. "
        "Write like a research analyst: separate conclusions, conditions, "
        "limitations, uncertainty, and follow-up work. "
        "Prefer a structure that reads like a real report: executive summary, "
        "method/scope, dimension chapters, uncertainty, and next steps when relevant. "
        "Do not collapse the report into one section or one umbrella claim."
    )
    user_prompt = (
        "Produce the next editor draft JSON with exactly these top-level keys:\n"
        "- draft_id\n"
        "- draft_version\n"
        "- report_markdown\n"
        "- sections\n"
        "Each section must contain:\n"
        "- section_id\n"
        "- title\n"
        "- section_role\n"
        "- argument_posture\n"
        "- markdown_body\n"
        "- paragraphs\n"
        "Each paragraph must contain:\n"
        "- paragraph_id\n"
        "- text\n"
        "- claim_ids\n"
        "- evidence_ids\n"
        "- confidence\n"
        "- limitations\n"
        "- argument_posture\n"
        "Rules:\n"
        "1) Keep claim_ids and evidence_ids in the JSON structure (paragraph.claim_ids / "
        "evidence_ids) for auditability, but NEVER surface them in report_markdown or "
        "markdown_body text — see rule 12.\n"
        "2) If a claim is weak or unsupported, lower confidence and say so in limitations.\n"
        "3) Write `report_markdown` as readable Chinese Markdown sections, "
        "not as a schema dump.\n"
        "4) Preserve the requested draft_version.\n"
        "5) Group claims by dimension / claim family where possible.\n"
        "6) Conclusive claims should be evidence-backed; low-diversity or "
        "caveat-heavy claims must be phrased as conditional.\n"
        "7) Do not introduce fields beyond the schema.\n"
        "8) The draft should usually feel like a real deep-research report, including "
        "some of these functions when relevant: Executive Summary, Method/Scope, "
        "dimension chapters, Risks/Uncertainty, and Next Steps.\n"
        "9) Prefer analytical prose over bullet-only output; bullets may be used "
        "inside a section, but the whole report should remain readable as a memo.\n"
        "10) Multiple claims should normally map to multiple paragraphs or sections; "
        "do not merge everything into one coarse conclusion.\n"
        "11) Keep the JSON compact and valid. Do not output trailing commas, comments, "
        "or prose outside the JSON object.\n"
        "12) **绝对禁止在 `report_markdown` / `markdown_body` / 段落 `text` 中出现内部标识符**："
        "如 claim_id（claim_policy_primary）、evidence_id（ev_atomic_src_005_0）、"
        "obligation_id（obl_statistics_data）、paragraph_id（p_001）、source_id、level_2 "
        "等变量名/内部 ID 一律不得出现在用户可见的报告正文里。需要引用证据时，用可读的"
        "来源描述（如“根据新华网2026年报道”“依据《政府工作报告》”），不要用 [ev_xxx] "
        "或 [claim_xxx] 形式的 ID 标注。\n"
        "Suggested section strategy:\n"
        "- Executive Summary: summarize the main supported conclusions and caveats.\n"
        "- Method And Scope: explain what source families and evidence scope were used.\n"
        "- Dimension Sections: organize by policy / disclosure / local rollout / "
        "procurement / statistics / risk when relevant.\n"
        "- Uncertainty And Next Steps: explain what remains unverified.\n"
        f"Draft version: {draft_version}\n"
        f"Original query:\n{query}\n"
        "Claim summary:\n"
        f"{json.dumps(claim_summary, ensure_ascii=False, indent=2)}\n"
        "Compact evidence bundle:\n"
        f"{json.dumps(_compact_evidence_bundle(evidence_bundle), ensure_ascii=False, indent=2)}\n"
        "Compact section outline:\n"
        f"{json.dumps(_compact_outline(outline), ensure_ascii=False, indent=2)}\n"
        "Recent prior drafts summary:\n"
        f"{json.dumps(prior_summary, ensure_ascii=False, indent=2)}"
    )
    return system_prompt, user_prompt


def build_editor2_review_prompts(
    *,
    query: str,
    plan: dict[str, Any],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    support_matrix: list[dict[str, Any]],
    latest_draft: dict[str, Any],
    review_focus: list[str] | None = None,
) -> tuple[str, str]:
    claim_summary = [
        {
            "claim_id": claim.get("claim_id"),
            "text": _truncate_text(claim.get("text"), limit=180),
            "supported": claim.get("supported"),
            "claim_family": claim.get("claim_family"),
            "required_source_family": claim.get("required_source_family"),
            "support_requirement": claim.get("support_requirement"),
            "evidence_ids": list(claim.get("evidence_ids", []))[:8],
        }
        for claim in claims[:16]
    ]
    evidence_summary = [
        {
            "evidence_id": item.get("evidence_id"),
            "summary": _truncate_text(item.get("summary"), limit=180),
            "support_strength": item.get("support_strength"),
            "specificity": item.get("specificity"),
            "limitations": [
                _truncate_text(value, limit=90)
                for value in list(item.get("limitations", []))[:3]
            ],
            "source_ids": list(item.get("source_ids") or [item.get("source_id")])[:4],
        }
        for item in evidence[:12]
    ]
    source_summary = [
        {
            "source_id": source.get("source_id"),
            "title": _truncate_text(source.get("title"), limit=120),
            "source_family": source.get("source_family"),
            "source_role": (source.get("source_quality_v2") or {}).get("source_role"),
            "usage_role": (source.get("source_quality_v2") or {}).get("usage_role"),
            "credibility_score": (source.get("source_quality_v2") or {}).get(
                "credibility_score"
            ),
        }
        for source in sources[:10]
    ]
    draft_summary = {
        "draft_id": latest_draft.get("draft_id"),
        "draft_version": latest_draft.get("draft_version"),
        "report_markdown": str(latest_draft.get("report_markdown") or "")[:1200],
        "sections": [
            {
                "section_id": section.get("section_id"),
                "title": section.get("title"),
                "section_role": section.get("section_role"),
                "argument_posture": section.get("argument_posture"),
                "markdown_body": str(section.get("markdown_body") or "")[:320],
                "claim_ids": [
                    claim_id
                    for paragraph in list(section.get("paragraphs", []))
                    if isinstance(paragraph, dict)
                    for claim_id in list(paragraph.get("claim_ids", []))
                ][:12],
            }
            for section in list(latest_draft.get("sections", []))[:6]
            if isinstance(section, dict)
        ],
    }
    system_prompt = (
        "You are Editor2, a senior review analyst and opponent reviewer in a "
        "production deep-research workflow. Return one strict JSON object only. "
        "Your job is not to rewrite the report directly. Your job is to identify "
        "research-quality issues in the current Editor1 Markdown draft, especially "
        "unsupported claims, source-family mismatch, section framing mismatch, "
        "overstated prose, missing caveats, missing dimension coverage, and weak "
        "reader-facing report structure. Use only the provided claims, evidence, "
        "support matrix, sources, and draft context. Do not invent claims, "
        "evidence_ids, or source facts. Review the draft like a real research "
        "opponent before publication, not like a generic QA linter."
    )
    user_prompt = (
        "Return JSON with top-level key `issues`.\n"
        "Each issue must include:\n"
        "- issue_id\n"
        "- severity\n"
        "- issue_type\n"
        "- target_claim_id\n"
        "- description\n"
        "- required_fix\n"
        "- suggested_search_queries\n"
        "Rules:\n"
        "1) Use `blocker` only when evidence or source-family sufficiency is materially broken.\n"
        "2) Use `warning` for section framing, caveat, diversity, and presentation issues.\n"
        "3) Prefer concrete report-review language, not generic QA comments.\n"
        "4) If the problem is wording/placement, point toward revision rather "
        "than more search.\n"
        "5) If the problem is missing evidence, suggested queries should "
        "reflect the claim family.\n"
        "6) Do not emit duplicate issues for the same underlying problem.\n"
        "7) Review the draft as a readable report, not only as a claim table: "
        "flag when executive summary, section role, caveat placement, or "
        "dimension coverage would mislead a real reader.\n"
        "8) Prefer issue language that a senior analyst would give to a junior "
        "research writer, with clear required fixes.\n"
        f"Query:\n{query}\n"
        "Dimension plan:\n"
        f"{json.dumps(plan.get('dimension_plan', []), ensure_ascii=False, indent=2)}\n"
        "Review focus:\n"
        f"{json.dumps(review_focus or [], ensure_ascii=False, indent=2)}\n"
        "Claims:\n"
        f"{json.dumps(claim_summary, ensure_ascii=False, indent=2)}\n"
        "Evidence summary:\n"
        f"{json.dumps(evidence_summary, ensure_ascii=False, indent=2)}\n"
        "Support matrix summary:\n"
        f"{json.dumps(_compact_support_matrix_rows(support_matrix), ensure_ascii=False, indent=2)}\n"  # noqa: E501
        "Source summary:\n"
        f"{json.dumps(source_summary, ensure_ascii=False, indent=2)}\n"
        "Latest Editor1 draft summary:\n"
        f"{json.dumps(draft_summary, ensure_ascii=False, indent=2)}"
    )
    return system_prompt, user_prompt


def build_verifier_prompts(
    *,
    query: str,
    plan: dict[str, Any],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    support_matrix: list[dict[str, Any]],
    latest_draft: dict[str, Any],
    review_issues: list[dict[str, Any]],
) -> tuple[str, str]:
    claim_summary = [
        {
            "claim_id": claim.get("claim_id"),
            "text": _truncate_text(claim.get("text"), limit=180),
            "claim_family": claim.get("claim_family"),
            "required_source_family": claim.get("required_source_family"),
            "support_requirement": claim.get("support_requirement"),
            "evidence_ids": list(claim.get("evidence_ids", []))[:8],
        }
        for claim in claims[:12]
    ]
    evidence_summary = [
        {
            "evidence_id": item.get("evidence_id"),
            "summary": _truncate_text(item.get("summary"), limit=180),
            "support_strength": item.get("support_strength"),
            "specificity": item.get("specificity"),
            "limitations": [
                _truncate_text(value, limit=90)
                for value in list(item.get("limitations", []))[:3]
            ],
            "source_ids": list(item.get("source_ids") or [item.get("source_id")])[:4],
        }
        for item in evidence[:12]
    ]
    source_summary = [
        {
            "source_id": source.get("source_id"),
            "source_family": source.get("source_family"),
            "source_role": (source.get("source_quality_v2") or {}).get("source_role"),
            "usage_role": (source.get("source_quality_v2") or {}).get("usage_role"),
            "credibility_score": (source.get("source_quality_v2") or {}).get(
                "credibility_score"
            ),
        }
        for source in sources[:10]
    ]
    verifier_draft_summary = {
        "draft_id": latest_draft.get("draft_id"),
        "draft_version": latest_draft.get("draft_version"),
        "report_markdown": str(latest_draft.get("report_markdown") or "")[:1000],
        "section_count": len(list(latest_draft.get("sections", []))),
    }
    system_prompt = (
        "You are the Evidence Judge and verifier in a production deep-research "
        "workflow. Return one strict JSON object only. Verify whether each claim "
        "is supported, partially supported, unsupported, or contradicted, using "
        "the support matrix, evidence, source quality, review issues, and the "
        "current Editor1 draft framing. Do not invent new claims, evidence, or sources. "
        "Your job is to protect report quality and auditability: a readable report "
        "may still fail verification if the evidence is too weak, too narrow, or "
        "presented too conclusively."
    )
    user_prompt = (
        "Return JSON with top-level keys:\n"
        "- claim_verifications\n"
        "- quality_scores\n"
        "Each claim_verification must include:\n"
        "- claim_id\n"
        "- support_status\n"
        "- support_score\n"
        "- evidence_ids\n"
        "- source_ids\n"
        "- notes\n"
        "Rules:\n"
        "1) `support_status` must be one of supported / partially_supported / "
        "unsupported / contradicted.\n"
        "2) `notes` should explain missing support, source-family mismatch, "
        "weak source role, or report-body framing risk.\n"
        "3) `quality_scores` must include evidence_coverage, citation_integrity, "
        "source_quality, contradiction_resolution, and final_score.\n"
        "4) Do not flatten everything to one default score.\n"
        "5) The verifier should care both about support and whether the report "
        "body overstates the current evidence.\n"
        "6) Use meaningful score spread: different claims and final scores should "
        "reflect real differences in evidence quality, source diversity, and report framing.\n"
        "7) If a claim is only supportable as conditional or scope-limited, say so "
        "explicitly in notes instead of silently passing it.\n"
        f"Query:\n{query}\n"
        "Dimension plan:\n"
        f"{json.dumps(plan.get('dimension_plan', []), ensure_ascii=False, indent=2)}\n"
        "Claims:\n"
        f"{json.dumps(claim_summary, ensure_ascii=False, indent=2)}\n"
        "Evidence summary:\n"
        f"{json.dumps(evidence_summary, ensure_ascii=False, indent=2)}\n"
        "Support matrix summary:\n"
        f"{json.dumps(_compact_support_matrix_rows(support_matrix), ensure_ascii=False, indent=2)}\n"  # noqa: E501
        "Source summary:\n"
        f"{json.dumps(source_summary, ensure_ascii=False, indent=2)}\n"
        "Review issues:\n"
        f"{json.dumps(review_issues[:12], ensure_ascii=False, indent=2)}\n"
        "Latest Editor1 draft summary:\n"
        f"{json.dumps(verifier_draft_summary, ensure_ascii=False, indent=2)}"
    )
    return system_prompt, user_prompt
