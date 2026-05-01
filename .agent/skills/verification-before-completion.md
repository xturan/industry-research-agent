# Skill: verification-before-completion

## Purpose

Use this skill before claiming that work is complete, fixed, validated, or ready.

Evidence comes before completion claims.

## Use when

Use this skill when about to say:

- done
- fixed
- complete
- tests passed
- ready
- validated
- no issue found

## Required process

1. Identify what evidence proves the claim.
2. Run or retrieve fresh evidence.
3. Read the output, not just the command exit.
4. Compare the output to the expected pass condition.
5. Record failures, skipped checks, and residual risks.
6. Only then state completion status.

## Evidence types

- Test output.
- Lint or compile output.
- API response.
- Eval result.
- Manual dry-run result with scenario and observed behavior.
- File existence and content checks for docs/governance tasks.
- Diff/scope review.

## Completion wording

Use precise status:

- `completed`: all required checks passed.
- `completed_with_risk`: required behavior passes but residual risk remains.
- `blocked`: a required dependency, credential, permission, or unclear failure remains.
- `partial`: only part of the requested scope is complete.

## Red flags

- "Looks good."
- "Should work."
- "I did not run tests, but..."
- "The worker said it passed."
- "This is docs-only, so no validation needed."
- "The previous run should still be valid."

## Required final note

Every completion summary should include:

- What changed.
- Validation run.
- Skipped checks and why.
- Assumptions.
- Remaining risks or TODOs.
- Next recommended action.
