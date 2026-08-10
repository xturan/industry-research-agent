from __future__ import annotations

import json
# ruff: noqa: E501, I001

import importlib.machinery
import importlib.util
import re
import sys
import tempfile
from packages.research_harness.plan_semantic import build_semantic_plan as _caliber_semantic_plan
from packages.research_harness.tooling.executor import ToolExecutor as _FixedToolExecutor
from packages.research_harness.tooling.llm_agents import (
    build_editor1_draft_prompts as _fixed_build_editor1_draft_prompts,
)

from pathlib import Path
from types import ModuleType
from typing import Any

from packages.research_harness import research_taxonomy
from packages.research_harness.research_contract import compile_research_contract
from packages.research_harness.source_cluster import slot_source_counts
from packages.sources.local_source_patterns import canonical_source_family


def _candidate_impl_paths() -> list[Path]:
    # Prefer the version-controlled bytecode bundled inside the package so the
    # graph no longer depends on a file living in the system temp dir (which gets
    # cleared, taking the whole provider-backed graph down with it). Fall back to
    # temp-dir copies only if the in-repo bundle is missing.
    candidates: list[Path] = []
    bundled = Path(__file__).with_name("_real_nodes_impl.cpython-313.pyc")
    if bundled.exists():
        candidates.append(bundled)

    temp_dir = Path(tempfile.gettempdir())
    temp_candidates = sorted(
        temp_dir.glob("real_nodes*.pyc"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    explicit = temp_dir / "real_nodes.cpython-313.pyc"
    if explicit.exists() and explicit not in temp_candidates:
        temp_candidates.insert(0, explicit)
    for path in temp_candidates:
        if path not in candidates:
            candidates.append(path)
    return candidates


def _load_impl() -> ModuleType:
    candidates = _candidate_impl_paths()
    if not candidates:
        raise ImportError("Recovered real_nodes bytecode was not found in the system temp directory.")

    pyc_path = candidates[0]
    module_name = "_research_harness_real_nodes_impl"
    loader = importlib.machinery.SourcelessFileLoader(module_name, str(pyc_path))
    spec = importlib.util.spec_from_loader(module_name, loader)
    if spec is None:
        raise ImportError(f"Failed to build a module spec for {pyc_path}.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    loader.exec_module(module)
    return module


_impl = _load_impl()
_search_provider_override: Any | None = None
_caliber_monkeypatched: bool = False
_trace_ctx: dict[str, Any] | None = None
MAX_RESULTS_PER_SEARCH = 5


def _set_trace_ctx(state: dict[str, Any] | None, node_name: str) -> None:
    """Set the module-level LLM trace context for the current node.

    Persists run_id (parsed from thread_id "research_run:{id}") + node_name so
    downstream LLM call sites can attach real-input audit artifacts."""
    global _trace_ctx
    if not state:
        _trace_ctx = None
        return
    thread = str(state.get("thread_id") or "")
    run_id = thread.replace("research_run:", "") if "research_run:" in thread else None
    _trace_ctx = {"run_id": run_id, "node_name": node_name}


def _get_trace_ctx() -> dict[str, Any] | None:
    return _trace_ctx
_GENERIC_QUERY_SUFFIXES = (
    "通知",
    "公告",
    "政策",
    "项目",
    "实施方案",
    "工作方案",
    "年报",
    "披露",
    "官方来源",
    "官方证据",
    "官方政策证据",
)
_GENERIC_SEARCH_NOISE_PATTERNS = (
    "官方来源",
    "官方证据",
    "官方政策证据",
    "官方",
    "来源",
    "证据",
)
_SPAM_TITLE_MARKERS = (
    "app下载",
    "官网版下载",
    "直播app",
    "直播",
    "小红书下载",
    "攻略",
    "通关",
    "赛特降临",
    "阿娇",
    "高潮",
    "在线看片",
    "成人视频",
    "手游",
    "游戏",
)
_PRIMARY_TOPIC_ANCHORS = (
    "低空经济",
    "新能源汽车",
    "人形机器人",
    "人工智能",
    "商业航天",
    "光伏",
    "储能",
    "算力",
    "机器人",
    "盐湖",
    "绿电",
    "绿氢",
)

for _name in dir(_impl):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_impl, _name)


def _sync_impl_dependencies() -> None:
    global _impl
    _impl = _load_impl()
    if _search_provider_override is not None and hasattr(_impl, "set_search_provider_override"):
        _impl.set_search_provider_override(_search_provider_override)
    for _name in (
        "build_semantic_plan",
        "build_editor1_draft_prompts",
        "build_editor2_review_prompts",
        "build_verifier_prompts",
        "call_tooling_json",
    ):
        if _name in globals():
            setattr(_impl, _name, globals()[_name])

    # ── Caliber expansion: replace bytecode build_semantic_plan with ours ──
    _impl.build_semantic_plan = _caliber_semantic_plan  # noqa: B010

    # ── Monkeypatch compatibility: allow tests to override build_semantic_plan ──
    _patched = getattr(sys.modules.get(__name__, None), "build_semantic_plan", None)
    global _caliber_monkeypatched
    _caliber_monkeypatched = _patched is not None and callable(_patched)
    if _caliber_monkeypatched:
        _impl.build_semantic_plan = _patched  # noqa: B010

    # ── Editor1 fixes: inject fixed evidence bundle / outline / limitations ──
    _impl.build_editor1_draft_prompts = _fixed_build_editor1_draft_prompts  # noqa: B010
    _impl.ToolExecutor = _FixedToolExecutor  # noqa: B010
    from packages.capability_gateway import build_gateway_aware_search_provider
    from packages.sources.search_discovery import SearchDiscoveryRequest

    _impl.TavilySearchRequest = SearchDiscoveryRequest
    if _search_provider_override is None:
        _impl._search_provider = build_gateway_aware_search_provider
    else:
        _impl._search_provider = lambda: _search_provider_override


def editor2_review_provider_backed(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    _sync_impl_dependencies()
    result = _impl.editor2_review_provider_backed(state, tool_session=tool_session)
    support_matrix = list(state.get("claim_support_matrix", []))
    build_fallback_issues = getattr(_impl, "_build_editor2_fallback_issues", None)
    dedupe_issues = getattr(_impl, "_dedupe_issue_dicts", None)
    recommend_route = getattr(_impl, "_recommend_editor2_route", None)
    fallback_issues = (
        build_fallback_issues(state, support_matrix=support_matrix)
        if callable(build_fallback_issues)
        else []
    )
    latest_draft = {}
    drafts = list(state.get("drafts", []))
    if drafts and isinstance(drafts[-1], dict):
        latest_draft = drafts[-1]
    sections = [
        section for section in list(latest_draft.get("sections", [])) if isinstance(section, dict)
    ]
    role_resolver = getattr(_impl, "_section_role_for_claim_family", None)
    if not callable(role_resolver):
        role_resolver = lambda claim_family: {  # noqa: E731
            "policy_basis": "policy_basis",
            "local_rollout": "local_rollout",
            "procurement_award": "procurement_award",
            "statistics_corroboration": "statistics_corroboration",
            "company_disclosure": "company_disclosure",
            "risk": "risk",
        }.get(claim_family, "analysis")
    # ── Phase 4: Build evidence & source lookups once before the claim loop ──
    ev_map = {str(e.get("evidence_id")): e for e in state.get("evidence", [])}
    src_map = {str(s.get("source_id")): s for s in state.get("sources", [])}
    for claim in list(state.get("claims", [])):
        claim_id = str(claim.get("claim_id") or "")
        expected_role = role_resolver(str(claim.get("claim_family") or ""))
        matching_sections = [
            section
            for section in sections
            if any(
                claim_id in list(paragraph.get("claim_ids", []))
                for paragraph in list(section.get("paragraphs", []))
                if isinstance(paragraph, dict)
            )
        ]
        if matching_sections and any(
            str(section.get("section_role") or "") != expected_role
            for section in matching_sections
        ):
            fallback_issues.append(
                {
                    "issue_id": f"issue_section_role_{claim_id}",
                    "severity": "warning",
                    "issue_type": "section_role_mismatch",
                    "target_claim_id": claim_id,
                    "description": "The draft section role does not match the analytical role of the claim.",
                    "required_fix": "Move the claim into a section whose role matches the claim family.",
                    "suggested_search_queries": [],
                }
            )

        # ── Phase 4: P0 review issue detections ──
        ev_ids = [str(eid) for eid in claim.get("evidence_ids", [])]
        required_family = str(claim.get("required_source_family") or "")

        # Detection 1: unsupported_claim (blocker)
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
            continue

        # Detection 2: source_family_mismatch (blocker)
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

        # Detection 3: low_source_diversity (warning)
        unique_sources = set()
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

        # Detection 4: critical_limitation_unresolved (warning)
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

    merged_issues = [*list(result.get("review_issues", [])), *fallback_issues]
    review_issues = dedupe_issues(merged_issues) if callable(dedupe_issues) else merged_issues
    result["review_issues"] = review_issues
    result["issue_count"] = len(review_issues)
    if callable(recommend_route):
        result["editor2_route_recommendation"] = recommend_route(review_issues)
    return result


def plan_task_provider_backed(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    _sync_impl_dependencies()
    result = _impl.plan_task_provider_backed(state, tool_session=tool_session)
    # 补证 re-entry：gate 路由 ADD_EVIDENCE 回到这里时 loop_count 递增。
    # 用 result 里的 dimension_coverage 判断（chief_gate 每轮写入；首轮无）。
    _prev_loop = int(state.get("loop_count", 0) or 0)
    if "dimension_coverage" in result or "dimension_coverage" in state:
        result["loop_count"] = _prev_loop + 1
    else:
        result["loop_count"] = _prev_loop
    query = str(state.get("query") or result.get("query") or "").strip()
    plan = dict(result.get("plan") or {})
    query_requirements = _resolve_query_requirements(
        query=query,
        existing=dict(result.get("query_requirements") or {}),
    )
    result["query_requirements"] = query_requirements
    plan = _ensure_query_coverage_contract(
        query=query,
        plan=plan,
        query_requirements=query_requirements,
        max_rounds=int(state.get("max_rounds", 12) or 12),
    )
    # ── Caliber expansion: only when planner used real LLM and not monkeypatched ──
    planner_metadata = dict(result.get("planner_metadata") or {})
    planner_mode = str(planner_metadata.get("planner_mode", ""))
    if (planner_mode not in ("deterministic_fallback", "offline_rules_v1", "")
            and not _caliber_monkeypatched):
        try:
            from packages.research_harness.caliber_expander import expand_caliber
            caliber = expand_caliber(query=query)
            fp = caliber.final_search_plan if caliber else {}
            fg_count = len(fp.get("search_groups", []))
            if caliber and fp and (not caliber.fallback_used or fg_count > 0):
                caliber_rounds: list[dict[str, Any]] = []
                anchors = fp.get("anchor_phrases", [])
                if anchors:
                    caliber_rounds.append({
                        "round_number": 1,
                        "objective": "原始查询锚点搜索",
                        "search_phrases": [
                            str(a.get("phrase", "")) for a in anchors[:3]
                        ],
                        "include_domains": [],
                        "target_dimensions": [],
                        "expected_source_tier": "B",
                    })
                for g in fp.get("search_groups", []):
                    phrases = [str(p.get("phrase", "")) for p in g.get("search_phrases", [])]
                    if not phrases:
                        continue
                    # Map source_type_preference to include_domains
                    src_prefs = list(g.get("source_type_preference", []))
                    domains = _map_source_prefs_to_domains(src_prefs)
                    caliber_rounds.append({
                        "round_number": len(caliber_rounds) + 1,
                        "objective": str(g.get("dominant_intent", "")),
                        "search_phrases": phrases[:5],
                        "include_domains": domains,
                        "target_dimensions": [str(g.get("target_evidence_need", ""))],
                        "expected_source_tier": "B",
                    })
                if caliber_rounds:
                    # Enrich caliber rounds with dimension IDs and domains
                    dim_plan = list(plan.get("dimension_plan", []))
                    _map_caliber_targets_to_dimension_ids(caliber_rounds, dim_plan)
                    enriched_rounds, review = _rewrite_search_rounds_for_diversity(
                        query=query,
                        search_rounds=caliber_rounds,
                        dimension_plan=dim_plan,
                        query_requirements=query_requirements,
                    )
                    plan["search_rounds"] = enriched_rounds
                    result["plan"] = plan
                    planner_metadata["search_round_rewrite_mode"] = "caliber_expansion_v1"
                    planner_metadata["search_round_review"] = review
                    planner_metadata["caliber_search_groups"] = len(caliber_rounds) - (1 if anchors else 0)
                    result["planner_metadata"] = planner_metadata
        except Exception:
            pass  # non-fatal: caliber failure keeps original search rounds
    else:
        # ── Fallback: run diversity rewrite when caliber is not active ──
        original_rounds = [dict(item) for item in list(plan.get("search_rounds", []))]
        rewritten_rounds, review = _rewrite_search_rounds_for_diversity(
            query=query,
            search_rounds=original_rounds,
            dimension_plan=list(plan.get("dimension_plan", [])),
            query_requirements=query_requirements,
        )
        plan["search_rounds"] = rewritten_rounds
        result["plan"] = plan
        planner_metadata["search_round_rewrite_mode"] = (
            "semantic_planner_plus_deterministic_diversification_v1"
        )
        planner_metadata["search_round_review"] = review
        result["planner_metadata"] = planner_metadata

    loop_count = int(state.get("loop_count", 0) or 0)

    # ── Goal-Driven Evidence ReAct Phase 2.5: spec-driven first-pass retrieval ──
    # Phase 2 can backfill evidence after build_evidence sees gaps. Phase 2.5
    # moves a bounded part of that source-family awareness into the first
    # collect_sources wave so high-value families are not only discovered after a
    # downstream rescue loop. This is first-pass only; gap re-entry still uses the
    # dedicated Phase 8 path below.
    if loop_count == 0:
        plan = dict(result.get("plan") or plan)
        plan, spec_first_pass_meta, spec_min_rounds = _inject_spec_driven_first_pass_rounds(
            query=query,
            plan=plan,
            query_requirements=query_requirements,
            max_rounds=int(state.get("max_rounds", 12) or 12),
        )
        if spec_first_pass_meta.get("added_rounds", 0) > 0:
            result["plan"] = plan
            pm = dict(result.get("planner_metadata") or {})
            pm["spec_driven_first_pass"] = spec_first_pass_meta
            result["planner_metadata"] = pm
            result["spec_first_pass_min_search_rounds"] = spec_min_rounds

    # ── Phase 8: Gap-driven second-round retrieval ──
    # On re-entry (gate routed ADD_EVIDENCE back here), inject gap-targeted
    # search rounds derived from uncovered obligations so the funnel actually
    # widens instead of re-running identical phrases (which dedup to nothing).
    required_actions = list(state.get("required_actions", []))
    if loop_count > 0 and required_actions:
        gap_rounds = _build_gap_targeted_rounds(
            query=query,
            required_actions=required_actions,
            obligation_coverage=list(state.get("required_obligation_coverage", [])),
            query_requirements=query_requirements,
        )
        if gap_rounds:
            plan = dict(result.get("plan") or {})
            original_rounds = list(plan.get("search_rounds", []))
            # collect_sources slices search_rounds[:max_rounds], and the
            # original rounds already ran in the first pass (re-running them
            # dedups to nothing by URL). So on re-entry, put gap rounds FIRST
            # so they fall inside the slice and actually execute; keep the
            # originals after as harmless fallback.
            for offset, rnd in enumerate(gap_rounds):
                rnd["round_number"] = offset + 1
            for offset, rnd in enumerate(original_rounds):
                if isinstance(rnd, dict):
                    rnd["round_number"] = len(gap_rounds) + offset + 1
            plan["search_rounds"] = [*gap_rounds, *original_rounds]
            result["plan"] = plan
            pm = dict(result.get("planner_metadata") or {})
            pm["gap_targeted_rounds_added"] = len(gap_rounds)
            pm["gap_retrieval_loop"] = loop_count
            result["planner_metadata"] = pm
            # ADR 0001 #5: gap retrieval can emit more rounds than the first-pass
            # max_rounds budget (dual-query => 2 rounds per family). Surface the
            # required round count so collect_sources can widen its slice and not
            # truncate the gap rounds it was given.
            result["gap_min_search_rounds"] = len(gap_rounds)

    # ── 收口：确保 10 个基础维度都有搜索轮 + 维度定向短语 ──
    # 上面 caliber/rewrite/spec/gap 多条路径各自改写 search_rounds，导致被执行的轮次
    # （collect_sources 取 search_rounds[:max_rounds]）常常仍是整句 query 变体，且
    # LLM 的 search_groups 可能漏掉某些基础维度（如 market_scale/industry_chain/风险）。
    # 这里在 plan 定稿前：① ensure_base_dimension_rounds 补齐 10 个规范基础维度的轮
    # （插在锚点轮后，小预算内先执行）；② _enrich_round_phrases 把 query 变体短语
    # 替换成维度定向短语（招标 中标 / 上市公司 公告 / 统计 公报）。
    try:
        from packages.research_harness.plan_semantic import (
            _enrich_round_phrases,
            ensure_base_dimension_rounds,
        )

        final_plan = dict(result.get("plan") or plan)
        final_rounds = [dict(r) for r in (final_plan.get("search_rounds") or [])]
        if final_rounds:
            final_rounds = ensure_base_dimension_rounds(
                final_rounds,
                list(final_plan.get("dimension_plan") or []),
                query,
            )
            final_rounds = _enrich_round_phrases(
                final_rounds,
                list(final_plan.get("dimension_plan") or []),
                query,
            )
            final_plan["search_rounds"] = final_rounds
            result["plan"] = final_plan
            # 收口只补写 enrichment 键，不得用外层旧 planner_metadata 覆盖
            # 前面写入的 spec_driven_first_pass / gap_targeted_rounds_added。
            pm_final = dict(result.get("planner_metadata") or {})
            pm_final["search_round_final_enrichment"] = "base_dims_v1"
            result["planner_metadata"] = pm_final
    except Exception:  # noqa: BLE001 - 非致命：失败保留原 plan
        pass

    return result


_GAP_FAMILY_TEMPLATES: dict[str, dict[str, Any]] = {
    "policy_document": {
        "suffixes": ["政策 原文 官方", "实施方案 通知 政府", "专项政策 措施 发布"],
        "domains": ["gov.cn"],
        "tier": "A",
        "backbone": "local_government",
    },
    "company_disclosure": {
        "suffixes": ["上市公司 公告", "年报 披露", "投资者关系 业务"],
        "domains": ["cninfo.com.cn", "sse.com.cn", "szse.cn"],
        "tier": "B",
        "backbone": None,  # disclosure is nationwide (cninfo/exchanges), no local targeting
    },
    "exchange_disclosure": {
        "suffixes": ["交易所 公告", "年报 披露", "投资者关系 业务"],
        "domains": ["cninfo.com.cn", "sse.com.cn", "szse.cn"],
        "tier": "B",
        "backbone": None,
    },
    "tender_procurement": {
        "suffixes": ["项目 招标 公示", "中标 公告 建设", "政府采购 公共资源交易"],
        "domains": ["ccgp.gov.cn", "ggzy"],
        "tier": "B",
        "backbone": "project_public_resource",
    },
    "official_statistics": {
        "suffixes": ["统计 公报 数据", "产业 数据 指标", "行业 规模 产值"],
        "domains": ["stats.gov.cn"],
        "tier": "B",
        "backbone": "statistics_fiscal",
    },
    "local_official": {
        "suffixes": ["政府 新闻 发布", "部门 动态 解读", "项目 落地 本地"],
        "domains": ["gov.cn"],
        "tier": "B",
        "backbone": "local_government",
    },
    "location_matched_official_or_project_source": {
        "suffixes": ["项目 落地 本地", "政策 实施 地区"],
        "domains": ["gov.cn"],
        "tier": "B",
        "backbone": "local_government",
    },
    "industry_research": {
        "suffixes": ["行业 报告 白皮书", "产业 研究 分析", "市场规模 报告 研究"],
        "domains": [],
        "tier": "C",
        "backbone": None,
    },
    "broker_research": {
        "suffixes": ["券商 研报 行业", "证券 研究 报告", "行业 深度 报告"],
        "domains": [],
        "tier": "C",
        "backbone": None,
    },
    "operator_data": {
        "suffixes": ["运营商 数据 平台", "运营 数据 统计", "企业 运营 数据"],
        "domains": [],
        "tier": "B",
        "backbone": None,
    },
    "certification_database": {
        "suffixes": ["适航 认证 审定", "型号 合格证 审定", "认证 资质 名录"],
        "domains": [],
        "tier": "B",
        "backbone": None,
    },
}

_SPEC_FIRST_PASS_FAMILY_TEMPLATES: dict[str, dict[str, Any]] = {
    "policy_document": {
        "suffixes": ["政策 原文 官方", "实施方案 通知 政府"],
        "tier": "A",
    },
    "local_official": {
        "suffixes": ["政府 新闻 发布", "部门 动态 解读"],
        "tier": "B",
    },
    "tender_procurement": {
        "suffixes": ["项目 招标 公示", "中标 公告 建设"],
        "tier": "B",
    },
    "company_disclosure": {
        "suffixes": ["上市公司 公告", "年报 披露"],
        "tier": "B",
    },
    "exchange_disclosure": {
        "suffixes": ["交易所 公告", "年报 披露"],
        "tier": "B",
    },
    "official_statistics": {
        "suffixes": ["统计 公报 数据", "产业 数据 指标"],
        "tier": "B",
    },
    "environmental_land": {
        "suffixes": ["环评 公示 项目", "土地 出让 公告"],
        "tier": "B",
    },
    "industry_research": {
        "suffixes": ["协会 报告 数据", "行业 白皮书"],
        "tier": "C",
    },
}
_SPEC_FIRST_PASS_FAMILY_PRIORITY = (
    "tender_procurement",
    "company_disclosure",
    "exchange_disclosure",
    "official_statistics",
    "policy_document",
    "local_official",
    "environmental_land",
    "industry_research",
)
_SPEC_FIRST_PASS_MAX_EXTRA_ROUNDS = 3
_SPEC_FIRST_PASS_MAX_PHRASES_PER_FAMILY = 2
_SPEC_FIRST_PASS_MAX_TOTAL_ROUNDS = 4


def _inject_spec_driven_first_pass_rounds(
    *,
    query: str,
    plan: dict[str, Any],
    query_requirements: dict[str, Any],
    max_rounds: int,
) -> tuple[dict[str, Any], dict[str, Any], int]:
    rounds = [
        dict(item)
        for item in list(plan.get("search_rounds", []))
        if isinstance(item, dict)
    ]
    # 2026-08-11：只走 family 确定性模板（_build_spec_driven_first_pass_rounds）。
    # LLM 按 claim slot 生成检索词的设计已废弃（用户指示回到固定维度基本搜索）。
    spec_rounds, meta = _build_spec_driven_first_pass_rounds(
        query=query,
        plan=plan,
        query_requirements=query_requirements,
    )
    if not spec_rounds:
        meta["added_rounds"] = 0
        return plan, meta, max_rounds

    spec_rounds = spec_rounds[:_SPEC_FIRST_PASS_MAX_EXTRA_ROUNDS]
    preserved_head = rounds[:1]
    preserved_tail = rounds[1:]
    merged = [*preserved_head, *spec_rounds, *preserved_tail]
    for index, round_plan in enumerate(merged, start=1):
        round_plan["round_number"] = index

    updated = dict(plan)
    updated["search_rounds"] = merged
    min_rounds = min(
        len(merged),
        max(max_rounds, len(preserved_head) + len(spec_rounds)),
        _SPEC_FIRST_PASS_MAX_TOTAL_ROUNDS,
    )
    meta.update(
        {
            "added_rounds": len(spec_rounds),
            "min_search_rounds": min_rounds,
            "estimated_extra_search_requests": sum(
                len(list(round_plan.get("search_phrases", [])))
                for round_plan in spec_rounds
            ),
            "max_extra_rounds": _SPEC_FIRST_PASS_MAX_EXTRA_ROUNDS,
            "max_phrases_per_family": _SPEC_FIRST_PASS_MAX_PHRASES_PER_FAMILY,
            "hard_domain_filtering": False,
        }
    )
    return updated, meta, min_rounds

def _build_spec_driven_first_pass_rounds(
    *,
    query: str,
    plan: dict[str, Any],
    query_requirements: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        from packages.research_harness.plan_semantic import (
            build_evidence_requirement_spec,
        )
        from packages.sources.local_source_patterns import canonical_source_family
    except Exception:
        return [], {"status": "unavailable"}

    spec = build_evidence_requirement_spec(plan)
    if not spec:
        return [], {"status": "no_spec"}

    location = str(query_requirements.get("target_location") or "").strip()
    base_query = _compact_topic(_gap_core_topic(query, location))
    family_entries: dict[str, list[dict[str, Any]]] = {}
    for entry in spec:
        if not isinstance(entry, dict):
            continue
        for raw_family in list(entry.get("required_source_families", [])):
            family = canonical_source_family(str(raw_family))
            if family not in _SPEC_FIRST_PASS_FAMILY_TEMPLATES:
                continue
            family_entries.setdefault(family, []).append(entry)

    if not family_entries:
        return [], {"status": "no_targetable_families", "spec_entry_count": len(spec)}

    priority = {
        family: index for index, family in enumerate(_SPEC_FIRST_PASS_FAMILY_PRIORITY)
    }
    ordered_families = sorted(
        family_entries,
        key=lambda family: (
            priority.get(family, len(priority)),
            -max(
                int(entry.get("min_evidence", 0) or 0)
                for entry in family_entries.get(family, [])
            ),
            family,
        ),
    )

    rounds: list[dict[str, Any]] = []
    for family in ordered_families[:_SPEC_FIRST_PASS_MAX_EXTRA_ROUNDS]:
        tmpl = _SPEC_FIRST_PASS_FAMILY_TEMPLATES[family]
        entries = family_entries[family]
        dimension_ids = _dedupe_terms_local(
            [
                str(entry.get("dimension_id") or "").strip()
                for entry in entries
                if str(entry.get("dimension_id") or "").strip()
            ]
        )
        sections = _dedupe_terms_local(
            [
                str(entry.get("section") or "").strip()
                for entry in entries
                if str(entry.get("section") or "").strip()
            ]
        )
        phrases: list[str] = []
        for suffix in list(tmpl.get("suffixes", []))[:_SPEC_FIRST_PASS_MAX_PHRASES_PER_FAMILY]:
            loc = f"{location} " if location else ""
            phrases.append(_normalize_space(f"{loc}{base_query} {suffix}")[:120])
        if not phrases:
            continue
        rounds.append(
            {
                "round_number": 0,
                "objective": f"spec-driven first-pass retrieval: {family}",
                "search_phrases": phrases,
                # ADR 0001: hard domain filters hurt local recall. Keep discovery
                # open and let concise location/topic phrases carry precision.
                "include_domains": [],
                "target_dimensions": dimension_ids or [family],
                "expected_source_tier": str(tmpl.get("tier") or "B"),
                "_round_origin": "spec_driven_first_pass",
                "_spec_driven_first_pass": True,
                "_target_source_family": family,
                "_evidence_sections": sections,
            }
        )

    return rounds, {
        "status": "ready" if rounds else "no_rounds",
        "spec_entry_count": len(spec),
        "target_families": [
            round_plan.get("_target_source_family") for round_plan in rounds
        ],
    }


def _build_claim_evidence_actions(
    *,
    claims: list[dict[str, Any]],
    query: str,
    query_requirements: dict[str, Any],
) -> list[dict[str, Any]]:
    location = str(query_requirements.get("target_location") or "").strip()
    topic = _gap_core_topic(query, location)
    actions: list[dict[str, Any]] = []
    for claim in claims:
        if claim.get("supported") is True:
            continue
        claim_id = str(claim.get("claim_id") or "").strip()
        family = str(claim.get("required_source_family") or "policy_document").strip()
        if not claim_id:
            continue
        tmpl = (
            _SPEC_FIRST_PASS_FAMILY_TEMPLATES.get(family)
            or _GAP_FAMILY_TEMPLATES.get(family)
            or _SPEC_FIRST_PASS_FAMILY_TEMPLATES["policy_document"]
        )
        phrases: list[str] = []
        for suffix in list(tmpl.get("suffixes", []))[:2]:
            loc = f"{location} " if location else ""
            phrases.append(_normalize_space(f"{loc}{topic} {suffix}")[:120])
        actions.append(
            {
                "action_type": "ADD_EVIDENCE",
                "target_claim_id": claim_id,
                "required_source_family": family,
                "suggested_search_queries": _dedupe_terms_local(phrases),
            }
        )
    return actions


def _local_domains_for_gap_family(family: str, location: str) -> list[str]:
    """ADR 0001: resolve concrete local government/transaction domains for a gap
    family + location via the existing local_source_patterns knowledge base.

    Returns [] when no location, no backbone mapping, or the KB has no domains —
    callers then fall back to the template's generic domains."""
    if not location:
        return []
    tmpl = _GAP_FAMILY_TEMPLATES.get(family) or {}
    backbone = tmpl.get("backbone")
    if not backbone:
        return []
    try:
        from packages.sources.local_source_patterns import (
            local_source_domains_for_backbones,
        )
        domains = local_source_domains_for_backbones([location], [backbone])
    except Exception:
        return []
    return [str(d).strip() for d in (domains or []) if str(d).strip()]


_GAP_TOPIC_STOPWORDS = (
    "情况", "现状", "及", "与", "和", "的", "等",
    "产业政策", "企业披露", "项目落地", "落地情况", "披露", "项目",
    "相关", "官方来源", "官方", "来源", "证据",
)
_GAP_TOPIC_YEAR_RE = re.compile(r"20\d{2}\s*年?")


def _gap_core_topic(query: str, location: str) -> str:
    """ADR 0001 #3: reduce a verbose query to its core topic for gap phrases.

    Strips the year, the location (carried separately as a prefix), and broad
    descriptor words so "2025年合肥市低空经济产业政策、企业披露与项目落地情况"
    becomes "低空经济". The template suffix (政策 原文 / 招标 中标 / ...) supplies
    the rest, mirroring the concise manual query that recalled real local sources.
    """
    text = _normalize_space(query)
    text = _GAP_TOPIC_YEAR_RE.sub(" ", text)
    if location:
        text = text.replace(location, " ")
        # strip a leading 市/省/县/区 administrative suffix left behind when the
        # location stem was removed (e.g. "合肥市" -> drop "合肥" -> leading "市")
        text = re.sub(r"^\s*[省市县区]", " ", text.strip())
    # split on punctuation/space, drop stopword-ish chunks, keep the longest
    # remaining meaningful run as the core topic
    for stop in _GAP_TOPIC_STOPWORDS:
        text = text.replace(stop, " ")
    text = re.sub(r"[、，,。；;]", " ", text)
    parts = [p.strip() for p in text.split() if len(p.strip()) >= 2]
    core = " ".join(dict.fromkeys(parts))  # dedupe, preserve order
    core = _normalize_space(core)
    # 截到疑问/判断词前（"是否已进入规模化落地阶段？"等），保留主语核心，避免
    # 长 query 稀释 gap 补搜短语（_compact_topic 定义在后，运行时解析）。
    return _compact_topic(core) or _normalize_space(query)


def _compact_topic(query: str, max_chars: int = 30) -> str:
    """压缩 query 为紧凑主题，作为维度搜索短语的前缀。

    截到第一个问号/句号，再截到"是否/能否/如何/目前/处于/还是"等疑问/判断词前，
    保留主语核心。例如
    "半导体设备和材料国产替代是否已经从政策支持转化为订单和收入？请重点检查招投标..."
    -> "半导体设备和材料国产替代"。
    """
    q = _normalize_space(str(query or "")).strip()
    for sep in ("？", "?", "。", "；", ";"):
        idx = q.find(sep)
        if 5 < idx:
            q = q[:idx]
            break
    for marker in ("是否已经", "是否", "能不能", "能否", "如何", "目前", "处于", "还是", "有没有"):
        idx = q.find(marker)
        if 3 < idx:
            q = q[:idx]
            break
    return q[:max_chars]


def _build_gap_targeted_rounds(
    *,
    query: str,
    required_actions: list[dict[str, Any]],
    obligation_coverage: list[dict[str, Any]],
    query_requirements: dict[str, Any],
) -> list[dict[str, Any]]:
    """Phase 8: turn uncovered-obligation gate actions into targeted search
    rounds so re-entry widens the funnel toward the missing source families."""
    # Map obligation_id -> source_family from the authoritative coverage table.
    obl_family: dict[str, str] = {}
    for obl in obligation_coverage:
        if isinstance(obl, dict):
            oid = str(obl.get("obligation_id") or "")
            fam = str(obl.get("source_family") or "")
            if oid:
                obl_family[oid] = fam
    location = str(query_requirements.get("target_location") or "").strip()
    # 修复：target_location 常被编译提取器误设为完整 query 前截（逗号分隔子句被当地点），
    # 拼进 gap 短语会变成 query 变体。超过 30 字符视为污染（非真实地名），丢弃 location
    # 前缀，只用 base_query + suffix（base_query 已含主题）。
    if location and len(location) > 30:
        location = ""
    # ADR 0001 #3 fix: gap phrases were built from the full verbose query
    # ("2025年合肥市低空经济产业政策、企业披露与项目落地情况"), which dilutes the
    # core topic. The user's manual Tavily test showed a concise "合肥低空经济政策"
    # recalls the real local sources. Reduce the query to its core topic term and
    # let location + the template suffix carry the rest.
    base_query = _gap_core_topic(query, location)
    seen_families: set[str] = set()
    rounds: list[dict[str, Any]] = []
    for action in required_actions:
        if not isinstance(action, dict):
            continue
        target = str(action.get("target") or "")
        family = obl_family.get(target, "")
        if not family:
            # 优先用 action 显式声明的 required_source_family（字节码 gate 的 action 用
            # target_claim_id + required_source_family，而非 target 字段）。
            family = str(action.get("required_source_family") or "")
        if not family:
            # target may already be a family name, a "<family>_evidence" obligation
            # id, or "location_matched". Strip a trailing "_evidence" and match.
            stripped = target
            for suffix in ("_evidence", "_documents", "_source"):
                if stripped.endswith(suffix):
                    stripped = stripped[: -len(suffix)]
                    break
            family = (
                stripped
                if stripped in _GAP_FAMILY_TEMPLATES
                else (
                    "location_matched_official_or_project_source"
                    if "location" in target
                    else "policy_document"
                )
            )
        if family in seen_families:
            continue
        seen_families.add(family)
        tmpl = _GAP_FAMILY_TEMPLATES.get(family, _GAP_FAMILY_TEMPLATES["policy_document"])
        phrases = []
        for suffix in tmpl["suffixes"][:3]:
            loc = f"{location} " if location else ""
            phrases.append(_normalize_space(f"{loc}{base_query} {suffix}")[:120])
        # ADR 0001 (revised 2026-06-21): the original design硬过滤 local-gov
        # domains (hefei.gov.cn ...) for the gap round. Live case1 disproved its
        # core assumption: Tavily returned 0 for the local-domain-filtered round,
        # while the real Hefei policy sources live on aggregator/media domains
        # (ichuanghui.org, ahchanye.com, news.cn) — NOT on hefei.gov.cn. A manual
        # `search_depth="advanced"` query with NO domain filter surfaced them.
        # Fix: gap rounds no longer hard-filter by domain. Recall now comes from
        # search_depth=advanced (set in collect_sources) + clean location phrases.
        # include_domains is left empty so Tavily can rank real local sources from
        # any host; the location term in the phrase keeps them on-topic.
        rounds.append({
            "round_number": 0,  # renumbered by caller
            "objective": f"gap 补检: {family} 未覆盖 obligation",
            "search_phrases": phrases,
            "include_domains": [],
            "target_dimensions": [family],
            "expected_source_tier": tmpl["tier"],
            "_gap_targeted": True,
            "_gap_source_family": family,
        })
    return rounds


def _map_caliber_targets_to_dimension_ids(
    rounds: list[dict[str, Any]],
    dimension_plan: list[dict[str, Any]],
) -> None:
    if not dimension_plan:
        return
    # Build evidence_name → dimension_id mapping from dimension_plan
    name_to_dim: dict[str, str] = {}
    for dim in dimension_plan:
        dim_type = str(dim.get("dimension_type", "")).lower()
        dim_id = str(dim.get("dimension_id", ""))
        if dim_type and dim_id:
            name_to_dim[dim_type] = dim_id
    for rnd in rounds:
        targets = list(rnd.get("target_dimensions", []))
        mapped = []
        for t in targets:
            t_lower = str(t).lower().replace(" ", "_")
            if t_lower in name_to_dim:
                mapped.append(name_to_dim[t_lower])
            else:
                mapped.append(t)
        rnd["target_dimensions"] = mapped or targets


def _map_source_prefs_to_domains(source_prefs: list[str]) -> list[str]:
    """Map source_type_preference entries to domain patterns."""
    domain_map = {
        "巨潮资讯": "cninfo.com.cn",
        "cninfo": "cninfo.com.cn",
        "上交所": "sse.com.cn",
        "深交所": "szse.cn",
        "交易所": "sse.com.cn",
        "政府采购": "ccgp.gov.cn",
        "公共资源交易": "ggzy",
        "政府网站": "gov.cn",
        "地方政府": "gov.cn",
    }
    domains = []
    for pref in source_prefs:
        pref_lower = str(pref).lower()
        for key, domain in domain_map.items():
            if key in pref_lower or key in pref:
                if domain not in domains:
                    domains.append(domain)
    return domains[:4]


def _resolve_query_requirements(
    *,
    query: str,
    existing: dict[str, Any],
) -> dict[str, Any]:
    derived: dict[str, Any] = {}
    builder = globals().get("_build_query_requirements")
    if callable(builder):
        try:
            built = builder(query)
            if isinstance(built, dict):
                derived = dict(built)
        except Exception:  # noqa: BLE001
            derived = {}
    merged = {
        **derived,
        **existing,
    }
    merged["needs_company_disclosure"] = bool(
        merged.get("needs_company_disclosure")
        or any(token in query for token in ("上市公司", "年报", "披露", "交易所", "公告"))
    )
    target_location = str(merged.get("target_location") or "").strip()
    if not target_location:
        locations = _extract_search_locations(query=query, query_requirements=merged)
        if locations:
            merged["target_location"] = ",".join(locations)
    merged["is_location_sensitive"] = bool(
        merged.get("is_location_sensitive") or merged.get("target_location")
    )
    return merged


def _ensure_query_coverage_contract(
    *,
    query: str,
    plan: dict[str, Any],
    query_requirements: dict[str, Any],
    max_rounds: int,
) -> dict[str, Any]:
    updated = dict(plan)
    dimension_plan = [
        dict(item)
        for item in list(updated.get("dimension_plan", []))
        if isinstance(item, dict)
    ]
    research_dimensions = [
        dict(item)
        for item in list(updated.get("research_dimensions", []))
        if isinstance(item, dict)
    ]
    search_rounds = [
        dict(item)
        for item in list(updated.get("search_rounds", []))
        if isinstance(item, dict)
    ]

    if query_requirements.get("is_location_sensitive"):
        dimension_plan = _ensure_dimension_entry(
            dimension_plan=dimension_plan,
            entry=_synthetic_local_dimension_entry(query=query, query_requirements=query_requirements),
        )
        research_dimensions = _ensure_research_dimension_entry(
            research_dimensions=research_dimensions,
            entry=_synthetic_local_research_dimension(query=query, query_requirements=query_requirements),
        )
    if query_requirements.get("needs_company_disclosure"):
        dimension_plan = _ensure_dimension_entry(
            dimension_plan=dimension_plan,
            entry=_synthetic_disclosure_dimension_entry(query=query),
        )
        research_dimensions = _ensure_research_dimension_entry(
            research_dimensions=research_dimensions,
            entry=_synthetic_disclosure_research_dimension(query=query),
        )

    search_rounds = _ensure_required_search_rounds(
        query=query,
        search_rounds=search_rounds,
        dimension_plan=dimension_plan,
        query_requirements=query_requirements,
        max_rounds=max_rounds,
    )

    updated["dimension_plan"] = dimension_plan
    updated["research_dimensions"] = research_dimensions
    updated["search_rounds"] = search_rounds
    return updated


def _ensure_dimension_entry(
    *,
    dimension_plan: list[dict[str, Any]],
    entry: dict[str, Any],
) -> list[dict[str, Any]]:
    dimension_id = str(entry.get("dimension_id") or "")
    if any(str(item.get("dimension_id") or "") == dimension_id for item in dimension_plan):
        return dimension_plan
    return [*dimension_plan, entry]


def _ensure_research_dimension_entry(
    *,
    research_dimensions: list[dict[str, Any]],
    entry: dict[str, Any],
) -> list[dict[str, Any]]:
    dimension_id = str(entry.get("dimension_id") or "")
    if any(str(item.get("dimension_id") or "") == dimension_id for item in research_dimensions):
        return research_dimensions
    return [*research_dimensions, entry]


def _synthetic_disclosure_dimension_entry(*, query: str) -> dict[str, Any]:
    return {
        "dimension_id": "d_company_fundamentals",
        "dimension_type": "company_fundamentals",
        "research_question": f"What exchange, annual-report, or filing evidence supports {query}?",
        "why_it_matters": "Disclosure evidence checks whether company-side statements support the topic.",
        "coverage_required": "Collect annual reports, exchange filings, or cninfo-grade disclosures.",
        "expected_section_heading": "企业经营与财务",
        "source_priority": "enterprise",
        "source_families": ["exchange_disclosure", "company_disclosure"],
        "caliber_terms": [
            f"{query} 上市公司 年报",
            f"{query} 交易所 公告",
            f"{query} cninfo 披露",
        ],
    }


def _synthetic_disclosure_research_dimension(*, query: str) -> dict[str, Any]:
    return {
        "dimension_id": "d_company_fundamentals",
        "label": "企业经营与财务",
        "description": "annual reports, filings, exchange notices, and cninfo disclosures",
        "caliber_terms": [
            f"{query} 上市公司 年报",
            f"{query} 交易所 公告",
            f"{query} cninfo 披露",
        ],
        "source_priority": "enterprise",
    }


def _synthetic_local_dimension_entry(
    *,
    query: str,
    query_requirements: dict[str, Any],
) -> dict[str, Any]:
    location = _first_location_value(query=query, query_requirements=query_requirements)
    location_prefix = f"{location} " if location else ""
    return {
        "dimension_id": "d_regional_benchmark",
        "dimension_type": "regional_benchmark",
        "research_question": f"What region-comparison evidence places {query} locally?",
        "why_it_matters": "Region comparison prevents the search plan from treating local presence as local advantage.",
        "coverage_required": "Collect locality-matched metrics, cluster, policy, and benchmark evidence.",
        "expected_section_heading": "区域比较与产业集群",
        "source_priority": "government",
        "source_families": ["official_statistics", "local_official"],
        "caliber_terms": [
            f"{location_prefix}{query} 区域 比较".strip(),
            f"{location_prefix}{query} 产业集群".strip(),
            f"{location_prefix}{query} 对标 城市".strip(),
        ],
    }


def _synthetic_local_research_dimension(
    *,
    query: str,
    query_requirements: dict[str, Any],
) -> dict[str, Any]:
    location = _first_location_value(query=query, query_requirements=query_requirements)
    location_prefix = f"{location} " if location else ""
    return {
        "dimension_id": "d_regional_benchmark",
        "label": "区域比较与产业集群",
        "description": "region comparison, cluster, and benchmark signals",
        "caliber_terms": [
            f"{location_prefix}{query} 区域 比较".strip(),
            f"{location_prefix}{query} 产业集群".strip(),
            f"{location_prefix}{query} 对标 城市".strip(),
        ],
        "source_priority": "government",
    }


def _ensure_required_search_rounds(
    *,
    query: str,
    search_rounds: list[dict[str, Any]],
    dimension_plan: list[dict[str, Any]],
    query_requirements: dict[str, Any],
    max_rounds: int,
) -> list[dict[str, Any]]:
    rounds = [dict(item) for item in search_rounds]
    if not rounds:
        rounds = [
            {
                "round_number": 1,
                "objective": "collect official policy sources",
                "search_phrases": [query],
                "include_domains": ["gov.cn"],
                "target_dimensions": ["d_policy"],
                "expected_source_tier": "A",
            }
        ]
    if query_requirements.get("is_location_sensitive"):
        local_index = 1 if len(rounds) > 1 else 0
        rounds[local_index] = _merge_round_dimension(
            round_plan=rounds[local_index],
            dimension_id="d_regional_benchmark",
            source_domains=["gov.cn"],
        )
    if query_requirements.get("needs_company_disclosure"):
        disclosure_index = 1 if len(rounds) > 1 else 0
        rounds[disclosure_index] = _merge_round_dimension(
            round_plan=rounds[disclosure_index],
            dimension_id="d_company_fundamentals",
            source_domains=["cninfo.com.cn", "sse.com.cn", "szse.cn"],
        )
    if len(rounds) > max_rounds:
        rounds = rounds[:max_rounds]
    for index, round_plan in enumerate(rounds, start=1):
        round_plan["round_number"] = index
    return rounds


def _merge_round_dimension(
    *,
    round_plan: dict[str, Any],
    dimension_id: str,
    source_domains: list[str],
) -> dict[str, Any]:
    merged = dict(round_plan)
    target_dimensions = _dedupe_terms_local(
        [
            *[
                str(item).strip()
                for item in list(merged.get("target_dimensions", []))
                if str(item).strip()
            ],
            dimension_id,
        ]
    )
    include_domains = _dedupe_terms_local(
        [
            *[
                str(item).strip()
                for item in list(merged.get("include_domains", []))
                if str(item).strip()
            ],
            *source_domains,
        ]
    )
    merged["target_dimensions"] = target_dimensions
    merged["include_domains"] = include_domains
    return merged


def _first_location_value(*, query: str, query_requirements: dict[str, Any]) -> str:
    locations = _extract_search_locations(query=query, query_requirements=query_requirements)
    return locations[0] if locations else ""


def _rewrite_search_rounds_for_diversity(
    *,
    query: str,
    search_rounds: list[dict[str, Any]],
    dimension_plan: list[dict[str, Any]],
    query_requirements: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dimension_by_id = {
        str(item.get("dimension_id") or ""): dict(item)
        for item in dimension_plan
        if isinstance(item, dict) and item.get("dimension_id")
    }
    rewritten_rounds: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    for round_plan in search_rounds:
        current = dict(round_plan)
        original_phrases = [
            str(item).strip()
            for item in list(current.get("search_phrases", []))
            if str(item).strip()
        ]
        target_dimensions = [
            str(item).strip()
            for item in list(current.get("target_dimensions", []))
            if str(item).strip()
        ]
        enriched = _build_diverse_search_phrases(
            query=query,
            original_phrases=original_phrases,
            target_dimensions=target_dimensions,
            dimension_by_id=dimension_by_id,
            query_requirements=query_requirements,
        )
        current["search_phrases"] = enriched
        rewritten_rounds.append(current)
        review.append(
            {
                "round_number": current.get("round_number"),
                "objective": current.get("objective"),
                "target_dimensions": target_dimensions,
                "original_search_phrases": original_phrases,
                "final_search_phrases": enriched,
            }
        )
    return rewritten_rounds, review


def _build_diverse_search_phrases(
    *,
    query: str,
    original_phrases: list[str],
    target_dimensions: list[str],
    dimension_by_id: dict[str, dict[str, Any]],
    query_requirements: dict[str, Any],
) -> list[str]:
    query_normalized = _normalize_space(query)
    locations = _extract_search_locations(query=query, query_requirements=query_requirements)
    # 过滤误识别的长"地点"（编译提取器常把 query 逗号分隔的证据清单当 location，
    # 如 "招投标,中标公告,客户验证..." -> 会污染 location_prefix 和 topic）。
    locations = [loc for loc in locations if len(str(loc).strip()) <= 8]
    location = locations[0] if locations else ""
    # topic 直接从原始 query 压缩（不经过 _derive_search_topic，避免 location 剥离残留 ", , ,"）
    topic = _compact_topic(query)
    preferred: list[str] = []

    for dimension_id in target_dimensions:
        dimension = dict(dimension_by_id.get(dimension_id) or {})
        dimension_type = str(dimension.get("dimension_type") or "").strip()
        preferred.extend(
            _dimension_search_phrase_templates(
                query=query_normalized,
                topic=topic,
                location=location,
                dimension_type=dimension_type,
                caliber_terms=[
                    str(item).strip()
                    for item in list(dimension.get("caliber_terms", []))
                    if str(item).strip()
                ],
                query_requirements=query_requirements,
            )
        )

    retained_originals = [
        phrase
        for phrase in original_phrases
        if not _looks_like_shallow_query_variant(phrase=phrase, query=query_normalized)
    ]
    fallback_originals = [
        phrase
        for phrase in original_phrases
        if phrase not in retained_originals
    ]

    merged = _dedupe_terms_local(
        [
            *preferred,
            *retained_originals,
            *fallback_originals,
        ]
    )
    return merged[:6] if merged else original_phrases[:6]


def _dimension_search_phrase_templates(
    *,
    query: str,
    topic: str,
    location: str,
    dimension_type: str,
    caliber_terms: list[str],
    query_requirements: dict[str, Any],
) -> list[str]:
    topic_or_query = topic or query
    location_prefix = f"{location} " if location else ""
    phrases: list[str] = []
    dtype = research_taxonomy.canonicalize_dimension_type(dimension_type)
    if dtype == "policy_regulation":
        phrases.extend(
            [
                f"{location_prefix}{topic_or_query} 政策 原文",
                f"{location_prefix}{topic_or_query} 工作方案",
                # Keep the location on the implementation-plan phrase too: dropping
                # it (the old `{topic_or_query} 实施方案`) turned this into a
                # nationwide query that pulled in out-of-region policy sources.
                f"{location_prefix}{topic_or_query} 实施方案",
            ]
        )
    elif dtype == "market_scale":
        subject = f"{location_prefix}{topic_or_query}".strip() or topic_or_query
        phrases.extend(
            [
                f"{subject} 统计 公报",
                f"{subject} 产业 规模",
                f"{subject} 市场 数据",
            ]
        )
    elif dtype == "project_execution":
        phrases.extend(
            [
                f"{location_prefix}{topic_or_query} 招标 中标",
                f"{location_prefix}{topic_or_query} 项目 公示",
                f"{location_prefix}{topic_or_query} 公共资源交易",
            ]
        )
    elif dtype == "industry_chain":
        # Per-stage chain coverage phrases (upstream / midstream / downstream).
        phrases.extend(
            [
                f"{location_prefix}{topic_or_query} 产业链",
                f"{location_prefix}{topic_or_query} 上游 原材料",
                f"{location_prefix}{topic_or_query} 中游 制造",
                f"{location_prefix}{topic_or_query} 下游 应用",
            ]
        )
    elif dtype == "supply_competition":
        phrases.extend(
            [
                f"{location_prefix}{topic_or_query} 龙头企业",
                f"{location_prefix}{topic_or_query} 企业 产能",
                f"{location_prefix}{topic_or_query} 市场份额",
            ]
        )
    elif dtype in ("company_fundamentals",) or query_requirements.get(
        "needs_company_disclosure"
    ):
        # When the query is location-sensitive, bias disclosure search toward the
        # local company so the round does not pull in unrelated nationwide
        # issuers (e.g. a Hefei query surfacing 绿地控股/中国通号 disclosures).
        disc_subject = f"{location_prefix}{topic_or_query}".strip() or topic_or_query
        phrases.extend(
            [
                f"{disc_subject} 上市公司 年报",
                f"{disc_subject} 交易所 公告",
                f"{topic_or_query} cninfo 披露",
            ]
        )
    elif dtype == "demand_scenarios":
        phrases.extend(
            [
                f"{location_prefix}{topic_or_query} 应用 场景",
                f"{location_prefix}{topic_or_query} 订单 需求",
                f"{location_prefix}{topic_or_query} 商业 运营",
            ]
        )
    elif dtype == "technology_product":
        phrases.extend(
            [
                f"{topic_or_query} 技术 路线",
                f"{topic_or_query} 产品 参数",
                f"{topic_or_query} 适航 认证",
            ]
        )
    elif dtype == "business_economics":
        phrases.extend(
            [
                f"{topic_or_query} 成本 收益",
                f"{topic_or_query} 商业模式",
                f"{topic_or_query} 补贴 依赖",
            ]
        )
    elif dtype == "risk_constraints":
        phrases.extend(
            [
                f"{topic_or_query} 风险 瓶颈",
                f"{topic_or_query} 安全 事故",
                f"{topic_or_query} 监管 约束",
            ]
        )
    elif dtype == "regional_benchmark":
        phrases.extend(
            [
                f"{topic_or_query} 区域 比较",
                f"{topic_or_query} 产业集群",
                f"{topic_or_query} 对标 城市",
            ]
        )
    elif dtype == "capital_activity":
        phrases.extend(
            [
                f"{topic_or_query} 融资",
                f"{topic_or_query} 产业基金",
                f"{topic_or_query} 并购",
            ]
        )
    elif dtype == "outlook_drivers":
        phrases.extend(
            [
                f"{topic_or_query} 前景 趋势",
                f"{topic_or_query} 未来 预测",
                f"{topic_or_query} 增长 驱动",
            ]
        )
    elif dtype == "industry_scope":
        phrases.extend(
            [
                f"{topic_or_query} 产业 定义",
                f"{topic_or_query} 统计 口径",
                f"{topic_or_query} 边界 范围",
            ]
        )
    phrases.extend(caliber_terms[:2])
    return [phrase for phrase in phrases if phrase.strip()]


def _extract_search_locations(
    *,
    query: str,
    query_requirements: dict[str, Any],
) -> list[str]:
    target_location = str(query_requirements.get("target_location") or "").strip()
    extractor = globals().get("_extract_target_locations")
    if callable(extractor):
        locations = extractor(target_location, query=query)
        if isinstance(locations, list):
            return [str(item).strip() for item in locations if str(item).strip()]
    return [target_location] if target_location else []


def _derive_search_topic(*, query: str, locations: list[str]) -> str:
    topic = str(query or "").strip()
    for pattern in _GENERIC_SEARCH_NOISE_PATTERNS:
        topic = topic.replace(pattern, " ")
    for location in locations:
        topic = topic.replace(location, " ")
    topic = re.sub(r"\s+", " ", topic).strip()
    return topic or str(query or "").strip()


def _looks_like_shallow_query_variant(*, phrase: str, query: str) -> bool:
    phrase_normalized = _normalize_space(phrase)
    query_normalized = _normalize_space(query)
    if not phrase_normalized or not query_normalized:
        return False
    if phrase_normalized == query_normalized:
        return True
    for suffix in _GENERIC_QUERY_SUFFIXES:
        if phrase_normalized == f"{query_normalized} {suffix}":
            return True
        if phrase_normalized == f"{query_normalized}{suffix}":
            return True
    return False


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _dedupe_terms_local(values: list[str]) -> list[str]:
    dedupe_terms = getattr(_impl, "_dedupe_terms", None)
    if callable(dedupe_terms):
        return [
            str(item).strip()
            for item in dedupe_terms(values)
            if str(item).strip()
        ]
    output: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in output:
            output.append(normalized)
    return output


def build_evidence_provider_backed(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    _sync_impl_dependencies()
    _set_trace_ctx(state, "build_evidence")
    # evidence 从精排 chunk 直接抽（不再拼回 source；chunk_id↔source_id 保留在 evidence）。

    result = _impl.build_evidence_provider_backed(state, tool_session=tool_session)
    # ── Phase E1: dimension-driven deep backfill ──
    # Run 10-20 field-targeted searches per dimension (from search_key_fields) and
    # append the returned pages as sources, so the atomic extractor sees rich
    # per-dimension material instead of only the top-12-chunk view. Tagged sources
    # (`_deep_backfilled`) do not alter source_count / Sufficiency Gate raw counts.
    dimension_plan = list((state.get("plan") or {}).get("dimension_plan", []))
    try:
        deep_meta = _evidence_deep_backfill(state=state, dimension_plan=dimension_plan)
        if deep_meta.get("added_sources", 0):
            result["evidence_deep_backfill_meta"] = deep_meta
    except Exception:
        pass
    sources = list(state.get("sources", []))

    # ── 精排 chunk 直接作 evidence（用户核心指示，2026-08-10） ──
    # 不再 LLM 抽取原子事实；evidence = 检索词检索回来的精排 chunk 本身。
    # 字节码 base evidence（每条 source 1 条 snippet 摘要）弃用，避免 editor1
    # 混入低质摘要——精排 chunk 全文才是 editor1/editor2 的直接材料。
    base_evidence = list(result.get("evidence", []))
    chunk_evidence = _build_chunk_evidence_from_state(
        query=str(state.get("query", "")),
        sources=sources,
        base_evidence=base_evidence,
        dimension_plan=dimension_plan,
        state=state,
    )
    if chunk_evidence:
        result["evidence"] = chunk_evidence
    else:
        # 极端兜底：无任何精排 chunk（如全部 source 过短）时保留 base evidence
        result["evidence"] = base_evidence
    # ── Phase 3: Enrich evidence with relevance scoring and metadata ──
    query = str(state.get("query", ""))
    sources = list(state.get("sources", []))
    evidence_items = list(result.get("evidence", []))
    if evidence_items:
        enriched = _enrich_evidence_semantics(
            evidence_items=evidence_items,
            sources=sources,
            query=query,
        )
        result["evidence"] = enriched
    # ── Goal-Driven Evidence ReAct (PLAN goal-driven-evidence-react-v1, Phase 2) ──
    # build_evidence now knows the final report's evidence needs: derive the
    # evidence_requirement_spec from the plan, self-check which sections are
    # under-covered, and record the gap diagnostics so downstream (and a future
    # bounded re-extraction loop) can act on it. Degrades gracefully when no plan.
    try:
        gap_report = _evidence_gap_selfcheck(
            plan=dict(state.get("plan") or {}),
            evidence_items=list(result.get("evidence", [])),
            sources=sources,
        )
        if gap_report:
            result["evidence_gap_report"] = gap_report
            # Goal-Driven Evidence ReAct (Phase 2 second half): if a section is
            # under-covered (insufficient_count gap), re-extract from source with
            # a family-targeted query, append new evidence, and re-check. Bounded.
            backfilled = _evidence_react_backfill(
                state=state,
                result=result,
                gap_report=gap_report,
                tool_session=tool_session,
            )
            if backfilled:
                result["evidence"] = backfilled.get("evidence", result.get("evidence"))
                result["evidence_gap_report"] = backfilled.get(
                    "evidence_gap_report", gap_report
                )
                result["evidence_react_meta"] = backfilled.get("meta", {})
    except Exception:
        pass

    # ── Phase A2 (shadow): source content clustering metadata ──
    # Shadow only: computes duplicate-content clusters over the collected
    # sources and attaches them to the result as metadata. It NEVER mutates the
    # source records, NEVER writes origin_source_id, and NEVER changes the
    # formal source_count / claim / gate / report behavior.
    try:
        shadow = _shadow_source_clustering_meta(state=state, sources=list(state.get("sources", [])))
        if shadow:
            result["shadow_source_clustering"] = shadow
    except Exception:
        pass

    # ── Phase B.2: evaluation recording (fail-open, never blocks the run) ──
    try:
        from packages.research_harness.evaluation_recorder import (
            ensure_store,
            mark_search_tasks_terminal,
            record_claim_slots,
            record_evidence_units,
            record_search_events,
            record_search_tasks,
            write_store,
        )
        from packages.research_harness.research_contract import compile_research_contract

        store = ensure_store(state, result)
        run_id = str(state.get("run_id") or "")
        plan = state.get("plan") or {}
        contract = compile_research_contract(plan)
        record_claim_slots(store, plan)
        # SearchTasks are planned in plan.search_rounds (not derived from results).
        record_search_tasks(store, plan, run_id)
        slot_by_family: dict[str, list[str]] = {}
        for sec in contract.get("sections", []):
            for s in sec.get("claim_slots", []):
                slot_by_family.setdefault(s.get("source_family"), []).append(s["slot_id"])
        record_search_events(store, state, run_id, slot_by_family=slot_by_family)
        mark_search_tasks_terminal(store, state, run_id)
        record_evidence_units(
            store,
            list(result.get("evidence", [])),
            list(state.get("sources", [])),
            contract,
            run_id,
        )
        write_store(state, result, store)
    except Exception as exc:
        result.setdefault("evaluation_persistence_status", "degraded")
        result["evaluation_persistence_diagnostic"] = f"record_error:{type(exc).__name__}"
    return result


def _shadow_source_clustering_meta(
    *,
    state: dict[str, Any],
    sources: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Compute Phase A2 shadow clustering metadata (never mutates inputs).

    Review 2026-08-03: at build_evidence time there is no Claim->slot mapping yet,
    so only SOURCE FAMILY level aggregation is emitted (never a fake
    "family:xxx" slot). aggregation_level is explicit. Real Claim-Slot counts are
    computed by a later hook once claims + contract exist (see
    _attach_shadow_slot_counts_from_claims).
    """
    from packages.research_harness.source_cluster import cluster_sources

    cluster_output = cluster_sources(sources)
    if not cluster_output.get("clusters"):
        return None

    # family-level counts (correct aggregation, not a fake slot)
    sources_by_family: dict[str, list[str]] = {}
    for src in sources:
        if not isinstance(src, dict) or not src.get("source_id"):
            continue
        fam = str(src.get("source_family") or "unknown")
        sources_by_family.setdefault(fam, []).append(str(src["source_id"]))
    family_rows = slot_source_counts(sources_by_family, cluster_output)

    return {
        "report": {
            "raw_source_count": cluster_output["raw_source_count"],
            "shadow_distinct_content_count": cluster_output["shadow_distinct_content_count"],
            "shadow_duplicate_adjusted_source_count": cluster_output["shadow_duplicate_adjusted_source_count"],
            "clustering_mode": cluster_output["clustering_mode"],
            "clustering_version": cluster_output["clustering_version"],
        },
        "family_counts": family_rows,
        "slot_counts": [],
        "aggregation_level": "source_family_fallback",
        "cluster_count": len(cluster_output["clusters"]),
        "candidate_count": len(cluster_output["candidates"]),
        "revision_candidate_count": len(cluster_output["revision_candidates"]),
        "duplicate_removed_count": cluster_output["raw_source_count"] - cluster_output["shadow_duplicate_adjusted_source_count"],
    }


def _attach_shadow_slot_counts_from_claims(
    *,
    state: dict[str, Any],
    shadow: dict[str, Any],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Attach REAL Claim-Slot counts once claims + contract exist (build_claims).

    Maps each claim to contract slots (via required_source_family / linked
    evidence family, same logic as _backfill_claim_slot_ids), then counts the
    distinct content clusters behind each slot's supporting sources. Sets
    aggregation_level="claim_slot". Never mutates sources/claims.
    """
    from packages.research_harness.source_cluster import cluster_sources

    claims = [c for c in (state.get("claims") or []) if isinstance(c, dict)]
    plan = state.get("plan")
    if not claims or not isinstance(plan, dict):
        return shadow
    contract = compile_research_contract(plan)
    evidence = [e for e in (state.get("evidence") or []) if isinstance(e, dict)]
    evidence_map = {str(e.get("evidence_id")): e for e in evidence}
    src_family_by_id: dict[str, str] = {}
    for src in sources:
        if isinstance(src, dict) and src.get("source_id"):
            src_family_by_id[str(src["source_id"])] = canonical_source_family(
                src.get("source_family")
            )

    # backfill slot_ids onto working copies (do not mutate the real claims)
    working = []
    for claim in claims:
        copy_claim = dict(claim)
        copy_claim["evidence_ids"] = list(claim.get("evidence_ids", []))
        working.append(copy_claim)
    _backfill_claim_slot_ids(
        claims=working,
        contract=contract,
        evidence_map=evidence_map,
        src_family_by_id=src_family_by_id,
    )

    cluster_output = cluster_sources(sources)
    # slot_id -> supporting evidence / source ids / claim ids (from claims bound to that slot)
    slot_to_evidence_ids: dict[str, list[str]] = {}
    slot_to_source_ids: dict[str, list[str]] = {}
    slot_to_claim_ids: dict[str, list[str]] = {}
    for claim in working:
        for slot_id in claim.get("slot_ids", []) or ([claim.get("primary_slot_id")] if claim.get("primary_slot_id") else []):
            if not slot_id:
                continue
            slot_to_claim_ids.setdefault(str(slot_id), []).append(str(claim.get("claim_id")))
            for eid in claim.get("evidence_ids", []):
                ev = evidence_map.get(str(eid))
                if not ev:
                    continue
                slot_to_evidence_ids.setdefault(str(slot_id), []).append(str(eid))
                for sid in [ev.get("source_id")] + list(ev.get("source_ids", []) or []):
                    if sid:
                        slot_to_source_ids.setdefault(str(slot_id), []).append(str(sid))

    slot_rows = []
    for slot_id, source_ids in slot_to_source_ids.items():
        raw = len(set(source_ids))
        distinct_clusters = {
            cluster["content_cluster_id"]
            for cluster in cluster_output["clusters"]
            for sid in cluster["source_ids"]
            if sid in set(source_ids)
        }
        slot_rows.append({
            "slot_id": slot_id,
            "supporting_evidence_count": len(set(slot_to_evidence_ids.get(slot_id, []))),
            "raw_supporting_source_count": raw,
            "distinct_supporting_content_count": len(distinct_clusters),
            "supporting_claim_count": len(set(slot_to_claim_ids.get(slot_id, []))),
            "shadow_count_difference": len(distinct_clusters) - raw,
            "affected_claim_ids": list(dict.fromkeys(slot_to_claim_ids.get(slot_id, []))),
        })

    shadow["slot_counts"] = slot_rows
    shadow["aggregation_level"] = "claim_slot"
    return shadow


def build_claims_provider_backed(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    _sync_impl_dependencies()
    _set_trace_ctx(state, "build_claims")
    result = _impl.build_claims_provider_backed(state, tool_session=tool_session)
    claims = list(result.get("claims", []))
    evidence = list(state.get("evidence", []))
    if claims:
        # G4 精简：过滤挂到 claim 上的低质 evidence（usage_role=context_only/exclude 的
        # evidence 会让 claim 永远无法 supported——LLM 常把商业媒体证据挂到官方政策 claim 上）。
        # 过滤后 claim 只挂合格证据；无合格证据的 claim 诚实 unsupported（触发补证）。
        _usage_role_by_ev: dict[str, str] = {}
        _src_by_id = {str(s.get("source_id")): s for s in state.get("sources") or []}
        for _e in evidence:
            if not isinstance(_e, dict):
                continue
            _src = _src_by_id.get(str(_e.get("source_id") or ""), {})
            _role = str(
                (_src.get("source_quality_v2") or {}).get("usage_role")
                or _src.get("source_usage_role")
                or ""
            )
            _usage_role_by_ev[str(_e.get("evidence_id") or "")] = _role
        _LOW_QUALITY_ROLES = {"context_only", "exclude_from_primary_evidence"}
        for _claim in claims:
            if not isinstance(_claim, dict):
                continue
            _ids = [str(x) for x in (_claim.get("evidence_ids") or []) if str(x)]
            _kept = [
                eid for eid in _ids
                if _usage_role_by_ev.get(eid, "") not in _LOW_QUALITY_ROLES
            ]
            if _kept != _ids:
                _claim["evidence_ids"] = _kept
        enriched = _enrich_claim_semantics(claims=claims, evidence=evidence)
        result["claims"] = enriched
        claims = enriched

    # ── Phase A: slot-driven Claim Expander ──
    # Replaces the old `len(claims) < 8` count trigger: only supplement claims
    # for slots whose evidence is already satisfied but which no claim covers.
    evidence_map = {str(e.get("evidence_id")): e for e in evidence if isinstance(e, dict)}
    # evidence items carry source_id (not source_family); resolve family via the
    # source objects (same convention as _evidence_gap_selfcheck).
    src_family_by_id: dict[str, str] = {}
    for src in state.get("sources") or []:
        if isinstance(src, dict) and src.get("source_id"):
            src_family_by_id[str(src["source_id"])] = canonical_source_family(
                src.get("source_family")
            )
    plan = state.get("plan")
    contract = compile_research_contract(plan if isinstance(plan, dict) else {})
    # ResearchGap: slots the evidence layer cannot close (separate from claims).
    result["research_gaps"] = _build_research_gaps(
        contract=contract,
        evidence=evidence,
        src_family_by_id=src_family_by_id,
    )
    _backfill_claim_slot_ids(
        claims=claims,
        contract=contract,
        evidence_map=evidence_map,
        src_family_by_id=src_family_by_id,
    )
    gap_slots = _find_claim_gap_slots(
        contract=contract,
        claims=claims,
        evidence=evidence,
        evidence_map=evidence_map,
        src_family_by_id=src_family_by_id,
    )
    if gap_slots:
        existing_ids = {str(c.get("claim_id", "")) for c in claims}
        supplement = _llm_supplement_claims_slot_driven(
            query=str(state.get("query", "")),
            claims=claims,
            evidence=evidence,
            sources=list(state.get("sources", [])),
            existing_claim_ids=existing_ids,
            gap_slots=gap_slots,
            src_family_by_id=src_family_by_id,
        )
        if supplement:
            for claim in supplement:
                _annotate_claim_card(claim=claim, evidence_map=evidence_map)
            result["claims"] = [*claims, *supplement]

    # ── Phase A2 (shadow): attach REAL Claim-Slot counts now that claims exist ──
    # Only upgrades the shadow metadata (aggregation_level -> claim_slot); it
    # never mutates sources/claims and never changes the formal gate/report.
    try:
        shadow = result.get("shadow_source_clustering")
        if isinstance(shadow, dict):
            result["shadow_source_clustering"] = _attach_shadow_slot_counts_from_claims(
                state=state,
                shadow=shadow,
                sources=list(state.get("sources", [])),
            )
    except Exception:
        pass

    # ── Phase B.1 (shadow): dual-track CoverageReport integration ──
    # Computes/records raw vs duplicate-adjusted readiness. SHADOW ONLY: never
    # blocks Editor1, never triggers backfill, never changes claim strength,
    # never approves writing expressions, never changes the final report.
    try:
        from packages.research_harness.sufficiency_gate import build_shadow_coverage_report

        report_state = dict(state)
        report_state["evidence"] = evidence
        report_state["claims"] = list(result.get("claims", []))
        report_state["research_gaps"] = result.get("research_gaps", [])
        coverage = build_shadow_coverage_report(report_state)
        result["shadow_coverage_report"] = coverage
    except Exception:
        pass

    # ── Phase B.2: record ClaimCards only (fail-open, never blocks the run) ──
    # Lifecycle: build_claims may re-run each round after Evidence updates, so it
    # must NOT close planned/running SearchTasks globally — a still-pending
    # backfill task would be cancelled before it reaches the provider. Run-close
    # of all remaining tasks happens at finalize_report (finalize_run).
    try:
        from packages.research_harness.evaluation_recorder import (
            ensure_store,
            record_claim_cards,
            write_store,
        )

        store = ensure_store(state, result)
        record_claim_cards(store, list(result.get("claims", [])), str(state.get("run_id") or ""))
        write_store(state, result, store)
    except Exception as exc:
        result.setdefault("evaluation_persistence_status", "degraded")
        result["evaluation_persistence_diagnostic"] = f"record_error:{type(exc).__name__}"
    return result


def _evidence_families(
    ev: dict[str, Any],
    src_family_by_id: dict[str, str],
) -> set[str]:
    """Canonical source families for an evidence item, via source_id(s) with an
    inline source_family fallback (mirrors _evidence_gap_selfcheck)."""
    fams: set[str] = set()
    for sid in ([ev.get("source_id")] + list(ev.get("source_ids", []))):
        if sid and str(sid) in src_family_by_id:
            fams.add(src_family_by_id[str(sid)])
    if not fams and ev.get("source_family"):
        fams.add(canonical_source_family(ev.get("source_family")))
    return fams


_SLOT_PRIORITY_RANK: dict[str, int] = {"critical": 0, "required": 1, "optional": 2}


def _backfill_claim_slot_ids(
    *,
    claims: list[dict[str, Any]],
    contract: dict[str, Any],
    evidence_map: dict[str, dict[str, Any]],
    src_family_by_id: dict[str, str],
) -> None:
    """Attach slot_ids to claims that already cover contract slot(s).

    Existing claims have no slot_id (planner unchanged); this derives ALL
    matching slots deterministically from required_source_family / linked
    evidence family, so downstream Coverage and Claim-usage stats can aggregate
    by slot without loss (a claim may answer several slots).
    """
    slots = [s for sec in contract.get("sections", []) for s in sec.get("claim_slots", [])]
    if not slots:
        return
    slot_order = {s["slot_id"]: i for i, s in enumerate(slots)}
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        existing = [str(x) for x in claim.get("slot_ids", []) if x]
        if claim.get("primary_slot_id") and existing:
            continue
        matched = [
            slot for slot in slots
            if _claim_covers_slot(
                claim=claim,
                slot=slot,
                evidence_map=evidence_map,
                src_family_by_id=src_family_by_id,
            )
        ]
        if not matched:
            continue
        matched_sorted = sorted(
            matched,
            key=lambda s: (_SLOT_PRIORITY_RANK.get(s.get("required"), 9), slot_order.get(s["slot_id"], 9)),
        )
        slot_ids = list(dict.fromkeys([*existing, *(s["slot_id"] for s in matched_sorted)]))
        claim["slot_ids"] = slot_ids
        claim["primary_slot_id"] = slot_ids[0]
        claim.setdefault("slot_id", slot_ids[0])


def _claim_covers_slot(
    *,
    claim: dict[str, Any],
    slot: dict[str, Any],
    evidence_map: dict[str, dict[str, Any]],
    src_family_by_id: dict[str, str],
) -> bool:
    """Does this claim already cover the contract slot?"""
    slot_family = slot["source_family"]
    raw_required = claim.get("required_source_family")
    # Empty required_source_family must NOT match (canonical_source_family("")
    # falls back to the default "local_official", which would over-match every
    # unlabeled claim to the local_official slot).
    if raw_required and canonical_source_family(raw_required) == slot_family:
        return True
    for eid in claim.get("evidence_ids", []):
        ev = evidence_map.get(str(eid))
        if ev and slot_family in _evidence_families(ev, src_family_by_id):
            return True
    return False


def _slot_evidence_count(
    slot: dict[str, Any],
    evidence: list[dict[str, Any]],
    src_family_by_id: dict[str, str],
) -> int:
    slot_family = slot["source_family"]
    return sum(
        1
        for e in evidence
        if isinstance(e, dict) and slot_family in _evidence_families(e, src_family_by_id)
    )


def _slot_evidence_has_conflict(
    slot: dict[str, Any],
    evidence: list[dict[str, Any]],
    src_family_by_id: dict[str, str],
) -> bool:
    """True when this slot's evidence is internally contradictory."""
    slot_family = slot["source_family"]
    slot_evidence = [
        e for e in evidence
        if isinstance(e, dict) and slot_family in _evidence_families(e, src_family_by_id)
    ]
    conflict_lims = [
        str(lim)
        for e in slot_evidence
        for lim in e.get("limitations", [])
        if isinstance(lim, str)
    ]
    return any(m in "".join(conflict_lims) for m in _CONFLICT_MARKERS)


def _slot_evidence_satisfies_fields(
    slot: dict[str, Any],
    evidence: list[dict[str, Any]],
    src_family_by_id: dict[str, str],
) -> bool:
    """Key-fields gate driven by the slot's field_requirements (review 2026-08-03).

    - strict mode: every mandatory_fields present AND count(any_of present) >=
      minimum_optional_fields.
    - legacy_any_key_field mode: at least one declared key field present.

    A slot with no declared key fields passes trivially. Which specific fields
    are still missing is reported by the ResearchGap layer.
    """
    slot_family = slot["source_family"]
    slot_evidence = [
        e for e in evidence
        if isinstance(e, dict) and slot_family in _evidence_families(e, src_family_by_id)
    ]
    if not slot_evidence:
        return False

    field_requirements = slot.get("field_requirements")
    mode = str(slot.get("field_validation_mode") or "legacy_any_key_field")
    if isinstance(field_requirements, dict) and mode == "strict":
        mandatory = [str(f) for f in field_requirements.get("mandatory_fields", []) if f]
        any_of = [str(f) for f in field_requirements.get("any_of_fields", []) if f]
        try:
            min_opt = int(field_requirements.get("minimum_optional_fields", 0))
        except (TypeError, ValueError):
            min_opt = 0
        if mandatory and not all(any(e.get(k) for e in slot_evidence) for k in mandatory):
            return False
        present_any = sum(1 for k in any_of if any(e.get(k) for e in slot_evidence))
        return present_any >= max(0, min_opt)

    # legacy fallback
    key_fields = [k for k in slot.get("key_fields", []) if k]
    if not key_fields:
        return True
    return any(any(e.get(k) for e in slot_evidence) for k in key_fields)


def _find_claim_gap_slots(
    *,
    contract: dict[str, Any],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    evidence_map: dict[str, dict[str, Any]],
    src_family_by_id: dict[str, str],
) -> list[dict[str, Any]]:
    """Slots whose evidence is satisfied but which no claim covers.

    A claim-gap slot is one with:
    - evidence_count >= min_evidence (the evidence layer gathered enough),
    - no conflicting evidence (contradiction -> ResearchGap, not a claim gap),
    - all required key_fields present (missing fields -> ResearchGap),
    - no claim linked to it yet.

    These are the only slots the Claim Expander supplements — it never chases a
    count.
    """
    gap_slots: list[dict[str, Any]] = []
    for sec in contract.get("sections", []):
        for slot in sec.get("claim_slots", []):
            covered = any(
                _claim_covers_slot(
                    claim=c,
                    slot=slot,
                    evidence_map=evidence_map,
                    src_family_by_id=src_family_by_id,
                )
                for c in claims
                if isinstance(c, dict)
            )
            if covered:
                continue
            count = _slot_evidence_count(slot, evidence, src_family_by_id)
            min_evidence = int(slot.get("min_evidence") or 1)
            if count < max(1, min_evidence):
                continue
            if _slot_evidence_has_conflict(slot, evidence, src_family_by_id):
                continue
            if not _slot_evidence_satisfies_fields(slot, evidence, src_family_by_id):
                continue
            gap_slots.append(slot)
    return gap_slots


# ── ResearchGap (research-contract-refactor Phase A, review 2026-08-03) ──
# A ResearchGap is SEPARATE from a ClaimCard: a claim is something the report
# MAY assert; a gap is the reason a slot cannot be closed yet. "未找到某项信息"
# is not a self-evident claim fact — it becomes writable only after search
# coverage is sufficient. Until a CoverageReport exists (Phase B/A2), gaps carry
# the honest "未覆盖/不足/矛盾" expressions below.

_GAP_FAMILY_LABELS: dict[str, str] = {
    "policy_document": "政策文件",
    "local_official": "地方官方动态",
    "official_statistics": "官方统计",
    "tender_procurement": "招投标交易",
    "exchange_disclosure": "交易所披露",
    "company_disclosure": "公司披露",
    "company_material": "公司资料",
    "certification_database": "认证数据库",
    "standard_document": "标准文件",
    "patent_database": "专利数据库",
    "association_thinktank": "行业协会与智库",
    "broker_research": "券商研报",
    "industry_research": "行业研究",
    "commercial_media": "商业媒体",
    "operator_data": "运营数据",
    "environmental_land": "环境土地",
}


def _gap_candidate_expression(
    gap_type: str,
    slot: dict[str, Any],
    missing_fields: list[str],
) -> str:
    """Candidate report expression — deliberately scoped to the COLLECTED
    evidence, never "公开渠道暂未发现" (that implies a full public-space search
    commitment only allowed after Sufficiency Gate coverage review)."""
    family_label = _GAP_FAMILY_LABELS.get(slot.get("source_family", ""), "相关来源")
    question = str(slot.get("research_question") or "").strip()
    if gap_type == "no_reliable_evidence":
        base = f"当前已收集证据中未包含可核验的{family_label}材料"
        return f"{base}，无法对{'「' + question + '」' if question else '该问题'}作出判断"
    if gap_type == "missing_fields":
        fields = "、".join(missing_fields) if missing_fields else "关键字段"
        return f"现有{family_label}证据缺少{fields}，不足以形成完整判断"
    if gap_type == "contradiction":
        return f"{family_label}信息对该问题存在不一致表述，需并列呈现不同口径并标注不确定性"
    if gap_type == "not_found":
        return "当前检索范围内未发现该项信息（需覆盖评审后确认）"
    return "当前证据不足以对该问题作出判断"


def _build_research_gaps(
    *,
    contract: dict[str, Any],
    evidence: list[dict[str, Any]],
    src_family_by_id: dict[str, str],
) -> list[dict[str, Any]]:
    """Derive ResearchGap objects for every slot the evidence layer cannot close.

    gap_type values (deterministic, per slot):
    - no_reliable_evidence: no usable evidence for the slot at all
    - contradiction: evidence for the slot is internally conflicting
    - missing_fields: evidence exists but lacks the slot's required key_fields
    - not_found: reserved (only reachable via explicit coverage signal)

    Returns a list of gap dicts (additive; never raises).
    """
    gaps: list[dict[str, Any]] = []
    for sec in contract.get("sections", []):
        for slot in sec.get("claim_slots", []):
            slot_family = slot["source_family"]
            slot_evidence = [
                e for e in evidence
                if isinstance(e, dict)
                and slot_family in _evidence_families(e, src_family_by_id)
            ]

            gap_type: str | None = None
            missing_fields: list[str] = []
            if not slot_evidence:
                gap_type = "no_reliable_evidence"
            else:
                conflict_lims = [
                    str(lim)
                    for e in slot_evidence
                    for lim in e.get("limitations", [])
                    if isinstance(lim, str)
                ]
                if any(m in "".join(conflict_lims) for m in _CONFLICT_MARKERS):
                    gap_type = "contradiction"
                for field in slot.get("key_fields", []):
                    if field and not any(e.get(field) for e in slot_evidence):
                        missing_fields.append(str(field))
                if gap_type is None and missing_fields:
                    gap_type = "missing_fields"

            if gap_type is None:
                continue
            gaps.append(
                {
                    "gap_id": f"gap_{len(gaps) + 1}",
                    "slot_id": slot["slot_id"],
                    "section_id": slot["section_id"],
                    "source_family": slot_family,
                    "gap_type": gap_type,
                    "searched_source_families": [slot_family],
                    "missing_fields": missing_fields,
                    # Reportability is gated by the Sufficiency Gate (Phase B):
                    # until search coverage is reviewed, only the candidate
                    # expression scoped to COLLECTED evidence is writable.
                    "reportability": "pending_coverage_review",
                    "candidate_report_expression": _gap_candidate_expression(
                        gap_type, slot, missing_fields
                    ),
                    "approved_report_expression": None,
                    "priority": slot.get("required", "required"),
                }
            )
    return gaps


def _llm_supplement_claims_slot_driven(
    *,
    query: str,
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    existing_claim_ids: set[str],
    gap_slots: list[dict[str, Any]],
    src_family_by_id: dict[str, str],
) -> list[dict[str, Any]] | None:
    """Generate claims for evidence-satisfied-but-unclaimed slots.

    Slot-driven AND batched (review 2026-08-03): slots are grouped by section
    and sent in batches of up to 4 per LLM call. Each returned claim MUST bind a
    slot_id from the batch. Slots the LLM cannot close are returned as
    unresolved_slots (they become ResearchGaps downstream), instead of silently
    forcing a claim. This keeps slot constraint while bounding LLM call count.
    """
    import json as _json
    from packages.research_harness.tooling.llm_agents import call_tooling_json

    if not gap_slots:
        return None
    existing_texts = "\n".join(
        f"- {c.get('claim_id')}: {c.get('text', '')}" for c in claims
    )

    # group by section, batch in chunks of 4 slots
    by_section: dict[str, list[dict[str, Any]]] = {}
    for slot in gap_slots:
        by_section.setdefault(str(slot.get("section_id") or "_"), []).append(slot)

    new_claims: list[dict[str, Any]] = []
    generated_id_counter = 0
    # 本批已生成 claim_id 集合（LLM 常跨 batch 返回相同 c_suppl_N，需去重防重复）。
    batch_claim_ids: set[str] = set()

    for section_slots in by_section.values():
        for batch in (section_slots[i:i + 4] for i in range(0, len(section_slots), 4)):
            batch_by_slot_id = {str(slot.get("slot_id")): slot for slot in batch}
            slot_blocks: list[str] = []
            for slot in batch:
                slot_family = slot.get("source_family")
                slot_evidence = [
                    e for e in evidence
                    if isinstance(e, dict)
                    and slot_family in _evidence_families(e, src_family_by_id)
                ]
                slot_evidence_texts = _json.dumps(
                    [{
                        "id": e.get("evidence_id"),
                        "summary": str(e.get("summary", ""))[:200],
                        "limitations": list(
                            e.get("limitations", []) if isinstance(e.get("limitations"), list) else []
                        ),
                    } for e in slot_evidence[:4]],
                    ensure_ascii=False, indent=2,
                )
                slot_blocks.append(
                    f"[slot_id: {slot.get('slot_id')}]\n"
                    f"研究问题: {str(slot.get('research_question') or query)}\n"
                    f"source_family: {slot_family}\n"
                    f"可用证据:\n{slot_evidence_texts}"
                )
            prompt = (
                f"Query: {query}\n\n"
                f"已有 Claims (不要重复):\n{existing_texts}\n\n"
                f"为以下 {len(batch)} 个 slot 各生成 0-1 条研究断言(claim)。\n"
                f"{chr(10).join(slot_blocks)}\n\n"
                f"要求:\n"
                f"- 每个 claim 必须带 slot_id，且只能取上述给出的 slot_id\n"
                f"- claim_id 用 c_suppl_N 格式 (N 为递增数字)\n"
                f"- text: 中文完整句子, 15-50 字, 只断言该 slot 证据能支撑的内容\n"
                f"- claim_family: 按证据类型 (policy_basis/execution_evidence/company_disclosure/statistics_or_data 等)\n"
                f"- evidence_ids: 从该 slot 的可用证据中挑选 1-3 条\n"
                f"- required_source_family: 该 slot 的 source_family\n"
                f"- supported: true\n"
                f"- 若某个 slot 的证据不足以形成断言，不要硬编，把它列进 unresolved_slots 并给出 reason\n"
                f"输出 JSON 对象: {{\"claims\": [{{...}}], \"unresolved_slots\": [{{\"slot_id\": \"...\", \"reason\": \"...\"}}]}}"
            )
            try:
                llm_result = call_tooling_json(
                    system_prompt="你是一个研究分析师。为缺失证据覆盖的研究 slot 批量补充断言。",
                    user_prompt=prompt,
                    enable_thinking=False,
                    trace_ctx=_get_trace_ctx(),
                )
            except Exception:
                continue
            payload = llm_result.payload if llm_result else None
            if not isinstance(payload, dict):
                continue
            for item in payload.get("claims", []):
                if not isinstance(item, dict):
                    continue
                slot_id = str(item.get("slot_id") or "")
                if slot_id not in batch_by_slot_id:
                    slot_id = str(batch_by_slot_id[list(batch_by_slot_id)[0]].get("slot_id")) if batch_by_slot_id else ""
                cid = str(item.get("claim_id", ""))
                if not cid:
                    generated_id_counter += 1
                    cid = f"c_suppl_{generated_id_counter}"
                # 去重必须同时检查已有 claims 和本批 new_claims（LLM 常跨 batch 返回相同
                # c_suppl_N id，之前只查 existing 导致 c_suppl_1 重复多次）。
                if cid in existing_claim_ids or cid in batch_claim_ids:
                    continue
                batch_claim_ids.add(cid)
                new_claims.append({
                    "claim_id": cid,
                    "text": str(item.get("text", "")),
                    "claim_family": str(item.get("claim_family", "analysis")),
                    "supported": True,
                    "evidence_ids": list(item.get("evidence_ids", [])),
                    "required_source_family": str(item.get("required_source_family") or batch_by_slot_id.get(slot_id, {}).get("source_family", "")),
                    "slot_id": slot_id,
                    "slot_ids": [slot_id] if slot_id else [],
                    "primary_slot_id": slot_id,
                    "_source": "llm_supplement_slot_driven",
                })
    return new_claims if new_claims else None


def _estimate_editor_prompt_tokens(value: Any) -> int:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return max(1, len(value) // 4)


def _build_editor1_actual_input_pack(state: dict[str, Any]) -> dict[str, Any]:
    """Build and budget only the material actually sent to Editor1."""
    from packages.research_harness.prompt_assets import get_prompt_asset

    strategy = str(state.get("strategy") or "provider_backed_v1")
    asset = get_prompt_asset(node_name="editor1_draft", strategy=strategy)
    limit = int(asset.context_budget_tokens or 1600)
    claims = [item for item in list(state.get("claims", [])) if isinstance(item, dict)]
    evidence = [item for item in list(state.get("evidence", [])) if isinstance(item, dict)]
    sources = [item for item in list(state.get("sources", [])) if isinstance(item, dict)]
    claim_rows = [
        {
            "id": item.get("claim_id"),
            "family": item.get("claim_family"),
            "text": str(item.get("text") or "")[:500],
            "supported": item.get("supported"),
            "evidence_count": len(item.get("evidence_ids", [])),
            # ── ClaimCard (research-contract-refactor Phase A, additive) ──
            "claim_type": item.get("claim_type", ""),
            "epistemic_status": item.get("epistemic_status", ""),
            "max_assertion_level": item.get("max_assertion_level"),
            "forbidden_assertion_levels": list(item.get("forbidden_assertion_levels", []))
            if isinstance(item.get("forbidden_assertion_levels"), list) else [],
            "forbidden_expansions": list(item.get("forbidden_expansions", []))
            if isinstance(item.get("forbidden_expansions"), list) else [],
        }
        for item in claims
    ]

    def _priority(item: dict[str, Any]) -> tuple[float, int, str]:
        try:
            strength = float(item.get("support_strength", 0.0))
        except (TypeError, ValueError):
            strength = 0.0
        direct = 1 if str(item.get("support_type")) == "direct_support" else 0
        return (-strength, -direct, str(item.get("evidence_id") or ""))

    raw_rows: list[dict[str, Any]] = []
    dropped_ids: list[str] = []
    drop_reasons: dict[str, str] = {}
    duplicate_token_estimate = 0
    seen: set[str] = set()
    for item in sorted(evidence, key=_priority):
        evidence_id = str(item.get("evidence_id") or "")
        summary = " ".join(str(item.get("summary") or "").split())
        dedupe_key = "|".join((str(item.get("source_id") or ""),
                               str(item.get("source_family") or ""),
                               summary.casefold()))
        if dedupe_key in seen:
            dropped_ids.append(evidence_id)
            drop_reasons[evidence_id] = "duplicate_evidence"
            duplicate_token_estimate += _estimate_editor_prompt_tokens(summary)
            continue
        seen.add(dedupe_key)
        raw_rows.append({
            "id": evidence_id, "source_id": item.get("source_id"),
            "source_family": str(item.get("source_family") or ""),
            "support_type": str(item.get("support_type") or ""),
            "support_strength": item.get("support_strength"),
            "region": str(item.get("region") or ""),
            "time_ref": str(item.get("time_ref") or ""),
            "policy_tool": list(item.get("policy_tool", []))
            if isinstance(item.get("policy_tool"), list) else [],
            "summary": summary,
            "limitations": list(item.get("limitations", []))
            if isinstance(item.get("limitations"), list) else [],
        })
    source_rows = [
        {"id": item.get("source_id"), "title": str(item.get("title") or "")[:240],
         "source_family": str(item.get("source_family") or ""),
         "url": str(item.get("url") or "")[:500]}
        for item in sources[:20]
    ]
    pretrim_payload = {"query": str(state.get("query") or ""),
                       "claims": claim_rows, "evidence": raw_rows,
                       "sources": source_rows}
    pretrim_tokens = (
        _estimate_editor_prompt_tokens(pretrim_payload) + duplicate_token_estimate
    )
    selected_rows: list[dict[str, Any]] = []
    for row in raw_rows:
        compact = dict(row)
        compact["summary"] = str(compact.get("summary") or "")[:300]
        candidate_payload = {"query": pretrim_payload["query"],
                             "claims": claim_rows,
                             "evidence": [*selected_rows, compact],
                             "sources": source_rows}
        if _estimate_editor_prompt_tokens(candidate_payload) <= limit:
            selected_rows.append(compact)
        else:
            evidence_id = str(row.get("id") or "")
            dropped_ids.append(evidence_id)
            drop_reasons[evidence_id] = "hard_budget_overflow"
    final_payload = {"query": pretrim_payload["query"], "claims": claim_rows,
                     "evidence": selected_rows, "sources": source_rows}
    final_tokens = _estimate_editor_prompt_tokens(final_payload)
    if final_tokens > limit:
        final_payload["sources"] = []
        final_tokens = _estimate_editor_prompt_tokens(final_payload)
    return {"payload": final_payload, "metadata": {
        "pack_version": "editor1_actual_input_v1",
        "budget_scope": "actual_prompt_only",
        "prompt_budget_limit": limit,
        "prompt_pretrim_estimated_tokens": pretrim_tokens,
        "prompt_estimated_tokens": final_tokens,
        "prompt_budget_status": "over_budget" if final_tokens > limit else "within_budget",
        "prompt_pretrim_budget_status": (
            "over_budget" if pretrim_tokens > limit else "within_budget"
        ),
        "prompt_truncated": bool(dropped_ids or pretrim_tokens > final_tokens),
        "prompt_selected_ids": [str(item.get("id") or "") for item in selected_rows],
        "prompt_dropped_ids": dropped_ids, "drop_reasons": drop_reasons,
        "selected_source_families": sorted(
            {str(item.get("source_family") or "") for item in selected_rows
             if item.get("source_family")}
        ),
        "selected_regions": sorted(
            {str(item.get("region") or "") for item in selected_rows if item.get("region")}
        ),
        "included_claim_ids": [str(item.get("id") or "") for item in claim_rows],
    }}


def _assess_draft_narrative_quality(markdown: str) -> dict[str, Any]:
    lines = [line.strip() for line in str(markdown or "").splitlines() if line.strip()]
    headings = [line[3:].strip() for line in lines if line.startswith("## ")]
    section_count = len(headings)
    duplicate_heading_count = section_count - len(set(headings))
    generic_heading_count = sum(
        1 for heading in headings if heading.startswith("专题证据分析")
    )
    bullet_count = sum(1 for line in lines if line.startswith(("- ", "* ")))
    prose_lines = [
        line for line in lines if not line.startswith(("#", "- ", "* ", ">", "|", "---"))
    ]
    ledger_ratio = bullet_count / max(1, bullet_count + len(prose_lines))
    lowered = str(markdown or "").casefold()
    ledger_heading = any(
        marker in lowered for marker in ("## key claims", "## evidence and limitations", "## claims")
    )
    ledger_dominant = ledger_ratio >= 0.45 or (ledger_heading and section_count <= 3)
    placeholder_sections = any(
        marker in lowered
        for marker in ("## overall coordination", "## resource development", "## project execution")
    )
    semantic_heading_passed = (
        duplicate_heading_count == 0
        and generic_heading_count <= max(1, section_count // 3)
    )
    minimum_passed = (
        len(str(markdown or "")) >= 100
        and section_count >= 4
        and not ledger_dominant
        and not placeholder_sections
        and semantic_heading_passed
    )
    score = min(100, section_count * 10 + min(30, len(prose_lines) * 5))
    if ledger_dominant:
        score -= 40
    if placeholder_sections:
        score -= 20
    score -= duplicate_heading_count * 8
    score -= generic_heading_count * 6
    return {
        "rubric_version": "narrative_v2",
        "passes_minimum_narrative_standard": minimum_passed,
        "ledger_dominant": ledger_dominant,
        "has_placeholder_sections": placeholder_sections,
        "semantic_heading_passed": semantic_heading_passed,
        "duplicate_heading_count": duplicate_heading_count,
        "generic_heading_count": generic_heading_count,
        "section_count": section_count,
        "analysis_paragraph_count": len(prose_lines),
        "evidence_ledger_paragraph_ratio": round(ledger_ratio, 3),
        "score": max(0, score),
    }


def _best_existing_draft(drafts: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates: list[tuple[int, int, dict[str, Any]]] = []
    for draft in drafts:
        if not isinstance(draft, dict):
            continue
        quality = _assess_draft_narrative_quality(str(draft.get("report_markdown") or ""))
        if quality["passes_minimum_narrative_standard"]:
            candidates.append((int(quality["score"]),
                               int(draft.get("draft_version") or 0), draft))
    return max(candidates, key=lambda item: (item[0], item[1]))[2] if candidates else None


def _resolve_editor1_call_tooling_json() -> Any:
    """Honor either module-level or provider-module test/runtime overrides."""
    from packages.research_harness.tooling import llm_agents

    module_call = globals().get("call_tooling_json")
    provider_call = llm_agents.call_tooling_json
    module_name = str(getattr(module_call, "__module__", ""))
    if callable(module_call) and not module_name.startswith(
        "packages.research_harness.tooling"
    ):
        return module_call
    return provider_call


def editor1_draft_provider_backed(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    _set_trace_ctx(state, "editor1_draft")
    # ── Phase B: Always use LLM to write report, skip bytecode editor1 ──
    import uuid as _uuid

    if tool_session is not None:
        claim_ids = [
            str(item.get("claim_id"))
            for item in list(state.get("claims", []))
            if isinstance(item, dict) and item.get("claim_id")
        ][:20]
        tool_session.call_tool("get_evidence_bundle", {"claim_ids": claim_ids})
        tool_session.call_tool("compose_section_outline", {"claim_ids": claim_ids})

    try:
        result = _generate_real_editor1_draft(state=state)
    except Exception as exc:
        canonical = state.get("canonical_draft")
        if not isinstance(canonical, dict):
            canonical = _best_existing_draft(list(state.get("drafts", [])))
        fallback_md, fallback_sections = _build_narrative_fallback_from_claims(
            query=str(state.get("query", "")),
            claims=list(state.get("claims", [])),
            evidence_items=list(state.get("evidence", [])),
            sources=list(state.get("sources", [])),
        )
        draft_id = f"draft_{_uuid.uuid4().hex[:8]}"
        fallback_draft = {
            "draft_id": draft_id,
            "draft_version": len(state.get("drafts", [])) + 1,
            "report_markdown": fallback_md,
            "sections": fallback_sections,
        }
        selected = canonical if isinstance(canonical, dict) else fallback_draft
        try:
            pack_meta = _build_editor1_actual_input_pack(state)["metadata"]
        except Exception as pack_exc:
            pack_meta = {
                "pack_version": "editor1_actual_input_v1",
                "prompt_budget_status": "unavailable",
                "pack_error_type": type(pack_exc).__name__,
            }
        result = {
            "report_markdown": str(selected.get("report_markdown") or ""),
            "sections": list(selected.get("sections", [])),
            "draft_id": selected.get("draft_id"),
            "draft_version": selected.get("draft_version"),
            "drafts": [*list(state.get("drafts", [])), fallback_draft],
            "canonical_draft": selected,
            "canonical_draft_id": selected.get("draft_id"),
            "retained_previous_draft": isinstance(canonical, dict),
            "contract_meta": {
                "editor1_draft": {
                    "status": "generation_exception_fallback",
                    "used_fallback": True,
                    "retained_previous_draft": isinstance(canonical, dict),
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc)[:500],
                    "actual_input_pack": pack_meta,
                }
            },
        }

    # Fallback: only if output is genuinely deficient (too short or no
    # section structure). A multi-section synthesized report beats the
    # template ledger even when shorter than the soft target.
    rm = str(result.get("report_markdown", ""))
    if not result.get("retained_previous_draft") and (
        len(rm) < 800 or rm.count("\n## ") < 3
    ):
        fallback_md, fallback_sections = _build_narrative_fallback_from_claims(
            query=str(state.get("query", "")),
            claims=list(state.get("claims", [])),
            evidence_items=list(state.get("evidence", [])),
            sources=list(state.get("sources", [])),
        )
        draft_id = result.get("draft_id") or f"draft_{_uuid.uuid4().hex[:8]}"
        draft_version = result.get("draft_version") or 1
        result["report_markdown"] = fallback_md
        result["sections"] = fallback_sections
        result["drafts"] = [*list(state.get("drafts", [])), {
            "draft_id": draft_id,
            "draft_version": draft_version,
            "report_markdown": fallback_md,
            "sections": fallback_sections,
        }]

    # Ensure drafts is populated even for LLM-success path (belt-and-suspenders)
    if not result.get("drafts"):
        result["drafts"] = list(state.get("drafts", []))

    # ── Phase 3 (remediation): Align section_role with claim_family ──
    result = _align_section_roles_in_draft(state=state, result=result)

    # ── Phase A (StructuredDraft): paragraph-level claim_ids/evidence_ids + unused_claim_ids ──
    mapping = _annotate_draft_paragraph_mapping(
        sections=list(result.get("sections", [])),
        claims=list(state.get("claims", [])),
        evidence=list(state.get("evidence", [])),
    )
    result["sections"] = mapping["sections"]
    result["unused_claim_ids"] = mapping["unused_claim_ids"]

    if tool_session is not None:
        result["tool_traces"] = tool_session.export_traces()

    return result


def _align_section_roles_in_draft(
    *,
    state: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Align section_role with the dominant claim_family in each section.

    This reduces section_role_mismatch review issues from editor2.
    """
    _FAMILY_TO_ROLE = {
        "policy_basis": "policy_evidence",
        "local_rollout": "local_implementation",
        "execution_evidence": "project_execution",
        "execution": "project_execution",
        "company_disclosure": "corporate_disclosure",
        "disclosure": "corporate_disclosure",
        "statistics_or_data": "industry_data",
        "risk_assessment": "risk_and_uncertainty",
    }
    claims = list(state.get("claims", []))
    claim_families = {
        str(c.get("claim_id", "")): str(c.get("claim_family", ""))
        for c in claims
    }
    sections = list(result.get("sections", []))
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        paras = list(sec.get("paragraphs", []))
        # Count claim families in this section
        family_counts: dict[str, int] = {}
        for p in paras:
            if not isinstance(p, dict):
                continue
            for cid in p.get("claim_ids", []):
                family = claim_families.get(str(cid), "")
                if family:
                    family_counts[family] = family_counts.get(family, 0) + 1
        if family_counts:
            dominant = max(family_counts, key=lambda k: family_counts[k])
            aligned_role = _FAMILY_TO_ROLE.get(dominant, "dimension_chapter")
            sec["section_role"] = aligned_role
    result["sections"] = sections
    return result


def _generate_real_editor1_draft(
    *,
    state: dict[str, Any],
    fallback_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a real LLM draft when bytecode editor1 falls back.

    Uses the fixed build_editor1_draft_prompts (with correct evidence bundle shape,
    enriched claims, and dimension-based outline) and calls the LLM directly.
    Falls back leniently: even imperfect JSON is usable if we can extract content.
    """
    # ── Phase B: LLM research report as primary writer ──
    import json as _json
    import uuid as _uuid

    # ── Phase 9: resolve inputs from state (previously undefined → NameError →
    # silent template fallback; the LLM writer never actually ran). ──
    query = str(state.get("query", "")).strip()
    claims = list(state.get("claims", []))
    evidence_items = list(state.get("evidence", []))
    sources = list(state.get("sources", []))
    prior_drafts = list(state.get("drafts", []))
    draft_version = len(prior_drafts) + 1

    actual_input_pack = _build_editor1_actual_input_pack(state)
    prompt_payload = dict(actual_input_pack["payload"])
    claims_json = _json.dumps(prompt_payload["claims"], ensure_ascii=False, indent=2)
    evidence_json = _json.dumps(prompt_payload["evidence"], ensure_ascii=False, indent=2)
    sources_json = _json.dumps(prompt_payload["sources"], ensure_ascii=False, indent=2)
    llm_exception: Exception | None = None

    # ── Call LLM ──
    llm_call_meta: dict[str, Any] = {}
    try:
        llm_result = _resolve_editor1_call_tooling_json()(
            system_prompt=(
                "你是资深行业研究员。基于提供的证据材料撰写专业中文深度研究报告。\n\n"
                "要求:\n"
                "1. 完整研报结构: 标题、执行摘要、方法口径、各维度分析、风险与不确定性、结论与展望、来源说明\n"
                "2. 每个断言都要有分析性叙述——不只罗列证据，要解释含义和重要性\n"
                "3. 必须做跨来源综合: 发现证据间的逻辑关联与传导链条"
                "(政策→地方落地→项目/基础设施→公司业务→产业链), 不要逐条复述证据\n"
                "4. 必须做地区/主体对比: 利用证据的 region 字段横向比较不同地区"
                "政策力度、落地阶段、政策工具(policy_tool)差异, 用表格呈现\n"
                "5. 标注证据局限性(单源支撑、估算非官方、覆盖有限、support_type=background 时不可当作强结论)\n"
                "6. 区分来源可信度与对断言的支撑强度: 官方来源≠结论可靠, "
                "support_type/support_strength 低或 needs_fulltext_check 为真时须降级表述\n"
                "7. 方法口径必须与正文一致: 未实际覆盖的维度(如公司公告/行业统计)不得宣称已覆盖, "
                "应明确列为数据缺口\n"
                "8. 中文撰写，专业但不晦涩; 4000-6000字(根据证据量自适应)\n\n"
                "章节: # 标题, ## 执行摘要, ## 方法与口径, ## 政策主线分析, "
                "## 地方政策与项目对比(表格), ## 传导链条与产业链映射, "
                "## 公司披露(无则标注缺口), ## 行业数据(无则标注缺口), "
                "## 风险与不确定性, ## 结论与展望, ## 后续跟踪清单, ## 来源说明\n\n"
                "用 [证据ID] 标注引用。\n"
                "9. 每个自然段（段落之间用空行分隔）在其正文前用 HTML 注释显式声明"
                "该段引用的断言与证据，格式如下（若该段未引用任何断言/证据则省略对应行）:\n"
                "<!-- paragraph_id: p_001 -->\n"
                "<!-- claim_ids: claim_001, claim_004 -->\n"
                "<!-- evidence_ids: ev_001, ev_007 -->\n"
                "只能引用「研究断言」里给出的 claim_id 和证据里给出的 evidence_id，"
                "不得编造不存在的 ID；若无法确定该段对应哪个 claim，可省略 claim_ids 行。\n"
                "输出 JSON 对象: {\"report_markdown\": \"<完整Markdown研报正文>\"}"
            ),
            user_prompt=(
                f"研究问题: {query}\n\n"
                f"研究断言:\n{claims_json}\n\n"
                f"证据材料:\n{evidence_json}\n\n"
                f"信息来源:\n{sources_json}\n\n"
                f"请输出完整 Markdown 中文研报。"
            ),
            enable_thinking=False,
            max_tokens=8000,
            trace_ctx=_get_trace_ctx(),
        )
        llm_data = llm_result.payload if llm_result else None
        llm_call_meta = dict(llm_result.metadata or {}) if llm_result else {}
    except Exception as exc:
        llm_exception = exc
        llm_data = None

    if isinstance(llm_data, dict):
        llm_markdown = str(llm_data.get("report_markdown") or llm_data.get("content") or "")
    elif isinstance(llm_data, str):
        llm_markdown = llm_data
    else:
        llm_markdown = ""

    # ── Fallback to template only if LLM output is genuinely deficient ──
    # A real synthesized report (multi-section structure) beats the template
    # ledger even when shorter than the soft target. Fall back only when the
    # output is too short to be a report OR lacks section structure.
    _section_count = llm_markdown.count("\n## ")
    if len(llm_markdown) < 800 or _section_count < 3:
        canonical = state.get("canonical_draft")
        if not isinstance(canonical, dict):
            canonical = _best_existing_draft(prior_drafts)
        if isinstance(canonical, dict):
            result = dict(fallback_result or {})
            result.update(
                {
                    "draft_id": canonical.get("draft_id"),
                    "draft_version": canonical.get("draft_version", draft_version - 1),
                    "report_markdown": str(canonical.get("report_markdown") or ""),
                    "sections": list(canonical.get("sections", [])),
                    "drafts": prior_drafts,
                    "canonical_draft": canonical,
                    "canonical_draft_id": canonical.get("draft_id"),
                    "retained_previous_draft": True,
                }
            )
            contract_meta = dict(result.get("contract_meta", {}))
            editor_meta: dict[str, Any] = {
                "status": "retained_previous_draft",
                "used_fallback": True,
                "retained_previous_draft": True,
                "attempt_count": 1,
                "attempts": [{"mode": "llm_research_report_v1", "status": "deficient"}],
                "input_mode": "provider_backed_v1",
                "actual_input_pack": actual_input_pack["metadata"],
            }
            editor_meta.update(llm_call_meta)
            if llm_exception is not None:
                editor_meta["exception_type"] = type(llm_exception).__name__
                editor_meta["exception_message"] = str(llm_exception)[:500]
            contract_meta["editor1_draft"] = editor_meta
            result["contract_meta"] = contract_meta
            return result
        structured_md, structured_sections = _build_narrative_fallback_from_claims(
            query=query, claims=claims, evidence_items=evidence_items, sources=sources,
        )
        result = dict(fallback_result or {})
        fb_draft_id = f"draft_{_uuid.uuid4().hex[:8]}"
        result["draft_id"] = fb_draft_id
        result["draft_version"] = draft_version
        result["report_markdown"] = structured_md
        result["sections"] = structured_sections
        # Ensure drafts is populated — runner reads partial["drafts"][-1].
        result["drafts"] = [*prior_drafts, {
            "draft_id": fb_draft_id,
            "draft_version": draft_version,
            "report_markdown": structured_md,
            "sections": structured_sections,
        }]
        result["canonical_draft"] = result["drafts"][-1]
        result["canonical_draft_id"] = fb_draft_id
        contract_meta = dict(result.get("contract_meta", {}))
        editor_meta = {
            "status": "structured_fallback",
            "used_fallback": True,
            "retained_previous_draft": False,
            "attempt_count": 1,
            "attempts": [{"mode": "llm_research_report_v1", "status": "deficient"}],
            "input_mode": "provider_backed_v1",
            "actual_input_pack": actual_input_pack["metadata"],
        }
        editor_meta.update(llm_call_meta)
        if llm_exception is not None:
            editor_meta["exception_type"] = type(llm_exception).__name__
            editor_meta["exception_message"] = str(llm_exception)[:500]
        contract_meta["editor1_draft"] = editor_meta
        result["contract_meta"] = contract_meta
        return result

    # ── Parse sections from LLM markdown ──
    sections = _parse_markdown_sections(llm_markdown)

    # ── Assemble result ──
    draft_id = f"draft_{_uuid.uuid4().hex[:8]}"
    result = dict(fallback_result or {})
    result["draft_id"] = draft_id
    result["draft_version"] = draft_version
    result["report_markdown"] = llm_markdown
    result["sections"] = sections

    new_draft = {
        "draft_id": draft_id, "draft_version": draft_version,
        "report_markdown": llm_markdown, "sections": sections,
        "narrative_quality": _assess_draft_narrative_quality(llm_markdown),
    }
    previous = state.get("canonical_draft")
    if not isinstance(previous, dict):
        previous = _best_existing_draft(prior_drafts)
    candidate_quality = dict(new_draft["narrative_quality"])
    previous_quality = (
        _assess_draft_narrative_quality(str(previous.get("report_markdown") or ""))
        if isinstance(previous, dict)
        else None
    )
    retain_previous = bool(
        isinstance(previous, dict)
        and (
            not candidate_quality["passes_minimum_narrative_standard"]
            or int(candidate_quality["score"]) < int(previous_quality["score"])
        )
    )
    if retain_previous:
        result["draft_id"] = previous.get("draft_id")
        result["draft_version"] = previous.get("draft_version")
        result["report_markdown"] = str(previous.get("report_markdown") or "")
        result["sections"] = list(previous.get("sections", []))
        result["drafts"] = [*prior_drafts, new_draft]
        result["canonical_draft"] = previous
        result["canonical_draft_id"] = previous.get("draft_id")
        result["retained_previous_draft"] = True
    else:
        result["drafts"] = [*prior_drafts, new_draft]
        result["canonical_draft"] = new_draft
        result["canonical_draft_id"] = draft_id
        result["retained_previous_draft"] = False

    contract_meta = dict(result.get("contract_meta", {}))
    contract_meta["editor1_draft"] = {
        "status": "retained_previous_draft" if retain_previous else "llm_synthesized",
        "used_fallback": False, "attempt_count": 1,
        "attempts": [{"mode": "llm_research_report_v1", "status": "succeeded"}],
        "input_mode": "provider_backed_v1",
        "note": "Phase B: LLM research report as primary writer",
        "actual_input_pack": actual_input_pack["metadata"],
        "retained_previous_draft": retain_previous,
        **llm_call_meta,
    }
    result["contract_meta"] = contract_meta

    return result


def _parse_markdown_sections(markdown: str) -> list[dict[str, Any]]:
    """Parse ## headers from LLM markdown into section dicts."""
    sections: list[dict[str, Any]] = []
    current_title = "正文"
    current_body: list[str] = []
    for line in markdown.split("\n"):
        if line.startswith("## "):
            if current_body:
                sections.append({
                    "section_id": f"sec_{len(sections) + 1}",
                    "title": current_title,
                    "section_role": "analysis",
                    "argument_posture": "evidence_backed",
                    "markdown_body": "\n".join(current_body).strip(),
                    "paragraphs": [],
                })
            current_title = line[3:].strip()
            current_body = []
        else:
            current_body.append(line)
    if current_body:
        sections.append({
            "section_id": f"sec_{len(sections) + 1}",
            "title": current_title,
            "section_role": "analysis",
            "argument_posture": "evidence_backed",
            "markdown_body": "\n".join(current_body).strip(),
            "paragraphs": [],
        })
    return sections


# ── StructuredDraft paragraph mapping (research-contract-refactor Phase A) ──
# Binds each report paragraph to the claims + evidence it uses, and reports
# which claims were left unused.
#
# Review 2026-08-03: the FORMAL source of truth is Editor1's EXPLICIT markers
# (<!-- paragraph_id: ... -->, <!-- claim_ids: ... -->, <!-- evidence_ids: ... -->).
# The citation-marker + text-verbatim heuristic is retained ONLY as a fallback,
# and every heuristic paragraph is flagged mapping_source="heuristic" so the
# Verifier (Phase C) can prioritize paragraphs that lack explicit mapping.

_CITATION_MARKER_RE = re.compile(r"\[([A-Za-z_][A-Za-z0-9_\-]*)\](?!\()")
_EXPLICIT_MARKER_RE = re.compile(r"<!--\s*([a-z_]+)\s*:\s*([^>]*?)\s*-->")


def _extract_cited_evidence_ids(text: str) -> list[str]:
    """Extract bare [evidence_id] citation markers, ignoring markdown links."""
    return [match.group(1) for match in _CITATION_MARKER_RE.finditer(text or "")]


def _parse_explicit_paragraph_markers(text: str) -> tuple[str | None, list[str], list[str]]:
    """Parse Editor1 explicit mapping markers.

    Returns (paragraph_id, claim_ids, evidence_ids). Id lists are comma/space
    separated. Empty lists mean "no explicit mapping for that axis".
    """
    paragraph_id: str | None = None
    claim_ids: list[str] = []
    evidence_ids: list[str] = []
    for match in _EXPLICIT_MARKER_RE.finditer(text or ""):
        key = match.group(1).strip().casefold()
        ids = [v.strip() for v in re.split(r"[,，\s]+", match.group(2).strip()) if v.strip()]
        if key == "paragraph_id":
            paragraph_id = ids[0] if ids else None
        elif key in ("claim_ids", "claim_id"):
            claim_ids = ids
        elif key in ("evidence_ids", "evidence_id"):
            evidence_ids = ids
    return paragraph_id, claim_ids, evidence_ids


def _strip_explicit_markers(text: str) -> str:
    """Remove <!-- ... --> marker lines from the visible paragraph text."""
    lines = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _heuristic_mapping_confidence(
    *,
    text_matched_claims: list[str],
    evidence_overlap_claims: list[str],
) -> float:
    """Deterministic heuristic confidence (0..0.95) for non-explicit bindings.

    text-verbatim matching is the strongest heuristic signal; pure evidence
    overlap is weaker; no binding at all scores 0.
    """
    if text_matched_claims:
        return 0.9
    if evidence_overlap_claims:
        return 0.6
    return 0.0


def _validate_paragraph_mapping(
    *,
    paragraph: dict[str, Any],
    claim_by_id: dict[str, dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    ev_ids_in_claims: dict[str, set[str]],
) -> None:
    """Deterministic validation of a paragraph's claim/evidence binding.

    "editor_explicit" means the mapping SOURCE is Editor1's marker — it does NOT
    mean the mapping is CORRECT (review 2026-08-03). This checks:
    - every claim_id exists
    - every evidence_id exists
    - every evidence_id belongs to at least one bound claim's support set
    Sets mapping_validated / mapping_issues on the paragraph.
    """
    issues: list[str] = []
    claim_ids = [str(x) for x in paragraph.get("claim_ids", []) if x]
    evidence_ids = [str(x) for x in paragraph.get("evidence_ids", []) if x]

    for cid in claim_ids:
        if cid not in claim_by_id:
            issues.append(f"claim_id {cid} does not exist")
    for eid in evidence_ids:
        if eid not in evidence_by_id:
            issues.append(f"evidence_id {eid} does not exist")
    # explicit/claimed evidence must be in at least one bound claim's support set
    bound_support: set[str] = set()
    for cid in claim_ids:
        if cid in claim_by_id:
            bound_support |= ev_ids_in_claims.get(cid, set())
    if evidence_ids and claim_ids and bound_support:
        foreign = [eid for eid in evidence_ids if eid not in bound_support]
        if foreign:
            issues.append(
                f"evidence {','.join(foreign)} not in any bound claim's support set"
            )

    paragraph["mapping_validated"] = not issues
    paragraph["mapping_issues"] = issues


def _annotate_draft_paragraph_mapping(
    *,
    sections: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bind paragraphs to claim_ids/evidence_ids and compute unused_claim_ids.

    - EXPLICIT path: Editor1 `<!-- claim_ids/evidence_ids -->` markers are the
      formal mapping (mapping_source="editor_explicit", confidence=1.0).
    - HEURISTIC path (fallback): `[evidence_id]` citation markers + claim text
      verbatim match (mapping_source="heuristic", confidence<1.0).
    - unused_claim_ids: report-level claims not bound to any paragraph.

    Returns {"sections": [...], "unused_claim_ids": [...]}. Pure and additive.
    """
    claim_by_id: dict[str, dict[str, Any]] = {}
    ev_ids_in_claims: dict[str, set[str]] = {}
    for claim in claims:
        if not isinstance(claim, dict) or not claim.get("claim_id"):
            continue
        cid = str(claim["claim_id"])
        claim_by_id[cid] = claim
        ev_ids_in_claims[cid] = {
            str(eid) for eid in claim.get("evidence_ids", []) if eid
        }

    valid_evidence_ids = {
        str(e.get("evidence_id")) for e in evidence if isinstance(e, dict) and e.get("evidence_id")
    }
    evidence_by_id = {
        str(e.get("evidence_id")): e for e in evidence if isinstance(e, dict) and e.get("evidence_id")
    }
    used_claim_ids: set[str] = set()

    for section in sections:
        if not isinstance(section, dict):
            continue
        body = str(section.get("markdown_body") or "")
        paragraphs = section.get("paragraphs")
        if not isinstance(paragraphs, list) or not paragraphs:
            paragraph_texts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
            paragraphs = [
                {
                    "paragraph_id": f"{section.get('section_id') or 'sec'}.p{i + 1}",
                    "text": p,
                }
                for i, p in enumerate(paragraph_texts)
            ]
        seen_paragraph_ids: set[str] = set()
        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                continue
            raw_text = str(paragraph.get("text") or "")
            explicit_pid, explicit_claims, explicit_evs = _parse_explicit_paragraph_markers(raw_text)
            explicit = bool(explicit_claims or explicit_evs or explicit_pid)

            # Visible text without markers; evidence citation parse uses it.
            text = _strip_explicit_markers(raw_text) if explicit else raw_text
            cited = [
                eid for eid in _extract_cited_evidence_ids(text)
                if eid in valid_evidence_ids or not valid_evidence_ids
            ]

            paragraph_evidence_ids = [str(x) for x in paragraph.get("evidence_ids", []) if x]
            if explicit_evs:
                paragraph["evidence_ids"] = list(dict.fromkeys([*paragraph_evidence_ids, *explicit_evs]))
            else:
                paragraph["evidence_ids"] = list(dict.fromkeys([*paragraph_evidence_ids, *cited]))
            if explicit_pid:
                paragraph["paragraph_id"] = explicit_pid
            paragraph["text"] = text

            normalized_text = _normalize_for_match(text)
            text_matched_claims: list[str] = []
            evidence_overlap_claims: list[str] = []
            if not explicit_claims:
                for cid, claim in claim_by_id.items():
                    shares_evidence = bool(set(cited) & ev_ids_in_claims.get(cid, set()))
                    text_present = (
                        bool(normalized_text)
                        and _normalize_for_match(claim.get("text")) in normalized_text
                    )
                    if text_present:
                        text_matched_claims.append(cid)
                    elif shares_evidence:
                        evidence_overlap_claims.append(cid)

            existing_claim_ids = [str(x) for x in paragraph.get("claim_ids", []) if x]
            if explicit_claims:
                merged_claims = list(dict.fromkeys([*existing_claim_ids, *explicit_claims]))
                paragraph["mapping_source"] = "editor_explicit"
                paragraph["mapping_confidence"] = 1.0
            else:
                merged_claims = list(dict.fromkeys([*existing_claim_ids, *text_matched_claims, *evidence_overlap_claims]))
                paragraph["mapping_source"] = "heuristic"
                paragraph["mapping_confidence"] = _heuristic_mapping_confidence(
                    text_matched_claims=text_matched_claims,
                    evidence_overlap_claims=evidence_overlap_claims,
                )
            paragraph["claim_ids"] = merged_claims
            used_claim_ids.update(merged_claims)

            # ── Validate binding (ID existence + claim-evidence support) ──
            _validate_paragraph_mapping(
                paragraph=paragraph,
                claim_by_id=claim_by_id,
                evidence_by_id=evidence_by_id,
                ev_ids_in_claims=ev_ids_in_claims,
            )
            pid = str(paragraph.get("paragraph_id") or "")
            if pid:
                if pid in seen_paragraph_ids:
                    issues = list(paragraph.get("mapping_issues", []))
                    issues.append(f"duplicate paragraph_id {pid}")
                    paragraph["mapping_issues"] = issues
                    paragraph["mapping_validated"] = False
                seen_paragraph_ids.add(pid)
        section["paragraphs"] = paragraphs

    unused_claim_ids = [
        cid for cid in claim_by_id if cid not in used_claim_ids
    ]
    return {"sections": sections, "unused_claim_ids": unused_claim_ids}


def _merge_llm_into_structured_report(
    *,
    llm_markdown: str,
    structured_markdown: str,
    llm_sections: list[dict[str, Any]],
    structured_sections: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Merge LLM output into the structured report template.

    Uses the structured report as the base (guarantees full section coverage)
    but replaces dimension body sections with LLM content when it's richer.
    """
    if len(llm_markdown) > len(structured_markdown) * 1.3:
        # LLM output is significantly longer — prefer it but add missing sections
        merged = llm_markdown
        # Check for missing critical sections
        for required in ["执行摘要", "方法与口径", "风险", "结论"]:
            if required not in llm_markdown:
                # Find the section in structured and append
                start = structured_markdown.find(f"## {required}")
                if start > 0:
                    end = structured_markdown.find("\n## ", start + 5)
                    section_text = structured_markdown[start:end] if end > 0 else structured_markdown[start:]
                    merged = merged.rstrip() + "\n\n" + section_text
        return merged, llm_sections or structured_sections
    # Default: use structured
    return structured_markdown, structured_sections


def _build_minimal_draft_from_claims(
    *,
    query: str,
    claims: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Build a minimal readable draft when LLM output is insufficient."""
    ev_map = {str(e.get("evidence_id")): e for e in evidence_items if isinstance(e, dict)}

    sections = []
    # Group claims by family
    family_claims: dict[str, list[dict[str, Any]]] = {}
    for c in claims:
        family = str(c.get("claim_family", "other"))
        family_claims.setdefault(family, []).append(c)

    # ── Map claim_family to section_role for review alignment ──
    _FAMILY_TO_ROLE: dict[str, str] = {
        "policy_basis": "policy_evidence",
        "local_rollout": "local_implementation",
        "execution_evidence": "project_execution",
        "execution": "project_execution",
        "company_disclosure": "corporate_disclosure",
        "disclosure": "corporate_disclosure",
        "statistics_or_data": "industry_data",
        "risk_assessment": "risk_and_uncertainty",
    }

    for family, group_claims in family_claims.items():
        paras = []
        for i, c in enumerate(group_claims, 1):
            ev_ids = [str(eid) for eid in c.get("evidence_ids", [])]
            ev_notes = []
            for eid in ev_ids[:3]:
                ev = ev_map.get(eid, {})
                summary = str(ev.get("summary", ""))[:120]
                if summary:
                    ev_notes.append(summary)
            confidence = "medium"
            if c.get("supported") and any(
                ev_map.get(eid, {}).get("support_strength", 0) > 0.5
                for eid in ev_ids
            ):
                confidence = "high"
            elif not c.get("supported"):
                confidence = "low"
            paras.append({
                "paragraph_id": f"p_{family}_{i}",
                "text": str(c.get("text", "")),
                "claim_ids": [str(c.get("claim_id", ""))],
                "evidence_ids": ev_ids[:3],
                "confidence": confidence,
                "limitations": ev_notes[:2],
                "argument_posture": "evidence_backed" if c.get("supported") else "exploratory",
            })

        section_role = _FAMILY_TO_ROLE.get(family, "dimension_chapter")
        sections.append({
            "section_id": f"sec_{family}",
            "title": family.replace("_", " ").title(),
            "section_role": section_role,
            "argument_posture": "evidence_backed",
            "markdown_body": chr(10).join(
                f"**{p['text']}**" + chr(10) +
                (f"  证据: {chr(10).join(p.get('limitations', [])[:2])}" if p.get("limitations") else "")
                for p in paras
            ),
            "paragraphs": paras,
        })

    # ── Phase 4: Build proper report structure ──
    total_sources = len({str(s.get("source_id", "")) for s in sources})
    supported_claims = sum(1 for c in claims if c.get("supported"))
    total_claims = len(claims)
    source_families_used = {
        str(s.get("source_family", "unknown")) for s in sources
    }

    # Title
    report_md = f"# {query}\n\n"

    # Executive Summary
    report_md += "## 执行摘要\n\n"
    summary_parts = [
        f"本报告针对「{query}」进行了证据驱动的研究分析。",
        f"共检索并筛选 {total_sources} 个来源, "
        f"提取 {len(evidence_items)} 条证据, "
        f"形成 {total_claims} 条可审计研究断言 "
        f"({supported_claims} 条有证据支撑)。",
    ]
    if source_families_used:
        families_cn = {
            "policy_document": "政策文件", "company_disclosure": "公司披露",
            "exchange_disclosure": "交易所披露",
            "tender_procurement": "招投标交易",
            "official_statistics": "官方统计",
        }
        family_names = [families_cn.get(f, f) for f in source_families_used]
        summary_parts.append(f"覆盖源类型: {', '.join(family_names)}。")
    report_md += " ".join(summary_parts) + "\n\n"

    # Method and Scope
    report_md += "## 方法与口径\n\n"
    report_md += (
        "本报告基于公开可获取的官方政策文件、上市公司年报与公告、"
        "公共资源交易平台公示信息及行业统计数据。所有结论均标注对应的"
        "证据来源和支撑强度。未覆盖的证据面向和不确定结论在风险章节中"
        "单独说明。\n\n"
    )

    # Dimension body sections (from family groups)
    for family, group_claims in family_claims.items():
        section_role = _FAMILY_TO_ROLE.get(family, "dimension_chapter")
        title = {
            "policy_basis": "政策依据", "local_rollout": "地方落地",
            "execution_evidence": "项目执行", "execution": "项目执行",
            "company_disclosure": "企业披露", "disclosure": "企业披露",
            "statistics_or_data": "行业数据", "risk_assessment": "风险与不确定性",
        }.get(family, family.replace("_", " ").title())
        report_md += f"## {title}\n\n"
        for _i, c in enumerate(group_claims, 1):
            claim_text = str(c.get("text", ""))
            ev_ids = [str(eid) for eid in c.get("evidence_ids", [])]
            confidence = "高" if c.get("supported") else "待验证"

            report_md += f"**{claim_text}**\n\n"
            report_md += f"  - 支撑强度: {confidence}"
            if ev_ids:
                for eid in ev_ids[:3]:
                    ev = ev_map.get(eid, {})
                    ev_summary = str(ev.get("summary", ""))[:200]
                    strength = ev.get("support_strength", "?")
                    if ev_summary:
                        report_md += f"\n  - 证据 [{eid}] (强度:{strength}): {ev_summary}"
            report_md += "\n\n"
        sections.append({
            "section_id": f"sec_{family}",
            "title": title,
            "section_role": section_role,
            "argument_posture": "evidence_backed",
            "markdown_body": "",  # Filled by markdown above
            "paragraphs": paras,
        })

    # Risk and Uncertainty
    report_md += "## 风险与不确定性\n\n"
    risks_found = False
    for c in claims:
        if c.get("_low_confidence") or not c.get("supported"):
            if not risks_found:
                risks_found = True
        if c.get("_low_confidence"):
            report_md += f"- **待验证**: {str(c.get('text', ''))[:150]}"
            lims = c.get("limitations", [])
            if isinstance(lims, list) and lims:
                report_md += f" (限制: {', '.join(str(lim) for lim in lims[:2])})"
            report_md += "\n"
    if not risks_found:
        report_md += (
            "当前证据覆盖面有限, 部分维度可能缺少交叉验证。"
            "建议在关键结论引用前复核原始来源。\n"
        )
    report_md += "\n"

    # Conclusion
    report_md += "## 结论与后续研究方向\n\n"
    if supported_claims > 0:
        report_md += (
            f"基于当前证据, 共 {supported_claims}/{total_claims} 条研究断言获得证据支撑。"
        )
    unsupported_families = [
        f for f, cs in family_claims.items()
        if not any(c.get("supported") for c in cs)
    ]
    if unsupported_families:
        report_md += (
            f"以下维度证据不足, 建议补充搜索: "
            f"{', '.join(unsupported_families)}。\n"
        )
    else:
        report_md += "各维度均已找到支撑证据。\n"
    report_md += "\n"

    # Source Notes (replaces Audit Appendix at the end)
    report_md += "## 来源说明\n\n"
    report_md += (
        "以下为本次报告引用的全部来源。每个来源标注了源族(source family)和类型, "
        "便于判断证据的可信度和适用范围。\n\n"
    )
    report_md += "| 来源ID | 标题 | 源族 | 可信度 | 使用方式 | URL |\n"
    report_md += "|---|---|---|---|---|\n"
    for s in sources[:10]:
        sid = str(s.get("source_id", ""))
        title = str(s.get("title", ""))[:60]
        family = str(s.get("source_family", ""))
        url = str(s.get("url", ""))[:80]
        report_md += f"| {sid} | {title} | {family} | {url} |\n"

    return report_md, sections


def _build_narrative_fallback_from_claims(
    *,
    query: str,
    claims: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Compose a readable deterministic report without inventing new facts."""
    evidence_by_id = {
        str(item.get("evidence_id")): item
        for item in evidence_items
        if isinstance(item, dict) and item.get("evidence_id")
    }
    clean_excerpt = getattr(_impl, "_clean_report_excerpt", lambda text: str(text or "").strip())
    family_titles = {
        "policy_basis": "政策基础与制度方向",
        "local_rollout": "地方落地与区域协同",
        "execution_evidence": "项目执行与落地信号",
        "execution": "项目执行与落地信号",
        "company_disclosure": "企业披露与经营验证",
        "disclosure": "企业披露与经营验证",
        "statistics_or_data": "统计验证与规模判断",
        "risk_assessment": "约束条件与反向证据",
    }
    family_roles = {
        "policy_basis": "policy_evidence",
        "local_rollout": "local_implementation",
        "execution_evidence": "project_execution",
        "execution": "project_execution",
        "company_disclosure": "corporate_disclosure",
        "disclosure": "corporate_disclosure",
        "statistics_or_data": "industry_data",
        "risk_assessment": "risk_and_uncertainty",
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for claim in claims:
        if isinstance(claim, dict):
            grouped.setdefault(str(claim.get("claim_family") or "other"), []).append(claim)

    def _sentence(value: Any) -> str:
        text = str(value or "").strip().rstrip("。！？.!?")
        return f"{text}。" if text else ""

    def _family_title(family: str) -> str:
        normalized = re.sub(r"[_\-]+", " ", family).casefold()
        semantic_titles = (
            (("policy", "政策"), "政策基础与制度方向"),
            (("overall", "assessment", "综合", "总体"), "综合评估"),
            (("coordination", "synergy", "multi city", "cross regional", "协同"), "跨区域协同"),
            (("dominance", "leader", "location", "local", "regional", "city", "主导", "核心"), "区域主导格局"),
            (("project", "execution", "tender", "procurement", "项目执行", "招标", "采购"), "项目执行与落地信号"),
            (("company", "disclosure", "enterprise", "企业披露", "公司披露"), "企业披露与经营验证"),
            (("investment", "capital", "funding", "企业投资", "投资", "资金"), "企业投资与资金条件"),
            (("technology", "technical", "maturity", "产业化", "技术"), "技术成熟度与产业化能力"),
            (("regulatory", "compliance", "approval", "filing", "备案", "审批", "合规"), "审批与合规条件"),
            (("statistic", "data", "scale", "production", "统计", "数据", "规模", "产量"), "统计验证与规模判断"),
            (("vehicle", "整车"), "整车产业"),
            (("battery", "电池"), "电池产业链"),
            (("parts", "component", "零部件"), "零部件产业链"),
            (("fiscal", "subsidy", "fund", "财政", "补贴", "基金"), "财政支持与产业资金"),
            (("resource", "资源"), "资源基础"),
            (("transport", "infrastructure", "交通", "基础设施"), "交通与基础设施条件"),
            (("power", "energy", "电力", "能源"), "电力与能源条件"),
            (("environment", "land", "环评", "环境", "土地"), "环境与土地约束"),
            (("risk", "constraint", "风险", "约束"), "约束条件与反向证据"),
        )
        for markers, title in semantic_titles:
            if any(marker in normalized for marker in markers):
                return title
        return family_titles.get(family, "专题证据分析")

    def _claim_paragraph(claim: dict[str, Any]) -> tuple[str, list[str]]:
        claim_text = _sentence(claim.get("text"))
        evidence_ids = [
            str(item) for item in list(claim.get("evidence_ids") or [])
            if str(item) in evidence_by_id
        ][:3]
        summaries = [
            _sentence(clean_excerpt(str(evidence_by_id[item].get("summary") or ""))[:320])
            for item in evidence_ids
            if evidence_by_id[item].get("summary")
        ][:2]
        citations = "、".join(f"[{item}]" for item in evidence_ids)
        if claim.get("supported") and citations:
            support = f"这一判断由证据 {citations} 支撑"
            if summaries:
                support += f"；相关材料显示，{' '.join(summaries)}"
            paragraph = f"现有证据表明，{claim_text}{support}"
        elif citations:
            paragraph = (
                f"现有材料提出，{claim_text}但证据 {citations} 尚不足以形成稳定结论，"
                "应把它视为需要继续核验的研究假设。"
            )
        else:
            paragraph = (
                f"研究断言认为，{claim_text}当前没有可直接定位的证据支撑，"
                "因此不能据此作确定性判断。"
            )
        limitations = list(claim.get("limitations") or [])
        if limitations:
            paragraph += f" 当前限制是：{'；'.join(str(item) for item in limitations[:2])}。"
        return paragraph, evidence_ids

    supported = [item for item in claims if isinstance(item, dict) and item.get("supported")]
    unsupported = [item for item in claims if isinstance(item, dict) and not item.get("supported")]
    headline_claims = "；".join(
        str(item.get("text") or "").strip().rstrip("。") for item in supported[:2]
    )
    if not headline_claims:
        headline_claims = "当前证据不足以形成稳定的方向性判断"
    source_ids = {
        str(item.get("source_id"))
        for item in sources if isinstance(item, dict) and item.get("source_id")
    }
    source_ids.update(
        str(item.get("source_id"))
        for item in evidence_items if isinstance(item, dict) and item.get("source_id")
    )
    source_families = sorted({
        str(item.get("source_family") or "unknown")
        for item in sources if isinstance(item, dict)
    } | {
        str(item.get("source_family"))
        for item in evidence_items
        if isinstance(item, dict) and item.get("source_family")
    })
    markdown_parts = [
        f"# {query}",
        "## 执行摘要",
        (
            f"基于 {len(source_ids)} 个来源、{len(evidence_items)} 条证据和 {len(claims)} 条研究断言，"
            f"现有材料更支持以下初步判断：{headline_claims}。"
            "该结论是对当前公开证据的综合，不等同于对未来结果的确定性预测。"
        ),
        "## 研究方法与边界",
        (
            "本报告按政策、地方落地、项目执行、企业披露和统计验证等证据链组织分析。"
            "正文只复述现有 claim 与 evidence 能支持的内容，不用缺失材料补齐叙事；"
            + (
                f"当前覆盖 {len(source_families)} 类来源"
                if source_families
                else "当前来源类别元数据不完整"
            )
            + f"，其中仍有 {len(unsupported)} 条断言缺少充分支持。"
        ),
    ]
    sections: list[dict[str, Any]] = []
    section_summaries: list[str] = []
    title_counts: dict[str, int] = {}
    for family, family_claims in grouped.items():
        base_title = _family_title(family)
        title_count = title_counts.get(base_title, 0)
        title_counts[base_title] = title_count + 1
        title = (
            base_title
            if title_count == 0
            else f"{base_title}（补充证据{title_count}）"
        )
        paragraphs: list[dict[str, Any]] = []
        prose: list[str] = []
        for index, claim in enumerate(family_claims, 1):
            paragraph, evidence_ids = _claim_paragraph(claim)
            prose.append(paragraph)
            paragraphs.append({
                "paragraph_id": f"p_{family}_{index}",
                "text": paragraph,
                "claim_ids": [str(claim.get("claim_id") or "")],
                "evidence_ids": evidence_ids,
                "confidence": "high" if claim.get("supported") else "low",
                "limitations": list(claim.get("limitations") or [])[:2],
                "argument_posture": "evidence_backed" if claim.get("supported") else "exploratory",
            })
        supported_count = sum(1 for item in family_claims if item.get("supported"))
        synthesis = (
            f"综合来看，本节 {len(family_claims)} 条判断中有 {supported_count} 条获得证据支持。"
            "这意味着该维度可以作为总体判断的一部分，但仍需与其他证据链交叉验证。"
        )
        prose.append(synthesis)
        section_summaries.append(f"{title}有 {supported_count}/{len(family_claims)} 条判断获得支持")
        body = "\n\n".join(prose)
        markdown_parts.extend([f"## {title}", body])
        sections.append({
            "section_id": f"sec_{family}",
            "title": title,
            "section_role": family_roles.get(family, "dimension_chapter"),
            "argument_posture": "evidence_backed" if supported_count else "exploratory",
            "markdown_body": body,
            "paragraphs": paragraphs,
        })

    chain_text = "；".join(section_summaries[:5]) or "各证据维度尚未形成可比较的支持关系"
    markdown_parts.extend([
        "## 综合判断与传导链条",
        (
            f"从证据链的连接情况看，{chain_text}。"
            "只有当政策方向能够被地方项目、企业披露或统计变化继续验证时，"
            "才能把方向性信号提升为落地判断；任何单一政策或单个项目都不足以替代这一链条。"
        ),
        "## 风险、不确定性与反向验证",
        (
            f"当前仍有 {len(unsupported)} 条断言缺少充分支持，且公开来源可能存在发布时间、"
            "统计口径和项目状态不一致。后续应优先补齐缺失的强证据类别，并复核关键证据原文；"
            "如果新增材料与现有判断冲突，应降低结论强度，而不是用更多同质材料覆盖反证。"
        ),
        "## 结论与后续研究方向",
        (
            f"现阶段可确认的是：{headline_claims}。这一结论的适用边界是当前已获取的公开证据，"
            "后续应围绕尚未支持的断言、地域精度和项目状态开展定向补证。"
        ),
        "## 来源说明",
        "来源详情、URL、source family 与证据强度保留在 dossier 和审计附录中，正文仅以内联证据 ID 标示支撑关系。",
    ])
    return "\n\n".join(markdown_parts).strip() + "\n", sections


def verify_claims_provider_backed(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    _sync_impl_dependencies()
    result = _impl.verify_claims_provider_backed(state, tool_session=tool_session)
    latest_draft = {}
    drafts = list(state.get("drafts", []))
    if drafts and isinstance(drafts[-1], dict):
        latest_draft = drafts[-1]
    sections = [
        section for section in list(latest_draft.get("sections", [])) if isinstance(section, dict)
    ]
    claims_by_id = {
        str(claim.get("claim_id") or ""): claim
        for claim in list(result.get("claims") or state.get("claims") or [])
        if isinstance(claim, dict)
    }
    evidence_map = {
        str(item.get("evidence_id") or ""): item
        for item in list(result.get("evidence") or state.get("evidence") or [])
        if isinstance(item, dict)
    }
    source_map = {
        str(item.get("source_id") or ""): item
        for item in list(result.get("sources") or state.get("sources") or [])
        if isinstance(item, dict)
    }
    for verification in list(result.get("claim_verifications", [])):
        claim_id = str(verification.get("claim_id") or "")
        notes = list(verification.get("notes", []))
        has_section = any(
            claim_id in list(paragraph.get("claim_ids", []))
            for section in sections
            for paragraph in list(section.get("paragraphs", []))
            if isinstance(paragraph, dict)
        )
        if not has_section and not any("readable section" in str(note) for note in notes):
            notes.append("The current Editor1 draft does not place this claim into a readable section.")
            verification["notes"] = notes
        claim = claims_by_id.get(claim_id)
        if claim:
            decisions = _claim_eligibility_decisions(
                claim=claim,
                evidence_map=evidence_map,
                source_map=source_map,
            )
            verification["claim_support_eligibility"] = decisions
            eligible_ids = [
                str(item.get("evidence_id") or "")
                for item in decisions
                if item.get("eligible") and str(item.get("evidence_id") or "")
            ]
            # G4 精简：support_status 改为规则判定（LLM 的状态与分数常矛盾——高分却
            # unsupported）。规则：eligible 证据数 ≥ 要求数 → supported；≥1 → partially；
            # 0 → unsupported。support_score 用 eligible 证据的平均 support_strength。
            requirement = str(claim.get("support_requirement") or "")
            required_count = _required_evidence_count(requirement)
            eligible_count = len(eligible_ids)
            if eligible_count >= max(required_count, 1):
                status = "supported"
            elif eligible_count >= 1:
                status = "partially_supported"
            else:
                status = "unsupported"
            verification["support_status"] = status
            verification["verified"] = status == "supported"
            verification["supported"] = status == "supported"
            # support_score = eligible 证据的平均 support_strength（单一数字来源）
            if eligible_ids:
                strengths = [
                    _evidence_float(evidence_map.get(eid, {}).get("support_strength"), 0.0)
                    for eid in eligible_ids
                ]
                verification["support_score"] = round(
                    sum(strengths) / max(len(strengths), 1), 3
                )
            else:
                verification["support_score"] = 0.0
            if status == "unsupported" and not any(
                "eligible evidence" in str(note) for note in notes
            ):
                reason_codes = sorted(
                    {
                        str(item.get("reason_code") or "")
                        for item in decisions
                        if str(item.get("reason_code") or "")
                    }
                )
                notes.append(
                    "No eligible evidence supports this claim; reasons: "
                    + ", ".join(reason_codes)
                )
                verification["notes"] = notes
    for row in list(result.get("claim_support_matrix", [])):
        if not isinstance(row, dict):
            continue
        claim_id = str(row.get("claim_id") or "")
        claim = claims_by_id.get(claim_id)
        if not claim:
            continue
        decisions = _claim_eligibility_decisions(
            claim=claim,
            evidence_map=evidence_map,
            source_map=source_map,
        )
        row["claim_support_eligibility"] = decisions
        row["eligible_evidence_ids"] = sorted(
            {
                str(item.get("evidence_id") or "")
                for item in decisions
                if item.get("eligible") and str(item.get("evidence_id") or "")
            }
        )
        row["eligibility_passed"] = bool(row["eligible_evidence_ids"])
        if decisions and not row["eligibility_passed"]:
            row["verified"] = False
            row["supported"] = False
    return result


def _merge_route_recommendations(
    *,
    editor2_recommendation: dict[str, Any],
    verifier_recommendation: dict[str, Any],
) -> dict[str, Any]:
    merge = getattr(_impl, "_merge_route_recommendations", None)
    if callable(merge):
        return merge(
            editor2_recommendation=editor2_recommendation,
            verifier_recommendation=verifier_recommendation,
        )

    dedupe_terms = getattr(_impl, "_dedupe_terms", None)
    if not callable(dedupe_terms):
        dedupe_terms = lambda values: list(dict.fromkeys(str(item) for item in values if str(item).strip()))  # noqa: E731

    priority = {
        "human_review": 4,
        "collect_sources": 3,
        "editor1_draft": 2,
        "editor2_review": 1,
        "finalize_report": 0,
        "": -1,
    }

    candidates = [
        dict(editor2_recommendation or {}),
        dict(verifier_recommendation or {}),
    ]
    selected = max(
        candidates,
        key=lambda item: priority.get(str(item.get("preferred_route") or ""), -1),
    )
    return {
        "preferred_route": str(selected.get("preferred_route") or ""),
        "preferred_action": str(selected.get("preferred_action") or ""),
        "target_claim_ids": dedupe_terms(
            str(item)
            for item in list(selected.get("target_claim_ids", []))
            if str(item).strip()
        ),
        "reason": str(selected.get("reason") or ""),
        "editor2_recommendation": dict(editor2_recommendation or {}),
        "verifier_recommendation": dict(verifier_recommendation or {}),
    }


def collect_sources_provider_backed(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    _sync_impl_dependencies()
    search_provider_factory = getattr(_impl, "_search_provider", None)
    search_with_retry = getattr(_impl, "_search_with_retry", None)
    domain_from_url = getattr(_impl, "_domain_from_url", None)
    bounded_source_text = getattr(_impl, "_bounded_source_text", None)
    if not callable(search_provider_factory):
        return _impl.collect_sources_provider_backed(state, tool_session=tool_session)
    provider = search_provider_factory()
    plan = dict(state.get("plan") or {})
    existing_urls = {
        str(source.get("url", "")).strip()
        for source in list(state.get("sources", []))
        if source.get("url")
    }
    sources = list(state.get("sources", []))
    search_events: list[dict[str, Any]] = list(state.get("search_events", []))

    # ── Phase B.2: record PLANNED SearchTasks before execution (append-only) ──
    # Persist search tasks BEFORE any search runs, so planned-but-never-run tasks
    # are not lost and the planned->running->completed/failed chain is complete.
    try:
        from packages.research_harness.evaluation_recorder import (
            record_search_tasks,
        )
        from packages.research_harness.eval_persistence import RunEvaluationStore

        _store = RunEvaluationStore.from_dict(state.get("evaluation_store"))
        record_search_tasks(_store, plan, str(state.get("run_id") or ""))
        state = {**state, "evaluation_store": _store.to_dict()}
    except Exception:
        pass
    max_rounds = int(state.get("max_rounds", 12) or 12)
    # ADR 0001 #5: gap retrieval (dual-query, ~2 rounds per uncovered family) can
    # exceed the first-pass max_rounds budget. plan_task records how many gap
    # rounds it injected; widen the slice so they are not truncated. Gap rounds
    # are a deliberate remediation, not subject to the first-pass round budget.
    _gap_min = int(state.get("gap_min_search_rounds", 0) or 0)
    if _gap_min > max_rounds:
        max_rounds = _gap_min
    _spec_min = int(state.get("spec_first_pass_min_search_rounds", 0) or 0)
    if _spec_min > max_rounds:
        max_rounds = _spec_min

    all_rounds = [dict(r) for r in list(plan.get("search_rounds", [])) if isinstance(r, dict)]
    # ── 2026-08-11：两阶段搜索（用户指示）──
    # 段一：固定维度基本搜索（plan.search_rounds 已由 ensure_base_dimension_rounds
    #       保证 10 base+4 conditional 各一轮，taxonomy 定向词）。
    # 段二：基于已采集 source 检查维度覆盖，对未覆盖维度深度补搜（紧跟其后）。
    # 移除 slot 轮重排（LLM 按 claim slot 生成检索词的设计已废弃）。
    ordered_rounds = all_rounds[:max_rounds]

    for round_plan in ordered_rounds:
        sources, existing_urls, search_events = _run_search_round(
            state=state, round_plan=round_plan,
            provider=provider, search_with_retry=search_with_retry,
            domain_from_url=domain_from_url, bounded_source_text=bounded_source_text,
            sources=sources, existing_urls=existing_urls, search_events=search_events,
        )
        if not sources:
            # 段一无任何采集（搜索环境/query 问题）→ 不盲补第二轮，交给 gate 判定
            return {"sources": sources, "search_events": search_events}

    # ── 段二：未覆盖维度深度补搜 ──
    second_pass_rounds = _build_second_pass_rounds(
        query=str(state.get("query") or ""),
        plan=plan,
        sources=sources,
        query_requirements=dict(state.get("query_requirements") or {}),
    )
    for round_plan in second_pass_rounds:
        sources, existing_urls, search_events = _run_search_round(
            state=state, round_plan=round_plan,
            provider=provider, search_with_retry=search_with_retry,
            domain_from_url=domain_from_url, bounded_source_text=bounded_source_text,
            sources=sources, existing_urls=existing_urls, search_events=search_events,
        )
    return {"sources": sources, "search_events": search_events}


def _run_search_round(
    *,
    state: dict[str, Any],
    round_plan: dict[str, Any],
    provider: Any,
    search_with_retry: Any,
    domain_from_url: Any,
    bounded_source_text: Any,
    sources: list[dict[str, Any]],
    existing_urls: set[str],
    search_events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str], list[dict[str, Any]]]:
    """执行一个搜索轮：遍历轮内 search_phrases，采集 sources + 记录 search_events。

    2026-08-11：从 collect_sources_provider_backed 抽取的可复用 helper，供
    段一（固定维度基本搜索）和段二（未覆盖维度深度补搜）共用。
    """
    current_round = dict(round_plan)
    round_number = int(current_round.get("round_number", 1) or 1)
    include_domains = list(current_round.get("include_domains", []))
    expected_tier = str(current_round.get("expected_source_tier") or "C")
    target_dimensions = [
        str(item).strip()
        for item in list(current_round.get("target_dimensions", []))
        if str(item).strip()
    ]
    round_origin = str(current_round.get("_round_origin") or "similarity_driven")
    target_source_family = str(current_round.get("_target_source_family") or "")
    evidence_sections = [
        str(item).strip()
        for item in list(current_round.get("_evidence_sections", []))
        if str(item).strip()
    ]
    rejection_summary: dict[str, int] = {}
    accepted_result_count = 0
    target_family_match_count = 0
    target_family_mismatch_count = 0
    per_phrase_limit = _search_results_limit_for_round(
        query=str(state.get("query") or ""),
        round_plan=current_round,
        query_requirements=dict(state.get("query_requirements") or {}),
    )
    for phrase in list(current_round.get("search_phrases", []))[:6]:
        tavily_request_cls = getattr(_impl, "TavilySearchRequest", None)
        if tavily_request_cls is None or not callable(search_with_retry):
            return _impl.collect_sources_provider_backed(state, tool_session=tool_session)
        request = tavily_request_cls(
            query=str(phrase),
            include_domains=include_domains,
            max_results=per_phrase_limit,
            include_raw_content=True,
            search_depth="advanced",
        )
        response, retry_meta = search_with_retry(provider, request)
        usage = response.usage.model_dump(mode="json") if response.usage else {}
        search_events.append(
            {
                "round_number": round_number,
                "search_phrase": phrase,
                "status": response.status.value,
                "result_count": len(response.results),
                "estimated_credits": usage.get("estimated_credits", 0),
                "discovery_provider": usage.get("provider"),
                "discovery_metadata": dict(response.raw_response_metadata or {}),
                "attempt_count": retry_meta["attempt_count"],
                "retry_count": retry_meta["retry_count"],
                "attempt_statuses": retry_meta["attempt_statuses"],
                "retryable_error_count": retry_meta["retryable_error_count"],
                "target_dimensions": target_dimensions,
                "round_origin": round_origin,
                "target_source_family": target_source_family,
                "evidence_sections": evidence_sections,
                "requested_max_results": per_phrase_limit,
                "accepted_result_count": 0,
                "rejected_result_count": 0,
                "rejected_reasons": {},
                "target_family_match_count": 0,
                "target_family_mismatch_count": 0,
                "errors": [
                    (
                        error.model_dump(mode="json")
                        if hasattr(error, "model_dump")
                        else str(error)
                    )
                    for error in response.errors
                ],
            }
        )
        for result in response.results[:per_phrase_limit]:
            url = str(result.url or "").strip()
            if not url or url in existing_urls:
                continue
            existing_urls.add(url)
            if not callable(domain_from_url) or not callable(bounded_source_text):
                return _impl.collect_sources_provider_backed(state, tool_session=tool_session)
            domain = domain_from_url(url)
            full_page_text = str(result.raw_content or result.content or "")
            raw_text, raw_text_meta = bounded_source_text(full_page_text)
            # ── Preserve full text for chunk retrieval, bypassing 2400 limit ──
            full_text = full_page_text if len(full_page_text) > len(raw_text) + 50 else raw_text
            source_id = f"src_{len(sources) + 1:03d}"
            infer_source_family = getattr(_impl, "_infer_source_family", None)
            if callable(infer_source_family):
                source_family = infer_source_family(
                    domain=domain,
                    url=url,
                    title=result.title,
                    phrase=str(phrase),
                )
            else:
                source_family = "policy_document"
            # ADR 0002: normalize the produced family to the canonical 8-value
            # taxonomy so all downstream read sites see a regular value.
            # 方案B：unknown/未识别的源（知乎/自媒体/聚合站）不得兜底成 local_official
            # （否则它们会被当"官方"证据提取，实际 classify 为 aggregator → context_only）。
            # 仅官方域（gov.cn/官方域）才允许兜底 local_official；否则标 aggregator_or_unknown。
            try:
                from packages.sources.local_source_patterns import (
                    canonical_source_family,
                )
                from packages.sources.source_quality import (
                    _CENTRAL_OFFICIAL_DOMAINS,
                )
                raw_family = str(source_family or "").strip().lower()
                # 权威媒体/高校白名单：虽是聚合内容来源但可信（新华网/央媒/高校），
                # 不算低质聚合器，保留 local_official 兜底。
                _AUTHORITATIVE_MEDIA_SUFFIXES = (
                    ".news.cn", ".people.com.cn", ".xinhuanet.com",
                    ".cctv.com", ".gov.cn", ".edu.cn", ".ce.cn", ".gmw.cn",
                )
                is_official_domain = (
                    domain.endswith(_AUTHORITATIVE_MEDIA_SUFFIXES)
                    or domain in _CENTRAL_OFFICIAL_DOMAINS
                )
                if (raw_family in {"", "unknown"} or raw_family == "local_official") \
                        and not is_official_domain:
                    source_family = "aggregator_or_unknown"
                source_family = canonical_source_family(source_family)
            except Exception:
                pass
            rejection_reason = _source_rejection_reason(
                query=str(state.get("query") or ""),
                title=str(result.title or ""),
                url=url,
                domain=domain,
                content_text=str(result.content or ""),
                raw_text=raw_text,
                source_family=source_family,
                target_dimensions=target_dimensions,
                query_requirements=dict(state.get("query_requirements") or {}),
            )
            if rejection_reason is not None:
                rejection_summary[rejection_reason] = (
                    rejection_summary.get(rejection_reason, 0) + 1
                )
                continue
            # G4 精简（R1）：collect 阶段不再算 source_quality_v2 —— score_sources 单点
            # 统一评分（score_sources_single_point），避免双算。这里只存原始字段 + 元数据。
            target_family_match = (
                not target_source_family
                or _source_family_matches_requirement(target_source_family, source_family)
            )
            target_family_mismatch_reason = ""
            if target_source_family and not target_family_match:
                target_family_mismatch_count += 1
                target_family_mismatch_reason = (
                    f"target_source_family={target_source_family}; "
                    f"actual_source_family={source_family}"
                )
            else:
                target_family_match_count += 1
            sources.append(
                {
                    "source_id": source_id,
                    "url": url,
                    "domain": domain,
                    "title": result.title or url,
                    "snippet": result.content or "",
                    "raw_text": raw_text,
                    "raw_text_meta": raw_text_meta,
                    "full_text": full_text,
                    "source_family": source_family,
                    # source_quality_v2 在 score_sources 节点由 score_sources_single_point 填充
                    "search_phrase": str(phrase),
                    "discovered_by_phrase": str(phrase),
                    "published_date": result.published_date or "",
                    "search_score": result.score or 0.0,
                    "round": round_number,
                    "round_objective": current_round.get("objective", ""),
                    "expected_source_tier": expected_tier,
                    "target_dimensions": target_dimensions,
                    "round_origin": round_origin,
                    "target_source_family": target_source_family,
                    "target_source_family_match": target_family_match,
                    "target_source_family_mismatch_reason": target_family_mismatch_reason,
                    "evidence_sections": evidence_sections,
                    "provider": "search_discovery",
                    "discovery_provider": result.provider or usage.get("provider"),
                    "discovery_route": result.route
                    or response.raw_response_metadata.get("route"),
                    "content_origin": result.content_origin
                    or response.raw_response_metadata.get("content_origin")
                    or "search_discovery",
                    "discovery_metadata": dict(response.raw_response_metadata or {}),
                }
            )
            accepted_result_count += 1
        if search_events:
            search_events[-1]["accepted_result_count"] = accepted_result_count
            search_events[-1]["rejected_result_count"] = sum(rejection_summary.values())
            search_events[-1]["rejected_reasons"] = dict(rejection_summary)
            search_events[-1]["target_family_match_count"] = target_family_match_count
            search_events[-1]["target_family_mismatch_count"] = target_family_mismatch_count
    return sources, existing_urls, search_events


def _build_second_pass_rounds(
    *,
    query: str,
    plan: dict[str, Any],
    sources: list[dict[str, Any]],
    query_requirements: dict[str, Any],
) -> list[dict[str, Any]]:
    """段二：对未覆盖维度生成深度补搜轮（source 级覆盖判定）。

    2026-08-11 用户指示：固定维度基本搜索 → 检查覆盖 → 未覆盖维度深度补搜。
    维度 covered = 该维度任一 required（非 context）source_family 有 ≥1 source。
    未覆盖维度用 `_SEARCH_FIELD_TERMS` 映射其 search_key_fields 生成补搜短语
    （与 _fallback_phrases_for_dim 同源），标 `_second_pass_dim_backfill`。
    """
    try:
        from packages.research_harness import research_taxonomy
        from packages.research_harness.plan_semantic import (
            _SEARCH_FIELD_TERMS,
            _short_topic,
        )
    except Exception:
        return []

    location = str(query_requirements.get("target_location") or "").strip()
    base_query = _gap_core_topic(query, location)
    topic = _short_topic(query)

    # 已采集 sources 的 family 覆盖（canonical）
    covered_families = {
        canonical_source_family(str(s.get("source_family") or ""))
        for s in sources if isinstance(s, dict) and s.get("source_family")
    }
    # context family 不触发补搜（industry_research 等一搜就覆盖，会虚高）
    context_families = set(getattr(research_taxonomy, "CONTEXT_FAMILIES", set()))

    dims = [
        d for d in (plan.get("dimension_plan") or [])
        if isinstance(d, dict) and d.get("dimension_id") and d.get("dimension_type")
    ]
    # 固定维度 = 基础 + conditional
    base_types = {
        str(v.get("label") or k) for k, v in getattr(research_taxonomy, "DIMENSIONS", {}).items()
        if v.get("base_or_conditional") == "base"
    }
    # 用 dimension_type 判定维度是否属固定集（通过 taxonomy canonicalize）
    from packages.research_harness import research_taxonomy as _rt

    rounds: list[dict[str, Any]] = []
    for dim in dims:
        dim_id = str(dim.get("dimension_id") or "")
        dim_type = _rt.canonicalize_dimension_type(str(dim.get("dimension_type") or ""))
        dim_meta = _rt.DIMENSIONS.get(dim_type, {})
        if dim_meta.get("base_or_conditional") not in {"base", "conditional"}:
            continue  # 只补搜固定维度
        req_fams = {
            canonical_source_family(str(f)) for f in (dim.get("source_families") or [])
            if str(f).strip()
        }
        req_fams -= context_families
        if not req_fams:
            continue
        if req_fams & covered_families:
            continue  # 该维度任一 required family 有 source → 已覆盖
        # 未覆盖 → 生成补搜短语（search_key_fields → 定向词）
        phrases: list[str] = []
        for field in dim_meta.get("search_key_fields", []) or []:
            term = _SEARCH_FIELD_TERMS.get(str(field))
            if term:
                phrase = _normalize_space(f"{topic} {term}")[:120] if topic else term
                if phrase and phrase not in phrases:
                    phrases.append(phrase)
        # 兜底：直接用维度 heading 作为定向词
        if not phrases:
            heading = str(dim.get("expected_section_heading") or dim_type)
            if heading:
                phrases.append(_normalize_space(f"{topic} {heading}")[:120])
        if not phrases:
            continue
        rounds.append({
            "round_number": 0,
            "objective": f"second-pass dim backfill: {dim_id}",
            "search_phrases": phrases[:_SECOND_PASS_MAX_PHRASES_PER_DIM],
            "include_domains": [],
            "target_dimensions": [dim_id],
            "expected_source_tier": "B",
            "_round_origin": "second_pass_dim_backfill",
            "_second_pass_dim_backfill": True,
        })
        if len(rounds) >= _SECOND_PASS_MAX_ROUNDS:
            break
    return rounds


_SECOND_PASS_MAX_ROUNDS = 6
_SECOND_PASS_MAX_PHRASES_PER_DIM = 3


def _search_results_limit_for_round(
    *,
    query: str,
    round_plan: dict[str, Any],
    query_requirements: dict[str, Any],
) -> int:
    target_dimensions = {
        str(item).strip()
        for item in list(round_plan.get("target_dimensions", []))
        if str(item).strip()
    }
    objective = str(round_plan.get("objective") or "").lower()
    if "company_fundamentals" in target_dimensions or query_requirements.get(
        "needs_company_disclosure"
    ):
        return 8
    if "d_execution" in target_dimensions or "procurement" in objective or "project" in objective:
        return 8
    if "regional_benchmark" in target_dimensions or query_requirements.get("is_location_sensitive"):
        return 6
    if "market_scale" in target_dimensions:
        return 5
    if "d_policy" in target_dimensions:
        return 5
    return MAX_RESULTS_PER_SEARCH


def _source_rejection_reason(
    *,
    query: str,
    title: str,
    url: str,
    domain: str,
    content_text: str,
    raw_text: str,
    source_family: str,
    target_dimensions: list[str],
    query_requirements: dict[str, Any],
) -> str | None:
    haystack = _normalize_space(" ".join([title, url, domain, content_text, raw_text])).lower()
    if _contains_spam_markers(title=title, url=url, haystack=haystack):
        return "spam_or_content_farm"
    required_anchor = _primary_anchor_for_query(query)
    if required_anchor and required_anchor.lower() not in haystack:
        return "missing_primary_topic_anchor"
    if "regional_benchmark" in set(target_dimensions):
        location = _first_location_value(query=query, query_requirements=query_requirements)
        if location and location not in " ".join([title, url, content_text, raw_text]):
            return "local_round_location_mismatch"
    if source_family in {"company_disclosure", "exchange_disclosure"}:
        if not any(token in haystack for token in ("年报", "披露", "公告", "cninfo", "交易所")):
            return "weak_disclosure_evidence"
    return None


def _contains_spam_markers(*, title: str, url: str, haystack: str) -> bool:
    title_lower = str(title or "").lower()
    url_lower = str(url or "").lower()
    combined = f"{title_lower} {url_lower} {haystack}"
    return any(marker.lower() in combined for marker in _SPAM_TITLE_MARKERS)


def _assess_graph_source_quality_v2(
    *,
    query: str,
    domain: str,
    url: str,
    title: str,
    snippet: str,
    extracted_text: str,
    source_family: str,
    published_date: str,
    discovered_by_phrase: str,
    expanded_terms: list[str],
) -> dict[str, Any]:
    try:
        from packages.sources.source_quality import assess_source_quality_v2

        return assess_source_quality_v2(
            query=query,
            domain=domain,
            url=url,
            title=title,
            snippet=snippet,
            extracted_text=extracted_text,
            source_family=source_family,
            published_date=published_date,
            discovered_by_phrase=discovered_by_phrase,
            expanded_terms=expanded_terms,
        ).to_dict()
    except Exception:
        return {
            "tier": "C",
            "source_role": "unknown",
            "freshness": {
                "score": 0.0,
                "label": "unknown",
                "publication_date": published_date or None,
                "date_source": "unknown",
                "age_days": None,
                "validity_status": "unknown",
                "notes": "Source quality assessment failed.",
            },
            "query_relevance": {
                "score": 0.0,
                "label": "unknown",
                "signals": {
                    "source_family_match": False,
                    "discovered_by_phrase": discovered_by_phrase,
                },
            },
            "credibility_score": 0.0,
            "usage_role": "context_only",
            "not_sufficient_for": ["primary_claim_support"],
        }


def score_sources_single_point(state: dict[str, Any]) -> dict[str, Any]:
    """G4 精简：source 评分单点执行（修 R1 双算 + 绕过字节码冻结评分器）。

    collect_sources 只存原始字段（不评分）；此函数在 score_sources 节点用活的
    `packages.sources.source_quality.assess_source_quality_v2` 对每个 source 评分一次，
    覆盖 source_quality_v2 / source_tier / source_usage_role / source_credibility_score /
    source_evaluator_mode。字节码 `_real_nodes_impl.pyc` 的冻结评分器不再参与。
    """
    query = str(state.get("query") or "")
    sources = []
    for source in list(state.get("sources") or []):
        if not isinstance(source, dict):
            sources.append(source)
            continue
        domain = str(source.get("domain") or "")
        url = str(source.get("url") or source.get("source_url") or "")
        title = str(source.get("title") or "")
        raw_text = str(source.get("raw_text") or source.get("clean_text") or "")
        quality = _assess_graph_source_quality_v2(
            query=query,
            domain=domain,
            url=url,
            title=title,
            snippet=str(source.get("snippet") or ""),
            extracted_text=raw_text[:4000],
            source_family=str(source.get("source_family") or ""),
            published_date=str(source.get("published_date") or ""),
            discovered_by_phrase=str(source.get("discovered_by_phrase") or ""),
            expanded_terms=list(source.get("expanded_terms") or []),
        )
        scored = dict(source)
        scored["source_quality_v2"] = quality
        scored["source_tier"] = quality.get("tier") or "C"
        scored["source_usage_role"] = quality.get("usage_role") or "context_only"
        scored["source_credibility_score"] = quality.get("credibility_score") or 0.0
        scored["source_evaluator_mode"] = "deterministic_rules_source_quality_v2_single_point"
        sources.append(scored)
    return {"sources": sources}


def _primary_anchor_for_query(query: str) -> str:
    for anchor in _PRIMARY_TOPIC_ANCHORS:
        if anchor in query:
            return anchor
    return ""


def _dim_required_evidence_types(dimension_type: str) -> set[str]:
    """按 research_taxonomy 维度主证据通道映射 evidence_type（维度版 evidence 覆盖判定）。

    只返回映射表内的类型，不做全量兜底（避免维度间证据串扰）。
    主判 source_family，evidence_type 仅兜底（本地源 family 命名漂移时靠类型救回）。
    """
    from packages.research_harness import research_taxonomy

    dtype = research_taxonomy.canonicalize_dimension_type(str(dimension_type or ""))
    mapping = {
        "project_execution": {"project_approval", "procurement_award"},
        "market_scale": {"statistics_metric", "industry_metric", "official_data_release"},
        "industry_chain": {"industry_metric", "company_disclosure_statement"},
        "supply_competition": {"company_disclosure_statement", "industry_metric"},
        "demand_scenarios": {"operator_data", "company_disclosure_statement"},
        "technology_product": {"certification_record", "implementation_rule"},
        "policy_regulation": {"policy_original", "implementation_plan", "policy_signal"},
        "local_rollout": {"implementation_plan", "project_approval"},
        "business_economics": {"company_disclosure_statement", "statistics_metric"},
        "risk_constraints": {"policy_signal", "implementation_plan"},
        "statistics": {"statistics_metric", "official_data_release", "industry_metric"},
        "company_fundamentals": {"company_disclosure_statement", "industry_metric"},
        "disclosure": {"company_disclosure_statement", "ir_disclosure"},
    }
    return set(mapping.get(dtype, set()))


def _dimension_coverage_report(state: dict[str, Any]) -> dict[str, Any]:
    """按 target_dimensions 分组统计 evidence 覆盖度（gate 判定唯一依据，无 claim）。

    每维度 {dimension_id, dimension_type, evidence_count, distinct_sources,
    min_evidence, covered, missing_key_fields}。证据→维度映射：
    evidence.source_family ∈ dim.required_source_families 或
    evidence.evidence_type ∈ _dim_required_evidence_types(dim.dimension_type)。
    """
    from packages.research_harness.plan_semantic import (
        _DEFAULT_MIN_EVIDENCE,
        build_evidence_requirement_spec,
    )

    plan = state.get("plan") or {}
    dims = {str(d.get("dimension_id")): d for d in (plan.get("dimension_plan") or []) if isinstance(d, dict)}
    spec = build_evidence_requirement_spec(plan)
    # 维度 → 最低 evidence 数（spec 或默认 2）
    min_ev: dict[str, int] = {}
    for entry in spec or []:
        if not isinstance(entry, dict):
            continue
        did = str(entry.get("dimension_id") or "")
        if did:
            min_ev[did] = max(min_ev.get(did, 0), int(entry.get("min_evidence") or _DEFAULT_MIN_EVIDENCE))
    for did in dims:
        min_ev.setdefault(did, _DEFAULT_MIN_EVIDENCE)

    evidence = list(state.get("evidence", []))
    # source_family 由 _enrich_evidence_semantics 补写；缺失时从 source 反查
    src_by_id = {str(s.get("source_id")): s for s in state.get("sources") or []}
    # 维度 → 合格 evidence
    dim_evidence: dict[str, list[dict]] = {did: [] for did in dims}
    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        ev_type = str(ev.get("evidence_type") or "")
        family = str(ev.get("source_family") or "")
        if not family:
            src = src_by_id.get(str(ev.get("source_id") or ""), {})
            family = str(src.get("source_family") or "")
        proof = str(ev.get("proof_strength") or "")
        if proof in {"context_only", "ineligible"}:
            continue  # 低质证据不计覆盖
        ev_family = canonical_source_family(family) if family else ""
        for did, dim in dims.items():
            # plan.dimension_plan 用 source_families 字段；兼容旧 required_source_families。
            raw_fams = dim.get("source_families") or dim.get("required_source_families") or []
            req_fams = {canonical_source_family(str(f)) for f in raw_fams if str(f).strip()}
            dim_type = str(dim.get("dimension_type") or "")
            if (ev_family and ev_family in req_fams) or (
                ev_type in _dim_required_evidence_types(dim_type)
            ):
                dim_evidence[did].append(ev)

    report: dict[str, dict] = {}
    # 2026-08-10：slot 级覆盖判定——维度 covered = 该维度任一 required/critical
    # claim slot 有 ≥1 条匹配 evidence（evidence 带 supports_slot_ids 时优先用；
    # 否则回退 evidence 条数 ≥ min_evidence 的旧判定）。
    contract = compile_research_contract(plan)
    slot_by_section: dict[str, list[dict[str, Any]]] = {}
    for sec in contract.get("sections", []):
        sid_ = str(sec.get("section_id") or "")
        slot_by_section.setdefault(sid_, []).extend(sec.get("claim_slots", []))
    for did, dim in dims.items():
        evs = dim_evidence[did]
        distinct_sources = {str(e.get("source_id") or "") for e in evs if e.get("source_id")}
        section_slots = [
            s for s in slot_by_section.get(did, [])
            if isinstance(s, dict) and str(s.get("required") or "") in {"critical", "required"}
        ]
        if section_slots:
            # slot 级：维度 covered = 任一 required slot 有匹配 evidence
            covered = any(
                any(str(s.get("slot_id")) in list(ev.get("supports_slot_ids") or []) for ev in evs)
                for s in section_slots
            ) or bool(evs)
        else:
            covered = len(evs) >= max(min_ev.get(did, 1), 1) and len(distinct_sources) >= 1
        report[did] = {
            "dimension_id": did,
            "dimension_type": str(dim.get("dimension_type") or ""),
            "expected_section_heading": str(dim.get("expected_section_heading") or ""),
            "required_source_families": sorted({
                canonical_source_family(str(f)) for f in (
                    dim.get("source_families") or dim.get("required_source_families") or []
                )
                if str(f).strip()
            }),
            "evidence_count": len(evs),
            "distinct_sources": len(distinct_sources),
            "min_evidence": min_ev.get(did, 1),
            "covered": covered,
            "missing_key_fields": [],
        }
    return report


def chief_gate_provider_backed(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    # ── Phase C：不再调字节码 gate（其 claim/obligation 判定在砍 claim 后失效）。
    # 基于维度 evidence 覆盖度判定，允许空缺（报告标注）。
    result: dict[str, Any] = {}
    decision = ""
    route_recommendation = _merge_route_recommendations(
        editor2_recommendation=dict(state.get("editor2_route_recommendation") or {}),
        verifier_recommendation=dict(state.get("verifier_route_recommendation") or {}),
    )
    preferred_action = str(route_recommendation.get("preferred_action") or "")
    preferred_route = str(route_recommendation.get("preferred_route") or "")
    claims = list(state.get("claims", []))
    sources = list(state.get("sources", []))
    review_issues = list(state.get("review_issues", []))
    verifications = list(state.get("claim_verifications", []))

    # ── Phase C：维度 evidence 覆盖度判定（无 claim 时 gate 的唯一依据） ──
    # 允许空缺：coverage 达标即 PASS（缺的维度在报告标注）；硬 blocker 优先 HUMAN_REVIEW。
    _dim_report = _dimension_coverage_report(state)
    state["dimension_coverage"] = _dim_report
    result["dimension_coverage"] = _dim_report
    _total_dims = max(len(_dim_report), 1)
    _covered_dims = sum(1 for r in _dim_report.values() if r.get("covered"))
    _dim_ratio = _covered_dims / _total_dims
    _loop = int(state.get("loop_count") or 0)
    # max_loop_count 显式传 0 表示不允许补证（loop budget 用尽直接终态判定）；
    # 不能用 `or 1` 把 0 抬成 1（否则 max_loop_count=0 也会先补一轮再终态）。
    _raw_max = state.get("max_loop_count")
    _max_loop = 0 if _raw_max is None else max(0, int(_raw_max))
    # ── Phase C：从维度覆盖派生 quality_scores（方案 A，保持契约不变） ──
    # evidence_coverage = 覆盖维度数 / 总维度数；final_score 用同一覆盖度（不再
    # 依赖已删除的 claim_verifications 产物）。blocker/低覆盖不隐藏：HUMAN_REVIEW
    # 分支也保留真实分数，由 runner/dossier 消费。
    _qs = dict(state.get("quality_scores") or {})
    _qs["evidence_coverage"] = round(_dim_ratio, 4)
    _qs.setdefault("citation_integrity", 1.0)
    _qs.setdefault("source_quality", 0.8)
    _qs.setdefault("contradiction_resolution", 1.0)
    _qs["final_score"] = round(
        _qs["evidence_coverage"] * 0.4
        + _qs["citation_integrity"] * 0.3
        + _qs["source_quality"] * 0.2
        + _qs["contradiction_resolution"] * 0.1,
        2,
    )
    result["quality_scores"] = dict(_qs)
    state["quality_scores"] = dict(_qs)
    # 硬质量 blocker（矛盾/虚假/风险）→ 无论 ratio 都 HUMAN_REVIEW
    _HARD_QUALITY = {"contradiction", "hallucination", "fabrication", "p0_risk"}
    _hard_blockers = [
        i for i in review_issues
        if str(i.get("issue_type") or "") in _HARD_QUALITY
    ]
    if _hard_blockers:
        result["decision"] = "HUMAN_REVIEW"
        result["gate_route_to"] = "human_review"
        result["gate_reason"] = (
            f"存在真实质量 blocker ({len(_hard_blockers)}个: "
            f"{', '.join(sorted({str(i.get('issue_type')) for i in _hard_blockers}))})"
        )
        result["required_actions"] = [{"action_type": "HUMAN_REVIEW", "target": None}]
        return result
    if _dim_ratio >= 1.0:
        result["decision"] = "PASS"
        result["gate_reason"] = f"全部 {_covered_dims}/{_total_dims} 维度 evidence 覆盖达标"
        result["gate_route_to"] = "finalize_report"
        result["required_actions"] = []
        return result
    elif _dim_ratio >= 0.5 and _loop >= _max_loop:
        # 允许空缺：补证轮用尽后 coverage 达标即 PASS，未覆盖维度报告标注
        uncovered = [
            r.get("expected_section_heading") or r.get("dimension_id")
            for r in _dim_report.values() if not r.get("covered")
        ]
        result["decision"] = "PASS"
        result["gate_route_to"] = "finalize_report"
        result["required_actions"] = []
        result["gate_reason"] = (
            f"维度覆盖 {_covered_dims}/{_total_dims} ({_dim_ratio:.0%})，补证轮已用尽 "
            f"({_loop}/{_max_loop})，按阈值 PASS；未覆盖维度报告标注: {', '.join(uncovered[:5])}"
        )
        return result
    elif _dim_ratio >= 0.5:
        result["decision"] = "ADD_EVIDENCE"
        result["gate_route_to"] = "collect_sources"
        uncovered_dims = [
            r.get("dimension_id") for r in _dim_report.values() if not r.get("covered")
        ]
        result["required_actions"] = [
            {"action_type": "ADD_EVIDENCE", "target": dim_id}
            for dim_id in uncovered_dims[:3]
        ]
        result["gate_reason"] = (
            f"维度 evidence 覆盖 {_covered_dims}/{_total_dims} ({_dim_ratio:.0%})，"
            f"需补 {len(uncovered_dims)} 个未覆盖维度"
        )
        result["loop_count"] = _loop + 1
        state["loop_count"] = _loop + 1  # 直接改 state（langgraph 增量合并可能丢 result 字段）
        return result
    elif _loop < _max_loop:
        result["decision"] = "ADD_EVIDENCE"
        result["gate_route_to"] = "collect_sources"
        result["required_actions"] = [
            {"action_type": "ADD_EVIDENCE", "target": did}
            for did in [r.get("dimension_id") for r in _dim_report.values() if not r.get("covered")][:3]
        ]
        result["gate_reason"] = (
            f"维度覆盖不足 ({_dim_ratio:.0%})，补证轮 {_loop+1}/{_max_loop}"
        )
        result["loop_count"] = _loop + 1
        state["loop_count"] = _loop + 1  # 直接改 state（langgraph 增量合并可能丢 result 字段）
        return result
    else:
        result["decision"] = "HUMAN_REVIEW"
        result["gate_route_to"] = "human_review"
        result["gate_reason"] = (
            f"维度 evidence 覆盖过低 ({_dim_ratio:.0%})，补证轮已用尽，需人工介入"
        )
        result["required_actions"] = [{"action_type": "HUMAN_REVIEW", "target": None}]
        return result
    result["gate_reason"] = str(result.get("gate_reason") or "")
    decision = str(result.get("decision") or "")
    low_diversity_risk = any(
        "fewer than two distinct sources" in str(note)
        for item in verifications
        for note in list(item.get("notes", []))
    )
    all_policy_basis = bool(claims) and all(
        str(claim.get("claim_family") or "") in {"policy_basis", "general"} for claim in claims
    )
    audited_source_families = {
        str(source.get("source_family") or "") for source in sources if source.get("source_id")
    }
    has_audited_baseline_sources = bool(
        audited_source_families
        & {"policy_document", "tender_procurement", "local_official"}
    )
    no_unsupported_claims = not any(
        str(item.get("support_status") or "") in {"unsupported", "contradicted"}
        for item in verifications
    )
    # ── Phase 4: Compute obligation coverage from claim_support_matrix ──
    support_matrix = list(state.get("claim_support_matrix", []))
    # Group by required_source_family: check if each family has ≥1 matched claim
    family_coverage: dict[str, bool] = {}
    for row in support_matrix:
        if not isinstance(row, dict):
            continue
        family = str(row.get("required_source_family") or "")
        if not family:
            continue
        # Coverage: prefer eligibility-aware support when available.
        has_evidence = (
            bool(row.get("eligibility_passed"))
            if "eligibility_passed" in row
            else bool(row.get("evidence_ids") or row.get("source_ids"))
        )
        current = family_coverage.get(family, False)
        family_coverage[family] = current or has_evidence
    all_obligations_covered = (
        len(family_coverage) > 0
        and all(family_coverage.values())
    )
    # Also check from claims if matrix is empty
    if not all_obligations_covered and not support_matrix:
        claim_families = {str(c.get("required_source_family") or "") for c in claims}
        all_supported = all(
            c.get("supported") for c in claims if c.get("required_source_family")
        )
        all_obligations_covered = bool(claim_families) and all_supported

    obligation_coverage = list(state.get("required_obligation_coverage", []))
    # The authoritative coverage is computed by the bytecode _impl and written to
    # result.contract_meta.chief_gate.required_obligation_coverage. The input
    # state usually does NOT carry it yet (verify_claims/_impl produce it during
    # this same gate step), so prefer the _impl output to avoid the family_covered
    # heuristic disagreeing with the coverage table the summary later reports.
    _impl_coverage = (
        dict(result.get("contract_meta") or {})
        .get("chief_gate", {})
        .get("required_obligation_coverage", [])
    )
    if _impl_coverage:
        obligation_coverage = list(_impl_coverage)
    # ── Relevance hard gate (A): a location obligation is only truly covered if
    # at least one CLAIM is actually about that location. The _impl marks
    # obl_location_precision covered from a `matched_ratio` word-frequency of the
    # location string in source text — so an out-of-region report that merely
    # mentions "合肥" in passing passes. Require non-empty supporting_claim_ids
    # (and a real matched_ratio) so a topically-off report drops to not-covered,
    # raising the gap and triggering the Phase 8 gap-retrieval loop.
    _LOCATION_MIN_RATIO = 0.5
    for _obl in obligation_coverage:
        if not isinstance(_obl, dict):
            continue
        if str(_obl.get("obligation_id") or "") != "obl_location_precision":
            continue
        if not _obl.get("covered"):
            continue
        supporting = list(_obl.get("supporting_claim_ids") or [])
        ratio = _obl.get("matched_ratio")
        ratio_ok = isinstance(ratio, (int, float)) and ratio >= _LOCATION_MIN_RATIO
        if not supporting or not ratio_ok:
            _obl["covered"] = False
            _obl["relevance_downgrade"] = (
                "no claim is about the target location"
                if not supporting
                else f"location match ratio {ratio} below {_LOCATION_MIN_RATIO}"
            )
    if not all_obligations_covered and obligation_coverage:
        all_obligations_covered = all(
            obl.get("covered") for obl in obligation_coverage
            if isinstance(obl, dict)
        )

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

    # Obligation gap: compute directly from claims, evidence, and sources
    # (claim_support_matrix and obligation_coverage may not be in gate state)
    # Collect which required_source_families have evidence support
    family_covered: dict[str, bool] = {}
    for claim in claims:
        family = str(claim.get("required_source_family") or "")
        if not family:
            continue
        ev_ids = [str(eid) for eid in claim.get("evidence_ids", [])]
        has_support = bool(ev_ids)
        if family not in family_covered:
            family_covered[family] = has_support
        else:
            family_covered[family] = family_covered[family] or has_support
    # Also check from matrix if available
    for row in support_matrix:
        if not isinstance(row, dict):
            continue
        family = str(row.get("required_source_family") or "")
        if not family:
            continue
        if family in family_covered and "eligibility_passed" not in row:
            continue
        has_ev = (
            bool(row.get("eligibility_passed"))
            if "eligibility_passed" in row
            else bool(row.get("evidence_ids") or row.get("source_ids"))
        )
        family_covered[family] = has_ev
    obligation_gap_count = sum(1 for v in family_covered.values() if not v)
    # Obligation truth: prefer the authoritative required_obligation_coverage
    # produced by verify_claims / chief_gate (it checks whether evidence really
    # comes from the required source family). The family_covered heuristic above
    # only checks that some claim has a non-empty evidence_ids list, which can
    # report a family as covered even when the evidence is from a different
    # family — that is exactly the blind-PASS gap this block must close. When
    # obligation_coverage is present, its `covered` field is the source of truth.
    if obligation_coverage:
        obligation_gap_count = sum(
            1 for o in obligation_coverage
            if isinstance(o, dict) and not o.get("covered")
        )
    has_obligation_gap = obligation_gap_count > 0
    # Write the reconciled gap count back so contract_meta (and the summary that
    # reads contract_meta.chief_gate.obligation_gap_count) agrees with the gate
    # decision and the required_obligation_coverage table. Otherwise the _impl's
    # stale family-heuristic value contradicts a PASS decision.
    _cm = dict(result.get("contract_meta") or {})
    _cg = dict(_cm.get("chief_gate") or {})
    _cg["obligation_gap_count"] = obligation_gap_count
    _cg["required_obligation_coverage"] = obligation_coverage
    _cm["chief_gate"] = _cg
    result["contract_meta"] = _cm
    result["required_obligation_coverage"] = obligation_coverage

    if (preferred_action == "HUMAN_REVIEW" or preferred_route == "human_review"):
        if all_obligations_covered:
            # Editor2/verifier recommend human review, but all required
            # source families are satisfied → downgrade to REVIEW_RISK
            result["decision"] = "REVIEW_RISK"
            result["gate_route_to"] = "editor2_review"
            result["required_actions"] = []
            result["gate_reason"] = (
                "所有 obligation 已覆盖, editor2/verifier 的 HUMAN_REVIEW "
                "推荐降级为 REVIEW_RISK"
            )
            return result
        result["decision"] = "HUMAN_REVIEW"
        result["gate_route_to"] = "human_review"
        result["required_actions"] = []
        if str(route_recommendation.get("reason") or ""):
            result["gate_reason"] = str(route_recommendation.get("reason") or "")
        # ── Phase 4: Attach P0 context for human reviewer ──
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
        return result
    # ── Phase 2 (PRD): Product-quality blocking rules ──
    # These only override when bytecode would otherwise PASS.
    # HUMAN_REVIEW from editor2/verifier remains higher authority.

    # Block 1: obligation gaps prevent PASS (but not HUMAN_REVIEW)
    # 方案 A（G4 精简）需在 _impl 字节码把 decision 改为 HUMAN_REVIEW 之前生效——
    # 但字节码在 loop 预算尽后先设 HUMAN_REVIEW。因此这里对 loop 已尽 + coverage 达标
    # 的情形，无论当前 decision 是 ADD_EVIDENCE 还是 HUMAN_REVIEW，都按 coverage 降级 PASS，
    # 避免 run 卡死在补证/人工介入循环。缺的维度由报告以"证据不足"诚实标注。
    _loop = int(state.get("loop_count") or 0)
    _max_loop = int(state.get("max_loop_count") or 1)
    # 用 verifications 的 support_status 算覆盖率（claims[].supported 不可靠——verify_claims
    # 规则化后 verification 的 supported 才对）。
    _verifications = list(state.get("claim_verifications", []))
    _claim_cov = 0.0
    if _verifications:
        _supported_claims = sum(
            1 for v in _verifications
            if str(v.get("support_status") or "") == "supported"
        )
        _claim_cov = _supported_claims / len(_verifications)
    elif claims:
        _supported_claims = sum(
            1 for c in claims if c.get("supported") is True
        )
        _claim_cov = _supported_claims / len(claims)
    if _loop >= _max_loop and _claim_cov >= 0.5 and decision in {
        "ADD_EVIDENCE", "REVISE_TEXT", "HUMAN_REVIEW", "PASS",
    }:
        # 方案 A 降级仅用于「证据数量够但来源族不全」。阻断降级的必须是真实质量缺陷：
        # 虚假断言/矛盾（不可信），以及「几乎全部 claim 都单源」（证据过窄）。
        # unsupported_claim / source_family_mismatch 反映的正是证据不足或 family 命名差异，
        # 是方案 A 要放行的（缺的维度以证据不足诚实标注），不阻断。
        _HARD_QUALITY_TYPES = {
            "contradiction", "hallucination", "fabrication", "p0_risk",
        }
        _quality_blockers = [
            i for i in review_issues
            if str(i.get("issue_type") or "") in _HARD_QUALITY_TYPES
        ]
        # 来源多样性：仅当「超半数 claim 都单源」才算证据过窄；个别单源不阻断。
        _low_diversity = False
        if support_matrix:
            _low_count = sum(
                1 for _row in support_matrix
                if isinstance(_row, dict) and int(_row.get("source_count") or 0) < 2
            )
            _low_diversity = _low_count / len(support_matrix) > 0.5
        if _quality_blockers or _low_diversity:
            result["decision"] = "HUMAN_REVIEW"
            result["gate_reason"] = (
                f"存在真实质量 blocker ({len(_quality_blockers)}个) 或来源多样性严重不足"
                f"（超半数 claim 单源），即使 coverage {_claim_cov:.0%} 达标也需人工介入。"
            )
            result["required_actions"] = [
                {"action_type": "HUMAN_REVIEW", "target": None}
            ]
            return result
        result["decision"] = "PASS"
        result["gate_reason"] = (
            f"补证轮次已用尽 ({_loop}/{_max_loop})，claim 覆盖率 {_claim_cov:.0%} "
            f"(>=0.5)，按阈值降级 PASS；未覆盖维度以证据不足诚实标注。"
        )
        result["required_actions"] = []
        return result
    if has_obligation_gap and decision in {"PASS", "ADD_EVIDENCE", "REVISE_TEXT"}:
        uncovered_names = [
            str(o.get("obligation_id", "?")) for o in obligation_coverage
            if isinstance(o, dict) and not o.get("covered")
        ] if obligation_coverage else ["obl_policy_primary"]
        claim_actions = _build_claim_evidence_actions(
            claims=claims,
            query=str(state.get("query") or ""),
            query_requirements=dict(state.get("query_requirements") or {}),
        )
        obligation_actions = [
            {"action_type": "ADD_EVIDENCE", "target": name}
            for name in uncovered_names[:3]
        ]
        result["decision"] = "ADD_EVIDENCE"
        result["gate_route_to"] = "collect_sources"
        result["required_actions"] = [*claim_actions[:3], *obligation_actions]
        result["gate_reason"] = (
            f"obligation 未覆盖 ({obligation_gap_count}个: "
            f"{', '.join(uncovered_names[:3])}) — "
            "必须补充对应源族的证据后才能通过"
        )
        return result

    # Phase 5: Same-domain overconcentration detection
    domain_counts: dict[str, int] = {}
    for source in sources:
        domain = str(source.get("domain", "") or source.get("url", ""))
        if domain:
            # Normalize: strip www and extract main domain
            domain = domain.replace("www.", "").split("/")[0]
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
    overconcentrated_domains = [
        d for d, c in domain_counts.items() if c >= 3 and len(domain_counts) > 1
    ]
    has_domain_overconcentration = len(overconcentrated_domains) > 0

    # Phase 5: Local precision enforcement
    local_precision = state.get("gate_local_precision", 1.0)
    if isinstance(local_precision, (int, float)):
        local_precision = float(local_precision)
    else:
        local_precision = 1.0
    is_location_query = bool(
        state.get("query_requirements", {}).get("is_location_sensitive")
        or state.get("query_requirements", {}).get("target_location")
    )
    has_weak_local_precision = (
        is_location_query and local_precision < 0.30
    )

    # Phase 5: Same-domain concentration prevents clean PASS
    if has_domain_overconcentration and decision in {"PASS", "REVISE_TEXT"}:
        result["decision"] = "REVIEW_RISK"
        result["gate_route_to"] = "editor2_review"
        result["required_actions"] = []
        result["gate_reason"] = (
            f"源过度集中 ({', '.join(overconcentrated_domains[:3])}) — "
            f"{len(overconcentrated_domains)}个域名占源总数{len(sources)}的比例过高, "
            "可能缺乏视角多样性"
        )
        return result

    # Phase 5: Weak local precision prevents PASS
    if has_weak_local_precision and decision in {"PASS", "REVISE_TEXT"}:
        result["decision"] = "ADD_EVIDENCE"
        result["gate_route_to"] = "collect_sources"
        result["required_actions"] = [
            {"action_type": "ADD_EVIDENCE", "target": "location_matched",
             "reason": f"地域匹配精度仅{local_precision:.0%}, 需补充本地源"}
        ]
        result["gate_reason"] = (
            f"地域精度不足 ({local_precision:.0%}) — "
            "指定地域查询的本地源占比过低, 需要补充本地源"
        )
        return result

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
        qs = dict(result.get("quality_scores") or {})
        original = qs.get("final_score", 0.7)
        qs["final_score"] = round(original * 0.85, 2)
        result["quality_scores"] = qs
        # Still allow PASS but with downgraded score

    # Override ADD_EVIDENCE when all obligations are already covered
    if decision == "ADD_EVIDENCE" and all_obligations_covered:
        result["decision"] = "PASS"
        result["gate_route_to"] = "finalize_report"
        result["required_actions"] = []
        result["gate_reason"] = "所有 obligation 已覆盖 — 无需追加证据, 直接通过"
        return result
    if preferred_action == "ADD_EVIDENCE" and decision in {"PASS", "REVISE_TEXT"}:
        result["decision"] = "ADD_EVIDENCE"
        result["gate_route_to"] = "collect_sources"
        if str(route_recommendation.get("reason") or ""):
            result["gate_reason"] = str(route_recommendation.get("reason") or "")
        return result
    if preferred_action == "REVISE_TEXT" and decision == "PASS":
        result["decision"] = "REVISE_TEXT"
        result["gate_route_to"] = "editor1_draft"
        if str(route_recommendation.get("reason") or ""):
            result["gate_reason"] = str(route_recommendation.get("reason") or "")
        return result
    if preferred_action == "REVIEW_RISK" and decision == "PASS":
        result["decision"] = "REVIEW_RISK"
        result["gate_route_to"] = "editor2_review"
        if str(route_recommendation.get("reason") or ""):
            result["gate_reason"] = str(route_recommendation.get("reason") or "")
        return result
    explicit_route_preference = preferred_action in {
        "ADD_EVIDENCE",
        "REVISE_TEXT",
        "REVIEW_RISK",
        "HUMAN_REVIEW",
    }
    # ── Phase 4: Simplified PASS when all obligations covered ──
    if all_obligations_covered and not has_hard_blockers and no_unsupported_claims:
        # ── Boost quality scores when evidence is sufficient ──
        qs = dict(result.get("quality_scores", {}))
        if qs.get("final_score", 0) < 0.7:
            qs["final_score"] = 0.7
        if qs.get("evidence_coverage", 0) < 0.5:
            qs["evidence_coverage"] = 0.5
        result["quality_scores"] = qs
        result["decision"] = "PASS"
        result["gate_route_to"] = "finalize_report"
        result["required_actions"] = []
        result["gate_reason"] = (
            "所有 obligation 已覆盖且无 blocker 或 unsupported claim — 通过"
        )
        return result

    if (
        decision in {"REVISE_TEXT", "HUMAN_REVIEW"}
        and not (
            preferred_action == "HUMAN_REVIEW" or preferred_route == "human_review"
        )
        and not explicit_route_preference
        and not low_diversity_risk
        and (all_policy_basis or has_audited_baseline_sources)
        and not has_hard_blockers
        and no_unsupported_claims
    ):
        result["decision"] = "PASS"
        result["gate_route_to"] = "finalize_report"
        result["required_actions"] = []
        result["gate_reason"] = (
            "Single-source official policy baseline claims can pass when no blocking evidence issue remains."
        )
    # ── Phase 4: Catch-all P0 context for HUMAN_REVIEW paths ──
    if result.get("decision") == "HUMAN_REVIEW" and not result.get("human_review"):
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
    # ── Phase 4: attach report_level on every gate path (incl. HUMAN_REVIEW) ──
    # finalize may be skipped on HUMAN_REVIEW, so grade here too: chief_gate is on
    # both PASS and HUMAN_REVIEW paths and reads evidence_gap_report from state.
    try:
        _graded = _claim_strength_guard(
            report_markdown="(gate-level grade)",
            gap_report=dict(state.get("evidence_gap_report") or {}),
            required_obligation_coverage=obligation_coverage,
        )
        if _graded:
            result["report_level"] = _graded.get("report_level")
            result["report_level_reason"] = _graded.get("reason", [])
    except Exception:
        pass
    return result


_REPORT_LEVEL_LABELS = {
    1: "线索报告",
    2: "初步研究报告",
    3: "深度研究报告",
    4: "投研决策报告",
}


def _claim_strength_guard(
    *,
    report_markdown: str,
    gap_report: dict[str, Any],
    required_obligation_coverage: list[dict[str, Any]] | None = None,
    human_review: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Phase 4: grade the report honestly from the evidence_gap_report and
    prepend a level banner + coverage-gap disclosure. An evidence-thin report
    (multiple insufficient_count sections) is capped at level_2 so it is not
    presented as a finished deep-research report.

    Returns {report_markdown, report_level, reason} or None when nothing to do.
    Default behavior is表述-level disclosure (report still emitted); it does NOT
    block finalize — that honest-degrade choice keeps a level_2 report usable
    rather than forcing HUMAN_REVIEW under Tavily recall limits (ADR 0001)."""
    if not report_markdown:
        return None
    gaps = gap_report.get("gaps", []) if isinstance(gap_report, dict) else []
    insufficient = [g for g in gaps if isinstance(g, dict)
                    and g.get("gap_kind") == "insufficient_count"]
    missing_only = [g for g in gaps if isinstance(g, dict)
                    and g.get("gap_kind") == "missing_fields"]
    spec_sections = int(gap_report.get("spec_sections", 0) or 0) if isinstance(gap_report, dict) else 0

    # Grade: many uncovered required sections => lower level.
    n_insuff = len(insufficient)
    reason: list[str] = []
    if spec_sections == 0:
        return None  # no spec to grade against; leave report unchanged
    report_form = _assess_draft_narrative_quality(report_markdown)
    form_passed = bool(report_form["passes_minimum_narrative_standard"])
    uncovered_obligations = [
        item
        for item in list(required_obligation_coverage or [])
        if isinstance(item, dict) and item.get("covered") is False
    ]
    review_status = str((human_review or {}).get("status") or "").casefold()
    unresolved_review = review_status in {"pending", "required", "human_review_required"}
    evidence_blockers = [
        item
        for item in list((human_review or {}).get("blocking_issues") or [])
        if isinstance(item, dict)
        and str(item.get("severity") or "").casefold() == "blocker"
        and str(item.get("issue_type") or "").casefold() != "human_review_required"
    ]
    if uncovered_obligations:
        level = 2
        obligation_ids = "、".join(
            str(item.get("obligation_id") or item.get("source_family") or "unknown")
            for item in uncovered_obligations
        )
        reason.append(f"强制证据义务尚未覆盖：{obligation_ids}")
    elif evidence_blockers:
        level = 2
        blocker_types = "、".join(
            sorted(
                {
                    str(item.get("issue_type") or "evidence_blocker")
                    for item in evidence_blockers
                }
            )
        )
        reason.append(f"仍存在阻断级证据问题：{blocker_types}")
    elif unresolved_review:
        level = 2
        reason.append("人工复核尚未完成，报告不能晋级为深度研究级别")
    elif n_insuff == 0 and not missing_only and form_passed:
        level = 3
        reason.append("所有报告维度均有充足证据支撑")
    elif n_insuff == 0 and form_passed:
        level = 3
        reason.append("各维度证据数充足，部分维度缺字段颗粒度（金额/主体/阶段）")
    elif n_insuff == 0:
        level = 2
        reason.append("report-form gate 未通过：正文缺少深度研究叙事或呈证据账本形态")
    elif n_insuff <= 1:
        level = 2
        reason.append(f"{n_insuff} 个维度证据不足（insufficient_count），核心结论需谨慎")
    else:
        level = 2
        reason.append(f"{n_insuff} 个维度证据缺失，报告维持初步研究级别，不宜作投研决策依据")

    label = _REPORT_LEVEL_LABELS.get(level, "初步研究报告")
    banner_lines = [
        f"> **报告等级：level_{level} · {label}**",
        ">",
    ]
    for r in reason:
        banner_lines.append(f"> - {r}")
    if insufficient:
        gap_secs = "、".join(
            str(g.get("section") or g.get("dimension_type") or "?")
            for g in insufficient
        )
        banner_lines.append(
            f"> - 证据不足维度（本轮证据池内未识别充足证据，不作判断）：{gap_secs}"
        )
    banner = "\n".join(banner_lines)
    graded_md = f"{banner}\n\n{report_markdown}"
    return {
        "report_markdown": graded_md,
        "report_level": f"level_{level}",
        "reason": reason,
        "report_form_gate": report_form,
        "uncovered_obligation_count": len(uncovered_obligations),
        "evidence_blocker_count": len(evidence_blockers),
        "human_review_unresolved": unresolved_review,
    }


def _build_evidence_quality_observability(state: dict[str, Any]) -> dict[str, Any]:
    evidence_items = [item for item in list(state.get("evidence", [])) if isinstance(item, dict)]
    support_rows = [
        item for item in list(state.get("claim_support_matrix", [])) if isinstance(item, dict)
    ]
    type_counts: dict[str, int] = {}
    proof_counts: dict[str, int] = {}
    ineligible: list[dict[str, Any]] = []
    for item in evidence_items:
        quality = item.get("evidence_quality_v2")
        if not isinstance(quality, dict):
            quality = {}
        evidence_type = str(item.get("evidence_type") or quality.get("evidence_type") or "unknown")
        proof_strength = str(
            item.get("proof_strength") or quality.get("proof_strength") or "unknown"
        )
        type_counts[evidence_type] = type_counts.get(evidence_type, 0) + 1
        proof_counts[proof_strength] = proof_counts.get(proof_strength, 0) + 1
        if proof_strength in {"context_only", "ineligible"} or not quality.get(
            "primary_support_eligible", True
        ):
            ineligible.append(
                {
                    "evidence_id": str(item.get("evidence_id") or ""),
                    "evidence_type": evidence_type,
                    "proof_strength": proof_strength,
                    "not_sufficient_for": list(quality.get("not_sufficient_for") or []),
                }
            )
    failed_decisions: list[dict[str, Any]] = []
    for row in support_rows:
        for decision in list(row.get("claim_support_eligibility") or []):
            if isinstance(decision, dict) and not decision.get("eligible"):
                failed_decisions.append(
                    {
                        "claim_id": str(decision.get("claim_id") or row.get("claim_id") or ""),
                        "evidence_id": str(decision.get("evidence_id") or ""),
                        "reason_code": str(decision.get("reason_code") or ""),
                        "required_source_family": str(
                            decision.get("required_source_family") or ""
                        ),
                        "actual_source_family": str(decision.get("actual_source_family") or ""),
                        "evidence_type": str(decision.get("evidence_type") or ""),
                        "proof_strength": str(decision.get("proof_strength") or ""),
                    }
                )
    return {
        "evidence_count": len(evidence_items),
        "evidence_type_counts": dict(sorted(type_counts.items())),
        "proof_strength_counts": dict(sorted(proof_counts.items())),
        "ineligible_evidence": ineligible[:20],
        "ineligible_evidence_count": len(ineligible),
        "eligibility_failure_count": len(failed_decisions),
        "eligibility_failures": failed_decisions[:20],
    }


def _render_evidence_quality_audit_markdown(summary: dict[str, Any]) -> str:
    if not summary:
        return ""
    lines = [
        "## Evidence Quality / Eligibility",
        "",
        f"- Evidence count: {summary.get('evidence_count', 0)}",
        f"- Ineligible evidence count: {summary.get('ineligible_evidence_count', 0)}",
        f"- Eligibility failure count: {summary.get('eligibility_failure_count', 0)}",
        f"- Evidence types: {summary.get('evidence_type_counts', {})}",
        f"- Proof strengths: {summary.get('proof_strength_counts', {})}",
    ]
    failures = list(summary.get("eligibility_failures") or [])
    if failures:
        lines.extend(["", "| Claim | Evidence | Reason | Required | Actual | Type | Strength |"])
        lines.append("|---|---|---|---|---|---|---|")
        for item in failures[:10]:
            lines.append(
                "| {claim_id} | {evidence_id} | {reason_code} | "
                "{required_source_family} | {actual_source_family} | "
                "{evidence_type} | {proof_strength} |".format(**item)
            )
    return "\n".join(lines).strip()


def finalize_report_provider_backed(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    _sync_impl_dependencies()
    result = _impl.finalize_report_provider_backed(state, tool_session=tool_session)

    # ── Phase 3 (remediation): Separate reader report from audit appendix ──
    # report_markdown is nested inside final_report dict
    final_report = dict(result.get("final_report", {}))
    if not final_report:
        final_report = dict(result)

    canonical = state.get("canonical_draft")
    if not isinstance(canonical, dict):
        canonical = _best_existing_draft(list(state.get("drafts", [])))
    canonical_guard: dict[str, Any] = {
        "retained_previous_draft": False,
        "canonical_draft_id": canonical.get("draft_id") if isinstance(canonical, dict) else None,
    }
    if isinstance(canonical, dict):
        canonical_body = str(canonical.get("report_markdown") or "")
        impl_body = str(final_report.get("report_markdown") or "")
        impl_audit = ""
        for marker in ("## Audit Appendix", "## 审计附录"):
            marker_index = impl_body.find(marker)
            if marker_index >= 0:
                impl_audit = impl_body[marker_index:].strip()
                impl_body = impl_body[:marker_index].strip()
                break
        canonical_quality = _assess_draft_narrative_quality(canonical_body)
        structured_body, structured_sections = _build_narrative_fallback_from_claims(
            query=str(state.get("query") or ""),
            claims=list(state.get("claims") or []),
            evidence_items=list(state.get("evidence") or []),
            sources=list(state.get("sources") or []),
        )
        structured_quality = _assess_draft_narrative_quality(structured_body)
        if (
            state.get("claims")
            and structured_quality["passes_minimum_narrative_standard"]
            and not canonical_quality["passes_minimum_narrative_standard"]
        ):
            canonical = {
                "draft_id": "finalizer_structured_fallback",
                "draft_version": canonical.get("draft_version"),
                "report_markdown": structured_body,
                "sections": structured_sections,
            }
            canonical_body = structured_body
            canonical_quality = structured_quality
            canonical_guard.update(
                {
                    "canonical_draft_id": "finalizer_structured_fallback",
                    "regenerated_from_claims": True,
                    "regeneration_reason": "structured_fallback_has_higher_narrative_quality",
                }
            )
        impl_quality = _assess_draft_narrative_quality(impl_body)
        should_retain = bool(
            canonical_quality["passes_minimum_narrative_standard"]
            and (
                not impl_quality["passes_minimum_narrative_standard"]
                or int(impl_quality["score"]) < int(canonical_quality["score"])
            )
        )
        if should_retain:
            final_report["report_markdown"] = canonical_body
            final_report["editor1_report_markdown"] = canonical_body
            if impl_audit:
                final_report["audit_markdown"] = impl_audit
            result["final_report"] = final_report
            canonical_guard.update(
                {
                    "retained_previous_draft": True,
                    "guard_triggered": True,
                    "used_draft_id": canonical.get("draft_id"),
                    "reason": "latest_or_impl_report_failed_canonical_quality_comparison",
                }
            )
    selected_body = str(final_report.get("report_markdown") or "")
    selected_quality = _assess_draft_narrative_quality(selected_body)
    if state.get("claims") and (
        int(selected_quality["duplicate_heading_count"]) > 0
        or int(selected_quality["generic_heading_count"]) > 1
    ):
        structured_body, structured_sections = _build_narrative_fallback_from_claims(
            query=str(state.get("query") or ""),
            claims=list(state.get("claims") or []),
            evidence_items=list(state.get("evidence") or []),
            sources=list(state.get("sources") or []),
        )
        structured_quality = _assess_draft_narrative_quality(structured_body)
        if structured_quality["passes_minimum_narrative_standard"]:
            final_report["report_markdown"] = structured_body
            final_report["editor1_report_markdown"] = structured_body
            final_report["narrative_sections"] = structured_sections
            result["final_report"] = final_report
            canonical_guard.update(
                {
                    "canonical_draft_id": "finalizer_structured_fallback",
                    "regenerated_from_claims": True,
                    "regeneration_reason": "selected_report_failed_narrative_v2",
                }
            )

    contract_meta = dict(result.get("contract_meta") or {})
    contract_meta["finalizer_canonical_guard"] = canonical_guard
    result["contract_meta"] = contract_meta
    rm = str(final_report.get("report_markdown", ""))
    if rm:
        audit_idx = len(rm)
        for marker in (
            "## Audit Appendix",
            "## 审计附录",
        ):
            idx = rm.find(marker)
            if idx >= 0 and idx < audit_idx:
                audit_idx = idx
        if audit_idx < len(rm):
            reader_body = rm[:audit_idx].strip()
            audit_body = rm[audit_idx:].strip()
            final_report["report_markdown"] = reader_body
            final_report["audit_markdown"] = audit_body
            result["final_report"] = final_report

    # ── Phase 4: claim_strength_guard + report level ──
    # Use the evidence_gap_report (carried in state) to honestly grade the report
    # (level_1..4) and prepend a level banner + coverage-gap disclosure, so an
    # evidence-thin report is not presented as a finished deep-research report.
    try:
        graded = _claim_strength_guard(
            report_markdown=str(final_report.get("report_markdown", "")),
            gap_report=dict(state.get("evidence_gap_report") or {}),
            required_obligation_coverage=list(
                state.get("required_obligation_coverage") or []
            ),
            human_review=(
                dict(state.get("human_review") or {})
                if isinstance(state.get("human_review"), dict)
                else None
            ),
        )
        if graded:
            final_report["report_markdown"] = graded.get(
                "report_markdown", final_report.get("report_markdown", "")
            )
            final_report["report_level"] = graded.get("report_level")
            final_report["report_level_reason"] = graded.get("reason", [])
            result["final_report"] = final_report
    except Exception as exc:
        contract_meta = dict(result.get("contract_meta") or {})
        contract_meta["report_level_guard_error"] = {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)[:500],
        }
        result["contract_meta"] = contract_meta

    evidence_quality_summary = _build_evidence_quality_observability(state)
    contract_meta = dict(result.get("contract_meta") or {})
    contract_meta["evidence_quality"] = evidence_quality_summary
    result["contract_meta"] = contract_meta
    audit_addendum = _render_evidence_quality_audit_markdown(evidence_quality_summary)
    if audit_addendum:
        existing_audit = str(final_report.get("audit_markdown") or "").strip()
        final_report["audit_markdown"] = (
            f"{existing_audit}\n\n{audit_addendum}".strip()
            if existing_audit
            else audit_addendum
        )
        result["final_report"] = final_report

    # B.3.3b: run-close of remaining SearchTasks is handled centrally by the
    # Runner's finalize_evaluation_run (covers ALL termination paths, including
    # HUMAN_REVIEW where finalize_report never runs). finalize_report must NOT be
    # the only run-close point.
    return result


# ── B.3.3b Advisory Gap Backfill node (shadow-only, flag-gated, fail-open) ───

_advisory_backfill_override: tuple[bool | None, str | None] | None = None
_advisory_search_executor_override: Any | None = None
_advisory_evidence_builder_override: Any | None = None


def set_advisory_backfill_override(*, enabled: bool | None = None, mode: str | None = None) -> None:
    """Test hook to override the ADVISORY_GAP_BACKFILL_ENABLED / _MODE flags."""
    global _advisory_backfill_override
    _advisory_backfill_override = (enabled, mode)


def set_advisory_backfill_components(search_executor: Any = None, evidence_builder: Any = None) -> None:
    """Test hook to inject fake executor/builder into the advisory node."""
    global _advisory_search_executor_override, _advisory_evidence_builder_override
    _advisory_search_executor_override = search_executor
    _advisory_evidence_builder_override = evidence_builder


def _advisory_backfill_flags() -> tuple[bool, str]:
    if _advisory_backfill_override is not None:
        enabled, mode = _advisory_backfill_override
        return bool(enabled), (mode or "shadow")
    from packages.core.config import get_settings

    s = get_settings()
    return bool(s.advisory_gap_backfill_enabled), str(s.advisory_gap_backfill_mode or "shadow")


def _advisory_search_executor() -> Any:
    if _advisory_search_executor_override is not None:
        return _advisory_search_executor_override
    from packages.research_harness.advisory_backfill_live import AnySearchBackfillExecutor

    return AnySearchBackfillExecutor()


def _advisory_evidence_builder() -> Any:
    if _advisory_evidence_builder_override is not None:
        return _advisory_evidence_builder_override
    from packages.research_harness.advisory_backfill_live import ContentPresenceEvidenceBuilder

    return ContentPresenceEvidenceBuilder()


def advisory_gap_backfill_provider_backed(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    """Shadow advisory backfill node (B.3.3b).

    Runs between build_claims and editor1_draft. Gated by
    ADVISORY_GAP_BACKFILL_ENABLED (default false). When enabled it clones the
    persisted RunEvaluationStore and runs run_advisory_backfill against the
    search provider + content-presence evidence builder, writing ONLY the
    `advisory_backfill` / `advisory_backfill_status` namespaces.

    It NEVER mutates state.sources / evidence / claims / documents /
    approved_claims / coverage_report / final_report, so Editor1 input is
    byte-for-byte unchanged. Fail-open: a provider/build error degrades the
    advisory output but never blocks Editor1 or the report.
    """
    enabled, mode = _advisory_backfill_flags()
    if not enabled or mode != "shadow":
        return {}
    store_data = state.get("evaluation_store")
    if not isinstance(store_data, dict):
        return {}
    try:
        from packages.research_harness.advisory_backfill import run_advisory_backfill
        from packages.research_harness.eval_persistence import (
            RunEvaluationStore,
            build_evaluable_coverage_report,
        )
        from packages.research_harness.gap_retrieval import derive_gaps, propose_search_actions

        original_store = RunEvaluationStore.from_dict(store_data)
        snapshot = build_evaluable_coverage_report(original_store)
        gaps, _ = derive_gaps(snapshot, original_store)
        base_query = str(state.get("query") or "")
        actions = propose_search_actions(
            gaps, original_store, base_query=base_query, max_per_slot=2,
        )
        result = run_advisory_backfill(
            store=original_store,
            current_snapshot=snapshot,
            research_gaps=gaps,
            proposed_actions=actions,
            search_executor=_advisory_search_executor(),
            evidence_builder=_advisory_evidence_builder(),
            base_query=base_query,
            max_rounds=2,
            max_actions_per_round=3,
            max_actions_per_slot=2,
            max_total_actions=6,
        )
        from dataclasses import asdict

        return {
            "advisory_backfill": {
                **result.to_dict(),
                # Shadow store (copy-on-write): backfill SearchTasks / SearchEvents
                # / Evidence live ONLY here, never in the main evaluation_store.
                "evaluation_store": result.final_store.to_dict(),
                "gaps": [asdict(g) for g in gaps],
                "actions": [asdict(a) for a in actions],
                "diagnostics": [],
            },
            "advisory_backfill_status": "completed",
        }
    except Exception as exc:  # noqa: BLE001 - fail-open, never blocks Editor1
        return {
            "advisory_backfill_status": "degraded",
            "advisory_backfill_diagnostics": [
                {"code": "ADVISORY_BACKFILL_FAILED", "message": str(exc)[:500]}
            ],
        }


# ── C.2 Structured Shadow Editor1 node (claim-constrained, shadow-only) ─────

_structured_shadow_override: tuple[bool | None, str | None] | None = None


def set_structured_shadow_override(*, enabled: bool | None = None, mode: str | None = None) -> None:
    """Test hook to override STRUCTURED_DRAFT_SHADOW_ENABLED / _MODE."""
    global _structured_shadow_override
    _structured_shadow_override = (enabled, mode)


def _structured_shadow_flags() -> tuple[bool, str]:
    if _structured_shadow_override is not None:
        enabled, mode = _structured_shadow_override
        return bool(enabled), (mode or "shadow")
    from packages.core.config import get_settings

    s = get_settings()
    return bool(s.structured_draft_shadow_enabled), str(
        s.structured_draft_shadow_mode or "shadow"
    )


def structured_shadow_editor1_provider_backed(
    state: dict[str, Any],
    *,
    tool_session: Any | None = None,
) -> dict[str, Any]:
    """C.2 claim-constrained StructuredDraft shadow node.

    Runs between advisory_gap_backfill and editor1_draft. Gated by
    STRUCTURED_DRAFT_SHADOW_ENABLED (default false). It reads ONLY the MAIN
    EvaluationStore and computes the MAIN CoverageReport from it — it MUST NOT
    read state.advisory_backfill.evaluation_store, so shadow backfill evidence
    never leaks into the writing input.

    Writes ONLY the `structured_draft_shadow` namespace (status / editor1_input /
    draft / validation_report / diagnostics / input_fingerprint). Never touches
    drafts / report_markdown / final_report / claims / evidence / coverage_report.
    Fail-open: a build error degrades the shadow but never blocks editor1_draft.
    """
    enabled, mode = _structured_shadow_flags()
    if not enabled or mode != "shadow":
        return {}
    store_data = state.get("evaluation_store")
    if not isinstance(store_data, dict):
        return {}
    try:
        from packages.research_harness.eval_persistence import (
            RunEvaluationStore,
            build_evaluable_coverage_report,
        )
        from packages.research_harness.structured_draft import (
            build_structured_shadow_draft,
            compile_editor1_input,
            draft_to_dict,
            editor_input_to_dict,
            input_fingerprint,
            validate_structured_draft,
        )

        store = RunEvaluationStore.from_dict(store_data)
        # MAIN coverage from the MAIN store (never the advisory shadow store).
        coverage_report = build_evaluable_coverage_report(store)
        research_gaps = [
            g for g in (state.get("research_gaps") or []) if isinstance(g, dict)
        ]
        editor_input = compile_editor1_input(
            store=store,
            coverage_report=coverage_report,
            research_gaps=research_gaps,
        )
        draft = build_structured_shadow_draft(
            editor_input,
            run_id=str(store.run_id or state.get("run_id") or ""),
        )
        validation = validate_structured_draft(
            draft,
            claim_cards=store.claim_cards,
            evidence_units=store.evidence_units,
            coverage_report=coverage_report,
        )
        return {
            "structured_draft_shadow": {
                "status": "completed",
                "editor1_input": editor_input_to_dict(editor_input),
                "draft": draft_to_dict(draft),
                "validation_report": validation.to_dict(),
                "diagnostics": [],
                "input_fingerprint": input_fingerprint(editor_input),
                "schema_version": "structured_draft_shadow_v1",
            }
        }
    except Exception as exc:  # noqa: BLE001 - fail-open, never blocks editor1
        return {
            "structured_draft_shadow": {
                "status": "degraded",
                "diagnostics": [
                    {"code": "STRUCTURED_DRAFT_SHADOW_FAILED", "message": str(exc)[:500]}
                ],
                "schema_version": "structured_draft_shadow_v1",
            }
        }


def set_search_provider_override(provider: Any | None) -> None:
    global _search_provider_override
    _search_provider_override = provider
    if hasattr(_impl, "set_search_provider_override"):
        _impl.set_search_provider_override(provider)


# ── Phase 3: Evidence/Claim semantic enrichment ──


def _inject_chunk_text_into_sources(
    *,
    state: dict[str, Any],
    source_chunks: list[dict[str, Any]],
    retrieval_pack: dict[str, Any],
) -> None:
    """Replace source raw_text with top-ranked retrieval chunks per source.

    Each source gets its top N chunks (by retrieval ranking) concatenated as
    raw_text. This makes the evidence builder see focused, relevant text
    instead of truncated full text (2400-char limit in bytecode).
    """
    # Build source_id → [chunks] from source_chunks
    source_chunk_map: dict[str, list[str]] = {}
    for chunk in source_chunks:
        if not isinstance(chunk, dict):
            continue
        sid = str(chunk.get("source_id") or "")
        text = str(chunk.get("text") or chunk.get("chunk_text") or "")
        if sid and text:
            source_chunk_map.setdefault(sid, []).append(text)

    if not source_chunk_map:
        return

    sources = list(state.get("sources", []))
    for i, source in enumerate(sources):
        sid = str(source.get("source_id", ""))
        chunks_for_source = source_chunk_map.get(sid, [])
        if not chunks_for_source:
            continue
        # 每个 source 都注入自己的 chunk（已按 reranker 精排序）；cap ~6000 字符
        # 覆盖该源全部 chunk，让原子抽取基于精排片段而非全文。
        selected: list[str] = []
        total_chars = 0
        max_chars = 6000
        for text in chunks_for_source:
            if total_chars + len(text) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 200:
                    selected.append(text[:remaining])
                break
            selected.append(text)
            total_chars += len(text)
        if selected:
            sources[i]["raw_text"] = "\n---\n".join(selected)
            sources[i]["_retrieval_chunks_used"] = len(selected)
            sources[i]["_retrieval_text_chars"] = sum(len(t) for t in selected)

    state["sources"] = sources


_ATOMIC_MIN_FULLTEXT_CHARS = 120
_ATOMIC_MAX_FACTS_PER_SOURCE = 5
_ATOMIC_MAX_TOTAL_FACTS = 40
# G4 提速：原子事实 LLM 抽取的并行线程数（每个 source 独立 LLM 调用，线程安全）。
_ATOMIC_EXTRACT_PARALLEL_WORKERS = 6
# 2026-08-10：evidence 按 claim slot 限量——每 slot 保留 top-K 条精排 chunk
# evidence（控制检索回的 evidence 总量：28 slots × K → 28-84 条）。
_EVIDENCE_TOP_K_PER_SLOT = 3
# evidence 从精排 chunk 抽：上限 8000 字符（容纳 2-3 块 1700 字符 chunk）。
_ATOMIC_MAX_FULLTEXT_CHARS = 8000


def _source_chunk_fulltext(
    source: dict[str, Any], state: dict[str, Any] | None = None
) -> str:
    """从精排 chunk 读取 source 文本（evidence 直接基于精排 chunk 构建）。

    `state["source_chunks"]` 是 reranker 精排后的 chunk（chunk_id↔source_id 保留）。
    按 source_id 取出该源全部精排 chunk 拼接，上限 _ATOMIC_MAX_FULLTEXT_CHARS。
    无 chunk（deep-backfill/ReAct 补证路径的新源未走 parse_sources）时回退 source.raw_text。
    """
    if state is not None:
        source_chunks = list(state.get("source_chunks", []))
        sid = str(source.get("source_id") or "")
        parts: list[str] = []
        total = 0
        for chunk in source_chunks:
            if not isinstance(chunk, dict):
                continue
            if str(chunk.get("source_id") or "") != sid:
                continue
            text = str(chunk.get("chunk_text") or chunk.get("text") or "")
            if not text:
                continue
            if total + len(text) > _ATOMIC_MAX_FULLTEXT_CHARS:
                remaining = _ATOMIC_MAX_FULLTEXT_CHARS - total
                if remaining > 200:
                    parts.append(text[:remaining])
                break
            parts.append(text)
            total += len(text)
        if parts:
            return "\n---\n".join(parts)
    # 兜底：无精排 chunk（deep-backfill 新源）→ 用 raw_text（定向内容）或全文。
    for key in ("raw_text", "content_text", "snippet"):
        val = str(source.get(key) or "")
        if len(val) >= _ATOMIC_MIN_FULLTEXT_CHARS:
            return val
    return str(source.get("full_text") or "")
    """Best available fulltext for a source, preferring the retrieval-chunk view.

    `_inject_chunk_text_into_sources` writes top retrieval chunks into `raw_text`
    (query-focused, ~5000 chars). Prefer it over `full_text` (entire page, can be
    64k chars) so atomic extraction consumes focused, relevant text instead of the
    whole page — smaller LLM input, lower cost, better signal.
    """
    for key in ("raw_text", "content_text", "snippet", "summary"):
        val = str(source.get(key) or "")
        if len(val) >= _ATOMIC_MIN_FULLTEXT_CHARS:
            return val
    # full_text only as fallback when no focused text exists (e.g. no chunks
    # retrieved for this source).
    val = str(source.get("full_text") or "")
    if len(val) >= _ATOMIC_MIN_FULLTEXT_CHARS:
        return val
    # fall back to the longest available text even if short
    candidates = [str(source.get(k) or "") for k in ("full_text", "raw_text", "snippet")]
    return max(candidates, key=len) if candidates else ""


def _source_dimension_key_fields(
    source: dict[str, Any],
    dimension_plan: list[dict[str, Any]] | None,
) -> list[str]:
    """Return the Chinese search_key_fields of the dimension that a source maps
    to (by source_family overlap). Deep-backfilled sources carry an explicit
    `_deep_dimension` dimension_id. Empty when no dimension matches."""
    dim_plan = list(dimension_plan or [])
    deep_dim_id = str(source.get("_deep_dimension") or "")
    if deep_dim_id:
        for dim in dim_plan:
            if isinstance(dim, dict) and str(dim.get("dimension_id") or "") == deep_dim_id:
                return list(dim.get("search_key_fields") or [])
    fam = str(source.get("source_family") or "")
    if not fam:
        return []
    for dim in dim_plan:
        if not isinstance(dim, dict):
            continue
        families = [str(f) for f in (dim.get("source_families") or []) if str(f).strip()]
        if fam in families:
            return list(dim.get("search_key_fields") or [])
    return []


def _build_chunk_evidence_from_state(
    *,
    query: str,
    sources: list[dict[str, Any]],
    base_evidence: list[dict[str, Any]],
    dimension_plan: list[dict[str, Any]] | None = None,
    state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """精排 chunk 直接作 evidence（不再 LLM 抽取原子事实）。

    用户核心指示：evidence = 检索词检索回来的精排 chunk 本身，editor1 → editor2
    直接消费。每个精排 chunk 转成一条 evidence（text=chunk 全文，evidence_id=
    chunk_id），带 source_id/source_family/source_uri/rerank_score。

    控制数量（2026-08-10）：只保留匹配到 required/critical claim slot 的 chunk，
    每 slot 按 rerank_score 限 top_k 条，evidence 带 supports_slot_ids。字节码
    base evidence 不再使用。deep-backfill 新源（无精排 chunk）回退 raw_text。
    """
    source_chunks = list((state or {}).get("source_chunks", []))
    src_by_id = {str(s.get("source_id") or ""): s for s in sources if isinstance(s, dict)}
    plan = dict((state or {}).get("plan") or {})
    contract = compile_research_contract(plan)
    # slot 索引：canonical source_family -> [slot_id, ...]
    slot_by_family: dict[str, list[str]] = {}
    slot_by_id: dict[str, dict[str, Any]] = {}
    for sec in contract.get("sections", []):
        for s in sec.get("claim_slots", []):
            if not isinstance(s, dict):
                continue
            fid = canonical_source_family(str(s.get("source_family") or ""))
            slot_by_family.setdefault(fid, []).append(str(s["slot_id"]))
            slot_by_id[str(s["slot_id"])] = s
    top_k = int((state or {}).get("evidence_top_k_per_slot") or _EVIDENCE_TOP_K_PER_SLOT)

    # 1) 精排 chunk 按 slot 匹配，每 slot 限量 top_k（按 rerank_score 降序）
    #    只保留 required/critical slot（optional 不进首轮，控制总量）。
    slot_to_chunks: dict[str, list[dict[str, Any]]] = {}
    for chunk in source_chunks:
        if not isinstance(chunk, dict):
            continue
        chunk_id = str(chunk.get("chunk_id") or chunk.get("id") or "")
        if not chunk_id:
            continue
        text = str(chunk.get("chunk_text") or "")
        if not text.strip():
            continue
        fam = canonical_source_family(
            str(chunk.get("source_family") or src_by_id.get(str(chunk.get("source_id") or ""), {}).get("source_family") or "")
        )
        if not fam:
            continue
        # 该 chunk 匹配的所有 required/critical slot
        matched_slots = [
            sid for sid in slot_by_family.get(fam, [])
            if str(slot_by_id.get(sid, {}).get("required") or "") in {"critical", "required"}
        ]
        if not matched_slots:
            continue
        score = float(chunk.get("rerank_score") or 0.0)
        for sid in matched_slots:
            slot_to_chunks.setdefault(sid, []).append({
                "chunk": chunk, "score": score, "matched_slots": matched_slots,
            })

    chunk_evidence: list[dict[str, Any]] = []
    seen_chunks: set[str] = set()
    for sid, entries in slot_to_chunks.items():
        entries.sort(key=lambda e: -e["score"])
        for entry in entries[:top_k]:
            chunk = entry["chunk"]
            chunk_id = str(chunk.get("chunk_id") or chunk.get("id") or "")
            if chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk_id)
            sid_src = str(chunk.get("source_id") or "")
            src = src_by_id.get(sid_src, {})
            chunk_evidence.append({
                "evidence_id": chunk_id,
                "source_id": sid_src,
                "source_url": str(chunk.get("source_uri") or src.get("url") or ""),
                "source_family": str(chunk.get("source_family") or src.get("source_family") or ""),
                "summary": _normalize_space(text := str(chunk.get("chunk_text") or "")),
                "text": text,
                "support_type": "direct_support" if float(chunk.get("rerank_score") or 0) >= 0.3 else "background_support",
                "support_strength": round(min(1.0, float(chunk.get("rerank_score") or 0.0)), 3),
                "specificity": "chunk",
                "limitations": [],
                "evaluator_mode": "chunk_evidence_v1",
                "chunk_ids": [chunk_id],
                "source_ids": [sid_src] if sid_src else [],
                "supports_slot_ids": entry["matched_slots"],
                "region": "",
                "time_ref": "",
                "policy_tool": [],
                "entity": "",
                "quoted_span": text[:150],
                "quote_verified": True,
                "content_completeness": "high",
                "rerank_score": chunk.get("rerank_score"),
                "rerank_bucket": chunk.get("rerank_bucket"),
                "document_title": str(chunk.get("document_title") or ""),
                "_chunk_evidence": True,
                "_slot_evidence": True,
            })
    # 2) 无精排 chunk 的新源（deep-backfill/ReAct 路径）：raw_text 构建一条
    existing_sids = {str(e.get("source_id") or "") for e in base_evidence if isinstance(e, dict)}
    for source in sources:
        if not isinstance(source, dict):
            continue
        sid = str(source.get("source_id") or "")
        if not sid or sid in {str(c.get("source_id") or "") for c in chunk_evidence}:
            continue
        if sid in existing_sids:
            continue
        raw = str(source.get("raw_text") or source.get("full_text") or "").strip()
        if len(raw) < _ATOMIC_MIN_FULLTEXT_CHARS:
            continue
        fam = canonical_source_family(str(source.get("source_family") or ""))
        matched_slots = [
            sid_s for sid_s in slot_by_family.get(fam, [])
            if str(slot_by_id.get(sid_s, {}).get("required") or "") in {"critical", "required"}
        ]
        if not matched_slots:
            continue
        chunk_evidence.append({
            "evidence_id": f"ev_raw_{sid}",
            "source_id": sid,
            "source_url": str(source.get("url") or ""),
            "source_family": str(source.get("source_family") or ""),
            "summary": _normalize_space(raw)[:400],
            "text": raw,
            "support_type": "background_support",
            "support_strength": 0.3,
            "specificity": "chunk",
            "limitations": [],
            "evaluator_mode": "chunk_evidence_raw_v1",
            "chunk_ids": [],
            "source_ids": [sid],
            "supports_slot_ids": matched_slots,
            "region": "",
            "time_ref": "",
            "policy_tool": [],
            "entity": "",
            "quoted_span": raw[:150],
            "quote_verified": True,
            "content_completeness": "medium",
            "_chunk_evidence": True,
            "_slot_evidence": True,
        })
    return chunk_evidence


def _llm_extract_atomic_facts(
    *,
    query: str,
    source: dict[str, Any],
    fulltext: str,
    dimension_plan: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """LLM path: extract typed atomic facts from one source's fulltext.

    Phase E1: reads up to _ATOMIC_MAX_FULLTEXT_CHARS of the source text (full
    chunk context, not a 3000-char cut), and tags each atomic fact with the
    dimension's search_key_fields it carries."""
    from packages.research_harness.tooling.llm_agents import call_tooling_json

    family = str(source.get("source_family") or "")
    dim_key_fields = _source_dimension_key_fields(source, dimension_plan)
    key_fields_hint = ""
    if dim_key_fields:
        key_fields_hint = (
            f"该来源对应研究维度的关键字段: {dim_key_fields}\n"
            f"每条事实必须标注 key_fields(该事实命中的关键字段子集, 从中选择, "
            f"如 ['代表企业','价值量'])。\n"
        )
    prompt = (
        f"研究问题: {query}\n"
        f"来源族: {family}\n"
        f"来源标题: {source.get('title', '')}\n"
        f"来源正文:\n{fulltext[:_ATOMIC_MAX_FULLTEXT_CHARS]}\n\n"
        f"从上述正文中抽取最多 {_ATOMIC_MAX_FACTS_PER_SOURCE} 条\"原子事实\"。"
        f"每条必须是正文里明确写出的、可独立核查的具体事实("
        f"量化目标/金额/补贴/时间节点/主管部门/应用场景/项目名称等),"
        f"不要泛泛复述标题。\n"
        f"{key_fields_hint}"
        f"每条字段: summary(中文具体事实,20-120字), support_type(direct_support|"
        f"primary_support|background_support), specificity(policy_statement|"
        f"implementation_rule|project_announcement|order_or_contract|"
        f"production_or_revenue|background), region(地区,无则空串), "
        f"time_ref(时间,无则空串), policy_tool(手段列表,如补贴/基金/示范区/基础设施), "
        f"entity(主体,无则空串), "
        f"stage(项目阶段, 仅项目类填: 规划|招标|中标|开工|试运行|常态运营, 无则空串), "
        f"amount(金额/规模数字+单位, 如'10亿元'/'500架次', 无则空串), "
        f"quoted_span(该条事实在原文中的逐字引用片段, 50-150字, 必须能从正文中"
        f"原样找到, 不可改写), "
        f"content_completeness(high|medium|low), "
        f"key_fields(命中的维度关键字段列表, 无维度字段时为空数组)。\n"
        f"只输出 JSON 对象: {{\"facts\": [{{...}}]}}"
    )
    try:
        res = call_tooling_json(
            system_prompt="你是产业研究分析师,从政策/项目/披露正文中抽取可核查的原子事实。",
            user_prompt=prompt,
            enable_thinking=False,
            trace_ctx=_get_trace_ctx(),
        )
    except Exception:
        return []
    payload = res.payload if res else None
    if not isinstance(payload, dict):
        return []
    raw_facts = payload.get("facts")
    if not isinstance(raw_facts, list):
        return []
    facts: list[dict[str, Any]] = []
    for idx, rf in enumerate(raw_facts[:_ATOMIC_MAX_FACTS_PER_SOURCE]):
        if not isinstance(rf, dict):
            continue
        summary = _normalize_space(str(rf.get("summary", "")))
        if len(summary) < 8:
            continue
        facts.append(_make_atomic_evidence_item(
            source=source, idx=idx, summary=summary,
            support_type=str(rf.get("support_type", "background_support")),
            specificity=str(rf.get("specificity", "background")),
            region=str(rf.get("region", "")),
            time_ref=str(rf.get("time_ref", "")),
            policy_tool=rf.get("policy_tool", []),
            entity=str(rf.get("entity", "")),
            stage=str(rf.get("stage", "")),
            amount=str(rf.get("amount", "")),
            quoted_span=str(rf.get("quoted_span", "")),
            content_completeness=str(rf.get("content_completeness", "medium")),
            key_fields=[str(k) for k in (rf.get("key_fields") or []) if str(k).strip()],
            extractor="llm_atomic_v1",
        ))
    return facts


_ATOMIC_SIGNAL_RE = re.compile(
    r"\d|亿|万元|补贴|基金|示范区|机场|目标|到20|出台|实施|场景|项目|招标|"
    r"中标|公告|年报|披露|建成|投产|订单|产能"
)
_POLICY_TOOL_MARKERS = {
    "补贴": "补贴", "基金": "产业基金", "示范区": "示范区", "机场": "基础设施",
    "基础设施": "基础设施", "招标": "招标采购", "采购": "招标采购",
}


def _match_dim_key_fields(sent: str, dim_key_fields: list[str]) -> list[str]:
    """Roughly tag which dimension key fields a sentence carries (substring or
    _SEARCH_FIELD_TERMS token hit). Used by the deterministic extractor."""
    from packages.research_harness.plan_semantic import _SEARCH_FIELD_TERMS

    hit: list[str] = []
    for field in dim_key_fields:
        if field in sent:
            hit.append(field)
            continue
        term = _SEARCH_FIELD_TERMS.get(field) or ""
        if term and any(tok in sent for tok in term.split()):
            hit.append(field)
    return hit


def _deterministic_atomic_facts(
    *,
    source: dict[str, Any],
    fulltext: str,
    dimension_plan: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """No-provider fallback: split fulltext on sentence boundaries and keep
    sentences that carry concrete signals (numbers, money, tools, milestones)."""
    sentences = re.split(r"[。;；\n]", fulltext)
    dim_key_fields = _source_dimension_key_fields(source, dimension_plan)
    facts: list[dict[str, Any]] = []
    for idx, raw in enumerate(sentences):
        sent = _normalize_space(raw)
        if len(sent) < 12 or not _ATOMIC_SIGNAL_RE.search(sent):
            continue
        tools = sorted({
            label for marker, label in _POLICY_TOOL_MARKERS.items() if marker in sent
        })
        has_number = bool(re.search(r"\d", sent))
        facts.append(_make_atomic_evidence_item(
            source=source, idx=idx, summary=sent[:120],
            support_type="primary_support" if has_number else "background_support",
            specificity="implementation_rule" if tools else "background",
            region="", time_ref="",
            policy_tool=tools, entity="",
            quoted_span=sent[:150],
            content_completeness="medium" if has_number else "low",
            key_fields=_match_dim_key_fields(sent, dim_key_fields),
            extractor="deterministic_atomic_v1",
        ))
        if len(facts) >= _ATOMIC_MAX_FACTS_PER_SOURCE:
            break
    return facts


def _normalize_quote_text(s: str) -> str:
    """NFKC + whitespace/full-width punctuation normalization for quote matching."""
    import unicodedata
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = s.replace(" ", "").replace("\u3000", "")
    return s.replace("，", ",").replace("。", ".").replace("：", ":").replace("；", ";")


def _source_texts(source: dict[str, Any]) -> list[str]:
    return [
        str(source.get("full_text", "") or ""),
        str(source.get("raw_text", "") or ""),
        str(source.get("content_text", "") or ""),
    ]


def _quote_in_source(quoted_span: str, source: dict[str, Any]) -> bool:
    """Deterministic check that a quoted_span actually appears in the source text.

    Phase A: quoted_span is only trusted when it is a verbatim substring of the
    source's raw/full text (after whitespace/punctuation normalization). This
    prevents the extractor from emitting a span that never existed in the source.
    """
    if not quoted_span:
        return False
    haystack = " ".join(_source_texts(source))
    if not haystack:
        return False
    nq = _normalize_quote_text(quoted_span)
    nh = _normalize_quote_text(haystack)
    return bool(nq) and (nq in nh)


def _locate_quote_in_source(quoted_span: str, source: dict[str, Any]) -> dict[str, Any]:
    """Best-effort raw-offset location of quoted_span in the source text.

    Returns {"quote_start", "quote_end", "quote_occurrence", "offset_mode"}:
    - raw: exact substring found in the source's raw text (raw offsets).
    - normalized: NFKC-normalized offsets (the raw index may differ after
      normalization; occurrence is still reported for disambiguation).
    - none: not located.
    """
    if not quoted_span:
        return {"quote_start": -1, "quote_end": -1, "quote_occurrence": 0, "offset_mode": "none"}
    for text in _source_texts(source):
        if not text:
            continue
        idx = text.find(quoted_span)
        if idx >= 0:
            occurrence = text[:idx].count(quoted_span) + 1
            return {
                "quote_start": idx,
                "quote_end": idx + len(quoted_span),
                "quote_occurrence": occurrence,
                "offset_mode": "raw",
            }
    nq = _normalize_quote_text(quoted_span)
    for text in _source_texts(source):
        if not text or not nq:
            continue
        norm_text = _normalize_quote_text(text)
        idx = norm_text.find(nq)
        if idx >= 0:
            occurrence = norm_text[:idx].count(nq) + 1
            return {
                "quote_start": idx,
                "quote_end": idx + len(nq),
                "quote_occurrence": occurrence,
                "offset_mode": "normalized",
            }
    return {"quote_start": -1, "quote_end": -1, "quote_occurrence": 0, "offset_mode": "none"}


def _make_atomic_evidence_item(
    *,
    source: dict[str, Any],
    idx: int,
    summary: str,
    support_type: str,
    specificity: str,
    region: str,
    time_ref: str,
    policy_tool: Any,
    entity: str,
    content_completeness: str,
    extractor: str,
    stage: str = "",
    amount: str = "",
    quoted_span: str = "",
    key_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Build an atomic evidence item that matches the base evidence shape plus
    Phase 7 typed fields. needs_fulltext_check is derived, not trusted from LLM.
    Phase 3 adds stage (project lifecycle) + amount (quantitative) for the
    project-execution field granularity the gap self-check looks for.
    Phase A adds quoted_span: the exact source-text span supporting this fact
    (separate from the model-summarized `summary`). quote_verified is a
    deterministic substring check against the source text, not LLM-trusted.
    Phase E1 adds key_fields: which of the dimension's search_key_fields this
    atomic fact carries (e.g. industry_chain -> ['代表企业','价值量'])."""
    sid = str(source.get("source_id") or "")
    tools = [str(t) for t in policy_tool] if isinstance(policy_tool, list) else (
        [str(policy_tool)] if policy_tool else []
    )
    valid_support = {"direct_support", "primary_support", "background_support"}
    if support_type not in valid_support:
        support_type = "background_support"
    return {
        "evidence_id": f"ev_atomic_{sid}_{idx}",
        "source_id": sid,
        "source_url": str(source.get("url") or source.get("source_url") or ""),
        "summary": summary,
        "support_type": support_type,
        "support_strength": 0.0,  # filled by _enrich_evidence_semantics
        "specificity": specificity,
        "limitations": [],
        "evaluator_mode": extractor,
        "chunk_ids": [],
        "source_ids": [sid],
        "region": region,
        "time_ref": time_ref,
        "policy_tool": tools,
        "entity": entity,
        "stage": stage,
        "amount": amount,
        "quoted_span": quoted_span,
        "quote_verified": _quote_in_source(quoted_span, source),
        "quote_loc": _locate_quote_in_source(quoted_span, source),
        "content_completeness": content_completeness,
        "needs_fulltext_check": content_completeness == "low",
        "key_fields": list(key_fields or []),
        "_atomic": True,
    }


def _region_match_for_text(*, query: str, text: str, domain: str = "") -> str:
    """Content-based region match for relevance up-weighting (ADR 0001 lesson).

    Returns the local-region match_type ("exact_local" / "child_local" /
    "parent_local" / "unrelated_region" / "unknown") by running the existing
    classify_local_region_match over the source title+summary text — NOT the
    domain, because real local sources often live on non-local-looking hosts
    (ichuanghui.org, ahchanye.com, mirrored gov sites). Returns "unknown" when
    the query has no resolvable location or the KB is unavailable."""
    location = _first_location_value(query=query, query_requirements={})
    if not location:
        return "unknown"
    try:
        from packages.sources.local_source_patterns import classify_local_region_match
        payload = classify_local_region_match(
            [location], str(text or ""), candidate_domain=domain or None,
        )
    except Exception:
        return "unknown"
    if isinstance(payload, dict):
        return str(payload.get("match_type") or "unknown")
    return "unknown"


def _evidence_gap_selfcheck(
    *,
    plan: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Goal-Driven Evidence ReAct (Phase 2): compare gathered evidence against
    the evidence_requirement_spec derived from the plan, and report which report
    sections are under-covered (count below min_evidence) or missing key fields.

    Returns {} when no plan/spec is available (graceful degrade). The report is
    diagnostic metadata; a future bounded re-extraction loop consumes it."""
    if not plan:
        return {}
    try:
        from packages.research_harness.plan_semantic import (
            build_evidence_requirement_spec,
        )
        spec = build_evidence_requirement_spec(plan)
    except Exception:
        return {}
    if not spec:
        return {}

    from packages.sources.local_source_patterns import canonical_source_family

    # evidence items carry source_id (not source_family); map via the source obj.
    src_family_by_id: dict[str, str] = {}
    for src in (sources or []):
        if isinstance(src, dict) and src.get("source_id"):
            src_family_by_id[str(src["source_id"])] = canonical_source_family(
                src.get("source_family")
            )

    fam_counts: dict[str, int] = {}
    present_fields: set[str] = set()
    for ev in evidence_items:
        if not isinstance(ev, dict):
            continue
        # resolve family from the evidence's source_id(s) via the source map;
        # fall back to an inline source_family if one is ever present.
        ev_fams: set[str] = set()
        for sid in ([ev.get("source_id")] + list(ev.get("source_ids", []))):
            if sid and str(sid) in src_family_by_id:
                ev_fams.add(src_family_by_id[str(sid)])
        if not ev_fams and ev.get("source_family"):
            ev_fams.add(canonical_source_family(ev.get("source_family")))
        for fam in ev_fams:
            fam_counts[fam] = fam_counts.get(fam, 0) + 1
        for fld in ("region", "time_ref", "policy_tool", "amount", "stage",
                    "company", "metric", "subject", "project_name"):
            if ev.get(fld):
                present_fields.add(fld)

    gaps: list[dict[str, Any]] = []
    for entry in spec:
        families = [
            canonical_source_family(f)
            for f in entry.get("required_source_families", [])
        ]
        covered = sum(fam_counts.get(f, 0) for f in families)
        min_ev = int(entry.get("min_evidence", 2))
        missing_fields = [
            f for f in entry.get("key_fields", []) if f not in present_fields
        ]
        if covered < min_ev or missing_fields:
            gaps.append({
                "section": entry.get("section"),
                "dimension_type": entry.get("dimension_type"),
                "required_source_families": entry.get("required_source_families"),
                "covered_evidence": covered,
                "min_evidence": min_ev,
                "missing_key_fields": missing_fields,
                "gap_kind": (
                    "insufficient_count" if covered < min_ev else "missing_fields"
                ),
            })
    return {
        "spec_sections": len(spec),
        "gap_sections": len(gaps),
        "gaps": gaps,
    }


_EVIDENCE_REACT_MAX_ROUNDS = 2
_EVIDENCE_REACT_PER_QUERY = 6

# ── Phase E1: dimension-driven deep backfill ──
# For each research dimension with search_key_fields, run 10-20 field-targeted
# searches and append the returned pages as sources, so the atomic extractor sees
# rich per-dimension material instead of only the top-12-chunk view from
# collect_sources. New sources are tagged `_deep_backfilled`.
_EVIDENCE_DEEP_MAX_PHRASES_PER_DIM = 12
_EVIDENCE_DEEP_MAX_DIMS = 10
_EVIDENCE_DEEP_MAX_SOURCES = 40
# G4 提速：深补搜并行搜索的线程数（每个任务各自建 provider，线程安全）。
_EVIDENCE_DEEP_PARALLEL_WORKERS = 6
# Atomic extractor reads up to this many chars of a source's fulltext (was 3000,
# which dropped the chunked context). Bumped to pair with the 5000-8000 max_tokens.
_ATOMIC_MAX_FULLTEXT_CHARS = 6000


def _build_dim_deep_phrases(
    *, dim: dict[str, Any], topic: str, location: str
) -> list[str]:
    """Build 10-20 field-targeted search phrases for a research dimension from
    its Chinese search_key_fields (e.g. industry_chain -> '代表企业 龙头企业')."""
    from packages.research_harness.plan_semantic import _SEARCH_FIELD_TERMS

    skf = list(dim.get("search_key_fields") or [])
    loc = f"{location} " if location else ""
    phrases: list[str] = []
    for field in skf:
        term = _SEARCH_FIELD_TERMS.get(field) or field
        base = _normalize_space(f"{loc}{topic} {term}")[:120]
        if base and base not in phrases:
            phrases.append(base)
        if len(phrases) >= _EVIDENCE_DEEP_MAX_PHRASES_PER_DIM:
            break
        variant = _normalize_space(f"{loc}{topic} {term} 最新")[:120]
        if variant and variant not in phrases:
            phrases.append(variant)
        if len(phrases) >= _EVIDENCE_DEEP_MAX_PHRASES_PER_DIM:
            break
    return phrases[:_EVIDENCE_DEEP_MAX_PHRASES_PER_DIM]


def _evidence_deep_backfill(
    *,
    state: dict[str, Any],
    dimension_plan: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deep backfill (Phase E1): for each research dimension that carries
    search_key_fields, generate 10-20 field-targeted search phrases, run real
    searches, and append new sources so the atomic extractor has rich per-dimension
    material. New sources are tagged `_deep_backfilled` and appended to
    state['sources'] so the subsequent atomic extraction covers them."""
    provider_factory = getattr(_impl, "_search_provider", None)
    search_with_retry = getattr(_impl, "_search_with_retry", None)
    request_cls = getattr(_impl, "TavilySearchRequest", None)
    if not (callable(provider_factory) and callable(search_with_retry) and request_cls is not None):
        return {"phrases": [], "added_sources": 0, "dims": []}

    query = str(state.get("query", ""))
    location = str((state.get("query_requirements") or {}).get("target_location") or "").strip()
    topic = _gap_core_topic(query, location)
    sources = list(state.get("sources", []))
    existing_urls = {
        str(s.get("url") or s.get("source_url") or "")
        for s in sources if isinstance(s, dict)
    }
    meta: dict[str, Any] = {"phrases": [], "added_sources": 0, "dims": []}
    new_sources: list[dict[str, Any]] = []
    # G4 提速：并行化深补搜。先收集所有 (phrase, dim) 任务，再用 ThreadPoolExecutor
    # 并发搜索（每任务各自建 provider，线程安全），把 10 维度 × 12 短语的串行
    # 搜索缩到 ~4-6 并发批次。
    _search_plan: list[tuple[str, dict[str, Any]]] = []
    for dim in list(dimension_plan or [])[:_EVIDENCE_DEEP_MAX_DIMS]:
        if not isinstance(dim, dict):
            continue
        if not dim.get("search_key_fields"):
            continue
        phrases = _build_dim_deep_phrases(dim=dim, topic=topic, location=location)
        if not phrases:
            continue
        for phrase in phrases:
            _search_plan.append((phrase, dim))
        meta["phrases"].extend(phrases)
        meta["dims"].append({
            "dimension_id": dim.get("dimension_id"),
            "dimension_type": dim.get("dimension_type"),
            "phrases": phrases,
        })
    if not _search_plan:
        meta["added_sources"] = 0
        return meta

    def _search_one(task: tuple[str, dict[str, Any]]) -> list[dict[str, Any]]:
        phrase, dim = task
        hits: list[dict[str, Any]] = []
        try:
            _prov = provider_factory()
            req = request_cls(
                query=phrase, include_domains=[], max_results=4,
                include_raw_content=True, search_depth="advanced",
            )
            resp, _ = search_with_retry(_prov, req)
            if isinstance(resp, tuple):
                resp = resp[0] if resp else None
            if resp is None:
                return hits
            families = dim.get("source_families") or []
            family = str(families[0]) if families else "industry_research"
            for hit in (getattr(resp, "results", None) or []):
                url = str(getattr(hit, "url", "") or "")
                raw = str(getattr(hit, "raw_content", "") or getattr(hit, "content", "") or "")
                if not url or len(raw) < _ATOMIC_MIN_FULLTEXT_CHARS:
                    continue
                hits.append({
                    "url": url,
                    "title": str(getattr(hit, "title", "") or ""),
                    "source_family": family,
                    "raw_text": raw[:_ATOMIC_MAX_FULLTEXT_CHARS],
                    "full_text": raw,
                    "snippet": str(getattr(hit, "content", "") or "")[:200],
                    "source_tier": "B",
                    "_deep_backfilled": True,
                    "_deep_dimension": dim.get("dimension_id"),
                })
        except Exception:
            pass
        return hits

    from concurrent.futures import ThreadPoolExecutor

    # 并发搜索（限 6 线程），收集去重；_EVIDENCE_DEEP_MAX_SOURCES 限制新增源数。
    with ThreadPoolExecutor(max_workers=_EVIDENCE_DEEP_PARALLEL_WORKERS) as pool:
        _results = list(pool.map(_search_one, _search_plan))
    for hits in _results:
        if len(new_sources) >= _EVIDENCE_DEEP_MAX_SOURCES:
            break
        for hit in hits:
            if len(new_sources) >= _EVIDENCE_DEEP_MAX_SOURCES:
                break
            url = hit["url"]
            if url in existing_urls:
                continue
            existing_urls.add(url)
            hit["source_id"] = f"src_deep_{len(sources) + len(new_sources) + 1}"
            new_sources.append(hit)
    if new_sources:
        state["sources"] = [*sources, *new_sources]
    meta["added_sources"] = len(new_sources)
    return meta


def _evidence_react_backfill(
    *,
    state: dict[str, Any],
    result: dict[str, Any],
    gap_report: dict[str, Any],
    tool_session: Any = None,
) -> dict[str, Any] | None:
    """Goal-Driven Evidence ReAct (Phase 2 second half): for each
    insufficient_count gap family, run a family-targeted second-pass search
    (reusing collect's provider), turn new hits into evidence, append, and
    re-check. Bounded by _EVIDENCE_REACT_MAX_ROUNDS. Returns updated
    {evidence, evidence_gap_report, meta} or None when nothing was done.

    Only insufficient_count (0/min) gaps trigger re-extraction; missing_fields
    gaps are field-granularity issues handled by Phase 3 (stage/quant). When the
    provider is unavailable or returns nothing, the gap honestly remains."""
    search_provider_factory = getattr(_impl, "_search_provider", None)
    search_with_retry = getattr(_impl, "_search_with_retry", None)
    tavily_request_cls = getattr(_impl, "TavilySearchRequest", None)
    if not (callable(search_provider_factory) and callable(search_with_retry)
            and tavily_request_cls is not None):
        return None

    query = str(state.get("query", ""))
    location = str((state.get("query_requirements") or {}).get("target_location") or "").strip()
    base_topic = _gap_core_topic(query, location)
    sources = list(state.get("sources", []))
    evidence = list(result.get("evidence", []))
    existing_urls = {
        str(s.get("url") or s.get("source_url") or "")
        for s in sources if isinstance(s, dict)
    }

    rounds_done = 0
    families_tried: set[str] = set()
    meta: dict[str, Any] = {"rounds": 0, "queries": [], "added_sources": 0, "added_evidence": 0}

    current_gap = gap_report
    while rounds_done < _EVIDENCE_REACT_MAX_ROUNDS:
        insufficient = [
            g for g in current_gap.get("gaps", [])
            if g.get("gap_kind") == "insufficient_count"
        ]
        # only families not yet tried this call
        targets = []
        for g in insufficient:
            for fam in (g.get("required_source_families") or []):
                if fam not in families_tried:
                    targets.append((fam, g))
                    break
        if not targets:
            break

        new_sources: list[dict[str, Any]] = []
        for fam, _g in targets:
            families_tried.add(fam)
            tmpl = _GAP_FAMILY_TEMPLATES.get(fam, {})
            suffix = (tmpl.get("suffixes") or ["相关 公告"])[0]
            loc = f"{location} " if location else ""
            phrase = _normalize_space(f"{loc}{base_topic} {suffix}")[:120]
            meta["queries"].append(phrase)
            try:
                provider = search_provider_factory()
                request = tavily_request_cls(
                    query=str(phrase),
                    include_domains=[],
                    max_results=_EVIDENCE_REACT_PER_QUERY,
                    include_raw_content=True,
                    search_depth="advanced",
                )
                response = search_with_retry(provider, request)
            except Exception:
                continue
            # _search_with_retry returns (response, meta) — unpack the tuple.
            if isinstance(response, tuple):
                response = response[0] if response else None
            if response is None:
                continue
            for hit in (getattr(response, "results", None) or []):
                url = str(getattr(hit, "url", "") or "")
                if not url or url in existing_urls:
                    continue
                existing_urls.add(url)
                new_sources.append({
                    "source_id": f"src_react_{len(sources) + len(new_sources) + 1}",
                    "url": url,
                    "title": str(getattr(hit, "title", "") or ""),
                    "raw_text": str(getattr(hit, "raw_content", "") or getattr(hit, "content", "") or ""),
                    "snippet": str(getattr(hit, "content", "") or ""),
                    "source_family": fam,
                    "_react_backfilled": True,
                })

        if not new_sources:
            break

        sources.extend(new_sources)
        meta["added_sources"] += len(new_sources)
        # 精排 chunk 直接作 evidence（deep-backfill 新源无 chunk 时走 raw_text 兜底）
        chunk_ev = _build_chunk_evidence_from_state(
            query=query, sources=new_sources, base_evidence=evidence, state=state,
        )
        if chunk_ev:
            enriched = _enrich_evidence_semantics(
                evidence_items=chunk_ev, sources=new_sources, query=query,
            )
            evidence.extend(enriched)
            meta["added_evidence"] += len(enriched)

        rounds_done += 1
        meta["rounds"] = rounds_done
        # re-check gaps with the enlarged evidence + sources
        current_gap = _evidence_gap_selfcheck(
            plan=dict(state.get("plan") or {}),
            evidence_items=evidence,
            sources=sources,
        )

    if meta["added_evidence"] == 0 and meta["added_sources"] == 0:
        return None
    # persist enlarged sources back to state so downstream (claim/editor) sees them
    state["sources"] = sources
    return {
        "evidence": evidence,
        "evidence_gap_report": current_gap,
        "meta": meta,
    }


def _evidence_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _infer_evidence_type_for_graph(
    *,
    item: dict[str, Any],
    source: dict[str, Any],
    summary: str,
) -> str:
    # Canonicalize so legacy/raw family strings fold to the new 16-value set.
    source_family = canonical_source_family(source.get("source_family"))
    specificity = str(item.get("specificity") or "")
    support_type = str(item.get("support_type") or "")
    source_quality = source.get("source_quality_v2")
    source_role = ""
    if isinstance(source_quality, dict):
        source_role = str(source_quality.get("source_role") or "")
    text = f"{summary} {source.get('title', '')}"

    if source_family == "policy_document":
        if source_role == "official_news_or_interpretation":
            return "policy_signal"
        if specificity in {"implementation_rule", "implementation_plan"}:
            return "implementation_plan"
        if specificity in {"policy_statement", "formal_notice"}:
            return "policy_original"
        return "policy_original" if support_type == "direct_support" else "policy_signal"
    if source_family == "local_official":
        return "policy_signal"
    if source_family == "tender_procurement":
        if any(token in text for token in ("中标", "成交", "采购结果", "招标公告")):
            return "procurement_award"
        return "project_approval"
    if source_family == "official_statistics":
        return "statistics_metric"
    if source_family in {"exchange_disclosure", "company_disclosure"}:
        if any(token in text for token in ("年报", "公告", "披露", "投资者关系")):
            return "company_disclosure_statement"
        return "ir_disclosure"
    if source_family == "environmental_land":
        return "project_approval"
    if source_family in {"industry_research", "association_thinktank", "broker_research"}:
        return "industry_metric"
    if source_family == "media_context":
        return "media_context"
    return "background_context"


def _proof_strength_from_support(
    *,
    support_strength: float,
    usage_role: str,
    evidence_type: str,
) -> str:
    """G4 精简：proof_strength 只由 support_strength（已折入 tier/意图/region）+
    usage_role + evidence_type 判定。原 quality_score 无独立消费，移除。
    原 citation_integrity<0.45 门为死门（恒 ≥0.85），移除。"""
    if usage_role in {"context_only", "exclude_from_primary_evidence"}:
        return "context_only"
    if evidence_type in {"background_context", "media_context"}:
        return "context_only"
    if support_strength >= 0.75:
        return "strong"
    if support_strength >= 0.55:
        return "medium"
    if support_strength >= 0.35:
        return "weak"
    return "ineligible"


def _build_evidence_quality_v2_for_graph(
    *,
    item: dict[str, Any],
    source: dict[str, Any],
    summary: str,
    support_strength: float,
) -> dict[str, Any]:
    """G4 精简：evidence 质量只保留真出口字段。

    移除：quality_score / claim_relevance / evidence_specificity / citation_integrity /
    primary_support_eligible —— 均无独立消费（claim 匹配只用 proof_strength/evidence_type，
    support_strength 才是被 editor/report/gate 广泛消费的字段）。
    """
    source_quality = source.get("source_quality_v2")
    if not isinstance(source_quality, dict):
        source_quality = {}
    evidence_type = _infer_evidence_type_for_graph(
        item=item,
        source=source,
        summary=summary,
    )
    source_credibility_score = _evidence_float(
        source_quality.get("credibility_score", source.get("source_credibility_score")),
        0.0,
    )
    usage_role = str(source_quality.get("usage_role") or source.get("source_usage_role") or "")
    proof_strength = _proof_strength_from_support(
        support_strength=support_strength,
        usage_role=usage_role,
        evidence_type=evidence_type,
    )
    not_sufficient_for = list(source_quality.get("not_sufficient_for") or [])
    if proof_strength in {"context_only", "ineligible"}:
        not_sufficient_for.append("primary_claim_support")
    if evidence_type == "policy_signal":
        not_sufficient_for.append("formal_policy_original_requirement")
    not_sufficient_for = sorted(set(str(item) for item in not_sufficient_for if item))
    return {
        "evidence_type": evidence_type,
        "proof_strength": proof_strength,
        "inherited_source_quality": {
            "source_family": str(source.get("source_family") or ""),
            "source_tier": str(source_quality.get("tier") or source.get("source_tier") or "C"),
            "source_role": str(source_quality.get("source_role") or ""),
            "source_credibility_score": source_credibility_score,
            "source_usage_role": usage_role,
        },
        "not_sufficient_for": not_sufficient_for,
    }


def _required_evidence_count(requirement: str) -> int:
    """从 support_requirement（如 '至少2条地方政策证据' / '至少1条官方政策证据'）解析
    要求的证据条数。默认 1（至少一条）。"""
    text = str(requirement or "")
    for token in ("至少", "at least"):
        if token in text:
            import re as _re

            m = _re.search(r"(\d+)", text)
            if m:
                return int(m.group(1))
    return 1


def _claim_required_evidence_types(claim: dict[str, Any]) -> set[str]:
    requirement = str(claim.get("support_requirement") or claim.get("claim_family") or "")
    required_family = str(claim.get("required_source_family") or "")
    if "statistics" in requirement or "statistics" in required_family:
        return {"statistics_metric", "official_data_release", "industry_metric"}
    if (
        "company" in requirement
        or "disclosure" in requirement
        or required_family in {"company_disclosure", "exchange_disclosure"}
    ):
        return {"company_disclosure_statement", "annual_report_statement", "announcement", "ir_disclosure"}
    if "procurement" in requirement or "award" in requirement or required_family == "tender_procurement":
        return {"procurement_award", "project_approval"}
    if "project" in requirement:
        return {"procurement_award", "project_approval", "implementation_plan"}
    if "policy" in requirement or required_family == "policy_document":
        return {"policy_original", "implementation_plan", "formal_notice"}
    return set()


def _source_family_matches_requirement(required_family: str, actual_family: str) -> bool:
    if not required_family:
        return True
    # legacy sentinel: a location-matched official/project source satisfies both
    # policy and project requirements.
    if required_family == "location_matched_official_or_project_source":
        return canonical_source_family(actual_family) in {
            "policy_document",
            "tender_procurement",
            "local_official",
        }
    return canonical_source_family(required_family) == canonical_source_family(actual_family)


def _evaluate_claim_support_eligibility(
    *,
    claim: dict[str, Any],
    evidence: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    required_family = str(claim.get("required_source_family") or "")
    actual_family = str(source.get("source_family") or "")
    evidence_quality = evidence.get("evidence_quality_v2")
    if not isinstance(evidence_quality, dict):
        evidence_quality = {}
    source_quality = source.get("source_quality_v2")
    if not isinstance(source_quality, dict):
        source_quality = {}
    evidence_type = str(evidence.get("evidence_type") or evidence_quality.get("evidence_type") or "")
    proof_strength = str(evidence.get("proof_strength") or evidence_quality.get("proof_strength") or "")
    usage_role = str(
        source_quality.get("usage_role")
        or source.get("source_usage_role")
        or evidence_quality.get("inherited_source_quality", {}).get("source_usage_role")
        or ""
    )
    required_types = _claim_required_evidence_types(claim)
    reason_code = "eligible"
    eligible = True
    if required_family and not _source_family_matches_requirement(required_family, actual_family):
        eligible = False
        reason_code = "wrong_source_family"
    elif usage_role in {"context_only", "exclude_from_primary_evidence"}:
        eligible = False
        reason_code = "context_only"
    elif proof_strength in {"context_only", "ineligible"}:
        eligible = False
        reason_code = proof_strength
    elif required_types and evidence_type not in required_types:
        eligible = False
        reason_code = "wrong_evidence_type"
    # G4 精简：移除 citation_integrity<0.45（死门，恒≥0.85）与 source credibility<0.35
    # （usage_role 已前置排除低分源）两死分支。
    return {
        "eligible": eligible,
        "reason_code": reason_code,
        "claim_id": str(claim.get("claim_id") or ""),
        "evidence_id": str(evidence.get("evidence_id") or ""),
        "source_id": str(source.get("source_id") or ""),
        "required_source_family": required_family,
        "actual_source_family": actual_family,
        "required_evidence_types": sorted(required_types),
        "evidence_type": evidence_type,
        "proof_strength": proof_strength,
        "source_usage_role": usage_role,
        "source_credibility_score": _evidence_float(
            source_quality.get("credibility_score", source.get("source_credibility_score")),
            0.0,
        ),
    }


def _claim_eligibility_decisions(
    *,
    claim: dict[str, Any],
    evidence_map: dict[str, dict[str, Any]],
    source_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for evidence_id in [str(item) for item in claim.get("evidence_ids", []) if str(item)]:
        evidence = evidence_map.get(evidence_id, {})
        source_ids = [str(item) for item in evidence.get("source_ids", []) if str(item)]
        if not source_ids:
            source_id = str(evidence.get("source_id") or "")
            if source_id:
                source_ids = [source_id]
        for source_id in source_ids:
            source = source_map.get(source_id, {})
            decisions.append(
                _evaluate_claim_support_eligibility(
                    claim=claim,
                    evidence=evidence,
                    source=source,
                )
            )
    return decisions


def _enrich_evidence_semantics(
    *,
    evidence_items: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    """Enrich evidence with support_strength, query relevance, and fix limitations.

    Phase 3 goal: make evidence semantics richer before they reach claims/editor1.
    """
    source_map = {str(s.get("source_id")): s for s in sources}
    enriched = []
    for item in evidence_items:
        if not isinstance(item, dict):
            enriched.append(item)
            continue
        # ── 补写 source_family（editor/gate 按维度分组需要） ──
        _ev_src = source_map.get(str(item.get("source_id") or ""), {})
        if not item.get("source_family") and _ev_src:
            item["source_family"] = str(_ev_src.get("source_family") or "")
        # ── Fix limitations: guard against char-split ──
        raw_lim = item.get("limitations")
        if isinstance(raw_lim, str):
            item["limitations"] = [raw_lim] if raw_lim else []
        elif isinstance(raw_lim, list):
            if raw_lim and all(
                isinstance(x, str) and len(x) == 1 for x in raw_lim
            ):
                rejoined = "".join(raw_lim)
                item["limitations"] = [rejoined] if rejoined else []
        # ── Compute support_strength based on evidence quality ──
        summary = str(item.get("summary", ""))
        source = source_map.get(str(item.get("source_id") or ""), {})
        source_title = str(source.get("title", ""))
        combined_text = summary + source_title
        source_family = str(source.get("source_family", ""))
        source_tier = str(
            source.get("source_tier")
            or (source.get("source_quality_v2") or {}).get("tier")
            or "C"
        )
        support_type = str(item.get("support_type", "background_support"))
        # Base strength from source tier
        tier_strength = {"A": 0.8, "B": 0.6, "C": 0.35, "D": 0.15}.get(source_tier, 0.35)
        # Boost for direct support
        if support_type == "direct_support":
            tier_strength += 0.15
        # Boost for source family matching query intent
        if "年报" in query or "披露" in query:
            if source_family in {"company_disclosure", "exchange_disclosure"}:
                tier_strength += 0.1
        if "政策" in query:
            if source_family == "policy_document":
                tier_strength += 0.1
        if "项目" in query or "招标" in query:
            if source_family == "tender_procurement":
                tier_strength += 0.1
        # Summary quality: longer, more detailed summaries = stronger
        if len(summary) > 80:
            tier_strength += 0.05
        if len(summary) > 200:
            tier_strength += 0.05
        # Region relevance up-weight（折入 support_strength，原 _query_relevance_score 冗余）
        region_match = _region_match_for_text(
            query=query,
            text=combined_text,
            domain=str(source.get("domain") or ""),
        )
        if region_match == "exact_local":
            tier_strength += 0.1
        elif region_match in ("child_local", "parent_local"):
            tier_strength += 0.05
        elif region_match == "unrelated_region":
            tier_strength -= 0.15
        # Cap at 1.0；权威 overwrite（原 max 双算 → 单一公式）
        strength = round(min(1.0, max(0.0, tier_strength)), 3)
        item["support_strength"] = strength
        evidence_quality_v2 = _build_evidence_quality_v2_for_graph(
            item=item,
            source=source,
            summary=summary,
            support_strength=float(item.get("support_strength") or 0.0),
        )
        item["evidence_quality_v2"] = evidence_quality_v2
        item["evidence_type"] = evidence_quality_v2["evidence_type"]
        item["proof_strength"] = evidence_quality_v2["proof_strength"]
        # ── Fix truncated limitations using evidence summary ──
        fixed_lims = []
        for lim in item.get("limitations", []):
            if isinstance(lim, str) and len(lim) < 20 and not lim.endswith("。"):
                if len(summary) > len(lim) + 10:
                    fixed_lims.append(summary[:200])
                else:
                    fixed_lims.append(lim + "…(截断)")
            else:
                fixed_lims.append(lim)
        if fixed_lims:
            item["limitations"] = fixed_lims
        enriched.append(item)
    return enriched


# ── ClaimCard (research-contract-refactor Phase A) ──────────────────────────
# Additive ClaimCard schema on top of existing claim dicts. Old fields are
# preserved; new fields are derived deterministically from claim text + linked
# evidence, so the same input always yields the same ClaimCard (no LLM).
#
# Canonical claim_type enum:
#   fact / comparison / trend / causal / synthesis / risk / outlook / evidence_gap
# Canonical epistemic_status enum:
#   supported / supported_with_limitation / partially_supported / conflicted /
#   unsupported / not_found

_CLAIM_TYPE_KEYWORDS: dict[str, list[str]] = {
    "comparison": [
        "相比", "对比", "高于", "低于", "超过", "不及", "优于", "劣于",
        "差距", "倍", "位次", "排名", "领先", "落后",
    ],
    "trend": [
        "增长", "下降", "上升", "下滑", "上涨", "回落", "趋势", "同比", "环比",
        "逐年", "持续增长", "持续下降", "波动", "回升", "走高", "走低",
    ],
    "causal": [
        "因为", "因此", "导致", "推动", "带动", "促进", "源于", "得益于",
        "由于", "促使", "助推", "引发", "驱动",
    ],
    "risk": [
        "风险", "不确定", "缺乏", "不足", "未能", "尚未", "隐患", "挑战",
        "待解", "承压", "脆弱", "制约",
    ],
    "outlook": [
        "预计", "预期", "展望", "未来", "规划", "目标", "力争", "有望",
        "计划", "将建设", "将投产", "将落地", "拟",
    ],
    "synthesis": [
        "综合", "总体", "整体", "综上", "概览", "总结", "全貌", "综上所述",
        "总体来看", "整体而言",
    ],
    "fact": [
        "数据显示", "发布", "年报显示", "披露", "报告显示", "统计", "公告",
        "公布", "明确", "于", "万元", "亿元", "万亿",
    ],
}

_CLAIM_TYPE_PRECEDENCE: list[str] = [
    "comparison",
    "trend",
    "causal",
    "risk",
    "outlook",
    "synthesis",
    "fact",
]

_CONFLICT_MARKERS: list[str] = ["矛盾", "冲突", "不一致", "存疑", "contradict"]


def _classify_claim_type(text: str) -> str:
    """Deterministic 8-value claim_type classification (highest-precedence hit)."""
    for ctype in _CLAIM_TYPE_PRECEDENCE:
        if any(kw in text for kw in _CLAIM_TYPE_KEYWORDS[ctype]):
            return ctype
    return "fact"


def _classify_epistemic_status(
    *,
    claim: dict[str, Any],
    claim_text: str,
    supported: bool,
    evidence_quality: dict[str, Any],
) -> str:
    """Deterministic epistemic_status from support flags + linked evidence.

    `not_found` is deliberately NOT auto-assigned here: "未找到" is not a
    self-evident fact — it only becomes true after search coverage reaches a
    threshold. Until a CoverageReport exists (Phase B/A2), a claim with no
    evidence is simply `unsupported`; the corresponding ResearchGap carries the
    "未找到/未覆盖" expression instead (review 2026-08-03).
    """
    linked = int(evidence_quality.get("linked_evidence_count") or 0)
    avg = float(evidence_quality.get("avg_support_strength") or 0.0)
    limitations = [
        str(x) for x in claim.get("limitations", []) if isinstance(x, str)
    ]
    if any(m in "".join(limitations) for m in _CONFLICT_MARKERS):
        return "conflicted"
    if linked == 0:
        return "unsupported"
    if not supported:
        return "partially_supported" if avg >= 0.3 else "unsupported"
    if avg >= 0.6 and not limitations:
        return "supported"
    return "supported_with_limitation"


def _compute_max_assertion_level(
    *,
    supported: bool,
    evidence_quality: dict[str, Any],
) -> int:
    """Highest report level (1..4) this claim may be asserted at.

    Mirrors _claim_strength_guard semantics: level_3 = deep research,
    level_4 = investment-decision grade, requires >=2 independent sources.
    """
    linked = int(evidence_quality.get("linked_evidence_count") or 0)
    src = int(evidence_quality.get("linked_source_count") or 0)
    avg = float(evidence_quality.get("avg_support_strength") or 0.0)
    if not supported or linked == 0:
        return 1
    if src >= 2 and avg >= 0.7:
        return 4
    if avg >= 0.6:
        return 3
    if avg >= 0.4:
        return 2
    return 1


def _compute_forbidden_assertion_levels(max_assertion_level: int) -> list[str]:
    """Machine-readable: report levels the claim must NOT be asserted at.

    Derivable from max_assertion_level; persisted for cheap runtime checks and
    kept consistent by construction (a single source computes both).
    """
    return [f"level_{i}" for i in range(max_assertion_level + 1, 5)]


# Human-readable name for each assertion rank (review 2026-08-03). The machine
# field stays the int rank; the label is for prompts/logs/self-documentation.
_ASSERTION_LEVEL_LABELS: dict[int, str] = {
    1: "mention_only",
    2: "fact_confirmed",
    3: "pattern_supported",
    4: "strong_conclusion",
}


def assertion_level_label(rank: int) -> str:
    return _ASSERTION_LEVEL_LABELS.get(int(rank), "mention_only")


def _compute_forbidden_expansions(
    *,
    claim: dict[str, Any],
    claim_text: str,
    supported: bool,
    epistemic_status: str,
    evidence_quality: dict[str, Any],
) -> list[str]:
    """NL guardrails for Editor1: what this claim must NOT expand into."""
    hints: list[str] = []
    avg = float(evidence_quality.get("avg_support_strength") or 0.0)
    single_source_risk = bool(evidence_quality.get("single_source_risk"))
    required_family = str(claim.get("required_source_family") or "")

    if epistemic_status == "unsupported":
        hints.append("该断言暂无证据支撑，不得展开为正式论点；如必须提及，须标注为'待核实'")
    elif epistemic_status == "not_found":
        hints.append("该断言属于'未发现'结论，仅可陈述检索未果，不得断言为'不存在'")
    elif epistemic_status == "conflicted":
        hints.append("证据间存在矛盾，写作时须并列呈现不同口径并标注不确定性，不得单向采信")
    elif single_source_risk:
        hints.append("该结论仅来自单一来源，不得外推为全局性/跨区域结论")
    elif avg < 0.6:
        hints.append("证据强度中等偏弱，写作时须弱化为'初步迹象/尚待验证'，不得写成确定性结论")

    if any(m in claim_text for m in [
        "未投运", "未投产", "未建成", "在建", "筹建",
        "已投运", "已投产", "已建成", "全面投产",
    ]):
        hints.append("不得断言项目已投运/已投产/已建成")
    if any(m in claim_text for m in ["未签约", "意向", "框架协议", "备忘录"]):
        hints.append("不得把意向/框架表述为正式签约或实际落地")
    if required_family and not supported:
        hints.append(f"该 claim 依赖 {required_family} 证据，写作前需确认该来源类型已就位")
    # Global writing rules (e.g. "new numeric facts require evidence binding")
    # live in the contract's writing_policy, NOT in every claim card
    # (review 2026-08-03). Only claim-specific boundaries belong here.
    return hints[:3]


def _annotate_claim_card(
    *,
    claim: dict[str, Any],
    evidence_map: dict[str, dict[str, Any]],
) -> None:
    """Add ClaimCard fields to a claim dict in place (additive, deterministic).

    Caller must have already computed claim['_evidence_quality'] (see
    _enrich_claim_semantics). Missing/bad values degrade to safe defaults so
    this never raises.
    """
    if not isinstance(claim, dict):
        return
    evidence_quality = claim.get("_evidence_quality")
    if not isinstance(evidence_quality, dict):
        # Recompute a proper fallback from linked evidence so claims that skip
        # _enrich_claim_semantics (e.g. LLM supplements) still get grounded cards.
        ev_ids = [str(eid) for eid in claim.get("evidence_ids", [])]
        linked_evidence = [
            evidence_map[eid] for eid in ev_ids if evidence_map.get(eid)
        ]
        strengths = [
            float(e["support_strength"])
            for e in linked_evidence
            if isinstance(e.get("support_strength"), (int, float))
        ]
        source_ids_seen: set[str] = set()
        for e in linked_evidence:
            for sid in e.get("source_ids", []):
                source_ids_seen.add(str(sid))
            if e.get("source_id"):
                source_ids_seen.add(str(e["source_id"]))
        evidence_quality = {
            "linked_evidence_count": len(linked_evidence),
            "linked_source_count": len(source_ids_seen),
            "avg_support_strength": (
                round(sum(strengths) / len(strengths), 3) if strengths else 0.0
            ),
            "single_source_risk": len(source_ids_seen) < 2 and len(linked_evidence) > 0,
        }
        claim["_evidence_quality"] = evidence_quality
    claim_text = str(claim.get("text") or "")
    supported = bool(claim.get("supported"))

    claim_type = _classify_claim_type(claim_text)
    epistemic_status = _classify_epistemic_status(
        claim=claim,
        claim_text=claim_text,
        supported=supported,
        evidence_quality=evidence_quality,
    )
    max_assertion_level = _compute_max_assertion_level(
        supported=supported,
        evidence_quality=evidence_quality,
    )

    # Multi-slot binding: a claim may answer several slots. primary_slot_id is
    # the highest-priority one; slot_id stays as the backward-compat alias.
    existing_slot_ids = [str(x) for x in claim.get("slot_ids", []) if x]
    if not existing_slot_ids:
        sid = str(claim.get("slot_id") or "")
        existing_slot_ids = [sid] if sid else []
    primary_slot_id = str(claim.get("primary_slot_id") or (existing_slot_ids[0] if existing_slot_ids else ""))
    claim.setdefault("slot_id", primary_slot_id)
    claim["primary_slot_id"] = primary_slot_id
    claim["slot_ids"] = list(dict.fromkeys(existing_slot_ids))

    claim["claim_type"] = claim_type
    claim["epistemic_status"] = epistemic_status
    # Machine rank + human-readable label (review 2026-08-03): the int stays the
    # machine truth; the label is for prompts/logs/self-documentation.
    claim["max_assertion_level"] = max_assertion_level
    claim["assertion_level_label"] = assertion_level_label(max_assertion_level)
    claim["forbidden_assertion_levels"] = _compute_forbidden_assertion_levels(
        max_assertion_level
    )
    claim["forbidden_expansions"] = _compute_forbidden_expansions(
        claim=claim,
        claim_text=claim_text,
        supported=supported,
        epistemic_status=epistemic_status,
        evidence_quality=evidence_quality,
    )


def _enrich_claim_semantics(
    *,
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Enrich claims with evidence-to-claim traceability, claim type, and
    multi-source quality metadata.

    Phase 3 goal: claims should clearly show support quality, claim type,
    and whether they rely on single vs multiple sources.
    """
    _CLAIM_TYPE_INDICATORS: dict[str, list[str]] = {
        "fact": ["数据显示", "发布", "年报显示", "披露", "报告显示", "统计", "公告"],
        "interpretation": ["表明", "反映", "说明", "体现", "意味着", "暗示", "可见"],
        "risk": ["风险", "不确定", "缺乏", "不足", "未能", "尚未", "待核实", "可能"],
    }

    evidence_map = {str(e.get("evidence_id")): e for e in evidence if isinstance(e, dict)}
    enriched = []
    for claim in claims:
        if not isinstance(claim, dict):
            enriched.append(claim)
            continue
        ev_ids = [str(eid) for eid in claim.get("evidence_ids", [])]
        # Compute evidence quality from linked evidence
        support_strengths = []
        source_ids_seen: set[str] = set()
        for eid in ev_ids:
            ev = evidence_map.get(eid, {})
            strength = ev.get("support_strength")
            if isinstance(strength, (int, float)):
                support_strengths.append(float(strength))
            for sid in ev.get("source_ids", []):
                source_ids_seen.add(str(sid))
        avg_strength = (
            round(sum(support_strengths) / len(support_strengths), 3)
            if support_strengths else 0.0
        )
        claim["_evidence_quality"] = {
            "linked_evidence_count": len(ev_ids),
            "linked_source_count": len(source_ids_seen),
            "avg_support_strength": avg_strength,
            "single_source_risk": len(source_ids_seen) < 2 and len(ev_ids) > 0,
            "evidence_quality_labels": [
                str(evidence_map.get(eid, {}).get("proof_strength", "unknown"))
                for eid in ev_ids[:5]
            ],
        }

        # ── Claim type classification ──
        claim_text = str(claim.get("text", ""))
        claim_type = "fact"
        type_hits: dict[str, int] = {}
        for ctype, keywords in _CLAIM_TYPE_INDICATORS.items():
            hits = sum(1 for kw in keywords if kw in claim_text)
            if hits:
                type_hits[ctype] = hits
        if type_hits:
            claim_type = max(type_hits, key=lambda k: type_hits[k])
        # Downgrade to risk if single source + low strength
        if claim["_evidence_quality"]["single_source_risk"] and avg_strength < 0.5:
            claim_type = "risk"
        claim["_claim_type"] = claim_type

        # ── Low-confidence marking ──
        is_low_confidence = (
            not claim.get("supported")
            or avg_strength < 0.3
            or (claim["_evidence_quality"]["single_source_risk"] and avg_strength < 0.6)
        )
        claim["_low_confidence"] = is_low_confidence
        if is_low_confidence:
            claim.setdefault("limitations", [])
            if isinstance(claim["limitations"], list):
                reason = (
                    "单源低强度" if claim["_evidence_quality"]["single_source_risk"]
                    else "证据不足"
                )
                if reason not in [str(lim) for lim in claim["limitations"]]:
                    claim["limitations"].append(reason)

        # Auto-derive claim_family if missing
        if not claim.get("claim_family"):
            text = str(claim.get("text", ""))
            required = str(claim.get("required_source_family", ""))
            if "政策" in text or "policy" in required:
                claim["claim_family"] = "policy_basis"
            elif "披露" in text or "年报" in text or "disclosure" in required:
                claim["claim_family"] = "company_disclosure"
            elif "项目" in text or "招标" in text or "transaction" in required:
                claim["claim_family"] = "execution_evidence"
            elif "数据" in text or "统计" in text:
                claim["claim_family"] = "statistics_or_data"
            else:
                claim["claim_family"] = "other"

        # ── ClaimCard (additive, deterministic) ──
        _annotate_claim_card(claim=claim, evidence_map=evidence_map)

        enriched.append(claim)
    return enriched
