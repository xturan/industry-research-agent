# Deep Research Agent v1

Status: completed

Created: 2026-05-01

Primary active PLAN: yes

## Objective

Build a Deep Research Agent that mimics GPT Deep Research methodology: LLM-driven multi-round iterative search, source tiering, evidence chain construction, and cross-verified report assembly — all for Chinese government/industry research queries.

## Design Direction

Mimic GPT Deep Research's 6-step cycle:

```
Query → Caliber Expansion → Multi-Round Search → Source Tiering → Evidence Chain → Report
```

Key insight from GPT DR: "人形机器人" is NOT the right search term for Guangdong policy — the actual policy caliber uses "具身智能机器人 / 智能机器人 / AI与机器人". The agent must discover these caliber expansions, not just enumerate keywords.

## Architecture

```
DeepResearchAgent
  │
  ├─ Phase 1: Query Understanding (1 LLM call)
  │   - Decompose query into research dimensions
  │   - Generate caliber-expanded search terms per dimension
  │   - Define round plan: what to search, in what order
  │
  ├─ Phase 2: Multi-Round Search (3-6 rounds × Tavily + 1 LLM/round)
  │   Each round:
  │     1. Execute Tavily search with round-specific phrases
  │     2. Crawl top results via Crawl4AI
  │     3. LLM evaluates: are results sufficient? what to search next?
  │     4. If gap found → next round with adjusted phrases
  │     5. If sufficient → stop
  │
  ├─ Phase 3: Source Tiering (1 LLM call)
  │   - Classify each source: A/B/C/D
  │   - Score 5 dimensions: authority, proximity, timeliness, verifiability, relevance
  │   - Mark uncertain sources
  │
  ├─ Phase 4: Evidence Chain Construction (1 LLM call)
  │   - Link: policy → implementation detail → project → enterprise
  │   - Stage classification: 发布/示范/订单/产线/量产
  │   - Identify evidence gaps
  │
  └─ Phase 5: Report Assembly (1 LLM call)
      - Executive summary with explicit confidence
      - Structured tables (policy, project, risk)
      - Uncertainty documentation
      - Source list with tier annotations
```

## Modules

### `packages/agents/deep_research.py`
Main orchestrator: `DeepResearchAgent.run(query) → DeepResearchReport`

### `packages/agents/deep_research_schemas.py`
Data models: ResearchDimension, SearchRound, SourceAssessment, EvidenceChain, DeepResearchReport

### `packages/agents/deep_research_prompts.py`
LLM prompts for each phase: caliber expansion, round evaluation, source tiering, evidence chain, report assembly

## Continue Rule (ENFORCED)

Continue through all phases without stopping. Stop only for: protected contract change, repeated validation failure, or external dependency issue.

## Validation

```powershell
ruff check packages/agents/deep_research*.py
pytest tests/test_deep_research_agent.py -v
```

## Progress

- 2026-05-01: PLAN created. Phase 1 starting.

## Next Action

Implement Phase 1: Query Understanding with caliber expansion.
