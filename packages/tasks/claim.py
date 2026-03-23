from __future__ import annotations


def compute_retry_delay_seconds(*, attempt_count: int, base_delay_seconds: int) -> int:
    """Exponential backoff with an upper bound for deterministic local behavior."""
    bounded_attempt = max(min(attempt_count, 6), 1)
    delay = max(base_delay_seconds, 1) * (2 ** (bounded_attempt - 1))
    return min(delay, 300)
