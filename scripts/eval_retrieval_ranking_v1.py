"""Evaluate real retrieval ranking quality: bge-m3 embedding + LLM-reranker rerank.

Pipeline (mirrors graph-runtime path of retrieval_bridge):
  multi-phrase AnySearch collect -> dedup -> coarse rank (BM25 + real bge-m3 ∥ RRF)
  -> chunk -> LLM reranker rerank (real vLLM) vs deterministic fallback.

Usage:
  python scripts/eval_retrieval_ranking_v1.py \
      --query "湖南浏阳烟花产业发展" \
      --phrases "浏阳 烟花 产业链" "浏阳 烟花 产值" "浏阳 烟花爆竹 政策"

  # deterministic-comparison run (forces fallback even if services are up):
  python scripts/eval_retrieval_ranking_v1.py --force-fallback
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from packages.research_harness import retrieval_rank as rr  # noqa: E402
from scripts.compare_search_providers import anysearch_search  # noqa: E402

DEFAULT_PHRASES = [
    "浏阳 烟花 产业链",
    "浏阳 烟花 产值 出口",
    "浏阳 烟花爆竹 企业 名单",
    "浏阳 烟花爆竹 政策 监管",
    "浏阳 烟花 产业集群 园区",
    "浏阳 花炮 产业 发展规划",
]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and value:
            os.environ.setdefault(name, value)


def _family(url: str, title: str) -> str:
    host = (url.split("/")[2].lower() if "://" in url else "").removeprefix("www.")
    text = f"{title} {url}".lower()
    if host.endswith("gov.cn") or host.endswith("ndrc.gov.cn"):
        if any(t in text for t in ("统计", "tjj", "公报")):
            return "official_statistics"
        if any(t in text for t in ("采购", "招标", "ggzy", "ccgp")):
            return "tender_procurement"
        return "policy_document"
    if any(host.endswith(s) for s in ("cninfo.com.cn", "sse.com.cn", "szse.cn", "bse.cn")):
        return "company_disclosure"
    if any(t in text for t in ("采购", "招标", "ggzy", "ccgp")):
        return "tender_procurement"
    if any(t in text for t in ("日报", "新闻", "news")):
        return "local_official"
    return "industry_research"


def collect_sources(
    phrases: list[str], api_key: str, max_results: int, timeout: int
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, phrase in enumerate(phrases):
        started = perf_counter()
        try:
            results, meta = anysearch_search(
                phrase, max_results=max_results, api_key=api_key, timeout_seconds=timeout
            )
        except Exception as exc:  # noqa: BLE001 - keep collecting across phrase failures
            print(f"  [phrase {i}] search failed: {type(exc).__name__}: {str(exc)[:200]}")
            continue
        for result in results:
            if not result.url or result.url in seen:
                continue
            seen.add(result.url)
            sources.append(
                {
                    "source_id": f"src_{len(sources)}",
                    "url": result.url,
                    "title": result.title,
                    "source_family": _family(result.url, result.title),
                    "snippet": result.snippet,
                    "raw_text": result.content or result.snippet,
                    "full_text": result.content or result.snippet,
                }
            )
        print(
            f"  [phrase {i}] '{phrase}' -> {len(results)} results "
            f"({(perf_counter() - started):.1f}s)"
        )
    return sources


def keyword_hits(texts: list[str], keywords: list[str]) -> dict[str, bool]:
    joined = "\n".join(texts).lower()
    return {kw: kw in joined for kw in keywords}


def summarize_rank(name: str, out: dict[str, Any]) -> dict[str, Any]:
    chunks = out.get("source_chunks", [])
    chunk_texts = [str(c.get("chunk_text") or "") for c in chunks]
    keywords = [
        "浏阳", "烟花", "产业链", "产值", "出口",
        "企业", "政策", "安全", "产业集群", "花炮",
    ]
    hits = keyword_hits(chunk_texts, keywords)
    return {
        "name": name,
        "rerank_mode": out.get("rerank_mode"),
        "coarse_meta": out.get("coarse_meta"),
        "n_chunks": len(chunks),
        "keyword_hits": {k: v for k, v in hits.items()},
        "hit_coverage": round(sum(hits.values()) / len(hits), 3),
        "top_chunks": [
            {
                "rank": i,
                "source_id": c.get("source_id"),
                "family": c.get("source_family"),
                "rerank_score": c.get("rerank_score"),
                "text": str(c.get("chunk_text") or "")[:90],
            }
            for i, c in enumerate(chunks[:10])
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate real retrieval ranking quality")
    parser.add_argument("--query", default="湖南浏阳烟花产业发展")
    parser.add_argument("--phrases", nargs="*", default=None)
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--coarse-top-n", type=int, default=30)
    parser.add_argument("--rerank-top-k", type=int, default=24)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--force-fallback", action="store_true",
                        help="point endpoints at unreachable ports to force fallback")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--phase", choices=["full", "coarse", "rerank"], default="full",
                        help="two-phase: coarse (embed+chunk) / rerank (load, LLM reranker)")
    parser.add_argument("--chunks-io", type=Path,
                        default=Path("data/tmp/retrieval_ranking_eval_v1/chunks_phase1.json"))
    args = parser.parse_args()

    load_env_file(args.env_file)
    api_key = os.getenv("ANYSEARCH_API_KEY")
    phrases = args.phrases or DEFAULT_PHRASES
    print(f"== query: {args.query}")
    print(f"== phrases ({len(phrases)}): {phrases}")

    if args.force_fallback:
        # Force both lanes to fail so the pipeline falls back to deterministic.
        os.environ["RERANK_ENDPOINT"] = "http://localhost:59998/v1/chat/completions"
        os.environ["EMBEDDING_ENDPOINT"] = "http://localhost:59999/v1/embeddings"

    if args.phase == "coarse":
        print("\n== [coarse] collecting sources (AnySearch multi-phrase)")
        sources = collect_sources(phrases, api_key, args.max_results, args.timeout)
        print(f"== [coarse] collected {len(sources)} raw sources")
        deduped = rr.dedup_sources(sources)
        coarse = rr.coarse_rank_bm25_vector_rrf(
            deduped, args.query, phrases, top_n=args.coarse_top_n
        )
        chunks = rr.chunk_documents(coarse, max_chars=700)
        payload = {
            "query": args.query,
            "phrases": phrases,
            "coarse_meta": {
                "dedup_count": len(deduped),
                "coarse_count": len(coarse),
                "chunk_count": len(chunks),
            },
            "sources": sources,
            "ranked_sources": coarse,
            "chunks": chunks,
        }
        args.chunks_io.parent.mkdir(parents=True, exist_ok=True)
        args.chunks_io.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"== [coarse] saved {len(chunks)} chunks "
            f"+ {len(coarse)} ranked sources -> {args.chunks_io}"
        )
        print("\n== coarse top-5 documents (RRF score, real bge-m3)")
        for i, s in enumerate(coarse[:5]):
            print(f"  {i + 1}. [{s.get('_coarse_rrf_score')}] {s.get('source_family')} :: "
                  f"{str(s.get('title') or '')[:60]}")
        return 0

    if args.phase == "rerank":
        if not args.chunks_io.exists():
            print(f"[error] chunks file not found: {args.chunks_io}", file=sys.stderr)
            return 1
        payload = json.loads(args.chunks_io.read_text(encoding="utf-8"))
        chunks = payload["chunks"]
        q = payload["query"]
        ph = payload["phrases"]
        print(f"== [rerank] loaded {len(chunks)} chunks from {args.chunks_io}")
        print("== [rerank] running REAL LLM-reranker rerank...")
        ranked_real, mode_real = rr.rerank_chunks_llm(
            q, ph, chunks, top_k=args.rerank_top_k
        )
        # Force the deterministic fallback path on the SAME chunks by simulating
        # a down LLM reranker (settings are cached, so env-var override won't work).
        _orig = rr.rerank_with_llm

        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise ConnectionError("forced model down for comparison")

        rr.rerank_with_llm = _boom
        try:
            ranked_det, mode_det = rr.rerank_chunks_llm(
                q, ph, chunks, top_k=args.rerank_top_k
            )
        finally:
            rr.rerank_with_llm = _orig
        real_sum = summarize_rank(
            "llm_reranker",
            {"source_chunks": ranked_real, "rerank_mode": mode_real,
             "coarse_meta": payload.get("coarse_meta")},
        )
        det_sum = summarize_rank(
            "deterministic",
            {"source_chunks": ranked_det, "rerank_mode": mode_det,
             "coarse_meta": payload.get("coarse_meta")},
        )
        print(json.dumps({"real_llm_reranker": real_sum,
                          "deterministic_on_same_chunks": det_sum},
                         ensure_ascii=False, indent=2))
        out_dir = Path("data/tmp/retrieval_ranking_eval_v1")
        out_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "query": q, "phrases": ph, "coarse_meta": payload.get("coarse_meta"),
            "real": {"mode": mode_real, "chunks": ranked_real, "summary": real_sum},
            "deterministic": {"mode": mode_det, "chunks": ranked_det, "summary": det_sum},
        }
        path = out_dir / "rerank_phase2.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n== saved to {path}")
        return 0

    print("\n== collecting sources (AnySearch multi-phrase)")
    sources = collect_sources(phrases, api_key, args.max_results, args.timeout)
    print(f"== collected {len(sources)} raw sources")

    print(
        "\n== running rank_retrieved_sources (real bge-m3 + LLM reranker)"
        if not args.force_fallback
        else "\n== running rank_retrieved_sources (FORCED deterministic fallback)"
    )
    started = perf_counter()
    out = rr.rank_retrieved_sources(
        sources,
        args.query,
        phrases,
        coarse_top_n=args.coarse_top_n,
        rerank_top_k=args.rerank_top_k,
    )
    elapsed = perf_counter() - started

    summary = summarize_rank("real" if not args.force_fallback else "fallback", out)
    summary["elapsed_s"] = round(elapsed, 2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n== coarse top-5 documents (RRF score)")
    for i, s in enumerate(out.get("ranked_sources", [])[:5]):
        print(f"  {i + 1}. [{s.get('_coarse_rrf_score')}] {s.get('source_family')} :: "
              f"{str(s.get('title') or '')[:60]}")

    if args.save:
        out_dir = Path("data/tmp/retrieval_ranking_eval_v1")
        out_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
            "query": args.query,
            "phrases": phrases,
            "forced_fallback": args.force_fallback,
            "elapsed_s": elapsed,
            "summary": summary,
            "sources": sources,
            "result": out,
        }
        path = out_dir / ("fallback.json" if args.force_fallback else "real.json")
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n== saved to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
