# Source Quality Scoring v2

Status: pending_human_review_phase1_shadow_implemented

Created: 2026-06-09

Primary active PLAN: user_requested_sidecar

## Objective

Plan and implement a better source rating model that keeps the existing A/B/C/D
tier while replacing the confusing five-score average with an auditable source
quality layer.

The source layer must include freshness/timeliness for search-returned sources,
without duplicating the later Evidence Judge's claim-support work.

## Task Classification

- Primary area: `source_layer`
- Secondary areas: `research_workflow`, `eval_policy_ops`
- Protected contracts:
  - Do not silently change `SourceAssessment` public response shape.
  - Do not change EvidenceBundle or citation shape.
  - Do not change `/deep-research/analyze` response shape in Phase 1.
  - Do not remove the existing A/B/C/D tier or legacy five fields in Phase 1.

## Design Position

Keep A/B/C/D as source admission tier:

- A/B/C/D answers: "What kind of source is this, and is it admissible?"
- Source Quality v2 answers: "Why is this source credible, fresh, auditable,
  relevant to the query, and how should the pipeline use it?"
- Evidence Judge answers: "Does this source support a concrete claim?"

Do not put `claim_support_strength` in the source layer. That belongs to the
evidence layer because a source can support one claim strongly and another
claim weakly.

## Source Layer Fields

Phase 1 should compute these as a shadow structure, not as public
`SourceAssessment` schema fields:

```json
{
  "source_quality_v2": {
    "tier": "A",
    "source_role": "official_policy_original",
    "publisher_authority": 0.95,
    "auditability": 0.9,
    "freshness": {
      "score": 0.85,
      "label": "fresh",
      "publication_date": "2025-11-27",
      "date_source": "search_result_published_date",
      "age_days": 194,
      "validity_status": "likely_current",
      "notes": "Formal policy source; not stale by age alone."
    },
    "query_relevance": {
      "score": 0.76,
      "label": "related",
      "signals": {
        "query_phrase_match": true,
        "title_snippet_match": true,
        "extracted_text_match": false,
        "source_family_match": true,
        "discovered_by_phrase": "low altitude procurement"
      }
    },
    "credibility_score": 0.84,
    "credibility_label": "high",
    "usage_role": "primary_evidence_candidate",
    "not_sufficient_for": ["winning bid evidence", "revenue confirmation"],
    "reason": "Official policy source, current enough, auditable, and related to the policy aspect of the query."
  }
}
```

### Field Meanings

- `source_role`: what role the source plays, such as official policy original,
  public resource transaction, company disclosure, official interpretation, or
  commercial context.
- `publisher_authority`: how authoritative the publisher is. This is about who
  published the source, not whether it proves a claim.
- `auditability`: how easy the source is to verify and cite, based on URL
  stability, document number, attachment/PDF, date, and publisher identity.
- `freshness`: how current the source is for this research task. It must track
  both a numeric score and the evidence used to infer the date.
- `query_relevance`: how well the source matches the user's query before a
  concrete claim is generated.
- `usage_role`: how the pipeline is allowed to use the source, such as primary
  evidence candidate, supporting evidence candidate, context only, or exclude.
- `not_sufficient_for`: specific evidence needs the source cannot satisfy.

## Freshness / Timeliness Design

Freshness should be source-layer metadata, not evidence-layer judgment.

It should answer:

> Is this source current enough to be used for this research task?

It should not answer:

> Does this source prove a specific claim?

### Date Extraction Priority

1. Search result `published_date`, if available.
2. Structured crawler metadata, if available.
3. Date or year in URL.
4. Date or year in title.
5. Date or year in extracted text.
6. Unknown.

The chosen date must record `date_source`, so the dossier can explain why the
system thinks the source is fresh or stale.

### Freshness Rules By Source Role

Policy / regulation sources:

- Newer is useful, but older formal rules may still be valid.
- A policy should not be marked stale only because it is more than one year old.
- If the source is old, mark `validity_status=needs_validity_check` instead of
  blindly excluding it.

Procurement / transaction sources:

- More time-sensitive.
- Old procurement notices should usually be treated as historical evidence.
- Winning-bid or transaction records can remain useful for historical project
  confirmation, but not for "current opportunity" claims.

Statistics / data releases:

- Freshness depends on the requested period.
- The score should compare the source period with the query period when a query
  asks for a specific year or recent data.

Company disclosures:

- Annual reports and exchange announcements should be judged against reporting
  period and filing date.

News / interpretation sources:

- Stale quickly unless used only as historical context.

### Freshness Output Labels

- `fresh`: current enough for direct use.
- `acceptable`: usable, but not the newest available source.
- `historical`: useful only for historical context.
- `needs_validity_check`: formal source is old or date is unclear; check whether
  still effective.
- `unknown_date`: no reliable date was found.

## Query Relevance Design

`query_relevance` should not default to an LLM.

Use deterministic signals first:

- `query_phrase_match`: checks whether the user's original or expanded query
  terms appear in source title, snippet, or extracted text.
- `title_snippet_match`: checks whether the search result title and summary
  match the query intent before full extraction is available.
- `extracted_text_match`: checks the crawled body text or PDF text; this is
  stronger than title/snippet because it looks inside the source.
- `source_family_match`: checks whether the source type matches the evidence
  need, such as policy, procurement, statistics, disclosure, project record, or
  regulatory record.
- `search_phrase_that_discovered_source`: records which expanded phrase found
  the source and whether that phrase was broad or high-intent.

Use an LLM only when deterministic signals conflict or the source is high value.
When an LLM is used, record evaluator mode and visible reasoning output in the
dossier trace, but not hidden chain-of-thought.

## Credibility Score Design

Avoid a simple average.

Recommended computation:

1. Apply hard gates:
   - D-tier commercial media without original citation cannot be primary
     evidence.
   - Low auditability cannot be primary evidence.
   - Unknown date on time-sensitive sources reduces usage role.
2. Compute source credibility from:
   - `publisher_authority`
   - `source_role`
   - `auditability`
   - `freshness`
3. Use the weakest critical dimension when it creates citation risk.

Example:

An official source with high authority but very poor auditability should not
become high-confidence evidence just because the average looks good.

## Phase Plan

### Phase 0 - Planning And Glossary

- Create this PLAN.
- Update `docs/source-quality-scoring-v2.md` with the formal implementation
  model and term glossary.
- No code changes.

### Phase 1 - Shadow Source Quality v2

- Add internal `source_quality_v2` computation in Deep Research.
- Do not change public `SourceAssessment` schema.
- Store v2 source quality records in dossier context and trace.
- Render a Source Quality v2 table in dossier.
- Keep legacy five scores visible but mark their average as legacy.

Implementation units:

- `classify_source_role(domain, url, title, source_family)`
- `score_publisher_authority(domain, source_role, tier)`
- `score_auditability(domain, url, title, extracted_text)`
- `score_freshness(title, url, published_date, extracted_text, source_role, query)`
- `score_query_relevance(query, expanded_terms, discovered_phrase, title, snippet, extracted_text, source_role)`
- `derive_usage_role(tier, source_role, auditability, freshness, query_relevance)`

#### Phase 1 Execution Mode

Mode: light_subagent risk level, executed locally.

Reason: the change is a scoped source-layer / Deep Research dossier integration,
does not alter public response schemas, and keeps Source Quality v2 in shadow
context. Subagent spawning was not used because the available subagent tool
requires explicit user authorization for delegation.

Allowed write scope:

- `packages/sources/source_quality.py`
- `packages/sources/__init__.py`
- `packages/agents/deep_research.py`
- `packages/research_reports/dossier.py`
- focused tests and design docs

Forbidden changes:

- no `SourceAssessment` schema changes
- no `EvidenceItem` schema changes
- no `/deep-research/analyze` response-shape changes
- no EvidenceBundle or citation contract changes

### Phase 2 - Evidence-Layer Support Scoring

- Add evidence-level `claim_support_strength`, `support_type`, and
  `limitations` as internal/dossier context first.
- Keep EvidenceItem public schema unchanged unless a separate schema migration
  plan is approved.
- Make Evidence Judge consume source quality v2 plus evidence text.

### Phase 3 - Contract Migration Decision

- Decide whether to add optional public fields to `SourceAssessment` and/or
  `EvidenceItem`.
- If yes, write migration and compatibility impact explicitly before code.

## Validation Plan

Phase 1 validation:

- Unit tests for role, auditability, freshness, and query relevance scoring.
- Dossier rendering test for Source Quality v2 glossary fields.
- Focused Deep Research fake-provider test confirming v2 quality appears in
  dossier context.
- Focused API test confirming `/deep-research/analyze` response shape is
  unchanged.
- Live low-cost API run only after unit/API checks pass.

Required checks:

- `python -m py_compile` on changed files.
- `python -m ruff check` on changed files.
- `pytest -q tests/test_research_run_dossier.py`
- `pytest -q tests/test_deep_research_agent.py -k "not convenience_entry_point"`
- `pytest -q tests/test_research_api.py tests/test_research_run_dossier.py`
- Research contract focused tests if `packages/agents/**` changes.

## Risks

- If `query_relevance` is implemented too aggressively, good but indirect
  official sources may be discarded too early.
- If freshness rules are too simple, old but still-valid formal policies may be
  wrongly downgraded.
- If v2 fields are added to public schemas too early, downstream response-shape
  compatibility may break.
- If too many English field names appear in dossier without explanation, the
  output becomes abstract again. All dossier-visible keywords need glossary
  entries.

## Progress

### 2026-06-09 - Phase 1 shadow implementation completed

Implemented:

- Added `packages/sources/source_quality.py` with deterministic Source Quality
  v2 scoring: source role, publisher authority, auditability, freshness,
  query relevance, credibility score/label, usage role, and
  `not_sufficient_for`.
- Deep Research Phase 2 now carries `published_date`,
  `discovered_by_phrase`, and `round_objective` for collected search sources.
- Deep Research Phase 3 now computes `source_quality_v2` after the legacy
  A/B/C/D `SourceAssessment`, stores records in `source_quality_v2_by_url`,
  and records them in visible trace output with `source_quality_v2_mode`.
- Dossier rendering now includes a Source Quality v2 table and a Chinese
  glossary explaining all dossier-visible English keywords.
- `/deep-research/analyze` public response shape remains unchanged; v2 records
  are internal/dossier context only.

Validation:

- `python -m py_compile` on changed files -> pass.
- changed-file `python -m ruff check ...` -> pass.
- `pytest -q tests/test_sources_source_quality_v2.py` -> `3 passed`.
- `pytest -q tests/test_research_run_dossier.py` -> `3 passed`.
- `pytest -q tests/test_deep_research_agent.py -k "not convenience_entry_point"`
  -> `11 passed / 1 deselected`.
- `pytest -q tests/test_research_api.py` -> `3 passed`.
- Source regression:
  - `pytest -q tests/test_sources_layer.py` -> `8 passed`.
  - `pytest -q tests/test_sources_adapters_v1.py` -> `8 passed`.
  - `pytest -q tests/test_sources_hardening_step34.py` -> `4 passed`.
  - `pytest -q tests/test_sources_evals_step35.py` -> `7 passed`.
- Research contract:
  - `pytest -q tests/test_agents_workflow.py` -> `11 passed`.
  - `pytest -q tests/test_research_provider_integration.py` -> `9 passed`.
  - `pytest -q tests/test_deepseek_provider.py` -> `2 passed`.
- Repo-wide `python -m ruff check .` was run and still fails on pre-existing
  `.agent/hooks`, `.claude/worktrees`, and Unsloth cache files outside this
  change.

Assumptions:

- Phase 1 uses deterministic rules only. LLM-assisted relevance evaluation is
  deferred until deterministic signals prove insufficient.
- Live real-provider API validation is deferred as a cost-bearing next step
  unless the user requests it for this slice.

### 2026-06-09 - Low-cost real-provider API validation completed

Run:

- Local HTTP API: `POST /deep-research/analyze`
- Query: `2025年低空经济政策与公共资源采购中标证据 官方来源`
- `max_rounds=1`
- Providers: real DeepSeek + real Tavily via local `.env`
- Temporary DB: `data/tmp/source_quality_v2_live_api/reports.db`

Result:

- HTTP API completed successfully.
- Elapsed: `103.6s`
- Sources: `12`
- Evidence items: `12`
- Search rounds: `1`
- Estimated Tavily credits: `24`
- Overall confidence: `medium`
- Report ID in temp DB: `1`
- API response did not expose `source_quality_v2`.
- Dossier contained Source Quality v2 table, glossary, and trace
  `source_quality_v2_mode=deterministic_shadow`.

Artifacts:

- `data/tmp/source_quality_v2_live_api/live_summary.json`
- `data/tmp/source_quality_v2_live_api/analyze_response.json`
- `data/tmp/source_quality_v2_live_api/dossier.md`
- Persisted dossier path:
  `data/run_dossiers/deep_research/20260609/report_1/dossier.md`

Finding:

- The run proved V2 observability works, but also showed a first tuning issue:
  the query asked for procurement / winning-bid evidence, while the first-round
  sources were mostly policy, statistics, and interpretation pages. V2 correctly
  recorded `not_sufficient_for` such as `winning bid evidence`, but some
  source-family-mismatched policy sources still received
  `primary_evidence_candidate`.

Remediation completed:

- If `source_family_match=false` and the query/search phrase has procurement,
  statistics, disclosure, or regulatory intent, `query_relevance` is capped and
  `usage_role` cannot be primary.
- Added regression coverage:
  `test_family_mismatch_with_procurement_intent_is_not_primary`.

Post-remediation validation:

- changed-file `python -m ruff check ...` -> pass.
- `pytest -q tests/test_sources_source_quality_v2.py` -> `4 passed`.
- `pytest -q tests/test_deep_research_agent.py -k "source_tiering_records_source_quality_v2_shadow_context or not convenience_entry_point"`
  -> `11 passed / 1 deselected`.
- `pytest -q tests/test_research_run_dossier.py` -> `3 passed`.

### 2026-06-10 - Live dossier LLM trace quality audit completed

Audited:

- Reviewed the live dossier's seven LLM calls:
  - query understanding
  - parser / structurer evidence chain
  - thesis builder
  - opponent
  - evidence judge
  - risk analyst
  - report assembly
- Created the audit artifact:
  `data/tmp/source_quality_v2_live_api/llm_trace_quality_audit.md`.

Findings:

- V1 dossier observability is sufficient to inspect real model inputs and
  outputs, but downstream agent prompts remain too thin.
- Parser/Structurer evidence-chain construction failed with `ProviderParseError`
  / invalid JSON after receiving long polluted source text.
- Thesis Builder, Opponent, and Evidence Judge receive polluted evidence text
  containing page chrome such as breadcrumbs, image markdown, print buttons,
  language links, and `javascript:void(0)` navigation.
- Risk Analyst is under-grounded because it receives thesis summaries and
  evidence sufficiency only, without URLs, source tier, Source Quality v2, or
  raw/clean evidence.
- Report Assembly is the strongest node in this run because it acknowledges the
  procurement/winning-bid evidence gap, but it still lacks URL-level and
  claim-level support context.

Recommended next implementation slice:

- Add an LLM-prompt-only evidence text sanitizer.
- Add Parser/Structurer JSON retry/repair or structured fallback around the
  evidence-chain call.
- Pass compact Source Quality v2 capsules into downstream agents.
- Strengthen Thesis Builder, Opponent, Evidence Judge, and Risk Analyst prompt
  contracts without changing public response schemas.
- Add regression tests using the observed page chrome pollution examples.

## Next Action

Implement V2.1 observability quality remediation: clean evidence text before LLM
prompt assembly, pass Source Quality v2 capsules to downstream agents, and
strengthen agent prompt/output contracts while preserving public response
schemas.
