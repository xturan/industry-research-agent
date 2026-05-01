---
description: "Route execution: choose local_direct, light_subagent, full_subagent, or remediation_gate based on task risk. Use before implementing a PLAN or non-trivial task."
argument-hint: "[task description]"
---

# Workflow Execution Router

Read `.agent/skills/execution-mode-router.md` and `.agent/skills/subagent-gate-contract.md` for full rules.

## Quick Route Selection

| Mode | Use for | Required validation |
|---|---|---|
| `local_direct` | Docs, scripts, isolated tests, low-risk config/report updates | Focused checks, update PLAN/STATUS |
| `light_subagent` | Single module implementation, no protected-contract change | Implementation worker, code-quality gate |
| `full_subagent` | Cross-module, protected-contract risk, source/provider/research boundary changes | Full director → Group2 → Group3 flow |
| `remediation_gate` | Failed live/eval gate, user goal unchanged | Narrow fix, fresh validation |

## Process

1. Classify the task area and write scope
2. Check whether the active PLAN already names an execution mode
3. Check hard escalation triggers:
   - EvidenceBundle, citation, research response, provider abstraction, task status, run lifecycle changes
   - Source routing/provider semantics changes across modules
   - New source/provider integration path
   - Multiple Group2 lanes must coordinate
   - Live validation failure suggesting boundary/contract/case-design problems
   - Material user-facing research conclusion risk
4. Choose the lightest safe mode
5. Run mode-specific workflow and validation
6. Escalate if validation fails twice for the same failure class

## Subagent Gate Contract (full_subagent only)

```
Director (invest_project_director)
  → freeze phase objective and validation
  → Architecture Gate when lane triggers apply
  → assign Group 2 task-specific worker instances
  → Group 2 implements within lane write scope
  → Group 3 code-quality validation (invest_code_quality_checker)
  → Group 3 functional validation (invest_functional_validator)
  → director records phase transition
  → invest_project_summarizer after final done condition
```

Group2 lanes:
- `system_contract_architect` → invest_agent_architecture_builder
- `source_provider_integrator` → invest_feature_programmer
- `research_workflow_implementer` → invest_feature_programmer
- `eval_harness_implementer` → invest_feature_programmer

## Output

Record: Mode, Reason, Risk triggers, Allowed write scope, Forbidden changes, Required validation, Escalation rule.
