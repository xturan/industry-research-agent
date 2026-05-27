# STATUS.md

## Repository Current Focus

Primary active long-running PLAN is now Source Local Procurement Regulatory Depth v1.

### Source Tier Model (LoRA 后训练) — Step 3 完成, 结论形成

**Plan**: `.agent/PLANS/unified-research-pipeline-v1.md` (Step 1-8)
**Status**: Step 3 (训练) 完成 ✅ | 结论: Hybrid 三层架构为最优解
**Reports**: `packages/training/EVAL_REPORT.md`, `packages/training/TRAINING_REPORT.md`

已完成全部:
- 环境: PyTorch 2.12.0+cu128 (SJTU镜像), VS Build Tools (MSVC), RTX 5060 sm_120 ✅
- 模型: deepseek-r1:7b (Ollama 4.7GB) ✅
- 训练: 17min, 3 epochs, loss 3.64→0.33, 154MB LoRA adapter ✅
- 数据集: 809 samples, 564 train / 120 val / 125 test

关键发现:
- LoRA 无法教模型区分 A/B (都是 .gov.cn, 仅凭 domain+url+title)
- B 级从 100% 崩溃到 5.6% — 模型过度学习 A 级模式
- 规则分类器 (_classify_source) 对 A/B 已是 100% 最优解
- 模型价值在 C 级 (46.7% vs 规则 6.7%)

最终方案: Hybrid 三层架构 — 硬规则处理 A/B/D (60-70%命中), qwen2.5:7b 处理 C 级+边界

Source Local Statistics Regional Precision v1 completed with a successor blocker. It reduced the statistics/source-profile blocker, recovered M02/M03/P08-style official data evidence, and its Phase 6 12-case live reached `12 success`, `0` audit shape diagnostics, `8 fail / 4 weak_pass`, and no dominant general `statistics` gap. Full 50-query live remains deferred. The next objective is local procurement / public-resource, regulatory-record, environmental/land, and city/county project-record depth.

Execution workflow update: PLAN execution is now speed-biased through `.agent/skills/execution-mode-router.md`. Routine docs/eval/status work should use `local_direct`; scoped source/provider/eval implementation should use `light_subagent`; failed live/eval gates should use `remediation_gate`; full v2 subagent workflow remains reserved for protected-contract, source/provider/research boundary, multi-lane, or user-facing evidence-risk work.

## Primary Active Plan

- `.agent/PLANS/research-product-v1.md` — active_phase1
- Previous completed: `.agent/PLANS/deep-research-agent-v1.md`
- Previous completed with successor blocker: `.agent/PLANS/archive/source-local-statistics-regional-precision-v1.md`
- Previous completed with successor blocker: `.agent/PLANS/archive/source-transaction-file-local-depth-v1.md`
- Previous completed with successor blocker: `.agent/PLANS/archive/source-local-quant-file-backbone-v1.md`
- Previous completed with successor blocker: `.agent/PLANS/archive/source-family-evidence-backbone-v1.md`
- Superseded unexecuted plan: `.agent/PLANS/archive/source-transaction-local-record-adapter-remediation-v1.md`
- Previous completed with successor blocker: `.agent/PLANS/archive/source-multigranular-evidence-sufficiency-v1.md`
- Previous completed with successor blocker: `.agent/PLANS/archive/source-structured-evidence-backbone-v1.md`
- Previous completed with successor blocker: `.agent/PLANS/archive/source-evidence-quality-gate-remediation-v1.md`
- Previous completed with successor blocker: `.agent/PLANS/archive/source-evidence-sufficiency-remediation-v2.md`
- Previous completed with successor blocker: `.agent/PLANS/source-local-evidence-backbone-remediation-v1.md`
- Previous blocked plan: `.agent/PLANS/source-generalized-evidence-remediation-v1.md`
- Previous blocked plan: `.agent/PLANS/source-strong-evidence-adapter-remediation-v1.md`
- Previous blocked plan: `.agent/PLANS/source-profile-adapter-remediation-v1.md`
- Previous blocked plan: `.agent/PLANS/source-direct-structured-execution-v1.md`
- Latest completed: `.agent/PLANS/archive/source-evidence-coverage-remediation-v1.md`
- Latest completed: `.agent/PLANS/archive/source-routing-remediation-v1.md`
- Previous eval plan: `.agent/PLANS/source-quality-stress-eval-v1.md`
- Last completed: `.agent/PLANS/archive/domestic-source-coverage-and-routing-v2.md`
- Latest governance sidecar completed: `.agent/PLANS/archive/execution-mode-router-tech-roadmap-v1.md`
- State: search_quality_plan_completed

## Current Phase

- Search Quality Improvement v1 completed. Layer 1 (Tavily advanced depth + domain expansion + phrase augmentation) and Layer 2 (deterministic + LLM-ready search phrase augmentation) implemented. 230 tests passing.
- 3 files changed: search_discovery.py, search_assisted_domestic.py, search_phrase_augmenter.py (new).

## Task Classification

- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`
- Current step: Search quality improvements complete. Ready for next priority.
- Protected contracts: EvidenceBundle schema, EvidenceItem citation fields, `source_quality_summary`, research analyze response shape, provider abstraction semantics, source routing response shape, task/job status semantics, `run` / `run_steps` meaning, provider/config compatibility, direct-keep primary paths, legacy `enable_source_acquisition=False` behavior, content asset metadata contract, and delivery state transition behavior remain protected.

## Current Source Local Procurement Regulatory Depth Snapshot

Active plan:

- `.agent/PLANS/source-local-procurement-regulatory-depth-v1.md`

State:

- `active_phase1_public_resource_procurement`
- Phase 0: blocker matrix completed
- Phase 1: tender / public-resource backbone in progress
- Phase 2: regulatory / environmental / land backbone pending
- Phase 3: city / county project record depth pending
- Phase 4: low-cost targeted gate pending
- Phase 5: 12-case smoke rerun pending
- Phase 6: 50-query readiness decision pending
- Execution mode: `local_direct` for Phase 0 artifacts, `light_subagent` for scoped implementation
- Full 50-query live evaluation remains deferred

Baseline from `source-local-statistics-regional-precision-v1` Phase 6:

- Live artifact: `data/tmp/source_quality_stress_eval/runs/source_local_statistics_regional_precision_v1_phase6_12case_live_v1`
- Live gate: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, shape diagnostics `0`, verdicts `8 fail / 4 weak_pass`
- Estimated Tavily credits: `66`
- Average latency: `60972.31 ms`
- Passed thresholds:
  - general `statistics` gap reduced below threshold
  - `project_list=2` against target `<=4`
- Failed threshold:
  - `tender_or_procurement=7` against target `<=5`
- Other recurring gaps:
  - `regulatory_record=4`
  - `environmental_or_land_record=2`
  - city/county source-level mismatch across local project, procurement, regulatory, land, and environmental evidence
- Next action:
  - Start Phase 1 with source-family tests for public-resource/procurement records and download/detail candidate handling.

## Latest Completed Source Local Statistics Regional Precision Snapshot

Archived plan:

- `.agent/PLANS/archive/source-local-statistics-regional-precision-v1.md`

State:

- `completed_with_successor_blocker`
- Phase 0: blocker matrix completed
- Phase 1: exact-local and homonym precision completed
- Phase 2: local statistics / fiscal / energy backbone completed
- Phase 3: direct data adapter candidate gate completed
- Phase 4: sector quantitative supplement control completed
- Phase 5: low-cost targeted gate completed with narrower blocker
- Phase 5B: official statistics source-profile remediation completed
- Phase 6: 12-case smoke rerun completed with successor blocker
- Phase 7: 50-query readiness decision completed: not ready
- Execution mode: `local_direct` for Phase 0 artifacts, `light_subagent` for scoped implementation
- Full 50-query live evaluation remains deferred

Current baseline from `source-transaction-file-local-depth-v1` Phase 7:

- Live artifact: `data/tmp/source_quality_stress_eval/runs/source_transaction_file_local_depth_v1_phase7_live_v1`
- Live gate: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, shape diagnostics `0`
- Audit verdicts: `8 fail / 4 weak_pass`
- Estimated Tavily credits: `69`
- Average latency: `37125.15 ms`
- DeepSeek tokens: `360596`
- `Download is starting` marker count: `0`
- Passed thresholds:
  - `tender_or_procurement=5` against target `<=5`
  - `project_list=3` against target `<=4`
- Failed threshold:
  - `statistics=4` against target `<=3`
- Other recurring gaps: `industry_association=3`, `industry_report=3`, `local_government=3`, `regulatory_record=2`
- Phase 0 artifacts:
  - `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase0/blocker_matrix.json`
  - `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase0/blocker_matrix.md`
- Phase 1 first slice:
  - exact-local `policy_direction` now rejects unrelated local `.gov.cn` candidates when the query has exact-local focus.
  - K12-style `若羌` salt-lake policy search no longer accepts unrelated `yanhu.gov.cn` as a broad `gov.cn` policy result.
  - Additional anti-overfit coverage: C01-style `合肥` city query rejects unrelated `sz.gov.cn`, while central `ndrc.gov.cn` policy context remains accepted.
  - Validation: source resolver tests -> `25 passed`; focused source suite -> `235 passed`; source regression -> `27 passed`; domestic regression -> `16 passed`.
- Phase 2 first slice:
  - data_metrics fallback now recognizes official energy/electricity operation, trade/customs/import-export, port/logistics, and budget-execution quantitative pages from relevant `.gov.cn` departments.
  - Commerce policy/news pages remain rejected as non-statistical evidence.
  - Validation: targeted RED `3 failed / 1 passed`; targeted GREEN -> `4 passed`; data_metrics lane tests -> `20 passed`; lane execution tests -> `70 passed`; focused source suite -> `239 passed`; source regression -> `27 passed`; domestic regression -> `16 passed`.
- Phase 3 first slice:
  - Added deterministic data adapter candidate classification and generated candidate gate artifacts.
  - Candidate gate summary: `54` candidates total; `22` manual source-profile candidates; `13` existing source-profile update candidates; `5` direct structured adapter candidates; `12` search-assisted candidates; `2` out-of-scope context sources.
  - Artifacts:
    - `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase3/data_adapter_candidates.json`
    - `data/tmp/source_quality_stress_eval/source_local_statistics_regional_precision_phase3/data_adapter_candidates.md`
  - Validation: data adapter tests -> `6 passed`; focused candidate/data-metrics tests -> `26 passed`; focused source suite -> `245 passed`; source regression -> `27 passed`; domestic regression -> `16 passed`.
- Phase 4 first slice:
  - Added `sector_quantitative_supplement_control` source-family metadata.
  - Added `official_quantitative_obligation_satisfied` so industry association/report/third-party context sources cannot satisfy official quantitative obligations alone.
  - Search-assisted industry-topic evidence now carries supplemental-family metadata and `official_quantitative_obligation_satisfied=false`.
  - Validation: source-family tests -> `7 passed`; search-assisted industry metadata test -> `1 passed`; focused source suite -> `252 passed`; source regression -> `27 passed`; domestic regression -> `16 passed`.
- Phase 5 low-cost targeted gate:
  - Main run: `data/tmp/source_quality_stress_eval/runs/source_local_statistics_regional_precision_v1_phase5_subset_v1`
  - Live: `6 success`, `41` estimated Tavily credits, `40155.02 ms` average latency.
  - DeepSeek audit: `6 success`, shape diagnostics `0`, verdicts `3 fail / 3 weak_pass`, `180621` tokens.
  - Gaps: `statistics=4`, `tender_or_procurement=5`, `industry_association=3`, `industry_report=3`.
  - Exact-local remediation:
    - `神木` / `若羌` known exact-local entities now use the city/county `municipal` bucket instead of `provincial`.
    - `sxsm.gov.cn` and `xjrq.gov.cn` now resolve as `exact_park_or_county` with `local_claim_allowed=true`.
    - K12 transient Tavily SSL EOF was recovered by a K12-only retry.
  - Data-metrics remediation:
    - Province multi-city data phrases now start with the statistics agency / statistical bulletin.
    - Official statistical-classification PDFs are accepted as data-metrics candidates.
    - P04 recovered `statistics` coverage through `安徽省2025年国民经济和社会发展统计公报`.
    - M02/M03/P08 still need stable official data/source-profile remediation.
  - Validation: changed-file ruff / py_compile -> pass; query+resolver+lane tests -> `163 passed`; focused source suite -> `243 passed`; source regression -> `27 passed`; domestic regression -> `16 passed`.
- Phase 5B official statistics source-profile remediation:
  - Inner Mongolia energy metrics now prioritize energy-operation/statistics-bulletin phrases and official energy/statistics domains.
  - Inner Mongolia statistics profile now uses the statistics-bulletin entry URL plus real list/detail selectors.
  - Profile list discovery now ranks mixed statistical bulletins by query intent and hydrates data-metrics direct HTML list-detail items with detail-page text.
  - Generic statistics index pages such as `stats.gov.cn/sj/`, `/sj/zxfb`, and title `数据` remain rejected as `generic_stats_homepage`.
  - Live `M02` data_metrics single-case v1 recovered statistics coverage through `全国数据资源调查报告（2023年）` with `1` Tavily fallback credit.
  - Live `P08` data_metrics single-case v3 recovered statistics coverage through `内蒙古自治区2025年国民经济和社会发展统计公报` with `0` Tavily fallback credits.
  - Live `M03/P04/P08` data_metrics retry v8 reports `3 success`, `2` estimated Tavily credits, average latency `5928.64 ms`; M03 uses the low-altitude statistical-classification PDF, P04 uses a Wuhu statistical bulletin, and P08 uses the Inner Mongolia annual bulletin.
  - Validation: changed-file focused tests -> `166 passed`; changed-file ruff/py_compile -> pass; source regression -> `252 passed`; source layer regression -> `27 passed`; domestic/profile/PDF regression -> `18 passed`.
- Successor implementation slice: Source Local Procurement Regulatory Depth v1 Phase 0 blocker matrix.

## Latest Completed Source Transaction File Local Depth Snapshot

Archived plan:

- `.agent/PLANS/archive/source-transaction-file-local-depth-v1.md`

State:

- `completed_with_successor_blocker`
- Phase 0: successor blocker matrix completed
- Phase 1: file/download adapter Architecture Gate completed
- Phase 2: official file extractor slice completed
- Phase 3: transaction/procurement/project source backbone completed
- Phase 4: exact-local strong evidence depth completed
- Phase 5: macro-to-local obligation fanout completed
- Phase 6: low-cost targeted gate completed
- Phase 7: 12-case smoke rerun completed with successor blocker
- Phase 8: 50-query readiness decision completed: not ready
- Execution mode: `light_subagent` by default
- Full 50-query live evaluation remains deferred

Current baseline from `source-local-quant-file-backbone-v1` Phase 5:

- Live artifact: `data/tmp/source_quality_stress_eval/runs/source_local_quant_file_backbone_v1_phase5_live_v1`
- Live gate: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, shape diagnostics `0`
- Audit verdicts: `1 blocker / 8 fail / 3 weak_pass`
- Estimated Tavily credits: `70`
- Average latency: `55287.68 ms`
- Main remaining blocker: `tender_or_procurement=7` failed target `<=5`; file/download candidates are now structured but need real official file adapters and local-depth source backbones.
- Phase 0 artifacts:
  - `data/tmp/source_quality_stress_eval/source_transaction_file_local_depth_phase0/blocker_matrix.json`
  - `data/tmp/source_quality_stress_eval/source_transaction_file_local_depth_phase0/blocker_matrix.md`
- Latest implementation slice: transaction/procurement/project source-family backbone completed; non-PDF download/file candidates remain structured unsupported gaps.
- Next implementation slice: 12-case smoke rerun.
- Phase 1 validation:
  - targeted RED/GREEN official energy operation data test -> pass after implementation
  - data_metrics lane tests -> `12 passed`
  - focused source suite -> `214 passed`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
- Phase 2 validation:
  - RED/GREEN data-metrics `.xlsx` file candidate gate -> pass after implementation
  - data_metrics lane tests -> `15 passed`
  - focused source suite -> `217 passed`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
- Phase 3 validation:
  - RED/GREEN tests for project PDF quality family, stronger procurement-detail prioritization, and generic policy/news false-procurement guard -> pass after implementation
  - Project fallback / PDF / tender tests -> `17 passed`
  - Low-cost project subset v2: `3 success / 0 runtime error`, `4` estimated Tavily credits, `6282.69 ms` average latency
  - `M02`/`P08` NDRC pages now stay `project_list` instead of false `tender_or_procurement`
  - `C09` public-resource pages retain `tender_or_procurement` and `public_resource_procurement`
  - changed-file ruff / py_compile -> pass
  - focused source suite -> `230 passed`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
- Phase 4 validation:
  - RED/GREEN tests for exact-local city/county domain priority and generic flag parent-claim guard -> pass after implementation
  - Focused exact-local/query tests -> `8 passed`
  - Focused local-region/lane tests -> `7 passed`
  - changed-file ruff / py_compile -> pass
  - focused source suite -> `233 passed`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
- Phase 5 validation:
  - RED/GREEN tests for macro policy-to-demand fanout -> pass after implementation
  - Phase-adjacent query/retrieval tests -> `26 passed`
  - changed-file ruff / py_compile -> pass
  - focused source suite -> `235 passed`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
  - M02 now requires `national_policy_direction`, `provincial_policy_rollout`, project, data, and disclosure lanes instead of allowing project/data/disclosure alone
- Phase 6 validation:
  - Phase 6 subset case file: `data/tmp/source_quality_stress_eval/source_transaction_file_local_depth_phase6_subset_cases.json`
  - v1 run: `data/tmp/source_quality_stress_eval/runs/source_transaction_file_local_depth_v1_phase6_subset_v1`
  - v1 result: `6 success`, `34` estimated Tavily credits, `35546.57 ms` average latency
  - M02 focused run: `data/tmp/source_quality_stress_eval/runs/source_transaction_file_local_depth_v1_phase6_m02_v1`
  - M02 result: `1 success`, `6` estimated Tavily credits; local rollout now executes under `first_wave_local_policy_generic`
  - v2 run: `data/tmp/source_quality_stress_eval/runs/source_transaction_file_local_depth_v1_phase6_subset_v2`
  - v2 result: `6 success`, `35` estimated Tavily credits, `39021.25 ms` average latency
  - `Download is starting` marker count: `0`
  - Narrower blockers: M02 macro-to-local local rollout can still hit crawl timeout/budget exhaustion; K07 local rollout has anti-bot/forbidden partials
- Phase 4 targeted subset:
  - Case file: `data/tmp/source_quality_stress_eval/source_local_quant_file_backbone_phase4_subset_cases.json`
  - v1 artifact: `data/tmp/source_quality_stress_eval/runs/source_local_quant_file_backbone_v1_phase4_subset_v1`
  - v1 result: `6 success`, `33` estimated Tavily credits, `33278.28 ms` average latency
  - v1 finding: project/public-resource download endpoints still reached Crawl4AI as `Download is starting`
  - Remediation: project fallback now gates file/download candidates as `project_file_requires_adapter`
  - v2 artifact: `data/tmp/source_quality_stress_eval/runs/source_local_quant_file_backbone_v1_phase4_subset_v2`
  - v2 result: `6 success`, `37` estimated Tavily credits, `29029.82 ms` average latency
  - v2 finding: file/download candidates are structured and no per-query task artifact contains `Download is starting`
  - Remaining narrower blockers: `P08` data-metrics low-budget exhaustion; `M03` data-metrics PDF file adapter; `P08` project public-resource download adapter

## Latest Completed Source Family Evidence Backbone Snapshot

Baseline from `source-multigranular-evidence-sufficiency-v1` Phase 5:

- Live artifact: `data/tmp/source_quality_stress_eval/runs/source_multigranular_evidence_sufficiency_v1_phase5_live_v1`
- Live gate: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, shape diagnostics `0`
- Audit verdicts: `9 fail / 3 weak_pass`
- Estimated Tavily credits: `76`
- Average latency: `79597.44 ms`
- Primary remaining source gaps:
  - `tender_or_procurement=7`
  - `project_list=5`
  - `regulatory_record=4`
  - `local_government=3`
  - `statistics=3`
  - `environmental_or_land_record=2`

Hard strategy:

- Keep 12-case as smoke/regression gate, not tuning target.
- Build reusable source-family backbones:
  - public-resource / government-procurement
  - project-list / filing / approval / key-project records
  - local statistics / fiscal records
  - environmental / land / natural-resource records
- Use generic city/county source patterns, site-search fallback, and explicit parent fallback metadata.
- Defer full 50-query live until Phase 8 readiness decision.

Phase 0 output target:

- `data/tmp/source_quality_stress_eval/source_family_backbone_phase0/blocker_matrix.json`
- `data/tmp/source_quality_stress_eval/source_family_backbone_phase0/blocker_matrix.md`

Phase 0 completed:

- Created `data/tmp/source_quality_stress_eval/source_family_backbone_phase0/blocker_matrix.json`.
- Created `data/tmp/source_quality_stress_eval/source_family_backbone_phase0/blocker_matrix.md`.
- Frozen six reusable blocker families:
  - `city_county_fallback_transparency`
  - `public_resource_procurement`
  - `project_filing_approval_key_project`
  - `local_statistics_fiscal`
  - `environmental_land_natural_resource`
  - `extraction_pdf_quality_gate`
- Selected first implementation order:
  - city/county fallback transparency
  - public-resource / procurement
  - project filing / approval / key-project
  - local statistics / fiscal
  - environmental / land / natural-resource
  - extraction / PDF / zero-text quality gate
- Phase 0 validation kept the work artifact-only: no production code changed and no full 50-query live run was triggered.

Phase 1 target:

- Define or refine internal source-family backbone helpers without public contract changes.
- Add anti-overfit tests proving rules are source-family-based rather than query-ID-specific.
- Use the Phase 0 matrix as the implementation contract.

Phase 1 completed:

- Added `packages/sources/source_family_backbone.py`.
- Added `tests/test_sources_source_family_backbone.py`.
- Source-family contract now exposes six reusable blocker families from Phase 0.
- Anti-overfit tests verify selection by source classes, evidence obligations, and regional level, not query IDs or case IDs.
- Public EvidenceBundle, citation, provider, and research response contracts were not changed.
- Validation:
  - RED: `pytest -q tests\test_sources_source_family_backbone.py` failed with missing module before implementation.
  - GREEN: `pytest -q tests\test_sources_source_family_backbone.py` -> `4 passed`.
  - Focused ruff: `python -m ruff check packages\sources\source_family_backbone.py tests\test_sources_source_family_backbone.py` -> pass.
  - Focused py_compile -> pass.
  - Focused retrieval/local/source-family tests -> `49 passed`.
  - Source regression tests -> `27 passed`.
  - Domestic source regression tests -> `16 passed`.
  - Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt (`47` errors).

Phase 2 target:

- Improve `tender_or_procurement` recall and precision without query-ID-specific remediation.
- Prefer detail/award/tender pages over portal/search/category pages.
- Keep procurement logic distinct from project-list logic.

Phase 2 progress:

- Wired source-family backbone selection into direct-lane evidence quality metadata.
- `tender_or_procurement` evidence now records `source_family_backbones` including `public_resource_procurement`.
- Project evidence with tender/procurement signals retains both `public_resource_procurement` and `project_filing_approval_key_project`, keeping procurement and project-list families distinct.
- Added lane-execution regression coverage for procurement source-family metadata.
- Rejected public-resource list/search/category paths such as `jyxx/index.html` as `generic_project_navigation`, while preserving detail/award/tender pages.
- Added city/county multi-sector project phrase ordering so a `公共资源交易 招标 中标` phrase stays inside the first two search-budget slots.
- Low-cost subset `source_family_evidence_backbone_v1_phase2_procurement_subset_v2`:
  - `7 success / 0 runtime error`
  - `11` estimated Tavily credits
  - `6421.91 ms` average latency
  - `project_list` missing `1/7`
  - `tender_or_procurement` missing `3/7`
- Phase 2 acceptance passed; next phase is project-list / filing / approval backbone.
- Narrower blocker retained for later extraction/PDF quality work: public-resource download endpoints can trigger Crawl4AI `Page.goto: Download is starting`; failures are visible in extraction metadata.
- Validation:
  - RED: `pytest -q tests\test_sources_lane_execution.py -k tender_procurement` failed with missing `source_family_backbones` metadata.
  - GREEN: same focused test -> `1 passed`.
  - RED/GREEN public-resource list-page rejection -> focused test `1 passed`.
  - RED/GREEN city/county public-resource early-budget phrase test -> related query tests `3 passed`.
  - Focused ruff/py_compile on changed source/test files -> pass.
  - Focused query/source-family/lane/local/retrieval tests -> `156 passed, 1 warning`.
  - Source regression tests -> `27 passed`.
  - Domestic source regression tests -> `16 passed`.

Phase 3 target:

- Improve reusable project-list / filing / approval / key-project evidence.
- Keep Phase 2 procurement behavior as a regression guard.
- Run a low-cost project-list subset before Phase 4.

Phase 3 completed:

- Local tests:
  - Query project phrase tests -> `5 passed`.
  - Lane project-search / planning-page rejection tests -> `12 passed`.
- Low-cost project subset `source_family_evidence_backbone_v1_phase3_project_subset_v1`:
  - `8 success / 0 runtime error`
  - `12` estimated Tavily credits
  - `14041.26 ms` average latency
  - `project_list` missing `2/8`
  - `tender_or_procurement` missing `4/8`
- Phase 3 acceptance passed; next phase is local statistics / fiscal backbone.
- Narrower blocker carried forward: K07/P08 project-list gaps are dominated by extraction/runtime failures on local portal/download endpoints, not by project-list phrase/routing absence.

Phase 4 target:

- Improve local statistics / fiscal source patterns and phrase ordering.
- Preserve exact-local vs parent fallback metadata for numeric/fiscal evidence.
- Run a low-cost statistics/fiscal subset before Phase 5.

Phase 4 completed:

- Added statistics/fiscal source-role gating for data-metrics search fallback.
- Rejected media/news context pages such as KJT media-focus and city portal news from being counted as strong `statistics` evidence.
- Preserved acceptance for `tjj.*`, `tj.*`, national statistics/customs, statistics/fiscal report paths, and real government-work-report paths.
- Regional multi-sector data queries now prioritize a local statistics-agency / statistics-bulletin phrase before broad metric phrases.
- Low-cost statistics/fiscal subset `source_family_evidence_backbone_v1_phase4_stats_subset_v4`:
  - `4 success / 0 runtime error`
  - `5` estimated Tavily credits
  - `6306.13 ms` average latency
  - C07 rejected city-portal news and kept `tjj.changzhou.gov.cn` statistics pages
  - P08 rejected Mofcom price news, NDRC policy pages, and Inner Mongolia KJT media-focus pages instead of counting them as strong statistics evidence
- Narrower blocker carried forward: P08 still has no usable exact statistics/fiscal document under the low-cost two-search budget after false positives are removed; handle as source-profile/search-depth or adapter decision, not by weakening evidence quality gates.

Phase 5 completed:

- Official-record search fallback now rejects unrelated local public-body pages for exact city/county tasks before Crawl4AI extraction.
- Low-cost official-record subset `source_family_evidence_backbone_v1_phase5_official_record_subset_v4`:
  - `5 success / 0 runtime error`
  - `11` estimated Tavily credits
  - `5642.57 ms` average latency
  - no source coverage gaps
  - no evidence sufficiency gaps
- C01 now rejects `jiaxiang.gov.cn`, `sthjj.chizhou.gov.cn`, generic search/navigation pages, and generic case pages before extraction; parent/province-level positives remain allowed when properly signaled.
- Validation passed:
  - official-record lane tests -> `25 passed`
  - focused source-family/source-layer tests -> `213 passed`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
  - changed-file ruff/py_compile -> pass

Phase 6 completed:

- Candidate decisions and document `evidence_quality` now expose `parent_evidence_only`, `local_claim_allowed`, `fallback_level`, and `fallback_source`.
- Low-cost city/county fallback subset `source_family_evidence_backbone_v1_phase6_city_county_subset_v1`:
  - `5 success / 0 runtime error`
  - `11` estimated Tavily credits
  - `6333.2 ms` average latency
- Live behavior:
  - C01 and K09 province-level ecology records are downgraded as parent-only (`local_claim_allowed=false`).
  - K12 exact-local Bazhou/Ruoqiang evidence remains claim-eligible (`local_claim_allowed=true`).
- Validation passed:
  - local-region/fallback lane tests -> `48 passed`
  - focused source-family/source-layer tests -> `213 passed`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
  - changed-file ruff/py_compile -> pass

## Superseded Source Transaction Local Record Adapter Snapshot

Superseded unexecuted plan:

- `.agent/PLANS/archive/source-transaction-local-record-adapter-remediation-v1.md`

State:

- `superseded_unexecuted`
- Replaced before implementation by `.agent/PLANS/source-family-evidence-backbone-v1.md`

Successor baseline from `source-multigranular-evidence-sufficiency-v1` Phase 5:

- Live artifact: `data/tmp/source_quality_stress_eval/runs/source_multigranular_evidence_sufficiency_v1_phase5_live_v1`
- Live gate: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, shape diagnostics `0`
- Audit verdicts: `9 fail / 3 weak_pass`
- Estimated Tavily credits: `76`
- Average latency: `79597.44 ms`
- Primary remaining source gaps:
  - `tender_or_procurement=7`
  - `project_list=5`
  - `regulatory_record=4`
  - `local_government=3`
  - `statistics=3`
  - `environmental_or_land_record=2`
- Phase 4 matrix:
  - `data/tmp/source_quality_stress_eval/source_multigranular_evidence_sufficiency_phase4/adapter_decision_matrix.json`
  - `data/tmp/source_quality_stress_eval/source_multigranular_evidence_sufficiency_phase4/adapter_decision_matrix.md`

## Latest Source Multigranular Evidence Sufficiency Snapshot

Completed plan:

- `.agent/PLANS/archive/source-multigranular-evidence-sufficiency-v1.md`

Baseline inherited from `source-structured-evidence-backbone-v1` Phase 5:

- Live artifact: `data/tmp/source_quality_stress_eval/runs/source_structured_evidence_backbone_v1_phase5_live_v1`
- Live gate: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, shape diagnostics `0`
- Audit blockers: `0`
- Audit verdicts: `7 fail / 5 weak_pass / 0 pass`
- Estimated Tavily credits: `75`
- Average latency: `61372.52 ms`
- Passed source-count thresholds:
  - `project_list=1` missing vs target `<=5`
  - `tender_or_procurement=3` missing vs target `<=5`
  - `local_government=1` missing vs target `<=3`
  - `statistics=2` missing vs target `<=3`
  - `environmental_or_land_record=1` missing vs target `<=2`
- Failed quality threshold:
  - weak/pass target failed: `5/12` vs required `>=6/12`
  - fail-count target failed: `7` vs required `<=6`
- Phase 0 completed:
  - Created `data/tmp/source_quality_stress_eval/source_multigranular_evidence_sufficiency_phase0/obligation_matrix.json`.
  - Created `data/tmp/source_quality_stress_eval/source_multigranular_evidence_sufficiency_phase0/obligation_matrix.md`.
  - Frozen obligation families:
    - `administrative_granularity`
    - `multi_city_distribution`
    - `multi_sector_decomposition`
    - `quantitative_metric_evidence`
    - `exact_local_depth`
    - `extraction_or_adapter_decision`
- Phase 1 target:
  - Implement reusable evidence-obligation metadata in query decomposition / retrieval planning.
  - Validation must prove province distribution, multi-sector, quantitative metric, and exact-local obligations without query-ID-specific branches.
- Phase 1 completed:
  - Added `evidence_obligations` metadata to `QueryDecompositionTask` and `CoverageLanePlan`.
  - Exposed administrative granularity, multi-city distribution, multi-sector decomposition, quantitative metric, and exact-local depth obligations.
  - RED/GREEN phase1 tests passed after implementation.
  - Validation:
    - `pytest -q tests\test_sources_query_decomposition.py` -> `56 passed`
    - `pytest -q tests\test_sources_retrieval_plan.py` -> `35 passed`
    - focused source suite -> `198 passed, 1 warning`
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
    - focused ruff/py_compile -> pass
- Phase 2 completed:
  - Added non-anchor city domain/phrase expansion for province distribution queries.
  - Added sector-specific local/project/data phrases for multi-sector queries.
  - Validation: query/retrieval tests `95 passed`; focused source suite `202 passed`; source regression `27 passed`; domestic regression `16 passed`.
- Phase 3 completed:
  - Added `evidence_sufficiency_gaps` to batch reports.
  - Baseline preview separated `56` sufficiency gaps from `22` source-coverage gaps.
- Phase 4 completed:
  - Created adapter decision matrix with five owner categories.
- Phase 5 completed with successor blocker:
  - Live `12 success`, audit schema `12 success`, shape diagnostics `0`.
  - Quality failed: `9 fail / 3 weak_pass`; `tender_or_procurement=7`.
  - Full 50-query live remains deferred.

## Latest Source Structured Evidence Backbone Snapshot

Completed plan:

- `.agent/PLANS/archive/source-structured-evidence-backbone-v1.md`

Baseline inherited from `source-evidence-quality-gate-remediation-v1` Phase 5:

- Live artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase5_live_v1`
- Live gate: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, shape diagnostics `0`, total tokens `424427`
- Audit verdicts: `10 fail / 2 weak_pass / 0 pass`
- Estimated Tavily credits: `75`
- Average latency: `44521.71 ms`
- Failed Phase 5 thresholds:
  - weak/pass target failed: `2/12` vs required `>=6/12`
  - fail-count target failed: `10` vs required `<=6`
  - `project_list=6` vs target `<=5`
  - `tender_or_procurement=7` vs target `<=5`
- Passed Phase 5 source-count thresholds:
  - `local_government=1` vs target `<=3`
  - `statistics=1` vs target `<=3`
  - `environmental_or_land_record=2` vs target `<=2`
- Source roadmap:
  - `requires_reopening_plan_items=7`
  - `adapter_candidates=6`
- Phase 0 completed:
  - Created `data/tmp/source_quality_stress_eval/source_structured_evidence_backbone_phase0/failure_matrix.json`.
  - Created `data/tmp/source_quality_stress_eval/source_structured_evidence_backbone_phase0/failure_matrix.md`.
  - Source-family matrix validation -> `phase0_matrix_ok 6 public_resource_and_procurement`.
- Phase 1 target:
  - Implement reusable source-family/domain/evidence-signal rules for public-resource and procurement evidence.
  - Reduce `tender_or_procurement` missing count from `7` toward `<=5` without increasing default fanout or regressing project-list coverage.
- Phase 1 completed:
  - Added a reusable public-resource/procurement search-signal gate for generic-title trading pages on `ggzy`, `ccgp`, `zfcg`, `cgw`, and related detail paths.
  - Low-cost subset `source_structured_evidence_backbone_v1_phase1_procurement_subset_v1` -> `7 success`, estimated Tavily credits `13`, average latency `7430.53 ms`, `query_invalid_count=0`.
  - `M02`, `M03`, and `P08` project lanes now cover both `project_list` and `tender_or_procurement`.
  - `C01/P04` still cover only `project_list`; `K09/K12` still lack usable project/procurement evidence.
  - Validation: project fallback tests `7 passed`; focused source suite `173 passed`; source regression `27 passed`; domestic regression `16 passed`.
- Phase 2 target:
  - Improve project-list evidence via approval, filing, key-project, start/production, and development-zone project patterns.
  - Keep generic policy interpretation and broad planning pages from masquerading as strong project evidence.
- Phase 2 completed:
  - Project transaction phrase ordering now prioritizes `项目备案 审批` and `重点项目 开工 投产` for approval/filing/industrialization queries.
  - Project-cluster queries now keep `重点项目 开工 投产` plus `公共资源交易 招标 中标` in the two-credit search window.
  - Official government/DRC-style project approval snippets can be accepted when they contain concrete project approval/key-project signals.
  - Broad planning/public-comment/expert-view/policy-interpretation pages are rejected as `generic_project_planning_or_interpretation`.
  - Low-cost subset `source_structured_evidence_backbone_v1_phase2_project_subset_v2` -> `8 success`, estimated Tavily credits `15`, average latency `10000.77 ms`, `query_invalid_count=0`.
  - Subset coverage: `project_list` missing `1`, `tender_or_procurement` missing `4`.
  - Validation: query decomposition tests `51 passed`; project fallback tests `11 passed`; focused source suite `180 passed`; source regression `27 passed`; domestic regression `16 passed`.
- Phase 3 target:
  - Keep `environmental_or_land_record <= 2` stable while reducing `regulatory_record` misses.
  - Improve MEE/provincial ecology, natural resources, planning, land transfer, approval, and filing record evidence without trusting retrieval-query terms alone.
- Phase 3 completed:
  - Added national-scope official-record handling for local `.gov.cn` detail pages when the task is national/unscoped, the page has record signals, and relevance terms match.
  - Added matching post-extraction domain allowance so valid national-scope local official records are not discarded as off-domain after Crawl4AI/static extraction.
  - Expanded official-record department snippet trust to DRC/FGW/FZGGW/NDRC-style government domains for regulatory records while preserving record-signal and relevance gates.
  - Low-cost subset `source_structured_evidence_backbone_v1_phase3_official_record_subset_v1` -> `5 success`, estimated Tavily credits `13`, average latency `18320.51 ms`, `query_invalid_count=0`.
  - `M02` now covers `environmental_or_land_record` and `regulatory_record`; `P08/K09/K12` retained coverage; `K07` remains missing both official-record classes as a county-level sparse-source/profile gap.
  - Validation: official-record tests `21 passed`; query decomposition tests `51 passed`; focused source suite `182 passed`; source regression `27 passed`; domestic regression `16 passed`.
  - Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt (`47` errors).
- Phase 4 target:
  - Improve regional enterprise disclosure relevance and industry report/price/capacity evidence.
  - Keep disclosure direct paths primary and search-only evidence supplementary.
- Phase 4 completed:
  - Added regional industry-topic phrase generation for P04/P10-style local industry evidence.
  - Added audit-visible `association_report`, `price_data`, and `industry_price_capacity` metadata for industry-topic documents.
  - Added industry-topic root/channel URL rejection so allowlisted association home/channel pages do not become strong evidence.
  - Added regional enterprise disclosure phrases and region-tagged candidate prioritization; C07 now ranks `天合光能` / `亿纬锂能` before generic battery names.
  - Low-cost industry subset `source_structured_evidence_backbone_v1_phase4_industry_subset_v3` -> `3 success`, estimated Tavily credits `3`, average latency `38613.34 ms`, `query_invalid_count=0`.
  - Low-cost disclosure subset `source_structured_evidence_backbone_v1_phase4_disclosure_subset_v1` -> `3 success`, estimated Tavily credits `0`, average latency `772.66 ms`, `query_invalid_count=0`.
  - Validation: focused source/disclosure suite `192 passed`; source regression `27 passed`; domestic regression `16 passed`; focused ruff/py_compile passed.
  - Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt (`47` errors).
- Phase 5 target:
  - Re-run the 12-case live inspection, DeepSeek audit, and batch report.
  - Acceptance remains the PLAN gate: `12 success / 0 runtime error`, audit schema success, `0` blockers, and quality/source-gap thresholds.

## Current Source Evidence Quality Gate Remediation Snapshot

Active plan:

- `.agent/PLANS/archive/source-evidence-quality-gate-remediation-v1.md`

Baseline inherited from `source-evidence-sufficiency-remediation-v2` Phase 5:

- Live artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase5_live_v1`
- Live gate: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, shape diagnostics `0`, total tokens `298099`
- Audit verdicts: `11 fail / 1 weak_pass / 0 pass`
- Estimated Tavily credits: `79`
- Average latency: `43861.95 ms`
- Failed Phase 5 thresholds:
  - weak/pass target failed: `1/12` vs required `>=6/12`
  - fail-count target failed: `11` vs required `<=6`
  - `project_list` target failed: `7` vs required `<=5`
  - `tender_or_procurement` new strong-evidence gap: `7`
- Passed Phase 5 source-count thresholds:
  - `statistics=2` vs target `<=3`
  - `environmental_or_land_record=2` vs target `<=2`
- Credential note:
  - The first DeepSeek audit attempt failed with `12` authentication errors because a manually loaded `.env` value preserved a trailing quote in `DEEPSEEK_API_KEY`.
  - Clearing the inherited process variable and letting the audit script strip `.env` quotes produced the final successful audit.

Phase 1 validation snapshot:

- Query phrase-order remediation:
  - Project-list style tasks now put `重点项目 开工 投产` first and `公共资源交易 招标 中标` second, keeping `项目清单` as third fallback.
  - Low-altitude and real-estate project phrases now also include public-resource/tender signals inside the two-credit search window.
- New eval case file:
  - `data/tmp/source_quality_stress_eval/source_evidence_quality_gate_phase1_project_subset_cases.json`
- Validation:
  - `pytest -q tests\test_sources_query_decomposition.py` -> `48 passed`
  - focused source suite -> `171 passed, 1 warning`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
  - focused ruff/py_compile -> pass
  - JSON subset parse check -> `case_count=7`
- Low-cost live subset:
  - Final artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase1_project_subset_v2`
  - Result: `7 success`, estimated Tavily credits `11`, average latency `5905.07 ms`, `query_invalid_count=0`
  - Improvements: `C07` and `M06` now cover both `project_list` and `tender_or_procurement`; `C01`, `M02`, and `P04` cover `project_list`.
  - Remaining gaps: `K12` sparse county recall; `P08` accepted project PDFs but produced download/zero-usable-evidence extraction behavior; `C01/M02/P04` still lack tender/procurement evidence.

Phase 2 validation snapshot:

- Exact-local-first local rollout remediation:
  - Municipal commercial-space local rollout tasks now keep exact Xi'an domains in the first-wave domain pool and exclude Shaanxi parent domains from that same pool.
  - `xcaib.xa.gov.cn` is now a Xi'an local-government and project/public-resource source-pattern domain.
  - Parent/city fallback remains explicit through `parent_evidence_only` and `local_claim_allowed` metadata instead of masquerading as exact-local evidence.
- New eval case file:
  - `data/tmp/source_quality_stress_eval/source_evidence_quality_gate_phase2_local_subset_cases.json`
- Validation:
  - `pytest -q tests\test_sources_query_decomposition.py -k "xian_commercial_space"` -> `2 passed`
  - `pytest -q tests\test_sources_local_source_patterns.py` -> `8 passed`
  - `pytest -q tests\test_sources_query_decomposition.py` -> `48 passed`
  - focused ruff/py_compile -> pass
  - focused source suite -> `171 passed, 1 warning`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
- Low-cost live subset:
  - Final artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase2_local_subset_v3`
  - Result: `4 success`, estimated Tavily credits `4`, average latency `21950.08 ms`, `query_invalid_count=0`.
  - `C09` now covers `local_government` and `official_policy` through exact-city Xi'an official evidence.
  - `K07` covers `local_government` and `official_policy` through exact county seed fallback, with anti-bot extraction diagnostics visible.
  - `K09` and `K12` cover local source classes but remain parent/city fallback with `parent_evidence_only=true` and `local_claim_allowed=false`.

Phase 3 validation snapshot:

- Official-record evidence-quality hardening:
  - Official-record weak-document filtering no longer uses `discovery_query` as document topic evidence.
  - Direct-lane evidence-quality scoring no longer uses `discovery_query` in topic/source-class evidence haystacks.
  - Added a regression test for P08-style sparse/unrelated PDF cover text where only the retrieval query contains the target topic terms.
- New eval case file:
  - `data/tmp/source_quality_stress_eval/source_evidence_quality_gate_phase3_official_extraction_subset_cases.json`
- Validation:
  - `pytest -q tests\test_sources_lane_execution.py -k "official_record_relevance_does_not_trust_discovery_query_only"` -> `1 passed`
  - `pytest -q tests\test_sources_lane_execution.py -k "official_record"` -> `19 passed, 1 warning`
  - focused ruff/py_compile -> pass
  - focused source suite -> `172 passed, 1 warning`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
- Low-cost live subset:
  - Final artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase3_official_extraction_subset_v2`
  - Result: `4 success`, estimated Tavily credits `11`, average latency `8151.06 ms`, `query_invalid_count=0`.
  - `P08` retained usable MEE HTML official-record evidence and surfaced one PDF download failure.
  - `K09` retained usable official-record HTML/PDF evidence and surfaced one `zero_text` PDF failure.
  - `M02` and `K07` completed without runtime errors but had no accepted official-record candidate in this official-record-only slice.

Phase 4 validation snapshot:

- Compact audit-input visibility hardening:
  - Oversized artifacts passed to DeepSeek now include an `audit_summary` with task family, source-class coverage, coverage gaps, direct fallback statuses, selected counts, estimated credits, evidence-quality summaries, rejected-document reasons, document source classes, extraction metadata, and structured error classes.
  - Small artifacts are left unchanged to avoid unnecessary token overhead.
  - No public EvidenceBundle, citation, research response, provider, or task/run contract changed.
- Validation:
  - `pytest -q tests\test_source_quality_llm_audit.py tests\test_source_quality_batch_report.py tests\test_source_quality_live_inspection.py` -> `8 passed, 1 warning`
  - `python -m ruff check data\tmp\_source_quality_llm_audit.py tests\test_source_quality_llm_audit.py tests\test_source_quality_batch_report.py tests\test_source_quality_live_inspection.py` -> pass
  - `python -m py_compile data\tmp\_source_quality_llm_audit.py tests\test_source_quality_llm_audit.py tests\test_source_quality_batch_report.py tests\test_source_quality_live_inspection.py` -> pass
- Compact-shape smoke check:
  - `K09` and `P08` oversized artifacts from `source_evidence_quality_gate_v1_phase3_official_extraction_subset_v2` include `audit_summary`.
  - `K07` and `M02` remained under the compact threshold and were left unchanged.

Current phase:

- Phase 5: 12-Case Quality Gate.

Next validation target:

- 12-case live gate.
- DeepSeek audit transport/schema and quality verdicts.
- Batch report source-gap thresholds.
- Do not run the 50-query live evaluation until the 12-case strong-evidence quality gate materially improves.

## Current Source Evidence Sufficiency Remediation v2 Slice Snapshot

Active plan:

- `.agent/PLANS/archive/source-evidence-sufficiency-remediation-v2.md`

Phase 2 completed at implementation-gate level:

- Added metadata-only source-class annotation for accepted search-assisted `policy_direction`, `local_rollout`, and `industry_topic` documents.
- `local_rollout` accepted raw and normalized documents now expose `source_class` and `source_classes`, so eval artifacts can mark `local_government` / `official_policy` coverage without relying on LLM inference from article text.
- Domain repair now preserves priority order while deduping valid domains.
- `data_metrics` domain selection now prefers exact-local entity domains and local statistics/fiscal backbone domains before parent/region-generic and national defaults.
- Direct/fallback documents now promote `evidence_quality.source_class` into common `metadata.source_class/source_classes`.
- Parent-government domains that only mention the exact local region no longer become `exact_local`; they remain `parent_local` or `child_local` based on hierarchy evidence.
- `data_metrics` financial/fiscal phrases now balance exact-local statistics agency targeting with a broader second fallback phrase to preserve recall under the two-credit budget.
- No protected public EvidenceBundle, citation, research response, provider, or task/run contract changed.

Validation snapshot:

- `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py` -> `146 passed, 1 warning`
- source regression -> `27 passed`
- domestic regression -> `16 passed`
- focused ruff/py_compile for changed production/test files -> pass
- repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt (`47` errors)
- low-cost live artifact `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase2_local_rollout_visibility_smoke_v1` -> `2 success`, estimated Tavily credits `2`, average latency `5431.21 ms`, `query_invalid_count=0`
- low-cost live artifact `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase2_data_metrics_visibility_smoke_v5` -> `2 success`, estimated Tavily credits `3`, average latency `6791.12 ms`, `query_invalid_count=0`

Observed behavior:

- `C01` and `K09` `local_rollout` artifacts now show complete `local_government` / `official_policy` source-class coverage.
- `C01` still surfaced a structured Crawl4AI anti-bot/minimal-text extraction error, but the task preserved partial-failure behavior and metadata visibility.
- `C01` and `K09` `data_metrics` artifacts now show `statistics` source-class coverage with document-level `source_class/source_classes` metadata.
- C01 statistics evidence is now transparently classified as `child_local`; K09 statistics evidence is `parent_local`, not misleading `exact_local`.
- Phase 3 project/public-resource and official-record implementation gate is complete.
- Project/public-resource evidence now supports multi-source-class metadata: `project_list` plus `tender_or_procurement` when accepted documents show tender/procurement signals.
- Official-record evidence now supports multi-source-class metadata: `environmental_or_land_record` plus `regulatory_record` when accepted documents show approval/filing/regulatory signals.
- Conservative official-record search-signal handling now allows ecology/environment or natural-resources department domains to use search snippet/content record signals while broad `gov.cn`, unrelated local domains, and `/dxal/` typical-case pages remain protected.
- Phase 3 validation snapshot:
  - `pytest -q tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py` -> `79 passed, 1 warning`
  - `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py` -> `70 passed`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
  - focused ruff/py_compile for changed production/test files -> pass
  - repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt (`47` errors)
- Low-cost live Phase 3 artifacts:
  - `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase3_project_smoke_v2` -> `2 success`, estimated Tavily credits `4`, average latency `17751.6 ms`, `query_invalid_count=0`
  - `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase3_official_record_smoke_v3` -> `2 success`, estimated Tavily credits `2`, average latency `3247.3 ms`, `query_invalid_count=0`
- Observed Phase 3 behavior:
  - `K09` `project_transaction` now covers `project_list` and `tender_or_procurement`.
  - `C01` `official_record` now covers `environmental_or_land_record` and `regulatory_record`.
  - `C01` `project_transaction` still lacks `tender_or_procurement`; this remains a source-availability/search-recall risk.
  - `K09` `official_record` still lacks usable evidence because the selected official PDF produced structured `zero_text` / `pdf_or_download` diagnostics.
- Phase 4 is complete. Full missing-count acceptance remains deferred to the Phase 5 12-case evidence-sufficiency gate.
- Phase 4 industry/market specialist gate is complete:
  - `source_resolver.SUPPLEMENTAL_DOMAINS` now reuses the query-decomposition supplemental allowlist, preventing CAAM/battery100/chinapv/HIIPB style public supplemental domains from being misclassified as `other`.
  - C07-style mixed industry capacity/price phrases are split by subindustry and include `最新` to bias discovery toward fresher evidence.
  - `industry_topic` theme matching now scopes to the current Tavily query phrase, preventing cross-round theme leakage.
  - Final low-cost live artifact `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase4_industry_market_smoke_v6` -> `3 success`, estimated Tavily credits `3`, average latency `44585.64 ms`, `query_invalid_count=0`.
  - `C07`, `P04`, and `P10` industry task artifacts now show complete `industry_report` / `industry_association` coverage.
  - Residual risk: C07 public industry discovery can still surface stale/weak CAAM/CCPIT evidence and one CAAM homepage timeout; this is deferred to the Phase 5 audit rather than patched with query-specific rules.

## Latest Source Generalized Evidence Remediation Snapshot

Created 2026-04-29:

- `.agent/PLANS/source-generalized-evidence-remediation-v1.md`

Phase 7 handoff baseline from `source-strong-evidence-adapter-remediation-v1`:

- Live artifact: `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_live_final_v1`
- Live gate: `12 success / 0 runtime error`
- DeepSeek audit status: `12 success / 0 invalid_json`
- DeepSeek audit verdicts: `10 fail / 1 weak_pass / 1 blocker`
- Missing source classes above target: `project_list=7`, `statistics=7`, `environmental_or_land_record=5`, `official_policy=2`
- Successor objective: generalize remediation around coverage lanes, local source profiles, extraction reliability, and evidence sufficiency.

Phase 0/1/2/3 validation snapshot:

- Phase 0 generated `data/tmp/source_quality_stress_eval/generalized_remediation_phase0/failure_taxonomy.json` and `.md`.
- Phase 0 taxonomy identified the highest-impact families: evidence sufficiency, extraction reliability, local statistics, local project/public-resource, official records, industry capacity/market, local capital/research, policy relevance, coverage lane planner, and specialist regulator.
- Phase 1 slice 1 enhanced coverage-lane search phrases for capacity/market-price, local fund/university/research, and low-altitude scale/order proof obligations.
- Validation passed: focused ruff/py_compile; `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_source_quality_failure_taxonomy.py tests\test_source_quality_llm_audit.py` -> `81 passed`; source regression -> `27 passed`; domestic regression -> `16 passed`; routing gate `generalized_phase1_routing_v1` -> `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
- Phase 2 added reusable local source-class domain patterns in `packages/sources/local_source_patterns.py` and connected them to decomposition/source resolver matching for statistics, fiscal/local-government, public-resource/project, and environmental/land/official-record lanes.
- Phase 2 validation passed: focused ruff/py_compile; local source pattern/decomposition checks -> `6 passed`; focused source/decomposition/profile checks -> `92 passed`; profile/lane/router checks -> `33 passed`; source regression -> `27 passed`; domestic regression -> `16 passed`; routing gate `generalized_phase2_routing_v1` -> `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
- Phase 3 added structured Crawl4AI extraction failure classification under existing error/detail metadata. It classifies PDF/download, anti-bot/403, SSL/certificate, timeout, minimal-text/empty, runtime-error, and missing-runner-result failures without browser automation/OCR or public schema changes.
- Phase 3 validation passed: focused ruff/py_compile; Crawl4AI RED/GREEN tests -> `2 passed`; extraction/PDF validation -> `16 passed`; source regression -> `27 passed`; domestic regression -> `16 passed`.
- Phase 4 added direct-lane evidence-quality diagnostics under existing metadata only. Accepted direct/fallback documents now carry `evidence_quality`; lane metadata includes `evidence_quality_summary`; weak-document rejections include quality diagnostics for source class, topic, region, administrative level, content, and date signals.
- Phase 4 validation passed: RED/GREEN lane tests -> `3 passed`; focused ruff/py_compile passed; focused Phase 4 validation -> `51 passed`; focused decomposition/profile checks -> `92 passed`; source regression -> `27 passed`; domestic regression -> `16 passed`; repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt.
- Phase 5 routing gate artifact `data/tmp/source_quality_stress_eval/runs/generalized_phase5_routing_v1` reports `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
- Phase 5 live artifact `data/tmp/source_quality_stress_eval/runs/generalized_phase5_live_v1` reports `12 success / 0 runtime error`, average latency `34752.02 ms`, estimated Tavily credits `78`, and `query_invalid_count=0`.
- Phase 5 DeepSeek audit completed after one timeout and resume run. Final audit status: `12 success`, audit shape diagnostics `0`, verdicts `1 blocker / 8 fail / 3 weak_pass`, total tokens `274905`.
- Phase 5 failed acceptance: blocker `C01`; weak/pass count `3/12` is below the `6/12` target; `statistics=4` exceeds target `<=3`; `environmental_or_land_record=3` exceeds target `<=2`. `project_list=5` met target `<=6`.
- Phase 6 50-query expansion is deferred because the 12-case quality gate did not pass. The next PLAN must target general local evidence backbones and extraction/budget reliability, not case-specific overfitting.

Current PLAN phase:

- Superseded by `.agent/PLANS/source-local-evidence-backbone-remediation-v1.md`.

## Latest Source Local Evidence Backbone Remediation Snapshot

Created 2026-04-29:

- `.agent/PLANS/source-local-evidence-backbone-remediation-v1.md`

Baseline inherited from `source-generalized-evidence-remediation-v1` Phase 5:

- Routing artifact: `data/tmp/source_quality_stress_eval/runs/generalized_phase5_routing_v1`
- Live artifact: `data/tmp/source_quality_stress_eval/runs/generalized_phase5_live_v1`
- Live gate: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, shape diagnostics `0`, verdicts `1 blocker / 8 fail / 3 weak_pass`
- Tavily credits: `78`
- Main gaps: `local_government=5`, `project_list=5`, `statistics=4`, `environmental_or_land_record=3`

Current PLAN phase:

- Completed with successor blocker. Successor active plan is `.agent/PLANS/source-evidence-sufficiency-remediation-v2.md`.

Phase 0 and Phase 1 validation snapshot:

- Added `data/tmp/_source_local_evidence_backbone_matrix.py` and `tests/test_source_local_evidence_backbone_matrix.py`.
- Generated `data/tmp/source_quality_stress_eval/local_evidence_backbone_phase0/backbone_matrix.json` and `.md`.
- Backbone matrix active buckets:
  - `local_government`: `8` cases
  - `project_public_resource`: `6` cases
  - `statistics_fiscal`: `7` cases
  - `environmental_land_record`: `4` cases
  - `extraction_reliability`: `12` cases
  - `budget_lane_scheduling`: `12` cases, `78` credits vs baseline `69`
- Added reusable local source backbone helpers in `packages/sources/local_source_patterns.py`:
  - `local_evidence_backbone_for_source_class()`
  - `local_source_domains_for_backbones()`
- Tests now use Unicode escape strings for Chinese region literals to avoid PowerShell/console mojibake.
- Validation passed:
  - focused ruff/py_compile for changed matrix/source-pattern files -> pass
  - `pytest -q tests\test_sources_local_source_patterns.py` -> `6 passed`
  - `pytest -q tests\test_source_local_evidence_backbone_matrix.py` -> `1 passed`
  - focused source/decomposition/profile suite -> `95 passed`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
- Repo-wide `python -m ruff check .` was rerun and still fails on known historical `data/tmp` scratch/demo lint debt, not on files changed in this PLAN slice.
- Phase 1 slice 2 wired the local evidence backbone helpers into production query-decomposition domain selection for `local_rollout`, `project_transaction`, `data_metrics`, and `official_record`.
- Phase 1 slice 2 validation passed:
  - RED/GREEN focused tests -> `2 passed`
  - focused source/decomposition/profile suite -> `97 passed`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
  - profile/lane/router focused check -> `33 passed, 1 warning`
  - routing eval artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase1_routing_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`
  - matrix artifact `data/tmp/source_quality_stress_eval/local_evidence_backbone_phase1/backbone_matrix.json` and `.md`
- Focused ruff/py_compile for changed files passed. Repo-wide `python -m ruff check .` still fails on known historical `data/tmp` scratch/demo lint debt (`47` errors), not on Phase 1 touched files.
- Phase 2 slice 1 added generalized project/statistics phrase targeting and project/data fallback budget caps:
  - project phrases now target `重点项目/项目清单`, `开工/投产`, and `招标/中标` when query evidence obligations indicate project lists or rollout.
  - statistics/fiscal phrases now target `统计公报/财政`, `财政资金/补贴`, and investment data when query evidence obligations indicate fiscal support or funding.
  - `DirectStructuredLaneExecutor` now has `max_project_fallback_search_credits` and `max_data_metrics_fallback_search_credits` with budget metadata and `search_credit_budget_exhausted` status.
- Phase 2 slice 1 validation passed:
  - RED/GREEN focused tests -> `3 passed`
  - query/lane/retrieval focused suite -> `107 passed, 1 warning`
  - focused ruff/py_compile for changed Phase 2 files -> pass
  - routing eval artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_routing_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
  - focused profile/lane/router check -> `35 passed, 1 warning`
- Repo-wide `python -m ruff check .` still fails on known historical `data/tmp` scratch/demo lint debt (`47` errors), not on Phase 2 touched files.
- Phase 2 low-cost live subset completed:
  - subset case file `data/tmp/source_quality_stress_eval/local_backbone_phase2_live_subset_cases.json` with `C01` and `K09`
  - project live artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_project_live_subset_v1` -> `2 success`, estimated Tavily credits `4`, average latency `7210.45 ms`, query invalid count `0`
  - data live artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_data_live_subset_v1` -> `2 success`, estimated Tavily credits `3`, average latency `5724.73 ms`, query invalid count `0`
  - observed behavior: data metrics found usable C01 statistics evidence; C01/K09 project evidence remained weak; K09 data metrics exhausted the two-credit cap without usable exact-local evidence
  - generalized next issue: administrative hierarchy semantics are too coarse. The system needs to distinguish exact-local, child-county/district, parent-city/province, and unrelated-region evidence instead of treating all non-exact matches as simple region mismatches.
- Phase 2 admin-hierarchy slice completed at deterministic/code level:
  - Added `classify_local_region_match()` for `exact_local`, `child_local`, `parent_local`, `unrelated_region`, and `unknown` source-region classifications.
  - Project/data fallback candidate decisions and accepted evidence-quality metadata now carry `local_region_match_type` and related matched-region diagnostics.
  - Evidence-quality region matching no longer counts `discovery_query` as source-region evidence, so query echo cannot upgrade parent evidence into exact-local evidence.
  - Validation passed:
    - RED/GREEN focused tests -> `3 passed`
    - local/source/lane/retrieval focused suite -> `117 passed, 1 warning`
    - focused ruff/py_compile for changed production/tests -> pass
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
    - focused profile/lane/router check -> `37 passed, 1 warning`
    - offline routing artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_admin_hierarchy_routing_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`
  - Live v2 artifacts were generated but did not validate recall because Tavily returned HTTP `432` on every project/data search request:
    - `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_project_live_subset_v2`
    - `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_data_live_subset_v2`
  - Treat Tavily HTTP `432` as the current live-gate blocker, not as a source-routing logic failure.
- Phase 2 provider blocker remediation completed:
  - Added `TAVILY_API_KEYS` settings support and Tavily adapter multi-key rotation/fallback for provider key/quota/status failures (`401`, `403`, `429`, `432`).
  - `.env` now stores the local gitignored credential values for primary and rotating Tavily keys; raw credentials were not written to PLAN, STATUS, scripts, or run artifacts.
  - `.env` was normalized to UTF-8 without BOM after Pydantic failed to read the BOM-prefixed first env var.
  - Validation passed:
    - `pytest -q tests\test_sources_search_discovery.py` -> `10 passed`
    - `pytest -q tests\test_sources_search_discovery.py tests\test_sources_lane_execution.py` -> `41 passed, 1 warning`
    - `python -m ruff check packages\core\config.py packages\sources\search_discovery.py tests\test_sources_search_discovery.py` -> pass
    - `python -m py_compile packages\core\config.py packages\sources\search_discovery.py tests\test_sources_search_discovery.py` -> pass
    - credential marker scan found raw key markers only in `.env`
  - Live v3 rerun resolved the Tavily `432` blocker:
    - `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_project_live_subset_v3` -> `2 success`, estimated Tavily credits `4`, average latency `7720.96 ms`, `query_invalid_count=0`
    - `data/tmp/source_quality_stress_eval/runs/local_backbone_phase2_data_live_subset_v3` -> `2 success`, estimated Tavily credits `2`, average latency `6204.24 ms`, `query_invalid_count=0`
  - Observed behavior:
    - `C01` project fallback accepted a `child_local` candidate after the admin-hierarchy slice.
    - `K09` project fallback still had no accepted project candidate under the two-credit cap.
    - `C01` and `K09` data/statistics fallback both accepted exact-local evidence candidates.
  - Phase 2 decision:
    - Provider blocker resolved.
    - Phase 2 local implementation and low-cost live gate are sufficient to proceed to Phase 3.
    - Cross-case missing-count targets remain to be verified by the Phase 5 12-case quality gate.
- Phase 3 slice 1 completed:
  - Added formal administrative region terms for generic `official_record` search phrases, e.g. `肥西县` / `合肥市` instead of only `肥西` / `合肥`.
  - Kept existing dedicated official-record phrase templates for `神木`, `若羌`, and `内蒙古` stable.
  - Added document-level official-record domain guard so extracted pages outside the task allowlist are rejected unless they are region-matched `.gov.cn` records and do not explicitly declare an unrelated local government in title or metadata hints.
  - Validation passed:
    - RED/GREEN focused tests -> pass
    - `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py` -> `88 passed, 1 warning`
    - `pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_domestic_scaleout_phase7.py tests\test_sources_city_county_fallback.py` -> `44 passed`
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
    - focused ruff/py_compile for changed Phase 3 files -> pass
    - routing artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase3_routing_formal_region_terms_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`
  - Live validation:
    - `data/tmp/source_quality_stress_eval/runs/local_backbone_phase3_official_record_c01_replay_v3` -> `1 success`, estimated Tavily credits `3`, average latency `7812.32 ms`, `query_invalid_count=0`
    - The previous false-positive `jiaxiang.gov.cn` page for C01 is now rejected as `official_record_domain_mismatch` and no longer becomes evidence.
  - Repo-wide `python -m ruff check .` still fails on known historical `data/tmp` scratch/demo lint debt (`47` errors), not on files touched in this slice.
  - Phase 3 remains active; C01 still lacks usable local official-record evidence, but now fails transparently instead of accepting unrelated evidence.
- Phase 3 slice 2 completed:
  - Added static official-record PDF fallback in `packages/sources/lane_execution.py`.
  - Official-record PDF candidates now use existing PDF download/text extraction services instead of being rejected at candidate selection.
  - PDF/download failures are surfaced as structured evidence gaps with `pdf_extraction.failure_classes` and `extraction_failure_class=pdf_or_download`.
  - Validation passed:
    - PDF focused tests -> `2 passed`
    - `pytest -q tests\test_sources_lane_execution.py` -> `36 passed, 1 warning`
    - Phase 3 focused suite -> `105 passed, 1 warning`
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
    - focused ruff/py_compile -> pass
    - routing artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase3_pdf_static_routing_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`
  - Live official-record subset artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase3_official_record_pdf_static_live_v1` -> `5 success`, estimated Tavily credits `9`, average latency `11169.7 ms`, `query_invalid_count=0`.
  - The official-record subset now has `3` evidence_found and `2` without evidence; `K09` succeeds via static PDF extraction.
  - Phase 3 acceptance is met; execution has moved to Phase 4.
- Phase 4 completed:
  - Added `data/tmp/_source_quality_budget_diagnostics.py` and `tests/test_source_quality_budget_diagnostics.py`.
  - Budget diagnostics now record total estimated Tavily credits, compare against a `78` baseline, aggregate credits by task family, and flag local lanes that spend search credits on broad/national domains before targeted local domains.
  - Budget artifacts:
    - `data/tmp/source_quality_stress_eval/runs/local_backbone_phase4_budget_pdf_static_v1` -> official-record subset `9` credits, within baseline, no budget flags.
    - `data/tmp/source_quality_stress_eval/runs/local_backbone_phase4_budget_baseline_v1` -> 12-case baseline `78` credits, within baseline, one targeted-domain recommendation for municipal `industry_topic` empty-domain fanout.
  - Validation passed:
    - `pytest -q tests\test_source_quality_budget_diagnostics.py` -> `1 passed`
    - focused ruff/py_compile for the budget diagnostics script/test -> pass
    - focused eval harness tests -> `3 passed, 1 warning`
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
  - Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt (`47` errors), not on Phase 4 touched files.
  - Phase 4 acceptance is met; execution has moved to Phase 5.
- Phase 5 completed with successor blocker:
  - Routing artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase5_routing_v1` -> `12` cases, `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
  - Live artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase5_live_v1` -> `12 success`, estimated Tavily credits `78`, average latency `36040.35 ms`, `query_invalid_count=0`.
  - DeepSeek audit -> `12 success`, shape diagnostics `0`, verdicts `1 blocker / 11 fail`, total tokens `288722`.
  - Batch report gaps: `local_government=5`, `project_list=5`, `statistics=4`, `environmental_or_land_record=2`.
  - Budget artifact `data/tmp/source_quality_stress_eval/runs/local_backbone_phase5_budget_v1` -> `78` credits, no budget expansion flag.
  - Backbone artifact `data/tmp/source_quality_stress_eval/local_evidence_backbone_phase5` -> budget lane inactive, remaining active lanes are local government, project/public-resource, statistics/fiscal, environmental/land, and extraction reliability.
  - Phase 6 50-query live expansion is deferred because the 12-case quality gate failed.

## Latest Source Evidence Sufficiency Remediation v2 Snapshot

Created 2026-04-29:

- `.agent/PLANS/source-evidence-sufficiency-remediation-v2.md`

Baseline inherited from `source-local-evidence-backbone-remediation-v1` Phase 5:

- Runtime and budget are stable: `12 success`, `78` Tavily credits.
- Quality gate failed: `1 blocker / 11 fail`, `0` weak/pass.
- Main gaps: `local_government=5`, `project_list=5`, `statistics=4`, `environmental_or_land_record=2`.
- Known blocker: `C07` needs reusable industry association / market-price / photovoltaic supply-chain evidence.

Current PLAN phase:

- Phase 2: Local Government And Statistics/Fiscal Backbone.

Phase 0 validation snapshot:

- Generated `data/tmp/source_quality_stress_eval/source_evidence_sufficiency_v2_phase0/backbone_matrix.json` and `.md`.
- Confirmed successor blocker is evidence sufficiency, not runtime or budget:
  - live runtime: `12 success / 0 runtime error`
  - budget: `78` credits, credit delta `0`
  - audit schema: `0` shape diagnostics
- Frozen gaps: `local_government=5`, `project_list=5`, `statistics=4`, `environmental_or_land_record=2`.
- Phase 1 validation snapshot:
  - Added metadata-only `source_class_coverage` diagnostics to `data/tmp/_source_quality_live_inspection.py`.
  - No public EvidenceBundle/citation/research response schema changed.
  - Focused eval harness tests -> `4 passed, 1 warning`.
  - Source regression -> `27 passed`.
  - Domestic regression -> `16 passed`.
  - Low-cost live smoke `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase1_visibility_smoke_v1` -> `2 success`, `3` credits; C01/K09 `data_metrics` tasks show `statistics` expected and covered.

## Latest Source Strong Evidence Adapter Remediation Snapshot

Created 2026-04-29:

- `.agent/PLANS/source-strong-evidence-adapter-remediation-v1.md`

## Latest Subagent Model Cost Policy Snapshot

Completed 2026-04-29:

- `.agent/PLANS/archive/subagent-model-cost-policy-v1.md`

Current project subagent model policy:

- Standard reasoning speed is `medium`.
- `invest_project_director`: `gpt-5.4`, `medium`.
- `invest_project_summarizer`: `gpt-5.4`, `medium`.
- `invest_agent_architecture_builder`: `gpt-5.4`, `medium`.
- `invest_feature_programmer`: `gpt-5.3-codex`, `medium`.
- `invest_code_quality_checker`: `gpt-5.3-codex-spark`, `medium`.
- `invest_functional_validator`: `gpt-5.4`, `medium`.

Rationale:

- Remove default `gpt-5.5` usage from project subagents to reduce token/cost pressure.
- Use Codex Spark only for high-frequency short mechanical checks.
- Keep concrete implementation on the coding-optimized Codex model instead of Spark by default.

Validation:

- `Get-ChildItem .codex\agents\*.toml | Select-String -Pattern 'gpt-5\.5|model_reasoning_effort = "high"'` -> no matches.
- TOML parse check over `.codex/agents/*.toml` -> all six files parsed and report the intended model/reasoning matrix.
- Documentation checks confirmed `gpt-5.3-codex-spark`, `gpt-5.4`, and `medium` are present in the current subagent overview, operating model, gate contract, and archived model-cost PLAN.

Runtime caveat:

- Current already-open Codex sessions may still show tool-level fixed agent metadata until local `.codex/agents/*.toml` is reloaded by the runtime. The repository policy and project-local agent config have been updated.

Objective:

- Move the source system from "routing/runtime works" to "strong evidence coverage is good enough for staged 50-query evaluation".
- Build durable evidence backbones for company disclosure, project/procurement/tender records, statistics/structured data, and environmental/land/regulatory records.
- Keep Tavily as discovery support, not as a replacement for direct structured evidence lanes.

Baseline reused from `data/tmp/source_quality_stress_eval/runs/evidence_coverage_final_live_v2`:

- 12-case routing gate: `9 pass / 3 weak_pass`, no fail/blocker.
- 12-case live gate: `12 success / 0 runtime error`, estimated Tavily credits `19`, average latency `13703.9 ms`, `query_invalid_count=0`.
- DeepSeek audit: `12 success`, `0 invalid_schema`, `0 blocker`, verdicts `11 fail / 1 weak_pass`, total tokens `183928`.
- Main systemic gaps: `company_disclosure` missing in `12/12`, `project_list` missing in `12/12`, `statistics` missing in `7/12`, `environmental_or_land_record` missing in `5/12`.

Current PLAN phase:

- Phase 7: run the 12-case strong-evidence quality gate using the final Phase 6 live artifact unless a fresh live rerun is required.

Phase 0 completion snapshot:

- Generated `data/tmp/source_quality_stress_eval/strong_evidence_phase0/strong_evidence_gap_matrix_v1.json`.
- Generated `data/tmp/source_quality_stress_eval/strong_evidence_phase0/strong_evidence_gap_matrix_v1.csv`.
- Generated `data/tmp/source_quality_stress_eval/strong_evidence_phase0/strong_evidence_gap_matrix_v1.md`.
- Matrix coverage: `12` smoke cases x `4` target source classes = `48` rows.
- Target missing counts: `company_disclosure=12`, `project_list=12`, `statistics=7`, `environmental_or_land_record=5`.
- Architecture gate decision: `phase1_can_proceed_without_public_contract_change`.
- Director gate confirmed no protected public contract change is needed before Phase 1. Phase 2 needs a narrow Architecture Gate before direct disclosure behavior changes.
- Group3 functional validator artifact-level validation passed, but initially failed the PLAN gate because PLAN/STATUS did not yet record the artifact paths and gate decision. This STATUS update corrects that gap.

Phase 1 completion snapshot:

- Added `data/tmp/_source_quality_strong_evidence_matrix.py`.
- Added `data/tmp/source_quality_stress_eval/strong_evidence_smoke_cases_v1.json`.
- Added `tests/test_source_quality_strong_evidence_matrix.py`.
- The script produces reusable JSON/CSV/Markdown strong-evidence gap artifacts and a typed Phase 1 queue from the final live/audit run.

Phase 1 validation:

- `python -m py_compile data\tmp\_source_quality_batch_report.py data\tmp\_source_quality_routing_eval.py data\tmp\_source_quality_strong_evidence_matrix.py` -> pass.
- `python -m py_compile data\tmp\_source_quality_strong_evidence_matrix.py tests\test_source_quality_strong_evidence_matrix.py` -> pass.
- `pytest -q tests\test_source_quality_batch_report.py tests\test_source_quality_strong_evidence_matrix.py` -> `3 passed`.
- `python data\tmp\_source_quality_strong_evidence_matrix.py --run-dir data\tmp\source_quality_stress_eval\runs\evidence_coverage_final_live_v2 --output-dir data\tmp\source_quality_stress_eval\strong_evidence_phase0` -> `48` rows, `12` cases, phase0 decision `phase1_can_proceed_without_public_contract_change`.

Phase 2 Architecture Gate:

- Direct-keep disclosure boundary is frozen as CNINFO / SSE / SZSE / BSE only.
- Primary disclosure evidence must not route through Tavily/search-assisted discovery.
- Phase 2 may add an internal deterministic `disclosure_mapping` layer and existing-metadata no-match gaps without public schema changes.
- BSE remains an allowed direct-keep boundary but should execute only for mapped BSE candidates; otherwise return explicit unsupported/no-match.
- Forbidden changes: EvidenceBundle/citation/research response/provider/task/run contract changes, browser automation, OCR, login/paid sources, and generic exchange-homepage evidence.

Phase 2 implementation snapshot:

- Added `packages/sources/disclosure_mapping.py` with deterministic topic/entity/search contracts for direct-keep disclosure evidence.
- Wired `enterprise_disclosure` lane execution in `packages/sources/lane_execution.py` to use explicit ticker/company hints or deterministic topic anchors before direct adapter search.
- Added entity-mismatch rejection so generic exchange homepages/navigation pages do not count as disclosure evidence.
- Added precise no-entity no-match handling through existing metadata and partial status semantics.
- Added sector-disclosure routing in `packages/sources/query_decomposition.py` so strong-evidence cases like `P04` and `K09` get an enterprise-disclosure lane even when the user query does not literally say "上市公司".
- Added/updated focused tests in `tests/test_sources_disclosure_mapping.py`, `tests/test_sources_lane_execution.py`, and `tests/test_sources_query_decomposition.py`.
- Generated `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase2_disclosure_mapping/disclosure_mapping_summary.json`: `12/12` smoke cases now have mapped disclosure entity candidates.
- Phase 2 routing gate: `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase2_routing` -> `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
- Focused validation passed: focused ruff, py_compile, source focused pytest `85 passed`, source regression `27 passed`, domestic regression `16 passed`.
- Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch-script lint debt.
- Audit-level `company_disclosure` missing-count reduction remains deferred to Phase 7's 12-case strong-evidence live/audit gate to avoid spending a DeepSeek audit run after every backbone phase.

Phase 3 slice 1 snapshot:

- Repaired CCGP list selectors, GGZY project entry URL, and NDRC project entry URL.
- Added project-lane rejection for generic navigation, irrelevant project records, wrong-region fallback candidates, and non-project policy/commentary pages.
- Added supplemental Tavily + Crawl4AI project fallback that runs only after direct project profiles return no usable evidence and uses `allow_supplemental_direct_keep=True`.
- Extended project-transaction query decomposition to include regional and exact-local official domains.
- Low-cost live smoke:
  - `C09` Xi'an hard-tech/commercial-space produced one public-resource fallback evidence item.
  - `M03` low-altitude macro project lane rejected generic GGZY navigation and NDRC policy/commentary pages without concrete project signals.
  - `K07` Feixi NEV now rejects wrong-region Hai'an/Lujiang candidates and non-project NDRC commentary, returning explicit no-evidence instead of false evidence.
- Phase 3 routing eval artifact: `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase3_routing` -> `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
- Validation passed: focused ruff/py_compile, focused source pytest `87 passed`, source regression `27 passed`, domestic regression `16 passed`.
- Phase 3 acceptance is complete: final project-lane live smoke artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase3_project_lane_live_smoke_after_hint_v1/project_lane_live_smoke.json` reached `6/12` cases with project evidence (`M02`, `M06`, `P04`, `P10`, `C07`, `C09`) and `6/12` without (`M03`, `P08`, `C01`, `K07`, `K09`, `K12`), meeting the `project_list <= 6/12` missing-count threshold.
- Phase 3 final implementation added metadata-hint filtering for project fallback documents, allowing sparse Crawl4AI pages to retain Tavily accepted candidate title/snippet context when evaluating project relevance. This converted `M06` from `executed_without_evidence` to `executed_with_evidence` for the GGZY "天河区柯木塱村城中村改造项目" candidate without changing protected public contracts.
- Phase 3 final validation passed: focused ruff/py_compile passed; focused source plan pytest `88 passed`; source regression `27 passed`; domestic regression `16 passed`; routing eval artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase3_routing_after_hint_v1` reports `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
- Phase 4 acceptance is complete: final data-metrics live smoke artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase4_data_metrics_live_smoke_v4/data_metrics_live_smoke.json` reached `7/12` cases with statistics evidence (`M02`, `M06`, `P04`, `P10`, `C07`, `K09`, `K12`). Against the Phase 0 missing-statistics baseline, remaining missing cases are `P08` and `C01`, so `statistics` missing count fell from `7/12` to `2/12`, meeting the `<=3/12` threshold.
- Phase 4 implementation added supplemental data-metrics Tavily+Crawl4AI fallback after direct profile failure, regional/exact-local domains for data-metrics tasks, broader quantity-validation triggers, direct data relevance rejection, and narrow exact-local government-work-report acceptance.
- Phase 4 final validation passed: focused ruff/py_compile passed; focused source plan pytest `92 passed`; source regression `27 passed`; domestic regression `16 passed`; routing eval artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase4_routing_v1` reports `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
- Phase 5 acceptance is complete: final official-record live smoke artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase5_official_record_live_smoke_v7` reached `4/5` cases with official-record evidence (`P08`, `C01`, `K09`, `K12`) and `1/5` explicit no-evidence gap (`K07`), with estimated direct fallback Tavily credits `10`. This meets the Phase 5 `environmental_or_land_record` target before Phase 7 audit.
- Phase 5 implementation added the internal `official_record` task family, official-record Tavily+Crawl4AI fallback, exact-local/parent official domains for 神木 and 若羌, narrow high-yield official-record phrases, PDF candidate skip behavior, broad `gov.cn` tightening for local official-record discovery, and document-level relevance checks against search-hint-only or late-boilerplate matches.
- Phase 5 final validation passed: focused ruff/py_compile passed; focused source/eval pytest `103 passed`; source regression `27 passed`; domestic regression `16 passed`; routing eval artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase5_routing_final_v1` reports `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
- Phase 5 caveat for Phase 6: `C01` still uses a broad Anhui natural-resources land-use case as official-record evidence. It should be tightened by evidence-quality scoring rather than treated as a Phase 5 blocker, because the missing-count target is already met and `K07` remains transparently unsupported.
- Phase 6 slice 1 implemented a generic official-record case-page rejection rule. `dxal` paths and `典型案例` official pages are now treated as weak narrative pages rather than strong environmental/land/regulatory records. The live C01 smoke at `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_scoring_c01_live_v1` reports `accepted_document_count=0` and `weak_document_rejections[].reason_code=generic_official_record_case_page`.
- Phase 6 slice 1 validation passed for touched files and source regressions: focused ruff/py_compile passed; lane execution tests `23 passed`; focused source PLAN suite `104 passed`; source regression `27 passed`; domestic regression `16 passed`. Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` lint debt.
- Phase 6 slice 2 implemented official-record adaptive third-phrase fanout. The lane still stops after accepted candidates, but it can try a third phrase when the first two phrases yield no accepted candidate. The 5-case smoke at `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_official_record_smoke_v2` reports `5 success`, estimated Tavily credits `14`, and `query_invalid_count=0`: `P08`, `K09`, and `K12` retained evidence; `C01` is rejected as `generic_official_record_case_page`; `K07` remains explicit no-evidence.
- Phase 6 slice 3 added explicit official-record fallback budget control. `DirectStructuredLaneExecutor` now accepts `max_official_record_fallback_search_credits`, records `max_estimated_tavily_credits`, `budget_state`, and `stop_reason` under existing `official_record_search_fallback` metadata, and stops fanout on `search_credit_budget_exhausted`. The live inspection harness exposes `--max-official-record-search-credits` and now passes `--max-candidates` into direct fallback candidate limits.
- Phase 6 slice 3 validation passed: focused ruff/py_compile passed; `pytest -q tests\test_sources_lane_execution.py tests\test_source_quality_live_inspection.py` -> `26 passed`; focused source PLAN suite -> `106 passed`; source regression -> `27 passed`; domestic regression -> `16 passed`. Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch lint debt.
- Phase 6 slice 3 live artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_official_record_smoke_cap2_v2` reports `5 success`, estimated Tavily credits `9`, average latency `12730.49 ms`, and `query_invalid_count=0`. Compared with cap=3 artifact `strong_evidence_phase6_official_record_smoke_v2` at `14` credits, cap=2 preserves evidence on `P08`, `K09`, and `K12`, keeps `C01` rejected as `generic_official_record_case_page`, and marks `K07` as explicit no-evidence / budget-exhausted.
- Phase 6 slice 4 completed: added `packages/sources/disclosure_api.py` with CNINFO direct announcement fallback after weak direct disclosure pages, `0` Tavily credit usage, China-local CNINFO timestamp normalization, and weak non-operating disclosure-title filtering. Disclosure-only live artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_disclosure_api_smoke_v3` reports `12/12` success and `12/12` enterprise-disclosure lanes with evidence at `0` estimated Tavily credits.
- Phase 6 slice 5 completed: official-record search now accepts region-matched subprovincial `.gov.cn` official domains with official-record signal while preserving wrong-region rejection. Diagnostic official-record artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_official_record_after_subprovincial_domain_v1` recovered `P08` official-record evidence under cap=2.
- Phase 6 final gate completed:
  - Routing artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_routing_after_disclosure_api_v1` -> `9 pass / 3 weak_pass`, `0 fail`, `0 blocker`.
  - Full live artifact `data/tmp/source_quality_stress_eval/runs/strong_evidence_phase6_live_final_v1` -> `12 success / 0 runtime error`, estimated Tavily credits `69`, average latency `21752.27 ms`, `query_invalid_count=0`.
  - Final strong-evidence coverage snapshot: `enterprise_disclosure=12/12`, `project_transaction=6/12`, `data_metrics=6/11 executed tasks`, `official_record=3/6 executed tasks`.
  - Final focused validation: ruff/py_compile passed; focused source PLAN suite `110 passed`; source regression `27 passed`; domestic regression `16 passed`.

Planning validation:

- `Test-Path .agent\PLANS\source-strong-evidence-adapter-remediation-v1.md` -> `True`.
- `Select-String` over `.agent\STATUS.md`, `.agent\PLANS\INDEX.md`, and the PLAN confirmed this PLAN is active and Phase 0 is the current next action.
- `git status --short -- .agent\PLANS\source-strong-evidence-adapter-remediation-v1.md .agent\STATUS.md .agent\PLANS\INDEX.md` shows only `.agent` planning artifacts for this step.
- No production code is intentionally changed in the PLAN creation step.

## Latest Source Evidence Coverage Remediation Snapshot

Created 2026-04-28, completed and archived 2026-04-29:

- `.agent/PLANS/archive/source-evidence-coverage-remediation-v1.md`

Baseline from `source-profile-adapter-remediation-v1` Phase 5:

- 12-case routing gate: `9 pass / 3 weak_pass`.
- 12-case live gate: `12 success / 0 runtime error`, estimated Tavily credits `22`, average latency `25921.55 ms`, `query_invalid_count=0`.
- DeepSeek audit: `3 blocker / 9 fail`, audit status `7 success / 5 invalid_schema`, total tokens `197281`.
- Batch blockers: `M06`, `P08`, `K09`.
- Full 50-case live source-quality run remains blocked.

Completed PLAN objective:

- Fix audit schema robustness so invalid-schema output is not confused with source blockers.
- Remediate evidence coverage for `M06` macro real-estate, `P08` Inner Mongolia energy/coal-chemical, and `K09` Shenmu coal/coal-chemical.
- Preserve explicit source gaps where a new adapter family is required.

Phase 1 completion snapshot:

- Phase 0 fixture is present at `data/tmp/source_quality_stress_eval/smoke_blockers_evidence_coverage_v1.json` with `M06`, `P08`, and `K09`.
- Added compact retry for parsed-but-invalid-schema DeepSeek audit responses in `data/tmp/_source_quality_llm_audit.py`.
- Added machine-readable `invalid_schema` diagnostics when retry cannot repair required fields.
- Added batch-report separation for audit shape diagnostics in `data/tmp/_source_quality_batch_report.py`.
- Focused validation passed: ruff, py_compile, and `pytest -q tests\test_source_quality_llm_audit.py tests\test_source_quality_batch_report.py` -> `5 passed`.
- Real artifact probe `data/tmp/source_quality_stress_eval/runs/evidence_coverage_phase1_audit_retry` reached `12` audit successes, `0` invalid schema rows, `audit_shape_diagnostic_count=0`, `3 blocker / 9 fail`, total tokens `181004`.
- Recovery proof: `recovered_from_invalid_schema` for `K09` and `M02`; `recovered_from_invalid_json` for `C01`, `C07`, `C09`, `K07`, `M06`, `P04`, and `P08`.
- After schema-noise removal, the current true blocker set is `C01`, `K07`, and `M06`.
- Recalibrated blocker fixture is `data/tmp/source_quality_stress_eval/smoke_blockers_evidence_coverage_phase1_actual_v1.json`.

Phase 2 completion snapshot:

- `M06` policy decomposition now uses central-domain-targeted phrases: `site:mohurd.gov.cn`, `site:www.gov.cn`, and `site:ndrc.gov.cn`.
- Search-assisted real-estate policy lane now strips broad `gov.cn` and keeps only central policy domains (`www.gov.cn`, `mohurd.gov.cn`, `ndrc.gov.cn`, `stats.gov.cn`).
- Source resolver now rejects non-central `.gov.cn` candidates in macro real-estate policy lane with `national_policy_non_central_domain` even if broad `gov.cn` is present in allowlists.
- Focused validation passed: `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_source_resolver.py tests\test_sources_search_assisted_domestic.py` -> `69 passed`.
- Required source/domestic regressions passed: `tests\test_sources_layer.py` (`8`), `tests\test_sources_adapters_v1.py` (`8`), `tests\test_sources_hardening_step34.py` (`4`), `tests\test_sources_evals_step35.py` (`7`), `tests\test_sources_router_domestic.py` (`2`), `tests\test_sources_profile_adapter.py` (`4`), `tests\test_sources_real_domestic_step42.py` (`4`), `tests\test_sources_pdf_step43.py` (`6`).
- Low-cost recalibrated routing eval passed: `data/tmp/source_quality_stress_eval/runs/evidence_coverage_phase2_m06_routing` -> `3 pass` (`C01`, `K07`, `M06`).
- Phase 2 was reopened after live validation found routing-only success insufficient: `data/tmp/source_quality_stress_eval/runs/evidence_coverage_phase2_m06_live_gate/per_query/M06.json` had `accepted_document_count=0`.
- Added official central seed fallback for M06 real-estate policy/data evidence and fixed coverage judging so a lane with sufficient accepted documents is not failed only because the candidate/extraction budget is fully used.
- New live artifact `data/tmp/source_quality_stress_eval/runs/evidence_coverage_phase2_m06_live_gate_after_seed_v2/per_query/M06.json` passed with `accepted_document_count=3`, accepted MOHURD and NBS URLs, `coverage_sufficient=true`, and local `.gov.cn` noise rejected as `off_domain_candidate`.
- Group3 validation passed: code-quality `PASS_WITH_KNOWN_DEBT`; functional validator `PASS`.
- Latest focused validation passed: source focused pytest `106 passed`, source regression `27 passed`, domestic regression `16 passed`; repo-wide ruff remains blocked only by known historical `data/tmp` lint debt.

Phase 3 completion snapshot:

- `C01` local-rollout candidate selection now prioritizes exact Hefei city official evidence over Anhui province or national fallback.
- Generic navigation/index/search pages and attachment-first hits are rejected before evidence extraction.
- Conditional Hefei GXJ official seed fallback is available only when no organic exact-city candidate exists.
- Latest C01 live artifact: `data/tmp/source_quality_stress_eval/runs/evidence_coverage_phase3_c01_live_v5/per_query/C01.json`.
- C01 local rollout accepted 3 Hefei `gxj.hefei.gov.cn` documents, `coverage_sufficient=true`, `fallback_level=exact_city`, and no province-level URL counted as evidence.
- Crawl4AI anti-bot/minimal-text failures remain explicit; fallback evidence is labeled `official_seed_fallback`.
- Validation passed: focused ruff/py_compile, source focused pytest `112 passed`, source regression `27 passed`, domestic regression `16 passed`; Group3 functional validation returned `PASS`.

Phase 4 completion snapshot:

- `K07` now has conditional Feixi county official seed fallback for verified `xf.ahfeixi.gov.cn` pages when no organic exact-county candidate exists.
- Hefei parent material is no longer accepted as exact Feixi proof; exact-county metadata is preserved with `fallback_level=exact_park_or_county`, `parent_evidence_only=false`, and `local_claim_allowed=true`.
- Latest K07 live artifact: `data/tmp/source_quality_stress_eval/runs/evidence_coverage_phase4_k07_live_v3/per_query/K07.json`.
- K07 local rollout accepted 3 Feixi `xf.ahfeixi.gov.cn` documents, `coverage_sufficient=true`, and Crawl4AI failures remain explicit with `official_seed_fallback_succeeded=3`.
- The K07 artifact now exposes `seed_excluded_domain_override=true`, `seed_exclusion_override_reason=verified_exact_local_seed_replaces_stale_search_discovery`, and `employment_or_labor_data_adapter_not_available`.
- Validation passed: focused ruff/py_compile, targeted K07/employment tests `2 passed`, source focused pytest `114 passed`, source regression `27 passed`, domestic regression `16 passed`.
- Residual risks: Feixi evidence uses seed fallback excerpts because Crawl4AI sees minimal-text pages; GGZY project lane still has a retryable `404`; customs/statistics lane still hits local certificate failure in this run.

Phase 5 completion snapshot:

- Routing gate artifact: `data/tmp/source_quality_stress_eval/runs/evidence_coverage_final_routing_v2` -> `9 pass / 3 weak_pass`, no fail/blocker.
- Live gate artifact: `data/tmp/source_quality_stress_eval/runs/evidence_coverage_final_live_v2` -> `12 success / 0 runtime error`, estimated Tavily credits `19`, average latency `13703.9 ms`, `query_invalid_count=0`.
- DeepSeek audit first hit a process timeout after writing 9 case audit files; rerun with `--resume` completed successfully.
- DeepSeek audit summary: `12 success`, verdicts `11 fail / 1 weak_pass`, total tokens `183928`, no blocker verdicts and no invalid schema rows.
- Batch report summary: live `12 success`, audit shape diagnostics `0`, blockers `0`.
- Main remaining systemic gaps: `company_disclosure` missing in `12/12`, `project_list` missing in `12/12`, `statistics` missing in `7/12`, `environmental_or_land_record` missing in `5/12`.
- Decision: current PLAN done condition is met because the blocker gate is cleared, but full 50-case live evaluation is not recommended until a successor strong-evidence adapter/profile remediation PLAN addresses these source classes.

## Latest Source Profile Adapter Remediation Snapshot

Created 2026-04-28:

- `.agent/PLANS/source-profile-adapter-remediation-v1.md`

Current baseline:

- Source Direct Structured Execution v1 Phase 7 routing smoke: `8 pass / 4 weak_pass`, `0 fail`, `0 blocker`.
- Source Direct Structured Execution v1 Phase 7 live smoke: `12 success / 0 runtime error`, estimated Tavily credits `20`, average latency `29012.79 ms`, `query_invalid_count=0`.
- Source Direct Structured Execution v1 Phase 7 DeepSeek audit: `7 success / 5 invalid_json`, verdicts `3 blocker / 9 fail`, total tokens `202538`.
- Remaining blocker cases: `K07`, `M03`, and `M06`.
- Full 50-case live source-quality run remains blocked until the 12-case audit gate reaches `<=2` blockers.

Current PLAN objective:

- Remediate source profile / adapter coverage and source routing precision for the three blockers.
- Add audit-harness robustness where invalid JSON creates false uncertainty.
- Preserve all protected EvidenceBundle, citation, research response, provider, and task/run contracts.

Current Phase 0 director gate result:

- Real-world validation plan added/refined in `.agent/PLANS/source-profile-adapter-remediation-v1.md`.
- Blocker inventory recorded for:
  - `K07`: Feixi/Hefei exact-local routing, county project/public-resource, land/EIA official-record gap, parent-fallback labeling, and company-disclosure precision.
  - `M03`: missing CAAC / aviation regulator profile coverage, airspace reform, airworthiness, low-altitude infrastructure/procurement execution, local pilot evidence, and enterprise-order/company-disclosure hints.
  - `M06`: missing MOHURD / central real-estate policy targeting, real-estate statistics facets, project/list evidence, downstream enterprise disclosure hints, and rejection of arbitrary local/generic homepage evidence.
- Group 2 / Group 3 assignments are now explicit in the PLAN.
- Phase 1 authorized scope is audit/fixture-only; no `packages/sources/**` production source/profile changes before Phase 1 checks complete.

Phase 1 completion snapshot:

- `_source_quality_llm_audit.py` retries truncated/invalid JSON with a compact no-reasoning retry.
- Unrecovered parser failures remain `invalid_json` with diagnostics and do not become audit passes.
- `tests/test_source_quality_llm_audit.py` covers fenced JSON recovery and truncated-response retry.
- Validation: focused ruff -> pass; py_compile -> pass; `pytest -q tests\test_source_quality_llm_audit.py` -> `2 passed`; blocker fixture load assertion -> `['M03', 'M06', 'K07']`.
- Group3 code-quality and functional validation both passed. Functional artifact: `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase1_validation/functional_validation.json`.

Phase 2 completion snapshot:

- Added low-altitude regulator/source facets for `M03`, including CAAC / aviation regulator official discovery, airspace reform, airworthiness, infrastructure, local-pilot, and enterprise-disclosure query facets.
- `M03` now decomposes into policy direction, local rollout, project transaction, enterprise disclosure, industry topic, and data metrics tasks.
- Retrieval lanes now include provincial policy rollout and industry-association supplemental evidence for low-altitude macro queries.
- 3-case blocker live inspection artifact: `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase2_blockers` -> `3 success / 0 runtime error`, estimated Tavily credits `5`, `query_invalid_count=0`.
- `M03` live artifact accepted CAAC official pages from `www.caac.gov.cn` and Crawl4AI fetched CAAC content successfully.
- Validation: focused ruff/py_compile -> pass; focused source pytest -> `82 passed`; source regression -> `27 passed`; domestic checks -> `16 passed`; Group3 code-quality gate -> pass with known repo-wide `data/tmp` ruff debt; Group3 functional gate -> pass with artifact `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase2_validation/functional_validation.json`.
- Remaining Phase 2 risk: `project_transaction` is executed but still returns `executed_without_evidence`; local-pilot evidence may need later profile/adapter work.

Phase 3 completion snapshot:

- Added macro real-estate theme recognition for `M06`.
- Policy routing now targets MOHURD / State Council / NDRC / NBS domains and no longer uses broad `gov.cn`.
- Query facets now include destocking, urban village renovation, three major projects, local acquisition/storage, starts/completions/sales/inventory, downstream demand, and enterprise revenue/disclosure.
- Retrieval no longer requires `city_county_fallback` for this macro query.
- Search-assisted candidate filtering now prevents real-estate macro policy tasks from widening to arbitrary local `*.gov.cn` pages.
- 3-case routing artifact: `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase3_routing` -> `3 pass`.
- 3-case live artifact: `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase3_blockers_v2` -> `3 success / 0 runtime error`, estimated Tavily credits `4`, `query_invalid_count=0`.
- `M06` live artifact rejected local policy candidates from domains such as `zjt.fujian.gov.cn`, `jw.shenyang.gov.cn`, `cgzf.sh.gov.cn`, `zjw.sh.gov.cn`, and `www.hunan.gov.cn` as `off_domain_candidate`.
- Validation: focused ruff/py_compile -> pass; focused source pytest -> `94 passed`; source regression -> `27 passed`; domestic checks -> `16 passed`; Group3 code-quality gate -> pass with known repo-wide `data/tmp` ruff debt; Group3 functional gate -> pass with artifact `data/tmp/source_quality_stress_eval/runs/profile_remediation_phase3_validation/functional_validation.json`.
- Remaining Phase 3 risk: central policy pages did not land in the latest live run; the lane now reports `partial` / `budget_exhausted` instead of accepting weak local pages. Project/statistics/disclosure lanes still often return `executed_without_evidence`; `cn_project_ggzy_trade_v1` may need later profile refresh due retryable 404 on `https://www.ggzy.gov.cn/jyxx/`.

Phase 4 completion snapshot:

- `K07` local rollout now keeps county/city official domains: `ahfeixi.gov.cn`, `hefei.gov.cn`, `fgw.hefei.gov.cn`, `gxj.hefei.gov.cn`, `jxj.hefei.gov.cn`, and `tjj.hefei.gov.cn`.
- Stale `xf.ahfeixi.gov.cn` search-indexed pages are excluded from the local rollout discovery budget because they return stale 404/minimal-text pages.
- `K07` no longer accepts stale Feixi Pioneer pages or broad Anhui province-level material as exact county proof.
- If no exact county/city official candidate is found, the artifact records `coverage_sufficient=false`, `accepted_candidate_count=0`, and preserves `parent_evidence_only=true` / `local_claim_allowed=false` semantics.
- Land/EIA remains an explicit `official_record_adapter_not_available` gap; no new adapter family was introduced.
- Phase 4 validation: focused ruff/py_compile -> pass; focused source pytest -> `97 passed`; source regression -> `27 passed`; domestic checks -> `16 passed`; 3-case routing -> `3 pass`; 3-case live -> `3 success / 0 runtime error`, estimated Tavily credits `5`, `query_invalid_count=0`.
- Group3 code-quality and functional validation both passed.

Current Phase 5 next action:

- Run the final 12-case routing/live/audit/batch gate.

Phase 0 local inventory update:

- Added `data/tmp/source_quality_stress_eval/smoke_blockers_profile_remediation_v1.json` for low-cost targeted validation of `M03`, `M06`, and `K07`.
- Existing enabled registry coverage includes CCGP/GGZY/NDRC project profiles, CNINFO/SSE/SZSE disclosure lane candidates, national statistics, Anhui statistics, and Anhui policy/industry/commerce profiles.
- Missing registered coverage: CAAC / civil-aviation regulator profile, MOHURD / housing ministry profile, Feixi/Hefei project profile, and domestic land/EIA official-record profile.
- Artifact issue: `batch_eval.json` is parseable and authoritative, but some per-query artifacts under `direct_exec_final_live/per_query/*.json` fail `ConvertFrom-Json` because malformed/mojibake JSON strings break parsing. This is a Phase 1 audit/runtime robustness input.

Planning validation:

- `Test-Path .agent\PLANS\source-profile-adapter-remediation-v1.md` is required.
- `Select-String` over `.agent\STATUS.md` and `.agent\PLANS\INDEX.md` must confirm this PLAN is the active PLAN.
- No production code is intentionally changed in the PLAN creation step.

## Latest Source Quality Stress Eval Snapshot

Created 2026-04-28:

- `.agent/PLANS/source-quality-stress-eval-v1.md`

Latest execution snapshot on 2026-04-28:

- API smoke gate passed for DeepSeek `deepseek-v4-pro`: HTTP 200, JSON output, reasoning token usage observed.
- API smoke gate passed for Tavily key validity using English and `site:` low-cost queries: HTTP 200 with one result each.
- Tavily returned HTTP 400 `Query is invalid` for one pure Chinese smoke query, so live inspection must preserve query-invalid diagnostics and support rewrite/fallback planning.
- Phase 0 Architecture Gate completed with required PLAN sections present.
- Phase 1 completed in `data/tmp` scope:
  - `data/tmp/source_quality_stress_eval/source_quality_cases_v1.json` contains 50 cases.
  - `data/tmp/source_quality_stress_eval/smoke_cases_v1.json` contains 12 smoke IDs.
  - `data/tmp/_source_quality_routing_eval.py` provides offline routing inspection.
  - Artifacts were written to `data/tmp/source_quality_stress_eval/runs/manual_smoke_routing` and `data/tmp/source_quality_stress_eval/runs/full_routing`.
- Phase 1 validation:
  - `python -m py_compile data\tmp\_source_quality_routing_eval.py` -> pass
  - JSON load check -> `source_quality_cases_v1.json ok 50`, `smoke_cases_v1.json ok 12`
  - Smoke routing -> `12 cases: 10 weak_pass, 2 fail, 0 blocker`
  - Full routing -> `50 cases: 43 weak_pass, 7 fail, 0 blocker`
- Main routing quality signals:
  - all 50 cases are missing at least one expected lane
  - 7 city/county cases missed `city_county_fallback`
  - no direct-keep blocker was detected by the offline harness
- Local persistent key handling:
  - `E:\invest_agent\.env` exists for local-only Tavily/DeepSeek credentials and source-eval defaults.
  - `.env` is gitignored; PLAN/STATUS/scripts/artifacts must not contain raw key values.
  - Source-quality eval scripts now auto-load `.env` and record only key presence booleans.
  - `.env` was normalized to UTF-8 without BOM after the first loader check missed `TAVILY_API_KEY`.
  - Current working copy of tracked `command.txt` was redacted to placeholders after secret-like key tokens were found; a follow-up scan found `0` secret-like matches outside `.env`.
  - Risk: repository history/baseline may still contain an old key in `command.txt`; rotate that key if it is still valid.
- Phase 2 live smoke completed:
  - command: `python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\smoke_cases_v1.json --mode extraction_inspection --max-rounds 2 --max-candidates 3 --output-dir data\tmp\source_quality_stress_eval\runs\manual_smoke --print-json`
  - result: `12` cases, `10 success`, `2 error`, `22` estimated Tavily credits, average latency `8962.21 ms`
  - artifacts: `data/tmp/source_quality_stress_eval/runs/manual_smoke/per_query`, `raw_traces`, `crawl4ai_excerpts`, and `live_summary.json`
- Phase 3 DeepSeek audit completed:
  - model: `deepseek-v4-pro`
  - thinking: `enabled`
  - reasoning effort: `max`
  - final audit summary: `12` cases, `11 success`, `1 invalid_json`, verdicts `9 blocker`, `3 fail`, `91144` total tokens
  - first full audit attempt timed out after partial progress; `_source_quality_llm_audit.py` now supports `--resume`
  - no private reasoning content or raw secret values are stored in artifacts
- Phase 4 batch roadmap completed:
  - artifacts: `data/tmp/source_quality_stress_eval/runs/manual_smoke/batch_eval.json` and `source_roadmap.json`
  - batch summary: `12` queries, live `10 success / 2 error`, audit `9 blocker / 3 fail`, `9` reopening-plan items
  - top missing source classes: `company_disclosure` (`12`), `project_list` (`11`), `local_government` (`7`), `statistics` (`7`), `environmental_or_land_record` (`4`)
- Phase 5 decision:
  - full 50-case live run is deferred by PLAN stop condition because smoke already found production remediation blockers.
  - next work should create/select a remediation PLAN before spending more Tavily/DeepSeek budget on full live runs.
- Final verification snapshot:
  - `python -m py_compile data\tmp\_source_quality_routing_eval.py data\tmp\_source_quality_live_inspection.py data\tmp\_source_quality_llm_audit.py data\tmp\_source_quality_batch_report.py` -> pass
  - `.env` loader check -> Tavily and DeepSeek keys present, model default set, no values printed
  - `git check-ignore -v .env` -> `.gitignore:9:.env`
  - secret-like scan outside `.env` -> `0` matches

## Latest Source Routing Remediation Snapshot

Created 2026-04-28:

- `.agent/PLANS/archive/source-routing-remediation-v1.md`

Final result:

- Status: `completed`
- Phase 1 fixed Crawl4AI Windows Unicode/GBK runtime extraction failures.
- Phase 2 fixed first-wave city/county/province routing hints and preserved local search-assisted lanes for C01/C07/K07/K09/K12-style cases.
- Phase 3 made required direct structured lanes visible as control gaps using `direct_structured_primary_path_required` while preserving direct-keep primary paths.
- Phase 4 hardened `data/tmp/_source_quality_batch_report.py` against Windows/GBK JSON output failures.
- Phase 5 re-ran the 12-case smoke set and recorded the full-run gate decision.

Validation snapshot:

- `pytest -q tests\test_sources_crawl4ai_extraction.py` -> `8 passed`
- `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_source_resolver.py tests\test_sources_crawl4ai_extraction.py tests\test_sources_search_assisted_domestic.py` -> `88 passed`
- `python -m ruff check packages\sources\retrieval_plan.py tests\test_sources_retrieval_plan.py` -> pass
- Focused ruff for touched source/test/eval files -> pass
- Focused py_compile for touched source/test/eval files -> pass
- Routing smoke artifact: `data/tmp/source_quality_stress_eval/runs/remediation_phase3_routing` -> `8 pass / 4 weak_pass`
- Live smoke artifact: `data/tmp/source_quality_stress_eval/runs/remediation_smoke_live` -> `12 success / 0 error`, estimated Tavily credits `21`, average latency `14817.63 ms`, `query_invalid_count=0`
- DeepSeek audit on remediation live artifact -> `10 success / 2 invalid_json`, verdicts `5 blocker / 7 fail`, total tokens `183719`
- Batch roadmap artifact: `data/tmp/source_quality_stress_eval/runs/remediation_smoke_live/source_roadmap.json`

Full 50-case live decision:

- Deferred. Runtime and first-wave routing blockers improved, but the remediation smoke audit still has `5` blockers.
- The next PLAN should address direct structured lane execution, lane-budget scheduling, and stronger evidence coverage for project/procurement, statistics, disclosure, and environmental/land records.

Historical design:

- Phase 1 fixes Crawl4AI Windows Unicode/GBK runtime extraction failures first.
- Phase 2 fixes explicit city/county region detection and preserves local search-assisted lanes for C01/C07/K07/K09/K12-style cases.
- Phase 3 makes direct-keep source-class gaps deterministic and visible without routing direct adapters through Tavily.
- Phase 4 hardens eval roadmap aggregation.
- Phase 5 re-runs smoke and decides whether full 50-case live evaluation is cost-justified.

## Latest Source Direct Structured Execution Snapshot

Created 2026-04-28:

- `.agent/PLANS/source-direct-structured-execution-v1.md`

Current design:

- The next work is not broad source expansion. It is a lane-aware execution bridge for required direct structured lanes.
- Required direct lanes must end in one of: `executed_with_evidence`, `executed_without_evidence`, `skipped_budget_exhausted`, `skipped_no_adapter`, `skipped_unsupported_source_class`, `refused_direct_keep_boundary`, or `failed_runtime_error`.
- Search-assisted lanes continue to use Tavily + Crawl4AI.
- Direct structured lanes should use existing `SourceRegistry`, `SourceToolRegistry`, `GenericProfileSourceAdapter`, and available profiles first.
- Missing direct adapters must produce precise unsupported gaps, not silent omissions.
- Full 50-case live eval remains blocked until the 12-case smoke audit reduces from `5` blockers to `<=2` and no blocker is caused by required direct lanes not being executed.

Phase 0 next action:

- Inventory `CoverageLane -> SourceIntent -> SourceProfile / adapter availability`.
- Decide whether `environmental_or_land_record` can remain a project/regulatory sub-intent in v1 or needs a new source-layer lane.
- No production code should change before the Phase 0 Architecture Gate is recorded in the PLAN.

Planning validation:

- `Test-Path .agent\PLANS\source-direct-structured-execution-v1.md` -> `True`
- `Select-String` over `.agent\STATUS.md`, `.agent\PLANS\INDEX.md`, and the PLAN confirmed the active PLAN, `planned` status, and Phase 0 next action.
- No production code was intentionally changed in this planning step.
- Dirty worktree remains broad from prior work; future implementation must use focused scope review.
- STATUS cleanup completed: older Crawl4AI remediation phase results are explicitly excluded from this PLAN's progress.

Execution status:

- Phase 0 Architecture Gate completed on 2026-04-28.
- Inventory found 71 registered profiles, 67 enabled profiles, profile-backed coverage for project/statistics/disclosure lanes, sparse city/county coverage, and no domestic environmental/land-record direct profile.
- Phase 1 Lane Execution Contract and Scheduler completed on 2026-04-28.
- Added internal direct structured lane execution through existing profile-backed adapters and updated live inspection so direct lanes are not silently filtered out when search tasks are capped.
- Added M02 regression coverage so national computing queries with explicit `地方项目清单` / `建设需求` keep the `project_transaction` direct lane.
- Phase 1 validation:
  - focused source/query/lane pytest -> `75 passed`
  - source regression pytest -> `27 passed`
  - domestic source pytest -> `16 passed`
  - focused source/test ruff and py_compile -> pass
  - repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt
  - low-cost live smoke `data/tmp/source_quality_stress_eval/runs/direct_exec_phase1_smoke` -> `12 success / 0 error`, estimated Tavily credits `12`, `query_invalid_count=0`
  - M02 direct-only artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_phase1_m02_direct_only` -> `project_transaction`, `enterprise_disclosure`, and `data_metrics` all reached `executed_with_evidence` with `0` Tavily credits
- Phase 2 Project / Procurement / Public Resource Lane completed on 2026-04-28.
- Added Xi'an/Shaanxi regional routing hints and `商业航天` / `硬科技` theme recognition so C09 project phrases no longer receive a generic `全国` prefix.
- Added project-lane weak-document filtering so generic homepages/list pages such as `ccgp.gov.cn` 首页 do not count as valid project evidence.
- Phase 2 validation:
  - focused lane/query/retrieval pytest -> `61 passed`
  - source regression pytest -> `27 passed`
  - domestic source pytest -> `16 passed`
  - focused source/test ruff and py_compile -> pass
  - project direct-only artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_phase2_project_direct_only_v2` -> `M02`, `P08`, `C09` all attempted `project_transaction`; all returned `executed_without_evidence` with `weak_document_rejections` instead of false homepage evidence; estimated Tavily credits `0`
- Phase 3 Statistics / Data Metrics Lane completed on 2026-04-28.
- Added data-metrics preservation for direct-keep/disclosure queries that explicitly ask for price, capacity, scale, statistics, or data evidence.
- Added `cn_data_nmg_stats_bulletin_v1` and changed data lane source ordering to prefer regional statistics profiles before national statistics where available.
- Added weak statistics homepage filtering so generic `stats.gov.cn/english/` style pages no longer count as valid data evidence.
- Phase 3 validation:
  - focused lane/query/retrieval/source-resolver pytest -> `73 passed`
  - source regression pytest -> `27 passed`
  - domestic source pytest -> `16 passed`
  - focused source/test ruff and py_compile -> pass
  - repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt
  - stats direct-only artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_phase3_stats_direct_only` -> `M02`, `M06`, `P08`, `C07` all generated or executed `data_metrics`; `M02`/`M06`/`P08` returned `executed_without_evidence` with generic statistics homepage rejections; `P08` attempted `cn_data_nmg_stats_bulletin_v1` before national statistics; `C07` recorded Jiangsu statistics/commerce HTTP 403 as structured runtime failure, not false data evidence
- Do not treat the completed Crawl4AI GBK remediation from `.agent/PLANS/archive/source-routing-remediation-v1.md` as progress for this PLAN.
- Phase 4 Enterprise Disclosure Lane completed on 2026-04-28.
- Added enterprise-disclosure preservation for blocker queries that ask for enterprise revenue, orders, investment, downstream demand, local funds, or company evidence.
- Added weak disclosure filtering so CNINFO generic homepages and SSE non-disclosure party-building pages no longer count as company disclosure evidence.
- Changed generic `上市公司` wording to a missing-company limitation instead of a company hint.
- Phase 4 validation:
  - focused disclosure lane pytest -> `2 passed`
  - focused lane/query/retrieval/search-assisted pytest -> `82 passed`
  - source regression pytest -> `27 passed`
  - domestic source pytest -> `16 passed`
  - focused source/test ruff and py_compile -> pass
  - focused source/test glob ruff -> pass
  - repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt
  - disclosure direct-only artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_phase4_disclosure_direct_only` -> `M02`, `M06`, `P08`, `C07`, and `C09` all generated and attempted `enterprise_disclosure`; all ended `executed_without_evidence` with `missing_company_hint=true`, `document_count=0`, `rejected_document_count=2`, and weak-document rejections for CNINFO `首页` and SSE `党建动态`; estimated Tavily credits `0`
- Phase 5 Environmental / Land / Regulatory Records completed on 2026-04-28.
- Added deterministic official-record need detection for EIA, natural-resources, land-transfer, project-filing, land, energy-consumption, project-approval, and filing queries.
- Added `official_record_adapter_not_available` coverage gaps on the existing `project_transaction` lane, with `fallback_source=environmental_or_land_record`; no new public CoverageLane, EvidenceBundle, citation, API, task, or run contract was introduced.
- Updated live inspection artifacts to include compact retrieval-plan lanes/gaps/planner metadata so official-record gaps are visible in real inspection outputs.
- Added Phase 5 smoke case file `data/tmp/source_quality_stress_eval/smoke_official_records_phase5.json` for `P08`, `K07`, `K09`, `K12`, and `C01`.
- Phase 5 validation:
  - focused official-record tests -> `2 passed`
  - focused retrieval/query/lane/search-assisted pytest -> `84 passed`
  - source regression pytest -> `27 passed`
  - domestic source pytest -> `16 passed`
  - focused source/test/eval ruff and py_compile -> pass
  - focused source/test glob ruff -> pass
  - repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt
  - routing artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_phase5_routing` -> `5 pass / 0 fail`; all five cases include `official_record_adapter_not_available`
  - direct-only live artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_phase5_official_records_direct_only` -> `4 success / 1 error`, estimated Tavily credits `0`; `K07` has the official-record gap but no selected direct task under `--max-search-tasks 0`, which is now the first Phase 6 scheduling issue
- Phase 6 first remediation completed on 2026-04-28:
  - Park/city holdout remains local-only for generic park policy queries.
  - Park/county queries that explicitly ask for project clusters, real projects, land, enterprise evidence, announcements, statistics, capacity, prices, or labor data now preserve direct control lanes.
  - Live inspection now orders direct structured tasks before capped search-assisted tasks.
  - Direct-only official-record artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_phase6_official_records_direct_only` -> `5 success / 0 error`, estimated Tavily credits `0`, fixing the previous K07 empty-execution issue.
  - Focused Phase 6 validation: targeted park/K07 pytest -> `6 passed`; focused retrieval/query/lane/search-assisted pytest -> `85 passed`; focused ruff/py_compile -> pass; UTF-8 case-file task-order validation passed with order `enterprise_disclosure`, `project_transaction`, then `local_rollout`.
  - Full 12-case Phase 6 low-cost smoke initially exposed remaining `M06` / `C07` project-lane omissions.
- Phase 6 final remediation completed on 2026-04-28:
  - Added RED/GREEN regressions so `M06` real-estate / three-projects queries and `C07` Changzhou capacity-risk queries preserve `project_transaction` when they ask for `开工`, `投产`, `资金来源`, `项目备案`, or `土地项目` evidence.
  - `packages/sources/query_decomposition.py` now maps those project execution terms to `project_transaction` in both generic decomposition and disclosure-direct-keep branches.
  - Direct-only artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_phase6_smoke_direct_only_v2` -> `12 success / 0 error`, estimated Tavily credits `0`; `M06` and `C07` now execute `project_transaction`.
  - Low-cost live artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_phase6_smoke_lowcost_v2` -> `12 success / 0 error`, estimated Tavily credits `12`, average latency `14804.15 ms`, `query_invalid_count=0`.
  - Batch report `data/tmp/source_quality_stress_eval/runs/direct_exec_phase6_smoke_lowcost_v2/batch_eval.json` -> `12 success`, no runtime blockers in the non-LLM batch layer.
  - Blocker-driving cases `M02`, `M06`, `P08`, `C07`, and `C09` all show required direct-lane execution attempts or structured runtime/no-evidence states.
  - Validation: RED tests failed first, then targeted project-lane tests -> `2 passed`; focused query/retrieval/lane/search-assisted pytest -> `87 passed`; source regression pytest -> `27 passed`; domestic source pytest -> `16 passed`; focused source/test ruff and py_compile -> pass.
  - `python -m ruff check .` still fails only on known historical `data/tmp` scratch/demo lint debt, not touched Phase 6 files.
- Phase 7 smoke audit and full-run gate executed on 2026-04-28:
  - Routing smoke artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_final_routing` -> `8 pass / 4 weak_pass`, `0 fail`, `0 blocker`.
  - Live smoke artifact `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live` -> `12 success / 0 runtime error`, estimated Tavily credits `20`, average latency `29012.79 ms`, `query_invalid_count=0`.
  - DeepSeek audit on `direct_exec_final_live` -> `7 success / 5 invalid_json`, verdicts `3 blocker / 9 fail`, total tokens `202538`.
  - Batch report `data/tmp/source_quality_stress_eval/runs/direct_exec_final_live/batch_eval.json` confirms blockers: `K07`, `M03`, and `M06`.
  - Remaining blockers are source coverage / adapter / source-profile issues, not silent direct-lane scheduling omissions.
  - Full 50-case live eval remains deferred because the `<=2` blocker gate was not met.

## Latest Domestic Source Coverage Routing Snapshot

Created 2026-04-28:

- `.agent/PLANS/domestic-source-coverage-and-routing-v2.md`

The new PLAN formalizes the recent design decisions:

- C first: define CoverageLane and RetrievalPlan before broad source expansion.
- DeepSeek may act as a constrained retrieval planner/evaluator, not a free-form search agent.
- Deterministic code owns source-role compatibility, domain strategies, direct-keep boundaries, and schema repair/refusal.
- Tavily remains search discovery and Crawl4AI remains page extraction.
- City/county coverage uses an official-domain-first fallback ladder instead of one maintained profile per city/county.
- Q03 regression is explicit: `广东人形机器人产业政策和项目落地情况` must not route humanoid robotics policy lanes through low-altitude/aviation supplemental domains.

Phase 0 director gate result:

- CoverageLane v1 scope frozen to the nine lanes in the active PLAN.
- RetrievalPlan v1 is a source-layer planning contract, not an API response-shape or EvidenceBundle schema change.
- Public RetrievalPlan types should live in `packages/sources/retrieval_plan.py`; Phase 1 must not add them to `packages/sources/schemas.py`.
- `SRC-COV-01..10` are frozen as the first eval cases. The Chinese text in the PLAN is valid UTF-8; display mojibake is a console/rendering issue.
- Group2 Phase 1 assignment order: `system_contract_architect` first, then `source_provider_integrator`; optional `eval_harness_implementer` only if the Architecture Gate requires a small offline eval helper.
- Group3 validation must include focused code-quality checks, Q03 negative-domain validation, direct-keep checks, unknown supplemental-theme non-fanout, and city/county plus park/zone fallback cases.
- Production code was not changed by the director gate.

Phase 1 Architecture Gate result:

- Decision: `proceed`.
- RetrievalPlan v1 remains a source-layer planning contract, not an API response, EvidenceBundle, citation, `source_quality_summary`, or research analyze shape change.
- Public RetrievalPlan types remain assigned to `packages/sources/retrieval_plan.py`; Phase 1 must not add them to `packages/sources/schemas.py`.
- Current gate write scope was limited to `.agent/PLANS/domestic-source-coverage-and-routing-v2.md` and `.agent/STATUS.md`; production code was not changed.
- Approved implementation scope: `packages/sources/retrieval_plan.py`, `packages/sources/query_decomposition.py`, `tests/test_sources_retrieval_plan.py`, focused additions to `tests/test_sources_query_decomposition.py`; optional offline `data/tmp/_retrieval_plan_phase1_eval.py` only if needed.
- Forbidden implementation scope: `packages/sources/schemas.py`, `packages/agents/workflow.py`, `packages/providers/**`, `packages/core/config.py`, protected API/evidence/task/content/delivery contracts, and broad `packages/sources/profiles/**` expansion.
- Mandatory Phase 1 validation includes Q03 negative-domain exclusion, direct-keep preservation, unknown supplemental-theme non-fanout, deterministic fallback without credentials, and city/county plus park fallback semantics that do not claim local coverage from parent-level evidence.

Phase 1 implementation and validation result:

- `packages/sources/retrieval_plan.py` now contains source-layer RetrievalPlan v1 contracts and deterministic fallback planning.
- `packages/sources/query_decomposition.py` was repaired so `local_rollout` does not inherit supplemental domains and unknown supplemental themes do not fan out to all supplemental domains.
- Focused tests were added in `tests/test_sources_retrieval_plan.py` and `tests/test_sources_query_decomposition.py`.
- Functional remediation added customs/commerce/export coverage for `SRC-COV-04` and prevented policy-only computing-infrastructure queries from forcing a project lane.
- Validation snapshot:
  - `python -m ruff check packages\sources\retrieval_plan.py packages\sources\query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py` -> pass
  - `python -m py_compile packages\sources\retrieval_plan.py packages\sources\query_decomposition.py tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py` -> pass
  - `pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py` -> `42 passed`
  - `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`
  - `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`
  - Functional validator field artifact: `data/tmp/retrieval_plan_field_validation_20260428.json`
- Repo-wide `python -m ruff check .` still fails on unrelated historical `data/tmp` scratch/demo scripts; focused Phase 1 files pass.
- Scope caveat: forbidden-path dirty files remain from the pre-existing dirty worktree recorded in `.agent/WORKTREE_INVENTORY.md`; no destructive cleanup or reversion was performed.

Phase 2 Architecture Gate result:

- Decision: `proceed`.
- Affected contracts: provider abstraction may be consumed through existing `JsonProviderClient` / `DeepSeekProviderClient.generate_json`; config may reuse existing DeepSeek settings or add only backward-compatible planner-specific settings; source-layer `RetrievalPlan` is the only planning contract touched.
- Protected contracts remain unchanged: API responses, EvidenceBundle, EvidenceItem citation fields, `source_quality_summary`, research analyze response, source routing response, task/job semantics, `run` / `run_steps`, content asset metadata, and delivery transitions.
- Approved implementation scope: `packages/sources/retrieval_planner_deepseek.py`, `tests/test_sources_retrieval_planner_deepseek.py`, focused `tests/test_deepseek_provider.py`; `packages/providers/**` or `packages/core/config.py` only if narrow and backward-compatible.
- Forbidden implementation scope: `packages/agents/workflow.py`, `packages/sources/schemas.py`, protected evidence/API/task/content/delivery contracts, broad profile expansion, direct-keep weakening, credential persistence, private reasoning storage, invented domains/lanes/source intents/domain strategies.
- DeepSeek planner contract: prompt must produce strict RetrievalPlan-compatible JSON only; schema validation is mandatory; repair once then deterministic fallback; no private reasoning, no secrets, no direct answers, no invented domains/lanes.
- Phase 2 validation must include missing-key fallback, mock invalid JSON, invalid enum/schema repair/refusal, refusal/direct-answer fallback, no-secret metadata checks, focused ruff/py_compile/pytest, source regression, forbidden-path scope check, and optional live smoke only when `DEEPSEEK_API_KEY` exists in the current process.
- Current gate write scope was limited to `.agent/PLANS/domestic-source-coverage-and-routing-v2.md` and `.agent/STATUS.md`; production code was not changed.

Phase 2 implementation and validation result:

- `packages/sources/retrieval_planner_deepseek.py` now provides optional DeepSeek-assisted RetrievalPlan planning through the existing `JsonProviderClient` boundary.
- `tests/test_sources_retrieval_planner_deepseek.py` covers missing-key fallback, fake valid provider output, invalid enum/schema fallback, metadata-only repair, invented-field rejection, direct-keep preservation, deterministic authoritative-field enforcement, secret-like phrase filtering, and no reasoning/secret metadata persistence.
- Deterministic `build_retrieval_plan(query)` remains credential-free and unchanged as the safe default path.
- DeepSeek provider output can only safely contribute filtered search/exact phrases and negative terms; deterministic code remains authoritative for `plan_id`, round policy, stop conditions, coverage gaps, source intents, domain strategy, execution bucket, fallback ladder, allowed domains, and direct-keep boundaries.
- Validation snapshot:
  - `python -m ruff check packages\sources\retrieval_planner_deepseek.py tests\test_sources_retrieval_planner_deepseek.py tests\test_deepseek_provider.py` -> pass
  - `python -m py_compile packages\sources\retrieval_planner_deepseek.py tests\test_sources_retrieval_planner_deepseek.py tests\test_deepseek_provider.py` -> pass
  - `pytest -q tests\test_sources_retrieval_planner_deepseek.py tests\test_deepseek_provider.py` -> `10 passed`
  - `pytest -q tests\test_sources_retrieval_plan.py tests\test_sources_query_decomposition.py` -> `42 passed`
  - `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`
  - Domestic source regression validator reported `16 passed`
  - Functional validator artifact: `data/tmp/deepseek_retrieval_planner_functional_validation_20260428.json`
- Optional live DeepSeek smoke was skipped because `DEEPSEEK_API_KEY` was absent in the current process.
- Repo-wide `python -m ruff check .` still fails on unrelated historical `data/tmp` scratch/demo scripts; focused Phase 2 files pass.
- Scope caveat remains: dirty forbidden files from `.agent/WORKTREE_INVENTORY.md` are still present, so git cannot prove Phase 2 scope from a clean baseline. No destructive cleanup or reversion was performed.

Phase 3 Architecture Gate result:

- Decision: `proceed`.
- Affected contracts: source resolver and compatibility gate may affect only source-layer execution planning, source intent resolution, candidate decisions, rejection reason metadata, and source-layer coverage gap handling.
- Protected contracts remain unchanged: API responses, EvidenceBundle, EvidenceItem citation fields, `source_quality_summary`, research analyze response shape, provider abstraction semantics, source routing response shape, task/job semantics, `run` / `run_steps`, content asset metadata, and delivery state transitions.
- Approved implementation scope: `packages/sources/source_resolver.py` if needed, `packages/sources/search_assisted_domestic.py`, `packages/sources/query_decomposition.py`, `tests/test_sources_source_resolver.py`, focused `tests/test_sources_search_assisted_domestic.py`, and focused `tests/test_sources_query_decomposition.py`.
- Forbidden implementation scope: `packages/sources/schemas.py`, `packages/agents/workflow.py`, `packages/providers/**`, `packages/core/config.py`, broad `packages/sources/profiles/**` or `packages/sources/packs.py` expansion, protected downstream contracts, and direct-keep weakening.
- Compatibility gate design: enforce domain strategy, source-role compatibility, region match, theme alias match, negative-term rejection, supplemental-not-primary separation, direct-keep boundary violation handling, and city/county/park parent fallback gap semantics.
- Migration path: keep existing `QueryDecompositionTask` source-assisted execution available; add a source-layer resolver that consumes RetrievalPlan lanes and bridges internally to existing task/orchestrator inputs without changing callers or public response contracts.
- Phase 3 validation must include Q03 negative-domain, unknown supplemental no fanout, direct-keep preserved, city/park fallback gap, candidate rejection reason codes, focused pytest, source regression, domestic source regression, and forbidden-path scope review.
- Current gate write scope was limited to `.agent/PLANS/domestic-source-coverage-and-routing-v2.md` and `.agent/STATUS.md`; production code was not changed.

Phase 3 implementation and validation result:

- `packages/sources/source_resolver.py` now provides the first typed compatibility gate for search-assisted candidate decisions.
- `packages/sources/search_assisted_domestic.py` now calls the resolver before Crawl4AI extraction and reports rejection reason codes for domain/topic/role/region/negative-term/direct-keep/unsupported-lane failures.
- `packages/sources/query_decomposition.py` now carries negative terms for humanoid robotics policy/local/data tasks and keeps unknown supplemental themes from fanning out.
- Focused tests were added or extended in `tests/test_sources_source_resolver.py`, `tests/test_sources_search_assisted_domestic.py`, and `tests/test_sources_query_decomposition.py`.
- Validation snapshot:
  - `python -m ruff check packages\sources\source_resolver.py packages\sources\search_assisted_domestic.py packages\sources\query_decomposition.py tests\test_sources_source_resolver.py tests\test_sources_search_assisted_domestic.py tests\test_sources_query_decomposition.py` -> pass
  - `python -m py_compile packages\sources\source_resolver.py packages\sources\search_assisted_domestic.py packages\sources\query_decomposition.py tests\test_sources_source_resolver.py tests\test_sources_search_assisted_domestic.py tests\test_sources_query_decomposition.py` -> pass
  - `pytest -q tests\test_sources_source_resolver.py tests\test_sources_search_assisted_domestic.py tests\test_sources_query_decomposition.py` -> `39 passed`
  - `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_search_discovery.py` -> `43 passed`
  - `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`
  - `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`
  - Group3 code-quality gate -> pass
  - Group3 functional gate -> pass, artifact `data/tmp/phase3_source_resolver_functional_validation_20260428.json`
- Functional validator confirmed Q03 primary lanes reject `aopa.org.cn` / `china-uav.cn`, unknown supplemental themes do not fan out, direct-keep task families do not call search/extraction, city/park parent evidence remains a gap, and required rejection codes are observable.
- Repo-wide `python -m ruff check .` still fails on unrelated historical `data/tmp` scratch/demo scripts; focused Phase 3 files pass.
- Scope caveat remains: dirty forbidden files from `.agent/WORKTREE_INVENTORY.md` are still present, so git cannot prove Phase 3 scope from a clean baseline. No destructive cleanup or reversion was performed.

Phase 4 Architecture Gate result:

- Decision: `proceed`.
- Minimal expansion scope: national policy/statistics/customs/commerce backbone plus first-wave provincial backbone only for Guangdong, Jiangsu, Anhui, Zhejiang, Sichuan, Shanghai, and normalization of existing Hubei, Shandong, Fujian, and Henan metadata where tests already depend on those entries.
- Source roles to expand first: national policy, national statistics/customs/commerce, provincial government, provincial DRC, provincial industry/MIIT, provincial statistics, provincial science/technology, and provincial commerce/trade where trade/export queries require it.
- Approved implementation scope: `packages/sources/profiles/china_scaleout.py`, `packages/sources/profiles/china_policy.py`, `packages/sources/packs.py`, `packages/sources/router.py`, narrow `packages/sources/retrieval_plan.py` metadata if needed, narrow `packages/sources/source_resolver.py` domain/role compatibility if needed, and focused tests.
- Forbidden implementation scope: `packages/sources/schemas.py`, `packages/agents/workflow.py`, `packages/providers/**`, `packages/core/config.py`, protected evidence/API/research/task/content/delivery contracts, task/job semantics, `run` / `run_steps`, content asset metadata, delivery transitions, and direct-keep weakening.
- City/county containment: Phase 4 must not add maintained city/county/park profiles, packs, or routing strategies. Existing historical `city_park_pack_cn_v1` / `build_phase4_city_park_profiles` code may remain untouched, but Phase 5 owns city/county fallback discovery.
- Leakage controls: Q03 humanoid robotics policy/local/data lanes must still reject `aopa.org.cn` and `china-uav.cn`; unknown supplemental themes must not fan out; supplemental domains must not be added to primary official policy/data/source-role lanes.
- Direct-keep protection: project transaction, enterprise disclosure, structured data, credit/GSXT, judicial, and exchange disclosure primary paths remain direct structured paths and must not route through Tavily/Crawl4AI primary execution.
- Required Phase 4 validation: province policy/data role coverage, `SRC-COV-04` trade/customs/commerce, Q03 regression, unknown supplemental non-fanout, direct-keep preservation, city/county containment, focused router/profile/retrieval/resolver tests, source regression, and domestic source regression.
- Current gate write scope was limited to `.agent/PLANS/domestic-source-coverage-and-routing-v2.md` and `.agent/STATUS.md`; production code was not changed.

Phase 4 implementation and validation result:

- `packages/sources/profiles/china_scaleout.py` now includes `build_phase4_national_provincial_backbone_profiles()` with national MOST/NBS/Customs/MOFCOM and first-wave provincial policy/data/trade backbone entries for Guangdong, Jiangsu, Anhui, Zhejiang, Sichuan, and Shanghai.
- `packages/sources/profiles/__init__.py` now registers the new Phase 4 backbone builder into `build_domestic_source_profiles()` while preserving existing `build_phase4_city_park_profiles()` behavior.
- `packages/sources/packs.py` now includes `policy_data_backbone_pack_cn_v1` and `cn_policy_data_backbone_v1`; the new pack excludes city/county/park source IDs.
- `packages/sources/router.py` now adds narrow routing/score support for national data/trade sources and first-wave provincial official backbone sources.
- `packages/sources/query_decomposition.py` and `packages/sources/source_resolver.py` now include first-wave official provincial domains for stable Q03/local regional matching.
- Added focused test file `tests/test_sources_domestic_scaleout_phase7.py`.
- Group3 initial review found and remediation fixed two issues: `cn_policy_ndrc_tzgg_v1` was disabled in the default registry, and default local-rollout routing still fanned out into unrelated provincial/city/park sources for Q03-style queries.
- Final validation snapshot after remediation:
  - `python -m ruff check packages\\sources\\profiles\\china_scaleout.py packages\\sources\\profiles\\__init__.py packages\\sources\\packs.py packages\\sources\\router.py packages\\sources\\query_decomposition.py packages\\sources\\source_resolver.py packages\\sources\\retrieval_plan.py tests\\test_sources_domestic_scaleout_phase7.py tests\\test_sources_retrieval_plan.py tests\\test_sources_query_decomposition.py tests\\test_sources_source_resolver.py tests\\test_sources_search_assisted_domestic.py tests\\test_sources_tiaokuai_phase23.py` -> pass
  - `python -m py_compile packages\\sources\\profiles\\china_scaleout.py packages\\sources\\profiles\\__init__.py packages\\sources\\packs.py packages\\sources\\router.py packages\\sources\\query_decomposition.py packages\\sources\\source_resolver.py packages\\sources\\retrieval_plan.py tests\\test_sources_domestic_scaleout_phase7.py tests\\test_sources_retrieval_plan.py tests\\test_sources_query_decomposition.py tests\\test_sources_source_resolver.py tests\\test_sources_search_assisted_domestic.py tests\\test_sources_tiaokuai_phase23.py` -> pass
  - `pytest -q tests\\test_sources_domestic_scaleout_phase7.py tests\\test_sources_retrieval_plan.py tests\\test_sources_query_decomposition.py tests\\test_sources_source_resolver.py tests\\test_sources_search_assisted_domestic.py tests\\test_sources_tiaokuai_phase23.py` -> `73 passed`
  - `pytest -q tests\\test_sources_domestic_scaleout_phase3.py tests\\test_sources_domestic_scaleout_phase4.py tests\\test_sources_router_domestic.py tests\\test_sources_profile_adapter.py` -> `12 passed`
  - `pytest -q tests\\test_sources_layer.py tests\\test_sources_adapters_v1.py tests\\test_sources_hardening_step34.py tests\\test_sources_evals_step35.py` -> `27 passed`
  - `pytest -q tests\\test_sources_router_domestic.py tests\\test_sources_profile_adapter.py tests\\test_sources_real_domestic_step42.py tests\\test_sources_pdf_step43.py` -> `16 passed`
  - Group3 code-quality recheck -> pass
  - Group3 functional recheck -> pass; artifact `data/tmp/phase4_backbone_functional_validation_20260428.json` has `overall_pass: true`

Phase 5 director gate result:

- Decision: proceed to Phase 5 Architecture Gate, not implementation yet.
- Production code was not changed by the director gate.
- Phase 5 Architecture Gate may proceed because Phase 4 remediation and Group3 revalidation passed, no active execution blocker is recorded, and the planned work can be constrained to source-layer fallback discovery without protected contract changes.
- Refined real-world validation focus: city/county/park official-domain-first ladder, parent-level evidence labeling, exact-local coverage-gap transparency, direct-keep primary-path preservation, Q03 negative-domain regression, unknown supplemental non-fanout, Phase 4 source-map freeze, and bounded Tavily/Crawl4AI usage through existing RetrievalPlan round policy.
- Blockers that require human input or a revised Architecture Gate: protected evidence/API/research/provider/task/content/delivery contract change, provider/config edit, mandatory live Tavily/DeepSeek credentials, broad maintained city/county/park profile expansion, direct-keep weakening, or inability to represent parent fallback/gap metadata inside existing source-layer contracts.

Phase 5 Architecture Gate result:

- Decision: `proceed`.
- Production code was not changed by the gate; gate writes were limited to `.agent/PLANS/domestic-source-coverage-and-routing-v2.md` and `.agent/STATUS.md`.
- Approved implementation scope is source-layer only: `packages/sources/source_resolver.py`, `packages/sources/search_assisted_domestic.py`, narrow `packages/sources/query_decomposition.py`, narrow `packages/sources/retrieval_plan.py`, `tests/test_sources_city_county_fallback.py`, focused additions to `tests/test_sources_search_assisted_domestic.py`, `tests/test_sources_source_resolver.py`, `tests/test_sources_retrieval_plan.py`, `tests/test_sources_query_decomposition.py`, and optional `data/tmp/_phase5_city_county_fallback_eval.py`.
- Forbidden scope: `packages/sources/schemas.py`, `packages/agents/workflow.py`, `packages/providers/**`, `packages/core/config.py`, `packages/tasks/**`, `packages/content/**`, `packages/delivery/**`, broad city/county/park profile/pack/router expansion, and all protected evidence/API/research/provider/task/run/content/delivery contracts.
- Fallback-level metadata uses existing source-layer contracts: `CoverageGap.fallback_level`, `fallback_source`, `parent_evidence_only`, `local_claim_allowed`, lane success criteria, and `DomesticSearchAssistedResponse.metadata`. Exact local/city/province/national labels must not claim exact local coverage from parent evidence.
- Direct-keep preservation is mandatory for project transaction, enterprise disclosure, structured data/data metrics, credit/GSXT, judicial, and exchange disclosure lanes. Any primary Tavily/Crawl4AI routing for these lanes is `direct_keep_boundary_violation`.
- Tavily/Crawl4AI behavior must be bounded through existing RetrievalPlan `round_policy`; no provider/config edits and no mandatory live credentials are approved.
- Required validation: focused ruff, py_compile, focused pytest, source regression, domestic source regression, forbidden-path scope review, `SRC-COV-05`, `SRC-COV-07`, county/district fixture, Q03 regression, unknown supplemental non-fanout, direct-keep boundaries, and bounded Tavily/Crawl4AI behavior.

Phase 5 Group2 implementation and validation result:

- Implemented approved source-layer fallback discovery scope in `packages/sources/source_resolver.py`, `packages/sources/search_assisted_domestic.py`, and narrow `packages/sources/query_decomposition.py`; no provider/config/protected-contract edits were made.
- Added `tests/test_sources_city_county_fallback.py` plus focused additions in `tests/test_sources_search_assisted_domestic.py`, `tests/test_sources_source_resolver.py`, `tests/test_sources_retrieval_plan.py`, and `tests/test_sources_query_decomposition.py`.
- Validation snapshot:
  - `python -m ruff check packages\sources\source_resolver.py packages\sources\search_assisted_domestic.py packages\sources\query_decomposition.py packages\sources\retrieval_plan.py tests\test_sources_city_county_fallback.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py` -> pass
  - `python -m py_compile packages\sources\source_resolver.py packages\sources\search_assisted_domestic.py packages\sources\query_decomposition.py packages\sources\retrieval_plan.py tests\test_sources_city_county_fallback.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py` -> pass
  - `pytest -q tests\test_sources_city_county_fallback.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py` -> `68 passed`
  - `pytest -q tests\test_sources_layer.py` -> `8 passed`
  - `pytest -q tests\test_sources_adapters_v1.py` -> `8 passed`
  - `pytest -q tests\test_sources_hardening_step34.py` -> `4 passed`
  - `pytest -q tests\test_sources_evals_step35.py` -> `7 passed`
  - `pytest -q tests\test_sources_router_domestic.py` -> `2 passed`
  - `pytest -q tests\test_sources_profile_adapter.py` -> `4 passed`
  - `pytest -q tests\test_sources_real_domestic_step42.py` -> `4 passed`
  - `pytest -q tests\test_sources_pdf_step43.py` -> `6 passed`
  - `python -m ruff check .` -> fails on pre-existing `data/tmp` historical scripts; unchanged known non-Phase-5 blocker.

Phase 5 final remediation and acceptance result:

- Functional validation initially failed because `decompose_query("苏州工业园区光伏项目政策")` did not preserve exact park discovery: no `sipac.gov.cn` and no search phrase retaining `苏州工业园区`.
- Remediation added exact local entity discovery hints in `packages/sources/query_decomposition.py` for explicit `苏州工业园区` queries. This injects `sipac.gov.cn` and exact search phrases without adding maintained city/county/park profiles, packs, or router expansion.
- Final validation snapshot:
  - focused ruff for Phase 5 source/test files -> pass
  - focused py_compile for Phase 5 source/test files -> pass
  - `pytest -q tests\test_sources_city_county_fallback.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_query_decomposition.py tests\test_sources_retrieval_plan.py` -> `68 passed`
  - source regression -> `27 passed`
  - domestic regression -> `16 passed`
  - Group3 code-quality remediation recheck -> pass
  - Group3 functional remediation recheck -> pass
  - `data/tmp/phase5_city_county_fallback_functional_validation_20260428.json` -> `overall_pass: true`
  - local artifact/probe confirmed `sipac.gov.cn` is present and a search phrase preserves `苏州工业园区`

Phase 6 director gate result:

- Decision: proceed to Phase 6 Architecture Gate, not implementation yet.
- Current write scope was limited to `.agent/PLANS/domestic-source-coverage-and-routing-v2.md` and `.agent/STATUS.md`; production code was not changed.
- Task classification: primary `source_layer`; secondary `domestic_source_collectors` and `eval_policy_ops`.
- Architecture Gate must confirm Phase 6 can keep multi-round orchestration, per-round traces, budget enforcement, and coverage sufficiency judging inside source-layer contracts/artifacts without changing protected evidence/API/research/source-routing/provider/task/content/delivery contracts.
- Refined validation plan now requires offline/mocked proof for Round 1 stop-on-sufficiency, Round 2 required-lane-only gap closure, bounded Round 3 supplemental/fallback behavior, `round_policy` budget enforcement, structured budget-exhaustion gaps, Q03 negative-domain regression, direct-keep preservation, city/county fallback preservation, and no incompatible domain widening.
- Group2 assignment: `invest_agent_architecture_builder` / `system_contract_architect` owns the Phase 6 Architecture Gate first; after `Decision: proceed`, `invest_feature_programmer` / `source_provider_integrator` may implement only the approved source-layer modules and focused tests; optional `eval_harness_implementer` may add an offline JSON-printable eval helper under `data/tmp/` only if tests cannot express sufficiency traces.
- Group3 assignment: `invest_code_quality_checker` runs focused ruff, py_compile, focused pytest, source regression, domestic source regression, and forbidden-path scope review; `invest_functional_validator` owns practical case design and must inspect actual judge/orchestration artifacts, not only worker summaries.
- Blockers requiring revised Architecture Gate or human input: any protected contract change, provider/config edit, mandatory live Tavily/DeepSeek credential requirement, research workflow response-shape change, direct-keep weakening, broad source/profile expansion, incompatible domain widening, or inability to represent sufficiency/budget/round gaps inside existing source-layer objects.

Phase 6 Architecture Gate result:

- Decision: `proceed`.
- Gate write scope was limited to `.agent/PLANS/domestic-source-coverage-and-routing-v2.md` and `.agent/STATUS.md`; production code was not changed.
- Architecture intent: keep multi-round execution, per-round trace metadata, coverage sufficiency judging, budget enforcement, budget-exhaustion gaps, and domain-widening controls inside source-layer contracts/artifacts.
- Source-layer contracts approved for Phase 6: `RetrievalPlan.round_policy`, `RetrievalPlan.stop_conditions`, `CoverageLanePlan.success_criteria`, `CoverageGap`, `CandidateCompatibilityDecision.reason_code`, and internal `DomesticSearchAssistedResponse.metadata` trace keys.
- Approved implementation scope: `packages/sources/coverage_judge.py`, `packages/sources/search_assisted_domestic.py`, narrow `packages/sources/retrieval_plan.py`, narrow `packages/sources/source_resolver.py`, `tests/test_sources_coverage_judge.py`, focused additions to existing source-layer tests, and optional `data/tmp/_phase6_multi_round_coverage_eval.py`.
- Forbidden implementation scope remains: `packages/sources/schemas.py`, `packages/agents/workflow.py`, `packages/providers/**`, `packages/core/config.py`, `packages/tasks/**`, `packages/content/**`, `packages/delivery/**`, broad source/profile/pack/router expansion, protected downstream contracts, mandatory live credentials, research workflow integration, incompatible domain widening, and direct-keep weakening.
- Required validation: Round 1 stop-on-sufficiency, Round 2 required-lane gap closure only, bounded Round 3 supplemental/fallback, credit/candidate/extraction budget enforcement, structured budget-exhaustion gaps, Q03 regression, direct-keep preservation, city/county fallback preservation, and no incompatible domain widening.
- Stop conditions: reopen Architecture Gate if implementation requires protected contracts, provider/config edits, mandatory live Tavily/DeepSeek credentials, research workflow response-shape changes, broad source expansion, incompatible domain widening, or direct-keep weakening.

Phase 6 Group2 implementation and validation snapshot:

- Added `packages/sources/coverage_judge.py` with deterministic lane sufficiency and round transition decisions.
- Updated `packages/sources/search_assisted_domestic.py` for bounded multi-round execution, source-layer budget accounting, structured coverage gaps, and round trace metadata.
- Narrow additions in `packages/sources/retrieval_plan.py` and `packages/sources/source_resolver.py` for lane/task-family mapping and supplemental-or-fallback eligibility helpers.
- Added `tests/test_sources_coverage_judge.py` plus focused Phase 6 assertions in search-assisted/retrieval-plan/source-resolver/city-county/query-decomposition tests.
- Validation snapshot:
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

Phase 6 completion result:

- Group3 code-quality validation returned `PASS_WITH_KNOWN_DEBT`; focused ruff, py_compile, Phase 6 focused pytest, source regression, and domestic regression passed. Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` lint debt.
- Group3 functional validation returned `PASS`; artifact `data/tmp/phase6_multi_round_coverage_functional_validation_20260428.json` reports `overall_pass: true`, `9` checks, and `0` failures.
- Validated behavior includes Round 1 stop-on-sufficiency, Round 2 required-lane-only gap closure, bounded Round 3 supplemental/fallback, budget metadata and budget-exhaustion gaps, Q03 supplemental-domain rejection, direct-keep refusal, Suzhou Industrial Park `sipac.gov.cn` hint preservation, and `domain_widening_blocked=true` round traces.
- Phase 6 is complete. No protected downstream contract, provider/config, research workflow, broad source expansion, incompatible domain widening, or direct-keep weakening was required.
- Phase 7 director gate completed with `Decision: proceed_to_architecture_gate`; production code remains untouched.

Phase 7 director gate result:

- Current state is now `active_phase7_architecture_gate_ready`.
- Architecture Gate must decide the internal boundary for RetrievalPlan-backed research source acquisition before touching `packages/agents/workflow.py`, `packages/sources/service.py`, public response compatibility, or source-acquisition summary semantics.
- Mandatory validation plan covers legacy `enable_source_acquisition=False`, enabled source acquisition, explicit `source_ids` override, direct-keep primary paths, Q03 negative-domain regression, Suzhou Industrial Park fallback hints/gaps, coverage-gap visibility through existing compatible fields, `source_quality_summary` shape, and run trace semantics.
- Group2 next lane: `system_contract_architect` backed by `invest_agent_architecture_builder`.
- Candidate implementation lanes after Architecture Gate proceeds: `research_workflow_implementer`, optional `source_provider_integrator`, optional `eval_harness_implementer`.
- Group3 validation lanes: `invest_code_quality_checker` for focused ruff/compile/pytest, research-contract checks, source/domestic regressions as applicable; `invest_functional_validator` for practical response/trace validation against the Phase 7 real-world cases.
- Stop and revise if integration requires protected response-shape drift, EvidenceBundle/citation changes, task/job status changes, `run` / `run_steps` meaning changes, mandatory live credentials, public source schema changes, broad source expansion, or direct-keep weakening.

Phase 7 Architecture Gate result:

- Decision: `proceed`.
- Current state is now `active_phase7_implementation_ready`.
- Architecture decision: RetrievalPlan-backed coverage metadata can enter research workflow through existing internal source-acquisition paths without changing protected public contracts.
- Safest boundary: keep `packages/agents/workflow.py` query-decomposition based for the first implementation slice. Do not make workflow consume `packages.sources.retrieval_plan.build_retrieval_plan()` directly yet.
- Existing compatible paths are sufficient:
  - `SearchAssistedDomesticOrchestrator.orchestrate_task()` already emits `round_policy`, `budget_state`, `round_trace`, `coverage_sufficient`, `coverage_gaps`, candidate decisions, and fallback metadata in `DomesticSearchAssistedResponse.metadata`.
  - `workflow.py` already nests that metadata under `SourceAcquisitionSummary.source_traces[].metadata.response_metadata` for `tool_name == "search_assisted_domestic"`.
  - Optional visibility may use compact `SourceAcquisitionSummary.notes[]` strings and string-only `SourceEvidenceBundle.gaps[]`; structured coverage details must stay in trace metadata.
- Affected contracts remain compatible:
  - `ResearchAnalyzeRequest`, `ResearchAnalysisResult`, `SourceAcquisitionSummary`, Source EvidenceBundle, Source EvidenceItem, Citation, `source_quality_summary`, source routing response shape, task/job semantics, `run` / `run_steps`, provider/config compatibility, explicit `source_ids` override behavior, direct-keep behavior, and legacy `enable_source_acquisition=False` behavior remain unchanged.
- Approved implementation write scope:
  - `packages/agents/workflow.py` for narrow metadata/gap/note propagation inside `_run_source_acquisition`.
  - `tests/test_agents_workflow.py` and `tests/test_research_api.py` for focused compatibility tests.
  - Optional narrow `packages/sources/service.py` or focused source helper/tests only if an internal metadata normalization helper is proven necessary.
  - Optional `data/tmp/_phase7_retrieval_plan_research_workflow_eval.py` if practical offline probes are needed.
- Forbidden scope:
  - No edits to `packages/agents/schemas.py` or `packages/sources/schemas.py`.
  - No schema/public response changes, no non-string `EvidenceBundle.gaps`, no `source_quality_summary` shape changes, no task/job or `run_steps` semantic changes, no provider/config requirements, no broad source expansion, no direct-keep weakening, and no secret/private-reasoning trace storage.
- Group2 next lane: `research_workflow_implementer`; activate `source_provider_integrator` only if internal source-layer helper glue is required; activate `eval_harness_implementer` only if Group3 needs offline probes beyond pytest.
- Group3 validation plan: focused ruff/compile, `pytest -q tests/test_agents_workflow.py`, `pytest -q tests/test_research_api.py`, `pytest -q tests/test_research_provider_integration.py`, `pytest -q tests/test_deepseek_provider.py`, plus source/domestic regressions if source-layer files change. Functional validation must cover legacy disabled mode, enabled source acquisition, explicit source IDs override, direct-keep, Q03 negative-domain behavior, Suzhou Industrial Park fallback, coverage gaps, `source_quality_summary` key shape, and run trace semantics.
- Stop and rollback: stop if implementation needs any protected contract drift or direct `build_retrieval_plan()` workflow execution. Roll back by removing the narrow metadata bridge and retaining the current query-decomposition source-assisted path.

Phase 7 Group2 implementation result:

- Scope completed: `packages/agents/workflow.py` and `tests/test_agents_workflow.py` only; `tests/test_research_api.py` required no assertions change for this slice.
- Workflow remains query-decomposition based. No direct `build_retrieval_plan()` workflow consumption was added.
- Existing `source_traces[].metadata.response_metadata` behavior for `tool_name == "search_assisted_domestic"` remains intact and now explicitly verified for `coverage_gaps`, `round_trace`, `budget_state`, and `coverage_sufficient`.
- Added compact compatibility visibility by propagating string-only coverage gap markers into existing fields:
  - `SourceAcquisitionSummary.notes[]`: `coverage_gap_count=<n>`, `coverage_gap:<lane_id>:<reason_code>`
  - `SourceEvidenceBundle.gaps[]`: deduplicated `coverage_gap:<lane_id>:<reason_code>` markers
- Direct-keep controls, explicit `source_ids` override, and legacy `enable_source_acquisition=False` behavior remain unchanged and covered by focused tests.
- Validation snapshot:
  - `python -m ruff check packages\\agents\\workflow.py tests\\test_agents_workflow.py tests\\test_research_api.py` -> pass
  - `python -m py_compile packages\\agents\\workflow.py tests\\test_agents_workflow.py tests\\test_research_api.py` -> pass
  - `pytest -q tests\\test_agents_workflow.py tests\\test_research_api.py` -> `13 passed`
  - `pytest -q tests\\test_research_provider_integration.py` -> `9 passed`
  - `pytest -q tests\\test_deepseek_provider.py` -> `2 passed`
  - `python -m ruff check .` -> fails on pre-existing historical `data/tmp` lint debt (known non-blocker for this focused phase)

Phase 7 completion result:

- Group3 code-quality validation returned `PASS_WITH_KNOWN_DEBT`; focused ruff, py_compile, workflow/API pytest (`13 passed`), and research provider/DeepSeek pytest (`11 passed`) passed. Repo-wide `python -m ruff check .` still fails only on known historical `data/tmp` lint debt.
- Group3 functional validation returned `PASS`; artifact `data/tmp/phase7_retrieval_plan_workflow_functional_validation_20260428.json` reports `overall_pass: true`, `12/12` checks passed, and `0` failures.
- Validated behavior includes disabled legacy path, enabled source-acquisition metadata bridge, compact coverage gap notes, string-only retrieval gaps, explicit `source_ids` override, direct-keep control path, Q03 negative-domain behavior, Suzhou Industrial Park fallback hints, unchanged `source_quality_summary` shape, unchanged run step semantics, and no direct `build_retrieval_plan()` workflow consumption.
- Domestic Source Coverage and Routing v2 reached its done condition and was archived at `.agent/PLANS/archive/domestic-source-coverage-and-routing-v2.md`.

## Latest Workspace Hygiene Snapshot

Completed 2026-04-28:

- Created `.agent/PLANS/workspace-hygiene-v1.md`.
- Moved completed plans from `.agent/PLANS/` to `.agent/PLANS/archive/`.
- Created `.agent/PLANS/INDEX.md`.
- Created `.agent/WORKTREE_INVENTORY.md`.
- Updated `.agent/STATUS.md` to show no active long-running PLAN.

Current PLAN root:

- `.agent/PLANS/INDEX.md`
- `.agent/PLANS/agentic-operating-system-v2.md`

Pending human review:

- `.agent/PLANS/agentic-operating-system-v2.md` remains `completed_pending_human_review`.

Completed and archived:

- `.agent/PLANS/archive/domestic-source-lite-refactor-v1.md`
- `.agent/PLANS/archive/research-workflow-source-assisted-integration-v1.md`
- `.agent/PLANS/archive/group2-worker-lane-design-v1.md`
- `.agent/PLANS/archive/domestic-source-coverage-and-routing-v2.md`
- `.agent/PLANS/archive/agentic-operating-system-v2-phase0-authority-freeze.md`
- `.agent/PLANS/archive/agentic-operating-system-v2-phase8-superpowers-advisory.md`
- `.agent/PLANS/archive/workspace-hygiene-v1.md`

Dirty worktree inventory:

- `.agent/WORKTREE_INVENTORY.md`

No destructive cleanup was performed.

## Latest Source-Assisted Research Integration Snapshot

Completed PLAN archived for human review/reference:

- `.agent/PLANS/archive/research-workflow-source-assisted-integration-v1.md`

Current phase:

- Phase 4: Full Validation and Handoff completed.

Phase 0 director gate result:

- Architecture Gate confirmed.
- Real-world validation plan added to the active PLAN.
- Protected contracts verified as sufficient for Phase 1 without schema or response-shape changes.
- `packages/agents/schemas.py` and `packages/sources/schemas.py` are not expected to change in Phase 1; schema edits require Architecture Gate revision.
- Implementation may proceed only through existing `ResearchAnalyzeRequest`, `ResearchAnalysisResult`, `SourceAcquisitionSummary`, source `EvidenceItem` / `Citation` / `EvidenceBundle`, and RAG bundle conversion contracts.

Planned model:

- Keep `enable_source_acquisition=False` legacy RAG path unchanged.
- Keep existing source registry/adapters available.
- Add search-assisted domestic branch inside research source acquisition only for allowed query decomposition tasks.
- Preserve direct-keep tasks as controls; do not route disclosure, project transaction, or structured-data primary paths through Tavily.
- Convert search-assisted normalized documents into existing Source EvidenceItems and then into existing RAG EvidenceBundle shape.
- Use Group2 lanes:
  - `system_contract_architect`
  - `source_provider_integrator`
  - `research_workflow_implementer`
  - `eval_harness_implementer`

Final implementation and validation snapshot:

- `packages/agents/workflow.py` now runs query-decomposition-gated search-assisted domestic tasks only when source acquisition is enabled and no explicit `source_ids` override is present.
- `packages/sources/search_assisted_domestic.py` converts search-assisted normalized/raw documents into existing Source `EvidenceItem` / `Citation` contracts.
- Direct-keep disclosure/project/structured-data tasks remain controls and do not use Tavily/Crawl4AI as the primary path.
- Holdout city/park tasks remain transparent through unsupported/partial traces and do not fabricate search-assisted evidence.
- New eval harness: `data/tmp/_research_workflow_source_assisted_eval.py`.
- Group3 code-quality gate: passed.
- Group3 functional gate: passed for offline RW-SAI-01..08; RW-SAI-09 live status recorded as skipped because `TAVILY_API_KEY` was absent from the current process.
- Director remediation decision: `phase1_2_complete`; `packages/sources/schemas.py` public additions are treated as pre-existing dirty-worktree caveat/separate PLAN risk, not a blocker for this PLAN.

## Latest Group2 Lane Validation Snapshot

Group2 Worker Lane Design v1 completed and accepted by human review:

- Created `.agent/PLANS/archive/group2-worker-lane-design-v1.md`
- Created `.agent/skills/group2-worker-lane-design.md`
- Updated `.agent/SKILL_ROUTER.md`
- Updated `.agent/skills/subagent-gate-contract.md`
- Updated `.agent/evals/workflow-pressure-scenarios.md`
- Updated `.agent/STATUS.md`

The adopted model is:

```text
fixed capability lane + task-specific worker instance
```

Initial Group2 lanes:

- `system_contract_architect` backed by `invest_agent_architecture_builder`
- `source_provider_integrator` backed by `invest_feature_programmer` with lane role card
- `research_workflow_implementer` backed by `invest_feature_programmer` with lane role card
- `eval_harness_implementer` backed by `invest_feature_programmer` with lane role card

Validation run:

- `Select-String -Path '.agent\skills\group2-worker-lane-design.md' -Pattern 'Purpose','Use when','Skip when','Authority','Inputs','Process','Outputs','Validation','Red flags','Completion note'` -> pass
- `Select-String -Path '.agent\SKILL_ROUTER.md','.agent\skills\subagent-gate-contract.md','.agent\evals\workflow-pressure-scenarios.md' -Pattern 'group2-worker-lane-design','Architecture Gate','system_contract_architect','task-specific worker instance','WPS-015','WPS-016'` -> pass
- `git status --short -- .agent AGENTS.md packages` -> reviewed; still shows pre-existing dirty/untracked `AGENTS.md` and production paths plus untracked `.agent`

Production tests were not run because this plan changed only `.agent` governance artifacts.

Human review result:

- Accepted on 2026-04-28.
- `.agent/PLANS/archive/group2-worker-lane-design-v1.md` status is now `completed`.
- Promotion into `AGENTS.md` remains deferred to a separate behavior-governance PLAN if needed.

## Latest Completed Milestone

`domestic-source-lite-refactor-v1.md` reached its done condition after Phase 5 remediation and live validation.

Domestic Source Lite Refactor completed:

- Phase 1 query decomposition contract and validation
- Phase 2 Tavily search discovery integration
- Phase 3 Crawl4AI extraction integration
- Phase 4 first-wave search-assisted domestic orchestration
- Phase 5 query-based usability eval, credit review, and live remediation

The completed domestic PLAN now remains at `.agent/PLANS/archive/domestic-source-lite-refactor-v1.md`.

## Recent Validation Snapshot

Phase 0 validation for Agentic Operating System v2:

- Created `.agent/PLANS/agentic-operating-system-v2-phase0-authority-freeze.md`
- Updated `.agent/PLANS/agentic-operating-system-v2.md` with Phase 0 completion, validation, and next action
- Confirmed `.agent/STATUS.md` points to `.agent/PLANS/agentic-operating-system-v2.md`
- Confirmed Phase 0 stayed docs/governance-only within `.agent`
- Superpowers remains advisory, not authoritative
- Group 3 functional governance dry-runs passed:
  - Superpowers conflict -> keep `.agent/STATUS.md` and active PLAN canonical
  - request to edit `AGENTS.md` -> defer because Phase 0 forbids it
  - request to change protected contract -> stop and require explicit PLAN migration/compatibility/validation
  - worker self-certifies without Group 3 validation -> incomplete until independent validation
- Group 3 scope validation passed artifact/content checks but flagged a dirty-worktree risk:
  - current working tree includes pre-existing dirty/untracked `AGENTS.md`, production, docs, tests, scripts, and data files
  - `.agent` is untracked from git's perspective
  - without a clean pre-phase baseline, git cannot independently prove Phase 0 introduced no non-`.agent` changes

Phase 1-8 completion snapshot:

- User accepted the dirty-worktree scope-proof risk and continuation proceeded with `.agent`-only writes.
- Created `.agent/skills/intent-discovery-gate.md`
- Created `.agent/skills/brainstorming.md`
- Created `.agent/skills/design-brief-template.md`
- Created `.agent/SKILL_ROUTER.md`
- Created `.agent/skills/plan-self-review.md`
- Created `.agent/skills/subagent-gate-contract.md`
- Created `.agent/skills/verification-before-completion.md`
- Created `.agent/skills/systematic-debugging.md`
- Created `.agent/skills/tdd-policy.md`
- Created `.agent/RUNS/README.md`
- Created `.agent/RUNS/2026-04-27-agentic-os-v2-docs-governance/run.md`
- Created `.agent/RUNS/2026-04-27-agentic-os-v2-docs-governance/decisions.md`
- Created `.agent/RUNS/2026-04-27-agentic-os-v2-docs-governance/validation.md`
- Created `.agent/RUNS/2026-04-27-agentic-os-v2-docs-governance/risks.md`
- Created `.agent/evals/workflow-pressure-scenarios.md`
- Created `.agent/PLANS/agentic-operating-system-v2-phase8-superpowers-advisory.md`
- No Superpowers plugin installation or activation occurred.
- Validation commands/checks:
  - required artifact existence check -> pass
  - `Select-String` checks for `completed_pending_human_review`, Phase 8, and next recommended PLAN -> pass
  - `Select-String` checks for active PLAN done condition and Superpowers advisory decision -> pass
  - `.agent` Tavily credential-prefix check -> no match
  - `git status --short -- .agent AGENTS.md packages` -> confirms `.agent` changes plus pre-existing dirty/untracked `AGENTS.md` and production paths
- Production tests were not run because this continuation intentionally changed only `.agent` docs/governance artifacts.
- Human review correction:
  - Added missing explicit `.agent/skills/brainstorming.md`
  - Updated `.agent/SKILL_ROUTER.md` to route open-ended brainstorming/design exploration to the brainstorming skill
  - Updated Phase 0 authority-freeze and active PLAN references so Superpowers `brainstorming` maps to a named project-native skill, not only to intake/design-brief artifacts
- Human review correction for Group1/Group3 and skill format:
  - Added `.agent/skills/director-remediation-gate.md`
  - Added `.agent/skills/real-world-case-design.md`
  - Added `.agent/skills/skill-design-standard.md`
  - Updated `.agent/SKILL_ROUTER.md` to replace the vague trigger-description example with enforceable skill design rules
  - Updated `.agent/skills/subagent-gate-contract.md` so Group1 can open remediation gates without changing user goals, and Group3 owns real-world case design
  - Updated `.agent/evals/workflow-pressure-scenarios.md` with director-remediation, worker-easy-cases, and vague-skill-trigger pressure scenarios
- Human review correction for brainstorming depth:
  - Redesigned `.agent/skills/brainstorming.md` to adapt Superpowers' deeper collaborative design flow.
  - Added assumption ledger, one-question-at-a-time Socratic loop, real option generation, recommendation, pressure testing, staged design sections, and Design Brief/PLAN exit.
  - Added `WPS-014: Superficial brainstorming` to `.agent/evals/workflow-pressure-scenarios.md`.

Planning validation for Agentic Operating System v2:

- Created `.agent/PLANS/agentic-operating-system-v2.md`
- Updated `.agent/STATUS.md` to point to the new active PLAN
- No production code changed
- No `AGENTS.md` changes made
- Superpowers remains advisory, not authoritative

Last domestic source validation snapshot retained for historical context:

- `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_domestic_scaleout_phase5.py tests\test_sources_search_assisted_domestic.py tests\test_sources_search_discovery.py tests\test_sources_crawl4ai_extraction.py` -> `53 passed`
- `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`
- `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`
- `python data\tmp\_phase5_search_assisted_domestic_eval.py --mode offline` -> pass
- `python data\tmp\_phase5_search_assisted_domestic_eval.py --mode live` -> pass

Repo-wide check note:

- `python -m ruff check .` still fails on unrelated historical `data/tmp` scratch/demo scripts.
- This is not a blocker for the new planning-only step.

## Current Blockers

- No active confirmation blocker for the current PLAN.
- Active quality blocker: local/regional statistics, fiscal, energy, trade/customs data and exact-local regional precision remain insufficient after Source Transaction File Local Depth v1 Phase 7.
- The archived transaction/local-record plan and completed transaction/file-depth plan should not be implemented directly.
- No active provider/runtime blocker; Tavily multi-key rotation is available and DeepSeek audit transport succeeded after quote-safe `.env` loading.
- Latest 12-case gate has stable runtime and audit schema but still failed evidence quality (`8 fail / 4 weak_pass`); `statistics=4` is above target `<=3`.
- Full 50-case live source-quality run is still strategically blocked by transaction/procurement/project/local-record evidence sufficiency, not runtime.
- Do not spend budget on the full 50-case live run until the successor PLAN passes a 12-case gate or records a narrower blocker.
- The previous generalized and local-backbone PLANs remain the comparison baseline; do not restart source research from scratch.
- Any remediation must improve general source/evidence quality patterns rather than hard-coding a single query, company, region, or domain.
- No active blocker for the completed domestic source coverage and routing v2 PLAN.
- Dirty worktree remains broad; consult `.agent/WORKTREE_INVENTORY.md` before starting the next PLAN.
- Do not edit `AGENTS.md` unless a separate PLAN explicitly authorizes promotion of stable governance rules.
- Do not install or activate Superpowers as a controlling plugin unless a future PLAN reopens that decision.

## Environment Notes

- Use local gitignored `.env` or temporary process env for `TAVILY_API_KEY` / `DEEPSEEK_API_KEY`; do not write raw credentials to PLAN, STATUS, scripts, artifacts, `.env.example`, or run logs.
- Local gitignored `.env` currently has a Tavily key pool with `5` entries for rotation; do not copy raw keys into tracked files.
- For Windows PowerShell live Chinese-query validation, avoid piping literal Chinese through here-strings; use UTF-8 files or Unicode escape strings.
- Recommended PowerShell env for Crawl4AI/Tavily live validation:
  - `$env:PYTHONIOENCODING='utf-8'`
  - `$env:PYTHONUTF8='1'`
  - `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`
- Environment warnings observed but non-blocking:
  - `requests` / `urllib3` / `chardet` dependency warning
  - `s3fs` / `fsspec` mismatch after Crawl4AI installation

## Risks / TODOs

- Group2 lane model is currently a governance/skill rule; runtime still has the existing backing subagents.
- The source-assisted product PLAN validated the Group2 lane model in practice, and human review accepted it on 2026-04-28; promotion into `AGENTS.md` still requires a separate behavior-governance PLAN.
- Completed PLANs have been moved to `.agent/PLANS/archive/`; see `.agent/PLANS/INDEX.md`.
- `agentic-operating-system-v2.md` remains `completed_pending_human_review` in `.agent/PLANS/`.
- `packages/sources/schemas.py` has public additions relative to HEAD from the pre-existing dirty worktree. This PLAN does not depend on them; future release boundary work should handle them in a separate Architecture Gate/PLAN.
- Repo-wide `python -m ruff check .` still fails on unrelated historical `data/tmp` scratch/demo scripts. Focused checks for touched production/test/eval files pass.
- Optional live RW-SAI-09 was skipped in the completed source-assisted PLAN because that process did not have `TAVILY_API_KEY`.
- Over-adopting Superpowers could make routine tasks too heavy; the new PLAN explicitly requires project-native adaptation.
- Skill proliferation could reduce clarity unless triggers are narrow and behavior-changing skill edits have pressure scenarios.
- Run traces must not record private chain-of-thought or secrets.
- Future AGENTS changes should be handled as behavior-changing governance changes with validation.
- Phase 4 has a naming-risk from historical `build_phase4_city_park_profiles` / `city_park_pack_cn_v1` code. Do not expand or reinterpret those city/park profiles as the current Phase 4; handle any cleanup/rename only if a focused compatibility-safe task requires it.
- Phase 6 has remediated the `C01` broad `dxal` official-record case-page acceptance, added CNINFO direct disclosure fallback, and recovered region-matched subprovincial official-record domains. Remaining work belongs to Phase 7 audit interpretation or a new remediation gate.
- The `K12` official-record no-evidence result from `strong_evidence_phase6_official_record_smoke_v1` was traced to phrase fanout; v2 recovered K12 through third-phrase fanout. The remaining cost risk is mitigated by `max_official_record_fallback_search_credits`; use cap=2 as the default cost-controlled gate and cap=3 only for recall sensitivity checks.
- The 50-query set should be used to find reusable source-routing, discovery, extraction, and evidence-quality failures; avoid patching isolated query symptoms unless they represent a documented broader class.

## Next Recommended Action

- Continue `.agent/PLANS/source-local-procurement-regulatory-depth-v1.md` with Phase 1 tender / public-resource backbone.
- Source Local Statistics Regional Precision v1 completed with successor blocker; do not continue implementing inside the archived statistics PLAN.
- Preserve K09/K12 exact-local claim repairs and P04 statistics recovery as regression gates.
- Use the latest Phase 6 audit gaps (`tender_or_procurement=7`, `regulatory_record=4`, `environmental_or_land_record=2`) to build the next source-family blocker matrix.
- Use the 12-case smoke set as regression evidence, not as a hardcoded tuning target.
- Use query examples as symptoms for general rules, not targets for hard-coded remediation.
- Do not run the full 50-case live evaluation until the successor PLAN reaches Phase 7 readiness and records a budget cap.
- Keep the dirty-worktree and repo-wide `data/tmp` ruff debt visible before implementation.

## Latest Execution Mode Router And Technical Roadmap Snapshot

Completed sidecar governance plan:

- `.agent/PLANS/archive/execution-mode-router-tech-roadmap-v1.md`

Result:

- Added `.agent/skills/execution-mode-router.md`.
- Updated `.agent/SKILL_ROUTER.md` and `.agent/skills/subagent-gate-contract.md` so full v2 subagent orchestration is selected by route/risk instead of being the default for every PLAN execution.
- Updated `AGENTS.md` PLAN implementation trigger rule to use a speed-biased execution router.
- Added `docs/technical-roadmap-evolution.md` as the durable technical-route evolution log.

Operating default:

- `local_direct` for low-risk docs/eval/status/report work.
- `light_subagent` for scoped implementation without protected-contract risk.
- `remediation_gate` for failed live/eval gates with unchanged user goals.
- `full_subagent` for protected contracts, source/provider/research workflow boundaries, multiple Group2 lanes, or user-facing evidence-risk work.

## Queued Plans

- `longtasks-substrate-v1.md` (not created in repo yet)
- `theme-watchlist-intel-workbench-v1.md` (not created in repo yet)

## Update Rule

Update this file after each phase completion or when the primary active plan changes.
