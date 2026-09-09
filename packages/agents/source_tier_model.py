"""LLM-based Source Tiering via fine-tuned DeepSeek-R1-Distill-Qwen-7B.

Three-layer constraint architecture:
  Layer 3: Constitutional hard rules (override model)
  Layer 1: Pydantic output validation (fallback on parse failure)
  Layer 2: Confidence gating (fallback on low confidence)
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class SourceTierPrediction(BaseModel):
    tier: Literal["A", "B", "C", "D"]
    authority_score: float = Field(ge=0.0, le=1.0)
    usage_note: str = Field(max_length=200, default="")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


SOURCE_TIER_SYSTEM_PROMPT = (
    "你是一个信息源分级专家。严格根据以下标准判断信息源等级：\n\n"
    "A级（仅限政策原文）: 政府发布的法规、通知、规划、实施细则的原文。"
    "URL通常含/zcfb/、/xxgk/、/flfg/或.pdf。域名必须是.gov.cn\n"
    "B级（官方但非政策原文）: 政府新闻动态、政策解读新闻、公共资源交易平台招标公告、"
    "企业公告（cninfo/sse/szse）、上市公司年报。URL常含/xwdt/、/dtxx/、/jggs/\n"
    "C级（半官方/专业机构）: 行业协会(.org/.org.cn)、研究院所、智库报告、"
    "咨询公司分析、学术论文\n"
    "D级（低可信度）: 商业新闻媒体(sohu/sina/163/qq/百家号)、微信公众号文章、"
    "内容聚合器、2020年前的过时信息\n\n"
    "关键区分规则：\n"
    "- .gov.cn域名不一定是A级！政府网站的新闻动态(/xwdt/)、领导讲话是B级\n"
    "- 只有政策法规原文才是A级\n"
    "- 2020年前发布的内容降为D级\n\n"
    '返回JSON: {"tier":"A/B/C/D","authority_score":0.0-1.0,'
    '"usage_note":"一句话理由","confidence":0.0-1.0}'
)


class HardRuleOverrides:
    """Layer 3: Constitutional rules that override model predictions."""

    _CENTRAL_MINISTRIES = frozenset({
        "www.gov.cn", "ndrc.gov.cn", "www.ndrc.gov.cn",
        "miit.gov.cn", "www.miit.gov.cn",
        "most.gov.cn", "www.most.gov.cn",
        "mofcom.gov.cn", "www.mofcom.gov.cn",
        "stats.gov.cn", "www.stats.gov.cn",
        "customs.gov.cn", "www.customs.gov.cn",
        "mof.gov.cn", "www.mof.gov.cn",
        "mee.gov.cn", "www.mee.gov.cn",
        "mohurd.gov.cn", "www.mohurd.gov.cn",
        "samr.gov.cn", "www.samr.gov.cn",
        "nea.gov.cn", "www.nea.gov.cn",
    })
    _POLICY_PATH_MARKERS = ("zcfb", "xxgk", "flfg", "gzdt/zc", "zwgk/wjk")
    _PROCUREMENT_MARKERS = ("ggzy", "ccgp", "ggzyjy", "zfcg")
    _EXCHANGE_DOMAINS = frozenset({"cninfo.com.cn", "sse.com.cn", "szse.cn"})

    def check(
        self, domain: str, url: str, title: str
    ) -> SourceTierPrediction | None:
        """Return override if a constitutional rule matches, else None."""
        # Central government ministries → always A
        if domain in self._CENTRAL_MINISTRIES:
            return SourceTierPrediction(
                tier="A", authority_score=0.98,
                usage_note="中央部委——一手证据", confidence=0.99,
            )
        # .gov.cn + PDF → always A
        if domain.endswith(".gov.cn") and url.lower().endswith(".pdf"):
            return SourceTierPrediction(
                tier="A", authority_score=0.95,
                usage_note="政府PDF文件——政策原文", confidence=0.99,
            )
        # .gov.cn + policy path markers → always A
        if domain.endswith(".gov.cn") and any(m in url for m in self._POLICY_PATH_MARKERS):
            return SourceTierPrediction(
                tier="A", authority_score=0.93,
                usage_note="政府政策发布路径", confidence=0.95,
            )
        # Procurement platforms → always B
        if any(m in domain for m in self._PROCUREMENT_MARKERS):
            return SourceTierPrediction(
                tier="B", authority_score=0.80,
                usage_note="公共资源交易平台", confidence=0.99,
            )
        # Exchange/disclosure platforms → always B
        if any(d in domain for d in self._EXCHANGE_DOMAINS):
            return SourceTierPrediction(
                tier="B", authority_score=0.80,
                usage_note="企业公告平台", confidence=0.99,
            )
        # Severely outdated (pre-2020 in URL/title) → always D
        years = re.findall(r"(20[0-1]\d)", url + title)
        if years and max(int(y) for y in years) < 2020:
            return SourceTierPrediction(
                tier="D", authority_score=0.15,
                usage_note="严重过时——仅供历史参考", confidence=0.99,
            )
        return None


class SourceTierModel:
    """LLM-based source tiering with three-layer constraints."""

    def __init__(self, model_name: str = "qwen2.5:7b"):
        self._model_name = model_name
        self._hard_rules = HardRuleOverrides()
        self._ollama = None
        self._available: bool | None = None

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                from packages.providers.ollama_provider import OllamaProvider
                self._ollama = OllamaProvider(model=self._model_name)
                self._available = self._ollama.available
            except Exception:
                self._available = False
        return self._available

    def classify(
        self,
        *,
        domain: str,
        url: str,
        title: str,
        snippet: str = "",
        extracted_text: str = "",
    ) -> SourceTierPrediction:
        """Classify a source with three-layer constraints."""
        if not domain:
            try:
                domain = urlparse(url).netloc.lower()
            except Exception:
                domain = ""

        # Layer 3: Hard rule overrides
        override = self._hard_rules.check(domain, url, title)
        if override is not None:
            return override

        # Model inference
        if not self.available or self._ollama is None:
            return self._fallback_rules(domain, url, title)

        user_prompt = f"域名: {domain}\nURL: {url}\n标题: {title}"
        if snippet:
            user_prompt += f"\n摘要: {snippet[:200]}"
        if extracted_text:
            user_prompt += f"\n内容片段: {extracted_text[:300]}"

        result = self._ollama.generate_json(
            system_prompt=SOURCE_TIER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        if result.get("error"):
            return self._fallback_rules(domain, url, title)

        # Layer 1: Pydantic validation
        prediction = self._parse_result(result.get("json_data", {}))
        if prediction is None:
            return self._fallback_rules(domain, url, title)

        # Layer 2: Confidence gating
        if prediction.confidence < 0.6:
            return self._fallback_rules(domain, url, title)

        return prediction

    def classify_batch(
        self,
        sources: list[dict[str, str]],
    ) -> list[SourceTierPrediction]:
        """Classify multiple sources (batch optimization)."""
        results = []
        for source in sources:
            results.append(self.classify(
                domain=source.get("domain", ""),
                url=source.get("url", ""),
                title=source.get("title", ""),
                snippet=source.get("snippet", ""),
                extracted_text=source.get("extracted_text", ""),
            ))
        return results

    def _parse_result(self, result: Any) -> SourceTierPrediction | None:
        """Parse and validate model output."""
        if result is None:
            return None
        try:
            if isinstance(result, dict):
                return SourceTierPrediction(**result)
            if isinstance(result, str):
                data = json.loads(result)
                return SourceTierPrediction(**data)
        except Exception:
            pass
        return None

    def _fallback_rules(
        self, domain: str, url: str, title: str
    ) -> SourceTierPrediction:
        """Fallback to deterministic rule-based classification."""
        from packages.agents.deep_research import _classify_source
        tier, authority, usage_note = _classify_source(
            domain=domain, url=url, title=title
        )
        return SourceTierPrediction(
            tier=tier,
            authority_score=authority,
            usage_note=usage_note,
            confidence=0.5,
        )


_source_tier_model: SourceTierModel | None = None


def get_source_tier_model() -> SourceTierModel | None:
    """Get singleton SourceTierModel instance (None if unavailable)."""
    global _source_tier_model
    if _source_tier_model is None:
        _source_tier_model = SourceTierModel()
    if not _source_tier_model.available:
        return None
    return _source_tier_model
