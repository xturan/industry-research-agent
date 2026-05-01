# Plan: Source v2 Tiaokuai Foundation

Status: completed  
Priority: high  
Owner: codex/human  
Scope: source subsystem  
Created: 2026-04-20  
Last Updated: 2026-04-20

## Objective
Refactor and expand the source subsystem into a China-specific line/block structured source system that is:
- more complete
- more stable
- easier to use
- more efficient for source-assisted research

## Scope
In scope:
- domestic source profile schema refactor
- line/block structured source registry fields
- router upgrades for line/block-aware routing
- source pack abstraction
- source-assisted research integration for source packs
- source efficiency/stability hardening where needed
- docs and validation updates

## Out of scope
- browser fallback
- OCR
- complex auth/login
- deep pagination across many domestic sites
- network-facing MCP server
- large international source rollout
- subagent orchestration

## Constraints
- Do not add many sites blindly.
- Keep deterministic and inspectable routing behavior.
- Preserve partial-failure tolerance and traceability.
- Keep source-assisted research backward-compatible where practical.
- Do not implement multiple phases at once.

## Phases
- [x] Phase 1: Tiaokuai schema refactor
- [x] Phase 2: Tiaokuai-aware routing
- [x] Phase 3: Source pack rollout
- [x] Phase 4: Source hardening and efficiency
- [x] Phase 5: Simplified usage surface

### Phase 1: Tiaokuai schema refactor
Goal:
- extend domestic source profiles with line/block aware fields

Target fields:
- governance_axis
- line_family
- regional_level
- info_type
- publisher_type
- source_role
- priority_hint

Success criteria:
- existing domestic profiles are migrated
- schema remains typed and inspectable
- current NDRC / SZSE paths still work

### Phase 2: Tiaokuai-aware routing
Goal:
- upgrade router so it understands line-vs-block reasoning

Expected behavior:
- policy-style queries prefer line-based primary sources first
- disclosure/company queries prefer exchange/disclosure sources
- local rollout / project landing queries prefer regional/block sources
- industry trend queries may blend association + line-based sources

Success criteria:
- router outputs line/block-aware score breakdown
- routing remains deterministic and explainable
- existing international routing is not broken

### Phase 3: Source pack rollout
Goal:
- introduce reusable domestic source packs

Planned packs:
- policy_pack_cn
- disclosure_pack_cn
- local_rollout_pack_cn
- industry_signal_pack_cn

Success criteria:
- at least two packs are real and usable
- source-assisted research can run with pack-based selection
- pack metadata is visible in response or trace

### Phase 4: Source hardening and efficiency
Goal:
- improve practical efficiency and stability

Planned work:
- canonical URL dedupe
- bounded fetch defaults
- per-pack sensible limits
- attachment/page evidence dedupe
- improved warnings and traces
- optional lightweight caching if clearly useful

Success criteria:
- repeated runs reduce unnecessary duplication
- bundle metadata is clearer
- source quality summary stays stable

### Phase 5: Simplified usage surface
Goal:
- make source usage easier at the top-level API/request layer

Examples:
- source_strategy = "cn_policy_first"
- source_pack = "policy_pack_cn"
- domestic_mode = "tiao_priority"
- regional_focus = ["anhui", "guangdong"]

Success criteria:
- upper-layer usage becomes simpler
- old source_ids path remains backward-compatible
- source choice is still inspectable

## Current phase
Completed

## Validation
Always run for source changes:
- `.agent/skills/source-regression-check.md`

Also run for domestic source changes:
- `.agent/skills/domestic-source-check.md`

Run for research request/response impact:
- `.agent/skills/research-contract-check.md`

Latest validation run (Phase 1):
- `python -m ruff check .`
- `pytest -q tests/test_sources_layer.py tests/test_sources_adapters_v1.py tests/test_sources_hardening_step34.py tests/test_sources_evals_step35.py tests/test_sources_router_domestic.py tests/test_sources_profile_adapter.py tests/test_sources_real_domestic_step42.py tests/test_sources_pdf_step43.py tests/test_sources_tiaokuai_phase1.py`
- Result: 45 passed, 0 failed

Latest validation run (Phase 2 + Phase 3):
- `python -m ruff check .`
- `pytest -q tests/test_sources_layer.py tests/test_sources_adapters_v1.py tests/test_sources_hardening_step34.py tests/test_sources_evals_step35.py tests/test_sources_router_domestic.py tests/test_sources_profile_adapter.py tests/test_sources_real_domestic_step42.py tests/test_sources_pdf_step43.py tests/test_sources_tiaokuai_phase1.py tests/test_sources_tiaokuai_phase23.py`
- Result: 49 passed, 0 failed

Latest validation run (Phase 4 + Phase 5):
- `python -m ruff check .`
- `pytest -q tests/test_sources_layer.py tests/test_sources_adapters_v1.py tests/test_sources_hardening_step34.py tests/test_sources_evals_step35.py tests/test_sources_router_domestic.py tests/test_sources_profile_adapter.py tests/test_sources_real_domestic_step42.py tests/test_sources_pdf_step43.py tests/test_sources_tiaokuai_phase1.py tests/test_sources_tiaokuai_phase23.py`
- Result: 52 passed, 0 failed

## Progress
- [x] Plan baseline created and set as primary active plan
- [x] Phase 1 implementation completed:
  - extended `SourceProfile` with tiaokuai fields: `governance_axis`, `line_family`,
    `regional_level`, `info_type`, `publisher_type`, `source_role`
  - added typed enums for the new fields
  - migrated domestic profiles in `china_policy.py`, `china_exchange.py`, `china_industry.py`
  - added Phase 1 migration tests in `tests/test_sources_tiaokuai_phase1.py`
- [x] Phase 2 implementation completed:
  - upgraded `SourceRouter.route(...)` to consume `SourceProfile` metadata via
    `profiles_by_source`
  - added tiaokuai scoring signals into `score_breakdown`:
    `tiaokuai_axis_bonus`, `tiaokuai_line_family_bonus`, `tiaokuai_regional_bonus`,
    `tiaokuai_info_type_bonus`, `tiaokuai_source_role_bonus`
  - added local-rollout candidate routing to avoid empty domestic recommendations on rollout
    query patterns
- [x] Phase 3 implementation completed:
  - introduced source-pack module `packages/sources/packs.py` with:
    `policy_pack_cn`, `disclosure_pack_cn`, `local_rollout_pack_cn`,
    `industry_signal_pack_cn`
  - added `QueryContext.source_pack` for explicit pack-based source selection
  - integrated source-pack behavior into router/service/tool flow:
    - `SourceRouter` applies pack candidates, pack bonus, and pack-based filtering
    - `SourceIntelligenceService.build_bundle_for_query(..., source_pack=...)` supports
      explicit pack handoff
    - route/bundle traces include `source_pack` metadata
  - added Phase 2/3 tests in `tests/test_sources_tiaokuai_phase23.py`
- [x] Phase 4 implementation completed:
  - added canonical URI dedupe in source evidence bundle assembly
  - dedupes `documents` and `evidence_items` with stable metadata counters
  - added per-pack bounded defaults:
    - `default_max_documents_per_source`
    - `default_max_evidence_per_source`
  - exposed dedupe/source-pack default application metadata in bundle trace output
- [x] Phase 5 implementation completed:
  - added top-level simplified usage fields in `QueryContext`:
    - `source_strategy`
    - `domestic_mode`
    - `regional_focus`
  - added strategy-to-pack mapping (`cn_policy_first`, `cn_disclosure_first`, etc.)
  - integrated strategy/mode/regional signals into router score breakdown and trace metadata
  - preserved backward compatibility for old non-pack routing paths
  - added/expanded Phase 4/5 tests in `tests/test_sources_tiaokuai_phase23.py`

## Risks
- schema migration could break current domestic collectors
- router may become too complex before source packs exist
- source packs may become a second abstraction layer with low adoption
- expansion pressure may cause premature source sprawl
- too much focus on completeness may reduce finishability
- new tiaokuai fields are optional by design; enforcement rules are not yet added and must be
  considered in later phases when introducing source-pack/router constraints
- source-pack routing currently uses static pack definitions; no dynamic account-policy overrides
  yet
- pack filtering is strict by design; mixed pack + broad discovery strategy needs explicit policy
  in later phases if required
- dedupe logic is currently bundle-time only; persistent storage-level canonicalization is still
  TODO for future source hardening work

## Next action
Plan completed.
Recommended next plan:
- `longtasks-substrate-v1.md` (queued)
