from __future__ import annotations

from typing import NamedTuple

from packages.sources.enums import QueryType
from packages.sources.schemas import QueryContext, RoutingRecommendation, SourcePerformanceItem


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

    TRUST_BONUS = {
        "sec_edgar": 8.0,
        "world_bank": 7.0,
        "eia": 7.0,
        "who_gho": 7.0,
        "user_input": 2.0,
        "cn_policy_ndrc_tzgg_v1": 8.0,
        "cn_exchange_szse_notice_v1": 7.0,
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
    ) -> list[RoutingRecommendation]:
        performance_by_source = performance_by_source or {}
        query = query_context.query.lower()
        query_type, query_terms = self.classify_query_type(query_context)
        include_domestic_profiles = self.include_domestic_profiles or bool(
            query_context.metadata.get("include_domestic_profiles")
        )

        candidates: dict[str, _RuleMatch] = {}
        if query_context.user_provided_sources:
            candidates["user_input"] = _RuleMatch(
                source_id="user_input",
                reason="user_provided_sources present; prioritize user context.",
                base_rule_score=95.0,
                matched_terms=["user_provided_sources"],
                selected_via="user_provided_sources",
            )

        macro_terms = self._matched_terms(query, self.MACRO_KEYWORDS)
        if macro_terms:
            candidates["world_bank"] = _RuleMatch(
                source_id="world_bank",
                reason="Matched macro/GDP/CPI/population keywords.",
                base_rule_score=90.0,
                matched_terms=macro_terms,
            )

        energy_terms = self._matched_terms(query, self.ENERGY_KEYWORDS)
        if energy_terms:
            candidates["eia"] = _RuleMatch(
                source_id="eia",
                reason="Matched energy/oil/gas/electricity/inventory keywords.",
                base_rule_score=92.0,
                matched_terms=energy_terms,
            )

        filing_terms = self._matched_terms(query, self.FILING_KEYWORDS)
        if filing_terms or query_context.tickers:
            terms = filing_terms if filing_terms else ["ticker_context"]
            candidates["sec_edgar"] = _RuleMatch(
                source_id="sec_edgar",
                reason="Matched filing/ticker/10-K/10-Q keywords.",
                base_rule_score=95.0,
                matched_terms=terms,
            )

        health_terms = self._matched_terms(query, self.HEALTH_KEYWORDS)
        if health_terms:
            candidates["who_gho"] = _RuleMatch(
                source_id="who_gho",
                reason="Matched health/mortality/disease/life expectancy keywords.",
                base_rule_score=88.0,
                matched_terms=health_terms,
            )

        if include_domestic_profiles:
            policy_terms = self._matched_terms(query, self.DOMESTIC_POLICY_KEYWORDS)
            if policy_terms:
                candidates["cn_policy_ndrc_tzgg_v1"] = _RuleMatch(
                    source_id="cn_policy_ndrc_tzgg_v1",
                    reason="Matched domestic policy/notice/guidance keywords.",
                    base_rule_score=91.0,
                    matched_terms=policy_terms,
                )

            exchange_terms = self._matched_terms(query, self.DOMESTIC_EXCHANGE_KEYWORDS)
            if exchange_terms:
                candidates["cn_exchange_szse_notice_v1"] = _RuleMatch(
                    source_id="cn_exchange_szse_notice_v1",
                    reason="Matched domestic exchange/announcement/disclosure keywords.",
                    base_rule_score=90.0,
                    matched_terms=exchange_terms,
                )

            industry_terms = self._matched_terms(query, self.DOMESTIC_INDUSTRY_KEYWORDS)
            if industry_terms:
                candidates["cn_industry_association_generic"] = _RuleMatch(
                    source_id="cn_industry_association_generic",
                    reason="Matched domestic association/alliance/industry-report keywords.",
                    base_rule_score=89.0,
                    matched_terms=industry_terms,
                )

        recommendations: list[RoutingRecommendation] = []
        for source_id, rule in candidates.items():
            trust_bonus = self.TRUST_BONUS.get(source_id, 0.0)
            query_fit_bonus = self.QUERY_FIT_BONUS.get(query_type, {}).get(source_id, 0.0)
            performance_adjustments = self._performance_adjustments(
                performance_by_source.get(source_id)
            )

            final_score = (
                rule.base_rule_score
                + trust_bonus
                + query_fit_bonus
                + sum(performance_adjustments.values())
            )
            final_score = round(max(final_score, 0.0), 4)
            priority = max(1, min(100, int(round(final_score))))
            score_breakdown = {
                "rule_match_score": round(rule.base_rule_score, 4),
                "trust_bonus": round(trust_bonus, 4),
                "query_fit_bonus": round(query_fit_bonus, 4),
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
        return ordered[: query_context.max_sources]

    def _performance_adjustments(
        self, item: SourcePerformanceItem | None
    ) -> dict[str, float]:
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
