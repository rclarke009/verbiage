"""Tests for document metadata extraction."""

from app.document_metadata import detect_storm, extract_address, extract_document_metadata


def test_extract_address_from_header():
    text = "Engineering Report - 100 Harbor Example Road, Sampletown, FL 30010\n\nProperty Overview"
    assert extract_address(text) == "100 Harbor Example Road, Sampletown, FL 30010"


def test_detect_storm_hurricane_ian():
    text = "Damage following Hurricane Ian in September 2022."
    storm_id, name, date_iso = detect_storm(text)
    assert storm_id == "ian-2022"
    assert name == "Ian"
    assert date_iso == "2022-09-28"


def test_detect_storm_generic_windstorm_returns_none():
    text = "Damage following the reported windstorm event."
    assert detect_storm(text) == (None, None, None)


def test_extract_document_metadata_address_only():
    text = "Engineering Report - 412 Example Drive, Sample City, FL 30040\n\nConclusion"
    meta = extract_document_metadata(text)
    assert meta["address"] == "412 Example Drive, Sample City, FL 30040"
    assert meta["storm_id"] is None
