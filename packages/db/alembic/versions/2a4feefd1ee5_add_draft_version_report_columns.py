"""add draft version report columns + gate/review schema drift sync

Revision ID: 2a4feefd1ee5
Revises: a4b5c6d7e8f9
Create Date: 2026-08-12 21:31:54.478535

修复 ORM 模型与迁移的 schema 漂移（2026-08-12 发现）：
- research_graph_draft_versions 缺 report_markdown / sections_json（ORM SELECT * 崩溃）
- research_graph_quality_gate_results 缺 gate_reason / gate_route_to
- research_graph_review_issues 缺 description / required_fix / suggested_search_queries_json
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a4feefd1ee5'
down_revision: Union[str, None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # draft_versions：分章节报告持久化列
    op.add_column(
        "research_graph_draft_versions",
        sa.Column("report_markdown", sa.Text(), nullable=True),
    )
    op.add_column(
        "research_graph_draft_versions",
        sa.Column("sections_json", sa.JSON(), nullable=True),
    )
    # quality gate：gate 判定详情
    op.add_column(
        "research_graph_quality_gate_results",
        sa.Column("gate_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "research_graph_quality_gate_results",
        sa.Column("gate_route_to", sa.String(length=64), nullable=True),
    )
    # review issues：审稿问题详情
    op.add_column(
        "research_graph_review_issues",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "research_graph_review_issues",
        sa.Column("required_fix", sa.Text(), nullable=True),
    )
    op.add_column(
        "research_graph_review_issues",
        sa.Column("suggested_search_queries_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_graph_review_issues", "suggested_search_queries_json")
    op.drop_column("research_graph_review_issues", "required_fix")
    op.drop_column("research_graph_review_issues", "description")
    op.drop_column("research_graph_quality_gate_results", "gate_route_to")
    op.drop_column("research_graph_quality_gate_results", "gate_reason")
    op.drop_column("research_graph_draft_versions", "sections_json")
    op.drop_column("research_graph_draft_versions", "report_markdown")
