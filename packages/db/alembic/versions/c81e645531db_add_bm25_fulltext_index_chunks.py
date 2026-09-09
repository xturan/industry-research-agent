"""Add BM25/full-text search index on document_chunks

Uses PostgreSQL built-in tsvector/tsquery as primary path.
If paradedb or pg_bm25 extension is available, creates bm25 index instead.

Revision ID: c81e645531db
Revises: f6a7b8c9d0e1
Create Date: 2026-06-18
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c81e645531db"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE
            ext_exists boolean;
        BEGIN
            -- Check for paradedb first (upstream of pg_bm25)
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'paradedb'
            ) INTO ext_exists;

            IF ext_exists THEN
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_chunks_bm25 '
                    'ON document_chunks USING bm25 (id, text, section_name) '
                    'WITH (key_field=''id'', text_fields=''{"text": {}, "section_name": {}}'')';
                RETURN;
            END IF;

            -- Check for pg_bm25
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'pg_bm25'
            ) INTO ext_exists;

            IF ext_exists THEN
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_chunks_bm25 '
                    'ON document_chunks USING bm25 (id, text, section_name)';
                RETURN;
            END IF;

            -- Fallback: PostgreSQL built-in full-text search with GIN index
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_chunks_fts '
                'ON document_chunks '
                'USING gin (to_tsvector(''simple'', '
                'coalesce(text, '''') || '' '' || coalesce(section_name, '''')))';
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_bm25")
    op.execute("DROP INDEX IF EXISTS idx_chunks_fts")
