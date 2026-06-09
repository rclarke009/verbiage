"""Unit tests for street-address normalization and folder similarity."""

from app.address_match import (
    address_folder_similarity,
    extract_folder_street_segment,
    extract_house_number,
    extract_street_line,
    house_numbers_conflict,
    normalize_street_address,
)


def test_extract_street_line_first_segment():
    assert extract_street_line("412 Gulfview Drive, Tampa, FL") == "412 Gulfview Drive"


def test_extract_street_line_strips_unit():
    assert extract_street_line("123 Main St Apt 4B, Tampa") == "123 Main St"


def test_extract_folder_street_segment_before_dash():
    assert (
        extract_folder_street_segment("412 Gulfview Dr - John Smith - Acme Insurance")
        == "412 Gulfview Dr"
    )


def test_extract_folder_street_segment_no_dash():
    assert extract_folder_street_segment("412 Gulfview Drive") == "412 Gulfview Drive"


def test_normalize_street_address_suffix_expansion():
    assert normalize_street_address("412 Gulfview St") == "412 gulfview street"
    assert normalize_street_address("412 Gulfview Dr.") == "412 gulfview drive"
    assert normalize_street_address("123 N Main Ave") == "123 north main avenue"


def test_normalize_street_address_directional_expansion():
    assert normalize_street_address("123 N Main St") == "123 north main street"
    assert normalize_street_address("456 SW Oak Ln") == "456 southwest oak lane"


def test_extract_house_number():
    assert extract_house_number("412 Gulfview Drive") == "412"
    assert extract_house_number("Gulfview Drive") is None


def test_house_numbers_conflict():
    assert house_numbers_conflict("412 Gulfview Dr", "413 Gulfview Dr - Owner") is True
    assert house_numbers_conflict("412 Gulfview Dr", "412 Gulfview Dr - Owner") is False


def test_address_folder_similarity_owner_client_folder():
    score = address_folder_similarity(
        "412 Gulfview Drive, Tampa, FL",
        "412 Gulfview Dr - John Smith - Acme Insurance",
    )
    assert score >= 0.95


def test_address_folder_similarity_st_vs_street():
    score = address_folder_similarity(
        "412 Gulfview St",
        "412 Gulfview Street - Owner Name",
    )
    assert score >= 0.95


def test_address_folder_similarity_directional():
    score = address_folder_similarity(
        "123 N Main St",
        "123 North Main Street - Client",
    )
    assert score >= 0.95
