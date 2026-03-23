from dataclasses import dataclass
from enum import Enum, auto


class LocationType(Enum):
    ZIP = auto()
    CITY_STATE = auto()
    IATA = auto()
    ICAO = auto()


class Units(Enum):
    METRIC = "metric"  # metric first (default — matches existing bot behavior)
    IMPERIAL = "imperial"  # imperial first


@dataclass
class LocationResult:
    type: LocationType
    query: str  # canonical string passed to provider
    raw: str  # original user input, for error messages


@dataclass
class WeatherResult:
    location_name: str  # e.g. "San Mateo, California"
    condition: str  # e.g. "Partly Cloudy"
    temp_f: float
    feels_like_f: float | None  # None for METAR (not available)
    temp_c: float
    feels_like_c: float | None  # None for METAR (not available)
    humidity_pct: int | None  # None for METAR when dewpoint unavailable
    wind_dir: str  # e.g. "NW"
    wind_mph: float
    wind_kph: float
    wind_gust_mph: float | None
    wind_gust_kph: float | None
    visibility_mi: float | None  # None when METAR reports unrestricted (9999)
    visibility_km: float | None  # None when METAR reports unrestricted (9999)
    uv_index: float | None = None
    metar_raw: str | None = None  # populated only by AvWxProvider


@dataclass
class ForecastResult:
    """
    Today's forecast data. Populated by WeatherAPIProvider.get_forecast() via
    the /forecast.json endpoint. Passed as optional to format_current() — None
    when the provider does not support forecasts (e.g. AvWxProvider).
    """

    condition: str
    high_c: float
    high_f: float
    low_c: float
    low_f: float


@dataclass
class UserPref:
    location: str | None = None  # None if not yet set
    metar: bool = False  # whether --metar was set when the pref was saved
    units: Units = Units.METRIC  # default matches existing bot behavior
