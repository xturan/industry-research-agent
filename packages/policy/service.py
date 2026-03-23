from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from packages.agents.schemas import ResearchAnalysisResult
from packages.db.models import ContentAsset
from packages.policy.schemas import DeliveryPolicyResult, PolicyIssue, PolicyReport

FORBIDDEN_RECOMMENDATION_PHRASES = (
    "strong buy",
    "buy now",
    "sell now",
    "buy recommendation",
    "sell recommendation",
    "立即买入",
    "立即卖出",
    "买入建议",
    "卖出建议",
)

DISCLAIMER_MARKERS = (
    "not investment advice",
    "does not constitute investment advice",
    "research only",
    "仅用于研究",
    "不构成投资建议",
    "鍏嶈矗澹版槑",
    "涓嶆瀯鎴愪换浣曡瘉鍒镐拱鍗栧缓璁垨鎶曡祫鎵胯",
)


class PolicyChecker:
    # TODO: Extend with policy packs and account-level policy overrides.
    # TODO: Add policy severity calibration from eval benchmark data.

    def check_content_text(
        self,
        *,
        title: str | None,
        body: str | None,
        disclaimers: Iterable[str] | None = None,
    ) -> PolicyReport:
        issues: list[PolicyIssue] = []
        joined_text = " ".join(filter(None, [title or "", body or ""]))
        text_l = joined_text.lower()

        for phrase in FORBIDDEN_RECOMMENDATION_PHRASES:
            if phrase in text_l:
                issues.append(
                    PolicyIssue(
                        code="forbidden_recommendation_phrase",
                        severity="high",
                        message=f"Found forbidden phrase: {phrase}",
                        location="body",
                    )
                )

        has_disclaimer = False
        disclaimer_text = " ".join(disclaimers or [])
        check_text = f"{joined_text} {disclaimer_text}".lower()
        for marker in DISCLAIMER_MARKERS:
            if marker in check_text:
                has_disclaimer = True
                break
        if not has_disclaimer:
            issues.append(
                PolicyIssue(
                    code="missing_disclaimer",
                    severity="medium",
                    message="Content is missing required disclaimer language.",
                    location="body",
                )
            )

        return PolicyReport(passed=not issues, issues=issues)

    def check_research_result(self, result: ResearchAnalysisResult) -> PolicyReport:
        issues: list[PolicyIssue] = []
        for thesis in result.theses:
            if not thesis.evidence_refs and not thesis.evidence_chunk_ids:
                issues.append(
                    PolicyIssue(
                        code="missing_thesis_evidence_refs",
                        severity="high",
                        message=f"Thesis {thesis.thesis_id} has no evidence refs.",
                        location="theses",
                    )
                )
        if result.insufficient_evidence and result.confidence_score > 0.45:
            issues.append(
                PolicyIssue(
                    code="insufficient_evidence_high_confidence",
                    severity="high",
                    message="insufficient_evidence flow should not return high confidence.",
                    location="final_memo",
                )
            )
        if result.insufficient_evidence and result.theses:
            issues.append(
                PolicyIssue(
                    code="insufficient_evidence_has_theses",
                    severity="medium",
                    message="insufficient_evidence flow should avoid strong thesis claims.",
                    location="theses",
                )
            )

        return PolicyReport(passed=not issues, issues=issues)

    def check_research_result_payload(self, payload: dict[str, Any]) -> PolicyReport:
        result = ResearchAnalysisResult.model_validate(payload)
        return self.check_research_result(result)

    def check_content_asset(self, asset: ContentAsset | dict[str, Any]) -> PolicyReport:
        if isinstance(asset, ContentAsset):
            meta_json = asset.meta_json if isinstance(asset.meta_json, dict) else {}
            disclaimers = meta_json.get("disclaimers")
            disclaimer_list = disclaimers if isinstance(disclaimers, list) else []
            return self.check_content_text(
                title=asset.title,
                body=asset.body_markdown,
                disclaimers=[str(item) for item in disclaimer_list],
            )

        meta_json = asset.get("meta_json") if isinstance(asset.get("meta_json"), dict) else {}
        disclaimers = meta_json.get("disclaimers")
        disclaimer_list = disclaimers if isinstance(disclaimers, list) else []
        return self.check_content_text(
            title=str(asset.get("title") or ""),
            body=str(asset.get("body_markdown") or ""),
            disclaimers=[str(item) for item in disclaimer_list],
        )

    def check_delivery_assets(self, assets: list[ContentAsset]) -> DeliveryPolicyResult:
        reports: dict[int, PolicyReport] = {}
        blocked_asset_ids: list[int] = []
        for asset in assets:
            report = self.check_content_asset(asset)
            reports[asset.id] = report
            if not report.passed:
                blocked_asset_ids.append(asset.id)
        return DeliveryPolicyResult(
            passed=not blocked_asset_ids,
            blocked_asset_ids=blocked_asset_ids,
            asset_reports=reports,
        )
