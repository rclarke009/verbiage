"""Tests for document metadata extraction."""

from app.document_metadata import detect_storm, extract_address, extract_document_metadata


def test_extract_address_from_header():
    text = "Engineering Report - 100 Harbor Example Road, Sampletown, FL 30010\n\nProperty Overview"
    assert extract_address(text) == "100 Harbor Example Road, Sampletown, FL 30010"


def test_extract_address_from_address_label_single_line():
    """Residential Testing-style header with Address: on one line (CR route)."""
    text = (
        "Residential Testing \n"
        "Prepared for: Jordan & Morgan Sample \n"
        "Address: 1200 NE Example CR 100, Sampleville, FL 30070 \n"
        "  \n"
        "\n"
        "27 Jun 2024 E24-6-0018 \n"
        "1200 NE Example CR 100, Sampleville, FL 30070 PAGE 2 OF 51 \n"
    )
    assert extract_address(text) == "1200 NE Example CR 100, Sampleville, FL 30070"


def test_extract_address_from_address_label_multiline_circle():
    """Multiline header: street on Address: line, city/state/ZIP on next."""
    text = (
        "Prepared for:  Alex Sampleton \n"
        "Address:   400 Example Cir SW \n"
        "   Sample Oaks, FL 30071\n"
        "ENGINEERING \n"
        "REPORT\n"
    )
    assert extract_address(text) == "400 Example Cir SW, Sample Oaks, FL 30071"


def test_extract_address_from_address_label_multiline_terrace():
    text = (
        "Prepared for: Casey Example \n"
        "Address: 15000 Example Terrace \n"
        " Sample Oaks, FL 30072 \n"
        "7 Aug 2025 E2025-07102 \n"
    )
    assert extract_address(text) == "15000 Example Terrace, Sample Oaks, FL 30072"


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


def test_extract_document_metadata_residential_testing_style():
    text = (
        "Residential Testing\n"
        "Prepared for: Jordan & Morgan Sample\n"
        "Address: 1200 NE Example CR 100, Sampleville, FL 30070\n"
        "Damage following Hurricane Idalia in 2023.\n"
    )
    meta = extract_document_metadata(text)
    assert meta["address"] == "1200 NE Example CR 100, Sampleville, FL 30070"
    assert meta["storm_id"] == "idalia-2023"
