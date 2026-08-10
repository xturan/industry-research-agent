"""A2.6 — Entity-bound Critical Fact Conflict v2 (FactFrame).

The v1 rule compared whole-document fact SETS (status words / amounts / years)
and over-blocked long multi-entity texts. v2 binds facts to a frame:

    entity / attribute / scope / time / value

Only when the SAME (entity, attribute, scope) carries a DIFFERENT value do we
treat it as a hard conflict. Unbound differences are only risk flags, never a
hard block. Exact normalized-content hash skips conflict detection entirely.

Deterministic only (no LLM) so clustering stays reproducible.
"""

from __future__ import annotations

import re

# ── Status lifecycle (ordered) ──────────────────────────────────────────────
_STATUS_ORDER: list[str] = [
    "拟建", "签约", "备案", "开工", "建设中", "试运行", "投运", "正式投运",
    "运营", "停运", "终止",
]
_STATUS_WORDS: tuple[str, ...] = tuple(_STATUS_ORDER)
# Longest-first alternation so "正式投运" is not split into "投运".
_STATUS_RE = re.compile("|".join(sorted(_STATUS_ORDER, key=len, reverse=True)))

# Amount types (attribute), so 总投资 vs 一期投资 vs 合同金额 are NOT conflated.
_AMOUNT_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("一期投资", "phase1_investment"),
    ("二期投资", "phase2_investment"),
    ("总投资", "total_investment"),
    ("合同金额", "contract_amount"),
    ("中标金额", "winning_bid_amount"),
    ("补贴", "subsidy"),
    ("年度投资", "annual_investment"),
    ("注册资本", "registered_capital"),
]

_MONEY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(亿元|万元|万亿)")
_YEAR_RE = re.compile(r"(19|20)\d{2}")

# Candidate entity names: quoted/book-bracketed names + rule templates.
_ENTITY_NAME_RE = re.compile(
    r"[“\"『《]([^”\"』》]{2,30})[”\"』》]"
    r"|([\u4e00-\u9fa5A-Za-z0-9]{2,24}(?:项目|工程|园区|航线|公司|集团|大学|研究院|政策|专项行动|示范区|产业集群))"
)

_ENTITY_SUFFIXES = re.compile(r"(?:项目|工程|有限公司|股份有限公司|集团)$")
_ENTITY_PREFIX = re.compile(
    r"^(?:合肥市|安徽省|广东省|江门市|江门|合肥|安徽|广东|我省|我市|我县|全市|全省)"
)

# Facts within this many chars before a money/status token count as bound.
_BIND_WINDOW = 60


def _normalize_entity(name: str) -> str:
    n = re.sub(r"\s+", "", str(name or ""))
    n = _ENTITY_PREFIX.sub("", n)
    n = _ENTITY_SUFFIXES.sub("", n)
    return n.strip()


def extract_entities(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in _ENTITY_NAME_RE.finditer(str(text or "")):
        name = (m.group(1) or m.group(2) or "").strip()
        norm = _normalize_entity(name)
        if len(norm) >= 2 and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _nearest_entity(pre_text: str, entities: list[str]) -> str | None:
    best: str | None = None
    best_pos = -1
    for e in entities:
        pos = pre_text.rfind(e)
        if pos > best_pos:
            best_pos = pos
            best = e
    return best


def _amount_type(pre_text: str) -> str:
    for kw, attr in _AMOUNT_TYPE_KEYWORDS:
        if kw in pre_text:
            return attr
    return "amount"


def extract_fact_frames(text: str) -> list[dict]:
    """Return bound fact frames [{entity, attribute, scope, value, unit}]."""
    entities = extract_entities(text)
    frames: list[dict] = []

    for m in _MONEY_RE.finditer(str(text or "")):
        value = float(m.group(1))
        unit = m.group(2)
        pre = str(text)[max(0, m.start() - _BIND_WINDOW): m.start()]
        entity = _nearest_entity(pre, entities)
        attr = _amount_type(pre)
        frames.append({
            "entity": entity or "UNBOUND",
            "attribute": f"amount:{attr}",
            "scope": "",  # scope extraction is a later refinement
            "value": value,
            "unit": unit,
        })

    for m in _STATUS_RE.finditer(str(text or "")):
        word = m.group(0)
        pre = str(text)[max(0, m.start() - _BIND_WINDOW): m.start()]
        entity = _nearest_entity(pre, entities)
        frames.append({
            "entity": entity or "UNBOUND",
            "attribute": "operation_status",
            "scope": "",
            "value": word,
            "unit": None,
        })
    return frames


def _status_is_revision(v1: str, v2: str) -> bool:
    if v1 == v2:
        return False
    if v1 in _STATUS_ORDER and v2 in _STATUS_ORDER:
        return True  # same entity+scope, different lifecycle state -> revision
    return False


def bound_fact_conflict(a: str, b: str) -> list[dict]:
    """Hard conflicts between two texts on the SAME (entity, attribute, scope).

    Returns a list of conflict details. Facts that fail to bind to a shared
    entity are NOT treated as conflicts (unbound difference = risk flag only).
    """
    fa = extract_fact_frames(a)
    fb = extract_fact_frames(b)
    conflicts: list[dict] = []

    def _value_key(f: dict) -> tuple:
        return (f["entity"], f["attribute"], f.get("unit"))

    by_key_a: dict[tuple, list[dict]] = {}
    for f in fa:
        by_key_a.setdefault(_value_key(f), []).append(f)
    by_key_b: dict[tuple, list[dict]] = {}
    for f in fb:
        by_key_b.setdefault(_value_key(f), []).append(f)

    for key in set(by_key_a) & set(by_key_b):
        if key[0] == "UNBOUND":
            continue
        vals_a = {f["value"] for f in by_key_a[key]}
        vals_b = {f["value"] for f in by_key_b[key]}
        if vals_a == vals_b:
            continue
        attr = key[1]
        if attr.startswith("amount:"):
            # same unit amount values differ on a bound entity
            for va in vals_a:
                for vb in vals_b:
                    if abs(va - vb) / max(va, vb, 1e-9) > 0.05:
                        conflicts.append({
                            "entity": key[0], "attribute": attr, "scope": key[2],
                            "a_value": va, "b_value": vb, "unit": key[2] or None,
                        })
        elif attr == "operation_status":
            for va in vals_a:
                for vb in vals_b:
                    if _status_is_revision(str(va), str(vb)):
                        conflicts.append({
                            "entity": key[0], "attribute": attr, "scope": key[2],
                            "a_value": va, "b_value": vb,
                        })
    return conflicts


def critical_fact_conflict_v2(a: str, b: str) -> bool:
    """v2 conflict predicate: exact-hash skip + bound conflicts only.

    Lazy-import content_fingerprint to avoid a module-load cycle with
    source_cluster (which imports this function).
    """
    if a and b:
        from packages.research_harness.source_cluster import content_fingerprint
        if content_fingerprint(a) == content_fingerprint(b):
            return False  # exact content cannot be a revision
    return bool(bound_fact_conflict(a, b))
