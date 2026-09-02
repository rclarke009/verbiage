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
    weather_attribution_text,
    weather_continued_text,
    weather_text,
)
from app.geocode.address_format import report_address_lines
from app.report_writer.constants import get_report_type, report_type_def, sections_for_type
from app.report_writer.document_layout import (
    ensure_layout,
    included_specimens,
    ordered_included_photos,
    section_keys_visible,
)
from app.report_writer.damage_detection import count_photo_stats, photo_review_summary, select_export_images
from app.report_writer.image_utils import compress_image_bytes, image_emu_size
from app.report_writer.historical_aerials import (
    _ATTRIBUTION as _HISTORICAL_AERIALS_ATTRIBUTION,
    included_historical_aerials,
)
from app.report_writer.property_maps import read_property_map_bytes
from app.report_writer.property_appraiser import read_property_appraiser_bytes
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
class ReportSpecimen:
    id: str
    label: str
    testing_type_id: str
    result: str
    notes: str = ""


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
    weather_continued_text: str
    weather_attribution_text: str
    engineering_letter_paragraphs: list[str]
    sections: list[ReportSection] = field(default_factory=list)
    photos: list[ReportPhoto] = field(default_factory=list)
    specimens: list[ReportSpecimen] = field(default_factory=list)
    property_satellite: ReportPhoto | None = None
    property_roadmap: ReportPhoto | None = None
    property_map_attribution: str = "Map data © Google"
    property_appraiser: ReportPhoto | None = None
    property_appraiser_attribution: str = ""
    historical_aerials: list[ReportPhoto] = field(default_factory=list)
    historical_aerials_comment: str = ""
    historical_aerials_attribution: str = _HISTORICAL_AERIALS_ATTRIBUTION
    include_page_numbers: bool = True
    include_address_footer: bool = True
    include_weather: bool = True
    skip_cover: bool = False
    pages_tuned: bool = False
    starting_page_number: int = 1


def _photo_caption(vision: dict | None, fallback: str = "") -> str:
    if fallback.strip():
        return fallback.strip()
    if not vision:
        return "Inspection photograph."
    cap = (vision.get("caption") or "").strip()
    obs = (vision.get("observations") or "").strip()
    if cap and obs:
        return f"{cap} {obs}"
    return cap or obs or "Inspection photograph."


def _load_property_map_photo(meta: dict, variant: str, caption: str) -> ReportPhoto | None:
    raw = read_property_map_bytes(meta, variant)
    if not raw:
        return None
    data, ext = compress_image_bytes(raw, max_dimension=1000, quality=80)
    cx, cy = image_emu_size(data, width_inches=3.2, max_height_inches=3.0)
    return ReportPhoto(data=data, caption=caption, file_extension=ext, cx=cx, cy=cy)


def _load_property_appraiser_photo(meta: dict) -> ReportPhoto | None:
    raw = read_property_appraiser_bytes(meta)
    if not raw:
        return None
    data, ext = compress_image_bytes(raw, max_dimension=1400, quality=80)
    cx, cy = image_emu_size(data, width_inches=6.5, max_height_inches=8.0)
    county = (meta.get("property_appraiser_county") or "").strip()
    caption = f"{county} County property appraiser parcel record." if county else "County property appraiser parcel record."
    return ReportPhoto(data=data, caption=caption, file_extension=ext, cx=cx, cy=cy)


def _property_appraiser_attribution(meta: dict) -> str:
    county = (meta.get("property_appraiser_county") or "").strip()
    url = (meta.get("property_appraiser_source_url") or "").strip()
    parts = []
    if county:
        parts.append(f"{county} County Property Appraiser")
    if url:
        parts.append(url)
    return " · ".join(parts) if parts else "County property appraiser public records"


def _load_historical_aerial_photos(meta: dict) -> list[ReportPhoto]:
    photos: list[ReportPhoto] = []
    for item in included_historical_aerials(meta):
        path = (item.get("path") or "").strip()
        if not path:
            continue
        try:
            raw = read_claim_image_bytes(path)
        except OSError:
            continue
        data, ext = compress_image_bytes(raw, max_dimension=1000, quality=80)
        cx, cy = image_emu_size(data, width_inches=3.2, max_height_inches=3.0)
        year = item.get("year")
        caption = f"NAIP aerial imagery — {year}." if year else "NAIP aerial imagery."
        photos.append(ReportPhoto(data=data, caption=caption, file_extension=ext, cx=cx, cy=cy))
    return photos


def build_report_document(
    claim: dict,
    sections: dict[str, dict],
    images: list[dict] | None = None,
    *,
    skip_cover: bool = False,
    pages_tuned: bool = False,
) -> ReportDocument:
    meta = claim.get("property_metadata") or {}
    type_id = get_report_type(meta)
    type_def = report_type_def(type_id)
    layout = ensure_layout(meta, images=images or [])
    title = (claim.get("title") or type_def.export_title).strip()
    claim_id = str(claim.get("claim_id") or "")
    report_number = claim_id[:8].upper() if claim_id else "DRAFT"
    client = default_client_name(meta, title)
    line1, line2, full_address = report_address_lines(meta)
    conclusion = (
        (sections.get("recommendations_conclusion") or {}).get("content")
        or (sections.get("conclusion") or {}).get("content")
        or ""
    )

    labels = dict(sections_for_type(type_id))
    doc_sections: list[ReportSection] = []
    for key in section_keys_visible(layout, type_id):
        content = ((sections.get(key) or {}).get("content") or "").strip()
        if content:
            doc_sections.append(ReportSection(key=key, label=labels.get(key, key).upper(), content=content))

    photos: list[ReportPhoto] = []
    has_layout_photos = bool(layout.get("photos"))
    if has_layout_photos:
        img_list = ordered_included_photos(layout, images or [])
    else:
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

    max_dim = 700 if pages_tuned else 800
    for img, raw in zip(img_list, raw_bytes_list):
        if not raw:
            continue
        data, ext = compress_image_bytes(raw, max_dimension=max_dim, quality=75)
        width_in = 3.2 if pages_tuned else None
        if width_in:
            cx, cy = image_emu_size(data, width_inches=width_in, max_height_inches=2.5)
        else:
            cx, cy = image_emu_size(data)
        photos.append(
            ReportPhoto(
                data=data,
                caption=_photo_caption(img.get("vision_analysis"), str(img.get("_layout_caption") or "")),
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

    property_satellite = _load_property_map_photo(meta, "satellite", "Satellite view of property location.")
    property_roadmap = _load_property_map_photo(meta, "roadmap", "Property location within Florida.")
    property_appraiser = _load_property_appraiser_photo(meta)
    historical_aerials = _load_historical_aerial_photos(meta)
    historical_comment = (meta.get("historical_aerials_comment") or "").strip()

    specimens = [
        ReportSpecimen(
            id=str(item.get("id") or item.get("label") or ""),
            label=str(item.get("label") or "Specimen"),
            testing_type_id=str(item.get("testing_type_id") or ""),
            result=str(item.get("result") or ""),
            notes=str(item.get("notes") or ""),
        )
        for item in included_specimens(layout)
    ]

    include_letter = bool(layout.get("include_engineering_letter"))
    if type_id != "engineering":
        include_letter = False
    try:
        start_page = max(1, int(layout.get("starting_page_number") or 1))
    except (TypeError, ValueError):
        start_page = 1

    return ReportDocument(
        title=title,
        claim_id=claim_id,
        report_number=report_number,
        client_name=client,
        address_line1=line1,
        address_line2=line2,
        full_address=full_address,
        inspection_date=default_inspection_date(meta),
        prepared_by=default_prepared_by(meta),
        include_engineering_letter=include_letter,
        purpose_text=purpose_text(meta),
        observations_text=obs,
        weather_text=weather_text(meta) if layout.get("include_weather", True) else "",
        weather_continued_text=weather_continued_text(meta) if layout.get("include_weather", True) else "",
        weather_attribution_text=weather_attribution_text(meta) if layout.get("include_weather", True) else "",
        engineering_letter_paragraphs=engineering_letter_paragraphs(
            meta, line1 or full_address, conclusion
        ),
        sections=doc_sections,
        photos=photos,
        specimens=specimens,
        property_satellite=property_satellite,
        property_roadmap=property_roadmap,
        property_appraiser=property_appraiser,
        property_appraiser_attribution=_property_appraiser_attribution(meta) if property_appraiser else "",
        historical_aerials=historical_aerials,
        historical_aerials_comment=historical_comment if historical_aerials else "",
        include_page_numbers=bool(layout.get("include_page_numbers", True)),
        include_address_footer=bool(layout.get("include_address_footer", True)),
        include_weather=bool(layout.get("include_weather", True)),
        skip_cover=skip_cover,
        pages_tuned=pages_tuned,
        starting_page_number=start_page,
    )
