# AnySearch Skill Strong Evidence Eval v1

Status: completed

## Objective

Compare the official AnySearch Skill workflow with Tavily basic for difficult but obtainable Chinese industrial evidence, with separate judgments for project landing, enterprise disclosure, tender/procurement, and environmental/land records.

## Classification

- Primary area: `eval_policy_ops`
- Secondary areas: `source_layer`, `provider_layer`
- Execution mode: `local_direct`

## Scope

- Install and verify the official AnySearch Skill.
- Add a reusable strong-evidence query set with concrete entities and document targets.
- Compare AnySearch general search, AnySearch Skill vertical/hybrid search where supported, and Tavily basic.
- Score authority, entity/region match, evidence-family match, implementation signals, depth, noise, and latency.
- Preserve raw provider output and a per-family recommendation.

## Non-Goals

- Do not integrate AnySearch into production discovery routing.
- Do not change source or evidence contracts.
- Do not optimize production behavior for one test query.
- Do not treat media summaries as substitutes for official records.

## Provider Strategy

| Evidence family | AnySearch Skill route | Tavily route | Strong evidence target |
|---|---|---|---|
| Enterprise disclosure | General plus `finance.news/announcement` | Basic domain-aware search | Exchange/IR announcement with ticker, date, and event |
| Project landing | General search | Basic domain-aware search | DRC/project list/owner record with status and entity |
| Tender/procurement | General search | Basic domain-aware search | Procurement or public-resource detail/award notice |
| Environment/land | General search | Basic domain-aware search | EIA acceptance/approval or natural-resource/land record |

`business.company` may supplement entity identity but cannot prove project execution. AnySearch currently has no China-specific tender, EIA, or land vertical; those families must be evaluated as general discovery.

## Milestones

### M0 Skill Contract

- [x] Install official `anysearch-ai/anysearch-skill`.
- [x] Verify CLI and inspect relevant vertical contracts.
- [x] Record that only A-share announcement search directly maps to a target evidence family.

### M1 Case And Metric Design

- [x] Add 8 concrete, difficult, obtainable cases across four evidence families.
- [x] Encode expected strong domains, document signals, entity/region requirements, and weak-source exclusions.
- [x] Define deterministic family-specific metrics.

### M2 Harness

- [x] Add official Skill JSON-RPC/Markdown parsing and Tavily basic comparison.
- [x] Preserve raw output, normalized results, metrics, latency, and errors.
- [x] Add focused unit tests.

### M3 Live Gates

- [x] Run a four-case smoke gate.
- [x] Run the complete strong-evidence set.
- [x] Produce per-family recommendations instead of one misleading global winner.

### M4 Decision

- [x] Decide that AnySearch is useful as a supplemental discovery lane for disclosure, local tender, and EIA evidence, not as a Tavily replacement.
- [x] Defer production integration to a separate future PLAN.

## Validation

- `python -m py_compile scripts\\compare_search_skill_strong_evidence.py`
- `python -m ruff check scripts\\compare_search_skill_strong_evidence.py tests\\test_compare_search_skill_strong_evidence.py`
- `pytest -q tests\\test_compare_search_skill_strong_evidence.py`
- Four-case live smoke with one case per evidence family.
- Full live run with raw artifacts when provider quota permits.

## Acceptance Gates

- Results are grouped by evidence family.
- Official/primary-source rate and family match are visible independently from text depth.
- Enterprise disclosure evaluates vertical and general AnySearch routes separately.
- Hard-to-obtain local records expose failure rather than receive a false pass.
- No provider is recommended globally solely from aggregate score.

## Continue Rule

Continue automatically through milestones while validation is safe. Stop only for credentials/quota, repeated provider failure, protected-contract impact, or worsening regressions.

## Risks

- Anonymous AnySearch quota may limit the full run.
- Search results are time-sensitive and may differ between runs.
- AnySearch Skill returns Markdown rather than a stable structured search result schema.
- Tavily domain controls and AnySearch vertical capabilities are not feature-identical.

## Progress

- 2026-07-15: Official Skill installed and CLI verified.
- 2026-07-15: Relevant vertical inventory inspected. `finance.news/announcement` is directly useful; project/tender/EIA/land require general discovery.
- 2026-07-15: Compile, Ruff, and focused pytest passed (`3 passed`).
- 2026-07-15: Four-family smoke completed with all provider calls successful.
- 2026-07-15: Full 8-case run completed. AnySearch led enterprise disclosure, tender/procurement, and environment/land; Tavily led project landing.

## Decision

- Keep Tavily as the current general discovery baseline.
- Treat AnySearch Skill as a candidate supplemental lane, especially for A-share announcements and local EIA records.
- Do not use aggregate score as a provider replacement decision.
- Project landing remains a shared weakness and still needs source-family routing/direct-source remediation.

## Next Action

If production adoption is requested, create a separate PLAN for optional provider routing, budget controls, fallback semantics, and research-harness validation.
