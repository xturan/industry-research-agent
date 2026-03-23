from __future__ import annotations

from packages.content.schemas import ContentFormat

BASE_DISCLAIMER = (
    "免责声明：本文仅用于产业研究与信息交流，不构成任何证券买卖建议或投资承诺。"
)

LOW_CONFIDENCE_DISCLAIMER = (
    "风险提示：当前证据强度偏弱，结论仅供研究讨论，后续需补充更多一手资料验证。"
)


def build_platform_disclaimer(content_format: ContentFormat, low_confidence: bool) -> str:
    if content_format == ContentFormat.DOUYIN_SCRIPT and low_confidence:
        return (
            "口播风险提示：证据仍不足，以下观点仅供行业研究参考，不构成投资建议。"
        )
    if low_confidence:
        return f"{LOW_CONFIDENCE_DISCLAIMER}\n{BASE_DISCLAIMER}"
    return BASE_DISCLAIMER
