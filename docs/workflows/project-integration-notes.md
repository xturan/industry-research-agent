# Project Integration Notes

Status: draft
Audience: maintainers adapting the universal workflow to this repository
Scope: compatibility notes, not production behavior changes

## Purpose

This document explains how the universal review-gated workflow can coexist with
this repository's current project-bound agent system.

It does not replace existing `invest_*` subagents or active research workflow
contracts. It provides a compatibility map for future adoption.

## Current Project System

The current project already has project-bound roles and governance skills:

- `invest_project_director`
- `invest_project_summarizer`
- `invest_agent_architecture_builder`
- `invest_feature_programmer`
- `invest_code_quality_checker`
- `invest_functional_validator`

It also has supporting skills:

- `.agent/skills/execution-mode-router.md`
- `.agent/skills/subagent-gate-contract.md`
- `.agent/skills/group2-worker-lane-design.md`
- `.agent/skills/tdd-policy.md`
- `.agent/skills/real-world-case-design.md`

These remain valid for this repository unless a later approved PLAN explicitly
migrates them.

## Universal-To-Project Mapping

| Universal role | Current project role | Notes |
|---|---|---|
| `workflow-director` | `invest_project_director` | Same responsibility: read PLAN/STATUS, refine validation, assign workers, control phase transitions. |
| `workflow-summarizer` | `invest_project_summarizer` | Same responsibility: evaluate completed PLAN and whether capabilities need updates. |
| `architecture-builder` | `invest_agent_architecture_builder` | Same architecture/boundary role; current project has stronger source/research contract constraints. |
| `feature-implementer` | `invest_feature_programmer` | Same concrete implementation role; current project may add lane-specific role cards. |
| `code-quality-validator` | `invest_code_quality_checker` | Same code-quality gate responsibility. |
| `functional-validator` | `invest_functional_validator` | Same practical validation responsibility. |

## Compatibility Rules

1. Universal workflow docs should use universal names.
2. This project's active PLAN may map universal names to `invest_*` names.
3. Existing `invest_*` roles should not be deleted during open-source workflow
   work.
4. Project-specific constraints in `AGENTS.md` and `.agent/STATUS.md` remain
   higher authority inside this repository.
5. The universal PRD workflow remains explicit-only even in this repository.
6. `group2-design` remains explicit-only and must use multi-round human review.

## Current Project Adoption Path

Recommended incremental adoption:

1. Keep current `invest_*` roles unchanged.
2. Add universal docs and examples under `docs/workflows/`.
3. Add plugin-first package skeleton only after docs are reviewed.
4. Create universal skills as plugin contents before changing project-local
   `.agent/skills`.
5. If project-local skills need updates, run a dedicated PLAN and review gate.
6. If executable hooks are added, start in warn-only mode.

## What Must Not Change In This PLAN

This workflow documentation PLAN must not change:

- EvidenceBundle shape;
- citation structure;
- source quality fields;
- research analyze response shape;
- task/job status semantics;
- run/run_steps meaning;
- content asset metadata contract;
- delivery state transitions;
- existing source/provider routing behavior.

## Project-Specific Group2 Note

The current `.agent/skills/group2-worker-lane-design.md` is project-bound and
more specific than the universal workflow. It uses lanes such as:

- `system_contract_architect`
- `source_provider_integrator`
- `research_workflow_implementer`
- `eval_harness_implementer`

These should remain project-specific examples of what `group2-design` can
produce. They should not be copied into the universal plugin as defaults.

## Future Migration Option

A future PLAN may create:

```text
plugins/review-gated-agent-workflow/
  skills/
  hooks/
  scripts/
  templates/
```

Then this repository can either:

- install the plugin and keep project-bound `invest_*` mappings locally; or
- copy selected skills into `.agent/skills/` after review; or
- maintain both, with project-local rules taking precedence.

## Validation For This Integration Note

This document is valid when:

- universal and project-bound names are clearly separated;
- the existing `invest_*` system is preserved;
- no production contracts are changed;
- adoption is described as incremental and review-gated;
- future hook behavior is not presented as already enforced.
