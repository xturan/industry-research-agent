from __future__ import annotations

import argparse
import json

from packages.db.session import SessionLocal
from packages.evals.schemas import SmokeEvalRequest
from packages.evals.service import EvalService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic smoke eval.")
    parser.add_argument("--query", type=str, default="lithium pricing outlook")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--no-bootstrap", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal() as session:
        response = EvalService(session).run_smoke(
            SmokeEvalRequest(
                query=args.query,
                top_k=args.top_k,
                bootstrap_sample=not args.no_bootstrap,
            )
        )
        run_view = EvalService(session).get_eval_run(response.eval_run_id)
        print(
            json.dumps(
                {
                    "response": response.model_dump(mode="json"),
                    "run": run_view.model_dump(mode="json") if run_view else None,
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
