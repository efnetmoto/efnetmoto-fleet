import requests

from weather.conversions import c_to_f, degrees_to_cardinal, f_to_c, kph_to_mph, m_to_km, m_to_mi
from weather.exceptions import ProviderError
from weather.models import ForecastResult, FormatMode, LocationResult, LocationType, WeatherResult
from weather.providers.base import WeatherProvider

_OBSERVATION_URL = "https://api.weather.gov/stations/{station_id}/observations/latest"
_STATION_URL = "https://api.weather.gov/stations/{station_id}"
_POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"
_HEADERS = {
    "User-Agent": "efnetmoto-fleet-weather/1.0 (+https://github.com/efnetmoto/efnetmoto-fleet)"
}


def _get_nested_value(data: dict, key: str) -> float | None:
    """Extract the ``value`` field from a nested NWS observation property.

    NWS wraps each measurement as ``{"unitCode": ..., "value": ..., "qualityControl": ...}``.
    Returns None when the value is null or the key is absent.
    """
    inner = data.get(key) or {}
    value = inner.get("value")
    return float(value) if value is not None else None


def _parse_obs(obs: dict, loc: LocationResult) -> WeatherResult:
    """Parse a raw NWS weather observation entry into a WeatherResult.

    Args:
        obs: The ``properties`` dict from the api.weather.gov response.
        loc: The resolved location used as a fallback for the station name.

    Returns:
        A populated WeatherResult with temperature, humidity, and wind data.

    Raises:
        ProviderError: If temperature is not reported (null) — the observation
            is not useful without it.
    """
    temp_c = _get_nested_value(obs, "temperature")
    if temp_c is None:
        raise ProviderError(f"NWS station {loc.query} is not reporting temperature data")
    temp_c = round(temp_c, 1)
    temp_f = c_to_f(temp_c)

    wind_chill = _get_nested_value(obs, "windChill")
    heat_index = _get_nested_value(obs, "heatIndex")
    if wind_chill is not None:
        feels_like_c = round(wind_chill, 1)
        feels_like_f = c_to_f(feels_like_c)
    elif heat_index is not None:
        feels_like_c = round(heat_index, 1)
        feels_like_f = c_to_f(feels_like_c)
    else:
        feels_like_c = None
        feels_like_f = None

    humidity = _get_nested_value(obs, "relativeHumidity")
    humidity_pct = int(round(humidity)) if humidity is not None else None

    wdir = _get_nested_value(obs, "windDirection")
    wind_dir = "N/A" if wdir is None else degrees_to_cardinal(wdir)

    wind_kph = _get_nested_value(obs, "windSpeed")
    if wind_kph is None:
        wind_kph = 0.0
    wind_mph = kph_to_mph(wind_kph)

    wind_gust_kph = _get_nested_value(obs, "windGust")
    wind_gust_mph = kph_to_mph(wind_gust_kph) if wind_gust_kph is not None else None

    vis_m = _get_nested_value(obs, "visibility")
    if vis_m is not None:
        visibility_km = m_to_km(vis_m)
        visibility_mi = m_to_mi(vis_m)
    else:
        visibility_km = None
        visibility_mi = None

    condition = obs.get("textDescription") or None

    station_name = obs.get("stationName") or loc.query
    station_id = obs.get("stationId") or loc.query
    loc_name = f"{station_name} ({station_id})"

    return WeatherResult(
        location_name=loc_name,
        condition=condition,
        temp_f=temp_f,
        feels_like_f=feels_like_f,
        temp_c=temp_c,
        feels_like_c=feels_like_c,
        humidity_pct=humidity_pct,
        wind_dir=wind_dir,
        wind_mph=wind_mph,
        wind_kph=wind_kph,
        wind_gust_mph=wind_gust_mph,
        wind_gust_kph=wind_gust_kph,
        visibility_mi=visibility_mi,
        visibility_km=visibility_km,
    )


def _parse_temp(period: dict) -> int | None:
    """Extract temperature from a forecast period.

    The API currently returns a plain integer with a separate temperatureUnit
    field. The spec deprecates this in favor of a QuantitativeValue object; both
    formats are handled here.
    """
    temp = period.get("temperature")
    if isinstance(temp, dict):
        temp = temp.get("value")
    if temp is None:
        return None
    return int(temp)


def _parse_forecast_periods(periods: list[dict]) -> ForecastResult:
    if not periods:
        raise ProviderError("NWS forecast returned no periods")

    condition = periods[0].get("shortForecast") or "Unknown"

    high_f = None
    low_f = None
    for period in periods[:4]:
        temp = _parse_temp(period)
        if temp is None:
            continue
        if period.get("isDaytime") and high_f is None:
            high_f = temp
        elif not period.get("isDaytime") and low_f is None:
            low_f = temp
        if high_f is not None and low_f is not None:
            break

    if high_f is None or low_f is None:
        raise ProviderError("NWS forecast did not include both high and low temperatures")

    return ForecastResult(
        condition=condition,
        high_f=float(high_f),
        high_c=f_to_c(float(high_f)),
        low_f=float(low_f),
        low_c=f_to_c(float(low_f)),
    )


class NationalWeatherServiceProvider(WeatherProvider):
    preferred_types = frozenset()
    format_mode = FormatMode.CURRENT
    id = "nws"

    @property
    def name(self) -> str:
        return "National Weather Service (api.weather.gov)"

    def supports(self, loc: LocationResult) -> bool:
        return loc.type in (LocationType.NWS_STATION, LocationType.ICAO)

    def get_weather(self, loc: LocationResult) -> WeatherResult:
        try:
            resp = requests.get(
                _OBSERVATION_URL.format(station_id=loc.query),
                headers=_HEADERS,
                timeout=10,
            )
        except requests.Timeout:
            raise ProviderError("Request timed out")
        except requests.ConnectionError:
            raise ProviderError("Could not reach api.weather.gov")

        if resp.status_code == 404:
            raise ProviderError(f"NWS station '{loc.query}' not found")
        if resp.status_code != 200:
            raise ProviderError(f"api.weather.gov returned HTTP {resp.status_code}")

        try:
            data = resp.json()
        except ValueError:
            raise ProviderError("Unexpected response from api.weather.gov")

        try:
            return _parse_obs(data["properties"], loc)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ProviderError(f"Could not parse NWS response: {exc}")

    def get_forecast(self, loc: LocationResult) -> ForecastResult | None:
        lat, lon = self._get_coords(loc)
        forecast_url = self._resolve_forecast_url(lat, lon)
        return self._fetch_forecast(forecast_url)

    def _get_coords(self, loc: LocationResult) -> tuple[float, float]:
        try:
            resp = requests.get(
                _STATION_URL.format(station_id=loc.query),
                headers=_HEADERS,
                timeout=10,
            )
        except requests.Timeout:
            raise ProviderError("Request timed out")
        except requests.ConnectionError:
            raise ProviderError("Could not reach api.weather.gov")

        if resp.status_code != 200:
            raise ProviderError(f"api.weather.gov returned HTTP {resp.status_code}")

        try:
            coords = resp.json()["geometry"]["coordinates"]
            return (coords[1], coords[0])  # (lat, lon)
        except (ValueError, KeyError, TypeError, IndexError):
            raise ProviderError("Could not parse station location from api.weather.gov")

    def _resolve_forecast_url(self, lat: float, lon: float) -> str:
        try:
            resp = requests.get(
                _POINTS_URL.format(lat=lat, lon=lon),
                headers=_HEADERS,
                timeout=10,
            )
        except requests.Timeout:
            raise ProviderError("Request timed out")
        except requests.ConnectionError:
            raise ProviderError("Could not reach api.weather.gov")

        if resp.status_code != 200:
            raise ProviderError(f"api.weather.gov returned HTTP {resp.status_code}")

        try:
            return resp.json()["properties"]["forecast"]
        except (ValueError, KeyError, TypeError):
            raise ProviderError("Could not resolve forecast URL from api.weather.gov")

    def _fetch_forecast(self, url: str) -> ForecastResult:
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=10)
        except requests.Timeout:
            raise ProviderError("Request timed out")
        except requests.ConnectionError:
            raise ProviderError("Could not reach api.weather.gov")

        if resp.status_code != 200:
            raise ProviderError(f"api.weather.gov returned HTTP {resp.status_code}")

        try:
            periods = resp.json()["properties"]["periods"]
            return _parse_forecast_periods(periods)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise ProviderError(f"Could not parse NWS forecast: {exc}")
