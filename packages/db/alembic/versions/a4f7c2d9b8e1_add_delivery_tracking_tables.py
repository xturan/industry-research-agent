"""add delivery tracking tables

Revision ID: a4f7c2d9b8e1
Revises: 8d3f2f77f3b1
Create Date: 2026-03-17 10:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4f7c2d9b8e1"
down_revision: Union[str, None] = "8d3f2f77f3b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    old_run_type = sa.Enum(
        "research",
        "thesis_build",
        "content_generate",
        "memory_refresh",
        name="run_type",
        native_enum=False,
    )
    new_run_type = sa.Enum(
        "research",
        "thesis_build",
        "content_generate",
        "memory_refresh",
        "delivery_dispatch",
        name="run_type",
        native_enum=False,
    )
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.alter_column(
            "run_type",
            existing_type=old_run_type,
            type_=new_run_type,
            existing_nullable=False,
        )

    op.create_table(
        "delivery_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_run_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "pending_review",
                "ready",
                "dispatching",
                "dispatched",
                "partial_failed",
                "failed",
                "cancelled",
                name="delivery_job_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "delivery_target",
            sa.Enum(
                "export_bundle",
                "webhook",
                "manual_review",
                "mock_social_connector",
                name="delivery_target",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "review_status",
            sa.Enum(
                "not_required",
                "pending",
                "approved",
                "rejected",
                name="delivery_review_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.Enum(
                "mock",
                "dry_run",
                name="delivery_mode",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("requested_by", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
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
            ["source_run_id"],
            ["runs.id"],
            name=op.f("fk_delivery_jobs_source_run_id_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_jobs")),
    )
    op.create_index(
        "ix_delivery_jobs_status_created_at",
        "delivery_jobs",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_delivery_jobs_review_status",
        "delivery_jobs",
        ["review_status"],
        unique=False,
    )
    op.create_index(op.f("ix_delivery_jobs_source_run_id"), "delivery_jobs", ["source_run_id"], unique=False)

    op.create_table(
        "delivery_job_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("delivery_job_id", sa.Integer(), nullable=False),
        sa.Column("content_asset_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "exported",
                "dispatched",
                "failed",
                "skipped",
                name="delivery_item_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("exported_path", sa.String(length=1024), nullable=True),
        sa.Column("dispatched_ref", sa.String(length=1024), nullable=True),
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
            ["content_asset_id"],
            ["content_assets.id"],
            name=op.f("fk_delivery_job_items_content_asset_id_content_assets"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["delivery_job_id"],
            ["delivery_jobs.id"],
            name=op.f("fk_delivery_job_items_delivery_job_id_delivery_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_job_items")),
    )
    op.create_index(
        "ix_delivery_job_items_delivery_job_id_status",
        "delivery_job_items",
        ["delivery_job_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_delivery_job_items_content_asset_id",
        "delivery_job_items",
        ["content_asset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_delivery_job_items_delivery_job_id"),
        "delivery_job_items",
        ["delivery_job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_delivery_job_items_delivery_job_id"), table_name="delivery_job_items")
    op.drop_index("ix_delivery_job_items_content_asset_id", table_name="delivery_job_items")
    op.drop_index(
        "ix_delivery_job_items_delivery_job_id_status",
        table_name="delivery_job_items",
    )
    op.drop_table("delivery_job_items")

    op.drop_index(op.f("ix_delivery_jobs_source_run_id"), table_name="delivery_jobs")
    op.drop_index("ix_delivery_jobs_review_status", table_name="delivery_jobs")
    op.drop_index("ix_delivery_jobs_status_created_at", table_name="delivery_jobs")
    op.drop_table("delivery_jobs")

    old_run_type = sa.Enum(
        "research",
        "thesis_build",
        "content_generate",
        "memory_refresh",
        name="run_type",
        native_enum=False,
    )
    new_run_type = sa.Enum(
        "research",
        "thesis_build",
        "content_generate",
        "memory_refresh",
        "delivery_dispatch",
        name="run_type",
        native_enum=False,
    )
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.alter_column(
            "run_type",
            existing_type=new_run_type,
            type_=old_run_type,
            existing_nullable=False,
        )
