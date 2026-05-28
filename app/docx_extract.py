"""
Extract plain text from DOCX bytes for ingest.
Uses python-docx; raises ValueError on empty output or unreadable files.
"""

from io import BytesIO

from docx import Document


def extract_text_from_docx(data: bytes) -> str:
    """
    Extract full text from DOCX bytes. Returns stripped string.

    Raises:
        ValueError: If file is too small, unreadable, or yields no text.
    """
    if not data or len(data) < 100:
        raise ValueError("File too small or empty to be a valid DOCX")
    try:
        doc = Document(BytesIO(data))
        parts = []
        for para in doc.paragraphs:
            t = (para.text or "").strip()
            if t:
                parts.append(t)
        text = "\n".join(parts).strip()
        if not text or len(text) < 10:
            raise ValueError("DOCX produced no extractable text (may be empty)")
        return text
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not read DOCX: {e}") from e
