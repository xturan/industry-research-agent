# Research Product v1

Status: active_phase1_report_persistence

Created: 2026-05-02

Primary active PLAN: yes

## Objective

Productize the Deep Research Agent: persistent report storage, LLM evidence quality assessment, auto counter-evidence search, HTML report export. Make research results durable, shareable, and intelligence-enhanced.

## Design Direction

```
DeepResearchAgent.run(query)
  → report persisted to DB (new)
  → LLM evidence depth assessment (enhanced Phase 4)
  → auto counter-evidence search (new Phase 4b)
  → JSON + HTML report (new Phase 5)
  → workbench history + comparison
```

## Phase 1: Report Persistence + History API

Status: completed

Tasks:
- Create DB model `ResearchReport` (query, result JSON, tiering, timestamps)
- Create `packages/research_reports/` package with service + schemas
- Create `GET /research-reports` (list) + `GET /research-reports/{id}` (detail) API
- Auto-persist after each DeepResearchAgent.run()
- Add history panel to workbench UI

## Phase 2: LLM Evidence Depth Assessment

Status: pending

Tasks:
- Replace deterministic evidence stage fallback with LLM assessment
- Per-evidence-item: stage classification + confidence + gaps
- Feed extracted content (not just titles) into assessment
- Fall back to deterministic if LLM unavailable

## Phase 3: Auto Counter-Evidence Search

Status: pending

Tasks:
- After Phase 4 evidence chain, run counter-evidence search
- Use negative/opposing terms to search for disconfirming evidence
- Add to report as counter_evidence_chain
- Enhance uncertainty documentation

## Phase 4: HTML Report Export

Status: pending

Tasks:
- Jinja2 template for HTML research report
- Render: executive summary, source table, evidence chain, tiering, gaps
- `GET /research-reports/{id}/html` endpoint
- Workbench download button

## Continue Rule (ENFORCED)

Continue through all phases. Stop only for: protected contract change, repeated validation failure, or external dependency issue.

## Progress

- 2026-05-02: PLAN created. Phase 1 starting.
