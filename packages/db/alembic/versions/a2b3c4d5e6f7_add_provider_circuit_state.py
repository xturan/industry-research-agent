"""add provider circuit state table (G2.4)

Revision ID: a2b3c4d5e6f7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-08 00:00:00.000000

Provider 熔断运行时状态（与 CapabilityRegistry 分离）：
- provider_circuit_state：per-provider CLOSED/OPEN/HALF_OPEN + 连续失败计数 +
  opened_at / next_probe_at（cooldown 探测）。

只有 NETWORK/TIMEOUT/RATE_LIMIT/PROVIDER_5XX 计入 circuit；
CAPACITY_EXHAUSTED / OUTPUT_INVALID / BUSINESS_VALIDATION / CANCELLED 不污染。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_circuit_state",
        sa.Column("provider_instance_id", sa.String(), primary_key=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_probe_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("provider_circuit_state")
