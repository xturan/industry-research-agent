"""构建维度搜索词（一次 LLM 调用）—— 调试用，不改生产代码。

用户要求（2026-08-11）：基于 query，针对每个维度和对应关键词，用一次 LLM
调用构建搜索词，覆盖全面。本脚本输出 14 维度的搜索词供审阅。

用法：
    python scripts/build_dimension_search_terms.py "低空经济 中标公告"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from packages.research_harness import research_taxonomy as rt
from packages.research_harness.tooling.llm_agents import call_tooling_json


def _escape(text: str) -> str:
    return str(text or "").replace("\\", "\\\\").replace('"', '\\"')


def build_dimension_prompt(query: str) -> str:
    """构造一次 LLM 调用的 prompt：query + 14 维度（name + search_key_fields + primary family）。"""
    # 把 query 拆成核心成分，强制搜索词体现 query 特点
    tokens = [t.strip() for t in query.replace(" ", " ").split() if t.strip()]
    core = tokens[0] if tokens else query  # 主题词，如"低空经济"
    intent = " ".join(tokens[1:]) if len(tokens) > 1 else ""  # 意图词，如"中标公告"
    intent_hint = f"（本 query 的核心意图是「{intent}」，必须体现在搜索词中）" if intent else ""
    lines: list[str] = [
        f"研究主题（query）: {query}",
        f"query 主题词: {core}",
        f"query 意图词: {intent or '（无）'}{intent_hint}",
        "",
        "请为以下 14 个研究维度各生成 2-3 条中文搜索词。",
    ]
    lines.append("搜索词要求：")
    lines.append(f"1. 每条搜索词必须包含【query 主题「{core}」】；但不要每条都以 query 意图「{intent}」开头——"
                 f"混搭两种风格：")
    lines.append(f"   a. 从 query 意图切入：如「{core} {intent} 产业链环节」「{core} 中标企业 市场份额」"
                 f"（体现 query 研究角度）")
    lines.append(f"   b. 从维度本身切入：如「{core} 产业链 上下游 代表企业」「{core} 安全 事故 监管处罚」"
                 f"（恢复维度天然检索面，不绑定 query 意图）")
    lines.append("2. 每条搜索词覆盖该维度的核心检索字段（产业链环节/竞争格局/应用场景/毛利率/"
                 "订单/投资金额/风险/事故等），让搜索词精准命中该维度")
    lines.append("3. 每条 = query主题 + 维度核心词 + 数据来源类型（政策文件/统计公报/招标公告/交易所披露/行业报告）")
    lines.append("4. 不同维度搜索词要有区分度；同一维度内 a/b 两种风格混搭，避免全部同质")
    lines.append("5. 建议每维度 2 条从 query 意图切入 + 1 条从维度本身切入")
    lines.append("")
    for dim_id, meta in rt.DIMENSIONS.items():
        family = rt.DIMENSION_PRIMARY_FAMILY.get(dim_id, "")
        lines.append(f"- dimension_id: {dim_id}")
        lines.append(f"  维度名: {meta['label']}")
        lines.append(f"  要检索的关键字段: {'、'.join(meta['search_key_fields'][:8])}")
        lines.append(f"  首选来源类型: {family}")
        lines.append("")
    lines.append("只输出 JSON，不要其他文字，格式：")
    lines.append('{"dimensions": {"industry_scope": ["搜索词1", "搜索词2", "搜索词3"], ...}}')
    return "\n".join(lines)


def fallback_terms(query: str, dim_id: str, meta: dict) -> list[str]:
    """确定性兜底：search_key_fields 前 2 个 + 维度中文名。"""
    terms: list[str] = []
    for field in meta["search_key_fields"][:2]:
        terms.append(f"{query} {field}".strip())
    if not terms:
        terms.append(f"{query} {meta['label']}".strip())
    return terms[:3]


def main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else "低空经济 中标公告"
    print(f"=== 构建维度搜索词（query: {query}）===\n")

    prompt = build_dimension_prompt(query)
    print("--- 一次 LLM 调用 ---")
    try:
        res = call_tooling_json(
            system_prompt="你是产业研究检索词生成器。为每个研究维度生成精准、可执行的中文搜索词，只输出 JSON。",
            user_prompt=prompt,
            enable_thinking=False,
            max_tokens=4000,
            task_type="dimension_search_terms",
        )
        payload = res.payload if res else None
        print(f"llm_mode: {res.metadata.get('llm_mode') if res else 'N/A'} | "
              f"llm_reason: {res.metadata.get('llm_reason') if res else 'N/A'}")
    except Exception as exc:
        print(f"LLM 调用异常: {type(exc).__name__}: {exc}")
        payload = None

    results: dict[str, list[str]] = {}
    if isinstance(payload, dict) and isinstance(payload.get("dimensions"), dict):
        raw = payload["dimensions"]
        for dim_id, meta in rt.DIMENSIONS.items():
            got = [str(x) for x in (raw.get(dim_id) or []) if str(x).strip()]
            results[dim_id] = got[:3] or fallback_terms(query, dim_id, meta)
    else:
        print("!! LLM 未返回有效 JSON，回退确定性搜索词")
        for dim_id, meta in rt.DIMENSIONS.items():
            results[dim_id] = fallback_terms(query, dim_id, meta)

    # 输出
    print("\n=== 14 维度搜索词 ===")
    for dim_id, meta in rt.DIMENSIONS.items():
        mark = " [base]" if meta["base_or_conditional"] == "base" else " [cond]"
        print(f"\n{dim_id}{mark} {meta['label']}")
        for term in results[dim_id]:
            print(f"  - {term}")

    out = Path("data/reports") / f"dimension_search_terms_{query[:20].replace(' ', '_')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"query": query, "dimensions": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== 已保存: {out} ===")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
