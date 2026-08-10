from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NodeToolPolicy:
    allowed_tools: frozenset[str]
    max_tool_calls: int
    allow_network: bool
    allow_state_write: bool
    read_scopes: frozenset[str]


DEFAULT_NODE_TOOL_POLICY = NodeToolPolicy(
    allowed_tools=frozenset(),
    max_tool_calls=0,
    allow_network=False,
    allow_state_write=False,
    read_scopes=frozenset(),
)


NODE_TOOL_POLICIES: dict[str, NodeToolPolicy] = {
    "editor1_draft": NodeToolPolicy(
        allowed_tools=frozenset(
            {
                "get_evidence_bundle",
                "get_source_bundle",
                "compose_section_outline",
            }
        ),
        max_tool_calls=6,
        allow_network=False,
        allow_state_write=False,
        read_scopes=frozenset({"claims", "evidence", "sources", "drafts"}),
    ),
    "editor2_review": NodeToolPolicy(
        allowed_tools=frozenset(
            {
                "get_claim_support_matrix",
                "get_evidence_bundle",
                "get_source_bundle",
                "request_revision",
            }
        ),
        max_tool_calls=8,
        allow_network=False,
        allow_state_write=False,
        read_scopes=frozenset(
            {"claims", "evidence", "sources", "review_issues", "drafts", "claim_support_matrix"}
        ),
    ),
    "chief_gate": NodeToolPolicy(
        allowed_tools=frozenset(
            {
                "get_claim_support_matrix",
                "get_source_bundle",
                "request_replan",
            }
        ),
        max_tool_calls=6,
        allow_network=False,
        allow_state_write=False,
        read_scopes=frozenset(
            {
                "claims",
                "sources",
                "review_issues",
                "quality_scores",
                "claim_verifications",
                "claim_support_matrix",
                "query_requirements",
            }
        ),
    ),
    "finalize_report": NodeToolPolicy(
        allowed_tools=frozenset(
            {
                "get_claim_support_matrix",
                "get_evidence_bundle",
                "compose_final_report",
            }
        ),
        max_tool_calls=5,
        allow_network=False,
        allow_state_write=False,
        read_scopes=frozenset(
            {
                "claims",
                "evidence",
                "sources",
                "quality_scores",
                "review_issues",
                "drafts",
                "claim_support_matrix",
            }
        ),
    ),
}
