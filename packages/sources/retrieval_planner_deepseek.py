from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from packages.core.config import Settings, get_settings
from packages.providers import DeepSeekProviderClient
from packages.providers.base import JsonProviderClient, ProviderConfigError, ProviderError
from packages.sources.retrieval_plan import (
    CoverageLane,
    CoverageLanePlan,
    DomainStrategy,
    ExecutionBucket,
    PlannerMetadata,
    RetrievalPlan,
    build_deterministic_retrieval_plan,
)

SCHEMA_VERSION = "retrieval_plan_v1"

DIRECT_KEEP_LANES: set[CoverageLane] = {
    CoverageLane.PROJECT_TRANSACTION,
    CoverageLane.ENTERPRISE_DISCLOSURE,
    CoverageLane.STATISTICS_OR_INDUSTRY_DATA,
}

DIRECT_KEEP_BUCKET = ExecutionBucket.DIRECT_STRUCTURED_SOURCES
DIRECT_KEEP_STRATEGY = DomainStrategy.DIRECT_STRUCTURED_ONLY


@dataclass(slots=True)
class DeepSeekRetrievalPlannerSettings:
    api_key: str | None
    base_url: str
    model: str
    timeout_seconds: int
    max_retries: int
    max_tokens: int | None = None
    enable_thinking: bool = False


class DeepSeekRetrievalPlanner:
    def __init__(
        self,
        *,
        client: JsonProviderClient | None = None,
        settings: DeepSeekRetrievalPlannerSettings | None = None,
    ) -> None:
        self.settings = settings or deepseek_retrieval_planner_settings_from_app_settings()
        self._explicit_client = client

    def build(self, query: str) -> RetrievalPlan:
        deterministic = build_deterministic_retrieval_plan(query)

        if self._explicit_client is not None:
            return self._build_with_client(
                query=deterministic.original_query,
                deterministic=deterministic,
                client=self._explicit_client,
            )

        if not self.settings.api_key:
            return _deterministic_fallback(
                deterministic,
                provider="deterministic",
                model="offline_rules_v1",
                notes=["deepseek_client_missing", "fallback_reason=missing_api_key"],
            )

        try:
            client = DeepSeekProviderClient(
                api_key=self.settings.api_key,
                base_url=self.settings.base_url,
                model=self.settings.model,
                timeout_seconds=self.settings.timeout_seconds,
                max_retries=self.settings.max_retries,
                max_tokens=self.settings.max_tokens,
                store_reasoning_content=False,
            )
        except ProviderConfigError:
            return _deterministic_fallback(
                deterministic,
                provider="deterministic",
                model="offline_rules_v1",
                notes=["deepseek_client_init_failed", "fallback_reason=provider_config_error"],
            )

        return self._build_with_client(
            query=deterministic.original_query,
            deterministic=deterministic,
            client=client,
        )

    def _build_with_client(
        self,
        *,
        query: str,
        deterministic: RetrievalPlan,
        client: JsonProviderClient,
    ) -> RetrievalPlan:
        system_prompt, user_prompt = _build_planner_prompts(query)
        try:
            response = client.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self.settings.model,
                enable_thinking=self.settings.enable_thinking,
            )
        except ProviderError as exc:
            return _deterministic_fallback(
                deterministic,
                provider="deterministic",
                model="offline_rules_v1",
                notes=[
                    "deepseek_provider_error",
                    f"fallback_reason={type(exc).__name__}",
                ],
            )
        except Exception as exc:  # noqa: BLE001
            return _deterministic_fallback(
                deterministic,
                provider="deterministic",
                model="offline_rules_v1",
                notes=[
                    "deepseek_provider_error",
                    f"fallback_reason={type(exc).__name__}",
                ],
            )

        provider = _safe_provider_name(response.provider)
        model = _safe_model_name(response.model)

        if not isinstance(response.json_data, dict):
            return _deterministic_fallback(
                deterministic,
                provider="deterministic",
                model="offline_rules_v1",
                notes=[
                    "invalid_provider_payload",
                    "fallback_reason=non_object_json",
                    f"planner_provider={provider}",
                    f"planner_model={model}",
                ],
            )

        payload = deepcopy(response.json_data)
        payload["original_query"] = query

        if _looks_like_direct_answer(payload):
            return _deterministic_fallback(
                deterministic,
                provider="deterministic",
                model="offline_rules_v1",
                notes=[
                    "invalid_provider_payload",
                    "fallback_reason=direct_answer_or_refusal",
                    f"planner_provider={provider}",
                    f"planner_model={model}",
                ],
            )

        repair_notes: list[str] = []
        repair_applied = False
        try:
            validated = RetrievalPlan.model_validate(payload)
        except ValidationError as exc:
            if not _metadata_only_validation_error(exc):
                return _deterministic_fallback(
                    deterministic,
                    provider="deterministic",
                    model="offline_rules_v1",
                    notes=[
                        "schema_validation_failed",
                        "fallback_reason=unsafe_validation_error",
                        f"planner_provider={provider}",
                        f"planner_model={model}",
                    ],
                )

            repaired_payload = deepcopy(payload)
            repaired_payload["planner_metadata"] = _planner_metadata_payload(
                deterministic=deterministic,
                provider=provider,
                model=model,
                deterministic_fallback=False,
                repair_applied=True,
                notes=["metadata_repaired"],
            )
            try:
                validated = RetrievalPlan.model_validate(repaired_payload)
                repair_applied = True
                repair_notes.append("metadata_repaired")
            except ValidationError:
                return _deterministic_fallback(
                    deterministic,
                    provider="deterministic",
                    model="offline_rules_v1",
                    notes=[
                        "schema_validation_failed",
                        "fallback_reason=repair_failed",
                        f"planner_provider={provider}",
                        f"planner_model={model}",
                    ],
                )

        return _sanitize_provider_plan(
            plan=validated,
            deterministic=deterministic,
            provider=provider,
            model=model,
            repair_applied=repair_applied,
            extra_notes=repair_notes,
        )


def deepseek_retrieval_planner_settings_from_app_settings(
    settings: Settings | None = None,
) -> DeepSeekRetrievalPlannerSettings:
    app_settings = settings or get_settings()
    return DeepSeekRetrievalPlannerSettings(
        api_key=app_settings.deepseek_api_key,
        base_url=app_settings.deepseek_base_url,
        model=app_settings.deepseek_research_model,
        timeout_seconds=app_settings.deepseek_timeout_seconds,
        max_retries=app_settings.deepseek_max_retries,
        max_tokens=app_settings.deepseek_max_tokens,
        enable_thinking=False,
    )


def build_retrieval_plan_with_deepseek(
    query: str,
    *,
    client: JsonProviderClient | None = None,
    settings: DeepSeekRetrievalPlannerSettings | None = None,
) -> RetrievalPlan:
    planner = DeepSeekRetrievalPlanner(client=client, settings=settings)
    return planner.build(query)


def _sanitize_provider_plan(
    *,
    plan: RetrievalPlan,
    deterministic: RetrievalPlan,
    provider: str,
    model: str,
    repair_applied: bool,
    extra_notes: list[str],
) -> RetrievalPlan:
    provider_lanes = {lane.lane_id: lane for lane in plan.coverage_lanes}
    lane_updates: list[CoverageLanePlan] = []
    authoritative_overrides = 0
    max_phrases = deterministic.round_policy.max_search_phrases_per_lane

    for deterministic_lane in deterministic.coverage_lanes:
        provider_lane = provider_lanes.get(deterministic_lane.lane_id)
        if provider_lane is None:
            lane_updates.append(deterministic_lane)
            continue

        update: dict[str, Any] = {}
        provider_phrases = _safe_phrase_list(
            provider_lane.search_phrases,
            max_items=max_phrases,
        )
        if provider_phrases:
            update["search_phrases"] = provider_phrases

        provider_exact = _safe_phrase_list(
            provider_lane.exact_phrases,
            max_items=max_phrases,
        )
        if provider_exact:
            update["exact_phrases"] = provider_exact

        update["negative_terms"] = _merge_terms(
            deterministic_lane.negative_terms,
            provider_lane.negative_terms,
            max_items=12,
        )

        if _has_authoritative_field_drift(
            deterministic_lane=deterministic_lane,
            provider_lane=provider_lane,
        ):
            authoritative_overrides += 1

        lane_updates.append(deterministic_lane.model_copy(update=update))

    ignored_provider_lanes = [
        lane.lane_id.value
        for lane in plan.coverage_lanes
        if lane.lane_id not in {item.lane_id for item in deterministic.coverage_lanes}
    ]

    notes = list(extra_notes)
    if authoritative_overrides:
        notes.append("authoritative_fields_enforced")
    if ignored_provider_lanes:
        notes.append("provider_extra_lanes_ignored")

    metadata = PlannerMetadata(
        planner_provider=provider,
        planner_model=model,
        schema_version=SCHEMA_VERSION,
        deterministic_fallback=False,
        repair_applied=repair_applied,
        supplemental_theme=deterministic.planner_metadata.supplemental_theme,
        supplemental_domains=deterministic.planner_metadata.supplemental_domains,
        notes=notes,
    )
    return deterministic.model_copy(
        update={
            "coverage_lanes": lane_updates,
            "round_policy": deterministic.round_policy,
            "stop_conditions": deterministic.stop_conditions,
            "coverage_gaps": deterministic.coverage_gaps,
            "planner_metadata": metadata,
        }
    )


def _has_authoritative_field_drift(
    *,
    deterministic_lane: CoverageLanePlan,
    provider_lane: CoverageLanePlan,
) -> bool:
    return any(
        (
            provider_lane.required != deterministic_lane.required,
            provider_lane.priority != deterministic_lane.priority,
            provider_lane.source_intents != deterministic_lane.source_intents,
            provider_lane.execution_bucket != deterministic_lane.execution_bucket,
            provider_lane.domain_strategy != deterministic_lane.domain_strategy,
            provider_lane.allowed_domains != deterministic_lane.allowed_domains,
            provider_lane.success_criteria != deterministic_lane.success_criteria,
            provider_lane.fallback_ladder != deterministic_lane.fallback_ladder,
            (
                provider_lane.lane_id in DIRECT_KEEP_LANES
                and (
                    provider_lane.execution_bucket != DIRECT_KEEP_BUCKET
                    or provider_lane.domain_strategy != DIRECT_KEEP_STRATEGY
                )
            )
        )
    )


def _safe_phrase_list(values: list[str], *, max_items: int) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or _looks_secret_like(text):
            continue
        if text not in result:
            result.append(text)
        if len(result) >= max_items:
            break
    return result


def _merge_terms(
    default_terms: list[str],
    provider_terms: list[str],
    *,
    max_items: int,
) -> list[str]:
    result: list[str] = []
    for value in [*default_terms, *provider_terms]:
        text = str(value).strip()
        if not text or _looks_secret_like(text) or text in result:
            continue
        result.append(text)
        if len(result) >= max_items:
            break
    return result


def _looks_secret_like(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "api_key",
            "apikey",
            "secret",
            "password",
            "token",
            "sk-",
            "tvly-",
        )
    )


def _deterministic_fallback(
    deterministic: RetrievalPlan,
    *,
    provider: str,
    model: str,
    notes: list[str],
) -> RetrievalPlan:
    metadata = PlannerMetadata(
        planner_provider=provider,
        planner_model=model,
        schema_version=SCHEMA_VERSION,
        deterministic_fallback=True,
        repair_applied=False,
        supplemental_theme=deterministic.planner_metadata.supplemental_theme,
        supplemental_domains=deterministic.planner_metadata.supplemental_domains,
        notes=notes,
    )
    return deterministic.model_copy(update={"planner_metadata": metadata})


def _metadata_only_validation_error(exc: ValidationError) -> bool:
    errors = exc.errors()
    if not errors:
        return False
    for item in errors:
        loc = item.get("loc") or ()
        if not loc:
            return False
        if loc[0] != "planner_metadata":
            return False
    return True


def _planner_metadata_payload(
    *,
    deterministic: RetrievalPlan,
    provider: str,
    model: str,
    deterministic_fallback: bool,
    repair_applied: bool,
    notes: list[str],
) -> dict[str, Any]:
    return {
        "planner_provider": provider,
        "planner_model": model,
        "schema_version": SCHEMA_VERSION,
        "deterministic_fallback": deterministic_fallback,
        "repair_applied": repair_applied,
        "supplemental_theme": deterministic.planner_metadata.supplemental_theme,
        "supplemental_domains": deterministic.planner_metadata.supplemental_domains,
        "notes": notes,
    }


def _looks_like_direct_answer(payload: dict[str, Any]) -> bool:
    answer_like_keys = {
        "answer",
        "final_answer",
        "response",
        "refusal",
        "analysis",
    }
    payload_keys = {str(key).strip().lower() for key in payload.keys()}
    if not (answer_like_keys & payload_keys):
        return False
    return "coverage_lanes" not in payload_keys


def _safe_provider_name(value: Any) -> str:
    text = str(value or "deepseek").strip().lower()
    if not text:
        return "deepseek"
    if len(text) > 60:
        return text[:60]
    return text


def _safe_model_name(value: Any) -> str:
    text = str(value or "configured_by_env").strip()
    if not text:
        return "configured_by_env"
    if len(text) > 120:
        return text[:120]
    return text


def _build_planner_prompts(query: str) -> tuple[str, str]:
    allowed_lanes = ", ".join(lane.value for lane in CoverageLane)
    from packages.sources.retrieval_plan import SourceIntent

    allowed_source_intents = ", ".join(intent.value for intent in SourceIntent)
    allowed_domain_strategies = ", ".join(strategy.value for strategy in DomainStrategy)
    allowed_execution_buckets = ", ".join(bucket.value for bucket in ExecutionBucket)

    system_prompt = (
        "You are a retrieval planner for a source-layer pipeline. "
        "Do not answer the user query. Return one JSON object only that matches RetrievalPlan. "
        "No markdown, no explanations, no chain-of-thought, no credentials, no secrets."
    )

    user_prompt = (
        "Build a RetrievalPlan JSON for the query below.\n"
        "Strict requirements:\n"
        "1) Output RetrievalPlan JSON object only.\n"
        "2) Do NOT answer the query.\n"
        "3) coverage_lanes[].lane_id must be one of: "
        f"{allowed_lanes}.\n"
        "4) coverage_lanes[].source_intents[] must use only: "
        f"{allowed_source_intents}.\n"
        "5) coverage_lanes[].domain_strategy must use only: "
        f"{allowed_domain_strategies}.\n"
        "6) coverage_lanes[].execution_bucket must use only: "
        f"{allowed_execution_buckets}.\n"
        "7) Do not invent domains, source categories, lane values, "
        "source intents, or domain strategies.\n"
        "8) Direct-keep primary lanes (project_transaction, enterprise_disclosure, "
        "statistics_or_industry_data) must remain direct_structured_sources with "
        "direct_structured_only.\n"
        "9) Never include private reasoning or credential-like fields in output.\n"
        "Query:\n"
        f"{query}"
    )
    return system_prompt, user_prompt


__all__ = [
    "DeepSeekRetrievalPlanner",
    "DeepSeekRetrievalPlannerSettings",
    "build_retrieval_plan_with_deepseek",
    "deepseek_retrieval_planner_settings_from_app_settings",
]
