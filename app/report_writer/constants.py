"""Report Writer section keys, labels, and per-type templates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReportTypeId = Literal["engineering", "roof", "window_test"]

DEFAULT_REPORT_TYPE: ReportTypeId = "engineering"
REPORT_TYPE_KEY = "report_type"


_VOCABULARY_CONTRACT = (
    "Reuse terminology from field notes and prior sections verbatim where possible. "
    "Do not substitute synonyms for technical findings (e.g. if notes say 'brittle test failed,' "
    "do not rephrase as 'loss of structural integrity'). "
    "Do not recommend inspections of components not mentioned in field notes or prior sections. "
    "Do not open with generic phrases like 'In conclusion' unless mirrored in retrieved context."
)

_ROOF_TERMINOLOGY = (
    "Use roofing inspection vocabulary for shingles and roof coverings.",
    "After a failed brittle test, state shingles are brittle and not suitable for repair.",
    (
        "Do not use structural engineering terms (e.g. structural integrity, load-bearing, "
        "compromised structure) when referring to shingles or roof coverings."
    ),
    "Do not recommend inspections of soffit, fascia, or other components unless field notes or "
    "prior sections mention them.",
)

_ENGINEERING_TERMINOLOGY = (
    "Reserve structural engineering terms for framing, decking, and load-bearing elements.",
    (
        "When describing shingle or roof covering condition, use roofing terminology "
        "(brittle, creased, torn, lifted); do not describe shingles as losing structural integrity."
    ),
    "Do not recommend inspections of building components not mentioned in field notes or prior sections.",
)

_WINDOW_TEST_TERMINOLOGY = (
    "Use ASTM E1105 and fenestration testing vocabulary.",
    "Do not recommend additional testing or inspections not supported by field notes.",
)


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
    corpus_title_terms: tuple[str, ...] = ()
    terminology_rules: tuple[str, ...] = ()
    section_retrieval_extra: tuple[tuple[str, str], ...] = ()
    section_outline: tuple[tuple[str, str], ...] = ()


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
        corpus_title_terms=("engineering report", "engineering inspection", "storm damage report"),
        terminology_rules=_ENGINEERING_TERMINOLOGY,
        section_retrieval_extra=(
            ("property_overview", "property overview purpose date of loss"),
            ("summary_findings", "summary of findings storm damage"),
            ("roof_observations", "roof observations brittle test shingle damage"),
            ("interior_observations", "interior observations water intrusion drywall"),
            ("exterior_observations", "exterior observations siding structural"),
            (
                "recommendations_conclusion",
                "recommendations conclusion repair replacement Florida Building Code",
            ),
        ),
        section_outline=(
            (
                "recommendations_conclusion",
                "Structure example (adapt to this claim): Based on field observations at [address], "
                "storm-related damage consistent with [storm] was documented. "
                "[State repair/replacement recommendations per notes.] "
                "All repairs must comply with the Florida Building Code: Existing Building 2023.",
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
        corpus_title_terms=("roof report", "roof inspection"),
        terminology_rules=_ROOF_TERMINOLOGY,
        section_retrieval_extra=(
            ("summary", "roof report summary storm damage findings"),
            ("areas_of_concern", "areas of concern roof damage debris"),
            ("recommendations", "roof recommendations replacement brittle test repair"),
            (
                "conclusion",
                "roof report conclusion brittle test replacement not feasible wind damage",
            ),
        ),
        section_outline=(
            (
                "recommendations",
                "If brittle test failed, state shingles are brittle and not suitable for repair; "
                "recommend full roof replacement when repairs are not feasible.",
            ),
            (
                "conclusion",
                "Structure example (adapt to this claim): Based on the field inspection of the roof at "
                "[address], wind-related storm damage consistent with [storm] was observed, including "
                "[primary findings from notes]. [If brittle test failed: The brittle test failed, "
                "indicating the shingles are brittle and not suitable for repair.] Given the extent of "
                "damage documented, repairs to the existing roof are not feasible and full roof "
                "replacement is recommended.",
            ),
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
        corpus_title_terms=("window test", "ASTM E1105", "fenestration"),
        terminology_rules=_WINDOW_TEST_TERMINOLOGY,
        section_retrieval_extra=(
            ("overview", "window test report overview purpose scope"),
            ("weather_history", "weather history storm wind data"),
            ("test_summary", "ASTM E1105 test summary specimen pass fail"),
            (
                "recommendations_conclusion",
                "window test recommendations conclusion repair replacement",
            ),
        ),
        section_outline=(
            (
                "recommendations_conclusion",
                "State repair or replacement recommendations based on specimen pass/fail results; "
                "reference cyclical wind pressure only when supported by notes.",
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


def terminology_rules_for(type_id: str) -> tuple[str, ...]:
    return report_type_def(type_id).terminology_rules


def section_retrieval_extra_for(type_id: str, section_key: str) -> str:
    extra = dict(report_type_def(type_id).section_retrieval_extra)
    return extra.get(section_key, "")


def section_outline_for(type_id: str, section_key: str) -> str:
    outlines = dict(report_type_def(type_id).section_outline)
    return outlines.get(section_key, "")


def corpus_title_terms_for(type_id: str) -> tuple[str, ...]:
    return report_type_def(type_id).corpus_title_terms


def vocabulary_contract() -> str:
    return _VOCABULARY_CONTRACT


# Backward-compatible aliases (engineering template).
REPORT_SECTIONS: list[tuple[str, str]] = list(REPORT_TYPES["engineering"].sections)
SECTION_KEYS = section_keys_for_type("engineering")

DEFAULT_TOP_K = 8
