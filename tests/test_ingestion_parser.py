from packages.db.models import SourceType
from packages.ingestion.parser import parse_source
from packages.ingestion.schemas import RawSourceData


def test_markdown_parser_extracts_sections_and_title() -> None:
    content = (
        b"# Grid Storage Update\n\n"
        b"## Supply\n"
        b"Refining capacity remains constrained.\n\n"
        b"## Demand\n"
        b"Utility-scale projects continue to expand."
    )
    raw = RawSourceData(
        source_uri="file:///tmp/sample.md",
        source_name="sample.md",
        source_type=SourceType.REPORT,
        content_bytes=content,
        media_type="text/markdown",
        file_extension=".md",
    )

    parsed = parse_source(raw)

    assert parsed.title == "Grid Storage Update"
    assert len(parsed.sections) == 2
    assert parsed.sections[0].section_name == "Supply"
    assert "Refining capacity" in parsed.sections[0].text
