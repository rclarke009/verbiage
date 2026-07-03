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
    assert extract_street_line("412 Example Drive, Tampa, FL") == "412 Example Drive"


def test_extract_street_line_strips_unit():
    assert extract_street_line("123 Main St Apt 4B, Tampa") == "123 Main St"


def test_extract_folder_street_segment_before_dash():
    assert (
        extract_folder_street_segment("412 Example Dr - Sample Owner - Acme Insurance")
        == "412 Example Dr"
    )


def test_extract_folder_street_segment_no_dash():
    assert extract_folder_street_segment("412 Example Drive") == "412 Example Drive"


def test_normalize_street_address_suffix_expansion():
    assert normalize_street_address("412 Example St") == "412 example street"
    assert normalize_street_address("412 Example Dr.") == "412 example drive"
    assert normalize_street_address("123 N Main Ave") == "123 north main avenue"


def test_normalize_street_address_directional_expansion():
    assert normalize_street_address("123 N Main St") == "123 north main street"
    assert normalize_street_address("456 SW Oak Ln") == "456 southwest oak lane"


def test_extract_house_number():
    assert extract_house_number("412 Example Drive") == "412"
    assert extract_house_number("Example Drive") is None


def test_house_numbers_conflict():
    assert house_numbers_conflict("412 Example Dr", "413 Example Dr - Owner") is True
    assert house_numbers_conflict("412 Example Dr", "412 Example Dr - Owner") is False


def test_address_folder_similarity_owner_client_folder():
    score = address_folder_similarity(
        "412 Example Drive, Tampa, FL",
        "412 Example Dr - Sample Owner - Acme Insurance",
    )
    assert score >= 0.95


def test_address_folder_similarity_st_vs_street():
    score = address_folder_similarity(
        "412 Example St",
        "412 Example Street - Owner Name",
    )
    assert score >= 0.95


def test_address_folder_similarity_directional():
    score = address_folder_similarity(
        "123 N Main St",
        "123 North Main Street - Client",
    )
    assert score >= 0.95
