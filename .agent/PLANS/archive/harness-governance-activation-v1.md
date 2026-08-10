# Harness Governance Activation v1

Status: completed

Created: 2026-06-01

Primary active PLAN: yes (governance/ops track; supersedes no source-layer PLAN)

## Objective

Make the project's governance actually fire instead of relying on the model
remembering to read `SKILL_ROUTER.md`, and restore a clean single-active-PLAN
signal. Two workstreams only:

1. **治理 skill 真正生效** — promote the highest-value `.agent/skills/*.md`
   governance rules into native `.claude/skills/<name>/SKILL.md` trigger
   wrappers (with `name` + trigger-rich `description` frontmatter) so the
   harness auto-surfaces them. Native wrappers stay thin and point to the
   canonical `.agent/skills/*.md` as the single source of truth (no rule
   duplication, no drift).
2. **PLAN 状态清理** — audit the 15 files currently in `.agent/PLANS/`
   (vs 26 archived), archive completed and superseded/blocked
   remediation-chain PLANs, mark genuinely-queued ones clearly, and resync
   `INDEX.md` + `STATUS.md` so exactly one primary active PLAN is signalled.

## Task Classification

- Primary area: `eval_policy_ops` (governance / docs)
- Secondary impacted: none (no `packages/**` production code touched)
- High-risk contracts touched: none. This PLAN must not modify EvidenceBundle,
  citation fields, research response shape, provider abstraction, task/run
  semantics, or any source-layer behavior.
- Type: implementation-starting, but docs/governance only.

## Scope

In scope:

- Create `.claude/skills/<name>/SKILL.md` thin wrappers for a selected set of
  governance skills.
- Optionally wire a hook to inject a governance pointer (only if native skills
  alone prove insufficient — see Phase 2 decision gate).
- Audit, archive, and re-label PLAN files; resync `INDEX.md` and the
  `STATUS.md` "Primary Active Plan" list and "Repository Current Focus".
- Update `SKILL_ROUTER.md` to note that selected skills now have native
  auto-trigger wrappers.

Explicitly OUT OF SCOPE (future work, recorded in Next Action only):

- STATUS.md 2172-line trim into a ~150-line handoff + history file.
- Re-evaluating `bypassPermissions` / adding a destructive-action PreToolUse
  permission gate.
- A `SessionStart` hook that consumes `last_session.json` / `last_error.json` /
  `memory_touched.txt` signals.

## Constraints

- Native wrappers MUST NOT restate the full rule body; they carry trigger
  metadata + a one-screen summary + an explicit pointer to the canonical
  `.agent/skills/<name>.md`. Single source of truth stays in `.agent/skills/`.
- `description` frontmatter must encode WHEN to use (trigger conditions), not a
  vague internal-process summary (per `skill-design-standard.md`).
- Do not delete any `.agent/skills/*.md` or PLAN file; archive by moving into
  `.agent/PLANS/archive/`, never by deletion.
- Conflict order stays: `AGENTS.md` > `STATUS.md` > active PLAN > skills.
- `local_direct` execution mode (low risk, docs/governance). No subagents.

## Architecture / Design Direction

```
.agent/skills/<name>.md        <- canonical rule body (single source of truth)
        ▲ pointer
        │
.claude/skills/<name>/SKILL.md  <- NEW thin native wrapper
        - frontmatter: name + trigger-rich description (auto-surfaced by harness)
        - body: one-screen summary + "Authoritative source: .agent/skills/<name>.md"
        │
SKILL_ROUTER.md                 <- updated: marks which skills now auto-trigger
```

Selection principle: promote skills whose MISFIRE is most costly and whose
trigger is most objective (file globs, completion claims, failure events).
Leave brainstorm/design/PLAN-creation as slash commands + router entries
(already discoverable, intent-driven, lower auto-trigger value).

Promotion set (Phase 1):

| Native wrapper | Canonical source | Trigger (description encodes) |
|---|---|---|
| `verification-before-completion` | `.agent/skills/verification-before-completion.md` | about to claim done/fixed/passed/ready |
| `source-regression-check` | `.agent/skills/source-regression-check.md` | edits under `packages/sources/**` or source parts of `packages/agents/**` |
| `domestic-source-check` | `.agent/skills/domestic-source-check.md` | domestic source collector code changed |
| `research-contract-check` | `.agent/skills/research-contract-check.md` | research workflow / provider abstraction changed |
| `task-flow-check` | `.agent/skills/task-flow-check.md` | task/worker/substrate code changed |
| `systematic-debugging` | `.agent/skills/systematic-debugging.md` | debugging a failure/flaky behavior |
| `execution-mode-router` | `.agent/skills/execution-mode-router.md` | starting/continuing PLAN execution |

## Phases

### Phase 1 — Native skill wrappers (治理 skill 真正生效)

Status: completed

Objective: create `.claude/skills/<name>/SKILL.md` for each skill in the
promotion set, as thin trigger wrappers pointing to the canonical
`.agent/skills/*.md`.

Acceptance criteria:

- 7 `SKILL.md` files exist under `.claude/skills/<name>/`.
- Each has valid frontmatter: `name` (kebab matches dir) + `description` that
  states explicit trigger conditions (file globs / completion claims / failure
  events / PLAN-execution), not a process summary.
- Each body is ≤ one screen and contains the line
  `Authoritative source: .agent/skills/<name>.md`.
- No rule logic is duplicated/forked from the canonical file.

Validation:

```bash
ls .claude/skills/*/SKILL.md            # expect 7
grep -L "Authoritative source" .claude/skills/*/SKILL.md   # expect empty
grep -c "^name:" .claude/skills/*/SKILL.md  # each = 1
python -c "import re,glob,sys; [sys.exit('bad frontmatter: '+f) for f in glob.glob('.claude/skills/*/SKILL.md') if not open(f,encoding='utf-8').read().startswith('---')]"
```

Risks: native skill `description` too broad → over-triggers and adds context
noise. Mitigation: scope each description to concrete file globs / events.

### Phase 2 — Decision gate: are native wrappers enough?

Status: completed

Objective: decide whether native auto-surfacing is sufficient or whether a hook
is also needed to force-inject a governance pointer.

Acceptance criteria:

- Documented decision recorded in this PLAN's Progress: `native_only` or
  `native_plus_hook`.
- If `native_plus_hook`: a `UserPromptSubmit` or `PreToolUse` hook is added to
  `.claude/settings.json` that injects the SKILL_ROUTER pointer when a touched
  path matches a governed module. Hook must be additive and non-blocking
  (never hard-fail a tool call).
- If `native_only`: explicitly record why no hook is needed.

Validation:

```bash
python -c "import json;d=json.load(open('.claude/settings.json'));print(json.dumps(d.get('hooks',{}),indent=2,ensure_ascii=False))"
# if a hook was added, run it once with a sample payload and confirm exit 0
```

Default expectation: `native_only` (lower complexity, no new failure surface).
Escalate to hook only if Phase 1 trigger coverage has objective gaps.

### Phase 3 — PLAN state cleanup (PLAN 状态清理)

Status: completed

Objective: restore a clean single-active-PLAN signal across the filesystem,
`INDEX.md`, and `STATUS.md`.

Audit decisions (to confirm during execution against file `Status:` headers):

- `theme-watchlist-intel-workbench-v1.md` — INDEX says `completed` →
  move to `archive/`.
- The remediation/evidence chain currently loose in `.agent/PLANS/`
  (`source-direct-structured-execution-v1`, `source-profile-adapter-remediation-v1`,
  `source-strong-evidence-adapter-remediation-v1`,
  `source-generalized-evidence-remediation-v1`,
  `source-local-evidence-backbone-remediation-v1`,
  `source-quality-stress-eval-v1`) — all marked blocked/superseded in INDEX →
  move superseded/blocked-handoff ones to `archive/`, keeping only any that are
  a live successor.
- `source-local-procurement-regulatory-depth-v1.md` — INDEX's named active
  (paused per Route C) → keep, mark `queued_paused`.
- `agentic-operating-system-v2.md` — `completed_pending_human_review` → keep in
  place under a "Pending Human Review" section (do not archive without user).
- Remaining (`research-product-v1`, `unified-research-pipeline-v1`,
  `longtasks-substrate-v1`, `deep-research-agent-v1`) — read each `Status:`
  header and classify as active / queued / completed→archive. Do not guess;
  read the header.

Acceptance criteria:

- Every file remaining in `.agent/PLANS/` (non-archive) is either the single
  primary active PLAN, a clearly-labelled queued PLAN, or pending-human-review.
- No file whose own header says `completed`/`superseded` remains outside
  `archive/`.
- `INDEX.md` "Active Plan" table lists exactly one primary active PLAN and a
  truthful queued list; archived entries moved to the archived section.
- `STATUS.md` "Primary Active Plan" list and "Repository Current Focus" agree
  with `INDEX.md` (no contradiction about what is active).

Validation:

```bash
ls .agent/PLANS/*.md | wc -l        # expect materially fewer than 15
for f in .agent/PLANS/*.md; do echo "$f: $(grep -m1 -i '^status' "$f")"; done
grep -n "Primary active PLAN: yes" .agent/PLANS/*.md   # expect exactly 1
```

Risks: misclassifying a paused-but-live PLAN as archived. Mitigation: classify
strictly from each file's own `Status:` header, not from memory; archiving is a
move (reversible), never a delete.

### Phase 4 — Router + cross-doc consistency

Status: completed

Objective: update `SKILL_ROUTER.md` to reflect native auto-trigger wrappers and
confirm no governance doc contradicts another.

Acceptance criteria:

- `SKILL_ROUTER.md` notes which skills now have native `.claude/skills/`
  wrappers (so the router and native layer agree).
- `AGENTS.md` "Mandatory checks by task type" still matches the promoted skill
  set (no stale skill names).
- This PLAN's Progress records the final file inventory.

Validation:

```bash
grep -n "native" .agent/SKILL_ROUTER.md || echo "router note missing"
ruff check .agent 2>/dev/null || echo "ruff n/a for md (ok)"
```

## Continue Rule

After a phase passes its validation block, immediately continue to the next
phase. Record progress in this PLAN. Do not pause between phases for routine
completion (per AGENTS.md Phase auto-switch rule). Phase 2 is a decision gate,
not a stop — record the decision and continue.

## Done Condition

- 7 native `.claude/skills/*/SKILL.md` wrappers exist and validate.
- Phase 2 decision recorded (native_only or native_plus_hook, implemented).
- `.agent/PLANS/` shows exactly one primary active PLAN; INDEX.md and STATUS.md
  agree; completed/superseded PLANs archived.
- `SKILL_ROUTER.md` updated; no governance-doc contradiction.
- Then: set this PLAN `Status: completed`, move to `archive/`, and point
  STATUS.md at the next active PLAN (or "no active long task").

## Stop Conditions

- A PLAN's own `Status:` header is ambiguous and cannot be classified without
  user input (Phase 3).
- Adding a hook would require touching `settings.json` in a way that risks the
  existing three hooks (Phase 2) — pause and confirm.
- Any step would require touching `packages/**` production code (out of scope).
- User explicitly pauses.

## Validation Loop

Run per-phase validation blocks above. Global end check:

```bash
ls .claude/skills/*/SKILL.md | wc -l            # 7
ls .agent/PLANS/*.md | wc -l                    # << 15, one primary active
grep -rn "Primary active PLAN: yes" .agent/PLANS/*.md | wc -l   # 1
```

Pass = all three match expectations and no governance doc contradicts another.

## Progress

- 2026-06-01: PLAN created (planning-only). Durable context read: AGENTS.md,
  STATUS.md section headers, INDEX.md, promotion-candidate skill files,
  execution-mode-router. Verified native SKILL.md convention works
  (`~/.claude/skills/crawl4ai/SKILL.md` frontmatter = `name` + `description`)
  and confirmed no `.claude/skills/` dir exists yet. No code changed.
- 2026-06-12: Phase 1 completed. Created 7 native thin wrappers under
  `.claude/skills/<name>/SKILL.md` for:
  `verification-before-completion`, `source-regression-check`,
  `domestic-source-check`, `research-contract-check`, `task-flow-check`,
  `systematic-debugging`, and `execution-mode-router`. Validation confirmed
  wrapper count `7`, `Authoritative source` count `7`, and frontmatter
  structure `OK`.
- 2026-06-12: Phase 2 completed with decision `native_only`. No hook was added
  because the promoted native wrappers cover objective trigger conditions and a
  hook would add a new failure surface before evidence shows native surfacing is
  insufficient.
- 2026-06-12: Phase 3 completed. Archived completed/superseded/blocked loose
  PLAN files, rewrote `INDEX.md` into active / queued-paused / pending-review
  sections, changed stale primary headers on queued plans, and replaced the
  contradictory `STATUS.md` handoff with a concise current-state version.
  Validation confirmed exactly one non-archive `Primary active PLAN: yes`
  before final archive.
- 2026-06-12: Phase 4 completed. Updated `.agent/SKILL_ROUTER.md` with the
  native wrapper mapping while preserving `.agent/skills/*.md` as the
  authoritative rule bodies.
- 2026-06-12: PLAN completed. Governance wrappers and PLAN/STATUS cleanup are
  in place; this PLAN can be archived.
- 2026-06-21: Follow-on WS2 maintenance (not a gap in the original — Phase 3 was
  done 2026-06-12). In the 9 days since, the active dir re-accumulated to 25
  PLANs as new work completed/superseded/blocked (readable-report remediation
  completed 4/4, quality-v2 superseded, several source remediation chains
  blocked, etc.). Re-ran the same WS2 cleanup: archived 15
  completed/superseded/blocked PLANs (active 25 → 10), rewrote `INDEX.md` into
  Active / Active-Reference / Pending-Human-Review / Recently-Archived sections,
  and resynced `STATUS.md` Primary Active Plan (no longer points to the now-
  archived remediation PLAN). 10 active PLANs remain: 3 in execution
  (search-caliber-expansion, research-product, source-local-procurement), 4
  active-reference Phase-0 contracts, 3 pending human review. Confirms the
  governance pattern needs periodic re-runs, not just one-time activation.

## Risks and Rollback

- Drift risk: native wrapper bodies could fork from canonical `.agent/skills`.
  Rollback: wrappers are thin pointers; delete the `.claude/skills/<name>/`
  dir to revert with zero impact on canonical rules.
- Over-trigger risk: too-broad `description` adds context noise. Rollback:
  tighten description or remove the wrapper dir.
- PLAN-archive misclassification: archiving is a `git mv`-style move; restore by
  moving the file back out of `archive/`.

## Next Action

Archive this completed PLAN and leave `.agent/STATUS.md` pointing to no active
long-running plan until the next user-selected plan is resumed.
