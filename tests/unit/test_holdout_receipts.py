from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.data.holdout_receipts import (
    begin_holdout_consumption,
    read_holdout_receipt,
    write_holdout_receipt,
)


class HoldoutReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="atlas-holdout-test-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "master_holdout_consumption.json"
        self.binding = {
            "authorization_id": "a" * 64,
            "walk_forward_end": date(2026, 9, 3),
            "walk_forward_manifest": self.path.with_name("walk_forward_daily.json"),
        }

    def begin(self):
        return begin_holdout_consumption(self.path, **self.binding)

    def replay_started(self):
        value = self.begin()
        value.update(status="CONSUMED_REPLAY_STARTED", protected_return_rows_read=123,
                     protected_rows_accounting_pending=False)
        return write_holdout_receipt(self.path, value)

    def test_failed_retry_preserves_history_and_known_count(self):
        value = self.replay_started()
        first_clock = value["first_consumption_started_at_utc"]
        value.update(status="CONSUMED_REPLAY_FAILED", replay_exit_code=7,
                     replay_error="synthetic interruption")
        failed = write_holdout_receipt(self.path, value)
        retry = self.begin()
        self.assertEqual(retry["attempt_number"], 2)
        self.assertEqual(retry["protected_return_rows_read"], 123)
        self.assertTrue(retry["protected_rows_accounting_pending"])
        self.assertEqual(retry["first_consumption_started_at_utc"], first_clock)
        archived = self.path.with_name("master_holdout_consumption_history") / f"{failed['receipt_sha256']}.json"
        self.assertEqual(json.loads(archived.read_text()), failed)
        self.assertEqual(read_holdout_receipt(self.path), retry)

    def test_materialization_interruption_remains_consumed_on_retry(self):
        first = self.begin()
        retry = self.begin()
        self.assertEqual(retry["attempt_number"], 2)
        self.assertEqual(retry["receipt_history"], [first["receipt_sha256"]])
        self.assertIsNone(retry["protected_return_rows_read"])
        self.assertEqual(read_holdout_receipt(self.path), retry)

    def test_completed_run_is_reused_without_overwriting_receipt(self):
        value = self.replay_started()
        value.update(status="CONSUMED_WALK_FORWARD_COMPLETE", replay_exit_code=0)
        complete = write_holdout_receipt(self.path, value)
        content = self.path.read_bytes()
        self.assertEqual(self.begin(), complete)
        self.assertEqual(self.path.read_bytes(), content)

    def test_prior_snapshot_tampering_blocks_read_and_retry(self):
        value = self.replay_started()
        snapshot = self.path.with_name("master_holdout_consumption_history") / f"{value['receipt_history'][0]}.json"
        snapshot.write_text("{}")
        with self.assertRaises(ValueError):
            read_holdout_receipt(self.path)
        with self.assertRaises(ValueError):
            self.begin()

    def test_missing_current_receipt_cannot_erase_preserved_consumption(self):
        self.replay_started()
        self.path.unlink()
        with self.assertRaisesRegex(ValueError, "permanent history exists"):
            self.begin()

    def test_known_count_cannot_be_cleared_or_changed(self):
        original = self.replay_started()
        for count in (None, 0, 122, 124):
            with self.subTest(count=count):
                changed = {**original, "status": "CONSUMED_REPLAY_FAILED",
                           "protected_return_rows_read": count}
                with self.assertRaisesRegex(ValueError, "known protected-row"):
                    write_holdout_receipt(self.path, changed)
        self.assertEqual(read_holdout_receipt(self.path), original)

    def test_different_authorization_cannot_resume(self):
        original = self.begin()
        with self.assertRaisesRegex(ValueError, "different source"):
            begin_holdout_consumption(self.path, **{**self.binding, "authorization_id": "b" * 64})
        self.assertEqual(read_holdout_receipt(self.path), original)

    def test_crash_before_projection_keeps_old_receipt_and_snapshot(self):
        from unittest.mock import patch
        from packages.data import holdout_receipts

        original = self.begin()
        changed = {**original, "status": "CONSUMED_MATERIALIZATION_FAILED"}
        writer = holdout_receipts.atomic_write_text

        def interrupted(path, text, **kwargs):
            if path == self.path:
                raise OSError("synthetic interrupted projection")
            return writer(path, text, **kwargs)

        with patch.object(holdout_receipts, "atomic_write_text", interrupted):
            with self.assertRaises(OSError):
                write_holdout_receipt(self.path, changed)
        self.assertEqual(read_holdout_receipt(self.path), original)
        self.assertEqual(self.begin()["attempt_number"], 2)

    def test_stale_writer_cannot_overwrite_new_state(self):
        original = self.begin()
        self.begin()
        with self.assertRaisesRegex(ValueError, "changed since"):
            write_holdout_receipt(self.path, {**original, "status": "CONSUMED_MATERIALIZATION_FAILED"})

    def test_success_after_failure_retains_both_attempts(self):
        value = self.replay_started()
        value["status"] = "CONSUMED_REPLAY_FAILED"
        write_holdout_receipt(self.path, value)
        retry = self.begin()
        retry.update(status="CONSUMED_REPLAY_STARTED", protected_rows_accounting_pending=False)
        retry = write_holdout_receipt(self.path, retry)
        retry.update(status="CONSUMED_WALK_FORWARD_COMPLETE", replay_exit_code=0)
        complete = write_holdout_receipt(self.path, retry)
        self.assertEqual(len(complete["receipt_history"]), 5)
        self.assertEqual(read_holdout_receipt(self.path), complete)


if __name__ == "__main__":
    unittest.main()
