from __future__ import annotations

from packages.data.alpaca_backfill_canonical_promotion import (
    ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION,
    PROMOTION_STATUS_COMPLETE,
)
from packages.data.alpaca_backfill_canonical_promotion_validation import (
    GATE8_REVALIDATION_CONTRACT_VERSION,
    gate8_revalidation_checks,
)


def _clean_report() -> dict[str, object]:
    return {
        "contract_version": ALPACA_BACKFILL_CANONICAL_PROMOTION_CONTRACT_VERSION,
        "status": PROMOTION_STATUS_COMPLETE,
        "revalidation_contract_version": GATE8_REVALIDATION_CONTRACT_VERSION,
        "stored_manifest_status": PROMOTION_STATUS_COMPLETE,
        "preflight_report_hash_exact": True,
        "candidate_parent_current": True,
        "gate7_parent_current": True,
        "promotion_source_fingerprint_current": True,
        "candidate_hashes_exact": True,
        "promoted_hashes_exact": True,
        "massive_baseline_unchanged": True,
        "row_accounting_exact": True,
        "session_accounting_exact": True,
        "promoted_symbol_accounting_exact": True,
        "production_schema_exact": True,
        "production_semantics_exact": True,
        "duplicate_keys": 0,
        "seam_not_overwritten": True,
        "gate7_policy_bound": True,
        "promotion_session_journal_accounting_exact": True,
    }


def test_gate8_revalidation_requires_live_disk_proof_contract() -> None:
    report = _clean_report()
    assert all(gate8_revalidation_checks(report).values())


def test_gate8_revalidation_fails_when_candidate_parent_drifts() -> None:
    report = _clean_report()
    report["candidate_parent_current"] = False
    checks = gate8_revalidation_checks(report)
    assert checks["candidate_parent_current"] is False
    assert not all(checks.values())


def test_gate8_revalidation_fails_when_preflight_baseline_proof_changes() -> None:
    report = _clean_report()
    report["preflight_report_hash_exact"] = False
    checks = gate8_revalidation_checks(report)
    assert checks["preflight_report_hash_exact"] is False
    assert not all(checks.values())
