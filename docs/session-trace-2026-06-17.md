# 工作会话 Trace — 2026-06-17

## 勘误状态

Status: superseded_by_remediation_plan

本文件保留为历史 trace，但不能作为
`.agent/PLANS/deep-research-readable-report-quality-v2.md` 已完成的证明。
后续审阅复跑 `scripts/report_quality_inspect.py` 后确认：

- `data/tmp/phase6_smoke/case1_hefei` 到 `case4_coal` 四个 live artifact 均仍被判定为 `workflow_pass_product_fail`。
- `case1_hefei` 仍出现 `decision=PASS` 与 `gate_obligation_gap_count=1` 同时存在的问题。
- 因此，正确状态是“有明显改善，但未达产品级完成”。

当前接管计划：

- `.agent/PLANS/deep-research-readable-report-remediation-v1.md`

阅读规则：

- 下文 Phase 记录保留原始会话脉络，但其中“已完成”“正确阻断”“无 active PLAN”等结论已被本勘误覆盖。
- 当前可信状态以 `.agent/STATUS.md` 和 `.agent/PLANS/deep-research-readable-report-remediation-v1.md` 为准。

## 概述

本文件记录了 2026 年 6 月 17 日一次 Deep Research 报告质量升级会话。
从"workflow 能输出 Markdown"的基线出发，本轮确实形成了质量检查工具、
更长的 Markdown 结构和若干 live smoke 产物；但后续复核表明，本轮尚未
将 graph_v1 升级为"能够稳定交付产品级中文深度研究 Markdown 报告"的可验收系统。

**PLAN**: `.agent/PLANS/deep-research-readable-report-quality-v2.md`  
**PRD**: `docs/prd/deep_research_readable_report_prd_v0_1.md`

## 基线（改造前）

```
数据来源: data/tmp/final_fix_smoke/case1

workflow:       status=succeeded, decision=PASS
report_markdown_chars: 4763
business_body_chars: 867 (18%)
audit_appendix_start_index: 869
sections_found: 3/6 (仅 executive_summary, policy_basis, disclosure)
gate_obligation_gap_count: 1 (obl_policy_primary 未覆盖但仍 PASS)
support_strength: 全部 0.0
limitations: 碎字(单字符拆分) + 截断
p0_review_issue_count: 10
over_budget_context_packs: 10
checks_passed: 1/9

判定: workflow_pass_product_fail
```

## Phase 1: Baseline Quality Harness

**目标**: 建立可复跑的报告质量检查工具，明确当前基线为 `workflow_pass_product_fail`。

**新建文件**:
- `scripts/report_quality_inspect.py` — 9 指标质量检查 harness
- `tests/test_report_quality_inspect.py` — 11 个测试
- `scripts/__init__.py`

**9 项检查指标**:
1. `business_body_length` — 正文字符数 (阈值 ≥1500)
2. `business_body_ratio` — 正文占比 (阈值 ≥35%)
3. `required_sections` — 必需章节覆盖 (缺失 ≤2)
4. `obligation_gaps` — obligation 缺口 (阈值 0)
5. `obligation_coverage_detail` — 每个 obligation 的覆盖状态
6. `source_family_mismatch` — 源族错配 (阈值 0)
7. `p0_issues` — P0 审稿问题 (阈值 0)
8. `limitations_truncated` — 限制截断 (阈值 ≤3)
9. `over_budget_packs` — 超预算 context pack (阈值 ≤5)

**验证**:
```
ruff: All checks passed
pytest: 11 passed
real baseline: workflow_pass_product_fail (1/9 checks pass)
```

## Phase 2: Gate Quality Contract

**目标**: 使 Chief Gate 消费产品质量阻断因素。Gate 不能再在 obligation 未覆盖时盲 PASS。

**修改文件**: `packages/research_harness/real_nodes.py`

**5 个 gate 阻断规则**:

| 阻断规则 | 条件 | Gate 输出 | 中文 reason |
|---------|------|----------|------------|
| Obligation 未覆盖 | required_source_family 缺证据 | ADD_EVIDENCE | "obligation 未覆盖 — 必须补充对应源族证据后才能通过" |
| Source-family 错配 | policy claim 仅由 disclosure 支撑 | ADD_EVIDENCE | "政策 claim 仅由 company_disclosure 支撑, 不可通过" |
| P0 审稿问题 | blocker 或 section_role mismatch | REVIEW_RISK | "P0 问题必须被 Editor2/verifier 解决后才能继续" |
| 同域过度集中 | 单域名占 ≥3 个源 | REVIEW_RISK | "N个域名占源总数比例过高, 可能缺乏视角多样性" |
| 地域精度不足 | location query 但本地源 <30% | ADD_EVIDENCE | "地域精度不足, 需补充本地源" |

**关键设计**: 阻断规则只在 bytecode gate 要 PASS/REVISE_TEXT 时才生效。HUMAN_REVIEW 保持最高优先级。

**验证**:
```
ruff: All checks passed
gate tests: 4/5 pass (1 pre-existing Python 3.13 StopIteration issue)
live smoke: historical note claimed the gate prevented blind PASS, but later
review found `case1_hefei` still had `decision=PASS` with
`gate_obligation_gap_count=1`
```

**勘误后的效果判断**: `obl_policy_primary: covered=False` 仍可能 PASS。该问题未关闭，已转入
`.agent/PLANS/deep-research-readable-report-remediation-v1.md` Phase 2。

## Phase 3: Evidence And Claim Quality Upgrade

**目标**: 让 evidence 有真实支撑强度，claims 有类型分类和置信标记。

**修改文件**: `packages/research_harness/real_nodes.py`

**Enrich evidence semantics** (`_enrich_evidence_semantics`):
- `support_strength` 从 tier(0.15-0.8) + support_type(direct+0.15) + source_family_match(+0.1) + summary_length(+0.05-0.1) 计算
- 修复 limitations 碎字: `list("该政策为内蒙古")` → `["该政策为内蒙古"]`
- 检测截断: 中文 <20 字且无句号 → 标记 `…(截断)`
- Query relevance scoring with family boost

**Enrich claim semantics** (`_enrich_claim_semantics`):
- `claim_type` 自动分类: fact / interpretation / risk（基于文本关键词匹配）
- `_evidence_quality.single_source_risk` — 标记单源支撑的 claim
- `_low_confidence` — 低置信标记（avg_strength<0.3 或 单源+强度<0.6）
- `_evidence_quality.linked_source_count` — 独立来源计数
- `limitations` 自动注入低置信原因

**验证**:
```
ruff: All checks passed
evidence/claim tests: 6/7 pass (1 pre-existing verifier test)
live smoke: support_strength 从 0.0 变为 0.15-0.95
```

## Phase 4: Editor1 Report Body Composer

**目标**: 让 Editor1 从 claim-paragraph 映射变成真正的报告体写作。

**修改文件**: `packages/research_harness/real_nodes.py`

**新增函数**:
- `_build_minimal_draft_from_claims` 重写 — 生成完整报告结构
- `_merge_llm_into_structured_report` — LLM 输出与结构模板合并

**报告结构**:
```
# {query}
## 执行摘要          ← 报告概述、来源统计、覆盖源类型
## 方法与口径         ← 公开数据源说明
## {维度章节}         ← 按 claim_family 分组，含证据溯源和支撑强度
## 风险与不确定性     ← 低置信 claim，单源限制
## 结论与后续研究方向  ← 证据覆盖总结，未覆盖维度建议
## 来源说明           ← 完整的来源表(ID/标题/源族/URL)
```

**验证**:
```
ruff: All checks passed
editor1 tests: 3/3 pass
live smoke: business_body_chars 867→2473 (+185%), ratio 18%→33%
```

## Phase 5: Source And Search Acceptance Loop

**目标**: 源审阅可见化，同域检测，地域精度门禁。

**修改文件**: `packages/research_harness/real_nodes.py`

**新增 gate 规则**:
- 同域过度集中检测: `domain_counts` → ≥3 sources from same domain → REVIEW_RISK
- 地域精度门禁: location query + local_precision<30% → ADD_EVIDENCE

**报告增强**:
- 来源说明表增加源族/可信度/使用方式列

**验证**:
```
ruff: All checks passed
gate tests: 4/5 pass
```

## Phase 6: Live Product Validation Matrix

**目标**: 4 个金标准 case 的 live 对比，不只看 workflow 状态，对比报告质量。

**4 个 Case 结果**:

| Case | Query | Decision | Body Chars | Ratio | Sections |
|------|-------|----------|-----------|-------|----------|
| 1 合肥低空经济 | 2025年合肥低空经济上市公司年报披露与地方政策项目公示 | PASS | 2613 | 0.341 | 6/6 |
| 2 广东人形机器人 | 2025年广东人形机器人产业政策与项目落地证据 | PASS | 2710 | 0.462 | 6/6 |
| 3 新能源汽车 | 2025年中国新能源汽车产业政策支持与产业链证据 | PASS | 2770 | 0.351 | 5/6 |
| 4 神木煤化工 | 2025年陕西神木煤炭与煤化工产业扩展空间与政策证据 | PASS | 2155 | 0.315 | 5/6 |

4 case average: body=2562 chars, ratio=37%, sections=5.5/6

勘误：上表的 `PASS` 是 workflow decision，不是 product-quality pass。复跑
`scripts/report_quality_inspect.py` 后，四个 case 均仍为
`workflow_pass_product_fail`。

## Phase 7: Documentation And Handoff

**更新文件**:
- `.agent/PLANS/deep-research-readable-report-quality-v2.md` — 完整 progress + before/after + promotion recommendation
- `.agent/STATUS.md` — 历史记录当时写作口径；后续已改为 remediation PLAN active
- `docs/session-trace-2026-06-17.md` — 本文件

**Promotion Recommendation**: `keep_opt_in_record_blockers`

## 改造前后效果对比

| 指标 | 改造前 | 改造后 (4-case avg) | 变化 |
|------|--------|---------------------|------|
| business_body_chars | 867 | 2562 | +195% |
| business_body_ratio | 0.182 | 0.367 | +102% |
| required_sections | 3/6 | 5.5/6 | +2.5 sections |
| gate blind PASS | YES | case1 仍存在 | 未修复，remediation PLAN Phase 2 继续处理 |
| support_strength | 0.0 | 0.15-0.95 | 真实计算 |
| limitations | 碎字 | 仍有截断风险 | 未完全修复，需继续验证 |
| source text | 2400 chars | 3236-11411 chars | 突破 2400 上限 |
| chunk retrieval | 0 chunks | 43 chunks | 激活 |
| checks passed | 1/9 | 3-8/9 | 有改善但仍为 product fail |

## 示例: 改造前后同一 Case 对比

### 改造前 (final_fix_smoke/case1)

```
report_markdown: 4763 chars (正文 867, 附录 3896)
body_ratio: 0.182
sections: Executive Summary, Policy Basis, Disclosure (3/6)
gate: PASS despite obl_policy_primary uncovered
support_strength: 0.0

报告内容示例:
"## Policy Basis\n\n**国家层面已将低空经济写入政府工作报告..."
"## Company Disclosure\n\n**四创电子2025年年报披露..."
"---\n\n## Audit Appendix\n## Executive Summary\n..."
```

### 改造后 (phase6 case1_hefei)

```
report_markdown: 7664 chars (正文 2613, 附录 5051)
body_ratio: 0.341
sections: 执行摘要, 方法与口径, 政策依据, 企业披露, 风险与不确定性, 结论与后续研究方向, 来源说明 (6/6)
gate: still product-failing; case1 keeps decision=PASS despite obligation gap
support_strength: 0.15-0.95

报告内容示例:
"# 2025年合肥低空经济...
## 执行摘要
本报告针对「...」进行了证据驱动的研究分析。共检索并筛选 N 个来源...

## 方法与口径
本报告基于公开可获取的官方政策文件、上市公司年报...

## 政策依据
**安徽省发布了省级低空经济政策文件...**
  - 支撑强度: 高
  - 证据 [ev_005] (强度:0.95): ...

## 企业披露
**四创电子2025年年报披露...**
  - 支撑强度: 高

## 风险与不确定性
- **待验证**: ...

## 结论与后续研究方向
基于当前证据, 共 X/Y 条研究断言获得证据支撑。

## 来源说明
| 来源ID | 标题 | 源族 | 可信度 | URL |
```

## 改动文件清单 (12 个文件)

| 文件 | 操作 | 行数估计 | 关联 Phase |
|------|------|---------|-----------|
| `packages/research_harness/real_nodes.py` | 修改 | +600 | Phase 2,3,4,5 |
| `packages/research_harness/nodes.py` | 修改 | +50 | Phase 3(chunk) |
| `packages/research_harness/tooling/llm_agents.py` | 修改 | +80 | Phase 3(editor1) |
| `packages/research_harness/tooling/executor.py` | 修改 | +60 | Phase 3(editor1) |
| `packages/research_harness/plan_semantic.py` | 修改 | +50 | Phase 3(caliber) |
| `packages/research_harness/caliber_expander.py` | 新建 | ~1000 | Phase 3(caliber) |
| `scripts/report_quality_inspect.py` | 新建 | ~340 | Phase 1 |
| `scripts/__init__.py` | 新建 | 0 | Phase 1 |
| `tests/test_report_quality_inspect.py` | 新建 | ~180 | Phase 1 |
| `tests/test_caliber_expander.py` | 新建 | ~280 | Phase 3 |
| `tests/test_research_harness_plan_semantic.py` | 修改 | +5 | Phase 3(fix) |
| `tests/test_research_api.py` | 修改 | +2 | Phase 3(fix) |

## 剩余风险

| 风险 | 说明 |
|------|------|
| Audit appendix 膨胀 | 字节码 finalize_report 生成的 audit appendix 占据 Markdown 大头，需字节码层面改动分离 |
| Human review 无 UI | gate 输出 HUMAN_REVIEW 后需手动 resume，用户不可见 |
| Editor1 LLM 输出长度 | ~2600 chars 对窄 query 可接受，长报需更广源覆盖 |
| Context pack 超预算 | 10-13 个 pack 超 budget，chunk retrieval 缓解但未根除 |
| real_nodes 代理层 | 对 broad 改动有维护风险，建议重建 source 后做宽改动 |

## 下一步建议

1. **字节码层面**: 分离 report artifact 和 audit sidecar，让 `report_markdown` 不再被 audit appendix 主导
2. **Human review 可视化**: API/UI 层面暴露 HUMAN_REVIEW 状态和 resume 流程
3. **搜索深度**: 提高 max_rounds/search budget 以增加源覆盖和 source diversity
4. **金标准评测**: 积累更多 golden case，建立回归评测集
