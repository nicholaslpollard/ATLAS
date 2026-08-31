from __future__ import annotations

import hashlib
import json
from typing import Any

from packages.backtesting.alpha_gate_finra_short_interest_scientific_policy import (
    FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
)
from packages.backtesting.alpha_gate_finra_short_interest_source_closeout_probe import (
    FINRA_SHORT_INTEREST_UNDERPOWERED_CANDIDATE,
    FINRAShortInterestSourceCloseoutProbeError,
    collect_finra_source_only_closeout_evidence,
)
from packages.core.settings import AtlasSettings


FINRA_SHORT_INTEREST_CLOSEOUT_CONTRACT = (
    "alpha-gate-finra-short-interest-closeout-v1-"
    "protected-source-insufficient-no-market-outcomes"
)
FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_TARGET_HEAD = (
    "d312ec95752ab49a6fcbec18973faacb96d4aa89"
)
FINRA_SHORT_INTEREST_ACCEPTED_PROBE_HEAD = (
    "5ceac74ad67c8f3539b03192cf1946d51d476434"
)
FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_REPORT_SHA256 = (
    "56479707945a59752aeb2056f3cfbcfd2df1e4a87ada31c9e8e6d3ed93f314cd"
)
FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_ROWS_SHA256 = (
    "21c7dd2e44013ba0f1d290019db70f7b0f23b0603c5e965cbd8b441128190e48"
)
FINRA_SHORT_INTEREST_ACCEPTED_PROBE_EVIDENCE_FINGERPRINT = (
    "c624da82b45fb8d530c2400262598f266ec6309e614a0dcd135b38d9ba5518ce"
)
FINRA_SHORT_INTEREST_ACCEPTED_CLOSEOUT_EVIDENCE_FINGERPRINT = (
    "bdd494a01ed23d891c460e353831cba6f9cf010c5bf38cf1c9c527b4abe8b565"
)
FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_DISPOSITION = (
    "ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT"
)
FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_ROWS = 19_343
FINRA_SHORT_INTEREST_ACCEPTED_DEVELOPMENT_ROWS = 14_841
FINRA_SHORT_INTEREST_ACCEPTED_PROTECTED_ROWS = 4_502
FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_EVENT_ROWS = 257
FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_SIGNAL_SESSIONS = 26
FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_UNIQUE_INSTRUMENTS = 211


class FINRAShortInterestCloseoutError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def validate_finra_source_only_negative_closeout(settings: AtlasSettings) -> dict[str, Any]:
    """Validate the accepted target predictor artifacts only.

    The delegated probe is persisted-artifact-only and performs no FINRA, Massive,
    market-price, benchmark, broker, order, PAPER, LIVE, or automation reads/writes.
    """
    try:
        evidence = collect_finra_source_only_closeout_evidence(settings)
    except FINRAShortInterestSourceCloseoutProbeError as exc:
        raise FINRAShortInterestCloseoutError(str(exc)) from exc

    underpowered = evidence.get("underpowered_protected_source")
    underpowered = underpowered if isinstance(underpowered, dict) else {}
    checks = {
        "scientific_fingerprint_exact": evidence.get("scientific_fingerprint")
        == FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
        "source_disposition_exact": evidence.get("disposition")
        == FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_DISPOSITION,
        "probe_evidence_fingerprint_exact": evidence.get("evidence_fingerprint")
        == FINRA_SHORT_INTEREST_ACCEPTED_PROBE_EVIDENCE_FINGERPRINT,
        "predictor_report_sha_exact": evidence.get("predictor_report_sha256")
        == FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_REPORT_SHA256,
        "predictor_rows_sha_exact": evidence.get("predictor_rows_sha256")
        == FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_ROWS_SHA256,
        "predictor_rows_exact": int(evidence.get("predictor_rows", -1))
        == FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_ROWS,
        "development_rows_exact": int(evidence.get("stage_counts", {}).get("DEVELOPMENT", -1))
        == FINRA_SHORT_INTEREST_ACCEPTED_DEVELOPMENT_ROWS,
        "protected_rows_exact": int(evidence.get("stage_counts", {}).get("PROTECTED", -1))
        == FINRA_SHORT_INTEREST_ACCEPTED_PROTECTED_ROWS,
        "underpowered_candidate_exact": evidence.get("underpowered_candidate")
        == FINRA_SHORT_INTEREST_UNDERPOWERED_CANDIDATE,
        "underpowered_event_rows_exact": int(underpowered.get("event_rows", -1))
        == FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_EVENT_ROWS,
        "underpowered_signal_sessions_exact": int(underpowered.get("signal_sessions", -1))
        == FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_SIGNAL_SESSIONS,
        "underpowered_unique_instruments_exact": int(underpowered.get("unique_instruments", -1))
        == FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_UNIQUE_INSTRUMENTS,
        "failing_gate_exact": evidence.get("failing_gate") == "protected_min_rows",
        "target_outcomes_unread": int(evidence.get("target_outcome_rows_read", -1)) == 0,
        "protected_returns_unread": int(evidence.get("protected_return_rows_read", -1)) == 0,
        "protected_holdout_unconsumed": evidence.get("protected_holdout_consumed") is False,
        "phase33_authority_false": evidence.get("phase33_signal_to_trade_authority") is False,
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise FINRAShortInterestCloseoutError(
            "FINRA source-only negative closeout evidence failed: " + ", ".join(failed)
        )

    closeout_evidence = {
        "closeout_contract": FINRA_SHORT_INTEREST_CLOSEOUT_CONTRACT,
        "accepted_source_target_head": FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_TARGET_HEAD,
        "accepted_probe_head": FINRA_SHORT_INTEREST_ACCEPTED_PROBE_HEAD,
        "scientific_fingerprint": FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
        "predictor_report_sha256": FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_REPORT_SHA256,
        "predictor_rows_sha256": FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_ROWS_SHA256,
        "probe_evidence_fingerprint": FINRA_SHORT_INTEREST_ACCEPTED_PROBE_EVIDENCE_FINGERPRINT,
        "source_disposition": FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_DISPOSITION,
        "underpowered_candidate": FINRA_SHORT_INTEREST_UNDERPOWERED_CANDIDATE,
        "protected_event_rows": FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_EVENT_ROWS,
        "protected_signal_sessions": FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_SIGNAL_SESSIONS,
        "protected_unique_instruments": FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_UNIQUE_INSTRUMENTS,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "historical_supported_alpha": 0,
        "phase33_signal_to_trade_authority": False,
    }
    closeout_fingerprint = _fingerprint(closeout_evidence)
    if closeout_fingerprint != FINRA_SHORT_INTEREST_ACCEPTED_CLOSEOUT_EVIDENCE_FINGERPRINT:
        raise FINRAShortInterestCloseoutError(
            "FINRA closeout evidence fingerprint differs from the accepted target evidence"
        )

    return {
        "contract_version": FINRA_SHORT_INTEREST_CLOSEOUT_CONTRACT,
        "pass": True,
        "disposition": "ACCEPTED_NEGATIVE",
        "source_disposition": FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_DISPOSITION,
        "accepted_source_target_head": FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_TARGET_HEAD,
        "accepted_probe_head": FINRA_SHORT_INTEREST_ACCEPTED_PROBE_HEAD,
        "evidence_fingerprint": closeout_fingerprint,
        "probe_evidence_fingerprint": FINRA_SHORT_INTEREST_ACCEPTED_PROBE_EVIDENCE_FINGERPRINT,
        "checks": checks,
        "historical_supported_alpha": 0,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "phase33_signal_to_trade_authority": False,
        "next_scientific_action": (
            "Define and preregister a materially different economic/information alpha mechanism; "
            "do not prune or retune the accepted-negative FINRA v1 family."
        ),
    }
