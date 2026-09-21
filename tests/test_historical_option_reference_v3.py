from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

import packages.data.historical_option_reference_v3 as acquisition
from packages.core.settings import load_settings
from packages.data.historical_option_reference_v3_contract import (
    CONFLICT_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    CONFLICT_RESOLUTION_POLICY,
    HISTORICAL_OPTION_REFERENCE_V3_CONTRACT_FINGERPRINT,
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


def _row(*, exchange: str, correction=None, shares: int = 100):
    row = {
        "ticker": "O:AAL140621C00020000",
        "underlying_ticker": "AAL",
        "contract_type": "call",
        "expiration_date": "2014-06-21",
        "strike_price": 20,
        "exercise_style": "american",
        "shares_per_contract": shares,
        "primary_exchange": exchange,
        "cfi": "OCASPS",
        "additional_underlyings": [],
    }
    if correction is not None:
        row["correction"] = correction
    return row


def test_v3_contract_is_frozen_and_narrow() -> None:
    manifest = acquisition_contract_manifest()

    assert (
        HISTORICAL_OPTION_REFERENCE_V3_CONTRACT_FINGERPRINT
        == "7a9dab85c57bbc6cd93dee2472a9244d86e8c1776f986cd97036b9963bc4c48e"
    )
    assert manifest["parent_v2_contract_fingerprint"] == (
        "6d0af0b58a66b77c445d7e561d759dfd947e348e994045a1f7cfc16aeb9ccb41"
    )
    assert manifest["conflict_diagnostic"]["evidence_fingerprint"] == (
        CONFLICT_DIAGNOSTIC_EVIDENCE_FINGERPRINT
        == "20f255cab7b19e1d27902a76ed386e94156393c019434fbff4623b6d269a1722"
    )
    fallback = manifest["normalization"]["narrow_conflict_fallback"]
    assert fallback["eligible_reference_state"] == "EXPIRED"
    assert fallback["eligible_highest_correction_rank"] == -1
    assert fallback["allowed_differing_fields"] == ["primary_exchange"]
    assert fallback["repeat_count"] == 2
    assert fallback["overview_payload_must_exactly_match_one_current_conflicting_payload"] is True
    assert fallback["otherwise"] == "FAIL_CLOSED"
    assert manifest["known_conflict_preacquisition_probe"][
        "must_pass_before_bulk_provider_acquisition"
    ] is True
    assert manifest["authority"]["strategy_outcome_access"] is False
    assert manifest["authority"]["paper_authority"] is False
    assert manifest["authority"]["live_authority"] is False


def test_v3_resolves_only_primary_exchange_conflict_from_stable_preexpiration_overview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _row(exchange="BATO")
    right = _row(exchange="XMIO")
    calls: list[str] = []

    def fake_request(_settings, *, url: str, api_key: str):
        assert api_key == "token"
        calls.append(url)
        assert "as_of=2014-06-20" in url
        return {
            "status": "OK",
            "request_id": f"overview-{len(calls)}",
            "results": right,
        }

    monkeypatch.setattr(acquisition, "_request_json", fake_request)

    normalized, discarded = acquisition._resolve_ticker_versions(
        [left, right],
        partition=PARTITION,
        settings=settings,
        api_key="token",
    )

    assert len(calls) == 2
    assert normalized["primary_exchange"] == "XMIO"
    assert normalized["provider_record_sha256"] == acquisition._stable_hash(right)
    assert normalized["historically_resolved_conflict"] is True
    assert normalized["conflict_resolution_policy"] == CONFLICT_RESOLUTION_POLICY
    assert normalized["conflict_resolution_as_of_date"] == "2014-06-20"
    assert normalized["conflict_resolution_repeat_count"] == 2
    assert normalized["conflict_resolution_differing_fields_json"] == (
        '["primary_exchange"]'
    )
    assert discarded == 1


def test_v3_rejects_same_rank_economic_conflict_without_provider_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)

    def should_not_request(*_args, **_kwargs):
        raise AssertionError("provider fallback must not run for economic conflicts")

    monkeypatch.setattr(acquisition, "_request_json", should_not_request)

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV3Error,
        match="exceed frozen V3 allowance",
    ):
        acquisition._resolve_ticker_versions(
            [
                _row(exchange="BATO", shares=100),
                _row(exchange="BATO", shares=50),
            ],
            partition=PARTITION,
            settings=settings,
            api_key="token",
        )


def test_v3_rejects_explicit_same_correction_conflict(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV3Error,
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


def test_v3_rejects_stable_overview_that_matches_no_current_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _row(exchange="BATO")
    right = _row(exchange="XMIO")
    unseen = _row(exchange="XBOX")

    monkeypatch.setattr(
        acquisition,
        "_request_json",
        lambda *_args, **_kwargs: {
            "status": "OK",
            "request_id": "stable-unseen",
            "results": unseen,
        },
    )

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV3Error,
        match="did not exactly match any current conflicting payload",
    ):
        acquisition._resolve_ticker_versions(
            [left, right],
            partition=PARTITION,
            settings=settings,
            api_key="token",
        )


def test_known_conflict_probe_must_resolve_before_bulk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    left = _row(exchange="BATO")
    right = _row(exchange="XMIO")
    calls: list[str] = []

    def fake_request(_settings, *, url: str, api_key: str):
        calls.append(url)
        if "underlying_ticker=AAL" in url:
            return {
                "status": "OK",
                "request_id": "list",
                "results": [
                    left,
                    right,
                    {
                        **right,
                        "ticker": "O:AAL2140621C00020000",
                    },
                ],
            }
        return {
            "status": "OK",
            "request_id": f"overview-{len(calls)}",
            "results": right,
        }

    monkeypatch.setattr(acquisition, "_request_json", fake_request)

    result = acquisition._known_conflict_resolution_probe(
        settings,
        api_key="token",
    )

    assert len(calls) == 3
    assert result["status"] == "PASS"
    assert result["ticker"] == "O:AAL140621C00020000"
    assert result["selected_primary_exchange"] == "XMIO"
    assert result["resolution_as_of_date"] == "2014-06-20"
    assert result["diagnostic_evidence_fingerprint"] == (
        CONFLICT_DIAGNOSTIC_EVIDENCE_FINGERPRINT
    )


def test_v3_never_merges_adjusted_series_into_standard_ticker() -> None:
    standard = _row(exchange="BATO")
    adjusted = {
        **standard,
        "ticker": "O:AAL2140621C00020000",
    }

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV3Error,
        match="mixed ticker identities",
    ):
        acquisition._resolve_ticker_versions(
            [standard, adjusted],
            partition=PARTITION,
        )
