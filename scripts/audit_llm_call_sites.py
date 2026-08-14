"""G2.2d LLM Call-Site Bypass Audit v2.

分开统计两个维度：
1. **Provider Boundary Visibility**：所有业务 LLM 调用点是否都能被 Gateway 认知
   （即已分类）。共享 helper 也算「对 Gateway 可见」，因为它透传 caller 的
   workload identity。
2. **Logical Workload Classification**：逻辑 workload 是否全部落入 LLM taxonomy。
   共享 helper 本身没有 workload 身份（workload identity 属于业务 caller），
   不计作独立 workload。

**不修改任何正式 Provider 行为。** 产出 data/tmp/llm_call_site_audit/audit.json。

用法：python -m scripts.audit_llm_call_sites
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
OUT_DIR = _REPO / "data" / "tmp" / "llm_call_site_audit"

_LLM_PATTERNS = re.compile(
    r"\.generate_json\(|\.generate_text\(|chat\.completions\.create|ainvoke\(|llm\.invoke\("
)

_EXCLUDE_DIRS = {
    "__pycache__", "test", "tests", "dev_demo", "training", "scripts",
    ".claude", ".venv", "evals",
}
_EXCLUDE_FILE_HINTS = ("test_", "conftest", "_smoke", "_bench", "dev_demo")

# 共享 helper：自身无 workload 身份，其 workload 来自业务 caller。
_SHARED_HELPER_FILES = (
    "packages/agents/llm_agents.py",
    "packages/research_harness/tooling/llm_agents.py",
)

# 共享 helper 服务的逻辑 workload（caller → task_type），用于 workload 统计。
_SHARED_HELPER_WORKLOADS: dict[str, list[tuple[str, str]]] = {
    "packages/agents/llm_agents.py": [
        ("supervisor_intake", "intent_planning"),
        ("thesis_builder", "research_planning"),
        ("opponent", "research_planning"),
        ("evidence_judge", "structured_repair"),
        ("risk_analyst", "structured_repair"),
    ],
    "packages/research_harness/tooling/llm_agents.py": [
        ("structured_compare/editor", "structured_draft"),
    ],
}


@dataclass
class CallSite:
    file: str
    line: int
    function: str
    pattern: str
    task_type: str  # task_type 或 "unclassified"
    is_helper: bool = False


def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        parts = set(path.parts)
        if parts & _EXCLUDE_DIRS:
            continue
        if any(hint in path.name for hint in _EXCLUDE_FILE_HINTS):
            continue
        rel = str(path.relative_to(_REPO)).replace("\\", "/")
        if "packages/providers/" in rel:
            continue  # provider 实现层，非调用点
        yield path, rel


def _classify(file_rel: str, function: str, line_text: str) -> str | None:
    """按文件/函数/prompt 关键字分类。返回 task_type 或 None（未分类）。"""
    if "search_phrase_augmenter" in file_rel:
        return "search_phrase_generation"
    if "retrieval_planner" in file_rel:
        return "research_planning"
    if "tooling/llm_agents" in file_rel:
        return "structured_draft"  # 共享 helper（结构化编辑/compare 路径）
    if "agents/llm_agents" in file_rel:
        return "research_planning"  # 共享 helper（5-step agent）
    if "source_tier_model" in file_rel:
        return "source_tier_classification"  # 已纳入 taxonomy
    if "caliber_expander" in file_rel:
        if "INTENT_PLANNER" in line_text or "intent_planner" in function:
            return "intent_planning"
        if "SEARCH_BUILDER" in line_text or "search_builder" in function:
            return "search_phrase_generation"
        return "query_expansion"
    if "deep_research" in file_rel:
        if "caliber" in function or "caliber" in line_text.lower():
            return "query_expansion"
        return "research_planning"
    return None


def run_audit() -> dict[str, Any]:
    call_sites: list[CallSite] = []
    for root in (_REPO / "packages", _REPO / "apps"):
        if not root.exists():
            continue
        for path, rel in _iter_python_files(root):
            function = ""
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for lineno, raw in enumerate(lines, start=1):
                m_def = re.match(r"^\s*(?:async\s+)?def\s+(\w+)", raw)
                if m_def:
                    function = m_def.group(1)
                if not _LLM_PATTERNS.search(raw):
                    continue
                is_helper = rel in _SHARED_HELPER_FILES
                task_type = _classify(rel, function, raw) or "unclassified"
                call_sites.append(
                    CallSite(
                        file=rel, line=lineno, function=function,
                        pattern=_LLM_PATTERNS.search(raw).group(0),
                        task_type=task_type, is_helper=is_helper,
                    )
                )

    # ── 维度 1：Provider Boundary Visibility ─────────────────────────────────
    total_sites = len(call_sites)
    visible = [c for c in call_sites if c.task_type != "unclassified"]
    unclassified_sites = [c for c in call_sites if c.task_type == "unclassified"]

    # ── 维度 2：Logical Workload Classification ──────────────────────────────
    workloads: list[dict[str, str]] = []
    # 非 helper 的 call site 各自代表一个逻辑 workload
    for c in call_sites:
        if not c.is_helper:
            workloads.append({"source": f"{c.file}:{c.line}", "task_type": c.task_type})
    # 共享 helper 由 caller 声明 workload（helper 本身不是 workload）
    for helper_file, caller_workloads in _SHARED_HELPER_WORKLOADS.items():
        for caller, task_type in caller_workloads:
            workloads.append({"source": f"{helper_file}::{caller}", "task_type": task_type})

    classified_workloads = [w for w in workloads if w["task_type"] != "unclassified"]
    unclassified_workloads = [w for w in workloads if w["task_type"] == "unclassified"]

    report = {
        "provider_boundary_visibility": {
            "total": total_sites,
            "gateway_visible": len(visible),
            "rate": round(len(visible) / total_sites, 4) if total_sites else 0.0,
        },
        "workload_classification": {
            "total": len(workloads),
            "classified": len(classified_workloads),
            "rate": round(len(classified_workloads) / len(workloads), 4) if workloads else 0.0,
        },
        "unclassified_call_sites": [asdict(c) for c in unclassified_sites],
        "unclassified_workloads": unclassified_workloads,
        "direct_provider_bypass_count": len(unclassified_sites),
        "shared_helpers": list(_SHARED_HELPER_FILES),
        "call_sites": [asdict(c) for c in sorted(call_sites, key=lambda c: c.file)],
        "workloads": sorted(workloads, key=lambda w: w["source"]),
        "note": (
            "provider 实现层(packages/providers/*)不计入；共享 helper 的 workload "
            "身份属于业务 caller（helper 透传 task_type），helper 本身不计为独立 "
            "workload。direct_provider_bypass = 未分类的业务 LLM 调用点。"
        ),
    }
    return report


def main() -> int:
    report = run_audit()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    pv = report["provider_boundary_visibility"]
    wc = report["workload_classification"]
    print(f"[audit] provider_boundary_visibility = {pv['gateway_visible']}/{pv['total']} "
          f"({pv['rate']:.2%})")
    print(f"[audit] workload_classification      = {wc['classified']}/{wc['total']} "
          f"({wc['rate']:.2%})")
    print(f"[audit] direct_provider_bypass_count = {report['direct_provider_bypass_count']}")
    for c in report["unclassified_call_sites"]:
        print(f"  UNCLASSIFIED {c['file']}:{c['line']} ({c['function']})")
    for w in report["workloads"]:
        print(f"  workload {w['task_type']:<28} {w['source']}")
    print(f"[audit] -> {OUT_DIR / 'audit.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
