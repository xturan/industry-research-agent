from __future__ import annotations

import hashlib
import json
from typing import Any

from packages.research_harness.prompt_assets import get_prompt_asset

CHROME_NOISE_MARKERS = (
    "[首页]",
    "打印",
    "收藏",
    "javascript:void(0)",
)

def sanitize_text(text: str) -> str:
    cleaned = text
    for noise in CHROME_NOISE_MARKERS:
        cleaned = cleaned.replace(noise, " ")
    return " ".join(cleaned.split())


def build_context_pack_summary(
    *,
    node_name: str,
    agent_name: str,
    state: dict[str, Any],
    state_before: dict[str, Any] | None = None,
    state_after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    asset = get_prompt_asset(
        node_name=node_name,
        strategy=str(state.get("strategy", "shadow_langgraph_v1")),
    )
    sources = list(state.get("sources", []))
    source_chunks = list(state.get("source_chunks", []))
    evidence = list(state.get("evidence", []))
    claims = list(state.get("claims", []))
    drafts = list(state.get("drafts", []))
    review_issues = list(state.get("review_issues", []))
    claim_verifications = list(state.get("claim_verifications", []))

    raw_chars = 0
    clean_chars = 0
    removed_markers: list[str] = []
    source_ids_with_clean_text: list[str] = []
    for source in sources:
        raw_text = str(source.get("raw_text", "") or "")
        clean_text = str(source.get("clean_text", "") or "")
        raw_chars += len(raw_text)
        clean_chars += len(clean_text)
        if clean_text:
            source_ids_with_clean_text.append(str(source.get("source_id", "")))
        for marker in CHROME_NOISE_MARKERS:
            if marker in raw_text and marker not in clean_text and marker not in removed_markers:
                removed_markers.append(marker)

    input_fingerprint = {
        "query": state.get("query"),
        "decision": state.get("decision"),
        "loop_count": state.get("loop_count", 0),
        "source_ids": [source.get("source_id") for source in sources],
        "evidence_ids": [item.get("evidence_id") for item in evidence],
        "claim_ids": [item.get("claim_id") for item in claims],
        "claim_verification_ids": [item.get("claim_id") for item in claim_verifications],
        "issue_ids": [item.get("issue_id") for item in review_issues],
        "chunk_ids": [item.get("chunk_id") for item in source_chunks],
    }
    input_hash = hashlib.sha256(
        json.dumps(input_fingerprint, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]

    included_fields = ["query"]
    if sources:
        included_fields.extend(["sources", "source_quality_v2"])
    if source_chunks:
        included_fields.append("source_chunks")
    if state.get("retrieval_pack"):
        included_fields.append("retrieval_pack")
    if evidence:
        included_fields.append("evidence")
    if claims:
        included_fields.append("claims")
    if claim_verifications:
        included_fields.append("claim_verifications")
    if drafts:
        included_fields.append("drafts")
    if review_issues:
        included_fields.append("review_issues")

    state_footprint_estimate = estimate_token_count(
        query=str(state.get("query", "")),
        sources=sources,
        evidence=evidence,
        claims=claims,
        drafts=drafts,
        source_chunks=source_chunks,
    )
    editor_meta = dict((state.get("contract_meta") or {}).get("editor1_draft") or {})
    actual_input_pack = dict(editor_meta.get("actual_input_pack") or {})
    has_actual_prompt_measurement = node_name == "editor1_draft" and bool(actual_input_pack)
    footprint_status, footprint_overage_tokens = _context_budget_status(
        token_estimate=state_footprint_estimate,
        context_budget_tokens=asset.context_budget_tokens,
    )
    if has_actual_prompt_measurement:
        prompt_estimate = int(actual_input_pack.get("prompt_estimated_tokens") or 0)
        budget_status = str(actual_input_pack.get("prompt_budget_status") or "unbudgeted")
        budget_overage_tokens = max(
            0,
            int(actual_input_pack.get("prompt_estimated_tokens") or prompt_estimate)
            - int(actual_input_pack.get("prompt_budget_limit") or asset.context_budget_tokens or 0),
        )
    else:
        # A state footprint is useful for memory/serialization diagnostics, but
        # it is not evidence that this node sent the same payload to an LLM.
        prompt_estimate = 0
        budget_status = "unbudgeted"
        budget_overage_tokens = 0

    return {
        "context_pack_id": f"ctx_{node_name}_{len(state.get('context_packs', [])) + 1}",
        "node_name": node_name,
        "agent_name": agent_name,
        "prompt_version": asset.prompt_version,
        "input_hash": input_hash,
        "included_source_ids": [source.get("source_id") for source in sources],
        "included_evidence_ids": [item.get("evidence_id") for item in evidence],
        "included_claim_ids": [item.get("claim_id") for item in claims],
        "included_issue_ids": [item.get("issue_id") for item in review_issues],
        "included_fields": included_fields,
        "context_budget_tokens": asset.context_budget_tokens,
        "tool_permissions": list(asset.tool_permissions),
        "fallback_usage_review": asset.fallback_usage_review,
        "live_validation_focus": list(asset.live_validation_focus),
        "failure_class_focus": list(asset.failure_class_focus),
        "token_estimate": prompt_estimate,
        "prompt_estimated_tokens": prompt_estimate,
        "state_footprint_estimated_tokens": state_footprint_estimate,
        "state_footprint_budget_status": footprint_status,
        "state_footprint_budget_overage_tokens": footprint_overage_tokens,
        "actual_prompt_measured": has_actual_prompt_measurement,
        "budget_status": budget_status,
        "budget_overage_tokens": budget_overage_tokens,
        "sanitization_summary": {
            "source_count": len(sources),
            "source_count_with_clean_text": len(source_ids_with_clean_text),
            "raw_text_chars": raw_chars,
            "clean_text_chars": clean_chars,
            "removed_markers": removed_markers,
            "removed_marker_count": len(removed_markers),
        },
        # ── Phase C: IO snapshot for dossier auditing ──
        "io_snapshot": _build_io_snapshot(state_before=state_before, state_after=state_after),
    }


def estimate_token_count(
    *,
    query: str,
    sources: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
    source_chunks: list[dict[str, Any]] | None = None,
) -> int:
    char_budget = len(query)
    char_budget += sum(
        len(str(item.get("clean_text", "") or item.get("raw_text", ""))) for item in sources
    )
    char_budget += sum(
        len(str(item.get("chunk_text", ""))) for item in list(source_chunks or [])
    )
    char_budget += sum(len(str(item.get("summary", ""))) for item in evidence)
    char_budget += sum(len(str(item.get("text", ""))) for item in claims)
    char_budget += sum(
        len(str(paragraph.get("text", "")))
        for draft in drafts
        for section in draft.get("sections", [])
        for paragraph in section.get("paragraphs", [])
    )
    return max(1, char_budget // 4)


def _context_budget_status(
    *,
    token_estimate: int,
    context_budget_tokens: int | None,
) -> tuple[str, int]:
    if context_budget_tokens is None:
        return "unbudgeted", 0
    overage = max(0, int(token_estimate) - int(context_budget_tokens))
    if overage:
        return "over_budget", overage
    return "within_budget", 0


# ── Phase C: IO snapshot helpers ──

_SENSITIVE_KEYS = frozenset(
    {"api_key", "token", "password", "secret", "authorization", "auth_token"}
)


def _build_io_snapshot(
    *,
    state_before: dict[str, Any] | None,
    state_after: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if state_before is None and state_after is None:
        return None
    snap: dict[str, Any] = {}
    if state_before is not None:
        snap["state_before_keys"] = sorted(state_before.keys())
        snap["state_before_summary"] = _state_summary(state_before)
    if state_after is not None:
        snap["state_after_keys"] = sorted(state_after.keys())
        snap["state_after_summary"] = _state_summary(state_after)
    return snap


def _state_summary(state: dict[str, Any]) -> dict[str, str]:
    summary: dict[str, str] = {}
    for key, value in state.items():
        if key.startswith("_"):
            continue
        if isinstance(value, list):
            summary[key] = f"list[{len(value)}]"
        elif isinstance(value, dict):
            summary[key] = f"dict[{len(value)} keys]"
        elif isinstance(value, str):
            summary[key] = value[:100] if len(value) > 100 else value
        elif isinstance(value, (int, float, bool)):
            summary[key] = str(value)
        elif value is None:
            summary[key] = "null"
        else:
            summary[key] = type(value).__name__
    return summary


def _sanitize_state(state: dict[str, Any], max_depth: int = 4) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in state.items():
        if key.startswith("_"):
            continue
        key_lower = key.lower()
        if any(sk in key_lower for sk in _SENSITIVE_KEYS):
            cleaned[key] = "[FILTERED]"
        elif isinstance(value, dict):
            if max_depth <= 0:
                cleaned[key] = f"[dict: {len(value)} keys]"
            else:
                cleaned[key] = _sanitize_state(value, max_depth - 1)
        elif isinstance(value, list):
            if max_depth <= 0:
                cleaned[key] = f"[list: {len(value)} items]"
            else:
                cleaned[key] = [
                    _sanitize_state(v, max_depth - 1) if isinstance(v, dict) else v
                    for v in value[:20]
                ]
        elif isinstance(value, str) and len(value) > 2000:
            cleaned[key] = value[:2000] + "...[TRUNCATED]"
        else:
            cleaned[key] = value
    return cleaned
