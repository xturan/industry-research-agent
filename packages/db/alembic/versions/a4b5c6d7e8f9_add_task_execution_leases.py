"""add task execution leases + execution_generation (G3)

Revision ID: a4b5c6d7e8f9
Revises: a3b4c5d6e7f8
Create Date: 2026-08-08 00:00:00.000000

G3 Execution Plane：
- task_jobs.execution_generation：fencing token（每次 claim +1）
- task_execution_leases：Worker 执行所有权（Lease/Heartbeat/TTL/Generation）
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "task_jobs",
        sa.Column("execution_generation", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "task_execution_leases",
        sa.Column("lease_id", sa.String(), primary_key=True),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=True),
        sa.Column("worker_id", sa.String(), nullable=False),
        sa.Column("execution_generation", sa.Integer(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tel_active", "task_execution_leases", ["run_id", "released_at"])


def downgrade() -> None:
    op.drop_table("task_execution_leases")
    op.drop_column("task_jobs", "execution_generation")
