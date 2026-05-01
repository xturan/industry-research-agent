from __future__ import annotations

from packages.sources.disclosure_api import CninfoDisclosureApiProvider
from packages.sources.disclosure_mapping import build_disclosure_search_spec
from packages.sources.enums import InfoType, LineFamily, RegionalLevel
from packages.sources.query_decomposition import QueryDecompositionTask


class _FakeCninfoResponse:
    def __init__(self, announcements: list[dict[str, object]] | None = None) -> None:
        self._announcements = announcements

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "announcements": self._announcements
            or [
                _announcement(
                    title="2025年年度报告",
                    adjunct_url="finalpage/2026-03-17/1225012497.PDF",
                    announcement_id="1225012497",
                )
            ]
        }


class _FakeCninfoSession:
    def __init__(self, announcements: list[dict[str, object]] | None = None) -> None:
        self.posts: list[dict[str, object]] = []
        self._announcements = announcements

    def post(self, url, *, headers, data, timeout):  # noqa: ANN001
        self.posts.append(
            {
                "url": url,
                "headers": headers,
                "data": data,
                "timeout": timeout,
            }
        )
        return _FakeCninfoResponse(self._announcements)


def test_cninfo_disclosure_api_provider_builds_documents_from_announcements() -> None:
    session = _FakeCninfoSession()
    provider = CninfoDisclosureApiProvider(session=session, timeout_seconds=3)
    spec = build_disclosure_search_spec("低空经济 上市公司 公告")

    documents, normalized_documents, errors, metadata = provider.search(
        task=_enterprise_disclosure_task(),
        spec=spec,
        max_results=1,
    )

    assert errors == []
    assert metadata["provider"] == "cninfo_direct_api"
    assert metadata["status"] == "evidence_found"
    assert metadata["estimated_tavily_credits"] == 0
    assert session.posts
    assert "中信海直" in str(session.posts[0]["data"]["searchkey"])
    assert documents[0].source_id == "cn_exchange_cninfo_announcement_v1"
    assert documents[0].source_uri == (
        "https://static.cninfo.com.cn/finalpage/2026-03-17/1225012497.PDF"
    )
    assert "2026-03-17" in (documents[0].raw_text or "")
    assert "1773676800000" not in (documents[0].raw_text or "")
    assert normalized_documents[0].metadata["final_url"] == documents[0].source_uri
    assert normalized_documents[0].sections[0].text


def test_cninfo_disclosure_api_provider_skips_non_operating_disclosures() -> None:
    session = _FakeCninfoSession(
        announcements=[
            _announcement(
                title="北京市通商律师事务所关于海南海峡航运股份有限公司股票期权激励计划的法律意见书",
                adjunct_url="finalpage/2026-04-28/weak.PDF",
                announcement_id="weak",
            ),
            _announcement(
                title="2025年年度报告",
                adjunct_url="finalpage/2026-04-11/strong.PDF",
                announcement_id="strong",
            ),
        ]
    )
    provider = CninfoDisclosureApiProvider(session=session, timeout_seconds=3)

    documents, normalized_documents, errors, metadata = provider.search(
        task=_enterprise_disclosure_task(),
        spec=build_disclosure_search_spec("低空经济 上市公司 公告"),
        max_results=1,
    )

    assert errors == []
    assert metadata["status"] == "evidence_found"
    assert documents[0].document_id == "cninfo_announcement_strong"
    assert "法律意见书" not in documents[0].title
    assert normalized_documents[0].title == documents[0].title


def _announcement(
    *,
    title: str,
    adjunct_url: str,
    announcement_id: str,
) -> dict[str, object]:
    return {
        "secName": "中信海直",
        "secCode": "000099",
        "announcementTitle": title,
        "announcementTime": 1773676800000,
        "adjunctUrl": adjunct_url,
        "announcementId": announcement_id,
    }


def _enterprise_disclosure_task() -> QueryDecompositionTask:
    return QueryDecompositionTask(
        task_id="enterprise_disclosure_test",
        task_family="enterprise_disclosure",
        tiaokuai_axis="mixed",
        line_family=LineFamily.EXCHANGE,
        regional_level=RegionalLevel.CROSS_REGION,
        info_type=InfoType.REGULATORY_ANNOUNCEMENT,
        execution_bucket="direct_structured_sources",
        source_cluster="official_disclosure_backbone",
        source_strategy_hint="test",
        include_domains=[],
        exclude_domains=[],
        search_phrases=["低空经济 上市公司 公告"],
        negative_terms=[],
        evidence_goal="Find listed-company disclosure evidence.",
        fallback_path="Use direct disclosure adapters.",
        priority=80,
        confidence=0.8,
    )
