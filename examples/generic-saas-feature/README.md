# Generic SaaS Feature Example

This example shows how the review-gated agent workflow handles a generic SaaS
feature without binding to any specific project domain.

Feature:

```text
Team task board with assignment, status changes, and due-date filtering.
```

Explicit trigger:

```text
$prd-workflow 为团队任务看板功能生成可审阅 PRD
```

Non-triggers:

```text
帮我修复任务列表排序 bug
解释 task service 的权限判断
跑一下任务模块测试
继续执行 PLAN
```

Expected route:

1. Gate A: confirm feature frame.
2. Gate B: brainstorm.
3. Gate C: generate PRD/RPD.
4. Gate D: human PRD review.
5. Gate E: optional `group2-design`.
6. Gate F: create PLAN from approved PRD.
7. Gate G: human PLAN review.
8. Gate H: wait for explicit PLAN implementation command.
9. PLAN execution phases begin only after approval.

Files:

- `prd_review.md`
- `plan.md`
- `group2_design.md`
- `validation.md`
