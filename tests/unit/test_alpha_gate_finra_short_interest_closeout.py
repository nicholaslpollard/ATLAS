from __future__ import annotations

from packages.backtesting import alpha_gate_finra_short_interest_closeout as closeout


def test_finra_closeout_acceptance_constants_are_pinned() -> None:
    assert closeout.FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_TARGET_HEAD == (
        "d312ec95752ab49a6fcbec18973faacb96d4aa89"
    )
    assert closeout.FINRA_SHORT_INTEREST_ACCEPTED_PROBE_HEAD == (
        "5ceac74ad67c8f3539b03192cf1946d51d476434"
    )
    assert closeout.FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_REPORT_SHA256 == (
        "56479707945a59752aeb2056f3cfbcfd2df1e4a87ada31c9e8e6d3ed93f314cd"
    )
    assert closeout.FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_ROWS_SHA256 == (
        "21c7dd2e44013ba0f1d290019db70f7b0f23b0603c5e965cbd8b441128190e48"
    )
    assert closeout.FINRA_SHORT_INTEREST_ACCEPTED_PROBE_EVIDENCE_FINGERPRINT == (
        "c624da82b45fb8d530c2400262598f266ec6309e614a0dcd135b38d9ba5518ce"
    )
    assert closeout.FINRA_SHORT_INTEREST_ACCEPTED_CLOSEOUT_EVIDENCE_FINGERPRINT == (
        "bdd494a01ed23d891c460e353831cba6f9cf010c5bf38cf1c9c527b4abe8b565"
    )


def test_finra_closeout_preserves_exact_source_negative() -> None:
    assert closeout.FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_DISPOSITION == (
        "ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT"
    )
    assert closeout.FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_ROWS == 19_343
    assert closeout.FINRA_SHORT_INTEREST_ACCEPTED_DEVELOPMENT_ROWS == 14_841
    assert closeout.FINRA_SHORT_INTEREST_ACCEPTED_PROTECTED_ROWS == 4_502
    assert closeout.FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_EVENT_ROWS == 257
    assert closeout.FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_SIGNAL_SESSIONS == 26
    assert closeout.FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_UNIQUE_INSTRUMENTS == 211


def test_finra_closeout_fingerprint_payload_is_stable() -> None:
    payload = {
        "closeout_contract": closeout.FINRA_SHORT_INTEREST_CLOSEOUT_CONTRACT,
        "accepted_source_target_head": closeout.FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_TARGET_HEAD,
        "accepted_probe_head": closeout.FINRA_SHORT_INTEREST_ACCEPTED_PROBE_HEAD,
        "scientific_fingerprint": closeout.FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
        "predictor_report_sha256": closeout.FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_REPORT_SHA256,
        "predictor_rows_sha256": closeout.FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_ROWS_SHA256,
        "probe_evidence_fingerprint": closeout.FINRA_SHORT_INTEREST_ACCEPTED_PROBE_EVIDENCE_FINGERPRINT,
        "source_disposition": closeout.FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_DISPOSITION,
        "underpowered_candidate": closeout.FINRA_SHORT_INTEREST_UNDERPOWERED_CANDIDATE,
        "protected_event_rows": closeout.FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_EVENT_ROWS,
        "protected_signal_sessions": closeout.FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_SIGNAL_SESSIONS,
        "protected_unique_instruments": closeout.FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_UNIQUE_INSTRUMENTS,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "historical_supported_alpha": 0,
        "phase33_signal_to_trade_authority": False,
    }
    assert closeout._fingerprint(payload) == (
        closeout.FINRA_SHORT_INTEREST_ACCEPTED_CLOSEOUT_EVIDENCE_FINGERPRINT
    )
