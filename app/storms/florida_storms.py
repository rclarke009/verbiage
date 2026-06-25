"""Florida storm catalog (mirrors frontend/src/data/floridaStorms.ts)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FloridaStorm:
    id: str
    name: str
    year: int
    landfall_date: str
    landfall_display: str
    storm_type: Literal["hurricane", "tropical_storm"]
    category: str
    landfall_region: str


FLORIDA_STORMS: tuple[FloridaStorm, ...] = (
    FloridaStorm(
        id="milton-2024",
        name="Milton",
        year=2024,
        landfall_date="2024-10-09",
        landfall_display="October 9, 2024",
        storm_type="hurricane",
        category="Cat 3",
        landfall_region="Siesta Key, FL",
    ),
    FloridaStorm(
        id="helene-2024",
        name="Helene",
        year=2024,
        landfall_date="2024-09-26",
        landfall_display="September 26, 2024",
        storm_type="hurricane",
        category="Cat 4",
        landfall_region="Near Perry, FL",
    ),
    FloridaStorm(
        id="debby-2024",
        name="Debby",
        year=2024,
        landfall_date="2024-08-05",
        landfall_display="August 5, 2024",
        storm_type="hurricane",
        category="Cat 1",
        landfall_region="Steinhatchee, FL",
    ),
    FloridaStorm(
        id="idalia-2023",
        name="Idalia",
        year=2023,
        landfall_date="2023-08-30",
        landfall_display="August 30, 2023",
        storm_type="hurricane",
        category="Cat 3",
        landfall_region="Keaton Beach, FL",
    ),
    FloridaStorm(
        id="ian-2022",
        name="Ian",
        year=2022,
        landfall_date="2022-09-28",
        landfall_display="September 28, 2022",
        storm_type="hurricane",
        category="Cat 4",
        landfall_region="Cayo Costa, FL",
    ),
    FloridaStorm(
        id="nicole-2022",
        name="Nicole",
        year=2022,
        landfall_date="2022-11-10",
        landfall_display="November 10, 2022",
        storm_type="hurricane",
        category="Cat 1",
        landfall_region="Vero Beach, FL",
    ),
    FloridaStorm(
        id="elsa-2021",
        name="Elsa",
        year=2021,
        landfall_date="2021-07-07",
        landfall_display="July 7, 2021",
        storm_type="tropical_storm",
        category="Tropical Storm",
        landfall_region="Taylor County, FL",
    ),
    FloridaStorm(
        id="fred-2021",
        name="Fred",
        year=2021,
        landfall_date="2021-08-16",
        landfall_display="August 16, 2021",
        storm_type="tropical_storm",
        category="Tropical Storm",
        landfall_region="Cape San Blas, FL",
    ),
    FloridaStorm(
        id="mindy-2021",
        name="Mindy",
        year=2021,
        landfall_date="2021-09-08",
        landfall_display="September 8, 2021",
        storm_type="tropical_storm",
        category="Tropical Storm",
        landfall_region="St. Vincent Island, FL",
    ),
)


def get_storm_by_id(storm_id: str) -> FloridaStorm | None:
    needle = (storm_id or "").strip().lower()
    if not needle:
        return None
    for storm in FLORIDA_STORMS:
        if storm.id.lower() == needle:
            return storm
    return None
