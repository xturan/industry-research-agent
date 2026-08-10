# CONTEXT.md — invest_agent 领域术语表 (Ubiquitous Language)

仅记录领域术语定义, 不含实现细节。架构决策见 `docs/adr/`。

## 源分类 (Source Classification)

源分类是**三个正交维度**, 不是一套标签。回答三个不同问题:

### Tier (可信度等级) — "这个源多可信?"
固定 4 值: `A` / `B` / `C` / `D`。
- A: 政府政策原文 (法规/通知/规划/实施细则)
- B: 政府新闻/公共资源交易平台/企业公告/上市披露
- C: 行业协会/研究机构/政策解读/咨询报告
- D: 商业媒体/自媒体/聚合器/严重过时源

### Source Role (来源角色) — "这个源扮演什么角色?"
固定 10 值 (由 `classify_source_role` 判定): official_policy_original /
official_notice_or_rule / official_news_or_interpretation /
public_resource_transaction / company_disclosure / statistics_or_data_release /
industry_association_context / research_or_think_tank_context /
commercial_media_context / aggregator_or_unknown。
用于 publisher_authority 打分。

### Source Family (证据族) — "这个源属于哪类证据?"
**规范 8 值** (ADR 0002, 收敛自此前的自由字符串): `official_policy` /
`official_news` / `public_resource_transaction` / `company_disclosure` /
`statistics` / `industry_research` / `environmental_land` / `commercial_media`。
- 双向可映射: family → role (可信度判定), family → backbone (本地定向)。
- 规范化入口: `canonical_source_family(raw)` (待实现, ADR 0002)。
- 历史问题: 曾无中央枚举, 同概念多写法 (统计 5 种/项目 5 种/环境 3 种/行业 4 种),
  现由 alias 表收敛。

### Local Evidence Backbone (本地证据骨干) — "本地定向搜哪类站?"
固定 4 值: `local_government` / `project_public_resource` /
`statistics_fiscal` / `environmental_land_record`。
用于 `local_source_domains_for_backbones()` 解析本地政府/交易域名。
注: company_disclosure / industry_research / commercial_media 无 backbone
(全国性或无定向价值)。

## 维度关系速查

| 概念 | Tier | Role | Family(规范8值) | Backbone |
|---|---|---|---|---|
| 政策原文 | A | official_policy_original | official_policy | local_government |
| 政府新闻/解读 | B | official_news_or_interpretation | official_news | local_government |
| 公共资源交易 | B | public_resource_transaction | public_resource_transaction | project_public_resource |
| 企业披露 | B | company_disclosure | company_disclosure | (无) |
| 统计数据 | B/C | statistics_or_data_release | statistics | statistics_fiscal |
| 行业协会/研究 | C | industry_association_context / research_or_think_tank | industry_research | (无) |
| 环境/土地记录 | B/C | (归 statistics) | environmental_land | environmental_land_record |
| 商业媒体/聚合 | D | commercial_media_context / aggregator_or_unknown | commercial_media | (无) |

## 关键区分 (避免混淆)

- **Tier ≠ Family ≠ Role**: 三个正交维度。一个源同时有 tier(可信度)、role(角色)、
  family(证据类型) 三个标签, 不要用一个推断另一个的全部 (但 family 可单向映射到
  role/backbone 作辅助)。
- **域名 ≠ 地域** (ADR 0001 教训): 判断源的地域相关性必须看内容文本, 不能看域名
  字符串。合肥政策原文常托管在 ichuanghui.org、宣城 gov 镜像等域名不含"合肥"的站。
- **source_family 是规范 8 值, 不是自由字符串** (ADR 0002): 新代码必须用
  `canonical_source_family()` 规范化, 不要直接写字面量。
