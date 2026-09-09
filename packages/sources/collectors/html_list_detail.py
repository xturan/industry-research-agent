from __future__ import annotations

import re
from datetime import datetime
from time import perf_counter
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from packages.sources.collectors.base import (
    BaseCollector,
    CollectorRequest,
    CollectorResponse,
    DetailPageContent,
    DiscoveredItem,
    PdfArtifact,
)
from packages.sources.collectors.normalize import (
    normalize_detail_page_to_documents,
    normalize_discovered_item_to_raw_document,
)
from packages.sources.enums import CollectorType, ToolStatus
from packages.sources.schemas import DocumentSection, NormalizedDocument


class HtmlListDetailCollector(BaseCollector):
    # TODO: Add browser fallback for JS-rendered pages in Step 4.2.
    # TODO: Add site-specific parser rules and deep pagination strategies later.
    @property
    def collector_type(self) -> CollectorType:
        return CollectorType.HTML_LIST_DETAIL

    def discover_items(self, request: CollectorRequest) -> CollectorResponse:
        started = perf_counter()
        html = request.raw_html or str(request.payload.get("html") or "")
        if not html.strip():
            return self.not_implemented(
                request,
                operation="discover_items",
                note=(
                    "Provide raw_html or payload['html']; live page fetching is "
                    "deferred to Step 4.2."
                ),
            )

        soup = BeautifulSoup(html, "html.parser")
        item_selector = request.profile.selectors.get("list_item") or "a[href]"
        item_nodes = soup.select(item_selector)
        items: list[DiscoveredItem] = []
        base_url = request.entry_url or (
            request.profile.entry_urls[0] if request.profile.entry_urls else ""
        )

        for index, node in enumerate(item_nodes):
            link_node = (
                node
                if getattr(node, "name", None) == "a" and node.get("href")
                else node.select_one(request.profile.selectors.get("list_item_link", "a[href]"))
            )
            script_link = None
            if link_node is None or not link_node.get("href"):
                script_link = self._extract_script_defined_link(node, request)
                if script_link is None:
                    continue
            title = (
                link_node.get_text(" ", strip=True)
                if link_node is not None and link_node.get("href")
                else script_link["title"]
            ) or node.get_text(" ", strip=True)
            if not title:
                continue
            published_at = self._parse_datetime(
                self._select_text(node, request.profile.selectors.get("list_item_date"))
                or (
                    link_node.get("data-published-at")
                    if link_node is not None and link_node.get("href")
                    else None
                )
                or node.get("data-published-at")
            )
            summary = self._select_text(node, request.profile.selectors.get("list_item_summary"))
            href = (
                str(link_node.get("href"))
                if link_node is not None and link_node.get("href")
                else script_link["href"]
            )
            script_item_id = script_link.get("item_id") if script_link is not None else None
            script_external_id = (
                script_link.get("external_id") if script_link is not None else None
            )
            items.append(
                DiscoveredItem(
                    item_id=(
                        node.get("data-id")
                        or (
                            link_node.get("data-id")
                            if link_node is not None and link_node.get("href")
                            else None
                        )
                        or script_item_id
                        or f"item_{index}"
                    ),
                    source_id=request.source_id,
                    title=title,
                    url=urljoin(base_url, href),
                    summary=summary,
                    published_at=published_at,
                    external_id=(
                        node.get("data-external-id")
                        or (
                            link_node.get("data-external-id")
                            if link_node is not None and link_node.get("href")
                            else None
                        )
                        or script_external_id
                    ),
                    list_position=index,
                    metadata={
                        "list_selector": item_selector,
                        "detail_required": request.profile.detail_required,
                        "script_defined_link": bool(script_link),
                    },
                )
            )

        status = ToolStatus.SUCCESS if items else ToolStatus.PARTIAL
        warnings = [] if items else ["No list items discovered from provided HTML."]
        return CollectorResponse(
            status=status,
            collector_name=self.collector_name,
            source_id=request.source_id,
            items=items,
            message=f"Discovered {len(items)} list item(s).",
            trace=self.build_trace(
                request=request,
                operation="discover_items",
                status=status,
                duration_ms=(perf_counter() - started) * 1000.0,
                page_count=1,
                item_count=len(items),
                warnings=warnings,
                metadata={"selector_used": item_selector},
            ),
        )

    def fetch_detail(self, request: CollectorRequest) -> CollectorResponse:
        started = perf_counter()
        if request.detail_page is not None:
            return CollectorResponse(
                status=ToolStatus.SUCCESS,
                collector_name=self.collector_name,
                source_id=request.source_id,
                detail_pages=[request.detail_page],
                message="Used provided detail_page payload.",
                trace=self.build_trace(
                    request=request,
                    operation="fetch_detail",
                    status=ToolStatus.SUCCESS,
                    duration_ms=(perf_counter() - started) * 1000.0,
                    item_count=1,
                ),
            )

        html = request.raw_html or str(
            request.payload.get("detail_html") or request.payload.get("html") or ""
        )
        if not html.strip():
            return self.not_implemented(
                request,
                operation="fetch_detail",
                note=(
                    "Provide raw_html or payload['detail_html']; network detail "
                    "fetching is deferred."
                ),
            )

        soup = BeautifulSoup(html, "html.parser")
        title = self._select_text(
            soup,
            request.profile.selectors.get("detail_title") or "h1, title",
        )
        if not title:
            title = request.item.title if request.item is not None else "Untitled detail page"
        content_text = self._select_text(
            soup,
            request.profile.selectors.get("detail_content")
            or "article, .article-content, .content, body",
            separator="\n",
        )
        published_at = self._parse_datetime(
            self._select_text(soup, request.profile.selectors.get("detail_published_at"))
        )
        detail_url = request.detail_url or (
            request.item.url if request.item is not None else request.entry_url
        )
        detail = DetailPageContent(
            item_id=request.item.item_id if request.item is not None else "detail_0",
            source_id=request.source_id,
            url=detail_url
            or (
                request.profile.entry_urls[0]
                if request.profile.entry_urls
                else "about:blank"
            ),
            title=title,
            published_at=published_at
            or (request.item.published_at if request.item is not None else None),
            html=html,
            text_content=content_text or title,
            summary=(content_text[:240] if content_text else None),
            sections=[
                DocumentSection(
                    section_id="main_content",
                    heading=title,
                    text=content_text or title,
                )
            ],
            metadata={
                "detail_required": request.profile.detail_required,
                "collector_type": self.collector_type.value,
            },
        )
        return CollectorResponse(
            status=ToolStatus.SUCCESS,
            collector_name=self.collector_name,
            source_id=request.source_id,
            detail_pages=[detail],
            message="Parsed detail page content.",
            trace=self.build_trace(
                request=request,
                operation="fetch_detail",
                status=ToolStatus.SUCCESS,
                duration_ms=(perf_counter() - started) * 1000.0,
                item_count=1,
            ),
        )

    def discover_attachments(self, request: CollectorRequest) -> CollectorResponse:
        started = perf_counter()
        if request.pdf_artifacts:
            return CollectorResponse(
                status=ToolStatus.SUCCESS,
                collector_name=self.collector_name,
                source_id=request.source_id,
                pdf_artifacts=request.pdf_artifacts,
                message="Used provided pdf_artifacts payload.",
                trace=self.build_trace(
                    request=request,
                    operation="discover_attachments",
                    status=ToolStatus.SUCCESS,
                    duration_ms=(perf_counter() - started) * 1000.0,
                    item_count=len(request.pdf_artifacts),
                ),
            )

        html = (
            request.detail_page.html
            if request.detail_page is not None and request.detail_page.html
            else request.raw_html
            or str(request.payload.get("detail_html") or request.payload.get("html") or "")
        )
        if not html.strip():
            return self.not_implemented(
                request,
                operation="discover_attachments",
                note="Provide detail HTML to discover attachment links.",
            )

        soup = BeautifulSoup(html, "html.parser")
        selector = request.profile.selectors.get("attachment_links") or "a[href]"
        base_url = (
            request.detail_url
            or (request.detail_page.url if request.detail_page is not None else None)
            or (request.item.url if request.item is not None else None)
            or request.entry_url
            or (request.profile.entry_urls[0] if request.profile.entry_urls else "")
        )
        artifacts: list[PdfArtifact] = []
        for index, node in enumerate(soup.select(selector)):
            href = str(node.get("href") or "")
            if ".pdf" not in href.lower():
                continue
            resolved_url = urljoin(base_url, href)
            parsed = urlparse(resolved_url)
            filename = parsed.path.split("/")[-1] or f"attachment_{index}.pdf"
            artifacts.append(
                PdfArtifact(
                    artifact_id=node.get("data-attachment-id") or f"pdf_{index}",
                    source_id=request.source_id,
                    item_id=request.item.item_id if request.item is not None else None,
                    url=resolved_url,
                    title=node.get_text(" ", strip=True) or filename,
                    filename=filename,
                    attachment_ref=filename,
                    metadata={"selector_used": selector},
                )
            )

        status = ToolStatus.SUCCESS if artifacts else ToolStatus.PARTIAL
        warnings = [] if artifacts else ["No PDF attachments discovered from detail HTML."]
        return CollectorResponse(
            status=status,
            collector_name=self.collector_name,
            source_id=request.source_id,
            pdf_artifacts=artifacts,
            message=f"Discovered {len(artifacts)} PDF attachment(s).",
            trace=self.build_trace(
                request=request,
                operation="discover_attachments",
                status=status,
                duration_ms=(perf_counter() - started) * 1000.0,
                item_count=len(artifacts),
                warnings=warnings,
                metadata={"selector_used": selector},
            ),
        )

    def normalize_to_documents(self, request: CollectorRequest) -> CollectorResponse:
        started = perf_counter()
        raw_documents = []
        normalized_documents = []
        publisher = str(request.profile.collector_config.get("publisher") or "").strip() or None

        if request.detail_page is not None:
            raw, normalized = normalize_detail_page_to_documents(
                request.detail_page,
                attachments=request.pdf_artifacts,
            )
            if publisher is not None:
                raw.publisher = publisher
                normalized.metadata = {**normalized.metadata, "publisher": publisher}
            raw_documents.append(raw)
            normalized_documents.append(normalized)
        elif request.item is not None:
            raw = normalize_discovered_item_to_raw_document(request.item, publisher=publisher)
            raw_documents.append(raw)
            normalized_documents.append(
                NormalizedDocument(
                    document_id=raw.document_id,
                    source_id=request.item.source_id,
                    title=request.item.title,
                    language=request.profile.language or "zh-CN",
                    published_at=request.item.published_at,
                    summary=request.item.summary,
                    sections=[
                        DocumentSection(
                            section_id="list_item_summary",
                            heading=request.item.title,
                            text=request.item.summary or request.item.title,
                        )
                    ],
                    metadata={
                        **raw.metadata,
                        **({"publisher": publisher} if publisher is not None else {}),
                    },
                )
            )
        else:
            return self.not_implemented(
                request,
                operation="normalize_to_documents",
                note="Provide item or detail_page before document normalization.",
            )

        return CollectorResponse(
            status=ToolStatus.SUCCESS,
            collector_name=self.collector_name,
            source_id=request.source_id,
            raw_documents=raw_documents,
            normalized_documents=normalized_documents,
            pdf_artifacts=request.pdf_artifacts,
            message="Normalized collector outputs into document contracts.",
            trace=self.build_trace(
                request=request,
                operation="normalize_to_documents",
                status=ToolStatus.SUCCESS,
                duration_ms=(perf_counter() - started) * 1000.0,
                item_count=len(normalized_documents),
            ),
        )

    def _select_text(self, node, selector: str | None, *, separator: str = " ") -> str | None:
        if selector is None:
            return None
        target = node.select_one(selector)
        if target is None:
            return None
        text = target.get_text(separator, strip=True)
        return text or None

    def _parse_datetime(self, raw_value: str | None) -> datetime | None:
        if raw_value is None:
            return None
        normalized = (
            raw_value.strip()
            .replace("/", "-")
            .replace("\u5e74", "-")
            .replace("\u6708", "-")
            .replace("\u65e5", "")
        )
        if not normalized:
            return None
        candidates = [normalized]
        if len(normalized) == 10:
            candidates.append(f"{normalized}T00:00:00")
        for candidate in candidates:
            try:
                return datetime.fromisoformat(candidate)
            except ValueError:
                continue
        return None

    def _extract_script_defined_link(
        self,
        node,
        request: CollectorRequest,
    ) -> dict[str, str] | None:
        parser_name = str(request.profile.collector_config.get("list_item_script_parser") or "")
        if parser_name != "szse_notice_v1":
            return None
        script_node = node.select_one("script")
        if script_node is None:
            return None
        script_text = script_node.get_text("\n", strip=True)
        href_match = re.search(r"var\s+curHref\s*=\s*'([^']+)'", script_text)
        title_match = re.search(r"var\s+curTitle\s*=\s*'([^']+)'", script_text)
        if href_match is None or title_match is None:
            return None
        href = href_match.group(1).strip()
        title = title_match.group(1).strip()
        if not href or not title:
            return None
        external_id = ""
        external_match = re.search(r"t(\d+)_([0-9]+)\.html", href)
        if external_match is not None:
            external_id = f"{external_match.group(1)}_{external_match.group(2)}"
        return {
            "href": href,
            "title": title,
            "item_id": external_id or href,
            "external_id": external_id or href,
        }
