from __future__ import annotations

from langgraph.graph import END, StateGraph

from packages.research_harness.nodes import (
    advisory_gap_backfill,
    build_evidence,
    chief_gate,
    collect_sources,
    editor1_draft,
    editor2_review,
    finalize_report,
    human_review,
    parse_sources,
    plan_task,
    score_sources,
    structured_shadow_editor1,
)
from packages.research_harness.state import ResearchGraphState


def build_research_graph(runner) -> object:
    graph = StateGraph(ResearchGraphState)
    graph.add_node("plan_task", runner.make_node_handler("plan_task", "Planner", plan_task))
    graph.add_node(
        "collect_sources",
        runner.make_node_handler("collect_sources", "Source Hunter", collect_sources),
    )
    graph.add_node(
        "parse_sources",
        runner.make_node_handler("parse_sources", "Parser/Structurer", parse_sources),
    )
    graph.add_node(
        "score_sources",
        runner.make_node_handler("score_sources", "Source Quality v2", score_sources),
    )
    graph.add_node(
        "build_evidence",
        runner.make_node_handler("build_evidence", "Evidence Builder", build_evidence),
    )
    # B.3.3b: shadow advisory gap backfill. Edge is FIXED (-> editor1_draft);
    # it is NOT a loop-control node and never changes routing based on results.
    graph.add_node(
        "advisory_gap_backfill",
        runner.make_node_handler(
            "advisory_gap_backfill", "Advisory Gap Backfill", advisory_gap_backfill
        ),
    )
    # C.2: claim-constrained StructuredDraft shadow. Edge is FIXED
    # (-> editor1_draft); never changes routing based on validation results.
    graph.add_node(
        "structured_shadow_editor1",
        runner.make_node_handler(
            "structured_shadow_editor1", "Structured Shadow Editor1",
            structured_shadow_editor1,
        ),
    )
    graph.add_node(
        "editor1_draft",
        runner.make_node_handler("editor1_draft", "Editor1", editor1_draft),
    )
    graph.add_node(
        "editor2_review",
        runner.make_node_handler("editor2_review", "Editor2", editor2_review),
    )
    graph.add_node(
        "chief_gate",
        runner.make_node_handler("chief_gate", "Chief Gate", chief_gate),
    )
    graph.add_node(
        "human_review",
        runner.make_node_handler("human_review", "Human Review", human_review),
    )
    graph.add_node(
        "finalize_report",
        runner.make_node_handler("finalize_report", "Supervisor", finalize_report),
    )

    graph.set_entry_point("plan_task")
    graph.add_edge("plan_task", "collect_sources")
    graph.add_edge("collect_sources", "parse_sources")
    graph.add_edge("parse_sources", "score_sources")
    graph.add_edge("score_sources", "build_evidence")
    graph.add_edge("build_evidence", "advisory_gap_backfill")
    graph.add_edge("advisory_gap_backfill", "structured_shadow_editor1")
    graph.add_edge("structured_shadow_editor1", "editor1_draft")
    graph.add_edge("editor1_draft", "editor2_review")
    graph.add_edge("editor2_review", "chief_gate")
    graph.add_conditional_edges(
        "chief_gate",
        runner.route_after_chief_gate,
        {
            "PASS": "finalize_report",
            "ADD_EVIDENCE": "plan_task",
            "REVISE_TEXT": "editor1_draft",
            "REVIEW_RISK": "editor2_review",
            "HUMAN_REVIEW": "human_review",
            "FAILED": "finalize_report",
        },
    )
    graph.add_edge("human_review", END)
    graph.add_edge("finalize_report", END)
    return graph.compile()
