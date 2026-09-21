from __future__ import annotations

from datetime import date
import gzip
import json
import threading
from pathlib import Path

import pytest

import packages.data.historical_option_reference_v2 as acquisition
from packages.core.settings import load_settings
from packages.data.historical_option_reference_v2_contract import (
    CORRECTION_SELECTION_POLICY,
    HISTORICAL_OPTION_REFERENCE_V2_CONTRACT_FINGERPRINT,
    ReferencePartition,
    acquisition_contract_manifest,
)


PARTITION = ReferencePartition(
    key="expired-2014-08",
    state="EXPIRED",
    expiration_gte=date(2014, 8, 1),
    expiration_lt=date(2014, 9, 1),
    expired=True,
)


def _record(
    *,
    correction=None,
    strike_price=20,
    shares_per_contract=100,
    additional_underlyings=None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "ticker": "O:AAL140816C00020000",
        "underlying_ticker": "AAL",
        "contract_type": "call",
        "expiration_date": "2014-08-16",
        "strike_price": strike_price,
        "exercise_style": "american",
        "shares_per_contract": shares_per_contract,
        "primary_exchange": "XBOX",
        "cfi": "OCASPS",
        "additional_underlyings": additional_underlyings or [],
    }
    if correction is not None:
        result["correction"] = correction
    return result


def test_v2_contract_is_frozen_and_preserves_v1_failure() -> None:
    manifest = acquisition_contract_manifest()

    assert (
        HISTORICAL_OPTION_REFERENCE_V2_CONTRACT_FINGERPRINT
        == "6d0af0b58a66b77c445d7e561d759dfd947e348e994045a1f7cfc16aeb9ccb41"
    )
    assert manifest["parent_v1_contract_fingerprint"] == (
        "95eb5048336e411cb31c912e2cf8569915aedd42fc9e9f0fd0917f3fb3fe3f23"
    )
    assert manifest["v1_observed_failure"] == {
        "partition": "expired-2014-08",
        "ticker": "O:AAL140816C00020000",
        "failure_class": "DUPLICATE_TICKER_VERSION_SEMANTICS",
    }
    duplicate_policy = manifest["normalization"]["duplicate_ticker_resolution"]
    assert duplicate_policy["policy"] == CORRECTION_SELECTION_POLICY
    assert duplicate_policy["missing_correction_rank"] == -1
    assert duplicate_policy["highest_numeric_correction_wins"] is True
    assert (
        duplicate_policy["same_highest_correction_conflicting_payload"]
        == "FAIL_CLOSED"
    )
    assert manifest["normalization"]["preserve_all_provider_rows_in_raw"] is True
    assert manifest["authority"]["strategy_outcome_access"] is False
    assert manifest["authority"]["paper_authority"] is False
    assert manifest["authority"]["live_authority"] is False


def test_highest_explicit_correction_wins_and_lineage_is_preserved() -> None:
    uncorrected = _record()
    corrected = _record(
        correction=1,
        shares_per_contract=50,
        additional_underlyings=[
            {"underlying": "AAL", "type": "equity", "amount": 50}
        ],
    )

    normalized, discarded = acquisition._resolve_ticker_versions(
        [uncorrected, corrected],
        partition=PARTITION,
    )

    assert normalized["selected_correction_rank"] == 1
    assert normalized["version_count"] == 2
    assert normalized["shares_per_contract"] == "50"
    assert normalized["observed_correction_ranks_json"] == "[-1,1]"
    assert discarded == 1
    assert len(
        __import__("json").loads(normalized["discarded_version_hashes_json"])
    ) == 1
    assert normalized["exact_duplicate_rows"] == 0
    assert normalized["correction_selection_policy"] == CORRECTION_SELECTION_POLICY


def test_explicit_zero_correction_ranks_above_missing_correction() -> None:
    normalized, discarded = acquisition._resolve_ticker_versions(
        [_record(), _record(correction=0)],
        partition=PARTITION,
    )

    assert normalized["selected_correction_rank"] == 0
    assert normalized["observed_correction_ranks_json"] == "[-1,0]"
    assert discarded == 1


def test_same_highest_correction_conflict_fails_closed() -> None:
    with pytest.raises(
        acquisition.HistoricalOptionReferenceV2Error,
        match="conflicting provider rows share highest correction rank 2",
    ):
        acquisition._resolve_ticker_versions(
            [
                _record(correction=2, shares_per_contract=100),
                _record(correction=2, shares_per_contract=50),
            ],
            partition=PARTITION,
        )


def test_exact_same_highest_correction_is_deduped_but_counted() -> None:
    item = _record(correction=3, shares_per_contract=50)

    normalized, discarded = acquisition._resolve_ticker_versions(
        [dict(item), dict(item)],
        partition=PARTITION,
    )

    assert normalized["selected_correction_rank"] == 3
    assert normalized["version_count"] == 2
    assert normalized["exact_duplicate_rows"] == 1
    assert discarded == 1


def test_correction_must_be_integral() -> None:
    with pytest.raises(
        acquisition.HistoricalOptionReferenceV2Error,
        match="correction value",
    ):
        acquisition._resolve_ticker_versions(
            [_record(correction="1.5")],
            partition=PARTITION,
        )


def test_documented_rare_other_contract_type_is_structurally_allowed() -> None:
    item = _record()
    item["contract_type"] = "other"

    normalized, discarded = acquisition._resolve_ticker_versions(
        [item],
        partition=PARTITION,
    )

    assert normalized["contract_type"] == "other"
    assert discarded == 0


def _settings(tmp_path: Path):
    base = load_settings(Path(__file__).resolve().parents[1])
    return base.model_copy(update={"project_root": tmp_path.resolve()})


def _write_verified_v1_artifacts(
    tmp_path: Path,
) -> tuple[object, dict[str, object]]:
    settings = _settings(tmp_path)
    paths = acquisition._v1_partition_paths(settings, PARTITION)
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    raw_item = _record()
    raw_bytes = gzip.compress(
        (acquisition._stable_json(raw_item) + "\n").encode("utf-8"),
        compresslevel=6,
        mtime=0,
    )
    paths["raw"].write_bytes(raw_bytes)
    paths["normalized"].write_bytes(b"verified-v1-normalized-placeholder")

    receipt: dict[str, object] = {
        "status": "COMPLETE",
        "contract": "atlas-historical-option-reference-v1",
        "contract_fingerprint": (
            "95eb5048336e411cb31c912e2cf8569915aedd42fc9e9f0fd0917f3fb3fe3f23"
        ),
        "provider": "massive",
        "partition": PARTITION.key,
        "reference_as_of_date": "2026-09-19",
        "reference_state": PARTITION.state,
        "expiration_gte": PARTITION.expiration_gte.isoformat(),
        "expiration_lt": PARTITION.expiration_lt.isoformat(),
        "expired_query_value": True,
        "page_limit": 1000,
        "page_count": 1,
        "request_id_count": 1,
        "raw_provider_records": 1,
        "normalized_unique_contracts": 1,
        "duplicate_ticker_rows": 0,
        "raw_path": acquisition._relative(settings, paths["raw"]),
        "normalized_path": acquisition._relative(settings, paths["normalized"]),
        "raw_bytes": paths["raw"].stat().st_size,
        "normalized_bytes": paths["normalized"].stat().st_size,
        "raw_sha256": acquisition._sha256_file(paths["raw"]),
        "normalized_sha256": acquisition._sha256_file(paths["normalized"]),
        "source_role": "REFERENCE_IDENTITY_STRUCTURE_ONLY",
    }
    receipt["receipt_fingerprint"] = acquisition._stable_hash(receipt)
    paths["receipt"].write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return settings, receipt


def test_verified_v1_receipt_can_be_reused_only_while_hashes_match(
    tmp_path: Path,
) -> None:
    settings, receipt = _write_verified_v1_artifacts(tmp_path)

    verified = acquisition._verified_v1_receipt(settings, PARTITION)

    assert verified is not None
    assert verified["receipt_fingerprint"] == receipt["receipt_fingerprint"]

    paths = acquisition._v1_partition_paths(settings, PARTITION)
    paths["normalized"].write_bytes(b"corrupted")

    assert acquisition._verified_v1_receipt(settings, PARTITION) is None


def test_verified_v1_raw_is_locally_renormalized_into_v2(
    tmp_path: Path,
) -> None:
    settings, receipt = _write_verified_v1_artifacts(tmp_path)

    imported = acquisition._import_verified_v1_partition(
        settings,
        PARTITION,
        v1_receipt=receipt,
        persistence_lock=threading.Lock(),
    )

    assert imported["status"] == "COMPLETE"
    assert imported["imported_from_verified_v1"] is True
    assert imported["v1_receipt_fingerprint"] == receipt["receipt_fingerprint"]
    assert imported["raw_provider_records"] == 1
    assert imported["normalized_unique_contracts"] == 1
    assert imported["duplicate_version_rows"] == 0
    assert imported["raw_version_reconciliation"] is True

    v1_paths = acquisition._v1_partition_paths(settings, PARTITION)
    v2_paths = acquisition._partition_paths(settings, PARTITION)
    assert imported["raw_path"] == acquisition._relative(settings, v1_paths["raw"])
    assert not v2_paths["raw"].exists()
    assert v2_paths["normalized"].is_file()
    assert v2_paths["receipt"].is_file()
    assert acquisition._verified_existing_receipt(settings, PARTITION) is not None


def test_receipt_artifact_path_rejects_project_escape(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV2Error,
        match="escapes project root",
    ):
        acquisition._receipt_artifact_path(
            settings,
            {"raw_path": "../outside.jsonl.gz"},
            "raw_path",
        )
