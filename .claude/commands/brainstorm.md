---
description: "Deep collaborative exploration for product design, architecture, agent workflow, source strategy, or governance. Converge on defensible design before implementation."
argument-hint: "[design question or topic]"
---

# Brainstorming

Deep collaborative exploration before converting ideas into a Design Brief, PLAN, or implementation. See `.agent/skills/brainstorming.md` for full rules.

This is NOT an implementation step. Actively challenge weak assumptions, surface tradeoffs, and converge on a defensible design.

## Process

1. **Frame the problem**: Objective in one sentence, the decision being made, what is NOT being decided, why it matters
2. **Explore existing context**: Current PLAN, STATUS, existing skills, contracts, prior validation failures
3. **Build assumption ledger**: Make implicit assumptions visible with confidence/impact/verification
4. **Ask one high-leverage question at a time** when user input is needed
5. **Separate goals, constraints, and preferences** — prevent preferences from becoming fake constraints
6. **Generate 2-3 real options** — meaningfully different, each with: best-fit, optimizes, sacrifices, failure mode, validation needed
7. **Recommend, then pressure-test** — what breaks first? what's harder later? skeptical reviewer objection? hidden cost? rollback?
8. **Present in approval-sized sections** — operating model, roles, authority, data flow, validation, failure handling, rollback, migration
9. **Convert agreed direction into artifact** — Design Brief → PLAN, not directly to implementation

## Output Shape

```md
## Objective
<one sentence>

## Context Read
- <files/docs/status read>

## Assumptions
| Assumption | Confidence | Impact if wrong | How to verify |

## Options
| Option | Optimizes | Sacrifices | Failure mode | Validation |

## Recommendation
<recommended option and reason>

## Pressure Test
- <objection / failure mode>

## Next Step
<Design Brief / PLAN / direct implementation / blocking question>
```

## Red Flags

- Jumping straight to implementation
- Asking many questions before reading local context
- Listing options without a recommendation
- Cosmetic options that don't change tradeoffs
- Treating brainstorming as approved implementation
- Ignoring protected-contract or authority boundaries
