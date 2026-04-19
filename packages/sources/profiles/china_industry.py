from __future__ import annotations

from packages.sources.enums import (
    AccessMethod,
    CollectorType,
    PaginationMode,
    SourceCategory,
    TrustTier,
)
from packages.sources.schemas import SourceAccess, SourceCapabilities, SourceProfile


def build_cn_industry_association_generic_profile(*, enabled: bool = False) -> SourceProfile:
    return SourceProfile(
        source_id="cn_industry_association_generic",
        display_name="China Industry Association Generic",
        category=SourceCategory.INDUSTRY_ASSOCIATION,
        trust_tier=TrustTier.SECONDARY_INSTITUTIONAL,
        enabled=enabled,
        description=(
            "Generic domestic industry-association or institute collector family "
            "for reports/notices."
        ),
        access=SourceAccess(
            access_method=AccessMethod.WEB,
            auth_required=False,
            base_url="https://example.cn/industry",
        ),
        capabilities=SourceCapabilities(
            supports_search=True,
            supports_document_detail=True,
            supports_evidence_extraction=True,
            supports_time_filter=True,
            supports_keyword_filter=True,
            supports_bulk=True,
        ),
        priority_hint=68,
        tags=["china", "industry", "association", "report", "pdf"],
        profile_family="china_industry",
        collector_type=CollectorType.HTML_LIST_DETAIL,
        entry_urls=["https://example.cn/industry/notices"],
        selectors={
            "list_item": ".report-item, .notice-item, li",
            "list_item_link": "a[href]",
            "list_item_date": ".date, .publish-date, time",
            "list_item_summary": ".summary, .abstract, p",
            "detail_title": "h1, .report-title, .title",
            "detail_content": ".report-content, article, .content, .detail-content",
            "detail_published_at": ".publish-date, .date, time",
            "attachment_links": "a[href$='.pdf'], a[href*='.pdf?'], .download a[href]",
        },
        detail_required=True,
        pdf_expected=True,
        pagination_mode=PaginationMode.NEXT_LINK,
        language="zh-CN",
        encoding_hints=["utf-8", "gbk", "gb18030"],
        collector_config={
            "attachment_keywords": [
                "\u62a5\u544a",
                "\u767d\u76ae\u4e66",
                "\u9644\u4ef6",
                "\u4e0b\u8f7d",
            ],
            "report_formats": ["html", "pdf"],
            "detail_required_for_pdf_discovery": True,
        },
        collector_notes=[
            "browser_fallback_todo",
            "site_specific_parser_rules_todo",
            "auth_login_collectors_todo",
        ],
    )
