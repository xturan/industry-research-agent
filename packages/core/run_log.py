from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from packages.core.config import get_settings

LOGGER = logging.getLogger(__name__)

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11 fallback
    UTC = timezone(timedelta(0))

SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "password",
    "reasoning",
    "secret",
    "token",
)

TEXT_HEAVY_KEY_PARTS = (
    "body",
    "chunk_text",
    "content_text",
    "executive_summary",
    "inline_text",
    "markdown",
    "memo",
    "quote_text",
    "rationale",
    "summary",
    "support_text",
)


def compact_value(
    value: Any,
    *,
    max_chars: int,
    max_items: int,
    depth: int = 0,
    max_depth: int = 3,
) -> Any:
    """Return a compact JSON-safe summary for runtime audit logs."""

    if depth > max_depth:
        return {"_truncated": "max_depth"}
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, BaseModel):
        return compact_value(
            value.model_dump(mode="json"),
            max_chars=max_chars,
            max_items=max_items,
            depth=depth,
            max_depth=max_depth,
        )
    if isinstance(value, str):
        if len(value) <= max_chars:
            return value
        return f"{value[:max_chars]}...[truncated chars={len(value)}]"
    if isinstance(value, bytes):
        return f"<bytes len={len(value)}>"
    if isinstance(value, dict):
        compacted: dict[str, Any] = {}
        items = list(value.items())
        for raw_key, raw_item in items[:max_items]:
            key = str(raw_key)
            key_lower = key.lower()
            if any(part in key_lower for part in SENSITIVE_KEY_PARTS):
                compacted[key] = "<redacted>"
            elif isinstance(raw_item, str) and any(
                part in key_lower for part in TEXT_HEAVY_KEY_PARTS
            ):
                preview_limit = min(max_chars, 80)
                compacted[key] = {
                    "chars": len(raw_item),
                    "preview": (
                        raw_item
                        if len(raw_item) <= preview_limit
                        else f"{raw_item[:preview_limit]}...[truncated chars={len(raw_item)}]"
                    ),
                }
            else:
                compacted[key] = compact_value(
                    raw_item,
                    max_chars=max_chars,
                    max_items=max_items,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
        if len(items) > max_items:
            compacted["_truncated_items"] = len(items) - max_items
        return compacted
    if isinstance(value, list | tuple | set):
        sequence = list(value)
        compacted_items = [
            compact_value(
                item,
                max_chars=max_chars,
                max_items=max_items,
                depth=depth + 1,
                max_depth=max_depth,
            )
            for item in sequence[:max_items]
        ]
        if len(sequence) > max_items:
            compacted_items.append({"_truncated_items": len(sequence) - max_items})
        return compacted_items
    return compact_value(
        str(value),
        max_chars=max_chars,
        max_items=max_items,
        depth=depth + 1,
        max_depth=max_depth,
    )


def slugify_task_name(task_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", task_name.strip().lower()).strip("-")
    return (slug or "task")[:80]


class CompactRunLogger:
    """Side-effect-only JSONL logger for compact execution trace summaries."""

    def __init__(
        self,
        *,
        task_name: str,
        run_id: int | str | None = None,
        base_dir: str | Path | None = None,
        enabled: bool | None = None,
        max_value_chars: int | None = None,
        max_items: int | None = None,
        started_at: datetime | None = None,
    ) -> None:
        settings = get_settings()
        self.task_name = task_name
        self.run_id = run_id
        self.enabled = settings.system_run_log_enabled if enabled is None else enabled
        self.max_value_chars = max_value_chars or settings.system_run_log_max_value_chars
        self.max_items = max_items or settings.system_run_log_max_items
        self.started_at = started_at or datetime.now(UTC)
        self._path: Path | None = None
        if self.enabled:
            root = Path(base_dir or settings.system_run_log_dir)
            timestamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
            run_part = f"_run-{run_id}" if run_id is not None else f"_{uuid4().hex[:8]}"
            self._path = root / f"{timestamp}_{slugify_task_name(task_name)}{run_part}.jsonl"

    @property
    def path(self) -> Path | None:
        return self._path

    def record(
        self,
        event: str,
        *,
        input_summary: Any | None = None,
        decision_summary: str | list[str] | None = None,
        output_summary: Any | None = None,
        error: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled or self._path is None:
            return
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "event": event,
            "task": self.task_name,
        }
        if self.run_id is not None:
            payload["run_id"] = self.run_id
        if input_summary is not None:
            payload["input"] = self._compact(input_summary)
        if decision_summary is not None:
            payload["decision"] = self._compact(decision_summary)
        if output_summary is not None:
            payload["output"] = self._compact(output_summary)
        if error is not None:
            payload["error"] = self._compact(error)
        if meta:
            payload["meta"] = self._compact(meta)
        self._append(payload)

    def start(self, *, input_summary: Any, decision_summary: str | list[str]) -> None:
        self.record(
            "start",
            input_summary=input_summary,
            decision_summary=decision_summary,
            meta={"log_path": str(self._path) if self._path is not None else None},
        )

    def step(
        self,
        *,
        step_name: str,
        agent_name: str | None,
        input_summary: Any | None,
        output_summary: Any | None = None,
        status: str = "succeeded",
        error: str | None = None,
    ) -> None:
        self.record(
            "step",
            input_summary=input_summary,
            decision_summary=f"{status}: {step_name} via {agent_name or 'system'}",
            output_summary=output_summary,
            error=error,
            meta={"step_name": step_name, "agent_name": agent_name, "status": status},
        )

    def finish(self, *, status: str, output_summary: Any) -> None:
        self.record(
            "finish",
            decision_summary=f"finish task with status={status}",
            output_summary=output_summary,
            meta={"status": status},
        )

    def _compact(self, value: Any) -> Any:
        return compact_value(
            value,
            max_chars=max(40, self.max_value_chars),
            max_items=max(1, self.max_items),
        )

    def _append(self, payload: dict[str, Any]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)  # type: ignore[union-attr]
            with self._path.open("a", encoding="utf-8") as handle:  # type: ignore[union-attr]
                handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
                handle.write("\n")
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("system run log write failed: %s", exc)
