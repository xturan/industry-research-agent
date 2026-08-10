# Plan: AnySearch vs Tavily Search Comparison v1

Status: completed
Priority: high
Owner: codex
Scope: eval_policy_ops
Created: 2026-07-15
Last Updated: 2026-07-15

## Objective

Build and run a repeatable, provider-neutral comparison of AnySearch and Tavily for Chinese industry-research discovery. Measure returned-result relevance, source authority/diversity, usable content depth, latency, and failure transparency before any production provider decision.

## Task Classification

Primary area: `eval_policy_ops`

Secondary areas:
- `provider_layer`
- `source_layer`

High-risk contracts protected:
- No change to `EvidenceBundle`, citations, source routing, provider abstraction, or public research response shapes.

## Scope

In scope:
- Standalone comparison CLI and a fixed UTF-8 cross-level query set.
- AnySearch auto routing versus Tavily `basic` and `advanced`, with equal result counts.
- Deterministic relevance, source authority/diversity, content-depth, latency, URL-validity, and failure metrics.
- Raw and aggregate JSON/Markdown artifacts plus focused mocked tests.

Out of scope:
- Production AnySearch integration or Tavily replacement.
- Evidence/source quality contract changes.

## Design Direction

```text
fixed cases
  -> AnySearch (zone=cn, zh-CN)
  -> Tavily basic (country=china)
  -> Tavily advanced (country=china)
  -> normalized results
  -> deterministic metrics + raw artifacts
  -> aggregate comparison
```

AnySearch exposes no public `search_depth` parameter, so depth is measured through returned cleaned-content coverage/length, expected-term coverage, unique-domain breadth, official-source coverage, and usable URL rate.

## Milestones

### Milestone 0: Contract And Baseline

Acceptance:
- Official AnySearch request/response contract is recorded.
- Credentials are detected without printing values.
- Execution route is `local_direct`.

### Completed. A production integration decision remains a separate PLAN.

Acceptance:
- CLI supports provider selection and records per-case errors without aborting the batch.
- Unit tests cover envelope parsing, normalization, metrics, and aggregation.

Validation:
- `python -m py_compile scripts\compare_search_providers.py tests\test_compare_search_providers.py`
- `python -m ruff check scripts\compare_search_providers.py tests\test_compare_search_providers.py`
- `pytest -q tests\test_compare_search_providers.py`

### Milestone 2: Live Comparison

Acceptance:
- At least one query per administrative level runs against both providers.
- Raw results and aggregate JSON/Markdown artifacts exist.
- Findings distinguish relevance, source quality, depth, latency, and failures.

## Continue Rule

Continue automatically when validation passes and no credential, quota, network, or protected-contract blocker exists.

## Stop Conditions

Stop only for missing external access, repeated provider failure without a safe diagnostic path, unexpected protected-contract requirements, or final done condition.

## Done Condition

- Harness and focused tests pass.
- Live comparison artifacts exist for available providers.
- Findings state what is proven, uncertain, and whether production integration is justified.
- PLAN and STATUS are updated.

## Validation Loop

1. Implement one provider-neutral slice.
2. Run compile, lint, and focused tests.
3. Run a one-query live smoke.
4. Run the cross-level set if smoke succeeds.
5. Inspect raw artifacts before drawing conclusions.

## Sandbox And Trust Notes

- Workspace: `E:\invest_agent`.
- Tavily credentials are present in `.env`.
- AnySearch uses its documented anonymous tier when `ANYSEARCH_API_KEY` is absent.
- Browser runtime is unavailable under current Windows sandbox error 1058; official HTTPS docs/API are reachable.

## Progress

- [x] Milestone 0
- [x] Milestone 1
- [x] Milestone 2

## Current Milestone

Completed. A production integration decision remains a separate PLAN.

## Risks

- Live result volatility requires raw timestamped artifacts.
- Anonymous AnySearch quota may limit a full run.
- Keyword metrics require raw-result inspection before conclusions.
- AnySearch returns cleaned content while Tavily defaults to snippets; report this as a provider capability difference.

## Rollback

Remove the standalone eval files and generated artifacts; no production path changes.

## Next Action

Implement the harness and tests, then run the cross-level live comparison.

## Final Validation Snapshot

- Python compile: passed.
- Ruff focused check: passed.
- Focused pytest: `3 passed`.
- One-case smoke: all three lanes succeeded.
- Eight-case raw run: 24/24 provider-case calls succeeded at `data/tmp/search_provider_comparison/full_8_20260715`.
- Geo-aware four-case gate: 12/12 provider-case calls succeeded at `data/tmp/search_provider_comparison/geo_gate_4_20260715`.

## Final Findings

- AnySearch led geo-aware average relevance (`89.62`) and returned depth (`94.98`).
- Source quality was effectively tied: AnySearch `57.25`, Tavily basic `57.5`.
- Tavily advanced did not consistently beat basic and showed more cross-region noise in local cases.
- AnySearch is suitable for an optional Chinese discovery-lane trial, not yet a Tavily replacement.
