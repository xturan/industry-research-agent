"""add task queue tables

Revision ID: b1c2d3e4f5a6
Revises: a4f7c2d9b8e1
Create Date: 2026-03-18 20:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a4f7c2d9b8e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "task_type",
            sa.Enum(
                "research_analyze",
                "content_generate",
                "delivery_dispatch",
                name="task_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "succeeded",
                "failed",
                "dead_letter",
                "cancelled",
                name="task_job_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("source_run_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_task_jobs_task_jobs_attempt_count_non_negative"),
        ),
        sa.CheckConstraint(
            "max_attempts >= 1",
            name=op.f("ck_task_jobs_task_jobs_max_attempts_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["runs.id"],
            name=op.f("fk_task_jobs_source_run_id_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_jobs")),
        sa.UniqueConstraint(
            "task_type",
            "idempotency_key",
            name="uq_task_jobs_task_type_idempotency_key",
        ),
    )
    op.create_index("ix_task_jobs_idempotency_key", "task_jobs", ["idempotency_key"], unique=False)
    op.create_index(op.f("ix_task_jobs_source_run_id"), "task_jobs", ["source_run_id"], unique=False)
    op.create_index(
        "ix_task_jobs_status_available_at_priority",
        "task_jobs",
        ["status", "available_at", "priority"],
        unique=False,
    )
    op.create_index(
        "ix_task_jobs_task_type_status",
        "task_jobs",
        ["task_type", "status"],
        unique=False,
    )

    op.create_table(
        "task_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_job_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "succeeded",
                "failed",
                "retry_scheduled",
                "cancelled",
                name="task_attempt_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_job_id"],
            ["task_jobs.id"],
            name=op.f("fk_task_attempts_task_job_id_task_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_attempts")),
        sa.UniqueConstraint(
            "task_job_id",
            "attempt_number",
            name="uq_task_attempts_task_job_id_attempt_number",
        ),
    )
    op.create_index(
        op.f("ix_task_attempts_task_job_id"),
        "task_attempts",
        ["task_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_attempts_task_job_id_started_at",
        "task_attempts",
        ["task_job_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_task_attempts_worker_id_started_at",
        "task_attempts",
        ["worker_id", "started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_task_attempts_worker_id_started_at", table_name="task_attempts")
    op.drop_index("ix_task_attempts_task_job_id_started_at", table_name="task_attempts")
    op.drop_index(op.f("ix_task_attempts_task_job_id"), table_name="task_attempts")
    op.drop_table("task_attempts")

    op.drop_index("ix_task_jobs_task_type_status", table_name="task_jobs")
    op.drop_index("ix_task_jobs_status_available_at_priority", table_name="task_jobs")
    op.drop_index(op.f("ix_task_jobs_source_run_id"), table_name="task_jobs")
    op.drop_index("ix_task_jobs_idempotency_key", table_name="task_jobs")
    op.drop_table("task_jobs")
