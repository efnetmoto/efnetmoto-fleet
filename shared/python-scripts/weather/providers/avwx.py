import requests

from weather.conversions import degrees_to_cardinal, humidity_from_dewpoint
from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType, WeatherResult
from weather.providers.base import WeatherProvider


def _parse_obs(obs: dict, loc: LocationResult) -> WeatherResult:
    temp_c = float(obs["temp"])
    temp_f = temp_c * 9 / 5 + 32

    # Humidity from dewpoint if available
    dewp = obs.get("dewp")
    humidity: int | None = humidity_from_dewpoint(temp_c, float(dewp)) if dewp is not None else None

    # Wind
    wdir = obs.get("wdir")
    if wdir is None:
        wind_dir = "N/A"
    elif wdir == "VRB":
        wind_dir = "VRB"
    else:
        wind_dir = degrees_to_cardinal(wdir)

    wspd_kts = float(obs.get("wspd") or 0)
    wind_mph = round(wspd_kts * 1.15078, 1)
    wind_kph = round(wspd_kts * 1.852, 1)

    wgst = obs.get("wgst")
    if wgst is not None:
        gust_kts = float(wgst)
        wind_gust_mph: float | None = round(gust_kts * 1.15078, 1)
        wind_gust_kph: float | None = round(gust_kts * 1.852, 1)
    else:
        wind_gust_mph = None
        wind_gust_kph = None

    # Visibility — in statute miles, a string value (e.g. 10+) means "greater than 10 sm"
    visib_raw = obs.get("visib")
    if visib_raw is not None and str(visib_raw).endswith("+"):
        visibility_mi = None
        visibility_km = None
    elif visib_raw is not None and float(visib_raw):
        visibility_mi: float | None = float(visib_raw)
        visibility_km: float | None = round(float(visib_raw) * 1.60934, 1)
    else:
        visibility_mi = None
        visibility_km = None

    # Condition from flight category or sky conditions
    flight_cat = obs.get("flight_category", "")
    wx_string = obs.get("wxString") or ""
    if wx_string:
        condition = wx_string
    elif flight_cat:
        condition = flight_cat
    else:
        condition = "Unknown"

    return WeatherResult(
        location_name=obs.get("icaoId", loc.query),
        condition=condition,
        temp_f=round(temp_f, 1),
        feels_like_f=None,
        temp_c=round(temp_c, 1),
        feels_like_c=None,
        humidity_pct=humidity,
        wind_dir=wind_dir,
        wind_mph=wind_mph,
        wind_kph=wind_kph,
        wind_gust_mph=wind_gust_mph,
        wind_gust_kph=wind_gust_kph,
        visibility_mi=visibility_mi,
        visibility_km=visibility_km,
        uv_index=None,
        metar_raw=obs.get("rawOb"),
    )


class AvWxProvider(WeatherProvider):
    @property
    def name(self) -> str:
        return "aviationweather.gov"

    def supports(self, loc: LocationResult) -> bool:
        return loc.type == LocationType.ICAO

    def get_weather(self, loc: LocationResult) -> WeatherResult:
        try:
            resp = requests.get(
                "https://aviationweather.gov/api/data/metar",
                params={"ids": loc.query, "format": "json", "taf": "false"},
                timeout=10,
            )
        except requests.Timeout:
            raise ProviderError("Request timed out")
        except requests.ConnectionError:
            raise ProviderError("Could not reach aviationweather.gov")

        # AvWx API returns a 204 when the station is not valid
        if resp.status_code == 204:
            raise ProviderError(f"No METAR data found for {loc.query}")

        if resp.status_code != 200:
            raise ProviderError(f"aviationweather.gov returned HTTP {resp.status_code}")

        try:
            data = resp.json()
        except ValueError:
            raise ProviderError("Unexpected response from aviationweather.gov")

        try:
            return _parse_obs(data[0], loc)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ProviderError(f"Could not parse METAR response: {exc}")
