from __future__ import annotations

from dataclasses import dataclass

from packages.sources.packs import list_source_packs


@dataclass(frozen=True)
class DomesticInventoryRow:
    report_code: str
    cluster: str
    rollout_layer: str
    priority_tier: str
    template_family: str
    execution_state: str
    source_key: str
    notes: str = ""


@dataclass(frozen=True)
class TemplateMappingRow:
    template_family: str
    report_template_name: str
    sample_sources: tuple[str, ...]
    reuse_target: str
    priority_tier: str


@dataclass(frozen=True)
class SampleSourceRow:
    source_id: str
    display_name: str
    template_family: str
    cluster: str
    report_codes: tuple[str, ...]
    state: str


_DOMESTIC_INVENTORY_ROWS: tuple[DomesticInventoryRow, ...] = (
    # L1: policy backbone
    DomesticInventoryRow(
        "C01",
        "central_policy_backbone",
        "L1",
        "P0",
        "policy_library_template",
        "executable",
        "cn_policy_state_council_zcwj_v1",
    ),
    DomesticInventoryRow(
        "C02",
        "central_policy_backbone",
        "L1",
        "P0",
        "policy_library_template",
        "executable",
        "cn_policy_ndrc_tzgg_v1",
    ),
    DomesticInventoryRow(
        "C03",
        "central_policy_backbone",
        "L1",
        "P0",
        "policy_library_template",
        "executable",
        "cn_policy_miit_tzgg_v1",
    ),
    DomesticInventoryRow(
        "C04",
        "central_policy_extension",
        "L1",
        "P1",
        "policy_library_template",
        "implementation_deferred",
        "cn_policy_mof_notice_generic",
    ),
    DomesticInventoryRow(
        "C05",
        "central_policy_extension",
        "L1",
        "P1",
        "policy_library_template",
        "implementation_deferred",
        "cn_policy_mofcom_notice_generic",
    ),
    DomesticInventoryRow(
        "C06",
        "central_policy_extension",
        "L1",
        "P1",
        "policy_library_template",
        "implementation_deferred",
        "cn_policy_mee_notice_generic",
    ),
    DomesticInventoryRow(
        "C07",
        "central_policy_extension",
        "L1",
        "P1",
        "policy_library_template",
        "implementation_deferred",
        "cn_policy_mnr_notice_generic",
    ),
    DomesticInventoryRow(
        "C08",
        "central_policy_extension",
        "L1",
        "P1",
        "policy_library_template",
        "implementation_deferred",
        "cn_policy_mara_notice_generic",
    ),
    DomesticInventoryRow(
        "C09",
        "central_policy_extension",
        "L1",
        "P2",
        "policy_library_template",
        "implementation_deferred",
        "cn_policy_most_notice_generic",
    ),
    DomesticInventoryRow(
        "C10",
        "central_policy_extension",
        "L1",
        "P2",
        "policy_library_template",
        "implementation_deferred",
        "cn_policy_mohurd_notice_generic",
    ),
    DomesticInventoryRow(
        "C11",
        "central_policy_extension",
        "L1",
        "P2",
        "policy_library_template",
        "implementation_deferred",
        "cn_policy_mot_notice_generic",
    ),
    DomesticInventoryRow(
        "C12",
        "macro_indicator_backbone",
        "L1",
        "P0",
        "data_table_template",
        "implementation_deferred",
        "cn_data_stats_nea_generic",
    ),
    DomesticInventoryRow(
        "C13",
        "macro_indicator_extension",
        "L1",
        "P2",
        "data_table_template",
        "implementation_deferred",
        "cn_data_ministry_generic",
    ),
    DomesticInventoryRow(
        "C14",
        "macro_indicator_backbone",
        "L1",
        "P0",
        "data_table_template",
        "implementation_deferred",
        "cn_data_nbs_indicator_generic",
    ),
    DomesticInventoryRow(
        "C15",
        "macro_indicator_backbone",
        "L1",
        "P0",
        "data_table_template",
        "implementation_deferred",
        "cn_data_customs_indicator_generic",
    ),
    DomesticInventoryRow(
        "C16",
        "macro_indicator_extension",
        "L1",
        "P2",
        "data_table_template",
        "implementation_deferred",
        "cn_data_pricing_monitor_generic",
    ),
    # L1: disclosure backbone
    DomesticInventoryRow(
        "C17",
        "official_disclosure_backbone",
        "L1",
        "P0",
        "disclosure_template",
        "executable",
        "cn_exchange_sse_notice_v1",
    ),
    DomesticInventoryRow(
        "C18",
        "official_disclosure_backbone",
        "L1",
        "P0",
        "disclosure_template",
        "executable",
        "cn_exchange_szse_notice_v1",
    ),
    DomesticInventoryRow(
        "C19",
        "official_disclosure_backbone",
        "L1",
        "P0",
        "disclosure_template",
        "executable",
        "cn_exchange_cninfo_announcement_v1",
    ),
    DomesticInventoryRow(
        "C20",
        "official_disclosure_extension",
        "L1",
        "P1",
        "disclosure_template",
        "implementation_deferred",
        "cn_exchange_bse_notice_generic",
    ),
    DomesticInventoryRow(
        "C21",
        "official_disclosure_extension",
        "L1",
        "P1",
        "disclosure_template",
        "implementation_deferred",
        "cn_exchange_neeq_notice_generic",
    ),
    DomesticInventoryRow(
        "C22",
        "official_disclosure_backbone",
        "L1",
        "P0",
        "disclosure_template",
        "implementation_deferred",
        "cn_bond_disclosure_generic",
    ),
    DomesticInventoryRow(
        "C23",
        "official_disclosure_backbone",
        "L1",
        "P0",
        "disclosure_template",
        "implementation_deferred",
        "cn_regulator_csrc_notice_generic",
    ),
    # L2: province/city/park
    DomesticInventoryRow(
        "C24",
        "province_backbone",
        "L2",
        "P0",
        "province_portal_template",
        "executable",
        "cn_policy_shanghai_portal_policy_v1",
    ),
    DomesticInventoryRow(
        "C25",
        "province_backbone",
        "L2",
        "P0",
        "province_drc_template",
        "executable",
        "cn_policy_zhejiang_drc_tzgg_v1",
    ),
    DomesticInventoryRow(
        "C26",
        "province_backbone",
        "L2",
        "P0",
        "province_miit_template",
        "executable",
        "cn_policy_js_gxt_zcwj_v1",
    ),
    DomesticInventoryRow(
        "C27",
        "province_extension",
        "L2",
        "P1",
        "data_table_template",
        "implementation_deferred",
        "cn_data_provincial_stats_generic",
    ),
    DomesticInventoryRow(
        "C28",
        "province_extension",
        "L2",
        "P1",
        "province_portal_template",
        "implementation_deferred",
        "cn_policy_provincial_eco_env_generic",
    ),
    DomesticInventoryRow(
        "C29",
        "city_rollout",
        "L2",
        "P1",
        "city_dept_template",
        "executable",
        "cn_policy_shenzhen_gxt_tzgg_v1",
    ),
    DomesticInventoryRow(
        "C30",
        "park_rollout",
        "L2",
        "P2",
        "park_template",
        "implementation_deferred",
        "cn_park_national_whitelist_generic",
    ),
    DomesticInventoryRow(
        "C31",
        "park_rollout",
        "L2",
        "P2",
        "park_template",
        "implementation_deferred",
        "cn_park_provincial_whitelist_generic",
    ),
    # L1/L2: project and transaction signals
    DomesticInventoryRow(
        "C32",
        "project_transaction_backbone",
        "L1",
        "P0",
        "project_query_template",
        "executable",
        "cn_project_ccgp_procurement_v1",
    ),
    DomesticInventoryRow(
        "C33",
        "project_transaction_backbone",
        "L1",
        "P0",
        "project_query_template",
        "executable",
        "cn_project_ggzy_trade_v1",
    ),
    DomesticInventoryRow(
        "C34",
        "project_transaction_backbone",
        "L1",
        "P0",
        "project_query_template",
        "executable",
        "cn_project_ndrc_approval_v1",
    ),
    DomesticInventoryRow(
        "C35",
        "project_transaction_extension",
        "L1",
        "P1",
        "project_query_template",
        "implementation_deferred",
        "cn_project_land_mining_generic",
    ),
    # L3: enterprise / association / supervision
    DomesticInventoryRow(
        "C36",
        "enterprise_enhancement",
        "L3",
        "P1",
        "disclosure_template",
        "implementation_deferred",
        "cn_enterprise_sasac_generic",
    ),
    DomesticInventoryRow(
        "C37",
        "enterprise_enhancement",
        "L3",
        "P1",
        "disclosure_template",
        "implementation_deferred",
        "cn_enterprise_central_soe_ir_generic",
    ),
    DomesticInventoryRow(
        "C38",
        "enterprise_enhancement",
        "L3",
        "P1",
        "disclosure_template",
        "implementation_deferred",
        "cn_enterprise_listed_ir_generic",
    ),
    DomesticInventoryRow(
        "C39",
        "association_enhancement",
        "L3",
        "P2",
        "association_template",
        "placeholder",
        "cn_industry_association_generic",
    ),
    DomesticInventoryRow(
        "C40",
        "association_enhancement",
        "L3",
        "P2",
        "association_template",
        "implementation_deferred",
        "cn_industry_alliance_generic",
    ),
    DomesticInventoryRow(
        "C41",
        "topic_enhancement",
        "L3",
        "P2",
        "association_template",
        "implementation_deferred",
        "cn_industry_topic_platform_generic",
    ),
    DomesticInventoryRow(
        "C42",
        "supervision_enhancement",
        "L3",
        "P1",
        "project_query_template",
        "implementation_deferred",
        "cn_supervision_credit_china_generic",
    ),
    DomesticInventoryRow(
        "C43",
        "supervision_enhancement",
        "L3",
        "P1",
        "project_query_template",
        "implementation_deferred",
        "cn_supervision_gsxt_generic",
    ),
    DomesticInventoryRow(
        "C44",
        "supervision_enhancement",
        "L3",
        "P1",
        "project_query_template",
        "implementation_deferred",
        "cn_supervision_judicial_open_generic",
    ),
    DomesticInventoryRow(
        "C45",
        "association_enhancement",
        "L3",
        "P2",
        "association_template",
        "implementation_deferred",
        "cn_industry_expo_forum_generic",
    ),
    DomesticInventoryRow(
        "C46",
        "association_enhancement",
        "L3",
        "P2",
        "association_template",
        "implementation_deferred",
        "cn_industry_whitepaper_topic_generic",
    ),
)


_TEMPLATE_MAPPING_ROWS: tuple[TemplateMappingRow, ...] = (
    TemplateMappingRow(
        template_family="policy_library_template",
        report_template_name="Policy Document Library",
        sample_sources=(
            "cn_policy_state_council_zcwj_v1",
            "cn_policy_ndrc_tzgg_v1",
            "cn_policy_miit_tzgg_v1",
        ),
        reuse_target="MOF/MOFCOM/MOHURD/MOT ministry lines",
        priority_tier="P0",
    ),
    TemplateMappingRow(
        template_family="disclosure_template",
        report_template_name="Exchange Disclosure",
        sample_sources=(
            "cn_exchange_sse_notice_v1",
            "cn_exchange_szse_notice_v1",
            "cn_exchange_cninfo_announcement_v1",
        ),
        reuse_target="BSE/NEEQ/IR/bond disclosure",
        priority_tier="P0",
    ),
    TemplateMappingRow(
        template_family="data_table_template",
        report_template_name="Structured Data Table",
        sample_sources=("cn_data_nbs_indicator_generic", "cn_data_customs_indicator_generic"),
        reuse_target="provincial stats and pricing monitor",
        priority_tier="P0",
    ),
    TemplateMappingRow(
        template_family="province_portal_template",
        report_template_name="Provincial Portal",
        sample_sources=("cn_policy_shanghai_portal_policy_v1",),
        reuse_target="province-level portal rollout",
        priority_tier="P1",
    ),
    TemplateMappingRow(
        template_family="province_drc_template",
        report_template_name="Provincial DRC",
        sample_sources=("cn_policy_zhejiang_drc_tzgg_v1", "cn_policy_gd_drc_tzgg_v1"),
        reuse_target="province DRC rollout",
        priority_tier="P0",
    ),
    TemplateMappingRow(
        template_family="province_miit_template",
        report_template_name="Provincial MIIT",
        sample_sources=("cn_policy_js_gxt_zcwj_v1", "cn_policy_hubei_gxt_tzgg_v1"),
        reuse_target="province MIIT rollout",
        priority_tier="P0",
    ),
    TemplateMappingRow(
        template_family="project_query_template",
        report_template_name="Project/Procurement Query",
        sample_sources=(
            "cn_project_ccgp_procurement_v1",
            "cn_project_ggzy_trade_v1",
            "cn_project_ndrc_approval_v1",
        ),
        reuse_target="approval and land/mining query systems",
        priority_tier="P0",
    ),
    TemplateMappingRow(
        template_family="city_dept_template",
        report_template_name="City Department",
        sample_sources=(
            "cn_policy_shenzhen_gxt_tzgg_v1",
            "cn_policy_suzhou_drc_tzgg_v1",
            "cn_policy_hangzhou_fgw_tzgg_v1",
            "cn_policy_wuhan_gxt_tzgg_v1",
        ),
        reuse_target="city-level rollout whitelist",
        priority_tier="P1",
    ),
    TemplateMappingRow(
        template_family="association_template",
        report_template_name="Association / Topic",
        sample_sources=("cn_industry_association_generic",),
        reuse_target="national association and thematic signals",
        priority_tier="P2",
    ),
    TemplateMappingRow(
        template_family="park_template",
        report_template_name="Park / Development Zone",
        sample_sources=("cn_park_national_whitelist_generic",),
        reuse_target="park whitelist rollout",
        priority_tier="P2",
    ),
)


_FIRST_WAVE_SAMPLE_SOURCES: tuple[SampleSourceRow, ...] = (
    SampleSourceRow(
        source_id="cn_policy_state_council_zcwj_v1",
        display_name="State Council Policy Library",
        template_family="policy_library_template",
        cluster="central_policy_backbone",
        report_codes=("C01",),
        state="beta",
    ),
    SampleSourceRow(
        source_id="cn_policy_ndrc_tzgg_v1",
        display_name="NDRC Notice",
        template_family="policy_library_template",
        cluster="central_policy_backbone",
        report_codes=("C02",),
        state="executable",
    ),
    SampleSourceRow(
        source_id="cn_policy_miit_tzgg_v1",
        display_name="MIIT Notice",
        template_family="policy_library_template",
        cluster="central_policy_backbone",
        report_codes=("C03",),
        state="beta",
    ),
    SampleSourceRow(
        source_id="cn_exchange_sse_notice_v1",
        display_name="SSE Notice",
        template_family="disclosure_template",
        cluster="official_disclosure_backbone",
        report_codes=("C17",),
        state="beta",
    ),
    SampleSourceRow(
        source_id="cn_exchange_szse_notice_v1",
        display_name="SZSE Notice",
        template_family="disclosure_template",
        cluster="official_disclosure_backbone",
        report_codes=("C18",),
        state="executable",
    ),
    SampleSourceRow(
        source_id="cn_exchange_cninfo_announcement_v1",
        display_name="CNINFO Announcement",
        template_family="disclosure_template",
        cluster="official_disclosure_backbone",
        report_codes=("C19",),
        state="beta",
    ),
    SampleSourceRow(
        source_id="cn_policy_gd_drc_tzgg_v1",
        display_name="Guangdong DRC",
        template_family="province_drc_template",
        cluster="province_backbone",
        report_codes=("C25",),
        state="beta",
    ),
    SampleSourceRow(
        source_id="cn_policy_js_gxt_zcwj_v1",
        display_name="Jiangsu MIIT",
        template_family="province_miit_template",
        cluster="province_backbone",
        report_codes=("C26",),
        state="beta",
    ),
    SampleSourceRow(
        source_id="cn_policy_shenzhen_gxt_tzgg_v1",
        display_name="Shenzhen MIIT",
        template_family="city_dept_template",
        cluster="city_rollout",
        report_codes=("C29",),
        state="beta",
    ),
    SampleSourceRow(
        source_id="cn_policy_hangzhou_fgw_tzgg_v1",
        display_name="Hangzhou DRC",
        template_family="city_dept_template",
        cluster="city_rollout",
        report_codes=("C29",),
        state="beta",
    ),
)


_FROZEN_TEMPLATE_FAMILIES: tuple[str, str] = (
    "policy_library_template",
    "disclosure_template",
)


def list_domestic_inventory_rows() -> list[DomesticInventoryRow]:
    return list(_DOMESTIC_INVENTORY_ROWS)


def list_template_mapping_rows() -> list[TemplateMappingRow]:
    return list(_TEMPLATE_MAPPING_ROWS)


def list_first_wave_sample_sources() -> list[SampleSourceRow]:
    return list(_FIRST_WAVE_SAMPLE_SOURCES)


def list_frozen_template_families() -> list[str]:
    return list(_FROZEN_TEMPLATE_FAMILIES)


def list_report_codes() -> list[str]:
    return [f"C{index:02d}" for index in range(1, 47)]


def list_inventory_report_codes() -> list[str]:
    return sorted({row.report_code for row in _DOMESTIC_INVENTORY_ROWS})


def list_pack_state_rows() -> list[dict[str, str | int]]:
    return [
        {
            "pack_id": pack.pack_id,
            "state": pack.state,
            "rollout_phase": pack.rollout_phase,
            "source_count": len(pack.source_ids),
            "template_families": ",".join(pack.template_families),
        }
        for pack in list_source_packs()
    ]


def list_executable_source_keys() -> list[str]:
    return [
        row.source_key for row in _DOMESTIC_INVENTORY_ROWS if row.execution_state == "executable"
    ]
