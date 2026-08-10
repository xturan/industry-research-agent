from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy.orm import Session

from packages.db.models import (
    ResearchGraphClaimEvidenceLink,
    ResearchGraphClaimRecord,
    ResearchGraphClaimVerificationRecord,
    ResearchGraphDraftVersionRecord,
    ResearchGraphEvidenceRecord,
    ResearchGraphQualityGateResult,
    ResearchGraphReviewIssueRecord,
    ResearchGraphSourceRecord,
)

RecordT = TypeVar("RecordT")


class GraphBusinessRecordRepository:
    """Persist queryable graph-v1 business records derived from graph state."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def persist_state(self, state: dict[str, Any]) -> None:
        run_id = int(state["run_id"])
        self._persist_sources(run_id, list(state.get("sources", [])))
        self._persist_evidence(run_id, list(state.get("evidence", [])))
        self._persist_claims(run_id, list(state.get("claims", [])))
        self._persist_claim_evidence_links(run_id, list(state.get("claims", [])))
        self._persist_claim_verifications(
            run_id,
            list(state.get("claim_verifications", [])),
        )
        self._persist_drafts(run_id, list(state.get("drafts", [])))
        self._persist_review_issues(run_id, list(state.get("review_issues", [])))
        self._persist_gate_result(run_id, state)
        self.session.commit()

    def load_run_records(self, run_id: int) -> dict[str, list[dict[str, Any]]]:
        return {
            "sources": [
                self._source_payload(row)
                for row in self.session.query(ResearchGraphSourceRecord)
                .filter_by(run_id=run_id)
                .order_by(ResearchGraphSourceRecord.source_id)
                .all()
            ],
            "evidence": [
                self._evidence_payload(row)
                for row in self.session.query(ResearchGraphEvidenceRecord)
                .filter_by(run_id=run_id)
                .order_by(ResearchGraphEvidenceRecord.evidence_id)
                .all()
            ],
            "claims": [
                self._claim_payload(row)
                for row in self.session.query(ResearchGraphClaimRecord)
                .filter_by(run_id=run_id)
                .order_by(ResearchGraphClaimRecord.claim_id)
                .all()
            ],
            "claim_evidence_links": [
                self._claim_evidence_link_payload(row)
                for row in self.session.query(ResearchGraphClaimEvidenceLink)
                .filter_by(run_id=run_id)
                .order_by(
                    ResearchGraphClaimEvidenceLink.claim_id,
                    ResearchGraphClaimEvidenceLink.evidence_id,
                )
                .all()
            ],
            "claim_verifications": [
                self._claim_verification_payload(row)
                for row in self.session.query(ResearchGraphClaimVerificationRecord)
                .filter_by(run_id=run_id)
                .order_by(ResearchGraphClaimVerificationRecord.claim_id)
                .all()
            ],
            "draft_versions": [
                self._draft_payload(row)
                for row in self.session.query(ResearchGraphDraftVersionRecord)
                .filter_by(run_id=run_id)
                .order_by(ResearchGraphDraftVersionRecord.draft_version)
                .all()
            ],
            "review_issues": [
                self._review_issue_payload(row)
                for row in self.session.query(ResearchGraphReviewIssueRecord)
                .filter_by(run_id=run_id)
                .order_by(ResearchGraphReviewIssueRecord.issue_id)
                .all()
            ],
            "quality_gate_results": [
                self._quality_gate_payload(row)
                for row in self.session.query(ResearchGraphQualityGateResult)
                .filter_by(run_id=run_id)
                .order_by(ResearchGraphQualityGateResult.gate_id)
                .all()
            ],
        }

    def record_counts(self, run_id: int) -> dict[str, int]:
        return {
            key: len(value)
            for key, value in self.load_run_records(run_id).items()
        }

    def build_claim_support_matrix(self, run_id: int) -> list[dict[str, Any]]:
        records = self.load_run_records(run_id)
        evidence_by_id = {
            str(item.get("evidence_id")): item for item in records["evidence"]
        }
        source_by_id = {
            str(item.get("source_id")): item for item in records["sources"]
        }
        verification_by_claim_id = {
            str(item.get("claim_id")): item for item in records["claim_verifications"]
        }
        matrix = []
        for claim in records["claims"]:
            evidence_ids = [str(item) for item in claim.get("evidence_ids", [])]
            evidence_rows = [
                evidence_by_id[evidence_id]
                for evidence_id in evidence_ids
                if evidence_id in evidence_by_id
            ]
            source_ids = _dedupe_text(
                item.get("source_id") for item in evidence_rows if item.get("source_id")
            )
            source_rows = [
                source_by_id[source_id] for source_id in source_ids if source_id in source_by_id
            ]
            required_family = str(claim.get("required_source_family") or "")
            family_matched = (
                not required_family
                or any(
                    _source_matches_required_family(source, required_family)
                    for source in source_rows
                )
            )
            strengths = [
                float(item["support_strength"])
                for item in evidence_rows
                if item.get("support_strength") is not None
            ]
            verification = verification_by_claim_id.get(str(claim.get("claim_id")), {})
            matrix.append(
                {
                    "claim_id": claim.get("claim_id"),
                    "required_source_family": required_family or None,
                    "support_requirement": claim.get("support_requirement"),
                    "evidence_ids": evidence_ids,
                    "source_ids": source_ids,
                    "support_status": verification.get("support_status"),
                    "support_score": verification.get("support_score"),
                    "evidence_count": len(evidence_rows),
                    "source_count": len(source_rows),
                    "family_matched": family_matched,
                    "avg_support_strength": (
                        round(sum(strengths) / len(strengths), 3) if strengths else 0.0
                    ),
                    "evidence_specificities": _dedupe_text(
                        item.get("specificity") for item in evidence_rows
                    ),
                    "source_families": _dedupe_text(
                        item.get("source_family") for item in source_rows
                    ),
                    "usage_roles": _dedupe_text(
                        item.get("usage_role") for item in source_rows
                    ),
                }
            )
        return matrix

    def _persist_sources(self, run_id: int, sources: list[dict[str, Any]]) -> None:
        for source in sources:
            source_id = _required_text(source, "source_id")
            quality = _dict(source.get("source_quality_v2"))
            row = self._upsert(
                ResearchGraphSourceRecord,
                run_id=run_id,
                key_name="source_id",
                key_value=source_id,
            )
            row.url = str(source.get("url") or "")
            row.domain = _optional_text(source.get("domain"))
            row.title = _optional_text(source.get("title"))
            row.source_family = _optional_text(source.get("source_family"))
            row.source_tier = _optional_text(source.get("source_tier") or quality.get("tier"))
            row.source_role = _optional_text(quality.get("source_role"))
            row.usage_role = _optional_text(quality.get("usage_role"))
            row.search_phrase = _optional_text(source.get("search_phrase"))
            row.discovered_by_phrase = _optional_text(source.get("discovered_by_phrase"))
            row.published_date = _optional_text(source.get("published_date"))
            row.search_score = _float_or_none(source.get("search_score"))
            row.raw_text_meta_json = _dict_or_none(source.get("raw_text_meta"))
            row.source_quality_json = quality or None
            row.payload_json = dict(source)
            self.session.add(row)

    def _persist_evidence(self, run_id: int, evidence: list[dict[str, Any]]) -> None:
        for item in evidence:
            evidence_id = _required_text(item, "evidence_id")
            row = self._upsert(
                ResearchGraphEvidenceRecord,
                run_id=run_id,
                key_name="evidence_id",
                key_value=evidence_id,
            )
            row.source_id = _optional_text(item.get("source_id"))
            row.source_url = _optional_text(item.get("source_url"))
            row.support_type = _optional_text(item.get("support_type"))
            row.support_strength = _float_or_none(item.get("support_strength"))
            row.specificity = _optional_text(item.get("specificity"))
            row.evaluator_mode = _optional_text(item.get("evaluator_mode"))
            row.summary = _optional_text(item.get("summary"))
            row.limitations_json = _list_or_none(item.get("limitations"))
            row.payload_json = dict(item)
            self.session.add(row)

    def _persist_claims(self, run_id: int, claims: list[dict[str, Any]]) -> None:
        for claim in claims:
            claim_id = _required_text(claim, "claim_id")
            row = self._upsert(
                ResearchGraphClaimRecord,
                run_id=run_id,
                key_name="claim_id",
                key_value=claim_id,
            )
            row.text = str(claim.get("text") or "")
            row.supported = _bool_or_none(claim.get("supported"))
            row.required_source_family = _optional_text(claim.get("required_source_family"))
            row.support_requirement = _optional_text(claim.get("support_requirement"))
            row.evidence_ids_json = _list_or_none(claim.get("evidence_ids"))
            row.payload_json = dict(claim)
            self.session.add(row)

    def _persist_claim_evidence_links(
        self,
        run_id: int,
        claims: list[dict[str, Any]],
    ) -> None:
        self.session.query(ResearchGraphClaimEvidenceLink).filter_by(run_id=run_id).delete(
            synchronize_session="fetch"
        )
        for claim in claims:
            claim_id = _required_text(claim, "claim_id")
            for evidence_id in _list_or_empty(claim.get("evidence_ids")):
                row = ResearchGraphClaimEvidenceLink(
                    run_id=run_id,
                    claim_id=claim_id,
                    evidence_id=str(evidence_id),
                    link_type="declared_support",
                    payload_json={"source": "claim.evidence_ids"},
                )
                self.session.add(row)

    def _persist_claim_verifications(
        self,
        run_id: int,
        verifications: list[dict[str, Any]],
    ) -> None:
        for item in verifications:
            claim_id = _required_text(item, "claim_id")
            row = self._upsert(
                ResearchGraphClaimVerificationRecord,
                run_id=run_id,
                key_name="claim_id",
                key_value=claim_id,
            )
            row.support_status = str(item.get("support_status") or "unsupported")
            row.support_score = _float_or_none(item.get("support_score"))
            row.evidence_ids_json = _list_or_none(item.get("evidence_ids"))
            row.source_ids_json = _list_or_none(item.get("source_ids"))
            row.notes_json = _list_or_none(item.get("notes"))
            row.payload_json = dict(item)
            self.session.add(row)

    def _persist_drafts(self, run_id: int, drafts: list[dict[str, Any]]) -> None:
        for draft in drafts:
            draft_id = _required_text(draft, "draft_id")
            row = self._upsert(
                ResearchGraphDraftVersionRecord,
                run_id=run_id,
                key_name="draft_id",
                key_value=draft_id,
            )
            row.draft_version = int(draft.get("draft_version") or 1)
            row.payload_json = dict(draft)
            self.session.add(row)

    def _persist_review_issues(self, run_id: int, issues: list[dict[str, Any]]) -> None:
        for issue in issues:
            issue_id = _required_text(issue, "issue_id")
            row = self._upsert(
                ResearchGraphReviewIssueRecord,
                run_id=run_id,
                key_name="issue_id",
                key_value=issue_id,
            )
            row.severity = str(issue.get("severity") or "warning")
            row.issue_type = str(issue.get("issue_type") or "unknown")
            row.target_claim_id = _optional_text(issue.get("target_claim_id"))
            row.payload_json = dict(issue)
            self.session.add(row)

    def _persist_gate_result(self, run_id: int, state: dict[str, Any]) -> None:
        if state.get("decision") is None:
            return
        row = self._upsert(
            ResearchGraphQualityGateResult,
            run_id=run_id,
            key_name="gate_id",
            key_value="latest",
        )
        row.decision = _optional_text(state.get("decision"))
        row.route_to = _optional_text(state.get("gate_route_to"))
        row.reason = _optional_text(state.get("gate_reason"))
        row.quality_scores_json = _dict_or_none(state.get("quality_scores"))
        row.required_actions_json = _list_or_none(state.get("required_actions"))
        row.payload_json = {
            "decision": state.get("decision"),
            "route_to": state.get("gate_route_to"),
            "reason": state.get("gate_reason"),
            "quality_scores": state.get("quality_scores", {}),
            "required_actions": state.get("required_actions", []),
            "loop_count": state.get("loop_count", 0),
        }
        self.session.add(row)

    def _upsert(
        self,
        model: type[RecordT],
        *,
        run_id: int,
        key_name: str,
        key_value: str,
    ) -> RecordT:
        # 幂等 upsert：先 flush 让同 session 已 add 的 pending 行落库（autoflush=False
        # 下 query 查不到 pending 新行，会再 add 一条 → commit 撞唯一约束/历史重复）。
        # 再用 .first() 复用已有行（历史可能有重复，one_or_none 会抛 MultipleResultsFound）。
        # flush 不主动 rollback：若 flush 因唯一冲突失败，由 persist_state 外层处理。
        self.session.flush()
        row = (
            self.session.query(model)
            .filter_by(run_id=run_id, **{key_name: key_value})
            .first()
        )
        if row is not None:
            return row
        return model(run_id=run_id, **{key_name: key_value})  # type: ignore[call-arg]

    def _source_payload(self, row: ResearchGraphSourceRecord) -> dict[str, Any]:
        return {
            "source_id": row.source_id,
            "url": row.url,
            "domain": row.domain,
            "title": row.title,
            "source_family": row.source_family,
            "source_tier": row.source_tier,
            "source_role": row.source_role,
            "usage_role": row.usage_role,
            "search_phrase": row.search_phrase,
            "discovered_by_phrase": row.discovered_by_phrase,
            "published_date": row.published_date,
            "search_score": row.search_score,
            "payload": row.payload_json,
        }

    def _evidence_payload(self, row: ResearchGraphEvidenceRecord) -> dict[str, Any]:
        return {
            "evidence_id": row.evidence_id,
            "source_id": row.source_id,
            "support_type": row.support_type,
            "support_strength": row.support_strength,
            "specificity": row.specificity,
            "summary": row.summary,
            "payload": row.payload_json,
        }

    def _claim_payload(self, row: ResearchGraphClaimRecord) -> dict[str, Any]:
        return {
            "claim_id": row.claim_id,
            "text": row.text,
            "supported": row.supported,
            "required_source_family": row.required_source_family,
            "support_requirement": row.support_requirement,
            "evidence_ids": row.evidence_ids_json or [],
            "payload": row.payload_json,
        }

    def _claim_evidence_link_payload(
        self,
        row: ResearchGraphClaimEvidenceLink,
    ) -> dict[str, Any]:
        return {
            "claim_id": row.claim_id,
            "evidence_id": row.evidence_id,
            "link_type": row.link_type,
        }

    def _claim_verification_payload(
        self,
        row: ResearchGraphClaimVerificationRecord,
    ) -> dict[str, Any]:
        return {
            "claim_id": row.claim_id,
            "support_status": row.support_status,
            "support_score": row.support_score,
            "evidence_ids": row.evidence_ids_json or [],
            "source_ids": row.source_ids_json or [],
            "notes": row.notes_json or [],
            "payload": row.payload_json,
        }

    def _draft_payload(self, row: ResearchGraphDraftVersionRecord) -> dict[str, Any]:
        return {
            "draft_id": row.draft_id,
            "draft_version": row.draft_version,
            "payload": row.payload_json,
        }

    def _review_issue_payload(self, row: ResearchGraphReviewIssueRecord) -> dict[str, Any]:
        return {
            "issue_id": row.issue_id,
            "severity": row.severity,
            "issue_type": row.issue_type,
            "target_claim_id": row.target_claim_id,
            "payload": row.payload_json,
        }

    def _quality_gate_payload(self, row: ResearchGraphQualityGateResult) -> dict[str, Any]:
        return {
            "gate_id": row.gate_id,
            "decision": row.decision,
            "route_to": row.route_to,
            "reason": row.reason,
            "quality_scores": row.quality_scores_json or {},
            "required_actions": row.required_actions_json or [],
            "payload": row.payload_json,
        }


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"Graph business record missing required key: {key}")
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def _list_or_none(value: Any) -> list[Any] | None:
    return list(value) if isinstance(value, list) else None


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _dedupe_text(values: Any) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return output


def _source_matches_required_family(
    source: dict[str, Any],
    required_family: str,
) -> bool:
    source_family = str(source.get("source_family") or "")
    if source_family == required_family:
        return True
    quality = _dict(source.get("payload", {}).get("source_quality_v2"))
    role = str(source.get("source_role") or quality.get("source_role") or "")
    if required_family in {"tender_procurement", "public_resource_transaction"}:
        return (
            source_family in {"tender_procurement", "public_resource_transaction", "procurement"}
            or role in {"public_resource_transaction", "procurement_award"}
        )
    if required_family in {"policy_document", "official_policy"}:
        return (
            source_family in {"policy_document", "official_policy", "policy"}
            or role in {"official_policy", "policy_document"}
        )
    return False
