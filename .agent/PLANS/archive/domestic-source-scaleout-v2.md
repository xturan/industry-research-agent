# Plan: Domestic Source Scaleout v2

Status: completed
Priority: high
Owner: codex/human
Scope: domestic source subsystem
Created: 2026-04-21
Last Updated: 2026-04-21

## Objective
把国内 Source 从“少量真实站点 + generic/profile/pack 占位”推进成一个可规模化扩张、可样本验证、可分层 rollout、后期可持续治理的国内信息源体系。

本计划不从零重新调研源，而是直接基于既有《中国产业研究信息源扩展与接入设计报告》的分层结论执行。

## Why this plan matters
当前问题不是没有更多公开源，而是：
- 没有按研究价值、结构稳定性、可接入性、持续运维成本做源分层
- 真实可执行的国内源仍然太少
- pack 仍有 placeholder 成分
- 上层研究需求无法由当前国内源覆盖充分支撑

根据现有研究报告，推荐优先顺序应为：
1. 政策类
2. 披露类
3. 地方块面类
4. 统计/交易/审批类
5. 协会类

并采用混合式分层接入：
- 核心源直连官方站点
- 外围源采用官方聚合或专题平台回填
- 高异构/强漂移/低频但高价值源采用白名单专题接入
- 高风险源在早期采用 metadata-first 与静态快照

## Execution principle
本计划采用三段式推进：
- 早期：样本验证期
- 中期：规模接入期
- 后期：完善治理期

规则：
- 先模板，后规模
- 先主干，后长尾
- 先 executable pack，后 placeholder pack
- 先可验证，后可扩张
- 每一阶段必须以表格中的任务族为执行单位，不按零散站点随意推进

## Out of scope
当前计划不包含：
- browser fallback
- OCR
- complex auth/login
- deep pagination 全覆盖
- network-facing MCP server
- Theme/Watchlist 产品层
- 长时任务基座进一步抽象化

## Design anchors reused from research
直接复用研究报告中的核心锚点：
- 推荐优先级顺序
- 10 类可复用接入模板
- P0/P1/P2 三期结构
- 首批 16 类试点源建议
- 90 天实施节奏
- 风险矩阵与底层能力建议

## Source rollout master table

| Rollout Layer | Source Cluster | Report Basis | Template Family | Early Sample Goal | Mid-term Goal | Late-stage Goal | Phase | Priority | Acceptance Focus |
|---|---|---|---|---|---|---|---|---|---|
| L1 | 中央政策主干 | C01/C02/C03/C12 | 政策文件库模板 | 跑通国务院政策库 / 发改委 / 工信部 / 能源局样板 | 补财政部 / 商务部等 P1 条线 | 完善附件、全文、解读联动 | Phase 1-2 | P0 | list/detail/attachment 稳定、年份分片可用 |
| L1 | 官方披露主干 | C17/C18/C19/C22/C23 | 披露公告模板 | 跑通上交所 + 深交所 + 巨潮 + 债券披露样板 | 补北交所 / 股转 | 形成事件链与跨平台去重 | Phase 1-2 | P0 | 公告增量、附件、问询/回复/处罚链路可用 |
| L1 | 统计/数据主干 | C12/C14/C15 | 结构化数据模板 | 跑通国家统计局 / 海关 / 能源指标样板 | 扩省统计与价格运行 | 做口径版本化与指标治理 | Phase 2 | P0 | 指标抽取、快照、时间序列稳定 |
| L1 | 项目/交易主干 | C32/C33/C34/C35 | 查询平台模板 / 土地矿权模板 | 跑通政府采购 / 公共资源交易 / 投资项目审批样板 | 扩土地矿权/规划公示 | 做跨源项目链聚合 | Phase 2-3 | P0/P1 | metadata-first 稳定、结果页与详情页可回溯 |
| L2 | 省级块面主干 | C24/C25/C26/C27/C28 | 省门户模板 / 省发改模板 / 省工信模板 / 省统计模板 / 省生态环境模板 | 首批样板省跑通 6 省 | 扩至 10-12 省 | 形成全国省级主干网 | Phase 1-3 | P0/P1 | 至少 3 类省级模板可跨省复用 |
| L2 | 城市级块面样板 | C29 | 城市门户模板 / 城市发改模板 / 城市工信模板 | 首批跑通 4 个样板市 | 扩到 8-12 个重点城市 | 做城市专题扩容 | Phase 3-4 | P1/P2 | 模板可复制、栏目树稳定、重复转载可去重 |
| L2 | 园区/开发区样板 | C30/C31 | 园区与城市模板 | 只做国家级/产业关键园区白名单 | 扩 1-2 类园区模板 | 做园区专题增强 | Phase 4-5 | P2 | 只在白名单下稳定运行，不全量铺开 |
| L3 | 协会/联盟/专题增强 | C39/C40/C45/C46 | 协会模板 / 专题模板 | 先做全国性协会与重点专题平台样板 | 扩 1-2 个高价值地方协会/联盟 | 作为行业增强层接入 | Phase 4-5 | P2 | 不做唯一真相源，能补充主干证据即可 |
| L3 | 信用/监管/司法增强 | C42/C43/C44 | 查询平台模板 / 司法模板 | 先做信用中国 / GSXT 样板 | 按专题接入司法公开 | 只做专题增强，不做早期全量 | Phase 4-6 | P1/P2 | 合规边界明确，metadata-first，失败可降级 |
| L3 | 企业/国资/IR 增强 | C36/C37/C38 | IR 模板 | 先做央企/上市公司 IR 样板 | 扩地方国企白名单 | 建立公司补链层 | Phase 4-6 | P1/P2 | 补链有效，不强依赖站点一致性 |

## Phase roadmap

### Phase 0: Inventory Rebase
Goal:
- 把现有国内 source、pack、generic/profile、report 中的 C01-C46 映射成可执行 inventory
- 不新增 collector
- 只做台账、模板归类、优先级、依赖关系确认

Deliverables:
- domestic source inventory table
- template mapping table
- executable vs placeholder pack table
- first-wave sample source shortlist

Acceptance:
- 所有现有国内 source 和报告中 P0/P1/P2 类别进入统一 inventory
- pack 状态明确（executable / beta / placeholder）
- 当前真实 domestic 源与报告类别映射完成

Fallback:
- 若某类源定义不清，先标记为 `category-confirmed / implementation-deferred`

### Phase 1: Sample Validation
Goal:
- 用最小样本验证模板族是否成立

Required sample clusters:
- 中央政策主干
- 官方披露主干
- 省级块面样板
- 首批城市样板

Sample scope:
- 国务院政策库
- 发改委
- 工信部
- 上交所
- 深交所
- 巨潮资讯
- 广东 / 江苏 / 浙江 / 湖北 / 四川 / 上海
- 深圳 / 苏州 / 杭州 / 武汉

Acceptance:
- 至少 10 个真实样板站点跑通
- 至少 6 类模板可复用
- 样板 pack 能输出真实 evidence
- 失败行为保持结构化

Fallback:
- 难站点降级为 metadata-first
- 单站异常不阻塞模板推进

### Phase 2: Backbone Buildout
Goal:
- 把报告中的 P0 主干层做成稳定统一体系

Target clusters:
- 政策主干
- 披露主干
- 统计/海关/能源指标
- 公共资源/政府采购/项目审批

Acceptance:
- `policy_pack_cn_v2` executable
- `disclosure_pack_cn_v2` executable
- `project_signal_pack_cn_v1` executable
- 至少 12 类首批试点源进入真实运行状态

Fallback:
- 聚合源只做辅助召回，不替代主源
- 对查询平台保持 metadata-first

### Phase 3: Provincial Rollout
Goal:
- 把省级模板复制到更多重点省份

Priority provinces:
- 广东
- 江苏
- 浙江
- 山东
- 安徽
- 湖北
- 四川
- 上海/北京（直辖市类模板）
- 福建
- 河南
- 湖南
- 重庆
- 陕西
- 天津
- 河北
- 江西
- 辽宁

Acceptance:
- 至少 8 个省级真实站点进入 executable
- 至少 3 个省级模板可跨省复用
- `local_rollout_pack_cn_v2` 可用于区域研究

Fallback:
- 省级站点特殊逻辑以 `template + site patch` 方式处理
- 不为单站破坏模板纯度

### Phase 4: City and Park Rollout
Goal:
- 做城市层与园区层专题增强

Priority cities:
- 深圳
- 广州
- 苏州
- 南京
- 杭州
- 宁波
- 合肥
- 武汉
- 成都
- 重庆
- 青岛
- 厦门
- 郑州
- 长沙
- 西安
- 天津滨海新区
- 北京经开区
- 上海临港

Acceptance:
- 4 个样板城市稳定运行
- 城市模板可复制到至少 2 个额外城市
- 园区模板至少 1 类可用

Fallback:
- 园区类只做白名单
- 不全量铺开

### Phase 5: Association and Special Topic Enhancement
Goal:
- 接入全国性协会、重点行业专题平台、部分地方联盟

Acceptance:
- `industry_signal_pack_cn_v2` 不再只是 generic
- 协会类 source 能作为补充证据进入 research

Fallback:
- 协会类永远不做唯一真相源
- 只抓标题/摘要/附件时也可接受

### Phase 6: Governance and Reliability
Goal:
- 完成治理、监控、缓存、回退与季度复盘机制

Acceptance:
- 站点/模板/pack 三层监控
- drift 检测
- 去重与快照策略
- 备用源切换逻辑
- 人工兜底流程
- 季度复盘机制

## Priority sources reused from report

### P0 主干层（直接复用报告）
- 国务院政策文件库/国务院公报
- 国家发展改革委
- 工业和信息化部
- 国家能源局
- 国家统计局
- 海关总署
- 中国证监会及派出机构
- 上海证券交易所
- 深圳证券交易所
- 巨潮资讯
- 银行间债券/中国货币网/交易商协会
- 省政府政策文件库
- 省发改委
- 省工信厅
- 全国公共资源交易平台
- 投资项目在线审批监管平台
- 政府采购平台

### P1 扩展增强层（直接复用报告）
- 财政部
- 商务部
- 生态环境部
- 自然资源部
- 农业农村部
- 市场监管总局/国家标准/处罚文书
- 国家知识产权局
- 北交所
- 全国股转
- 省统计局
- 省生态环境厅
- 土地矿权规划公示
- 央企/国资委
- 上市公司 IR
- 价格运行监测
- 信用中国
- GSXT
- 重点行业专题平台

### P2 专题异构层（直接复用报告）
- 科技部/国家科技管理系统
- 住建部
- 交通运输部
- 重点地市
- 国家级园区/省级园区
- 地方国资委与地方国企
- 全国性协会
- 地方协会
- 司法公开
- 行业展会与论坛

## Template-first execution table

| Template Family | Corresponding Report Template | First Validation Samples | Reuse Target | Notes |
|---|---|---|---|---|
| policy_library_template | 政策文件库模板 | 国务院政策库、发改委、工信部 | 财政部、商务部、住建部、交通部 | 优先做年份/类型分片 |
| disclosure_template | 披露公告模板 | 上交所、深交所、巨潮、债券披露 | 北交所、股转、IR | 做事件链与去重 |
| data_table_template | 结构化数据模板 | 统计局、海关、能源指标 | 省统计局、价格监测 | 做口径版本化 |
| province_portal_template | 园区与城市模板（省门户变体） | 广东/上海省级门户 | 复制到各省政府门户 | 先 metadata-first |
| province_drc_template | 政策文件库模板（省级） | 浙江/四川发改委 | 复制到各省发改委 | 发改委是重点主模板 |
| province_miit_template | 政策文件库模板（省级） | 江苏/湖北工信 | 复制到各省工信厅 | 工信模板优先度最高 |
| project_query_template | 查询平台模板 | 公共资源/项目审批/政采 | 各省地方交易/审批平台 | 先 metadata-first |
| city_dept_template | 园区与城市模板 | 深圳/苏州/杭州/武汉 | 扩到 8-12 个重点城市 | 城市层只白名单扩张 |
| association_template | 协会模板 | 全国性协会样板 | 地方协会/联盟专题扩张 | 不作为主干证据 |
| park_template | 园区与城市模板 | 中关村/临港等白名单 | 产业关键园区 | 后期才做 |

## Task decomposition rules
- 不按单站零散推进，而按模板族推进
- 一个阶段只推进 1-2 个模板族
- 新增站点必须先挂靠已有模板；若无法挂靠，需说明为什么要新增模板
- 每个模板族都必须先样本验证，再规模复制
- 每次扩张前必须完成一次 regression + domestic check + pack demo

## Dependencies
- 依赖已完成的 `source-v2-tiaokuai-foundation`
- 保持当前 NDRC / SZSE / PDF minimal pipeline 稳定
- 依赖现有 source pack / tiaokuai routing / profile schema

## Validation
Always run:
- `.agent/skills/source-regression-check.md`
- `.agent/skills/domestic-source-check.md`

When request/response or research integration changes:
- `.agent/skills/research-contract-check.md`

Suggested sample demos each phase:
- one policy-style demo
- one disclosure-style demo
- one provincial/local rollout demo
- one partial-failure demo

## Human review points
- Phase 0 end: inventory / template mapping review
- Phase 1 end: sample template viability review
- Phase 2 end: P0 backbone readiness review
- Phase 3 end: provincial rollout stability review
- Phase 4 end: city/park whitelist expansion review
- Phase 6 end: quarterly governance review

## Failure rollback strategy
- 单站失败：降级为 metadata-first
- 模板不稳定：退回样本阶段，不立即扩省/扩市
- 聚合源失效：回退到源头官方源
- pack 不稳定：标记为 beta，不提升为 executable
- 附件链路不稳定：保留 raw/ref，不阻塞 metadata 入库

## Monitoring and ops
Track at minimum:
- fetch success rate
- parse success rate
- attachment success rate
- drift rate
- duplicate ratio
- freshness lag
- pack evidence density
- source contribution score

## Progress
- [x] Phase 0 completed
- [x] Phase 1 completed
- [x] Phase 2 completed
- [x] Phase 3 completed
- [x] Phase 4 completed
- [x] Phase 5 completed
- [x] Phase 6 completed

## Current phase
Completed

## Next action
Archive this plan and start the next queued long-running plan.

## Validation snapshot (Phase 0 + Phase 1)
- `python -m ruff check .`
- `pytest -q tests/test_sources_domestic_scaleout_phase0.py tests/test_sources_domestic_scaleout_phase1.py`
- `pytest -q tests/test_sources_layer.py tests/test_sources_adapters_v1.py tests/test_sources_hardening_step34.py tests/test_sources_evals_step35.py tests/test_sources_router_domestic.py tests/test_sources_profile_adapter.py tests/test_sources_real_domestic_step42.py tests/test_sources_pdf_step43.py tests/test_sources_tiaokuai_phase1.py tests/test_sources_tiaokuai_phase23.py tests/test_sources_domestic_scaleout_phase0.py tests/test_sources_domestic_scaleout_phase1.py`

## Validation snapshot (Phase 2)
- `python -m ruff check .`
- `pytest -q tests/test_sources_domestic_scaleout_phase0.py tests/test_sources_domestic_scaleout_phase1.py tests/test_sources_domestic_scaleout_phase2.py`
- `pytest -q tests/test_sources_layer.py tests/test_sources_adapters_v1.py tests/test_sources_hardening_step34.py tests/test_sources_evals_step35.py tests/test_sources_router_domestic.py tests/test_sources_profile_adapter.py tests/test_sources_real_domestic_step42.py tests/test_sources_pdf_step43.py tests/test_sources_tiaokuai_phase1.py tests/test_sources_tiaokuai_phase23.py tests/test_sources_domestic_scaleout_phase0.py tests/test_sources_domestic_scaleout_phase1.py tests/test_sources_domestic_scaleout_phase2.py`

## Validation snapshot (Phase 3 kickoff)
- `python -m ruff check .`
- `pytest -q tests/test_sources_domestic_scaleout_phase0.py tests/test_sources_domestic_scaleout_phase1.py tests/test_sources_domestic_scaleout_phase2.py tests/test_sources_domestic_scaleout_phase3.py`
- `pytest -q tests/test_sources_layer.py tests/test_sources_adapters_v1.py tests/test_sources_hardening_step34.py tests/test_sources_evals_step35.py tests/test_sources_router_domestic.py tests/test_sources_profile_adapter.py tests/test_sources_real_domestic_step42.py tests/test_sources_pdf_step43.py tests/test_sources_tiaokuai_phase1.py tests/test_sources_tiaokuai_phase23.py tests/test_sources_domestic_scaleout_phase0.py tests/test_sources_domestic_scaleout_phase1.py tests/test_sources_domestic_scaleout_phase2.py tests/test_sources_domestic_scaleout_phase3.py`

## Validation snapshot (Phase 4 + Phase 5 + Phase 6 completion)
- `python -m ruff check .`
- `pytest -q tests/test_sources_layer.py tests/test_sources_adapters_v1.py tests/test_sources_hardening_step34.py tests/test_sources_evals_step35.py tests/test_sources_router_domestic.py tests/test_sources_profile_adapter.py tests/test_sources_real_domestic_step42.py tests/test_sources_pdf_step43.py tests/test_sources_tiaokuai_phase1.py tests/test_sources_tiaokuai_phase23.py tests/test_sources_domestic_scaleout_phase0.py tests/test_sources_domestic_scaleout_phase1.py tests/test_sources_domestic_scaleout_phase2.py tests/test_sources_domestic_scaleout_phase3.py tests/test_sources_domestic_scaleout_phase4.py tests/test_sources_domestic_scaleout_phase5.py tests/test_sources_domestic_scaleout_phase6.py`
- Result: `74 passed`

## Completion summary
- Phase 3:
  - expanded provincial rollout with `cn_policy_fujian_drc_tzgg_v1` and `cn_policy_henan_gxt_tzgg_v1`
  - promoted `local_rollout_pack_cn_v2` to `executable`
- Phase 4:
  - added city/park profiles (`guangzhou`, `nanjing`, `chengdu`, `lingang`)
  - introduced `city_park_pack_cn_v1`
- Phase 5:
  - added association profiles (`cn_industry_caam_news_v1`, `cn_industry_ces_report_v1`)
  - introduced `industry_signal_pack_cn_v2` and strategy route
- Phase 6:
  - implemented source governance snapshot (`fetch/parse/attachment/drift/duplicate/freshness/density/contribution`)
  - integrated governance snapshot into bundle metadata and service API
