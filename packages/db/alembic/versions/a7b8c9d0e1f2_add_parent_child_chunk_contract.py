"""add parent child chunk contract

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-15 20:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("document_chunks") as batch_op:
        batch_op.add_column(
            sa.Column("chunk_level", sa.String(length=16), nullable=True)
        )
        batch_op.add_column(
            sa.Column("parent_chunk_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("section_path", sa.String(length=1024), nullable=True)
        )
        batch_op.add_column(
            sa.Column("index_text", sa.Text(), nullable=True)
        )
    op.execute("UPDATE document_chunks SET chunk_level = 'child' WHERE chunk_level IS NULL")
    op.execute("UPDATE document_chunks SET index_text = text WHERE index_text IS NULL")
    with op.batch_alter_table("document_chunks") as batch_op:
        batch_op.alter_column("chunk_level", nullable=False)
        batch_op.drop_constraint(
            "uq_document_chunks_document_id_chunk_index",
            type_="unique",
        )
        batch_op.create_unique_constraint(
            "uq_document_chunks_document_id_level_chunk_index",
            ["document_id", "chunk_level", "chunk_index"],
        )
        batch_op.create_foreign_key(
            "fk_document_chunks_parent_chunk_id",
            "document_chunks",
            ["parent_chunk_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index(
        "ix_document_chunks_parent_chunk_id",
        "document_chunks",
        ["parent_chunk_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_parent_chunk_id", table_name="document_chunks")
    with op.batch_alter_table("document_chunks") as batch_op:
        batch_op.drop_constraint("fk_document_chunks_parent_chunk_id", type_="foreignkey")
        batch_op.drop_constraint(
            "uq_document_chunks_document_id_level_chunk_index",
            type_="unique",
        )
        batch_op.create_unique_constraint(
            "uq_document_chunks_document_id_chunk_index",
            ["document_id", "chunk_index"],
        )
        batch_op.drop_column("index_text")
        batch_op.drop_column("section_path")
        batch_op.drop_column("parent_chunk_id")
        batch_op.drop_column("chunk_level")
