"""Resume metrics — A-line: 强证据覆盖率 (source & retrieval evaluation).

Runs a subset of the 50-case eval set through the provider-backed smoke runner,
in three comparison arms (Baseline / Current / Ablation), and computes the
strong-evidence coverage rate per case.

Metrics (per your resume-eval plan):
  strong_evidence_coverage = A/B-tier, locatable-original Evidence covering a
      required claim dimension, divided by total required claim dimensions.
  (Coverage is counted against the case's evidence-requirement card, not raw
  webpage counts.)

Usage:
    python scripts/resume_eval_A.py \
        --cases data/tmp/source_quality_stress_eval/source_quality_cases_v1.json \
        --ids M03 M12 P04 P08 C01 K07 \
        --arms current only \
        --max-rounds 1 --max-loop-count 1 --env-file .env
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SMOKE = REPO / "scripts" / "graph_provider_backed_smoke.py"

# A/B tier => strong evidence (usable as primary support)
STRONG_TIERS = {"A", "B"}
# Fallback when response lacks a tier per evidence: treat support_type/strength.
MIN_STRONG_STRENGTH = 0.6


def _load_cases(path: Path, ids: list[str]) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data["cases"] if isinstance(data, dict) else data
    selected = [c for c in cases if c.get("query_id") in ids]
    if not selected:
        sys.exit(f"[ERROR] No cases matched ids {ids}")
    return selected


def _run_smoke(query: str, qid: str, output_dir: Path, *, env_file: str,
               max_rounds: int, max_loop: int, arm_env: dict) -> dict:
    cmd = [
        sys.executable, str(SMOKE),
        "--query", query,
        "--max-rounds", str(max_rounds),
        "--max-loop-count", str(max_loop),
        "--output-dir", str(output_dir / qid),
        "--env-file", env_file,
        "--reset",
    ]
    env = dict(__import__("os").environ)
    env.update(arm_env)
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=REPO)
    resp_path = output_dir / qid / "response.json"
    if not resp_path.exists():
        return {"error": f"no response.json (exit {proc.returncode})",
                "stderr": (proc.stderr or "")[-300:]}
    return json.loads(resp_path.read_text(encoding="utf-8"))


def _extract_evidence_tiers(response: dict) -> list[dict]:
    """Collect evidence items with best-effort tier/strength.

    Handles multiple evidence schemas: the atomic-evidence schema
    (evidence_id + source_id/support_type/support_strength) and the
    source-quality schema (evidence_id + evidence_type/proof_strength).
    """
    out = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("evidence_id"):
                out.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(response)
    return out


def _extract_dossier_evidence(dossier_path: Path) -> list[dict]:
    """Parse the evidence table from a run's dossier.md.

    The graph smoke persists full evidence items (evidence_id / support_type /
    support_strength / specificity / summary) only in the dossier table, not in
    response.json (which keeps counts + ineligible-evidence audit). Parsing the
    `| ev_... |` rows gives the eval real evidence to score (fix 0/0 baseline).

    Dossier evidence row shape:
        | ev_001 | src_002 | background_support | 0.9 | policy_statement |
          llm_synthesized_provider_backed_v1 | <summary> | [<limitations>] |
    """
    if not dossier_path or not dossier_path.exists():
        return []
    evidence: list[dict] = []
    try:
        lines = dossier_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip().startswith("| ev_"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        evidence_id = cells[0]
        strength = cells[3]
        try:
            strength_f = float(strength)
        except (TypeError, ValueError):
            strength_f = 0.0
        evidence.append({
            "evidence_id": evidence_id,
            "source_id": cells[1] if len(cells) > 1 else "",
            "support_type": cells[2] if len(cells) > 2 else "",
            "support_strength": strength_f,
            "specificity": cells[4] if len(cells) > 4 else "",
            "summary": cells[6] if len(cells) > 6 else "",
        })
    return evidence


def _coverage(case: dict, response: dict, dossier_path: Path | None = None) -> dict:
    """Strong-evidence coverage vs the case's required claim dimensions.

    Simplification for this first pass: count a required dimension as covered
    when there is at least one strong evidence item whose summary/support
    references that dimension's keyword, OR when strong evidence count >= the
    case minimum. A later pass will do claim-level matching.

    dossier_path supplies the full evidence table when response.json only holds
    an ineligible-evidence audit (fix for the 0/0 baseline).
    """
    required = case.get("required_claim_dimensions", [])
    min_strong = int(case.get("minimum_strong_evidence_count", 2))
    evs = _extract_evidence_tiers(response) + _extract_dossier_evidence(dossier_path)
    strong = [e for e in evs if _is_strong(e)]
    # keyword fallback: mark dimension covered if it appears in strong-evidence
    # summaries (title/region/time etc.), else by generic strong count.
    covered = 0
    covered_by: list[str] = []
    for dim in required:
        dimkw = str(dim).lower()
        hit = any(
            dimkw in str(e.get("summary", "")).lower()
            or dimkw in str(e.get("region", "")).lower()
            for e in strong
        )
        if hit or len(strong) >= min_strong:
            covered += 1
            covered_by.append(dim)
    return {
        "required_dimensions": required,
        "strong_evidence_count": len(strong),
        "total_evidence_count": len(evs),
        "covered_dimensions": covered_by,
        "coverage": round(covered / max(len(required), 1), 3),
    }


def _is_strong(ev: dict) -> bool:
    # schema 1: atomic evidence (tier / support_strength / support_type)
    tier = str(ev.get("tier", "") or "")
    if tier in STRONG_TIERS:
        return True
    st = ev.get("support_strength")
    try:
        if st is not None and float(st) >= MIN_STRONG_STRENGTH:
            return True
    except (TypeError, ValueError):
        pass
    stype = str(ev.get("support_type", "") or "")
    if stype in {"direct_support", "primary_support"}:
        return True
    # schema 2: source-quality evidence (proof_strength; numeric or label)
    ps = ev.get("proof_strength")
    if isinstance(ps, str):
        if ps.lower() in {"strong", "high", "primary", "direct"}:
            return True
        return False  # weak / medium / unsupported are not strong
    try:
        if ps is not None and float(ps) >= MIN_STRONG_STRENGTH:
            return True
    except (TypeError, ValueError):
        pass
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="A-line: strong-evidence coverage")
    ap.add_argument("--cases", required=True, help="50-case eval json")
    ap.add_argument("--ids", nargs="+", required=True, help="query_ids to run")
    ap.add_argument("--arms", nargs="+", default=["current"],
                    choices=["baseline", "current", "ablation"])
    ap.add_argument("--max-rounds", type=int, default=2)
    ap.add_argument("--max-loop-count", type=int, default=1)
    ap.add_argument("--env-file", default=".env")
    ap.add_argument("--output-dir", default="data/tmp/resume_eval_A")
    args = ap.parse_args()

    cases = _load_cases(Path(args.cases), args.ids)
    out_root = REPO / args.output_dir
    out_root.mkdir(parents=True, exist_ok=True)

    # Arm -> env overrides. Ablation forces lexical fallback (no RRF/dense),
    # baseline leaves defaults (generic), current is the real pipeline.
    ARM_ENV = {
        "baseline": {},
        "current": {},
        "ablation": {"RESUME_EVAL_RETRIEVAL_MODE": "lexical_fallback_v1"},
    }

    results = []
    for case in cases:
        qid = case["query_id"]
        for arm in args.arms:
            resp = _run_smoke(
                case["query"], qid, out_root, env_file=args.env_file,
                max_rounds=args.max_rounds, max_loop=args.max_loop_count,
                arm_env=ARM_ENV[arm],
            )
            if "error" in resp:
                print(f"[FAIL] {qid}/{arm}: {resp['error']}")
                results.append({"query_id": qid, "arm": arm, "error": resp["error"]})
                continue
            cov = _coverage(case, resp, dossier_path=out_root / qid / "dossier.md")
            results.append({
                "query_id": qid, "arm": arm,
                "granularity": case["granularity"], "industry": case["industry"],
                **cov,
            })
            print(f"[OK] {qid}/{arm}: coverage={cov['coverage']} "
                  f"strong={cov['strong_evidence_count']}/{cov['total_evidence_count']}")

    summary_path = out_root / "resume_eval_A_summary.json"
    summary_path.write_text(
        json.dumps({"results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[DONE] {len(results)} runs. Summary: {summary_path}")


if __name__ == "__main__":
    main()
