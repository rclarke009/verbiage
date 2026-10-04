"""Claim splitting for the faithfulness gate. Runs in normal pytest (no Docker)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_JUDGES = Path(__file__).resolve().parent / "eval" / "judges.py"
_spec = importlib.util.spec_from_file_location("eval_judges", _JUDGES)
assert _spec is not None and _spec.loader is not None
_judges = importlib.util.module_from_spec(_spec)
sys.modules["eval_judges"] = _judges
_spec.loader.exec_module(_judges)
split_claims = _judges.split_claims


def test_straight_quotes_ignore_markdown_title():
    answer = (
        '**Engineering Report - 100 Maple Court** (`100_maple`)\n'
        '- "The north slope shingles were creased and displaced."\n'
        '- "Granules were collected in the gutter below the eave."'
    )
    assert split_claims(answer) == [
        "The north slope shingles were creased and displaced.",
        "Granules were collected in the gutter below the eave.",
    ]


def test_curly_quotes_match_straight_quotes():
    straight = (
        "**Engineering Report - 800 Sand Example Road, Duneville, FL 30060**\n"
        '- "The exterior stucco finish on the west elevation exhibited hairline '
        'cracking and spalling at the window corners."\n'
        '- Conclusion also notes "stucco cracking at the window corners" '
        "as part of the wind-driven-rain findings."
    )
    curly = (
        "**Engineering Report - 800 Sand Example Road, Duneville, FL 30060**\n"
        "- \u201cThe exterior stucco finish on the west elevation exhibited hairline "
        "cracking and spalling at the window corners.\u201d\n"
        "- Conclusion also notes \u201cstucco cracking at the window corners\u201d "
        "as part of the wind-driven-rain findings."
    )
    assert split_claims(curly) == split_claims(straight)
    assert split_claims(curly) == [
        "The exterior stucco finish on the west elevation exhibited hairline "
        "cracking and spalling at the window corners.",
        "stucco cracking at the window corners",
    ]


def test_curly_quote_after_period_does_not_glue_title_to_claim():
    answer = (
        "**Engineering Report - 150 Ocean Example Terrace, Surfside, FL 30055** "
        "(`150_ocean_example_terrace_surfside`)\n\n"
        "- The property has \u201caluminum soffit and fascia at the eaves.\u201d\n"
        "- \u201cSoffit and fascia along the north eave were detached and bent outward.\u201d"
    )
    claims = split_claims(answer)
    assert "Engineering Report" not in " ".join(claims)
    assert claims == [
        "aluminum soffit and fascia at the eaves.",
        "Soffit and fascia along the north eave were detached and bent outward.",
    ]


def test_unquoted_answer_splits_on_sentences_and_newlines():
    answer = (
        "The north slope shingles were creased.\n"
        "Granules were collected in the gutter below the eave."
    )
    assert split_claims(answer) == [
        "The north slope shingles were creased.",
        "Granules were collected in the gutter below the eave.",
    ]
