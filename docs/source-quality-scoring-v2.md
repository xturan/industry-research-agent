# Source Quality Scoring v2 Design Notes

Status: draft

Last updated: 2026-06-09

Implementation plan: `.agent/PLANS/source-quality-scoring-v2.md`

## Purpose

This note clarifies how source quality scoring should evolve after the V1
five-score design showed overlapping dimensions.

The goal is not to replace the existing A/B/C/D source tier immediately. The
goal is to stop treating mixed concepts as equal numeric dimensions and to make
future dossier fields understandable.

## Main Conclusion

Keep A/B/C/D as the source admission tier.

Do not put full evidence judgment into source scoring.

Use two separate layers:

1. Source layer: decide whether a source is credible and potentially useful.
2. Evidence layer: decide whether a specific source actually supports a
   specific claim.

This separation avoids duplicating the later Evidence Judge pipeline.

## Why The Old Five Scores Are Problematic

Current fields:

- `authority_score`
- `proximity_score`
- `timeliness_score`
- `verifiability_score`
- `relevance_score`

Problems:

- `authority_score`, `proximity_score`, and `verifiability_score` all reward
  official `.gov.cn` style sources, so official-domain evidence is counted
  multiple times.
- `tier` and `authority_score` are not independent; the tier is already mostly
  derived from authority and source type.
- `relevance_score` is currently hardcoded in the Deep Research path, so it is
  not a real measurement.
- A plain average makes weak dimensions look acceptable. For credibility, the
  weakest critical dimension often matters more than the mean.

## Where Relevance Should Be Judged

Relevance should not be a single vague score.

Split it into:

- `query_relevance`: source-level match to the user's query or search intent.
- `claim_support_strength`: evidence-level support for a specific claim.

`query_relevance` can be computed in Phase 3 because the source, query, title,
snippet, and extracted text are already available.

`claim_support_strength` should be computed in Phase 4 because the concrete
claim does not exist until evidence items are created.

## Should Relevance Use An LLM?

Default answer: not always.

Recommended decision path:

1. Use deterministic scoring first:
   - `query phrase match`: checks whether the user's query terms or expanded
     query terms appear in the source text. It is used as a cheap first signal
     that the source is about the same topic.
   - `title/snippet match`: checks whether the search result title and summary
     mention the query intent. It is used before full page extraction is
     available.
   - `extracted text match`: checks whether the crawled page text or PDF text
     contains the relevant terms. It is stronger than title/snippet match
     because it inspects the source body.
   - `source family match`: checks whether the source type matches the evidence
     need, such as policy, procurement, statistics, disclosure, project record,
     or regulatory record.
   - `search phrase that discovered the source`: records which expanded search
     phrase found the source. It helps explain whether the source came from a
     high-intent query such as procurement or only from a broad background
     query.
2. Use embeddings or local text similarity when available.
3. Use an LLM only for borderline or high-value cases where deterministic
   signals disagree.

When an LLM is used, record the prompt, visible output, parsed JSON, evaluator
mode, and reason in the run dossier trace.

## Avoiding Evidence Judge Duplication

The source layer should not answer:

> Does this source prove the final claim?

That is Evidence Judge territory.

The source layer may answer:

> Is this source credible, auditable, fresh, and related enough to enter the
> evidence pipeline?

The evidence layer then answers:

> Does this source support this specific claim, and how strongly?

Example:

An NDRC policy page can be highly credible and relevant to low-altitude economy
policy. It may strongly support a claim about policy direction, but it should
not strongly support a claim about procurement orders unless the page contains
procurement evidence.

## Proposed Field Placement

### SourceAssessment Layer

Fields that can be judged before concrete evidence claims exist:

- `tier`
- `source_credibility`
- `query_relevance`
- `source_role`
- `usage_role`

### EvidenceItem Layer

Fields that require a concrete claim:

- `claim_support_strength`
- `evidence_granularity`
- `support_type`
- `limitations`

## Term Glossary

### `tier`

A/B/C/D source class.

Use this as a coarse source admission gate.

Example:

- A: official policy original, official PDF, formal government document
- B: official but indirect, public resource platform, exchange disclosure
- C: association, think tank, research context
- D: commercial media, self-media, aggregator, stale or weak source

### `publisher_authority`

How authoritative the publisher is.

This is about who published the source, not whether the source proves the
current claim.

Examples:

- Central ministry: high
- Local government: high or medium-high
- Public resource trading platform: medium-high
- Commercial media: low to medium

### `source_role`

What role the source plays.

This replaces the old vague idea of proximity.

Suggested values:

- `official_policy_original`
- `official_notice_or_rule`
- `public_resource_transaction`
- `company_disclosure`
- `official_news_or_interpretation`
- `statistics_or_data_release`
- `industry_association_context`
- `research_or_think_tank_context`
- `commercial_media_context`
- `aggregator_or_unknown`

### `auditability`

How easy it is to verify and cite the source.

This replaces the old `verifiability_score` name.

Signals:

- stable URL
- formal document page
- publication date
- document number
- PDF or attachment
- publisher identity
- original page rather than repost

### `freshness`

How current the source is for the user's research task.

This should consider dates in title, URL, page metadata, and document text.

Freshness is not always "newer is better". Some laws or formal rules remain
valid for years. Future implementation should distinguish publication date from
effective validity when possible.

### `credibility_score`

Derived source credibility score.

This should not be a simple average of all dimensions.

Recommended logic:

- apply hard gates first
- penalize weak auditability or stale sources
- use the weakest critical dimension when it creates citation risk
- keep the score explainable through `usage_note`

### `query_relevance`

How well the source matches the user's query or search intent.

This belongs to the source layer because it can be estimated before evidence
claims are generated.

Possible deterministic signals:

- query terms in title
- query terms in snippet
- query terms in extracted text
- source discovered by a high-intent search phrase
- source family matches the query obligation, such as procurement, policy,
  statistics, disclosure, or project record

Use an LLM only when these signals conflict or the case is high value.

### `claim_support_strength`

How strongly a source supports a specific claim.

This belongs to the evidence layer, not the source layer.

Example:

The same government source may have:

- high support for "local policy exists"
- low support for "procurement contract has been awarded"

### `evidence_granularity`

The level of real-world specificity of an evidence item.

This is close to the existing `EvidenceItem.stage`, but should be described
clearly in reports and dossiers.

Suggested values:

- `policy_statement`
- `implementation_rule`
- `project_announcement`
- `public_procurement`
- `winning_bid`
- `production_line`
- `mass_production`
- `revenue_confirmed`
- `statistical_data`
- `regulatory_record`

### `support_type`

The relationship between evidence and claim.

Suggested values:

- `direct`: source directly states the claim
- `indirect`: source supports an inference, but does not state the claim
- `background`: source provides context only
- `counter_evidence`: source weakens or challenges the claim

### `fitness_score`

Avoid using this as a source-level field for now.

If needed later, it should be derived at the evidence layer from:

- `query_relevance`
- `claim_support_strength`
- `evidence_granularity`
- `support_type`

Do not use `fitness_score` as a vague replacement for evidence judgment.

### `usage_role`

How the system is allowed to use the source.

Suggested values:

- `primary_evidence_candidate`
- `supporting_evidence_candidate`
- `context_only`
- `counter_evidence_candidate`
- `exclude_from_primary_evidence`

### `not_sufficient_for`

A list of claims or evidence needs that this source cannot satisfy.

Example:

An official policy page may be sufficient for policy direction but not
sufficient for:

- procurement award evidence
- company revenue confirmation
- production capacity confirmation

## Recommended Implementation Direction

Phase 1:

- Keep old five fields for compatibility.
- Mark the old five-field average as legacy display only.
- Add source-level `source_credibility`, `source_role`, `query_relevance`, and
  `usage_role` internally or in dossier context first.
- Do not change `/deep-research/analyze` response shape yet.

### Phase 1 Runtime Placement

Phase 1 stores Source Quality v2 as shadow context, not as public schema:

- `source_quality_v2_by_url`: Deep Research run context field. It is a map from
  source URL to the v2 quality record, used by the dossier renderer and trace
  review. It should not appear in `/deep-research/analyze` response JSON.
- `published_date`: search-candidate metadata copied from Tavily when available.
  It is the first freshness date signal, but it is not treated as final proof.
- `discovered_by_phrase`: search-candidate metadata showing which expanded
  search phrase found the source. It explains whether a source came from a
  high-intent phrase such as procurement/statistics/policy, or from a broad
  background phrase.
- `round_objective`: search-candidate metadata showing the objective of the
  search round that produced the source. It helps audit why the source was
  searched in that round.
- `source_quality_v2_mode`: trace metadata. In Phase 1 the value is
  `deterministic_shadow`, meaning the record was produced by rules and is used
  for observability, not as a public contract.

### Phase 1 Field Interpretation

- `source_role`: belongs to the source layer. It answers "what kind of source is
  this?" such as official policy, public-resource transaction, company
  disclosure, official statistics, association context, or commercial context.
- `publisher_authority`: belongs to the source layer. It scores the publisher's
  authority; it does not say whether the source proves a later claim.
- `auditability`: belongs to the source layer. It scores whether the source is
  easy to verify through stable URL, date, document number, PDF/attachment, and
  publisher identity.
- `freshness`: belongs to the source layer. It records the date signal and
  timeliness label. For formal policies, older dates may become
  `needs_validity_check` instead of automatic exclusion.
- `query_relevance`: belongs to the source layer. It estimates whether the
  source matches the original query or expanded search intent before claim-level
  evidence judging starts.
- `usage_role`: belongs to the source layer. It tells the pipeline whether the
  source may be used as primary evidence candidate, supporting evidence,
  context-only material, or excluded from primary evidence.
- `not_sufficient_for`: belongs to the source layer. It lists evidence needs the
  source cannot satisfy, such as winning-bid proof, revenue confirmation, or
  production capacity confirmation.

### Phase 1 Live-Tuning Rule

When the query or discovered search phrase has a specific source-family intent,
such as procurement, statistics, disclosure, or regulatory evidence, a source
whose `source_family_match` is false must not become a primary evidence
candidate only because it shares broad topic words.

Example:

- Query asks for procurement or winning-bid evidence.
- A policy source is still useful for policy background.
- It should be `supporting_evidence_candidate`, not
  `primary_evidence_candidate`, and `not_sufficient_for` should include
  `winning bid evidence`.

Phase 2:

- Add evidence-level `claim_support_strength`, `support_type`, and
  `limitations`.
- Let Evidence Judge consume source credibility plus source text when assigning
  claim support.

Phase 3:

- Consider schema migration only after downstream users no longer depend on the
  old five fields.

## Rule For Future Dossier Keywords

Any new scoring keyword shown in a dossier must have a glossary entry in this
document or its successor.

Do not introduce unexplained fields such as `query_relevance`,
`claim_support_strength`, `evidence_granularity`, or `fitness_score` without
explaining what object they belong to and how they should be interpreted.
