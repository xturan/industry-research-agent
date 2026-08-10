# Changelog

## 0.1.0 - 2026-07-01

Initial release candidate.

Added:

- Plugin manifest.
- Six reusable skills:
  - `prd-workflow`
  - `brainstorm`
  - `prd-html-review`
  - `plan-from-prd`
  - `group2-design`
  - `workflow-scope-guard`
- Explicit-only metadata for `prd-workflow` and `group2-design`.
- Conservative hook scripts and `hooks.json`.
- PRD/RPD, PLAN, Group2 design, and scope-rule templates.
- Package validation script.
- Release documentation and marketplace example.

Notes:

- Hooks are packaged but not automatically trusted or installed.
- `group2-design` is intentionally multi-round and human-reviewed.
- PRD workflow is explicit-only and should not trigger for normal coding tasks.
