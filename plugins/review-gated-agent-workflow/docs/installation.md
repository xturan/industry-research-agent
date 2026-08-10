# Installation

This plugin can be used in two ways:

1. as a Codex plugin through a marketplace entry;
2. by copying individual skills, hooks, scripts, or templates.

## Repo Marketplace Example

The repository-level marketplace example lives at:

```text
.agents/plugins/marketplace.json
```

It points to:

```text
./plugins/review-gated-agent-workflow
```

This file is an example source for a repo or team marketplace. It does not
install or trust hooks by itself.

## Manual Copy Fallback

Copy skills from:

```text
plugins/review-gated-agent-workflow/skills/
```

Copy templates from:

```text
plugins/review-gated-agent-workflow/templates/
```

Copy hooks only after reviewing:

```text
plugins/review-gated-agent-workflow/hooks/
```

## Explicit Invocation

Use:

```text
$prd-workflow
$group2-design
```

Do not expect these skills to trigger implicitly for normal implementation,
testing, review, or explanation tasks.
