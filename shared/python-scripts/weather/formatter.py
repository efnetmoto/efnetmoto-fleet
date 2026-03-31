from weather.models import ForecastResult, Units, WeatherResult


def _dual(
    metric_val: float, metric_unit: str, imperial_val: float, imperial_unit: str, units: Units
) -> str:
    if units == Units.METRIC:
        return f"{metric_val:.1f}{metric_unit}/{imperial_val:.1f}{imperial_unit}"
    return f"{imperial_val:.1f}{imperial_unit}/{metric_val:.1f}{metric_unit}"


def format_pws(result: WeatherResult, units: Units = Units.METRIC) -> str:
    """Format a PWS (personal weather station) WeatherResult into an IRC message string."""
    temp = _dual(result.temp_c, "C", result.temp_f, "F", units)
    detail = temp
    if result.feels_like_c is not None and result.feels_like_f is not None:
        feels = _dual(result.feels_like_c, "C", result.feels_like_f, "F", units)
        detail += f" (Feels like {feels})"
    if result.humidity_pct is not None:
        detail += f" (Humidity: {result.humidity_pct}%)"

    wind = _dual(result.wind_kph, "kph", result.wind_mph, "mph", units)
    wind_str = f"Wind: {result.wind_dir} at {wind}"
    if result.wind_gust_mph is not None and result.wind_gust_kph is not None:
        gust = _dual(result.wind_gust_kph, "kph", result.wind_gust_mph, "mph", units)
        wind_str += f" (Gust: {gust})"

    pipe_fields = [detail, wind_str]

    if result.uv_index is not None:
        pipe_fields.append(f"UV: {result.uv_index:.0f}")

    if result.rain_today_in is not None and result.rain_today_mm is not None:
        if units == Units.METRIC:
            pipe_fields.append(
                f"Rain today: {result.rain_today_mm:.1f}mm/{result.rain_today_in:.2f}in"
            )
        else:
            pipe_fields.append(
                f"Rain today: {result.rain_today_in:.2f}in/{result.rain_today_mm:.1f}mm"
            )

    return f"PWS: {result.location_name} :: " + " | ".join(pipe_fields)


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

    if result.condition is not None:
        return " :: ".join([result.location_name, result.condition, segment3_full])
    return " :: ".join([result.location_name, segment3_full])


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
        vis = "> 10 SM"
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
            result.metar_raw,
            " | ".join(pipe_fields),
        ]
    )
