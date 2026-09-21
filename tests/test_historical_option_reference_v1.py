from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

import packages.data.historical_option_reference_v1 as acquisition
from packages.core.settings import load_settings
from packages.data.historical_option_reference_v1_contract import (
    ACTIVE_HARD_END_EXCLUSIVE,
    HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT,
    HISTORY_START,
    REFERENCE_AS_OF_DATE,
    ReferencePartition,
    acquisition_contract_manifest,
    reference_partitions,
)


def _settings(tmp_path: Path):
    base = load_settings(Path(__file__).resolve().parents[1])
    return base.model_copy(update={"project_root": tmp_path.resolve()})


def _record(
    ticker: str = "O:SPY260918C00500000",
    *,
    expiration_date: str = "2026-09-18",
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "underlying_ticker": "SPY",
        "contract_type": "call",
        "expiration_date": expiration_date,
        "strike_price": 500,
        "exercise_style": "american",
        "shares_per_contract": 100,
        "primary_exchange": "BATO",
        "cfi": "OCASPS",
        "correction": 0,
        "additional_underlyings": [],
    }


def test_acquisition_contract_is_frozen_and_source_only() -> None:
    manifest = acquisition_contract_manifest()

    assert (
        HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT
        == "95eb5048336e411cb31c912e2cf8569915aedd42fc9e9f0fd0917f3fb3fe3f23"
    )
    assert manifest["reference_as_of_date"] == "2026-09-19"
    assert manifest["history_start"] == "2014-06-02"
    assert manifest["active_hard_end_exclusive"] == "2032-01-01"
    assert manifest["page_limit"] == 1000
    assert manifest["storage_category"] == "options_reference"
    assert len(manifest["partitions"]) == 212
    assert manifest["authority"] == {
        "source_acquisition_only": True,
        "predictor_generation": False,
        "strategy_outcome_access": False,
        "paper_authority": False,
        "live_authority": False,
    }
    assert manifest["source_role"]["reference_identity_and_structure"] is True
    assert (
        manifest["source_role"]["historical_candidate_availability_authority"]
        is False
    )
    assert (
        manifest["source_role"]["historical_dynamic_deliverable_authority"]
        is False
    )


def test_reference_partitions_cover_frozen_scope_without_overlap() -> None:
    partitions = reference_partitions()

    assert len(partitions) == 212
    assert partitions[0] == ReferencePartition(
        key="expired-2014-06",
        state="EXPIRED",
        expiration_gte=HISTORY_START,
        expiration_lt=date(2014, 7, 1),
        expired=True,
    )
    assert partitions[-1] == ReferencePartition(
        key="active-2031-12",
        state="ACTIVE",
        expiration_gte=date(2031, 12, 1),
        expiration_lt=ACTIVE_HARD_END_EXCLUSIVE,
        expired=False,
    )

    expired = [item for item in partitions if item.state == "EXPIRED"]
    active = [item for item in partitions if item.state == "ACTIVE"]
    assert expired[-1].expiration_lt == REFERENCE_AS_OF_DATE.replace(day=20)
    assert active[0].expiration_gte == REFERENCE_AS_OF_DATE.replace(day=20)

    ordered = sorted(
        partitions,
        key=lambda item: (item.expiration_gte, item.state),
    )
    for left, right in zip(ordered, ordered[1:]):
        if left.state == right.state:
            assert left.expiration_lt <= right.expiration_gte


def test_normalization_preserves_structural_fields_and_authority() -> None:
    partition = ReferencePartition(
        key="expired-2026-09",
        state="EXPIRED",
        expiration_gte=date(2026, 9, 1),
        expiration_lt=date(2026, 9, 20),
        expired=True,
    )
    raw = _record()
    normalized = acquisition._normalize_record(raw, partition=partition)

    assert normalized["ticker"] == raw["ticker"]
    assert normalized["underlying_ticker"] == "SPY"
    assert normalized["expiration_date"] == "2026-09-18"
    assert normalized["reference_as_of_date"] == "2026-09-19"
    assert normalized["reference_state"] == "EXPIRED"
    assert normalized["source_role"] == "REFERENCE_IDENTITY_STRUCTURE_ONLY"
    assert normalized["provider_record_sha256"]


def test_normalization_fails_if_provider_row_escapes_partition() -> None:
    partition = ReferencePartition(
        key="expired-2026-08",
        state="EXPIRED",
        expiration_gte=date(2026, 8, 1),
        expiration_lt=date(2026, 9, 1),
        expired=True,
    )

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV1Error,
        match="escaped",
    ):
        acquisition._normalize_record(
            _record(expiration_date="2026-09-18"),
            partition=partition,
        )


def test_active_hard_end_probe_fails_closed_on_any_returned_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        acquisition,
        "_request_json",
        lambda *_args, **_kwargs: {
            "status": "OK",
            "results": [
                _record(
                    ticker="O:SPY320116C00500000",
                    expiration_date="2032-01-16",
                )
            ],
        },
    )

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV1Error,
        match="hard end",
    ):
        acquisition._boundary_probe(settings, api_key="token")


def test_active_hard_end_probe_accepts_empty_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        acquisition,
        "_request_json",
        lambda *_args, **_kwargs: {
            "status": "OK",
            "results": [],
        },
    )

    report = acquisition._boundary_probe(settings, api_key="token")

    assert report["status"] == "PASS"
    assert report["result_count"] == 0
    assert report["expiration_date_gte"] == "2032-01-01"
