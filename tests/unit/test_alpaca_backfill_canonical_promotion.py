from __future__ import annotations

from pathlib import Path

import pytest

from packages.data.alpaca_backfill_canonical_promotion import (
    ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION,
    COPY_NEW,
    FAIL_COLLISION,
    PROMOTION_STATUS_COMPLETE,
    REUSE_EXACT,
    gate8_acceptance_checks,
    inventory_fingerprint,
    promotion_action,
    promotion_source_fingerprint,
    session_date_from_daily_path,
)


def test_gate8_contract_is_explicit_journaled_session_atomic() -> None:
    assert ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION.startswith(
        "historical-backfill-canonical-promotion-v1"
    )
    assert "journaled-session-atomic" in ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION


def test_gate8_daily_path_parser_preserves_exact_session() -> None:
    path = Path("stocks/1d/year=2021/date=2021-08-13/part-000.parquet")
    assert session_date_from_daily_path(path).isoformat() == "2021-08-13"


def test_gate8_daily_path_parser_rejects_non_partition_path() -> None:
    with pytest.raises(ValueError, match="lacks date= partition"):
        session_date_from_daily_path(Path("stocks/1d/2021-08-13/part-000.parquet"))


def test_gate8_absent_target_is_copy_new() -> None:
    assert promotion_action(
        target_exists=False,
        target_sha256=None,
        candidate_sha256="candidate",
    ) == COPY_NEW


def test_gate8_exact_existing_target_is_resumable_reuse() -> None:
    assert promotion_action(
        target_exists=True,
        target_sha256="same",
        candidate_sha256="same",
    ) == REUSE_EXACT


def test_gate8_nonmatching_existing_target_fails_closed() -> None:
    assert promotion_action(
        target_exists=True,
        target_sha256="production-other",
        candidate_sha256="candidate",
    ) == FAIL_COLLISION


def test_gate8_inventory_fingerprint_is_order_independent() -> None:
    rows = [
        {"session_date": "2016-01-05", "relative_path": "b", "sha256": "2"},
        {"session_date": "2016-01-04", "relative_path": "a", "sha256": "1"},
    ]
    assert inventory_fingerprint(rows) == inventory_fingerprint(list(reversed(rows)))


def test_gate8_source_fingerprint_binds_gate7_policy() -> None:
    base = promotion_source_fingerprint(
        candidate_fingerprint="candidate",
        gate7_fingerprint="gate7-a",
        gate7_decision_sha256="decision",
        candidate_inventory_fingerprint="candidate-files",
        massive_baseline_fingerprint="massive-files",
    )
    changed = promotion_source_fingerprint(
        candidate_fingerprint="candidate",
        gate7_fingerprint="gate7-b",
        gate7_decision_sha256="decision",
        candidate_inventory_fingerprint="candidate-files",
        massive_baseline_fingerprint="massive-files",
    )
    assert base != changed


def test_gate8_acceptance_checks_require_every_safety_invariant() -> None:
    report = {
        "contract_version": ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION,
        "status": PROMOTION_STATUS_COMPLETE,
        "candidate_hashes_exact": True,
        "promoted_hashes_exact": True,
        "massive_baseline_unchanged": True,
        "row_accounting_exact": True,
        "session_accounting_exact": True,
        "production_schema_exact": True,
        "production_semantics_exact": True,
        "duplicate_keys": 0,
        "seam_not_overwritten": True,
        "gate7_policy_bound": True,
    }
    assert all(gate8_acceptance_checks(report).values())


def test_gate8_acceptance_checks_fail_when_massive_baseline_changes() -> None:
    report = {
        "contract_version": ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION,
        "status": PROMOTION_STATUS_COMPLETE,
        "candidate_hashes_exact": True,
        "promoted_hashes_exact": True,
        "massive_baseline_unchanged": False,
        "row_accounting_exact": True,
        "session_accounting_exact": True,
        "production_schema_exact": True,
        "production_semantics_exact": True,
        "duplicate_keys": 0,
        "seam_not_overwritten": True,
        "gate7_policy_bound": True,
    }
    checks = gate8_acceptance_checks(report)
    assert checks["massive_baseline_unchanged"] is False
    assert not all(checks.values())
