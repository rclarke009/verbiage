"""Tests for generation run cancellation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.report_writer.queries import cancel_generation_run_if_running


def test_cancel_generation_run_if_running_updates_status():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = ("running",)

    with patch("app.report_writer.queries.finish_generation_run") as finish:
        with patch("app.report_writer.queries.set_claim_status_after_run") as set_status:
            cancelled = cancel_generation_run_if_running(
                conn,
                claim_id="claim-1",
                run_id="run-1",
                user_id="user-1",
            )

    assert cancelled is True
    finish.assert_called_once_with(conn, "run-1", status="cancelled")
    set_status.assert_called_once_with(conn, "claim-1", "draft")


def test_cancel_generation_run_skips_completed():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = ("completed",)

    with patch("app.report_writer.queries.finish_generation_run") as finish:
        cancelled = cancel_generation_run_if_running(
            conn,
            claim_id="claim-1",
            run_id="run-1",
            user_id="user-1",
        )

    assert cancelled is False
    finish.assert_not_called()
