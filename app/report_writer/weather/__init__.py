"""Multi-source weather aggregation for Report Writer."""

from app.report_writer.weather.aggregator import (
    apply_recommendations,
    fetch_weather_options,
    weather_metadata_from_options,
)
from app.report_writer.weather.types import WeatherCandidate, WeatherOptions
from app.report_writer.weather.utils import (
    normalize_address_for_key,
    parse_storm_date,
    weather_fetch_key,
)

# Backward-compatible alias used in tests
WeatherSnapshot = WeatherOptions


async def fetch_weather_for_location(address: str, storm_date):
    """Legacy entry point — returns full weather options."""
    from datetime import date

    if not isinstance(storm_date, date):
        raise TypeError("storm_date must be a date")
    return await fetch_weather_options(address, storm_date)


def weather_metadata_from_snapshot(snapshot, address: str) -> dict[str, str]:
    """Legacy helper — accepts WeatherOptions."""
    return weather_metadata_from_options(snapshot, address)


__all__ = [
    "WeatherCandidate",
    "WeatherOptions",
    "WeatherSnapshot",
    "apply_recommendations",
    "fetch_weather_for_location",
    "fetch_weather_options",
    "normalize_address_for_key",
    "parse_storm_date",
    "weather_fetch_key",
    "weather_metadata_from_options",
    "weather_metadata_from_snapshot",
]
