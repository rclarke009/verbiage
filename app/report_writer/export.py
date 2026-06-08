"""Export claim draft to formatted DOCX and PDF."""

from __future__ import annotations

from app.report_writer.docx_renderer import render_report_docx
from app.report_writer.pdf_renderer import render_report_pdf
from app.report_writer.report_document import ReportDocument, build_report_document


def build_report_from_claim(
    claim: dict,
    sections: dict[str, dict],
    images: list[dict] | None = None,
) -> ReportDocument:
    return build_report_document(claim, sections, images)


def draft_to_docx_bytes(
    sections: dict[str, dict],
    title: str = "Engineering Report",
    *,
    claim: dict | None = None,
    images: list[dict] | None = None,
) -> bytes:
    claim_data = claim or {"title": title, "claim_id": "", "property_metadata": {}}
    if title and not claim_data.get("title"):
        claim_data = {**claim_data, "title": title}
    doc = build_report_document(claim_data, sections, images)
    return render_report_docx(doc)


def draft_to_pdf_bytes(
    sections: dict[str, dict],
    title: str = "Engineering Report",
    *,
    claim: dict | None = None,
    images: list[dict] | None = None,
) -> bytes:
    claim_data = claim or {"title": title, "claim_id": "", "property_metadata": {}}
    if title and not claim_data.get("title"):
        claim_data = {**claim_data, "title": title}
    doc = build_report_document(claim_data, sections, images)
    return render_report_pdf(doc)
