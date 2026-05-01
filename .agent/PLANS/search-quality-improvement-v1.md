# Search Quality Improvement v1

Status: completed

Created: 2026-05-01

Primary active PLAN: yes

## Objective

Improve search source data quality by enhancing Tavily search parameters, expanding search phrase coverage, and dynamically targeting procurement/regulatory domains. Per Route A+B strategy: Layer 1 (Tavily + phrase enhancement) first, Layer 2 (LLM query decomposition) second.

## Design Direction

```
Query
  → query_decomposition (deterministic, enhanced with procurement keywords)
  → Tavily search (advanced depth for procurement queries, domain-targeted)
  → candidate filtering (existing + procurement domain boost)
  → Crawl4AI extraction (existing)
  → evidence classification (existing + procurement source class)
```

## Layer 1: Tavily Advanced Depth + Phrase Enhancement

Status: completed

### 1a. Smart Tavily Search Depth ✅
- `_task_has_procurement_context()` in `search_discovery.py` detects 15 procurement/regulatory keywords
- Procurement tasks → `search_depth="advanced"`, `topic="news"`
- General tasks → defaults to `basic` / `general` (cost-effective)

### 1b. Search Phrase Enhancement ✅
- `search_phrase_augmenter.py` — new module with `augment_search_phrases()`
- Deterministic expansion: 9 keyword families with 3 expansions each
- Region-qualified term injection (e.g., "合肥 招标" → "合肥 招标公告")
- LLM augmentation path ready for future integration

### 1c. Dynamic Domain Expansion ✅
- `_expand_task_domains_for_search()` in `search_assisted_domestic.py`
- Detects procurement context + known regions
- Adds procurement backbone domains via `local_source_domains_for_backbones()`
- Deduplicates and filters through `domain_has_procurement_signal()`

## Layer 2: LLM-Assisted Query Decomposition

Status: completed (deterministic augmentation active; LLM path scaffolded)

- `augment_search_phrases()` supports optional DeepSeek client for LLM augmentation
- Falls back to deterministic keyword expansion when LLM unavailable
- LLM prompt designed for Chinese government/data search term generation
- Integration point in `orchestrate_task()` via `_augment_task_search_phrases()`

## Validation

```powershell
ruff: All checks passed
pytest: 230 passed, 0 failed
  - 10 search_discovery
  - 25 search_assisted_domestic
  - 61 query_decomposition
  - 51 source_resolver
  - 71 lane_execution
  - 12 local_source_patterns
```

## Files Changed

| File | Change |
|------|------|
| `packages/sources/search_discovery.py` | +procurement context detection, smart search_depth/topic |
| `packages/sources/search_assisted_domestic.py` | +domain expansion, +phrase augmentation integration |
| `packages/sources/search_phrase_augmenter.py` | NEW — deterministic + LLM search phrase augmentation |

## Next Action

PLAN complete. To measure real impact: run a targeted live gate on procurement-affected cases with the enhanced search pipeline. Requires Tavily credits + DeepSeek audit.
