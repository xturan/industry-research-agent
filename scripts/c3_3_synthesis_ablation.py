# ruff: noqa: E501
"""Phase C.3.3 — Synthesis Ablation blind-review package (Case1 only).

From the SAME validated StructuredDraft derives two markdown versions that
differ ONLY in whether synthesis paragraphs are present:

  without_synthesis = factual + gap paragraphs
  with_synthesis    = factual + gap + synthesis paragraphs

The factual/gap paragraphs are NOT regenerated (they are shared verbatim), so
the only experimental variable is the presence of `paragraph_role == "synthesis"`.

Outputs data/tmp/c3_3_synthesis_ablation/:
  case_01/{report_A.md, report_B.md, review_form.md, invariant_check.json,
           synthesis_contract.json}
  blind_mapping.json            (A/B -> with/without; open after review)
  C3_3_SYNTHESIS_ABLATION_SUMMARY.md

Note: this round covers ONLY `implementation_to_stage` (the type that fired on
Case1). policy_to_implementation / cross_source_corroboration are uncovered.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from packages.research_harness.structured_compare import render_structured_draft_markdown
from packages.research_harness.structured_draft import (
    DraftParagraph,
    DraftSection,
    StructuredDraft,
)

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "data" / "tmp" / "c3_structured_compare" / "case_01__zero_shot"
OUT = REPO / "data" / "tmp" / "c3_3_synthesis_ablation"

REVIEW_FORM = """# case_01 — Synthesis Ablation 盲审

请先读 report_A.md 与 report_B.md（同一事实段，仅差异：是否含 synthesis 段）。
填写前不要打开 blind_mapping.json。只评价"有无 synthesis"的增益。

## 六维评分（1–5，5=最好；N/A 若无 synthesis 段则该项留空）

| 维度 | A | B | 备注 |
| --- | --- | --- | --- |
| 综合价值 |  |  | 是否说明多个事实共同意味着什么 |
| 非重复性 |  |  | 是否只是把 factual 段重说一遍 |
| 衔接自然度 |  |  | 是否自然连接本节事实 |
| 阅读收益 |  |  | 删除该段后是否明显损失理解 |

## 通过/不通过（对含 synthesis 的版本）

- 证据边界：通过 / 不通过（是否保留"尚不足以判断是否进入规模化商业运营阶段"）
- 阶段判断：通过 / 不通过（是否只表达"观察到初步实施迹象"，未越级为成熟/规模化/稳定商业化）

## 严重问题（记录出现于哪一版）

- 新事实：
- 新数字：
- 因果越界：
- 阶段越级：
- 重复事实：
- 空泛总结：
- 表述生硬：

## 最终偏好

- A / B / 无明显差异
- with_synthesis 是否**明显优于** without_synthesis：是 / 否 / 不确定
- 评语：
"""


def _draft_from_dict(d: dict) -> StructuredDraft:
    sections = []
    for s in d.get("sections", []):
        paragraphs = [
            DraftParagraph(
                paragraph_id=p["paragraph_id"], text=p["text"],
                claim_ids=tuple(p.get("claim_ids", [])),
                evidence_ids=tuple(p.get("evidence_ids", [])),
                assertion_level=p.get("assertion_level", "mentioned"),
                limitations=tuple(p.get("limitations", [])),
                paragraph_role=p.get("paragraph_role", "factual"),
                numeric_mentions=tuple(p.get("numeric_mentions", [])),
                synthesis_id=p.get("synthesis_id", ""),
            )
            for p in s.get("paragraphs", [])
        ]
        sections.append(DraftSection(
            section_id=s["section_id"], title=s.get("title", s["section_id"]),
            readiness_at_write=s.get("readiness_at_write", "ready"),
            paragraphs=tuple(paragraphs),
        ))
    return StructuredDraft(
        draft_id=d.get("draft_id", ""), run_id=d.get("run_id", ""),
        draft_version=d.get("draft_version", 1),
        report_title=d.get("report_title", ""), sections=tuple(sections),
        unused_claim_ids=tuple(d.get("unused_claim_ids", [])),
        unresolved_gap_ids=tuple(d.get("unresolved_gap_ids", [])),
    )


def _strip_synthesis(draft: StructuredDraft) -> StructuredDraft:
    sections = tuple(
        DraftSection(
            section_id=s.section_id, title=s.title,
            readiness_at_write=s.readiness_at_write,
            paragraphs=tuple(p for p in s.paragraphs if p.paragraph_role != "synthesis"),
        )
        for s in draft.sections
    )
    return StructuredDraft(
        draft_id=draft.draft_id, run_id=draft.run_id,
        draft_version=draft.draft_version, report_title=draft.report_title,
        sections=sections, unused_claim_ids=draft.unused_claim_ids,
        unresolved_gap_ids=draft.unresolved_gap_ids,
    )


def _non_synthesis_paras(draft: StructuredDraft) -> list[tuple]:
    return [
        (p.paragraph_id, p.text, p.claim_ids, p.evidence_ids, p.limitations,
         p.assertion_level, p.numeric_mentions)
        for s in draft.sections for p in s.paragraphs if p.paragraph_role != "synthesis"
    ]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    src = json.loads((SRC / "structured_draft.json").read_text(encoding="utf-8"))
    draft_full = _draft_from_dict(src)
    draft_without = _strip_synthesis(draft_full)

    # Invariant check: non-synthesis paragraphs must be byte-identical.
    a = _non_synthesis_paras(draft_full)
    b = _non_synthesis_paras(draft_without)
    invariant = {
        "same_factual_paragraphs": a == b,
        "same_gap_paragraphs": a == b,
        "same_claim_ids": [p[2] for p in a] == [p[2] for p in b],
        "same_evidence_ids": [p[3] for p in a] == [p[3] for p in b],
        "same_numeric_mentions": [p[6] for p in a] == [p[6] for p in b],
        "same_limitations": [p[4] for p in a] == [p[4] for p in b],
        "same_section_order": [s.section_id for s in draft_full.sections]
        == [s.section_id for s in draft_without.sections],
        "only_difference": ["synthesis_paragraphs"],
    }
    assert a == b, "non-synthesis paragraphs differ -> cannot build a fair ablation"
    assert invariant["same_section_order"]

    with_md = render_structured_draft_markdown(draft_full)
    without_md = render_structured_draft_markdown(draft_without)

    synthesis_paras = [
        p for s in draft_full.sections for p in s.paragraphs if p.paragraph_role == "synthesis"
    ]
    covered = {"implementation_to_stage"} if synthesis_paras else set()
    contract_info = [{
        "synthesis_id": p.synthesis_id, "claim_ids": list(p.claim_ids),
        "evidence_ids": list(p.evidence_ids), "assertion_level": p.assertion_level,
        "limitations": list(p.limitations), "text": p.text,
    } for p in synthesis_paras]
    syn_meta = {
        "covered_synthesis_types": sorted(covered),
        "uncovered_synthesis_types": sorted(
            {"policy_to_implementation", "cross_source_corroboration"} - covered),
        "synthesis_paragraph_count": len(synthesis_paras),
        "synthesis_word_count": len(
            "".join(p.text for p in synthesis_paras).replace(" ", "")),
        "semantic_fallback_used": True,  # Case1 historical claims used verified-evidence fallback
    }

    OUT.mkdir(parents=True, exist_ok=True)
    d = OUT / "case_01"
    d.mkdir(parents=True, exist_ok=True)

    rng = random.Random(20260805)
    if rng.random() < 0.5:
        a_md, b_md = without_md, with_md
        mapping = {"case_01": {"A": "without_synthesis", "B": "with_synthesis"}}
    else:
        a_md, b_md = with_md, without_md
        mapping = {"case_01": {"A": "with_synthesis", "B": "without_synthesis"}}

    (d / "report_A.md").write_text(a_md, encoding="utf-8")
    (d / "report_B.md").write_text(b_md, encoding="utf-8")
    (d / "review_form.md").write_text(REVIEW_FORM, encoding="utf-8")
    (d / "invariant_check.json").write_text(
        json.dumps(invariant, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "synthesis_contract.json").write_text(
        json.dumps(contract_info, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "blind_mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = (
        "# C.3.3 Synthesis Ablation — Summary\n\n"
        f"covered_synthesis_types: {syn_meta['covered_synthesis_types']}\n"
        f"uncovered_synthesis_types: {syn_meta['uncovered_synthesis_types']}\n\n"
        "评审者填写 review_form.md 后，把六维评分 / 通过项 / 偏好汇总到这里。"
        "盲审完成前不要打开 blind_mapping.json。\n"
    )
    (OUT / "C3_3_SYNTHESIS_ABLATION_SUMMARY.md").write_text(summary, encoding="utf-8")

    print("=== invariant ===")
    print(json.dumps(invariant, ensure_ascii=False, indent=2))
    print("=== synthesis meta ===")
    print(json.dumps(syn_meta, ensure_ascii=False, indent=2))
    print(f"[DONE] -> {OUT}  (DO NOT open blind_mapping.json until review is done)")


if __name__ == "__main__":
    main()
