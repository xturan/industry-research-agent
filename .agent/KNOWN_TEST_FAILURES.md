# Known Test Failures (Baseline)

> 用途: 固化测试基线, 便于后续判断"新增改动是否扩大失败范围"。
> 规则: 任何改动合并前, 至少重新运行本文档末尾的 focused 命令集,
> 确认失败数不高于 baseline (changed_failure_count == 0)。

## Baseline

```yaml
baseline_commit: 5dfbf9c
baseline_date: 2026-08-04
known_failures: 36
changed_failure_count: 0
```

## 已知失败分类 (36, 均为改动前即存在, 与 B.2/B.3 无关)

- **packages/sources LLM audit** (`test_source_quality_llm_audit.py`): DeepSeek 调用 /
  schema 诊断相关, 依赖真实 LLM / 网络。
- **packages/sources strong evidence matrix** (`test_source_quality_strong_evidence_matrix.py`):
  离线评估写入 / 分类, 依赖外部评估数据。
- **packages/sources domestic scaleout** (`test_sources_domestic_scaleout_phase5.py` /
  `test_sources_domestic_scaleout_phase7.py`): 阈值 / 离线 eval / live selection,
  依赖国内源路由与网络。
- **graph 环境相关** (`test_research_harness_graph.py`, 2 例):
  - `test_graph_runner_keeps_runtime_documents_while_human_review_is_pending`
    (shadow 模式未产生 runtime documents, 环境相关)。
  - `test_graph_runner_provider_backed_uses_search_provider`
    (stubbed LLM 下图路由到 HUMAN_REVIEW 未产出 report_id, 环境相关)。

## 已验证通过集 (每次改动后回归)

```bash
# B.3 相关 research_harness fast 集 (含 B.3.3a + B.3.3b)
python -m pytest \
  tests/test_research_harness_gap_retrieval.py \
  tests/test_research_harness_runner_eval_integration.py \
  tests/test_research_harness_eval_persistence.py \
  tests/test_research_harness_advisory_backfill.py \
  tests/test_research_harness_advisory_gap_backfill_node.py \
  tests/test_research_harness_finalize_evaluation.py \
  tests/test_research_harness_contract.py \
  tests/test_research_harness_claim_card.py \
  tests/test_research_harness_sufficiency_gate.py \
  -q --no-header

# finalization/persistence/resume graph 测试
python -m pytest tests/test_research_harness_graph.py -q --no-header \
  -k "finalize_report or claim_slot or evaluation_store or persistence \
      or graph_runner_loops or graph_runner_hits_human or resume_from_pending"
```

最近一次基线回归 (2026-08-04):
- B.3 + C.1 + C.2 + C.3.1 + C.3.2 + C.3.3 相关 fast 集: **192 passed**
  (C.3.1 校准 18 + C.3.2 Assignment 12 + C.3.3 Synthesis 16)
- finalization/persistence/resume graph 测试: **11 passed**
- B.3.4 OFF/ON 验收: 见 `data/tmp/b3_graph_shadow_acceptance/B3_GRAPH_SHADOW_ACCEPTANCE.md`
- C.1 StructuredDraft 测试: **13 passed**
- C.2 Structured Shadow OFF/ON 验收: 见
  `data/tmp/c2_structured_shadow_acceptance/C2_STRUCTURED_SHADOW_ACCEPTANCE.md`
- C.3.1 Structured Compare 测试: **13 passed** (见
  `tests/test_research_harness_structured_compare.py`)

## 密钥安全备注

- `.env` 已加入 `.gitignore`, 未跟踪, 从未进入 git 历史
  (`git log --all -- .env` 为空; 全 refs grep API key = 0 命中)。
- 仓库只保留 `.env.example` (占位符, 无真实凭据)。
