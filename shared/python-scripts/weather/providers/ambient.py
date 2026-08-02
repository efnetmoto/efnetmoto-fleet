"""Ambient Weather personal weather station provider.

IMPORTANT: This provider uses the undocumented public device endpoint that
the ambientweather.net web dashboard calls internally. This endpoint carries
no versioning guarantee and may change or require authentication without
notice. It is the primary operational risk for this provider.
"""

import requests

from weather.conversions import degrees_to_cardinal, f_to_c, inches_to_mm, mph_to_kph
from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType, WeatherResult
from weather.providers.base import WeatherProvider

_ENDPOINT = "https://lightning.ambientweather.net/devices"

_AMBIENT_TYPES = {LocationType.AMBIENT_SLUG, LocationType.AMBIENT_URL}

# Fields lastData must carry as live scalars to populate WeatherResult's required
# (non-optional) attributes.
#
# When some stations' outdoor sensor array has gone offline, they stop including
# these in their data push while still reporting indoor/console fields
# (e.g. baromrelin/baromabsin) and retaining a stale `hl` (daily high/low) block
# from earlier readings. When that happens we can't honestly show current conditions,
# so we detect it up front rather than letting a KeyError on an arbitrary field surface
# as a confusing parse error.
_REQUIRED_LIVE_FIELDS = ("tempf", "feelsLike", "humidity", "winddir", "windspeedmph")


class AmbientProvider(WeatherProvider):
    @property
    def name(self) -> str:
        return "Ambient Weather (ambientweather.net)"

    def supports(self, loc: LocationResult) -> bool:
        return loc.type in _AMBIENT_TYPES

    def get_weather(self, loc: LocationResult) -> WeatherResult:
        try:
            resp = requests.get(
                _ENDPOINT,
                params={"public.slug": loc.query},
                timeout=10,
            )
        except requests.Timeout:
            raise ProviderError("Request timed out")
        except requests.ConnectionError:
            raise ProviderError("Could not reach Ambient Weather")

        if resp.status_code != 200:
            try:
                msg = resp.json().get("message", f"HTTP {resp.status_code}")
            except (ValueError, AttributeError):
                msg = f"HTTP {resp.status_code}"
            raise ProviderError(f"Ambient Weather returned {msg}")

        try:
            envelope = resp.json()
        except ValueError:
            raise ProviderError("Unexpected response from Ambient Weather")

        data = envelope.get("data", [])
        if not data:
            raise ProviderError("Station has no data. It may be offline or newly registered.")

        try:
            device = data[0]
            last = device["lastData"]
            info = device["info"]

            if any(field not in last for field in _REQUIRED_LIVE_FIELDS):
                raise ProviderError(
                    "Station data is out of date. It may be offline or between reports."
                )

            location_name = f"{info['name']}, {info['coords']['location']}"

            temp_f = float(last["tempf"])
            temp_c = f_to_c(temp_f)

            feels_like_f = float(last["feelsLike"])
            feels_like_c = f_to_c(feels_like_f)

            humidity_pct = int(last["humidity"])

            wind_dir = degrees_to_cardinal(last["winddir"])
            wind_mph = float(last["windspeedmph"])
            wind_kph = mph_to_kph(wind_mph)

            raw_gust = last.get("windgustmph")
            if raw_gust is not None:
                wind_gust_mph: float | None = float(raw_gust)
                wind_gust_kph: float | None = mph_to_kph(wind_gust_mph)
            else:
                wind_gust_mph = None
                wind_gust_kph = None

            raw_uv = last.get("uv")
            uv_index: float | None = float(raw_uv) if raw_uv is not None else None

            raw_daily_rain = last.get("dailyrainin")
            if raw_daily_rain is not None:
                rain_today_in: float | None = float(raw_daily_rain)
                rain_today_mm: float | None = inches_to_mm(rain_today_in)
            else:
                rain_today_in = None
                rain_today_mm = None

            raw_event_rain = last.get("eventrainin")
            if raw_event_rain is not None:
                event_rain_in: float | None = float(raw_event_rain)
                event_rain_mm: float | None = inches_to_mm(event_rain_in)
            else:
                event_rain_in = None
                event_rain_mm = None

        except ProviderError:
            raise
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ProviderError(f"Could not parse Ambient Weather response: {exc}")

        return WeatherResult(
            location_name=location_name,
            condition=None,
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
            visibility_mi=None,
            visibility_km=None,
            uv_index=uv_index,
            rain_today_in=rain_today_in,
            rain_today_mm=rain_today_mm,
            event_rain_in=event_rain_in,
            event_rain_mm=event_rain_mm,
        )
