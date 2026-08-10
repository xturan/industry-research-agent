# Hook Trust

Hooks in this plugin are packaged as reviewable lifecycle scripts. They are not
intended to be silently enabled.

## Hook Behavior

The hooks are conservative:

- missing workflow stage -> warn/no-op;
- allowed target -> pass;
- forbidden target -> block;
- missing run-state -> warn/no-op.

## Review Before Trust

Before enabling hooks, review:

- `hooks/hooks.json`
- `hooks/scope_preflight.py`
- `hooks/diff_postflight.py`
- `hooks/stop_gate_check.py`
- `templates/hook_scope_rules.yaml`

## Smoke Checks

Allowed path:

```powershell
$env:REVIEW_GATED_STAGE='brainstorm'
$env:REVIEW_GATED_TARGETS='docs/prd/foo/brainstorm.md'
$env:REVIEW_GATED_SCOPE_RULES='plugins/review-gated-agent-workflow/templates/hook_scope_rules.yaml'
python plugins\review-gated-agent-workflow\hooks\scope_preflight.py
```

Forbidden path:

```powershell
$env:REVIEW_GATED_STAGE='brainstorm'
$env:REVIEW_GATED_TARGETS='packages/foo.py'
$env:REVIEW_GATED_SCOPE_RULES='plugins/review-gated-agent-workflow/templates/hook_scope_rules.yaml'
python plugins\review-gated-agent-workflow\hooks\scope_preflight.py
```

Expected:

- allowed path prints `decision=pass`;
- forbidden path prints `decision=block`.
