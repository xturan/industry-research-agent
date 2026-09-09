from __future__ import annotations

from datetime import datetime

import pytest

from packages.sources.adapters import (
    EIAAdapter,
    SecEdgarAdapter,
    UserInputAdapter,
    WHOGHOAdapter,
    WorldBankAdapter,
)
from packages.sources.enums import ToolErrorCode, ToolStatus
from packages.sources.registry import build_default_source_registry
from packages.sources.router import SourceRouter
from packages.sources.schemas import QueryContext, TimeRange, ToolRequest, UserProvidedSource
from packages.sources.service import SourceIntelligenceService
from packages.sources.tools import build_source_tool_registry


def test_source_schema_validation() -> None:
    context = QueryContext(
        query="GDP and CPI trend",
        time_range=TimeRange(
            start_at=datetime(2020, 1, 1),
            end_at=datetime(2024, 12, 31),
        ),
        user_provided_sources=[
            UserProvidedSource(
                source_uri="file://local/note.md",
                inline_text="User context for macro hypothesis.",
            )
        ],
    )
    assert context.query
    with pytest.raises(ValueError):
        TimeRange(start_at=datetime(2024, 1, 1), end_at=datetime(2020, 1, 1))


def test_registry_registration_and_listing() -> None:
    registry = build_default_source_registry()
    profiles = registry.list_profiles(enabled_only=True)
    source_ids = {profile.source_id for profile in profiles}
    assert {"user_input", "world_bank", "eia", "sec_edgar", "who_gho"} <= source_ids
    assert all(profile.enabled for profile in profiles)


def test_router_macro_and_user_input_routing() -> None:
    router = SourceRouter()
    macro = router.route(QueryContext(query="GDP CPI population outlook"))
    assert any(item.source_id == "world_bank" for item in macro)

    with_user_input = router.route(
        QueryContext(
            query="energy demand scenario",
            user_provided_sources=[
                UserProvidedSource(inline_text="internal deck note about electricity demand")
            ],
        )
    )
    assert any(item.source_id == "user_input" for item in with_user_input)


def test_adapter_profile_validity() -> None:
    adapters = [
        UserInputAdapter(),
        SecEdgarAdapter(),
        WorldBankAdapter(),
        EIAAdapter(),
        WHOGHOAdapter(),
    ]
    for adapter in adapters:
        profile = adapter.get_profile()
        assert profile.source_id
        assert profile.display_name
        assert profile.capabilities is not None


def test_tool_registry_dispatch_shape() -> None:
    tools = build_source_tool_registry()
    response = tools.dispatch(
        ToolRequest(
            tool_name="route_research_sources",
            query_context=QueryContext(query="oil inventory change and electricity demand"),
        )
    )
    assert response.status == ToolStatus.SUCCESS
    assert any(item.source_id == "eia" for item in response.route_recommendations)


def test_source_service_basic_behavior() -> None:
    service = SourceIntelligenceService()
    route = service.route_sources(QueryContext(query="GDP and population by country"))
    assert any(item.source_id == "world_bank" for item in route)

    bundle_response = service.build_bundle_for_query(
        QueryContext(
            query="internal thesis notes",
            user_provided_sources=[UserProvidedSource(inline_text="Company A margin expanded.")],
        )
    )
    assert bundle_response.bundle is not None
    assert bundle_response.bundle.query == "internal thesis notes"


def test_user_input_tool_path() -> None:
    tools = build_source_tool_registry()
    request = ToolRequest(
        tool_name="fetch_user_provided_source",
        query_context=QueryContext(
            query="manual notes",
            user_provided_sources=[
                UserProvidedSource(
                    title="Analyst note",
                    inline_text="Demand risk persists in Q2.",
                )
            ],
        ),
    )
    response = tools.dispatch(request)
    assert response.status == ToolStatus.SUCCESS
    assert response.documents


def test_unsupported_adapter_method_handled_gracefully() -> None:
    tools = build_source_tool_registry()
    response = tools.dispatch(
        ToolRequest(
            tool_name="search_source_documents",
            query_context=QueryContext(query="health mortality baseline"),
            source_id="who_gho",
        )
    )
    assert response.status == ToolStatus.NOT_IMPLEMENTED
    assert response.errors
    assert response.errors[0].code == ToolErrorCode.NOT_IMPLEMENTED
