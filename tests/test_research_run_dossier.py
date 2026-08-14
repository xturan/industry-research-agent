import importlib.util
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.agents.deep_research import DeepResearchAgent
from packages.agents.deep_research_schemas import (
    DeepResearchReport,
    EvidenceItem,
    SourceAssessment,
)
from packages.research_reports.dossier import (
    write_deep_research_dossier,
    write_graph_research_dossier,
)
from packages.research_reports.schemas import ResearchReportCreate
from packages.research_reports.service import ResearchReportService


def _sample_report() -> DeepResearchReport:
    return DeepResearchReport(
        query="lithium policy evidence",
        executive_summary="Evidence indicates policy support, but project-level proof is partial.",
        overall_confidence="medium",
        key_findings=["Policy support exists."],
        source_assessments=[
            SourceAssessment(
                url="https://www.gov.cn/policy.html",
                title="Official policy",
                tier="A",
                authority_score=0.95,
                proximity_score=0.9,
                timeliness_score=0.8,
                verifiability_score=0.9,
                relevance_score=0.7,
                overall_usable=True,
                usage_note="Central government source",
            )
        ],
        evidence_chain=[
            EvidenceItem(
                evidence_id="ev1",
                claim="Policy support exists.",
                source_urls=["https://www.gov.cn/policy.html"],
                stage="policy_statement",
                confidence="high",
                verification_status="verified",
            )
        ],
        search_rounds_executed=1,
        estimated_tavily_credits=1,
    )


def test_write_deep_research_dossier_contains_three_sections(tmp_path: Path) -> None:
    report = _sample_report()
    path = write_deep_research_dossier(
        report_id=7,
        query=report.query,
        report=report,
        context={
            "understanding": {
                "research_dimensions": [
                    {
                        "label": "Policy",
                        "description": "Policy direction",
                        "caliber_terms": ["policy", "notice"],
                        "source_priority": "government",
                    }
                ]
            },
            "round_log": [
                {
                    "round": 1,
                    "objective": "Search policy",
                    "phrases": ["policy notice"],
                    "domains": ["gov.cn"],
                    "status": "completed",
                    "sources_found": 1,
                }
            ],
            "collected_sources": [
                {
                    "round": 1,
                    "title": "Official policy",
                    "url": "https://www.gov.cn/policy.html",
                    "domain": "www.gov.cn",
                    "score": 0.9,
                }
            ],
            "source_evaluator_modes": {
                "https://www.gov.cn/policy.html": "deterministic_rules",
            },
            "source_quality_v2_by_url": {
                "https://www.gov.cn/policy.html": {
                    "tier": "A",
                    "source_role": "official_policy_original",
                    "publisher_authority": 0.98,
                    "auditability": 0.9,
                    "freshness": {
                        "score": 0.86,
                        "label": "fresh",
                        "publication_date": "2026-01-01",
                        "date_source": "search_result_published_date",
                        "age_days": 12,
                        "validity_status": "likely_current",
                        "notes": "Date came from search metadata.",
                    },
                    "query_relevance": {
                        "score": 0.82,
                        "label": "highly_related",
                        "signals": {
                            "query_phrase_match": True,
                            "title_snippet_match": True,
                            "extracted_text_match": False,
                            "source_family_match": True,
                            "discovered_by_phrase": "policy notice",
                            "discovered_phrase_high_intent": True,
                        },
                    },
                    "credibility_score": 0.9,
                    "credibility_label": "high",
                    "usage_role": "primary_evidence_candidate",
                    "not_sufficient_for": ["winning bid evidence"],
                    "reason": "Official source with strong source-layer quality.",
                }
            },
            "trace_events": [
                {
                    "event_id": 1,
                    "step": "query_understanding",
                    "agent": "DeepResearchAgent",
                    "event_type": "llm_call",
                    "status": "completed",
                    "inputs": {
                        "system_prompt": "system prompt",
                        "user_prompt": "user prompt",
                    },
                    "outputs": {
                        "content_text": '{"research_dimensions":[]}',
                        "json_data": {"research_dimensions": []},
                    },
                    "metadata": {
                        "provider": "fake",
                        "model": "fake-model",
                        "response_ms": 12.3,
                    },
                }
            ],
            "debate": {"theses": [{"thesis_id": "t1"}]},
            "counter_evidence": [],
        },
        base_dir=tmp_path,
    )

    text = path.read_text(encoding="utf-8")
    assert "## 1. Query And Sources" in text
    assert "## 2. Evidence And Agent Pipeline" in text
    assert "## 3. Content Assets And Generation Trace" in text
    assert "### Detailed Agent Trace" in text
    assert "Trace Event 1" in text
    assert "system prompt" in text
    assert "deterministic_rules" in text
    assert "### Source Quality v2" in text
    assert "`query_relevance`" in text
    assert "query phrase match" in text
    assert "源的角色" in text
    assert "Policy support exists." in text


def test_research_report_service_persists_dossier_path(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'reports.db').as_posix()}")
    with Session(engine) as session:
        service = ResearchReportService(session)
        saved = service.save(
            ResearchReportCreate(
                query="test",
                report_json={"query": "test"},
                dossier_path="data/run_dossiers/demo/dossier.md",
            )
        )
        service.update_dossier_path(saved.id, "data/run_dossiers/demo/updated.md")
        fetched = service.get_report(saved.id)

    assert fetched is not None
    assert fetched.dossier_path == "data/run_dossiers/demo/updated.md"
    assert fetched.report_json["dossier_path"] == (
        "data/run_dossiers/demo/updated.md"
    )

    with Session(engine) as session:
        summaries = ResearchReportService(session).list_reports()
    assert summaries[0].dossier_path == "data/run_dossiers/demo/updated.md"


def test_research_report_service_adds_dossier_path_to_old_table(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE research_reports ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "query TEXT NOT NULL, report_json TEXT NOT NULL, "
            "source_count INTEGER DEFAULT 0, evidence_count INTEGER DEFAULT 0, "
            "overall_confidence TEXT DEFAULT 'medium', "
            "search_rounds INTEGER DEFAULT 0, tavily_credits INTEGER DEFAULT 0, "
            "created_at TEXT NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO research_reports "
            "(query, report_json, created_at) "
            "VALUES ('legacy', "
            "'{\"query\": \"legacy\", "
            "\"dossier_path\": \"data/run_dossiers/legacy/original.md\"}', "
            "'2026-07-15')"
        )

    with Session(engine) as session:
        service = ResearchReportService(session)
        summaries = service.list_reports()
        assert summaries[0].dossier_path == (
            "data/run_dossiers/legacy/original.md"
        )
        service.update_dossier_path(1, "data/run_dossiers/legacy/dossier.md")
        fetched = service.get_report(1)

    assert fetched is not None
    assert fetched.dossier_path == "data/run_dossiers/legacy/dossier.md"
    assert fetched.report_json["dossier_path"] == (
        "data/run_dossiers/legacy/dossier.md"
    )


def test_research_report_service_preserves_embedded_dossier_path(
    tmp_path: Path,
) -> None:
    engine = create_engine(
        f"sqlite+pysqlite:///{(tmp_path / 'embedded.db').as_posix()}"
    )
    with Session(engine) as session:
        service = ResearchReportService(session)
        saved = service.save(
            ResearchReportCreate(
                query="embedded",
                report_json={
                    "query": "embedded",
                    "dossier_path": "data/run_dossiers/embedded/dossier.md",
                },
            )
        )
        fetched = service.get_report(saved.id)
        summaries = service.list_reports()

    assert fetched is not None
    assert fetched.dossier_path == "data/run_dossiers/embedded/dossier.md"
    assert summaries[0].dossier_path == "data/run_dossiers/embedded/dossier.md"


def test_write_graph_research_dossier_contains_context_pack_sections(tmp_path: Path) -> None:
    path = write_graph_research_dossier(
        run_id=9,
        query="低空经济 中标公告",
        response_json={
            "run_id": 9,
            "thread_id": "research_run:9",
            "status": "succeeded",
            "decision": "PASS",
            "quality_scores": {
                "evidence_coverage": 1.0,
                "citation_integrity": 0.96,
                "source_quality": 0.84,
                "final_score": 0.9,
            },
            "node_steps": [
                {
                    "node_name": "parse_sources",
                    "agent_name": "Parser/Structurer",
                    "status": "succeeded",
                    "output_summary": {
                        "source_count": 2,
                    },
                },
                {
                    "node_name": "editor1_draft",
                    "agent_name": "Editor1",
                    "status": "succeeded",
                    "output_summary": {
                        "draft_version": 1,
                        "contract_meta": {
                            "editor1_draft": {
                                "status": "normalized",
                                "attempt_count": 1,
                                "used_fallback": False,
                                "input_mode": "provider_backed_v1",
                                "llm_mode": "live_provider",
                                "attempts": [
                                    {
                                        "mode": "validate_dict",
                                        "status": "success",
                                        "normalizations": [
                                            "editor_draft_numeric_confidence_to_label"
                                        ],
                                    }
                                ],
                                "tooling": {
                                    "evidence_bundle_tool_status": "allowed",
                                    "outline_tool_status": "allowed",
                                },
                            }
                        },
                    },
                },
            ],
            "context_packs": [
                {
                    "context_pack_id": "ctx_parse_sources_1",
                    "node_name": "parse_sources",
                    "agent_name": "Parser/Structurer",
                    "prompt_version": "shadow_v1.parse_sources",
                    "input_hash": "abc123",
                    "included_source_ids": ["src_policy"],
                    "included_evidence_ids": [],
                    "included_claim_ids": [],
                    "included_issue_ids": [],
                    "included_fields": ["query", "sources"],
                    "context_budget_tokens": 32,
                    "token_estimate": 42,
                    "budget_status": "over_budget",
                    "budget_overage_tokens": 10,
                    "sanitization_summary": {
                        "raw_text_chars": 120,
                        "clean_text_chars": 80,
                        "removed_markers": ["[首页]", "打印", "javascript:void(0)"],
                        "removed_marker_count": 3,
                    },
                }
            ],
            "report_preview": {"executive_summary": "shadow summary"},
            "planner_metadata": {
                "planner_mode": "deterministic_fallback",
                "planner_provider": "deterministic",
                "planner_model": "offline_rules_v1",
                "deterministic_fallback": True,
                "summary_memory_used": True,
                "summary_memory_keys": ["recurring_themes", "repeated_gaps"],
            },
            "dossier_path": "",
        },
        context={
            "node_steps": [
                {
                    "node_name": "parse_sources",
                    "agent_name": "Parser/Structurer",
                    "status": "succeeded",
                    "output_summary": {"source_count": 2},
                },
                {
                    "node_name": "editor1_draft",
                    "agent_name": "Editor1",
                    "status": "succeeded",
                    "output_summary": {
                        "draft_version": 1,
                        "contract_meta": {
                            "editor1_draft": {
                                "status": "normalized",
                                "attempt_count": 1,
                                "used_fallback": False,
                                "input_mode": "provider_backed_v1",
                                "llm_mode": "live_provider",
                                "attempts": [
                                    {
                                        "mode": "validate_dict",
                                        "status": "success",
                                        "normalizations": [
                                            "editor_draft_numeric_confidence_to_label"
                                        ],
                                    }
                                ],
                                "tooling": {
                                    "evidence_bundle_tool_status": "allowed",
                                    "outline_tool_status": "allowed",
                                },
                            }
                        },
                    },
                },
            ],
            "context_packs": [
                {
                    "context_pack_id": "ctx_parse_sources_1",
                    "node_name": "parse_sources",
                    "agent_name": "Parser/Structurer",
                    "prompt_version": "shadow_v1.parse_sources",
                    "input_hash": "abc123",
                    "included_source_ids": ["src_policy"],
                    "included_evidence_ids": [],
                    "included_claim_ids": [],
                    "included_issue_ids": [],
                    "included_fields": ["query", "sources"],
                    "context_budget_tokens": 32,
                    "token_estimate": 42,
                    "budget_status": "over_budget",
                    "budget_overage_tokens": 10,
                    "sanitization_summary": {
                        "raw_text_chars": 120,
                        "clean_text_chars": 80,
                        "removed_markers": ["[首页]", "打印", "javascript:void(0)"],
                        "removed_marker_count": 3,
                    },
                }
            ],
            "plan": {
                "research_dimensions": [
                    {
                        "dimension_id": "d_policy",
                        "label": "official policy grounding",
                        "description": "policy documents",
                        "caliber_terms": ["低空经济 政策"],
                        "source_priority": "government",
                    }
                ],
                "dimension_plan": [
                    {
                        "dimension_id": "d_policy",
                        "dimension_type": "policy",
                        "research_question": "What official policy supports low-altitude economy?",
                        "why_it_matters": "Policy grounding keeps the report auditable.",
                        "coverage_required": "Collect at least one official policy source.",
                        "expected_section_heading": "政策依据与口径",
                        "source_priority": "government",
                        "source_families": ["official_policy"],
                        "caliber_terms": ["低空经济 政策"],
                    },
                    {
                        "dimension_id": "d_execution",
                        "dimension_type": "execution",
                        "research_question": (
                            "What project or procurement evidence shows execution?"
                        ),
                        "why_it_matters": "Execution evidence separates intent from rollout.",
                        "coverage_required": "Collect auditable project or procurement notices.",
                        "expected_section_heading": "项目与执行证据",
                        "source_priority": "mixed",
                        "source_families": ["public_resource_transaction"],
                        "caliber_terms": ["低空经济 中标公告"],
                    },
                ],
                "search_rounds": [
                    {
                        "round_number": 1,
                        "objective": "collect policy",
                        "search_phrases": ["低空经济 政策"],
                    },
                    {
                        "round_number": 2,
                        "objective": "collect execution",
                        "search_phrases": ["低空经济 中标公告"],
                    },
                ],
                "source_obligations": [
                    {"obligation_id": "obl_policy_primary", "source_family": "official_policy"},
                    {
                        "obligation_id": "obl_procurement_award",
                        "source_family": "public_resource_transaction",
                    },
                ],
            },
            "planner_metadata": {
                "planner_mode": "deterministic_fallback",
                "planner_provider": "deterministic",
                "planner_model": "offline_rules_v1",
                "deterministic_fallback": True,
                "summary_memory_used": True,
                "summary_memory_keys": ["recurring_themes", "repeated_gaps"],
            },
            "summary_memory": {
                "recurring_themes": ["政策先行", "执行验证"],
                "repeated_gaps": ["缺少项目公示"],
            },
            "retrieval_pack": {
                "query": "低空经济 中标公告",
                "retrieval_mode": "graph_runtime_hybrid_contract_v1",
                "dimension_focus": [
                    {
                        "dimension_id": "d_policy",
                        "dimension_type": "policy",
                        "expected_section_heading": "政策依据与口径",
                        "source_families": ["official_policy"],
                        "caliber_terms": ["低空经济 政策"],
                    }
                ],
                "obligation_focus": [
                    {
                        "obligation_id": "obl_policy_primary",
                        "source_family": "official_policy",
                        "required_for": "policy grounding",
                        "min_required_evidence": 1,
                    }
                ],
                "total_candidates": 3,
                "returned_count": 2,
                "notes": ["Built graph-local chunks from current source text."],
                "items": [
                    {
                        "chunk_id": 10000001,
                        "document_title": "Policy source",
                        "score": 1.15,
                        "citation_locator": "https://www.gov.cn/policy.html | chunk:0",
                        "chunk_text": "低空经济政策正文。",
                    }
                ],
            },
            "quality_scores": {"final_score": 0.9},
            "decision": "PASS",
            "final_report": {"executive_summary": "shadow summary"},
            "search_events": [
                {
                    "round_number": 1,
                    "search_phrase": "低空经济 中标公告",
                    "status": "success",
                    "result_count": 2,
                    "estimated_credits": 1,
                    "errors": [],
                }
            ],
            "sources": [
                {
                    "source_id": "src_policy",
                    "url": "https://www.gov.cn/policy.html",
                    "title": "Policy source",
                    "source_family": "official_policy",
                    "source_quality_v2": {
                        "tier": "A",
                        "source_role": "official_policy_original",
                        "usage_role": "primary_evidence_candidate",
                        "credibility_score": 0.88,
                    },
                    "raw_text_meta": {"retained_chars": 120},
                    "search_phrase": "低空经济 政策",
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_1",
                    "source_id": "src_policy",
                    "support_type": "background_support",
                    "support_strength": 0.58,
                    "specificity": "policy_statement",
                    "evaluator_mode": "rule_based_provider_backed_v1",
                    "summary": "policy summary",
                    "limitations": ["not procurement evidence"],
                }
            ],
            "claims": [
                {
                    "claim_id": "claim_policy_primary",
                    "supported": True,
                    "required_source_family": "official_policy",
                    "support_requirement": "policy_statement",
                    "evidence_ids": ["ev_1"],
                    "text": "policy claim",
                }
            ],
            "claim_verifications": [
                {
                    "claim_id": "claim_policy_primary",
                    "support_status": "supported",
                    "support_score": 0.58,
                    "evidence_ids": ["ev_1"],
                    "source_ids": ["src_policy"],
                    "notes": [],
                }
            ],
            "tool_traces": [
                {
                    "trace_id": "editor1_draft_1_get_evidence_bundle",
                    "node_name": "editor1_draft",
                    "agent_name": "Editor1",
                    "tool_name": "get_evidence_bundle",
                    "tool_kind": "read_only",
                    "call_index": 1,
                    "status": "allowed",
                    "reason_code": "allowed",
                    "message": "tool call allowed",
                    "args_summary": {"keys": ["claim_ids"], "hash": "abc123"},
                    "result_summary": {"keys": ["claim_count", "evidence_count", "items"]},
                }
            ],
        },
        base_dir=tmp_path,
    )

    text = path.read_text(encoding="utf-8")
    assert "## 1. Graph Overview" in text
    assert "### Planner Contract" in text
    assert "## 2. Node Execution Trace" in text
    assert "## 3. Source, Evidence, And Claim State" in text
    assert "### Search Events" in text
    assert "### Sources" in text
    assert "### Evidence" in text
    assert "### Claims" in text
    assert "### Claim Verifications" in text
    assert "### Contract Diagnostics" in text
    assert "## 4. Context Packs" in text
    assert "## 5. Tool Traces" in text
    assert "## 6. Human Review" in text
    assert "## 7. Final Report Preview" in text
    assert "Summary Memory Used" in text
    assert "Dimension Plan Count" in text
    assert "政策依据与口径" in text
    assert "项目与执行证据" in text
    assert "recurring_themes" in text
    assert "### Retrieval Pack" in text
    assert "graph_runtime_hybrid_contract_v1" in text
    assert "#### Retrieval Focus Contract" in text
    assert "obl_policy_primary" in text
    assert "`search_events`" in text
    assert "`support_status`" in text
    assert "editor_draft_numeric_confidence_to_label" in text
    assert "evidence_bundle_tool_status=allowed" in text
    assert "`context_pack_id`" in text
    assert "`prompt_version`" in text
    assert "`input_hash`" in text
    assert "`included_source_ids`" in text
    assert "`token_estimate`" in text
    assert "`budget_status`" in text
    assert "`budget_overage_tokens`" in text
    assert "removed_markers" in text
    assert "javascript:void(0)" in text
    assert "get_evidence_bundle" in text


def test_deep_research_agent_records_visible_llm_trace() -> None:
    class FakeClient:
        def generate_json(self, **_: object) -> SimpleNamespace:
            return SimpleNamespace(
                json_data={"answer": "ok"},
                content_text='{"answer":"ok"}',
                metadata=SimpleNamespace(
                    provider="fake",
                    model="fake-model",
                    request_id="req-1",
                    usage={"total_tokens": 3},
                    finish_reason="stop",
                    response_ms=7.5,
                ),
            )

    agent = DeepResearchAgent(deepseek_client=FakeClient())
    response = agent._call_llm(
        system_prompt="system with api_key=secret-value",
        user_prompt="user prompt",
        step="unit_step",
        agent_name="Unit Agent",
    )

    assert response["json_data"] == {"answer": "ok"}
    event = agent._trace_events[-1]
    assert event["event_type"] == "llm_call"
    assert event["step"] == "unit_step"
    assert event["agent"] == "Unit Agent"
    assert event["outputs"]["json_data"] == {"answer": "ok"}
    assert event["metadata"]["usage"] == {"total_tokens": 3}
    assert "secret-value" not in event["inputs"]["system_prompt"]


def test_graph_contract_diagnostics_helpers_capture_normalization_and_budget() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "graph_provider_backed_smoke.py"
    spec = importlib.util.spec_from_file_location("graph_provider_backed_smoke", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    response = {
        "node_steps": [
            {
                "node_name": "editor1_draft",
                "output_summary": {
                    "contract_meta": {
                        "editor1_draft": {
                            "status": "normalized",
                            "used_fallback": False,
                            "attempt_count": 1,
                            "input_mode": "provider_backed_v1",
                            "llm_mode": "live_provider",
                            "attempts": [
                                {
                                    "mode": "validate_dict",
                                    "status": "success",
                                    "normalizations": [
                                        "editor_draft_numeric_confidence_to_label"
                                    ],
                                }
                            ],
                        }
                    }
                },
            }
        ],
        "context_packs": [
            {
                "node_name": "editor1_draft",
                "context_pack_id": "ctx_editor1",
                "token_estimate": 128,
                "context_budget_tokens": 64,
                "budget_status": "over_budget",
                "budget_overage_tokens": 64,
            }
        ],
    }

    diagnostics = module._contract_diagnostics_from_response(response)

    assert diagnostics
    assert diagnostics[0]["node_name"] == "editor1_draft"
    assert diagnostics[0]["status"] == "normalized"
    assert diagnostics[0]["used_fallback"] is False
    assert diagnostics[0]["normalizations"] == [
        "editor_draft_numeric_confidence_to_label"
    ]


def test_graph_smoke_exports_only_real_final_report_markdown(
    tmp_path: Path,
) -> None:
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "graph_provider_backed_smoke.py"
    )
    spec = importlib.util.spec_from_file_location(
        "graph_provider_backed_smoke_export",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    artifact = module._write_final_report_artifact(
        {"report_markdown": "  # Final Report\n\nVerified body.  "},
        tmp_path,
    )

    assert artifact == tmp_path / "FINAL_REPORT.md"
    assert artifact.read_text(encoding="utf-8") == (
        "# Final Report\n\nVerified body."
    )

    artifact.unlink()
    assert module._write_final_report_artifact(
        {"report_markdown": "   "},
        tmp_path,
    ) is None
    assert not artifact.exists()
