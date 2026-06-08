"""Report Writer section keys and labels."""

REPORT_SECTIONS: list[tuple[str, str]] = [
    ("property_overview", "Property Overview"),
    ("roof_observations", "Roof Observations"),
    ("interior_observations", "Interior Observations"),
    ("conclusion", "Conclusion"),
]

SECTION_KEYS = [k for k, _ in REPORT_SECTIONS]

DEFAULT_TOP_K = 8
