from abc import ABC, abstractmethod

from weather.models import ForecastResult, FormatMode, LocationResult, WeatherResult


class WeatherProvider(ABC):
    # Stable CLI identifier for manual provider selection (e.g. "awn").
    id: str = ""

    # Location types this provider *owns* — it wins auto-discovery routing for
    # these types regardless of registration order.  An empty set (the default)
    # means the provider is a fallback-only catch-all (e.g. WeatherAPI).
    preferred_types: frozenset = frozenset()

    # Which formatter the handler should use to render this provider's results.
    # Defaults to CURRENT; providers override as needed.
    format_mode: FormatMode = FormatMode.CURRENT

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name, used in logs."""
        ...

    @abstractmethod
    def supports(self, loc: LocationResult) -> bool:
        """Return True if this provider can handle the given location type."""
        ...

    @abstractmethod
    def get_weather(self, loc: LocationResult) -> WeatherResult:
        """Fetch current conditions for the given location.

        Args:
            loc: Resolved location to fetch weather for.

        Returns:
            Current conditions as a WeatherResult.

        Raises:
            ProviderError: On any upstream failure.
        """
        ...

    def get_forecast(self, loc: LocationResult) -> ForecastResult | None:
        """Fetch today's forecast for the given location.

        Default implementation returns None — override in providers that support it.

        Args:
            loc: Resolved location to fetch a forecast for.

        Returns:
            Today's forecast, or None if this provider does not support forecasts.

        Raises:
            ProviderError: On any upstream failure.
        """
        return None
