# Skill: systematic-debugging

## Purpose

Use this skill when a command, test, external API, integration, or workflow behaves unexpectedly.

The goal is root-cause-first debugging, not speculative patching.

## Use when

Use this skill when:

- A command or test fails.
- A live eval differs from offline tests.
- An API returns an unexpected error or shape.
- A tool behaves differently than expected.
- A bug is reported without a clear root cause.
- A fix attempt failed.

## Process

1. Capture the exact failure.
2. Reproduce or isolate the smallest failing path.
3. Classify the failure.
4. Identify likely root cause with evidence.
5. Make the smallest coherent fix.
6. Re-run the failing path.
7. Run regression checks relevant to the touched module.
8. Record the result in the active PLAN or STATUS if it affects long-running work.

## Failure classes

- environment_mismatch
- missing_dependency
- credential_or_permission
- contract_regression
- routing_regression
- provider_behavior_change
- external_api_volatility
- encoding_or_shell_mismatch
- dirty_worktree_scope_risk
- test_fixture_drift

## Red flags

- "Try this quick fix" before reproduction.
- Changing multiple unrelated files to see what happens.
- Ignoring stderr or traceback details.
- Treating a live provider failure as a local test failure without evidence.
- Re-running the same command repeatedly without changing the hypothesis.
- Patching around a protected contract.

## Completion note

Record:

- Failing command or scenario.
- Root cause.
- Fix.
- Verification command.
- Remaining risk.
