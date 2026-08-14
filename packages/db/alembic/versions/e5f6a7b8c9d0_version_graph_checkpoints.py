"""version graph checkpoints

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-11 18:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_graph_checkpoints",
        sa.Column("checkpoint_version", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE research_graph_checkpoints SET checkpoint_version = 1")
    with op.batch_alter_table("research_graph_checkpoints") as batch_op:
        batch_op.alter_column("checkpoint_version", nullable=False)
        batch_op.drop_constraint("uq_research_graph_checkpoints_run_id", type_="unique")
        batch_op.create_unique_constraint(
            "uq_research_graph_checkpoints_run_id_checkpoint_version",
            ["run_id", "checkpoint_version"],
        )
    op.create_index(
        "ix_research_graph_checkpoints_run_id_saved_at",
        "research_graph_checkpoints",
        ["run_id", "saved_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_research_graph_checkpoints_run_id_saved_at", table_name="research_graph_checkpoints")
    with op.batch_alter_table("research_graph_checkpoints") as batch_op:
        batch_op.drop_constraint(
            "uq_research_graph_checkpoints_run_id_checkpoint_version",
            type_="unique",
        )
        batch_op.create_unique_constraint("uq_research_graph_checkpoints_run_id", ["run_id"])
    op.drop_column("research_graph_checkpoints", "checkpoint_version")
