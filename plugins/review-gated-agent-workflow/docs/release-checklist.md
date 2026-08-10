# Release Checklist

## Package

- [ ] `.codex-plugin/plugin.json` exists.
- [ ] Plugin manifest parses as JSON.
- [ ] Plugin name is `review-gated-agent-workflow`.
- [ ] Six skill files exist.
- [ ] `prd-workflow` is explicit-only.
- [ ] `group2-design` is explicit-only.
- [ ] Hooks are present but not silently trusted.
- [ ] Templates are project-independent.

## Documentation

- [ ] README explains what the plugin does.
- [ ] Installation doc explains marketplace and copy fallback.
- [ ] Hook trust doc explains review expectations.
- [ ] CONTRIBUTING explains skill and hook requirements.
- [ ] CHANGELOG has the release entry.
- [ ] LICENSE exists.

## Validation

- [ ] Package validation passes.
- [ ] Python hook scripts compile.
- [ ] Allowed hook smoke case passes.
- [ ] Forbidden hook smoke case blocks.
- [ ] Marketplace JSON parses.

## Release Notes

Mention:

- PRD workflow is explicit-only.
- `group2-design` is explicit-only and human-reviewed.
- Hooks are conservative and require trust review.
- The package is universal by default; project binding happens in examples or
  downstream project mappings.
