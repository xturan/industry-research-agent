# Skill: brainstorming

## Purpose

Use this skill for deep collaborative exploration before product, architecture, agent workflow, source strategy, or governance design is converted into a Design Brief, PLAN, or implementation.

This is the project-native equivalent of the Superpowers `brainstorming` concept. It should actively help the user think, challenge weak assumptions, surface tradeoffs, and converge on a defensible design. It is not an implementation step.

## Use when

Use this skill when:

- The user explicitly asks to brainstorm, discuss, explore, compare, think through, or co-design.
- The task involves product design, agent design, workflow design, source strategy, architecture, validation strategy, or governance.
- The solution space is open and multiple approaches are plausible.
- The decision could affect future engineering behavior, protected contracts, validation gates, or long-running PLAN structure.
- A shallow answer would hide important tradeoffs or failure modes.

## Skip when

Skip this skill when:

- The active PLAN already defines the next implementation action and the user says to continue.
- The request is a small low-risk edit.
- The user asks for a direct factual answer.
- The first step must be debugging a concrete failure.
- The user explicitly asks to avoid discussion and the task is low-risk.

## Authority

- `AGENTS.md`, `.agent/STATUS.md`, and the active PLAN remain higher authority.
- This skill may recommend a Design Brief or PLAN, but it does not approve implementation by itself.
- This skill must not authorize protected-contract changes.
- Superpowers is advisory only; borrow its design discipline without creating competing plan/status/memory paths.
- Do not record private chain-of-thought. Record visible questions, tradeoffs, assumptions, recommendations, and decisions.

## Inputs

Read only the context needed for the design discussion:

- `.agent/STATUS.md`
- active PLAN if one is relevant
- `.agent/SKILL_ROUTER.md`
- related `.agent/skills/*.md`
- relevant project files, docs, tests, or recent validation artifacts
- user-provided constraints, examples, and preferences

## Depth modes

Choose the lightest mode that still produces a strong design.

| Mode | Use when | Expected output |
|---|---|---|
| quick | narrow design question, low risk | recommendation with 1-2 tradeoffs |
| standard | most product/workflow design discussions | options, recommendation, validation, next step |
| deep | explicit brainstorming, agent architecture, protected boundaries, major workflow design | iterative questions, assumptions, options, pressure test, staged design, Design Brief/PLAN exit |

When the user explicitly says "brainstorm" or asks for collaboration on design, default to `deep` unless the request is clearly small.

## Process

### 1. Frame the design problem

Start by stating:

- The objective in one sentence.
- The decision being made.
- What is not being decided yet.
- Why the decision matters.

If the task is too broad, decompose it before asking details. Do not refine a giant undifferentiated project.

### 2. Explore existing context before questioning

Check local project context when available:

- Current PLAN and STATUS.
- Existing skills, agents, contracts, or workflows.
- Prior validation failures, dirty-worktree risks, or protected contracts.

Then state what the existing context implies. This prevents asking the user questions already answered by the repository.

### 3. Build an assumption ledger

Make implicit assumptions visible:

```md
## Assumptions

| Assumption | Confidence | Impact if wrong | How to verify |
|---|---:|---|---|
| <assumption> | high / medium / low | <impact> | <check> |
```

Challenge medium/low-confidence assumptions before design hardens.

### 4. Ask one high-leverage question at a time

Ask only one question per turn when user input is needed.

Prefer multiple-choice questions when they reduce ambiguity:

```md
Question: Which risk should dominate this design?

Options:
- A. Speed: accept lighter gates and more manual review.
- B. Reliability: stronger gates, more validation overhead.
- C. Auditability: more traces and case evidence, slower execution.
```

Use questions to uncover:

- User goal.
- Primary user or operator.
- Success criteria.
- Non-goals.
- Constraints.
- Failure modes.
- Cost/latency limits.
- Review/approval boundaries.
- Evidence required to trust the outcome.

Do not ask a long questionnaire unless the user asks for a workshop.

### 5. Separate goals, constraints, and preferences

Keep these separate:

- Goal: outcome the user wants.
- Constraint: rule that cannot be violated.
- Preference: tradeoff the user leans toward.
- Hypothesis: belief that needs validation.

This prevents preferences from becoming fake constraints.

### 6. Generate 2-3 real options

Each option must be meaningfully different.

For each option, include:

- Best-fit situation.
- What it optimizes.
- What it sacrifices.
- Failure mode.
- Validation needed.

Avoid cosmetic alternatives.

### 7. Recommend, then pressure-test

Lead with the recommended option and explain why it is strongest for the stated goal.

Then pressure-test it:

- What breaks first?
- What does it make harder later?
- What would a skeptical reviewer object to?
- What hidden cost does it introduce?
- What rollback exists?
- What metric or case would disprove it?

If the pressure test reveals a serious issue, revise the recommendation instead of defending it.

### 8. Present the design in approval-sized sections

For non-trivial designs, present sections separately and ask whether the section is directionally right before moving on.

Typical sections:

- Operating model.
- Roles and responsibilities.
- Authority boundaries.
- Data or artifact flow.
- Validation and eval loop.
- Failure handling.
- Rollback.
- Migration path.

Scale section length to complexity. Use a few sentences for simple areas; use deeper explanation only where risk or tradeoff is material.

### 9. Convert the agreed direction into an artifact

Once the user agrees with the direction:

- Use `design-brief-template.md` for design alignment.
- Use `plan-creator` for long-running implementation.
- Use `plan-self-review.md` before execution.

Do not jump from brainstorming directly into production implementation unless the user explicitly asks and the task is low-risk.

## Outputs

For deep brainstorming, produce:

- Objective.
- Assumptions.
- Key constraints.
- 2-3 options.
- Recommendation.
- Pressure test.
- Validation approach.
- Next artifact: Design Brief, PLAN, or explicit blocker question.

## Output shape

```md
## Objective

<one sentence>

## Context Read

- <files/docs/status read>

## Assumptions

| Assumption | Confidence | Impact if wrong | How to verify |
|---|---:|---|---|

## Options

| Option | Optimizes | Sacrifices | Failure mode | Validation |
|---|---|---|---|---|

## Recommendation

<recommended option and reason>

## Pressure Test

- <objection / failure mode>

## Design Sections

<sectioned design if the user agrees to continue>

## Next Step

<Design Brief / PLAN / direct implementation / one blocking question>
```

## Question policy

Ask a question when:

- The user's goal is materially ambiguous.
- A protected contract may change.
- A choice affects cost, timeline, data safety, compliance, or user-facing behavior.
- Two options imply meaningfully different product outcomes.
- Repository context cannot resolve the ambiguity.

Do not ask a question when:

- You can make a low-risk assumption and state it.
- The active PLAN already defines the next action.
- The question would only delay obvious context gathering.

## Validation

Brainstorming is successful when:

- The user can see their options more clearly than before.
- The recommendation is explicit and defensible.
- Weak assumptions are visible.
- Failure modes and validation are named.
- The next step is concrete.

For skill validation:

- Dry-run an open-ended design request and confirm the output includes assumptions, real options, pressure test, and next artifact.
- Confirm no implementation action is taken before a Design Brief or PLAN when risk is non-trivial.

## Red flags

- Jumping straight to implementation while the user is asking for design thinking.
- Asking many questions before reading available local context.
- Listing options without a recommendation.
- Offering cosmetic options that do not change tradeoffs.
- Treating brainstorming as approved implementation.
- Ignoring protected-contract or authority boundaries.
- Recording private chain-of-thought instead of visible tradeoffs.
- Giving agreeable but shallow advice when a skeptical design review is needed.

## Completion note

When brainstorming materially affects project direction, record:

- Chosen option.
- Rejected options and why.
- Open assumptions.
- Validation needed.
- Whether the next artifact is a Design Brief or PLAN.
