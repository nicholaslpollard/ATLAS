from __future__ import annotations

from packages.core.enums import InstrumentIdentityQuality
from packages.ml.identity_probe import (
    AUTHORITATIVE_INTERVAL,
    ML_HISTORICAL_IDENTITY_PROBE_CONTRACT_VERSION,
    UNIQUE_REFERENCE_NO_REUSE,
    UNMAPPED_REFERENCE,
    UNRESOLVED_FALLBACK_IDENTITY,
    UNRESOLVED_METADATA_CONFLICT,
    UNRESOLVED_MULTI_REFERENCE,
    UNRESOLVED_TICKER_REUSE,
    identity_status,
    structural_eligibility_reasons,
)


def test_phase10_historical_identity_probe_contract() -> None:
    assert ML_HISTORICAL_IDENTITY_PROBE_CONTRACT_VERSION == (
        "ml-historical-identity-probe-v1-authority-unique-reference-structural-eligibility"
    )


def test_authoritative_interval_wins_over_reuse_and_reference_ambiguity() -> None:
    assert (
        identity_status(
            authoritative_interval_count=1,
            reference_identity_count=2,
            reuse_identity_count=3,
            identity_quality=InstrumentIdentityQuality.STRONG.value,
            metadata_conflict=True,
        )
        == AUTHORITATIVE_INTERVAL
    )


def test_unique_strong_or_medium_reference_is_safe_only_without_reuse() -> None:
    for quality in (
        InstrumentIdentityQuality.STRONG.value,
        InstrumentIdentityQuality.MEDIUM.value,
    ):
        assert (
            identity_status(
                authoritative_interval_count=0,
                reference_identity_count=1,
                reuse_identity_count=1,
                identity_quality=quality,
                metadata_conflict=False,
            )
            == UNIQUE_REFERENCE_NO_REUSE
        )
    assert (
        identity_status(
            authoritative_interval_count=0,
            reference_identity_count=1,
            reuse_identity_count=2,
            identity_quality=InstrumentIdentityQuality.STRONG.value,
            metadata_conflict=False,
        )
        == UNRESOLVED_TICKER_REUSE
    )


def test_unresolved_identity_classes_are_conservative() -> None:
    assert (
        identity_status(
            authoritative_interval_count=0,
            reference_identity_count=0,
            reuse_identity_count=0,
            identity_quality=None,
            metadata_conflict=False,
        )
        == UNMAPPED_REFERENCE
    )
    assert (
        identity_status(
            authoritative_interval_count=0,
            reference_identity_count=2,
            reuse_identity_count=1,
            identity_quality=InstrumentIdentityQuality.STRONG.value,
            metadata_conflict=False,
        )
        == UNRESOLVED_MULTI_REFERENCE
    )
    assert (
        identity_status(
            authoritative_interval_count=0,
            reference_identity_count=1,
            reuse_identity_count=1,
            identity_quality=InstrumentIdentityQuality.FALLBACK.value,
            metadata_conflict=False,
        )
        == UNRESOLVED_FALLBACK_IDENTITY
    )
    assert (
        identity_status(
            authoritative_interval_count=2,
            reference_identity_count=1,
            reuse_identity_count=1,
            identity_quality=InstrumentIdentityQuality.STRONG.value,
            metadata_conflict=False,
        )
        == UNRESOLVED_METADATA_CONFLICT
    )


def test_structural_eligibility_ignores_current_active_delisted_state() -> None:
    assert (
        structural_eligibility_reasons(
            market="stocks",
            locale="us",
            primary_exchange="XNAS",
            security_type="CS",
        )
        == ()
    )
    reasons = structural_eligibility_reasons(
        market="stocks",
        locale="us",
        primary_exchange="OTC",
        security_type="WARRANT",
    )
    assert "UNSUPPORTED_EXCHANGE" in reasons
    assert "UNSUPPORTED_SECURITY_TYPE" in reasons
