"""Weather provider for CWOP stations via the api.aprs.fi API."""

import os

import requests

from weather.conversions import c_to_f, degrees_to_cardinal, mm_to_inches, mps_to_kph, mps_to_mph
from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType, WeatherResult
from weather.providers.base import WeatherProvider


def _parse_obs(obs: dict, loc: LocationResult) -> WeatherResult:
    """Parse a raw APRS weather observation entry into a WeatherResult.

    Args:
        obs: A single entry dict from the api.aprs.fi ``entries`` list.
        loc: The resolved location used as a fallback for the station name.

    Returns:
        A populated WeatherResult with temperature, humidity, rain, and wind data.
    """
    temp_c = float(obs.get("temp") or 0)
    temp_c = round(temp_c, 1)
    temp_f = c_to_f(temp_c)

    humidity = int(obs.get("humidity", 0))

    wdir = obs.get("wind_direction")
    if wdir is None:
        wind_dir = "N/A"
    else:
        wdir = float(wdir)
        wind_dir = degrees_to_cardinal(wdir)

    wspd_mps = float(obs.get("wind_speed") or 0)
    wind_mph = mps_to_mph(wspd_mps)
    wind_kph = mps_to_kph(wspd_mps)

    wgst = obs.get("wind_gust")
    if wgst is not None:
        gust_mps = float(wgst)
        wind_gust_mph = mps_to_mph(gust_mps)
        wind_gust_kph = mps_to_kph(gust_mps)
    else:
        wind_gust_mph = None
        wind_gust_kph = None

    rain_since_midnight = float(obs.get("rain_mn") or 0)
    rain_in = mm_to_inches(rain_since_midnight)
    rain_mm = round(rain_since_midnight, 1)

    return WeatherResult(
        location_name=obs.get("name", loc.query),
        temp_f=temp_f,
        feels_like_f=None,
        temp_c=temp_c,
        feels_like_c=None,
        humidity_pct=humidity,
        wind_dir=wind_dir,
        wind_mph=wind_mph,
        wind_kph=wind_kph,
        wind_gust_mph=wind_gust_mph,
        wind_gust_kph=wind_gust_kph,
        rain_today_in=rain_in,
        rain_today_mm=rain_mm,
    )


class AprsProvider(WeatherProvider):
    """Weather provider that fetches CWOP station data from api.aprs.fi."""

    def __init__(self):
        """Initialize the provider, loading the API key from the environment.

        Raises:
            RuntimeError: If the ``APRSFI_KEY`` environment variable is not set.
        """
        key = os.environ.get("APRSFI_KEY")
        if not key:
            raise RuntimeError(
                "APRSFI_KEY environment variable not set. "
                "Set it in the Ansible vault file in group_vars"
            )
        self._key = key
        self.aprs_baseurl = "https://api.aprs.fi/api/get"

    @property
    def name(self) -> str:
        """Human-readable name of this provider."""
        return "api.aprs.fi"

    def supports(self, loc: LocationResult) -> bool:
        """Return True if the location is an APRS/CWOP station query.

        Args:
            loc: The resolved location to check.

        Returns:
            True when ``loc.type`` is ``LocationType.APRS``, False otherwise.
        """
        return loc.type == LocationType.APRS

    def get_weather(self, loc: LocationResult) -> WeatherResult:
        """Fetch current weather for an APRS/CWOP station.

        Args:
            loc: The resolved location whose ``query`` field holds the station
                call sign with the Weather Station SSID suffixed (e.g. ``"KK4LFC-13"``).

        Returns:
            A WeatherResult populated from the most recent station observation.

        Raises:
            ProviderError: If the request times out, the connection fails, the
                server returns a non-200 status, the response is unparseable, no
                matching station is found, or the observation data is malformed.
        """
        try:
            resp = requests.get(
                self.aprs_baseurl,
                params={"format": "json", "name": loc.query, "apikey": self._key, "what": "wx"},
                headers={
                    "User-Agent": "efnetmoto-fleet-weather/1.0 (+https://github.com/efnetmoto/efnetmoto-fleet)"
                },
                timeout=10,
            )
        except requests.Timeout:
            raise ProviderError("Request timed out")
        except requests.ConnectionError:
            raise ProviderError("Could not reach api.aprs.fi")

        if resp.status_code != 200:
            raise ProviderError(f"api.aprs.fi returned HTTP {resp.status_code}")

        try:
            data = resp.json()
        except ValueError:
            raise ProviderError("Unexpected response from api.aprs.fi")

        if data["found"] < 1:
            raise ProviderError(f"No matching CWOP station found for {loc.query}")

        try:
            return _parse_obs(data["entries"][0], loc)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ProviderError(f"Could not parse APRS response: {exc}")
