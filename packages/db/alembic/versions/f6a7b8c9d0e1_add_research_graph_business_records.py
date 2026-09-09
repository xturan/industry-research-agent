"""add research graph business records

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "research_graph_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("source_family", sa.String(length=128), nullable=True),
        sa.Column("source_tier", sa.String(length=32), nullable=True),
        sa.Column("source_role", sa.String(length=128), nullable=True),
        sa.Column("usage_role", sa.String(length=128), nullable=True),
        sa.Column("search_phrase", sa.Text(), nullable=True),
        sa.Column("discovered_by_phrase", sa.Text(), nullable=True),
        sa.Column("published_date", sa.String(length=64), nullable=True),
        sa.Column("search_score", sa.Float(), nullable=True),
        sa.Column("raw_text_meta_json", sa.JSON(), nullable=True),
        sa.Column("source_quality_json", sa.JSON(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "source_id", name="uq_research_graph_sources_run_source"),
    )
    op.create_index(op.f("ix_research_graph_sources_run_id"), "research_graph_sources", ["run_id"])
    op.create_index("ix_research_graph_sources_run_family", "research_graph_sources", ["run_id", "source_family"])
    op.create_index("ix_research_graph_sources_domain", "research_graph_sources", ["domain"])

    op.create_table(
        "research_graph_evidence_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("support_type", sa.String(length=128), nullable=True),
        sa.Column("support_strength", sa.Float(), nullable=True),
        sa.Column("specificity", sa.String(length=128), nullable=True),
        sa.Column("evaluator_mode", sa.String(length=128), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("limitations_json", sa.JSON(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "evidence_id",
            name="uq_research_graph_evidence_items_run_evidence",
        ),
    )
    op.create_index(op.f("ix_research_graph_evidence_items_run_id"), "research_graph_evidence_items", ["run_id"])
    op.create_index("ix_research_graph_evidence_items_run_source", "research_graph_evidence_items", ["run_id", "source_id"])

    op.create_table(
        "research_graph_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("supported", sa.Boolean(), nullable=True),
        sa.Column("required_source_family", sa.String(length=128), nullable=True),
        sa.Column("support_requirement", sa.String(length=128), nullable=True),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "claim_id", name="uq_research_graph_claims_run_claim"),
    )
    op.create_index(op.f("ix_research_graph_claims_run_id"), "research_graph_claims", ["run_id"])
    op.create_index("ix_research_graph_claims_required_family", "research_graph_claims", ["required_source_family"])

    op.create_table(
        "research_graph_claim_evidence_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_id", sa.String(length=128), nullable=False),
        sa.Column("link_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "claim_id",
            "evidence_id",
            name="uq_research_graph_claim_evidence_links_run_claim_evidence",
        ),
    )
    op.create_index(op.f("ix_research_graph_claim_evidence_links_run_id"), "research_graph_claim_evidence_links", ["run_id"])
    op.create_index("ix_research_graph_claim_evidence_links_run_claim", "research_graph_claim_evidence_links", ["run_id", "claim_id"])

    op.create_table(
        "research_graph_claim_verifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("support_status", sa.String(length=64), nullable=False),
        sa.Column("support_score", sa.Float(), nullable=True),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=True),
        sa.Column("source_ids_json", sa.JSON(), nullable=True),
        sa.Column("notes_json", sa.JSON(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "claim_id",
            name="uq_research_graph_claim_verifications_run_claim",
        ),
    )
    op.create_index(op.f("ix_research_graph_claim_verifications_run_id"), "research_graph_claim_verifications", ["run_id"])
    op.create_index("ix_research_graph_claim_verifications_status", "research_graph_claim_verifications", ["support_status"])

    op.create_table(
        "research_graph_draft_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.String(length=128), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "draft_id", name="uq_research_graph_drafts_run_draft"),
        sa.UniqueConstraint(
            "run_id",
            "draft_version",
            name="uq_research_graph_drafts_run_version",
        ),
    )
    op.create_index(op.f("ix_research_graph_draft_versions_run_id"), "research_graph_draft_versions", ["run_id"])

    op.create_table(
        "research_graph_review_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=64), nullable=False),
        sa.Column("issue_type", sa.String(length=128), nullable=False),
        sa.Column("target_claim_id", sa.String(length=128), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "issue_id",
            name="uq_research_graph_review_issues_run_issue",
        ),
    )
    op.create_index(op.f("ix_research_graph_review_issues_run_id"), "research_graph_review_issues", ["run_id"])
    op.create_index("ix_research_graph_review_issues_run_severity", "research_graph_review_issues", ["run_id", "severity"])

    op.create_table(
        "research_graph_quality_gate_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("gate_id", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=64), nullable=True),
        sa.Column("route_to", sa.String(length=128), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("quality_scores_json", sa.JSON(), nullable=True),
        sa.Column("required_actions_json", sa.JSON(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "gate_id", name="uq_research_graph_gate_results_run_gate"),
    )
    op.create_index(op.f("ix_research_graph_quality_gate_results_run_id"), "research_graph_quality_gate_results", ["run_id"])
    op.create_index("ix_research_graph_quality_gate_results_decision", "research_graph_quality_gate_results", ["decision"])


def downgrade() -> None:
    op.drop_index("ix_research_graph_quality_gate_results_decision", table_name="research_graph_quality_gate_results")
    op.drop_index(op.f("ix_research_graph_quality_gate_results_run_id"), table_name="research_graph_quality_gate_results")
    op.drop_table("research_graph_quality_gate_results")

    op.drop_index("ix_research_graph_review_issues_run_severity", table_name="research_graph_review_issues")
    op.drop_index(op.f("ix_research_graph_review_issues_run_id"), table_name="research_graph_review_issues")
    op.drop_table("research_graph_review_issues")

    op.drop_index(op.f("ix_research_graph_draft_versions_run_id"), table_name="research_graph_draft_versions")
    op.drop_table("research_graph_draft_versions")

    op.drop_index("ix_research_graph_claim_verifications_status", table_name="research_graph_claim_verifications")
    op.drop_index(op.f("ix_research_graph_claim_verifications_run_id"), table_name="research_graph_claim_verifications")
    op.drop_table("research_graph_claim_verifications")

    op.drop_index("ix_research_graph_claim_evidence_links_run_claim", table_name="research_graph_claim_evidence_links")
    op.drop_index(op.f("ix_research_graph_claim_evidence_links_run_id"), table_name="research_graph_claim_evidence_links")
    op.drop_table("research_graph_claim_evidence_links")

    op.drop_index("ix_research_graph_claims_required_family", table_name="research_graph_claims")
    op.drop_index(op.f("ix_research_graph_claims_run_id"), table_name="research_graph_claims")
    op.drop_table("research_graph_claims")

    op.drop_index("ix_research_graph_evidence_items_run_source", table_name="research_graph_evidence_items")
    op.drop_index(op.f("ix_research_graph_evidence_items_run_id"), table_name="research_graph_evidence_items")
    op.drop_table("research_graph_evidence_items")

    op.drop_index("ix_research_graph_sources_domain", table_name="research_graph_sources")
    op.drop_index("ix_research_graph_sources_run_family", table_name="research_graph_sources")
    op.drop_index(op.f("ix_research_graph_sources_run_id"), table_name="research_graph_sources")
    op.drop_table("research_graph_sources")
