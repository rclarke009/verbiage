"""Report Writer section keys, labels, and per-type templates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReportTypeId = Literal["engineering", "roof", "window_test"]

DEFAULT_REPORT_TYPE: ReportTypeId = "engineering"
REPORT_TYPE_KEY = "report_type"


@dataclass(frozen=True)
class ReportTypeDef:
    id: ReportTypeId
    label: str
    description: str
    sections: tuple[tuple[str, str], ...]
    retrieval_terms: tuple[str, ...]
    export_title: str
    prompt_preamble: str
    section_guidance: tuple[tuple[str, str], ...] = ()


REPORT_TYPES: dict[ReportTypeId, ReportTypeDef] = {
    "engineering": ReportTypeDef(
        id="engineering",
        label="Engineering Report",
        description=(
            "Full residential storm-damage assessment across roof, interior, exterior, "
            "and structural systems; may include PE-signed engineering letter language."
        ),
        sections=(
            ("property_overview", "Property Overview"),
            ("summary_findings", "Summary of Findings"),
            ("roof_observations", "Roof Observations"),
            ("interior_observations", "Interior Observations"),
            ("exterior_observations", "Exterior Observations"),
            ("recommendations_conclusion", "Recommendations & Conclusion"),
        ),
        retrieval_terms=(
            "engineering report",
            "summary of findings",
            "recommendations and conclusion",
            "storm damage inspection",
        ),
        export_title="Engineering Report",
        prompt_preamble=(
            "You are drafting a storm damage engineering report section. "
            "Write professional inspection language grounded in the field notes and retrieved "
            "similar reports below. Address cause, origin, extent, and repairability. "
            "Do not invent damage not supported by the notes or context."
        ),
        section_guidance=(
            ("property_overview", "Cover purpose, date of loss, and property context."),
            ("summary_findings", "Summarize key findings across building systems."),
            ("roof_observations", "Describe roof damage, testing, and repairability."),
            ("interior_observations", "Describe interior water intrusion and drywall damage."),
            ("exterior_observations", "Describe siding, structural, and exterior conditions."),
            (
                "recommendations_conclusion",
                "State repair recommendations and professional conclusions; mention FBC compliance where appropriate.",
            ),
        ),
    ),
    "roof": ReportTypeDef(
        id="roof",
        label="Roof Report",
        description=(
            "Residential roof inspection focused on shingle/deck condition, brittle test, "
            "wind-borne debris impacts, and soffit/fascia damage."
        ),
        sections=(
            ("summary", "Summary"),
            ("areas_of_concern", "Areas of Concern"),
            ("recommendations", "Recommendations"),
            ("conclusion", "Conclusion"),
        ),
        retrieval_terms=(
            "roof report",
            "roof inspection",
            "brittle test",
            "areas of concern",
            "wind-borne debris",
        ),
        export_title="Roof Report",
        prompt_preamble=(
            "You are drafting a residential roof inspection report section. "
            "Write professional roofing inspection language grounded in the field notes and retrieved "
            "similar roof reports below. Focus on shingle condition, debris impacts, brittle test, "
            "and soffit/fascia. Do not invent damage not supported by the notes or context."
        ),
        section_guidance=(
            ("summary", "Summarize roof type, storm context, and primary findings."),
            (
                "areas_of_concern",
                "List specific areas of concern as concise bullet-style items where appropriate.",
            ),
            ("recommendations", "State repair or replacement recommendations for the roof system."),
            ("conclusion", "Conclude whether wind storm damage is evident and if repairs are feasible."),
        ),
    ),
    "window_test": ReportTypeDef(
        id="window_test",
        label="Window Test Report",
        description=(
            "ASTM E1105 field water-penetration testing on installed fenestration after storm events."
        ),
        sections=(
            ("overview", "Overview"),
            ("weather_history", "Weather History"),
            ("test_summary", "Summary of Findings"),
            ("recommendations_conclusion", "Recommendations & Conclusion"),
        ),
        retrieval_terms=(
            "window test report",
            "ASTM E1105",
            "specimen",
            "water penetration",
            "fenestration",
        ),
        export_title="Window Test Report",
        prompt_preamble=(
            "You are drafting a window test report section. "
            "Write professional fenestration testing language grounded in the field notes and retrieved "
            "similar window test reports below. Reference ASTM E1105 methodology and specimen pass/fail "
            "results where supported. Do not invent test results not supported by the notes or context."
        ),
        section_guidance=(
            ("overview", "Cover report number context, purpose, DOL, and inspection scope."),
            ("weather_history", "Describe storm history and wind data relevant to window failure."),
            (
                "test_summary",
                "Summarize specimens tested, pass/fail counts, and ASTM E1105 methodology.",
            ),
            (
                "recommendations_conclusion",
                "State repair/replacement recommendations and cyclical wind pressure context where relevant.",
            ),
        ),
    ),
}


def is_valid_report_type(value: str | None) -> value is ReportTypeId:
    return value in REPORT_TYPES


def get_report_type(property_metadata: dict | None) -> ReportTypeId:
    meta = property_metadata or {}
    raw = (meta.get(REPORT_TYPE_KEY) or meta.get("report_template") or "").strip()
    if raw in REPORT_TYPES:
        return raw  # type: ignore[return-value]
    return DEFAULT_REPORT_TYPE


def require_report_type(property_metadata: dict | None) -> ReportTypeId:
    meta = property_metadata or {}
    raw = (meta.get(REPORT_TYPE_KEY) or meta.get("report_template") or "").strip()
    if raw not in REPORT_TYPES:
        raise ValueError("report_type is required and must be engineering, roof, or window_test")
    return raw  # type: ignore[return-value]


def report_type_def(type_id: str) -> ReportTypeDef:
    if type_id not in REPORT_TYPES:
        return REPORT_TYPES[DEFAULT_REPORT_TYPE]
    return REPORT_TYPES[type_id]  # type: ignore[index]


def sections_for_type(type_id: str) -> list[tuple[str, str]]:
    return list(report_type_def(type_id).sections)


def section_keys_for_type(type_id: str) -> list[str]:
    return [k for k, _ in sections_for_type(type_id)]


def section_labels_for_type(type_id: str) -> dict[str, str]:
    return dict(sections_for_type(type_id))


def section_guidance_for(type_id: str, section_key: str) -> str:
    guidance = dict(report_type_def(type_id).section_guidance)
    return guidance.get(section_key, "")


# Backward-compatible aliases (engineering template).
REPORT_SECTIONS: list[tuple[str, str]] = list(REPORT_TYPES["engineering"].sections)
SECTION_KEYS = section_keys_for_type("engineering")

DEFAULT_TOP_K = 8
