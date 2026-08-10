# Validation Example: Team Task Board

Status: example

## Trigger Dry Run

| Prompt | Expected |
|---|---|
| `$prd-workflow 为团队任务看板功能生成可审阅 PRD` | Enter PRD workflow. |
| `为这个项目设计 Group2` | Enter explicit group2-design. |
| `帮我修复任务列表排序 bug` | Normal Codex workflow. |
| `继续执行 PLAN` | PLAN execution route, not PRD workflow. |

## Functional Cases

| Case | Type | Pass Criteria |
|---|---|---|
| TC-001 | primary_success_case | Valid task creates in `todo`. |
| TC-002 | negative_control | Missing title returns validation error. |
| TC-003 | primary_success_case | Combined filters return only matching tasks. |
| TC-004 | negative_control | Forbidden transition is rejected. |

## Gate Checks

- PRD review required before PLAN creation.
- PLAN review required before implementation.
- Group2 cannot edit PLAN.
- Group3 cannot silently patch production code.
- Phase status appears only after PLAN execution begins.
