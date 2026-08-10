# Review-Gated Agent Workflow

This Codex plugin packages a universal workflow for feature work that should
start with explicit PRD design and human review.

## What It Provides

- Explicit PRD workflow entry.
- Brainstorm and PRD/RPD review artifact flow.
- Human PRD review gate.
- PLAN creation only after PRD approval.
- Human PLAN review gate.
- PLAN execution phase status model.
- Multi-round `group2-design`.
- Conservative hook scope guard templates and scripts.
- Reusable PRD, PLAN, Group2 design, and scope-rule templates.

## Explicit-Only Policy

The heavyweight entry points are explicit-only:

- `prd-workflow`
- `group2-design`

They should not trigger for ordinary coding, test, review, or explanation
requests.

Valid prompts:

```text
$prd-workflow 为导入 CSV 功能生成可审阅 PRD
$group2-design 为这个项目设计 Group2
```

Non-triggers:

```text
帮我修这个 bug
继续执行 PLAN
跑一下测试
解释这个模块
帮我 review 这个 diff
```

## Package Layout

```text
review-gated-agent-workflow/
  .codex-plugin/plugin.json
  skills/
  hooks/
  scripts/
  templates/
  assets/
```

## Hook Safety

Hook scripts are conservative. If workflow stage information is missing, they
warn or no-op rather than blocking. They do not auto-enter PRD workflow.

## Validation

Run from the repository root:

```powershell
python plugins\review-gated-agent-workflow\scripts\validate_plugin_package.py plugins\review-gated-agent-workflow
```
