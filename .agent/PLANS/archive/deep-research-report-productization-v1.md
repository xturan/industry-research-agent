# Deep Research Report Productization v1

Status: superseded_by_quality_v2

Created: 2026-06-15

Primary active PLAN: no

Superseded by:

- `.agent/PLANS/deep-research-readable-report-quality-v2.md`

Reason:

- The previous productization plan established the broad direction and partial
  implementation baseline. The next execution cycle now needs a stricter PRD
  and quality-gated PLAN focused on turning Markdown output into a product-grade
  readable Deep Research report.

## Objective

Turn the current opt-in LangGraph / harness path into a production-oriented
Deep Research report system whose final user-facing artifact is a readable,
long-form Chinese Markdown report in the style and functional depth of the
reference `deep-research-report*.md` files, while keeping JSON outputs as an
audit layer rather than the final product itself.

Selected direction:

```text
Harness is the control plane, not the business substitute.
It should constrain agent behavior, tool permissions, retries, human review,
and auditability, but it must not collapse the research product into
structured-only output.
```

Reference report targets:

- `E:/Edge_download/deep-research-report.md`
- `E:/Edge_download/deep-research-report (1).md`
- `E:/Edge_download/deep-research-report (2).md`

Observed target characteristics from the reference reports:

- final artifact is long-form Chinese Markdown, roughly 10k-20k characters
- strong `执行摘要`
- explicit `方法与口径` or equivalent scope/method section
- dimension-driven chaptering such as 政策、披露、地方、项目、产业链、风险、建议
- tables, timelines, or `mermaid` diagrams when they improve readability
- clear separation between facts, inference, uncertainty, and follow-up work
- report body is readable on its own, while audit JSON remains traceable behind it

## Task Classification

- Primary area: `research_workflow`
- Secondary areas:
  - `content_factory`
  - `provider_layer`
  - `source_layer`
  - `memory_feedback`
  - `eval_policy_ops`
  - `task_substrate`
  - `delivery_layer`
- Expected execution mode:
  - `full_subagent` for retrieval architecture, evidence/claim redesign, report writing system, persistence, and API-visible behavior
  - `light_subagent` for isolated helper, schema-safe formatter, and dossier/report polish slices
  - `remediation_gate` for failed live validation or report-quality regressions

## Scope

In scope:

- redesigning planner outputs around explicit research dimensions
- integrating chunk-aware hybrid retrieval for downstream research context
- replacing deterministic evidence/claim authorship with LLM-authored synthesis plus deterministic validation
- redesigning editor prompts, context packs, and human-review exposure
- rebuilding the final report into a readable deep-research Markdown artifact
- adding two-layer memory that feeds future planning
- preserving audit JSON, dossier, and run traceability as secondary artifacts

Out of scope for this plan:

- replacing legacy `/deep-research/analyze` or `/research/analyze` as defaults
- browser automation, OCR, login-gated sources, or paid/private source expansion unless explicitly reopened by another plan
- broad product UI redesign beyond what is required to surface `HUMAN_REVIEW` and final report artifacts correctly
- weakening auditability in order to improve writing style

## Constraints

- `graph_v1` must remain opt-in until the live product gate is passed
- every conclusion in the final report must remain traceable to evidence lineage
- harness governance must remain explicit per node: tools, context, fallback, and audit
- final report readability cannot be traded away for schema neatness
- retrieval, memory, and report-writing changes must remain compatible with the existing production-oriented monorepo and database direction
- the product must remain positioned as industry intelligence and research assistance rather than direct securities investment advice

## Protected Contracts

Do not silently change:

- legacy `/deep-research/analyze` response shape
- legacy `/research/analyze` response shape
- public `DeepResearchReport`, `EvidenceItem`, `SourceAssessment` schemas unless explicitly planned
- existing citation traceability requirements
- task/job status semantics
- `runs` / `run_steps` meaning
- `human_review` pause/resume semantics
- content asset metadata compatibility
- the product boundary that the system provides industry intelligence and research assistance rather than direct securities investment advice

If any protected contract must change, document:

- why the change is required
- backward compatibility impact
- migration path
- validation commands

## Product Definition

Key principles:

- `Harness`:
  指 research harness。它位于 workflow 的控制层，负责约束 agent 行为、工具权限、上下文预算、重试、人工审核与审计追踪。使用它的价值，是让多 agent 工作流更可控、更安全、更可回放；不使用它时，系统更容易退化成黑箱 prompt 链。新增代价是每个节点都要明确 contract、tooling 和 fallback，工程复杂度会上升。
- `Final report`:
  指最终交付给用户阅读的深度研究报告正文。它属于产品交付层，必须可直接阅读、可讨论、可复核，而不是让用户自己去拼 JSON。
- `Dimension plan`:
  指 `plan_task` 先把 query 拆成明确研究维度，例如政策维度、披露维度、地方维度、项目维度、产业链维度、风险维度。它属于研究规划阶段，用来决定搜索范围、轮次、来源义务和章节骨架。没有它时，搜索会变成泛泛而谈的“找一些资料”；有了它，搜索才会围绕明确的研究问题展开。
- `Evidence`:
  指有论证意义的证据单元，不等于单条 source，也不等于单个 chunk。一个 evidence 可以由多个 sources / chunks 归并而成，并应显式说明支持什么、限制什么、冲突什么。
- `Claim`:
  指可审计的研究断言，属于研究推理层。一个 claim 可以由多个 evidence 支撑或反驳，并应区分事实性 claim、解释性 claim、风险性 claim、待核实 claim。
- `Memory`:
  指运行后沉淀的主题偏好、查询倾向、反复出现的关注点和总结结果。它属于长期反馈层，作用是让 `plan_task` 不再每次从零开始。

Current unacceptable behavior to eliminate:

1. `plan_task` still tolerates vague planning instead of explicit dimension coverage.
2. `evidence` and `claim` are still heavily program-mapped instead of LLM-authored with logical synthesis.
3. `editor1` / `editor2` do not yet behave like real researchers with role-grounded prompts and context.
4. retrieval still bypasses the intended chunk + PostgreSQL + pgvector + BM25 + reranker path.
5. memory does not yet exist as a two-layer production feature feeding back into planning.
6. final report is still too close to an audit preview instead of a true readable research report.

## Golden Output Contract

The final product of this plan is not `response.json`. The final product is:

```text
Readable deep-research Markdown report
  + auditable structured sidecar
  + human-review checkpoint artifacts
  + dossier / run trace for internal inspection
```

Required report qualities:

- the primary artifact is `report_markdown`
- the report body is Chinese, readable, and dimension-structured
- the report should normally include:
  - title
  - executive summary
  - method/scope/caliber statement
  - dimension-driven body sections
  - evidence tables or comparative tables when useful
  - uncertainty / risk / blocker section
  - conclusion and next-step research suggestions
  - source / citation appendix or embedded source notes
- not every query must use identical headings, but each report must provide equivalent analytical functions
- major factual statements must remain traceable to evidence and source lineage
- tables, timelines, and `mermaid` are optional tools for readability, not decorative requirements
- raw JSON, contract diagnostics, and tool traces belong to audit surfaces, not to the main report body

Unacceptable end state:

- a report that is only one short section with a few bullet claims
- a body that reads like schema dump or stitched JSON
- evidence scores without practical interpretability
- `HUMAN_REVIEW` existing in storage but not clearly exposed to the user workflow

## Architecture Direction

### 1. Planner must become explicit dimension planning

`plan_task` must stop producing vague intent language such as “some sources” or
“a few rounds”. It must produce explicit, inspectable research dimensions and
coverage obligations.

Required planner outputs:

- `dimension_plan`:
  each dimension must declare `dimension_type`, `research_question`,
  `why_it_matters`, `coverage_required`, and expected chapter usage
- `source_obligations`:
  each dimension must declare what source families are mandatory
- `search_rounds`:
  each round must declare exact objective, target dimension(s), source scope,
  and stop condition
- `memory_inputs`:
  planner must ingest summarized prior-run memory when available

Mandatory dimension examples when relevant:

- 政策维度
- 披露维度
- 地方维度
- 项目/招采维度
- 产业链维度
- 统计/验证维度
- 风险与不确定性维度

### 2. Retrieval must use chunks plus hybrid search

The system should reuse the existing chunking capabilities and move retrieval
to a hybrid stack instead of feeding entire sources directly into downstream
agents.

Retrieval components:

- `chunk`:
  把长文档切成较小、可定位、可引用的文本单元。相比整篇 source 直接喂给 agent，chunk 的价值是能减少无关上下文、提高证据定位精度；代价是需要维护 chunk 边界、章节元数据和引用映射。
- `pgvector`:
  PostgreSQL 的向量检索能力，用来按语义召回相关 chunks。相比只靠关键词，它能找到同义表达和语义近邻；代价是需要 embedding 建库和索引维护。
- `BM25`:
  关键词稀疏检索，用来抓政策名、地名、项目名、年份、公告编号这类精确词命中。相比纯向量检索，它对实体词和精确匹配更强；不足是同义召回能力弱。
- `reranker`:
  对 hybrid 检索候选进行再次排序，挑出真正最可引用的 chunks。相比不做 rerank，前几名结果会更稳定、更贴 query；代价是多一次模型或服务调用。

Target retrieval flow:

```text
source acquisition
  -> parse / normalize
  -> chunk
  -> pgvector + BM25 hybrid retrieval
  -> reranker
  -> auditable retrieval pack
  -> evidence synthesis context
```

### 3. Evidence and claim must be LLM-authored with logic

`evidence` and `claim` must no longer be simple program-mapped projections.

Required redesign:

- one evidence may merge multiple chunks and multiple sources
- one claim may depend on multiple supporting or conflicting evidence items
- evidence generation prompt must explain:
  - what proposition the evidence supports
  - what it does not prove
  - what time/location/entity scope it applies to
  - what contradictory or weak signals exist
- claim generation prompt must explain:
  - what the claim is
  - whether it is fact / interpretation / risk / uncertainty
  - which evidence bundle supports it
  - what caveats remain

Deterministic logic should remain as validator and scorer, not as the main author of research meaning.

### 4. Editor roles must match real research work

`editor1` and `editor2` must be redesigned around real analyst roles.

- `Editor1`:
  首席研究员/初稿作者。负责把 dimension plan、claim graph、evidence bundles 和 retrieval context 写成第一版报告骨架与章节正文。
- `Editor2`:
  审稿研究员/反方审校。负责找出论证跳跃、证据不足、章节失衡、表述夸张、风险遗漏与待核实项。

Both prompts must be audited for:

- role identity
- writing objective
- allowed evidence scope
- prohibited behavior
- output contract
- section-level context packing strategy

### 5. Memory must be two-layer and feed the planner

Memory design:

- Layer 1 `raw_run_memory`:
  原始运行层，保存 summary JSON、dossier、关键中间产物和数据库运行记录。
- Layer 2 `summary_memory`:
  API summary 层，对多次运行出现的关键词、倾向、主题关注点、重复缺口和偏好进行聚合总结。

Memory update rule:

- do not update memory on one-off noise
- update only when repeated keywords, themes, or tendencies appear across runs
- every memory update must be traceable back to the raw run layer
- planner consumes summary memory as context for future dimension planning

## Agent Execution Contract

Role binding for this plan:

- `Planner / Dimension Planner`:
  owns explicit dimension decomposition, source obligations, round planning, and memory-aware planning
- `Source Hunter / Retrieval Strategist`:
  owns source acquisition boundaries and retrieval pack quality
- `Parser/Structurer / Chunk Builder`:
  owns parsing, normalization, chunking, metadata integrity, and chunk traceability
- `Evidence Synthesizer`:
  owns LLM-authored evidence bundle generation across multiple chunks/sources
- `Claim Builder`:
  owns LLM-authored claim graph construction and claim taxonomy
- `Editor1 Lead Analyst`:
  owns first-draft report outline and section writing
- `Editor2 Review Analyst / Opponent`:
  owns critique, gap detection, uncertainty elevation, and revision instructions
- `Evidence Judge / Verifier`:
  owns deterministic and model-assisted support validation
- `Chief Gate`:
  owns routing, risk escalation, and `HUMAN_REVIEW` decisions
- `Report Composer / Supervisor`:
  owns final Markdown report assembly and audit sidecar packaging
- `Memory Summarizer`:
  owns summary-memory updates from accumulated run history

Harness policy for all nodes:

- tool permissions must be explicit per node
- context budget must be enforced and observable
- fallbacks must degrade safely without redefining the product goal
- no node may replace report writing with schema-only output and still claim success

## Phases

### Phase 0: Freeze Product Contract And Golden Report Rubric

Status: completed

Objective:

- freeze what “good final output” means using the three reference reports
- freeze harness role boundaries so control-plane work cannot replace business semantics
- freeze the initial prompt/context audit matrix for each major node

Acceptance criteria:

- a written report-quality rubric exists and is attached to this plan or its follow-up docs
- the target report contract is explicit enough that implementation can be judged against it
- current workflow gaps are mapped node-by-node

Validation:

- reference report structures decoded and summarized
- active PLAN / STATUS / INDEX aligned
- rubric document created:
  - `.agent/PLANS/deep-research-report-rubric-v1.md`
- node-by-node contract matrix created:
  - `.agent/PLANS/deep-research-agent-contract-matrix-v1.md`

### Phase 1: Redesign `plan_task` Around Explicit Dimensions And Memory

Status: completed

Objective:

- replace vague planner output with dimension-explicit planning
- inject summary memory into planner context

Acceptance criteria:

- planner output names concrete dimensions, source obligations, and search rounds
- planner forbids vague quantifiers in final structured plan text
- dimension plan feeds downstream retrieval and writing stages

Validation:

- unit tests for planner output contract
- live smoke on policy-heavy, disclosure-heavy, and locality-sensitive queries

### Phase 2: Build Hybrid Retrieval Substrate On Chunks

Status: completed

Objective:

- move downstream context assembly from whole-source bias to chunk-level hybrid retrieval

Acceptance criteria:

- parsed sources are chunked with stable metadata
- PostgreSQL + pgvector retrieval is integrated for semantic recall
- BM25 is integrated for precise lexical recall
- reranker is integrated for final retrieval ordering
- retrieval packs remain auditable back to source and chunk ids

Validation:

- retrieval-focused tests for chunk lineage and ranking behavior
- live queries show chunk-level evidence pickup rather than whole-document dumping

### Phase 3: Replace Program-Mapped Evidence / Claim With LLM Synthesis

Status: in_progress

Objective:

- generate evidence and claims through role-grounded prompts using retrieval packs

Acceptance criteria:

- evidence may merge multiple chunks and sources
- claims may aggregate multiple evidence items
- evidence and claims carry logical caveats, not just score fields
- claim volume scales with report dimensions instead of collapsing to one coarse claim per round

Validation:

- schema tests for evidence / claim contracts
- live cases show materially richer evidence and claim graphs than the current deterministic mapping

### Phase 4: Redesign Research Writer Roles And Human Review Surface

Status: pending

Objective:

- redesign `editor1` and `editor2` as real research roles
- make `HUMAN_REVIEW` visible and actionable in API/UI flows

Acceptance criteria:

- editor prompts and context packs are documented and auditable
- editor outputs reflect research structure, not schema-dump language
- human review payload is clearly surfaced when triggered

Validation:

- prompt/context audit doc for editor nodes
- smoke case with forced and organic `HUMAN_REVIEW`

### Phase 5: Build The Final Readable Report System

Status: pending

Objective:

- generate the final report as a real readable Markdown artifact rather than a deterministic preview

Acceptance criteria:

- final report contains executive summary, method/scope, dimension sections, risks/uncertainty, and conclusion/next steps
- tables, timelines, or diagrams are inserted where they improve comprehension
- report body is readable without opening JSON
- audit JSON remains available as sidecar instead of replacing the report

Validation:

- report rendering tests
- readability spot checks against the golden rubric
- live artifacts for the three reference-style case families

### Phase 6: Add Two-Layer Memory And Planner Feedback Loop

Status: pending

Objective:

- persist raw run memory and build summary memory that feeds future planning

Acceptance criteria:

- raw run memory stores summary JSON, dossier, and important run metadata
- summary memory updates only on repeated signals
- planner can consume summary memory safely and audibly

Validation:

- memory update tests
- repeated-run simulation showing no memory update on one-off noise and update on repeated trends

### Phase 7: Live Product Gate Against Golden Cases

Status: pending

Objective:

- prove that the rebuilt path produces report-quality output in real cases

Golden case families:

- policy + local rollout case
- disclosure-heavy case
- procurement / policy case
- at least one additional contradiction-or-uncertainty-heavy case

Acceptance criteria:

- each case produces a readable report that passes the rubric
- claim/evidence density is materially better than the current baseline
- human review appears when warranted and is visible
- graph_v1 remains opt-in until this gate is passed

Validation:

- live smoke runs with real provider calls
- dossier and audit artifact inspection
- before/after comparison against the current baseline outputs

## Continue Rule

After each phase, continue automatically to the next phase when:

- acceptance criteria are met
- required validation passes
- no approval, credential, runtime, or human-review blocker exists
- no protected contract change is required beyond what this plan already authorized

Do not stop merely because one phase summary is complete.

## Done Condition

This plan is done only when all of the following are true:

- the primary LangGraph report artifact is a readable deep-research Markdown report aligned to the golden contract
- planner output is dimension-explicit and memory-aware
- retrieval uses chunk-aware hybrid search with auditable ranking
- evidence and claims are LLM-authored and logically structured
- editor prompts/contexts reflect real research roles
- two-layer memory exists and feeds future planning
- live golden cases demonstrate materially improved output quality

## Stop Conditions

Stop and realign only when:

- the work starts improving audit structure while worsening final report quality
- a protected contract change is unexpectedly required
- the required retrieval/database/runtime dependencies are unavailable
- live validation repeatedly fails without a safe repair path
- the user explicitly pauses or changes product direction

## Validation Loop

Planning-step validation completed in this turn:

- decode and inspect the three reference report files
- confirm target report characteristics
- align new PLAN, STATUS, and plan index

Implementation-phase validation targets:

```powershell
python -m py_compile packages\research_harness\*.py packages\research_reports\*.py scripts\*.py tests\*.py
python -m ruff check packages\research_harness packages\research_reports scripts tests
pytest -q tests\test_research_harness_graph.py
pytest -q tests\test_research_run_dossier.py
pytest -q tests\test_retrieval_*.py
pytest -q tests\test_research_memory_*.py
python scripts\graph_provider_backed_smoke.py --query "<golden case query>" --execution-mode provider_backed
```

Additional validation requirements to add during implementation:

- prompt/context audit snapshots for each major agent
- report-rubric checks on final Markdown
- before/after comparisons on claim count, evidence density, and human-review visibility

## Progress

- 2026-06-15: user explicitly corrected the product goal back to readable deep-research reports and away from structured-only outputs
- 2026-06-15: golden reference reports were decoded and their structural features were extracted
- 2026-06-15: this PLAN was created as the new primary active plan
- 2026-06-15: Phase 0 deliverables were written:
  - report-quality rubric
  - node-by-node prompt/context contract matrix
- 2026-06-15: active execution focus advanced to Phase 1 planner + memory contract implementation
- 2026-06-16: Phase 3 editor1 context quality fixes implemented:
  - `_compact_evidence_bundle` shape detection: handles both evidence-centric
    (evidence_id/summary/source) and claim-centric (claim_id/claim_text/evidence[])
    formats, fixing the null-items bug where editor1 saw empty evidence bundles
  - `_safe_limitations_list`: prevents char-split when limitations come as a
    string (list("政策为内蒙古") → ["政策为内蒙古"], not ["政","策",...])
  - `_tool_compose_section_outline`: groups claims by claim_family for
    dimension-based sections instead of one "Evidence-backed claims" section
  - prior fallback draft filtering: skips drafts with fallback markers so
    editor1 doesn't see failed drafts as reference
  - Injected fixed functions into bytecode module via _sync_impl_dependencies
- 2026-06-16: Phase 3 evidence/claim semantic enrichment implemented:
  - `_enrich_evidence_semantics`: query relevance scoring, limitations fix,
    source-family-based relevance boost
  - `_enrich_claim_semantics`: evidence-to-claim traceability, auto-derived
    claim_family, linked evidence quality metadata
  - Applied in `build_evidence_provider_backed` and `build_claims_provider_backed`
  - Smoke verified: limitations no longer char-split, evidence relevance
    improved (合肥 policy source instead of Inner Mongolia PDF)
- 2026-06-15: Phase 1 slice 1 implemented in code:
  - `ResearchGraphState` now carries `summary_memory`
  - `plan_task_provider_backed` now passes `summary_memory` into planner calls and exposes planner metadata for `summary_memory_used` plus `summary_memory_keys`
  - `SemanticPlanPayload` now includes explicit `dimension_plan`
  - planner prompt now explicitly asks for `dimension_plan`, bans vague quantifiers, and scopes `summary_memory` to recurring themes / repeated gaps rather than factual evidence
  - deterministic fallback planner now emits formal `dimension_plan` entries for policy, local rollout, execution, disclosure, and statistics dimensions when relevant
- 2026-06-15: Phase 1 slice 1 validation passed:
  - `python -m py_compile packages\research_harness\plan_semantic.py packages\research_harness\real_nodes.py packages\research_harness\state.py tests\test_research_harness_plan_semantic.py tests\test_research_harness_graph.py tests\test_research_harness_state.py`
  - `python -m ruff check packages\research_harness\plan_semantic.py packages\research_harness\real_nodes.py packages\research_harness\state.py tests\test_research_harness_plan_semantic.py tests\test_research_harness_graph.py tests\test_research_harness_state.py`
  - `pytest -q tests\test_research_harness_plan_semantic.py`
  - `pytest -q tests\test_research_harness_state.py`
  - `pytest -q tests\test_research_harness_graph.py -k "plan_task_provider_backed or build_initial_state"`
- 2026-06-15: Phase 1 slice 2 implemented:
  - `runner` now exposes planner-side `dimension_plan` counts and `dimension_types` in `plan_task` step output summaries
  - graph dossier now renders a dedicated `Planner Contract` section showing planner mode, dimension-plan rows, and summary-memory input
  - planner-side memory contract was frozen in:
    - `.agent/PLANS/deep-research-memory-contract-v1.md`
- 2026-06-15: Phase 1 slice 2 validation passed:
  - `python -m py_compile packages\research_harness\runner.py packages\research_reports\dossier.py tests\test_research_run_dossier.py tests\test_research_harness_graph.py`
  - `python -m ruff check packages\research_harness\runner.py packages\research_reports\dossier.py tests\test_research_run_dossier.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_research_run_dossier.py`
  - `pytest -q tests\test_research_harness_graph.py -k "provider_backed_uses_search_provider or provider_backed_editor1_records_tool_traces"`
- 2026-06-15: Phase 1 final cleanup completed:
  - shadow planner path now also emits formal `dimension_plan`
  - `.agent/PLANS/deep-research-memory-contract-v1.md` now includes a concrete Phase 6 task breakdown
- 2026-06-15: Phase 2 slice 1 implemented:
  - `parse_sources` now produces graph-local `source_chunks`
  - graph now emits an auditable `retrieval_pack` with `graph_source_chunk_lexical_v1`
  - node-step summaries and dossier now surface chunk/retrieval-layer audit details
  - implementation reuses existing chunking semantics from `packages.ingestion.chunker` instead of inventing a separate graph-only chunk contract
- 2026-06-15: Phase 2 slice 1 validation passed:
  - `python -m py_compile packages\research_harness\state.py packages\research_harness\nodes.py packages\research_harness\real_nodes.py packages\research_harness\context.py packages\research_harness\retrieval_bridge.py packages\research_harness\runner.py packages\research_reports\dossier.py tests\test_research_harness_state.py tests\test_research_harness_graph.py tests\test_research_run_dossier.py`
  - `python -m ruff check packages\research_harness\state.py packages\research_harness\nodes.py packages\research_harness\real_nodes.py packages\research_harness\context.py packages\research_harness\retrieval_bridge.py packages\research_harness\runner.py packages\research_reports\dossier.py tests\test_research_harness_state.py tests\test_research_harness_graph.py tests\test_research_run_dossier.py`
  - `pytest -q tests\test_research_harness_state.py`
  - `pytest -q tests\test_research_run_dossier.py`
  - `pytest -q tests\test_research_harness_graph.py -k "provider_backed_uses_search_provider or shadow_plan_task_emits_dimension_plan or plan_task_provider_backed_exposes_summary_memory_usage"`
- 2026-06-15: Phase 2 slice 2 implemented:
  - `build_graph_retrieval_artifacts` now accepts planner-side `dimension_plan` and `source_obligations`
  - graph retrieval moved from query-only lexical ranking to a graph-runtime hybrid contract that combines:
    - query lexical match
    - dimension-term match
    - source-family obligation match
    - source-family weighting
    - target-location alignment
  - retrieval artifacts now expose:
    - `dimension_focus`
    - `obligation_focus`
    - richer `score_breakdown` fields such as `dimension_bonus`, `obligation_bonus`, `location_bonus`, and `source_family_bonus`
  - graph dossier now renders a dedicated `Retrieval Focus Contract` section so retrieval intent can be audited before evidence/claim synthesis
- 2026-06-15: Phase 2 slice 2 validation passed:
  - `python -m py_compile packages\research_harness\retrieval_bridge.py packages\research_harness\nodes.py packages\research_harness\real_nodes.py packages\research_reports\dossier.py tests\test_research_harness_graph.py tests\test_research_run_dossier.py`
  - `python -m ruff check packages\research_harness\retrieval_bridge.py packages\research_harness\nodes.py packages\research_harness\real_nodes.py packages\research_reports\dossier.py tests\test_research_harness_graph.py tests\test_research_run_dossier.py`
  - `pytest -q tests\test_research_harness_graph.py -k "build_graph_retrieval_artifacts_uses_dimension_and_obligation_focus or provider_backed_uses_search_provider or shadow_plan_task_emits_dimension_plan or plan_task_provider_backed_exposes_summary_memory_usage"`
  - `pytest -q tests\test_research_run_dossier.py`
- 2026-06-15: Phase 2 slice 3 implemented:
  - `ToolSession` now carries the runner SQLAlchemy session so graph nodes can opt into scoped database-backed helpers without changing node signatures again
  - `parse_sources` now passes `run_id` plus runner session into the retrieval bridge
  - retrieval bridge now supports a persistent graph retrieval adapter:
    - current graph-run sources are normalized into scoped `Document` / `DocumentChunk` / `Citation` rows
    - backend retrieval is delegated to `ChunkRetrievalService`
    - retrieval is constrained to the current graph run's persisted document ids instead of polluting global retrieval scope
    - backend retrieval results are re-ranked with graph-specific dimension / obligation / location focus bonuses
  - retrieval audit output now exposes:
    - `adapter_status`
    - `persisted_document_ids`
    - `backend_retrieval_mode`
  - dossier retrieval summary now renders adapter/backend retrieval status so persistent-vs-fallback behavior is visible without opening JSON
- 2026-06-15: Phase 2 slice 3 validation passed:
  - `python -m py_compile packages\research_harness\retrieval_bridge.py packages\research_harness\tooling\harness.py packages\research_harness\runner.py packages\research_harness\nodes.py packages\research_harness\real_nodes.py packages\research_reports\dossier.py tests\test_research_harness_graph.py tests\test_research_run_dossier.py`
  - `python -m ruff check packages\research_harness\retrieval_bridge.py packages\research_harness\tooling\harness.py packages\research_harness\runner.py packages\research_harness\nodes.py packages\research_harness\real_nodes.py packages\research_reports\dossier.py tests\test_research_harness_graph.py tests\test_research_run_dossier.py`
  - `pytest -q tests\test_research_harness_graph.py -k "persists_graph_runtime_chunks_for_scoped_retrieval or build_graph_retrieval_artifacts_uses_dimension_and_obligation_focus or provider_backed_uses_search_provider"`
  - `pytest -q tests\test_research_run_dossier.py`
  - `pytest -q tests\test_rag_retrieval.py`
  - `pytest -q tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py`
  - note: full `pytest -q tests\test_research_harness_graph.py` hit the current tool timeout window and should be rerun with a longer timeout if needed
- 2026-06-15: Phase 2 slice 4 implemented:
  - scoped graph retrieval documents now carry explicit lifecycle metadata:
    - `graph_runtime_document=true`
    - `graph_run_id`
    - `retention_policy=delete_on_terminal_run`
  - retrieval audit payload now exposes:
    - `retention_policy`
    - `cleanup_scope`
  - `ResearchGraphRunner._finish_run(...)` now performs scoped graph document cleanup only for terminal runs
  - `HUMAN_REVIEW` pending runs deliberately skip cleanup so resume can continue with intact retrieval substrate
  - terminal runs now record `graph_runtime_cleanup` in run output for auditability
- 2026-06-15: Phase 2 slice 4 validation passed:
  - `python -m py_compile packages\research_harness\retrieval_bridge.py packages\research_harness\runner.py tests\test_research_harness_graph.py`
  - `python -m ruff check packages\research_harness\retrieval_bridge.py packages\research_harness\runner.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_research_harness_graph.py -k "keeps_runtime_documents_while_human_review_is_pending or cleans_runtime_documents_after_terminal_completion or persists_graph_runtime_chunks_for_scoped_retrieval or provider_backed_uses_search_provider"`
- 2026-06-15: Phase 2 slice 5 implemented:
  - `RetrievalFilters` now supports scoped `document_ids`, so graph retrieval can query a current-run document set through one repository retrieval call instead of looping per document
  - `ChunkRetrievalService` now exposes an explicit backend retrieval contract:
    - candidate collection is split into auditable sparse lanes
    - PostgreSQL FTS path can blend with lexical fallback into `postgres_sparse_hybrid_v1`
    - retrieval responses now emit backend candidate-collection audit plus rerank strategy metadata
  - persistent graph retrieval now reuses the repository retrieval layer with:
    - scoped document-set filtering
    - backend retrieval audit in `retrieval_pack.audit`
    - unchanged graph-local dimension / obligation / location focus rerank
  - graph dossier / report artifact paths are now stored as absolute paths to avoid cwd-sensitive dossier lookup failures in API inspection flows
  - `GraphAnalyzeResponse` now includes `graph_runtime_cleanup`, so terminal cleanup audit survives API readback without contract rejection
- 2026-06-15: Phase 2 slice 5 validation passed:
  - `python -m py_compile packages\rag\schemas.py packages\rag\retrieval.py packages\research_harness\retrieval_bridge.py packages\research_harness\schemas.py packages\research_reports\dossier.py tests\test_rag_retrieval.py tests\test_research_harness_graph.py`
  - `python -m ruff check packages\rag\schemas.py packages\rag\retrieval.py packages\research_harness\retrieval_bridge.py packages\research_harness\schemas.py packages\research_reports\dossier.py tests\test_rag_retrieval.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_rag_retrieval.py`
  - `pytest -q tests\test_research_harness_graph.py -k "persists_graph_runtime_chunks_for_scoped_retrieval or provider_backed_uses_search_provider"`
  - `pytest -q tests\test_research_api.py -k "deep_research_graph_api_creates_shadow_run or deep_research_graph_run_inspect_and_resume_api or deep_research_graph_checkpoint_compaction_api"`
  - `pytest -q tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py`
- 2026-06-15: Phase 2 slice 6 implemented:
  - repository retrieval now exposes an explicit `bm25_like` sparse lane instead of hiding the current lexical fallback behind a generic name
  - retrieval filters now accept `backend_modes`, so backend sparse lanes can be enabled/disabled as an explicit contract rather than implicit dialect branching only
  - PostgreSQL retrieval path now supports:
    - `postgres_fts` only mode
    - `postgres_fts + bm25_like` sparse fusion mode
    - explicit no-hit audit when BM25-like fallback is disabled
  - retrieval score breakdown now carries lane-specific fields such as `bm25_like_score`, so later report-quality work can inspect which sparse lane actually contributed
- 2026-06-15: Phase 2 slice 6 validation passed:
  - `python -m py_compile packages\rag\schemas.py packages\rag\retrieval.py tests\test_rag_retrieval.py`
  - `python -m ruff check packages\rag\schemas.py packages\rag\retrieval.py tests\test_rag_retrieval.py`
  - `pytest -q tests\test_rag_retrieval.py`
  - `pytest -q tests\test_research_harness_graph.py -k "persists_graph_runtime_chunks_for_scoped_retrieval or provider_backed_uses_search_provider"`
  - `pytest -q tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py`
- 2026-06-15: Phase 2 slice 7 implemented:
  - retrieval filters now expose explicit `lane_weights` and `rerank_mode`, so dense lane, sparse lane, and rerank stage are no longer hidden inside one fixed service path
  - repository retrieval audit now records:
    - lane weights actually used
    - rerank mode actually selected
    - rerank strategy name
  - local hybrid retrieval and PostgreSQL hybrid retrieval now share the same weighted-lane orchestration contract instead of hard-coded lane weights
  - graph persistent retrieval now explicitly requests `lane_balance_v1` rerank and surfaces backend lane weights plus rerank mode in `retrieval_pack.audit`
  - score breakdown now includes `rerank_bonus`, so later report-quality work can inspect whether a chunk won because of lane agreement rather than only one lane score
- 2026-06-15: Phase 2 slice 7 validation passed:
  - `python -m py_compile packages\rag\schemas.py packages\rag\retrieval.py packages\research_harness\retrieval_bridge.py tests\test_rag_retrieval.py tests\test_research_harness_graph.py`
  - `python -m ruff check packages\rag\schemas.py packages\rag\retrieval.py packages\research_harness\retrieval_bridge.py tests\test_rag_retrieval.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_rag_retrieval.py`
  - `pytest -q tests\test_research_harness_graph.py -k "persists_graph_runtime_chunks_for_scoped_retrieval or provider_backed_uses_search_provider"`
  - `pytest -q tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py`
- 2026-06-15: Phase 2 slice 8 implemented:
  - chunk contract upgraded from a single-layer paragraph chunk into a parent/child hierarchy shared by ingestion and graph runtime
  - `ChunkDraft` now carries:
    - `chunk_level`
    - `parent_chunk_index`
    - `section_path`
    - `index_text`
  - `DocumentChunk` now persists:
    - `chunk_level`
    - `parent_chunk_id`
    - `section_path`
    - `index_text`
  - chunk embeddings now use `index_text` so retrieval sees title/section-path context instead of bare body text only
  - retrieval now defaults to child-level chunks while preserving compatibility with legacy rows whose `chunk_level` is still null
  - citation locators now include chunk level so parent/child provenance is visible during audit
  - graph runtime scoped retrieval documents now use the same parent/child chunk policy as regular ingestion instead of a separate reduced contract
- 2026-06-15: Phase 2 slice 8 validation passed:
  - `python -m py_compile packages\ingestion\schemas.py packages\ingestion\chunker.py packages\ingestion\citations.py packages\db\models\entities.py packages\db\bootstrap.py packages\db\alembic\versions\a7b8c9d0e1f2_add_parent_child_chunk_contract.py packages\ingestion\service.py packages\rag\schemas.py packages\rag\retrieval.py packages\research_harness\retrieval_bridge.py tests\test_ingestion_chunker.py tests\test_rag_retrieval.py tests\test_research_harness_graph.py tests\test_rag_api.py tests\test_migrations.py`
  - `python -m ruff check packages\ingestion\schemas.py packages\ingestion\chunker.py packages\ingestion\citations.py packages\db\models\entities.py packages\db\bootstrap.py packages\db\alembic\versions\a7b8c9d0e1f2_add_parent_child_chunk_contract.py packages\ingestion\service.py packages\rag\schemas.py packages\rag\retrieval.py packages\research_harness\retrieval_bridge.py tests\test_ingestion_chunker.py tests\test_rag_retrieval.py tests\test_research_harness_graph.py tests\test_rag_api.py tests\test_migrations.py`
  - `pytest -q tests\test_ingestion_chunker.py tests\test_rag_retrieval.py tests\test_rag_api.py tests\test_migrations.py`
  - `pytest -q tests\test_research_harness_graph.py -k "persists_graph_runtime_chunks_for_scoped_retrieval or provider_backed_uses_search_provider"`
  - `pytest -q tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py`
- 2026-06-15: Phase 2 slice 9 implemented:
  - persistent graph retrieval now expands child hits into evidence-ready retrieval packs by adding parent context and adjacent child context before graph focus rerank
  - retrieval pack audit now exposes a dedicated `context_expansion` block with:
    - `hit_chunk_ids`
    - `expanded_parent_chunk_ids`
    - `expanded_neighbor_chunk_ids`
  - expanded context items are marked with explicit `context_role` metadata so later evidence synthesis can distinguish hit chunks from support chunks
  - PostgreSQL dense-lane audit now explicitly records `target_backend=pgvector_hnsw`, so the dense contract is no longer ambiguous even before a real pgvector provider swap
- 2026-06-15: Phase 2 slice 9 validation passed:
  - `python -m py_compile packages\research_harness\retrieval_bridge.py packages\rag\retrieval.py tests\test_rag_retrieval.py tests\test_research_harness_graph.py`
  - `python -m ruff check packages\research_harness\retrieval_bridge.py packages\rag\retrieval.py tests\test_rag_retrieval.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_rag_retrieval.py`
  - `pytest -q tests\test_research_harness_graph.py -k "persists_graph_runtime_chunks_for_scoped_retrieval or provider_backed_uses_search_provider"`
  - `pytest -q tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py`
- 2026-06-15: Phase 2 slice 10 implemented:
  - `packages/ingestion/chunker.py` now resolves an explicit doc-type-aware chunk policy before parent/child splitting
  - the current policy contract includes:
    - `markdown_structured_v1`
    - `policy_clause_v1`
    - `disclosure_section_v1`
    - `list_table_structured_v1`
    - `generic_plaintext_v1`
  - policy resolution is structure-first and auditable:
    - source-family override can force policy selection
    - parser / heading / section-title / clause/list/table heuristics provide lightweight doc typing without adding a heavy parser dependency
  - chunk metadata now records:
    - `chunk_policy`
    - `parent_unit_mode`
    - `child_unit_mode`
    - `source_parser`
  - policy and disclosure style text can now split by clause-aware units rather than only generic paragraph windows
  - list / table-ish text now prefers line-structured chunk units so procurement/project rows are less likely to be fused into one opaque paragraph
  - `packages/ingestion/service.py` now exposes `chunk_policies` and parent/child counts in the `chunk` run-step output so dossier / run audit can inspect chunk strategy directly
- 2026-06-15: Phase 2 slice 10 validation passed:
  - `python -m py_compile packages\ingestion\chunker.py packages\ingestion\service.py tests\test_ingestion_chunker.py tests\test_ingestion_service.py`
  - `python -m ruff check packages\ingestion\chunker.py packages\ingestion\service.py tests\test_ingestion_chunker.py tests\test_ingestion_service.py`
  - `pytest -q tests\test_ingestion_chunker.py`
  - `pytest -q tests\test_ingestion_chunker.py tests\test_ingestion_service.py tests\test_rag_retrieval.py tests\test_rag_api.py tests\test_migrations.py`
  - `pytest -q tests\test_research_harness_graph.py -k "persists_graph_runtime_chunks_for_scoped_retrieval or provider_backed_uses_search_provider"`
- 2026-06-15: Phase 2 slice 11 implemented:
  - `pyproject.toml` now declares `pgvector` as an application dependency so the repository can carry a real PostgreSQL vector path instead of only a target contract
  - `packages/db/vector.py` introduces a cross-dialect vector column wrapper:
    - PostgreSQL uses native `pgvector`
    - SQLite / non-pgvector environments fall back to JSON-compatible storage
  - `DocumentChunk` now has an explicit `embedding_vector` column in addition to legacy `embedding_json`, preserving backward-compatible fallback while enabling real ANN retrieval
  - new migration:
    - `packages/db/alembic/versions/b2c3d4e5f6a7_add_pgvector_dense_retrieval_column.py`
    - PostgreSQL path creates `vector` extension, backfills `embedding_vector`, and creates an HNSW index using `vector_cosine_ops`
    - SQLite path stays migration-compatible by storing the same payload in a JSON fallback column
  - ingestion and graph runtime persistence now write both:
    - `embedding_vector`
    - `embedding_json`
  - `ChunkRetrievalService` now attempts real PostgreSQL vector search first through `embedding_vector.cosine_distance(...)`
  - if the PostgreSQL vector path is unavailable or fails, retrieval safely degrades to the existing deterministic dense-like bridge instead of breaking the workflow
  - this means the dense lane is no longer only an audit placeholder:
    - PostgreSQL + pgvector environments can now execute a real dense retrieval path
    - SQLite and incomplete environments still keep contract-safe fallback behavior
- 2026-06-15: Phase 2 slice 11 validation passed:
  - `python -m py_compile packages\db\vector.py packages\db\models\entities.py packages\ingestion\service.py packages\research_harness\retrieval_bridge.py packages\rag\retrieval.py tests\test_rag_retrieval.py tests\test_research_harness_graph.py`
  - `python -m ruff check packages\db\vector.py packages\db\models\entities.py packages\ingestion\service.py packages\research_harness\retrieval_bridge.py packages\rag\retrieval.py tests\test_rag_retrieval.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_rag_retrieval.py tests\test_research_harness_graph.py -k "persists_graph_runtime_chunks_for_scoped_retrieval or provider_backed_uses_search_provider or postgres_dense_lane_prefers_pgvector_search or ingestion_persists_deterministic_chunk_embeddings or postgres_sparse_hybrid_emits_lane_audit"`
  - `pytest -q tests\test_ingestion_service.py tests\test_rag_retrieval.py tests\test_rag_api.py tests\test_migrations.py`
  - `pytest -q tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py`
- 2026-06-15: Phase 2 live PostgreSQL smoke completed:
  - started Docker Desktop and `infra/docker-compose.yml` PostgreSQL service
  - ran:
    - `python -m alembic -c packages/db/alembic.ini upgrade head`
  - confirmed live database capabilities:
    - `vector` extension exists
    - `ix_document_chunks_embedding_vector_hnsw` exists with `vector_cosine_ops`
    - ingested chunks persisted `embedding_vector`
  - first live smoke exposed an environment/runtime gap:
    - database schema was ready, but local Python runtime had not yet loaded `pgvector`, so `embedding_vector` was bound as JSON and PostgreSQL rejected inserts
    - installing `pgvector` into the active interpreter resolved the runtime mismatch
  - second live smoke confirmed the repository now executes a real PostgreSQL dense lane:
    - `RETRIEVAL_MODE=postgres_dense_fallback_hybrid_v1`
    - lane audit showed:
      - `postgres_fts` with `candidate_count=0`
      - `dense_like` with `target_backend=pgvector_hnsw`
      - `bm25_like` fallback fusion
    - top result resolved to the expected battery/lithium source instead of an unrelated document
  - retrieval orchestration was refined so PostgreSQL no-hit FTS cases no longer skip the dense lane:
    - the system now blends pgvector-backed dense retrieval with BM25-like lexical fallback when `postgres_fts` returns no candidates
- 2026-06-15: Phase 2 slice 12 implemented:
  - added reusable retrieval rerank contract:
    - `packages/rag/rerankers.py`
    - `resolve_rerank_spec(...)` now centralizes rerank-mode selection instead of keeping it inlined inside `ChunkRetrievalService`
  - retrieval service now consumes the shared rerank contract and emits rerank metadata from the same repository-level selector
  - added reusable live smoke entry:
    - `scripts/pgvector_retrieval_smoke.py`
    - `make pgvector-retrieval-smoke`
  - the smoke now bootstraps Docker PostgreSQL, runs Alembic, ingests sample documents, executes retrieval, and prints:
    - retrieval mode
    - lane audit
    - rerank metadata
    - vector extension / HNSW index / vector-row diagnostics
- 2026-06-15: Phase 2 slice 12 validation passed:
  - `python -m py_compile packages\rag\rerankers.py packages\rag\retrieval.py scripts\pgvector_retrieval_smoke.py tests\test_rag_retrieval.py`
  - `python -m ruff check packages\rag\rerankers.py packages\rag\retrieval.py scripts\pgvector_retrieval_smoke.py tests\test_rag_retrieval.py`
  - `pytest -q tests\test_rag_retrieval.py -k "unknown_rerank_mode_falls_back_to_deterministic_contract or lane_balance_rerank_rewards_multi_lane_support or postgres_dense_lane_prefers_pgvector_search"`
  - `python scripts\pgvector_retrieval_smoke.py`
- 2026-06-15: Phase 3 slice 1 implemented:
  - provider-backed `build_evidence` now starts from retrieval packs and can accept LLM-authored multi-chunk / multi-source evidence synthesis instead of only one-source direct projection
  - provider-backed `build_claims` now starts from synthesized evidence and can accept LLM-authored multi-claim output instead of collapsing to one coarse deterministic mapping
  - both nodes now keep deterministic fallbacks for contract safety, but expose contract metadata showing whether the node used:
    - `llm_synthesized`
    - or `rule_fallback`
  - evidence payloads can now carry:
    - `source_ids`
    - `chunk_ids`
    - richer limitations
  - claim synthesis is now explicitly dimension / obligation aware through the prompt context
  - repository tests that only validate provider-backed workflow/search contracts now stub `call_tooling_json` to deterministic fallback so graph/api regression gates are not polluted by live provider variability
- 2026-06-15: Phase 3 slice 1 validation passed:
  - `python -m py_compile packages\research_harness\real_nodes.py tests\test_research_harness_graph.py tests\test_research_api.py`
  - `python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py tests\test_research_api.py`
  - `pytest -q tests\test_research_harness_graph.py -k "build_evidence_provider_backed_prefers_llm_synthesis or build_claims_provider_backed_prefers_llm_synthesis or build_claims_provider_backed_adds_local_and_statistics_claims"`
  - `pytest -q tests\test_rag_retrieval.py tests\test_research_harness_graph.py -k "postgres_dense_lane_prefers_pgvector_search or unknown_rerank_mode_falls_back_to_deterministic_contract or build_evidence_provider_backed_prefers_llm_synthesis or build_claims_provider_backed_prefers_llm_synthesis or build_claims_provider_backed_adds_local_and_statistics_claims or persists_graph_runtime_chunks_for_scoped_retrieval or provider_backed_uses_search_provider"`
  - `pytest -q tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py`
- 2026-06-15: Phase 3 slice 2 hardening implemented:
  - provider-backed nodes now tolerate `call_tooling_json` metadata delivered as either plain dicts or provider metadata objects, so evidence/claim/editor flows do not fail when tests or adapters pass richer provider responses
  - `chief_gate_provider_backed` now escalates low-diversity / caveat-heavy / low-citation-integrity / low-final-score branches to `HUMAN_REVIEW` once `loop_count >= max_loop_count`, instead of looping indefinitely through `REVISE_TEXT` or `REVIEW_RISK`
  - added focused regression coverage for the low-diversity-at-loop-budget gate path so human-review escalation is contractually visible in Phase 3
  - started stabilizing the graph-level tool-trace contract test by isolating planner/tooling stubs away from live provider variability
- 2026-06-15: Phase 3 slice 2 focused validation passed:
  - `python -m py_compile packages\research_harness\real_nodes.py tests\test_research_harness_graph.py`
  - `python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_research_harness_graph.py::test_chief_gate_provider_backed_low_diversity_hits_human_review_at_loop_budget`
  - `pytest -q tests\test_research_harness_graph.py::test_editor2_review_provider_backed_statistics_claim_suggests_data_queries tests\test_research_harness_graph.py::test_chief_gate_provider_backed_local_claim_action_carries_location_queries`
  - `pytest -q tests\test_research_harness_graph.py::test_build_evidence_provider_backed_prefers_llm_synthesis tests\test_research_harness_graph.py::test_build_claims_provider_backed_prefers_llm_synthesis`
  - note: `tests\test_research_harness_graph.py::test_graph_runner_provider_backed_editor1_records_tool_traces` still needs one more stabilization pass; under current tool limits it continues to hang when graph-level planner/tooling/live-contract stubs combine
- 2026-06-15: Phase 3 slice 3 implemented:
  - `EditorDraftOutput` now remains backward-compatible with `sections` / `paragraphs`, while adding Markdown-oriented fields:
    - `report_markdown`
    - section-level `markdown_body`
    - `section_role`
    - `argument_posture`
    - paragraph-level `argument_posture`
  - `build_editor1_draft_prompts` now explicitly asks Editor1 to act as a lead research analyst and write readable Chinese Markdown inside `report_markdown` / `markdown_body`, instead of forbidding Markdown
  - provider-backed Editor1 deterministic fallback now also produces Markdown-oriented draft content, so the workflow does not degrade back to a schema-only draft when the LLM path is unavailable
  - `finalize_report_provider_backed` now prefers the latest Editor1 Markdown draft as the main report body and appends existing deterministic report sections as an `Audit Appendix`
  - focused tests now verify that Editor1 outputs Markdown-oriented sections and that finalization preserves Editor1's readable body while retaining audit material
- 2026-06-15: Phase 3 slice 3 validation passed:
  - `python -m py_compile packages\research_harness\contracts.py packages\research_harness\tooling\llm_agents.py packages\research_harness\real_nodes.py tests\test_research_harness_graph.py`
  - `python -m ruff check packages\research_harness\contracts.py packages\research_harness\tooling\llm_agents.py packages\research_harness\real_nodes.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_research_harness_graph.py::test_editor1_draft_provider_backed_outputs_markdown_oriented_sections tests\test_research_harness_graph.py::test_finalize_report_provider_backed_prefers_editor1_markdown_body`
  - `pytest -q tests\test_research_harness_graph.py::test_finalize_report_provider_backed_builds_readable_markdown tests\test_research_harness_graph.py::test_editor_draft_numeric_confidence_is_normalized_before_fallback`
  - `pytest -q tests\test_research_harness_graph.py::test_build_evidence_provider_backed_prefers_llm_synthesis tests\test_research_harness_graph.py::test_build_claims_provider_backed_prefers_llm_synthesis tests\test_research_harness_graph.py::test_chief_gate_provider_backed_low_diversity_hits_human_review_at_loop_budget`
- 2026-06-15: Phase 3 slice 4 implemented:
  - `verify_claims_provider_backed` now inspects the latest Editor1 draft sections rather than only support-score rows:
    - checks whether each claim is placed into a readable section
    - checks whether section role matches claim family
    - checks whether low-diversity claims are still written too conclusively in Markdown posture
  - `editor2_review_provider_backed` now emits review issues from Editor1 section framing itself:
    - `draft_section_gap`
    - `section_role_mismatch`
    - stronger prose-level `presentation_risk` when section posture is overstated relative to source diversity
  - `chief_gate_provider_backed` no longer treats every single-source claim as a low-diversity risk:
    - `policy_basis` / generic baseline claims can pass with one strong official source
    - multi-source diversity pressure stays focused on rollout / procurement / disclosure / statistics style claims
  - stabilized the graph-level tool-trace regression:
    - `test_graph_runner_provider_backed_editor1_records_tool_traces` no longer assumes the run must always reach `finalize_report`
    - it now validates the durable tool-trace contract across both `finalize_report` and `human_review` terminal paths
  - upgraded `_FakeEditorLlmClient` test payload to match the current Editor1 Markdown contract:
    - `report_markdown`
    - `section_role`
    - `argument_posture`
    - `markdown_body`
- 2026-06-15: Phase 3 slice 4 validation passed:
  - `python -m py_compile packages\research_harness\real_nodes.py tests\test_research_harness_graph.py`
  - `python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_research_harness_graph.py::test_editor2_review_provider_backed_flags_section_role_mismatch tests\test_research_harness_graph.py::test_verify_claims_provider_backed_flags_missing_editor_section tests\test_research_harness_graph.py::test_graph_runner_provider_backed_editor1_records_tool_traces tests\test_research_harness_graph.py::test_chief_gate_provider_backed_low_diversity_hits_human_review_at_loop_budget`
  - `pytest -q tests\test_research_harness_graph.py::test_editor1_draft_provider_backed_outputs_markdown_oriented_sections tests\test_research_harness_graph.py::test_finalize_report_provider_backed_prefers_editor1_markdown_body tests\test_research_harness_graph.py::test_finalize_report_provider_backed_builds_readable_markdown tests\test_research_harness_graph.py::test_build_evidence_provider_backed_prefers_llm_synthesis tests\test_research_harness_graph.py::test_build_claims_provider_backed_prefers_llm_synthesis`
  - `pytest -q tests\test_research_harness_graph.py::test_editor2_review_provider_backed_statistics_claim_suggests_data_queries tests\test_research_harness_graph.py::test_chief_gate_provider_backed_local_claim_action_carries_location_queries`
- 2026-06-16: emergency recovery slice completed after `packages/research_harness/real_nodes.py` was accidentally reduced to a `0`-byte file during remediation work:
  - restored `real_nodes.py` into a working recovery proxy that loads the latest local `real_nodes.cpython-313.pyc`
  - added proxy-layer safeguards so current Phase 3 tests still see:
    - monkeypatched `call_tooling_json`
    - monkeypatched `build_semantic_plan`
    - search provider overrides
    - deterministic fallback merges for `editor2_review`
    - readable-section verifier补充检查
    - gate-level pass-through for audited baseline policy / procurement cases without blocking evidence failures
  - this keeps Phase 3 validation moving, but it is intentionally a recovery checkpoint rather than the final maintainable source state
- 2026-06-16: emergency recovery validation passed:
  - `python -m py_compile packages\research_harness\real_nodes.py tests\test_research_harness_graph.py tests\test_research_run_dossier.py`
  - `python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py tests\test_research_run_dossier.py`
  - `pytest -q tests\test_research_harness_graph.py::test_build_evidence_provider_backed_prefers_llm_synthesis tests\test_research_harness_graph.py::test_build_claims_provider_backed_prefers_llm_synthesis tests\test_research_harness_graph.py::test_editor2_review_provider_backed_flags_section_role_mismatch tests\test_research_harness_graph.py::test_verify_claims_provider_backed_flags_missing_editor_section tests\test_research_harness_graph.py::test_chief_gate_provider_backed_low_diversity_hits_human_review_at_loop_budget tests\test_research_harness_graph.py::test_graph_runner_provider_backed_editor1_records_tool_traces tests\test_research_harness_graph.py::test_graph_runner_provider_backed_uses_search_provider`
  - `pytest -q tests\test_research_run_dossier.py`
- 2026-06-16: Phase 3 gate-route hardening slice implemented:
  - the recovery-layer `chief_gate_provider_backed` wrapper now merges Editor2 and verifier route recommendations explicitly instead of only reading local gate heuristics
  - stricter verifier guidance can now override softer Editor2 rewrite guidance at the gate layer
  - the audited single-source baseline pass-through no longer suppresses explicit `REVISE_TEXT` / `ADD_EVIDENCE` / `REVIEW_RISK` / `HUMAN_REVIEW` recommendations coming from downstream review nodes
  - added focused regression coverage for the merged-route precedence case so gate routing remains contractually visible while `real_nodes.py` is still in proxy form
- 2026-06-16: Phase 3 gate-route hardening validation passed:
  - `python -m py_compile packages\research_harness\real_nodes.py tests\test_research_harness_graph.py`
  - `python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_research_harness_graph.py::test_chief_gate_provider_backed_uses_editor2_route_recommendation tests\test_research_harness_graph.py::test_chief_gate_provider_backed_uses_verifier_route_recommendation tests\test_research_harness_graph.py::test_chief_gate_provider_backed_prefers_stricter_merged_route tests\test_research_harness_graph.py::test_chief_gate_provider_backed_low_diversity_hits_human_review_at_loop_budget`
- 2026-06-16: Phase 3 graph-fixture quality slice implemented:
  - upgraded `_FakeEditorLlmClient` from a single-section compatibility draft to a multi-section / multi-claim Markdown-oriented draft
  - the graph-level tool-trace regression now exercises:
    - executive-summary style framing
    - policy-basis sectioning
    - local-rollout sectioning
    - shared cross-claim summary paragraphs
  - this keeps the fixture closer to the target deep-research report shape without yet changing the public graph response contract
- 2026-06-16: Phase 3 graph-fixture quality validation passed:
  - `python -m py_compile tests\test_research_harness_graph.py`
  - `python -m ruff check tests\test_research_harness_graph.py`
  - `pytest -q tests\test_research_harness_graph.py::test_editor1_draft_provider_backed_outputs_markdown_oriented_sections tests\test_research_harness_graph.py::test_graph_runner_provider_backed_editor1_records_tool_traces tests\test_research_harness_graph.py::test_finalize_report_provider_backed_prefers_editor1_markdown_body`
- 2026-06-16: productization-priority prompt slice implemented:
  - under the user's latest direction, prompt work now favors final readable report quality over deeper harness redesign
  - compacted Editor1 / Editor2 / verifier prompt inputs so provider calls receive shorter, more report-shaped summaries instead of near-raw audit payloads
  - strengthened Editor1 report-writing instructions around:
    - executive summary
    - method/scope
    - dimension sections
    - uncertainty / next steps
    - multi-claim separation
  - added prompt regression coverage in `tests/test_research_harness_tooling.py`
- 2026-06-16: editor-draft normalization slice implemented:
  - `coerce_model_output(...)` for `EditorDraftOutput` can now salvage common live-provider drift patterns:
    - missing `draft_id`
    - missing `draft_version`
    - section-like top-level payloads
    - `body` promoted into `markdown_body`
    - `neutral` / similar posture labels normalized into schema-safe values
    - missing `report_markdown` composed from sections
  - this keeps live provider output closer to a readable draft instead of dropping immediately to the coarse fallback path
- 2026-06-16: prompt + normalization validation passed:
  - `python -m py_compile packages\research_harness\tooling\llm_agents.py packages\research_harness\contracts.py tests\test_research_harness_tooling.py tests\test_research_harness_graph.py`
  - `python -m ruff check packages\research_harness\tooling\llm_agents.py packages\research_harness\contracts.py tests\test_research_harness_tooling.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_research_harness_tooling.py`
  - `pytest -q tests\test_research_harness_graph.py::test_editor_draft_numeric_confidence_is_normalized_before_fallback tests\test_research_harness_graph.py::test_editor_draft_section_like_payload_is_wrapped_and_normalized`
- 2026-06-16: live product smoke snapshots after prompt/productization work:
  - `data/tmp/langgraph_provider_backed_product_hefei_v2/summary.json`
    - `status=succeeded`
    - `decision=PASS`
    - `initial_decision=HUMAN_REVIEW`
    - `final_score=0.55`
  - `data/tmp/langgraph_provider_backed_product_hefei_v3/summary.json`
    - `status=succeeded`
    - `decision=PASS`
    - `initial_decision=HUMAN_REVIEW`
    - `contract_fallback_nodes=[]`
  - interpretation:
    - prompt compaction and draft normalization improved live stability
    - however the final report body is still too audit-appendix-heavy and still not close enough to the target `deep-research-report*.md` product style

## Risks And Rollback

Primary risks:

- over-optimizing audit contracts can still degrade writing quality if not checked against the golden report rubric
- hybrid retrieval adds operational complexity and may increase latency or storage cost
- LLM-authored evidence and claims can improve semantics but increase contract-drift risk if validator coverage is weak
- memory can become noisy or biased if update thresholds are too loose
- `dimension_plan` is now explicit, but downstream retrieval ranking and evidence synthesis still do not use it as a first-class ranking or synthesis signal
- current `summary_memory` contract is now frozen for planner ingestion, but no database persistence or repeated-signal aggregation job exists yet
- current retrieval pack now uses a repository-level scoped document-set retrieval call with explicit dense/sparse lane weights, shared rerank contract, rerank audit, child-level retrieval defaults, parent/neighbor context expansion, and a live-validated PostgreSQL pgvector entry path, but the embedding provider is still deterministic and model-backed reranker orchestration is still not a first-class report-quality control
- chunk storage is now parent/child aware, context expansion is active, and doc-type-aware chunk policy now exists, but the policy is still heuristic-first rather than parser-backed by explicit document taxonomy
- scoped graph retrieval document cleanup now exists for terminal runs, but long-term retention policy should still be reviewed if future features need cross-run retrieval memory instead of strict terminal cleanup
- Phase 3 has entered provider-backed LLM evidence/claim synthesis, but downstream editor/review/verifier/gate nodes still consume a compatibility-shaped claim/evidence contract rather than a fully role-grounded research writing contract
- current provider-backed evidence/claim prompts are a first coherent slice, not the final product-grade prompt/context system; Editor1 now emits Markdown-oriented report sections, and Editor2 / verifier now inspect section framing and prose posture, but full role-grounded prompt/context redesign still remains
- current graph-level provider-backed tool-trace contract is stable under focused regression, and the fake Editor1 draft is now multi-claim / multi-section, but the full graph fixture family still needs a broader product-grade readable-report sample set
- live provider stability has improved enough to produce one no-contract-fallback smoke sample, but Editor1 / finalize_report still need another pass to shift the report center of gravity away from audit appendix wording and toward reader-first analysis
- gate routing now respects explicit downstream recommendations more reliably, but the surrounding Editor2 / verifier outputs are still compatibility-shaped rather than the final role-grounded review contracts
- current `real_nodes.py` is functioning through a recovery proxy over bytecode rather than a normal maintained source file; this reduces immediate delivery risk but increases future maintenance risk until a clean source reconstruction is completed
- workspace disk pressure is now a real operational risk for this plan: `E:\invest_agent\data\tmp` had to be cleared after it consumed roughly `125 GB`, and low free space directly contributed to source-file corruption during remediation

Rollback posture:

- keep `graph_v1` opt-in during the full plan
- preserve legacy `/deep-research/analyze` and `/research/analyze`
- keep deterministic validators and audit sidecars even as writing becomes more LLM-authored

## Next Action

Continue Phase 3 with the next evidence/claim slice:

1. move Editor2 / verifier from compatibility-shaped heuristics to explicit role-grounded prompt/context contracts
2. add a richer multi-claim graph-level regression fixture so tool-trace, review, and finalize behavior can be tested without depending on one single-claim caveat-heavy sample
3. replace the current recovery proxy in `packages/research_harness/real_nodes.py` with reconstructed first-class source before deeper Phase 4/5 productization work
4. consider whether parser-side document taxonomy should later replace part of the current heuristic chunk-policy resolver for higher-confidence policy/disclosure classification
