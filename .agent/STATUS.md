# STATUS.md

## Gateway 三层总状态

```text
G1 Research Control Plane     ACCEPTED
  - Admission / Idempotency / Run API / Events / Cancellation

G2 Provider Plane             ACCEPTED
  - LLM/Search Routing · Provider Budget · Circuit/Fallback · Telemetry

G3 Execution Plane            ACCEPTED (2026-08-08)
  - Global Active Run Capacity · TaskExecutionLease · Heartbeat/Crash Recovery · Fencing

Gateway Full-stack Acceptance ACCEPTED (2026-08-08)
  - 5 deterministic cases 全 PASS（normal / search fallback / crash-fencing /
    cancellation / active-run-capacity）

Research Gateway MVP         ACCEPTED（Gateway 开发冻结，回 Research/Evidence/Report 主线）
```

### Gateway Full-stack Acceptance — ACCEPTED (2026-08-08)

- `scripts/gateway_fullstack_acceptance.py`（真实 PG + deterministic fake providers）：
  1. **normal run**：POST 语义 → G1 submit → G3 claim → 执行（G2 Search+LLM）→ fenced
     finalize → Run SUCCEEDED + report 可读。
  2. **search fallback**：AnySearch ERROR → Tavily SUCCESS，ProviderAttempt 记录
     C1 AnySearch failed + C2 Tavily success。
  3. **worker crash/reclaim/fencing**：A gen=1 → lease 过期 → B gen=2 → A finalize 拒绝、
     **stale_artifact_publish=0**（最终 report = B 的结果）。
  4. **cancellation**：expired lease + cancel_requested → Run CANCELLED。
  5. **active-run-capacity**：max_active_runs=2 → max_observed=2，其余 QUEUED，最终全 SUCCEEDED。
- **Fencing 覆盖业务 artifact**：`DeepResearchAgent.run(..., expected_generation=)` +
  `_persist_report_for_run(..., expected_generation=)`——落库前校验 Run 当前 generation，
  mismatch 则跳过（`STALE_ARTIFACT_PUBLISH_SKIPPED`）。
- leaks：execution_lease=0 / provider_permit=0 / db_connection=0。
- 真实 DeepSeek/AnySearch 是另跑的 environment smoke，不把外部波动当架构失败。

## Research Gateway MVP — ACCEPTED

**Gateway 开发冻结**。G1/G2/G3 + Full-stack 全部完成，回到 invest-agent 主线：
Industry-chain Coverage / Evidence & Claim Coverage / Research Quality /
Structured Synthesis / Report Narrative Quality。

## G1 Research Control Plane — ACCEPTED (2026-08-07)

```text
G1 Research Control Plane
Status: ACCEPTED

Capabilities:
- G1.1 Research Run API
- G1.2 Idempotent Run Submission
- G1.3 Global Queue Admission & Backpressure
- G1.4 RunEvent Timeline
- G1.5 Cooperative Cancellation
- G1.6 PostgreSQL Concurrency Acceptance

Production invariants validated:
- exactly-one Run creation per idempotency scope/key
- exactly-one initial Task
- hard QUEUED capacity
- terminal state immutability
- cooperative cancellation convergence
- concurrent RunEvent sequencing
- observability fail-open
```

> 口径：**exactly-one 只限定在 Run creation / initial task creation**；Worker 后续
> crash/retry 仍属 **at-least-once execution attempts**，不扩大保证范围。

- 验收产物：`data/tmp/gateway_g1_6_acceptance/acceptance.json` + `G1_6_POSTGRES_ACCEPTANCE.md`
  （真实 PostgreSQL 16.13，10/10 PASS）。
- 测试基础设施强化：G1.6 Harness 每次 case 后校验连接池泄漏
  （`engine.pool.checkedout()`），`session_leak_detected=false` 为通过条件。
- 根因记录（G1.6 修复）：验收脚本创建大量长生命周期 Session，部分在后续
  autobegin 后仍持有活动事务/连接且未显式 close；随并发 case 累积连接池
  starvation。修复 = 将每次操作的 Session 生命周期限定在 contextmanager，
  operation 结束后无条件 close / rollback residual transaction / release
  checked-out connection。注意：`Session.commit()` 会结束事务并归还连接，但
  Session 后续任何 DB 操作会 autobegin 重新 checkout；因此用 context manager
  限定生命周期仍是正确做法。

## G2 Capability / Provider Plane — G2.2 in progress

```text
G0  Execution Foundation
  ↓
G1  Research Control Plane        ✅ ACCEPTED
  ↓
G2  Capability / Provider Plane   ← NEXT（G2.2 进行中）
  ↓
G3  Worker Scheduling
  ↓
G4  Full-stack Load Acceptance
```

- G1 回答：Run 能不能进来、现在在哪里、能不能取消。
- G2 回答：Run 内部需要 LLM/Search 时，到底调用谁、能否调用、失败以后怎么办。
- **冻结原则**：Agent 不再知道「我要 DeepSeek / AnySearch」，Agent 只知道
  「我要结构化抽取 / 网页搜索这种能力」；Provider 选择逐步全部收归 Capability
  Gateway。

### G2.1 Capability Contract & Registry — ACCEPTED (2026-08-07)

```text
G2.1 Capability Contract & Registry
Status: Accepted

Validated:
- capability/request/instance contract
- capability hard filtering
- required feature filtering
- circuit/open filtering primitive
- concurrency/quota eligibility primitive
- deterministic candidate ordering
- LLM/Search registry
- DeepSeek/OpenRouter and AnySearch/Tavily candidate chains

Not yet validated:
- production call-path integration
- runtime failure fallback
- concurrency enforcement
- circuit state transitions
- provider metrics
```

> 口径：`current_concurrency / quota / circuit_state / health` 现阶段是
> **routing inputs / contract fields**，不代表 Concurrency Budget / Circuit
> Breaker 已实现——真正的状态维护与竞争控制在 G2.3/G2.4。

### G2.2a Routing Plan Shadow — ACCEPTED (2026-08-07)

```text
G2.2a Routing Plan Shadow
Status: Accepted

Validated:
- CapabilityRouter → RoutingPlan（primary / fallback_chain / eligible / filtered / trace）
- deterministic route（同请求同 plan）；request_fingerprint 由请求内容哈希
- strict / fallback_allowed policy；feature 过滤
- Legacy vs Gateway SEARCH 选择等价（divergence=0）
- shadow 不 invoke Provider（非干预）
- Registry 只做 eligibility；Router 只做 decision→plan；Adapter 只做 invocation
```

### G2.2b Search Gateway Primary — ACCEPTED (2026-08-07)

```text
G2.2b Search Gateway Primary
Status: Accepted

Validated (Runtime Equivalence):
- AnySearch SUCCESS   == Legacy/Gateway 调用顺序+结果一致
- AnySearch ERROR→Tavily SUCCESS == 调用顺序+结果+provider identity 一致
- Both ERROR == 失败 Contract（status/error 语义）一致
- shadow 模式 Gateway transport 0 次；gateway 模式 Legacy selector 不执行
- 输出统一 SearchDiscoveryResponse，下游不见 Provider 原始响应
- request_fingerprint（确定性）与 execution_id（每次调用唯一）已拆分
```

- 新增 `SearchCapabilityService`（统一 SEARCH 入口，业务层不判断 flag）：
  - off → Legacy；shadow → Legacy 执行 + Gateway 只 route 对比；gateway → Gateway
    route + Adapter invoke（Legacy selector 不执行）；`enabled=false` 优先于 mode。
- **5 个生产模块 / 8 个 Search provider call sites 已切换至 Gateway-aware facade**：
  `deep_research`×2、`lane_execution`×3、`advisory_backfill_live`×1、
  `real_nodes`×1、`search_assisted_domestic`×1。
- 生产调用点清单见 `scripts/audit_search_call_sites.py`（可复核）。

### G2.2c LLM Routing Shadow — ACCEPTED

- LLM workload taxonomy（10 类）：`LLMTaskType` / `LLMTaskProfile` / `LLM_TASK_PROFILES`，
  requirements 集中定义（Agent 不得手写 provider requirements）。
- 第一版 policy：
  - fallback_allowed：`query_expansion`、`search_phrase_generation`
    （OpenRouter Free 只作为这两个 task_type 的 best-effort fallback candidate）。
  - strict：`intent_planning`、`research_planning`、`evidence_extraction`、
    `claim_generation`、`structured_draft`、`constrained_synthesis`、`structured_repair`、
    `source_tier_classification`（strict 的 RoutingPlan 禁止出现 OpenRouter Free fallback）。
- `LLMCapabilityService` shadow plan（纯路由不 invoke）。

### G2.2d Deterministic Routing Contract Acceptance — ACCEPTED

- **Router STRICT 硬化**：strict = 只允许 primary-role 合格 Provider；fallback_chain
  恒空；primary 不可用 → primary=None（不提升 fallback-role）。strict isolation 是
  **架构规则**，不依赖 provider feature 缺失（反事实测试证明）。
- **Provider-agnostic**：`source_tier_classification` → `ollama.source_tier.local`
  （Ollama 本地，strict）；`CapabilityInstance.task_types` 白名单限定服务范围。
- **Primary equivalence 升级**：gateway primary == legacy 语义 provider
  （`legacy_primary_instance`），不再假设全部 DeepSeek。
- **audit v2**：provider boundary visibility=9/9 (100%)；workload classification
  =13/13 (100%)；unclassified=0；direct bypass=0。
- 验收产物 `data/tmp/g2_2_routing_acceptance/`：
  `search_runtime_equivalence.json` / `llm_workload_audit.json` /
  `strict_policy_regression.json` / `routing_acceptance.json` /
  `G2_2_DETERMINISTIC_ROUTING_ACCEPTANCE.md`。

### G2.2 Deterministic Capability Routing — ACCEPTED (2026-08-08)

```text
G2.2 Deterministic Capability Routing
Status: ACCEPTED

Validated:
- SEARCH: 5 模块 / 8 call sites Runtime Equivalence（G2.2b）
- LLM workload: provider boundary visibility=100% / classification=100%
  / unclassified=0 / direct bypass=0
- Routing policy: legacy primary divergence=0 / STRICT fallback leakage=0
  / best-effort fallback plan 正确
- Shadow safety: Gateway transport calls=0 / Legacy runtime unchanged
```

- Feature flags（按 capability 分离）：`CAPABILITY_GATEWAY_ENABLED=false` +
  `CAPABILITY_GATEWAY_SEARCH_MODE=shadow` + `CAPABILITY_GATEWAY_LLM_MODE=off`。
- 顺序：G2.1 ✅ → G2.2a ✅ → G2.2b ✅ → G2.2c ✅ → G2.2d ✅ → **G2.3 ← IN PROGRESS**。

### G2.3 Provider Concurrency Budget — ACCEPTED (2026-08-08)

```text
G2.3 Provider Concurrency Budget
Status: ACCEPTED

G2.3a InProcess Budget        — Accepted（单进程语义验证）
G2.3b PostgreSQL Lease Budget — Accepted（production shared lease）

Hard invariants:
- 跨进程 hard cap（max_observed_active_leases <= cap）
- overshoot = 0
- success / error / cancel release
- waiting-cancel 不 invoke
- stale lease recovery（TTL 过期容量恢复）
- per-provider independence
- permit leak = 0
- Provider call 期间不持 DB transaction/connection
```

- 目标：无论多少 Run/Worker 并发，同一 Provider 的 `inflight calls` 永远 ≤
  `max_concurrency`（保护外部 Provider / 本地模型不被内部高并发打爆）。
- 三个身份：`request_fingerprint`（plan）/ `route_execution_id`（一次 Gateway
  invocation）/ `provider_call_id`（一次 Provider attempt，**permit 绑定它**）。
- `packages/capability_gateway/budget.py`：
  - `ProviderConcurrencyPolicy` / `ProviderPermit`（lease_id / acquired_at /
    expires_at / released_at）/ `ConcurrencyBudget` Protocol。
  - `InProcessConcurrencyBudget`（G2.3a：单进程语义验证，**非多进程生产保证**）。
  - `PostgresLeaseConcurrencyBudget`（G2.3b：production shared lease）。
- acquire = **短事务**：INSERT/ON CONFLICT state 行 → `SELECT ... FOR UPDATE` →
  清理过期/已释放 lease → count active → 若 < max insert lease → commit。
  **Provider 网络调用期间不持有 DB transaction/connection。**
- Lease 带 `expires_at`：Worker crash（kill -9）→ TTL 过期 → 容量自动恢复。
- 饱和第一版 = 有界等待（acquire_timeout）→ `PROVIDER_CAPACITY_EXHAUSTED`；
  **不自动 fallback、不计 health/circuit failure**（fallback-on-runtime → G2.4）。
- 等待支持业务取消（should_cancel）→ `BudgetWaitCancelled`，不 invoke provider。
- `RoutingInvoker` 集成：每 Provider attempt `acquire → invoke → finally release`
  （成功/失败/异常/取消都必须 release）。
- alembic：`a1b2c3d4e5f6_add_provider_concurrency_budget.py`（leases + state 表）。
- **验收（G2.3a in-process + G2.3b PostgreSQL）**：
  - G2.3a 10 例（硬上限 max_inflight=cap / success/error/cancel release /
    waiting-cancel 不 invoke / timeout / per-provider 独立 / stale recovery /
    permit 绑定 provider_call_id）。
  - G2.3b `scripts/g2_3_concurrency_acceptance.py`：30 worker × cap=5 →
    **max_observed_active_leases=5、overshoot=0、permit_leak=false、
    stale_recovery=PASS、per-provider 独立=PASS**（真实 PG）。
  - **修复**：lease `expires_at` 改为用 **DB 时钟**（`SELECT now()`）计算，
    免疫 Python↔DB 时钟漂移（容器时钟快 ~1.7s 曾导致 TTL=1s 的 lease 立即过期）。
- 本轮不做：RPM / quota / cost / circuit / dynamic routing / runtime fallback。
- Known unrelated flaky：`test_sources_lane_execution.py::test_project_lane_rejects_*`
  2 例（单独跑通过，非 G2.3 语义，另行登记）。

### G2.4 Circuit Breaker & Runtime Fallback — ACCEPTED (2026-08-08)

```text
G2.4 Circuit Breaker & Runtime Fallback
Status: ACCEPTED

G2.4a Failure Classification + Circuit — Accepted
G2.4b Runtime Fallback                    — Accepted

Validated:
- 10 类 ProviderFailureClass；只有 NETWORK/TIMEOUT/RATE_LIMIT/PROVIDER_5XX 计入 circuit
- CAPACITY_EXHAUSTED / OUTPUT_INVALID / BUSINESS_VALIDATION / CANCELLED 不污染 circuit
- CircuitStateStore（InMemory + Postgres）与 CapabilityRegistry 分离
- OPEN → 不产生 transport call；cooldown → HALF_OPEN 受控 probe → 成功 CLOSED / 失败 OPEN
- FallbackPolicy：FALLBACK_ALLOWED 允许 5 类；STRICT 一律不 fallback
- fallback 只在 RoutingPlan.fallback_chain 内；cancel 不 fallback；capacity 先 bounded wait
- RoutingInvoker 编排：circuit → budget → adapter → classifier → circuit feedback → fallback
```

- 修正表述：**容量耗尽只是一个 Runtime Failure Class；是否 fallback 由 workload 的
  RoutingPolicy + FallbackPolicy 决定**，不是「容量满就换 Provider」。
- 链路：`Failure → FailureClassifier → FailureClass → FallbackPolicy → 允许 fallback？`
- G2.4a 实现：`ProviderFailureClass`（10 类）+ `FailureClassifier` +
  `CircuitStateStore`（`InMemoryCircuitStateStore` + `PostgresCircuitStateStore`）+
  `CircuitBreaker`（CLOSED/OPEN/HALF_OPEN，`now_provider` 注入单一时钟源）。
  - 只有 NETWORK/TIMEOUT/RATE_LIMIT/PROVIDER_5XX 计入 Provider availability failure。
  - CAPACITY_EXHAUSTED / OUTPUT_INVALID / BUSINESS_VALIDATION / CANCELLED 不污染 circuit。
  - OPEN → 不产生 transport call；cooldown 后受控 HALF_OPEN probe。
  - Circuit runtime state 与 CapabilityRegistry 分离。
- G2.4b 实现：`FallbackPolicy` + `RoutingInvoker` 编排（circuit → budget → adapter →
  classifier → circuit feedback → fallback），未传 fallback_policy 时保持 Legacy。
  - Fallback 只在 `RoutingPlan.fallback_chain` 内；STRICT 一律不 fallback。
  - FALLBACK_ALLOWED 第一版允许：NETWORK/TIMEOUT/RATE_LIMIT/PROVIDER_5XX/CAPACITY_EXHAUSTED。
  - AUTH/QUOTA/OUTPUT_INVALID/BUSINESS_VALIDATION/CANCELLED 禁止 fallback。
  - 每次 attempt 独立 `provider_call_id`，同一 fallback chain 共用 `route_execution_id`。
- **测试**：G2.4a 8 例 + G2.4b 10 例（含 best-effort timeout→fallback、strict 不
  fallback、capacity fallback 不污染 circuit、cancel 不 fallback、circuit OPEN 跳过
  provider、FallbackPolicy 表）；**PG circuit store 冒烟通过**（DB 时钟单源）。
- alembic：`a2b3c4d5e6f7_add_provider_circuit_state.py`。
- DB 时钟单源规则：DB 内 lease/lock/deadline/expiry 的生命周期判断一律用 **DB time**
  （Python 只做生成、DB 做判断会因时钟漂移失效）——G3 Worker lease 直接复用。

### G2.5 Provider Observability & Health — MVP Accepted

- **先观测，后评分**：不做综合 health score；先把每次 Provider attempt 变成可追踪、
  可统计、可解释的数据事实。
- **收缩决定**：G2.5c Health-aware routing / G2.6 Embed-Rerank / G2.7 全部暂缓（Post-MVP）。
  当前判断标准 = 「这个功能是不是完成 Gateway MVP 必需的」。
- **G2.5a Provider Attempt Telemetry**：
  - `ProviderAttemptRecord`（append-only；一次 route_execution_id 可对应多个
    provider_call_id——fallback chain 完整 trace）。
  - 覆盖完整 attempt 生命周期：success / failed / circuit_rejected /
    capacity_exhausted / no_adapter / cancelled；circuit/capacity → `transport_invoked=false`。
  - `ProviderAttemptRecorder`（InMemory + Postgres）**fail-open**：telemetry 写失败
    不影响业务（PROVIDER_CALL_METRIC_PERSIST_FAILED）。
  - **禁止记录 raw prompt / raw response / API key / full source**（只记 token/result
    用量 + task_type/model/schema 元数据）。
  - `RoutingInvoker` 每个 attempt 的 finally 记录；同 route 不同 provider_call_id。
- **G2.5b Provider Health Snapshot**：`build_health_snapshot` 从 records 聚合
  availability / latency / capacity / quality（**三失败维度分离**：
  transport_success_rate / availability_failure_rate / business_quality_failure_rate；
  capacity 独立统计）。`dimensions()` 输出可解释标签（healthy/degraded/saturated/normal），
  **无综合分**。Health 暂不改变正式 Router。
- **G2.5c Health-aware Routing Shadow**：`compare_health_routing` 只算不改
  （unhealthy 排除、saturated 降序），验证后再决定 Promote。
- **测试**：G2.5a 8 例 + G2.5b/c 6 例；**PG attempt recorder 冒烟通过**。
- alembic：`a3b4c5d6e7f8_add_provider_attempt_records.py`。
- 验收目标：attempt coverage 100% / fallback traceability 100% / duplicate
  provider_call_id 0 / metrics 失败不破坏业务 / circuit·capacity rejection transport 0 /
  availability 分类 100% / capacity·quality 不污染 availability / secret 0 持久化。

### G3 Execution Plane — ACCEPTED (2026-08-08)

```text
G3 Execution Plane
Status: ACCEPTED

Validated（InMemory 8 例 + PostgreSQL 验收）:
- Global Active Run Capacity：active 以 non-expired lease 为准（跨进程）
- Claim = 短原子事务（pg_advisory_xact_lock 串行化 capacity 检查 + claim + lease 创建）
- exactly-one owner（FOR UPDATE SKIP LOCKED + generation）
- Heartbeat 续租（DB clock）；Lease TTL 过期可 reclaim
- Fencing：stale worker 用旧 generation finalize → 写 0 行
- Crash recovery：expired lease → cancel→CANCELLED / 有剩余→requeue / 耗尽→FAILED
- lease leak = 0 / overshoot = 0（50 worker × cap5 → max_observed=5）
```

- `packages/execution/execution_lease.py`：`TaskExecutionLease`（lease_id/task_id/run_id/
  worker_id/execution_generation/acquired_at/heartbeat_at/expires_at/released_at）+
  `InMemoryExecutionLeaseStore`（测试）+ `PostgresExecutionLeaseStore`（**DB clock**）。
- `packages/execution/coordinator.py`：`ExecutionCoordinator`（claim/heartbeat/
  finalize-fenced/recover_expired）InMemory + Postgres。
- `packages/execution/worker.py`：`process_next`（recover → claim → execute → fenced finalize）。
- 增强现有 TaskService/Worker（不新建 Queue）；Run 生命周期保持 QUEUED→RUNNING→TERMINAL，
  retry 主要发生在 Task 层。
- Heartbeat 不写 RunEvent（只记录 WORKER_CLAIMED / WORKER_LEASE_EXPIRED / WORKER_RECLAIMED）。
- alembic：`a4b5c6d7e8f9_add_task_execution_leases.py`（task_jobs.execution_generation +
  task_execution_leases 表）。
- **PG 验收** `scripts/g3_execution_acceptance.py`：50 worker × cap5 →
  succeeded=50、failed_finalize=0、**max_observed=5、overshoot=0**、active_leases_after=0；
  fencing/crash/cancel/exhaustion 全 PASS。
- 关键修复：capacity 检查必须与 lease 创建在同一短事务内（否则并发 overshoot）；
  `result_json` 需 `CAST(... AS jsonb)` 处理 dict 参数。

### Gateway MVP Closeout — ACCEPTED (2026-08-08)

```text
Gateway MVP = ACCEPTED

G1 Research Control Plane              ✅
G2 Provider Gateway Core               ✅
G2-M1 LLM Gateway Production Wiring    ✅
G2-M2 Real Telemetry Wiring            ✅
G2-M3 End-to-End Gateway Acceptance    ✅
```

- **M1 — LLM 正式走 Gateway**：`LLMCapabilityService.generate_json/generate_text`
  （off/shadow/gateway，与 Search 对称）；`build_llm_adapter_registry`
  （DeepSeek + OpenRouter stub，client 可注入）；`build_gateway_aware_llm_client`
  （drop-in client）。**接线**：`tooling/llm_agents.py::call_tooling_json` 在
  `LLM_MODE=gateway` 时走 Gateway facade（STRICT → DeepSeek only，行为不变）。
  - STRICT（planning/evidence/claim/draft/synthesis/repair）→ DeepSeek only。
  - best-effort（query_expansion / search_phrase_generation）→ DeepSeek→OpenRouter。
  - 测试：`test_capability_llm_gateway.py` 7 例（off/shadow/gateway、strict/fallback、
    circuit skip、telemetry、token usage）。
- **M2 — Telemetry 挂上**：Search + LLM 工厂均接受 `recorder`（注入
  PostgresProviderAttemptRecorder 后自动落库）。Health Snapshot 保持 observe-only。
- **M3 — 端到端验收**：`scripts/gateway_mvp_acceptance.py`
  `Gateway MVP = ACCEPTED`（Search normal/fallback/all-error + LLM strict/best-effort/
  strict-fail + telemetry fallback chain 完整 trace）。
- **冻结声明**：Gateway MVP 完成，**停止 Gateway 主动扩展**；后续问题驱动扩展
  （DeepSeek 常满 → health-aware routing；Reranker OOM → EMBED/RERANK；OpenRouter
  rate limit → RPM Budget）。主线回到 Research/Evidence/Report Quality。

## 评分体系精简（2026-08-09）—— 4 层单一链路重构

**目标**：4 个评分环节（source/evidence/claim匹配/run汇总）过度复杂、重复计算、多字段"算了没人用"。
三个审计 agent 交叉验证 + 用户确认（源码单点绕过字节码 + citation_integrity 真实化）。

**Phase 1 安全清理**（零行为变化）：
- 删 `score_source_quality_with_model`（rerankers.py，零调用方死代码）
- 删死列 `ResearchGraphEvidenceRecord.source_ids_json` / `ResearchGraphClaimRecord.claim_family`
  + 2 处重复 `payload_json`（entities.py）
- 删 dossier `_render_source_quality_v2` + glossary（context 从不填充，dead path）
- 删 phase3 `secondary_support` 死分支 + `source_map` 未用变量

**Phase 2 核心精简**：
- **source_quality.py 单分数重构**：去 `tier` 输入（计划常量回灌，run16 全 B 无判别力）；
  `SourceQualityV2` 删 publisher_authority/auditability/credibility_label/reason；
  `_tier_from_credibility` 派生 tier（≥0.72=A/≥0.55=B/≥0.35=C/else D，**D 档死代码被激活**）；
  `derive_usage_role` 去 tier、改 credibility 阈值。
- **score_sources 单点化（修 R1 双算）**：`score_sources_single_point` 用活代码遍历评分；
  collect_sources 删重复 assess（只存原始字段）；nodes.py 改调单点，**绕过字节码冻结评分器**。
- **evidence 精简**：support_strength 权威 overwrite（原 max 双算）；`_build_evidence_quality_v2_for_graph`
  输出仅 {evidence_type, proof_strength, not_sufficient_for, inherited_source_quality}；
  删 quality_score/claim_relevance/evidence_specificity/citation_integrity/primary_support_eligible；
  `_proof_strength_from_support` 只用 support_strength+usage_role+evidence_type。
- **claim 去死门**：删 citation_integrity<0.45 / credibility<0.35 两死分支。
- **run 汇总真实化**：citation_integrity 改为"被引用证据可解析 source_url 比例"（原 0.96/0.82 硬编码）；
  final_score 加权 0.4/0.3/0.2/0.1。

**Phase 2 发现并修复的 2 个真实 bug**：
- 招投标源（ggzy.hefei.gov.cn）历史日期被 `derive_usage_role` 一刀切 context_only →
  修正 historical 分支只排除商业媒体（招投标/政策原文是历史档案性质，保留）。
- 新华网/人民网等央媒被 classify_source_role 判 aggregator（cred 0.3）→ 加
  `_AUTHORITATIVE_MEDIA_MARKERS` + publisher_authority 档位 0.68。

**Phase 3 收尾**：删孤儿 `_quality_reason`/`_credibility_label`/`_citation_integrity_for_graph_evidence`/
`_evidence_specificity_score`；异常兜底 dict 对齐新 schema；终扫零残留。

**验证**：
- 新评分：gov.cn→cred 0.866/tier A/primary；招投标→0.560/B/supporting；新华网→0.548/C；
  知乎→0.364/C/exclude（**D 档出现，低质源正确降级**）。
- 59 相关测试 passed + ruff 全干净。`test_verify_claims_provider_backed_*` 2 个为**预存失败**
  （claim_support_matrix 结构 + live provider flaky，非本次引入）。

**support_status 规则化（2026-08-09）—— coverage 0 → 0.7**：
- 根因：support_status 由 LLM 判定（build_verifier_prompts），LLM 常"给高分却判 unsupported"
  （run 17：c1 support_score=0.98 但 unsupported）——状态与分数矛盾。
- 修复（real_nodes.py verify_claims 包装层）：`support_status` 改为**规则判定**——
  eligible 证据数 ≥ required_count → supported；≥1 → partially；0 → unsupported；
  `support_score` 改为 eligible 证据平均 support_strength（单一数字来源）；LLM 只产 notes。
  `_required_evidence_count` 解析 support_requirement（"至少2条"→2）。
- 端到端验证（run 18，低空 query，真实 provider）：
  - **evidence_coverage 0 → 0.7**（2 supported / 2 unsupported）；final_score 0.34 → 0.68。
  - 12 节点全 succeeded；decision=ADD_EVIDENCE（2 个无证据 claim 诚实 unsupported → chief_gate 要求补证，
    非崩溃）。
  - 新评分持续生效：source 分档（A 37/B 7/C 23/D 2）、strong 证据 9→54、context_only 48%→37%。
- claim 覆盖诊断：claim 常一 claim 覆盖多维度（政策+空域+基建），企业订单/适航认证等证据稀缺维度
  生成"现有证据未提供…无法验证"的**诚实 claim**（不编造）。18 claim 中核心维度覆盖，但无证据维度
  触发补证循环。

**Gap 补证 + 方案 A 降级（2026-08-09）—— 推进报告生成**：
- **Gap 补证修复**（第二轮搜索找企业订单/行业报告）：
  - `_build_gap_targeted_rounds` 补 4 个缺失 family 模板（industry_research/broker_research/
    operator_data/certification_database）。
  - 修 target 解析：`<family>_evidence` 后缀剥离（company_disclosure_evidence→company_disclosure）。
  - 修 `target_location` 污染：被编译提取器误设为完整 query 前截（109 字符）→ >30 字符丢弃
    location 前缀，只用 base_query+suffix。
  - `_enrich_round_phrases` 跳过 `_gap_targeted` 轮（不重写 gap 定向短语）。
  - `_gap_core_topic` 加 `_compact_topic` 压缩（截到"是否"前）。
  - 验证：gap 轮短语从 query 变体 → `低空经济 上市公司 公告 / 行业 报告 白皮书 / 券商 研报`。
- **方案 A 降级 PASS**（补证轮尽后按 coverage 阈值出报告）：
  - 根因：`_impl` 字节码在 loop 预算尽后设 HUMAN_REVIEW，run 卡死补证循环。
  - 修复：`chief_gate_provider_backed` 在 loop 已尽 + claim coverage ≥0.5 时降级 PASS；
    用 verifications 的 support_status 算覆盖率（claims[].supported 不可靠）。
  - 质量保护：真实 blocker（contradiction/hallucination/fabrication）或超半数 claim 单源
    → 仍 HUMAN_REVIEW；unsupported_claim/source_family_mismatch（family 命名差异）不阻断。
  - 验证：run 24 数据（coverage 0.62, 低多样 32%）→ PASS；9 个 gate 测试全过。
- **修复**：`research_graph_claims.support_requirement` 列 varchar(32)→varchar(128)
  （第二轮长 support_requirement 触发 StringDataRightTruncation）。
- **端到端**：run 24 完整跑通 24 节点（两轮 + human_review）；run 25/26 因外部搜索超时中断
  （AnySearch 连接关闭，非代码 bug）。核心链路（补证→降级→出报告）逻辑已验证。

**提速 + 报告生成打通（2026-08-09）—— 首个完整报告**：
- **瓶颈定位**：score_sources 非瓶颈（纯规则）；真瓶颈是 `_evidence_deep_backfill`
  （10 维度 × 12 短语 = 120 次串行搜索）和 `_extract_atomic_evidence`（100+ 源串行 LLM）。
- **并行化**：两者都改 `ThreadPoolExecutor(6)` 并发（每任务各自建 provider/client，线程安全）。
  run 从 ~15 分钟 → ~8 分钟（**提速 ~40%**）。
- **首个完整报告（run 27）**：25 节点全 succeeded + `finalize_report`，
  `decision=PASS`（方案 A 降级），**level_2 初步研究报告生成**（3 claims / 117 sources /
  145 evidence）。报告含执行摘要/方法与口径/政策主线分析，诚实标注证据不足维度。
- **报告变量名清理**：run 27 报告泄漏内部 ID（`[ev_atomic_src_005_0]` 引用标注、
  `<!-- claim_ids -->` 注释块、`obl_statistics_data`）。修复 `build_editor1_draft_prompts`：
  规则 12 绝对禁止内部标识符进正文（引用用"根据新华网2026年报道"可读形式），
  规则 1 改"claim_ids/evidence_ids 只进 JSON 结构不进正文"。
- **注意**：run 28 因外部搜索超时中断（AnySearch provider 波动，非代码 bug）；外部搜索
  稳定性是剩余风险（第二轮补证搜索依赖）。

**搜索失败根因修复（2026-08-09）—— RemoteDisconnected 漏捕获**：
- **现象**：run 25/26/28 第二轮 collect_sources 报 "Remote end closed connection without response"，
  整个 run 失败。
- **根因（实证）**：`http.client.RemoteDisconnected` **不是 URLError 子类**（是 OSError→
  ConnectionResetError），而 `_default_anysearch_transport`/`_default_tavily_transport` 只捕获
  HTTPError/URLError → 异常漏到上层，`_search_with_retry` 无法识别为可重试错误。
  且 `CAPABILITY_GATEWAY_ENABLED=False`，搜索走 legacy（无网关 fallback/circuit 保护）。
- **修复**：两个 transport 补 `except OSError` → 转 `SourceAnySearchError(retryable=True)` /
  `SourceTavilyError(retryable=True)`，让 `_search_with_retry` 重试而非失败。
  验证：模拟 RemoteDisconnected → 正确转 retryable；41 相关测试通过。
- **可选后续**：`CAPABILITY_GATEWAY_ENABLED=True` 可启用网关 fallback（AnySearch→Tavily）
  + circuit 保护，但需先确认 gateway search_mode 行为。

**补证质量修复（2026-08-10）—— 低质证据过滤 + c_suppl 去重**：
- **问题**：第二轮补证后 claims 从 4 → 18，但新增多为 unsupported（coverage 稀释到 0.22）。
  两个根因：
  1. **LLM 把低质源证据挂到官方 claim 上**（c2/c3 挂 commercial_media 证据但要求
     official_policy）→ 永远无法 supported。
  2. **c_suppl_1 重复 7 次**（LLM 跨 batch 返回相同 id，去重只查 existing 没查本批）。
- **修复**：
  1. `build_claims_provider_backed` 过滤挂到 claim 上的低质 evidence（usage_role ∈
     {context_only, exclude_from_primary_evidence} 移除）——claim 只挂合格证据，无合格
     证据的诚实 unsupported（触发补证）。
  2. c_suppl 去重加 `batch_claim_ids` 集合（查 existing + 本批）。
- **验证（run 31）**：claims 18 → 7 无重复；unsupported 均诚实（1 条证据）；链路稳定
  （搜索不中断、无崩溃）。coverage 0.29 < 0.5 → 诚实 HUMAN_REVIEW（低空 query 的公司披露/
  统计证据确实稀缺，是证据供给问题非代码 bug）。
- **结论**：系统行为现在正确且诚实——证据充分时出报告（run 27 level_2），证据不足时
  人工介入而非编造。

**原子抽取输入缩小（2026-08-10）—— chunk 优先于全文**：
- **问题（用户指出）**：evidence 应从 chunk 来，但 `_source_fulltext` 优先取 `full_text`
  （整页全文，p50 2319 / max 64529 字符），chunk 检索注入的 `raw_text`（top-12 chunk 拼接，
  ~5000 字符）被忽略 → LLM 输入过大（成本高）+ 信号分散。
- **修复**：`_source_fulltext` 字段优先级反转——`raw_text`（chunk）优先，`full_text` 仅
  fallback。实测：src_011 从 34011 → 5000，src_015 从 5656 → 4241。
- **验证**：enrich 测试通过；前 20 源中 4 个有 chunk 的全用 chunk。
- **剩余**：只有 ~20% 源有 chunk（`_inject_chunk_text_into_sources` 只注入 top-12 chunk 到
  部分源），其余仍 fallback 全文。下一步可扩大 chunk 注入覆盖面。

**Evidence 构建架构对齐（2026-08-10）—— 每个粗排 source 都 chunk + 精排**：
- **用户设计澄清**：evidence 应从"粗排选中的每个 source 原文 → 每个 source 都 chunk 处理
  → 每个 chunk 过 reranker 精排 → 构建 evidence"而来，而非只 top-24 chunk 落入少数源。
- **改动**：
  1. `rank_retrieved_sources`：`rerank_chunks_llm(top_k=max(rerank_top_k, len(chunks)))`——
     返回**所有粗排 source 的 chunk**（不只 top-24），rerank 只影响排序。验证：30 源 →
     30 chunks 全覆盖。
  2. `_inject_chunk_text_into_sources`：每个 source 注入**自己的全部 chunk**（cap 6000，
     不再 top-12 限制）——让原子抽取基于精排片段而非全文。
- **验证**：retrieval_rank 12 测试通过；30 源 chunk 全覆盖。
- **效果**：有 chunk 的源 LLM 输入从全文（max 6.4 万字）→ 精排片段（~6000 字符），
  成本降 + 信号集中。deep backfill 新源自带定向 raw_text，同样走片段。

## G4 Full-stack Load Acceptance — Network Layer (2026-08-08)

```text
G4  Full-stack Load Acceptance
  ├─ Network Layer        ✅ PASS
  ├─ Execution Plane Load ✅ PASS
  └─ Provider Plane Load  ✅ PASS（下方）
```

- `scripts/gateway_network_load_acceptance.py`（真实 HTTP + 真实 PG，独立测试库
  `invest_agent_g4_load`，uvicorn 子进程 + httpx async 并发）：
  1. **S1 solo baseline**：POST→202 / GET→200 / cancel→200，solo submit ~118ms。
  2. **S2 burst submission**：cap=40，60 并发 → **恰好 40×202 / 20×503**，无 5xx；
     **peak_db_connections=17**（app 默认池 5+10=15 + 采样）。
     吞吐 **76.6 rps**（wall 0.78s），p50=545ms / p95=748ms（延迟主要在连接池排队）。
  3. **S3 idempotency replay**：同 key 20 并发 → 恰好 1 run，19 replay / 1 create，DB 无重复。
  4. **S4 poll storm**：200 并发 GET /runs+events → 全 200，吞吐 **112.5 rps**。
  5. **S5 cancel burst**：10 并发 cancel QUEUED → 全 200，completed=10，capacity -10。
  6. **S6 capacity reclaim**：queued=31，15 并发 → 恰好 9×202 / 6×503，边界精确回 40。
  7. **S7 leak & integrity**：pool.checkedout=0，孤儿 lease=0，幂等重复=0。
- 结论：控制面在网络层并发下**正确性全过**。诚实发现：默认连接池（5+10=15）
  是并发吞吐的真实瓶颈（高并发延迟主要花在池排队），生产可按预期峰值调
  `pool_size / max_overflow`（如 `DATABASE_URL?pool_size=20&max_overflow=20`）。

## G4 Full-stack Load Acceptance — Execution Plane Load (2026-08-08)

- `scripts/gateway_execution_load_acceptance.py`（真实 PG + DB clock）：
  1. **E1 sustained_drain**：200 tasks × 50 worker × cap5 持续 drain →
     **max_observed=5、overshoot=0**、全 succeeded、**drain 吞吐 ~80 tps**；
     worker 在 finalize 前 heartbeat（心跳负载）。claim p50~8ms / p95~20ms。
  2. **E2 recovery_storm**：40 tasks 全部 claim → SQL 强制批量过期 →
     **8 线程并发 recover_expired** → 每个 task **恰好恢复一次**（duplicate=0）、
     全 requeue、回收后容量可再 claim。
  3. **E3 concurrent_fencing**：30 tasks claim(gen1) → 过期 → recover → claim(gen2)，
     30 stale + 30 new **并发 finalize** → stale 全拒 / new 全成 /
     **stale_artifact_publish=0**。
  4. **E4 leak**：孤儿 lease=0、pool.checkedout=0。
- **压测发现并修复一个真实并发 bug**：`PostgresExecutionCoordinator.recover_expired`
  原实现「先 SELECT 再 UPDATE」有 TOCTOU 竞态——8 线程 recovery 风暴下
  **40 个 task 里 35 个被重复恢复**。修复 = 状态迁移改用**条件 UPDATE**
  （`UPDATE ... WHERE status='running'` + rowcount），并发下恰好一个 winner，
  其余 rollback + release。E2 dup **35 → 0**；`g3_execution_acceptance` 与
  `tests/test_execution.py`（8 例）全部仍 PASS（无回归）。
- 结论：Execution Plane 在持续负载 + 恢复风暴 + fencing 风暴下正确性全过；
  并发 recovery 现在是恰好一次。

## G4 Full-stack Load Acceptance — Provider Plane Load (2026-08-08)

- `scripts/gateway_provider_load_acceptance.py`（deterministic fake provider +
  真实 PG budget/circuit/telemetry，走 RoutingInvoker 全编排）：
  1. **P1 budget_under_load**：primary max_concurrency=5，50 并发 invoke →
     **max_observed=5、overshoot=0**、全 success、permit 无泄漏；吞吐 **38 invokes/s**
     （延迟主要是 50 并发争 5 个 permit 的排队，是预算的正确行为）。
  2. **P2 circuit_open_recover**：primary 连续 NETWORK 失败 → 3 次后 **OPEN** →
     拒绝期 5 次 **circuit_rejected**（不产生 transport call）→ cooldown 后
     **HALF_OPEN probe 成功 → CLOSED**（probe 走 primary 非 fallback）。
  3. **P3 fallback_under_concurrency**：primary 失败、fallback success，30 并发 →
     全 success 走 fallback；telemetry：fallback_success=30、fallback_used=30、
     primary failed/rejected=30。
  4. **P4 non_availability_no_circuit**：BUSINESS_VALIDATION ×5 → 不 fallback、
     **不污染 circuit**（保持 CLOSED、allow=True）。
  5. **P5 leak**：permit 无活动、pool.checkedout=0。
- 结论：Provider Plane 在并发负载下预算不过发、circuit 状态机完整、fallback 链可靠、
  非可用性失败不误伤 circuit、telemetry 一致。

## Evidence 层精排 chunk 直接作 evidence（2026-08-10）—— 砍原子事实抽取

**用户核心指示**：不抽原子事实，检索词检索回来的精排 chunk 直接作 evidence，editor1/editor2 直接消费写报告。

- **`_build_chunk_evidence_from_state`（新）**：每个精排 chunk → 一条 evidence（evidence_id=chunk_id，text=chunk 全文，带 source_id/source_family/rerank_score）。deep-backfill 新源无 chunk 时回退 raw_text。
- **`build_evidence`** 砍掉 `_extract_atomic_evidence`（LLM 原子抽取 + 并行线程池），字节码 base evidence 弃用。

## Evidence 按 claim slot 定向检索 + 数量控制（2026-08-10）

**用户澄清（核心）**：控制的是"检索回来的 evidence 数量"（少而精），不是构建后裁剪。
证据构建 = **claim slot（证据槽位）→ LLM 构建检索词 → 定向检索 → 每 slot 限量**。

- **`_build_slot_search_rounds`（新）**：LLM 按 claim slot 生成定向检索词（输入 slot 的
  research_question + key_fields + source_family，输出 2-3 条检索词/槽位），
  失败回退 `_SPEC_FIRST_PASS_FAMILY_TEMPLATES`。28 slots（12 required + 16 optional）。
- **`_build_chunk_evidence_from_state` 改造**：精排 chunk 按 source_family 匹配 slot，
  只保留 required/critical slot，每 slot 按 rerank_score 限 top-K（`_EVIDENCE_TOP_K_PER_SLOT=3`），
  evidence 带 `supports_slot_ids`。100 chunk → 12 evidence（每 slot top-3）。
- **collect_sources slot 轮优先**：slot 定向轮不受 max_rounds 切片截断，先执行
  （真实 run：18 slot 轮先跑）。
- **`_search_results_limit_for_round`**：slot 轮每轮返回量收敛 `_SLOT_SEARCH_RESULTS_LIMIT=3`。
- **gate slot 级覆盖**：`_dimension_coverage_report` 判定维度 covered = 该维度任一
  required slot 有 ≥1 条匹配 evidence（evidence 带 supports_slot_ids）。
- **数量控制效果**：真实 run 442 evidence → slot 限量后 ~28-84 条（验证中）。

## 两阶段搜索收敛（2026-08-11）—— 固定维度基本搜索 + 未覆盖维度深度补搜

**用户指示**：搜索收敛为两段式，一次到位，用 AnySearch。

- **collect 两段式**：固定维度基本搜索（taxonomy 10 base+4 conditional 定向词，每维一轮）→
  覆盖检查（source required family）→ 未覆盖维度深度补搜（`_build_second_pass_rounds`，≤6 轮）。
  抽 `_run_search_round` helper 复用两段。
- **删除 `_build_slot_search_rounds`**（LLM 按 claim slot 生成检索词——用户否决），
  `_inject_spec_driven_first_pass_rounds` 回退 family 模板。
- **每轮短语收敛到 2 个**（`_enrich_round_phrases`），搜索请求 66→26 次。
- **一次到位**：`max_loop_count` 默认 0 → gate 永不 ADD_EVIDENCE，直接 PASS/标注
  （gate 逻辑确认：`_max_loop=0` 时 ratio≥0.5→PASS、<0.5→HUMAN_REVIEW）。
- **AnySearch primary**：`.env` 显式 `SEARCH_DISCOVERY_PROVIDER=anysearch`。
- **reranker 健康检查**（`reranker_health_check`）：vLLM 不可达快速回退 deterministic，
  修复 parse_sources 卡死（之前逐 chunk 30s 超时）。
- **真实 run 验证（v3，300s）**：26 次搜索 / 90 source / 57 evidence / 纯 AnySearch /
  PASS（10/14 维）/ 报告 5375 字符。vs 收敛前 48 分钟 / 66 搜索 / 442 evidence。
- **`_evidence_react_backfill`** 同样改用 chunk-evidence。
- **真实端到端验证（2026-08-10）**：真实 Tavily 搜索 149 source → 932 chunk → 442 条 chunk evidence（全 direct_support，evaluator_mode=chunk_evidence_v1，无原子抽取）→ 第一轮 gate ADD_EVIDENCE（13/14 维）→ loop 补证 → 第二轮 gate PASS（14/14 维）→ 真实 DeepSeek editor1 产出 4436 字符完整研报（执行摘要/政策主线/地方对比表格/传导链条/公司披露/行业数据/风险/结论/来源说明）。report_id=1，evidence_coverage=1.0，final_score=0.96。
- **遗留死代码**：`_llm_extract_atomic_facts`/`_deterministic_atomic_facts`/`_make_atomic_evidence_item`（互引，无 live 调用，可后续清理）。

## 测试翻新到 evidence 视角（2026-08-10）

- `test_research_harness_graph.py` 18 个失败（初始全量）→ 已修复 13+，剩余 provider_backed 断言翻新中。
- **生产 bug 修复（6 个）**：
  1. `_dimension_coverage_report` 读错字段（`required_source_families` → `source_families` + canonical 归一化）。
  2. `max_loop_count=0` 被 `or 1` 抬成 1（无 loop 预算也先补一轮）。
  3. `human_review` 节点 `dict(drafts)[-1]` 崩溃 → `list(...)[-1]`。
  4. shadow gate 无条件放行 → 统一维度覆盖判定。
  5. `retrieval_bridge` 引用已删字段（`index_text`/`chunk_level`/`embedding_vector`）→ chunk 持久化崩溃。
  6. `plan_task` 收口覆盖 `spec_driven_first_pass` 元数据。

## Evidence Quality Audit (2026-08-08) — 首个真实端到端证据质量审计

`scripts/evidence_quality_audit.py`：对 3 个真实研究 query（低空经济 / 数据要素 / 半导体）
跑 graph-runtime pipeline（真实搜索 + LLM），从 run checkpoint 提取 evidence，做结构性
打分 + 语义审计（本地 reranker 0-4 相关性 + DeepSeek judge support/authority）。

**结果（3 query 汇总）：**
- **关键阻塞**：3 个 run **全部在 `verify_claims` 节点失败**（SQLAlchemy
  `Multiple rows were found`，编译字节码 `_real_nodes_impl` 内）→ pipeline 无法返回完整报告。
  evidence 已构建（52-66 条/query）但只在 checkpoint，不随响应返回。**需单独排查修复。**
- **语义质量整体较好**：authority A/B 占比 80-100%（官方/权威媒体）；support rate 0.9-1.0
  但**以 partial 为主**（证据权威但多为泛述，未精确验证 query 子维度）；mean relevance 2.7-3.5/4。
- **结构性弱点**：
  - `locator_ratio=0`：evidence 不带 chunk 定位（无具体段落级引用）。
  - `orphan_evidence_ratio≈0.77-0.82`：大量被采集 evidence 未被任何 claim 引用
    （低空 65 条仅 12 条被引用；数据要素 66 条、半导体 52 条类似）。
  - `citation_integrity=0.85`（pipeline 自带评分，全常量=启发式非实测）。
- 结论：**证据来源权威、相关性尚可，但"泛而不用"（高 orphan）+ 弱证明强度
  （63% context_only）+ 无段落定位**，是 evidence 质量的主要短板；且 verify_claims
  阻塞让报告根本回不来。方向：修 verify_claims → 降 orphan（claim 聚焦采集）→
  证据带 locator。

## Rerank Query 覆盖修复 (2026-08-08) — 精排 query 覆盖全部搜索词

**问题**：`_build_rerank_query` 旧实现只取 `search_phrases[:6]`，实测 run_1（低空经济）
plan 有 **60 个搜索词**（5 轮 search_rounds + 15 个 dimension caliber_terms），rerank query
只覆盖前 6 个且多为 query 整句重复变体 → **54 个搜索词没进精排 query**，各维度独特词
（通用航空/eVTOL/无人机/产业边界/中标…）全漏，相关证据可能被降权。

**修复**（`packages/research_harness/retrieval_rank.py`，方案 A）：
- 归一化 + 精确去重全部 phrase（不只前 6）。
- `_phrase_new_info`：phrase 含 query（整句变体）→ 只取 delta 词段；短短语（caliber_terms）
  → 整体加入（清洗标点）；否则取 query 未覆盖词段。
- 按信息长度升序优先加入（短独特词先放），上限 `_RERANK_QUERY_MAX_CHARS=900`
  （vLLM max_len 1536 token 内）。
- 实测：run_1 的 60 短语 → 新 query 386 字符，通用航空/eVTOL/无人机/产业边界/中标/上市公司年报/
  cninfo 披露 全覆盖，无标点噪音；旧 query 369 字符漏 6+ 关键词。
- 排序验证（真实 reranker）：新 query 把「上市公司年报」证据 bucket 2→3、无关证据 0.079→0.013。

**测试**：`tests/test_retrieval_rank.py` 新增 2 例（独特词全覆盖 / query 变体去重不堆积）；
`test_retrieval_rank.py + test_rag_retrieval.py + test_rag_chunk_quality.py` 19 passed，ruff 干净。

**粗排同步修复**（`coarse_rank_bm25_vector_rrf`）：BM25 旧实现只 `search_phrases[:8]`、向量路只嵌
query ——同样漏维度词。改为**两路都用覆盖 query**（复用 `_build_rerank_query` 产物）。实测
run_1 的 23 sources + 60 短语：top-8 把 **上市公司/中标**（交易/披露类证据）提进覆盖，
丢掉泛化的 产业边界/订单——更偏好具体证据类源。新增 `test_coarse_rank_covers_late_phrase_terms`。

**采集缺口（关键发现）**：run_1 的 23 个来源语料**本身缺** query 子维度——企业订单/地方试点/
项目公示/统计公报/年报/竞争格局/招商 全无。排序（coarse+rerank）已覆盖语料里所有维度词，
但**搜索没采到这些维度的具体证据源** → 再好的排序也补不了。这是下一步真正要修的瓶颈
（search 采集/round 结构/源质量门槛），不是排序问题。

## 采集层修复：搜索轮次维度定向 (2026-08-08)

**根因**：run_1 的 `search_events` 显示实际执行的 8 次搜索**全是 query 整句重复变体**
（rounds 0-3 的 2+2+2+2），维度定向短语（round 4 的 上市公司年报/交易所公告等）一次都没执行。
原因：搜索 builder LLM 把整句 query 当 `search_phrases` 填进有 `target_dimensions` 的轮次，
而 `_map_search_groups_to_rounds` 的 fallback 只对"无轮覆盖"的维度补轮（这些轮已声称覆盖了维度）→
**搜索预算全浪费在 query 重复上，企业订单/招投标/统计公报等维度一个都没搜到**。

**修复**（`packages/research_harness/plan_semantic.py`）：
- `_enrich_round_phrases`：对每轮，用其 `target_dimensions` 的**短 caliber_terms** 或
  **search_key_fields**（维度自身 → base taxonomy）派生定向短语；现有短语全是 query 变体
  （标点无关检测）→ **替换**，否则合并。
- `_dim_search_terms`：search_key_fields 里**优先取有 `_SEARCH_FIELD_TERMS` 映射的证据类型字段**
  （招标状态→招标 中标、投资金额→投资 金额、市场份额→市场份额 占有率），再补原始字段。
- 实测 run_1 修复后轮次：round 1 含 **"招标 中标 / 投资 金额 / 项目 阶段"**，round 2 含
  竞争格局/商业模式，round 4 保留 上市公司年报/交易所公告/cninfo 披露——旧版这些全无。
- 覆盖证据类型：中标/订单/项目/试点/基础设施/上市公司/年报/竞争格局/投资 全有。
  仍缺 统计公报/招投标字面/收入（taxonomy 无对应字段映射，后续补）。

**测试**：`tests/test_research_harness_plan_semantic.py` +2（query 变体替换 / key_fields
优先证据类型字段）；plan_semantic + retrieval_rank 21 passed，ruff 干净。

**真跑验证（半导体 query，run 7）——成功**：
- **sources 24 → 71**（维度定向搜索采集面大幅拓宽）；source 族含 tender_procurement×4 /
  company_disclosure×2 / official_statistics×1。
- 证据类型覆盖：**中标/招投标/招标/订单/合同/客户验证/收入/营收/年报/公告/采购/项目/
  产值/产量/验收 全有**，仅 统计公报 缺。
- 62 条 evidence：tender_procurement 9 + company_disclosure 1 + official_statistics 1。
- 执行到的搜索全部维度定向：`半导体设备材料 国产化 招投标 中标 客户验证 上市公司 收入结构`
  / `... 招标 中标` / `上市公司 年报` / `收入` / `毛利率 利润` 等（旧版全是 query 整句）。

**关键改动链**（`real_nodes.py` + `plan_semantic.py`）：
1. `_compact_topic` / `_short_topic`：query 压缩为紧凑主题（截到 是否/能否 前）。
2. `plan_task_provider_backed` 收口：plan 定稿前对 search_rounds 统一 `_enrich_round_phrases`
   （覆盖 caliber/rewrite/spec/gap 多路径），保证被执行的轮次是维度短语。
3. `_build_spec_driven_first_pass_rounds` / `_build_diverse_search_phrases` 用紧凑 topic。

**剩余**：verify_claims 仍是 run 完成阻塞（独立任务）。

**10 个基础维度 taxonomy 审计 + 补 统计公报（2026-08-08）**：
- 审计 `research_taxonomy.BASE_DIMENSIONS` 10 个基础维度的 `search_key_fields` → `_SEARCH_FIELD_TERMS`
  映射。发现 **market_scale 缺 统计公报**（统计类证据采不到）。
- 补：`_SEARCH_FIELD_TERMS` 加 `"统计公报"→"统计 公报 数据"`、`"统计数据"→"统计 公报 产值"`；
  market_scale 的 search_key_fields 首位插入 `"统计公报"`。
- 验证：10 个维度 `_dim_search_terms` / `_enrich_round_phrases` 全部产出可用定向短语——
  industry_scope→产品 品类、policy_regulation→补贴 基金 示范区、**market_scale→统计 公报 数据**、
  industry_chain→产业链 环节、supply_competition→市场份额、demand_scenarios→场景名称、
  technology_product→认证 资质、project_execution→投资 金额、business_economics→盈利模式 收费、
  risk_constraints→风险 安全。**10/10 满足搜索需要。**
- 测试：plan_semantic + retrieval_rank + rag_retrieval 26 passed，ruff 干净。

**base-10 补轮（2026-08-08）——确保 10 个基础维度都有搜索轮**：
- 根因：10 个基础维度全在 `dimension_plan`，但实际 `search_rounds` 由编译 planner 的 LLM
  `search_groups` 决定，LLM 常只覆盖 6 个基础维度（run_7 漏 market_scale/industry_chain/
  supply_competition/technology_product/risk_constraints）。plan_semantic 的 base-10 fallback
  能补全，但实际路径没用它。
- 修复：`ensure_base_dimension_rounds`（plan_semantic）+ 收口调用（real_nodes），未覆盖的
  基础维度补独立轮并插在锚点轮后（小预算内先执行）；`_enrich_round_phrases` dim 解析支持
  canonical type 匹配（`d_market_scale` ↔ plan id `market_scale`）。
- 验证（模拟 run_7 plan）：11 轮、**10/10 基础维度覆盖**；新增轮短语紧凑维度定向——
  `d_market_scale → 半导体设备和材料国产替代 统计 公报 数据`、
  `d_supply_competition → ... 竞争格局 / 市场份额`、`d_risk_constraints → ... 风险 / 瓶颈`。
- 测试：+1 `test_ensure_base_dimension_rounds_covers_all_10_base_dims`；27 passed，ruff 干净。

**⚠️ 运维告警：graph run 压垮 PostgreSQL → 已定位并修复（2026-08-08）**：
- 根因（Workflow 3-agent 诊断 + 实测）：**不是单 run 泄漏**。单 run 连接峰值仅 2
  （`diag_graph_full.py` 实测）。真因：`get_engine` 只传 `pool_pre_ping=True`，走 SQLAlchemy
  默认 `pool_size=5, max_overflow=10`（15/进程）、`pool_timeout=30`、**无 pool_recycle**；
  uvicorn+worker 多进程各持一池叠加；且 AdmissionController 只 cap QUEUED 不强制 running
  → 并发 run 超过池上限 30s 超时。估算当前安全并发 ~5-8 run。
- 修复：`packages/db/session.py` 显式 `pool_size=5, max_overflow=5, pool_timeout=60,
  pool_recycle=1800`（10/进程，recycle 防 PG 重启 stale）；`packages/core/config.py` 加
  `DB_POOL_SIZE/DB_POOL_MAX_OVERFLOW/DB_POOL_TIMEOUT/DB_POOL_RECYCLE` 环境可调。
  修后 ~85/10 ≈ 8 进程余量，20+ 并发 run 安全。无需 PgBouncer（单实例足矣，水平扩展再加）。
- 验证：engine pool 生效（5+5/60s/1800s）；DB 相关测试 23 passed。
- 关联放大器（后续可优化）：`RunEventRecorder.record` 每次事件开 session；
  `/deep-research/analyze` 是 sync 路由走线程池，池须匹配并发。

## verify_claims 阻塞修复（2026-08-09）—— 首个完整跑通的真实 run

**verify_claims MultipleResultsFound 根因定位并修复**：
- 现象：run 1/5/6/7/11 全部在 verify_claims 失败（`Multiple rows were found`）。
- 根因（复现验证）：`persistence.py::_upsert` 用 `.one_or_none()` 查已有行，但历史数据存在
  `(run_id, key)` 重复行（多次 persist_state 叠加 + `_persist_claim_evidence_links` 的
  `delete(synchronize_session=False)` 不清 session pending）→ 命中多行抛 MultipleResultsFound。
- 修复：
  1. `_upsert` 改为 `session.flush()` 后 `.first()`（幂等复用已有行；flush 让同 session pending
     落库，避免 commit 撞唯一约束）。
  2. `_persist_claim_evidence_links` delete 改 `synchronize_session="fetch"`。
  3. 清理历史重复（review_issues -31 / claim_evidence_links -115）+ 唯一约束
     `uq_rg_review_issues_run_issue`。
- **验证（run 14，低空 query，真实 provider）**：全部 12 节点 succeeded——
  plan→collect(70 sources)→parse→score→build_evidence(73)→build_claims→gap_backfill→
  editor1→editor2→**verify_claims→chief_gate**。`decision=ADD_EVIDENCE`（不再崩溃，返回可用
  质量评分：evidence_coverage 0.6 / citation_integrity 0.5 / source_quality 0.6 / final 0.58）。
- 采集质量（run 14）：evidence 覆盖 中标/招投标/订单/客户验证/收入/年报 等全有。
- 注意：`test_research_harness_runner_eval_integration.py` 2 个失败为**预存**（stash 确认无改动
  也失败），与本轮无关。

## 采集源 usage_role 修复（方案B，2026-08-09）—— 低质源不再冒充官方

**根因**：`_impl._infer_source_family` 对知乎/自媒体/聚合站返回 `unknown`，`canonical_source_family`
兜底成 `local_official`（local_source_patterns.py:186）→ 低质源被当"官方"采进 evidence → 后续
`classify_source_role` 虽正确判 `aggregator_or_unknown`，但证据已带 local_official 假象，
proof_strength 只能判 context_only（48%）。

**修复**（real_nodes.py 采集归一化处）：`canonical_source_family` 归一化前，对 `unknown/空/local_official`
但**非官方域**的源直接改判 `aggregator_or_unknown`；权威媒体/高校白名单（.news.cn/.people.com.cn/
.edu.cn/.gov.cn 等）保留 local_official。

**验证**：
- 知乎/自媒体/聚合站（zhihu.com/whipcy.com/tvoao.com）→ **commercial_media**（不再 local_official）。
- 新华网/人大/人民日报 → **local_official**（权威保留）。
- 政府/统计局 → policy_document/official_statistics（不变）。
- run 16 实测：低质源（知乎×4）全归 commercial_media；family 分布
  commercial_media 37 / policy_document 27 / local_official 10。
- 27 相关测试 passed，ruff 干净。

## G4 Full-stack Load Acceptance — 完结 (2026-08-08)

三层负载切片全部 PASS：Network / Execution / Provider。G4 目标达成：
Full-stack 在真实 HTTP + 真实 PG + deterministic provider 下的**高并发正确性**已验证，
且压测驱动了两个真实修复：①`recover_expired` 并发双处理（TOCTOU）→ 条件 UPDATE；
②默认连接池 5+10=15 是网络层吞吐瓶颈 → 生产按峰值调 pool_size/max_overflow。

## Current Authoritative Handoff (2026-08-03 Research Contract Refactor Phase A)

- `scripts/gateway_network_load_acceptance.py`（真实 HTTP + 真实 PG，独立测试库
  `invest_agent_g4_load`，uvicorn 子进程 + httpx async 并发）：
  1. **S1 solo baseline**：POST→202 / GET→200 / cancel→200，solo submit ~118ms。
  2. **S2 burst submission**：cap=40，60 并发 → **恰好 40×202 / 20×503**，无 5xx；
     **peak_db_connections=17**（app 默认池 5+10=15 + 采样）。
     吞吐 **76.6 rps**（wall 0.78s），p50=545ms / p95=748ms（延迟主要在连接池排队）。
  3. **S3 idempotency replay**：同 key 20 并发 → 恰好 1 run，19 replay / 1 create，DB 无重复。
  4. **S4 poll storm**：200 并发 GET /runs+events → 全 200，吞吐 **112.5 rps**。
  5. **S5 cancel burst**：10 并发 cancel QUEUED → 全 200，completed=10，capacity -10。
  6. **S6 capacity reclaim**：queued=31，15 并发 → 恰好 9×202 / 6×503，边界精确回 40。
  7. **S7 leak & integrity**：pool.checkedout=0，孤儿 lease=0，幂等重复=0。
- 结论：控制面在网络层并发下**正确性全过**。诚实发现：默认连接池（5+10=15）
  是并发吞吐的真实瓶颈（高并发延迟主要花在池排队），生产可按预期峰值调
  `pool_size / max_overflow`（如 `DATABASE_URL?pool_size=20&max_overflow=20`）。

## Current Authoritative Handoff (2026-08-03 Research Contract Refactor Phase A)

- Primary active PLAN: `.agent/PLANS/research-contract-refactor-v1.md`.
- Status: `active_phaseA_core_schema_formalize`.
- Primary area: `research_workflow`; secondary: `provider_layer`, `eval_policy_ops`, `source_layer`, `task_substrate`.
- 阶段顺序 (用户评审): Phase 0 → A → A2 → B → C → D → E; 5 项硬要求已在 PLAN 固化。
- Phase 0 ✅ (2026-06-23): trace 补 prompt_version/hash/git/temperature/schema_version; 冻结 smoke_6+regression_10; pipeline_*_mode feature flags。
- Phase A (2026-08-03, **accepted**: implementation complete; L1 ✅; L2 replay ✅; L3 = pending milestone):
  - EvidenceUnit `quoted_span` + `quote_verified` (确定性 substring 校验) + `quote_loc`
    (quote_start/quote_end/quote_occurrence/offset_mode)。
  - ClaimCard 字段 (`_annotate_claim_card`, 纯确定性): claim_type(8 值) / epistemic_status /
    max_assertion_level(int rank) + assertion_level_label(具名) / forbidden_assertion_levels /
    forbidden_expansions / primary_slot_id + slot_ids; editor1 input pack 透传。
  - `packages/research_harness/research_contract.py` Contract Compiler:
    `compile_research_contract(plan) -> ResearchContract v1` (sections/claim_slots/
    writing_policy/meta), 不改 Planner; `critical` 只来自 `plan["critical_slots"]` 显式声明。
  - Claim Expander 改 slot-driven: 删除 `len(claims)<8`; gap-slot 检测含 required-fields +
    contradiction 门槛; `_llm_supplement_claims_slot_driven` 按 section 批量 (≤4 slot/调用)。
  - ResearchGap 与 ClaimCard 分离: `_build_research_gaps` (gap_type=no_reliable_evidence/
    contradiction/missing_fields + allowed_report_expression) 挂 `build_claims` 结果。
  - StructuredDraft paragraph 映射: Editor1 显式 `<!-- claim_ids/evidence_ids -->` marker
    (mapping_source=editor_explicit) + 启发式 fallback (mapping_source=heuristic, confidence<1);
    报告级 unused_claim_ids。
- 评审 4 项 must-fix + L2 前 4 个末尾约束已全部落地 (2026-08-03):
  family→critical 删除 / evidence_gap 拆 ResearchGap (reportability=pending_coverage_review) /
  paragraph 显式映射+校验 (mapping_validated/issues) / field_requirements (mandatory+any_of) /
  NO_CRITICAL_SLOT_DECLARED warning / live-provider 测试隔离 / 0/0 基线修复。
- **L2 Replay** (最小, accepted): `tests/fixtures/research_replay/{M03,C01,K07}/fixture.json`
  (recorded parsed_sources, 禁网) + `tests/test_research_l2_replay.py` (结构性 invariant:
  schema/citation/quote/claim/draft/determinism)。
- Latest validation: L1 (claim_card+contract 56 例) + L2 (7 例) + graph 聚焦回归 (7 例) = **76 例全绿**;
  ruff 0; py_compile 通过。
- Baseline: 0/0 基线已修复 — `data/tmp/resume_eval_A_6b/resume_eval_A_summary_valid.json`
  (dossier 证据解析重算, 6/6 非零)。live 6 题对比按 L1/L2/L3 分层改在 L3 里程碑跑。
- **Phase A2 (Shadow Source Content Clustering, 2026-08-03)**:
  `packages/research_harness/source_cluster.py` 纯确定性 (canonicalize_url/normalize_title/
  normalize_content/content_fingerprint/SimHash + number/date overlap; exact + near-dup;
  representative-based 非 Union-Find; revision candidate 不合并; critical-fact conflict 检查)。
  Shadow 输出 report/slot/cluster 三级 (shadow_distinct_content_count /
  shadow_duplicate_adjusted_source_count); 集成挂 `build_evidence` 结果
  `shadow_source_clustering` (仅元数据, 不写 origin_source_id, 不突变 source)。
  审计: precision=1.0 recall=1.0 false_merge=0.0 (10 场景 fixture, 非验收指标)。
- **Phase A2.5 (Real-data Shadow Validation, 2026-08-04)**:
  - 冻结 manifest 改 `freeze_tag`+`base_commit`+`manifest_commit=null` (校验以 git rev-parse 为准)。
  - per-slot 统计: `family_counts` 与真实 `slot_counts` 分离 + `aggregation_level`。
  - M03 slot 口径矛盾已修复: ReAct 补充 source 并入 + 空正文单例簇 → raw==distinct。
  - slot 新增 supporting_evidence_count/supporting_claim_count; invariant
    (distinct<=raw<=evidence; 无多成员簇时 raw==distinct) 6 题全过, 0 violation。
  - `scripts/shadow_difference_report.py` (6 题录制 DB 禁网): total raw=196 distinct=194
    reduction=0.0102; 仅 P04 有真实重复簇 (confidence 0.969)。
  - **人工审查清单**: `scripts/audit_pairs_review.py` 产出 **218 分层 pairs**
    (auto_merge 3 / candidate 158 / near_threshold 33 / revision 24) →
    `audit_pairs_review.md` + `.csv` + `audit_pairs_all.json`。
  - **高风险首轮审查包 (60 对)**: `audit_priority_review.md/.csv/_manifest.json`
    (seed=20260804): auto_merge 3 + revision 24 + top candidate 15 +
    0.78 阈值附近 10 (5 上/5 下) + random candidate 8; 每对含冲突详情/LCS/差异/human 空字段。
    **盲审拆分**: `audit_priority_review_blind.csv` (无 algorithm) +
    `audit_priority_review_algorithm.csv` (pair_id 关联; candidate→uncertain/manual_review)。
    **盲审协议**: `docs/source-clustering-annotation-protocol-v1.md` (8 值标签 + merge 映射 +
    confidence + 边界规则, annotation_schema_version=source_cluster_human_label_v1)。
  - formal read path DISABLED。
- **Phase B.1 (Shadow CoverageReport Integration, 2026-08-04 完成)**:
  `packages/research_harness/sufficiency_gate.py` `build_shadow_coverage_report(state)` —
  完整双轨 CoverageReport (report/section/slot 三级 raw vs duplicate_adjusted;
  critical_gate 仅显式 critical_slots 时 enabled; content distinctness 仅作 proxy,
  independence=not_evaluable; search_execution 记录"未找到"vs"未搜索";
  ResearchGap shadow_reportability 可生成但 approved 恒 None)。
  集成挂 `build_claims` 结果 `shadow_coverage_report` (shadow only)。
  **三态升级 (2026-08-04)**: satisfied/unsatisfied/not_evaluable; 数量门槛分离
  (min_evidence_items/min_raw_supporting_sources/min_distinct_content_sources/
  min_independent_sources); readiness 增 unknown; not_evaluable 不计 coverage=0。
  `scripts/shadow_coverage_report.py` 6 录制 case: 每 case 全 slot not_evaluable
  (缺 key_field + search_events 的正确诚实答案), 0 flip; 11 测试全绿。
- **盲审 pilot (2026-08-04, 60 对已标注)**: exact_duplicate 41 / full_reprint 17 /
  summary_or_excerpt 2。24 对 trivial self-pairs (同 source_id+URL) 已排除 →
  真实跨来源 36 对: auto_merge precision=1.0 (3/3, false_merge=0); candidate 100% merge-eligible
  (0.90 阈值过保守信号); revision protection 不可评估 (pool 无真实 revision pair)。
  已修 audit_pairs_review.py (source_id 去重 + revision 需内容不同); 汇总
  `data/tmp/shadow_difference_report/blind_review_pilot_summary.{json,md}`。
  pilot 结论: 无误并, 但 sample 过小不构成 95% 泛化; formal read path 仍 DISABLED。
- **Blocking rules + 阈值下探 (2026-08-04)**: `source_cluster.py` 增三类 blocking rules
  (critical_fact_conflict 保守版 / summary_or_excerpt / document_type_incompatible), blocking 命中→candidate。
  初版 critical_fact_conflict 对长文过度触发(33/36误拦)已改保守。`scripts/threshold_sweep.py`
  (task/case group split Calibration/Validation + 逐阈值 precision/recall/false_merge/severe_fp/
  revision_protection; 选择=severe_fp==0 & precision>=0.95 后最大 recall)。
  **pilot 结果 (36 真实跨来源)**: precision 全程 1.0 (0 FP), 阈值 0.90→0.80 recall 0.55→0.82
  (校准)/0.61(验证), selected=0.80。
- **Clean Pool v2 (2026-08-04)**: `data/tmp/shadow_difference_report_v2/` 733 对
  (candidate 167 / hard_negative 530 / near_threshold 33 / auto_merge 3 / revision 0);
  0 self-pair; revision=0 确认历史数据无真实跨来源 revision。
- **正式验证集采样 (2026-08-04)**: 分层抽 **194 真实对** → `clean_pool_v2_sample_blind.csv` 待标注;
  **26 benchmark fixtures** (revision 20 + doc-type 6) → `clean_pool_v2_benchmark_fixtures.json`。
- **B.2 Observed Read Path (2026-08-04)**: `observed_read_path_b2.py` 三轨 (raw/0.90/0.80)
  readiness + transitions + blocking hits; 0.80 仅 pilot_candidate; 纯观测不改系统。
  synthetic demo: raw satisfied / dup@0.90 satisfied / dup@0.80 unsatisfied (阈值敏感性演示)。
- **含 fixtures 的 sweep (2026-08-04)**: validation precision=1.0, recall=0.65, false_merge=0,
  severe_fp=0, **revision_protection=1.0**, selected=0.78; ablation 证 blocking rules 必要
  (none 模式 revision_protection=0.0)。
- **正式验证 (2026-08-04, 194 对标注完成)**: 去重后 127 唯一对; Calibration 选阈值
  precision 全程 1.0 → **selected=0.78** (recall 0.583); **Validation precision=1.0** (0 FP/0 severe),
  **recall=0.261 (<0.80 未达标)**, 根因 critical_fact_conflict 过度拦截 16 对 full_reprint/exact;
  revision protection / near_dup_rewrite 无法从本批验收 (无正例)。
  报告 `data/tmp/threshold_sweep_v2/VALIDATION_SUMMARY.md`。
- **A2.6 Entity-bound Conflict v2 (FactFrame, 2026-08-04)**: 16 对误拦截错误分类
  (multi_entity 8 / text_truncation 8); `packages/research_harness/fact_frame.py`
  (entity/attribute/scope/value 绑定; exact-hash skip; 未绑定不硬拦; 金额分类型/状态有序);
  接入 blocking_reasons; 8 测试 + 全量 111 绿。
  阈值配置: production_threshold=0.90, pilot_candidate=0.78,
  entity_bound_conflict_version=factframe_v2_implemented, formal_read_path=disabled。
  v2 Validation 冻结为 Error Analysis Set (不重调)。
- **A2 冻结 (2026-08-04)**: Phase A2 — Source Content Clustering **Provisionally Accepted
  for Shadow and Advisory Use**。formal read path DISABLED; Gate Enforcement DISABLED。
  Tiered usage 落地: exact_duplicate_adjusted_count (确定性, 正式可用) /
  likely_reprint_adjusted_count (advisory, 仅 SOURCE_SUPPORT_MAY_SHARE_SAME_CONTENT_ORIGIN
  warning) / distinct_supporting_content_count (shadow)。未验收: source independence,
  near-dup gate enforcement, revision lineage, production threshold 0.78。
- **Phase B.2 Evaluability Persistence (2026-08-04)**: `eval_persistence.py`
  追加式 store 持久化 ClaimSlot/SearchTask/SearchEvent/EvidenceUnit(key_fields 状态)/
  ClaimCard/CoverageSnapshot; `build_evaluable_coverage_report` 三态判定 +
  evaluation_completeness + readiness(unknown 防假 ready)。
  **Runner 接入**: `evaluation_recorder.py` + real_nodes 挂钩 (fail-open) —
  build_evidence 记录 ClaimSlots/SearchEvents/EvidenceUnits(key_fields 状态+family→slot),
  build_claims 记录 ClaimCards; `build_runtime_coverage_report` 显式双模式
  (evaluable_persistence/legacy_shadow, 不隐式切换); store to_dict/from_dict 支持
  checkpoint; 幂等记录 (同 ID 去重, 冲突记 IDEMPOTENCY_CONFLICT)。
  14 B.2 测试 (8 L2 + 6 集成) 全绿, 全量 132 例。
  **Real-run Acceptance (2026-08-04)**: 2 个全新任务 (无旧 checkpoint) —
  Case1 (证据充足) completeness=1.0, satisfied 3/unsatisfied 3/not_evaluable 0;
  Case2 (证据稀疏) completeness=0.57, satisfied 1/unsatisfied 3/not_evaluable 3。
  均不再全量 not_evaluable; coverage_input_source=evaluable_persistence,
  legacy_fallback_used=false。可追踪缺口 (SearchTask/Event recording、evidence
  field/link) 记录于 `data/tmp/b2_real_run_acceptance/B2_REAL_RUN_ACCEPTANCE.md`。
  **Phase B.2: Accepted。**
- **B.2 收尾补丁 (2026-08-04)**: SearchEvent recording rate 分母改实际执行任务数;
  SearchTask 生命周期修复 — `close_search_tasks` 作用域化
  (`round_id`/`exclude_task_ids` 参数), 从 `build_claims` 的全局收口移出
  (build_claims 只记录 ClaimCard), run-close 收口改挂 `finalize_report` 终结点
  (planned→cancelled, reason=run_close_planned_not_executed)。
- **Phase B.3 Gap Retrieval (B.3.1+B.3.2)**: `gap_retrieval.py` —
  ResearchGap (仅 unsatisfied, 8 类 gap_type, approved 恒 null) /
  EvaluationGap (仅 not_evaluable, repair action 第一版只 execute/retry) /
  SuggestedSearchAction (确定性 query 模板 + 优先级 + 去重, 不执行) /
  build_snapshot_diff。11 测试全绿, 全量 137 例。
  Gate Enforcement / Editor1 Blocking / Expression Approval 均 Disabled。
- **Phase B.3.3 Advisory Backfill Harness (2026-08-04)**: `advisory_backfill.py`
  独立 Harness (不接正式路由) — 每轮重派生 ResearchGap → 生成/去重
  SuggestedSearchAction → 创建 SearchTask(origin=gap_backfill, 带
  originating_gap_id/action_id) → SearchExecutor → SearchEvent(追加式) →
  Evidence(Scheme B: originating_search_event_ids) → 重算 CoverageSnapshot →
  SnapshotDiff; 8 条停止条件 (all_resolved/no_action/max_rounds/budget/
  slot_no_gain×2/degraded/eval_gap_only/provider_failure); 未解决 Gap→exhausted,
  approved_expression 恒 null。SearchTaskRecord 增 origin 溯源字段;
  store.degraded + copy()。12 机制测试全绿。
  **真实 Provider 运行**: `scripts/b3_advisory_backfill.py` 对 Case1/Case2 —
  Case1: d_local_rollout...execution_evidence unsatisfied→satisfied, 3 gap
  exhausted; Case2: 同 slot satisfied, 4 gap exhausted, official_policy
  not_evaluable 维持不变; query_repeat=0, approved_expression=0。
  产物 `data/tmp/b3_advisory_backfill/`, 验收 `B3_BACKFILL_ACCEPTANCE.md`。
- **Phase B.3.3b Graph Shadow Node (2026-08-04)**: `advisory_gap_backfill`
  Graph 节点 (build_claims → advisory_gap_backfill → editor1_draft, 边固定非循环)。
  copy-on-write shadow: 仅在 `advisory_backfill` 命名空间写 `run_advisory_backfill`
  结果, 不改 sources/evidence/claims/documents/coverage/final_report; flag
  `ADVISORY_GAP_BACKFILL_ENABLED` 默认 OFF + `_MODE=shadow`。节点 fail-open
  (degraded 不阻断 Editor1)。真实实现移入 `advisory_backfill_live.py`
  (AnySearch 执行器 + 内容关键词证据构建); SearchEvent 记录
  configured/executed/fallback trace; `SEARCH_PROVIDER_POLICY=required` 时
  anysearch 无 key 启动即报错不静默降级。
  **终结语义**: `finalize_evaluation_run` 独立于 finalize_report, 覆盖全部终止路径
  (REPORT_COMPLETED/HUMAN_REVIEW/BUDGET_EXHAUSTED/PROVIDER_FAILED/GRAPH_ERROR/
  USER_CANCELLED); HUMAN_REVIEW → planned/running 标 `suspended`
  (可 resume), 其余 → `cancelled`+reason; 挂 Runner 中心, finalize_report 不再是唯一
  run-close 点。SearchTask 增 `suspended`/`superseded` 状态。
  **测试**: `finalize_evaluation` 9 例 + `advisory_gap_backfill_node` 11 例 = 20 全绿;
  B.3.3 相关 fast 集 125 全绿; finalization/persistence graph 测试 10 全绿。
  AnySearch key 已配入 .env, 实测直接 success (provider_used=anysearch)。
- **Phase B.3.4 Graph Real-run Acceptance (2026-08-04)**: `scripts/b3_graph_shadow_acceptance.py`
  对 Case1/Case2 跑 flag OFF vs ON (确定性主路径 stub + 真实 AnySearch advisory):
  main_state/editor1_input/final_report 均 unchanged (false/false/false);
  advisory_backfill_generated=true, resolved_shadow_slots=2, exhausted=4/6,
  approved_expression=0, query_repeat=0; Case1 REPORT_COMPLETED / Case2
  HUMAN_REVIEW 双跑一致, 无遗留 running task。backfill SearchEvent 记录
  configured/executed/fallback trace (anysearch 直接命中, 无降级)。
  产物 `data/tmp/b3_graph_shadow_acceptance/`, 验收 `B3_GRAPH_SHADOW_ACCEPTANCE.md`。
  **Phase B.3: Provisionally Accepted for Advisory Use (Gate/Editor1/Expression 仍 Disabled)**。
- **Phase C.1 Claim-Constrained StructuredDraft (shadow, 2026-08-04)**: `structured_draft.py`
  — C.1.1 StructuredDraft 冻结 dataclass schema (StructuredDraft/DraftSection/
  DraftParagraph, 段落显式绑定 claim_ids+evidence_ids+assertion_level+limitations);
  C.1.2 `compile_editor1_input` (仅 approved ClaimCard 进入, Evidence 裁剪为
  approved claim 引用集合); C.1.3 `build_structured_shadow_draft` 确定性逐节
  shadow (ready/partial → factual 段落, blocked/unknown → 仅 gap_descriptive,
  assertion 按 claim max_allowed + section readiness 双重封顶, limitations 保留);
  C.1.4 `validate_structured_draft` 确定性校验 (引用完整性/assertion 越级/
  limitation 保留/readiness 姿态/gap 负面断言)。ClaimCardRecord 增 `text`。
  13 测试全绿; 真实 Case1/Case2 通过 (Case1: 15 approved claims/22 evidence,
  validation passed; Case2 unknown sections → gap_descriptive, 无强结论)。
  **正式 Markdown 输出不变, 纯 shadow, 未接 Graph 节点 (C.2 再做)**。
- **Phase C.2 Structured Shadow Graph Integration (2026-08-04)**: `structured_shadow_editor1`
  Graph 节点 (build_claims → advisory_gap_backfill → structured_shadow_editor1 →
  editor1_draft, 边固定非循环)。只读主 evaluation_store + 主 CoverageReport
  (绝不读 `advisory_backfill.evaluation_store`), 只写 `structured_draft_shadow`
  命名空间 (status/editor1_input/draft/validation_report/diagnostics/
  input_fingerprint); flag `STRUCTURED_DRAFT_SHADOW_ENABLED=false` 默认 +
  `_MODE=shadow`; fail-open。Shadow Draft 用稳定 content-derived ID
  (draft_id = hash(run_id+version+approved_claim_ids+coverage_snapshot_id),
  paragraph_id 同理), 无 uuid 随机, checkpoint 幂等。
  **测试**: C.2 8 例 (flag off / happy / input filtering / OFF-ON 非干预 / node
  failure degraded / checkpoint 稳定 ID / unknown→gap_descriptive / backfill
  隔离) 全绿; B.3+C.1+C.2 fast 集现 146 全绿。
  **真实 OFF/ON 验收**: Case1/Case2 main_state/formal editor1 input/report_markdown/
  final_report 全部 unchanged; shadow_draft_generated=true, shadow_validation_passed=true,
  approved_claim=2; Case2 HUMAN_REVIEW 双跑一致。产物
  `data/tmp/c2_structured_shadow_acceptance/`, 验收 `C2_STRUCTURED_SHADOW_ACCEPTANCE.md`。
  **Phase C.2: Accepted。StructuredDraft Schema + Validator 冻结。**
- **Phase C.3.1 Structured Compare (2026-08-04)**: `structured_compare.py` —
  同输入双轨: Legacy Editor1 (正式输出不变) vs Claim-Constrained Structured
  Editor1 (逐节调真实 DeepSeek 输出严格 JSON → `validate_llm_section` → 最多重试 1
  次 → `StructuredDraft` → 确定性 renderer → `structured_markdown` → 全稿
  validator → `comparison_report`)。Structured 只读 C.1 Editor1Input, 禁读
  Raw/full evidence/pending/advisory shadow/Legacy 草稿。配置
  `EDITOR1_MODE=legacy` + `STRUCTURED_EDITOR1_COMPARE_ENABLED=false` +
  `MAX_RETRIES=1` (允许值 legacy/structured_compare/canary/primary, 只实现 compare)。
  **关键修复**: Phase A ClaimCard 断言词汇 (pattern_supported/strong_conclusion +
  数字 1-4) 与 C.1 枚举不一致 → `normalize_claim_assertion` 归一化, assertion
  越级从 4/2 降为 0。
  **测试**: C.3.1 13 例全绿; fast 集 159 全绿。
  **真实验收**: Case1/3 structured_validation_passed=true, Case2=false
  (blocked_unknown_strong_claims=2 被 validator 拦截); approved claim 使用率
  0.27/0.29/1.0 (低, 触发 content_loss_warning); limitation Case2 丢失; 正式
  legacy 未变。
  **决策门: 继续 Compare (调 Prompt 与 Section 输入, 不扩 Schema)** — 基础设施
  与安全护栏有效, 剩余问题在 LLM 对 allowed claims 组织与 readiness 遵从度;
  不进入 structured_primary_canary。
- **C.3.1 Prompt/Input 校准 (Prompt v2, 2026-08-04)**: 修正指标语义
  (required/eligible claim usage 两档; limitation_retention 对 blocked/unknown/
  无 factual 记 not_applicable; 新增 paragraph mapping rates); 每节 Coverage
  Contract (required/optional claims + required limitations + forbidden
  conclusions + paragraph budget); 每 Claim 只给 1-2 条最强 Evidence; blocked/
  unknown 节不调 LLM 确定性生成 gap; Prompt v2 分层 + readiness 选择 few-shot
  (虚拟 ID); Retry 注入精准缺失反馈; Validator 多 Claim 段落证据按并集校验
  (消除 45 条误报)。18 C.3.1 测试全绿; fast 集 164 全绿。
  **消融 (zero-shot vs few-shot, 同 LLM/temp/input/retry)**: required coverage
  Case1/3/4 = 1.0; assertion/blocked = 0; mapping = 100%。Few-shot 未一致胜出
  (Case2 帮, Case1/3 差) → **不保留**。Case3/4 eligible=0.5 (<80%) →
  **按停止条件不调 Prompt v3/v4**, 下一轮修 Section–Claim assignment
  (Claim 去重 + required 划定), 不扩 Schema。产物
  `data/tmp/c3_structured_compare/C3_STRUCTURED_COMPARE_CALIBRATION.md`。
- **Phase C.3.2 Section–Claim Assignment (2026-08-04)**: `section_claim_assignment.py`
  — 结构优先 Section 归属 (primary_slot_id → section_id); Claim Signature
  (entity+attribute+scope+time+value+slot) 确定性聚类; 同族代表选择; required/
  optional/suppressed 三档, suppressed 记录 reason + suppressed_by_claim_id
  (exact_duplicate/semantic_duplicate/subsumed/conflicting_claim/
  background_overflow 等); `ContextAuditReport` 每节监控 Claim/Evidence/Token/
  使用率/overload。集成进 build_section_inputs (allowed=required+optional,
  suppressed 不进 prompt; Required 覆盖成为硬校验)。指标空集合改为
  null + `*_status: not_applicable`。12 测试全绿; fast 集 176 全绿。
  **真实验收 (zero-shot)**: eligible 覆盖 1.0 (Case3 0.5→1.0, Case5 holdout 1.0),
  Case1 validation 从 False(2 节失败)→True, assertion 0, blocked 0,
  required 1.0。产物
  `data/tmp/c3_structured_compare/C3_STRUCTURED_COMPARE_ASSIGNMENT.md`。
  **Phase C.3.2: Accepted。**
  **人工盲审 A/B (2026-08-04)**: 三 case (01/02/05) 盲审结论 —— **Legacy 效果更好**。
  → 决策门: **不进入 structured_primary_canary**, 保持 structured_compare,
  C.3.2 冻结 (不再调 Prompt / Claim Assignment)。下一步只研究
  **Structured Synthesis Paragraph** (在不引入新事实前提下, 对多个 Claim 做
  受约束综合, 补研究叙事/传导/相互印证), 达标后再评估 canary。
  Case5 标记 assignment_mechanics_only, 不参与叙事评价。
- **Phase C.3.3 Constrained Synthesis Layer (2026-08-05)**: `constrained_synthesis.py`
  — SynthesisContract + 确定性 Trigger Compiler (policy_to_implementation /
  implementation_to_stage / cross_source_corroboration, 同节 ≥2 不同 Claim) +
  LLM 只表达 Contract 的严格 JSON 生成 + Synthesis Validator (Claim/Evidence/实体/
  数字闭包, assertion, limitation, forbidden) + Evidence Gap Paragraph Builder
  (确定性, 输出 searched scope + missing fields) + Semantic Critic (advisory)。
  接入 structured_compare (factual → synthesis → rich gap → validate → render);
  DraftParagraph 增 synthesis role + synthesis_id。16 测试全绿; fast 192 全绿。
  **真实验收**: case_06 holdout 生成 3 条 implementation_to_stage synthesis
  (limitation 保留); 修复 synthesis_id 未注入 prompt 导致 LLM 自造 ID 的硬问题;
  真实 Case1 因 section 单一 family 触发少 (触发条件需贴近真实分布, 后续迭代)。
  **Phase C.3.3: Accepted (shadow, 受约束)。仍不进 canary**, 需再次人工盲审。
- **C.3.3.1 Cross-Section Synthesis Trigger Patch (2026-08-05)**: Trigger 从
  section-local 改为 report-level scan; SynthesisContract 增 `target_section_id`
  (跨节合成插入指定节); 跨节 policy_to_implementation 需 region 一致/上下级 +
  共享 theme + 时间顺序 (政策晚于项目 → inference 降为
  policy_direction_aligned_with_existing, 禁因果)。9 新测试全绿; C.3.3 共 25;
  fast 201 全绿。
  **真实 Case1 仍未触发**: B.2 case_01 的 approved/assigned claims 以政策 Claim
  为主 (claim_policy_primary 多 slot 进 3 节), 无独立落地/实现 Claim 落在另一节
  → 即使 report-level scan 也缺 impl 候选。**数据分布问题, 非代码 bug**;
  合成消融盲审需改用 policy+impl 共存的数据 (如保留 impl 代表或构造 case)。
- **C.3.3.2 Claim Availability Trace Audit (2026-08-05)**: `scripts/c3_claim_availability_audit.py`
  追踪 Case1 实现事实在 Source→Evidence→Claim→Approval→Slot→Assignment 的存活。
  **结论: drop_stage = `claim_text_persistence`** —— 6 类实现事实 (航线/投运/
  架次/政务/消防/公司披露) 全部 Evidence 存在、Claim 存在且 approved、绑定 slot、
  已分配, 但持久化 ClaimCard 的 **`text` 字段为空** (历史 B.2 store 在 text 字段
  加入前录制)。synthesis 触发器依赖 claim.text 检测 policy/implementation/status/
  scenario → 全空 → 不触发。部分事实因空 text 被 Assignment 合并标 section_assignment
  (次生)。产物 `data/tmp/c3_claim_availability_audit/`。
  **推荐修复**: ①真实 run `record_claim_cards` 已持久化 text; ②触发器
  `_is_policy/_is_implementation/_has_status/_is_scenario` 与 region/theme 提取应
  同时读 claim 关联 Evidence quoted_span (事实在证据里), 不扩 Schema。
- **C.3.3.3 Claim Semantic Basis Fallback (2026-08-05)**: 新增
  `build_claim_semantic_basis` / `select_semantic_evidence` — claim.text 非空优先;
  为空时只用该 Claim 自身绑定的 **verified Evidence quoted_span** (最多 2 条,
  去同 Content Cluster, 记录 fallback_used/evidence_ids/diagnostics)。
  policy/implementation/status/scenario/region/theme/time 统一读 semantic basis;
  不读 Raw Source / 全量 Evidence / Legacy / Backfill Shadow。修复
  `implementation_to_stage` a==b 退化 (要求 distinct 伙伴 Claim)。
  16 新测试全绿; C.3.3 共 41; fast 217 全绿。
  **Case1 重跑**: `semantic_fallback_claim_count > 0` ✓; `implementation_to_stage`
  触发 (distinct: c_statistics_001 + c_suppl_1) ✓; 但 **LLM 合成输出被 validator
  拦下** (自造数字"2025年6月" + forbidden "规模化商业运营/产业成熟") — LLM 契约
  合规问题, 非 fallback 问题; `policy_to_implementation` 因真实政策(低空/产业)与
  实现(政务/航线)主题不匹配未触发 (保守正确, 符合"不强行触发")。
  **未重建盲审包** (按"未成功前不重建")。
- **C.3.3.4 Synthesis Compliance Forensics / Repair (2026-08-05)**: 取证发现
  forbidden-conclusion 裸关键词匹配把"否定式边界说明"（如"尚不足以判断其是否已进入
  规模化商业运营"）误判为越界；且 LLM 自造数字（"2025年6月"）。修复：
  ① Validator 否定窗口检测（不足以判断/无法确认/不能确认/不支持/不可据此推断），
     正向断言才报 `positive_forbidden_assertion`，否定式边界通过；
  ② `allowed_numeric_mentions` 从 Contract allowed Evidence span 自动提取，
     Prompt 显式列出 + "不得自创数字"，正文与 numeric_mentions 都校验；
  ③ 精准 Retry（unsupported_numeric_mentions / positive_forbidden_assertions /
     missing_limitations 结构化反馈 + 保留已通过段落）；
  ④ 每次失败保存 forensics（contract/raw/parsed/issues/retry/final_status）。
  5 新测试; C.3.3 共 46; fast 222 全绿。
  **Case1 同一 contract 重跑成功**: `implementation_to_stage`
  (c_statistics_001 + c_suppl_1) 生成合规 synthesis 段并追加到 draft
  （roles 含 synthesis），否定式边界通过，数字仅用证据允许项。
  未改 Assignment / Trigger 类型 / Prompt v2。
- **Synthesis Ablation 盲审包 (2026-08-05)**: `scripts/c3_3_synthesis_ablation.py`
  从同一 case_01 StructuredDraft 派生 without_synthesis / with_synthesis 两版
  （共享同一 factual/gap 段，唯一变量 = synthesis），自动不变量校验全部通过
  (same_factual/gap/claims/evidence/numbers/limitations/section_order,
  only_difference=[synthesis])，随机 A/B 映射存 blind_mapping.json，
  输出 review_form.md / invariant_check.json / synthesis_contract.json /
  C3_3_SYNTHESIS_ABLATION_SUMMARY.md。
  本轮仅覆盖 `implementation_to_stage` (1 段, 125 字)；`policy_to_implementation`
  与 `cross_source_corroboration` 未覆盖（真实政策/实现主题不匹配，未强行触发）。
  另修复 assemble 时 synthesis_id 未保留的小缺陷。
  产物 `data/tmp/c3_3_synthesis_ablation/`。
- **测试状态表述（保守, 2026-08-04）**: 不宣称 full suite passed。
  准确口径: B.3.3a 12 全绿 + B.3.3b 20 全绿; B.3 相关 research_harness fast 集
  125 全绿; finalization/persistence graph 测试 10 全绿;
  全量仓库套件含 **36 个已知外部/网络失败** (packages/sources LLM/network/offline eval,
  改动前即存在, 与 B.3 无关; 2 个 graph 测试环境相关失败亦为既有)。
  如需证明既有失败未扩大, 以 git diff 后的 fast 集 + 上述 focused 集为准。
- **主流程回归 (2026-08-04 起)**: 让 Sufficiency Gate 使用当前 Schema 的真实
  Search Events / Evidence key fields / Claim Slots → 驱动 Gap Retrieval →
  约束 Editor1。新运行需持久化 Claim Slot / Evidence key fields / Search task 状态 /
  Content Cluster / Claim-Evidence-Slot links, 再在新数据上验证 CoverageReport。
  优先级: ① Sufficiency Gate 真可评估 → ② Gap Retrieval (insufficient slot → 缺失字段 →
  suggested_search_actions → 定向补搜) → ③ Editor1 ClaimCard 约束 → ④ 全文分层审查。
- 注: STATUS.md 下方 2026-07-16 及更早 handoff 为历史记录, 已由本节 supersede。

## Previous Handoff (2026-07-16 Report Narrative And Context Budget Remediation Completed)

- Primary active PLAN: none.
- Completed PLAN: `.agent/PLANS/archive/report-narrative-context-budget-remediation-v1.md`.
- Status: `completed_archived`.
- Primary area: `research_workflow`; secondary: `provider_layer`, `eval_policy_ops`.
- Execution mode: `local_direct`; user explicitly requested no further subagents for this task.
- Result: final reports no longer degrade into evidence ledgers; actual Editor1 prompt budget is separated from state footprint; public context snapshots no longer embed full graph state; obligation gaps cap reports at `level_2`.
- Latest validation: focused graph `17 passed`; protected/report regression `42 passed`; compile passed; changed-file Ruff passed.
- Live artifacts: `data/tmp/report_narrative_context_budget_live/P04_final_v3/` and `data/tmp/report_narrative_context_budget_live/K12_final_v2/`.
- Live outcome: both reports have complete narrative structure and unique semantic headings; both remain `level_2` because `obl_location_precision` is uncovered.
- Context payload outcome: K12 `response.json` reduced to about 620 KB from the prior roughly 67 MB full-state snapshot baseline; Editor1 prompt packs were 1573/1600 and 1592/1600.
- Blockers: none for this PLAN. Residual product risk is the generic location parser/exact-local obligation routing, especially K12's malformed target location.
- Next recommended action: create a separate general location-parser and exact-local routing PLAN only when the user chooses to continue that source-quality line.
## Previous Handoff (2026-07-15 AnySearch And Final Report Completion)

- Primary active PLAN: none.
- Completed PLANs:
  - `.agent/PLANS/archive/anysearch-production-discovery-integration-v1.md`
  - `.agent/PLANS/archive/report-final-artifact-persistence-remediation-v1.md`
- Status: `completed_archived`
- Result: AnySearch is the default discovery provider with explicit Tavily fallback; the normal graph path now persists dossier paths and exports real `FINAL_REPORT.md` artifacts.
- Live validation: P04 and K12 both completed with `PASS`, `report_preview.report_id=1`, direct dossier/final-report artifacts, and 10/10 successful search events; no recovery script was used.
- Protected contracts: EvidenceBundle, citations, source quality, public research responses, graph decisions, and task/run semantics were not changed.
- Comparison artifact: `data/tmp/anysearch_final_report_remediation/COMPARISON.md`.
- Remaining risks: K12 location parsing/precision, claim-level citation visibility, context-pack budget overrun, and isolated SQLite run-id artifact collision.
- Next action: create a separate report-quality PLAN only if the user chooses to remediate those remaining risks.
## Current Authoritative Handoff (2026-07-15 AnySearch Skill Strong Evidence Eval)

- Completed PLAN: `.agent/PLANS/archive/anysearch-skill-strong-evidence-eval-v1.md`
- Status: `completed_archived`
- Primary area: `eval_policy_ops`
- Execution mode: `local_direct`
- Current slice: compare the official AnySearch Skill with Tavily basic on project landing, enterprise disclosures, tender/procurement, and environment/land strong evidence.
- Protected contracts: no production provider, source router, EvidenceBundle, or citation changes are allowed in this PLAN.
- Latest validation: compile and Ruff passed; focused pytest `3 passed`; 4-case smoke and full 8-case live runs completed with all provider calls successful.
- Next action: create a separate production integration PLAN only if AnySearch should become an optional discovery lane.

## Current Authoritative Handoff (2026-07-15 AnySearch Comparison)

- Completed PLAN: `.agent/PLANS/archive/anysearch-tavily-comparison-v1.md`
- Status: `completed_archived`
- Primary area: `eval_policy_ops`
- Validation: compile and Ruff passed; focused pytest `3 passed`; live geo-aware gate `12/12` calls succeeded.
- Result: AnySearch led relevance and returned depth; source quality tied Tavily basic; Tavily advanced had no stable advantage.
- Next action: create a separate production integration PLAN only if AnySearch should become an optional discovery lane.

Last updated: 2026-07-01

This file is the current execution handoff. Historical details live in each
PLAN file and in `.agent/PLANS/archive/`.

## Current Authoritative Handoff (2026-06-30)

This section supersedes older handoff snapshots below for the current requested
work. Historical research workflow handoffs remain below and should be resumed
only when the user returns to that line.

Primary active PLAN:

- None for the review-gated workflow release-prep line.
- Completed PLAN archived at
  `.agent/PLANS/archive/review-gated-agent-workflow-release-prep-v1.md`
- Status: `completed_archived`
- Primary area: `docs_only`
- Secondary areas: `task_substrate`, `eval_policy_ops`, `memory_feedback`

Current active slice:

- Completed: `Review-Gated Agent Workflow Release Prep v1`
- Purpose: prepared the review-gated workflow plugin for GitHub-style release
  with plugin-local release docs, installation guidance, hook trust notes,
  release checklist, and repo marketplace example.
- Plain Chinese explanation: 鐜板湪缁х画鍋氬紑婧愬彂甯冨噯澶囥€備笉浼氳鐩栧綋鍓嶄粨搴撴牴
  README锛屼笉瀹夎鎻掍欢锛屼笉鍚敤 hooks锛屽彧琛ュ厖鎻掍欢鐩綍鍐呯殑鍙戝竷璧勬枡鍜?  `.agents/plugins/marketplace.json` 绀轰緥銆傝 release-prep PLAN 宸插畬鎴愩€?
Latest validation:

- Read `docs/prd/prd_reference_for_codex.md` as the PRD template baseline.
- Read `.agent/skills/group2-worker-lane-design.md`,
  `.agent/skills/subagent-gate-contract.md`, `.agent/skills/tdd-policy.md`,
  and `.agent/skills/real-world-case-design.md`.
- Checked official Codex manual sections for skills, subagents, plugins, and
  hooks. Design direction: plugin-first distribution with copyable
  skills/hooks/templates.
- Created `.agent/PLANS/review-gated-agent-workflow-open-source-v1.md`.
- `Test-Path .agent\PLANS\review-gated-agent-workflow-open-source-v1.md`
  -> `True`.
- `Select-String -Path .agent\STATUS.md -Pattern "review-gated-agent-workflow-open-source-v1"`
  matched the primary active PLAN entry.
- `git status --short` shows a dirty worktree with many unrelated existing
  changes; this planning step only touched `.agent/STATUS.md` and the new PLAN.
- Created `docs/workflows/review-gated-agent-workflow.md`.
- Created `docs/workflows/open-source-package-format.md`.
- Created `docs/workflows/skill-contracts.md`.
- Created `docs/workflows/hook-scope-guard.md`.
- Created `docs/workflows/project-integration-notes.md`.
- Created `examples/generic-saas-feature/` with PRD/RPD, PLAN, Group2 design,
  and validation examples.
- Archived the completed PLAN to
  `.agent/PLANS/archive/review-gated-agent-workflow-open-source-v1.md`.

Next recommended action:

1. If the user wants real publication, create a separate task for extracting
   this plugin package into a public GitHub repository, tagging v0.1.0, and
   validating install instructions.
2. If the user wants local Codex installation, run a separate marketplace/trust
   review task.
3. Keep PRD workflow and `group2-design` explicit-only.

## Current Authoritative Handoff (2026-06-25)

This section supersedes older handoff snapshots below. Treat this section and
`.agent/PLANS/evidence-eligibility-source-quality-v1.md` as the execution
authority.

## Current Authoritative Handoff Update (2026-06-25 Phase 2-5)

This update supersedes the older evidence-eligibility handoff details
immediately below.

Primary active PLAN:

- `.agent/PLANS/research-contract-refactor-v1.md`
- Status: `active_phaseA_core_schema_formalize`
- Phase 0 (baseline observability) ✅: trace 补 prompt_version/hash/git/temperature;
  冻结 smoke_6 + regression_10 评测子集; 建 pipeline_*_mode feature flags
- Primary area: `research_workflow`
- Secondary areas: `provider_layer`, `eval_policy_ops`, `source_layer`, `task_substrate`
- Parent of evidence-layer plans: `.agent/PLANS/goal-driven-evidence-react-v1.md` + `.agent/PLANS/evidence-eligibility-source-quality-v1.md` (已完成的前置 evidence 工作)
- 阶段顺序 (用户评审调整): Phase 0 基线观测 → A 核心 Schema → A2 来源聚类 → B Sufficiency Gate → C 全量分层审查 → D Planner 收敛 → E 高级能力
- 5 项硬要求: (1) Prompt Registry 最低版进 Phase 0; (2) 基础聚类提前 A2; (3) critical 硬门禁; (4) Claim Expander slot-driven; (5) additive/dual-write/shadow/feature-flag

Current active slice:

- Phase 5 partially completed: `live regression gate`
- Purpose: source quality now flows into graph evidence, verifier eligibility,
  chief-gate obligation coverage, and final-report audit observability. The
  remaining blocker is the full final-report live smoke timeout.
- Plain Chinese explanation: graph source 鐨勮瘎绾у凡缁忎笅浼犲埌 evidence锛沞vidence
  鍐嶇敓鎴?`evidence_type`銆乣proof_strength` 鍜?eligibility锛岀敤鏉ュ垽鏂竴鏉¤瘉鎹?  鏄惁鐪熺殑鑳芥敮鎾戞煇涓?claim銆傚綋鍓嶄唬鐮佸拰鏈湴娴嬭瘯宸查€氳繃锛屽墿浣欓棶棰樻槸 full live
  smoke 瓒呮椂锛屾病鏈夌敓鎴愭渶缁?artifact銆?
Latest validation:

- `python -m ruff check packages\research_harness\real_nodes.py tests\test_research_harness_graph.py` passed.
- `python -m py_compile packages\research_harness\real_nodes.py tests\test_research_harness_graph.py` passed.
- `pytest -q tests\test_research_harness_graph.py -k "evidence_quality or evidence_eligibility or build_evidence or source_family or verifier or finalize or chief_gate"` -> 16 passed, 62 deselected.
- `pytest -q tests\test_agents_workflow.py tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py` -> 24 passed.
- Narrow live inspection passed and wrote artifacts under
  `data/tmp/evidence_eligibility_inspect`.
- Full final-report smoke timed out after 364 seconds and produced no stable
  artifact under `data/tmp/evidence_eligibility_full`.
- Target-family mismatch risk remediation:
  - `collect_sources_provider_backed` now records
    `target_source_family_match`, `target_source_family_mismatch_reason`, and
    search-event match/mismatch counts.
  - Mismatched sources are retained for possible other uses, but their
    `source_quality_v2.not_sufficient_for` includes
    `target_source_family:<family>`.
  - `scripts/inspect_spec_first_pass_live.py` now reports
    `spec_target_family_mismatch_count` and preview-level mismatch details.
  - ruff and py_compile passed for the changed files.
  - focused pytest for this slice was blocked by Codex usage limit and still
    needs to be rerun.

Next recommended action:

1. Resolve the Phase 5 full live smoke timeout before marking the PLAN
   complete.
2. Rerun the blocked focused pytest:
   `pytest -q tests\test_research_harness_graph.py -k "collect_sources_provider_backed_exposes_spec_round_diagnostics or evidence_eligibility or source_family"`.
3. Prefer a bounded full-smoke command that writes partial artifacts before
   timeout, or rerun with a longer timeout and narrower retrieval budget.
4. Inspect `contract_meta.evidence_quality`, `final_report.audit_markdown`, and
   `claim_support_matrix[*].claim_support_eligibility`.
5. If final report still PASSes with ineligible evidence, reopen Phase 3/4;
   otherwise mark Phase 5 completed and archive the PLAN.

Primary active PLAN:

- `.agent/PLANS/evidence-eligibility-source-quality-v1.md`
- Status: `active_phase1_completed_phase2_pending`
- Primary area: `research_workflow`
- Secondary areas: `source_layer`, `provider_layer`, `eval_policy_ops`
- Parent / reference PLAN: `.agent/PLANS/goal-driven-evidence-react-v1.md`

Current active slice:

- Phase 2 pending: `evidence type and evidence quality`
- Purpose: source-quality reuse is now implemented for graph sources. The next
  slice should make graph evidence inherit `source_quality_v2` and expose
  internal `evidence_quality_v2`, including `evidence_type`, `proof_strength`,
  and eligibility-oriented quality fields.
- Plain Chinese explanation: graph source 鐜板湪宸茬粡甯︽湁鏉ユ簮璇勭骇锛涗笅涓€姝ユ槸璁╂瘡鏉?  evidence 缁ф壙瀵瑰簲 source 鐨勮瘎绾э紝骞跺垽鏂繖鏉?evidence 鍒板簳鑳借瘉鏄庝粈涔堛€?
Execution mode:

- Recommended route: `remediation_gate`.
- Reason: the 2026-06-24 full final-report live test reached final report but
  required auto-approval over `HUMAN_REVIEW`, and exposed source-family mismatch
  plus weak source/evidence/gate linkage.
- Public `/deep-research/analyze` and `/research/analyze` response shapes are
  not authorized to change in this PLAN.

Latest baseline:

- Phase 1 implementation completed:
  - `packages/research_harness/real_nodes.py` now calls
    `packages.sources.source_quality.assess_source_quality_v2` for accepted
    graph sources in `collect_sources_provider_backed`.
  - Accepted graph sources now carry `source_quality_v2`, `source_tier`,
    `source_usage_role`, and `source_credibility_score`.
  - `tests/test_research_harness_graph.py` now asserts accepted collect sources
    expose these fields.
- Phase 1 validation:
  - `python -m ruff check packages\research_harness\real_nodes.py packages\sources\source_quality.py tests\test_research_harness_graph.py` passed.
  - `python -m py_compile packages\research_harness\real_nodes.py packages\sources\source_quality.py tests\test_research_harness_graph.py` passed.
  - `pytest -q tests\test_sources_source_quality_v2.py tests\test_research_harness_graph.py -k "source_quality or source_family or chief_gate"` -> 12 passed, 66 deselected.
  - `pytest -q tests\test_research_harness_graph.py::test_collect_sources_provider_backed_filters_spam_and_keeps_location_match` -> 1 passed.
  - `pytest -q tests\test_agents_workflow.py tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py` -> 24 passed.
- Parent Phase 2.5 already implemented bounded `spec_driven_first_pass` search
  rounds in `packages/research_harness/real_nodes.py`.
- Narrow live inspection showed 6 `spec_driven_first_pass` search events, 25
  spec-driven sources, and target families `public_resource_transaction`,
  `company_disclosure`, and `statistics`.
- Full final-report live baseline:
  - Query:
    `2025骞村悎鑲ヤ綆绌虹粡娴庡湴鏂规斂绛栥€佷笂甯傚叕鍙告姭闇蹭笌椤圭洰钀藉湴鎯呭喌`
  - Artifact:
    `data/tmp/full_final_report_hefei_phase2_5/FINAL_REPORT.md`
  - Workflow status: `succeeded`.
  - Final decision: `PASS`, but only after initial `HUMAN_REVIEW` was
    auto-approved with `resume_action=approve`.
  - Report level: `level_2`.
  - Main blockers exposed: source-family mismatch, uncontrolled credit
    amplification, provider planner parse fallback, over-budget context packs,
    and missing search/claim diagnostics in the dossier.

Next recommended action:

1. Execute Phase 2 of `.agent/PLANS/evidence-eligibility-source-quality-v1.md`.
2. Add internal `evidence_quality_v2` metadata to graph evidence so evidence
   inherits source quality.
3. Infer conservative `evidence_type` / `proof_strength` without changing
   public `EvidenceBundle` or citation schema.
4. Run focused pytest for `build_evidence`, `source_family`, and future
   `evidence_quality` coverage.

## Current Authoritative Handoff

Primary active PLAN:

- `.agent/PLANS/goal-driven-evidence-react-v1.md`
- Status: `active_phase2_5_full_final_report_live_completed_pending_remediation`
- Primary area: `research_workflow`
- Secondary areas: `source_layer`, `provider_layer`, `eval_policy_ops`

Current active slice:

- Phase 2.5: `spec-driven first-pass retrieval`
- Purpose: move `evidence_requirement_spec` awareness into first-pass retrieval,
  before ReAct evidence backfill.
- Plain Chinese explanation: `evidence_requirement_spec` is the report evidence
  requirement table. It says which source families and key fields each report
  section needs. Phase 2.5 should let `collect_sources` use that table during
  the first search wave, instead of waiting until `build_evidence` discovers
  gaps and backfills them later.

Execution mode:

- Routed through `.agent/skills/execution-mode-router.md`.
- Treated as protected-boundary work because Phase 2.5 changes
  `collect_sources` search semantics and may affect user-facing evidence
  coverage.
- Public `/deep-research/analyze` and `/research/analyze` response shapes were
  not changed.

Latest implementation validation:

- Implemented bounded `spec_driven_first_pass` search rounds in
  `packages/research_harness/real_nodes.py`.
- Added internal `spec_first_pass_min_search_rounds` state key in
  `packages/research_harness/state.py`.
- Added plan/collect diagnostics tests in
  `tests/test_research_harness_graph.py`.
- Focused validation passed:
  - `python -m ruff check packages\research_harness\real_nodes.py packages\research_harness\state.py tests\test_research_harness_graph.py`
  - `python -m py_compile packages\research_harness\real_nodes.py packages\research_harness\state.py tests\test_research_harness_graph.py`
  - `pytest -q tests\test_research_harness_graph.py -k "spec_driven_first_pass or no_spec_fallback or exposes_spec_round_diagnostics or build_evidence or chief_gate or finalize"` 鈫?16 passed.
  - `pytest -q tests\test_agents_workflow.py tests\test_research_api.py tests\test_research_provider_integration.py tests\test_deepseek_provider.py` 鈫?24 passed.
- Live validation update:
  - Narrow live inspection passed with
    `scripts/inspect_spec_first_pass_live.py`.
  - Artifacts:
    `data/tmp/spec_first_pass_live_inspect/summary.json`,
    `data/tmp/spec_first_pass_live_inspect/plan_result.json`, and
    `data/tmp/spec_first_pass_live_inspect/collect_result.json`.
  - Real provider output contained 6 `spec_driven_first_pass` search events,
    25 spec-driven sources, and target families
    `public_resource_transaction`, `company_disclosure`, `statistics`.
  - Budget risk: estimated credits were 20 in the narrow run because
    collect uses advanced search and Phase 2.5 currently emits 3 families x
    2 phrases.
- Full final-report live validation update:
  - Query:
    `2025骞村悎鑲ヤ綆绌虹粡娴庡湴鏂规斂绛栥€佷笂甯傚叕鍙告姭闇蹭笌椤圭洰钀藉湴鎯呭喌`
  - Command:
    `python scripts\graph_provider_backed_smoke.py --query "2025骞村悎鑲ヤ綆绌虹粡娴庡湴鏂规斂绛栥€佷笂甯傚叕鍙告姭闇蹭笌椤圭洰钀藉湴鎯呭喌" --max-rounds 1 --max-loop-count 1 --output-dir data\tmp\full_final_report_hefei_phase2_5 --env-file .env --reset --resume-action approve --resume-notes "Manual approval for full final-report live test."`
  - Result: full graph reached `final_report` and produced
    `data/tmp/full_final_report_hefei_phase2_5/FINAL_REPORT.md`.
  - Runtime: about 683.5s.
  - Workflow status: `succeeded`.
  - Final decision: `PASS`, but only after initial `HUMAN_REVIEW` was
    auto-approved with `resume_action=approve`.
  - Report level: `level_2` preliminary research report.
  - Quality scores: evidence_coverage 0.7, citation_integrity 0.8,
    source_quality 0.6, contradiction_resolution 1.0, final_score 0.75.
  - Phase 2.5 was active in the full graph: observed 12
    `spec_driven_first_pass` search events across two collect steps.
  - Main blockers exposed: source-family mismatch, uncontrolled credit
    amplification, provider planner parse fallback, over-budget context packs,
    and missing search/claim diagnostics in the dossier.
- Known validation gap:
  - `python -m ruff check .` fails on pre-existing/generated paths
    (`.agent/hooks`, `.claude/worktrees`, `unsloth_compiled_cache`), while the
    changed files pass targeted ruff.
  - Earlier full graph live smoke timed out after 304s and produced no files in
    `data/tmp/goal_evidence_phase2_5_live_smoke`; the later
    `full_final_report_hefei_phase2_5` run completed only with auto-approval
    over a HUMAN_REVIEW gate.

Next recommended action:

1. Add explicit Phase 2.5 credit controls before defaulting this behavior for
   high-frequency use. Candidate: reduce default spec phrases per family from 2
   to 1 or add a provider-credit cap.
2. Repair source-family evidence matching so `official_policy` claims are not
   satisfied by generic `official_news`, and `statistics` claims are not
   satisfied by `company_disclosure`.
3. Improve final-report observability: expose title/URL citations in the report
   body and include search events / claim verifications in the dossier.
4. Rerun a narrow live inspection and one full final-report live test after
   remediation.

Historical note:

- Sections below include older snapshots from Tavily recall, readable-report
  remediation, and other sidecar plans. Treat this `Current Authoritative
  Handoff` section and the active PLAN as the execution authority.

## Repository Current Focus

### NEW primary active: Goal-Driven Evidence ReAct v1 (2026-06-21)

**Plan**: `.agent/PLANS/goal-driven-evidence-react-v1.md` 鈥?`active_phase0_design_frozen`
After a /brainstorm on GPT's report evaluation (report is level_2 鍒濇鐮旂┒鎶ュ憡,
not level_3 娣卞害鐮旀姤), the user chose a **goal-driven evidence ReAct** redesign
over my initial passive "evidence-matrix + guard" idea. Core insight (code-
verified): retrieval is similarity-driven, and `build_evidence` does NOT know
the final report format (report/draft/鏍煎紡: False) though `tool_session` is
already passed in. editor1 knows the 11-section framework but the evidence is
already fixed by then 鈥?the segments work in isolation.
- Redesign: `build_evidence` becomes a goal-driven editor 鈥?reads an
  `evidence_requirement_spec` (section 鈫?required source_family + min evidence +
  key fields 閲戦/涓讳綋/闃舵/棰戞), self-checks gaps after first build, calls
  tool_session to re-extract from source (ReAct loop, bounded), until the
  framework is filled. claim/editor1 do NOT get this ability.
- + `claim_strength_guard` before finalize (spec as sufficiency baseline):
  downgrade琛ㄨ堪 by default, HUMAN_REVIEW only when core claims all weak; outputs
  report level (1-4).
- Phase 0 design frozen; Phase 1 done (`build_evidence_requirement_spec` in
  plan_semantic.py, derives section鈫抺families, min_evidence, key_fields} from
  dimension_plan + obligations); Phase 2 self-check subset done
  (`_evidence_gap_selfcheck` in real_nodes.py 鈥?build_evidence now emits
  `evidence_gap_report` flagging under-covered/missing-field sections; resolves
  family via source_id鈫抯ource since evidence items have no source_family field).
  ruff 0 serious, build_evidence 1 passed zero-regression, deterministic check
  passed (policy covered=3/2 ok, execution covered=0/2 鐪熺己鍙?.
  Next: re-run live to confirm real gap_report (bug-version product
  data/tmp/evidence_gap_case1 is stale), then decide ReAct re-extraction loop
  (Phase 2 second half) vs jump to claim_strength_guard (Phase 4) given Tavily
  recall limits (ADR 0001).



### Source Taxonomy Unification (ADR 0002) 鈥?IMPLEMENTED 2026-06-21, live-validated

source_family was an unconstrained free string (5 spellings for statistics, 5
for project, 3 for environmental, 4 for industry). Unified to a canonical
8-value taxonomy via 5-question grilling (see `docs/adr/0002`, `CONTEXT.md`,
`docs/source-taxonomy-inventory.md`).
- `local_source_patterns.py`: `CanonicalSourceFamily` Literal (8 values) +
  `_FAMILY_ALIAS_TO_CANONICAL` + `canonical_source_family()` / `family_to_role()`
  / `family_to_backbone()`. 17/17 synonym-convergence test passed.
- Producers normalized: `real_nodes.py` collect_sources + `retrieval_bridge.py`
  (2x `or "graph_source"`). `llm_agents.py`/`plan_semantic.py` confirmed as
  read-through / obligation-contract, not source producers 鈥?left untouched.
- Validation: ruff 0 serious; source-layer regression 13 passed (zero
  regression); live case1 鈥?3636 source objects all canonical (official_policy
  2298 / official_news 954 / company_disclosure 384). The only non-canonical
  value `location_matched_official_or_project_source` (2x) is the chief_gate
  obligation-coverage requirement field, correctly out of scope.
- Out of scope (future): unify the 4 parallel search-caliber expanders;
  optionally add a distinct role for environmental_land.



Two active tracks:

**Track 0: Tavily Recall Fix for Location-Sensitive Queries** (ADR 0001 + correction) 鈥?fixed, live-validating
- Problem: location-sensitive queries (e.g. "鍚堣偉浣庣┖缁忔祹") produce reports whose
  body is out-of-region (娣卞湷/姹熻嫃/姹犲窞); live case1 recalled 0 Hefei sources.
- ADR 0001 (`docs/adr/0001-tavily-local-targeted-gap-retrieval.md`) first
  designed local-domain hard-targeting via `local_source_domains_for_backbones`.
  USER'S TAVILY TEST DISPROVED ITS CORE ASSUMPTION (see ADR "淇 2026-06-21"):
  a manual `search_depth="advanced"` + clean query `"鍚堣偉浣庣┖缁忔祹鏀跨瓥"` with NO
  include_domains returned real Hefei policy originals on aggregator/media hosts
  (ichuanghui.org銆婂悎鑲ュ競鏀寔浣庣┖缁忔祹鍙戝睍鑻ュ共鏀跨瓥銆? ahchanye.com 琛屽姩璁″垝,
  news.cn) 鈥?NOT on hefei.gov.cn. The local-domain-filtered round returned 0.
- TRUE root causes (3, replacing the ADR's original diagnosis):
  1. collect_sources Tavily call lacked `search_depth="advanced"` (used basic).
     FIXED: added search_depth="advanced" to the request (real_nodes.py ~L1909).
  2. include_domains hard-filter backfired 鈥?Hefei sources aren't on the filtered
     gov domains. FIXED: `_build_gap_targeted_rounds` no longer hard-filters
     domains (include_domains=[]); recall comes from advanced + clean location
     phrase. Dropped the dual-query/local-domain design.
  3. query over-concatenation dilutes the core term (vs simple "鍚堣偉浣庣┖缁忔祹鏀跨瓥").
     FIXED: `_gap_core_topic()` reduces the verbose query to its core topic
     (strips year, location stem incl. trailing 甯?鐪? broad descriptors) so the
     gap phrase becomes "鍚堣偉 浣庣┖缁忔祹 椤圭洰 钀藉湴 鏈湴" instead of the full
     "鍚堣偉 2025骞村悎鑲ュ競浣庣┖缁忔祹浜т笟鏀跨瓥銆佷紒涓氭姭闇蹭笌椤圭洰钀藉湴鎯呭喌 ...".
- A+C relevance fix still stands (gate location hard-gate + phrase location
  retention) 鈫?location obligations drop to not-covered 鈫?trigger Phase 8 gap
  loop. The gap loop now uses advanced + no-filter instead of local hard-filter.
- Live validation: #1+#2 confirmed (data/tmp/tavily_advanced_case1) 鈥?Hefei
  source recall 0/20 鈫?3/20 (ahchanye.com 琛屽姩璁″垝 脳2, ichuanghui.org 鏀跨瓥鍘熸枃).
  All-3-fixes run in progress (data/tmp/tavily_all3_case1b) to measure further lift.
- Live validation FINAL (data/tmp/tavily_4fix_fg, all 4 fixes): Hefei source
  recall 0/20 鈫?3/10 (after #1+#2) 鈫?**8/20** (all 4). Report body flipped to
  Hefei-primary: "鍚堣偉" mentioned 60x vs out-of-region (娣卞湷/姝︽眽/閲嶅簡/涓婃捣) 23x.
  Recalled the missing first-hand Hefei originals (鍚堣偉甯傛斂搴滃姙銆婃敮鎸佷綆绌虹粡娴庡彂灞?
  鑻ュ共鏀跨瓥銆? 銆婂悎鑲ュ競浣庣┖缁忔祹鍙戝睍琛屽姩璁″垝2023-2025銆? 寰佹眰鎰忚绋? 宄伴鍚堜綔).
  FINAL_REPORT.md = 5823 chars, 11 sections. decision=HUMAN_REVIEW (honest).
- Status: Track 0 COMPLETE 鈥?all 4 root causes fixed and live-validated.
- LESSON: verify a provider's capability under its simplest call (advanced +
  clean query) BEFORE designing complex targeting. ADR 0001's original design
  over-engineered on an unverified "local data lives on gov domains" assumption.

**Track 1: Readable Report Remediation** 鉁?COMPLETE (Phases 1-9 + 4/4 live product_pass)
- Phase 1-4: inspector truth 鉁? gate obligation 鉁? report separation 鉁? P0 gate consumption 鉁?
- Depth track (7-9) added after grounded brainstorm on the "evidence ledger"
  critique: symptoms accurate, but its 9-node pipeline mostly already exists.
  Real bottleneck = starved nodes (5 sources, 1:1 evidence, all
  background_support) + the LLM writer NEVER actually running.
- Phase 7 (atomic evidence extraction) 鉁? source fulltext 鈫?multiple typed
  atomic evidence (live: 45-50 evidence/run), deterministic fallback.
- Phase 8 (gap-driven 2nd-round retrieval) 鉁? plan_task consumes gate
  required_actions on re-entry, injects family-targeted gap rounds FIRST so
  they fall inside the collect_sources max_rounds slice and actually execute.
- Phase 9 (writer synthesis) 鉁? found+fixed the biggest defect 鈥?
  `_generate_real_editor1_draft` raised NameError every call 鈫?silent template
  fallback, so the LLM writer had NEVER run. Fixed inputs, piped Phase 7 atomic
  metadata, rebuilt prompt (region comparison + transmission chain + method/body
  consistency + credibility-vs-support separation), JSON output, max_tokens=8000
  (1200 truncated the report 鈫?parse fail 鈫?template), drafts populated in
  fallback (runner IndexError), gate-caliber fix (prefer _impl coverage + write
  reconciled gap back), inspector draft-fallback + over_budget advisory.
- Phase 5 (live 4-case rerun) 鉁? **4/4 product_pass** 鈥?case1 Hefei (PASS,
  9src/48ev), case2 robot (PASS, 25/50), case3 NEV (PASS, 24/45), case4 coal
  (HUMAN_REVIEW draft, 31/50). Reports are genuine syntheses (region tables,
  transmission chains, data-gap labels), not ledgers. Sample:
  `data/tmp/depth_track_case1c/FINAL_REPORT.md` (5279 chars, 11 sections).
- Phase 6 鉁? graph_v1 REMAINS OPT-IN. Follow-up needed: reconstruct
  `real_nodes.py` from recovery-proxy to first-class source before default
  promotion; refine `estimate_token_count` to the curated digest; update 2 stale
  editor1 tests to the Chinese LLM-report contract.

**Track 2: Subsystem A 鈥?Search/Retrieval Infrastructure Upgrade** 鉁?
- Phase A1-A3 complete: chunk quality, hybrid search, caliber expansion

**Track 3: Subsystem B 鈥?Editor1 LLM Report + Content Depth** 鉁?
- build_claims LLM supplement to 鈮? claims
- Editor1 always LLM (skip bytecode)
- LLM prompt: full Chinese research report (4000-6000 chars)

**Track 4: Subsystem C 鈥?Dossier i18n + Context Pack I/O** 鉁?
- Dossier fully Chinese
- Context pack full IO snapshots per node (state before/after in details blocks)

graph_v1 stays **opt-in**. Remaining quality gaps (over_budget_context_packs)
are bytecode-level issues.

## Primary Active Plan

WS2 cleanup (2026-06-21): the readable-report remediation PLAN is COMPLETE and
archived (`archive/deep-research-readable-report-remediation-v1.md`, depth track
4/4 product_pass). Active dir reduced 25 鈫?10 PLANs; INDEX.md resynced.

Current primary active work line: **Tavily recall + search-caliber for
location-sensitive deep-research** (Track 0 above, ADR 0001 鈥?all 4 root causes
fixed and live-validated: Hefei recall 0鈫?/20, report 鍚堣偉 60x vs 澶栧湴 23x).

Active PLANs (in execution):
- `.agent/PLANS/search-caliber-expansion-v1.md` 鈥?`active_phase2_graph_integration`
- `.agent/PLANS/research-product-v1.md` 鈥?`active_phase1_report_persistence`
- `.agent/PLANS/source-local-procurement-regulatory-depth-v1.md` 鈥?`active_phase1_completed_pending_targeted_gate`

Active reference (Phase-0 contracts): `deep-research-report-rubric-v1`,
`deep-research-agent-contract-matrix-v1`, `deep-research-memory-contract-v1`,
`langgraph-v1-promotion-gate-v1`.

Pending human review: `agentic-operating-system-v2`, `source-quality-scoring-v2`,
`langgraph-research-workflow-harness-v1`.

Archived completed remediation (reference): the readable-report depth track
(Phases 1-9 + 4/4 live product_pass) is in
`archive/deep-research-readable-report-remediation-v1.md`.
- Primary area: `research_workflow`
- Secondary areas: `content_factory`, `eval_policy_ops`, `provider_layer`,
  `source_layer`, `task_substrate`, `delivery_layer`

## Completed / Superseded Plans

- `.agent/PLANS/deep-research-readable-report-quality-v2.md` 鈫?superseded_partial_quality_gate_failed
- `docs/session-trace-2026-06-17.md` 鈫?superseded_by_remediation_plan (historical only, has errata)

## Latest Validation Snapshot

Re-run 4 live cases (2026-06-17, `data/tmp/remediation_final`):
- case1_hefei: HUMAN_REVIEW (gate correctly blocked on obl_policy_primary)
- case2_robot: PASS workflow, 8/9 checks, report/audit separated, ratio=1.0 鈥?product_fail (over_budget_context_packs)
- case3_nev: PASS workflow, 8/9 checks, report/audit separated, ratio=1.0 鈥?product_fail (over_budget_context_packs)
- case4_coal: PASS workflow, 7/9 checks, report/audit separated 鈥?product_fail (body_ratio + over_budget_context_packs)

All four cases remain `workflow_pass_product_fail`. The gate correctly blocks
case1, but 3/4 cases pass workflow while failing product quality.

Tests:
- quality_inspect: 16/16 passed
- finalize/report_markdown: 5/5 passed (fixed 2026-06-17, was 1/5)
- gate subset (chief_gate/obligation/source_family): 4/5 passed (1 pre-existing location-action gap)
- editor1: 3/3 passed

## Remaining Known Gaps

- `p0_review_issue_count` still >0 in all cases (section_role mismatch from bytecode)
- `limitations_truncated` still >3 (bytecode truncation)
- `over_budget_context_packs` still >5 (context pack sizing in bytecode)
- case1 gate correctly blocks but report is empty (by design 鈥?no finalize on HUMAN_REVIEW)

## Corrected Historical State

Previous false claims corrected 2026-06-17:

- STATUS previously claimed "remediation cycle completed" and "No active long-running PLAN"
  while simultaneously listing Primary Active Plan with active blockers. Now unified:
  remediation PLAN is active, Phase 3 just completed, Phase 4/5 pending.
- PLAN previously claimed `completed_keep_opt_in_with_documented_gaps` while
  Done Condition requires Phase 4 and 5 completion. Now marked `active_phase3_completed_phase4_pending`.
- Test claim "finalize 5/5" was false (was 1/5). Now genuinely 5/5 after Phase 3 fix.
- Live quality claim "3 product PASS + 1 闃绘柇" was false. All 4 cases are
  `workflow_pass_product_fail`. Corrected.

## Current Blockers

- P0 review issues (section_role mismatch) not yet gate-consumable (Phase 4)
- Context pack budget overage not yet addressed (bytecode-level)
- Live product gate rerun not yet performed (Phase 5)

## Recommended Next Action

Phase 4: Make Editor2 / verifier P0 issues gate-consumable so that
section_role mismatch, low source diversity, source family mismatch,
and unresolved critical limitations affect final gate decisions.

```powershell
pytest -q tests\test_research_harness_graph.py -k "editor2 or verifier or chief_gate"
```

## Current Authoritative Handoff Update (2026-07-10 Report Coverage Smoke Pressure)

Primary active PLAN:

- `.agent/PLANS/report-coverage-smoke-pressure-v1.md`
- Status: `active_pressure_run_completed_with_recovery_blocker`
- Primary area: `eval_policy_ops`
- Secondary areas: `research_workflow`, `source_layer`, `provider_layer`

Latest validation:

- Created 50-query full set: `data/evals/report_coverage_50_queries_v1.json`.
- Created 8-query smoke set: `data/evals/report_coverage_smoke_8_queries_v1.json`.
- Created pressure runner: `data/tmp/_run_report_coverage_smoke_pressure.py`.
- Dry-run passed for 8 cases.
- Live run completed: `data/tmp/report_coverage_smoke_pressure_v1/run_20260710_1736`.
- Raw runner result: 4 normal succeeded summaries (`M02`, `M03`, `P08`, `C01`) and 4 process failures (`P04`, `C07`, `K07`, `K12`).
- Process failure root cause: missing `ResearchReportService.update_dossier_path`.
- Created recovery script: `data/tmp/_recover_report_coverage_pressure_artifacts.py`.
- Artifact recovery produced 8/8 `dossier.md` and 8/8 `FINAL_REPORT.md`.
- Recovery summary: `data/tmp/report_coverage_smoke_pressure_v1/run_20260710_1736/artifact_recovery_summary.json`.

Next recommended action:

1. Repair report persistence/export blocker:
   - restore `dossier_path` support in `packages/research_reports/schemas.py` and `packages/research_reports/service.py`;
   - implement `ResearchReportService.update_dossier_path()`;
   - make `scripts/graph_provider_backed_smoke.py` export `FINAL_REPORT.md` directly.
2. Rerun failed normal-summary cases `P04`, `C07`, `K07`, `K12` without recovery.
3. Only after the normal path produces 8/8 dossier and final report should the full 50-query run be considered.
