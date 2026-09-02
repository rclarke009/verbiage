"""Import a WindowTest Full Job Package ZIP into a Verbiage claim."""

from __future__ import annotations

import io
import json
import mimetypes
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.report_writer.document_layout import LAYOUT_KEY, empty_layout, set_layout
from app.report_writer.queries import create_claim, create_section_revision, insert_claim_image
from app.report_writer.storage import storage_path_for, write_claim_image

MANIFEST_NAMES = ("full-job-package.json", "privatefull-job-package.json")


class JobPackageError(ValueError):
    pass


@dataclass
class ParsedPhoto:
    image_file: str
    notes: str
    include: bool
    photo_type: str
    data: bytes = b""


@dataclass
class ParsedSpecimen:
    source_id: str
    label: str
    testing_type_id: str
    result: str
    notes: str
    inaccessible: bool
    photos: list[ParsedPhoto] = field(default_factory=list)


@dataclass
class ParsedJobPackage:
    job: dict[str, Any]
    specimens: list[ParsedSpecimen]
    files: dict[str, bytes]


def _zip_namemap(zf: zipfile.ZipFile) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in zf.namelist():
        if name.endswith("/"):
            continue
        mapping[name] = name
        mapping[Path(name).name] = name
        mapping[name.lstrip("./")] = name
    return mapping


def _read_json_member(zf: zipfile.ZipFile, namemap: dict[str, str]) -> dict[str, Any]:
    for candidate in MANIFEST_NAMES:
        real = namemap.get(candidate)
        if real:
            return json.loads(zf.read(real).decode("utf-8"))
    for name in zf.namelist():
        if name.lower().endswith("full-job-package.json"):
            return json.loads(zf.read(name).decode("utf-8"))
    raise JobPackageError("ZIP is missing full-job-package.json")


def _bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes"}


def _read_bytes(zf: zipfile.ZipFile, namemap: dict[str, str], rel: str | None) -> bytes:
    if not rel:
        return b""
    key = rel.strip().lstrip("./")
    real = namemap.get(key) or namemap.get(Path(key).name)
    if not real:
        return b""
    return zf.read(real)


def _photos_from_list(raw_photos: list[Any], zf: zipfile.ZipFile, namemap: dict[str, str]) -> list[ParsedPhoto]:
    out: list[ParsedPhoto] = []
    for item in raw_photos or []:
        if not isinstance(item, dict):
            continue
        rel = str(item.get("imageFile") or item.get("image_file") or "")
        out.append(
            ParsedPhoto(
                image_file=rel,
                notes=str(item.get("notes") or "").strip(),
                include=_bool(item.get("includeInReport", item.get("include_in_report")), True),
                photo_type=str(item.get("photoType") or item.get("photo_type") or ""),
                data=_read_bytes(zf, namemap, rel),
            )
        )
    return out


def parse_full_job_package(zip_bytes: bytes) -> ParsedJobPackage:
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise JobPackageError("File is not a ZIP archive") from exc
    with zf:
        namemap = _zip_namemap(zf)
        payload = _read_json_member(zf, namemap)
        job = payload.get("job") if isinstance(payload.get("job"), dict) else payload
        if not isinstance(job, dict):
            raise JobPackageError("Job package JSON is missing a job object")

        specimens: list[ParsedSpecimen] = []
        for window in job.get("windows") or []:
            if not isinstance(window, dict):
                continue
            result = str(window.get("testResult") or window.get("test_result") or "").strip() or "N/A"
            if _bool(window.get("isInaccessible"), False):
                result = "Inaccessible"
            specimens.append(
                ParsedSpecimen(
                    source_id=str(window.get("windowId") or window.get("window_id") or window.get("windowNumber") or ""),
                    label=str(window.get("windowNumber") or window.get("window_number") or "Specimen"),
                    testing_type_id="windows",
                    result=result,
                    notes=str(window.get("notes") or window.get("untestedReason") or "").strip(),
                    inaccessible=_bool(window.get("isInaccessible"), False),
                    photos=_photos_from_list(window.get("photos") or [], zf, namemap),
                )
            )
        for section in job.get("specimenSections") or job.get("specimen_sections") or []:
            if not isinstance(section, dict):
                continue
            photos = section.get("sectionPhotos") or section.get("section_photos") or section.get("photos") or []
            specimens.append(
                ParsedSpecimen(
                    source_id=str(section.get("sectionId") or section.get("section_id") or ""),
                    label=str(section.get("sectionName") or section.get("section_name") or "Section"),
                    testing_type_id=str(section.get("testingTypeId") or section.get("testing_type_id") or "other"),
                    result=str(section.get("result") or "N/A"),
                    notes=str(section.get("notes") or "").strip(),
                    inaccessible=False,
                    photos=_photos_from_list(photos, zf, namemap),
                )
            )

        files: dict[str, bytes] = {}
        for key, field in (
            ("overhead", "overheadImageFile"),
            ("front", "frontOfHomeImageFile"),
            ("calibration1", "equipmentCalibrationImage1File"),
            ("calibration2", "equipmentCalibrationImage2File"),
        ):
            data = _read_bytes(zf, namemap, job.get(field) or job.get(field[0].lower() + field[1:]))
            if data:
                files[key] = data

        return ParsedJobPackage(job=job, specimens=specimens, files=files)


def _address_meta(job: dict[str, Any]) -> dict[str, str]:
    return {
        "report_type": "window_test",
        "address": str(job.get("addressLine1") or job.get("address_line1") or "").strip(),
        "city": str(job.get("city") or "").strip(),
        "state": str(job.get("state") or "").strip(),
        "zip": str(job.get("zip") or "").strip(),
        "client_name": str(job.get("clientName") or job.get("client_name") or "").strip(),
        "prepared_by": str(job.get("inspectorName") or job.get("inspector_name") or "").strip(),
        "inspection_date": str(job.get("inspectionDate") or job.get("inspection_date") or "").strip(),
        "include_engineering_letter": "true" if _bool(job.get("includeEngineeringLetter"), False) else "false",
        "boilerplate_purpose": str(job.get("customPurposeText") or "").strip(),
        "boilerplate_observations": str(job.get("customObservationsText") or "").strip(),
        "boilerplate_weather": str(job.get("customWeatherText") or "").strip(),
        "source_job_id": str(job.get("jobId") or job.get("job_id") or "").strip(),
    }


def _field_notes(job: dict[str, Any], specimens: list[ParsedSpecimen]) -> str:
    parts: list[str] = []
    notes = str(job.get("notes") or "").strip()
    if notes:
        parts.append(notes)
    concern = str(job.get("areasOfConcern") or job.get("areas_of_concern") or "").strip()
    if concern:
        parts.append(f"Areas of concern: {concern}")
    lines = []
    for spec in specimens:
        lines.append(f"{spec.label}: {spec.result}" + (f" — {spec.notes}" if spec.notes else ""))
    if lines:
        parts.append("Specimens:\n" + "\n".join(lines))
    return "\n\n".join(parts)


def _section_seed(job: dict[str, Any], specimens: list[ParsedSpecimen]) -> dict[str, str]:
    passed = sum(1 for s in specimens if s.result.lower() == "pass")
    failed = sum(1 for s in specimens if s.result.lower() == "fail")
    summary_lines = [f"{s.label}: {s.result}" for s in specimens]
    overview = str(job.get("customPurposeText") or "").strip() or (
        f"Window water-penetration testing at {job.get('addressLine1') or 'the subject property'}."
    )
    weather = str(job.get("customWeatherText") or "").strip()
    if not weather:
        bits = []
        if job.get("namedStormName") or job.get("named_storm_name"):
            bits.append(str(job.get("namedStormName") or job.get("named_storm_name")))
        if job.get("weatherCondition"):
            bits.append(str(job["weatherCondition"]))
        weather = " ".join(bits)
    test_summary = str(job.get("customObservationsText") or "").strip() or (
        f"{len(specimens)} specimen(s) tested; {passed} passed, {failed} failed.\n" + "\n".join(summary_lines)
    )
    recs = str(job.get("customRecommendationsText") or job.get("conclusionComment") or "").strip()
    return {
        "overview": overview,
        "weather_history": weather,
        "test_summary": test_summary,
        "recommendations_conclusion": recs,
    }


def import_full_job_package(conn, *, user_id: str, zip_bytes: bytes, filename: str = "") -> dict[str, Any]:
    parsed = parse_full_job_package(zip_bytes)
    job = parsed.job
    meta = _address_meta(job)
    layout = empty_layout("window_test")
    layout["include_page_numbers"] = _bool(job.get("includePageNumbersInReport"), True)
    layout["include_address_footer"] = _bool(job.get("includeAddressInReport"), True)
    layout["include_engineering_letter"] = _bool(job.get("includeEngineeringLetter"), False)
    layout["include_weather"] = _bool(job.get("includeWeatherInReport"), True)
    try:
        layout["starting_page_number"] = max(1, int(job.get("reportStartingPageNumber") or 1))
    except (TypeError, ValueError):
        layout["starting_page_number"] = 1

    client = meta["client_name"] or "Window test"
    address = meta["address"]
    title = f"{client} — {address}".strip(" —") if address else client
    notes = _field_notes(job, parsed.specimens)
    meta = set_layout(meta, layout)

    claim = create_claim(
        conn,
        user_id=user_id,
        title=title[:500],
        property_metadata=meta,
        field_notes=notes,
    )
    claim_id = claim["claim_id"]
    for key, content in _section_seed(job, parsed.specimens).items():
        if content.strip():
            create_section_revision(
                conn,
                claim_id=claim_id,
                section_key=key,
                content=content,
                origin="job_package_import",
                generation_run_id=None,
            )

    photos_layout: list[dict[str, Any]] = []
    specimens_layout: list[dict[str, Any]] = []
    sort_order = 0

    def _store_photo(photo: ParsedPhoto, specimen_id: str | None) -> str | None:
        nonlocal sort_order
        if not photo.data:
            return None
        name = Path(photo.image_file).name or "photo.jpg"
        ctype = mimetypes.guess_type(name)[0] or "image/jpeg"
        row = insert_claim_image(
            conn,
            claim_id=claim_id,
            user_id=user_id,
            storage_path="",
            filename=name,
            content_type=ctype,
            size_bytes=len(photo.data),
            sort_order=sort_order,
            vision_analysis={"caption": photo.notes, "observations": photo.notes},
            analysis_status="succeeded",
        )
        image_id = str(row["image_id"])
        path = storage_path_for(user_id, claim_id, image_id, name)
        write_claim_image(path, photo.data)
        _set_image_storage_path(conn, image_id, path)
        photos_layout.append(
            {
                "image_id": image_id,
                "include": photo.include,
                "caption": photo.notes,
                "sort_order": sort_order,
                "specimen_id": specimen_id,
                "photo_type": photo.photo_type,
            }
        )
        sort_order += 1
        return image_id

    extra_index = 0
    for key, data in parsed.files.items():
        extra_index += 1
        _store_photo(
            ParsedPhoto(image_file=f"{key}.jpg", notes=key.replace("1", " 1").replace("2", " 2"), include=True, photo_type=key, data=data),
            None,
        )

    for spec in parsed.specimens:
        photo_ids: list[str] = []
        specimen_id = spec.source_id or spec.label
        for photo in spec.photos:
            image_id = _store_photo(photo, specimen_id)
            if image_id:
                photo_ids.append(image_id)
        specimens_layout.append(
            {
                "id": specimen_id,
                "label": spec.label,
                "testing_type_id": spec.testing_type_id,
                "result": spec.result,
                "notes": spec.notes,
                "include": True,
                "photo_ids": photo_ids,
                "inaccessible": spec.inaccessible,
            }
        )

    layout["photos"] = photos_layout
    layout["specimens"] = specimens_layout
    meta = set_layout(meta, layout)
    from app.report_writer.queries import update_claim

    updated = update_claim(conn, claim_id, user_id, property_metadata=meta)
    claim = updated or claim
    claim["_import_filename"] = filename
    claim["_specimen_count"] = len(specimens_layout)
    claim["_photo_count"] = len(photos_layout)
    return claim


def _set_image_storage_path(conn, image_id: str, storage_path: str) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE report_claim_images SET storage_path = %s WHERE image_id = %s::uuid",
            (storage_path, image_id),
        )
        conn.commit()
    finally:
        cur.close()
