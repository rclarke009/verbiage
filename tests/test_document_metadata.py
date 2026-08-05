"""Tests for document metadata extraction."""

from app.document_metadata import detect_storm, extract_address, extract_document_metadata


def test_extract_address_from_header():
    text = "Engineering Report - 100 Harbor Example Road, Sampletown, FL 30010\n\nProperty Overview"
    assert extract_address(text) == "100 Harbor Example Road, Sampletown, FL 30010"


def test_extract_address_from_address_label_single_line():
    """Hitchcock-style Residential Testing header with Address: on one line."""
    text = (
        "Residential Testing \n"
        "Prepared for: Jerald & Marilyn Hitchcock \n"
        "Address: 3440 NE CR 255, Lee, FL 32059 \n"
        "  \n"
        "\n"
        "27 Jun 2024 E24-6-0018 \n"
        "3440 NE CR 255, Lee, FL 32059 PAGE 2 OF 51 \n"
    )
    assert extract_address(text) == "3440 NE CR 255, Lee, FL 32059"


def test_extract_address_from_address_label_multiline_live_oak():
    """Live Oak-style header: street on Address: line, city/state/ZIP on next."""
    text = (
        "Prepared for:  James Ogles \n"
        "Address:   971 Pineview Cir SW \n"
        "   Live Oak, FL 32064\n"
        "ENGINEERING \n"
        "REPORT\n"
    )
    assert extract_address(text) == "971 Pineview Cir SW, Live Oak, FL 32064"


def test_extract_address_from_address_label_multiline_terrace():
    text = (
        "Prepared for: Corynne Rina Kramer \n"
        "Address: 15771 60th Terrace \n"
        " Live Oak, FL 32060 \n"
        "7 Aug 2025 E2025-07102 \n"
    )
    assert extract_address(text) == "15771 60th Terrace, Live Oak, FL 32060"


def test_extract_address_fl_street_zip_fallback():
    """When Address: label is missing, first FL street+ZIP line in the header wins."""
    text = (
        "PROPERTY LOCATION\n"
        "412 Example Drive, Sample City, FL 30040\n"
        "Inspected after the storm.\n"
    )
    assert extract_address(text) == "412 Example Drive, Sample City, FL 30040"


def test_extract_address_prefers_engineering_report_header():
    text = (
        "Engineering Report - 100 Harbor Example Road, Sampletown, FL 30010\n"
        "Address: 999 Other St, Elsewhere, FL 32001\n"
    )
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


def test_extract_document_metadata_hitchcock_style():
    text = (
        "Residential Testing\n"
        "Prepared for: Jerald & Marilyn Hitchcock\n"
        "Address: 3440 NE CR 255, Lee, FL 32059\n"
        "Damage following Hurricane Idalia in 2023.\n"
    )
    meta = extract_document_metadata(text)
    assert meta["address"] == "3440 NE CR 255, Lee, FL 32059"
    assert meta["storm_id"] == "idalia-2023"
