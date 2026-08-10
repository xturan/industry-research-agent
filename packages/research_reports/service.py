from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import inspect, text
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
                "  dossier_path TEXT,"
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
        columns = {
            str(column["name"])
            for column in inspect(self.session.get_bind()).get_columns(
                "research_reports"
            )
        }
        if "dossier_path" not in columns:
            self.session.execute(
                text("ALTER TABLE research_reports ADD COLUMN dossier_path TEXT")
            )
            self.session.commit()

    def save(self, request: ResearchReportCreate) -> ResearchReportView:
        now = datetime.now(UTC)
        report_json = dict(request.report_json)
        dossier_path = (
            request.dossier_path
            if request.dossier_path is not None
            else _embedded_dossier_path(report_json)
        )
        report_json["dossier_path"] = dossier_path
        self.session.execute(
            text(
                "INSERT INTO research_reports "
                "(query, report_json, dossier_path, source_count, evidence_count, "
                "overall_confidence, search_rounds, tavily_credits, created_at) "
                "VALUES (:q, :rj, :dp, :sc, :ec, :oc, :sr, :tc, :ca)"
            ),
            {
                "q": request.query[:500],
                "rj": json.dumps(report_json, ensure_ascii=False),
                "dp": dossier_path,
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
            report_json=report_json,
            dossier_path=dossier_path,
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
                "SELECT id, query, dossier_path, report_json, source_count, "
                "evidence_count, "
                "overall_confidence, search_rounds, tavily_credits, created_at "
                "FROM research_reports ORDER BY id DESC LIMIT :lim"
            ),
            {"lim": limit},
        ).fetchall()
        reports: list[ResearchReportSummary] = []
        for row in rows:
            report_json = _decode_report_json(row[3])
            reports.append(
                ResearchReportSummary(
                    id=row[0],
                    query=row[1],
                    dossier_path=row[2] or _embedded_dossier_path(report_json),
                    source_count=row[4],
                    evidence_count=row[5],
                    overall_confidence=row[6],
                    search_rounds=row[7],
                    tavily_credits=row[8],
                    created_at=row[9],
                )
            )
        return reports

    def get_report(self, report_id: int) -> ResearchReportView | None:
        row = self.session.execute(
            text(
                "SELECT id, query, report_json, dossier_path, source_count, "
                "evidence_count, "
                "overall_confidence, search_rounds, tavily_credits, created_at "
                "FROM research_reports WHERE id = :rid"
            ),
            {"rid": report_id},
        ).fetchone()
        if row is None:
            return None
        report_json = _decode_report_json(row[2])
        dossier_path = row[3] or _embedded_dossier_path(report_json)
        report_json["dossier_path"] = dossier_path
        return ResearchReportView(
            id=row[0], query=row[1], report_json=report_json or {},
            dossier_path=dossier_path, source_count=row[4], evidence_count=row[5],
            overall_confidence=row[6], search_rounds=row[7],
            tavily_credits=row[8], created_at=row[9],
        )

    def update_dossier_path(self, report_id: int, dossier_path: str) -> None:
        row = self.session.execute(
            text("SELECT report_json FROM research_reports WHERE id = :rid"),
            {"rid": report_id},
        ).fetchone()
        if row is None:
            return
        report_json = _decode_report_json(row[0])
        report_json["dossier_path"] = dossier_path
        self.session.execute(
            text(
                "UPDATE research_reports "
                "SET dossier_path = :dp, report_json = :rj WHERE id = :rid"
            ),
            {
                "dp": dossier_path,
                "rj": json.dumps(report_json, ensure_ascii=False),
                "rid": report_id,
            },
        )
        self.session.commit()


def _decode_report_json(value: object) -> dict[str, object]:
    if isinstance(value, str):
        value = json.loads(value)
    return dict(value) if isinstance(value, dict) else {}


def _embedded_dossier_path(report_json: dict[str, object]) -> str | None:
    value = report_json.get("dossier_path")
    return value if isinstance(value, str) and value else None
