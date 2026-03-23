import argparse
import logging

from packages.core.config import get_settings
from packages.core.logging import bind_log_context, configure_logging
from packages.tasks.worker import TaskWorker

LOGGER = logging.getLogger(__name__)


def run_once(*, worker_id: str, poll_interval_seconds: int) -> None:
    worker = TaskWorker(worker_id=worker_id, poll_interval_seconds=poll_interval_seconds)
    did_work = worker.run_once()
    LOGGER.info("worker tick completed worker_id=%s did_work=%s", worker_id, did_work)


def run_forever(*, worker_id: str, poll_interval_seconds: int) -> None:
    worker = TaskWorker(worker_id=worker_id, poll_interval_seconds=poll_interval_seconds)
    worker.run_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Invest Agent task worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single worker claim/execute tick",
    )
    parser.add_argument("--worker-id", type=str, default=None)
    parser.add_argument("--poll-interval-seconds", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    settings = get_settings()
    args = parse_args()
    configure_logging(settings.log_level)
    worker_id = args.worker_id or settings.task_worker_id
    poll_interval_seconds = args.poll_interval_seconds or settings.worker_poll_interval_seconds

    with bind_log_context(worker_id=worker_id):
        LOGGER.info(
            "starting worker service worker_id=%s poll_interval_seconds=%s",
            worker_id,
            poll_interval_seconds,
        )
        if args.once:
            run_once(worker_id=worker_id, poll_interval_seconds=poll_interval_seconds)
            return

        try:
            run_forever(worker_id=worker_id, poll_interval_seconds=poll_interval_seconds)
        except KeyboardInterrupt:
            LOGGER.info("worker shutdown requested")


if __name__ == "__main__":
    main()
