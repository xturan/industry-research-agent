# Subsystem B: Editor1 LLM 报告撰写 + 内容深度升级 — Design Spec

Status: approved | Date: 2026-06-18

## Objective

将 Editor1 从程序模板拼段落升级为 LLM 直接撰写中文深度研报。
同时解决 claim 太少（5 个）、报告太短（2600 字）的问题。

## Architecture: Three Changes

### Part 1 — Editor1 始终 LLM

**当前**：bytecode editor1 → 成功用 bytecode / 失败用模板+LLM 混合（模板为主）

**改为**：直接进 LLM 撰写 → 失败才用模板兜底

改动 `editor1_draft_provider_backed`（`real_nodes.py:987-1006`）：
- 移除 `_impl.editor1_draft_provider_backed(state, ...)` 调用
- 直接调用 `_generate_real_editor1_draft(state=state)`
- Fallback 保留（LLM 输出 < 1500 chars 时回退模板）

### Part 2 — Claim 数量 + 质量

**2a. build_claims wrapper**（`real_nodes.py:871`）：

字节码 `_impl.build_claims_provider_backed` 产出 claims。
若 `len(claims) < 8`，调用 LLM 从 evidence 列表挖掘更多 claim：

Prompt 要求：
```
从以下 evidence 列表中生成额外的研究断言(claims)：
- 每个 evidence 至少对应 1 个 claim
- 不同 source_family 产生不同类型（official_policy→政策断言, company_disclosure→财务/业务断言）
- 每个 claim: claim_id, text(中文), claim_family, evidence_ids, required_source_family
- 避免与已有 claim 重复
输出 JSON 数组，追加到 existing_claims
```

**2b. Editor1 深度分析**：

LLM 撰写 prompt 要求对每个 claim 做分析性叙述：
- 不只是罗列证据 → 解释"这意味着什么"
- 发现 claim 间关联（政策→项目的因果链）
- 标注证据缺口
- 矛盾 evidence 做对比

### Part 3 — 完整研报结构

**目标**：5000-8000 字，8-10 section，标准研报结构。

**LLM Prompt 要求的 section 结构**：

| Section | 内容要求 | 字数 |
|---------|---------|------|
| 标题 + 执行摘要 | query 主题 + 整体结论 + 关键发现 3-5 条 | 300-500 |
| 方法与口径 | 来源类型、时间/地域范围、事实与推断边界 | 200-400 |
| 政策维度 | 分析性叙述 + evidence 引用，解释政策含义 | 500-800 |
| 地方落地 | 地方执行信号 + 证据分析 | 400-700 |
| 项目执行 | 具体项目/招标/落地案例 | 400-700 |
| 公司披露 | 上市公司相关披露 + 财务/业务分析 | 400-700 |
| 行业数据 | 统计数据 + 趋势分析 | 300-500 |
| 风险与不确定性 | 证据局限、未覆盖面向、推断风险 | 300-500 |
| 结论与展望 | 综合判断 + 后续研究方向 | 200-400 |
| 来源说明 | 来源表格（已有） | 自动生成 |

**LLM Prompt 核心要求**：

```
你是资深行业研究员。基于提供的 claims、evidence、sources，撰写一份中文深度研究报告。

要求：
1. 完整的研报结构（见上述 section 列表）
2. 每个 claim 必须有分析性叙述——不只是"证据支持了某某"，要解释为什么重要、意味着什么
3. 发现 claim 间的逻辑关联（如政策如何推动项目落地）
4. 明确标注证据局限性（如果某个 claim 只有一个 evidence，标注"单源支撑，建议交叉验证"）
5. 如果有多个 evidence 支持同一结论，做综合判断而非简单罗列
6. 使用中文撰写，专业但不晦涩，让非专业读者也能理解
7. 报告长度 5000-8000 字

输入材料：
- Query: {query}
- Claims: {claims_json}
- Evidence: {evidence_json}
- Sources: {sources_json}

输出：纯 Markdown 文本（不是 JSON），直接可发布。
```

## Protected Contracts

- 不修改 legacy `/deep-research/analyze` 和 `/research/analyze`
- `graph_v1` 保持 opt-in
- `response.json` 结构不变（`report_markdown` 字段内容升级但字段名不变）
- 已有 gate/editor2/human_review 逻辑不变
- build_claims 的 claim 追加不修改字节码产出的原有 claims

## Fallback / Safety

- LLM 调用失败 → 回退 `_build_minimal_draft_from_claims`（模板兜底，≥1500 chars）
- LLM 输出 < 1500 chars → 视为失败，回退模板
- build_claims LLM 失败 → 保持字节码原始 claims（即使 < 8 个）
- 所有 LLM 调用的 max_tokens 和 timeout 基于 settings 配置

## Validation

```powershell
# Editor1 tests
pytest -q tests/test_research_harness_graph.py -k "editor1" -v

# Build claims tests
pytest -q tests/test_research_harness_graph.py -k "build_claims" -v

# Full regression
pytest -q tests/test_research_harness_graph.py -k "editor2 or chief_gate or human_review" -v

# Live smoke
python scripts/graph_provider_backed_smoke.py --query "2025年广东人形机器人产业政策与项目落地证据" --max-rounds 2 --output-dir "data/tmp/subsystem_b_smoke/case1" --env-file .env --reset
python scripts/report_quality_inspect.py --response "data/tmp/subsystem_b_smoke/case1/response.json" --summary "data/tmp/subsystem_b_smoke/case1/summary.json"
```
