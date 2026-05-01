---
description: "Systematic debugging: reproduce, isolate root cause, classify failure, apply minimal fix, and verify. No speculative patching."
argument-hint: "[failing command or scenario]"
---

# Systematic Debugging

Root-cause-first debugging. No speculative patching. See `.agent/skills/systematic-debugging.md` for full rules.

## Process

1. **Capture** the exact failure (command, output, traceback, exit code)
2. **Reproduce** or isolate the smallest failing path
3. **Classify** the failure:
   - `environment_mismatch` — OS, Python version, shell, encoding
   - `missing_dependency` — package not installed or wrong version
   - `credential_or_permission` — API key, token, file permission
   - `contract_regression` — schema, response shape, type drift
   - `routing_regression` — source or API routing changed behavior
   - `provider_behavior_change` — external API/Tavily/Crawl4AI changed
   - `external_api_volatility` — transient network/service issue
   - `encoding_or_shell_mismatch` — CRLF/LF, encoding
   - `dirty_worktree_scope_risk` — unrelated changes interfering
   - `test_fixture_drift` — test data stale or wrong
4. **Identify** likely root cause with evidence
5. **Fix** with the smallest coherent change
6. **Re-run** the failing path
7. **Run regression checks** relevant to the touched module
8. **Record** result in active PLAN or STATUS if it affects long-running work

## Red Flags

- "Try this quick fix" before reproduction
- Changing multiple unrelated files
- Ignoring stderr or traceback details
- Treating live provider failure as local test failure
- Re-running same command without changing hypothesis
- Patching around a protected contract

## Completion Note

Record: Failing command/scenario, Root cause, Fix, Verification command, Remaining risk.
