from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]{2,}")
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}")


def build_deterministic_embedding(
    text: str,
    *,
    dimensions: int = 16,
) -> list[float]:
    vector = [0.0] * max(dimensions, 1)
    tokens = _tokenize(text)
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.sha1(token.encode("utf-8")).digest()
        slot = int.from_bytes(digest[:2], "big") % len(vector)
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        magnitude = 1.0 + (digest[3] / 255.0)
        vector[slot] += sign * magnitude
    return _normalize(vector)


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_list = [float(value) for value in left]
    right_list = [float(value) for value in right]
    if not left_list or not right_list or len(left_list) != len(right_list):
        return 0.0
    numerator = sum(a * b for a, b in zip(left_list, right_list, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left_list))
    right_norm = math.sqrt(sum(b * b for b in right_list))
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 0.0:
        return [0.0 for _ in values]
    return [value / norm for value in values]


def embed_text(
    text: str,
    *,
    endpoint: str | None = None,
    model: str | None = None,
    dimensions: int = 1024,
    timeout: float = 30.0,
) -> list[float] | None:
    """Real embedding via a vLLM OpenAI-compatible /embeddings endpoint.

    Returns None on any failure so callers can fall back to the deterministic
    hash embedding. Endpoint/model resolve from settings when not passed."""
    import requests

    if endpoint is None or model is None:
        from packages.core.config import get_settings

        settings = get_settings()
        endpoint = endpoint or settings.embedding_endpoint
        model = model or settings.embedding_model
        dimensions = dimensions or settings.embedding_dimensions
    if not endpoint or not model:
        return None
    try:
        resp = requests.post(
            endpoint,
            json={"model": model, "input": str(text or "")[:2000]},
            timeout=timeout,
        )
        data = resp.json()
        vector = data.get("data", [{}])[0].get("embedding")
        if not isinstance(vector, list) or not vector:
            return None
        floats = [float(value) for value in vector[:dimensions]]
        if not floats:
            return None
        return _normalize(floats)
    except Exception:
        return None


def embed_text_batch(
    texts: list[str],
    *,
    endpoint: str | None = None,
    model: str | None = None,
    dimensions: int = 1024,
    timeout: float = 60.0,
) -> list[list[float]]:
    """Batch embedding (single POST). Falls back to deterministic per item."""
    import requests

    if endpoint is None or model is None:
        from packages.core.config import get_settings

        settings = get_settings()
        endpoint = endpoint or settings.embedding_endpoint
        model = model or settings.embedding_model
        dimensions = dimensions or settings.embedding_dimensions
    if not endpoint or not model:
        return [build_deterministic_embedding(t, dimensions=dimensions) for t in texts]
    try:
        resp = requests.post(
            endpoint,
            json={"model": model, "input": [str(t or "")[:2000] for t in texts]},
            timeout=timeout,
        )
        data = resp.json()
        items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
        out: list[list[float]] = []
        for item in items:
            vector = item.get("embedding")
            floats = (
                [float(v) for v in (vector or [])[:dimensions]]
                if isinstance(vector, list)
                else []
            )
            if floats:
                out.append(_normalize(floats))
            else:
                out.append(build_deterministic_embedding("", dimensions=dimensions))
        return out
    except Exception:
        return [build_deterministic_embedding(t, dimensions=dimensions) for t in texts]


def _tokenize(text: str) -> list[str]:
    normalized = str(text or "").lower()
    alnum_tokens = TOKEN_PATTERN.findall(normalized)
    cjk_tokens = CJK_PATTERN.findall(normalized)
    seen: set[str] = set()
    tokens: list[str] = []
    for token in [*alnum_tokens, *cjk_tokens]:
        if not token or token in seen:
            continue
        tokens.append(token)
        seen.add(token)
    return tokens
