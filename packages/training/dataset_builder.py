"""Build training dataset for Source Tiering model.

Combines:
1. Real seed data from Deep Research runs (seed_source_assessments.jsonl)
2. Synthetic data generated from domain knowledge + rule-based labeling

Outputs Alpaca-format JSONL for LoRA fine-tuning.

Usage:
    python -m packages.training.dataset_builder
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from urllib.parse import urlparse

SEED_FILE = Path(__file__).parent / "data" / "seed_source_assessments.jsonl"
OUTPUT_DIR = Path(__file__).parent / "data"
TRAIN_FILE = OUTPUT_DIR / "source_tier_train.jsonl"
VAL_FILE = OUTPUT_DIR / "source_tier_val.jsonl"
TEST_FILE = OUTPUT_DIR / "source_tier_test.jsonl"

SYSTEM_INSTRUCTION = (
    "你是一个信息源分级专家。根据以下信息源的元数据，判断其可信度等级和权威性。\n\n"
    "分级标准：\n"
    "A级: 政府官方政策原文（法规、通知、规划、实施细则）\n"
    "B级: 政府新闻/公共资源交易平台、企业公告、上市公司披露\n"
    "C级: 行业协会、研究机构、政策解读、3年以上旧源\n"
    "D级: 商业媒体、自媒体、聚合器、严重过时源\n\n"
    "返回JSON: {\"tier\":\"A/B/C/D\",\"authority_score\":0.0-1.0,"
    "\"usage_note\":\"简短使用建议\",\"confidence\":0.0-1.0}"
)


def _format_input(url: str, title: str, domain: str = "") -> str:
    if not domain:
        try:
            domain = urlparse(url).netloc.lower()
        except Exception:
            domain = ""
    lines = [f"域名: {domain}", f"URL: {url}", f"标题: {title}"]
    return "\n".join(lines)


def _format_output(tier: str, authority_score: float, usage_note: str) -> str:
    confidence = 0.95 if tier in ("A", "B") else 0.80
    return json.dumps({
        "tier": tier,
        "authority_score": round(authority_score, 2),
        "usage_note": usage_note[:150],
        "confidence": confidence,
    }, ensure_ascii=False)


def load_seed_data() -> list[dict]:
    """Load real seed data from Deep Research runs."""
    if not SEED_FILE.exists():
        print(f"[WARN] Seed file not found: {SEED_FILE}")
        return []
    samples = []
    with open(SEED_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    print(f"[INFO] Loaded {len(samples)} seed samples")
    return samples


def generate_synthetic_data() -> list[dict]:
    """Generate synthetic training data from domain knowledge."""
    samples = []

    # --- A-tier: Central government ministries ---
    central_domains = [
        ("www.gov.cn", "国务院"),
        ("ndrc.gov.cn", "国家发改委"),
        ("miit.gov.cn", "工信部"),
        ("most.gov.cn", "科技部"),
        ("mofcom.gov.cn", "商务部"),
        ("stats.gov.cn", "国家统计局"),
        ("customs.gov.cn", "海关总署"),
        ("mof.gov.cn", "财政部"),
        ("mee.gov.cn", "生态环境部"),
        ("mohurd.gov.cn", "住建部"),
    ]
    policy_titles = [
        "关于印发{}产业发展行动计划的通知",
        "{}领域实施细则（试行）",
        "关于加快推进{}高质量发展的若干措施",
        "{}专项资金管理办法",
        "关于{}的指导意见",
    ]
    industries = ["新能源汽车", "人工智能", "低空经济", "数据要素", "半导体",
                  "氢能", "储能", "光伏", "生物医药", "商业航天"]

    for domain, dept in central_domains:
        for title_tpl in policy_titles[:3]:
            for ind in random.sample(industries, 3):
                title = title_tpl.format(ind)
                url = f"https://{domain}/zwgk/zcwj/2025/{random.randint(1000,9999)}.html"
                samples.append({
                    "url": url, "title": title, "domain": domain,
                    "tier": "A", "authority_score": 0.95,
                    "usage_note": f"{dept}正式政策文件——可作为一手证据",
                })
    # Gov PDF documents
    for domain, dept in central_domains[:5]:
        for ind in random.sample(industries, 2):
            title = f"{ind}发展规划（2025-2030）"
            url = f"https://{domain}/attachment/2025/{random.randint(100,999)}.pdf"
            samples.append({
                "url": url, "title": title, "domain": domain,
                "tier": "A", "authority_score": 0.95,
                "usage_note": "官方政策文件PDF——一手证据",
            })

    return samples


def generate_synthetic_b_tier() -> list[dict]:
    """B-tier: Gov news, procurement platforms, enterprise announcements."""
    samples = []

    procurement_domains = [
        "ggzy.hefei.gov.cn", "ggzyjy.jiangsu.gov.cn", "ccgp.gov.cn",
        "ggzy.hunan.gov.cn", "ggzy.shandong.gov.cn", "ggzy.zj.gov.cn",
    ]
    procurement_titles = [
        "{}项目招标公告", "{}设备采购中标公示",
        "{}工程施工招标公告", "{}服务采购结果公告",
    ]
    for domain in procurement_domains:
        for title_tpl in procurement_titles:
            for ind in random.sample(
                ["智慧城市", "数据中心", "充电桩", "光伏电站", "污水处理"], 2
            ):
                title = title_tpl.format(ind)
                url = f"https://{domain}/jyxx/2025/{random.randint(10000,99999)}.html"
                samples.append({
                    "url": url, "title": title, "domain": domain,
                    "tier": "B", "authority_score": 0.80,
                    "usage_note": "公共资源交易平台——项目落地证据",
                })

    gov_news_domains = [
        "www.gd.gov.cn", "www.zj.gov.cn", "www.ah.gov.cn",
        "www.sc.gov.cn", "www.js.gov.cn", "www.sd.gov.cn",
    ]
    for domain in gov_news_domains:
        title = f"省政府召开{random.choice(['新能源', '数字经济', '低空经济'])}专题会议"
        url = f"https://{domain}/xwzx/zwdt/2025/{random.randint(100,999)}.html"
        samples.append({
            "url": url, "title": title, "domain": domain,
            "tier": "B", "authority_score": 0.75,
            "usage_note": "政府新闻——需核实是否有配套政策文件",
        })

    enterprise_domains = ["cninfo.com.cn", "sse.com.cn", "szse.cn"]
    for domain in enterprise_domains:
        for title in ["关于签订重大合同的公告", "2025年第一季度报告",
                      "关于中标项目的公告", "关于获得政府补助的公告"]:
            url = f"https://www.{domain}/disclosure/2025/{random.randint(1000,9999)}.html"
            samples.append({
                "url": url, "title": title, "domain": f"www.{domain}",
                "tier": "B", "authority_score": 0.80,
                "usage_note": "上市公司公告——企业层面证据",
            })

    return samples


def generate_synthetic_cd_tier() -> list[dict]:
    """C/D-tier: Associations, media, outdated sources — expanded for balance."""
    samples = []
    industries = ["新能源汽车", "人工智能", "低空经济", "数据要素", "半导体",
                  "氢能", "储能", "光伏", "生物医药", "商业航天"]

    # --- C-tier: Industry associations (expanded) ---
    assoc_domains = [
        ("caam.org.cn", "中国汽车工业协会"),
        ("caai.cn", "中国人工智能学会"),
        ("chinapv.org.cn", "中国光伏行业协会"),
        ("cec.org.cn", "中国电力企业联合会"),
        ("csia.net.cn", "中国半导体行业协会"),
        ("cbia.com.cn", "中国电池工业协会"),
        ("wind.com.cn", "中国可再生能源学会风能专委会"),
        ("cmes.org", "中国机械工程学会"),
        ("cppia.com.cn", "中国塑料加工工业协会"),
        ("chinairn.com", "中研网"),
    ]
    assoc_titles = [
        "{}发布2025年行业运行报告",
        "{}：行业发展白皮书",
        "{}关于行业标准的通知",
        "{}年度统计数据发布",
        "{}行业景气指数月报",
    ]
    for domain, name in assoc_domains:
        for title_tpl in assoc_titles[:3]:
            title = title_tpl.format(name)
            url = f"https://www.{domain}/news/2025/{random.randint(100,999)}.html"
            samples.append({
                "url": url, "title": title, "domain": f"www.{domain}",
                "tier": "C", "authority_score": 0.55,
                "usage_note": "行业协会——用于背景参考，非一手证据",
            })

    # C-tier: Research institutes and think tanks
    research_domains = [
        ("cas.cn", "中国科学院"), ("cass.cn", "中国社科院"),
        ("drc.gov.cn", "国务院发展研究中心"), ("cicc.com", "中金研究"),
        ("ccidgroup.com", "赛迪研究院"),
    ]
    for domain, name in research_domains:
        for title in [f"{name}：产业发展趋势分析", f"{name}发布研究报告"]:
            url = f"https://www.{domain}/research/2025/{random.randint(100,999)}.html"
            samples.append({
                "url": url, "title": title, "domain": f"www.{domain}",
                "tier": "C", "authority_score": 0.50,
                "usage_note": "研究机构——可作为分析参考，需核实数据来源",
            })

    # C-tier: Policy interpretation articles on gov sites (not policy itself)
    for province in ["广东", "浙江", "江苏", "山东", "四川", "湖北",
                     "安徽", "河南", "湖南", "福建", "河北", "陕西"]:
        for title_tpl in [
            "专家解读：{}省新能源产业政策要点",
            "{}省发改委负责人答记者问",
            "一图读懂{}省低空经济发展规划",
        ]:
            title = title_tpl.format(province)
            domain = f"www.{province[:1]}.gov.cn"
            url = f"https://{domain}/jdhy/2025/{random.randint(100,999)}.html"
            samples.append({
                "url": url, "title": title, "domain": domain,
                "tier": "C", "authority_score": 0.45,
                "usage_note": "政策解读/答记者问——非政策原文，需找到原始文件",
            })

    # C-tier: Consulting firms and market research
    consulting = [
        ("iresearch.cn", "艾瑞咨询"), ("analysys.cn", "易观"),
        ("forward.com.cn", "前瞻产业研究院"), ("chyxx.com", "智研咨询"),
        ("leadleo.com", "头豹研究院"), ("qianzhan.com", "前瞻网"),
    ]
    for domain, name in consulting:
        for title in [f"{name}：2025年{random.choice(industries)}市场规模预测",
                      f"{name}发布{random.choice(industries)}行业深度报告"]:
            url = f"https://www.{domain}/report/2025/{random.randint(100,999)}.html"
            samples.append({
                "url": url, "title": title, "domain": f"www.{domain}",
                "tier": "C", "authority_score": 0.40,
                "usage_note": "咨询机构报告——数据可参考但需交叉验证",
            })

    # C-tier: Old but relevant gov sources (2-3 years)
    for year in [2022, 2023]:
        for ind in random.sample(industries, 4):
            title = f"关于促进{ind}产业发展的若干意见（{year}年）"
            url = f"https://www.gov.cn/zwgk/{year}/content_{random.randint(1000,9999)}.htm"
            samples.append({
                "url": url, "title": title, "domain": "www.gov.cn",
                "tier": "C", "authority_score": 0.30,
                "usage_note": f"政策文件已过时（{year}年）——仅供历史背景参考",
            })

    # --- D-tier: Commercial media (expanded) ---
    media_domains = [
        "36kr.com", "thepaper.cn", "jiemian.com", "cls.cn",
        "yicai.com", "caixin.com", "sohu.com", "sina.com.cn",
        "163.com", "qq.com", "baidu.com", "zhihu.com",
        "huxiu.com", "tmtpost.com", "leiphone.com", "iyiou.com",
    ]
    media_titles = [
        "{}：{}行业最新动态",
        "{}行业深度分析：未来趋势展望",
        "{}概念股大涨，机构看好后市",
        "万字长文解读{}产业链投资机会",
        "{}赛道火热，多家企业加速布局",
    ]
    industries_d = industries
    for domain in media_domains:
        for _ in range(3):
            title_tpl = random.choice(media_titles)
            ind = random.choice(industries_d)
            prefix = random.choice(["深度", "独家", "重磅", "最新", "突发"])
            title = title_tpl.format(prefix if "{}" in title_tpl[:5] else ind, ind)
            url = f"https://www.{domain}/article/2025/{random.randint(10000,99999)}"
            samples.append({
                "url": url, "title": title, "domain": f"www.{domain}",
                "tier": "D", "authority_score": 0.30,
                "usage_note": "商业媒体——需核实原始来源后方可引用",
            })

    # D-tier: Self-media / WeChat articles
    wechat_titles = [
        "重磅！{}政策即将出台", "{}行业内部人士透露最新消息",
        "深度好文：{}产业全景解析", "{}龙头企业独家调研纪要",
    ]
    for _ in range(20):
        title = random.choice(wechat_titles).format(random.choice(industries_d))
        url = f"https://mp.weixin.qq.com/s/{random.randint(100000,999999)}"
        samples.append({
            "url": url, "title": title, "domain": "mp.weixin.qq.com",
            "tier": "D", "authority_score": 0.20,
            "usage_note": "自媒体/微信公众号——不可作为证据来源",
        })

    # D-tier: Severely outdated gov sources (expanded years)
    for year in [2015, 2016, 2017, 2018, 2019]:
        for ind in random.sample(industries_d, 3):
            title = f"关于{year}年{ind}推广应用的通知"
            url = f"https://www.gov.cn/zwgk/{year}/content_{random.randint(1000,9999)}.htm"
            samples.append({
                "url": url, "title": title, "domain": "www.gov.cn",
                "tier": "D", "authority_score": 0.15,
                "usage_note": "严重过时（5年以上）——仅供历史参考",
            })

    # D-tier: Aggregator / SEO sites
    agg_domains = ["ofweek.com", "polaris.cn", "bjx.com.cn",
                   "in-en.com", "solarbe.com", "energytrend.cn"]
    for domain in agg_domains:
        for _ in range(3):
            title = f"{random.choice(industries_d)}行业{random.choice(['周报', '月报', '快讯', '速递'])}"
            url = f"https://www.{domain}/news/2025/{random.randint(1000,9999)}.html"
            samples.append({
                "url": url, "title": title, "domain": f"www.{domain}",
                "tier": "D", "authority_score": 0.25,
                "usage_note": "行业聚合站——二手信息，需追溯原始来源",
            })

    return samples


def convert_to_alpaca(samples: list[dict]) -> list[dict]:
    """Convert raw samples to Alpaca instruction-following format."""
    alpaca_samples = []
    for s in samples:
        domain = s.get("domain", "")
        if not domain:
            try:
                domain = urlparse(s["url"]).netloc.lower()
            except Exception:
                domain = ""
        input_text = _format_input(s["url"], s["title"], domain)
        output_text = _format_output(
            s["tier"], s["authority_score"], s.get("usage_note", "")
        )
        alpaca_samples.append({
            "instruction": SYSTEM_INSTRUCTION,
            "input": input_text,
            "output": output_text,
        })
    return alpaca_samples


def split_dataset(
    samples: list[dict], train_ratio: float = 0.70, val_ratio: float = 0.15
) -> tuple[list[dict], list[dict], list[dict]]:
    """Split into train/val/test with stratification by tier."""
    by_tier: dict[str, list[dict]] = {"A": [], "B": [], "C": [], "D": []}
    for s in samples:
        output_str = s.get("output", "")
        if '"A"' in output_str:
            by_tier["A"].append(s)
        elif '"B"' in output_str:
            by_tier["B"].append(s)
        elif '"C"' in output_str:
            by_tier["C"].append(s)
        else:
            by_tier["D"].append(s)

    train, val, test = [], [], []
    for tier_samples in by_tier.values():
        random.shuffle(tier_samples)
        n = len(tier_samples)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        train.extend(tier_samples[:n_train])
        val.extend(tier_samples[n_train:n_train + n_val])
        test.extend(tier_samples[n_train + n_val:])

    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)
    return train, val, test


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(42)

    # 1. Load real seed data
    seed_samples = load_seed_data()

    # 2. Generate synthetic data
    synthetic_a = generate_synthetic_data()
    synthetic_b = generate_synthetic_b_tier()
    synthetic_cd = generate_synthetic_cd_tier()
    all_synthetic = synthetic_a + synthetic_b + synthetic_cd

    print(f"[INFO] Synthetic: A={len(synthetic_a)}, B={len(synthetic_b)}, "
          f"CD={len(synthetic_cd)}, total={len(all_synthetic)}")

    # 3. Combine
    all_raw = seed_samples + all_synthetic
    print(f"[INFO] Total raw samples: {len(all_raw)}")

    # 4. Convert to Alpaca format
    alpaca = convert_to_alpaca(all_raw)

    # 5. Split
    train, val, test = split_dataset(alpaca)
    print(f"[INFO] Split: train={len(train)}, val={len(val)}, test={len(test)}")

    # 6. Write output files
    for filepath, data in [(TRAIN_FILE, train), (VAL_FILE, val), (TEST_FILE, test)]:
        with open(filepath, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"[INFO] Written: {filepath} ({len(data)} samples)")

    # 7. Print tier distribution
    for name, data in [("train", train), ("val", val), ("test", test)]:
        dist = {"A": 0, "B": 0, "C": 0, "D": 0}
        for s in data:
            out = s.get("output", "")
            for t in "ABCD":
                if f'"{t}"' in out:
                    dist[t] += 1
                    break
        print(f"  {name}: {dist}")


if __name__ == "__main__":
    main()
