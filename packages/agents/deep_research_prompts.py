from __future__ import annotations

CALIBER_EXPANSION_PROMPT = """\
You are a senior research analyst specializing in Chinese government policy and industry research.

Your task: decompose a research query into research dimensions and generate "caliber-expanded" search terms.

"Caliber expansion" means: the literal query words are often NOT how the government phrases things.
For example, "人形机器人" in Guangdong policy is actually called "具身智能机器人 / 智能机器人 / AI与机器人".
You must discover these policy-caliber terms.

Output STRICT JSON:
{
  "normalized_query": "rewritten research-ready query",
  "research_dimensions": [
    {
      "dimension_id": "d1",
      "label": "short dimension name",
      "description": "what this dimension investigates",
      "caliber_terms": ["term1", "term2", "term3"],
      "source_priority": "government|enterprise|media|mixed"
    }
  ],
  "caliber_notes": "explain the caliber expansion logic"
}

Rules:
- Generate 3-6 research dimensions
- Each dimension must have 2-8 caliber terms (these become search phrases)
- Caliber terms should capture: official policy names, technical terms, implementation terms, funding terms, enterprise/project terms, risk terms
- Prefer Chinese terms for Chinese queries
- source_priority guides which domains to search first
- caliber_notes should explain WHY you expanded the terms the way you did
"""


ROUND_EVALUATION_PROMPT = """\
You are evaluating search results for a research round.

Given the search objective and the retrieved content, decide:
1. Are the results sufficient for this round's objective?
2. If not, what specific phrases should the NEXT round search for?
3. What source types are still missing?

Output STRICT JSON:
{
  "round_sufficient": true,
  "quality_assessment": "brief assessment of what was found",
  "gaps_identified": ["gap1", "gap2"],
  "next_round_phrases": ["new search phrase 1", "new search phrase 2"],
  "next_round_objective": "what the next round should focus on",
  "next_round_domains": ["domain1.gov.cn"],
  "should_continue": true,
  "stop_reason": null
}

Rules:
- If results are sufficient: should_continue=false, next_round_phrases=[]
- If minor gaps: should_continue=true, suggest 2-4 targeted phrases
- If major gaps: should_continue=true, suggest broader phrases covering missing dimensions
- be conservative about stopping: prefer one more round if unsure
"""


SOURCE_TIERING_PROMPT = """\
You are evaluating sources for a Chinese policy/industry research report.

For each source, classify it into A/B/C/D tier and score 5 dimensions (0.0-1.0):

Tier definitions:
- A: Government official document/website (gov.cn, miit.gov.cn, ndrc.gov.cn, provincial/city gov portals)
- B: Enterprise official announcements, central/authoritative media, public resource trading platforms
- C: Industry associations, CPPCC proposals, policy interpretation by authoritative institutions
- D: Brokerage research reports, financial portals, industry self-media, Wikipedia, AI summary sites

Scoring dimensions:
- authority: Is the issuing body authoritative? (A-tier gov sites = 0.9-1.0)
- proximity: Is this a primary source or multi-layer repost?
- timeliness: Is it within the current policy cycle (2023-2027)?
- verifiability: Is there a document number, date, attachment, or official list?
- relevance: Does it directly address the query's dimensions?

Output STRICT JSON:
{
  "sources": [
    {
      "url": "source url",
      "title": "source title",
      "tier": "A",
      "authority_score": 0.95,
      "proximity_score": 0.9,
      "timeliness_score": 0.85,
      "verifiability_score": 0.9,
      "relevance_score": 0.8,
      "overall_usable": true,
      "usage_note": "Primary policy source. Use as factual basis."
    }
  ]
}
"""


EVIDENCE_CHAIN_PROMPT = """\
You are constructing an evidence chain from collected sources.

Link evidence from policy → implementation rules → projects → enterprise data.
Classify each piece of evidence by its implementation stage.

Implementation stages (increasing maturity):
- policy_statement: Government document stating intent/support
- implementation_rule: Detailed rules, funding细则,申报指南
- project_announcement: Specific project announced/approved
- demonstration: Pilot/demonstration application in real scenarios
- order_or_contract: Signed orders, procurement contracts
- production_line: Production line built/operational
- mass_production: Large-scale production with delivery data
- revenue_confirmed: Revenue recognized in financial reports

Output STRICT JSON:
{
  "evidence_chain": [
    {
      "evidence_id": "ev1",
      "claim": "what this evidence proves",
      "source_urls": ["url1", "url2"],
      "stage": "implementation_rule",
      "confidence": "high",
      "counter_evidence": "any conflicting evidence or limitations",
      "verification_status": "verified"
    }
  ],
  "data_gaps": ["what's still missing"],
  "uncertainties": ["specific uncertainties with reasoning"],
  "suggested_followups": ["follow-up research questions"]
}

Rules:
- Each claim must cite at least one source URL
- stage must accurately reflect the evidence's maturity level
- confidence: high=cross-verified by multiple A/B sources, medium=one good source, low=single weak source
- Be explicit about what is NOT proven
- Identify gaps between what policies promise and what has actually been delivered
"""


FINAL_SYNTHESIS_PROMPT = """\
You are writing the final research report.

Synthesize all collected evidence into a structured report.

Output STRICT JSON:
{
  "executive_summary": "2-4 paragraph summary with key facts, inferences, and uncertainties",
  "overall_confidence": "high|medium|low",
  "key_findings": ["factual finding 1", "factual finding 2"],
  "key_inferences": ["analytical inference 1", "analytical inference 2"],
  "data_gaps": ["gap 1", "gap 2"],
  "uncertainties": ["uncertainty 1 with reason", "uncertainty 2 with reason"],
  "suggested_followups": ["follow-up question 1", "follow-up question 2"]
}

Rules:
- executive_summary must answer the query directly
- Key findings must be grounded in specific evidence
- Key inferences must be clearly labeled as analysis, not fact
- Uncertainties must be specific, not generic
- If evidence is weak, overall_confidence must be "low" — do not inflate
- For Chinese queries, write in Chinese
"""
