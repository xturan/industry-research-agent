# Skill: intent-discovery-gate

## Purpose

Use a lightweight Socratic intake gate before ambiguous, high-risk, architectural, product-design, or long-running tasks.

The goal is to prevent premature implementation while avoiding heavy process for routine work.

## Use when

Use this skill when any condition applies:

- The user's goal is ambiguous or underspecified.
- The task may change architecture, data flow, workflow state, protected contracts, or user-facing behavior.
- The task could become or update a long-running PLAN.
- Multiple viable strategies exist with meaningful tradeoffs.
- The user asks for agent design, application design, source strategy, workflow design, or process design.
- The task could be expensive, irreversible, compliance-sensitive, or hard to roll back.

## Skip when

Do not use this gate when:

- The active PLAN defines the next action and the user says to continue.
- The request is a small low-risk code or docs edit with clear scope.
- The user asks a narrow factual question.
- The task is a straightforward reproduction of a known error and the first step is to inspect logs.

## Intake output

Produce only the minimum needed to unblock execution:

- Objective: one sentence.
- Success criteria: observable result.
- Non-goals: what should not be changed.
- Constraints: relevant rules, contracts, credentials, environment, or time limits.
- Candidate approaches: 2-3 options only when tradeoffs matter.
- Recommended approach: concise rationale.
- Questions: ask only if a safe assumption would be risky.

## Question policy

Prefer execution with stated assumptions when risk is low.

Ask a question when:

- A protected contract might change.
- Data loss, credential exposure, or irreversible behavior is possible.
- The user intent cannot be inferred from repository state.
- Two approaches have materially different costs or product outcomes.

Ask at most one short question at a time unless the user explicitly requests a broader workshop.

## Red flags

Stop and use this gate if you catch yourself thinking:

- "The user probably means..." and the assumption affects architecture or contracts.
- "This is just a process change" while it affects agent behavior.
- "We can update AGENTS later" while changing effective governance now.
- "No need to define success criteria" for a long-running task.
- "The phase name is enough" without acceptance criteria.

## Dry-run examples

### Small bug fix

Request: "Fix the typo in this docs heading."

Decision: skip the gate. Make the small edit and verify the file.

### Ambiguous product design

Request: "Redesign how our research agents work."

Decision: use the gate. Clarify objective, constraints, non-goals, and candidate operating models before writing a PLAN.

### High-risk workflow change

Request: "Change EvidenceBundle so citations are optional."

Decision: use the gate and stop before implementation. This touches a protected contract and needs explicit PLAN authorization, migration impact, and validation.

## Completion note

If this gate creates or changes a PLAN, update `.agent/STATUS.md` and the active PLAN with the decision, assumptions, validation path, and next action.
