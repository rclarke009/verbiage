"""Tests for demo corpus auto-seed helpers."""

from unittest.mock import MagicMock, patch

from app.demo_seed import clear_eval_fixture, demo_corpus_needs_seed


def test_demo_corpus_needs_seed_when_empty():
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = (0,)
    conn.cursor.return_value = cur
    with patch("app.demo_seed.corpus_docs", return_value=[("a", "t", "x")] * 12):
        with patch("app.demo_seed.DEMO_RESEED_CORPUS", False):
            assert demo_corpus_needs_seed(conn) is True


def test_demo_corpus_needs_seed_when_stale():
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = (8,)
    conn.cursor.return_value = cur
    with patch("app.demo_seed.corpus_docs", return_value=[("a", "t", "x")] * 12):
        with patch("app.demo_seed.DEMO_RESEED_CORPUS", False):
            assert demo_corpus_needs_seed(conn) is True


def test_demo_corpus_needs_seed_when_current():
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = (12,)
    conn.cursor.return_value = cur
    with patch("app.demo_seed.corpus_docs", return_value=[("a", "t", "x")] * 12):
        with patch("app.demo_seed.DEMO_RESEED_CORPUS", False):
            assert demo_corpus_needs_seed(conn) is False


def test_clear_eval_fixture_deletes_rows():
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = [("doc-1",), ("doc-2",)]
    conn.cursor.return_value = cur
    removed = clear_eval_fixture(conn)
    assert removed == 2
    assert cur.execute.call_count >= 7
    conn.commit.assert_called_once()
