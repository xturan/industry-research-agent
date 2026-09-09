from __future__ import annotations

from packages.sources.live_fetch import LiveHtmlFetchService


def test_live_html_fetch_service_success(monkeypatch) -> None:
    service = LiveHtmlFetchService(timeout_seconds=1.0, max_retries=1, backoff_seconds=0.0)

    def _fake_request_once(url: str, *, headers: dict[str, str], timeout_seconds: float):
        assert url == "https://example.cn/list"
        assert headers["User-Agent"]
        assert timeout_seconds == 1.0
        return b"<html><body>ok</body></html>", 200, "text/html; charset=utf-8", url

    monkeypatch.setattr(service, "_request_once", _fake_request_once)
    result = service.fetch_html("https://example.cn/list")
    assert result.status_code == 200
    assert result.encoding == "utf-8"
    assert "ok" in result.text
    assert result.attempts == 1
    assert result.retry_count == 0


def test_live_html_fetch_service_timeout_retry(monkeypatch) -> None:
    service = LiveHtmlFetchService(timeout_seconds=1.0, max_retries=1, backoff_seconds=0.0)
    state = {"count": 0}

    def _flaky_request_once(url: str, *, headers: dict[str, str], timeout_seconds: float):
        state["count"] += 1
        if state["count"] == 1:
            raise TimeoutError("temporary timeout")
        return b"<html><body>retried</body></html>", 200, "text/html; charset=utf-8", url

    monkeypatch.setattr(service, "_request_once", _flaky_request_once)
    result = service.fetch_html("https://example.cn/detail")
    assert state["count"] == 2
    assert result.retry_count == 1
    assert result.attempts == 2
    assert "retried" in result.text
