import pytest

from weather.formatter import format_current, format_metar
from weather.models import ForecastResult, Units, WeatherResult


@pytest.fixture
def sjc_result():
    return WeatherResult(
        location_name="San Jose International Airport, San Jose",
        condition="Clear sky",
        temp_c=28.9,
        temp_f=84.0,
        feels_like_c=28.9,
        feels_like_f=84.1,
        humidity_pct=45,
        wind_dir="N",
        wind_mph=3.4,
        wind_kph=5.5,
        wind_gust_mph=None,
        wind_gust_kph=None,
        visibility_mi=10.0,
        visibility_km=16.1,
        uv_index=8.0,
    )


@pytest.fixture
def sjc_forecast():
    return ForecastResult(
        condition="Clear sky",
        high_c=31.0,
        high_f=87.8,
        low_c=12.6,
        low_f=54.7,
    )


def test_format_current_metric_with_forecast(sjc_result, sjc_forecast):
    out = format_current(sjc_result, forecast=sjc_forecast, units=Units.METRIC)
    expected = (
        "San Jose International Airport, San Jose :: Clear sky :: "
        "28.9C/84.0F (Humidity: 45%) | Feels like: 28.9C/84.1F | "
        "Wind: N at 5.5kph/3.4mph | Today: Clear sky. High 31.0C/87.8F - Low 12.6C/54.7F"
    )
    assert out == expected


def test_format_current_metric_no_forecast(sjc_result):
    out = format_current(sjc_result, forecast=None, units=Units.METRIC)
    assert "Today:" not in out
    assert "28.9C/84.0F" in out
    assert "(Humidity: 45%)" in out


def test_format_current_imperial(sjc_result):
    out = format_current(sjc_result, units=Units.IMPERIAL)
    assert "84.0F/28.9C" in out
    assert "3.4mph/5.5kph" in out
    assert "84.1F/28.9C" in out  # feels like


def test_format_current_separator_style(sjc_result):
    out = format_current(sjc_result, units=Units.METRIC)
    parts = out.split(" :: ")
    assert len(parts) >= 3
    assert parts[0] == "San Jose International Airport, San Jose"
    assert parts[1] == "Clear sky"


@pytest.fixture
def ksfo_metar_result():
    return WeatherResult(
        location_name="KSFO",
        condition="",
        temp_c=16.0,
        temp_f=60.8,
        feels_like_c=None,
        feels_like_f=None,
        humidity_pct=None,
        wind_dir="W",
        wind_mph=9.4,
        wind_kph=15.1,
        wind_gust_mph=None,
        wind_gust_kph=None,
        visibility_mi=10.0,
        visibility_km=16.1,
        metar_raw="METAR KSFO 141956Z 28013KT 10SM FEW020 16/09 A2992",
    )


def test_format_metar_metric(ksfo_metar_result):
    out = format_metar(ksfo_metar_result, units=Units.METRIC)
    assert "METAR" in out
    assert "KSFO 141956Z 28013KT 10SM FEW020 16/09 A2992" in out
    assert "16.0C/60.8F" in out
    assert "15.1kph/9.4mph" in out
    assert "10.0SM" in out


def test_format_metar_visibility_nonetype_imperial(ksfo_metar_result):
    ksfo_metar_result.visibility_mi = None
    ksfo_metar_result.visibility_km = None
    out = format_metar(ksfo_metar_result, units=Units.IMPERIAL)
    assert "> 10 SM" in out


def test_format_metar_visibility_nonetype_metric(ksfo_metar_result):
    ksfo_metar_result.visibility_mi = None
    ksfo_metar_result.visibility_km = None
    out = format_metar(ksfo_metar_result, units=Units.METRIC)
    assert "> 10 SM" in out


def test_format_metar_requires_metar_raw():
    result = WeatherResult(
        location_name="KSFO",
        condition="",
        temp_c=16.0,
        temp_f=60.8,
        feels_like_c=None,
        feels_like_f=None,
        humidity_pct=None,
        wind_dir="W",
        wind_mph=9.4,
        wind_kph=15.1,
        wind_gust_mph=None,
        wind_gust_kph=None,
        visibility_mi=10.0,
        visibility_km=16.1,
        metar_raw=None,
    )
    with pytest.raises(ValueError):
        format_metar(result)


def test_line_length_under_400(sjc_result, sjc_forecast):
    out = format_current(sjc_result, forecast=sjc_forecast, units=Units.METRIC)
    assert len(out) < 400
