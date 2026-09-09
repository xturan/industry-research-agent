from __future__ import annotations

from typing import NamedTuple

from packages.sources.enums import (
    GovernanceAxis,
    InfoType,
    LineFamily,
    QueryType,
    RegionalLevel,
    SourceRole,
)
from packages.sources.packs import get_source_pack, resolve_strategy_pack
from packages.sources.schemas import (
    QueryContext,
    RoutingRecommendation,
    SourcePerformanceItem,
    SourceProfile,
)


class _RuleMatch(NamedTuple):
    source_id: str
    reason: str
    base_rule_score: float
    matched_terms: list[str]
    selected_via: str = "routing_logic"


class SourceRouter:
    MACRO_KEYWORDS = (
        "macro",
        "gdp",
        "cpi",
        "inflation",
        "population",
        "unemployment",
    )
    ENERGY_KEYWORDS = (
        "oil",
        "gas",
        "electricity",
        "inventory",
        "energy",
        "crude",
    )
    FILING_KEYWORDS = (
        "filing",
        "annual report",
        "10-k",
        "10-q",
        "ticker",
        "sec",
        "earnings",
    )
    HEALTH_KEYWORDS = (
        "health",
        "mortality",
        "disease",
        "life expectancy",
        "epidemiology",
    )
    DOMESTIC_POLICY_KEYWORDS = (
        "policy",
        "notice",
        "guidance",
        "\u90e8\u59d4",
        "\u653f\u7b56",
        "\u901a\u77e5",
    )
    DOMESTIC_EXCHANGE_KEYWORDS = (
        "announcement",
        "disclosure",
        "exchange",
        "\u516c\u544a",
        "\u62ab\u9732",
        "\u5e74\u62a5",
    )
    DOMESTIC_INDUSTRY_KEYWORDS = (
        "association",
        "alliance",
        "industry report",
        "\u534f\u4f1a",
        "\u8054\u76df",
        "\u767d\u76ae\u4e66",
    )
    DOMESTIC_DATA_KEYWORDS = (
        "statistics",
        "data",
        "export",
        "trade",
        "customs",
        "commerce",
        "\u7edf\u8ba1",
        "\u6570\u636e",
        "\u89c4\u6a21",
        "\u4f01\u4e1a\u6570\u91cf",
        "\u51fa\u53e3",
        "\u8d38\u6613",
        "\u6d77\u5173",
        "\u5916\u8d38",
        "\u5546\u52a1",
    )
    LOCAL_ROLLOUT_KEYWORDS = (
        "local",
        "regional",
        "pilot",
        "rollout",
        "\u5730\u65b9",
        "\u7701",
        "\u5e02",
        "\u8bd5\u70b9",
        "\u843d\u5730",
        "\u9879\u76ee",
    )
    PROJECT_SIGNAL_KEYWORDS = (
        "procurement",
        "bidding",
        "tender",
        "project approval",
        "public resource",
        "government purchase",
        "\u653f\u5e9c\u91c7\u8d2d",
        "\u516c\u5171\u8d44\u6e90\u4ea4\u6613",
        "\u6295\u8d44\u9879\u76ee\u5ba1\u6279",
        "\u62db\u6807",
        "\u4e2d\u6807",
        "\u9879\u76ee",
    )
    INDUSTRY_TREND_KEYWORDS = (
        "industry trend",
        "outlook",
        "signal",
        "\u884c\u4e1a",
        "\u8d8b\u52bf",
        "\u666f\u6c14",
        "\u4fe1\u53f7",
        "\u767d\u76ae\u4e66",
        "\u534f\u4f1a",
    )

    TRUST_BONUS = {
        "sec_edgar": 8.0,
        "world_bank": 7.0,
        "eia": 7.0,
        "who_gho": 7.0,
        "user_input": 2.0,
        "cn_policy_ndrc_tzgg_v1": 8.0,
        "cn_policy_state_council_zcwj_v1": 8.0,
        "cn_policy_miit_tzgg_v1": 7.5,
        "cn_policy_most_tzgg_v1": 7.5,
        "cn_data_stats_national_v1": 7.5,
        "cn_data_customs_trade_v1": 7.5,
        "cn_trade_mofcom_policy_v1": 7.5,
        "cn_exchange_szse_notice_v1": 7.0,
        "cn_exchange_sse_notice_v1": 7.0,
        "cn_exchange_cninfo_announcement_v1": 6.5,
        "cn_policy_gd_portal_policy_v1": 6.5,
        "cn_policy_gd_drc_tzgg_v1": 6.5,
        "cn_policy_gd_industry_gdii_v1": 6.5,
        "cn_data_gd_stats_bulletin_v1": 6.5,
        "cn_policy_gd_stc_gdstc_v1": 6.5,
        "cn_trade_gd_commerce_policy_v1": 6.5,
        "cn_policy_js_portal_policy_v1": 6.5,
        "cn_policy_js_drc_fzggw_v1": 6.5,
        "cn_policy_js_gxt_zcwj_v1": 6.5,
        "cn_data_js_stats_bulletin_v1": 6.5,
        "cn_policy_js_science_kxjst_v1": 6.5,
        "cn_trade_js_commerce_policy_v1": 6.5,
        "cn_policy_ah_portal_policy_v1": 6.5,
        "cn_policy_ah_industry_jx_v1": 6.5,
        "cn_data_ah_stats_bulletin_v1": 6.5,
        "cn_policy_ah_kjt_tzgg_v1": 6.5,
        "cn_trade_ah_commerce_policy_v1": 6.5,
        "cn_policy_zj_portal_policy_v1": 6.5,
        "cn_policy_zj_industry_jxt_v1": 6.5,
        "cn_data_zj_stats_bulletin_v1": 6.5,
        "cn_policy_zj_science_kjt_v1": 6.5,
        "cn_trade_zj_commerce_policy_v1": 6.5,
        "cn_policy_zhejiang_drc_tzgg_v1": 6.5,
        "cn_policy_hubei_gxt_tzgg_v1": 6.0,
        "cn_policy_sc_portal_policy_v1": 6.5,
        "cn_policy_sc_industry_jxt_v1": 6.5,
        "cn_data_sc_stats_bulletin_v1": 6.5,
        "cn_policy_sc_science_kjt_v1": 6.5,
        "cn_trade_sc_commerce_policy_v1": 6.5,
        "cn_policy_sichuan_drc_tzgg_v1": 6.0,
        "cn_policy_shanghai_portal_policy_v1": 6.0,
        "cn_policy_sh_drc_fgw_v1": 6.5,
        "cn_policy_sh_industry_sheitc_v1": 6.5,
        "cn_data_sh_stats_bulletin_v1": 6.5,
        "cn_policy_sh_stcsm_tzgg_v1": 6.5,
        "cn_trade_sh_commerce_policy_v1": 6.5,
        "cn_policy_shenzhen_gxt_tzgg_v1": 6.0,
        "cn_policy_suzhou_drc_tzgg_v1": 6.0,
        "cn_policy_hangzhou_fgw_tzgg_v1": 6.0,
        "cn_policy_wuhan_gxt_tzgg_v1": 6.0,
        "cn_policy_anhui_drc_tzgg_v1": 6.5,
        "cn_policy_shandong_gxt_tzgg_v1": 6.5,
        "cn_policy_fujian_drc_tzgg_v1": 6.0,
        "cn_policy_henan_gxt_tzgg_v1": 6.0,
        "cn_policy_guangzhou_gxt_tzgg_v1": 6.0,
        "cn_policy_nanjing_gxt_tzgg_v1": 6.0,
        "cn_policy_chengdu_jxj_tzgg_v1": 6.0,
        "cn_park_sh_lingang_tzgg_v1": 5.5,
        "cn_project_ccgp_procurement_v1": 7.0,
        "cn_project_ggzy_trade_v1": 7.0,
        "cn_project_ndrc_approval_v1": 7.5,
        "cn_industry_caam_news_v1": 5.5,
        "cn_industry_ces_report_v1": 5.5,
        "cn_policy_generic": 8.0,
        "cn_exchange_announcement_generic": 7.0,
        "cn_industry_association_generic": 5.0,
    }

    QUERY_FIT_BONUS = {
        QueryType.MACRO: {"world_bank": 14.0},
        QueryType.ENERGY: {"eia": 14.0},
        QueryType.FILING: {"sec_edgar": 14.0},
        QueryType.HEALTH: {"who_gho": 14.0},
        QueryType.GENERAL: {},
    }

    def __init__(self, *, include_domestic_profiles: bool = False) -> None:
        self.include_domestic_profiles = include_domestic_profiles

    def classify_query_type(self, query_context: QueryContext) -> tuple[QueryType, list[str]]:
        query = query_context.query.lower()
        matches = {
            QueryType.MACRO: self._matched_terms(query, self.MACRO_KEYWORDS),
            QueryType.ENERGY: self._matched_terms(query, self.ENERGY_KEYWORDS),
            QueryType.FILING: self._matched_terms(query, self.FILING_KEYWORDS),
            QueryType.HEALTH: self._matched_terms(query, self.HEALTH_KEYWORDS),
        }
        if query_context.tickers:
            matches[QueryType.FILING] = [
                *matches[QueryType.FILING],
                "ticker_context",
            ]

        ranked = sorted(
            matches.items(),
            key=lambda item: (len(item[1]), item[0].value),
            reverse=True,
        )
        best_type, best_terms = ranked[0]
        if not best_terms:
            return QueryType.GENERAL, []
        return best_type, sorted(set(best_terms))

    def route(
        self,
        query_context: QueryContext,
        *,
        performance_by_source: dict[str, SourcePerformanceItem] | None = None,
        profiles_by_source: dict[str, SourceProfile] | None = None,
    ) -> list[RoutingRecommendation]:
        performance_by_source = performance_by_source or {}
        profiles_by_source = profiles_by_source or {}
        query = query_context.query.lower()
        query_type, query_terms = self.classify_query_type(query_context)
        include_domestic_profiles = self.include_domestic_profiles or bool(
            query_context.metadata.get("include_domestic_profiles")
        )
        source_strategy = (
            query_context.source_strategy
            or str(query_context.metadata.get("source_strategy") or "").strip()
            or None
        )
        domestic_mode = (
            query_context.domestic_mode
            or str(query_context.metadata.get("domestic_mode") or "").strip()
            or None
        )
        regional_focus = [
            value.strip().lower()
            for value in (
                query_context.regional_focus or query_context.metadata.get("regional_focus") or []
            )
            if isinstance(value, str) and value.strip()
        ]

        candidates: dict[str, _RuleMatch] = {}
        requested_pack_id = (
            query_context.source_pack
            or str(query_context.metadata.get("source_pack") or "").strip()
            or None
        )
        requested_pack = get_source_pack(requested_pack_id)
        strategy_pack = None
        if requested_pack is None:
            strategy_pack = resolve_strategy_pack(source_strategy)
            if strategy_pack is not None:
                requested_pack = strategy_pack
                include_domestic_profiles = True
        if query_context.user_provided_sources:
            candidates["user_input"] = _RuleMatch(
                source_id="user_input",
                reason="user_provided_sources present; prioritize user context.",
                base_rule_score=95.0,
                matched_terms=["user_provided_sources"],
                selected_via="user_provided_sources",
            )
        if requested_pack is not None:
            for index, source_id in enumerate(requested_pack.source_ids):
                selected_via = "source_pack"
                if strategy_pack is not None and source_strategy is not None:
                    selected_via = "source_strategy"
                candidates[source_id] = _RuleMatch(
                    source_id=source_id,
                    reason=(
                        f"Selected by source_pack={requested_pack.pack_id} "
                        f"({requested_pack.display_name})."
                    ),
                    base_rule_score=84.0 - float(index),
                    matched_terms=[f"source_pack:{requested_pack.pack_id}"],
                    selected_via=selected_via,
                )

        macro_terms = self._matched_terms(query, self.MACRO_KEYWORDS)
        if macro_terms:
            candidates.setdefault(
                "world_bank",
                _RuleMatch(
                    source_id="world_bank",
                    reason="Matched macro/GDP/CPI/population keywords.",
                    base_rule_score=90.0,
                    matched_terms=macro_terms,
                ),
            )

        energy_terms = self._matched_terms(query, self.ENERGY_KEYWORDS)
        if energy_terms:
            candidates.setdefault(
                "eia",
                _RuleMatch(
                    source_id="eia",
                    reason="Matched energy/oil/gas/electricity/inventory keywords.",
                    base_rule_score=92.0,
                    matched_terms=energy_terms,
                ),
            )

        filing_terms = self._matched_terms(query, self.FILING_KEYWORDS)
        if filing_terms or query_context.tickers:
            terms = filing_terms if filing_terms else ["ticker_context"]
            candidates.setdefault(
                "sec_edgar",
                _RuleMatch(
                    source_id="sec_edgar",
                    reason="Matched filing/ticker/10-K/10-Q keywords.",
                    base_rule_score=95.0,
                    matched_terms=terms,
                ),
            )

        health_terms = self._matched_terms(query, self.HEALTH_KEYWORDS)
        if health_terms:
            candidates.setdefault(
                "who_gho",
                _RuleMatch(
                    source_id="who_gho",
                    reason="Matched health/mortality/disease/life expectancy keywords.",
                    base_rule_score=88.0,
                    matched_terms=health_terms,
                ),
            )

        if include_domestic_profiles:
            policy_terms = self._matched_terms(query, self.DOMESTIC_POLICY_KEYWORDS)
            if policy_terms:
                candidates.setdefault(
                    "cn_policy_ndrc_tzgg_v1",
                    _RuleMatch(
                        source_id="cn_policy_ndrc_tzgg_v1",
                        reason="Matched domestic policy/notice/guidance keywords.",
                        base_rule_score=91.0,
                        matched_terms=policy_terms,
                    ),
                )
                candidates.setdefault(
                    "cn_policy_state_council_zcwj_v1",
                    _RuleMatch(
                        source_id="cn_policy_state_council_zcwj_v1",
                        reason=(
                            "Matched domestic policy/notice keywords for "
                            "State Council policy library."
                        ),
                        base_rule_score=90.0,
                        matched_terms=policy_terms,
                    ),
                )
                candidates.setdefault(
                    "cn_policy_miit_tzgg_v1",
                    _RuleMatch(
                        source_id="cn_policy_miit_tzgg_v1",
                        reason="Matched domestic policy/notice keywords for MIIT notice line.",
                        base_rule_score=89.0,
                        matched_terms=policy_terms,
                    ),
                )
                candidates.setdefault(
                    "cn_policy_most_tzgg_v1",
                    _RuleMatch(
                        source_id="cn_policy_most_tzgg_v1",
                        reason="Matched domestic policy/notice keywords for MOST notice line.",
                        base_rule_score=88.5,
                        matched_terms=policy_terms,
                    ),
                )

            exchange_terms = self._matched_terms(query, self.DOMESTIC_EXCHANGE_KEYWORDS)
            if exchange_terms:
                candidates.setdefault(
                    "cn_exchange_szse_notice_v1",
                    _RuleMatch(
                        source_id="cn_exchange_szse_notice_v1",
                        reason="Matched domestic exchange/announcement/disclosure keywords.",
                        base_rule_score=90.0,
                        matched_terms=exchange_terms,
                    ),
                )
                candidates.setdefault(
                    "cn_exchange_sse_notice_v1",
                    _RuleMatch(
                        source_id="cn_exchange_sse_notice_v1",
                        reason="Matched domestic exchange/disclosure keywords for SSE notices.",
                        base_rule_score=89.0,
                        matched_terms=exchange_terms,
                    ),
                )
                candidates.setdefault(
                    "cn_exchange_cninfo_announcement_v1",
                    _RuleMatch(
                        source_id="cn_exchange_cninfo_announcement_v1",
                        reason=(
                            "Matched domestic exchange/disclosure keywords for "
                            "CNINFO announcements."
                        ),
                        base_rule_score=88.0,
                        matched_terms=exchange_terms,
                    ),
                )

            industry_terms = self._matched_terms(query, self.DOMESTIC_INDUSTRY_KEYWORDS)
            if industry_terms:
                candidates.setdefault(
                    "cn_industry_association_generic",
                    _RuleMatch(
                        source_id="cn_industry_association_generic",
                        reason="Matched domestic association/alliance/industry-report keywords.",
                        base_rule_score=89.0,
                        matched_terms=industry_terms,
                    ),
                )
                candidates.setdefault(
                    "cn_industry_caam_news_v1",
                    _RuleMatch(
                        source_id="cn_industry_caam_news_v1",
                        reason="Matched industry trend keywords for CAAM signal source.",
                        base_rule_score=88.0,
                        matched_terms=industry_terms,
                    ),
                )
                candidates.setdefault(
                    "cn_industry_ces_report_v1",
                    _RuleMatch(
                        source_id="cn_industry_ces_report_v1",
                        reason="Matched industry trend keywords for CES report source.",
                        base_rule_score=87.0,
                        matched_terms=industry_terms,
                    ),
                )
            local_rollout_terms = self._matched_terms(query, self.LOCAL_ROLLOUT_KEYWORDS)
            if local_rollout_terms:
                candidates.setdefault(
                    "cn_policy_generic",
                    _RuleMatch(
                        source_id="cn_policy_generic",
                        reason="Matched domestic local-rollout/project implementation keywords.",
                        base_rule_score=88.0,
                        matched_terms=local_rollout_terms,
                    ),
                )
                candidates.setdefault(
                    "cn_industry_association_generic",
                    _RuleMatch(
                        source_id="cn_industry_association_generic",
                        reason="Matched domestic local-rollout/project implementation keywords.",
                        base_rule_score=87.0,
                        matched_terms=local_rollout_terms,
                    ),
                )

            data_terms = self._matched_terms(query, self.DOMESTIC_DATA_KEYWORDS)
            if data_terms:
                candidates.setdefault(
                    "cn_data_stats_national_v1",
                    _RuleMatch(
                        source_id="cn_data_stats_national_v1",
                        reason="Matched data/statistics keywords for NBS backbone source.",
                        base_rule_score=89.0,
                        matched_terms=data_terms,
                    ),
                )
                candidates.setdefault(
                    "cn_data_customs_trade_v1",
                    _RuleMatch(
                        source_id="cn_data_customs_trade_v1",
                        reason="Matched customs/trade/export keywords for customs backbone source.",
                        base_rule_score=88.5,
                        matched_terms=data_terms,
                    ),
                )
                candidates.setdefault(
                    "cn_trade_mofcom_policy_v1",
                    _RuleMatch(
                        source_id="cn_trade_mofcom_policy_v1",
                        reason="Matched customs/trade/export keywords for MOFCOM backbone source.",
                        base_rule_score=88.0,
                        matched_terms=data_terms,
                    ),
                )

            provincial_backbone_candidates = {
                "\u5e7f\u4e1c": (
                    "cn_policy_gd_portal_policy_v1",
                    "cn_policy_gd_drc_tzgg_v1",
                    "cn_policy_gd_industry_gdii_v1",
                    "cn_data_gd_stats_bulletin_v1",
                    "cn_policy_gd_stc_gdstc_v1",
                    "cn_trade_gd_commerce_policy_v1",
                ),
                "\u6c5f\u82cf": (
                    "cn_policy_js_portal_policy_v1",
                    "cn_policy_js_drc_fzggw_v1",
                    "cn_policy_js_gxt_zcwj_v1",
                    "cn_data_js_stats_bulletin_v1",
                    "cn_policy_js_science_kxjst_v1",
                    "cn_trade_js_commerce_policy_v1",
                ),
                "\u5b89\u5fbd": (
                    "cn_policy_ah_portal_policy_v1",
                    "cn_policy_anhui_drc_tzgg_v1",
                    "cn_policy_ah_industry_jx_v1",
                    "cn_data_ah_stats_bulletin_v1",
                    "cn_policy_ah_kjt_tzgg_v1",
                    "cn_trade_ah_commerce_policy_v1",
                ),
                "\u6d59\u6c5f": (
                    "cn_policy_zj_portal_policy_v1",
                    "cn_policy_zhejiang_drc_tzgg_v1",
                    "cn_policy_zj_industry_jxt_v1",
                    "cn_data_zj_stats_bulletin_v1",
                    "cn_policy_zj_science_kjt_v1",
                    "cn_trade_zj_commerce_policy_v1",
                ),
                "\u56db\u5ddd": (
                    "cn_policy_sc_portal_policy_v1",
                    "cn_policy_sichuan_drc_tzgg_v1",
                    "cn_policy_sc_industry_jxt_v1",
                    "cn_data_sc_stats_bulletin_v1",
                    "cn_policy_sc_science_kjt_v1",
                    "cn_trade_sc_commerce_policy_v1",
                ),
                "\u4e0a\u6d77": (
                    "cn_policy_shanghai_portal_policy_v1",
                    "cn_policy_sh_drc_fgw_v1",
                    "cn_policy_sh_industry_sheitc_v1",
                    "cn_data_sh_stats_bulletin_v1",
                    "cn_policy_sh_stcsm_tzgg_v1",
                    "cn_trade_sh_commerce_policy_v1",
                ),
            }
            for region, source_ids in provincial_backbone_candidates.items():
                if region not in query:
                    continue
                for index, source_id in enumerate(source_ids):
                    candidates.setdefault(
                        source_id,
                        _RuleMatch(
                            source_id=source_id,
                            reason=f"Matched provincial backbone role for region {region}.",
                            base_rule_score=87.0 - float(index),
                            matched_terms=[region],
                        ),
                    )

            project_signal_terms = self._matched_terms(query, self.PROJECT_SIGNAL_KEYWORDS)
            if project_signal_terms:
                candidates.setdefault(
                    "cn_project_ccgp_procurement_v1",
                    _RuleMatch(
                        source_id="cn_project_ccgp_procurement_v1",
                        reason="Matched procurement/tender/project keywords.",
                        base_rule_score=90.0,
                        matched_terms=project_signal_terms,
                    ),
                )
                candidates.setdefault(
                    "cn_project_ggzy_trade_v1",
                    _RuleMatch(
                        source_id="cn_project_ggzy_trade_v1",
                        reason="Matched public-resource-trade/project keywords.",
                        base_rule_score=89.0,
                        matched_terms=project_signal_terms,
                    ),
                )
                candidates.setdefault(
                    "cn_project_ndrc_approval_v1",
                    _RuleMatch(
                        source_id="cn_project_ndrc_approval_v1",
                        reason="Matched project approval keywords.",
                        base_rule_score=88.0,
                        matched_terms=project_signal_terms,
                    ),
                )

        recommendations: list[RoutingRecommendation] = []
        local_rollout_terms = self._matched_terms(query, self.LOCAL_ROLLOUT_KEYWORDS)
        industry_trend_terms = self._matched_terms(query, self.INDUSTRY_TREND_KEYWORDS)
        intent_flags = {
            "policy": bool(self._matched_terms(query, self.DOMESTIC_POLICY_KEYWORDS)),
            "disclosure": bool(
                self._matched_terms(query, self.DOMESTIC_EXCHANGE_KEYWORDS) or filing_terms
            ),
            "local_rollout": bool(local_rollout_terms),
            "industry_trend": bool(industry_trend_terms),
        }
        for source_id, rule in candidates.items():
            trust_bonus = self.TRUST_BONUS.get(source_id, 0.0)
            query_fit_bonus = self.QUERY_FIT_BONUS.get(query_type, {}).get(source_id, 0.0)
            performance_adjustments = self._performance_adjustments(
                performance_by_source.get(source_id)
            )
            tiaokuai_adjustments = self._tiaokuai_adjustments(
                profiles_by_source.get(source_id),
                intent_flags=intent_flags,
                domestic_mode=domestic_mode,
                regional_focus=regional_focus,
            )
            source_pack_bonus = 0.0
            if requested_pack is not None and source_id in requested_pack.source_ids:
                source_pack_bonus = 5.0

            final_score = (
                rule.base_rule_score
                + trust_bonus
                + query_fit_bonus
                + sum(performance_adjustments.values())
                + sum(tiaokuai_adjustments.values())
                + source_pack_bonus
            )
            final_score = round(max(final_score, 0.0), 4)
            priority = max(1, min(100, int(round(final_score))))
            score_breakdown = {
                "rule_match_score": round(rule.base_rule_score, 4),
                "trust_bonus": round(trust_bonus, 4),
                "query_fit_bonus": round(query_fit_bonus, 4),
                **tiaokuai_adjustments,
                "source_pack_bonus": round(source_pack_bonus, 4),
                **performance_adjustments,
            }
            reason = (
                f"{rule.reason} "
                f"query_type={query_type.value}; matched_terms={','.join(rule.matched_terms)}"
            )
            recommendations.append(
                RoutingRecommendation(
                    source_id=source_id,
                    reason=reason,
                    priority=priority,
                    query_type=query_type,
                    final_score=final_score,
                    score_breakdown=score_breakdown,
                    selected_via=rule.selected_via,
                    matched_terms=sorted(set([*rule.matched_terms, *query_terms])),
                )
            )

        ordered = sorted(
            recommendations,
            key=lambda item: (-item.final_score, -item.priority, item.source_id),
        )
        if requested_pack is not None:
            pack_sources = set(requested_pack.source_ids)
            ordered = [
                item
                for item in ordered
                if item.source_id in pack_sources or item.source_id == "user_input"
            ]
        return ordered[: query_context.max_sources]

    def _tiaokuai_adjustments(
        self,
        profile: SourceProfile | None,
        *,
        intent_flags: dict[str, bool],
        domestic_mode: str | None = None,
        regional_focus: list[str] | None = None,
    ) -> dict[str, float]:
        base = {
            "tiaokuai_axis_bonus": 0.0,
            "tiaokuai_line_family_bonus": 0.0,
            "tiaokuai_regional_bonus": 0.0,
            "tiaokuai_info_type_bonus": 0.0,
            "tiaokuai_source_role_bonus": 0.0,
            "tiaokuai_mode_bonus": 0.0,
        }
        if profile is None:
            return base

        if intent_flags["policy"]:
            if profile.governance_axis == GovernanceAxis.LINE:
                base["tiaokuai_axis_bonus"] += 4.0
            if profile.line_family == LineFamily.POLICY:
                base["tiaokuai_line_family_bonus"] += 6.0
            if profile.info_type == InfoType.POLICY_NOTICE:
                base["tiaokuai_info_type_bonus"] += 4.0
            if profile.source_role == SourceRole.PRIMARY:
                base["tiaokuai_source_role_bonus"] += 2.0

        if intent_flags["disclosure"]:
            if profile.governance_axis == GovernanceAxis.LINE:
                base["tiaokuai_axis_bonus"] += 3.0
            if profile.line_family == LineFamily.EXCHANGE:
                base["tiaokuai_line_family_bonus"] += 6.0
            if profile.info_type == InfoType.REGULATORY_ANNOUNCEMENT:
                base["tiaokuai_info_type_bonus"] += 4.0
            if profile.source_role == SourceRole.PRIMARY:
                base["tiaokuai_source_role_bonus"] += 2.0

        if intent_flags["local_rollout"]:
            if profile.governance_axis == GovernanceAxis.BLOCK:
                base["tiaokuai_axis_bonus"] += 6.0
            if profile.regional_level in {
                RegionalLevel.PROVINCIAL,
                RegionalLevel.MUNICIPAL,
                RegionalLevel.CROSS_REGION,
            }:
                base["tiaokuai_regional_bonus"] += 5.0
            if profile.source_role in {SourceRole.SECONDARY, SourceRole.SUPPLEMENTAL}:
                base["tiaokuai_source_role_bonus"] += 2.0
            if profile.info_type == InfoType.PROJECT_TRANSACTION:
                base["tiaokuai_info_type_bonus"] += 4.0

        if intent_flags["industry_trend"]:
            if profile.line_family == LineFamily.INDUSTRY:
                base["tiaokuai_line_family_bonus"] += 5.0
            if profile.info_type in {InfoType.INDUSTRY_REPORT, InfoType.INDUSTRY_NOTICE}:
                base["tiaokuai_info_type_bonus"] += 3.0
            if profile.source_role == SourceRole.SUPPLEMENTAL:
                base["tiaokuai_source_role_bonus"] += 2.0

        if domestic_mode == "tiao_priority" and profile.governance_axis is not None:
            base["tiaokuai_mode_bonus"] += 1.5

        if regional_focus:
            if profile.regional_level in {
                RegionalLevel.PROVINCIAL,
                RegionalLevel.MUNICIPAL,
                RegionalLevel.CROSS_REGION,
            }:
                base["tiaokuai_regional_bonus"] += 2.0

        return {key: round(value, 4) for key, value in base.items()}

    def _performance_adjustments(self, item: SourcePerformanceItem | None) -> dict[str, float]:
        if item is None or item.attempt_count <= 0:
            return {
                "historical_success_bonus": 0.0,
                "evidence_density_bonus": 0.0,
                "citation_completeness_bonus": 0.0,
                "failure_penalty": 0.0,
                "no_result_penalty": 0.0,
                "latency_penalty": 0.0,
            }

        attempts = float(max(item.attempt_count, 1))
        success_rate = (item.success_count + 0.5 * item.partial_count) / attempts
        failure_rate = item.failure_count / attempts
        no_result_rate = item.no_result_count / attempts
        latency_penalty = min(max(item.avg_latency_ms, 0.0) / 8000.0, 1.0) * -2.0

        return {
            "historical_success_bonus": round(success_rate * 12.0, 4),
            "evidence_density_bonus": round(min(item.avg_evidence_density, 2.0) * 6.0, 4),
            "citation_completeness_bonus": round(
                min(max(item.avg_citation_completeness, 0.0), 1.0) * 6.0,
                4,
            ),
            "failure_penalty": round(failure_rate * -10.0, 4),
            "no_result_penalty": round(no_result_rate * -6.0, 4),
            "latency_penalty": round(latency_penalty, 4),
        }

    def _matched_terms(self, query: str, keywords: tuple[str, ...]) -> list[str]:
        return [keyword for keyword in keywords if keyword in query]
