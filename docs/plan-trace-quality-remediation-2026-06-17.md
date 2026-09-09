# PLAN Trace: Deep Research Readable Report Remediation

**PLAN**: `.agent/PLANS/deep-research-readable-report-remediation-v1.md`
**Date**: 2026-06-17
**Status**: `active_phase3_completed_phase4_pending` (was falsely `completed_keep_opt_in_with_documented_gaps`, corrected 2026-06-17)

## Objective

修复 graph_v1 的 workflow success 与 product-quality success 之间的鸿沟。
使 gate 不再盲 PASS、审计附录不再主导正文、P0 问题能被 gate 消费。

## Phase 执行 Trace

### Phase 0: Status Correction

**目标**: 更正之前 quality-v2 PLAN 过早声称"完成"的错误，建立诚实的基线。

**基线数据** (Phase 6 smoke):
```
case1_hefei: PASS, 3/9 checks, gate_obligation_gap_count=1 仍 PASS
case2_robot: PASS, 6/9 checks
case3_nev:   PASS, 8/9 checks
case4_coal:  PASS, 7/9 checks
全部: workflow_pass_product_fail
```

### Phase 1: Quality Inspector Truth Fix

**目标**: 修复 `report_quality_inspect.py` 的 claim/evidence/source 计数路径。

**改动**:
- `scripts/report_quality_inspect.py` — 从 `report_preview` 顶层整数 / `tool_composed_report.claim_briefs` / `node_steps.output_summary` 三层回退读取

**验证**: 四 case 重新判定后均显示真实计数，确认为 `workflow_pass_product_fail`。

### Phase 2: Gate Obligation Hard Block

**目标**: 使 `gate_obligation_gap_count > 0` 不能返回 PASS。

**根因**: `has_obligation_gap` 用 `family_covered` 启发式（只判断是否有非空 evidence_ids），不检查 evidence 是否真的来自 required source family。与 `all_obligations_covered` 使用两套不一致的 truth source。

**改动** (`packages/research_harness/real_nodes.py`):
- `has_obligation_gap` 优先使用 `required_obligation_coverage[].covered`（由 verify_claims 产生）
- `family_covered` 启发式仅作为 `obligation_coverage` 缺失时的 fallback
- 消除了两个并行的 obligation 计算路径

**验证**:
- gate tests: 4/5 pass (1 预存)
- 模拟 case1 状态: `obl_policy_primary.covered=false` → `decision=ADD_EVIDENCE`, `gate_reason="obligation 未覆盖 (1个: obl_policy_primary) — 必须补充对应源族的证据后才能通过"`
- HUMAN_REVIEW 优先级保持

### Phase 3: Report Artifact Separation

**目标**: 将 reader-facing 报告正文与 audit appendix 分离。

**改动** (`packages/research_harness/real_nodes.py`):
- `finalize_report_provider_backed` 后处理: 检测 `## Audit Appendix` / `## 审计附录` markers，将 `report_markdown` 拆分为 reader body + `audit_markdown`
- **2026-06-17 修复**: 初始实现 marker 列表过宽，包含了 `Evidence And Limitations`、`Claim Verifications`、`key_claims` 等读者侧段落头，导致 `report_markdown` 丢失来源展示和 Evidence 展示。修复后仅保留 `## Audit Appendix` / `## 审计附录`。

**验证**:
- finalize tests: 5/5 pass (修复前 1/5，修复后全部通过)
- live smoke: bytecode 已独立产出 `report_preview.report_markdown` 和 `report_preview.audit_markdown`

### Phase 4: P0 Review Issue Gate Consumption

**状态**: **pending**

**目标**: P0 问题影响 gate 决策。

**当前代码已有但不够**:
- gate 已有 `has_p0_issues` 检测 (line 1709: `p0_issue_count + section_role_mismatches`)
- gate line 1860: 若 `has_p0_issues` 且 decision ∈ {PASS, REVISE_TEXT} → 路由到 `editor2_review`
- **问题 1**: editor2 fallback issues 的 severity 是 "warning" (line 195)，不是 "blocker"/"p0"，不触发 p0_issue_count
- **问题 2**: section_role_mismatch 通过独立启发式计数，与 review_issues 列表解耦
- **问题 3**: low source diversity、source family mismatch 在 gate 内单独检测 (line 1697)，但未作为 P0 issue 标准化

**Phase 4 需要做的**:
1. 让 editor2/verifier 产出 severity="blocker" 的 P0 issue (而非 warning)
2. 统一 gate 的 P0 判定：只从 `review_issues` 列表读取，不再用独立启发式
3. source family mismatch / low diversity 通过 review_issues 标准化传递

### Phase 5: Live Product Gate Rerun

**状态**: **pending** (依赖 Phase 4 完成)

**目标**: 重跑 4 个 case，验证所有修复效果。

**当前实际状态** (`data/tmp/remediation_final`):
- case1_hefei: HUMAN_REVIEW (gate 正确阻断)
- case2_robot: PASS workflow, 8/9 checks — `workflow_pass_product_fail` (over_budget_context_packs)
- case3_nev: PASS workflow, 8/9 checks — `workflow_pass_product_fail` (over_budget_context_packs)
- case4_coal: PASS workflow, 7/9 checks — `workflow_pass_product_fail` (body_ratio + over_budget_context_packs)
- 全部 4 case 仍是 `workflow_pass_product_fail`，未达到 Phase 5 的 `≥3/4 product pass` 标准

### Phase 6: Final Handoff

**状态**: **not_yet** (blocked by Phase 4 and Phase 5)

Done Condition 要求 Phase 4 (P0 gate consumption) 和 Phase 5 (≥3/4 product pass) 完成后才能 final handoff。

## 实现目标达成情况 (2026-06-17 修正)

| 目标 | 状态 | 说明 |
|------|------|------|
| gate 不盲 PASS | ✅ | obligation gap → HUMAN_REVIEW/ADD_EVIDENCE (Phase 2) |
| 正文/审计分离 | ✅ | reader report + audit_markdown 独立, finalize 5/5 (Phase 3, 已修复) |
| quality inspector | ✅ | 正确读取 graph-v1 计数路径, 16/16 tests (Phase 1) |

| 未达标 | 原因 | 下一步 |
|--------|------|--------|
| P0 issues gate consumption | 未实现 (Phase 4 pending) | editor2 severity 需从 warning → blocker, gate 统一读取 |
| 4-case live product pass | 未达标 (Phase 5 pending) | 全部仍是 workflow_pass_product_fail |
| p0_issues 仍 >0 | section_role mismatch 未阻断 gate | Phase 4 |
| over_budget_packs 仍 >5 | context pack 配置在字节码 | 字节码层修复 |
| case1 无报告 | gate 正确阻断 → 无 finalize | 增加 HUMAN_REVIEW 时的草稿保留 |

## 改动的文件 (累计)

| 文件 | 操作 | 关联 Phase |
|------|------|-----------|
| `packages/research_harness/real_nodes.py` | 修改 | Phase 2,3 (Phase 3 fix 2026-06-17: narrowed split markers) |
| `scripts/report_quality_inspect.py` | 修改 | Phase 1 |
| `tests/test_research_harness_graph.py` | 修改 | Phase 3 |
| `tests/test_report_quality_inspect.py` | 修改 | Phase 1 |
| `.agent/PLANS/deep-research-readable-report-remediation-v1.md` | 修改 | Phase 6 |
| `.agent/STATUS.md` | 修改 | Phase 6 |
| `.agent/PLANS/INDEX.md` | 修改 | Phase 6 |
| `docs/plan-trace-quality-remediation-2026-06-17.md` | 新建 | Phase 6 |

## Before / After (当前实际效果)

### Before (quality-v2 结束时)

```
case1_hefei: PASS, gate_obligation_gap_count=1 仍 PASS (盲 PASS)
report_markdown: 5184 chars, 正文和审计附录混合
business_body_ratio: 0.182-0.462
checks passed: 3-8/9
全部: workflow_pass_product_fail
```

### Current (remediation Phase 3 完成后)

```
case1_hefei: HUMAN_REVIEW (gate 正确阻断, Phase 2 fix)
case2_robot: PASS workflow, 8/9 checks — product_fail (over_budget_context_packs)
case3_nev:   PASS workflow, 8/9 checks — product_fail (over_budget_context_packs)
case4_coal:  PASS workflow, 7/9 checks — product_fail (body_ratio + over_budget_context_packs)
report_markdown: 纯正文, audit_markdown: 独立审计文件 (Phase 3 fix)
全部仍是 workflow_pass_product_fail
Next: Phase 4 (P0 gate consumption) → Phase 5 (live rerun with product pass target)
```
