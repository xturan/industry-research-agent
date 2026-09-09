# Source Query Decomposition Rules

Status: draft
Owner: codex/human
Created: 2026-04-26
Applies to: `domestic-source-lite-refactor-v1`

## Purpose

This document teaches an LLM how to decompose a user research query into high-quality source search tasks while preserving the project's 条块 source design.

The decomposer does not answer the user. It produces auditable search tasks for later Tavily discovery, Crawl4AI extraction, direct structured adapters, and evidence bundle generation.

## Core Principle

Every decomposition must preserve the distinction between:

- `条`: national or vertical policy, disclosure, industry, and cross-domain lines.
- `块`: province, city, region, park, and local implementation layers.
- `条块结合`: questions that need both vertical policy context and local implementation evidence.

The decomposer should never collapse a research query into one generic search string when the question requires multiple source families.

## Allowed Tiaokuai Fields

Use only the existing conceptual fields unless a later PLAN authorizes schema changes.

Allowed axis values:
- `line`
- `block`
- `mixed`

Allowed line families:
- `policy`
- `exchange`
- `industry`
- `cross_domain`

Allowed regional levels:
- `national`
- `provincial`
- `municipal`
- `cross_region`

Allowed info types:
- `policy_notice`
- `regulatory_announcement`
- `industry_report`
- `industry_notice`
- `project_transaction`

Allowed execution buckets:
- `search_assisted_sources`
- `direct_structured_sources`
- `placeholder_or_manual_sources`

## Decomposition Output Shape

The LLM should produce a JSON-like object with this shape. This is a planning contract, not yet a production schema.

```json
{
  "original_query": "",
  "normalized_theme": "",
  "regional_focus": [],
  "time_horizon": "",
  "user_intent": "",
  "decomposition_tasks": [
    {
      "task_id": "",
      "task_family": "",
      "tiaokuai_axis": "",
      "line_family": "",
      "regional_level": "",
      "info_type": "",
      "execution_bucket": "",
      "source_cluster": "",
      "source_strategy_hint": "",
      "include_domains": [],
      "exclude_domains": [],
      "search_phrases": [],
      "exact_phrases": [],
      "negative_terms": [],
      "evidence_goal": "",
      "fallback_path": "",
      "priority": 0,
      "confidence": 0.0
    }
  ],
  "unsupported_or_missing_sources": [],
  "notes": []
}
```

## Required Task Families

Use these task families when relevant. Do not force every query into every family.

| Task family | Axis | Default bucket | Evidence goal |
|---|---|---|---|
| `policy_direction` | `line` | `search_assisted_sources` | National policy direction, ministry guidance, planning language. |
| `local_rollout` | `block` | `search_assisted_sources` | Province/city/park implementation, local support policies, pilots. |
| `project_transaction` | `mixed` | `direct_structured_sources` | Procurement, public resource trading, project approval, construction signals. |
| `enterprise_disclosure` | `line` or `mixed` | `direct_structured_sources` | Listed-company announcements, exchange filings, official IR supplements. |
| `industry_topic` | `line` | `search_assisted_sources` | Associations, white papers, forums, topical platforms, expert/industry signals. |
| `data_metrics` | `line` or `block` | `direct_structured_sources` | Statistics, indicators, market size, trade, production, price data. |

## Search Phrase Quality Rules

Each search phrase must:

- Include the normalized theme.
- Include region terms when the task is block or mixed.
- Include intent terms such as `政策`, `规划`, `试点`, `项目`, `招标`, `公告`, `白皮书`, `产业链`, `前景`, or `趋势` when relevant.
- Stay short enough for search, usually 4 to 10 meaningful Chinese tokens.
- Avoid vague standalone phrases like `发展前景`, `行业分析`, or `政策有哪些`.
- Avoid mixing too many task intents into one phrase.
- Prefer Chinese official terminology over casual wording.
- Produce no more than 3 search phrases per task by default.

Use domain constraints through `include_domains` instead of stuffing many `site:` terms into the query, unless a later implementation specifically chooses the `site:` pattern.

## Direct Source Preservation Rules

The decomposer must not route these as pure Tavily search tasks:

- Exchange and disclosure sources: SSE, SZSE, BSE, NEEQ, CNINFO, bond disclosure, CSRC disclosure.
- Structured data sources: NBS, customs, energy indicators, price monitoring, provincial statistics.
- Query platforms: government procurement, public resource trading, investment project approval.
- Credit/GSXT/judicial sources unless a later PLAN authorizes a special path.

For these sources, Tavily can only be marked as `supplement` or `fallback`, not the primary path.

## LLM Guardrails

The LLM must:

- Not invent report IDs.
- Not invent direct adapter availability.
- Not claim a source has been searched or crawled.
- Not generate investment advice.
- Not produce conclusions; only produce search tasks.
- Mark missing source coverage explicitly in `unsupported_or_missing_sources`.
- Use low confidence when a query requires source families not present in the taxonomy.

Deterministic validation should reject or repair:

- unsupported `tiaokuai_axis`
- unsupported `line_family`
- unsupported `execution_bucket`
- missing theme
- missing region for block tasks
- more than 3 search phrases per task
- direct-keep sources routed as pure `search_assisted_sources`
- domains that are not on an allowlist or profile-derived list

## Example: Anhui Low-Altitude Economy

Original query:

```text
安徽的低空经济未来前景如何
```

Expected normalized fields:

```json
{
  "normalized_theme": "低空经济",
  "regional_focus": ["安徽"],
  "time_horizon": "future_outlook",
  "user_intent": "assess regional industry outlook with evidence"
}
```

Expected decomposition tasks:

```json
[
  {
    "task_id": "policy_direction_1",
    "task_family": "policy_direction",
    "tiaokuai_axis": "line",
    "line_family": "policy",
    "regional_level": "national",
    "info_type": "policy_notice",
    "execution_bucket": "search_assisted_sources",
    "source_cluster": "central_policy_backbone",
    "source_strategy_hint": "cn_policy_first_v2",
    "include_domains": ["gov.cn", "ndrc.gov.cn", "miit.gov.cn"],
    "search_phrases": [
      "低空经济 政策 规划",
      "低空经济 发展 指导意见",
      "低空经济 试点 示范 政策"
    ],
    "evidence_goal": "Find national policy framing and official direction.",
    "fallback_path": "Use policy direct profiles where available.",
    "priority": 90,
    "confidence": 0.85
  },
  {
    "task_id": "local_rollout_anhui_1",
    "task_family": "local_rollout",
    "tiaokuai_axis": "block",
    "line_family": "policy",
    "regional_level": "provincial",
    "info_type": "policy_notice",
    "execution_bucket": "search_assisted_sources",
    "source_cluster": "province_backbone",
    "source_strategy_hint": "cn_local_rollout_v2",
    "include_domains": ["ah.gov.cn", "fzggw.ah.gov.cn"],
    "search_phrases": [
      "安徽 低空经济 政策 规划",
      "安徽 低空经济 试点 项目",
      "安徽 低空经济 产业 发展"
    ],
    "evidence_goal": "Find Anhui local policy, rollout, and implementation signals.",
    "fallback_path": "Use Anhui DRC profile if live fetch is healthy; otherwise keep Tavily URL candidates.",
    "priority": 100,
    "confidence": 0.9
  },
  {
    "task_id": "project_transaction_anhui_1",
    "task_family": "project_transaction",
    "tiaokuai_axis": "mixed",
    "line_family": "cross_domain",
    "regional_level": "provincial",
    "info_type": "project_transaction",
    "execution_bucket": "direct_structured_sources",
    "source_cluster": "project_transaction_backbone",
    "source_strategy_hint": "cn_project_signal",
    "include_domains": ["ccgp.gov.cn", "ggzy.gov.cn"],
    "search_phrases": [
      "安徽 低空经济 招标 中标",
      "安徽 无人机 通航 项目",
      "安徽 低空经济 基础设施 项目"
    ],
    "evidence_goal": "Find project and transaction signals that indicate real implementation.",
    "fallback_path": "Use Tavily only as supplement; direct query platform path remains primary.",
    "priority": 80,
    "confidence": 0.75
  },
  {
    "task_id": "enterprise_disclosure_1",
    "task_family": "enterprise_disclosure",
    "tiaokuai_axis": "mixed",
    "line_family": "exchange",
    "regional_level": "cross_region",
    "info_type": "regulatory_announcement",
    "execution_bucket": "direct_structured_sources",
    "source_cluster": "official_disclosure_backbone",
    "source_strategy_hint": "cn_disclosure_first_v2",
    "include_domains": ["cninfo.com.cn", "sse.com.cn", "szse.cn"],
    "search_phrases": [
      "低空经济 上市公司 公告 安徽",
      "无人机 通航 低空经济 公告",
      "eVTOL 低空经济 上市公司"
    ],
    "evidence_goal": "Find company-side disclosed business signals and avoid relying only on policy language.",
    "fallback_path": "Direct disclosure adapter first; Tavily only for IR or supplement discovery.",
    "priority": 70,
    "confidence": 0.7
  },
  {
    "task_id": "industry_topic_1",
    "task_family": "industry_topic",
    "tiaokuai_axis": "line",
    "line_family": "industry",
    "regional_level": "national",
    "info_type": "industry_report",
    "execution_bucket": "search_assisted_sources",
    "source_cluster": "association_enhancement",
    "source_strategy_hint": "cn_industry_signal_v2",
    "include_domains": [],
    "search_phrases": [
      "低空经济 白皮书 产业链",
      "低空经济 协会 报告",
      "低空经济 发展趋势 无人机 通航"
    ],
    "evidence_goal": "Find supplementary industry interpretation and trend signals.",
    "fallback_path": "Use association/topic sources as supplemental evidence only.",
    "priority": 60,
    "confidence": 0.65
  }
]
```

Missing-source note:

```json
{
  "unsupported_or_missing_sources": [
    "Aviation-specific regulator/source family may be needed for low-altitude economy topics if not covered by existing C01-C46 mappings."
  ]
}
```

## Prompt Template Skeleton

Use this as the first implementation prompt skeleton for the LLM decomposer.

```text
You are decomposing a research query for a source-driven industry intelligence system.

Rules:
- Do not answer the query.
- Produce search tasks only.
- Preserve 条/块/条块结合.
- Use only allowed axis, line_family, regional_level, info_type, and execution_bucket values.
- Keep direct structured sources direct.
- Produce at most 3 search phrases per task.
- Mark missing source coverage explicitly.

Input:
{query}

Known source taxonomy:
{source_taxonomy_summary}

Allowed domains by source cluster:
{domain_allowlist}

Return JSON matching the documented decomposition output shape.
```

## Review Checklist

Before a decomposition can trigger Tavily:

- The theme is normalized.
- Regional focus is extracted when present.
- At least one task has a clear evidence goal.
- Direct-keep sources are not converted to Tavily-only mode.
- Search phrases are not duplicates.
- `include_domains` is empty only when the source cluster is intentionally open discovery.
- Missing source coverage is explicitly stated.

