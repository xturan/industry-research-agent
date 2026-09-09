"""add provider attempt records table (G2.5)

Revision ID: a3b4c5d6e7f8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-08 00:00:00.000000

Provider Attempt Telemetry（append-only）：
每次真实 Provider attempt 一条记录；一次 route_execution_id 可对应多个
provider_call_id（fallback chain）。circuit/capacity 也记 attempt 但
transport_invoked=false。禁止记录 raw prompt / API key / full source。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_attempt_records",
        sa.Column("provider_call_id", sa.String(), primary_key=True),
        sa.Column("route_execution_id", sa.String(), nullable=False),
        sa.Column("request_fingerprint", sa.String(), nullable=True),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("provider_instance_id", sa.String(), nullable=False),
        sa.Column("capability", sa.String(), nullable=True),
        sa.Column("task_type", sa.String(), nullable=True),
        sa.Column("attempt_index", sa.Integer(), nullable=False),
        sa.Column("transport_invoked", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("failure_class", sa.String(), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("fallback_index", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("request_count", sa.Integer(), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=True),
        sa.Column("cost_estimate", sa.Float(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_par_route", "provider_attempt_records", ["route_execution_id"])
    op.create_index(
        "ix_par_provider_created",
        "provider_attempt_records", ["provider_instance_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("provider_attempt_records")
