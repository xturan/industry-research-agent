# Skill: director-remediation-gate

## Purpose

Use this skill when a PLAN execution encounters a blocker, validation failure, ambiguous requirement, external-provider issue, or scope problem.

This gives Group 1 / `invest_project_director` limited authority to adjust the execution path without silently changing the user's product goal.

## Use when

Use this skill when:

- A worker reports that implementation cannot proceed as planned.
- Code-quality or functional validation fails.
- Offline tests pass but live/provider behavior fails.
- A task requires a narrower remediation gate.
- A dirty worktree prevents clean scope proof.
- The current phase's route is wrong but the user goal remains valid.
- A potential protected-contract change is discovered during execution.

## Skip when

Skip this skill when:

- The fix is a small local correction inside the current worker's authorized scope.
- The active PLAN already contains a remediation gate for the exact failure.
- The user explicitly changes the product goal, which requires a Design Brief or PLAN update.

## Authority

Group 1 may change:

- Phase sequencing.
- Worker assignments.
- Validation strategy.
- Remediation gates.
- Allowed write scope inside the existing user goal.
- Fallback route if the original route fails safely.

Group 1 may not silently change:

- User's product goal.
- Protected contracts.
- Public response shapes.
- Source routing semantics.
- Task/job status semantics.
- Evidence/citation contracts.
- Superpowers authority boundaries.

## Inputs

- `.agent/STATUS.md`
- active `.agent/PLANS/<plan>.md`
- failing command, validation report, worker summary, or run trace
- relevant module-specific check skill

## Failure classes

- `implementation_bug`
- `validation_failure`
- `environment_or_dependency`
- `external_api_volatility`
- `ambiguous_requirement`
- `scope_overreach`
- `protected_contract_risk`
- `dirty_worktree_scope_risk`
- `case_design_gap`

## Process

1. Capture the failure evidence.
2. Classify the failure.
3. Decide whether the user goal remains unchanged.
4. If unchanged, write a narrow remediation gate into the PLAN.
5. Freeze allowed write scope and forbidden paths.
6. Assign the smallest needed worker or validator.
7. Require fresh validation before phase completion.
8. Update `.agent/STATUS.md`.

## Outputs

The remediation gate should include:

- Reason for reopening or pausing the phase.
- Failure class.
- Allowed write scope.
- Protected contracts.
- Required fix.
- Required validation.
- Acceptance criteria.
- Next action.

## Validation

- PLAN contains the remediation gate before implementation continues.
- STATUS reflects blocked/remediation state.
- The user goal did not change silently.
- Protected-contract changes are blocked unless explicitly authorized.
- Group 3 validates after remediation.

## Red flags

- Calling a goal change a "small remediation".
- Letting Group 2 expand scope to make tests pass.
- Treating external API volatility as a reason to weaken evidence standards.
- Skipping Group 3 after remediation.
- Editing protected contracts because the planned path was inconvenient.

## Completion note

Record the remediation outcome in the PLAN and STATUS:

- failure class
- change made to the execution path
- validation result
- remaining risk
