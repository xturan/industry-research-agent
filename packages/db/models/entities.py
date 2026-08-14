from __future__ import annotations

from datetime import date, datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import Base
from packages.db.models.enums import (
    ContentStatus,
    ContentType,
    DeliveryItemStatus,
    DeliveryJobStatus,
    DeliveryMode,
    DeliveryReviewStatus,
    DeliveryTarget,
    DocumentStatus,
    EvalStatus,
    EvalType,
    MemoryType,
    RelationType,
    RunStatus,
    RunType,
    SourceType,
    StepStatus,
    TaskAttemptStatus,
    TaskJobStatus,
    TaskType,
    ThemeStatus,
    ThesisStance,
    ThesisStatus,
)


def enum_column(enum_cls: type[PyEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_source_type_published_at", "source_type", "published_at"),
        Index("ix_documents_published_at", "published_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        enum_column(SourceType, "source_type"), nullable=False, index=True
    )
    source_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    status: Mapped[DocumentStatus] = mapped_column(
        enum_column(DocumentStatus, "document_status"),
        nullable=False,
        default=DocumentStatus.NEW,
    )

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    citations: Mapped[list[Citation]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_id_chunk_index",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_json: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)

    document: Mapped[Document] = relationship(back_populates="chunks")
    citations: Mapped[list[Citation]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )
    thesis_links: Mapped[list[ThesisEvidenceLink]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )


class Citation(TimestampMixin, Base):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quote_text: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped[Document] = relationship(back_populates="citations")
    chunk: Mapped[DocumentChunk | None] = relationship(back_populates="citations")


class Theme(TimestampMixin, Base):
    __tablename__ = "themes"
    __table_args__ = (Index("ix_themes_slug", "slug"), Index("ix_themes_name", "name"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ThemeStatus] = mapped_column(
        enum_column(ThemeStatus, "theme_status"),
        nullable=False,
        default=ThemeStatus.ACTIVE,
    )

    events: Mapped[list[Event]] = relationship(back_populates="theme", cascade="all, delete-orphan")
    theses: Mapped[list[Thesis]] = relationship(
        back_populates="theme", cascade="all, delete-orphan"
    )
    content_assets: Mapped[list[ContentAsset]] = relationship(back_populates="theme")
    runs: Mapped[list[Run]] = relationship(back_populates="theme")


class Company(TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("ticker", "market", name="uq_companies_ticker_market"),
        Index("ix_companies_name", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(32), nullable=True)
    market: Mapped[str | None] = mapped_column(String(64), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Event(TimestampMixin, Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    theme_id: Mapped[int] = mapped_column(
        ForeignKey("themes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    theme: Mapped[Theme] = relationship(back_populates="events")


class Thesis(TimestampMixin, Base):
    __tablename__ = "theses"
    __table_args__ = (
        Index("ix_theses_theme_id_stance", "theme_id", "stance"),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="theses_confidence_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    theme_id: Mapped[int] = mapped_column(
        ForeignKey("themes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    stance: Mapped[ThesisStance] = mapped_column(
        enum_column(ThesisStance, "thesis_stance"),
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[ThesisStatus] = mapped_column(
        enum_column(ThesisStatus, "thesis_status"),
        nullable=False,
        default=ThesisStatus.DRAFT,
    )

    theme: Mapped[Theme] = relationship(back_populates="theses")
    evidence_links: Mapped[list[ThesisEvidenceLink]] = relationship(
        back_populates="thesis", cascade="all, delete-orphan"
    )
    risks: Mapped[list[ThesisRisk]] = relationship(
        back_populates="thesis", cascade="all, delete-orphan"
    )
    content_assets: Mapped[list[ContentAsset]] = relationship(back_populates="thesis")


class ThesisEvidenceLink(TimestampMixin, Base):
    __tablename__ = "thesis_evidence_links"
    __table_args__ = (
        UniqueConstraint(
            "thesis_id",
            "chunk_id",
            "relation_type",
            name="uq_thesis_evidence_links_thesis_chunk_relation",
        ),
        CheckConstraint(
            "weight IS NULL OR (weight >= 0.0 AND weight <= 1.0)",
            name="thesis_link_weight_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thesis_id: Mapped[int] = mapped_column(
        ForeignKey("theses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type: Mapped[RelationType] = mapped_column(
        enum_column(RelationType, "relation_type"),
        nullable=False,
    )
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    thesis: Mapped[Thesis] = relationship(back_populates="evidence_links")
    chunk: Mapped[DocumentChunk] = relationship(back_populates="thesis_links")


class ThesisRisk(TimestampMixin, Base):
    __tablename__ = "thesis_risks"
    __table_args__ = (
        CheckConstraint(
            "severity IS NULL OR (severity >= 1 AND severity <= 5)",
            name="thesis_risks_severity_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thesis_id: Mapped[int] = mapped_column(
        ForeignKey("theses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    risk_title: Mapped[str] = mapped_column(String(255), nullable=False)
    risk_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    thesis: Mapped[Thesis] = relationship(back_populates="risks")


class ContentAsset(TimestampMixin, Base):
    __tablename__ = "content_assets"
    __table_args__ = (Index("ix_content_assets_content_type_status", "content_type", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    theme_id: Mapped[int | None] = mapped_column(
        ForeignKey("themes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    thesis_id: Mapped[int | None] = mapped_column(
        ForeignKey("theses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    content_type: Mapped[ContentType] = mapped_column(
        enum_column(ContentType, "content_type"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ContentStatus] = mapped_column(
        enum_column(ContentStatus, "content_status"),
        nullable=False,
        default=ContentStatus.DRAFT,
    )
    body_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    theme: Mapped[Theme | None] = relationship(back_populates="content_assets")
    thesis: Mapped[Thesis | None] = relationship(back_populates="content_assets")
    feedback_events: Mapped[list[ContentFeedbackEvent]] = relationship(
        back_populates="content_asset",
        cascade="all, delete-orphan",
    )
    delivery_items: Mapped[list[DeliveryJobItem]] = relationship(back_populates="content_asset")


class ContentFeedbackEvent(TimestampMixin, Base):
    __tablename__ = "content_feedback_events"
    __table_args__ = (
        CheckConstraint("views >= 0", name="content_feedback_views_non_negative"),
        CheckConstraint("likes >= 0", name="content_feedback_likes_non_negative"),
        CheckConstraint("comments >= 0", name="content_feedback_comments_non_negative"),
        CheckConstraint("shares >= 0", name="content_feedback_shares_non_negative"),
        CheckConstraint("saves >= 0", name="content_feedback_saves_non_negative"),
        CheckConstraint("clicks >= 0", name="content_feedback_clicks_non_negative"),
        CheckConstraint(
            "conversions >= 0",
            name="content_feedback_conversions_non_negative",
        ),
        Index("ix_content_feedback_events_channel_captured_at", "channel", "captured_at"),
        Index(
            "ix_content_feedback_events_content_asset_id_captured_at",
            "content_asset_id",
            "captured_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_asset_id: Mapped[int] = mapped_column(
        ForeignKey("content_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    likes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shares: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    saves: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conversions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    content_asset: Mapped[ContentAsset] = relationship(back_populates="feedback_events")


class Run(TimestampMixin, Base):
    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_runs_status_started_at", "status", "started_at"),
        # G1.2 idempotent Run submission: exactly-one Run per (scope, key).
        UniqueConstraint("idempotency_scope", "idempotency_key", name="uq_runs_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[RunType] = mapped_column(enum_column(RunType, "run_type"), nullable=False)
    theme_id: Mapped[int | None] = mapped_column(
        ForeignKey("themes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[RunStatus] = mapped_column(
        enum_column(RunStatus, "run_status"),
        nullable=False,
        default=RunStatus.QUEUED,
    )
    input_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    output_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # G1.2 idempotency (scope is a stable "default" until a tenant/auth domain lands).
    idempotency_scope: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # G1.5 cooperative cancellation: set when a cancel is REQUESTED but the run is
    # still RUNNING; the worker observes it and stops at the next safe boundary.
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    theme: Mapped[Theme | None] = relationship(back_populates="runs")
    steps: Mapped[list[RunStep]] = relationship(back_populates="run", cascade="all, delete-orphan")
    events: Mapped[list[RunEvent]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    delivery_jobs: Mapped[list[DeliveryJob]] = relationship(back_populates="source_run")
    task_jobs: Mapped[list[TaskJob]] = relationship(back_populates="source_run")


class DeliveryJob(TimestampMixin, Base):
    __tablename__ = "delivery_jobs"
    __table_args__ = (
        Index("ix_delivery_jobs_status_created_at", "status", "created_at"),
        Index("ix_delivery_jobs_review_status", "review_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[DeliveryJobStatus] = mapped_column(
        enum_column(DeliveryJobStatus, "delivery_job_status"),
        nullable=False,
        default=DeliveryJobStatus.DRAFT,
    )
    delivery_target: Mapped[DeliveryTarget] = mapped_column(
        enum_column(DeliveryTarget, "delivery_target"),
        nullable=False,
    )
    review_status: Mapped[DeliveryReviewStatus] = mapped_column(
        enum_column(DeliveryReviewStatus, "delivery_review_status"),
        nullable=False,
        default=DeliveryReviewStatus.NOT_REQUIRED,
    )
    mode: Mapped[DeliveryMode] = mapped_column(
        enum_column(DeliveryMode, "delivery_mode"),
        nullable=False,
        default=DeliveryMode.MOCK,
    )
    requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source_run: Mapped[Run | None] = relationship(back_populates="delivery_jobs")
    items: Mapped[list[DeliveryJobItem]] = relationship(
        back_populates="delivery_job",
        cascade="all, delete-orphan",
    )


class DeliveryJobItem(TimestampMixin, Base):
    __tablename__ = "delivery_job_items"
    __table_args__ = (
        Index("ix_delivery_job_items_delivery_job_id_status", "delivery_job_id", "status"),
        Index("ix_delivery_job_items_content_asset_id", "content_asset_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delivery_job_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[DeliveryItemStatus] = mapped_column(
        enum_column(DeliveryItemStatus, "delivery_item_status"),
        nullable=False,
        default=DeliveryItemStatus.PENDING,
    )
    exported_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    dispatched_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    delivery_job: Mapped[DeliveryJob] = relationship(back_populates="items")
    content_asset: Mapped[ContentAsset | None] = relationship(back_populates="delivery_items")


class TaskJob(TimestampMixin, Base):
    __tablename__ = "task_jobs"
    __table_args__ = (
        UniqueConstraint(
            "task_type",
            "idempotency_key",
            name="uq_task_jobs_task_type_idempotency_key",
        ),
        CheckConstraint("attempt_count >= 0", name="task_jobs_attempt_count_non_negative"),
        CheckConstraint("max_attempts >= 1", name="task_jobs_max_attempts_positive"),
        Index("ix_task_jobs_status_available_at_priority", "status", "available_at", "priority"),
        Index("ix_task_jobs_task_type_status", "task_type", "status"),
        Index("ix_task_jobs_idempotency_key", "idempotency_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_type: Mapped[TaskType] = mapped_column(
        enum_column(TaskType, "task_type"),
        nullable=False,
    )
    status: Mapped[TaskJobStatus] = mapped_column(
        enum_column(TaskJobStatus, "task_job_status"),
        nullable=False,
        default=TaskJobStatus.QUEUED,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    # G3: fencing token——每次 claim +1；stale worker finalize 时用旧 generation 写 0 行。
    execution_generation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source_run: Mapped[Run | None] = relationship(back_populates="task_jobs")
    attempts: Mapped[list[TaskAttempt]] = relationship(
        back_populates="task_job",
        cascade="all, delete-orphan",
    )


class TaskAttempt(TimestampMixin, Base):
    __tablename__ = "task_attempts"
    __table_args__ = (
        UniqueConstraint(
            "task_job_id",
            "attempt_number",
            name="uq_task_attempts_task_job_id_attempt_number",
        ),
        Index("ix_task_attempts_task_job_id_started_at", "task_job_id", "started_at"),
        Index("ix_task_attempts_worker_id_started_at", "worker_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_job_id: Mapped[int] = mapped_column(
        ForeignKey("task_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[TaskAttemptStatus] = mapped_column(
        enum_column(TaskAttemptStatus, "task_attempt_status"),
        nullable=False,
        default=TaskAttemptStatus.RUNNING,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    task_job: Mapped[TaskJob] = relationship(back_populates="attempts")


class EvalRun(TimestampMixin, Base):
    __tablename__ = "eval_runs"
    __table_args__ = (
        Index("ix_eval_runs_eval_type_status_created_at", "eval_type", "status", "created_at"),
        Index("ix_eval_runs_target_type_target_ref", "target_type", "target_ref"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eval_type: Mapped[EvalType] = mapped_column(
        enum_column(EvalType, "eval_type"),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[EvalStatus] = mapped_column(
        enum_column(EvalStatus, "eval_status"),
        nullable=False,
        default=EvalStatus.RUNNING,
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list[EvalRunItem]] = relationship(
        back_populates="eval_run",
        cascade="all, delete-orphan",
    )


class EvalRunItem(TimestampMixin, Base):
    __tablename__ = "eval_run_items"
    __table_args__ = (Index("ix_eval_run_items_eval_run_id_passed", "eval_run_id", "passed"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eval_run_id: Mapped[int] = mapped_column(
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_name: Mapped[str] = mapped_column(String(128), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    eval_run: Mapped[EvalRun] = relationship(back_populates="items")


class RunStep(TimestampMixin, Base):
    __tablename__ = "run_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[StepStatus] = mapped_column(
        enum_column(StepStatus, "step_status"),
        nullable=False,
        default=StepStatus.PENDING,
    )
    input_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    output_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[Run] = relationship(back_populates="steps")


class RunEvent(TimestampMixin, Base):
    """G1.4 append-only timeline of a Research Run (NOT the source of truth for
    Run.status — Run.status remains authoritative)."""

    __tablename__ = "run_events"
    __table_args__ = (
        Index("ix_run_events_run_id_sequence", "run_id", "sequence"),
        UniqueConstraint("run_id", "sequence", name="uq_run_events_run_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    run: Mapped[Run] = relationship(back_populates="events")


class MemoryRecord(TimestampMixin, Base):
    __tablename__ = "memory_records"
    __table_args__ = (Index("ix_memory_records_memory_type_scope_key", "memory_type", "scope_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    memory_type: Mapped[MemoryType] = mapped_column(
        enum_column(MemoryType, "memory_type"),
        nullable=False,
    )
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # TODO: Switch to pgvector columns + ANN index when vector retrieval service is integrated.


# ── Graph v1 Research Records ──


class ResearchGraphCheckpoint(Base):
    __tablename__ = "research_graph_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    checkpoint_version: Mapped[int] = mapped_column(Integer, nullable=False)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    current_node: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResearchGraphSourceRecord(Base):
    __tablename__ = "research_graph_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    domain: Mapped[str | None] = mapped_column(String(256), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_tier: Mapped[str | None] = mapped_column(String(8), nullable=True)
    source_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    usage_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    search_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_by_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    search_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_text_meta_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    source_quality_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    payload_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class ResearchGraphEvidenceRecord(Base):
    __tablename__ = "research_graph_evidence_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    evidence_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    support_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    support_strength: Mapped[float | None] = mapped_column(Float, nullable=True)
    specificity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations_json: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    payload_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class ResearchGraphClaimRecord(Base):
    __tablename__ = "research_graph_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    supported: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_ids_json: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    required_source_family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    support_requirement: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class ResearchGraphClaimEvidenceLink(Base):
    __tablename__ = "research_graph_claim_evidence_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_id: Mapped[str] = mapped_column(String(128), nullable=False)
    link_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)


class ResearchGraphClaimVerificationRecord(Base):
    __tablename__ = "research_graph_claim_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False)
    support_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    support_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_ids_json: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    source_ids_json: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    notes_json: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    payload_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class ResearchGraphDraftVersionRecord(Base):
    __tablename__ = "research_graph_draft_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    draft_id: Mapped[str] = mapped_column(String(128), nullable=False)
    draft_version: Mapped[int] = mapped_column(Integer, nullable=False)
    report_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    sections_json: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    payload_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class ResearchGraphReviewIssueRecord(Base):
    __tablename__ = "research_graph_review_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    issue_id: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    issue_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_claim_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_search_queries_json: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    payload_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class ResearchGraphQualityGateResult(Base):
    __tablename__ = "research_graph_quality_gate_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    gate_id: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gate_route_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    route_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    gate_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_actions_json: Mapped[list[object] | None] = mapped_column(JSON, nullable=True)
    quality_scores_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    payload_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
