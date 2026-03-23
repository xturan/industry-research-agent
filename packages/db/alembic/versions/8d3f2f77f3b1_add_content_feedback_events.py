"""add content feedback events

Revision ID: 8d3f2f77f3b1
Revises: 5271bbb18a1e
Create Date: 2026-03-16 21:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d3f2f77f3b1"
down_revision: Union[str, None] = "5271bbb18a1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_feedback_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_asset_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.Column("likes", sa.Integer(), nullable=False),
        sa.Column("comments", sa.Integer(), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("saves", sa.Integer(), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("conversions", sa.Integer(), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
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
        sa.CheckConstraint("views >= 0", name=op.f("ck_content_feedback_events_content_feedback_views_non_negative")),
        sa.CheckConstraint("likes >= 0", name=op.f("ck_content_feedback_events_content_feedback_likes_non_negative")),
        sa.CheckConstraint("comments >= 0", name=op.f("ck_content_feedback_events_content_feedback_comments_non_negative")),
        sa.CheckConstraint("shares >= 0", name=op.f("ck_content_feedback_events_content_feedback_shares_non_negative")),
        sa.CheckConstraint("saves >= 0", name=op.f("ck_content_feedback_events_content_feedback_saves_non_negative")),
        sa.CheckConstraint("clicks >= 0", name=op.f("ck_content_feedback_events_content_feedback_clicks_non_negative")),
        sa.CheckConstraint(
            "conversions >= 0",
            name=op.f("ck_content_feedback_events_content_feedback_conversions_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["content_asset_id"],
            ["content_assets.id"],
            name=op.f("fk_content_feedback_events_content_asset_id_content_assets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_feedback_events")),
    )
    op.create_index(
        op.f("ix_content_feedback_events_content_asset_id"),
        "content_feedback_events",
        ["content_asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_content_feedback_events_channel_captured_at",
        "content_feedback_events",
        ["channel", "captured_at"],
        unique=False,
    )
    op.create_index(
        "ix_content_feedback_events_content_asset_id_captured_at",
        "content_feedback_events",
        ["content_asset_id", "captured_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_content_feedback_events_content_asset_id_captured_at",
        table_name="content_feedback_events",
    )
    op.drop_index(
        "ix_content_feedback_events_channel_captured_at",
        table_name="content_feedback_events",
    )
    op.drop_index(op.f("ix_content_feedback_events_content_asset_id"), table_name="content_feedback_events")
    op.drop_table("content_feedback_events")
