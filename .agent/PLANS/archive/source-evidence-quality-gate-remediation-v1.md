# Source Evidence Quality Gate Remediation v1

Status: completed_with_successor_blocker

Created: 2026-04-29

Primary active PLAN: yes

Supersedes active execution of:

- `.agent/PLANS/archive/source-evidence-sufficiency-remediation-v2.md`

## Objective

Improve the system from "source classes are visible" to "strong evidence is actually sufficient for the judge."

The previous PLAN proved that runtime, routing, source-class metadata, and DeepSeek transport are mostly stable, but the 12-case quality gate still failed:

- Live gate: `12 success / 0 runtime error`
- DeepSeek audit: `12 success`, shape diagnostics `0`
- Verdicts: `11 fail / 1 weak_pass / 0 pass`
- Tavily credits: `79`
- Average latency: `43861.95 ms`

The main blocker is no longer metadata visibility. It is strong-evidence quality, especially project/public-resource evidence, local-government precision, and PDF/download extraction.

## Task Classification

- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `eval_policy_ops`, `provider_layer`

Protected contracts:

- EvidenceBundle schema
- EvidenceItem citation fields
- `source_quality_summary` shape
- research analyze response shape
- provider abstraction semantics
- source routing response shape
- task/job status semantics
- direct-keep primary paths
- legacy `enable_source_acquisition=False` behavior

No protected-contract change is allowed without an explicit Architecture Gate section in this PLAN.

## Baseline Artifacts

Primary baseline:

- `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase5_live_v1/live_summary.json`
- `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase5_live_v1/batch_eval.json`
- `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase5_live_v1/source_roadmap.json`
- `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase5_live_v1/llm_audit_summary.json`
- `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase5_live_v1/llm_audit/*.json`
- `data/tmp/source_quality_stress_eval/runs/source_evidence_sufficiency_v2_phase5_live_v1/per_query/*.json`

Baseline missing source classes from DeepSeek audit:

| Source class | Missing count | Affected cases |
|---|---:|---|
| `project_list` | `7` | `C07`, `K07`, `K12`, `M02`, `M03`, `M06`, `P08` |
| `tender_or_procurement` | `7` | `C01`, `C07`, `K12`, `M02`, `M03`, `M06`, `P04` |
| `local_government` | `4` | `C01`, `C09`, `K07`, `K09` |
| `environmental_or_land_record` | `2` | `K07`, `M02` |
| `local_policy` | `2` | `K12`, `P04` |
| `official_policy` | `2` | `M02`, `P08` |
| `regulatory_record` | `2` | `M02`, `M03` |
| `statistics` | `2` | `K09`, `P08` |

Important distinction:

- Per-query metadata coverage is better than the LLM verdicts.
- Therefore the next work must improve relevance, precision, extraction content, and judge-visible evidence, not just add `source_class` labels.

## Design Direction

Use the 12 cases as regression pressure, not as hardcoded targets.

```text
Query
  -> evidence obligations
  -> lane planner with strong-evidence budget
  -> project/public-resource and local official source precision
  -> extraction quality gate
  -> evidence packaging that exposes source, date, region, class, snippet, and failure reason
  -> DeepSeek audit
```

General principles:

- Fix source classes and source patterns, not one-off query strings.
- Prefer direct-keep or structured fallback only when the evidence type is inherently structured.
- Keep Tavily fanout capped and measurable.
- Preserve transparent failure when public evidence cannot be reached.
- Do not run the 50-query live set before the 12-case quality gate improves.

## Scope

In scope:

- Project/public-resource and tender/procurement search strategy.
- Local-government source precision for city/county/province cases.
- Official policy and regulatory evidence for macro project claims.
- Static PDF/download extraction diagnostics and recoverable text paths where safe.
- Evidence-content quality scoring under existing metadata.
- Eval artifact packaging so the LLM judge can see enough source evidence.

Out of scope unless reopened:

- Browser automation.
- OCR.
- Paid/private data.
- Login-gated sources.
- Public contract shape changes.
- Query-specific hardcoding.
- Full 50-query live evaluation.

## Phases

### Phase 0: Failure Synthesis And Gate Freeze

Objective:

- Freeze the strong-evidence blocker from the previous PLAN and prevent overfitting.

Acceptance criteria:

- Baseline artifacts and thresholds are recorded.
- Failures are grouped by reusable source-quality class.
- Full 50-query run remains deferred.

Validation:

```powershell
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\source_evidence_sufficiency_v2_phase5_live_v1 --print-json
```

### Phase 1: Project/Public-Resource Evidence Backbone

Objective:

- Reduce `project_list` and `tender_or_procurement` gaps by improving general project lane precision.

Tasks:

- Review current project lane phrase templates and candidate acceptance.
- Add reusable project/public-resource patterns for:
  - major project lists
  - project approval and filing
  - public-resource trading
  - procurement/tender/winning-bid pages
- Ensure project lanes do not accept generic news as strong project evidence.
- Keep project fallback credit caps visible.

Acceptance criteria:

- Deterministic tests prove project/tender source-class expectations and rejection rules.
- Low-cost live subset shows improved project/tender coverage without uncapped fanout.
- No protected public contract changes.

### Phase 2: Local Official Source Precision

Objective:

- Improve city/county/province local-government evidence quality and regional granularity.

Tasks:

- Generalize source-profile candidates from the audit into reusable local source patterns.
- Improve exact-local vs parent-local vs child-local scoring in accepted evidence.
- Add local official source preferences for city/county project, finance, statistics, and land/environment pages.
- Keep parent-level evidence explicit when exact-local evidence is unavailable.

Acceptance criteria:

- `local_government` gap improves from `4` toward `<=3`.
- Local source granularity is visible in artifacts.
- Tests prove parent evidence cannot silently masquerade as exact-local evidence.

### Phase 3: Official Policy, Regulatory, And Extraction Quality

Objective:

- Improve official-policy/regulatory/land-record recall and reduce low-quality extracted content.

Tasks:

- Improve official-record task phrases for macro and provincial project claims.
- Add static recovery or clearer diagnostics for PDF/download pages where safe.
- Add content-quality signals for minimal text, homepage hits, generic policy pages, stale pages, and unrelated records.
- Keep unrecoverable binaries transparent.

Acceptance criteria:

- `environmental_or_land_record <= 2` remains stable.
- `regulatory_record` and `official_policy` gaps improve or are transparently explained.
- Extraction failures are classified and visible to the audit.

### Phase 4: Evidence Packaging For Audit Visibility

Objective:

- Ensure the judge sees enough high-signal evidence without changing public EvidenceBundle contracts.

Tasks:

- Review the compact artifact passed to DeepSeek.
- Preserve source title, URL, date, source class, region match, snippet, extraction status, and task family.
- Reduce noisy boilerplate where it hides relevant source text.
- Add deterministic tests for artifact compaction and audit-shape stability.

Acceptance criteria:

- DeepSeek audit input is explainable from artifacts.
- No shape diagnostics.
- No public API contract change.

### Phase 5: 12-Case Quality Gate

Objective:

- Re-run the 12-case live gate and DeepSeek audit.

Acceptance criteria:

- Live gate: `12 success / 0 runtime error`.
- Audit transport/schema: `12 success`, shape diagnostics `0`.
- Audit blockers: `0`.
- At least `6/12` cases are `weak_pass` or `pass`, or fail count falls to `<=6`.
- `project_list <= 5`.
- `tender_or_procurement <= 5`.
- `local_government <= 3`.
- `statistics <= 3`.
- `environmental_or_land_record <= 2`.
- Estimated Tavily credits are recorded and justified.

### Phase 6: Staged 50-Query Decision

Objective:

- Decide whether to expand to the 50-query live set.

Acceptance criteria:

- If Phase 5 passes, run staged offline/low-cost expansion before full live.
- If Phase 5 fails, record a narrower successor blocker and do not spend 50-query live budget.

## Continue Rule

After each milestone, continue automatically when:

- acceptance criteria are met
- required validations pass
- no credential, dependency, permission, or human-review blocker exists
- no high-risk contract change is required without PLAN authorization

Do not treat a milestone summary as a default stop point.

## Stop Conditions

Stop and request guidance if:

- a protected contract change is required
- live credentials are unavailable
- a source requires browser automation, OCR, login, paid access, or private data
- validation fails and the safe repair path is unclear
- external API behavior prevents reliable validation
- the user explicitly pauses

## Validation Loop

Minimum focused checks after implementation slices:

```powershell
python -m ruff check <changed files>
python -m py_compile <changed files>
pytest -q tests\test_sources_query_decomposition.py tests\test_sources_search_assisted_domestic.py tests\test_sources_source_resolver.py tests\test_sources_lane_execution.py tests\test_sources_local_source_patterns.py tests\test_sources_retrieval_plan.py
pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py
pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py
```

Live gate after remediation:

```powershell
python data\tmp\_source_quality_live_inspection.py --case-file data\tmp\source_quality_stress_eval\strong_evidence_smoke_cases_v1.json --mode extraction_inspection --max-search-tasks 2 --max-rounds 2 --max-candidates 3 --content-chars 1200 --output-dir data\tmp\source_quality_stress_eval\runs\source_evidence_quality_gate_v1_phase5_live_v1 --print-json
python data\tmp\_source_quality_llm_audit.py --run-dir data\tmp\source_quality_stress_eval\runs\source_evidence_quality_gate_v1_phase5_live_v1 --provider deepseek --model deepseek-v4-pro --thinking true --reasoning-effort max --timeout 240 --max-output-tokens 8192 --print-summary
python data\tmp\_source_quality_batch_report.py --run-dir data\tmp\source_quality_stress_eval\runs\source_evidence_quality_gate_v1_phase5_live_v1 --print-json
```

## Progress

- 2026-04-29: PLAN created from `source-evidence-sufficiency-remediation-v2` Phase 5 successor blocker.
- 2026-04-29: Phase 0 completed.
  - Baseline artifacts recorded.
  - Strong-evidence blocker frozen around project/tender evidence, local official precision, official/regulatory recall, extraction quality, and audit-visible evidence packaging.
  - Full 50-query live run remains deferred.
- 2026-04-29: Phase 1 completed with a narrow generalized project/tender phrase-order remediation.
  - Diagnosis:
    - Project fallback is capped at `2` search credits by default.
    - Several project tasks used the first two credits on `project list` and `start/production` phrases, so `tender/procurement` discovery often never ran.
    - Moving tender phrases too aggressively to the second slot initially improved C07/M06 but regressed C01/P04 project-list coverage.
  - Implementation:
    - Project-list style tasks now use a first phrase that combines `重点项目` with `开工/投产`.
    - The second phrase targets `公共资源交易 招标 中标`.
    - The third phrase keeps `项目清单` as a fallback.
    - Low-altitude and real-estate project phrases now also put public-resource/tender signals within the two-credit window.
    - Added the Phase 1 project/tender subset case file:
      - `data/tmp/source_quality_stress_eval/source_evidence_quality_gate_phase1_project_subset_cases.json`
  - Validation:
    - `pytest -q tests\test_sources_query_decomposition.py` -> `48 passed`
    - focused source suite -> `171 passed, 1 warning`
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
    - focused ruff -> pass
    - focused py_compile -> pass
    - JSON subset parse check -> `case_count=7`, targets `project_list/tender_or_procurement`
  - Low-cost live subset:
    - First run artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase1_project_subset_v1`
    - First run result: `7 success`, `12` Tavily credits, but C01/P04 project-list coverage regressed.
    - Final artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase1_project_subset_v2`
    - Final result: `7 success`, `11` Tavily credits, average latency `5905.07 ms`, `query_invalid_count=0`.
    - Final observed coverage:
      - `C07`: covered `project_list` and `tender_or_procurement`.
      - `M06`: covered `project_list` and `tender_or_procurement`.
      - `C01`, `M02`, `P04`: covered `project_list`; tender/procurement still missing.
      - `K12`: still missing both project classes due sparse county recall.
      - `P08`: accepted project PDFs but Crawl4AI returned download/zero-usable-evidence behavior; this is now an extraction/PDF issue.
  - Phase 1 decision:
    - The phrase-order fix improves project evidence recall without increasing the default search-credit cap.
    - Remaining project/tender gaps are no longer just phrase-order problems; they belong to Phase 2 local precision and Phase 3 PDF/extraction quality.
- 2026-04-29: Phase 2 completed with a generalized exact-local-first local rollout remediation.
  - Diagnosis:
    - The C09 local rollout query was no longer a task-family or source-class issue; the first-wave `include_domains` mixed exact Xi'an domains with Shaanxi parent domains.
    - Tavily preferred high-scoring parent/provincial results when parent domains were in the same first-wave domain pool.
    - `domains_for_task()` had a commercial-space parent-domain guard, but `repair_task_candidate()` and local-backbone domain expansion could reintroduce parent domains.
  - Implementation:
    - Added an exact-local-first local rollout domain mode for municipal commercial-space tasks.
    - Added `xcaib.xa.gov.cn` as a Xi'an local-government and project/public-resource source pattern.
    - Phase 2 local rollout now keeps parent evidence as fallback metadata instead of mixing parent domains into the first-wave exact-local pool.
    - Added the Phase 2 local subset case file:
      - `data/tmp/source_quality_stress_eval/source_evidence_quality_gate_phase2_local_subset_cases.json`
  - Validation:
    - `pytest -q tests\test_sources_query_decomposition.py -k "xian_commercial_space"` -> `2 passed`
    - `pytest -q tests\test_sources_local_source_patterns.py` -> `8 passed`
    - `pytest -q tests\test_sources_query_decomposition.py` -> `48 passed`
    - focused ruff -> pass
    - focused py_compile -> pass
    - focused source suite -> `171 passed, 1 warning`
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
  - Low-cost live subset:
    - Final artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase2_local_subset_v3`
    - Result: `4 success`, estimated Tavily credits `4`, average latency `21950.08 ms`, `query_invalid_count=0`.
    - Observed local coverage:
      - `C09`: covered `local_government` and `official_policy` through exact-city Xi'an official evidence; first-wave domains are now `xa.gov.cn`, `xadrc.xa.gov.cn`, `xakj.xa.gov.cn`, and `xcaib.xa.gov.cn`.
      - `K07`: covered `local_government` and `official_policy` through exact county seed fallback; extraction still hit anti-bot diagnostics.
      - `K09` and `K12`: covered local source classes but remained parent/city fallback with `parent_evidence_only=true` and `local_claim_allowed=false`.
  - Phase 2 decision:
    - The main local-government gap is now materially improved for the city-level C09 case without hardcoding a single Tavily result.
    - Remaining risks move to Phase 3 and Phase 4: timeout/anti-bot extraction, misleading best fallback source when the highest-scored accepted candidate fails extraction, and judge-visible evidence packaging.
- 2026-04-29: Phase 3 completed with a focused official-record evidence-quality hardening.
  - Diagnosis:
    - Official-record PDF/static extraction already existed, but evidence quality could be inflated when `discovery_query` terms were reused as document topic evidence.
    - P08-style sparse PDF cover text could be treated as strong evidence even when the extracted PDF text did not contain the actual topic terms.
    - Some PDF/download failures are real source-access failures; these should remain visible rather than be hidden by unrelated accepted candidates.
  - Implementation:
    - Official-record weak-document filtering now excludes `discovery_query` from document relevance and signal checks.
    - Direct-lane evidence-quality scoring now excludes `discovery_query` from the topic/source-class evidence haystack.
    - Added a regression test proving discovery-query-only topic matches are rejected for official-record evidence.
    - Added the Phase 3 official/extraction subset case file:
      - `data/tmp/source_quality_stress_eval/source_evidence_quality_gate_phase3_official_extraction_subset_cases.json`
  - Validation:
    - `pytest -q tests\test_sources_lane_execution.py -k "official_record_relevance_does_not_trust_discovery_query_only"` -> `1 passed`
    - `pytest -q tests\test_sources_lane_execution.py -k "official_record"` -> `19 passed, 1 warning`
    - focused ruff -> pass
    - focused py_compile -> pass
    - focused source suite -> `172 passed, 1 warning`
    - source regression -> `27 passed`
    - domestic regression -> `16 passed`
  - Low-cost live subset:
    - First run artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase3_official_extraction_subset_v1`
    - First run result: `3 success / 1 error`; `M03` had no `official_record` lane and was removed from this official-record-specific subset.
    - Final artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase3_official_extraction_subset_v2`
    - Final result: `4 success`, estimated Tavily credits `11`, average latency `8151.06 ms`, `query_invalid_count=0`.
    - Observed behavior:
      - `P08`: retained usable MEE HTML official-record evidence and surfaced one PDF download failure.
      - `K09`: retained usable official-record HTML/PDF evidence and surfaced one `zero_text` PDF failure.
      - `M02` and `K07`: no accepted official-record candidate in this slice, but completed without runtime errors.
  - Phase 3 decision:
    - Strong-evidence quality is now more conservative because retrieval query text can no longer make an unrelated extracted document look topical.
    - Remaining work moves to Phase 4: make extraction failures, rejected weak documents, and evidence-quality reasons more visible in the compact audit input.
- 2026-04-29: Phase 4 completed with compact audit-input visibility hardening.
  - Diagnosis:
    - DeepSeek receives compacted per-query artifacts when raw extraction payloads exceed the prompt budget.
    - The previous compact view preserved task/document payloads but did not provide an explicit high-signal audit summary for evidence-quality reasons, rejected documents, direct fallback diagnostics, or extraction failure classes.
    - This could make the judge over-focus on visible snippets and miss why a lane was weak, rejected, or partially failed.
  - Implementation:
    - Added compact `audit_summary` generation for oversized artifacts in `data/tmp/_source_quality_llm_audit.py`.
    - The summary preserves task family, source-class coverage, coverage gaps, direct fallback statuses, selected counts, estimated credits, evidence-quality summaries, rejected-document reasons, document source classes, extraction metadata, and structured error classes.
    - Added a deterministic audit-compaction regression test covering evidence-quality details, rejected documents, PDF extraction failures, and document source-class summaries.
  - Validation:
    - `pytest -q tests\test_source_quality_llm_audit.py tests\test_source_quality_batch_report.py tests\test_source_quality_live_inspection.py` -> `8 passed, 1 warning`
    - `python -m ruff check data\tmp\_source_quality_llm_audit.py tests\test_source_quality_llm_audit.py tests\test_source_quality_batch_report.py tests\test_source_quality_live_inspection.py` -> pass
    - `python -m py_compile data\tmp\_source_quality_llm_audit.py tests\test_source_quality_llm_audit.py tests\test_source_quality_batch_report.py tests\test_source_quality_live_inspection.py` -> pass
    - Phase 3 compact-shape smoke check on `source_evidence_quality_gate_v1_phase3_official_extraction_subset_v2` confirmed oversized artifacts now include `audit_summary`.
  - Phase 4 decision:
    - Audit packaging is now visible enough to rerun the 12-case quality gate.
    - Small artifacts are left unchanged to avoid unnecessary token overhead; oversized artifacts receive the explicit summary.
- 2026-04-29: Phase 5 completed and Phase 6 recorded successor blocker.
  - Live gate:
    - Artifact: `data/tmp/source_quality_stress_eval/runs/source_evidence_quality_gate_v1_phase5_live_v1`
    - Result: `12 success / 0 runtime error`
    - Estimated Tavily credits: `75`
    - Average latency: `44521.71 ms`
  - DeepSeek audit:
    - Result: `12 success`, shape diagnostics `0`
    - Verdicts: `10 fail / 2 weak_pass / 0 pass`
    - Total tokens: `424427`
  - Batch report:
    - `project_list=6`
    - `tender_or_procurement=7`
    - `local_government=1`
    - `statistics=1`
    - `environmental_or_land_record=2`
    - `requires_reopening_plan_items=7`
  - Acceptance result:
    - Runtime and schema gates passed.
    - Quality gate failed because `weak_pass/pass=2/12` and `fail=10`; project/tender gaps remained above target.
  - Phase 6 decision:
    - Do not run the full 50-query live set.
    - Open successor PLAN `.agent/PLANS/source-structured-evidence-backbone-v1.md` focused on reusable public-resource/procurement, project-list, official-record, regional disclosure, and industry evidence backbones.

## Current Phase

Completed with successor blocker.

## Risks And Rollback

Risks:

- DeepSeek may remain stricter than deterministic source-class metrics.
- Public-resource pages can be PDF/download-heavy and unstable.
- More project recall can increase Tavily credits.
- City/county exact-local evidence may be unavailable for some public sources.
- Dirty worktree remains broad; do not revert unrelated changes.

Rollback:

- Revert only files changed under this PLAN.
- Preserve the previous baseline run `source_evidence_sufficiency_v2_phase5_live_v1` for comparison.
- Disable new source-profile patterns if they introduce domain/topic drift.

## Next Action

Continue with `.agent/PLANS/source-structured-evidence-backbone-v1.md`. Do not run the full 50-query live set until the successor PLAN passes a 12-case quality gate or records a narrower blocker.
