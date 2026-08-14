from __future__ import annotations

from packages.sources.enums import (
    AccessMethod,
    CollectorType,
    GovernanceAxis,
    InfoType,
    LineFamily,
    PaginationMode,
    PublisherType,
    RegionalLevel,
    SourceCategory,
    SourceRole,
    TrustTier,
)
from packages.sources.schemas import SourceAccess, SourceCapabilities, SourceProfile


def build_cn_policy_generic_profile(*, enabled: bool = False) -> SourceProfile:
    return SourceProfile(
        source_id="cn_policy_generic",
        display_name="China Policy Portal Generic",
        category=SourceCategory.POLICY_PORTAL,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        enabled=enabled,
        description=(
            "Generic domestic policy-portal collector family for notice/article list-detail pages."
        ),
        access=SourceAccess(
            access_method=AccessMethod.WEB,
            auth_required=False,
            base_url="https://example.cn/policy",
        ),
        capabilities=SourceCapabilities(
            supports_search=True,
            supports_document_detail=True,
            supports_evidence_extraction=True,
            supports_time_filter=True,
            supports_keyword_filter=True,
            supports_bulk=True,
        ),
        priority_hint=74,
        tags=["china", "policy", "html", "pdf"],
        profile_family="china_policy",
        governance_axis=GovernanceAxis.LINE,
        line_family=LineFamily.POLICY,
        regional_level=RegionalLevel.NATIONAL,
        info_type=InfoType.POLICY_NOTICE,
        publisher_type=PublisherType.MINISTRY,
        source_role=SourceRole.PRIMARY,
        collector_type=CollectorType.HTML_LIST_DETAIL,
        entry_urls=["https://example.cn/policy/list"],
        selectors={
            "list_item": ".list-item, li",
            "list_item_link": "a[href]",
            "list_item_date": ".date, .publish-date, time",
            "list_item_summary": ".summary, .desc, p",
            "detail_title": "h1, .article-title, .title",
            "detail_content": "article, .article-content, .content, .detail-content",
            "detail_published_at": ".publish-date, .date, time",
            "attachment_links": "a[href$='.pdf'], a[href*='.pdf?'], .attachment a[href]",
        },
        detail_required=True,
        pdf_expected=True,
        pagination_mode=PaginationMode.PAGE_NUMBER,
        language="zh-CN",
        encoding_hints=["utf-8", "gb18030"],
        collector_config={
            "list_window_days_default": 30,
            "date_patterns": ["%Y-%m-%d", "%Y/%m/%d"],
            "attachment_keywords": ["\u9644\u4ef6", "pdf", "\u4e0b\u8f7d"],
        },
        collector_notes=[
            "browser_fallback_todo",
            "auth_login_collectors_todo",
            "domestic_source_eval_integration_todo",
        ],
    )


def build_cn_policy_ndrc_tzgg_v1_profile(*, enabled: bool = False) -> SourceProfile:
    return SourceProfile(
        source_id="cn_policy_ndrc_tzgg_v1",
        display_name="NDRC Notices",
        category=SourceCategory.POLICY_PORTAL,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        enabled=enabled,
        description=(
            "National Development and Reform Commission notice list/detail pages "
            "under 通知公告."
        ),
        access=SourceAccess(
            access_method=AccessMethod.WEB,
            auth_required=False,
            base_url="https://www.ndrc.gov.cn",
        ),
        capabilities=SourceCapabilities(
            supports_search=True,
            supports_document_detail=True,
            supports_evidence_extraction=True,
            supports_time_filter=True,
            supports_keyword_filter=True,
            supports_bulk=False,
        ),
        priority_hint=82,
        tags=["china", "ndrc", "policy", "notice", "attachment"],
        profile_family="china_policy",
        governance_axis=GovernanceAxis.LINE,
        line_family=LineFamily.POLICY,
        regional_level=RegionalLevel.NATIONAL,
        info_type=InfoType.POLICY_NOTICE,
        publisher_type=PublisherType.MINISTRY,
        source_role=SourceRole.PRIMARY,
        collector_type=CollectorType.HTML_LIST_DETAIL,
        entry_urls=["https://www.ndrc.gov.cn/xwdt/tzgg/index.html"],
        selectors={
            "list_item": ".list li",
            "list_item_link": "a[href]",
            "list_item_date": "span",
            "detail_title": ".article_title",
            "detail_content": ".article_con .TRS_Editor, .article_con",
            "detail_published_at": ".shezhi .time",
            "attachment_links": (
                ".attachment_r a[href$='.pdf'], "
                ".attachment_r a[href*='.pdf?']"
            ),
        },
        detail_required=True,
        pdf_expected=True,
        pagination_mode=PaginationMode.PAGE_NUMBER,
        language="zh-CN",
        encoding_hints=["utf-8"],
        collector_config={
            "publisher": "国家发展和改革委员会",
            "attachment_keywords": ["附件", "PDF", "下载"],
            "date_patterns": ["%Y/%m/%d", "%Y-%m-%d"],
            "first_page_only": True,
        },
        collector_notes=[
            "real_site_profile_v1",
            "browser_fallback_todo",
            "anti_bot_resilience_todo",
        ],
    )
