"""Unit tests for address compose/split helpers."""

from app.geocode.address_format import (
    compose_full_address,
    has_structured_address,
    report_address_lines,
    split_legacy_address,
)


def test_compose_structured_address():
    meta = {
        "address": "412 Gulfview Drive",
        "address2": "Apt 2",
        "city": "Tampa",
        "state": "FL",
        "zip": "33609",
    }
    assert compose_full_address(meta) == "412 Gulfview Drive, Apt 2, Tampa, FL 33609"


def test_compose_without_address2():
    meta = {
        "address": "412 Gulfview Drive",
        "city": "Tampa",
        "state": "FL",
        "zip": "33609",
    }
    assert compose_full_address(meta) == "412 Gulfview Drive, Tampa, FL 33609"


def test_split_legacy_three_part_address():
    parsed = split_legacy_address("412 Gulfview Drive, Tampa, FL 33609")
    assert parsed == {
        "address": "412 Gulfview Drive",
        "address2": "",
        "city": "Tampa",
        "state": "FL",
        "zip": "33609",
    }


def test_split_legacy_two_part_address():
    parsed = split_legacy_address("412 Gulfview Drive, Tampa, FL")
    assert parsed["address"] == "412 Gulfview Drive"
    assert parsed["city"] == "Tampa"
    assert parsed["state"] == "FL"


def test_has_structured_address_detects_city():
    assert has_structured_address({"address": "412 Gulfview Drive", "city": "Tampa"}) is True
    assert has_structured_address({"address": "412 Gulfview Drive, Tampa, FL"}) is False


def test_report_address_lines_structured():
    line1, line2, full = report_address_lines(
        {
            "address": "412 Gulfview Drive",
            "address2": "Suite 100",
            "city": "Tampa",
            "state": "FL",
            "zip": "33609",
        }
    )
    assert line1 == "412 Gulfview Drive, Suite 100"
    assert line2 == "Tampa, FL 33609"
    assert full == "412 Gulfview Drive, Suite 100, Tampa, FL 33609"


def test_report_address_lines_legacy_fallback():
    line1, line2, full = report_address_lines({"address": "412 Gulfview Drive, Tampa, FL"})
    assert line1 == "412 Gulfview Drive"
    assert line2 == "Tampa, FL"
    assert full == "412 Gulfview Drive, Tampa, FL"
