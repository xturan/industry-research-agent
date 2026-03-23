from __future__ import annotations

from packages.agents.schemas import ResearchAnalysisResult
from packages.content.schemas import ContentFormat, GeneratedContentDraft
from packages.content.templates import build_platform_disclaimer


class DeterministicContentGenerator:
    """Deterministic content shaping from structured research memo."""

    # TODO: Introduce richer brand/style packs with configurable voice presets.
    # TODO: Add title A/B generation policy once eval metrics are available.

    def generate(
        self,
        *,
        content_format: ContentFormat,
        research: ResearchAnalysisResult,
        style_hints: list[str],
        title_preference: str | None,
    ) -> GeneratedContentDraft:
        low_confidence = research.insufficient_evidence or research.confidence_score < 0.5
        disclaimer = build_platform_disclaimer(content_format, low_confidence)
        key_points = self._key_points(research)

        if content_format == ContentFormat.WECHAT_ARTICLE:
            title = title_preference or f"{research.query}：结构化研究解读（公众号版）"
            body = self._wechat_article(title, research, key_points, disclaimer, style_hints)
        elif content_format == ContentFormat.XIAOHONGSHU_POST:
            title = title_preference or f"3分钟看懂：{research.query}"
            body = self._xiaohongshu_post(title, research, key_points, disclaimer, style_hints)
        else:
            title = title_preference or f"{research.query} 口播脚本"
            body = self._douyin_script(title, research, key_points, disclaimer, style_hints)

        return GeneratedContentDraft(
            content_format=content_format,
            title=title,
            body_text=body,
            key_points=key_points,
            disclaimer=disclaimer,
            platform_meta={
                "style_hints": style_hints,
                "confidence_score": research.confidence_score,
                "insufficient_evidence": research.insufficient_evidence,
                "source_research_run_id": research.run_id,
            },
        )

    def _key_points(self, research: ResearchAnalysisResult) -> list[str]:
        points: list[str] = []
        for thesis in research.theses[:3]:
            points.append(f"观点：{thesis.title}")
        for objection in research.objections[:2]:
            points.append(f"反方：{objection.objection}")
        for risk in research.risks[:2]:
            points.append(f"风险：{risk.risk_title}")
        if not points:
            points.append("当前暂无足够证据形成高置信内容。")
        return points

    def _wechat_article(
        self,
        title: str,
        research: ResearchAnalysisResult,
        key_points: list[str],
        disclaimer: str,
        style_hints: list[str],
    ) -> str:
        thesis_blocks: list[str] = []
        for index, item in enumerate(research.theses[:3], start=1):
            refs = "; ".join(item.evidence_refs)
            thesis_blocks.append(f"### 观点{index}\n- {item.summary}\n- 证据引用：{refs}")
        theses = "\n".join(thesis_blocks) or "### 观点\n- 当前证据有限，优先补充资料。"

        risks = (
            "\n".join([f"- {item.risk_description}" for item in research.risks[:3]])
            or "- 暂无高质量风险证据。"
        )
        objections = (
            "\n".join([f"- {item.objection}" for item in research.objections[:3]])
            or "- 暂无可用反方材料。"
        )
        hint_line = (
            f"风格提示：{', '.join(style_hints)}" if style_hints else "风格提示：理性、结构化"
        )
        return (
            f"# {title}\n\n"
            f"## 导语\n{research.final_memo.executive_summary}\n\n"
            f"## 核心结论\n{theses}\n\n"
            f"## 反方挑战\n{objections}\n\n"
            f"## 关键风险\n{risks}\n\n"
            f"## 关键信号清单\n"
            + "\n".join([f"- {point}" for point in key_points])
            + f"\n\n## 结语\n{hint_line}\n\n## 风险与合规\n{disclaimer}\n"
        )

    def _xiaohongshu_post(
        self,
        title: str,
        research: ResearchAnalysisResult,
        key_points: list[str],
        disclaimer: str,
        style_hints: list[str],
    ) -> str:
        hook = f"先说结论：关于「{research.query}」这条线，最强信号和最大不确定性同时存在。"
        takeaways = "\n".join([f"- {point}" for point in key_points[:5]])
        next_steps = "\n".join(
            [f"- {question}" for question in research.final_memo.suggested_next_questions[:3]]
        )
        hint_line = f"风格：{', '.join(style_hints)}" if style_hints else "风格：轻量、观点清晰"
        return (
            f"# {title}\n\n"
            f"{hook}\n\n"
            f"## 快速看点\n{takeaways}\n\n"
            f"## 反方视角\n"
            + "\n".join([f"- {item.objection}" for item in research.objections[:2]])
            + "\n\n## 后续要追\n"
            f"{next_steps}\n\n"
            f"{hint_line}\n\n"
            f"{disclaimer}\n"
        )

    def _douyin_script(
        self,
        title: str,
        research: ResearchAnalysisResult,
        key_points: list[str],
        disclaimer: str,
        style_hints: list[str],
    ) -> str:
        beats = key_points[:5]
        while len(beats) < 3:
            beats.append("补充证据后再做结论升级。")
        beat_lines = "\n".join([f"- 第{i + 1}点：{point}" for i, point in enumerate(beats)])
        tone = ", ".join(style_hints) if style_hints else "语速稳、观点克制"
        return (
            f"【标题】{title}\n"
            f"【开场钩子】今天用一分钟讲清楚：{research.query} 到底有哪些可验证信号。\n"
            f"【主体节奏】\n{beat_lines}\n"
            f"【收尾】如果你在跟踪这条产业线，下一步重点看证据更新而不是情绪。\n"
            f"【口播风格】{tone}\n"
            f"【风险提示】{disclaimer}\n"
        )
