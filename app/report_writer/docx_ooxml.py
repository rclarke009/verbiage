"""WordprocessingML XML builders for DOCX export."""

from __future__ import annotations

import html
import re


def xml_escape(text: str) -> str:
    return html.escape(text, quote=False)


def page_break() -> str:
    return "<w:p><w:r><w:br w:type=\"page\"/></w:r></w:p>"


def xml_spacer(before: int = 0, after: int = 0) -> str:
    return f"<w:p><w:pPr><w:spacing w:before=\"{before}\" w:after=\"{after}\"/></w:pPr></w:p>"


def xml_paragraph(
    text: str,
    *,
    bold: bool = False,
    color: str | None = None,
    font_size: float | None = None,
    spacing_before: int | None = None,
    spacing_after: int | None = None,
    centered: bool = False,
) -> str:
    p_pr = ""
    if centered:
        p_pr += "<w:jc w:val=\"center\"/>"
    if spacing_before is not None or spacing_after is not None:
        p_pr += f"<w:spacing w:before=\"{spacing_before or 0}\" w:after=\"{spacing_after or 0}\"/>"
    p_pr_tag = f"<w:pPr>{p_pr}</w:pPr>" if p_pr else ""
    font = "Graphik Bold" if bold else "Graphik"
    r_pr = f"<w:rFonts w:ascii=\"{font}\" w:hAnsi=\"{font}\" w:eastAsia=\"{font}\"/>"
    if bold:
        r_pr += "<w:b/>"
    if font_size is not None:
        half = int(font_size * 2)
        r_pr += f"<w:sz w:val=\"{half}\"/><w:szCs w:val=\"{half}\"/>"
    if color:
        r_pr += f"<w:color w:val=\"{color}\"/>"
    return (
        f"<w:p>{p_pr_tag}<w:r><w:rPr>{r_pr}</w:rPr>"
        f"<w:t xml:space=\"preserve\">{xml_escape(text)}</w:t></w:r></w:p>"
    )


def xml_engineering_paragraph(text: str, *, spacing_before: int = 0, spacing_after: int = 0) -> str:
    return (
        f"<w:p><w:pPr><w:spacing w:before=\"{spacing_before}\" w:after=\"{spacing_after}\"/></w:pPr>"
        f"<w:r><w:rPr><w:rFonts w:ascii=\"Gill Sans\" w:hAnsi=\"Gill Sans\"/></w:rPr>"
        f"<w:t xml:space=\"preserve\">{xml_escape(text)}</w:t></w:r></w:p>"
    )


def xml_large_bold(title: str, *, color: str = "276091", spacing_before: int = 446, spacing_after: int = 0) -> str:
    return (
        f"<w:p><w:pPr><w:spacing w:before=\"{spacing_before}\" w:after=\"{spacing_after}\"/></w:pPr>"
        f"<w:r><w:rPr><w:rFonts w:ascii=\"Graphik Bold\" w:hAnsi=\"Graphik Bold\"/>"
        f"<w:b/><w:sz w:val=\"48\"/><w:color w:val=\"{color}\"/></w:rPr>"
        f"<w:t xml:space=\"preserve\">{xml_escape(title)}</w:t></w:r></w:p>"
    )


def xml_overview_title(text: str, *, spacing_before: int = 446, spacing_after: int = 0) -> str:
    return (
        f"<w:p><w:pPr><w:spacing w:before=\"{spacing_before}\" w:after=\"{spacing_after}\"/></w:pPr>"
        f"<w:r><w:rPr><w:rFonts w:ascii=\"Graphik Bold\" w:hAnsi=\"Graphik Bold\"/>"
        f"<w:b/><w:sz w:val=\"54\"/><w:color w:val=\"276091\"/></w:rPr>"
        f"<w:t xml:space=\"preserve\">{xml_escape(text)}</w:t></w:r></w:p>"
    )


def xml_overview_address_subtitle(text: str, *, spacing_after: int = 240) -> str:
    return (
        f"<w:p><w:pPr><w:spacing w:after=\"{spacing_after}\"/></w:pPr>"
        f"<w:r><w:rPr><w:rFonts w:ascii=\"Graphik\" w:hAnsi=\"Graphik\"/>"
        f"<w:sz w:val=\"32\"/><w:color w:val=\"276091\"/></w:rPr>"
        f"<w:t xml:space=\"preserve\">{xml_escape(text)}</w:t></w:r></w:p>"
    )


def xml_overview_row(label: str, value: str, *, spacing_after: int = 120) -> str:
    return (
        f"<w:p><w:pPr><w:spacing w:after=\"{spacing_after}\"/></w:pPr>"
        f"<w:r><w:rPr><w:rFonts w:ascii=\"Graphik Semibold\" w:hAnsi=\"Graphik Semibold\"/>"
        f"<w:sz w:val=\"32\"/><w:color w:val=\"276091\"/></w:rPr>"
        f"<w:t xml:space=\"preserve\">{xml_escape(label)}:</w:t></w:r>"
        f"<w:r><w:rPr><w:rFonts w:ascii=\"Graphik\" w:hAnsi=\"Graphik\"/></w:rPr>"
        f"<w:t xml:space=\"preserve\"> {xml_escape(value)}</w:t></w:r></w:p>"
    )


def xml_body_paragraphs(text: str) -> str:
    chunks = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not chunks:
        chunks = [line.strip() for line in text.splitlines() if line.strip()]
    return "".join(xml_paragraph(p, spacing_after=120) for p in chunks)


def xml_full_page_image(rel_id: str, doc_pr_id: int, cx: int, cy: int) -> str:
    return f"""
    <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
         xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
         xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
         xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
         xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
      <w:r><w:drawing>
        <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="251658240"
                   behindDoc="0" layoutInCell="1" locked="0" allowOverlap="1">
          <wp:simplePos x="0" y="0"/>
          <wp:positionH relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionH>
          <wp:positionV relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionV>
          <wp:extent cx="{cx}" cy="{cy}"/>
          <wp:wrapNone/>
          <wp:docPr id="{doc_pr_id}" name="Image{doc_pr_id}"/>
          <wp:cNvGraphicFramePr/>
          <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
            <pic:pic>
              <pic:nvPicPr><pic:cNvPr id="0" name="Image{doc_pr_id}"/><pic:cNvPicPr/></pic:nvPicPr>
              <pic:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
              <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
                <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
            </pic:pic>
          </a:graphicData></a:graphic>
        </wp:anchor>
      </w:drawing></w:r>
    </w:p>"""


def xml_cover_text_with_tabs(parts: list[str], *, x_emu: int, y_emu: int, font_size: int = 14) -> str:
    """Cover overlay text using tabs between label/value segments."""
    text_box_id = abs(hash(tuple(parts))) % 1_000_000
    text_box_width = int(4.0 * 914_400)
    runs = ""
    for i, part in enumerate(parts):
        if i:
            runs += "<w:tab/>"
        runs += (
            f"<w:r><w:rPr><w:rFonts w:ascii=\"Graphik\" w:hAnsi=\"Graphik\"/>"
            f"<w:sz w:val=\"{font_size * 2}\"/><w:color w:val=\"10325d\"/></w:rPr>"
            f"<w:t xml:space=\"preserve\">{xml_escape(part)}</w:t></w:r>"
        )
    return f"""
    <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
         xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
         xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
         xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
      <w:r><w:drawing>
        <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="251658241"
                   behindDoc="0" layoutInCell="1" locked="0" allowOverlap="1">
          <wp:positionH relativeFrom="page"><wp:posOffset>{x_emu}</wp:posOffset></wp:positionH>
          <wp:positionV relativeFrom="page"><wp:posOffset>{y_emu}</wp:posOffset></wp:positionV>
          <wp:extent cx="{text_box_width}" cy="{int(0.5 * 914_400)}"/>
          <wp:wrapNone/>
          <wp:docPr id="{text_box_id}" name="TextBox{text_box_id}"/>
          <a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
            <wps:wsp>
              <wps:cNvPr id="{text_box_id}" name="TextBox{text_box_id}"/>
              <wps:cNvSpPr txBox="1"/>
              <wps:spPr><a:xfrm><a:off x="{x_emu}" y="{y_emu}"/>
                <a:ext cx="{text_box_width}" cy="{int(0.5 * 914_400)}"/></a:xfrm>
                <a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></wps:spPr>
              <wps:txbx><w:txbxContent><w:p>{runs}</w:p></w:txbxContent></wps:txbx>
            </wps:wsp>
          </a:graphicData></a:graphic>
        </wp:anchor>
      </w:drawing></w:r>
    </w:p>"""


def xml_image_paragraph(rel_id: str, doc_pr_id: int, cx: int, cy: int, *, centered: bool = True) -> str:
    jc = "<w:jc w:val=\"center\"/>" if centered else ""
    return f"""
    <w:p><w:pPr>{jc}</w:pPr><w:r><w:drawing>
      <wp:inline distT="0" distB="0" distL="0" distR="0"
        xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
        xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
        xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
        xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
        <wp:extent cx="{cx}" cy="{cy}"/>
        <wp:docPr id="{doc_pr_id}" name="Image{doc_pr_id}"/>
        <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
          <pic:pic>
            <pic:nvPicPr><pic:cNvPr id="0" name="Image{doc_pr_id}"/><pic:cNvPicPr/></pic:nvPicPr>
            <pic:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
            <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
              <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
          </pic:pic>
        </a:graphicData></a:graphic>
      </wp:inline>
    </w:drawing></w:r></w:p>"""


def xml_anchored_image(rel_id: str, doc_pr_id: int, cx: int, cy: int) -> str:
    return f"""
    <w:p><w:r><w:drawing>
      <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="251658242"
        xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
        xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
        xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
        xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
        <wp:simplePos x="0" y="0"/>
        <wp:positionH relativeFrom="column"><wp:align>right</wp:align></wp:positionH>
        <wp:positionV relativeFrom="paragraph"><wp:posOffset>0</wp:posOffset></wp:positionV>
        <wp:extent cx="{cx}" cy="{cy}"/>
        <wp:wrapNone/>
        <wp:docPr id="{doc_pr_id}" name="Stamp{doc_pr_id}"/>
        <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
          <pic:pic>
            <pic:nvPicPr><pic:cNvPr id="0" name="Stamp{doc_pr_id}"/><pic:cNvPicPr/></pic:nvPicPr>
            <pic:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
            <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
              <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
          </pic:pic>
        </a:graphicData></a:graphic>
      </wp:anchor>
    </w:drawing></w:r></w:p>"""


def xml_photo_cell(rel_id: str, doc_pr_id: int, caption: str, cx: int, cy: int) -> str:
    cap = xml_paragraph(caption, spacing_before=60, spacing_after=0)
    img = xml_image_paragraph(rel_id, doc_pr_id, cx, cy, centered=True)
    return img + cap


def xml_photo_table(entries: list[tuple[str, int, str, int, int]], *, columns: int) -> str:
    col_width = 5200 if columns > 1 else 9000
    xml = (
        '<w:tbl xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:tblPr><w:tblW w:w=\"0\" w:type=\"auto\"/><w:tblLayout w:type=\"fixed\"/>"
        "<w:jc w:val=\"center\"/></w:tblPr><w:tblGrid>"
    )
    for _ in range(columns):
        xml += f"<w:gridCol w:w=\"{col_width}\"/>"
    xml += "</w:tblGrid>"
    idx = 0
    while idx < len(entries):
        xml += "<w:tr><w:trPr><w:cantSplit/></w:trPr>"
        for _ in range(columns):
            xml += f"<w:tc><w:tcPr><w:tcW w:w=\"{col_width}\" w:type=\"dxa\"/></w:tcPr>"
            if idx < len(entries):
                rel_id, doc_pr_id, caption, cx, cy = entries[idx]
                xml += xml_photo_cell(rel_id, doc_pr_id, caption, cx, cy)
                idx += 1
            else:
                xml += "<w:p/>"
            xml += "</w:tc>"
        xml += "</w:tr>"
    xml += "</w:tbl>"
    return xml


def wrap_document_xml(body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
            xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
  <w:body>
    {body}
  </w:body>
</w:document>"""


def wrap_rels_xml(body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{body}
</Relationships>"""
