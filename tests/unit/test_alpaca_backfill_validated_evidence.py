from copy import deepcopy

from packages.data.alpaca_backfill_quality import ZERO_ACTIVITY_PLACEHOLDER_CLASS
from packages.data.alpaca_backfill_session_quality import TRADE_BACKED
from packages.data.alpaca_backfill_validated_evidence import (
    ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION,
    build_fingerprint_payload,
    evidence_row_from_record,
    stable_source_fingerprint,
)


def _quality() -> dict[str, object]:
    return {
        "contract_version": "historical-backfill-quality-v2-zero-activity-placeholder-evidence",
        "identity_safe_bar_rows": 2,
        "trade_backed_usable_rows": 1,
        "zero_activity_placeholder_rows": 1,
        "quarantined_response_bar_rows": 0,
        "observed_symbols": 1,
        "definite_invalid_rows": 0,
        "zero_activity_candidate_policy": "PRESERVE_RAW_EXCLUDE_FROM_TRADE_BACKED_CANDIDATE",
        "generated_at_utc": "ignored",
    }


def _session() -> dict[str, object]:
    return {
        "contract_version": "historical-backfill-quality-session-coverage-v1-trade-lifespan-xnys",
        "unique_session_keys": 2,
        "duplicate_session_rows": 0,
        "non_exchange_session_rows": 0,
        "missing_sessions_within_lifespans": 0,
        "raw_row_accounting_exact": True,
        "parent_classification_accounting_exact": True,
        "unique_session_accounting_exact": True,
        "generated_at_utc": "ignored",
    }


def test_evidence_fingerprint_is_order_stable() -> None:
    pages = [
        {"year": 2020, "batch_index": 2, "page_index": 0, "sha256": "B"},
        {"year": 2020, "batch_index": 1, "page_index": 0, "sha256": "A"},
    ]
    first = build_fingerprint_payload(
        page_entries=pages,
        anomaly_sha256="ANOM",
        quality=_quality(),
        session=_session(),
    )
    second = build_fingerprint_payload(
        page_entries=list(reversed(pages)),
        anomaly_sha256="ANOM",
        quality=_quality(),
        session=_session(),
    )
    assert stable_source_fingerprint(first) == stable_source_fingerprint(second)
    assert first["contract_version"] == ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION


def test_evidence_fingerprint_changes_when_raw_page_sha_changes() -> None:
    pages = [{"year": 2020, "batch_index": 1, "page_index": 0, "sha256": "A"}]
    first = build_fingerprint_payload(
        page_entries=pages,
        anomaly_sha256="ANOM",
        quality=_quality(),
        session=_session(),
    )
    changed = deepcopy(pages)
    changed[0]["sha256"] = "B"
    second = build_fingerprint_payload(
        page_entries=changed,
        anomaly_sha256="ANOM",
        quality=_quality(),
        session=_session(),
    )
    assert stable_source_fingerprint(first) != stable_source_fingerprint(second)


def test_evidence_fingerprint_ignores_parent_generation_timestamp() -> None:
    quality_a = _quality()
    quality_b = _quality()
    quality_b["generated_at_utc"] = "different"
    first = build_fingerprint_payload(
        page_entries=[], anomaly_sha256="A", quality=quality_a, session=_session()
    )
    second = build_fingerprint_payload(
        page_entries=[], anomaly_sha256="A", quality=quality_b, session=_session()
    )
    assert stable_source_fingerprint(first) == stable_source_fingerprint(second)


def test_trade_backed_cache_row_preserves_exact_ticker_literal() -> None:
    row = evidence_row_from_record(
        record={
            "t": "2020-01-06T05:00:00Z",
            "o": 10.0,
            "h": 11.0,
            "l": 9.5,
            "c": 10.5,
            "v": 100,
            "n": 5,
            "vw": 10.25,
        },
        symbol="NAN",
        year=2020,
        batch_index=7,
        page_index=1,
        page_sha256="abc",
        record_index=3,
    )
    assert row["provider_symbol"] == "NAN"
    assert row["bar_class"] == TRADE_BACKED
    assert row["session_date"] == "2020-01-06"
    assert row["source_batch_index"] == 7
    assert row["source_page_sha256"] == "abc"


def test_zero_activity_cache_row_remains_explicit_placeholder() -> None:
    row = evidence_row_from_record(
        record={
            "t": "2020-01-06T05:00:00Z",
            "o": 10.0,
            "h": 10.0,
            "l": 10.0,
            "c": 10.0,
            "v": 0,
            "n": 0,
            "vw": 0,
        },
        symbol="ABC",
        year=2020,
        batch_index=0,
        page_index=0,
        page_sha256="abc",
        record_index=0,
    )
    assert row["bar_class"] == ZERO_ACTIVITY_PLACEHOLDER_CLASS
    assert row["volume"] == 0.0
    assert row["trade_count"] == 0.0
    assert row["vwap"] == 0.0
