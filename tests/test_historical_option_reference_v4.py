from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

import packages.data.historical_option_reference_v4 as acquisition
from packages.core.settings import load_settings
from packages.data.historical_option_reference_v4_contract import (
    ACHI_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    AAL_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    CONFLICT_RESOLUTION_POLICY,
    HISTORICAL_OPTION_REFERENCE_V4_CONTRACT_FINGERPRINT,
    ReferencePartition,
    acquisition_contract_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PARTITION = ReferencePartition(
    key="expired-2014-06",
    state="EXPIRED",
    expiration_gte=date(2014, 6, 2),
    expiration_lt=date(2014, 7, 1),
    expired=True,
)


def _settings(tmp_path: Path):
    base = load_settings(PROJECT_ROOT)
    return base.model_copy(update={"project_root": tmp_path.resolve()})


def _row(
    *,
    ticker: str = "O:AAL140621C00020000",
    underlying: str = "AAL",
    exchange: str = "BATO",
    strike: int = 20,
    correction=None,
    shares: int = 100,
):
    row = {
        "ticker": ticker,
        "underlying_ticker": underlying,
        "contract_type": "call",
        "expiration_date": "2014-06-21",
        "strike_price": strike,
        "exercise_style": "american",
        "shares_per_contract": shares,
        "primary_exchange": exchange,
        "cfi": "OCASPS",
        "additional_underlyings": [],
    }
    if correction is not None:
        row["correction"] = correction
    return row


def test_v4_contract_is_frozen_and_narrow() -> None:
    manifest = acquisition_contract_manifest()

    assert HISTORICAL_OPTION_REFERENCE_V4_CONTRACT_FINGERPRINT == (
        "2ddeb58d5f552ff0edb87a2244f130b813cf49600f5f82b1f50d8e1ee047a57d"
    )
    assert manifest["parent_v3_contract_fingerprint"] == (
        "7a9dab85c57bbc6cd93dee2472a9244d86e8c1776f986cd97036b9963bc4c48e"
    )
    assert manifest["accepted_diagnostics"]["aal_primary_exchange"][
        "evidence_fingerprint"
    ] == AAL_DIAGNOSTIC_EVIDENCE_FINGERPRINT
    assert manifest["accepted_diagnostics"]["achi_underlying_identity"][
        "evidence_fingerprint"
    ] == ACHI_DIAGNOSTIC_EVIDENCE_FINGERPRINT

    fallback = manifest["normalization"]["narrow_conflict_fallback"]
    assert fallback["eligible_reference_state"] == "EXPIRED"
    assert fallback["eligible_highest_correction_rank"] == -1
    assert fallback["allowed_differing_fields"] == [
        "primary_exchange",
        "underlying_ticker",
    ]
    assert fallback["historical_list"]["underlying_filter"] == "OMITTED"
    assert fallback["historical_list"]["target_ticker_rows_required"] == 1
    assert fallback["historical_list_and_overview_payload_must_match"] is True
    assert (
        fallback[
            "historical_payload_must_exactly_match_one_current_conflicting_payload"
        ]
        is True
    )
    assert fallback["stock_reference_not_runtime_authority"] is True
    assert fallback["external_corroboration_not_runtime_authority"] is True
    assert fallback["otherwise"] == "FAIL_CLOSED"

    assert manifest["reuse"] == {
        "verified_v4_receipts": True,
        "verified_v3_raw_lineage": True,
        "verified_v2_raw_lineage": True,
        "verified_v1_raw_lineage": True,
        "local_renormalization_required": True,
        "raw_copy_required": False,
    }
    assert manifest["authority"]["strategy_outcome_access"] is False
    assert manifest["authority"]["paper_authority"] is False
    assert manifest["authority"]["live_authority"] is False


def test_v4_resolves_primary_exchange_conflict_only_from_matching_historical_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _row(exchange="BATO")
    right = _row(exchange="XMIO")
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
        assert ticker == left["ticker"]
        assert contract_type == "call"
        assert expiration == date(2014, 6, 21)
        assert strike_price == "20"
        assert as_of == date(2014, 6, 20)
        list_calls.append(ticker)
        return right, [f"list-{len(list_calls)}"]

    def fake_request(_settings, *, url: str, api_key: str):
        assert api_key == "token"
        assert "as_of=2014-06-20" in url
        overview_calls.append(url)
        return {
            "status": "OK",
            "request_id": f"overview-{len(overview_calls)}",
            "results": right,
        }

    monkeypatch.setattr(
        acquisition,
        "_historical_target_row_once",
        fake_historical_list,
    )
    monkeypatch.setattr(acquisition, "_request_json", fake_request)

    normalized, discarded = acquisition._resolve_ticker_versions(
        [left, right],
        partition=PARTITION,
        settings=settings,
        api_key="token",
    )

    assert len(list_calls) == 2
    assert len(overview_calls) == 2
    assert normalized["primary_exchange"] == "XMIO"
    assert normalized["underlying_ticker"] == "AAL"
    assert normalized["historically_resolved_conflict"] is True
    assert normalized["conflict_resolution_policy"] == CONFLICT_RESOLUTION_POLICY
    assert normalized["conflict_resolution_as_of_date"] == "2014-06-20"
    assert normalized["conflict_resolution_differing_fields_json"] == (
        '["primary_exchange"]'
    )
    assert discarded == 1


def test_v4_resolves_underlying_identity_conflict_only_from_matching_historical_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    old_symbol = _row(
        ticker="O:ACHI140621C00001000",
        underlying="AH",
        exchange="XBOX",
        strike=1,
    )
    historical_symbol = _row(
        ticker="O:ACHI140621C00001000",
        underlying="ACHI",
        exchange="XBOX",
        strike=1,
    )

    monkeypatch.setattr(
        acquisition,
        "_historical_target_row_once",
        lambda *_args, **_kwargs: (
            historical_symbol,
            ["historical-list"],
        ),
    )
    monkeypatch.setattr(
        acquisition,
        "_request_json",
        lambda *_args, **_kwargs: {
            "status": "OK",
            "request_id": "historical-overview",
            "results": historical_symbol,
        },
    )

    normalized, discarded = acquisition._resolve_ticker_versions(
        [historical_symbol, old_symbol],
        partition=PARTITION,
        settings=settings,
        api_key="token",
    )

    assert normalized["underlying_ticker"] == "ACHI"
    assert normalized["historically_resolved_conflict"] is True
    assert normalized["conflict_resolution_differing_fields_json"] == (
        '["underlying_ticker"]'
    )
    assert normalized["conflict_resolution_historical_list_sha256"] == (
        acquisition._stable_hash(historical_symbol)
    )
    assert normalized["conflict_resolution_overview_sha256"] == (
        acquisition._stable_hash(historical_symbol)
    )
    assert discarded == 1


def test_v4_rejects_economic_conflict_before_provider_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)

    def should_not_request(*_args, **_kwargs):
        raise AssertionError("provider fallback must not run for economic conflicts")

    monkeypatch.setattr(
        acquisition,
        "_historical_target_row_once",
        should_not_request,
    )
    monkeypatch.setattr(acquisition, "_request_json", should_not_request)

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV4Error,
        match="exceed frozen V4 allowance",
    ):
        acquisition._resolve_ticker_versions(
            [
                _row(shares=100),
                _row(shares=50),
            ],
            partition=PARTITION,
            settings=settings,
            api_key="token",
        )


def test_v4_rejects_explicit_same_correction_conflict(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV4Error,
        match="requires missing correction",
    ):
        acquisition._resolve_ticker_versions(
            [
                _row(exchange="BATO", correction=2),
                _row(exchange="XMIO", correction=2),
            ],
            partition=PARTITION,
            settings=settings,
            api_key="token",
        )


def test_v4_rejects_historical_list_overview_disagreement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _row(exchange="BATO")
    right = _row(exchange="XMIO")

    monkeypatch.setattr(
        acquisition,
        "_historical_target_row_once",
        lambda *_args, **_kwargs: (right, ["list"]),
    )
    monkeypatch.setattr(
        acquisition,
        "_request_json",
        lambda *_args, **_kwargs: {
            "status": "OK",
            "request_id": "overview",
            "results": left,
        },
    )

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV4Error,
        match="structural-list and Contract Overview payloads did not match",
    ):
        acquisition._resolve_ticker_versions(
            [left, right],
            partition=PARTITION,
            settings=settings,
            api_key="token",
        )


def test_v4_rejects_historical_payload_not_present_in_current_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _row(exchange="BATO")
    right = _row(exchange="XMIO")
    unseen = _row(exchange="XBOX")

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
        acquisition.HistoricalOptionReferenceV4Error,
        match="matched 0 current conflicting rows instead of 1",
    ):
        acquisition._resolve_ticker_versions(
            [left, right],
            partition=PARTITION,
            settings=settings,
            api_key="token",
        )


def test_v4_never_merges_adjusted_series_into_standard_ticker() -> None:
    standard = _row(exchange="BATO")
    adjusted = {
        **standard,
        "ticker": "O:AAL2140621C00020000",
    }

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV4Error,
        match="mixed ticker identities",
    ):
        acquisition._resolve_ticker_versions(
            [standard, adjusted],
            partition=PARTITION,
        )
