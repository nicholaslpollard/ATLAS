from pathlib import Path

import duckdb

from packages.data.alpaca_backfill_seam import (
    ALPACA_BACKFILL_CANDIDATE_BOUNDARY_SESSION,
    ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION,
    ALPACA_BACKFILL_SEAM_TARGET_SESSION,
    _chunks,
    _relative_difference,
    classify_seam_response_symbol,
    seam_source_fingerprint,
)
from packages.data.alpaca_backfill_seam_runtime import (
    AlpacaBackfillSeamRuntimeProbe,
    canonical_daily_physical_schema_exact,
)
from packages.schemas.canonical_market import CANONICAL_STOCK_DAILY_SCHEMA


def _write_schema_only_parquet(path: Path, *, extra_column: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    expressions = [
        f"CAST(NULL AS {column.duckdb_type}) AS {column.name}"
        for column in CANONICAL_STOCK_DAILY_SCHEMA
    ]
    if extra_column:
        expressions.append("CAST(NULL AS VARCHAR) AS unexpected_physical_column")
    target = str(path).replace("\\", "/").replace("'", "''")
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            f"COPY (SELECT {', '.join(expressions)} WHERE FALSE) "
            f"TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    finally:
        con.close()


def test_gate7a_boundary_is_adjacent_friday_to_monday() -> None:
    assert ALPACA_BACKFILL_CANDIDATE_BOUNDARY_SESSION.isoformat() == "2021-08-13"
    assert ALPACA_BACKFILL_SEAM_TARGET_SESSION.isoformat() == "2021-08-16"
    assert (ALPACA_BACKFILL_SEAM_TARGET_SESSION - ALPACA_BACKFILL_CANDIDATE_BOUNDARY_SESSION).days == 3


def test_gate7a_exact_unique_response_symbol_is_safe() -> None:
    result = classify_seam_response_symbol("BCpC", ("ABC", "BCpC"), {"ABC", "BCpC"})
    assert result == (None, "BCpC", 1)


def test_gate7a_casefold_response_is_quarantined() -> None:
    classification, requested, count = classify_seam_response_symbol(
        "BCPC", ("ABC", "BCpC"), {"ABC", "BCpC"}
    )
    assert classification == "CASE_FOLD_RESPONSE"
    assert requested == "BCpC"
    assert count == 1


def test_gate7a_casefold_collision_is_quarantined_more_strictly() -> None:
    classification, requested, count = classify_seam_response_symbol(
        "BCPC", ("ABC", "BCpC"), {"ABC", "BCpC", "BCPC"}
    )
    assert classification == "CASE_FOLD_IDENTITY_COLLISION"
    assert requested == "BCpC"
    assert count == 1


def test_gate7a_same_batch_casefold_pair_is_ambiguous_even_for_exact_return() -> None:
    classification, requested, count = classify_seam_response_symbol(
        "BCPC", ("BCpC", "BCPC"), {"BCpC", "BCPC"}
    )
    assert classification == "AMBIGUOUS_CASE_FOLD_RESPONSE"
    assert requested is None
    assert count == 2


def test_gate7a_unrequested_response_symbol_is_quarantined() -> None:
    classification, requested, count = classify_seam_response_symbol(
        "XYZ", ("ABC", "DEF"), {"ABC", "DEF"}
    )
    assert classification == "UNREQUESTED_RESPONSE_SYMBOL"
    assert requested is None
    assert count == 0


def test_gate7a_source_fingerprint_is_deterministic_case_and_parent_sensitive() -> None:
    kwargs = {
        "candidate_fingerprint": "candidate",
        "candidate_boundary_sha256": "friday",
        "massive_boundary_sha256": "monday",
        "symbols": ["ABC", "BCpC"],
        "symbol_batch_size": 100,
        "feed": "sip",
        "adjustment": "raw",
        "asof": "-",
        "timeframe": "1Day",
    }
    first = seam_source_fingerprint(**kwargs)
    assert first == seam_source_fingerprint(**kwargs)
    assert len(first) == 64
    assert first != seam_source_fingerprint(**{**kwargs, "symbols": ["ABC", "BCPC"]})
    assert first != seam_source_fingerprint(**{**kwargs, "massive_boundary_sha256": "changed"})


def test_gate7a_chunks_are_stable_and_complete() -> None:
    assert list(_chunks(["A", "B", "C", "D", "E"], 2)) == [
        ("A", "B"),
        ("C", "D"),
        ("E",),
    ]


def test_gate7a_relative_difference_is_symmetric() -> None:
    assert _relative_difference(100.0, 101.0) == _relative_difference(101.0, 100.0)
    assert _relative_difference(5.0, 5.0) == 0.0


def test_gate7a_contract_is_explicitly_same_session_provider_probe() -> None:
    assert ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION.startswith(
        "historical-backfill-seam-v1"
    )
    assert "same-session-provider-probe" in ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION


def test_gate7a_physical_schema_ignores_hive_path_virtual_columns(tmp_path: Path) -> None:
    path = (
        tmp_path
        / "stocks"
        / "1d"
        / "year=2021"
        / "date=2021-08-13"
        / "part-000.parquet"
    )
    _write_schema_only_parquet(path)

    assert canonical_daily_physical_schema_exact(path) is True
    assert AlpacaBackfillSeamRuntimeProbe._schema_exact(path) is True


def test_gate7a_physical_schema_still_rejects_real_extra_columns(tmp_path: Path) -> None:
    path = (
        tmp_path
        / "stocks"
        / "1d"
        / "year=2021"
        / "date=2021-08-13"
        / "part-000.parquet"
    )
    _write_schema_only_parquet(path, extra_column=True)

    assert canonical_daily_physical_schema_exact(path) is False
    assert AlpacaBackfillSeamRuntimeProbe._schema_exact(path) is False
