"""PDF report renderer (WindowTest2-style layout via ReportLab)."""

from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.report_writer.image_utils import load_asset_bytes
from app.report_writer.report_document import ReportDocument

BRAND = colors.HexColor("#276091")
ACCENT = colors.HexColor("#5BA3D6")
PAGE_W, PAGE_H = letter


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Heading1"],
            fontSize=24,
            textColor=BRAND,
            spaceAfter=12,
            fontName="Helvetica-Bold",
        ),
        "section": ParagraphStyle(
            "section",
            parent=base["Heading2"],
            fontSize=18,
            textColor=BRAND,
            spaceBefore=18,
            spaceAfter=8,
            fontName="Helvetica-Bold",
        ),
        "label": ParagraphStyle(
            "label",
            parent=base["Normal"],
            fontSize=11,
            textColor=BRAND,
            fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            spaceAfter=10,
        ),
        "meta": ParagraphStyle(
            "meta",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
        ),
        "cover": ParagraphStyle(
            "cover",
            parent=base["Normal"],
            fontSize=14,
            textColor=colors.HexColor("#10325d"),
            fontName="Helvetica-Bold",
        ),
    }


def _footer(canvas, doc_template, *, address: str, page_num: int, total_pages: int) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.grey)
    canvas.drawString(0.7 * inch, 0.5 * inch, address.upper()[:80])
    canvas.drawRightString(PAGE_W - 0.7 * inch, 0.5 * inch, f"Page {page_num} of {total_pages}")
    canvas.restoreState()


def render_report_pdf(doc: ReportDocument) -> bytes:
    buf = io.BytesIO()
    story: list = []
    styles = _styles()

    # Pre-count pages roughly for footer (SimpleDocTemplate two-pass)
    page_count = 1  # cover
    page_count += 1  # overview
    if doc.include_engineering_letter:
        page_count += 1
    page_count += 1  # purpose/weather
    page_count += max(1, len(doc.sections))
    if doc.photos:
        page_count += max(1, (len(doc.photos) + 3) // 4)

    def on_page(canvas, doc_template) -> None:
        page_num = canvas.getPageNumber()
        if page_num > 1:
            _footer(canvas, doc_template, address=doc.address_line1 or doc.full_address, page_num=page_num, total_pages=page_count)

    pdf = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.75 * inch,
    )

    # Cover page drawn via onFirstPage callback below
    def draw_cover(canvas, _doc) -> None:
        try:
            cover = ImageReader(io.BytesIO(load_asset_bytes("cover_page.png")))
            canvas.drawImage(cover, 0, 0, width=PAGE_W, height=PAGE_H, preserveAspectRatio=True, anchor="c")
        except Exception:
            canvas.setFillColor(BRAND)
            canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(colors.HexColor("#10325d"))
        y = 1.6 * inch
        for line in [
            "Residential",
            f"Prepared for: {doc.client_name}",
            f"Address: {doc.address_line1}",
            doc.address_line2,
        ]:
            if line:
                canvas.drawString(0.83 * inch, y, line)
                y -= 0.25 * inch

    # Build content starting page 2
    story.append(PageBreak())
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("OVERVIEW", styles["title"]))
    if doc.address_line1:
        story.append(Paragraph(doc.address_line1, styles["label"]))
    story.append(Spacer(1, 0.15 * inch))
    for label, value in [
        ("REPORT NUMBER", doc.report_number),
        ("DATE OF INSPECTIONS", doc.inspection_date),
        ("PREPARED FOR", doc.client_name),
        ("PREPARED BY", doc.prepared_by),
        ("ADDRESS", doc.full_address),
    ]:
        story.append(Paragraph(f"<b>{label}:</b> {value}", styles["meta"]))
        story.append(Spacer(1, 0.08 * inch))
    story.append(PageBreak())

    if doc.include_engineering_letter:
        story.extend(_engineering_letter_flow(doc, styles))
        story.append(PageBreak())

    story.append(Paragraph("<b>PURPOSE:</b>", ParagraphStyle("p", parent=styles["body"], textColor=ACCENT, fontName="Helvetica-Bold")))
    story.append(Paragraph(doc.purpose_text, styles["body"]))
    story.append(Paragraph("<b>OBSERVATIONS:</b>", ParagraphStyle("o", parent=styles["body"], textColor=ACCENT, fontName="Helvetica-Bold")))
    story.append(Paragraph(doc.observations_text, styles["body"]))
    story.append(Paragraph("<b>WEATHER HISTORY:</b>", ParagraphStyle("w", parent=styles["body"], textColor=ACCENT, fontName="Helvetica-Bold")))
    story.append(Paragraph(doc.weather_text, styles["body"]))
    story.append(PageBreak())

    for section in doc.sections:
        story.append(Paragraph(section.label, styles["section"]))
        for para in _split_paragraphs(section.content):
            story.append(Paragraph(para.replace("\n", "<br/>"), styles["body"]))
        story.append(Spacer(1, 0.1 * inch))

    if doc.photos:
        story.append(PageBreak())
        story.append(Paragraph("INSPECTION PHOTOGRAPHS", styles["section"]))
        story.append(Spacer(1, 0.1 * inch))
        for i in range(0, len(doc.photos), 4):
            group = doc.photos[i : i + 4]
            for photo in group:
                img = Image(io.BytesIO(photo.data), width=3.2 * inch, height=2.4 * inch)
                story.append(img)
                story.append(Paragraph(photo.caption, styles["body"]))
                story.append(Spacer(1, 0.08 * inch))
            if i + 4 < len(doc.photos):
                story.append(PageBreak())

    def first_page(canvas, doc_template) -> None:
        draw_cover(canvas, doc_template)

    def later_pages(canvas, doc_template) -> None:
        on_page(canvas, doc_template)

    pdf.build(story, onFirstPage=first_page, onLaterPages=later_pages)
    return buf.getvalue()


def _engineering_letter_flow(doc: ReportDocument, styles: dict[str, ParagraphStyle]) -> list:
    flow: list = []
    flow.append(Paragraph("ENGINEERING LETTER", styles["title"]))
    flow.append(Spacer(1, 0.1 * inch))
    for line in [
        doc.inspection_date,
        doc.client_name,
        doc.address_line1,
        doc.address_line2,
        "K. Renevier, P.E.",
        "FL Reg. No. 98372",
        "1281 Trailhead Pl",
        "Harrison, OH 45030",
    ]:
        if line:
            flow.append(Paragraph(line, styles["body"]))
    first = doc.client_name.split()[0] if doc.client_name else "Client"
    flow.append(Spacer(1, 0.1 * inch))
    flow.append(Paragraph(f"Greetings {first},", styles["body"]))
    for para in doc.engineering_letter_paragraphs:
        flow.append(Paragraph(para, styles["body"]))
    flow.append(Paragraph("Respectfully Submitted,", styles["body"]))
    flow.append(Paragraph("Stuart Jay Clarke", styles["body"]))
    flow.append(Paragraph("K. Renevier, P.E.", styles["body"]))
    try:
        stamp = load_asset_bytes("engineer_stamp.png")
        flow.append(Image(io.BytesIO(stamp), width=1.5 * inch, height=1.5 * inch))
    except OSError:
        pass
    disclaimer = (
        "Kyle Renevier, State of Florida, Professional Engineer, License No. 98372. "
        "This item has been digitally signed and sealed by Kyle Renevier on the date indicated here. "
        "Printed copies of this document are not considered signed and sealed."
    )
    flow.append(Paragraph(disclaimer, styles["body"]))
    return flow


def _split_paragraphs(text: str) -> list[str]:
    chunks = [p.strip() for p in text.split("\n\n") if p.strip()]
    if chunks:
        return chunks
    return [line.strip() for line in text.splitlines() if line.strip()] or [text]
