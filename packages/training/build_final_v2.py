"""Final v2 dataset builder — enriched pool → balanced training splits with content."""
import json, random, sys
from collections import Counter
from pathlib import Path

random.seed(42)
DATA_DIR = Path(__file__).parent / "data"

# Load enriched
with open(DATA_DIR / "source_tier_training_dataset_enriched.jsonl", encoding="utf-8") as f:
    enriched = [json.loads(line) for line in f if line.strip()]

# Balance
by_tier = {t: [r for r in enriched if r["label"]["tier"] == t] for t in "ABCD"}
by_tier["B"] = sorted(by_tier["B"], key=lambda r: (
    not r["verification"].get("accessed"),
    r["routing"]["route_type"] != "llm_needed",
))[:280]
balanced = by_tier["A"] + by_tier["B"] + by_tier["C"] + by_tier["D"]
print(f"Balanced: A={len(by_tier['A'])} B={len(by_tier['B'])} C={len(by_tier['C'])} D={len(by_tier['D'])} = {len(balanced)}")

DEPTS = ["国家发展和改革委员会", "工业和信息化部", "科学技术部", "财政部", "生态环境部", "国家能源局"]
INDS = ["新能源汽车", "人工智能", "低空经济", "数据要素", "半导体", "氢能", "储能", "光伏", "生物医药"]
SOURCES = ["新华社", "人民日报", "经济日报", "科技日报"]
ORGS = ["中国汽车工业协会", "中国光伏行业协会", "中国半导体行业协会", "艾瑞咨询", "前瞻产业研究院"]
PROVS = ["广东", "浙江", "江苏", "山东", "四川"]
DOCS = ["发展规划", "实施意见", "行动方案", "管理办法"]


def is_good_content(ch):
    if not ch or len(ch) < 100:
        return False
    cjk = sum(1 for c in ch if "\u4e00" <= c <= "\u9fff")
    if cjk / len(ch) < 0.05:
        return False
    lines = ch.split("\n")
    if len(lines) > 2:
        nav = sum(1 for l in lines[:5] if l.strip().startswith(("![", "* [", "登录", "无障碍", "长者模式")))
        if nav >= 3:
            return False
    return True


def gen_body(tier, domain="", title=""):
    y = random.randint(2024, 2026)
    dept = random.choice(DEPTS)
    ind = random.choice(INDS)
    if domain:
        if "ndrc" in domain: dept = "国家发展和改革委员会"
        elif "miit" in domain: dept = "工业和信息化部"
        elif "mee" in domain: dept = "生态环境部"
        elif "mof" in domain: dept = "财政部"
        elif "nea" in domain: dept = "国家能源局"
    if title:
        for i in INDS:
            if i in title: ind = i; break

    if tier == "A":
        return (
            f"{dept}关于印发{ind}{random.choice(DOCS)}的通知\n"
            f"{dept}发〔{y}〕{random.randint(100,999)}号\n\n"
            f"各省、自治区、直辖市人民政府，国务院各部委、各直属机构：\n\n"
            f"为深入贯彻落实党中央、国务院关于{ind}发展的决策部署，加快推动{ind}高质量发展，"
            f"经国务院同意，现将《{ind}{random.choice(DOCS)}》印发给你们，请结合实际认真贯彻执行。\n\n"
            f"一、总体要求\n"
            f"以习近平新时代中国特色社会主义思想为指导，立足新发展阶段，推动{ind}实现质的有效提升和量的合理增长。\n\n"
            f"二、主要目标\n"
            f"到{y+random.randint(3,5)}年，{ind}综合实力显著增强。产业总产值年均增长{random.randint(8,20)}%以上。\n\n"
            f"三、重点任务\n"
            f"（一）加强技术创新。围绕{ind}关键环节，组织实施重大科技攻关。\n"
            f"（二）完善标准体系。加快制定{ind}相关国家标准和行业标准。\n"
            f"（三）强化要素保障。加大财政金融支持力度。\n\n"
            f"四、保障措施\n"
            f"（一）加强组织领导。建立{ind}发展协调机制。\n"
            f"（二）强化监督考核。将{ind}发展纳入考核评价体系。\n\n"
            f"{dept}\n{y}年{random.randint(1,12)}月{random.randint(1,28)}日"
        )
    elif tier == "B":
        return (
            f"{dept}调研{ind}发展情况\n"
            f"来源：{random.choice(SOURCES)} 时间：{y}-{random.randint(1,12):02d}-{random.randint(1,28):02d}\n\n"
            f"近日，{dept}负责同志赴{random.choice(PROVS)}调研{ind}发展情况。"
            f"调研组实地考察了多家{ind}企业，详细了解生产经营、技术创新、市场开拓等情况。\n\n"
            f"在企业生产车间，调研组成员认真察看生产流程，询问产品性能、市场销售等情况。"
            f"企业负责人介绍了近年来取得的进展。\n\n"
            f"调研组对企业取得的成绩给予充分肯定，指出{ind}发展势头良好，"
            f"要继续坚持创新驱动，不断提升核心竞争力。\n\n"
            f"调研组还与当地政府部门进行了座谈，就优化营商环境进行了深入交流。"
        )
    elif tier == "C":
        return (
            f"{random.choice(ORGS)}发布{ind}行业研究报告\n"
            f"来源：{random.choice(ORGS)} 时间：{y}-{random.randint(1,12):02d}-{random.randint(1,28):02d}\n\n"
            f"{random.choice(ORGS)}日前发布《{y}年{ind}行业发展研究报告》。"
            f"报告基于对全国{random.randint(50,500)}家{ind}企业的调研数据，"
            f"从市场规模、竞争格局、技术趋势等维度进行了深入分析。\n\n"
            f"报告显示，{y}年{ind}行业市场规模达到{random.randint(500,5000)}亿元，"
            f"同比增长{random.randint(5,30)}%。"
            f"报告指出，随着政策持续支持和下游需求增长，{ind}保持良好发展态势。\n\n"
            f"在竞争格局方面，报告分析认为行业集中度进一步提升，"
            f"头部企业凭借技术和渠道占据主要份额。\n\n"
            f"报告建议，{ind}企业应加大研发投入，关注技术迭代趋势。"
        )
    else:
        t = title or f"{ind}行业观察"
        return (
            f"{t}\n"
            f"来源：{random.choice(SOURCES)} 作者：记者{random.choice(['张某','李某','王某'])} "
            f"时间：{y}-{random.randint(1,12):02d}-{random.randint(1,28):02d}\n\n"
            f"近日，{ind}领域传出重大消息。据知情人士透露，某公司已完成新一轮融资，"
            f"估值超{random.randint(10,100)}亿元。\n\n"
            f"记者了解到，近年来{ind}行业发展迅速。"
            f"业内人士分析认为，行业仍面临{random.choice(['产能过剩','技术瓶颈','标准缺失'])}等挑战。\n\n"
            f"值得注意的是，多家上市公司纷纷布局{ind}赛道。"
            f"有观点认为，短期热度存在一定泡沫风险。\n\n"
            f"对此，记者致电相关负责人，截至发稿未获回复。\n\n"
            f"（本文仅供参考，不构成投资建议）"
        )


COC = (
    "你是一个信息源分级专家。请先逐步推理再返回JSON。"
    "A=政策原文(.gov.cn+/zcfb/),B=官方新闻/交易公告,C=协会/研究/解读,D=商业媒体/自媒体/过时。"
)

samples = []
real_used = 0
synth_used = 0

for r in balanced:
    info = r.get("url_info", {})
    label = r.get("label", {})
    tier = label.get("tier", "?")
    domain = info.get("domain", "")
    url = info.get("url", "")
    title = (info.get("title") or "").strip()
    cot = r.get("cot_reasoning", "")
    authority = r.get("scores", {}).get("authority_score", 0.8)
    reason = label.get("reason", "")
    conf = label.get("confidence", 0.9)

    input_text = f"域名: {domain}\nURL: {url}\n标题: {title}"

    ch = r.get("content", {}).get("content_head", "") or ""
    if is_good_content(ch):
        input_text += f"\n正文片段: {ch[:800]}"
        real_used += 1
    else:
        input_text += f"\n正文片段: {gen_body(tier, domain=domain, title=title)[:800]}"
        synth_used += 1

    output_text = (
        f"{cot}\n\n"
        f'{{"tier": "{tier}", "authority_score": {authority}, '
        f'"usage_note": "{reason}", "confidence": {conf}}}'
    )

    samples.append({
        "instruction": COC,
        "input": input_text,
        "output": output_text,
        "tier": tier,
        "domain": domain,
        "route_type": r.get("routing", {}).get("route_type", ""),
        "has_content": True,
    })

# Add extra C and D
for _ in range(60):
    cd = random.choice(["www.caam.org.cn", "www.chinapv.org.cn", "www.cas.cn", "www.iresearch.cn"])
    ti = f"{random.choice(ORGS)}：{random.choice(INDS)}{random.choice(['行业报告','趋势分析','发展展望'])}"
    body = gen_body("C", domain=cd, title=ti)
    samples.append({
        "instruction": COC,
        "input": f"域名: {cd}\nURL: https://{cd}/r/{random.randint(100,999)}.html\n标题: {ti}\n正文片段: {body[:800]}",
        "output": (
            f"Step 1: 域名 {cd} 不是.gov.cn\n"
            f"Step 2: 属于行业协会/研究机构\n"
            f"Step 3: 标题含研究报告用语\n"
            f"Step 4: 正文为研究报告格式\n"
            f"结论: 综合判断为 C 级(专业报告/解读)\n\n"
            f'{{"tier": "C", "authority_score": 0.5, "usage_note": "行业协会/研究机构——背景参考", "confidence": 0.85}}'
        ),
        "tier": "C", "domain": cd, "route_type": "llm_needed", "has_content": True,
    })

for _ in range(50):
    dd = random.choice(["www.sohu.com", "finance.sina.com.cn", "www.163.com", "www.thepaper.cn"])
    ti = f"{random.choice(INDS)}：{random.choice(['风口还是泡沫','万亿赛道爆发'])}"
    body = gen_body("D", domain=dd, title=ti)
    samples.append({
        "instruction": COC,
        "input": f"域名: {dd}\nURL: https://{dd}/a/{random.randint(100000,999999)}.html\n标题: {ti}\n正文片段: {body[:800]}",
        "output": (
            f"Step 1: 域名 {dd} 是商业媒体\n"
            f"Step 2: 不在已知权威清单中\n"
            f"Step 3: 标题为自媒体风格\n"
            f"Step 4: 正文含媒体标记（知情人士/记者/免责声明）\n"
            f"结论: 综合判断为 D 级(商业媒体/低可信度)\n\n"
            f'{{"tier": "D", "authority_score": 0.25, "usage_note": "商业媒体——不作为证据来源", "confidence": 0.95}}'
        ),
        "tier": "D", "domain": dd, "route_type": "rule_direct", "has_content": True,
    })

random.shuffle(samples)

# Split
train, val, test = [], [], []
for t in "ABCD":
    ts = [s for s in samples if s["tier"] == t]
    random.shuffle(ts)
    n = len(ts)
    train.extend(ts[:int(n * 0.7)])
    val.extend(ts[int(n * 0.7):int(n * 0.85)])
    test.extend(ts[int(n * 0.85):])

random.shuffle(train); random.shuffle(val); random.shuffle(test)

for fname, data in [
    ("source_tier_train_v2.jsonl", train),
    ("source_tier_val_v2.jsonl", val),
    ("source_tier_test_v2.jsonl", test),
]:
    with open(DATA_DIR / fname, "w", encoding="utf-8") as f:
        for s in data:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

print(f"\n真实正文: {real_used} | 合成正文: {synth_used} | 新增C+D: 110")
print(f"总计: {len(samples)} samples, 100% 有正文\n")
for name, data in [("Train", train), ("Val", val), ("Test", test)]:
    tiers = Counter(s["tier"] for s in data)
    print(f"  {name}: {len(data)} ({dict(tiers)})")
