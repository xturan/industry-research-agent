"""Evidence Quality Audit — 真实端到端证据审计。

对一组真实研究 query 跑 graph-runtime pipeline（真实搜索 + LLM），从 run 输出中
提取 evidence/claims，做两层检查：

  1. 结构性（离线）：
       citation 完整性（url/title/locator/retrieved_at）
       evidence 是否有 locator
       avg evidence per claim
       来源 family 覆盖度 / 孤儿 evidence（无 claim 引用）
  2. 语义（每条 evidence）：
       relevance：本地 reranker（vLLM :8000，rerank-lora）0-4（查询↔证据）
       support  ：DeepSeek judge 证据是否支撑其声明（yes/partial/no）
       authority：DeepSeek judge 来源权威度 A/B/C/D

产出 data/tmp/evidence_quality_audit/（逐 query + 汇总）。

用法：
  python scripts/evidence_quality_audit.py [--queries n] [--max-evidence 10]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sqlalchemy.orm import Session

from packages.research_harness.runner import ResearchGraphRunner
from packages.research_harness.schemas import GraphAnalyzeRequest

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone.utc

OUT_DIR = _REPO / "data" / "tmp" / "evidence_quality_audit"
RERANK_ENDPOINT = "http://localhost:8000/v1/chat/completions"
RERANK_MODEL = "rerank-lora"

AUDIT_QUERIES = [
    "低空经济在中央层面的政策支持是否已经进入规模化落地阶段？"
    "请分别验证空域改革、适航认证、基础设施建设、地方试点和企业订单。",
    "中国数据要素和公共数据授权运营政策目前处于“制度建设”还是“财政/项目落地”阶段？"
    "请找出预算、招投标、平台建设、运营主体四类证据。",
    "半导体设备和材料国产替代是否已经从政策支持转化为订单和收入？"
    "请重点检查招投标、中标公告、客户验证、上市公司收入结构。",
]

STRUCTURAL_THRESHOLDS = {
    "citation_ratio": 0.7,
    "locator_ratio": 0.5,
    "avg_evidence_per_claim": 1.5,
    "min_source_families": 2,
}
SEMANTIC_THRESHOLDS = {
    "mean_relevance": 2.5,  # reranker 0-4
    "support_rate": 0.6,  # (yes+partial)/audited
    "authority_ok_rate": 0.6,  # A/B/C / audited
}


# ── extraction ───────────────────────────────────────────────────────────────

def _walk_collect(obj: Any, evidence: dict[str, dict], claims: dict[str, dict]) -> None:
    if isinstance(obj, dict):
        if "evidence_id" in obj and any(
            k in obj
            for k in (
                "support_text", "text", "citation", "summary", "support_strength", "source_url",
            )
        ):
            evidence[str(obj["evidence_id"])] = obj
        if "claim_id" in obj and ("text" in obj or "claim_text" in obj or "evidence_ids" in obj):
            claims[str(obj["claim_id"])] = obj
        for v in obj.values():
            _walk_collect(v, evidence, claims)
    elif isinstance(obj, list):
        for v in obj:
            _walk_collect(v, evidence, claims)


def _evidence_text(ev: dict[str, Any]) -> str:
    return str(
        ev.get("support_text")
        or ev.get("text")
        or ev.get("summary")
        or ev.get("support_strength")
        or ""
    )[:1200]


def _evidence_url(ev: dict[str, Any]) -> str:
    cit = ev.get("citation")
    if isinstance(cit, dict):
        return str(cit.get("url") or cit.get("source_url") or "")
    return str(ev.get("source_url") or "")


def _evidence_locator(ev: dict[str, Any]) -> str:
    cit = ev.get("citation")
    if isinstance(cit, dict) and cit.get("locator"):
        return str(cit.get("locator"))
    if ev.get("locator"):
        return str(ev.get("locator"))
    if ev.get("chunk_id"):
        return str(ev.get("chunk_id"))
    chunk_ids = ev.get("chunk_ids")
    if isinstance(chunk_ids, list) and chunk_ids:
        return str(chunk_ids[0])
    return ""


def _evidence_family(ev: dict[str, Any]) -> str:
    for key in ("source_family",):
        if ev.get(key):
            return str(ev[key])
    for sub in ("evidence_quality_v2", "metadata"):
        meta = ev.get(sub)
        if isinstance(meta, dict) and meta.get("source_family"):
            return str(meta["source_family"])
    return ""


def _evidence_score(ev: dict[str, Any]) -> float:
    try:
        return float(ev.get("score") or ev.get("_query_relevance_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _claim_text(claim: dict[str, Any]) -> str:
    return str(claim.get("text") or claim.get("claim_text") or "")[:600]


def _extract_from_state(
    state: dict[str, Any],
) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    """从 graph state 提取 evidence/claims/sources（checkpoint 或 run 状态）。"""
    evidence: dict[str, dict] = {}
    claims: dict[str, dict] = {}
    sources: dict[str, dict] = {}
    _walk_collect(state, evidence, claims)
    for src in state.get("sources", []) or []:
        if isinstance(src, dict) and src.get("source_id"):
            sources[str(src["source_id"])] = src
    return evidence, claims, sources


def load_checkpoint_state(checkpoint_path: str) -> dict[str, Any]:
    import json as _json

    d = _json.load(open(checkpoint_path, encoding="utf-8"))
    state = d.get("state")
    if not isinstance(state, dict):
        raise ValueError(f"no state in checkpoint {checkpoint_path}")
    return state


# ── run a real query ─────────────────────────────────────────────────────────

def run_graph(session: Session, query: str) -> dict[str, Any]:
    runner = ResearchGraphRunner(session)
    response = runner.run(
        GraphAnalyzeRequest(
            query=query,
            max_rounds=2,
            max_loop_count=1,
            execution_mode="provider_backed",
        )
    )
    evidence, claims, sources = _extract_from_state(response.model_dump(mode="json"))
    fallback = ""
    # 若 run 失败，从 checkpoint 提取失败前已构建的 evidence（verify_claims 阻塞场景）
    if not evidence and response.status == "failed":
        cp = _REPO / "data" / "graph_checkpoints" / f"run_{response.run_id}" / "latest.json"
        if cp.exists():
            try:
                state = load_checkpoint_state(str(cp))
                evidence, claims, sources = _extract_from_state(state)
                fallback = "checkpoint"
            except Exception:  # noqa: BLE001
                fallback = "checkpoint_error"
    return {
        "run_id": response.run_id,
        "status": response.status,
        "decision": response.decision,
        "quality_scores": response.quality_scores,
        "evidence": evidence,
        "claims": claims,
        "sources": sources,
        "evidence_source": fallback or ("response" if evidence else "none"),
    }


# ── structural grading ───────────────────────────────────────────────────────

def structural_grade(
    evidence: dict[str, dict], claims: dict[str, dict], sources: dict[str, dict] | None = None
) -> dict[str, Any]:
    ev_list = list(evidence.values())
    n = len(ev_list)
    if n == 0:
        return {"n_evidence": 0, "n_claims": len(claims), "checks": []}
    sources = sources or {}
    cited = 0
    locator = 0
    cit_integrity: list[float] = []
    for ev in ev_list:
        if _evidence_url(ev):
            cited += 1
        if _evidence_locator(ev):
            locator += 1
        eq = ev.get("evidence_quality_v2")
        if isinstance(eq, dict):
            ci = eq.get("citation_integrity")
            if isinstance(ci, (int, float)):
                cit_integrity.append(float(ci))
    citation_ratio = cited / n
    locator_ratio = locator / n
    mean_citation_integrity = (
        round(sum(cit_integrity) / len(cit_integrity), 3) if cit_integrity else None
    )

    claim_evidence_counts = []
    for claim in claims.values():
        ids = [str(x) for x in claim.get("evidence_ids", []) if x]
        claim_evidence_counts.append(len(ids))
    avg_evidence_per_claim = (
        round(sum(claim_evidence_counts) / len(claim_evidence_counts), 3)
        if claim_evidence_counts
        else 0.0
    )

    # source families among evidence（优先通过 source_id → source 解析）
    src_families = set()
    for ev in ev_list:
        fam = _evidence_family(ev)
        if not fam and ev.get("source_id"):
            src = sources.get(str(ev["source_id"]))
            if src:
                fam = str(src.get("source_family") or "")
        if fam:
            src_families.add(fam)
    families_covered = sorted(src_families)

    # orphan evidence: evidence_id not referenced by any claim
    ref_ids = set()
    for claim in claims.values():
        for x in claim.get("evidence_ids", []):
            ref_ids.add(str(x))
    orphan_count = sum(1 for eid in evidence if eid not in ref_ids)
    orphan_ratio = round(orphan_count / n, 3)

    checks = {
        "n_evidence": n,
        "n_claims": len(claims),
        "citation_ratio": round(citation_ratio, 3),
        "locator_ratio": round(locator_ratio, 3),
        "mean_citation_integrity": mean_citation_integrity,
        "avg_evidence_per_claim": avg_evidence_per_claim,
        "source_families": families_covered,
        "n_source_families": len(families_covered),
        "orphan_evidence_ratio": orphan_ratio,
    }
    passed = (
        citation_ratio >= STRUCTURAL_THRESHOLDS["citation_ratio"]
        and locator_ratio >= STRUCTURAL_THRESHOLDS["locator_ratio"]
        and avg_evidence_per_claim >= STRUCTURAL_THRESHOLDS["avg_evidence_per_claim"]
        and len(families_covered) >= STRUCTURAL_THRESHOLDS["min_source_families"]
    )
    checks["_passed"] = bool(passed)
    return checks


# ── semantic audit ───────────────────────────────────────────────────────────

def _rerank_relevance(query: str, claim_text: str, support_text: str) -> dict[str, Any]:
    from packages.rag.rerankers import rerank_with_llm

    rerank_query = f"{query} {claim_text}".strip()[:500]
    try:
        out = rerank_with_llm(
            rerank_query,
            [{"chunk_id": "ev", "chunk_text": support_text}],
            model_endpoint=RERANK_ENDPOINT, model_name=RERANK_MODEL, top_k=1, timeout=20,
        )
        if out:
            return {
                "rerank_bucket": out[0].get("rerank_bucket"),
                "rerank_score": out[0].get("rerank_score"),
            }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"rerank_failed:{type(exc).__name__}"}
    return {"error": "no_rerank_output"}


def _deepseek_judge(
    client, query: str, claim_text: str, support_text: str, url: str
) -> dict[str, Any]:
    system_prompt = (
        "你是产业研究证据质量审计员。判断给定证据对研究声明/查询的支撑质量。"
        "只输出 JSON，不要多余文字。"
    )
    user_prompt = (
        f"研究查询：{query}\n\n"
        f"研究声明：{claim_text}\n\n"
        f"证据来源URL：{url}\n\n"
        f"证据文本：{support_text}\n\n"
        '请输出JSON：{"support": "yes|partial|no", "relevance": 0-4, '
        '"authority": "A|B|C|D", "reason": "一句话理由"}。'
        "authority: A=官方/政府/权威统计, B=权威行业媒体/研究机构, "
        "C=一般商业/聚合, D=低质/不可靠。"
    )
    try:
        resp = client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        data = resp.json_data
        if not isinstance(data, dict):
            return {"error": "judge_non_dict"}
        return {
            "support": str(data.get("support", "unknown"))[:10],
            "relevance": int(data.get("relevance", -1)),
            "authority": str(data.get("authority", "?")).upper()[:1],
            "reason": str(data.get("reason", ""))[:200],
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"judge_failed:{type(exc).__name__}"}


def semantic_audit(query: str, evidence: dict[str, dict], claims: dict[str, dict],
                   *, max_evidence: int) -> dict[str, Any]:
    from packages.core.config import get_settings
    from packages.providers import DeepSeekProviderClient

    settings = get_settings()
    client = DeepSeekProviderClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_research_model,
        timeout_seconds=settings.deepseek_timeout_seconds,
        max_retries=settings.deepseek_max_retries,
        max_tokens=400,
        store_reasoning_content=False,
    )
    # 优先审计被 claim 引用且 score 高的 evidence
    ref_count: dict[str, int] = {}
    for claim in claims.values():
        for x in claim.get("evidence_ids", []):
            ref_count[str(x)] = ref_count.get(str(x), 0) + 1
    ranked = sorted(
        evidence.keys(),
        key=lambda eid: (ref_count.get(eid, 0), _evidence_score(evidence[eid])),
        reverse=True,
    )
    selected = ranked[:max_evidence]

    per_evidence = []
    relevance_buckets: list[int] = []
    support_counts = {"yes": 0, "partial": 0, "no": 0, "unknown": 0}
    authority_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "?": 0}
    judge_errors = 0

    for eid in selected:
        ev = evidence[eid]
        support_text = _evidence_text(ev)
        url = _evidence_url(ev)
        claim_text = _claim_text(next(
            (c for c in claims.values() if eid in [str(x) for x in c.get("evidence_ids", [])]),
            {},
        ))
        rr = _rerank_relevance(query, claim_text, support_text)
        judge = _deepseek_judge(client, query, claim_text, support_text, url)
        if "error" in judge:
            judge_errors += 1
        else:
            support_counts[judge.get("support", "unknown")] = (
                support_counts.get(judge.get("support", "unknown"), 0) + 1
            )
            auth = judge.get("authority", "?")
            authority_counts[auth] = authority_counts.get(auth, 0) + 1
            rel = judge.get("relevance", -1)
            if isinstance(rel, int) and 0 <= rel <= 4:
                relevance_buckets.append(rel)
        per_evidence.append({
            "evidence_id": eid,
            "source_url": url,
            "reranker": rr,
            "judge": judge,
            "evidence_text": support_text[:200],
        })

    audited = len(selected)
    support_rate = round(
        (support_counts["yes"] + support_counts["partial"]) / max(audited, 1), 3
    )
    mean_relevance = round(sum(relevance_buckets) / max(len(relevance_buckets), 1), 3)
    authority_ok = authority_counts["A"] + authority_counts["B"] + authority_counts["C"]
    authority_ok_rate = round(authority_ok / max(audited, 1), 3)
    return {
        "audited": audited,
        "judge_errors": judge_errors,
        "mean_relevance": mean_relevance,
        "support_rate": support_rate,
        "support_counts": support_counts,
        "authority_counts": authority_counts,
        "authority_ok_rate": authority_ok_rate,
        "per_evidence": per_evidence,
    }


def _semantic_passed(sem: dict[str, Any]) -> bool:
    if sem["audited"] == 0:
        return False
    return (
        sem["mean_relevance"] >= SEMANTIC_THRESHOLDS["mean_relevance"]
        and sem["support_rate"] >= SEMANTIC_THRESHOLDS["support_rate"]
        and sem["authority_ok_rate"] >= SEMANTIC_THRESHOLDS["authority_ok_rate"]
    )


# ── main ─────────────────────────────────────────────────────────────────────

def _bootstrap() -> None:
    """在目标 DB 上创建完整 schema（当前模型 + execution 表）。要求用独立审计库，
    dev 库 runs 表缺 G1.2 idempotency 列且 create_all 不会补列。"""
    from packages.db.base import Base
    from packages.db.session import get_engine
    from packages.execution.execution_lease import create_execution_tables

    engine = get_engine()
    Base.metadata.create_all(engine)
    create_execution_tables(engine)
    engine.dispose()


def _session() -> Session:
    from packages.db.session import SessionLocal

    return SessionLocal()


def _run_queries(queries: list[str], max_evidence: int) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for i, query in enumerate(queries):
        qkey = f"q{i}"
        print(f"[audit] running query {i}: {query[:40]}...", flush=True)
        t0 = time.perf_counter()
        with _session() as session:
            try:
                run = run_graph(session, query)
            except Exception as exc:  # noqa: BLE001
                print(f"  run FAILED: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
                results[qkey] = {"query": query, "error": str(exc), "PASS": False}
                continue
        run_seconds = round(time.perf_counter() - t0, 1)
        evidence, claims = run["evidence"], run["claims"]
        struct = structural_grade(evidence, claims, run.get("sources"))
        sem = semantic_audit(query, evidence, claims, max_evidence=max_evidence)
        sem_pass = _semantic_passed(sem)
        struct_pass = bool(struct.get("_passed"))
        overall_pass = bool(struct_pass and sem_pass) if evidence else False
        print(
            f"  run={run['run_id']} status={run['status']} decision={run['decision']} "
            f"evidence={len(evidence)} claims={len(claims)} ev_source={run.get('evidence_source')} "
            f"run_s={run_seconds} PASS={overall_pass}",
            flush=True,
        )
        results[qkey] = {
            "query": query,
            "run_id": run["run_id"],
            "status": run["status"],
            "decision": run["decision"],
            "quality_scores": run["quality_scores"],
            "evidence_source": run.get("evidence_source"),
            "run_seconds": run_seconds,
            "structural": struct,
            "semantic": sem,
            "PASS": overall_pass,
        }
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence quality audit")
    parser.add_argument("--queries", type=int, default=3, help="how many audit queries")
    parser.add_argument(
        "--max-evidence", type=int, default=10, help="max evidence audited per query"
    )
    parser.add_argument(
        "--offset", type=int, default=0, help="skip first N audit queries"
    )
    parser.add_argument(
        "--from-checkpoint", type=str, default=None,
        help="audit an existing run checkpoint state (skip running the pipeline)",
    )
    args = parser.parse_args()

    if args.from_checkpoint:
        _bootstrap()
        state = load_checkpoint_state(args.from_checkpoint)
        query = str(state.get("query") or "?")[:500]
        evidence, claims, sources = _extract_from_state(state)
        print(
            f"[audit] checkpoint: query={query[:40]}... "
            f"evidence={len(evidence)} claims={len(claims)}"
        )
        struct = structural_grade(evidence, claims, sources)
        sem = semantic_audit(query, evidence, claims, max_evidence=args.max_evidence)
        sem_pass = _semantic_passed(sem)
        overall = bool(struct.get("_passed") and sem_pass) if evidence else False
        results = {"q0": {
            "query": query, "run_id": state.get("run_id"), "status": "checkpoint",
            "decision": state.get("decision"), "quality_scores": state.get("quality_scores"),
            "structural": struct, "semantic": sem, "PASS": overall,
        }}
    else:
        _bootstrap()
        queries = AUDIT_QUERIES[args.offset : args.offset + args.queries]
        results = _run_queries(queries, args.max_evidence)

    all_pass = all(v.get("PASS", False) for v in results.values())
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "thresholds": {"structural": STRUCTURAL_THRESHOLDS, "semantic": SEMANTIC_THRESHOLDS},
        "queries": results,
        "status": "PASS" if all_pass else "FAIL",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "evidence_quality_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: v for k, v in report.items() if k != "queries"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nEvidence Quality Audit {'PASS' if all_pass else 'FAIL'} -> {OUT_DIR}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
