# Plan: Review-Gated Agent Workflow Plugin Implementation v1

Status: completed
Priority: high
Owner: codex/human
Scope: docs_only
Created: 2026-06-30
Last Updated: 2026-06-30

## Objective

Implement the open-source plugin skeleton for the review-gated agent workflow:

- Codex plugin manifest;
- reusable `SKILL.md` files;
- explicit-only skill metadata for PRD workflow and group2-design;
- hook definitions and conservative hook scripts;
- reusable templates;
- plugin README;
- lightweight validation script.

This PLAN turns the previously completed design documentation into a concrete
repository package shape without changing production product code or protected
research workflow contracts.

## Task Classification

Primary area: `docs_only`

Secondary areas:
- `task_substrate`
- `eval_policy_ops`
- `memory_feedback`

High-risk contracts:
- Do not change EvidenceBundle, citations, source quality, task/job status,
  run/run_steps, public API response shapes, or delivery contracts.
- Do not replace existing project-specific `invest_*` workflow.
- Do not enable hooks globally; create plugin-bundled hook files only.

## Background Reused

- `.agent/PLANS/archive/review-gated-agent-workflow-open-source-v1.md`
- `docs/workflows/review-gated-agent-workflow.md`
- `docs/workflows/open-source-package-format.md`
- `docs/workflows/skill-contracts.md`
- `docs/workflows/hook-scope-guard.md`
- `docs/workflows/project-integration-notes.md`
- `examples/generic-saas-feature/`
- Official Codex plugin guidance checked during the prior PLAN.

## Scope

In scope:
- Create `plugins/review-gated-agent-workflow/`.
- Create `.codex-plugin/plugin.json`.
- Create skill directories and `SKILL.md` files:
  - `prd-workflow`
  - `brainstorm`
  - `prd-html-review`
  - `plan-from-prd`
  - `group2-design`
  - `workflow-scope-guard`
- Create explicit-only `agents/openai.yaml` for `prd-workflow` and
  `group2-design`.
- Create hook files and scope-rule templates.
- Create template files for PRD/RPD, PLAN, Group2 design, and scope rules.
- Create plugin README and validation script.
- Run file/content validation and a lightweight Python validation script.

Out of scope:
- No production code changes.
- No installation into a real Codex marketplace unless the user asks later.
- No global hook activation.
- No live provider calls.
- No project-specific worker migration.

## Constraints

- Plugin contents must remain universal and project-independent.
- `prd-workflow` and `group2-design` must be explicit-only.
- Hook scripts must be conservative and should not auto-enter PRD workflow.
- Scripts should be lightweight, local, and dependency-free.
- Keep plugin manifest minimal and valid.
- Do not edit unrelated dirty worktree files.

## Architecture / Design Direction

Target package:

```text
plugins/review-gated-agent-workflow/
  README.md
  .codex-plugin/plugin.json
  skills/
  hooks/
  scripts/
  templates/
  assets/
```

Hook scripts are designed as conservative validators:

- `scope_preflight.py`: checks optional environment-provided stage and target
  path against scope rules.
- `diff_postflight.py`: checks changed paths passed through args or stdin.
- `stop_gate_check.py`: checks a lightweight run-state file when present.

If no stage/run-state is provided, scripts should warn/no-op rather than block.

## Milestones

### Milestone 0: Plan And Handoff

Acceptance:
- PLAN exists.
- STATUS points to this PLAN.

Validation:
- `Test-Path .agent\PLANS\review-gated-agent-workflow-plugin-implementation-v1.md`
- `Select-String -Path .agent\STATUS.md -Pattern "review-gated-agent-workflow-plugin-implementation-v1"`

### Milestone 1: Plugin Skeleton And Manifest

Acceptance:
- Plugin root exists.
- `.codex-plugin/plugin.json` exists.
- Plugin README exists.
- Manifest includes `name`, `version`, `description`, and `skills`.

Validation:
- File existence checks.
- JSON parse check.

### Milestone 2: Skill Files

Acceptance:
- All six `SKILL.md` files exist.
- `prd-workflow` and `group2-design` include explicit-only metadata.
- Each skill includes use/skip rules, inputs, outputs, scope boundaries, and
  stop conditions.

Validation:
- File existence checks.
- Content checks for front matter and explicit-only metadata.

### Milestone 3: Hooks And Scope Templates

Acceptance:
- `hooks/hooks.json` exists.
- Hook scripts exist.
- `templates/hook_scope_rules.yaml` exists.
- Scripts default to warn/no-op when context is missing.

Validation:
- Python compile checks.
- Script smoke checks.

### Milestone 4: PRD/PLAN/Group2 Templates

Acceptance:
- `templates/prd_review.md`
- `templates/prd_review.html`
- `templates/plan.md`
- `templates/group2_design.md`

Validation:
- File existence and content checks.

### Milestone 5: Package Validation

Acceptance:
- `scripts/validate_plugin_package.py` validates the package.
- Validation passes locally.
- PLAN and STATUS record results.

Validation:
- `python plugins\review-gated-agent-workflow\scripts\validate_plugin_package.py plugins\review-gated-agent-workflow`

## Continue Rule

Continue automatically across milestones when validation passes and no protected
contract or permission blocker appears.

## Stop Conditions

Stop only when:
- plugin file writes are blocked;
- validation repeatedly fails without a safe fix;
- implementation would require changing production code or protected contracts;
- user pauses or changes the goal.

## Done Condition

The PLAN is complete when:
- plugin skeleton exists;
- skills, hooks, scripts, and templates exist;
- explicit-only policies are present;
- validation script passes;
- STATUS and PLAN record results;
- remaining risks are recorded.

## Progress

- [x] Milestone 0: Plan And Handoff
- [x] Milestone 1: Plugin Skeleton And Manifest
- [x] Milestone 2: Skill Files
- [x] Milestone 3: Hooks And Scope Templates
- [x] Milestone 4: PRD/PLAN/Group2 Templates
- [x] Milestone 5: Package Validation

## Current Milestone

Completed.

## Validation Snapshot

- `python plugins\review-gated-agent-workflow\scripts\validate_plugin_package.py plugins\review-gated-agent-workflow`
  -> PASS.
- `python -m py_compile plugins\review-gated-agent-workflow\hooks\scope_preflight.py plugins\review-gated-agent-workflow\hooks\diff_postflight.py plugins\review-gated-agent-workflow\hooks\stop_gate_check.py plugins\review-gated-agent-workflow\scripts\validate_plugin_package.py`
  -> passed.
- Hook smoke:
  - brainstorm writing `docs/prd/foo/brainstorm.md` -> `decision=pass`.
  - brainstorm writing `packages/foo.py` -> `decision=block`.

## Risks

- Hook scripts may look enforceable before installation/trust. Mitigation:
  document warn/no-op defaults and do not install globally.
- Plugin manifest schema could reject unsupported fields. Mitigation: keep
  manifest minimal.
- Dirty worktree has unrelated existing changes. Mitigation: only modify plugin
  package, PLAN, and STATUS.

## Next Action

Archive this PLAN. If the user wants installation/testing in Codex, create a
separate PLAN for marketplace wiring and hook trust review.

## Completion Report

What was done:
- Created a plugin-first package under `plugins/review-gated-agent-workflow/`.
- Added plugin manifest and README.
- Added six reusable skills.
- Added explicit-only skill metadata for `prd-workflow` and `group2-design`.
- Added hook config, conservative hook scripts, and scope-rule template.
- Added PRD/RPD, PLAN, and Group2 design templates.
- Added package validation script.

Implemented capability:
- The workflow is now represented as an installable/copyable Codex plugin
  package, not only as design documentation.

Concrete validation cases:
- Package structure validates.
- Python hook/scripts compile.
- Allowed brainstorm write passes preflight.
- Forbidden brainstorm write to production code blocks preflight.

Before / after examples:
- Before: the workflow existed only as docs and examples.
  After: it has plugin manifest, skills, hooks, templates, and validation.
- Before: hook scope guard was design-only.
  After: hook scripts can warn/pass/block based on stage and target paths.

Remaining risks / TODOs:
- Plugin is not installed into a Codex marketplace.
- Hook command paths may need adjustment after real plugin installation.
- Hook scripts use a small YAML subset parser, enough for current template but
  not a general YAML implementation.
