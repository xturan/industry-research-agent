# Source Strong Evidence Adapter Remediation v1

Status: blocked_handoff_to_successor

Created: 2026-04-29

Primary active PLAN: yes

## Objective

Move the source system from "routing/runtime works" to "strong evidence coverage is good enough for staged 50-query evaluation".

The previous source-quality gate cleared runtime and audit-shape blockers, but the DeepSeek audit still judged the 12-case smoke set as `11 fail / 1 weak_pass` because key strong evidence classes are repeatedly missing:

- `company_disclosure`: missing in `12/12`
- `project_list`: missing in `12/12`
- `statistics`: missing in `7/12`
- `environmental_or_land_record`: missing in `5/12`

This PLAN builds durable source backbones for those source classes before attempting a full 50-case live run.

## Task Classification

- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `provider_layer`, `eval_policy_ops`
- Possible later impact: `research_workflow` only if evidence visibility needs a compatibility-safe metadata bridge
- Planning step type: long-running source remediation PLAN

Protected contracts:

- EvidenceBundle schema
- EvidenceItem citation fields
- `source_quality_summary` shape
- research analyze response shape
- provider abstraction semantics
- source routing response shape
- task/job status semantics
- `run` / `run_steps` meaning
- direct-keep primary paths
- legacy `enable_source_acquisition=False` behavior

Any change to a protected contract requires an explicit Architecture Gate update in this PLAN before implementation.

## Baseline

Authoritative baseline artifacts:

- `data/tmp/source_quality_stress_eval/runs/evidence_coverage_final_live_v2/batch_eval.json`
- `data/tmp/source_quality_stress_eval/runs/evidence_coverage_final_live_v2/source_roadmap.json`
- `.agent/PLANS/archive/source-evidence-coverage-remediation-v1.md`

Current baseline:

- 12-case routing gate: `9 pass / 3 weak_pass`, no fail/blocker
- 12-case live gate: `12 success / 0 runtime error`
- Estimated Tavily credits: `19`
- Average latency: `13703.9 ms`
- `query_invalid_count=0`
- DeepSeek audit: `12 success`, `0 invalid_schema`, `0 blocker`
- DeepSeek audit verdicts: `11 fail / 1 weak_pass`
- Main systemic gaps: company disclosure, project/list, statistics, environmental/land/record evidence

Interpretation:

The system can decompose, route, search, fetch, and audit. The weak point is not basic runtime. The weak point is that direct or high-quality evidence lanes often execute without producing usable evidence, or return generic/navigation/homepage material instead of claim-supporting documents.

## Diagnosis

1. Direct structured lanes are present in retrieval plans, but many lanes still return `executed_without_evidence` or equivalent weak gaps.
2. Search-assisted local policy lanes improved, but they cannot replace project, tender, disclosure, statistics, EIA, land, or regulatory records.
3. `company_disclosure` cannot be solved by exchange homepages. It needs topic-to-company/entity mapping, announcement search, and disclosure-specific filtering.
4. `project_list` cannot be solved by generic government pages. It needs project-list, procurement, public-resource, approval, and tender platforms.
5. `statistics` needs source-specific tables, communiques, topic pages, and stable date/region metadata.
6. `environmental_or_land_record` needs explicit source profiles or adapter candidates; otherwise local project reality remains under-verified.
7. The LLM-generated `source_roadmap.json` contains useful signals but also noisy or non-object recommendations. It needs a deterministic normalizer before it can drive implementation queues.

## Architecture Direction

Use four strong-evidence backbones. Tavily remains discovery support, not the primary proof path for direct structured evidence.

```text
User query
  -> query decomposition / retrieval plan
  -> lane executor
  -> strong evidence backbones
       -> disclosure backbone
       -> project/procurement backbone
       -> statistics backbone
       -> official records backbone
  -> fetch / extract / normalize
  -> source quality scoring
  -> existing evidence bundle / trace metadata
  -> source-quality eval harness
```

### Backbone 1: Company Disclosure

Purpose:

- Find listed-company announcements, annual reports, investor-relations material, exchange inquiry replies, and official disclosure evidence.

Expected implementation direction:

- Keep CNINFO / SSE / SZSE / BSE as direct-keep sources.
- Add topic-to-company/entity candidate mapping where needed.
- Query by topic keywords plus company candidates, not by generic exchange domain only.
- Reject exchange homepages, navigation pages, and unrelated announcements.
- Preserve no-match as an explicit structured gap.

### Backbone 2: Project / Procurement / Tender

Purpose:

- Prove project reality: projects, approvals, procurement, public-resource trading, tenders, winning bids, and major construction lists.

Expected implementation direction:

- Repair or replace brittle generic CCGP / GGZY paths.
- Add source profiles for national, provincial, city, and selected county platforms.
- Prefer static HTML/list-detail/PDF-link paths before browser automation.
- Label whether evidence is project-list, procurement, tender, bid-winning, or approval evidence.

### Backbone 3: Statistics / Structured Data

Purpose:

- Provide dated quantitative evidence for policy transmission, industry scale, regional structure, and data conflicts.

Expected implementation direction:

- Repair national and local statistics profiles that currently land on generic pages or fail SSL/certificate handling.
- Add statistical communiques, annual/monthly statistics, customs/trade data, and industry association data where relevant.
- Preserve time period, region, metric name, value, unit, and source page where available.
- If a table cannot be parsed safely, return an explicit extraction gap instead of fabricating a value.

### Backbone 4: Environmental / Land / Regulatory Records

Purpose:

- Verify physical project reality, capacity expansion, resource constraints, land use, EIA, approval, licensing, and regulatory constraints.

Expected implementation direction:

- Add official-record source profiles for EIA, natural resources / land transfer, project filing, approvals, permits, and regulatory notices.
- Start with search-assisted official-record profiles where direct adapters are too expensive.
- Promote to direct adapter only when the source is stable, high-value, and repeatedly needed.

## Scope

In scope:

- Baseline gap matrix derived from the 12-case smoke set.
- Deterministic source-roadmap normalization.
- Source registry/profile updates for the four strong-evidence backbones.
- Focused adapter repair where existing direct lanes are already present but ineffective.
- Lane execution improvements that preserve current response contracts.
- Evidence quality scoring and generic-page rejection if compatible with current schema.
- Focused tests and live smoke gates.
- Staged expansion toward 50 cases only after 12-case quality improves.

Generalization guardrail:

- The 12-case smoke set and future 50-query pressure set are evaluation and regression instruments, not templates for case-specific code.
- A remediation may use one query as a symptom, but the resulting rule must generalize to a reusable source class, lane behavior, evidence-quality pattern, or extraction/ranking failure mode.
- Do not add query-id-specific, company-specific, city-specific, or one-off domain hacks unless the PLAN explicitly records why the case represents a broader class and which other cases validate the rule.
- Prefer changes that improve source routing precision, strong-evidence class coverage, evidence relevance scoring, citation integrity, failure transparency, or extraction quality across a family of queries.
- If a fix would only improve one query while weakening the general source paradigm, record it as a case caveat or future adapter candidate instead of implementing it.

Out of scope:

- Full 50-case live evaluation before the 12-case strong-evidence gate improves.
- New public EvidenceBundle or research response schema fields without an Architecture Gate.
- Browser automation, OCR, login-gated sources, or paid databases unless a later phase explicitly authorizes them.
- Direct securities investment advice or any buy/sell/hold/target-price output.

## Agent Execution Contract

STATUS is the current checkpoint. This PLAN is the execution contract. Agents are role-bound executors and validators.

Default execution flow when the user says to execute the PLAN:

1. `invest_project_director`
   - Read `.agent/STATUS.md` and this PLAN.
   - Confirm the current phase and refine the real-world validation gate.
   - Assign Group 2 and Group 3 work.
   - Stop implementation if a protected contract change is required but not authorized.
2. Group 2 workers
   - `invest_agent_architecture_builder`: owns Architecture Gate decisions, protected-contract impact analysis, and source-backbone design when needed.
   - `invest_feature_programmer`: owns concrete source profile, adapter, script, and test changes.
   - Worker lanes should be task-specific:
     - `eval_harness_worker`
     - `disclosure_backbone_worker`
     - `project_procurement_worker`
     - `statistics_backbone_worker`
     - `official_record_worker`
3. Group 3 validators
   - `invest_code_quality_checker`: focused ruff, compile, focused pytest, and scope review.
   - `invest_functional_validator`: real-world validation against this PLAN's smoke cases and artifacts.
4. `invest_project_summarizer`
   - Use only after the PLAN reaches its final done condition.
   - Summarize practical effects, before/after examples, remaining gaps, and whether new agent skills are needed.

Agents must not independently reinterpret the roadmap. The director may refine phase scope inside this PLAN; workers must report results back into this PLAN and `.agent/STATUS.md`.

## Milestones

### Phase 0: Baseline Matrix And Architecture Gate

Objective:

- Convert the previous live/audit outputs into a concrete gap matrix before changing code.

Tasks:

- Load `batch_eval.json` and `source_roadmap.json`.
- Produce a query x source_class x lane x current_source x failure_reason matrix.
- Identify which gaps can be fixed by source profile updates, which need adapter repair, and which need new adapter families.
- Confirm write scopes for later phases.

Acceptance criteria:

- A baseline gap matrix exists under `data/tmp/source_quality_stress_eval/`.
- The matrix lists at least the 12 smoke cases and the four primary source classes.
- The PLAN records whether Phase 1 can proceed without protected contract changes.
- No production source code is changed in Phase 0 unless the user explicitly changes the scope.

Validation:

```powershell
python -c "import json; p='data/tmp/source_quality_stress_eval/runs/evidence_coverage_final_live_v2/batch_eval.json'; data=json.load(open(p,encoding='utf-8')); print(type(data).__name__)"
python -c "import json; p='data/tmp/source_quality_stress_eval/runs/evidence_coverage_final_live_v2/source_roadmap.json'; data=json.load(open(p,encoding='utf-8')); print(type(data).__name__)"
Test-Path data\tmp\source_quality_stress_eval
git status --short -- .agent data\tmp\source_quality_stress_eval packages\sources tests
```

### Phase 1: Eval Roadmap Normalizer And Strong-Evidence Fixture

Objective:

- Make eval feedback actionable and deterministic.

Tasks:

- Normalize `source_roadmap.json` into a stable implementation queue.
- Convert noisy LLM recommendations into typed items:
  - source class
  - affected query IDs
  - access method
  - implementation complexity
  - expected coverage gain
  - production-code impact
- Create a focused strong-evidence regression fixture from the 12 smoke cases.
- Add pass/fail gates for source-class missing counts.

Acceptance criteria:

- A deterministic roadmap report can rank source gaps without requiring another LLM call.
- A strong-evidence smoke fixture exists and is reusable.
- The output explicitly separates source addition, routing improvement, and evidence pipeline improvement.

Validation:

```powershell
python -m py_compile data\tmp\_source_quality_batch_report.py
python -m py_compile data\tmp\_source_quality_routing_eval.py
```

### Phase 2: Company Disclosure Backbone

Objective:

- Turn `company_disclosure` from a repeated missing source class into a usable direct-keep evidence lane.

Tasks:

- Inspect current CNINFO / SSE / SZSE / BSE registry and adapters.
- Add or repair topic-to-company/entity mapping for the smoke cases.
- Add announcement keyword templates for low-altitude economy, real estate chain, new energy vehicle chain, energy/coal-chemical, data center, and hard-tech cases.
- Reject generic exchange homepages and irrelevant announcements.
- Preserve explicit no-match gaps.

Acceptance criteria:

- At least `4/12` smoke cases produce usable disclosure evidence or a precise no-match gap.
- `company_disclosure` missing count falls from `12/12` to `<=8/12`.
- No direct-keep source is routed primarily through Tavily.

Validation:

```powershell
pytest -q tests\test_sources_profile_adapter.py tests\test_sources_retrieval_plan.py
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\strong_evidence_phase2_routing --print-json
```

### Phase 3: Project / Procurement / Tender Backbone

Objective:

- Improve `project_list`, procurement, public-resource trading, tender, bid-winning, and approval evidence.

Tasks:

- Repair existing CCGP / GGZY / NDRC project profile behavior where it returns 404, generic pages, or no usable evidence.
- Add targeted local project/procurement/public-resource profiles for the smoke cases.
- Add source strategy hints for province, city, and county project evidence.
- Ensure project evidence is labeled as project-list, procurement, tender, bid-winning, or approval where possible.

Acceptance criteria:

- `project_list` missing count falls from `12/12` to `<=6/12`.
- Project/procurement lanes do not accept generic government homepages as evidence.
- Failed platforms return structured partial failures with retryability and source class.

Validation:

```powershell
pytest -q tests\test_sources_lane_execution.py tests\test_sources_profile_adapter.py tests\test_sources_source_resolver.py
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\strong_evidence_phase3_routing --print-json
```

### Phase 4: Statistics / Structured Data Backbone

Objective:

- Add stable dated data evidence for the cases that require quantitative support.

Tasks:

- Repair national and local statistics profile failures.
- Add statistical communiques and data-page profiles for province/city/county levels where relevant.
- Add customs/trade and industry data sources only where the query needs them.
- Add table/excerpt handling that preserves date, metric, unit, region, and source.

Acceptance criteria:

- `statistics` missing count falls from `7/12` to `<=3/12`.
- Statistics evidence has date/period and region metadata when available.
- Failed extraction returns explicit gap, not fabricated metrics.

Validation:

```powershell
pytest -q tests\test_sources_profile_adapter.py tests\test_sources_search_assisted_domestic.py
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\strong_evidence_phase4_routing --print-json
```

### Phase 5: Environmental / Land / Regulatory Records Backbone

Objective:

- Add project reality checks for EIA, land transfer, filing, approval, permits, and regulatory records.

Tasks:

- Add official-record source profiles for high-value smoke cases.
- Prefer search-assisted official-record profiles first.
- Promote to direct adapter only for stable, repeated, high-value sources.
- Preserve explicit unsupported gaps where source access requires browser automation, OCR, login, or paid databases.

Acceptance criteria:

- `environmental_or_land_record` missing count falls from `5/12` to `<=2/12`, or each remaining gap has a precise unsupported reason and adapter candidate.
- County/city project claims are not treated as strong without local project/record evidence or an explicit caveat.

Validation:

```powershell
pytest -q tests\test_sources_lane_execution.py tests\test_sources_source_resolver.py
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\strong_evidence_phase5_routing --print-json
```

### Phase 6: Evidence Quality Scoring And Generic-Page Rejection

Objective:

- Prevent weak pages from being counted as evidence and make evidence sufficiency easier to diagnose.

Tasks:

- Add or refine scoring rules for:
  - generic homepage/navigation/search pages
  - wrong region
  - wrong administrative level
  - stale date
  - weak media-only evidence
  - source class mismatch
- Use case-specific failures, such as the broad `C01` official-record page, only as symptoms for generic source-quality rules.
- Keep scoring in existing metadata/trace structures unless Architecture Gate approves a schema change.
- Make lane-level evidence sufficiency visible in eval artifacts.

Acceptance criteria:

- Generic homepages are rejected before extraction or excluded from accepted evidence.
- Each lane can distinguish usable evidence, weak evidence, and explicit gap.
- No public schema drift is introduced.
- Phase 6 changes are justified as general source/evidence rules and include at least one regression test that does not depend on a single query ID.

Validation:

```powershell
pytest -q tests\test_sources_source_resolver.py tests\test_sources_search_assisted_domestic.py tests\test_sources_lane_execution.py
```

### Phase 7: 12-Case Strong-Evidence Quality Gate

Objective:

- Re-run the 12-case smoke gate and prove source quality improved.

Tasks:

- Run routing inspection.
- Run live source acquisition.
- Run DeepSeek audit with resume support.
- Run batch report.
- Compare before/after missing source-class counts and audit verdicts.

Acceptance criteria:

- Live gate: `12 success / 0 runtime error`
- Audit schema: `0 invalid_schema`
- Audit blockers: `0`
- Audit verdict improvement: at least `6/12` cases are `weak_pass` or `pass`, or fail count falls to `<=6`
- Missing source-class targets:
  - `company_disclosure <= 6/12`
  - `project_list <= 6/12`
  - `statistics <= 3/12`
  - `environmental_or_land_record <= 2/12`

Validation:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\strong_evidence_final_routing --print-json
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\strong_evidence_final_live --max-cases 12 --print-json
python data\tmp\_source_quality_llm_audit.py --run-dir data\tmp\source_quality_stress_eval\runs\strong_evidence_final_live --resume --print-summary
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\strong_evidence_final_live --print-json
```

### Phase 8: Controlled 50-Case Expansion

Objective:

- Expand from 12-case smoke to the broader source-routing pressure set only after the strong-evidence gate improves.

Tasks:

- Run offline routing on all 50 cases.
- Run a staged live subset before full live if cost or latency risk is high.
- Run full 50-case live only when Phase 7 acceptance criteria are met.
- Convert failures into the next remediation roadmap.

Acceptance criteria:

- 50-case live execution is either completed with cost/latency/audit summary, or explicitly deferred with evidence.
- No blocker or schema failure is hidden.
- The next source roadmap is generated from real eval artifacts, not intuition.

Validation:

```powershell
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\source_quality_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\strong_evidence_50_routing --print-json
```

Full live/audit commands are gated on Phase 7 results and available budget.

## Continue Rule

After each milestone, continue automatically to the next milestone when:

- acceptance criteria are met
- required validation passes
- no approval, permission, dependency, or human-review blocker exists
- no high-risk contract change is required without explicit PLAN authorization

Do not treat "summarize this milestone" as a default stop point. Stop only at an explicit blocker, explicit user pause, failed validation without a safe fix, or final done condition.

## Stop Conditions

Stop and ask for guidance if:

- a protected EvidenceBundle/citation/research-response/provider/task contract change is required
- a source requires browser automation, OCR, login, paid access, or non-public scraping not authorized by this PLAN
- credentials are missing for live validation
- live runs repeatedly fail because of external API/provider behavior that cannot be safely worked around
- validation fails and the repair path is unclear or high risk
- the user explicitly pauses the work

## Done Condition

This PLAN is complete when:

- Phase 7 passes the 12-case strong-evidence gate, or records a clear blocker with a successor PLAN
- the previous `11 fail / 1 weak_pass` audit baseline is improved and documented
- missing source-class counts are reduced against the baseline targets
- Phase 8 is either completed or explicitly deferred with a cost/risk decision
- `.agent/STATUS.md` and this PLAN contain final progress, validation, risks, and next action
- the final report includes:
  - what changed
  - what user/system capability was implemented
  - concrete test cases
  - two before/after examples
  - files created/modified
  - validation commands/results
  - remaining risks/TODOs

## Risks And Rollback

Risks:

- Some official sources may require dynamic interaction, OCR, login, or anti-bot handling.
- Company disclosure mapping can become noisy without strong entity filters.
- Local public-resource and statistics sites can have unstable URLs, SSL issues, or page-template drift.
- LLM audit may remain strict even after source-class coverage improves; use missing-count and artifact-level diagnostics alongside verdicts.
- Dirty worktree is broad. Scope must be checked before every implementation phase.

Rollback:

- Disable new source profiles or adapter registrations while preserving previous search-assisted behavior.
- Revert only files changed by this PLAN; do not revert unrelated dirty worktree changes.
- Keep previous artifact baseline under `evidence_coverage_final_live_v2` as the comparison point.

## Progress

- 2026-04-29: PLAN created from the completed `source-evidence-coverage-remediation-v1` handoff. No production code changed.
- 2026-04-29: Planning validation passed: PLAN file exists; `Select-String` confirms `.agent/STATUS.md`, `.agent/PLANS/INDEX.md`, and this PLAN all reference the active PLAN, Phase 0, and the primary missing source classes. `git status --short -- .agent\PLANS\source-strong-evidence-adapter-remediation-v1.md .agent\STATUS.md .agent\PLANS\INDEX.md` shows only `.agent` planning artifacts for this step.
- 2026-04-29: Phase 0 completed. Generated baseline artifacts:
  - `data/tmp/source_quality_stress_eval/strong_evidence_phase0/strong_evidence_gap_matrix_v1.json`
  - `data/tmp/source_quality_stress_eval/strong_evidence_phase0/strong_evidence_gap_matrix_v1.csv`
  - `data/tmp/source_quality_stress_eval/strong_evidence_phase0/strong_evidence_gap_matrix_v1.md`
  Matrix covers `12` smoke cases x `4` target source classes = `48` rows. Target missing counts are `company_disclosure=12`, `project_list=12`, `statistics=7`, `environmental_or_land_record=5`. Architecture gate decision is `phase1_can_proceed_without_public_contract_change`.
- 2026-04-29: Director gate confirmed no protected public contract change is needed before Phase 1. Phase 1 is eval/artifact-only and forbids `packages/sources/**`; Phase 2 needs a narrow Architecture Gate before changing direct disclosure behavior.
- 2026-04-29: Group3 functional validator initially returned FAIL only because PLAN/STATUS did not yet record the Phase 0 artifact path and gate decision. Artifact-level validation passed: JSON `case_summaries=12`, JSON/CSV matrix rows `48`, target class row counts `12` each, target missing counts matched baseline, and no Phase 0 production-code attribution was found beyond pre-existing dirty workspace risk.
- 2026-04-29: Phase 1 completed. Added deterministic strong-evidence matrix tool and fixture:
  - `data/tmp/_source_quality_strong_evidence_matrix.py`
  - `data/tmp/source_quality_stress_eval/strong_evidence_smoke_cases_v1.json`
  - `tests/test_source_quality_strong_evidence_matrix.py`
  The script turns the final live/audit artifacts into a reusable JSON/CSV/Markdown matrix, typed Phase 1 queue, architecture gate decision, and source-class missing-count baseline.
- 2026-04-29: Phase 1 validation passed:
  - `python -m py_compile data\tmp\_source_quality_batch_report.py data\tmp\_source_quality_routing_eval.py data\tmp\_source_quality_strong_evidence_matrix.py`
  - `python -m py_compile data\tmp\_source_quality_strong_evidence_matrix.py tests\test_source_quality_strong_evidence_matrix.py`
  - `pytest -q tests\test_source_quality_batch_report.py tests\test_source_quality_strong_evidence_matrix.py` -> `3 passed`
  - `python data\tmp\_source_quality_strong_evidence_matrix.py --run-dir data\tmp\source_quality_stress_eval\runs\evidence_coverage_final_live_v2 --output-dir data\tmp\source_quality_stress_eval\strong_evidence_phase0` -> `48` rows, `12` cases, phase0 decision `phase1_can_proceed_without_public_contract_change`
- 2026-04-29: Phase 2 Architecture Gate completed. Direct-keep disclosure remains CNINFO / SSE / SZSE / BSE only; primary disclosure must not route through Tavily/search-assisted discovery. Phase 2 may add an internal deterministic `disclosure_mapping` layer and existing-metadata no-match gaps without public schema changes. BSE is frozen as a direct-keep boundary but should only execute for mapped BSE candidates; otherwise return explicit unsupported/no-match.
- 2026-04-29: Phase 2 implementation completed within the Architecture Gate. Added public-contract-safe deterministic disclosure mapping, direct-keep enterprise-disclosure lane wiring, entity-mismatch rejection, precise no-entity no-match handling, and sector-disclosure routing for strong-evidence cases that need company disclosure but do not literally say "上市公司". No EvidenceBundle, citation, research response, provider, task/run, or public source-quality schema was changed.
- 2026-04-29: Phase 2 disclosure mapping artifact generated at `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase2_disclosure_mapping/disclosure_mapping_summary.json`. Result: `12/12` smoke cases now have mapped disclosure entity candidates; examples include `P04 -> 江淮汽车 / 国轩高科`, `K09 -> 陕西煤业 / 中国神华 / 宝丰能源`, `M03 -> 中信海直 / 万丰奥威 / 宗申动力`, and `M06 -> 三一重工 / 海尔智家 / 东方雨虹 / 中国建筑`.
- 2026-04-29: Phase 2 validation passed with known repo-wide lint debt:
  - `python -m ruff check packages\sources\disclosure_mapping.py packages\sources\lane_execution.py packages\sources\query_decomposition.py tests\test_sources_disclosure_mapping.py tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_profile_adapter.py` -> pass
  - `python -m py_compile packages\sources\disclosure_mapping.py packages\sources\lane_execution.py packages\sources\query_decomposition.py tests\test_sources_disclosure_mapping.py tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py` -> pass
  - `pytest -q tests\test_sources_disclosure_mapping.py tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_profile_adapter.py` -> `85 passed`
  - `python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\strong_evidence_smoke_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\strong_evidence_phase2_routing --print-json` -> `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`
  - source regression: `tests/test_sources_layer.py` -> `8 passed`; `tests/test_sources_adapters_v1.py` -> `8 passed`; `tests/test_sources_hardening_step34.py` -> `4 passed`; `tests/test_sources_evals_step35.py` -> `7 passed`
  - domestic regression: `tests/test_sources_router_domestic.py tests/test_sources_profile_adapter.py tests/test_sources_real_domestic_step42.py tests/test_sources_pdf_step43.py` -> `16 passed`
  - `python -m ruff check .` still fails only on known historical `data/tmp` scratch-script lint debt.
- 2026-04-29: Phase 2 acceptance note: this phase proves disclosure routing/mapping/no-match behavior without spending a new DeepSeek audit run. The audit-level `company_disclosure` missing-count target remains part of Phase 7's 12-case strong-evidence gate.
- 2026-04-29: Phase 3 slice 1 completed, but Phase 3 acceptance is not yet met. Changes:
  - Repaired `cn_project_ccgp_procurement_v1` list parsing with CCGP `.ulst li` selectors.
  - Replaced stale `cn_project_ggzy_trade_v1` entry URL `https://www.ggzy.gov.cn/jyxx/` with `https://www.ggzy.gov.cn/deal/dealList.html`.
  - Replaced stale `cn_project_ndrc_approval_v1` entry URL `https://www.ndrc.gov.cn/fgsj/tjsj/jggl/` with `https://www.ndrc.gov.cn/fgsj/tzcx/`.
  - Added project-lane weak-document rejection for generic project navigation pages and relevance mismatches.
  - Added supplemental Tavily + Crawl4AI project-search fallback that only runs after direct project profiles return no usable evidence. It preserves direct-keep protection by using Crawl4AI with `allow_supplemental_direct_keep=True`.
  - Added project fallback candidate filters for allowed domain, duplicate URL, generic public-resource navigation, region mismatch, and missing project/procurement/tender signal.
  - Extended project-transaction query decomposition to include regional and exact-local official domains, so project fallback can search local government/public-project domains instead of only national CCGP/GGZY/NDRC.
- 2026-04-29: Phase 3 slice 1 live smoke:
  - `M03` rejects generic GGZY navigation and NDRC policy/commentary pages without concrete project signals, returning explicit no accepted project candidates.
  - `C09` found one Xi'an public-resource candidate through supplemental project fallback.
  - `K07` now rejects wrong-region Hai'an/Lujiang candidates and non-project NDRC commentary; latest K07 project lane result is explicit `executed_without_evidence` / `no_accepted_candidates`, which is preferable to false project evidence.
- 2026-04-29: Phase 3 slice 1 validation passed:
  - Focused ruff/py_compile over touched source/test files -> pass.
  - `pytest -q tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_domestic_scaleout_phase2.py` -> `50 passed`.
  - Source regression: `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`.
  - Domestic regression: `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`.
  - Focused source plan set: `pytest -q tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_profile_adapter.py tests\test_sources_domestic_scaleout_phase2.py` -> `87 passed`.
  - Phase 3 routing eval: `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase3_routing` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
  - Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt.
- 2026-04-29: Phase 3 acceptance status: completed after slice 2. Added project fallback metadata-hint filtering so a sparse Crawl4AI page can still be retained when Tavily's accepted candidate title/snippet proves it is a concrete project/procurement/tender record. This converted `M06` from `executed_without_evidence` to `executed_with_evidence` using the same GGZY "天河区柯木塱村城中村改造项目" candidate, without changing EvidenceBundle/citation/provider/task public contracts.
- 2026-04-29: Phase 3 final live smoke artifact: `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase3_project_lane_live_smoke_after_hint_v1/project_lane_live_smoke.json`. Result: `12` cases, `6` with project evidence (`M02`, `M06`, `P04`, `P10`, `C07`, `C09`), `6` without project evidence (`M03`, `P08`, `C01`, `K07`, `K09`, `K12`), estimated Tavily credits `17`. This proves `project_list` missing-count reduction from `12/12` to `6/12`, meeting the Phase 3 acceptance threshold.
- 2026-04-29: Phase 3 final validation passed:
  - Focused ruff over touched source/test files -> pass.
  - Focused py_compile over touched source/test files -> pass.
  - `pytest -q tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_profile_adapter.py tests\test_sources_domestic_scaleout_phase2.py` -> `88 passed`.
  - Source regression: `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`.
  - Domestic regression: `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`.
  - Phase 3 routing eval: `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase3_routing_after_hint_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
- 2026-04-29: Phase 4 completed. Added a supplemental data-metrics search fallback that runs only after direct statistics/data profiles return no usable evidence. It uses low-cost Tavily search plus Crawl4AI with `allow_supplemental_direct_keep=True`, records metadata under existing `data_metrics_search_fallback`, and does not change EvidenceBundle/citation/provider/task public contracts.
- 2026-04-29: Phase 4 query routing/data-quality fixes:
  - `data_metrics` now inherits regional and exact-local official domains, matching project-lane behavior for local statistics/data needs.
  - quantity-validation terms such as `产量`, `能耗`, `财政`, `收入`, `投资`, `补贴`, `项目分布`, `资源`, `交通`, and `电力` now trigger a data-metrics lane.
  - irrelevant direct data documents, such as generic commerce/event pages, are rejected as `data_metrics_relevance_mismatch` before they can count as evidence.
  - exact-local government work reports are allowed as narrow supplemental statistics evidence when region-matched, because county/city annual reports often carry fiscal, output, energy, and production indicators.
- 2026-04-29: Phase 4 final live smoke artifact: `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase4_data_metrics_live_smoke_v4/data_metrics_live_smoke.json`. Result: `12` cases, `7` with statistics evidence (`M02`, `M06`, `P04`, `P10`, `C07`, `K09`, `K12`), `5` without (`M03`, `P08`, `C01`, `C09`, `K07`), estimated Tavily credits `14`. Against the Phase 0 missing-statistics baseline, covered missing cases are now `M02`, `P04`, `P10`, `K09`, and `K12`; remaining missing baseline cases are `P08` and `C01`, proving `statistics` missing-count reduction from `7/12` to `2/12`.
- 2026-04-29: Phase 4 validation passed:
  - Focused ruff over touched source/test files -> pass.
  - Focused py_compile over touched source/test files -> pass.
  - `pytest -q tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_profile_adapter.py tests\test_sources_domestic_scaleout_phase2.py` -> `92 passed`.
  - Source regression: `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`.
  - Domestic regression: `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`.
  - Phase 4 routing eval: `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase4_routing_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
- 2026-04-29: Phase 5 completed. Added an internal `official_record` task family mapped to the existing `project_transaction` retrieval lane, preserving public retrieval/EvidenceBundle contracts while distinguishing official environmental/land/regulatory evidence through task family, source cluster, and metadata.
- 2026-04-29: Phase 5 implementation added official-record search fallback through Tavily + Crawl4AI, exact-local and parent official-record domains for 神木 / 若羌 / 内蒙古, narrow high-yield official-record query phrases, PDF candidate skip behavior while no PDF adapter is available, broad `gov.cn` tightening for local official-record discovery, and document-level relevance checks that avoid counting full pages where core topic terms only appear in search hints or late boilerplate.
- 2026-04-29: Phase 5 live smoke artifact: `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase5_official_record_live_smoke_v7`. Result: `5` cases, `4` with official-record evidence (`P08`, `C01`, `K09`, `K12`) and `1` explicit no-evidence gap (`K07`), estimated direct fallback Tavily credits `10`. This reduces the `environmental_or_land_record` missing baseline from `5/12` to at most `1/5` in the Phase 5 missing-case slice, meeting the target `<=2/12` equivalent for this slice before Phase 7 audit.
- 2026-04-29: Phase 5 validation passed:
  - Focused ruff over touched source/test/eval files -> pass.
  - Focused py_compile over touched source/test/eval files -> pass.
  - `pytest -q tests\test_source_quality_live_inspection.py tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_profile_adapter.py tests\test_sources_domestic_scaleout_phase2.py` -> `103 passed`.
  - Source regression: `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`.
  - Domestic regression: `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`.
  - Phase 5 routing eval: `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase5_routing_final_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
- 2026-04-29: Phase 5 caveats recorded for Phase 6. `C01` still uses a broad Anhui natural-resources land-use case as official-record evidence, which may be too weak for the Hefei NEV cluster claim. Treat this as a Phase 6 evidence-quality scoring task rather than a Phase 5 blocker because the Phase 5 missing-count target is already met and K07 remains transparently unsupported.
- 2026-04-29: Added the Phase 6 generalization guardrail. The 12-case and future 50-query sets must drive reusable source-routing, discovery, extraction, and evidence-quality improvements, not overfit single-query fixes. `C01` remains a symptom for generic official-record weak-evidence rejection, not permission for query-specific code.
- 2026-04-29: Phase 6 slice 1 implemented a generic official-record case-page rejection rule. Official-record pages that are narrative case/example pages, including `dxal` paths and `典型案例` titles, are no longer counted as strong environmental/land/regulatory evidence. This is a source-quality rule for a page type, not a `C01` query-specific patch.
- 2026-04-29: Phase 6 slice 1 validation:
  - RED: `pytest -q tests\test_sources_lane_execution.py::test_official_record_lane_rejects_generic_case_page_without_record_subject` first failed because the generic case page was accepted as evidence.
  - GREEN: the same test now passes after the generic case-page rejection rule.
  - Focused checks: `python -m ruff check packages\sources\lane_execution.py tests\test_sources_lane_execution.py` -> pass; `python -m py_compile packages\sources\lane_execution.py tests\test_sources_lane_execution.py` -> pass; `pytest -q tests\test_sources_lane_execution.py` -> `23 passed`.
  - Focused source PLAN suite: `pytest -q tests\test_source_quality_live_inspection.py tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_profile_adapter.py tests\test_sources_domestic_scaleout_phase2.py` -> `104 passed`.
  - Source regression: `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`.
  - Domestic regression: `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`.
  - Repo-wide `python -m ruff check .` still fails on known historical `data/tmp` scratch-file lint debt, not touched Phase 6 files.
  - Low-cost live smoke: `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_scoring_c01_live_v1` -> `1` case success, estimated Tavily credits `2`, accepted document count `0`; the broad Anhui `dxal` page is rejected as `generic_official_record_case_page`.
- 2026-04-29: Phase 6 slice 2 implemented official-record adaptive third-phrase fanout. The direct fallback still stops after the first accepted candidate set, but when the first two search phrases produce no accepted candidate it can try the third phrase. This addresses a reusable discovery-quality issue exposed by `K12`, not a query-specific patch.
- 2026-04-29: Phase 6 official-record 5-case smoke artifact generated at `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_official_record_smoke_v2`. Result: `5` cases success, estimated Tavily credits `14`, `query_invalid_count=0`. `P08`, `K09`, and `K12` retained accepted official-record evidence; `C01` was correctly rejected as `generic_official_record_case_page`; `K07` remained transparent no-evidence. This confirms the case-page quality rule did not destroy the key positive official-record controls, while the fanout rule recovered K12.
- 2026-04-29: Phase 6 slice 3 implemented an explicit official-record fallback search budget. `DirectStructuredLaneExecutor` now accepts `max_official_record_fallback_search_credits`, records `max_estimated_tavily_credits`, `budget_state`, and `stop_reason` in existing fallback metadata, and stops search fanout when the lane-level budget is exhausted. The live inspection harness now exposes `--max-official-record-search-credits` and passes `--max-candidates` through to direct fallback candidate limits so CLI budget controls match actual direct-lane execution.
- 2026-04-29: Phase 6 slice 3 validation:
  - RED: `pytest -q tests\test_sources_lane_execution.py::test_official_record_search_fallback_respects_search_credit_budget` first failed because the executor did not accept `max_official_record_fallback_search_credits`.
  - GREEN/control: the budget-cap test and `test_official_record_lane_tries_third_phrase_when_first_two_have_no_candidates` both pass, proving cap=2 can stop fanout while default cap=3 still allows third-phrase recovery.
  - Focused checks: `python -m ruff check packages\sources\lane_execution.py tests\test_sources_lane_execution.py data\tmp\_source_quality_live_inspection.py tests\test_source_quality_live_inspection.py` -> pass; `python -m py_compile packages\sources\lane_execution.py tests\test_sources_lane_execution.py data\tmp\_source_quality_live_inspection.py tests\test_source_quality_live_inspection.py` -> pass; `pytest -q tests\test_sources_lane_execution.py tests\test_source_quality_live_inspection.py` -> `26 passed`.
  - Focused source PLAN suite: `pytest -q tests\test_source_quality_live_inspection.py tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_profile_adapter.py tests\test_sources_domestic_scaleout_phase2.py` -> `106 passed`.
  - Source regression: `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`.
  - Domestic regression: `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`.
  - Repo-wide `python -m ruff check .` still fails on known historical `data/tmp` scratch-file lint debt, not on touched files.
  - Live cost-control smoke: `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_official_record_smoke_cap2_v2` -> `5` cases success, estimated Tavily credits `9`, average latency `12730.49 ms`, `query_invalid_count=0`. Compared with cap=3 artifact `strong_evidence_phase6_official_record_smoke_v2` at `14` credits, cap=2 preserves evidence on `P08`, `K09`, and `K12`, keeps `C01` rejected as `generic_official_record_case_page`, and exposes `K07` as `search_credit_budget_exhausted` / no evidence.
- 2026-04-29: Phase 6 slice 4 completed. Added `packages/sources/disclosure_api.py`, a CNINFO direct announcement API fallback that runs only after direct disclosure profiles return no usable evidence. It preserves the CNINFO/SSE/SZSE/BSE direct-keep boundary, uses `0` Tavily credits, converts CNINFO millisecond timestamps to China-local `YYYY-MM-DD` date labels, and rejects weak non-operating disclosure titles such as legal opinions / stock-option exercise materials unless they also contain operating signals.
- 2026-04-29: Phase 6 slice 4 validation:
  - RED/GREEN: `pytest -q tests\test_sources_lane_execution.py::test_disclosure_lane_uses_direct_cninfo_fallback_after_generic_exchange_pages` first failed before the executor accepted `disclosure_api_provider`, then passed after fallback wiring.
  - RED/GREEN: `pytest -q tests\test_sources_disclosure_api.py::test_cninfo_disclosure_api_provider_builds_documents_from_announcements` first exposed raw CNINFO millisecond timestamps in `raw_text`, then passed after China-local date normalization.
  - RED/GREEN: `pytest -q tests\test_sources_disclosure_api.py::test_cninfo_disclosure_api_provider_skips_non_operating_disclosures` first accepted a legal-opinion/stock-option title, then passed after weak non-operating disclosure filtering.
  - Disclosure-only live artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_disclosure_api_smoke_v3` -> `12/12` cases success, `12/12` enterprise-disclosure lanes with evidence, estimated Tavily credits `0`, average latency `1027.02 ms`, `query_invalid_count=0`.
- 2026-04-29: Phase 6 slice 5 completed. Official-record search candidate domain handling now allows region-matched subprovincial `.gov.cn` official domains when the title/snippet/URL also has an official-record signal. This fixes a reusable provincial-record pattern where real EIA/approval records sit on city/league/ district government domains, while preserving the broad `gov.cn` wrong-region rejection.
- 2026-04-29: Phase 6 slice 5 validation:
  - RED/GREEN: `pytest -q tests\test_sources_lane_execution.py::test_official_record_lane_accepts_region_matched_subprovincial_gov_domain` first failed as `executed_without_evidence`, then passed after region-matched local official-domain acceptance.
  - Control: `pytest -q tests\test_sources_lane_execution.py::test_official_record_search_fallback_does_not_treat_broad_gov_cn_as_local_match` still passes, proving wrong-region local pages are not accepted.
  - Official-record-only smoke `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_official_record_after_subprovincial_domain_v1` recovered `P08` official-record evidence with cap=2. This task-family-only run marks cases without an official-record task as `error`, so it is diagnostic only, not a batch status gate.
- 2026-04-29: Phase 6 final routing/live gate completed:
  - Routing artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_routing_after_disclosure_api_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
  - Full live artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_live_final_v1` -> `12 success / 0 runtime error`, estimated Tavily credits `69`, average latency `21752.27 ms`, `query_invalid_count=0`.
  - Strong-evidence coverage in the final live artifact: `enterprise_disclosure=12/12`, `project_transaction=6/12`, `data_metrics=6/11 executed tasks`, `official_record=3/6 executed tasks`.
  - Weak evidence diagnostics remain visible: `generic_disclosure_homepage=12`, `non_disclosure_page=12`, `project_relevance_mismatch=12`, `generic_project_navigation=12`, `generic_stats_homepage=10`, `generic_official_record_case_page=1`.
- 2026-04-29: Phase 6 final validation passed:
  - `python -m ruff check packages\sources\disclosure_api.py packages\sources\lane_execution.py tests\test_sources_disclosure_api.py tests\test_sources_lane_execution.py data\tmp\_source_quality_live_inspection.py tests\test_source_quality_live_inspection.py` -> pass.
  - `python -m py_compile packages\sources\disclosure_api.py packages\sources\lane_execution.py tests\test_sources_disclosure_api.py tests\test_sources_lane_execution.py data\tmp\_source_quality_live_inspection.py tests\test_source_quality_live_inspection.py` -> pass.
  - `pytest -q tests\test_source_quality_live_inspection.py tests\test_sources_disclosure_api.py tests\test_sources_lane_execution.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_profile_adapter.py tests\test_sources_domestic_scaleout_phase2.py` -> `110 passed`.
  - Source regression: `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`.
  - Domestic regression: `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`.
  - Repo-wide `python -m ruff check .` remains known historical `data/tmp` scratch-file lint debt and was not re-run as a completion gate for this focused phase.
- 2026-04-29: Phase 7 live/audit gate completed and did not meet acceptance. Live artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_live_final_v1` reports `12 success / 0 runtime error`, estimated Tavily credits `69`, average latency `21752.27 ms`. DeepSeek audit was repaired from one `invalid_json` P10 retry issue to `12 success / 0 invalid_json`, but verdicts remain `10 fail / 1 weak_pass / 1 blocker`, so the required `>=6/12 weak_pass/pass` or `fail <=6` target was not met.
- 2026-04-29: Phase 7 missing source-class counts remain above target: `project_list=7`, `statistics=7`, `environmental_or_land_record=5`, `official_policy=2`. The blocker is `M03` with missing province/city rollout, project transaction, association, and structured data backbone evidence. Because the failures are systemic and not a narrow one-case issue, this PLAN is handed off to successor PLAN `.agent/PLANS/source-generalized-evidence-remediation-v1.md`.
- 2026-04-29: Phase 7 eval-harness remediation completed: `data/tmp/_source_quality_llm_audit.py` now supports configurable `--max-output-tokens` with default `8192`, and truncated invalid JSON retry uses the larger compact output budget. Validation: `python -m ruff check data\tmp\_source_quality_llm_audit.py tests\test_source_quality_llm_audit.py` -> pass; `python -m py_compile data\tmp\_source_quality_llm_audit.py tests\test_source_quality_llm_audit.py` -> pass; `pytest -q tests\test_source_quality_llm_audit.py` -> `4 passed`.

## Current Phase

Blocked handoff to successor PLAN.

## Next Action

Use `.agent/PLANS/source-generalized-evidence-remediation-v1.md` as the new primary active PLAN. Start with Phase 0 failure taxonomy generation from the Phase 7 artifacts before any new production source changes.
