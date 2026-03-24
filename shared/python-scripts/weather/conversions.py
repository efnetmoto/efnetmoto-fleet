"""Pure unit and format conversion functions.

No imports from within the weather/ package — stdlib only.
No state, no side effects. This module is the single source of truth
for all unit arithmetic in the package.
"""

_WIND_DIRS = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
]


def degrees_to_cardinal(degrees: float) -> str:
    """Convert wind direction in degrees to a cardinal string e.g. 'NNW'."""
    try:
        idx = round(float(degrees) / 22.5) % 16
        return _WIND_DIRS[idx]
    except (TypeError, ValueError):
        return str(degrees)


def f_to_c(f: float) -> float:
    """Convert Fahrenheit to Celsius, rounded to one decimal place."""
    return round((f - 32) * 5 / 9, 1)


def c_to_f(c: float) -> float:
    """Convert Celsius to Fahrenheit, rounded to one decimal place."""
    return round(c * 9 / 5 + 32, 1)


def mph_to_kph(mph: float) -> float:
    """Convert miles per hour to kilometres per hour, rounded to one decimal."""
    return round(mph * 1.60934, 1)


def kph_to_mph(kph: float) -> float:
    """Convert kilometres per hour to miles per hour, rounded to one decimal."""
    return round(kph / 1.60934, 1)


def inches_to_mm(inches: float) -> float:
    """Convert inches to millimetres, rounded to one decimal place."""
    return round(inches * 25.4, 1)
