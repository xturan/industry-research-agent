from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SourcePack:
    pack_id: str
    display_name: str
    source_ids: tuple[str, ...]
    description: str
    default_max_documents_per_source: int = 3
    default_max_evidence_per_source: int = 2
    state: Literal["executable", "beta", "placeholder"] = "placeholder"
    rollout_phase: int = 0
    template_families: tuple[str, ...] = ()


SOURCE_PACKS: dict[str, SourcePack] = {
    "policy_pack_cn": SourcePack(
        pack_id="policy_pack_cn",
        display_name="CN Policy Pack",
        source_ids=("cn_policy_ndrc_tzgg_v1", "cn_policy_generic"),
        description="Policy-first domestic source pack for ministry notice/policy research.",
        default_max_documents_per_source=4,
        default_max_evidence_per_source=2,
        state="executable",
        rollout_phase=0,
        template_families=("policy_library_template",),
    ),
    "disclosure_pack_cn": SourcePack(
        pack_id="disclosure_pack_cn",
        display_name="CN Disclosure Pack",
        source_ids=("cn_exchange_szse_notice_v1", "cn_exchange_announcement_generic"),
        description="Disclosure-first domestic source pack for announcement/exchange flows.",
        default_max_documents_per_source=3,
        default_max_evidence_per_source=2,
        state="executable",
        rollout_phase=0,
        template_families=("disclosure_template",),
    ),
    "local_rollout_pack_cn": SourcePack(
        pack_id="local_rollout_pack_cn",
        display_name="CN Local Rollout Pack",
        source_ids=("cn_policy_generic", "cn_industry_association_generic"),
        description="Domestic pack for local project rollout/industry landing tracking.",
        default_max_documents_per_source=2,
        default_max_evidence_per_source=2,
        state="beta",
        rollout_phase=0,
        template_families=(
            "province_portal_template",
            "city_dept_template",
        ),
    ),
    "local_rollout_pack_cn_v2": SourcePack(
        pack_id="local_rollout_pack_cn_v2",
        display_name="CN Local Rollout Pack v2",
        source_ids=(
            "cn_policy_anhui_drc_tzgg_v1",
            "cn_policy_shandong_gxt_tzgg_v1",
            "cn_policy_fujian_drc_tzgg_v1",
            "cn_policy_henan_gxt_tzgg_v1",
            "cn_policy_gd_drc_tzgg_v1",
            "cn_policy_js_gxt_zcwj_v1",
            "cn_policy_zhejiang_drc_tzgg_v1",
            "cn_policy_hubei_gxt_tzgg_v1",
            "cn_policy_sichuan_drc_tzgg_v1",
            "cn_policy_shanghai_portal_policy_v1",
            "cn_policy_shenzhen_gxt_tzgg_v1",
            "cn_policy_hangzhou_fgw_tzgg_v1",
            "cn_industry_association_generic",
        ),
        description=(
            "Provincial/local rollout v2 pack using template-first replication "
            "for DRC/MIIT/portal/city lines."
        ),
        default_max_documents_per_source=2,
        default_max_evidence_per_source=2,
        state="executable",
        rollout_phase=3,
        template_families=(
            "province_portal_template",
            "province_drc_template",
            "province_miit_template",
            "city_dept_template",
        ),
    ),
    "policy_data_backbone_pack_cn_v1": SourcePack(
        pack_id="policy_data_backbone_pack_cn_v1",
        display_name="CN Policy Data Backbone Pack v1",
        source_ids=(
            "cn_policy_state_council_zcwj_v1",
            "cn_policy_ndrc_tzgg_v1",
            "cn_policy_miit_tzgg_v1",
            "cn_policy_most_tzgg_v1",
            "cn_data_stats_national_v1",
            "cn_data_customs_trade_v1",
            "cn_trade_mofcom_policy_v1",
            "cn_policy_gd_portal_policy_v1",
            "cn_policy_gd_drc_tzgg_v1",
            "cn_policy_gd_industry_gdii_v1",
            "cn_data_gd_stats_bulletin_v1",
            "cn_policy_gd_stc_gdstc_v1",
            "cn_trade_gd_commerce_policy_v1",
            "cn_policy_js_portal_policy_v1",
            "cn_policy_js_drc_fzggw_v1",
            "cn_policy_js_gxt_zcwj_v1",
            "cn_data_js_stats_bulletin_v1",
            "cn_policy_js_science_kxjst_v1",
            "cn_trade_js_commerce_policy_v1",
            "cn_policy_ah_portal_policy_v1",
            "cn_policy_anhui_drc_tzgg_v1",
            "cn_policy_ah_industry_jx_v1",
            "cn_data_ah_stats_bulletin_v1",
            "cn_policy_ah_kjt_tzgg_v1",
            "cn_trade_ah_commerce_policy_v1",
            "cn_policy_zj_portal_policy_v1",
            "cn_policy_zhejiang_drc_tzgg_v1",
            "cn_policy_zj_industry_jxt_v1",
            "cn_data_zj_stats_bulletin_v1",
            "cn_policy_zj_science_kjt_v1",
            "cn_trade_zj_commerce_policy_v1",
            "cn_policy_sc_portal_policy_v1",
            "cn_policy_sichuan_drc_tzgg_v1",
            "cn_policy_sc_industry_jxt_v1",
            "cn_data_sc_stats_bulletin_v1",
            "cn_policy_sc_science_kjt_v1",
            "cn_trade_sc_commerce_policy_v1",
            "cn_policy_shanghai_portal_policy_v1",
            "cn_policy_sh_drc_fgw_v1",
            "cn_policy_sh_industry_sheitc_v1",
            "cn_data_sh_stats_bulletin_v1",
            "cn_policy_sh_stcsm_tzgg_v1",
            "cn_trade_sh_commerce_policy_v1",
        ),
        description=(
            "Phase-4 national/provincial policy and data backbone pack. "
            "Contains only national and provincial official sources."
        ),
        default_max_documents_per_source=3,
        default_max_evidence_per_source=2,
        state="executable",
        rollout_phase=4,
        template_families=(
            "policy_library_template",
            "province_portal_template",
            "province_drc_template",
            "province_miit_template",
            "province_stats_template",
            "province_science_template",
            "province_commerce_template",
            "national_stats_template",
            "national_customs_template",
        ),
    ),
    "city_park_pack_cn_v1": SourcePack(
        pack_id="city_park_pack_cn_v1",
        display_name="CN City and Park Pack v1",
        source_ids=(
            "cn_policy_shenzhen_gxt_tzgg_v1",
            "cn_policy_suzhou_drc_tzgg_v1",
            "cn_policy_hangzhou_fgw_tzgg_v1",
            "cn_policy_wuhan_gxt_tzgg_v1",
            "cn_policy_guangzhou_gxt_tzgg_v1",
            "cn_policy_nanjing_gxt_tzgg_v1",
            "cn_policy_chengdu_jxj_tzgg_v1",
            "cn_park_sh_lingang_tzgg_v1",
        ),
        description=(
            "City and park rollout pack for regional implementation and "
            "industrial park intelligence."
        ),
        default_max_documents_per_source=2,
        default_max_evidence_per_source=2,
        state="executable",
        rollout_phase=4,
        template_families=(
            "city_dept_template",
            "park_template",
        ),
    ),
    "industry_signal_pack_cn": SourcePack(
        pack_id="industry_signal_pack_cn",
        display_name="CN Industry Signal Pack",
        source_ids=("cn_industry_association_generic", "cn_policy_ndrc_tzgg_v1"),
        description="Domestic pack for industry trend and policy-signal blending.",
        default_max_documents_per_source=2,
        default_max_evidence_per_source=3,
        state="placeholder",
        rollout_phase=0,
        template_families=("association_template",),
    ),
    "industry_signal_pack_cn_v2": SourcePack(
        pack_id="industry_signal_pack_cn_v2",
        display_name="CN Industry Signal Pack v2",
        source_ids=(
            "cn_industry_caam_news_v1",
            "cn_industry_ces_report_v1",
            "cn_policy_ndrc_tzgg_v1",
            "cn_exchange_sse_notice_v1",
        ),
        description=(
            "Industry enhancement pack combining association-topic evidence "
            "with policy/disclosure anchors."
        ),
        default_max_documents_per_source=2,
        default_max_evidence_per_source=2,
        state="executable",
        rollout_phase=5,
        template_families=("association_template",),
    ),
    "policy_pack_cn_v2": SourcePack(
        pack_id="policy_pack_cn_v2",
        display_name="CN Policy Pack v2",
        source_ids=(
            "cn_policy_state_council_zcwj_v1",
            "cn_policy_ndrc_tzgg_v1",
            "cn_policy_miit_tzgg_v1",
            "cn_policy_generic",
        ),
        description=(
            "Policy backbone v2 pack for ministry-level policy retrieval "
            "(State Council + NDRC + MIIT)."
        ),
        default_max_documents_per_source=4,
        default_max_evidence_per_source=3,
        state="executable",
        rollout_phase=2,
        template_families=("policy_library_template",),
    ),
    "disclosure_pack_cn_v2": SourcePack(
        pack_id="disclosure_pack_cn_v2",
        display_name="CN Disclosure Pack v2",
        source_ids=(
            "cn_exchange_sse_notice_v1",
            "cn_exchange_szse_notice_v1",
            "cn_exchange_cninfo_announcement_v1",
            "cn_exchange_announcement_generic",
        ),
        description=(
            "Disclosure backbone v2 pack for SSE/SZSE/CNINFO announcement "
            "and exchange disclosure flows."
        ),
        default_max_documents_per_source=4,
        default_max_evidence_per_source=3,
        state="executable",
        rollout_phase=2,
        template_families=("disclosure_template",),
    ),
    "project_signal_pack_cn_v1": SourcePack(
        pack_id="project_signal_pack_cn_v1",
        display_name="CN Project Signal Pack v1",
        source_ids=(
            "cn_project_ccgp_procurement_v1",
            "cn_project_ggzy_trade_v1",
            "cn_project_ndrc_approval_v1",
        ),
        description=(
            "Project/transaction backbone pack for government procurement, "
            "public resource exchange, and project approval signals."
        ),
        default_max_documents_per_source=3,
        default_max_evidence_per_source=2,
        state="executable",
        rollout_phase=2,
        template_families=("project_query_template",),
    ),
    "phase1_sample_pack_cn": SourcePack(
        pack_id="phase1_sample_pack_cn",
        display_name="CN Phase1 Sample Pack",
        source_ids=(
            "cn_policy_state_council_zcwj_v1",
            "cn_policy_ndrc_tzgg_v1",
            "cn_policy_miit_tzgg_v1",
            "cn_exchange_sse_notice_v1",
            "cn_exchange_szse_notice_v1",
            "cn_exchange_cninfo_announcement_v1",
            "cn_policy_gd_drc_tzgg_v1",
            "cn_policy_js_gxt_zcwj_v1",
            "cn_policy_shenzhen_gxt_tzgg_v1",
            "cn_policy_hangzhou_fgw_tzgg_v1",
        ),
        description=(
            "Phase1 sample-validation pack covering policy/disclosure/provincial/city "
            "template families."
        ),
        default_max_documents_per_source=3,
        default_max_evidence_per_source=2,
        state="beta",
        rollout_phase=1,
        template_families=(
            "policy_library_template",
            "disclosure_template",
            "province_drc_template",
            "province_miit_template",
            "city_dept_template",
        ),
    ),
}

SOURCE_STRATEGY_TO_PACK = {
    "cn_policy_first": "policy_pack_cn",
    "cn_disclosure_first": "disclosure_pack_cn",
    "cn_local_rollout": "local_rollout_pack_cn",
    "cn_local_rollout_v2": "local_rollout_pack_cn_v2",
    "cn_policy_data_backbone_v1": "policy_data_backbone_pack_cn_v1",
    "cn_city_park_rollout": "city_park_pack_cn_v1",
    "cn_industry_signal": "industry_signal_pack_cn",
    "cn_industry_signal_v2": "industry_signal_pack_cn_v2",
    "cn_policy_first_v2": "policy_pack_cn_v2",
    "cn_disclosure_first_v2": "disclosure_pack_cn_v2",
    "cn_project_signal": "project_signal_pack_cn_v1",
    "cn_phase1_samples": "phase1_sample_pack_cn",
}


def get_source_pack(pack_id: str | None) -> SourcePack | None:
    if pack_id is None:
        return None
    return SOURCE_PACKS.get(pack_id.strip())


def list_source_packs() -> list[SourcePack]:
    return [SOURCE_PACKS[key] for key in sorted(SOURCE_PACKS.keys())]


def list_source_packs_by_state(
    state: Literal["executable", "beta", "placeholder"] | None = None,
) -> list[SourcePack]:
    if state is None:
        return list_source_packs()
    return [pack for pack in list_source_packs() if pack.state == state]


def resolve_strategy_pack(source_strategy: str | None) -> SourcePack | None:
    if source_strategy is None:
        return None
    mapped = SOURCE_STRATEGY_TO_PACK.get(source_strategy.strip())
    if mapped is None:
        return None
    return SOURCE_PACKS.get(mapped)
