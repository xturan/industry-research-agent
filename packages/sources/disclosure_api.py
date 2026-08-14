from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any

import requests

from packages.sources.disclosure_mapping import (
    DisclosureAnnouncementSearchSpec,
    DisclosureEntityCandidate,
)
from packages.sources.enums import ToolErrorCode
from packages.sources.query_decomposition import QueryDecompositionTask
from packages.sources.schemas import (
    DocumentSection,
    NormalizedDocument,
    RawDocument,
    ToolError,
)

CNINFO_DISCLOSURE_QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_BASE_URL = "https://static.cninfo.com.cn"
CNINFO_TIMEZONE = timezone(timedelta(hours=8))


class CninfoDisclosureApiProvider:
    """Direct CNINFO announcement search for disclosure lanes."""

    def __init__(self, *, session: requests.Session | None = None, timeout_seconds: int = 20):
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def search(
        self,
        *,
        task: QueryDecompositionTask,
        spec: DisclosureAnnouncementSearchSpec,
        max_results: int,
    ) -> tuple[list[RawDocument], list[NormalizedDocument], list[ToolError], dict[str, Any]]:
        capped_max_results = max(1, min(max_results, 5))
        metadata: dict[str, Any] = {
            "attempted": True,
            "provider": "cninfo_direct_api",
            "status": "no_results",
            "query_count": 0,
            "document_count": 0,
            "normalized_document_count": 0,
            "skipped_weak_announcement_count": 0,
            "estimated_tavily_credits": 0,
        }
        documents: list[RawDocument] = []
        normalized_documents: list[NormalizedDocument] = []
        errors: list[ToolError] = []
        seen_urls: set[str] = set()

        for candidate in spec.entity_candidates[:3]:
            for query in _query_variants(candidate, spec):
                metadata["query_count"] += 1
                payload = _cninfo_payload(query, page_size=max(capped_max_results, 3))
                try:
                    response = self.session.post(
                        CNINFO_DISCLOSURE_QUERY_URL,
                        headers=_cninfo_headers(),
                        data=payload,
                        timeout=self.timeout_seconds,
                    )
                    response.raise_for_status()
                    data = response.json()
                except Exception as exc:  # noqa: BLE001
                    errors.append(
                        ToolError(
                            code=ToolErrorCode.INTERNAL_ERROR,
                            message=f"CNINFO disclosure API request failed: {exc}",
                            retryable=True,
                            detail={
                                "provider": "cninfo_direct_api",
                                "query": query,
                                "error_type": type(exc).__name__,
                            },
                        )
                    )
                    continue

                for announcement in data.get("announcements") or []:
                    if not _announcement_matches_candidate(announcement, candidate):
                        continue
                    if _is_weak_non_operating_announcement(announcement):
                        metadata["skipped_weak_announcement_count"] += 1
                        continue
                    raw_document = _announcement_to_raw_document(
                        announcement=announcement,
                        spec=spec,
                        task=task,
                        query=query,
                    )
                    if raw_document.source_uri in seen_urls:
                        continue
                    seen_urls.add(raw_document.source_uri)
                    normalized_document = _raw_to_normalized(raw_document)
                    documents.append(raw_document)
                    normalized_documents.append(normalized_document)
                    if len(documents) >= capped_max_results:
                        metadata.update(
                            {
                                "status": "evidence_found",
                                "document_count": len(documents),
                                "normalized_document_count": len(normalized_documents),
                            }
                        )
                        return documents, normalized_documents, errors, metadata

        if errors and not documents:
            metadata["status"] = "request_failed"
        metadata["document_count"] = len(documents)
        metadata["normalized_document_count"] = len(normalized_documents)
        return documents, normalized_documents, errors, metadata


def _cninfo_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0",
        "Referer": (
            "https://www.cninfo.com.cn/new/commonUrl/"
            "pageOfSearch?url=disclosure/list/search"
        ),
        "X-Requested-With": "XMLHttpRequest",
    }


def _cninfo_payload(query: str, *, page_size: int) -> dict[str, Any]:
    return {
        "pageNum": 1,
        "pageSize": page_size,
        "column": "",
        "tabName": "fulltext",
        "plate": "",
        "stock": "",
        "searchkey": query,
        "seDate": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }


def _query_variants(
    candidate: DisclosureEntityCandidate,
    spec: DisclosureAnnouncementSearchSpec,
) -> list[str]:
    variants: list[str] = []
    if spec.topic_keywords:
        variants.append(f"{candidate.name} {spec.topic_keywords[0]}")
    variants.append(f"{candidate.name} 年报")
    variants.append(candidate.name)
    return _dedupe(variants)


def _announcement_matches_candidate(
    announcement: dict[str, Any],
    candidate: DisclosureEntityCandidate,
) -> bool:
    sec_name = _clean_text(str(announcement.get("secName") or ""))
    sec_code = _clean_text(str(announcement.get("secCode") or ""))
    title = _clean_text(str(announcement.get("announcementTitle") or ""))
    ticker_root = str(candidate.ticker or "").split(".", 1)[0]
    haystack = f"{sec_name} {sec_code} {title}"
    return bool(
        (candidate.name and candidate.name in haystack)
        or (ticker_root and ticker_root in haystack)
    )


def _is_weak_non_operating_announcement(announcement: dict[str, Any]) -> bool:
    title = _clean_text(str(announcement.get("announcementTitle") or ""))
    if not title:
        return True
    weak_terms = (
        "法律意见书",
        "股票期权",
        "行权价格",
        "行权条件",
        "注销部分股票期权",
        "权益分派",
        "股东大会",
        "董事会决议",
        "监事会决议",
        "独立董事",
        "公司章程",
        "减持计划",
        "股份质押",
    )
    operating_terms = (
        "年度报告",
        "半年度报告",
        "季度报告",
        "项目",
        "投资",
        "合同",
        "订单",
        "中标",
        "合作协议",
        "经营",
        "业务",
        "产能",
        "建设",
        "收入",
        "进展",
        "风险提示",
        "投资者关系",
    )
    return any(term in title for term in weak_terms) and not any(
        term in title for term in operating_terms
    )


def _announcement_to_raw_document(
    *,
    announcement: dict[str, Any],
    spec: DisclosureAnnouncementSearchSpec,
    task: QueryDecompositionTask,
    query: str,
) -> RawDocument:
    title = _clean_text(str(announcement.get("announcementTitle") or "CNINFO announcement"))
    sec_name = _clean_text(str(announcement.get("secName") or ""))
    sec_code = _clean_text(str(announcement.get("secCode") or ""))
    published_at = _parse_cninfo_announcement_time(announcement.get("announcementTime"))
    published_at_label = published_at.date().isoformat() if published_at is not None else ""
    source_uri = _announcement_url(str(announcement.get("adjunctUrl") or ""))
    announcement_id = str(
        announcement.get("announcementId")
        or announcement.get("id")
        or hashlib.sha1(source_uri.encode("utf-8")).hexdigest()[:16]
    )
    document_id = f"cninfo_announcement_{announcement_id}"
    raw_text = " ".join(
        item
        for item in (
            sec_name,
            sec_code,
            title,
            published_at_label,
            " ".join(spec.topic_keywords),
            task.evidence_goal,
        )
        if item
    )
    return RawDocument(
        document_id=document_id,
        source_id="cn_exchange_cninfo_announcement_v1",
        title=f"{sec_name}: {title}" if sec_name else title,
        source_uri=source_uri,
        published_at=published_at,
        raw_text=raw_text,
        metadata={
            "provider": "cninfo_direct_api",
            "source_class": "company_disclosure",
            "sec_name": sec_name,
            "sec_code": sec_code,
            "announcement_id": announcement_id,
            "published_at_label": published_at_label,
            "discovery_query": query,
            "disclosure_search_spec": spec.to_dict(),
        },
    )


def _raw_to_normalized(raw_document: RawDocument) -> NormalizedDocument:
    section_id = f"{raw_document.document_id}_sec_1"
    return NormalizedDocument(
        document_id=raw_document.document_id,
        source_id=raw_document.source_id,
        title=raw_document.title,
        summary=raw_document.raw_text,
        published_at=raw_document.published_at,
        sections=[
            DocumentSection(
                section_id=section_id,
                heading=raw_document.title,
                text=raw_document.raw_text or "",
                metadata={
                    "provider": "cninfo_direct_api",
                    "requested_url": raw_document.source_uri,
                    "final_url": raw_document.source_uri,
                },
            )
        ],
        metadata={
            **raw_document.metadata,
            "requested_url": raw_document.source_uri,
            "final_url": raw_document.source_uri,
        },
    )


def _announcement_url(adjunct_url: str) -> str:
    if adjunct_url.startswith(("http://", "https://")):
        return adjunct_url
    return f"{CNINFO_STATIC_BASE_URL}/{adjunct_url.lstrip('/')}"


def _clean_text(value: str) -> str:
    return re.sub(r"<[^>]+>", "", unescape(value)).strip()


def _parse_cninfo_announcement_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000, tz=CNINFO_TIMEZONE)
    text = _clean_text(str(value))
    if not text:
        return None
    if text.isdigit():
        timestamp = int(text)
        if timestamp > 10_000_000_000:
            return datetime.fromtimestamp(timestamp / 1000, tz=CNINFO_TIMEZONE)
        return datetime.fromtimestamp(timestamp, tz=CNINFO_TIMEZONE)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = " ".join(value.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
