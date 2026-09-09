# Subsystem B: Editor1 LLM Report Writing + Content Depth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Editor1 用 LLM 直接撰写 5000-8000 字中文研报，build_claims LLM 补充到 ≥8 个 claim。

**Architecture:** 三处函数改动全在 `real_nodes.py`：`editor1_draft_provider_backed` 跳过 bytecode 直接调 LLM，`build_claims_provider_backed` claim < 8 时 LLM 补足，`_generate_real_editor1_draft` LLM prompt 改为完整研报撰写。

**Tech Stack:** Python, DeepSeek, call_tooling_json

## Global Constraints

- 不修改 legacy `/deep-research/analyze` 和 `/research/analyze`
- `graph_v1` 保持 opt-in
- `response.json` 结构不变（`report_markdown` 内容升级但字段不变）
- 已有 gate/editor2/human_review 逻辑不变
- build_claims 的 LLM 补充不删除字节码原始 claims
- 所有 LLM 失败时回退模板兜底

---

### Task 1: build_claims LLM Supplement

**通俗说明**：字节码通常只产出 5 个 claim。不够时让 LLM 从 evidence 列表中挖掘更多——每个 evidence 至少对应一个 claim，不同类型 evidence 产生不同类型 claim。

**Files:**
- Modify: `packages/research_harness/real_nodes.py:971-984`

**Interfaces:**
- Consumes: `state["evidence"]`, `state["sources"]`, 字节码产出的 `result["claims"]`
- Produces: `result["claims"]` ≥ 8 (or original if ≥8 or LLM failed)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_research_harness_graph.py — 追加
def test_build_claims_header_supplements_when_under_8() -> None:
    """When bytecode produces < 8 claims, LLM should supplement."""
    from packages.research_harness import real_nodes
    result = real_nodes.build_claims_provider_backed({
        "query": "2025年低空经济政策",
        "claims": [
            {"claim_id": "c1", "claim_family": "policy_basis",
             "text": "政策支持低空经济", "supported": True,
             "evidence_ids": ["ev1"], "required_source_family": "official_policy"},
            {"claim_id": "c2", "claim_family": "local_rollout",
             "text": "合肥项目落地", "supported": True,
             "evidence_ids": ["ev2"], "required_source_family": "official_policy"},
        ],
        "evidence": [
            {"evidence_id": "ev1", "source_id": "src1", "source_family": "official_policy",
             "support_type": "direct_support", "support_strength": 0.9,
             "summary": "国务院通知支持低空经济应用场景建设。", "limitations": []},
            {"evidence_id": "ev2", "source_id": "src2", "source_family": "official_policy",
             "support_type": "direct_support", "support_strength": 0.82,
             "summary": "合肥发布低空经济地方实施方案。", "limitations": []},
            {"evidence_id": "ev3", "source_id": "src3", "source_family": "company_disclosure",
             "support_type": "direct_support", "support_strength": 0.75,
             "summary": "亿航智能2025年报披露低空经济业务收入增长。", "limitations": []},
        ],
        "sources": [
            {"source_id": "src1", "source_family": "official_policy", "title": "国务院通知"},
            {"source_id": "src2", "source_family": "official_policy", "title": "合肥方案"},
            {"source_id": "src3", "source_family": "company_disclosure", "title": "亿航年报"},
        ],
    })
    claims = result.get("claims", [])
    assert len(claims) >= 3  # 2 original + 1 LLM supplement (at minimum)
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
python -m pytest tests/test_research_harness_graph.py::test_build_claims_header_supplements_when_under_8 -v
```
Expected: FAIL — assertion len(claims) >= 3 (currently only 2)

- [ ] **Step 3: Implement LLM supplement**

In `build_claims_provider_backed`, after enrichment, add:

```python
def build_claims_provider_backed(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    _sync_impl_dependencies()
    result = _impl.build_claims_provider_backed(state, tool_session=tool_session)
    claims = list(result.get("claims", []))
    evidence = list(state.get("evidence", []))
    if claims:
        enriched = _enrich_claim_semantics(claims=claims, evidence=evidence)
        result["claims"] = enriched
        claims = enriched

    # ── Phase B: LLM supplement when claim count too low ──
    if len(claims) < 8 and len(evidence) >= 3:
        existing_ids = {str(c.get("claim_id", "")) for c in claims}
        supplement = _llm_supplement_claims(
            query=str(state.get("query", "")),
            claims=claims,
            evidence=evidence,
            sources=list(state.get("sources", [])),
            existing_claim_ids=existing_ids,
        )
        if supplement:
            result["claims"] = [*claims, *supplement]
    return result


def _llm_supplement_claims(
    *,
    query: str,
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    existing_claim_ids: set[str],
) -> list[dict[str, Any]] | None:
    """Call LLM to generate additional claims from evidence when claim count < 8."""
    import json as _json
    from packages.research_harness.tooling.llm_agents import call_tooling_json

    existing_texts = "\n".join(
        f"- {c.get('claim_id')}: {c.get('text', '')}" for c in claims
    )
    evidence_texts = _json.dumps(
        [{"id": e.get("evidence_id"), "summary": e.get("summary", "")[:200],
          "source_family": e.get("source_family", "")} for e in evidence],
        ensure_ascii=False, indent=2,
    )

    prompt = (
        f"Query: {query}\n\n"
        f"已有 Claims (不要重复):\n{existing_texts}\n\n"
        f"可用 Evidence:\n{evidence_texts}\n\n"
        f"从上述 evidence 中挖掘 {8 - len(claims)} 个额外的研究断言(claims)。\n"
        f"要求:\n"
        f"- 每个 evidence 至少产生 1 个 claim\n"
        f"- official_policy evidence → policy_basis 或 local_rollout claim\n"
        f"- company_disclosure evidence → company_disclosure claim\n"
        f"- public_resource_transaction evidence → execution_evidence claim\n"
        f"- 每个 claim: claim_id(用 c_suppl_N 格式), text(中文, 完整句子), "
        f"claim_family, evidence_ids(对应证据ID), required_source_family, supported=true\n"
        f"- 避免与已有 claim 重复\n"
        f"输出 JSON 数组: [{{...}}, ...]"
    )

    try:
        llm_result = call_tooling_json(
            system_prompt="你是一个研究分析师。从证据中提取额外的研究断言。",
            user_prompt=prompt,
            enable_thinking=False,
        )
        if llm_result and isinstance(llm_result.payload, list):
            new_claims = []
            for item in llm_result.payload:
                if not isinstance(item, dict):
                    continue
                cid = str(item.get("claim_id", ""))
                if cid in existing_claim_ids:
                    continue
                new_claims.append({
                    "claim_id": cid,
                    "text": str(item.get("text", "")),
                    "claim_family": str(item.get("claim_family", "analysis")),
                    "supported": True,
                    "evidence_ids": list(item.get("evidence_ids", [])),
                    "required_source_family": str(item.get("required_source_family", "")),
                    "_source": "llm_supplement",
                })
            return new_claims if new_claims else None
    except Exception:
        return None
    return None
```

- [ ] **Step 4: Run tests**

```powershell
python -m pytest tests/test_research_harness_graph.py -k "build_claims" -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/research_harness/real_nodes.py tests/test_research_harness_graph.py
git commit -m "feat: build_claims LLM supplement to ≥8 claims"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

### Task 2: editor1_draft_provider_backed → Always LLM

**通俗说明**：编辑器不再走字节码，直接调 LLM 写报告。只有 LLM 失败才用模板兜底。

**Files:**
- Modify: `packages/research_harness/real_nodes.py:987-1006`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_research_harness_graph.py — 追加
def test_editor1_always_produces_llm_draft() -> None:
    """Editor1 should produce a real LLM draft, not bytecode output."""
    from packages.research_harness import real_nodes
    result = real_nodes.editor1_draft_provider_backed({
        "query": "2025年低空经济政策与项目证据",
        "claims": [
            {"claim_id": "c1", "claim_family": "policy_basis",
             "text": "政策支持低空经济", "supported": True,
             "evidence_ids": ["ev1"], "required_source_family": "official_policy"},
        ],
        "evidence": [
            {"evidence_id": "ev1", "source_id": "src1", "source_family": "official_policy",
             "support_type": "direct_support", "support_strength": 0.9,
             "summary": "国务院通知支持低空经济。", "limitations": []},
        ],
        "sources": [{"source_id": "src1", "title": "国务院通知"}],
        "drafts": [],
    })
    md = result.get("report_markdown", "")
    assert len(md) > 500
    assert "执行摘要" in md or "Executive Summary" in md or "低空经济" in md
```

- [ ] **Step 2: Run test**

```powershell
python -m pytest tests/test_research_harness_graph.py::test_editor1_always_produces_llm_draft -v
```

- [ ] **Step 3: Implement**

Replace `editor1_draft_provider_backed`:

```python
def editor1_draft_provider_backed(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    # ── Phase B: Always use LLM to write report, skip bytecode editor1 ──
    try:
        result = _generate_real_editor1_draft(state=state)
    except Exception:
        result = _build_minimal_draft_from_claims(
            query=str(state.get("query", "")),
            claims=list(state.get("claims", [])),
            evidence_items=list(state.get("evidence", [])),
            sources=list(state.get("sources", [])),
        )
        result = {"report_markdown": result[0], "sections": result[1]}

    # Fallback: if LLM output is too short, use template
    rm = str(result.get("report_markdown", ""))
    if len(rm) < 1500:
        fallback_md, fallback_sections = _build_minimal_draft_from_claims(
            query=str(state.get("query", "")),
            claims=list(state.get("claims", [])),
            evidence_items=list(state.get("evidence", [])),
            sources=list(state.get("sources", [])),
        )
        result["report_markdown"] = fallback_md
        result["sections"] = fallback_sections

    # Phase 3: Align section roles
    result = _align_section_roles_in_draft(state=state, result=result)
    return result
```

- [ ] **Step 4: Run tests**

```powershell
python -m pytest tests/test_research_harness_graph.py -k "editor1" -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/research_harness/real_nodes.py tests/test_research_harness_graph.py
git commit -m "feat: editor1 always uses LLM to write report, skip bytecode"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

### Task 3: Rewrite _generate_real_editor1_draft LLM Prompt

**通俗说明**：让 LLM prompt 从"帮忙填模板"变成"你是研究员，写一份完整中文研报"。5000-8000 字、8-10 section、分析性叙述、证据引用、交叉验证。

**Files:**
- Modify: `packages/research_harness/real_nodes.py:1055-1168`

- [ ] **Step 1: Write the failing test**

```python
def test_editor1_llm_report_has_analytical_depth() -> None:
    """LLM report should have more than just claim listing — analytical narrative."""
    from packages.research_harness import real_nodes
    result = real_nodes._generate_real_editor1_draft(state={
        "query": "2025年合肥低空经济政策与项目落地证据",
        "claims": [
            {"claim_id": "c1", "claim_family": "policy_basis",
             "text": "国务院发布低空经济支持政策", "supported": True,
             "evidence_ids": ["ev1"], "required_source_family": "official_policy"},
            {"claim_id": "c2", "claim_family": "local_rollout",
             "text": "合肥出台低空经济地方实施方案", "supported": True,
             "evidence_ids": ["ev2"], "required_source_family": "official_policy"},
            {"claim_id": "c3", "claim_family": "execution_evidence",
             "text": "合肥低空经济示范项目中标", "supported": True,
             "evidence_ids": ["ev3"], "required_source_family": "public_resource_transaction"},
            {"claim_id": "c4", "claim_family": "company_disclosure",
             "text": "亿航智能年报披露合肥业务", "supported": True,
             "evidence_ids": ["ev4"], "required_source_family": "company_disclosure"},
            {"claim_id": "c5", "claim_family": "policy_basis",
             "text": "民航局发布低空经济适航标准", "supported": True,
             "evidence_ids": ["ev5"], "required_source_family": "official_policy"},
            {"claim_id": "c6", "claim_family": "execution_evidence",
             "text": "合肥eVTOL试飞基地获批", "supported": True,
             "evidence_ids": ["ev6"], "required_source_family": "public_resource_transaction"},
            {"claim_id": "c7", "claim_family": "statistics_or_data",
             "text": "2025年低空经济市场规模达500亿", "supported": False,
             "evidence_ids": ["ev7"], "required_source_family": "statistics_or_data_release"},
            {"claim_id": "c8", "claim_family": "risk_assessment",
             "text": "低空经济政策落实存在地方差异风险", "supported": True,
             "evidence_ids": ["ev2", "ev8"], "required_source_family": "official_policy"},
        ],
        "evidence": [
            {"evidence_id": "ev1", "source_id": "src1", "source_family": "official_policy",
             "support_type": "direct_support", "support_strength": 0.95,
             "summary": "国务院通知支持低空经济", "limitations": []},
            {"evidence_id": "ev2", "source_id": "src2", "source_family": "official_policy",
             "support_type": "direct_support", "support_strength": 0.9,
             "summary": "合肥发布低空方案", "limitations": []},
            {"evidence_id": "ev3", "source_id": "src3", "source_family": "public_resource_transaction",
             "support_type": "direct_support", "support_strength": 0.85,
             "summary": "中标公告", "limitations": []},
            {"evidence_id": "ev4", "source_id": "src4", "source_family": "company_disclosure",
             "support_type": "direct_support", "support_strength": 0.8,
             "summary": "亿航年报", "limitations": []},
            {"evidence_id": "ev5", "source_id": "src5", "source_family": "official_policy",
             "support_type": "direct_support", "support_strength": 0.9,
             "summary": "民航局标准", "limitations": []},
            {"evidence_id": "ev6", "source_id": "src6", "source_family": "public_resource_transaction",
             "support_type": "direct_support", "support_strength": 0.85,
             "summary": "试飞基地获批", "limitations": []},
            {"evidence_id": "ev7", "source_id": "src7", "source_family": "statistics_or_data_release",
             "support_type": "background_support", "support_strength": 0.4,
             "summary": "市场规模估算", "limitations": ["数据来自行业估算非官方统计"]},
            {"evidence_id": "ev8", "source_id": "src8", "source_family": "official_policy",
             "support_type": "background_support", "support_strength": 0.6,
             "summary": "多地政策差异", "limitations": ["仅覆盖东部省份"]},
        ],
        "sources": [
            {"source_id": "src1", "title": "国务院通知", "source_family": "official_policy"},
            {"source_id": "src2", "title": "合肥方案", "source_family": "official_policy"},
            {"source_id": "src3", "title": "中标公告", "source_family": "public_resource_transaction"},
            {"source_id": "src4", "title": "亿航年报", "source_family": "company_disclosure"},
            {"source_id": "src5", "title": "民航局标准", "source_family": "official_policy"},
            {"source_id": "src6", "title": "试飞基地", "source_family": "public_resource_transaction"},
            {"source_id": "src7", "title": "市场估算", "source_family": "statistics_or_data_release"},
            {"source_id": "src8", "title": "政策差异", "source_family": "official_policy"},
        ],
        "drafts": [],
    })
    md = result.get("report_markdown", "")
    assert len(md) >= 2000  # Minimum length
```

- [ ] **Step 2: Run test**

```powershell
python -m pytest tests/test_research_harness_graph.py::test_editor1_llm_report_has_analytical_depth -v
```

- [ ] **Step 3: Rewrite the LLM prompt**

Replace the content inside `_generate_real_editor1_draft` — specifically the prompt building section (lines 1089-1096) — with the new research report prompt:

```python
    # ── Phase B: Build research report prompts ──
    import json as _json

    claims_json = _json.dumps(
        [{"id": c.get("claim_id"), "family": c.get("claim_family"),
          "text": c.get("text"), "supported": c.get("supported"),
          "evidence_count": len(c.get("evidence_ids", []))}
         for c in claims],
        ensure_ascii=False, indent=2,
    )
    evidence_json = _json.dumps(
        [{"id": e.get("evidence_id"), "source_family": e.get("source_family", ""),
          "support_strength": e.get("support_strength"),
          "summary": e.get("summary", "")[:300],
          "limitations": e.get("limitations", [])}
         for e in evidence_items],
        ensure_ascii=False, indent=2,
    )
    sources_json = _json.dumps(
        [{"id": s.get("source_id"), "title": s.get("title"),
          "source_family": s.get("source_family", ""),
          "url": s.get("url", "")}
         for s in sources[:20]],
        ensure_ascii=False, indent=2,
    )

    system_prompt = (
        "你是资深行业研究员，拥有10年行业研究经验。你的任务是基于提供的证据材料，"
        "撰写一份专业的中文深度研究报告。\n\n"
        "报告要求：\n"
        "1. 完整研报结构：标题、执行摘要、方法口径、各维度分析章节、风险与不确定性、结论与展望、来源说明\n"
        "2. 每个研究断言(claim)都要有分析性叙述——不只罗列证据，要解释其含义和重要性\n"
        "3. 发现不同证据之间的逻辑关联（如政策如何推动项目落地、公司披露如何验证政策效果）\n"
        "4. 明确标注证据局限性（单源支撑、行业估算非官方统计、覆盖范围有限等）\n"
        "5. 多证据支撑同一结论时要综合判断，而非简单罗列\n"
        "6. 中文撰写，专业但不晦涩，让非专业读者也能理解\n"
        "7. 报告长度 4000-6000 字（根据证据量自适应）\n\n"
        "章节结构：\n"
        "- # 标题（query主题）\n"
        "- ## 执行摘要（整体结论+3-5条关键发现）\n"
        "- ## 方法与口径（来源类型、时间/地域范围、推断边界）\n"
        "- ## 政策分析（政策维度claims+分析）\n"
        "- ## 地方落地与项目执行（如有相关claims）\n"
        "- ## 公司披露（如有相关claims）\n"
        "- ## 行业数据（如有相关claims）\n"
        "- ## 风险与不确定性（证据局限+推断风险+未覆盖面向）\n"
        "- ## 结论与展望（综合判断+后续关注方向）\n"
        "- ## 来源说明（来源表格）\n\n"
        "证据引用格式：在文中用 [ev_id] 标注证据来源。\n"
        "输出纯 Markdown 文本（不是 JSON），直接可发布。"
    )

    user_prompt = (
        f"请撰写研究报告。\n\n"
        f"研究问题: {query}\n\n"
        f"研究断言(Claims):\n{claims_json}\n\n"
        f"证据材料(Evidence):\n{evidence_json}\n\n"
        f"信息来源(Sources):\n{sources_json}\n\n"
        f"请输出完整的 Markdown 格式中文研报。"
    )
```

- [ ] **Step 4: Simplify the LLM call and post-processing**

Remove the complex `_merge_llm_into_structured_report` logic. Replace lines 1098-1144 with:

```python
    from packages.research_harness.tooling.llm_agents import call_tooling_json

    llm_result = call_tooling_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        enable_thinking=False,
    )

    # LLM may return the report in payload.report_markdown or as raw text
    llm_data = llm_result.payload if llm_result else None
    if isinstance(llm_data, dict):
        llm_markdown = str(llm_data.get("report_markdown") or llm_data.get("content") or "")
    elif isinstance(llm_data, str):
        llm_markdown = llm_data
    else:
        # LLM failed — use template
        structured_md, structured_sections = _build_minimal_draft_from_claims(
            query=query, claims=claims, evidence_items=evidence_items, sources=sources,
        )
        return {**fallback_result,
                "report_markdown": structured_md, "sections": structured_sections}

    if len(llm_markdown) < 1500:
        structured_md, structured_sections = _build_minimal_draft_from_claims(
            query=query, claims=claims, evidence_items=evidence_items, sources=sources,
        )
        return {**fallback_result,
                "report_markdown": structured_md, "sections": structured_sections}

    # Build sections from LLM content (parse ## headers)
    sections = _parse_markdown_sections(llm_markdown)

    draft_id = f"draft_{_uuid.uuid4().hex[:8]}"
    result = dict(fallback_result)
    result["draft_id"] = draft_id
    result["draft_version"] = draft_version
    result["report_markdown"] = llm_markdown
    result["sections"] = sections
    # ... rest of result assembly
```

Also add the helper `_parse_markdown_sections`:

```python
def _parse_markdown_sections(markdown: str) -> list[dict[str, Any]]:
    """Parse ## headers from LLM markdown into section dicts."""
    sections = []
    current_title = "正文"
    current_body: list[str] = []
    for line in markdown.split("\n"):
        if line.startswith("## "):
            if current_body:
                sections.append({
                    "section_id": f"sec_{len(sections)+1}",
                    "title": current_title,
                    "section_role": "analysis",
                    "argument_posture": "evidence_backed",
                    "markdown_body": "\n".join(current_body),
                    "paragraphs": [],
                })
            current_title = line[3:].strip()
            current_body = []
        else:
            current_body.append(line)
    if current_body:
        sections.append({
            "section_id": f"sec_{len(sections)+1}",
            "title": current_title,
            "section_role": "analysis",
            "argument_posture": "evidence_backed",
            "markdown_body": "\n".join(current_body),
            "paragraphs": [],
        })
    return sections
```

- [ ] **Step 5: Run tests**

```powershell
python -m pytest tests/test_research_harness_graph.py -k "editor1 or analytical_depth" -v
```

- [ ] **Step 6: Commit**

```bash
git add packages/research_harness/real_nodes.py tests/test_research_harness_graph.py
git commit -m "feat: editor1 LLM prompt — full Chinese research report, 4000-6000 chars"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

### Task 4: Regression + Live Smoke

- [ ] **Step 1: Full regression**

```powershell
pytest -q tests/test_research_harness_graph.py -k "editor1 or build_claims or editor2 or chief_gate" -v
pytest -q tests/test_report_quality_inspect.py -v
```

- [ ] **Step 2: Live smoke**

```powershell
python scripts/graph_provider_backed_smoke.py --query "2025年广东人形机器人产业政策与项目落地证据" --max-rounds 2 --output-dir "data/tmp/subsystem_b_smoke/case1" --env-file .env --reset
python scripts/report_quality_inspect.py --response "data/tmp/subsystem_b_smoke/case1/response.json" --summary "data/tmp/subsystem_b_smoke/case1/summary.json"
```

Expected: report_markdown ≥ 4000 chars, claim_count ≥ 8

- [ ] **Step 3: Update STATUS**

```bash
git add .agent/STATUS.md
git commit -m "chore: Subsystem B complete — Editor1 LLM report writing + content depth"

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```
