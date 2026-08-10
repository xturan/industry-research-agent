"""Conservative preflight scope check for review-gated workflow hooks.

The script is intentionally dependency-free and warn-by-default. It reads:

- REVIEW_GATED_STAGE: current workflow stage, optional.
- REVIEW_GATED_TARGETS: semicolon-separated target paths, optional.
- REVIEW_GATED_SCOPE_RULES: path to scope rules, optional.

When context is missing, the script emits a warning and exits 0.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
import sys


def _load_rules(path: Path) -> dict[str, list[str]]:
    """Parse the small YAML subset used by hook_scope_rules.yaml."""
    rules: dict[str, list[str]] = {}
    current_stage: str | None = None
    current_key: str | None = None

    if not path.exists():
        return rules

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            current_stage = stripped[:-1]
            current_key = None
            rules.setdefault(f"{current_stage}:allowed_write", [])
            rules.setdefault(f"{current_stage}:forbidden_write", [])
            continue
        if current_stage and line.startswith("    ") and stripped.endswith(":"):
            current_key = stripped[:-1]
            rules.setdefault(f"{current_stage}:{current_key}", [])
            continue
        if current_stage and current_key and stripped.startswith("- "):
            rules.setdefault(f"{current_stage}:{current_key}", []).append(stripped[2:].strip('"'))
    return rules


def _matches(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def main() -> int:
    stage = os.environ.get("REVIEW_GATED_STAGE", "").strip()
    targets = [p.strip() for p in os.environ.get("REVIEW_GATED_TARGETS", "").split(";") if p.strip()]
    rules_path = Path(os.environ.get("REVIEW_GATED_SCOPE_RULES", "templates/hook_scope_rules.yaml"))

    if not stage or not targets:
        print("decision=warn stage=unknown reason=missing REVIEW_GATED_STAGE or REVIEW_GATED_TARGETS")
        return 0

    rules = _load_rules(rules_path)
    forbidden = rules.get(f"{stage}:forbidden_write", [])
    violations = [target for target in targets if _matches(target, forbidden)]

    if violations:
        print(f"decision=block stage={stage} violations={';'.join(violations)}")
        return 2

    print(f"decision=pass stage={stage} targets={';'.join(targets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
