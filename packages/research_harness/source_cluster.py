"""Shadow Source Content Clustering (research-contract-refactor Phase A2).

Deterministic, no LLM, no embedding. Two layers:

- **Exact duplicate**: identical normalized-content hash -> one cluster with
  duplicate_confidence 1.0. Same canonical_url but DIFFERENT content is a
  revision candidate (never merged).
- **Near-duplicate candidate**: title char n-gram Jaccard + content SimHash +
  number/date overlap. Representative-based clustering (NOT simple Union-Find),
  so A~B, B~C does NOT chain into A~C. High-confidence -> shadow cluster merge;
  medium-confidence -> candidate only (never auto-merged).

**Shadow Mode boundary (review 2026-08-03)**: this module NEVER writes
origin_source_id, NEVER mutates the source records, and NEVER changes the formal
source_count / claim / gate / report. It only produces shadow metadata.

"Content cluster" is a statement about *content duplication*, NOT about
independent source entities (same-event independent interviews, policy
interpretations, and "same number, different analysis" are deliberately NOT
merged).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from packages.research_harness.fact_frame import critical_fact_conflict_v2
from packages.sources.local_source_patterns import canonical_source_family

CLUSTERING_VERSION = "source_cluster_v1"
CLUSTERING_MODE = "shadow"

# Tracking params dropped during URL canonicalization (deterministic, safe).
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "yclid", "igshid", "spm", "from", "from_",
    "source", "refer", "share_token", "wxfrm",
}

# Deterministic print/mobile suffixes stripped from the URL path.
_PRINT_MOBILE_PATH = re.compile(r"(/print|/amp|/mobile|/m|/wap)(/|$)", re.IGNORECASE)
_PRINT_MOBILE_PARAM = re.compile(r"^(print|amp|mobile|wap|m|output|format)$", re.IGNORECASE)


# ── Normalization (pure, deterministic) ─────────────────────────────────────

def _normalize_unicode(text: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKC", str(text or ""))


def canonicalize_url(url: str) -> str:
    """Deterministic URL canonicalization.

    - lower scheme + host, drop default ports
    - drop fragment
    - strip tracking params; drop print/mobile markers
    - sort remaining query params
    - unify trailing slash on the path
    """
    url = _normalize_unicode(url or "").strip()
    if not url:
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    scheme = (parts.scheme or "https").lower()
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    try:
        port = parts.port
    except ValueError:
        port = None
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    path = parts.path or ""
    path = _PRINT_MOBILE_PATH.sub("/", path)
    # unify trailing slash except bare root
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    query_items = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        key = key.strip().lower()
        if key in _TRACKING_PARAMS:
            continue
        if _PRINT_MOBILE_PARAM.match(key):
            continue
        query_items.append((key, value))
    query_items.sort()
    new_query = urlencode(query_items) if query_items else ""
    return urlunsplit((scheme, host, path, new_query, ""))


def normalize_title(title: str) -> str:
    """NFKC normalize + strip site-name suffixes/prefixes + collapse whitespace.

    Handles common CMS site-name decorations:
      "正文 - 站点名" / "正文 | 站点名" / "正文 _ 站点名" / "正文 — 站点名"
      "【站点名】正文" / "正文【站点名】"
    Aggressive stripping is acceptable here because title is only a near-dup
    FEATURE — the merge gate is content similarity, not title.
    """
    text = _normalize_unicode(title or "").strip()
    # strip trailing site-name: " - X", " | X", " _ X", " — X"
    text = re.sub(r"\s*[-–—|·_]\s*[^-–—|·_]{2,40}$", "", text).strip()
    # strip leading bracketed site name: 【X】正文 / [X] 正文
    text = re.sub(r"^(?:【[^】]*】|\[[^\]]*\]|（[^）]*）)\s*", "", text).strip()
    # strip trailing bracketed site name
    text = re.sub(r"\s*(?:【[^】]*】|\[[^\]]*\]|（[^）]*）)$", "", text).strip()
    # collapse whitespace
    return re.sub(r"\s+", " ", text).strip()


def normalize_content(content: str) -> str:
    """NFKC normalize + collapse all whitespace to a single space."""
    return re.sub(r"\s+", " ", _normalize_unicode(content or "")).strip()


# ── Fingerprint + similarity features (deterministic) ───────────────────────

def content_fingerprint(content: str) -> str:
    norm = normalize_content(content)
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _char_ngrams(text: str, n: int) -> set[str]:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < n:
        return {compact} if compact else set()
    return {compact[i:i + n] for i in range(len(compact) - n + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def title_similarity(a: str, b: str) -> float:
    """Char bigram Jaccard on normalized titles."""
    return _jaccard(_char_ngrams(normalize_title(a), 2), _char_ngrams(normalize_title(b), 2))


def _simhash(text: str, *, shingle_len: int = 8, bits: int = 64) -> int:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < shingle_len:
        shingles = {compact} if compact else set()
    else:
        shingles = {compact[i:i + shingle_len] for i in range(len(compact) - shingle_len + 1)}
    vector = [0] * bits
    mask = (1 << bits) - 1
    for shingle in shingles:
        h = int(hashlib.md5(shingle.encode("utf-8")).hexdigest(), 16) & mask
        for i in range(bits):
            if h & (1 << i):
                vector[i] += 1
            else:
                vector[i] -= 1
    fp = 0
    for i in range(bits):
        if vector[i] >= 0:
            fp |= 1 << i
    return fp


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def content_similarity(a: str, b: str) -> float:
    """SimHash cosine-ish similarity in [0,1] over normalized content."""
    na, nb = normalize_content(a), normalize_content(b)
    if not na or not nb:
        return 0.0
    fa, fb = _simhash(na), _simhash(nb)
    return 1.0 - _hamming(fa, fb) / 64.0


def content_similarity_from_hashes(fa: int, fb: int) -> float:
    """Similarity from precomputed SimHash fingerprints (avoids recomputation)."""
    return 1.0 - _hamming(fa, fb) / 64.0


# ── Blocking rules (review 2026-08-04) ──────────────────────────────────────
# Precision guards applied BEFORE auto-merge, independent of the single
# similarity threshold. If ANY block fires, the pair must NOT be auto-merged —
# lowering the threshold alone is not the precision lever.

_SUMMARY_LENGTH_RATIO = 0.5  # one side < 50% of the other -> likely summary/excerpt

# Document-type incompatibility: these family pairs are conceptually different
# document classes and must never merge even at high similarity (policy original
# vs commentary / analysis, announcement vs media analysis, ...).
_INCOMPATIBLE_FAMILY_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("policy_document", "commercial_media"),
        ("policy_document", "industry_research"),
        ("company_disclosure", "commercial_media"),
        ("local_official", "industry_research"),
    }
)


def _doc_type_incompatible(a_family: Any, b_family: Any) -> bool:
    fa, fb = canonical_source_family(a_family), canonical_source_family(b_family)
    return (fa, fb) in _INCOMPATIBLE_FAMILY_PAIRS or (fb, fa) in _INCOMPATIBLE_FAMILY_PAIRS


def blocking_reasons(
    a_text: str,
    b_text: str,
    *,
    a_family: Any = None,
    b_family: Any = None,
) -> list[str]:
    """Blocking reasons that forbid auto-merge regardless of similarity.

    - critical_fact_conflict: status/amount/year/subject changed
    - summary_or_excerpt: one side is far shorter than the other
    - document_type_incompatible: incompatible source_family document classes
    """
    reasons: list[str] = []
    # A2.6: entity-bound FactFrame conflict (exact-hash skip + bound conflicts only).
    if critical_fact_conflict_v2(a_text, b_text):
        reasons.append("critical_fact_conflict")
    na, nb = len(normalize_content(a_text)), len(normalize_content(b_text))
    if na and nb and min(na, nb) / max(na, nb) < _SUMMARY_LENGTH_RATIO:
        reasons.append("summary_or_excerpt")
    if _doc_type_incompatible(a_family, b_family):
        reasons.append("document_type_incompatible")
    return reasons


# ── Critical-fact conflict (review 2026-08-03) ──────────────────────────────
# Two near-duplicate texts may be ~95% identical yet differ on a critical fact
# (project status, monetary amount, key year). Such texts are status updates,
# NOT reprints — they must never be auto-merged.

_STATUS_WORDS: tuple[str, ...] = (
    "拟建", "立项", "签约", "开工", "在建", "试运行", "投运", "运营",
    "停运", "延期", "终止", "招标", "中标", "建成", "验收",
)
_MONEY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(亿元|万元|万亿)")
_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _extract_status_words(text: str) -> set[str]:
    compact = normalize_content(text)
    return {w for w in _STATUS_WORDS if w in compact}


def _extract_money(text: str) -> list[tuple[float, str]]:
    compact = normalize_content(text)
    return [(float(m.group(1)), m.group(2)) for m in _MONEY_RE.finditer(compact)]


def _extract_years(text: str) -> set[str]:
    compact = normalize_content(text)
    return {m.group(0) for m in _YEAR_RE.finditer(compact)}


def _money_signature(text: str) -> dict[str, set[float]]:
    """unit -> set of rounded values appearing in the text."""
    signature: dict[str, set[float]] = {}
    for value, unit in _extract_money(text):
        signature.setdefault(unit, set()).add(round(value, 2))
    return signature


def _money_conflict(a: str, b: str) -> bool:
    """For each unit, every value in A must have a near-match in B (and vice
    versa). 500亿 in both is fine; 10亿 in A vs 12亿 in B is a conflict."""
    sa, sb = _money_signature(a), _money_signature(b)
    for unit, values_a in sa.items():
        if unit not in sb:
            continue
        values_b = sb[unit]
        for va in values_a:
            if not any(abs(va - vb) / max(va, vb, 1e-9) <= 0.05 for vb in values_b):
                return True
        for vb in values_b:
            if not any(abs(va - vb) / max(va, vb, 1e-9) <= 0.05 for va in values_a):
                return True
    return False


def _critical_fact_conflict(a: str, b: str) -> bool:
    """True when two near-duplicate texts disagree on a critical fact.

    Deliberately CONSERVATIVE (precision-first, review 2026-08-04): long
    multi-project articles mention many status words and year ranges, so set
    inequality is a false-positive trap. Only the most unambiguous signals fire:

    - project status word sets are DISJOINT (completely different states)
    - same monetary unit but a value differs (>5%, no near-match)
    - both texts carry exactly ONE key year and they differ (single-key-year)
    """
    sa, sb = _extract_status_words(a), _extract_status_words(b)
    if sa and sb and sa.isdisjoint(sb):
        return True
    if _money_conflict(a, b):
        return True
    ya, yb = _extract_years(a), _extract_years(b)
    if len(ya) == 1 and len(yb) == 1 and ya != yb and (sa or sb):
        return True
    return False


_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?(?:亿|万|%|％|亿\w*|万元|亿元)?")


def _number_set(text: str) -> set[str]:
    compact = normalize_content(text)
    return {m.group(0) for m in _NUMBER_RE.finditer(compact) if m.group(0)}


def number_overlap(a: str, b: str) -> float:
    """Containment of the smaller number set in the larger (how much is shared)."""
    na, nb = _number_set(a), _number_set(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    smaller, larger = (na, nb) if len(na) <= len(nb) else (nb, na)
    return len(smaller & larger) / len(larger)


_DATE_RE = re.compile(r"(19|20)\d{2}\s*[年./-]\s*\d{1,2}\s*[月./-]\s*\d{1,2}")


def _date_set(text: str) -> set[str]:
    compact = normalize_content(text)
    return {m.group(0) for m in _DATE_RE.finditer(compact)}


def date_overlap(a: str, b: str) -> float:
    na, nb = _date_set(a), _date_set(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    smaller, larger = (na, nb) if len(na) <= len(nb) else (nb, na)
    return len(smaller & larger) / len(larger)


# ── Source indexing ─────────────────────────────────────────────────────────

def _source_content(source: dict[str, Any]) -> str:
    for key in ("full_text", "raw_text", "content_text"):
        value = str(source.get(key) or "")
        if value.strip():
            return value
    return ""


def _index_source(source: dict[str, Any]) -> dict[str, Any]:
    sid = str(source.get("source_id") or "")
    url = canonicalize_url(str(source.get("url") or source.get("source_url") or ""))
    title = str(source.get("title") or "")
    content = _source_content(source)
    return {
        "source_id": sid,
        "canonical_url": url,
        "normalized_title": normalize_title(title),
        "content": content,
        "content_fingerprint": content_fingerprint(content) if content else "",
        "raw": source,
    }


# ── Clustering ──────────────────────────────────────────────────────────────

def _exact_clusters(
    indexed: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Group by content fingerprint. Sources with same fingerprint -> one cluster.

    Same canonical_url but different content -> revision candidate (returned
    separately, never merged).
    """
    by_fp: dict[str, list[dict[str, Any]]] = {}
    for item in indexed:
        fp = item["content_fingerprint"]
        if fp:
            by_fp.setdefault(fp, []).append(item)

    clusters: list[dict[str, Any]] = []
    for members in by_fp.values():
        if not members:
            continue
        if len(members) == 1:
            clusters.append(
                {
                    "content_cluster_id": f"cluster_{len(clusters) + 1:03d}",
                    "source_ids": [members[0]["source_id"]],
                    "cluster_representative_source_id": members[0]["source_id"],
                    "duplicate_confidence": 0.0,
                    "duplicate_reason": ["unique_content"],
                    "exact": False,
                }
            )
        else:
            clusters.append(
                {
                    "content_cluster_id": f"cluster_{len(clusters) + 1:03d}",
                    "source_ids": [m["source_id"] for m in members],
                    "cluster_representative_source_id": members[0]["source_id"],
                    "duplicate_confidence": 1.0,
                    "duplicate_reason": ["exact_content_hash"],
                    "exact": True,
                }
            )

    # Sources with no content (empty fingerprint) are distinct singletons too —
    # they cannot be clustered, but they still count toward raw == distinct.
    clustered_ids: set[str] = set()
    for cluster in clusters:
        clustered_ids.update(cluster["source_ids"])
    for item in indexed:
        if item["source_id"] not in clustered_ids:
            clusters.append(
                {
                    "content_cluster_id": f"cluster_{len(clusters) + 1:03d}",
                    "source_ids": [item["source_id"]],
                    "cluster_representative_source_id": item["source_id"],
                    "duplicate_confidence": 0.0,
                    "duplicate_reason": ["unique_content"],
                    "exact": False,
                }
            )

    # revision candidates: same canonical_url, different content
    by_url: dict[str, list[dict[str, Any]]] = {}
    for item in indexed:
        if item["canonical_url"]:
            by_url.setdefault(item["canonical_url"], []).append(item)
    revision_candidates: list[dict[str, Any]] = []
    for url, members in by_url.items():
        fingerprints = {m["content_fingerprint"] for m in members if m["content_fingerprint"]}
        if len(members) > 1 and len(fingerprints) > 1:
            revision_candidates.append(
                {
                    "canonical_url": url,
                    "source_ids": [m["source_id"] for m in members],
                    "reason": "same_url_different_content",
                }
            )
    return clusters, revision_candidates


def _near_duplicate_pass(
    indexed: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    *,
    high_threshold: float = 0.90,
    candidate_threshold: float = 0.78,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Representative-based near-duplicate pass.

    Only SINGLETON sources are movable. Each singleton is compared ONLY against
    each cluster's REPRESENTATIVE (never every member), which prevents A~B, B~C
    chaining / cumulative drift. High-confidence -> merged into the matched
    cluster; medium-confidence -> candidate only (never auto-merged).
    """
    source_to_cluster: dict[str, dict[str, Any]] = {}
    for cluster in clusters:
        for sid in cluster.get("source_ids", []):
            source_to_cluster[str(sid)] = cluster

    def _rep_of(cluster: dict[str, Any]) -> dict[str, Any] | None:
        rep_id = cluster.get("cluster_representative_source_id")
        return next((m for m in indexed if m["source_id"] == rep_id), None)

    candidates: list[dict[str, Any]] = []

    # Precompute SimHash fingerprints once per source (large real texts are
    # expensive; avoids O(pairs x texts) recomputation).
    simhash_cache: dict[str, int] = {}
    for item in indexed:
        if item.get("content"):
            simhash_cache[item["source_id"]] = _simhash(normalize_content(item["content"]))

    singleton_ids = [
        c["source_ids"][0] for c in clusters if len(c.get("source_ids", [])) == 1
    ]
    for sid in singleton_ids:
        cluster = source_to_cluster.get(sid)
        if cluster is None or len(cluster.get("source_ids", [])) > 1:
            continue  # already merged into a multi-source cluster
        item = next((m for m in indexed if m["source_id"] == sid), None)
        if item is None or not item.get("content"):
            continue
        item_fp = simhash_cache.get(sid)
        if item_fp is None:
            continue
        best: tuple[float, dict[str, Any] | None, float] = (0.0, None, 0.0)
        for candidate_cluster in clusters:
            if candidate_cluster is cluster:
                continue
            rep = _rep_of(candidate_cluster)
            if rep is None or rep["source_id"] == sid:
                continue
            rep_fp = simhash_cache.get(rep["source_id"])
            if rep_fp is None:
                continue
            cs = content_similarity_from_hashes(item_fp, rep_fp)
            if cs > best[0]:
                ts = title_similarity(item["normalized_title"], rep["normalized_title"])
                best = (cs, candidate_cluster, ts)
        score, target, title_sim = best
        if target is None or score < candidate_threshold:
            continue
        if score >= high_threshold:
            rep = _rep_of(target)
            rep_content = rep["content"] if rep is not None else ""
            blocked = (
                blocking_reasons(
                    item["content"],
                    rep_content,
                    a_family=item["raw"].get("source_family"),
                    b_family=rep["raw"].get("source_family"),
                )
                if rep_content
                else []
            )
            if blocked:
                candidates.append(
                    {
                        "content_cluster_id": target["content_cluster_id"],
                        "source_id": sid,
                        "representative_source_id": target["cluster_representative_source_id"],
                        "duplicate_confidence": round(score, 3),
                        "duplicate_reason": list(blocked),
                        "candidate_only": True,
                    }
                )
                continue
            reasons = (
                ["body_high_similarity", "title_high_similarity"]
                if title_sim >= 0.7
                else ["body_high_similarity"]
            )
            target["source_ids"].append(sid)
            target["duplicate_confidence"] = round(
                max(score, float(target.get("duplicate_confidence") or 0.0)), 3
            )
            target["duplicate_reason"] = list(
                dict.fromkeys([*target.get("duplicate_reason", []), *reasons])
            )
            source_to_cluster[sid] = target
            if cluster in clusters:
                clusters.remove(cluster)
        else:
            # candidate band: surface any blocking-rule reason so it is auditable
            cand_rep = _rep_of(target)
            cand_rep_content = cand_rep["content"] if cand_rep is not None else ""
            cand_blocked = (
                blocking_reasons(
                    item["content"],
                    cand_rep_content,
                    a_family=item["raw"].get("source_family"),
                    b_family=cand_rep["raw"].get("source_family") if cand_rep is not None else None,
                )
                if cand_rep_content
                else []
            )
            candidates.append(
                {
                    "content_cluster_id": target["content_cluster_id"],
                    "source_id": sid,
                    "representative_source_id": target["cluster_representative_source_id"],
                    "duplicate_confidence": round(score, 3),
                    "duplicate_reason": (
                        list(cand_blocked) if cand_blocked else ["body_medium_similarity"]
                    ),
                    "candidate_only": True,
                }
            )
    return clusters, candidates


# ── Public API ──────────────────────────────────────────────────────────────

def cluster_sources(
    sources: list[dict[str, Any]],
    *,
    high_threshold: float = 0.90,
    candidate_threshold: float = 0.78,
) -> dict[str, Any]:
    """Cluster sources by content duplication (shadow only).

    Returns a shadow metadata dict. Does NOT mutate any source record.
    """
    if not isinstance(sources, list):
        sources = []
    indexed = [_index_source(s) for s in sources if isinstance(s, dict)]
    clusters, revision_candidates = _exact_clusters(indexed)
    clusters, near_candidates = _near_duplicate_pass(
        indexed, clusters,
        high_threshold=high_threshold,
        candidate_threshold=candidate_threshold,
    )

    distinct_content_count = len(clusters)
    return {
        "raw_source_count": len(indexed),
        "shadow_distinct_content_count": distinct_content_count,
        "shadow_duplicate_adjusted_source_count": distinct_content_count,
        "clustering_mode": CLUSTERING_MODE,
        "clustering_version": CLUSTERING_VERSION,
        "clusters": clusters,
        "candidates": near_candidates,
        "revision_candidates": revision_candidates,
    }


def slot_source_counts(
    sources_by_slot: dict[str, list[str]],
    cluster_output: dict[str, Any],
) -> list[dict[str, Any]]:
    """Per-slot shadow count differences.

    sources_by_slot: {slot_id: [source_id, ...]} (raw supporting sources).
    """
    source_to_cluster: dict[str, str] = {}
    for cluster in cluster_output.get("clusters", []):
        for sid in cluster.get("source_ids", []):
            source_to_cluster[str(sid)] = cluster["content_cluster_id"]

    rows: list[dict[str, Any]] = []
    for slot_id, source_ids in sources_by_slot.items():
        raw_ids = [str(s) for s in source_ids]
        distinct_clusters = {
            source_to_cluster[sid] for sid in raw_ids if sid in source_to_cluster
        }
        distinct_count = len(distinct_clusters)
        rows.append(
            {
                "slot_id": slot_id,
                "raw_supporting_source_count": len(raw_ids),
                "shadow_distinct_content_count": distinct_count,
                "shadow_count_difference": distinct_count - len(raw_ids),
            }
        )
    return rows
