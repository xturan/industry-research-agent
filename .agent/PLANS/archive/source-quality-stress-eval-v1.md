# Plan: Source Quality Stress Eval v1

Status: blocked_pending_remediation_plan
Priority: high
Owner: codex/human
Scope: routing/discovery/extraction inspection, LLM-assisted source quality audit, source roadmap generation
Created: 2026-04-28
Last Updated: 2026-04-28

## Objective

Build a repeatable source-routing stress evaluation loop for the domestic source system using a curated 50-query challenge set.

The first implementation focuses on:

```text
routing + discovery + extraction inspection
```

It must evaluate whether the system:

- decomposes each query into the correct coverage lanes
- routes to appropriate source classes and administrative levels
- discovers relevant URLs through Tavily
- extracts useful text through Crawl4AI
- exposes coverage gaps and source failures transparently
- produces structured improvement recommendations for future source expansion

This PLAN is not a full research-answer evaluation plan yet. Full answer quality, memo synthesis, and final narrative evaluation are deferred until source acquisition quality is measurable.

## Design Decision: LLM Evaluator Provider

Decision: use DeepSeek API as the first primary LLM evaluator, with deterministic hard gates before LLM scoring.

Default evaluator model decision, verified against official DeepSeek API docs on 2026-04-28:

- Default highest-quality evaluator model: `deepseek-v4-pro`
- Mode: thinking enabled
- Reasoning effort: `max` for final smoke/full audit runs; `high` is acceptable for cheap development probes
- Fallback/low-cost model: `deepseek-v4-flash`
- Do not use `deepseek-chat` or `deepseek-reasoner` as new defaults. Official docs state these aliases will be deprecated on 2026-07-24 and currently map to `deepseek-v4-flash` non-thinking/thinking compatibility modes.
- JSON audit calls must use `response_format={"type": "json_object"}` and include the word `json` plus an example JSON schema in the prompt.

Rationale:

- DeepSeek is already present in the repository provider direction and `Domestic Source Coverage and Routing v2` added optional DeepSeek planning with deterministic fallback.
- Batch evaluation of 50 cases needs repeatable API calls, JSON artifacts, retry behavior, and cost tracking.
- Codex local/session evaluation is useful for design review and human-in-the-loop interpretation, but it is not the right first execution engine for batch eval artifacts because it is session-bound and harder to replay from scripts.
- Deterministic code must own hard failure gates; LLM output must not be the only acceptance authority.

Operating model:

```text
deterministic gates
  -> DeepSeek source-quality audit
  -> batch aggregation
  -> source roadmap
  -> human/Codex review
  -> future remediation PLAN if production source changes are needed
```

Fallback:

- If `DEEPSEEK_API_KEY` is missing, the eval harness must still run deterministic routing/discovery/extraction inspection and mark LLM audit as `skipped_missing_api_key`.
- Missing DeepSeek credentials must not block smoke routing tests.
- Missing Tavily credentials blocks live discovery/extraction inspection, but routing-only mode must still run.

## Task Classification

Primary area: `eval_policy_ops`

Secondary areas:

- `source_layer`
- `domestic_source_collectors`
- `provider_layer`
- `research_workflow`

Planning-only current step:

- This PLAN creation does not authorize production code changes.
- First implementation slices should prefer `data/tmp`, `.agent`, `docs`, and `tests` artifacts.
- Any required changes under `packages/sources/**`, `packages/agents/workflow.py`, provider abstractions, API response schemas, or EvidenceBundle contracts must be marked as a blocker and handled by a separate remediation PLAN or explicit Architecture Gate.

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

## Scope

In scope:

- 50-query source-routing stress set
- 10 to 12 query smoke subset
- routing-only inspection
- Tavily discovery inspection
- Crawl4AI extraction inspection
- deterministic hard gates
- DeepSeek LLM evaluator prompt and JSON output schema
- per-query source gap analysis
- batch source roadmap generation
- source profile / adapter / routing improvement recommendations
- cost and latency reporting
- artifacts under `data/tmp`
- PLAN/status updates

Out of scope for first pass:

- final research answer quality evaluation
- automatic production source code modification
- automatic creation of source adapters
- CI gating for all 50 live cases
- browser automation, OCR, or login-gated sources
- direct securities investment recommendation generation
- changing downstream EvidenceBundle or API response shapes

## API Key And Runtime Configuration

Credentials may be loaded from a local project `.env` file for repeated local evaluation runs. The `.env` file must stay gitignored and must never be copied into PLAN, STATUS, scripts, artifacts, `.env.example`, or run logs.

Secret handling rule:

- real local API keys may exist only in `E:\invest_agent\.env` or ephemeral process environment variables
- PLAN/STATUS/scripts/artifacts must store only placeholders, key presence booleans, or provider/model names
- eval scripts may auto-load `.env`, but must not print secret values
- if a script needs to record credentials state, record only `*_api_key_present=true|false`

PowerShell placeholders:

```powershell
cd E:\invest_agent

$env:TAVILY_API_KEY="<YOUR_TAVILY_API_KEY>"
$env:DEEPSEEK_API_KEY="<YOUR_DEEPSEEK_API_KEY>"
$env:LLM_PROVIDER="deepseek"
$env:DEEPSEEK_RESEARCH_MODEL="deepseek-v4-pro"
$env:SOURCE_EVAL_LLM_PROVIDER="deepseek"
$env:SOURCE_EVAL_LLM_MODEL="deepseek-v4-pro"
$env:SOURCE_EVAL_LLM_THINKING="enabled"
$env:SOURCE_EVAL_LLM_REASONING_EFFORT="max"
$env:SOURCE_EVAL_MODE="routing_discovery_extraction"
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```


Expected fallback behavior:

| Missing key | Expected behavior |
|---|---|
| `TAVILY_API_KEY` missing | routing-only can run; live discovery/extraction skipped with structured reason |
| `DEEPSEEK_API_KEY` missing | deterministic gates can run; LLM audit skipped with structured reason |
| both missing | offline routing-only smoke can run |

Local persistent setup:

```text
E:\invest_agent\.env
```

This file is intentionally local-only and gitignored. It may contain:

```text
TAVILY_API_KEY=<YOUR_TAVILY_API_KEY>
DEEPSEEK_API_KEY=<YOUR_DEEPSEEK_API_KEY>
SOURCE_EVAL_LLM_PROVIDER=deepseek
SOURCE_EVAL_LLM_MODEL=deepseek-v4-pro
SOURCE_EVAL_LLM_THINKING=enabled
SOURCE_EVAL_LLM_REASONING_EFFORT=max
PYTHONIOENCODING=utf-8
PYTHONUTF8=1
```

## Architecture Direction

Target first-pass pipeline:

```text
source_quality_cases.json
  -> routing_only runner
     -> decompose_query / RetrievalPlan inspection
     -> deterministic routing gates
  -> discovery runner
     -> Tavily Search
     -> candidate decisions
  -> extraction runner
     -> Crawl4AI
     -> raw_text / normalized_sections excerpts
  -> deterministic source-quality gates
  -> DeepSeek LLM audit
  -> per_query_eval.json
  -> batch_eval.json
  -> source_roadmap.json
```

Layering:

| Layer | Purpose | External cost |
|---|---|---|
| `routing_only` | inspect decomposition, lanes, domains, direct-keep behavior | none |
| `discovery_only` | inspect Tavily candidate URL quality | Tavily credits |
| `extraction_inspection` | inspect Crawl4AI fetched content | Tavily credits plus crawl runtime |
| `llm_audit` | judge relevance, sufficiency, source gaps, roadmap | DeepSeek tokens |
| `full_research_eval` | future answer quality evaluation | deferred |

## Query Case Schema

Each case should be represented as structured JSON, not only as text.

```json
{
  "id": "P04",
  "level": "province",
  "query": "安徽省新能源汽车产业链是否仍依赖合肥龙头带动，还是已经形成全省多地协同？请从整车、电池、零部件、财政补贴和项目分布验证。",
  "stress_targets": [
    "regional_granularity",
    "source_routing",
    "project_evidence",
    "company_disclosure"
  ],
  "expected_lanes": [
    "provincial_policy_rollout",
    "statistics_or_industry_data",
    "project_transaction",
    "enterprise_disclosure"
  ],
  "expected_source_classes": [
    "official_policy",
    "statistics",
    "project_list",
    "company_disclosure"
  ],
  "forbidden_patterns": [
    "只用国家新能源汽车政策回答",
    "只用媒体报道代替项目/统计/公告",
    "输出买入/卖出/持有建议"
  ],
  "minimum_acceptance": {
    "strong_evidence_classes_min": 2,
    "citation_count_min": 3,
    "must_expose_coverage_gaps": true
  }
}
```

## Fixed Source Class Taxonomy

The evaluator must use fixed source classes to keep roadmap output stable.

| Source class | Meaning |
|---|---|
| `official_policy` | central/province/city/county policy documents, plans, notices, implementation plans |
| `statistics` | NBS, local statistics bureaus, statistical communiques, sector statistics |
| `project_list` | key project lists, major project starts, filings, investment project pages |
| `tender_or_procurement` | government procurement, public resource trading, tenders, awards |
| `company_disclosure` | listed company announcements, annual reports, exchange filings, IR |
| `environmental_or_land_record` | EIA, energy assessment, land transfer, natural resources notices |
| `regulatory_record` | approvals, licenses, penalties, regulatory notices, access permits |
| `industry_association` | association data, prices, output, installed capacity, sales |
| `trade_data` | customs, commerce, ports, logistics, cross-border e-commerce |
| `local_government` | local government, DRC, industry bureau, commerce bureau, park management committee |
| `media_context` | official media or industry media as context only |
| `third_party_context` | research institutions or non-official data platforms as weak auxiliary context |

## Deterministic Hard Gates

Hard gates must run before LLM audit.

Blocker gates:

- direct investment advice appears in output artifacts where an answer is evaluated
- direct-keep lane is routed through Tavily/Crawl4AI as primary execution
- city/county query is answered with only national/province evidence and no gap
- source trace reports fetch/extract failure but final status hides it
- critical claims lack citation in future full-answer mode

Fail gates:

- expected administrative level is missing from discovered/extracted sources
- accepted URL domain is outside lane allowlist
- source class required by case is absent without a coverage gap
- extraction returns mostly navigation text and no useful body content
- `coverage_sufficient=false` but no structured gap is emitted

Warning gates:

- high Tavily credit use
- high latency
- source is relevant but stale
- weak source class overused
- candidate limit may have prematurely hidden better sources

## LLM Audit Output Schema

DeepSeek evaluator should output strict JSON per query.

```json
{
  "query_id": "P04",
  "overall_score": 0,
  "verdict": "pass | weak_pass | fail | blocker",
  "dimension_scores": {
    "intent_decomposition": 0,
    "source_coverage": 0,
    "evidence_sufficiency": 0,
    "citation_integrity": 0,
    "regional_granularity": 0,
    "temporal_data_consistency": 0,
    "compliance_risk_control": 0,
    "operational_diagnostics": 0
  },
  "covered_source_classes": [],
  "missing_source_classes": [],
  "source_gap_analysis": {
    "missing_critical_sources": [],
    "overused_weak_sources": [],
    "source_level_mismatch": {
      "expected_level": "macro | province | city | county",
      "actual_sources_used": [],
      "problem": "",
      "severity": "low | medium | high | blocker"
    }
  },
  "recommended_sources_to_add": [],
  "source_routing_improvement": [],
  "evidence_pipeline_improvement": [],
  "implementation_recommendation": {
    "needs_production_code_change": false,
    "can_be_fixed_in_eval_prompt_or_docs": true,
    "can_be_fixed_by_source_profile_update": false,
    "requires_new_adapter": false,
    "requires_new_source_registry_entry": false,
    "requires_reopening_plan": false,
    "recommended_next_step": "",
    "blocker_reason": null
  }
}
```

LLM audit rules:

- Do not answer the original research query.
- Judge only the observed routing/discovery/extraction artifacts.
- Do not invent source evidence not present in artifacts.
- If recommending sources, include source class, administrative level, access method, affected query IDs, complexity, cost impact, and whether production code changes are needed.
- Mark `requires_reopening_plan=true` for any recommendation that modifies `packages/sources/**`, workflow behavior, provider abstraction, or protected contracts.

## Batch Output Schema

Batch output must produce a roadmap, not only scores.

Required artifacts:

```text
data/tmp/source_quality_stress_eval/
  source_quality_cases_v1.json
  smoke_cases_v1.json
  runs/<timestamp>/
    per_query/
      <query_id>.json
    batch_eval.json
    source_roadmap.json
    raw_traces/
    crawl4ai_excerpts/
```

`source_roadmap.json` must include:

- `p0_sources_to_add_or_fix`
- `p1_sources_to_add_or_fix`
- `p2_sources_to_add_or_fix`
- `routing_roadmap`
- `source_profile_updates`
- `adapter_candidates`
- `regression_test_plan`
- `requires_reopening_plan_items`

## Smoke Query Set

Use a 10 to 12 case smoke set before running all 50 cases.

Initial recommended smoke set:

| ID | Reason |
|---|---|
| `M02` | macro policy-to-project conversion for East Data West Computing / data centers |
| `M03` | low-altitude economy policy-to-project and regulator prerequisites |
| `M06` | macro policy transmission and data conflict |
| `P04` | Anhui NEV province-level industrial chain and project/company evidence |
| `P08` | Inner Mongolia green power / hydrogen / coal chemical resource-to-project logic |
| `P10` | Hainan policy dividend versus real industrial investment |
| `C01` | Hefei city cluster and supply-chain self-circulation |
| `C07` | Changzhou battery/PV capacity concentration risk |
| `C09` | Xi'an commercial aerospace and hard-tech order loop |
| `K07` | Feixi county NEV spillover versus independent project cluster |
| `K09` | Shenmu coal/coal-chemical expansion under dual-carbon constraints |
| `K12` | Ruoqiang sparse-source lithium/potash/new-energy industrialization transparency |

## Milestones

### Phase 0: Architecture Gate and Case Schema Freeze

Objective:

- Freeze the eval architecture, provider choice, source class taxonomy, case schema, and artifact layout before implementation.

Tasks:

- Confirm DeepSeek-as-evaluator with deterministic gates first.
- Freeze `source_quality_cases_v1.json` schema.
- Freeze smoke set IDs.
- Define exact hard gates.
- Define LLM audit prompt boundary.
- Define when a result can create a remediation PLAN.

Acceptance criteria:

- PLAN records provider decision and fallback behavior.
- Source class taxonomy is fixed.
- JSON schema is concrete enough to implement.
- No production code change is required for Phase 0.

Validation:

```powershell
Select-String -Path .agent\PLANS\source-quality-stress-eval-v1.md -Pattern "Decision: use DeepSeek API","source_quality_cases_v1","Deterministic Hard Gates","Smoke Query Set"
```

### Phase 1: Case Set and Offline Routing Harness

Objective:

- Create the 50-query case file and a routing-only harness that does not require external credentials.

Allowed write scope:

- `data/tmp/source_quality_stress_eval/source_quality_cases_v1.json`
- `data/tmp/source_quality_stress_eval/smoke_cases_v1.json`
- `data/tmp/_source_quality_routing_eval.py`
- optional docs under `docs/`
- focused tests if the harness is moved out of `data/tmp`

Tasks:

- Convert the 50 user-provided queries into structured case records.
- Add expected lanes/source classes/forbidden patterns/minimum acceptance.
- Run routing-only inspection through existing query decomposition/RetrievalPlan behavior.
- Emit per-case routing artifacts.

Acceptance criteria:

- All smoke cases run without `TAVILY_API_KEY` or `DEEPSEEK_API_KEY`.
- Q03-style negative-domain behavior remains visible.
- Direct-keep cases are identified as direct-keep controls, not executed through search-assisted primary path.

Validation:

```powershell
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --print-json
```

### Phase 2: Tavily Discovery and Crawl4AI Extraction Inspection

Objective:

- Run controlled live discovery/extraction for smoke cases and record source trace artifacts.

Allowed write scope:

- `data/tmp/_source_quality_live_inspection.py`
- `data/tmp/source_quality_stress_eval/runs/**`
- possible narrow improvements to existing tmp inspection script only

Tasks:

- Reuse existing Tavily/Crawl4AI source-assisted path.
- Run bounded `max_rounds`, `max_candidates`, and per-case cost limits.
- Record accepted/rejected candidates, rejection reasons, raw text excerpts, normalized sections, coverage gaps, and budget state.

Acceptance criteria:

- Smoke cases produce per-query artifacts.
- Failures are structured and do not crash the batch.
- Cost and latency are recorded.

Validation:

```powershell
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\manual_smoke
```

### Phase 3: DeepSeek LLM Audit Layer

Objective:

- Add optional DeepSeek evaluator that scores observed artifacts and produces source improvement recommendations.
- Use `deepseek-v4-pro` with thinking enabled and `reasoning_effort=max` for quality-critical audit runs.

Allowed write scope:

- `data/tmp/_source_quality_llm_audit.py`
- `data/tmp/source_quality_stress_eval/prompts/source_quality_eval_prompt.md`
- `data/tmp/source_quality_stress_eval/runs/**`

Tasks:

- Add strict JSON evaluator prompt.
- Include deterministic gate results in LLM input.
- Validate LLM output schema.
- Skip gracefully if `DEEPSEEK_API_KEY` is missing.
- Record model name, thinking mode, reasoning effort, response format, token usage, and finish reason in audit artifacts.
- Do not store private `reasoning_content` in repository artifacts or run logs.

Acceptance criteria:

- With `DEEPSEEK_API_KEY`, smoke run emits per-query LLM audit JSON.
- Without `DEEPSEEK_API_KEY`, deterministic eval artifacts still pass with `llm_audit_status=skipped_missing_api_key`.
- LLM output never stores private chain-of-thought or secrets.

Validation:

```powershell
python data\tmp\_source_quality_llm_audit.py --run-dir data\tmp\source_quality_stress_eval\runs\manual_smoke --provider deepseek --model deepseek-v4-pro --thinking enabled --reasoning-effort max --print-summary
```

### Phase 4: Batch Aggregation and Source Roadmap

Objective:

- Turn per-query artifacts into batch-level eval, roadmap, regression plan, and blocker list.

Allowed write scope:

- `data/tmp/_source_quality_batch_report.py`
- `data/tmp/source_quality_stress_eval/runs/**`
- optional markdown summary under `data/tmp/source_quality_stress_eval/`

Tasks:

- Aggregate scores by level: macro/province/city/county.
- Count missing source classes.
- Identify routing failures and source-level mismatches.
- Generate `source_roadmap.json`.
- Mark items requiring production changes as `requires_reopening_plan=true`.

Acceptance criteria:

- Batch report separates eval/script/docs fixes from production source changes.
- P0/P1/P2 roadmap is generated.
- Regression test plan is generated from failed/weak cases.

Validation:

```powershell
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\manual_smoke --print-json
```

### Phase 5: Full 50-Case Run and Remediation Triage

Objective:

- Run the full 50-query source stress eval and decide the next remediation PLAN.

Tasks:

- Run routing-only for all 50.
- Run live discovery/extraction for all 50 only if cost is acceptable.
- Run DeepSeek audit if credentials are available.
- Create final batch report.
- Identify P0 blockers requiring production source changes.

Acceptance criteria:

- Batch artifacts are complete.
- `source_roadmap.json` ranks source additions, routing improvements, adapter candidates, and evidence pipeline improvements.
- Next PLAN recommendation is clear.

Validation:

```powershell
python data\tmp\_source_quality_routing_eval.py --case-file data\tmp\source_quality_stress_eval\source_quality_cases_v1.json --output-dir data\tmp\source_quality_stress_eval\runs\full_routing
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\source_quality_cases_v1.json --mode extraction_inspection --output-dir data\tmp\source_quality_stress_eval\runs\full_live
python data\tmp\_source_quality_llm_audit.py --run-dir data\tmp\source_quality_stress_eval\runs\full_live --provider deepseek
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\full_live --print-json
```

## Continue Rule

After each milestone, continue automatically to the next milestone when:

- acceptance criteria are met
- focused validation passes
- no credentials are required for the next offline milestone
- no high-risk contract change is needed
- no production source change is required without explicit Architecture Gate authorization
- the user has not explicitly asked to pause

Do not treat milestone summary as a stop condition.

## Stop Conditions

Stop and request guidance when:

- the next step requires modifying `packages/sources/**`, `packages/agents/workflow.py`, provider abstraction, or protected contracts without explicit PLAN/Architecture Gate authorization
- live Tavily cost becomes unexpectedly high
- DeepSeek evaluator output is invalid or unstable after retry/repair
- Crawl4AI cannot run in the current environment and no fallback inspection is possible
- the 50-query set reveals a P0 blocker that should be handled in a remediation PLAN before continuing batch expansion
- user explicitly asks to pause

## Agent Execution Contract

Use the v2 subagent workflow if implementation is started.

Group 1:

- `invest_project_director`
- Owns phase gate refinement, real-world validation, and scope protection.
- May open a narrow remediation gate if eval surfaces blockers, but may not change user goals.

Group 2:

- `invest_agent_architecture_builder` for Phase 0 Architecture Gate and any protected-boundary decisions.
- `invest_feature_programmer` as `eval_harness_implementer` for scripts/case files/artifacts.
- `invest_feature_programmer` as `source_provider_integrator` only if a later remediation PLAN explicitly allows source-layer production changes.

Group 3:

- `invest_code_quality_checker` for focused ruff, py_compile, and pytest where relevant.
- `invest_functional_validator` for real-world case behavior and artifact inspection.

Final:

- `invest_project_summarizer` only after the PLAN reaches done condition.

## Done Condition

This PLAN is done when:

- 50-query case set exists in structured JSON
- smoke set exists
- routing-only eval works offline
- live discovery/extraction inspection works for smoke cases when `TAVILY_API_KEY` is present
- DeepSeek LLM audit works or cleanly skips when key is absent
- batch report and source roadmap are generated
- P0/P1/P2 recommendations are ranked
- any production code change recommendations are marked as requiring a new PLAN or Architecture Gate
- final PLAN completion report includes what was done, user-facing capability, concrete test cases, two before/after behavior examples, validation, risks, and next step

## Risks

- Live web volatility can change Tavily/Crawl4AI results across runs.
- Full 50-case run may consume non-trivial Tavily and DeepSeek credits.
- LLM evaluator may overgeneralize source recommendations unless constrained by schema and deterministic gates.
- County-level cases may expose real source scarcity; this should be recorded as coverage gap, not treated as script failure.
- Existing dirty worktree and `data/tmp` ruff debt can make repo-wide checks noisy.
- Current source inspection script shows that extracted pages can include navigation boilerplate; evaluator must distinguish body content from chrome.

## Rollback

Since Phase 1-4 should be scripts/artifacts/docs-only:

- Remove newly created `data/tmp/source_quality_stress_eval/**` artifacts if needed.
- Remove temporary eval scripts under `data/tmp`.
- Reset `.agent/STATUS.md` active PLAN pointer if implementation is paused.
- Do not revert unrelated dirty production files.

## Progress

- 2026-04-28: PLAN created from user-approved direction: first evaluate `routing + discovery + extraction inspection`, choose DeepSeek API as primary repeatable LLM evaluator, reserve API key placeholders, and keep production code changes gated.
- 2026-04-28: API smoke gate attempted. `DEEPSEEK_API_KEY` and `TAVILY_API_KEY` were not present in the current Codex process environment, so no external API call was made. Raw keys found in the PLAN placeholder section were replaced with `<YOUR_..._API_KEY>` placeholders to preserve the repository secret-handling rule.
- 2026-04-28: API smoke gate completed using one-time keys that were present in the PLAN at the user's request, then the PLAN/STATUS secret-like values were redacted back to placeholders. DeepSeek `deepseek-v4-pro` returned HTTP 200 with JSON output and reasoning token usage. Tavily returned HTTP 200 for English and `site:` low-cost smoke queries; one pure Chinese smoke query returned HTTP 400 `Query is invalid`, so later live inspection must record query-invalid failures and support rewrite/fallback.
- 2026-04-28: Phase 0 Architecture Gate completed. Validation command `Select-String -Path .agent\PLANS\source-quality-stress-eval-v1.md -Pattern "Decision: use DeepSeek API","source_quality_cases_v1","Deterministic Hard Gates","Smoke Query Set"` found all required sections.
- 2026-04-28: Phase 1 Case Set and Offline Routing Harness completed in `data/tmp` scope. Created `source_quality_cases_v1.json` with 50 structured cases, `smoke_cases_v1.json` with 12 smoke IDs, and `_source_quality_routing_eval.py` for offline routing inspection.
- 2026-04-28: Phase 1 validation snapshot: `python -m py_compile data\tmp\_source_quality_routing_eval.py` passed; JSON case validation loaded 50 full cases and 12 smoke cases; smoke routing run wrote `data/tmp/source_quality_stress_eval/runs/manual_smoke_routing`; full routing run wrote `data/tmp/source_quality_stress_eval/runs/full_routing`.
- 2026-04-28: Phase 1 observed routing quality signals: smoke summary `12 cases = 10 weak_pass, 2 fail, 0 blocker`; full summary `50 cases = 43 weak_pass, 7 fail, 0 blocker`. All 50 cases reported at least one missing expected lane; 7 city/county cases missed `city_county_fallback`. This is captured as eval signal for future remediation, not as a harness blocker.
- 2026-04-28: Local persistent key handling added. Created `E:\invest_agent\.env` with user-provided Tavily/DeepSeek keys and source-eval defaults. Verified `.env` is gitignored with `git check-ignore .env`; real keys are not written into PLAN/STATUS/scripts/artifacts.
- 2026-04-28: `.env` encoding normalized to UTF-8 without BOM after the first loader check missed `TAVILY_API_KEY` because the key name had a BOM prefix. Current loader check reports both Tavily and DeepSeek keys present without printing values.
- 2026-04-28: Secret hygiene scan found a tracked `command.txt` containing secret-like API key tokens. Current working copy was redacted to `<YOUR_TAVILY_API_KEY>` / `<YOUR_DEEPSEEK_API_KEY>`, and a second scan found `0` secret-like matches outside `.env`. Repository history/baseline may still contain an old key and should be handled by key rotation/history cleanup if that key is still valid.
- 2026-04-28: Phase 2 Tavily Discovery and Crawl4AI Extraction Inspection completed for the 12-case smoke set. Validation command `python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\manual_smoke --print-json` completed with `10 success`, `2 error`, `22` estimated Tavily credits, and average latency `8962.21 ms`. Artifacts were written under `data/tmp/source_quality_stress_eval/runs/manual_smoke`.
- 2026-04-28: Phase 3 DeepSeek LLM Audit completed for the smoke run using `deepseek-v4-pro`, thinking enabled, `reasoning_effort=max`, and `.env` auto-loading. The first 12-case audit timed out after partial progress; `_source_quality_llm_audit.py` was updated with `--resume` and schema-safe fallback handling. Final audit summary: `12` cases, `11 success`, `1 invalid_json`, verdicts `9 blocker`, `3 fail`, and `91144` total tokens. No private reasoning content or secret values are stored in artifacts.
- 2026-04-28: Phase 4 Batch Aggregation and Source Roadmap completed. `_source_quality_batch_report.py` generated `batch_eval.json` and `source_roadmap.json` for the smoke run. Batch summary: `12` queries, live status `10 success / 2 error`, audit verdicts `9 blocker / 3 fail`, total estimated Tavily credits `22`, average latency `8962.21 ms`, `9` reopening-plan items. Top missing source classes were `company_disclosure` (`12`), `project_list` (`11`), `local_government` (`7`), `statistics` (`7`), and `environmental_or_land_record` (`4`).
- 2026-04-28: Phase 5 full 50-case live run deferred by PLAN stop condition. The smoke run already surfaced P0/P1 production remediation blockers and `9` reopening-plan items; running the full 50 live set now would spend additional Tavily/DeepSeek budget without addressing the root source-routing and evidence-pipeline gaps first.
- 2026-04-28: Final verification snapshot: source-quality eval scripts passed `python -m py_compile`; `.env` loader check reported Tavily and DeepSeek keys present without printing values; `git check-ignore -v .env` confirmed `.gitignore:9:.env`; secret-like scan found `0` matches outside `.env`.

## Next Action

Phase 5 Remediation Triage:

- Do not run full 50-case live discovery/extraction until the smoke blockers are triaged.
- Create or select a remediation PLAN focused on source routing, source-profile/source-class coverage, Crawl4AI extraction quality, and evaluator robustness.
- Recommended next PLAN name: `source-routing-remediation-v1.md`.
- Use `data/tmp/source_quality_stress_eval/runs/manual_smoke/batch_eval.json` and `data/tmp/source_quality_stress_eval/runs/manual_smoke/source_roadmap.json` as the remediation input.
