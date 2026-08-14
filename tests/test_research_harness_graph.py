import json
from pathlib import Path
from time import sleep
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import (
    Citation,
    Document,
    DocumentChunk,
    ResearchGraphCheckpoint,
    Run,
    RunStep,
)
from packages.db.models.enums import RunStatus
from packages.db.session import reset_db_session_state
from packages.providers.base import JsonProviderResponse, ProviderCallMetadata
from packages.research_harness import nodes as harness_nodes
from packages.research_harness import real_nodes
from packages.research_harness.checkpoints import GraphCheckpointRepository
from packages.research_harness.context import build_context_pack_summary
from packages.research_harness.contracts import EditorDraftOutput, coerce_model_output
from packages.research_harness.persistence import GraphBusinessRecordRepository
from packages.research_harness.plan_semantic import SemanticPlanResult
from packages.research_harness.runner import ResearchGraphRunner
from packages.research_harness.schemas import GraphAnalyzeRequest
from packages.research_harness.tooling.llm_agents import StructuredLlmCallResult
from packages.research_reports.service import ResearchReportService
from packages.sources.enums import ToolErrorCode, ToolStatus
from packages.sources.schemas import ToolError
from packages.sources.search_discovery import (
    TavilySearchRequest,
    TavilySearchResponse,
    TavilySearchResult,
    TavilyUsageMetadata,
)


class _FakeSearchProvider:
    """Deterministic mock of Tavily search.

    Returns a diverse set of results (policy / procurement / statistics /
    disclosure) so collect_sources can accumulate multiple sources across the
    many search rounds of a run. Without this diversity, every round returns the
    same URL, the URL-dedup collapses the run to a single source, and the
    dimension-coverage gate (evidence-view) can never reach PASS.
    """

    _RESULTS = [
        TavilySearchResult(
            title="低空经济政策通知 2025",
            url="https://www.gov.cn/zhengce/2025-low-altitude-policy.html",
            content="国务院有关低空经济政策通知，提出支持低空经济应用场景建设。",
            score=0.91,
            published_date="2025-01-15",
            raw_content=(
                "[首页] 打印 收藏 javascript:void(0) 政策正文：国务院发布关于支持低空经济"
                "发展的政策通知。通知提出到2025年建成一批低空经济示范应用场景，设立专项补贴基金"
                "支持通用航空基础设施建设。通知明确推动无人机物流、低空旅游、应急救援等应用场景"
                "落地，并要求各省出台配套实施方案。主管部门为民航局和发改委，政策实施期限为"
                "2025年至2027年，鼓励地方政府配套产业基金支持低空经济产业链发展，推动空域管理"
                "改革试点，支持有条件的城市开展无人机配送商业化运营。"
            ),
        ),
        TavilySearchResult(
            title="低空经济示范项目中标公告 2025",
            url="https://www.ggzy.gov.cn/award/2025-low-altitude-award.html",
            content="公共资源交易中心发布低空经济示范项目中标公告，包含项目结果。",
            score=0.93,
            published_date="2025-05-20",
            raw_content=(
                "[首页] 打印 收藏 javascript:void(0) 中标公告正文：合肥低空经济示范项目"
                "完成评审并发布中标结果，项目金额约1.2亿元。中标企业为某通用航空公司，建设内容"
                "包括无人机起降场和低空飞行服务系统。项目招标由合肥市公共资源交易中心组织，"
                "招标编号为HF2025-001，建设周期为2025年6月至2026年12月。中标通知书已发出，"
                "要求中标企业在30日内签订合同并缴纳履约保证金。项目建成后将服务低空物流和"
                "应急救援场景，预计年运营能力达到10万架次起降。"
            ),
        ),
        TavilySearchResult(
            title="低空经济运行统计公报 2025",
            url="https://www.stats.gov.cn/bulletin/2025-low-altitude.html",
            content="统计公报披露低空经济项目数量和投资规模。",
            score=0.88,
            published_date="2025-06-10",
            raw_content=(
                "[首页] 打印 收藏 javascript:void(0) 统计公报正文：2025年上半年全国低空经济"
                "相关项目投资规模达到350亿元，同比增长42%。新增通用航空企业87家，无人机注册"
                "数量突破130万架。低空经济相关产业园区达到45个，从业人员超过80万人。统计口径"
                "覆盖无人机研发制造、运营服务、基础设施三类，其中运营服务规模占比最大达到55%。"
                "预计2025年全年低空经济市场规模将达到1200亿元，无人机物流订单量同比增长"
                "68%，低空旅游项目接待游客数量超过500万人次。"
            ),
        ),
        TavilySearchResult(
            title="某上市公司低空经济业务披露公告",
            url="https://www.cninfo.com.cn/disclosure/2025-low-altitude.html",
            content="公司披露低空经济业务进展和订单情况。",
            score=0.86,
            published_date="2025-04-18",
            raw_content=(
                "[首页] 打印 收藏 javascript:void(0) 公告正文：公司公告披露低空经济业务"
                "取得重大进展，与某地方政府签订无人机物流合作协议，涉及订单金额约5000万元。"
                "公司主营业务为无人机整机制造，2024年年报显示低空经济业务收入同比增长35%，"
                "毛利率达到42%。公司已获得民用无人驾驶航空器运营合格证，正在申请扩大运营范围，"
                "预计2025年将新增低空物流航线20条。公司表示将加大低空经济领域研发投入，"
                "计划建设无人机研发测试基地。"
            ),
        ),
        TavilySearchResult(
            title="合肥市低空经济工作方案",
            url="https://www.hefei.gov.cn/policy/2025-low-altitude-plan.html",
            content="合肥市发布低空经济工作方案，推进场景建设。",
            score=0.9,
            published_date="2025-03-20",
            raw_content=(
                "[首页] 打印 收藏 javascript:void(0) 政策正文：合肥市发布低空经济高质量"
                "发展工作方案，提出到2027年建成低空经济产业集聚区。方案重点支持无人机制造、"
                "低空物流和低空旅游场景，配套出台产业扶持基金政策，设立每年2亿元的专项扶持"
                "资金。方案明确加快低空飞行服务站和起降点建设，规划新建起降点50个，推进"
                "肥东、肥西、长丰等区县示范应用，支持企业申报低空经济示范项目，对获批项目"
                "给予最高500万元补贴。"
            ),
        ),
    ]

    def search(self, request: TavilySearchRequest) -> TavilySearchResponse:
        query = request.query
        if "ggzy.gov.cn" in request.include_domains or "ccgp.gov.cn" in request.include_domains:
            results = [self._RESULTS[1]]
        else:
            # 无 domain 定向：返回多样结果（去重后保留多 source），模拟真实 Tavily。
            results = list(self._RESULTS)
        return TavilySearchResponse(
            status=ToolStatus.SUCCESS,
            query=query,
            results=results,
            usage=TavilyUsageMetadata(
                search_depth="basic",
                max_results=request.max_results or 5,
                estimated_credits=1,
                result_count=len(results),
                request_params={"query": query},
            ),
        )

    def search_task(self, task):
        return []


class _PolicyOnlySearchProvider:
    def search(self, request: TavilySearchRequest) -> TavilySearchResponse:
        return TavilySearchResponse(
            status=ToolStatus.SUCCESS,
            query=request.query,
            results=[
                TavilySearchResult(
                    title="低空经济政策通知 2025",
                    url="https://www.gov.cn/zhengce/2025-low-altitude-policy.html",
                    content="国务院有关低空经济政策通知，提出支持应用场景建设。",
                    score=0.91,
                    published_date="2025-01-15",
                    raw_content="政策正文：支持低空经济应用场景建设。",
                )
            ],
            usage=TavilyUsageMetadata(
                search_depth="basic",
                max_results=request.max_results or 5,
                estimated_credits=1,
                result_count=1,
                request_params={"query": request.query},
            ),
        )

    def search_task(self, task):
        return []


class _FlakyThenSuccessSearchProvider:
    def __init__(self) -> None:
        self.calls_by_query: dict[str, int] = {}

    def search(self, request: TavilySearchRequest) -> TavilySearchResponse:
        count = self.calls_by_query.get(request.query, 0) + 1
        self.calls_by_query[request.query] = count
        if count == 1:
            return TavilySearchResponse(
                status=ToolStatus.ERROR,
                query=request.query,
                results=[],
                errors=[
                    ToolError(
                        code=ToolErrorCode.INTERNAL_ERROR,
                        message="[SSL: UNEXPECTED_EOF_WHILE_READING]",
                        retryable=True,
                    )
                ],
                usage=TavilyUsageMetadata(
                    search_depth="basic",
                    max_results=request.max_results or 5,
                    estimated_credits=1,
                    result_count=0,
                    request_params={"query": request.query},
                ),
            )
        return _FakeSearchProvider().search(request)

    def search_task(self, task):
        return []


class _SpamHeavySearchProvider:
    def search(self, request: TavilySearchRequest) -> TavilySearchResponse:
        results = [
            TavilySearchResult(
                title="心悦直播app官网版下载安卓",
                url="http://byzx.baoying.gov.cn/admin/kindeditor/attached/file/live-app.html",
                content="直播app下载介绍页面。",
                score=0.99,
                published_date="2025-06-01",
                raw_content="直播app下载介绍页面。",
            ),
            TavilySearchResult(
                title="小红书下载|《双生幻想》赛特降临剧情挑战攻略出炉，轻松通关赢 ...",
                url="http://byzx.baoying.gov.cn/admin/kindeditor/attached/file/game-guide.html",
                content="游戏下载和攻略页面。",
                score=0.98,
                published_date="2025-06-01",
                raw_content="游戏下载和攻略页面。",
            ),
            TavilySearchResult(
                title="合肥低空经济工作方案",
                url="https://www.hefei.gov.cn/policy/low-altitude-plan.html",
                content="合肥发布低空经济工作方案，推进场景建设和项目公示。",
                score=0.95,
                published_date="2025-03-20",
                raw_content="合肥发布低空经济工作方案，推进场景建设和项目公示。",
            ),
        ]
        return TavilySearchResponse(
            status=ToolStatus.SUCCESS,
            query=request.query,
            results=results,
            usage=TavilyUsageMetadata(
                search_depth="basic",
                max_results=request.max_results or 5,
                estimated_credits=1,
                result_count=len(results),
                request_params={"query": request.query},
            ),
        )

    def search_task(self, task):
        return []


class _FakeEditorLlmClient:
    def generate_json(self, **kwargs) -> JsonProviderResponse:  # noqa: ANN003
        _ = kwargs
        payload = {
            "draft_id": "draft_1",
            "draft_version": 1,
            "report_markdown": (
                "# low altitude economy local policy official source\n\n"
                "## Executive Summary\n\n"
                "The current draft separates policy basis from execution evidence and keeps "
                "both sections conditional pending follow-up implementation notices.\n\n"
                "## Policy Basis\n\n"
                "### low altitude economy local policy official source has official policy or "
                "regulatory grounding from auditable sources.\n\n"
                "- 论证姿态：`conditional`\n"
                "- 对应 claim：`claim_policy_primary`\n"
                "- 证据基础：官方政策原文与采购公告共同支撑当前判断。\n"
                "- 局限与条件：当前仍需结合更多执行层公告持续更新。\n\n"
                "## Local Rollout\n\n"
                "### local rollout evidence is visible, but still depends on later execution "
                "status disclosures.\n\n"
                "- 论证姿态：`conditional`\n"
                "- 对应 claim：`claim_local_rollout`\n"
                "- 证据基础：地方工作方案与项目公示片段提供了执行层线索。\n"
                "- 局限与条件：尚未纳入最终验收或长期跟踪公告。\n"
            ),
            "sections": [
                {
                    "section_id": "sec_executive_summary",
                    "title": "Executive Summary",
                    "section_role": "analysis",
                    "argument_posture": "conditional",
                    "markdown_body": (
                        "The current draft separates policy basis from execution evidence and "
                        "keeps both sections conditional pending follow-up implementation notices."
                    ),
                    "paragraphs": [
                        {
                            "paragraph_id": "p_exec_summary",
                            "text": (
                                "The report currently supports a policy basis claim and a local "
                                "rollout claim, but both remain conditional."
                            ),
                            "claim_ids": [
                                "claim_policy_primary",
                                "claim_local_rollout",
                            ],
                            "evidence_ids": ["ev_1", "ev_2"],
                            "confidence": "medium",
                            "limitations": [
                                "Execution-stage progress notices are still needed."
                            ],
                            "argument_posture": "conditional",
                        }
                    ],
                },
                {
                    "section_id": "sec_policy_basis",
                    "title": "Policy Basis",
                    "section_role": "policy_basis",
                    "argument_posture": "conditional",
                    "markdown_body": (
                        "### low altitude economy local policy official source has official "
                        "policy or regulatory grounding from auditable sources.\n\n"
                        "- 论证姿态：`conditional`\n"
                        "- 对应 claim：`claim_policy_primary`\n"
                        "- 证据基础：官方政策原文与采购公告共同支撑当前判断。\n"
                        "- 局限与条件：当前仍需结合更多执行层公告持续更新。\n"
                    ),
                    "paragraphs": [
                        {
                            "paragraph_id": "p_claim_policy_primary",
                            "text": (
                                "The query has official policy grounding supported by "
                                "the provided evidence bundle, but the current wording "
                                "remains conditional."
                            ),
                            "claim_ids": ["claim_policy_primary"],
                            "evidence_ids": ["ev_1"],
                            "confidence": "high",
                            "limitations": [
                                "Further execution-stage notices should still be tracked."
                            ],
                            "argument_posture": "conditional",
                        }
                    ],
                }
                ,
                {
                    "section_id": "sec_local_rollout",
                    "title": "Local Rollout",
                    "section_role": "local_rollout",
                    "argument_posture": "conditional",
                    "markdown_body": (
                        "### local rollout evidence is visible, but still depends on later "
                        "execution status disclosures.\n\n"
                        "- 论证姿态：`conditional`\n"
                        "- 对应 claim：`claim_local_rollout`\n"
                        "- 证据基础：地方工作方案与项目公示片段提供了执行层线索。\n"
                        "- 局限与条件：尚未纳入最终验收或长期跟踪公告。\n"
                    ),
                    "paragraphs": [
                        {
                            "paragraph_id": "p_claim_local_rollout",
                            "text": (
                                "Local rollout evidence exists in the current evidence bundle, "
                                "but the implementation status should still be tracked."
                            ),
                            "claim_ids": ["claim_local_rollout"],
                            "evidence_ids": ["ev_2"],
                            "confidence": "medium",
                            "limitations": [
                                "Execution progress and completion notices remain outstanding."
                            ],
                            "argument_posture": "conditional",
                        }
                    ],
                },
            ],
        }
        return JsonProviderResponse(
            provider="deepseek",
            model="deepseek-chat",
            content_text="{}",
            json_data=payload,
            metadata=ProviderCallMetadata(
                provider="deepseek",
                model="deepseek-chat",
                request_id="editor-req-1",
                usage={"prompt_tokens": 10, "completion_tokens": 12},
                finish_reason="stop",
                response_ms=12.5,
            ),
        )


def _setup_graph_db(monkeypatch, tmp_path: Path) -> str:
    db_path = tmp_path / "research_graph.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    reset_db_session_state()
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return db_url


def _unlink_with_retry(path: Path, *, attempts: int = 5, delay_seconds: float = 0.1) -> None:
    last_error: OSError | None = None
    for _ in range(attempts):
        try:
            path.unlink()
            return
        except OSError as exc:
            last_error = exc
            sleep(delay_seconds)
    if last_error is not None:
        raise last_error


def test_graph_runner_loops_then_passes(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        result = ResearchGraphRunner(session).run(
            GraphAnalyzeRequest(query="低空经济 中标公告", max_rounds=2, max_loop_count=2)
        )
        run = session.get(Run, result.run_id)
        steps = session.scalars(select(RunStep).where(RunStep.run_id == result.run_id)).all()

        run = session.get(Run, result.run_id)
        steps = session.scalars(select(RunStep).where(RunStep.run_id == result.run_id)).all()

    assert result.status == "succeeded"
    assert result.thread_id == f"research_run:{result.run_id}"
    assert result.decision == "PASS"
    # 维度覆盖允许空缺：过半达标即 PASS（未覆盖维度在 gate_reason 标注）
    assert result.quality_scores["evidence_coverage"] >= 0.5
    assert len(result.context_packs) >= len(result.node_steps)
    assert any(step.node_name == "chief_gate" for step in result.node_steps)
    parse_pack = next(pack for pack in result.context_packs if pack.node_name == "parse_sources")
    assert parse_pack.prompt_version == "shadow_v1.parse_sources"
    assert "sources" in parse_pack.included_fields
    assert parse_pack.sanitization_summary["removed_marker_count"] >= 1
    assert {step.step_name for step in steps} >= {
        "plan_task",
        "collect_sources",
        "parse_sources",
        "score_sources",
        "build_evidence",
        "editor1_draft",
        "editor2_review",
        "chief_gate",
        "finalize_report",
    }
    assert run is not None
    assert run.status == RunStatus.SUCCEEDED
    assert run.input_json["pipeline"] == "langgraph_research_harness_v1"
    assert run.input_json["thread_id"] == result.thread_id
    assert result.dossier_path
    assert Path(result.dossier_path).exists()
    assert run.output_json["dossier_path"] == result.dossier_path
    assert result.checkpoint_path
    assert Path(result.checkpoint_path).exists()
    assert run.output_json["checkpoint_path"] == result.checkpoint_path
    gate_steps = [step for step in steps if step.step_name == "chief_gate"]
    gate_step = gate_steps[0]
    assert gate_step.output_json["gate_reason"]
    assert gate_step.output_json["dimension_coverage"]
    assert gate_step.output_json["quality_scores"]["evidence_coverage"] >= 0
    parse_step = next(step for step in steps if step.step_name == "parse_sources")
    assert parse_step.output_json["context_pack_summary"]["node_name"] == "parse_sources"
    assert parse_step.output_json["context_pack_summary"]["sanitization_summary"][
        "removed_marker_count"
    ] >= 1

    with Session(engine) as session:
        checkpoint = session.scalar(
            select(ResearchGraphCheckpoint).where(
                ResearchGraphCheckpoint.run_id == result.run_id
            )
        )
    assert checkpoint is not None
    assert checkpoint.run_id == result.run_id
    assert checkpoint.thread_id == result.thread_id
    assert checkpoint.checkpoint_version >= 1
    assert result.checkpoint_history
    assert result.checkpoint_history[0].checkpoint_version >= 1


def test_graph_runner_hits_human_review_when_loop_budget_is_zero(
    monkeypatch, tmp_path: Path
) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        result = ResearchGraphRunner(session).run(
            GraphAnalyzeRequest(query="低空经济 中标公告", max_rounds=1, max_loop_count=0)
        )
        run = session.get(Run, result.run_id)
        steps = session.scalars(select(RunStep).where(RunStep.run_id == result.run_id)).all()

    assert result.status == "succeeded"
    assert result.decision == "HUMAN_REVIEW"
    assert result.human_review is not None
    assert result.human_review.pending is True
    assert result.human_review.status == "pending"
    assert result.human_review.gate_reason
    assert result.human_review.supported_actions == [
        "approve",
        "add_evidence",
        "rewrite",
        "reject",
    ]
    assert result.quality_scores["evidence_coverage"] < 0.5
    assert result.human_review.required_actions
    assert result.human_review.required_actions[0]["action_type"] == "HUMAN_REVIEW"
    assert any(step.node_name == "human_review" for step in result.node_steps)
    assert not any(step.node_name == "finalize_report" for step in result.node_steps)
    assert result.report_preview == {}
    assert run is not None
    assert run.output_json["human_review"]["pending"] is True
    assert not run.output_json["report_preview"]
    assert {step.step_name for step in steps} >= {
        "plan_task",
        "collect_sources",
        "parse_sources",
        "score_sources",
        "build_evidence",
        "editor1_draft",
        "editor2_review",
        "chief_gate",
        "human_review",
    }
    assert "finalize_report" not in {step.step_name for step in steps}


def test_graph_runner_resume_from_pending_human_review_approval(
    monkeypatch, tmp_path: Path
) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    query = "\u4f4e\u7a7a\u7ecf\u6d4e \u4e2d\u6807\u516c\u544a"

    with Session(engine) as session:
        first = ResearchGraphRunner(session).run(
            GraphAnalyzeRequest(query=query, max_rounds=1, max_loop_count=0)
        )
        resumed = ResearchGraphRunner(session).run(
            GraphAnalyzeRequest(
                query=query,
                max_rounds=1,
                max_loop_count=0,
                resume_run_id=first.run_id,
                human_review_action="approve",
                human_review_notes="Evidence is sufficient for publication.",
            )
        )
        run = session.get(Run, first.run_id)
        steps = session.scalars(select(RunStep).where(RunStep.run_id == first.run_id)).all()

    assert first.decision == "HUMAN_REVIEW"
    assert first.human_review is not None
    assert first.human_review.pending is True
    assert resumed.run_id == first.run_id
    assert resumed.resumed_from_checkpoint is True
    assert resumed.status == "succeeded"
    assert resumed.decision == "PASS"
    assert resumed.human_review is not None
    assert resumed.human_review.pending is False
    assert resumed.human_review.status == "approved"
    assert resumed.human_review.selected_action == "approve"
    assert resumed.human_review.notes == "Evidence is sufficient for publication."
    assert resumed.report_preview["report_id"] > 0
    assert any(step.node_name == "human_review" for step in resumed.node_steps)
    assert any(step.node_name == "finalize_report" for step in resumed.node_steps)
    assert run is not None
    assert run.output_json["decision"] == "PASS"
    assert run.output_json["human_review"]["status"] == "approved"
    assert any(step.step_name == "finalize_report" for step in steps)


def test_graph_runner_keeps_runtime_documents_while_human_review_is_pending(
    monkeypatch, tmp_path: Path
) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        result = ResearchGraphRunner(session).run(
            GraphAnalyzeRequest(query="低空经济 中标公告", max_rounds=1, max_loop_count=0)
        )
        runtime_documents = session.scalars(
            select(Document).where(Document.content_hash.like(f"graph:{result.run_id}:%"))
        ).all()
        runtime_chunks = session.scalars(
            select(DocumentChunk).join(Document, Document.id == DocumentChunk.document_id).where(
                Document.content_hash.like(f"graph:{result.run_id}:%")
            )
        ).all()

    assert result.decision == "HUMAN_REVIEW"
    assert result.human_review is not None
    assert result.human_review.pending is True
    assert runtime_documents
    assert runtime_chunks


def test_graph_runner_cleans_runtime_documents_after_terminal_completion(
    monkeypatch, tmp_path: Path
) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    real_nodes.set_search_provider_override(_FakeSearchProvider())

    try:
        with Session(engine) as session:
            result = ResearchGraphRunner(session).run(
                GraphAnalyzeRequest(
                    query="低空经济 中标公告",
                    max_rounds=2,
                    max_loop_count=2,
                    execution_mode="provider_backed",
                )
            )
            remaining_documents = session.scalars(
                select(Document).where(Document.content_hash.like(f"graph:{result.run_id}:%"))
            ).all()
            remaining_chunks = session.scalars(
                select(DocumentChunk)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(Document.content_hash.like(f"graph:{result.run_id}:%"))
            ).all()
            remaining_citations = session.scalars(
                select(Citation)
                .join(Document, Document.id == Citation.document_id)
                .where(Document.content_hash.like(f"graph:{result.run_id}:%"))
            ).all()
            run = session.get(Run, result.run_id)
    finally:
        real_nodes.set_search_provider_override(None)

    assert result.decision == "PASS"
    assert remaining_documents == []
    assert remaining_chunks == []
    assert remaining_citations == []
    assert run is not None
    assert run.output_json["graph_runtime_cleanup"]["status"] == "cleaned"
    assert run.output_json["graph_runtime_cleanup"]["retention_policy"] == (
        "delete_on_terminal_run"
    )


def test_graph_runner_provider_backed_uses_search_provider(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    real_nodes.set_search_provider_override(_FakeSearchProvider())
    monkeypatch.setattr(
        real_nodes,
        "call_tooling_json",
        lambda **kwargs: type(
            "FakeResult",
            (),
            {
                "payload": None,
                "metadata": {
                    "llm_mode": "deterministic_fallback",
                    "llm_reason": "test_stubbed_for_runner_contract",
                },
            },
        )(),
    )

    try:
        with Session(engine) as session:
            result = ResearchGraphRunner(session).run(
                GraphAnalyzeRequest(
                    query="低空经济 中标公告",
                    max_rounds=2,
                    max_loop_count=2,
                    execution_mode="provider_backed",
                )
            )
            report = ResearchReportService(session).get_report(
                result.report_preview["report_id"]
            )
            run = session.get(Run, result.run_id)
            steps = session.scalars(
                select(RunStep).where(RunStep.run_id == result.run_id)
            ).all()
            run_output_json = dict(run.output_json or {}) if run is not None else {}
    finally:
        real_nodes.set_search_provider_override(None)

    assert result.status == "succeeded"
    assert result.decision == "PASS"
    assert "共形成" in result.report_preview["executive_summary"]
    assert "PASS" in result.report_preview["executive_summary"]
    assert "report_markdown" in result.report_preview
    # evidence 视角报告：editor1 用 evidence 写中文章节（不再有英文 Key Claims 结构）。
    assert "## 执行摘要" in result.report_preview["report_markdown"]
    assert "## 研究方法与边界" in result.report_preview["report_markdown"]
    assert result.report_preview["evidence_count"] >= 2
    assert result.report_preview["sections"]
    assert any(
        section["section_id"] == "key_claims" for section in result.report_preview["sections"]
    )
    assert result.report_preview["report_id"] > 0
    assert result.report_preview["report_artifact"]["workflow_version"] == "graph_v1"
    assert result.report_preview["report_artifact"]["graph_run_id"] == result.run_id
    assert report is not None
    assert report.dossier_path == result.dossier_path
    assert report.report_json["workflow_version"] == "graph_v1"
    assert report.report_json["graph_run_id"] == result.run_id
    assert report.report_json["thread_id"] == result.thread_id
    assert report.report_json["dossier_path"] == result.dossier_path
    assert "report_markdown" in report.report_json
    assert "## 执行摘要" in report.report_json["report_markdown"]
    assert report.report_json["compliance_statement"]
    assert run is not None
    assert run_output_json["report_preview"]["report_id"] == result.report_preview["report_id"]
    assert run.input_json["execution_mode"] == "provider_backed"
    assert run.input_json["strategy"] == "provider_backed_v1"
    collect_steps = [step for step in steps if step.step_name == "collect_sources"]
    collect_step = max(
        collect_steps,
        key=lambda step: int(step.output_json.get("source_count", 0)),
    )
    assert collect_step.output_json["source_count"] >= 2
    assert collect_step.output_json["search_events"]
    assert all("mock" not in source_id for source_id in collect_step.output_json["source_ids"])
    score_step = next(step for step in steps if step.step_name == "score_sources")
    score_pack = score_step.output_json["context_pack_summary"]
    assert score_pack["prompt_version"] == "provider_backed_v1.score_sources"
    plan_step = next(step for step in steps if step.step_name == "plan_task")
    assert plan_step.output_json["plan_summary"]["research_dimension_count"] >= 2
    assert plan_step.output_json["plan_summary"]["dimension_plan_count"] >= 2
    assert "policy" in plan_step.output_json["plan_summary"]["dimension_types"]
    parse_step = next(step for step in steps if step.step_name == "parse_sources")
    assert parse_step.output_json["source_chunk_count"] >= 1
    assert parse_step.output_json["retrieval_pack_summary"]["retrieval_mode"] == (
        "graph_runtime_rank_v1"
    )
    assert parse_step.output_json["retrieval_pack_summary"]["adapter_status"] == (
        "persistent_graph_documents"
    )
    assert parse_step.output_json["retrieval_pack_summary"]["backend_retrieval_mode"].startswith(
        "graph_persistent_retrieval_adapter_v1"
    )
    assert parse_step.output_json["retrieval_pack_summary"]["returned_count"] >= 1
    evidence_step = next(step for step in steps if step.step_name == "build_evidence")
    assert evidence_step.output_json["evidence_count"] >= 2
    assert "direct_support" in evidence_step.output_json["support_types"]
    editor_step = next(step for step in steps if step.step_name == "editor1_draft")
    assert (
        editor_step.output_json["context_pack_summary"]["prompt_version"]
        == "provider_backed_v1.editor1_draft"
    )
    assert (
        editor_step.output_json["contract_meta"]["editor1_draft"]["input_mode"]
        == "provider_backed_v1"
    )
    review_step = next(step for step in steps if step.step_name == "editor2_review")
    assert (
        review_step.output_json["context_pack_summary"]["prompt_version"]
        == "provider_backed_v1.editor2_review"
    )
    assert (
        review_step.output_json["contract_meta"]["editor2_review"]["input_mode"]
        == "provider_backed_v1"
    )
    gate_steps = [step for step in steps if step.step_name == "chief_gate"]
    gate_step = gate_steps[-1]
    assert (
        gate_step.output_json["context_pack_summary"]["prompt_version"]
        == "provider_backed_v1.chief_gate"
    )
    assert gate_step.output_json["dimension_coverage"]
    assert gate_step.output_json["quality_scores"]["evidence_coverage"] >= 0.5
    assert gate_step.output_json["required_actions"] == []
    assert gate_step.output_json["decision"] == "PASS"
    parse_pack = next(pack for pack in result.context_packs if pack.node_name == "parse_sources")
    assert parse_pack.prompt_version == "provider_backed_v1.parse_sources"
    assert parse_pack.context_budget_tokens is not None
    assert parse_pack.context_budget_tokens > 0
    assert parse_pack.budget_status == "unbudgeted"
    assert parse_pack.token_estimate == 0
    assert parse_pack.budget_overage_tokens == 0
    assert parse_pack.live_validation_focus
    assert parse_pack.failure_class_focus
    assert parse_pack.sanitization_summary["removed_marker_count"] >= 1
    assert result.dossier_path
    dossier_text = Path(result.dossier_path).read_text(encoding="utf-8")
    assert "规划合约" in dossier_text
    assert "Dimension Plan" in dossier_text
    assert "graph_persistent_retrieval_adapter_v1" in dossier_text
    assert "Evidence" in dossier_text


def test_graph_runner_provider_backed_editor1_records_tool_traces(
    monkeypatch, tmp_path: Path
) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    real_nodes.set_search_provider_override(_FakeSearchProvider())

    def _fake_build_semantic_plan(**kwargs):
        return SemanticPlanResult(
            payload=kwargs["fallback_payload"],
            metadata={
                "planner_mode": "deterministic_fallback",
                "planner_provider": "deterministic",
                "planner_model": "offline_rules_v1",
                "deterministic_fallback": True,
                "reason": "test_stubbed_for_editor_tool_trace_contract",
            },
        )

    monkeypatch.setattr(real_nodes, "build_semantic_plan", _fake_build_semantic_plan)
    monkeypatch.setattr(
        real_nodes,
        "call_tooling_json",
        lambda **kwargs: StructuredLlmCallResult(
            payload=_FakeEditorLlmClient().generate_json(**kwargs).json_data,
            metadata={
                "llm_mode": "live_provider",
                "llm_reason": "provider_response_accepted",
                "llm_provider": "deepseek",
                "llm_model": "deepseek-chat",
            },
        ),
    )

    try:
        with Session(engine) as session:
            result = ResearchGraphRunner(session).run(
                GraphAnalyzeRequest(
                    query="低空经济 中标公告",
                    max_rounds=2,
                    max_loop_count=2,
                    execution_mode="provider_backed",
                )
            )
            steps = session.scalars(
                select(RunStep).where(RunStep.run_id == result.run_id)
            ).all()
    finally:
        real_nodes.set_search_provider_override(None)

    editor_step = next(step for step in steps if step.step_name == "editor1_draft")
    review_step = next(step for step in steps if step.step_name == "editor2_review")
    gate_steps = [step for step in steps if step.step_name == "chief_gate"]
    gate_step = gate_steps[0]
    final_gate_step = gate_steps[-1]
    tool_traces = editor_step.output_json["tool_traces"]
    finalize_step = next(
        (step for step in steps if step.step_name == "finalize_report"),
        None,
    )
    human_review_step = next(
        (step for step in steps if step.step_name == "human_review"),
        None,
    )

    assert result.status == "succeeded"
    assert tool_traces
    assert any(trace["tool_name"] == "get_evidence_bundle" for trace in tool_traces)
    assert any(trace["tool_name"] == "compose_section_outline" for trace in tool_traces)
    assert all(trace["tool_name"] != "write_database_record" for trace in tool_traces)
    assert editor_step.output_json["contract_meta"]["editor1_draft"]["llm_mode"] == "live_provider"
    assert any(
        trace["tool_name"] == "get_claim_support_matrix"
        for trace in review_step.output_json["tool_traces"]
    )
    # gate 改维度覆盖判定（不再 claim 判定），不记录 claim_support_matrix trace；
    # 断言 evidence 视角的覆盖输出。
    assert gate_step.output_json["dimension_coverage"]
    assert finalize_step is not None or human_review_step is not None
    if finalize_step is not None:
        assert any(
            trace["tool_name"] == "compose_final_report"
            for trace in finalize_step.output_json["tool_traces"]
        )
        report_markdown = result.report_preview.get("report_markdown", "")
        assert "## Executive Summary" in report_markdown or "## 执行摘要" in report_markdown
        assert "## Policy Basis" in report_markdown or "政策" in report_markdown
    else:
        assert final_gate_step.output_json["decision"] == "HUMAN_REVIEW"
        assert human_review_step is not None
        assert human_review_step.output_json["human_review"]["pending"] is True
        draft_snapshot = human_review_step.output_json["human_review"]["draft_snapshot"]
        snapshot_markdown = draft_snapshot.get("report_markdown", "")
        assert "## Executive Summary" in snapshot_markdown or "## 执行摘要" in snapshot_markdown
        assert "## Policy Basis" in snapshot_markdown or "政策" in snapshot_markdown
    assert review_step.output_json["issue_count"] >= 0
    assert final_gate_step.output_json["decision"] in {
        "PASS",
        "ADD_EVIDENCE",
        "REVISE_TEXT",
        "HUMAN_REVIEW",
    }
    assert (
        final_gate_step.output_json["required_actions"]
        or final_gate_step.output_json["decision"] == "PASS"
    )
    assert result.dossier_path
    dossier_text = Path(result.dossier_path).read_text(encoding="utf-8")
    assert "## 5. Tool Traces" in dossier_text or "工具调用轨迹" in dossier_text
    assert "get_evidence_bundle" in dossier_text
    assert (
        "compose_final_report" in dossier_text
        or "get_claim_support_matrix" in dossier_text
    )


def test_graph_runner_persists_business_records_idempotently(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    real_nodes.set_search_provider_override(_FakeSearchProvider())

    try:
        with Session(engine) as session:
            result = ResearchGraphRunner(session).run(
                GraphAnalyzeRequest(
                    query="low altitude economy procurement award notice",
                    max_rounds=2,
                    max_loop_count=2,
                    execution_mode="provider_backed",
                )
            )
            repository = GraphBusinessRecordRepository(session)
            records = repository.load_run_records(result.run_id)
            support_matrix = repository.build_claim_support_matrix(result.run_id)
            counts_before = repository.record_counts(result.run_id)
            checkpoint = GraphCheckpointRepository(session=session).load(run_id=result.run_id)
            assert checkpoint is not None
            repository.persist_state(checkpoint["state"])
            counts_after = repository.record_counts(result.run_id)
    finally:
        real_nodes.set_search_provider_override(None)

    assert result.status == "succeeded"
    assert len(records["sources"]) >= 2
    assert len(records["evidence"]) >= 2
    # evidence 视角：claims/verify 已砍，业务记录只保留 sources/evidence/draft/gate。
    assert records["claims"] == []
    assert records["claim_verifications"] == []
    assert records["draft_versions"]
    assert records["quality_gate_results"][0]["decision"] in {
        "PASS",
        "HUMAN_REVIEW",
        "ADD_EVIDENCE",
        "REVIEW_RISK",
    }
    assert records["quality_gate_results"][0]["quality_scores"]["evidence_coverage"] >= 0
    assert counts_after == counts_before


def test_graph_runner_provider_backed_requires_procurement_evidence(
    monkeypatch, tmp_path: Path
) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    real_nodes.set_search_provider_override(_PolicyOnlySearchProvider())

    try:
        with Session(engine) as session:
            result = ResearchGraphRunner(session).run(
                GraphAnalyzeRequest(
                    query="低空经济 中标公告",
                    max_rounds=2,
                    max_loop_count=1,
                    execution_mode="provider_backed",
                )
            )
            steps = session.scalars(
                select(RunStep).where(RunStep.run_id == result.run_id)
            ).all()
    finally:
        real_nodes.set_search_provider_override(None)

    assert result.status == "succeeded"
    assert result.decision == "HUMAN_REVIEW"
    # evidence 视角：无 verify_claims，procurement 证据不足 → gate ADD_EVIDENCE 补
    # project_execution/tender 维度（required_actions 用 target 维度 id）。
    gate_steps = [step for step in steps if step.step_name == "chief_gate"]
    assert any(
        any(
            action.get("action_type") == "ADD_EVIDENCE"
            and str(action.get("target") or "") in {"project_execution", "d_execution", "d_project_execution", "d_project_execution"}
            for action in step.output_json.get("required_actions", [])
        )
        for step in gate_steps
    )


def test_graph_runner_provider_backed_retries_retryable_search_errors(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(real_nodes, "SEARCH_RETRY_BACKOFF_SECONDS", 0)
    monkeypatch.setattr(real_nodes, "sleep", lambda _: None)
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    fake_provider = _FlakyThenSuccessSearchProvider()
    real_nodes.set_search_provider_override(fake_provider)

    try:
        with Session(engine) as session:
            result = ResearchGraphRunner(session).run(
                GraphAnalyzeRequest(
                    query="低空经济 中标公告",
                    max_rounds=2,
                    max_loop_count=1,
                    execution_mode="provider_backed",
                )
            )
            steps = session.scalars(
                select(RunStep).where(RunStep.run_id == result.run_id)
            ).all()
    finally:
        real_nodes.set_search_provider_override(None)

    assert result.status == "succeeded"
    collect_step = next(step for step in steps if step.step_name == "collect_sources")
    search_events = collect_step.output_json["search_events"]
    assert search_events
    assert all(event["status"] == "success" for event in search_events)
    assert any(event["attempt_count"] == 2 for event in search_events)
    assert any(event["retry_count"] == 1 for event in search_events)
    assert any("error" in event["attempt_statuses"] for event in search_events)


def test_graph_runner_provider_backed_disclosure_query_requires_disclosure_sources(
    monkeypatch, tmp_path: Path
) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    real_nodes.set_search_provider_override(_FakeSearchProvider())

    try:
        with Session(engine) as session:
            result = ResearchGraphRunner(session).run(
                GraphAnalyzeRequest(
                    query="2025年低空经济上市公司年报披露与官方政策证据",
                    max_rounds=2,
                    max_loop_count=1,
                    execution_mode="provider_backed",
                )
            )
            steps = session.scalars(
                select(RunStep).where(RunStep.run_id == result.run_id)
            ).all()
    finally:
        real_nodes.set_search_provider_override(None)

    assert result.status == "succeeded"
    assert result.decision in {"ADD_EVIDENCE", "HUMAN_REVIEW"}
    gate_step = next(step for step in steps if step.step_name == "chief_gate")
    assert gate_step.output_json["contract_meta"]["chief_gate"]["obligation_gap_count"] >= 1
    assert any(
        item.get("source_family") == "company_disclosure" and item.get("covered") is False
        for item in gate_step.output_json["contract_meta"]["chief_gate"][
            "required_obligation_coverage"
        ]
    )
    assert any(
        action.get("required_source_family") == "company_disclosure"
        for action in gate_step.output_json.get("required_actions", [])
    )
    assert gate_step.output_json["planner_replan_request"]["reason"] == "chief_gate_add_evidence"
    assert "company_disclosure" in gate_step.output_json["planner_replan_request"][
        "obligation_gap_families"
    ]


def test_collect_sources_provider_backed_filters_spam_and_keeps_location_match() -> None:
    real_nodes.set_search_provider_override(_SpamHeavySearchProvider())
    try:
        result = real_nodes.collect_sources_provider_backed(
            {
                "query": "2025年合肥低空经济地方政策项目公示官方来源",
                "max_rounds": 1,
                "query_requirements": {
                    "needs_company_disclosure": False,
                    "target_location": "合肥",
                    "is_location_sensitive": True,
                },
                "plan": {
                    "search_rounds": [
                        {
                            "round_number": 1,
                            "objective": "collect local policy rollout",
                            "search_phrases": ["合肥 低空经济 工作方案"],
                            "include_domains": ["gov.cn"],
                            "target_dimensions": ["d_local_rollout"],
                            "expected_source_tier": "A",
                        }
                    ]
                },
                "sources": [],
                "search_events": [],
            }
        )
    finally:
        real_nodes.set_search_provider_override(None)

    assert len(result["sources"]) == 1
    source = result["sources"][0]
    # G4 后 collect 阶段不再算 source_quality_v2（score_sources 单点统一评分）；
    # 这里断言 collect 的原始元数据 + 过滤语义。
    assert source["source_family"] == "policy_document"
    assert source["url"] == "https://www.hefei.gov.cn/policy/low-altitude-plan.html"
    assert source["target_source_family_match"] is True
    assert result["sources"][0]["title"] == "合肥低空经济工作方案"
    event = result["search_events"][0]
    assert event["accepted_result_count"] == 1
    assert event["rejected_result_count"] >= 2
    assert event["rejected_reasons"].get("spam_or_content_farm", 0) >= 2


def test_graph_runner_provider_backed_local_query_flags_low_location_precision(
    monkeypatch, tmp_path: Path
) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    real_nodes.set_search_provider_override(_FakeSearchProvider())

    try:
        with Session(engine) as session:
            result = ResearchGraphRunner(session).run(
                GraphAnalyzeRequest(
                    query="2025年合肥低空经济地方政策项目公示官方来源",
                    max_rounds=2,
                    max_loop_count=1,
                    execution_mode="provider_backed",
                )
            )
            steps = session.scalars(
                select(RunStep).where(RunStep.run_id == result.run_id)
            ).all()
    finally:
        real_nodes.set_search_provider_override(None)

    assert result.status == "succeeded"
    assert result.decision in {"HUMAN_REVIEW", "ADD_EVIDENCE"}
    # evidence 视角：gate 用 dimension_coverage，不再产字节码 local_precision/obligation。
    gate_step = next(step for step in steps if step.step_name == "chief_gate")
    assert gate_step.output_json["dimension_coverage"]
    assert gate_step.output_json["quality_scores"]["evidence_coverage"] < 0.5


def test_graph_runner_provider_backed_high_search_error_rate_blocks_clean_pass(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(real_nodes, "SEARCH_RETRY_BACKOFF_SECONDS", 0)
    monkeypatch.setattr(real_nodes, "sleep", lambda _: None)
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    fake_provider = _FlakyThenSuccessSearchProvider()
    real_nodes.set_search_provider_override(fake_provider)

    try:
        with Session(engine) as session:
            result = ResearchGraphRunner(session).run(
                GraphAnalyzeRequest(
                    query="2025年低空经济上市公司年报披露与官方政策证据",
                    max_rounds=2,
                    max_loop_count=1,
                    execution_mode="provider_backed",
                )
            )
            steps = session.scalars(
                select(RunStep).where(RunStep.run_id == result.run_id)
            ).all()
    finally:
        real_nodes.set_search_provider_override(None)

    assert result.status == "succeeded"
    gate_step = next(step for step in steps if step.step_name == "chief_gate")
    gate_meta = gate_step.output_json["contract_meta"]["chief_gate"]
    assert gate_meta["unstable_search_rate"] > 0.30
    assert result.decision in {"REVIEW_RISK", "ADD_EVIDENCE", "HUMAN_REVIEW"}


def test_graph_runner_phase3_contract_fallbacks_are_visible(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)
    real_nodes.set_search_provider_override(_FakeSearchProvider())

    # 用结构化无效输出驱动 editor1/editor2 走 fallback 契约（provider 路径）。
    monkeypatch.setattr(
        real_nodes,
        "call_tooling_json",
        lambda **kwargs: StructuredLlmCallResult(
            payload=_FakeEditorLlmClient().generate_json(**kwargs).json_data,
            metadata={
                "llm_mode": "live_provider",
                "llm_reason": "provider_response_accepted",
                "llm_provider": "deepseek",
                "llm_model": "deepseek-chat",
            },
        ),
    )

    query = "低空经济 中标公告"
    try:
        with Session(engine) as session:
            result = ResearchGraphRunner(session).run(
                GraphAnalyzeRequest(
                    query=query, max_rounds=2, max_loop_count=1, execution_mode="provider_backed"
                )
            )
            steps = session.scalars(
                select(RunStep).where(RunStep.run_id == result.run_id)
            ).all()
    finally:
        real_nodes.set_search_provider_override(None)

    assert result.status == "succeeded"
    editor_step = next(step for step in steps if step.step_name == "editor1_draft")
    assert editor_step.output_json["contract_meta"]["editor1_draft"]["input_mode"] == (
        "provider_backed_v1"
    )
    review_step = next(step for step in steps if step.step_name == "editor2_review")
    assert review_step.output_json["contract_meta"]["editor2_review"]["input_mode"] == (
        "provider_backed_v1"
    )
    gate_step = next(step for step in steps if step.step_name == "chief_gate")
    assert gate_step.output_json["dimension_coverage"]
    assert gate_step.output_json["quality_scores"]["evidence_coverage"] >= 0


def test_graph_runner_resume_from_checkpoint(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    query = "低空经济 中标公告"
    with Session(engine) as session:
        first = ResearchGraphRunner(session).run(
            GraphAnalyzeRequest(query=query, max_rounds=2, max_loop_count=2)
        )
        assert first.checkpoint_path is not None
        _unlink_with_retry(Path(first.checkpoint_path))
        resumed = ResearchGraphRunner(session).run(
            GraphAnalyzeRequest(
                query=query,
                max_rounds=2,
                max_loop_count=2,
                resume_run_id=first.run_id,
            )
        )
        run = session.get(Run, first.run_id)
        reports = ResearchReportService(session).list_reports(limit=10)
        run_output_json = dict(run.output_json or {}) if run is not None else {}

    assert resumed.run_id == first.run_id
    assert resumed.resumed_from_checkpoint is True
    assert resumed.decision == "PASS"
    assert resumed.report_preview["report_id"] == first.report_preview["report_id"]
    assert sum(
        1
        for report in reports
        if report.query == query and report.id == resumed.report_preview["report_id"]
    ) == 1
    assert resumed.checkpoint_path
    assert Path(resumed.checkpoint_path).exists()
    assert run is not None
    assert run_output_json["resumed_from_checkpoint"] is True
    assert (
        resumed.checkpoint_history[0].checkpoint_version
        > first.checkpoint_history[0].checkpoint_version
    )


def test_graph_checkpoint_compaction_preserves_latest_resume(
    monkeypatch, tmp_path: Path
) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    query = "low altitude award notice"
    with Session(engine) as session:
        first = ResearchGraphRunner(session).run(
            GraphAnalyzeRequest(query=query, max_rounds=2, max_loop_count=2)
        )
        resumed_once = ResearchGraphRunner(session).run(
            GraphAnalyzeRequest(
                query=query,
                max_rounds=2,
                max_loop_count=2,
                resume_run_id=first.run_id,
            )
        )
        resumed_twice = ResearchGraphRunner(session).run(
            GraphAnalyzeRequest(
                query=query,
                max_rounds=2,
                max_loop_count=2,
                resume_run_id=first.run_id,
            )
        )

        repository = GraphCheckpointRepository(session=session)
        before_count = repository.history_count(run_id=first.run_id)
        compacted = repository.compact(run_id=first.run_id, keep_latest=2)
        after_count = repository.history_count(run_id=first.run_id)
        resumed_after_compaction = ResearchGraphRunner(session).run(
            GraphAnalyzeRequest(
                query=query,
                max_rounds=2,
                max_loop_count=2,
                resume_run_id=first.run_id,
            )
        )

    assert before_count > 2
    assert compacted["deleted_count"] == before_count - 2
    assert compacted["retained_count"] == 2
    assert after_count == 2
    assert compacted["latest_checkpoint_version"] == resumed_twice.checkpoint_history[
        0
    ].checkpoint_version
    assert resumed_after_compaction.run_id == first.run_id
    assert resumed_after_compaction.resumed_from_checkpoint is True
    assert (
        resumed_after_compaction.checkpoint_history[0].checkpoint_version
        > resumed_once.checkpoint_history[0].checkpoint_version
    )


def test_graph_runner_resume_after_failed_parse(monkeypatch, tmp_path: Path) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    failing_query = "low altitude award notice __force_fail_parse__"
    resumed_query = "low altitude award notice"
    with Session(engine) as session:
        first = ResearchGraphRunner(session).run(
            GraphAnalyzeRequest(query=failing_query, max_rounds=2, max_loop_count=2)
        )
        assert first.status == "failed"
        assert first.checkpoint_path is not None
        _unlink_with_retry(Path(first.checkpoint_path))
        resumed = ResearchGraphRunner(session).run(
            GraphAnalyzeRequest(
                query=resumed_query,
                max_rounds=2,
                max_loop_count=2,
                resume_run_id=first.run_id,
            )
        )
        run = session.get(Run, first.run_id)
        steps = session.scalars(select(RunStep).where(RunStep.run_id == first.run_id)).all()

    assert resumed.run_id == first.run_id
    assert resumed.resumed_from_checkpoint is True
    assert resumed.status == "succeeded"
    assert run is not None
    assert run.output_json["status"] == "succeeded"
    assert any(
        step.step_name == "parse_sources" and step.status.value == "failed" for step in steps
    )
    assert any(
        step.step_name == "parse_sources" and step.status.value == "succeeded" for step in steps
    )


def test_plan_task_provider_backed_prioritizes_disclosure_round_when_query_needs_it(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_build_semantic_plan(**kwargs):
        captured.update(kwargs)
        return SemanticPlanResult(
            payload=kwargs["fallback_payload"],
            metadata={
                "planner_mode": "deterministic_fallback",
                "planner_provider": "deterministic",
                "planner_model": "offline_rules_v1",
                "deterministic_fallback": True,
                "reason": "test_capture",
            },
        )

    monkeypatch.setattr(real_nodes, "build_semantic_plan", _fake_build_semantic_plan)

    result = real_nodes.plan_task_provider_backed(
        {
            "query": "2025年低空经济上市公司年报披露与官方政策证据",
            "max_rounds": 2,
            "summary_memory": {
                "recurring_themes": ["披露优先"],
                "repeated_gaps": ["缺少交易所披露"],
            },
            "planner_replan_request": {
                "reason": "chief_gate_add_evidence",
                "obligation_gap_families": ["company_disclosure"],
                "execution_term_hints": ["2025年低空经济上市公司年报披露与官方政策证据 cninfo"],
            },
        }
    )

    fallback_payload = captured["fallback_payload"]
    plan = fallback_payload["plan"]
    rounds = plan["search_rounds"]
    dimensions = {item["dimension_id"]: item for item in plan["research_dimensions"]}
    dimension_plan = {item["dimension_id"]: item for item in plan["dimension_plan"]}

    assert result["planner_metadata"]["planner_mode"] == "deterministic_fallback"
    assert result["planner_metadata"]["summary_memory_used"] is True
    assert result["planner_metadata"]["summary_memory_keys"] == [
        "recurring_themes",
        "repeated_gaps",
    ]
    assert "d_disclosure" in dimensions
    assert "d_disclosure" in dimension_plan
    assert dimension_plan["d_disclosure"]["dimension_type"] == "disclosure"
    assert plan["caliber_notes"]
    assert len(rounds) == 2
    assert rounds[1]["target_dimensions"] == ["d_disclosure"]
    assert "cninfo.com.cn" in rounds[1]["include_domains"]
    assert any("年报" in phrase or "cninfo" in phrase for phrase in rounds[1]["search_phrases"])
    assert result["planner_metadata"]["search_round_rewrite_mode"] == (
        "semantic_planner_plus_deterministic_diversification_v1"
    )
    assert result["planner_metadata"]["search_round_review"]


def test_plan_task_provider_backed_prioritizes_local_round_for_location_sensitive_query(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_build_semantic_plan(**kwargs):
        captured.update(kwargs)
        return SemanticPlanResult(
            payload=kwargs["fallback_payload"],
            metadata={
                "planner_mode": "deterministic_fallback",
                "planner_provider": "deterministic",
                "planner_model": "offline_rules_v1",
                "deterministic_fallback": True,
                "reason": "test_capture",
            },
        )

    monkeypatch.setattr(real_nodes, "build_semantic_plan", _fake_build_semantic_plan)

    result = real_nodes.plan_task_provider_backed(
        {
            "query": "2025年合肥低空经济地方政策项目公示官方来源",
            "max_rounds": 2,
            "planner_replan_request": {
                "reason": "chief_gate_add_evidence",
                "policy_term_hints": ["合肥 低空经济 工作方案"],
                "execution_term_hints": ["合肥 低空经济 项目公示"],
            },
        }
    )

    fallback_payload = captured["fallback_payload"]
    plan = fallback_payload["plan"]
    rounds = plan["search_rounds"]
    dimensions = {item["dimension_id"]: item for item in plan["research_dimensions"]}
    dimension_plan = {item["dimension_id"]: item for item in plan["dimension_plan"]}

    assert result["query_requirements"]["target_location"] == "合肥"
    assert result["planner_metadata"]["summary_memory_used"] is False
    assert "d_local_rollout" in dimensions
    assert "d_local_rollout" in dimension_plan
    assert dimension_plan["d_local_rollout"]["dimension_type"] == "local_rollout"
    assert len(rounds) == 2
    assert "d_local_rollout" in rounds[1]["target_dimensions"]
    assert rounds[1]["include_domains"] == ["gov.cn"]
    assert any("合肥" in phrase for phrase in rounds[1]["search_phrases"])
    assert result["planner_metadata"]["search_round_review"]


def test_plan_task_provider_backed_rewrites_shallow_suffix_queries(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_build_semantic_plan(**kwargs):
        captured.update(kwargs)
        return SemanticPlanResult(
            payload=kwargs["fallback_payload"],
            metadata={
                "planner_mode": "deterministic_fallback",
                "planner_provider": "deterministic",
                "planner_model": "offline_rules_v1",
                "deterministic_fallback": True,
                "reason": "test_capture",
            },
        )

    monkeypatch.setattr(real_nodes, "build_semantic_plan", _fake_build_semantic_plan)

    result = real_nodes.plan_task_provider_backed(
        {
            "query": "2025年合肥低空经济上市公司年报披露与地方政策项目公示官方来源",
            "max_rounds": 2,
        }
    )

    rounds = result["plan"]["search_rounds"]
    assert captured["query"] == "2025年合肥低空经济上市公司年报披露与地方政策项目公示官方来源"
    assert len(rounds[0]["search_phrases"]) >= 3
    assert rounds[0]["search_phrases"][0] != (
        "2025年合肥低空经济上市公司年报披露与地方政策项目公示官方来源"
    )
    assert any(
        phrase.endswith("工作方案") or phrase.endswith("项目公示")
        or "cninfo" in phrase
        for phrase in rounds[0]["search_phrases"]
    )
    assert result["planner_metadata"]["search_round_rewrite_mode"] == (
        "semantic_planner_plus_deterministic_diversification_v1"
    )


def test_plan_task_provider_backed_forces_disclosure_and_local_dimensions_from_query(
    monkeypatch,
) -> None:
    def _fake_build_semantic_plan(**kwargs):
        fallback_payload = kwargs["fallback_payload"]
        payload = {
            **fallback_payload,
            "query_requirements": {
                "needs_company_disclosure": False,
                "target_location": None,
                "is_location_sensitive": False,
            },
            "plan": {
                **fallback_payload["plan"],
                "dimension_plan": [
                    item
                    for item in fallback_payload["plan"]["dimension_plan"]
                    if item["dimension_type"] in {"policy", "statistics"}
                ],
                "research_dimensions": [
                    item
                    for item in fallback_payload["plan"]["research_dimensions"]
                    if item["dimension_id"] in {"d_policy", "d_statistics"}
                ],
                "search_rounds": [
                    {
                        "round_number": 1,
                        "objective": "collect national policy",
                        "search_phrases": [
                            kwargs["query"],
                            f"{kwargs['query']} 通知",
                        ],
                        "include_domains": ["gov.cn"],
                        "target_dimensions": ["d_policy"],
                        "expected_source_tier": "A",
                    },
                    {
                        "round_number": 2,
                        "objective": "collect statistics",
                        "search_phrases": [
                            f"{kwargs['query']} 统计公报",
                        ],
                        "include_domains": ["stats.gov.cn"],
                        "target_dimensions": ["d_statistics"],
                        "expected_source_tier": "B",
                    },
                ],
            },
        }
        return SemanticPlanResult(
            payload=payload,
            metadata={
                "planner_mode": "semantic_provider",
                "planner_provider": "deepseek",
                "planner_model": "deepseek-chat",
                "deterministic_fallback": False,
                "reason": "test_force_query_coverage",
            },
        )

    monkeypatch.setattr(real_nodes, "build_semantic_plan", _fake_build_semantic_plan)

    result = real_nodes.plan_task_provider_backed(
        {
            "query": "2025年合肥低空经济上市公司年报披露与地方政策项目公示官方来源",
            "max_rounds": 2,
        }
    )

    rounds = result["plan"]["search_rounds"]
    dimension_types = {
        item["dimension_type"] for item in result["plan"]["dimension_plan"]
    }

    assert result["query_requirements"]["needs_company_disclosure"] is True
    assert result["query_requirements"]["is_location_sensitive"] is True
    dimension_ids = {item["dimension_id"] for item in result["plan"]["dimension_plan"]}
    assert "d_company_fundamentals" in dimension_ids
    assert "d_regional_benchmark" in dimension_ids
    assert {"company_fundamentals", "regional_benchmark"} <= dimension_types
    assert any("cninfo.com.cn" in round_plan["include_domains"] for round_plan in rounds)
    assert any("d_company_fundamentals" in round_plan["target_dimensions"] for round_plan in rounds)
    assert any("d_regional_benchmark" in round_plan["target_dimensions"] for round_plan in rounds)


def test_plan_task_provider_backed_injects_spec_driven_first_pass_rounds(
    monkeypatch,
) -> None:
    def _fake_build_semantic_plan(**kwargs):
        fallback_payload = kwargs["fallback_payload"]
        payload = {
            **fallback_payload,
            "plan": {
                **fallback_payload["plan"],
                "dimension_plan": [
                    {
                        "dimension_id": "d_policy",
                        "dimension_type": "policy",
                        "research_question": "What is the policy basis?",
                        "why_it_matters": "Baseline policy framing.",
                        "coverage_required": "Find official policy framing.",
                        "expected_section_heading": "Policy Basis",
                        "source_priority": "official",
                        "source_families": ["official_policy"],
                        "caliber_terms": [],
                    },
                    {
                        "dimension_id": "d_execution",
                        "dimension_type": "execution",
                        "research_question": "Are there landed projects?",
                        "why_it_matters": "Project evidence proves rollout.",
                        "coverage_required": "Find tender or project evidence.",
                        "expected_section_heading": "Project Rollout",
                        "source_priority": "project",
                        "source_families": ["public_resource_transaction"],
                        "caliber_terms": [],
                    },
                    {
                        "dimension_id": "d_disclosure",
                        "dimension_type": "disclosure",
                        "research_question": "Do companies disclose progress?",
                        "why_it_matters": "Disclosure verifies enterprise signals.",
                        "coverage_required": "Find listed-company disclosures.",
                        "expected_section_heading": "Company Disclosure",
                        "source_priority": "disclosure",
                        "source_families": ["company_disclosure"],
                        "caliber_terms": [],
                    },
                    {
                        "dimension_id": "d_statistics",
                        "dimension_type": "statistics",
                        "research_question": "What data confirms the trend?",
                        "why_it_matters": "Statistics corroborate scale.",
                        "coverage_required": "Find official data releases.",
                        "expected_section_heading": "Statistics",
                        "source_priority": "data",
                        "source_families": ["statistics_or_data_release"],
                        "caliber_terms": [],
                    },
                ],
                "search_rounds": [
                    {
                        "round_number": 1,
                        "objective": "collect baseline policy",
                        "search_phrases": [kwargs["query"]],
                        "include_domains": ["gov.cn"],
                        "target_dimensions": ["d_policy"],
                        "expected_source_tier": "A",
                    }
                ],
            },
        }
        return SemanticPlanResult(
            payload=payload,
            metadata={
                "planner_mode": "semantic_provider",
                "planner_provider": "deepseek",
                "planner_model": "deepseek-chat",
                "deterministic_fallback": False,
                "reason": "test_spec_first_pass",
            },
        )

    monkeypatch.setattr(real_nodes, "build_semantic_plan", _fake_build_semantic_plan)

    result = real_nodes.plan_task_provider_backed(
        {
            "query": "Hefei low altitude economy policy projects and disclosures",
            "max_rounds": 1,
        }
    )

    rounds = result["plan"]["search_rounds"]
    spec_rounds = [
        round_plan
        for round_plan in rounds
        if round_plan.get("_round_origin") == "spec_driven_first_pass"
    ]
    families = {round_plan.get("_target_source_family") for round_plan in spec_rounds}

    assert result["spec_first_pass_min_search_rounds"] >= 4
    assert result["planner_metadata"]["spec_driven_first_pass"]["added_rounds"] == 3
    assert "tender_procurement" in families
    assert "company_disclosure" in families
    # The 3rd spec round may be exchange_disclosure or official_statistics
    # depending on the priority cap + synthetic company_fundamentals injection.
    assert "exchange_disclosure" in families or "official_statistics" in families
    assert all(round_plan["include_domains"] == [] for round_plan in spec_rounds)
    # 收口（_enrich_round_phrases）会为 spec round 追加维度定向短语，
    # 数量可超 2 但必须是定向短语而非整句 query 变体（含维度术语）。
    for round_plan in spec_rounds:
        family = round_plan["_target_source_family"]
        assert len(round_plan["search_phrases"]) >= 1
        if family == "company_disclosure":
            assert any("公告" in p or "披露" in p for p in round_plan["search_phrases"])
        elif family == "official_statistics":
            assert any("统计" in p or "公报" in p for p in round_plan["search_phrases"])


def test_plan_task_provider_backed_keeps_no_spec_fallback(monkeypatch) -> None:
    def _fake_build_semantic_plan(**kwargs):
        fallback_payload = kwargs["fallback_payload"]
        payload = {
            **fallback_payload,
            "plan": {
                **fallback_payload["plan"],
                "dimension_plan": [],
                "search_rounds": [
                    {
                        "round_number": 1,
                        "objective": "collect baseline policy",
                        "search_phrases": [kwargs["query"]],
                        "include_domains": ["gov.cn"],
                        "target_dimensions": ["d_policy"],
                        "expected_source_tier": "A",
                    }
                ],
            },
        }
        return SemanticPlanResult(
            payload=payload,
            metadata={
                "planner_mode": "semantic_provider",
                "planner_provider": "deepseek",
                "planner_model": "deepseek-chat",
                "deterministic_fallback": False,
                "reason": "test_no_spec",
            },
        )

    monkeypatch.setattr(real_nodes, "build_semantic_plan", _fake_build_semantic_plan)

    result = real_nodes.plan_task_provider_backed(
        {"query": "low altitude economy policy", "max_rounds": 1}
    )

    assert "spec_first_pass_min_search_rounds" not in result
    assert not any(
        round_plan.get("_round_origin") == "spec_driven_first_pass"
        for round_plan in result["plan"]["search_rounds"]
    )


def test_collect_sources_provider_backed_exposes_spec_round_diagnostics() -> None:
    real_nodes.set_search_provider_override(_FakeSearchProvider())
    try:
        result = real_nodes.collect_sources_provider_backed(
            {
                "query": "low altitude economy policy",
                "max_rounds": 1,
                "spec_first_pass_min_search_rounds": 2,
                "query_requirements": {},
                "plan": {
                    "search_rounds": [
                        {
                            "round_number": 1,
                            "objective": "spec-driven first-pass retrieval: company_disclosure",
                            "search_phrases": ["low altitude economy listed company announcement"],
                            "include_domains": [],
                            "target_dimensions": ["d_disclosure"],
                            "expected_source_tier": "B",
                            "_round_origin": "spec_driven_first_pass",
                            "_target_source_family": "company_disclosure",
                            "_evidence_sections": ["Company Disclosure"],
                        },
                    ]
                },
                "sources": [],
                "search_events": [],
            }
        )
    finally:
        real_nodes.set_search_provider_override(None)

    spec_event = next(
        event
        for event in result["search_events"]
        if event["round_number"] == 1
    )
    assert spec_event["round_origin"] == "spec_driven_first_pass"
    assert spec_event["target_source_family"] == "company_disclosure"
    assert spec_event["evidence_sections"] == ["Company Disclosure"]
    assert spec_event["target_family_mismatch_count"] == 1
    spec_source = next(
        source
        for source in result["sources"]
        if source.get("round_origin") == "spec_driven_first_pass"
        and source.get("target_source_family") == "company_disclosure"
    )
    assert spec_source["source_family"] == "policy_document"
    assert spec_source["target_source_family_match"] is False
    assert spec_source["target_source_family_mismatch_reason"]


def test_plan_task_provider_backed_exposes_summary_memory_usage(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_build_semantic_plan(**kwargs):
        captured.update(kwargs)
        return SemanticPlanResult(
            payload=kwargs["fallback_payload"],
            metadata={
                "planner_mode": "deterministic_fallback",
                "planner_provider": "deterministic",
                "planner_model": "offline_rules_v1",
                "deterministic_fallback": True,
                "reason": "test_capture",
            },
        )

    monkeypatch.setattr(real_nodes, "build_semantic_plan", _fake_build_semantic_plan)

    result = real_nodes.plan_task_provider_backed(
        {
            "query": "2025年低空经济政策项目官方来源",
            "max_rounds": 1,
            "summary_memory": {
                "recurring_themes": ["政策先行"],
                "preferred_dimensions": ["policy", "statistics"],
            },
        }
    )

    assert captured["summary_memory"] == {
        "recurring_themes": ["政策先行"],
        "preferred_dimensions": ["policy", "statistics"],
    }
    assert result["planner_metadata"]["summary_memory_used"] is True
    assert result["planner_metadata"]["summary_memory_keys"] == [
        "preferred_dimensions",
        "recurring_themes",
    ]


def test_shadow_plan_task_emits_dimension_plan() -> None:
    payload = harness_nodes.plan_task(
        {
            "query": "low altitude economy procurement award notice",
            "max_rounds": 2,
            "strategy": "shadow_langgraph_v1",
        }
    )

    assert payload["plan"]["dimension_plan"]
    assert {item["dimension_type"] for item in payload["plan"]["dimension_plan"]} >= {
        "policy_regulation",
        "project_execution",
    }


def test_build_graph_retrieval_artifacts_uses_dimension_and_obligation_focus() -> None:
    payload = harness_nodes.parse_sources(
        {
            "query": "2025年合肥低空经济中标公告官方来源",
            "strategy": "shadow_langgraph_v1",
            "sources": [
                {
                    "source_id": "src_policy_local",
                    "url": "https://www.hefei.gov.cn/policy/low-altitude.html",
                    "title": "合肥低空经济工作方案",
                    "source_family": "official_policy",
                    "raw_text": "合肥发布低空经济工作方案，推动项目公示与场景建设。",
                },
                {
                    "source_id": "src_award",
                    "url": "https://www.ggzy.gov.cn/award/low-altitude.html",
                    "title": "低空经济示范项目中标公告",
                    "source_family": "public_resource_transaction",
                    "raw_text": "公共资源交易中心发布低空经济示范项目中标公告，披露中标结果。",
                },
            ],
            "plan": {
                "dimension_plan": [
                    {
                        "dimension_id": "d_local_rollout",
                        "dimension_type": "local_rollout",
                        "research_question": "What rollout evidence exists in 合肥?",
                        "expected_section_heading": "地方落地与区域进展",
                        "source_families": [
                            "official_policy",
                            "public_resource_transaction",
                        ],
                        "caliber_terms": ["合肥", "项目公示", "中标公告"],
                    },
                    {
                        "dimension_id": "d_execution",
                        "dimension_type": "execution",
                        "research_question": "What award notice shows execution?",
                        "expected_section_heading": "项目与执行证据",
                        "source_families": ["public_resource_transaction"],
                        "caliber_terms": ["中标公告", "交易中心"],
                    },
                ],
                "source_obligations": [
                    {
                        "obligation_id": "obl_procurement_award",
                        "source_family": "public_resource_transaction",
                        "required_for": "procurement or award evidence",
                        "min_required_evidence": 1,
                    }
                ],
            },
            "query_requirements": {
                "target_location": "合肥",
                "is_location_sensitive": True,
            },
        }
    )

    retrieval_pack = payload["retrieval_pack"]
    assert retrieval_pack["retrieval_mode"] == "graph_runtime_rank_v1"
    assert retrieval_pack["dimension_focus"]
    assert retrieval_pack["obligation_focus"]
    assert retrieval_pack["items"]
    top_item = retrieval_pack["items"][0]
    # New ranking: dedup -> BM25+vector(RRF) -> chunk -> rerank.
    assert "rerank_score" in top_item["score_breakdown"]
    assert "coarse_rrf" in top_item["score_breakdown"]
    assert top_item["chunk_metadata"].get("graph_source_id")


def test_parse_sources_persists_graph_runtime_chunks_for_scoped_retrieval(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_url = _setup_graph_db(monkeypatch, tmp_path)
    engine = create_engine(db_url)

    with Session(engine) as session:
        payload = harness_nodes.parse_sources(
            {
                "run_id": 99,
                "query": "合肥 低空经济 中标公告",
                "strategy": "shadow_langgraph_v1",
                "sources": [
                    {
                        "source_id": "src_policy_local",
                        "url": "https://www.hefei.gov.cn/policy/low-altitude.html",
                        "title": "合肥低空经济工作方案",
                        "source_family": "official_policy",
                        "raw_text": "合肥发布低空经济工作方案，推动项目公示与场景建设。",
                    },
                    {
                        "source_id": "src_award",
                        "url": "https://www.ggzy.gov.cn/award/low-altitude.html",
                        "title": "低空经济示范项目中标公告",
                        "source_family": "public_resource_transaction",
                        "raw_text": "公共资源交易中心发布低空经济示范项目中标公告，披露中标结果。",
                    },
                ],
                "plan": {
                    "dimension_plan": [
                        {
                            "dimension_id": "d_local_rollout",
                            "dimension_type": "local_rollout",
                            "research_question": "What rollout evidence exists in 合肥?",
                            "expected_section_heading": "地方落地与区域进展",
                            "source_families": [
                                "official_policy",
                                "public_resource_transaction",
                            ],
                            "caliber_terms": ["合肥", "项目公示", "中标公告"],
                        }
                    ],
                    "source_obligations": [
                        {
                            "obligation_id": "obl_procurement_award",
                            "source_family": "public_resource_transaction",
                            "required_for": "procurement or award evidence",
                            "min_required_evidence": 1,
                        }
                    ],
                },
                "query_requirements": {
                    "target_location": "合肥",
                    "is_location_sensitive": True,
                },
            },
            tool_session=SimpleNamespace(db_session=session),
        )

        persisted_chunks = session.scalars(select(DocumentChunk)).all()

    retrieval_pack = payload["retrieval_pack"]
    assert persisted_chunks
    assert all(chunk.embedding_model == "deterministic_hash_embed_v1" for chunk in persisted_chunks)
    assert all(chunk.embedding_dimension == 16 for chunk in persisted_chunks)
    assert all(chunk.embedding_json for chunk in persisted_chunks)
    # ChunkDraft 重构后无 parent/child 层级：chunk 平铺，索引文本=chunk 文本。
    assert len(persisted_chunks) == 2
    assert {chunk.document_id for chunk in persisted_chunks} == {1, 2}
    assert all(chunk.text for chunk in persisted_chunks)
    assert retrieval_pack["adapter_status"] == "persistent_graph_documents"
    assert retrieval_pack["persisted_document_ids"]
    assert retrieval_pack["retrieval_mode"] == "graph_runtime_rank_v1"
    assert retrieval_pack["backend_retrieval_mode"].startswith(
        "graph_persistent_retrieval_adapter_v1"
    )
    assert retrieval_pack["audit"]["ranked_source_count"] >= 2
    assert retrieval_pack["audit"]["persisted_document_ids"]
    assert retrieval_pack["items"]
    top_item = retrieval_pack["items"][0]
    assert top_item["chunk_metadata"]["graph_source_id"]
    assert top_item["chunk_metadata"]["source_family"]
    assert top_item["score_breakdown"]["rerank_score"] is not None
    assert len(retrieval_pack["items"]) >= 1



def test_build_evidence_provider_backed_prefers_llm_synthesis(monkeypatch) -> None:
    monkeypatch.setattr(
        real_nodes,
        "call_tooling_json",
        lambda **kwargs: type(
            "FakeResult",
            (),
            {
                "payload": {
                    "evidence_items": [
                        {
                            "evidence_id": "ev_merged_policy",
                            "summary": (
                                "合并政策正文与实施段落后，可以确认该地方政策"
                                "已经形成正式工作方案。"
                            ),
                            "support_type": "background_support",
                            "support_strength": 0.79,
                            "specificity": "policy_statement",
                            "limitations": ["尚未直接证明后续项目全部落地。"],
                            "source_ids": ["src_policy_local"],
                            "chunk_ids": [101, 102],
                        }
                    ]
                },
                "metadata": {
                    "llm_mode": "live_provider",
                    "llm_reason": "provider_response_accepted",
                },
            },
        )(),
    )

    result = real_nodes.build_evidence_provider_backed(
        {
            "query": "2025年合肥低空经济政策与项目进展",
            "plan": {"dimension_plan": [{"dimension_type": "policy"}]},
            "query_requirements": {"target_location": "合肥", "is_location_sensitive": True},
            "sources": [
                {
                    "source_id": "src_policy_local",
                    "url": "https://www.hefei.gov.cn/policy/low-altitude.html",
                    "title": "合肥低空经济工作方案",
                    "source_family": "official_policy",
                    "clean_text": "合肥发布低空经济工作方案，并明确推进一批项目。",
                    "source_quality_v2": {
                        "source_role": "official_policy_original",
                        "usage_role": "primary_support",
                        "credibility_score": 0.9,
                    },
                }
            ],
            "retrieval_pack": {
                "items": [
                    {
                        "chunk_id": 101,
                        "source_id": "src_policy_local",
                        "chunk_text": "合肥发布低空经济工作方案。",
                    },
                    {
                        "chunk_id": 102,
                        "source_id": "src_policy_local",
                        "chunk_text": "方案明确推进一批项目。",
                    },
                ]
            },
        }
    )

    assert result["evidence"][0]["evidence_id"] == "ev_merged_policy"
    assert result["evidence"][0]["chunk_ids"] == [101, 102]
    assert result["evidence"][0]["source_ids"] == ["src_policy_local"]
    assert result["contract_meta"]["build_evidence"]["used_fallback"] is False


def test_enrich_evidence_semantics_attaches_evidence_quality_v2() -> None:
    enriched = real_nodes._enrich_evidence_semantics(
        evidence_items=[
            {
                "evidence_id": "ev_policy",
                "source_id": "src_policy",
                "source_ids": ["src_policy"],
                "summary": "Hefei issued a low-altitude economy implementation plan.",
                "support_type": "direct_support",
                "specificity": "policy_statement",
                "limitations": [],
            },
            {
                "evidence_id": "ev_news",
                "source_id": "src_news",
                "source_ids": ["src_news"],
                "summary": "An official news page described low-altitude economy signals.",
                "support_type": "direct_support",
                "specificity": "policy_statement",
                "limitations": [],
            },
        ],
        sources=[
            {
                "source_id": "src_policy",
                "title": "Hefei low-altitude economy implementation plan",
                "url": "https://www.hefei.gov.cn/policy/low-altitude.html",
                "source_family": "official_policy",
                "source_quality_v2": {
                    "tier": "A",
                    "source_role": "official_policy_original",
                    "credibility_score": 0.9,
                    "credibility_label": "high",
                    "usage_role": "primary_evidence_candidate",
                    "not_sufficient_for": [],
                    "query_relevance": {"score": 0.9},
                },
            },
            {
                "source_id": "src_news",
                "title": "Official news on low-altitude economy",
                "url": "https://www.hefei.gov.cn/news/low-altitude.html",
                "source_family": "official_policy",
                "source_quality_v2": {
                    "tier": "B",
                    "source_role": "official_news_or_interpretation",
                    "credibility_score": 0.68,
                    "credibility_label": "medium",
                    "usage_role": "context_only",
                    "not_sufficient_for": ["formal policy original"],
                    "query_relevance": {"score": 0.62},
                },
            },
        ],
        query="Hefei low-altitude economy policy",
    )

    policy = next(item for item in enriched if item["evidence_id"] == "ev_policy")
    news = next(item for item in enriched if item["evidence_id"] == "ev_news")

    assert policy["evidence_type"] == "policy_original"
    assert policy["proof_strength"] in {"strong", "medium"}
    assert policy["evidence_quality_v2"]["inherited_source_quality"][
        "source_credibility_score"
    ] == 0.9

    assert news["evidence_type"] == "policy_signal"
    assert news["proof_strength"] == "context_only"
    assert "formal_policy_original_requirement" in news["evidence_quality_v2"][
        "not_sufficient_for"
    ]


def test_claim_support_eligibility_rejects_policy_signal_for_policy_original() -> None:
    decision = real_nodes._evaluate_claim_support_eligibility(
        claim={
            "claim_id": "claim_policy",
            "required_source_family": "official_policy",
            "support_requirement": "policy_statement",
        },
        evidence={
            "evidence_id": "ev_news",
            "evidence_type": "policy_signal",
            "proof_strength": "context_only",
            "evidence_quality_v2": {
                "evidence_type": "policy_signal",
                "proof_strength": "context_only",
                "citation_integrity": 0.85,
                "quality_score": 0.58,
            },
        },
        source={
            "source_id": "src_news",
            "source_family": "official_policy",
            "source_quality_v2": {
                "source_role": "official_news_or_interpretation",
                "usage_role": "context_only",
                "credibility_score": 0.68,
            },
        },
    )

    assert decision["eligible"] is False
    assert decision["reason_code"] == "context_only"
    assert decision["evidence_type"] == "policy_signal"


# ── Evidence-view gate fixtures ─────────────────────────────────────────────
# chief_gate 已改为基于 plan.dimension_plan 的 evidence 覆盖度判定（_dimension_coverage_report）：
# 每维度按 evidence.source_family ∈ dim.required_source_families 或
# evidence.evidence_type 命中维度主证据通道 匹配，统计 covered/evidence_count/min_evidence。
# 旧 claim + claim_support_matrix fixture 已弃用，以下 helper 专供 evidence 视角测试。


def _gate_evidence(
    evidence_id: str,
    source_id: str,
    *,
    source_family: str,
    evidence_type: str,
    proof_strength: str = "strong",
) -> dict:
    """Build an evidence dict consumed by the dimension-coverage report."""
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "source_family": source_family,
        "evidence_type": evidence_type,
        "proof_strength": proof_strength,
    }


def _gate_source(source_id: str, *, source_family: str) -> dict:
    return {"source_id": source_id, "source_family": source_family}


def _gate_dimension(
    dimension_id: str,
    *,
    dimension_type: str,
    expected_section_heading: str,
    source_families: list[str],
) -> dict:
    """Build a dimension_plan entry. Both keys are set because the coverage report
    reads `required_source_families` while min_evidence is derived (via
    build_evidence_requirement_spec) from `source_families`."""
    return {
        "dimension_id": dimension_id,
        "dimension_type": dimension_type,
        "expected_section_heading": expected_section_heading,
        "source_families": source_families,
        "required_source_families": source_families,
    }


def _gate_state(
    *,
    plan: list[dict],
    evidence: list[dict],
    sources: list[dict],
    review_issues: list[dict] | None = None,
    loop_count: int = 0,
    max_loop_count: int = 2,
    query_requirements: dict | None = None,
    editor2_route_recommendation: dict | None = None,
    verifier_route_recommendation: dict | None = None,
    query: str = "2025年低空经济政策与地方项目",
) -> dict:
    return {
        "query": query,
        "plan": {"dimension_plan": plan},
        "evidence": evidence,
        "sources": sources,
        "review_issues": review_issues or [],
        "loop_count": loop_count,
        "max_loop_count": max_loop_count,
        "query_requirements": query_requirements or {},
        "search_events": [],
        "editor2_route_recommendation": editor2_route_recommendation or {},
        "verifier_route_recommendation": verifier_route_recommendation or {},
    }


def test_chief_gate_evidence_coverage_rejects_ineligible_proof() -> None:
    """Evidence 视角：context_only/ineligible 证据不构成维度覆盖（unsupported 语义）。

    原 verify_claims 的 unsupported 判定已由维度 evidence 覆盖 gate 取代：某维度只有
    低质（context_only）证据时视为未覆盖 → 需补证，而非直接放行。
    """
    result = real_nodes.chief_gate_provider_backed(
        _gate_state(
            plan=[
                _gate_dimension(
                    "d_local_rollout",
                    dimension_type="local_rollout",
                    expected_section_heading="项目落地",
                    source_families=["tender_procurement"],
                ),
            ],
            evidence=[
                _gate_evidence(
                    "ev_local",
                    "src_local",
                    source_family="tender_procurement",
                    evidence_type="procurement_award",
                    proof_strength="context_only",
                ),
            ],
            sources=[
                _gate_source("src_local", source_family="tender_procurement"),
            ],
        )
    )

    coverage = result["dimension_coverage"]["d_local_rollout"]
    assert coverage["covered"] is False
    assert coverage["evidence_count"] == 0
    assert result["decision"] == "ADD_EVIDENCE"
    assert result["required_actions"] == [
        {"action_type": "ADD_EVIDENCE", "target": "d_local_rollout"}
    ]


def test_build_claims_provider_backed_prefers_llm_synthesis(monkeypatch) -> None:
    monkeypatch.setattr(
        real_nodes,
        "call_tooling_json",
        lambda **kwargs: type(
            "FakeResult",
            (),
            {
                "payload": {
                    "claims": [
                        {
                            "claim_id": "claim_policy_basis",
                            "text": "合肥低空经济已经形成正式政策工作方案。",
                            "evidence_ids": ["ev_policy_local"],
                            "supported": True,
                            "required_source_family": "official_policy",
                            "support_requirement": "policy_statement",
                            "claim_family": "policy_basis",
                        },
                        {
                            "claim_id": "claim_data_corroboration",
                            "text": "统计口径可以用来验证项目规模与进展趋势。",
                            "evidence_ids": ["ev_stats"],
                            "supported": True,
                            "required_source_family": "statistics_or_data_release",
                            "support_requirement": "statistics_or_data_release",
                            "claim_family": "statistics_corroboration",
                        },
                    ]
                },
                "metadata": {
                    "llm_mode": "live_provider",
                    "llm_reason": "provider_response_accepted",
                },
            },
        )(),
    )

    result = real_nodes.build_claims_provider_backed(
        {
            "query": "2025年合肥低空经济政策与项目进展",
            "query_requirements": {"target_location": "合肥", "is_location_sensitive": True},
            "plan": {
                "dimension_plan": [
                    {"dimension_type": "policy"},
                    {"dimension_type": "statistics"},
                ],
                "source_obligations": [
                    {"obligation_id": "obl_policy_primary", "source_family": "official_policy"},
                    {
                        "obligation_id": "obl_stats_primary",
                        "source_family": "statistics_or_data_release",
                    },
                ],
            },
            "sources": [
                {"source_id": "src_policy_local", "source_family": "official_policy"},
                {"source_id": "src_stats", "source_family": "statistics_or_data_release"},
            ],
            "evidence": [
                {
                    "evidence_id": "ev_policy_local",
                    "source_id": "src_policy_local",
                    "source_ids": ["src_policy_local"],
                    "specificity": "policy_statement",
                    "support_type": "background_support",
                    "support_strength": 0.74,
                },
                {
                    "evidence_id": "ev_stats",
                    "source_id": "src_stats",
                    "source_ids": ["src_stats"],
                    "specificity": "statistics_or_data_release",
                    "support_type": "direct_support",
                    "support_strength": 0.82,
                },
            ],
        }
    )

    assert {item["claim_id"] for item in result["claims"]} == {
        "claim_policy_basis",
        "claim_data_corroboration",
    }
    assert result["contract_meta"]["build_claims"]["used_fallback"] is False


def test_editor1_draft_provider_backed_outputs_markdown_oriented_sections(monkeypatch) -> None:
    # Isolate from live providers (review 2026-08-03): the editor1 writer must
    # not hit live DeepSeek in a unit test. Patch the module-level override that
    # _resolve_editor1_call_tooling_json honors, returning a fixed English-title
    # report so the assertion is deterministic and offline.
    def _fake_call_tooling_json(**kwargs):
        return StructuredLlmCallResult(
            payload={
                "report_markdown": (
                    "# low altitude economy policy and local rollout\n\n"
                    "## 执行摘要\n\n"
                    "本报告基于现有证据，对低空经济政策与地方落地情况进行初步分析。"
                    "核心发现是地方落地具有官方政策依据。\n\n"
                    "## 方法与口径\n\n"
                    "本报告主要依赖官方政策文件与地方公开信息，对证据的局限性逐条标注。\n\n"
                    "## 政策主线分析\n\n"
                    "地方政策为产业发展提供了制度基础，具体落地仍依赖后续项目执行。\n\n"
                    "## 地方政策与项目对比\n\n"
                    "不同地区的政策工具与落地阶段存在差异，需结合具体项目验证。\n\n"
                    "## 结论与展望\n\n"
                    "总体来看，该产业正处于政策驱动向项目落地过渡的阶段。\n\n"
                    "## 风险与不确定性\n\n"
                    "政策执行与项目落地仍存在不确定性，需持续跟踪。\n\n"
                    "## 来源说明\n\n"
                    "本报告引用的证据均来自公开渠道。"
                )
            },
            raw_text="ok",
            metadata={},
        )

    monkeypatch.setattr(real_nodes, "call_tooling_json", _fake_call_tooling_json)

    result = real_nodes.editor1_draft_provider_backed(
        {
            "query": "low altitude economy policy and local rollout",
            "claims": [
                {
                    "claim_id": "claim_local_rollout",
                    "text": "Local rollout has official policy grounding.",
                    "supported": True,
                    "claim_family": "local_rollout",
                    "evidence_ids": ["ev_local_policy"],
                    "required_source_family": "official_policy",
                    "support_requirement": "policy_statement",
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_local_policy",
                    "source_id": "src_local_policy",
                    "source_ids": ["src_local_policy", "src_city_notice"],
                    "chunk_ids": [101, 102],
                    "summary": "Local official notice and city notice support the rollout.",
                    "limitations": [],
                    "support_strength": 0.84,
                    "specificity": "policy_statement",
                }
            ],
            "sources": [],
        }
    )

    draft = result["drafts"][-1]
    section = draft["sections"][0]

    assert draft["report_markdown"].startswith("# low altitude economy")
    assert draft["report_markdown"].count("\n## ") >= 3
    assert section["section_role"] == "local_implementation"


def test_editor1_draft_provider_backed_tracks_actual_prompt_budget_and_context_summary(
    monkeypatch,
) -> None:
    captured: dict[str, str] = {}

    def _fake_call_tooling_json(**kwargs):
        captured["user_prompt"] = kwargs["user_prompt"]
        return StructuredLlmCallResult(
            payload={
                "report_markdown": (
                    "# Budgeted Draft\n\n"
                    "## ????\n\n???????????????\n\n"
                    "## ?????\n\n??????????\n\n"
                    "## ???????\n\n???????"
                )
            },
            raw_text="ok",
            metadata={},
        )

    monkeypatch.setattr(
        "packages.research_harness.tooling.llm_agents.call_tooling_json",
        _fake_call_tooling_json,
    )

    state = {
        "query": "budgeted editor1 prompt",
        "claims": [
            {
                "claim_id": "claim_policy",
                "text": "Policy exists.",
                "supported": True,
                "claim_family": "policy_basis",
                "evidence_ids": ["ev_1", "ev_2", "ev_3"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "ev_1",
                "source_id": "src_a",
                "summary": "High priority policy evidence." * 80,
                "support_strength": 0.95,
                "support_type": "direct_support",
                "source_family": "official_policy",
                "region": "Hefei",
            },
            {
                "evidence_id": "ev_2",
                "source_id": "src_a",
                "summary": "High priority policy evidence." * 80,
                "support_strength": 0.95,
                "support_type": "direct_support",
                "source_family": "official_policy",
                "region": "Hefei",
            },
            {
                "evidence_id": "ev_3",
                "source_id": "src_b",
                "summary": "Secondary disclosure evidence." * 80,
                "support_strength": 0.40,
                "support_type": "background_support",
                "source_family": "company_disclosure",
                "region": "Hefei",
            },
        ],
        "sources": [
            {
                "source_id": "src_a",
                "title": "Policy A",
                "source_family": "official_policy",
                "url": "https://example.com/policy-a",
                "raw_text": "A" * 2400,
                "clean_text": "A" * 2400,
            },
            {
                "source_id": "src_b",
                "title": "Disclosure B",
                "source_family": "company_disclosure",
                "url": "https://example.com/disclosure-b",
                "raw_text": "B" * 2400,
                "clean_text": "B" * 2400,
            },
        ],
    }

    result = real_nodes.editor1_draft_provider_backed(state)
    meta = result["contract_meta"]["editor1_draft"]
    pack = meta["actual_input_pack"]

    assert pack["prompt_budget_status"] == "within_budget"
    assert pack["prompt_pretrim_budget_status"] == "over_budget"
    assert pack["prompt_truncated"] is True
    assert "ev_2" in pack["prompt_dropped_ids"]
    assert pack["drop_reasons"]["ev_2"] == "duplicate_evidence"
    assert pack["prompt_estimated_tokens"] <= pack["prompt_budget_limit"]
    assert set(pack["selected_source_families"]) == {
        "company_disclosure",
        "official_policy",
    }
    assert pack["selected_regions"] == ["Hefei"]
    assert pack["included_claim_ids"] == ["claim_policy"]
    assert "ev_2" not in captured["user_prompt"]

    pack_state = {**state, **result}
    summary = build_context_pack_summary(
        node_name="editor1_draft",
        agent_name="editor1",
        state=pack_state,
        state_before=state,
        state_after=pack_state,
    )
    assert summary["prompt_estimated_tokens"] == pack["prompt_estimated_tokens"]
    assert summary["state_footprint_estimated_tokens"] > summary["prompt_estimated_tokens"]
    assert summary["budget_status"] == pack["prompt_budget_status"]
    assert "state_before_full" not in summary["io_snapshot"]
    assert "state_after_full" not in summary["io_snapshot"]
    assert len(json.dumps(summary["io_snapshot"], ensure_ascii=False)) < 10_000


def test_editor1_draft_provider_backed_retains_canonical_narrative_over_fallback(
    monkeypatch,
) -> None:
    def _fake_call_tooling_json(**kwargs):
        return StructuredLlmCallResult(
            payload={"report_markdown": "too short"},
            raw_text="bad",
            metadata={},
        )

    monkeypatch.setattr(
        "packages.research_harness.tooling.llm_agents.call_tooling_json",
        _fake_call_tooling_json,
    )

    prior_markdown = (
        "# Canonical Draft\n\n"
        "## Executive Summary\n\nBounded conclusion.\n\n"
        "## Method\n\nEvidence comparison.\n\n"
        "## Analysis\n\nImplementation varies.\n\n"
        "## Risks\n\nEvidence gaps remain.\n\n"
        "## Conclusion\n\nFurther verification is required."
    )
    state = {
        "query": "canonical draft retention",
        "drafts": [
            {
                "draft_id": "draft_good",
                "draft_version": 1,
                "report_markdown": prior_markdown,
                "sections": real_nodes._parse_markdown_sections(prior_markdown),
            }
        ],
        "claims": [
            {
                "claim_id": "claim_policy",
                "text": "Policy exists.",
                "supported": True,
                "claim_family": "policy_basis",
                "evidence_ids": ["ev_1"],
            }
        ],
        "evidence": [
            {"evidence_id": "ev_1", "source_id": "src_1", "summary": "Evidence summary."}
        ],
        "sources": [{"source_id": "src_1", "title": "Source 1"}],
    }

    result = real_nodes.editor1_draft_provider_backed(state)

    assert result["retained_previous_draft"] is True
    assert result["canonical_draft_id"] == "draft_good"
    assert result["report_markdown"] == prior_markdown
    assert result["contract_meta"]["editor1_draft"]["used_fallback"] is True
    assert result["contract_meta"]["editor1_draft"]["retained_previous_draft"] is True


def test_support_strength_avoids_flat_background_cap() -> None:
    strong_background = real_nodes._support_strength(
        {
            "credibility_score": 0.92,
            "query_relevance": {"score": 0.88},
            "freshness": {"score": 0.86, "label": "current"},
            "source_role": "official_policy_original",
            "usage_role": "primary_support",
        },
        support_type="background_support",
    )
    medium_background = real_nodes._support_strength(
        {
            "credibility_score": 0.84,
            "query_relevance": {"score": 0.73},
            "freshness": {"score": 0.52, "label": "recent"},
            "source_role": "official_notice_or_rule",
            "usage_role": "secondary_support",
        },
        support_type="background_support",
    )
    direct_support = real_nodes._support_strength(
        {
            "credibility_score": 0.88,
            "query_relevance": {"score": 0.82},
            "freshness": {"score": 0.80, "label": "current"},
            "source_role": "statistics_or_data_release",
            "usage_role": "primary_support",
        },
        support_type="direct_support",
    )

    assert strong_background > 0.68
    assert medium_background < strong_background
    assert direct_support > strong_background


def test_editor2_review_provider_backed_statistics_claim_suggests_data_queries() -> None:
    result = real_nodes.editor2_review_provider_backed(
        {
            "query": "2025年合肥低空经济地方政策项目公示官方来源",
            "claims": [
                {
                    "claim_id": "claim_statistics_corroboration",
                    "supported": False,
                    "required_source_family": "statistics_or_data_release",
                    "support_requirement": "statistics_or_data_release",
                    "claim_family": "statistics_corroboration",
                    "evidence_ids": [],
                }
            ],
            "evidence": [],
            "sources": [],
        }
    )

    issue = result["review_issues"][0]
    suggested = issue["suggested_search_queries"]

    assert issue["target_claim_id"] == "claim_statistics_corroboration"
    assert suggested
    assert any("统计" in item or "数据" in item for item in suggested)

def test_editor2_review_provider_backed_flags_section_role_mismatch() -> None:
    result = real_nodes.editor2_review_provider_backed(
        {
            "query": "low altitude economy local rollout",
            "claims": [
                {
                    "claim_id": "claim_local_rollout",
                    "text": "Local rollout evidence exists.",
                    "supported": True,
                    "required_source_family": "official_policy",
                    "support_requirement": "policy_statement",
                    "claim_family": "local_rollout",
                    "evidence_ids": ["ev_local"],
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_local",
                    "source_id": "src_local",
                    "source_ids": ["src_local", "src_local_2"],
                    "limitations": [],
                }
            ],
            "sources": [
                {"source_id": "src_local", "source_family": "official_policy"},
                {"source_id": "src_local_2", "source_family": "official_policy"},
            ],
            "drafts": [
                {
                    "draft_id": "draft_1",
                    "draft_version": 1,
                    "report_markdown": "# Draft",
                    "sections": [
                        {
                            "section_id": "sec_policy_basis",
                            "title": "Policy Basis",
                            "section_role": "policy_basis",
                            "argument_posture": "conditional",
                            "markdown_body": "Local rollout evidence exists.",
                            "paragraphs": [
                                {
                                    "paragraph_id": "p_local",
                                    "text": "Local rollout evidence exists.",
                                    "claim_ids": ["claim_local_rollout"],
                                    "evidence_ids": ["ev_local"],
                                    "confidence": "medium",
                                    "limitations": [],
                                    "argument_posture": "conditional",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )

    assert any(
        issue["issue_type"] == "section_role_mismatch"
        for issue in result["review_issues"]
    )


def test_editor2_review_provider_backed_prefers_llm_synthesis(monkeypatch) -> None:
    monkeypatch.setattr(
        real_nodes,
        "call_tooling_json",
        lambda **kwargs: StructuredLlmCallResult(
            payload={
                "issues": [
                    {
                        "issue_id": "issue_llm_section_gap",
                        "severity": "warning",
                        "issue_type": "draft_section_gap",
                        "target_claim_id": "claim_local_rollout",
                        "description": "LLM reviewer found a missing readable section.",
                        "required_fix": "Add a readable local rollout section in the report body.",
                        "suggested_search_queries": ["合肥 低空经济 项目公示"],
                    }
                ]
            },
            metadata={
                "llm_mode": "live_provider",
                "llm_reason": "provider_response_accepted",
                "llm_provider": "deepseek",
                "llm_model": "deepseek-chat",
            },
        ),
    )

    result = real_nodes.editor2_review_provider_backed(
        {
            "query": "2025年合肥低空经济地方项目进展",
            "plan": {
                "dimension_plan": [
                    {
                        "dimension_type": "地方维度",
                        "research_question": "合肥本地项目是否已有正式落地与公示证据",
                    }
                ]
            },
            "claims": [
                {
                    "claim_id": "claim_local_rollout",
                    "text": "合肥本地已有低空经济项目落地信号。",
                    "supported": True,
                    "required_source_family": "official_policy",
                    "support_requirement": "policy_statement",
                    "claim_family": "local_rollout",
                    "evidence_ids": ["ev_local"],
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_local",
                    "source_id": "src_local",
                    "source_ids": ["src_local", "src_local_2"],
                    "limitations": [],
                    "summary": "地方项目公示与地方政策通知形成初步支撑。",
                }
            ],
            "sources": [
                {"source_id": "src_local", "source_family": "official_policy"},
                {"source_id": "src_local_2", "source_family": "official_policy"},
            ],
            "claim_support_matrix": [
                {
                    "claim_id": "claim_local_rollout",
                    "required_source_family": "official_policy",
                    "family_matched": True,
                    "evidence_count": 1,
                    "source_count": 2,
                }
            ],
            "drafts": [
                {
                    "draft_id": "draft_1",
                    "draft_version": 1,
                    "report_markdown": "# Draft",
                    "sections": [],
                }
            ],
        }
    )

    assert result["review_issues"][0]["issue_id"] == "issue_llm_section_gap"
    assert result["editor2_route_recommendation"]["preferred_action"] == "REVISE_TEXT"
    assert result["contract_meta"]["editor2_review"]["review_mode"] == "llm_synthesized"
    assert result["contract_meta"]["editor2_review"]["llm_mode"] == "live_provider"


def test_editor2_review_provider_backed_flags_source_family_mismatch_as_blocker() -> None:
    """Evidence source_family=company_disclosure but claim requires official_policy → blocker."""
    result = real_nodes.editor2_review_provider_backed({
        "claims": [
            {
                "claim_id": "c1",
                "claim_family": "policy_basis",
                "text": "政策支持低空经济",
                "supported": True,
                "evidence_ids": ["ev1"],
                "required_source_family": "official_policy",
            }
        ],
        "evidence": [
            {
                "evidence_id": "ev1",
                "source_id": "src1",
                "support_type": "direct_support",
                "support_strength": 0.8,
                "summary": "公司披露中提到政策支持",
                "limitations": [],
            }
        ],
        "sources": [
            {
                "source_id": "src1",
                "source_family": "company_disclosure",
                "title": "某公司年报",
            }
        ],
        "drafts": [],
        "claim_support_matrix": [
            {
                "claim_id": "c1",
                "required_source_family": "official_policy",
                "source_families": ["company_disclosure"],
                "evidence_ids": ["ev1"],
                "avg_support_strength": 0.8,
            }
        ],
    })
    issues = result.get("review_issues", [])
    mismatch = [i for i in issues if i.get("issue_type") == "source_family_mismatch"]
    assert len(mismatch) >= 1
    assert mismatch[0]["severity"] == "blocker"
    assert mismatch[0]["target_claim_id"] == "c1"


def test_editor2_review_provider_backed_flags_unsupported_claim_as_blocker() -> None:
    """Claim has no evidence_ids → blocker."""
    result = real_nodes.editor2_review_provider_backed({
        "claims": [
            {
                "claim_id": "c1",
                "claim_family": "policy_basis",
                "text": "无证据断言",
                "supported": False,
                "evidence_ids": [],
                "required_source_family": "official_policy",
            }
        ],
        "evidence": [],
        "sources": [],
        "drafts": [],
        "claim_support_matrix": [],
    })
    issues = result.get("review_issues", [])
    unsupported = [i for i in issues if i.get("issue_type") == "unsupported_claim"]
    assert len(unsupported) >= 1
    assert unsupported[0]["severity"] == "blocker"


def test_editor2_review_provider_backed_flags_low_source_diversity_as_warning() -> None:
    """Claim has only one evidence → warning (not blocker)."""
    result = real_nodes.editor2_review_provider_backed({
        "claims": [
            {
                "claim_id": "c1",
                "claim_family": "policy_basis",
                "text": "单源支撑的结论",
                "supported": True,
                "evidence_ids": ["ev1"],
                "required_source_family": "official_policy",
            }
        ],
        "evidence": [
            {
                "evidence_id": "ev1",
                "source_id": "src1",
                "support_type": "direct_support",
                "support_strength": 0.8,
                "summary": "政策文件支持",
                "limitations": [],
            }
        ],
        "sources": [
            {
                "source_id": "src1",
                "source_family": "official_policy",
                "title": "国务院政策通知",
            }
        ],
        "drafts": [],
        "claim_support_matrix": [
            {
                "claim_id": "c1",
                "required_source_family": "official_policy",
                "source_families": ["official_policy"],
                "evidence_ids": ["ev1"],
                "avg_support_strength": 0.8,
            }
        ],
    })
    issues = result.get("review_issues", [])
    low_div = [i for i in issues if i.get("issue_type") == "low_source_diversity"]
    assert len(low_div) >= 1
    assert low_div[0]["severity"] == "warning"


def test_editor2_review_provider_backed_flags_critical_limitation_as_warning() -> None:
    """Evidence has a limitation containing a critical keyword → warning."""
    result = real_nodes.editor2_review_provider_backed({
        "claims": [
            {
                "claim_id": "c1",
                "claim_family": "policy_basis",
                "text": "有限制的结论",
                "supported": True,
                "evidence_ids": ["ev1"],
                "required_source_family": "official_policy",
            }
        ],
        "evidence": [
            {
                "evidence_id": "ev1",
                "source_id": "src1",
                "support_type": "direct_support",
                "support_strength": 0.7,
                "summary": "政策文件支持",
                "limitations": ["数据缺失，无法完整评估"],
            }
        ],
        "sources": [
            {
                "source_id": "src1",
                "source_family": "official_policy",
                "title": "国务院政策通知",
            }
        ],
        "drafts": [],
        "claim_support_matrix": [
            {
                "claim_id": "c1",
                "required_source_family": "official_policy",
                "source_families": ["official_policy"],
                "evidence_ids": ["ev1"],
                "avg_support_strength": 0.7,
            }
        ],
    })
    issues = result.get("review_issues", [])
    crit_lim = [i for i in issues if i.get("issue_type") == "critical_limitation_unresolved"]
    assert len(crit_lim) >= 1
    assert crit_lim[0]["severity"] == "warning"
    assert crit_lim[0]["target_claim_id"] == "c1"
    assert "缺失" in crit_lim[0]["description"]


def test_chief_gate_provider_backed_uses_editor2_route_recommendation() -> None:
    """维度 evidence 全覆盖时 gate 优先按覆盖度 PASS，editor2 的 REVISE_TEXT 不阻断。

    Evidence 视角下 editor2/verifier 的 route recommendation 不再主导 decision——
    维度覆盖达标即 PASS（editor2 的改写建议仅作为状态输入，由下游消费）。
    """
    result = real_nodes.chief_gate_provider_backed(
        _gate_state(
            plan=[
                _gate_dimension(
                    "d_policy",
                    dimension_type="policy",
                    expected_section_heading="政策与监管",
                    source_families=["policy_document"],
                ),
                _gate_dimension(
                    "d_local_rollout",
                    dimension_type="local_rollout",
                    expected_section_heading="项目落地",
                    source_families=["tender_procurement"],
                ),
            ],
            evidence=[
                _gate_evidence(
                    "ev_policy_1", "src_policy_1",
                    source_family="policy_document",
                    evidence_type="policy_original",
                ),
                _gate_evidence(
                    "ev_policy_2", "src_policy_2",
                    source_family="policy_document",
                    evidence_type="policy_original",
                ),
                _gate_evidence(
                    "ev_local_1", "src_local_1",
                    source_family="tender_procurement",
                    evidence_type="procurement_award",
                ),
                _gate_evidence(
                    "ev_local_2", "src_local_2",
                    source_family="tender_procurement",
                    evidence_type="project_approval",
                ),
            ],
            sources=[
                _gate_source("src_policy_1", source_family="policy_document"),
                _gate_source("src_policy_2", source_family="policy_document"),
                _gate_source("src_local_1", source_family="tender_procurement"),
                _gate_source("src_local_2", source_family="tender_procurement"),
            ],
            review_issues=[
                {
                    "issue_id": "issue_section_gap",
                    "severity": "warning",
                    "issue_type": "draft_section_gap",
                    "target_claim_id": "claim_local_rollout",
                    "description": "Draft section gap.",
                    "required_fix": "Add readable section.",
                    "suggested_search_queries": [],
                }
            ],
            editor2_route_recommendation={
                "preferred_route": "editor1_draft",
                "preferred_action": "REVISE_TEXT",
                "target_claim_ids": ["claim_local_rollout"],
                "reason": "Editor2 wants a rewrite.",
            },
            verifier_route_recommendation={
                "preferred_route": "finalize_report",
                "preferred_action": "PASS",
                "target_claim_ids": [],
                "reason": "Verifier is satisfied.",
            },
        )
    )

    assert result["decision"] == "PASS"
    assert result["gate_route_to"] == "finalize_report"
    assert set(result["dimension_coverage"]) == {"d_policy", "d_local_rollout"}
    assert all(r["covered"] for r in result["dimension_coverage"].values())


def test_verify_claims_provider_backed_flags_missing_editor_section() -> None:
    result = real_nodes.verify_claims_provider_backed(
        {
            "query": "low altitude economy policy",
            "claims": [
                {
                    "claim_id": "claim_policy_primary",
                    "text": "Policy basis exists.",
                    "supported": True,
                    "required_source_family": "official_policy",
                    "support_requirement": "policy_statement",
                    "claim_family": "policy_basis",
                    "evidence_ids": ["ev_policy"],
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_policy",
                    "source_id": "src_policy",
                    "source_ids": ["src_policy"],
                    "support_strength": 0.82,
                    "specificity": "policy_statement",
                    "limitations": [],
                }
            ],
            "sources": [
                {
                    "source_id": "src_policy",
                    "source_family": "official_policy",
                    "source_quality_v2": {
                        "credibility_score": 0.9,
                        "usage_role": "primary_support",
                    },
                }
            ],
            "claim_support_matrix": [
                {
                    "claim_id": "claim_policy_primary",
                    "evidence_ids": ["ev_policy"],
                    "source_ids": ["src_policy"],
                    "avg_support_strength": 0.82,
                    "evidence_specificities": ["policy_statement"],
                    "family_matched": True,
                    "evidence_count": 1,
                    "source_count": 1,
                }
            ],
            "drafts": [
                {
                    "draft_id": "draft_1",
                    "draft_version": 1,
                    "report_markdown": "# Draft without claim mention",
                    "sections": [],
                }
            ],
        }
    )

    notes = result["claim_verifications"][0]["notes"]
    assert any("readable section" in note for note in notes)


def test_chief_gate_evidence_coverage_prefers_llm_synthesized_evidence_type() -> None:
    """Evidence 视角：source_family 漂移时，evidence.evidence_type 命中维度主证据通道兜底。

    原 verify_claims 的 LLM 综合判定（按 evidence_type 归并证据）已由维度覆盖 gate 取代：
    本地源 family 命名与 required_source_families 不一致，但 evidence_type 属于该维度的
    主证据通道 → 维度仍覆盖。
    """
    result = real_nodes.chief_gate_provider_backed(
        _gate_state(
            plan=[
                _gate_dimension(
                    "d_policy",
                    dimension_type="policy",
                    expected_section_heading="政策与监管",
                    source_families=["policy_document"],
                ),
            ],
            evidence=[
                _gate_evidence(
                    "ev_1",
                    "src_1",
                    source_family="local_official",
                    evidence_type="policy_original",
                    proof_strength="strong",
                ),
                _gate_evidence(
                    "ev_2",
                    "src_2",
                    source_family="local_official",
                    evidence_type="policy_signal",
                    proof_strength="medium",
                ),
            ],
            sources=[
                _gate_source("src_1", source_family="local_official"),
                _gate_source("src_2", source_family="local_official"),
            ],
        )
    )

    coverage = result["dimension_coverage"]["d_policy"]
    assert coverage["covered"] is True
    assert coverage["evidence_count"] == 2
    assert coverage["distinct_sources"] == 2
    assert result["decision"] == "PASS"
    assert result["gate_route_to"] == "finalize_report"


def test_chief_gate_provider_backed_uses_verifier_route_recommendation() -> None:
    """维度 evidence 全覆盖时 PASS；verifier 的 HUMAN_REVIEW 推荐不再覆盖覆盖度判定。"""
    result = real_nodes.chief_gate_provider_backed(
        _gate_state(
            plan=[
                _gate_dimension(
                    "d_policy",
                    dimension_type="policy",
                    expected_section_heading="政策与监管",
                    source_families=["policy_document"],
                ),
            ],
            evidence=[
                _gate_evidence(
                    "ev_policy_1", "src_policy_1",
                    source_family="policy_document",
                    evidence_type="policy_original",
                ),
                _gate_evidence(
                    "ev_policy_2", "src_policy_2",
                    source_family="policy_document",
                    evidence_type="policy_original",
                ),
            ],
            sources=[
                _gate_source("src_policy_1", source_family="policy_document"),
                _gate_source("src_policy_2", source_family="policy_document"),
            ],
            verifier_route_recommendation={
                "preferred_route": "human_review",
                "preferred_action": "HUMAN_REVIEW",
                "target_claim_ids": ["claim_policy_primary"],
                "reason": "Verifier wants human review.",
            },
        )
    )

    assert result["decision"] == "PASS"
    assert result["gate_route_to"] == "finalize_report"
    assert result["dimension_coverage"]["d_policy"]["covered"] is True


def test_chief_gate_provider_backed_prefers_stricter_merged_route() -> None:
    """维度覆盖不足时 gate 走 ADD_EVIDENCE，editor2/verifier 的推荐不主导 decision。

    核心语义（更严的合并路由）保留，但 fixture 改为 evidence 视角：两个维度只有 1 个
    被覆盖（ratio=0.5 且 loop 未耗尽）→ 补证，required_actions 指向未覆盖维度。
    """
    result = real_nodes.chief_gate_provider_backed(
        _gate_state(
            plan=[
                _gate_dimension(
                    "d_policy",
                    dimension_type="policy",
                    expected_section_heading="政策与监管",
                    source_families=["policy_document"],
                ),
                _gate_dimension(
                    "d_market",
                    dimension_type="market",
                    expected_section_heading="市场规模与增长",
                    source_families=["official_statistics"],
                ),
            ],
            evidence=[
                _gate_evidence(
                    "ev_policy_1", "src_policy_1",
                    source_family="policy_document",
                    evidence_type="policy_original",
                ),
                _gate_evidence(
                    "ev_policy_2", "src_policy_2",
                    source_family="policy_document",
                    evidence_type="policy_original",
                ),
            ],
            sources=[
                _gate_source("src_policy_1", source_family="policy_document"),
                _gate_source("src_policy_2", source_family="policy_document"),
            ],
            review_issues=[
                {
                    "issue_id": "issue_section_gap",
                    "severity": "warning",
                    "issue_type": "draft_section_gap",
                    "target_claim_id": "claim_local_rollout",
                    "description": "Draft section gap.",
                    "required_fix": "Add readable section.",
                    "suggested_search_queries": [],
                }
            ],
            editor2_route_recommendation={
                "preferred_route": "editor1_draft",
                "preferred_action": "REVISE_TEXT",
                "target_claim_ids": ["claim_local_rollout"],
                "reason": "Editor2 requests a rewrite.",
            },
            verifier_route_recommendation={
                "preferred_route": "human_review",
                "preferred_action": "HUMAN_REVIEW",
                "target_claim_ids": ["claim_local_rollout"],
                "reason": "Verifier requires a human release decision.",
            },
        )
    )

    assert result["decision"] == "ADD_EVIDENCE"
    assert result["gate_route_to"] == "collect_sources"
    assert result["dimension_coverage"]["d_policy"]["covered"] is True
    assert result["dimension_coverage"]["d_market"]["covered"] is False
    assert result["required_actions"] == [
        {"action_type": "ADD_EVIDENCE", "target": "d_market"}
    ]


def test_chief_gate_blocks_on_review_issue_blocker() -> None:
    """Gate sees a blocker in review_issues — cannot PASS."""
    result = real_nodes.chief_gate_provider_backed({
        "query": "测试查询",
        "claims": [
            {"claim_id": "c1", "claim_family": "policy_basis",
             "text": "some policy", "supported": True,
             "evidence_ids": ["ev1"],
             "required_source_family": "official_policy"},
        ],
        "evidence": [
            {"evidence_id": "ev1", "source_id": "src1",
             "support_type": "direct_support", "support_strength": 0.8,
             "summary": "policy text", "limitations": []},
        ],
        "sources": [
            {"source_id": "src1", "source_family": "official_policy",
             "title": "国务院政策通知", "url": "http://example.com/policy",
             "domain": "example.com"},
        ],
        "review_issues": [
            {
                "issue_id": "issue_001",
                "severity": "blocker",
                "issue_type": "source_family_mismatch",
                "target_claim_id": "c1",
                "description": "政策 claim 只有公司披露支撑",
            }
        ],
        "claim_verifications": [],
        "claim_support_matrix": [
            {"claim_id": "c1", "required_source_family": "official_policy",
             "source_families": ["official_policy"],
             "evidence_ids": ["ev1"], "avg_support_strength": 0.8,
             "verified": True},
        ],
        "required_obligation_coverage": [
            {"obligation_id": "obl_policy_primary",
             "required_source_family": "official_policy", "covered": True},
        ],
        "quality_scores": {"final_score": 0.8},
        "editor2_route_recommendation": {},
        "verifier_route_recommendation": {},
        "query_requirements": {},
    })
    assert result["decision"] != "PASS"


def test_chief_gate_downgrades_on_warnings_when_no_blockers() -> None:
    """Evidence 视角：仅 warning（无硬 blocker），维度覆盖达标 → 仍 PASS，不降级阻断。

    原「质量分 downgrade」断言已随旧 gate 移除——新 gate 只以维度 evidence 覆盖度为依据；
    warning 不参与维度覆盖，覆盖达标即放行。
    """
    result = real_nodes.chief_gate_provider_backed(
        _gate_state(
            plan=[
                _gate_dimension(
                    "d_policy",
                    dimension_type="policy",
                    expected_section_heading="政策与监管",
                    source_families=["policy_document"],
                ),
            ],
            evidence=[
                _gate_evidence(
                    "ev_1", "src_1",
                    source_family="policy_document",
                    evidence_type="policy_original",
                ),
                _gate_evidence(
                    "ev_2", "src_2",
                    source_family="policy_document",
                    evidence_type="policy_original",
                ),
            ],
            sources=[
                _gate_source("src_1", source_family="policy_document"),
                _gate_source("src_2", source_family="policy_document"),
            ],
            review_issues=[
                {
                    "issue_id": "issue_002",
                    "severity": "warning",
                    "issue_type": "low_source_diversity",
                    "target_claim_id": "c1",
                    "description": "单源支撑",
                }
            ],
        )
    )

    assert result["decision"] == "PASS"
    assert result["gate_route_to"] == "finalize_report"
    assert result["dimension_coverage"]["d_policy"]["covered"] is True


def test_chief_gate_provider_backed_local_claim_action_carries_location_queries() -> None:
    """Evidence 视角：本地维度未覆盖时 gate 产生 ADD_EVIDENCE action，目标为未覆盖维度。

    核心语义（本地 roll-out 证据缺失 → 触发补证）保留；required_actions 直接指向未覆盖
    维度（含 expected_section_heading），由下游依据 query_requirements 生成位置查询。
    """
    result = real_nodes.chief_gate_provider_backed(
        _gate_state(
            plan=[
                _gate_dimension(
                    "d_local_rollout",
                    dimension_type="local_rollout",
                    expected_section_heading="项目落地",
                    source_families=["tender_procurement"],
                ),
            ],
            evidence=[],
            sources=[],
            query="2025年合肥低空经济地方政策项目公示官方来源",
            query_requirements={
                "needs_company_disclosure": False,
                "target_location": "合肥",
                "is_location_sensitive": True,
            },
        )
    )

    local_action = next(
        item
        for item in result["required_actions"]
        if item.get("target") == "d_local_rollout"
    )

    assert result["decision"] == "ADD_EVIDENCE"
    assert result["gate_route_to"] == "collect_sources"
    assert local_action["action_type"] == "ADD_EVIDENCE"
    assert result["dimension_coverage"]["d_local_rollout"]["covered"] is False
    # 维度空缺 + 本地查询 → 补证目标必须是本地 roll-out 维度（合肥）
    assert result["dimension_coverage"]["d_local_rollout"][
        "expected_section_heading"
    ] == "项目落地"


def test_finalize_report_provider_backed_builds_readable_markdown() -> None:
    result = real_nodes.finalize_report_provider_backed(
        {
            "query": "2025年合肥低空经济地方政策项目公示官方来源",
            "decision": "PASS",
            "gate_reason": "Provider-backed source, evidence, and claim checks passed.",
            "claims": [
                {
                    "claim_id": "claim_policy_primary",
                    "text": "存在官方政策依据。",
                    "supported": True,
                    "claim_family": "policy_basis",
                    "evidence_ids": ["ev_policy"],
                    "required_source_family": "official_policy",
                    "support_requirement": "policy_statement",
                },
                {
                    "claim_id": "claim_local_rollout",
                    "text": "存在合肥本地项目公示或实施依据。",
                    "supported": True,
                    "claim_family": "local_rollout",
                    "evidence_ids": ["ev_local"],
                    "required_source_family": "official_policy",
                    "support_requirement": "policy_statement",
                },
            ],
            "evidence": [
                {
                    "evidence_id": "ev_policy",
                    "source_id": "src_policy",
                    "support_type": "background_support",
                    "support_strength": 0.74,
                    "specificity": "policy_statement",
                    "summary": "[网站首页] 政策文件支持低空经济发展。",
                    "limitations": [],
                },
                {
                    "evidence_id": "ev_local",
                    "source_id": "src_local",
                    "support_type": "direct_support",
                    "support_strength": 0.82,
                    "specificity": "policy_statement",
                    "summary": "%PDF-1.7 合肥发布地方工作方案并附带项目公示信息。",
                    "limitations": ["仍需后续执行进展公告。"],
                },
            ],
            "claim_verifications": [
                {
                    "claim_id": "claim_policy_primary",
                    "support_status": "supported",
                    "support_score": 0.74,
                    "evidence_ids": ["ev_policy"],
                    "source_ids": ["src_policy"],
                    "notes": [],
                },
                {
                    "claim_id": "claim_local_rollout",
                    "support_status": "supported",
                    "support_score": 0.82,
                    "evidence_ids": ["ev_local"],
                    "source_ids": ["src_local"],
                    "notes": ["本地化证据已覆盖合肥。"],
                },
            ],
            "claim_support_matrix": [
                {
                    "claim_id": "claim_policy_primary",
                    "avg_support_strength": 0.74,
                    "evidence_count": 1,
                },
                {
                    "claim_id": "claim_local_rollout",
                    "avg_support_strength": 0.82,
                    "evidence_count": 1,
                },
            ],
            "quality_scores": {
                "evidence_coverage": 1.0,
                "citation_integrity": 0.96,
                "source_quality": 0.84,
                "contradiction_resolution": 0.8,
                "final_score": 0.9,
            },
            "review_issues": [],
            "required_actions": [],
            "sources": [
                {"source_id": "src_policy", "title": "国家政策文件"},
                {"source_id": "src_local", "title": "合肥地方工作方案"},
            ],
        }
    )

    report = result["final_report"]

    assert "report_markdown" in report
    assert "## Executive Summary" in report["report_markdown"]
    assert "## Key Claims" in report["report_markdown"]
    assert "## Evidence And Limitations" in report["report_markdown"]
    assert "## Review Status" in report["report_markdown"]
    assert "国家政策文件" in report["report_markdown"]
    assert "合肥地方工作方案" in report["report_markdown"]
    assert "[网站首页]" not in report["report_markdown"]
    assert "%PDF-1.7" not in report["report_markdown"]
    assert "骞" not in report["report_markdown"]
    assert "绛" not in report["report_markdown"]
    assert report["sections"]
    assert any(section["section_id"] == "executive_summary" for section in report["sections"])
    assert any(section["section_id"] == "key_claims" for section in report["sections"])
    assert any("claim_local_rollout" in section["claim_ids"] for section in report["sections"])


def test_finalize_report_provider_backed_exposes_evidence_quality_audit() -> None:
    result = real_nodes.finalize_report_provider_backed(
        {
            "query": "low altitude economy policy",
            "decision": "HUMAN_REVIEW",
            "gate_reason": "evidence requires review",
            "claims": [
                {
                    "claim_id": "claim_policy",
                    "text": "A formal policy exists.",
                    "supported": False,
                    "claim_family": "policy_basis",
                    "evidence_ids": ["ev_news"],
                    "required_source_family": "official_policy",
                    "support_requirement": "policy_statement",
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_news",
                    "source_id": "src_news",
                    "evidence_type": "policy_signal",
                    "proof_strength": "context_only",
                    "summary": "Official news signal.",
                    "evidence_quality_v2": {
                        "evidence_type": "policy_signal",
                        "proof_strength": "context_only",
                        "primary_support_eligible": False,
                        "not_sufficient_for": ["formal_policy_original_requirement"],
                    },
                }
            ],
            "claim_verifications": [],
            "claim_support_matrix": [
                {
                    "claim_id": "claim_policy",
                    "required_source_family": "official_policy",
                    "evidence_ids": ["ev_news"],
                    "eligibility_passed": False,
                    "claim_support_eligibility": [
                        {
                            "claim_id": "claim_policy",
                            "evidence_id": "ev_news",
                            "eligible": False,
                            "reason_code": "context_only",
                            "required_source_family": "official_policy",
                            "actual_source_family": "official_policy",
                            "evidence_type": "policy_signal",
                            "proof_strength": "context_only",
                        }
                    ],
                }
            ],
            "review_issues": [],
            "sources": [
                {
                    "source_id": "src_news",
                    "source_family": "official_policy",
                    "title": "Official news signal",
                }
            ],
        }
    )

    summary = result["contract_meta"]["evidence_quality"]
    audit_markdown = result["final_report"]["audit_markdown"]

    assert summary["eligibility_failure_count"] == 1
    assert summary["ineligible_evidence_count"] == 1
    assert "Evidence Quality / Eligibility" in audit_markdown
    assert "context_only" in audit_markdown


def test_finalize_report_provider_backed_prefers_editor1_markdown_body() -> None:
    result = real_nodes.finalize_report_provider_backed(
        {
            "query": "low altitude economy policy",
            "decision": "PASS",
            "gate_reason": "checks passed",
            "drafts": [
                {
                    "draft_id": "draft_1",
                    "draft_version": 1,
                    "report_markdown": (
                        "# Analyst Draft\n\n"
                        "## Policy Basis\n\n"
                        "This is the Editor1 readable section body."
                    ),
                    "sections": [],
                }
            ],
            "claims": [
                {
                    "claim_id": "claim_policy_primary",
                    "text": "Policy basis exists.",
                    "supported": True,
                    "claim_family": "policy_basis",
                    "evidence_ids": ["ev_policy"],
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_policy",
                    "source_id": "src_policy",
                    "support_type": "direct_support",
                    "support_strength": 0.82,
                    "specificity": "policy_statement",
                    "summary": "Official policy source.",
                    "limitations": [],
                }
            ],
            "claim_verifications": [
                {
                    "claim_id": "claim_policy_primary",
                    "support_status": "supported",
                    "support_score": 0.82,
                    "evidence_ids": ["ev_policy"],
                    "source_ids": ["src_policy"],
                    "notes": [],
                }
            ],
            "review_issues": [],
            "sources": [{"source_id": "src_policy", "title": "Official policy"}],
        }
    )

    markdown = result["final_report"]["report_markdown"]

    assert markdown.startswith("# Analyst Draft")
    assert "This is the Editor1 readable section body." in markdown
    # Audit appendix is now separated into audit_markdown (Phase 3 remediation)
    assert "## Audit Appendix" in (
        markdown if "## Audit Appendix" in markdown
        else result["final_report"].get("audit_markdown", "")
    )
    assert result["final_report"]["editor1_report_markdown"].startswith("# Analyst Draft")


def test_finalize_report_provider_backed_prefers_canonical_draft_over_latest_ledger() -> None:
    canonical_markdown = (
        "# Canonical Draft\n\n"
        "## Executive Summary\n\nBounded conclusion.\n\n"
        "## Method\n\nEvidence comparison.\n\n"
        "## Analysis\n\nImplementation varies.\n\n"
        "## Risks\n\nEvidence gaps remain.\n\n"
        "## Conclusion\n\nFurther verification is required."
    )
    ledger_markdown = (
        "# Latest Ledger\n\n"
        "## Key Claims\n\n- claim 1\n- claim 2\n\n"
        "## Evidence And Limitations\n\n- ev 1\n- ev 2"
    )
    result = real_nodes.finalize_report_provider_backed(
        {
            "query": "finalizer canonical guard",
            "decision": "PASS",
            "gate_reason": "checks passed",
            "canonical_draft": {
                "draft_id": "draft_good",
                "draft_version": 1,
                "report_markdown": canonical_markdown,
                "sections": real_nodes._parse_markdown_sections(canonical_markdown),
            },
            "drafts": [
                {
                    "draft_id": "draft_good",
                    "draft_version": 1,
                    "report_markdown": canonical_markdown,
                    "sections": real_nodes._parse_markdown_sections(canonical_markdown),
                },
                {
                    "draft_id": "draft_bad",
                    "draft_version": 2,
                    "report_markdown": ledger_markdown,
                    "sections": real_nodes._parse_markdown_sections(ledger_markdown),
                },
            ],
            "claims": [
                {
                    "claim_id": "claim_policy_primary",
                    "text": "Policy basis exists.",
                    "supported": True,
                    "claim_family": "policy_basis",
                    "evidence_ids": ["ev_policy"],
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_policy",
                    "source_id": "src_policy",
                    "support_type": "direct_support",
                    "support_strength": 0.82,
                    "specificity": "policy_statement",
                    "summary": "Official policy source.",
                    "limitations": [],
                }
            ],
            "claim_verifications": [
                {
                    "claim_id": "claim_policy_primary",
                    "support_status": "supported",
                    "support_score": 0.82,
                    "evidence_ids": ["ev_policy"],
                    "source_ids": ["src_policy"],
                    "notes": [],
                }
            ],
            "review_issues": [],
            "sources": [{"source_id": "src_policy", "title": "Official policy"}],
        }
    )

    markdown = result["final_report"]["report_markdown"]

    assert markdown.startswith("# Canonical Draft")
    assert "Latest Ledger" not in markdown
    assert result["final_report"]["editor1_report_markdown"].startswith("# Canonical Draft")
    assert result["contract_meta"]["finalizer_canonical_guard"]["retained_previous_draft"] is True


def test_claim_strength_guard_requires_report_form_for_level_3() -> None:
    graded = real_nodes._claim_strength_guard(
        report_markdown=(
            "# Ledger Draft\n\n"
            "## Key Claims\n\n- claim 1\n- claim 2\n\n"
            "## Evidence And Limitations\n\n- ev 1\n- ev 2"
        ),
        gap_report={"spec_sections": 3, "gaps": []},
    )

    assert graded is not None
    assert graded["report_level"] == "level_2"
    assert any("report-form" in reason for reason in graded["reason"])


def test_claim_strength_guard_caps_level_when_required_obligation_is_uncovered() -> None:
    graded = real_nodes._claim_strength_guard(
        report_markdown=(
            "# Narrative Report\n\n"
            "## Executive Summary\n\nEvidence supports a bounded conclusion.\n\n"
            "## Method\n\nThe analysis compares policy and execution evidence.\n\n"
            "## Analysis\n\nThe sources show a direction, but implementation varies.\n\n"
            "## Risks\n\nLocal project evidence remains incomplete.\n\n"
            "## Conclusion\n\nThe conclusion remains conditional."
        ),
        gap_report={"spec_sections": 4, "gaps": []},
        required_obligation_coverage=[
            {
                "obligation_id": "obl_location_precision",
                "covered": False,
            }
        ],
    )

    assert graded is not None
    assert graded["report_level"] == "level_2"
    assert graded["uncovered_obligation_count"] == 1
    assert any("obl_location_precision" in reason for reason in graded["reason"])


def test_finalize_report_uses_propagated_obligation_coverage_for_level() -> None:
    narrative = (
        "# Narrative Report\n\n"
        "## Executive Summary\n\nEvidence supports a bounded conclusion.\n\n"
        "## Method\n\nThe analysis compares policy and execution evidence.\n\n"
        "## Analysis\n\nThe sources show a direction, but implementation varies.\n\n"
        "## Risks\n\nLocal project evidence remains incomplete.\n\n"
        "## Conclusion\n\nThe conclusion remains conditional."
    )
    result = real_nodes.finalize_report_provider_backed(
        {
            "query": "local evidence coverage",
            "decision": "PASS",
            "gate_reason": "loop budget reached",
            "drafts": [
                {
                    "draft_id": "draft_1",
                    "draft_version": 1,
                    "report_markdown": narrative,
                    "sections": real_nodes._parse_markdown_sections(narrative),
                }
            ],
            "claims": [],
            "evidence": [],
            "sources": [],
            "claim_verifications": [],
            "review_issues": [],
            "evidence_gap_report": {"spec_sections": 4, "gaps": []},
            "required_obligation_coverage": [
                {
                    "obligation_id": "obl_location_precision",
                    "source_family": "location_matched_official_or_project_source",
                    "covered": False,
                }
            ],
        }
    )

    assert result["final_report"]["report_level"] == "level_2"
    assert "obl_location_precision" in result["final_report"]["report_markdown"]


def test_claim_strength_guard_keeps_approved_report_below_level_3_with_blockers() -> None:
    graded = real_nodes._claim_strength_guard(
        report_markdown=(
            "# Narrative Report\n\n"
            "## Executive Summary\n\nEvidence supports a bounded conclusion.\n\n"
            "## Method\n\nThe analysis compares policy and execution evidence.\n\n"
            "## Analysis\n\nThe sources show a direction, but implementation varies.\n\n"
            "## Risks\n\nLocal project evidence remains incomplete.\n\n"
            "## Conclusion\n\nThe conclusion remains conditional."
        ),
        gap_report={"spec_sections": 4, "gaps": []},
        human_review={
            "status": "approved",
            "blocking_issues": [
                {"issue_type": "unsupported_claim", "severity": "blocker"},
                {"issue_type": "human_review_required", "severity": "blocker"},
            ],
        },
    )

    assert graded is not None
    assert graded["report_level"] == "level_2"
    assert graded["evidence_blocker_count"] == 1
    assert graded["human_review_unresolved"] is False
    assert any("unsupported_claim" in reason for reason in graded["reason"])


def test_deterministic_editor_fallback_is_narrative_not_evidence_ledger() -> None:
    markdown, sections = real_nodes._build_narrative_fallback_from_claims(
        query="Assess whether implementation followed policy intent",
        claims=[
            {
                "claim_id": "c1",
                "claim_family": "Policy Framework",
                "text": "The policy defines a direction",
                "evidence_ids": ["ev1"],
                "supported": True,
            },
            {
                "claim_id": "c2",
                "claim_family": "execution_evidence",
                "text": "Implementation remains incomplete",
                "evidence_ids": ["ev2"],
                "supported": False,
            },
        ],
        evidence_items=[
            {
                "evidence_id": "ev1",
                "source_id": "s1",
                "source_family": "official_policy",
                "summary": "An official policy states the direction.",
            },
            {
                "evidence_id": "ev2",
                "source_id": "s2",
                "source_family": "project_list",
                "summary": "A project notice lacks completion evidence.",
            },
        ],
        sources=[],
    )

    quality = real_nodes._assess_draft_narrative_quality(markdown)
    assert quality["passes_minimum_narrative_standard"] is True
    assert quality["ledger_dominant"] is False
    assert "## 综合判断与传导链条" in markdown
    assert "## 政策基础与制度方向" in markdown
    assert "## Policy Framework" not in markdown
    assert "基于 2 个来源" in markdown
    assert "证据 [ev1]" in markdown
    assert len(sections) == 2


def test_narrative_fallback_maps_chinese_claim_families_to_unique_titles() -> None:
    markdown, _ = real_nodes._build_narrative_fallback_from_claims(
        query="县级产业化条件",
        claims=[
            {"claim_id": "c1", "claim_family": "环评条件", "text": "环评已批复"},
            {"claim_id": "c2", "claim_family": "项目备案与企业投资", "text": "项目已备案"},
            {"claim_id": "c3", "claim_family": "产业化条件", "text": "项目已试产"},
            {"claim_id": "c4", "claim_family": "资源条件", "text": "资源可利用"},
            {"claim_id": "c5", "claim_family": "交通与电力", "text": "基础设施待核验"},
        ],
        evidence_items=[],
        sources=[],
    )

    headings = [line for line in markdown.splitlines() if line.startswith("## ")]
    assert "## 环境与土地约束" in headings
    assert "## 企业投资与资金条件" in headings
    assert "## 技术成熟度与产业化能力" in headings
    assert "## 资源基础" in headings
    assert "## 交通与基础设施条件" in headings
    assert "当前来源类别元数据不完整" in markdown
    assert len(headings) == len(set(headings))


def test_clean_report_excerpt_drops_navigation_and_pdf_tokens() -> None:
    noisy_nav = (
        "* (/index.html) * [信息发布](/xxfb/index.html) * [信息公开]"
        "(/public/column/126676984?type=2&nav=1)"
    )
    noisy_pdf = (
        "[PDF] 安徽省加快培育发展低空经济实施方案 | % 1 0 obj <>/Outlines 5 0 R "
        "/Pages 2 0 R /Type/Catalog"
    )

    assert real_nodes._clean_report_excerpt(noisy_nav) == ""
    assert real_nodes._clean_report_excerpt(noisy_pdf) == ""


def test_clean_report_excerpt_drops_office_zip_binary_payload() -> None:
    noisy_docx = (
        "PK! [Content_Types].xmlPK!Qz( word/fontTable.xmlOo0?M[VqX[8 "
        "docProps/core.xml random binary text"
    )

    assert real_nodes._clean_report_excerpt(noisy_docx) == ""


def test_clean_report_excerpt_drops_index_shtml_navigation_and_report_boilerplate() -> None:
    noisy_shtml_nav = (
        "1. 当前位置： 2. (/index.shtml) 3. > 4. [研究](/list/yanjiu/1/cateinfo.html) "
        "5. > 6. [评论视点](/list/yanjiu/pinglun/1/cateinfo.htm)"
    )
    noisy_annual_report = (
        "杭州纵横通信股份有限公司2025 年年度报告摘要 公司代码：603602 公司简称：纵横通信 "
        "2025 年年度报告摘要 第一节重要提示 1、本年度报告摘要来自年度报告"
    )

    assert real_nodes._clean_report_excerpt(noisy_shtml_nav) == ""
    assert real_nodes._clean_report_excerpt(noisy_annual_report) == ""


def test_clean_report_excerpt_drops_investor_record_and_logo_navigation_noise() -> None:
    noisy_investor_record = (
        "证券代码：603101 证券简称：汇嘉时代 新疆汇嘉时代百货股份有限公司 "
        "投资者关系活动记录表 编号：2025-003 投资者关系活动类别"
    )
    noisy_gov_logo = (
        "[![](images/zwgklogo.png)](https://www.ndrc.gov.cn/) 政府信息公开 | | | | "
        "--- | --- | | 公开事项名称："
    )

    assert real_nodes._clean_report_excerpt(noisy_investor_record) == ""
    assert real_nodes._clean_report_excerpt(noisy_gov_logo) == ""


def test_chief_gate_provider_backed_low_diversity_hits_human_review_at_loop_budget() -> None:
    """Evidence 视角：维度覆盖过低且补证轮已用尽 → HUMAN_REVIEW。

    核心语义（低多样性/低覆盖在 loop budget 耗尽后进入人工介入）保留：两个维度均无
    合格 evidence，loop 已耗尽（2/2），ratio<0.5 且无 loop → HUMAN_REVIEW。
    """
    result = real_nodes.chief_gate_provider_backed(
        _gate_state(
            plan=[
                _gate_dimension(
                    "d_policy",
                    dimension_type="policy",
                    expected_section_heading="政策与监管",
                    source_families=["policy_document"],
                ),
                _gate_dimension(
                    "d_market",
                    dimension_type="market",
                    expected_section_heading="市场规模与增长",
                    source_families=["official_statistics"],
                ),
            ],
            evidence=[],
            sources=[],
            loop_count=2,
            max_loop_count=2,
        )
    )

    assert result["decision"] == "HUMAN_REVIEW"
    assert result["gate_route_to"] == "human_review"
    assert all(
        r["covered"] is False for r in result["dimension_coverage"].values()
    )
    # loop budget 已用尽 → gate_reason 标注补证轮耗尽
    assert "补证轮已用尽" in result["gate_reason"]
    assert any(
        item["action_type"] == "HUMAN_REVIEW" for item in result["required_actions"]
    )


def test_finalize_report_provider_backed_cleans_noisy_source_titles() -> None:
    result = real_nodes.finalize_report_provider_backed(
        {
            "query": "2025年低空经济上市公司年报披露与官方政策证据",
            "decision": "PASS",
            "gate_reason": "Provider-backed source, evidence, and claim checks passed.",
            "claims": [
                {
                    "claim_id": "claim_statistics_corroboration",
                    "text": "存在统计口径佐证。",
                    "supported": True,
                    "claim_family": "statistics_corroboration",
                    "evidence_ids": ["ev_stats"],
                    "required_source_family": "statistics_or_data_release",
                    "support_requirement": "statistics_or_data_release",
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_stats",
                    "source_id": "src_stats",
                    "support_type": "direct_support",
                    "support_strength": 0.87,
                    "specificity": "statistics_or_data_release",
                    "summary": "统计分类通知正文。",
                    "limitations": [],
                }
            ],
            "claim_verifications": [
                {
                    "claim_id": "claim_statistics_corroboration",
                    "support_status": "supported",
                    "support_score": 0.87,
                    "evidence_ids": ["ev_stats"],
                    "source_ids": ["src_stats"],
                    "notes": [],
                }
            ],
            "claim_support_matrix": [
                {
                    "claim_id": "claim_statistics_corroboration",
                    "avg_support_strength": 0.87,
                    "evidence_count": 1,
                }
            ],
            "quality_scores": {
                "evidence_coverage": 1.0,
                "citation_integrity": 0.96,
                "source_quality": 0.84,
                "contradiction_resolution": 0.8,
                "final_score": 0.9,
            },
            "review_issues": [],
            "required_actions": [],
                "sources": [
                    {
                        "source_id": "src_stats",
                        "title": (
                            "关于印发统计分类通知 | * [简体]( ;) * [繁体]( ;) "
                            "* (/index.html) * [新闻中心]"
                        ),
                    }
                ],
            }
        )

    markdown = result["final_report"]["report_markdown"]

    assert "关于印发统计分类通知" in markdown
    assert "* [简体]" not in markdown
    assert "(/index.html)" not in markdown


def test_clean_report_title_drops_content_farm_titles() -> None:
    noisy_news_title = "轻松关闭推送，静享搜狐新闻时光"
    noisy_guide_title = "炼金新兵速成手册：新手攻略全解析"

    assert real_nodes._clean_report_title(noisy_news_title) == ""
    assert real_nodes._clean_report_title(noisy_guide_title) == ""


def test_choose_report_source_label_prefers_generic_label_for_investor_record() -> None:
    label = real_nodes._choose_report_source_label(
        {
            "source_family": "company_disclosure",
            "source_quality_v2": {
                "source_role": "company_disclosure",
                "usage_role": "primary_evidence_candidate",
            },
            "title": "[PDF] 新疆汇嘉时代百货股份有限公司投资者关系活动记录表",
        }
    )

    assert label == "公司披露补充材料"


def test_choose_report_source_label_degrades_non_report_disclosure_material() -> None:
    label = real_nodes._choose_report_source_label(
        {
            "source_family": "company_disclosure",
            "source_quality_v2": {
                "source_role": "company_disclosure",
                "usage_role": "primary_evidence_candidate",
            },
            "title": (
                "[PDF] 湖南兴湘投资控股集团有限公司2025年面向专业投资者"
                "公开发行科技创新公司债券（低空经济）（第一期）发行结果公告"
            ),
        }
    )

    assert label == "公司披露补充材料"


def test_choose_report_source_label_degrades_article_like_policy_title() -> None:
    label = real_nodes._choose_report_source_label(
        {
            "source_family": "official_policy",
            "source_quality_v2": {
                "source_role": "official_policy_original",
                "usage_role": "supporting_evidence_candidate",
            },
            "title": "低空经济：我国经济增长的新引擎 - 广州空港经济区管理委员会",
        }
    )

    assert label == "政策支持类来源"


def test_choose_report_source_label_degrades_industry_news_and_policy_compilation_titles() -> None:
    industry_news = real_nodes._choose_report_source_label(
        {
            "source_family": "official_policy",
            "source_quality_v2": {
                "source_role": "official_policy_original",
                "usage_role": "supporting_evidence_candidate",
            },
            "title": "推进低空经济发展需技术与政策双轮驱动_行业资讯_数字中国建设峰会",
        }
    )
    policy_compilation = real_nodes._choose_report_source_label(
        {
            "source_family": "official_policy",
            "source_quality_v2": {
                "source_role": "official_policy_original",
                "usage_role": "supporting_evidence_candidate",
            },
            "title": "[PDF] 文件汇编 - 西藏自治区发展和改革委员会 - 西藏自治区人民政府",
        }
    )

    assert industry_news == "政策支持类来源"
    assert policy_compilation == "政策支持类来源"


def test_choose_report_source_label_degrades_content_farm_policy_and_gazette_stats_titles() -> None:
    policy_content_farm = real_nodes._choose_report_source_label(
        {
            "source_family": "official_policy",
            "source_quality_v2": {
                "source_role": "official_policy_original",
                "usage_role": "supporting_evidence_candidate",
            },
            "title": "黄色软件不打马赛克3.0V-少女的秘密",
        }
    )
    stats_gazette = real_nodes._choose_report_source_label(
        {
            "source_family": "statistics_or_data_release",
            "source_quality_v2": {
                "source_role": "statistics_or_data_release",
                "usage_role": "supporting_evidence_candidate",
            },
            "title": "[PDF] 厦门市人民代表大会常务委员会公报",
        }
    )

    assert policy_content_farm == "政策支持类来源"
    assert stats_gazette == "统计口径或分类通知"


def test_finalize_report_provider_backed_omits_noisy_excerpt_when_label_is_generic() -> None:
    result = real_nodes.finalize_report_provider_backed(
        {
            "query": "2025年低空经济上市公司年报披露与官方政策证据",
            "decision": "PASS",
            "gate_reason": "Provider-backed source, evidence, and claim checks passed.",
            "claims": [
                {
                    "claim_id": "claim_policy_primary",
                    "text": "存在政策支持依据。",
                    "supported": True,
                    "claim_family": "policy_basis",
                    "evidence_ids": ["ev_policy"],
                    "required_source_family": "official_policy",
                    "support_requirement": "policy_statement",
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_policy",
                    "source_id": "src_policy",
                    "support_type": "background_support",
                    "support_strength": 0.81,
                    "specificity": "policy_statement",
                    "summary": (
                        "涂鸦智能，披露2025年财报！欧美人 全国人大代表冯兴亚建言："
                        "制定低空经济..."
                    ),
                    "limitations": [],
                }
            ],
            "claim_verifications": [
                {
                    "claim_id": "claim_policy_primary",
                    "support_status": "supported",
                    "support_score": 0.81,
                    "evidence_ids": ["ev_policy"],
                    "source_ids": ["src_policy"],
                    "notes": [],
                }
            ],
            "claim_support_matrix": [
                {
                    "claim_id": "claim_policy_primary",
                    "avg_support_strength": 0.81,
                    "evidence_count": 1,
                }
            ],
            "quality_scores": {
                "evidence_coverage": 1.0,
                "citation_integrity": 0.96,
                "source_quality": 0.84,
                "contradiction_resolution": 0.8,
                "final_score": 0.9,
            },
            "review_issues": [],
            "required_actions": [],
            "sources": [
                {
                    "source_id": "src_policy",
                    "source_family": "official_policy",
                    "source_quality_v2": {
                        "source_role": "official_policy_original",
                        "usage_role": "supporting_evidence_candidate",
                    },
                    "title": "推进低空经济发展需技术与政策双轮驱动_行业资讯_数字中国建设峰会",
                }
            ],
        }
    )

    markdown = result["final_report"]["report_markdown"]

    assert "政策支持类来源" in markdown
    assert "涂鸦智能" not in markdown
    assert "冯兴亚" not in markdown


def test_finalize_report_provider_backed_repairs_mojibake_for_display() -> None:
    def chars(*codepoints: int) -> str:
        return "".join(chr(codepoint) for codepoint in codepoints)

    def mojibake(value: str) -> str:
        return value.encode("utf-8").decode("gbk", errors="ignore")

    query = "2025" + chars(
        0x5E74, 0x5408, 0x80A5, 0x4F4E, 0x7A7A, 0x7ECF, 0x6D4E,
        0x5730, 0x65B9, 0x653F, 0x7B56, 0x5B98, 0x65B9, 0x6765, 0x6E90,
    )
    claim_text = "2025" + chars(
        0x5E74, 0x5408, 0x80A5, 0x4F4E, 0x7A7A, 0x7ECF, 0x6D4E,
        0x6709, 0x653F, 0x7B56, 0x4F9D, 0x636E, 0x3002,
    )
    evidence_summary = chars(
        0x5408, 0x80A5, 0x5E02, 0x652F, 0x6301, 0x4F4E, 0x7A7A,
        0x7ECF, 0x6D4E, 0x653F, 0x7B56, 0x6765, 0x6E90, 0x3002,
    )
    source_title = chars(
        0x5408, 0x80A5, 0x5E02, 0x652F, 0x6301, 0x4F4E, 0x7A7A,
        0x7ECF, 0x6D4E, 0x53D1, 0x5C55, 0x653F, 0x7B56,
    )

    result = real_nodes.finalize_report_provider_backed(
        {
            "query": mojibake(query),
            "decision": "PASS",
            "gate_reason": "Provider-backed source, evidence, and claim checks passed.",
            "claims": [
                {
                    "claim_id": "claim_policy_primary",
                    "text": mojibake(claim_text),
                    "supported": True,
                    "claim_family": "policy_basis",
                    "evidence_ids": ["ev_policy"],
                    "required_source_family": "official_policy",
                    "support_requirement": "policy_statement",
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_policy",
                    "source_id": "src_policy",
                    "support_type": "direct_support",
                    "support_strength": 0.82,
                    "specificity": "policy_statement",
                    "summary": mojibake(evidence_summary),
                    "limitations": [],
                }
            ],
            "claim_verifications": [
                {
                    "claim_id": "claim_policy_primary",
                    "support_status": "supported",
                    "support_score": 0.82,
                    "evidence_ids": ["ev_policy"],
                    "source_ids": ["src_policy"],
                    "notes": [],
                }
            ],
            "review_issues": [],
            "required_actions": [],
            "sources": [
                {
                    "source_id": "src_policy",
                    "source_family": "official_policy",
                    "source_quality_v2": {
                        "source_role": "official_policy_original",
                        "usage_role": "primary_evidence_candidate",
                    },
                    "title": mojibake(source_title),
                }
            ],
        }
    )

    markdown = result["final_report"]["report_markdown"]

    assert query[:10] in markdown
    assert source_title[:9] in markdown
    assert "\u9a9e" not in markdown
    assert "\u935a" not in markdown

def test_editor_draft_numeric_confidence_is_normalized_before_fallback() -> None:
    model, meta = coerce_model_output(
        {
            "draft_id": "draft_1",
            "draft_version": 1,
            "sections": [
                {
                    "section_id": "summary",
                    "title": "Summary",
                    "paragraphs": [
                        {
                            "paragraph_id": "p1",
                            "text": "可用段落。",
                            "claim_ids": ["claim_policy_primary"],
                            "evidence_ids": ["ev_1"],
                            "confidence": 0.82,
                            "limitations": [],
                        }
                    ],
                }
            ],
        },
        model_cls=EditorDraftOutput,
        fallback_factory=lambda: {
            "draft_id": "fallback",
            "draft_version": 1,
            "sections": [],
        },
    )

    assert isinstance(model, EditorDraftOutput)
    assert model.sections[0].paragraphs[0].confidence == "high"
    assert meta["status"] == "normalized"
    assert meta["used_fallback"] is False
    assert set(meta["attempts"][0]["normalizations"]) >= {
        "editor_draft_numeric_confidence_to_label",
        "editor_draft_report_markdown_composed_from_sections",
    }


def test_editor_draft_section_like_payload_is_wrapped_and_normalized() -> None:
    model, meta = coerce_model_output(
        {
            "section_id": "sec_exec_summary",
            "title": "Executive Summary",
            "section_role": "analysis",
            "argument_posture": "neutral",
            "body": "本节是模型直接返回的单个 section。",
            "paragraphs": [
                {
                    "paragraph_id": "p1",
                    "text": "存在可读摘要。",
                    "claim_ids": ["claim_policy_primary"],
                    "evidence_ids": ["ev_1"],
                    "confidence": "medium",
                    "limitations": [],
                    "argument_posture": "neutral",
                }
            ],
        },
        model_cls=EditorDraftOutput,
        fallback_factory=lambda: {
            "draft_id": "fallback",
            "draft_version": 1,
            "sections": [],
        },
    )

    assert isinstance(model, EditorDraftOutput)
    assert model.draft_id == "editor_draft_normalized"
    assert model.draft_version == 1
    assert model.sections[0].markdown_body == "本节是模型直接返回的单个 section。"
    assert model.sections[0].argument_posture == "mixed"
    assert model.sections[0].paragraphs[0].argument_posture == "conditional"
    assert "Executive Summary" in model.report_markdown
    assert meta["used_fallback"] is False
    assert meta["status"] == "normalized"
    assert set(meta["attempts"][0]["normalizations"]) >= {
        "editor_draft_missing_draft_id",
        "editor_draft_missing_draft_version",
        "editor_draft_section_wrapped_as_output",
        "editor_draft_section_body_promoted_to_markdown_body",
        "editor_draft_report_markdown_composed_from_sections",
    }


def test_clean_report_excerpt_drops_table_of_contents_style_pdf_text() -> None:
    noisy_toc = (
        "文件汇编 西藏自治区发展和改革委员会 编 目录 — 1 — 目 录 国家文件 "
        "1. 中华人民共和国民营经济促进法 8 2. 中共中"
    )
    noisy_gov_gazette = (
        "目录 市政府文件 许昌市人民政府关于印发许昌市“十四五”市场监管现代化规划 的通知"
        " · · · · · · · · · ·"
    )

    assert real_nodes._clean_report_excerpt(noisy_toc) == ""
    assert real_nodes._clean_report_excerpt(noisy_gov_gazette) == ""


def test_build_query_requirements_extracts_multiple_locations() -> None:
    requirements = real_nodes._build_query_requirements(
        "2025年合肥和武汉低空经济地方政策项目公示官方来源对比"
    )

    assert requirements["is_location_sensitive"] is True
    assert requirements["target_location"] == "合肥,武汉"


def test_location_match_summary_tracks_multi_city_coverage() -> None:
    summary = real_nodes._location_match_summary(
        sources=[
            {
                "title": "合肥低空经济项目公示",
                "url": "",
                "domain": "",
                "clean_text": "",
                "snippet": "",
            },
            {
                "title": "武汉低空经济政策通知",
                "url": "",
                "domain": "",
                "clean_text": "",
                "snippet": "",
            },
            {
                "title": "国家低空经济政策",
                "url": "",
                "domain": "",
                "clean_text": "",
                "snippet": "",
            },
        ],
        target_location="合肥,武汉",
    )

    assert summary["target_locations"] == ["合肥", "武汉"]
    assert summary["matched_locations"] == ["合肥", "武汉"]
    assert summary["matched_ratio"] == 0.667
    assert summary["coverage_complete"] is True


def test_normalize_query_requirements_drops_non_location_target_text() -> None:
    normalized = real_nodes._normalize_query_requirements(
        query="2025年低空经济政策目标与统计数据官方证据",
        query_requirements={
            "needs_company_disclosure": False,
            "target_location": "2025年低空经济政策目标与统计数据官方证据",
            "is_location_sensitive": True,
        },
    )

    assert normalized == {
        "needs_company_disclosure": False,
        "target_location": None,
        "is_location_sensitive": False,
    }


def test_human_review_state_includes_p0_context_from_gate() -> None:
    """Evidence 视角：硬质量 blocker（contradiction）优先 HUMAN_REVIEW，维度覆盖报告透出。

    原 P0-context 断言基于旧 claim-based gate 的 Phase-4 代码（已随砍 claim 移除）。
    新 gate 在 Phase C 硬 blocker 分支直接返回 HUMAN_REVIEW，human_review 状态由
    human_review 节点消费 gate_reason + required_actions 组装——这里断言 gate 产出的
    覆盖报告与 blocker 判定。
    """
    result = real_nodes.chief_gate_provider_backed(
        _gate_state(
            plan=[
                _gate_dimension(
                    "d_policy",
                    dimension_type="policy",
                    expected_section_heading="政策与监管",
                    source_families=["policy_document"],
                ),
            ],
            evidence=[
                _gate_evidence(
                    "ev_1", "src_1",
                    source_family="policy_document",
                    evidence_type="policy_original",
                ),
                _gate_evidence(
                    "ev_2", "src_2",
                    source_family="policy_document",
                    evidence_type="policy_original",
                ),
            ],
            sources=[
                _gate_source("src_1", source_family="policy_document"),
                _gate_source("src_2", source_family="policy_document"),
            ],
            review_issues=[
                {
                    "issue_id": "issue_001",
                    "severity": "blocker",
                    "issue_type": "contradiction",
                    "target_claim_id": "c1",
                    "description": "证据间存在矛盾，需要人工裁决",
                }
            ],
        )
    )

    assert result["decision"] == "HUMAN_REVIEW"
    assert result["gate_route_to"] == "human_review"
    assert any(
        item["action_type"] == "HUMAN_REVIEW" for item in result["required_actions"]
    )
    # 即便维度 evidence 覆盖达标，硬 blocker 仍优先人工介入
    assert result["dimension_coverage"]["d_policy"]["covered"] is True
    assert "contradiction" in result["gate_reason"]


def test_human_review_action_includes_override_p0() -> None:
    """GraphAnalyzeRequest.human_review_action accepts 'override_p0'."""
    from packages.research_harness.schemas import GraphAnalyzeRequest
    req = GraphAnalyzeRequest(
        query="测试",
        human_review_action="override_p0",
        human_review_notes="误判，这是合法的交叉引用",
    )
    assert req.human_review_action == "override_p0"


def test_apply_human_review_override_p0() -> None:
    """_apply_human_review_action with override_p0 marks issues as overridden."""
    from packages.research_harness.runner import _apply_human_review_action
    state = {
        "human_review": {
            "pending": True,
            "blocking_issues": [
                {"issue_id": "issue_001", "severity": "blocker",
                 "issue_type": "source_family_mismatch"}
            ],
            "p0_review_context": {
                "available_actions": ["approve", "override_p0"],
                "suggested_action": "add_evidence",
                "suggested_reason": "需要补充政策原文",
            },
        },
        "decision": "HUMAN_REVIEW",
    }
    result = _apply_human_review_action(
        state, action="override_p0", notes="合法交叉引用"
    )
    hr = result.get("human_review", {})
    assert hr.get("pending") is False
    assert hr.get("selected_action") == "override_p0"
    assert result.get("decision") == "PASS"
    for issue in hr.get("blocking_issues", []):
        assert issue.get("overridden_by_human") is True
