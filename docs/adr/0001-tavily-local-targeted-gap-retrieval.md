# ADR 0001: Tavily 本地定向 gap 重搜策略

Status: Accepted
Date: 2026-06-21
Context area: research_workflow / source retrieval (graph-v1 collect_sources)

## 背景

graph-v1 的 Deep Research 对 location-sensitive 查询(如"2025年合肥市低空经济
产业政策")产出的报告，主体内容是外地(深圳/江苏/池州)，本地(合肥)一手料
近乎为零。live case1 实测：重搜后 7 个源里合肥/安徽 = 0。

根因经 grilling 确认为**检索定向缺失**，而非 query 文本问题：
- C 修复后 query 短语已带"合肥"，但 Tavily 相关性排序由全网曝光度主导，
  深圳/江苏低空经济权威源曝光度碾压合肥本地小站。
- collect_sources 的 Tavily request 只有 `include_domains` 一个定向手段，
  而它在多数检索轮为空；无 `search_depth` / `topic` / 地域加权。

## 决策

经五题 grilling，定下 Tavily 本地定向 gap 重搜策略：

1. **根因 = 检索定向缺失**(非 query 文本)。策略重心放在 include_domains
   定向，而非继续堆 query 关键词。

2. **复用现成本地域名知识库**：`packages/sources/local_source_patterns.py`
   的 `local_source_domains_for_backbones(regions, backbones)`，而非新建、也
   不靠 LLM 动态生成域名。research_harness 重写时漏接了这套已验证的项目资产。

3. **3b 软定向(仅 gap 重搜轮)**：首轮全网广撒网保召回率，只在 A 机制
   (location obligation 硬门槛)触发的第二轮 gap 重搜才注入本地 include_domains。
   与既有 Phase 8 gap 循环天然契合。backbone 按检索轮 target_dimensions 映射：
   d_policy/d_local_rollout → local_government；d_execution →
   project_public_resource；d_statistics → statistics_fiscal；
   d_disclosure → 不注入本地域名(企业披露走全国 cninfo/交易所)。

4. **并行双查询兜底**：gap 重搜对每个缺口 family 产出两个轮——一轮带本地
   include_domains(精准补本地)，一轮空 include_domains(保召回)。共享
   collect_sources 现有的 `existing_urls` 自动去重(L1822/1888)。本地有索引则
   拿到一手源；本地无索引也不比现状更糟；A 的 gap 机制保证最终诚实降级。

5. **动态放宽 max_rounds**：gap 重搜阶段有效 `max_rounds = max(原值,
   gap轮数 + 1)`，保证翻倍后的 gap 轮全执行、不挤占原始轮。gap 轮是 A 机制
   刻意触发的必要补救，不应被为首轮设的预算上限误伤。

## 权衡与备选(已否决)

- **3a 每轮硬定向**(否决)：include_domains 是 Tavily 硬过滤；本地站索引稀疏
  时会导致该轮 0 结果，比"返回外地源"更糟。3b 用软定向 + 并行双查询规避。
- **LLM 动态生成域名**(否决)：易幻觉出不存在的域名、每次耗 token、不稳定。
- **新增本地源 provider**(否决)：工程量大，超出"搜索策略"范围；Tavily 仍是
  当前唯一 provider。
- **5-合并(phrase 级 include_domains)**(否决)：需把轮级 include_domains 降为
  phrase 级，改动 collect_sources 循环结构，改动面更大。
- **5-限额(放宽但封顶)**(保留为未来选项)：若 gap 轮 credit 失控，可加封顶。

## 影响

- 单一接入点：`_build_gap_targeted_rounds`(real_nodes.py L478-528)在 location
  非空时，把 `_GAP_FAMILY_TEMPLATES` 的通用 domains 替换为
  `local_source_domains_for_backbones([location], <family→backbone>)` 的本地
  具体域名，并为每 family 产出本地轮 + 无过滤轮。
- collect_sources 的有效 max_rounds 随 gap 轮数动态放宽。
- 不改 Tavily request 的 phrase 循环结构、不改 URL 去重、不引入新 provider。

## 已知局限

- 若合肥本地源在 Tavily 索引中本就稀缺，并行双查询也召不回——此时 A 的
  location obligation 硬门槛会如实降级为 HUMAN_REVIEW + 数据缺口标注。这是
  正确的产品行为(诚实暴露本地证据不足)，而非缺陷。要真正产出本地内容需
  source 层更深工作(本地站定向爬取 / 区县级 query 扩展)，超出本 ADR 范围。

## 修正 (2026-06-21): 核心假设被实测证伪

live case1 实测推翻了本 ADR 决策 #2/#4 的核心假设。

证伪证据:
- 决策假设"合肥本地一手料在本地政府域名(hefei.gov.cn)"。实测中,带
  `include_domains=[hefei.gov.cn,...]` 的本地定向轮 Tavily 返回 **0 结果**。
- 但用户手动用 `search_depth="advanced"` + 干净 query `"合肥低空经济政策"` +
  **不带任何 include_domains**,Tavily 返回大量真实合肥政策原文:
  - `ichuanghui.org/6052.html` — 合肥市政府办《支持低空经济发展若干政策》原文
  - `ahchanye.com` — 《合肥市低空经济发展行动计划(2023-2025)》
  - `news.cn` — 新华社合肥低空经济报道
- 即:合肥真实一手料在**聚合站/媒体/产业站**,NOT 在 hefei.gov.cn。硬过滤本地
  政府域名恰好把真实合肥源全挡了。

真实根因(取代本 ADR 原诊断):
1. collect_sources 的 Tavily 调用**缺 `search_depth="advanced"`**(用了默认
   basic)。这是召回质量的首要因素。
2. **include_domains 硬过滤帮倒忙**——合肥源不在被过滤的本地政府域名上。
3. query 过度拼接(超长 + "合肥"重复)稀释核心词,不如简洁 `"合肥低空经济政策"`。

修正后的实现:
- collect_sources 的 Tavily request 加 `search_depth="advanced"`。
- `_build_gap_targeted_rounds` **不再硬过滤域名**(include_domains=[]),靠
  advanced + 干净 location phrase 让 Tavily 自己召回真实本地源。
- 保留 A 的 location obligation 硬门槛(诚实降级)与 gap 触发机制不变。

教训: 在为"召回不到本地源"设计复杂定向策略前,应先验证 provider 在**最简
调用**(advanced + 干净 query)下的真实能力。本 ADR 原设计基于未经验证的
"本地料在政府域名"假设,过度工程化。
