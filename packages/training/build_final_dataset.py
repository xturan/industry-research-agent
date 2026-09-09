"""
从 enriched candidate pool 构建最终训练数据集。

输入: source_tier_training_dataset_enriched.jsonl
输出:
  - source_tier_train_v2.jsonl (~560 samples, 70%)
  - source_tier_val_v2.jsonl (~120 samples, 15%)
  - source_tier_test_v2.jsonl (~120 samples, 15%)
  - 总体统计报告

策略:
  - A: 保留全部 (228)
  - B: 下采样到 ~280 (从 409)
  - C: 保留全部 (160)
  - D: 保留全部 (138)
  - 目标 ~806 条，A:28%/B:35%/C:20%/D:17%
  - 分层随机划分 train/val/test (70/15/15)
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
INPUT_FILE = DATA_DIR / "source_tier_training_dataset_enriched.jsonl"
OUTPUT_TRAIN = DATA_DIR / "source_tier_train_v2.jsonl"
OUTPUT_VAL = DATA_DIR / "source_tier_val_v2.jsonl"
OUTPUT_TEST = DATA_DIR / "source_tier_test_v2.jsonl"

COC_INSTRUCTION = (
    "你是一个信息源分级专家。请严格按照以下步骤推理并判断信息源的A/B/C/D等级。\n\n"
    "分级标准：\n"
    "A级（政策法规原文）: 政府发布的法规、通知、规划、实施细则的原文。"
    "域名必须是.gov.cn且路径含政策标记（/zcfb//xxgk/等）或标题含通知/意见/办法。\n"
    "B级（官方新闻/公告）: .gov.cn新闻动态、公共资源交易公告、上市公司披露——"
    "不是政策原文但来自官方渠道。\n"
    "C级（专业报告/解读）: 行业协会(.org)、研究机构、咨询公司报告、政策解读。\n"
    "D级（商业媒体/低可信度）: 商业新闻媒体、自媒体、聚合器、2020年前的过时信息。\n\n"
    "请先逐步推理(Step1域名→Step2路径→Step3标题→Step4结论)，然后返回JSON。"
)


def load_enriched(filepath: Path) -> list[dict]:
    records = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def format_training_sample(record: dict) -> dict:
    """Convert enriched record to Alpaca-style training sample with CoT."""
    info = record.get("url_info", {})
    domain = info.get("domain", "")
    url = info.get("url", "")
    title = info.get("title", "") or ""
    label = record.get("label", {})
    tier = label.get("tier", "?")
    cot = record.get("cot_reasoning", "")

    # Input: domain + URL + title
    input_text = f"域名: {domain}\nURL: {url}\n标题: {title}"

    # Add content snippet if crawled
    content_head = record.get("content", {}).get("content_head", "")
    if content_head and len(content_head) > 50:
        input_text += f"\n正文片段: {content_head[:500]}"

    # Output: CoT reasoning + JSON
    authority_score = record.get("scores", {}).get("authority_score", 0.8)
    usage_note = label.get("reason", "基于规则和页面分析的分级判断")
    confidence = label.get("confidence", 0.9)

    output_text = (
        f"{cot}\n\n"
        f'{{"tier": "{tier}", "authority_score": {authority_score}, '
        f'"usage_note": "{usage_note}", "confidence": {confidence}}}'
    )

    return {
        "instruction": COC_INSTRUCTION,
        "input": input_text,
        "output": output_text,
        "tier": tier,
        "domain": domain,
        "route_type": record.get("routing", {}).get("route_type", ""),
        "has_content": bool(content_head and len(content_head) > 50),
    }


def main():
    random.seed(42)

    print(f"[INFO] Loading enriched records from {INPUT_FILE}")
    records = load_enriched(INPUT_FILE)
    print(f"[INFO] Total: {len(records)}")

    # Balance: downsample B-tier
    by_tier = {t: [r for r in records if r["label"]["tier"] == t] for t in "ABCD"}
    print(f"[INFO] Before balancing: A={len(by_tier['A'])} B={len(by_tier['B'])} "
          f"C={len(by_tier['C'])} D={len(by_tier['D'])}")

    # Keep all A/C/D, downsample B to ~280
    target_b = 280
    if len(by_tier["B"]) > target_b:
        # Prioritize: crawled + llm_needed > crawled + rule_direct > uncrawled
        b_priority = sorted(
            by_tier["B"],
            key=lambda r: (
                not r["verification"].get("accessed"),  # crawled first
                r["routing"]["route_type"] != "llm_needed",  # llm_needed first
            ),
        )
        by_tier["B"] = b_priority[:target_b]

    balanced = by_tier["A"] + by_tier["B"] + by_tier["C"] + by_tier["D"]
    print(f"[INFO] After balancing: A={len(by_tier['A'])} B={len(by_tier['B'])} "
          f"C={len(by_tier['C'])} D={len(by_tier['D'])} total={len(balanced)}")

    # Format as training samples
    samples = [format_training_sample(r) for r in balanced]

    # Stratified split by tier
    train_samples, val_samples, test_samples = [], [], []
    for t in "ABCD":
        tier_samples = [s for s in samples if s["tier"] == t]
        random.shuffle(tier_samples)
        n = len(tier_samples)
        n_train = int(n * 0.70)
        n_val = int(n * 0.15)
        train_samples.extend(tier_samples[:n_train])
        val_samples.extend(tier_samples[n_train:n_train + n_val])
        test_samples.extend(tier_samples[n_train + n_val:])

    random.shuffle(train_samples)
    random.shuffle(val_samples)
    random.shuffle(test_samples)

    # Write output
    for filepath, data in [
        (OUTPUT_TRAIN, train_samples),
        (OUTPUT_VAL, val_samples),
        (OUTPUT_TEST, test_samples),
    ]:
        with open(filepath, "w", encoding="utf-8") as f:
            for s in data:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        print(f"[INFO] Wrote {len(data)} samples to {filepath}")

    # Statistics
    for name, data in [("Train", train_samples), ("Val", val_samples), ("Test", test_samples)]:
        tiers = Counter(s["tier"] for s in data)
        has_content = sum(1 for s in data if s.get("has_content"))
        has_cot = sum(1 for s in data if "Step 1" in s.get("output", ""))
        print(f"\n  {name}: {len(data)} samples, tiers={dict(tiers)}, "
              f"with_content={has_content}, with_CoT={has_cot}")

    # Distinguishability check
    print(f"\n[INFO] Key quality metrics:")
    all_samples = train_samples + val_samples + test_samples
    for t in "ABCD":
        tier_samples = [s for s in all_samples if s["tier"] == t]
        with_content = sum(1 for s in tier_samples if s.get("has_content"))
        print(f"  Tier {t}: {len(tier_samples)} samples, {with_content} have page content")


if __name__ == "__main__":
    main()
