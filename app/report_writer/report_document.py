"""Build a structured ReportDocument from claim data for export renderers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.config import REPORT_EXPORT_DAMAGE_PHOTOS_ONLY, REPORT_EXPORT_MAX_PHOTOS
from app.report_writer.boilerplate import (
    default_client_name,
    default_inspection_date,
    default_prepared_by,
    engineering_letter_paragraphs,
    include_engineering_letter,
    observations_text,
    purpose_text,
    weather_text,
)
from app.report_writer.constants import get_report_type, report_type_def, sections_for_type
from app.report_writer.damage_detection import count_photo_stats, photo_review_summary, select_export_images
from app.report_writer.image_utils import compress_image_bytes
from app.report_writer.storage import read_claim_image_bytes


def _download_drive_image(img: dict) -> bytes | None:
    drive_file_id = img.get("drive_file_id")
    if not drive_file_id:
        return None
    try:
        from app.drive_client import download_drive_file_bytes

        data, _ = download_drive_file_bytes(drive_file_id, img.get("filename") or drive_file_id)
        return data
    except Exception:
        return None


def _read_image_bytes(img: dict) -> bytes | None:
    path = img.get("storage_path")
    if path:
        try:
            return read_claim_image_bytes(path)
        except OSError:
            pass
    return _download_drive_image(img)


@dataclass
class ReportPhoto:
    data: bytes
    caption: str
    file_extension: str = "jpeg"
    cx: int = 0
    cy: int = 0


@dataclass
class ReportSection:
    key: str
    label: str
    content: str


@dataclass
class ReportDocument:
    title: str
    claim_id: str
    report_number: str
    client_name: str
    address_line1: str
    address_line2: str
    full_address: str
    inspection_date: str
    prepared_by: str
    include_engineering_letter: bool
    purpose_text: str
    observations_text: str
    weather_text: str
    engineering_letter_paragraphs: list[str]
    sections: list[ReportSection] = field(default_factory=list)
    photos: list[ReportPhoto] = field(default_factory=list)


def _split_address(raw: str) -> tuple[str, str]:
    raw = (raw or "").strip()
    if not raw:
        return "", ""
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) >= 3:
        return parts[0], ", ".join(parts[1:])
    if len(parts) == 2:
        return parts[0], parts[1]
    return raw, ""


def _photo_caption(vision: dict | None) -> str:
    if not vision:
        return "Inspection photograph."
    cap = (vision.get("caption") or "").strip()
    obs = (vision.get("observations") or "").strip()
    if cap and obs:
        return f"{cap} {obs}"
    return cap or obs or "Inspection photograph."


def build_report_document(
    claim: dict,
    sections: dict[str, dict],
    images: list[dict] | None = None,
) -> ReportDocument:
    meta = claim.get("property_metadata") or {}
    type_id = get_report_type(meta)
    type_def = report_type_def(type_id)
    title = (claim.get("title") or type_def.export_title).strip()
    claim_id = str(claim.get("claim_id") or "")
    report_number = claim_id[:8].upper() if claim_id else "DRAFT"
    client = default_client_name(meta, title)
    address_raw = (meta.get("address") or "").strip()
    line1, line2 = _split_address(address_raw)
    full_address = address_raw or "Unknown"
    conclusion = (
        (sections.get("recommendations_conclusion") or {}).get("content")
        or (sections.get("conclusion") or {}).get("content")
        or ""
    )

    doc_sections: list[ReportSection] = []
    for key, label in sections_for_type(type_id):
        content = ((sections.get(key) or {}).get("content") or "").strip()
        if content:
            doc_sections.append(ReportSection(key=key, label=label.upper(), content=content))

    photos: list[ReportPhoto] = []
    img_list = select_export_images(
        images or [],
        max_photos=REPORT_EXPORT_MAX_PHOTOS,
        damage_only=REPORT_EXPORT_DAMAGE_PHOTOS_ONLY,
    )
    if img_list:
        workers = min(4, len(img_list))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            raw_bytes_list = list(pool.map(_read_image_bytes, img_list))
    else:
        raw_bytes_list = []

    for img, raw in zip(img_list, raw_bytes_list):
        if not raw:
            continue
        # Sized for ~3.5" embed in PDF/DOCX; keeps memory and render time down on large claims.
        data, ext = compress_image_bytes(raw, max_dimension=800, quality=75)
        from app.report_writer.image_utils import image_emu_size

        cx, cy = image_emu_size(data)
        photos.append(
            ReportPhoto(
                data=data,
                caption=_photo_caption(img.get("vision_analysis")),
                file_extension=ext,
                cx=cx,
                cy=cy,
            )
        )

    obs = observations_text(meta)
    if not (meta.get("boilerplate_observations") or "").strip():
        stats = count_photo_stats(images or [])
        summary = photo_review_summary(stats["examined"], stats["with_damage"])
        if summary:
            obs = f"{obs} {summary}"

    return ReportDocument(
        title=title,
        claim_id=claim_id,
        report_number=report_number,
        client_name=client,
        address_line1=line1 or address_raw,
        address_line2=line2,
        full_address=full_address,
        inspection_date=default_inspection_date(meta),
        prepared_by=default_prepared_by(meta),
        include_engineering_letter=type_id == "engineering" and include_engineering_letter(meta),
        purpose_text=purpose_text(meta),
        observations_text=obs,
        weather_text=weather_text(meta),
        engineering_letter_paragraphs=engineering_letter_paragraphs(meta, line1 or address_raw, conclusion),
        sections=doc_sections,
        photos=photos,
    )
