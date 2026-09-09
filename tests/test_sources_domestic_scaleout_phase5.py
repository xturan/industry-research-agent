from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from packages.sources.query_decomposition import decompose_query
from packages.sources.registry import build_default_source_registry
from packages.sources.schemas import QueryContext, ToolRequest
from packages.sources.tools import build_source_tool_registry


def _load_phase5_eval_module() -> ModuleType:
    root = Path(__file__).resolve().parents[1]
    module_path = root / "data" / "tmp" / "_phase5_search_assisted_domestic_eval.py"
    spec = importlib.util.spec_from_file_location("phase5_eval_helper", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_phase5_industry_profiles_registered_with_adapters() -> None:
    registry = build_default_source_registry()
    profiles = {
        profile.source_id: profile for profile in registry.list_profiles(enabled_only=False)
    }
    expected = {
        "cn_industry_caam_news_v1",
        "cn_industry_ces_report_v1",
    }
    assert expected.issubset(set(profiles))
    for source_id in expected:
        assert profiles[source_id].enabled is True
        assert registry.get_adapter(source_id, enabled_only=True) is not None


def test_industry_signal_pack_v2_routes_expected_sources() -> None:
    tool_registry = build_source_tool_registry(source_registry=build_default_source_registry())
    response = tool_registry.dispatch(
        ToolRequest(
            tool_name="route_research_sources",
            query_context=QueryContext(
                query="行业 趋势 协会 白皮书 景气 信号",
                source_pack="industry_signal_pack_cn_v2",
                max_sources=6,
            ),
        )
    )
    assert response.route_recommendations
    source_ids = {item.source_id for item in response.route_recommendations}
    assert source_ids <= {
        "cn_industry_caam_news_v1",
        "cn_industry_ces_report_v1",
        "cn_policy_ndrc_tzgg_v1",
        "cn_exchange_sse_notice_v1",
    }
    assert {"cn_industry_caam_news_v1", "cn_industry_ces_report_v1"} & source_ids


def test_industry_signal_strategy_v2_resolves_to_pack() -> None:
    tool_registry = build_source_tool_registry(source_registry=build_default_source_registry())
    response = tool_registry.dispatch(
        ToolRequest(
            tool_name="route_research_sources",
            query_context=QueryContext(
                query="行业 报告 协会 信号",
                source_strategy="cn_industry_signal_v2",
                max_sources=6,
            ),
        )
    )
    assert response.route_recommendations
    assert all(item.selected_via == "source_strategy" for item in response.route_recommendations)


def test_phase5_query_set_is_frozen_q01_q10() -> None:
    module = _load_phase5_eval_module()
    payload = module.build_query_set_payload()

    query_ids = [item["query_id"] for item in payload["queries"]]
    assert query_ids == [f"Q{index:02d}" for index in range(1, 11)]
    assert payload["phase"] == "phase5"
    assert payload["settings"] == module.FROZEN_SETTINGS
    assert payload["primary_cohort_query_ids"] == list(module.PRIMARY_QUERY_IDS)

    query_map = {item["query_id"]: item for item in payload["queries"]}
    expected_q01 = (
        "\u5b89\u5fbd\u7684\u4f4e\u7a7a\u7ecf\u6d4e"
        "\u672a\u6765\u524d\u666f\u5982\u4f55\uff1f"
    )
    assert query_map["Q01"]["query"] == expected_q01
    assert query_map["Q02"]["case_class"] == "volatility_sentinel"
    assert query_map["Q02"]["counts_toward_primary_cohort"] is True
    assert query_map["Q07"]["case_class"] == "park_city_holdout"
    assert query_map["Q08"]["case_class"] == "direct_keep_control"


def test_phase5_offline_eval_schema_and_thresholds_pass() -> None:
    module = _load_phase5_eval_module()
    result = module.run_phase5_eval(mode="offline")

    assert result["mode"] == "offline"
    assert result["acceptance_pass"] is True
    assert result["aggregates"]["primary_successes"] >= 4
    assert result["aggregates"]["official_successes"] >= 2
    assert result["aggregates"]["supplemental_successes"] >= 1

    required = set(module.CASE_REQUIRED_FIELDS)
    cases = module.build_offline_cases()
    for case in cases:
        assert required <= set(case.keys())
        assert case["case_class"] in module.CASE_CLASSES
        assert case["pass_classification"] in module.PASS_CLASSIFICATIONS

    case_map = {case["query_id"]: case for case in result["cases"]}
    assert case_map["Q07"]["pass_classification"] == "park_city_holdout_pass"
    assert case_map["Q07"]["estimated_tavily_credits"] == 0
    for query_id in ("Q08", "Q09", "Q10"):
        assert case_map[query_id]["pass_classification"] == "direct_keep_control_pass"
        assert case_map[query_id]["estimated_tavily_credits"] == 0


def test_phase5_thresholds_fail_when_direct_keep_routes_to_search_assisted() -> None:
    module = _load_phase5_eval_module()
    cases = module.build_offline_cases()
    case_map = {case["query_id"]: case for case in cases}

    case_map["Q08"]["executed_search_assisted_tasks"] = ["enterprise_disclosure_1"]
    case_map["Q08"]["guardrail_flags"]["direct_keep_routed_to_tavily_or_crawl4ai"] = True
    case_map["Q08"]["estimated_tavily_credits"] = 1
    case_map["Q08"]["pass_classification"] = "fail"

    evaluation = module.evaluate_phase5_thresholds(cases)

    assert evaluation["pass"] is False
    assert any("immediate_fail_conditions_triggered" in item for item in evaluation["failures"])
    assert "direct_keep_credits_not_zero:Q08" in evaluation["failures"]


def test_phase5_thresholds_fail_when_holdout_breaks_contract() -> None:
    module = _load_phase5_eval_module()
    cases = module.build_offline_cases()
    case_map = {case["query_id"]: case for case in cases}

    case_map["Q07"]["estimated_tavily_credits"] = 1
    case_map["Q07"]["pass_classification"] = "fail"

    evaluation = module.evaluate_phase5_thresholds(cases)

    assert evaluation["pass"] is False
    assert "holdout_pass_classification_invalid" in evaluation["failures"]
    assert "holdout_credits_must_be_zero" in evaluation["failures"]


def test_phase5_live_selection_caps_fanout_and_preserves_controls() -> None:
    module = _load_phase5_eval_module()
    frozen_by_id = {item.query_id: item for item in module.FROZEN_QUERIES}

    q01_tasks = decompose_query(frozen_by_id["Q01"].query).decomposition_tasks
    selected_q01 = module._select_live_execution_tasks(frozen_by_id["Q01"], q01_tasks)
    search_tasks_q01 = [
        task for task in selected_q01 if task.execution_bucket == "search_assisted_sources"
    ]
    assert len(search_tasks_q01) <= module.MAX_LIVE_SEARCH_ASSISTED_TASKS_PER_CASE
    assert all(
        len(task.search_phrases) <= module.MAX_LIVE_SEARCH_PHRASES_PER_TASK
        for task in search_tasks_q01
    )

    q07_tasks = decompose_query(frozen_by_id["Q07"].query).decomposition_tasks
    selected_q07 = module._select_live_execution_tasks(frozen_by_id["Q07"], q07_tasks)
    assert [task.source_cluster for task in selected_q07] == ["park_city_rollout_backbone"]

    for query_id in ("Q08", "Q09", "Q10"):
        tasks = decompose_query(frozen_by_id[query_id].query).decomposition_tasks
        selected = module._select_live_execution_tasks(frozen_by_id[query_id], tasks)
        assert selected
        assert {task.execution_bucket for task in selected} == {"direct_structured_sources"}


def test_phase5_artifact_writer_uses_frozen_schema(tmp_path: Path) -> None:
    module = _load_phase5_eval_module()
    cases = module.build_offline_cases()
    query_set = module.build_query_set_payload()
    result = module.run_phase5_eval(mode="offline")

    module.write_artifacts(
        query_set_payload=query_set,
        result_payload=result,
        cases=cases,
        output_dir=tmp_path,
    )

    assert (tmp_path / module.QUERY_SET_FILENAME).exists()
    assert (tmp_path / module.RESULTS_FILENAME).exists()
    assert (tmp_path / module.SUMMARY_FILENAME).exists()
    assert (tmp_path / module.CASE_DIR_NAME / "Q01.json").exists()
