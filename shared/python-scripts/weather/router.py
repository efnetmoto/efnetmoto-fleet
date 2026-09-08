from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType
from weather.providers.base import WeatherProvider


class ProviderRouter:
    def __init__(self, providers: list[WeatherProvider]):
        self._providers = providers
        self._by_id: dict[str, WeatherProvider] = {}
        for p in providers:
            if p.id in self._by_id:
                raise ValueError(f"duplicate provider id: {p.id}")
            self._by_id[p.id] = p

    def available_ids(self) -> list[str]:
        """Return all provider ids in registration order."""
        return [p.id for p in self._providers]

    def route(
        self,
        loc: LocationResult,
        metar: bool = False,
        provider_id: str | None = None,
    ) -> WeatherProvider:
        """Select the appropriate provider for the given location.

        Auto-discovery (provider_id is None):
            ICAO codes require metar=True. Without it, a ProviderError is raised
            with an actionable message directing the user to use --metar or the
            IATA equivalent. If metar=True and location is ICAO, AvWxProvider is
            preferred. Otherwise, the first provider that owns the location type
            (via preferred_types) wins; if none own it, the first provider whose
            supports() returns True is used (the catch-all fallback).

        Manual override (provider_id is set):
            Bypasses all auto-discovery guards (including metar/ICAO checks).
            The named provider is used directly. If it does not support the
            location, a ProviderError is raised.

        Args:
            loc: Resolved location to route.
            metar: If True and loc.type is ICAO, prefer the METAR provider.
                Ignored when provider_id is set.
            provider_id: If set, force the provider with this id, bypassing
                auto-discovery.

        Returns:
            A WeatherProvider that supports the given location.

        Raises:
            ProviderError: If no provider supports the location, the named
                provider is unknown, or the named provider can't handle the
                location.
            ValueError: If two providers share the same id (at construction).
        """
        if provider_id is not None:
            provider = self._by_id.get(provider_id)
            if provider is None:
                available = ", ".join(f"--{s}" for s in self.available_ids())
                raise ProviderError(f"Unknown provider '--{provider_id}'. Available: {available}.")
            if not provider.supports(loc):
                raise ProviderError(f"{provider.name} can't handle that location.")
            return provider

        if loc.type == LocationType.ICAO and not metar:
            raise ProviderError(
                f"ICAO codes require --metar (e.g. .wz --metar {loc.raw})."
                f" For general weather use the IATA code instead (e.g. .wz SFO)."
            )

        if metar and loc.type != LocationType.ICAO:
            raise ProviderError(
                "METAR output requires 3-digit ICAO codes as input."
                " See https://en.wikipedia.org/wiki/List_of_airports_by_ICAO_code:_A"
                " for a complete list."
            )

        # Affinity: a provider that owns this location type wins regardless of order
        for p in self._providers:
            if loc.type in p.preferred_types:
                return p

        # Fallback: first registered provider that supports it
        for p in self._providers:
            if p.supports(loc):
                return p

        raise ProviderError(f"No provider available for location: {loc.raw}")
