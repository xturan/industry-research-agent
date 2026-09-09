from __future__ import annotations

from packages.sources.adapters import (
    BaseSourceAdapter,
    EIAAdapter,
    SecEdgarAdapter,
    UserInputAdapter,
    WHOGHOAdapter,
    WorldBankAdapter,
)
from packages.sources.profiles import build_domestic_source_profiles
from packages.sources.schemas import SourceProfile


class SourceRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, BaseSourceAdapter | None] = {}
        self._profiles: dict[str, SourceProfile] = {}

    def register(self, adapter: BaseSourceAdapter) -> None:
        profile = adapter.get_profile()
        self.register_profile(profile, adapter=adapter)

    def register_profile(
        self,
        profile: SourceProfile,
        *,
        adapter: BaseSourceAdapter | None = None,
    ) -> None:
        self._profiles[profile.source_id] = profile
        if adapter is not None:
            self._adapters[profile.source_id] = adapter

    def register_generic_profile(self, profile: SourceProfile) -> None:
        from packages.sources.profile_adapter import GenericProfileSourceAdapter

        self.register_profile(profile, adapter=GenericProfileSourceAdapter(profile))

    def get_adapter(self, source_id: str, *, enabled_only: bool = True) -> BaseSourceAdapter | None:
        profile = self._profiles.get(source_id)
        if profile is None:
            return None
        if enabled_only and not profile.enabled:
            return None
        adapter = self._adapters.get(source_id)
        if adapter is None:
            return None
        return adapter

    def get_profile(self, source_id: str, *, enabled_only: bool = True) -> SourceProfile | None:
        profile = self._profiles.get(source_id)
        if profile is None:
            return None
        if enabled_only and not profile.enabled:
            return None
        return profile

    def list_profiles(self, *, enabled_only: bool = True) -> list[SourceProfile]:
        profiles = list(self._profiles.values())
        if enabled_only:
            profiles = [profile for profile in profiles if profile.enabled]
        return sorted(profiles, key=lambda profile: (-profile.priority_hint, profile.source_id))

    def has_enabled_collector_profiles(self) -> bool:
        return any(
            profile.enabled and profile.collector_type is not None
            for profile in self._profiles.values()
        )


def build_default_source_registry() -> SourceRegistry:
    registry = SourceRegistry()
    for adapter in [
        UserInputAdapter(),
        SecEdgarAdapter(),
        WorldBankAdapter(),
        EIAAdapter(),
        WHOGHOAdapter(),
    ]:
        registry.register(adapter)
    for profile in build_domestic_source_profiles():
        registry.register_generic_profile(profile)
    return registry
