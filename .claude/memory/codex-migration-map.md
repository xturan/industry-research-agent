# Codex → Claude Code Migration Map

Reference only. Load on demand. Do NOT put this in AGENTS.md — it changes as the project evolves and would break prompt cache.

## Slash Commands

| Command | Equivalent Codex Skill |
|---|---|
| `/workflow` | execution-mode-router + subagent-gate-contract |
| `/source-check` | source-regression-check + domestic-source-check |
| `/debug` | systematic-debugging |
| `/brainstorm` | brainstorming |
| `/plan-review` | plan-self-review |

## Subagent Roles

See `.claude/memory/subagents.md` for full role definitions (mapped from `.codex/agents/*.toml`).

## Config Migration

| Claude Code | Codex |
|---|---|
| `.claude/settings.json` | `.codex/config.toml` |
| `~/.claude/CLAUDE.md` | `~/.codex/AGENTS.md` + `memories/PROFILE.md` + `memories/ACTIVE.md` |
| `~/.claude/settings.json` | `~/.codex/config.toml` |
| `~/.claude/commands/plan-creator.md` | `~/.codex/skills/plan-creator/SKILL.md` |

## Scheduled Tasks

| Task | Schedule | Equivalent Codex |
|---|---|---|
| `daily-invest-agent-progress` | Daily 2:57 AM | `automations/automation.toml` (3AM heartbeat) |

## Key Rules

- `.agent/skills/` — authoritative reference (17 skills preserved)
- `.agent/STATUS.md` + `.agent/PLANS/` — single source of truth
- AGENTS.md > STATUS.md > `.claude/` convenience commands
- Original Codex memories remain at `~/.codex/memories/` as historical reference
