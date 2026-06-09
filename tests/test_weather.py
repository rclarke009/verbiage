"""Tests for Visual Crossing weather client and boilerplate integration."""

from __future__ import annotations

from datetime import date

import pytest

from app.report_writer.boilerplate import weather_text
from app.report_writer.weather import (
    WeatherSnapshot,
    _snapshot_from_response,
    parse_storm_date,
    weather_fetch_key,
    weather_metadata_from_snapshot,
)


def test_parse_storm_date_iso() -> None:
    assert parse_storm_date("2024-10-09") == date(2024, 10, 9)


def test_parse_storm_date_display() -> None:
    assert parse_storm_date("October 9, 2024") == date(2024, 10, 9)
    assert parse_storm_date("September 28, 2022") == date(2022, 9, 28)


def test_parse_storm_date_invalid() -> None:
    with pytest.raises(ValueError, match="Unrecognized"):
        parse_storm_date("not a date")


def test_snapshot_from_response() -> None:
    data = {
        "resolvedAddress": "Tampa, FL, United States",
        "latitude": 27.95,
        "longitude": -82.46,
        "days": [
            {
                "datetime": "2024-10-09",
                "windspeed": 60.2,
                "windgust": 86.4,
                "stations": ["KTPA", "KMCF"],
            }
        ],
    }
    snap = _snapshot_from_response(data, date(2024, 10, 9))
    assert snap.wind_speed_mph == 60.2
    assert snap.wind_gust_mph == 86.4
    assert snap.stations == ["KTPA", "KMCF"]
    assert snap.resolved_address == "Tampa, FL, United States"
    assert snap.date_iso == "2024-10-09"


def test_weather_metadata_from_snapshot() -> None:
    snap = WeatherSnapshot(
        wind_speed_mph=60.0,
        wind_gust_mph=86.0,
        stations=["KTPA"],
        resolved_address="Tampa, FL",
        latitude=27.95,
        longitude=-82.46,
        date_iso="2024-10-09",
        date_display="October 9, 2024",
    )
    meta = weather_metadata_from_snapshot(snap, "412 Gulfview Dr, Tampa, FL")
    assert meta["wind_speed_mph"] == "60"
    assert meta["wind_gust_mph"] == "86"
    assert meta["weather_stations"] == "KTPA"
    assert meta["weather_source"] == "visual_crossing"
    assert meta["weather_fetch_key"] == weather_fetch_key("412 Gulfview Dr, Tampa, FL", "2024-10-09")


def test_weather_text_with_wind_speeds() -> None:
    meta = {
        "storm_name": "Milton",
        "storm_type": "hurricane",
        "storm_date": "October 9, 2024",
        "storm_category": "Cat 3",
        "wind_speed_mph": "60",
        "wind_gust_mph": "86",
        "weather_stations": "KTPA",
    }
    text = weather_text(meta)
    assert "Hurricane Milton" in text
    assert "60 mph" in text
    assert "86 mph" in text
    assert "KTPA" in text
    assert "reasonable to assume" not in text


def test_weather_text_without_wind_speeds_fallback() -> None:
    meta = {
        "storm_name": "Ian",
        "storm_type": "hurricane",
        "storm_date": "September 28, 2022",
    }
    text = weather_text(meta)
    assert "reasonable to assume" in text
    assert "60 mph" not in text
