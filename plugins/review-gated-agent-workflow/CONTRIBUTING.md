# Contributing

This plugin is designed to stay universal. Keep project-specific behavior in
examples or downstream project mappings, not in default skills.

## Contribution Rules

- Keep `prd-workflow` explicit-only.
- Keep `group2-design` explicit-only and multi-round.
- Do not add domain-specific assumptions to default templates.
- Do not make hooks auto-enter PRD workflow.
- Prefer warn/no-op hook behavior when workflow stage is unknown.
- Add validation when adding skills, scripts, hooks, or templates.

## Adding A Skill

Each skill must include:

- front matter with `name` and `description`;
- use conditions;
- skip conditions;
- inputs;
- outputs;
- allowed writes;
- forbidden writes;
- stop conditions.

Heavy workflow entry points should include `agents/openai.yaml` with:

```yaml
policy:
  allow_implicit_invocation: false
```

## Adding A Hook

Hooks must be conservative and transparent.

Required behavior:

- print a concise decision;
- avoid network calls;
- avoid modifying files;
- default to warn/no-op when required context is missing;
- return nonzero only for clear blocking conditions.

## Validation

Run:

```powershell
python plugins\review-gated-agent-workflow\scripts\validate_plugin_package.py plugins\review-gated-agent-workflow
python -m py_compile plugins\review-gated-agent-workflow\hooks\scope_preflight.py plugins\review-gated-agent-workflow\hooks\diff_postflight.py plugins\review-gated-agent-workflow\hooks\stop_gate_check.py plugins\review-gated-agent-workflow\scripts\validate_plugin_package.py
```
