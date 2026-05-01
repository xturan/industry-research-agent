# Skill: tdd-policy

## Purpose

Define when this repository should use test-first development, characterization tests, live evals, or manual governance dry-runs.

## Use when

Use this skill when:

- Adding new behavior.
- Fixing a bug.
- Changing routing, provider, workflow, task, or source behavior.
- Creating governance skills that change agent behavior.
- Deciding whether test-first is practical.

## Policy

Use test-first when:

- The behavior is deterministic.
- The expected output can be asserted locally.
- The change affects production code.
- The bug can be reproduced in a test.

Use characterization tests when:

- Legacy behavior must be preserved before refactoring.
- The current behavior is unclear but observable.
- A broad refactor needs a safety net.

Use live evals when:

- External search, crawling, provider, or API behavior is part of the product claim.
- Offline tests pass but real-world behavior matters.
- Cost, latency, or failure transparency is part of acceptance.

Use manual governance dry-runs when:

- The artifact is a PLAN, skill, router, or status rule.
- The behavior being tested is agent decision-making rather than executable code.

## Exceptions

Test-first may be skipped for:

- Throwaway exploration.
- Documentation-only edits.
- PLAN/status updates.
- Generated artifacts that are verified by file/content checks.
- Emergency diagnostic reads.

When skipped, record why and what validation replaced it.

## Red flags

- "Too simple to test" for production behavior.
- "I'll add tests later" after changing contracts.
- "Manual checked" without scenario details.
- Using offline tests to claim live provider reliability.
- Using live success to bypass deterministic regression tests.

## Completion note

Tie validation to the active PLAN and relevant module-specific check skill.
