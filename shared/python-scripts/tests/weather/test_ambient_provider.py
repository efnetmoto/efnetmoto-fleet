import json

import pytest
import requests
import responses as responses_lib

from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType
from weather.providers.ambient import AmbientProvider

_ENDPOINT = "https://lightning.ambientweather.net/devices"
_SLUG = "aaaabbbbccccddddaaaabbbbccccdddd"


@pytest.fixture
def ambient_devices_raw_resp(fixtures_dir):
    with open(fixtures_dir / "ambient_device.json") as f:
        return json.load(f)


@pytest.fixture
def slug_loc():
    return LocationResult(type=LocationType.AMBIENT_SLUG, query=_SLUG, raw=_SLUG)


@pytest.fixture
def provider():
    return AmbientProvider()


def test_ambient_get_forecast_returns_none(provider, slug_loc):
    """AmbientProvider does not support forecasts - get_forecast returns None"""
    assert provider.get_forecast(slug_loc) is None


@responses_lib.activate
def test_slug_returns_weather_result(provider, slug_loc, ambient_devices_raw_resp):
    responses_lib.add(
        responses_lib.GET,
        _ENDPOINT,
        json=ambient_devices_raw_resp,
        status=200,
    )
    result = provider.get_weather(slug_loc)
    assert result.location_name == "Test Station, Testville"
    assert result.temp_f == 82.0
    assert result.temp_c == 27.8
    assert result.feels_like_f == 80.4
    assert result.feels_like_c == 26.9
    assert result.humidity_pct == 29
    assert result.wind_dir == "NNW"
    assert result.wind_mph == 3.6
    assert result.wind_kph == 5.8
    assert result.condition is None
    assert result.visibility_mi is None
    assert result.visibility_km is None
    assert result.rain_today_in == 0.0
    assert result.rain_today_mm == 0.0


@responses_lib.activate
def test_connection_error(provider, ksfo_loc):
    responses_lib.add(
        responses_lib.GET,
        _ENDPOINT,
        body=requests.ConnectionError(),
    )
    with pytest.raises(ProviderError, match="Could not reach"):
        provider.get_weather(ksfo_loc)


@responses_lib.activate
def test_non_200_raises_provider_error(provider, slug_loc):
    responses_lib.add(
        responses_lib.GET,
        _ENDPOINT,
        json={"message": "kablooey"},
        status=400,
    )
    with pytest.raises(ProviderError, match="kablooey"):
        provider.get_weather(slug_loc)


@responses_lib.activate
def test_empty_data_raises_provider_error(provider, slug_loc):
    responses_lib.add(
        responses_lib.GET,
        _ENDPOINT,
        json={"total": 0, "limit": 15, "skip": 0, "data": []},
        status=200,
    )
    with pytest.raises(ProviderError, match="offline"):
        provider.get_weather(slug_loc)


@responses_lib.activate
def test_http_500_raises_provider_error(provider, slug_loc):
    responses_lib.add(responses_lib.GET, _ENDPOINT, json={}, status=500)
    with pytest.raises(ProviderError):
        provider.get_weather(slug_loc)


@responses_lib.activate
def test_timeout_raises_provider_error(provider, slug_loc):
    responses_lib.add(
        responses_lib.GET,
        _ENDPOINT,
        body=requests.Timeout(),
    )
    with pytest.raises(ProviderError, match="timed out"):
        provider.get_weather(slug_loc)


def test_supports_slug(provider):
    loc = LocationResult(type=LocationType.AMBIENT_SLUG, query=_SLUG, raw=_SLUG)
    assert provider.supports(loc) is True


def test_supports_url(provider):
    url = f"https://ambientweather.net/dashboard/{_SLUG}"
    loc = LocationResult(type=LocationType.AMBIENT_URL, query=_SLUG, raw=url)
    assert provider.supports(loc) is True


def test_does_not_support_zip(provider):
    loc = LocationResult(type=LocationType.ZIP, query="94025", raw="94025")
    assert provider.supports(loc) is False
