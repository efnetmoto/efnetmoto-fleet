import json
from pathlib import Path

import pytest
import requests
import responses as responses_lib

from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType
from weather.providers.avwx import AvWxProvider
from weather.providers.weatherapi import WeatherAPIProvider
from weather.router import ProviderRouter

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("WEATHERAPI_KEY", "test-key-12345")
    return WeatherAPIProvider()


@pytest.fixture
def ksfo_loc():
    return LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")


# WeatherAPIProvider — get_weather


@responses_lib.activate
def test_happy_path(provider, ksfo_loc):
    data = json.loads((FIXTURES / "weatherapi_current.json").read_text())
    responses_lib.add(
        responses_lib.GET,
        "https://api.weatherapi.com/v1/current.json",
        json=data,
        status=200,
    )
    result = provider.get_weather(ksfo_loc)
    assert result.location_name == "San Francisco, California"
    assert result.condition == "Partly Cloudy"
    assert result.temp_c == 16.0
    assert result.temp_f == 60.8
    assert result.humidity_pct == 72
    assert result.wind_dir == "W"
    assert result.uv_index == 3.0


@responses_lib.activate
def test_api_error_response(provider, ksfo_loc):
    responses_lib.add(
        responses_lib.GET,
        "https://api.weatherapi.com/v1/current.json",
        json={"error": {"code": 1006, "message": "No matching location found."}},
        status=400,
    )
    with pytest.raises(ProviderError, match="No matching location found"):
        provider.get_weather(ksfo_loc)


@responses_lib.activate
def test_timeout(provider, ksfo_loc):
    responses_lib.add(
        responses_lib.GET,
        "https://api.weatherapi.com/v1/current.json",
        body=requests.Timeout(),
    )
    with pytest.raises(ProviderError, match="timed out"):
        provider.get_weather(ksfo_loc)


@responses_lib.activate
def test_connection_error(provider, ksfo_loc):
    responses_lib.add(
        responses_lib.GET,
        "https://api.weatherapi.com/v1/current.json",
        body=requests.ConnectionError(),
    )
    with pytest.raises(ProviderError, match="Could not reach"):
        provider.get_weather(ksfo_loc)


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("WEATHERAPI_KEY", raising=False)
    with pytest.raises(RuntimeError, match="WEATHERAPI_KEY"):
        WeatherAPIProvider()


def test_supports_all_location_types(provider):
    for loc_type in LocationType:
        loc = LocationResult(type=loc_type, query="test", raw="test")
        assert provider.supports(loc) is True


# WeatherAPIProvider — get_forecast


@responses_lib.activate
def test_get_forecast_happy_path(provider, ksfo_loc):
    data = json.loads((FIXTURES / "weatherapi_forecast.json").read_text())
    responses_lib.add(
        responses_lib.GET,
        "https://api.weatherapi.com/v1/forecast.json",
        json=data,
        status=200,
    )
    forecast = provider.get_forecast(ksfo_loc)
    assert forecast is not None
    assert forecast.condition == "Partly Cloudy"
    assert forecast.high_c == 19.0
    assert forecast.high_f == 66.2
    assert forecast.low_c == 11.0
    assert forecast.low_f == 51.8


@responses_lib.activate
def test_get_forecast_error_returns_provider_error(provider, ksfo_loc):
    responses_lib.add(
        responses_lib.GET,
        "https://api.weatherapi.com/v1/forecast.json",
        json={"error": {"code": 1006, "message": "No matching location found."}},
        status=400,
    )
    with pytest.raises(ProviderError):
        provider.get_forecast(ksfo_loc)


# AvWxProvider


def test_avwx_get_forecast_returns_none():
    """AvWxProvider does not support forecasts — get_forecast returns None."""
    p = AvWxProvider()
    loc = LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")
    assert p.get_forecast(loc) is None


def test_avwx_supports_icao_only():
    p = AvWxProvider()
    assert p.supports(LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")) is True
    assert p.supports(LocationResult(type=LocationType.ZIP, query="94025", raw="94025")) is False
    assert p.supports(LocationResult(type=LocationType.IATA, query="SFO", raw="SFO")) is False
    assert p.supports(LocationResult(type=LocationType.CITY_STATE, query="SF", raw="SF")) is False


@responses_lib.activate
def test_avwx_happy_path():
    data = json.loads((FIXTURES / "avwx_metar.json").read_text())
    responses_lib.add(
        responses_lib.GET,
        "https://aviationweather.gov/api/data/metar",
        json=data,
        status=200,
    )
    p = AvWxProvider()
    loc = LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")
    result = p.get_weather(loc)
    assert result.location_name == "KSFO"
    assert result.temp_c == 16.0
    assert result.metar_raw == "KSFO 141956Z 28013KT 10SM FEW020 16/09 A2992 RMK AO2 SLP130"
    assert result.feels_like_c is None
    assert result.feels_like_f is None
    assert result.humidity_pct is not None  # calculated from dewpoint


@responses_lib.activate
def test_avwx_station_not_found():
    responses_lib.add(
        responses_lib.GET,
        "https://aviationweather.gov/api/data/metar",
        json=[],
        status=200,
    )
    p = AvWxProvider()
    loc = LocationResult(type=LocationType.ICAO, query="ZZZZ", raw="ZZZZ")
    with pytest.raises(ProviderError, match="No METAR data found"):
        p.get_weather(loc)


# ProviderRouter


def test_router_metar_prefers_avwx(monkeypatch):
    monkeypatch.setenv("WEATHERAPI_KEY", "test-key-12345")
    wapi = WeatherAPIProvider()
    avwx = AvWxProvider()
    router = ProviderRouter([wapi, avwx])
    loc = LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")
    selected = router.route(loc, metar=True)
    assert isinstance(selected, AvWxProvider)


def test_router_no_metar_prefers_weatherapi(monkeypatch):
    monkeypatch.setenv("WEATHERAPI_KEY", "test-key-12345")
    wapi = WeatherAPIProvider()
    avwx = AvWxProvider()
    router = ProviderRouter([wapi, avwx])
    loc = LocationResult(type=LocationType.ZIP, query="94025", raw="94025")
    selected = router.route(loc, metar=False)
    assert isinstance(selected, WeatherAPIProvider)


def test_router_no_provider_raises(monkeypatch):
    monkeypatch.setenv("WEATHERAPI_KEY", "test-key-12345")
    avwx = AvWxProvider()
    router = ProviderRouter([avwx])  # only avwx, which only handles ICAO
    loc = LocationResult(type=LocationType.ZIP, query="94025", raw="94025")
    with pytest.raises(ProviderError, match="No provider available"):
        router.route(loc)


def test_router_icao_without_metar_raises(monkeypatch):
    """ICAO codes without --metar are rejected with an actionable error."""
    monkeypatch.setenv("WEATHERAPI_KEY", "test-key-12345")
    wapi = WeatherAPIProvider()
    avwx = AvWxProvider()
    router = ProviderRouter([wapi, avwx])
    loc = LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")
    with pytest.raises(ProviderError, match="--metar"):
        router.route(loc, metar=False)
