"""G3 Execution Plane — 增强现有 Persistent Task + Worker。

- Global Active Run Capacity（max_active_runs，跨进程 PG）
- TaskExecutionLease（Lease + Heartbeat + TTL + Generation/Fencing）
- Claim = 短原子事务；Agent 长任务期间不持 DB transaction/connection
- Crash recovery（cancel-aware / requeue / retry exhaustion）
"""

from packages.execution.coordinator import (
    ClaimedExecution,
    ExecutionCoordinator,
    InMemoryExecutionCoordinator,
    PostgresExecutionCoordinator,
    RecoveryResult,
)
from packages.execution.execution_lease import (
    DDL_EXECUTION_LEASES,
    ExecutionLeaseStore,
    InMemoryExecutionLeaseStore,
    PostgresExecutionLeaseStore,
    TaskExecutionLease,
    create_execution_tables,
)
from packages.execution.worker import execute_claimed, process_next

__all__ = [
    "ClaimedExecution",
    "ExecutionCoordinator",
    "InMemoryExecutionCoordinator",
    "PostgresExecutionCoordinator",
    "RecoveryResult",
    "DDL_EXECUTION_LEASES",
    "ExecutionLeaseStore",
    "InMemoryExecutionLeaseStore",
    "PostgresExecutionLeaseStore",
    "TaskExecutionLease",
    "create_execution_tables",
    "process_next",
    "execute_claimed",
]
