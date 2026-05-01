from __future__ import annotations

from packages.agents.deep_research import DeepResearchAgent, deep_research
from packages.agents.deep_research_schemas import (
    DeepResearchReport,
    EvidenceItem,
    QueryUnderstanding,
    ResearchDimension,
    SearchRoundPlan,
    SourceAssessment,
)


class TestSchemas:
    def test_research_dimension_valid(self) -> None:
        dim = ResearchDimension(
            dimension_id="d1",
            label="政策方向",
            description="国家和省级政策文件",
            caliber_terms=["具身智能机器人", "人工智能与机器人"],
            source_priority="government",
        )
        assert dim.dimension_id == "d1"
        assert len(dim.caliber_terms) == 2

    def test_search_round_plan_valid(self) -> None:
        plan = SearchRoundPlan(
            round_number=1,
            objective="搜索国家政策",
            search_phrases=["人形机器人 政策", "具身智能 指导意见"],
            include_domains=["gov.cn"],
            target_dimensions=["d1"],
            expected_source_tier="A",
        )
        assert plan.round_number == 1
        assert len(plan.search_phrases) == 2

    def test_source_assessment_valid(self) -> None:
        sa = SourceAssessment(
            url="https://www.miit.gov.cn/policy.html",
            title="人形机器人创新发展指导意见",
            tier="A",
            authority_score=0.95,
            proximity_score=0.9,
            timeliness_score=0.85,
            verifiability_score=0.9,
            relevance_score=0.8,
        )
        assert sa.tier == "A"
        assert sa.overall_usable is True

    def test_evidence_item_stage_enum(self) -> None:
        ei = EvidenceItem(
            evidence_id="ev1",
            claim="广东已发布AI与机器人12条政策",
            source_urls=["https://www.gd.gov.cn/policy.html"],
            stage="implementation_rule",
            confidence="high",
        )
        assert ei.stage == "implementation_rule"
        assert ei.verification_status == "unverified"

    def test_deep_research_report_empty(self) -> None:
        report = DeepResearchReport(
            query="test query",
            executive_summary="test summary",
            overall_confidence="medium",
        )
        assert report.query == "test query"
        assert len(report.evidence_chain) == 0


class TestAgent:
    def test_agent_creates_without_client(self) -> None:
        agent = DeepResearchAgent(deepseek_client=None)
        assert agent.max_rounds == 6
        assert agent._client is None

    def test_query_understanding_fallback(self) -> None:
        agent = DeepResearchAgent(deepseek_client=None)
        result = agent._phase1_query_understanding("广东人形机器人产业政策")
        assert isinstance(result, QueryUnderstanding)
        assert len(result.research_dimensions) >= 2
        assert result.normalized_query

    def test_build_search_plan(self) -> None:
        agent = DeepResearchAgent(deepseek_client=None)
        understanding = QueryUnderstanding(
            normalized_query="test",
            research_dimensions=[
                ResearchDimension(
                    dimension_id="d1",
                    label="政策",
                    description="政策文件",
                    caliber_terms=["政策", "指导意见"],
                    source_priority="government",
                ),
                ResearchDimension(
                    dimension_id="d2",
                    label="项目",
                    description="项目落地",
                    caliber_terms=["招标", "项目"],
                    source_priority="enterprise",
                ),
            ],
        )
        plan = agent._build_search_plan(understanding)
        assert len(plan.rounds) >= 3
        assert plan.rounds[0].expected_source_tier == "A"

    def test_source_tiering_deterministic(self) -> None:
        agent = DeepResearchAgent(deepseek_client=None)
        agent._collected_sources = [
            {"url": "https://www.gov.cn/policy.html", "domain": "www.gov.cn", "title": "Test"},
            {
                "url": "https://ggzy.hefei.gov.cn/tender",
                "domain": "ggzy.hefei.gov.cn",
                "title": "招标",
            },
            {"url": "https://example.com/blog", "domain": "example.com", "title": "Blog"},
        ]
        results = agent._phase3_source_tiering()
        assert len(results) == 3
        assert results[0].tier == "A"
        assert results[1].tier == "B"
        assert results[2].tier == "D"

    def test_phase5_produces_report_even_without_llm(self) -> None:
        agent = DeepResearchAgent(deepseek_client=None)
        understanding = QueryUnderstanding(
            normalized_query="test",
            research_dimensions=[
                ResearchDimension(
                    dimension_id="d1",
                    label="测试维度",
                    description="测试用维度",
                    caliber_terms=["测试"],
                    source_priority="government",
                )
            ],
        )
        report = agent._phase5_report_assembly(
            query="test query",
            understanding=understanding,
            evidence_items=[],
            source_assessments=[],
        )
        assert isinstance(report, DeepResearchReport)
        assert report.query == "test query"

    def test_convenience_entry_point(self) -> None:
        report = deep_research("广东人形机器人")
        assert isinstance(report, DeepResearchReport)
        assert report.query == "广东人形机器人"
