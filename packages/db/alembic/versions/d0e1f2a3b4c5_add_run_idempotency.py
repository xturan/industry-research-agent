"""add run idempotency columns (G1.2)

Revision ID: d0e1f2a3b4c5
Revises: b2c3d4e5f6a7, c81e645531db
Create Date: 2026-08-07 00:00:00.000000

Adds idempotency_scope / idempotency_key / idempotency_request_hash to runs with
a UNIQUE(scope, key) constraint — the DB-level guarantee for exactly-once Run
creation under concurrent retries.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = ("b2c3d4e5f6a7", "c81e645531db")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.add_column(sa.Column("idempotency_scope", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("idempotency_request_hash", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint(
            "uq_runs_idempotency", ["idempotency_scope", "idempotency_key"]
        )


def downgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_constraint("uq_runs_idempotency", type_="unique")
        batch_op.drop_column("idempotency_request_hash")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("idempotency_scope")
