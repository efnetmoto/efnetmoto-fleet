import pytest

from weather.conversions import (
    c_to_f,
    degrees_to_cardinal,
    f_to_c,
    humidity_from_dewpoint,
    inches_to_mm,
    kph_to_mph,
    mm_to_inches,
    mph_to_kph,
    mps_to_kph,
    mps_to_mph,
)


@pytest.mark.parametrize(
    "degrees, expected",
    [
        (0, "N"),
        (90, "E"),
        (180, "S"),
        (270, "W"),
        (329, "NNW"),
        (360, "N"),
    ],
)
def test_degrees_to_cardinal(degrees, expected):
    assert degrees_to_cardinal(degrees) == expected


def test_degrees_to_cardinal_string_input():
    assert degrees_to_cardinal("N") == "N"


@pytest.mark.parametrize(
    "fahrenheit, expected",
    [
        (-12.3, -24.6),
        (32.0, 0.0),
        (82.0, 27.8),
    ],
)
def test_f_to_c(fahrenheit, expected):
    assert f_to_c(fahrenheit) == expected


@pytest.mark.parametrize(
    "celcius, expected",
    [
        (-12.3, 9.9),
        (0, 32.0),
        (27.8, 82.0),
    ],
)
def test_c_to_f(celcius, expected):
    assert c_to_f(celcius) == expected


def test_mph_to_kph():
    assert mph_to_kph(3.6) == 5.8


def test_kph_to_mph():
    assert kph_to_mph(5.8) == 3.6


def test_inches_to_mm():
    assert inches_to_mm(0.031) == 0.8


def test_mm_to_inches():
    assert mm_to_inches(3.6) == 0.14


def test_mps_to_mph():
    assert mps_to_mph(1.23) == 2.8


def test_mps_to_kph():
    assert mps_to_kph(1.23) == 4.4


def test_humidity_from_dewpoint():
    assert humidity_from_dewpoint(22, 11.94) == 53
