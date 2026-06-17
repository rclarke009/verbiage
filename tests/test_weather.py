"""Tests for multi-source weather aggregation and boilerplate integration."""

from __future__ import annotations

from datetime import date

import pytest

from app.report_writer.boilerplate import weather_text
from app.report_writer.weather.aggregator import apply_recommendations, weather_metadata_from_options
from app.report_writer.weather.providers import spc_reports
from app.report_writer.weather.types import WeatherCandidate, WeatherOptions
from app.report_writer.weather.utils import knots_to_mph, parse_storm_date, weather_fetch_key
from app.report_writer.weather import weather_metadata_from_snapshot


def test_parse_storm_date_iso() -> None:
    assert parse_storm_date("2024-10-09") == date(2024, 10, 9)


def test_parse_storm_date_display() -> None:
    assert parse_storm_date("October 9, 2024") == date(2024, 10, 9)
    assert parse_storm_date("September 28, 2022") == date(2022, 9, 28)


def test_parse_storm_date_invalid() -> None:
    with pytest.raises(ValueError, match="Unrecognized"):
        parse_storm_date("not a date")


def test_spc_parse_hail_size() -> None:
    assert spc_reports._parse_hail_size("1.75") == 1.75
    assert spc_reports._parse_hail_size("1.75 inch") == 1.75


def test_apply_recommendations_prefers_tier1_over_tier3() -> None:
    candidates = [
        WeatherCandidate(
            id="vc:wind",
            metric="wind_gust",
            value=90.0,
            unit="mph",
            source="visual_crossing",
            label="VC",
            tier=3,
        ),
        WeatherCandidate(
            id="iem:KTPA:gust",
            metric="wind_gust",
            value=86.0,
            unit="mph",
            source="iem_asos",
            label="KTPA",
            tier=1,
            station="KTPA",
            distance_mi=8.0,
        ),
    ]
    selected = apply_recommendations(candidates, max_distance_mi=50)
    assert selected["wind_gust"] == "iem:KTPA:gust"
    recommended = next(c for c in candidates if c.recommended)
    assert recommended.id == "iem:KTPA:gust"


def test_apply_recommendations_highest_value_within_tier() -> None:
    candidates = [
        WeatherCandidate(
            id="iem:a",
            metric="wind_gust",
            value=80.0,
            unit="mph",
            source="iem_asos",
            label="A",
            tier=1,
            distance_mi=5.0,
        ),
        WeatherCandidate(
            id="iem:b",
            metric="wind_gust",
            value=92.0,
            unit="mph",
            source="iem_asos",
            label="B",
            tier=1,
            distance_mi=15.0,
        ),
    ]
    selected = apply_recommendations(candidates, max_distance_mi=50)
    assert selected["wind_gust"] == "iem:b"


def test_knots_to_mph() -> None:
    assert round(knots_to_mph(50), 1) == 57.5


def test_weather_metadata_from_options() -> None:
    options = WeatherOptions(
        wind_speed_mph=60.0,
        wind_gust_mph=86.0,
        hail_size_in=1.25,
        precip_in=None,
        stations=["KTPA"],
        resolved_address="Tampa, FL",
        latitude=27.95,
        longitude=-82.46,
        date_iso="2024-10-09",
        date_display="October 9, 2024",
        fetch_key=weather_fetch_key("Tampa, FL", "2024-10-09"),
        candidates=[],
        selected={"wind_speed": "vc:daily:wind_speed", "wind_gust": "vc:daily:wind_gust"},
        attribution=[],
    )
    meta = weather_metadata_from_options(options, "412 Gulfview Dr, Tampa, FL")
    assert meta["wind_speed_mph"] == "60"
    assert meta["wind_gust_mph"] == "86"
    assert meta["hail_size_in"] == "1.25"
    assert meta["weather_stations"] == "KTPA"
    assert meta["weather_source"] == "multi"


def test_weather_metadata_from_snapshot_legacy() -> None:
    options = WeatherOptions(
        wind_speed_mph=60.0,
        wind_gust_mph=86.0,
        hail_size_in=None,
        precip_in=None,
        stations=["KTPA"],
        resolved_address="Tampa, FL",
        latitude=27.95,
        longitude=-82.46,
        date_iso="2024-10-09",
        date_display="October 9, 2024",
        fetch_key=weather_fetch_key("412 Gulfview Dr, Tampa, FL", "2024-10-09"),
        candidates=[],
        selected={},
        attribution=[],
    )
    meta = weather_metadata_from_snapshot(options, "412 Gulfview Dr, Tampa, FL")
    assert meta["wind_speed_mph"] == "60"
    assert meta["wind_gust_mph"] == "86"


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


def test_weather_text_with_hail() -> None:
    meta = {
        "storm_name": "Ian",
        "storm_type": "hurricane",
        "storm_date": "September 28, 2022",
        "hail_size_in": "1.5",
    }
    text = weather_text(meta)
    assert "1.5 inches" in text
    assert "hail" in text.lower()


def test_weather_text_without_wind_speeds_fallback() -> None:
    meta = {
        "storm_name": "Ian",
        "storm_type": "hurricane",
        "storm_date": "September 28, 2022",
    }
    text = weather_text(meta)
    assert "reasonable to assume" in text
    assert "60 mph" not in text
