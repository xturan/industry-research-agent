"""Validate the collection-layer fix end-to-end: run ONE real query through the
graph runner and inspect the executed searches + collected sources.

Goal: confirm the dimension-targeted search-round fix makes the executed searches
actually target evidence types (招投标/中标/订单/统计公报/收入…), and that the
collected sources now contain such evidence — instead of the old behavior where
all searches were query-variant duplicates.

The run will likely FAIL at verify_claims (known blocker); we read the checkpoint
state (search_events + sources) which is populated before that node.

Usage:
  DATABASE_URL=... python scripts/validate_collection_fix.py [--query-idx 0]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone.utc

QUERIES = [
    "半导体设备和材料国产替代是否已经从政策支持转化为订单和收入？"
    "请重点检查招投标、中标公告、客户验证、上市公司收入结构。",
    "低空经济在中央层面的政策支持是否已经进入规模化落地阶段？"
    "请分别验证空域改革、适航认证、基础设施建设、地方试点和企业订单。",
]

EVIDENCE_KEYWORDS = [
    "中标", "招投标", "招标", "订单", "合同", "客户验证", "收入", "营收", "年报",
    "公告", "采购", "项目", "统计公报", "产值", "产量", "试点", "批复", "验收",
]


def _bootstrap() -> None:
    from packages.db.base import Base
    from packages.db.session import get_engine
    from packages.execution.execution_lease import create_execution_tables

    engine = get_engine()
    Base.metadata.create_all(engine)
    create_execution_tables(engine)
    engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate collection fix")
    parser.add_argument("--query-idx", type=int, default=0)
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args()

    _bootstrap()
    query = QUERIES[args.query_idx]

    from packages.db.session import SessionLocal
    from packages.research_harness.runner import ResearchGraphRunner
    from packages.research_harness.schemas import GraphAnalyzeRequest

    with SessionLocal() as session:
        runner = ResearchGraphRunner(session)
        response = runner.run(GraphAnalyzeRequest(
            query=query,
            max_rounds=args.max_rounds,
            max_loop_count=1,
            execution_mode="provider_backed",
        ))
    run_id = response.run_id
    print(f"run_id={run_id} status={response.status} decision={response.decision}")

    cp = _REPO / "data" / "graph_checkpoints" / f"run_{run_id}" / "latest.json"
    if not cp.exists():
        print("no checkpoint; cannot inspect collection")
        return 1
    st = json.loads(cp.read_text(encoding="utf-8"))["state"]

    print("\n=== 实际执行的搜索（search_events）===")
    evs = st.get("search_events") or []
    for i, e in enumerate(evs):
        phrase = str(e.get("query") or e.get("search_phrase") or "")
        print(f"  [{i}] status={e.get('status')} results={e.get('result_count')} :: {phrase[:70]}")

    print("\n=== plan.search_rounds（前 6 轮各短语数）===")
    rounds = (st.get("plan") or {}).get("search_rounds") or []
    for i, r in enumerate(rounds[:6]):
        n_phr = len(r.get("search_phrases") or [])
        print(f"  round {i}: {n_phr} phrases | dims={r.get('target_dimensions')}")

    print("\n=== 收集到的 sources 证据类型覆盖 ===")
    sources = st.get("sources") or []
    corpus = " ".join(str(s.get("full_text") or s.get("raw_text") or "") for s in sources)
    print(f"  source_count={len(sources)}")
    for kw in EVIDENCE_KEYWORDS:
        print(f"  {kw:6s}: {'有' if kw in corpus else '无'}")

    # 每条 source 的标题 + family + 是否含订单/中标类证据词
    print("\n=== 具体 source 命中证据词 ===")
    for s in sources[:12]:
        text = str(s.get("full_text") or s.get("raw_text") or "")
        hit = [kw for kw in EVIDENCE_KEYWORDS if kw in text][:6]
        sid = s.get("source_id")
        fam = str(s.get("source_family") or "")[:16]
        title = str(s.get("title") or "")[:28]
        print(f"  {sid:12s} {fam:16s} title={title} hits={hit}")

    print(f"\ngenerated_at={datetime.now(UTC).isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
