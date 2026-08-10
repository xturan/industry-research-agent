# Deep Research Report Rubric v1

Status: active_reference_rubric

Created: 2026-06-15

Parent PLAN:

- `.agent/PLANS/deep-research-report-productization-v1.md`

## Purpose

This rubric defines what counts as a production-worthy Deep Research report for
the LangGraph path.

It is derived from the reference reports:

- `E:/Edge_download/deep-research-report.md`
- `E:/Edge_download/deep-research-report (1).md`
- `E:/Edge_download/deep-research-report (2).md`

This rubric evaluates the final user-facing Markdown artifact, not only its
audit sidecar.

## Design Principle

The final report must satisfy two layers at the same time:

1. `Readable delivery layer`
   也就是用户真正阅读的最终报告正文。它必须像成熟研究报告，而不是像结构化数据导出。
2. `Auditable evidence layer`
   也就是 claims、evidence、tool traces、review issues、dossier 等可追踪层。它负责支撑复核，但不应覆盖正文可读性。

If these two layers conflict, the system must not solve the conflict by
degrading the delivery layer into schema-shaped text.

## Golden Report Contract

A passing report should normally be:

- Chinese Markdown
- materially readable without opening `response.json`
- long-form rather than one-screen summary
- evidence-grounded rather than purely rhetorical
- structured by research dimensions rather than by internal pipeline stages

Target length guidance:

- usually at least `8,000+` Chinese characters for medium research cases
- often `10,000-20,000` Chinese characters for full cases
- shorter reports are allowed only when the query scope is genuinely narrow and
  the report still satisfies all functional sections

## Required Sections

Not every report must use identical headings, but every report must provide the
following functions.

### 1. Title

Must:

- clearly state the research object
- indicate scope or angle when relevant

Good examples:

- region + industry + policy landing
- policy impact + time window + industry chain stage
- city/county + resource/industry expansion space assessment

### 2. Executive Summary

Purpose:

- give the reader the answer first
- summarize the key findings, constraints, and overall judgment

Must include:

- the top conclusions
- the most important supporting logic
- the biggest constraint or uncertainty
- where appropriate, a direct bottom-line judgment

Fail conditions:

- only repeating the query
- only listing claims without synthesis
- no uncertainty or caveat at all

### 3. Method And Scope

Purpose:

- explain what evidence families were used
- explain time range, region scope, and interpretive boundaries

Must include where relevant:

- source families used
- time window
- region/entity scope
- what was treated as fact
- what was treated as inference
- what remains unverified

Fail conditions:

- no explanation of method or evidence basis
- hiding uncertainty behind strong prose

### 4. Dimension-Driven Body Sections

Purpose:

- organize the report around research dimensions instead of internal pipeline nodes

Typical dimensions:

- 政策维度
- 披露维度
- 地方维度
- 项目/招采维度
- 产业链维度
- 统计/验证维度
- 风险与不确定性维度

Must:

- have clear section intent
- answer a specific research question
- not duplicate the previous section in slightly different wording

Fail conditions:

- sections are merely “Claim 1 / Claim 2 / Claim 3”
- sections are organized around system internals like planner/evidence/editor

### 5. Evidence Presentation

Purpose:

- make evidence legible and inspectable inside the report

Acceptable forms:

- short evidence tables
- comparison tables
- bullet evidence chains
- embedded source notes
- timeline blocks

Must:

- show why the cited evidence matters
- distinguish direct evidence from background evidence
- avoid flooding the reader with raw excerpts

Fail conditions:

- evidence shown only as IDs
- a large block of unprocessed snippets
- support scores with no interpretation

### 6. Risk / Uncertainty / Blocker Section

Purpose:

- explicitly surface what the report cannot fully prove

Must:

- state unresolved questions
- state evidence weakness or missing dimensions
- distinguish between “not found” and “not yet verified”

Fail conditions:

- pretending certainty where evidence is weak
- burying uncertainty only inside audit JSON

### 7. Conclusion And Next-Step Research

Purpose:

- close the report with usable synthesis

Must:

- restate the practical conclusion
- identify what should be investigated next if certainty is insufficient

Fail conditions:

- abrupt ending after the last evidence section
- no closing judgment

## Optional But High-Value Elements

These are not mandatory in every case, but strong reports should use them when
they improve understanding.

### Tables

Use when:

- comparing regions, companies, projects, policy clauses, or time periods

Why:

- a table compresses repeated prose and improves scanability

### Timeline

Use when:

- the query depends on chronology, policy sequence, or project progression

Why:

- without a timeline, causal interpretation becomes muddy

### Mermaid Diagram

Use when:

- a relationship, sequence, or dependency is easier to see graphically

Why:

- for policy-to-industry-chain, approval flow, or evidence chain structures,
  diagrams reduce cognitive load

Do not use:

- as decorative output
- when the same point is clearer in prose or table form

## Evidence And Claim Quality Requirements

### Evidence Quality

A passing report should reflect evidence with these properties:

- evidence may synthesize multiple sources or chunks
- evidence should define scope: time, location, entity, and proposition
- evidence should note what it supports and what it does not prove
- evidence should surface contradiction or ambiguity when present

Fail conditions:

- one source auto-becomes one evidence with no synthesis
- all evidence scores look flattened and semantically interchangeable

### Claim Quality

A passing report should reflect claims with these properties:

- more than one claim when the query has multiple dimensions
- claims should map to report logic, not only to source-family obligations
- claims should be distinguishable by type where relevant:
  - factual claim
  - interpretive claim
  - risk claim
  - uncertainty / pending-validation claim

Fail conditions:

- one coarse claim drives the whole report
- claims are too generic to structure a full report

## Human Review Visibility Requirements

If `HUMAN_REVIEW` is triggered, the user-facing flow must clearly show:

- why human review was triggered
- what blocking issues exist
- what actions are available:
  - approve
  - add evidence
  - rewrite
  - reject
- what draft/report snapshot is being reviewed

Fail conditions:

- human review exists only in persisted JSON
- final report appears without making the review tradeoff visible

## Scoring Rubric

Use the following 0-5 scoring bands for review. A production-ready report
should usually achieve at least `4` in every critical dimension and at least
`32/40` overall.

Critical dimensions:

1. `Question framing`
   Does the report clearly define what is being answered?
2. `Executive summary quality`
   Does the summary give the answer, not just the topic?
3. `Dimension coverage`
   Are the major research dimensions present and explicit?
4. `Evidence legibility`
   Can the reader understand the evidence without opening JSON?
5. `Claim logic`
   Do claims form a coherent reasoning structure?
6. `Uncertainty honesty`
   Are risks, blockers, and unknowns stated clearly?
7. `Readability and structure`
   Does the report feel like a real research artifact?
8. `Auditability`
   Can major statements be traced back to evidence and source lineage?

Scoring bands:

- `5`:
  strong production quality with minimal weakness
- `4`:
  solid and usable, minor polish gaps only
- `3`:
  partially good but with visible structural weakness
- `2`:
  materially below product standard
- `1`:
  mostly unusable as a final report
- `0`:
  fails the function entirely

## Hard Fail Conditions

Any of the following should fail the report even if other sections look strong:

- the final artifact is effectively a JSON dump in Markdown clothing
- claims are too few or too coarse to support the body structure
- there is no explicit uncertainty treatment
- human-review-triggering conditions are hidden from the user flow
- the report cannot distinguish direct evidence from weak/background support
- sectioning follows the pipeline rather than the research question

## Review Checklist

Use this checklist before calling a report “done”.

- Can a human reader understand the answer without opening the JSON sidecar?
- Does the executive summary state the actual judgment?
- Are the major research dimensions explicit?
- Are evidence tables or structured evidence presentations used where helpful?
- Are the claims numerous and specific enough to support a long-form report?
- Are uncertainty and blockers visible?
- Is the final report clearly superior to a stitched claims/evidence preview?
- Is every major conclusion still auditable through the sidecar artifacts?
