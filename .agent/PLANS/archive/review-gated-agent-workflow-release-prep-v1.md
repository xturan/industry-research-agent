# Plan: Review-Gated Agent Workflow Release Prep v1

Status: completed
Priority: medium
Owner: codex/human
Scope: docs_only
Created: 2026-07-01
Last Updated: 2026-07-01

## Objective

Prepare the review-gated agent workflow plugin for GitHub-style release by
adding plugin-local release documentation, license, changelog, contributing
guide, installation instructions, release checklist, and a repo marketplace
example.

## Task Classification

Primary area: `docs_only`

Secondary areas:
- `task_substrate`
- `eval_policy_ops`

High-risk contracts:
- Do not change production code.
- Do not change research workflow contracts.
- Do not globally install or trust hooks.
- Do not overwrite the repository's existing root README.

## Background Reused

- `plugins/review-gated-agent-workflow/`
- `.agent/PLANS/archive/review-gated-agent-workflow-open-source-v1.md`
- `.agent/PLANS/archive/review-gated-agent-workflow-plugin-implementation-v1.md`
- `docs/workflows/open-source-package-format.md`

## Scope

In scope:
- Add plugin-local `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`.
- Add plugin-local docs for installation, hook trust, and release checklist.
- Add `.agents/plugins/marketplace.json` as a repo marketplace example.
- Add validation for release docs and marketplace JSON.
- Update PLAN/STATUS and archive when done.

Out of scope:
- Publishing to GitHub.
- Running `codex plugin marketplace add`.
- Installing or trusting hooks.
- Rewriting root `README.md`.

## Milestones

### Milestone 0: Plan And Handoff

Acceptance:
- PLAN exists and STATUS points to it.

### Milestone 1: Release Docs

Acceptance:
- Plugin-local license, changelog, contributing guide, installation docs, hook
  trust docs, and release checklist exist.

### Milestone 2: Marketplace Example

Acceptance:
- `.agents/plugins/marketplace.json` exists and points to
  `./plugins/review-gated-agent-workflow`.
- JSON parses successfully.

### Milestone 3: Validation And Archive

Acceptance:
- Release docs exist.
- Marketplace JSON parses.
- Plugin package validation still passes.
- PLAN archived and STATUS updated.

## Validation

- `python plugins\review-gated-agent-workflow\scripts\validate_plugin_package.py plugins\review-gated-agent-workflow`
- JSON parse for `.agents/plugins/marketplace.json`
- File existence checks for release docs.

## Progress

- [x] Milestone 0: Plan And Handoff
- [x] Milestone 1: Release Docs
- [x] Milestone 2: Marketplace Example
- [x] Milestone 3: Validation And Archive

## Current Milestone

Completed.

## Validation Snapshot

- `python plugins\review-gated-agent-workflow\scripts\validate_plugin_package.py plugins\review-gated-agent-workflow`
  -> PASS.
- `python -c "import json, pathlib; json.loads(pathlib.Path('.agents/plugins/marketplace.json').read_text(encoding='utf-8')); print('marketplace json ok')"`
  -> `marketplace json ok`.
- `Test-Path` for release docs returned `True` for all required files:
  - `LICENSE`
  - `CHANGELOG.md`
  - `CONTRIBUTING.md`
  - `docs/installation.md`
  - `docs/hook-trust.md`
  - `docs/release-checklist.md`

## Risks

- Marketplace path semantics may differ by installation context. Mitigation:
  document this as a repo marketplace example, not an installed state.
- Hook trust review remains manual. Mitigation: document that hooks are not
  active until installed and trusted.

## Next Action

Archive this PLAN. If the user wants a real GitHub release next, create a
separate release/publication task for repository extraction, remote creation,
tagging, and publication.

## Completion Report

What was done:
- Added plugin-local release files:
  - `LICENSE`
  - `CHANGELOG.md`
  - `CONTRIBUTING.md`
  - `docs/installation.md`
  - `docs/hook-trust.md`
  - `docs/release-checklist.md`
- Added repo marketplace example:
  - `.agents/plugins/marketplace.json`

Implemented capability:
- The plugin package now has release-ready metadata and a repo marketplace
  example for installation documentation.

Concrete validation cases:
- Plugin package validation passes.
- Marketplace JSON parses.
- Required release docs exist.

Before / after examples:
- Before: plugin package existed but lacked public release docs.
  After: package includes license, changelog, contribution rules, install docs,
  hook trust notes, and release checklist.
- Before: marketplace shape was only described in docs.
  After: `.agents/plugins/marketplace.json` provides a concrete repo example.

Remaining risks / TODOs:
- The plugin is not published to GitHub.
- The marketplace has not been added through Codex CLI.
- Hooks have not been trusted or enabled in Codex.
