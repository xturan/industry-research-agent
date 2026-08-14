from __future__ import annotations

import re
from dataclasses import dataclass

# ── Citation markers: policy numbers, document IDs, percentages, tender codes ──
_CITATION_PATTERNS = [
    re.compile(r"[〔（(]\d{4}[）)〕]\d+号"),       # 粤府办〔2025〕12号
    re.compile(r"\d+年\d+月\d+日"),
    re.compile(r"\d+\.\d+%"),                    # 百分比
    re.compile(r"第[一二三四五六七八九十百千\d]+条"),
    re.compile(r"[A-Z]{2,}-\d{4,}"),             # 招标编号
    re.compile(r"\d+亿元|\d+万元"),               # 金额
]

_NOISE_PATTERNS = [
    re.compile(r"下载|app|直播|攻略|游戏|看片|在线", re.IGNORECASE),
    re.compile(r"javascript|cookie|广告|推广", re.IGNORECASE),
]

_SOURCE_TIER_AUTHORITY = {"A": 0.95, "B": 0.70, "C": 0.40, "D": 0.15}


@dataclass(slots=True)
class ChunkQualityScore:
    info_density: float    # 0-1, 中文字符占比 + 非噪声
    citability: float       # 0-1, 是否含结构化引用标记
    authority: float        # 0-1, 来源权威度
    composite: float        # 0-1, 加权综合

    def __init__(self, info_density: float, citability: float, authority: float):
        object.__setattr__(self, "info_density", round(info_density, 3))
        object.__setattr__(self, "citability", round(citability, 3))
        object.__setattr__(self, "authority", round(authority, 3))
        object.__setattr__(self, "composite", round(
            0.30 * info_density + 0.35 * citability + 0.35 * authority, 3
        ))


def score_chunk_quality(
    text: str,
    *,
    source_family: str = "graph_source",
    source_tier: str = "C",
) -> ChunkQualityScore:
    text = str(text or "").strip()
    if not text:
        return ChunkQualityScore(0.0, 0.0, 0.0)

    # ── Info density ──
    cjk_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    total_chars = max(len(text), 1)
    cjk_ratio = cjk_chars / total_chars
    noise_hits = sum(1 for p in _NOISE_PATTERNS if p.search(text))
    info_density = max(0.0, cjk_ratio - 0.10 * noise_hits)

    # ── Citability ──
    citation_hits = sum(1 for p in _CITATION_PATTERNS if p.search(text))
    citability = min(1.0, 0.15 * citation_hits + (0.15 if cjk_ratio > 0.5 else 0.0))

    # ── Authority ──
    authority = _SOURCE_TIER_AUTHORITY.get(source_tier.upper(), 0.35)

    return ChunkQualityScore(info_density, citability, authority)
