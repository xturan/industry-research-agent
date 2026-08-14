# Subsystem A: 搜索与检索基础设施升级 — Design Spec

Status: approved | Date: 2026-06-18 | Supersedes: deep-research-readable-report-remediation-v1 (Phase 5 未开始的部分)

## Objective

升级 deep research pipeline 的搜索规划和检索基础设施。当前三大瓶颈：

1. **搜索同质化** — search phrase 只是 query + 后缀改写，没做口径扩展
2. **检索粗糙** — SQLite + lexical matching，chunk 是 2400 字符机械截断
3. **chunk 参与浅** — chunk 只在 retrieval_bridge 中生成，不进入 PG、没有语义分块、缺少溯源和质量评分

目标：搜索多维度覆盖 → chunk 语义化存入 PG → 混合检索精排 → 更多更准的 evidence → 更好的报告。

## Architecture: Three-Phase Sequential

```
Phase A1: Chunk + PG 底座
    │  语义分块 / 溯源 / 质量评分 / embedding → PG document_chunks
    │  retrieval_bridge 从 SQLite 切到 PG
    ▼
Phase A2: 混合检索
    │  pg_bm25 扩展 / vector+BM25 并行 → RRF 合并 → cross-encoder reranker
    │  本地模型部署 (source quality v2 + reranker 共用)
    ▼
Phase A3: Caliber Expansion 口径扩展
    │  混合维度模板 + LLM 动态分析 → 多维度×多源族搜索短语矩阵
    │  替代 query+后缀的 search_round 生成
```

---

### Phase A1: Chunk + PG 底座

**目标**: 让 chunk 语义化、可溯源、带质量评分，全部存入 PG，替代 SQLite + 机械截断。

**设计要点**:

1. **语义分块** — 用 `packages/ingestion/chunker.py` 替代检索时 2400 字符截断。按段落/章节边界分块，每个 chunk 带 `chunk_index`、`section_title`、`parent_chunk_id`。

2. **chunk 溯源** — 每个 chunk 记录来源 source 的完整元数据：`source_family`、`source_tier`、`url`、`crawl_timestamp`。chunk 在 evidence 构建时不仅是文本，还自带可信度标签。

3. **chunk 质量评分** — extract/parse 阶段对每个 chunk 打分：
   - 信息密度：中文字符占比、非噪声内容比例
   - 可引用度：是否含政策编号、数据百分比、公告标题等结构化内容
   - 来源权威性：source_tier (A/B/C/D) 映射为基础分
   - 低质量 chunk 不进 evidence 构建

4. **embedding 生成** — 用 `build_deterministic_embedding`（已有）或本地模型 embedding，存入 PG `document_chunks` 表的 `vector` 列。

5. **retrieval_bridge 切 PG** — `_build_source_chunks` 不再用 SQLite/内存，改为写入 PG 并从 `document_chunks` 查询。`build_evidence` 从 PG 拉取。

**文件范围**: `packages/research_harness/retrieval_bridge.py`、`packages/ingestion/chunker.py`、`packages/rag/embeddings.py`、PG migration

---

### Phase A2: 混合检索（vector + BM25 + reranker）

**目标**: chunk 存入 PG 后，检索从纯 lexical 升级为混合检索 + 精排。

**检索流程**:
```
query → [pgvector ANN (HNSW)] ─┐
                                ├─ RRF 合并 → top-N 候选 → cross-encoder reranker → top-K
query → [pg_bm25 full-text]   ─┘
```

**设计要点**:

1. **pg_bm25 扩展** — 在 PG 16 实例上加载 `pg_bm25`（或 `paradedb`），为 `document_chunks` 建 BM25 索引。

2. **RRF 合并** — 一次 SQL 查询同时跑 vector ANN + BM25 full-text，Reciprocal Rank Fusion 合并排名。已有 HNSW 索引复用。

3. **Cross-encoder reranker** — 本地模型权重部署为 reranker 服务，候选 chunk 精排后输出 top-K。每个 chunk 带 `vector_score`、`bm25_score`、`rrf_score`、`rerank_score` 和检索来源标记。

4. **本地模型部署** — 模型权重路径 `packages\training\data\model_output_v8_dpo_from_v7_b005_lr2e6`，部署为本地推理服务（vLLM/Ollama 兼容接口），同时服务于：
   - source quality scoring v2（对 source 做 A/B/C/D 可信度打分）
   - cross-encoder reranker（对候选 chunk 做精排）
   - 两个用途共享同一模型实例

5. **ChunkRetrievalService 升级** — `packages/rag/retrieval.py` 的 `search_chunks` 改为调用混合检索管线。

**文件范围**: `packages/rag/retrieval.py`、`packages/rag/rerankers.py`、`packages/sources/source_quality.py`、PG migration、模型部署配置

---

### Phase A3: Caliber Expansion 口径扩展

**目标**: 搜索规划从 "query + 后缀" 升级为多维度 × 多源族的搜索短语矩阵。

**设计要点**:

1. **混合维度模板** — 预设 6 个默认维度 `{政策(policy), 地方落地(local_rollout), 项目执行(project_execution), 公司披露(company_disclosure), 统计数据(statistics), 风险(risk)}`。LLM 分析 query 后可以增减维度。

2. **LLM 调用** — DeepSeek 做 caliber 分析。Prompt 要求：识别 query 隐含的维度需求，为每个维度生成 3-5 个不同角度、不同措辞的搜索短语，避免同质化。输入 query + plan context。

3. **维度-源族绑定** — 每个维度映射到 `required_source_family`：
   - 政策 → `official_policy`（约束 `site:gov.cn`）
   - 地方落地 → `local_government_notice`（约束 `site:gov.cn`）
   - 项目执行 → `public_resource_transaction`（约束 `site:ggzy.gov.cn, site:ccgp.gov.cn`）
   - 公司披露 → `company_disclosure`
   - 统计数据 → `statistics_or_data_release`
   - 风险 → `risk_assessment`（不限域）

4. **搜索轮次生成** — caliber 输出 N 个维度 → N 个 search_round，每个 round 带 `search_phrases`、`include_domains`、`target_dimension`、`required_source_family`。替代当前纯 query 改写的 search_round。

5. **fallback 机制** — LLM 不可用时退回到模板默认维度 + query 后缀搜索，确保 pipeline 不中断。

**示例**:
```
输入: "2025年广东人形机器人产业政策与项目落地证据"

维度 1: 政策 → official_policy
  短语: ["广东省 人形机器人 产业发展规划", "广东省 机器人 产业政策 2025", "人形机器人 政策扶持 广东"]
  约束: site:gov.cn

维度 2: 项目执行 → public_resource_transaction
  短语: ["广东 人形机器人 产业园 项目", "机器人 产业基地 建设 招标", "佛山 人形机器人 项目落地"]
  约束: site:ggzy.gov.cn

维度 3: 公司披露 → company_disclosure
  短语: ["人形机器人 上市公司 年报 2025", "机器人 概念股 业绩 披露"]
```

**文件范围**: `packages/research_harness/real_nodes.py`（plan_task）、`packages/research_harness/caliber_expander.py`

---

## Protected Contracts

- 不修改 legacy `/deep-research/analyze` 和 `/research/analyze`
- `graph_v1` 保持 opt-in
- `response.json` 结构不变（chunk 审计信息追加到 context pack）
- 已有 gate/editor2/editor1 逻辑不变
- PG 迁移增量进行，不回滚已有 SQLite 数据（PG 已是主存储）

## Validation

```powershell
# Phase A1: chunk + PG
pytest -q tests/test_research_harness_graph.py -k "build_evidence or collect_sources"
python -m py_compile packages/research_harness/retrieval_bridge.py

# Phase A2: 混合检索
pytest -q tests/test_rag_retrieval.py
python scripts/pgvector_retrieval_smoke.py

# Phase A3: caliber expansion
pytest -q tests/test_caliber_expander.py
pytest -q tests/test_research_harness_graph.py -k "plan_task"

# 全量回归
pytest -q tests/test_research_harness_graph.py -k "editor2 or chief_gate or human_review"
pytest -q tests/test_report_quality_inspect.py
```

## Fallback / Safety

- 任何 PG 操作失败时 fallback 到内存 chunk（当前行为）
- BM25 扩展不可用时退回到纯 vector 检索
- LLM caliber 失败时退回到默认维度模板 + query 后缀搜索
- 本地模型不可用时 reranker 退回到 source_family bonus + lexical overlap 规则
