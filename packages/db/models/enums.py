from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 fallback

    class StrEnum(str, Enum):
        pass


class SourceType(StrEnum):
    REPORT = "report"
    ARTICLE = "article"
    FILING = "filing"
    TRANSCRIPT = "transcript"
    DATASET = "dataset"
    OTHER = "other"


class DocumentStatus(StrEnum):
    NEW = "new"
    PARSED = "parsed"
    INDEXED = "indexed"
    ARCHIVED = "archived"
    FAILED = "failed"


class ThemeStatus(StrEnum):
    ACTIVE = "active"
    MONITORING = "monitoring"
    ARCHIVED = "archived"


class ThesisStance(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ThesisStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    INVALIDATED = "invalidated"
    ARCHIVED = "archived"


class RelationType(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    CONTEXTUAL = "contextual"


class ContentType(StrEnum):
    ARTICLE = "article"
    REPORT = "report"
    VIDEO_SCRIPT = "video_script"
    THREAD = "thread"


class ContentStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    FAILED = "failed"


class RunType(StrEnum):
    RESEARCH = "research"
    THESIS_BUILD = "thesis_build"
    CONTENT_GENERATE = "content_generate"
    MEMORY_REFRESH = "memory_refresh"
    DELIVERY_DISPATCH = "delivery_dispatch"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class MemoryType(StrEnum):
    THEME = "theme"
    CONTENT_STRATEGY = "content_strategy"
    USER_PREFERENCE = "user_preference"
    RUN_TRACE = "run_trace"


class DeliveryTarget(StrEnum):
    EXPORT_BUNDLE = "export_bundle"
    WEBHOOK = "webhook"
    MANUAL_REVIEW = "manual_review"
    MOCK_SOCIAL_CONNECTOR = "mock_social_connector"


class DeliveryMode(StrEnum):
    MOCK = "mock"
    DRY_RUN = "dry_run"


class DeliveryJobStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    READY = "ready"
    DISPATCHING = "dispatching"
    DISPATCHED = "dispatched"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryReviewStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DeliveryItemStatus(StrEnum):
    PENDING = "pending"
    EXPORTED = "exported"
    DISPATCHED = "dispatched"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskType(StrEnum):
    RESEARCH_ANALYZE = "research_analyze"
    CONTENT_GENERATE = "content_generate"
    DELIVERY_DISPATCH = "delivery_dispatch"


class TaskJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class TaskAttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    CANCELLED = "cancelled"


class EvalType(StrEnum):
    RAG_CHUNKS = "rag_chunks"
    EVIDENCE_BUNDLE = "evidence_bundle"
    RESEARCH_ANALYZE = "research_analyze"
    CONTENT_GENERATE = "content_generate"
    TASK_DELIVERY_FLOW = "task_delivery_flow"
    SMOKE = "smoke"


class EvalStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
