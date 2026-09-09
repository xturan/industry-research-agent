# PRD: Deep Research 可读 Markdown 报告质量升级

## 1. 文档信息

| 字段 | 内容 |
|---|---|
| 文档名称 | PRD: Deep Research 可读 Markdown 报告质量升级 |
| 所属项目 | invest_agent |
| 版本 | v0.1 |
| 状态 | active_for_remediation |
| 作者 | Codex |
| 创建时间 | 2026-06-17 |
| 更新 时间 | 2026-06-17 |
| 关联模板 | `docs/prd_reference_for_codex.md` |
| 当前执行计划 | `.agent/PLANS/deep-research-readable-report-remediation-v1.md` |
| 历史实现计划 | `.agent/PLANS/deep-research-readable-report-quality-v2.md` |
| 关联参考报告 | `E:/Edge_download/deep-research-report.md`, `E:/Edge_download/deep-research-report (1).md`, `E:/Edge_download/deep-research-report (2).md` |

状态说明：

- 本 PRD 仍是有效的产品质量目标文档。
- `.agent/PLANS/deep-research-readable-report-quality-v2.md` 已被勘误为 `superseded_partial_quality_gate_failed`，不能作为完成证明。
- 当前实现应以 `.agent/PLANS/deep-research-readable-report-remediation-v1.md` 为唯一 active 执行计划。

## 2. 背景与问题

当前 LangGraph / harness 路径已经可以完成一次 provider-backed workflow，并在 `response.json` 的 `report_preview.report_markdown` 中生成 Markdown。这个能力说明系统具备了基础报告生成链路，但它还没有达到产品级深度研究报告的交付标准。

本 PRD 中几个核心概念先统一口径：

- `Final report` 指用户最终阅读的中文 Markdown 正文，属于产品交付层。它必须像研究报告，而不是 JSON 字段的展示页。
- `Audit sidecar` 指 `response.json`、tool traces、contract diagnostics、dossier 等审计材料，属于复核层。它必须保留，但不能替代正文。
- `Evidence` 指可论证的证据单元，不等于单个 source 或 chunk。一个 evidence 可以归并多个 chunks 和 sources，并说明支持什么、不支持什么、适用范围和局限。
- `Claim` 指可审计研究断言，是报告推理层。一个 claim 应由一个或多个 evidence 支撑，也可以记录反向证据、风险或待核实状态。
- `Gate` 指 workflow 的质量放行判断。它不能只代表流程跑完，而要代表报告满足最低产品质量门槛。

最新真实 smoke 暴露的问题如下。

| 问题 | 具体表现 | 影响 |
|---|---|---|
| Markdown 正文过短 | 最新 `report_markdown` 约 4763 字符，但正文约 869 字符后进入 `Audit Appendix` | 用户拿到的不是深研报告，而是短摘要加审计附录 |
| 章节功能不足 | 只有 `Policy Basis` 和 `Company Disclosure` 两个业务章节 | 缺少执行摘要、方法口径、地方落地、项目执行、风险、结论等报告功能 |
| Gate 语义不可信 | `summary.json` 显示 `gate_obligation_gap_count=1`，但报告写“所有 obligation 已覆盖”并 PASS | 质量门槛和实际证据状态不一致 |
| Source 和 obligation 错配 | policy claim 被 company disclosure evidence 支撑，official policy obligation 未覆盖 | 结论看似有证据，实际证据家族不匹配 |
| 单 claim 单 source | 多数 claim 只依赖一个 evidence/source | 缺少交叉验证，容易过度外推 |
| 审计内容压过正文 | `Audit Appendix` 成为主要内容体积 | 最终 artifact 仍像内部审计预览 |
| Review issue 未阻断 | section role mismatch、low source diversity 等 issue 仍存在但最终 PASS | Editor2 / verifier 的意见没有形成产品质量约束 |
| Context 预算失控 | 多个 context pack token estimate 超过 100k | LLM 输入质量不可控，成本和稳定性风险高 |

因此，本功能要解决的核心问题是：

> 把当前“workflow 能产出 Markdown”的基础链路，升级为“能够稳定交付产品级中文深度研究 Markdown 报告”的可验收系统。

## 3. 产品目标

本期目标是构建 Deep Research 可读报告质量升级能力，使用户输入研究 query 后，系统能够输出：

1. 一份以 `report_markdown` 为主交付物的中文深度研究报告。
2. 一份保留 claims、evidence、sources、tool traces、quality gates 的审计 sidecar。
3. 一套能阻断低质量报告 PASS 的 gate 规则。
4. 一套可复跑的 live smoke 和报告质量评分标准。

功能完成后，用户应该能够：

- 输入：自然语言研究问题，例如“2025年合肥低空经济上市公司年报披露与地方政策项目公示”。
- 获得：可直接阅读的 Markdown 报告，而不是需要自己拼装的 JSON。
- 判断：通过报告结构、引用、风险和结论判断输出是否可用。
- 追溯：通过 audit sidecar 和 dossier 追溯每个关键结论的证据来源。

## 4. 非目标

本期不解决以下问题：

1. 不将 `graph_v1` 直接替换为 legacy `/deep-research/analyze` 或 `/research/analyze` 默认路径。
2. 不承诺所有 query 都生成 1-2 万字报告；窄问题允许更短，但必须满足报告功能完整性。
3. 不接入登录、付费、OCR、浏览器自动化或非公开数据源。
4. 不把报告定位为直接证券投资建议。
5. 不用更复杂的 harness 设计替代报告质量提升。
6. 不把 source acquisition 的全网覆盖一次性做完；本期重点是让已召回来源进入正确的证据与报告机制。
7. 不允许为了让流程 PASS 而降低证据、gate 或引用要求。

## 5. 用户角色

| 用户角色 | 说明 | 核心诉求 | 使用频率 |
|---|---|---|---|
| 研究人员 | 使用系统生成行业、政策、公司披露、地方项目类研究报告 | 快速获得可读、可复核、可继续加工的报告初稿 | 高频 |
| 审核人员 | 检查 AI 生成报告是否证据充足、口径稳健 | 看清每个结论是否有足够证据和风险提示 | 中频 |
| 产品/运营人员 | 判断报告生成路径是否达到产品可用标准 | 明确哪些 query 能交付，哪些需要人工或追加检索 | 中频 |
| 工程维护者 | 维护 workflow、provider、source、RAG、report delivery | 通过测试和 artifact 判断变更是否改善报告质量 | 高频 |

## 6. 核心使用场景

### 场景 1：生成地方政策 + 上市公司披露研究报告

用户：研究人员。

用户输入：

```text
2025年合肥低空经济上市公司年报披露与地方政策项目公示
```

系统需要：

1. 识别政策、地方落地、项目执行、上市公司披露、统计验证、风险不确定性等维度。
2. 生成多意图搜索计划，而不是 query 加后缀。
3. 召回并过滤与合肥、低空经济、年报披露、地方政策或项目公示相关的来源。
4. 基于 chunk / retrieval pack 合成 evidence，再由 evidence 合成 claim。
5. 由 Editor1 生成可读报告正文。
6. 由 Editor2 / verifier / gate 对证据覆盖、章节角色、source diversity、obligation coverage 进行质量阻断。

系统输出：

1. `report_markdown`：可直接阅读的中文 Markdown 报告。
2. `response.json`：审计 sidecar。
3. `dossier.md`：内部复核材料。

成功标准：

- 报告正文不以审计附录为主体。
- 关键政策 claim 不能仅由公司年报支撑。
- official policy obligation 未覆盖时不能直接 PASS。

### 场景 2：审核人员复核报告是否可发布

用户：审核人员。

用户输入：

```text
打开本次 run 的 report_markdown、summary.json 和 dossier.md。
```

系统需要：

1. 在报告中清楚呈现事实、推断、不确定项。
2. 在 audit sidecar 中提供 claim -> evidence -> source 的链路。
3. 在 gate reason 中说明为什么 PASS、HUMAN_REVIEW 或 NEED_MORE_EVIDENCE。

成功标准：

- 审核人员不需要读完整 JSON 就能理解报告结论。
- 审核人员可以通过 sidecar 复核关键结论来源。
- gate 与 obligation coverage 不矛盾。

### 场景 3：证据不足时触发人工参与

用户：研究人员 / 审核人员。

用户输入：

```text
生成某地某产业政策落地和企业披露报告。
```

系统发现：

- 来源数量不足。
- source family 与 claim 所需证据类型不匹配。
- 关键 claim 只有单一来源。
- review issue 属于 P0 阻断类型。

系统输出：

1. 明确的 `HUMAN_REVIEW` 或 `NEED_MORE_EVIDENCE` 状态。
2. 可读的人工决策提示。
3. 需要用户选择的行动项，例如追加搜索、接受低置信报告、终止生成、手动补充来源。

成功标准：

- 人工参与节点不能只存在于内部状态。
- 用户能看懂为什么需要参与。
- 用户的 resume action 被写入 checkpoint 和 dossier。

## 7. 业务流程

### 7.1 主流程

1. 用户输入研究 query。
2. Planner 生成维度计划、source obligation、搜索轮次和报告章节意图。
3. Search caliber 模块生成多意图搜索短语，并记录可审阅的搜索策略。
4. Source Hunter 执行搜索、过滤垃圾/错域/错地域来源。
5. Parser / Retriever 将来源正文切分、检索、扩展上下文，形成 retrieval pack。
6. Evidence Builder 使用 retrieval pack 合成 evidence。
7. Claim Builder 使用 evidence graph 合成多类型 claim。
8. Editor1 生成接近最终交付形态的 Markdown 报告正文。
9. Editor2 / Verifier 检查报告结构、证据链、source diversity、obligation coverage、夸大表达。
10. Chief Gate 决定 PASS、HUMAN_REVIEW、NEED_MORE_EVIDENCE 或 FAIL。
11. Finalize Report 输出 `report_markdown` 和 audit sidecar。

### 7.2 流程说明

| 步骤 | 节点 | 输入 | 处理 | 输出 |
|---|---|---|---|---|
| 1 | 用户输入 | query | 接收自然语言研究问题 | normalized query |
| 2 | Planner | query + summary_memory | 拆解维度、义务、章节意图 | dimension_plan, source_obligations |
| 3 | Search Caliber | query + dimension_plan | 生成多意图搜索策略 | search_groups, search_round_review |
| 4 | Source Hunter | search_groups | 搜索、过滤、记录 rejected reasons | sources, search_events |
| 5 | Retriever | sources + chunks | chunk + hybrid retrieval + rerank | retrieval_pack |
| 6 | Evidence Builder | retrieval_pack | LLM 合成 evidence | evidence_bundle |
| 7 | Claim Builder | evidence_bundle | LLM 合成 claim graph | claims |
| 8 | Editor1 | report_context_pack | 生成报告正文 | draft_markdown |
| 9 | Editor2 / Verifier | draft + claims + evidence | 质量检查 | review_issues, verifications |
| 10 | Chief Gate | quality state | 产品质量放行判断 | decision, gate_reason |
| 11 | Finalize | draft + audit data | 组装交付物 | report_markdown, sidecar |

## 8. 功能需求

| 模块 | 功能点 | 优先级 | 输入 | 输出 | 规则 | 验收标准 |
|---|---|---|---|---|---|---|
| Report Contract | 主交付物定义 | P0 | final state | `report_markdown` | Markdown 是最终产物，JSON 是审计 sidecar | `report_preview.report_markdown` 存在且可独立阅读 |
| Report Structure | 产品级章节结构 | P0 | claims + evidence + dimensions | 多章节正文 | 必须包含执行摘要、方法口径、维度章节、风险、结论、来源说明 | 不允许只有 claim 列表或两个短章节 |
| Gate Quality | 质量阻断 | P0 | obligation + review issues + report metrics | PASS / HUMAN_REVIEW / NEED_MORE_EVIDENCE | P0 issue 未解决不能 PASS | obligation gap、family mismatch、严重低多样性时不能 PASS |
| Evidence Synthesis | 多源 evidence | P0 | retrieval_pack | evidence_bundle | evidence 由 LLM 综合，不做 source 直映射 | 关键 evidence 标明支持范围和局限 |
| Claim Synthesis | 多类型 claim | P0 | evidence_bundle | claim graph | claim 分 fact / interpretation / risk / uncertainty | 中等 query 至少 8 条有效 claim 或说明不足 |
| Source Quality | 来源相关性和地域约束 | P0 | search results | accepted/rejected sources | 错地域、广告、内容农场、弱相关来源应过滤 | source review 显示 URL 和拒绝理由 |
| Editor1 | 研究员式写作 | P0 | compact report context | draft_markdown | 直接写报告正文，不输出 schema dump | 业务正文占 `report_markdown` 主要部分 |
| Editor2 / Verifier | 审稿与反方校验 | P0 | draft + claim graph | blocking issues | 发现 P0 问题要影响 gate | issue 不再只记录不阻断 |
| Human Review | 人工参与 | P1 | gate decision | review prompt + resume options | 需要人工时清楚暴露参与点 | 用户能看到原因和可选操作 |
| Context Budget | 上下文压缩 | P1 | sources/chunks/claims | compact packs | Editor 节点不直接吞 100k token 原文 | 关键节点 token estimate 不超过预算阈值或有降级说明 |
| Artifact Delivery | 文件化报告 | P1 | final state | `.md` artifact path | 报告可直接打开审阅 | smoke 产物包含报告文件或明确 report path |

### 8.1 产品级章节结构

#### 功能说明

报告正文必须围绕用户研究问题组织，不围绕系统内部节点组织。章节标题可以随 query 调整，但必须提供等价功能。

#### 必备章节功能

1. 标题：明确研究对象和范围。
2. 执行摘要：先给结论、关键证据、最大不确定性。
3. 方法与口径：说明来源类型、时间范围、地域范围、事实与推断边界。
4. 维度正文：政策、披露、地方落地、项目执行、统计验证、风险等按 query 需要选择。
5. 证据呈现：表格、证据链、比较表或来源注释。
6. 风险与不确定性：说明不能证明什么、缺什么证据。
7. 结论与下一步研究：给出可继续验证的方向。
8. 来源说明：主要来源、引用和局限。

#### 验收标准

1. 中等复杂 query 的 `report_markdown` 正文建议不少于 8,000 中文字符。
2. 对完整研究 query，目标范围为 10,000-20,000 中文字符。
3. `Audit Appendix` 不得出现在正文前 70% 内容之前。
4. `Audit Appendix` 不得成为报告主体。
5. 报告不得只由 claim bullet 和 evidence dump 构成。

### 8.2 Gate 质量阻断

#### 功能说明

Gate 是产品放行节点，不只是流程结束节点。它必须把 evidence coverage、source family match、source diversity、review issue 和 report readability 纳入决策。

#### 阻断规则

| 阻断项 | PASS 条件 | 不满足时 |
|---|---|---|
| source obligation coverage | 必填 obligation 全覆盖 | NEED_MORE_EVIDENCE 或 HUMAN_REVIEW |
| source family match | 关键 claim 的 evidence family 满足要求 | NEED_MORE_EVIDENCE |
| local precision | 地域敏感 query 的主要来源匹配目标地域 | NEED_MORE_EVIDENCE 或 HUMAN_REVIEW |
| source diversity | 关键 claim 至少 2 个独立来源，或明确降级 | HUMAN_REVIEW |
| review issues | P0 issue 为 0 | HUMAN_REVIEW |
| report body ratio | 正文主体明显高于 audit appendix | FAIL_REPORT_QUALITY |
| limitations quality | 不出现系统性截断局限说明 | HUMAN_REVIEW |

#### 验收标准

1. 当 `gate_obligation_gap_count > 0` 时不得输出 `decision=PASS`。
2. 当 policy claim 只由 company disclosure 支撑时不得 PASS。
3. 当 Editor2 发现 P0 section role mismatch 或 low source diversity 时，gate 必须说明处理结果。

### 8.3 Evidence / Claim 生成

#### 功能说明

Evidence 和 claim 必须由 LLM 基于 retrieval pack 合成， deterministic 逻辑作为验证器和兜底器。

#### Evidence 输出要求

每条 evidence 必须包含：

- evidence_id
- supported_proposition
- source_ids
- chunk_ids 或 locator
- support_type
- support_strength
- source_family_basis
- time_scope
- location_scope
- entity_scope
- what_it_proves
- what_it_does_not_prove
- limitations
- conflict_notes

#### Claim 输出要求

每条 claim 必须包含：

- claim_id
- claim_text
- claim_type: fact / interpretation / risk / uncertainty / negative_signal
- required_source_family
- evidence_ids
- support_status
- caveats
- report_section_intent

#### 验收标准

1. 中等 query 至少生成 8 条有效 claim，除非 source scarcity 被 gate 明确记录。
2. 至少包含事实类、解释类、风险/不确定性类 claim。
3. 关键 claim 不允许全部依赖同一 source。
4. `limitations` 不得出现 `...(截断)` 这类不可读内容。

### 8.4 Editor1 / Editor2 角色

#### Editor1

Editor1 是首席研究员和报告作者。它的目标是写出接近最终交付的中文 Markdown 报告，而不是输出结构化中间件。

Editor1 必须：

1. 使用 dimension plan 组织章节。
2. 使用 claim graph 形成叙事逻辑。
3. 使用 evidence bundle 写证据链。
4. 明确事实、推断、风险、不确定项。
5. 避免“claim -> paragraph”的机械映射。

#### Editor2

Editor2 是审稿研究员和反方校验者。它的目标是找出报告是否能被产品放行。

Editor2 必须：

1. 检查章节角色是否匹配 claim family。
2. 检查 evidence 是否能支撑正文表达。
3. 检查来源是否多样且满足 source obligation。
4. 检查是否存在夸大、跳跃推断、缺少局限说明。
5. 将 P0 issue 输出为 gate 可消费的阻断项。

#### 验收标准

1. Editor1 输出的正文至少覆盖必备章节功能。
2. Editor2 issue 会进入 gate 决策，而不是只进入附录。
3. Editor1 / Editor2 的 prompt 和 context pack 可在 dossier 或 review artifact 中审计。

## 9. 输入输出定义

### 9.1 输入

| 输入类型 | 示例 | 是否必填 | 说明 |
|---|---|---|---|
| 用户 query | 2025年合肥低空经济上市公司年报披露与地方政策项目公示 | 是 | 自然语言研究问题 |
| time_scope | 2025年 | 否 | 若 query 中出现时间，系统自动识别 |
| location_scope | 合肥 | 否 | 若 query 中出现地域，系统自动识别 |
| source constraints | 官方来源、年报、项目公示 | 否 | 用户指定来源约束 |
| max_rounds | 2 | 否 | 搜索轮次上限 |
| max_loop_count | 1 | 否 | workflow 返工上限 |

### 9.2 输出

系统输出必须包含：

| 输出字段 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| report_markdown | string | 是 | 最终用户阅读的 Markdown 报告 |
| report_artifact_path | string | P1 | 可直接打开的 Markdown 文件路径 |
| response_json | object | 是 | 审计 sidecar |
| dossier_path | string | 是 | 内部复核文档 |
| decision | enum | 是 | PASS / HUMAN_REVIEW / NEED_MORE_EVIDENCE / FAIL |
| gate_reason | string | 是 | 放行或阻断原因 |
| claims | array | 是 | 可审计 claim graph |
| evidence | array | 是 | evidence bundle |
| sources | array | 是 | 来源列表和 URL |
| review_issues | array | 是 | Editor2 / verifier 的问题 |
| search_strategy_review | object | 是 | 搜索词和搜索意图审计 |

### 9.3 Markdown 输出最低结构

```markdown
# {研究标题}

## 执行摘要

## 方法与口径

## {维度章节 1}

## {维度章节 2}

## {维度章节 3}

## 风险、不确定性与待核实项

## 结论与下一步研究

## 主要来源与证据说明
```

## 10. AI 能力要求

| 能力 | 说明 | 输入 | 输出 | 质量要求 |
|---|---|---|---|---|
| 意图识别 | 判断 query 的研究对象、地域、时间、来源约束 | query | intent | 不遗漏政策、披露、地方、项目、统计等显性维度 |
| 搜索规划 | 生成多意图搜索计划 | intent + dimensions | search groups | 避免 query+后缀同质化 |
| 来源过滤 | 判断 URL / 标题 / 摘要 / 正文是否相关 | search results | accepted/rejected sources | 广告、错地域、弱相关、内容农场应拒绝 |
| 证据合成 | 从 retrieval pack 生成 evidence | chunks + sources | evidence bundle | 说明支持范围和局限 |
| claim 合成 | 从 evidence 生成研究断言 | evidence bundle | claim graph | 区分事实、推断、风险、不确定 |
| 报告写作 | 生成可读 Markdown 正文 | dimensions + claims + evidence | report draft | 接近参考 deep-research 报告风格 |
| 审稿校验 | 找出证据、章节、结论问题 | draft + graph | review issues | P0 issue 可被 gate 消费 |
| Gate 决策 | 产品质量放行 | metrics + issues | decision | 不因流程成功而误 PASS |

### AI 输出约束

1. 不允许编造不存在的政策、公告、数据或来源。
2. 不允许把推断写成事实。
3. 关键结论必须绑定 evidence。
4. 证据不足时必须降低结论确定性。
5. 不允许使用不可读的截断文本作为正式局限说明。
6. 不允许用 company disclosure 替代 official policy 来支撑政策 claim。
7. 不允许将 audit appendix 写成报告主体。

## 11. 数据与来源要求

### 11.1 来源类型

| 来源类型 | 示例 | 优先级 | 用途 |
|---|---|---|---|
| 官方政策 | 国务院、部委、省市政府、发改委等 | 高 | 政策依据 |
| 地方项目/公示 | 公共资源交易、项目公示、招投标公告 | 高 | 落地和执行证据 |
| 企业披露 | 年报、公告、交易所披露、巨潮资讯 | 高 | 企业事实和业务披露 |
| 统计数据 | 统计局、行业主管部门、官方数据发布 | 高 | 规模和趋势验证 |
| 权威媒体/解读 | 官方媒体、地方新闻、协会报告 | 中 | 背景补充 |
| 自媒体/内容农场 | 论坛、聚合页、广告下载页 | 低 | 默认不作为核心证据 |

### 11.2 来源验收要求

1. source review 必须展示 URL、标题、source family、search phrase、accepted/rejected reason。
2. 地域敏感 query 的本地来源比例必须达到可解释阈值，默认目标为 `local_precision >= 0.75`。
3. 每个 mandatory source obligation 必须显示 covered / not covered。
4. 来源不足时必须触发 NEED_MORE_EVIDENCE 或 HUMAN_REVIEW。

### 11.3 证据要求

1. 关键 claim 至少绑定 1 条 evidence。
2. 高确定性关键 claim 目标绑定至少 2 个独立来源。
3. evidence 必须可追溯到 source URL 和 chunk locator。
4. 多来源冲突时必须标注冲突，不允许强行合并。
5. 低质量来源不得通过高 support_strength 掩盖问题。

## 12. 非功能需求

| 类型 | 要求 | 验收方式 |
|---|---|---|
| 稳定性 | provider 失败时有明确 fallback 和诊断 | contract diagnostics |
| 可观测性 | 记录搜索词、URL、tool traces、context pack、gate reason | dossier / response.json |
| 可追溯性 | 每条关键 claim 可追溯到 evidence 和 source | 抽样检查 |
| 成本 | 记录 token、search credits、provider 调用次数 | summary.json |
| 上下文预算 | 关键 LLM 节点不直接传入超大原文 | context pack token estimate |
| 格式稳定性 | JSON sidecar 可解析，Markdown 可直接阅读 | `python -m json.tool` + Markdown inspection |
| 安全边界 | 不输出直接投资买卖建议 | 文本检查 |
| 可复现性 | smoke case 可通过脚本复跑 | `scripts/graph_provider_backed_smoke.py` |

## 13. 验收标准

### 13.1 功能验收

| 用例编号 | 输入 | 预期输出 | 验收标准 |
|---|---|---|---|
| TC-001 | 2025年合肥低空经济上市公司年报披露与地方政策项目公示 | 产品级 Markdown + sidecar | 报告包含执行摘要、方法口径、政策、披露、地方/项目、风险、结论、来源 |
| TC-002 | 广东省人形机器人产业政策与项目落地分析 | 政策和项目落地报告 | 至少覆盖政策、项目、企业、产业链、风险 |
| TC-003 | 2021年以来中国新能源汽车政策对三大环节需求支撑的证据链研究 | 多环节证据链报告 | 明确整车、电池、充电桩等维度 |
| TC-004 | 神木市煤炭与煤化工扩张空间评估 | 资源/项目/约束报告 | 明确资源、产能、项目、能耗碳排、政策路径 |
| TC-005 | 故意缺少官方政策来源的 query | NEED_MORE_EVIDENCE 或 HUMAN_REVIEW | 不得 PASS |

### 13.2 AI 质量验收

| 指标 | 目标值 | 说明 |
|---|---:|---|
| Markdown 可读性 | 必须通过 | 用户不打开 JSON 也能读懂核心结论 |
| 正文长度 | 中等 query 目标 >= 8,000 中文字符 | 窄问题可例外，但需说明 |
| 正文占比 | 正文主体 >= 70% | audit appendix 不得压过正文 |
| 必备章节覆盖 | >= 6 个功能章节 | 标题可变，但功能必须覆盖 |
| source obligation coverage | PASS 时 100% | 未覆盖不得 PASS |
| P0 review issue | PASS 时为 0 | 未处理不得 PASS |
| key claim source diversity | 关键 claim 目标 >= 2 sources | 不足需降级或人工审阅 |
| limitations 可读性 | 100% 不截断 | 不得出现 `...(截断)` |
| JSON 可解析 | 100% | `python -m json.tool response.json` 通过 |

### 13.3 异常验收

| 异常场景 | 预期行为 |
|---|---|
| 无足够官方来源 | 输出 NEED_MORE_EVIDENCE，不直接 PASS |
| 搜索结果广告/错域过多 | 记录 rejected reasons，并追加或降级搜索 |
| evidence 与 claim family 不匹配 | 阻断 PASS |
| LLM 输出格式错误 | 规范化、重试或记录 fallback |
| 章节与 claim family 错位 | Editor2 标记，gate 消费 |
| 人工审阅必要 | 用户可见 HUMAN_REVIEW 原因和 resume options |

## 14. 风险与边界

| 风险 | 说明 | 影响 | 应对策略 |
|---|---|---|---|
| 搜索质量不足 | Tavily 或通用搜索可能返回错域内容 | evidence 不足 | 强化 search caliber、source filter、obligation gate |
| LLM 过度自信 | LLM 可能把弱证据写成强结论 | 报告误导 | claim/evidence validator + gate 阻断 |
| 成本和延迟上升 | 长文报告、更多检索和多 agent 审稿增加成本 | 体验下降 | context pack 压缩、分阶段 smoke、缓存 |
| 旧代码形态不稳定 | `real_nodes.py` 仍是 recovery proxy | 后续维护难 | PLAN 中列为早期工程风险处理 |
| 报告模板僵化 | 过度固定章节会伤害不同 query 的表达 | 可读性下降 | 要求章节功能，不强制标题完全一致 |
| 证据不足仍被要求输出 | 某些 query 客观缺来源 | 低质量报告 | 明确 NEED_MORE_EVIDENCE / HUMAN_REVIEW |

## 15. 待确认问题

1. 产品级报告默认是否必须落盘为单独 `.md` 文件，还是继续只在 `response.json` 中提供字段。
2. 中等 query 的最小字符数是否固定为 8,000，还是按 query complexity 动态计算。
3. source diversity 的硬阈值是否对所有 claim 生效，还是只对 key claims 生效。
4. 是否在本期把两层 memory 接入 planner，还是先作为后续 PLAN 独立推进。
5. 是否允许在 source 不足时输出“低置信简报”，以及它的 UI/API 状态应如何命名。

## 16. PRD 质量检查清单

- [x] 写清楚用户是谁。
- [x] 写清楚要解决的问题。
- [x] 写清楚本期目标。
- [x] 写清楚非目标。
- [x] 写清楚核心流程。
- [x] 写清楚每个关键能力的输入和输出。
- [x] 写清楚异常情况。
- [x] 写清楚验收标准。
- [x] 写清楚 AI 输出质量要求。
- [x] 写清楚证据链和引用要求。
- [x] 写清楚失败兜底策略。
- [x] 写清楚风险。
- [x] 列出待确认问题。
- [x] 避免把实现方案写成 PRD 主体。
- [x] 可以拆成开发任务和测试用例。
