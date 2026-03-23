from weather.models import ForecastResult, Units, WeatherResult


def _dual(
    metric_val: float, metric_unit: str, imperial_val: float, imperial_unit: str, units: Units
) -> str:
    if units == Units.METRIC:
        return f"{metric_val:.1f}{metric_unit}/{imperial_val:.1f}{imperial_unit}"
    return f"{imperial_val:.1f}{imperial_unit}/{metric_val:.1f}{metric_unit}"


def format_current(
    result: WeatherResult,
    forecast: ForecastResult | None = None,
    units: Units = Units.METRIC,
) -> str:
    """Format a current conditions WeatherResult into an IRC message string.

    Args:
        result: Current conditions to format.
        forecast: If provided, today's high/low and condition are appended.
        units: Controls which value is shown first (metric or imperial).

    Returns:
        Formatted IRC message string.
    """
    segment3 = _dual(result.temp_c, "C", result.temp_f, "F", units)
    if result.humidity_pct is not None:
        segment3 += f" (Humidity: {result.humidity_pct}%)"

    pipe_fields = []

    if result.feels_like_c is not None and result.feels_like_f is not None:
        feels = _dual(result.feels_like_c, "C", result.feels_like_f, "F", units)
        pipe_fields.append(f"Feels like: {feels}")

    wind = _dual(result.wind_kph, "kph", result.wind_mph, "mph", units)
    pipe_fields.append(f"Wind: {result.wind_dir} at {wind}")

    if forecast is not None:
        high = _dual(forecast.high_c, "C", forecast.high_f, "F", units)
        low = _dual(forecast.low_c, "C", forecast.low_f, "F", units)
        pipe_fields.append(f"Today: {forecast.condition}. High {high} - Low {low}")

    segment3_full = segment3 + " | " + " | ".join(pipe_fields)
    return " :: ".join([result.location_name, result.condition, segment3_full])


def format_metar(
    result: WeatherResult,
    units: Units = Units.METRIC,
) -> str:
    """Format a METAR WeatherResult into an IRC message string.

    Args:
        result: METAR result to format. result.metar_raw must be set.
        units: Controls which value is shown first (metric or imperial).

    Returns:
        Formatted IRC message string.

    Raises:
        ValueError: If result.metar_raw is None.
    """
    if result.metar_raw is None:
        raise ValueError("metar_raw is required for format_metar")

    if result.visibility_mi is None:
        vis = "> 6 mi"
    else:
        vis = f"{result.visibility_mi:.1f}SM"

    wind = _dual(result.wind_kph, "kph", result.wind_mph, "mph", units)
    pipe_fields = [
        _dual(result.temp_c, "C", result.temp_f, "F", units),
        f"Wind: {result.wind_dir} at {wind}",
        f"Visibility: {vis}",
    ]

    return " :: ".join(
        [
            result.location_name,
            "METAR",
            result.metar_raw,
            " | ".join(pipe_fields),
        ]
    )
