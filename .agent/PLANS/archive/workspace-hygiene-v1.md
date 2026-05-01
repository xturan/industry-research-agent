# Plan: Workspace Hygiene v1

Status: completed
Priority: high
Owner: codex/human
Scope: plan hygiene, status handoff, dirty worktree inventory, non-destructive cleanup
Created: 2026-04-28
Last Updated: 2026-04-28

## Objective

Organize the current dirty worktree before starting the next product task.

The goal is not to revert or delete work. The goal is to make the repository state explicit enough that future PLAN execution can distinguish:

- completed plans that should be archived;
- plans awaiting human review;
- queued future plans that are not created yet;
- production/source/research changes that belong to completed work but remain uncommitted;
- unrelated dirty files that need later review.

## Task Classification

Primary area: `eval_policy_ops`

Secondary areas:

- `docs_only`
- `memory_feedback`
- `task_substrate`

## Scope

In scope:

- Archive completed PLAN files from `.agent/PLANS/` into `.agent/PLANS/archive/`.
- Keep human-review-pending PLAN files visible in `.agent/PLANS/`.
- Add a PLAN index showing active, pending-review, queued, and archived plans.
- Add a dirty worktree inventory artifact under `.agent/`.
- Update `.agent/STATUS.md` so it no longer points to a completed PLAN as the active execution path.

Out of scope:

- `git reset`, `git checkout --`, or deleting user work.
- Staging or committing files.
- Reverting production code.
- Changing protected product contracts.
- Running broad production tests for documentation-only hygiene.

## Constraints

- This is a non-destructive cleanup.
- Do not remove or rewrite production changes.
- Do not persist credentials.
- Treat existing dirty/untracked production files as work to classify, not work to discard.

## Phases

### Phase 0: Inventory

Acceptance:

- Current dirty/untracked state is inspected.
- PLAN status categories are identified.

Validation:

- `git status --short`
- `git diff --stat`
- `.agent/PLANS` status scan

Current state:

- completed

### Phase 1: PLAN Archive And Index

Acceptance:

- Completed PLAN files are moved to `.agent/PLANS/archive/`.
- Pending human-review PLAN files remain in `.agent/PLANS/`.
- `.agent/PLANS/INDEX.md` records the current state.

Validation:

- `.agent/PLANS` root contains only active/pending/index files.
- archive contains completed plans.

Current state:

- completed

### Phase 2: Dirty Worktree Inventory

Acceptance:

- Dirty files are grouped by likely ownership and next action.
- No file is deleted or reverted.

Validation:

- inventory artifact exists and references current `git status` categories.

Current state:

- completed

### Phase 3: STATUS Handoff

Acceptance:

- `.agent/STATUS.md` says there is no active long-running PLAN, unless the user selects one.
- Next recommended action is explicit.

Validation:

- status and index contain no stale instruction to execute completed plans.

Current state:

- completed

## Continue Rule

Continue through all phases if validation passes and no destructive action is required.

## Stop Conditions

Stop and ask before:

- deleting files;
- reverting code;
- staging or committing;
- moving a PLAN that is still awaiting human review;
- changing `AGENTS.md`;
- changing production code.

## Validation Loop

Required checks:

```powershell
git status --short
Select-String -Path .agent\PLANS\*.md -Pattern "^Status:"
Get-ChildItem .agent\PLANS -File
Get-ChildItem .agent\PLANS\archive -File
```

## Progress

- 2026-04-28: Created workspace hygiene PLAN after user requested dirty worktree organization before future work. Inventory found broad dirty worktree, completed PLANs left in root, and queued future PLAN names not yet created.
- 2026-04-28: Archived completed PLAN files to `.agent/PLANS/archive/`, leaving only `agentic-operating-system-v2.md`, `workspace-hygiene-v1.md`, and `INDEX.md` in `.agent/PLANS/` during execution.
- 2026-04-28: Created `.agent/PLANS/INDEX.md` and `.agent/WORKTREE_INVENTORY.md`.
- 2026-04-28: Updated `.agent/STATUS.md` to show no active long-running PLAN and to point future work at the PLAN index and worktree inventory.
- 2026-04-28: Completed this PLAN; it should be moved to `.agent/PLANS/archive/`.

## Risks

- Dirty production files remain uncommitted and cannot be attributed perfectly without a clean baseline.
- Moving PLAN files changes paths referenced by older STATUS notes; INDEX and STATUS must preserve discoverability.
- Repo-wide ruff may still fail because historical `data/tmp` scratch scripts remain in tree.

## Next Action

No execution action remains. Select the next active PLAN only after reviewing `.agent/PLANS/INDEX.md` and `.agent/WORKTREE_INVENTORY.md`.
