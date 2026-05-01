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
    PROJECT_SIGNAL = "project_signal"


class QueryType(StrEnum):
    MACRO = "macro"
    ENERGY = "energy"
    FILING = "filing"
    HEALTH = "health"
    GENERAL = "general"


class GovernanceAxis(StrEnum):
    LINE = "line"
    BLOCK = "block"
    MIXED = "mixed"


class LineFamily(StrEnum):
    POLICY = "policy"
    EXCHANGE = "exchange"
    INDUSTRY = "industry"
    CROSS_DOMAIN = "cross_domain"


class RegionalLevel(StrEnum):
    NATIONAL = "national"
    PROVINCIAL = "provincial"
    MUNICIPAL = "municipal"
    CROSS_REGION = "cross_region"


class InfoType(StrEnum):
    POLICY_NOTICE = "policy_notice"
    REGULATORY_ANNOUNCEMENT = "regulatory_announcement"
    INDUSTRY_REPORT = "industry_report"
    INDUSTRY_NOTICE = "industry_notice"
    PROJECT_TRANSACTION = "project_transaction"


class PublisherType(StrEnum):
    MINISTRY = "ministry"
    EXCHANGE = "exchange"
    ASSOCIATION = "association"
    INSTITUTION = "institution"
    MIXED = "mixed"


class SourceRole(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUPPLEMENTAL = "supplemental"


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
