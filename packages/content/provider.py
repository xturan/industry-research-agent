from __future__ import annotations

from dataclasses import dataclass

from packages.content.generators import DeterministicContentGenerator
from packages.content.schemas import ContentGenerationMode


@dataclass(slots=True)
class ContentProviderResolution:
    generator: DeterministicContentGenerator
    resolved_mode: ContentGenerationMode
    notes: list[str]


def resolve_content_provider(mode: ContentGenerationMode) -> ContentProviderResolution:
    if mode == ContentGenerationMode.MOCK:
        return ContentProviderResolution(
            generator=DeterministicContentGenerator(),
            resolved_mode=ContentGenerationMode.MOCK,
            notes=[],
        )

    # TODO: Integrate real LLM content provider with prompt/policy packs.
    return ContentProviderResolution(
        generator=DeterministicContentGenerator(),
        resolved_mode=ContentGenerationMode.MOCK,
        notes=["TODO: llm mode requested but not implemented, fallback to deterministic mock."],
    )
