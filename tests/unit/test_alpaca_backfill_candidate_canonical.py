from datetime import date
from pathlib import Path

import pytest

from packages.data.alpaca_backfill_candidate_canonical import (
    ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION,
    CANONICAL_DAILY_COLUMNS,
    CANONICAL_DAILY_TYPES,
    CANDIDATE_ROLE,
    candidate_daily_relative_path,
    candidate_source_fingerprint,
    candidate_source_id,
    identity_symbols_from_rows,
    path_is_isolated,
)


def test_gate6_candidate_path_mirrors_production_daily_partition_shape() -> None:
    assert candidate_daily_relative_path(date(2020, 7, 6)).as_posix() == (
        "stocks/1d/year=2020/date=2020-07-06/part-000.parquet"
    )


def test_gate6_candidate_schema_matches_production_daily_columns_and_types() -> None:
    assert CANONICAL_DAILY_COLUMNS == (
        "symbol",
        "timestamp_utc",
        "session_date",
        "timeframe",
        "session_segment",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vwap",
        "transaction_count",
        "provider",
        "dataset",
        "source_id",
        "is_adjusted",
        "provider_timestamp_utc",
    )
    assert len(CANONICAL_DAILY_TYPES) == len(CANONICAL_DAILY_COLUMNS)
    assert CANONICAL_DAILY_TYPES[1] == "TIMESTAMP WITH TIME ZONE"
    assert CANONICAL_DAILY_TYPES[11] == "BIGINT"
    assert CANONICAL_DAILY_TYPES[15] == "BOOLEAN"


def test_gate6_source_fingerprint_is_deterministic_and_identity_sensitive() -> None:
    kwargs = {
        "validated_evidence_fingerprint": "cache",
        "identity_segments_sha256": "segments",
        "identity_chains_sha256": "chains",
        "identity_report_sha256": "report",
        "exchange": "XNYS",
    }
    first = candidate_source_fingerprint(**kwargs)
    second = candidate_source_fingerprint(**kwargs)
    changed = candidate_source_fingerprint(
        **{**kwargs, "identity_segments_sha256": "segments-changed"}
    )

    assert first == second
    assert len(first) == 64
    assert changed != first


def test_gate6_source_id_is_explicit_raw_validated_alpaca_provenance() -> None:
    fingerprint = "a" * 64
    assert candidate_source_id(fingerprint) == (
        "alpaca:sip:1Day:raw:asof=-:validated:" + fingerprint
    )


def test_gate6_candidate_namespace_must_be_disjoint_from_production_canonical(
    tmp_path: Path,
) -> None:
    canonical = tmp_path / "canonical"
    candidate = tmp_path / "derived" / "historical_backfill" / "candidate"
    assert path_is_isolated(candidate, canonical) is True
    assert path_is_isolated(canonical / "candidate", canonical) is False
    assert path_is_isolated(canonical, canonical / "nested") is False


def test_gate6_identity_lookup_preserves_exact_provider_symbol_case() -> None:
    rows = [
        {"symbol": "BCpC", "identity_chain_id": "chain-a", "segment_id": "seg-a"},
        {"symbol": "BCPC", "identity_chain_id": "chain-b", "segment_id": "seg-b"},
    ]
    result = identity_symbols_from_rows(rows)

    assert set(result) == {"BCpC", "BCPC"}
    assert result["BCpC"]["identity_chain_id"] == "chain-a"
    assert result["BCPC"]["identity_chain_id"] == "chain-b"


def test_gate6_identity_lookup_refuses_duplicate_exact_symbol() -> None:
    rows = [
        {"symbol": "ABC", "identity_chain_id": "chain-a", "segment_id": "seg-a"},
        {"symbol": "ABC", "identity_chain_id": "chain-b", "segment_id": "seg-b"},
    ]
    with pytest.raises(RuntimeError, match="duplicate exact identity symbol"):
        identity_symbols_from_rows(rows)


def test_gate6_contract_and_role_explicitly_forbid_production_promotion() -> None:
    assert ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION.startswith(
        "historical-backfill-candidate-canonical-v1"
    )
    assert CANDIDATE_ROLE == "ISOLATED_CANDIDATE_CANONICAL_NOT_PRODUCTION"
