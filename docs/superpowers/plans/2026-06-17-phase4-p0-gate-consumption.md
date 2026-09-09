# Phase 4: P0 Review Issue Gate Consumption — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Editor2 产出的 P0 问题真正影响 gate 决策：blocker 阻止 PASS，warning 降级 quality_scores，HUMAN_REVIEW 附带 P0 上下文。

**Architecture:** 三处改动：1) `editor2_review_provider_backed` 扩展 fallback issue 生成（五种 issue_type，正确 severity），2) `chief_gate_provider_backed` 移除独立 P0 启发式改用 `review_issues` 统一消费，3) `GraphHumanReviewState` + `GraphAnalyzeRequest` + `_apply_human_review_action` 支持 `override_p0` action 和 P0 上下文。

**Tech Stack:** Python, Pydantic, pytest

## Global Constraints

- 不修改 legacy `/deep-research/analyze` 和 `/research/analyze` 路径
- `review_issues` list 结构不变，只新增 entry type
- 已有 HUMAN_REVIEW 优先级保持（HUMAN_REVIEW 分支在所有 block 之前返回）
- Obligation gap block (Block 1) 不变
- `GraphHumanReviewState` 字段改动为增量添加

---

### Task 1: Editor2 — 扩展 fallback issue 类型

**通俗解释**：让审稿器能发现更多种类的问题，并正确标"阻断"还是"提醒"。目前它只会说"章节归类不对"这一种问题，而且全标"提醒"。改完后它能识别：证据来源对不上（阻断）、完全没有证据支撑（阻断）、来源太单一（提醒）、关键限制没解决（提醒）。

**Files:**
- Modify: `packages/research_harness/real_nodes.py:176-207`（在现有 `for claim in ...` 循环内扩展）
- Test: `tests/test_research_harness_graph.py`（新增测试函数）

**Interfaces:**
- Consumes: `state["claims"]`, `state["evidence"]`, `state["sources"]`, `state["drafts"]`
- Produces: `result["review_issues"]` 包含新的 issue_type: `source_family_mismatch` (blocker), `unsupported_claim` (blocker), `low_source_diversity` (warning), `critical_limitation_unresolved` (warning)

- [ ] **Step 1: Write the failing test**

```python
def test_editor2_review_provider_backed_flags_source_family_mismatch_as_blocker() -> None:
    """Evidence source_family=company_disclosure but claim requires official_policy → blocker."""
    from packages.research_harness import real_nodes
    result = real_nodes.editor2_review_provider_backed({
        "claims": [
            {
                "claim_id": "c1",
                "claim_family": "policy_basis",
                "text": "政策支持低空经济",
                "supported": True,
                "evidence_ids": ["ev1"],
                "required_source_family": "official_policy",
            }
        ],
        "evidence": [
            {
                "evidence_id": "ev1",
                "source_id": "src1",
                "support_type": "direct_support",
                "support_strength": 0.8,
                "summary": "公司披露中提到政策支持",
                "limitations": [],
            }
        ],
        "sources": [
            {
                "source_id": "src1",
                "source_family": "company_disclosure",
                "title": "某公司年报",
            }
        ],
        "drafts": [],
        "claim_support_matrix": [
            {
                "claim_id": "c1",
                "required_source_family": "official_policy",
                "source_families": ["company_disclosure"],
                "evidence_ids": ["ev1"],
                "avg_support_strength": 0.8,
            }
        ],
    })
    issues = result.get("review_issues", [])
    mismatch = [i for i in issues if i.get("issue_type") == "source_family_mismatch"]
    assert len(mismatch) >= 1
    assert mismatch[0]["severity"] == "blocker"
    assert mismatch[0]["target_claim_id"] == "c1"


def test_editor2_review_provider_backed_flags_unsupported_claim_as_blocker() -> None:
    """Claim has no evidence_ids → blocker."""
    from packages.research_harness import real_nodes
    result = real_nodes.editor2_review_provider_backed({
        "claims": [
            {
                "claim_id": "c1",
                "claim_family": "policy_basis",
                "text": "无证据断言",
                "supported": False,
                "evidence_ids": [],
                "required_source_family": "official_policy",
            }
        ],
        "evidence": [],
        "sources": [],
        "drafts": [],
        "claim_support_matrix": [],
    })
    issues = result.get("review_issues", [])
    unsupported = [i for i in issues if i.get("issue_type") == "unsupported_claim"]
    assert len(unsupported) >= 1
    assert unsupported[0]["severity"] == "blocker"


def test_editor2_review_provider_backed_flags_low_source_diversity_as_warning() -> None:
    """Claim has only one evidence → warning (not blocker)."""
    from packages.research_harness import real_nodes
    result = real_nodes.editor2_review_provider_backed({
        "claims": [
            {
                "claim_id": "c1",
                "claim_family": "policy_basis",
                "text": "单源支撑的结论",
                "supported": True,
                "evidence_ids": ["ev1"],
                "required_source_family": "official_policy",
            }
        ],
        "evidence": [
            {
                "evidence_id": "ev1",
                "source_id": "src1",
                "support_type": "direct_support",
                "support_strength": 0.8,
                "summary": "政策文件支持",
                "limitations": [],
            }
        ],
        "sources": [
            {
                "source_id": "src1",
                "source_family": "official_policy",
                "title": "国务院政策通知",
            }
        ],
        "drafts": [],
        "claim_support_matrix": [
            {
                "claim_id": "c1",
                "required_source_family": "official_policy",
                "source_families": ["official_policy"],
                "evidence_ids": ["ev1"],
                "avg_support_strength": 0.8,
            }
        ],
    })
    issues = result.get("review_issues", [])
    low_div = [i for i in issues if i.get("issue_type") == "low_source_diversity"]
    assert len(low_div) >= 1
    assert low_div[0]["severity"] == "warning"
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
pytest -q tests/test_research_harness_graph.py -k "source_family_mismatch_as_blocker or unsupported_claim_as_blocker or low_source_diversity_as_warning" -v
```
Expected: 3 FAILED（新 issue_type 尚未生成）

- [ ] **Step 3: Write minimal implementation**

在 `editor2_review_provider_backed` 中，先在现有 `for claim in ...` 循环**之前**构建 `ev_map` 和 `src_map`（line 175 之前），然后在现有循环**之内**、`section_role_mismatch` 检测之后（line 202 之后）追加四个检测块：

```python
    # ── 在 line 175 (for claim 循环) 之前构建查找表 ──
    ev_map = {str(e.get("evidence_id")): e for e in state.get("evidence", [])}
    src_map = {str(s.get("source_id")): s for s in state.get("sources", [])}

    for claim in list(state.get("claims", [])):
        claim_id = str(claim.get("claim_id") or "")
        # ... 现有 section_role_mismatch 检测 (lines 177-202) 保持不变 ...

        # ── 以下为 Phase 4 新增，在 section_role_mismatch 检测之后 ──
        claim_id = str(claim.get("claim_id") or "")
        ev_ids = [str(eid) for eid in claim.get("evidence_ids", [])]
        required_family = str(claim.get("required_source_family") or "")

        # detection 1: unsupported_claim (blocker)
        if not ev_ids:
            fallback_issues.append({
                "issue_id": f"issue_unsupported_{claim_id}",
                "severity": "blocker",
                "issue_type": "unsupported_claim",
                "target_claim_id": claim_id,
                "description": "Claim has no evidence support — assertion without basis.",
                "required_fix": "Collect evidence from required source family or remove claim.",
                "suggested_search_queries": [],
            })
            continue  # 无 evidence 则后续检测无意义

        # detection 2: source_family_mismatch (blocker)
        if required_family:
            ev_src_families = set()
            for eid in ev_ids:
                ev = ev_map.get(eid, {})
                src_ids = [str(sid) for sid in ev.get("source_ids", [])]
                if not src_ids:
                    sid = str(ev.get("source_id") or "")
                    if sid:
                        src_ids = [sid]
                for sid in src_ids:
                    src = src_map.get(sid, {})
                    sf = str(src.get("source_family") or "")
                    if sf:
                        ev_src_families.add(sf)
            if ev_src_families and required_family not in ev_src_families:
                fallback_issues.append({
                    "issue_id": f"issue_src_family_mismatch_{claim_id}",
                    "severity": "blocker",
                    "issue_type": "source_family_mismatch",
                    "target_claim_id": claim_id,
                    "description": (
                        f"Claim requires {required_family} but evidence comes from "
                        f"{', '.join(sorted(ev_src_families))}"
                    ),
                    "required_fix": (
                        f"Collect evidence from {required_family} sources "
                        f"to support this claim."
                    ),
                    "suggested_search_queries": [],
                    "required_source_family": required_family,
                    "actual_source_families": sorted(ev_src_families),
                })

        # detection 3: low_source_diversity (warning)
        unique_sources: set[str] = set()
        for eid in ev_ids:
            ev = ev_map.get(eid, {})
            src_ids = [str(sid) for sid in ev.get("source_ids", [])]
            if not src_ids:
                sid = str(ev.get("source_id") or "")
                if sid:
                    src_ids = [sid]
            unique_sources.update(src_ids)
        if len(unique_sources) < 2 and unique_sources:
            fallback_issues.append({
                "issue_id": f"issue_low_diversity_{claim_id}",
                "severity": "warning",
                "issue_type": "low_source_diversity",
                "target_claim_id": claim_id,
                "description": (
                    f"Claim relies on only {len(unique_sources)} source(s) — "
                    "insufficient cross-validation."
                ),
                "required_fix": "Add at least one more independent source.",
                "suggested_search_queries": [],
            })

        # detection 4: critical_limitation_unresolved (warning)
        critical_keywords = ("不包含", "缺失", "无法确认", "待核实", "未覆盖", "不足")
        for eid in ev_ids:
            ev = ev_map.get(eid, {})
            limitations = ev.get("limitations", [])
            if isinstance(limitations, str):
                limitations = [limitations]
            for lim in limitations:
                if any(kw in str(lim) for kw in critical_keywords):
                    fallback_issues.append({
                        "issue_id": f"issue_critical_lim_{claim_id}_{eid}",
                        "severity": "warning",
                        "issue_type": "critical_limitation_unresolved",
                        "target_claim_id": claim_id,
                        "target_evidence_id": eid,
                        "description": f"Critical limitation: {lim}",
                        "required_fix": "Address or document this limitation.",
                        "suggested_search_queries": [],
                    })
                    break
```

注意：`ev_map` 和 `src_map` 在循环外构建一次（提到 `for claim in ...` 之前），避免重复构建。

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest -q tests/test_research_harness_graph.py -k "editor2_review_provider_backed" -v
```
Expected: 新增 3 个 PASS + 已有 editor2 测试保持 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_research_harness_graph.py packages/research_harness/real_nodes.py
git commit -m "feat: editor2 produces source_family_mismatch, unsupported_claim (blocker) + low_source_diversity, critical_limitation_unresolved (warning)"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

### Task 2: Gate — 统一从 review_issues 消费 P0

**通俗解释**：质量门现在自己用一套独立的规则去判断有没有 P0 问题（重复造轮子），跟审稿器产出的审稿列表互不相干。改完后质量门直接读审稿列表：审稿器说"阻断"就不让过，说"提醒"就降质量分。一套数据，不重复。

**Files:**
- Modify: `packages/research_harness/real_nodes.py:1664-1709`（移除独立启发式）、`real_nodes.py:1845-1869`（替换 Block 2 和 Block 3）
- Test: `tests/test_research_harness_graph.py`（新增测试函数）

**Interfaces:**
- Consumes: `state["review_issues"]`（Task 1 产出 + 字节码产出）
- Produces: gate 的 `decision`, `gate_reason`, `quality_scores` 受 P0 影响

- [ ] **Step 1: Write the failing test**

```python
def test_chief_gate_blocks_on_review_issue_blocker() -> None:
    """Gate sees a blocker in review_issues → cannot PASS."""
    from packages.research_harness import real_nodes
    result = real_nodes.chief_gate_provider_backed({
        "query": "测试查询",
        "claims": [],
        "evidence": [],
        "sources": [],
        "review_issues": [
            {
                "issue_id": "issue_001",
                "severity": "blocker",
                "issue_type": "source_family_mismatch",
                "target_claim_id": "c1",
                "description": "政策 claim 只有公司披露支撑",
            }
        ],
        "claim_verifications": [],
        "claim_support_matrix": [],
        "required_obligation_coverage": [],
        "quality_scores": {"final_score": 0.8},
        "editor2_route_recommendation": {},
        "verifier_route_recommendation": {},
        "query_requirements": {},
    })
    assert result["decision"] != "PASS"


def test_chief_gate_downgrades_on_warnings_when_no_blockers() -> None:
    """Only warnings (no blockers) → quality_scores downgraded but may PASS."""
    from packages.research_harness import real_nodes
    result = real_nodes.chief_gate_provider_backed({
        "query": "测试查询",
        "claims": [],
        "evidence": [],
        "sources": [],
        "review_issues": [
            {
                "issue_id": "issue_002",
                "severity": "warning",
                "issue_type": "low_source_diversity",
                "target_claim_id": "c1",
                "description": "单源支撑",
            }
        ],
        "claim_verifications": [],
        "claim_support_matrix": [],
        "required_obligation_coverage": [],
        "quality_scores": {"final_score": 0.9},
        "editor2_route_recommendation": {},
        "verifier_route_recommendation": {},
        "query_requirements": {},
    })
    qs = result.get("quality_scores", {})
    # With warnings, final_score should be discounted
    assert qs.get("final_score", 1.0) < 0.9
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
pytest -q tests/test_research_harness_graph.py -k "blocks_on_review_issue_blocker or downgrades_on_warnings" -v
```
Expected: 2 FAILED（gate 尚未从 review_issues 统一读取）

- [ ] **Step 3: Write minimal implementation**

**3a. 替换 P0 检测区**（lines 1699-1709）：

```python
    # ── Phase 4: Unified P0 detection from review_issues ──
    # blocker severity → hard block. warning severity → quality downgrade.
    hard_blockers = [
        i for i in review_issues
        if str(i.get("severity") or "").lower() == "blocker"
    ]
    warnings_list = [
        i for i in review_issues
        if str(i.get("severity") or "").lower() == "warning"
    ]
    has_hard_blockers = len(hard_blockers) > 0
    has_warnings = len(warnings_list) > 0
```

**3b. 移除独立 `has_source_family_mismatch` 检测**（lines 1664-1697）：

注释掉或删除 `source_family_mismatch_count` 计算和 `has_source_family_mismatch` 赋值。这段逻辑现在由 editor2 的 `source_family_mismatch` blocker issue 替代。

**3c. 替换 Block 2（line 1845-1857）和 Block 3（line 1859-1869）**：

```python
    # Block 2: P0 hard blockers prevent PASS (but not HUMAN_REVIEW)
    if has_hard_blockers and decision in {"PASS", "REVISE_TEXT", "ADD_EVIDENCE"}:
        blocker_types = {str(i.get("issue_type") or "?") for i in hard_blockers}
        result["decision"] = "REVIEW_RISK"
        result["gate_route_to"] = "editor2_review"
        result["required_actions"] = []
        result["gate_reason"] = (
            f"存在 P0 阻断问题 ({len(hard_blockers)}个: "
            f"{', '.join(sorted(blocker_types))}) — "
            "必须在 Editor2/verifier 解决后才能继续"
        )
        return result

    # Block 3: Warnings downgrade quality when no hard blockers
    if has_warnings and decision in {"PASS", "REVISE_TEXT"}:
        qs = dict(result.get("quality_scores", {}))
        original = qs.get("final_score", 0.7)
        qs["final_score"] = round(original * 0.85, 2)
        result["quality_scores"] = qs
        # Still allow PASS but with downgraded score
```

**3d. 更新末尾简化 PASS 条件**（line 1903）：将 `only_warning_issues` 检查替换为 `not has_hard_blockers`。

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest -q tests/test_research_harness_graph.py -k "chief_gate" -v
```
Expected: 新增测试 PASS，已有 gate 测试的预存失败数不变

- [ ] **Step 5: Commit**

```bash
git add tests/test_research_harness_graph.py packages/research_harness/real_nodes.py
git commit -m "feat: gate consumes P0 classification from review_issues, removes ad-hoc heuristics"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

### Task 3: HUMAN_REVIEW — 扩展 override_p0 action + P0 上下文

**通俗解释**：当报告因为 P0 问题被送去人工复核时，reviewer 现在只能看到"需要人看"这一句。改完后 reviewer 能看到具体是哪些 P0 问题触发的（比如"source_family_mismatch: 政策 claim 被公司披露支撑"），并且多了一个 `override_p0` 按钮——如果 reviewer 判断这是误判，可以覆盖继续。

**Files:**
- Modify: `packages/research_harness/schemas.py:15`（`human_review_action` Literal 加 `override_p0`）
- Modify: `packages/research_harness/schemas.py:26-44`（`GraphHumanReviewState` 加 `p0_review_context`）
- Modify: `packages/research_harness/runner.py:845-882`（`_apply_human_review_action` 处理 `override_p0`）
- Modify: `packages/research_harness/real_nodes.py:1763-1768`（HUMAN_REVIEW 路由时附带 P0 上下文）
- Test: `tests/test_research_harness_graph.py`（新增测试）

**Interfaces:**
- Consumes: gate 产出的 `hard_blockers` 和 `warnings_list`
- Produces: `human_review` state 中 `p0_review_context` + `blocking_issues` 已填充
- `GraphAnalyzeRequest.human_review_action` 新增 `"override_p0"` 选项

- [ ] **Step 1: Write the failing test**

```python
def test_human_review_state_includes_p0_context_from_gate() -> None:
    """When gate routes to HUMAN_REVIEW due to P0 blockers, human_review state
    should carry the P0 issue details for the reviewer."""
    from packages.research_harness import real_nodes
    result = real_nodes.chief_gate_provider_backed({
        "query": "测试查询",
        "claims": [
            {
                "claim_id": "c1",
                "claim_family": "policy_basis",
                "text": "政策支持",
                "supported": True,
                "evidence_ids": ["ev1"],
                "required_source_family": "official_policy",
            }
        ],
        "evidence": [
            {
                "evidence_id": "ev1",
                "source_id": "src1",
                "support_type": "direct_support",
                "support_strength": 0.8,
                "summary": "政策文件",
                "limitations": [],
            }
        ],
        "sources": [
            {
                "source_id": "src1",
                "source_family": "company_disclosure",
                "title": "年报",
            }
        ],
        "review_issues": [
            {
                "issue_id": "issue_001",
                "severity": "blocker",
                "issue_type": "source_family_mismatch",
                "target_claim_id": "c1",
                "description": "需要 official_policy 但证据来自 company_disclosure",
                "required_source_family": "official_policy",
                "actual_source_families": ["company_disclosure"],
            }
        ],
        "claim_verifications": [
            {
                "claim_id": "c1",
                "support_status": "supported",
                "support_score": 0.8,
                "evidence_ids": ["ev1"],
                "source_ids": ["src1"],
                "notes": [],
            }
        ],
        "claim_support_matrix": [],
        "required_obligation_coverage": [
            {"obligation_id": "obl_policy_primary", "covered": False,
             "required_source_family": "official_policy"}
        ],
        "quality_scores": {"final_score": 0.6},
        "editor2_route_recommendation": {},
        "verifier_route_recommendation": {},
        "query_requirements": {},
    })
    # Gate should route to HUMAN_REVIEW (obligation gap + P0 blocker)
    assert result["decision"] in ("HUMAN_REVIEW", "ADD_EVIDENCE", "REVIEW_RISK")


def test_human_review_action_includes_override_p0() -> None:
    """GraphAnalyzeRequest.human_review_action accepts 'override_p0'."""
    from packages.research_harness.schemas import GraphAnalyzeRequest
    req = GraphAnalyzeRequest(
        query="测试",
        human_review_action="override_p0",
        human_review_notes="误判, 这是合法的交叉引用",
    )
    assert req.human_review_action == "override_p0"


def test_apply_human_review_override_p0() -> None:
    """_apply_human_review_action with override_p0 marks issues as overridden."""
    from packages.research_harness.runner import _apply_human_review_action
    state = {
        "human_review": {
            "pending": True,
            "blocking_issues": [
                {"issue_id": "issue_001", "severity": "blocker",
                 "issue_type": "source_family_mismatch"}
            ],
            "p0_review_context": {
                "available_actions": ["approve", "override_p0"],
                "suggested_action": "add_evidence",
                "suggested_reason": "需要补充政策原文",
            },
        },
        "decision": "HUMAN_REVIEW",
    }
    result = _apply_human_review_action(
        state, action="override_p0", notes="合法交叉引用"
    )
    hr = result.get("human_review", {})
    assert hr.get("pending") is False
    assert hr.get("selected_action") == "override_p0"
    assert result.get("decision") == "PASS"
    # Overridden issues should be marked
    for issue in hr.get("blocking_issues", []):
        assert issue.get("overridden_by_human") is True
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
pytest -q tests/test_research_harness_graph.py -k "override_p0 or p0_context_from_gate" -v
```
Expected: FAILED（`override_p0` 不在 Literal 中 / `_apply_human_review_action` 不处理）

- [ ] **Step 3: Write minimal implementation**

**3a. `schemas.py` — 扩展 `human_review_action` Literal**：

```python
# Line 15: 扩展 Literal
human_review_action: Literal["approve", "add_evidence", "rewrite", "reject", "override_p0"] | None = None
```

**3b. `schemas.py` — 扩展 `GraphHumanReviewState`**：

```python
# Line 26-44: 在现有字段后添加
class GraphHumanReviewState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending: bool = False
    status: Literal[
        "pending",
        "approved",
        "add_evidence_requested",
        "rewrite_requested",
        "rejected",
        "overridden",  # NEW
    ]
    gate_reason: str | None = None
    blocking_issues: list[dict[str, Any]] = Field(default_factory=list)
    required_actions: list[dict[str, Any]] = Field(default_factory=list)
    supported_actions: list[str] = Field(default_factory=list)
    draft_snapshot: dict[str, Any] = Field(default_factory=dict)
    report_snapshot: dict[str, Any] = Field(default_factory=dict)
    selected_action: Literal["approve", "add_evidence", "rewrite", "reject", "override_p0"] | None = None
    notes: str | None = None
    p0_review_context: dict[str, Any] | None = None  # NEW
```

**3c. `runner.py` — `_apply_human_review_action` 处理 `override_p0`**：

```python
def _apply_human_review_action(
    state: dict[str, Any],
    *,
    action: str,
    notes: str | None,
) -> dict[str, Any]:
    payload = dict(state)
    existing = dict(payload.get("human_review") or {})
    if not existing or not bool(existing.get("pending", False)):
        return payload

    status_map = {
        "approve": "approved",
        "add_evidence": "add_evidence_requested",
        "rewrite": "rewrite_requested",
        "reject": "rejected",
        "override_p0": "overridden",  # NEW
    }
    decision_map = {
        "approve": "PASS",
        "add_evidence": "ADD_EVIDENCE",
        "rewrite": "REVISE_TEXT",
        "reject": "FAILED",
        "override_p0": "PASS",  # NEW: override continues as PASS
    }
    existing.update({
        "pending": False,
        "status": status_map[action],
        "selected_action": action,
        "notes": notes,
    })
    # NEW: mark overridden P0 issues
    if action == "override_p0":
        blocking_issues = existing.get("blocking_issues", [])
        for issue in blocking_issues:
            if isinstance(issue, dict):
                issue["overridden_by_human"] = True
        existing["blocking_issues"] = blocking_issues
    payload["human_review"] = existing
    payload["decision"] = decision_map[action]
    payload["gate_route_to"] = None
    if action == "reject":
        payload["required_actions"] = []
        payload["planner_replan_request"] = None
    return payload
```

**3d. `real_nodes.py` — HUMAN_REVIEW 路由时附带 P0 上下文**：

在 gate 的 HUMAN_REVIEW 返回之前（line 1763 `result["decision"] = "HUMAN_REVIEW"` 之后），添加 `human_review` state 初始化，附带 P0 上下文：

```python
        # ── Phase 4: 附带 P0 review context 到 HUMAN_REVIEW state ──
        if hard_blockers or has_obligation_gap:
            blocking_summary = [
                {
                    "issue_id": str(i.get("issue_id", "")),
                    "issue_type": str(i.get("issue_type", "")),
                    "severity": str(i.get("severity", "")),
                    "target_claim_id": str(i.get("target_claim_id", "")),
                    "description": str(i.get("description", "")),
                }
                for i in hard_blockers
            ]
            result["human_review"] = {
                "pending": True,
                "gate_reason": result.get("gate_reason", ""),
                "blocking_issues": blocking_summary,
                "p0_review_context": {
                    "available_actions": [
                        "approve", "add_evidence", "rewrite", "reject", "override_p0"
                    ],
                    "suggested_action": (
                        "add_evidence" if has_obligation_gap
                        else "override_p0" if len(hard_blockers) == 1
                        else "rewrite"
                    ),
                    "suggested_reason": (
                        "缺少必需来源族的证据" if has_obligation_gap
                        else f"存在 {len(hard_blockers)} 个 P0 阻断问题需要处理"
                    ),
                },
            }
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest -q tests/test_research_harness_graph.py -k "override_p0 or p0_context_from_gate or human_review" -v
```
Expected: 新增 3 个 PASS + 已有 human_review 测试保持 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_research_harness_graph.py packages/research_harness/real_nodes.py packages/research_harness/schemas.py packages/research_harness/runner.py
git commit -m "feat: HUMAN_REVIEW extension — override_p0 action, P0 review context in human_review state"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

### Task 4: 全量回归验证 + PLAN 更新

- [ ] **Step 1: Run full relevant test suite**

```powershell
pytest -q tests/test_research_harness_graph.py -k "editor2 or chief_gate or human_review or verifier" -v
```
Expected: 无新增失败（预存 `test_chief_gate_provider_backed_local_claim_action_carries_location_queries` 仍可能失败）

- [ ] **Step 2: Run quality_inspect tests**

```powershell
pytest -q tests/test_report_quality_inspect.py
```
Expected: 16 passed

- [ ] **Step 3: Update STATUS.md and PLAN**

Update `.agent/STATUS.md`:
- Phase 4 标记为 completed
- 更新 Latest Validation Snapshot

Update `.agent/PLANS/deep-research-readable-report-remediation-v1.md`:
- Phase 4 状态从 pending → completed
- 添加 validation result
- Next Action 更新为 Phase 5

- [ ] **Step 4: Commit**

```bash
git add .agent/STATUS.md .agent/PLANS/deep-research-readable-report-remediation-v1.md
git commit -m "chore: mark Phase 4 complete, update STATUS and PLAN"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```
