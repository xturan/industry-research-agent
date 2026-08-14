"""add research graph checkpoints

Revision ID: d4e5f6a7b8c9
Revises: c7d8e9f0a1b2
Create Date: 2026-06-11 18:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_graph_checkpoints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.String(length=255), nullable=False),
        sa.Column("current_node", sa.String(length=128), nullable=True),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column(
            "saved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
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
            ["run_id"],
            ["runs.id"],
            name=op.f("fk_research_graph_checkpoints_run_id_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_graph_checkpoints")),
        sa.UniqueConstraint("run_id", name="uq_research_graph_checkpoints_run_id"),
    )
    op.create_index(
        op.f("ix_research_graph_checkpoints_run_id"),
        "research_graph_checkpoints",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_research_graph_checkpoints_thread_id",
        "research_graph_checkpoints",
        ["thread_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_research_graph_checkpoints_thread_id", table_name="research_graph_checkpoints")
    op.drop_index(op.f("ix_research_graph_checkpoints_run_id"), table_name="research_graph_checkpoints")
    op.drop_table("research_graph_checkpoints")
