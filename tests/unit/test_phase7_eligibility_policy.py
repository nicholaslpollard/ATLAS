from datetime import UTC, datetime

from packages.core.enums import InstrumentIdentityQuality
from packages.schemas.universe import UniverseReasonCode
from packages.universe.eligibility import (
    ACTIVE_UNIVERSE_ELIGIBILITY_POLICY,
    UNIVERSE_ELIGIBILITY_POLICY_VERSION,
    UniverseEligibilityPolicy,
)


def evaluate(**overrides):
    payload = {
        "reference_active": True,
        "delisted_utc": None,
        "market": "stocks",
        "locale": "us",
        "primary_exchange": "XNAS",
        "security_type": "CS",
        "identity_quality": InstrumentIdentityQuality.STRONG,
    }
    payload.update(overrides)
    return ACTIVE_UNIVERSE_ELIGIBILITY_POLICY.evaluate(**payload)


def test_policy_is_bound_to_observed_active_us_exchange_metadata():
    policy = ACTIVE_UNIVERSE_ELIGIBILITY_POLICY
    assert policy.allowed_exchanges == ("ARCX", "BATS", "XASE", "XNAS", "XNYS")
    assert set(policy.allowed_security_types) == {
        "ADRC",
        "CS",
        "ETF",
        "ETN",
        "ETS",
        "ETV",
        "FUND",
        "PFD",
    }
    assert UNIVERSE_ELIGIBILITY_POLICY_VERSION.startswith("universe-eligibility-v1-")


def test_common_stock_etf_and_preferred_are_discovery_eligible():
    for security_type in ("CS", "ETF", "PFD", "ADRC", "FUND", "ETN", "ETS", "ETV"):
        eligible, reasons = evaluate(security_type=security_type)
        assert eligible
        assert reasons == (UniverseReasonCode.ELIGIBLE,)


def test_special_situation_wrappers_are_not_broad_discovery_eligible():
    for security_type in ("WARRANT", "RIGHT", "UNIT", "SP"):
        eligible, reasons = evaluate(security_type=security_type)
        assert not eligible
        assert UniverseReasonCode.UNSUPPORTED_SECURITY_TYPE in reasons


def test_fallback_identity_is_not_admitted_to_broad_discovery():
    eligible, reasons = evaluate(identity_quality=InstrumentIdentityQuality.FALLBACK)
    assert not eligible
    assert UniverseReasonCode.UNSUPPORTED_IDENTITY_QUALITY in reasons


def test_missing_or_unsupported_exchange_is_explicitly_blocked():
    eligible, reasons = evaluate(primary_exchange=None)
    assert not eligible
    assert UniverseReasonCode.MISSING_REFERENCE_METADATA in reasons

    eligible, reasons = evaluate(primary_exchange="OTCX")
    assert not eligible
    assert UniverseReasonCode.UNSUPPORTED_EXCHANGE in reasons


def test_reference_and_data_health_blocks_are_independent_and_auditable():
    eligible, reasons = evaluate(
        reference_active=False,
        delisted_utc=datetime(2026, 8, 1, tzinfo=UTC),
        data_available=False,
        data_quarantined=True,
        manual_exclude=True,
    )
    assert not eligible
    assert set(reasons) >= {
        UniverseReasonCode.REFERENCE_INACTIVE,
        UniverseReasonCode.REFERENCE_DELISTED,
        UniverseReasonCode.DATA_UNAVAILABLE,
        UniverseReasonCode.DATA_QUARANTINED,
        UniverseReasonCode.MANUAL_EXCLUDE,
    }


def test_policy_fingerprint_is_deterministic_and_semantic():
    first = UniverseEligibilityPolicy()
    second = UniverseEligibilityPolicy()
    assert first.fingerprint == second.fingerprint
    changed = UniverseEligibilityPolicy(allowed_security_types=("CS",))
    assert changed.fingerprint != first.fingerprint
