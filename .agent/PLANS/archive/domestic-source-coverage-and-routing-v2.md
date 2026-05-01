# Plan: Domestic Source Coverage and Routing v2

Status: completed
Priority: high
Owner: codex/human
Scope: domestic source coverage, retrieval planning, query routing, search-assisted discovery, evidence sufficiency
Created: 2026-04-28
Last Updated: 2026-04-28

## Objective

Upgrade the domestic source system from "search a few maintained sources" to a coverage-driven retrieval system that can determine which source lanes a query must cover, use DeepSeek as a constrained retrieval planner, use Tavily and Crawl4AI for search-assisted discovery/extraction, preserve direct structured sources, and report coverage gaps transparently.

## Task Classification

Primary area: `source_layer`

Secondary areas:
- `domestic_source_collectors`
- `provider_layer`
- `research_workflow`
- `eval_policy_ops`

Protected contracts:
- EvidenceBundle schema
- EvidenceItem citation fields
- `source_quality_summary` shape
- research analyze response shape
- provider abstraction semantics
- source routing response shape
- task/job status semantics
- `run` / `run_steps` meaning

Current step classification:
- Completed and ready for archive after Phase 7 Group3 acceptance
- Phase 6 multi-round search and coverage sufficiency judge completed with Group3 code-quality and functional validation
- Phase 5 completed city/county/park official-domain-first fallback discovery without one-profile-per-city expansion
- Phase 5 remediation preserved exact Suzhou Industrial Park discovery hints while avoiding maintained city/county profile or pack expansion
- Phase 7 completed the approved narrow workflow metadata bridge without protected response-shape, schema, provider/config, direct-keep, source override, or disabled-mode drift

## Background Reused

This PLAN reuses:
- completed `domestic-source-lite-refactor-v1` conclusions: Tavily is search discovery, Crawl4AI is page extraction, direct structured sources remain protected
- completed `research-workflow-source-assisted-integration-v1` conclusions: search-assisted evidence can enter the research workflow through existing contracts
- recent Q03 live artifact observation: Guangdong humanoid robot policy query leaked low-altitude/aviation supplemental domains into local policy tasks
- user decision: first solve Coverage Contract design, then expand national/provincial backbone and city/county fallback
- current DeepSeek provider infrastructure in `packages/providers/deepseek.py`, `packages/agents/provider.py`, and `packages/core/config.py`

## Problem Statement

The current source system has three structural weaknesses:

- Source selection is not yet coverage-driven. A query can produce search tasks without first declaring which evidence lanes must be covered.
- Domain routing is not semantically strict enough. Legal but irrelevant supplemental domains can enter unrelated tasks.
- City/county coverage cannot be maintained primarily through one profile per city or county. The system needs a fallback ladder that prevents catastrophic omission without overbuilding direct adapters.

## Design Direction

Target architecture:

```text
User Query
  -> Query Intent Extraction
  -> Coverage Contract Builder
  -> RetrievalPlan
  -> Source Lane Resolver
  -> Source Compatibility Gate
  -> Search / Direct / Fallback Execution
     -> Direct structured adapters
     -> Tavily Search Discovery
     -> Crawl4AI Extraction
  -> Coverage and Sufficiency Judge
  -> Additional targeted search rounds when gaps remain
  -> Existing Evidence Bundle / Research Workflow
```

Core principles:

- DeepSeek may propose retrieval plans, search phrases, and gap judgments.
- Deterministic code owns lane enums, source-role compatibility, direct-keep boundaries, domain allowlists, and repair/refusal.
- Tavily discovers URLs; it does not define source taxonomy or final conclusions.
- Crawl4AI extracts candidate pages; it does not decide evidence sufficiency.
- Direct structured sources remain primary for disclosure, project transaction, structured data, credit/GSXT, and judicial paths.
- Missing coverage must be represented as a structured coverage gap, not hidden behind a generic answer.

## CoverageLane Enum Draft

The first implementation should use fixed enum values. DeepSeek may choose from these values but must not invent new lanes at runtime.

| Enum | Required when | Primary source roles | Default execution path | Notes |
|---|---|---|---|---|
| `national_policy_direction` | Query asks about policy, direction, trend, outlook, regulatory framing, or national-level support | State Council, NDRC, MIIT, MOST, MOF, MOFCOM, sector regulator | search-assisted official domains, plus existing direct profiles where stable | Top-level policy anchor. |
| `provincial_policy_rollout` | Query names a province or asks about local implementation | provincial government portal, provincial DRC, provincial MIIT/industry department, provincial science/technology department | search-assisted official domains and maintained provincial profiles | Mandatory for province-level industry policy queries. |
| `city_county_fallback` | Query names a city, county, district, park, or asks about local landing below province level | city/county government portal, city DRC, city MIIT/industry bureau, city science/technology bureau | fallback discovery ladder using official domains | Avoids one-profile-per-city explosion. |
| `statistics_or_industry_data` | Query asks about scale, growth, future outlook, market size, company count, investment, export, or comparable quantitative support | NBS, provincial statistics bureau, city statistics bureau, customs, sector data pages | direct structured where available; search-assisted only for explanatory/statistical bulletin pages | Data lane should not be replaced by association commentary. |
| `project_transaction` | Query asks about projects, procurement, approval, tender, construction, landing, infrastructure, or implementation signals | government procurement, public resource trading, investment project approval, DRC project pages | direct structured primary; Tavily only supplement/entry discovery | Direct-keep primary path. |
| `enterprise_disclosure` | Query names listed companies, announcements, IR, annual reports, disclosures, securities filings, project progress by company | CNINFO, SSE, SZSE, BSE, NEEQ, company IR | direct structured primary; search-assisted only supplement | Direct-keep primary path. |
| `industry_association_signal` | Query asks for association, white paper, forum, alliance, exhibition, industry consensus, or needs supplemental trend signal | theme-compatible associations, alliances, topic platforms, white papers | search-assisted supplemental domains only after compatibility gate | Supplemental only. Must not replace official policy or data lanes. |
| `park_zone_signal` | Query asks about industrial parks, high-tech zones, development zones, free trade zones, demonstration zones | park/zone official sites, city/province park authorities | search-assisted official/whitelist fallback | Supplemental or local-implementation lane depending on query. |
| `media_news_context` | Query needs broader background but lacks official/public structured evidence | official media, reputable institutional news, local government reposts | optional late-stage fallback | Not accepted as primary evidence for policy or project claims. |

## Required Lane Selection Rules

Rules for common query classes:

| Query class | Required lanes | Optional lanes |
|---|---|---|
| national industry policy | `national_policy_direction` | `statistics_or_industry_data`, `industry_association_signal` |
| province industry outlook | `national_policy_direction`, `provincial_policy_rollout`, `statistics_or_industry_data` | `project_transaction`, `industry_association_signal`, `enterprise_disclosure` |
| city/county landing | `provincial_policy_rollout`, `city_county_fallback`, `project_transaction` | `park_zone_signal`, `statistics_or_industry_data` |
| project landing / infrastructure | `project_transaction`, `provincial_policy_rollout` | `city_county_fallback`, `park_zone_signal` |
| listed company project/disclosure | `enterprise_disclosure` | `project_transaction`, `industry_association_signal` |
| association / white paper supplement | `industry_association_signal` | `national_policy_direction` |
| quantitative market/data question | `statistics_or_industry_data` | `national_policy_direction`, `provincial_policy_rollout` |

## RetrievalPlan Schema Draft

The RetrievalPlan is the central contract between query understanding, source routing, search execution, and coverage validation.

```json
{
  "plan_id": "ret_plan_<stable_id>",
  "original_query": "广东人形机器人产业政策和项目落地情况",
  "normalized_theme": "人形机器人",
  "theme_aliases": ["具身智能", "智能机器人", "机器人产业"],
  "regions": [
    {
      "name": "广东",
      "level": "provincial",
      "parent": "全国"
    }
  ],
  "time_horizon": "latest_or_future_outlook",
  "user_intent": "assess_policy_and_project_rollout",
  "coverage_lanes": [
    {
      "lane_id": "provincial_policy_rollout",
      "required": true,
      "priority": 95,
      "source_role": "primary_official",
      "source_intents": [
        "province_government",
        "province_drc",
        "province_industry_department",
        "province_science_department"
      ],
      "execution_bucket": "search_assisted_sources",
      "domain_strategy": "region_official_domains_only",
      "search_phrases": [
        "广东 人形机器人 产业 政策",
        "广东 人形机器人 行动计划",
        "广东 具身智能 试点 示范"
      ],
      "exact_phrases": [],
      "negative_terms": ["无人机", "通航", "低空经济"],
      "success_criteria": {
        "min_accepted_documents": 1,
        "must_match_region": true,
        "must_match_theme": true,
        "must_match_source_role": true
      },
      "fallback_ladder": [
        "province_government_portal",
        "province_drc",
        "province_industry_department",
        "province_science_department",
        "national_policy_direction"
      ]
    }
  ],
  "round_policy": {
    "max_rounds": 3,
    "max_search_phrases_per_lane": 3,
    "max_candidates_per_lane": 3,
    "max_extractions_per_lane": 2,
    "max_estimated_tavily_credits": 12
  },
  "stop_conditions": {
    "required_lanes_attempted": true,
    "stop_when_all_required_lanes_sufficient": true,
    "stop_when_credit_budget_reached": true,
    "stop_on_direct_keep_boundary_violation": true
  },
  "coverage_gaps": [],
  "planner_metadata": {
    "planner_provider": "deepseek",
    "planner_model": "configured_by_env",
    "schema_version": "retrieval_plan_v1",
    "repair_applied": false
  }
}
```

### RetrievalPlan Field Semantics

| Field | Meaning | Authority |
|---|---|---|
| `plan_id` | Stable identifier for traceability | deterministic |
| `original_query` | User query | user input |
| `normalized_theme` | Main industry/topic | LLM proposal plus deterministic repair |
| `theme_aliases` | Search expansion terms | LLM proposal plus allowlisted/domain vocabulary |
| `regions` | Region focus and level | deterministic extraction plus LLM repair |
| `time_horizon` | latest, historical, future outlook, unspecified | LLM/deterministic |
| `user_intent` | canonical intent label | LLM proposal from fixed enum |
| `coverage_lanes` | required and optional evidence lanes | fixed enum, LLM may select |
| `source_intents` | abstract source roles, not free-form domains | fixed enum |
| `execution_bucket` | search-assisted, direct-structured, placeholder/manual | deterministic |
| `domain_strategy` | how domains are resolved | deterministic |
| `search_phrases` | Tavily or direct-query search phrases | LLM proposal plus validator |
| `negative_terms` | terms indicating semantic mismatch | LLM proposal plus deterministic theme map |
| `fallback_ladder` | escalation path when narrow source discovery fails | deterministic |
| `round_policy` | search budget and iteration cap | deterministic |
| `coverage_gaps` | missing or insufficient lanes after execution | deterministic judge plus LLM explanation |
| `planner_metadata` | audit metadata | deterministic, no private reasoning |

## Source Intent Enum Draft

Source intents are abstract and must be resolved into domains or adapters by deterministic code.

| Source intent | Typical domains/adapters | Allowed lanes |
|---|---|---|
| `state_council` | `gov.cn` | `national_policy_direction` |
| `national_drc` | `ndrc.gov.cn` | `national_policy_direction`, `project_transaction` supplement |
| `national_miit` | `miit.gov.cn` | `national_policy_direction` |
| `national_statistics` | `stats.gov.cn` | `statistics_or_industry_data` |
| `province_government` | province portal domains | `provincial_policy_rollout` |
| `province_drc` | province DRC domains | `provincial_policy_rollout`, `project_transaction` supplement |
| `province_industry_department` | province MIIT/industry bureau domains | `provincial_policy_rollout` |
| `province_statistics` | province statistics bureau domains | `statistics_or_industry_data` |
| `city_government` | city portal domains | `city_county_fallback` |
| `city_drc` | city DRC domains | `city_county_fallback`, `project_transaction` supplement |
| `city_industry_department` | city MIIT/industry bureau domains | `city_county_fallback` |
| `city_statistics` | city statistics bureau domains | `statistics_or_industry_data` |
| `public_resource_trade` | GGZY/direct adapters | `project_transaction` |
| `government_procurement` | CCGP/direct adapters | `project_transaction` |
| `exchange_disclosure` | CNINFO/SSE/SZSE/BSE/direct adapters | `enterprise_disclosure` |
| `theme_association` | theme-compatible association domains | `industry_association_signal` |
| `park_zone_official` | park/zone official domains | `park_zone_signal`, `city_county_fallback` |

## Domain Strategy Draft

| Strategy | Behavior |
|---|---|
| `national_official_domains_only` | Resolve only central ministry and national official domains. |
| `region_official_domains_only` | Resolve only province/city/county official domains matching the region. |
| `direct_structured_only` | Do not call Tavily/Crawl4AI primary path; use direct adapter or record direct-keep refusal if unavailable. |
| `theme_supplemental_domains_only` | Use only source domains tagged as compatible with the normalized theme. |
| `fallback_ladder_official_first` | Try exact local official source, then parent city/province/national official source. |
| `manual_or_placeholder` | Record unsupported coverage gap and do not fabricate search coverage. |

## DeepSeek Planner Contract

DeepSeek role:
- retrieval planner
- search phrase generator
- coverage-gap explainer
- candidate relevance helper

DeepSeek is not allowed to:
- answer the research query directly in the planning step
- invent domains, adapters, source categories, or coverage lanes
- route direct-keep lanes into Tavily/Crawl4AI as primary path
- weaken source compatibility gates
- store or emit private chain-of-thought

Required provider behavior:
- If `DEEPSEEK_API_KEY` is missing, use deterministic fallback planner.
- If DeepSeek output fails schema validation, repair once using deterministic defaults; if still invalid, fall back to deterministic planner.
- DeepSeek output must be traceable through provider/model/request metadata without storing secrets.

Environment placeholders:

```powershell
$env:DEEPSEEK_API_KEY="<set in current terminal only>"
$env:LLM_PROVIDER="deepseek"
$env:DEEPSEEK_RESEARCH_MODEL="deepseek-chat"
```

Do not persist credentials in PLAN, STATUS, scripts, test artifacts, or run logs.

## Multi-Round Search Strategy

Round policy:

| Round | Purpose | Execution |
|---|---|---|
| Round 0 | Build RetrievalPlan and coverage contract | DeepSeek planner or deterministic fallback |
| Round 1 | Search required official/direct lanes | Direct adapters and Tavily official-domain search |
| Round 2 | Search targeted gaps | Additional phrase/domain strategy only for insufficient required lanes |
| Round 3 | Supplemental fallback | association, park, city/county fallback, or media context with lower evidence role |

Stop after a round when:
- all required lanes are attempted and sufficient
- direct-keep boundary violation is detected
- credit budget is reached
- no compatible source domain or adapter exists
- provider failure prevents safe continuation

## Source Compatibility Gate

Candidate acceptance must check:
- source domain is allowed for the lane
- source role matches the lane
- region matches the lane when required
- theme or theme alias appears in title/snippet/content, unless the lane is a top-level broad policy source
- negative terms do not dominate the candidate
- attachment-first, search-page, login, and duplicate URLs remain rejected before extraction

New rejection reason candidates:
- `domain_topic_mismatch`
- `region_mismatch`
- `source_role_mismatch`
- `supplemental_used_in_primary_lane`
- `direct_keep_boundary_violation`
- `coverage_lane_not_supported`

## City and County Fallback Ladder

For city/county/park queries, use this ladder:

```text
exact city/county/park official domain
  -> city government portal
  -> city DRC / industry / science / statistics departments
  -> province government portal
  -> province DRC / industry / science / statistics departments
  -> national official policy or direct structured project/data source
  -> structured coverage gap
```

Acceptance:
- Do not claim city/county coverage if only province or national fallback was found.
- Record the fallback level used.
- If the city/county source is not discovered, return a transparent gap with parent-level evidence.

## Source Expansion Direction

### National Backbone

Priority source roles:
- State Council / China Government
- NDRC
- MIIT
- MOST
- MOF
- MOFCOM
- NBS
- Customs
- sector regulators where theme-specific

### Provincial Backbone

For each province, the source map should eventually include:
- province government portal
- province DRC
- province industry/MIIT department
- province statistics bureau
- province science/technology department
- province commerce department when export/trade is relevant
- province data/big-data bureau for digital economy, computing, AI, and low-altitude governance themes

### City/County Fallback

Do not create one maintained profile per city/county by default.

Use:
- dynamic official-domain discovery
- parent-region fallback
- strict source-role and region gates
- coverage-gap reporting

### Theme Supplemental Sources

Supplemental source maps must be theme-compatible:
- low-altitude economy: aviation, UAV, AOPA, low-altitude economy topic platforms
- humanoid robotics / embodied intelligence: robotics, AI, electronics, intelligent manufacturing associations and official topic platforms
- computing infrastructure: computing, data center, digital economy, energy, telecom sources
- photovoltaics: energy, industry, trade, customs, PV association sources
- battery swapping / NEV: MIIT, transport, energy, automotive associations, local pilot sources

Unknown themes must not default to all supplemental domains.

## Agent Execution Contract

Operating model:

```text
.agent/STATUS.md = current checkpoint
this PLAN = execution contract and state machine
agents = role-bound executors and validators
```

Role binding:

| Agent | Responsibility | Scope boundary |
|---|---|---|
| `invest_project_director` | Read STATUS and this PLAN, refine real-world validation, assign Group2/Group3 work, decide phase transition | May refine scope inside this PLAN but must not change user goal |
| `invest_agent_architecture_builder` | Design RetrievalPlan contracts, source compatibility rules, protected-contract boundaries, and migration strategy | Must stop if public schemas or response shapes need changes |
| `invest_feature_programmer` | Implement focused code, tests, scripts, and docs for assigned phase | Must not weaken direct-keep boundaries or expand domains without gates |
| `invest_code_quality_checker` | Run focused ruff, compile, pytest, import safety, and scope review | Does not self-certify functional behavior |
| `invest_functional_validator` | Validate real-world behavior, Q03 regression, coverage completeness, and gap transparency | Owns practical case design and negative-domain validation |
| `invest_project_summarizer` | Runs only after final done condition | Summarizes outcome and future capability updates |

Phase state machine:

```text
planned
  -> director_gate
  -> group2_assigned
  -> implemented
  -> code_checked
  -> functionally_validated
  -> phase_completed
  -> next_phase_started
```

## Phase 0 Director Gate Decision

Decision: proceed to Phase 1 only after the Architecture Gate records the public RetrievalPlan boundary. Phase 0 is planning/director complete for implementation assignment; production code remains untouched.

Task classification:
- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `provider_layer`, `research_workflow`, `eval_policy_ops`
- Current execution state: `director_gate_completed_pending_group2_phase1`

CoverageLane / RetrievalPlan v1 scope:
- Freeze the nine CoverageLane enum values currently listed in this PLAN for v1: `national_policy_direction`, `provincial_policy_rollout`, `city_county_fallback`, `statistics_or_industry_data`, `project_transaction`, `enterprise_disclosure`, `industry_association_signal`, `park_zone_signal`, `media_news_context`.
- Freeze SourceIntent and DomainStrategy as deterministic enums. DeepSeek may select enum values and propose phrases, but runtime code must reject invented lanes, invented source intents, invented domain strategies, and direct-keep boundary violations.
- RetrievalPlan v1 is a source-layer planning contract, not an API response-shape change and not an EvidenceBundle schema change.
- Public RetrievalPlan types should live in `packages/sources/retrieval_plan.py`. Do not add them to `packages/sources/schemas.py` in Phase 1 because that file already has unrelated public additions in the dirty worktree and should not become the release boundary for this PLAN.
- Phase 1 may use explicit imports from `packages.sources.retrieval_plan`; re-export through `packages/sources/__init__.py` is deferred unless the Architecture Gate proves it is required.

Frozen initial eval cases:
- Freeze `SRC-COV-01` through `SRC-COV-10` as the v1 eval suite.
- The Chinese query text in this PLAN is valid UTF-8; any mojibake observed in PowerShell output is a console/rendering issue, not a required PLAN correction.
- `SRC-COV-01` is the Q03 regression gate: Guangdong humanoid robotics policy/project routing must not accept low-altitude, UAV, aviation, or AOPA-style supplemental domains for required official/local lanes.
- `SRC-COV-05` and `SRC-COV-07` are the first city/county/park fallback gates: city/park coverage must record fallback level and must not claim exact local coverage when only parent-level evidence exists.
- `SRC-COV-10` remains a supplemental-lane negative-control case: it must not fan out into all official policy lanes unless the query asks for policy coverage.

Real-world validation plan:
- Offline Phase 1 validation must validate RetrievalPlan construction, enum repair/refusal, direct-keep bucket assignment, Q03 negative-domain terms, and city/county fallback ladder generation without Tavily, Crawl4AI, or DeepSeek credentials.
- Functional validation must inspect actual plan objects, not only test pass/fail output. Required observable fields: `coverage_lanes`, `source_intents`, `execution_bucket`, `domain_strategy`, `negative_terms`, `fallback_ladder`, `round_policy`, `stop_conditions`, `planner_metadata`.
- Q03 negative-domain validation must assert that low-altitude/aviation supplemental source intents or domains are absent from required official policy/project/data lanes for `SRC-COV-01`.
- City/county fallback validation must include at least one city policy/project case and one park/zone case. Pass requires a generated `city_county_fallback` or `park_zone_signal` lane, official-first fallback ladder, and transparent parent fallback/gap semantics.
- DeepSeek live validation is not mandatory in Phase 1. If credentials are absent, deterministic fallback is the expected path and must be recorded as such.

Group2 Phase 1 assignments:

1. `system_contract_architect`
   - Backing subagent: `invest_agent_architecture_builder`
   - Objective: produce the Phase 1 Architecture Gate for RetrievalPlan public type boundary, protected-contract impact, and fallback planner state machine.
   - Owned files / modules: `.agent/PLANS/domestic-source-coverage-and-routing-v2.md`, `.agent/STATUS.md`, optional docs under `docs/` if a boundary note is needed.
   - Forbidden paths / contracts: no production code edits; no EvidenceBundle, EvidenceItem citation, `source_quality_summary`, research analyze response, source routing response, provider abstraction, task/job, `run` / `run_steps`, content asset metadata, or delivery state-transition changes.
   - Required output: Architecture Gate with `Decision: proceed | revise | block`, explicit allowed write scope for the implementation worker, and rollback/fallback plan.

2. `source_provider_integrator`
   - Backing subagent: `invest_feature_programmer` with source/provider lane role card
   - Objective: implement typed RetrievalPlan contracts and deterministic fallback planner for Phase 1 after Architecture Gate proceeds.
   - Owned files / modules: `packages/sources/retrieval_plan.py`, `packages/sources/query_decomposition.py`, `tests/test_sources_retrieval_plan.py`, focused additions to `tests/test_sources_query_decomposition.py`.
   - Forbidden paths / contracts: `packages/sources/schemas.py`, `packages/agents/workflow.py`, `packages/providers/**`, `packages/core/config.py`, API response schemas, EvidenceBundle/citation models, task/job state, delivery/content modules, broad profile expansion under `packages/sources/profiles/**`.
   - Required output: valid deterministic RetrievalPlan generation for the frozen cases, direct-keep bucket preservation, unknown supplemental-theme refusal, and structured planner metadata without secrets.

3. `eval_harness_implementer`
   - Backing subagent: `invest_feature_programmer` with eval-harness lane role card
   - Objective: only if needed by Architecture Gate, add a small offline Phase 1 eval helper for the frozen `SRC-COV-01..10` RetrievalPlan cases.
   - Owned files / modules: `data/tmp/_retrieval_plan_phase1_eval.py` or a similarly scoped temporary eval script.
   - Forbidden paths / contracts: production source routing/execution modules, live provider credentials, broad data captures, any script that requires live Tavily/DeepSeek to pass Phase 1.
   - Required output: JSON-printable offline eval summary suitable for Group3 functional validation.

Group3 Phase 1 validation assignments:

1. `invest_code_quality_checker`
   - Run focused scope and quality checks:
     ```powershell
     python -m ruff check packages\sources\retrieval_plan.py packages\sources\query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
     python -m py_compile packages\sources\retrieval_plan.py packages\sources\query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
     pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
     ```
   - Also run the relevant source-regression subset if the implementation changes existing query decomposition behavior beyond additive planner construction.
   - Report dirty-worktree caveats and confirm no forbidden paths changed.

2. `invest_functional_validator`
   - Validate the frozen `SRC-COV-01..10` cases against the Phase 1 real-world validation plan.
   - Mandatory checks: Q03 negative-domain validation, direct-keep lane assignment for disclosure/project cases, unknown supplemental-theme non-fanout, city/county fallback and park/zone fallback cases, and deterministic fallback behavior without provider credentials.
   - Treat "tests pass" as insufficient unless actual plan fields and rejection/fallback semantics match this PLAN.

High-risk protected contracts and stop conditions:
- Stop if Phase 1 needs to modify `packages/sources/schemas.py`, EvidenceBundle schema, EvidenceItem citation fields, `source_quality_summary`, research analyze response shape, provider abstraction semantics, source routing response shape, task/job state, `run` / `run_steps`, content asset metadata, or delivery state transitions.
- Stop if RetrievalPlan cannot remain a source-layer planning contract without downstream response-shape changes.
- Stop if Q03 cannot be fixed without broad supplemental-domain expansion or weakening official-domain gates.
- Stop if city/county fallback requires one maintained profile per city/county instead of official-first discovery and structured gaps.
- Stop if live provider credentials become mandatory for Phase 1 acceptance.

## Phase 1 Architecture Gate Decision

Decision: proceed.

Classification:
- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `provider_layer`, `research_workflow`, `eval_policy_ops`
- Gate type: `system_contract_architect` / `invest_agent_architecture_builder`
- Gate scope: architecture and assignment only; no production code implementation in this gate.

Affected contracts:
- New source-layer planning contract: `RetrievalPlan` v1, `CoverageLane`, `SourceIntent`, `DomainStrategy`, lane-level success criteria, fallback ladder, round policy, stop conditions, and planner metadata.
- Existing source query decomposition contract: may be used as an input/compatibility bridge, but must not become the public RetrievalPlan schema.
- Existing direct-keep source boundaries: `enterprise_disclosure`, `project_transaction`, and structured data lanes remain direct primary paths.
- Existing protected contracts remain unaffected: EvidenceBundle schema, EvidenceItem citation fields, `source_quality_summary`, research analyze response shape, source routing response shape, provider abstraction semantics, task/job status semantics, `run` / `run_steps`, content asset metadata, and delivery state transitions.

Affected modules:
- Planned Phase 1 implementation modules: `packages/sources/retrieval_plan.py`, `packages/sources/query_decomposition.py`.
- Planned Phase 1 tests: `tests/test_sources_retrieval_plan.py`, focused additions to `tests/test_sources_query_decomposition.py`.
- Optional offline eval helper only if implementation needs a JSON-printable gate artifact: `data/tmp/_retrieval_plan_phase1_eval.py`.
- Forbidden for Phase 1: `packages/sources/schemas.py`, `packages/agents/workflow.py`, `packages/providers/**`, `packages/core/config.py`, API schemas, evidence/citation models, task/content/delivery modules, and broad profile expansion.

Current boundary:
- Current `decompose_query` emits task-family plans with execution buckets and include domains.
- Current search-assisted execution consumes `QueryDecompositionTask` and gates direct structured tasks away from Tavily/Crawl4AI.
- Retrieval planning does not yet exist as a typed source-layer contract; `packages/sources/retrieval_plan.py` is absent at this gate.
- Existing dirty worktree includes unrelated and pre-existing production changes, including `packages/sources/schemas.py`; those are not part of Phase 1 and must not be edited by this slice.

Proposed boundary:
- `packages/sources/retrieval_plan.py` owns the public source-layer planning types and deterministic fallback planner helpers for Phase 1.
- `packages/sources/query_decomposition.py` may call or adapt the deterministic planner, but only as a bridge that preserves existing callers.
- RetrievalPlan v1 is internal source-layer planning state. It must not be added to API response models, Source EvidenceBundle, RAG EvidenceBundle, citation structures, or research analyze response shape in Phase 1.
- DeepSeek is not wired in Phase 1. Planner metadata must support deterministic fallback and future provider attribution without requiring credentials or changing provider abstraction semantics.

Implementation slices:
- `source_provider_integrator`: implement typed RetrievalPlan contracts and deterministic fallback planner in the approved production/test files.
- `eval_harness_implementer`: optional only if the implementer needs an offline JSON summary for `SRC-COV-01..10`; it must not become a live-provider dependency.
- Group3 validators remain separate from Group2 implementation and must inspect actual plan objects, not only test pass/fail status.

Allowed write scope:
- For this Architecture Gate: `.agent/PLANS/domestic-source-coverage-and-routing-v2.md`, `.agent/STATUS.md`, optional docs under `docs/`.
- For Phase 1 implementation after this gate: `packages/sources/retrieval_plan.py`, `packages/sources/query_decomposition.py`, `tests/test_sources_retrieval_plan.py`, focused additions to `tests/test_sources_query_decomposition.py`.
- Optional Phase 1 eval helper: `data/tmp/_retrieval_plan_phase1_eval.py`, only if it is offline, credential-free, and JSON-printable.

Forbidden changes:
- Do not add RetrievalPlan, CoverageLane, SourceIntent, or DomainStrategy types to `packages/sources/schemas.py` in Phase 1.
- Do not change EvidenceBundle, EvidenceItem, Citation, `source_quality_summary`, research analyze responses, source routing responses, provider abstraction semantics, task/job state, `run` / `run_steps`, content asset metadata, or delivery state transitions.
- Do not edit `packages/agents/workflow.py`, `packages/providers/**`, `packages/core/config.py`, or broad `packages/sources/profiles/**` expansion in Phase 1.
- Do not make live Tavily, Crawl4AI, or DeepSeek credentials mandatory for Phase 1 validation.
- Do not use province-level or national-level evidence to claim city/county coverage. Parent fallback evidence must be represented as fallback/gap, not exact local coverage.
- Do not let Guangdong humanoid robotics lanes inherit low-altitude, aviation, UAV, or AOPA supplemental source intents/domains.
- Do not default unknown supplemental themes to every supplemental domain.

Validation design for Phase 1:
- Unit/schema validation:
  ```powershell
  python -m ruff check packages\sources\retrieval_plan.py packages\sources\query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
  python -m py_compile packages\sources\retrieval_plan.py packages\sources\query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
  pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
  ```
- Contract/scope validation:
  ```powershell
  git diff --name-only -- packages\sources tests data\tmp .agent docs
  Select-String -Path packages\sources\schemas.py -Pattern 'RetrievalPlan','CoverageLane','SourceIntent','DomainStrategy'
  ```
  The first command must show only the approved Phase 1 files plus known pre-existing dirty files; the second command must not show new Phase 1 type additions in `packages/sources/schemas.py`.
- Functional validation must inspect constructed RetrievalPlan objects for `SRC-COV-01..10` and verify: `coverage_lanes`, `source_intents`, `execution_bucket`, `domain_strategy`, `negative_terms`, `fallback_ladder`, `round_policy`, `stop_conditions`, and `planner_metadata`.
- Q03 hard negative: `SRC-COV-01` must include required national/provincial/project/data attempts for Guangdong humanoid robotics and must exclude low-altitude, aviation, UAV, AOPA-style supplemental domains/source intents from required official/project/data lanes.
- Direct-keep validation: `SRC-COV-05`, `SRC-COV-06`, and `SRC-COV-08` must keep project/disclosure lanes in `direct_structured_only` or the existing equivalent direct bucket; Tavily/Crawl4AI can only be supplemental or refused for those primary lanes.
- City/county and park validation: `SRC-COV-05` and `SRC-COV-07` must generate city/park fallback ladders. If only province/national fallback is available, the plan must label parent fallback or coverage gap rather than exact city/county coverage.
- Supplemental negative-control validation: `SRC-COV-10` must stay supplemental-only and must not fan out to all official policy lanes or all supplemental domains unless requested by query semantics.
- Deterministic fallback validation: Phase 1 must pass with `DEEPSEEK_API_KEY`, `TAVILY_API_KEY`, and Crawl4AI live access absent.

Rollback / fallback:
- If RetrievalPlan construction breaks existing query decomposition behavior, keep `decompose_query` legacy output as the compatibility path and route implementation back to `source_provider_integrator` with a narrower adapter-only fix.
- If typed planning requires protected response/schema changes, stop Phase 1 and open a revised Architecture Gate before any implementation.
- If Q03 cannot be satisfied without weakening official-domain gates or adding broad supplemental domains, block implementation and redesign the compatibility gate.
- If city/county fallback cannot distinguish exact local coverage from parent fallback, represent the lane as structured coverage gap and defer execution integration to Phase 5.
- If live provider integration becomes necessary, defer it to Phase 2; Phase 1 acceptance remains deterministic/offline.

Group2 implementation instructions:
- Implement `CoverageLane`, `SourceIntent`, `DomainStrategy`, `RetrievalPlan`, lane item models, success criteria, fallback ladder fields, round policy, stop conditions, coverage gaps, and planner metadata in `packages/sources/retrieval_plan.py`.
- Freeze CoverageLane v1 to exactly the nine PLAN lanes: `national_policy_direction`, `provincial_policy_rollout`, `city_county_fallback`, `statistics_or_industry_data`, `project_transaction`, `enterprise_disclosure`, `industry_association_signal`, `park_zone_signal`, `media_news_context`.
- Keep enums fixed and reject or repair unknown lane/source/domain-strategy values deterministically; do not allow LLM invented lanes.
- Add deterministic fallback planning that maps representative query classes to required/optional lanes, source intents, execution buckets, domain strategies, search phrases, negative terms, fallback ladder, and metadata.
- Adjust `packages/sources/query_decomposition.py` only as needed to expose or bridge deterministic RetrievalPlan construction while preserving existing `decompose_query` callers and direct-keep controls.
- Fix known planning hazards in the RetrievalPlan path: local rollout must not inherit all supplemental domains, unknown supplemental themes must not fan out to every supplemental domain, and Q03 humanoid robotics must carry low-altitude/aviation/UAV/AOPA negative terms.
- Do not change source execution, provider configuration, research workflow, API schemas, or evidence bundle conversion in Phase 1.

Group3 validation instructions:
- `invest_code_quality_checker` must run the focused ruff, py_compile, and pytest commands listed above, then inspect `git diff --name-only` for forbidden-path drift.
- `invest_functional_validator` must validate actual RetrievalPlan objects for `SRC-COV-01..10`; tests passing alone is insufficient.
- Required functional assertions: Q03 negative-domain exclusion, direct-keep bucket preservation, unknown supplemental-theme non-fanout, city/county and park fallback/gap semantics, and deterministic fallback behavior without provider credentials.
- Group3 must record whether `packages/sources/schemas.py` remained untouched by Phase 1 despite pre-existing dirty-worktree additions.
- If optional `data/tmp/_retrieval_plan_phase1_eval.py` is created, Group3 should run it offline and verify the JSON summary is credential-free and contains no secrets.

Gate result:
- Decision: proceed.
- Rationale: Phase 1 can be implemented as a narrow source-layer planning contract in a new module plus compatibility tests, without changing protected public response/evidence/provider/task contracts.
- Human-review stop remains required if implementation discovers that the public schema, downstream response shape, provider abstraction, or workflow execution path must change.

## Phase 2 Architecture Gate Decision

Decision: proceed.

Classification:
- Primary area: `source_layer`
- Secondary areas: `provider_layer`, `domestic_source_collectors`, `research_workflow`, `eval_policy_ops`
- Gate type: `system_contract_architect` / `invest_agent_architecture_builder`
- Gate scope: architecture and assignment only; no production code implementation in this gate.

Affected contracts:
- Provider abstraction: Phase 2 may consume the existing `JsonProviderClient` / `DeepSeekProviderClient.generate_json` boundary, but must not change provider exception semantics, metadata shape, or research-agent provider resolution behavior.
- Config settings: Phase 2 may reuse existing `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_RESEARCH_MODEL`, timeout, retry, max-token, and reasoning-storage settings. New planner-specific settings are allowed only if backward-compatible defaults preserve current behavior.
- Source-layer RetrievalPlan only: DeepSeek output is an optional proposal for `packages/sources/retrieval_plan.py` models and must be validated into the existing RetrievalPlan v1 contract.
- Protected contracts remain unchanged: API response shapes, EvidenceBundle schema, EvidenceItem citation fields, `source_quality_summary`, research analyze response shape, source routing response shape, task/job status semantics, `run` / `run_steps` meaning, content asset metadata, and delivery state transitions.

Allowed write scope for Phase 2 implementation:
- Preferred production module: `packages/sources/retrieval_planner_deepseek.py`.
- Required focused test module: `tests/test_sources_retrieval_planner_deepseek.py`.
- Existing provider tests may be extended only for current `DeepSeekProviderClient` JSON/metadata behavior: `tests/test_deepseek_provider.py`.
- `packages/providers/**` is allowed only for a narrow reusable provider helper or smoke module that is backward-compatible with existing provider contracts; do not change existing method signatures or exception classes unless this gate is revised.
- `packages/core/config.py` is allowed only for optional planner-specific settings with safe defaults, for example planner enablement, planner model override, or planner max tokens. These settings must not make DeepSeek mandatory and must not alter existing research LLM defaults.
- `.agent/PLANS/domestic-source-coverage-and-routing-v2.md` and `.agent/STATUS.md` must be updated after implementation and validation.

Forbidden changes:
- Do not change API request/response models, EvidenceBundle, EvidenceItem, Citation, `source_quality_summary`, research analyze response shape, source routing response shape, task/job status, `run` / `run_steps`, content metadata, or delivery transitions.
- Do not wire RetrievalPlan execution into `packages/agents/workflow.py` in Phase 2; workflow consumption belongs to Phase 7.
- Do not add planner fields to `packages/sources/schemas.py` or move RetrievalPlan public types out of `packages/sources/retrieval_plan.py`.
- Do not weaken direct-keep boundaries: `project_transaction`, `enterprise_disclosure`, and structured-data primary lanes must remain direct structured paths.
- Do not let DeepSeek invent domains, source lanes, source intents, domain strategies, execution buckets, fallback ladders, or compatibility gates.
- Do not persist `DEEPSEEK_API_KEY`, prompts containing secrets, provider raw private reasoning, or credentials in metadata, PLAN, STATUS, eval artifacts, logs, or tests.
- Do not make live DeepSeek credentials mandatory for required Phase 2 validation.

DeepSeek planner contract:
- Prompt boundary: DeepSeek is a retrieval planner/search-phrase proposer only. The system prompt must require one strict JSON object matching RetrievalPlan-compatible fields and must explicitly forbid direct answers, investment advice, private reasoning, and source/domain invention.
- Schema validation: parse provider JSON into existing Pydantic RetrievalPlan v1 models with `extra="forbid"` semantics preserved. Unknown enum values, unsupported lanes, bad execution buckets, invalid fallback fields, or schema extras must not pass through.
- Repair once: if provider JSON is syntactically invalid, rely on provider JSON repair once; if parsed JSON fails RetrievalPlan schema validation, perform one deterministic repair/normalization pass using fixed enums and source-layer defaults. If still invalid, fall back to deterministic planner.
- Fallback: missing key, provider config/auth/request/retry/parse/schema failure, refusal, empty content, direct-answer content, or unsafe metadata must return deterministic `build_deterministic_retrieval_plan(query)` with planner metadata recording fallback without secrets.
- No private reasoning: do not store `reasoning_content`; metadata may record `reasoning_available` as a boolean only.
- No secrets: metadata must include provider/model/schema/fallback/repair/refusal status only, never API keys, raw headers, prompts with secrets, environment values, or full provider raw response.
- No direct answer: reject or ignore outputs that answer the research question instead of emitting a plan.
- No invented domains/lanes: DeepSeek may propose `search_phrases`, `theme_aliases`, and lane selection from fixed enums only; deterministic code owns allowed domains, source-role compatibility, direct-keep boundaries, domain strategies, round policy, stop conditions, and fallback ladders.

Validation design:
- Missing-key fallback: instantiate planner with absent `DEEPSEEK_API_KEY` or failing provider factory and assert deterministic plan output plus credential-free metadata.
- Mock invalid JSON: provider/client returns invalid JSON then valid JSON; assert provider repair behavior remains covered and planner validates the final plan.
- Mock invalid enum/schema: DeepSeek JSON includes invented lane/source/domain strategy or extra fields; assert one deterministic repair/refusal path and fallback when still invalid.
- Mock refusal/direct answer: provider returns refusal text or an answer narrative instead of a plan; assert deterministic fallback and refusal/fallback metadata.
- No secrets in metadata: inspect `planner_metadata`, provider metadata, eval artifacts, and logs used by tests for absence of API key/env values, raw private reasoning, and raw prompt dumps.
- Focused pytest:
  ```powershell
  python -m ruff check packages\sources\retrieval_planner_deepseek.py tests\test_sources_retrieval_planner_deepseek.py tests\test_deepseek_provider.py
  python -m py_compile packages\sources\retrieval_planner_deepseek.py tests\test_sources_retrieval_planner_deepseek.py tests\test_deepseek_provider.py
  pytest -q tests\test_sources_retrieval_planner_deepseek.py tests\test_deepseek_provider.py
  ```
- Source regression check:
  ```powershell
  pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
  ```
- Optional live smoke only if `DEEPSEEK_API_KEY` exists in the current process; skipped live smoke is acceptable and must be recorded:
  ```powershell
  $env:PYTHONIOENCODING='utf-8'
  $env:PYTHONUTF8='1'
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
  pytest -q tests\test_sources_retrieval_planner_deepseek.py -m live
  ```

Group2 implementation instructions:
- `source_provider_integrator` should add a source-layer adapter in `packages/sources/retrieval_planner_deepseek.py` that accepts a query, optional `JsonProviderClient`, and optional settings object/provider factory.
- Keep `build_retrieval_plan(query)` deterministic unless Phase 2 explicitly adds a separate opt-in function such as `build_deepseek_retrieval_plan(...)` or `build_optional_deepseek_retrieval_plan(...)`; do not silently make existing callers require network/provider access.
- Construct prompts inside the source planner module, not in business workflow prompts. Prompts must list fixed enum values and allowed output fields and instruct the model not to answer the user query.
- Convert validated provider output into existing RetrievalPlan models; deterministic code must overwrite or repair authoritative fields such as `plan_id`, `original_query`, `round_policy`, `stop_conditions`, direct-keep buckets, domain strategies, fallback ladders, and allowed domains.
- Reuse `DeepSeekProviderClient.generate_json` where possible. Add provider/config code only if a narrow compatibility helper is required and covered by tests.
- Ensure all failure modes fall back to deterministic planning and record concise metadata notes without private reasoning or secrets.

Group3 validation instructions:
- `invest_code_quality_checker` must run the focused ruff, py_compile, focused pytest, and source regression commands listed above, then inspect `git diff --name-only` for forbidden-path drift.
- `invest_functional_validator` must validate actual planner outputs for at least missing-key fallback, valid mocked DeepSeek output, invalid JSON repair, invalid enum/schema fallback, refusal/direct-answer fallback, Q03 negative-domain preservation, direct-keep bucket preservation, and no-secret metadata.
- Optional live DeepSeek smoke must run only when the key is present in the current process; absence of a key is a recorded skip, not a blocker.
- Group3 must confirm `packages/agents/workflow.py`, `packages/sources/schemas.py`, protected evidence/API/task/content/delivery contracts, and broad profile files were not changed by Phase 2.

Gate result:
- Decision: proceed.
- Rationale: Phase 2 can be implemented as an optional source-layer DeepSeek planner adapter over the existing provider JSON boundary, with strict RetrievalPlan validation and deterministic fallback, without changing protected downstream contracts.
- Human-review stop remains required if implementation discovers that provider method signatures, config defaults, public source schemas, research workflow execution, API responses, evidence/citation contracts, task semantics, content metadata, or delivery behavior must change.

## Phased Roadmap

### Phase 0: Coverage Contract and RetrievalPlan Design

Objective:
- Freeze `CoverageLane`, `SourceIntent`, `DomainStrategy`, and `RetrievalPlan` contracts before production routing changes.

Allowed write scope:
- `.agent/PLANS/domestic-source-coverage-and-routing-v2.md`
- `.agent/STATUS.md`
- docs under `docs/`
- tests or fixtures only if the user explicitly starts implementation

Acceptance criteria:
- CoverageLane enum is fixed for v1 implementation.
- RetrievalPlan schema is explicit and validates planned planner/executor boundaries.
- Direct-keep boundaries are visible in the plan.
- Q03 regression expectation is recorded.
- No production code is changed during plan creation.

Validation:
- planning artifact existence check
- STATUS active-plan check
- plan-self-review placeholder and section scan

Next action:
- Run the Phase 1 Architecture Gate through `system_contract_architect`, then proceed to the scoped Phase 1 implementation only if the gate decision is `proceed`.

### Phase 1: Schema and Deterministic Fallback Planner

Objective:
- Implement typed contracts for CoverageLane, SourceIntent, DomainStrategy, RetrievalPlan, and deterministic fallback planning.

Likely write scope:
- `packages/sources/retrieval_plan.py`
- `packages/sources/query_decomposition.py`
- `tests/test_sources_retrieval_plan.py`
- `tests/test_sources_query_decomposition.py`

Acceptance criteria:
- Deterministic planner produces valid RetrievalPlan for representative queries.
- Direct-keep lanes use `direct_structured_only`.
- City/county queries include fallback ladder.
- Unknown supplemental themes do not receive all supplemental domains.

Validation:

```powershell
python -m ruff check packages\sources\retrieval_plan.py packages\sources\query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
python -m py_compile packages\sources\retrieval_plan.py packages\sources\query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
```

### Phase 2: DeepSeek Retrieval Planner Integration

Objective:
- Add an optional DeepSeek-backed planner that emits RetrievalPlan JSON under strict schema validation and deterministic fallback.

Allowed write scope:
- `packages/sources/retrieval_planner_deepseek.py`
- `tests/test_sources_retrieval_planner_deepseek.py`
- `tests/test_deepseek_provider.py` only for existing provider JSON/metadata behavior coverage
- `packages/providers/**` only if a narrow backward-compatible reusable helper is required
- `packages/core/config.py` only for backward-compatible planner-specific settings with safe defaults

Acceptance criteria:
- Missing `DEEPSEEK_API_KEY` falls back deterministically.
- Invalid DeepSeek output is repaired or refused without corrupting execution.
- Planner metadata records provider/model without secrets.
- No private reasoning content is stored.
- DeepSeek cannot invent lanes/source intents/domain strategies/domains or route direct-keep primary lanes into search-assisted execution.
- Existing `build_retrieval_plan(query)` deterministic behavior remains available without credentials/network.

Validation:

```powershell
python -m ruff check packages\sources\retrieval_planner_deepseek.py tests\test_sources_retrieval_planner_deepseek.py tests\test_deepseek_provider.py
python -m py_compile packages\sources\retrieval_planner_deepseek.py tests\test_sources_retrieval_planner_deepseek.py tests\test_deepseek_provider.py
pytest -q tests\test_sources_retrieval_planner_deepseek.py tests\test_deepseek_provider.py
pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
```

Optional live smoke:

```powershell
$env:DEEPSEEK_API_KEY="<set in current terminal only>"
$env:LLM_PROVIDER="deepseek"
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
pytest -q tests\test_sources_retrieval_planner_deepseek.py -m live
```

### Phase 3: Source Resolver and Compatibility Gate

Objective:
- Convert source intents into domains/adapters through deterministic source maps, and reject semantically incompatible candidates.

Affected contracts:
- Phase 3 may affect only source-layer execution planning, source intent resolution, search-assisted candidate decisions, and rejection metadata inside source-layer traces.
- Phase 3 must not change API response shapes, EvidenceBundle schema, EvidenceItem citation fields, `source_quality_summary`, research analyze response shape, task/job semantics, `run` / `run_steps`, content asset metadata, delivery state transitions, or provider abstraction semantics.
- RetrievalPlan remains a source-layer planning contract; compatibility outcomes must be represented through source-layer candidate decisions, metadata, or coverage gaps without promoting new public API contracts.

Allowed write scope:
- `packages/sources/source_resolver.py`
- `packages/sources/search_assisted_domestic.py`
- `packages/sources/query_decomposition.py`
- `tests/test_sources_source_resolver.py`
- focused additions to `tests/test_sources_search_assisted_domestic.py`
- focused additions to `tests/test_sources_query_decomposition.py`

Forbidden changes:
- `packages/sources/schemas.py`
- `packages/agents/workflow.py`
- `packages/providers/**`
- `packages/core/config.py`
- broad `packages/sources/profiles/**` or `packages/sources/packs.py` expansion
- weakening direct-keep guards for project transaction, enterprise disclosure, statistics/data, credit/GSXT, judicial, or disclosure-backed lanes
- changing protected API/evidence/research/task/content/delivery contracts

Compatibility gate design:
- Domain strategy enforcement: resolve domains/adapters from `CoverageLanePlan.domain_strategy`, `source_intents`, `allowed_domains`, and deterministic source maps; reject candidates whose domain is outside the lane strategy with reason codes such as `domain_topic_mismatch` or existing off-domain equivalents.
- Source-role compatibility: map domains/adapters to fixed source roles and reject role drift with `source_role_mismatch`; supplemental domains cannot satisfy official policy, statistics/data, project, or disclosure primary lanes.
- Region match: for lanes with `must_match_region=True`, require candidate domain metadata, title/snippet/content hints, or resolver metadata to match the lane region; parent fallback may be accepted only with fallback metadata and a coverage gap.
- Theme alias match: use `normalized_theme` and `theme_aliases` from RetrievalPlan to require topical evidence in title/snippet/content unless the lane is an explicitly broad national official policy lane.
- Negative-term rejection: reject candidates dominated by lane `negative_terms` before extraction; Q03 humanoid robotics must reject low-altitude, UAV, aviation, AOPA, and eVTOL leakage in policy/local/data lanes.
- Supplemental boundary: `industry_association_signal` and other supplemental domains may run only in supplemental lanes; reason `supplemental_used_in_primary_lane` is mandatory when a supplemental source appears in a primary lane.
- Direct-keep boundary: if a direct-structured lane is handed to Tavily/Crawl4AI as primary execution, return/record `direct_keep_boundary_violation` and stop that lane according to `stop_on_direct_keep_boundary_violation`.
- City/park parent fallback gap behavior: parent-level province/national evidence may be retained as fallback context only with `fallback_level`, `parent_evidence_only=True`, `local_claim_allowed=False`, and a coverage gap; do not claim city/county/park coverage from parent evidence.

Migration path from `QueryDecompositionTask` to RetrievalPlan lanes:
- Keep the existing query-decomposition and source-assisted path available as the compatibility path.
- Add a source-layer resolver that can consume `RetrievalPlan.coverage_lanes` and produce bounded execution inputs compatible with the existing search-assisted orchestrator.
- Bridge lane execution into existing `QueryDecompositionTask` only where needed by current adapters; preserve task IDs, execution buckets, source clusters, include/exclude domains, search phrases, exact phrases, and negative terms as source-layer metadata.
- Do not require callers of the current source-assisted path to pass RetrievalPlan yet; Phase 3 should allow tests to exercise resolver/gate behavior directly and through focused search-assisted candidate selection.
- Treat lane-to-task bridging as internal and reversible until Phase 7 integrates RetrievalPlan into research workflow.

Acceptance criteria:
- Local rollout no longer inherits supplemental domains.
- Q03 local rollout excludes low-altitude/aviation domains.
- Theme supplemental sources are theme-compatible.
- New rejection reasons are visible in candidate decisions.
- Direct-keep lanes remain protected.
- Unknown supplemental themes do not fan out to supplemental domains.
- Direct-keep tasks are preserved and refused/held before search-assisted execution when a boundary violation is detected.
- City/county and park fallback records parent fallback as a gap rather than local sufficiency.

Validation:

```powershell
python -m ruff check packages\sources\source_resolver.py packages\sources\search_assisted_domestic.py packages\sources\query_decomposition.py tests\test_sources_source_resolver.py tests\test_sources_search_assisted_domestic.py tests\test_sources_query_decomposition.py
python -m py_compile packages\sources\source_resolver.py packages\sources\search_assisted_domestic.py packages\sources\query_decomposition.py tests\test_sources_source_resolver.py tests\test_sources_search_assisted_domestic.py tests\test_sources_query_decomposition.py
pytest -q tests\test_sources_source_resolver.py tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_search_discovery.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

Required validation cases:
- Q03 negative-domain: humanoid robotics policy/local/data lanes reject low-altitude/aviation supplemental domains.
- Unknown supplemental no fanout: unknown themes resolve no supplemental domains unless explicitly mapped.
- Direct-keep preserved: direct structured lanes never enter Tavily/Crawl4AI primary execution.
- City/park fallback gap: parent fallback evidence is labeled as parent-only and does not satisfy exact local coverage.
- Candidate rejection reason codes: include `domain_topic_mismatch`, `region_mismatch`, `source_role_mismatch`, `supplemental_used_in_primary_lane`, `direct_keep_boundary_violation`, and `coverage_lane_not_supported` where applicable.

Group2 implementation instructions:
- `invest_agent_architecture_builder` / `system_contract_architect`: implement the smallest typed resolver surface in `packages/sources/source_resolver.py` if the existing modules cannot express lane-to-domain/adapters cleanly.
- `invest_feature_programmer` / `source_provider_integrator`: wire the resolver into search-assisted candidate selection without changing evidence/API contracts; keep candidate decisions auditable and bounded by the existing orchestrator response shape.
- Do not expand national/provincial/city profile coverage in Phase 3; source backbone expansion belongs to Phase 4.
- Do not edit `packages/sources/schemas.py`, `packages/agents/workflow.py`, providers, config, content, delivery, or task substrate.

Group3 validation instructions:
- `invest_code_quality_checker`: run focused ruff, py_compile, focused pytest, source regression, and domestic source regression commands listed above; record repo-wide ruff debt separately if it remains limited to historical `data/tmp` scripts.
- `invest_functional_validator`: inspect Q03, unknown supplemental, direct-keep, city/park fallback, and rejection-code behavior from actual test assertions and/or a small offline artifact; verify no protected contract or forbidden-path edits are required.
- If validation requires a protected contract change, stop and return `revise` or `block` rather than widening the implementation.

Architecture Gate decision:
- Decision: `proceed`.
- Rationale: the current implementation already isolates RetrievalPlan in `packages/sources/retrieval_plan.py` and keeps DeepSeek sanitized; Phase 3 can be implemented as source-layer resolver/gate logic using existing search-assisted response metadata without changing protected downstream contracts.

### Phase 4: National and Provincial Backbone Expansion

Objective:
- Build a more complete national/provincial source map for macro policy, local policy, statistics, industry department, science/technology, and commerce lanes.

Approved minimal expansion scope:
- National backbone first: State Council / gov.cn, NDRC, MIIT, MOST, MOFCOM, NBS, Customs, and MOF only where fiscal/subsidy policy terms require it.
- Provincial first wave: provinces/municipal-level parents already represented by frozen evals or existing profiles only: Guangdong, Jiangsu, Anhui, Zhejiang, Sichuan, Shanghai, plus normalization of existing Hubei, Shandong, Fujian, and Henan entries when tests already depend on them.
- For each first-wave province, map role metadata before broad profile creation: provincial government, provincial DRC, provincial industry/MIIT, provincial statistics, provincial science/technology, and provincial commerce/trade only when a trade/export query requires it.
- Missing role/domain mappings must produce an explicit coverage gap or fallback metadata; do not fabricate role coverage through generic or supplemental sources.
- Do not target all 31 province-level regions in Phase 4. Do not add new city/county maintained profiles in Phase 4.

Approved implementation write scope:
- `packages/sources/profiles/china_scaleout.py`
- `packages/sources/profiles/china_policy.py`
- `packages/sources/packs.py`
- `packages/sources/router.py`
- `packages/sources/retrieval_plan.py` only for narrow source-intent/fallback metadata already needed by national statistics/customs/commerce or provincial science/technology/commerce roles
- `packages/sources/source_resolver.py` only for narrow official-domain/source-role compatibility mappings needed by the new national/provincial domains
- focused tests under `tests/`

Forbidden implementation scope and contracts:
- Do not edit `packages/sources/schemas.py`, `packages/agents/workflow.py`, `packages/providers/**`, `packages/core/config.py`, protected evidence/API/research/task/content/delivery contracts, task/job semantics, `run` / `run_steps`, content asset metadata, or delivery state transitions.
- Do not weaken direct-keep lanes for project transaction, enterprise disclosure, structured data, credit/GSXT, judicial, or exchange disclosure paths.
- Do not add city/county/park profile builders, city/county source packs, or city/county strategy routing in Phase 4. Existing historical `city_park_pack_cn_v1` / `build_phase4_city_park_profiles` behavior may remain untouched, but it must not be expanded or used as the current Phase 4 work item.
- Do not add supplemental association/aviation/UAV domains to primary official policy, data, DRC, MIIT, statistics, science/technology, or commerce lanes.

Acceptance criteria:
- Province-level industry-policy query has official government, DRC, industry department, and statistics lane coverage where domain metadata exists.
- Coverage gap is explicit when a department domain is not mapped yet.
- No city/county full-profile explosion.
- `SRC-COV-04` has explicit commerce/trade/customs coverage through national customs/commerce and Jiangsu provincial commerce/trade metadata or a structured gap.
- Q03 humanoid robotics policy/local/data lanes still reject low-altitude/aviation supplemental domains such as `aopa.org.cn` and `china-uav.cn`.
- Unknown supplemental themes still resolve no supplemental domains and do not fan out to all known supplemental sources.
- Direct-keep project/disclosure/structured-data primary paths remain direct structured paths and are not routed through Tavily/Crawl4AI primary execution.

Validation:

```powershell
python -m ruff check packages\sources\profiles\china_scaleout.py packages\sources\profiles\china_policy.py packages\sources\packs.py packages\sources\router.py packages\sources\retrieval_plan.py packages\sources\source_resolver.py tests\test_sources_domestic_scaleout_phase3.py tests\test_sources_domestic_scaleout_phase4.py tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_retrieval_plan.py tests\test_sources_source_resolver.py tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py
python -m py_compile packages\sources\profiles\china_scaleout.py packages\sources\profiles\china_policy.py packages\sources\packs.py packages\sources\router.py packages\sources\retrieval_plan.py packages\sources\source_resolver.py tests\test_sources_domestic_scaleout_phase3.py tests\test_sources_domestic_scaleout_phase4.py tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_retrieval_plan.py tests\test_sources_source_resolver.py tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py
pytest -q tests\test_sources_domestic_scaleout_phase3.py tests\test_sources_domestic_scaleout_phase4.py tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py
pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_source_resolver.py tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
pytest -q tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

Required validation cases:
- Province policy/data coverage: Guangdong/Jiangsu/Anhui/Zhejiang/Sichuan/Shanghai first-wave role mapping is present where domain metadata exists, and missing roles emit explicit gap/fallback metadata.
- `SRC-COV-04`: Jiangsu photovoltaic overseas/trade-risk query includes national customs/commerce and provincial commerce/trade handling, or a structured gap if a role is not mapped.
- Q03 regression: Guangdong humanoid robotics policy/local/data lanes reject low-altitude/aviation supplemental domains.
- Unknown supplemental: unknown theme produces no supplemental-domain fanout.
- Direct-keep preservation: project transaction, enterprise disclosure, and structured-data primary lanes do not enter Tavily/Crawl4AI primary execution.
- City/county containment: no new maintained city/county profile or pack is introduced; city/county gaps/fallbacks remain Phase 5.

Group2 implementation assignment:
- `invest_agent_architecture_builder` / `system_contract_architect`: keep Phase 4 role/domain taxonomy constrained to the source-layer national/provincial backbone and confirm no protected downstream contract is needed.
- `invest_feature_programmer` / `source_provider_integrator`: implement only the approved source-map, pack/router, and focused-test changes; normalize legacy phase labels only when required for clarity and without deleting existing behavior.
- Optional `eval_harness_implementer`: add a small offline Phase 4 coverage probe only if focused tests cannot express province/data/trade coverage gaps cleanly.

Group3 validation assignment:
- `invest_code_quality_checker`: run focused ruff, py_compile, focused router/profile/retrieval/resolver pytest, source regression, and domestic source regression commands above; record repo-wide ruff debt separately if it remains limited to historical `data/tmp` scripts.
- `invest_functional_validator`: verify province policy/data coverage, `SRC-COV-04`, Q03 negative-domain rejection, unknown supplemental non-fanout, direct-keep preservation, and city/county containment from actual tests and/or a small offline artifact.

Architecture Gate decision:
- Decision: `proceed`.
- Rationale: Phase 4 can improve national/provincial backbone coverage using existing source profile, pack, router, RetrievalPlan, and resolver boundaries without changing protected evidence/API/research/task/content/delivery contracts. The implementation must stay national/provincial and must not become city/county one-profile-per-city expansion.

### Phase 5: City/County Fallback Discovery

Objective:
- Implement city/county/park fallback ladder with official-domain-first discovery and transparent parent-region fallback.

Director gate result:
- Decision: proceed to Phase 5 Architecture Gate.
- Rationale: Phase 4 final validation passed after remediation, the Phase 4 source-map is frozen, and Phase 5 can be designed inside the source-layer fallback/resolver/search-assisted boundaries without changing protected evidence/API/research/provider/task/content/delivery contracts.
- Architecture Gate must decide the exact implementation scope before production code changes. This director gate does not authorize implementation yet.

Architecture Gate decision:
- Decision: `proceed`.
- Classification: primary `source_layer`; secondary `domestic_source_collectors` and `eval_policy_ops`.
- Rationale: existing source-layer contracts are sufficient for Phase 5. `RetrievalPlan.coverage_gaps[]` already carries `fallback_level`, `fallback_source`, `parent_evidence_only`, and `local_claim_allowed`; `CoverageLanePlan.success_criteria` already carries `require_exact_local_match`, `allow_parent_fallback`, and `parent_fallback_requires_gap`; `DomainStrategy.FALLBACK_LADDER_OFFICIAL_FIRST` already represents official-first local fallback; `DomesticSearchAssistedResponse.metadata` can carry source-layer execution summaries without response-shape drift. No production code was changed by this gate.
- Protected-contract decision: preserve EvidenceBundle schema, EvidenceItem citation fields, `source_quality_summary` shape, research analyze response shape, provider abstraction semantics, source routing response shape, task/job semantics, `run` / `run_steps`, content asset metadata, and delivery transitions. If implementation needs any of these, the decision changes to `revise` and Phase 5 stops.
- Provider/config decision: no provider or config edits are approved. Tavily/Crawl4AI behavior must be bounded only through existing source-layer execution code and existing RetrievalPlan `round_policy`; if a provider/config edit becomes necessary, return to Architecture Gate with `revise`.

Fallback-level metadata semantics approved for Phase 5:
- Use existing source-layer contracts only. Do not add fields to EvidenceBundle, EvidenceItem citation, API response, research response, provider response, source routing response, task/job state, or delivery/content models.
- Authoritative fallback metadata lives in `RetrievalPlan.coverage_gaps[]` using:
  - `fallback_level`: one of `exact_local`, `city`, `province`, `national`, `exact_local_required`, or `unsupported`.
  - `fallback_source`: the source intent, ladder step, or accepted parent domain/source identifier that produced the fallback context.
  - `parent_evidence_only`: `true` whenever accepted evidence is above the requested local granularity.
  - `local_claim_allowed`: `true` only for exact local/park/county/city official evidence that matches the requested local region; `false` for province/national/context-only evidence.
  - `notes`: short audit notes such as `parent evidence must not masquerade as city/county/park coverage`.
- Execution metadata may additionally be recorded in `DomesticSearchAssistedResponse.metadata` under source-layer-only keys such as `fallback_ladder_attempted`, `accepted_fallback_level`, `exact_local_found`, `parent_evidence_only`, `local_claim_allowed`, `round_policy_enforced`, and `budget_exhausted`. These keys must remain internal execution metadata and must not require downstream response-shape changes.
- Candidate-level labels should use existing reason-code fields where possible. Approved reason codes include `accepted_exact_local_official`, `accepted_city_official`, `accepted_parent_province_fallback`, `accepted_parent_national_fallback`, `rejected_parent_fallback_for_exact_local_claim`, `local_official_not_discovered`, `fallback_budget_exhausted`, and existing compatibility rejection codes.
- Exact local labeling rules:
  - `exact_local`: accepted domain/source is the requested county, district, park, zone, or city official site and title/snippet/content matches the requested region and theme. `parent_evidence_only=false`; `local_claim_allowed=true`.
  - `city`: requested county/district/park evidence was not found, but the parent city official portal or city department evidence was accepted. `parent_evidence_only=true`; `local_claim_allowed=false` for the requested county/district/park claim.
  - `province`: requested city/county/park evidence was not found, but provincial government/DRC/industry/science/statistics/commerce evidence was accepted. `parent_evidence_only=true`; `local_claim_allowed=false`.
  - `national`: only national official policy/data/project context was accepted. `parent_evidence_only=true`; `local_claim_allowed=false`.
  - `exact_local_required`: no acceptable local evidence has been accepted yet for a required local lane; this is the initial or unresolved gap state.
  - `unsupported`: no compatible official source or safe parent fallback can be represented within the current source-layer contracts.

Direct-keep preservation rules approved for Phase 5:
- `project_transaction`: primary execution remains `direct_structured_sources` against public-resource trading, government procurement, and project approval/DRC structured paths. Tavily/Crawl4AI may only discover official context or supplemental entry pages after the direct lane is preserved; it must not satisfy the primary project lane.
- `enterprise_disclosure`: primary execution remains exchange/disclosure/IR direct paths. Tavily/Crawl4AI may only supplement non-primary context and must not replace CNINFO/SSE/SZSE/BSE/NEEQ-style disclosure lanes.
- `structured data` / `data_metrics`: primary execution remains structured statistics/customs/commerce/official data paths. Association/media pages cannot satisfy the data lane.
- `credit/GSXT`: remains direct/manual structured handling. Search-assisted execution must refuse primary routing and emit direct-keep/unsupported metadata rather than fabricating evidence.
- `judicial`: remains direct/manual structured handling. Search-assisted execution must refuse primary routing and emit direct-keep/unsupported metadata rather than fabricating evidence.
- `exchange disclosure`: remains direct disclosure backbone. Any listed-company or exchange disclosure request must keep `execution_bucket=direct_structured_sources`; search-assisted discovery is not a primary substitute.
- Boundary violation behavior: any direct-keep lane routed to Tavily/Crawl4AI primary execution must stop the task with `direct_keep_boundary_violation` and trigger Phase 5 remediation before completion.

Bounded Tavily/Crawl4AI behavior approved for Phase 5:
- Use existing `RetrievalPlan.round_policy` as the sole budget contract: `max_rounds`, `max_search_phrases_per_lane`, `max_candidates_per_lane`, `max_extractions_per_lane`, and `max_estimated_tavily_credits`.
- Round 1 attempts exact local official or park/zone official discovery first for `city_county_fallback` and `park_zone_signal`.
- Round 2 may target only unresolved required local gaps and may escalate to parent city/province official domains.
- Round 3 may add national official context only when local and province attempts fail or are insufficient; it must set parent fallback/gap metadata.
- Crawl4AI extraction count must not exceed `max_extractions_per_lane`; Tavily candidate acceptance must not exceed `max_candidates_per_lane`; search phrases must not exceed `max_search_phrases_per_lane`.
- Provider failure, absent `TAVILY_API_KEY`, budget exhaustion, or no compatible candidate must produce structured partial failure or coverage gap metadata. Mandatory validation must not require live Tavily/DeepSeek credentials.

Approved Architecture Gate scope:
- Define city/county/park fallback discovery semantics for `city_county_fallback` and `park_zone_signal` lanes.
- Define how official-domain-first discovery is represented in source-layer candidate decisions, fallback metadata, and coverage gaps without adding one maintained profile per city/county/park.
- Define parent fallback labeling so province/national evidence can support context but cannot satisfy exact city/county/park coverage.
- Define Tavily/Crawl4AI budget behavior for Phase 5 using existing RetrievalPlan round policy fields; no provider/config edits are authorized by this gate.
- Preserve direct-keep primary paths for project transaction, enterprise disclosure, structured data, credit/GSXT, judicial, and exchange disclosure lanes.

Approved implementation write scope after the Architecture Gate:
- `packages/sources/source_resolver.py`
- `packages/sources/search_assisted_domestic.py`
- `packages/sources/query_decomposition.py` only for source-layer local/county/district/park task classification, fallback phrases, or direct-keep regression repair
- `packages/sources/retrieval_plan.py` only for deterministic fallback-ladder construction, coverage-gap population, and tests that use existing fields; do not add new public model fields unless this gate is revised
- `tests/test_sources_city_county_fallback.py`
- focused additions to `tests/test_sources_search_assisted_domestic.py`, `tests/test_sources_source_resolver.py`, and `tests/test_sources_retrieval_plan.py`
- optional offline eval script `data/tmp/_phase5_city_county_fallback_eval.py` only if tests cannot express the real-world fallback/gap probes cleanly

Forbidden Phase 5 implementation write scope:
- `packages/sources/schemas.py`
- `packages/agents/workflow.py`
- `packages/providers/**`
- `packages/core/config.py`
- `packages/tasks/**`
- `packages/content/**`
- `packages/delivery/**`
- broad `packages/sources/profiles/**`, `packages/sources/packs.py`, or `packages/sources/router.py` expansion for city/county/park coverage
- any schema, citation, evidence, source-routing response, provider, task/job, run-log, content, or delivery contract change

Forbidden implementation scope and contracts:
- Do not edit `packages/sources/schemas.py`, `packages/agents/workflow.py`, `packages/providers/**`, `packages/core/config.py`, protected evidence/API/research/task/content/delivery contracts, task/job semantics, `run` / `run_steps`, content asset metadata, or delivery state transitions.
- Do not add maintained city/county/park profile builders, city/county packs, or broad city/county source-map expansion. Dynamic discovery and parent fallback metadata are allowed; one-profile-per-city expansion is not.
- Do not weaken direct-keep lanes or route their primary execution through Tavily/Crawl4AI.
- Do not broaden supplemental domains into official policy/data/project lanes, and do not reintroduce Q03-style low-altitude/aviation leakage for humanoid robotics lanes.
- Do not require live Tavily credentials for mandatory acceptance; live status may be recorded when a key is present in the current process.

Acceptance criteria:
- Exact city/county/park official-domain discovery is attempted before parent fallback.
- City/county source absence is represented as coverage gap, not fabricated coverage.
- Parent fallback evidence is labeled with fallback level.
- Parent province/national evidence does not mark exact city/county/park coverage as sufficient.
- Direct-keep lanes remain direct structured primary paths and do not enter Tavily/Crawl4AI primary execution.
- Q03 negative-domain and unknown supplemental-theme non-fanout behavior remains intact.
- Tavily usage is bounded by round policy and per-lane candidate/extraction budgets.

Real-world validation plan:
- Offline official-domain-first ladder probes:
  - `SRC-COV-05` Shenzhen low-altitude policy/tender query attempts city official fallback before province/national fallback, preserves direct `project_transaction` primary path, and records a gap if exact local official evidence is missing.
  - `SRC-COV-07` Chengdu AI industrial park query attempts park/zone official discovery, then city official discovery, then Sichuan/province fallback; parent evidence is labeled `fallback_level=province` or equivalent and does not satisfy exact park coverage.
  - A county/district-style query such as "Suzhou Industrial Park photovoltaic project policy" or equivalent fixture attempts exact park/district official discovery before Suzhou/Jiangsu parent fallback.
- Official-domain-first ladder assertions:
  - accepted candidates for city/county/park primary lanes must be official local domains or whitelisted official park/zone domains;
  - parent province/national domains may be accepted only as fallback/context evidence with explicit fallback level;
  - media, association, and supplemental domains cannot satisfy `city_county_fallback` or project primary lanes.
- Coverage-gap transparency assertions:
  - missing exact city/county/park official evidence emits a structured gap containing requested region, attempted fallback level, and reason;
  - parent-level evidence remains visible but is labeled as parent evidence rather than local evidence.
- Direct-keep preservation assertions:
  - project transaction, enterprise disclosure, structured data, credit/GSXT, judicial, and exchange disclosure primary lanes do not call Tavily/Crawl4AI as primary execution;
  - Phase 5 may use Tavily only for official-domain discovery or supplemental/context lanes allowed by the plan.
- Bounded Tavily assertions:
  - no Phase 5 offline test requires `TAVILY_API_KEY`;
  - mocked/live Tavily paths enforce existing `round_policy.max_search_phrases_per_lane`, `max_candidates_per_lane`, `max_extractions_per_lane`, and estimated credit budget;
  - provider failure or exhausted budget produces structured partial failure/gap metadata, not fabricated coverage.
- Regression assertions:
  - Q03 humanoid robotics lanes still reject `aopa.org.cn` and `china-uav.cn`;
  - unknown supplemental themes still do not fan out to all supplemental domains;
  - Phase 4 national/provincial backbone behavior remains unchanged except for compatibility bug fixes explicitly recorded in this PLAN.

Validation:

```powershell
python -m ruff check packages\sources\source_resolver.py packages\sources\search_assisted_domestic.py packages\sources\query_decomposition.py packages\sources\retrieval_plan.py tests\test_sources_city_county_fallback.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
python -m py_compile packages\sources\source_resolver.py packages\sources\search_assisted_domestic.py packages\sources\query_decomposition.py packages\sources\retrieval_plan.py tests\test_sources_city_county_fallback.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
pytest -q tests\test_sources_city_county_fallback.py tests\test_sources_search_assisted_domestic.py
pytest -q tests\test_sources_source_resolver.py tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

Required functional probes:
- `SRC-COV-05`: Shenzhen low-altitude policy/tender query produces `city_county_fallback` plus direct `project_transaction`; exact Shenzhen official discovery is attempted before Guangdong/national fallback; project lane remains direct; missing exact local official evidence creates a gap with `fallback_level=exact_local_required` or parent fallback metadata.
- `SRC-COV-07`: Chengdu AI industrial park query attempts park/zone official discovery first, then Chengdu city official, then Sichuan/province official, then national context; parent evidence uses `fallback_level=city|province|national`, `parent_evidence_only=true`, and `local_claim_allowed=false`.
- County/district fixture: Suzhou Industrial Park or comparable district/park query attempts exact park/district official discovery before Suzhou/Jiangsu parent fallback and does not add a maintained city/county profile or pack.
- Q03 regression: Guangdong humanoid robotics policy/local/data lanes still reject `aopa.org.cn` and `china-uav.cn`, and low-altitude/aviation supplemental domains do not enter official policy/data/project lanes.
- Unknown supplemental non-fanout: unknown association/white-paper supplemental query does not fan out to all supplemental domains and does not satisfy official policy/data lanes.
- Direct-keep boundaries: project transaction, enterprise disclosure, structured data/data metrics, credit/GSXT, judicial, and exchange disclosure lanes stay `direct_structured_sources`; any attempted search-assisted primary execution emits `direct_keep_boundary_violation`.
- Bounded Tavily/Crawl4AI: mocked search/extraction proves `round_policy` limits are enforced for search phrases, candidates, extractions, and estimated credit budget; provider failure or absent key yields structured partial failure/gap metadata.

Optional live smoke, only when `TAVILY_API_KEY` exists in the current process:

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
python data\tmp\_phase5_city_county_fallback_eval.py --mode live --print-json
```

Group2 assignment:
- `invest_agent_architecture_builder` / `system_contract_architect`: run the Phase 5 Architecture Gate first. Own `.agent/PLANS/domestic-source-coverage-and-routing-v2.md` and `.agent/STATUS.md` for the gate decision; production code remains off-limits during the gate. Required output: `Decision: proceed | revise | block`, exact implementation write scope, protected-contract impact, fallback-level metadata decision, and stop conditions.
- `invest_feature_programmer` / `source_provider_integrator`: after a `proceed` Architecture Gate only, implement the smallest Phase 5 source-layer changes in the approved modules and focused tests. Preserve Phase 4 backbone behavior, direct-keep boundaries, official-domain-first fallback, and bounded Tavily usage.
- Optional `eval_harness_implementer`: add an offline JSON-printable Phase 5 eval script under `data/tmp/` only if tests cannot express the real-world fallback/gap probes cleanly. It must not require live credentials.

Group3 validation assignment:
- `invest_code_quality_checker`: run focused ruff, py_compile, focused pytest, source regression, domestic source regression, and forbidden-path scope review. Record repo-wide ruff debt separately if it remains limited to historical `data/tmp` scripts.
- `invest_functional_validator`: validate actual fallback decisions and/or eval artifact for official-domain-first ladder behavior, parent-level evidence labeling, coverage-gap transparency, direct-keep preservation, Q03 negative-domain regression, unknown supplemental non-fanout, and bounded Tavily behavior.

Phase 5 blockers requiring human input or a revised Architecture Gate:
- Any protected contract change: EvidenceBundle, EvidenceItem citation fields, `source_quality_summary`, research analyze response, source routing response shape, provider abstraction semantics, task/job semantics, `run` / `run_steps`, content asset metadata, or delivery state transitions.
- Any provider/config edit or requirement that live Tavily/DeepSeek credentials become mandatory for acceptance.
- Any direct-keep weakening or primary Tavily/Crawl4AI routing for direct structured lanes.
- Any broad maintained city/county/park profile expansion or source-pack expansion.
- Any inability to represent parent fallback evidence and exact local coverage gaps within existing source-layer metadata without downstream response-shape drift.
- Any need to edit Phase 4 national/provincial backbone source-map files beyond a narrowly documented compatibility bug.
- Any validation failure where the safe repair path would require protected-contract drift, provider/config changes, or one-profile-per-city expansion.

Phase 5 rollback:
- Revert or disable only the Phase 5 source-layer implementation files from the approved scope; do not revert Phase 4 backbone files or unrelated dirty worktree changes.
- Keep deterministic RetrievalPlan fallback and current search-assisted domestic behavior as the safe baseline.
- If local fallback metadata proves insufficient, stop with `revise` and keep parent fallback represented as unresolved `coverage_gaps` rather than widening downstream response contracts.
- If live Tavily/Crawl4AI behavior is unstable, keep offline/mocked validation authoritative and record live status as skipped or partial failure.

### Phase 6: Multi-Round Search and Coverage Sufficiency Judge

Objective:
- Execute search rounds based on RetrievalPlan gaps and stop conditions.

Director gate result:
- Decision: proceed to Phase 6 Architecture Gate, not implementation yet.
- Rationale: Phase 5 final validation passed, and the existing source-layer `RetrievalPlan.round_policy`, lane `success_criteria`, source resolver decisions, and `coverage_gaps[]` appear sufficient to design bounded multi-round search and coverage sufficiency judging as internal source-layer behavior. The Architecture Gate must still confirm that no protected response-shape, provider/config, research workflow, or direct-keep contract change is required.
- Current state: `active_phase6_architecture_gate_assigned`.
- Production code was not changed by this director gate.

Architecture Gate questions:
- Can Phase 6 keep coverage sufficiency judging inside source-layer execution metadata and `RetrievalPlan.coverage_gaps[]` without changing EvidenceBundle, EvidenceItem citation fields, `source_quality_summary`, research analyze response shape, source routing response shape, task/job semantics, `run` / `run_steps`, content asset metadata, or delivery state transitions?
- Can per-round traces remain internal source-layer metadata or test/eval artifacts until Phase 7, rather than becoming a public research workflow response surface?
- Can Tavily/Crawl4AI usage be bounded entirely through existing `round_policy` and source-layer orchestration without provider/config edits or mandatory live credentials?
- Can direct-keep lanes remain direct structured primary paths, with search-assisted rounds limited to allowed official/context discovery only?

Architecture Gate result:
- Decision: `proceed`.
- Classification: primary `source_layer`; secondary `domestic_source_collectors` and `eval_policy_ops`.
- Gate write scope: `.agent/PLANS/domestic-source-coverage-and-routing-v2.md` and `.agent/STATUS.md` only. Production code was not changed by this gate.
- Rationale: existing source-layer objects are sufficient for Phase 6. `RetrievalPlan.round_policy`, `RetrievalPlan.stop_conditions`, `CoverageLanePlan.success_criteria`, `CoverageGap`, `CandidateCompatibilityDecision.reason_code`, and `DomesticSearchAssistedResponse.metadata` can carry multi-round execution, coverage sufficiency, budget, fallback, and gap state without changing protected downstream contracts.
- Current boundary: Phase 6 remains an internal source-layer execution/judge layer. It may enrich source-layer metadata and test/eval artifacts, but it must not expose new public research workflow response fields or alter source routing response shape.
- Proposed boundary: implement a deterministic coverage sufficiency judge plus bounded multi-round orchestration wrapper that consumes `RetrievalPlan` lanes and existing search-assisted task behavior, then writes lane status, round trace, budget state, and unresolved gaps into source-layer objects/artifacts.

Approved Phase 6 implementation write scope:
- `packages/sources/search_assisted_domestic.py`
- `packages/sources/retrieval_plan.py`
- `packages/sources/coverage_judge.py`
- `packages/sources/source_resolver.py` only for narrow compatibility metadata needed by the judge
- `tests/test_sources_coverage_judge.py`
- focused additions to `tests/test_sources_search_assisted_domestic.py`
- focused additions to `tests/test_sources_retrieval_plan.py`
- focused additions to `tests/test_sources_source_resolver.py`
- focused additions to `tests/test_sources_city_county_fallback.py`
- focused additions to `tests/test_sources_query_decomposition.py`
- optional offline eval script `data/tmp/_phase6_multi_round_coverage_eval.py` only if focused tests cannot express required-lane gap closure, budget exhaustion, and per-round trace artifacts cleanly

Forbidden Phase 6 implementation write scope:
- `packages/sources/schemas.py`
- `packages/agents/workflow.py`
- `packages/providers/**`
- `packages/core/config.py`
- `packages/tasks/**`
- `packages/content/**`
- `packages/delivery/**`
- broad `packages/sources/profiles/**`, `packages/sources/packs.py`, or `packages/sources/router.py` expansion
- any protected evidence/API/research/source-routing/provider/task/content/delivery contract change
- any direct-keep weakening or primary Tavily/Crawl4AI routing for direct structured lanes

Phase 6 source-layer contracts:
- Multi-round execution consumes `RetrievalPlan.coverage_lanes`, `round_policy`, `stop_conditions`, and existing `QueryDecompositionTask` / `DomesticSearchAssistedResponse` behavior. It must not require a new API request/response schema.
- Coverage sufficiency is evaluated per `CoverageLanePlan` using `success_criteria`, accepted candidate/document counts, resolver reason codes, direct-keep state, fallback metadata, and extraction status.
- `CoverageGap` remains the durable source-layer gap contract. Phase 6 may add gap entries with reason codes such as `insufficient_accepted_documents`, `no_compatible_sources`, `budget_exhausted_search_phrases`, `budget_exhausted_candidates`, `budget_exhausted_extractions`, `budget_exhausted_tavily_credits`, `round_limit_reached`, `direct_keep_unavailable`, `parent_fallback_only`, and `provider_partial_failure`. Existing `fallback_level`, `fallback_source`, `parent_evidence_only`, `local_claim_allowed`, and `notes` carry fallback/gap detail.
- `DomesticSearchAssistedResponse.metadata` may carry internal source-layer trace dictionaries, including `coverage_trace`, `round_traces`, `budget_state`, `lane_status`, `gap_closure`, and `stop_reason`. These metadata keys are not a protected public research response surface in Phase 6 and must not contain secrets or private reasoning.
- `CandidateCompatibilityDecision.reason_code` remains the compatibility gate signal for accepted/rejected candidates. Phase 6 may consume existing reason codes and add narrow source-layer reason metadata only if tests require it; it must not weaken existing rejection semantics.

Per-round trace metadata semantics:
- Each round trace records `round_index`, `round_kind`, `triggered_by_lane_ids`, `triggered_by_gap_reason_codes`, `required_lane_only`, `search_phrases_attempted`, `include_domains`, `exclude_domains`, `candidate_count`, `accepted_candidate_count`, `rejected_candidate_count`, `extraction_attempt_count`, `extraction_success_count`, `estimated_tavily_credits_spent`, `budget_remaining`, `provider_statuses`, `closed_gap_reason_codes`, `opened_gap_reason_codes`, and `stop_reason`.
- Round 0 is plan construction and is not counted against `round_policy.max_rounds`; execution rounds are Round 1 through Round 3, bounded by `round_policy.max_rounds`.
- Round 1 attempts required official/direct lanes first. Round 2 may target only insufficient required lanes. Round 3 may add bounded supplemental/fallback context only after required-lane status is known and cannot satisfy required official/data/project/direct lanes with incompatible evidence.
- Trace metadata must be deterministic and auditable. It must not store provider credentials, raw private prompts, private chain-of-thought, or unbounded full-page content.

Coverage sufficiency criteria:
- A lane is `sufficient` only when it has been attempted and accepted evidence meets `success_criteria.min_accepted_documents`, source role compatibility, domain strategy, theme/alias match when required, region match when required, negative-term rejection, duplicate/search-page/login/attachment filtering, and lane-specific direct/fallback constraints.
- A required lane with zero compatible candidates, failed extraction, budget exhaustion, parent-only fallback, or direct-keep unavailability is `insufficient` and must emit a `CoverageGap`.
- A city/county/park lane with only parent city/province/national evidence remains `parent_evidence_only=true` and `local_claim_allowed=false`; it may support context but cannot satisfy exact local coverage.
- Direct-keep lanes are sufficient only through direct structured execution or explicit compatible direct evidence. Search-assisted discovery may add context but cannot mark project transaction, enterprise disclosure, structured data/data metrics, credit/GSXT, judicial, or exchange disclosure primary lanes sufficient.
- Optional/supplemental lanes may improve context but cannot close a required official/data/project/direct gap unless the lane contract explicitly allows that source role and domain strategy.

Budget enforcement and exhaustion semantics:
- Before each search phrase, candidate selection, and extraction, the orchestrator must check `round_policy.max_search_phrases_per_lane`, `max_candidates_per_lane`, `max_extractions_per_lane`, `max_estimated_tavily_credits`, and `max_rounds`.
- The estimated Tavily credit counter is a source-layer budget guard and must work in mocked/offline tests without live Tavily credentials.
- When a budget limit is reached, Phase 6 stops the affected lane or run according to `stop_conditions` and emits a structured `CoverageGap` plus response metadata. It must not silently skip the gap or fabricate sufficiency.
- Provider failure is treated as partial failure or gap metadata unless deterministic source-layer evidence already satisfied the lane.

Domain-widening controls:
- Round 1 may use only lane-compatible domains/adapters from `domain_strategy`, `allowed_domains`, source intents, and existing resolver gates.
- Round 2 may expand phrases or fallback levels only inside the same required lane, source role, region, fallback ladder, and negative-term boundary.
- Round 3 may add bounded supplemental/fallback context but must not add supplemental domains to primary official policy/data/project/direct lanes.
- Unknown supplemental themes must not fan out to all supplemental domains.
- Parent region fallback must stay labeled and cannot become exact local sufficiency.

Acceptance criteria:
- Round 2/3 only run for insufficient required lanes.
- Credit budget and candidate budget are enforced.
- Coverage gaps are structured and traceable.
- Search does not widen into incompatible domains.
- A sufficient lane must satisfy its lane `success_criteria`: minimum accepted documents, required region match, required theme match, required source role, exact-local constraints, parent-fallback constraints, and direct-keep constraints.
- Required-lane gaps may trigger targeted additional rounds; optional or supplemental lanes must not cause broad domain widening or satisfy required official/data/project lanes.
- Direct-keep lanes remain sufficient only through direct structured execution or explicit direct-keep unavailable/gap metadata; generic search cannot mark them sufficient.
- City/county/park parent fallback remains visible as parent evidence and must not become exact local sufficiency.

Validation:

```powershell
python -m ruff check packages\sources\coverage_judge.py packages\sources\search_assisted_domestic.py packages\sources\retrieval_plan.py packages\sources\source_resolver.py tests\test_sources_coverage_judge.py tests\test_sources_search_assisted_domestic.py tests\test_sources_retrieval_plan.py tests\test_sources_source_resolver.py tests\test_sources_city_county_fallback.py tests\test_sources_query_decomposition.py
python -m py_compile packages\sources\coverage_judge.py packages\sources\search_assisted_domestic.py packages\sources\retrieval_plan.py packages\sources\source_resolver.py tests\test_sources_coverage_judge.py tests\test_sources_search_assisted_domestic.py tests\test_sources_retrieval_plan.py tests\test_sources_source_resolver.py tests\test_sources_city_county_fallback.py tests\test_sources_query_decomposition.py
pytest -q tests\test_sources_coverage_judge.py tests\test_sources_search_assisted_domestic.py tests\test_sources_retrieval_plan.py tests\test_sources_source_resolver.py tests\test_sources_city_county_fallback.py tests\test_sources_query_decomposition.py
pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_search_assisted_domestic.py tests\test_sources_search_discovery.py tests\test_sources_crawl4ai_extraction.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

Real-world validation plan:
- Multi-round search orchestration:
  - Offline mocked search/extraction must prove Round 1 stops when all required lanes are sufficient.
  - Round 2 may run only for insufficient required lanes and must use targeted gap phrases/domains derived from the lane and fallback ladder.
  - Round 3 may run only as bounded supplemental/fallback context; it cannot broaden required official/data/project lanes into incompatible domains.
  - No round may exceed `round_policy.max_rounds`, and no lane may exceed phrase, candidate, extraction, or estimated Tavily credit limits.
- Coverage sufficiency judging:
  - Judge output must be inspectable in source-layer objects or eval artifacts with per-lane attempted/sufficient status, accepted document count, rejection/gap reasons, fallback level, and budget state.
  - Sufficiency requires lane-compatible source role, domain strategy, region match when required, theme/alias match when required, negative-term rejection, attachment/search-page/login/duplicate filtering, and lane-specific success criteria.
  - Parent fallback evidence for city/county/park lanes must remain `parent_evidence_only=true` or equivalent and must keep `local_claim_allowed=false`; it cannot mark exact local coverage as sufficient.
- Budget enforcement:
  - Mocked Tavily and Crawl4AI paths must count search phrases, candidates, extractions, rounds, provider failures, and estimated Tavily credits.
  - Budget exhaustion must emit a structured coverage gap or partial-failure metadata; it must not fabricate sufficiency.
  - Mandatory validation must pass without `TAVILY_API_KEY` or `DEEPSEEK_API_KEY`; live smoke is optional and records skipped/partial status when credentials are absent.
- Required-lane gap closure:
  - `SRC-COV-01` requires national policy, provincial rollout, project transaction, and data/statistics attempts; insufficient official/data lanes may trigger targeted rounds, but low-altitude/aviation supplemental domains remain rejected.
  - `SRC-COV-04` must preserve customs/commerce/trade/data gap closure for Jiangsu photovoltaic export/trade-risk coverage without widening into unrelated provinces or supplemental-only domains.
  - `SRC-COV-09` must not allow association/media evidence to satisfy the required statistics/data lane.
- Direct-keep preservation:
  - `SRC-COV-05` and direct project-transaction lanes must keep project execution direct structured primary; search rounds may only discover official/context pages and cannot satisfy the direct project lane.
  - `SRC-COV-06` and `SRC-COV-08` must keep enterprise disclosure/exchange disclosure direct structured primary and cannot mark generic web search as sufficient.
  - Credit/GSXT, judicial, structured data, and exchange disclosure controls must emit direct-keep unavailable/gap metadata instead of search-assisted sufficiency when direct execution is unavailable.
- Q03 regression and domain widening controls:
  - Q03 Guangdong humanoid robotics policy/local/data lanes must still reject `aopa.org.cn`, `china-uav.cn`, low-altitude, UAV, and aviation supplemental domains.
  - Unknown supplemental themes must not fan out to all supplemental domains.
  - No incompatible national/provincial/city/county domain widening is allowed merely because an earlier round was insufficient.
- City/county fallback preservation:
  - Phase 5 `SRC-COV-05`, `SRC-COV-07`, and Suzhou Industrial Park fixture behavior must remain intact.
  - Exact local discovery must be attempted before parent fallback, parent fallback must be labeled, and no maintained city/county/park profile or pack expansion is allowed.

Group2 assignment:
- `invest_agent_architecture_builder` / `system_contract_architect`: run the Phase 6 Architecture Gate first. Own only `.agent/PLANS/domestic-source-coverage-and-routing-v2.md` and `.agent/STATUS.md` during the gate. Required output: `Decision: proceed | revise | block`, exact source-layer implementation write scope, sufficiency-judge boundary, per-round trace boundary, protected-contract impact, rollback/fallback plan, and stop conditions.
- `invest_feature_programmer` / `source_provider_integrator`: after a `proceed` Architecture Gate only, implement the smallest source-layer multi-round orchestration and coverage judge changes in approved modules and focused tests. Preserve Phase 5 fallback behavior, Q03 negative-domain controls, direct-keep boundaries, and budget enforcement.
- Optional `eval_harness_implementer`: add an offline JSON-printable Phase 6 eval helper under `data/tmp/` only if focused tests cannot express required-lane gap closure, budget exhaustion, and per-round sufficiency traces. It must not require live credentials or persist secrets.

Group3 validation assignment:
- `invest_code_quality_checker`: run focused ruff, py_compile, focused pytest, source regression, domestic source regression, and forbidden-path scope review. Record repo-wide ruff debt separately if it remains limited to historical `data/tmp` scripts.
- `invest_functional_validator`: design and execute practical offline cases for multi-round stop/continue behavior, coverage sufficiency, required-lane gap closure, budget exhaustion, Q03 negative-domain regression, direct-keep preservation, city/county fallback preservation, and no incompatible domain widening. Group 3 owns final case design and must inspect actual judge/orchestration artifacts, not only worker summaries.

Phase 6 blockers requiring human input or a revised Architecture Gate:
- Any protected contract change: EvidenceBundle, EvidenceItem citation fields, `source_quality_summary`, research analyze response, source routing response shape, provider abstraction semantics, task/job semantics, `run` / `run_steps`, content asset metadata, or delivery state transitions.
- Any provider/config edit or requirement that live Tavily/DeepSeek credentials become mandatory for acceptance.
- Any research workflow integration or public response-shape change; those remain Phase 7 concerns unless the Architecture Gate is explicitly revised.
- Any direct-keep weakening or primary Tavily/Crawl4AI routing for project transaction, enterprise disclosure, structured data/data metrics, credit/GSXT, judicial, or exchange disclosure lanes.
- Any broad maintained source expansion, one-profile-per-city/county/park expansion, or incompatible supplemental/national/provincial/city/county domain widening.
- Any inability to represent sufficiency state, budget exhaustion, round trace, and coverage gaps inside existing source-layer objects/artifacts without downstream contract drift.
- Any validation failure where the safe repair path would require protected-contract drift, provider/config changes, mandatory live credentials, or direct-keep weakening.

Phase 6 rollback:
- Disable or revert only Phase 6 source-layer implementation files from the approved Architecture Gate scope; do not revert Phase 5 fallback discovery or unrelated dirty worktree changes.
- Keep deterministic RetrievalPlan fallback, source resolver compatibility gates, and current search-assisted domestic behavior as the safe baseline.
- If coverage judge metadata is insufficient for downstream use, stop with `revise` and defer public response-surface design to Phase 7 rather than widening contracts in Phase 6.
- If live Tavily/Crawl4AI behavior is unstable, keep offline/mocked validation authoritative and record live status as skipped or structured partial failure.

### Phase 7: End-to-End Research Workflow Integration and Eval

Objective:
- Integrate RetrievalPlan into research source acquisition while preserving existing response contracts.

Likely write scope:
- `packages/agents/workflow.py`
- `packages/sources/service.py`
- `tests/test_agents_workflow.py`
- `tests/test_research_api.py`
- eval script under `data/tmp/`

Acceptance criteria:
- `enable_source_acquisition=False` legacy path remains unchanged.
- `enable_source_acquisition=True` can execute RetrievalPlan-based source acquisition.
- `SourceAcquisitionSummary` exposes coverage lanes and gaps through existing compatible fields.
- No protected response-shape drift occurs.

Validation:

```powershell
pytest -q tests\test_agents_workflow.py tests\test_research_api.py tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py
python data\tmp\_research_workflow_source_assisted_eval.py --mode offline --print-json
```

Optional live validation:

```powershell
$env:TAVILY_API_KEY="<set in current terminal only>"
$env:DEEPSEEK_API_KEY="<set in current terminal only>"
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
python data\tmp\_phase5_search_assisted_domestic_eval.py --mode live --print-json
```

### Phase 7 Director Gate Decision

Decision: proceed_to_architecture_gate. Phase 7 may proceed only to `invest_agent_architecture_builder` Architecture Gate. Implementation remains unauthorized until that gate records `Decision: proceed` with exact write scope and compatibility boundaries. Production code was not changed by this director gate.

Task classification and impacted modules:
- Primary area: `research_workflow`.
- Secondary areas: `source_layer`, `domestic_source_collectors`, `eval_policy_ops`.
- Candidate impacted modules for Architecture Gate review only: `packages/agents/workflow.py`, `packages/sources/service.py`, `packages/sources/search_assisted_domestic.py`, `packages/sources/retrieval_plan.py`, `packages/sources/coverage_judge.py`, `tests/test_agents_workflow.py`, `tests/test_research_api.py`, source regression tests, and optional eval scripts under `data/tmp/`.

Current state confirmed:
- `.agent/STATUS.md` and this PLAN both record Phase 6 as completed with Group3 code-quality and functional validation.
- Current state before this gate was `active_phase7_director_gate_ready`.
- Phase 7 objective is to integrate RetrievalPlan execution into research source acquisition while preserving existing response contracts and legacy `enable_source_acquisition=False` behavior.
- Existing source-assisted research workflow already has a query-decomposition-gated path and direct-keep controls; Architecture Gate must decide whether RetrievalPlan can replace or wrap that internal routing without public contract drift.

Protected contracts for Phase 7:
- EvidenceBundle schema.
- EvidenceItem citation fields.
- `source_quality_summary` shape.
- Research analyze response shape.
- Source routing response shape.
- Task/job status semantics.
- `run` / `run_steps` meaning.
- Provider/config compatibility.
- Direct-keep primary paths for enterprise disclosure, project transaction, structured data, credit/GSXT, judicial, and exchange disclosure.
- Legacy `enable_source_acquisition=False` behavior.

Phase 7 real-world validation plan:
- Offline validation is mandatory and authoritative. It must not require `TAVILY_API_KEY`, `DEEPSEEK_API_KEY`, live Crawl4AI network success, or live public-site stability.
- Legacy path case: `enable_source_acquisition=False` must continue to use the existing RAG/evidence bundle pipeline, return `source_acquisition.enabled == False`, and avoid RetrievalPlan/search-assisted execution.
- Enabled source-acquisition case: `enable_source_acquisition=True` with no `source_ids` override may run RetrievalPlan-backed source acquisition internally, but must return the existing research analyze response shape and existing `SourceAcquisitionSummary` fields.
- Explicit source override case: `enable_source_acquisition=True` with `source_ids` must keep the override authoritative and must not force RetrievalPlan/search-assisted execution.
- Direct-keep case: enterprise disclosure/project transaction/structured-data style queries must preserve direct structured primary paths and must not route primary execution through Tavily/Crawl4AI.
- Q03 regression case: Guangdong humanoid robotics policy/project/data workflow must not accept low-altitude/UAV/aviation/AOPA supplemental domains in required official lanes after research workflow integration.
- City/park fallback case: Suzhou Industrial Park style queries must preserve `sipac.gov.cn` discovery hints, parent fallback labeling, and structured coverage gaps without claiming exact local coverage from parent-only evidence.
- Coverage gap visibility case: required-lane insufficiency, budget exhaustion, and direct-keep boundary refusal must remain observable through existing compatible notes/traces/metadata fields, not new public response fields.
- Source quality case: `source_quality_summary` must retain the same shape while reflecting RetrievalPlan-produced source evidence through existing counters and quality fields only.
- Run trace case: any new internal source stage must not change task/job status semantics or the meaning of existing `run` / `run_steps`; if additional metadata is needed, it must be nested in existing compatible metadata fields.
- Optional live validation may be recorded only when credentials exist in the current process; missing credentials are a skip, not a blocker.

Exact Architecture Gate questions:
1. What is the internal boundary between `ResearchWorkflowRunner._run_source_acquisition`, `SourceIntelligenceService`, `build_retrieval_plan`, and `SearchAssistedDomesticOrchestrator`?
2. Should RetrievalPlan replace `decompose_query` for search-assisted workflow routing, wrap it as an internal planning layer, or run only for selected domestic policy/data/local cases in Phase 7?
3. Can RetrievalPlan lanes, coverage gaps, round traces, and sufficiency metadata be represented only through existing `SourceAcquisitionSummary.notes`, `source_traces[].metadata`, `SourceEvidenceBundle.gaps`, and existing bundle metadata without changing public schemas?
4. How is `enable_source_acquisition=False` proven to bypass RetrievalPlan and preserve the legacy RAG path exactly?
5. How are explicit `source_ids` overrides kept authoritative, including `source_ids=["world_bank"]` and user-provided sources?
6. How are direct-keep lanes mapped so project transaction, enterprise disclosure, structured data, credit/GSXT, judicial, and exchange disclosure remain direct primary paths?
7. What fallback occurs when deterministic RetrievalPlan construction fails or DeepSeek is unavailable, and can that fallback avoid mandatory live credentials?
8. What evidence conversion path maps RetrievalPlan/search-assisted documents into existing Source EvidenceItems and then RAG EvidenceBundle items without citation-field changes?
9. What exact tests or evals prove research analyze response shape, source routing response shape, `source_quality_summary`, task/job semantics, and `run_steps` compatibility?
10. What is the rollback switch if RetrievalPlan-backed source acquisition causes regressions: feature flag, internal mode flag, or retaining current query-decomposition path as default?

Group2 assignments after Architecture Gate proceeds:
1. `system_contract_architect`
   - Backing subagent: `invest_agent_architecture_builder`.
   - Objective: produce the Phase 7 Architecture Gate for research workflow/source acquisition integration boundaries.
   - Owned files/modules: `.agent/PLANS/domestic-source-coverage-and-routing-v2.md`, `.agent/STATUS.md`, optional docs under `docs/` if a boundary note is needed.
   - Forbidden scope: no production code edits during Architecture Gate; no protected contract changes.
   - Required output: Architecture Gate with affected contracts, current/proposed boundary, implementation slices, allowed/forbidden write scope, validation design, rollback/fallback, and `Decision: proceed | revise | block`.
2. `research_workflow_implementer`
   - Backing subagent: `invest_feature_programmer` with research workflow lane role card.
   - Objective: only after Architecture Gate `Decision: proceed`, implement the smallest compatible workflow integration for RetrievalPlan-backed source acquisition.
   - Candidate owned files/modules: `packages/agents/workflow.py`, narrow `packages/sources/service.py` only if the Architecture Gate requires an internal adapter method, `tests/test_agents_workflow.py`, `tests/test_research_api.py`.
   - Forbidden scope: `packages/agents/schemas.py`, `packages/sources/schemas.py`, EvidenceBundle/citation/schema changes, public research response shape changes, task/job semantics, `run` / `run_steps` meaning, provider/config behavior, broad source/profile expansion, direct-keep weakening.
3. `source_provider_integrator`
   - Backing subagent: `invest_feature_programmer` with source/provider lane role card.
   - Objective: only if Architecture Gate requires source-layer glue, expose RetrievalPlan/source-assisted execution through existing internal source-layer contracts without public schema drift.
   - Candidate owned files/modules: narrow `packages/sources/search_assisted_domestic.py`, `packages/sources/retrieval_plan.py`, `packages/sources/coverage_judge.py`, focused source tests.
   - Forbidden scope: public `packages/sources/schemas.py` changes, provider/config edits, new live credential requirements, broad source expansion, direct-keep weakening.
4. `eval_harness_implementer`
   - Backing subagent: `invest_feature_programmer` with eval harness lane role card.
   - Objective: add or update an offline Phase 7 eval script only if Architecture Gate requires practical workflow probes beyond pytest.
   - Candidate owned files/modules: `data/tmp/_phase7_retrieval_plan_research_workflow_eval.py` or focused additions to existing offline eval scripts.
   - Forbidden scope: mandatory live credentials, broad data capture, public response/schema changes.

Group3 validation assignments:
1. `invest_code_quality_checker`
   - Run focused ruff/compile/pytest for every touched production/test/eval file.
   - Run research contract checks: `pytest -q tests/test_agents_workflow.py`, `pytest -q tests/test_research_api.py`, `pytest -q tests/test_research_provider_integration.py`, and `pytest -q tests/test_deepseek_provider.py` where relevant to touched paths.
   - Run source regression checks when source-layer glue changes: `pytest -q tests/test_sources_layer.py`, `pytest -q tests/test_sources_adapters_v1.py`, `pytest -q tests/test_sources_hardening_step34.py`, `pytest -q tests/test_sources_evals_step35.py`.
   - Run domestic checks if domestic source behavior changes: `pytest -q tests/test_sources_router_domestic.py`, `pytest -q tests/test_sources_profile_adapter.py`, `pytest -q tests/test_sources_real_domestic_step42.py`, `pytest -q tests/test_sources_pdf_step43.py`.
   - Report known repo-wide `data/tmp` ruff debt separately from Phase 7 focused results.
2. `invest_functional_validator`
   - Validate offline real-world cases for legacy disabled mode, enabled source acquisition, explicit source override, direct-keep, Q03, city/park fallback, coverage gap visibility, source quality shape, and run trace compatibility.
   - Inspect actual response payload fields and trace metadata; do not accept "tests passed" alone.
   - Record optional live status only when credentials are present in the current process.

Phase 7 stop conditions:
- Stop and revise if Architecture Gate finds protected response-shape drift is required.
- Stop and request human input if public `ResearchAnalysisResult`, `SourceAcquisitionSummary`, Source EvidenceBundle/EvidenceItem/Citation, source routing response, task/job semantics, or `run` / `run_steps` meaning must change.
- Stop if Phase 7 would require mandatory live credentials, broad source expansion, direct-keep weakening, or public source schema changes.
- Stop if RetrievalPlan integration cannot preserve `enable_source_acquisition=False` legacy behavior.

## Phase 7 Architecture Gate Decision

Decision: `proceed`.

Classification:
- Primary area: `research_workflow`.
- Secondary areas: `source_layer`, `domestic_source_collectors`, `eval_policy_ops`.
- Gate type: `system_contract_architect` / `invest_agent_architecture_builder`.
- Gate scope: architecture and assignment only; no production code implementation in this gate.

Architecture intent:
- RetrievalPlan-backed source acquisition can be integrated into research workflow through the existing internal source-acquisition path without changing protected public contracts.
- The safest Phase 7 path is to keep `packages/agents/workflow.py` query-decomposition based for routing and execution, then surface Phase 6 coverage/round metadata already emitted by `SearchAssistedDomesticOrchestrator` through existing trace, notes, bundle gap, and metadata fields.
- `packages/agents/workflow.py` should not consume `packages.sources.retrieval_plan.build_retrieval_plan()` directly in the first Phase 7 implementation slice. Direct consumption would introduce a second planning authority inside research workflow and raise avoidable compatibility risk around lane-to-task mapping, source override behavior, and direct-keep boundaries.
- `build_retrieval_plan()` remains a source-layer planning contract and may continue to inform source-layer helpers and tests. If future implementation needs lane-to-task conversion, it must be added as source-layer adapter glue and gated separately before workflow imports it as an execution planner.

Current execution path observed:
- `ResearchWorkflowRunner.run()` preserves legacy behavior when `enable_source_acquisition=False`: it records skipped source stages, uses `retrieve_evidence` and `build_evidence_bundle`, and returns `SourceAcquisitionSummary(enabled=False)`.
- `ResearchWorkflowRunner._run_source_acquisition()` already routes sources through `SourceIntelligenceService`, skips search-assisted execution when `request.source_ids` is present, calls `decompose_query(request.query)` otherwise, runs only tasks with `execution_bucket == "search_assisted_sources"`, preserves direct-keep controls for `direct_structured_sources`, converts search-assisted documents to existing Source `EvidenceItem` / `Citation`, builds existing Source `EvidenceBundle`, and converts it to the existing RAG bundle.
- `SearchAssistedDomesticOrchestrator.orchestrate_task()` already emits Phase 6 metadata in `DomesticSearchAssistedResponse.metadata`: `round_policy`, `budget_state`, `round_trace`, `coverage_sufficient`, `coverage_gaps`, candidate decisions, and local fallback metadata.
- `workflow.py` already nests that response metadata under `SourceAcquisitionSummary.source_traces[].metadata.response_metadata` for `tool_name == "search_assisted_domestic"`.
- `SourceIntelligenceService` currently routes sources and dispatches bundle-building through existing source-layer contracts; Phase 7 does not require public source routing response-shape changes. Narrow internal service glue is optional only if implementation needs a helper to normalize source-layer trace/gap metadata.

Affected contracts and compatibility decision:
- `ResearchAnalyzeRequest`: unchanged. No new request field, no source-acquisition mode flag, and no provider/config field is required for Phase 7.
- `ResearchAnalysisResult`: unchanged. Coverage details remain inside existing `source_acquisition` summary and source trace metadata.
- `SourceAcquisitionSummary`: unchanged. Use existing `notes`, `source_traces`, `source_quality_summary`, and counters only.
- Source EvidenceBundle schema: unchanged. Do not add typed coverage-gap objects to `EvidenceBundle.gaps`; if workflow-level gap visibility is needed, append compact string tokens only and keep structured details in trace metadata.
- EvidenceItem / Citation fields: unchanged. Search-assisted conversion continues through existing `convert_search_response_to_evidence_items()` and existing citation metadata.
- `source_quality_summary`: unchanged. Do not add coverage-lane fields to this shape; RetrievalPlan/search-assisted output may affect existing counters, warnings, density, and citation completeness only through existing inputs.
- Source routing response shape: unchanged. Existing `RoutingRecommendation` and source service routing remain authoritative for routed source summaries.
- Task/job semantics and `run` / `run_steps`: unchanged. Existing source stage names keep their meaning. Phase 7 may add nested metadata to existing `source_search` or `source_build_bundle` step output, but must not rename, repurpose, or alter status semantics.
- Provider/config compatibility: unchanged. No mandatory DeepSeek/Tavily/live Crawl4AI credentials for offline acceptance. Missing live credentials remain skip/structured partial failure.
- Legacy `enable_source_acquisition=False`: unchanged and must not import or execute RetrievalPlan/search-assisted orchestration.
- Explicit `source_ids` override: unchanged and authoritative. RetrievalPlan/search-assisted execution remains skipped when `request.source_ids` is non-empty.
- Direct-keep primary paths: unchanged. `project_transaction`, `enterprise_disclosure`, structured data, credit/GSXT, judicial, and exchange-disclosure primary paths must not route through Tavily/Crawl4AI.

Minimal compatible implementation boundary:
- Primary implementation should be a narrow research workflow metadata bridge in `packages/agents/workflow.py`:
  - collect `response.metadata` from each `DomesticSearchAssistedResponse`;
  - keep it nested under existing `ToolTrace.metadata.response_metadata`;
  - optionally aggregate only compact compatibility notes into `SourceAcquisitionSummary.notes`;
  - optionally append existing-string `SourceEvidenceBundle.gaps` tokens for unsatisfied coverage, with structured details remaining in trace metadata.
- Optional source-layer adapter glue may be added only if it removes duplicated parsing of Phase 6 metadata. It must remain internal and must not change public schemas.
- The first implementation slice must not replace `decompose_query()` with `build_retrieval_plan()` inside workflow. Query decomposition remains the workflow execution bridge because it already preserves source override, direct-keep, and search-assisted task contracts.

Coverage lane/gap representation constraints:
- Structured coverage details path:
  - `ResearchAnalysisResult.source_acquisition.source_traces[].metadata.response_metadata.coverage_sufficient`
  - `ResearchAnalysisResult.source_acquisition.source_traces[].metadata.response_metadata.coverage_gaps`
  - `ResearchAnalysisResult.source_acquisition.source_traces[].metadata.response_metadata.round_trace`
  - `ResearchAnalysisResult.source_acquisition.source_traces[].metadata.response_metadata.budget_state`
  - `ResearchAnalysisResult.source_acquisition.source_traces[].metadata.response_metadata.candidate_decisions` through the existing sibling `candidate_decisions` trace metadata field.
- Required `coverage_gaps` item shape must stay JSON-serializable and source-layer internal, using the existing Phase 6 keys only: `lane_id`, `reason_code`, `required`, optional `fallback_level`, optional `fallback_source`, optional `parent_evidence_only`, optional `local_claim_allowed`, optional `notes`.
- Existing string gap path, if used:
  - `SourceEvidenceBundle.gaps[]` and converted `RetrievalResponse.notes[]` may contain compact strings such as `coverage_gap:<lane_id>:<reason_code>` or `coverage_gap:<lane_id>:parent_evidence_only`.
  - Do not put dict/list objects into `EvidenceBundle.gaps` because the current schema is `list[str]`.
- Existing summary notes path, if used:
  - `SourceAcquisitionSummary.notes[]` may include compact human-readable strings like `coverage_gap_count=<n>` or `coverage_gap:<lane_id>:<reason_code>`.
  - Do not add new `SourceAcquisitionSummary` fields.
- `source_quality_summary` must not carry lane/gap fields.

Approved implementation write scope after this gate:
- `packages/agents/workflow.py`: narrow metadata/gap/note propagation only within `_run_source_acquisition`; preserve existing stage names and disabled/override/direct-keep branches.
- `packages/sources/service.py`: optional narrow internal helper only if needed for source-layer metadata normalization; no public response shape changes.
- `tests/test_agents_workflow.py`: focused tests for disabled mode, enabled source acquisition, explicit source IDs override, direct-keep, coverage metadata propagation, `source_quality_summary` shape, and run-step semantics.
- `tests/test_research_api.py`: focused API response compatibility checks if workflow output serialization changes through existing fields.
- Optional focused source tests only if source-layer helper glue is touched: `tests/test_sources_search_assisted_domestic.py`, `tests/test_sources_retrieval_plan.py`, `tests/test_sources_coverage_judge.py`.
- Optional offline eval script: `data/tmp/_phase7_retrieval_plan_research_workflow_eval.py`, if Group3 requires practical response/trace probes beyond pytest.

Forbidden implementation scope:
- Do not edit `packages/agents/schemas.py` or `packages/sources/schemas.py`.
- Do not change `ResearchAnalyzeRequest`, `ResearchAnalysisResult`, `SourceAcquisitionSummary`, Source EvidenceBundle, Source EvidenceItem, Citation, or `SourceQualitySummary` schemas.
- Do not change source routing public response shape or `RoutingRecommendation` semantics.
- Do not change task/job status semantics, `run` / `run_steps` meaning, existing source stage names, content asset metadata, or delivery transitions.
- Do not add provider/config requirements or make live DeepSeek/Tavily/Crawl4AI credentials mandatory.
- Do not broaden domestic source/profile coverage, source packs, routing taxonomy, or domain allowlists as part of Phase 7.
- Do not route direct-keep primary lanes through Tavily/Crawl4AI.
- Do not store private reasoning, secrets, API keys, or raw provider prompts in traces, metadata, PLAN, STATUS, or eval artifacts.

Group2 implementation lane assignments after gate:
1. `research_workflow_implementer`
   - Backing subagent: `invest_feature_programmer` with research workflow lane role card.
   - Objective: implement the smallest compatible workflow metadata bridge using existing query-decomposition/search-assisted execution.
   - Owned files: `packages/agents/workflow.py`, `tests/test_agents_workflow.py`, and `tests/test_research_api.py` only if API serialization assertions are needed.
   - Required output: existing response shape preserved; Phase 6 coverage metadata visible through existing trace/notes/gap fields; disabled mode, explicit `source_ids`, and direct-keep behavior unchanged.
2. `source_provider_integrator`
   - Backing subagent: `invest_feature_programmer` with source/provider lane role card.
   - Use only if workflow implementation proves a source-layer internal adapter is needed.
   - Owned files if activated: narrow `packages/sources/service.py` or focused source-layer helper/tests. Do not change public schemas or source routing response shape.
3. `eval_harness_implementer`
   - Backing subagent: `invest_feature_programmer` with eval harness lane role card.
   - Use only if practical offline workflow probes are needed beyond pytest.
   - Owned file if activated: `data/tmp/_phase7_retrieval_plan_research_workflow_eval.py`.

Group3 validation plan:
- Code-quality gate:
  - `python -m ruff check packages\agents\workflow.py tests\test_agents_workflow.py tests\test_research_api.py`
  - `python -m py_compile packages\agents\workflow.py tests\test_agents_workflow.py tests\test_research_api.py`
  - If `packages/sources/service.py` or source helpers are touched, include those files and their focused tests in ruff/compile.
- Research contract gate:
  - `pytest -q tests\test_agents_workflow.py`
  - `pytest -q tests\test_research_api.py`
  - `pytest -q tests\test_research_provider_integration.py`
  - `pytest -q tests\test_deepseek_provider.py`
- Source regression gate when source-layer glue changes:
  - `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py`
- Domestic regression gate when domestic source behavior changes:
  - `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py`
- Functional validation cases:
  - legacy disabled mode: `enable_source_acquisition=False` uses existing RAG path, `source_acquisition.enabled == False`, source stages skipped, no RetrievalPlan/search-assisted execution;
  - enabled source acquisition: existing response shape with source evidence and trace metadata;
  - explicit `source_ids` override: authoritative `source_ids`, no search-assisted execution, routed sources unchanged;
  - direct-keep: direct structured task families do not call `SearchAssistedDomesticOrchestrator`;
  - Q03 negative-domain: humanoid robotics official lanes do not accept low-altitude/UAV/aviation/AOPA domains in trace candidate decisions;
  - Suzhou Industrial Park fallback: `sipac.gov.cn` hints and parent/local gap metadata remain visible without claiming parent-only evidence as exact local coverage;
  - coverage gaps: required-lane insufficiency, budget exhaustion, and direct-keep boundary refusal remain observable through existing `source_traces[].metadata.response_metadata.coverage_gaps` and optional compact notes/gap strings;
  - `source_quality_summary`: exact key set remains `sources_attempted`, `sources_succeeded`, `sources_failed`, `source_error_breakdown`, `citation_completeness_score`, `evidence_density`, `truncated_sources`, `warnings`;
  - run trace semantics: existing source stage names/statuses retain meaning; additional data is nested metadata only.

Stop conditions and rollback:
- Stop and revise if implementation requires new public fields, schema edits, non-string `EvidenceBundle.gaps`, `source_quality_summary` shape changes, task/job semantic changes, provider/config changes, mandatory live credentials, broad source expansion, or direct-keep weakening.
- Stop and request human input if workflow must consume `build_retrieval_plan()` directly as a new execution planner instead of staying query-decomposition based.
- Rollback path: remove the narrow workflow metadata bridge and return to the current query-decomposition source-assisted path. Because Phase 7 is constrained to existing fields, rollback preserves current disabled mode, explicit source override, direct-keep behavior, source routing, and evidence conversion.

## Required Evaluation Cases

Frozen initial cases:

| Case ID | Query | Required validation |
|---|---|---|
| `SRC-COV-01` | `广东人形机器人产业政策和项目落地情况` | Requires national policy, provincial rollout, project transaction, data/statistics attempt; must not include low-altitude/aviation domains for humanoid robotics. |
| `SRC-COV-02` | `安徽的低空经济未来前景如何` | Allows low-altitude supplemental domains only in supplemental lane; local rollout remains Anhui official first. |
| `SRC-COV-03` | `国家层面对算力基础设施有什么最新政策方向` | Requires national policy; optional data/statistics; no low-altitude or robotics supplemental leakage. |
| `SRC-COV-04` | `江苏光伏产业链出海面临哪些政策和贸易风险` | Requires national policy, provincial rollout, trade/commerce/customs angle, optional data. |
| `SRC-COV-05` | `深圳低空经济有哪些政策和招标信号` | Requires city fallback plus direct project transaction; must not route project lane through Tavily primary path. |
| `SRC-COV-06` | `中信海直（000099.SZ）在低空经济方向有哪些公告和项目` | Enterprise disclosure direct-keep primary; project transaction direct-keep primary. |
| `SRC-COV-07` | `成都人工智能产业园区有哪些政策和项目机会` | City/park fallback with transparent hold/gap if unsupported. |
| `SRC-COV-08` | `浙江低空经济相关上市公司有哪些公告` | Disclosure direct-keep primary; local policy optional supplement. |
| `SRC-COV-09` | `广东人形机器人产业规模和企业数量有什么数据支撑` | Statistics/data lane required; association signals cannot satisfy data lane. |
| `SRC-COV-10` | `某行业协会的白皮书和论坛信息如何作为补充证据` | Supplemental lane only; should not fan out to all official policy lanes unless requested. |

## Continue Rule

After each phase, continue automatically to the next phase when:
- acceptance criteria are met
- required validation passes
- no approval, credential, dependency, or human-review blocker exists
- no protected contract change is required without explicit authorization
- no direct-keep source boundary is violated

Do not treat phase summary as the default stopping point.

## Stop Conditions

Stop and request user guidance when:
- a protected contract must change
- DeepSeek credentials are required for mandatory validation and deterministic fallback is insufficient
- Tavily/Crawl4AI live behavior cannot be represented as structured partial failure
- source expansion would require broad unplanned profile creation
- validation fails and a safe repair path is unclear
- the user explicitly asks to pause
- final done condition is reached

## Done Condition

This PLAN is complete when:
- RetrievalPlan and CoverageLane contracts exist and are validated
- DeepSeek planner is optional, schema-bound, and has deterministic fallback
- source resolver prevents theme/domain leakage such as Q03 humanoid robotics receiving low-altitude/aviation domains
- national/provincial backbone source maps support required policy/data lanes
- city/county fallback ladder works without one-profile-per-city expansion
- multi-round search is bounded by lane sufficiency and credit budgets
- research workflow can consume the new retrieval plan without protected response-shape drift
- offline eval cases pass and optional live status is recorded when credentials are available

## Validation Loop

Use eval-driven improvement:

1. Make one focused change.
2. Run the focused validation for the phase.
3. Record results in this PLAN and `.agent/STATUS.md`.
4. If a required lane fails, improve planner/resolver/gate logic.
5. If a direct-keep or protected-contract boundary is violated, stop and open a remediation gate.

Baseline planning validation:

```powershell
Test-Path .agent\PLANS\domestic-source-coverage-and-routing-v2.md
Select-String -Path .agent\STATUS.md -Pattern 'domestic-source-coverage-and-routing-v2.md'
Select-String -Path .agent\PLANS\domestic-source-coverage-and-routing-v2.md -Pattern 'CoverageLane','RetrievalPlan','DeepSeek','Q03','Continue Rule','Stop Conditions','Done Condition'
```

## Risks and Rollback

Risks:
- Overusing DeepSeek could make retrieval behavior harder to audit.
- Source coverage contracts could become too strict and reduce recall.
- City/county fallback may still miss highly fragmented local content.
- Existing dirty worktree limits scope proof until release hygiene is handled.
- Public schema additions already present in `packages/sources/schemas.py` remain a separate release-boundary risk.
- Repo-wide ruff still has unrelated historical `data/tmp` lint debt.
- Phase 1 scope proof is limited by pre-existing dirty forbidden paths recorded in `.agent/WORKTREE_INVENTORY.md`; focused files and validations passed, but git cannot prove those unrelated files were untouched from a clean baseline.

Rollback:
- Keep deterministic fallback planner as default.
- Keep legacy `decompose_query` and existing source-assisted path available until RetrievalPlan path passes eval.
- Gate new RetrievalPlan execution behind an opt-in feature flag or source-acquisition mode.
- If live DeepSeek or Tavily fails, record structured provider failure and use deterministic/offline path.

## Progress

- 2026-04-28: Created PLAN from recent source coverage, Q03 routing relevance, city/county fallback, and DeepSeek retrieval-planner discussions. Planning-only step; no production code changed.
- 2026-04-28: Phase 0 director gate completed. CoverageLane/RetrievalPlan v1 scope frozen; `packages/sources/retrieval_plan.py` selected for public source-layer RetrievalPlan types; `SRC-COV-01..10` frozen as initial eval cases; Phase 1 Group2/Group3 assignments and stricter real-world validation plan recorded. Production code was not changed.
- 2026-04-28: Phase 1 Architecture Gate completed with `Decision: proceed`. The gate confirmed RetrievalPlan v1 remains a source-layer planning contract, Phase 1 must keep public types in `packages/sources/retrieval_plan.py`, `packages/sources/schemas.py` remains forbidden for Phase 1, Q03 negative-domain validation is mandatory, city/county fallback must not claim local coverage from parent evidence, and implementation is limited to the approved source/test files. Production code was not changed by the gate.
- 2026-04-28: Phase 1 implementation completed. Added `packages/sources/retrieval_plan.py` with fixed CoverageLane/SourceIntent/DomainStrategy/RetrievalPlan contracts and deterministic fallback builder; repaired `query_decomposition` so local rollout no longer inherits supplemental domains and unknown supplemental themes no longer fan out to every supplemental domain; added focused field-level tests for `SRC-COV-01..10`, direct-keep paths, Q03 negative-domain behavior, trade/customs/commerce coverage for `SRC-COV-04`, city/park fallback guards, and no-credential deterministic fallback.
- 2026-04-28: Phase 1 validation completed. Focused ruff passed; py_compile passed; focused pytest passed with `42 passed`; source regression pytest passed with `27 passed`; domestic source pytest passed with `16 passed`; functional validator passed after remediation and produced `data/tmp/retrieval_plan_field_validation_20260428.json`. Repo-wide `python -m ruff check .` still fails only on historical `data/tmp` scratch/demo scripts; this remains a known non-Phase-1 blocker.
- 2026-04-28: Phase 2 Architecture Gate completed with `Decision: proceed`. The gate confirmed DeepSeek planner integration is optional source-layer RetrievalPlan planning only, may consume the existing provider JSON boundary, and must preserve provider/config compatibility plus protected API/evidence/research/task/content/delivery contracts. Production code was not changed by the gate.
- 2026-04-28: Phase 2 implementation scope approved for `packages/sources/retrieval_planner_deepseek.py`, `tests/test_sources_retrieval_planner_deepseek.py`, focused `tests/test_deepseek_provider.py` coverage, and only necessary backward-compatible `packages/providers/**` or `packages/core/config.py` settings. Required validation includes missing-key fallback, mock invalid JSON, invalid enum/schema repair/refusal, direct-answer/refusal fallback, no-secret metadata, focused pytest, source regression, and optional live smoke only when `DEEPSEEK_API_KEY` is present.
- 2026-04-28: Phase 2 implementation completed. Added optional `packages/sources/retrieval_planner_deepseek.py` and `tests/test_sources_retrieval_planner_deepseek.py`; kept deterministic `build_retrieval_plan(query)` behavior credential-free; added DeepSeek planner fallback on missing client/key, provider failure, invalid enum/schema, invented fields, and direct-answer/refusal output; sanitized provider plans so deterministic code remains authoritative for `plan_id`, round policy, stop conditions, coverage gaps, source intents, domain strategy, execution bucket, fallback ladder, allowed domains, and direct-keep boundaries.
- 2026-04-28: Phase 2 validation completed. Focused ruff passed; py_compile passed; planner/provider pytest passed with `10 passed`; retrieval-plan regression pytest passed with `42 passed`; source regression pytest passed with `27 passed`; domestic source regression passed with `16 passed`; functional validator passed and produced `data/tmp/deepseek_retrieval_planner_functional_validation_20260428.json`. Optional live DeepSeek smoke was skipped because `DEEPSEEK_API_KEY` was absent in the current process. Repo-wide `python -m ruff check .` still fails only on historical `data/tmp` scratch/demo scripts and remains a known non-Phase-2 blocker.
- 2026-04-28: Phase 3 Architecture Gate completed with `Decision: proceed`. The gate confirmed source resolver/compatibility work affects only source-layer execution and candidate decisions; protected API, EvidenceBundle, citation, research, task, content, delivery, provider, and source routing response contracts remain unchanged. Approved scope is limited to resolver/search-assisted/query-decomposition code and focused tests; forbidden scope includes `packages/sources/schemas.py`, `packages/agents/workflow.py`, providers/config, broad profile expansion, and direct-keep weakening. Production code was not changed by the gate.
- 2026-04-28: Phase 3 implementation completed. Added `packages/sources/source_resolver.py`; wired candidate compatibility checks into `packages/sources/search_assisted_domestic.py`; updated `packages/sources/query_decomposition.py` so humanoid robotics policy/local/data tasks carry low-altitude/UAV negative terms; added focused resolver/search-assisted/query-decomposition tests. The gate now rejects incompatible candidates by domain, source role, region, theme alias, negative terms, supplemental-primary misuse, direct-keep boundary, and unsupported coverage lane.
- 2026-04-28: Phase 3 validation completed. Focused ruff passed; py_compile passed; focused pytest passed with `39 passed`; search-assisted/source-discovery regression passed with `43 passed`; source regression passed with `27 passed`; domestic source regression passed with `16 passed`; Group3 code-quality gate passed; Group3 functional validator passed and produced `data/tmp/phase3_source_resolver_functional_validation_20260428.json` with 11 offline probes. Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo scripts. Scope proof remains limited by pre-existing dirty protected paths recorded in `.agent/WORKTREE_INVENTORY.md`.
- 2026-04-28: Phase 4 Architecture Gate completed with `Decision: proceed`. The gate froze Phase 4 to minimal national/provincial backbone expansion: national policy/statistics/customs/commerce roles and first-wave provincial government/DRC/industry-MIIT/statistics/science-technology/commerce roles where domain metadata exists. City/county full-profile expansion remains forbidden until Phase 5 except explicit fallback/gap metadata. Approved implementation scope is limited to source profiles, packs, router, narrow RetrievalPlan/resolver metadata, and focused tests; protected downstream contracts and direct-keep primary paths remain unchanged.
- 2026-04-28: Phase 4 implementation completed for minimal national/provincial backbone expansion. Added `build_phase4_national_provincial_backbone_profiles()` with national MOST/NBS/Customs/MOFCOM and first-wave Guangdong/Jiangsu/Anhui/Zhejiang/Sichuan/Shanghai policy/data/trade backbone entries; registered builder into `build_domestic_source_profiles()`; added `policy_data_backbone_pack_cn_v1`; added narrow router data/trade/provincial backbone routing boosts; expanded `query_decomposition.REGION_DOMAIN_MAP` and resolver region-domain matching for first-wave official domains; added focused test `tests/test_sources_domestic_scaleout_phase7.py`.
- 2026-04-28: Phase 4 initial Group3 review found two live issues: `cn_policy_ndrc_tzgg_v1` was referenced by the new backbone path but disabled in the default registry, and default local-rollout routing still fanned out into unrelated provincial/city/park sources for Q03-style queries.
- 2026-04-28: Phase 4 remediation completed. Enabled the NDRC profile in the default registry, added regression tests, and removed unconditional default local-rollout fanout into unrelated first-wave provinces, historical city sources, and park/zone sources while preserving generic local-rollout sources and explicit city/park strategy behavior.
- 2026-04-28: Phase 4 final validation completed after remediation:
  - `python -m ruff check packages\\sources\\profiles\\china_scaleout.py packages\\sources\\profiles\\__init__.py packages\\sources\\packs.py packages\\sources\\router.py packages\\sources\\query_decomposition.py packages\\sources\\source_resolver.py packages\\sources\\retrieval_plan.py tests\\test_sources_domestic_scaleout_phase7.py tests\\test_sources_retrieval_plan.py tests\\test_sources_query_decomposition.py tests\\test_sources_source_resolver.py tests\\test_sources_search_assisted_domestic.py tests\\test_sources_tiaokuai_phase23.py` -> pass
  - `python -m py_compile packages\\sources\\profiles\\china_scaleout.py packages\\sources\\profiles\\__init__.py packages\\sources\\packs.py packages\\sources\\router.py packages\\sources\\query_decomposition.py packages\\sources\\source_resolver.py packages\\sources\\retrieval_plan.py tests\\test_sources_domestic_scaleout_phase7.py tests\\test_sources_retrieval_plan.py tests\\test_sources_query_decomposition.py tests\\test_sources_source_resolver.py tests\\test_sources_search_assisted_domestic.py tests\\test_sources_tiaokuai_phase23.py` -> pass
  - `pytest -q tests\\test_sources_domestic_scaleout_phase7.py tests\\test_sources_retrieval_plan.py tests\\test_sources_query_decomposition.py tests\\test_sources_source_resolver.py tests\\test_sources_search_assisted_domestic.py tests\\test_sources_tiaokuai_phase23.py` -> `73 passed`
  - `pytest -q tests\\test_sources_domestic_scaleout_phase3.py tests\\test_sources_domestic_scaleout_phase4.py tests\\test_sources_router_domestic.py tests\\test_sources_profile_adapter.py` -> `12 passed`
  - `pytest -q tests\\test_sources_layer.py tests\\test_sources_adapters_v1.py tests\\test_sources_hardening_step34.py tests\\test_sources_evals_step35.py` -> `27 passed`
  - `pytest -q tests\\test_sources_router_domestic.py tests\\test_sources_profile_adapter.py tests\\test_sources_real_domestic_step42.py tests\\test_sources_pdf_step43.py` -> `16 passed`
  - Group3 code-quality recheck -> pass
  - Group3 functional recheck -> pass; artifact `data/tmp/phase4_backbone_functional_validation_20260428.json` has `overall_pass: true`
- 2026-04-28: Phase 5 director gate completed. Decision: proceed to Phase 5 Architecture Gate, not implementation yet. The real-world validation plan was refined for city/county/park official-domain-first fallback discovery, parent-level evidence labeling, coverage-gap transparency, direct-keep preservation, Q03/unknown-supplemental regressions, and bounded Tavily usage. Production code was not changed.
- 2026-04-28: Phase 5 Architecture Gate completed. Decision: `proceed`. Approved implementation is source-layer only and limited to resolver/search-assisted/query-decomposition/retrieval-plan behavior plus focused tests and optional offline eval. Existing source-layer contracts can carry fallback metadata, so no protected evidence/API/research/provider/task/content/delivery contract changes and no provider/config edits are authorized. Production code was not changed by the gate.
- 2026-04-28: Phase 5 Group2 `source_provider_integrator` implementation completed within approved scope. Updated `packages/sources/source_resolver.py`, `packages/sources/search_assisted_domestic.py`, and narrow `packages/sources/query_decomposition.py` for city/county/park official-domain-first fallback discovery, municipal local-rollout enablement, parent-level fallback labeling, and bounded candidate policy metadata. Added `tests/test_sources_city_county_fallback.py` and focused test additions in resolver/search-assisted/retrieval-plan/query-decomposition suites. No protected contract/provider/config/task/content/delivery changes were made.
- 2026-04-28: Phase 5 validation snapshot (Group2 scope):
  - `python -m ruff check packages\\sources\\source_resolver.py packages\\sources\\search_assisted_domestic.py packages\\sources\\query_decomposition.py packages\\sources\\retrieval_plan.py tests\\test_sources_city_county_fallback.py tests\\test_sources_search_assisted_domestic.py tests\\test_sources_source_resolver.py tests\\test_sources_query_decomposition.py tests\\test_sources_retrieval_plan.py` -> pass
  - `python -m py_compile packages\\sources\\source_resolver.py packages\\sources\\search_assisted_domestic.py packages\\sources\\query_decomposition.py packages\\sources\\retrieval_plan.py tests\\test_sources_city_county_fallback.py tests\\test_sources_search_assisted_domestic.py tests\\test_sources_source_resolver.py tests\\test_sources_query_decomposition.py tests\\test_sources_retrieval_plan.py` -> pass
  - `pytest -q tests\\test_sources_city_county_fallback.py tests\\test_sources_search_assisted_domestic.py tests\\test_sources_source_resolver.py tests\\test_sources_query_decomposition.py tests\\test_sources_retrieval_plan.py` -> `68 passed`
  - `pytest -q tests\\test_sources_layer.py` -> `8 passed`
  - `pytest -q tests\\test_sources_adapters_v1.py` -> `8 passed`
  - `pytest -q tests\\test_sources_hardening_step34.py` -> `4 passed`
  - `pytest -q tests\\test_sources_evals_step35.py` -> `7 passed`
  - `pytest -q tests\\test_sources_router_domestic.py` -> `2 passed`
  - `pytest -q tests\\test_sources_profile_adapter.py` -> `4 passed`
  - `pytest -q tests\\test_sources_real_domestic_step42.py` -> `4 passed`
  - `pytest -q tests\\test_sources_pdf_step43.py` -> `6 passed`
  - `python -m ruff check .` -> fails on pre-existing historical `data/tmp` lint debt; unchanged known non-Phase-5 blocker.
- 2026-04-28: Phase 5 first functional validation found one acceptance failure: `decompose_query("苏州工业园区光伏项目政策")` did not preserve exact park discovery, because it omitted `sipac.gov.cn` and search phrases containing `苏州工业园区`.
- 2026-04-28: Phase 5 remediation completed with TDD. Added a failing assertion for the county/district fixture, then added exact local entity discovery hints in `packages/sources/query_decomposition.py` for explicit `苏州工业园区` queries. This injects `sipac.gov.cn` and exact search phrases without adding maintained city/county/park profiles, packs, or router expansion.
- 2026-04-28: Phase 5 final validation completed:
  - `python -m ruff check packages\\sources\\source_resolver.py packages\\sources\\search_assisted_domestic.py packages\\sources\\query_decomposition.py packages\\sources\\retrieval_plan.py tests\\test_sources_city_county_fallback.py tests\\test_sources_search_assisted_domestic.py tests\\test_sources_source_resolver.py tests\\test_sources_query_decomposition.py tests\\test_sources_retrieval_plan.py` -> pass
  - `python -m py_compile packages\\sources\\source_resolver.py packages\\sources\\search_assisted_domestic.py packages\\sources\\query_decomposition.py packages\\sources\\retrieval_plan.py tests\\test_sources_city_county_fallback.py tests\\test_sources_search_assisted_domestic.py tests\\test_sources_source_resolver.py tests\\test_sources_query_decomposition.py tests\\test_sources_retrieval_plan.py` -> pass
  - `pytest -q tests\\test_sources_city_county_fallback.py tests\\test_sources_search_assisted_domestic.py tests\\test_sources_source_resolver.py tests\\test_sources_query_decomposition.py tests\\test_sources_retrieval_plan.py` -> `68 passed`
  - `pytest -q tests\\test_sources_layer.py tests\\test_sources_adapters_v1.py tests\\test_sources_hardening_step34.py tests\\test_sources_evals_step35.py` -> `27 passed`
  - `pytest -q tests\\test_sources_router_domestic.py tests\\test_sources_profile_adapter.py tests\\test_sources_real_domestic_step42.py tests\\test_sources_pdf_step43.py` -> `16 passed`
  - Group3 code-quality remediation recheck -> pass
  - Group3 functional remediation recheck -> pass; artifact `data/tmp/phase5_city_county_fallback_functional_validation_20260428.json` has `overall_pass: true`
  - Local artifact probe confirmed `sipac.gov.cn` is present and a search phrase preserves `苏州工业园区`.
- 2026-04-28: Phase 6 director gate completed. Decision: proceed to Phase 6 Architecture Gate, not implementation yet. The real-world validation plan was refined for multi-round stop/continue behavior, coverage sufficiency judging, budget enforcement, required-lane gap closure, direct-keep preservation, Q03 regression, city/county fallback preservation, and no incompatible domain widening. Group2 and Group3 assignments were recorded. Production code was not changed.
- 2026-04-28: Phase 6 Architecture Gate completed with `Decision: proceed`. The gate confirmed multi-round execution, per-round trace metadata, coverage sufficiency judging, budget enforcement, budget-exhaustion gaps, and domain-widening controls can remain inside source-layer contracts/artifacts using `RetrievalPlan.round_policy`, `CoverageLanePlan.success_criteria`, `CoverageGap`, `CandidateCompatibilityDecision.reason_code`, and `DomesticSearchAssistedResponse.metadata`. Approved implementation is source-layer only: `packages/sources/coverage_judge.py`, `packages/sources/search_assisted_domestic.py`, narrow `packages/sources/retrieval_plan.py`, narrow `packages/sources/source_resolver.py`, focused tests, and optional offline eval under `data/tmp/_phase6_multi_round_coverage_eval.py`. Protected downstream contracts, provider/config edits, mandatory live credentials, research workflow integration, broad source/profile expansion, incompatible domain widening, and direct-keep weakening remain forbidden. Production code was not changed by the gate.
- 2026-04-28: Phase 6 Group2 `source_provider_integrator` implementation completed within approved scope. Added deterministic source-layer coverage sufficiency judge (`packages/sources/coverage_judge.py`), integrated bounded multi-round execution and budget/trace/gap metadata into `packages/sources/search_assisted_domestic.py`, and added narrow helper mappings in `packages/sources/retrieval_plan.py` and `packages/sources/source_resolver.py`. Added `tests/test_sources_coverage_judge.py` and focused Phase 6 assertions in search-assisted/retrieval-plan/source-resolver/city-county/query-decomposition tests.
- 2026-04-28: Phase 6 Group2 validation snapshot:
  - `python -m ruff check packages/sources/coverage_judge.py packages/sources/search_assisted_domestic.py packages/sources/retrieval_plan.py packages/sources/source_resolver.py tests/test_sources_coverage_judge.py tests/test_sources_search_assisted_domestic.py tests/test_sources_retrieval_plan.py tests/test_sources_source_resolver.py tests/test_sources_city_county_fallback.py tests/test_sources_query_decomposition.py` -> pass
  - `python -m py_compile packages/sources/coverage_judge.py packages/sources/search_assisted_domestic.py packages/sources/retrieval_plan.py packages/sources/source_resolver.py tests/test_sources_coverage_judge.py tests/test_sources_search_assisted_domestic.py tests/test_sources_retrieval_plan.py tests/test_sources_source_resolver.py tests/test_sources_city_county_fallback.py tests/test_sources_query_decomposition.py` -> pass
  - `pytest -q tests/test_sources_coverage_judge.py tests/test_sources_search_assisted_domestic.py tests/test_sources_retrieval_plan.py tests/test_sources_source_resolver.py tests/test_sources_city_county_fallback.py tests/test_sources_query_decomposition.py` -> `80 passed`
  - `python -m ruff check .` -> fails on pre-existing historical `data/tmp` lint debt; unchanged known non-Phase-6 blocker.
  - `pytest -q tests/test_sources_layer.py` -> `8 passed`
  - `pytest -q tests/test_sources_adapters_v1.py` -> `8 passed`
  - `pytest -q tests/test_sources_hardening_step34.py` -> `4 passed`
  - `pytest -q tests/test_sources_evals_step35.py` -> `7 passed`
  - `pytest -q tests/test_sources_router_domestic.py` -> `2 passed`
  - `pytest -q tests/test_sources_profile_adapter.py` -> `4 passed`
  - `pytest -q tests/test_sources_real_domestic_step42.py` -> `4 passed`
  - `pytest -q tests/test_sources_pdf_step43.py` -> `6 passed`
- 2026-04-28: Phase 6 Group3 code-quality validation completed with `PASS_WITH_KNOWN_DEBT`. Fresh local and Group3 checks passed for focused ruff, py_compile, Phase 6 focused pytest (`80 passed`), source regression (`27 passed`), and domestic regression (`16 passed`). Optional repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` lint debt and is not a Phase 6 blocker.
- 2026-04-28: Phase 6 Group3 functional validation completed with `PASS`. Artifact `data/tmp/phase6_multi_round_coverage_functional_validation_20260428.json` has `overall_pass: true`, `9` checks, and `0` failures. It validates Round 1 stop-on-sufficiency, Round 2 required-lane-only gap closure, bounded Round 3 supplemental/fallback behavior, budget metadata and exhaustion gaps, Q03 supplemental-domain rejection, direct-keep refusal, Suzhou Industrial Park `sipac.gov.cn` hint preservation, and `domain_widening_blocked=true` in round traces.
- 2026-04-28: Phase 6 marked completed. No protected downstream contracts, provider/config files, research workflow files, broad source expansion, incompatible domain widening, or direct-keep weakening were authorized or required. Dirty-worktree scope proof remains limited by pre-existing untracked/dirty files.
- 2026-04-28: Phase 7 director gate completed with `Decision: proceed_to_architecture_gate`. The gate confirmed Phase 7 may move only to `invest_agent_architecture_builder` Architecture Gate, not implementation. It refined the real-world validation plan for legacy disabled mode, enabled source acquisition, explicit `source_ids` override, direct-keep preservation, Q03 negative-domain regression, city/park fallback, coverage-gap visibility, `source_quality_summary` compatibility, and run trace semantics. Group2/Group3 assignments and protected-contract stop conditions were recorded. Production code was not changed.
- 2026-04-28: Phase 7 Architecture Gate completed with `Decision: proceed`. The gate found RetrievalPlan-backed coverage metadata can enter research workflow through existing internal source-acquisition fields without changing `ResearchAnalyzeRequest`, `ResearchAnalysisResult`, Source EvidenceBundle/EvidenceItem/Citation schemas, `source_quality_summary`, source routing response shape, task/job semantics, `run` / `run_steps`, provider/config compatibility, direct-keep behavior, explicit `source_ids` override behavior, or legacy `enable_source_acquisition=False`. The approved path keeps `workflow.py` query-decomposition based and surfaces Phase 6 orchestrator metadata through existing `SourceAcquisitionSummary.source_traces[].metadata.response_metadata`, optional compact `notes`, and optional string-only `SourceEvidenceBundle.gaps`. `workflow.py` must not consume `build_retrieval_plan()` directly in the first Phase 7 implementation slice. Approved implementation scope is narrow workflow metadata propagation plus focused tests, with optional internal source-layer helper/eval script only if needed. Production code was not changed by this gate.
- 2026-04-28: Phase 7 Group2 `research_workflow_implementer` slice completed with narrow query-decomposition workflow metadata bridging only. `packages/agents/workflow.py` continues using query decomposition and now aggregates string-only coverage gap markers from `search_assisted_domestic` response metadata into existing `SourceEvidenceBundle.gaps[]` and `SourceAcquisitionSummary.notes[]` (`coverage_gap_count=<n>`, `coverage_gap:<lane_id>:<reason_code>`), while preserving existing `SourceAcquisitionSummary.source_traces[].metadata.response_metadata` payloads (`round_trace`, `coverage_gaps`, `budget_state`, `coverage_sufficient`). No `build_retrieval_plan()` direct workflow wiring, no protected contract changes, no provider/config changes, no source-layer file changes, and no direct-keep/source-ids/disabled-mode behavior changes were introduced.
- 2026-04-28: Phase 7 Group2 validation snapshot:
  - `python -m ruff check packages\\agents\\workflow.py tests\\test_agents_workflow.py tests\\test_research_api.py` -> pass
  - `python -m py_compile packages\\agents\\workflow.py tests\\test_agents_workflow.py tests\\test_research_api.py` -> pass
  - `pytest -q tests\\test_agents_workflow.py tests\\test_research_api.py` -> `13 passed`
  - `pytest -q tests\\test_research_provider_integration.py` -> `9 passed`
  - `pytest -q tests\\test_deepseek_provider.py` -> `2 passed`
  - `python -m ruff check .` -> fails on pre-existing historical `data/tmp` lint debt; unchanged known non-Phase-7 blocker.
- 2026-04-28: Phase 7 Group3 code-quality validation completed with `PASS_WITH_KNOWN_DEBT`. Focused ruff, py_compile, workflow/API pytest (`13 passed`), and research provider/DeepSeek pytest (`11 passed`) passed. Optional repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` lint debt and remains non-blocking for this PLAN.
- 2026-04-28: Phase 7 Group3 functional validation completed with `PASS`. Artifact `data/tmp/phase7_retrieval_plan_workflow_functional_validation_20260428.json` reports `overall_pass: true`, `12/12` checks passed, and `0` failures. It validated disabled legacy path, enabled source-acquisition metadata bridge, compact coverage gap notes, string-only retrieval gaps, explicit `source_ids` override, direct-keep control path, Q03 negative-domain behavior, Suzhou Industrial Park fallback hints, `source_quality_summary` shape, run step semantics, and no direct `build_retrieval_plan()` workflow consumption.
- 2026-04-28: PLAN done condition reached. RetrievalPlan/CoverageLane contracts, optional DeepSeek planner fallback, source resolver leakage controls, national/provincial backbone, city/county fallback, bounded multi-round search, and compatible research workflow consumption are implemented and validated. Optional live status remains non-mandatory; offline deterministic validation is authoritative.

## Next Action

Completed:
- Move this PLAN to `.agent/PLANS/archive/domestic-source-coverage-and-routing-v2.md`.
- Update `.agent/STATUS.md` so no primary active long-running PLAN remains.
- Use `invest_project_summarizer` for post-completion review and recommendations.
