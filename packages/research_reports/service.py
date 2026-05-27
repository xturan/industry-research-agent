from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from packages.research_reports.schemas import (
    ResearchReportCreate,
    ResearchReportSummary,
    ResearchReportView,
)

try:
    UTC = datetime.UTC
except AttributeError:
    UTC = timezone.utc  # noqa: UP017


class ResearchReportService:
    """Service for persisting and retrieving Deep Research reports."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._ensure_table()

    def _ensure_table(self) -> None:
        self.session.execute(
            text(
                "CREATE TABLE IF NOT EXISTS research_reports ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  query TEXT NOT NULL,"
                "  report_json TEXT NOT NULL,"
                "  source_count INTEGER DEFAULT 0,"
                "  evidence_count INTEGER DEFAULT 0,"
                "  overall_confidence TEXT DEFAULT 'medium',"
                "  search_rounds INTEGER DEFAULT 0,"
                "  tavily_credits INTEGER DEFAULT 0,"
                "  created_at TEXT NOT NULL"
                ")"
            )
        )
        self.session.commit()

    def save(self, request: ResearchReportCreate) -> ResearchReportView:
        now = datetime.now(UTC)
        self.session.execute(
            text(
                "INSERT INTO research_reports "
                "(query, report_json, source_count, evidence_count, "
                "overall_confidence, search_rounds, tavily_credits, created_at) "
                "VALUES (:q, :rj, :sc, :ec, :oc, :sr, :tc, :ca)"
            ),
            {
                "q": request.query[:500],
                "rj": json.dumps(request.report_json, ensure_ascii=False),
                "sc": request.source_count,
                "ec": request.evidence_count,
                "oc": request.overall_confidence,
                "sr": request.search_rounds,
                "tc": request.tavily_credits,
                "ca": now,
            },
        )
        self.session.commit()
        # Fetch the inserted ID
        row = self.session.execute(
            text("SELECT id FROM research_reports ORDER BY id DESC LIMIT 1")
        ).fetchone()
        report_id = row[0] if row else 0
        return ResearchReportView(
            id=report_id,
            query=request.query,
            report_json=request.report_json,
            source_count=request.source_count,
            evidence_count=request.evidence_count,
            overall_confidence=request.overall_confidence,
            search_rounds=request.search_rounds,
            tavily_credits=request.tavily_credits,
            created_at=now,
        )

    def list_reports(self, limit: int = 20) -> list[ResearchReportSummary]:
        rows = self.session.execute(
            text(
                "SELECT id, query, source_count, evidence_count, "
                "overall_confidence, search_rounds, tavily_credits, created_at "
                "FROM research_reports ORDER BY id DESC LIMIT :lim"
            ),
            {"lim": limit},
        ).fetchall()
        return [
            ResearchReportSummary(
                id=r[0], query=r[1], source_count=r[2], evidence_count=r[3],
                overall_confidence=r[4], search_rounds=r[5], tavily_credits=r[6],
                created_at=r[7],
            )
            for r in rows
        ]

    def get_report(self, report_id: int) -> ResearchReportView | None:
        row = self.session.execute(
            text(
                "SELECT id, query, report_json, source_count, evidence_count, "
                "overall_confidence, search_rounds, tavily_credits, created_at "
                "FROM research_reports WHERE id = :rid"
            ),
            {"rid": report_id},
        ).fetchone()
        if row is None:
            return None
        report_json = row[2]
        if isinstance(report_json, str):
            report_json = json.loads(report_json)
        return ResearchReportView(
            id=row[0], query=row[1], report_json=report_json or {},
            source_count=row[3], evidence_count=row[4],
            overall_confidence=row[5], search_rounds=row[6],
            tavily_credits=row[7], created_at=row[8],
        )
