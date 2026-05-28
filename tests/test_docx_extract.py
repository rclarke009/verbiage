"""DOCX text extraction."""

import io
import zipfile

import pytest

from app.docx_extract import extract_text_from_docx

DOCX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

DOCX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOCX_DOCUMENT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Hello from DOCX ingest test.</w:t></w:r></w:p>
    <w:p><w:r><w:t>Second paragraph for length.</w:t></w:r></w:p>
  </w:body>
</w:document>"""


def _minimal_docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", DOCX_CONTENT_TYPES)
        zf.writestr("_rels/.rels", DOCX_RELS)
        zf.writestr("word/document.xml", DOCX_DOCUMENT)
    return buf.getvalue()


def test_extract_text_from_docx_success():
    text = extract_text_from_docx(_minimal_docx_bytes())
    assert "Hello from DOCX ingest test" in text
    assert "Second paragraph" in text


def test_extract_text_from_docx_too_small():
    with pytest.raises(ValueError, match="too small"):
        extract_text_from_docx(b"x" * 50)


def test_extract_text_from_docx_invalid():
    with pytest.raises(ValueError, match="Could not read DOCX"):
        extract_text_from_docx(b"0" * 200)
