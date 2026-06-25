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
    assert suggestion.address == "412 Gulfview Drive"
    assert suggestion.address2 == ""
    assert suggestion.city == "Tampa"
    assert suggestion.state == "FL"
    assert suggestion.zip == "33609"
    assert suggestion.label == "412 Gulfview Drive, Tampa, FL 33609"


def test_format_includes_unit_as_address2():
    suggestion = format_nominatim_result(
        _item(
            house_number="412",
            road="Gulfview Drive",
            unit="Apt 2",
            city="Tampa",
            state="Florida",
            postcode="33609",
        )
    )
    assert suggestion is not None
    assert suggestion.address == "412 Gulfview Drive"
    assert suggestion.address2 == "Apt 2"


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
    assert suggestion.address == "100 Main Street"
    assert suggestion.city == "Springfield"
    assert suggestion.state == "IL"


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
    assert suggestion.address == "55 Oak Lane"
    assert suggestion.city == "Smallville"
    assert suggestion.state == "KS"


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
    assert suggestion.address == "Gulfview Drive"
    assert suggestion.city == "Tampa"
    assert suggestion.state == "FL"


def test_format_usps_city_override_wekiwa_springs():
    suggestion = format_nominatim_result(
        _item(
            house_number="111",
            road="Cedar Oak Trail",
            town="Wekiwa Springs",
            state="Florida",
            postcode="32750",
        )
    )
    assert suggestion is not None
    assert suggestion.address == "111 Cedar Oak Trail"
    assert suggestion.city == "Longwood"
    assert suggestion.state == "FL"
    assert suggestion.zip == "32750"
    assert suggestion.label == "111 Cedar Oak Trail, Longwood, FL 32750"
