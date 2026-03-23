from abc import ABC, abstractmethod

from weather.models import ForecastResult, LocationResult, WeatherResult


class WeatherProvider(ABC):
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
