from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.providers.base import JsonProviderResponse, ProviderCallMetadata
from packages.sources.retrieval_plan import (
    CoverageLane,
    DomainStrategy,
    ExecutionBucket,
    SourceIntent,
    build_deterministic_retrieval_plan,
)
from packages.sources.retrieval_planner_deepseek import (
    DeepSeekRetrievalPlannerSettings,
    build_retrieval_plan_with_deepseek,
)


@dataclass(slots=True)
class _FakeJsonClient:
    payload: dict[str, Any]
    provider: str = "deepseek"
    model: str = "deepseek-chat"

    def generate_json(self, **kwargs: Any) -> JsonProviderResponse:  # noqa: ANN401
        _ = kwargs
        return JsonProviderResponse(
            provider=self.provider,
            model=self.model,
            content_text="{}",
            json_data=self.payload,
            metadata=ProviderCallMetadata(
                provider=self.provider,
                model=self.model,
                request_id="fake-req",
                usage={"prompt_tokens": 1, "completion_tokens": 1},
                finish_reason="stop",
                response_ms=1.0,
                extra={"api_key": "SHOULD_NOT_LEAK", "trace": "internal"},
            ),
            reasoning_content="internal-chain-of-thought",
        )


def _no_key_settings() -> DeepSeekRetrievalPlannerSettings:
    return DeepSeekRetrievalPlannerSettings(
        api_key=None,
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        timeout_seconds=30,
        max_retries=0,
    )


def test_missing_client_falls_back_deterministic() -> None:
    query = "广东人形机器人产业政策和项目落地情况"

    plan = build_retrieval_plan_with_deepseek(query, settings=_no_key_settings())
    deterministic = build_deterministic_retrieval_plan(query)

    assert plan.coverage_lanes == deterministic.coverage_lanes
    assert plan.plan_id == deterministic.plan_id
    assert plan.planner_metadata.deterministic_fallback is True
    assert plan.planner_metadata.planner_provider == "deterministic"
    assert any("deepseek_client_missing" in note for note in plan.planner_metadata.notes)


def test_valid_provider_output_accepted_with_safe_metadata() -> None:
    query = "广东人形机器人产业政策和项目落地情况"
    deterministic = build_deterministic_retrieval_plan(query)

    provider_payload = deterministic.model_dump()
    provider_payload["planner_metadata"]["notes"] = ["model-produced"]
    provider_payload["planner_metadata"]["planner_provider"] = "deepseek"
    provider_payload["planner_metadata"]["planner_model"] = "deepseek-chat"

    plan = build_retrieval_plan_with_deepseek(query, client=_FakeJsonClient(provider_payload))

    assert plan.planner_metadata.planner_provider == "deepseek"
    assert plan.planner_metadata.planner_model == "deepseek-chat"
    assert plan.planner_metadata.deterministic_fallback is False
    assert "internal-chain-of-thought" not in " ".join(plan.planner_metadata.notes)
    joined_notes = " ".join(plan.planner_metadata.notes).lower()
    assert "api_key" not in joined_notes
    assert "should_not_leak" not in joined_notes


def test_invalid_lane_enum_falls_back_to_deterministic() -> None:
    query = "广东人形机器人产业政策和项目落地情况"
    deterministic = build_deterministic_retrieval_plan(query)
    provider_payload = deterministic.model_dump()
    provider_payload["coverage_lanes"][0]["lane_id"] = "invented_lane"

    plan = build_retrieval_plan_with_deepseek(query, client=_FakeJsonClient(provider_payload))

    assert plan.coverage_lanes == deterministic.coverage_lanes
    assert plan.planner_metadata.deterministic_fallback is True
    assert any("schema_validation_failed" in note for note in plan.planner_metadata.notes)


def test_invalid_enum_repaired_once_when_only_metadata_is_invalid() -> None:
    query = "广东人形机器人产业政策和项目落地情况"
    deterministic = build_deterministic_retrieval_plan(query)
    provider_payload = deterministic.model_dump()
    provider_payload["planner_metadata"]["deterministic_fallback"] = "nope"

    plan = build_retrieval_plan_with_deepseek(query, client=_FakeJsonClient(provider_payload))

    assert plan.coverage_lanes == deterministic.coverage_lanes
    assert plan.planner_metadata.planner_provider == "deepseek"
    assert plan.planner_metadata.deterministic_fallback is False
    assert plan.planner_metadata.repair_applied is True
    assert any("metadata_repaired" in note for note in plan.planner_metadata.notes)


def test_extra_invented_top_level_field_is_rejected_and_fallback() -> None:
    query = "广东人形机器人产业政策和项目落地情况"
    deterministic = build_deterministic_retrieval_plan(query)
    provider_payload = deterministic.model_dump()
    provider_payload["invented_top_field"] = "not-allowed"

    plan = build_retrieval_plan_with_deepseek(query, client=_FakeJsonClient(provider_payload))

    assert plan.coverage_lanes == deterministic.coverage_lanes
    assert plan.planner_metadata.deterministic_fallback is True
    assert any("schema_validation_failed" in note for note in plan.planner_metadata.notes)


def test_direct_keep_boundary_preserved_even_if_provider_changes_bucket() -> None:
    query = "中信海直（000099.SZ）在低空经济方向有哪些公告和项目"
    deterministic = build_deterministic_retrieval_plan(query)
    provider_payload = deterministic.model_dump()

    for lane in provider_payload["coverage_lanes"]:
        if lane["lane_id"] in {
            CoverageLane.PROJECT_TRANSACTION.value,
            CoverageLane.ENTERPRISE_DISCLOSURE.value,
        }:
            lane["execution_bucket"] = ExecutionBucket.SEARCH_ASSISTED_SOURCES.value
            lane["domain_strategy"] = DomainStrategy.REGION_OFFICIAL_DOMAINS_ONLY.value

    plan = build_retrieval_plan_with_deepseek(query, client=_FakeJsonClient(provider_payload))

    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}
    assert lane_by_id[CoverageLane.PROJECT_TRANSACTION].execution_bucket == (
        ExecutionBucket.DIRECT_STRUCTURED_SOURCES
    )
    assert lane_by_id[CoverageLane.PROJECT_TRANSACTION].domain_strategy == (
        DomainStrategy.DIRECT_STRUCTURED_ONLY
    )
    assert lane_by_id[CoverageLane.ENTERPRISE_DISCLOSURE].execution_bucket == (
        ExecutionBucket.DIRECT_STRUCTURED_SOURCES
    )
    assert lane_by_id[CoverageLane.ENTERPRISE_DISCLOSURE].domain_strategy == (
        DomainStrategy.DIRECT_STRUCTURED_ONLY
    )


def test_authoritative_fields_are_enforced_over_provider_payload() -> None:
    query = "江苏光伏产业链出海面临哪些政策和贸易风险"
    deterministic = build_deterministic_retrieval_plan(query)
    provider_payload = deterministic.model_dump()
    provider_payload["plan_id"] = "provider-plan-id"
    provider_payload["round_policy"]["max_rounds"] = 5
    provider_payload["stop_conditions"]["stop_when_credit_budget_reached"] = False

    for lane in provider_payload["coverage_lanes"]:
        if lane["lane_id"] == CoverageLane.PROVINCIAL_POLICY_ROLLOUT.value:
            lane["source_intents"] = [SourceIntent.THEME_ASSOCIATION.value]
            lane["domain_strategy"] = DomainStrategy.THEME_SUPPLEMENTAL_DOMAINS_ONLY.value
            lane["fallback_ladder"] = ["provider_invented_fallback"]
            lane["allowed_domains"] = ["aopa.org.cn"]
            lane["search_phrases"] = [
                "江苏 光伏 出海 商务 政策",
                "api_key=SHOULD_NOT_LEAK",
            ]

    plan = build_retrieval_plan_with_deepseek(query, client=_FakeJsonClient(provider_payload))
    lane_by_id = {lane.lane_id: lane for lane in plan.coverage_lanes}
    deterministic_by_id = {lane.lane_id: lane for lane in deterministic.coverage_lanes}
    rollout = lane_by_id[CoverageLane.PROVINCIAL_POLICY_ROLLOUT]
    deterministic_rollout = deterministic_by_id[CoverageLane.PROVINCIAL_POLICY_ROLLOUT]

    assert plan.plan_id == deterministic.plan_id
    assert plan.round_policy == deterministic.round_policy
    assert plan.stop_conditions == deterministic.stop_conditions
    assert rollout.source_intents == deterministic_rollout.source_intents
    assert rollout.domain_strategy == deterministic_rollout.domain_strategy
    assert rollout.fallback_ladder == deterministic_rollout.fallback_ladder
    assert rollout.allowed_domains == deterministic_rollout.allowed_domains
    assert rollout.search_phrases == ["江苏 光伏 出海 商务 政策"]
    assert any("authoritative_fields_enforced" in note for note in plan.planner_metadata.notes)


def test_reasoning_and_secrets_are_not_persisted_in_metadata_notes() -> None:
    query = "广东人形机器人产业政策和项目落地情况"
    deterministic = build_deterministic_retrieval_plan(query)
    provider_payload = deterministic.model_dump()

    plan = build_retrieval_plan_with_deepseek(query, client=_FakeJsonClient(provider_payload))

    notes_text = " ".join(plan.planner_metadata.notes).lower()
    assert "reasoning" not in notes_text
    assert "chain-of-thought" not in notes_text
    assert "api_key" not in notes_text
    assert "should_not_leak" not in notes_text
