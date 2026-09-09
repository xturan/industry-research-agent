# Subsystem C: Dossier 中文化 + Context Pack 完整 I/O — Design Spec

Status: approved | Date: 2026-06-18

## Objective

1. Dossier.md 全中文输出，不再中英混杂
2. Context Pack 记录每个 node 的完整输入输出快照，审阅者能逐节点查看 pipeline 行为

## Part 1 — Dossier 全中文

**File**: `packages/research_reports/dossier.py`

将所有英文 section header、字段标签、表格标题、描述文本改为中文。

改动范围：`render_graph_research_dossier` 和所有 `_render_graph_*` 辅助函数中的字符串字面量。

示例映射：
- `"## 1. Graph Overview"` → `"## 1. 运行概览"`
- `"## 2. Node Execution Trace"` → `"## 2. 节点执行追踪"`
- `"## 3. Source, Evidence, And Claim State"` → `"## 3. 来源、证据与断言状态"`
- `"## 4. Context Packs"` → `"## 4. 上下文包"`
- `"## 5. Tool Traces"` → `"## 5. 工具调用追踪"`
- `"## 6. Human Review"` → `"## 6. 人工复核"`
- `"## 7. Final Report Preview"` → `"## 7. 最终报告预览"`
- `"| Item | Value |"` → `"| 指标 | 数值 |"`
- `"No ... details were captured."` → `"未捕获...详情。"`

## Part 2 — Context Pack 完整 I/O 快照

**Files**:
- `packages/research_harness/context.py` — `build_context_pack_summary` 扩展
- `packages/research_harness/runner.py` — node 执行后调用处
- `packages/research_reports/dossier.py` — `_render_graph_context_pack_details` 扩展

**改动**:

1. **state snapshot 捕获**（runner.py）：每个 node 执行前捕获 `state_before`，执行后捕获 `state_after`。过滤敏感字段（API key、token、password 等）。

2. **build_context_pack_summary 扩展**（context.py）：新增 `state_before` 和 `state_after` 参数。生成 `io_snapshot` 字段包含：
   ```json
   {
     "state_before_keys": [...],
     "state_after_keys": [...],
     "state_before_summary": {"query": "...", "sources_count": 5, ...},
     "state_after_summary": {"decision": "PASS", ...},
     "state_before_full": {...},
     "state_after_full": {...}
   }
   ```

3. **Dossier 呈现**（dossier.py）：每个 node 一个 `<details>` 折叠区块：
   - summary 行：node 名称、输入/输出 key 数量、关键摘要
   - 展开后：输入状态摘要表 + 输出状态摘要表 + 完整 JSON

## Protected Contracts

- `response.json` 结构不变（`context_packs` 新增 `io_snapshot` 字段为增量）
- 不修改 pipeline 执行逻辑
- 不影响 graph 决策路径

## Validation

```powershell
# Dossier compilation
python -m py_compile packages/research_reports/dossier.py

# Context pack
python -m py_compile packages/research_harness/context.py

# Live smoke — verify dossier generated
python scripts/graph_provider_backed_smoke.py --query "低空经济政策" --max-rounds 1 --output-dir "data/tmp/subsystem_c_smoke" --env-file .env --reset
# Check: data/tmp/subsystem_c_smoke/dossier.md is all Chinese + has IO snapshots
```
