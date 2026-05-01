# Plan: Crawl4AI Domestic Article Extractor v1

Status: completed
Priority: medium
Owner: codex/human
Scope: source subsystem
Created: 2026-04-22
Last Updated: 2026-04-26

## Objective
Improve the standalone Crawl4AI article script so it produces stable markdown and structured table output for domestic policy/article pages.

## Scope
In scope:
- study official Crawl4AI docs before changing the script
- improve markdown generation strategy usage
- improve title/meta extraction
- preserve or enrich table extraction in structured output
- make markdown output distinguish headings and tables clearly

Out of scope:
- integrating Crawl4AI into the production source pipeline
- multi-page crawling
- OCR / PDF extraction
- generalized site-wide schema generation

## Constraints
- keep changes isolated to the standalone script unless a tiny helper is clearly justified
- prefer official Crawl4AI patterns over ad-hoc scraping when practical
- retain fallback behavior for weak Crawl4AI results
- keep local verification lightweight

## Phases
- [x] Phase 1: Study Crawl4AI docs for markdown and table extraction
- [x] Phase 2: Refactor script output model and extraction flow
- [x] Phase 3: Validate script behavior and update status

## Current phase
Completed

## Validation
- `python -m ruff check scripts\\crawl4ai_ichuanghui_4925.py`
- `python -m py_compile scripts\\crawl4ai_ichuanghui_4925.py`

## Progress
- Read official Crawl4AI docs for markdown generation, fit markdown, crawler result fields, table extraction, and structured CSS extraction.
- Confirmed target page contains title/meta/content plus two HTML tables.
- Refactored the script to:
  - explicitly configure `DefaultMarkdownGenerator`
  - apply `PruningContentFilter`
  - use `JsonCssExtractionStrategy` for article-level fields
  - enable `DefaultTableExtraction`
  - render tables into markdown instead of silently flattening them
  - preserve HTML fallback when Crawl4AI output quality is too weak
- Static validation passed after refactor:
  - `python -m ruff check scripts\\crawl4ai_ichuanghui_4925.py`
  - `python -m py_compile scripts\\crawl4ai_ichuanghui_4925.py`
- User explicitly requested marking this plan completed on 2026-04-26.

## Risks
- true Crawl4AI-enabled end-to-end runtime validation was not completed in this environment
- Crawl4AI cleaned HTML may remain too aggressive for some Chinese sites, so fallback logic must remain

## Next action
None. Plan archived as completed by user request.
