"""add provider concurrency budget tables (G2.3)

Revision ID: a1b2c3d4e5f6
Revises: f2a3b4c5d6e7
Create Date: 2026-08-08 00:00:00.000000

Provider 并发预算：
- provider_concurrency_state  -> per-provider transaction lock anchor
- provider_concurrency_leases -> active lease（acquire/release、TTL 过期恢复）

acquire 是短事务：FOR UPDATE state 行 → 清理过期/已释放 lease → count active →
insert lease → commit。**Provider 网络调用期间不持有 DB transaction/connection。**
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_concurrency_leases",
        sa.Column("lease_id", sa.String(), primary_key=True),
        sa.Column("provider_instance_id", sa.String(), nullable=False),
        sa.Column("route_execution_id", sa.String(), nullable=False),
        sa.Column("provider_call_id", sa.String(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_pcl_provider", "provider_concurrency_leases", ["provider_instance_id"]
    )

    op.create_table(
        "provider_concurrency_state",
        sa.Column("provider_instance_id", sa.String(), primary_key=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("provider_concurrency_state")
    op.drop_table("provider_concurrency_leases")
