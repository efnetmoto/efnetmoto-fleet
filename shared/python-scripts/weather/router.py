from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType
from weather.providers.base import WeatherProvider


class ProviderRouter:
    def __init__(self, providers: list[WeatherProvider]):
        self._providers = providers

    def route(self, loc: LocationResult, metar: bool = False) -> WeatherProvider:
        """Select the appropriate provider for the given location.

        ICAO codes require metar=True. Without it, a ProviderError is raised with
        an actionable message directing the user to use --metar or the IATA equivalent.
        If metar=True and location is ICAO, prefer AvWxProvider. Otherwise,
        returns the first provider that supports the location type.

        Args:
            loc: Resolved location to route.
            metar: If True and loc.type is ICAO, prefer the METAR provider.

        Returns:
            A WeatherProvider that supports the given location.

        Raises:
            ProviderError: If no provider supports the location, or if an ICAO
                code is given without metar=True.
        """
        if loc.type == LocationType.ICAO and not metar:
            raise ProviderError(
                f"ICAO codes require --metar (e.g. .wz --metar {loc.raw})."
                f" For general weather use the IATA code instead (e.g. .wz SFO)."
            )
        if metar and loc.type == LocationType.ICAO:
            for p in reversed(self._providers):
                if p.supports(loc):
                    return p
        for p in self._providers:
            if p.supports(loc):
                return p
        raise ProviderError(f"No provider available for location: {loc.raw}")
