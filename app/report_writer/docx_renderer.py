"""Template-based DOCX report renderer (WindowTest2-style)."""

from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from pathlib import Path

from app.report_writer.docx_ooxml import (
    page_break,
    wrap_document_xml,
    wrap_rels_xml,
    xml_anchored_image,
    xml_body_paragraphs,
    xml_cover_text_with_tabs,
    xml_engineering_paragraph,
    xml_full_page_image,
    xml_large_bold,
    xml_overview_address_subtitle,
    xml_overview_row,
    xml_overview_title,
    xml_paragraph,
    xml_photo_table,
    xml_spacer,
)
from app.report_writer.image_utils import compress_image_bytes, image_emu_size, load_asset_bytes
from app.report_writer.report_document import ReportDocument

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
TEMPLATE_NAME = "BaseTemplateWithImage.docx"
EMU_PER_INCH = 914_400


class _ImageRef:
    def __init__(self, rel_id: str, doc_pr_id: int, cx: int, cy: int):
        self.rel_id = rel_id
        self.doc_pr_id = doc_pr_id
        self.cx = cx
        self.cy = cy


class DocxReportRenderer:
    def __init__(self) -> None:
        self._image_index = 1
        self._used_rel_ids: set[str] = set()
        self._rels = ""
        self._used_extensions: set[str] = set()
        self._media: dict[str, bytes] = {}

    def render(self, doc: ReportDocument) -> bytes:
        template_path = ASSETS_DIR / TEMPLATE_NAME
        if not template_path.is_file():
            raise FileNotFoundError(f"DOCX template not found: {template_path}")

        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            with zipfile.ZipFile(template_path, "r") as zf:
                zf.extractall(temp_dir)

            media_dir = temp_dir / "word" / "media"
            if media_dir.exists():
                shutil.rmtree(media_dir)
            media_dir.mkdir(parents=True)

            self._image_index = 1
            self._used_rel_ids = set()
            self._rels = self._read_existing_rels(temp_dir)
            self._used_extensions = set()
            self._media = {}

            body = self._build_body(doc)

            doc_xml_path = temp_dir / "word" / "document.xml"
            doc_xml_path.write_text(wrap_document_xml(body), encoding="utf-8")

            rels_path = temp_dir / "word" / "_rels" / "document.xml.rels"
            rels_path.write_text(wrap_rels_xml(self._rels), encoding="utf-8")

            for name, data in self._media.items():
                (media_dir / name).write_bytes(data)

            self._update_content_types(temp_dir)

            out_buf = io.BytesIO()
            with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as out_zf:
                for path in sorted(temp_dir.rglob("*")):
                    if path.is_file():
                        arcname = path.relative_to(temp_dir).as_posix()
                        out_zf.write(path, arcname)
            return out_buf.getvalue()

    def _read_existing_rels(self, temp_dir: Path) -> str:
        rels_path = temp_dir / "word" / "_rels" / "document.xml.rels"
        if not rels_path.is_file():
            return ""
        text = rels_path.read_text(encoding="utf-8")
        preserved = ""
        for match in __import__("re").finditer(r"<Relationship[^>]*/>", text):
            chunk = match.group(0)
            if "relationships/image" not in chunk:
                preserved += f"  {chunk}\n"
                id_match = __import__("re").search(r'Id="([^"]+)"', chunk)
                if id_match:
                    self._used_rel_ids.add(id_match.group(1))
        return preserved

    def _add_image(
        self,
        data: bytes,
        prefix: str,
        *,
        cx: int | None = None,
        cy: int | None = None,
        compress: bool = True,
    ) -> _ImageRef:
        if compress:
            compressed, ext = compress_image_bytes(data)
        else:
            compressed, ext = data, "jpeg"
        if cx is None or cy is None:
            cx, cy = image_emu_size(compressed)
        rel_id = f"rIdImage{self._image_index}"
        while rel_id in self._used_rel_ids:
            self._image_index += 1
            rel_id = f"rIdImage{self._image_index}"
        self._used_rel_ids.add(rel_id)
        doc_pr_id = self._image_index
        image_name = f"{prefix}{self._image_index}.{ext}"
        self._media[image_name] = compressed
        self._rels += (
            f'  <Relationship Id="{rel_id}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            f'Target="media/{image_name}"/>\n'
        )
        self._used_extensions.add(ext.lower())
        self._image_index += 1
        return _ImageRef(rel_id, doc_pr_id, cx, cy)

    def _build_body(self, doc: ReportDocument) -> str:
        body = ""
        cover_data = load_asset_bytes("cover_page.png")
        cover_ref = self._add_image(
            cover_data,
            "cover",
            cx=int(8.5 * EMU_PER_INCH),
            cy=int(11.0 * EMU_PER_INCH),
        )
        body += xml_full_page_image(cover_ref.rel_id, cover_ref.doc_pr_id, cover_ref.cx, cover_ref.cy)

        x = int(0.83 * EMU_PER_INCH)
        body += xml_cover_text_with_tabs(["Residential"], x_emu=x, y_emu=int(8.96 * EMU_PER_INCH), font_size=20)
        body += xml_cover_text_with_tabs(
            ["Prepared for:", doc.client_name], x_emu=x, y_emu=int(9.34 * EMU_PER_INCH)
        )
        body += xml_cover_text_with_tabs(
            ["Address:", doc.address_line1], x_emu=x, y_emu=int(9.59 * EMU_PER_INCH)
        )
        if doc.address_line2:
            body += xml_cover_text_with_tabs([doc.address_line2], x_emu=x, y_emu=int(9.84 * EMU_PER_INCH))
        body += page_break()

        body += xml_overview_title("OVERVIEW")
        if doc.address_line1:
            body += xml_overview_address_subtitle(doc.address_line1)
        for label, value in [
            ("REPORT NUMBER", doc.report_number),
            ("DATE OF INSPECTIONS", doc.inspection_date),
            ("PREPARED FOR", doc.client_name),
            ("PREPARED BY", doc.prepared_by),
            ("ADDRESS", doc.full_address),
        ]:
            body += xml_overview_row(label, value)
        body += page_break()

        if doc.include_engineering_letter:
            body += self._engineering_letter_xml(doc)
            body += page_break()

        body += xml_paragraph("PURPOSE:", bold=True, color="5BA3D6", spacing_after=0)
        body += xml_paragraph(doc.purpose_text, spacing_after=240)
        body += xml_paragraph("OBSERVATIONS:", bold=True, color="5BA3D6", spacing_after=0)
        body += xml_paragraph(doc.observations_text, spacing_after=240)
        body += xml_paragraph("WEATHER HISTORY:", bold=True, color="5BA3D6", spacing_after=0)
        body += xml_paragraph(doc.weather_text, spacing_after=240)
        body += self._property_location_xml(doc)
        body += page_break()

        for section in doc.sections:
            body += xml_large_bold(section.label)
            body += xml_spacer(after=120)
            body += xml_body_paragraphs(section.content)

        if doc.photos:
            body += page_break()
            body += xml_large_bold("INSPECTION PHOTOGRAPHS")
            body += xml_spacer(after=120)
            idx = 0
            while idx < len(doc.photos):
                group = doc.photos[idx : idx + 4]
                entries = []
                for photo in group:
                    ref = self._add_image(photo.data, "photo", cx=photo.cx, cy=photo.cy, compress=False)
                    entries.append((ref.rel_id, ref.doc_pr_id, photo.caption, ref.cx, ref.cy))
                cols = 2 if len(group) > 1 else 1
                body += xml_photo_table(entries, columns=cols)
                body += xml_spacer(before=120, after=120)
                idx += 4
                if idx < len(doc.photos):
                    body += page_break()

        return body

    def _property_location_xml(self, doc: ReportDocument) -> str:
        if not doc.property_satellite and not doc.property_roadmap:
            return ""
        xml = page_break()
        xml += xml_large_bold("PROPERTY LOCATION")
        xml += xml_spacer(after=120)
        entries = []
        for photo in (doc.property_satellite, doc.property_roadmap):
            if not photo:
                continue
            ref = self._add_image(photo.data, "map", cx=photo.cx, cy=photo.cy, compress=False)
            entries.append((ref.rel_id, ref.doc_pr_id, photo.caption, ref.cx, ref.cy))
        if entries:
            cols = 2 if len(entries) > 1 else 1
            xml += xml_photo_table(entries, columns=cols)
            xml += xml_spacer(before=120, after=60)
            xml += xml_paragraph(doc.property_map_attribution, spacing_after=0)
        return xml

    def _engineering_letter_xml(self, doc: ReportDocument) -> str:
        xml = xml_large_bold("ENGINEERING LETTER") + xml_spacer(after=120)
        xml += xml_engineering_paragraph(doc.inspection_date, spacing_after=120)
        xml += xml_engineering_paragraph(doc.client_name)
        if doc.address_line1:
            xml += xml_engineering_paragraph(doc.address_line1)
        if doc.address_line2:
            xml += xml_engineering_paragraph(doc.address_line2, spacing_after=120)
        for line in [
            "K. Renevier, P.E.",
            "FL Reg. No. 98372",
            "1281 Trailhead Pl",
            "Harrison, OH 45030",
        ]:
            xml += xml_engineering_paragraph(line)
        xml += xml_spacer(before=120)
        first = doc.client_name.split()[0] if doc.client_name else "Client"
        xml += xml_engineering_paragraph(f"Greetings {first},", spacing_after=120)
        for i, para in enumerate(doc.engineering_letter_paragraphs):
            xml += xml_engineering_paragraph(para, spacing_after=60 if i < 2 else 120)
        xml += xml_engineering_paragraph("Respectfully Submitted,", spacing_after=120)
        xml += xml_engineering_paragraph("Stuart Jay Clarke")
        xml += xml_engineering_paragraph("K. Renevier, P.E.", spacing_after=120)

        stamp_data = load_asset_bytes("engineer_stamp.png")
        stamp_ref = self._add_image(
            stamp_data,
            "stamp",
            cx=int(2.35 * EMU_PER_INCH),
            cy=int(2.35 * EMU_PER_INCH),
        )
        xml += xml_anchored_image(stamp_ref.rel_id, stamp_ref.doc_pr_id, stamp_ref.cx, stamp_ref.cy)
        disclaimer = (
            "Kyle Renevier, State of Florida, Professional Engineer, License No. 98372. "
            "This item has been digitally signed and sealed by Kyle Renevier on the date indicated here. "
            "Printed copies of this document are not considered signed and sealed and the signature must "
            "be verified on any electronic copies."
        )
        xml += xml_engineering_paragraph(disclaimer, spacing_before=240)
        return xml

    def _update_content_types(self, temp_dir: Path) -> None:
        ct_path = temp_dir / "[Content_Types].xml"
        if not ct_path.is_file():
            return
        xml = ct_path.read_text(encoding="utf-8")
        known = {"png": "image/png", "jpeg": "image/jpeg", "jpg": "image/jpeg"}
        for ext in self._used_extensions:
            ct = known.get(ext)
            if ct and f'Extension="{ext}"' not in xml:
                xml = xml.replace("</Types>", f'    <Default Extension="{ext}" ContentType="{ct}"/>\n</Types>')
        ct_path.write_text(xml, encoding="utf-8")


def render_report_docx(doc: ReportDocument) -> bytes:
    return DocxReportRenderer().render(doc)
