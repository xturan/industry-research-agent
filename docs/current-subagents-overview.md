# 当前 6 个 Subagents 说明

## 总体原则

当前项目使用 v2 六角色 subagent 工作体系。

核心规则：

```text
PLAN 是严格施工图纸。
```

每个非简单任务都应该从 active PLAN 出发，而不是依赖隐藏对话记忆。active PLAN 需要记录目标、范围、约束、当前阶段、真实场景验证计划、worker 分工、验证结果、风险和下一步。

当用户说“开始实施PLAN”“执行PLAN”“实施当前PLAN”或等价表达时，应自动启动 v2 subagent 工作流，不需要用户额外点名 subagent。

## 角色总览

| Group | Agent | 默认模型 | 推理强度 | 核心职责 |
| --- | --- | --- | --- | --- |
| Group 1 管理 | `invest_project_director` | `gpt-5.4` | `medium` | 读取 STATUS 和 active PLAN，写入真实场景验证计划，安排 Group 2/3 |
| Group 1 管理 | `invest_project_summarizer` | `gpt-5.4` | `medium` | PLAN 完成后总结项目影响，并判断是否需要更新 worker 能力 |
| Group 2 执行 | `invest_agent_architecture_builder` | `gpt-5.4` | `medium` | 设计和搭建 agent / harness engineering 架构 |
| Group 2 执行 | `invest_feature_programmer` | `gpt-5.3-codex` | `medium` | 完成具体代码、工具、source、API、script、测试等实现 |
| Group 3 验证 | `invest_code_quality_checker` | `gpt-5.3-codex-spark` | `medium` | 执行 ruff、compile、focused pytest、import safety 等质量检查 |
| Group 3 验证 | `invest_functional_validator` | `gpt-5.4` | `medium` | 按 PLAN 的真实场景验证要求测试实际功能 |

## 模型成本策略

- 默认推理强度使用 `medium`，作为“标准”速度/质量档，避免长期 PLAN 执行中默认高推理造成 token 放大。
- 原使用 `gpt-5.5` 的管理、架构和功能验证角色统一降为 `gpt-5.4`。
- 高频、短时、偏命令验证的 `invest_code_quality_checker` 使用 `gpt-5.3-codex-spark`。
- 真实代码实现的 `invest_feature_programmer` 保留 `gpt-5.3-codex`，但推理强度降为 `medium`；只有明确的长时复杂编码任务才临时升级。
- 若 future task 是“次数多但每个任务很短”的临时 worker，可优先用 `gpt-5.3-codex-spark`；涉及复杂架构、受保护契约或实际功能判断时不要默认用 Spark。

配置文件位置：

```text
.codex/agents/
```

当前文件：

```text
invest_project_director.toml
invest_project_summarizer.toml
invest_agent_architecture_builder.toml
invest_feature_programmer.toml
invest_code_quality_checker.toml
invest_functional_validator.toml
```

## 标准工作流

```text
invest_project_director
  -> 更新 active PLAN 的真实场景验证计划
  -> 安排 Group 2 和 Group 3
  -> Group 2 执行架构/代码工作
  -> Group 3 执行代码质量检查
  -> Group 3 执行真实功能验证
  -> invest_project_summarizer 在 PLAN 完成后总结
  -> 判断是否需要更新 Group 2/3 能力
```

## Group 1: 管理层

### `invest_project_director`

使用时机：

- 每个非简单 PLAN-driven 任务开始时。
- 用户说“开始实施PLAN”“执行PLAN”“实施当前PLAN”时。
- 需要进入一个 active PLAN 的下一阶段时。

主要职责：

- 读取 `AGENTS.md`、`.agent/STATUS.md` 和 active PLAN。
- 理解项目当前状态、PLAN 当前阶段和约束。
- 在 Group 2 开始前，把“真实场景验证计划”写入 active PLAN。
- 把当前阶段拆成明确的 worker 任务。
- 决定是否需要 `invest_agent_architecture_builder`。
- 决定是否需要 `invest_feature_programmer`。
- 决定是否需要 `invest_code_quality_checker`。
- 决定是否需要 `invest_functional_validator`。
- 更新 PLAN 的 progress、validation、risks、next action。

典型输出：

```text
task_classification:
active_plan_summary:
real_world_validation_plan:
group2_assignments:
group3_assignments:
phase_gates:
risks:
next_action:
```

边界：

- 不直接承担大规模代码实现。
- 不绕过 PLAN。
- 不允许 worker 在没有验证计划的情况下开始实现。

### `invest_project_summarizer`

使用时机：

- PLAN 完成后。
- 某一阶段达到明确 completion gate 后，需要总结影响时。

主要职责：

- 读取 completed PLAN 和验证证据。
- 总结完成了什么、验证了什么、还有什么风险。
- 评估当前 PLAN 对未来项目工作的影响。
- 判断 Group 2 或 Group 3 的 worker 能力是否需要更新。
- 如果不需要更新，明确记录“不需要更新”。
- 建议下一个 active PLAN，或记录当前没有 active long-running PLAN。

典型输出：

```text
completed_plan_summary:
validation_summary:
remaining_risks:
future_project_needs:
worker_capability_update_needed:
recommended_status_update:
```

边界：

- 不为一次性问题重写 worker 角色。
- 不替代 `invest_project_director` 做 active phase 调度。
- 不修改生产代码。

## Group 2: 执行层

### `invest_agent_architecture_builder`

使用时机：

- 任务涉及 agent 架构、harness engineering、编排合同、工具接口、provider 边界、运行日志/trace 设计。

主要职责：

- 设计或搭建 agent 架构。
- 定义 orchestration contract。
- 设计 handoff payload。
- 设计 tool/provider abstraction。
- 搭建 execution scaffolding。
- 把 PLAN-driven validation hook 接入架构。
- 保持后续可迁移到 MCP-style tool adapters。

典型任务：

- 新建 agent 编排层。
- 定义 subagent handoff schema。
- 设计 run trace / execution log 架构。
- 把 prompt-only 路径改为 typed contracts。
- 结构性更新 `.codex/agents/` 或 agent workflow docs。

典型输出：

```text
architecture_intent:
files_changed:
contracts_touched:
validation_run:
risks:
next_architecture_step:
```

边界：

- 不实现无关业务功能。
- 不静默修改 EvidenceBundle、research response、task state 等高风险契约。
- 不把关键架构决策只藏在 prompt 中。

### `invest_feature_programmer`

使用时机：

- 需要完成具体功能、代码、source 检索、工具、API、service、script、测试、bug fix。

主要职责：

- 按 active PLAN 的当前阶段写 scoped production code。
- 遵循项目既有模式。
- 保持改动窄且可验证。
- 实现后报告修改文件、行为变化和验证结果。

典型任务：

- 修改 source retrieval 行为。
- 新增或更新 source/tool adapter。
- 更新 API route。
- 实现 workflow step。
- 修复 parser 或 script。
- 添加 focused tests。

典型输出：

```text
assigned_scope:
files_changed:
behavior_changed:
validation_run:
validation_result:
blockers:
contract_risks:
next_recommendation:
```

边界：

- 不做大范围 speculative refactor。
- 不静默修改高风险契约。
- 不削弱 direct structured adapters 或已有 source 合同。
- 不输出直接证券投资建议。

## Group 3: 验证层

### `invest_code_quality_checker`

使用时机：

- Group 2 完成实现后。
- practical validation 前。
- 需要确认代码是否能跑通基础质量门槛时。

主要职责：

- 运行或指定 `ruff`。
- 运行 `py_compile`。
- 运行 focused `pytest`。
- 根据任务类型运行 `.agent/skills/*` 对应检查。
- 检查 import safety 和 touched-file scope。
- 区分当前改动导致的问题和已有无关问题。

典型输出：

```text
scope_checked:
commands_run:
results:
failures:
pre_existing_unrelated_failures:
required_fixes:
```

边界：

- 不静默修生产代码。
- 不削弱测试。
- 不把未运行的命令说成通过。

### `invest_functional_validator`

使用时机：

- code quality checks 通过后。
- PLAN 中有真实场景验证要求时。
- 需要验证功能是否在真实目标场景中可用时。

主要职责：

- 读取 PLAN 中的 `Real-world validation plan`。
- 执行真实场景验证。
- 使用 API 调用、脚本、worker tick、运行日志、artifact、local demo 等方式观察实际行为。
- 对比 acceptance criteria。
- 反馈是否通过、阻塞在哪里、下一步该怎么验证。

典型输出：

```text
plan_requirement_tested:
commands_or_operations_run:
observed_behavior:
acceptance_result:
evidence_artifacts:
blockers:
next_validation_step:
```

边界：

- 不静默 patch 产品代码。
- 外部依赖缺失时要记录 blocker，不伪造通过。
- 临时运行 artifact 可以生成，但不应默认提交。

## 自动触发规则

当用户说以下任一表达时：

```text
开始实施PLAN
开始实施 PLAN
实施当前PLAN
执行PLAN
```

或等价表达时，默认自动执行：

```text
invest_project_director
  -> Group 2
  -> Group 3
  -> invest_project_summarizer
```

无需用户额外说“按 v2 subagent 工作流”或点名 subagents。

如果当前没有 active PLAN，则先创建或选择合适 PLAN，再继续执行。

## 当前 active PLAN 下的使用方式

当前 active PLAN：

```text
.agent/PLANS/domestic-source-lite-refactor-v1.md
```

当前阶段：

```text
Phase 5: Query-Based Usability Eval and Cost Review
```

如果现在说“开始实施PLAN”，期望流程是：

1. `invest_project_director` 读取 Phase 5，确认 frozen non-production scope。
2. `invest_project_director` 确认或补全 Phase 5 的真实场景验证计划。
3. Group 2 主要使用 `invest_feature_programmer` 实现 eval helper script 和 `data/tmp` artifacts。
4. 如涉及 harness / artifact schema / eval scaffold 结构设计，再使用 `invest_agent_architecture_builder`。
5. `invest_code_quality_checker` 跑 focused ruff、compile、pytest。
6. `invest_functional_validator` 按 10-query set 做可用性、成本、失败透明度验证。
7. PLAN 完成后，`invest_project_summarizer` 总结 Phase 5 和是否需要更新 Group 2/3 能力。

## 最小调用模板

开始当前 PLAN：

```text
开始实施PLAN
```

只让项目总监准备任务：

```text
使用 invest_project_director，读取当前 STATUS 和 active PLAN，补全真实场景验证计划，并安排 Group2/Group3。
```

只做质量检查：

```text
使用 invest_code_quality_checker 检查当前改动。
```

只做实际功能验证：

```text
使用 invest_functional_validator 按 PLAN 的真实场景验证计划执行验证。
```
