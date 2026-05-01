# Decisions

## D1: Continue despite dirty worktree

Decision:
- Accept the previously recorded dirty-worktree scope-proof risk and continue with `.agent`-only writes.

Reason:
- The user explicitly said "continue" after being offered the risk-acceptance option.

Boundary:
- This does not authorize edits to `AGENTS.md` or production code.

## D2: Keep Superpowers advisory

Decision:
- Keep Superpowers as a reference methodology only.

Reason:
- Native `.agent` artifacts now cover the adopted/adapted concepts.

Boundary:
- No plugin activation occurred.

## D3: Do not record private chain-of-thought

Decision:
- Run traces store external engineering evidence only.

Reason:
- The operating model needs auditability without hidden reasoning capture.
