"""Demo Report Writer sample claim: metadata, photos, and guest gates."""

from app.demo_sample import PHOTOS_DIR, SAMPLE_ADDRESS, SAMPLE_DATE_ISO, SAMPLE_PHOTOS, sample_property_metadata, weather_fetch_key


def test_sample_weather_key_matches_spa_normalization():
    meta = sample_property_metadata()
    assert meta["report_type"] == "engineering"
    assert meta["address"] == "100 Harbor Example Road"
    assert meta["city"] == "Sampletown"
    assert meta["storm_date"] == "September 28, 2022"
    assert meta["storm_date_iso"] == SAMPLE_DATE_ISO
    assert meta["weather_fetch_key"] == weather_fetch_key(SAMPLE_ADDRESS, SAMPLE_DATE_ISO)
    assert meta["weather_fetch_key"] == "100 harbor example road, sampletown, fl 30010|2022-09-28"
    assert "missing or creased" in meta["weather_candidates_json"] or "demo-wind" in meta["weather_candidates_json"]


def test_sample_roof_photos_are_jpegs():
    assert len(SAMPLE_PHOTOS) >= 3
    for photo in SAMPLE_PHOTOS:
        data = (PHOTOS_DIR / photo.filename).read_bytes()
        assert data[:2] == b"\xff\xd8"
        assert "missing" in photo.observations.lower() or "creased" in photo.observations.lower() or "shingle" in photo.observations.lower()
