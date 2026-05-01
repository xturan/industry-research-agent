from __future__ import annotations

from typing import Any

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

_DEFAULT_POLICY_SELECTORS: dict[str, str] = {
    "list_item": ".list li, .article-list li, .news_list li, .txtList li, li",
    "list_item_link": "a[href]",
    "list_item_date": ".date, .publish-date, .time, span",
    "list_item_summary": ".summary, .desc, p",
    "detail_title": "h1, .article_title, .title, .Tit",
    "detail_content": (
        ".article-content, .article_con, .content, .TRS_Editor, .detail-content, article, body"
    ),
    "detail_published_at": ".publish-date, .date, .time, time",
    "attachment_links": (
        "a[href$='.pdf'], a[href*='.pdf?'], .attachment a[href], .download a[href]"
    ),
}

_DEFAULT_DISCLOSURE_SELECTORS: dict[str, str] = {
    "list_item": ".article-list li, .newsList li, tr[data-id], li",
    "list_item_link": "a[href]",
    "list_item_date": ".date, .time, .publish-date, td",
    "list_item_summary": ".summary, .desc, td",
    "detail_title": "h1, .title, .des-header .title",
    "detail_content": ".des-content, .article-content, .content, article, body",
    "detail_published_at": ".date, .time, time",
    "attachment_links": (
        "a[href$='.pdf'], a[href*='.pdf?'], .des-content a[href], .attachment a[href]"
    ),
}

_DEFAULT_PROJECT_SELECTORS: dict[str, str] = {
    "list_item": ".article-list li, .news_list li, .search-list li, tr, li",
    "list_item_link": "a[href]",
    "list_item_date": ".date, .time, .publish-date, td, span",
    "list_item_summary": ".summary, .desc, .project-summary, p, td",
    "detail_title": "h1, .title, .article_title, .project-title",
    "detail_content": (
        ".article-content, .detail-content, .project-content, .content, article, body"
    ),
    "detail_published_at": ".publish-date, .date, .time, time",
    "attachment_links": (
        "a[href$='.pdf'], a[href*='.pdf?'], .attachment a[href], .download a[href]"
    ),
}

_DEFAULT_INDUSTRY_SELECTORS: dict[str, str] = {
    "list_item": ".report-item, .notice-item, .article-list li, .news_list li, li",
    "list_item_link": "a[href]",
    "list_item_date": ".date, .publish-date, .time, span",
    "list_item_summary": ".summary, .desc, p",
    "detail_title": "h1, .title, .report-title, .article_title",
    "detail_content": ".report-content, .article-content, .content, article, body",
    "detail_published_at": ".publish-date, .date, .time, time",
    "attachment_links": (
        "a[href$='.pdf'], a[href*='.pdf?'], .attachment a[href], .download a[href]"
    ),
}


def _build_policy_profile(
    *,
    source_id: str,
    display_name: str,
    base_url: str,
    entry_url: str,
    governance_axis: GovernanceAxis,
    regional_level: RegionalLevel,
    source_role: SourceRole,
    publisher_type: PublisherType,
    template_family: str,
    priority_hint: int,
    tags: list[str],
    collector_config: dict[str, Any] | None = None,
    selectors: dict[str, str] | None = None,
    enabled: bool = True,
) -> SourceProfile:
    return SourceProfile(
        source_id=source_id,
        display_name=display_name,
        category=SourceCategory.POLICY_PORTAL,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        enabled=enabled,
        description=f"Phase-1 sample domestic policy source ({template_family}).",
        access=SourceAccess(
            access_method=AccessMethod.WEB,
            auth_required=False,
            base_url=base_url,
        ),
        capabilities=SourceCapabilities(
            supports_search=True,
            supports_document_detail=True,
            supports_evidence_extraction=True,
            supports_time_filter=True,
            supports_keyword_filter=True,
            supports_bulk=False,
        ),
        priority_hint=priority_hint,
        tags=tags,
        profile_family="china_scaleout",
        governance_axis=governance_axis,
        line_family=LineFamily.POLICY,
        regional_level=regional_level,
        info_type=InfoType.POLICY_NOTICE,
        publisher_type=publisher_type,
        source_role=source_role,
        collector_type=CollectorType.HTML_LIST_DETAIL,
        entry_urls=[entry_url],
        selectors={**_DEFAULT_POLICY_SELECTORS, **(selectors or {})},
        detail_required=True,
        pdf_expected=True,
        pagination_mode=PaginationMode.PAGE_NUMBER,
        language="zh-CN",
        encoding_hints=["utf-8", "gb18030"],
        collector_config={
            "template_family": template_family,
            "phase": "phase1_sample_validation",
            "date_patterns": ["%Y-%m-%d", "%Y/%m/%d"],
            **(collector_config or {}),
        },
        collector_notes=[
            "phase1_sample_profile",
            "site_patch_tuning_todo",
            "browser_fallback_todo",
        ],
    )


def _build_disclosure_profile(
    *,
    source_id: str,
    display_name: str,
    base_url: str,
    entry_url: str,
    priority_hint: int,
    tags: list[str],
    collector_config: dict[str, Any] | None = None,
    selectors: dict[str, str] | None = None,
    enabled: bool = True,
) -> SourceProfile:
    return SourceProfile(
        source_id=source_id,
        display_name=display_name,
        category=SourceCategory.EXCHANGE_ANNOUNCEMENT,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        enabled=enabled,
        description="Phase-1 sample domestic disclosure source (disclosure_template).",
        access=SourceAccess(
            access_method=AccessMethod.WEB,
            auth_required=False,
            base_url=base_url,
        ),
        capabilities=SourceCapabilities(
            supports_search=True,
            supports_document_detail=True,
            supports_evidence_extraction=True,
            supports_time_filter=True,
            supports_keyword_filter=True,
            supports_bulk=False,
        ),
        priority_hint=priority_hint,
        tags=tags,
        profile_family="china_scaleout",
        governance_axis=GovernanceAxis.LINE,
        line_family=LineFamily.EXCHANGE,
        regional_level=RegionalLevel.NATIONAL,
        info_type=InfoType.REGULATORY_ANNOUNCEMENT,
        publisher_type=PublisherType.EXCHANGE,
        source_role=SourceRole.PRIMARY,
        collector_type=CollectorType.HTML_LIST_DETAIL,
        entry_urls=[entry_url],
        selectors={**_DEFAULT_DISCLOSURE_SELECTORS, **(selectors or {})},
        detail_required=True,
        pdf_expected=True,
        pagination_mode=PaginationMode.PAGE_NUMBER,
        language="zh-CN",
        encoding_hints=["utf-8", "gb18030"],
        collector_config={
            "template_family": "disclosure_template",
            "phase": "phase1_sample_validation",
            **(collector_config or {}),
        },
        collector_notes=[
            "phase1_sample_profile",
            "site_patch_tuning_todo",
            "browser_fallback_todo",
        ],
    )


def _build_project_profile(
    *,
    source_id: str,
    display_name: str,
    base_url: str,
    entry_url: str,
    governance_axis: GovernanceAxis,
    regional_level: RegionalLevel,
    source_role: SourceRole,
    priority_hint: int,
    tags: list[str],
    collector_config: dict[str, Any] | None = None,
    selectors: dict[str, str] | None = None,
    enabled: bool = True,
) -> SourceProfile:
    return SourceProfile(
        source_id=source_id,
        display_name=display_name,
        category=SourceCategory.PROJECT_SIGNAL,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        enabled=enabled,
        description="Phase-2 project-signal source (metadata-first compatible).",
        access=SourceAccess(
            access_method=AccessMethod.WEB,
            auth_required=False,
            base_url=base_url,
        ),
        capabilities=SourceCapabilities(
            supports_search=True,
            supports_document_detail=True,
            supports_evidence_extraction=True,
            supports_time_filter=True,
            supports_keyword_filter=True,
            supports_bulk=False,
        ),
        priority_hint=priority_hint,
        tags=tags,
        profile_family="china_scaleout",
        governance_axis=governance_axis,
        line_family=LineFamily.CROSS_DOMAIN,
        regional_level=regional_level,
        info_type=InfoType.PROJECT_TRANSACTION,
        publisher_type=PublisherType.INSTITUTION,
        source_role=source_role,
        collector_type=CollectorType.HTML_LIST_DETAIL,
        entry_urls=[entry_url],
        selectors={**_DEFAULT_PROJECT_SELECTORS, **(selectors or {})},
        detail_required=False,
        pdf_expected=False,
        pagination_mode=PaginationMode.PAGE_NUMBER,
        language="zh-CN",
        encoding_hints=["utf-8", "gb18030"],
        collector_config={
            "template_family": "project_query_template",
            "phase": "phase2_backbone_buildout",
            "metadata_first": True,
            "date_patterns": ["%Y-%m-%d", "%Y/%m/%d"],
            **(collector_config or {}),
        },
        collector_notes=[
            "phase2_backbone_profile",
            "metadata_first_mode",
            "site_patch_tuning_todo",
            "browser_fallback_todo",
        ],
    )


def _build_park_profile(
    *,
    source_id: str,
    display_name: str,
    base_url: str,
    entry_url: str,
    regional_level: RegionalLevel,
    priority_hint: int,
    tags: list[str],
    collector_config: dict[str, Any] | None = None,
    selectors: dict[str, str] | None = None,
    enabled: bool = True,
) -> SourceProfile:
    return _build_project_profile(
        source_id=source_id,
        display_name=display_name,
        base_url=base_url,
        entry_url=entry_url,
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=regional_level,
        source_role=SourceRole.SUPPLEMENTAL,
        priority_hint=priority_hint,
        tags=tags,
        collector_config={
            "template_family": "park_template",
            "phase": "phase4_city_park_rollout",
            **(collector_config or {}),
        },
        selectors=selectors,
        enabled=enabled,
    )


def _build_industry_profile(
    *,
    source_id: str,
    display_name: str,
    base_url: str,
    entry_url: str,
    regional_level: RegionalLevel,
    info_type: InfoType,
    priority_hint: int,
    tags: list[str],
    collector_config: dict[str, Any] | None = None,
    selectors: dict[str, str] | None = None,
    enabled: bool = True,
) -> SourceProfile:
    return SourceProfile(
        source_id=source_id,
        display_name=display_name,
        category=SourceCategory.INDUSTRY_ASSOCIATION,
        trust_tier=TrustTier.SECONDARY_INSTITUTIONAL,
        enabled=enabled,
        description="Phase-5 industry/association signal source.",
        access=SourceAccess(
            access_method=AccessMethod.WEB,
            auth_required=False,
            base_url=base_url,
        ),
        capabilities=SourceCapabilities(
            supports_search=True,
            supports_document_detail=True,
            supports_evidence_extraction=True,
            supports_time_filter=True,
            supports_keyword_filter=True,
            supports_bulk=False,
        ),
        priority_hint=priority_hint,
        tags=tags,
        profile_family="china_scaleout",
        governance_axis=GovernanceAxis.BLOCK,
        line_family=LineFamily.INDUSTRY,
        regional_level=regional_level,
        info_type=info_type,
        publisher_type=PublisherType.ASSOCIATION,
        source_role=SourceRole.SUPPLEMENTAL,
        collector_type=CollectorType.HTML_LIST_DETAIL,
        entry_urls=[entry_url],
        selectors={**_DEFAULT_INDUSTRY_SELECTORS, **(selectors or {})},
        detail_required=True,
        pdf_expected=True,
        pagination_mode=PaginationMode.PAGE_NUMBER,
        language="zh-CN",
        encoding_hints=["utf-8", "gb18030"],
        collector_config={
            "template_family": "association_template",
            "phase": "phase5_association_special_topic",
            "date_patterns": ["%Y-%m-%d", "%Y/%m/%d"],
            **(collector_config or {}),
        },
        collector_notes=[
            "phase5_industry_profile",
            "site_patch_tuning_todo",
            "browser_fallback_todo",
        ],
    )


def _build_data_profile(
    *,
    source_id: str,
    display_name: str,
    base_url: str,
    entry_url: str,
    governance_axis: GovernanceAxis,
    regional_level: RegionalLevel,
    source_role: SourceRole,
    publisher_type: PublisherType,
    template_family: str,
    priority_hint: int,
    tags: list[str],
    collector_config: dict[str, Any] | None = None,
    selectors: dict[str, str] | None = None,
    enabled: bool = True,
) -> SourceProfile:
    return SourceProfile(
        source_id=source_id,
        display_name=display_name,
        category=SourceCategory.MACRO_DATA,
        trust_tier=TrustTier.PRIMARY_OFFICIAL,
        enabled=enabled,
        description="Phase-4 national/provincial backbone data source.",
        access=SourceAccess(
            access_method=AccessMethod.WEB,
            auth_required=False,
            base_url=base_url,
        ),
        capabilities=SourceCapabilities(
            supports_search=True,
            supports_document_detail=True,
            supports_evidence_extraction=True,
            supports_time_filter=True,
            supports_keyword_filter=True,
            supports_bulk=False,
        ),
        priority_hint=priority_hint,
        tags=tags,
        profile_family="china_scaleout",
        governance_axis=governance_axis,
        line_family=LineFamily.CROSS_DOMAIN,
        regional_level=regional_level,
        info_type=InfoType.INDUSTRY_NOTICE,
        publisher_type=publisher_type,
        source_role=source_role,
        collector_type=CollectorType.HTML_LIST_DETAIL,
        entry_urls=[entry_url],
        selectors={**_DEFAULT_POLICY_SELECTORS, **(selectors or {})},
        detail_required=True,
        pdf_expected=True,
        pagination_mode=PaginationMode.PAGE_NUMBER,
        language="zh-CN",
        encoding_hints=["utf-8", "gb18030"],
        collector_config={
            "template_family": template_family,
            "phase": "phase4_national_provincial_backbone",
            "date_patterns": ["%Y-%m-%d", "%Y/%m/%d"],
            **(collector_config or {}),
        },
        collector_notes=[
            "phase4_backbone_profile",
            "site_patch_tuning_todo",
            "browser_fallback_todo",
        ],
    )


def build_cn_policy_state_council_zcwj_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_state_council_zcwj_v1",
        display_name="State Council Policy Documents",
        base_url="https://www.gov.cn",
        entry_url="https://www.gov.cn/zhengce/zuixin.htm",
        governance_axis=GovernanceAxis.LINE,
        regional_level=RegionalLevel.NATIONAL,
        source_role=SourceRole.PRIMARY,
        publisher_type=PublisherType.MINISTRY,
        template_family="policy_library_template",
        priority_hint=86,
        tags=["china", "policy", "state-council", "phase1"],
        enabled=enabled,
    )


def build_cn_policy_miit_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_miit_tzgg_v1",
        display_name="MIIT Notices",
        base_url="https://www.miit.gov.cn",
        entry_url="https://www.miit.gov.cn/zwgk/wjgs",
        governance_axis=GovernanceAxis.LINE,
        regional_level=RegionalLevel.NATIONAL,
        source_role=SourceRole.PRIMARY,
        publisher_type=PublisherType.MINISTRY,
        template_family="policy_library_template",
        priority_hint=84,
        tags=["china", "policy", "miit", "phase1"],
        enabled=enabled,
    )


def build_cn_exchange_sse_notice_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_disclosure_profile(
        source_id="cn_exchange_sse_notice_v1",
        display_name="SSE Notices",
        base_url="https://www.sse.com.cn",
        entry_url="https://www.sse.com.cn/disclosure/announcement/general/",
        priority_hint=84,
        tags=["china", "sse", "disclosure", "phase1"],
        enabled=enabled,
    )


def build_cn_exchange_cninfo_announcement_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_disclosure_profile(
        source_id="cn_exchange_cninfo_announcement_v1",
        display_name="CNINFO Announcements",
        base_url="https://www.cninfo.com.cn",
        entry_url="https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
        priority_hint=82,
        tags=["china", "cninfo", "disclosure", "phase1"],
        collector_config={"search_payload_required": True},
        enabled=enabled,
    )


def build_cn_policy_gd_drc_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_gd_drc_tzgg_v1",
        display_name="Guangdong DRC Notices",
        base_url="https://drc.gd.gov.cn",
        entry_url="https://drc.gd.gov.cn/zwgk/tzgg/",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.PROVINCIAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="province_drc_template",
        priority_hint=77,
        tags=["china", "guangdong", "drc", "phase1"],
        enabled=enabled,
    )


def build_cn_policy_js_gxt_zcwj_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_js_gxt_zcwj_v1",
        display_name="Jiangsu MIIT Policy Docs",
        base_url="https://gxt.jiangsu.gov.cn",
        entry_url="https://gxt.jiangsu.gov.cn/col/col62439/index.html",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.PROVINCIAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="province_miit_template",
        priority_hint=76,
        tags=["china", "jiangsu", "miit", "phase1"],
        enabled=enabled,
    )


def build_cn_policy_zhejiang_drc_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_zhejiang_drc_tzgg_v1",
        display_name="Zhejiang DRC Notices",
        base_url="https://fzggw.zj.gov.cn",
        entry_url="https://fzggw.zj.gov.cn/col/col1599544/index.html",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.PROVINCIAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="province_drc_template",
        priority_hint=76,
        tags=["china", "zhejiang", "drc", "phase1"],
        enabled=enabled,
    )


def build_cn_policy_hubei_gxt_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_hubei_gxt_tzgg_v1",
        display_name="Hubei MIIT Notices",
        base_url="https://gxt.hubei.gov.cn",
        entry_url="https://gxt.hubei.gov.cn/fbjd/tzgg/",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.PROVINCIAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="province_miit_template",
        priority_hint=75,
        tags=["china", "hubei", "miit", "phase1"],
        enabled=enabled,
    )


def build_cn_policy_sichuan_drc_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_sichuan_drc_tzgg_v1",
        display_name="Sichuan DRC Notices",
        base_url="https://fgw.sc.gov.cn",
        entry_url="https://fgw.sc.gov.cn/sfgw/c106071/zfxxgk_list.shtml",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.PROVINCIAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="province_drc_template",
        priority_hint=75,
        tags=["china", "sichuan", "drc", "phase1"],
        enabled=enabled,
    )


def build_cn_policy_shanghai_portal_policy_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_shanghai_portal_policy_v1",
        display_name="Shanghai Gov Policy Portal",
        base_url="https://www.shanghai.gov.cn",
        entry_url="https://www.shanghai.gov.cn/nw12344/index.html",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.PROVINCIAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="province_portal_template",
        priority_hint=74,
        tags=["china", "shanghai", "portal", "phase1"],
        enabled=enabled,
    )


def build_cn_policy_shenzhen_gxt_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_shenzhen_gxt_tzgg_v1",
        display_name="Shenzhen MIIT Notices",
        base_url="https://gxj.sz.gov.cn",
        entry_url="https://gxj.sz.gov.cn/xxgk/qt/tzgg/",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.MUNICIPAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="city_dept_template",
        priority_hint=73,
        tags=["china", "shenzhen", "miit", "phase1"],
        enabled=enabled,
    )


def build_cn_policy_suzhou_drc_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_suzhou_drc_tzgg_v1",
        display_name="Suzhou DRC Notices",
        base_url="https://fgw.suzhou.gov.cn",
        entry_url="https://fgw.suzhou.gov.cn/szfgw/tzgg/list.shtml",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.MUNICIPAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="city_dept_template",
        priority_hint=72,
        tags=["china", "suzhou", "drc", "phase1"],
        enabled=enabled,
    )


def build_cn_policy_hangzhou_fgw_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_hangzhou_fgw_tzgg_v1",
        display_name="Hangzhou DRC Notices",
        base_url="https://fgw.hangzhou.gov.cn",
        entry_url="https://fgw.hangzhou.gov.cn/col/col1229460512/index.html",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.MUNICIPAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="city_dept_template",
        priority_hint=72,
        tags=["china", "hangzhou", "drc", "phase1"],
        enabled=enabled,
    )


def build_cn_policy_wuhan_gxt_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_wuhan_gxt_tzgg_v1",
        display_name="Wuhan MIIT Notices",
        base_url="https://gxj.wuhan.gov.cn",
        entry_url="https://gxj.wuhan.gov.cn/zwgk_19/tzgg/",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.MUNICIPAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="city_dept_template",
        priority_hint=72,
        tags=["china", "wuhan", "miit", "phase1"],
        enabled=enabled,
    )


def build_phase1_sample_profiles(*, enabled: bool = True) -> list[SourceProfile]:
    return [
        build_cn_policy_state_council_zcwj_v1_profile(enabled=enabled),
        build_cn_policy_miit_tzgg_v1_profile(enabled=enabled),
        build_cn_exchange_sse_notice_v1_profile(enabled=enabled),
        build_cn_exchange_cninfo_announcement_v1_profile(enabled=enabled),
        build_cn_policy_gd_drc_tzgg_v1_profile(enabled=enabled),
        build_cn_policy_js_gxt_zcwj_v1_profile(enabled=enabled),
        build_cn_policy_zhejiang_drc_tzgg_v1_profile(enabled=enabled),
        build_cn_policy_hubei_gxt_tzgg_v1_profile(enabled=enabled),
        build_cn_policy_sichuan_drc_tzgg_v1_profile(enabled=enabled),
        build_cn_policy_shanghai_portal_policy_v1_profile(enabled=enabled),
        build_cn_policy_shenzhen_gxt_tzgg_v1_profile(enabled=enabled),
        build_cn_policy_suzhou_drc_tzgg_v1_profile(enabled=enabled),
        build_cn_policy_hangzhou_fgw_tzgg_v1_profile(enabled=enabled),
        build_cn_policy_wuhan_gxt_tzgg_v1_profile(enabled=enabled),
    ]


def build_cn_policy_anhui_drc_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_anhui_drc_tzgg_v1",
        display_name="Anhui DRC Notices",
        base_url="https://fzggw.ah.gov.cn",
        entry_url="https://fzggw.ah.gov.cn/public/column/21611",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.PROVINCIAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="province_drc_template",
        priority_hint=75,
        tags=["china", "anhui", "drc", "phase3"],
        enabled=enabled,
    )


def build_cn_policy_shandong_gxt_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_shandong_gxt_tzgg_v1",
        display_name="Shandong MIIT Notices",
        base_url="http://gxt.shandong.gov.cn",
        entry_url="http://gxt.shandong.gov.cn/col/col15841/index.html",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.PROVINCIAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="province_miit_template",
        priority_hint=75,
        tags=["china", "shandong", "miit", "phase3"],
        enabled=enabled,
    )


def build_cn_policy_fujian_drc_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_fujian_drc_tzgg_v1",
        display_name="Fujian DRC Notices",
        base_url="https://fgw.fujian.gov.cn",
        entry_url="https://fgw.fujian.gov.cn/zwgk/tzgg/",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.PROVINCIAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="province_drc_template",
        priority_hint=74,
        tags=["china", "fujian", "drc", "phase3"],
        enabled=enabled,
    )


def build_cn_policy_henan_gxt_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_henan_gxt_tzgg_v1",
        display_name="Henan MIIT Notices",
        base_url="https://gxt.henan.gov.cn",
        entry_url="https://gxt.henan.gov.cn/jxdt/tzgg/",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.PROVINCIAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="province_miit_template",
        priority_hint=74,
        tags=["china", "henan", "miit", "phase3"],
        enabled=enabled,
    )


def build_cn_policy_guangzhou_gxt_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_guangzhou_gxt_tzgg_v1",
        display_name="Guangzhou MIIT Notices",
        base_url="https://gxj.gz.gov.cn",
        entry_url="https://gxj.gz.gov.cn/zwgk/tzgg/",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.MUNICIPAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="city_dept_template",
        priority_hint=72,
        tags=["china", "guangzhou", "miit", "phase4"],
        enabled=enabled,
    )


def build_cn_policy_nanjing_gxt_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_nanjing_gxt_tzgg_v1",
        display_name="Nanjing MIIT Notices",
        base_url="https://gxhxxhj.nanjing.gov.cn",
        entry_url="https://gxhxxhj.nanjing.gov.cn/njsgxj/tzgg/list.shtml",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.MUNICIPAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="city_dept_template",
        priority_hint=71,
        tags=["china", "nanjing", "miit", "phase4"],
        enabled=enabled,
    )


def build_cn_policy_chengdu_jxj_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_policy_profile(
        source_id="cn_policy_chengdu_jxj_tzgg_v1",
        display_name="Chengdu Economy and IT Notices",
        base_url="https://jxj.chengdu.gov.cn",
        entry_url="https://jxj.chengdu.gov.cn/cdsjxw/c132574/list.shtml",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.MUNICIPAL,
        source_role=SourceRole.SECONDARY,
        publisher_type=PublisherType.INSTITUTION,
        template_family="city_dept_template",
        priority_hint=71,
        tags=["china", "chengdu", "miit", "phase4"],
        enabled=enabled,
    )


def build_cn_park_sh_lingang_tzgg_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_park_profile(
        source_id="cn_park_sh_lingang_tzgg_v1",
        display_name="Shanghai Lingang Notices",
        base_url="https://www.lingang.gov.cn",
        entry_url="https://www.lingang.gov.cn/html/website/lingang/tzgg/",
        regional_level=RegionalLevel.MUNICIPAL,
        priority_hint=70,
        tags=["china", "park", "lingang", "phase4"],
        enabled=enabled,
    )


def build_cn_industry_caam_news_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_industry_profile(
        source_id="cn_industry_caam_news_v1",
        display_name="CAAM Industry News",
        base_url="http://www.caam.org.cn",
        entry_url="http://www.caam.org.cn/newslist/a0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-1.html",
        regional_level=RegionalLevel.NATIONAL,
        info_type=InfoType.INDUSTRY_NOTICE,
        priority_hint=69,
        tags=["china", "association", "caam", "phase5"],
        enabled=enabled,
    )


def build_cn_industry_ces_report_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_industry_profile(
        source_id="cn_industry_ces_report_v1",
        display_name="China Electronics Society Reports",
        base_url="https://www.cie.org.cn",
        entry_url="https://www.cie.org.cn/list/31.html",
        regional_level=RegionalLevel.NATIONAL,
        info_type=InfoType.INDUSTRY_REPORT,
        priority_hint=68,
        tags=["china", "association", "electronics", "phase5"],
        enabled=enabled,
    )


def build_cn_project_ccgp_procurement_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_project_profile(
        source_id="cn_project_ccgp_procurement_v1",
        display_name="CCGP Procurement Notices",
        base_url="https://www.ccgp.gov.cn",
        entry_url="https://www.ccgp.gov.cn/cggg/",
        governance_axis=GovernanceAxis.LINE,
        regional_level=RegionalLevel.NATIONAL,
        source_role=SourceRole.PRIMARY,
        priority_hint=82,
        tags=["china", "procurement", "project", "phase2"],
        selectors={
            "list_item": ".ulst li",
            "list_item_link": "a[href]",
            "list_item_date": "span",
            "list_item_summary": "span, p",
        },
        enabled=enabled,
    )


def build_cn_project_ggzy_trade_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_project_profile(
        source_id="cn_project_ggzy_trade_v1",
        display_name="National Public Resource Trade",
        base_url="https://www.ggzy.gov.cn",
        entry_url="https://www.ggzy.gov.cn/deal/dealList.html",
        governance_axis=GovernanceAxis.BLOCK,
        regional_level=RegionalLevel.CROSS_REGION,
        source_role=SourceRole.PRIMARY,
        priority_hint=81,
        tags=["china", "public-resource", "project", "phase2"],
        enabled=enabled,
    )


def build_cn_project_ndrc_approval_v1_profile(*, enabled: bool = True) -> SourceProfile:
    return _build_project_profile(
        source_id="cn_project_ndrc_approval_v1",
        display_name="NDRC Project Approval",
        base_url="https://www.ndrc.gov.cn",
        entry_url="https://www.ndrc.gov.cn/fgsj/tzcx/",
        governance_axis=GovernanceAxis.LINE,
        regional_level=RegionalLevel.NATIONAL,
        source_role=SourceRole.PRIMARY,
        priority_hint=80,
        tags=["china", "approval", "project", "phase2"],
        enabled=enabled,
    )


def build_phase2_backbone_profiles(*, enabled: bool = True) -> list[SourceProfile]:
    return [
        build_cn_project_ccgp_procurement_v1_profile(enabled=enabled),
        build_cn_project_ggzy_trade_v1_profile(enabled=enabled),
        build_cn_project_ndrc_approval_v1_profile(enabled=enabled),
    ]


def build_phase3_provincial_profiles(*, enabled: bool = True) -> list[SourceProfile]:
    return [
        build_cn_policy_anhui_drc_tzgg_v1_profile(enabled=enabled),
        build_cn_policy_shandong_gxt_tzgg_v1_profile(enabled=enabled),
        build_cn_policy_fujian_drc_tzgg_v1_profile(enabled=enabled),
        build_cn_policy_henan_gxt_tzgg_v1_profile(enabled=enabled),
    ]


def build_phase4_city_park_profiles(*, enabled: bool = True) -> list[SourceProfile]:
    return [
        build_cn_policy_guangzhou_gxt_tzgg_v1_profile(enabled=enabled),
        build_cn_policy_nanjing_gxt_tzgg_v1_profile(enabled=enabled),
        build_cn_policy_chengdu_jxj_tzgg_v1_profile(enabled=enabled),
        build_cn_park_sh_lingang_tzgg_v1_profile(enabled=enabled),
    ]


def build_phase5_industry_profiles(*, enabled: bool = True) -> list[SourceProfile]:
    return [
        build_cn_industry_caam_news_v1_profile(enabled=enabled),
        build_cn_industry_ces_report_v1_profile(enabled=enabled),
    ]


def build_phase4_national_provincial_backbone_profiles(
    *,
    enabled: bool = True,
) -> list[SourceProfile]:
    profiles: list[SourceProfile] = [
        _build_policy_profile(
            source_id="cn_policy_most_tzgg_v1",
            display_name="MOST Notices",
            base_url="https://www.most.gov.cn",
            entry_url="https://www.most.gov.cn/xxgk/xinxifenlei/fdzdgknr/tzgg/index.html",
            governance_axis=GovernanceAxis.LINE,
            regional_level=RegionalLevel.NATIONAL,
            source_role=SourceRole.PRIMARY,
            publisher_type=PublisherType.MINISTRY,
            template_family="policy_library_template",
            priority_hint=84,
            tags=["china", "policy", "most", "phase4"],
            collector_config={
                "phase": "phase4_national_provincial_backbone",
                "source_intent": "national_science_department",
                "coverage_lane": "national_policy_direction",
                "official_role": "national_science_department",
            },
            enabled=enabled,
        ),
        _build_data_profile(
            source_id="cn_data_stats_national_v1",
            display_name="National Bureau of Statistics Bulletins",
            base_url="https://www.stats.gov.cn",
            entry_url="https://www.stats.gov.cn/sj/zxfb/",
            governance_axis=GovernanceAxis.LINE,
            regional_level=RegionalLevel.NATIONAL,
            source_role=SourceRole.PRIMARY,
            publisher_type=PublisherType.MINISTRY,
            template_family="national_stats_template",
            priority_hint=84,
            tags=["china", "data", "stats", "phase4"],
            collector_config={
                "source_intent": "national_statistics",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "national_statistics",
            },
            enabled=enabled,
        ),
        _build_data_profile(
            source_id="cn_data_customs_trade_v1",
            display_name="General Administration of Customs Trade Data",
            base_url="https://www.customs.gov.cn",
            entry_url="https://www.customs.gov.cn/customs/302249/302274/302277/index.html",
            governance_axis=GovernanceAxis.LINE,
            regional_level=RegionalLevel.NATIONAL,
            source_role=SourceRole.PRIMARY,
            publisher_type=PublisherType.MINISTRY,
            template_family="national_customs_template",
            priority_hint=83,
            tags=["china", "data", "customs", "trade", "phase4"],
            collector_config={
                "source_intent": "national_customs",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "national_customs",
            },
            enabled=enabled,
        ),
        _build_policy_profile(
            source_id="cn_trade_mofcom_policy_v1",
            display_name="MOFCOM Policy",
            base_url="https://www.mofcom.gov.cn",
            entry_url="https://www.mofcom.gov.cn/zwgk/zcfb/",
            governance_axis=GovernanceAxis.LINE,
            regional_level=RegionalLevel.NATIONAL,
            source_role=SourceRole.PRIMARY,
            publisher_type=PublisherType.MINISTRY,
            template_family="policy_library_template",
            priority_hint=83,
            tags=["china", "trade", "mofcom", "phase4"],
            collector_config={
                "phase": "phase4_national_provincial_backbone",
                "source_intent": "national_commerce",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "national_commerce",
            },
            enabled=enabled,
        ),
    ]

    policy_specs: list[dict[str, Any]] = [
        {
            "source_id": "cn_policy_gd_portal_policy_v1",
            "display_name": "Guangdong Government Policy Portal",
            "base_url": "https://www.gd.gov.cn",
            "entry_url": "https://www.gd.gov.cn/zwgk/wjk/qbwj/",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_portal_template",
            "priority_hint": 79,
            "tags": ["china", "guangdong", "portal", "phase4"],
            "collector_config": {
                "source_intent": "province_government",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_government",
            },
        },
        {
            "source_id": "cn_policy_gd_industry_gdii_v1",
            "display_name": "Guangdong Industry and IT Department Notices",
            "base_url": "https://gdii.gd.gov.cn",
            "entry_url": "https://gdii.gd.gov.cn/zwgk/tzgg/",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_miit_template",
            "priority_hint": 78,
            "tags": ["china", "guangdong", "industry", "phase4"],
            "collector_config": {
                "source_intent": "province_industry_department",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_industry_department",
            },
        },
        {
            "source_id": "cn_policy_gd_stc_gdstc_v1",
            "display_name": "Guangdong Science and Technology Department Notices",
            "base_url": "https://gdstc.gd.gov.cn",
            "entry_url": "https://gdstc.gd.gov.cn/zwgk_n/tzgg/",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_science_template",
            "priority_hint": 77,
            "tags": ["china", "guangdong", "science", "phase4"],
            "collector_config": {
                "source_intent": "province_science_department",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_science_department",
            },
        },
        {
            "source_id": "cn_trade_gd_commerce_policy_v1",
            "display_name": "Guangdong Commerce Department Policy",
            "base_url": "https://com.gd.gov.cn",
            "entry_url": "https://com.gd.gov.cn/zwgk/zcwj/",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_commerce_template",
            "priority_hint": 77,
            "tags": ["china", "guangdong", "commerce", "phase4"],
            "collector_config": {
                "source_intent": "province_commerce",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "province_commerce",
            },
        },
        {
            "source_id": "cn_policy_js_portal_policy_v1",
            "display_name": "Jiangsu Government Policy Portal",
            "base_url": "https://www.jiangsu.gov.cn",
            "entry_url": "https://www.jiangsu.gov.cn/col/col46143/index.html",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_portal_template",
            "priority_hint": 79,
            "tags": ["china", "jiangsu", "portal", "phase4"],
            "collector_config": {
                "source_intent": "province_government",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_government",
            },
        },
        {
            "source_id": "cn_policy_js_drc_fzggw_v1",
            "display_name": "Jiangsu DRC Notices",
            "base_url": "https://fzggw.jiangsu.gov.cn",
            "entry_url": "https://fzggw.jiangsu.gov.cn/col/col28400/index.html",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_drc_template",
            "priority_hint": 78,
            "tags": ["china", "jiangsu", "drc", "phase4"],
            "collector_config": {
                "source_intent": "province_drc",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_drc",
            },
        },
        {
            "source_id": "cn_policy_js_science_kxjst_v1",
            "display_name": "Jiangsu Science and Technology Department Notices",
            "base_url": "https://kxjst.jiangsu.gov.cn",
            "entry_url": "https://kxjst.jiangsu.gov.cn/col/col76126/index.html",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_science_template",
            "priority_hint": 77,
            "tags": ["china", "jiangsu", "science", "phase4"],
            "collector_config": {
                "source_intent": "province_science_department",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_science_department",
            },
        },
        {
            "source_id": "cn_trade_js_commerce_policy_v1",
            "display_name": "Jiangsu Commerce Department Policy",
            "base_url": "https://doc.jiangsu.gov.cn",
            "entry_url": "https://doc.jiangsu.gov.cn/col/col69879/index.html",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_commerce_template",
            "priority_hint": 77,
            "tags": ["china", "jiangsu", "commerce", "phase4"],
            "collector_config": {
                "source_intent": "province_commerce",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "province_commerce",
            },
        },
        {
            "source_id": "cn_policy_ah_portal_policy_v1",
            "display_name": "Anhui Government Policy Portal",
            "base_url": "https://www.ah.gov.cn",
            "entry_url": "https://www.ah.gov.cn/zcfg/index.html",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_portal_template",
            "priority_hint": 79,
            "tags": ["china", "anhui", "portal", "phase4"],
            "collector_config": {
                "source_intent": "province_government",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_government",
            },
        },
        {
            "source_id": "cn_policy_ah_industry_jx_v1",
            "display_name": "Anhui Industry and IT Department Notices",
            "base_url": "https://jx.ah.gov.cn",
            "entry_url": "https://jx.ah.gov.cn/public/column/22061",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_miit_template",
            "priority_hint": 78,
            "tags": ["china", "anhui", "industry", "phase4"],
            "collector_config": {
                "source_intent": "province_industry_department",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_industry_department",
            },
        },
        {
            "source_id": "cn_policy_ah_kjt_tzgg_v1",
            "display_name": "Anhui Science and Technology Department Notices",
            "base_url": "https://kjt.ah.gov.cn",
            "entry_url": "https://kjt.ah.gov.cn/xwzx/tzgg/index.html",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_science_template",
            "priority_hint": 77,
            "tags": ["china", "anhui", "science", "phase4"],
            "collector_config": {
                "source_intent": "province_science_department",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_science_department",
            },
        },
        {
            "source_id": "cn_trade_ah_commerce_policy_v1",
            "display_name": "Anhui Commerce Department Policy",
            "base_url": "https://commerce.ah.gov.cn",
            "entry_url": "https://commerce.ah.gov.cn/public/column/21701",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_commerce_template",
            "priority_hint": 77,
            "tags": ["china", "anhui", "commerce", "phase4"],
            "collector_config": {
                "source_intent": "province_commerce",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "province_commerce",
            },
        },
        {
            "source_id": "cn_policy_zj_portal_policy_v1",
            "display_name": "Zhejiang Government Policy Portal",
            "base_url": "https://www.zj.gov.cn",
            "entry_url": "https://www.zj.gov.cn/col/col1229017138/index.html",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_portal_template",
            "priority_hint": 79,
            "tags": ["china", "zhejiang", "portal", "phase4"],
            "collector_config": {
                "source_intent": "province_government",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_government",
            },
        },
        {
            "source_id": "cn_policy_zj_industry_jxt_v1",
            "display_name": "Zhejiang Economy and IT Department Notices",
            "base_url": "https://jxt.zj.gov.cn",
            "entry_url": "https://jxt.zj.gov.cn/col/col1229120577/index.html",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_miit_template",
            "priority_hint": 78,
            "tags": ["china", "zhejiang", "industry", "phase4"],
            "collector_config": {
                "source_intent": "province_industry_department",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_industry_department",
            },
        },
        {
            "source_id": "cn_policy_zj_science_kjt_v1",
            "display_name": "Zhejiang Science and Technology Department Notices",
            "base_url": "https://kjt.zj.gov.cn",
            "entry_url": "https://kjt.zj.gov.cn/col/col1228971342/index.html",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_science_template",
            "priority_hint": 77,
            "tags": ["china", "zhejiang", "science", "phase4"],
            "collector_config": {
                "source_intent": "province_science_department",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_science_department",
            },
        },
        {
            "source_id": "cn_trade_zj_commerce_policy_v1",
            "display_name": "Zhejiang Commerce Department Policy",
            "base_url": "https://zcom.zj.gov.cn",
            "entry_url": "https://zcom.zj.gov.cn/col/col1229251058/index.html",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_commerce_template",
            "priority_hint": 77,
            "tags": ["china", "zhejiang", "commerce", "phase4"],
            "collector_config": {
                "source_intent": "province_commerce",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "province_commerce",
            },
        },
        {
            "source_id": "cn_policy_sc_portal_policy_v1",
            "display_name": "Sichuan Government Policy Portal",
            "base_url": "https://www.sc.gov.cn",
            "entry_url": "https://www.sc.gov.cn/10462/c103045/zfwj.shtml",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_portal_template",
            "priority_hint": 79,
            "tags": ["china", "sichuan", "portal", "phase4"],
            "collector_config": {
                "source_intent": "province_government",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_government",
            },
        },
        {
            "source_id": "cn_policy_sc_industry_jxt_v1",
            "display_name": "Sichuan Economy and IT Department Notices",
            "base_url": "https://jxt.sc.gov.cn",
            "entry_url": "https://jxt.sc.gov.cn/scjxt/c100473/list.shtml",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_miit_template",
            "priority_hint": 78,
            "tags": ["china", "sichuan", "industry", "phase4"],
            "collector_config": {
                "source_intent": "province_industry_department",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_industry_department",
            },
        },
        {
            "source_id": "cn_policy_sc_science_kjt_v1",
            "display_name": "Sichuan Science and Technology Department Notices",
            "base_url": "https://kjt.sc.gov.cn",
            "entry_url": "https://kjt.sc.gov.cn/kjt/c100390/list.shtml",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_science_template",
            "priority_hint": 77,
            "tags": ["china", "sichuan", "science", "phase4"],
            "collector_config": {
                "source_intent": "province_science_department",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_science_department",
            },
        },
        {
            "source_id": "cn_trade_sc_commerce_policy_v1",
            "display_name": "Sichuan Commerce Department Policy",
            "base_url": "https://swt.sc.gov.cn",
            "entry_url": "https://swt.sc.gov.cn/sccom/c105281/list.shtml",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_commerce_template",
            "priority_hint": 77,
            "tags": ["china", "sichuan", "commerce", "phase4"],
            "collector_config": {
                "source_intent": "province_commerce",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "province_commerce",
            },
        },
        {
            "source_id": "cn_policy_sh_drc_fgw_v1",
            "display_name": "Shanghai DRC Notices",
            "base_url": "https://fgw.sh.gov.cn",
            "entry_url": "https://fgw.sh.gov.cn/fzggw/tzgg/index.html",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_drc_template",
            "priority_hint": 78,
            "tags": ["china", "shanghai", "drc", "phase4"],
            "collector_config": {
                "source_intent": "province_drc",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_drc",
            },
        },
        {
            "source_id": "cn_policy_sh_industry_sheitc_v1",
            "display_name": "Shanghai Economy and IT Commission Notices",
            "base_url": "https://sheitc.sh.gov.cn",
            "entry_url": "https://sheitc.sh.gov.cn/jxw/tzgg/",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_miit_template",
            "priority_hint": 78,
            "tags": ["china", "shanghai", "industry", "phase4"],
            "collector_config": {
                "source_intent": "province_industry_department",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_industry_department",
            },
        },
        {
            "source_id": "cn_policy_sh_stcsm_tzgg_v1",
            "display_name": "Shanghai Science and Technology Commission Notices",
            "base_url": "https://stcsm.sh.gov.cn",
            "entry_url": "https://stcsm.sh.gov.cn/zwgk/tzgg/",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_science_template",
            "priority_hint": 77,
            "tags": ["china", "shanghai", "science", "phase4"],
            "collector_config": {
                "source_intent": "province_science_department",
                "coverage_lane": "provincial_policy_rollout",
                "official_role": "province_science_department",
            },
        },
        {
            "source_id": "cn_trade_sh_commerce_policy_v1",
            "display_name": "Shanghai Commerce Commission Policy",
            "base_url": "https://sww.sh.gov.cn",
            "entry_url": "https://sww.sh.gov.cn/zwgk/zcfg/",
            "regional_level": RegionalLevel.PROVINCIAL,
            "source_role": SourceRole.SECONDARY,
            "template_family": "province_commerce_template",
            "priority_hint": 77,
            "tags": ["china", "shanghai", "commerce", "phase4"],
            "collector_config": {
                "source_intent": "province_commerce",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "province_commerce",
            },
        },
    ]

    data_specs: list[dict[str, Any]] = [
        {
            "source_id": "cn_data_gd_stats_bulletin_v1",
            "display_name": "Guangdong Statistics Bureau Data Bulletins",
            "base_url": "https://stats.gd.gov.cn",
            "entry_url": "https://stats.gd.gov.cn/tjsj/tjgb/",
            "priority_hint": 78,
            "tags": ["china", "guangdong", "stats", "phase4"],
            "collector_config": {
                "source_intent": "province_statistics",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "province_statistics",
            },
        },
        {
            "source_id": "cn_data_js_stats_bulletin_v1",
            "display_name": "Jiangsu Statistics Bureau Data Bulletins",
            "base_url": "https://tj.jiangsu.gov.cn",
            "entry_url": "https://tj.jiangsu.gov.cn/col/col40309/index.html",
            "priority_hint": 78,
            "tags": ["china", "jiangsu", "stats", "phase4"],
            "collector_config": {
                "source_intent": "province_statistics",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "province_statistics",
            },
        },
        {
            "source_id": "cn_data_nmg_stats_bulletin_v1",
            "display_name": "Inner Mongolia Statistics Bureau Data Bulletins",
            "base_url": "https://tj.nmg.gov.cn",
            "entry_url": "https://tj.nmg.gov.cn/tjyw/tjgb/",
            "priority_hint": 78,
            "tags": ["china", "inner-mongolia", "stats", "phase3"],
            "collector_config": {
                "source_intent": "province_statistics",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "province_statistics",
            },
            "selectors": {
                "list_item": ".dlp_glrtbody li",
                "detail_content": ".trs_editor_view, .trs_paper_default, body",
            },
        },
        {
            "source_id": "cn_data_ah_stats_bulletin_v1",
            "display_name": "Anhui Statistics Bureau Data Bulletins",
            "base_url": "https://tjj.ah.gov.cn",
            "entry_url": "https://tjj.ah.gov.cn/ssah/qwfbjd/tjgb/index.html",
            "priority_hint": 78,
            "tags": ["china", "anhui", "stats", "phase4"],
            "collector_config": {
                "source_intent": "province_statistics",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "province_statistics",
            },
        },
        {
            "source_id": "cn_data_zj_stats_bulletin_v1",
            "display_name": "Zhejiang Statistics Bureau Data Bulletins",
            "base_url": "https://tjj.zj.gov.cn",
            "entry_url": "https://tjj.zj.gov.cn/col/col1525563/index.html",
            "priority_hint": 78,
            "tags": ["china", "zhejiang", "stats", "phase4"],
            "collector_config": {
                "source_intent": "province_statistics",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "province_statistics",
            },
        },
        {
            "source_id": "cn_data_sc_stats_bulletin_v1",
            "display_name": "Sichuan Statistics Bureau Data Bulletins",
            "base_url": "https://tjj.sc.gov.cn",
            "entry_url": "https://tjj.sc.gov.cn/scstjj/c105855/list.shtml",
            "priority_hint": 78,
            "tags": ["china", "sichuan", "stats", "phase4"],
            "collector_config": {
                "source_intent": "province_statistics",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "province_statistics",
            },
        },
        {
            "source_id": "cn_data_sh_stats_bulletin_v1",
            "display_name": "Shanghai Statistics Bureau Data Bulletins",
            "base_url": "https://tjj.sh.gov.cn",
            "entry_url": "https://tjj.sh.gov.cn/tjnj/index.html",
            "priority_hint": 78,
            "tags": ["china", "shanghai", "stats", "phase4"],
            "collector_config": {
                "source_intent": "province_statistics",
                "coverage_lane": "statistics_or_industry_data",
                "official_role": "province_statistics",
            },
        },
    ]

    for spec in policy_specs:
        profiles.append(
            _build_policy_profile(
                source_id=spec["source_id"],
                display_name=spec["display_name"],
                base_url=spec["base_url"],
                entry_url=spec["entry_url"],
                governance_axis=GovernanceAxis.BLOCK,
                regional_level=spec["regional_level"],
                source_role=spec["source_role"],
                publisher_type=PublisherType.INSTITUTION,
                template_family=spec["template_family"],
                priority_hint=spec["priority_hint"],
                tags=spec["tags"],
                collector_config={
                    "phase": "phase4_national_provincial_backbone",
                    **spec["collector_config"],
                },
                enabled=enabled,
            )
        )

    for spec in data_specs:
        profiles.append(
            _build_data_profile(
                source_id=spec["source_id"],
                display_name=spec["display_name"],
                base_url=spec["base_url"],
                entry_url=spec["entry_url"],
                governance_axis=GovernanceAxis.BLOCK,
                regional_level=RegionalLevel.PROVINCIAL,
                source_role=SourceRole.SECONDARY,
                publisher_type=PublisherType.INSTITUTION,
                template_family="province_stats_template",
                priority_hint=spec["priority_hint"],
                tags=spec["tags"],
                collector_config=spec["collector_config"],
                selectors=spec.get("selectors"),
                enabled=enabled,
            )
        )

    return profiles
