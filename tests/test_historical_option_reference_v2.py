from __future__ import annotations

from datetime import date

import pytest

import packages.data.historical_option_reference_v2 as acquisition
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
        match="non-integral correction value",
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
