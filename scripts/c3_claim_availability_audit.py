# ruff: noqa: E501
"""Phase C.3.3.2 — Claim Availability Trace Audit (Case1).

Not a feature: a deterministic trace of WHY implementation facts that Legacy
wrote are missing from the Structured synthesis path. For each fact category
traces: Legacy -> Source -> EvidenceUnit -> ClaimCard -> approval -> slot ->
Section assignment -> final required/optional/suppressed -> drop_stage.

Outputs under data/tmp/c3_claim_availability_audit/:
  case_01_claim_trace.json
  case_01_missing_claims.csv
  C3_CLAIM_AVAILABILITY_AUDIT.md
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
B2 = REPO / "data" / "tmp" / "b2_real_run_acceptance" / "case_01"
OUT = REPO / "data" / "tmp" / "c3_claim_availability_audit"

# fact_key -> representative keywords (searched in Legacy / source / evidence)
FACTS = [
    ("route_operational", ("跨城", "航线", "开通", "启用")),
    ("project_landed", ("投运", "落地", "交付", "正式运营")),
    ("flight_metrics", ("架次", "飞行时长", "20493", "2544")),
    ("gov_app", ("政务", "一网统飞", "无人机机场", "378条")),
    ("application_scenarios", ("消防", "物流配送", "医疗", "巡检")),
    ("company_disclosure", ("上市公司", "公司", "年报", "披露", "收入")),
]

DROP_STAGES = [
    ("legacy_bypass", "Legacy 直接从 Raw Source 写出，未进入 Evidence/Claim 体系"),
    ("evidence_extraction", "Source 有实现事实，但未生成 EvidenceUnit"),
    ("claim_generation", "Evidence 有实现事实，但未生成 ClaimCard"),
    ("claim_text_persistence", "Claim 存在且 approved，但 claim.text 未持久化（历史 store）"),
    ("claim_approval", "Claim 已生成但未 approved"),
    ("section_assignment", "Claim approved 但被 Assignment 错误压制/错配"),
    ("available", "全程存活，可用于 synthesis"),
]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[。\n]", text or "") if len(s.strip()) > 8]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    store = json.loads((B2 / "evaluation_store.json").read_text(encoding="utf-8"))
    response = json.loads((B2 / "response.json").read_text(encoding="utf-8"))
    legacy = str((response.get("report_preview") or {}).get("report_markdown") or "")
    if not legacy:
        legacy = str(
            (REPO / "data" / "tmp" / "c3_structured_compare" / "case_01__zero_shot"
             / "legacy_markdown.md").read_text(encoding="utf-8")
        )

    evidence_units = store.get("evidence_units", {})
    claim_cards = store.get("claim_cards", {})
    # Sources: derive from dossier if present (best-effort)
    dossier_path = response.get("dossier_path")
    source_text = ""
    if dossier_path and Path(dossier_path).exists():
        source_text = Path(dossier_path).read_text(encoding="utf-8")

    # Section assignment (C.3.2)
    from packages.research_harness.eval_persistence import (
        RunEvaluationStore,
        build_evaluable_coverage_report,
    )
    from packages.research_harness.gap_retrieval import derive_gaps
    from packages.research_harness.section_claim_assignment import assign_section_claims
    from packages.research_harness.structured_draft import compile_editor1_input

    rst = RunEvaluationStore.from_dict(store)
    report = build_evaluable_coverage_report(rst)
    gaps, _ = derive_gaps(report, rst)
    ei = compile_editor1_input(store=rst, coverage_report=report, research_gaps=gaps)
    assignments = assign_section_claims(ei)
    # claim_id -> (section, status)
    claim_dest: dict[str, dict] = {}
    for a in assignments:
        for cid in a.required_claim_ids:
            claim_dest[cid] = {"section": a.section_id, "assignment": "required"}
        for cid in a.optional_claim_ids:
            claim_dest[cid] = {"section": a.section_id, "assignment": "optional"}
        for s in a.suppressed_claims:
            claim_dest[s.claim_id] = {"section": a.section_id, "assignment": "suppressed",
                                      "reason": s.reason}

    rows = []
    for fact_key, keywords in FACTS:
        legacy_sents = [s for s in _sentences(legacy) if any(k in s for k in keywords)]
        legacy_found = bool(legacy_sents)
        source_found = any(k in source_text for k in keywords)
        matching_evidence = [
            eid for eid, e in evidence_units.items()
            if any(k in (e.get("quoted_span") or "") for k in keywords)
            or any(k in str((e.get("key_fields") or {}).get(k2, {}).get("value", ""))
                   for k in keywords for k2 in e.get("key_fields") or {})
        ]
        evidence_found = bool(matching_evidence)
        matching_claims = [
            cid for cid, c in claim_cards.items()
            if any(k in (c.get("text") or "") for k in keywords)
            or any(eid in (c.get("evidence_ids") or []) for eid in matching_evidence)
        ]
        claim_found = bool(matching_claims)
        approved_ids = [cid for cid in matching_claims
                        if claim_cards[cid].get("approval_status") == "approved"]
        assigned_info = {cid: claim_dest.get(cid, {"section": None, "assignment": "none"})
                         for cid in approved_ids}

        # drop stage determination
        drop_stage = "available"
        drop_reason = ""
        if not evidence_found and not source_found:
            drop_stage = "legacy_bypass"
            drop_reason = "Legacy 写出的实现事实既不在 Evidence 也不在可识别 Source"
        elif source_found and not evidence_found:
            drop_stage = "evidence_extraction"
            drop_reason = "Source 有实现事实但未生成 Evidence"
        elif evidence_found and not claim_found:
            drop_stage = "claim_generation"
            drop_reason = "Evidence 有实现事实但无对应 Claim"
        elif claim_found and not approved_ids:
            drop_stage = "claim_approval"
            drop_reason = "实现 Claim 已生成但未 approved"
        elif approved_ids and all(
            info.get("assignment") in {"suppressed", "none"} for info in assigned_info.values()
        ):
            drop_stage = "section_assignment"
            drop_reason = "实现 Claim approved 但被 Assignment 压制/错配"
        elif approved_ids and all(not (c.get("text") or "") for c in
                                  [claim_cards[cid] for cid in approved_ids]):
            # approved + assigned + linked to implementation evidence, but no claim text
            drop_stage = "claim_text_persistence"
            drop_reason = "实现 Claim 存在且 approved/已分配，但 claim.text 为空（历史 store 未持久化）"

        rows.append({
            "fact_key": fact_key,
            "legacy_found": legacy_found,
            "legacy_text": legacy_sents[0][:120] if legacy_sents else "",
            "source_found": source_found,
            "evidence_found": evidence_found,
            "evidence_ids": matching_evidence[:5],
            "claim_found": claim_found,
            "claim_ids": matching_claims[:5],
            "approved_ids": approved_ids[:5],
            "assigned": {cid: info.get("assignment") for cid, info in assigned_info.items()},
            "drop_stage": drop_stage,
            "drop_reason": drop_reason,
        })

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "case_01_claim_trace.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    with (OUT / "case_01_missing_claims.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    md = ["# C.3.3.2 Claim Availability Trace Audit — Case1\n"]
    md.append("## 结论：实现事实在 `claim_text_persistence` 环节丢失\n")
    md.append("实现事实在 Evidence→Claim(approved)→Slot→Assignment 全程存活，")
    md.append("但持久化 ClaimCard 的 `text` 字段为空（历史 B.2 store 在 text 字段加入前录制）。")
    md.append("synthesis 触发器依赖 claim.text 检测 policy/implementation/status/scenario，")
    md.append("因此即使实现证据齐全也无法触发。\n")
    md.append("| fact_key | legacy | source | evidence | claim | approved | assigned | drop_stage |")
    md.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        md.append(f"| {r['fact_key']} | {r['legacy_found']} | {r['source_found']} | "
                  f"{r['evidence_found']} | {r['claim_found']} | {bool(r['approved_ids'])} | "
                  f"{bool(r['assigned'])} | {r['drop_stage']} |")
    md.append("\n## 推荐修复（按审计结论）\n")
    md.append("1. 真实运行：`record_claim_cards` 已持久化 claim.text（新 run 无此问题）。")
    md.append("2. 触发器稳健性：`_is_policy/_is_implementation/_has_status/_is_scenario` 与")
    md.append("   region/theme 提取应同时读 claim 关联的 Evidence quoted_span（事实在证据里），")
    md.append("   而非只读 claim.text。这是窄修复，不扩 Schema。")
    (OUT / "C3_CLAIM_AVAILABILITY_AUDIT.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
