"""
Source Tier 数据集加工脚本 — 从 URL 候选池抓取详情页并生成高质量训练数据。

Phase 1: rule_direct 样本 → 规则特征提取（无需爬虫）
Phase 2: llm_needed / rule_conflict 样本 → crawl4ai 抓取 + 语义分析
Phase 3: 生成 CoT 推理链 + 输出 enriched dataset

Usage:
    python -m packages.training.enrich_candidate_pool [--max-crawl 200] [--batch-size 5]
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DATA_DIR = Path(__file__).parent / "data"
POOL_FILE = DATA_DIR / "source_tier_unified_candidate_pool_dedup_v1.jsonl"
OUTPUT_FILE = DATA_DIR / "source_tier_training_dataset_enriched.jsonl"

# ── Rule-based feature extraction (Phase 1: no crawling needed) ──

POLICY_PATH_MARKERS = (
    "/zcfb/", "/xxgk/", "/zfxxgk/", "/flfg/", "/gkmlpt/",
    "/content/post_", "/public/", "/tzgg/", "/zwgk/wjk/",
)
NEWS_PATH_MARKERS = (
    "/xwdt/", "/xwzx/", "/zwdt/", "/mtjj/", "/xwfb/",
    "/xinwen/", "/news/", "/mtbd/",
)
INTERPRET_PATH_MARKERS = ("/jdhy/", "/zcjd/", "/jiedu/")
POLICY_TITLE_KEYWORDS = (
    "办法", "措施", "行动计划", "实施细则", "通知", "意见", "方案",
    "规定", "条例", "规划纲要", "指导意见", "若干措施", "管理办法",
)
NEWS_TITLE_KEYWORDS = ("召开", "座谈", "调研", "考察", "会见", "主持", "出席")
INTERPRET_TITLE_KEYWORDS = ("解读", "答记者问", "一图读懂", "图解")
CENTRAL_MINISTRIES = frozenset({
    "www.gov.cn", "ndrc.gov.cn", "www.ndrc.gov.cn",
    "miit.gov.cn", "www.miit.gov.cn", "most.gov.cn", "www.most.gov.cn",
    "mofcom.gov.cn", "www.mofcom.gov.cn", "stats.gov.cn", "www.stats.gov.cn",
    "customs.gov.cn", "www.customs.gov.cn", "mof.gov.cn", "www.mof.gov.cn",
    "mee.gov.cn", "www.mee.gov.cn", "mohurd.gov.cn", "www.mohurd.gov.cn",
    "samr.gov.cn", "www.samr.gov.cn", "nea.gov.cn", "www.nea.gov.cn",
})
PROCUREMENT_MARKERS = ("ggzy", "ccgp", "ggzyjy", "zfcg")
EXCHANGE_DOMAINS = frozenset({"cninfo.com.cn", "sse.com.cn", "szse.cn"})
COMMERCIAL_MEDIA = frozenset({
    "sohu.com", "sina.com.cn", "163.com", "qq.com", "ifeng.com",
    "yicai.com", "caixin.com", "thepaper.cn", "jiemian.com",
    "36kr.com", "huxiu.com", "cls.cn", "eastmoney.com",
})
SELF_MEDIA = frozenset({
    "zhihu.com", "baidu.com", "toutiao.com", "mp.weixin.qq.com",
})

def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""

def classify_route(record: dict) -> str:
    """Determine route_type from domain/URL/title without crawling."""
    info = record.get("url_info", {})
    domain = info.get("domain", "")
    url = info.get("url", "")
    title = info.get("title", "") or ""

    # Tier-specific rules
    if domain in CENTRAL_MINISTRIES:
        return "rule_direct"
    if domain.endswith(".gov.cn") and url.lower().endswith(".pdf"):
        return "rule_direct"
    if any(m in domain for m in PROCUREMENT_MARKERS):
        return "rule_direct"
    if domain in EXCHANGE_DOMAINS:
        return "rule_direct"
    if domain in COMMERCIAL_MEDIA or domain in SELF_MEDIA:
        return "rule_direct"

    # .gov.cn with clear markers → rule_direct
    if domain.endswith(".gov.cn"):
        url_lower = url.lower()
        if any(m in url_lower for m in POLICY_PATH_MARKERS):
            return "rule_direct"
        if any(kw in title for kw in POLICY_TITLE_KEYWORDS):
            return "rule_direct"
        if any(m in url_lower for m in NEWS_PATH_MARKERS):
            return "rule_direct"

    # Ambiguous or needs content → llm_needed
    return "llm_needed"


def extract_rule_features(record: dict) -> dict:
    """Extract semantic features using rules only (no crawling)."""
    info = record.get("url_info", {})
    domain = info.get("domain", "")
    url = info.get("url", "")
    title = info.get("title", "") or ""
    url_lower = url.lower()
    label = record.get("label", {})
    tier = label.get("tier", "?")

    features = {
        "authority_type": "government" if domain.endswith(".gov.cn") else "unknown",
        "document_type": None,
        "source_relation": "original",
        "is_policy_original": False,
        "is_policy_interpretation": False,
        "is_government_news": False,
        "is_professional_report": False,
        "is_enterprise_disclosure": False,
        "is_commercial_media": False,
        "is_repost": False,
        "is_outdated": False,
        "evidence_sentences": [],
    }

    # Year check
    years = re.findall(r"(20[0-2]\d)", url + title)
    if years and max(int(y) for y in years) < 2020:
        features["is_outdated"] = True

    if domain in COMMERCIAL_MEDIA or domain in SELF_MEDIA:
        features["is_commercial_media"] = True
        features["authority_type"] = "commercial_media"

    if domain.endswith(".gov.cn"):
        features["authority_type"] = "government"
        if url_lower.endswith(".pdf"):
            features["is_policy_original"] = True
            features["document_type"] = "policy_pdf"
        elif any(m in url_lower for m in POLICY_PATH_MARKERS):
            features["is_policy_original"] = True
            features["document_type"] = "policy_page"
        elif any(kw in title for kw in POLICY_TITLE_KEYWORDS):
            features["is_policy_original"] = True
            features["document_type"] = "policy_page"
        elif any(m in url_lower for m in NEWS_PATH_MARKERS):
            features["is_government_news"] = True
            features["document_type"] = "gov_news"
        elif any(kw in title for kw in NEWS_TITLE_KEYWORDS):
            features["is_government_news"] = True
            features["document_type"] = "gov_news"
        elif any(m in url_lower for m in INTERPRET_PATH_MARKERS):
            features["is_policy_interpretation"] = True
            features["document_type"] = "policy_interpretation"
        elif any(kw in title for kw in INTERPRET_TITLE_KEYWORDS):
            features["is_policy_interpretation"] = True
            features["document_type"] = "policy_interpretation"

    if any(m in domain for m in PROCUREMENT_MARKERS):
        features["is_enterprise_disclosure"] = True
        features["document_type"] = "procurement"
    if domain in EXCHANGE_DOMAINS:
        features["is_enterprise_disclosure"] = True
        features["document_type"] = "enterprise_disclosure"

    # Org domains
    if domain.endswith(".org") or domain.endswith(".org.cn"):
        features["is_professional_report"] = True
        features["authority_type"] = "industry_association"

    return features


def generate_cot_reasoning(record: dict, features: dict) -> str:
    """Generate Chain-of-Thought reasoning for this sample."""
    info = record.get("url_info", {})
    domain = info.get("domain", "")
    url = info.get("url", "")
    title = info.get("title", "") or ""
    tier = record.get("label", {}).get("tier", "?")
    url_lower = url.lower()

    steps = []

    # Step 1: Domain analysis
    if domain in CENTRAL_MINISTRIES:
        steps.append(f"域名 {domain} 属于中央部委，最高权威")
    elif domain.endswith(".gov.cn"):
        steps.append(f"域名 {domain} 以 .gov.cn 结尾，属于政府网站")
    elif domain.endswith(".org") or domain.endswith(".org.cn"):
        steps.append(f"域名 {domain} 是 .org/.org.cn，属于行业协会或非营利组织")
    elif domain in COMMERCIAL_MEDIA:
        steps.append(f"域名 {domain} 是商业新闻媒体")
    elif domain in SELF_MEDIA:
        steps.append(f"域名 {domain} 是自媒体/聚合平台")
    else:
        steps.append(f"域名 {domain} 不在已知权威清单中")

    # Step 2: URL path analysis
    path = urlparse(url).path.lower()
    if any(m in url_lower for m in POLICY_PATH_MARKERS):
        steps.append(f"URL路径包含政策发布标记")
    elif any(m in url_lower for m in NEWS_PATH_MARKERS):
        steps.append(f"URL路径包含新闻动态标记")
    elif any(m in url_lower for m in INTERPRET_PATH_MARKERS):
        steps.append(f"URL路径包含政策解读标记")
    elif url_lower.endswith(".pdf"):
        steps.append("URL 是 PDF 文件")

    # Step 3: Title analysis
    if any(kw in title for kw in POLICY_TITLE_KEYWORDS):
        steps.append(f"标题含政策关键词，表明是正式文件")
    elif any(kw in title for kw in NEWS_TITLE_KEYWORDS):
        steps.append(f"标题含新闻类动词，表明是动态报道")
    elif any(kw in title for kw in INTERPRET_TITLE_KEYWORDS):
        steps.append(f"标题含解读标记，表明是政策解读")

    # Step 4: Year check
    years = re.findall(r"(20[0-2]\d)", url + title)
    if years:
        latest = max(int(y) for y in years)
        if latest < 2020:
            steps.append(f"年份 {latest} < 2020，严重过时")
        elif latest < 2023:
            steps.append(f"年份 {latest}，时效性一般")

    # Step 5: Conclusion
    tier_names = {"A": "政策法规原文", "B": "官方新闻/公告", "C": "专业报告/解读", "D": "商业媒体/低可信度"}
    steps.append(f"结论: 综合判断为 {tier} 级({tier_names.get(tier, '未知')})")

    return "\n".join(f"Step {i+1}: {s}" for i, s in enumerate(steps))


# ── Crawl4ai page fetching (Phase 2: actual crawling) ──

async def crawl_page(url: str, timeout_ms: int = 30000) -> dict | None:
    """Crawl a single page and extract structured content. Returns None on failure."""
    try:
        from crawl4ai import (
            AsyncWebCrawler, CrawlerRunConfig, CacheMode,
            PruningContentFilter, DefaultMarkdownGenerator,
        )

        # Use PruningContentFilter to remove nav/header/footer noise
        prune_filter = PruningContentFilter(
            threshold=0.45,
            threshold_type="fixed",
            min_word_threshold=10,
        )
        md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)

        config = CrawlerRunConfig(
            page_timeout=timeout_ms,
            cache_mode=CacheMode.BYPASS,
            scan_full_page=False,
            markdown_generator=md_generator,
            exclude_external_links=True,
            excluded_tags=["nav", "footer", "header", "script", "style", "img"],
        )

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url, config=config)

        if not result or not result.success:
            return None

        # Extract markdown
        if result.markdown:
            fit_md = (result.markdown.fit_markdown or "").strip()
            raw_md = (result.markdown.raw_markdown or "").strip()
            # Prefer fit if substantial, else raw
            markdown = fit_md if len(fit_md) > 200 else raw_md
        else:
            markdown = ""

        # Post-process: extract text paragraphs (CJK-focused)
        content_head = _extract_article_body(markdown)

        return {
            "title": result.metadata.get("title", "") if result.metadata else "",
            "markdown": markdown[:5000],
            "content_head": content_head[:2000],
        }
    except Exception as exc:
        return {"error": str(exc), "title": "", "markdown": "", "content_head": ""}


def _extract_article_body(markdown: str) -> str:
    """Extract the article body from markdown, stripping nav/accessibility noise."""
    if not markdown:
        return ""

    lines = markdown.split("\n")
    paragraphs = []
    in_article = False
    cjk_char_count = 0

    for line in lines:
        line = line.strip()
        if not line or len(line) < 15:
            continue

        # Count CJK characters to detect real content vs navigation
        cjk = sum(1 for c in line if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')

        # Skip image-only lines, accessibility toolbar links, nav items
        if line.startswith("![") or line.startswith("* [") or line.startswith("["):
            continue
        if re.match(r"^(当前位置|首页|无障碍|长者模式|English|网站地图)", line):
            continue

        # Lines with substantial CJK content are article text
        if cjk >= 5 and len(line) > 20:
            in_article = True
            paragraphs.append(line)
        elif in_article and cjk >= 3:
            paragraphs.append(line)
        elif in_article and len(paragraphs) > 3 and cjk == 0:
            # Non-CJK line after article body → likely reached footer
            if len(paragraphs) > 5:
                break

    return "\n".join(paragraphs[:30])


async def crawl_batch(urls: list[str], concurrency: int = 3) -> list[dict | None]:
    """Crawl multiple URLs with controlled concurrency."""
    semaphore = asyncio.Semaphore(concurrency)

    async def crawl_with_limit(url):
        async with semaphore:
            return await crawl_page(url)

    tasks = [crawl_with_limit(u) for u in urls]
    return await asyncio.gather(*tasks)


def extract_key_sentences(markdown: str, tier: str) -> list[str]:
    """Extract 3-8 key sentences that support the tier classification."""
    if not markdown:
        return []

    # Use article body extraction to get clean text lines
    clean_body = _extract_article_body(markdown)
    lines = [l.strip() for l in clean_body.split("\n") if l.strip() and len(l.strip()) > 20]
    if not lines:
        lines = [l.strip() for l in markdown.split("\n") if l.strip() and len(l.strip()) > 20]

    sentences = []

    tier_patterns = {
        "A": ["印发", "遵照执行", "通知如下", "现发布", "自.*起施行",
              "请认真贯彻", "经.*同意", "现予.*发布", "特此通知", "批准"],
        "B": ["召开", "会议指出", "调研", "考察", "强调", "要求",
              "招标", "中标", "公告", "公示", "成交"],
        "C": ["报告", "研究表明", "数据显示", "趋势分析", "预测",
              "解读", "行业协会", "建议", "展望", "统计"],
        "D": ["转载", "来源:", "记者.*报道", "点击查看", "关注",
              "扫码", "订阅", "广告"],
    }

    patterns = tier_patterns.get(tier, [])
    for line in lines:
        if any(re.search(p, line) for p in patterns):
            sentences.append(line)
            if len(sentences) >= 6:
                break

    # Fallback: use longest substantive lines from article body
    if len(sentences) < 3:
        substantive = [l for l in lines if len(l) > 30 and not l.startswith("#")][:6]
        for s in substantive:
            if s not in sentences:
                sentences.append(s)

    return sentences[:8]


def find_attachments(url: str, markdown: str, html: str) -> list[str]:
    """Find PDF/OFD/DOC attachment links in content."""
    attachments = []
    combined = f"{url} {markdown} {html}"
    for ext in [".pdf", ".ofd", ".doc", ".docx"]:
        pattern = rf'https?://[^\s"\'<>]+{ext}'
        found = re.findall(pattern, combined, re.IGNORECASE)
        attachments.extend(found[:3])
    return list(set(attachments))[:5]


def find_outbound_links(markdown: str, html: str) -> list[str]:
    """Find links in content that point to original policy sources."""
    outbound = []
    combined = f"{markdown} {html}"
    # gov.cn links in non-gov content
    gov_links = re.findall(r'https?://[^\s"\'<>]*\.gov\.cn[^\s"\'<>]*', combined)
    outbound.extend(gov_links[:5])
    return list(set(outbound))[:5]


# ── Main pipeline ──

def load_pool(filepath: Path) -> list[dict]:
    records = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def save_output(records: list[dict], filepath: Path):
    with open(filepath, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


async def main_async(max_crawl: int = 200, batch_size: int = 5):
    records = load_pool(POOL_FILE)
    print(f"[INFO] Loaded {len(records)} candidate records")

    # Pre-classify routes
    for r in records:
        route = classify_route(r)
        r["routing"]["route_type"] = route

    route_counts = Counter(r["routing"]["route_type"] for r in records)
    print(f"[INFO] Route distribution: {dict(route_counts)}")

    # Phase 1: Process rule_direct samples (no crawling)
    rule_direct = [r for r in records if r["routing"]["route_type"] == "rule_direct"]
    print(f"\n[Phase 1] Processing {len(rule_direct)} rule_direct samples...")
    for r in rule_direct:
        features = extract_rule_features(r)
        r["semantic_features"].update(features)
        r["routing"]["rule_confidence"] = 0.95
        r["verification"]["accessed"] = False
        r["verification"]["needs_detail_fetch"] = False
        # Generate CoT
        r["cot_reasoning"] = generate_cot_reasoning(r, features)
    print(f"[Phase 1] Done: {len(rule_direct)} rule_direct enriched")

    # Phase 2: Crawl llm_needed + rule_conflict samples
    to_crawl = [
        r for r in records
        if r["routing"]["route_type"] in ("llm_needed", "rule_conflict")
        and r["verification"].get("needs_detail_fetch", True)
    ][:max_crawl]

    print(f"\n[Phase 2] Crawling {len(to_crawl)} pages (max {max_crawl})...")
    urls = [r["url_info"]["url"] for r in to_crawl]

    crawled = 0
    failed = 0
    for i in range(0, len(urls), batch_size):
        batch_urls = urls[i:i + batch_size]
        batch_records = to_crawl[i:i + batch_size]

        results = await crawl_batch(batch_urls, concurrency=3)

        for record, result in zip(batch_records, results):
            url = record["url_info"]["url"]
            domain = record["url_info"]["domain"]

            if result and "error" not in result:
                # Update url_info with crawled data
                if result.get("title"):
                    record["url_info"]["title"] = result["title"]

                # Extract content
                markdown = result.get("markdown", "")
                content_head = result.get("content_head", "")

                record["content"]["content_head"] = content_head
                record["content"]["content_head_source"] = "crawl4ai"
                # Use content_head for key sentences (already cleaned)
                record["content"]["content_key_sentences"] = extract_key_sentences(
                    content_head, record["label"]["tier"]
                )
                record["content"]["attachments"] = find_attachments(url, markdown, html)
                record["content"]["outbound_links"] = find_outbound_links(markdown, html)

                # Update semantic features
                record["semantic_features"]["evidence_sentences"] = (
                    record["content"]["content_key_sentences"][:4]
                )

                record["verification"]["accessed"] = True
                record["verification"]["is_detail_page"] = True
                record["verification"]["needs_detail_fetch"] = False

                # Update routing
                if record["routing"]["route_type"] == "rule_conflict":
                    record["routing"]["llm_needed_reason"] = (
                        "规则判定与页面语义存在冲突——已抓取正文待人工审核"
                    )
                else:
                    record["routing"]["llm_needed_reason"] = (
                        "已抓取正文——规则无法仅凭域名/URL/标题判断"
                    )

                crawled += 1
            else:
                error_msg = result.get("error", "unreachable") if result else "unreachable"
                record["content"]["content_head"] = f"[UNREACHABLE: {error_msg}]"
                record["verification"]["accessed"] = False
                record["verification"]["needs_detail_fetch"] = True
                record["verification"]["why_not_synthetic"] = (
                    f"页面无法访问({error_msg})——标记为 needs_review"
                )
                failed += 1

            # Generate CoT
            features = record.get("semantic_features", {})
            record["cot_reasoning"] = generate_cot_reasoning(record, features)

        if (i // batch_size + 1) % 10 == 0:
            print(f"  [{min(i+batch_size, len(urls))}/{len(urls)}] "
                  f"crawled={crawled} failed={failed}")

    print(f"[Phase 2] Done: {crawled} crawled, {failed} failed")

    # Phase 3: Output enriched dataset
    print(f"\n[Phase 3] Writing enriched dataset to {OUTPUT_FILE}...")
    save_output(records, OUTPUT_FILE)

    # Statistics
    tiers = Counter(r["label"]["tier"] for r in records)
    routes = Counter(r["routing"]["route_type"] for r in records)
    accessed = sum(1 for r in records if r["verification"].get("accessed"))
    has_cot = sum(1 for r in records if r.get("cot_reasoning"))
    needs_review = sum(1 for r in records if r["verification"].get("needs_detail_fetch"))

    print(f"\n{'='*50}")
    print(f"  数据集加工完成")
    print(f"{'='*50}")
    print(f"  总样本数: {len(records)}")
    print(f"  分级分布: {dict(tiers)}")
    print(f"  路由分布: {dict(routes)}")
    print(f"  已访问页面: {accessed}/{len(records)}")
    print(f"  已生成 CoT: {has_cot}/{len(records)}")
    print(f"  需人工审核: {needs_review}")
    print(f"  输出文件: {OUTPUT_FILE}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-crawl", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=5)
    args = parser.parse_args()

    asyncio.run(main_async(max_crawl=args.max_crawl, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
