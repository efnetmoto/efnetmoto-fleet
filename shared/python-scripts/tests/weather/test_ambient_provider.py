import json
import os

import pytest
import responses as responses_lib

from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType
from weather.providers.ambient import AmbientProvider

_FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "ambient_device.json")
_ENDPOINT = "https://lightning.ambientweather.net/devices"
_SLUG = "aaaabbbbccccddddaaaabbbbccccdddd"


@pytest.fixture
def fixture_data():
    with open(_FIXTURE_PATH) as f:
        return json.load(f)


@pytest.fixture
def slug_loc():
    return LocationResult(type=LocationType.AMBIENT_SLUG, query=_SLUG, raw=_SLUG)


@pytest.fixture
def provider():
    return AmbientProvider()


@responses_lib.activate
def test_slug_returns_weather_result(provider, slug_loc, fixture_data):
    responses_lib.add(
        responses_lib.GET,
        _ENDPOINT,
        json=fixture_data,
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


@responses_lib.activate
def test_condition_is_none(provider, slug_loc, fixture_data):
    responses_lib.add(responses_lib.GET, _ENDPOINT, json=fixture_data, status=200)
    result = provider.get_weather(slug_loc)
    assert result.condition is None


@responses_lib.activate
def test_visibility_is_none(provider, slug_loc, fixture_data):
    responses_lib.add(responses_lib.GET, _ENDPOINT, json=fixture_data, status=200)
    result = provider.get_weather(slug_loc)
    assert result.visibility_mi is None
    assert result.visibility_km is None


@responses_lib.activate
def test_rain_today_populated(provider, slug_loc, fixture_data):
    responses_lib.add(responses_lib.GET, _ENDPOINT, json=fixture_data, status=200)
    result = provider.get_weather(slug_loc)
    assert result.rain_today_in == 0.0
    assert result.rain_today_mm == 0.0


@responses_lib.activate
def test_wind_dir_is_cardinal(provider, slug_loc, fixture_data):
    responses_lib.add(responses_lib.GET, _ENDPOINT, json=fixture_data, status=200)
    result = provider.get_weather(slug_loc)
    assert result.wind_dir == "NNW"


@responses_lib.activate
def test_location_name(provider, slug_loc, fixture_data):
    responses_lib.add(responses_lib.GET, _ENDPOINT, json=fixture_data, status=200)
    result = provider.get_weather(slug_loc)
    assert result.location_name == "Test Station, Testville"


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
    import requests as req_lib

    responses_lib.add(
        responses_lib.GET,
        _ENDPOINT,
        body=req_lib.Timeout(),
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
