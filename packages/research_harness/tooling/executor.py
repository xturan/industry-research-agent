from __future__ import annotations

from typing import Any


def _safe_limitations_list(value: Any) -> list[str]:
    """Return limitations as a list of strings, guarding against character-splitting.

    When a string is passed (e.g. model outputs a sentence), wrapping it in a
    single-element list prevents `list(\"政策为内蒙古\")` → `[\"政\",\"策\",...]`.
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item]
    return []


class ToolExecutor:
    def execute(
        self,
        *,
        tool_name: str,
        args: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        method = getattr(self, f"_tool_{tool_name}", None)
        if method is None:
            raise ValueError(f"Unknown tool: {tool_name}")
        return method(args=args, state=state)

    def _tool_get_evidence_bundle(
        self,
        *,
        args: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        claim_ids = {str(item) for item in list(args.get("claim_ids", [])) if str(item).strip()}
        claims = list(state.get("claims", []))
        evidence = list(state.get("evidence", []))
        evidence_map = {str(item.get("evidence_id")): item for item in evidence}
        source_map = {
            str(item.get("source_id")): item for item in list(state.get("sources", []))
        }
        selected_claims = [
            claim for claim in claims if not claim_ids or str(claim.get("claim_id")) in claim_ids
        ]
        selected_evidence_ids: list[str] = []
        for claim in selected_claims:
            selected_evidence_ids.extend(str(item) for item in claim.get("evidence_ids", []))
        deduped_ids = []
        for evidence_id in selected_evidence_ids:
            if evidence_id and evidence_id not in deduped_ids:
                deduped_ids.append(evidence_id)
        items = []
        for evidence_id in deduped_ids:
            evidence_item = evidence_map.get(evidence_id)
            if evidence_item is None:
                continue
            source = source_map.get(str(evidence_item.get("source_id")))
            items.append(
                {
                    "evidence_id": evidence_item.get("evidence_id"),
                    "claim_ids": [
                        str(claim.get("claim_id"))
                        for claim in selected_claims
                        if evidence_id in [str(item) for item in claim.get("evidence_ids", [])]
                    ],
                    "summary": evidence_item.get("summary", ""),
                    "support_type": evidence_item.get("support_type", ""),
                    "support_strength": evidence_item.get("support_strength", 0.0),
                    "specificity": evidence_item.get("specificity", ""),
                    "source_ids": list(evidence_item.get("source_ids", []))[:6],
                    "chunk_ids": list(evidence_item.get("chunk_ids", []))[:10],
                    "evaluator_mode": evidence_item.get("evaluator_mode", ""),
                    "limitations": _safe_limitations_list(
                        evidence_item.get("limitations", [])
                    )[:6],
                    "source": {
                        "source_id": source.get("source_id") if source else None,
                        "title": source.get("title") if source else "",
                        "url": source.get("url") if source else "",
                        "source_family": source.get("source_family") if source else "",
                        "source_tier": source.get("source_tier") if source else "",
                    },
                }
            )
        return {
            "claim_count": len(selected_claims),
            "evidence_count": len(items),
            "items": items,
        }

    def _tool_get_claim_support_matrix(
        self,
        *,
        args: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        claim_ids = {str(item) for item in list(args.get("claim_ids", [])) if str(item).strip()}
        rows = [
            dict(item)
            for item in list(state.get("claim_support_matrix", []))
            if not claim_ids or str(item.get("claim_id")) in claim_ids
        ]
        return {
            "row_count": len(rows),
            "rows": rows,
        }

    def _tool_get_source_bundle(
        self,
        *,
        args: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        source_ids = {str(item) for item in list(args.get("source_ids", [])) if str(item).strip()}
        source_families = {
            str(item) for item in list(args.get("source_families", [])) if str(item).strip()
        }
        rows = []
        for source in list(state.get("sources", [])):
            if source_ids and str(source.get("source_id")) not in source_ids:
                continue
            if source_families and str(source.get("source_family")) not in source_families:
                continue
            quality = dict(source.get("source_quality_v2") or {})
            rows.append(
                {
                    "source_id": source.get("source_id"),
                    "title": source.get("title", ""),
                    "url": source.get("url", ""),
                    "domain": source.get("domain", ""),
                    "source_family": source.get("source_family", ""),
                    "source_tier": source.get("source_tier", ""),
                    "published_date": source.get("published_date", ""),
                    "search_phrase": source.get("search_phrase", ""),
                    "quality": {
                        "credibility_score": quality.get("credibility_score"),
                        "source_role": quality.get("source_role"),
                        "usage_role": quality.get("usage_role"),
                        "query_relevance": quality.get("query_relevance"),
                    },
                }
            )
        return {
            "source_count": len(rows),
            "items": rows,
        }

    def _tool_request_replan(
        self,
        *,
        args: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        claim_ids = [str(item) for item in list(args.get("focus_claim_ids", [])) if str(item).strip()]
        return {
            "proposal": {
                "reason": "llm_requested_replan",
                "focus_claim_ids": claim_ids,
                "note": str(args.get("note") or ""),
                "existing_gate_reason": str(state.get("gate_reason") or ""),
                "required_actions": list(state.get("required_actions", []))[:8],
            }
        }

    def _tool_request_revision(
        self,
        *,
        args: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        claim_ids = [str(item) for item in list(args.get("target_claim_ids", [])) if str(item).strip()]
        related_issues = [
            dict(issue)
            for issue in list(state.get("review_issues", []))
            if not claim_ids or str(issue.get("target_claim_id")) in claim_ids
        ]
        return {
            "proposal": {
                "target_claim_ids": claim_ids,
                "note": str(args.get("note") or ""),
                "issue_count": len(related_issues),
                "issues": related_issues[:8],
            }
        }

    _FAMILY_SECTION_TITLES: dict[str, str] = {
        "policy_basis": "政策依据",
        "local_rollout": "地方政策落地",
        "execution_evidence": "项目执行证据",
        "company_disclosure": "企业披露",
        "statistics_or_data": "行业数据",
        "risk_assessment": "风险与不确定性",
    }

    def _tool_compose_section_outline(
        self,
        *,
        args: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        claim_ids = {str(item) for item in list(args.get("claim_ids", [])) if str(item).strip()}
        claims = [
            claim
            for claim in list(state.get("claims", []))
            if not claim_ids or str(claim.get("claim_id")) in claim_ids
        ]
        # ── Group claims by claim_family for dimension-based sections ──
        family_groups: dict[str, list[dict[str, Any]]] = {}
        for claim in claims:
            family = str(claim.get("claim_family", "") or "other")
            family_groups.setdefault(family, []).append(claim)

        sections = []
        for family, group_claims in family_groups.items():
            title = self._FAMILY_SECTION_TITLES.get(family, family.replace("_", " ").title())
            sections.append({
                "section_id": f"sec_{family}",
                "title": title,
                "section_role": "dimension_chapter",
                "claim_ids": [str(c.get("claim_id")) for c in group_claims],
                "claim_family": family,
                "claim_count": len(group_claims),
            })

        # If only one family group, still create a meaningful outline
        if len(sections) <= 1 and claims:
            sections.append({
                "section_id": "sec_summary",
                "title": "执行摘要",
                "section_role": "executive_summary",
                "claim_ids": [str(c.get("claim_id")) for c in claims],
                "claim_family": "summary",
                "claim_count": len(claims),
            })

        return {
            "section_count": len(sections),
            "sections": sections,
        }

    def _tool_compose_final_report(
        self,
        *,
        args: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        _ = args
        claims = list(state.get("claims", []))
        evidence = list(state.get("evidence", []))
        quality_scores = dict(state.get("quality_scores", {}))
        review_issues = list(state.get("review_issues", []))
        return {
            "query": state.get("query", ""),
            "decision": state.get("decision"),
            "quality_scores": quality_scores,
            "claim_briefs": [
                {
                    "claim_id": claim.get("claim_id"),
                    "text": claim.get("text"),
                    "supported": claim.get("supported"),
                    "claim_family": claim.get("claim_family"),
                    "required_source_family": claim.get("required_source_family"),
                    "support_requirement": claim.get("support_requirement"),
                    "evidence_count": len(claim.get("evidence_ids", [])),
                }
                for claim in claims[:10]
            ],
            "evidence_count": len(evidence),
            "issue_count": len(review_issues),
        }
