# Source Family Evidence Backbone v1

Status: completed_with_successor_blocker

Created: 2026-04-30

Primary active PLAN: yes

Supersedes:

- `.agent/PLANS/archive/source-transaction-local-record-adapter-remediation-v1.md` (`superseded_unexecuted`)
- follow-up blocker from `.agent/PLANS/archive/source-multigranular-evidence-sufficiency-v1.md`

## Objective

Stop the repeated small remediation loop around the 12-case gate and build reusable source-family evidence backbones.

The goal is not to make the 12 smoke queries look better by hard-coding cases. The goal is to improve the general source acquisition pattern for industry research queries that need strong evidence from:

- public-resource / government-procurement records;
- project-list / filing / approval / key-project records;
- local statistics / fiscal records;
- environmental / land / natural-resource records.

The 12-case set remains a smoke/regression gate. It must not become the task target.

## Baseline

Latest source-quality baseline:

- Run artifact: `data/tmp/source_quality_stress_eval/runs/source_multigranular_evidence_sufficiency_v1_phase5_live_v1`
- Live: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, shape diagnostics `0`
- Verdicts: `9 fail / 3 weak_pass`
- Estimated Tavily credits: `76`
- Average latency: `79597.44 ms`
- Main remaining source gaps:
  - `tender_or_procurement=7`
  - `project_list=5`
  - `regulatory_record=4`
  - `local_government=3`
  - `statistics=3`
  - `environmental_or_land_record=2`

Recent conclusion:

- Runtime/search/extraction path is usable.
- Evidence quality is not yet sufficient.
- The missing capability is source-family backbone design, not another query-specific routing patch.

## Task Classification

- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `eval_policy_ops`, `provider_layer`
- Execution default: `light_subagent` for scoped implementation; `local_direct` for Phase 0 planning/artifact work.

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

No protected-contract change is allowed without an explicit Architecture Gate and `full_subagent` escalation.

## Scope

In scope:

- Source-family blocker matrix.
- Public-resource / government-procurement source backbone.
- Project-list / filing / approval / key-project source backbone.
- Local statistics / fiscal source backbone.
- Environmental / land / natural-resource source backbone.
- City/county generic domain patterns and site-search fallback strategy.
- Parent fallback transparency:
  - `parent_evidence_only`
  - `local_claim_allowed`
  - `fallback_level`
  - `fallback_source`
- Extraction and PDF failure classification for evidence-quality decisions.
- Low-cost subset validation and 12-case smoke gate rerun.

Out of scope unless reopened:

- Full 50-query live run.
- Browser automation as a default crawler.
- OCR.
- Login-gated, paid, or private databases.
- Direct securities investment advice.
- Public API response-shape changes.
- Query-specific hard-coded fixes.

## Design Direction

Move from query-first remediation to source-family backbone construction:

```text
User Query
  -> Query Decomposition
  -> Evidence Obligations
  -> Source-Family Backbone Selection
  -> Discovery Strategy
     -> domain pattern
     -> site-search fallback
     -> direct adapter when necessary
  -> Extraction Decision
  -> Evidence Quality Gate
  -> Coverage / Sufficiency Diagnostics
```

## Source-Family Backbones

### 1. Public-Resource / Government-Procurement

Purpose:

- Prove whether policy or industry direction has become actual procurement, tender, award, or public-resource trading activity.

Expected evidence:

- 招标公告
- 中标/成交公告
- 政府采购公告
- 公共资源交易详情页
- 项目采购文件 metadata

Initial access strategy:

- Search-assisted first using domain patterns and source-class signals.
- Prefer detail pages over portal/search/category pages.
- Direct adapter only if repeated public-resource platforms expose stable list/detail structure.

General domain hints:

- `ggzy.*.gov.cn`
- `ggzyjy.*.gov.cn`
- `zfcg.*.gov.cn`
- `ccgp.gov.cn`
- city/county public-resource trading center domains

Do not count as strong evidence:

- portal home pages;
- generic policy interpretation;
- search result pages without concrete tender/award text;
- pages where only the retrieval query contains the topic terms.

### 2. Project-List / Filing / Approval / Key-Project

Purpose:

- Prove whether investment, industrial layout, or local development direction has concrete project support.

Expected evidence:

- 重点项目清单
- 项目备案 / 审批 / 核准
- 开工 / 投产 / 签约
- 园区项目动态
- 重大项目集中开工

Initial access strategy:

- Search-assisted with stricter signal ranking.
- Favor official project pages from 发改委、工信、园区、政务公开、开发区管委会.
- Treat招商宣传 as weak unless it contains project主体、投资额、建设地点、状态、日期.

Do not count as strong evidence:

- broad industry planning;
- expert interpretation;
- policy goal without project entity;
- duplicated local media summary without official source.

### 3. Local Statistics / Fiscal Records

Purpose:

- Prove scale, trend, fiscal support, investment intensity, industrial output, trade, energy, transport, or employment claims.

Expected evidence:

- 统计公报
- 统计年鉴
- 部门统计数据
- 财政预算 / 决算 / 专项资金
- 工业增加值、固定资产投资、产量、用电、财政收入等指标

Initial access strategy:

- Search-assisted by official statistics/fiscal domains.
- Prefer structured tables, bulletins, annual reports, and official PDF/HTML text.
- Preserve year and metric metadata.

Do not count as strong evidence:

- old data without time context;
- provincial data silently replacing city/county data;
- media-reported numbers without official citation.

### 4. Environmental / Land / Natural-Resource Records

Purpose:

- Prove project reality, location, capacity, land use, resource condition, environmental approval, or constraint.

Expected evidence:

- 环评公示
- 能评 / 节能审查
- 土地出让公告
- 规划许可 / 建设工程许可
- 自然资源公告
- 矿权 / 资源储量 / 勘查开发记录

Initial access strategy:

- Search-assisted first with official ecology/natural-resource/planning domains.
- Static HTML/PDF extraction before browser/OCR.
- Accept parent fallback only when exact-local public evidence is sparse and metadata marks the limitation.

Do not count as strong evidence:

- wrong-region EIA or land record;
- unrelated PDF cover page;
- zero-text PDF extraction;
- procurement/project evidence misclassified as environmental/land evidence.

## City / County Strategy

Do not try to fully enumerate every city and county upfront.

Use a generic pattern plus explicit fallback:

```text
Exact local source pattern
  -> exact city/county official site-search
  -> parent province/city official fallback
  -> national official fallback
  -> explicit evidence gap
```

Required metadata behavior:

- exact-local evidence may support local claims;
- parent evidence must set `parent_evidence_only=true`;
- if exact-local evidence is missing, set `local_claim_allowed=false` unless the source itself proves exact-local relevance;
- downstream answer generation must see the limitation as a gap, not as success.

## Source-Family Blocker Matrix

Phase 0 must create a blocker matrix before production changes.

Minimum columns:

| Column | Meaning |
|---|---|
| source_family | procurement / project / statistics_fiscal / environmental_land |
| source_classes | expected source classes |
| affected_queries | smoke query IDs as symptoms, not targets |
| expected_evidence | what evidence should look like |
| current_failure_mode | discovery / routing / profile / extraction / scoring / reporting |
| current_artifact_evidence | baseline artifact path or audit detail |
| proposed_access_method | search_assisted / direct_adapter_candidate / source_profile / site_search_fallback |
| implementation_slice | first reusable slice |
| validation_subset | low-cost validation cases |
| anti_overfit_guard | how the slice avoids query-specific hardcoding |

## Agent Execution Contract

Use `.agent/skills/execution-mode-router.md`.

Default execution:

- Phase 0: `local_direct`
- Phase 1-6: `light_subagent` unless a hard escalation trigger appears
- Phase 7: `light_subagent` for harness execution and `full_subagent` only if audit/case design changes protected behavior
- Phase 8: `planning_only` or `local_direct`

Escalate to `full_subagent` when:

- a protected contract may change;
- provider abstraction or public research response shape changes;
- multiple Group2 lanes must coordinate related production writes;
- source/provider boundary changes require architecture review;
- functional validation reveals a case-design or evidence-contract issue.

Group2 lane default:

- `source_provider_integrator` for source/provider/routing/extraction work.
- `eval_harness_implementer` only when eval scripts or audit reporting change.
- `system_contract_architect` only when Architecture Gate triggers apply.

Group3 requirements:

- code-quality validation for production/test code changes;
- functional validation for smoke/live/evidence behavior;
- no worker self-certification.

## Phases

### Phase 0: Source-Family Blocker Matrix Freeze

Execution mode: `local_direct`

Objective:

- Freeze source-family failures before any production change.

Tasks:

- Read latest 12-case batch/audit artifacts.
- Group failures by source family, not query ID.
- Distinguish discovery, routing, source-profile, extraction, scoring, and reporting failures.
- Create matrix artifacts under `data/tmp/source_quality_stress_eval/source_family_backbone_phase0/`.
- Select the first implementation slice.

Acceptance criteria:

- Matrix JSON and markdown exist.
- Each implementation slice maps to a reusable source-family rule.
- No full 50-query live run is triggered.
- No production code is changed.

### Phase 1: Backbone Contract And Anti-Overfit Guard

Execution mode: `light_subagent`

Objective:

- Define the internal source-family backbone contract without changing public response shapes.

Tasks:

- Add or refine internal enums/config/helpers only if needed.
- Ensure source-family obligations can be represented without query-ID branches.
- Add regression tests that prove the same rule applies across at least two query levels or regions.

Acceptance criteria:

- No public EvidenceBundle or research response shape changes.
- Tests prove the rule is source-family-based, not query-specific.

### Phase 2: Public-Resource / Procurement Backbone

Execution mode: `light_subagent`

Objective:

- Improve `tender_or_procurement` recall and precision without broad fanout.

Tasks:

- Strengthen procurement domain and URL pattern recognition.
- Add site-search fallback phrases for exact-local procurement sources.
- Prefer detail and award/tender pages over portal pages.
- Reject generic policy pages as procurement evidence.

Acceptance criteria:

- Procurement subset reduces `tender_or_procurement` gaps versus baseline or records a narrower blocker.
- Tavily credit usage remains capped and visible.
- Generic policy pages do not count as procurement evidence.

### Phase 3: Project-List / Filing / Approval Backbone

Execution mode: `light_subagent`

Objective:

- Improve concrete project evidence while preventing policy/planning pages from masquerading as project evidence.

Tasks:

- Add reusable project signals for filing, approval, key-project, start, production, industrial-park project status.
- Strengthen phrase ordering for city/province/project tasks.
- Add wrong-evidence negative tests.

Acceptance criteria:

- `project_list` missing count does not regress.
- At least one low-cost project subset improves.
- Broad planning pages remain weak evidence unless project entity/status is present.

### Phase 4: Local Statistics / Fiscal Backbone

Execution mode: `light_subagent`

Objective:

- Improve official local numeric evidence for scale, trend, fiscal support, investment, output, and local constraints.

Tasks:

- Add local statistics/fiscal source patterns.
- Preserve metric/year/source metadata where available.
- Ensure parent-level data is not silently treated as exact-local data.

Acceptance criteria:

- Statistics/fiscal subset reports exact-local vs parent fallback accurately.
- No stale or wrong-level data is counted as strong local evidence.

### Phase 5: Environmental / Land / Natural-Resource Backbone

Execution mode: `light_subagent`

Objective:

- Improve project-reality evidence from land, EIA, planning, natural-resource, and regulatory records.

Tasks:

- Strengthen official-record domain and relevance rules.
- Reject wrong-region and zero-text evidence.
- Keep environmental/land records distinct from procurement/project evidence.

Acceptance criteria:

- Environmental/land subset keeps or improves baseline.
- Wrong-region records are rejected or marked weak.
- PDF/HTML extraction failures are visible.

### Phase 6: City / County Fallback Generalization

Execution mode: `light_subagent`

Objective:

- Make city/county source depth practical without enumerating every locality.

Tasks:

- Implement generic local domain pattern rules.
- Add site-search fallback strategy.
- Preserve explicit parent fallback metadata.
- Add negative tests for parent evidence overclaim.

Acceptance criteria:

- Exact-local evidence and parent fallback are visibly separated.
- Local claims are blocked or downgraded when exact-local evidence is missing.
- Rules work across at least city and county examples.

### Phase 7: 12-Case Smoke Gate

Execution mode: `light_subagent`

Objective:

- Re-run the same 12-case gate as a smoke/regression check, not as a tuning target.

Acceptance criteria:

- Live: `12 success / 0 runtime error`.
- DeepSeek audit: `12 success`, shape diagnostics `0`.
- `tender_or_procurement <= 5`.
- `project_list <= 5`.
- `local_government <= 3`.
- `statistics <= 3`.
- `environmental_or_land_record <= 2`.
- Weak/pass count improves from `3/12`, or a narrower source-family blocker is recorded.

### Phase 8: 50-Query Expansion Decision

Execution mode: `planning_only` or `local_direct`

Objective:

- Decide whether the system is ready for staged 50-query evaluation.

Tasks:

- Compare baseline and Phase 7 artifacts.
- Decide whether to run:
  - no 50-query live yet;
  - 12 more query expansion;
  - full 50-query offline only;
  - full 50-query live with budget cap.

Acceptance criteria:

- A cost-aware decision is recorded.
- No full 50-query live run occurs by default.

## Continue Rule

After each phase, continue automatically when:

- acceptance criteria pass;
- required validation passes;
- no protected-contract change is needed;
- no browser automation, OCR, login-gated source, or paid/private data is required;
- cost and latency remain visible;
- the next phase has a safe execution mode.

Stop when:

- a protected-contract change is required;
- full 50-query live is the next step but cost/quality gate is not met;
- validation fails and the safe fix is unclear;
- implementation would become query-specific hardcoding;
- the user explicitly pauses.

## Validation Loop

Focused source checks:

```powershell
python -m ruff check <changed files>
python -m py_compile <changed files>
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py tests\test_sources_disclosure_mapping.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

Low-cost subset rule:

- Each source-family implementation phase must run a targeted low-cost subset before the 12-case gate.
- The subset must include at least one positive case and one negative/control case when practical.

12-case live gate:

```powershell
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\strong_evidence_smoke_cases_v1.json --mode extraction_inspection --max-search-tasks 2 --max-rounds 2 --max-candidates 3 --content-chars 1200 --output-dir data\tmp\source_quality_stress_eval\runs\source_family_evidence_backbone_v1_phase7_live_v1
python data\tmp\_source_quality_llm_audit.py --run-dir data\tmp\source_quality_stress_eval\runs\source_family_evidence_backbone_v1_phase7_live_v1 --provider deepseek --model deepseek-v4-pro --thinking true --reasoning-effort max --timeout 240 --max-output-tokens 8192 --print-summary
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\source_family_evidence_backbone_v1_phase7_live_v1 --print-json
```

## Cost Controls

- Do not run full 50-query live during this PLAN unless Phase 8 explicitly records readiness and budget cap.
- Keep Tavily search depth low by default.
- Use subset evals before the 12-case gate.
- Use DeepSeek audit only after live artifacts are complete and worth judging.
- Record estimated credits and latency in every live gate summary.

## Done Condition

This PLAN is done when one of these is true:

- source-family backbones pass the 12-case smoke gate and Phase 8 records staged 50-query readiness; or
- the 12-case gate identifies a narrower blocker that requires a separate Architecture Gate or adapter PLAN; or
- implementation reaches a legitimate out-of-scope requirement such as browser automation, OCR, login-gated sources, or protected-contract change.

## Progress

- 2026-04-30: PLAN created to replace repeated small remediation loops with source-family backbone construction.
- 2026-04-30: Phase 0 completed with source-family blocker matrix artifacts:
  - `data/tmp/source_quality_stress_eval/source_family_backbone_phase0/blocker_matrix.json`
  - `data/tmp/source_quality_stress_eval/source_family_backbone_phase0/blocker_matrix.md`
  - Frozen six reusable blocker families: `city_county_fallback_transparency`, `public_resource_procurement`, `project_filing_approval_key_project`, `local_statistics_fiscal`, `environmental_land_natural_resource`, and `extraction_pdf_quality_gate`.
  - Selected first implementation order: city/county fallback transparency first, then public-resource/procurement, then project filing/approval.
  - Phase 0 stayed artifact-only; no production code changed and no full 50-query live run was triggered.
- 2026-04-30: Phase 1 completed with an internal source-family backbone contract and anti-overfit tests:
  - Added `packages/sources/source_family_backbone.py`.
  - Added `tests/test_sources_source_family_backbone.py`.
  - Contract exposes the six Phase 0 blocker families without changing public EvidenceBundle, citation, provider, or research response schemas.
  - Anti-overfit guard verifies selection is based on source classes, evidence obligations, and regional level, not query IDs or case IDs.
  - Validation passed for focused ruff/py_compile, source-family/local-pattern/retrieval-plan tests, source regression tests, and domestic source regression tests.
  - Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt (`47` errors), not on changed files.
- 2026-04-30: Phase 2 completed with reusable public-resource / procurement backbone improvements:
  - Wired source-family backbone selection into direct-lane evidence quality metadata.
  - Procurement/project fallback evidence now records `source_family_backbones`, so `tender_or_procurement` evidence can be audited as `public_resource_procurement` while retaining the distinct `project_filing_approval_key_project` family.
  - Added a lane-execution regression assertion for procurement source-family metadata.
  - Rejected public-resource list/search/category paths such as `jyxx/index.html` as `generic_project_navigation`, while preserving detail/award/tender pages.
  - Added city/county multi-sector project phrase ordering so a `公共资源交易 招标 中标` phrase stays inside the first two search-budget slots.
  - Low-cost subset artifact: `data/tmp/source_quality_stress_eval/runs/source_family_evidence_backbone_v1_phase2_procurement_subset_v2`.
  - Live subset result: `7 success / 0 runtime error`, `11` estimated Tavily credits, `6421.91 ms` average latency.
  - Live source-class coverage from artifact: `project_list` missing `1/7`, `tender_or_procurement` missing `3/7`, passing the Phase 2 subset targets (`project_list <= 6`, `tender_or_procurement <= 5`) without broad fanout.
  - Validation passed: focused procurement lane tests `3 passed`; query phrase ordering tests `3 passed`; focused query/source-family/lane/local/retrieval tests `156 passed`; source regression `27 passed`; domestic regression `16 passed`; changed-file ruff/py_compile passed.
  - Narrower blocker recorded for later extraction/PDF quality work: public-resource download endpoints can trigger Crawl4AI `Page.goto: Download is starting`; the failure is visible in extraction metadata and should be handled outside Phase 2.
- 2026-04-30: Phase 3 completed by validating the existing project-list / filing / approval backbone under the new Phase 2 guardrails:
  - Local tests for project phrase ordering and project-search candidate filtering passed:
    - `pytest -q tests\test_sources_query_decomposition.py -k "project_transaction_prioritizes or project_cluster_queries or national_computing_query or city_multisector"` -> `5 passed`.
    - `pytest -q tests\test_sources_lane_execution.py -k "official_approval_snippet or generic_project_planning or project_search"` -> `12 passed`.
  - Low-cost project subset artifact: `data/tmp/source_quality_stress_eval/runs/source_family_evidence_backbone_v1_phase3_project_subset_v1`.
  - Live subset result: `8 success / 0 runtime error`, `12` estimated Tavily credits, `14041.26 ms` average latency.
  - Live source-class coverage from artifact: `project_list` missing `2/8`, `tender_or_procurement` missing `4/8`, passing the Phase 3 subset targets (`project_list <= 5`, `tender_or_procurement <= 5`).
  - Broad planning and navigation pages remain rejected by existing negative tests; Phase 2 public-resource behavior did not regress.
  - Narrower blocker carried forward: K07/P08 project-list gaps are dominated by extraction/runtime failures on local portal/download endpoints, not by missing project-list phrase or source-family routing.
- 2026-04-30: Phase 4 completed with local statistics / fiscal source-role gating and phrase-order improvements:
  - Data-metrics search fallback now requires a statistics/fiscal source role before accepting fallback candidates as `statistics`.
  - `tjj.*`, `tj.*`, national statistics/customs, statistics/fiscal report paths, and real government-work-report paths remain allowed.
  - Media/news context paths such as `mtjj`, `kjdt`, `xwdt`, `xwzx`, `ns_news`, and `news` are not allowed to bypass the source-role gate merely because the title or snippet contains numeric/statistical terms.
  - Regional multi-sector data queries now place a local statistics-agency / statistics-bulletin phrase ahead of broad multi-sector metric phrases.
  - Added focused RED/GREEN tests for rejecting media-focus statistics false positives, rejecting media-focus government-report mirrors, accepting `tjj.*` statistics bureau pages, and accepting `tj.*` statistics subdomains.
  - Low-cost statistics/fiscal subset artifact: `data/tmp/source_quality_stress_eval/runs/source_family_evidence_backbone_v1_phase4_stats_subset_v4`.
  - Live subset result: `4 success / 0 runtime error`, `5` estimated Tavily credits, `6306.13 ms` average latency.
  - Live behavior improved: C07 now rejects city-portal news pages and keeps `tjj.changzhou.gov.cn` statistics pages; P08 now rejects Mofcom price news, NDRC policy pages, and Inner Mongolia KJT media-focus pages instead of counting them as strong statistics evidence.
  - Narrower blocker carried forward: P08 still has no usable exact statistics/fiscal document under the low-cost two-search budget after false positives are removed; this should be handled as a source-profile/search-depth or adapter decision, not by weakening evidence quality gates.
  - Validation passed: data-metrics lane tests `11 passed`; query statistics/fiscal tests `6 passed`; focused source-family/source-layer tests `161 passed`; source regression `27 passed`; domestic regression `16 passed`; changed-file ruff/py_compile passed.
- 2026-04-30: Phase 5 completed with environmental / land / natural-resource candidate precision improvements:
  - Official-record search fallback now rejects unrelated local public-body pages for exact city/county tasks before Crawl4AI extraction, including external local-government pages that merely mention the target city and same-province other-city ecology/natural-resource department pages.
  - Parent-scope and province-level positives remain allowed: parent province department pages and subprovincial records under a provincial query still pass when they carry official-record signals.
  - Low-cost official-record subset artifact: `data/tmp/source_quality_stress_eval/runs/source_family_evidence_backbone_v1_phase5_official_record_subset_v4`.
  - Live subset result: `5 success / 0 runtime error`, `11` estimated Tavily credits, `5642.57 ms` average latency, no source coverage gaps, no evidence sufficiency gaps.
  - Live behavior improved: C01 rejects `jiaxiang.gov.cn`, `sthjj.chizhou.gov.cn`, generic search/navigation pages, and generic case pages before extraction; C01 keeps only a province-level ecology record as usable evidence.
  - Validation passed: official-record tests `25 passed`; focused source-family/source-layer tests `213 passed`; source regression `27 passed`; domestic regression `16 passed`; changed-file ruff/py_compile passed.
- 2026-04-30: Phase 6 completed with explicit city/county fallback metadata:
  - Candidate decisions and document `evidence_quality` now expose `parent_evidence_only`, `local_claim_allowed`, `fallback_level`, and `fallback_source` from the existing local-region match.
  - Parent-level evidence is visible as `parent_evidence_only=true` and `local_claim_allowed=false`; exact/child local evidence remains claim-eligible.
  - Low-cost city/county fallback subset artifact: `data/tmp/source_quality_stress_eval/runs/source_family_evidence_backbone_v1_phase6_city_county_subset_v1`.
  - Live subset result: `5 success / 0 runtime error`, `11` estimated Tavily credits, `6333.2 ms` average latency.
  - Live behavior: C01 and K09 province-level ecology records are downgraded as parent-only; K12 exact-local Bazhou/Ruoqiang evidence remains `local_claim_allowed=true`.
  - Validation passed: local-region/fallback lane tests `48 passed`; focused source-family/source-layer tests `213 passed`; source regression `27 passed`; domestic regression `16 passed`; changed-file ruff/py_compile passed.
- 2026-04-30: Phase 7 completed the 12-case smoke gate and identified a narrower successor blocker:
  - Live artifact: `data/tmp/source_quality_stress_eval/runs/source_family_evidence_backbone_v1_phase7_live_v1`.
  - Live result: `12 success / 0 runtime error`, `71` estimated Tavily credits, `41380.16 ms` average latency, `0` invalid query rows.
  - DeepSeek audit result: `12 success`, audit shape diagnostics `0`, verdicts `8 fail / 4 weak_pass`, total tokens `440898`.
  - Batch report artifacts:
    - `data/tmp/source_quality_stress_eval/runs/source_family_evidence_backbone_v1_phase7_live_v1/batch_eval.json`
    - `data/tmp/source_quality_stress_eval/runs/source_family_evidence_backbone_v1_phase7_live_v1/source_roadmap.json`
  - Source-class threshold results: `tender_or_procurement=4`, `project_list=3`, `local_government=1`, and `environmental_or_land_record=1` passed; `statistics=4` failed target `<=3`.
  - Quality improved slightly from baseline `9 fail / 3 weak_pass` to `8 fail / 4 weak_pass`, but the gate did not pass.
  - Remaining blocker is narrower and reusable: local quantitative/statistics evidence, download/file extraction, and exact-local profile/adapter coverage for city/county/province cases.
- 2026-04-30: Phase 8 readiness decision completed:
  - Full 50-query live remains deferred.
  - Do not spend additional live budget on broad 50-query evaluation until the successor plan handles local quantitative evidence and file/download extraction.
  - Successor PLAN created: `.agent/PLANS/source-local-quant-file-backbone-v1.md`.

## Current Phase

Completed with successor blocker after Phase 7 / Phase 8 readiness decision.

## Risks And Rollback

Risks:

- Overfitting source rules to the 12 smoke queries.
- Increasing Tavily spend by broadening fanout instead of improving precision.
- Treating portal pages, failed PDFs, or wrong-region records as strong evidence.
- Making city/county coverage too ambitious by trying to enumerate all localities.
- Accidentally changing public response or EvidenceBundle contracts.

Rollback:

- Revert only files changed under this PLAN.
- Keep `source_multigranular_evidence_sufficiency_v1_phase5_live_v1` as baseline.
- Disable a source-family rule if it increases source drift or cost without improving evidence sufficiency.
- Keep the old transaction/local-record plan archived as a narrower fallback reference.

## Next Action

This PLAN has reached its done condition by identifying a narrower successor blocker.

Next active work should move to `.agent/PLANS/source-local-quant-file-backbone-v1.md` and focus on:

1. local statistics / fiscal / quantitative official evidence;
2. download-capable PDF/XLS/DOC extraction and failure classification;
3. exact-local city/county source profiles without hard-coding individual smoke queries;
4. a new low-cost subset before any 12-case rerun.
