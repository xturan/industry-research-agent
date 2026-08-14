# Review-Gated Workflow Skill Contracts

Status: draft
Audience: plugin authors, workflow maintainers
Scope: reusable skill contract design

## Contract Rules

All skills in this workflow must follow these rules:

- Keep project-independent defaults.
- Use explicit trigger language for heavyweight workflows.
- Document skip conditions.
- Declare inputs and outputs.
- Declare allowed writes and forbidden writes.
- Stop at human review gates.
- Keep implementation and validation separate.
- Prefer concise outputs that can be consumed by the next skill.

`prd-workflow` and `group2-design` must be explicit-only. They should include:

```yaml
policy:
  allow_implicit_invocation: false
```

## Skill: prd-workflow

Suggested path:

```text
plugins/review-gated-agent-workflow/skills/prd-workflow/SKILL.md
```

Front matter:

```md
---
name: prd-workflow
description: Explicitly start the review-gated PRD workflow for a feature, generating brainstorm output, reviewable PRD/RPD, human review gates, and PLAN creation only after approval. Do not trigger for ordinary coding, testing, review, or explanation tasks.
---
```

Use when:

- The user explicitly says `$prd-workflow`.
- The user explicitly asks to start PRD design or PRD review workflow.
- The user asks to generate a PRD/RPD before implementation.

Skip when:

- The user asks to fix a bug.
- The user asks to continue an existing PLAN.
- The user asks for code explanation, tests, review, or a small edit.
- The active task already has an approved PLAN and no PRD change is requested.

Inputs:

- feature name;
- project or product context;
- target users;
- goals;
- non-goals;
- known constraints;
- existing PRD template, if any.

Outputs:

- brainstorm brief;
- reviewable PRD/RPD artifact path;
- PRD review questions;
- approval state;
- PLAN path after approval.

Allowed writes:

- PRD/RPD draft folder;
- PLAN file only after PRD approval;
- status/handoff only when creating or updating the active PLAN.

Forbidden writes:

- production code;
- test code;
- runtime config;
- project-bound Group2 design unless explicit `group2-design` is invoked.

Stop conditions:

- PRD/RPD is ready for human review.
- PLAN is ready for human review.
- User rejects or redirects scope.
- Required feature facts cannot be inferred safely.

## Skill: brainstorm

Suggested path:

```text
plugins/review-gated-agent-workflow/skills/brainstorm/SKILL.md
```

Front matter:

```md
---
name: brainstorm
description: Build a project-independent requirement frame with problem statement, goals, non-goals, alternatives, risks, assumptions, and open questions for PRD workflow.
---
```

Use when:

- Called by `prd-workflow`.
- The user explicitly asks for early requirement thinking before PRD.

Skip when:

- The task is already implementation-ready.
- The user only wants a code change or test run.
- Brainstorming would overwrite an approved PRD or PLAN without review.

Inputs:

- raw user request;
- available project/product context;
- prior PRD or design notes;
- constraints and non-goals.

Outputs:

- problem frame;
- user and scenario assumptions;
- solution candidates;
- risks and danger points;
- PRD open questions;
- suggested acceptance themes.

Allowed writes:

- brainstorm draft notes;
- PRD/RPD input artifacts.

Forbidden writes:

- production code;
- PLAN;
- STATUS;
- hooks;
- subagent configuration.

Stop conditions:

- Critical product facts are missing.
- Multiple incompatible product directions remain.
- User requests to pause for review.

## Skill: prd-html-review

Suggested path:

```text
plugins/review-gated-agent-workflow/skills/prd-html-review/SKILL.md
```

Front matter:

```md
---
name: prd-html-review
description: Generate a reviewable PRD/RPD artifact, usually HTML plus Markdown source, with diagrams, risk matrix, acceptance criteria, and human review questions.
---
```

Use when:

- Called by `prd-workflow` after brainstorm.
- The user explicitly asks for an HTML PRD/RPD review artifact.

Skip when:

- PRD has not been framed.
- User asks for PLAN creation directly from an already approved document.
- The task is ordinary implementation.

Inputs:

- brainstorm brief;
- PRD template;
- project/product context;
- target review audience;
- known risks and open questions.

Outputs:

- `reviewable_prd.html`;
- optional `reviewable_prd.md`;
- diagrams or embedded Mermaid;
- review checklist;
- risk and decision summary.

Allowed writes:

- PRD/RPD files;
- PRD assets.

Forbidden writes:

- PLAN files;
- STATUS;
- production code;
- project worker configuration.

Stop conditions:

- PRD/RPD is generated and ready for human review.
- Template requirements conflict with user-provided scope.
- Required review fields are missing.

## Skill: plan-from-prd

Suggested path:

```text
plugins/review-gated-agent-workflow/skills/plan-from-prd/SKILL.md
```

Front matter:

```md
---
name: plan-from-prd
description: Convert an approved PRD/RPD into a durable PLAN with phases, validation, gates, scope boundaries, and explicit stop conditions.
---
```

Use when:

- Human has approved the PRD/RPD.
- The user explicitly asks to create a PLAN from an approved PRD.
- `prd-workflow` reaches the PLAN creation gate.

Skip when:

- PRD/RPD has not been approved.
- User asks for a draft PRD, not a PLAN.
- The task is a small one-off edit where repository rules do not require PLAN.

Inputs:

- approved PRD/RPD;
- approval notes;
- scope and non-goals;
- acceptance criteria;
- risks;
- project planning rules.

Outputs:

- PLAN file;
- STATUS handoff update, when applicable;
- validation loop;
- phase status scheme;
- stop conditions.

Allowed writes:

- PLAN file;
- STATUS or equivalent handoff file;
- optional planning artifacts.

Forbidden writes:

- production code;
- tests;
- hooks;
- project worker config.

Stop conditions:

- PLAN is ready for human review.
- PRD approval is missing or ambiguous.
- PLAN requires a protected contract change not approved in PRD.

## Skill: group2-design

Suggested path:

```text
plugins/review-gated-agent-workflow/skills/group2-design/SKILL.md
```

Front matter:

```md
---
name: group2-design
description: Explicitly design project-bound Group2 implementation workers through multi-round human dialogue. Do not trigger implicitly or complete in one automatic pass.
---
```

Use when:

- The user explicitly invokes `$group2-design`.
- The user explicitly asks to design or update Group2 workers for a project.
- PRD workflow reaches a human-approved need for project-bound Group2 design.

Skip when:

- The user has not explicitly requested group design.
- Existing Group2 design is sufficient for the active PLAN.
- The request is ordinary implementation, test, review, or explanation.

Required rounds:

1. Project discovery.
2. Role proposal.
3. Scope and permission boundaries.
4. Group3 validation handoff.
5. Human final review.

Inputs:

- project type;
- architecture and stack;
- existing roles;
- risk boundaries;
- active PRD or PLAN;
- human corrections per round.

Outputs:

- project-bound Group2 role design;
- mapping from universal roles to project roles;
- allowed and forbidden write scopes;
- validation handoff contract;
- accepted open questions or TODOs.

Allowed writes:

- group design docs;
- templates;
- example role cards.

Forbidden writes:

- production code;
- active PLAN unless the workflow explicitly assigns governance output;
- STATUS unless the project uses it for approved design handoff;
- Group3 validation results.

Stop conditions:

- each required human review point;
- project facts are disputed;
- human rejects the proposed role split;
- scope boundaries cannot be made safe.

## Skill: workflow-scope-guard

Suggested path:

```text
plugins/review-gated-agent-workflow/skills/workflow-scope-guard/SKILL.md
```

Front matter:

```md
---
name: workflow-scope-guard
description: Define and audit stage-specific read/write boundaries for review-gated workflow skills, hooks, Group2 implementation, Group3 validation, and summarization.
---
```

Use when:

- Writing hook scope rules.
- Auditing a worker's allowed writes.
- Reviewing a diff for scope violations.
- A phase claims completion.

Skip when:

- The task is read-only and has no file changes.
- The repository already has stricter active hook rules for the exact stage.

Inputs:

- current workflow stage;
- active PLAN phase;
- assigned worker role;
- changed files;
- allowed and forbidden paths;
- protected contracts.

Outputs:

- scope decision: pass, warn, or block;
- violated paths or contracts;
- suggested remediation;
- concise audit summary.

Allowed writes:

- validation reports;
- hook scope templates;
- PLAN/STATUS notes only when assigned by governance phase.

Forbidden writes:

- production code fixes during validation;
- rewriting the user's intent;
- auto-entering PRD workflow.

Stop conditions:

- forbidden write detected;
- protected contract touched without explicit authorization;
- worker role and assigned scope do not match;
- validation cannot determine whether a change is in scope.

## Contract-Level Validation

A release candidate passes skill-contract validation when:

- `prd-workflow` is explicit-only.
- `group2-design` is explicit-only.
- Ordinary coding, review, test, and explanation prompts do not trigger PRD
  workflow.
- Each skill declares use, skip, inputs, outputs, allowed writes, forbidden
  writes, and stop conditions.
- Heavy skills stop at human review gates.
- Group2 and Group3 responsibilities remain separate.
- Skill names remain project-independent.
