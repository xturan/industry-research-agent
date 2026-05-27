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

    def run(self, query: str, *, persist: bool = True) -> DeepResearchReport:
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

        # Phase 4: Evidence Chain (structured, always runs)
        evidence_items = self._phase4_evidence_chain(query, source_assessments)

        # Phase 4b: Multi-Agent Debate (Thesis→Opponent→Judge→Risk)
        debate = self._phase4b_multi_agent_debate(
            query=query,
            source_assessments=source_assessments,
            evidence_items=evidence_items,
        )

        # Phase 4c: Counter-evidence search
        counter_evidence = self._phase4b_counter_evidence(query, evidence_items)

        # Phase 5: Report Assembly (with debate output)
        report = self._phase5_report_assembly(
            query=query,
            understanding=understanding,
            evidence_items=evidence_items,
            counter_evidence=counter_evidence,
            source_assessments=source_assessments,
            debate=debate,
        )

        # Local ML quality prediction (free, no API call)
        try:
            from packages.agents.local_models import (
                QualityPredictor,
                predict_source_gaps,
            )
            quality = QualityPredictor.from_run_stats(
                total_queries=1,
                gaps=[{"missing_count": len(report.data_gaps)}],
                total_credits=report.estimated_tavily_credits,
            )
            if quality.get("quality") == "fail_likely" and report.overall_confidence != "low":
                report.uncertainties.append(
                    f"[ML预测] 本地模型预测本报告可能未通过质量审计 "
                    f"(置信度: {quality.get('score', 0):.0%})。建议补充搜索或人工复核。"
                )

            # Predict source gaps
            expected_classes = [
                "tender_or_procurement", "project_list", "statistics",
                "regulatory_record", "environmental_or_land_record",
                "company_disclosure", "official_policy",
                "industry_association", "industry_report", "local_government",
            ]
            gap_preds = predict_source_gaps(expected_classes)
            high_risk_gaps = [g for g in gap_preds if g["predicted_missing"] >= 3]
            if high_risk_gaps:
                gap_warning = (
                    "[ML预测] 以下 source class 可能缺失: "
                    + ", ".join(
                        f"{g['source_class']}(预计缺{g['predicted_missing']})"
                        for g in high_risk_gaps[:3]
                    )
                )
                if gap_warning not in report.uncertainties:
                    report.uncertainties.append(gap_warning)
        except Exception:
            pass

        # Auto-persist
        if persist:
            _persist_report(query=query, report=report)

        return report

    # ------------------------------------------------------------------
    # Phase 1: Query Understanding
    # ------------------------------------------------------------------

    def _phase1_query_understanding(self, query: str) -> QueryUnderstanding:
        # Try local Ollama first (free), fall back to DeepSeek
        response = self._try_local_caliber_expansion(query)
        if response and response.get("research_dimensions"):
            return self._parse_understanding(response, query)

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

    def _try_local_caliber_expansion(self, query: str) -> dict[str, Any] | None:
        """Try Ollama for caliber expansion (free, local)."""
        try:
            from packages.providers.ollama_provider import get_ollama
            ollama = get_ollama()
            if not ollama.available:
                return None
            result = ollama.generate_json(
                system_prompt=(
                    "将研究查询分解为3-5个维度，每个维度给出2-4个口径扩展搜索词。"
                    "中文输出。只返回JSON。"
                ),
                user_prompt=(
                    f"查询: {query}\n\n"
                    '返回格式: {"research_dimensions":['
                    '{"dimension_id":"d1","label":"维度名","description":"说明",'
                    '"caliber_terms":["词1","词2"],"source_priority":"government|enterprise|mixed"}]}\n\n'
                    "注意：中国政府的政策口径可能与字面查询不同。例如'人形机器人'在广东政策中称为'具身智能机器人'。"
                ),
            )
            if result.get("json_data") and result["json_data"].get("research_dimensions"):
                return result["json_data"]
        except Exception:
            pass
        return None

    def _parse_understanding(
        self, data: dict[str, Any], query: str
    ) -> QueryUnderstanding:
        """Parse caliber expansion output into QueryUnderstanding."""
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

        # Round 3: Project/implementation evidence (procurement, bidding, projects)
        project_terms: list[str] = []
        for d in understanding.research_dimensions:
            project_terms.extend(d.caliber_terms[:2])
        # Append procurement-specific terms for project-focused search
        project_keywords = [
            "招标公告", "中标公示", "项目备案", "环评公示",
            "采购公告", "公共资源交易",
        ]
        for kw in project_keywords:
            if any(kw in t for t in project_terms):
                continue
            project_terms.append(kw)
        rounds.append(
            SearchRoundPlan(
                round_number=round_num,
                objective="搜索项目落地、招投标、采购公告等实施层证据",
                search_phrases=project_terms[:6] or [understanding.normalized_query],
                include_domains=["gov.cn", "ggzy.gov.cn"],
                target_dimensions=[d.dimension_id for d in understanding.research_dimensions[:4]],
                expected_source_tier="B",
            )
        )
        round_num += 1

        # Round 4: Enterprise announcements and company evidence
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
                    objective="搜索企业公告、上市公司披露和公司官网信息",
                    search_phrases=enterprise_terms[:6] or [understanding.normalized_query],
                    include_domains=["cninfo.com.cn", "sse.com.cn", "szse.cn"],
                    target_dimensions=[d.dimension_id for d in enterprise_dims[:3]],
                    expected_source_tier="B",
                )
            )
            round_num += 1

        # Round 5: Data and statistics
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
                        # Try to extract page content; pass query for BM25 filtering
                        extracted_text = _try_crawl_page(url, query=query)
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

            # Supplementary: enterprise disclosure API for enterprise-targeted rounds
            if "enterprise" in str(round_plan.target_dimensions) or any(
                kw in " ".join(round_plan.search_phrases)
                for kw in ("企业", "公告", "披露", "上市")
            ):
                for phrase in round_plan.search_phrases[:1]:
                    try:
                        disclosure_sources = _try_disclosure_search(phrase)
                        for ds in disclosure_sources:
                            if ds["url"] not in seen_urls:
                                seen_urls.add(ds["url"])
                                round_sources.append(ds)
                    except Exception:
                        pass

            # Stop early if we have enough sources
            if len(self._collected_sources) >= self.max_sources_per_round * 3:
                break

    # ------------------------------------------------------------------
    # Phase 3: Source Tiering
    # ------------------------------------------------------------------

    def _phase3_source_tiering(self) -> list[SourceAssessment]:
        """Classify sources by tier — model-first with rule fallback."""
        from packages.agents.source_tier_model import get_source_tier_model

        tier_model = get_source_tier_model()
        tiered: list[SourceAssessment] = []
        for source in self._collected_sources:
            domain = source.get("domain", "")
            url = source.get("url", "")
            title = source.get("title", "")

            if tier_model is not None:
                prediction = tier_model.classify(
                    domain=domain, url=url, title=title,
                    snippet=source.get("snippet", ""),
                    extracted_text=source.get("extracted_text", ""),
                )
                tier = prediction.tier
                authority = prediction.authority_score
                usage_note = prediction.usage_note
            else:
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
    # Phase 4b: Multi-Agent Debate
    # ------------------------------------------------------------------

    def _phase4b_multi_agent_debate(
        self,
        *,
        query: str,
        source_assessments: list[SourceAssessment],
        evidence_items: list[EvidenceItem],
    ) -> dict[str, Any]:
        """Run multi-agent debate: Thesis Builder → Opponent → Judge → Risk."""
        if self._client is None:
            return {}

        # Build an evidence text blob from collected sources
        evidence_text = _build_evidence_text(source_assessments, self._collected_sources)

        # 1) Thesis Builder
        theses = self._run_thesis_builder(query, evidence_text, evidence_items)
        if not theses:
            return {}

        # 2) Opponent
        objections = self._run_opponent(theses, evidence_text)

        # 3) Evidence Judge
        judge_output = self._run_evidence_judge(theses, objections, evidence_text)

        # 4) Risk Analyst
        risks = self._run_risk_analyst(theses, judge_output, objections)

        return {
            "theses": theses,
            "objections": objections,
            "evidence_judge": judge_output,
            "risks": risks,
        }

    def _run_thesis_builder(
        self, query: str, evidence_text: str, evidence_items: list[EvidenceItem]
    ) -> list[dict[str, Any]]:
        response = self._call_llm(
            use_debate_client=True,
            system_prompt=(
                "Build 3-5 evidence-supported theses. Output JSON: "
                '{"theses":[{"thesis_id":"t1","title":"...",'
                '"stance":"constructive|neutral|cautionary","summary":"...",'
                '"confidence_score":0.5,"support_strength":0.5,"rationale":"..."}]}'
            ),
            user_prompt=(
                f"Query: {query}\n\n"
                f"Evidence:\n{evidence_text[:2500]}\n\n"
                "Build 3-5 theses. Write in Chinese."
            ),
        )
        data = response.get("json_data", {}) if isinstance(response, dict) else {}
        return data.get("theses", []) if isinstance(data, dict) else []

    def _run_opponent(
        self, theses: list[dict[str, Any]], evidence_text: str
    ) -> list[dict[str, Any]]:
        thesis_text = "\n".join(
            f"- [{t.get('thesis_id','?')}] {t.get('title','')}: {t.get('summary','')[:120]}"
            for t in theses
        )
        response = self._call_llm(
            use_debate_client=True,
            system_prompt=(
                "Pressure-test each thesis. Output JSON: "
                '{"objections":[{"thesis_id":"...","objection":"...",'
                '"severity":1-5,"rationale":"..."}]} '
                "(1=minor,3=meaningful,5=seriously undermined)"
            ),
            user_prompt=(
                f"Theses:\n{thesis_text}\n\n"
                f"Evidence:\n{evidence_text[:2000]}\n\n"
                "Challenge each thesis. Write in Chinese."
            ),
        )
        data = response.get("json_data", {}) if isinstance(response, dict) else {}
        return data.get("objections", []) if isinstance(data, dict) else []

    def _run_evidence_judge(
        self,
        theses: list[dict[str, Any]],
        objections: list[dict[str, Any]],
        evidence_text: str,
    ) -> dict[str, Any]:
        thesis_text = "\n".join(
            f"- [{t.get('thesis_id','?')}] {t.get('title','')}" for t in theses
        )
        response = self._call_llm(
            use_debate_client=True,
            system_prompt="""\
Evaluate evidence quality per thesis. Output JSON:
{"coverage":[{"thesis_id":"...","support_score":0.0-1.0,"support_label":"strong|moderate|weak|insufficient","gaps":["..."],"notes":"..."}],"overall_sufficiency_score":0.0-1.0,"overall_label":"strong|moderate|weak|insufficient","global_gaps":["..."]}
""",
            user_prompt=(
                f"Theses:\n{thesis_text}\n"
                f"Objections: {len(objections)}\n\n"
                f"Evidence:\n{evidence_text[:2000]}\n\n"
                "Evaluate. Write in Chinese."
            ),
        )
        data = response.get("json_data", {}) if isinstance(response, dict) else {}
        return data if isinstance(data, dict) else {}

    def _run_risk_analyst(
        self,
        theses: list[dict[str, Any]],
        judge_output: dict[str, Any],
        objections: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        thesis_text = "\n".join(
            f"- [{t.get('thesis_id','?')}] {t.get('title','')}" for t in theses
        )
        response = self._call_llm(
            use_debate_client=True,
            system_prompt="""\
Identify failure conditions for each thesis. Output JSON:
{"risks":[{"thesis_id":"...","risk_title":"...","risk_description":"...","invalidation_condition":"...","severity":1-5}]}
severity: 1=edge case, 3=meaningful, 5=central failure mode.
""",
            user_prompt=(
                f"Theses:\n{thesis_text}\n"
                f"Evidence sufficiency: {judge_output.get('overall_sufficiency_score','?')} "
                f"({judge_output.get('overall_label','?')})\n\n"
                "Identify risks. Write in Chinese."
            ),
        )
        data = response.get("json_data", {}) if isinstance(response, dict) else {}
        return data.get("risks", []) if isinstance(data, dict) else []

    # ------------------------------------------------------------------
    # Phase 4c: Counter-Evidence Search
    # ------------------------------------------------------------------

    def _phase4b_counter_evidence(
        self, query: str, evidence_items: list[EvidenceItem]
    ) -> list[EvidenceItem]:
        """Search for counter-evidence that challenges or qualifies the main evidence."""
        if not evidence_items:
            return []

        # Build opposing search terms
        counter_terms: list[str] = []
        opposition_words = ["风险", "问题", "挑战", "不足", "失败", "取消", "暂停",
                            "质疑", "反对", "批评", "违规", "处罚"]
        for item in evidence_items[:3]:
            claim = item.claim[:60]
            for opp in opposition_words[:3]:
                counter_terms.append(f"{claim} {opp}")
        if not counter_terms:
            return []

        # Search for counter-evidence (limited: 3 Tavily searches)
        from packages.sources.search_discovery import (
            SearchDiscoveryProvider,
            TavilySearchAdapter,
            TavilySearchRequest,
        )
        adapter: SearchDiscoveryProvider = TavilySearchAdapter()
        counter_items: list[EvidenceItem] = []
        seen_urls: set[str] = set()

        for term in counter_terms[:3]:
            try:
                resp = adapter.search(TavilySearchRequest(query=term, max_results=3))
                self._total_credits += max(1, len(resp.results))
                for result in resp.results[:2]:
                    url = result.url.strip()
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    counter_items.append(EvidenceItem(
                        evidence_id=f"ce_{len(counter_items)+1}",
                        claim=f"[反方] {result.title or term}",
                        source_urls=[url],
                        stage="policy_statement",
                        confidence="low",
                        verification_status="unverified",
                    ))
            except Exception:
                continue

        return counter_items

    def _phase5_report_assembly(
        self,
        *,
        query: str,
        understanding: QueryUnderstanding,
        evidence_items: list[EvidenceItem],
        counter_evidence: list[EvidenceItem] | None = None,
        source_assessments: list[SourceAssessment],
        debate: dict[str, Any] | None = None,
    ) -> DeepResearchReport:
        evidence_summary = "\n".join(
            f"- [{e.stage}|{e.confidence}] {e.claim}" for e in evidence_items[:20]
        )
        debate_text = ""
        if debate:
            theses = debate.get("theses", [])
            objections = debate.get("objections", [])
            judge = debate.get("evidence_judge", {})
            risks = debate.get("risks", [])
            debate_text = (
                f"\n\nMulti-Agent Debate Output:\n"
                f"Theses ({len(theses)}):\n"
                + "\n".join(
                    f"- [{t.get('thesis_id','?')}|conf={t.get('confidence_score','?')}] "
                    f"{t.get('title','')}"
                    for t in theses
                )
                + f"\n\nObjections ({len(objections)}):\n"
                + "\n".join(
                    f"- [{o.get('thesis_id','?')}|sev={o.get('severity','?')}] "
                    f"{o.get('objection','')[:120]}"
                    for o in objections
                )
                + f"\n\nEvidence Judge: overall={judge.get('overall_label','?')} "
                f"score={judge.get('overall_sufficiency_score','?')}"
                + f"\n\nRisks ({len(risks)}):\n"
                + "\n".join(
                    f"- [{r.get('thesis_id','?')}|sev={r.get('severity','?')}] "
                    f"{r.get('risk_title','')}"
                    for r in risks
                )
            )
        response = self._call_llm(
            system_prompt=FINAL_SYNTHESIS_PROMPT,
            user_prompt=(
                f"Research query: {query}\n\n"
                f"Research dimensions:\n"
                + "\n".join(
                    f"- {d.label}: {d.description}" for d in understanding.research_dimensions
                )
                + f"\n\nEvidence collected:\n{evidence_summary}"
                + debate_text
                + f"\n\nSources assessed: {len(source_assessments)} total "
                f"({sum(1 for s in source_assessments if s.tier == 'A')} A-tier, "
                f"{sum(1 for s in source_assessments if s.tier == 'B')} B-tier)\n\n"
                "Synthesize into the final research report. "
                "Incorporate the multi-agent debate output. "
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

    def _make_debate_client(self) -> Any:
        """Create a separate client with higher max_tokens for debate outputs."""
        settings = get_settings()
        try:
            return DeepSeekProviderClient(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model=settings.deepseek_research_model,
                timeout_seconds=max(settings.deepseek_timeout_seconds, 300),
                max_retries=0,
                max_tokens=4000,  # Debate JSON needs more tokens
                store_reasoning_content=False,
            )
        except ProviderConfigError:
            return self._client

    def _call_llm(
        self, *, system_prompt: str, user_prompt: str, use_debate_client: bool = False
    ) -> dict[str, Any]:
        client = self._make_debate_client() if use_debate_client else self._client
        if client is None:
            return {"json_data": {}, "content_text": ""}
        try:
            response = client.generate_json(
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


def _persist_report(*, query: str, report: DeepResearchReport) -> None:
    """Persist a Deep Research report to the database."""
    try:
        from packages.db.session import SessionLocal
        from packages.research_reports.schemas import ResearchReportCreate
        from packages.research_reports.service import ResearchReportService

        with SessionLocal() as session:
            service = ResearchReportService(session)
            service.save(ResearchReportCreate(
                query=query,
                report_json=report.model_dump(mode="json"),
                source_count=len(report.source_assessments),
                evidence_count=len(report.evidence_chain),
                overall_confidence=report.overall_confidence,
                search_rounds=report.search_rounds_executed,
                tavily_credits=report.estimated_tavily_credits,
            ))
    except Exception:
        pass  # Non-critical — don't break the pipeline for persistence


def deep_research(query: str) -> DeepResearchReport:
    """Convenience entry point."""
    agent = DeepResearchAgent()
    return agent.run(query)


def _domain_from_url(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return parsed.netloc.lower()


def _build_evidence_text(
    source_assessments: list[Any],
    collected_sources: list[dict[str, Any]],
) -> str:
    """Build a text blob from collected sources for LLM agents."""
    lines: list[str] = []
    for s in source_assessments[:15]:
        title = getattr(s, "title", "")
        tier = getattr(s, "tier", "?")
        url = getattr(s, "url", "")
        text = ""
        for cs in collected_sources:
            if cs.get("url") == url:
                text = (cs.get("extracted_text") or cs.get("snippet") or "")[:500]
                break
        lines.append(f"[{tier}] {title}")
        if text.strip():
            lines.append(f"  {text.strip()[:400]}")
    return "\n".join(lines)


def _try_crawl_page(url: str, *, query: str = "") -> str | None:
    """Extract text from URL. Priority: Tavily Extract → Crawl4AI → PDF download."""
    # Skip binary file types that are handled separately
    if url.lower().endswith((".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar")):
        return None

    # 1) Try Tavily Extract (clean, LLM-optimized, no browser overhead)
    text = _try_tavily_extract(url)
    if text:
        return text

    # 2) Fall back to Crawl4AI for HTML pages
    if not url.lower().endswith(".pdf"):
        text = _try_crawl4ai_extract(url, query=query)
        if text:
            return text

    # 3) PDF extraction
    if url.lower().endswith(".pdf"):
        text = _try_pdf_extract(url)
        if text:
            return text

    return None


def _try_tavily_extract(url: str) -> str | None:
    """Use Tavily Extract API for clean, LLM-optimized content extraction."""
    try:
        from packages.core.config import get_settings
        settings = get_settings()
        api_key = settings.tavily_api_key
        if not api_key:
            return None

        import json as _json
        import urllib.request

        payload = _json.dumps({
            "urls": [url],
            "include_images": False,
            "extract_depth": "basic",
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.tavily.com/extract",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        results = data.get("results", [])
        if results:
            raw = results[0].get("raw_content", "")
            if raw.strip():
                return _clean_extracted_text(raw)[:2000]
    except Exception:
        pass
    return None


def _try_crawl4ai_extract(url: str, *, query: str = "") -> str | None:
    """Fallback: use Crawl4AI for HTML extraction with optional BM25 filtering."""
    try:
        # Try BM25-filtered crawl if query is available
        text = _try_crawl4ai_bm25(url, query)
        if text:
            return text

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
                    texts.append(_clean_extracted_text(section.text.strip())[:800])
        if texts:
            return "\n\n".join(texts[:3])
        for doc in resp.documents:
            if doc.raw_text:
                return _clean_extracted_text(doc.raw_text)[:1200]
    except Exception:
        pass
    return None


def _try_crawl4ai_bm25(url: str, query: str) -> str | None:
    """Use Crawl4AI with BM25 content filtering to get query-relevant content."""
    if not query or not query.strip():
        return None
    try:
        import asyncio

        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
        from crawl4ai.content_filter_strategy import BM25ContentFilter
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

        async def _crawl():
            bm25 = BM25ContentFilter(user_query=query, bm25_threshold=0.8)
            md_gen = DefaultMarkdownGenerator(content_filter=bm25)
            config = CrawlerRunConfig(
                markdown_generator=md_gen,
                page_timeout=30000,
                cache_mode="bypass",
            )
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url, config=config)
                if result and result.markdown:
                    fit = result.markdown.fit_markdown or ""
                    if fit.strip():
                        return _clean_extracted_text(fit.strip())[:2000]
                    raw = result.markdown.raw_markdown or ""
                    if raw.strip():
                        return _clean_extracted_text(raw.strip())[:2000]
            return None

        return asyncio.run(_crawl())
    except Exception:
        return None


def _try_pdf_extract(url: str) -> str | None:
    """Download and extract text from PDF."""
    try:
        from packages.sources.live_pdf import LivePdfDownloadService
        from packages.sources.pdf_text import PdfTextExtractionService

        downloader = LivePdfDownloadService()
        result = downloader.download_pdf(url=url, source_id="deep_research")
        extractor = PdfTextExtractionService()
        extraction = extractor.extract_from_file(
            file_path=result.file_path,
            source_id="deep_research",
            max_pages=8,
        )
        if extraction and extraction.full_text.strip():
            return _clean_extracted_text(extraction.full_text.strip())[:2000]
        if extraction and extraction.pages:
            text = " ".join(
                p.text for p in extraction.pages[:5] if p.text.strip()
            )
            if text.strip():
                return _clean_extracted_text(text.strip())[:2000]
    except Exception:
        pass
    return None


def _clean_extracted_text(text: str) -> str:
    """Remove navigation noise, headers, footers from extracted web content."""
    import re

    # Strip lines that are pure navigation/UI noise
    noise_patterns = [
        r'^\s*[♿⏩🔍🔎📱\U0001F300-\U0001F6FF]*\s*(无障碍|长者|适老|关怀|辅助).*\s*$',
        r'^\s*(简体|繁体|移动版|English|EN|网站地图|关于我们|设为首页|收藏本站|加入收藏).*\s*$',
        r'^\s*(首页|政务公开|新闻中心|互动交流|在线咨询|领导信箱|我要写信).*\s*$',
        r'^\s*[|｜\s]*(搜索|Search|热门搜索).*\s*$',
        r'^\s*©\s*\d{4}.*$',
        r'^\s*(备案|ICP|公安).*\d+号.*$',
        r'^\s*(主办|承办|协办|版权所有|技术支持).*\s*$',
        r'^\s*\[.+\]\s*$',  # Pure bracket labels like [无障碍模式]
        r'^\s*!\[.+\]\(.+\)\s*$',  # Markdown image-only lines
    ]
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if cleaned_lines and cleaned_lines[-1] != '':
                cleaned_lines.append('')
            continue
        if any(re.match(p, stripped) for p in noise_patterns):
            continue
        # Skip lines that are mostly URL fragments / JS calls
        if stripped.startswith('javascript:') or stripped.startswith('#'):
            continue
        cleaned_lines.append(line)

    result = '\n'.join(cleaned_lines)
    # Collapse multiple blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()[:2000]


def _try_disclosure_search(query: str) -> list[dict[str, Any]]:
    """Try CNINFO (巨潮) enterprise disclosure search."""
    try:
        from packages.sources.disclosure_api import CninfoDisclosureApiProvider
        from packages.sources.disclosure_mapping import (
            DisclosureAnnouncementSearchSpec,
            DisclosureEntityCandidate,
        )
        from packages.sources.query_decomposition import (
            GovernanceAxis,
            InfoType,
            LineFamily,
            QueryDecompositionTask,
            RegionalLevel,
        )

        provider = CninfoDisclosureApiProvider()
        task = QueryDecompositionTask(
            task_id="dr_disclosure",
            task_family="enterprise_disclosure",
            tiaokuai_axis=GovernanceAxis.LINE,
            line_family=LineFamily.DISCLOSURE,
            regional_level=RegionalLevel.NATIONAL,
            info_type=InfoType.ANNOUNCEMENT,
            execution_bucket="direct_structured_sources",
            source_cluster="official_disclosure_backbone",
            include_domains=["cninfo.com.cn"],
            search_phrases=[query],
            evidence_goal="Find enterprise announcements",
            fallback_path="skip",
        )
        spec = DisclosureAnnouncementSearchSpec(
            entity_candidates=[DisclosureEntityCandidate(keyword=query)],
            date_start=None,
            date_end=None,
        )
        docs, normalized, errors, _meta = provider.search(
            task=task, spec=spec, max_results=3
        )
        sources: list[dict[str, Any]] = []
        for doc in docs[:3]:
            url = doc.source_uri or ""
            if url:
                sources.append({
                    "url": url,
                    "domain": _domain_from_url(url) if url else "",
                    "title": doc.title or "企业公告",
                    "snippet": (doc.raw_text or "")[:300],
                    "extracted_text": (doc.raw_text or "")[:1200],
                    "score": 0.85,
                    "round": -1,
                })
        for doc in normalized[:3]:
            url = (doc.metadata or {}).get("url", "") if isinstance(doc.metadata, dict) else ""
            if url and not any(s["url"] == url for s in sources):
                sources.append({
                    "url": url,
                    "domain": _domain_from_url(url) if url else "",
                    "title": doc.title or "企业公告",
                    "snippet": doc.summary or "",
                    "extracted_text": (doc.sections[0].text if doc.sections else "")[:1200],
                    "score": 0.85,
                    "round": -1,
                })
        return sources
    except Exception:
        return []


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

    # Check recency before final classification
    timeliness = _score_timeliness(title, url)
    if timeliness < 0.30:
        # Source is very old (>5 years)
        return "D", 0.15, "Severely outdated — exclude from primary evidence"
    if timeliness < 0.40:
        return "C", 0.30, "Outdated (3+ years) — use only for historical context"

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
    """Score timeliness based on year hints in URL/title.
    Sources older than 3 years are heavily penalized."""
    import re
    years = re.findall(r"(20[2-9]\d)", url + title)
    if years:
        latest = max(int(y) for y in years)
        if latest >= 2026:
            return 0.95
        if latest >= 2025:
            return 0.90
        if latest >= 2024:
            return 0.80
        if latest >= 2023:
            return 0.65
        if latest >= 2020:
            return 0.35  # Heavily penalized: 3+ years old
        return 0.15  # Pre-2020: barely usable
    return 0.40  # No year info: assume stale


def _score_verifiability(domain: str, url: str) -> float:
    """Score verifiability — does it have document numbers, dates, attachments?"""
    if url.lower().endswith(".pdf"):
        return 0.85
    if domain.endswith(".gov.cn"):
        if any(m in url.lower() for m in ("/content/", "/post_", "/public/", "/detail/")):
            return 0.90
        return 0.70
    return 0.40
