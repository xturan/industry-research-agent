"""Validate the review-gated-agent-workflow plugin package."""

from __future__ import annotations

import json
from pathlib import Path
import sys


REQUIRED_SKILLS = [
    "prd-workflow",
    "brainstorm",
    "prd-html-review",
    "plan-from-prd",
    "group2-design",
    "workflow-scope-guard",
]

REQUIRED_TEMPLATES = [
    "prd_review.md",
    "prd_review.html",
    "plan.md",
    "group2_design.md",
    "hook_scope_rules.yaml",
]

REQUIRED_HOOKS = [
    "hooks.json",
    "scope_preflight.py",
    "diff_postflight.py",
    "stop_gate_check.py",
]


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def check_file(path: Path) -> str | None:
    if not path.exists():
        return f"missing {path}"
    if not path.is_file():
        return f"not a file {path}"
    return None


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(".")
    root = root.resolve()

    manifest = root / ".codex-plugin" / "plugin.json"
    if error := check_file(manifest):
        return fail(error)

    try:
        plugin_json = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return fail(f"invalid plugin.json: {exc}")

    for key in ["name", "version", "description", "skills"]:
        if key not in plugin_json:
            return fail(f"plugin.json missing {key}")

    if plugin_json["name"] != "review-gated-agent-workflow":
        return fail("plugin.json name must be review-gated-agent-workflow")

    for skill in REQUIRED_SKILLS:
        skill_file = root / "skills" / skill / "SKILL.md"
        if error := check_file(skill_file):
            return fail(error)
        text = skill_file.read_text(encoding="utf-8")
        if f"name: {skill}" not in text:
            return fail(f"{skill_file} missing matching front matter name")
        if "Use When" not in text or "Skip When" not in text:
            return fail(f"{skill_file} missing Use When or Skip When section")

    for explicit_skill in ["prd-workflow", "group2-design"]:
        policy = root / "skills" / explicit_skill / "agents" / "openai.yaml"
        if error := check_file(policy):
            return fail(error)
        if "allow_implicit_invocation: false" not in policy.read_text(encoding="utf-8"):
            return fail(f"{policy} must disable implicit invocation")

    for hook in REQUIRED_HOOKS:
        if error := check_file(root / "hooks" / hook):
            return fail(error)

    hooks_json = root / "hooks" / "hooks.json"
    try:
        json.loads(hooks_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return fail(f"invalid hooks.json: {exc}")

    for template in REQUIRED_TEMPLATES:
        if error := check_file(root / "templates" / template):
            return fail(error)

    print("PASS: plugin package structure is valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
