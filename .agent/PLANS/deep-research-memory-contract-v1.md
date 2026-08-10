# Deep Research Memory Contract v1

Status: active_phase1_contract_freeze

Created: 2026-06-15

Parent PLAN:

- `.agent/PLANS/deep-research-report-productization-v1.md`

## Purpose

Freeze the planner-side memory contract before retrieval, evidence, and final
report rewiring expands the state surface.

This document defines what `summary_memory` means, what it must not mean, and
how future persistence/update work should feed the planner safely.

## Why This Exists

`summary_memory` sits in the planning stage.

Its purpose is not to inject new facts into the report. Its purpose is to help
the planner avoid restarting from zero every run when repeated patterns have
already emerged, such as:

- recurring evidence gaps
- repeated user/report emphasis
- repeated locality sensitivity
- repeated source-family insufficiency

Without this layer, every `plan_task` call behaves as if no prior run has ever
revealed stable blind spots or repeated planning needs.

## Two-Layer Memory Model

### Layer 1: `raw_run_memory`

What it is:

- the original run record layer
- stores concrete run artifacts and audit objects

Expected contents:

- `response.json`
- dossier markdown
- planner metadata
- node step summaries
- search events
- tool traces
- final report metadata

Primary role:

- audit and reconstruction

Planner rule:

- `plan_task` should not directly consume the whole raw layer as prompt context
- raw layer is too noisy and too large to act as planning memory

### Layer 2: `summary_memory`

What it is:

- a compact API-summary layer derived from repeated raw run signals

Primary role:

- planner input for repeated themes, repeated evidence gaps, and repeated
  planning preferences

Allowed planner meaning:

- recurring themes
- repeated evidence gaps
- repeated source-family misses
- repeated locality or disclosure needs
- repeated preferred report emphases

Forbidden planner meaning:

- direct factual evidence
- report conclusion override
- synthetic source creation
- hidden user instruction override

## Current Frozen Input Contract

Current code-level planner input:

- `ResearchGraphState.summary_memory: dict[str, Any]`
- `plan_task_provider_backed(..., summary_memory=...)`
- planner prompt section: `Summary memory:`

Current metadata exposure:

- `planner_metadata.summary_memory_used`
- `planner_metadata.summary_memory_keys`

Current allowed payload shape:

```json
{
  "recurring_themes": ["政策先行", "执行验证"],
  "repeated_gaps": ["缺少项目公示"],
  "preferred_dimensions": ["policy", "execution"],
  "source_family_watchlist": ["company_disclosure"]
}
```

The exact key set may expand later, but Phase 1 freezes these rules:

- keys must be descriptive and audit-friendly
- values should prefer short arrays / short strings / simple dicts
- planner must treat them as planning hints, not evidence

## Update Threshold Policy

`summary_memory` should not update on one-off noise.

Future persistence work must follow this minimum threshold:

- one isolated run signal: do not promote
- repeated signal across multiple runs: eligible for promotion
- repeated signal should normally appear at least 2-3 times before promotion

Examples:

- one run misses a local project notice:
  do not update `summary_memory`
- three runs in the same theme repeatedly miss procurement-grade evidence:
  promote a repeated gap summary

## Planner Consumption Rules

`plan_task` may use `summary_memory` to:

- add missing dimensions earlier
- strengthen source obligations
- prioritize a repeated gap in search rounds
- surface repeated locality/disclosure sensitivity

`plan_task` may not use `summary_memory` to:

- state that a fact is true
- mark a claim as supported
- skip evidence collection because memory already suggests a conclusion

## Implementation Direction For Later Phases

Phase 6 should implement:

1. raw run persistence indexing
2. summarizer job from raw run layer to summary layer
3. repeated-signal threshold logic
4. planner-safe summary projection
5. audit view for why a summary-memory entry exists

## Phase 6 Task Breakdown

Translate Phase 6 into concrete implementation lanes:

1. persistence lane
   - add raw run memory storage objects for dossier path, response sidecar, planner metadata, and key run summaries
   - define the write boundary so graph runs can emit raw memory without blocking the main report workflow
2. aggregation lane
   - implement a summarizer that groups repeated gaps, repeated themes, and repeated preferred dimensions across runs
   - ensure aggregation works at least by query theme or normalized topic family
3. threshold lane
   - require repeated signals before promotion into `summary_memory`
   - reject one-off noisy events and transient provider failures
4. planner projection lane
   - project only planner-safe keys into `summary_memory`
   - expose `summary_memory_used` and applied keys in dossier / step summaries
5. audit lane
   - provide a traceable explanation for why each promoted memory key exists
   - preserve links back to the raw run ids that triggered promotion

## Validation Expectations

When Phase 6 begins, validation should prove:

- one-off noise does not update `summary_memory`
- repeated gaps do update `summary_memory`
- planner receives only compact summary input
- dossier / audit surfaces can explain which memory keys were applied

## Current Scope Boundary

This document does not yet implement:

- database schema for memory tables
- summary-memory aggregation jobs
- memory decay / pruning
- account-level personalization

It only freezes the planner-side contract so downstream work can build on a
stable input boundary.
