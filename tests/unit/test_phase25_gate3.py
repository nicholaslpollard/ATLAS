from __future__ import annotations

import pytest

from packages.backtesting.phase25_gate3 import observed_page_bounds, projected_request_bounds
from packages.backtesting.phase25_policy import (
    PHASE25_GATE3_ACTIVE,
    PHASE25_GATE3_EARLIEST_SESSION_ENTITLEMENT_PROBE_REQUIRED,
    PHASE25_GATE3_ENDPOINT,
    PHASE25_GATE3_EXISTING_VALID_REFERENCE_PRESERVED,
    PHASE25_GATE3_FORCE_REPLACE_EXISTING_REFERENCE,
    PHASE25_GATE3_INCLUDE_INACTIVE,
    PHASE25_GATE3_MARKET,
    PHASE25_GATE3_PAGE_LIMIT,
    PHASE25_GATE3_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED,
    PHASE25_PROVIDER_READS,
    phase25_gate0_policy_fingerprint,
    phase25_gate1_policy_fingerprint,
    phase25_gate2_policy_fingerprint,
    phase25_gate3_policy_fingerprint,
)


def test_gate3_observed_page_bounds_match_gate2_target_scale() -> None:
    active_rows = [9403, 12066, 12071, 12078, 12085, 12088, 12092]
    assert observed_page_bounds(active_rows, page_limit=1000) == (10, 13)
    assert projected_request_bounds(
        missing_sessions=1253,
        observed_min_pages=10,
        observed_max_pages=13,
    ) == (12530, 16289)


def test_gate3_request_bounds_fail_closed_on_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        observed_page_bounds([], page_limit=1000)
    with pytest.raises(ValueError):
        observed_page_bounds([100], page_limit=0)
    with pytest.raises(ValueError):
        projected_request_bounds(
            missing_sessions=-1,
            observed_min_pages=10,
            observed_max_pages=13,
        )


def test_gate3_policy_is_provider_free_and_exact_active_only() -> None:
    assert PHASE25_PROVIDER_READS == 0
    assert PHASE25_GATE3_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED is False
    assert PHASE25_GATE3_ENDPOINT == "/v3/reference/tickers"
    assert PHASE25_GATE3_MARKET == "stocks"
    assert PHASE25_GATE3_ACTIVE is True
    assert PHASE25_GATE3_PAGE_LIMIT == 1000
    assert PHASE25_GATE3_INCLUDE_INACTIVE is False
    assert PHASE25_GATE3_FORCE_REPLACE_EXISTING_REFERENCE is False
    assert PHASE25_GATE3_EXISTING_VALID_REFERENCE_PRESERVED is True
    assert PHASE25_GATE3_EARLIEST_SESSION_ENTITLEMENT_PROBE_REQUIRED is True
    assert len(phase25_gate3_policy_fingerprint()) == 64


def test_gate3_addition_does_not_change_accepted_prior_policy_fingerprints() -> None:
    assert (
        phase25_gate0_policy_fingerprint()
        == "994b05f2bc7fd8329578e0ca2a621de2602d2d71e7f8c06101a22b9ca9468604"
    )
    assert (
        phase25_gate1_policy_fingerprint()
        == "1c134efdb64ad8ccd527be2ca870d5f3eddba3f6538654e68ca06f0aa4f64207"
    )
    assert (
        phase25_gate2_policy_fingerprint()
        == "417ef8af0b463a6983e6b54cfb510d8f556245c87818f8b8e24d90737049f083"
    )
