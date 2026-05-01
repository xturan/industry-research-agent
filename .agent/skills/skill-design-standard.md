# Skill: skill-design-standard

## Purpose

Use this skill when creating, reviewing, or updating project-native `.agent/skills/*.md` files or user-level Codex skills.

The goal is to keep skills discoverable, concise, triggerable, and testable. This adapts the Superpowers skill design principle: the description/trigger tells the agent when to load the skill; the body tells the agent what to do after it is loaded.

## Use when

Use this skill when:

- Creating a new `.agent/skills/*.md` file.
- Updating an existing project-native skill.
- Adding or changing skill routing in `.agent/SKILL_ROUTER.md`.
- Promoting a `.agent` skill into a user-level Codex skill.
- Reviewing whether a skill is too vague, too broad, or not triggerable.
- A user says a skill trigger is unclear.

## Skip when

Skip this skill when:

- Only executing an already selected skill.
- Editing a PLAN or STATUS without changing skill behavior.
- Making a small typo fix that does not affect trigger or process semantics.

## Core principle

```text
Trigger metadata decides when the skill is loaded.
The skill body decides what to do after loading.
Validation proves the behavior changed correctly.
```

## Skill kinds

### Project-native `.agent` skill

Project-native skills live in `.agent/skills/*.md` and are routed through `.agent/SKILL_ROUTER.md`.

Required structure:

```md
# Skill: <skill-name>

## Purpose

<One paragraph: what this skill controls and why it exists.>

## Use when

- <Concrete trigger condition>

## Skip when

- <Concrete non-trigger condition>

## Authority

- <How this skill relates to AGENTS, STATUS, PLAN, protected contracts, and Superpowers advisory material.>

## Inputs

- <Files, artifacts, commands, or context the agent should read when using this skill.>

## Process

1. <Step>

## Outputs

- <Expected artifact, decision, validation result, or PLAN/STATUS update>

## Validation

- <How to verify the skill was applied correctly>

## Red flags

- <Rationalization or shortcut that means stop>

## Completion note

<What to record when this skill materially affects work.>
```

### User-level Codex skill

User-level Codex skills live under the Codex skill directory and should follow the official skill format:

```yaml
---
name: <lowercase-hyphen-name>
description: <what the skill does and exactly when to use it>
---
```

Rules:

- `description` must contain all important trigger conditions.
- Do not rely on body "Use when" sections for discoverability.
- Body should stay concise and procedural.
- Use references only when they are loaded conditionally.
- Do not add auxiliary docs unless they directly support the skill.

## Trigger description standard

A good trigger description must include:

- Action domain: what class of work the skill handles.
- Trigger context: when the skill should be used.
- Boundary: when it should not be used or what higher authority limits it.
- Specific terms users or agents are likely to say.

Good:

```yaml
description: Use when creating or updating project-native skills, SKILL_ROUTER entries, or Codex skill frontmatter; enforce trigger clarity, required sections, validation, and Superpowers-compatible skill design.
```

Bad:

```yaml
description: This skill asks questions, writes a plan, validates work, and updates status.
```

Why bad:

- It describes internal steps instead of trigger conditions.
- It is too broad.
- It does not say what task should activate the skill.
- It overlaps many other skills.

## Process for new skills

1. Identify the exact user/task signals that should trigger the skill.
2. Confirm the skill is narrower than existing skills.
3. Define skip conditions to prevent over-triggering.
4. Define authority boundaries.
5. Write the minimum process needed after loading.
6. Add red flags that catch likely agent shortcuts.
7. Add validation or pressure scenarios.
8. Update `.agent/SKILL_ROUTER.md`.
9. Update the active PLAN/STATUS if this changes the operating model.

## Validation

For a new or changed skill:

- `Select-String` confirms the skill has `Purpose`, `Use when`, `Skip when`, `Process`, `Validation`, `Red flags`, and `Completion note`.
- Router entry exists if the skill is project-native.
- At least one dry-run scenario or validation rule exists.
- The skill does not require private chain-of-thought.
- The skill does not override `AGENTS.md`, STATUS, active PLAN, protected contracts, or Superpowers advisory boundaries.

## Red flags

- Description says what the skill does internally but not when to use it.
- Skill covers too many unrelated task classes.
- No skip conditions.
- No validation or pressure scenario.
- Skill can override the active PLAN.
- Skill requires hidden reasoning or private chain-of-thought.
- Skill lets a worker self-certify completion.

## Completion note

When a skill is added or materially changed, record:

- Why the trigger was needed.
- Which router entry changed.
- What validation or pressure scenario covers it.
- Whether the change should later be promoted into `AGENTS.md`.
