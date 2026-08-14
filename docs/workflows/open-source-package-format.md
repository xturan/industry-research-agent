# Open Source Package Format

Status: draft
Audience: maintainers publishing the workflow to GitHub
Scope: plugin-first distribution format

## Recommendation

Publish this workflow as a Codex plugin-first repository.

Use the plugin as the primary installable unit because the workflow is more than
a set of standalone subagents. It includes:

- skills;
- hook definitions;
- scripts;
- templates;
- reviewable PRD/RPD assets;
- examples;
- package-level documentation.

Standalone skills are still useful for authoring and local copying, but the
open-source repository should treat them as plugin contents rather than the top
level product.

## Why Plugin-First

Use plugin-first when:

- multiple skills must work together;
- lifecycle hooks are part of the workflow;
- scripts or templates are required;
- the workflow should be installed by teams;
- examples and assets should travel with the workflow;
- future versions need a stable package identity.

Use copy-only skills when:

- the workflow is personal or repo-local;
- there is only one instruction-only skill;
- hooks and scripts are not needed;
- the user wants to inspect or adapt files manually.

This project needs the first path. The repository can still expose copyable
folders as a fallback.

## Repository Layout

Recommended GitHub repository:

```text
review-gated-agent-workflow/
  README.md
  LICENSE
  CHANGELOG.md
  CONTRIBUTING.md

  docs/
    workflow-overview.md
    review-gates.md
    plan-phase-status.md
    group2-design.md
    hook-scope-policy.md
    plugin-installation.md
    examples.md

  plugins/
    review-gated-agent-workflow/
      .codex-plugin/
        plugin.json

      skills/
        prd-workflow/
          SKILL.md
          agents/
            openai.yaml
        brainstorm/
          SKILL.md
        prd-html-review/
          SKILL.md
        plan-from-prd/
          SKILL.md
        group2-design/
          SKILL.md
          agents/
            openai.yaml
        workflow-scope-guard/
          SKILL.md

      hooks/
        hooks.json
        scope_preflight.py
        diff_postflight.py
        stop_gate_check.py

      scripts/
        render_prd_html.py
        update_phase_status.py
        validate_scope.py
        validate_plugin_package.py

      templates/
        prd_review.html
        prd_review.md
        plan.md
        group2_design.md
        hook_scope_rules.yaml

      assets/
        workflow.svg
        risk_matrix.svg

  .agents/
    plugins/
      marketplace.json

  examples/
    generic-saas-feature/
      README.md
      prd_review.md
      plan.md
      group2_design.md
    data-pipeline-feature/
      README.md
    ai-agent-feature/
      README.md
```

## Plugin Manifest

Minimal manifest:

```json
{
  "name": "review-gated-agent-workflow",
  "version": "0.1.0",
  "description": "A universal review-gated Codex workflow for explicit PRD design, human review, PLAN creation, scoped implementation, validation, and workflow evolution.",
  "skills": "./skills/"
}
```

Do not add unsupported fields to the manifest. Lifecycle hooks should live in
the plugin's `hooks/hooks.json` and be documented as requiring trust review.

## Marketplace Example

Repo-local marketplace example:

```json
{
  "name": "review-gated-workflows",
  "interface": {
    "displayName": "Review-Gated Workflows"
  },
  "plugins": [
    {
      "name": "review-gated-agent-workflow",
      "source": {
        "source": "local",
        "path": "./plugins/review-gated-agent-workflow"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

## Skill Invocation Policy

The PRD workflow and group design skills must be explicit-only.

Each should include `agents/openai.yaml` like:

```yaml
policy:
  allow_implicit_invocation: false
```

Recommended explicit skills:

| Skill | Trigger policy | Purpose |
|---|---|---|
| `prd-workflow` | explicit-only | Enter the full PRD-to-PLAN review workflow. |
| `group2-design` | explicit-only | Design project-bound Group2 workers through multi-round human dialogue. |
| `brainstorm` | invoked by `prd-workflow` | Create requirement frame, alternatives, risks, and open questions. |
| `prd-html-review` | invoked by `prd-workflow` | Generate reviewable PRD/RPD artifacts. |
| `plan-from-prd` | invoked after PRD approval | Create a PLAN from approved PRD/RPD content. |
| `workflow-scope-guard` | invoked by docs/hooks | Define and audit write boundaries. |

## Hook Packaging

Hooks should be included but conservative by default.

Recommended hook files:

```text
hooks/
  hooks.json
  scope_preflight.py
  diff_postflight.py
  stop_gate_check.py
```

Recommended events:

| Event | Purpose |
|---|---|
| `PreToolUse` | Check whether a requested write target is allowed for the current workflow stage. |
| `PostToolUse` | Audit diffs and detect forbidden file changes. |
| `Stop` | Verify required review gates, phase status, and completion claims before stopping. |

Hook rules:

- Hooks must be concise.
- Hooks must not silently change workflow mode.
- Hooks must not auto-enter PRD workflow.
- Hooks must report violations with a short reason and suggested next action.
- Hooks must be documented as trust-reviewed lifecycle scripts.

## Templates

Templates should be stable, project-independent starting points:

| Template | Purpose |
|---|---|
| `prd_review.html` | Reviewable PRD/RPD shell with diagrams and acceptance tables. |
| `prd_review.md` | Markdown source version of the PRD/RPD. |
| `plan.md` | PLAN skeleton aligned with review-gated workflow. |
| `group2_design.md` | Multi-round group design output format. |
| `hook_scope_rules.yaml` | Stage read/write/forbidden-scope declaration. |

Project-specific examples may fill these templates, but the templates
themselves should avoid domain-specific assumptions.

## Examples

Examples should prove portability. Avoid using only one domain.

Recommended examples:

| Example | Purpose |
|---|---|
| `generic-saas-feature` | Demonstrates ordinary product feature planning. |
| `data-pipeline-feature` | Demonstrates validation and scope guards for data workflows. |
| `ai-agent-feature` | Demonstrates AI behavior, evidence, evaluation, and human review gates. |

Each example should include:

- explicit trigger prompt;
- PRD/RPD artifact;
- approved PLAN outline;
- optional group2-design result;
- phase status example;
- trigger and non-trigger examples.

## README Contract

The top-level `README.md` should explain:

1. what the workflow solves;
2. when to use it;
3. when not to use it;
4. plugin installation;
5. copy-only fallback;
6. explicit invocation examples;
7. group2-design human review model;
8. hook trust and scope guard behavior;
9. repository layout;
10. contribution rules.

## Release Checklist

Before publishing:

- [ ] Plugin manifest validates.
- [ ] `prd-workflow` is explicit-only.
- [ ] `group2-design` is explicit-only.
- [ ] Hooks are documented and trust-review safe.
- [ ] Templates contain no project-specific names.
- [ ] Examples cover at least two domains.
- [ ] README includes non-trigger examples.
- [ ] License is selected.
- [ ] CHANGELOG has initial release notes.
- [ ] CONTRIBUTING explains how to add skills, hooks, and examples.

## What Not To Publish As The Main Format

Do not publish only as:

- a loose collection of `.toml` subagents;
- a single giant `AGENTS.md`;
- a docs-only repository with no installable package;
- a project-bound workflow hardcoded to one domain;
- a hook-only package that changes behavior without reviewable skills.

Those formats can be useful as references, but they are not enough for this
workflow's full lifecycle.
