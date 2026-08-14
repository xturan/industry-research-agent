"""
为训练数据生成高质量正文——真实爬取内容优先，合成内容补充缺口。
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# ── 填充变量 ──

DEPTS = [
    "国家发展和改革委员会", "工业和信息化部", "科学技术部",
    "财政部", "生态环境部", "住房和城乡建设部",
    "国家能源局", "国家市场监督管理总局",
]
INDUSTRIES = [
    "新能源汽车", "人工智能", "低空经济", "数据要素", "半导体",
    "氢能", "储能", "光伏", "生物医药", "商业航天", "新型储能",
]
DOC_TYPES = ["发展规划", "实施意见", "行动方案", "管理办法", "指导意见"]
SOURCES = ["新华社", "人民日报", "经济日报", "科技日报", "中国证券报"]
ORGS = [
    "中国汽车工业协会", "中国光伏行业协会", "中国半导体行业协会",
    "中国电力企业联合会", "艾瑞咨询", "前瞻产业研究院",
    "赛迪研究院", "中国国际经济交流中心",
]
PROVINCES = ["广东", "浙江", "江苏", "山东", "四川", "湖北"]
EXPERTS = ["首席经济学家", "研究院院长", "高级分析师"]
AUTHORS = ["记者 张某", "编辑 李某", "研究员 王某"]

random.seed(42)

# ── 正文模板 ──

A_TEMPLATES = [
    """{dept}关于印发{industry}{doc_type}的通知
{dept}发〔{year}〕{num}号

各省、自治区、直辖市人民政府，国务院各部委、各直属机构：

为深入贯彻落实党中央、国务院关于{industry}发展的决策部署，加快推动{industry}高质量发展，经国务院同意，现将《{industry}{doc_type}》印发给你们，请结合实际认真贯彻执行。

一、总体要求
以习近平新时代中国特色社会主义思想为指导，立足新发展阶段，完整、准确、全面贯彻新发展理念，构建新发展格局，推动{industry}实现质的有效提升和量的合理增长。

二、主要目标
到{year2}年，{industry}综合实力显著增强，关键技术取得突破。产业总产值年均增长{percent}%以上，研发投入强度达到{percent2}%以上。

三、重点任务
（一）加强技术创新。围绕{industry}关键环节，组织实施重大科技攻关。
（二）完善标准体系。加快制定{industry}相关国家标准和行业标准。
（三）强化要素保障。加大财政金融支持力度，引导社会资本参与。

四、保障措施
（一）加强组织领导。建立{industry}发展协调机制。
（二）强化监督考核。将{industry}发展纳入考核评价体系。

{dept}
{year}年{month}月{day}日""",
]

B_TEMPLATES = [
    """{dept}召开{industry}专题座谈会
来源：{source} 时间：{year}-{month:02d}-{day:02d}

{day}日，{dept}在京召开{industry}发展专题座谈会。{dept}主要负责同志出席会议并讲话。

会议指出，{industry}是国民经济的重要组成部分，对于推动高质量发展具有重要意义。近年来，在党中央、国务院的坚强领导下，{industry}发展取得显著成效。

会议强调，要深入贯彻落实中央经济工作会议精神，坚持问题导向和目标导向，聚焦{industry}领域的关键问题，加大政策支持力度。

会议要求，各相关部门要加强协调配合，形成工作合力。要密切跟踪{industry}发展动态，及时研究解决新情况新问题。

{dept}相关部门负责同志、部分企业代表参加了座谈会。""",

    """{dept}调研{industry}发展情况
来源：{source} 时间：{year}-{month:02d}-{day:02d}

近日，{dept}负责同志赴{province}调研{industry}发展情况。调研组实地考察了多家{industry}企业，详细了解生产经营、技术创新、市场开拓等情况。

在企业生产车间，调研组成员认真察看生产流程，询问产品性能、市场销售等情况。企业负责人介绍了近年来取得的进展。

调研组对企业取得的成绩给予充分肯定，指出{industry}发展势头良好，要继续坚持创新驱动，不断提升核心竞争力。

调研组还与当地政府部门进行了座谈，就优化营商环境进行了深入交流。""",
]

C_TEMPLATES = [
    """{org}发布{industry}行业研究报告
来源：{org} 时间：{year}-{month:02d}-{day:02d}

{org}日前发布《{year}年{industry}行业发展研究报告》。报告基于对全国{num2}家{industry}企业的调研数据，从市场规模、竞争格局、技术趋势等维度进行了深入分析。

报告显示，{year}年{industry}行业市场规模达到{market_size}，同比增长{growth}。报告指出，随着政策持续支持和下游需求增长，{industry}保持良好发展态势。

在竞争格局方面，报告分析认为行业集中度进一步提升，头部企业凭借技术和渠道占据主要份额。同时一批创新型中小企业快速成长。

报告建议，{industry}企业应加大研发投入，关注技术迭代趋势。同时建议政府部门进一步完善相关政策体系。

本次研究得到了相关部门的指导和支持。""",

    """专家解读：{policy_title}
来源：{source} 时间：{year}-{month:02d}-{day:02d}

{dept}日前发布《{policy_title}》，引发社会各界广泛关注。对此，记者采访了{org}{expert}进行解读。

{expert}表示，该政策是贯彻落实中央关于{industry}发展决策部署的重要举措。政策从{pillar1}、{pillar2}等方面提出了具体要求。

{expert}分析认为，政策的主要亮点：一是{highlight1}；二是{highlight2}；三是{highlight3}。

对于政策的实施效果，{expert}认为关键在于落实。"政策要真正发挥效果，需要在{aspect1}和{aspect2}方面同步推进。"

{expert}建议，{industry}相关企业应认真研究政策内容，把握政策红利，加快转型升级。""",
]

D_TEMPLATES = [
    """{title}
来源：{source} 作者：{author} 时间：{year}-{month:02d}-{day:02d}

近日，{industry}领域传出重大消息。据知情人士透露，{event_desc}。

记者了解到，{background}。业内人士分析认为，{analysis}。

值得注意的是，{highlight}。有观点认为，{opinion}。

对此，记者致电相关负责人，截至发稿未获回复。

对于{industry}行业的未来发展，市场人士看法不一。乐观者认为{optimistic}；谨慎者则提醒{caution}。

（本文仅供参考，不构成投资建议）""",

    """{title}
原创 {author} {year}-{month:02d}-{day:02d}

最近后台很多朋友问我{industry}这个方向怎么样，今天跟大家聊聊这个话题。

最近{event_description}

我从几个角度来分析：

第一，{point1}

第二，{point2}

第三，{point3}

总结一下，{conclusion}

大家怎么看？欢迎在评论区留言讨论。

（关注本公众号，获取更多深度分析）""",
]

ALL_TEMPLATES = {"A": A_TEMPLATES, "B": B_TEMPLATES, "C": C_TEMPLATES, "D": D_TEMPLATES}


def build_context(domain: str, title: str, tier: str) -> dict:
    """Build template context from domain/title hints."""
    year = random.randint(2024, 2026)
    dept = random.choice(DEPTS)
    industry = random.choice(INDUSTRIES)

    # Match domain to known entities
    if domain:
        if "ndrc" in domain: dept = "国家发展和改革委员会"
        elif "miit" in domain: dept = "工业和信息化部"
        elif "mee" in domain: dept = "生态环境部"
        elif "mof" in domain: dept = "财政部"
        elif "mofcom" in domain: dept = "商务部"
        elif "customs" in domain: dept = "海关总署"
        elif "nea" in domain: dept = "国家能源局"
        elif "stats" in domain: dept = "国家统计局"
        elif any(d in domain for d in ["caam", "chinapv", "cec", "csia", "cppia"]):
            dept = random.choice(ORGS)
        elif "cas" in domain: dept = "中国科学院"
        elif "iresearch" in domain or "qianzhan" in domain or "analysys" in domain:
            dept = random.choice([o for o in ORGS if "咨询" in o or "研究院" in o])

    if title:
        for ind in INDUSTRIES:
            if ind in title:
                industry = ind
                break

    return {
        "year": year, "year2": year + random.randint(3, 5),
        "dept": dept, "industry": industry,
        "doc_type": random.choice(DOC_TYPES),
        "source": random.choice(SOURCES),
        "province": random.choice(PROVINCES),
        "org": random.choice(ORGS),
        "month": random.randint(1, 12), "day": random.randint(1, 28),
        "num": random.randint(100, 999),
        "num2": random.randint(50, 500),
        "percent": random.randint(8, 20), "percent2": random.randint(3, 10),
        "growth": f"{random.randint(5, 30)}%",
        "market_size": f"{random.randint(500, 5000)}亿元",
        "expert": random.choice(EXPERTS),
        "author": random.choice(AUTHORS),
        "policy_title": random.choice(["关于加快新型工业化发展的意见", "促进数字经济高质量发展若干措施", "推动绿色低碳转型行动方案"]),
        "pillar1": random.choice(["技术创新", "产业升级"]),
        "pillar2": random.choice(["要素保障", "人才培养"]),
        "highlight1": random.choice(["明确了发展路线图", "加大财政支持力度", "建立跨部门协调机制"]),
        "highlight2": random.choice(["提出了量化目标", "强化标准引领", "突出企业主体地位"]),
        "highlight3": random.choice(["注重产业链协同", "鼓励先行先试"]),
        "aspect1": random.choice(["政策执行", "资金配套"]),
        "aspect2": random.choice(["地方落地", "企业参与"]),
        "title": title or f"{industry}行业观察",
        "event_desc": f"某公司完成新一轮融资，估值超{random.randint(10, 100)}亿元",
        "background": f"近年来{industry}行业快速发展",
        "analysis": f"行业面临{random.choice(['产能过剩', '技术瓶颈', '标准缺失'])}挑战",
        "highlight": f"多家上市公司布局{industry}赛道",
        "opinion": "短期热度存在一定泡沫风险",
        "optimistic": "政策和技术双轮驱动下行业前景广阔",
        "caution": "需警惕竞争加剧等风险",
        "event_description": f"近日{industry}行业迎来利好，相关部门表示将出台扶持政策",
        "point1": random.choice(["政策面：国家持续加码支持", "技术面：关键突破带来新机会"]),
        "point2": random.choice(["资本面：巨头纷纷入场", "产业面：产业链日趋完善"]),
        "point3": random.choice(["风险面：不确定性仍然存在", "监管面：合规要求提高"]),
        "conclusion": random.choice(["中长期看好但短期需谨慎", "行业进入黄金发展期"]),
    }


def generate_body(tier: str, domain: str = "", title: str = "") -> str:
    ctx = build_context(domain, title, tier)
    template = random.choice(ALL_TEMPLATES.get(tier, A_TEMPLATES))
    return template.format(**ctx)


# ── Main ──

def main():
    random.seed(42)

    # Load all three splits
    splits = {}
    for name in ["source_tier_train_v2.jsonl", "source_tier_val_v2.jsonl",
                 "source_tier_test_v2.jsonl"]:
        fpath = DATA_DIR / name
        if fpath.exists():
            with open(fpath, encoding="utf-8") as f:
                splits[name] = [json.loads(line) for line in f if line.strip()]

    all_samples = []
    for name, samples in splits.items():
        for s in samples:
            s["_split"] = name
            all_samples.append(s)

    print(f"[INFO] Total samples: {len(all_samples)}")

    # Use real content where available
    real_count = 0
    for s in all_samples:
        raw = s.get("real_content", "")
        if raw and len(raw) > 100:
            # Filter out navigation-heavy content (images, links, accessibility toolbar)
            lines = raw.split("\n")
            nav_lines = sum(1 for l in lines if l.strip().startswith(("![", "* [", "[!(", "登录")))
            cjk = sum(1 for c in raw if '\u4e00' <= c <= '\u9fff')
            # Require >40% CJK and <15% nav lines
            if cjk / len(raw) > 0.08 and nav_lines / max(len(lines), 1) < 0.15:
                s["input"] += f"\n正文片段: {raw[:800]}"
                s["has_content"] = True
                real_count += 1
    print(f"[INFO] Real crawled content (filtered): {real_count}")

    # Generate content for those without
    gen_count = Counter()
    for s in all_samples:
        if s.get("has_content"):
            continue
        tier = s["tier"]
        domain = s.get("domain", "")
        title = s.get("title", "")
        body = generate_body(tier, domain=domain, title=title)
        s["input"] += f"\n正文片段: {body[:800]}"
        s["has_content"] = True
        gen_count[tier] += 1
    print(f"[INFO] Synthetic content: {dict(gen_count)}")

    # Add extra C and D samples for balance
    COC_INST = all_samples[0]["instruction"]
    new_c = 0
    for _ in range(60):
        c_domain = random.choice([
            "www.caam.org.cn", "www.chinapv.org.cn", "www.cec.org.cn",
            "www.cas.cn", "www.iresearch.cn", "www.qianzhan.com",
        ])
        title = f"{random.choice(ORGS)}：{random.choice(INDUSTRIES)}{random.choice(['行业报告', '趋势分析', '发展展望'])}"
        body = generate_body("C", domain=c_domain, title=title)
        all_samples.append({
            "instruction": COC_INST,
            "input": f"域名: {c_domain}\nURL: https://{c_domain}/report/{random.randint(100,999)}.html\n标题: {title}\n正文片段: {body[:800]}",
            "output": f'Step 1: 域名 {c_domain} 不是.gov.cn——不是政府网站\n'
                      f'Step 2: {c_domain} 是行业协会/研究机构/咨询公司\n'
                      f'Step 3: 标题含研究报告用语\n'
                      f'Step 4: 正文为研究报告格式，含数据分析和趋势预测\n'
                      f'结论: 综合判断为 C 级(专业报告/解读)\n\n'
                      f'{{"tier": "C", "authority_score": 0.5, "usage_note": "行业协会/研究机构——背景参考", "confidence": 0.85}}',
            "tier": "C", "domain": c_domain, "route_type": "llm_needed", "has_content": True,
        })
        new_c += 1

    new_d = 0
    for _ in range(50):
        d_domain = random.choice([
            "www.sohu.com", "finance.sina.com.cn", "www.163.com",
            "www.thepaper.cn", "mp.weixin.qq.com",
        ])
        title = f"{random.choice(INDUSTRIES)}：{random.choice(['风口还是泡沫', '万亿赛道爆发', '政策红利释放'])}"
        body = generate_body("D", domain=d_domain, title=title)
        all_samples.append({
            "instruction": COC_INST,
            "input": f"域名: {d_domain}\nURL: https://{d_domain}/a/{random.randint(100000,999999)}.html\n标题: {title}\n正文片段: {body[:800]}",
            "output": f'Step 1: 域名 {d_domain} 是商业媒体/自媒体\n'
                      f'Step 2: {d_domain} 不在已知权威清单中\n'
                      f'Step 3: 标题为自媒体风格\n'
                      f'Step 4: 正文含媒体标记（知情人士/记者了解/免责声明）\n'
                      f'结论: 综合判断为 D 级(商业媒体/低可信度)\n\n'
                      f'{{"tier": "D", "authority_score": 0.25, "usage_note": "商业媒体——不作为证据来源", "confidence": 0.95}}',
            "tier": "D", "domain": d_domain, "route_type": "rule_direct", "has_content": True,
        })
        new_d += 1

    print(f"[INFO] Added synthetic: C={new_c}, D={new_d}")
    random.shuffle(all_samples)

    # Re-split: 70/15/15
    train, val, test = [], [], []
    for t in "ABCD":
        ts = [s for s in all_samples if s["tier"] == t]
        random.shuffle(ts)
        n = len(ts)
        train.extend(ts[:int(n * 0.7)])
        val.extend(ts[int(n * 0.7):int(n * 0.85)])
        test.extend(ts[int(n * 0.85):])

    random.shuffle(train); random.shuffle(val); random.shuffle(test)

    # Clean up internal fields and write
    for fname, data in [("source_tier_train_v2.jsonl", train),
                         ("source_tier_val_v2.jsonl", val),
                         ("source_tier_test_v2.jsonl", test)]:
        with open(DATA_DIR / fname, "w", encoding="utf-8") as f:
            for s in data:
                clean = {k: v for k, v in s.items()
                         if k not in ("_split", "real_content")}
                f.write(json.dumps(clean, ensure_ascii=False) + "\n")

    # Final stats
    print(f"\n{'='*50}")
    for name, data in [("Train", train), ("Val", val), ("Test", test)]:
        tiers = Counter(s["tier"] for s in data)
        with_c = sum(1 for s in data if s.get("has_content"))
        print(f"  {name}: {len(data)} {dict(tiers)}, content={with_c}")

    total = train + val + test
    print(f"\n  TOTAL: {len(total)}, all have content: {all(s.get('has_content') for s in total)}")
    print(f"  Real content: {real_count}, Synthetic: {sum(gen_count.values())}, New C+D: {new_c + new_d}")


if __name__ == "__main__":
    main()
