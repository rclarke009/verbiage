"""CI-safe tests for retrieval metric math and gold-label completeness.

Does not need Docker, an LLM, or VERBIAGE_EVAL=1.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

EVAL_DIR = Path(__file__).resolve().parent / "eval"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from retrieval_metrics import hit_at, mrr, recall_at, unique_doc_ids, unique_ids  # noqa: E402

GOLD_PATH = EVAL_DIR / "gold_questions.yaml"


class _Chunk:
    def __init__(self, doc_id: str) -> None:
        self.doc_id = doc_id


def test_unique_ids_preserves_first_occurrence():
    assert unique_ids(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_unique_doc_ids_from_chunks():
    chunks = [_Chunk("d1"), _Chunk("d2"), _Chunk("d1")]
    assert unique_doc_ids(chunks) == ["d1", "d2"]


def test_recall_at_full_and_cutoff():
    retrieved = ["a", "x", "b", "y"]
    relevant = ["a", "b"]
    assert recall_at(retrieved, relevant, k=None) == 1.0
    assert recall_at(retrieved, relevant, k=1) == 0.5
    assert recall_at(retrieved, relevant, k=3) == 1.0
    assert recall_at(["x", "y"], relevant, k=2) == 0.0


def test_recall_at_counts_unique_doc_ids():
    # Two chunks from the same gold doc still count as one retrieved doc.
    assert recall_at(["a", "a", "b"], ["a", "b"], k=1) == 0.5
    assert recall_at(["a", "a", "b"], ["a", "b"], k=2) == 1.0


def test_recall_at_undefined_without_gold():
    assert recall_at(["a"], [], k=1) is None
    assert hit_at(["a"], [], k=1) is None
    assert mrr(["a"], [], k=1) is None


def test_hit_at_and_mrr():
    retrieved = ["x", "gold", "y"]
    relevant = ["gold"]
    assert hit_at(retrieved, relevant, k=1) == 0.0
    assert hit_at(retrieved, relevant, k=2) == 1.0
    assert mrr(retrieved, relevant, k=1) == 0.0
    assert mrr(retrieved, relevant, k=2) == 0.5
    assert mrr(["gold"], relevant, k=1) == 1.0


def test_gold_questions_have_doc_labels():
    data = yaml.safe_load(GOLD_PATH.read_text())
    questions = data["questions"]
    assert questions, "gold set is empty"

    for q in questions:
        qid = q["id"]
        category = q["category"]
        labels = q.get("relevant_doc_ids") or []
        if category == "unanswerable":
            assert not labels, f"{qid}: unanswerable questions must not list relevant_doc_ids"
        else:
            assert labels, f"{qid}: answerable questions need relevant_doc_ids"
            assert len(labels) == len(set(labels)), f"{qid}: duplicate relevant_doc_ids"
