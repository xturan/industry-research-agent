"""Conservative postflight diff audit for review-gated workflow hooks."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from scope_preflight import _load_rules, _matches


def _changed_files_from_git() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return []
    files: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            files.append(path)
    return files


def main() -> int:
    stage = os.environ.get("REVIEW_GATED_STAGE", "").strip()
    explicit = [p.strip() for p in os.environ.get("REVIEW_GATED_CHANGED_FILES", "").split(";") if p.strip()]
    changed = explicit or _changed_files_from_git()

    if not stage:
        print("decision=warn stage=unknown reason=missing REVIEW_GATED_STAGE")
        return 0
    if not changed:
        print(f"decision=warn stage={stage} reason=no changed files detected")
        return 0

    rules_path = Path(os.environ.get("REVIEW_GATED_SCOPE_RULES", "templates/hook_scope_rules.yaml"))
    rules = _load_rules(rules_path)
    forbidden = rules.get(f"{stage}:forbidden_write", [])
    violations = [path for path in changed if _matches(path, forbidden)]

    if violations:
        print(f"decision=block stage={stage} violations={';'.join(violations)}")
        return 2

    print(f"decision=pass stage={stage} changed_files={';'.join(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
