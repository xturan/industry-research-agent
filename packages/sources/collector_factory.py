from __future__ import annotations

from packages.sources.collectors import BaseCollector, HtmlListDetailCollector
from packages.sources.schemas import SourceProfile


class CollectorExecutorFactory:
    def __init__(self) -> None:
        self._collectors: dict[str, BaseCollector] = {
            "html_list_detail": HtmlListDetailCollector(),
        }

    def get_collector(self, profile: SourceProfile) -> BaseCollector | None:
        collector_type = profile.collector_type
        if collector_type is None:
            return None
        return self._collectors.get(collector_type.value)
