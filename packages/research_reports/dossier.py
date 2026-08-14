from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.agents.deep_research_schemas import DeepResearchReport

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone.utc  # noqa: UP017


def write_deep_research_dossier(
    *,
    report_id: int,
    query: str,
    report: DeepResearchReport,
    context: dict[str, Any] | None = None,
    base_dir: str | Path = "data/run_dossiers",
) -> Path:
    """Write a human-readable Markdown dossier for a Deep Research report."""

    now = datetime.now(UTC)
    root = Path(base_dir) / "deep_research" / now.strftime("%Y%m%d") / f"report_{report_id}"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "dossier.md"
    path.write_text(
        render_deep_research_dossier(
            report_id=report_id,
            query=query,
            report=report,
            context=context or {},
            generated_at=now,
        ),
        encoding="utf-8",
    )
    return path.resolve()


def write_graph_research_dossier(
    *,
    run_id: int,
    query: str,
    response_json: dict[str, Any],
    context: dict[str, Any] | None = None,
    base_dir: str | Path = "data/run_dossiers",
) -> Path:
    """Write a human-readable Markdown dossier for a shadow graph research run."""

    now = datetime.now(UTC)
    root = Path(base_dir) / "deep_research_graph" / now.strftime("%Y%m%d") / f"run_{run_id}"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "dossier.md"
    path.write_text(
        render_graph_research_dossier(
            run_id=run_id,
            query=query,
            response_json=response_json,
            context=context or {},
            generated_at=now,
        ),
        encoding="utf-8",
    )
    return path.resolve()


def render_deep_research_dossier(
    *,
    report_id: int,
    query: str,
    report: DeepResearchReport,
    context: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> str:
    context = context or {}
    generated_at = generated_at or datetime.now(UTC)

    parts = [
        "# Deep Research 运行档案\n",
        f"- 报告 ID: `{report_id}`",
        f"- 生成时间: `{generated_at.isoformat()}`",
        f"- 原始查询: { _inline(query) }",
        f"- 综合置信度: `{report.overall_confidence}`",
        f"- 搜索轮次: `{report.search_rounds_executed}`",
        f"- 预估积分: `{report.estimated_tavily_credits}`",
        "",
        "## 1. 查询与来源",
        _render_query_expansion(context),
        _render_search_rounds(context),
        _render_source_candidates(context),
        _render_source_assessments(report, context),
        "## 2. 证据与代理流水线",
        _render_evidence(report),
        _render_agent_pipeline(report, context),
        _render_detailed_agent_trace(context),
        "## 3. 内容资产与生成追踪",
        _render_content_assets(context),
        "## Dossier Notes",
        (
            "- V2 records visible inputs, outputs, source decisions, evidence, and "
            "agent-stage summaries. It does not store raw hidden model reasoning."
        ),
        (
            "- Sensitive fields such as API keys, authorization headers, tokens, "
            "and reasoning are excluded."
        ),
        "",
    ]
    return "\n".join(part for part in parts if part is not None)


def render_graph_research_dossier(
    *,
    run_id: int,
    query: str,
    response_json: dict[str, Any],
    context: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> str:
    context = context or {}
    generated_at = generated_at or datetime.now(UTC)

    parts = [
        "# LangGraph 研报运行档案\n",
        f"- 运行 ID: `{run_id}`",
        f"- 生成时间: `{generated_at.isoformat()}`",
        f"- 原始查询: { _inline(query) }",
        f"- 线程 ID: `{response_json.get('thread_id', '')}`",
        f"- 状态: `{response_json.get('status', '')}`",
        f"- 决策: `{response_json.get('decision', '')}`",
        f"- 从检查点恢复: `{response_json.get('resumed_from_checkpoint', False)}`",
        f"- 检查点路径: `{response_json.get('checkpoint_path', '')}`",
        f"- 档案路径: `{response_json.get('dossier_path', '')}`",
        "",
        "## 1. 运行概览",
        _render_graph_overview(response_json, context),
        _render_graph_planner_contract(context),
        "## 2. 节点执行追踪",
        _render_graph_node_steps(context),
        "## 3. 来源、证据与断言",
        _render_graph_search_events(context),
        _render_graph_sources(context),
        _render_graph_retrieval_pack(context),
        _render_graph_evidence(context),
        _render_graph_claims(context),
        _render_graph_claim_support_matrix(context),
        _render_graph_claim_verifications(context),
        _render_graph_contract_diagnostics(context),
        "## 4. 上下文包",
        _render_graph_context_pack_table(context),
        _render_graph_context_pack_details(context),
        "## 5. 工具调用追踪",
        _render_graph_tool_traces(context),
        "## 6. 人工复核",
        _render_graph_human_review(context),
        "## 7. 最终报告预览",
        _render_graph_final_report(context),
        "## 术语说明",
        _render_graph_glossary(),
        "## 档案说明",
        "- 本档案记录可见的图状态、节点输出和上下文包摘要。",
        "- 不记录隐藏的思维链或密钥信息。",
        "",
    ]
    return "\n".join(part for part in parts if part is not None)


def _render_query_expansion(context: dict[str, Any]) -> str:
    understanding = context.get("understanding") or {}
    dimensions = understanding.get("research_dimensions") or []
    if not dimensions:
        return "### 查询扩展\n\n未捕获查询扩展详情。\n"

    rows = [
        "| 维度 | 描述 | 口径词 | 来源优先级 |",
        "|---|---|---|---|",
    ]
    for dim in dimensions:
        terms = dim.get("caliber_terms") or []
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(dim.get("label", "")),
                    _cell(dim.get("description", "")),
                    _cell(", ".join(str(term) for term in terms)),
                    _cell(dim.get("source_priority", "")),
                ]
            )
            + " |"
        )
    return "### 查询扩展\n\n" + "\n".join(rows) + "\n"


def _render_graph_overview(response_json: dict[str, Any], context: dict[str, Any]) -> str:
    quality_scores = context.get("quality_scores") or response_json.get("quality_scores") or {}
    rows = [
        "| 指标 | 数值 |",
        "|---|---|",
        f"| 节点数 | `{len(context.get('node_steps', []))}` |",
        f"| 上下文包数 | `{len(context.get('context_packs', []))}` |",
        f"| 证据覆盖率 | `{quality_scores.get('evidence_coverage', '')}` |",
        f"| 引用完整性 | `{quality_scores.get('citation_integrity', '')}` |",
        f"| 来源质量 | `{quality_scores.get('source_quality', '')}` |",
        f"| 综合评分 | `{quality_scores.get('final_score', '')}` |",
    ]
    return "\n".join(rows) + "\n"


def _render_graph_planner_contract(context: dict[str, Any]) -> str:
    plan = context.get("plan") or {}
    planner_metadata = context.get("planner_metadata") or {}
    summary_memory = context.get("summary_memory") or {}
    research_dimensions = plan.get("research_dimensions") or []
    dimension_plan = plan.get("dimension_plan") or []
    if (
        not research_dimensions
        and not dimension_plan
        and not planner_metadata
        and not summary_memory
    ):
        return "### 规划合约\n\n未捕获规划合约详情。\n"

    summary_rows = [
        "| 规划项 | 数值 |",
        "|---|---|",
        f"| Planner Mode | `{planner_metadata.get('planner_mode', '')}` |",
        f"| Planner Provider | `{planner_metadata.get('planner_provider', '')}` |",
        f"| Planner Model | `{planner_metadata.get('planner_model', '')}` |",
        f"| Deterministic Fallback | `{planner_metadata.get('deterministic_fallback', '')}` |",
        f"| Summary Memory Used | `{planner_metadata.get('summary_memory_used', False)}` |",
        (
            "| Summary Memory Keys | "
            + _cell(", ".join(planner_metadata.get("summary_memory_keys", [])))
            + " |"
        ),
        f"| Research Dimension Count | `{len(research_dimensions)}` |",
        f"| Dimension Plan Count | `{len(dimension_plan)}` |",
        f"| Search Round Count | `{len(plan.get('search_rounds', []))}` |",
        f"| Source Obligation Count | `{len(plan.get('source_obligations', []))}` |",
    ]

    dimension_rows = [
        (
            "| Dimension ID | Dimension Type | Research Question | Why It Matters | "
            "Coverage Required | Expected Section | Source Families |"
        ),
        "|---|---|---|---|---|---|---|",
    ]
    for item in dimension_plan[:20]:
        dimension_rows.append(
            "| "
            + " | ".join(
                [
                    _cell(item.get("dimension_id", "")),
                    _cell(item.get("dimension_type", "")),
                    _cell(item.get("research_question", "")),
                    _cell(item.get("why_it_matters", "")),
                    _cell(item.get("coverage_required", "")),
                    _cell(item.get("expected_section_heading", "")),
                    _cell(", ".join(str(x) for x in item.get("source_families", []))),
                ]
            )
            + " |"
        )

    summary_memory_block = (
        "#### Summary Memory Input\n\n"
        + _fence_json(summary_memory, limit=2_000)
        + "\n"
        if summary_memory
        else "#### Summary Memory Input\n\nNo summary memory was provided to this run.\n"
    )

    note = (
        "`dimension_plan` 是 planner 正式产出的研究维度合同。它不只是粗略主题列表，而是明确规定："
        "每个研究维度要回答什么问题、为什么重要、覆盖义务是什么、预期写入报告哪个章节、以及优先依赖哪类来源。"
        "`summary_memory` 不是事实证据，而是历史运行中反复出现的主题偏好、证据缺口或规划倾向，"
        "用来影响下一轮任务规划。"
    )
    dimension_block = (
        "\n".join(dimension_rows) + "\n"
        if dimension_plan
        else "未捕获维度计划条目。\n"
    )
    return (
        "### 规划合约\n\n"
        + note
        + "\n\n"
        + "\n".join(summary_rows)
        + "\n\n#### Dimension Plan\n\n"
        + dimension_block
        + "\n"
        + summary_memory_block
    )


def _render_graph_node_steps(context: dict[str, Any]) -> str:
    steps = context.get("node_steps") or []
    if not steps:
        return "未捕获图节点步骤。\n"
    rows = [
        "| Node | Agent | Status | Output Summary |",
        "|---|---|---|---|",
    ]
    for step in steps[:120]:
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(step.get("node_name", "")),
                    _cell(step.get("agent_name", "")),
                    _cell(step.get("status", "")),
                    _cell(step.get("output_summary", {})),
                ]
            )
            + " |"
        )
    return "\n".join(rows) + "\n"


def _render_graph_search_events(context: dict[str, Any]) -> str:
    events = context.get("search_events") or []
    if not events:
        return "### 搜索事件\n\n未捕获搜索事件。\n"
    rows = [
        "| Round | Search Phrase | Status | Result Count | Estimated Credits | Errors |",
        "|---:|---|---|---:|---:|---|",
    ]
    for event in events[:80]:
        errors = event.get("errors") or []
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(event.get("round_number", "")),
                    _cell(event.get("search_phrase", "")),
                    _cell(event.get("status", "")),
                    _cell(event.get("result_count", "")),
                    _cell(event.get("estimated_credits", "")),
                    _cell(errors[:2]),
                ]
            )
            + " |"
        )
    note = (
        "`search_events` 是 `collect_sources` 节点的搜索调用记录；它用于解释"
        "每个扩展搜索词是否成功、返回了多少结果、估算花费多少 Tavily credits，"
        "以及是否出现 provider 错误。它不是最终证据，只是源发现过程的审计轨迹。"
    )
    return "### 搜索事件\n\n" + note + "\n\n" + "\n".join(rows) + "\n"


def _render_graph_sources(context: dict[str, Any]) -> str:
    sources = context.get("sources") or []
    if not sources:
        return "### 来源\n\n未捕获图来源对象.\n"
    rows = [
        (
            "| Source ID | Tier | Source Family | Source Role | Usage Role | "
            "Credibility | Search Phrase | Title | URL | Text Retained |"
        ),
        "|---|---|---|---|---|---:|---|---|---|---:|",
    ]
    for source in sources[:80]:
        quality = source.get("source_quality_v2") or {}
        raw_meta = source.get("raw_text_meta") or {}
        retained = raw_meta.get("retained_chars", len(str(source.get("raw_text", ""))))
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(source.get("source_id", "")),
                    _cell(source.get("source_tier") or quality.get("tier", "")),
                    _cell(source.get("source_family", "")),
                    _cell(quality.get("source_role", "")),
                    _cell(quality.get("usage_role", "")),
                    _cell(quality.get("credibility_score", "")),
                    _cell(source.get("search_phrase", "")),
                    _cell(source.get("title", "")),
                    _link_cell(source.get("url", "")),
                    _cell(retained),
                ]
            )
            + " |"
        )
    note = (
        "`source_family` 是采集层对源类型的初步归类，例如政策、公共资源交易、"
        "统计数据或公司披露；`source_role` 和 `usage_role` 来自 Source Quality v2，"
        "分别表示源的角色和后续可用方式。"
    )
    return "### 来源\n\n" + note + "\n\n" + "\n".join(rows) + "\n"


def _render_graph_retrieval_pack(context: dict[str, Any]) -> str:
    retrieval_pack = context.get("retrieval_pack") or {}
    if not retrieval_pack:
        return "### 检索包\n\n未捕获检索包.\n"
    items = retrieval_pack.get("items") or []
    rows = [
        "| Chunk ID | Title | Score | Locator | Chunk Text |",
        "|---|---|---:|---|---|",
    ]
    for item in items[:20]:
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(item.get("chunk_id", "")),
                    _cell(item.get("document_title", "")),
                    _cell(item.get("score", "")),
                    _cell(item.get("citation_locator", "")),
                    _cell(item.get("chunk_text", "")),
                ]
            )
            + " |"
        )
    note = (
        "`retrieval_pack` 是 graph 在当前 source text 上构建出来的 chunk 级检索审计对象。"
        "它属于检索层，不是最终 evidence；它的作用是把后续 evidence/claim 生成切换到"
        "可审计的 chunk 级上下文。"
        "当前版本已经进入 graph-runtime hybrid contract："
        "它会结合 query 命中、研究维度术语、source obligation、来源类型与地域对齐做排序。"
        "但它仍是过渡桥，后续还会升级到 chunk + PostgreSQL + "
        "pgvector + BM25 + reranker 的混合检索。"
    )
    summary = [
        f"- Retrieval Mode: `{retrieval_pack.get('retrieval_mode', '')}`",
        f"- Adapter Status: `{retrieval_pack.get('adapter_status', '')}`",
        f"- Backend Retrieval Mode: `{retrieval_pack.get('backend_retrieval_mode', '')}`",
        f"- Total Candidates: `{retrieval_pack.get('total_candidates', 0)}`",
        f"- Returned Count: `{retrieval_pack.get('returned_count', 0)}`",
    ]
    dimension_focus = retrieval_pack.get("dimension_focus") or []
    obligation_focus = retrieval_pack.get("obligation_focus") or []
    focus_rows = [
        "| Focus Type | Focus ID | Meaning | Source Families / Terms |",
        "|---|---|---|---|",
    ]
    for item in dimension_focus[:12]:
        focus_rows.append(
            "| "
            + " | ".join(
                [
                    "dimension",
                    _cell(item.get("dimension_id", "")),
                    _cell(item.get("expected_section_heading", "")),
                    _cell(
                        ", ".join(str(x) for x in item.get("source_families", []))
                        + " / "
                        + ", ".join(str(x) for x in item.get("caliber_terms", []))
                    ),
                ]
            )
            + " |"
        )
    for item in obligation_focus[:12]:
        focus_rows.append(
            "| "
            + " | ".join(
                [
                    "obligation",
                    _cell(item.get("obligation_id", "")),
                    _cell(item.get("required_for", "")),
                    _cell(str(item.get("source_family", ""))),
                ]
            )
            + " |"
        )
    return (
        "### 检索包\n\n"
        + note
        + "\n\n"
        + "\n".join(summary)
        + "\n\n"
        + "#### Retrieval Focus Contract\n\n"
        + (
            "\n".join(focus_rows) + "\n\n"
            if len(focus_rows) > 2
            else "未捕获检索焦点行。\n\n"
        )
        + "\n".join(rows)
        + "\n"
    )


def _render_graph_evidence(context: dict[str, Any]) -> str:
    evidence = context.get("evidence") or []
    if not evidence:
        return "### 证据\n\n未捕获图证据对象.\n"
    rows = [
        (
            "| Evidence ID | Source ID | Support Type | Support Strength | Specificity | "
            "Evaluator Mode | Summary | Limitations |"
        ),
        "|---|---|---|---:|---|---|---|---|",
    ]
    for item in evidence[:80]:
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(item.get("evidence_id", "")),
                    _cell(item.get("source_id", "")),
                    _cell(item.get("support_type", "")),
                    _cell(item.get("support_strength", "")),
                    _cell(item.get("specificity", "")),
                    _cell(item.get("evaluator_mode", "")),
                    _cell(item.get("summary", "")),
                    _cell(item.get("limitations", [])),
                ]
            )
            + " |"
        )
    note = (
        "`support_type` 表示证据支持类型，例如 direct_support 是直接支持，"
        "background_support 是背景支撑；`specificity` 表示证据粒度，例如政策文本、"
        "中标公告、统计发布或公司披露；`evaluator_mode` 记录证据评估方式。"
    )
    return "### 证据\n\n" + note + "\n\n" + "\n".join(rows) + "\n"


def _render_graph_claims(context: dict[str, Any]) -> str:
    claims = context.get("claims") or []
    if not claims:
        return "### 研究断言\n\n未捕获图断言对象.\n"
    rows = [
        (
            "| Claim ID | Supported | Required Source Family | Support Requirement | "
            "Evidence IDs | Text |"
        ),
        "|---|---|---|---|---|---|",
    ]
    for claim in claims[:80]:
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(claim.get("claim_id", "")),
                    _cell(claim.get("supported", "")),
                    _cell(claim.get("required_source_family", "")),
                    _cell(claim.get("support_requirement", "")),
                    _cell(", ".join(str(x) for x in claim.get("evidence_ids", []))),
                    _cell(claim.get("text", "")),
                ]
            )
            + " |"
        )
    note = (
        "`required_source_family` 表示该 claim 需要哪一类源才能成立；"
        "`support_requirement` 表示它需要哪一类证据粒度，例如 policy_statement "
        "或 procurement_award_notice。"
    )
    return "### 研究断言\n\n" + note + "\n\n" + "\n".join(rows) + "\n"


def _render_graph_claim_support_matrix(context: dict[str, Any]) -> str:
    matrix = context.get("claim_support_matrix") or []
    if not matrix:
        return "### 断言支撑矩阵\n\n未捕获断言支撑矩阵记录.\n"
    rows = [
        (
            "| Claim ID | Required Source Family | Family Matched | Evidence Count | "
            "Source Count | Avg Support Strength | Evidence Specificities | Source Families | "
            "Usage Roles |"
        ),
        "|---|---|---|---:|---:|---:|---|---|---|",
    ]
    for item in matrix[:80]:
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(item.get("claim_id", "")),
                    _cell(item.get("required_source_family", "")),
                    _cell(item.get("family_matched", "")),
                    _cell(item.get("evidence_count", "")),
                    _cell(item.get("source_count", "")),
                    _cell(item.get("avg_support_strength", "")),
                    _cell(", ".join(str(x) for x in item.get("evidence_specificities", []))),
                    _cell(", ".join(str(x) for x in item.get("source_families", []))),
                    _cell(", ".join(str(x) for x in item.get("usage_roles", []))),
                ]
            )
            + " |"
        )
    note = (
        "`claim_support_matrix` 是从数据库中的 graph business records 读回后生成的证据链视图。"
        "`family_matched` 表示该 claim 关联的 source 类型是否满足 `required_source_family`；"
        "`evidence_count` 和 `source_count` 分别表示关联证据数和来源数；"
        "`avg_support_strength` 是关联 evidence 的平均支持强度，用于调试 verifier/gate，"
        "不是 source 层 A/B/C/D 评级。"
    )
    return "### 断言支撑矩阵\n\n" + note + "\n\n" + "\n".join(rows) + "\n"


def _render_graph_claim_verifications(context: dict[str, Any]) -> str:
    verifications = context.get("claim_verifications") or []
    if not verifications:
        return "### 断言验证\n\n未捕获断言验证记录.\n"
    rows = [
        "| Claim ID | Support Status | Support Score | Evidence IDs | Source IDs | Notes |",
        "|---|---|---:|---|---|---|",
    ]
    for item in verifications[:80]:
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(item.get("claim_id", "")),
                    _cell(item.get("support_status", "")),
                    _cell(item.get("support_score", "")),
                    _cell(", ".join(str(x) for x in item.get("evidence_ids", []))),
                    _cell(", ".join(str(x) for x in item.get("source_ids", []))),
                    _cell(item.get("notes", [])),
                ]
            )
            + " |"
        )
    note = (
        "`support_status` 是 verifier 对 claim 的判断：supported 表示支持充分，"
        "partially_supported 表示部分支持，unsupported 表示当前证据不足，"
        "contradicted 表示存在反向证据。`support_score` 是针对 claim 的支持强度，"
        "不是 source 层评级分。"
    )
    return "### 断言验证\n\n" + note + "\n\n" + "\n".join(rows) + "\n"


def _render_graph_contract_diagnostics(context: dict[str, Any]) -> str:
    diagnostics = _collect_graph_contract_diagnostics(context)
    if not diagnostics:
        return "### 合约诊断\n\n未捕获合约诊断.\n"
    rows = [
        (
            "| Node | Contract Status | Used Fallback | Attempt Count | "
            "Normalizations | Input Mode | LLM Mode | Tooling Summary |"
        ),
        "|---|---|---|---:|---|---|---|---|",
    ]
    for item in diagnostics:
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(item.get("node_name", "")),
                    _cell(item.get("status", "")),
                    _cell(item.get("used_fallback", "")),
                    _cell(item.get("attempt_count", "")),
                    _cell(", ".join(str(x) for x in item.get("normalizations", []))),
                    _cell(item.get("input_mode", "")),
                    _cell(item.get("llm_mode", "")),
                    _cell(item.get("tooling_summary", "")),
                ]
            )
            + " |"
        )
    note = (
        "`contract diagnostics` 记录的是结构化输出合同在各节点上的通过方式。"
        "它用来区分原始输出直接通过、经过可解释规范化后通过，还是最终走了 fallback。"
    )
    details = ["### 合约诊断", "", note, "", "\n".join(rows), ""]
    for item in diagnostics:
        details.extend(_render_contract_diagnostic_detail(item))
    return "\n".join(details) + "\n"


def _render_graph_context_pack_table(context: dict[str, Any]) -> str:
    packs = context.get("context_packs") or []
    if not packs:
        return "未捕获上下文包。\n"
    rows = [
        (
            "| Context Pack ID | Node | Prompt Version | Token Estimate | "
            "Budget Status | Budget Overage | Included Fields | Removed Markers |"
        ),
        "|---|---|---|---:|---|---:|---|---|",
    ]
    for pack in packs[:120]:
        sanitization = pack.get("sanitization_summary") or {}
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(pack.get("context_pack_id", "")),
                    _cell(pack.get("node_name", "")),
                    _cell(pack.get("prompt_version", "")),
                    _cell(pack.get("token_estimate", "")),
                    _cell(pack.get("budget_status", "")),
                    _cell(pack.get("budget_overage_tokens", "")),
                    _cell(", ".join(str(x) for x in pack.get("included_fields", []))),
                    _cell(", ".join(str(x) for x in sanitization.get("removed_markers", []))),
                ]
            )
            + " |"
        )
    return "\n".join(rows) + "\n"


def _render_graph_context_pack_details(context: dict[str, Any]) -> str:
    packs = context.get("context_packs") or []
    if not packs:
        return ""
    lines = ["### 上下文包详情", ""]
    for pack in packs[:40]:
        node = pack.get("node_name", "?")
        agent = pack.get("agent_name", "?")
        io_snap = pack.get("io_snapshot")

        summary = f"#### {pack.get('context_pack_id', '')} / {node} ({agent})"
        lines.extend([summary, ""])

        # Basic metadata
        lines.extend([
            f"- 提示词版本: {_inline(pack.get('prompt_version', ''))}",
            f"- 输入哈希: `{pack.get('input_hash', '')}`",
            f"- Token估算: `{pack.get('token_estimate', '')}` (预算: `{pack.get('context_budget_tokens', '')}`, 状态: `{pack.get('budget_status', '')}`)",
            "",
        ])

        # ── Phase C: IO Snapshot with details blocks ──
        if io_snap:
            lines.append("<details>")
            before_count = len(io_snap.get("state_before_keys", []))
            after_count = len(io_snap.get("state_after_keys", []))
            lines.append(f"<summary>📋 IO 快照 — 输入 {before_count} 键 / 输出 {after_count} 键</summary>")
            lines.append("")

            if "state_before_summary" in io_snap:
                lines.append("**输入状态**")
                lines.append("| 字段 | 值 |")
                lines.append("|---|---|")
                for k, v in sorted(io_snap["state_before_summary"].items())[:20]:
                    lines.append(f"| `{k}` | {_cell(str(v)[:120])} |")
                lines.append("")

            if "state_after_summary" in io_snap:
                lines.append("**输出状态**")
                lines.append("| 字段 | 值 |")
                lines.append("|---|---|")
                for k, v in sorted(io_snap["state_after_summary"].items())[:20]:
                    lines.append(f"| `{k}` | {_cell(str(v)[:120])} |")
                lines.append("")

            if "state_before_full" in io_snap:
                lines.append("<details>")
                lines.append("<summary>完整输入 (JSON)</summary>")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(io_snap["state_before_full"], ensure_ascii=False, indent=2)[:20000])
                lines.append("```")
                lines.append("</details>")
                lines.append("")

            if "state_after_full" in io_snap:
                lines.append("<details>")
                lines.append("<summary>完整输出 (JSON)</summary>")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(io_snap["state_after_full"], ensure_ascii=False, indent=2)[:20000])
                lines.append("```")
                lines.append("</details>")
                lines.append("")

            lines.append("</details>")
            lines.append("")
        else:
            lines.append("*无 IO 快照*")
            lines.append("")

    return "\n".join(lines) + "\n"


def _render_graph_tool_traces(context: dict[str, Any]) -> str:
    traces = context.get("tool_traces") or []
    if not traces:
        return "未捕获工具追踪。\n"
    rows = [
        "| Node | Tool | Status | Reason Code | Args Summary | Result Summary |",
        "|---|---|---|---|---|---|",
    ]
    for trace in traces[:160]:
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(trace.get("node_name", "")),
                    _cell(trace.get("tool_name", "")),
                    _cell(trace.get("status", "")),
                    _cell(trace.get("reason_code", "")),
                    _cell(trace.get("args_summary", {})),
                    _cell(trace.get("result_summary", {})),
                ]
            )
            + " |"
        )
    note = (
        "`tool_traces` 记录的是节点通过 tooling harness 发起的工具调用。"
        "它会显示该调用是否被放行、拒绝原因代码，以及参数和结果的摘要。"
    )
    return note + "\n\n" + "\n".join(rows) + "\n"


def _render_graph_final_report(context: dict[str, Any]) -> str:
    report = context.get("final_report") or {}
    if not report:
        return "未捕获最终报告预览.\n"
    return _fence_json(report, limit=4000) + "\n"


def _render_graph_human_review(context: dict[str, Any]) -> str:
    human_review = context.get("human_review") or {}
    if not human_review:
        return "未捕获人工复核状态.\n"
    return _fence_json(human_review, limit=4000) + "\n"


def _collect_graph_contract_diagnostics(context: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for step in context.get("node_steps") or []:
        output_summary = step.get("output_summary") or {}
        contract_meta = output_summary.get("contract_meta") or {}
        if not isinstance(contract_meta, dict):
            continue
        for node_name, meta in contract_meta.items():
            if not isinstance(meta, dict):
                continue
            attempts = meta.get("attempts") or []
            normalizations: list[str] = []
            for attempt in attempts:
                if isinstance(attempt, dict):
                    normalizations.extend(
                        str(value) for value in list(attempt.get("normalizations", [])) if value
                    )
            tooling = meta.get("tooling") or {}
            diagnostics.append(
                {
                    "node_name": node_name,
                    "status": meta.get("status", ""),
                    "used_fallback": meta.get("used_fallback", False),
                    "attempt_count": meta.get("attempt_count", 0),
                    "normalizations": _dedupe_preserve_order(normalizations),
                    "input_mode": meta.get("input_mode", ""),
                    "llm_mode": meta.get("llm_mode", ""),
                    "tooling_summary": _summarize_tooling(tooling),
                    "meta": meta,
                }
            )
    return diagnostics


def _render_contract_diagnostic_detail(item: dict[str, Any]) -> list[str]:
    lines = [
        f"#### Contract Detail / {_cell(item.get('node_name', ''))}",
        "",
        _fence_json(item.get("meta", {}), limit=3500),
        "",
    ]
    return lines


def _summarize_tooling(tooling: Any) -> str:
    if not isinstance(tooling, dict) or not tooling:
        return ""
    parts: list[str] = []
    for key in (
        "evidence_bundle_tool_status",
        "outline_tool_status",
        "claim_support_matrix_tool_status",
        "source_bundle_tool_status",
        "compose_final_report_status",
        "revision_request_status",
        "replan_request_status",
        "final_report_tool_status",
        "evidence_bundle_status",
    ):
        value = tooling.get(key)
        if value:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _render_graph_glossary() -> str:
    lines = [
        (
            "- `context_pack_id`: 当前节点输入包的审计 ID。"
            "用于区分不同节点、不同轮次到底用了哪一份上下文。"
        ),
        (
            "- `prompt_version`: 当前节点使用的输入契约版本。"
            "它告诉你这个节点是按哪一版提示词/结构化协议在运行。"
        ),
        (
            "- `input_hash`: 输入指纹哈希。它不是原文内容本身，"
            "而是为了比较两次节点运行是不是吃了同一份有效上下文。"
        ),
        (
            "- `included_source_ids`: 这个节点在执行时可见的 source 对象列表。"
            "它回答“这个 agent 当时到底看到了哪些源”。"
        ),
        (
            "- `included_evidence_ids`: 这个节点可见的 evidence 对象列表。"
            "它回答“这个 agent 当时到底用到了哪些证据片段”。"
        ),
        (
            "- `included_claim_ids`: 这个节点可见的 claim 对象列表。"
            "它回答“这个节点是在处理哪些可验证断言”。"
        ),
        (
            "- `included_issue_ids`: 这个节点可见的 review issue 列表。"
            "它回答“这个节点是否带着上一轮审稿问题继续工作”。"
        ),
        (
            "- `included_fields`: 当前上下文包暴露给该节点的状态字段类别，"
            "例如 `sources`、`evidence`、`claims`、`review_issues`。"
        ),
        (
            "- `token_estimate`: 粗略 token 估算，不是 provider 返回的精确 token。"
            "它用来观察某个节点的上下文是否在不断膨胀。"
        ),
        (
            "- `sanitization_summary`: 清洗摘要。它记录清洗前后字符数、"
            "哪些页面噪音标记被移除了，以及有多少 source 已经具备 clean text。"
        ),
        (
            "- `removed_markers`: 被识别并移除的页面噪音标记，"
            "例如 `[首页]`、`打印`、`收藏`、`javascript:void(0)`。"
            "这些不是研究证据，而是导航或页面 chrome。"
        ),
        (
            "- `node_steps`: graph 中每个节点的可见执行记录。"
            "它告诉你节点名、agent 名、状态和该节点输出了什么摘要。"
        ),
        (
            "- `tool_traces`: 节点通过 tooling harness 发起的工具调用轨迹。"
            "它用于审计节点申请了什么工具、是否被放行，以及工具结果的摘要。"
        ),
    ]
    return "\n".join(lines) + "\n"


def _render_search_rounds(context: dict[str, Any]) -> str:
    round_log = context.get("round_log") or []
    search_plan = context.get("search_plan") or {}
    plan_rounds = search_plan.get("rounds") or []
    rows = [
        "| Round | Objective | Search Phrases | Domains | Status | Sources Found |",
        "|---:|---|---|---|---|---:|",
    ]
    if round_log:
        for item in round_log:
            rows.append(
                "| "
                + " | ".join(
                    [
                        _cell(item.get("round", "")),
                        _cell(item.get("objective", "")),
                        _cell(", ".join(str(x) for x in item.get("phrases", [])[:8])),
                        _cell(", ".join(str(x) for x in item.get("domains", [])[:8])),
                        _cell(item.get("status", "")),
                        _cell(item.get("sources_found", 0)),
                    ]
                )
                + " |"
            )
    elif plan_rounds:
        for item in plan_rounds:
            rows.append(
                "| "
                + " | ".join(
                    [
                        _cell(item.get("round_number", "")),
                        _cell(item.get("objective", "")),
                        _cell(", ".join(str(x) for x in item.get("search_phrases", [])[:8])),
                        _cell(", ".join(str(x) for x in item.get("include_domains", [])[:8])),
                        "planned_not_executed",
                        "0",
                    ]
                )
                + " |"
            )
    else:
        return "### 搜索轮次\n\n未捕获搜索轮次详情.\n"
    return "### 搜索轮次\n\n" + "\n".join(rows) + "\n"


def _render_source_candidates(context: dict[str, Any]) -> str:
    sources = context.get("collected_sources") or []
    if not sources:
        return "### 来源候选 By Search\n\nNo source candidates were collected.\n"
    rows = [
        (
            "| Round | Objective | Discovered By Phrase | Published Date | "
            "Title | URL | Domain | Discovery Score |"
        ),
        "|---:|---|---|---|---|---|---|---:|",
    ]
    for source in sources[:80]:
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(source.get("round", "")),
                    _cell(source.get("round_objective", "")),
                    _cell(source.get("discovered_by_phrase", "")),
                    _cell(source.get("published_date", "")),
                    _cell(source.get("title", "")),
                    _link_cell(source.get("url", "")),
                    _cell(source.get("domain", "")),
                    _cell(source.get("score", "")),
                ]
            )
            + " |"
        )
    return "### 来源候选 By Search\n\n" + "\n".join(rows) + "\n"


def _render_source_assessments(
    report: DeepResearchReport,
    context: dict[str, Any],
) -> str:
    evaluator_modes = context.get("source_evaluator_modes") or {}
    if not report.source_assessments:
        return "### Final Source Selection And Ratings\n\nNo sources were assessed.\n"
    rows = [
        "| Selected | Tier | Legacy Avg Score | Evaluator Mode | Title | URL | Usage Note |",
        "|---|---|---:|---|---|---|---|",
    ]
    for source in report.source_assessments[:80]:
        mode = evaluator_modes.get(source.url, "unknown")
        score = round(
            (
                source.authority_score
                + source.proximity_score
                + source.timeliness_score
                + source.verifiability_score
                + source.relevance_score
            )
            / 5,
            3,
        )
        rows.append(
            "| "
            + " | ".join(
                [
                    "yes" if source.overall_usable else "no",
                    _cell(source.tier),
                    _cell(score),
                    _cell(mode),
                    _cell(source.title),
                    _link_cell(source.url),
                    _cell(source.usage_note),
                ]
            )
            + " |"
        )
    note = (
        "Legacy Avg Score is the old five-field average "
        "(authority/proximity/timeliness/verifiability/relevance). "
        "It is kept for compatibility; Source Quality v2 below is the new "
        "auditable source-layer view."
    )
    return (
        "### Final Source Selection And Ratings\n\n"
        + note
        + "\n\n"
        + "\n".join(rows)
        + "\n"
    )


def _render_evidence(report: DeepResearchReport) -> str:
    if not report.evidence_chain:
        return "### Selected Evidence\n\nNo evidence items were selected.\n"
    rows = [
        "| Evidence ID | Stage | Confidence | Verification | Claim | Source URLs |",
        "|---|---|---|---|---|---|",
    ]
    for item in report.evidence_chain[:80]:
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(item.evidence_id),
                    _cell(item.stage),
                    _cell(item.confidence),
                    _cell(item.verification_status),
                    _cell(item.claim),
                    _cell(", ".join(item.source_urls[:5])),
                ]
            )
            + " |"
        )
    return "### Selected Evidence\n\n" + "\n".join(rows) + "\n"


def _render_agent_pipeline(report: DeepResearchReport, context: dict[str, Any]) -> str:
    debate = context.get("debate") or {}
    counter_evidence = context.get("counter_evidence") or []
    rows = [
        "| Step | Agent/System | Status | Visible Work Record |",
        "|---|---|---|---|",
        "| query_understanding | DeepResearchAgent | completed | "
        + _cell("normalized query and research dimensions captured")
        + " |",
        "| multi_round_search | Source Hunter | completed | "
        + _cell(f"{report.search_rounds_executed} rounds executed")
        + " |",
        "| source_tiering | Evidence Judge / Source Tier | completed | "
        + _cell(f"{len(report.source_assessments)} sources assessed")
        + " |",
        "| evidence_chain | Parser/Structurer | completed | "
        + _cell(f"{len(report.evidence_chain)} evidence items selected")
        + " |",
        "| thesis_builder | Thesis Builder | "
        + _cell("completed" if debate.get("theses") else "not_captured_or_skipped")
        + " | "
        + _cell(_summarize_count(debate.get("theses"), "theses"))
        + " |",
        "| opponent | Opponent | "
        + _cell("completed" if debate.get("objections") else "not_captured_or_skipped")
        + " | "
        + _cell(_summarize_count(debate.get("objections"), "objections"))
        + " |",
        "| evidence_judge | Evidence Judge | "
        + _cell("completed" if debate.get("evidence_judge") else "not_captured_or_skipped")
        + " | "
        + _cell(str((debate.get("evidence_judge") or {}).get("overall_label", "")))
        + " |",
        "| risk_analyst | Risk Analyst | "
        + _cell("completed" if debate.get("risks") else "not_captured_or_skipped")
        + " | "
        + _cell(_summarize_count(debate.get("risks"), "risks"))
        + " |",
        "| counter_evidence_search | Source Hunter | completed | "
        + _cell(f"{len(counter_evidence)} counter-evidence items")
        + " |",
        "| report_assembly | Supervisor | completed | "
        + _cell(report.executive_summary[:240])
        + " |",
    ]
    return "### 代理流水线 Records\n\n" + "\n".join(rows) + "\n"


def _render_detailed_agent_trace(context: dict[str, Any]) -> str:
    events = context.get("trace_events") or []
    if not events:
        return "### 代理追踪详情\n\n未捕获追踪事件详情.\n"

    summary_rows = [
        "| Event | Step | Agent | Type | Status | Duration | Output Summary |",
        "|---:|---|---|---|---|---:|---|",
    ]
    for event in events[:120]:
        metadata = event.get("metadata") or {}
        duration = metadata.get("duration_ms") or metadata.get("response_ms") or ""
        summary_rows.append(
            "| "
            + " | ".join(
                [
                    _cell(event.get("event_id", "")),
                    _cell(event.get("step", "")),
                    _cell(event.get("agent", "")),
                    _cell(event.get("event_type", "")),
                    _cell(event.get("status", "")),
                    _cell(duration),
                    _cell(_trace_output_summary(event)),
                ]
            )
            + " |"
        )

    details = ["### 代理追踪详情", "", "\n".join(summary_rows), ""]
    for event in events[:80]:
        details.extend(_render_trace_event_detail(event))
    if len(events) > 80:
        details.append(f"\nTrace truncated in Markdown: {len(events) - 80} more events captured.")
    return "\n".join(details) + "\n"


def _render_trace_event_detail(event: dict[str, Any]) -> list[str]:
    event_id = _cell(event.get("event_id", ""))
    step = _cell(event.get("step", ""))
    agent = _cell(event.get("agent", ""))
    event_type = _cell(event.get("event_type", ""))
    status = _cell(event.get("status", ""))
    lines = [
        f"#### Trace Event {event_id}: {step} / {agent} / {event_type}",
        "",
        f"- Status: `{status}`",
    ]
    if event.get("metadata"):
        lines.extend(["- Metadata:", _fence_json(event.get("metadata"))])
    if event.get("inputs"):
        lines.extend(["- Inputs:", _fence_json(event.get("inputs"))])
    if event.get("outputs"):
        lines.extend(["- Outputs:", _fence_json(event.get("outputs"))])
    if event.get("error"):
        lines.extend(["- Error:", _fence_text(event.get("error"))])
    lines.append("")
    return lines


def _trace_output_summary(event: dict[str, Any]) -> str:
    outputs = event.get("outputs") or {}
    if not isinstance(outputs, dict):
        return str(outputs)[:180]
    if "result_count" in outputs:
        return f"{outputs.get('result_count')} search results"
    if "json_data" in outputs:
        data = outputs.get("json_data") or {}
        if isinstance(data, dict):
            return "json keys: " + ", ".join(str(key) for key in list(data.keys())[:6])
        return "json output captured"
    if "source_count" in outputs:
        return f"{outputs.get('source_count')} sources"
    if "evidence_count" in outputs:
        return f"{outputs.get('evidence_count')} evidence items"
    if "overall_confidence" in outputs:
        return f"confidence={outputs.get('overall_confidence')}"
    return _cell(outputs)


def _fence_json(value: Any, *, limit: int = 6000) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2)
    except TypeError:
        text = str(value)
    return "```json\n" + _truncate_block(text, limit) + "\n```"


def _fence_text(value: Any, *, limit: int = 3000) -> str:
    return "```text\n" + _truncate_block(str(value), limit) + "\n```"


def _truncate_block(text: str, limit: int) -> str:
    text = text.replace("```", "` ` `")
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


def _render_content_assets(context: dict[str, Any]) -> str:
    assets = context.get("content_assets") or []
    if not assets:
        return (
            "### Produced Content Assets\n\n"
            "No content assets were attached to this Deep Research V2 dossier. "
            "The section is reserved for the content-generation integration slice.\n"
        )
    rows = [
        "| Asset ID | Type | Title | Status | Generation Record |",
        "|---|---|---|---|---|",
    ]
    for asset in assets:
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(asset.get("asset_id", "")),
                    _cell(asset.get("content_type", "")),
                    _cell(asset.get("title", "")),
                    _cell(asset.get("status", "")),
                    _cell(asset.get("generation_record", "")),
                ]
            )
            + " |"
        )
    return "### Produced Content Assets\n\n" + "\n".join(rows) + "\n"


def _summarize_count(value: Any, label: str) -> str:
    if isinstance(value, list):
        return f"{len(value)} {label}"
    return f"0 {label}"


def _inline(value: Any) -> str:
    return str(value).replace("\n", " ").strip()


def _cell(value: Any) -> str:
    text = _inline(value)
    text = text.replace("|", "\\|")
    if len(text) > 180:
        return text[:177] + "..."
    return text


def _link_cell(url: Any) -> str:
    text = _cell(url)
    return text or ""
