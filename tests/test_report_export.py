"""Tests for formatted report export (DOCX + PDF)."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile

import pytest

from app.report_writer.boilerplate import purpose_text, weather_text
from app.report_writer.docx_ooxml import xml_escape
from app.report_writer.export import draft_to_docx_bytes, draft_to_pdf_bytes
from app.report_writer.report_document import build_report_document


@pytest.fixture
def sample_claim() -> dict:
    return {
        "claim_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "title": "Huseman",
        "property_metadata": {
            "report_type": "engineering",
            "address": "3795 Riviera Cir, Bonita Springs, FL 34134",
            "property_type": "single-family",
            "client_name": "Huseman",
            "inspection_date": "Sep 15, 2023",
            "prepared_by": "Stuart Jay Clarke, CGC and CCC",
            "storm_name": "Ian",
            "storm_date": "September 28, 2022",
            "storm_type": "hurricane",
            "storm_category": "Cat 4",
            "landfall_region": "Near Fort Myers, FL",
            "include_engineering_letter": "true",
        },
        "field_notes": "Roof and interior damage observed.",
    }


@pytest.fixture
def sample_sections() -> dict[str, dict]:
    return {
        "property_overview": {
            "content": "The subject property is a single-family residence with storm-related damage.",
        },
        "roof_observations": {
            "content": "Several shingles were missing on the windward slope.",
        },
        "interior_observations": {
            "content": "Water staining was noted on the garage ceiling.",
        },
        "recommendations_conclusion": {
            "content": (
                "It is my professional opinion that the property sustained damage during Hurricane Ian. "
                "All repairs must comply with the Florida Building Code: Existing Building 2023."
            ),
        },
    }


def test_storm_placeholders_in_boilerplate(sample_claim: dict) -> None:
    meta = sample_claim["property_metadata"]
    purpose = purpose_text(meta)
    weather = weather_text(meta)
    assert "September 28, 2022" in purpose
    assert "Hurricane Ian" in weather
    assert "Cat 4" in weather


def test_build_report_document(sample_claim: dict, sample_sections: dict[str, dict]) -> None:
    doc = build_report_document(sample_claim, sample_sections, images=[])
    assert doc.client_name == "Huseman"
    assert doc.report_number == "A1B2C3D4"
    assert len(doc.sections) == 4
    assert doc.sections[-1].key == "recommendations_conclusion"
    assert doc.include_engineering_letter is True
    assert any("Hurricane Ian" in p for p in doc.engineering_letter_paragraphs)


def test_docx_export_structure(sample_claim: dict, sample_sections: dict[str, dict]) -> None:
    data = draft_to_docx_bytes(sample_sections, claim=sample_claim, images=[])
    assert data[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        assert "word/document.xml" in names
        doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "OVERVIEW" in doc_xml
        assert "ENGINEERING LETTER" in doc_xml
        assert "PROPERTY OVERVIEW" in doc_xml
        assert "ROOF OBSERVATIONS" in doc_xml
        assert "WEATHER HISTORY" in doc_xml
        assert "sectPr" in doc_xml
        ET.fromstring(doc_xml)


def test_pdf_export_structure(sample_claim: dict, sample_sections: dict[str, dict]) -> None:
    data = draft_to_pdf_bytes(sample_sections, claim=sample_claim, images=[])
    assert data.startswith(b"%PDF")
    assert len(data) > 1000


def test_docx_without_engineering_letter(sample_claim: dict, sample_sections: dict[str, dict]) -> None:
    claim = {
        **sample_claim,
        "property_metadata": {
            **sample_claim["property_metadata"],
            "include_engineering_letter": "false",
        },
    }
    data = draft_to_docx_bytes(sample_sections, claim=claim, images=[])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
    assert "ENGINEERING LETTER" not in doc_xml
    assert "PURPOSE:" in doc_xml
    assert "sectPr" in doc_xml


def test_xml_escape_strips_control_characters() -> None:
    assert xml_escape("hello\x0bworld") == "helloworld"
    assert xml_escape("a & b < c") == "a &amp; b &lt; c"


def test_docx_export_with_control_characters_in_content(
    sample_claim: dict,
    sample_sections: dict[str, dict],
) -> None:
    sections = {
        **sample_sections,
        "property_overview": {"content": "Text with\x0billegal\x1fchars & symbols."},
    }
    data = draft_to_docx_bytes(sections, claim=sample_claim, images=[])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
    ET.fromstring(doc_xml)
    assert "illegalchars" in doc_xml.replace(" ", "")
