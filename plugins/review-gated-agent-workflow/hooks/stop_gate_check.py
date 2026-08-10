"""Stop gate check for review-gated workflow runs.

The optional REVIEW_GATED_RUN_STATE file is a simple key=value text file.
Missing state is treated as warn/no-op so ordinary Codex work is not blocked.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


def _read_state(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    state: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        state[key.strip()] = value.strip()
    return state


def main() -> int:
    state_path = os.environ.get("REVIEW_GATED_RUN_STATE", "").strip()
    if not state_path:
        print("decision=warn reason=missing REVIEW_GATED_RUN_STATE")
        return 0

    state = _read_state(Path(state_path))
    stage = state.get("stage", "")
    prd_approved = state.get("prd_approved", "false").lower() == "true"
    plan_approved = state.get("plan_approved", "false").lower() == "true"
    claiming_complete = state.get("claiming_complete", "false").lower() == "true"
    group3_validated = state.get("group3_validated", "false").lower() == "true"

    if stage == "plan_from_prd" and not prd_approved:
        print("decision=block reason=PLAN creation requires PRD approval")
        return 2
    if stage == "group2_implementation" and not plan_approved:
        print("decision=block reason=implementation requires PLAN approval")
        return 2
    if claiming_complete and stage == "group2_implementation" and not group3_validated:
        print("decision=block reason=Group2 cannot self-certify without Group3 validation")
        return 2

    print(f"decision=pass stage={stage or 'unknown'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
