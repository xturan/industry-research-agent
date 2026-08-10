from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.providers.base import JsonProviderClient
from packages.research_harness import research_taxonomy
from packages.sources.local_source_patterns import canonical_source_family


class SemanticResearchDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=400)
    caliber_terms: list[str] = Field(default_factory=list, max_length=8)
    source_priority: str = Field(min_length=1, max_length=40)


class SemanticSourceObligation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obligation_id: str = Field(min_length=1, max_length=80)
    source_family: str = Field(min_length=1, max_length=80)
    required_for: str = Field(min_length=1, max_length=240)
    min_required_evidence: int = Field(default=1, ge=1, le=5)


class SemanticDimensionPlanEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension_id: str = Field(min_length=1, max_length=80)
    dimension_type: str = Field(min_length=1, max_length=80)
    research_question: str = Field(min_length=1, max_length=300)
    why_it_matters: str = Field(min_length=1, max_length=400)
    coverage_required: str = Field(min_length=1, max_length=320)
    expected_section_heading: str = Field(min_length=1, max_length=160)
    source_priority: str = Field(min_length=1, max_length=40)
    source_families: list[str] = Field(default_factory=list, max_length=8)
    key_fields: list[str] = Field(default_factory=list, max_length=12)
    search_key_fields: list[str] = Field(default_factory=list, max_length=24)
    caliber_terms: list[str] = Field(default_factory=list, max_length=8)


class SemanticSearchRound(BaseModel):
    model_config = ConfigDict(extra="forbid")

    round_number: int = Field(ge=1, le=12)
    objective: str = Field(min_length=1, max_length=240)
    search_phrases: list[str] = Field(default_factory=list, max_length=6)
    include_domains: list[str] = Field(default_factory=list, max_length=8)
    target_dimensions: list[str] = Field(default_factory=list, max_length=8)
    expected_source_tier: str = Field(min_length=1, max_length=8)


class SemanticQueryRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    needs_company_disclosure: bool = False
    target_location: str | None = Field(default=None, max_length=80)
    is_location_sensitive: bool = False


class SemanticPlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_query: str = Field(min_length=1, max_length=500)
    research_dimensions: list[SemanticResearchDimension] = Field(default_factory=list)
    dimension_plan: list[SemanticDimensionPlanEntry] = Field(default_factory=list)
    caliber_notes: str = Field(default="", max_length=800)
    source_obligations: list[SemanticSourceObligation] = Field(default_factory=list)
    search_rounds: list[SemanticSearchRound] = Field(default_factory=list)
    query_requirements: SemanticQueryRequirements = Field(
        default_factory=SemanticQueryRequirements
    )


@dataclass(slots=True)
class SemanticPlanResult:
    payload: dict[str, Any]
    metadata: dict[str, Any]


def build_semantic_plan(
    *,
    query: str,
    fallback_payload: dict[str, Any],
    client: JsonProviderClient | None = None,
    replan_request: dict[str, Any] | None = None,
    summary_memory: dict[str, Any] | None = None,
    enable_caliber_expansion: bool = True,
) -> SemanticPlanResult:
    """Build the semantic plan WITHOUT the old single "semantic plan assembly"
    LLM call (that call is DISABLED). The research structure (research_dimensions
    / dimension_plan / source_obligations / query_requirements) is produced by
    the intent planner (layer 1 of expand_caliber); the search rounds are
    produced by the search builder (layer 2) and mapped deterministically. The
    result is merged with the bytecode deterministic fallback payload so the
    downstream plan shape is unchanged.

    The planning pipeline is now exactly 2 LLM calls (intent planner + search
    builder), never 3.
    """
    if not enable_caliber_expansion:
        return SemanticPlanResult(
            payload=fallback_payload,
            metadata={
                "planner_mode": "deterministic_fallback",
                "planner_provider": "deterministic",
                "planner_model": "offline_rules_v1",
                "deterministic_fallback": True,
                "reason": "caliber_expansion_disabled",
            },
        )

    from packages.research_harness.caliber_expander import expand_caliber

    try:
        caliber = expand_caliber(
            query=query,
            client=client,
            replan_request=replan_request,
            summary_memory=summary_memory,
        )
    except Exception as exc:  # noqa: BLE001
        return SemanticPlanResult(
            payload=fallback_payload,
            metadata={
                "planner_mode": "deterministic_fallback",
                "planner_provider": "deterministic",
                "planner_model": "offline_rules_v1",
                "deterministic_fallback": True,
                "reason": f"caliber_error:{type(exc).__name__}",
            },
        )

    semantic_dict = _assemble_payload_from_caliber(
        query=query, caliber=caliber, fallback_payload=fallback_payload
    )
    try:
        payload = SemanticPlanPayload.model_validate(semantic_dict)
        reason = "semantic_plan_accepted"
    except ValidationError:
        repaired = _repair_payload(
            payload=semantic_dict, fallback_payload=fallback_payload
        )
        try:
            payload = SemanticPlanPayload.model_validate(repaired)
            reason = "semantic_plan_repaired"
        except ValidationError:
            return SemanticPlanResult(
                payload=fallback_payload,
                metadata={
                    "planner_mode": "deterministic_fallback",
                    "planner_provider": "deterministic",
                    "planner_model": "offline_rules_v1",
                    "deterministic_fallback": True,
                    "reason": "schema_validation_failed",
                },
            )

    merged = _merge_with_fallback(
        fallback_payload=fallback_payload,
        semantic_payload=payload.model_dump(mode="json"),
    )
    merged["caliber_intent_plan"] = caliber.intent_plan
    merged["caliber_search_plan"] = caliber.final_search_plan
    merged["caliber_guard_review"] = caliber.guard_review

    intent_llm = caliber.metadata.get("layer1_mode") == "llm"
    group_count = len(
        [
            g for g in (caliber.final_search_plan or {}).get("search_groups", [])
            if isinstance(g, dict) and g.get("search_phrases")
        ]
    )
    metadata = {
        "planner_mode": "semantic_provider" if intent_llm else "deterministic_fallback",
        "planner_provider": str(
            caliber.metadata.get("intent_provider") or "deterministic"
        ),
        "planner_model": str(
            caliber.metadata.get("intent_model") or "offline_rules_v1"
        ),
        "deterministic_fallback": not intent_llm,
        "reason": reason,
        "caliber_mode": "fallback" if caliber.fallback_used else "llm",
        "planner_stage": "caliber_only",
        "layer1_mode": caliber.metadata.get("layer1_mode", "full_fallback"),
        "layer2_mode": caliber.metadata.get("layer2_mode", "full_fallback"),
        "caliber_search_groups": group_count,
    }
    return SemanticPlanResult(payload=merged, metadata=metadata)


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


_DOMAIN_BY_SOURCE_PREF: dict[str, str] = {
    "巨潮资讯": "cninfo.com.cn",
    "cninfo": "cninfo.com.cn",
    "上交所": "sse.com.cn",
    "深交所": "szse.cn",
    "交易所": "sse.com.cn",
    "政府采购": "ccgp.gov.cn",
    "公共资源交易": "ggzy.gov.cn",
    "政府网站": "gov.cn",
    "地方政府": "gov.cn",
}


def _lcs_len(a: str, b: str) -> int:
    """Longest common substring length (best-effort, for Chinese title matching)."""
    if not a or not b:
        return 0
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    best = 0
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                if dp[i][j] > best:
                    best = dp[i][j]
    return best


def _resolve_round_target_dimensions(
    group: dict[str, Any], dimension_plan: list[dict[str, Any]]
) -> list[str]:
    """Resolve a search_group to its target dimension_id.

    Priority: (1) exact target == dimension_id / dimension_type; (2) Chinese
    title substring match against expected_section_heading / taxonomy label;
    (3) best longest-common-substring >= 2; (4) required_source_family overlap.
    The old family-first ordering collapsed every group onto the first dimension
    that shares the family (e.g. all industry_research groups -> industry_scope),
    which broke per-dimension search planning."""
    family = str(group.get("required_source_family") or "").strip()
    target = str(group.get("target_evidence_need") or "").strip()

    def _dim_ids(dim: dict[str, Any]) -> list[str]:
        return [
            str(dim.get("dimension_id") or "").strip()
        ] if str(dim.get("dimension_id") or "").strip() else []

    if not target:
        return [family] if family else []

    # (1) exact dimension_id / dimension_type match
    for dim in dimension_plan:
        if not isinstance(dim, dict):
            continue
        dim_id = str(dim.get("dimension_id") or "").strip()
        dtype = str(dim.get("dimension_type") or "").strip()
        if target in (dim_id, dtype):
            return _dim_ids(dim)
    # (2) substring match against heading / taxonomy label
    for dim in dimension_plan:
        if not isinstance(dim, dict):
            continue
        dim_id = str(dim.get("dimension_id") or "").strip()
        heading = str(dim.get("expected_section_heading") or "")
        label = str(
            research_taxonomy.DIMENSIONS.get(
                research_taxonomy.canonicalize_dimension_type(
                    str(dim.get("dimension_type") or "")
                ),
                {},
            ).get("label", "")
        )
        if target in heading or heading in target or target in label or label in target:
            return _dim_ids(dim)
    # (3) best longest-common-substring >= 2 (handles near-miss titles)
    best_dim_id = ""
    best_len = 0
    for dim in dimension_plan:
        if not isinstance(dim, dict):
            continue
        dim_id = str(dim.get("dimension_id") or "").strip()
        heading = str(dim.get("expected_section_heading") or "")
        label = str(
            research_taxonomy.DIMENSIONS.get(
                research_taxonomy.canonicalize_dimension_type(
                    str(dim.get("dimension_type") or "")
                ),
                {},
            ).get("label", "")
        )
        for candidate in (heading, label):
            length = _lcs_len(target, candidate)
            if length > best_len:
                best_len = length
                best_dim_id = dim_id
    if best_len >= 2 and best_dim_id:
        return [best_dim_id]
    # (4) family overlap with source_families
    if family:
        for dim in dimension_plan:
            if not isinstance(dim, dict):
                continue
            dim_id = str(dim.get("dimension_id") or "").strip()
            families = [
                canonical_source_family(f)
                for f in (dim.get("source_families") or [])
                if str(f).strip()
            ]
            if canonical_source_family(family) in families:
                return _dim_ids(dim)
    return [target]


_SEARCH_FIELD_TERMS: dict[str, str] = {
    "代表企业": "龙头企业 企业名单",
    "核心产品或服务": "产品 品类",
    "纳入范围": "范围 定义",
    "统计口径": "统计口径 数据",
    "产业链环节": "产业链 环节 上游 中游 下游",
    "上下游关系": "供应商 客户 上下游",
    "客户或供应商": "客户 供应商",
    "产能或供给能力": "产能 产量",
    "收入来源": "收入 营收",
    "价值量": "附加值 利润",
    "本地化程度": "本地 企业",
    "指标数值": "亿元 数值",
    "同比或复合增速": "增长率 同比",
    "细分市场": "细分 市场",
    "政策工具": "补贴 基金 示范区",
    "量化目标": "目标 规划",
    "支持金额或补贴标准": "补贴 金额",
    "市场份额": "市场份额 占有率",
    "认证状态": "认证 资质",
    "量产状态": "量产 产能",
    "招标状态": "招标 中标",
    "投资金额": "投资 金额",
    "当前阶段": "项目 阶段",
    "收费模式": "盈利模式 收费",
    "毛利率": "毛利率 利润",
    "补贴依赖": "补贴 依赖",
    "风险类型": "风险 安全",
    "对标地区": "对比 城市",
    "驱动因素": "驱动 因素 前景",
    "统计公报": "统计 公报 数据",
    "统计数据": "统计 公报 产值",
}


def _fallback_phrases_for_dim(
    dim: dict[str, Any], query: str | None
) -> list[str]:
    """Synthesize search phrases for a dimension omitted by the search builder,
    derived from its Chinese search_key_fields so the fallback round still
    targets the dimension's key fields."""
    skf = list(dim.get("search_key_fields") or [])
    topic = str(query or "").strip()
    out: list[str] = []
    for field in skf:
        if len(out) >= 5:
            break
        term = _SEARCH_FIELD_TERMS.get(field) or field
        phrase = f"{topic} {term}".strip() if topic else term
        if phrase and phrase not in out:
            out.append(phrase)
    return out[:5]


def _short_topic(query: str | None) -> str:
    """取 query 的紧凑主题，作为维度短语前缀。截到第一个问号/句号，再截到
    "是否/能否/如何/目前/处于/还是"等疑问/判断词前，保留主语核心（与
    real_nodes._compact_topic 一致）。避免把整句 query 塞进每条搜索词。"""
    q = str(query or "").strip()
    for sep in ("？", "?", "。", "；", ";"):
        idx = q.find(sep)
        if 5 < idx:
            q = q[:idx]
            break
    for marker in ("是否已经", "是否", "能不能", "能否", "如何", "目前", "处于", "还是"):
        idx = q.find(marker)
        if 3 < idx:
            q = q[:idx]
            break
    return q[:40]


def _norm_phrase(text: str) -> str:
    import re as _re

    return _re.sub(r"[\s、，,。；;？?（）()\[\]]", "", text)


def _is_query_variant(phrase: str, query: str) -> bool:
    """整句 query 变体检测（标点/空格无关）：phrase 与 query 互含即视为变体。"""
    p = _norm_phrase(str(phrase))
    q = _norm_phrase(str(query))
    if not p or not q:
        return False
    return q in p or p in q


def _dim_search_terms(dim: dict[str, Any], q: str) -> list[str]:
    """从维度派生定向搜索词：优先短的 caliber_terms，其次 search_key_fields
    （维度自身 → base taxonomy）。search_key_fields 里**优先取有
    `_SEARCH_FIELD_TERMS` 映射的证据类型字段**（如 招标状态→招标 中标、
    收入来源→收入 营收），再补原始字段名。"""
    terms = [str(t).strip() for t in (dim.get("caliber_terms") or []) if str(t).strip()]
    good = [
        t for t in terms
        if len(t) <= 20 and not _is_query_variant(t, q)
    ]
    if good:
        return good[:3]
    fields = list(dim.get("search_key_fields") or [])
    if not fields:
        dtype = research_taxonomy.canonicalize_dimension_type(
            str(dim.get("dimension_type") or "")
        )
        fields = list(research_taxonomy.DIMENSIONS.get(dtype, {}).get("search_key_fields", []))
    mapped = [f for f in fields if f in _SEARCH_FIELD_TERMS]
    raw = [f for f in fields if f not in _SEARCH_FIELD_TERMS]
    out: list[str] = []
    for f in mapped[:3]:
        term = str(_SEARCH_FIELD_TERMS.get(f) or f).strip()
        if term and term not in out:
            out.append(term)
    for f in raw:
        if len(out) >= 4:
            break
        term = str(f).strip()
        if term and term not in out:
            out.append(term)
    return out


def _enrich_round_phrases(
    rounds: list[dict[str, Any]],
    dimension_plan: list[dict[str, Any]],
    query: str | None,
) -> list[dict[str, Any]]:
    """确保每轮 search_phrases 真正定向到其 target_dimensions 的独特词。

    背景：搜索 builder LLM 常把整句 query 当作 search_phrases / caliber_terms
    填进有 target_dimensions 的轮次 → 实际搜索全打在 query 上，维度（企业订单/
    招投标/统计公报…）一个都没搜到。这里用 target_dimensions 的短 caliber_terms
    或 search_key_fields 派生定向短语，替换掉 query 变体短语。
    """
    # dim 索引：按 dimension_id 及其 canonical dimension_type（含 d_ 前缀）都能查到，
    # 兼容 round 的 target_dimensions 用 "d_market_scale" 而 plan 的 id 是 "market_scale"。
    dims: dict[str, dict[str, Any]] = {}
    for _d in dimension_plan:
        if not isinstance(_d, dict):
            continue
        _did = str(_d.get("dimension_id") or "").strip()
        if _did:
            dims.setdefault(_did, _d)
        _dtype = research_taxonomy.canonicalize_dimension_type(
            str(_d.get("dimension_type") or "")
        )
        if _dtype:
            dims.setdefault(_dtype, _d)
            dims.setdefault(f"d_{_dtype}", _d)
    topic = _short_topic(query)
    q = str(query or "").strip()
    for r in rounds:
        # gap 补搜轮（_gap_targeted）和段二维度补搜轮（_second_pass_dim_backfill）
        # 的短语是缺口 family/维度专用定向词，不该被重写成维度词。跳过。
        if r.get("_gap_targeted") or r.get("_second_pass_dim_backfill"):
            continue
        target_ids = [str(t) for t in r.get("target_dimensions", []) if str(t)]
        if not target_ids:
            continue
        dim_phrases: list[str] = []
        for tid in target_ids:
            dim = dims.get(tid)
            if not dim:
                continue
            for term in _dim_search_terms(dim, q):
                phrase = f"{topic} {term}".strip() if topic else term
                if phrase and phrase not in dim_phrases:
                    dim_phrases.append(phrase)
        if not dim_phrases:
            continue
        existing = [str(p) for p in r.get("search_phrases") or [] if str(p).strip()]
        # 现有短语全是 query 变体 → 用定向短语替换，避免浪费搜索预算
        all_variants = bool(existing) and all(_is_query_variant(p, q) for p in existing)
        # 2026-08-11：每轮只保留 top-2 定向短语，收敛搜索请求数（固定维度轮
        # 每轮 1-2 个最强定向词即可，不必把维度全部 search_key_fields 都搜一遍）。
        _ROUND_PHRASE_LIMIT = 2
        if all_variants:
            r["search_phrases"] = dim_phrases[:_ROUND_PHRASE_LIMIT]
        else:
            merged = list(existing)
            seen = set(merged)
            for p in dim_phrases:
                if p not in seen:
                    seen.add(p)
                    merged.append(p)
            r["search_phrases"] = merged[:_ROUND_PHRASE_LIMIT]
    return rounds


def ensure_base_dimension_rounds(
    rounds: list[dict[str, Any]],
    dimension_plan: list[dict[str, Any]],
    query: str | None,
) -> list[dict[str, Any]]:
    """确保 10 个规范基础维度每个都有搜索轮。

    复用 `_map_search_groups_to_rounds` 的 base-10 fallback：对未被任何现存轮
    target_dimensions 覆盖的基础维度，用其 search_key_fields 派生搜索短语补一轮。
    新轮插在锚点轮（round 0）之后，保证小 max_rounds 预算下基础维度先被执行
    （否则追加到尾部会被预算截掉，搜不到）。
    """
    base_dims: dict[str, dict[str, Any]] = {}
    for base_type in research_taxonomy.BASE_DIMENSIONS:
        meta = research_taxonomy.DIMENSIONS.get(base_type, {})
        base_dims[f"d_{base_type}"] = {
            "dimension_id": f"d_{base_type}",
            "dimension_type": base_type,
            "expected_section_heading": meta.get("expected_section_heading", base_type),
            "search_key_fields": list(meta.get("search_key_fields", [])),
        }
    covered: set[str] = set()
    for r in rounds:
        for d in r.get("target_dimensions", []):
            covered.add(str(d))
    added: list[dict[str, Any]] = []
    for dim_id, dim in base_dims.items():
        dtype = research_taxonomy.canonicalize_dimension_type(
            str(dim.get("dimension_type") or "")
        )
        if dim_id in covered or dtype in covered or f"d_{dtype}" in covered:
            continue
        phrases = _fallback_phrases_for_dim(dim, query)
        if not phrases:
            continue
        heading = dim.get("expected_section_heading") or dtype or dim_id
        added.append({
            "round_number": len(rounds) + len(added) + 1,
            "objective": f"检索{heading}",
            "search_phrases": phrases[:6],
            "include_domains": [],
            "target_dimensions": [dim_id],
            "expected_source_tier": "B",
        })
    if not added:
        return rounds
    merged = [rounds[0], *added, *rounds[1:]] if rounds else added
    for idx, r in enumerate(merged, start=1):
        r["round_number"] = idx
    return merged


def _map_search_groups_to_rounds(
    final_plan: dict[str, Any],
    dimension_plan: list[dict[str, Any]],
    query: str | None = None,
) -> list[dict[str, Any]]:
    """Deterministically map caliber search_groups + anchor_phrases to the
    plan's search_rounds shape (round_number/objective/search_phrases/
    include_domains/target_dimensions/expected_source_tier).

    If the search builder omitted a dimension, a fallback round is synthesized
    from that dimension's search_key_fields so every dimension still gets a
    search target."""
    rounds: list[dict[str, Any]] = []
    anchors = list(final_plan.get("anchor_phrases", []) or [])
    anchor_phrases = [
        str(a.get("phrase", ""))
        for a in anchors if isinstance(a, dict) and str(a.get("phrase", ""))
    ]
    if anchor_phrases:
        rounds.append({
            "round_number": 1,
            "objective": "原始查询锚点搜索",
            "search_phrases": anchor_phrases[:3],
            "include_domains": [],
            "target_dimensions": [],
            "expected_source_tier": "B",
        })
    for g in list(final_plan.get("search_groups", []) or []):
        if not isinstance(g, dict):
            continue
        phrases = [
            str(p.get("phrase", ""))
            for p in g.get("search_phrases", [])
            if isinstance(p, dict) and str(p.get("phrase", ""))
        ]
        if not phrases:
            continue
        if len(rounds) >= 12:
            break
        domains = [
            str(d) for d in (g.get("include_domains") or []) if str(d).strip()
        ]
        if not domains:
            for pref in (g.get("source_type_preference") or []):
                dom = _DOMAIN_BY_SOURCE_PREF.get(str(pref).strip())
                if dom and dom not in domains:
                    domains.append(dom)
        rounds.append({
            "round_number": len(rounds) + 1,
            "objective": str(g.get("dominant_intent") or "")[:240],
            "search_phrases": phrases[:6],
            "include_domains": domains,
            "target_dimensions": _resolve_round_target_dimensions(g, dimension_plan),
            "expected_source_tier": "B",
        })

    # Fallback: ensure every EXPECTED dimension has a round. Expected = the 10
    # canonical base dimensions (authoritative floor) + any conditional dimensions
    # the intent produced. This decouples search-round coverage from how many
    # groups the search-builder LLM happened to emit (it is not reliable at
    # emitting all dimension groups).
    base_dims: dict[str, dict[str, Any]] = {}
    for base_type in research_taxonomy.BASE_DIMENSIONS:
        meta = research_taxonomy.DIMENSIONS.get(base_type, {})
        base_dims[f"d_{base_type}"] = {
            "dimension_id": f"d_{base_type}",
            "dimension_type": base_type,
            "expected_section_heading": meta.get("expected_section_heading", base_type),
            "search_key_fields": list(meta.get("search_key_fields", [])),
        }
    conditional_dims: dict[str, dict[str, Any]] = {}
    for dim in dimension_plan:
        if not isinstance(dim, dict):
            continue
        dtype = research_taxonomy.canonicalize_dimension_type(
            str(dim.get("dimension_type") or "")
        )
        if dtype in research_taxonomy.BASE_DIMENSIONS:
            continue  # base dims come from the canonical floor
        dim_id = str(dim.get("dimension_id") or "").strip()
        if dim_id:
            conditional_dims[dim_id] = dict(dim)
    expected_dims = {**base_dims, **conditional_dims}

    covered_dim_ids: set[str] = set()
    for r in rounds:
        for d in r.get("target_dimensions", []):
            covered_dim_ids.add(str(d))
    for dim_id, dim in expected_dims.items():
        dtype = research_taxonomy.canonicalize_dimension_type(
            str(dim.get("dimension_type") or "")
        )
        if (
            dim_id in covered_dim_ids
            or dtype in covered_dim_ids
            or f"d_{dtype}" in covered_dim_ids
        ):
            continue
        if len(rounds) >= 12:
            break
        phrases = _fallback_phrases_for_dim(dim, query)
        if not phrases:
            continue
        heading = dim.get("expected_section_heading") or dtype or dim_id
        rounds.append({
            "round_number": len(rounds) + 1,
            "objective": f"检索{heading}",
            "search_phrases": phrases[:6],
            "include_domains": [],
            "target_dimensions": [dim_id],
            "expected_source_tier": "B",
        })
    # 用 target_dimensions 的 caliber_terms/search_key_fields 定向每轮短语，
    # 替换 query 变体短语（保证执行到的搜索是维度定向的，而不是整句 query）。
    return _enrich_round_phrases(rounds, dimension_plan, query)


def _research_dim_from_plan_entry(entry: dict[str, Any]) -> dict[str, Any]:
    dim_id = str(entry.get("dimension_id") or "").strip()
    heading = str(entry.get("expected_section_heading") or dim_id or "其他")
    return {
        "dimension_id": dim_id,
        "label": heading[:120],
        "description": str(entry.get("why_it_matters") or "")[:400],
        "caliber_terms": [
            str(t) for t in (entry.get("caliber_terms") or []) if str(t).strip()
        ][:8],
        "source_priority": str(entry.get("source_priority") or "mixed").strip()
        or "mixed",
    }


def _assemble_payload_from_caliber(
    *,
    query: str,
    caliber: Any,
    fallback_payload: dict[str, Any],
) -> dict[str, Any]:
    """Assemble a SemanticPlanPayload-shaped dict from a CaliberExpansionResult.

    The research structure comes from the intent planner (caliber.intent_plan);
    the search rounds come from the search builder (caliber.final_search_plan)
    mapped deterministically. Missing structure falls back to the bytecode
    deterministic fallback plan.
    """
    intent_plan = dict(caliber.intent_plan or {})
    final_plan = dict(caliber.final_search_plan or {})
    fallback_plan = dict(fallback_payload.get("plan", {}) or {})

    dimension_plan = _as_list(intent_plan.get("dimension_plan"))
    research_dimensions = _as_list(intent_plan.get("research_dimensions"))
    if not research_dimensions and dimension_plan:
        research_dimensions = [
            _research_dim_from_plan_entry(e)
            for e in dimension_plan if isinstance(e, dict)
        ]
    if not research_dimensions:
        research_dimensions = _as_list(fallback_plan.get("research_dimensions"))
    if not dimension_plan:
        dimension_plan = _as_list(fallback_plan.get("dimension_plan"))

    source_obligations = _as_list(intent_plan.get("source_obligations"))
    if not source_obligations:
        source_obligations = _as_list(fallback_plan.get("source_obligations"))

    qr = intent_plan.get("query_requirements")
    query_requirements = dict(qr) if isinstance(qr, dict) else {}
    if not query_requirements:
        query_requirements = dict(fallback_plan.get("query_requirements", {}) or {})
        if not query_requirements:
            query_requirements = dict(
                fallback_payload.get("query_requirements", {}) or {}
            )

    caliber_notes = "；".join(
        str(n) for n in (intent_plan.get("caliber_notes") or []) if str(n).strip()
    )[:800]

    search_rounds = _map_search_groups_to_rounds(final_plan, dimension_plan, query=query)
    if not search_rounds:
        search_rounds = _as_list(fallback_plan.get("search_rounds"))

    return {
        "normalized_query": str(
            intent_plan.get("normalized_query") or caliber.normalized_query or query
        )[:500],
        "research_dimensions": research_dimensions,
        "dimension_plan": dimension_plan,
        "caliber_notes": caliber_notes,
        "source_obligations": source_obligations,
        "search_rounds": search_rounds,
        "query_requirements": query_requirements,
    }


def _merge_with_fallback(
    *,
    fallback_payload: dict[str, Any],
    semantic_payload: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(fallback_payload)
    fallback_query_requirements = dict(fallback_payload.get("query_requirements", {}))
    semantic_query_requirements = dict(semantic_payload.get("query_requirements", {}))
    merged_query_requirements = {
        **fallback_query_requirements,
        **semantic_query_requirements,
    }
    merged_query_requirements["needs_company_disclosure"] = bool(
        fallback_query_requirements.get("needs_company_disclosure")
        or semantic_query_requirements.get("needs_company_disclosure")
    )
    merged_query_requirements["target_location"] = (
        semantic_query_requirements.get("target_location")
        or fallback_query_requirements.get("target_location")
    )
    merged_query_requirements["is_location_sensitive"] = bool(
        fallback_query_requirements.get("is_location_sensitive")
        or semantic_query_requirements.get("is_location_sensitive")
        or merged_query_requirements.get("target_location")
    )
    merged["query_requirements"] = {
        **merged_query_requirements,
    }
    fallback_plan = dict(fallback_payload.get("plan", {}))
    merged["plan"] = {
        **fallback_plan,
        "normalized_query": semantic_payload.get(
            "normalized_query",
            fallback_plan.get("normalized_query", ""),
        ),
        "research_dimensions": _merge_research_dimensions(
            fallback=list(fallback_plan.get("research_dimensions", [])),
            semantic=list(semantic_payload.get("research_dimensions", [])),
        ),
        "dimension_plan": _merge_dimension_plan(
            fallback=list(fallback_plan.get("dimension_plan", [])),
            semantic=list(semantic_payload.get("dimension_plan", [])),
            query_requirements=merged_query_requirements,
        ),
        "caliber_notes": semantic_payload.get(
            "caliber_notes",
            fallback_plan.get("caliber_notes", ""),
        ),
        "source_obligations": _merge_source_obligations(
            fallback=list(fallback_plan.get("source_obligations", [])),
            semantic=list(semantic_payload.get("source_obligations", [])),
            query_requirements=merged_query_requirements,
        ),
        "search_rounds": semantic_payload.get(
            "search_rounds",
            fallback_plan.get("search_rounds", []),
        ),
        "execution_mode": fallback_plan.get(
            "execution_mode",
            "provider_backed",
        ),
    }
    return merged


def _repair_payload(
    *,
    payload: dict[str, Any],
    fallback_payload: dict[str, Any],
) -> dict[str, Any]:
    fallback_plan = dict(fallback_payload.get("plan", {}))
    repaired = {
        "normalized_query": payload.get(
            "normalized_query",
            fallback_plan.get("normalized_query", ""),
        ),
        "research_dimensions": _repair_dimensions(
            payload.get("research_dimensions"),
            fallback=list(fallback_plan.get("research_dimensions", [])),
        ),
        "dimension_plan": _repair_dimension_plan(
            payload.get("dimension_plan"),
            fallback=list(fallback_plan.get("dimension_plan", [])),
        ),
        "caliber_notes": str(
            payload.get("caliber_notes") or fallback_plan.get("caliber_notes") or ""
        )[:800],
        "source_obligations": _repair_source_obligations(
            payload.get("source_obligations"),
            fallback=list(fallback_plan.get("source_obligations", [])),
        ),
        "search_rounds": _repair_search_rounds(
            payload.get("search_rounds"),
            fallback=list(fallback_plan.get("search_rounds", [])),
        ),
        "query_requirements": payload.get("query_requirements", {}),
    }
    if not isinstance(repaired["query_requirements"], dict):
        repaired["query_requirements"] = {}
    query_requirements = dict(repaired["query_requirements"])
    query_requirements.setdefault("needs_company_disclosure", False)
    query_requirements.setdefault("target_location", None)
    query_requirements.setdefault("is_location_sensitive", False)
    repaired["query_requirements"] = query_requirements
    return repaired


def _repair_dimensions(
    value: Any,
    *,
    fallback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    repaired: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        fallback_item = fallback[index] if index < len(fallback) else {}
        dimension_id = str(
            item.get("dimension_id") or fallback_item.get("dimension_id") or ""
        ).strip()
        label = str(item.get("label") or fallback_item.get("label") or "").strip()
        description = str(item.get("description") or fallback_item.get("description") or "").strip()
        source_priority = str(
            item.get("source_priority") or fallback_item.get("source_priority") or "mixed"
        ).strip()
        caliber_terms_raw = item.get("caliber_terms")
        if not isinstance(caliber_terms_raw, list):
            caliber_terms_raw = fallback_item.get("caliber_terms", [])
        caliber_terms = [
            str(term).strip() for term in list(caliber_terms_raw) if str(term).strip()
        ][:8]
        if dimension_id and label and description and source_priority:
            repaired.append(
                {
                    "dimension_id": dimension_id,
                    "label": label,
                    "description": description,
                    "caliber_terms": caliber_terms,
                    "source_priority": source_priority,
                }
            )
    return repaired or fallback


def _repair_source_obligations(
    value: Any,
    *,
    fallback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    repaired: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        fallback_item = fallback[index] if index < len(fallback) else {}
        obligation_id = str(
            item.get("obligation_id") or fallback_item.get("obligation_id") or ""
        ).strip()
        source_family = str(
            item.get("source_family") or fallback_item.get("source_family") or ""
        ).strip()
        required_for = str(
            item.get("required_for") or fallback_item.get("required_for") or ""
        ).strip()
        min_required_evidence = item.get(
            "min_required_evidence",
            fallback_item.get("min_required_evidence", 1),
        )
        try:
            min_required_evidence = int(min_required_evidence)
        except (TypeError, ValueError):
            min_required_evidence = 1
        if obligation_id and source_family and required_for:
            repaired.append(
                {
                    "obligation_id": obligation_id,
                    "source_family": source_family,
                    "required_for": required_for,
                    "min_required_evidence": min(5, max(1, min_required_evidence)),
                }
            )
    return repaired or fallback


def _repair_dimension_plan(
    value: Any,
    *,
    fallback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    repaired: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        fallback_item = fallback[index] if index < len(fallback) else {}
        dimension_id = str(
            item.get("dimension_id") or fallback_item.get("dimension_id") or ""
        ).strip()
        dimension_type = str(
            item.get("dimension_type") or fallback_item.get("dimension_type") or ""
        ).strip()
        research_question = str(
            item.get("research_question") or fallback_item.get("research_question") or ""
        ).strip()
        why_it_matters = str(
            item.get("why_it_matters") or fallback_item.get("why_it_matters") or ""
        ).strip()
        coverage_required = str(
            item.get("coverage_required") or fallback_item.get("coverage_required") or ""
        ).strip()
        expected_section_heading = str(
            item.get("expected_section_heading")
            or fallback_item.get("expected_section_heading")
            or ""
        ).strip()
        source_priority = str(
            item.get("source_priority") or fallback_item.get("source_priority") or "mixed"
        ).strip()
        source_families_raw = item.get("source_families")
        if not isinstance(source_families_raw, list):
            source_families_raw = fallback_item.get("source_families", [])
        caliber_terms_raw = item.get("caliber_terms")
        if not isinstance(caliber_terms_raw, list):
            caliber_terms_raw = fallback_item.get("caliber_terms", [])
        source_families = [
            str(value).strip()
            for value in list(source_families_raw)
            if str(value).strip()
        ][:8]
        caliber_terms = [
            str(term).strip()
            for term in list(caliber_terms_raw)
            if str(term).strip()
        ][:8]
        if (
            dimension_id
            and dimension_type
            and research_question
            and why_it_matters
            and coverage_required
            and expected_section_heading
            and source_priority
        ):
            repaired.append(
                {
                    "dimension_id": dimension_id,
                    "dimension_type": dimension_type,
                    "research_question": research_question,
                    "why_it_matters": why_it_matters,
                    "coverage_required": coverage_required,
                    "expected_section_heading": expected_section_heading,
                    "source_priority": source_priority,
                    "source_families": source_families,
                    "caliber_terms": caliber_terms,
                }
            )
    return repaired or fallback


def _repair_search_rounds(
    value: Any,
    *,
    fallback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    repaired: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        fallback_item = fallback[index] if index < len(fallback) else {}
        round_number = item.get("round_number", fallback_item.get("round_number", index + 1))
        try:
            round_number = int(round_number)
        except (TypeError, ValueError):
            round_number = index + 1
        objective = str(item.get("objective") or fallback_item.get("objective") or "").strip()
        expected_source_tier = str(
            item.get("expected_source_tier") or fallback_item.get("expected_source_tier") or "B"
        ).strip()
        target_dimensions_raw = item.get("target_dimensions")
        if not isinstance(target_dimensions_raw, list):
            target_dimensions_raw = fallback_item.get("target_dimensions", [])
        phrases_raw = item.get("search_phrases")
        if not isinstance(phrases_raw, list):
            phrases_raw = fallback_item.get("search_phrases", [])
        domains_raw = item.get("include_domains")
        if not isinstance(domains_raw, list):
            domains_raw = fallback_item.get("include_domains", [])
        search_phrases = _dedupe_preserve_order(
            str(term).strip() for term in list(phrases_raw) if str(term).strip()
        )[:6]
        include_domains = [
            str(domain).strip() for domain in list(domains_raw) if str(domain).strip()
        ][:8]
        target_dimensions = [
            str(value).strip()
            for value in list(target_dimensions_raw)
            if str(value).strip()
        ][:8]
        if objective and expected_source_tier and search_phrases:
            repaired.append(
                {
                    "round_number": min(6, max(1, round_number)),
                    "objective": objective,
                    "search_phrases": search_phrases,
                    "include_domains": include_domains,
                    "target_dimensions": target_dimensions,
                    "expected_source_tier": expected_source_tier,
                }
            )
    return repaired or fallback


def _merge_source_obligations(
    *,
    fallback: list[dict[str, Any]],
    semantic: list[dict[str, Any]],
    query_requirements: dict[str, Any],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {
        str(item.get("obligation_id")): dict(item) for item in fallback if item.get("obligation_id")
    }
    for item in semantic:
        obligation_id = str(item.get("obligation_id") or "").strip()
        if not obligation_id:
            continue
        by_id[obligation_id] = dict(item)
    if query_requirements.get("needs_company_disclosure"):
        disclosure = next(
            (
                dict(item)
                for item in fallback
                if str(item.get("source_family") or "") == "company_disclosure"
            ),
            None,
        )
        if disclosure is not None:
            by_id[str(disclosure.get("obligation_id"))] = disclosure
    if query_requirements.get("target_location"):
        policy_primary = next(
            (
                dict(item)
                for item in fallback
                if canonical_source_family(item.get("source_family"))
                == "policy_document"
            ),
            None,
        )
        if policy_primary is not None:
            by_id[str(policy_primary.get("obligation_id"))] = policy_primary
    return list(by_id.values())


def _merge_research_dimensions(
    *,
    fallback: list[dict[str, Any]],
    semantic: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge research_dimensions by dimension_id with a fallback floor.

    Same id-dedup merge used for dimension_plan / source_obligations. The floor
    guarantees the plan always carries the bytecode deterministic dimensions even
    when the intent planner returns fewer (runner invariant: >= 2 dims incl. a
    policy dimension)."""
    by_id: dict[str, dict[str, Any]] = {
        str(item.get("dimension_id")): dict(item)
        for item in fallback
        if isinstance(item, dict) and item.get("dimension_id")
    }
    for item in semantic:
        if not isinstance(item, dict):
            continue
        dimension_id = str(item.get("dimension_id") or "").strip()
        if not dimension_id:
            continue
        by_id[dimension_id] = dict(item)
    return list(by_id.values())


def _merge_dimension_plan(
    *,
    fallback: list[dict[str, Any]],
    semantic: list[dict[str, Any]],
    query_requirements: dict[str, Any],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {
        str(item.get("dimension_id")): dict(item)
        for item in fallback
        if item.get("dimension_id")
    }
    for item in semantic:
        dimension_id = str(item.get("dimension_id") or "").strip()
        if not dimension_id:
            continue
        by_id[dimension_id] = dict(item)

    def _has_dim_type(dim_type: str) -> bool:
        canon = research_taxonomy.canonicalize_dimension_type(dim_type)
        return any(
            research_taxonomy.canonicalize_dimension_type(
                str(d.get("dimension_type") or "")
            ) == canon
            for d in by_id.values()
            if isinstance(d, dict)
        )

    def _ensure_synthetic(dim_type: str) -> None:
        """Guarantee a required dimension survives even if the intent planner
        omitted it. Prefer an existing fallback entry of the same canonical
        type; otherwise emit a synthetic default from the taxonomy."""
        if _has_dim_type(dim_type):
            return
        for item in fallback:
            if research_taxonomy.canonicalize_dimension_type(
                str(item.get("dimension_type") or "")
            ) == research_taxonomy.canonicalize_dimension_type(dim_type):
                by_id[str(item.get("dimension_id"))] = dict(item)
                return
        meta = research_taxonomy.DIMENSIONS.get(dim_type, {})
        primary_family = research_taxonomy.DIMENSION_PRIMARY_FAMILY.get(
            dim_type, "industry_research"
        )
        dim_id = f"d_{dim_type}"
        by_id[dim_id] = {
            "dimension_id": dim_id,
            "dimension_type": dim_type,
            "research_question": f"该产业的{dim_type}证据是什么？",
            "why_it_matters": meta.get("label", dim_type),
            "coverage_required": f"收集{dim_type}相关证据",
            "expected_section_heading": meta.get(
                "expected_section_heading", dim_type
            ),
            "source_priority": meta.get("source_priority", "mixed"),
            "source_families": [primary_family],
            "key_fields": list(meta.get("key_fields", [])),
            "caliber_terms": [],
        }

    # Force all 10 base dimensions so a full industry-research plan is always
    # produced, even when the intent planner omitted some.
    for dim_type in research_taxonomy.BASE_DIMENSIONS:
        _ensure_synthetic(dim_type)
    # Conditional dimensions per query intent.
    if query_requirements.get("needs_company_disclosure"):
        _ensure_synthetic("company_fundamentals")
    if query_requirements.get("target_location"):
        _ensure_synthetic("regional_benchmark")
    return list(by_id.values())


def _dedupe_preserve_order(values: Any) -> list[str]:
    output: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in output:
            output.append(normalized)
    return output


# ── Goal-Driven Evidence ReAct (PLAN goal-driven-evidence-react-v1, Phase 1) ──
# evidence_requirement_spec: per report section, what evidence build_evidence
# must gather. Derived from the existing semantic plan (dimension_plan +
# source_obligations) so build_evidence stops working in isolation and instead
# knows the final report's evidence needs. One spec feeds both the build_evidence
# ReAct loop (what to backfill) and claim_strength_guard (sufficiency baseline).

# Which structured fields each dimension type should try to capture, so a thin
# "项目落地" section demands 金额/主体/阶段 instead of a bare line. Read from the
# canonical taxonomy (research_taxonomy) — the single source of truth.
_DIMENSION_KEY_FIELDS: dict[str, list[str]] = {
    dim_id: list(meta.get("key_fields", []))
    for dim_id, meta in research_taxonomy.DIMENSIONS.items()
}
_DEFAULT_MIN_EVIDENCE = 2


def build_evidence_requirement_spec(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive the evidence_requirement_spec from a semantic plan dict.

    Each entry = {section, dimension_type, dimension_id, required_source_families,
    min_evidence, key_fields, coverage_required}. Pure derivation, no I/O — safe
    to call from build_evidence and from claim_strength_guard."""
    if not isinstance(plan, dict):
        return []
    dimension_plan = plan.get("dimension_plan") or []
    obligations = plan.get("source_obligations") or []

    # obligation min-evidence keyed by source_family, to enrich per-dimension mins
    obl_min_by_family: dict[str, int] = {}
    for obl in obligations:
        if not isinstance(obl, dict):
            continue
        fam = str(obl.get("source_family") or "").strip()
        if not fam:
            continue
        try:
            mn = int(obl.get("min_required_evidence") or 1)
        except (TypeError, ValueError):
            mn = 1
        obl_min_by_family[fam] = max(obl_min_by_family.get(fam, 0), mn)

    spec: list[dict[str, Any]] = []
    for dim in dimension_plan:
        if not isinstance(dim, dict):
            continue
        dtype = research_taxonomy.canonicalize_dimension_type(
            str(dim.get("dimension_type") or "").strip()
        )
        families = _dedupe_preserve_order(dim.get("source_families") or [])
        # min evidence: the strongest obligation min among this dim's families,
        # else the default floor
        fam_mins = [obl_min_by_family[f] for f in families if f in obl_min_by_family]
        min_evidence = (
            max([*fam_mins, _DEFAULT_MIN_EVIDENCE])
            if fam_mins
            else _DEFAULT_MIN_EVIDENCE
        )
        spec.append({
            "section": str(dim.get("expected_section_heading") or dtype or "其他"),
            "dimension_type": dtype,
            "dimension_id": str(dim.get("dimension_id") or ""),
            "required_source_families": families,
            "min_evidence": min_evidence,
            "key_fields": list(_DIMENSION_KEY_FIELDS.get(dtype, [])),
            "coverage_required": str(dim.get("coverage_required") or ""),
        })
    return spec

