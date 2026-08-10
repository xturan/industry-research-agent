# Search Caliber Expansion v1

Status: active_phase2_graph_integration

Created: 2026-06-16

Primary active PLAN: no (sidecar to deep-research-report-productization-v1.md)

## Objective

Implement the search caliber expansion module per PRD v0.1. Insert a two-layer
LLM + deterministic guard between the planner and search execution, so the
system produces diversified, evidence-oriented search phrases instead of
query+suffix homogenized variants.

## Task Classification

- Primary area: `research_workflow`
- Secondary areas: `provider_layer`, `source_layer`, `eval_policy_ops`
- Execution mode: `local_direct` for module authoring + `light_subagent` for tests
- Type: implementation — new module + integration + tests

## Scope

In scope:

- `packages/research_harness/caliber_expander.py` — new module (~500-600 lines)
  - Layer 1: `IntentPlanner` — query → `intent_plan` (user_goal, query_levels, evidence_needs, expansion_policy, search_budget_advice)
  - Layer 2: `SearchPhraseBuilder` — query + intent_plan → `search_plan` (anchor_phrases, search_groups, deferred_search_ideas, quality_checks)
  - Deterministic Guard: `CaliberGuard` — suffix filter, long-overlap filter, dedup, anchor ratio checker, group intent validator
- `packages/research_harness/schemas.py` — add Pydantic models for intent_plan and search_plan
- `packages/research_harness/plan_semantic.py` — integration: caliber_expander runs after plan_semantic, before search_rounds are finalized
- `packages/research_harness/prompt_assets.py` — add 2 LLM prompts (intent planner + phrase builder)
- `tests/test_caliber_expander.py` — unit tests for guard rules, integration tests for full pipeline

Out of scope:

- Replacing search execution (Tavily) or Crawl4AI
- Golden query evaluation (use PRD section 16 acceptance cases manually)
- Replan / deferred expansion execution (v0.2)
- Multi-model voting or A/B testing

## Architecture

```
plan_semantic.build_semantic_plan()
        │
        ▼
[NEW] caliber_expander.expand_caliber()
        ├─ Layer 1: _intent_planner(query) → intent_plan
        │   ├─ LLM path (DeepSeek, JSON structured output)
        │   └─ Fallback: keyword-trigger rules
        │
        ├─ Layer 2: _search_phrase_builder(query, intent_plan) → search_plan
        │   ├─ LLM path
        │   └─ Fallback: template expansion by evidence_need type
        │
        └─ Guard: _caliber_guard(search_plan) → final_search_plan + review
            ├─ 11.2 anchor coverage
            ├─ 11.3 suffix filter
            ├─ 11.4 long-overlap filter
            ├─ 11.5 phrase length check
            ├─ 11.6 group intent validator
            └─ Dedup
                    │
                    ▼
[existing] search_rounds building (real_nodes.py _rewrite_search_rounds_for_diversity)
```

## Phases

### Phase 1: Module Implementation

Status: in_progress

Objective: Create caliber_expander.py with schemas, prompts, and guard. Integrate
into plan_task node via plan_semantic.py. Write focused tests.

Acceptance criteria:
- caliber_expander.py exists and imports cleanly
- `expand_caliber("2025年合肥低空经济上市公司年报披露与地方政策项目公示官方来源")` returns valid JSON
- Layer 1 identifies required policy + project + disclosure evidence needs
- Layer 2 produces at least 3 search groups with distinct intents
- Guard removes suffix-only variants
- Each search phrase has intent + reason fields
- Deterministic fallback works when LLM unavailable
- 10+ unit/guard tests pass

### Phase 2: Graph Integration

Status: pending

Objective: Wire caliber_expander into plan_task_provider_backed node. Search
rounds reflect caliber-expanded phrases.

### Phase 3: Manual Acceptance Validation

Status: pending

Objective: Run PRD section 16 test cases (TC-001 through TC-008) manually,
verify required evidence coverage.

## Risks

- Two additional LLM calls increase latency ~2-4s per query. Mitigation: Layer 1
  cache by normalized_query fingerprint; second call skippable if Layer 1 returns
  only 1 evidence need.
- LLM may still generate suffix variants despite prompt. Mitigation: Guard
  filters are deterministic last line of defense.
- DeepSeek JSON instability. Mitigation: Pydantic repair + keyword fallback.

## Progress

### 2026-06-16 — Phase 1 implemented, Phase 2 integrated

- Phase 1: `caliber_expander.py` created (~400 lines)
  - Pydantic schemas: IntentPlan, SearchPlan, UserGoal, EvidenceNeed, etc.
  - Layer 1: IntentPlanner — LLM prompt + keyword fallback
  - Layer 2: SearchPhraseBuilder — LLM prompt + template fallback
  - CaliberGuard: suffix filter, long-overlap filter, dedup, anchor injector,
    group intent validator
  - expand_caliber() main entry with full fallback path
  - `_build_fallback_intent_plan()`: 4 keyword families (企业披露/地方政策/项目公示/行业数据)
  - `_build_fallback_search_plan()`: template-based phrase generation per
    evidence need type
- Phase 2: Integrated into `plan_semantic.py`
  - `build_semantic_plan(enable_caliber_expansion=True)` → runs caliber
  - search_groups mapped to search_rounds
  - Caliber metadata added to plan result
  - Non-fatal: caliber failure falls back without breaking plan
- Tests: 18 passed (ruff + py_compile clean)
  - Guard unit tests: suffix filter, LCS overlap, dedup, anchor injection
  - Fallback: Layer 1 keyword detection, Layer 2 template generation
  - Schema validation: IntentPlan, SearchPlan Pydantic models
  - Integration: expand_caliber full pipeline with guards

## Next Action

Phase 3: Manual acceptance validation using PRD section 16 test cases (TC-001 through TC-008).
