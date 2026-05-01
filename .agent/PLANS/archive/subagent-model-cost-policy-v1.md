# Subagent Model Cost Policy v1

Status: completed

Created: 2026-04-29

Primary active PLAN: no

## Objective

Lower default subagent token cost while preserving role quality boundaries.

## Scope

In scope:

- `.codex/agents/*.toml` model and reasoning-effort settings.
- Current subagent operating docs.
- Project subagent gate skill documentation.

Out of scope:

- EvidenceBundle, source, research, provider, task, or run contract changes.
- Runtime changes outside existing Codex subagent configuration files.
- Changing the active source remediation PLAN.

## Decision

- Treat `medium` as the standard reasoning speed for all project subagents.
- Replace project subagent defaults using `gpt-5.5` with `gpt-5.4`.
- Use `gpt-5.3-codex-spark` for the high-frequency short code-quality validation role.
- Keep concrete implementation on `gpt-5.3-codex`, but reduce its reasoning effort to `medium`.

## Resulting Matrix

| Agent | Model | Reasoning |
| --- | --- | --- |
| `invest_project_director` | `gpt-5.4` | `medium` |
| `invest_project_summarizer` | `gpt-5.4` | `medium` |
| `invest_agent_architecture_builder` | `gpt-5.4` | `medium` |
| `invest_feature_programmer` | `gpt-5.3-codex` | `medium` |
| `invest_code_quality_checker` | `gpt-5.3-codex-spark` | `medium` |
| `invest_functional_validator` | `gpt-5.4` | `medium` |

## Validation

Required checks:

```powershell
Get-ChildItem .codex\agents\*.toml | Select-String -Pattern 'gpt-5.5|model_reasoning_effort = "high"'
Get-ChildItem .codex\agents\*.toml | Select-String -Pattern 'model =|model_reasoning_effort'
Select-String -Path docs\current-subagents-overview.md,docs\subagents-operating-model.md,.agent\skills\subagent-gate-contract.md -Pattern 'gpt-5.3-codex-spark','gpt-5.4','medium'
```

## Risks

- Some complex architecture or functional-validation tasks may need temporary model escalation.
- If Codex runtime ignores project-local `.codex/agents/*.toml` because project trust/config is inactive, these files document the intended policy but may not control actual spawned agents.
- The tool-level built-in agent types may still report fixed model metadata in the current session; future sessions should verify whether local agent configs are reloaded.

## Next Action

Use the new model matrix for future subagent work. Escalate only for explicitly complex tasks and record the exception in the active PLAN.
