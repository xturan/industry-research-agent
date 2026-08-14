# ADR 0002: 统一 Source Taxonomy (source_family 规范化)

Status: Implemented (2026-06-21, live-validated)
Date: 2026-06-21
Context area: source_layer / research_workflow
Related: `docs/source-taxonomy-inventory.md` (现状图谱), ADR 0001 (Tavily 召回)

## 背景

源分类当前有 5 套并存体系 (见现状图谱), 最混乱的是 `source_family`:
无中央枚举、自由字符串, 同一概念多写法 (统计 5 种、项目 5 种、环境 3 种、
行业 4 种)。`source_family` 被 226 次引用 / 19 文件, 但产生点是少数 infer
函数。`source_role` (10 值规范枚举 + classify_source_role 函数) 是唯一规范的
一套, 且 `classify_source_role(source_family=...)` 已以 family 为输入。

## 决策 (经 5 题 grilling)

1. **基准 = source_role 的规范性**: 以已有 10 值 source_role 为可信度角色基准,
   把混乱的 source_family 收敛对齐到它。tier(A/B/C/D) 保留为正交的可信度等级
   维度 (tier 答"多可信", family 答"什么类型", role 答"什么角色")。

2. **机制 = 中央规范化函数 + alias 映射表**: 新增 `canonical_source_family()`
   + alias 表, 只在产生点注入规范化; 226 处读取点不动 (读到规范值, 向后兼容)。
   不做全局字符串替换 (高风险、易漏改透传链)。

3. **取值 = 8 个中间粒度规范 family** (双向可映射 role + backbone):

   | 规范 family | 收敛的同义词 | → role | → backbone |
   |---|---|---|---|
   | `official_policy` | official_policy, provincial_policy | official_policy_original | local_government |
   | `official_news` | official_news_or_interpretation | official_news_or_interpretation | local_government |
   | `public_resource_transaction` | project_public_resource, project_transaction, project_list, local_project_tender, tender_or_procurement, procurement | public_resource_transaction | project_public_resource |
   | `company_disclosure` | company_disclosure, disclosure | company_disclosure | (无, 全国) |
   | `statistics` | statistics_or_data, statistics_or_data_release, statistics_corroboration, statistics_fiscal, trade_data, energy_constraint_data | statistics_or_data_release | statistics_fiscal |
   | `industry_research` | industry_association_context, industry_data, industry_report, industry_topic, research_or_think_tank_context | industry_association_context / research_or_think_tank | (无) |
   | `environmental_land` | environmental_land_record, environmental_or_land_record, environmental_record | (归 statistics/data) | environmental_land_record |
   | `commercial_media` | media, commercial_media_context, aggregator | commercial_media_context / aggregator_or_unknown | (无) |

   中间粒度的理由: 纯用 role 10 值会丢 backbone 定向语义; 纯用 backbone 4 值
   可信度区分不足 (媒体/研究/披露会糊在一起)。8 值是同时满足"可信度判定 +
   本地定向"的最小集。

4. **落点 = `packages/sources/local_source_patterns.py`**: 零依赖
   (0 个 packages.* import) → 任何产生点可安全 import, 无循环依赖; real_nodes
   主产生点已 import 它; 它已是 backbone 体系的家 (family→backbone 映射内聚)。
   family→role 映射让 source_quality.classify_source_role 反向 import 它
   (family 是更底层概念)。

5. **迁移 = 三步渐进** (每步独立验证、可回退):
   - Step 1 加法 (零风险): 新增 `Literal CanonicalSourceFamily` (8 值) +
     `canonical_source_family(raw)->str` (alias 表) + `family_to_role()` /
     `family_to_backbone()`。纯新增, 不动现有代码。
   - Step 2 产生点接入 (低风险): 在少数产生点 (`_infer_source_family`、
     retrieval_bridge 的 `or "graph_source"` 等) 包 `canonical_source_family(...)`。
     读取点不动。每接一点跑 live smoke 验证召回/分类不退化。
   - Step 3 断言收敛 (验证): 测试遍历已知同义词断言都映射到 8 值之一;
     live case1 跑通确认 gate obligation 匹配、backbone 定向仍正确。

## 权衡与备选 (已否决)

- 以 source_family 为基准 (否决): 把混乱固化成标准, 治标不治本。
- 全新第三套枚举 (否决): 要改 226+180 处引用, 工程量巨大、高风险。
- 直接复用 role 10 值当 family (否决): 丢 backbone 定向语义; role 细分对 family
  用途过细。
- 更粗 4-5 值对齐 backbone (否决): 可信度区分不足。
- 放 source_quality.py / 新建独立模块 (否决): 前者使 real_nodes 新增依赖;
  后者要反转现有依赖方向。
- 一次性全局替换 226 处 (否决): 高风险、难回退。

## 影响

- 新增: `local_source_patterns.py` 的 8 值 Literal + 3 个映射函数 + alias 表。
- 改动: 少数 source_family 产生点包一层规范化 (Step 2)。
- 不动: 226 处读取点、tier 体系、source_role 的 10 值定义。
- 收益: source_family 从"无约束自由字符串"变为"8 值规范 + 双向映射", 消除
  5 套统计/5 套项目等同义词混乱; family↔role↔backbone 三者对齐, 新增一类源
  只需在 alias 表 + 两张映射加一行。

## 已知局限 / 未决

- environmental_land 映射到 role 时归入 statistics/data (无独立环境 role), 可能
  损失细分; 若未来需要可加独立 role。
- 搜索口径扩展的 4 套并行 (caliber_expander / dimension templates / gap_core_topic
  / phrase_augmenter) 不在本 ADR 范围 — 本 ADR 只统一 source_family, 口径扩展
  统一是后续独立工作。

## 实施记录 (2026-06-21, live-validated)

三步迁移已全部落地:
- Step 1 (加法): `local_source_patterns.py` 新增 `CanonicalSourceFamily` 8 值
  Literal + `_FAMILY_ALIAS_TO_CANONICAL` 别名表 + `canonical_source_family()` /
  `family_to_role()` / `family_to_backbone()`。17/17 同义词收敛测试通过。
- Step 2 (产生点接入): `real_nodes.py` collect_sources (infer_source_family
  返回值 + fallback) 和 `retrieval_bridge.py` (2 处 `or "graph_source"` 默认)
  包 `canonical_source_family()`。排查确认 `llm_agents.py:44` 和
  `plan_semantic.py:461` 是读取透传/obligation 契约层, 非源产生点, 不动。
- 中间验证: ruff 0 严重错误; source 层回归 `test_sources_layer` +
  `test_rag_retrieval` 13 passed 零回归。
- Step 3 (live 断言收敛): live case1 端到端, 3636 个**源对象** source_family
  全部收敛到规范值 (official_policy 2298 / official_news 954 /
  company_disclosure 384)。唯一非规范值
  `location_matched_official_or_project_source` (2 处) 是
  `chief_gate.contract_meta.required_obligation_coverage[].source_family`,
  即 obligation 的"需求源族"契约字段, 不在 source_family 统一范围, 正确未规范化。

改动文件: `packages/sources/local_source_patterns.py`,
`packages/research_harness/real_nodes.py`,
`packages/research_harness/retrieval_bridge.py`, 本 ADR, `CONTEXT.md`。
