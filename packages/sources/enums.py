from __future__ import annotations

from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 fallback

    class StrEnum(str, Enum):
        pass


class SourceCategory(StrEnum):
    USER_PROVIDED = "user_provided"
    REGULATORY_FILINGS = "regulatory_filings"
    MACRO_DATA = "macro_data"
    ENERGY_DATA = "energy_data"
    HEALTH_DATA = "health_data"
    POLICY_PORTAL = "policy_portal"
    EXCHANGE_ANNOUNCEMENT = "exchange_announcement"
    INDUSTRY_ASSOCIATION = "industry_association"


class QueryType(StrEnum):
    MACRO = "macro"
    ENERGY = "energy"
    FILING = "filing"
    HEALTH = "health"
    GENERAL = "general"


class AccessMethod(StrEnum):
    API = "api"
    FILE_UPLOAD = "file_upload"
    WEB = "web"
    MANUAL = "manual"


class TrustTier(StrEnum):
    PRIMARY_OFFICIAL = "primary_official"
    SECONDARY_INSTITUTIONAL = "secondary_institutional"
    USER_PROVIDED = "user_provided"


class EvidenceMode(StrEnum):
    RAW_DOCUMENT = "raw_document"
    NORMALIZED_DOCUMENT = "normalized_document"
    EXTRACTED_EVIDENCE = "extracted_evidence"


class CollectorType(StrEnum):
    HTML_LIST_DETAIL = "html_list_detail"
    PDF_FETCH = "pdf_fetch"
    PDF_TEXT_EXTRACT = "pdf_text_extract"


class PaginationMode(StrEnum):
    NONE = "none"
    PAGE_NUMBER = "page_number"
    LOAD_MORE = "load_more"
    NEXT_LINK = "next_link"
    CURSOR = "cursor"


class ChinaLocatorType(StrEnum):
    SECTION = "section"
    PAGE = "page"
    ATTACHMENT = "attachment"
    URL = "url"
    ANNOUNCEMENT_ID = "announcement_id"
    DOCUMENT_ID = "document_id"


class ToolStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"
    UNSUPPORTED = "unsupported"
    NOT_IMPLEMENTED = "not_implemented"


class ToolErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    SOURCE_NOT_FOUND = "source_not_found"
    SOURCE_DISABLED = "source_disabled"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    NOT_IMPLEMENTED = "not_implemented"
    INTERNAL_ERROR = "internal_error"
