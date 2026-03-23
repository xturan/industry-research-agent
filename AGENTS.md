# AGENTS.md

## Project
Build a production-oriented AI application for industry-report mining, investment-theme intelligence extraction, and multi-channel content generation.

The application should support:
- multi-agent research workflows
- MCP-based tool integration
- memory, RAG, and database-backed evidence management
- article/report/video-script generation
- async task processing
- observability
- future reinforcement-learning-ready run logging

## Product constraints
- Do NOT position the product as direct securities investment advice.
- Position it as industry intelligence, research assistance, and content production.
- Every conclusion must be traceable to evidence.
- Prefer deterministic code/workflows over prompt-only logic when possible.

## Engineering constraints
- Use a monorepo layout.
- Prefer Python for backend and agent orchestration.
- Prefer FastAPI for API service.
- Prefer PostgreSQL as primary database.
- Prefer pgvector for vector search.
- Prefer Redis for cache / task state / short-term memory.
- Use object storage abstraction for raw reports and generated assets.
- Use an async task queue for long-running jobs.
- Include tests for every major module.
- Add Makefile targets for setup, run, test, lint.
- Add Docker Compose for local development.
- Keep the code modular and production-oriented.

## Agent architecture expectations
Implement these roles over time:
- Supervisor Agent
- Source Hunter Agent
- Parser/Structurer Agent
- Thesis Builder Agent
- Opponent Agent
- Evidence Judge Agent
- Content Strategist Agent
- Growth Analyst Agent

## RAG expectations
- Use hybrid retrieval design in architecture
- preserve metadata for source, time, industry, company, document section, confidence
- support evidence bundles, not just raw chunks
- retrieval results must be auditable

## Memory expectations
Support:
- theme memory
- content strategy memory
- user/account preference memory
- run memory / execution trace memory

## Tooling expectations
Tooling should be integrated through clean interfaces so it can later be swapped to MCP servers.
Do not tightly couple business logic to a single provider.

## Delivery rules
- Work step by step
- At the end of each step, produce:
  1. what changed
  2. files created/modified
  3. commands to verify
  4. known risks / TODOs
- Do not silently skip failed commands
- If something is ambiguous, choose the most pragmatic implementation and explain it in the final step summary

## Quality gates
Before claiming a step is done:
- run tests relevant to the changed modules
- run lint/format where configured
- verify the app starts if startup code changed
- verify migrations if schema changed