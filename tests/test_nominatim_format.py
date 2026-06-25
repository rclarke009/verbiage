"""Unit tests for Nominatim address formatting (no live network)."""

from app.geocode.nominatim import format_nominatim_result


def _item(**address: str) -> dict:
    return {
        "place_id": 123456,
        "display_name": "unused",
        "address": address,
    }


def test_format_full_us_street_address():
    suggestion = format_nominatim_result(
        _item(
            house_number="412",
            road="Gulfview Drive",
            city="Tampa",
            state="Florida",
            postcode="33609",
            country="United States",
        )
    )
    assert suggestion is not None
    assert suggestion.id == "123456"
    assert suggestion.address == "412 Gulfview Drive, Tampa, FL"
    assert suggestion.label == "412 Gulfview Drive, Tampa, FL 33609"


def test_format_state_already_abbreviated():
    suggestion = format_nominatim_result(
        _item(
            house_number="100",
            road="Main Street",
            town="Springfield",
            state="IL",
        )
    )
    assert suggestion is not None
    assert suggestion.address == "100 Main Street, Springfield, IL"


def test_format_uses_town_when_no_city():
    suggestion = format_nominatim_result(
        _item(
            house_number="55",
            road="Oak Lane",
            town="Smallville",
            state="Kansas",
        )
    )
    assert suggestion is not None
    assert suggestion.address == "55 Oak Lane, Smallville, KS"


def test_format_skips_missing_street():
    assert format_nominatim_result(_item(city="Tampa", state="Florida")) is None


def test_format_skips_missing_city():
    assert format_nominatim_result(_item(house_number="1", road="Main St", state="Florida")) is None


def test_format_skips_missing_state():
    assert format_nominatim_result(_item(house_number="1", road="Main St", city="Tampa")) is None


def test_format_road_only_without_house_number():
    suggestion = format_nominatim_result(
        _item(
            road="Gulfview Drive",
            city="Tampa",
            state="Florida",
        )
    )
    assert suggestion is not None
    assert suggestion.address == "Gulfview Drive, Tampa, FL"
