from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from packages.db.models import SourceType
from packages.ingestion.schemas import RawSourceData

DEFAULT_USER_AGENT = "invest-agent-ingestion/0.1"


def _extension_from_name_or_media_type(name: str, media_type: str | None) -> str:
    suffix = Path(name).suffix.lower()
    if suffix:
        return suffix
    if media_type == "text/markdown":
        return ".md"
    if media_type == "text/html":
        return ".html"
    if media_type == "text/plain":
        return ".txt"
    return ".bin"


def fetch_local_file(
    file_path: str | Path, source_type: SourceType = SourceType.OTHER
) -> RawSourceData:
    path = Path(file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Local file does not exist: {path}")
    bytes_data = path.read_bytes()
    media_type = "text/plain"
    if path.suffix.lower() in {".html", ".htm"}:
        media_type = "text/html"
    elif path.suffix.lower() == ".md":
        media_type = "text/markdown"
    return RawSourceData(
        source_uri=path.as_uri(),
        source_name=path.name,
        source_type=source_type,
        content_bytes=bytes_data,
        media_type=media_type,
        file_extension=path.suffix.lower() or ".txt",
    )


def fetch_url(
    url: str,
    *,
    source_type: SourceType = SourceType.ARTICLE,
    timeout_seconds: int = 20,
) -> RawSourceData:
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec: B310
        content_bytes = response.read()
        media_type = response.headers.get_content_type()
        final_url = response.geturl()

    parsed = urlparse(final_url)
    source_name = Path(parsed.path).name or "index.html"
    extension = _extension_from_name_or_media_type(source_name, media_type)
    if not Path(source_name).suffix:
        source_name = f"{source_name}{extension}"

    return RawSourceData(
        source_uri=final_url,
        source_name=source_name,
        source_type=source_type,
        content_bytes=content_bytes,
        media_type=media_type,
        file_extension=extension,
    )
