import json

import pytest
import requests
import responses as responses_lib

from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType
from weather.providers.weatherapi import WeatherAPIProvider


@pytest.fixture
def provider():
    return WeatherAPIProvider()


@pytest.fixture
def weatherapi_raw_resp(fixtures_dir):
    return json.loads((fixtures_dir / "weatherapi_current.json").read_text())


@pytest.fixture
def weatherapi_forecast_raw_resp(fixtures_dir):
    return json.loads((fixtures_dir / "weatherapi_forecast.json").read_text())


@responses_lib.activate
def test_happy_path(provider, ksfo_loc, weatherapi_raw_resp):
    responses_lib.add(
        responses_lib.GET,
        "https://api.weatherapi.com/v1/current.json",
        json=weatherapi_raw_resp,
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


@pytest.mark.parametrize("loc_type", list(LocationType))
def test_supports_all_location_types(provider, loc_type):
    loc = LocationResult(type=loc_type, query="test", raw="test")
    assert provider.supports(loc) is True


@responses_lib.activate
def test_get_forecast_happy_path(provider, weatherapi_forecast_raw_resp, ksfo_loc):
    responses_lib.add(
        responses_lib.GET,
        "https://api.weatherapi.com/v1/forecast.json",
        json=weatherapi_forecast_raw_resp,
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
