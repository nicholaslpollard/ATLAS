from __future__ import annotations

from datetime import date

import pytest

from packages.backtesting.phase32_predictor_acceptance import (
    PHASE32_PREDICTOR_INDEPENDENT_ACCEPTANCE_CONTRACT,
    PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256,
    PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256,
    Phase32PredictorIndependentAcceptanceError,
    _decision_and_exit_sessions,
    _rebuild_predictors,
    _stage_for_decision,
    reconcile_massive_text_rows,
)


def _base_text() -> dict[str, object]:
    return {
        "accession_number": "0000000001-23-000001",
        "cik": "0000000001",
        "filing_date": "2023-10-05",
        "form_type": "8-K",
        "filing_url": "https://www.sec.gov/example.txt",
        "items_text": "same filing text",
    }


def _filing(candidate_id: str, accession: str) -> dict[str, object]:
    return {
        "eligibility": "eligible",
        "instrument": {
            "instrument_id": "figi:ABC",
            "identity_key": ["composite_figi", "ABC"],
            "identity_quality": "strong",
        },
        "candidate_ids": [candidate_id],
        "accession_number": accession,
        "issuer_cik": "0000000001",
        "decision_session": "2023-10-06",
        "exit_session": "2023-10-13",
        "stage": "development",
        "provider_tickers": ["ABC"],
        "taxonomy_triples": [["x", "y", "z"]],
        "acceptance_datetime": "2023-10-05T16:00:00-04:00",
        "sec_source_record_sha256": "a" * 64,
        "massive_text_sha256": "b" * 64,
        "supporting_text_sha256": ["c" * 64],
    }


def test_independent_contract_pins_target_machine_artifacts() -> None:
    assert PHASE32_PREDICTOR_INDEPENDENT_ACCEPTANCE_CONTRACT == (
        "phase32-predictor-independent-acceptance-v1-local-immutable-source-only"
    )
    assert PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256 == (
        "18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31"
    )
    assert PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256 == (
        "c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9"
    )


def test_independent_text_reconciliation_accepts_ticker_only_multiplicity() -> None:
    base = _base_text()
    result = reconcile_massive_text_rows(
        [{**base, "ticker": "FRNM"}, {**base, "ticker": "PCSC"}],
        accession="0000000001-23-000001",
        issuer_cik="0000000001",
    )
    assert result["row_count"] == 2
    assert result["tickers"] == ["FRNM", "PCSC"]
    assert len(result["aggregate_sha256"]) == 64
    assert len(result["non_ticker_sha256"]) == 64


def test_independent_text_reconciliation_fails_non_ticker_conflict() -> None:
    base = _base_text()
    with pytest.raises(Phase32PredictorIndependentAcceptanceError, match="conflict beyond ticker"):
        reconcile_massive_text_rows(
            [{**base, "ticker": "FRNM"}, {**base, "ticker": "PCSC", "items_text": "changed"}],
            accession="0000000001-23-000001",
            issuer_cik="0000000001",
        )


def test_strict_after_open_chronology_is_recomputed_independently() -> None:
    pre_open_decision, pre_open_exit = _decision_and_exit_sessions("2023-10-05T08:00:00-04:00")
    equal_open_decision, equal_open_exit = _decision_and_exit_sessions("2023-10-05T09:30:00-04:00")
    assert pre_open_decision == date(2023, 10, 5)
    assert pre_open_exit == date(2023, 10, 12)
    assert equal_open_decision == date(2023, 10, 6)
    assert equal_open_exit == date(2023, 10, 13)


def test_stage_boundaries_are_recomputed_independently() -> None:
    assert _stage_for_decision(date(2021, 8, 16)) == "development"
    assert _stage_for_decision(date(2026, 5, 4)) == "development"
    assert _stage_for_decision(date(2026, 5, 5)) == "outer_embargo"
    assert _stage_for_decision(date(2026, 5, 12)) == "protected_predictor_only"
    assert _stage_for_decision(date(2026, 8, 4)) == "protected_predictor_only"
    assert _stage_for_decision(date(2026, 8, 5)) == "outside_frozen_signal_window"


def test_independent_predictor_rebuild_excludes_long_short_contradiction() -> None:
    predictors, contradictory_sessions, contradictory_rows = _rebuild_predictors(
        [
            _filing("share_repurchase_long", "0000000001-23-000001"),
            _filing("equity_issuance_short", "0000000001-23-000002"),
        ]
    )
    assert predictors == []
    assert contradictory_sessions == 1
    assert contradictory_rows == 2


def test_independent_predictor_rebuild_preserves_zero_outcome_authority() -> None:
    predictors, contradictory_sessions, contradictory_rows = _rebuild_predictors(
        [_filing("share_repurchase_long", "0000000001-23-000001")]
    )
    assert len(predictors) == 1
    assert predictors[0]["candidate_id"] == "share_repurchase_long"
    assert predictors[0]["outcome_rows_read"] == 0
    assert contradictory_sessions == 0
    assert contradictory_rows == 0
