"""
Local LLM provider via Ollama for free, offline inference.
Replaces DeepSeek API calls for lightweight tasks (tiering, caliber expansion).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any


class OllamaProvider:
    """Local LLM inference via Ollama. No API key, no network, no cost."""

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        timeout_seconds: int = 120,
    ) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        ollama_paths = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
            os.path.join(os.environ.get("ProgramFiles", ""), "Ollama", "ollama.exe"),
            "ollama",
        ]
        self._ollama_bin = ""
        for path in ollama_paths:
            if os.path.exists(path) or path == "ollama":
                self._ollama_bin = path
                break

    @property
    def available(self) -> bool:
        return bool(self._ollama_bin)

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Generate structured JSON output from local model via HTTP API."""
        if not self.available:
            return {"json_data": {}, "content_text": "", "error": "ollama_not_found"}

        import urllib.request

        payload = json.dumps({
            "model": self.model,
            "prompt": f"{system_prompt}\n\n{user_prompt}\n\nReturn ONLY valid JSON.",
            "stream": False,
            "options": {"temperature": temperature},
            "format": "json",
        }).encode("utf-8")

        try:
            started = time.perf_counter()
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            elapsed_ms = round((time.perf_counter() - started) * 1000)

            content = data.get("response", "").strip()
            json_data = self._parse_json(content)

            return {
                "json_data": json_data,
                "content_text": content,
                "model": self.model,
                "response_ms": elapsed_ms,
            }
        except Exception as exc:
            return {"json_data": {}, "content_text": "", "error": str(exc)}

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        """Extract JSON from model output (may have markdown fences or ANSI codes)."""
        import re

        # Strip ANSI escape sequences that Ollama terminal output may include
        content = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", content)
        content = content.strip()

        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if fence:
            try:
                return json.loads(fence.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding JSON object in text
        brace = re.search(r"\{.*\}", content, re.DOTALL)
        if brace:
            try:
                return json.loads(brace.group(0))
            except json.JSONDecodeError:
                pass

        return {}


# ── Convenience ──

_ollama: OllamaProvider | None = None


def get_ollama() -> OllamaProvider:
    global _ollama
    if _ollama is None:
        _ollama = OllamaProvider()
    return _ollama
