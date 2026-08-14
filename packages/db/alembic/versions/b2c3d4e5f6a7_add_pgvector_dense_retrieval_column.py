"""add pgvector dense retrieval column

Revision ID: b2c3d4e5f6a7
Revises: a7b8c9d0e1f2
Create Date: 2026-06-15 22:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("ALTER TABLE document_chunks ADD COLUMN embedding_vector vector(16)")
        op.execute(
            "UPDATE document_chunks "
            "SET embedding_vector = embedding_json::text::vector "
            "WHERE embedding_json IS NOT NULL AND embedding_dimension = 16"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_vector_hnsw "
            "ON document_chunks USING hnsw (embedding_vector vector_cosine_ops)"
        )
        return

    with op.batch_alter_table("document_chunks") as batch_op:
        batch_op.add_column(sa.Column("embedding_vector", sa.JSON(), nullable=True))
    op.execute(
        "UPDATE document_chunks SET embedding_vector = embedding_json "
        "WHERE embedding_json IS NOT NULL"
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_vector_hnsw")
        op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding_vector")
        return

    with op.batch_alter_table("document_chunks") as batch_op:
        batch_op.drop_column("embedding_vector")
