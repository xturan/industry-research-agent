from packages.research_harness.state import build_initial_state


def test_build_initial_state_reuses_run_and_thread_ids() -> None:
    state = build_initial_state(
        run_id=12,
        task_job_id=34,
        query="低空经济 中标公告",
        max_rounds=2,
        max_loop_count=1,
    )

    assert state["run_id"] == 12
    assert state["task_job_id"] == 34
    assert state["thread_id"] == "research_run:12"
    assert state["loop_count"] == 0
    assert state["summary_memory"] == {}
    assert state["sources"] == []
    assert state["source_chunks"] == []
    assert state["retrieval_pack"] == {}
    assert state["evidence"] == []
