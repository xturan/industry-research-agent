# Source Content Clustering 人工盲审标注协议

> **annotation_schema_version**: `source_cluster_human_label_v1`
> **labeling_protocol_version**: `source_cluster_review_protocol_v1`
> 修改标签定义 / merge 映射 / confidence 规则 / 摘要合并策略时必须升级版本号，不能覆盖本协议。

## 1. 标注目的

判断两篇 Source 是否属于**同一份信息稿件或其直接改写版本**，用于评估 Source Content Clustering 的自动合并准确率。

**本次标注判断的是**：两篇文本是否应在"内容去重计数"中视为同一份内容。

**本次标注不判断**：
- 哪个页面是最初发布者；
- 两个发布主体是否真正独立；
- 信息是否来自同一线下消息源；
- Source 的可信度或来源等级；
- 文章观点是否正确。

必须严格区分：

```text
同一事件 ≠ 同一稿件
内容相关 ≠ 应当合并
内容重复 ≠ 来源主体独立
```

## 2. 标注文件

编辑 `audit_priority_review_blind.csv`，填写三个字段：

| 字段                 | 是否必填 | 说明                          |
| -------------------- | ---- | ---------------------------- |
| `human_label`        | 是    | 使用下方固定的 8 个标签之一              |
| `human_confidence`   | 是    | 使用 `high`、`medium` 或 `low`    |
| `review_notes`       | 建议  | 简要记录判断依据，特别是边界案例            |

**不要查看或修改** `audit_priority_review_algorithm.csv`（含算法判断，仅用于标注完成后的指标对照，提前查看会产生锚定偏差）。

## 3. 固定标签定义

### 3.1 `exact_duplicate`
两侧正文实质内容完全相同，仅存在非内容差异（URL 参数、移动/打印/镜像页、发布时间格式、模板/导航/页脚、空格标点排版、编辑版权信息）。→ **merge**

### 3.2 `full_reprint`
一侧完整转载另一侧正文，可能增加来源声明、编者按、开头/结尾小段说明、网站固定模板，或少量不影响事实含义的格式调整。主体段落顺序基本一致，关键事实/数字/表述高度一致，无新增独立采访/分析/实质信息。→ **merge**

### 3.3 `near_duplicate_rewrite`
非逐字相同，但明显基于同一稿件轻度改写（调句序、换同义词、删背景段、缩短重排）。核心事实集合基本完全相同，关键数字/日期/主体/状态一致，无明显新增独立信息，结构呈同稿衍生关系。→ **merge**
> 不要因为两篇都描述同一事件就使用此标签。

### 3.4 `summary_or_excerpt`
一侧仅摘录/摘要/简要转述另一侧（只保留前两段、只摘若干数字、将完整公告压缩成一段摘要）。未保留完整信息量。→ **do_not_merge**
> 摘要只能支持部分 Evidence，不能与完整原文等价计数。后续可单独建立 `summary_of`/`excerpt_of` 关系，但当前不直接归入同一内容簇。

### 3.5 `same_event_independent_reporting`
报道同一事件，但由不同作者/机构独立撰写：结构不同、引用/采访对象不同、一侧有现场描述或独有材料、核心数字可能相同但叙事和信息来源不同。→ **do_not_merge**

### 3.6 `revision_or_status_update`
两侧高度相似但关键事实更新/变化：拟建→签约→开工→试运行→正式投运→停运/终止；金额/年份/规模/主体实质变化；后续版本补充新进展。即使正文大部分相同，只要关键状态变化就不能作普通转载合并。→ **do_not_merge**
> 后续可记录为 `revision_of`。

### 3.7 `related_but_independent`
主题相关但不属同一稿件、也不是同一事件独立报道：政策原文 vs 政策解读、政策 vs 券商分析、项目新闻 vs 行业背景、公司公告 vs 媒体评论、同一统计数字不同分析结论、同一产业主题不同项目。→ **do_not_merge**

### 3.8 `uncertain`
材料不足以稳定判断或特征冲突：正文严重截断、只有标题/极短片段、无法判断是否独立新增、页面解析质量差、可能是转载也可能是独立改写、时间来源不足。→ **manual_review**
> 不要为了完成标注强行选择其他标签。

## 4. 标签 → 聚类动作映射

| 人工标签 | 聚类动作 |
| --- | --- |
| `exact_duplicate` | merge |
| `full_reprint` | merge |
| `near_duplicate_rewrite` | merge |
| `summary_or_excerpt` | do_not_merge |
| `same_event_independent_reporting` | do_not_merge |
| `revision_or_status_update` | do_not_merge |
| `related_but_independent` | do_not_merge |
| `uncertain` | manual_review |

## 5. 推荐判断顺序

1. **关键事实变化**：先查项目状态/日期年份/金额规模/主体/否定表达/新增进展。存在实质更新 → 优先 `revision_or_status_update`，不要因相似度高而合并。
2. **是否同一完整稿件**：正文主体/事实组织/段落顺序基本一致 → 逐字差异 `exact_duplicate`；完整转载 `full_reprint`；轻度改写 `near_duplicate_rewrite`。
3. **是否只保留部分内容**：明显摘要/摘录 → `summary_or_excerpt`。
4. **是否同一事件独立报道**：事件相同但独立采访/独有段落/不同信息组织 → `same_event_independent_reporting`。
5. **是否只是主题相关**：政策/项目/行业/数字相关 → `related_but_independent`。
6. **材料不足** → `uncertain`。

## 6. Human Confidence 定义

- `high`：证据明确，几乎无其他合理解释（正文完全一致、明确"转载自…"、状态明确从开工→投运、明显不同独立采访）。
- `medium`：总体较明确但存在边界（删改较多仍像同稿改写、摘要与轻度改写边界、独立新增信息较少）。
- `low`：正文不足/解析差/两种同样合理判断。**低置信优先 `uncertain`**，不强行选确定标签。

## 7. Review Notes 推荐写法

备注无需很长，记录决定性依据。示例：
- 正文和段落顺序完全一致，仅网站模板不同。
- B 只保留 A 的前两段和三个数字，属于摘要。
- 两篇均报道同一投运事件，但 B 增加企业负责人采访和独有运营数据。
- 正文高度相似，但 A 表述"试运行"，B 更新为"正式投运"。
- 只有标题和短摘要，无法判断是否全文转载。

## 8. 特殊边界规则

- **政策原文 vs 政策解读**：默认 `related_but_independent`，即使解读大量引用原文。
- **公司公告 vs 媒体报道**：全文转载公告 → `full_reprint`；媒体增加分析/采访/推断 → `same_event_independent_reporting` 或 `related_but_independent`。
- **同一数字**：共享金额/增长率/统计值不足以证明同稿。
- **同一事件**：共享项目/政策/企业名称不足以证明同稿。
- **时间差**：发布时间不同不自动意味着 revision，需判断关键事实是否变化。
- **摘要转载**：当前协议中摘要与完整原文不直接合并，避免 Evidence 支撑范围被错误等同。

## 9. 标注质量检查

- `human_label` 只用固定 8 值；
- `human_confidence` 只用 `high/medium/low`；
- `uncertain` 不应同时填 `high`；
- 所有 `revision_or_status_update` 写明变化的状态/金额/日期；
- 所有 `near_duplicate_rewrite` 确认没有独立新增事实；
- 不要参考算法文件后再修改标签（除非进入正式复核阶段）。
