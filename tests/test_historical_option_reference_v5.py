from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

import packages.data.historical_option_reference_v5 as acquisition
from packages.core.settings import load_settings
from packages.data.historical_option_reference_v5_contract import (
    ACT2_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    CONFLICT_RESOLUTION_POLICY,
    HISTORICAL_OPTION_REFERENCE_V5_CONTRACT_FINGERPRINT,
    ReferencePartition,
    acquisition_contract_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

JUNE_PARTITION = ReferencePartition(
    key="expired-2014-06",
    state="EXPIRED",
    expiration_gte=date(2014, 6, 2),
    expiration_lt=date(2014, 7, 1),
    expired=True,
)
JULY_PARTITION = ReferencePartition(
    key="expired-2014-07",
    state="EXPIRED",
    expiration_gte=date(2014, 7, 1),
    expiration_lt=date(2014, 8, 1),
    expired=True,
)
ACTIVE_PARTITION = ReferencePartition(
    key="active-2026-09",
    state="ACTIVE",
    expiration_gte=date(2026, 9, 20),
    expiration_lt=date(2026, 10, 1),
    expired=False,
)

_MISSING = object()


def _settings(tmp_path: Path):
    base = load_settings(PROJECT_ROOT)
    return base.model_copy(update={"project_root": tmp_path.resolve()})


def _row(
    *,
    ticker: str = "O:AAL140621C00020000",
    underlying: str = "AAL",
    exchange: str = "BATO",
    expiration: str = "2014-06-21",
    strike: int = 20,
    correction: object = _MISSING,
    shares: int = 100,
    additional_underlyings: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "ticker": ticker,
        "underlying_ticker": underlying,
        "contract_type": "call",
        "expiration_date": expiration,
        "strike_price": strike,
        "exercise_style": "american",
        "shares_per_contract": shares,
        "primary_exchange": exchange,
        "cfi": "OCASPS",
        "additional_underlyings": additional_underlyings or [],
    }
    if correction is not _MISSING:
        row["correction"] = correction
    return row


def _act2_row(*, amount: float, correction: int = 2) -> dict[str, object]:
    return _row(
        ticker="O:ACT2140719C00045000",
        underlying="ACT",
        exchange="XBOX",
        expiration="2014-07-19",
        strike=45,
        correction=correction,
        additional_underlyings=[
            {
                "amount": amount,
                "type": "currency",
                "underlying": "USD",
            }
        ],
    )


def test_v5_contract_is_frozen_and_narrow() -> None:
    manifest = acquisition_contract_manifest()

    assert HISTORICAL_OPTION_REFERENCE_V5_CONTRACT_FINGERPRINT == (
        "4a9775c90414d8a454654d5f0928d79b68dec785b16b493e197ea34471aef1ea"
    )
    assert manifest["parent_v4_contract_fingerprint"] == (
        "2ddeb58d5f552ff0edb87a2244f130b813cf49600f5f82b1f50d8e1ee047a57d"
    )
    act2 = manifest["accepted_diagnostics"]["act2_explicit_correction_deliverable"]
    assert act2["evidence_fingerprint"] == ACT2_DIAGNOSTIC_EVIDENCE_FINGERPRINT
    assert act2["current_correction_values"] == [2]
    assert act2["historical_correction_values"] == [2]
    assert act2["differing_fields"] == ["additional_underlyings"]

    unversioned = manifest["normalization"]["unversioned_identity_fallback"]
    assert unversioned["eligible_highest_correction_rank"] == -1
    assert unversioned["allowed_differing_fields"] == [
        "primary_exchange",
        "underlying_ticker",
    ]

    explicit = manifest["normalization"][
        "explicit_correction_deliverable_fallback"
    ]
    assert explicit["eligible_highest_correction_rank"] == "EXPLICIT_NONNEGATIVE"
    assert explicit["allowed_differing_fields"] == ["additional_underlyings"]
    assert (
        explicit[
            "historical_payload_correction_rank_must_equal_current_highest_rank"
        ]
        is True
    )
    assert explicit["dynamic_deliverable_authority_created"] is False
    assert explicit["otherwise"] == "FAIL_CLOSED"

    assert manifest["reuse"] == {
        "verified_v5_receipts": True,
        "verified_v4_raw_lineage": True,
        "verified_v3_raw_lineage": True,
        "verified_v2_raw_lineage": True,
        "verified_v1_raw_lineage": True,
        "local_renormalization_required": True,
        "raw_copy_required": False,
    }
    assert manifest["authority"]["strategy_outcome_access"] is False
    assert manifest["authority"]["paper_authority"] is False
    assert manifest["authority"]["live_authority"] is False


def test_v5_retains_unversioned_primary_exchange_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _row(exchange="BATO")
    historical = _row(exchange="XMIO")

    monkeypatch.setattr(
        acquisition,
        "_historical_target_row_once",
        lambda *_args, **_kwargs: (historical, ["list"]),
    )
    monkeypatch.setattr(
        acquisition,
        "_request_json",
        lambda *_args, **_kwargs: {
            "status": "OK",
            "request_id": "overview",
            "results": historical,
        },
    )

    normalized, discarded = acquisition._resolve_ticker_versions(
        [left, historical],
        partition=JUNE_PARTITION,
        settings=settings,
        api_key="token",
    )

    assert normalized["primary_exchange"] == "XMIO"
    assert normalized["selected_correction_rank"] == -1
    assert normalized["historically_resolved_conflict"] is True
    assert normalized["conflict_resolution_policy"] == CONFLICT_RESOLUTION_POLICY
    assert normalized["conflict_resolution_differing_fields_json"] == (
        '["primary_exchange"]'
    )
    assert discarded == 1


def test_v5_resolves_act2_explicit_correction_deliverable_only_from_historical_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _act2_row(amount=2617.04)
    historical = _act2_row(amount=2604)

    list_calls: list[str] = []
    overview_calls: list[str] = []

    def fake_historical_list(
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
        assert ticker == "O:ACT2140719C00045000"
        assert contract_type == "call"
        assert expiration == date(2014, 7, 19)
        assert strike_price == "45"
        assert as_of == date(2014, 7, 18)
        list_calls.append(ticker)
        return historical, [f"list-{len(list_calls)}"]

    def fake_request(_settings, *, url: str, api_key: str):
        assert api_key == "token"
        assert "as_of=2014-07-18" in url
        overview_calls.append(url)
        return {
            "status": "OK",
            "request_id": f"overview-{len(overview_calls)}",
            "results": historical,
        }

    monkeypatch.setattr(
        acquisition,
        "_historical_target_row_once",
        fake_historical_list,
    )
    monkeypatch.setattr(acquisition, "_request_json", fake_request)

    normalized, discarded = acquisition._resolve_ticker_versions(
        [left, historical],
        partition=JULY_PARTITION,
        settings=settings,
        api_key="token",
    )

    assert len(list_calls) == 2
    assert len(overview_calls) == 2
    assert normalized["selected_correction_rank"] == 2
    assert normalized["additional_underlyings_json"] == (
        '[{"amount":2604,"type":"currency","underlying":"USD"}]'
    )
    assert normalized["historically_resolved_conflict"] is True
    assert normalized["conflict_resolution_as_of_date"] == "2014-07-18"
    assert normalized["conflict_resolution_differing_fields_json"] == (
        '["additional_underlyings"]'
    )
    assert normalized["conflict_resolution_historical_list_sha256"] == (
        acquisition._stable_hash(historical)
    )
    assert normalized["conflict_resolution_overview_sha256"] == (
        acquisition._stable_hash(historical)
    )
    assert discarded == 1


def test_v5_rejects_explicit_primary_exchange_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)

    def should_not_request(*_args, **_kwargs):
        raise AssertionError("provider fallback must not run for disallowed fields")

    monkeypatch.setattr(
        acquisition,
        "_historical_target_row_once",
        should_not_request,
    )
    monkeypatch.setattr(acquisition, "_request_json", should_not_request)

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV5Error,
        match="explicit same-rank conflict fields",
    ):
        acquisition._resolve_ticker_versions(
            [
                _row(exchange="BATO", correction=2),
                _row(exchange="XMIO", correction=2),
            ],
            partition=JUNE_PARTITION,
            settings=settings,
            api_key="token",
        )


def test_v5_rejects_explicit_deliverable_conflict_on_active_contract(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    left = _row(
        ticker="O:TEST260925C00045000",
        underlying="TEST",
        expiration="2026-09-25",
        strike=45,
        correction=2,
        additional_underlyings=[
            {"amount": 1, "type": "currency", "underlying": "USD"}
        ],
    )
    right = {
        **left,
        "additional_underlyings": [
            {"amount": 2, "type": "currency", "underlying": "USD"}
        ],
    }

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV5Error,
        match="expired-contract only",
    ):
        acquisition._resolve_ticker_versions(
            [left, right],
            partition=ACTIVE_PARTITION,
            settings=settings,
            api_key="token",
        )


def test_v5_rejects_historical_correction_rank_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _act2_row(amount=2617.04, correction=2)
    right = _act2_row(amount=2604, correction=2)
    historical_wrong_rank = _act2_row(amount=2604, correction=1)

    monkeypatch.setattr(
        acquisition,
        "_historical_target_row_once",
        lambda *_args, **_kwargs: (historical_wrong_rank, ["list"]),
    )

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV5Error,
        match="did not equal current highest rank 2",
    ):
        acquisition._resolve_ticker_versions(
            [left, right],
            partition=JULY_PARTITION,
            settings=settings,
            api_key="token",
        )


def test_v5_rejects_explicit_deliverable_historical_payload_not_in_current_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _act2_row(amount=2617.04)
    right = _act2_row(amount=2604)
    unseen = _act2_row(amount=2700)

    monkeypatch.setattr(
        acquisition,
        "_historical_target_row_once",
        lambda *_args, **_kwargs: (unseen, ["list"]),
    )
    monkeypatch.setattr(
        acquisition,
        "_request_json",
        lambda *_args, **_kwargs: {
            "status": "OK",
            "request_id": "overview",
            "results": unseen,
        },
    )

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV5Error,
        match="matched 0 current conflicting rows instead of 1",
    ):
        acquisition._resolve_ticker_versions(
            [left, right],
            partition=JULY_PARTITION,
            settings=settings,
            api_key="token",
        )


def test_v5_known_conflicts_freeze_three_distinct_resolution_cases() -> None:
    manifest = acquisition_contract_manifest()
    probes = manifest["known_conflict_preacquisition_probes"]

    assert [item["id"] for item in probes] == [
        "AAL_PRIMARY_EXCHANGE",
        "ACHI_UNDERLYING_IDENTITY",
        "ACT2_EXPLICIT_CORRECTION_DELIVERABLE",
    ]
    assert probes[0]["expected_highest_correction_rank"] == -1
    assert probes[1]["expected_highest_correction_rank"] == -1
    assert probes[2]["expected_highest_correction_rank"] == 2
    assert probes[2]["expected_differing_fields"] == ["additional_underlyings"]
    assert probes[2]["diagnostic_evidence_fingerprint"] == (
        ACT2_DIAGNOSTIC_EVIDENCE_FINGERPRINT
    )


def test_v5_never_merges_adjusted_series_into_standard_ticker() -> None:
    standard = _row()
    adjusted = {
        **standard,
        "ticker": "O:AAL2140621C00020000",
    }

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV5Error,
        match="mixed ticker identities",
    ):
        acquisition._resolve_ticker_versions(
            [standard, adjusted],
            partition=JUNE_PARTITION,
        )
