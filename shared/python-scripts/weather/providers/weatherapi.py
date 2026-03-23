import os

import requests

from weather.exceptions import ProviderError
from weather.models import ForecastResult, LocationResult, WeatherResult
from weather.providers.base import WeatherProvider


class WeatherAPIProvider(WeatherProvider):
    def __init__(self):
        key = os.environ.get("WEATHERAPI_KEY")
        if not key:
            raise RuntimeError(
                "WEATHERAPI_KEY environment variable is not set. "
                "Set it in the bot's .env file or Ansible host_vars."
            )
        self._key = key

    @property
    def name(self) -> str:
        return "WeatherAPI.com"

    def supports(self, loc: LocationResult) -> bool:
        return True

    def _get_json(self, url: str, params: dict) -> dict:
        try:
            resp = requests.get(url, params=params, timeout=10)
        except requests.Timeout:
            raise ProviderError("Request timed out")
        except requests.ConnectionError:
            raise ProviderError("Could not reach WeatherAPI")

        if resp.status_code != 200:
            try:
                msg = resp.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                msg = "Unexpected response from WeatherAPI"
            raise ProviderError(msg)

        return resp.json()

    def get_weather(self, loc: LocationResult) -> WeatherResult:
        try:
            data = self._get_json(
                "https://api.weatherapi.com/v1/current.json",
                {"key": self._key, "q": loc.query},
            )
            location = data["location"]
            current = data["current"]
            return WeatherResult(
                location_name=f"{location['name']}, {location['region']}",
                condition=current["condition"]["text"],
                temp_f=current["temp_f"],
                feels_like_f=current["feelslike_f"],
                temp_c=current["temp_c"],
                feels_like_c=current["feelslike_c"],
                humidity_pct=current["humidity"],
                wind_dir=current["wind_dir"],
                wind_mph=current["wind_mph"],
                wind_kph=current["wind_kph"],
                wind_gust_mph=current.get("gust_mph"),
                wind_gust_kph=current.get("gust_kph"),
                visibility_mi=current["vis_miles"],
                visibility_km=current["vis_km"],
                uv_index=current.get("uv"),
            )
        except (KeyError, TypeError, ValueError):
            raise ProviderError("Unexpected response from WeatherAPI")

    def get_forecast(self, loc: LocationResult) -> ForecastResult | None:
        try:
            data = self._get_json(
                "https://api.weatherapi.com/v1/forecast.json",
                {"key": self._key, "q": loc.query, "days": 1},
            )
            day = data["forecast"]["forecastday"][0]["day"]
            return ForecastResult(
                condition=day["condition"]["text"],
                high_c=day["maxtemp_c"],
                high_f=day["maxtemp_f"],
                low_c=day["mintemp_c"],
                low_f=day["mintemp_f"],
            )
        except (KeyError, TypeError, ValueError, IndexError):
            raise ProviderError("Unexpected response from WeatherAPI")
