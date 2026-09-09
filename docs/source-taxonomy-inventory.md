# 源分类现状图谱 (Source Taxonomy Inventory)

Status: reference (现状梳理, 非设计)
Created: 2026-06-21
用途: 厘清当前散落在多模块的源分类体系, 为是否统一提供全貌依据。

## TL;DR

源分类当前有 **5 套并存体系**, 散在不同模块, 彼此靠映射表勉强桥接,
**没有单一真相源**。最混乱的是 `source_family` —— 它无 Literal 枚举约束,
各模块用字符串字面量各写各的, 导致同一概念有 3-5 种写法。

## 五套分类体系

### A. Tier 分级 (可信度等级)
- 定义: `packages/agents/source_tier_model.py`, `deep_research.py`
- 取值: **A / B / C / D**
- 语义: A=政府政策原文; B=政府新闻/交易平台/企业公告; C=行业协会/研究机构/解读;
  D=商业媒体/自媒体/聚合器/过时源
- 用途: 证据可信度门槛 (overall_usable = tier in A/B)

### B. source_role (来源角色, source_quality v2)
- 定义: `packages/sources/source_quality.py` 的 `classify_source_role()`
- 取值 (10 种):
  - `official_policy_original` (政策原文)
  - `official_notice_or_rule` (通知/规章)
  - `official_news_or_interpretation` (政府新闻/解读)
  - `public_resource_transaction` (公共资源交易)
  - `company_disclosure` (企业披露)
  - `statistics_or_data_release` (统计/数据发布)
  - `industry_association_context` (行业协会)
  - `research_or_think_tank_context` (研究/智库)
  - `commercial_media_context` (商业媒体)
  - `aggregator_or_unknown` (聚合器/未知)
- 用途: SourceQualityV2 的细粒度角色判定 → publisher_authority 打分
- 注: 这是**最完整、最规范**的一套 (有明确函数 + 10 个固定取值)

### C. source_family (证据族) ⚠️ 最混乱
- 定义: **无中央枚举**, 散在 `real_nodes.py` / `source_quality.py` 字面量
- 同义词泛滥 (同概念多写法):
  - 统计类: `statistics` / `statistics_or_data` / `statistics_or_data_release` /
    `statistics_corroboration` / `statistics_fiscal` (5 种)
  - 项目类: `public_resource_transaction` / `project_public_resource` /
    `project_transaction` / `project_execution` / `project_list` (5 种)
  - 环境类: `environmental_land_record` / `environmental_or_land_record` /
    `environmental_record` (3 种)
  - 行业类: `industry_association_context` / `industry_data` /
    `industry_report` / `industry_topic` (4 种)
- 用途: gate obligation 匹配、证据归类、gap 重搜定向
- 问题: 无约束, 靠映射表桥接, 是"口径不统一"的主要来源

### D. LocalEvidenceBackbone (本地证据骨干)
- 定义: `packages/sources/local_source_patterns.py` 的 Literal
- 取值 (4 种): `local_government` / `project_public_resource` /
  `statistics_fiscal` / `environmental_land_record`
- 用途: 本地域名定向 (`local_source_domains_for_backbones`)

### E. LocalSourceClass (本地源类, 比 backbone 细)
- 定义: `local_source_patterns.py` 的 Literal
- 取值: `local_government` / `statistics` / `energy_constraint_data` /
  `trade_data` (+ 映射表里还有 official_policy / provincial_policy /
  financial_subsidy_notice / project_list / project_transaction /
  local_project_tender / environmental_or_land_record 等)
- 用途: 本地域名知识库的最细分类

## 模块间桥接映射 (现有)

### _SOURCE_CLASS_TO_BACKBONE (E→D)
```
local_government        → local_government
official_policy         → local_government
provincial_policy       → local_government
financial_subsidy_notice→ local_government
project_list            → project_public_resource
project_transaction     → project_public_resource
local_project_tender    → project_public_resource
tender_or_procurement   → project_public_resource
procurement             → project_public_resource
statistics              → statistics_fiscal
trade_data              → statistics_fiscal (推断)
```

### _BACKBONE_TO_LOCAL_SOURCE_CLASSES (D→E)
```
local_government         → (local_government,)
project_public_resource  → (project_public_resource,)
statistics_fiscal        → (statistics, energy_constraint_data, trade_data)
environmental_land_record→ (environmental_or_land_record,)
```

### _GAP_FAMILY_TEMPLATES family→backbone (C→D, real_nodes.py)
```
official_policy                            → local_government
company_disclosure                         → None (全国披露, 不本地定向)
public_resource_transaction                → project_public_resource
location_matched_official_or_project_source→ local_government
```

## 搜索口径扩展 (同样分散, 无统一)

query → 检索短语经过 4 套各自为政的环节:
1. `caliber_expander.py` — Intent Planner 口径展开 (IntentPlan/SearchPlan)
2. `_dimension_search_phrase_templates` (real_nodes.py) — 按 dimension_type 生成
3. `_gap_core_topic` (real_nodes.py) — gap 轮核心词提取 (2026-06-21 新增)
4. `search_phrase_augmenter.py` (旧 source 层) — 另一套短语增强

无"源分类 ↔ 搜索口径"的统一映射; dimension_type / source_family / backbone
三者在短语生成里混用。

## 概念对齐速查 (跨体系大致对应)

| 概念 | A.Tier | B.role | C.family | D.backbone |
|---|---|---|---|---|
| 政策原文 | A | official_policy_original | official_policy | local_government |
| 政府通知/新闻 | B | official_news_or_interpretation | official_policy | local_government |
| 公共资源交易 | B | public_resource_transaction | public_resource_transaction | project_public_resource |
| 企业披露 | B | company_disclosure | company_disclosure | (无,全国) |
| 统计数据 | B/C | statistics_or_data_release | statistics* (5种) | statistics_fiscal |
| 行业协会/研究 | C | industry_association_context / research_or_think_tank | industry_* (4种) | (无) |
| 商业媒体 | D | commercial_media_context | media | (无) |
| 聚合器/未知 | D | aggregator_or_unknown | (无) | (无) |

## 主要问题清单 (若要统一, 这些是靶点)

1. **source_family 无中央枚举** — 5 套统计写法、5 套项目写法、3 套环境写法、
   4 套行业写法。最高优先级收敛目标。
2. **B(role) 与 C(family) 概念重叠但不对齐** — role 有 10 个规范值, family
   是自由字符串; 两者本可合并为一套。
3. **搜索口径扩展 4 套并行** — 无统一映射, dimension_type/family/backbone 混用。
4. **D/E(local) 与 B/C(通用) 各自独立** — 本地体系和通用体系靠手写映射表桥接,
   新增一类源要同时改多处。

## 不在本图谱范围 (现状梳理, 非设计)

- 不提出统一方案 (那是后续设计决策)
- 不改动任何生产代码
- 仅记录"现在是什么样", 为"要不要统一、怎么统一"提供事实底座
