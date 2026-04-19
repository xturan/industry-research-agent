from __future__ import annotations

from packages.sources.enums import (
    AccessMethod,
    CollectorType,
    PaginationMode,
    SourceCategory,
    TrustTier,
)
from packages.sources.schemas import SourceAccess, SourceCapabilities, SourceProfile


def build_cn_exchange_announcement_generic_profile(*, enabled: bool = False) -> SourceProfile:
    return SourceProfile(
        source_id="cn_exchange_announcement_generic",
        display_name="China Exchange Announcement Generic",
        category=SourceCategory.EXCHANGE_ANNOUNCEMENT,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        enabled=enabled,
        description=(
            "Generic domestic exchange/company announcement collector family "
            "for announcement list pages."
        ),
        access=SourceAccess(
            access_method=AccessMethod.WEB,
            auth_required=False,
            base_url="https://example.cn/exchange",
        ),
        capabilities=SourceCapabilities(
            supports_search=True,
            supports_document_detail=True,
            supports_evidence_extraction=True,
            supports_time_filter=True,
            supports_keyword_filter=True,
            supports_bulk=True,
        ),
        priority_hint=76,
        tags=["china", "exchange", "announcement", "pdf"],
        profile_family="china_exchange",
        collector_type=CollectorType.HTML_LIST_DETAIL,
        entry_urls=["https://example.cn/exchange/announcements"],
        selectors={
            "list_item": "tr[data-id], .announcement-item, li",
            "list_item_link": "a[href]",
            "list_item_date": ".date, .publish-date, td.date, time",
            "list_item_summary": ".summary, .desc, td.summary",
            "detail_title": "h1, .announcement-title, .title",
            "detail_content": ".announcement-content, article, .content, .detail-content",
            "detail_published_at": ".publish-date, .date, time",
            "attachment_links": "a[href$='.pdf'], a[href*='.pdf?'], .attachment a[href]",
        },
        detail_required=True,
        pdf_expected=True,
        pagination_mode=PaginationMode.PAGE_NUMBER,
        language="zh-CN",
        encoding_hints=["utf-8", "gb18030"],
        collector_config={
            "external_id_source": "announcement_id",
            "attachment_keywords": ["\u516c\u544a", "\u9644\u4ef6", "pdf"],
            "pagination_hints": ["page", "pageNum", "pageno"],
        },
        collector_notes=[
            "deep_pagination_todo",
            "site_specific_parser_rules_todo",
            "domestic_source_eval_integration_todo",
        ],
    )


def build_cn_exchange_szse_notice_v1_profile(*, enabled: bool = False) -> SourceProfile:
    return SourceProfile(
        source_id="cn_exchange_szse_notice_v1",
        display_name="SZSE Notice Announcements",
        category=SourceCategory.EXCHANGE_ANNOUNCEMENT,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        enabled=enabled,
        description=(
            "Shenzhen Stock Exchange notice/disclosure list/detail pages under 通知公告."
        ),
        access=SourceAccess(
            access_method=AccessMethod.WEB,
            auth_required=False,
            base_url="https://www.szse.cn",
        ),
        capabilities=SourceCapabilities(
            supports_search=True,
            supports_document_detail=True,
            supports_evidence_extraction=True,
            supports_time_filter=True,
            supports_keyword_filter=True,
            supports_bulk=False,
        ),
        priority_hint=84,
        tags=["china", "szse", "exchange", "announcement", "disclosure"],
        profile_family="china_exchange",
        collector_type=CollectorType.HTML_LIST_DETAIL,
        entry_urls=["https://www.szse.cn/disclosure/notice/general/index.html"],
        selectors={
            "list_item": ".article-list li",
            "list_item_date": ".time span, .time",
            "detail_title": ".des-header .title",
            "detail_content": ".des-content",
            "detail_published_at": ".des-header .time span, .des-header .time",
            "attachment_links": (
                ".des-content a[href$='.pdf'], "
                ".des-content a[href*='.pdf?']"
            ),
        },
        detail_required=True,
        pdf_expected=False,
        pagination_mode=PaginationMode.PAGE_NUMBER,
        language="zh-CN",
        encoding_hints=["utf-8"],
        collector_config={
            "publisher": "深圳证券交易所",
            "list_item_script_parser": "szse_notice_v1",
            "date_patterns": ["%Y-%m-%d"],
            "first_page_only": True,
        },
        collector_notes=[
            "real_site_profile_v1",
            "script_defined_list_items",
            "browser_fallback_todo",
        ],
    )
