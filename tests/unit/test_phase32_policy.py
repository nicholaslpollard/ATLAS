from __future__ import annotations

import exchange_calendars as xcals

from packages.backtesting.phase32_policy import (
    PHASE32_CANDIDATES,
    PHASE32_DEVELOPMENT_LAST_SIGNAL,
    PHASE32_INSTRUMENT_ALLOWED_IDENTITY_QUALITIES,
    PHASE32_INSTRUMENT_IDENTITY_CONTRACT_VERSION,
    PHASE32_INSTRUMENT_MEDIUM_IDENTITY_RULE,
    PHASE32_INTERNAL_PURGE_SESSIONS,
    PHASE32_MULTIPLE_TESTING_METHOD,
    PHASE32_OUTCOME_HORIZON_SESSIONS,
    PHASE32_PROTECTED_LAST_SIGNAL,
    PHASE32_PROTECTED_OUTCOME_END,
    PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED,
    phase32_candidate_ids,
    phase32_policy_fingerprint,
)
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION


EXPECTED_FINGERPRINT = "4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7"
EXPECTED_CANDIDATES = (
    "equity_issuance_short",
    "share_repurchase_long",
    "financial_integrity_adverse_short",
    "listing_distress_short",
    "solvency_distress_short",
)


def test_phase32_policy_fingerprint_and_family_are_frozen() -> None:
    assert phase32_policy_fingerprint() == EXPECTED_FINGERPRINT
    assert phase32_candidate_ids() == EXPECTED_CANDIDATES
    assert len(PHASE32_CANDIDATES) == 5
    assert PHASE32_OUTCOME_HORIZON_SESSIONS == 5
    assert PHASE32_INTERNAL_PURGE_SESSIONS == 5
    assert PHASE32_MULTIPLE_TESTING_METHOD == "HOLM_BONFERRONI_GLOBAL_5"
    assert PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED is False


def test_phase32_policy_is_bound_to_accepted_identity_v4() -> None:
    assert PHASE32_INSTRUMENT_IDENTITY_CONTRACT_VERSION == IDENTITY_CONTRACT_VERSION
    assert PHASE32_INSTRUMENT_IDENTITY_CONTRACT_VERSION == (
        "instrument-identity-v4-no-issuer-level-medium-collapse"
    )
    assert PHASE32_INSTRUMENT_ALLOWED_IDENTITY_QUALITIES == ("strong", "medium")
    assert PHASE32_INSTRUMENT_MEDIUM_IDENTITY_RULE == (
        "CIK_PLUS_EXACT_PROVIDER_NATIVE_TICKER_PLUS_PRIMARY_EXCHANGE_PLUS_SECURITY_TYPE"
    )


def test_phase32_candidate_taxonomy_is_exact_and_directional() -> None:
    by_id = {candidate.candidate_id: candidate for candidate in PHASE32_CANDIDATES}
    assert by_id["share_repurchase_long"].direction == "LONG"
    assert by_id["share_repurchase_long"].taxonomy_triples == (
        ("capital_and_financing", "shareholder_returns", "share_repurchase_program"),
    )
    assert by_id["equity_issuance_short"].direction == "SHORT"
    assert by_id["listing_distress_short"].direction == "SHORT"
    assert (
        "regulatory_and_compliance",
        "exchange_listing",
        "listing_compliance_regained",
    ) not in by_id["listing_distress_short"].taxonomy_triples
    assert by_id["financial_integrity_adverse_short"].probe_census_rows == 53
    assert by_id["solvency_distress_short"].probe_census_rows == 64


def test_phase32_five_session_outer_boundaries_are_calendar_exact() -> None:
    calendar = xcals.get_calendar("XNYS")
    development_path = calendar.sessions_in_range(PHASE32_DEVELOPMENT_LAST_SIGNAL, "2026-05-11")
    protected_path = calendar.sessions_in_range(PHASE32_PROTECTED_LAST_SIGNAL, PHASE32_PROTECTED_OUTCOME_END)
    assert development_path.strftime("%Y-%m-%d").tolist() == [
        "2026-05-04",
        "2026-05-05",
        "2026-05-06",
        "2026-05-07",
        "2026-05-08",
        "2026-05-11",
    ]
    assert protected_path.strftime("%Y-%m-%d").tolist() == [
        "2026-08-04",
        "2026-08-05",
        "2026-08-06",
        "2026-08-07",
        "2026-08-10",
        "2026-08-11",
    ]
