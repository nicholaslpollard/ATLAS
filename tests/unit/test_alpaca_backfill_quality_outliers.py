import pytest

from packages.data.alpaca_backfill_quality import (
    ALPACA_BACKFILL_QUALITY_BASELINE_CONTRACT_VERSION,
)
from packages.data.alpaca_backfill_quality_outliers import (
    ALPACA_BACKFILL_QUALITY_OUTLIER_CONTRACT_VERSION,
    RAW_OUTLIER_POLICY,
    absolute_return_bucket,
    gate5_acceptance_checks,
    simple_return,
)
from packages.data.alpaca_backfill_session_quality import (
    ALPACA_BACKFILL_SESSION_QUALITY_CONTRACT_VERSION,
)


def _quality() -> dict[str, object]:
    return {
        "contract_version": ALPACA_BACKFILL_QUALITY_BASELINE_CONTRACT_VERSION,
        "canonical_data_modified": False,
        "definite_invalid_rows": 0,
        "row_accounting_exact": True,
        "quarantine_accounting_exact": True,
        "symbol_summary_reconciliation_exact": True,
        "trade_backed_accounting_exact": True,
    }


def _session() -> dict[str, object]:
    return {
        "contract_version": ALPACA_BACKFILL_SESSION_QUALITY_CONTRACT_VERSION,
        "canonical_data_modified": False,
        "duplicate_session_rows": 0,
        "non_exchange_session_rows": 0,
        "missing_sessions_within_lifespans": 0,
        "market_sessions_with_zero_raw_coverage": 0,
        "raw_row_accounting_exact": True,
        "parent_classification_accounting_exact": True,
        "unique_session_accounting_exact": True,
    }


def _cache() -> dict[str, object]:
    return {"pass": True, "source_fingerprint": "CACHE"}


def _outlier() -> dict[str, object]:
    return {
        "contract_version": ALPACA_BACKFILL_QUALITY_OUTLIER_CONTRACT_VERSION,
        "canonical_data_modified": False,
        "source_fingerprint": "CACHE",
        "transition_accounting_exact": True,
        "nonpositive_return_input_rows": 0,
        "raw_outlier_policy": RAW_OUTLIER_POLICY,
    }


def test_gate5c_simple_return() -> None:
    assert simple_return(100.0, 150.0) == pytest.approx(0.5)
    assert simple_return(100.0, 50.0) == pytest.approx(-0.5)


def test_gate5c_simple_return_rejects_nonpositive_inputs() -> None:
    with pytest.raises(ValueError):
        simple_return(0.0, 1.0)
    with pytest.raises(ValueError):
        simple_return(1.0, 0.0)


def test_gate5c_absolute_return_buckets_are_boundary_exact() -> None:
    assert absolute_return_bucket(0.2499) == "LT_25_PCT"
    assert absolute_return_bucket(-0.25) == "GE_25_PCT"
    assert absolute_return_bucket(0.50) == "GE_50_PCT"
    assert absolute_return_bucket(-1.00) == "GE_100_PCT"
    assert absolute_return_bucket(2.50) == "GE_250_PCT"
    assert absolute_return_bucket(-5.00) == "GE_500_PCT"


def test_gate5_final_acceptance_checks_clean_reports() -> None:
    checks = gate5_acceptance_checks(_quality(), _session(), _cache(), _outlier())
    assert checks
    assert all(checks.values())


def test_gate5_final_acceptance_checks_fail_on_drift() -> None:
    session = _session()
    session["missing_sessions_within_lifespans"] = 1
    checks = gate5_acceptance_checks(_quality(), session, _cache(), _outlier())
    assert checks["session_absent_lifespan_zero"] is False

    outlier = _outlier()
    outlier["source_fingerprint"] = "OTHER"
    checks = gate5_acceptance_checks(_quality(), _session(), _cache(), outlier)
    assert checks["outlier_source_fingerprint_matches_cache"] is False
