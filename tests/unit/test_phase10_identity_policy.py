from packages.ml.identity_policy import (
    CURRENT_ACTIVE_FILTER_USED,
    CURRENT_DELISTED_FILTER_USED,
    CURRENT_ROUTE_FILTER_USED,
    HISTORICAL_IDENTITY_SAFE_STATUSES,
    ML_HISTORICAL_IDENTITY_POLICY_CONTRACT_VERSION,
    TICKER_TEXT_SPLICING_ALLOWED,
    historical_identity_safe,
    historical_observation_eligible,
)
from packages.ml.identity_probe import (
    AUTHORITATIVE_INTERVAL,
    UNIQUE_REFERENCE_NO_REUSE,
    UNRESOLVED_TICKER_REUSE,
)


def test_phase10_identity_policy_contract_is_explicit() -> None:
    assert ML_HISTORICAL_IDENTITY_POLICY_CONTRACT_VERSION == (
        "ml-historical-identity-policy-v1-authoritative-or-unique-no-reuse-structural"
    )


def test_phase10_identity_policy_accepts_only_safe_identity_classes() -> None:
    assert HISTORICAL_IDENTITY_SAFE_STATUSES == (
        AUTHORITATIVE_INTERVAL,
        UNIQUE_REFERENCE_NO_REUSE,
    )
    assert historical_identity_safe(AUTHORITATIVE_INTERVAL)
    assert historical_identity_safe(UNIQUE_REFERENCE_NO_REUSE)
    assert not historical_identity_safe(UNRESOLVED_TICKER_REUSE)


def test_phase10_identity_policy_requires_structural_eligibility() -> None:
    assert historical_observation_eligible(
        identity_status=AUTHORITATIVE_INTERVAL,
        structural_exclusion_reasons=(),
    )
    assert not historical_observation_eligible(
        identity_status=AUTHORITATIVE_INTERVAL,
        structural_exclusion_reasons=("UNSUPPORTED_SECURITY_TYPE",),
    )


def test_phase10_identity_policy_never_uses_current_membership_or_splicing() -> None:
    assert CURRENT_ROUTE_FILTER_USED is False
    assert CURRENT_ACTIVE_FILTER_USED is False
    assert CURRENT_DELISTED_FILTER_USED is False
    assert TICKER_TEXT_SPLICING_ALLOWED is False
