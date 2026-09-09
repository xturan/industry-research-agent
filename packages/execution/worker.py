"""G3 Worker loop integration — claim → execute → fenced finalize。

替换/补充现有 `TaskService.process_next` 的执行路径：
    ExecutionCoordinator.claim()
        ↓
    handlers.execute(DeepResearchAgent)
        ↓
    coordinator.finalize(fenced execution_generation)
"""

from __future__ import annotations

from typing import Any

from packages.execution.coordinator import ClaimedExecution, ExecutionCoordinator


def execute_claimed(
    coordinator: ExecutionCoordinator,
    claimed: ClaimedExecution,
    handlers: Any,
) -> bool:
    """执行一个已 claim 的 task，并用 fencing 写回结果。

    返回 True = 当前 Worker 成功 finalize；False = 已被 fence（stale worker）。
    """
    try:
        execution = handlers.execute(
            task_type=claimed.task_type,
            payload_json=claimed.payload_json,
            source_run_id=claimed.run_id,
        )
        return coordinator.finalize(
            claimed, success=True, result_json=execution.result_json
        )
    except Exception as exc:  # noqa: BLE001
        return coordinator.finalize(
            claimed, success=False, error=str(exc)[:2000]
        )


def process_next(
    coordinator: ExecutionCoordinator,
    worker_id: str,
    handlers: Any,
    *,
    max_active_runs: int,
) -> ClaimedExecution | None:
    """Worker 单步：recover → claim → 执行 → fenced finalize。返回 claim（None = 无任务/满）。"""
    coordinator.recover_expired()  # 先清理过期 lease（cancel/requeue/fail）
    claimed = coordinator.claim(worker_id, max_active_runs=max_active_runs)
    if claimed is None:
        return None
    execute_claimed(coordinator, claimed, handlers)
    return claimed


__all__ = ["execute_claimed", "process_next"]
