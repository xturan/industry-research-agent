# Deep Research Agent Contract Matrix v1

Status: active_phase0_contract_matrix

Created: 2026-06-15

Parent PLAN:

- `.agent/PLANS/deep-research-report-productization-v1.md`

## Purpose

This document freezes the Phase 0 prompt/context contract matrix for the
Deep Research report productization plan.

It serves three jobs:

1. audit the current node behavior
2. define the target role for each node
3. give implementation-ready prompt/context contracts for the next phases

## Current Graph Baseline

Current node chain in `graph_v1`:

1. `plan_task`
2. `collect_sources`
3. `parse_sources`
4. `score_sources`
5. `build_evidence`
6. `build_claims`
7. `editor1_draft`
8. `editor2_review`
9. `verify_claims`
10. `chief_gate`
11. `human_review`
12. `finalize_report`

Current reality:

- live LLM prompt exists mainly for `plan_task` and `editor1_draft`
- several later nodes are still deterministic rule processors
- final report is still largely a deterministic composition layer

## Field Guide

- `Current behavior`:
  当前代码真实在做什么，而不是理论上想做什么。
- `Target role`:
  该节点产品化后应扮演的业务身份。
- `Prompt contract`:
  该节点的 prompt 里必须明确的角色、目标、禁止项和输出边界。
- `Context contract`:
  该节点允许拿到哪些上下文，以及这些上下文为什么属于它。
- `Output contract`:
  该节点最终必须产出什么结构或业务结果。

## Node Matrix

### 1. `plan_task`

Current behavior:

- current provider-backed planner already has a live LLM prompt
- but output still allows vague planning and does not fully freeze explicit dimension contracts

Current inputs:

- `query`
- `fallback_payload`
- `planner_replan_request`
- future state should also add summary memory

Current outputs:

- `plan`
- `query_requirements`
- `planner_metadata`

Current gap:

- dimensions are not yet treated as strict business objects
- planning can still drift into generic “search some sources” logic

Target role:

- `Dimension Planner`

Prompt contract:

- role:
  senior research planner for deep research report production
- must do:
  - decompose the query into explicit research dimensions
  - define why each dimension matters
  - define source obligations by dimension
  - define search rounds by dimension
  - integrate summary memory when present
- must not do:
  - answer the final research question directly
  - use vague quantifiers such as “some”, “several”, “a few”
  - produce dimensions with no downstream report function

Context contract:

- required:
  - user query
  - prior repeated-run summary memory
  - replan request if gate failed before
  - allowed source families and retrieval policy
- optional:
  - known industry/entity aliases
  - user/account preference memory

Output contract:

- `dimension_plan`
- `source_obligations`
- `search_rounds`
- `query_requirements`
- `caliber_notes`

### 2. `collect_sources`

Current behavior:

- deterministic search execution against planned search phrases

Current inputs:

- `plan.search_rounds`
- existing `sources`
- runtime search provider

Current gap:

- still too tied to search phrases rather than retrieval strategy objects

Target role:

- `Source Hunter / Retrieval Strategist`

Prompt contract:

- this node may remain mostly tool-driven rather than fully prompt-driven
- if an LLM layer is added, it should refine search intents per dimension, not write prose

Context contract:

- required:
  - dimension plan
  - source obligations
  - target entities / regions / dates
  - known aliases
  - allowed domains or source families

Output contract:

- raw source candidates
- search event trace
- dimension coverage trace

### 3. `parse_sources`

Current behavior:

- deterministic text cleaning

Target role:

- `Parser / Structurer / Chunk Builder`

Prompt contract:

- mostly non-prompt infrastructure
- if an LLM helper is ever used, it should only support normalization or structure extraction for difficult cases

Context contract:

- required:
  - fetched source text
  - source metadata
  - parser policy

Output contract:

- normalized source text
- chunk list with lineage metadata
- section / heading / page anchors where available

### 4. `score_sources`

Current behavior:

- deterministic source quality scoring

Target role:

- `Source Quality Assessor`

Prompt contract:

- deterministic-first
- optional model assistance only for edge classification cases

Context contract:

- required:
  - source metadata
  - query
  - dimension linkage
  - source-family policy

Output contract:

- `source_quality_v2`
- usage role
- source role
- quality notes

### 5. `build_evidence`

Current behavior:

- deterministic source-to-evidence projection
- one source too easily becomes one evidence

Current gap:

- lacks multi-source synthesis
- lacks proposition-level reasoning
- support strength is too flattened

Target role:

- `Evidence Synthesizer`

Prompt contract:

- role:
  research evidence analyst
- must do:
  - synthesize multiple chunks/sources into proposition-bearing evidence
  - identify scope, support type, caveats, and contradiction
  - distinguish direct support from context/background
- must not do:
  - invent facts outside retrieved material
  - collapse unrelated chunks into one evidence item

Context contract:

- required:
  - retrieval pack of ranked chunks
  - source metadata
  - dimension plan
  - source obligations
  - target entity / region / time scope
- optional:
  - cross-source contradiction hints

Output contract:

- evidence bundle items with:
  - proposition summary
  - source/chunk lineage
  - support scope
  - caveats
  - contradiction flags

### 6. `build_claims`

Current behavior:

- deterministic obligation-shaped claims

Current gap:

- claim count too low
- claim types too coarse
- claim structure too tied to source family instead of report logic

Target role:

- `Claim Builder / Thesis Builder`

Prompt contract:

- role:
  research thesis and claim architect
- must do:
  - derive multiple claims from evidence bundles
  - classify claims by type when relevant:
    - factual
    - interpretive
    - risk
    - uncertainty
  - align claims to report dimensions and likely sections
- must not do:
  - create claims unsupported by evidence bundles
  - collapse the whole report into one coarse claim

Context contract:

- required:
  - dimension plan
  - evidence bundles
  - source obligations
  - query requirements
- optional:
  - prior revision feedback

Output contract:

- claim graph with:
  - claim text
  - claim type
  - linked evidence ids
  - support status hypothesis
  - chapter relevance

### 7. `editor1_draft`

Current behavior:

- current live prompt writes strict JSON sections/paragraphs only
- strongly constrained toward concise schema output

Current gap:

- not a real report writer
- not designed for long-form final report structure

Target role:

- `Editor1 Lead Analyst`

Prompt contract:

- role:
  senior research analyst writing the first complete report draft
- must do:
  - convert dimension plan + claim graph + evidence bundles into report outline and section drafts
  - write readable analytical prose
  - separate facts, inference, and caveats
  - propose tables, timelines, or diagrams when useful
- must not do:
  - output schema-only paragraphs as the final writing layer
  - invent support beyond claim/evidence context
  - hide uncertainty

Context contract:

- required:
  - query
  - dimension plan
  - report outline scaffold
  - claim graph
  - top evidence bundles per section
  - uncertainty notes
  - prior draft summary when revising
- optional:
  - memory hints about preferred report style

Output contract:

- structured report draft, not raw JSON-only paragraph lists
- should at least carry:
  - section intent
  - section body
  - evidence references
  - open caveats

### 8. `editor2_review`

Current behavior:

- deterministic issue generation for unsupported claims or source-family mismatch

Current gap:

- not a real reviewer
- does not review argument quality, structure balance, or interpretive overreach

Target role:

- `Editor2 Review Analyst / Opponent`

Prompt contract:

- role:
  skeptical reviewing analyst
- must do:
  - challenge weak reasoning
  - identify claim overreach
  - identify structural imbalance
  - surface missing uncertainty
  - propose revision priorities
- must not do:
  - rewrite the full report itself
  - ignore evidence lineage

Context contract:

- required:
  - report draft
  - dimension plan
  - claim graph
  - evidence bundles
  - retrieval support summary
- optional:
  - prior review issues
  - chief-gate warning notes

Output contract:

- review issue list with:
  - issue type
  - severity
  - affected section or claim
  - revision guidance
  - whether more evidence or rewrite is needed

### 9. `verify_claims`

Current behavior:

- deterministic support-status computation and quality scores

Target role:

- `Evidence Judge / Verifier`

Prompt contract:

- deterministic-first with optional model-assisted contradiction inspection
- should not be the main author of claims

Context contract:

- required:
  - claim graph
  - evidence bundles
  - source/chunk lineage
  - review issues
  - support matrix

Output contract:

- claim verification records
- quality scores
- contradiction flags
- evidence coverage notes

### 10. `chief_gate`

Current behavior:

- deterministic decision tree

Target role:

- `Chief Gate`

Prompt contract:

- may remain largely deterministic
- optional model assistance only for complex tradeoff explanation, not for hidden routing

Context contract:

- required:
  - claim verifications
  - review issues
  - quality scores
  - source obligation coverage
  - search stability summary
  - human-review thresholds

Output contract:

- decision
- reason
- route
- required actions
- human-review trigger payload when appropriate

### 11. `human_review`

Current behavior:

- payload-based manual pause node

Target role:

- `Human Review Surface`

Prompt contract:

- no LLM needed by default
- this is a product interaction contract more than a generation contract

Context contract:

- required:
  - gate reason
  - blocking issues
  - required actions
  - current draft snapshot
  - current report snapshot

Output contract:

- visible review payload with clear user actions:
  - approve
  - add evidence
  - rewrite
  - reject

### 12. `finalize_report`

Current behavior:

- deterministic readable report composition
- still too close to a stitched preview

Current gap:

- no real final report writer/composer contract

Target role:

- `Report Composer / Supervisor`

Prompt contract:

- role:
  final report composer ensuring readability, coherence, and audit alignment
- must do:
  - assemble or refine the final Markdown report
  - preserve section logic
  - preserve traceability
  - integrate final uncertainty and source notes
- must not do:
  - downgrade the report into audit-preview format
  - hide unresolved blockers when they still matter

Context contract:

- required:
  - approved or gated draft
  - claim graph
  - evidence bundles
  - verification summary
  - review issues
  - final decision state
- optional:
  - tool-composed tables/appendices

Output contract:

- final `report_markdown`
- optional structured `sections`
- audit sidecar references
- report metadata summary

## Cross-Node Context Policy

### Context Must Follow Business Need

Each node should only receive context that belongs to its business role.

Good rule:

- planner gets planning context
- evidence synthesizer gets retrieval context
- editors get section-ready claim/evidence context
- verifier gets support-check context

Bad rule:

- dumping the whole state into every node

### Context Packing Strategy

Future context packing should use:

- dimension-local retrieval packs
- section-local evidence packs
- claim-local support packs
- summary memory, not raw long-run history, for planner memory injection

## Prompt Governance Requirements

Every true LLM-authored node must eventually define:

- role identity
- mission
- allowed tools
- required inputs
- forbidden behaviors
- output schema or content contract
- fallback policy
- live validation focus

## Phase 0 Gap Summary

The most important current-to-target gaps are:

1. planner is not strict enough about explicit dimensions
2. retrieval is not yet chunk-first hybrid retrieval
3. evidence is still too source-projection-oriented
4. claims are still too obligation-shaped and too few
5. editor1 is still a JSON paragraph writer, not a lead analyst
6. editor2 is still a rule checker, not a real reviewer
7. final report is still a deterministic preview rather than a true report composer
8. memory is missing entirely as a planner input

## Next Use

This matrix should drive Phase 1-5 implementation in the parent plan.

Before changing any node behavior, implementation should first point to the
relevant section in this matrix and confirm:

- whether the node remains deterministic-first
- whether it becomes prompt-authored
- what context it is allowed to see
- what business artifact it is responsible for producing
