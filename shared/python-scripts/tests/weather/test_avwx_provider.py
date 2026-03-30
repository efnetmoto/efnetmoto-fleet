import json
from pathlib import Path

import pytest
import responses as responses_lib

from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType
from weather.providers.avwx import AvWxProvider
from weather.providers.weatherapi import WeatherAPIProvider
from weather.router import ProviderRouter

FIXTURES = Path(__file__).parent / "fixtures"


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
def test_avwx_visibility_int():
    data = json.loads((FIXTURES / "avwx_metar.json").read_text())
    data[0]["visib"] = 50
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
    assert result.metar_raw == "KSFO 141956Z 28013KT 10SM FEW020 16/09 A2992 RMK AO2 SLP130"
    assert result.visibility_mi == 50
    assert result.visibility_km == 80.5


@responses_lib.activate
def test_avwx_visibility_string():
    data = json.loads((FIXTURES / "avwx_metar.json").read_text())
    data[0]["visib"] = "10+"
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
    assert result.metar_raw == "KSFO 141956Z 28013KT 10SM FEW020 16/09 A2992 RMK AO2 SLP130"
    assert result.visibility_mi is None
    assert result.visibility_km is None


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


def test_router_metar_prefers_avwx(monkeypatch):
    monkeypatch.setenv("WEATHERAPI_KEY", "test-key-12345")
    wapi = WeatherAPIProvider()
    avwx = AvWxProvider()
    router = ProviderRouter([wapi, avwx])
    loc = LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")
    selected = router.route(loc, metar=True)
    assert isinstance(selected, AvWxProvider)


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
