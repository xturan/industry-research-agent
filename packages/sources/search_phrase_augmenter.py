from __future__ import annotations

from typing import Any

from packages.providers import ProviderConfigError
from packages.sources.query_decomposition import QueryDecompositionTask

_AUGMENT_PROMPT = (
    "You are helping improve search quality for Chinese government and industry data queries. "
    "Given a search task, suggest 2-3 alternative search phrases that would find better results "
    "on Chinese government websites, public resource trading platforms, "
    "or official data portals.\n\n"
    "Rules:\n"
    "- Generate concise, keyword-rich Chinese search phrases\n"
    "- Include specific domain terms (e.g., 招标公告, 中标结果, 政府采购, 公共资源交易)\n"
    "- Preserve region names if present\n"
    "- Do NOT repeat the original phrases\n"
    "- Return JSON: {\"phrases\": [\"phrase1\", \"phrase2\", ...]}\n"
    "- Return empty list if the original phrases are already sufficient"
)

_DETERMINISTIC_PROCUREMENT_EXPANSIONS: dict[str, list[str]] = {
    "招标": ["招标公告", "中标候选人公示", "中标结果公告"],
    "中标": ["中标候选人公示", "中标结果公告", "成交公告"],
    "采购": ["政府采购意向", "采购公告", "采购结果公示"],
    "公共资源": ["公共资源交易公告", "国有产权交易", "土地出让公告"],
    "tender": ["tender notice", "bid winning announcement", "procurement notice"],
    "procurement": ["procurement notice", "government procurement", "public tender"],
    "项目": ["重点项目清单", "项目审批", "项目备案公示"],
    "产业": ["产业规划", "产业政策", "产业链分析"],
    "政策": ["政策通知", "法规文件", "实施意见"],
}


def augment_search_phrases(
    task: QueryDecompositionTask,
    *,
    deepseek_client: Any | None = None,
) -> list[str]:
    """Augment search phrases with additional terms for better search coverage.

    Tries LLM augmentation first (if client available), falls back to
    deterministic keyword-based expansion.
    """
    if deepseek_client is not None:
        try:
            return _llm_augment(task, deepseek_client)
        except Exception:
            pass  # Fall through to deterministic
    return _deterministic_augment(task)


def _llm_augment(
    task: QueryDecompositionTask,
    client: Any,
) -> list[str]:
    phrases_text = "\n".join(f"- {p}" for p in task.search_phrases)
    user_prompt = (
        f"Original search phrases:\n{phrases_text}\n\n"
        f"Search goal: {task.evidence_goal}\n"
        f"Source cluster: {task.source_cluster}\n"
        f"Task family: {task.task_family}"
    )
    try:
        response = client.generate_json(
            system_prompt=_AUGMENT_PROMPT,
            user_prompt=user_prompt,
            model=None,
            enable_thinking=False,
        )
        data = response.json_data
        if isinstance(data, dict) and isinstance(data.get("phrases"), list):
            new_phrases = [
                str(p).strip() for p in data["phrases"]
                if str(p).strip() and str(p).strip() not in set(task.search_phrases)
            ]
            return new_phrases[:3]
    except (ProviderConfigError, Exception):
        pass
    return []


def _deterministic_augment(task: QueryDecompositionTask) -> list[str]:
    """Generate additional search phrases by keyword expansion."""
    combined = " ".join([*task.search_phrases, task.evidence_goal]).lower()
    additional: list[str] = []

    for keyword, expansions in _DETERMINISTIC_PROCUREMENT_EXPANSIONS.items():
        if keyword.lower() in combined:
            for expansion in expansions:
                if expansion.lower() not in combined and expansion not in additional:
                    additional.append(expansion)

    # Add region-qualified versions
    known_regions = [
        "安徽", "合肥", "广东", "深圳", "江苏", "苏州", "常州",
        "浙江", "杭州", "上海", "陕西", "西安", "四川", "成都",
        "湖北", "武汉", "海南", "内蒙古", "河南", "福建", "山东",
        "肥西", "神木", "若羌",
    ]
    found_regions: list[str] = []
    for phrase in task.search_phrases:
        for region in known_regions:
            if region in phrase and region not in found_regions:
                found_regions.append(region)

    for region in found_regions[:2]:  # Max 2 regions to avoid phrase bloat
        for keyword in ("招标", "政府采购", "公共资源交易"):
            if keyword.lower() in combined:
                candidate = f"{region} {keyword}"
                if candidate not in additional and candidate not in task.search_phrases:
                    additional.append(candidate)

    return additional[:3]
