# Skill: real-world-case-design

## Purpose

Use this skill to design realistic functional validation cases for PLAN phases, especially source retrieval, research workflow, provider behavior, evidence quality, and agent orchestration.

The case designer belongs to Group 3 validation responsibility. Implementation workers should not design the only cases that judge their own work.

## Use when

Use this skill when:

- A PLAN needs practical validation beyond unit tests.
- A phase claims product behavior works.
- Source retrieval, Tavily, Crawl4AI, provider calls, research workflow, evidence bundle, or UI/API surface behavior is involved.
- A live eval, holdout, negative control, or regression case is needed.
- A worker's implementation could overfit to easy tests.

## Skip when

Skip this skill when:

- The task is a small docs-only edit and file/content checks are sufficient.
- The active PLAN already has a complete frozen case set.
- Only code style, formatting, or import safety is being checked.

## Authority

Group 1 / director defines:

- What behavior must be proven.
- Which source/product boundaries must not be violated.
- Acceptance thresholds.
- Cost/latency/failure-transparency constraints.

Group 3 / functional validator designs and executes:

- Specific real-world cases.
- Negative controls.
- Holdouts.
- Regression cases.
- Evidence-quality checks.
- Live/offline comparison.

Group 2 / implementer may suggest cases but must not be the sole author or sole validator.

## Inputs

- active PLAN and phase acceptance criteria
- director validation brief
- historical failures and regression notes
- source/domain allowlists where relevant
- live eval constraints such as credentials, cost, latency, and provider availability

## Case taxonomy

Every substantial functional case set should consider:

- `primary_success_case`: representative query or workflow expected to succeed.
- `hard_success_case`: complex but in-scope case expected to succeed.
- `negative_control`: case that should not route through the current path.
- `holdout_case`: unsupported or deferred case that must fail transparently.
- `regression_case`: previously failed or high-risk case.
- `cost_latency_case`: checks budget, fanout, runtime, or provider usage.
- `evidence_quality_case`: verifies source relevance, citation quality, and evidence sufficiency.

## Case schema

```md
## Case <id>: <name>

Type: primary_success_case | hard_success_case | negative_control | holdout_case | regression_case | cost_latency_case | evidence_quality_case
User query / scenario:
Expected route:
Expected evidence:
Forbidden behavior:
Validation method:
Pass criteria:
Failure classification:
Artifacts:
```

## Process

1. Read the active PLAN phase and director validation brief.
2. Identify the behavior that must be proven in the real world.
3. Draft a balanced case set using the taxonomy.
4. Mark which cases require live providers and which can run offline.
5. Define pass/fail thresholds before execution.
6. Execute or assign execution to the functional validator.
7. Record results and artifacts.
8. Feed failures into `director-remediation-gate.md`.

## Realism checks

A case set is not realistic if:

- It only contains happy paths.
- It only checks that "something was returned".
- It uses implementation-specific fixtures instead of user-like scenarios.
- It accepts off-domain or low-quality evidence without flagging it.
- It has no negative controls or holdouts.
- It ignores cost, latency, or failure transparency when external APIs are involved.

## Example: source-assisted research

User query:

```text
安徽的低空经济未来前景如何
```

Expected checks:

- Query decomposition covers central policy, Anhui rollout, project/transaction signals, enterprise disclosure, and industry supplement.
- Direct-keep disclosure and structured-data paths do not degrade into generic Tavily search.
- Evidence comes from official or approved supplemental domains.
- Failures include structured reasons and candidate metadata.
- Tavily credit and latency stay within threshold.

## Validation

- Case set is reviewed before implementation completion.
- Group 3, not Group 2, owns final case design.
- Results are stored in PLAN progress, run trace, or eval artifact.
- Failures route to director remediation instead of being hand-waved.

## Red flags

- Implementation worker designs only easy cases.
- Functional validator only reads worker summary.
- Case passes because it found any URL, not because evidence is relevant.
- Direct-keep controls are routed through generic search.
- Holdouts are treated as failures instead of transparent unsupported cases.

## Completion note

Record:

- case set path or summary
- live/offline split
- pass/fail counts
- failed cases and classifications
- remediation recommendation
