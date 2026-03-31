import pytest

from weather.formatter import format_current, format_metar, format_pws
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


@pytest.mark.parametrize("units", [Units.METRIC, Units.IMPERIAL])
def test_format_metar_visibility_nonetype(ksfo_metar_result, units):
    ksfo_metar_result.visibility_mi = None
    ksfo_metar_result.visibility_km = None
    out = format_metar(ksfo_metar_result, units=units)
    assert "> 10 SM" in out


def test_format_metar_requires_metar_raw(ksfo_metar_result):
    ksfo_metar_result.metar_raw = None
    with pytest.raises(ValueError):
        format_metar(ksfo_metar_result)


def test_line_length_under_400(sjc_result, sjc_forecast):
    out = format_current(sjc_result, forecast=sjc_forecast, units=Units.METRIC)
    assert len(out) < 400


@pytest.fixture
def pws_result():
    return WeatherResult(
        location_name="My Home Station",
        condition=None,
        temp_c=22.5,
        temp_f=72.5,
        feels_like_c=21.0,
        feels_like_f=69.8,
        humidity_pct=55,
        wind_dir="SW",
        wind_mph=8.1,
        wind_kph=13.0,
        wind_gust_mph=12.5,
        wind_gust_kph=20.1,
        uv_index=5.0,
        rain_today_in=0.1,
        rain_today_mm=2.5,
    )


def test_format_pws_metric(pws_result):
    out = format_pws(pws_result, units=Units.METRIC)
    expected = (
        "PWS: My Home Station :: "
        "22.5C/72.5F (Feels like 21.0C/69.8F) (Humidity: 55%) | "
        "Wind: SW at 13.0kph/8.1mph (Gust: 20.1kph/12.5mph) | "
        "UV: 5 | "
        "Rain today: 2.5mm/0.10in"
    )
    assert out == expected


def test_format_pws_imperial(pws_result):
    out = format_pws(pws_result, units=Units.IMPERIAL)
    assert "72.5F/22.5C" in out
    assert "8.1mph/13.0kph" in out


def test_format_pws_no_feels_like(pws_result):
    pws_result.feels_like_c = None
    pws_result.feels_like_f = None
    out = format_pws(pws_result, units=Units.METRIC)
    assert "Feels like" not in out


def test_format_pws_no_humidity(pws_result):
    pws_result.humidity_pct = None
    out = format_pws(pws_result, units=Units.METRIC)
    assert "Humidity" not in out


def test_format_pws_no_gust(pws_result):
    pws_result.wind_gust_mph = None
    pws_result.wind_gust_kph = None
    out = format_pws(pws_result, units=Units.METRIC)
    assert "Gust" not in out


@pytest.mark.parametrize(
    "units, expected",
    [
        (Units.METRIC, "Rain today: 2.5mm/0.10in"),
        (Units.IMPERIAL, "Rain today: 0.10in/2.5mm"),
    ],
)
def test_format_pws_rain_order(pws_result, units, expected):
    out = format_pws(pws_result, units=units)
    assert expected in out


def test_format_pws_no_optional_fields():
    result = WeatherResult(
        location_name="My Home Station",
        condition=None,
        temp_c=22.5,
        temp_f=72.5,
        feels_like_c=None,
        feels_like_f=None,
        humidity_pct=None,
        wind_dir="SW",
        wind_mph=8.1,
        wind_kph=13.0,
    )
    out = format_pws(result, units=Units.METRIC)
    assert out == "PWS: My Home Station :: 22.5C/72.5F | Wind: SW at 13.0kph/8.1mph"


def test_format_pws_line_length_under_400(pws_result):
    out = format_pws(pws_result, units=Units.METRIC)
    assert len(out) < 400
