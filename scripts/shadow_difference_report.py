# ruff: noqa: E501
"""Phase A2.5 — Real-data Shadow Difference Report.

Reads RECORDED graph checkpoints (no re-networking) for the frozen eval cases,
extracts real sources (full_text from source payload), runs the deterministic
shadow content clusterer, and reports:

- raw vs distinct content counts + reduction_rate
- duplicate cluster / candidate / revision-candidate distribution
- per-SOURCE-FAMILY count differences (clearly labeled, NOT fake slots)
- per-CLAIM-SLOT count differences (real slots from Contract + claims,
  aggregation_level=claim_slot)
- slots that flip raw satisfied -> shadow insufficient, with affected claim_ids
- a manual-audit sample (all auto-merge pairs + candidates) for human review

Shadow only: nothing here changes the formal source_count / claim / gate / report.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from packages.research_harness.real_nodes import _attach_shadow_slot_counts_from_claims
from packages.research_harness.research_contract import compile_research_contract
from packages.research_harness.source_cluster import cluster_sources, slot_source_counts

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ["M03", "M12", "P04", "P08", "C01", "K07"]


def _load_run(db_path: Path) -> dict:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    sources = []
    for r in cur.execute("SELECT * FROM research_graph_sources").fetchall():
        payload = json.loads(r["payload_json"] or "{}")
        sources.append({
            "source_id": r["source_id"],
            "url": r["url"] or "",
            "title": r["title"] or "",
            "source_family": r["source_family"] or "",
            "source_tier": r["source_tier"] or "",
            "published_date": r["published_date"] or None,
            "full_text": payload.get("full_text") or payload.get("raw_text") or "",
            "source_quality": payload.get("source_quality_v2") or {},
        })

    evidence = []
    for r in cur.execute("SELECT * FROM research_graph_evidence_items").fetchall():
        evidence.append({
            "evidence_id": r["evidence_id"],
            "source_id": r["source_id"],
            "support_strength": r["support_strength"],
            "source_ids": list(json.loads(r["source_ids_json"] or "[]")),
        })

    claims = []
    for r in cur.execute("SELECT * FROM research_graph_claims").fetchall():
        claims.append({
            "claim_id": r["claim_id"],
            "text": r["text"] or "",
            "required_source_family": r["required_source_family"] or "",
            "evidence_ids": list(json.loads(r["evidence_ids_json"] or "[]")),
            "supported": bool(r["supported"]),
        })

    plan = None
    cp = cur.execute("SELECT state_json FROM research_graph_checkpoints LIMIT 1").fetchone()
    if cp:
        state = json.loads(cp["state_json"] or "{}")
        plan = state.get("plan") if isinstance(state.get("plan"), dict) else None

    # Evidence may reference ReAct-backfilled sources not in the sources table.
    # Add them as content-less singletons (cannot cluster) so slot counts stay
    # internally consistent (raw == distinct for those).
    known_ids = {s["source_id"] for s in sources}
    for r in cur.execute("SELECT source_id, source_ids_json FROM research_graph_evidence_items").fetchall():
        for sid in [r["source_id"], *list(json.loads(r["source_ids_json"] or "[]"))]:
            if sid and str(sid) not in known_ids:
                sources.append({
                    "source_id": str(sid),
                    "url": "",
                    "title": "",
                    "source_family": "unknown",
                    "source_tier": "",
                    "published_date": None,
                    "full_text": "",
                    "source_quality": {},
                })
                known_ids.add(str(sid))

    con.close()
    return {"sources": sources, "evidence": evidence, "claims": claims, "plan": plan}


def _slot_min_evidence_map(contract: dict) -> dict[str, int]:
    return {
        s["slot_id"]: int(s.get("min_evidence") or 1)
        for sec in contract.get("sections", [])
        for s in sec.get("claim_slots", [])
    }


def _analyze_case(db_path: Path) -> dict:
    run = _load_run(db_path)
    sources = run["sources"]
    if not sources:
        return {"case": db_path.stem, "error": "no_sources"}
    cluster_output = cluster_sources(sources)
    src_family_by_id = {
        str(s["source_id"]): str(s["source_family"] or "unknown") for s in sources
    }

    # per-family counts (correct level)
    sources_by_family: dict[str, list[str]] = {}
    for sid, fam in src_family_by_id.items():
        sources_by_family.setdefault(fam, []).append(sid)
    family_counts = slot_source_counts(sources_by_family, cluster_output)

    # per-claim-slot counts (real slots)
    slot_counts = []
    slot_min_evidence = {}
    slot_impacts = []
    affected_claim_ids_map: dict[str, list[str]] = {}
    plan = run["plan"]
    if plan and run["claims"]:
        contract = compile_research_contract(plan)
        slot_min_evidence = _slot_min_evidence_map(contract)
        shadow = {
            "report": {},
            "family_counts": [],
            "slot_counts": [],
            "aggregation_level": "source_family_fallback",
            "cluster_count": len(cluster_output["clusters"]),
            "candidate_count": len(cluster_output["candidates"]),
            "revision_candidate_count": len(cluster_output["revision_candidates"]),
            "duplicate_removed_count": cluster_output["raw_source_count"] - cluster_output["shadow_duplicate_adjusted_source_count"],
        }
        state = {"plan": plan, "claims": run["claims"], "evidence": run["evidence"]}
        shadow = _attach_shadow_slot_counts_from_claims(
            state=state, shadow=shadow, sources=sources
        )
        slot_counts = shadow["slot_counts"]
        for row in slot_counts:
            sid = row["slot_id"]
            min_ev = slot_min_evidence.get(sid)
            raw = row["raw_supporting_source_count"]
            distinct = row["distinct_supporting_content_count"]
            if min_ev is not None and raw >= min_ev and distinct < min_ev:
                slot_impacts.append({
                    "slot_id": sid,
                    "raw_supporting_source_count": raw,
                    "distinct_supporting_content_count": distinct,
                    "min_evidence": min_ev,
                    "raw_status": "satisfied",
                    "shadow_status": "insufficient",
                    "affected_claim_ids": row.get("affected_claim_ids", []),
                })
                affected_claim_ids_map[sid] = row.get("affected_claim_ids", [])

    # cluster distribution
    singleton = sum(1 for c in cluster_output["clusters"] if len(c["source_ids"]) == 1)
    duplicate = sum(1 for c in cluster_output["clusters"] if len(c["source_ids"]) > 1)

    # manual-audit sample: auto-merged pairs + candidates
    audit_pairs = []
    for c in cluster_output["clusters"]:
        if len(c["source_ids"]) > 1:
            for sid in c["source_ids"][1:]:
                audit_pairs.append({
                    "kind": "auto_merge",
                    "cluster_id": c["content_cluster_id"],
                    "representative": c["cluster_representative_source_id"],
                    "source_id": sid,
                    "confidence": c["duplicate_confidence"],
                    "reason": c["duplicate_reason"],
                })
    for cand in cluster_output["candidates"]:
        audit_pairs.append({
            "kind": "candidate",
            "cluster_id": cand["content_cluster_id"],
            "representative": cand["representative_source_id"],
            "source_id": cand["source_id"],
            "confidence": cand["duplicate_confidence"],
            "reason": cand["duplicate_reason"],
        })

    reduction = (
        round(1.0 - cluster_output["shadow_duplicate_adjusted_source_count"] / max(1, cluster_output["raw_source_count"]), 4)
        if cluster_output["raw_source_count"] else 0.0
    )

    # ── invariants (review 2026-08-04) ──
    invariants: list[str] = []
    has_multi_member = any(len(c.get("source_ids", [])) > 1 for c in cluster_output["clusters"])
    if not has_multi_member:
        if cluster_output["raw_source_count"] != cluster_output["shadow_distinct_content_count"]:
            invariants.append(
                "TASK: no multi-member cluster but raw_source_count != distinct_content_count "
                f"({cluster_output['raw_source_count']} vs {cluster_output['shadow_distinct_content_count']})"
            )
    for row in slot_counts:
        ev = row.get("supporting_evidence_count", 0)
        raw = row.get("raw_supporting_source_count", 0)
        distinct = row.get("distinct_supporting_content_count", 0)
        if not (distinct <= raw <= ev):
            invariants.append(
                f"SLOT {row['slot_id']}: distinct({distinct}) <= raw({raw}) <= evidence({ev}) violated"
            )

    return {
        "case": db_path.stem,
        "task_summary": {
            "raw_source_count": cluster_output["raw_source_count"],
            "distinct_content_count": cluster_output["shadow_distinct_content_count"],
            "reduction_rate": reduction,
            "duplicate_removed_count": cluster_output["raw_source_count"] - cluster_output["shadow_duplicate_adjusted_source_count"],
        },
        "cluster_distribution": {
            "singleton_clusters": singleton,
            "duplicate_clusters": duplicate,
            "candidate_pairs": len(cluster_output["candidates"]),
            "revision_candidates": len(cluster_output["revision_candidates"]),
        },
        "family_counts": family_counts,
        "slot_counts": slot_counts,
        "slot_min_evidence": {k: v for k, v in slot_min_evidence.items() if k in {r["slot_id"] for r in slot_counts}},
        "slot_impacts": slot_impacts,
        "affected_claim_ids": affected_claim_ids_map,
        "audit_pairs": audit_pairs,
        "aggregation_level": "claim_slot" if slot_counts else "source_family_fallback",
        "invariants": invariants,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="A2.5 real-data shadow difference report")
    ap.add_argument("--cases", nargs="+", default=DEFAULT_CASES)
    ap.add_argument("--run-dir", default="data/tmp/resume_eval_A_6b")
    ap.add_argument("--output-dir", default="data/tmp/shadow_difference_report")
    args = ap.parse_args()

    out_dir = REPO / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = REPO / args.run_dir

    per_case = []
    for qid in args.cases:
        db = run_dir / f"{qid}.db"
        if not db.exists():
            print(f"[SKIP] {qid}: no {db}")
            continue
        result = _analyze_case(db)
        per_case.append(result)
        print(f"[OK] {qid}: raw={result['task_summary']['raw_source_count']} "
              f"distinct={result['task_summary']['distinct_content_count']} "
              f"reduction={result['task_summary']['reduction_rate']} "
              f"slots={len(result['slot_counts'])} impacts={len(result['slot_impacts'])}")

    total_raw = sum(r["task_summary"]["raw_source_count"] for r in per_case if "error" not in r)
    total_distinct = sum(r["task_summary"]["distinct_content_count"] for r in per_case if "error" not in r)

    all_audit = [p for r in per_case if "error" not in r for p in r["audit_pairs"]]
    report = {
        "clustering_version": "source_cluster_v1",
        "thresholds": {"auto_merge": 0.90, "candidate": 0.78},
        "input": {"run_dir": str(run_dir), "cases": args.cases, "network_allowed": False},
        "task_summary": {
            "task_count": len(per_case),
            "raw_source_count": total_raw,
            "distinct_content_count": total_distinct,
            "reduction_rate": round(1.0 - total_distinct / max(1, total_raw), 4),
        },
        "per_case": per_case,
        "manual_audit": {
            "pairs_available_for_review": len(all_audit),
            "auto_merge_pairs": sum(1 for p in all_audit if p["kind"] == "auto_merge"),
            "candidate_pairs": sum(1 for p in all_audit if p["kind"] == "candidate"),
            "note": "人工审查 ≥50 real pairs 后再更新 precision/false_merge; 当前报告不以此作为验收",
        },
    }
    (out_dir / "shadow_difference_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "audit_pairs.jsonl").write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in all_audit), encoding="utf-8"
    )
    print(f"\n[DONE] report -> {out_dir / 'shadow_difference_report.json'}")
    print(f"[DONE] audit pairs -> {out_dir / 'audit_pairs.jsonl'} ({len(all_audit)} pairs)")


if __name__ == "__main__":
    main()
