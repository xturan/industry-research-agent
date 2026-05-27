# Self-Improving Loop — Claude Native

> 从 Codex `self-improving-for-codex` 迁移至 Claude Code 的自进化闭环技能。
> 基于 AGENTS.md / CLAUDE.md + memories + 定时精炼自动化。

## 核心差异：Codex vs Claude

| 维度 | Codex | Claude Code |
|------|-------|-------------|
| 规则入口 | `~/.codex/AGENTS.md` | `~/.claude/CLAUDE.md` (全局) + `AGENTS.md` (项目) |
| 记忆目录 | `~/.codex/memories/` (5 文件) | `~/.claude/projects/<project>/memory/` (类型化) + Codex 5 文件 |
| 自动化触发 | Nightly review prompt | scheduled-tasks MCP |
| 记忆类型 | PROFILE/ACTIVE/LEARNINGS/ERRORS/FEATURE_REQUESTS | user/feedback/project/reference |
| 自进化技能 | `self-improving-for-codex` SKILL.md | 本文件 + `self-improving-agent` skill |

## 两大记忆系统的桥接

Claude Code 有两套记忆系统，必须协同工作：

### 系统 A：Codex 5 文件（保留，持续维护）
- **路径**：`C:\Users\LEGION\.codex\memories\`
- **角色**：LEARNINGS.md / ERRORS.md / FEATURE_REQUESTS.md 的原始沉淀地
- **维护**：由 Claude 通过 Edit/Write 直接写入

### 系统 B：Claude 项目记忆（新，类型化索引）
- **路径**：`C:\Users\LEGION\.claude\projects\E--invest-agent\memory\`
- **角色**：MEMORY.md 索引 → 指向具体 memory 文件
- **维护**：由 Claude 的 auto memory 机制写入

### 同步规则
1. **新 learnings/errors** → 写入 Codex 5 文件（系统 A），同时在 Claude memory 中建立索引条目
2. **用户画像 / 规则** → 已在 CLAUDE.md 中，Codex PROFILE.md/ACTIVE.md 保留为历史参考
3. **定时精炼** → 读取两套系统，合并、去重、升级，再分别写回

---

## Workflow：五步搭建自进化闭环

### Step 1: Audit（审计现有状态）

检查以下内容是否存在且最新：
1. `C:\Users\LEGION\.codex\memories\` 下 5 个核心文件
2. `C:\Users\LEGION\.claude\CLAUDE.md` 中的 Self-Improvement 段落
3. `C:\Users\LEGION\.claude\projects\E--invest-agent\memory\MEMORY.md` 的索引
4. 已注册的 scheduled tasks（通过 `list_scheduled_tasks`）
5. 已有 memory 的完整性和编码健康

**审计命令**：
```powershell
# 检查 Codex 记忆文件
Get-ChildItem C:\Users\LEGION\.codex\memories\ -Name

# 检查 Claude 项目记忆
Get-ChildItem C:\Users\LEGION\.claude\projects\E--invest-agent\memory\ -Name

# 检查自进化相关 scheduled tasks
# 使用 mcp__scheduled-tasks__list_scheduled_tasks
```

### Step 2: Establish（建立/修复记忆布局）

#### Codex 5 文件（系统 A）
确保以下 5 个文件存在且格式正确：
- `PROFILE.md` — 长期用户画像
- `ACTIVE.md` — 高优先级跨任务规则
- `LEARNINGS.md` — 可复用经验
- `ERRORS.md` — 排障知识
- `FEATURE_REQUESTS.md` — 能力缺口

损坏修复（如 ERRORS.md 出现非 UTF-8 字节）：
```python
# 用 Python 修复编码
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
```

#### Claude 项目记忆（系统 B）
确保 `memory/MEMORY.md` 索引存在，指向：
- Codex 5 文件的路径引用
- Claude 原生 memory 条目

**MEMORY.md 模板**：

```markdown
# MEMORY.md — invest_agent 项目记忆索引

## 系统 A：Codex 5 文件（原始沉淀）
- [PROFILE.md](C:\Users\LEGION\.codex\memories\PROFILE.md) — 长期用户画像
- [ACTIVE.md](C:\Users\LEGION\.codex\memories\ACTIVE.md) — 活跃规则（已迁移至 CLAUDE.md）
- [LEARNINGS.md](C:\Users\LEGION\.codex\memories\LEARNINGS.md) — 可复用经验
- [ERRORS.md](C:\Users\LEGION\.codex\memories\ERRORS.md) — 排障知识
- [FEATURE_REQUESTS.md](C:\Users\LEGION\.codex\memories\FEATURE_REQUESTS.md) — 能力缺口

## 系统 B：Claude 原生记忆
<!-- Claude auto memory 条目 -->
```

### Step 3: Wire（接入 CLAUDE.md）

在 `CLAUDE.md` 中确保 Self-Improvement 段落包含以下要素：

1. **记忆目录位置**（两套系统）
2. **启动读取**：每次新任务前读取 PROFILE.md + ACTIVE.md（已在 CLAUDE.md 中）
3. **日志触发条件**（已存在于 CLAUDE.md Memory Trigger Conditions）
4. **按类型路由写入**：
   - Codex LEARNINGS.md ← learnings, corrections, knowledge
   - Codex ERRORS.md ← unexpected errors, debugging
   - Codex FEATURE_REQUESTS.md ← missing capabilities
5. **升级规则**：LEARNINGS/ERRORS → ACTIVE → CLAUDE.md 的升级管线
6. **定时精炼感知**：了解存在夜间精炼任务

### Step 4: Nightly Review（定时精炼）

使用 `mcp__scheduled-tasks__create_scheduled_task` 创建夜间任务。

**cron**：`57 2 * * *`（每天凌晨 2:57 本地时间，避开整点高峰）

**任务内容**：读取并精炼 Codex 5 文件，尤其是过去 24 小时新增的 LEARNINGS。

### Step 5: Validate（验证闭环）

验证清单：
- [ ] CLAUDE.md 指向 PROFILE 和 ACTIVE
- [ ] 5 个 Codex 记忆文件存在且编码健康
- [ ] MEMORY.md 索引存在且指向正确
- [ ] 升级规则明确（LEARNINGS → ACTIVE → CLAUDE.md）
- [ ] 定时精炼任务已注册并启用
- [ ] 两套系统同步规则清晰

---

## 记忆升级管线

```
对话中触发 logging condition
       │
       ▼
写入 Codex LEARNINGS.md / ERRORS.md / FEATURE_REQUESTS.md
       │
       ▼
夜间精炼任务读取过去 24h 新增
       │
       ├── 不稳定/单次 → 保留在原始文件
       ├── 稳定/跨任务/重复出现 → 升级到 ACTIVE.md
       └── 用户画像/长期偏好 → 升级到 PROFILE.md
       │
       ▼
ACTIVE.md 中特别稳定/顶层规则 → 升级到 CLAUDE.md
```

## 升级判断标准

**升级到 ACTIVE.md**：
- 跨任务有效
- 多次出现或用户明确确认
- 能明显提升执行/沟通/排障质量

**升级到 CLAUDE.md**：
- 已成为稳定顶层规则
- 或用户明确要求"以后都按这个来"

**保留在 LEARNINGS/ERRORS**：
- 有价值但还不够稳定
- 可能只适用于特定场景

**丢弃/不记录**：
- 一次性任务细节
- 纯闲聊
- 显而易见的小失误
- 无法复用的噪音

---

## 定时精炼 Prompt（Nightly Review）

```
这是 Claude Code 全局 self-improving 体系的夜间精炼任务。

你的目标不是回看当天全部对话，而是维护两套记忆系统：

系统 A — Codex 5 文件：
  C:\Users\LEGION\.codex\memories\
  ├── PROFILE.md      ← 只存长期稳定用户画像
  ├── ACTIVE.md       ← 只存高优先级跨任务规则
  ├── LEARNINGS.md    ← 可复用经验/纠正/知识
  ├── ERRORS.md       ← 排障知识
  └── FEATURE_REQUESTS.md ← 能力缺口

系统 B — Claude 项目记忆：
  C:\Users\LEGION\.claude\projects\E--invest-agent\memory\
  └── MEMORY.md       ← 索引文件

核心任务：
1. 读取 LEARNINGS.md、ERRORS.md、FEATURE_REQUESTS.md
2. 聚焦过去 24 小时的新增内容
3. 判断哪些已足够稳定，应升级到 ACTIVE.md 或 PROFILE.md
4. 清理重复、过时、表达不清的条目
5. 更新 MEMORY.md 索引

提炼规则：
- 只有非显而易见、可复用、跨任务有效的内容才值得保留或升级
- 一次性任务细节、纯闲聊、临时上下文、没有复用价值的噪音 → 不升级
- 升级到 PROFILE.md 的条件：长期稳定用户画像/偏好
- 升级到 ACTIVE.md 的条件：跨任务有效、应在每次任务前参考

保守策略：
- 不确定是否升级 → 不升级
- 本轮无高价值升级内容 → 允许只输出摘要不修改文件
- 绝对不要自动修改 CLAUDE.md！如需修改，只在输出中给出建议文本

输出必须是中文，必须包含：
- 读取了哪些记忆文件
- 修改了哪些文件及原因
- 升级/合并/改写了哪些内容
- 放弃了哪些升级及理由
- 建议给 CLAUDE.md 的文本（如有）
- 仍有待清理的条目
```

---

## 与 self-improving-agent Skill 的协作

本 skill（`self-improving-loop`） 和已有的 `self-improving-agent` skill 分工：

| 职责 | self-improving-loop | self-improving-agent |
|------|---------------------|----------------------|
| 记忆文件维护 | ✅ 核心职责 | ❌ |
| 夜间精炼 | ✅ 驱动 | ❌ |
| 模式抽象 (semantic patterns) | ❌ | ✅ JSON patterns |
| 经验提取 (episodic memory) | ❌ | ✅ JSON episodes |
| Skill 文件更新 | ❌ | ✅ 进化标记 |
| 升级管线 (LEARNINGS → ACTIVE → CLAUDE.md) | ✅ 核心职责 | ❌ |

两者互补：
- `self-improving-loop` 管理**记忆文件**的长期健康
- `self-improving-agent` 管理**技能文件**的持续进化
- 夜间精炼时，loop 读取 agent 的 episodic memory 作为补充证据

---

## 快速启动

首次搭建自进化闭环时：
1. 执行 Step 1 Audit
2. 执行 Step 2 Establish（缺失则创建，损坏则修复）
3. 执行 Step 3 Wire（检查 CLAUDE.md 段落完整性）
4. 执行 Step 4 Nightly Review（创建定时任务）
5. 执行 Step 5 Validate（跑验证清单）

后续维护：
- 白天：对话中自动触发 logging → 写入 Codex 5 文件
- 夜间：定时精炼自动运行 → 合并/去重/升级
- 每周：人工检查 ACTIVE.md 是否有应升级到 CLAUDE.md 的规则
