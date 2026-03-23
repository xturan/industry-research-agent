from packages.ingestion.chunker import chunk_parsed_content
from packages.ingestion.schemas import ParsedContent, ParsedSection


def test_chunker_is_deterministic_and_preserves_section_name() -> None:
    section = ParsedSection(
        section_name="Market Outlook",
        locator="heading:0",
        text=(
            "Paragraph one about supply pressure.\n\n"
            "Paragraph two about contract pricing.\n\n"
            "Paragraph three about margin effects."
        ),
    )
    parsed = ParsedContent(
        title="Outlook",
        text=section.text,
        source_uri="file:///tmp/outlook.md",
        sections=[section],
    )

    first = chunk_parsed_content(parsed, max_chars=80)
    second = chunk_parsed_content(parsed, max_chars=80)

    assert len(first) >= 2
    assert [chunk.chunk_index for chunk in first] == list(range(len(first)))
    assert [chunk.section_name for chunk in first] == ["Market Outlook"] * len(first)
    assert [chunk.text for chunk in first] == [chunk.text for chunk in second]
