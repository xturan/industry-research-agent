from __future__ import annotations

from packages.registry.schemas import (
    PolicyEntry,
    RegistryPoliciesResponse,
    RegistryTemplatesResponse,
    StylePackEntry,
    TemplateEntry,
)

DEFAULT_DISCLAIMER_TEXT = (
    "This content is for industry research and intelligence sharing only, "
    "and does not constitute investment advice."
)


class RegistryService:
    # TODO: Externalize registry to versioned config files and support environment overlays.
    # TODO: Add template/policy experiment tags for A/B testing hooks.

    def list_templates(self) -> RegistryTemplatesResponse:
        templates = [
            TemplateEntry(
                template_id="wechat_article_v1",
                version="1.0.0",
                content_format="wechat_article",
                description="Long-form WeChat article template with evidence/risk sections.",
                sections=[
                    "intro",
                    "key_theses",
                    "counterarguments",
                    "risks",
                    "conclusion",
                    "disclaimer",
                ],
                style_pack="balanced_professional_v1",
            ),
            TemplateEntry(
                template_id="xiaohongshu_post_v1",
                version="1.0.0",
                content_format="xiaohongshu_post",
                description="Short punchy post template with hook and takeaways.",
                sections=["hook", "quick_points", "next_questions", "disclaimer"],
                style_pack="social_lightweight_v1",
            ),
            TemplateEntry(
                template_id="douyin_script_v1",
                version="1.0.0",
                content_format="douyin_script",
                description="Spoken script template with opening beats and CTA.",
                sections=["opening_hook", "beats", "closing", "disclaimer"],
                style_pack="spoken_concise_v1",
            ),
        ]
        return RegistryTemplatesResponse(templates=templates)

    def list_policies(self) -> RegistryPoliciesResponse:
        policies = [
            PolicyEntry(
                policy_id="content_guardrail_v1",
                version="1.0.0",
                description=(
                    "Content guardrails for recommendation language and disclaimer presence."
                ),
                rules=[
                    "flag explicit buy/sell recommendation phrases",
                    "require disclaimer marker in generated content",
                    "keep positioning as research/intelligence assistance",
                ],
                disclaimer_text=DEFAULT_DISCLAIMER_TEXT,
            ),
            PolicyEntry(
                policy_id="research_grounding_v1",
                version="1.0.0",
                description="Research memo grounding and confidence guardrails.",
                rules=[
                    "flag thesis items without evidence refs",
                    "insufficient-evidence flows must not return high confidence",
                    "preserve risk and gap reporting in final memo",
                ],
            ),
            PolicyEntry(
                policy_id="delivery_policy_gate_v1",
                version="1.0.0",
                description="Optional delivery pre-dispatch policy gate.",
                rules=[
                    "if enabled, block dispatch for content assets failing policy checks",
                    "persist policy warnings in delivery metadata when not blocking",
                ],
            ),
        ]
        return RegistryPoliciesResponse(policies=policies)

    def list_style_packs(self) -> list[StylePackEntry]:
        return [
            StylePackEntry(
                style_pack_id="balanced_professional_v1",
                description="Structured and neutral professional style.",
                tone_keywords=["structured", "balanced", "evidence-first"],
            ),
            StylePackEntry(
                style_pack_id="social_lightweight_v1",
                description="Light social style for short posts.",
                tone_keywords=["concise", "friendly", "insightful"],
            ),
            StylePackEntry(
                style_pack_id="spoken_concise_v1",
                description="Short spoken rhythm for script generation.",
                tone_keywords=["spoken", "clear", "quick-beat"],
            ),
        ]
