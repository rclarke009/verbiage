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
    Table,
    TableStyle,
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


def _footer(canvas, doc_template, *, address: str, page_num: int, include_address: bool, include_page_numbers: bool) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.grey)
    if include_address:
        canvas.drawString(0.7 * inch, 0.5 * inch, address.upper()[:80])
    if include_page_numbers:
        canvas.drawRightString(PAGE_W - 0.7 * inch, 0.5 * inch, f"Page {page_num}")
    canvas.restoreState()


def render_report_pdf(doc: ReportDocument) -> bytes:
    buf = io.BytesIO()
    story: list = []
    styles = _styles()

    def on_page(canvas, doc_template) -> None:
        page_num = canvas.getPageNumber()
        logical = doc.starting_page_number + page_num - 1
        if doc.skip_cover or page_num > 1:
            _footer(
                canvas,
                doc_template,
                address=doc.address_line1 or doc.full_address,
                page_num=logical,
                include_address=doc.include_address_footer,
                include_page_numbers=doc.include_page_numbers,
            )

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

    if not doc.skip_cover:
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
    if doc.include_weather:
        story.append(Paragraph("<b>WEATHER HISTORY:</b>", ParagraphStyle("w", parent=styles["body"], textColor=ACCENT, fontName="Helvetica-Bold")))
        story.append(Paragraph(doc.weather_text, styles["body"]))
        story.append(
            Paragraph(
                "<b>WEATHER HISTORY CONTINUED</b>",
                ParagraphStyle("wc", parent=styles["body"], textColor=ACCENT, fontName="Helvetica-Bold"),
            )
        )
        story.append(Paragraph(doc.weather_continued_text, styles["body"]))
        story.append(Paragraph(doc.weather_attribution_text, styles["body"]))
    story.extend(_property_appraiser_flow(doc, styles))
    story.extend(_property_location_flow(doc, styles))
    story.extend(_historical_aerials_flow(doc, styles))
    story.append(PageBreak())

    for section in doc.sections:
        story.append(Paragraph(section.label, styles["section"]))
        for para in _split_paragraphs(section.content):
            story.append(Paragraph(para.replace("\n", "<br/>"), styles["body"]))
        story.append(Spacer(1, 0.1 * inch))

    if doc.specimens:
        story.append(PageBreak())
        story.append(Paragraph("SPECIMEN TESTING", styles["section"]))
        story.append(Spacer(1, 0.1 * inch))
        table_data = [["Specimen", "Type", "Result", "Notes"]]
        for spec in doc.specimens:
            table_data.append([spec.label, spec.testing_type_id, spec.result, spec.notes[:80]])
        table = Table(table_data, colWidths=[1.6 * inch, 1.3 * inch, 1.2 * inch, 2.6 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(table)

    if doc.photos:
        story.append(PageBreak())
        story.append(Paragraph("INSPECTION PHOTOGRAPHS", styles["section"]))
        story.append(Spacer(1, 0.1 * inch))
        per_page = 2 if doc.pages_tuned else 4
        img_w = 3.2 * inch if doc.pages_tuned else 3.2 * inch
        img_h = 2.0 * inch if doc.pages_tuned else 2.4 * inch
        for i in range(0, len(doc.photos), per_page):
            group = doc.photos[i : i + per_page]
            for photo in group:
                img = Image(io.BytesIO(photo.data), width=img_w, height=img_h)
                story.append(img)
                story.append(Paragraph(photo.caption, styles["body"]))
                story.append(Spacer(1, 0.08 * inch))
            if i + per_page < len(doc.photos):
                story.append(PageBreak())

    def first_page(canvas, doc_template) -> None:
        if doc.skip_cover:
            on_page(canvas, doc_template)
        else:
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
    flow.append(Paragraph("Licensed Professional Engineer", styles["body"]))
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


def _property_appraiser_flow(doc: ReportDocument, styles: dict[str, ParagraphStyle]) -> list:
    if not doc.property_appraiser:
        return []
    photo = doc.property_appraiser
    flow: list = [PageBreak(), Paragraph("PROPERTY APPRAISER", styles["section"]), Spacer(1, 0.1 * inch)]
    width = 6.5 * inch
    height = 8.0 * inch
    if photo.cx and photo.cy:
        aspect = photo.cy / photo.cx
        height = min(width * aspect, 8.0 * inch)
    flow.append(Image(io.BytesIO(photo.data), width=width, height=height))
    flow.append(Paragraph(photo.caption, styles["body"]))
    if doc.property_appraiser_attribution:
        flow.append(Paragraph(doc.property_appraiser_attribution, styles["body"]))
    return flow


def _property_location_flow(doc: ReportDocument, styles: dict[str, ParagraphStyle]) -> list:
    if not doc.property_satellite and not doc.property_roadmap:
        return []
    flow: list = [PageBreak(), Paragraph("PROPERTY LOCATION", styles["section"]), Spacer(1, 0.1 * inch)]
    row: list = []
    for photo in (doc.property_satellite, doc.property_roadmap):
        if not photo:
            continue
        cell = [
            Image(io.BytesIO(photo.data), width=3.1 * inch, height=2.3 * inch),
            Paragraph(photo.caption, styles["body"]),
        ]
        row.append(cell)
    if len(row) == 2:
        table = Table([[row[0][0], row[1][0]], [row[0][1], row[1][1]]], colWidths=[3.2 * inch, 3.2 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        flow.append(table)
    elif row:
        flow.append(row[0][0])
        flow.append(row[0][1])
    flow.append(Paragraph(doc.property_map_attribution, styles["body"]))
    return flow


def _historical_aerials_flow(doc: ReportDocument, styles: dict[str, ParagraphStyle]) -> list:
    if not doc.historical_aerials:
        return []
    flow: list = [
        PageBreak(),
        Paragraph("HISTORICAL AERIAL IMAGERY", styles["section"]),
        Spacer(1, 0.1 * inch),
    ]
    if doc.historical_aerials_comment:
        flow.append(Paragraph(doc.historical_aerials_comment, styles["body"]))
        flow.append(Spacer(1, 0.08 * inch))
    photos = doc.historical_aerials
    for i in range(0, len(photos), 2):
        pair = photos[i : i + 2]
        cells_img = []
        cells_cap = []
        for photo in pair:
            cells_img.append(Image(io.BytesIO(photo.data), width=3.1 * inch, height=2.3 * inch))
            cells_cap.append(Paragraph(photo.caption, styles["body"]))
        if len(pair) == 2:
            table = Table([cells_img, cells_cap], colWidths=[3.2 * inch, 3.2 * inch])
            table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            flow.append(table)
        else:
            flow.append(cells_img[0])
            flow.append(cells_cap[0])
        flow.append(Spacer(1, 0.08 * inch))
    flow.append(Paragraph(doc.historical_aerials_attribution, styles["body"]))
    return flow


def _split_paragraphs(text: str) -> list[str]:
    chunks = [p.strip() for p in text.split("\n\n") if p.strip()]
    if chunks:
        return chunks
    return [line.strip() for line in text.splitlines() if line.strip()] or [text]
