import json

import pytest
import requests
import responses as responses_lib

from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType
from weather.providers.aprs import AprsProvider


@pytest.fixture
def provider():
    return AprsProvider()


@pytest.fixture
def aprs_loc():
    return LocationResult(type=LocationType.APRS, query="KSFO", raw="KSFO")


@pytest.fixture
def cwop_aprx_wx_raw_response(fixtures_dir):
    return json.loads((fixtures_dir / "cwop_aprs_wx.json").read_text())


def test_aprs_get_forecast_returns_none(provider, aprs_loc):
    """AprsProvider does not support forecasts - get_forecast returns None"""
    assert provider.get_forecast(aprs_loc) is None


def test_aprs_missing_api_key(monkeypatch):
    monkeypatch.delenv("APRSFI_KEY", raising=False)
    with pytest.raises(RuntimeError, match="APRSFI_KEY"):
        AprsProvider()


def test_aprs_supports_aprs_only(provider):
    assert (
        provider.supports(
            LocationResult(type=LocationType.APRS, query="KK6LVQ-13", raw="KK6LVQ-13")
        )
        is True
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
def test_aprs_happy_path(cwop_aprx_wx_raw_response, provider, aprs_loc):
    responses_lib.add(
        responses_lib.GET,
        provider.aprs_baseurl,
        json=cwop_aprx_wx_raw_response,
        status=200,
    )
    result = provider.get_weather(aprs_loc)
    assert result.location_name == "KK6LVQ-13"
    assert result.temp_c == 24.4
    assert result.temp_f == 75.9
    assert result.feels_like_c is None
    assert result.feels_like_f is None
    assert result.humidity_pct == 43
    assert result.wind_dir == "S"
    assert result.wind_mph == 0.9
    assert result.wind_kph == 1.4
    assert result.wind_gust_mph == 0.9
    assert result.wind_gust_kph == 1.4
    assert result.rain_today_in == 0.10
    assert result.rain_today_mm == 2.5


@responses_lib.activate
def test_aprs_api_error_response(provider, aprs_loc):
    responses_lib.add(
        responses_lib.GET,
        provider.aprs_baseurl,
        status=400,
    )
    with pytest.raises(ProviderError, match="api.aprs.fi returned HTTP 400"):
        provider.get_weather(aprs_loc)


@responses_lib.activate
def test_aprs_timeout(provider, aprs_loc):
    responses_lib.add(
        responses_lib.GET,
        provider.aprs_baseurl,
        body=requests.Timeout(),
    )
    with pytest.raises(ProviderError, match="timed out"):
        provider.get_weather(aprs_loc)


@responses_lib.activate
def test_aprs_cxn_error(provider, aprs_loc):
    responses_lib.add(
        responses_lib.GET,
        provider.aprs_baseurl,
        body=requests.ConnectionError(),
    )
    with pytest.raises(ProviderError, match="Could not reach"):
        provider.get_weather(aprs_loc)


@responses_lib.activate
def test_aprs_no_station_found(provider, aprs_loc):
    responses_lib.add(responses_lib.GET, provider.aprs_baseurl, json={"found": 0})
    with pytest.raises(ProviderError, match="No matching"):
        provider.get_weather(aprs_loc)


@responses_lib.activate
def test_aprs_bad_json(provider, aprs_loc):
    responses_lib.add(
        responses_lib.GET,
        provider.aprs_baseurl,
        body="notjson",
    )
    with pytest.raises(ProviderError, match="Unexpected"):
        provider.get_weather(aprs_loc)


@responses_lib.activate
def test_aprs_unparseable_response(provider, aprs_loc):
    responses_lib.add(
        responses_lib.GET,
        provider.aprs_baseurl,
        json={"found": 1},
    )
    with pytest.raises(ProviderError, match="Could not parse"):
        provider.get_weather(aprs_loc)


@responses_lib.activate
def test_aprs_wind_dir_none(cwop_aprx_wx_raw_response, provider, aprs_loc):
    cwop_aprx_wx_raw_response["entries"][0]["wind_direction"] = None
    responses_lib.add(
        responses_lib.GET,
        provider.aprs_baseurl,
        json=cwop_aprx_wx_raw_response,
        status=200,
    )
    result = provider.get_weather(aprs_loc)
    assert result.wind_dir == "N/A"


@responses_lib.activate
def test_aprs_wind_gust_none(cwop_aprx_wx_raw_response, provider, aprs_loc):
    cwop_aprx_wx_raw_response["entries"][0]["wind_gust"] = None
    responses_lib.add(
        responses_lib.GET,
        provider.aprs_baseurl,
        json=cwop_aprx_wx_raw_response,
        status=200,
    )
    result = provider.get_weather(aprs_loc)
    assert result.wind_gust_kph is None
    assert result.wind_gust_mph is None
