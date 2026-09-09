from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

try:
    from crawl4ai import (
        AsyncWebCrawler,
        BrowserConfig,
        CacheMode,
        CrawlerRunConfig,
        DefaultTableExtraction,
        JsonCssExtractionStrategy,
    )
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise SystemExit(
        "Missing dependency: crawl4ai\n"
        "Install it first:\n"
        "  pip install crawl4ai\n"
        "  playwright install\n"
        f"\nOriginal import error: {exc}"
    ) from exc


DEFAULT_URL = "https://www.ichuanghui.org/4925.html"
DEFAULT_JSON_OUTPUT = Path("data/tmp/ichuanghui_4925.json")
ARTICLE_SCHEMA = {
    "name": "IchuanghuiArticle",
    "baseSelector": "article.post",
    "fields": [
        {"name": "title", "selector": "h1.entry-title", "type": "text"},
        {"name": "published_at_text", "selector": "span.entry-date", "type": "text"},
        {"name": "views_text", "selector": "span.entry-views", "type": "text"},
        {"name": "meta_text", "selector": "div.entry-meta", "type": "text"},
        {"name": "content_html", "selector": "div.entry-content", "type": "html"},
    ],
}
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
HEADING_PATTERNS = [
    (re.compile(r"^[一二三四五六七八九十]+、"), 2),
    (re.compile(r"^（[一二三四五六七八九十]+）"), 3),
    (re.compile(r"^\d+[.、]"), 4),
]


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(str(text).split())


def safe_json_loads(raw: str | None) -> object:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def parse_crawl4ai_extracted_article(result: object) -> dict[str, object]:
    extracted = safe_json_loads(getattr(result, "extracted_content", None))
    if isinstance(extracted, list) and extracted:
        first = extracted[0]
        if isinstance(first, dict):
            return first
    if isinstance(extracted, dict):
        return extracted
    return {}


def parse_html_table(table_node, table_index: int) -> dict[str, object]:
    rows: list[list[str]] = []
    for row in table_node.select("tr"):
        cells = [
            normalize_text(cell.get_text(" ", strip=True))
            for cell in row.select("th, td")
        ]
        if any(cells):
            rows.append(cells)

    headers: list[str] = []
    body_rows: list[list[str]] = []
    if rows:
        headers = rows[0]
        body_rows = rows[1:]

    return {
        "table_index": table_index,
        "headers": headers,
        "rows": body_rows,
        "row_count": len(rows),
        "html": str(table_node),
    }


def classify_heading_level(text: str) -> int | None:
    for pattern, level in HEADING_PATTERNS:
        if pattern.match(text):
            return level
    return None


def extract_content_blocks(
    content_node,
) -> tuple[list[dict[str, object]], list[str], list[dict[str, object]]]:
    blocks: list[dict[str, object]] = []
    paragraphs: list[str] = []
    tables: list[dict[str, object]] = []
    table_index = 0

    for child in content_node.children:
        tag_name = getattr(child, "name", None)
        if tag_name is None:
            continue

        if tag_name == "p":
            text = normalize_text(child.get_text(" ", strip=True))
            if not text:
                continue
            paragraphs.append(text)
            heading_level = classify_heading_level(text)
            blocks.append(
                {
                    "type": "heading" if heading_level is not None else "paragraph",
                    "text": text,
                    "level": heading_level,
                }
            )
            continue

        if tag_name == "table":
            table_index += 1
            table_payload = parse_html_table(child, table_index)
            tables.append(table_payload)
            blocks.append(
                {
                    "type": "table",
                    "table_index": table_index,
                    "headers": table_payload["headers"],
                    "rows": table_payload["rows"],
                }
            )
            continue

        nested_paragraphs = child.select("p") if hasattr(child, "select") else []
        if nested_paragraphs:
            for paragraph in nested_paragraphs:
                text = normalize_text(paragraph.get_text(" ", strip=True))
                if not text:
                    continue
                paragraphs.append(text)
                heading_level = classify_heading_level(text)
                blocks.append(
                    {
                        "type": "heading" if heading_level is not None else "paragraph",
                        "text": text,
                        "level": heading_level,
                    }
                )

    return blocks, paragraphs, tables


def extract_article_payload(page_url: str, html: str) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article.post")
    root = article or soup

    title_node = root.select_one("h1.entry-title")
    entry_date_node = root.select_one("span.entry-date") or root.select_one("time")
    views_node = root.select_one("span.view-count")
    meta_node = root.select_one("div.entry-meta")
    content_node = root.select_one("div.entry-content")

    paragraphs: list[str] = []
    attachment_links: list[dict[str, str]] = []
    inline_links: list[dict[str, str]] = []
    content_blocks: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []

    if content_node is not None:
        content_blocks, paragraphs, tables = extract_content_blocks(content_node)

        for anchor in content_node.select("a[href]"):
            href = anchor.get("href", "").strip()
            if not href:
                continue
            absolute_href = urljoin(page_url, href)
            anchor_text = " ".join(anchor.get_text(" ", strip=True).split())
            link_payload = {"text": anchor_text, "href": absolute_href}
            inline_links.append(link_payload)
            if absolute_href.lower().endswith(".pdf"):
                attachment_links.append(link_payload)

    if not paragraphs and content_node is not None:
        merged_text = " ".join(content_node.get_text("\n", strip=True).split())
        if merged_text:
            paragraphs.append(merged_text)

    breadcrumbs = [
        " ".join(node.get_text(" ", strip=True).split())
        for node in soup.select(".breadcrumbs a, nav.breadcrumbs a")
        if node.get_text(strip=True)
    ]

    return {
        "url": page_url,
        "title": title_node.get_text(strip=True) if title_node else None,
        "published_at_text": (
            entry_date_node.get_text(" ", strip=True) if entry_date_node else None
        ),
        "views_text": views_node.get_text(" ", strip=True) if views_node else None,
        "meta_text": meta_node.get_text(" ", strip=True) if meta_node else None,
        "breadcrumbs": breadcrumbs,
        "paragraph_count": len(paragraphs),
        "paragraphs": paragraphs,
        "content_blocks": content_blocks,
        "content_text": "\n\n".join(paragraphs),
        "tables": tables,
        "table_count": len(tables),
        "attachment_links": attachment_links,
        "inline_links": inline_links,
    }


def is_meaningful_payload(payload: dict[str, object]) -> bool:
    title = payload.get("title")
    paragraph_count = payload.get("paragraph_count") or 0
    content_text = payload.get("content_text") or ""
    return bool(title) and int(paragraph_count) > 0 and len(str(content_text).strip()) > 80


def is_meaningful_markdown(markdown_text: str | None) -> bool:
    if not isinstance(markdown_text, str):
        return False
    normalized = markdown_text.strip()
    if not normalized:
        return False
    if normalized == "# Untitled":
        return False
    if len(normalized) < 80:
        return False
    return True


def build_markdown_from_payload(payload: dict[str, object]) -> str:
    title = payload.get("title") or "Untitled"
    published_at_text = payload.get("published_at_text") or ""
    views_text = payload.get("views_text") or ""
    url = payload.get("url") or ""
    content_blocks = payload.get("content_blocks") or []
    attachment_links = payload.get("attachment_links") or []

    lines = [f"# {title}"]
    if url:
        lines.extend(["", f"- URL: {url}"])
    if published_at_text:
        lines.append(f"- Published: {published_at_text}")
    if views_text:
        lines.append(f"- Views: {views_text}")

    if content_blocks:
        lines.extend(["", "## 正文", ""])
        for index, block in enumerate(content_blocks):
            block_type = block.get("type")
            if block_type == "heading":
                level = int(block.get("level") or 3)
                lines.append(f"{'#' * max(2, min(level, 6))} {block.get('text', '')}")
                lines.append("")
                continue

            if block_type == "paragraph":
                text = str(block.get("text") or "").strip()
                if text:
                    lines.append(text)
                    lines.append("")
                continue

            if block_type == "table":
                table_title = f"表 {block.get('table_index', index + 1)}"
                prev_block = content_blocks[index - 1] if index > 0 else None
                if isinstance(prev_block, dict):
                    prev_text = str(prev_block.get("text") or "").strip()
                    if prev_text and len(prev_text) <= 40 and "表" in prev_text:
                        table_title = prev_text
                lines.append(f"### {table_title}")
                lines.append("")
                lines.extend(render_markdown_table(block))
                lines.append("")

    if attachment_links:
        lines.append("## Attachments")
        lines.append("")
        for link in attachment_links:
            lines.append(f"- [{link['text'] or link['href']}]({link['href']})")

    return "\n".join(lines).strip()


def render_markdown_table(block: dict[str, object]) -> list[str]:
    headers = [escape_md_cell(str(item)) for item in (block.get("headers") or [])]
    rows = [
        [escape_md_cell(str(cell)) for cell in row]
        for row in (block.get("rows") or [])
    ]
    if not headers and not rows:
        return ["_Empty table_"]

    if not headers and rows:
        headers = [f"Column {index + 1}" for index in range(len(rows[0]))]

    column_count = max(
        len(headers),
        max((len(row) for row in rows), default=0),
    )
    headers = headers + [""] * (column_count - len(headers))
    normalized_rows = [row + [""] * (column_count - len(row)) for row in rows]

    table_lines = [
        f"| {' | '.join(headers)} |",
        f"| {' | '.join(['---'] * column_count)} |",
    ]
    for row in normalized_rows:
        table_lines.append(f"| {' | '.join(row)} |")
    return table_lines


def escape_md_cell(value: str) -> str:
    return normalize_text(value).replace("|", "\\|").replace("\n", "<br>")


def derive_markdown(result: object, payload: dict[str, object]) -> str:
    markdown_obj = getattr(result, "markdown", None)
    if markdown_obj is not None:
        raw_markdown = getattr(markdown_obj, "raw_markdown", None)
        if is_meaningful_markdown(raw_markdown):
            return raw_markdown.strip()
        fit_markdown = getattr(markdown_obj, "fit_markdown", None)
        if is_meaningful_markdown(fit_markdown):
            return fit_markdown.strip()
        if is_meaningful_markdown(markdown_obj):
            return markdown_obj.strip()

    return build_markdown_from_payload(payload)


def fetch_html_fallback(url: str) -> str:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


async def crawl_article(url: str) -> tuple[dict[str, object], str]:
    browser_config = BrowserConfig(headless=True, verbose=False)
    markdown_generator = DefaultMarkdownGenerator(
        content_source="raw_html",
        content_filter=PruningContentFilter(
            threshold=0.35,
            threshold_type="dynamic",
            min_word_threshold=3,
        ),
        options={
            "ignore_images": True,
            "ignore_links": False,
            "body_width": 0,
            "escape_html": False,
            "skip_internal_links": False,
        },
    )
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=1,
        css_selector="article.post",
        wait_for="css:article.post",
        page_timeout=60000,
        remove_overlay_elements=True,
        exclude_external_images=True,
        excluded_tags=["script", "style", "noscript", "iframe"],
        markdown_generator=markdown_generator,
        extraction_strategy=JsonCssExtractionStrategy(ARTICLE_SCHEMA, verbose=False),
        table_extraction=DefaultTableExtraction(
            table_score_threshold=4,
            min_rows=2,
            min_cols=2,
            verbose=False,
        ),
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)

    if not getattr(result, "success", False):
        raise RuntimeError(
            "Crawl4AI crawl failed: "
            f"status_code={getattr(result, 'status_code', None)} "
            f"error={getattr(result, 'error_message', None)}"
        )

    html = getattr(result, "cleaned_html", None) or getattr(result, "html", None)
    if not html:
        raise RuntimeError("Crawl4AI succeeded but returned no html/cleaned_html content.")

    payload = extract_article_payload(url, html)
    extracted_article = parse_crawl4ai_extracted_article(result)
    if extracted_article.get("title"):
        payload["title"] = extracted_article.get("title")
    if extracted_article.get("published_at_text"):
        payload["published_at_text"] = extracted_article.get("published_at_text")
    if extracted_article.get("views_text"):
        payload["views_text"] = extracted_article.get("views_text")
    if extracted_article.get("meta_text"):
        payload["meta_text"] = extracted_article.get("meta_text")
    content_html = extracted_article.get("content_html")
    if isinstance(content_html, str) and content_html.strip():
        extracted_content_payload = extract_article_payload(
            url,
            f"<article class='post'><div class='entry-content'>{content_html}</div></article>",
        )
        if extracted_content_payload.get("paragraph_count", 0):
            payload["content_blocks"] = extracted_content_payload["content_blocks"]
            payload["paragraph_count"] = extracted_content_payload["paragraph_count"]
            payload["paragraphs"] = extracted_content_payload["paragraphs"]
            payload["content_text"] = extracted_content_payload["content_text"]
            payload["tables"] = extracted_content_payload["tables"]
            payload["table_count"] = extracted_content_payload["table_count"]

    crawl4ai_tables = getattr(result, "tables", None)
    if isinstance(crawl4ai_tables, list) and crawl4ai_tables:
        payload["crawl4ai_tables"] = crawl4ai_tables

    extraction_path = "crawl4ai"
    if not is_meaningful_payload(payload):
        fallback_html = fetch_html_fallback(url)
        fallback_payload = extract_article_payload(url, fallback_html)
        if is_meaningful_payload(fallback_payload):
            payload = fallback_payload
            extraction_path = "requests_fallback"

    markdown_text = derive_markdown(result, payload)
    payload["crawl4ai_meta"] = {
        "success": bool(getattr(result, "success", False)),
        "status_code": getattr(result, "status_code", None),
        "cleaned_html_length": len(getattr(result, "cleaned_html", "") or ""),
        "html_length": len(getattr(result, "html", "") or ""),
        "raw_markdown_length": len(
            getattr(getattr(result, "markdown", None), "raw_markdown", "") or ""
        ),
        "fit_markdown_length": len(
            getattr(getattr(result, "markdown", None), "fit_markdown", "") or ""
        ),
        "markdown_length": len(markdown_text),
        "result_table_count": len(crawl4ai_tables) if isinstance(crawl4ai_tables, list) else 0,
        "extraction_path": extraction_path,
        "payload_meaningful": is_meaningful_payload(payload),
    }
    return payload, markdown_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl one ichuanghui article with Crawl4AI and export JSON + Markdown."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Target article URL.")
    parser.add_argument(
        "--output-json",
        default=str(DEFAULT_JSON_OUTPUT),
        help="JSON output path. Default: data/tmp/ichuanghui_4925.json",
    )
    parser.add_argument(
        "--output-md",
        default=None,
        help="Markdown output path. Default: same stem as JSON output with .md extension.",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    json_output_path = Path(args.output_json)
    md_output_path = (
        Path(args.output_md)
        if args.output_md is not None
        else json_output_path.with_suffix(".md")
    )

    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    md_output_path.parent.mkdir(parents=True, exist_ok=True)

    payload, markdown_text = asyncio.run(crawl_article(args.url))
    json_output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_output_path.write_text(markdown_text, encoding="utf-8")

    print(f"crawl complete: {args.url}")
    print(f"json output: {json_output_path}")
    print(f"markdown output: {md_output_path}")
    print(f"title: {payload.get('title')}")
    print(f"published_at: {payload.get('published_at_text')}")
    print(f"paragraph_count: {payload.get('paragraph_count')}")
    print(f"attachment_count: {len(payload.get('attachment_links', []))}")


if __name__ == "__main__":
    main()
