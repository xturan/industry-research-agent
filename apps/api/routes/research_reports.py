# ruff: noqa: E501  — HTML template embedded

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from packages.research_reports.schemas import (
    ResearchReportSummary,
    ResearchReportView,
)
from packages.research_reports.service import ResearchReportService

router = APIRouter(prefix="/research-reports", tags=["research-reports"])

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>{title}</title>
<style>
body{{font-family:-apple-system,'Microsoft YaHei',sans-serif;max-width:900px;margin:0 auto;padding:20px;background:#0f1117;color:#e1e4eb}}
h1{{color:#6c8cff;font-size:20px}}h2{{color:#8b8fa3;font-size:14px;margin-top:20px}}
.meta{{font-size:11px;color:#8b8fa3;margin-bottom:16px}}
.card{{background:#1a1d27;border:1px solid #2a2d3a;border-radius:8px;padding:14px;margin-bottom:10px}}
.tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;margin:2px}}
.A{{background:rgba(74,222,128,.15);color:#4ade80}}.B{{background:rgba(108,140,255,.15);color:#6c8cff}}
.C{{background:rgba(251,191,36,.15);color:#fbbf24}}.D{{background:rgba(248,113,113,.15);color:#f87171}}
.summary{{white-space:pre-wrap;line-height:1.7;font-size:13px}}
table{{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px}}
th,td{{text-align:left;padding:6px 10px;border-bottom:1px solid #2a2d3a}}
th{{color:#8b8fa3;font-weight:600}}
a{{color:#6c8cff}}
</style></head><body>
<h1>Research Report</h1>
<div class="meta">{meta}</div>
<div class="card"><div class="summary">{summary}</div></div>
<h2>Key Findings</h2>{findings}
<h2>Evidence Chain</h2>{evidence}
<h2>Sources ({source_count})</h2>
<table><tr><th>Tier</th><th>Title</th><th>URL</th></tr>{sources}</table>
<h2>Data Gaps</h2>{gaps}
<h2>Uncertainties</h2>{uncertainties}
</body></html>"""


@router.get("/{report_id}/html")
def get_report_html(
    report_id: int,
    session: Session = Depends(get_db_session),
):
    from fastapi.responses import HTMLResponse

    report = ResearchReportService(session).get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    rj = report.report_json
    summary = rj.get("executive_summary", "")
    sources = rj.get("source_assessments", [])
    evidence = rj.get("evidence_chain", [])
    findings = rj.get("key_findings", [])
    gaps = rj.get("data_gaps", [])
    uncertainties = rj.get("uncertainties", [])

    meta = (
        f"Query: {report.query} | "
        f"Confidence: {report.overall_confidence} | "
        f"Sources: {report.source_count} | "
        f"Evidence: {report.evidence_count} | "
        f"Credits: {report.tavily_credits}"
    )

    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    findings_html = "".join(
        f'<div class="card">✅ {esc(f)}</div>' for f in findings[:8]
    ) or "<p>None</p>"

    evidence_html = "".join(
        f'<div class="card"><strong>[{esc(e.get("stage","?"))}|{esc(e.get("confidence","?"))}]</strong> '
        f'{esc(e.get("claim",""))}<br>'
        + "".join(f'<a href="{esc(u)}">🔗</a> ' for u in (e.get("source_urls") or [])[:3])
        + '</div>'
        for e in evidence[:10]
    ) or "<p>None</p>"

    sources_html = "".join(
        f'<tr><td><span class="tag {esc(s.get("tier","D"))}">{esc(s.get("tier","D"))}</span></td>'
        f'<td>{esc(s.get("title",""))[:80]}</td>'
        f'<td><a href="{esc(s.get("url",""))}">{esc(s.get("url",""))[:60]}</a></td></tr>'
        for s in sources[:20]
    )

    gaps_html = "".join(
        f'<div class="card">⚠️ {esc(g)}</div>' for g in gaps[:8]
    ) or "<p>None</p>"

    uncertainties_html = "".join(
        f'<div class="card">❓ {esc(u)}</div>' for u in uncertainties[:8]
    ) or "<p>None</p>"

    html = _HTML_TEMPLATE.format(
        title=esc(report.query[:80]),
        meta=meta,
        summary=esc(summary),
        findings=findings_html,
        evidence=evidence_html,
        source_count=len(sources),
        sources=sources_html,
        gaps=gaps_html,
        uncertainties=uncertainties_html,
    )
    return HTMLResponse(content=html)


@router.get("", response_model=list[ResearchReportSummary])
def list_reports(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> list[ResearchReportSummary]:
    return ResearchReportService(session).list_reports(limit)


@router.get("/{report_id}", response_model=ResearchReportView)
def get_report(
    report_id: int,
    session: Session = Depends(get_db_session),
) -> ResearchReportView:
    report = ResearchReportService(session).get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
