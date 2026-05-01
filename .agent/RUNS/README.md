# Agent Run Traces

Status: active
Date: 2026-04-27

## Purpose

Store durable, auditable execution evidence for long-running or high-risk agent work without storing private chain-of-thought.

## When to create a run trace

Create a trace when:

- A PLAN phase changes repository behavior.
- A task uses multiple agents or validators.
- A live eval, external API, credential, or provider behavior matters.
- A dirty-worktree scope risk exists.
- A high-risk contract is discussed or blocked.
- A failure requires systematic debugging.

Skip for small low-risk single-file edits unless the active PLAN requires it.

## Directory format

```text
.agent/RUNS/<yyyy-mm-dd-hhmm>-<slug>/
  run.md
  decisions.md
  validation.md
  risks.md
  artifacts/
```

## Allowed content

- Task objective.
- User-visible assumptions.
- Files read.
- Skills used.
- PLAN and STATUS versions consulted.
- Decisions and alternatives considered at a summary level.
- Commands executed.
- Validation output summaries.
- Artifacts created.
- Risks, blockers, and TODOs.
- User approvals or explicit pauses.

## Forbidden content

- Private chain-of-thought.
- Hidden deliberation transcripts.
- Secrets, API keys, tokens, cookies, or passwords.
- Unredacted provider credentials.
- Raw copyrighted content beyond allowed excerpt limits.
- Personal data not required for the task.

## Redaction rules

- Replace secrets with `<redacted>`.
- Record that a credential was present only as `runtime env credential present`.
- Do not persist user-provided API keys.
- Prefer command names and summarized outputs over full logs when logs contain sensitive data.

## Minimum run.md

```md
# Run: <slug>

Date: <yyyy-mm-dd>
PLAN: <path>
Phase: <phase>
Status: completed | completed_with_risk | blocked

## Objective

## Context Read

## Work Performed

## Validation

## Risks / TODOs

## Next Action
```

## Completion note

If a run trace affects active work, link it from the active PLAN progress section and `.agent/STATUS.md`.
