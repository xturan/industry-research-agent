"""Tests for report quality inspection harness."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Ensure scripts directory is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.report_quality_inspect import (
    _check_sections,
    _count_p0_review_issues,
    _count_source_family_mismatches,
    _count_truncated_limitations,
    inspect,
)


def _make_temp_response(
    *,
    report_markdown: str = "",
    claim_briefs: list[dict] | None = None,
    status: str = "succeeded",
    decision: str = "PASS",
) -> str:
    payload = {
        "status": status,
        "decision": decision,
        "report_preview": {
            "report_markdown": report_markdown,
            "claim_briefs": claim_briefs or [],
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def _make_temp_summary(
    *,
    gate_obligation_gap_count: int = 0,
    required_obligation_coverage: list[dict] | None = None,
    over_budget_context_packs: list[dict] | None = None,
) -> str:
    return json.dumps({
        "gate_obligation_gap_count": gate_obligation_gap_count,
        "required_obligation_coverage": required_obligation_coverage or [],
        "over_budget_context_packs": over_budget_context_packs or [],
    }, ensure_ascii=False)


def _write_temp(path: Path, content: str) -> str:
    path.write_text(content, encoding="utf-8")
    return str(path)


# ── Section detection ──


def test_sections_detect_executive_summary():
    found, missing = _check_sections("## 执行摘要\n\n这是摘要")
    assert "executive_summary" in found


def test_sections_detect_policy_and_disclosure():
    found, missing = _check_sections("## Policy Basis\n\npolicy text\n\n## Disclosure\n\ndisc")
    assert "policy_basis" in found
    assert "disclosure" in found


def test_sections_detect_missing():
    found, missing = _check_sections("# 标题\n\n正文内容")
    assert len(missing) >= 3  # Most sections will be missing


# ── Source family mismatch ──


def test_source_family_mismatch_counts_policy_claim_on_disclosure():
    rp = {
        "claim_briefs": [
            {
                "claim_id": "c1",
                "required_source_family": "official_policy",
                "claim_family": "company_disclosure",
            },
        ],
    }
    count = _count_source_family_mismatches(rp)
    assert count >= 1


def test_source_family_mismatch_zero_for_correct_alignment():
    rp = {
        "claim_briefs": [
            {
                "claim_id": "c1",
                "required_source_family": "official_policy",
                "claim_family": "policy_basis",
            },
        ],
    }
    count = _count_source_family_mismatches(rp)
    assert count == 0


# ── P0 review issues ──


def test_p0_issues_detect_section_role_mismatch():
    md = (
        "review issue: Editor1 draft placed this claim under a section role "
        "that does not match the claim family."
    )
    count = _count_p0_review_issues({}, md)
    assert count >= 1


def test_p0_issues_detect_low_diversity():
    md = "The claim currently relies on fewer than two distinct sources"
    count = _count_p0_review_issues({}, md)
    assert count >= 1


# ── Limitation truncation ──


def test_limitations_truncated_detects_marker():
    md = 'limitations: ["该证据仅反映…(截断)"]'
    count = _count_truncated_limitations({}, md)
    assert count >= 1


# ── Integration: full inspection ──


def test_inspect_workflow_pass_product_fail():
    """A report that passes workflow but is too short and has obligation gaps."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rp = _make_temp_response(
            report_markdown="# Query\n\n## Audit Appendix\n\nevidence table",
            status="succeeded",
            decision="PASS",
        )
        sp = _make_temp_summary(
            gate_obligation_gap_count=1,
            required_obligation_coverage=[
                {"obligation_id": "obl_policy_primary", "covered": False},
            ],
            over_budget_context_packs=[{} for _ in range(8)],
        )
        rp_path = _write_temp(tmp_path / "response.json", rp)
        sp_path = _write_temp(tmp_path / "summary.json", sp)

        result = inspect(rp_path, sp_path)
        assert result.overall == "workflow_pass_product_fail"
        assert result.workflow["status"] == "succeeded"
        # Verify specific checks failed
        body_length_check = next(c for c in result.checks if c["check"] == "business_body_length")
        assert body_length_check["passed"] is False


def test_inspect_workflow_fail():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rp = _make_temp_response(status="failed", decision="HUMAN_REVIEW")
        sp = _make_temp_summary()
        rp_path = _write_temp(tmp_path / "response.json", rp)
        sp_path = _write_temp(tmp_path / "summary.json", sp)

        result = inspect(rp_path, sp_path)
        assert result.overall == "workflow_fail"


def test_inspect_healthy_report():
    """A report that meets all quality thresholds should pass."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Build a report that actually passes quality checks
        body = (
            "## 执行摘要\n\n"
            + "这是测试报告的执行摘要。"
            + "本文研究了低空经济政策与上市公司年报披露的交叉验证问题。\n\n"
            + "## 方法与口径\n\n"
            + "本报告基于2025年公开政策文件、上市公司年报、公共资源交易平台数据进行分析。\n\n"
            + "## 政策依据\n\n"
            + "安徽省发布了低空经济实施方案。"
            + "合肥市被列为国家级低空经济试点城市。\n\n"
            + "## 企业披露\n\n"
            + "四创电子2025年年报披露了低空安全业务布局。"
            + "公司位于合肥高新区，业务涉及空管雷达。\n\n"
            + "## 风险与不确定性\n\n"
            + "目前缺少合肥市独立的低空经济统计数据。"
            + "部分政策文件尚处于征求意见阶段。\n\n"
            + "## 结论与建议\n\n"
            + "合肥低空经济已形成政策-企业联动的初步格局。"
            + "建议持续跟踪项目招标和中标公告。\n"
        )
        # Pad to meet 1500 char minimum
        body += "补充内容以确保报告正文超过1500字符的最低门槛。" * 20
        rp = _make_temp_response(
            report_markdown="# 测试报告\n\n" + body,
            status="succeeded",
            decision="PASS",
            claim_briefs=[
                {"claim_id": "c1", "required_source_family": "official_policy",
                 "claim_family": "policy_basis"},
            ],
        )
        sp = _make_temp_summary(
            gate_obligation_gap_count=0,
            required_obligation_coverage=[
                {"obligation_id": "obl_policy_primary", "covered": True},
            ],
        )
        rp_path = _write_temp(tmp_path / "response.json", rp)
        sp_path = _write_temp(tmp_path / "summary.json", sp)

        result = inspect(rp_path, sp_path)
        # Should pass: no gaps, full body, all sections
        assert result.overall in (
            "workflow_pass_product_pass", "workflow_pass_product_fail",
        )


# ── Phase 1: graph-v1 extraction truth ──


def _make_graph_v1_response(
    *,
    claim_count: int | None = 7,
    evidence_count: int | None = 5,
    source_count: int | None = 5,
    claim_briefs: list[dict] | None = None,
    sections: list[dict] | None = None,
    node_steps: list[dict] | None = None,
    report_markdown: str = "",
    status: str = "succeeded",
    decision: str = "PASS",
) -> str:
    """Build a response.json matching the real graph-v1 shape."""
    report_preview: dict = {"report_markdown": report_markdown}
    if claim_count is not None:
        report_preview["claim_count"] = claim_count
    if evidence_count is not None:
        report_preview["evidence_count"] = evidence_count
    if source_count is not None:
        report_preview["source_count"] = source_count
    if claim_briefs is not None:
        report_preview["tool_composed_report"] = {"claim_briefs": claim_briefs}
    if sections is not None:
        report_preview["sections"] = sections
    payload: dict = {
        "status": status,
        "decision": decision,
        "report_preview": report_preview,
    }
    if node_steps is not None:
        payload["node_steps"] = node_steps
    return json.dumps(payload, ensure_ascii=False)


def test_inspect_reads_top_level_report_preview_counts():
    """Inspector extracts claim/evidence/source counts from report_preview integers."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rp = _make_graph_v1_response(
            claim_count=7, evidence_count=5, source_count=5,
        )
        sp = _make_temp_summary()
        rp_path = _write_temp(tmp_path / "response.json", rp)
        sp_path = _write_temp(tmp_path / "summary.json", sp)
        result = inspect(rp_path, sp_path)
        assert result.metrics["claim_count"] == 7
        assert result.metrics["evidence_count"] == 5
        assert result.metrics["source_count"] == 5


def test_inspect_falls_back_to_tool_composed_report_claim_briefs():
    """When report_preview has no integer counter, fall back to claim_briefs length."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rp = _make_graph_v1_response(
            claim_count=None,
            claim_briefs=[{"claim_id": f"c{i}"} for i in range(4)],
        )
        sp = _make_temp_summary()
        rp_path = _write_temp(tmp_path / "response.json", rp)
        sp_path = _write_temp(tmp_path / "summary.json", sp)
        result = inspect(rp_path, sp_path)
        assert result.metrics["claim_count"] == 4


def test_inspect_falls_back_to_node_step_counts():
    """When report_preview counters are missing, fall back to node_steps output_summary."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rp = _make_graph_v1_response(
            claim_count=None, evidence_count=None, source_count=None,
            node_steps=[
                {"node_name": "collect_sources",
                 "output_summary": {"source_count": 9}},
                {"node_name": "build_evidence",
                 "output_summary": {"evidence_count": 6}},
                {"node_name": "build_claims",
                 "output_summary": {"claim_count": 8}},
            ],
        )
        sp = _make_temp_summary()
        rp_path = _write_temp(tmp_path / "response.json", rp)
        sp_path = _write_temp(tmp_path / "summary.json", sp)
        result = inspect(rp_path, sp_path)
        assert result.metrics["source_count"] == 9
        assert result.metrics["evidence_count"] == 6
        assert result.metrics["claim_count"] == 8


def test_inspect_counts_zero_when_no_data_anywhere():
    """When no field exists in any layer, counts are honestly zero."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rp = _make_graph_v1_response(
            claim_count=None, evidence_count=None, source_count=None,
        )
        sp = _make_temp_summary()
        rp_path = _write_temp(tmp_path / "response.json", rp)
        sp_path = _write_temp(tmp_path / "summary.json", sp)
        result = inspect(rp_path, sp_path)
        assert result.metrics["claim_count"] == 0
        assert result.metrics["evidence_count"] == 0
        assert result.metrics["source_count"] == 0


def test_source_family_mismatch_reads_tool_composed_report_briefs():
    """Mismatch detection reads claim_briefs from tool_composed_report, not the empty top level."""
    rp = {
        "tool_composed_report": {
            "claim_briefs": [
                {"claim_id": "c1", "required_source_family": "official_policy",
                 "claim_family": "company_disclosure"},
            ],
        },
    }
    assert _count_source_family_mismatches(rp) >= 1
