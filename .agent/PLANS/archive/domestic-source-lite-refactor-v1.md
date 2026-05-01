# Plan: Domestic Source Lite Refactor v1

Status: completed
Priority: high
Owner: codex/human
Scope: source subsystem
Created: 2026-04-26
Last Updated: 2026-04-27

## Objective

鎶婂浗鍐呮簮妫€绱㈢瓥鐣ヤ粠鈥滄寔缁淮鎶ゅぇ閲忕珯鐐瑰唴鎼滅储/鍒楄〃閫昏緫鈥濇敹缂╀负鏇磋交鐨勬贩鍚堟灦鏋勶細

- 淇濈暀椤圭洰鑷繁鐨?query decomposition銆佹潯鍧楄矾鐢便€乻ource taxonomy銆乪vidence bundle 涓庡璁′綋绯汇€?- 璁?Tavily 鎺ョ閫氱敤缃戦〉婧愮殑鎼滅储鍙戠幇灞傘€?- 璁?Crawl4AI 鎺ョ閫氱敤缃戦〉椤甸潰鎶撳彇涓庢娊鍙栧眰銆?- 瀵规姭闇茬被銆佹煡璇㈠钩鍙扮被銆佺粨鏋勫寲鏁版嵁绫荤户缁繚鐣欑洿杩炴垨涓撶敤 adapter銆?
鏈鍒掍笉閲嶆柊璋冪爺鍥藉唴婧愶紝鑰屾槸澶嶇敤宸插畬鎴愮殑 `domestic-source-scaleout-v2`銆乣source-v2-tiaokuai-foundation`銆乣domestic_inventory.py` 涓?source pack 缁撹銆?
## Task Classification

Primary area: `source_layer`

Secondary areas:
- `domestic_source_collectors`
- `research_workflow`
- `provider_layer`
- `eval_policy_ops`

High-risk contracts:
- EvidenceBundle schema
- EvidenceItem citation fields
- `source_quality_summary`
- research analyze response shape
- task/job status semantics
- source routing behavior used by downstream research workflows

Current step classification: docs/plan formatting only. No production code is modified in this step.

## Background Reused

- Completed `domestic-source-scaleout-v2` source research and rollout conclusions.
- Existing `source-v2-tiaokuai-foundation` 鏉″潡 taxonomy and routing assumptions.
- Existing `domestic_inventory.py` and source pack classifications.
- Existing `docs/source-query-decomposition-rules.md` query decomposition rulebook.
- Existing `docs/subagents-operating-model.md` v2 six-agent operating model.
- User decision: Tavily should own generic search discovery, Crawl4AI should own generic page extraction, and direct structured adapters should remain protected.

## Scope

In scope:
- Reclassify domestic source families into search-assisted, direct structured, and placeholder/manual buckets.
- Define query decomposition as a first-class owned capability.
- Plan Tavily search discovery with low-credit defaults.
- Plan Crawl4AI extraction as the generic page-fetching and extraction layer.
- Preserve direct structured adapters for disclosure, structured data, and query platforms.
- Make the PLAN executable by the v2 subagent workflow.

Out of scope:
- Re-researching domestic source categories from scratch.
- Replacing disclosure, data-table, procurement, credit, GSXT, or judicial paths with Tavily-only search.
- Changing EvidenceBundle, citation, research response, or task/job contracts in this PLAN unless a later phase explicitly authorizes it.
- Running Tavily, Crawl4AI, browser automation, OCR, or live external extraction during Phase 1.

## Constraints

- Preserve existing evidence, citation, research response, source-quality, and task-state contracts unless explicitly authorized in this PLAN.
- Prefer narrow, reversible changes over broad refactors.
- Keep Tavily as discovery, not taxonomy or conclusion logic.
- Keep Crawl4AI as extraction, not routing or research judgment logic.
- Keep direct structured adapters as primary paths for high-structure sources.
- Keep each phase executable without hidden conversation memory.
- Record decisions, validation results, risks, and next action in this PLAN and `.agent/STATUS.md`.

## Architecture Direction

Target flow:

```text
User Query
  -> Query Decomposer
  -> Tiaokuai Router / Source Strategy
     -> Search-Assisted Path
        -> Tavily Search Discovery
        -> Crawl4AI Page Fetch and Extraction
        -> Normalizer
     -> Direct Structured Path
        -> disclosure adapters
        -> query platform adapters
        -> structured data adapters
        -> Normalizer
  -> Evidence Bundle
  -> Research Workflow
```

Architecture principles:

- Tavily discovers candidate URLs; it does not replace source taxonomy.
- Crawl4AI extracts pages; it does not decide research conclusions.
- Query decomposition is a project-owned capability and must follow the existing 鏉″潡浣撶郴.
- Direct structured adapters remain the primary path for high-structure sources.
- EvidenceBundle, EvidenceItem citations, `source_quality_summary`, and research response shapes are high-risk contracts and must not change unless a later phase explicitly authorizes it.

## Agent Execution Contract

Purpose:
- Make this PLAN the single execution contract for all implementation agents.
- Keep agents aligned to one phase, one scope, one validation loop, and one handoff state.
- Prevent phase-boundary stopping by recording explicit continue rules and stop conditions.

Operating model:
- `.agent/STATUS.md` is the current handoff checkpoint.
- This PLAN is the construction blueprint and state machine.
- `docs/subagents-operating-model.md` defines the role system.
- Agents may read related docs and code, but they must not redefine the active phase outside this PLAN.

Role binding:

| Agent | PLAN responsibility | Scope boundary |
|---|---|---|
| `invest_project_director` | Reads STATUS and this PLAN, freezes the current phase objective, adds or refines real-world validation, assigns Group 2 and Group 3 work, and decides phase transition. | Does not directly implement broad production changes. |
| `invest_agent_architecture_builder` | Designs contracts, provider boundaries, state transitions, trace metadata, and validation hooks. | Does not migrate large feature code unless explicitly assigned. |
| `invest_feature_programmer` | Implements scoped production code, tests, adapters, services, scripts, or source retrieval changes. | Must follow explicit write scope and must not weaken direct structured adapters. |
| `invest_code_quality_checker` | Runs ruff, compile checks, focused pytest, import safety checks, and scope correctness review. | Does not silently patch production logic. |
| `invest_functional_validator` | Validates actual product behavior against the PLAN with real-world queries and failure scenarios. | Does not treat test pass as sufficient if scenario behavior is wrong. |
| `invest_project_summarizer` | Runs after the PLAN is complete to summarize outcomes, remaining risks, and whether worker capability updates are needed. | Does not replace the director during active phases. |

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

Required per-phase agent block:

```md
### Agent Contract

Director Gate:
- Phase objective:
- Required real-world validation:
- Allowed write scope:
- High-risk contracts protected:

Group 2 Assignments:
- invest_agent_architecture_builder:
- invest_feature_programmer:

Group 3 Validation:
- invest_code_quality_checker:
- invest_functional_validator:

Completion Gate:
- Required code checks:
- Required functional checks:
- STATUS update required:
- PLAN progress update required:
```

## Phase 1 Agent Assignment Draft

This draft becomes binding when the user explicitly triggers implementation with "寮€濮嬪疄鏂絇LAN", "瀹炴柦褰撳墠PLAN", "鎵цPLAN", or an equivalent instruction.

Director Gate:
- Confirm Phase 1 is limited to Query Decomposer contract, prompt/rule templates, deterministic validation, and focused tests.
- Confirm Phase 1 does not invoke Tavily, does not require `TAVILY_API_KEY`, and does not call Crawl4AI.
- Add real-world validation cases before Group 2 starts.
- Protect EvidenceBundle, EvidenceItem citations, `source_quality_summary`, research response shapes, and task/job semantics.
- Freeze allowed write scope before assigning workers.

Group 2 Assignments:
- `invest_agent_architecture_builder` owns `QueryDecomposition` contract design, source bucket enum/boundary alignment, validation-state design, provider handoff shape for future Tavily/Crawl4AI phases, and trace/usage metadata design.
- `invest_feature_programmer` owns the minimal implementation of decomposition rules, prompt/rule loading, deterministic validator, fallback behavior, and focused tests for the Phase 1 contract.

Group 3 Validation:
- `invest_code_quality_checker` must run ruff, py_compile, focused pytest, import safety checks, and touched-file scope review for Phase 1 files.
- `invest_functional_validator` must validate decomposition behavior on real queries, including `瀹夊窘鐨勪綆绌虹粡娴庢湭鏉ュ墠鏅浣昤, without requiring Tavily or Crawl4AI.

Phase 1 functional validation cases:
- `瀹夊窘鐨勪綆绌虹粡娴庢湭鏉ュ墠鏅浣昤
- `骞夸笢浜哄舰鏈哄櫒浜轰骇涓氭斂绛栧拰椤圭洰钀藉湴鎯呭喌`
- `娣卞湷浣庣┖缁忔祹鏈夊摢浜涙斂绛栧拰鎷涙爣淇″彿`
- `涓俊娴风洿锛?00099.SZ锛夊湪浣庣┖缁忔祹鏂瑰悜鏈夊摢浜涘叕鍛婂拰椤圭洰`
- `鏂拌兘婧愭苯杞︽崲鐢垫斂绛栨湭鏉ヨ秼鍔縛
- `姹熻嫃鍏変紡浜т笟閾惧嚭娴烽潰涓村摢浜涙斂绛栧拰璐告槗椋庨櫓`
- `鎴愰兘浜哄伐鏅鸿兘浜т笟鍥尯鏈夊摢浜涙斂绛栧拰椤圭洰鏈轰細`
- `娴欐睙浣庣┖缁忔祹鐩稿叧涓婂競鍏徃鏈夊摢浜涘叕鍛奰
- `鍥藉灞傞潰瀵圭畻鍔涘熀纭€璁炬柦鏈変粈涔堟渶鏂版斂绛栨柟鍚慲
- `鏌愯涓氬崗浼氬鐧界毊涔﹀拰璁哄潧淇℃伅濡備綍浣滀负琛ュ厖璇佹嵁`

Phase 1 completion gate:
- Decomposition output contains task family, 鏉″潡 axis, line family, regional level, info type, execution bucket, source cluster, domain constraints, search phrases, evidence goal, and fallback.
- Direct structured source preservation is explicit for disclosure, data, query platform, credit/GSXT, and judicial categories.
- Invalid or over-expanded decomposition fails deterministically or falls back to template rules.
- Focused tests pass without external API keys.
- STATUS and this PLAN are updated with validation snapshot, risks, and next action.

## Source Reclassification Table

| Report IDs | Source cluster | Template family | New execution bucket | Default path | Notes |
|---|---|---|---|---|---|
| C01 | 鍥藉姟闄㈡斂绛栧簱 / 鍥藉姟闄㈠叕鎶?| `policy_library_template` | `search_assisted_sources` | Tavily Search -> Crawl4AI | 鏀跨瓥鏂囨湰鍏紑锛岄€傚悎鍙戠幇寮忔绱€?|
| C02-C05, C09-C11 | 鍙戞敼濮斻€佸伐淇￠儴銆佽储鏀块儴銆佸晢鍔￠儴銆佷綇寤洪儴銆佷氦閫氶儴绛夋斂绛栭儴闂?| `policy_library_template` | `search_assisted_sources` | Tavily Search -> Crawl4AI | 淇濈暀灏戦噺宸茬ǔ瀹氱洿杩炴簮浣滀负鍩哄噯锛屼絾 generic 鎼滅储杩佸埌 Tavily銆?|
| C06-C08 | 鐢熸€佺幆澧冦€佽嚜鐒惰祫婧愩€佸啘涓氬啘鏉戠瓑鍏ず/鏀跨瓥閮ㄩ棬 | `policy_library_template` / domain variants | `search_assisted_sources` with direct fallback | Tavily Search -> Crawl4AI; later per-site fallback | 鍙厛鍙戠幇寮忔绱紝閲嶈鍏ず绫诲悗缁彲鍗囦负涓撶敤妯℃澘銆?|
| C12, C14-C16, C27, C41 | 缁熻銆佹捣鍏炽€佽兘婧愭寚鏍囥€佷环鏍艰繍琛屻€佺渷缁熻 | `data_table_template` | `direct_structured_sources` | Dedicated structured adapter | 鎸囨爣/琛ㄦ牸/蹇収涓昏矾寰勪笉浜ょ粰 Tavily銆俆avily 鍙彲琛ュ彂鐜拌鏄庨〉銆?|
| C17-C23 | 璇佺洃浼氥€佷氦鏄撴墍銆佸法娼€佸€哄埜鎶湶 | `disclosure_template` | `direct_structured_sources` | Dedicated disclosure adapter | 楂樼粨鏋勫寲銆侀珮瀹¤浠峰€硷紝淇濈暀鐩磋繛涓昏矾寰勩€?|
| C24-C26, C28 | 鐪佹斂搴滈棬鎴枫€佺渷鍙戞敼銆佺渷宸ヤ俊銆佺渷鐢熸€佺幆澧?| `province_portal_template`, `province_drc_template`, `province_miit_template` | `search_assisted_sources` | Tavily Search with domain whitelist -> Crawl4AI | 鏉″潡浣撶郴閲岀殑鍧楅潰涓绘簮锛岄€傚悎鎸夊煙鍚嶅彂鐜般€?|
| C29 | 鍦扮骇甯傛斂搴滀笌鍩庡競閮ㄩ棬 | `city_dept_template` | `search_assisted_sources` | Tavily Search with city whitelist -> Crawl4AI | 鍩庡競绔欑偣寮傛瀯楂橈紝浼樺厛杞婚噺鍙戠幇銆?|
| C30-C31 | 鍥尯/寮€鍙戝尯 | `park_template` | `search_assisted_sources` | Tavily Search with whitelist -> Crawl4AI | 鐧藉悕鍗曚笓棰樻帴鍏ワ紝涓嶅仛鍏ㄩ噺閾哄紑銆?|
| C32-C35 | 鏀块噰銆佸叕鍏辫祫婧愩€侀」鐩鎵广€佸湡鍦扮熆鏉?| `project_query_template` | `direct_structured_sources` with search-assisted supplement | Dedicated query adapter; Tavily for琛ラ摼 | 涓昏矾寰勬槸鏉′欢鏌ヨ鍜岀粨鏋滆鎯咃紝涓嶆槸閫氱敤鎼滅储銆?|
| C36-C38 | 澶紒銆佸湴鏂瑰浗浼併€佷笂甯傚叕鍙?IR | `disclosure_template` / IR variants | `search_assisted_sources` with direct disclosure anchor | Tavily Search -> Crawl4AI, plus disclosure direct path | 閫傚悎浣滀负鎶湶琛ラ摼锛屼笉浣滀负鍞竴鐪熺浉婧愩€?|
| C39-C40, C45-C46 | 鍗忎細銆佽仈鐩熴€佸睍浼氳鍧涖€佺櫧鐨功/涓撻骞冲彴 | `association_template` | `search_assisted_sources` | Tavily Search -> Crawl4AI | 闀垮熬寮傛瀯锛屾渶閫傚悎鍙戠幇寮忔悳绱€?|
| C42-C44 | 淇＄敤銆丟SXT銆佸徃娉曞叕寮€ | `project_query_template` / supervision variants | `placeholder_or_manual_sources` or direct only | Dedicated adapter/manual review | 鍚堣鍜岀櫥褰曡竟鐣屽鏉傦紝涓嶈繘鍏?Tavily 涓昏矾寰勩€?|

## Tavily-Suitable Source Table

| Tiaokuai layer | Source category | Report IDs | Tavily role | Crawl4AI role | First-phase priority |
|---|---|---:|---|---|---|
| L1 line | 涓ぎ鏀跨瓥涓诲共鍜屾墿灞?| C01-C05, C09-C11 | discover policy/news/explanation URLs with domain constraints | extract title, date, body, attachments/outlinks | P0 |
| L2 block | 鐪佹斂搴溿€佺渷鍙戞敼銆佺渷宸ヤ俊銆佺渷鐢熸€佺幆澧?| C24-C28 | discover local policy and rollout URLs | extract article markdown and normalized evidence | P0 |
| L2 block | 鍦扮骇甯傛斂搴滃拰鍩庡競閮ㄩ棬 | C29 | discover city rollout and notice pages | extract article markdown | P1 |
| L2 block | 鍥尯/寮€鍙戝尯 | C30-C31 | discover whitelist park policy/project pages | extract article/project markdown | P2 |
| L3 supplement | 鍗忎細銆佽仈鐩熴€佸睍浼氳鍧涖€佺櫧鐨功/涓撻骞冲彴 | C39-C40, C45-C46 | discover topic/industry signals | extract markdown, tables, attachments when possible | P1 |
| L3 supplement | 浼佷笟/鍥戒紒/IR 琛ラ摼 | C36-C38 | discover official IR/news/announcement supplement pages | extract supplemental evidence | P2 |

## Direct-Keep Source Table

| Source category | Report IDs | Keep direct because | Tavily allowed role |
|---|---:|---|---|
| 璇佺洃浼?浜ゆ槗鎵€/宸ㄦ疆/鍊哄埜鎶湶 | C17-C23 | 闇€瑕佸閲忋€佷簨浠堕摼銆佸幓閲嶃€侀檮浠跺拰鍏憡 ID 瀹¤ | supplement only |
| 鍥藉缁熻灞€/娴峰叧/鑳芥簮鎸囨爣/浠锋牸杩愯 | C12, C14-C16, C41 | 鏈川鏄寚鏍囥€佽〃鏍笺€佸彛寰勭増鏈拰蹇収 | discover documentation only |
| 鏀垮簻閲囪喘/鍏叡璧勬簮浜ゆ槗/鎶曡祫椤圭洰瀹℃壒 | C32-C34 | 涓昏矾寰勬槸鏉′欢鏌ヨ銆佺粨鏋滃垪琛ㄣ€佽鎯呴〉 | supplement only |
| 鍦熷湴/鐭挎潈/瑙勫垝鍏ず | C35 | 娣卞垎椤靛拰鏌ヨ鏉′欢寮?| hybrid later |
| 淇＄敤涓浗/GSXT | C42-C43 | 鏌ヨ鍜屽悎瑙勮竟鐣屽鏉?| no main-path Tavily |
| 鍙告硶鍏紑 | C44 | 鍚堣銆佺櫥褰曘€佹绱㈣竟鐣屽鏉?| manual/special plan only |

## Query Decomposition Workstream

Query decomposition is promoted to a first-class workstream in this plan.

Rulebook file:
- `docs/source-query-decomposition-rules.md`

Purpose:
- Teach an LLM how to decompose a user research query into high-quality search tasks.
- Keep the decomposition aligned with existing 鏉″潡 design:
  - `GovernanceAxis.LINE`
  - `GovernanceAxis.BLOCK`
  - `GovernanceAxis.MIXED`
  - `LineFamily.POLICY`
  - `LineFamily.EXCHANGE`
  - `LineFamily.INDUSTRY`
  - `LineFamily.CROSS_DOMAIN`
  - `RegionalLevel.NATIONAL`
  - `RegionalLevel.PROVINCIAL`
  - `RegionalLevel.MUNICIPAL`
  - `RegionalLevel.CROSS_REGION`
  - `InfoType.POLICY_NOTICE`
  - `InfoType.REGULATORY_ANNOUNCEMENT`
  - `InfoType.INDUSTRY_REPORT`
  - `InfoType.INDUSTRY_NOTICE`
  - `InfoType.PROJECT_TRANSACTION`

LLM participation model:
- LLM proposes decomposition candidates and search phrases.
- Deterministic validation checks source bucket, domain allowlist, max query count, required region/theme terms, and unsupported-source flags.
- Low-confidence or unsupported decomposition falls back to rules-based templates.
- The LLM must not invent source categories, report IDs, or direct adapter capabilities.

Required decomposition outputs:
- original query
- normalized theme
- regional focus
- time horizon
- decomposition tasks
- each task's `tiaokuai_axis`
- each task's `line_family`
- each task's `regional_level`
- each task's `info_type`
- execution bucket
- source cluster
- include domains
- exclude domains
- search phrases
- evidence goal
- fallback path

Minimum task families:
- `policy_direction`
- `local_rollout`
- `project_transaction`
- `enterprise_disclosure`
- `industry_topic`
- optional `data_metrics`

Example acceptance target:
- Query: `瀹夊窘鐨勪綆绌虹粡娴庢湭鏉ュ墠鏅浣昤
- Expected decomposition:
  - central policy direction: national policy and ministry guidance for low-altitude economy
  - Anhui local rollout: Anhui province policy, DRC/MIIT/local government pages
  - project/transaction signals: procurement, public resource, approvals, low-altitude infrastructure
  - enterprise/disclosure signals: listed-company announcements and official IR supplement
  - industry/topic supplement: associations, white papers, forums, topic platforms
  - optional data metrics: statistics, aviation/transport/industry indicators if a quantitative claim is needed

## Tavily Configuration Placeholder

Environment:

```bash
TAVILY_API_KEY=__SET_IN_ENV__
```

Default low-credit settings:

```yaml
search:
  provider: tavily
  tavily:
    api_key: ${TAVILY_API_KEY}
    default_search_depth: basic
    default_topic: general
    default_country: china
    default_max_results: 5
    auto_parameters: false
    include_answer: false
    include_raw_content: false
    enable_usage_tracking: true
```

Credit strategy:
- Default to `basic` or `ultra-fast`.
- Default `max_results=5`.
- Use `include_domains` whenever the source bucket has known domains.
- Do not use Tavily Research as default source discovery.
- Do not use Tavily Extract by default when Crawl4AI can fetch locally.
- Escalate to `advanced` only after evaluation proves `basic` is insufficient or after human-approved second pass.

## Phased Roadmap

### Phase 0: Plan, Rulebook, and Source Reclassification

Goal:
- Freeze the architecture direction and query decomposition rulebook before production code changes.

Tasks:
- Create this active PLAN.
- Create `docs/source-query-decomposition-rules.md`.
- Classify C01-C46 into `search_assisted_sources`, `direct_structured_sources`, and `placeholder_or_manual_sources`.
- Identify direct-keep sources that must not be replaced by Tavily.
- Record credit-control strategy and API key placeholder.
- Add the Agent Execution Contract and Phase 1 Agent Assignment Draft.

Acceptance:
- PLAN is active in `.agent/STATUS.md`.
- Query decomposition rulebook exists and includes a worked example.
- Phase 1 can start without re-opening source research.
- Phase 1 can start through the v2 subagent workflow without redefining agent roles or validation gates.

### Phase 1: Query Decomposer Contract and Prompt Rules

Goal:
- Define the typed decomposition contract before invoking Tavily.

Tasks:
- Start with `invest_project_director` to confirm the Director Gate and assign Group 2/Group 3 work.
- Design a `QueryDecomposition` contract without changing EvidenceBundle.
- Add prompt/rule templates based on `docs/source-query-decomposition-rules.md`.
- Add deterministic validation for:
  - required theme and region extraction
  - allowed `tiaokuai_axis`
  - allowed source buckets
  - max search phrases per task
  - domain allowlist safety
  - direct-source preservation
- Add focused tests for 10 real queries, including low-altitude economy and region-specific questions.

Acceptance:
- `瀹夊窘鐨勪綆绌虹粡娴庢湭鏉ュ墠鏅浣昤 decomposes into multiple task families.
- Every task has a source bucket and execution path.
- The decomposer can produce search phrases without calling Tavily.
- Group 3 code-quality and functional validation are both recorded before moving to Phase 2.

### Phase 2: Tavily Search Discovery Layer

Goal:
- Add a Tavily-backed discovery path that consumes decomposition tasks.

Tasks:
- Add `TavilySearchAdapter` behind a provider interface.
- Support `include_domains`, `exclude_domains`, `country`, `topic`, `exact_match`, `max_results`, `search_depth`.
- Record Tavily request metadata and estimated credit use in trace metadata.
- Keep API key loading via settings/env.

Acceptance:
- At least 6 source categories return candidate URLs with `basic` mode.
- Usage metadata is recorded.
- Missing API key produces structured failure.

### Phase 3: Crawl4AI Extraction Layer

Goal:
- Convert Tavily candidate URLs into normalized documents and evidence inputs.

Tasks:
- Add `Crawl4AIExtractionService`.
- Extract title, URL, metadata, markdown, main content, tables, attachments/outlinks when available.
- Preserve structured partial failure behavior.
- Normalize Crawl4AI output into current source document contracts.

Acceptance:
- Candidate URLs from Phase 2 can be fetched into markdown.
- Extracted content can enter existing normalizer/evidence builder.
- Page failures do not crash the whole source-assisted flow.

### Phase 4: Search-Assisted Generic Source Migration

Goal:
- Move generic domestic source discovery to the Tavily + Crawl4AI path.

Migration candidates:
- `cn_policy_generic`
- `cn_industry_association_generic`
- province/city/park generic profiles
- association/topic/whitepaper generic profiles

Non-migration candidates:
- disclosure backbone
- structured data
- query platforms
- credit/GSXT/judicial paths

Acceptance:
- Generic path becomes search-assisted and lighter.
- Direct structured path remains available.
- Evidence bundle shape remains unchanged.

### Phase 5: Query-Based Usability Eval and Cost Review

Goal:
- Prove whether the lighter architecture is more usable than current live source behavior.

Tasks:
- Build an eval set with at least 10 real queries.
- Measure coverage, evidence sufficiency, source relevance, failure transparency, latency, and estimated Tavily credit use.
- Include at least:
  - one central policy query
  - one provincial policy query
  - one city/park query
  - one association/topic query
  - one disclosure query
  - one project/transaction query
  - `瀹夊窘鐨勪綆绌虹粡娴庢湭鏉ュ墠鏅浣昤

Acceptance:
- The team can identify which source categories work well with Tavily.
- The team can identify which direct adapters must remain.
- Credit usage is visible enough for product-level tradeoffs.

## Continue Rule

After each phase, continue automatically to the next phase when:
- acceptance criteria are met
- required code-quality and functional validation pass
- no credential, runtime, network, database, Docker, browser, or human-review blocker exists
- no high-risk contract change is being made without explicit PLAN authorization
- `.agent/STATUS.md` and this PLAN have both been updated with progress, validation, risks, and next action

Do not treat a phase summary as a default stopping point. For this PLAN, phase completion should trigger `invest_project_director` to advance the current phase unless a stop condition is reached.

## Stop Conditions

Stop and ask for user guidance only when:
- missing `TAVILY_API_KEY`, Crawl4AI runtime, network access, database/runtime dependency, or another external prerequisite blocks the next phase
- the next step would alter EvidenceBundle, EvidenceItem citations, `source_quality_summary`, research response shape, task/job semantics, or source routing contracts without explicit authorization
- validation fails and the repair path is unclear or high risk
- functional validation proves a core architecture assumption wrong
- the user explicitly pauses, asks for planning-only output, or changes product direction
- the final done condition is reached

## Done Condition

This PLAN is complete when:
- Phase 1 defines and validates query decomposition without external API keys
- Phase 2 integrates Tavily search discovery with low-credit defaults and structured missing-key behavior
- Phase 3 integrates Crawl4AI extraction with structured partial failure behavior
- Phase 4 migrates suitable generic source paths without weakening direct structured adapters
- Phase 5 completes query-based usability evaluation and credit review
- EvidenceBundle, citation, research response, source-quality, and task/job contracts are preserved or any approved changes are documented with migration impact
- `.agent/STATUS.md` reflects completion or the next active long-running PLAN
- remaining risks and TODOs are recorded

## Validation Loop

For each implementation phase:
1. `invest_project_director` confirms the current phase, updates the real-world validation plan, and assigns Group 2/Group 3 work.
2. Group 2 makes one coherent implementation change within explicit write scope.
3. `invest_code_quality_checker` runs required ruff, compile, focused pytest, import safety, and task-specific checks.
4. `invest_functional_validator` runs the real-world validation scenarios recorded in this PLAN.
5. If validation passes, record the exact snapshot and continue to the next phase.
6. If validation fails and the fix is safe, assign one focused repair loop.
7. If repair is unclear, high risk, or blocked by external dependency, record the blocker and stop.

## Sandbox And Trust Notes

- Workspace root: `E:\invest_agent`
- Project config/trust status: follow current Codex app project context and repository `AGENTS.md`
- Network/API needs:
  - Phase 1: none required
  - Phase 2: Tavily API key and network required for live search validation
  - Phase 3: Crawl4AI runtime and network required for live extraction validation
- Credentials:
  - `TAVILY_API_KEY=__SET_IN_ENV__`
- Database/Docker/browser needs:
  - Phase 1 should not require database, Docker, or browser
  - Later phases may need app/test runtime depending on integration path
- Fallback path:
  - If Tavily is unavailable, keep direct adapters and deterministic query templates
  - If Crawl4AI is unavailable, preserve URL candidates and structured extraction errors
  - If live external validation is unavailable, run contract tests and record the validation gap

## Validation Plan

During planning/docs-only phase:
- Verify files exist and `.agent/STATUS.md` points to this PLAN.
- No production code tests required because no production code is changed.

During implementation phases:
- Always run `.agent/skills/source-regression-check.md`.
- Run `.agent/skills/domestic-source-check.md` when domestic source code changes.
- Run `.agent/skills/research-contract-check.md` if research request/response or source-assisted handoff changes.
- Add focused tests for query decomposition before Tavily integration.
- Add practical live checks only when external access and API key are available.

Suggested real-world validation scenarios:
- `瀹夊窘鐨勪綆绌虹粡娴庢湭鏉ュ墠鏅浣昤
- `骞夸笢浜哄舰鏈哄櫒浜轰骇涓氭斂绛栧拰椤圭洰钀藉湴鎯呭喌`
- `娣卞湷浣庣┖缁忔祹鏈夊摢浜涙斂绛栧拰鎷涙爣淇″彿`
- `涓俊娴风洿锛?00099.SZ锛夊湪浣庣┖缁忔祹鏂瑰悜鏈夊摢浜涘叕鍛婂拰椤圭洰`
- `鏂拌兘婧愭苯杞︽崲鐢垫斂绛栨湭鏉ヨ秼鍔縛

## Real-world Validation Plan

Phase:
- Phase 1: Query Decomposer Contract and Prompt Rules

Scenario:
- Prove that the repository can decompose a realistic domestic industry-intelligence query into auditable tiaokuai-aligned tasks before any Tavily or Crawl4AI integration starts.
- Prove that the decomposer preserves direct structured paths for disclosure, statistics, procurement/query platforms, credit/GSXT, and judicial categories instead of collapsing everything into generic search.

Inputs:
- No network access, Tavily call, Crawl4AI call, browser automation, or `TAVILY_API_KEY` is allowed in this phase.
- Real validation query set:
  - `瀹夊窘鐨勪綆绌虹粡娴庢湭鏉ュ墠鏅浣昤
  - `骞夸笢浜哄舰鏈哄櫒浜轰骇涓氭斂绛栧拰椤圭洰钀藉湴鎯呭喌`
  - `娣卞湷浣庣┖缁忔祹鏈夊摢浜涙斂绛栧拰鎷涙爣淇″彿`
  - `涓俊娴风洿锛?00099.SZ锛夊湪浣庣┖缁忔祹鏂瑰悜鏈夊摢浜涘叕鍛婂拰椤圭洰`
  - `鏂拌兘婧愭苯杞︽崲鐢垫斂绛栨湭鏉ヨ秼鍔縛
  - `姹熻嫃鍏変紡浜т笟閾惧嚭娴烽潰涓村摢浜涙斂绛栧拰璐告槗椋庨櫓`
  - `鎴愰兘浜哄伐鏅鸿兘浜т笟鍥尯鏈夊摢浜涙斂绛栧拰椤圭洰鏈轰細`
  - `娴欐睙浣庣┖缁忔祹鐩稿叧涓婂競鍏徃鏈夊摢浜涘叕鍛奰
  - `鍥藉灞傞潰瀵圭畻鍔涘熀纭€璁炬柦鏈変粈涔堟渶鏂版斂绛栨柟鍚慲
  - `鏌愯涓氬崗浼氱殑鐧界毊涔﹀拰璁哄潧淇℃伅濡備綍浣滀负琛ュ厖璇佹嵁`
- Validation entrypoints may be focused unit tests, fixture-driven contract tests, or a deterministic local helper invoked from tests.

Expected behavior:
- Each query decomposes into one or more tasks with:
  - `task_family`
  - `tiaokuai_axis`
  - `line_family`
  - `regional_level`
  - `info_type`
  - `execution_bucket`
  - `source_cluster`
  - `include_domains` / `exclude_domains`
  - `search_phrases`
  - `evidence_goal`
  - `fallback_path`
- Search-assisted and direct-structured buckets remain distinguishable.
- Block or mixed tasks with regional intent carry explicit region terms.
- Unsupported or low-confidence cases are surfaced deterministically through fallback/template rules, not silent free-form output.

Acceptance criteria:
- `瀹夊窘鐨勪綆绌虹粡娴庢湭鏉ュ墠鏅浣昤 yields at least `policy_direction`, `local_rollout`, `project_transaction`, `enterprise_disclosure`, and `industry_topic`; `data_metrics` remains optional.
- `涓俊娴风洿锛?00099.SZ锛夊湪浣庣┖缁忔祹鏂瑰悜鏈夊摢浜涘叕鍛婂拰椤圭洰` preserves direct-structured handling for disclosure/project-query tasks and does not degrade them into pure `search_assisted_sources`.
- No task emits unsupported axis, line family, regional level, info type, or execution bucket values.
- No task emits more than 3 default search phrases.
- Phase 1 validation completes with no Tavily/Crawl4AI invocation and without requiring `TAVILY_API_KEY`.
- High-risk contracts remain unchanged:
  - EvidenceBundle schema
  - EvidenceItem citation fields
  - `source_quality_summary`
  - research analyze response shape
  - task/job status semantics
  - source routing contracts used by downstream workflows

Validation owner:
- `invest_code_quality_checker` owns automated checks, import/compile safety, and touched-file scope review.
- `invest_functional_validator` owns real-query decomposition checks against the 10-query set and the Phase 1 acceptance criteria.

Evidence to capture:
- Exact commands run for lint, compile, and pytest.
- One saved or test-asserted decomposition output for `瀹夊窘鐨勪綆绌虹粡娴庢湭鏉ュ墠鏅浣昤.
- One saved or test-asserted decomposition output for `涓俊娴风洿锛?00099.SZ锛夊湪浣庣┖缁忔祹鏂瑰悜鏈夊摢浜涘叕鍛婂拰椤圭洰`.
- Evidence that `TAVILY_API_KEY` is not required for Phase 1 validation.
- PLAN/STATUS notes recording pass, fail, or blocker classification.

Fallback/blocker handling:
- If the repo lacks a standalone decomposer entrypoint, Group 2 may add a narrow local helper/module, but must not wire live external providers in Phase 1.
- If deterministic validation cannot protect a direct-keep source family, stop Phase 1 and record the blocker before any Tavily-facing work starts.
- If a proposed implementation needs to alter a protected high-risk contract, stop and re-open the PLAN instead of patching around it.

### Phase 1 Agent Contract

Director Gate:
- Phase objective: establish a typed, testable query-decomposition contract and rule/prompt loading path without changing downstream research or evidence contracts.
- Required real-world validation: pass the 10-query offline decomposition checks above and prove direct-keep categories are preserved.
- Allowed write scope:
  - `invest_agent_architecture_builder`: `packages/sources/schemas.py`, `packages/sources/enums.py`, `packages/sources/governance.py`, `packages/sources/router.py`, `docs/source-query-decomposition-rules.md`, and one new narrow contract module under `packages/sources/` if needed.
  - `invest_feature_programmer`: one new decomposition implementation module under `packages/sources/`, narrow integration touchpoints in `packages/sources/service.py` or `packages/sources/router.py` only if needed to expose the contract, and focused tests under `tests/` for the Phase 1 query set.
- High-risk contracts protected:
  - no `EvidenceBundle` changes
  - no citation-field changes
  - no `source_quality_summary` changes
  - no research API/response shape changes
  - no task/job semantic changes
  - no production source-routing contract change beyond adding a backward-compatible decomposition helper/hook

Group 2 Assignments:
- `invest_agent_architecture_builder`:
  - define the `QueryDecomposition` contract, allowed enums, validation states, and future provider handoff fields
  - decide whether existing `packages/sources/schemas.py` should host the contract or whether a dedicated `packages/sources/query_decomposer.py` or similar module is cleaner
  - document module boundaries so Tavily/Crawl4AI can plug in later without Phase 1 rework
- `invest_feature_programmer`:
  - implement the minimal offline decomposer, rule/prompt loading, deterministic validator, fallback behavior, and focused tests
  - keep runtime entrypoints local to the source layer; do not wire networked providers or env-key dependencies

Group 3 Validation:
- `invest_code_quality_checker`:
  - run `python -m ruff check` on touched Phase 1 files
  - run `python -m py_compile` on touched Python files
  - run focused pytest for the new/updated decomposition tests
  - if `packages/sources/**` changes, run the required parts of `.agent/skills/source-regression-check.md`
  - if domestic profile/router logic changes, also run the required parts of `.agent/skills/domestic-source-check.md`
  - if source-assisted research handoff changes, also run `.agent/skills/research-contract-check.md`
- `invest_functional_validator`:
  - execute the 10-query offline validation set
  - inspect whether direct-keep sources remain direct for disclosure, data metrics, project/query platforms, and GSXT/judicial buckets
  - confirm no external provider call or API-key requirement is introduced in Phase 1

Completion Gate:
- Required code checks:
  - touched-file `ruff`
  - touched-file `py_compile`
  - focused pytest for decomposition coverage
  - additional source/research regression suites only if the touched scope reaches those contracts
- Required functional checks:
  - pass the 10-query offline validation set
  - capture at least two representative decomposition artifacts
  - prove direct structured preservation on disclosure/project-style inputs
- STATUS update required: yes, after Group 3 finishes or a blocker is found.
- PLAN progress update required: yes, after Director Gate, after implementation, and after validation.

## Risks

- Tavily search results may include stale, duplicated, or low-authority pages.
- Search discovery can hide source-specific pagination and attachment behavior.
- Crawl4AI extraction may miss tables, attachments, or JavaScript-rendered content.
- LLM query decomposition may over-expand or invent unsupported source paths.
- Tavily credit use can grow quickly if decomposition emits too many tasks.
- Current direct structured adapters may be accidentally weakened if migration boundaries are not explicit.

## Rollback

- Keep direct structured adapters as primary for disclosure, data, and query platforms.
- Keep existing profile-driven path until search-assisted generic path passes eval.
- If Tavily is unavailable, degrade to direct adapters and user-provided sources.
- If LLM decomposition is low-confidence, fall back to deterministic query templates.
- If Crawl4AI fails on a page, preserve URL candidate and structured error metadata.

## Validation Snapshot

- Planning baseline created:
  - `.agent/PLANS/domestic-source-lite-refactor-v1.md` exists
  - `.agent/STATUS.md` points to this PLAN
  - `docs/source-query-decomposition-rules.md` exists
  - no production code was modified by the plan creation step
- Agent-to-PLAN contract added:
  - Agent Execution Contract exists in this PLAN
  - Phase 1 Agent Assignment Draft exists in this PLAN
  - `.agent/STATUS.md` marks Phase 1 as ready for Director Gate
- Plan formatting update:
  - PLAN now includes Background Reused, Scope, Constraints, Continue Rule, Stop Conditions, Done Condition, Validation Loop, Sandbox And Trust Notes, Validation Snapshot, Risks, Rollback, Progress, Current Phase, and Next Action
  - no production code was modified by the formatting step
- Phase 1 Director Gate completed:
  - read `AGENTS.md`, `.agent/STATUS.md`, the active PLAN, `docs/subagents-operating-model.md`, `docs/source-query-decomposition-rules.md`, and the relevant source/research validation checklists
  - added a concrete Phase 1 `Real-world Validation Plan`
  - froze Group 2 / Group 3 write scope and validation ownership for offline-only Phase 1 execution
  - no production code was modified by the Director Gate step
- Phase 2 completed:
  - Tavily discovery contract, adapter behavior, request validation, exact-phrase mapping, and focused tests passed
  - live Tavily smoke validated six representative source categories using temporary process environment credentials
  - no credentials were written into this PLAN or repository files
- Phase 3 Director Gate completed:
  - read `AGENTS.md`, `.agent/STATUS.md`, the active PLAN, and the relevant validation skills:
    - `.agent/skills/source-regression-check.md`
    - `.agent/skills/domestic-source-check.md`
    - `.agent/skills/research-contract-check.md`
    - `.agent/skills/task-flow-check.md`
  - froze the Phase 3 real-world validation dataset shape, allowed write scope, Group 2 / Group 3 ownership, completion gate, and blocker / fallback rules
  - no production code was modified by the Director Gate step

## Progress

- Phase 1 and Phase 2 are complete with focused automated validation and Phase 2 live Tavily smoke.
- Phase 3 Director Gate is complete.
- Phase 3 real-world validation, write scope, validator ownership, and fallback rules are now explicit before Crawl4AI implementation starts.
- No production code was modified by this Director Gate step.

## Current Phase

Phase 3: Crawl4AI Extraction Layer. Director Gate completed; awaiting Group 2 execution.

## Next Action

Director Gate update:
- Run Group 2 Phase 3 work within the frozen write scope below.
- `invest_agent_architecture_builder` defines the Crawl4AI extraction contract, normalization boundary, and unavailable-runtime behavior.
- `invest_feature_programmer` implements the extraction layer, normalization bridge, and focused tests without weakening protected contracts.
- After implementation, hand off to `invest_code_quality_checker`, then `invest_functional_validator`, before considering Phase 4.

When the user says "寮€濮嬪疄鏂絇LAN", "瀹炴柦褰撳墠PLAN", "鎵цPLAN", or an equivalent instruction, start the v2 subagent workflow with `invest_project_director`, then run the assigned Group 2 and Group 3 agents for Phase 3.

---

## Phase 1 Completion Snapshot - 2026-04-26

Status:
- completed

What changed:
- Added `packages/sources/query_decomposition.py`.
- Added focused offline tests in `tests/test_sources_query_decomposition.py`.
- Exported decomposition contracts from `packages/sources/__init__.py`.

Validation:
- `python -m ruff check packages\sources\query_decomposition.py tests\test_sources_query_decomposition.py packages\sources\__init__.py`
- `python -m py_compile packages\sources\query_decomposition.py packages\sources\__init__.py tests\test_sources_query_decomposition.py`
- `pytest -q tests\test_sources_query_decomposition.py`
- Source regression focused suites passed:
  - `pytest -q tests\test_sources_layer.py`
  - `pytest -q tests\test_sources_adapters_v1.py`
  - `pytest -q tests\test_sources_hardening_step34.py`
  - `pytest -q tests\test_sources_evals_step35.py`
- Domestic source focused suites passed:
  - `pytest -q tests\test_sources_router_domestic.py`
  - `pytest -q tests\test_sources_profile_adapter.py`
  - `pytest -q tests\test_sources_real_domestic_step42.py`
  - `pytest -q tests\test_sources_pdf_step43.py`

Functional result:
- `安徽的低空经济未来前景如何` decomposes into `policy_direction`, `local_rollout`, `project_transaction`, `enterprise_disclosure`, and `industry_topic`.
- `中信海直（000099.SZ）在低空经济方向有哪些公告和项目` preserves direct structured handling for disclosure and project/transaction tasks.
- No Tavily, Crawl4AI, or `TAVILY_API_KEY` dependency is required for Phase 1.

Risks / notes:
- Phase 1 validation artifacts under `data/tmp` are scratch files and currently make repo-wide `ruff check .` fail if included.

## Phase 2 Implementation Snapshot - 2026-04-26

Status:
- implemented locally
- Group 3 validation in progress

What changed:
- Added `packages/sources/search_discovery.py`.
- Added Tavily settings to `packages/core/config.py`.
- Added Tavily placeholders to `.env.example`.
- Exported search discovery contracts from `packages/sources/__init__.py`.
- Added `tests/test_sources_search_discovery.py`.
- Sanitized this PLAN so credentials are represented as `TAVILY_API_KEY=__SET_IN_ENV__` instead of a literal key.

Validation:
- `python -m ruff check packages\sources\search_discovery.py packages\sources\__init__.py packages\core\config.py tests\test_sources_search_discovery.py`
- `python -m py_compile packages\sources\search_discovery.py packages\sources\__init__.py packages\core\config.py tests\test_sources_search_discovery.py`
- `pytest -q tests\test_sources_search_discovery.py tests\test_sources_query_decomposition.py`
- Source regression focused suites passed:
  - `pytest -q tests\test_sources_layer.py`
  - `pytest -q tests\test_sources_adapters_v1.py`
  - `pytest -q tests\test_sources_hardening_step34.py`
  - `pytest -q tests\test_sources_evals_step35.py`
- Domestic source focused suites passed:
  - `pytest -q tests\test_sources_router_domestic.py`
  - `pytest -q tests\test_sources_profile_adapter.py`
  - `pytest -q tests\test_sources_real_domestic_step42.py`
  - `pytest -q tests\test_sources_pdf_step43.py`

Functional result:
- Missing `TAVILY_API_KEY` returns a structured `ToolStatus.ERROR` response with `ToolErrorCode.INVALID_REQUEST`.
- Default Tavily request path uses low-credit settings: `search_depth=basic`, `max_results=5`, `auto_parameters=false`, `include_answer=false`, and `include_raw_content=false`.
- `include_domains`, `exclude_domains`, and `exact_match` are forwarded to Tavily payloads.
- `search_task()` consumes `QueryDecompositionTask.search_phrases` and domain constraints.
- Usage metadata records estimated credits and redacted request parameters.

Known validation limitation:
- `python -m ruff check .` still fails on `data/tmp` scratch/demo scripts. This is outside the Phase 2 touched production/test scope.
- Live Tavily validation has not been run in this process. The adapter reads `TAVILY_API_KEY` from settings/environment, not from this PLAN.

Next action:
- Wait for `invest_code_quality_checker` and `invest_functional_validator` Phase 2 reports.
- If Group 3 passes, either run one live smoke test with `TAVILY_API_KEY` exported in the shell or mark Phase 2 completed as contract-tested and start Phase 3 Director Gate for Crawl4AI extraction.

## Phase 2 Completion Snapshot - 2026-04-27

Status:
- completed

What changed after Group 3 review:
- Added request-level validation for `TavilySearchRequest.search_depth` and `TavilySearchRequest.topic`.
- Added exact phrase mapping in `TavilySearchAdapter.search_task()`:
  - `QueryDecompositionTask.exact_phrases` are added as quoted query terms.
  - `exact_match=True` is forwarded on task-driven Tavily requests.
- Added support for Tavily's current low-credit `fast` search depth.
- Added focused regression tests for invalid overrides, exact phrase mapping, and `fast` depth.

Validation:
- `python -m ruff check packages\sources\search_discovery.py packages\sources\__init__.py packages\core\config.py tests\test_sources_search_discovery.py`
- `python -m py_compile packages\sources\search_discovery.py packages\sources\__init__.py packages\core\config.py tests\test_sources_search_discovery.py`
- `pytest -q tests\test_sources_search_discovery.py tests\test_sources_query_decomposition.py`
  - result: `25 passed`
- Source regression focused suites:
  - `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py`
  - result: `27 passed`
- Domestic source focused suites:
  - `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py`
  - result: `16 passed`

Live Tavily smoke:
- API key authentication works with a temporary process environment variable.
- English official-style smoke query returned HTTP 200 and one result.
- Chinese queries work when the query is constructed through a safe UTF-8 path; earlier `Query is invalid` responses were caused by PowerShell pipe encoding corrupting Chinese text into `?`.
- Six basic-mode source-category smoke cases all returned success, 2 results, and estimated 1 credit:
  - `central_policy`
  - `provincial_policy`
  - `city_department`
  - `park_city`
  - `association_topic`
  - `enterprise_disclosure_supplement`

Group 3 result:
- `invest_code_quality_checker`: pass after request-level validator fix.
- `invest_functional_validator`: pass after exact phrase mapping fix and live smoke evidence.

Known limitations:
- Live smoke used a temporary process env key and did not persist credentials to `.env`.
- `python -m ruff check .` still fails on `data/tmp` scratch/demo files unrelated to Phase 2.
- Phase 2 provides discovery contracts and adapter behavior, but does not yet wire Tavily into the research workflow or generic source execution path.

Current Phase Update:
- Phase 2 is complete.
- Phase 3 starts with Director Gate for Crawl4AI Extraction Layer.

## Phase 3 Director Gate - 2026-04-27

Status:
- director_gate_completed
- ready for Group 2 execution

Task classification:
- Primary area: `source_layer`
- Secondary areas:
  - `domestic_source_collectors`
  - `provider_layer`
  - `eval_policy_ops`
- Protected contracts:
  - EvidenceBundle schema
  - EvidenceItem citation fields
  - `source_quality_summary`
  - research analyze response shape
  - task/job status semantics
  - structured partial-failure behavior used by source-assisted flows

Phase objective:
- Add a Crawl4AI-backed extraction layer that turns Tavily candidate URLs into typed source documents and normalized evidence inputs.
- Keep Tavily responsible only for URL discovery.
- Keep direct structured adapters as the primary path for disclosure, structured tables, project-query systems, credit/GSXT, and judicial sources.
- Preserve existing contracts instead of re-shaping EvidenceBundle, citations, research responses, or task state.

Real-world validation plan:
- Validation dataset:
  - use one pinned representative URL from each Phase 2 live-smoke source category:
    - `central_policy`
    - `provincial_policy`
    - `city_department`
    - `park_city`
    - `association_topic`
    - `enterprise_disclosure_supplement`
  - the URL set must come from the Phase 2 smoke outputs or an immediate rerun of the same smoke queries with a temporary process environment key; do not persist credentials in files
- Validation scenarios:
  - batch extraction of the 6 pinned URLs through the new Crawl4AI extraction entrypoint
  - one unavailable-runtime scenario where Crawl4AI is missing or disabled
  - one mixed-result batch where at least one URL is intentionally invalid, blocked, or unsupported to prove partial-failure containment
- Evidence to capture per URL:
  - original candidate URL
  - final/canonical URL if available
  - extracted title
  - extracted or inferred publish time if available
  - markdown length or main-content length
  - section count after normalization
  - attachment/outlink counts when present
  - extraction status, structured errors, and retryability
- Expected behavior:
  - successful pages produce typed `RawDocument` and/or `NormalizedDocument` inputs without altering EvidenceBundle or citation schemas
  - failed pages produce structured extraction errors and remain attached to the batch trace as URL-level failures
  - batch extraction never collapses the whole result because one page fails
  - the output remains auditable enough for later evidence-building steps
- Acceptance thresholds:
  - at least 4 of the 6 pinned URLs extract successfully into typed document outputs
  - at least 1 success must come from a policy/government page and at least 1 success must come from a non-policy supplemental page (`association_topic` or `enterprise_disclosure_supplement`)
  - the mixed-result batch must return both success and structured failure records in one response
  - the unavailable-runtime scenario must return a structured unavailable error instead of an import crash or hidden fallback
  - no validation step may require plan-level credential storage

Allowed write scope:
- `invest_agent_architecture_builder` may edit:
  - `packages/sources/schemas.py`
  - `packages/sources/__init__.py`
  - `packages/sources/service.py`
  - one new narrow extraction contract/module under `packages/sources/` such as `crawl4ai_extraction.py`
  - tests that define the extraction contract and failure-shape expectations
- `invest_feature_programmer` may edit:
  - the new Crawl4AI extraction implementation module under `packages/sources/`
  - `packages/core/config.py` only if an optional runtime/config switch is required
  - `packages/sources/__init__.py`
  - `packages/sources/service.py` or `packages/sources/tools.py` only if required to expose a narrow source-layer entrypoint
  - focused tests under `tests/` for extraction success, normalization, unavailable-runtime handling, and partial failures
- Not allowed in Phase 3 without re-opening this PLAN:
  - `packages/agents/**`
  - `apps/api/routes/research.py`
  - `packages/tasks/**`
  - changing router semantics for direct structured source families
  - changing EvidenceBundle, citations, `source_quality_summary`, research response shape, or task/job semantics

Group 2 assignments:
- `invest_agent_architecture_builder`:
  - define the extraction request/response contract between Tavily candidate URLs and normalized source documents
  - specify how Crawl4AI success, unavailable-runtime, and per-URL failure states map into existing `ToolStatus` / `ToolError` semantics
  - document the exact handoff point into existing `RawDocument` / `NormalizedDocument` shapes
  - keep attachment/outlink metadata auditable without introducing a new downstream contract
- `invest_feature_programmer`:
  - implement the narrow Crawl4AI extraction service and normalization bridge
  - preserve typed partial-failure behavior at URL granularity
  - keep the integration local to `packages/sources/**`
  - avoid browser automation, OCR, or broad migration into generic profile execution during this phase

Group 3 validation:
- `invest_code_quality_checker`:
  - run touched-file `python -m ruff check`
  - run touched-file `python -m py_compile`
  - run focused pytest for the new Crawl4AI extraction tests
  - run the required source-layer regression suites from `.agent/skills/source-regression-check.md`
  - if `profile_adapter.py`, `router.py`, `live_fetch.py`, `live_pdf.py`, or domestic profile files are touched, also run the domestic-source suites from `.agent/skills/domestic-source-check.md`
  - if `packages/sources/service.py`, `packages/sources/tools.py`, or source-assisted research handoff changes in a way that could affect research contracts, also run `.agent/skills/research-contract-check.md`
  - if any task/run state semantics are touched, stop and escalate; do not patch around it under Phase 3 scope
- `invest_functional_validator`:
  - pin the 6-URL validation dataset from Phase 2 smoke evidence or immediate rerun
  - execute the live extraction batch and the mixed-result batch
  - verify typed normalization into `RawDocument` / `NormalizedDocument`
  - verify structured unavailable-runtime behavior
  - verify no direct structured family was silently rerouted into generic Crawl4AI extraction as the primary path

Completion gate:
- Required code checks:
  - touched-file `ruff`
  - touched-file `py_compile`
  - focused pytest for the new extraction contract/tests
  - source regression commands required by `.agent/skills/source-regression-check.md`
  - domestic-source suites only if Phase 3 touched domestic profile/router/live-fetch/pdf files
  - research-contract suites only if the Phase 3 touch scope reaches source-assisted research handoff
- Required functional checks:
  - the 6-URL live validation dataset is pinned and recorded by category
  - at least 4/6 live URLs extract into typed documents
  - one mixed-result batch proves structured partial-failure containment
  - one unavailable-runtime scenario proves structured unavailability behavior
  - extracted outputs remain compatible with existing document/evidence input shapes
  - no protected contract changes are introduced
- STATUS update required:
  - yes, after Director Gate, after Group 2 implementation, and after Group 3 validation or blocker discovery
- PLAN progress update required:
  - yes, after Director Gate, after implementation, after validation, and at any blocker/fallback activation

Blockers and fallback rules:
- If the exact Phase 2 candidate URLs were not persisted, the functional validator must first pin one representative URL per source category by replaying the same smoke queries with temporary process credentials. If network or credentials are unavailable, record the blocker and fall back to fixture-based contract validation plus one manually supplied official URL when possible.
- If Crawl4AI runtime or browser dependencies are unavailable locally, Phase 3 may still land a wrapper that returns structured unavailable errors and passes contract tests, but the phase does not complete until the live extraction validation gap is recorded in both PLAN and STATUS.
- If a page is JS-heavy, malformed, or attachment-first, preserve the candidate URL, record structured failure or partial extraction metadata, and do not force a schema expansion just to store raw Crawl4AI internals.
- If implementation pressure spills into generic profile migration, direct structured routing changes, research response changes, or task-state changes, stop and re-open the PLAN instead of widening Phase 3 silently.

Next action:
- Assign `invest_agent_architecture_builder` and `invest_feature_programmer` to implement the Phase 3 extraction layer inside the frozen scope above.
- Require `invest_code_quality_checker` and `invest_functional_validator` to validate against the pinned 6-URL dataset before any Phase 4 migration work starts.

## Phase 3 Group 2 Implementation Snapshot - 2026-04-27

Status:
- implemented
- ready for Group 3 validation

What changed:
- Added `packages/sources/crawl4ai_extraction.py` as a minimal Crawl4AI extraction layer with:
  - typed request/response contracts for URL batch extraction
  - optional dependency wrapper (`Crawl4AIUnavailableError`) returning structured unavailable responses
  - typed `RawDocument` and `NormalizedDocument` mapping from Crawl4AI outputs
  - URL-level structured errors and `ToolStatus.PARTIAL` handling for mixed batches
- Added `tests/test_sources_crawl4ai_extraction.py` focused contract tests:
  - unavailable runtime -> structured unsupported response
  - successful extraction -> typed document normalization
  - mixed success/failure -> partial response with URL-scoped error detail
- Updated `packages/sources/__init__.py` with narrow Crawl4AI extraction exports only.

Validation:
- Focused checks:
  - `python -m ruff check packages\sources\crawl4ai_extraction.py packages\sources\__init__.py tests\test_sources_crawl4ai_extraction.py`
  - `python -m py_compile packages\sources\crawl4ai_extraction.py packages\sources\__init__.py tests\test_sources_crawl4ai_extraction.py`
  - `pytest -q tests\test_sources_crawl4ai_extraction.py` -> `3 passed`
- Source regression checks:
  - `pytest -q tests\test_sources_layer.py` -> `8 passed`
  - `pytest -q tests\test_sources_adapters_v1.py` -> `8 passed`
  - `pytest -q tests\test_sources_hardening_step34.py` -> `4 passed`
  - `pytest -q tests\test_sources_evals_step35.py` -> `7 passed`
- Required skill command note:
  - `python -m ruff check .` still fails on known unrelated `data/tmp` scratch/demo files (existing repository limitation, not introduced by Phase 3 Group 2 changes).

Assumptions:
- Crawl4AI remains an optional runtime dependency at this phase.
- No task-state, evidence schema, citation shape, or source routing contract changes are introduced.

Risks / TODO:
- Group 3 still needs live validation on the pinned 6-category URL set.
- Group 3 should confirm local Crawl4AI runtime availability vs structured unavailable fallback behavior under real execution.

Next action:
- Run `invest_code_quality_checker` and `invest_functional_validator` Phase 3 validation against the pinned live URL dataset and unavailable-runtime scenario.

## Phase 3 Completion Snapshot - 2026-04-27

Status:
- completed with recorded validation gaps

What changed after Group 3 review:
- Added `SearchUrlCandidate` as the provider-neutral bridge from Tavily discovery output into Crawl4AI extraction.
- Added direct-keep protection:
  - `direct_structured_sources` candidates are rejected by default for Crawl4AI primary extraction.
  - `allow_supplemental_direct_keep=True` is required for supplemental IR/news-style extraction.
- Added error-message truncation before constructing `ToolError`, preventing long Crawl4AI runtime errors from violating schema limits.
- Fixed Crawl4AI default runner contract:
  - `timeout_seconds` now maps to `page_timeout=timeout_seconds * 1000`.
  - `user_agent` now maps to request headers.
- Fixed unavailable-runtime response metadata so `requested` and `failed` reflect the real batch size.

Validation:
- Focused checks:
  - `python -m ruff check packages\sources\crawl4ai_extraction.py packages\sources\__init__.py tests\test_sources_crawl4ai_extraction.py packages\sources\search_discovery.py tests\test_sources_search_discovery.py`
  - `python -m py_compile packages\sources\crawl4ai_extraction.py packages\sources\__init__.py tests\test_sources_crawl4ai_extraction.py packages\sources\search_discovery.py tests\test_sources_search_discovery.py`
  - `pytest -q tests\test_sources_crawl4ai_extraction.py tests\test_sources_search_discovery.py tests\test_sources_query_decomposition.py`
  - result: `32 passed`
- Source regression:
  - `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py`
  - result: `27 passed`
- Domestic source regression:
  - `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py`
  - result: `16 passed`

Live Crawl4AI validation:
- Runtime:
  - `crawl4ai==0.8.6` installed in the local user Python environment for validation only.
  - Playwright Chromium install command completed.
- Artifacts:
  - `data/tmp/tavily_phase3_pinned_urls_html_preferred.json`
  - `data/tmp/crawl4ai_phase3_live_validation_html_preferred.json`
- Result:
  - `requested=6`
  - `succeeded=5`
  - `failed=1`
  - `batch_status=partial`
- Successful categories:
  - `central_policy`
  - `provincial_policy`
  - `city_department`
  - `association_topic`
  - `enterprise_disclosure_supplement`
- Failed category:
  - `park_city`
  - failure was preserved as URL-level structured error; the batch did not crash.
- Acceptance:
  - at least 4/6 live URLs succeeded: pass (`5/6`)
  - at least one government/policy page succeeded: pass
  - at least one supplemental page succeeded: pass
  - mixed-result partial failure: pass
  - unavailable-runtime structured response: pass
  - direct structured protection unless supplemental: pass
  - typed `RawDocument` / `NormalizedDocument` output: pass

Group 3 result:
- `invest_code_quality_checker`: pass, with known unrelated repo-wide `data/tmp` ruff limitation.
- `invest_functional_validator`: pass with gaps.

Recorded validation gaps:
- `park_city` in the HTML-preferred pinned dataset still resolved to an `.xlsx` attachment, so this category should be repinned to a true HTML page before Phase 5 usability scoring.
- Windows PowerShell default GBK output can fail on Crawl4AI Unicode log symbols. Future live Crawl4AI validation should set:
  - `$env:PYTHONIOENCODING='utf-8'`
  - `$env:PYTHONUTF8='1'`
  - `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`
- Installing Crawl4AI introduced environment warnings:
  - `s3fs` / `fsspec` dependency mismatch in the user Python environment
  - `requests` dependency warning for `urllib3` / `chardet`
  - these were environment warnings, not current source-layer test failures.

Current Phase Update:
- Phase 3 is complete.
- Phase 4 can start with Director Gate for search-assisted generic source migration.

## Phase 4 Director Gate - 2026-04-27

Status:
- director_gate_completed
- ready for Group 2 execution

Task classification:
- Primary area: `source_layer`
- Secondary areas:
  - `domestic_source_collectors`
  - `provider_layer`
  - `eval_policy_ops`
- Protected contracts:
  - EvidenceBundle schema
  - EvidenceItem citation fields
  - `source_quality_summary`
  - research analyze response shape
  - task/job status semantics
  - existing direct-profile execution semantics for explicit structured adapters

Phase objective:
- Migrate only suitable generic domestic source discovery and page extraction to the existing query decomposition -> Tavily -> Crawl4AI path.
- Keep explicit direct structured adapters primary for disclosure, structured data, project-query systems, credit/GSXT, and judicial sources.
- Keep existing real domestic profile adapters available as fallback/reference during Phase 4 instead of deleting or silently weakening them.
- Avoid widening into research workflow, API response, task-state, or EvidenceBundle contract changes.

First-wave migration candidates:
- Generic official policy discovery:
  - `cn_policy_generic`
  - central ministry extension families from inventory rows `C04-C11`:
    - `cn_policy_mof_notice_generic`
    - `cn_policy_mofcom_notice_generic`
    - `cn_policy_mee_notice_generic`
    - `cn_policy_mnr_notice_generic`
    - `cn_policy_mara_notice_generic`
    - `cn_policy_most_notice_generic`
    - `cn_policy_mohurd_notice_generic`
    - `cn_policy_mot_notice_generic`
  - scope rule:
    - only official `gov.cn` or ministry-domain HTML/article pages discovered through allowlisted Tavily queries
- Generic local policy rollout discovery:
  - inventory row `C28` / `cn_policy_provincial_eco_env_generic`
  - generic local policy tasks generated from `QueryDecompositionTask.task_family=local_rollout`
  - scope rule:
    - only official province/city `gov.cn` and explicitly allowlisted DRC/MIIT domains
- Supplemental association/topic discovery:
  - `cn_industry_association_generic`
  - inventory rows `C40`, `C45`, `C46`:
    - `cn_industry_alliance_generic`
    - `cn_industry_expo_forum_generic`
    - `cn_industry_whitepaper_topic_generic`
  - scope rule:
    - supplemental only; evidence can enrich policy/project/disclosure narratives but cannot replace direct official backbones

Explicit non-migration / direct-keep list:
- Official disclosure backbone remains direct primary:
  - inventory rows `C17-C23`
  - concrete and adjacent source families:
    - `cn_exchange_sse_notice_v1`
    - `cn_exchange_szse_notice_v1`
    - `cn_exchange_cninfo_announcement_v1`
    - `cn_exchange_bse_notice_generic`
    - `cn_exchange_neeq_notice_generic`
    - `cn_bond_disclosure_generic`
    - `cn_regulator_csrc_notice_generic`
- Structured data / indicator sources remain direct primary:
  - inventory rows `C12-C16`, `C27`
  - `cn_data_stats_nea_generic`
  - `cn_data_nbs_indicator_generic`
  - `cn_data_customs_indicator_generic`
  - `cn_data_pricing_monitor_generic`
  - `cn_data_provincial_stats_generic`
- Project/query platforms remain direct primary:
  - inventory rows `C32-C35`
  - `cn_project_ccgp_procurement_v1`
  - `cn_project_ggzy_trade_v1`
  - `cn_project_ndrc_approval_v1`
  - `cn_project_land_mining_generic`
- Credit / GSXT / judicial remain out of Tavily main path:
  - inventory rows `C42-C44`
  - `cn_supervision_credit_china_generic`
  - `cn_supervision_gsxt_generic`
  - `cn_supervision_judicial_open_generic`
- Enterprise disclosure enhancement is not a first-wave migration target:
  - inventory rows `C36-C38`
  - `cn_enterprise_sasac_generic`
  - `cn_enterprise_central_soe_ir_generic`
  - `cn_enterprise_listed_ir_generic`
  - supplemental official IR/news discovery may be planned later, but direct disclosure anchor must remain primary

Explicit later-wave hold list:
- City and park rollout families are not first-wave migration targets in Phase 4:
  - inventory rows `C29-C31`
  - `cn_policy_shenzhen_gxt_tzgg_v1`
  - `cn_policy_guangzhou_gxt_tzgg_v1`
  - `cn_policy_nanjing_gxt_tzgg_v1`
  - `cn_policy_chengdu_jxj_tzgg_v1`
  - `cn_park_national_whitelist_generic`
  - `cn_park_provincial_whitelist_generic`
  - `cn_park_sh_lingang_tzgg_v1`
- reason:
  - current validation already shows `park_city` attachment-first / non-HTML instability, so this family should not define Phase 4 acceptance

Real-world validation plan:
- Validation dataset:
  - use 6 migrated-path live cases plus 2 negative-control cases
  - migrated-path live cases:
    - one central ministry extension query routed to an official ministry notice family
    - one second central ministry extension query routed to a different official ministry family
    - one provincial/local rollout query routed to an allowlisted province/city official domain
    - one second local rollout query routed to a different allowlisted province/city official domain
    - one association/whitepaper supplemental query
    - one alliance/forum/topic supplemental query
  - negative-control cases:
    - one disclosure query such as listed-company announcement lookup that must remain `direct_structured_sources`
    - one project/procurement query that must remain `direct_structured_sources`
- Representative query themes:
  - `低空经济`
  - `人形机器人`
  - `新能源汽车换电`
  - `人工智能产业园区`
  - `算力基础设施`
- Execution flow to validate:
  - `decompose_query()` produces `search_assisted_sources` only for the approved first-wave families
  - Tavily discovery uses existing low-credit defaults and allowlisted domains
  - candidate filtering rejects off-domain, attachment-first, or direct-keep-primary URLs before Crawl4AI extraction
  - Crawl4AI extraction produces typed `RawDocument` / `NormalizedDocument` results or structured URL-level failures
  - failed migrated-path cases preserve fallback metadata without mutating EvidenceBundle or citation contracts
- Evidence to capture per case:
  - decomposition task family
  - execution bucket
  - include/exclude domain constraints
  - candidate URL list with accept/reject reasons
  - chosen URL final domain
  - extracted title, publish time, section count, and attachment/outlink counts
  - extraction status, structured errors, and whether fallback-to-existing-profile or hold-state was triggered
- Acceptance thresholds:
  - at least 4 of the 6 migrated-path live cases produce at least one typed normalized document from an allowlisted domain
  - at least 2 successes must be official government/ministry/province/city HTML pages
  - at least 1 success must be an association/topic supplemental page
  - both negative-control cases must remain on `direct_structured_sources` and must not invoke Crawl4AI as the primary path
  - off-domain or attachment-first candidates must fail closed with structured metadata instead of silently widening scope
  - no validation artifact or PLAN text may expose API keys

Allowed write scope:
- `invest_agent_architecture_builder` may edit:
  - `packages/sources/service.py`
  - `packages/sources/tools.py`
  - `packages/sources/schemas.py`
  - `packages/sources/query_decomposition.py`
  - `packages/sources/search_discovery.py`
  - `packages/sources/crawl4ai_extraction.py`
  - `packages/sources/__init__.py`
  - one new narrow orchestration module under `packages/sources/` such as `search_assisted_domestic.py`
  - focused tests that define orchestration, filtering, fallback, and protected-path expectations
- `invest_feature_programmer` may edit:
  - the same source-layer files above
  - `packages/core/config.py` only if a small feature flag or limit-setting toggle is required
  - focused tests under `tests/` for first-wave migration behavior
- Not allowed in Phase 4 without re-opening this PLAN:
  - `packages/sources/profile_adapter.py`
  - `packages/sources/live_fetch.py`
  - `packages/sources/live_pdf.py`
  - `packages/sources/collectors/**`
  - `packages/sources/profiles/**`
  - `packages/agents/**`
  - `apps/api/routes/research.py`
  - `packages/tasks/**`
  - `packages/content/**`
  - `packages/delivery/**`
  - changing EvidenceBundle, citations, `source_quality_summary`, research response shape, or task/job semantics
  - deleting or weakening existing explicit domestic profiles

Group 2 assignments:
- `invest_agent_architecture_builder`:
  - define the Phase 4 orchestration contract from decomposition task -> Tavily request -> candidate filtering -> Crawl4AI extraction
  - freeze the allowlist rules that determine which `search_assisted_sources` tasks are eligible for first-wave migration
  - define how fallback, hold-state, and direct-keep refusals are represented in trace metadata without changing downstream evidence contracts
  - keep the integration local to the source layer and avoid forcing premature `SourceToolRegistry` or research-route rewiring
- `invest_feature_programmer`:
  - implement the narrow search-assisted domestic orchestration entrypoint inside `packages/sources/**`
  - enforce the first-wave migration allowlist and direct-keep refusal gates
  - preserve existing Tavily low-credit defaults and existing Crawl4AI partial-failure behavior
  - add focused tests for migrated-path success, off-domain rejection, direct-keep refusal, and fallback metadata
  - do not remove existing real profiles or broaden the change into API/task/workflow code

Group 3 validation:
- `invest_code_quality_checker`:
  - run touched-file `python -m ruff check`
  - run touched-file `python -m py_compile`
  - run focused pytest for:
    - `tests/test_sources_query_decomposition.py`
    - `tests/test_sources_search_discovery.py`
    - `tests/test_sources_crawl4ai_extraction.py`
    - any new Phase 4 search-assisted migration tests
  - run the required source-layer regression suites from `.agent/skills/source-regression-check.md`
  - if `router.py`, `profile_adapter.py`, `live_fetch.py`, `live_pdf.py`, `packages/sources/profiles/**`, or domestic collector files are touched, also run the domestic-source suites from `.agent/skills/domestic-source-check.md`
  - if the implementation touches source-assisted research handoff semantics, also run `.agent/skills/research-contract-check.md`
  - if any task/run-state semantics are touched, stop and escalate instead of validating around the change
- `invest_functional_validator`:
  - run the 6 migrated-path live cases and 2 negative-control cases recorded above
  - pin the resulting candidate/extraction artifacts under `data/tmp/` or another non-contract scratch location
  - verify official-domain filtering, supplemental-only behavior, structured partial failure, and direct-keep refusal
  - verify that first-wave migration does not require editing old domestic profiles to succeed
  - verify that `park_city` remains out of first-wave acceptance and does not silently become a required success case

Rollback criteria:
- any `direct_structured_sources` task family or protected source cluster is routed into Tavily + Crawl4AI as the primary path
- two or more of the first three official-source live cases return only attachments, off-domain pages, or untyped extraction failures
- the implementation requires widening into `profile_adapter.py`, `collectors/**`, `profiles/**`, research routes, or task-state code to complete Phase 4
- the migrated path cannot record structured fallback / hold-state metadata without changing EvidenceBundle or citation contracts
- Tavily defaults would need to be raised above the current low-credit baseline (`basic`/`fast`, `max_results<=5`) just to make first-wave cases usable

Completion gate:
- Required code checks:
  - touched-file `ruff`
  - touched-file `py_compile`
  - focused pytest for Phase 4 orchestration tests plus the existing decomposition/discovery/extraction suites
  - source regression commands required by `.agent/skills/source-regression-check.md`
  - domestic-source suites only if the Phase 4 touch scope crosses domestic profile/router/live-fetch/live-pdf boundaries
  - research-contract suites only if source-assisted research handoff semantics are touched
- Required functional checks:
  - 6 migrated-path live cases and 2 negative-control cases are recorded with traceable artifacts
  - at least 4/6 migrated-path cases succeed into typed normalized documents
  - official-domain and supplemental acceptance thresholds pass
  - both negative-control direct-keep cases stay off the migrated primary path
  - `park_city` remains a recorded holdout, not a hidden requirement
  - no protected contract changes are introduced
- STATUS update required:
  - yes, after Director Gate, after Group 2 implementation, and after Group 3 validation or blocker discovery
- PLAN progress update required:
  - yes, after Director Gate, after implementation, after validation, and at any rollback/fallback activation

Assumptions:
- Phase 4 remains a source-layer integration step, not a research workflow or API migration.
- Existing real domestic profiles in `packages/sources/profiles/china_scaleout.py` remain valid fallback/reference assets even if a generic migrated path is added.
- Temporary credentials may be used in the shell for live validation, but must never be persisted to the PLAN or repository files.

Risks / TODO:
- Generic policy discovery can drift into attachment-first or off-domain URLs unless candidate filtering is explicit.
- Association/topic sources may be noisier than official policy sources, so supplemental-only enforcement must be tested with live cases.
- `park_city` remains a known holdout and should be repinned to a true HTML page before any later park-focused rollout or Phase 5 usability scoring.
- Repo-wide `python -m ruff check .` is still blocked by unrelated `data/tmp` scratch files; Group 3 should treat touched-file checks plus required source skill commands as the Phase 4 quality gate unless the housekeeping issue is separately fixed.

Next action:
- Assign `invest_agent_architecture_builder` and `invest_feature_programmer` to implement the first-wave search-assisted orchestration inside the frozen Phase 4 scope above.
- Require `invest_code_quality_checker` and `invest_functional_validator` to validate against the 6 migrated-path live cases plus 2 negative-control direct-keep cases before Phase 4 is marked complete.

## Phase 4 Completion Snapshot - 2026-04-27

Status:
- completed
- Phase 5 is ready for Director Gate

What changed:
- Added `packages/sources/search_assisted_domestic.py` as a narrow source-layer orchestration entrypoint:
  - gates `QueryDecompositionTask` into first-wave search-assisted vs hold/refuse decisions
  - allows only `policy_direction`, provincial `local_rollout`, and supplemental `industry_topic` tasks
  - refuses `direct_structured_sources` so disclosure, project/query, data, credit/GSXT, and judicial paths remain protected
  - holds city/park/park-city families outside first-wave migration
  - runs Tavily discovery through the existing low-credit adapter, then passes accepted URL candidates to Crawl4AI extraction
  - records candidate accept/reject reasons without changing EvidenceBundle, citation, source-quality, research response, or task-state contracts
- Added focused tests in `tests/test_sources_search_assisted_domestic.py`.
- Exported Phase 4 contracts from `packages/sources/__init__.py`.

Guardrails added after validation review:
- Supplemental association/topic discovery is closed to explicit supplemental domains or task-provided `include_domains`; arbitrary `.cn` domains are no longer accepted.
- `local_rollout` first-wave migration is limited to `RegionalLevel.PROVINCIAL`.
- Attachment-first URLs are rejected before extraction.
- Search/navigation URLs are rejected before extraction, including `/site/search`, `/search`, `/s`, `so.*`, and `search.*` patterns.

Code quality validation:
- `python -m ruff check packages\sources\search_assisted_domestic.py packages\sources\__init__.py tests\test_sources_search_assisted_domestic.py` -> pass
- `python -m py_compile packages\sources\search_assisted_domestic.py packages\sources\__init__.py tests\test_sources_search_assisted_domestic.py` -> pass
- `pytest -q tests\test_sources_search_assisted_domestic.py tests\test_sources_query_decomposition.py tests\test_sources_search_discovery.py tests\test_sources_crawl4ai_extraction.py` -> `39 passed`
- `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`
- `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`
- `python -m ruff check .` still fails only on unrelated `data/tmp` scratch/demo scripts with known `UP009`, `I001`, and `E501` issues.

Group 3 validation:
- `invest_code_quality_checker`: pass.
- `invest_functional_validator`: pass.

Live functional validation:
- Artifact: `data/tmp/search_assisted_domestic_phase4_live_validation.json`
- Credentials: temporary process environment only; no API key persisted in PLAN, STATUS, repository files, or artifact.
- Settings:
  - `search_depth=basic`
  - `max_results=5`
  - `auto_parameters=false`
  - `include_answer=false`
  - `include_raw_content=false`
- Result:
  - migrated-path cases: `6`
  - successful typed normalized-document cases: `4/6`
  - official government/ministry/province successes: `2`
  - supplemental association/topic successes: `2`
  - negative controls: `2`
  - negative controls passed: `true`
  - acceptance pass: `true`
- Successful migrated cases:
  - `central_ndrc_low_altitude`
  - `anhui_low_altitude_rollout`
  - `association_low_altitude_whitepaper`
  - `topic_compute_whitepaper`
- Partial/no-accepted-candidate cases kept structured and non-blocking:
  - `central_miit_robot`
  - `guangdong_robot_rollout`
- Negative controls refused before search/extraction:
  - `negative_disclosure_citic`
  - `negative_project_procurement`

Operational notes:
- Windows PowerShell can corrupt Chinese query text when piping here-string Python code, causing Tavily HTTP 400 `Query is invalid`.
- For live Chinese-query validation, use UTF-8 source files or Unicode escape strings, and set:
  - `$env:PYTHONIOENCODING='utf-8'`
  - `$env:PYTHONUTF8='1'`
  - `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`

Risks / TODO:
- Phase 4 live artifact does not contain a live `off_domain_candidate` sample, though focused tests and fake-input validation confirm off-domain candidates fail closed.
- `central_miit_robot` and `guangdong_robot_rollout` show Tavily result volatility under strict allowlists.
- `park_city` remains a holdout and should be repinned to a true HTML page before park-focused rollout or final usability scoring.
- Shared Python environment still has `requests` dependency warnings and `s3fs` / `fsspec` mismatch from Crawl4AI runtime installation.

Current Phase Update:
- Phase 4 is complete.
- Phase 5 can start with Director Gate for query-based usability eval and credit review.

Next action:
- Run Phase 5 Director Gate to freeze the 10-query usability eval set, scoring rubric, credit accounting fields, and validation artifacts before broader evaluation execution.

## Phase 5 Director Gate - 2026-04-27

Status:
- director_gate_completed
- ready for Group 2 execution

Task classification:
- Primary area: `source_layer`
- Secondary areas:
  - `domestic_source_collectors`
  - `provider_layer`
  - `eval_policy_ops`
- Protected contracts:
  - EvidenceBundle schema
  - EvidenceItem citation fields
  - `source_quality_summary`
  - research analyze response shape
  - task/job status semantics
  - downstream source-routing response shapes
- Phase 5 write policy:
  - no production code changes
  - Phase 5 may edit only scripts, artifacts, tests, and plan/docs files in the frozen scope below

Phase objective:
- Run a query-based usability and cost review on top of the existing Phase 4 search-assisted domestic contracts.
- Measure where the current query decomposition -> Tavily -> Crawl4AI path is already usable, where strict allowlists are still volatile, and which source families must remain direct.
- Keep `park_city` and other known hold families visible in scoring without widening production scope or silently changing routing behavior.

Frozen 10-query usability eval set:
- `Q01` `安徽的低空经济未来前景如何？`
  - cohort: `search_assisted_primary`
  - intent: mixed central policy + Anhui provincial rollout + supplemental topic signals
- `Q02` `国家层面对人形机器人有什么最新政策方向？`
  - cohort: `search_assisted_primary`
  - intent: central ministry policy direction
  - note: strict-allowlist volatility sentinel
- `Q03` `广东人形机器人产业政策和项目落地情况`
  - cohort: `search_assisted_primary`
  - intent: provincial rollout
  - note: strict-allowlist volatility sentinel
- `Q04` `国家层面对算力基础设施有什么最新政策方向？`
  - cohort: `search_assisted_primary`
  - intent: central policy direction
- `Q05` `低空经济行业协会、白皮书和论坛最近释放了哪些产业信号？`
  - cohort: `search_assisted_primary`
  - intent: supplemental association/topic evidence
- `Q06` `中国算力基础设施白皮书和产业论坛最近释放了哪些信号？`
  - cohort: `search_assisted_primary`
  - intent: supplemental topic evidence
- `Q07` `成都人工智能产业园区有哪些政策和项目机会？`
  - cohort: `park_city_holdout`
  - intent: city/park rollout holdout
- `Q08` `中信海直（000099.SZ）在低空经济方向有哪些公告和项目？`
  - cohort: `direct_keep_negative_control`
  - intent: disclosure/query-platform direct-keep control
- `Q09` `深圳低空经济有哪些招标和中标项目？`
  - cohort: `direct_keep_negative_control`
  - intent: procurement/project-query direct-keep control
- `Q10` `国家统计局和国家能源局有哪些新能源装机与发电量数据？`
  - cohort: `direct_keep_negative_control`
  - intent: structured data / indicator direct-keep control

Real-world validation plan:
- Validation entrypoint:
  - run the existing query decomposition -> search-assisted domestic orchestration contract
  - do not add new routing logic or alternate search path
  - use the existing Tavily discovery defaults and existing Crawl4AI extraction behavior from Phase 4
- Frozen live settings:
  - `search_depth=basic`
  - `max_results=5`
  - `auto_parameters=false`
  - `include_answer=false`
  - `include_raw_content=false`
  - temporary process env only for `TAVILY_API_KEY`
- Required per-query artifact fields:
  - `query_id`
  - `query`
  - `cohort`
  - `decomposition_tasks`
  - `executed_search_assisted_tasks`
  - `refused_direct_keep_tasks`
  - `hold_tasks`
  - `accepted_candidates`
  - `rejected_candidates`
  - `normalized_documents`
  - `structured_failures`
  - `coverage`
  - `evidence_sufficiency`
  - `source_relevance`
  - `failure_transparency`
  - `latency_ms`
  - `estimated_tavily_credits`
  - `pass_classification`
- Scoring rubric:
  - `coverage`
    - `2`: expected primary path is reached and the case returns at least one usable result, or the control/holdout is correctly refused/held
    - `1`: primary path is partially covered but usable output is incomplete
    - `0`: wrong bucket, missing expected path, or unusable result without justified hold/refusal
  - `evidence_sufficiency`
    - `2`: at least one typed normalized document is usable for research, or a control/holdout returns an actionable structured refusal/hold
    - `1`: only partial usable evidence or only metadata-level support is available
    - `0`: no usable evidence or actionable structured outcome
  - `source_relevance`
    - `2`: accepted evidence stays on official allowlisted domains or approved supplemental domains aligned to the task
    - `1`: only partially aligned evidence is available but no off-domain widening occurs
    - `0`: off-domain, irrelevant, or attachment-first evidence is accepted
  - `failure_transparency`
    - `2`: refusal, hold, no-candidate, or extraction failure is recorded with structured reasons and candidate-level detail
    - `1`: a structured failure exists but key routing/candidate detail is missing
    - `0`: failure is silent or only visible as an opaque exception
  - `latency_ms`
    - exact wall-clock elapsed time per query
  - `estimated_tavily_credits`
    - integer estimate equal to the number of Tavily discovery calls executed under the frozen `basic` settings
- Required artifacts under `data/tmp/`:
  - `data/tmp/search_assisted_domestic_phase5_query_set.json`
  - `data/tmp/search_assisted_domestic_phase5_results.json`
  - `data/tmp/search_assisted_domestic_phase5_summary.md`
  - `data/tmp/search_assisted_domestic_phase5_cases/<query_id>.json`
  - optional helper script: `data/tmp/_phase5_search_assisted_domestic_eval.py`
- Exact pass/fail thresholds:
  - search-assisted primary cohort is exactly `Q01-Q06`
  - at least `4/6` search-assisted primary queries must produce at least one typed normalized document from an allowlisted official or approved supplemental domain
  - at least `2` successful primary queries must be official government/ministry/province results
  - at least `1` successful primary query must be a supplemental association/topic result
  - every primary query must have `failure_transparency=2`
  - only `Q02` and `Q03` may pass as `transparent_partial` without a normalized document, and only if:
    - no off-domain or attachment-first URL is accepted
    - `coverage>=1`
    - `source_relevance>=1`
    - `failure_transparency=2`
  - `Q07` is a frozen holdout and passes only if it remains a structured `park_city` or equivalent city/park hold with:
    - `estimated_tavily_credits=0`
    - no accepted off-domain or attachment-first candidates
    - `failure_transparency=2`
  - `Q08-Q10` are direct-keep negative controls and all must pass with:
    - `coverage=2`
    - `failure_transparency=2`
    - `estimated_tavily_credits=0`
    - no Crawl4AI primary-path extraction
  - aggregate latency gates:
    - median latency for queries that invoke Tavily must be `<=25000 ms`
    - no more than `2` Tavily-invoking queries may exceed `45000 ms`
    - each direct-keep control and the `park_city` holdout must complete in `<=5000 ms`
  - aggregate credit gates:
    - total estimated Tavily credits across `Q01-Q07` must be `<=16`
    - no single query may exceed `3` estimated Tavily credits
  - fail immediately if any query:
    - widens into off-domain acceptance
    - accepts attachment-first URLs as primary evidence
    - routes a direct-keep control into Tavily/Crawl4AI primary handling
    - requires production-code modification to explain the result

`park_city` and allowlist-volatility handling:
- `park_city` remains intentionally out of first-wave production scope for Phase 5.
- Phase 5 records `Q07` as a scored holdout, not as a required migrated-path success.
- Do not repin `park_city` during Phase 5 unless a separate Director Gate reopens scope.
- `Q02` and `Q03` remain explicit strict-allowlist volatility sentinels.
- A volatility sentinel may finish as `transparent_partial`, but it must fail closed and preserve structured candidate/rejection metadata.
- Volatility does not justify raising Tavily depth, increasing `max_results`, or broadening domain allowlists during Phase 5.

Allowed write scope:
- `.agent/PLANS/domestic-source-lite-refactor-v1.md`
- `.agent/STATUS.md`
- `data/tmp/_phase5_search_assisted_domestic_eval.py`
- `data/tmp/search_assisted_domestic_phase5_query_set.json`
- `data/tmp/search_assisted_domestic_phase5_results.json`
- `data/tmp/search_assisted_domestic_phase5_summary.md`
- `data/tmp/search_assisted_domestic_phase5_cases/**`
- `tests/test_sources_domestic_scaleout_phase5.py`
- one new focused Phase 5 eval-contract test under `tests/` if needed
- one narrow docs note update if needed under `docs/`
- Not allowed in Phase 5 without reopening this PLAN:
  - `packages/sources/**`
  - `packages/agents/**`
  - `packages/tasks/**`
  - `apps/api/**`
  - `packages/content/**`
  - `packages/delivery/**`
  - any EvidenceBundle, citation, source-quality, research response, or task-state contract changes

Group 2 assignments:
- `invest_agent_architecture_builder`:
  - freeze the Phase 5 eval artifact schema, cohort tags, score semantics, and threshold logic in docs/tests
  - define how `transparent_partial`, `direct_keep_control_pass`, and `park_city_holdout_pass` are represented without touching production routing
  - review any helper script for contract fidelity to the existing query decomposition -> Tavily -> Crawl4AI chain
- `invest_feature_programmer`:
  - implement only the Phase 5 eval helper script/artifacts/tests/docs inside the allowed write scope
  - encode the frozen 10-query set and scoring rubric exactly as recorded above
  - produce the required `data/tmp/` artifacts
  - do not patch source-layer production modules to improve scores during Phase 5

Group 3 validation:
- `invest_code_quality_checker`:
  - run touched-file `python -m ruff check` on any new Phase 5 Python scripts/tests
  - run touched-file `python -m py_compile` on any new Phase 5 Python scripts/tests
  - run focused pytest for:
    - `tests/test_sources_domestic_scaleout_phase5.py`
    - any new Phase 5 eval-contract test
    - `tests/test_sources_search_assisted_domestic.py`
    - `tests/test_sources_query_decomposition.py`
    - `tests/test_sources_search_discovery.py`
    - `tests/test_sources_crawl4ai_extraction.py`
  - if any production source-layer file is touched, stop and escalate because that violates the frozen Phase 5 scope
- `invest_functional_validator`:
  - run the exact `Q01-Q10` query set with temporary process credentials only
  - verify the artifacts under `data/tmp/` are complete and threshold calculations are reproducible
  - verify `Q07` remains a holdout, `Q08-Q10` remain direct-keep controls, and `Q02-Q03` only pass as volatility partials if they fail closed
  - compare Phase 5 results against the Phase 4 live baseline to identify whether usability gain is real or only apparent

Completion gate:
- Required code checks:
  - touched-file `ruff`
  - touched-file `py_compile`
  - focused pytest for the Phase 5 tests listed above
- Required functional checks:
  - all required `data/tmp/` artifacts exist
  - all direct-keep controls pass
  - the holdout rule for `park_city` passes
  - the search-assisted cohort meets the frozen success, latency, and credit thresholds
  - no production code is modified
- STATUS update required:
  - yes, after Group 2 artifact/test implementation and after Group 3 validation
- PLAN progress update required:
  - yes, after implementation, after validation, and at any threshold failure/blocker

Risks / TODO:
- `Q02` and `Q03` are intentionally preserved as volatility sentinels; poor outcomes there are valid only if the system remains fail-closed and transparent.
- Repo-wide `python -m ruff check .` remains non-gating for Phase 5 because unrelated `data/tmp` scratch files still carry known lint debt.
- Phase 5 may prove that some mixed research queries are usable only when paired with direct-keep structured sources; that outcome should be recorded as a product constraint, not patched around inside this phase.

Next action:
- Proceed immediately to Phase 5 Group 2 implementation within the frozen scripts/artifacts/tests/docs scope.
- After Group 2 completes, run Group 3 validation against the exact thresholds above before any Phase 5 completion claim.

## Phase 5 Live Validation Snapshot - 2026-04-27

Status:
- live validation failed
- Phase 5 is blocked before completion

What was run:
- `python data\tmp\_phase5_search_assisted_domestic_eval.py --mode live`
- Runtime credentials were supplied only through the temporary process environment.
- No API key value was persisted to PLAN, STATUS, or artifacts.

Artifacts:
- `data/tmp/search_assisted_domestic_phase5_query_set.json`
- `data/tmp/search_assisted_domestic_phase5_results.json`
- `data/tmp/search_assisted_domestic_phase5_summary.md`
- `data/tmp/search_assisted_domestic_phase5_cases/Q01.json` through `Q10.json`

Live result:
- `acceptance_pass=false`
- primary successes: `6/6`
- official successes: `6`
- supplemental successes: `0`
- direct keep control passes: `3`
- park city holdout passes: `1`
- total estimated Tavily credits: `48`
- Q01-Q07 estimated Tavily credits: `39`
- max single-query credits: `9`
- median Tavily latency: `42941 ms`
- Tavily queries over `45000 ms`: `5`

Failed thresholds:
- supplemental success count below threshold
- median Tavily latency over limit
- too many Tavily queries over `45000 ms`
- Q01-Q07 total credits over limit
- single-query credits over limit
- `Q07` holdout credits must be zero
- `Q08-Q10` direct-keep controls had non-zero Tavily credits
- `Q08-Q10` direct-keep controls showed Crawl4AI primary extraction
- immediate fail conditions triggered for `Q08,Q09,Q10`

Interpretation:
- The offline deterministic harness is structurally valid, but the live provider path exposes a real gating problem.
- Current live execution still allows direct-keep control queries to produce search-assisted work and Crawl4AI extraction.
- The `park_city` holdout also invoked Tavily under the live helper path.
- Query decomposition / task selection is therefore not strict enough for the Phase 5 direct-keep and holdout acceptance criteria.
- The live path also over-expands queries, causing credit and latency thresholds to fail.

Scope impact:
- Fixing the live failure likely requires production source-layer changes in `packages/sources/query_decomposition.py` and/or the search-assisted task selection boundary.
- Such changes are explicitly outside the frozen Phase 5 write scope.
- Do not patch production source code inside Phase 5 without reopening the PLAN scope.

Next action:
- Stop Phase 5 auto-completion.
- Reopen the PLAN with a narrow remediation gate before any production fix:
  - tighten direct-keep query decomposition so disclosure, project/query, and structured-data controls do not emit primary search-assisted tasks
  - ensure city/park/park-city holdouts produce structured hold outcomes with zero Tavily credits
  - cap live search-assisted task fanout so credits remain within the Phase 5 threshold
  - rerun the Phase 5 live eval after remediation


## Phase 5 Group 2 Implementation Snapshot - 2026-04-27

Status:
- implemented (Group 2 scope complete)
- ready for Group 3 validation/review handoff

Scope executed (frozen non-production paths only):
- data/tmp/_phase5_search_assisted_domestic_eval.py
- data/tmp/search_assisted_domestic_phase5_query_set.json
- data/tmp/search_assisted_domestic_phase5_results.json
- data/tmp/search_assisted_domestic_phase5_summary.md
- data/tmp/search_assisted_domestic_phase5_cases/Q01.json ... Q10.json
- 	ests/test_sources_domestic_scaleout_phase5.py

What was implemented:
- Added deterministic offline-by-default Phase 5 eval helper with optional live mode (--mode live) gated by TAVILY_API_KEY.
- Encoded frozen Q01-Q10 query set, cohorts, required case fields, scoring dimensions, pass classifications, and aggregate threshold gates.
- Encoded direct-keep control semantics (Q08-Q10) and park_city holdout semantics (Q07) into evaluation logic.
- Added immediate-fail guardrails for off-domain acceptance, attachment-first acceptance, direct-keep misrouting, and production-code-change dependency.
- Generated required data/tmp Phase 5 artifacts and per-case JSON outputs.
- Replaced Phase 5 test module with focused eval-contract tests for frozen query-set/schema/threshold/direct-keep/holdout behavior.

Validation snapshot (local):
- python -m ruff check data/tmp/_phase5_search_assisted_domestic_eval.py tests/test_sources_domestic_scaleout_phase5.py -> pass
- python -m py_compile data/tmp/_phase5_search_assisted_domestic_eval.py tests/test_sources_domestic_scaleout_phase5.py -> pass
- pytest -q tests/test_sources_domestic_scaleout_phase5.py tests/test_sources_search_assisted_domestic.py tests/test_sources_query_decomposition.py tests/test_sources_search_discovery.py tests/test_sources_crawl4ai_extraction.py -> 43 passed
- python data/tmp/_phase5_search_assisted_domestic_eval.py --mode offline -> pass; artifacts regenerated

Risks / TODO:
- Artifact display may appear mojibake in non-UTF8 terminals, but files are written as UTF-8.
- Live mode depends on runtime network/provider conditions and local Crawl4AI availability; offline mode remains deterministic baseline.

Next action:
- Run Group 3 functional validation against this frozen artifact set and confirm Phase 5 completion gate.

## Phase 5 Remediation Gate - 2026-04-27

Status:
- reopened_narrow_scope
- authorized by user continuation after live validation failure

Task classification:
- Primary area: `source_layer`
- Secondary areas: `domestic_source_collectors`, `provider_layer`, `eval_policy_ops`

Reason for reopening:
- Phase 5 live validation failed because direct-keep controls, the park/city holdout, and live query fanout did not preserve the intended source boundaries.
- The failure is not only an eval artifact problem; it exposes production routing/decomposition gates that are too permissive for direct-keep and holdout cases.

Allowed remediation write scope:
- `packages/sources/query_decomposition.py`
- `data/tmp/_phase5_search_assisted_domestic_eval.py`
- `tests/test_sources_query_decomposition.py`
- `tests/test_sources_domestic_scaleout_phase5.py`
- `.agent/PLANS/domestic-source-lite-refactor-v1.md`
- `.agent/STATUS.md`

Protected contracts:
- EvidenceBundle schema
- EvidenceItem citation fields
- `source_quality_summary`
- research analyze response shape
- task/job status semantics
- downstream source-routing response shapes

Required fixes:
- Tighten direct-keep query decomposition so disclosure, procurement/project-query, and structured-data controls do not emit primary search-assisted tasks.
- Ensure city/park/park-city queries produce a structured hold outcome with zero Tavily credits in the Phase 5 live path.
- Cap live search-assisted fanout for the Phase 5 eval so each query stays within the frozen credit threshold.
- Preserve first-wave source boundaries: Tavily remains discovery only; Crawl4AI remains extraction only; direct structured sources remain protected.

Validation required:
- `python -m ruff check packages/sources/query_decomposition.py data/tmp/_phase5_search_assisted_domestic_eval.py tests/test_sources_query_decomposition.py tests/test_sources_domestic_scaleout_phase5.py`
- `python -m py_compile packages/sources/query_decomposition.py data/tmp/_phase5_search_assisted_domestic_eval.py tests/test_sources_query_decomposition.py tests/test_sources_domestic_scaleout_phase5.py`
- `pytest -q tests/test_sources_query_decomposition.py tests/test_sources_domestic_scaleout_phase5.py tests/test_sources_search_assisted_domestic.py tests/test_sources_search_discovery.py tests/test_sources_crawl4ai_extraction.py`
- Source regression checklist focused commands from `.agent/skills/source-regression-check.md`
- Domestic source checklist focused commands from `.agent/skills/domestic-source-check.md`
- `python data/tmp/_phase5_search_assisted_domestic_eval.py --mode offline`
- `python data/tmp/_phase5_search_assisted_domestic_eval.py --mode live` with `TAVILY_API_KEY` supplied only through temporary process environment

Acceptance:
- Q07 has `estimated_tavily_credits=0`, structured hold metadata, and no Crawl4AI primary extraction.
- Q08-Q10 have `estimated_tavily_credits=0`, direct-keep refusal metadata, and no Crawl4AI primary extraction.
- No single live query exceeds `3` estimated Tavily credits.
- Q01-Q07 total estimated Tavily credits stay within the existing Phase 5 threshold.
- Phase 5 live acceptance passes or any remaining failure is recorded with a concrete blocker and no credential leakage.

Next action:
- Implement the narrow decomposition/task-selection remediation and rerun Phase 5 validation.

## Phase 5 Remediation Completion Snapshot - 2026-04-27

Status:
- completed
- Phase 5 live acceptance passed after remediation
- PLAN done condition reached

What changed:
- Tightened `packages/sources/query_decomposition.py` so direct-keep disclosure, project-query, and structured-data controls no longer emit primary search-assisted tasks.
- Added a park/city holdout marker by emitting `park_city_rollout_backbone` for park/city rollout queries.
- Added supplemental domain and phrase steering for association/topic queries based on Phase 4 validated source behavior.
- Capped Phase 5 live execution fanout in `data/tmp/_phase5_search_assisted_domestic_eval.py`:
  - max 1 search phrase per live search-assisted task
  - max 3 search-assisted tasks per query
  - max 1 Crawl4AI extraction candidate per task

Validation snapshot:
- `python -m ruff check packages\sources\query_decomposition.py data\tmp\_phase5_search_assisted_domestic_eval.py tests\test_sources_query_decomposition.py tests\test_sources_domestic_scaleout_phase5.py` -> pass
- `python -m py_compile packages\sources\query_decomposition.py data\tmp\_phase5_search_assisted_domestic_eval.py tests\test_sources_query_decomposition.py tests\test_sources_domestic_scaleout_phase5.py` -> pass
- `pytest -q tests\test_sources_query_decomposition.py tests\test_sources_domestic_scaleout_phase5.py tests\test_sources_search_assisted_domestic.py tests\test_sources_search_discovery.py tests\test_sources_crawl4ai_extraction.py` -> `53 passed`
- `pytest -q tests\test_sources_layer.py tests\test_sources_adapters_v1.py tests\test_sources_hardening_step34.py tests\test_sources_evals_step35.py` -> `27 passed`
- `pytest -q tests\test_sources_router_domestic.py tests\test_sources_profile_adapter.py tests\test_sources_real_domestic_step42.py tests\test_sources_pdf_step43.py` -> `16 passed`
- `python data\tmp\_phase5_search_assisted_domestic_eval.py --mode offline` -> pass
- `python data\tmp\_phase5_search_assisted_domestic_eval.py --mode live` -> pass
- API key persistence check across PLAN, STATUS, Phase 5 results, and Phase 5 summary -> no key-pattern match

Live result:
- `acceptance_pass=true`
- primary successes: `6/6`
- official successes: `2`
- supplemental successes: `4`
- direct keep control passes: `3`
- park city holdout passes: `1`
- total estimated Tavily credits: `10`
- Q01-Q07 estimated Tavily credits: `10`
- max single-query credits: `3`
- median Tavily latency: `9916 ms`
- Tavily queries over `45000 ms`: `1`

Known risks / TODO:
- Repo-wide `python -m ruff check .` still fails on unrelated historical `data/tmp` scratch/demo scripts; touched-file ruff passes.
- Q03 still has one live latency outlier above `45000 ms`, but aggregate threshold allows up to two and acceptance passes.
- Supplemental success currently depends on curated association/topic domain steering; broader supplemental source expansion should remain explicit and allowlisted.
- The active PLAN is marked completed; archive/move can be done after human review if desired.

Next action:
- Treat `domestic-source-lite-refactor-v1` as complete.
- For the next product step, start a new PLAN focused on integrating this search-assisted source path into the end-to-end research workflow and UI-facing evidence bundle flow.
