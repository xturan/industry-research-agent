---
name: task-flow-check
description: Use when task substrate, worker behavior, async jobs, retry semantics, run/run_step lifecycle, task status, queue processing, or task API behavior may be changed.
---

# Task Flow Check

Use this native wrapper to surface the task/worker flow gate when execution semantics, retries, run state, or async job behavior may be affected.

Authoritative source: .agent/skills/task-flow-check.md

Follow the authoritative `.agent` skill and the active PLAN. Preserve existing task status semantics unless an active PLAN explicitly authorizes a migration.

Do not duplicate or reinterpret the full rule body here.
