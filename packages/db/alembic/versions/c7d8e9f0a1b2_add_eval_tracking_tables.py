"""add eval tracking tables

Revision ID: c7d8e9f0a1b2
Revises: b1c2d3e4f5a6
Create Date: 2026-03-18 21:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "eval_type",
            sa.Enum(
                "rag_chunks",
                "evidence_bundle",
                "research_analyze",
                "content_generate",
                "task_delivery_flow",
                "smoke",
                name="eval_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_ref", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "succeeded",
                "failed",
                name="eval_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eval_runs")),
    )
    op.create_index(
        "ix_eval_runs_eval_type_status_created_at",
        "eval_runs",
        ["eval_type", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_eval_runs_target_type_target_ref",
        "eval_runs",
        ["target_type", "target_ref"],
        unique=False,
    )

    op.create_table(
        "eval_run_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("eval_run_id", sa.Integer(), nullable=False),
        sa.Column("case_name", sa.String(length=128), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=True),
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
            ["eval_run_id"],
            ["eval_runs.id"],
            name=op.f("fk_eval_run_items_eval_run_id_eval_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eval_run_items")),
    )
    op.create_index(
        "ix_eval_run_items_eval_run_id_passed",
        "eval_run_items",
        ["eval_run_id", "passed"],
        unique=False,
    )
    op.create_index(op.f("ix_eval_run_items_eval_run_id"), "eval_run_items", ["eval_run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_eval_run_items_eval_run_id"), table_name="eval_run_items")
    op.drop_index("ix_eval_run_items_eval_run_id_passed", table_name="eval_run_items")
    op.drop_table("eval_run_items")

    op.drop_index("ix_eval_runs_target_type_target_ref", table_name="eval_runs")
    op.drop_index("ix_eval_runs_eval_type_status_created_at", table_name="eval_runs")
    op.drop_table("eval_runs")
