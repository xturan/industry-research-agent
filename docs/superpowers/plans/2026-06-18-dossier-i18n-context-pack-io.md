# Subsystem C: Dossier 中文化 + Context Pack I/O — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Dossier.md 全中文 + 每个 node 完整 I/O 快照可审阅。

**Architecture:** 两个独立 Task。Task 1 纯文本替换 dossier.py 中所有英文字符串为中文。Task 2 在 runner 的 node 执行前后捕获 state snapshot，扩展 context pack 的 io_snapshot 字段，dossier 中用 `<details>` 折叠呈现。

**Tech Stack:** Python, Markdown, JSON

## Global Constraints

- `response.json` 结构不变（`context_packs` 新增 `io_snapshot` 为增量字段）
- 不修改 pipeline 执行逻辑
- 不影响 graph 决策路径

---

### Task 1: Dossier 全中文

**通俗说明**：把 dossier.md 中所有英文 section 标题、表格头、描述文字替换为中文。

**Files:**
- Modify: `packages/research_reports/dossier.py`

- [ ] **Step 1: 替换 `render_graph_research_dossier` 的 section headers**

将所有英文 header 改为中文：

```python
# Line 128-168 — 替换所有英文字符串
parts = [
    "# LangGraph 研报运行档案\n",
    f"- 运行 ID: `{run_id}`",
    f"- 生成时间: `{generated_at.isoformat()}`",
    f"- 原始查询: { _inline(query) }",
    f"- 线程 ID: `{response_json.get('thread_id', '')}`",
    f"- 状态: `{response_json.get('status', '')}`",
    f"- 决策: `{response_json.get('decision', '')}`",
    "",
    "## 1. 运行概览",
    _render_graph_overview(response_json, context),
    _render_graph_planner_contract(context),
    "## 2. 节点执行追踪",
    _render_graph_node_steps(context),
    "## 3. 来源、证据与断言",
    _render_graph_search_events(context),
    _render_graph_sources(context),
    _render_graph_retrieval_pack(context),
    _render_graph_evidence(context),
    _render_graph_claims(context),
    _render_graph_claim_support_matrix(context),
    _render_graph_claim_verifications(context),
    _render_graph_contract_diagnostics(context),
    "## 4. 上下文包",
    _render_graph_context_pack_table(context),
    _render_graph_context_pack_details(context),
    "## 5. 工具调用追踪",
    _render_graph_tool_traces(context),
    "## 6. 人工复核",
    _render_graph_human_review(context),
    "## 7. 最终报告预览",
    _render_graph_final_report(context),
    "## 术语说明",
    _render_graph_glossary(),
    "## 档案说明",
    "- 本档案记录可见的图状态、节点输出和上下文包摘要。",
    "- 不记录隐藏的思维链或密钥信息。",
    "",
]
```

- [ ] **Step 2: 替换所有 `_render_graph_*` 函数中的英文字符串**

关键替换映射（全文件搜索替换）：

| 原英文 | 中文 |
|--------|------|
| `"No ... details were captured."` | `"未捕获...详情。"` |
| `"No ... were captured."` | `"未捕获...。"` |
| `"Not available in this run."` | `"本次运行中不可用。"` |
| `"| Item \| Value \|"` | `"\| 指标 \| 数值 \|"` |
| `"| Planner Item \| Value \|"` | `"\| 规划项 \| 数值 \|"` |
| `"| Field \| Value \|"` | `"\| 字段 \| 数值 \|"` |
| `"| Node \| Agent \| Status \| ..."` | `"\| 节点 \| 代理 \| 状态 \| ..."` |
| `"| Step # \| ..."` | `"\| 步骤 \| ..."` |
| `"### Planner Contract"` | `"### 规划合约"` |
| `"### Query Expansion"` | `"### 查询扩展"` |
| `"### Search Rounds"` | `"### 搜索轮次"` |
| `"### Source Candidates"` | `"### 来源候选"` |
| `"### Source Assessments"` | `"### 来源评估"` |
| `"### Source Quality V2"` | `"### 来源质量 V2"` |
| `"### Evidence Items"` | `"### 证据条目"` |
| `"### Claims"` | `"### 研究断言"` |
| `"### Agent Pipeline"` | `"### 代理流水线"` |
| `"### Context Packs"` | `"### 上下文包"` |
| `"### Tool Traces"` | `"### 工具追踪"` |
| `"### Human Review"` | `"### 人工复核"` |
| `"### Final Report"` | `"### 最终报告"` |
| `"Context Pack Details"` | `"上下文包详情"` |
| `"Over-budget Context Packs"` | `"超预算上下文包"` |
| `"Search Events"` | `"搜索事件"` |
| `"Retrieval Pack"` | `"检索包"` |
| `"Claim Verifications"` | `"断言验证"` |
| `"Contract Diagnostics"` | `"合约诊断"` |
| `"Graph Glossary"` | `"术语说明"` |
| `"Dossier Notes"` | `"档案说明"` |
| `"Node Execution Trace"` | `"节点执行追踪"` |
| `"Source, Evidence, And Claim State"` | `"来源、证据与断言状态"` |
| `"Content Assets And Generation Trace"` | `"内容资产与生成追踪"` |

- [ ] **Step 3: 运行编译验证**

```powershell
python -m py_compile packages/research_reports/dossier.py
```
Expected: OK (no errors)

- [ ] **Step 4: Commit**

```bash
git add packages/research_reports/dossier.py
git commit -m "feat: dossier fully Chinese — all section headers, labels, descriptions"
```

---

### Task 2: Context Pack 完整 I/O 快照

**通俗说明**：每个 node 执行前后捕获 state 快照，存入 context pack 的 `io_snapshot`。dossier 中用可折叠的 `<details>` 区块呈现。

**Files:**
- Modify: `packages/research_harness/context.py` — `build_context_pack_summary` 加 `io_snapshot`
- Modify: `packages/research_harness/runner.py` — node 执行前后捕获 state
- Modify: `packages/research_reports/dossier.py` — `_render_graph_context_pack_details` 渲染 IO 快照

- [ ] **Step 1: 扩展 `build_context_pack_summary`** (context.py)

在函数签名添加 `state_before` 和 `state_after` 参数，生成 `io_snapshot`:

```python
def build_context_pack_summary(
    *,
    node_name: str,
    agent_name: str,
    state: dict[str, Any],
    state_before: dict[str, Any] | None = None,   # NEW
    state_after: dict[str, Any] | None = None,     # NEW
) -> dict[str, Any]:
    # ... existing code ...

    # ── Phase C: Build IO snapshot ──
    io_snapshot = None
    if state_before is not None or state_after is not None:
        io_snapshot = {}
        if state_before is not None:
            io_snapshot["state_before_keys"] = sorted(state_before.keys())
            io_snapshot["state_before_summary"] = _state_summary(state_before)
            io_snapshot["state_before_full"] = _sanitize_state_for_dossier(state_before)
        if state_after is not None:
            io_snapshot["state_after_keys"] = sorted(state_after.keys())
            io_snapshot["state_after_summary"] = _state_summary(state_after)
            io_snapshot["state_after_full"] = _sanitize_state_for_dossier(state_after)

    return {
        # ... existing fields ...
        "io_snapshot": io_snapshot,   # NEW
    }


def _state_summary(state: dict[str, Any]) -> dict[str, str]:
    """Build human-readable summary of state keys."""
    summary: dict[str, str] = {}
    for key, value in state.items():
        if isinstance(value, list):
            summary[key] = f"list[{len(value)}]"
        elif isinstance(value, dict):
            summary[key] = f"dict[{len(value)} keys]"
        elif isinstance(value, str):
            summary[key] = value[:100] if len(value) > 100 else value
        elif isinstance(value, (int, float, bool)):
            summary[key] = str(value)
        elif value is None:
            summary[key] = "null"
        else:
            summary[key] = type(value).__name__
    return summary


def _sanitize_state_for_dossier(state: dict[str, Any]) -> dict[str, Any]:
    """Deep copy state, removing sensitive fields."""
    SENSITIVE_KEYS = {"api_key", "token", "password", "secret", "authorization"}
    cleaned: dict[str, Any] = {}
    for key, value in state.items():
        key_lower = key.lower()
        if any(sk in key_lower for sk in SENSITIVE_KEYS):
            cleaned[key] = "[已过滤]"
        elif isinstance(value, dict):
            cleaned[key] = _sanitize_state_for_dossier(value)
        elif isinstance(value, list):
            cleaned[key] = [
                _sanitize_state_for_dossier(v) if isinstance(v, dict) else v
                for v in value[:50]  # Cap list length
            ]
        elif isinstance(value, str) and len(value) > 5000:
            cleaned[key] = value[:5000] + "...[截断]"
        else:
            cleaned[key] = value
    return cleaned
```

- [ ] **Step 2: 在 runner.py 中捕获 state snapshot**

在 `runner.py` 的 `_run_node` 或 node 调用处，执行前 `state_before = dict(state)`，执行后 `state_after = dict(updated_state)`，传给 `build_context_pack_summary`。

具体改动位置（`runner.py` line ~227-235，`build_context_pack_summary` 调用处）：

```python
# Before node execution:
state_before = {k: v for k, v in state.items() if k != "_impl"}

# ... node.execute() ...

# After node execution, build context pack:
context_pack = build_context_pack_summary(
    node_name=node_name,
    agent_name=agent_name,
    state=updated,
    state_before=state_before,     # NEW
    state_after=updated,           # NEW
)
```

- [ ] **Step 3: 在 dossier.py 中渲染 IO 快照**

扩展 `_render_graph_context_pack_details`，为有 `io_snapshot` 的 pack 添加折叠区块：

```python
def _render_graph_context_pack_details(context: dict[str, Any]) -> str:
    packs = context.get("context_packs") or []
    if not packs:
        return "### 上下文包详情\n\n未捕获上下文包。\n"

    parts = ["### 上下文包详情\n"]
    for pack in packs:
        node = pack.get("node_name", "?")
        agent = pack.get("agent_name", "?")
        io_snap = pack.get("io_snapshot")
        
        parts.append(f"<details>\n<summary>节点: {node} ({agent})")
        if io_snap:
            before_keys = len(io_snap.get("state_before_keys", []))
            after_keys = len(io_snap.get("state_after_keys", []))
            parts[0] = parts[0].rstrip() + f" — 输入{before_keys}键 / 输出{after_keys}键"
        parts.append("</summary>\n")
        
        if io_snap:
            # Input summary table
            if "state_before_summary" in io_snap:
                parts.append("**输入状态摘要**\n")
                parts.append("| 字段 | 值 |\n|---|---|")
                for k, v in sorted(io_snap["state_before_summary"].items()):
                    parts.append(f"| `{k}` | {_cell(str(v)[:80])} |")
                parts.append("")
            
            # Output summary table
            if "state_after_summary" in io_snap:
                parts.append("**输出状态摘要**\n")
                parts.append("| 字段 | 值 |\n|---|---|")
                for k, v in sorted(io_snap["state_after_summary"].items()):
                    parts.append(f"| `{k}` | {_cell(str(v)[:80])} |")
                parts.append("")
            
            # Full JSON
            if "state_before_full" in io_snap:
                parts.append("\n<details>\n<summary>完整输入 (JSON)</summary>\n\n```json")
                parts.append(json.dumps(io_snap["state_before_full"], ensure_ascii=False, indent=2)[:20000])
                parts.append("```\n</details>\n")
            if "state_after_full" in io_snap:
                parts.append("\n<details>\n<summary>完整输出 (JSON)</summary>\n\n```json")
                parts.append(json.dumps(io_snap["state_after_full"], ensure_ascii=False, indent=2)[:20000])
                parts.append("```\n</details>\n")
        else:
            parts.append("无 IO 快照。")
        
        parts.append("</details>\n")
    
    return "\n".join(parts)
```

- [ ] **Step 4: 验证编译**

```powershell
python -m py_compile packages/research_harness/context.py
python -m py_compile packages/research_harness/runner.py
python -m py_compile packages/research_reports/dossier.py
```
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add packages/research_harness/context.py packages/research_harness/runner.py packages/research_reports/dossier.py
git commit -m "feat: context pack full IO snapshots — state before/after per node, details in dossier"
```

---

### Task 3: STATUS Update

- [ ] **Step 1: Update STATUS**

```bash
git add .agent/STATUS.md
git commit -m "chore: Subsystem C complete — dossier Chinese + context pack IO snapshots"
```
