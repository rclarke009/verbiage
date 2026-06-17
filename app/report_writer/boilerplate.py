"""Storm-damage report boilerplate text (adapted from WindowTest2 / reference PDFs)."""

from __future__ import annotations

from datetime import date


def _storm_label(meta: dict) -> str:
    name = (meta.get("storm_name") or "").strip()
    storm_type = (meta.get("storm_type") or "hurricane").strip().replace("_", " ")
    if name:
        if storm_type.lower() == "hurricane":
            return f"Hurricane {name}"
        return f"{storm_type.title()} {name}"
    return "the reported storm event"


def purpose_text(meta: dict) -> str:
    dol = (meta.get("storm_date") or meta.get("landfall_display") or "the date of loss").strip()
    override = (meta.get("boilerplate_purpose") or "").strip()
    if override:
        return override
    return (
        "True Reports was tasked by the insured to inspect the subject location in conjunction "
        f"with a property damage claim. The date of loss (DOL) for the claim was indicated to be {dol}. "
        "The goal of this exploration was to provide our professional opinion as to the cause, origin, "
        "extent, and repairability of the reported and observed damage at the property."
    )


def observations_text(meta: dict) -> str:
    override = (meta.get("boilerplate_observations") or "").strip()
    if override:
        return override
    return (
        "Our observations are presented herein. The property's condition is described in the "
        "photograph captions and elsewhere herein. Full-resolution images are retained "
        "electronically and can be provided upon request. Historical aerial and street "
        "photographs were also reviewed."
    )


def weather_text(meta: dict) -> str:
    override = (meta.get("boilerplate_weather") or "").strip()
    if override:
        return override
    storm = _storm_label(meta)
    storm_date = (meta.get("storm_date") or meta.get("landfall_display") or "").strip()
    category = (meta.get("storm_category") or "").strip()
    region = (meta.get("landfall_region") or "").strip()
    wind_speed = (meta.get("wind_speed_mph") or meta.get("weather_custom_wind_speed") or "").strip()
    wind_gust = (meta.get("wind_gust_mph") or meta.get("weather_custom_wind_gust") or "").strip()
    hail_size = (meta.get("hail_size_in") or meta.get("weather_custom_hail") or "").strip()
    stations = (meta.get("weather_stations") or "").strip()

    parts = [f"The home was directly in the path of {storm}."]
    if storm_date:
        parts.append(f"The event occurred on {storm_date}.")
    if category:
        parts.append(f"The storm was classified as {category}.")
    if region:
        parts.append(f"Landfall region: {region}.")

    if wind_speed or wind_gust:
        date_for_speeds = storm_date or (meta.get("weather_date_iso") or "").strip()
        speed_parts: list[str] = []
        if wind_speed and wind_gust:
            speed_parts.append(
                f"On {date_for_speeds}, sustained winds reached {wind_speed} mph "
                f"with gusts to {wind_gust} mph."
            )
        elif wind_speed:
            speed_parts.append(
                f"On {date_for_speeds}, sustained winds reached {wind_speed} mph."
            )
        elif wind_gust:
            speed_parts.append(f"On {date_for_speeds}, wind gusts reached {wind_gust} mph.")
        if stations:
            speed_parts.append(
                f"Data from weather stations {stations} near the property."
            )
        parts.append(" ".join(speed_parts))
    else:
        parts.append(
            "It is reasonable to assume that wind and gust speeds in the immediate area "
            "met or exceeded regional weather station readings for this event."
        )

    if hail_size:
        date_for_hail = storm_date or (meta.get("weather_date_iso") or "").strip()
        if date_for_hail:
            parts.append(
                f"On {date_for_hail}, hail up to {hail_size} inches was reported near the property."
            )
        else:
            parts.append(f"Hail up to {hail_size} inches was reported near the property.")

    return " ".join(parts)


def engineering_letter_paragraphs(meta: dict, address: str, conclusion: str = "") -> list[str]:
    addr = address.strip() or "the property"
    storm = _storm_label(meta)
    override1 = (meta.get("boilerplate_engineering_1") or "").strip()
    override2 = (meta.get("boilerplate_engineering_2") or "").strip()
    p1 = override1 or (
        "True Reports Inc. and the partnership with myself as an individual firm believe the effort "
        f"completed the condition residential inspection, as indicated herein this attached report. "
        "The inspection was completed in accordance with standard practices. The opinions presented in this "
        "report have been formulated within a reasonable degree of professional certainty. These opinions "
        "are based on a review of the available information, associated research, field observations, as "
        "well as our knowledge, training and experience. True Reports Inc. reserves the right to update "
        f"this report should additional information become available. The True Reports Inc.'s investigation "
        f"of the property at {addr}, was performed by the True Reports Inc. Field Inspection Team under "
        "my direct supervision."
    )
    if override2:
        p2 = override2
    elif conclusion.strip():
        p2 = conclusion.strip()
    else:
        p2 = (
            f"It is my professional opinion that the property sustained storm-related damage during {storm}. "
            "Repairs should address observed roof, interior, and exterior conditions as detailed in this report. "
            "All repairs must be in compliance with the Florida Building Code: Existing Building 2023."
        )
    p3 = (
        "True Reports Inc. appreciates the opportunity to assist with this inspection. "
        "Please call if you have any questions."
    )
    return [p1, p2, p3]


def default_inspection_date(meta: dict) -> str:
    raw = (meta.get("inspection_date") or "").strip()
    if raw:
        return raw
    return date.today().strftime("%b %d, %Y")


def default_client_name(meta: dict, title: str) -> str:
    return (meta.get("client_name") or title or "Unknown").strip() or "Unknown"


def default_prepared_by(meta: dict) -> str:
    return (meta.get("prepared_by") or "Stuart Jay Clarke, CGC and CCC").strip()


def include_engineering_letter(meta: dict) -> bool:
    val = meta.get("include_engineering_letter")
    if val is None:
        return True
    if isinstance(val, bool):
        return val
    return str(val).lower() not in ("0", "false", "no")
