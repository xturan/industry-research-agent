# Execution Mode Router And Technical Roadmap v1

Status: completed

Created: 2026-04-30

Completed: 2026-04-30

Primary active PLAN: no

## Objective

Add a speed-biased execution routing layer before subagent dispatch and initialize a durable technical-route evolution document.

## Scope

In scope:

- Add project-native execution mode router skill.
- Update skill router and subagent contract to preserve full v2 workflow only when needed.
- Update `AGENTS.md` PLAN trigger so execution first routes through the new mode selector.
- Add `docs/technical-roadmap-evolution.md` with key historical technical decisions.

Out of scope:

- Production code changes.
- Source-layer implementation.
- Live Tavily or DeepSeek validation.
- Changing EvidenceBundle, citation, provider, task, or public response contracts.

## Execution Mode

Mode: `local_direct`

Reason: governance/docs-only update with explicit user approval for speed-biased default.

Risk triggers: changes agent execution behavior but not production contracts.

Allowed write scope:

- `.agent/skills/execution-mode-router.md`
- `.agent/SKILL_ROUTER.md`
- `.agent/skills/subagent-gate-contract.md`
- `AGENTS.md`
- `docs/technical-roadmap-evolution.md`
- `.agent/PLANS/archive/execution-mode-router-tech-roadmap-v1.md`
- `.agent/PLANS/INDEX.md`
- `.agent/STATUS.md`

Forbidden changes:

- `packages/**`
- `tests/**`
- source/evidence/provider/research public contracts

Required validation:

- File existence and section checks.
- Router keyword checks.
- Secret-prefix scan for touched governance/docs files.

## Progress

- Added `.agent/skills/execution-mode-router.md`.
- Updated `.agent/SKILL_ROUTER.md` to route PLAN execution through execution mode selection.
- Updated `.agent/skills/subagent-gate-contract.md` so full subagent workflow is selected by router or explicit plan requirement, not the default first step.
- Updated `AGENTS.md` PLAN implementation trigger rule to use a speed-biased router.
- Added `docs/technical-roadmap-evolution.md` with initialized technical-route history.

## Validation

Completed:

- `Select-String -Path .agent\skills\execution-mode-router.md -Pattern 'Purpose','Use when','Skip when','Authority','Inputs','Process','Outputs','Validation','Red flags','Completion note','local_direct','light_subagent','full_subagent','remediation_gate'` -> pass.
- `Select-String -Path .agent\SKILL_ROUTER.md,.agent\skills\subagent-gate-contract.md,AGENTS.md -Pattern 'execution-mode-router','local_direct','light_subagent','full_subagent','remediation_gate','speed-biased'` -> pass.
- `Select-String -Path docs\technical-roadmap-evolution.md -Pattern 'Last updated','Problem','Decision','Method','Output','2026-04-30','Execution Mode','Source Strategy','Evidence Quality'` -> pass.
- Secret-prefix scan for touched governance/docs files with `tvly-` / `sk-` -> no matches.

## Risks

- The active source PLAN remains pending; this sidecar governance update must not be mistaken for source remediation execution.
- The timeline is initialized from current PLAN/STATUS artifacts and may need human correction if earlier historical details should be expanded.

## Next Action

Use execution mode router for the next source remediation step. Default to `light_subagent` or `local_direct` unless protected source/provider/evidence boundary triggers require `full_subagent`.
