from __future__ import annotations

import gzip
import json
import threading
from datetime import date
from pathlib import Path

import pytest

import packages.data.historical_option_reference_v6 as acquisition
from packages.core.settings import load_settings
from packages.data.historical_option_reference_v6_contract import (
    ACIW_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    AMBIGUITY_QUARANTINE_POLICY,
    HISTORICAL_OPTION_REFERENCE_V6_CONTRACT_FINGERPRINT,
    ReferencePartition,
    acquisition_contract_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

AUGUST_PARTITION = ReferencePartition(
    key="expired-2014-08",
    state="EXPIRED",
    expiration_gte=date(2014, 8, 1),
    expiration_lt=date(2014, 9, 1),
    expired=True,
)


def _settings(tmp_path: Path):
    base = load_settings(PROJECT_ROOT)
    return base.model_copy(update={"project_root": tmp_path.resolve()})


def _aciw_row(*, exchange: str, underlying: str = "ACIW") -> dict[str, object]:
    return {
        "ticker": "O:ACIW140816C00040000",
        "underlying_ticker": underlying,
        "contract_type": "call",
        "expiration_date": "2014-08-16",
        "strike_price": 40,
        "exercise_style": "american",
        "shares_per_contract": 100,
        "primary_exchange": exchange,
        "cfi": "OCASPS",
        "additional_underlyings": [],
    }


def _install_zero_historical_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def zero_gap(
        _settings,
        *,
        api_key: str,
        ticker: str,
        contract_type: str,
        expiration: date,
        strike_price: str,
        as_of: date,
    ):
        assert api_key == "token"
        assert ticker == "O:ACIW140816C00040000"
        assert contract_type == "call"
        assert expiration == date(2014, 8, 16)
        assert strike_price == "40"
        assert as_of == date(2014, 8, 15)
        calls.append({"ticker": ticker, "as_of": as_of.isoformat()})
        raise acquisition.HistoricalOptionReferenceV6HistoricalTargetCardinalityError(
            ticker=ticker,
            as_of=as_of,
            target_count=0,
            request_ids=[f"gap-{len(calls)}"],
        )

    monkeypatch.setattr(acquisition, "_historical_target_row_once", zero_gap)
    return calls


def test_v6_contract_freezes_no_guess_quarantine() -> None:
    manifest = acquisition_contract_manifest()

    # Temporary capture assertion is replaced with the exact frozen fingerprint
    # after the first CI import/test pass.
    assert HISTORICAL_OPTION_REFERENCE_V6_CONTRACT_FINGERPRINT == "__CAPTURE_V6_FINGERPRINT__"

    assert manifest["parent_v5_contract_fingerprint"] == (
        "4a9775c90414d8a454654d5f0928d79b68dec785b16b493e197ea34471aef1ea"
    )
    assert manifest["v5_observed_failure"]["partition"] == "expired-2014-08"
    assert manifest["v5_observed_failure"]["ticker"] == "O:ACIW140816C00040000"

    accepted = manifest["accepted_diagnostics"]["aciw_unresolved_primary_exchange_gap"]
    assert accepted["evidence_fingerprint"] == ACIW_DIAGNOSTIC_EVIDENCE_FINGERPRINT
    assert accepted["current_primary_exchanges"] == ["GMNI", "XCBO"]
    assert accepted["failed_preexpiration_target_rows"] == 0
    assert accepted["historical_exact_match_found"] is False

    quarantine = manifest["normalization"]["ambiguity_quarantine"]
    assert quarantine["policy"] == AMBIGUITY_QUARANTINE_POLICY
    assert quarantine["eligible_reference_state"] == "EXPIRED"
    assert quarantine["eligible_highest_correction_rank"] == -1
    assert quarantine["allowed_differing_fields"] == ["primary_exchange"]
    assert quarantine["current_underlying_ticker_must_be_identical"] is True
    assert quarantine["historical_target_row_count_required"] == 0
    assert quarantine["historical_zero_target_repeat_count"] == 2
    assert quarantine["preserve_all_raw_conflicting_rows"] is True
    assert quarantine["exclude_quarantined_ticker_from_normalized_reference"] is True
    assert quarantine["no_selected_provider_row"] is True
    assert quarantine["otherwise"] == "FAIL_CLOSED"

    assert manifest["reuse"]["verified_v6_receipts"] is True
    assert manifest["reuse"]["verified_v5_raw_lineage"] is True
    assert len(manifest["partitions"]) == 212
    assert manifest["authority"]["strategy_outcome_access"] is False
    assert manifest["authority"]["paper_authority"] is False
    assert manifest["authority"]["live_authority"] is False


def test_v6_aciw_gap_quarantines_without_selecting_a_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    calls = _install_zero_historical_gap(monkeypatch)
    rows = [
        _aciw_row(exchange="GMNI"),
        _aciw_row(exchange="XCBO"),
    ]

    with pytest.raises(acquisition.HistoricalOptionReferenceV6Quarantine) as exc_info:
        acquisition._resolve_ticker_versions(
            rows,
            partition=AUGUST_PARTITION,
            settings=settings,
            api_key="token",
        )

    assert len(calls) == 2
    record = exc_info.value.record
    assert record["ticker"] == "O:ACIW140816C00040000"
    assert record["reason"] == "NO_PROVIDER_NATIVE_PREEXPIRATION_IDENTITY"
    assert record["policy"] == AMBIGUITY_QUARANTINE_POLICY
    assert record["current_raw_row_count"] == 2
    assert record["current_underlying_tickers"] == ["ACIW"]
    assert record["current_primary_exchanges"] == ["GMNI", "XCBO"]
    assert record["current_correction_ranks"] == [-1]
    assert record["differing_fields"] == ["primary_exchange"]
    assert record["historical_as_of"] == "2014-08-15"
    assert record["historical_target_row_count"] == 0
    assert record["historical_zero_target_repeat_count"] == 2
    assert record["selected_provider_row"] is None
    assert record["excluded_from_normalized_reference"] is True
    assert record["diagnostic_evidence_fingerprints"] == [
        ACIW_DIAGNOSTIC_EVIDENCE_FINGERPRINT
    ]
    assert sorted(row["primary_exchange"] for row in record["raw_rows"]) == [
        "GMNI",
        "XCBO",
    ]
    assert len(str(record["quarantine_record_fingerprint"])) == 64


def test_v6_does_not_quarantine_unresolved_underlying_identity_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    _install_zero_historical_gap(monkeypatch)

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV6HistoricalTargetCardinalityError
    ):
        acquisition._resolve_ticker_versions(
            [
                _aciw_row(exchange="GMNI", underlying="ACIW"),
                _aciw_row(exchange="GMNI", underlying="ACI"),
            ],
            partition=AUGUST_PARTITION,
            settings=settings,
            api_key="token",
        )


def test_v6_does_not_quarantine_nonzero_historical_cardinality(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)

    def two_rows(
        _settings,
        *,
        ticker: str,
        as_of: date,
        **_kwargs,
    ):
        raise acquisition.HistoricalOptionReferenceV6HistoricalTargetCardinalityError(
            ticker=ticker,
            as_of=as_of,
            target_count=2,
            request_ids=["two"],
        )

    monkeypatch.setattr(acquisition, "_historical_target_row_once", two_rows)

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV6HistoricalTargetCardinalityError
    ) as exc_info:
        acquisition._resolve_ticker_versions(
            [
                _aciw_row(exchange="GMNI"),
                _aciw_row(exchange="XCBO"),
            ],
            partition=AUGUST_PARTITION,
            settings=settings,
            api_key="token",
        )

    assert exc_info.value.target_count == 2


def test_v6_partition_paths_include_separate_quarantine_artifact(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    paths = acquisition._partition_paths(settings, AUGUST_PARTITION)

    assert paths["raw"].name == "contracts.jsonl.gz"
    assert paths["normalized"].name == "contracts.parquet"
    assert paths["quarantine"].name == "quarantine.jsonl"
    assert paths["receipt"].name == "receipt.json"
    assert "historical_option_reference_v6" in str(paths["quarantine"])


def test_v6_parent_raw_rebuild_persists_quarantine_and_reconciles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    _install_zero_historical_gap(monkeypatch)
    monkeypatch.setattr(
        acquisition,
        "assert_category_acquisition_allowed",
        lambda *_args, **_kwargs: None,
    )

    raw_path = tmp_path / "parent" / "contracts.jsonl.gz"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        _aciw_row(exchange="GMNI"),
        _aciw_row(exchange="XCBO"),
    ]
    with gzip.open(raw_path, "wt", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(acquisition._stable_json(row) + "\n")

    parent_receipt = {
        "raw_provider_records": 2,
        "page_count": 1,
        "request_id_count": 1,
        "raw_origin_contract_fingerprint": "parent-origin",
        "receipt_fingerprint": "parent-receipt",
        "raw_sha256": acquisition._sha256_file(raw_path),
    }

    receipt = acquisition._rebuild_partition_from_parent_raw(
        settings,
        AUGUST_PARTITION,
        parent_receipt=parent_receipt,
        raw_path=raw_path,
        parent_contract_fingerprint="parent-contract",
        api_key="token",
        persistence_lock=threading.Lock(),
    )

    assert receipt["status"] == "COMPLETE"
    assert receipt["raw_provider_records"] == 2
    assert receipt["normalized_unique_contracts"] == 0
    assert receipt["duplicate_version_rows"] == 0
    assert receipt["quarantined_tickers"] == 1
    assert receipt["quarantined_raw_rows"] == 2
    assert receipt["raw_version_reconciliation"] is True
    assert receipt["ambiguity_quarantine_policy"] == AMBIGUITY_QUARANTINE_POLICY
    assert len(str(receipt["quarantine_sha256"])) == 64

    quarantine_path = settings.resolved_path(str(receipt["quarantine_path"]))
    assert quarantine_path.is_file()
    lines = [
        json.loads(line)
        for line in quarantine_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert lines[0]["ticker"] == "O:ACIW140816C00040000"
    assert lines[0]["selected_provider_row"] is None
    assert sorted(row["primary_exchange"] for row in lines[0]["raw_rows"]) == [
        "GMNI",
        "XCBO",
    ]

    normalized_path = settings.resolved_path(str(receipt["normalized_path"]))
    con = acquisition.duckdb.connect(database=":memory:")
    try:
        count = int(
            con.execute(
                f"SELECT count(*) FROM read_parquet('{str(normalized_path).replace(chr(39), chr(39)*2)}')"
            ).fetchone()[0]
        )
    finally:
        con.close()
    assert count == 0


def test_v6_known_quarantine_spec_is_exactly_aciw() -> None:
    manifest = acquisition_contract_manifest()
    probes = manifest["known_quarantine_preacquisition_probes"]

    assert len(probes) == 1
    assert probes[0]["id"] == "ACIW_UNRESOLVED_PRIMARY_EXCHANGE"
    assert probes[0]["ticker"] == "O:ACIW140816C00040000"
    assert probes[0]["expected_differing_fields"] == ["primary_exchange"]
    assert probes[0]["expected_underlying_tickers"] == ["ACIW"]
    assert probes[0]["expected_primary_exchanges"] == ["GMNI", "XCBO"]
    assert probes[0]["expected_highest_correction_rank"] == -1
    assert probes[0]["expected_historical_target_rows"] == 0
    assert probes[0]["diagnostic_evidence_fingerprint"] == (
        ACIW_DIAGNOSTIC_EVIDENCE_FINGERPRINT
    )
