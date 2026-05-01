from __future__ import annotations

from typing import Any

from packages.agents.deep_research_prompts import (
    CALIBER_EXPANSION_PROMPT,
    EVIDENCE_CHAIN_PROMPT,
    FINAL_SYNTHESIS_PROMPT,
)
from packages.agents.deep_research_schemas import (
    DeepResearchReport,
    EvidenceItem,
    MultiRoundSearchPlan,
    QueryUnderstanding,
    ResearchDimension,
    SearchRoundPlan,
    SourceAssessment,
)
from packages.core.config import get_settings
from packages.providers import DeepSeekProviderClient, ProviderConfigError


class DeepResearchAgent:
    """Multi-round agent that mimics GPT Deep Research methodology.

    Pipeline: Query Understanding → Multi-Round Search → Source Tiering →
              Evidence Chain → Report Assembly
    """

    def __init__(
        self,
        *,
        max_rounds: int = 6,
        max_sources_per_round: int = 5,
        deepseek_client: Any | None = None,
    ) -> None:
        self.max_rounds = max_rounds
        self.max_sources_per_round = max_sources_per_round
        self._client = deepseek_client
        self._collected_sources: list[dict[str, Any]] = []
        self._round_log: list[dict[str, Any]] = []
        self._total_credits = 0

    def run(self, query: str) -> DeepResearchReport:
        """Execute the full deep research pipeline."""
        if self._client is None:
            self._client = self._make_client()

        # Phase 1: Query Understanding
        understanding = self._phase1_query_understanding(query)

        # Phase 2: Multi-Round Search
        search_plan = self._build_search_plan(understanding)
        self._phase2_multi_round_search(query, search_plan)

        # Phase 3: Source Tiering
        source_assessments = self._phase3_source_tiering()

        # Phase 4: Evidence Chain
        evidence_items = self._phase4_evidence_chain(query, source_assessments)

        # Phase 5: Report Assembly
        report = self._phase5_report_assembly(
            query=query,
            understanding=understanding,
            evidence_items=evidence_items,
            source_assessments=source_assessments,
        )

        return report

    # ------------------------------------------------------------------
    # Phase 1: Query Understanding
    # ------------------------------------------------------------------

    def _phase1_query_understanding(self, query: str) -> QueryUnderstanding:
        response = self._call_llm(
            system_prompt=CALIBER_EXPANSION_PROMPT,
            user_prompt=(
                f"Research query: {query}\n\n"
                "Decompose this query into research dimensions with caliber-expanded "
                "search terms. Think about how the Chinese government would phrase "
                "these concepts in official documents."
            ),
        )
        data = response.get("json_data", {}) if isinstance(response, dict) else {}
        if isinstance(data, dict) and data.get("research_dimensions"):
            dims = [
                ResearchDimension(
                    dimension_id=d.get("dimension_id", f"d{i}"),
                    label=d.get("label", ""),
                    description=d.get("description", ""),
                    caliber_terms=d.get("caliber_terms", []),
                    source_priority=d.get("source_priority", "mixed"),
                )
                for i, d in enumerate(data.get("research_dimensions", []))
            ]
            return QueryUnderstanding(
                normalized_query=data.get("normalized_query", query),
                research_dimensions=dims,
                caliber_notes=data.get("caliber_notes", ""),
            )
        # Fallback: deterministic decomposition
        return QueryUnderstanding(
            normalized_query=query,
            research_dimensions=[
                ResearchDimension(
                    dimension_id="d1",
                    label="政策方向",
                    description="国家与地方政策文件",
                    caliber_terms=[query],
                    source_priority="government",
                ),
                ResearchDimension(
                    dimension_id="d2",
                    label="项目落地",
                    description="具体项目和企业证据",
                    caliber_terms=[query],
                    source_priority="enterprise",
                ),
            ],
        )

    # ------------------------------------------------------------------
    # Phase 2: Multi-Round Search Plan
    # ------------------------------------------------------------------

    def _build_search_plan(self, understanding: QueryUnderstanding) -> MultiRoundSearchPlan:
        rounds: list[SearchRoundPlan] = []
        round_num = 1

        # Round 1: National-level policy
        national_dims = [
            d for d in understanding.research_dimensions if d.source_priority == "government"
        ]
        if national_dims:
            national_terms: list[str] = []
            for d in national_dims[:3]:
                national_terms.extend(d.caliber_terms[:3])
            rounds.append(
                SearchRoundPlan(
                    round_number=round_num,
                    objective="搜索国家层面政策文件",
                    search_phrases=national_terms[:6] or [understanding.normalized_query],
                    include_domains=["gov.cn", "ndrc.gov.cn", "miit.gov.cn", "most.gov.cn"],
                    target_dimensions=[d.dimension_id for d in national_dims[:3]],
                    expected_source_tier="A",
                )
            )
            round_num += 1

        # Round 2: Provincial/local policy
        local_terms: list[str] = []
        for d in understanding.research_dimensions:
            local_terms.extend(d.caliber_terms[:2])
        rounds.append(
            SearchRoundPlan(
                round_number=round_num,
                objective="搜索省级和地方政策与实施细则",
                search_phrases=local_terms[:6] or [understanding.normalized_query],
                include_domains=["gov.cn"],
                target_dimensions=[d.dimension_id for d in understanding.research_dimensions[:4]],
                expected_source_tier="A",
            )
        )
        round_num += 1

        # Round 3: Enterprise/project evidence
        enterprise_dims = [
            d
            for d in understanding.research_dimensions
            if d.source_priority in ("enterprise", "mixed")
        ]
        if enterprise_dims:
            enterprise_terms: list[str] = []
            for d in enterprise_dims[:3]:
                enterprise_terms.extend(d.caliber_terms[:3])
            rounds.append(
                SearchRoundPlan(
                    round_number=round_num,
                    objective="搜索企业公告、项目落地和招投标信息",
                    search_phrases=enterprise_terms[:6] or [understanding.normalized_query],
                    include_domains=[],
                    target_dimensions=[d.dimension_id for d in enterprise_dims[:3]],
                    expected_source_tier="B",
                )
            )
            round_num += 1

        # Round 4: Data and statistics
        rounds.append(
            SearchRoundPlan(
                round_number=round_num,
                objective="搜索补充数据和行业统计",
                search_phrases=local_terms[:4] or [understanding.normalized_query],
                include_domains=["stats.gov.cn", "customs.gov.cn"],
                target_dimensions=[d.dimension_id for d in understanding.research_dimensions[:3]],
                expected_source_tier="B",
            )
        )

        return MultiRoundSearchPlan(
            rounds=rounds,
            stop_conditions=[
                "sufficient evidence for all dimensions",
                "budget exhausted",
                "3 consecutive rounds with no new sources",
            ],
        )

    def _phase2_multi_round_search(
        self,
        query: str,
        plan: MultiRoundSearchPlan,
    ) -> None:
        """Execute multi-round search using Tavily + Crawl4AI."""
        from packages.sources.search_discovery import (
            SearchDiscoveryProvider,
            TavilySearchAdapter,
            TavilySearchRequest,
        )

        search_adapter: SearchDiscoveryProvider = TavilySearchAdapter()
        seen_urls: set[str] = set()

        for round_plan in plan.rounds[: self.max_rounds]:
            round_sources: list[dict[str, Any]] = []
            for phrase in round_plan.search_phrases[:3]:
                try:
                    response = search_adapter.search(
                        TavilySearchRequest(
                            query=phrase,
                            include_domains=round_plan.include_domains,
                            max_results=5,
                        )
                    )
                    self._total_credits += _estimate_credits_for_response(response)
                    for result in response.results[:5]:
                        url = result.url.strip()
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        domain = _domain_from_url(url)
                        # Try to extract page content via Crawl4AI for top results
                        extracted_text = _try_crawl_page(url)
                        round_sources.append({
                            "url": url,
                            "domain": domain,
                            "title": result.title or "",
                            "snippet": result.content or "",
                            "extracted_text": extracted_text or "",
                            "score": result.score or 0.0,
                            "round": round_plan.round_number,
                        })
                except Exception:
                    continue

            self._collected_sources.extend(round_sources)
            self._round_log.append({
                "round": round_plan.round_number,
                "objective": round_plan.objective,
                "phrases": round_plan.search_phrases,
                "domains": round_plan.include_domains,
                "status": "completed",
                "sources_found": len(round_sources),
            })

            # Stop early if we have enough sources
            if len(self._collected_sources) >= self.max_sources_per_round * 3:
                break

    # ------------------------------------------------------------------
    # Phase 3: Source Tiering
    # ------------------------------------------------------------------

    def _phase3_source_tiering(self) -> list[SourceAssessment]:
        """Classify sources by tier with nuanced scoring."""
        tiered: list[SourceAssessment] = []
        for source in self._collected_sources:
            domain = source.get("domain", "")
            url = source.get("url", "")
            title = source.get("title", "")

            tier, authority, usage_note = _classify_source(
                domain=domain, url=url, title=title
            )
            tiered.append(
                SourceAssessment(
                    url=url,
                    title=title,
                    tier=tier,
                    authority_score=authority,
                    proximity_score=_score_proximity(domain, url),
                    timeliness_score=_score_timeliness(title, url),
                    verifiability_score=_score_verifiability(domain, url),
                    relevance_score=0.7,
                    overall_usable=tier in ("A", "B"),
                    usage_note=usage_note,
                )
            )
        return tiered

    # ------------------------------------------------------------------
    # Phase 4: Evidence Chain
    # ------------------------------------------------------------------

    def _phase4_evidence_chain(
        self,
        query: str,
        source_assessments: list[SourceAssessment],
    ) -> list[EvidenceItem]:
        if not source_assessments:
            return []

        # Build rich source summaries with extracted text
        source_lines: list[str] = []
        for s in source_assessments[:15]:
            line = f"[{s.tier}] {s.title}\n  URL: {s.url}"
            for cs in self._collected_sources:
                if cs.get("url") == s.url:
                    text = (cs.get("extracted_text") or cs.get("snippet") or "")[:500]
                    if text.strip():
                        line += f"\n  TEXT: {text.strip()}"
                    break
            source_lines.append(line)

        source_summary = "\n\n".join(source_lines)
        # Cap total chars to avoid overwhelming the LLM
        if len(source_summary) > 6000:
            source_summary = source_summary[:6000] + "\n\n[... truncated]"

        # Try LLM evidence chain
        response = self._call_llm(
            system_prompt=EVIDENCE_CHAIN_PROMPT,
            user_prompt=(
                f"Research query: {query}\n\n"
                f"SOURCES WITH CONTENT:\n{source_summary}\n\n"
                "Construct an evidence chain. For each piece of evidence, "
                "specify the claim, implementation stage, and confidence."
            ),
        )
        data = response.get("json_data", {}) if isinstance(response, dict) else {}
        if isinstance(data, dict) and data.get("evidence_chain"):
            return [
                EvidenceItem(
                    evidence_id=e.get("evidence_id", f"ev{i}"),
                    claim=e.get("claim", ""),
                    source_urls=e.get("source_urls", []),
                    stage=e.get("stage", "policy_statement"),
                    confidence=e.get("confidence", "medium"),
                    counter_evidence=e.get("counter_evidence", ""),
                    verification_status=e.get("verification_status", "unverified"),
                )
                for i, e in enumerate(data["evidence_chain"])
            ]

        # Fallback: build deterministic evidence items from collected sources
        items: list[EvidenceItem] = []
        for i, s in enumerate(source_assessments[:12]):
            if not s.overall_usable:
                continue
            if "细则" in s.title or "措施" in s.title:
                stage = "implementation_rule"
            elif "政策" in s.title or "方案" in s.title or "计划" in s.title:
                stage = "policy_statement"
            else:
                stage = "project_announcement"
            items.append(EvidenceItem(
                evidence_id=f"ev{i+1}",
                claim=s.title[:200],
                source_urls=[s.url],
                stage=stage,
                confidence="medium" if s.tier == "A" else "low",
                verification_status="partially_verified" if s.tier == "A" else "unverified",
            ))
        return items

    # ------------------------------------------------------------------
    # Phase 5: Report Assembly
    # ------------------------------------------------------------------

    def _phase5_report_assembly(
        self,
        *,
        query: str,
        understanding: QueryUnderstanding,
        evidence_items: list[EvidenceItem],
        source_assessments: list[SourceAssessment],
    ) -> DeepResearchReport:
        evidence_summary = "\n".join(
            f"- [{e.stage}|{e.confidence}] {e.claim}" for e in evidence_items[:20]
        )
        response = self._call_llm(
            system_prompt=FINAL_SYNTHESIS_PROMPT,
            user_prompt=(
                f"Research query: {query}\n\n"
                f"Research dimensions:\n"
                + "\n".join(
                    f"- {d.label}: {d.description}" for d in understanding.research_dimensions
                )
                + f"\n\nEvidence collected:\n{evidence_summary}\n\n"
                f"Sources assessed: {len(source_assessments)} total "
                f"({sum(1 for s in source_assessments if s.tier == 'A')} A-tier, "
                f"{sum(1 for s in source_assessments if s.tier == 'B')} B-tier)\n\n"
                "Synthesize into the final research report. "
                "Be explicit about confidence levels and uncertainties."
            ),
        )
        data = response.get("json_data", {}) if isinstance(response, dict) else {}
        if isinstance(data, dict) and data.get("executive_summary"):
            return DeepResearchReport(
                query=query,
                executive_summary=data.get("executive_summary", "No summary available."),
                overall_confidence=data.get("overall_confidence", "medium"),
                key_findings=data.get("key_findings", []),
                key_inferences=data.get("key_inferences", []),
                evidence_chain=evidence_items,
                source_assessments=source_assessments,
                data_gaps=data.get("data_gaps", []),
                uncertainties=data.get("uncertainties", []),
                suggested_followups=data.get("suggested_followups", []),
                search_rounds_executed=len(self._round_log),
                estimated_tavily_credits=self._total_credits,
            )
        return DeepResearchReport(
            query=query,
            executive_summary="Report assembly failed — LLM did not return valid JSON.",
            overall_confidence="low",
            source_assessments=source_assessments,
            evidence_chain=evidence_items,
            search_rounds_executed=len(self._round_log),
            estimated_tavily_credits=self._total_credits,
        )

    # ------------------------------------------------------------------
    # LLM helper
    # ------------------------------------------------------------------

    def _make_client(self) -> Any:
        settings = get_settings()
        try:
            return DeepSeekProviderClient(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model=settings.deepseek_research_model,
                timeout_seconds=settings.deepseek_timeout_seconds,
                max_retries=settings.deepseek_max_retries,
                max_tokens=settings.deepseek_max_tokens,
                store_reasoning_content=settings.deepseek_store_reasoning_content,
            )
        except ProviderConfigError:
            return None

    def _call_llm(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if self._client is None:
            return {"json_data": {}, "content_text": ""}
        try:
            response = self._client.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=None,
                enable_thinking=False,
            )
            return {
                "json_data": response.json_data,
                "content_text": response.content_text,
            }
        except Exception:
            return {"json_data": {}, "content_text": ""}


def deep_research(query: str) -> DeepResearchReport:
    """Convenience entry point."""
    agent = DeepResearchAgent()
    return agent.run(query)


def _domain_from_url(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return parsed.netloc.lower()


def _try_crawl_page(url: str) -> str | None:
    """Try to extract text content from a URL via Crawl4AI."""
    try:
        from packages.sources.crawl4ai_extraction import (
            Crawl4AIExtractionInput,
            Crawl4AIExtractionRequest,
            Crawl4AIExtractionService,
        )
        service = Crawl4AIExtractionService()
        resp = service.extract(
            Crawl4AIExtractionRequest(
                inputs=[Crawl4AIExtractionInput(url=url, source_id="deep_research")]
            )
        )
        texts: list[str] = []
        for doc in resp.normalized_documents:
            for section in doc.sections:
                if section.text.strip():
                    texts.append(section.text.strip()[:800])
        if texts:
            return "\n\n".join(texts[:3])
        for doc in resp.documents:
            if doc.raw_text:
                return doc.raw_text[:1200]
    except Exception:
        pass
    return None


def _estimate_credits_for_response(response: Any) -> int:
    """Estimate Tavily credits from a search response."""
    if hasattr(response, "results"):
        return max(1, len(response.results))
    return 1


def _classify_source(
    *, domain: str, url: str, title: str
) -> tuple[str, float, str]:
    """Classify a source into A/B/C/D tier with nuanced rules.

    A-tier: Official government DOCUMENTS (policy text, regulations, official notices)
    B-tier: Government news/aggregation, public resource platforms, enterprise announcements
    C-tier: Industry associations, research institutes, policy interpretation
    D-tier: Commercial media, self-media, aggregators
    """
    # Procurement/public resource platforms → B
    if any(m in domain for m in ("ggzy", "ccgp", "ggzyjy", "zfcg", "sse.com.cn", "szse.cn")):
        return "B", 0.80, "Public resource/official trading platform"

    # PDF attachments on gov sites → A (policy documents)
    if domain.endswith(".gov.cn") and url.lower().endswith(".pdf"):
        return "A", 0.95, "Official policy document (PDF)"

    # Central government ministries → A
    if domain in {"www.gov.cn", "ndrc.gov.cn", "miit.gov.cn", "most.gov.cn",
                  "mofcom.gov.cn", "stats.gov.cn", "customs.gov.cn"}:
        return "A", 0.98, "Central government ministry — primary source"

    # .gov.cn with policy/content indicators → A
    if domain.endswith(".gov.cn"):
        gov_policy_markers = (
            "/zwgk/", "/zfxxgk/", "/xxgk/", "/gkmlpt/",
            "/content/post_", "/public/", "/tzgg/",
            "content/detail/", "policy", "办法", "措施", "行动计划",
            "实施细则", "通知", "意见", "方案",
        )
        url_lower = url.lower()
        has_policy_marker = any(
            m.lower() in url_lower or m in title
            for m in gov_policy_markers
        )
        if has_policy_marker:
            return "A", 0.90, "Government policy/regulatory document"

        # Government news/portal without policy markers → B
        news_markers = ("/xwzx/", "/zwdt/", "/mtjj/", "/xwfb/", "/news/")
        if any(m in url_lower for m in news_markers):
            return "B", 0.75, "Government news/portal — verify against policy text"
        return "B", 0.70, "Government domain — verify document type"

    # Enterprise announcement platforms → B
    if domain in {"cninfo.com.cn"}:
        return "B", 0.80, "Enterprise announcement platform"

    # Industry associations → C
    if any(m in domain for m in ("caam.org.cn", "caai.cn", "chinapv.org.cn",
                                   "cppcc.gov.cn", "aopa.org.cn")):
        return "C", 0.55, "Industry association — use for context, not primary fact"

    # Default → D
    return "D", 0.30, "Verify against primary source before citing"


def _score_proximity(domain: str, url: str) -> float:
    """Score how close this is to a primary source."""
    if domain.endswith(".gov.cn"):
        return 0.90
    if domain in {"cninfo.com.cn", "sse.com.cn", "szse.cn"}:
        return 0.85
    return 0.50


def _score_timeliness(title: str, url: str) -> float:
    """Score timeliness based on year hints in URL/title."""
    import re
    years = re.findall(r"(20[2-9]\d)", url + title)
    if years:
        latest = max(int(y) for y in years)
        if latest >= 2025:
            return 0.95
        if latest >= 2023:
            return 0.80
        if latest >= 2020:
            return 0.60
    return 0.50


def _score_verifiability(domain: str, url: str) -> float:
    """Score verifiability — does it have document numbers, dates, attachments?"""
    if url.lower().endswith(".pdf"):
        return 0.85
    if domain.endswith(".gov.cn"):
        if any(m in url.lower() for m in ("/content/", "/post_", "/public/", "/detail/")):
            return 0.90
        return 0.70
    return 0.40
