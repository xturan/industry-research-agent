---
name: execution-mode-router
description: Use when starting, continuing, or resuming PLAN execution; choosing between local_direct, light_subagent, remediation_gate, and full_subagent; or deciding whether a task should escalate to the full agent workflow.
---

# Execution Mode Router

Use this native wrapper to surface the project route-selection gate before non-trivial PLAN execution.

Authoritative source: .agent/skills/execution-mode-router.md

Follow the authoritative `.agent` skill and the active PLAN. Prefer the lightest safe execution mode, and escalate only when protected contracts, source/provider/research boundaries, failed live gates, or multi-lane coordination require it.

Do not duplicate or reinterpret the full rule body here.
