"""Shared types for multi-source weather aggregation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

WeatherMetric = Literal["wind_speed", "wind_gust", "hail_size", "precip"]


@dataclass
class WeatherCandidate:
    id: str
    metric: WeatherMetric
    value: float
    unit: str
    source: str
    label: str
    tier: int
    station: str | None = None
    distance_mi: float | None = None
    recommended: bool = False
    recommendation_reason: str | None = None


@dataclass
class GeoContext:
    address: str
    storm_date: date
    latitude: float | None
    longitude: float | None
    resolved_address: str = ""
    stations: list[str] = field(default_factory=list)


@dataclass
class WeatherOptions:
    wind_speed_mph: float | None
    wind_gust_mph: float | None
    hail_size_in: float | None
    precip_in: float | None
    stations: list[str]
    resolved_address: str
    latitude: float | None
    longitude: float | None
    date_iso: str
    date_display: str
    fetch_key: str
    candidates: list[WeatherCandidate]
    selected: dict[str, str]
    attribution: list[str]
    source: str = "multi"
