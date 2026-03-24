from weather.conversions import (
    c_to_f,
    degrees_to_cardinal,
    f_to_c,
    inches_to_mm,
    kph_to_mph,
    mph_to_kph,
)


def test_degrees_to_cardinal_north():
    assert degrees_to_cardinal(0) == "N"


def test_degrees_to_cardinal_east():
    assert degrees_to_cardinal(90) == "E"


def test_degrees_to_cardinal_south():
    assert degrees_to_cardinal(180) == "S"


def test_degrees_to_cardinal_west():
    assert degrees_to_cardinal(270) == "W"


def test_degrees_to_cardinal_nnw():
    assert degrees_to_cardinal(329) == "NNW"


def test_degrees_to_cardinal_wraps():
    assert degrees_to_cardinal(360) == "N"


def test_f_to_c_freezing():
    assert f_to_c(32.0) == 0.0


def test_f_to_c_warm():
    assert f_to_c(82.0) == 27.8


def test_c_to_f_freezing():
    assert c_to_f(0.0) == 32.0


def test_mph_to_kph():
    assert mph_to_kph(3.6) == 5.8


def test_kph_to_mph():
    assert kph_to_mph(5.8) == 3.6


def test_inches_to_mm():
    assert inches_to_mm(0.031) == 0.8
