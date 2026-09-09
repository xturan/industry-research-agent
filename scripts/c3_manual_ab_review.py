# ruff: noqa: E501
"""Phase C.3.2 — Manual Blind A/B Review package builder.

Builds data/tmp/c3_manual_ab_review/:
  <case>/{report_A.md, report_B.md, review_form.md}
  blind_mapping.json   (A/B -> structured/legacy; DO NOT open before review)
  human_review.csv      (1-5 scores + serious issues + preference)
  C3_MANUAL_REVIEW_SUMMARY.md

For case_01 / case_05 the real structured/legacy pair comes from the C.3.2
zero-shot acceptance artifacts. For case_02 the B.2 legacy is empty, so a fresh
REAL graph run (provider + DeepSeek) is made to obtain a genuine legacy and
store, then structured_compare (real DeepSeek) is run on that same store.

The A/B assignment is randomized (seeded) and written ONLY to blind_mapping.json;
the console never prints the mapping.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from packages.research_harness.eval_persistence import (
    RunEvaluationStore,
    build_evaluable_coverage_report,
)
from packages.research_harness.gap_retrieval import derive_gaps
from packages.research_harness.structured_compare import (
    real_section_llm_call,
    run_structured_compare,
)

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "data" / "tmp" / "c3_structured_compare"
OUT = REPO / "data" / "tmp" / "c3_manual_ab_review"

CASES = {
    "case_01": "2025 年合肥低空物流项目的落地进展、运营状态及官方证据",
    "case_02": "2025 年合肥低空经济相关上市公司的项目收入及订单贡献",
    "case_05": None,  # synthetic holdout; pair from acceptance artifacts
}

REVIEW_FORM_TEMPLATE = """# {case_id} — 人工盲审 A/B

请先阅读 report_A.md 与 report_B.md，再填写本表。**在填写完之前不要打开 blind_mapping.json。**

## 六维评分（1–5，5=最好）

| 维度 | A 分 | B 分 | 备注 |
| --- | --- | --- | --- |
| 核心问题覆盖 |  |  | 是否真正回答研究问题 |
| 关键事实完整 |  |  | 关键项目/时间/数据/政策是否遗漏 |
| 证据边界 |  |  | 是否区分已确认/有限支持/暂未确认 |
| 研究叙事 |  |  | 逻辑组织而非事实清单 |
| 简洁与重复 |  |  | 是否有重复/空话/材料堆砌 |
| 可读性 |  |  | 段落衔接与表达是否自然 |

## 严重问题（记录出现于哪一版）

- 关键结论遗漏：
- 无依据推断：
- 数字或实体错误：
- 把未找到写成不存在：
- 重复内容明显：
- 段落机械拼接：

## 内容类型观察

- 必须保留（Required Claim / 关键数字 / 日期 / Limitation）是否齐全？
- 有价值的综合（政策→项目传导、产业阶段判断、相互印证）是否保留？
- 可压缩背景是否被合理压缩？
- 冗余（反复改写/重复数据/空泛总结）是否被删除？

## 总体判断

- 我更倾向的版本：A / B
- Structured 是否**不明显弱于** Legacy：是 / 否
- 建议：进入 structured_primary_canary / 暂不进入（需受约束综合能力）
- 备注：
"""


def _existing_pair(case_id: str) -> tuple[str, str] | None:
    d = SRC / f"{case_id}__zero_shot"
    structured_path = d / "structured_markdown.md"
    legacy_path = d / "legacy_markdown.md"
    if structured_path.exists() and legacy_path.exists() and (
        legacy_path.read_text(encoding="utf-8") or ""
    ).strip():
        return (structured_path.read_text(encoding="utf-8"),
                legacy_path.read_text(encoding="utf-8"))
    return None


def _real_case02_pair() -> tuple[str, str]:
    """Run a fresh REAL graph for case_02, then structured_compare on its store."""
    import os
    import sqlite3

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from packages.core.config import get_settings
    from packages.db.base import Base
    from packages.db.session import reset_db_session_state
    from packages.research_harness import real_nodes
    from packages.research_harness.runner import ResearchGraphRunner
    from packages.research_harness.schemas import GraphAnalyzeRequest

    work = OUT / "_generated_case_02"
    work.mkdir(parents=True, exist_ok=True)
    db_path = work / "graph.db"
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"
    os.environ.setdefault("TAVILY_SEARCH_DEPTH", "basic")
    os.environ.setdefault("TAVILY_TIMEOUT_SECONDS", "30")
    get_settings.cache_clear()
    reset_db_session_state()
    # Real provider + real DeepSeek (do NOT stub).
    real_nodes.set_advisory_backfill_override(enabled=False, mode="shadow")
    real_nodes.set_structured_shadow_override(enabled=False, mode="shadow")

    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ResearchGraphRunner(session).run(GraphAnalyzeRequest(
            query=CASES["case_02"], max_rounds=1, max_loop_count=1,
            execution_mode="provider_backed",
        ))

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT state_json FROM research_graph_checkpoints ORDER BY id DESC"
    ).fetchall()
    con.close()
    state = {}
    for row in rows:
        state = json.loads(row["state_json"] or "{}")
        if isinstance(state, dict) and state.get("run_id"):
            break
    store = RunEvaluationStore.from_dict(state.get("evaluation_store") or {})
    coverage = build_evaluable_coverage_report(store)
    gaps, _ = derive_gaps(coverage, store)
    drafts = state.get("drafts") or []
    legacy = ""
    if drafts:
        legacy = str(drafts[-1].get("report_markdown") or "")
    if not legacy:
        legacy = str((state.get("final_report") or {}).get("report_markdown") or "")

    result = run_structured_compare(
        store=store, coverage_report=coverage, research_gaps=gaps,
        legacy_markdown=legacy, llm_call=real_section_llm_call,
        run_id="case_02__generated", output_dir=str(work), max_retries=1,
        use_fewshot=False,
    )
    (work / "legacy_markdown.md").write_text(legacy, encoding="utf-8")
    (work / "structured_markdown.md").write_text(
        result["structured_markdown"], encoding="utf-8")
    return result["structured_markdown"], legacy


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", default=list(CASES))
    ap.add_argument("--seed", type=int, default=20260804)
    ap.add_argument("--no-case2-graph", action="store_true",
                    help="skip the real case_02 graph run if no legacy exists")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    mapping: dict[str, dict[str, str]] = {}
    csv_rows: list[dict] = []

    for case_id in args.cases:
        pair = _existing_pair(case_id)
        if pair is None and case_id == "case_02" and not args.no_case2_graph:
            print(f"[{case_id}] generating real legacy + structured pair ...")
            pair = _real_case02_pair()
        if pair is None:
            print(f"[{case_id}] WARN: no legacy present; skipping (legacy empty).")
            continue
        structured_md, legacy_md = pair
        # random A/B assignment
        if rng.random() < 0.5:
            a, b = structured_md, legacy_md
            mapping[case_id] = {"A": "structured", "B": "legacy"}
        else:
            a, b = legacy_md, structured_md
            mapping[case_id] = {"A": "legacy", "B": "structured"}

        d = OUT / case_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "report_A.md").write_text(a, encoding="utf-8")
        (d / "report_B.md").write_text(b, encoding="utf-8")
        (d / "review_form.md").write_text(
            REVIEW_FORM_TEMPLATE.format(case_id=case_id), encoding="utf-8")

        csv_rows.append({
            "case_id": case_id, "report_variant": "A", "core_question_coverage": "",
            "key_fact_completeness": "", "evidence_boundary": "",
            "research_narrative": "", "conciseness": "", "readability": "",
            "critical_omission": "", "unsupported_inference": "",
            "preferred_version": "", "review_notes": "",
        })
        csv_rows.append({
            "case_id": case_id, "report_variant": "B", "core_question_coverage": "",
            "key_fact_completeness": "", "evidence_boundary": "",
            "research_narrative": "", "conciseness": "", "readability": "",
            "critical_omission": "", "unsupported_inference": "",
            "preferred_version": "", "review_notes": "",
        })

    # Blind mapping saved separately; NOT printed to console.
    (OUT / "blind_mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")

    import csv

    with (OUT / "human_review.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)

    (OUT / "C3_MANUAL_REVIEW_SUMMARY.md").write_text(
        "# C.3.2 Manual Blind A/B Review — Summary\n\n"
        "Reviewer 填写 human_review.csv 后，把 6 维均分 / 严重问题 / 总体判断汇总到这里。\n"
        "盲审完成前不要打开 blind_mapping.json。\n\n"
        f"涉及 case: {', '.join(mapping.keys())}（mapping 见 blind_mapping.json）\n",
        encoding="utf-8",
    )
    print(f"\n[DONE] -> {OUT}  (DO NOT open blind_mapping.json until review is done)")


if __name__ == "__main__":
    main()
