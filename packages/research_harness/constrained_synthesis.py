# ruff: noqa: E501
"""Phase C.3.3 — Constrained Synthesis Layer (shadow).

Bridges the gap the manual A/B review exposed: Structured was compliant but
lacked cross-claim synthesis / transmission / risk explanation. This layer adds
STRICT, deterministic triggers + per-synthesis Contracts so the LLM only turns a
pre-approved inference into natural language — it never chooses which facts to
combine or what conclusion to draw.

Supported synthesis types (v1):
  policy_to_implementation        -> allowed_inference_code=policy_direction_has_observed_implementation
  implementation_to_stage         -> allowed_inference_code=evidence_of_initial_implementation
  cross_source_corroboration      -> allowed_inference_code=cross_source_fact_alignment
  evidence_gap_explanation        -> DETERMINISTIC (no LLM)

LLM is used ONLY for the first three, and only to express a SynthesisContract.
A Synthesis Validator enforces Claim/Evidence/entity/numeric/assertion/limitation
/forbidden-conclusion closure. A Semantic Critic is SHADOW ADVISORY only.

Legacy remains the only formal output; this layer only enriches the shadow
Structured version.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.research_harness.structured_draft import (
    ASSERTION_RANK,
    DraftParagraph,
)

SynthesisType = Literal[
    "policy_to_implementation", "implementation_to_stage",
    "cross_source_corroboration", "evidence_gap_explanation",
]

_IMPL_KEYWORDS = ("投运", "运营", "开工", "建成", "在建", "中标", "开通", "交付", "项目", "场景")
_SCENARIO_KEYWORDS = ("场景", "应用", "航线", "订单", "跨城", "货运")
_STAGE_FORBIDDEN = (
    "规模化商业运营", "产业成熟", "成熟阶段", "快速成长期", "爆发前夜",
    "稳定复制和推广条件", "已经形成完整产业链",
)
_CORROBORATION_FORBIDDEN = ("因果证明", "商业价值确认", "收入贡献确认", "已经获得订单收入")
_ORG_ENTITY_RE = re.compile(r"[\u4e00-\u9fff]{2,}(?:公司|集团|航空|科技|研究院|联盟|平台|中心|银行)")
_GAP_NEGATIVE = ("没有", "未形成", "不存在", "尚未形成")


# ── C.3.3.2 SynthesisContract ───────────────────────────────────────────────

@dataclass(frozen=True)
class SynthesisContract:
    synthesis_id: str
    # source section where the trigger was observed (may be "_report" for cross-section)
    section_id: str
    # section where the synthesis paragraph is INSERTED (cross-section patch)
    target_section_id: str
    synthesis_type: SynthesisType
    required_claim_ids: tuple[str, ...]
    allowed_evidence_ids: tuple[str, ...]
    allowed_inference_code: str
    max_assertion_level: str
    required_limitations: tuple[str, ...]
    forbidden_conclusions: tuple[str, ...]
    trigger_reasons: tuple[str, ...]
    schema_version: str = "synthesis_contract_v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "synthesis_id": self.synthesis_id,
            "section_id": self.section_id,
            "target_section_id": self.target_section_id,
            "synthesis_type": self.synthesis_type,
            "required_claim_ids": list(self.required_claim_ids),
            "allowed_evidence_ids": list(self.allowed_evidence_ids),
            "allowed_inference_code": self.allowed_inference_code,
            "max_assertion_level": self.max_assertion_level,
            "required_limitations": list(self.required_limitations),
            "forbidden_conclusions": list(self.forbidden_conclusions),
            "trigger_reasons": list(self.trigger_reasons),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class SynthesisTriggerInput:
    """Deterministic input for one section's synthesis triggers."""

    section_id: str
    claims: tuple[dict[str, Any], ...]                 # assigned claim cards
    slot_by_claim: dict[str, dict[str, Any]]           # claim_id -> slot
    evidence_map: dict[str, dict[str, Any]]            # evidence_id -> record
    # C.3.3.3: per-claim semantic view (claim.text or verified-evidence fallback)
    semantic_basis: dict[str, ClaimSemanticBasis] = field(default_factory=dict)


# ── C.3.3.3 Claim Semantic Basis (history-compatible, verified-evidence only) ─

@dataclass(frozen=True)
class ClaimSemanticBasis:
    claim_id: str
    text: str
    source: str                        # "claim_text" | "verified_evidence_fallback"
    evidence_ids: tuple[str, ...]
    fallback_used: bool
    diagnostics: tuple[str, ...]


def select_semantic_evidence(
    claim: dict[str, Any],
    evidence: list[dict[str, Any]],
    *,
    max_items: int = 2,
) -> list[dict[str, Any]]:
    """Pick up to `max_items` strongest evidence briefs for semantic fallback.

    Only `verified` evidence passed in by the caller is eligible (caller filters
    on quote_verification_status). Ranking:
      supports primary_slot > primary source > mandatory-field completeness >
      distinct content cluster > longer quoted span.
    Same content_cluster_id is deduplicated.
    """
    slot = str(claim.get("primary_slot_id") or "")
    mandatory = (claim.get("field_requirements") or {}).get("mandatory") or []

    def score(e: dict) -> tuple:
        supports = 1 if slot in (e.get("supports_slot_ids") or []) else 0
        primary = 1 if e.get("is_primary_source") else 0
        fields = 1 if mandatory and all(
            str(e.get("key_fields", {}).get(f, {}).get("status")) == "present"
            for f in mandatory
        ) else (0 if not mandatory else 0)
        span_len = len(str(e.get("quoted_span") or ""))
        return (supports, primary, fields, span_len)

    seen_clusters: set[str] = set()
    selected: list[dict[str, Any]] = []
    for e in sorted(evidence, key=score, reverse=True):
        cluster = str(e.get("content_cluster_id") or e.get("evidence_id"))
        if cluster in seen_clusters:
            continue
        seen_clusters.add(cluster)
        selected.append(e)
        if len(selected) >= max_items:
            break
    return selected


def build_claim_semantic_basis(
    claim: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
    *,
    max_items: int = 2,
) -> ClaimSemanticBasis:
    """Unified semantic view for a claim.

    - claim.text non-empty -> use it (source="claim_text").
    - claim.text empty -> ONLY the claim's OWN bound, verified Evidence
      quoted_spans (source="verified_evidence_fallback"). Never reads raw
      sources, all evidence, legacy draft, or backfill shadow store.
    """
    cid = str(claim.get("claim_id"))
    text = str(claim.get("text") or "").strip()
    if text:
        return ClaimSemanticBasis(
            claim_id=cid, text=text, source="claim_text",
            evidence_ids=(), fallback_used=False, diagnostics=(),
        )
    eligible = [
        evidence_by_id[eid]
        for eid in claim.get("evidence_ids", [])
        if eid in evidence_by_id
        and evidence_by_id[eid].get("quote_verification_status") == "verified"
    ]
    selected = select_semantic_evidence(claim, eligible, max_items=max_items)
    fallback_text = "\n".join(
        str(e.get("quoted_span") or "") for e in selected if (e.get("quoted_span") or "")
    )
    diagnostics = ("CLAIM_TEXT_EMPTY_USING_VERIFIED_EVIDENCE",)
    return ClaimSemanticBasis(
        claim_id=cid,
        text=fallback_text,
        source="verified_evidence_fallback" if fallback_text else "empty",
        evidence_ids=tuple(e["evidence_id"] for e in selected),
        fallback_used=bool(fallback_text),
        diagnostics=diagnostics,
    )


def build_semantic_basis_map(
    claims: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> dict[str, ClaimSemanticBasis]:
    return {
        str(c["claim_id"]): build_claim_semantic_basis(c, evidence_by_id)
        for c in claims
    }


# ── helpers ─────────────────────────────────────────────────────────────────

def _claim_slot(trigger: SynthesisTriggerInput, claim: dict) -> dict[str, Any]:
    return trigger.slot_by_claim.get(claim.get("claim_id"), {}) or {}


def _claim_text(trigger: SynthesisTriggerInput, claim: dict) -> str:
    basis = trigger.semantic_basis.get(claim.get("claim_id"))
    if basis is not None:
        return basis.text
    return str(claim.get("text") or "")


def _is_policy(trigger: SynthesisTriggerInput, claim: dict) -> bool:
    fam = str(_claim_slot(trigger, claim).get("source_family") or "")
    text = _claim_text(trigger, claim)
    return fam == "policy_document" or ("政策" in text or "规划" in text or "方案" in text)


def _is_implementation(trigger: SynthesisTriggerInput, claim: dict) -> bool:
    fam = str(_claim_slot(trigger, claim).get("source_family") or "")
    text = _claim_text(trigger, claim)
    return fam in {
        "tender_procurement",
        "exchange_disclosure",
        "company_disclosure",
        "local_official",
        "official_statistics",
    } or any(
        k in text for k in _IMPL_KEYWORDS
    )


def _has_status(trigger: SynthesisTriggerInput, claim: dict) -> bool:
    text = _claim_text(trigger, claim)
    return any(k in text for k in (
        "投运", "运营", "开工", "建成", "在建", "中标", "启用", "开通", "落地", "交付",
    ))


def _is_scenario(trigger: SynthesisTriggerInput, claim: dict) -> bool:
    text = _claim_text(trigger, claim)
    return any(k in text for k in _SCENARIO_KEYWORDS)


def _min_assertion(*claims: dict) -> str:
    levels = [str(c.get("max_allowed_assertion_level") or "mentioned") for c in claims]
    ranked = [ASSERTION_RANK.get(level, 0) for level in levels]
    return sorted(ASSERTION_RANK, key=lambda k: ASSERTION_RANK[k])[min(ranked)]


def _claim_limitations(claim: dict) -> list[str]:
    return [str(x) for x in claim.get("limitations") or []]


def _union_limitations(*claims: dict) -> list[str]:
    out: list[str] = []
    for c in claims:
        for lim in _claim_limitations(c):
            if lim and lim not in out:
                out.append(lim)
    return out


def _claim_evidence(trigger: SynthesisTriggerInput, claim: dict) -> list[str]:
    return [str(e) for e in claim.get("evidence_ids", []) if e in trigger.evidence_map]


# ── C.3.3.1 report-level cross-section helpers ──────────────────────────────

_REGION_NAMES = ("全国", "国家", "安徽", "合肥", "芜湖", "广东", "广州", "深圳", "东莞",
                 "浙江", "杭州", "宁波", "江苏", "南京", "苏州", "上海", "北京", "四川", "成都")
# subordinate (province -> cities); national policy applies everywhere
_REGION_SUBORDINATE = {
    "安徽": ("合肥", "芜湖"), "广东": ("广州", "深圳", "东莞"),
    "浙江": ("杭州", "宁波"), "江苏": ("南京", "苏州"), "四川": ("成都"),
}
_THEME_TOKENS = ("低空", "物流", "货运", "应用", "场景", "制造", "消防", "救援",
                 "航空", "航线", "订单", "收入", "政策", "产业", "无人")

_TIME_RE_YY = re.compile(r"(20\d{2})\s*年")


def _extract_regions(text: str) -> set[str]:
    return {r for r in _REGION_NAMES if r in (text or "")}


def _region_compatible(policy_text: str, impl_text: str) -> bool:
    policy_regions = _extract_regions(policy_text)
    impl_regions = _extract_regions(impl_text)
    if not impl_regions:
        return True  # implementation has no region -> cannot prove mismatch
    if not policy_regions:
        return False  # implementation has a region but policy doesn't -> be safe? no
    for pr in policy_regions:
        if pr in {"全国", "国家"}:
            return True
        if pr in impl_regions:
            return True
        if impl_regions & set(_REGION_SUBORDINATE.get(pr, ())):
            return True
    return False


def _theme_tokens(text: str) -> set[str]:
    return {t for t in _THEME_TOKENS if t in (text or "")}


def _shares_theme(a_text: str, b_text: str) -> bool:
    return bool(_theme_tokens(a_text) & _theme_tokens(b_text))


def _year(text: str) -> int | None:
    m = _TIME_RE_YY.search(text or "")
    return int(m.group(1)) if m else None


# ── C.3.3.1 Synthesis Trigger Compiler ──────────────────────────────────────

def compile_synthesis_triggers(
    trigger: SynthesisTriggerInput, *, synthesis_seq: list[int] | None = None,
) -> list[SynthesisContract]:
    """Deterministically decide WHICH (if any) synthesis a section may produce.

    Returns zero or more contracts; the LLM may only express these.
    """
    synthesis_seq = synthesis_seq or []
    contracts: list[SynthesisContract] = []
    claims = list(trigger.claims)
    if len(claims) < 2:
        return contracts

    def _next_id() -> str:
        idx = len(contracts) + (synthesis_seq[0] if synthesis_seq else 0)
        return f"syn_{trigger.section_id}_{idx}"

    # 1) policy_to_implementation
    policy_claims = [c for c in claims if _is_policy(trigger, c)]
    impl_claims = [c for c in claims if _is_implementation(trigger, c) and not _is_policy(trigger, c)]
    if policy_claims and impl_claims:
        a, b = policy_claims[0], impl_claims[0]
        contracts.append(SynthesisContract(
            synthesis_id=_next_id(),
            section_id=trigger.section_id,
            target_section_id=trigger.section_id,
            synthesis_type="policy_to_implementation",
            required_claim_ids=(a["claim_id"], b["claim_id"]),
            allowed_evidence_ids=tuple(_claim_evidence(trigger, a) + _claim_evidence(trigger, b)),
            allowed_inference_code="policy_direction_has_observed_implementation",
            max_assertion_level=_min_assertion(a, b),
            required_limitations=tuple(_union_limitations(a, b)),
            forbidden_conclusions=("已经成功推动当地形成成熟的低空物流产业", "政策已全面落地并形成完整产业链"),
            trigger_reasons=("policy_claim_present", "implementation_claim_present"),
        ))

    # 2) implementation_to_stage (needs operation + scenario/limitation; >=2 claims)
    operation_claims = [c for c in claims if _has_status(trigger, c)]
    scenario_claims = [c for c in claims if _is_scenario(trigger, c)]
    has_limitation = any(_claim_limitations(c) for c in claims)
    if operation_claims and (scenario_claims or has_limitation):
        a = operation_claims[0]
        # require a DISTINCT partner claim (operation != scenario/limitation) so the
        # synthesis actually combines two facts rather than a degenerate a==b.
        b = next((c for c in scenario_claims if c["claim_id"] != a["claim_id"]), None)
        if b is None:
            b = next(
                (c for c in claims if _claim_limitations(c) and c["claim_id"] != a["claim_id"]),
                None)
        if b is not None:
            contracts.append(SynthesisContract(
                synthesis_id=_next_id(),
                section_id=trigger.section_id,
                target_section_id=trigger.section_id,
                synthesis_type="implementation_to_stage",
                required_claim_ids=(a["claim_id"], b["claim_id"]),
                allowed_evidence_ids=tuple(_claim_evidence(trigger, a) + _claim_evidence(trigger, b)),
                allowed_inference_code="evidence_of_initial_implementation",
                max_assertion_level="observed",  # stage judgment stays conservative
                # carry limitations from EVERY section claim (stage synthesis must
                # preserve all operational-metric caveats, not just the two picked)
                required_limitations=tuple(_union_limitations(*claims)),
                forbidden_conclusions=_STAGE_FORBIDDEN,
                trigger_reasons=("operation_status_present", "limitation_or_scenario_present"),
            ))

    # 3) cross_source_corroboration (different family + different cluster + same slot)
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            a, b = claims[i], claims[j]
            if a["claim_id"] == b["claim_id"]:
                continue
            if str(a.get("primary_slot_id")) != str(b.get("primary_slot_id")):
                continue
            ea = [trigger.evidence_map[e] for e in _claim_evidence(trigger, a)]
            eb = [trigger.evidence_map[e] for e in _claim_evidence(trigger, b)]
            for e1 in ea:
                for e2 in eb:
                    fam1, fam2 = str(e1.get("source_family")), str(e2.get("source_family"))
                    cl1, cl2 = str(e1.get("content_cluster_id")), str(e2.get("content_cluster_id"))
                    if fam1 and fam2 and fam1 != fam2 and cl1 and cl2 and cl1 != cl2:
                        contracts.append(SynthesisContract(
                            synthesis_id=_next_id(),
                            section_id=trigger.section_id,
            target_section_id=trigger.section_id,
                            synthesis_type="cross_source_corroboration",
                            required_claim_ids=(a["claim_id"], b["claim_id"]),
                            allowed_evidence_ids=(e1["evidence_id"], e2["evidence_id"]),
                            allowed_inference_code="cross_source_fact_alignment",
                            max_assertion_level=_min_assertion(a, b),
                            required_limitations=tuple(_union_limitations(a, b)),
                            forbidden_conclusions=_CORROBORATION_FORBIDDEN,
                            trigger_reasons=("different_source_family", "different_content_cluster"),
                        ))
                        break
                else:
                    continue
                break
    return contracts


# ── C.3.3.1 report-level cross-section trigger scan ─────────────────────────

def _claim_evidence_for(claim: dict, evidence_map: dict[str, dict]) -> list[str]:
    return [str(e) for e in claim.get("evidence_ids", []) if e in evidence_map]


def compile_report_synthesis_triggers(
    section_inputs,
    *,
    slot_by_id: dict[str, dict],
    evidence_map: dict[str, dict],
) -> list[SynthesisContract]:
    """Report-level trigger scan.

    - Delegates per-section types (implementation_to_stage / cross_source /
      in-section policy_to_implementation) to compile_synthesis_triggers.
    - ADD cross-section policy_to_implementation: a policy Claim in one Section
      and an implementation Claim in ANOTHER Section, requiring region
      compatibility + shared theme + time ordering. The synthesis paragraph is
      inserted into the implementation claim's section (target_section_id).
    """
    seq = [0]
    contracts: list[SynthesisContract] = []
    claim_to_section: dict[str, str] = {}
    section_triggers: list[SynthesisTriggerInput] = []
    semantic_map: dict[str, ClaimSemanticBasis] = {}

    for si in section_inputs:
        if si.readiness in {"blocked", "unknown"}:
            continue
        slot_by_claim = {
            c["claim_id"]: slot_by_id.get(c.get("primary_slot_id") or "", {})
            for c in si.claim_cards
        }
        section_semantics = build_semantic_basis_map(list(si.claim_cards), evidence_map)
        semantic_map.update(section_semantics)
        trig = SynthesisTriggerInput(
            section_id=si.section_id, claims=si.claim_cards,
            slot_by_claim=slot_by_claim, evidence_map=evidence_map,
            semantic_basis=section_semantics,
        )
        section_triggers.append(trig)
        local = compile_synthesis_triggers(trig, synthesis_seq=seq)
        contracts.extend(local)
        seq[0] += len(local)
        for c in si.claim_cards:
            claim_to_section[c["claim_id"]] = si.section_id

    # cross-section policy_to_implementation (semantic basis = claim text OR
    # the claim's own verified-evidence fallback)
    policy_claims = [c for t in section_triggers for c in t.claims if _is_policy(t, c)]
    impl_claims = [
        c for t in section_triggers for c in t.claims
        if _is_implementation(t, c) and not _is_policy(t, c)
    ]
    for pc in policy_claims:
        pc_text = semantic_map.get(pc["claim_id"]).text
        for ic in impl_claims:
            ic_text = semantic_map.get(ic["claim_id"]).text
            p_sec = claim_to_section[pc["claim_id"]]
            i_sec = claim_to_section[ic["claim_id"]]
            if p_sec == i_sec:
                continue  # in-section policy_to_implementation already handled
            if not _region_compatible(pc_text, ic_text):
                continue
            if not _shares_theme(pc_text, ic_text):
                continue
            py, iy = _year(pc_text), _year(ic_text)
            if py is not None and iy is not None and py > iy:
                inference = "policy_direction_aligned_with_existing"
                forbidden = ("政策推动了项目落地", "政策导致项目投运", "政策取得成功")
            else:
                inference = "policy_direction_has_observed_implementation"
                forbidden = ("已经成功推动当地形成成熟的低空物流产业", "政策已全面落地并形成完整产业链")
            contracts.append(SynthesisContract(
                synthesis_id=f"syn_x_{seq[0]}",
                section_id="_report",
                target_section_id=i_sec,
                synthesis_type="policy_to_implementation",
                required_claim_ids=(pc["claim_id"], ic["claim_id"]),
                allowed_evidence_ids=tuple(
                    _claim_evidence_for(pc, evidence_map) + _claim_evidence_for(ic, evidence_map)),
                allowed_inference_code=inference,
                max_assertion_level=_min_assertion(pc, ic),
                required_limitations=tuple(_union_limitations(pc, ic)),
                forbidden_conclusions=forbidden,
                trigger_reasons=("cross_section_policy", "cross_section_implementation",
                                 "region_theme_matched"),
            ))
            seq[0] += 1
    return contracts


# ── C.3.3.4 Evidence Gap Paragraph Builder (deterministic, no LLM) ─────────

def build_evidence_gap_paragraph(
    *,
    section_id: str,
    gap_ids: list[str],
    searched_source_families: list[str],
    missing_fields: list[str],
    missing_source_families: list[str],
    available_partial_claim_ids: list[str],
) -> DraftParagraph:
    """A gap paragraph with information content (not a bare 'insufficient')."""
    searched = "、".join(dict.fromkeys(searched_source_families)) or "公开渠道"
    missing = "、".join(dict.fromkeys(missing_fields)) if missing_fields else "相关具体指标"
    missing_src = "、".join(dict.fromkeys(missing_source_families)) if missing_source_families else ""
    partial = (
        "已获得的信息主要反映行业政策和宏观市场背景，不能替代项目层面的经营数据。"
        if available_partial_claim_ids else ""
    )
    text = (
        f"本轮已检索{searched}，但现有材料尚未提供{missing}"
        + (f"，亦缺少{missing_src}来源的佐证" if missing_src else "")
        + "，因此目前无法判断相关事项的具体情况。"
        + partial
    )
    return DraftParagraph(
        paragraph_id=f"gap:{section_id}:0",
        text=text,
        assertion_level="observed",
        paragraph_role="gap_descriptive",
        limitations=(),
        numeric_mentions=(),
    )


# ── C.3.3.3 Synthesis Prompt + strict JSON model ────────────────────────────

class LLMSynthesisParagraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paragraph_role: Literal["synthesis"] = "synthesis"
    synthesis_id: str
    text: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    assertion_level: Literal["mentioned", "observed", "supported", "confirmed"] = "observed"
    limitations: list[str] = Field(default_factory=list)
    numeric_mentions: list[dict[str, str]] = Field(default_factory=list)


class LlmCall(Protocol):
    def __call__(self, system_prompt: str, user_prompt: str) -> dict[str, Any] | None: ...


def build_synthesis_prompt(
    contract: SynthesisContract, *, allowed_numeric_mentions: set[str] | None = None,
) -> tuple[str, str]:
    allowed_numbers = sorted(allowed_numeric_mentions or [])
    number_rule = (
        f"allowed_numeric_mentions={allowed_numbers}\n"
        "规则：正文与 numeric_mentions 只能出现 allowed_numeric_mentions 中的数字；"
        "不得自创日期、金额、比例或数量。若 allowed_numeric_mentions 为空，"
        "numeric_mentions 必须为 []，正文不得出现任何数字。"
    )
    system = (
        "你是严谨的中文产业研报综合段落写作者。只能把给定的 SynthesisContract 表达成一个自然段，"
        "严格禁止：\n"
        "1. 引入 Contract 之外的 Claim / Evidence / 新实体。\n"
        "2. 引入 allowed_numeric_mentions 之外的任何数字（日期/金额/比例/数量）。\n"
        "3. 超出 max_assertion_level。\n"
        "4. 遗漏 required_limitations（必须在正文体现）。\n"
        "5. 写出 positive forbidden_conclusions。注意：可以写否定式边界"
        "（例如'尚不足以判断是否已进入规模化商业运营'），这是允许的；"
        "但不得写正向断言（例如'已经进入规模化商业运营'）。\n"
        "6. 增加 Contract 未允许的因果/阶段/商业价值判断。\n"
        "输出必须是严格 JSON，无额外字段。"
    )
    user = (
        f"synthesis_id={contract.synthesis_id}\n"
        f"synthesis_type={contract.synthesis_type}\n"
        f"allowed_inference_code={contract.allowed_inference_code}\n"
        f"required_claim_ids={list(contract.required_claim_ids)}\n"
        f"allowed_evidence_ids={list(contract.allowed_evidence_ids)}\n"
        f"max_assertion_level={contract.max_assertion_level}\n"
        f"required_limitations={list(contract.required_limitations)}\n"
        f"forbidden_conclusions={list(contract.forbidden_conclusions)}\n"
        f"trigger_reasons={list(contract.trigger_reasons)}\n"
        f"{number_rule}\n"
        f"请按以下 schema 输出单个 paragraph JSON（synthesis_id 必须原样为 {contract.synthesis_id!r}）：\n"
        '{"paragraph_role":"synthesis","synthesis_id":"<synthesis_id>","text":"...",'
        '"claim_ids":[...],"evidence_ids":[...],"assertion_level":"...",'
        '"limitations":[...],"numeric_mentions":[{"text":"<allowed number>","evidence_id":"<allowed evidence>"}]}'
    )
    return system, user


def parse_synthesis_paragraph(raw: Any, *, contract: SynthesisContract) -> LLMSynthesisParagraph:
    if not isinstance(raw, dict):
        raise ValueError(f"synthesis JSON root must be an object, got {type(raw).__name__}")
    draft = LLMSynthesisParagraph.model_validate(raw)
    if draft.synthesis_id != contract.synthesis_id:
        raise ValueError(
            f"synthesis_id mismatch: expected {contract.synthesis_id!r}, got {draft.synthesis_id!r}"
        )
    return draft


# ── C.3.3.5 Synthesis Validator ─────────────────────────────────────────────

@dataclass(frozen=True)
class SynthesisIssue:
    code: str
    severity: Literal["error", "warning"] = "error"
    message: str = ""
    target_id: str = ""


# ── C.3.3.4 negation-aware forbidden + number whitelist ─────────────────────

_NEGATION_MARKERS = (
    "不足以判断", "不足以确认", "无法判断", "不能确认", "尚不能确认",
    "尚未能确认", "不支持", "不可据此推断", "不能据此确认", "无法确认",
)
_MEANINGFUL_NUM_RE = re.compile(
    r"[\d][\d.,]*\s*(?:亿|万|元|%|架|条|台|个|次|小时|公里|km|家|座|份|架次|架/时)"
    r"|20\d{2}"
)


def _positive_forbidden(sentence: str, forbidden: str) -> bool:
    """True when `forbidden` appears in a POSITIVE (non-negated) assertion.

    A negated boundary statement ("现有证据尚不足以判断其是否已进入规模化商业运营")
    is a CORRECT limitation expression and is allowed.
    """
    if forbidden not in sentence:
        return False
    start = 0
    while True:
        idx = sentence.find(forbidden, start)
        if idx < 0:
            return False
        window = sentence[max(0, idx - 40): idx + len(forbidden) + 40]
        if not any(marker in window for marker in _NEGATION_MARKERS):
            return True
        start = idx + len(forbidden)


def _extract_meaningful_numbers(text: str) -> set[str]:
    return {m.group(0).strip() for m in _MEANINGFUL_NUM_RE.finditer(text or "")}


def _allowed_numbers(contract: SynthesisContract, evidence_units: dict) -> set[str]:
    """Allowed numeric mentions = numbers present in the contract's allowed
    evidence quoted_spans (plus any in required claim texts)."""
    allowed: set[str] = set()
    for eid in contract.allowed_evidence_ids:
        e = evidence_units.get(eid)
        if e:
            allowed |= _extract_meaningful_numbers(str(e.get("quoted_span") or ""))
    return allowed


def _known_text(contract: SynthesisContract, claim_cards: dict, evidence_units: dict) -> str:
    parts = []
    for cid in contract.required_claim_ids:
        c = claim_cards.get(cid)
        if c:
            parts.append(str(c.get("text") or ""))
    for eid in contract.allowed_evidence_ids:
        e = evidence_units.get(eid)
        if e:
            parts.append(str(e.get("quoted_span") or ""))
    parts.append(contract.section_id)
    return " ".join(parts)


def validate_synthesis_paragraph(
    draft: LLMSynthesisParagraph,
    *,
    contract: SynthesisContract,
    claim_cards: dict[str, dict],
    evidence_units: dict[str, dict],
) -> list[SynthesisIssue]:
    issues: list[SynthesisIssue] = []

    extra_claims = set(draft.claim_ids) - set(contract.required_claim_ids)
    if extra_claims:
        issues.append(SynthesisIssue(
            "synthesis_claim_outside_contract", "error",
            f"claims outside contract: {sorted(extra_claims)}", ",".join(sorted(extra_claims))))
    extra_evidence = set(draft.evidence_ids) - set(contract.allowed_evidence_ids)
    if extra_evidence:
        issues.append(SynthesisIssue(
            "synthesis_evidence_outside_contract", "error",
            f"evidence outside contract: {sorted(extra_evidence)}",
            ",".join(sorted(extra_evidence))))

    known = _known_text(contract, claim_cards, evidence_units)
    allowed_numbers = _allowed_numbers(contract, evidence_units)
    body = draft.text or ""

    # Numeric closure: only numbers in the contract-allowed evidence spans are
    # allowed, both in numeric_mentions AND in the body text.
    for m in draft.numeric_mentions:
        text = str(m.get("text") or "") if isinstance(m, dict) else ""
        if text and not (_extract_meaningful_numbers(text) <= allowed_numbers):
            issues.append(SynthesisIssue(
                "unsupported_numeric_mention", "error",
                f"numeric mention {text!r} not in allowed_numeric_mentions", text))
    for num in _extract_meaningful_numbers(body):
        if num not in allowed_numbers:
            issues.append(SynthesisIssue(
                "unsupported_numeric_mention", "error",
                f"body number {num!r} not in allowed_numeric_mentions", num))

    # Entity closure (org-like names must come from contract-known text).
    for entity in _ORG_ENTITY_RE.findall(body):
        if entity not in known:
            issues.append(SynthesisIssue(
                "unsupported_synthesis_entity", "error",
                f"new entity {entity!r} not in contract claims/evidence", entity))

    # Assertion limit.
    if ASSERTION_RANK.get(draft.assertion_level, 0) > ASSERTION_RANK.get(
        contract.max_assertion_level, 0
    ):
        issues.append(SynthesisIssue(
            "synthesis_assertion_exceeded", "error",
            f"{draft.assertion_level} > contract max {contract.max_assertion_level}",
            draft.assertion_level))

    # Limitation preservation.
    missing_lim = set(contract.required_limitations) - set(draft.limitations)
    if missing_lim:
        issues.append(SynthesisIssue(
            "synthesis_limitation_missing", "error",
            f"required limitations missing: {sorted(missing_lim)}",
            ",".join(sorted(missing_lim))))

    # Forbidden conclusions: negation-aware (C.3.3.4). A negated boundary
    # statement ("尚不足以判断是否进入规模化商业运营") is a CORRECT limitation
    # expression and must NOT be flagged; only a POSITIVE assertion is a violation.
    for forbidden in contract.forbidden_conclusions:
        if forbidden and _positive_forbidden(body, forbidden):
            issues.append(SynthesisIssue(
                "positive_forbidden_assertion", "error",
                f"positive forbidden conclusion present: {forbidden}", forbidden))

    return issues


# ── generator with one retry ────────────────────────────────────────────────

def generate_synthesis_paragraph(
    contract: SynthesisContract,
    llm_call: LlmCall,
    *,
    claim_cards: dict[str, dict],
    evidence_units: dict[str, dict],
    max_retries: int = 1,
) -> tuple[LLMSynthesisParagraph | None, str, list[SynthesisIssue], list[dict]]:
    """Generate a synthesis paragraph with one precise retry.

    Returns (draft, status, issues, forensics) where forensics records the full
    failure context per attempt (raw output, parsed, issues, retry feedback).
    """
    allowed_numbers = _allowed_numbers(contract, evidence_units)
    last_draft: LLMSynthesisParagraph | None = None
    last_issues: list[SynthesisIssue] = []
    forensics: list[dict] = []
    for _attempt in range(max_retries + 1):
        system, user = build_synthesis_prompt(
            contract, allowed_numeric_mentions=allowed_numbers)
        attempt: dict = {"attempt": _attempt + 1}
        if _attempt > 0 and last_issues:
            user = f"{user}\n\n[仅修复以下问题，保留已通过段落]\n{_retry_feedback(last_issues)}"
        try:
            raw = llm_call(system, user)
        except Exception as exc:  # noqa: BLE001
            forensics.append({**attempt, "error": f"llm_call_failed:{type(exc).__name__}"})
            return None, "llm_failed", [SynthesisIssue("llm_call_failed", "error", str(exc)[:200])], forensics
        attempt["raw_llm_output"] = raw
        if raw is None:
            forensics.append({**attempt, "error": "llm returned None"})
            return None, "llm_failed", [SynthesisIssue("llm_call_failed", "error", "llm returned None")], forensics
        try:
            draft = parse_synthesis_paragraph(raw, contract=contract)
            attempt["parsed_paragraph"] = draft.model_dump()
        except (ValidationError, ValueError) as exc:
            attempt["parse_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            forensics.append(attempt)
            continue
        issues = validate_synthesis_paragraph(
            draft, contract=contract, claim_cards=claim_cards, evidence_units=evidence_units)
        attempt["validation_issues"] = [
            {"code": i.code, "severity": i.severity, "message": i.message, "target_id": i.target_id}
            for i in issues
        ]
        forensics.append(attempt)
        errors = [i for i in issues if i.severity == "error"]
        if not errors:
            return draft, "ok", [], forensics
        last_draft, last_issues = draft, issues
    return last_draft, "validation_failed", last_issues, forensics


def _retry_feedback(issues: list[SynthesisIssue]) -> str:
    """Structured, actionable retry feedback (C.3.3.4)."""
    feedback = {
        "unsupported_numeric_mentions": sorted({
            i.target_id for i in issues if i.code == "unsupported_numeric_mention"
        }),
        "positive_forbidden_assertions": sorted({
            i.target_id for i in issues if i.code == "positive_forbidden_assertion"
        }),
        "missing_limitations": sorted({
            i.target_id for i in issues if i.code == "synthesis_limitation_missing"
        }),
        "other_errors": sorted({i.code for i in issues}),
    }
    instruction = (
        "删除契约未允许的数字；保留正确的证据边界说明（否定式'不足以判断'是允许的，"
        "不得改写为'已经…'）；补齐缺失 limitation；不得改动已通过的 Claim/Evidence 引用。"
    )
    return f"{json.dumps(feedback, ensure_ascii=False)}。{instruction}"


# ── Semantic Critic (shadow advisory, never blocks) ─────────────────────────

_CRITIC_PROMPT = (
    "你是综合段语义审查器。判断给定综合段是否引入了其 Contract 未支持的"
    "新因果、新阶段判断或新商业结论。只输出 JSON："
    '{"risks":["..."]}，无风险则为 []。不得修改综合段。'
)


def run_semantic_critic(
    draft: LLMSynthesisParagraph,
    contract: SynthesisContract,
    llm_call: LlmCall | None,
) -> list[str]:
    """Advisory-only: returns risk strings; never blocks the report."""
    if llm_call is None:
        return []
    try:
        raw = llm_call(_CRITIC_PROMPT, f"contract={contract.to_dict()}\nparagraph={draft.model_dump()}")
        if isinstance(raw, dict):
            risks = raw.get("risks") or []
            return [str(r) for r in risks if r]
    except Exception:  # noqa: BLE001
        pass
    return []
