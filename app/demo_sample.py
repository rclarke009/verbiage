"""Shared guest Report Writer claim on the synthetic corpus."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from psycopg2.extras import Json, RealDictCursor

from app.demo import DEMO_GUEST_USER_ID
from app.report_writer.storage import storage_path_for, write_claim_image

logger = logging.getLogger(__name__)

DEMO_SAMPLE_CLAIM_ID = "c0ffee00-0000-4000-8000-000000000001"
SAMPLE_ADDRESS = "100 Harbor Example Road, Sampletown, FL 30010"
SAMPLE_DATE_ISO = "2022-09-28"
PHOTOS_DIR = Path(__file__).resolve().parent / "demo_corpus" / "photos"

SAMPLE_TITLE = "100 Harbor Example Road — sample engineering report"
SAMPLE_FIELD_NOTES = """Site visit at 100 Harbor Example Road, Sampletown, FL 30010 after Hurricane Ian (September 28, 2022).

Roof: several asphalt shingles were missing or creased on the windward slope. The damage created an opening through which wind-driven rain entered the roof assembly during the storm.

Interior: in the garage, water staining and softened drywall were noted on the ceiling and the upper portion of the north wall. The staining is consistent with water entering through the storm-created opening above.
"""


@dataclass(frozen=True)
class SamplePhoto:
    image_id: str
    filename: str
    caption: str
    observations: str


SAMPLE_PHOTOS: tuple[SamplePhoto, ...] = (
    SamplePhoto(
        "c0ffee00-0000-4000-8000-000000000011",
        "windward_slope.jpg",
        "Windward roof slope",
        "Several asphalt shingles are missing on the windward slope, leaving an opening in the roof covering.",
    ),
    SamplePhoto(
        "c0ffee00-0000-4000-8000-000000000012",
        "creased_shingles.jpg",
        "Creased shingles",
        "Shingles on the slope are creased and lifted, consistent with wind damage.",
    ),
    SamplePhoto(
        "c0ffee00-0000-4000-8000-000000000013",
        "shingle_field.jpg",
        "Asphalt shingle field",
        "Close view of the asphalt shingle field on the roof slope.",
    ),
    SamplePhoto(
        "c0ffee00-0000-4000-8000-000000000014",
        "lifted_tabs.jpg",
        "Lifted shingle tabs",
        "Shingle tabs are lifted along the slope, with a gap in the roof covering.",
    ),
)


def weather_fetch_key(address: str, date_iso: str) -> str:
    """Match the SPA key: lowercased address, collapsed whitespace, then the ISO date."""
    normalized = " ".join(address.strip().lower().split())
    return f"{normalized}|{date_iso}"


def sample_property_metadata() -> dict[str, str]:
    fetch_key = weather_fetch_key(SAMPLE_ADDRESS, SAMPLE_DATE_ISO)
    candidates = [
        {
            "id": "demo-wind",
            "metric": "wind_speed",
            "value": 95,
            "unit": "mph",
            "source": "sample",
            "label": "Sample sustained wind",
            "tier": 2,
            "recommended": True,
        },
        {
            "id": "demo-gust",
            "metric": "wind_gust",
            "value": 120,
            "unit": "mph",
            "source": "sample",
            "label": "Sample wind gust",
            "tier": 2,
            "recommended": True,
        },
        {
            "id": "demo-hail",
            "metric": "hail_size",
            "value": 1.0,
            "unit": "in",
            "source": "sample",
            "label": "Sample hail size",
            "tier": 2,
            "recommended": True,
        },
    ]
    return {
        "report_type": "engineering",
        "address": "100 Harbor Example Road",
        "address2": "",
        "city": "Sampletown",
        "state": "FL",
        "zip": "30010",
        "property_type": "Single-family residence",
        "storm_id": "ian-2022",
        "storm_name": "Ian",
        "storm_date": "September 28, 2022",
        "storm_date_iso": SAMPLE_DATE_ISO,
        "storm_type": "hurricane",
        "storm_category": "Cat 4",
        "landfall_region": "Cayo Costa, FL",
        "wind_speed_mph": "95",
        "wind_gust_mph": "120",
        "hail_size_in": "1",
        "weather_stations": "Sample station",
        "weather_resolved_address": SAMPLE_ADDRESS,
        "weather_date_iso": SAMPLE_DATE_ISO,
        "weather_source": "sample",
        "weather_fetched_at": "2022-09-29T12:00:00+00:00",
        "weather_fetch_key": fetch_key,
        "weather_wind_speed_source": "demo-wind",
        "weather_wind_gust_source": "demo-gust",
        "weather_hail_source": "demo-hail",
        "weather_candidates_json": json.dumps(candidates),
    }


def _photo_bytes(filename: str) -> bytes:
    path = PHOTOS_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Demo sample photo missing: {path}")
    return path.read_bytes()


def ensure_demo_sample_claim(conn) -> bool:
    """Insert the guest sample claim when missing, and refresh photo files on disk.

    Returns True when the claim row was created. Existing notes are left in place
    so a presenter edit survives the next boot. Photo bytes are rewritten every
    boot because the image directory is ephemeral on Render.
    """
    created = False
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            "SELECT claim_id FROM report_claims WHERE claim_id = %s::uuid",
            (DEMO_SAMPLE_CLAIM_ID,),
        )
        if cur.fetchone() is None:
            cur.execute(
                """
                INSERT INTO report_claims
                    (claim_id, user_id, title, property_metadata, field_notes, status)
                VALUES (%s::uuid, %s, %s, %s, %s, 'draft')
                """,
                (
                    DEMO_SAMPLE_CLAIM_ID,
                    DEMO_GUEST_USER_ID,
                    SAMPLE_TITLE,
                    Json(sample_property_metadata()),
                    SAMPLE_FIELD_NOTES,
                ),
            )
            created = True
            logger.info("Demo sample claim created (%s)", DEMO_SAMPLE_CLAIM_ID)

        for index, photo in enumerate(SAMPLE_PHOTOS):
            data = _photo_bytes(photo.filename)
            default_path = storage_path_for(
                DEMO_GUEST_USER_ID,
                DEMO_SAMPLE_CLAIM_ID,
                photo.image_id,
                photo.filename,
            )
            cur.execute(
                """
                SELECT storage_path FROM report_claim_images
                WHERE image_id = %s::uuid
                """,
                (photo.image_id,),
            )
            row = cur.fetchone()
            path = default_path
            vision = {
                "caption": photo.caption,
                "observations": photo.observations,
                "has_damage": True,
            }
            if row is None:
                cur.execute(
                    """
                    INSERT INTO report_claim_images
                        (image_id, claim_id, user_id, storage_path, filename,
                         content_type, size_bytes, sort_order, analysis_status,
                         vision_analysis)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, 'succeeded', %s)
                    """,
                    (
                        photo.image_id,
                        DEMO_SAMPLE_CLAIM_ID,
                        DEMO_GUEST_USER_ID,
                        default_path,
                        photo.filename,
                        "image/jpeg",
                        len(data),
                        index,
                        Json(vision),
                    ),
                )
            else:
                stored = row.get("storage_path")
                if stored:
                    path = stored
            write_claim_image(path, data)
        conn.commit()
        return created
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
