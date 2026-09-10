import copy
import json

import pytest
import requests
import responses as responses_lib

from weather.exceptions import ProviderError
from weather.models import FormatMode, LocationResult, LocationType
from weather.providers.nws import NationalWeatherServiceProvider

_OBSERVATION_URL = "https://api.weather.gov/stations/{station_id}/observations/latest"
_STATION_URL = "https://api.weather.gov/stations/{station_id}"
_POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"
_FORECAST_URL = "https://api.weather.gov/gridpoints/BOU/75,66/forecast"


@pytest.fixture
def provider():
    return NationalWeatherServiceProvider()


@pytest.fixture
def nws_loc():
    return LocationResult(type=LocationType.NWS_STATION, query="KDEN", raw="KDEN")


@pytest.fixture
def nws_obs_raw_response(fixtures_dir):
    return json.loads((fixtures_dir / "nws_observation.json").read_text())


@pytest.fixture
def nws_station_raw_response(fixtures_dir):
    return json.loads((fixtures_dir / "nws_station.json").read_text())


@pytest.fixture
def nws_forecast_raw_response(fixtures_dir):
    return json.loads((fixtures_dir / "nws_forecast.json").read_text())


@pytest.fixture
def nws_points_url(nws_station_raw_response):
    coords = nws_station_raw_response["geometry"]["coordinates"]
    return _POINTS_URL.format(lat=coords[1], lon=coords[0])


@responses_lib.activate
def test_nws_get_forecast_happy_path(
    provider, nws_loc, nws_station_raw_response, nws_forecast_raw_response, nws_points_url
):
    responses_lib.add(
        responses_lib.GET,
        _STATION_URL.format(station_id="KDEN"),
        json=nws_station_raw_response,
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        nws_points_url,
        json={"properties": {"forecast": _FORECAST_URL}},
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        _FORECAST_URL,
        json=nws_forecast_raw_response,
        status=200,
    )
    forecast = provider.get_forecast(nws_loc)
    assert forecast is not None
    assert forecast.condition == "Sunny"
    assert forecast.high_f == 80
    assert forecast.high_c == 26.7
    assert forecast.low_f == 55
    assert forecast.low_c == 12.8


@responses_lib.activate
def test_nws_forecast_station_timeout(provider, nws_loc):
    responses_lib.add(
        responses_lib.GET,
        _STATION_URL.format(station_id="KDEN"),
        body=requests.Timeout(),
    )
    with pytest.raises(ProviderError, match="timed out"):
        provider.get_forecast(nws_loc)


@responses_lib.activate
def test_nws_forecast_station_http_error(provider, nws_loc):
    responses_lib.add(
        responses_lib.GET,
        _STATION_URL.format(station_id="KDEN"),
        status=500,
    )
    with pytest.raises(ProviderError, match="HTTP 500"):
        provider.get_forecast(nws_loc)


@responses_lib.activate
def test_nws_forecast_points_timeout(provider, nws_loc, nws_station_raw_response, nws_points_url):
    responses_lib.add(
        responses_lib.GET,
        _STATION_URL.format(station_id="KDEN"),
        json=nws_station_raw_response,
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        nws_points_url,
        body=requests.Timeout(),
    )
    with pytest.raises(ProviderError, match="timed out"):
        provider.get_forecast(nws_loc)


@responses_lib.activate
def test_nws_forecast_points_http_error(
    provider, nws_loc, nws_station_raw_response, nws_points_url
):
    responses_lib.add(
        responses_lib.GET,
        _STATION_URL.format(station_id="KDEN"),
        json=nws_station_raw_response,
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        nws_points_url,
        status=500,
    )
    with pytest.raises(ProviderError, match="HTTP 500"):
        provider.get_forecast(nws_loc)


@responses_lib.activate
def test_nws_forecast_timeout(provider, nws_loc, nws_station_raw_response, nws_points_url):
    responses_lib.add(
        responses_lib.GET,
        _STATION_URL.format(station_id="KDEN"),
        json=nws_station_raw_response,
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        nws_points_url,
        json={"properties": {"forecast": _FORECAST_URL}},
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        _FORECAST_URL,
        body=requests.Timeout(),
    )
    with pytest.raises(ProviderError, match="timed out"):
        provider.get_forecast(nws_loc)


@responses_lib.activate
def test_nws_forecast_http_error(provider, nws_loc, nws_station_raw_response, nws_points_url):
    responses_lib.add(
        responses_lib.GET,
        _STATION_URL.format(station_id="KDEN"),
        json=nws_station_raw_response,
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        nws_points_url,
        json={"properties": {"forecast": _FORECAST_URL}},
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        _FORECAST_URL,
        status=500,
    )
    with pytest.raises(ProviderError, match="HTTP 500"):
        provider.get_forecast(nws_loc)


@responses_lib.activate
def test_nws_forecast_empty_periods(provider, nws_loc, nws_station_raw_response, nws_points_url):
    responses_lib.add(
        responses_lib.GET,
        _STATION_URL.format(station_id="KDEN"),
        json=nws_station_raw_response,
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        nws_points_url,
        json={"properties": {"forecast": _FORECAST_URL}},
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        _FORECAST_URL,
        json={"properties": {"periods": []}},
        status=200,
    )
    with pytest.raises(ProviderError, match="no periods"):
        provider.get_forecast(nws_loc)


@responses_lib.activate
def test_nws_forecast_no_daytime_period(
    provider, nws_loc, nws_station_raw_response, nws_forecast_raw_response, nws_points_url
):
    obs = copy.deepcopy(nws_forecast_raw_response)
    for p in obs["properties"]["periods"]:
        p["isDaytime"] = False
    responses_lib.add(
        responses_lib.GET,
        _STATION_URL.format(station_id="KDEN"),
        json=nws_station_raw_response,
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        nws_points_url,
        json={"properties": {"forecast": _FORECAST_URL}},
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        _FORECAST_URL,
        json=obs,
        status=200,
    )
    with pytest.raises(ProviderError, match="both high and low"):
        provider.get_forecast(nws_loc)


@responses_lib.activate
def test_nws_forecast_no_nighttime_period(
    provider, nws_loc, nws_station_raw_response, nws_forecast_raw_response, nws_points_url
):
    obs = copy.deepcopy(nws_forecast_raw_response)
    for p in obs["properties"]["periods"]:
        p["isDaytime"] = True
    responses_lib.add(
        responses_lib.GET,
        _STATION_URL.format(station_id="KDEN"),
        json=nws_station_raw_response,
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        nws_points_url,
        json={"properties": {"forecast": _FORECAST_URL}},
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        _FORECAST_URL,
        json=obs,
        status=200,
    )
    with pytest.raises(ProviderError, match="both high and low"):
        provider.get_forecast(nws_loc)


@responses_lib.activate
def test_nws_forecast_missing_shortForecast(
    provider, nws_loc, nws_station_raw_response, nws_forecast_raw_response, nws_points_url
):
    obs = copy.deepcopy(nws_forecast_raw_response)
    obs["properties"]["periods"][0]["shortForecast"] = None
    responses_lib.add(
        responses_lib.GET,
        _STATION_URL.format(station_id="KDEN"),
        json=nws_station_raw_response,
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        nws_points_url,
        json={"properties": {"forecast": _FORECAST_URL}},
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        _FORECAST_URL,
        json=obs,
        status=200,
    )
    forecast = provider.get_forecast(nws_loc)
    assert forecast is not None
    assert forecast.condition == "Unknown"


@responses_lib.activate
def test_nws_forecast_qv_temperature(
    provider, nws_loc, nws_station_raw_response, nws_forecast_raw_response, nws_points_url
):
    obs = copy.deepcopy(nws_forecast_raw_response)
    obs["properties"]["periods"][0]["temperature"] = {
        "value": 80,
        "unitCode": "wmoUnit:degC",
    }
    obs["properties"]["periods"][1]["temperature"] = {
        "value": 13,
        "unitCode": "wmoUnit:degC",
    }
    responses_lib.add(
        responses_lib.GET,
        _STATION_URL.format(station_id="KDEN"),
        json=nws_station_raw_response,
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        nws_points_url,
        json={"properties": {"forecast": _FORECAST_URL}},
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        _FORECAST_URL,
        json=obs,
        status=200,
    )
    forecast = provider.get_forecast(nws_loc)
    assert forecast is not None
    assert forecast.high_f == 80
    assert forecast.low_f == 13


@pytest.mark.parametrize(
    "loc_type, expected",
    [
        (LocationType.NWS_STATION, True),
        (LocationType.ICAO, True),
        (LocationType.ZIP, False),
        (LocationType.CITY_STATE, False),
        (LocationType.IATA, False),
        (LocationType.AMBIENT_SLUG, False),
        (LocationType.AMBIENT_URL, False),
        (LocationType.APRS, False),
    ],
)
def test_nws_supports_types(provider, loc_type, expected):
    """NWS accepts station IDs and ICAO codes only — not city/state, ZIP, etc."""
    loc = LocationResult(type=loc_type, query="KDEN", raw="KDEN")
    assert provider.supports(loc) is expected


def test_nws_identity_id(provider):
    assert provider.id == "nws"


def test_nws_identity_preferred_types(provider):
    assert provider.preferred_types == frozenset()


def test_nws_identity_format_mode(provider):
    assert provider.format_mode == FormatMode.CURRENT


@responses_lib.activate
def test_nws_happy_path(nws_obs_raw_response, provider, nws_loc):
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json=nws_obs_raw_response,
        status=200,
    )
    result = provider.get_weather(nws_loc)
    assert result.location_name == "Denver, Denver International Airport (KDEN)"
    assert result.condition == "Mostly Cloudy"
    assert result.temp_c == 25.6
    assert result.temp_f == 78.1
    assert result.feels_like_c == 26.3
    assert result.feels_like_f == 79.3
    assert result.humidity_pct == 39
    assert result.wind_dir == "W"
    assert result.wind_kph == 15.2
    assert result.wind_mph == 9.4
    assert result.wind_gust_kph == 25.3
    assert result.wind_gust_mph == 15.7
    assert result.visibility_km == 16.1
    assert result.visibility_mi == 10.0


@responses_lib.activate
def test_nws_timeout(provider, nws_loc):
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        body=requests.Timeout(),
    )
    with pytest.raises(ProviderError, match="timed out"):
        provider.get_weather(nws_loc)


@responses_lib.activate
def test_nws_connection_error(provider, nws_loc):
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        body=requests.ConnectionError(),
    )
    with pytest.raises(ProviderError, match="Could not reach"):
        provider.get_weather(nws_loc)


@responses_lib.activate
def test_nws_station_not_found(provider, nws_loc):
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json={"status": "404", "title": "Not Found", "detail": "Not Found"},
        status=404,
    )
    with pytest.raises(ProviderError, match="not found"):
        provider.get_weather(nws_loc)


@responses_lib.activate
def test_nws_http_error(provider, nws_loc):
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        status=500,
    )
    with pytest.raises(ProviderError, match="HTTP 500"):
        provider.get_weather(nws_loc)


@responses_lib.activate
def test_nws_bad_json(provider, nws_loc):
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        body="notjson",
    )
    with pytest.raises(ProviderError, match="Unexpected"):
        provider.get_weather(nws_loc)


@responses_lib.activate
def test_nws_null_temperature(provider, nws_loc, nws_obs_raw_response):
    """A station not reporting temperature raises a clear error, not 0.0C/32.0F."""
    obs = copy.deepcopy(nws_obs_raw_response)
    obs["properties"]["temperature"]["value"] = None
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json=obs,
        status=200,
    )
    with pytest.raises(ProviderError, match="not reporting temperature"):
        provider.get_weather(nws_loc)


@responses_lib.activate
def test_nws_null_wind_speed(provider, nws_loc, nws_obs_raw_response):
    """Null wind speed defaults to 0.0 (calm), not an error."""
    obs = copy.deepcopy(nws_obs_raw_response)
    obs["properties"]["windSpeed"]["value"] = None
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json=obs,
        status=200,
    )
    result = provider.get_weather(nws_loc)
    assert result.wind_kph == 0.0
    assert result.wind_mph == 0.0


@responses_lib.activate
def test_nws_null_wind_gust(provider, nws_loc, nws_obs_raw_response):
    obs = copy.deepcopy(nws_obs_raw_response)
    obs["properties"]["windGust"]["value"] = None
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json=obs,
        status=200,
    )
    result = provider.get_weather(nws_loc)
    assert result.wind_gust_kph is None
    assert result.wind_gust_mph is None


@responses_lib.activate
def test_nws_empty_text_description(provider, nws_loc, nws_obs_raw_response):
    """Empty string textDescription maps to None condition."""
    obs = copy.deepcopy(nws_obs_raw_response)
    obs["properties"]["textDescription"] = ""
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json=obs,
        status=200,
    )
    result = provider.get_weather(nws_loc)
    assert result.condition is None


@responses_lib.activate
def test_nws_null_text_description(provider, nws_loc, nws_obs_raw_response):
    obs = copy.deepcopy(nws_obs_raw_response)
    obs["properties"]["textDescription"] = None
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json=obs,
        status=200,
    )
    result = provider.get_weather(nws_loc)
    assert result.condition is None


@responses_lib.activate
def test_nws_null_humidity(provider, nws_loc, nws_obs_raw_response):
    obs = copy.deepcopy(nws_obs_raw_response)
    obs["properties"]["relativeHumidity"]["value"] = None
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json=obs,
        status=200,
    )
    result = provider.get_weather(nws_loc)
    assert result.humidity_pct is None


@responses_lib.activate
def test_nws_wind_chill_preferred_over_heat_index(provider, nws_loc, nws_obs_raw_response):
    """When both windChill and heatIndex are present, windChill wins."""
    obs = copy.deepcopy(nws_obs_raw_response)
    obs["properties"]["windChill"]["value"] = 10.0
    obs["properties"]["heatIndex"]["value"] = 30.0
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json=obs,
        status=200,
    )
    result = provider.get_weather(nws_loc)
    assert result.feels_like_c == 10.0
    assert result.feels_like_f == 50.0


@responses_lib.activate
def test_nws_no_feels_like(provider, nws_loc, nws_obs_raw_response):
    """Both windChill and heatIndex null — feels_like is None."""
    obs = copy.deepcopy(nws_obs_raw_response)
    obs["properties"]["windChill"]["value"] = None
    obs["properties"]["heatIndex"]["value"] = None
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json=obs,
        status=200,
    )
    result = provider.get_weather(nws_loc)
    assert result.feels_like_c is None
    assert result.feels_like_f is None


@responses_lib.activate
def test_nws_visibility(provider, nws_loc, nws_obs_raw_response):
    """Visibility in meters is converted to km and miles."""
    obs = copy.deepcopy(nws_obs_raw_response)
    obs["properties"]["visibility"]["value"] = 16093.44
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json=obs,
        status=200,
    )
    result = provider.get_weather(nws_loc)
    assert result.visibility_km == 16.1
    assert result.visibility_mi == 10.0


@responses_lib.activate
def test_nws_null_visibility(provider, nws_loc, nws_obs_raw_response):
    obs = copy.deepcopy(nws_obs_raw_response)
    obs["properties"]["visibility"]["value"] = None
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json=obs,
        status=200,
    )
    result = provider.get_weather(nws_loc)
    assert result.visibility_km is None
    assert result.visibility_mi is None


@responses_lib.activate
def test_nws_null_wind_direction(provider, nws_loc, nws_obs_raw_response):
    obs = copy.deepcopy(nws_obs_raw_response)
    obs["properties"]["windDirection"]["value"] = None
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json=obs,
        status=200,
    )
    result = provider.get_weather(nws_loc)
    assert result.wind_dir == "N/A"


@responses_lib.activate
def test_nws_unparseable_response(provider, nws_loc):
    """Response with no 'properties' key raises a parse error."""
    responses_lib.add(
        responses_lib.GET,
        _OBSERVATION_URL.format(station_id="KDEN"),
        json={"unexpected": "structure"},
        status=200,
    )
    with pytest.raises(ProviderError, match="Could not parse"):
        provider.get_weather(nws_loc)
