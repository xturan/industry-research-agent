from __future__ import annotations

import argparse
import json

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.content.schemas import ContentGenerateRequest
from packages.db.session import SessionLocal
from packages.tasks.schemas import (
    ContentGenerateTaskSubmitRequest,
    DeliveryDispatchTaskSubmitRequest,
    ResearchAnalyzeTaskSubmitRequest,
)
from packages.tasks.service import TaskService
from packages.tasks.worker import TaskWorker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Task queue demo utility.")
    parser.add_argument(
        "--task-type",
        choices=["research_analyze", "content_generate", "delivery_dispatch"],
        required=True,
    )
    parser.add_argument("--query", type=str, default="lithium pricing outlook")
    parser.add_argument("--delivery-job-id", type=int, default=None)
    parser.add_argument("--research-run-id", type=int, default=None)
    parser.add_argument("--idempotency-key", type=str, default=None)
    parser.add_argument("--process-once", action="store_true")
    parser.add_argument("--worker-id", type=str, default="dev-demo-worker")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal() as session:
        service = TaskService(session)
        if args.task_type == "research_analyze":
            accepted = service.enqueue_research(
                ResearchAnalyzeTaskSubmitRequest(
                    idempotency_key=args.idempotency_key,
                    request=ResearchAnalyzeRequest(query=args.query, mode="mock", top_k=6),
                )
            )
        elif args.task_type == "content_generate":
            if args.research_run_id is None:
                raise ValueError("--research-run-id is required for content_generate demo.")
            accepted = service.enqueue_content(
                ContentGenerateTaskSubmitRequest(
                    idempotency_key=args.idempotency_key,
                    request=ContentGenerateRequest(
                        research_run_id=args.research_run_id,
                        mode="mock",
                    ),
                )
            )
        else:
            if args.delivery_job_id is None:
                raise ValueError("--delivery-job-id is required for delivery_dispatch demo.")
            accepted = service.enqueue_delivery(
                DeliveryDispatchTaskSubmitRequest(
                    idempotency_key=args.idempotency_key,
                    delivery_job_id=args.delivery_job_id,
                )
            )
        print(
            json.dumps(
                {"accepted": accepted.model_dump(mode="json")},
                ensure_ascii=False,
                indent=2,
            )
        )

    if args.process_once:
        worker = TaskWorker(worker_id=args.worker_id, poll_interval_seconds=1)
        worker.run_once()
        with SessionLocal() as session:
            view = TaskService(session).get_task(accepted.task_id)
            print(json.dumps({"task": view.model_dump(mode="json")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
