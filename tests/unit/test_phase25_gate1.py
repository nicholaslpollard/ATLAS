from __future__ import annotations

from packages.backtesting.phase25_gate1 import classify_symbol_evidence
from packages.backtesting.phase25_policy import (
    PHASE25_EXACT_PIT_REFERENCE_REQUIRED_FOR_AUTHORITATIVE_PHASE7_REPLAY,
    PHASE25_FUTURE_REFERENCE_METADATA_AUTHORITY_ALLOWED,
    PHASE25_PROVIDER_READS,
    PHASE25_PROXY_UNIVERSE_SUPPORT_AUTHORITY_ALLOWED,
    phase25_gate1_policy_fingerprint,
)


def test_gate1_exact_first_seen_reference_classification() -> None:
    category, interval, bracketed = classify_symbol_evidence(
        reference_observation_count=2,
        reference_instrument_count=1,
        exact_first_seen_reference_count=1,
        exact_first_seen_classifiable_count=1,
        prior_or_same_reference_count=1,
        future_reference_count=1,
        metadata_variant_count=1,
        authoritative_interval_instrument_count=1,
    )
    assert category == "EXACT_FIRST_SEEN_REFERENCE"
    assert interval is True
    assert bracketed is True


def test_gate1_future_only_reference_never_becomes_authoritative() -> None:
    category, interval, bracketed = classify_symbol_evidence(
        reference_observation_count=3,
        reference_instrument_count=1,
        exact_first_seen_reference_count=0,
        exact_first_seen_classifiable_count=0,
        prior_or_same_reference_count=0,
        future_reference_count=3,
        metadata_variant_count=1,
        authoritative_interval_instrument_count=1,
    )
    assert category == "FUTURE_ONLY_REFERENCE"
    assert interval is True
    assert bracketed is False
    assert PHASE25_FUTURE_REFERENCE_METADATA_AUTHORITY_ALLOWED is False


def test_gate1_ambiguous_identity_fails_closed() -> None:
    category, interval, bracketed = classify_symbol_evidence(
        reference_observation_count=4,
        reference_instrument_count=2,
        exact_first_seen_reference_count=1,
        exact_first_seen_classifiable_count=1,
        prior_or_same_reference_count=2,
        future_reference_count=2,
        metadata_variant_count=1,
        authoritative_interval_instrument_count=2,
    )
    assert category == "AMBIGUOUS_LOCAL_IDENTITY"
    assert interval is False
    assert bracketed is False


def test_gate1_prior_reference_can_only_be_proxy_candidate_when_bracketed() -> None:
    category, interval, bracketed = classify_symbol_evidence(
        reference_observation_count=2,
        reference_instrument_count=1,
        exact_first_seen_reference_count=0,
        exact_first_seen_classifiable_count=0,
        prior_or_same_reference_count=1,
        future_reference_count=1,
        metadata_variant_count=1,
        authoritative_interval_instrument_count=1,
    )
    assert category == "PRIOR_REFERENCE_ONLY"
    assert interval is True
    assert bracketed is True
    assert PHASE25_PROXY_UNIVERSE_SUPPORT_AUTHORITY_ALLOWED is False


def test_gate1_policy_keeps_authority_zero_and_exact_pit_required() -> None:
    assert PHASE25_PROVIDER_READS == 0
    assert PHASE25_FUTURE_REFERENCE_METADATA_AUTHORITY_ALLOWED is False
    assert PHASE25_PROXY_UNIVERSE_SUPPORT_AUTHORITY_ALLOWED is False
    assert PHASE25_EXACT_PIT_REFERENCE_REQUIRED_FOR_AUTHORITATIVE_PHASE7_REPLAY is True
    assert len(phase25_gate1_policy_fingerprint()) == 64
