from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from packages.ingestion.schemas import RawSourceData, StoredRawSource


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())
    return cleaned.strip("-").lower() or "source"


class LocalRawStorage:
    """Local filesystem storage adapter for raw ingestion sources."""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)

    def persist(self, source: RawSourceData) -> StoredRawSource:
        digest = hashlib.sha256(source.content_bytes).hexdigest()
        extension = source.file_extension or ".bin"
        safe_name = _slugify(Path(source.source_name).stem)
        day_partition = datetime.now(timezone.utc).strftime("%Y%m%d")
        relative_path = Path(day_partition) / f"{safe_name}-{digest[:12]}{extension}"
        absolute_path = self.base_dir / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        if not absolute_path.exists():
            absolute_path.write_bytes(source.content_bytes)

        return StoredRawSource(
            storage_path=str(absolute_path.as_posix()),
            content_hash=digest,
            byte_size=len(source.content_bytes),
        )
