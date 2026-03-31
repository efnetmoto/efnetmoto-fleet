import json

import pytest
import requests
import responses as responses_lib

from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType
from weather.providers.avwx import AvWxProvider


@pytest.fixture
def avwx_metar_raw_response(fixtures_dir):
    return json.loads((fixtures_dir / "avwx_metar.json").read_text())


@pytest.fixture
def provider():
    return AvWxProvider()


def test_avwx_get_forecast_returns_none(provider, ksfo_loc):
    """AvWxProvider does not support forecasts — get_forecast returns None."""
    assert provider.get_forecast(ksfo_loc) is None


def test_avwx_supports_icao_only(provider):
    assert (
        provider.supports(LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")) is True
    )
    assert (
        provider.supports(LocationResult(type=LocationType.ZIP, query="94025", raw="94025"))
        is False
    )
    assert (
        provider.supports(LocationResult(type=LocationType.IATA, query="SFO", raw="SFO")) is False
    )
    assert (
        provider.supports(LocationResult(type=LocationType.CITY_STATE, query="SF", raw="SF"))
        is False
    )


@responses_lib.activate
def test_avwx_happy_path(avwx_metar_raw_response, provider, ksfo_loc):
    responses_lib.add(
        responses_lib.GET,
        "https://aviationweather.gov/api/data/metar",
        json=avwx_metar_raw_response,
        status=200,
    )
    result = provider.get_weather(ksfo_loc)
    assert result.location_name == "KSFO"
    assert result.temp_c == 16.0
    assert result.metar_raw == "METAR KSFO 141956Z 28013KT 10SM FEW020 16/09 A2992 RMK AO2 SLP130"
    assert result.feels_like_c is None
    assert result.feels_like_f is None
    assert result.humidity_pct is not None  # calculated from dewpoint


@responses_lib.activate
def test_timeout(provider, ksfo_loc):
    responses_lib.add(
        responses_lib.GET,
        "https://aviationweather.gov/api/data/metar",
        body=requests.Timeout(),
    )
    with pytest.raises(ProviderError, match="timed out"):
        provider.get_weather(ksfo_loc)


@responses_lib.activate
def test_connection_error(provider, ksfo_loc):
    responses_lib.add(
        responses_lib.GET,
        "https://aviationweather.gov/api/data/metar",
        body=requests.ConnectionError(),
    )
    with pytest.raises(ProviderError, match="Could not reach"):
        provider.get_weather(ksfo_loc)


@responses_lib.activate
def test_api_error_response(provider, ksfo_loc):
    responses_lib.add(
        responses_lib.GET,
        "https://aviationweather.gov/api/data/metar",
        status=400,
    )
    with pytest.raises(ProviderError, match="returned HTTP 400"):
        provider.get_weather(ksfo_loc)


@pytest.mark.parametrize("wdir, expected", [("VRB", "VRB"), (None, "N/A")])
@responses_lib.activate
def test_wind_direction_variable(wdir, expected, avwx_metar_raw_response, provider, ksfo_loc):
    avwx_metar_raw_response[0]["wdir"] = wdir
    responses_lib.add(
        responses_lib.GET,
        "https://aviationweather.gov/api/data/metar",
        json=avwx_metar_raw_response,
        status=200,
    )
    result = provider.get_weather(ksfo_loc)
    assert result.wind_dir == expected


@responses_lib.activate
def test_no_flt_cat_or_wxstring_returns_unk(avwx_metar_raw_response, provider, ksfo_loc):
    avwx_metar_raw_response[0]["flight_category"] = None
    avwx_metar_raw_response[0]["wxString"] = None
    responses_lib.add(
        responses_lib.GET,
        "https://aviationweather.gov/api/data/metar",
        json=avwx_metar_raw_response,
        status=200,
    )
    result = provider.get_weather(ksfo_loc)
    assert result.condition == "Unknown"


@pytest.mark.parametrize(
    "visibility, expected_mi, expected_km",
    [
        (50, 50, 80.5),
        ("50", 50, 80.5),
        ("10+", None, None),
    ],
)
@responses_lib.activate
def test_avwx_visibility_string_or_int(
    visibility, expected_mi, expected_km, avwx_metar_raw_response, provider, ksfo_loc
):
    avwx_metar_raw_response[0]["visib"] = visibility
    responses_lib.add(
        responses_lib.GET,
        "https://aviationweather.gov/api/data/metar",
        json=avwx_metar_raw_response,
        status=200,
    )
    result = provider.get_weather(ksfo_loc)
    assert result.visibility_mi == expected_mi
    assert result.visibility_km == expected_km


@responses_lib.activate
def test_avwx_station_not_found(provider):
    responses_lib.add(
        responses_lib.GET,
        "https://aviationweather.gov/api/data/metar",
        status=204,
    )
    loc = LocationResult(type=LocationType.ICAO, query="ZZZZ", raw="ZZZZ")
    with pytest.raises(ProviderError, match="No METAR data found"):
        provider.get_weather(loc)
