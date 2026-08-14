# Hook Scope Guard Design

Status: draft
Audience: plugin authors, maintainers, security reviewers
Scope: hook and scope-rule design for review-gated workflow

## Purpose

Hook scope guards make workflow boundaries mechanically visible.

They do not decide whether a task should enter PRD workflow. They only check
whether the current stage is allowed to read, write, or claim completion for the
files and artifacts it touched.

## Design Principles

1. Hooks must not auto-enter PRD workflow.
2. Hooks must not rewrite the user's intent.
3. Hooks should report short, actionable diagnostics.
4. Hooks should distinguish warnable risk from blocking violation.
5. Hooks should be conservative before trust is established.
6. Hooks should be packaged with the plugin but documented as trust-reviewed
   lifecycle scripts.

## Hook Files

Recommended plugin files:

```text
plugins/review-gated-agent-workflow/hooks/
  hooks.json
  scope_preflight.py
  diff_postflight.py
  stop_gate_check.py
```

Recommended template:

```text
plugins/review-gated-agent-workflow/templates/
  hook_scope_rules.yaml
```

## Hook Event Design

| Event | Script | Purpose |
|---|---|---|
| `PreToolUse` | `scope_preflight.py` | Check the intended tool/write target against the current workflow stage. |
| `PostToolUse` | `diff_postflight.py` | Inspect changed files and detect forbidden writes after tool execution. |
| `Stop` | `stop_gate_check.py` | Verify required review gates, phase status, and completion claims. |

Minimal `hooks.json` shape:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|apply_patch|Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python hooks/scope_preflight.py",
            "timeout": 30,
            "statusMessage": "Checking workflow scope"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash|apply_patch|Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python hooks/diff_postflight.py",
            "timeout": 30,
            "statusMessage": "Auditing workflow diff"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python hooks/stop_gate_check.py",
            "timeout": 30,
            "statusMessage": "Checking workflow completion gates"
          }
        ]
      }
    ]
  }
}
```

The final plugin implementation should resolve paths from the plugin or repo
root. The above shape is a design template, not a ready-to-run path guarantee.

## Scope Rule Template

Suggested `hook_scope_rules.yaml`:

```yaml
version: 1

default:
  decision: warn
  message: "No workflow stage matched; use normal Codex judgment."

stages:
  brainstorm:
    allowed_write:
      - "docs/prd/**"
      - "examples/**/brainstorm.md"
    forbidden_write:
      - "packages/**"
      - "apps/**"
      - "tests/**"
      - ".agent/PLANS/**"
      - ".agent/STATUS.md"
      - ".codex/agents/**"
    required_output:
      - "problem_frame"
      - "risks"
      - "open_questions"

  prd_html_review:
    allowed_write:
      - "docs/prd/**"
      - "examples/**/prd_review.*"
      - "examples/**/assets/**"
    forbidden_write:
      - "packages/**"
      - "apps/**"
      - "tests/**"
      - ".agent/PLANS/**"
      - ".agent/STATUS.md"
    required_output:
      - "reviewable_prd"
      - "risk_matrix"
      - "acceptance_table"

  plan_from_prd:
    allowed_write:
      - ".agent/PLANS/**"
      - ".agent/STATUS.md"
      - "examples/**/plan.md"
    forbidden_write:
      - "packages/**"
      - "apps/**"
      - "tests/**"
    required_output:
      - "plan_file"
      - "human_plan_review_gate"

  group2_design:
    allowed_write:
      - "docs/**/group2*.md"
      - "examples/**/group2_design.md"
      - "plugins/**/templates/group2_design.md"
    forbidden_write:
      - "packages/**"
      - "apps/**"
      - "tests/**"
      - ".agent/PLANS/**"
      - ".agent/STATUS.md"
    required_output:
      - "role_mapping"
      - "allowed_write_scope"
      - "validation_handoff"

  group2_implementation:
    allowed_write_from_plan: true
    forbidden_write:
      - ".agent/PLANS/**"
      - ".agent/STATUS.md"
      - ".codex/agents/**"
    required_output:
      - "changed_files"
      - "worker_validation"
      - "required_group3_validation"

  group3_validation:
    allowed_write:
      - "docs/**/validation*.md"
      - "data/tmp/**"
      - "examples/**/validation.md"
    forbidden_write:
      - "packages/**"
      - "apps/**"
      - ".agent/PLANS/**"
      - ".agent/STATUS.md"
    required_output:
      - "commands_run"
      - "results"
      - "functional_findings"

  summarizer:
    allowed_write:
      - ".agent/PLANS/**"
      - ".agent/STATUS.md"
      - "docs/**/summary*.md"
    forbidden_write:
      - "packages/**"
      - "apps/**"
      - "tests/**"
    required_output:
      - "outcome"
      - "risks"
      - "capability_update_decision"
```

## Decision Levels

| Decision | Meaning | Action |
|---|---|---|
| `pass` | Change is inside current stage scope. | Continue. |
| `warn` | Scope is unclear or no stage matched. | Continue only if user intent and PLAN support it. |
| `block` | Forbidden write or missing human gate. | Stop and report remediation. |

## Preflight Check

`scope_preflight.py` should check:

- current workflow stage;
- requested tool type;
- intended file target, when available;
- stage allowed writes;
- stage forbidden writes;
- whether a human review gate is pending.

Preflight should block:

- PRD workflow write attempting production code;
- Group2 implementation attempting PLAN/STATUS changes;
- Group3 validation attempting production code changes;
- PLAN creation before PRD approval;
- PLAN execution before PLAN approval.

## Postflight Diff Audit

`diff_postflight.py` should check:

- actual changed files;
- staged/unstaged diff scope;
- forbidden paths;
- unexpected protected contract files;
- whether changes match the active PLAN assignment.

Postflight should report:

```text
decision: pass | warn | block
stage: <stage>
changed_files:
  - <path>
violations:
  - <path>: <reason>
next_action: <short remediation>
```

## Stop Gate Check

`stop_gate_check.py` should check before completion claims:

- PRD review completed before PLAN creation;
- PLAN review completed before implementation;
- phase status only used after PLAN execution begins;
- Group2 did not self-certify without Group3;
- Group3 validation produced command/result or scenario evidence;
- summarizer ran only after done condition or explicit request.

Stop gate should not block ordinary read-only tasks that never entered the
review-gated workflow.

## Manual Governance Dry Run

Use these cases before enabling hooks:

| Scenario | Expected hook decision |
|---|---|
| `brainstorm` writes `docs/prd/foo/brainstorm.md` | pass |
| `brainstorm` edits `packages/service.py` | block |
| `prd_html_review` writes `docs/prd/foo/reviewable_prd.html` | pass |
| `plan_from_prd` edits `packages/service.py` | block |
| `group2_implementation` edits assigned source file | pass |
| `group2_implementation` edits `.agent/PLANS/foo.md` | block unless assigned as governance output |
| `group3_validation` writes validation report | pass |
| `group3_validation` fixes production bug silently | block |
| ordinary read-only explanation | warn or no-op, not PRD trigger |

## Implementation Notes

Initial open-source release may ship this as a documented design plus templates.
Executable hooks can be added once the plugin has a stable way to know the
current workflow stage.

Possible stage sources:

- environment variable set by the workflow script;
- PLAN metadata;
- temporary run-state file;
- explicit CLI argument to hook scripts;
- Codex hook payload, where available.

The first implementation should prefer transparent warnings over broad blocking
until the stage source is reliable.
