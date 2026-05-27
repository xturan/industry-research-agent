# Unified Research Pipeline v1

Status: completed

Created: 2026-05-02

Primary active PLAN: yes

## Objective

Unify `/research/analyze` and `/deep-research/analyze` into a single layered pipeline: quick/standard/deep modes driving the same Deep Research engine with configurable depth.

## Design

```
POST /research/analyze
  mode: "quick" | "standard" | "deep"
  ↓
UnifiedResearchRunner
  ↓
DeepResearchAgent.run(query, max_rounds=mode_to_rounds[mode])
  ↓
DeepResearchReport (unified output)
```

| mode | rounds | description |
|------|------|------|
| quick | 2 | Fast overview, <10 credits |
| standard | 3 | Balanced depth, ~15 credits |
| deep | 5 | Full deep research, ~25 credits + counter-evidence |

## Phase 1: Add mode routing

Status: in_progress

## Phase 2: Deprecation path

Status: pending
